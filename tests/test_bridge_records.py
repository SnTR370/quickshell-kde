#!/usr/bin/env python3
"""
P0 #9 Intellihide — KWin event bridge record merge tests.

SAFE: pure JS logic (services/kwin/BridgeRecords.js) executed under node (vm).
No quickshell/KWin/qdbus/Wayland is launched. Covers the merge layer that
WindowService.handleBridgeBatch runs on every bridge batch: uuid
normalization, strict validation, atomic snapshots, update/remove/desktop
payloads and capability defaults.
"""
import json
import os
import subprocess
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(REPO, "services/kwin/BridgeRecords.js")

DRIVER = r"""
const vm = require('vm'), fs = require('fs');
const ctx = {};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8').replace(/^\.pragma.*$/m, ''), ctx);
const B = ctx;
const input = JSON.parse(process.argv[2]);
let res;
if (input.op === 'validate') {
  res = B.validateWindowRecord(input.raw);
} else {
  res = B.applyBatch(input.states || {}, input.outputs || {}, input.payloads);
}
console.log(JSON.stringify(res));
"""

UUID = "0c1d2e3f-4a5b-4c6d-8e9f-a0b1c2d3e4f5"
UUID2 = "1d2e3f4a-5b4c-6d8e-9fa0-b1c2d3e4f5a6"


def run(op, raw=None, states=None, outputs=None, payloads=None):
    p = subprocess.run(
        ["node", "-e", DRIVER, JS, json.dumps(dict(
            op=op, raw=raw, states=states, outputs=outputs, payloads=payloads))],
        capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def rec(uuid=UUID, **kw):
    r = {
        "uuid": uuid, "output": "DP-1",
        "minimized": False, "maximizeMode": 0, "maximized": False,
        "fullScreen": False, "keepAbove": False, "onAllDesktops": False,
        "specialWindow": False,
        "desktops": ["d1"], "x": 0, "y": 0, "width": 100, "height": 100,
    }
    r.update(kw)
    return r


def batch(payloads, states=None, outputs=None):
    return run("batch", states=states, outputs=outputs, payloads=payloads)


class TestValidateWindowRecord(unittest.TestCase):
    def test_accepts_and_normalizes_uuid(self):
        for raw_uuid in (UUID, UUID.upper(), "{%s}" % UUID, "0_%s" % UUID,
                         "0_{%s}" % UUID.upper()):
            with self.subTest(raw_uuid=raw_uuid):
                r = run("validate", rec(uuid=raw_uuid))
                self.assertIsNotNone(r)
                self.assertEqual(r["uuid"], UUID)

    def test_rejects_invalid_uuid(self):
        for raw_uuid in ("", "not-a-uuid", "{}", 42, None, "0_" + UUID[:-1]):
            with self.subTest(raw_uuid=raw_uuid):
                self.assertIsNone(run("validate", rec(uuid=raw_uuid)))

    def test_rejects_wrong_types(self):
        cases = {
            "output non-string": rec(output=7),
            "output missing": {k: v for k, v in rec().items() if k != "output"},
            "desktops non-array": rec(desktops="d1"),
            "desktops bad id": rec(desktops=["d 1"]),
            "desktops empty id": rec(desktops=[""]),
            "desktops non-string": rec(desktops=[1]),
            "x non-number": rec(x="5"),
            "width infinite-like": rec(width=1e999 if False else "w"),
            "minimized truthy int": rec(minimized=1),
            "fullScreen string": rec(fullScreen="true"),
            "maximizeMode string": rec(maximizeMode="3"),
            "maximizeMode missing": {k: v for k, v in rec().items() if k != "maximizeMode"},
            "cap non-boolean": rec(closeable=0),
        }
        for name, raw in cases.items():
            with self.subTest(case=name):
                self.assertIsNone(run("validate", raw))

    def test_capability_defaults(self):
        raw = rec()
        r = run("validate", raw)
        for cap in ("minimizable", "maximizable", "fullScreenable",
                    "closeable", "moveable", "moveableAcrossScreens"):
            self.assertTrue(r[cap])
        r2 = run("validate", rec(closeable=False, moveableAcrossScreens=False))
        self.assertFalse(r2["closeable"])
        self.assertFalse(r2["moveableAcrossScreens"])
        self.assertTrue(r2["minimizable"])

    def test_geometry_rounded(self):
        r = run("validate", rec(x=10.4, y=20.6, width=100.5, height=1.0))
        self.assertEqual((r["x"], r["y"], r["width"], r["height"]), (10, 21, 101, 1))

    def test_non_object_rejected(self):
        for raw in (None, 5, "x", [], [rec()]):
            with self.subTest(raw=raw):
                self.assertIsNone(run("validate", raw))


class TestApplyBatch(unittest.TestCase):
    def test_non_array_rejected(self):
        self.assertFalse(batch(None)["ok"])
        self.assertFalse(batch({})["ok"])
        self.assertFalse(batch("snapshot")["ok"])

    def test_snapshot_replaces_atomically(self):
        states = {UUID2: {"minimized": True}}
        res = batch([{"type": "snapshot", "desktop": "d2", "windows": [rec()]}],
                    states=states, outputs={UUID2: "HDMI-1"})
        self.assertTrue(res["ok"])
        self.assertEqual(sorted(res["states"]), [UUID])
        self.assertEqual(sorted(res["outputs"]), [UUID])
        self.assertEqual(res["states"][UUID]["desktops"], ["d1"])
        self.assertEqual(res["desktopId"], "d2")

    def test_snapshot_with_one_bad_record_rejected_entirely(self):
        states = {UUID2: {"minimized": True}}
        res = batch([{"type": "snapshot", "windows": [rec(), rec(uuid="junk")]}],
                    states=states)
        self.assertTrue(res["ok"])
        # Previous state untouched: atomic replace means all-or-nothing.
        self.assertEqual(sorted(res["states"]), [UUID2])
        self.assertEqual(res["applied"], 0)
        self.assertEqual(res["skipped"], 1)

    def test_snapshot_without_windows_field_rejected(self):
        res = batch([{"type": "snapshot", "desktop": "d1"}])
        self.assertEqual(res["applied"], 0)
        self.assertEqual(res["skipped"], 1)

    def test_update_applies_and_empty_output_removes(self):
        res = batch([{"type": "update", "window": rec(output="DP-1")}])
        self.assertEqual(res["outputs"], {UUID: "DP-1"})
        res2 = batch([{"type": "update", "window": rec(output="")}], res["states"], res["outputs"])
        self.assertNotIn(UUID, res2["outputs"])
        self.assertIn(UUID, res2["states"])

    def test_update_invalid_record_skipped(self):
        res = batch([{"type": "update", "window": {"uuid": "junk"}}])
        self.assertEqual(res["applied"], 0)
        self.assertEqual(res["skipped"], 1)
        self.assertEqual(res["states"], {})

    def test_remove(self):
        states = {UUID: {"minimized": False}}
        res = batch([{"type": "remove", "uuid": "{%s}" % UUID.upper()}], states, {UUID: "DP-1"})
        self.assertEqual(res["states"], {})
        self.assertEqual(res["outputs"], {})
        self.assertEqual(res["applied"], 1)

    def test_remove_invalid_uuid_skipped(self):
        states = {UUID: {"minimized": False}}
        res = batch([{"type": "remove", "uuid": "junk"}], states)
        self.assertEqual(res["states"], {UUID: {"minimized": False}})
        self.assertEqual(res["skipped"], 1)

    def test_desktop_payload(self):
        res = batch([{"type": "desktop", "desktop": "d3"}])
        self.assertEqual(res["desktopId"], "d3")
        self.assertEqual(res["applied"], 1)
        res = batch([{"type": "desktop", "desktop": "d 3"}])
        self.assertEqual(res["desktopId"], "")
        self.assertEqual(res["skipped"], 1)
        res = batch([{"type": "desktop", "desktop": 3}])
        self.assertEqual(res["desktopId"], "")
        self.assertEqual(res["skipped"], 1)

    def test_unknown_payload_type_skipped(self):
        res = batch([{"type": "bogus"}, "string", 5, None])
        self.assertEqual(res["applied"], 0)
        self.assertEqual(res["skipped"], 4)
        self.assertEqual(res["states"], {})

    def test_order_matters(self):
        # update then remove -> gone; remove then update -> present
        r1 = batch([{"type": "update", "window": rec()},
                    {"type": "remove", "uuid": UUID}])
        self.assertEqual(r1["states"], {})
        r2 = batch([{"type": "remove", "uuid": UUID},
                    {"type": "update", "window": rec()}])
        self.assertEqual(sorted(r2["states"]), [UUID])

    def test_desktop_only_batch_reports_no_change(self):
        res = batch([{"type": "desktop", "desktop": "d9"}])
        self.assertFalse(res["changed"])
        self.assertTrue(res["ok"])

    def test_state_shape_matches_snapshot_parser(self):
        # Same keys/semantics as WindowService.parseWindowOutputsJson entries.
        res = batch([{"type": "update", "window": rec(
            maximizeMode=3, specialWindow=True, closeable=False)}])
        st = res["states"][UUID]
        self.assertTrue(st["maximized"])       # (maximizeMode & 3) === 3
        self.assertEqual(st["maximizeMode"], 3)
        self.assertFalse(st["keepAboveable"])  # !specialWindow
        self.assertFalse(st["closeable"])
        for key in ("minimized", "minimizable", "maximizable", "fullScreen",
                    "fullScreenable", "keepAbove", "moveable",
                    "moveableAcrossScreens", "onAllDesktops", "desktops",
                    "x", "y", "width", "height"):
            self.assertIn(key, st)


if __name__ == "__main__":
    unittest.main()
