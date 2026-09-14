import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coffee_work import core, cli
from coffee_work.google import Google

NOW = datetime(2026, 9, 12, 12, tzinfo=timezone.utc)


def event(id, kind="meeting", mins=8):
    start = (NOW + timedelta(minutes=mins)).isoformat()
    return {"id": id, "summary": "Planning", "start": {"dateTime": start},
            "attendees": [{"email": "a@example.com"}] if kind == "meeting" else [],
            "extendedProperties": {"private": {"coffee_work_type": kind}} if kind != "meeting" else {}}


class CoordinatorTest(unittest.TestCase):
    def test_tick_once_per_event_and_no_unapproved_recording(self):
        class FakeGoogle:
            def upcoming(self, now):
                return [event("meeting"), event("dinner", "restaurant", 45)]
        messages = []
        with tempfile.TemporaryDirectory() as temp, patch.object(cli, "HOME", Path(temp)):
            first = cli.tick(FakeGoogle(), {"mode": "manual"}, NOW, lambda text, cfg: messages.append(text))
            second = cli.tick(FakeGoogle(), {"mode": "manual"}, NOW, lambda text, cfg: messages.append(text))
        self.assertEqual(len(first), 3)
        self.assertEqual(second, [])
        self.assertEqual(len(messages), 3)
        self.assertTrue(any("record" in m.lower() and "explicit consent" in m for m in messages))
        self.assertTrue(any("Uber" in m for m in messages))

    def test_auto_prepares_but_only_offers_recording(self):
        class FakeGoogle:
            def upcoming(self, now):
                return [event("m")]
        notices = []
        with tempfile.TemporaryDirectory() as temp, patch.object(cli, "HOME", Path(temp)), patch.object(cli, "prepare", return_value={"join_link_opened": True}) as prep:
            out = cli.tick(FakeGoogle(), {"mode": "automatic"}, NOW, lambda text, cfg: notices.append(text))
        prep.assert_called_once()
        self.assertEqual([x["status"] for x in out], ["completed", "offered"])
        self.assertEqual(len(notices), 2)

    def test_failed_notification_retries(self):
        class FakeGoogle:
            def upcoming(self, now):
                return [event("m")]
        with tempfile.TemporaryDirectory() as temp, patch.object(cli, "HOME", Path(temp)):
            first = cli.tick(FakeGoogle(), {"mode": "manual"}, NOW, lambda text, cfg: (_ for _ in ()).throw(RuntimeError("offline")))
            again = cli.tick(FakeGoogle(), {"mode": "manual"}, NOW, lambda text, cfg: None)
        self.assertTrue(all(x["status"] == "failed" for x in first))
        self.assertEqual(len(again), 2)

    def test_allowlisted_link_only(self):
        self.assertIsNone(core.meeting_link({"description": "Join https://evil.example/?next=https://meet.google.com/x"}))
        self.assertEqual(core.meeting_link({"description": "Join https://meet.google.com/abc-defg-hij"}), "https://meet.google.com/abc-defg-hij")
        self.assertIsNone(core.meeting_link({"description": "https://meet.google.com.evil.example/a"}))

    def test_calendar_rejects_bad_date_and_foreign_delete(self):
        api = Google()
        with self.assertRaises(ValueError):
            api.create("X", "2026-09-12T10:00:00", "2026-09-12T11:00:00")
        class Events:
            def get(self, **kw): return self
            def execute(self): return {"summary": "someone else's event"}
        class Calendar:
            def events(self): return Events()
        api._calendar = Calendar()
        with self.assertRaises(ValueError):
            api.delete("other")

if __name__ == "__main__":
    unittest.main()
