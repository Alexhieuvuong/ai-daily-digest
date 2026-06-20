"""
Unit test cho sources.py — tập trung vào clean_html (lột HTML khỏi summary RSS).

Chạy:  python3 -m unittest scripts/test_sources.py -v
(yêu cầu: pip install feedparser)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sources import clean_html  # noqa: E402


class TestCleanHtml(unittest.TestCase):
    def test_empty_and_none_like(self):
        self.assertEqual(clean_html(""), "")
        self.assertEqual(clean_html(None or ""), "")

    def test_strips_vnexpress_image_wrapper(self):
        # Mẫu thật: summary VnExpress mở đầu bằng <a><img ...></a> rồi mới tới chữ.
        raw = ('<a href="https://vnexpress.net/x-5088031.html">'
               '<img src="https://vcdn1-vnexpress.vnecdn.net/2026/06/20/z79.jpg'
               '?w=1200&amp;h=0&amp;q=100"/></a>'
               'Giông lốc làm hàng chục cây xanh bật gốc, đè hai ôtô.')
        cleaned = clean_html(raw)
        self.assertEqual(cleaned,
                         "Giông lốc làm hàng chục cây xanh bật gốc, đè hai ôtô.")
        self.assertNotIn("<", cleaned)
        self.assertNotIn("vcdn1", cleaned)

    def test_unescapes_entities(self):
        self.assertEqual(clean_html("Giá &amp; lãi suất"), "Giá & lãi suất")

    def test_tags_stripped_before_unescape(self):
        # Lột thẻ TRƯỚC khi unescape: &lt;b&gt; phải còn nguyên dạng văn bản.
        self.assertEqual(clean_html("5 &lt; 10 và 20 &gt; 3"), "5 < 10 và 20 > 3")

    def test_collapses_whitespace(self):
        self.assertEqual(clean_html("a   b\n\t c"), "a b c")

    def test_preserves_vietnamese_diacritics(self):
        s = "Tăng trưởng GDP đạt mức ấn tượng"
        self.assertEqual(clean_html(s), s)


if __name__ == "__main__":
    unittest.main(verbosity=2)
