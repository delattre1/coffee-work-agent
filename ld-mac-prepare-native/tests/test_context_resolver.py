import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from context_resolver import ContextResolver  # noqa: E402
from unittest.mock import patch


class ContextResolverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.context = Path(self.temp.name) / "context.json"
        self.audit_patch = patch("context_resolver.audit", lambda *args, **kwargs: None)
        self.audit_patch.start()
        self.resolver = ContextResolver(self.context)

    def tearDown(self):
        self.audit_patch.stop()
        self.temp.cleanup()

    def test_builtin_and_custom_modes(self):
        self.assertIn("coding", self.resolver.list_modes())
        mode = self.resolver.set_mode(
            "demo", ["Keynote", "Notes", "Keynote"], ["https://example.com"], ["Slack"], "presentable"
        )
        self.assertEqual(mode["apps"], ["Keynote", "Notes"])
        self.assertEqual(ContextResolver(self.context).resolve_mode("demo")["layout"], "presentable")

    def test_patch_is_incremental_and_case_insensitive(self):
        mode = self.resolver.patch_mode("coding", ["Spotify"], [], [], [], [], ["messages"], None)
        self.assertIn("Spotify", mode["apps"])
        self.assertNotIn("Messages", mode["hide_apps"])

    def test_rejects_unsafe_url_scheme(self):
        with self.assertRaises(ValueError):
            self.resolver.set_mode("bad", [], ["javascript:alert(1)"], [], "none")

    def test_file_is_valid_json(self):
        self.resolver.set_mode("demo", [], [], [], "none")
        with self.context.open(encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["schema_version"], 2)


if __name__ == "__main__":
    unittest.main()
