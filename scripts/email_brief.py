"""
email_brief.py — gửi bản tin qua email (Resend).

Chuyển digest Markdown -> HTML rồi gửi bằng API của Resend.
Tự bỏ qua (no-op) nếu thiếu RESEND_API_KEY, để một lần chạy không bao giờ
thất bại chỉ vì email chưa được cấu hình.

Biến môi trường:
- RESEND_API_KEY  (bắt buộc để gửi; thiếu -> bỏ qua)
- EMAIL_TO        (người nhận; mặc định: hieuvuongforwork@gmail.com)
- EMAIL_FROM      (người gửi; mặc định: onboarding@resend.dev — sender test của Resend)
"""

import os

import requests
import markdown as md_lib


DEFAULT_TO = "hieuvuongforwork@gmail.com"
# Sender test của Resend: chỉ gửi được tới chính email chủ tài khoản khi chưa
# xác minh domain. Đổi sang địa chỉ thuộc domain đã verify để gửi cho người khác.
DEFAULT_FROM = "onboarding@resend.dev"


def _wrap_html(inner: str) -> str:
    """Bọc HTML body trong khung tối giản, dễ đọc trên mobile."""
    return f"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f6f8fa;">
  <div style="max-width:680px;margin:0 auto;padding:24px 20px;
              font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
              color:#1f2328;line-height:1.6;font-size:15px;">
    {inner}
  </div>
</body></html>"""


def send_email(subject: str, markdown_body: str) -> None:
    """Gửi bản tin qua Resend. Bỏ qua nếu chưa cấu hình RESEND_API_KEY."""
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        print("[email] RESEND_API_KEY chưa đặt — bỏ qua gửi email.")
        return

    to_addr = os.environ.get("EMAIL_TO", DEFAULT_TO)
    from_addr = os.environ.get("EMAIL_FROM", DEFAULT_FROM)

    # nl2br: giữ mỗi dòng Quan trọng/Vì sao/Nguồn trên một dòng riêng vì format
    # mới không còn dùng dấu gạch đầu dòng cho ba trường này.
    html = _wrap_html(md_lib.markdown(markdown_body, extensions=["extra", "nl2br"]))

    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": from_addr,
                "to": [to_addr],
                "subject": subject,
                "html": html,
            },
            timeout=30,
        )
        if resp.status_code in (200, 201):
            print(f"[email] Đã gửi tới {to_addr} (id: {resp.json().get('id')})")
        else:
            print(f"[email] Gửi thất bại {resp.status_code}: {resp.text[:200]}")
    except Exception as e:  # email lỗi không được làm hỏng cả run
        print(f"[email] Lỗi khi gửi: {e}")
