"""
Unit test cho summarize.py — tập trung vào _balance_by_source (cân bằng nguồn).

Chạy:  python3 -m unittest scripts/test_summarize.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from summarize import _balance_by_source, _build_user_prompt, _max_items_for  # noqa: E402


def _mk(source, n):
    return [{"source": source, "title": f"{source}{i}"} for i in range(n)]


class TestBalanceBySource(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(_balance_by_source([]), [])

    def test_caps_each_source(self):
        items = _mk("A", 6) + _mk("B", 1) + _mk("C", 2)
        out = _balance_by_source(items, cap=4)
        counts = {}
        for it in out:
            counts[it["source"]] = counts.get(it["source"], 0) + 1
        self.assertEqual(counts, {"A": 4, "B": 1, "C": 2})

    def test_round_robin_order(self):
        items = _mk("A", 3) + _mk("B", 1) + _mk("C", 2)
        out = [it["source"] for it in _balance_by_source(items, cap=4)]
        # một bài mỗi nguồn trước khi quay lại nguồn đầu
        self.assertEqual(out[:3], ["A", "B", "C"])

    def test_stable_within_source(self):
        items = _mk("A", 5)
        out = [it["title"] for it in _balance_by_source(items, cap=3)]
        self.assertEqual(out, ["A0", "A1", "A2"])

    def test_single_source_passthrough_up_to_cap(self):
        items = _mk("A", 2)
        self.assertEqual(len(_balance_by_source(items, cap=4)), 2)


class TestBuildUserPrompt(unittest.TestCase):
    def _items(self, key, label, source, n):
        return [{"category": key, "category_label": label,
                 "source": source, "title": f"{source}{i}",
                 "url": f"https://x/{source}{i}", "summary": "s"} for i in range(n)]

    def test_per_category_max_items_in_labels(self):
        grouped = {"vietnam": self._items("vietnam", "🇻🇳 Việt Nam", "VnExpress Thời sự", 6)}
        prompt = _build_user_prompt(grouped, "2026-06-20")
        self.assertIn(f"tối đa {_max_items_for('vietnam')} mục", prompt)

    def test_single_source_not_capped_to_per_source_cap(self):
        # cong_nghe có 1 nguồn (TechCrunch); KHÔNG bị cap 4 — phải đưa hết ứng viên.
        grouped = {"cong_nghe": self._items("cong_nghe", "💻 Công nghệ", "TechCrunch", 9)}
        prompt = _build_user_prompt(grouped, "2026-06-20")
        self.assertEqual(prompt.count("https://x/TechCrunch"), 9)

    def test_multi_source_balanced_and_capped(self):
        grouped = {"kinh_te": self._items("kinh_te", "💰", "CNBC", 10)
                                + self._items("kinh_te", "💰", "VnExpress KD", 2)}
        prompt = _build_user_prompt(grouped, "2026-06-20")
        # CNBC bị cap ở PER_SOURCE_CAP (4), VnExpress KD giữ cả 2
        self.assertEqual(prompt.count('"source": "CNBC"'), 4)
        self.assertEqual(prompt.count('"source": "VnExpress KD"'), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
