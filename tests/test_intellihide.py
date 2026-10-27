"""Execute production Intellihide.js under Node; no shell/compositor startup."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
DRIVER = r"""
const fs = require('fs'), vm = require('vm');
const ctx = vm.createContext({});
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8').replace(/^\.pragma.*$/m, ''), ctx);
const input = JSON.parse(process.argv[2]);
console.log(JSON.stringify(input.map(c => ctx.isObstructed(c.rect, c.states, c.desktop))));
"""
RECT = dict(x=0, y=0, width=100, height=100)


def obstructed(states, desktop="d1"):
    result = subprocess.run(
        ["node", "-e", DRIVER, str(ROOT / "services/kwin/Intellihide.js"),
         json.dumps([dict(rect=RECT, states=states, desktop=desktop)])],
        capture_output=True, text=True, timeout=10, check=True)
    return json.loads(result.stdout)[0]


class TestIntellihideDesktop(unittest.TestCase):
    def test_unknown_current_desktop(self):
        for desktop in (None, "", "  ", 1, False):
            with self.subTest(desktop=desktop):
                self.assertFalse(obstructed([{**RECT, "desktops": ["d1"]}], desktop))

    def test_missing_or_invalid_window_membership(self):
        self.assertFalse(obstructed([RECT]))
        for desktops in (None, [], "d1", {}, [None], [""], ["  "], [1]):
            with self.subTest(desktops=desktops):
                self.assertFalse(obstructed([{**RECT, "desktops": desktops}]))

    def test_confirmed_all_desktops(self):
        for desktop in (None, "", "  ", "d1", "d2"):
            with self.subTest(desktop=desktop):
                self.assertTrue(obstructed([{**RECT, "onAllDesktops": True}], desktop))

    def test_truthy_values_do_not_confirm_all_desktops(self):
        for value in (1, "true", "false", [], {}):
            with self.subTest(value=value):
                self.assertFalse(obstructed([{**RECT, "onAllDesktops": value}]))

    def test_matching_membership(self):
        self.assertTrue(obstructed([{**RECT, "desktops": ["d2", "d1"]}]))

    def test_other_desktop(self):
        self.assertFalse(obstructed([{**RECT, "desktops": ["d2"]}]))

    def test_minimized_all_desktops_does_not_obstruct(self):
        self.assertFalse(obstructed([{**RECT, "onAllDesktops": True, "minimized": True}], None))

    def test_nonoverlapping_all_desktops_does_not_obstruct(self):
        self.assertFalse(obstructed([{**RECT, "x": 100, "onAllDesktops": True}], None))

    def test_invalid_geometry_does_not_obstruct(self):
        self.assertFalse(obstructed([{**RECT, "width": 0, "onAllDesktops": True}], None))

    def test_unknown_window_does_not_mask_confirmed_window(self):
        self.assertTrue(obstructed([RECT, {**RECT, "desktops": ["d1"]}]))


if __name__ == "__main__":
    unittest.main()
