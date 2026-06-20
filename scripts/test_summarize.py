"""
Unit test cho summarize.py — tập trung vào _balance_by_source (cân bằng nguồn).

Chạy:  python3 -m unittest scripts/test_summarize.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from summarize import _balance_by_source  # noqa: E402


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
