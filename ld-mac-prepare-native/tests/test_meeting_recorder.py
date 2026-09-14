import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from meeting_recorder import MeetingError, _summary_markdown, start_recording, upcoming_events  # noqa: E402


class MeetingRecorderTests(unittest.TestCase):
    def test_recording_requires_explicit_confirmation(self):
        with self.assertRaises(MeetingError):
            start_recording("demo", confirmed_by_user=False, dry_run=True)

    def test_confirmed_dry_run_is_side_effect_free(self):
        result = start_recording("Product Review", confirmed_by_user=True, dry_run=True)
        self.assertTrue(result["recording"])
        self.assertTrue(result["dry_run"])

    def test_calendar_dry_run(self):
        events = upcoming_events(10, dry_run=True)
        self.assertEqual(events[0]["title"], "Product Review")

    def test_local_summary_extracts_signals(self):
        summary = _summary_markdown(
            "demo",
            "We decided to ship Friday. Alex will update the deck. The prototype is stable.",
            "2026-01-01T00:00:00Z",
        )
        self.assertIn("We decided to ship Friday", summary)
        self.assertIn("Alex will update the deck", summary)


if __name__ == "__main__":
    unittest.main()
