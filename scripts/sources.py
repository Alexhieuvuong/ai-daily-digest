"""
sources.py — cấu hình nguồn tin theo category cho bản fork ai-daily-digest.

Thay thế danh sách RSS_SOURCES gốc (vốn chuyên tin AI) bằng nguồn của bạn,
và bổ sung METADATA category để bước tóm tắt gom nhóm đúng 3 mảng:
Việt Nam / Kinh tế / Công nghệ.

Cách dùng:
- main.py gọi fetch_all() để lấy danh sách item đã chuẩn hóa (mỗi item kèm 'category').
- Nếu main.py gốc dùng RSS_SOURCES dạng [(url, name), ...] thì vẫn có RSS_SOURCES phẳng
  bên dưới để tương thích ngược; nhưng nên chuyển sang fetch_all() để có trường category.

Phụ thuộc: feedparser  (đã có hoặc thêm vào requirements.txt)
"""

from __future__ import annotations
import html
import os
import re
import socket
import time
import feedparser

# Timeout mạng mặc định (giây) khi tải feed — feedparser.parse() không có tham số
# timeout riêng, nên đặt mặc định cho socket để một feed treo không làm kẹt cả lần
# chạy. Các bước khác (DeepSeek/Resend) tự đặt timeout riêng nên không bị ảnh hưởng.
FEED_TIMEOUT = int(os.environ.get("FEED_TIMEOUT", "15"))
socket.setdefaulttimeout(FEED_TIMEOUT)

# ---- Cấu hình nguồn theo category -------------------------------------------
# Mỗi feed: (url, tên_nguồn_hiển_thị)
# Mỗi category nên gồm NHIỀU đầu báo để không bị một nguồn áp đảo (vd VnExpress hay
# CNBC). Việc cân bằng số bài mỗi nguồn được xử lý ở summarize.py (round-robin + cap),
# còn ở đây chỉ cần đảm bảo đa dạng nguồn.
CATEGORIES: dict[str, dict] = {
    "vietnam": {
        "label": "🇻🇳 Việt Nam",
        "feeds": [
            ("https://vnexpress.net/rss/thoi-su.rss", "VnExpress Thời sự"),
            ("https://vnexpress.net/rss/the-gioi.rss", "VnExpress Thế giới"),
            ("https://tuoitre.vn/rss/thoi-su.rss", "Tuổi Trẻ Thời sự"),
            ("https://thanhnien.vn/rss/thoi-su.rss", "Thanh Niên Thời sự"),
        ],
    },
    "kinh_te": {
        "label": "💰 Kinh tế / Tài chính",
        "feeds": [
            ("https://www.cnbc.com/id/100003114/device/rss/rss.html", "CNBC Top News"),
            ("https://www.cnbc.com/id/20910258/device/rss/rss.html", "CNBC Economy"),
            ("https://www.cnbc.com/id/10000664/device/rss/rss.html", "CNBC Finance"),
            ("https://vnexpress.net/rss/kinh-doanh.rss", "VnExpress Kinh doanh"),
            ("https://tuoitre.vn/rss/kinh-doanh.rss", "Tuổi Trẻ Kinh doanh"),
        ],
    },
    "cong_nghe": {
        "label": "💻 Công nghệ",
        "feeds": [
            ("https://techcrunch.com/feed/", "TechCrunch"),
            ("https://www.cnbc.com/id/19854910/device/rss/rss.html", "CNBC Tech"),
            ("https://vnexpress.net/rss/so-hoa.rss", "VnExpress Số hóa"),
        ],
    },
}

# Tương thích ngược: danh sách phẳng (url, name) nếu chỗ nào còn dùng kiểu cũ.
RSS_SOURCES: list[tuple[str, str]] = [
    (url, name)
    for cat in CATEGORIES.values()
    for (url, name) in cat["feeds"]
]

# Số bài tối đa lấy mỗi feed mỗi lần chạy (tránh ôm quá nhiều).
MAX_PER_FEED = 15


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def clean_html(text: str) -> str:
    """Lột thẻ HTML + giải mã entity từ summary của RSS, trả về văn bản thuần.

    Nhiều feed (vd VnExpress) nhét sẵn `<a><img ...></a>` ~270 ký tự ở ĐẦU summary
    trước phần chữ thật. Khối HTML này (a) làm loãng input gửi cho LLM, và (b) thổi
    phồng độ giống token_set_ratio giữa các bài KHÁC nhau (do cùng boilerplate
    vcdn1-vnexpress...), kéo near-dup về sát ngưỡng 0.80 → dễ bỏ nhầm tin thật.
    Lột thẻ TRƯỚC rồi mới unescape để entity `&lt;b&gt;` không biến thành thẻ mới.
    """
    if not text:
        return ""
    stripped = _TAG_RE.sub(" ", text)
    unescaped = html.unescape(stripped)
    return _WS_RE.sub(" ", unescaped).strip()


def _to_iso(entry) -> str | None:
    """Lấy thời điểm xuất bản ở dạng ISO nếu có."""
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return time.strftime("%Y-%m-%dT%H:%M:%S", t)
    return None


def fetch_category(cat_key: str) -> list[dict]:
    """Fetch toàn bộ feed của một category, trả về list item chuẩn hóa."""
    items: list[dict] = []
    cat = CATEGORIES[cat_key]
    for url, source_name in cat["feeds"]:
        try:
            parsed = feedparser.parse(url)
            for entry in parsed.entries[:MAX_PER_FEED]:
                link = entry.get("link", "")
                if not link:
                    continue
                items.append({
                    "title": clean_html(entry.get("title") or ""),
                    "url": link.strip(),
                    "summary": clean_html(entry.get("summary") or ""),
                    "source": source_name,
                    "category": cat_key,
                    "category_label": cat["label"],
                    "published": _to_iso(entry),
                })
        except Exception as e:  # 1 feed chết không làm hỏng cả run
            print(f"[sources] Lỗi khi đọc {url}: {e}")
    return items


def fetch_all() -> list[dict]:
    """Fetch tất cả category. Mỗi item có trường 'category' để gom nhóm khi tóm tắt."""
    out: list[dict] = []
    for cat_key in CATEGORIES:
        out.extend(fetch_category(cat_key))
    return out


if __name__ == "__main__":
    data = fetch_all()
    print(f"Tổng {len(data)} bài thô.")
    for it in data[:5]:
        print(f"- [{it['category']}] {it['title']}  ({it['source']})")
