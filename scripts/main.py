"""
News Digest - Main entry point (bản fork tiếng Việt, chạy mỗi 4h).

Luồng: load_state → fetch_all → khử trùng lặp xuyên lần chạy → tóm tắt tiếng Việt
→ lưu daily/{ngày}-{HHmm}.md → dựng lại docs/ → lưu watermark.
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from sources import fetch_all
from summarize import summarize
from generate_site import generate_site
from dedup import load_state, filter_new, save_state


# Giờ Việt Nam (UTC+7)
VN_TZ = timezone(timedelta(hours=7))


def main():
    now = datetime.now(VN_TZ)
    date_str = now.strftime("%Y-%m-%d")
    stamp = now.strftime("%H%M")
    slug = f"{date_str}-{stamp}"

    print(f"=== News Digest · {date_str} {stamp} (giờ VN) ===\n")

    # Step 1: nạp watermark các lần chạy trước
    state = load_state()

    # Step 2: fetch toàn bộ nguồn (list phẳng, mỗi item có 'category')
    print("[Bước 1] Lấy tin từ các nguồn...")
    raw = fetch_all()
    print(f"  Tổng {len(raw)} bài thô.")

    # Step 3: khử trùng lặp xuyên lần chạy
    new_items = filter_new(raw, state)
    print(f"  Còn {len(new_items)} bài mới sau khử trùng lặp.")
    if not new_items:
        print("Không có tin mới — bỏ qua lần chạy này.")
        return

    # Step 4: lưu dữ liệu thô để truy vết
    root = Path(__file__).parent.parent
    data_dir = root / "data"
    data_dir.mkdir(exist_ok=True)
    raw_file = data_dir / f"{slug}.raw.json"
    raw_file.write_text(
        json.dumps(
            {"slug": slug, "generated_at": now.isoformat(), "items": new_items},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[Bước 2] Đã lưu dữ liệu thô vào {raw_file}")

    # Step 5: tóm tắt tiếng Việt (gom theo category)
    print("\n[Bước 3] Tạo bản tóm tắt...")
    markdown = summarize(new_items, date_str)

    # Step 6: lưu digest — tên kèm giờ để không đè các lần chạy khác trong ngày
    output_dir = root / "daily"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / f"{slug}.md"
    output_file.write_text(markdown, encoding="utf-8")
    print(f"[Bước 4] Đã lưu digest vào {output_file}")

    # Step 7: dựng lại trang tĩnh
    print("\n[Bước 5] Dựng lại trang tĩnh...")
    generate_site(root=root)
    print("  Đã dựng → docs/")

    # Step 8: lưu watermark CUỐI CÙNG, sau khi mọi thứ xong
    save_state(state)
    print("\nXong! Đã cập nhật data/seen.json.")


if __name__ == "__main__":
    main()
