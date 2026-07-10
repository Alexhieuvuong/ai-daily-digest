"""
dedup.py — khử trùng lặp ĐA TẦNG (pure Python, không dùng LLM).

Mục tiêu: đảm bảo MỘT bài không bao giờ được gửi hai lần trong cửa sổ trượt
WINDOW_HOURS (72h — phải DÀI hơn thời gian một bài còn nằm trong RSS feed, vì feed
chậm như TechCrunch AI/CafeF giữ bài nhiều ngày; cửa sổ 24h từng khiến bài cũ
quay lại buffer sau khi bị prune và bị gửi lần hai).
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
    ROME_TZ = ZoneInfo("Europe/Rome")
except Exception:  # fallback: offset cố định (kém chính xác khi đổi giờ mùa/DST)
    VN_TZ = timezone(timedelta(hours=7))    # VN không có DST -> tương đương
    ROME_TZ = timezone(timedelta(hours=1))  # CET; KHÔNG khớp CEST mùa hè

from rapidfuzz import fuzz


STATE_PATH = os.environ.get("SENT_STATE_PATH", "data/sent_state.json")
WINDOW_HOURS = 72
NEAR_DUP_THRESHOLD = 0.80
BODY_CHARS = 200  # số ký tự đầu của body đưa vào content hash / lead

# ── Gom tin & quyết định gửi: ĐÚNG 3 EMAIL/NGÀY theo 3 khung giờ Rome ─────────
# Buffer tích lũy các tin ĐÃ khử trùng nhưng CHƯA gửi (giữ qua các lần chạy).
PENDING_PATH = os.environ.get("PENDING_PATH", "data/pending.json")
# Cần tối thiểu bao nhiêu tin mới thì khung đó mới gửi (để không gửi email rỗng).
# Mặc định 1: thực tế luôn có >=1 tin nên mỗi khung gửi đúng 1 bản.
MIN_ITEMS = int(os.environ.get("DIGEST_MIN_ITEMS", "1"))
# Tin nằm trong buffer quá lâu thì bỏ (tránh gửi tin quá cũ).
PENDING_MAX_HOURS = int(os.environ.get("PENDING_MAX_HOURS", "48"))
# Chạy tay (workflow_dispatch) đặt cờ này = "1" để GỬI NGAY, bỏ qua khung — tiện test.
# (Lần gửi tay KHÔNG đánh dấu khung -> không "ăn" mất 1 trong 3 bản thật trong ngày.)
FORCE_SEND = os.environ.get("DIGEST_FORCE_SEND", "") == "1"

# 3 khung giờ cố định theo GIỜ ROME, mỗi khung gửi ĐÚNG MỘT email/ngày (ngày tính theo
# lịch Rome). Mỗi khung là một KHOẢNG giờ địa phương đủ rộng để dù GitHub Actions cron
# bắn trễ 1–2h thì tick vẫn rơi đúng khung. Cron bắn một CẶP tick cho mỗi khung (phủ cả
# CEST mùa hè lẫn CET mùa đông); cờ "khung đã gửy" chặn tick thứ hai gửi trùng.
#   morning ~07:00 Rome  | noon ~13:00 Rome | night ~22:00 Rome
#   CEST(UTC+2): cron 05,06 / 11,12 / 20,21 UTC  -> 07,08 / 13,14 / 22,23 Rome
#   CET (UTC+1): cùng cron đó                     -> 06,07 / 12,13 / 21,22 Rome
SLOTS = (
    ("morning", 5, 11),   # giờ Rome trong [05:00, 11:00)
    ("noon",    11, 17),  # giờ Rome trong [11:00, 17:00)
    ("night",   20, 24),  # giờ Rome trong [20:00, 24:00)
)
# Giữ lịch sử "khung đã gửi" của vài ngày gần nhất rồi prune (tránh phình state).
SENT_SLOTS_KEEP_DAYS = 3

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


# ── Buffer tích lũy (pending) + quyết định gửi ───────────────────────────────

def load_pending(path: str = PENDING_PATH) -> dict:
    """Trả về {'last_sent': iso|None, 'items': [...], 'sent_slots': {ngày: [khung]}}."""
    empty = {"last_sent": None, "items": [], "sent_slots": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(empty)
    if not isinstance(data, dict):
        return dict(empty)
    data.setdefault("last_sent", None)
    items = data.get("items")
    data["items"] = items if isinstance(items, list) else []
    slots = data.get("sent_slots")
    data["sent_slots"] = slots if isinstance(slots, dict) else {}
    return data


def save_pending(buf: dict, path: str = PENDING_PATH) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(buf, f, ensure_ascii=False, indent=2)


def prune_pending(items: list[dict], now: datetime | None = None) -> list[dict]:
    """Bỏ tin đã nằm trong buffer lâu hơn PENDING_MAX_HOURS (theo first_seen)."""
    now = now or _now_vn()
    cutoff = now - timedelta(hours=PENDING_MAX_HOURS)
    kept = []
    for it in items:
        if not isinstance(it, dict):
            continue
        ts = _parse_ts(it.get("first_seen"))
        if ts is None or ts >= cutoff:  # thiếu mốc -> giữ lại
            kept.append(it)
    return kept


def _now_rome(now: datetime | None = None) -> datetime:
    """Giờ địa phương Rome (tự xử lý CEST/CET) từ `now` bất kỳ tz, hoặc thời điểm hiện tại."""
    base = now or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return base.astimezone(ROME_TZ)


def current_slot(now: datetime | None = None) -> str | None:
    """Tên khung ('morning'/'noon'/'night') mà thời điểm `now` rơi vào theo giờ Rome,
    hoặc None nếu nằm NGOÀI cả 3 khung (giờ chết -> không gửi)."""
    h = _now_rome(now).hour
    for name, lo, hi in SLOTS:
        if lo <= h < hi:
            return name
    return None


def slot_day(now: datetime | None = None) -> str:
    """Khóa 'ngày' (theo lịch Rome) để đánh dấu khung đã gửi."""
    return _now_rome(now).strftime("%Y-%m-%d")


def slot_already_sent(sent_slots: dict, now: datetime | None = None) -> bool:
    """Khung hiện tại đã gửi trong ngày (Rome) chưa? Ngoài giờ khung -> coi như 'đã gửi'."""
    slot = current_slot(now)
    if slot is None:
        return True
    return slot in (sent_slots.get(slot_day(now)) or [])


def mark_slot_sent(sent_slots: dict, now: datetime | None = None) -> dict:
    """Đánh dấu khung hiện tại đã gửi cho ngày (Rome) hiện tại, rồi prune ngày cũ."""
    slot = current_slot(now)
    if slot is not None:
        day = slot_day(now)
        done = sent_slots.setdefault(day, [])
        if slot not in done:
            done.append(slot)
    return prune_sent_slots(sent_slots, now)


def prune_sent_slots(sent_slots: dict, now: datetime | None = None) -> dict:
    """Chỉ giữ lịch sử khung của SENT_SLOTS_KEEP_DAYS ngày gần nhất (theo lịch Rome)."""
    cutoff = (_now_rome(now).date() - timedelta(days=SENT_SLOTS_KEEP_DAYS)).isoformat()
    return {d: v for d, v in sent_slots.items() if d >= cutoff}


def should_send(items: list[dict], sent_slots: dict, now: datetime | None = None) -> bool:
    """Quyết định có GỬI ngay không — mô hình "ĐÚNG 3 EMAIL/NGÀY theo khung Rome":

      1. FORCE_SEND (chạy tay) -> gửi ngay, bỏ qua khung (tiện test).
      2. Chưa đủ MIN_ITEMS tin -> không gửi (tránh email rỗng).
      3. Ngoài 3 khung giờ     -> không gửi.
      4. Khung hiện tại đã gửi -> không gửi (chặn tick thứ hai của cặp cron gửi trùng).
      5. Còn lại               -> gửi (đây là email đầu tiên của khung này hôm nay).

    `sent_slots`: dict {ngày_Rome: [tên_khung_đã_gửi,...]} lấy từ buffer pending.
    """
    if FORCE_SEND:
        return True
    if len(items) < MIN_ITEMS:
        return False
    return not slot_already_sent(sent_slots, now)


# ── Pipeline 3 tầng ──────────────────────────────────────────────────────────

def filter_new_articles(articles: list[dict], state: dict,
                        extra_window: list[dict] | None = None,
                        now: datetime | None = None, record: bool = True) -> list[dict]:
    """Lọc ra các bài MỚI (không trùng trong cửa sổ WINDOW_HOURS) qua 3 tầng và ghi vào state.

    `extra_window`: danh sách bài đã biết (vd buffer pending) cũng đưa vào so trùng,
    để không thêm lại tin đã chờ gửi. `record=False` để KHÔNG đánh dấu đã gửi (dùng khi
    mới chỉ gom vào buffer, chưa thật sự email).

    Bền với field thiếu/lỗi: bài không có cả url lẫn title thì bỏ qua, không gây crash.
    """
    now = now or _now_vn()
    prune_state(state, now)
    window_urls, window_hashes, window_texts = _window_index(state)
    for art in (extra_window or []):
        if not isinstance(art, dict):
            continue
        nu = normalize_url(art.get("url", ""))
        if nu:
            window_urls.add(nu)
        window_hashes.add(content_hash(art))
        window_texts.append(_sim_text(art))

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
