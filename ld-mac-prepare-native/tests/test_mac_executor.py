import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from mac_executor import _layout_bounds, apply_layout, capture_capsule  # noqa: E402


class MacExecutorTests(unittest.TestCase):
    def setUp(self):
        self.screen = {"x": 0, "y": 24, "width": 1440, "height": 876}

    def test_presentable_has_hero_and_support_column(self):
        bounds = _layout_bounds("presentable", self.screen, 3)
        self.assertEqual(len(bounds), 3)
        self.assertGreater(bounds[0][2], bounds[1][2])
        self.assertEqual(bounds[1][0], bounds[2][0])

    def test_all_layouts_return_positive_dimensions(self):
        for preset in ("presentable", "split", "top", "corner", "grid"):
            for bounds in _layout_bounds(preset, self.screen, 4):
                self.assertGreater(bounds[2], 0)
                self.assertGreater(bounds[3], 0)

    def test_dry_run_never_requires_macos(self):
        result = apply_layout(["Keynote", "Notes"], "split", dry_run=True)
        self.assertEqual(result["displays"], 1)
        capsule = capture_capsule("test intent", "test", dry_run=True)
        self.assertEqual(capsule["capsule"]["intent"], "test intent")


if __name__ == "__main__":
    unittest.main()
