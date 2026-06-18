"""
dedup.py — khử trùng lặp ĐA TẦNG (pure Python, không dùng LLM).

Mục tiêu: đảm bảo MỘT bài không bao giờ được gửi hai lần trong cửa sổ trượt 24 giờ.
Trạng thái lưu ở data/sent_state.json (được workflow commit ngược repo để giữ qua các
lần Actions chạy). Mọi mốc thời gian + ranh giới "ngày" dùng Asia/Ho_Chi_Minh.

Ba tầng lọc (chạy theo thứ tự, thuần Python):
  1. URL chuẩn hóa  — bỏ utm_*/tham số tracking, bỏ #fragment, bỏ "/" cuối, hạ host.
  2. Content hash   — sha256(tiêu_đề_chuẩn_hóa + 200 ký tự đầu của body).
  3. Gần trùng      — rapidfuzz token_set_ratio trên (tiêu đề + lead), ngưỡng ~0.80.

Cấu trúc state (keyed theo ngày VN, rồi theo content hash):
    {
      "2026-06-18": {
        "<hash>": {"url","title","source","lead","sent_at"}
      }
    }

Tích hợp main.py:
    from dedup import load_state, filter_new_articles, save_state
    state = load_state()
    new_items = filter_new_articles(fetch_all(), state)   # đã ghi survivors vào state
    if not new_items: return
    ... gửi new_items ...
    save_state(state)                                     # prune + lưu xuống đĩa
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

try:  # zoneinfo có sẵn từ Python 3.9
    from zoneinfo import ZoneInfo
    VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
except Exception:  # fallback: UTC+7 cố định (VN không có DST nên tương đương)
    VN_TZ = timezone(timedelta(hours=7))

from rapidfuzz import fuzz


STATE_PATH = os.environ.get("SENT_STATE_PATH", "data/sent_state.json")
WINDOW_HOURS = 24
NEAR_DUP_THRESHOLD = 0.80
BODY_CHARS = 200  # số ký tự đầu của body đưa vào content hash / lead

# Tham số query mang tính tracking — loại bỏ khi chuẩn hóa URL.
_TRACKING_PARAMS = {
    "gclid", "fbclid", "mc_cid", "mc_eid", "ref", "ref_src", "igshid",
    "spm", "cmpid", "cid", "yclid", "_hsenc", "_hsmi", "vero_id",
}

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)  # giữ chữ có dấu tiếng Việt
_WS_RE = re.compile(r"\s+")


# ── Chuẩn hóa ────────────────────────────────────────────────────────────────

def _is_tracking_param(key: str) -> bool:
    k = key.lower()
    return k.startswith("utm_") or k in _TRACKING_PARAMS


def normalize_url(url: str) -> str:
    """Chuẩn hóa URL để so khớp: hạ host, bỏ tracking param, bỏ fragment + '/' cuối."""
    if not url:
        return ""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url.strip()
    host = parts.netloc.lower()
    kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if not _is_tracking_param(k)]
    query = urlencode(kept)
    path = parts.path.rstrip("/")
    # bỏ fragment (phần tử thứ 5 = "")
    return urlunsplit((parts.scheme.lower(), host, path, query, ""))


def _normalize_text(text: str) -> str:
    """Hạ thường, bỏ dấu câu, gộp khoảng trắng. Giữ nguyên ký tự có dấu."""
    if not text:
        return ""
    t = _PUNCT_RE.sub(" ", text.lower())
    return _WS_RE.sub(" ", t).strip()


def content_hash(article: dict) -> str:
    """sha256(tiêu_đề_chuẩn_hóa + 200 ký tự đầu của body_chuẩn_hóa)."""
    title = _normalize_text(article.get("title", ""))
    body = _normalize_text(article.get("summary", ""))[:BODY_CHARS]
    raw = f"{title}|{body}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _sim_text(article_or_str) -> str:
    """Văn bản dùng cho so gần trùng: 'tiêu đề + lead'. Nhận dict hoặc chuỗi."""
    if isinstance(article_or_str, str):
        return article_or_str.strip()
    title = article_or_str.get("title", "") or ""
    lead = article_or_str.get("lead") or article_or_str.get("summary", "") or ""
    return f"{title} {lead}".strip()


def is_near_duplicate(article, others, threshold: float = NEAR_DUP_THRESHOLD) -> bool:
    """True nếu (tiêu đề + lead) của article gần trùng bất kỳ phần tử nào trong others.

    others: list các dict bài hoặc chuỗi văn bản đã có. Dùng token_set_ratio nên bắt
    được cùng sự kiện được kể bằng từ ngữ khác nhau (CNBC vs TechCrunch).
    """
    text = _sim_text(article)
    if not text:
        return False
    for other in others:
        other_text = _sim_text(other)
        if not other_text:
            continue
        if fuzz.token_set_ratio(text, other_text) / 100.0 >= threshold:
            return True
    return False


# ── State: load / prune / record / save ──────────────────────────────────────

def _now_vn() -> datetime:
    return datetime.now(VN_TZ)


def load_state(path: str = STATE_PATH) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _parse_ts(s):
    try:
        dt = datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:  # coi như giờ VN nếu thiếu offset
        dt = dt.replace(tzinfo=VN_TZ)
    return dt


def prune_state(state: dict, now: datetime | None = None) -> dict:
    """Bỏ mọi entry cũ hơn cửa sổ trượt WINDOW_HOURS; bỏ luôn key ngày rỗng."""
    now = now or _now_vn()
    cutoff = now - timedelta(hours=WINDOW_HOURS)
    for date_key in list(state.keys()):
        entries = state.get(date_key)
        if not isinstance(entries, dict):
            del state[date_key]
            continue
        for h in list(entries.keys()):
            ts = _parse_ts(entries[h].get("sent_at"))
            if ts is None or ts < cutoff:
                del entries[h]
        if not entries:
            del state[date_key]
    return state


def _window_index(state: dict):
    """Gom toàn bộ entry còn lại thành (urls, hashes, texts) để tra cứu nhanh."""
    urls, hashes, texts = set(), set(), []
    for entries in state.values():
        if not isinstance(entries, dict):
            continue
        for h, e in entries.items():
            hashes.add(h)
            nu = normalize_url(e.get("url", ""))
            if nu:
                urls.add(nu)
            texts.append(_sim_text(e))
    return urls, hashes, texts


def record_sent(state: dict, articles: list[dict], now: datetime | None = None) -> dict:
    """Ghi các bài đã gửi vào state[ngày_VN][content_hash]."""
    now = now or _now_vn()
    bucket = state.setdefault(now.strftime("%Y-%m-%d"), {})
    sent_at = now.isoformat(timespec="seconds")
    for art in articles:
        bucket[content_hash(art)] = {
            "url": (art.get("url") or "").strip(),
            "title": (art.get("title") or "").strip(),
            "source": art.get("source", ""),
            "lead": (art.get("summary") or "").strip()[:BODY_CHARS],
            "sent_at": sent_at,
        }
    return state


def save_state(state: dict, path: str = STATE_PATH, now: datetime | None = None) -> None:
    prune_state(state, now or _now_vn())
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ── Pipeline 3 tầng ──────────────────────────────────────────────────────────

def filter_new_articles(articles: list[dict], state: dict,
                        now: datetime | None = None, record: bool = True) -> list[dict]:
    """Lọc ra các bài MỚI (không trùng trong cửa sổ 24h) qua 3 tầng và ghi vào state.

    Bền với field thiếu/lỗi: bài không có cả url lẫn title thì bỏ qua, không gây crash.
    """
    now = now or _now_vn()
    prune_state(state, now)
    window_urls, window_hashes, window_texts = _window_index(state)

    survivors: list[dict] = []
    survivor_hashes: set[str] = set()
    survivor_texts: list[str] = []

    for art in articles:
        if not isinstance(art, dict):
            continue
        url_n = normalize_url(art.get("url", ""))
        title = (art.get("title") or "").strip()
        if not url_n and not title:
            continue  # không đủ dữ liệu để xử lý

        if url_n and url_n in window_urls:
            continue  # Tầng 1: URL chuẩn hóa

        h = content_hash(art)
        if h in window_hashes or h in survivor_hashes:
            continue  # Tầng 2: content hash (xuyên run + nội bộ run)

        if is_near_duplicate(art, window_texts + survivor_texts):
            continue  # Tầng 3: gần trùng (khác nguồn, cùng sự kiện)

        survivors.append(art)
        survivor_hashes.add(h)
        survivor_texts.append(_sim_text(art))

    if record and survivors:
        record_sent(state, survivors, now)
    return survivors


if __name__ == "__main__":
    st = load_state()
    demo = [
        {"url": "https://e.com/a?utm_source=x", "title": "Tin A", "summary": "Nội dung A"},
        {"url": "https://e.com/a#c", "title": "Tin A", "summary": "Nội dung A"},  # trùng
        {"url": "https://e.com/b", "title": "Tin B", "summary": "Nội dung B"},
    ]
    fresh = filter_new_articles(demo, st)
    print(f"{len(fresh)} bài mới:", [i["title"] for i in fresh])
