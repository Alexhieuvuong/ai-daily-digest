"""
notify_failure.py — gửi email cảnh báo khi một lần chạy thất bại.

Chỉ gọi từ workflow ở bước `if: failure()`. Tái dùng send_email (Resend),
nên cũng tự bỏ qua (no-op) nếu thiếu RESEND_API_KEY.

Biến môi trường (ngoài các biến của email_brief):
- RUN_URL  (link tới lần chạy GitHub Actions bị lỗi; tùy chọn)
"""

import os
from datetime import datetime, timezone, timedelta

from email_brief import send_email

VN_TZ = timezone(timedelta(hours=7))


def main() -> None:
    now = datetime.now(VN_TZ).strftime("%Y-%m-%d %H:%M")
    run_url = os.environ.get("RUN_URL", "").strip()

    body = (
        f"# ⚠️ Bản tin tổng hợp — lần chạy THẤT BẠI\n\n"
        f"Một lần chạy GitHub Actions đã lỗi lúc **{now}** (giờ VN).\n\n"
        f"Nguyên nhân thường gặp: API key hết hạn/hết credit, "
        f"hoặc một nguồn RSS đổi địa chỉ.\n\n"
    )
    if run_url:
        body += f"Xem log để biết chi tiết: [{run_url}]({run_url})\n"

    send_email("⚠️ Bản tin tổng hợp — lần chạy thất bại", body)


if __name__ == "__main__":
    main()
