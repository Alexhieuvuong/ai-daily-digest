# ADAPTATION GUIDE — biến ai-daily-digest thành digest cá nhân tiếng Việt (mỗi 4h)

Bộ file này dùng để áp lên bản **fork** của `Jimmuji/ai-daily-digest`. Repo gốc đã lo
collect → tóm tắt (gọi LLM) → lưu → GitHub Pages. Ta chỉ đổi nguồn, category, ngôn ngữ,
lịch và thêm khử trùng lặp xuyên lần chạy.

> Vì cấu trúc code nội bộ của repo có thể đổi, các bước dưới chỉ rõ ĐIỂM TÍCH HỢP.
> Mở `scripts/main.py` và `scripts/summarize.py` thật để khớp tên hàm/biến cho khớp.

## Bước 0 — Fork & bật
1. Fork repo trên GitHub.
2. Settings → Secrets and variables → Actions → New repository secret:
   - `API_KEY` = key model bạn dùng (DeepSeek mặc định, hoặc OpenAI/OpenRouter).
3. (Tùy chọn dùng Claude) thêm 2 repo *Variables*:
   - `API_BASE_URL` = `https://openrouter.ai/api/v1`
   - `API_MODEL`    = `anthropic/claude-3.5-sonnet` (hoặc model Claude khác)
4. Bật tab Actions.

## Bước 1 — Thay nguồn
Chép đè `scripts/sources.py` bằng file trong bộ này (đã cấu hình VnExpress / CNBC /
TechCrunch theo 3 category). Thêm `feedparser` vào `requirements.txt` nếu chưa có.

## Bước 2 — Thêm khử trùng lặp xuyên lần chạy
Chép `scripts/dedup.py` (mới) vào. Trong `scripts/main.py`, chèn vào luồng chính:

```python
from sources import fetch_all
from dedup import load_state, filter_new, save_state

def run():
    state = load_state()
    raw = fetch_all()                      # đã kèm 'category' mỗi item
    new_items = filter_new(raw, state)
    if not new_items:
        print("Không có tin mới — bỏ qua.")
        return
    digest_md = summarize(new_items)       # hàm tóm tắt của repo (xem Bước 3)
    save_digest(digest_md)                 # hàm lưu của repo (daily/ + docs/)
    save_state(state)                      # lưu watermark CUỐI CÙNG, sau khi xong
```

Quan trọng: `data/seen.json` phải được commit ngược repo (workflow đã `git add data/`).

## Bước 3 — Prompt tiếng Việt + 3 category
Trong `scripts/summarize.py`, thay prompt hệ thống/người dùng bằng nội dung dưới đây.
Truyền `new_items` đã nhóm theo `category` (dùng trường `category_label`).

System prompt:
```
Bạn là một biên tập viên tin tức kỳ cựu, viết bằng tiếng Việt tự nhiên, súc tích.
Nhiệm vụ: từ danh sách bài thô, CHỌN LỌC những tin đáng chú ý nhất và viết bản tin tóm tắt.
Quy tắc:
- Chỉ dùng thông tin có trong bài, TUYỆT ĐỐI không bịa.
- Mỗi category giữ tối đa 5 mục; gộp các bài cùng chủ đề thành một mục.
- Mỗi mục: 2-3 câu tiếng Việt, nêu vì sao đáng chú ý, kèm link gốc.
- Gắn mức quan trọng: ★☆☆☆☆ đến ★★★★★.
- Cuối bản tin thêm mục "Quan sát hôm nay": 2-3 câu nhận định xu hướng.
- Output Markdown, đúng cấu trúc category được yêu cầu.
```

User prompt (khung):
```
Hôm nay {date}. Hãy tạo bản digest theo các category sau, đúng thứ tự:
{liệt kê các category_label có tin}

Dữ liệu thô (JSON) — mỗi bài có title, url, summary, source, category:
{json các new_items}

Định dạng output cho mỗi mục:
1. **<Tiêu đề tóm tắt>**: <2-3 câu>.
   - Quan trọng: ★★★☆☆
   - Vì sao: <ngắn gọn>
   - Nguồn: [<source>](<url>)
```

Gợi ý chi phí: gom theo từng category thành ÍT lần gọi (1 lần/category, hoặc 1 lần cho
cả mẻ nếu vừa context) để tiết kiệm token.

## Bước 4 — Lịch mỗi 4 tiếng
Chép đè `.github/workflows/daily.yml` (hoặc đổi tên cho khớp workflow gốc) bằng file trong
bộ này. Cron đã đặt `0 */4 * * *`. Có thể đổi giờ cho hợp múi giờ VN nếu muốn các mốc
"đẹp" theo giờ địa phương (UTC+7).

## Bước 5 — Test
- Vào Actions → chọn workflow → **Run workflow** (chạy tay).
- Kiểm tra `daily/` có file mới, `data/seen.json` được cập nhật, trang GitHub Pages hiển thị.
- Chạy tay lần 2 ngay sau đó: phải ra "Không có tin mới" (xác nhận dedup hoạt động).

## Ghi chú
- Repo gốc dedup trong một mẻ; phần xuyên-lần-chạy là `dedup.py` ta thêm vào.
- Nếu main.py gốc còn dùng `RSS_SOURCES` dạng (url, name), file sources.py vẫn xuất biến
  đó để tương thích — nhưng nên chuyển sang `fetch_all()` để có trường `category`.
- Đừng commit API key. Chỉ để trong Secrets.
- License gốc MIT — thoải mái sửa, nhớ giữ ghi chú nguồn.
