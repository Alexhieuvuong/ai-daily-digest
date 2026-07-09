"""
Nhận định xu hướng thị trường — LLM call THỨ HAI, chạy sau summarize().

Chỉ chạy ở bản tin ĐẦU TIÊN của mỗi ngày (giờ VN); tổng hợp tin Kinh tế +
Chứng khoán VN của ~7 ngày qua (đọc lại daily/*.md) cộng tin mới hôm nay,
rồi viết nhận định dạng KỊCH BẢN (không dự đoán giá/điểm cụ thể).

Lỗi ở bước này KHÔNG được làm hỏng bản tin chính: generate_outlook() nuốt
mọi exception và trả về None — digest vẫn gửi như bình thường.
"""

import os
from datetime import timedelta
from pathlib import Path

from summarize import _post_with_retry
from generate_site import parse_digest

# Tiêu đề do CODE thêm vào (không phải model) để parser của trang tĩnh
# nhận diện chắc chắn (match "🧭"/"xu hướng" trong generate_site.parse_digest).
OUTLOOK_HEADING = "### 🧭 Nhận định xu hướng"

# Khớp với cat_type() của generate_site và item['category'] của sources.
FINANCE_TYPES = {"kinh_te", "chung_khoan_vn"}

HISTORY_DAYS = 7          # cửa sổ lịch sử đọc từ daily/*.md
MAX_HISTORY_LINES = 80    # trần số dòng lịch sử đưa vào prompt (bỏ dòng cũ nhất trước)
DESC_CHARS = 200          # cắt mô tả mỗi tin để tiết kiệm token


SYSTEM_PROMPT = """Bạn là chuyên gia phân tích thị trường tài chính kỳ cựu, viết tiếng Việt súc tích.
Nhiệm vụ: nhận định XU HƯỚNG dạng kịch bản dựa trên dòng tin kinh tế & chứng khoán 7 ngày qua.
Quy tắc:
- CHỈ dùng dữ kiện trong tin được cung cấp, TUYỆT ĐỐI không bịa số liệu.
- KHÔNG dự đoán giá/điểm số cụ thể, KHÔNG khuyến nghị mua/bán mã nào.
- Nhận định theo kịch bản: xu hướng nghiêng về đâu + điều kiện xác nhận/đảo chiều.
- Văn phong khách quan, thận trọng, không giật gân."""


def is_first_send_of_day(root: Path, date_str: str) -> bool:
    """True nếu hôm nay (ngày VN) chưa có bản tin nào được lưu.

    Dựa vào file daily/{date}-HHMM.md: workflow chỉ commit khi gửi thành công,
    run lỗi không commit — nên glob này phản ánh đúng "đã gửi hôm nay chưa".
    (sent_slots key theo ngày Rome, khung đêm rơi sang ngày VN hôm sau nên
    không dùng được cho câu hỏi này.)
    """
    if os.environ.get("OUTLOOK_FORCE", "") == "1":
        return True
    return not any((root / "daily").glob(f"{date_str}-*.md"))


def _load_history(root: Path, now) -> list:
    """Trích tin tài chính từ daily/*.md trong HISTORY_DAYS ngày gần nhất.

    Mỗi tin thành một dòng `- [YYYY-MM-DD] (★★★) Tiêu đề — mô tả`, sắp xếp
    cũ → mới; nếu vượt MAX_HISTORY_LINES thì bỏ bớt dòng CŨ nhất.
    """
    daily_dir = root / "daily"
    if not daily_dir.is_dir():
        return []
    cutoff = (now - timedelta(days=HISTORY_DAYS)).date().isoformat()
    lines = []
    for path in sorted(daily_dir.glob("*.md")):
        day = path.stem[:10]  # slug = YYYY-MM-DD-HHMM
        if day < cutoff:
            continue
        try:
            parsed = parse_digest(path.read_text(encoding="utf-8"))
        except Exception:
            continue  # file hỏng/không đúng định dạng — bỏ qua, không chặn cả pipeline
        for cat in parsed.get("categories", []):
            if cat.get("type") not in FINANCE_TYPES:
                continue
            for it in cat.get("items", []):
                desc = (it.get("desc") or "")[:DESC_CHARS]
                stars = "★" * it.get("star_count", 0)
                lines.append(f"- [{day}] ({stars}) {it.get('title', '')} — {desc}")
    return lines[-MAX_HISTORY_LINES:]


def _fresh_block(items: list) -> list:
    """Tin mới hôm nay (buffer pending) thuộc 2 nhóm tài chính."""
    lines = []
    for it in items:
        if it.get("category") not in FINANCE_TYPES:
            continue
        summary = (it.get("summary") or "")[:DESC_CHARS]
        lines.append(f"- {it.get('title', '')} ({it.get('source', '')}): {summary}")
    return lines


def _build_user_prompt(history_lines, fresh_lines, date_str) -> str:
    history = "\n".join(history_lines) or "(không có dữ liệu)"
    fresh = "\n".join(fresh_lines) or "(không có tin mới)"
    return f"""Hôm nay {date_str}. Dữ liệu gồm tin kinh tế & chứng khoán 7 ngày qua (đã tóm tắt, ★ = mức quan trọng) và tin mới hôm nay.

## TIN 7 NGÀY QUA
{history}

## TIN MỚI HÔM NAY
{fresh}

Viết ĐÚNG cấu trúc Markdown sau, KHÔNG thêm tiêu đề `#` nào khác:

**Tín hiệu 7 ngày qua**
- <2-3 bullet, mỗi bullet 1-2 câu tổng hợp tín hiệu nổi bật>

**Xu hướng nghiêng về:** <tích cực / thận trọng / trung lập> — <2-3 câu lý do>

**Cần theo dõi**
- <2-3 bullet: yếu tố sẽ XÁC NHẬN hoặc ĐẢO CHIỀU xu hướng trên>

_Nhận định tự động, không phải khuyến nghị đầu tư._"""


def generate_outlook(fresh_items: list, now, root: Path):
    """Trả về section markdown (bắt đầu bằng OUTLOOK_HEADING) hoặc None.

    KHÔNG BAO GIỜ raise — nhận định là phần phụ, bản tin chính vẫn phải gửi.
    """
    if os.environ.get("OUTLOOK_DISABLE", "") == "1":
        print("  Nhận định xu hướng: tắt qua OUTLOOK_DISABLE=1 — bỏ qua.")
        return None
    try:
        history_lines = _load_history(root, now)
        fresh_lines = _fresh_block(fresh_items)
        if not history_lines and not fresh_lines:
            print("  Nhận định xu hướng: không có tin tài chính nào — bỏ qua.")
            return None

        api_key = os.environ.get("API_KEY")
        if not api_key:
            raise ValueError("API_KEY environment variable is required")
        base_url = os.environ.get("API_BASE_URL", "https://api.deepseek.com")
        model = os.environ.get("API_MODEL", "deepseek-chat")

        date_str = now.strftime("%Y-%m-%d")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",
                 "content": _build_user_prompt(history_lines, fresh_lines, date_str)},
            ],
            # Nhiệt độ thấp: cần nhất quán/phân tích, không cần sáng tạo.
            "temperature": 0.3,
            "max_tokens": 1200,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        print(f"  Nhận định xu hướng: gọi {model} "
              f"({len(history_lines)} dòng lịch sử + {len(fresh_lines)} tin mới)...")
        result = _post_with_retry(f"{base_url}/chat/completions", headers, payload)
        choices = result.get("choices") or []
        content = (choices[0].get("message") or {}).get("content") if choices else None
        if not content:
            raise ValueError(f"API trả về không có choices/content: {str(result)[:300]}")
        return f"{OUTLOOK_HEADING}\n\n{content.strip()}"
    except Exception as e:  # nuốt mọi lỗi — chỉ cảnh báo trên log GitHub Actions
        print(f"::warning::Nhận định xu hướng thất bại (bỏ qua, digest vẫn gửi): {e}")
        return None


def append_outlook(markdown: str, outlook_md: str) -> str:
    """Chèn section TRƯỚC footer `---\\n*Tạo tự động...` của _wrap(); fallback: nối cuối."""
    parts = markdown.rsplit("\n---\n", 1)
    if len(parts) == 2:
        return f"{parts[0]}\n\n{outlook_md}\n\n---\n{parts[1]}"
    return f"{markdown}\n\n{outlook_md}\n"
