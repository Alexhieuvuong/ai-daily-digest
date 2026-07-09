"""
Unit test cho market_outlook.py — nhận định xu hướng thị trường.

Chạy:  python3 -m unittest scripts/test_market_outlook.py -v
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import market_outlook  # noqa: E402
from market_outlook import (  # noqa: E402
    OUTLOOK_HEADING, append_outlook, generate_outlook,
    is_first_send_of_day, _fresh_block, _load_history,
)
from generate_site import parse_digest  # noqa: E402


NOW = datetime(2026, 7, 9, 4, 30)

SAMPLE_DIGEST = """# Bản tin tổng hợp · {day}

## 💰 Kinh tế / Tài chính

**1. Tỷ giá hạ nhiệt**: USD/VND giảm mạnh sau tin Fed.
Quan trọng: ★★★★☆
Vì sao: Ảnh hưởng dòng vốn.
Nguồn: [CafeF](https://x/1)
___

## 📈 Tài chính / Chứng khoán VN

**1. Khối ngoại bán ròng**: Phiên thứ 5 liên tiếp.
Quan trọng: ★★★☆☆
Vì sao: Áp lực thanh khoản.
Nguồn: [CafeF](https://x/2)
___

## 🤖 AI

**1. Tin AI gì đó**: Không liên quan tài chính.
Quan trọng: ★★☆☆☆
Vì sao: Ngách.
Nguồn: [VnExpress](https://x/3)
___

### Quan sát hôm nay

Thị trường đang thận trọng chờ số liệu vĩ mô.

---
*Tạo tự động bởi AI Daily Digest dùng deepseek-chat*
"""


def _write_digest(daily_dir: Path, day: str, hhmm: str = "0430"):
    (daily_dir / f"{day}-{hhmm}.md").write_text(
        SAMPLE_DIGEST.format(day=day), encoding="utf-8")


class TestIsFirstSendOfDay(unittest.TestCase):
    def test_true_when_no_file_today(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "daily").mkdir()
            _write_digest(root / "daily", "2026-07-08")
            self.assertTrue(is_first_send_of_day(root, "2026-07-09"))

    def test_false_when_file_exists_today(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "daily").mkdir()
            _write_digest(root / "daily", "2026-07-09")
            self.assertFalse(is_first_send_of_day(root, "2026-07-09"))

    def test_force_env_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "daily").mkdir()
            _write_digest(root / "daily", "2026-07-09")
            with mock.patch.dict(os.environ, {"OUTLOOK_FORCE": "1"}):
                self.assertTrue(is_first_send_of_day(root, "2026-07-09"))


class TestLoadHistory(unittest.TestCase):
    def test_window_and_finance_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            daily = root / "daily"
            daily.mkdir()
            _write_digest(daily, "2026-06-30")  # > 7 ngày trước NOW -> loại
            _write_digest(daily, "2026-07-03")
            _write_digest(daily, "2026-07-08")
            lines = _load_history(root, NOW)
            joined = "\n".join(lines)
            # chỉ 2 ngày trong cửa sổ, mỗi ngày 2 tin tài chính
            self.assertEqual(len(lines), 4)
            self.assertNotIn("2026-06-30", joined)
            self.assertIn("[2026-07-03]", joined)
            self.assertIn("[2026-07-08]", joined)
            # tin AI không lọt vào
            self.assertNotIn("Tin AI", joined)
            # có sao + mô tả
            self.assertIn("(★★★★) Tỷ giá hạ nhiệt", joined)

    def test_line_cap_drops_oldest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            daily = root / "daily"
            daily.mkdir()
            for d in range(3, 9):  # 6 ngày x 2 tin = 12 dòng
                _write_digest(daily, f"2026-07-0{d}")
            with mock.patch.object(market_outlook, "MAX_HISTORY_LINES", 3):
                lines = _load_history(root, NOW)
            self.assertEqual(len(lines), 3)
            # giữ dòng MỚI nhất
            self.assertIn("[2026-07-08]", lines[-1])

    def test_missing_daily_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(_load_history(Path(tmp), NOW), [])


class TestFreshBlock(unittest.TestCase):
    def test_filters_finance_categories(self):
        items = [
            {"category": "kinh_te", "title": "GDP quý 2", "source": "CafeF",
             "summary": "Tăng trưởng vượt kỳ vọng."},
            {"category": "chung_khoan_vn", "title": "VN-Index", "source": "CafeF",
             "summary": "Thanh khoản giảm."},
            {"category": "ai", "title": "Tin AI", "source": "X", "summary": "..."},
            {"category": "vietnam", "title": "Tin VN", "source": "Y", "summary": "..."},
        ]
        lines = _fresh_block(items)
        self.assertEqual(len(lines), 2)
        self.assertIn("GDP quý 2 (CafeF)", lines[0])
        self.assertIn("VN-Index", lines[1])


class TestGenerateOutlook(unittest.TestCase):
    def _root_with_history(self, tmp):
        root = Path(tmp)
        daily = root / "daily"
        daily.mkdir()
        _write_digest(daily, "2026-07-08")
        return root

    def test_success_returns_section_with_heading(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root_with_history(tmp)
            fake = {"choices": [{"message": {"content": "**Tín hiệu 7 ngày qua**\n- ..."}}]}
            with mock.patch.dict(os.environ, {"API_KEY": "k"}), \
                 mock.patch.object(market_outlook, "_post_with_retry",
                                   return_value=fake) as m:
                out = generate_outlook([], NOW, root)
            self.assertIsNotNone(out)
            self.assertTrue(out.startswith(OUTLOOK_HEADING))
            # temperature thấp + max_tokens giới hạn
            payload = m.call_args[0][2]
            self.assertEqual(payload["temperature"], 0.3)
            self.assertEqual(payload["max_tokens"], 1200)

    def test_api_error_returns_none_not_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root_with_history(tmp)
            with mock.patch.dict(os.environ, {"API_KEY": "k"}), \
                 mock.patch.object(market_outlook, "_post_with_retry",
                                   side_effect=requests.exceptions.HTTPError("500")):
                self.assertIsNone(generate_outlook([], NOW, root))

    def test_empty_choices_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root_with_history(tmp)
            with mock.patch.dict(os.environ, {"API_KEY": "k"}), \
                 mock.patch.object(market_outlook, "_post_with_retry",
                                   return_value={"choices": []}):
                self.assertIsNone(generate_outlook([], NOW, root))

    def test_no_finance_data_skips_llm(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "daily").mkdir()
            with mock.patch.object(market_outlook, "_post_with_retry") as m:
                self.assertIsNone(generate_outlook([], NOW, root))
            m.assert_not_called()

    def test_disable_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root_with_history(tmp)
            with mock.patch.dict(os.environ, {"OUTLOOK_DISABLE": "1"}), \
                 mock.patch.object(market_outlook, "_post_with_retry") as m:
                self.assertIsNone(generate_outlook([], NOW, root))
            m.assert_not_called()


class TestAppendOutlook(unittest.TestCase):
    SECTION = f"{OUTLOOK_HEADING}\n\n**Tín hiệu 7 ngày qua**\n- abc"

    def test_inserts_before_footer(self):
        md = SAMPLE_DIGEST.format(day="2026-07-09")
        out = append_outlook(md, self.SECTION)
        # section nằm SAU Quan sát và TRƯỚC footer
        self.assertLess(out.index("Quan sát hôm nay"), out.index(OUTLOOK_HEADING))
        self.assertLess(out.index(OUTLOOK_HEADING), out.index("*Tạo tự động"))
        self.assertTrue(out.rstrip().endswith("deepseek-chat*"))

    def test_fallback_appends_at_end(self):
        md = "# Bản tin\n\nnội dung không có footer"
        out = append_outlook(md, self.SECTION)
        self.assertIn(OUTLOOK_HEADING, out)
        self.assertTrue(out.index(OUTLOOK_HEADING) > out.index("nội dung"))


class TestParseDigestOutlook(unittest.TestCase):
    """Regression: heading chứa 'nhận định' KHÔNG được lẫn vào observation."""

    def test_observation_and_outlook_separated(self):
        md = append_outlook(
            SAMPLE_DIGEST.format(day="2026-07-09"),
            f"{OUTLOOK_HEADING}\n\n**Tín hiệu 7 ngày qua**\n- Khối ngoại bán ròng\n\n"
            "**Xu hướng nghiêng về:** thận trọng — lý do.\n\n"
            "_Nhận định tự động, không phải khuyến nghị đầu tư._")
        parsed = parse_digest(md)
        self.assertEqual(parsed["observation"],
                         "Thị trường đang thận trọng chờ số liệu vĩ mô.")
        self.assertIn("**Tín hiệu 7 ngày qua**", parsed["outlook"])
        self.assertIn("- Khối ngoại bán ròng", parsed["outlook"])
        # footer không lọt vào outlook
        self.assertNotIn("Tạo tự động", parsed["outlook"])
        # outlook không lọt vào observation
        self.assertNotIn("Tín hiệu", parsed["observation"])

    def test_digest_without_outlook_has_empty_field(self):
        parsed = parse_digest(SAMPLE_DIGEST.format(day="2026-07-09"))
        self.assertEqual(parsed["outlook"], "")
        # bonus fix: footer '*Tạo tự động' không còn lẫn vào observation
        self.assertNotIn("Tạo tự động", parsed["observation"])


if __name__ == "__main__":
    unittest.main()
