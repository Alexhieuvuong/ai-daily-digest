"""
dedup.py — khử trùng lặp XUYÊN các lần chạy (cross-run) cho nhịp 4 tiếng.

Vì chạy mỗi 4h, nếu chỉ dedup trong một mẻ thì các bản digest sẽ lặp lại tin cũ.
Module này lưu trạng thái (URL đã xử lý + mốc thời gian) vào data/seen.json và chỉ
cho qua những bài MỚI.

Tích hợp vào main.py:
    from dedup import load_state, filter_new, save_state
    state = load_state()
    raw_items = fetch_all()                 # từ sources.py
    new_items = filter_new(raw_items, state)
    if not new_items:
        print("Không có tin mới — bỏ qua lần chạy này.")
        return
    # ... gửi new_items cho bước tóm tắt ...
    save_state(state)                       # lưu lại sau khi xử lý xong

Lưu ý: data/seen.json cần được commit ngược repo (workflow đã làm) để giữ trạng thái
giữa các lần Actions chạy.
"""

from __future__ import annotations
import json
import os
import hashlib
from datetime import datetime, timezone

STATE_PATH = os.environ.get("SEEN_STATE_PATH", "data/seen.json")

# Giữ tối đa bao nhiêu url_hash gần nhất (tránh file phình vô hạn).
MAX_SEEN = 5000


def url_hash(url: str) -> str:
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()[:16]


def load_state(path: str = STATE_PATH) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            data.setdefault("seen", [])
            data.setdefault("last_run", None)
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {"seen": [], "last_run": None}


def save_state(state: dict, path: str = STATE_PATH) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    # Cắt bớt seen cho gọn, giữ phần mới nhất ở cuối list.
    state["seen"] = state["seen"][-MAX_SEEN:]
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def filter_new(items: list[dict], state: dict) -> list[dict]:
    """
    Trả về các item chưa từng thấy (theo url_hash) và cập nhật state['seen'].
    Cũng khử trùng lặp NỘI BỘ trong cùng mẻ (cùng URL xuất hiện ở nhiều feed).
    """
    seen = set(state.get("seen", []))
    new_items: list[dict] = []
    batch_seen: set[str] = set()

    for it in items:
        url = it.get("url", "")
        if not url:
            continue
        h = url_hash(url)
        if h in seen or h in batch_seen:
            continue
        batch_seen.add(h)
        new_items.append(it)

    # Ghi nhận các hash mới vào state (giữ thứ tự, mới nhất ở cuối).
    state.setdefault("seen", []).extend(sorted(batch_seen))
    return new_items


if __name__ == "__main__":
    # Test nhanh
    st = load_state()
    demo = [
        {"url": "https://example.com/a", "title": "A"},
        {"url": "https://example.com/a", "title": "A-dup"},
        {"url": "https://example.com/b", "title": "B"},
    ]
    fresh = filter_new(demo, st)
    print(f"{len(fresh)} bài mới:", [i['title'] for i in fresh])
    save_state(st)
    print("Đã lưu state. Chạy lại lần nữa sẽ ra 0 bài mới.")
