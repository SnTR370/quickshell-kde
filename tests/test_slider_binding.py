#!/usr/bin/env python3
"""
P1 regression: Slider must not destroy a consumer's declarative `value` binding.

Layer: OFFSCREEN runtime. The real components/Slider.qml is driven by QtTest
mouse drag / click / wheel events inside `QT_QPA_PLATFORM=offscreen`, with an
isolated XDG_CONFIG_HOME. No KWin / Plasma session is touched.

Defect (pre-fix): MouseArea.updateFromMouse() and onWheel assigned
`root.value = ...` imperatively. In QML that assignment replaces the consumer's
declarative binding (e.g. `value: AudioService.volume`), so subsequent external
volume/brightness updates no longer move the slider.

Expected after the fix:
  * drag/click/wheel move the rendered slider and emit valueModified,
  * the external binding stays declarative,
  * a later external value update is reflected by the slider.
"""

import os
import subprocess
import tempfile
import unittest

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HARNESS = r"""import QtQuick
import QtQuick.Layouts
import QtTest
import Quickshell
import "./services"
import "./components"

FloatingWindow {
    id: win
    implicitWidth: 640
    implicitHeight: 400
    visible: true

    // External model values, mirroring AudioService.volume / BrightnessService.brightness.
    property real boundValue: 0.20
    property real freeValue: 0.20
    property var emittedBound: []
    property var emittedFree: []
    property var emittedPlain: []

    Column {
        x: 20
        y: 20
        spacing: 24

        // A: realistic consumer — declarative binding + handler feeding the model.
        Slider {
            id: boundSlider
            width: 200
            height: 24
            minimumValue: 0.0
            maximumValue: 1.0
            stepSize: 0.01
            value: win.boundValue
            onValueModified: v => { win.emittedBound.push(v); win.boundValue = v; }
        }

        // B: declarative binding only, no handler (a read/write control whose owner
        // updates the model out-of-band, e.g. media keys).
        Slider {
            id: freeSlider
            width: 200
            height: 24
            minimumValue: 0.0
            maximumValue: 1.0
            stepSize: 0.01
            value: win.freeValue
        }

        // C: uncontrolled slider, no external binding.
        Slider {
            id: plainSlider
            width: 200
            height: 24
            minimumValue: 0.0
            maximumValue: 1.0
            stepSize: 0.01
            value: 0.50
            onValueModified: v => win.emittedPlain.push(v)
        }
    }

    TestCase {
        id: tc
        name: "SliderBinding"
        when: false
        property var res: ({})

        // Rendered value: after the fix the slider exposes an internal
        // `_displayValue`; before the fix fall back to the public value.
        function shown(s) {
            return (s._displayValue !== undefined) ? s._displayValue : s.value;
        }

        function runTests() {
            const R = {};
            tc.res = R;
            wait(50);

            R.initialBound = boundSlider.value;
            R.initialFree = freeSlider.value;

            // ---- 1. Mouse drag -----------------------------------------------------
            // start at x=40 (0.2) and drag +100px -> x=140 (0.7)
            mouseDrag(boundSlider, 40, boundSlider.height / 2, 100, 0, Qt.LeftButton);
            wait(30);
            R.dragEmitted = win.emittedBound.slice();
            R.dragLast = R.dragEmitted.length ? R.dragEmitted[R.dragEmitted.length - 1] : -1;
            R.dragDisplayed = tc.shown(boundSlider);
            R.boundValueAfterDrag = win.boundValue;

            // A later external update (media key / other app) must move the slider.
            win.boundValue = 0.35;
            wait(30);
            R.boundValueAfterExternal = boundSlider.value;
            R.boundDisplayAfterExternal = tc.shown(boundSlider);

            // ---- 2. Click ----------------------------------------------------------
            win.emittedBound = [];
            mouseClick(boundSlider, 180, boundSlider.height / 2, Qt.LeftButton);
            wait(30);
            R.clickEmitted = win.emittedBound.slice();
            R.clickLast = R.clickEmitted.length ? R.clickEmitted[R.clickEmitted.length - 1] : -1;
            R.clickValue = boundSlider.value;

            // ---- 3. Wheel ----------------------------------------------------------
            const plainBefore = tc.shown(plainSlider);
            mouseWheel(plainSlider, 100, plainSlider.height / 2, 0, 120);
            wait(30);
            R.wheelEmitted = win.emittedPlain.slice();
            R.wheelDisplayed = tc.shown(plainSlider);
            R.wheelMoved = (plainBefore !== tc.shown(plainSlider));
            mouseWheel(plainSlider, 100, plainSlider.height / 2, 0, -120);
            wait(30);
            R.wheelBackEmitted = win.emittedPlain.length;

            // ---- 4. Hover / press-without-move must not emit -----------------------
            win.emittedBound = [];
            mouseMove(boundSlider, 60, boundSlider.height / 2);
            wait(20);
            R.hoverEmitted = win.emittedBound.length;

            // ---- 5. Drag on the binding-only slider, then external update ----------
            mouseDrag(freeSlider, 40, freeSlider.height / 2, 120, 0, Qt.LeftButton);
            wait(30);
            R.freeDisplayedAfterDrag = tc.shown(freeSlider);
            win.freeValue = 0.60;
            wait(30);
            R.freeValueAfterExternal = freeSlider.value;
            R.freeDisplayAfterExternal = tc.shown(freeSlider);

            // ---- 6. Public API surface still intact --------------------------------
            R.hasSignal = (boundSlider.valueModified !== undefined);
            R.initialBoundIsExternal = (R.initialBound === 0.20);
            R.initialFreeIsExternal = (R.initialFree === 0.20);

            console.log("SLIDER_BINDING_RESULT:" + JSON.stringify(R));
        }
    }

    Timer {
        interval: 300
        running: true
        repeat: false
        onTriggered: {
            try {
                tc.runTests();
            } catch (e) {
                console.log("SLIDER_BINDING_ERROR:" + e + " @ " + e.stack + " PARTIAL=" + JSON.stringify(tc.res));
            }
            Qt.quit();
        }
    }
}
"""


def run_harness(timeout=60):
    with tempfile.TemporaryDirectory() as tmp:
        env = os.environ.copy()
        env["XDG_CONFIG_HOME"] = tmp
        env["QT_QPA_PLATFORM"] = "offscreen"
        probe = os.path.join(REPO_DIR, "_test_slider_binding_probe.qml")
        try:
            with open(probe, "w") as f:
                f.write(HARNESS)
            proc = subprocess.run(
                ["quickshell", "-p", probe, "--no-duplicate"],
                cwd=REPO_DIR, env=env, capture_output=True, text=True, timeout=timeout,
            )
        finally:
            if os.path.exists(probe):
                os.remove(probe)
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    marker = "SLIDER_BINDING_RESULT:"
    if "SLIDER_BINDING_ERROR:" in combined:
        raise AssertionError(combined[combined.index("SLIDER_BINDING_ERROR:"):][:2500])
    if marker not in combined:
        raise AssertionError("Missing result marker in output:\n" + combined[-4000:])
    import json
    line = [l for l in combined.splitlines() if marker in l][-1]
    return json.loads(line.split(marker, 1)[1])


class TestSliderBinding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.R = run_harness()

    def test_01_initial_binding_respected(self):
        self.assertEqual(self.R["initialBound"], 0.20)
        self.assertEqual(self.R["initialFree"], 0.20)

    def test_02_drag_moves_slider_and_emits(self):
        self.assertTrue(self.R["dragEmitted"], "drag must emit valueModified")
        self.assertAlmostEqual(self.R["dragLast"], 0.70, delta=0.02)
        self.assertAlmostEqual(self.R["dragDisplayed"], 0.70, delta=0.02)
        self.assertAlmostEqual(self.R["boundValueAfterDrag"], self.R["dragLast"], delta=0.001)

    def test_03_external_update_after_drag_reaches_slider(self):
        # The core P1 regression: a later external update must move the slider.
        self.assertAlmostEqual(self.R["boundValueAfterExternal"], 0.35, delta=0.001)
        self.assertAlmostEqual(self.R["boundDisplayAfterExternal"], 0.35, delta=0.001)

    def test_04_click_moves_slider_and_emits(self):
        self.assertTrue(self.R["clickEmitted"], "click must emit valueModified")
        self.assertAlmostEqual(self.R["clickLast"], 0.90, delta=0.02)

    def test_05_wheel_moves_slider_and_emits(self):
        self.assertTrue(self.R["wheelMoved"], "wheel must move the displayed slider")
        self.assertTrue(self.R["wheelEmitted"], "wheel must emit valueModified")
        self.assertAlmostEqual(self.R["wheelEmitted"][0], 0.51, delta=0.001)
        self.assertAlmostEqual(self.R["wheelDisplayed"], 0.51, delta=0.001)
        self.assertEqual(self.R["wheelBackEmitted"], 2)

    def test_06_hover_does_not_emit(self):
        self.assertEqual(self.R["hoverEmitted"], 0)

    def test_07_binding_survives_drag_without_handler(self):
        self.assertAlmostEqual(self.R["freeDisplayedAfterDrag"], 0.80, delta=0.02)
        self.assertAlmostEqual(self.R["freeValueAfterExternal"], 0.60, delta=0.001)
        self.assertAlmostEqual(self.R["freeDisplayAfterExternal"], 0.60, delta=0.001)

    def test_08_public_api_preserved(self):
        self.assertTrue(self.R["hasSignal"])
        self.assertTrue(self.R["initialBoundIsExternal"])
        self.assertTrue(self.R["initialFreeIsExternal"])


if __name__ == "__main__":
    unittest.main()
