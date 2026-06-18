"""
Unit test cho dedup.py — kiểm tra từng tầng với ví dụ thực tế VN/EN.

Chạy:  python3 -m unittest scripts/test_dedup.py -v
(yêu cầu: pip install rapidfuzz)
"""

import os
import sys
import json
import tempfile
import unittest
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dedup  # noqa: E402


class TestNormalizeUrl(unittest.TestCase):
    def test_strips_tracking_fragment_and_trailing_slash(self):
        dirty = ("https://VnExpress.net/el-nino-rat-manh-5085535.html/"
                 "?utm_source=fb&utm_medium=social&fbclid=abc#box_comment")
        clean = "https://vnexpress.net/el-nino-rat-manh-5085535.html"
        self.assertEqual(dedup.normalize_url(dirty), clean)

    def test_host_case_unified(self):
        a = dedup.normalize_url("https://CNBC.com/2026/06/13/spacex-ipo.html")
        b = dedup.normalize_url("https://cnbc.com/2026/06/13/spacex-ipo.html")
        self.assertEqual(a, b)

    def test_keeps_meaningful_query(self):
        u = dedup.normalize_url("https://site.com/a?id=42&utm_source=x")
        self.assertIn("id=42", u)
        self.assertNotIn("utm_source", u)

    def test_empty(self):
        self.assertEqual(dedup.normalize_url(""), "")


class TestContentHash(unittest.TestCase):
    def test_same_story_changed_slug_same_hash(self):
        a = {"url": "https://vnexpress.net/el-nino-5085535.html",
             "title": "El Nino mạnh đe dọa nắng nóng",
             "summary": "Sự trở lại của El Nino được dự báo gây nắng nóng khốc liệt."}
        b = {"url": "https://vnexpress.net/el-nino-rat-manh-DIFFERENT.html",
             "title": "El Nino mạnh đe dọa nắng nóng",
             "summary": "Sự trở lại của El Nino được dự báo gây nắng nóng khốc liệt."}
        self.assertEqual(dedup.content_hash(a), dedup.content_hash(b))

    def test_punctuation_whitespace_case_invariant(self):
        a = {"title": "SpaceX IPO: kỷ lục!", "summary": "Vốn hóa vượt 2.000 tỷ USD"}
        b = {"title": "  spacex   ipo   kỷ lục  ", "summary": "vốn hóa vượt 2 000 tỷ usd"}
        self.assertEqual(dedup.content_hash(a), dedup.content_hash(b))

    def test_missing_fields_no_crash(self):
        self.assertIsInstance(dedup.content_hash({}), str)


class TestNearDuplicate(unittest.TestCase):
    def test_same_event_different_sources(self):
        # Cùng sự kiện, hai outlet viết khác nhau nhưng chia sẻ thực thể/số liệu chính
        # (SpaceX, Nasdaq, $2 trillion, 19%) — đúng kiểu tin được đăng lại/viết lại nhẹ.
        # (Giới hạn của lọc thuần từ vựng: paraphrase hoàn toàn — đổi cả $2T, "19 percent"
        #  — sẽ không bắt được; những ca đó để các tầng URL/hash xử lý nếu trùng nguồn.)
        cnbc = {"title": "SpaceX IPO debuts on Nasdaq, valuation tops $2 trillion",
                "summary": "SpaceX shares jump 19% on their first trading day."}
        tc = {"title": "SpaceX shares surge 19% as Nasdaq IPO valuation tops $2 trillion",
              "summary": "SpaceX stock jumped 19% on the first trading day on Nasdaq."}
        self.assertTrue(dedup.is_near_duplicate(cnbc, [tc]))

    def test_unrelated_stories_not_duplicate(self):
        a = {"title": "El Nino mạnh đe dọa nắng nóng và hạn hán",
             "summary": "Dự báo nắng nóng khốc liệt, xâm nhập mặn diện rộng."}
        b = {"title": "OpenAI bị điều tra bởi các tổng chưởng lý tiểu bang",
             "summary": "Một nhóm tổng chưởng lý mở cuộc điều tra về OpenAI."}
        self.assertFalse(dedup.is_near_duplicate(a, [b]))

    def test_compare_against_string_entries(self):
        art = {"title": "SpaceX IPO lập kỷ lục trên Nasdaq", "summary": "Vốn hóa vượt 2.000 tỷ USD"}
        self.assertTrue(dedup.is_near_duplicate(
            art, ["SpaceX IPO lập kỷ lục trên Nasdaq Vốn hóa vượt 2.000 tỷ USD"]))


class TestFilterPipelineAndState(unittest.TestCase):
    def setUp(self):
        self.now = dedup._now_vn()

    def test_end_to_end(self):
        # (b) đã gửi trước đó trong cửa sổ
        state = {}
        already = {"url": "https://vnexpress.net/da-lat-rac-5085581.html",
                   "title": "Hàng trăm tấn rác ùn ứ ở Đà Lạt",
                   "summary": "Nhà máy xử lý rác tạm ngừng khiến rác tồn đọng."}
        dedup.record_sent(state, [already], self.now - timedelta(hours=2))

        batch = [
            # (a) bài hoàn toàn mới
            {"url": "https://techcrunch.com/2026/06/13/openai-investigation/",
             "title": "OpenAI faces investigation from state attorneys general",
             "summary": "A coalition of state AGs opened a probe into OpenAI."},
            # (b) trùng URL đã gửi
            {"url": "https://vnexpress.net/da-lat-rac-5085581.html",
             "title": "Hàng trăm tấn rác ùn ứ ở Đà Lạt",
             "summary": "Nhà máy xử lý rác tạm ngừng khiến rác tồn đọng."},
            # (c) cùng bài (b) nhưng đổi slug/URL + utm -> content hash bắt
            {"url": "https://vnexpress.net/rac-un-u-da-lat-OTHER.html?utm_source=fb",
             "title": "Hàng trăm tấn rác ùn ứ ở Đà Lạt",
             "summary": "Nhà máy xử lý rác tạm ngừng khiến rác tồn đọng."},
            # (d) cùng sự kiện (a) khác nguồn/cách viết -> gần trùng bắt
            {"url": "https://www.cnbc.com/2026/06/13/openai-probe.html",
             "title": "State attorneys general launch probe into OpenAI",
             "summary": "A group of state AGs is investigating OpenAI."},
        ]
        survivors = dedup.filter_new_articles(batch, state, now=self.now)
        titles = [s["title"] for s in survivors]
        self.assertEqual(len(survivors), 1, f"chỉ 1 bài mới được qua, got {titles}")
        self.assertIn("OpenAI faces investigation", titles[0])

    def test_prune_removes_entries_older_than_24h(self):
        state = {}
        dedup.record_sent(state, [{"url": "https://x.com/old", "title": "Tin cũ",
                                   "summary": "..."}], self.now - timedelta(hours=30))
        dedup.record_sent(state, [{"url": "https://x.com/new", "title": "Tin mới",
                                   "summary": "..."}], self.now - timedelta(hours=1))
        dedup.prune_state(state, self.now)
        remaining = [e["title"] for d in state.values() for e in d.values()]
        self.assertEqual(remaining, ["Tin mới"])

    def test_near_midnight_not_resent(self):
        # Bài gửi lúc 23h hôm trước vẫn nằm trong cửa sổ 24h -> không gửi lại sáng hôm sau.
        state = {}
        art = {"url": "https://vnexpress.net/el-nino-5085535.html",
               "title": "El Nino mạnh đe dọa nắng nóng",
               "summary": "Dự báo nắng nóng khốc liệt."}
        dedup.record_sent(state, [art], self.now - timedelta(hours=8))
        survivors = dedup.filter_new_articles([art], state, now=self.now)
        self.assertEqual(survivors, [])

    def test_save_and_load_roundtrip(self):
        state = {}
        dedup.record_sent(state, [{"url": "https://x.com/a", "title": "A", "summary": "a"}],
                          self.now)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sent_state.json")
            dedup.save_state(state, path=path, now=self.now)
            loaded = dedup.load_state(path)
        self.assertEqual(json.dumps(loaded, sort_keys=True),
                         json.dumps(state, sort_keys=True))


class TestRobustness(unittest.TestCase):
    def test_missing_fields_do_not_raise(self):
        batch = [
            {},                                   # rỗng -> bỏ qua
            {"title": "Chỉ có tiêu đề"},          # thiếu url/summary
            {"url": "https://x.com/only-url"},    # thiếu title/summary
            {"url": "https://x.com/full", "title": "Đủ", "summary": "Nội dung"},
        ]
        survivors = dedup.filter_new_articles(batch, {}, now=dedup._now_vn())
        # bài rỗng bị loại; ba bài còn lại đều hợp lệ và khác nhau
        self.assertEqual(len(survivors), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
