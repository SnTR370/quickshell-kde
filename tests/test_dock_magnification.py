#!/usr/bin/env python3
"""
DOCK-004 Magnification tests: pointer-driven parabolic zoom + neighbor displacement.

SAFE: pure JS curve math executed under node (vm), static source contracts for
the QML wiring, and an offscreen Quickshell runtime probe exercising real
DockItem components (scale composition, lateral displacement, axis switch).
No quickshell/KWin/Wayland is launched against the live session.
"""
import json
import os
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(REPO, "modules/dock/Magnification.js")


def read(rel):
    with open(os.path.join(REPO, rel)) as f:
        return f.read()


DRIVER = r"""
const vm=require('vm'),fs=require('fs');
const ctx={};vm.createContext(ctx);vm.runInContext(fs.readFileSync(process.argv[1],'utf8').replace(/^\.pragma.*$/m,''),ctx);
const M=ctx;
const N=v=>(v==="@nan")?NaN:(v==="@inf")?Infinity:v;
const input=JSON.parse(process.argv[2]);
const out={};
if (input.bump) out.bump=input.bump.map(c=>M.bump(N(c.d),N(c.r)));
if (input.scaleAt) out.scaleAt=input.scaleAt.map(c=>M.scaleAt(N(c.d),N(c.r),N(c.m)));
if (input.resolve) out.resolve=input.resolve.map(c=>M.resolve(c.centers,c.extents,c.magnifiable,N(c.pointer),N(c.radius),N(c.maxScale),N(c.spacing)));
console.log(JSON.stringify(out));
"""


def run_node(payload):
    p = subprocess.run(["node", "-e", DRIVER, JS, json.dumps(payload)],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def resolve(centers, extents, magnifiable, pointer, radius=80, max_scale=1.5, spacing=8):
    r = run_node({"resolve": [dict(centers=centers, extents=extents, magnifiable=magnifiable,
                                   pointer=pointer, radius=radius, maxScale=max_scale,
                                   spacing=spacing)]})["resolve"][0]
    return r["scales"], r["offsets"], r["growth"]


def packed_centers(centers, offsets):
    """Reconstruct packed (displaced) centers the way the QML applies them."""
    return [c + o for c, o in zip(centers, offsets)]


class TestCurveMath(unittest.TestCase):
    """Pure parabolic curve properties (node vm, no QML)."""

    def test_bump_peak_and_compact_support(self):
        b = run_node({"bump": [{"d": 0, "r": 80}, {"d": 80, "r": 80},
                               {"d": 120, "r": 80}, {"d": -80, "r": 80},
                               {"d": 60, "r": 0}, {"d": 60, "r": -1},
                               {"d": "@nan", "r": 80}]})["bump"]
        self.assertAlmostEqual(b[0], 1.0, places=9)
        self.assertEqual(b[1], 0.0)
        self.assertEqual(b[2], 0.0)
        self.assertEqual(b[3], 0.0)  # symmetric: |d| used
        self.assertEqual(b[4], 0.0)  # invalid radius -> no magnification
        self.assertEqual(b[5], 0.0)
        self.assertEqual(b[6], 0.0)  # NaN distance -> safe zero

    def test_bump_monotonic_and_smooth_at_boundary(self):
        ds = [0, 20, 40, 60, 70, 76, 79, 80]
        b = run_node({"bump": [{"d": d, "r": 80} for d in ds]})["bump"]
        for i in range(len(b) - 1):
            self.assertGreaterEqual(b[i], b[i + 1])
        # C1 at the influence boundary: entering/leaving the radius causes no
        # jump in slope, so layout width changes smoothly (value ~ O(eps^2)).
        self.assertLess(b[6], 1e-3)

    def test_scale_at_configurable(self):
        s = run_node({"scaleAt": [
            {"d": 0, "r": 80, "m": 1.5},
            {"d": 80, "r": 80, "m": 1.5},
            {"d": 200, "r": 80, "m": 1.5},
            {"d": 0, "r": 80, "m": 2.0},
            {"d": 0, "r": 40, "m": 1.5},
            {"d": 60, "r": 40, "m": 1.5},
            {"d": 0, "r": 80, "m": 1.0},
            {"d": 0, "r": 80, "m": 0.5},
            {"d": 0, "r": 80, "m": "@nan"},
        ]})["scaleAt"]
        self.assertAlmostEqual(s[0], 1.5, places=9)
        self.assertAlmostEqual(s[1], 1.0, places=9)
        self.assertAlmostEqual(s[2], 1.0, places=9)
        self.assertAlmostEqual(s[3], 2.0, places=9)   # max scale configurable
        self.assertAlmostEqual(s[4], 1.5, places=9)
        self.assertAlmostEqual(s[5], 1.0, places=9)   # radius configurable
        self.assertEqual(s[6], 1.0)                   # maxScale <= 1 degrades to off
        self.assertEqual(s[7], 1.0)
        self.assertEqual(s[8], 1.0)                   # NaN maxScale degrades to off

    def test_scale_at_parabolic_values(self):
        # d=60, R=80: (1 - (60/80)^2)^2 = 0.19140625 -> 1 + 0.5 * that
        s = run_node({"scaleAt": [{"d": 60, "r": 80, "m": 1.5}]})["scaleAt"][0]
        self.assertAlmostEqual(s, 1.095703125, places=9)


class TestResolveLayout(unittest.TestCase):
    """Neighbor displacement + packing properties of Magnification.resolve (node vm)."""

    @staticmethod
    def equal_run(n=5, extent=52, spacing=8, start=26):
        centers = [start + i * (extent + spacing) for i in range(n)]
        return centers, [extent] * n

    def test_peak_neighbors_and_far_items(self):
        centers, extents = self.equal_run()
        scales, offsets, growth = resolve(centers, extents, [True] * 5, pointer=centers[2])
        self.assertAlmostEqual(scales[2], 1.5, places=9)   # nearest icon: max
        self.assertAlmostEqual(scales[1], 1.095703125, places=9)
        self.assertAlmostEqual(scales[3], 1.095703125, places=9)
        self.assertEqual(scales[0], 1.0)                   # outside radius: untouched
        self.assertEqual(scales[4], 1.0)
        self.assertAlmostEqual(growth, 52 * (0.5 + 2 * 0.095703125), places=6)
        self.assertGreater(growth, 0)

    def test_neighbors_physically_move_apart(self):
        centers, extents = self.equal_run()
        scales, offsets, growth = resolve(centers, extents, [True] * 5, pointer=centers[2])
        self.assertLess(offsets[0], -5)          # left side pushed left
        self.assertGreater(offsets[4], 5)        # right side pushed right
        self.assertAlmostEqual(offsets[0], -offsets[4], places=6)  # symmetric growth
        self.assertLess(abs(offsets[2]), 1.0)    # peak stays under the pointer
        # Packed magnified icons never overlap each other (incl. spacing).
        packed = packed_centers(centers, offsets)
        for i in range(4):
            gap = (packed[i + 1] - extents[i + 1] * scales[i + 1] / 2) \
                - (packed[i] + extents[i] * scales[i] / 2)
            self.assertGreaterEqual(gap, 8 - 1e-6)
        # Total run width grows by exactly `growth` and stays centered:
        self.assertAlmostEqual((packed[4] - packed[0]) - (centers[4] - centers[0]),
                               growth, places=6)
        run_center_before = (centers[0] - extents[0] / 2 + centers[4] + extents[4] / 2) / 2
        run_center_after = (packed[0] - extents[0] * scales[0] / 2
                            + packed[4] + extents[4] * scales[4] / 2) / 2
        self.assertAlmostEqual(run_center_before, run_center_after, places=6)

    def test_pointer_outside_or_inactive_resets_cleanly(self):
        centers, extents = self.equal_run()
        for pointer in (10000.0, "@nan", "@inf"):
            scales, offsets, growth = resolve(centers, extents, [True] * 5, pointer=pointer)
            self.assertEqual(scales, [1.0] * 5)
            self.assertEqual(offsets, [0.0] * 5)
            self.assertEqual(growth, 0.0)

    def test_non_magnifiable_entries_displace_but_never_scale(self):
        # Item, separator (1px), item: separator must move aside but keep scale 1.
        extents = [52, 1, 52]
        centers = [26, 60.5, 95]
        scales, offsets, growth = resolve(centers, extents, [True, False, True], pointer=26)
        self.assertAlmostEqual(scales[0], 1.5, places=9)
        self.assertEqual(scales[1], 1.0)
        # Item 2 sits 69px from the pointer: 1 + 0.5 * (1 - (69/80)^2)^2
        expected = 1 + 0.5 * ((1 - (69 / 80) ** 2) ** 2)
        self.assertAlmostEqual(scales[2], expected, places=9)
        self.assertNotEqual(offsets[1], 0.0)
        self.assertGreater(growth, 0)

    def test_axis_generic_vertical_data(self):
        # Vertical docks project y-centers onto the same 1-D math: identical
        # results with different extent/spacing magnitudes (e.g. a tall dock).
        centers = [30 + i * 66 for i in range(5)]  # y-centers, extent 60
        scales, offsets, growth = resolve(centers, [60] * 5, [True] * 5,
                                          pointer=centers[1], radius=90, max_scale=1.8,
                                          spacing=6)
        self.assertAlmostEqual(scales[1], 1.8, places=9)
        self.assertGreater(scales[2], 1.0)
        self.assertEqual(scales[4], 1.0)  # 3*66 = 198 > 90: outside radius
        self.assertLess(offsets[0], 0)
        self.assertGreater(offsets[4], 0)
        self.assertGreater(growth, 0)

    def test_js_has_no_polling(self):
        self.assertNotRegex(read("modules/dock/Magnification.js"),
                            r"Timer|setInterval|setTimeout|Process|execDetached")


class TestStaticWiring(unittest.TestCase):
    """Static source contracts for the QML integration."""

    def setUp(self):
        self.dock = read("modules/dock/Dock.qml")
        self.item = read("modules/dock/DockItem.qml")
        self.sep = read("modules/dock/DockSeparator.qml")
        self.slot = read("modules/dock/MagnifySlot.qml")
        self.cfg = read("services/config/ConfigService.qml")

    def test_dockitem_magnification_state_and_translate(self):
        self.assertIn("property real magnifiedScale: 1.0", self.item)
        self.assertIn("property real magnifiedOffset: 0.0", self.item)
        self.assertIn("readonly property real appliedMagnifiedOffset: root.isVerticalDock ? magTranslate.y : magTranslate.x", self.item)
        # Displacement is a transform on the WHOLE item along the layout axis.
        self.assertIn("id: magTranslate", self.item)
        self.assertIn("x: root.isVerticalDock ? 0 : root.magnifiedOffset", self.item)
        self.assertIn("y: root.isVerticalDock ? root.magnifiedOffset : 0", self.item)

    def test_dockitem_scale_contracts_preserved(self):
        # Pressed 0.92 still wins; the hover/popup 1.15 floor literal survives
        # verbatim; bounce still multiplies; magnification can only raise.
        self.assertIn("(dockItemMouse.pressed ? 0.92 :", self.item)
        self.assertIn("((dockItemMouse.containsMouse || root.isPopupOpen) ? 1.15 : 1.0)", self.item)
        self.assertIn("Math.max(((dockItemMouse.containsMouse || root.isPopupOpen) ? 1.15 : 1.0), root.magnifiedScale)", self.item)
        self.assertIn("* root.bounceScale", self.item)

    def test_dock_controller_wiring(self):
        self.assertIn('import "Magnification.js" as Magnification', self.dock)
        self.assertIn("function updateMagnification(surfacePos)", self.dock)
        self.assertIn("function resetMagnification()", self.dock)
        self.assertIn("Magnification.resolve(centers, extents, magnifiable, pointer", self.dock)
        # Event-driven pointer tracking via the existing surface HoverHandler.
        self.assertIn("onPointChanged: {", self.dock)
        self.assertIn("dockWindow.updateMagnification(point.position)", self.dock)
        # Surface grows with the displaced run so icons stay inside the dock.
        self.assertIn("rowLayout.implicitWidth + 16 + dockWindow.magnifiedGrowth", self.dock)
        self.assertIn("colLayout.implicitHeight + 16 + dockWindow.magnifiedGrowth", self.dock)

    def test_dock_controller_axis_generic(self):
        # The math is driven from the layout axis, not hardcoded x.
        self.assertIn("(vert ? mapped.y : mapped.x) - e.appliedMagnifiedOffset", self.dock)
        self.assertIn("(vert ? surfacePos.y : surfacePos.x)", self.dock)
        self.assertIn("dockWindow.isVertical ? colLayout : rowLayout", self.dock)
        self.assertIn("e.mapToItem(dockSurface, e.width / 2, e.height / 2)", self.dock)

    def test_dock_reset_triggers(self):
        self.assertIn("dockWindow.resetMagnification();", self.dock)
        # Reset when the pointer leaves, on drag start, on edge switch, when
        # hidden and when the user disables magnification.
        self.assertIn("function onDockMagnificationChanged()", self.dock)
        block = self.dock[self.dock.index("onIsDraggingChanged"):self.dock.index("onEdgeChanged")]
        self.assertIn("dockWindow.resetMagnification();", block)

    def test_no_new_timers_or_polling_in_dock(self):
        # Only the pre-existing timers: Dock has reveal/hide (2), DockItem has
        # the tooltip dwell timer (1); magnification adds none anywhere.
        self.assertEqual(self.dock.count("Timer {"), 2)
        self.assertEqual(self.item.count("Timer {"), 1)
        self.assertNotIn("setInterval", self.dock)
        for src in (self.item, self.sep, self.slot):
            self.assertNotRegex(src, r"setInterval|setTimeout")

    def test_separator_and_slot_displaceable(self):
        self.assertIn("property real magnifiedOffset: 0", self.sep)
        self.assertIn("id: sepTranslate", self.sep)
        self.assertIn("property real magnifiedOffset: 0", self.slot)
        self.assertIn("id: slotTranslate", self.slot)
        # Launcher/settings buttons wrapped so they displace with the icons.
        self.assertEqual(self.dock.count("MagnifySlot {"), 4)
        self.assertIn("MagnifySlot 1.0 MagnifySlot.qml", read("modules/dock/qmldir"))

    def test_config_service_knobs(self):
        self.assertIn("property bool dockMagnification: true", self.cfg)
        self.assertIn("property real dockMagnifyMaxScale: 1.5", self.cfg)
        self.assertIn("property int dockMagnifyRadius: 80", self.cfg)
        self.assertIn('"magnification": root.dockMagnification', self.cfg)
        self.assertIn('"magnifyMaxScale": root.dockMagnifyMaxScale', self.cfg)
        self.assertIn('"magnifyRadius": root.dockMagnifyRadius', self.cfg)
        self.assertIn("function setDockMagnification(on)", self.cfg)
        self.assertIn("function setDockMagnifyMaxScale(scale)", self.cfg)
        self.assertIn("function setDockMagnifyRadius(radius)", self.cfg)
        # Load path with clamping.
        self.assertIn('typeof parsed.magnification === "boolean"', self.cfg)
        self.assertIn("Math.max(1.0, Math.min(3.0, parsed.magnifyMaxScale))", self.cfg)
        self.assertIn("Math.max(24, Math.min(320, Math.round(parsed.magnifyRadius)))", self.cfg)

    def test_settings_ui_wiring(self):
        s = read("modules/settings/SettingsWindow.qml")
        self.assertIn("ConfigService.setDockMagnification(!ConfigService.dockMagnification)", s)
        self.assertIn("ConfigService.setDockMagnifyMaxScale(val)", s)
        self.assertIn("ConfigService.setDockMagnifyRadius(Math.round(val))", s)

    def test_fallback_config_defaults(self):
        d = json.loads(read("config/dock_config.json"))
        self.assertIs(d["magnification"], True)
        self.assertEqual(d["magnifyMaxScale"], 1.5)
        self.assertEqual(d["magnifyRadius"], 80)

    def test_qmllint_changed_modules(self):
        res = subprocess.run(
            ["qmllint", "modules/dock/Dock.qml", "modules/dock/DockItem.qml",
             "modules/dock/DockSeparator.qml", "modules/dock/MagnifySlot.qml",
             "services/config/ConfigService.qml", "modules/settings/SettingsWindow.qml"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"qmllint failed: {res.stderr}")


class TestRuntimeMagnification(unittest.TestCase):
    """Offscreen Quickshell runtime probe with real DockItem components."""

    def test_runtime_scale_displacement_and_axis_switch(self):
        probe_path = os.path.join(REPO, "_test_dock_magnify_probe.qml")
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["XDG_CONFIG_HOME"] = tmpdir
            env["QT_QPA_PLATFORM"] = "offscreen"
            try:
                with open(probe_path, "w") as pf:
                    pf.write("""import QtQuick
import QtQuick.Layouts
import QtTest
import Quickshell
import "./services"
import "./modules/dock"
import "./modules/dock/Magnification.js" as Magnification

FloatingWindow {
    id: win
    implicitWidth: 800
    implicitHeight: 400
    visible: true

    property string edge: "bottom"
    property bool isVertical: false
    property var activePopupItem: null
    readonly property bool hasActivePopup: activePopupItem !== null
    property var activeDragItem: null
    readonly property bool isDragging: activeDragItem !== null
    property bool isRevealed: true

    // Plain Item host: mapToItem targets must be Items, not the window.
    Item {
        id: host
        anchors.fill: parent

        RowLayout {
            id: horizLayout
            visible: !win.isVertical
            x: 40
            y: 40
            spacing: 8

            Repeater {
                id: horizRep
                model: ["org.kde.dolphin", "org.kde.konsole", "firefox", "code", "systemsettings"]
                DockItem {
                    required property var modelData
                    parentWindowRef: win
                    appId: modelData
                }
            }
        }

        ColumnLayout {
            id: vertLayout
            visible: win.isVertical
            x: 40
            y: 40
            spacing: 8

            Repeater {
                id: vertRep
                model: ["org.kde.dolphin", "org.kde.konsole", "firefox", "code", "systemsettings"]
                DockItem {
                    required property var modelData
                    parentWindowRef: win
                    appId: modelData
                }
            }
        }

        MagnifySlot {
            id: probeSlot
            dockWindowRef: win
            x: 600
            y: 200
            Rectangle { width: 40; height: 40; color: "blue" }
        }
    }

    TestCase {
        id: tc
        name: "DockMagnificationSuite"
        when: false

        function restCenters(rep, axis) {
            const res = [];
            for (let i = 0; i < rep.count; i++) {
                const it = rep.itemAt(i);
                const p = it.mapToItem(host, it.width / 2, it.height / 2);
                res.push((axis === "y" ? p.y : p.x) - it.appliedMagnifiedOffset);
            }
            return res;
        }

        function liveCenters(rep, axis) {
            const res = [];
            for (let i = 0; i < rep.count; i++) {
                const it = rep.itemAt(i);
                const p = it.mapToItem(host, it.width / 2, it.height / 2);
                res.push(axis === "y" ? p.y : p.x);
            }
            return res;
        }

        function applyResult(rep, res) {
            for (let i = 0; i < rep.count; i++) {
                rep.itemAt(i).magnifiedScale = res.scales[i];
                rep.itemAt(i).magnifiedOffset = res.offsets[i];
            }
        }

        function resetItems(rep) {
            for (let i = 0; i < rep.count; i++) {
                rep.itemAt(i).magnifiedScale = 1.0;
                rep.itemAt(i).magnifiedOffset = 0.0;
            }
        }

        function runTests() {
            wait(50);

            // --- Horizontal (bottom edge): pointer over the middle item ---
            const rest = restCenters(horizRep, "x");
            const extents = [];
            for (let i = 0; i < horizRep.count; i++) extents.push(horizRep.itemAt(i).width);
            const magnifiable = [true, true, true, true, true];
            const res = Magnification.resolve(rest, extents, magnifiable, rest[2], 80, 1.5, 8);
            const growth = res.growth;
            applyResult(horizRep, res);
            wait(250); // let the displacement/scale Behaviors settle

            const scalePeak = horizRep.itemAt(2).targetScale;
            const scaleNeighbor = horizRep.itemAt(1).targetScale;
            const scaleFar = horizRep.itemAt(0).targetScale;
            const after = liveCenters(horizRep, "x");
            const recoveredRest = restCenters(horizRep, "x");
            const restStable = recoveredRest.every((v, i) => Math.abs(v - rest[i]) < 0.5);

            // Slot displacement (launcher/settings wrapper mechanism).
            const slotBefore = probeSlot.mapToItem(host, 0, 0).x;
            probeSlot.magnifiedOffset = 25;
            wait(250);
            const slotAfter = probeSlot.mapToItem(host, 0, 0).x;
            const slotApplied = probeSlot.appliedMagnifiedOffset;
            probeSlot.magnifiedOffset = 0;

            // --- Scale contract composition on a single item ---
            const cItem = horizRep.itemAt(4);
            resetItems(horizRep);
            wait(250);
            const plainScale = cItem.targetScale;                 // no hover/popup/magnify
            cItem.magnifiedScale = 1.4;
            const magnifiedScale = cItem.targetScale;             // curve raises above floor
            cItem.menuOpen = true;
            const popupWithMagnify = cItem.targetScale;           // max(1.15, 1.4)
            cItem.magnifiedScale = 1.0;                           // controller reset (pointer left)
            const popupFloorPreserved = cItem.targetScale;        // 1.15 fallback
            cItem.menuOpen = false;
            cItem.bounceScale = 0.86;
            cItem.magnifiedScale = 1.5;
            const bounceComposition = cItem.targetScale;          // 1.5 * 0.86
            cItem.bounceScale = 1.0;
            cItem.magnifiedScale = 1.0;

            // --- Vertical (left edge): same math on the y axis ---
            win.isVertical = true;
            wait(50);
            const restV = restCenters(vertRep, "y");
            const extentsV = [];
            for (let i = 0; i < vertRep.count; i++) extentsV.push(vertRep.itemAt(i).height);
            const resV = Magnification.resolve(restV, extentsV, [true, true, true, true, true], restV[2], 80, 1.5, 8);
            applyResult(vertRep, resV);
            wait(250);
            const afterV = liveCenters(vertRep, "y");
            const scalePeakV = vertRep.itemAt(2).targetScale;
            const scaleNeighborV = vertRep.itemAt(1).targetScale;

            console.log("DOCK_MAGNIFY_RUNTIME:" + JSON.stringify({
                growth: growth,
                scalePeak: scalePeak,
                scaleNeighbor: scaleNeighbor,
                scaleFar: scaleFar,
                leftShift: after[0] - rest[0],
                rightShift: after[4] - rest[4],
                peakShift: after[2] - rest[2],
                gapGrowth: (after[4] - after[0]) - (rest[4] - rest[0]),
                restStable: restStable,
                slotShift: slotAfter - slotBefore,
                slotApplied: slotApplied,
                plainScale: plainScale,
                magnifiedScale: magnifiedScale,
                popupWithMagnify: popupWithMagnify,
                popupFloorPreserved: popupFloorPreserved,
                bounceComposition: bounceComposition,
                leftShiftV: afterV[0] - restV[0],
                rightShiftV: afterV[4] - restV[4],
                scalePeakV: scalePeakV,
                scaleNeighborV: scaleNeighborV
            }));
        }
    }

    Timer {
        interval: 300
        running: true
        repeat: false
        onTriggered: {
            // Any exception must still produce the marker + quit, otherwise
            // the probe hangs until the test timeout.
            let payload = null;
            try {
                tc.runTests();
            } catch (err) {
                payload = { probeError: String(err) };
            }
            if (payload) console.log("DOCK_MAGNIFY_RUNTIME:" + JSON.stringify(payload));
            Qt.quit();
        }
    }
}
""")
                proc = subprocess.run(
                    ["quickshell", "-p", probe_path, "--no-duplicate"],
                    cwd=REPO, env=env, capture_output=True, text=True, timeout=20
                )
                combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
                marker = "DOCK_MAGNIFY_RUNTIME:"
                self.assertIn(marker, combined, f"Missing marker in output:\n{combined}")
                payload_line = [line for line in combined.splitlines() if marker in line][-1]
                data = json.loads(payload_line.split(marker, 1)[1].strip())

                # Curve: peak maxed, neighbor raised, far item untouched.
                self.assertAlmostEqual(data["scalePeak"], 1.5, places=2)
                self.assertGreater(data["scaleNeighbor"], 1.05)
                self.assertLess(data["scaleNeighbor"], 1.5)
                self.assertAlmostEqual(data["scaleFar"], 1.0, places=2)
                self.assertGreater(data["growth"], 20)

                # Neighbors physically move apart; the peak stays under the pointer.
                self.assertLess(data["leftShift"], -5)
                self.assertGreater(data["rightShift"], 5)
                self.assertAlmostEqual(data["leftShift"], -data["rightShift"], places=1)
                self.assertLess(abs(data["peakShift"]), 2.0)
                self.assertAlmostEqual(data["gapGrowth"], data["growth"], places=1)

                # Rest-center measurement (mapped minus applied translate) is
                # stable under the applied displacement: no feedback loop.
                self.assertTrue(data["restStable"])

                # Slot (launcher/settings wrapper) displaces laterally too.
                self.assertGreater(data["slotShift"], 20)
                self.assertAlmostEqual(data["slotApplied"], 25, places=1)

                # Single-icon contracts preserved and composable.
                self.assertAlmostEqual(data["plainScale"], 1.0, places=2)
                self.assertAlmostEqual(data["magnifiedScale"], 1.4, places=2)
                self.assertAlmostEqual(data["popupWithMagnify"], 1.4, places=2)
                self.assertAlmostEqual(data["popupFloorPreserved"], 1.15, places=2)
                self.assertAlmostEqual(data["bounceComposition"], 1.29, places=2)

                # Vertical edges: same behavior driven from the y axis.
                self.assertLess(data["leftShiftV"], -5)
                self.assertGreater(data["rightShiftV"], 5)
                self.assertAlmostEqual(data["scalePeakV"], 1.5, places=2)
                self.assertGreater(data["scaleNeighborV"], 1.05)
            finally:
                if os.path.exists(probe_path):
                    os.remove(probe_path)


if __name__ == "__main__":
    unittest.main()
