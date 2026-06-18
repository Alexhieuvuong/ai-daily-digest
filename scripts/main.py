"""
News Digest - Main entry point (bản fork tiếng Việt, chạy mỗi 4h).

Luồng: nạp state + buffer → fetch_all → khử trùng lặp (vs đã-gửi ∪ đang-chờ) → GOM vào
buffer → CHỈ khi đủ ngưỡng (MIN_ITEMS) hoặc tới hạn ngày mới tóm tắt + gửi email + đánh
dấu đã gửi + xóa buffer. Gom-mà-chưa-gửi thì bỏ qua LLM để tránh email lèo tèo & tiết
kiệm token.
"""

import json
from pathlib import Path

from sources import fetch_all
from summarize import summarize
from generate_site import generate_site
from dedup import (
    load_state, save_state, record_sent,
    load_pending, save_pending, prune_pending,
    filter_new_articles, should_send,
    MIN_ITEMS, _now_vn, _parse_ts,
)
from email_brief import send_email


def main():
    now = _now_vn()
    date_str = now.strftime("%Y-%m-%d")
    stamp = now.strftime("%H%M")
    slug = f"{date_str}-{stamp}"
    now_iso = now.isoformat(timespec="seconds")

    print(f"=== News Digest · {date_str} {stamp} (giờ VN) ===\n")

    # Step 1: nạp trạng thái đã-gửi (dedup 24h) + buffer tích lũy
    state = load_state()
    buf = load_pending()
    pending = prune_pending(buf.get("items", []), now)

    # Step 2: fetch toàn bộ nguồn (list phẳng, mỗi item có 'category')
    print("[Bước 1] Lấy tin từ các nguồn...")
    raw = fetch_all()
    print(f"  Tổng {len(raw)} bài thô.")

    # Step 3: khử trùng lặp vs (đã gửi ∪ đang chờ); record=False vì chưa thật sự gửi
    survivors = filter_new_articles(raw, state, extra_window=pending,
                                    record=False, now=now)
    for s in survivors:
        s["first_seen"] = now_iso
    pending.extend(survivors)
    print(f"  +{len(survivors)} tin mới — buffer hiện có {len(pending)} tin.")

    # Step 4: quyết định — gửi hay gom tiếp?
    if not should_send(pending, _parse_ts(buf.get("last_sent")), now):
        # Lần đầu chưa có mốc -> đặt baseline để đồng hồ "đảm bảo ngày" chạy từ giờ.
        save_pending({"last_sent": buf.get("last_sent") or now_iso, "items": pending})
        print(f"Chưa đủ {MIN_ITEMS} tin và chưa tới hạn ngày — gom tiếp, "
              f"bỏ qua LLM/email (tiết kiệm token).")
        return

    print(f"  Đủ điều kiện gửi ({len(pending)} tin) — tạo bản tin...")

    # Step 5: lưu dữ liệu thô để truy vết
    root = Path(__file__).parent.parent
    data_dir = root / "data"
    data_dir.mkdir(exist_ok=True)
    raw_file = data_dir / f"{slug}.raw.json"
    raw_file.write_text(
        json.dumps(
            {"slug": slug, "generated_at": now_iso, "items": pending},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[Bước 2] Đã lưu dữ liệu thô vào {raw_file}")

    # Step 6: tóm tắt tiếng Việt (gom theo category) — LLM chỉ chạy khi thật sự gửi
    print("\n[Bước 3] Tạo bản tóm tắt...")
    markdown = summarize(pending, date_str)

    # Step 7: lưu digest — tên kèm giờ để không đè các lần chạy khác trong ngày
    output_dir = root / "daily"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / f"{slug}.md"
    output_file.write_text(markdown, encoding="utf-8")
    print(f"[Bước 4] Đã lưu digest vào {output_file}")

    # Step 8: dựng lại trang tĩnh
    print("\n[Bước 5] Dựng lại trang tĩnh...")
    generate_site(root=root)
    print("  Đã dựng → docs/")

    # Step 9: gửi bản tin qua email (tự bỏ qua nếu chưa cấu hình)
    print("\n[Bước 6] Gửi email...")
    send_email(f"Bản tin tổng hợp · {date_str} {now.strftime('%H:%M')}", markdown)

    # Step 10: đánh dấu các tin vừa gửi (dedup 24h) + xóa buffer pending
    record_sent(state, pending, now)
    save_state(state, now=now)
    save_pending({"last_sent": now_iso, "items": []})
    print("\nXong! Đã gửi, cập nhật sent_state.json và xóa buffer pending.")


if __name__ == "__main__":
    main()
