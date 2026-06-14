# PROJECT CONTEXT — AI News Digest (bản giao tiếp nối tiếp)

Tài liệu này tóm tắt toàn bộ quá trình thảo luận và quyết định, để các cuộc trò chuyện
sau (kể cả trong Claude Code/Cowork) nối tiếp được ngay mà không phải kể lại từ đầu.
Thêm file này vào knowledge của Project hoặc để trong repo.

## 1. Mục tiêu
Một agent CÁ NHÂN giúp tiết kiệm thời gian đọc tin: tự thu thập tin từ vài báo uy tín,
khử trùng lặp, phân loại theo category, tóm tắt ngắn gọn bằng tiếng Việt, chạy mỗi 4 tiếng.
Không phải sản phẩm đa người dùng. Ưu tiên: ít hạ tầng, rẻ, dễ sở hữu/sửa.

## 2. Quyết định kiến trúc (đã chốt)
Fork repo **Jimmuji/ai-daily-digest** (MIT, Python, GitHub Actions + GitHub Pages) và tùy biến.
Lý do chọn so với các phương án khác:
- **Tự build from scratch:** kiểm soát tối đa nhưng tốn công hơn không cần thiết.
- **ClawFeed (kevinho/clawfeed):** chỉ là lớp storage + dashboard; phần fetch + gọi LLM
  KHÔNG nằm trong repo (chỉ phụ thuộc better-sqlite3, không có SDK LLM). Phải chạy dưới
  agent host (OpenClaw) hoặc tự viết orchestrator. Quá khổ cho nhu cầu cá nhân.
- **OpenClaw:** agent runtime tự host chạy 24/7, quyền truy cập cấp hệ thống (rủi ro
  bảo mật, cần cô lập). Là trợ lý tổng quát — dùng dao mổ trâu cho việc tóm tin.
- **RSSBrew / FreshRSS + FeedDigest:** mạnh nhưng cần VPS chạy 24/7.
- **Jimmuji/ai-daily-digest (CHỌN):** tự chứa cả pipeline LLM, fork → đặt API key →
  bật Actions là chạy; đã có GitHub Pages + email (Buttondown). Chỉ cần dán API key,
  KHÔNG phải "build LLM".

Làm rõ quan niệm: không phương án nào bắt "build một LLM" — đều chỉ là gọi API. Khác
nhau ở hạ tầng. Jimmuji = zero server (chạy trên GitHub Actions). OpenClaw = service 24/7.

## 3. Việc cần tùy biến trên bản fork
Repo gốc chuyên tin AI (HuggingFace papers, GitHub trending, 36Kr...) và gốc Trung Quốc.
Cần đổi:
1. Nguồn: thay RSS_SOURCES bằng feed của mình (xem mục 4).
2. Category + ngôn ngữ: prompt sang 3 nhóm (Việt Nam / Kinh tế / Công nghệ), output tiếng Việt.
3. Lịch: cron `0 */4 * * *` (mỗi 4h) thay cho daily.
4. Khử trùng lặp xuyên lần chạy: thêm watermark (URL đã thấy + mốc thời gian) vì chạy 4h
   sẽ lặp tin nếu chỉ dedup trong một mẻ. ĐÂY LÀ PHẦN CODE THÊM ĐÁNG KỂ DUY NHẤT.
5. Model: dễ nhất là DeepSeek hoặc gpt-4o-mini. Muốn Claude thì trỏ API_BASE_URL sang
   OpenRouter (https://openrouter.ai/api/v1), API_MODEL = anthropic/claude-... (vì API gốc
   của Claude không tương thích định dạng OpenAI).

## 4. Nguồn RSS đã xác minh
Việt Nam — VnExpress:
- https://vnexpress.net/rss/tin-moi-nhat.rss
- https://vnexpress.net/rss/thoi-su.rss
- https://vnexpress.net/rss/the-gioi.rss
- https://vnexpress.net/rss/kinh-doanh.rss
Kinh tế / Tài chính — CNBC:
- https://www.cnbc.com/id/100003114/device/rss/rss.html  (US Top News)
- https://www.cnbc.com/id/20910258/device/rss/rss.html   (Economy)
- https://www.cnbc.com/id/10000664/device/rss/rss.html   (Finance)
Công nghệ:
- https://techcrunch.com/feed/
- https://www.cnbc.com/id/19854910/device/rss/rss.html   (CNBC Tech)
Bổ sung: Yahoo Finance https://finance.yahoo.com/news/rssindex ; Reuters, BBC, Ars Technica.

## 5. Trạng thái hiện tại
- Đã chọn repo và vạch rõ các thay đổi.
- Đã có sẵn (trong bộ file đính kèm): sources.py mới, dedup.py mới, daily.yml (cron 4h),
  prompt tiếng Việt, ADAPTATION_GUIDE.md.
- Việc tiếp theo: fork repo, áp các file này, wire dedup vào main.py, test bằng Run workflow.

## 6. Tham chiếu repo (đã khảo sát)
- Jimmuji/ai-daily-digest — bản đang chọn (MIT, Python, Actions+Pages, tự gọi LLM).
- yinan-c/RSS-GPT, RSSBrew — pattern Actions+Pages / self-host.
- fengchang/xExtension-FeedDigest — batch summarize + dịch sang ngôn ngữ đích.
- kevinho/clawfeed — storage+dashboard skill cho OpenClaw (đã loại).
- Feng Liu Medium "AI News Bot with Claude + GitHub Actions" — blueprint prompt biên tập.
