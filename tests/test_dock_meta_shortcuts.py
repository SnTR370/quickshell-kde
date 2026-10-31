#!/usr/bin/env python3
"""
DOCK-008 Meta+1..9 pinned dock application shortcuts tests.

SAFE: pure JS builder executed under node (vm), shell helper validation and
rendering with a private temp dir, static wiring contracts for the QML
integration, and an isolated KWin rig test (throwaway D-Bus session +
kwin_wayland --virtual, kglobalaccel embedded in KWin 6.8+) verifying that
the resident script really registers Meta+1..9 and that triggering a
shortcut toggles / cycles the matching window. The live Plasma session is
never touched.

Run with: python3 -m unittest tests.test_dock_meta_shortcuts
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(REPO, "services/kwin", "MetaShortcuts.js")
TEMPLATE = os.path.join(REPO, "services/kwin", "scripts", "kwin-meta-shortcuts.js")
HELPER = os.path.join(REPO, "services/kwin", "scripts", "kwin-meta-shortcuts.sh")
WINDOW_SERVICE = os.path.join(REPO, "services/kwin", "WindowService.qml")
CONFIG_SERVICE = os.path.join(REPO, "services/config", "ConfigService.qml")
SETTINGS_WINDOW = os.path.join(REPO, "modules/settings", "SettingsWindow.qml")
QML_BIN = "/usr/lib/qt6/bin/qml" if os.path.exists("/usr/lib/qt6/bin/qml") else shutil.which("qml")

# Qt key codes: Meta = 0x10000000, digit '1'..'9' = 0x31..0x39.
META_1 = 0x10000000 + 0x31


def read(path):
    with open(path) as f:
        return f.read()


DRIVER = r"""
const vm=require('vm'),fs=require('fs');
const ctx={};vm.createContext(ctx);vm.runInContext(fs.readFileSync(process.argv[1],'utf8').replace(/^\.pragma.*$/m,''),ctx);
const M=ctx;
const input=JSON.parse(process.argv[2]);
const out={};
const resolver=function(spec){ if(!spec) return null; return function(id){ return (spec[id]!==undefined)?spec[id]:null; }; };
if (input.entries) out.entries=input.entries.map(c=>M.buildPinnedEntries(c.list, resolver(c.resolveApp)));
if (input.json) out.json=input.json.map(c=>M.buildPinnedJson(c.list, resolver(c.resolveApp)));
if (input.script) out.script=input.script.map(c=>M.buildScriptContent(c.template, c.json));
console.log(JSON.stringify(out));
"""


def run_node(payload):
    p = subprocess.run(["node", "-e", DRIVER, LIB, json.dumps(payload)],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def entries(pinned_list, resolve_app=None):
    return run_node({"entries": [dict(list=pinned_list, resolveApp=resolve_app)]})["entries"][0]


def pinned_json(pinned_list, resolve_app=None):
    return run_node({"json": [dict(list=pinned_list, resolveApp=resolve_app)]})["json"][0]


def script_content(template_text, js):
    return run_node({"script": [dict(template=template_text, json=js)]})["script"][0]


# A realistic ApplicationService app object shape (scan_apps.py output).
FIREFOX_APP = {
    "id": "firefox",
    "startupWMClass": "firefox",
    "execBinary": "firefox",
    "icon": "firefox",
    "aliases": ["firefox", "Firefox", "navigator", "Mozilla Firefox", "firefox-esr"],
}
DOLPHIN_APP = {
    "id": "org.kde.dolphin",
    "startupWMClass": "dolphin",
    "execBinary": "dolphin",
    "icon": "org.kde.dolphin",
    "aliases": ["org.kde.dolphin", "dolphin", "Dosya Yöneticisi"],
}


class TestBuilderPure(unittest.TestCase):
    """Pure pinned-list -> match-key generation (node vm, no QML/KWin)."""

    def test_basic_mapping_and_alias_resolution(self):
        res = entries(["org.kde.dolphin", "firefox"],
                      {"org.kde.dolphin": DOLPHIN_APP, "firefox": FIREFOX_APP})
        self.assertEqual(res[0], ["org.kde.dolphin", "dolphin"])
        self.assertEqual(res[1], ["firefox", "navigator", "firefox-esr"])

    def test_desktop_suffix_and_case_normalized(self):
        res = entries(["Org.KDE.Dolphin.desktop"], {"Org.KDE.Dolphin.desktop": DOLPHIN_APP})
        self.assertEqual(res, [["org.kde.dolphin", "dolphin"]])

    def test_unresolvable_app_falls_back_to_raw_id(self):
        res = entries(["firefox"], {})
        self.assertEqual(res, [["firefox"]])

    def test_unsafe_and_ignored_keys_excluded(self):
        app = dict(FIREFOX_APP, aliases=["firefox", "has space", "slash/key",
                                         "env", "sh", "x", "window-foo", "@@weird",
                                         "application-x-executable", "semi;colon",
                                         "quote\"key", "amp&key", "pipe|key",
                                         "navigator", "firefox-esr"])
        res = entries(["firefox"], {"firefox": app})
        # Only the safe, non-generic keys survive (in stable first-seen order).
        self.assertEqual(res, [["firefox", "navigator", "firefox-esr"]])

    def test_order_stable_and_truncated_at_nine(self):
        pinned = ["app%d" % i for i in range(1, 13)]
        res = entries(pinned)
        self.assertEqual(len(res), 9)
        self.assertEqual([r[0] for r in res], ["app%d" % i for i in range(1, 10)])

    def test_empty_slots_preserved_for_index_alignment(self):
        # Slot 2 has no resolvable keys but must keep its dock position.
        res = entries(["firefox", "un resolvable!", "dolphin"],
                      {"firefox": FIREFOX_APP, "dolphin": DOLPHIN_APP})
        self.assertEqual(len(res), 3)
        self.assertEqual(res[1], [])
        self.assertEqual(res[2], ["dolphin", "org.kde.dolphin"])

    def test_invalid_input(self):
        self.assertEqual(entries(None), [])
        self.assertEqual(entries("firefox"), [])
        self.assertEqual(entries(42), [])

    def test_build_pinned_json_roundtrip(self):
        js = pinned_json(["org.kde.dolphin"], {"org.kde.dolphin": DOLPHIN_APP})
        self.assertEqual(json.loads(js), [["org.kde.dolphin", "dolphin"]])
        self.assertEqual(pinned_json([]), "[]")

    def test_build_script_content_substitution(self):
        tpl = "var PINNED = __PINNED_JSON__;\n// __PINNED_JSON__ stays in comment"
        out = script_content(tpl, '[["firefox"]]')
        self.assertEqual(out, 'var PINNED = [["firefox"]];\n// __PINNED_JSON__ stays in comment')

    def test_build_script_content_missing_placeholder(self):
        self.assertEqual(script_content("var x = 1;", '[["a"]]'), "")

    def test_template_has_exactly_one_placeholder(self):
        self.assertEqual(read(TEMPLATE).count("__PINNED_JSON__"), 1)

    def test_helper_render_matches_reference_builder(self):
        # The sed substitution in kwin-meta-shortcuts.sh must produce exactly
        # what MetaShortcuts.buildScriptContent produces.
        with tempfile.TemporaryDirectory(prefix="qs-meta-test-") as tmp:
            out = os.path.join(tmp, "rendered.js")
            js = pinned_json(["org.kde.dolphin", "firefox"],
                             {"org.kde.dolphin": DOLPHIN_APP, "firefox": FIREFOX_APP})
            p = subprocess.run([HELPER, "render", js, out], capture_output=True, text=True, timeout=30)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(read(out), script_content(read(TEMPLATE), js))


class TestShellHelper(unittest.TestCase):
    """kwin-meta-shortcuts.sh validation and actions (no KWin required)."""

    def run_helper(self, *args):
        return subprocess.run([HELPER] + list(args), capture_output=True, text=True, timeout=30)

    def test_rejects_unsafe_json(self):
        with tempfile.TemporaryDirectory(prefix="qs-meta-test-") as tmp:
            out = os.path.join(tmp, "x.js")
            for bad in ['["has space"]', '["pipe|x"]', '["semi;y"]', '["amp&x"]',
                        '["quote\\"x"]', '["back\\\\slash"]', "['single']", "",
                        '["tab\tx"]', "$(injection)", "'; rm -rf /;"]:
                p = self.run_helper("render", bad, out)
                self.assertNotEqual(p.returncode, 0, "accepted unsafe JSON: %r" % bad)
                self.assertFalse(os.path.exists(out), "wrote output for unsafe JSON: %r" % bad)

    def test_rejects_bad_plugin_name(self):
        for bad in ["bad name", "p|p", "../evil", "$(x)", ";", ""]:
            p = self.run_helper("load", "[[]]", bad)
            self.assertNotEqual(p.returncode, 0, "accepted plugin name: %r" % bad)

    def test_rejects_unknown_action_and_arg_count(self):
        self.assertNotEqual(self.run_helper("bogus").returncode, 0)
        self.assertNotEqual(self.run_helper("render", "[[]]").returncode, 0)
        self.assertNotEqual(self.run_helper().returncode, 0)

    def test_render_accepts_minimal_json(self):
        with tempfile.TemporaryDirectory(prefix="qs-meta-test-") as tmp:
            out = os.path.join(tmp, "ok.js")
            for good in ["[]", "[[]]", '[["a"]]', '[["a.b-c_d"],["e"]]']:
                p = self.run_helper("render", good, out)
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertIn("var PINNED = " + good + ";", read(out))


class TestStaticWiring(unittest.TestCase):
    """Source contracts for the QML integration (no runtime)."""

    def test_window_service_wiring(self):
        src = read(WINDOW_SERVICE)
        self.assertIn('import "MetaShortcuts.js" as MetaShortcuts', src)
        start = src.index("DOCK-008: Meta+1..9")
        end = src.index("function isValidOutputName")
        block = src[start:end]
        # Gated on live KWin session + dock enabled + feature toggle.
        self.assertIn("root.isLiveKWinSession", block)
        self.assertIn("ConfigService.dockEnabled", block)
        self.assertIn("ConfigService.dockMetaShortcuts", block)
        # Debounce timer must never repeat.
        self.assertIn("repeat: false", block)
        # The only repeating timer in this block is the bounded P1-5 health
        # check: slow cadence, gated on the feature being enabled AND a
        # successful load, and it only reads KWin state (never mutates).
        self.assertEqual(block.count("repeat: true"), 1)
        self.assertIn("id: metaShortcutsHealthTimer", block)
        self.assertIn("running: root.metaShortcutsEnabled && root.metaShortcutsLoadedJson !== \"\"",
                      block)
        self.assertIn("interval: 5000", block)
        # Health check decision: only a definitive KWin answer ("not loaded",
        # exit 0) resyncs; unreachable KWin is ignored (no retry loop).
        self.assertIn('buf.trim().indexOf("false") !== -1', block)
        # Argument arrays only, never sh -c string commands.
        self.assertIn('metaShortcutsProc.command = [scriptPath, "load", target', block)
        self.assertIn('metaShortcutsProc.command = [scriptPath, "unload",', block)
        self.assertNotIn('"sh"', block)
        self.assertNotIn("sh -c", block)
        # Script content generated from the pinned list through the pure builder.
        self.assertIn("MetaShortcuts.buildPinnedJson", block)
        # Bounded retry chain, never unbounded.
        self.assertIn("metaShortcutsFailedLoads < 3", block)
        # Shutdown: owned script must be unloaded.
        self.assertIn("Component.onDestruction", src)
        self.assertIn('Quickshell.execDetached([scriptPath, "unload", root.metaShortcutsPluginName])', src)

    def test_window_service_no_new_polling_timers(self):
        src = read(WINDOW_SERVICE)
        # Exactly three repeating timers may exist, each justified:
        # syncTimer (1 s KWin fallback sync), bridgeScannerTimer (5 s
        # safety net while the event bridge is active, P1-2) and
        # metaShortcutsHealthTimer (5 s gated KWin-restart survival check,
        # P1-5). No other repeating timer may be added.
        self.assertEqual(src.count("repeat: true"), 3)
        for timer_id in ("id: syncTimer", "id: bridgeScannerTimer",
                         "id: metaShortcutsHealthTimer"):
            self.assertIn(timer_id, src)

    def test_config_service_knob(self):
        src = read(CONFIG_SERVICE)
        # Opt-in default, load clamp, save, setter (mark modified) conventions.
        self.assertIn("property bool dockMetaShortcuts: false", src)
        self.assertIn('if (typeof parsed.metaShortcuts === "boolean" && !mod["metaShortcuts"])', src)
        self.assertIn('"metaShortcuts": root.dockMetaShortcuts', src)
        self.assertIn('_markDockModified("metaShortcuts")', src)
        self.assertIn("function setDockMetaShortcuts(on)", src)

    def test_settings_toggle(self):
        src = read(SETTINGS_WINDOW)
        self.assertIn("ConfigService.setDockMetaShortcuts(!ConfigService.dockMetaShortcuts)", src)
        self.assertIn("ConfigService.dockMetaShortcuts ?", src)

    def test_kwin_script_template_contracts(self):
        tpl = read(TEMPLATE)
        self.assertIn("registerShortcut(", tpl)
        self.assertIn('"Meta+" + (idx + 1)', tpl)
        # At most 9 shortcuts, one per dock slot.
        self.assertIn("Math.min(9, PINNED.length)", tpl)
        # Native window matching only; no timers, no D-Bus, no file access.
        self.assertNotIn("setInterval", tpl)
        self.assertNotIn("callDBus", tpl)
        self.assertNotIn("registerScreenEdge", tpl)
        # Stable, namespaced shortcut ids.
        self.assertIn('"quickshell-dock-meta-"', tpl)

    def test_helper_script_contracts(self):
        h = read(HELPER)
        self.assertIn("loadScript", h)
        self.assertIn("unloadScript", h)
        # Orphan cleanup before load, mirroring the event bridge.
        self.assertIn("org.kde.kwin.Scripting.unloadScript", h)
        self.assertIn("tr -d", h)
        self.assertNotIn("eval", h)


# ---------------------------------------------------------------------------
# Isolated KWin rig test (throwaway D-Bus session + kwin_wayland --virtual).
# KWin 6.8+ embeds the kglobalaccel daemon, so registerShortcut works and the
# org.kde.kglobalaccel Component interface can both list and invoke the
# registered shortcuts without touching the live session.
# ---------------------------------------------------------------------------

WIN_QML = """import QtQuick
import QtQuick.Window
Window {
    width: 400; height: 300; visible: true; title: "%s"
    Timer { interval: 60000; running: true; onTriggered: Qt.exit(0) }
}
"""

QUERY_JS = ("var ws = workspace.windowList(); var out = []; "
            "for (var i = 0; i < ws.length; i++) { var w = ws[i]; "
            "out.push({c: String(w.caption || ''), rc: String(w.resourceClass || ''), "
            "m: !!w.minimized, a: !!w.active, n: !!w.normalWindow}); } "
            "output_result(JSON.stringify(out));")


def wait_for(predicate, timeout_s, what):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.2)
    raise AssertionError("timed out waiting for " + what)


def run_inner(testroot):
    """Rig phases inside the dbus-run-session. Raises on any failure."""
    logs = os.path.join(testroot, "logs")
    scripts = os.path.join(testroot, "scripts")
    runtime = os.path.join(testroot, "runtime")
    config = os.path.join(testroot, "config")
    for d in (logs, scripts, config):
        os.makedirs(d, exist_ok=True)
    os.makedirs(runtime, exist_ok=True)
    os.chmod(runtime, 0o700)

    plugin = "quickshell-rig-meta"
    # Slot 1 matches the qml test windows (resourceClass org.qt-project.qml);
    # slot 2 matches nothing.
    js = pinned_json(["org.qt-project.qml", "no-such-app-xyz"])

    def run(cmd, **kw):
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60, **kw)

    def qdbus(*args):
        return run(["qdbus6"] + list(args))

    def is_loaded():
        r = qdbus("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.isScriptLoaded", plugin)
        return "true" in r.stdout.lower()

    def kwin_state():
        r = run(["kdotool", "kwinscript", "--inline", QUERY_JS])
        try:
            wins = json.loads(r.stdout.strip())
        except ValueError:
            return []
        return [w for w in wins if w.get("n")]

    def invoke(name):
        r = qdbus("org.kde.kglobalaccel", "/component/kwin",
                  "org.kde.kglobalaccel.Component.invokeShortcut", name)
        assert r.returncode == 0, "invokeShortcut(%s) failed: %s%s" % (name, r.stdout, r.stderr)

    kwin = subprocess.Popen(
        ["kwin_wayland", "--virtual", "--width", "1280", "--height", "800",
         "--no-lockscreen", "--no-kactivities", "--socket", "kwine2e"],
        stdout=open(os.path.join(logs, "kwin.log"), "w"),
        stderr=subprocess.STDOUT, env=os.environ)
    wins = []
    try:
        socket = os.path.join(runtime, "kwine2e")
        wait_for(lambda: os.path.exists(socket), 15, "kwin wayland socket")
        os.environ["WAYLAND_DISPLAY"] = "kwine2e"
        # Export WAYLAND_DISPLAY into the D-Bus activation environment (what
        # startplasma does): otherwise the qml test clients trigger an
        # xdg-desktop-portal backend crash-retry storm that starves kdotool.
        run(["dbus-update-activation-environment", "WAYLAND_DISPLAY=kwine2e"])
        wait_for(lambda: qdbus("org.kde.KWin", "/KWin", "org.kde.KWin.activeOutputName").returncode == 0,
                 30, "kwin D-Bus availability")
        print("RIG-STEP kwin-up")

        # --- load the resident script through the real helper ---
        p = run([HELPER, "load", js, plugin])
        assert p.returncode == 0, "helper load failed: %s%s" % (p.stdout, p.stderr)
        wait_for(is_loaded, 10, "meta shortcuts script loaded")
        print("RIG-STEP script-loaded")

        # --- Meta+1..N registered in the kwin component of kglobalaccel ---
        names = qdbus("org.kde.kglobalaccel", "/component/kwin",
                      "org.kde.kglobalaccel.Component.shortcutNames").stdout
        assert "quickshell-dock-meta-1" in names, "meta-1 not registered:\n" + names
        assert "quickshell-dock-meta-2" in names, "meta-2 not registered:\n" + names
        assert "quickshell-dock-meta-3" not in names, "shortcut registered beyond pinned slots"
        infos = qdbus("--literal", "org.kde.kglobalaccel", "/component/kwin",
                      "org.kde.kglobalaccel.Component.allShortcutInfos").stdout
        assert "quickshell-dock-meta-1" in infos and str(META_1) in infos, \
            "meta-1 not bound to Meta+1:\n" + infos[:2000]
        print("RIG-STEP shortcuts-registered")

        # --- two matching windows ---
        for name in ("meta-rig-a", "meta-rig-b"):
            path = os.path.join(scripts, name + ".qml")
            with open(path, "w") as f:
                f.write(WIN_QML % name)
            wins.append(subprocess.Popen(
                [QML_BIN, "-platform", "wayland", path],
                stdout=open(os.path.join(logs, name + ".log"), "w"),
                stderr=subprocess.STDOUT, env=os.environ))
        wait_for(lambda: len([w for w in kwin_state() if w["c"] in ("meta-rig-a", "meta-rig-b")]) == 2,
                 20, "both test windows mapped")
        print("RIG-STEP windows-up")

        def by_title():
            return {w["c"]: w for w in kwin_state() if w["c"] in ("meta-rig-a", "meta-rig-b")}

        def activate_and_wait(title, timeout_s=20):
            # kdotool can transiently fail while the qml test clients trigger
            # the xdg-desktop-portal D-Bus activation storm, so retry.
            deadline = time.monotonic() + timeout_s
            while time.monotonic() < deadline:
                if by_title().get(title, {}).get("a") is True:
                    return
                r = run(["kdotool", "search", "--name", title])
                lines = [l.strip() for l in r.stdout.strip().splitlines() if l.strip()]
                if lines:
                    run(["kdotool", "windowactivate", lines[0]])
                time.sleep(0.4)
            raise AssertionError("timed out waiting for " + title + " active")

        # 1) Active matching window is minimized (click "toggle" semantics).
        activate_and_wait("meta-rig-a")
        invoke("quickshell-dock-meta-1")
        wait_for(lambda: by_title().get("meta-rig-a", {}).get("m") is True, 10, "window A minimized")
        st = by_title()
        assert not st["meta-rig-a"]["a"], "minimized window still active"
        print("RIG-STEP toggle-minimize")

        # 2) Clear focus (KWin auto-activates the next window after a
        #    minimize), then a fresh cycle must activate exactly one window.
        for _ in range(4):
            if not any(w["a"] for w in by_title().values()):
                break
            invoke("quickshell-dock-meta-1")
            time.sleep(0.4)
        wait_for(lambda: not any(w["a"] for w in by_title().values()), 5,
                 "no matching window active after toggles")
        invoke("quickshell-dock-meta-1")
        wait_for(lambda: any(w["a"] and not w["m"] for w in by_title().values()), 10,
                 "cycle activated a window")
        first = [t for t, w in by_title().items() if w["a"]]
        assert len(first) == 1, "expected exactly one active window, got " + str(first)
        first = first[0]
        print("RIG-STEP cycle-activated " + first)

        # 3) Active -> minimized; after clearing auto-activation again, the
        #    next invoke must CYCLE to the other window (script-internal
        #    lastActivated state, not KWin focus order).
        invoke("quickshell-dock-meta-1")
        wait_for(lambda: by_title().get(first, {}).get("m") is True, 10, "cycled window minimized")
        for _ in range(4):
            if not any(w["a"] for w in by_title().values()):
                break
            invoke("quickshell-dock-meta-1")
            time.sleep(0.4)
        wait_for(lambda: not any(w["a"] for w in by_title().values()), 5,
                 "no matching window active after second toggle")
        invoke("quickshell-dock-meta-1")
        other = "meta-rig-b" if first == "meta-rig-a" else "meta-rig-a"
        wait_for(lambda: by_title().get(other, {}).get("a") is True, 10,
                 "cycle moved to the other window (" + other + ")")
        print("RIG-STEP cycle-moved")

        # 4) Slot with no matching app is a no-op.
        before = json.dumps(by_title(), sort_keys=True)
        invoke("quickshell-dock-meta-2")
        time.sleep(0.6)
        assert json.dumps(by_title(), sort_keys=True) == before, \
            "shortcut for unmatched pinned app changed window state"
        print("RIG-STEP unmatched-noop")

        # 5) Reload (orphan cleanup path).
        p = run([HELPER, "load", js, plugin])
        assert p.returncode == 0, "helper reload failed: %s%s" % (p.stdout, p.stderr)
        wait_for(is_loaded, 10, "script reloaded")
        print("RIG-STEP reloaded")

        # 6) P1-5: KWin restart survival. KWin drops transiently loaded
        #    scripts on restart; the shell's health check
        #    (WindowService.metaShortcutsHealthTimer) reacts by re-running
        #    the exact helper load below, restoring Meta+1..9.
        kwin.kill()
        kwin.wait(timeout=15)
        for w in wins:
            try:
                w.wait(timeout=10)
            except Exception:
                w.kill()
        print("RIG-STEP kwin-killed")
        kwin = subprocess.Popen(
            ["kwin_wayland", "--virtual", "--width", "1280", "--height", "800",
             "--no-lockscreen", "--no-kactivities", "--socket", "kwine2e2"],
            stdout=open(os.path.join(logs, "kwin2.log"), "w"),
            stderr=subprocess.STDOUT, env=os.environ)
        socket2 = os.path.join(runtime, "kwine2e2")
        wait_for(lambda: os.path.exists(socket2), 15, "second kwin wayland socket")
        os.environ["WAYLAND_DISPLAY"] = "kwine2e2"
        run(["dbus-update-activation-environment", "WAYLAND_DISPLAY=kwine2e2"])
        wait_for(lambda: qdbus("org.kde.KWin", "/KWin", "org.kde.KWin.activeOutputName").returncode == 0,
                 30, "second kwin D-Bus availability")
        # Platform behavior, verified: the transient script did NOT survive.
        r = qdbus("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.isScriptLoaded", plugin)
        assert r.returncode == 0 and "false" in r.stdout.lower(), \
            "isScriptLoaded must answer false after KWin restart: %s%s" % (r.stdout, r.stderr)
        print("RIG-STEP script-gone-after-restart")
        # Resync exactly as the WindowService health check triggers it.
        p = run([HELPER, "load", js, plugin])
        assert p.returncode == 0, "helper resync load failed: %s%s" % (p.stdout, p.stderr)
        wait_for(is_loaded, 10, "script restored after resync")
        print("RIG-STEP script-restored")
        # The shortcut is functional again on the new KWin.
        fresh_path = os.path.join(scripts, "meta-rig-fresh.qml")
        with open(fresh_path, "w") as f:
            f.write(WIN_QML % "meta-rig-fresh")
        fresh = subprocess.Popen(
            [QML_BIN, "-platform", "wayland", fresh_path],
            stdout=open(os.path.join(logs, "meta-rig-fresh.log"), "w"),
            stderr=subprocess.STDOUT, env=os.environ)
        wins.append(fresh)
        wait_for(lambda: any(w.get("c") == "meta-rig-fresh" for w in kwin_state()),
                 20, "fresh window mapped on second kwin")

        def fresh_state():
            for w in kwin_state():
                if w.get("c") == "meta-rig-fresh":
                    return w
            return {}

        invoke("quickshell-dock-meta-1")
        # The fresh window is usually already active on the new KWin, so the
        # first invoke may exercise the toggle (minimize) path; either
        # outcome proves the reloaded script handles the shortcut.
        wait_for(lambda: fresh_state().get("a") is True or fresh_state().get("m") is True,
                 10, "shortcut reacted after restart")
        if fresh_state().get("m"):
            invoke("quickshell-dock-meta-1")
        wait_for(lambda: fresh_state().get("a") is True and not fresh_state().get("m"),
                 10, "shortcut activates fresh window after restart")
        print("RIG-STEP shortcut-alive-after-restart")

        # 7) Clean unload.
        p = run([HELPER, "unload", plugin])
        assert p.returncode == 0, "helper unload failed: %s%s" % (p.stdout, p.stderr)
        wait_for(lambda: not is_loaded(), 10, "script unloaded")
        print("RIG-STEP unloaded")
    finally:
        for w in wins:
            if w.poll() is None:
                w.kill()
        if kwin.poll() is None:
            kwin.kill()
        try:
            subprocess.run(["pkill", "-P", str(kwin.pid)], timeout=10)
        except Exception:
            pass
        kwin.wait(timeout=15)


class TestKWinRigIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        missing = [t for t in ("kwin_wayland", "dbus-run-session", "qdbus6", "kdotool", "node")
                   if shutil.which(t) is None]
        if QML_BIN is None:
            missing.append("qml")
        if missing:
            raise unittest.SkipTest("missing required tools: " + ", ".join(missing))
        cls.testroot = tempfile.mkdtemp(prefix="qs-meta-e2e-")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "testroot"):
            shutil.rmtree(cls.testroot, ignore_errors=True)

    def test_meta_shortcuts_register_and_activate(self):
        env = dict(
            os.environ,
            XDG_RUNTIME_DIR=os.path.join(self.testroot, "runtime"),
            XDG_CONFIG_HOME=os.path.join(self.testroot, "config"),
            XDG_CURRENT_DESKTOP="KDE",
            KDE_FULL_SESSION="true",
            QT_QPA_PLATFORM="wayland",
        )
        env.pop("JOURNAL_STREAM", None)
        env.pop("INVOCATION_ID", None)
        os.makedirs(env["XDG_RUNTIME_DIR"], mode=0o700, exist_ok=True)

        proc = subprocess.run(
            ["dbus-run-session", "--", sys.executable, os.path.abspath(__file__),
             "--inner", self.testroot],
            env=env, capture_output=True, text=True, timeout=300)
        out = proc.stdout + proc.stderr
        self.assertIn("PY-RIG-PASS", out,
                      "isolated Meta+1..9 rig test failed (rc=%d):\n%s" % (proc.returncode, out[-4000:]))
        self.assertNotIn("PY-RIG-FAIL", out)
        self.assertEqual(proc.returncode, 0)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--inner":
        try:
            run_inner(sys.argv[2])
        except Exception as e:  # noqa: BLE001 - report and fail the outer test
            print("PY-RIG-FAIL: %s" % e)
            sys.exit(1)
        print("PY-RIG-PASS")
        sys.exit(0)
    # Drop argv so `python3 tests/test_dock_meta_shortcuts.py` runs unittest.
    sys.argv = [sys.argv[0]]
    unittest.main()
