"""
Tóm tắt tin bằng tiếng Việt — dùng API tương thích OpenAI (DeepSeek mặc định,
hoặc OpenAI / OpenRouter cho Claude).

Khác bản gốc (song ngữ Trung/Anh, nhóm news/papers/projects):
- Nhận danh sách item PHẲNG đã khử trùng lặp (mỗi item có 'category' + 'category_label').
- Gom nhóm theo 3 category: Việt Nam / Kinh tế / Công nghệ.
- Trả về MỘT bản markdown tiếng Việt.
"""

import json
import os
import time
from collections import OrderedDict

import requests

from sources import CATEGORIES, DEFAULT_MAX_ITEMS

# Trần số bài mỗi nguồn được đưa vào pool ứng viên CHO MỖI category (chỉ áp dụng khi
# category có >1 nguồn), để LLM không chỉ thấy toàn tin của một đầu báo (vd CNBC) rồi
# chọn lệch hẳn về nguồn đó. Category 1 nguồn không cần cân bằng nên bỏ qua.
PER_SOURCE_CAP = int(os.environ.get("DIGEST_PER_SOURCE_CAP", "4"))


SYSTEM_PROMPT = """Bạn là một biên tập viên tin tức kỳ cựu, viết bằng tiếng Việt tự nhiên, súc tích.
Nhiệm vụ: từ danh sách bài thô, CHỌN LỌC những tin đáng chú ý nhất và viết bản tin tóm tắt.
Quy tắc:
- Chỉ dùng thông tin có trong bài, TUYỆT ĐỐI không bịa.
- Số mục tối đa của MỖI category được ghi rõ trong phần yêu cầu bên dưới; gộp các bài cùng chủ đề thành một mục.
- Mỗi mục: 2-3 câu tiếng Việt, nêu vì sao đáng chú ý, kèm link gốc.
- Gắn mức quan trọng theo thang hiệu ứng/độ phủ (đừng lạm phát sao):
  ★★★★★ = sự kiện lớn tầm quốc gia/toàn cầu, ảnh hưởng nhiều người (chính sách lớn, vĩ mô, khủng hoảng).
  ★★★★☆ = quan trọng, tác động rộng tới một ngành/khu vực.
  ★★★☆☆ = đáng chú ý nhưng phạm vi vừa.
  ★★☆☆☆ = tin địa phương/ngách, tai nạn lẻ, sắc màu đời sống.
  ★☆☆☆☆ = bên lề, ít hệ quả.
- Cuối bản tin thêm mục "Quan sát hôm nay": 2-3 câu nhận định xu hướng.
- Output Markdown, đúng cấu trúc category được yêu cầu."""


def _group_by_category(items):
    """Gom item phẳng thành dict {cat_key: [items]} theo đúng thứ tự CATEGORIES."""
    grouped = {key: [] for key in CATEGORIES}
    for it in items:
        cat = it.get("category")
        if cat in grouped:
            grouped[cat].append(it)
        else:  # category lạ — vẫn giữ để không mất tin
            grouped.setdefault(cat, []).append(it)
    # bỏ category rỗng
    return {k: v for k, v in grouped.items() if v}


def _balance_by_source(items, cap=PER_SOURCE_CAP):
    """Round-robin theo nguồn + cap mỗi nguồn, để pool ứng viên cân bằng giữa các báo.

    Giữ thứ tự xuất hiện ban đầu trong mỗi nguồn; lấy lần lượt một bài mỗi nguồn cho tới
    khi cạn hoặc chạm `cap`. Nhờ vậy các nguồn ít tin vẫn lọt vào tầm chọn của LLM thay
    vì bị một đầu báo nhiều tin lấn át.
    """
    by_source = OrderedDict()
    for it in items:
        by_source.setdefault(it.get("source", ""), []).append(it)
    queues = [lst[:cap] for lst in by_source.values()]
    out = []
    i = 0
    while any(i < len(q) for q in queues):
        for q in queues:
            if i < len(q):
                out.append(q[i])
        i += 1
    return out


def _max_items_for(key):
    return CATEGORIES.get(key, {}).get("max_items", DEFAULT_MAX_ITEMS)


def _build_user_prompt(grouped, date_str):
    # Dữ liệu được TÁCH SẴN theo nhóm (mỗi nhóm một khối JSON riêng) thay vì một danh
    # sách phẳng, để model không tự xếp lại bài theo chủ đề — vd đẩy tin vĩ mô CafeF
    # sang nhóm "Việt Nam". Cân bằng nguồn trong từng nhóm (chỉ khi >1 nguồn).
    labels = []
    blocks = []
    for key, items in grouped.items():
        label = items[0].get("category_label") or CATEGORIES.get(key, {}).get("label", key)
        max_items = _max_items_for(key)
        labels.append(f"{label} — tối đa {max_items} mục")
        n_sources = len({it.get("source", "") for it in items})
        candidates = _balance_by_source(items) if n_sources > 1 else items
        payload = [
            {
                "title": it.get("title", ""),
                "url": it.get("url", ""),
                "summary": (it.get("summary") or "")[:500],
                "source": it.get("source", ""),
            }
            for it in candidates
        ]
        blocks.append(
            f"### NHÓM «{label}» (chọn tối đa {max_items} mục, CHỈ từ các bài dưới đây)\n"
            + json.dumps(payload, ensure_ascii=False, indent=2)
        )
    labels_block = "\n".join(f"- {lb}" for lb in labels)
    data_block = "\n\n".join(blocks)

    return f"""Hôm nay {date_str}. Tạo bản digest gồm ĐÚNG các nhóm sau, đúng thứ tự:
{labels_block}

QUY TẮC PHÂN NHÓM (bắt buộc):
- Mỗi bài CHỈ được tóm tắt trong nhóm mà nó được liệt kê bên dưới; TUYỆT ĐỐI không chuyển bài sang nhóm khác dù chủ đề có vẻ hợp nhóm khác.
- KHÔNG tạo nhóm mới và KHÔNG bỏ nhóm nào trong danh sách trên (nếu một nhóm không có bài thì ghi "_Không có tin mới._").

Dữ liệu thô, ĐÃ TÁCH theo nhóm:
{data_block}

Định dạng output cho mỗi mục (SỐ THỨ TỰ nằm TRONG phần tiêu đề in đậm, đánh số lại từ 1 trong mỗi nhóm; ba dòng Quan trọng/Vì sao/Nguồn KHÔNG đánh số và KHÔNG dùng dấu gạch đầu dòng; phân tách các mục bằng một dòng chỉ chứa `___`):
**1. <Tiêu đề tóm tắt>**: <2-3 câu>.
Quan trọng: ★★★☆☆
Vì sao: <ngắn gọn>
Nguồn: [<source>](<url>)
___

Dùng tiêu đề `## <category_label>` (đúng nhãn nhóm ở trên) cho mỗi nhóm, và `### Quan sát hôm nay` cho phần nhận định cuối."""


def _wrap(text, date_str, model):
    return f"""# Bản tin tổng hợp · {date_str}

{text}

---
*Tạo tự động bởi AI Daily Digest dùng {model}*
"""


def summarize(items, date_str):
    """Tạo digest tiếng Việt từ danh sách item đã khử trùng lặp.

    `items`: list phẳng, mỗi item có 'category' / 'category_label'.
    Trả về MỘT chuỗi markdown.
    """
    api_key = os.environ.get("API_KEY")
    if not api_key:
        raise ValueError("API_KEY environment variable is required")

    base_url = os.environ.get("API_BASE_URL", "https://api.deepseek.com")
    model = os.environ.get("API_MODEL", "deepseek-chat")

    grouped = _group_by_category(items)
    if not grouped:
        return f"# Bản tin tổng hợp · {date_str}\n\n> Không có tin mới hôm nay.\n"

    user_prompt = _build_user_prompt(grouped, date_str)

    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 8192,
    }

    print(f"Calling {model}...")
    result = _post_with_retry(url, headers, payload)
    text = result["choices"][0]["message"]["content"].strip()
    return _wrap(text, date_str, model)


# Số lần thử lại + khoảng chờ tối đa khi gặp 429 / 5xx (free model hay bị rate-limit).
MAX_RETRIES = 5
MAX_BACKOFF = 60


def _post_with_retry(url, headers, payload):
    """POST có retry với backoff, tôn trọng header Retry-After khi bị 429/5xx."""
    last_exc = None
    for attempt in range(MAX_RETRIES):
        resp = requests.post(url, headers=headers, json=payload, timeout=180)
        if resp.status_code == 429 or resp.status_code >= 500:
            # Ưu tiên Retry-After (giây) nếu nhà cung cấp trả về, nếu không thì backoff mũ.
            retry_after = resp.headers.get("Retry-After")
            try:
                wait = float(retry_after) if retry_after else 2 ** attempt
            except ValueError:
                wait = 2 ** attempt
            wait = min(wait, MAX_BACKOFF) + 1
            last_exc = requests.exceptions.HTTPError(
                f"{resp.status_code} từ API", response=resp
            )
            if attempt < MAX_RETRIES - 1:
                print(f"  [retry] {resp.status_code} — chờ {wait:.0f}s rồi thử lại "
                      f"(lần {attempt + 1}/{MAX_RETRIES})...")
                time.sleep(wait)
                continue
            raise last_exc
        resp.raise_for_status()
        return resp.json()
    raise last_exc
