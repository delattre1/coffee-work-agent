import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import browser_booking as b


class HelperTests(unittest.TestCase):
    def test_time_variants(self):
        v = b.time_variants("18:30")
        self.assertIn("18:30", v)
        self.assertTrue(any("6:30" in x for x in v))

    def test_bad_time(self):
        with self.assertRaises(b.ValidationError):
            b.time_variants("25:99")

    def test_date_variants(self):
        v = b.date_variants("2026-09-06")
        self.assertIn("2026-09-06", v)

    def test_normalization(self):
        self.assertEqual(
            b.norm_text(" Reservar   uma MESA "),
            "reservar uma mesa"
        )
        self.assertEqual(
            b.norm_text("Confirmação"),
            "confirmacao"
        )


if __name__ == "__main__":
    unittest.main()
