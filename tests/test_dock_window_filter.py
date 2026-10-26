#!/usr/bin/env python3
"""
P0 #8 Dock window filtering tests.

SAFE: pure JS logic executed under node (vm) + static source contracts.
No quickshell/KWin/qdbus/Wayland is launched (services here call qdbus on the live session,
so a quickshell harness is deliberately NOT used). Physical multi-monitor behavior is NOT covered.
"""
import json, os, re, subprocess, unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(REPO, "services/kwin/WindowFilter.js")


def read(rel):
    with open(os.path.join(REPO, rel)) as f:
        return f.read()


DRIVER = r"""
const vm=require('vm'),fs=require('fs');
const ctxo={};vm.createContext(ctxo);vm.runInContext(fs.readFileSync(process.argv[1],'utf8').replace(/^\.pragma.*$/m,''),ctxo);
const W=ctxo;
const input=JSON.parse(process.argv[2]);
const clean=id=>id.replace(/^\d+_/,'');
const out=input.cases.map(c=>{
  const ctx={mode:c.mode,screenName:c.screen,currentDesktopId:c.desk,states:input.states,cleanId:clean,
    outputOf:id=>{const o=input.outputs[clean(id)];return (o&&input.available.includes(o))?o:""}};
  return W.filterWindows(input.windows,ctx).map(w=>w.id);
});
console.log(JSON.stringify({out,norm:input.norm.map(W.normalizeMode)}));
"""

WINS = [{"id": f"0_{{{n}}}"} for n in ("A", "B", "C", "D", "E", "F")]
# A: d1/DP-1  B: d2/DP-1  C: d1/HDMI  D: all-desktops/HDMI  E: no state, no output  F: d1, output disconnected
STATES = {
    "{A}": {"desktops": ["d1"]}, "{B}": {"desktops": ["d2"]}, "{C}": {"desktops": ["d1"]},
    "{D}": {"onAllDesktops": True, "desktops": []}, "{F}": {"desktops": ["d1"]},
}
OUTPUTS = {"{A}": "DP-1", "{B}": "DP-1", "{C}": "HDMI-A-1", "{D}": "HDMI-A-1", "{F}": "DP-9"}
AVAIL = ["DP-1", "HDMI-A-1"]


def run(cases, windows=WINS, states=STATES, outputs=OUTPUTS, avail=AVAIL, norm=()):
    p = subprocess.run(["node", "-e", DRIVER, JS, json.dumps(dict(
        cases=cases, windows=windows, states=states, outputs=outputs, available=avail, norm=list(norm)))],
        capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    r = json.loads(p.stdout)
    return [[i[2:] for i in o] for o in r["out"]], r["norm"]


def one(mode, screen="", desk="d1", **kw):
    return run([dict(mode=mode, screen=screen, desk=desk)], **kw)[0][0]


class TestFilterLogic(unittest.TestCase):
    def test_all_modes(self):
        self.assertEqual(one("all", "DP-1"), ["{A}", "{B}", "{C}", "{D}", "{E}", "{F}"])
        self.assertEqual(one("desktop", "DP-1"), ["{A}", "{C}", "{D}", "{E}", "{F}"])
        self.assertEqual(one("monitor", "DP-1"), ["{A}", "{B}", "{E}", "{F}"])
        self.assertEqual(one("desktop-and-monitor", "DP-1"), ["{A}", "{E}", "{F}"])

    def test_desktop_change(self):
        self.assertEqual(one("desktop", "", "d2"), ["{B}", "{D}", "{E}"])
        self.assertEqual(one("desktop", "", "d1"), ["{A}", "{C}", "{D}", "{E}", "{F}"])

    def test_two_monitors_differ(self):
        self.assertEqual(one("monitor", "HDMI-A-1"), ["{C}", "{D}", "{E}", "{F}"])
        a, b = one("monitor", "DP-1"), one("monitor", "HDMI-A-1")
        self.assertNotEqual(a, b)

    def test_all_desktops_window_everywhere(self):
        for d in ("d1", "d2", "d3"):
            self.assertIn("{D}", one("desktop", "", d))

    def test_unknown_desktop_metadata_conservative(self):
        self.assertIn("{E}", one("desktop", "", "d2"))  # no state -> included
        self.assertEqual(one("desktop", "", ""), [w["id"][2:] for w in WINS])  # unknown current desktop
        st = dict(STATES); st["{A}"] = {"desktops": []}
        self.assertIn("{A}", one("desktop", "", "d2", states=st))  # stale empty list -> included

    def test_unknown_or_disconnected_monitor(self):
        self.assertIn("{F}", one("monitor", "DP-1"))  # DP-9 not available -> unknown -> included
        self.assertIn("{E}", one("monitor", "HDMI-A-1"))
        self.assertEqual(len(one("monitor", "")), 6)  # screen name unknown
        # reconnect: DP-9 becomes available -> F now belongs to DP-9 only
        self.assertNotIn("{F}", one("monitor", "DP-1", avail=AVAIL + ["DP-9"]))
        self.assertIn("{F}", one("monitor", "DP-9", avail=AVAIL + ["DP-9"]))

    def test_global_collection_untouched(self):
        ws = json.loads(json.dumps(WINS))
        one("desktop-and-monitor", "DP-1", windows=ws)
        self.assertEqual(ws, WINS)

    def test_pinned_zero_visible_semantics(self):
        # all windows of an app elsewhere -> zero visible, but app globally has windows
        wins = [WINS[1]]  # B: d2 / DP-1
        self.assertEqual(one("desktop", "DP-1", "d1", windows=wins), [])
        self.assertEqual(one("all", "DP-1", "d1", windows=wins), ["{B}"])

    def test_normalize_invalid_falls_back(self):
        _, n = run([], norm=["desktop", "bogus", None, 3, "", "monitor", "desktop-and-monitor", "ALL"])
        self.assertEqual(n, ["desktop", "all", "all", "all", "all", "monitor", "desktop-and-monitor", "all"])


class TestWiring(unittest.TestCase):
    def test_config_default_persistence(self):
        c = read("services/config/ConfigService.qml")
        self.assertIn('property string dockWindowFilter: "all"', c)
        self.assertIn('"windowFilter": root.dockWindowFilter', c)
        self.assertIn("WindowFilter.normalizeMode(parsed.windowFilter)", c)
        self.assertIn("if (norm === root.dockWindowFilter) return;", c)  # no redundant writes
        self.assertIn('"monitors": root.dockMonitors', c)  # existing key preserved

    def test_selectors_not_mutating_global(self):
        w = read("services/kwin/WindowService.qml")
        self.assertIn("function getFilteredWindowsForApp", w)
        body = w[w.index("function getFilteredWindowsForApp"):w.index("function getActiveWindowForApp")]
        self.assertNotIn("root.windows =", body)
        self.assertNotIn("root.runningAppIds =", body)
        self.assertEqual(len(re.findall(r"root\.windows = ", w)), 1)  # only parser assigns it

    def test_dock_uses_own_screen_not_visibility_list(self):
        i = read("modules/dock/DockItem.qml")
        self.assertIn("parentWindowRef.modelData.name", i)
        self.assertNotIn("dockMonitors", i)
        d = read("modules/dock/Dock.qml")
        self.assertIn("getFilteredRunningAppIds(ConfigService.dockWindowFilter, dockWindow.modelData", d)

    def test_chooser_menu_wheel_use_filtered(self):
        for f in ("modules/dock/DockMenu.qml", "modules/dock/WindowChooserPopup.qml"):
            self.assertIn("getFilteredWindowsForApp", read(f))
        i = read("modules/dock/DockItem.qml")
        self.assertIn("cycleAppWindows(root.appId, delta < 0, root.filterScreenName)", i)
        self.assertIn("filterScreenName: root.filterScreenName", i)

    def test_no_duplicate_launch_when_running_elsewhere(self):
        i = read("modules/dock/DockItem.qml")
        self.assertIn("root.windowCount === 0 && root.isRunning", i)

    def test_settings_selector(self):
        s = read("modules/settings/SettingsWindow.qml")
        self.assertIn("ConfigService.setDockWindowFilter(wfBtn.modelData.mode)", s)
        self.assertIn("ConfigService.toggleDockMonitor", s)  # monitor settings kept

    def test_no_new_polling(self):
        for f in ("services/kwin/WindowFilter.js",):
            self.assertNotRegex(read(f), r"Timer|Process|execDetached|setInterval|setTimeout")
        w = read("services/kwin/WindowService.qml")
        blk = w[w.index("Dock window filtering"):w.index("function getActiveWindowForApp")]
        self.assertNotRegex(blk, r"Timer|Process|execDetached|qdbus")

    def test_keyboard_nav_sources_unchanged_by_p0_8(self):
        d = subprocess.run(["git", "diff", "--name-only", "cf440ca", "--", "modules/dock/DockKeyboardNav.qml"],
                           cwd=REPO, capture_output=True, text=True).stdout.strip()
        self.assertEqual(d, "")


PICK_DRIVER = r"""
const vm=require('vm'),fs=require('fs');
const c={};vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8').replace(/^\.pragma.*$/m,''),c);
const i=JSON.parse(process.argv[2]);
const clean=x=>String(x||'').replace(/^0_/,'').replace(/[{}]/g,'').toLowerCase();
console.log(JSON.stringify(c.pickActivation(i.filtered,i.global,i.active,clean)));
"""


def pick(filtered, glob, active):
    ids = lambda l: [{"id": f"0_{{{n}}}", "caption": "same title"} for n in l]
    p = subprocess.run(["node", "-e", PICK_DRIVER, JS, json.dumps(dict(
        filtered=ids(filtered), **{"global": ids(glob)}, active=active))], capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


class TestActivationPick(unittest.TestCase):
    """Mocked pure-logic tests (node). Not physical KWin."""

    def test_active_excluded_by_filter_desktop_or_monitor(self):
        # active window "a" is out of filter (desktop or monitor filter yields only b,c)
        r = pick(["b", "c"], ["a", "b", "c"], "a")
        self.assertEqual(r["action"], "chooser")  # never toggles out-of-filter window
        self.assertEqual(r["id"], "")

    def test_multi_visible_no_active_visible(self):
        self.assertEqual(pick(["b", "c"], ["b", "c"], "")["action"], "chooser")

    def test_multi_visible_active_visible_toggles_it(self):
        r = pick(["b", "c"], ["a", "b", "c"], "{c}")
        self.assertEqual((r["action"], r["id"]), ("toggle", "0_{c}"))

    def test_zero_visible_running_activates_global_active(self):
        r = pick([], ["z", "a"], "z")
        self.assertEqual((r["action"], r["id"]), ("activate", "0_{z}"))

    def test_zero_visible_deterministic_fallback_not_toggle(self):
        r = pick([], ["z", "m", "a"], "unrelated")
        self.assertEqual((r["action"], r["id"]), ("activate", "0_{a}"))
        self.assertEqual(pick([], ["m", "a", "z"], "")["id"], "0_{a}")

    def test_zero_global_fails_safe(self):
        self.assertEqual(pick([], [], "x")["action"], "none")

    def test_all_mode_compat(self):
        # all mode: filtered == global
        r = pick(["a", "b"], ["a", "b"], "b")
        self.assertEqual((r["action"], r["id"]), ("toggle", "0_{b}"))

    def test_uuid_not_title(self):
        # all windows share the same title; only UUID decides
        r = pick(["b"], ["a", "b"], "a")
        self.assertEqual(r["action"], "chooser")

    def test_dockitem_wiring(self):
        i = read("modules/dock/DockItem.qml")
        self.assertNotIn("getActiveWindowForApp(root.appId)", i)
        self.assertIn("WindowService.pickActivation(root.appId, root.appWindows)", i)
        self.assertIn("WindowService.activateWindow(pick.id)", i)
        a = i[i.index("function activateItem"):i.index("function toggleContextMenu")]
        zero = a[:a.index("else if (root.windowCount === 0)")]
        self.assertNotIn("ApplicationService.launch", zero)
        self.assertNotIn("toggleWindow", zero)
        self.assertIn("ApplicationService.launch(root.app)", a)  # no-window launch unchanged

    def test_no_input_handler_changes(self):
        import subprocess as sp
        d = sp.run(["git", "diff", "e6f88f5", "--", "modules/dock/DockItem.qml"], capture_output=True, text=True, cwd=REPO).stdout
        for k in ("onWheel", "onPressed", "Keys.", "DragHandler", "onTapped", "onClicked", "contextMenu"):
            self.assertNotIn(k, "\n".join(l for l in d.splitlines() if l[:1] in "+-"))


if __name__ == "__main__":
    unittest.main()
