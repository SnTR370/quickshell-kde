#!/usr/bin/env python3
"""
DOCK-011 folder and application stack tests.

SAFE: pure stack helpers executed under node (vm), Meta+1..9 interaction
(stack markers never consume a shortcut slot), static wiring contracts for
the QML integration, qmllint of the touched files, and an isolated headless
runtime E2E (private XDG dirs + private D-Bus session, offscreen quickshell)
covering: seeded config load with sanitization (invalid stacks dropped,
dangling pinned markers removed, app-id dedupe), the full mutation API
(add/remove stack, add/remove member app, rename, path change), persistence
on disk and a fresh-process reload. The live Plasma session is never
touched; folder stacks never read the filesystem in config code.

Run with: python3 -m unittest tests.test_dock_stacks
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STACKS_JS = os.path.join(REPO, "services/config/DockStacks.js")
META_JS = os.path.join(REPO, "services/kwin/MetaShortcuts.js")
CONFIG_SERVICE = os.path.join(REPO, "services/config/ConfigService.qml")
APP_SERVICE = os.path.join(REPO, "services/applications/ApplicationService.qml")
DOCK_QML = os.path.join(REPO, "modules/dock/Dock.qml")
DOCK_ITEM_QML = os.path.join(REPO, "modules/dock/DockItem.qml")
DOCK_QMLDIR = os.path.join(REPO, "modules/dock/qmldir")
SETTINGS_WINDOW = os.path.join(REPO, "modules/settings/SettingsWindow.qml")
STACK_POPUP = os.path.join(REPO, "modules/dock/StackPopup.qml")
STACK_MENU = os.path.join(REPO, "modules/dock/StackMenu.qml")


def read(path):
    with open(path) as f:
        return f.read()


# Mirrors ConfigService.normalizeDockAppId (kept in sync by
# test_config_service_normalizer_contract below).
def _driver_normalizer():
    return (
        "const normalizeId=function(id){"
        "if(!id||typeof id!=='string')return '';"
        "const norm=id.trim().replace(/\\.desktop$/i,'');"
        "if(norm.length<=1||!/^[a-zA-Z0-9._-]+$/.test(norm))return '';"
        "const lower=norm.toLowerCase();"
        "if(['env','sh','bash','flatpak','snap','xdg-open','gio','gtk-launch',"
        "'electron','application-x-executable'].indexOf(lower)!==-1"
        "||lower.indexOf('window-')===0)return '';"
        "return norm;};\n"
    )


DRIVER = (
    "const vm=require('vm'),fs=require('fs');\n"
    "const ctx={};vm.createContext(ctx);vm.runInContext("
    "fs.readFileSync(process.argv[1],'utf8').replace(/^\\.pragma.*$/m,''),ctx);\n"
    "const D=ctx;\n"
    + _driver_normalizer() +
    "const input=JSON.parse(process.argv[2]);\n"
    "const out={};\n"
    # QVariant-marshalled sequence: array-like, Array.isArray() === false.
    "if(input.op==='toArraySeq'){"
    "const seq={length:2};seq[0]='a';seq[1]='b';"
    "out.seq=D.toArray(seq);out.isArray=Array.isArray(out.seq);}\n"
    "else if(input.op==='ids'){"
    "out.isId=input.cases.map(c=>D.isValidStackId(c));"
    "out.isEntry=input.cases.map(c=>D.isStackEntry(c));"
    "out.idFrom=input.cases.map(c=>D.stackIdFromEntry(c));"
    "out.entryFor=D.entryForStackId(input.entryFor);"
    "out.next=D.nextStackId(input.existing.map(s=>({id:s})));\n"
    "if(input.dedupe)out.dedupe=D.nextStackId(input.dedupe.map(s=>({id:s})));\n"
    "if(input.gap)out.gap=D.nextStackId(input.gap.map(s=>({id:s})));\n"
    "}\n"
    "else if(input.op==='title'){"
    "out.titles=input.cases.map(c=>D.sanitizeTitle(c.value,c.fallback));}\n"
    "else if(input.op==='path'){"
    "out.paths=input.cases.map(c=>D.sanitizePath(c));}\n"
    "else if(input.op==='appids'){"
    "out.appIds=D.sanitizeStackAppIds(input.list,normalizeId);"
    "out.noFn=D.sanitizeStackAppIds(input.list,null);\n"
    "out.cap=D.sanitizeStackAppIds(input.capList,normalizeId);\n"
    "}\n"
    "else if(input.op==='sanitize'){"
    "out.stacks=D.sanitizeStacks(input.list,normalizeId);}\n"
    "else if(input.op==='find'){"
    "out.found=D.findStack(input.stacks,input.id);\n"
    "out.bad=D.findStack(input.stacks,input.bad);\n"
    "}\n"
    "else if(input.op==='entries'){"
    "out.entries=D.buildDockEntries(input.pinned,input.stacks,"
    "function(id){const m=input.resolveApp||{};"
    "return (m[id]!==undefined)?m[id]:null;});\n"
    "}\n"
    "else if(input.op==='icon'){"
    "out.icons=[D.stackIcon(null),D.stackIcon({type:'folder'}),"
    "D.stackIcon({type:'apps'}),D.stackIcon({type:'apps',icon:'x-y'}),"
    "D.stackIcon({type:'apps',icon:''})];\n"
    "}\n"
    "console.log(JSON.stringify(out));\n"
)


def run_node(payload, lib=STACKS_JS):
    p = subprocess.run(["node", "-e", DRIVER, lib, json.dumps(payload)],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


# Realistic ApplicationService app object shape (scan_apps.py output).
FIREFOX_APP = {"id": "firefox", "startupWMClass": "firefox", "icon": "firefox",
               "name": "Firefox"}
DOLPHIN_APP = {"id": "org.kde.dolphin", "startupWMClass": "dolphin",
               "icon": "org.kde.dolphin", "name": "Dolphin"}
CODE_APP = {"id": "code", "startupWMClass": "code", "icon": "code",
            "name": "Code"}

SEED_STACKS = [
    {"id": "seed-folder", "type": "folder", "title": "Tmp Folder", "path": "/tmp"},
    # "Firefox" is a case-insensitive duplicate of "firefox" -> dropped.
    {"id": "seed-apps", "type": "apps", "title": "Browsers",
     "appIds": ["firefox", "Firefox", "org.kde.konsole", "sh", "has space"]},
    # Invalid: unknown type.
    {"id": "seed-bad1", "type": "bogus", "title": "Bad Type"},
    # Invalid: folder without a usable path.
    {"id": "seed-bad2", "type": "folder", "title": "No Path", "path": "relative/path"},
    # Invalid: bad id.
    {"id": "Bad Id!", "type": "apps", "title": "Bad Id"},
    # Invalid: traversal path.
    {"id": "seed-bad3", "type": "folder", "title": "Traversal", "path": "/tmp/../etc"},
]


class TestStackHelpersPure(unittest.TestCase):
    """Pure DockStacks.js helpers under node (no QML/KWin/filesystem)."""

    def test_toarray_handles_qvariant_sequences(self):
        """Qt marshals signal-hopped arrays as sequence objects (Array.isArray false)."""
        r = run_node({"op": "toArraySeq"})
        self.assertEqual(r["seq"], ["a", "b"])
        self.assertTrue(r["isArray"])
        self.assertEqual(run_node({"op": "toArraySeq"})["seq"], ["a", "b"])

    def test_id_and_entry_helpers(self):
        cases = ["st1", "stack:st1", "stack:", "stack:Bad Id", "plain-app",
                 "stack:st42", "a", "stack:st1 ", "stackx:1", "stack:st1.extra-x_9"]
        r = run_node({"op": "ids", "cases": cases, "existing": [],
                      "entryFor": "st7"})
        is_id = r["isId"]
        # "plain-app" matches the id pattern (it is just not a stack entry);
        # "stack:st1.extra-x_9" contains ':' so it is not a bare id, but IS
        # a valid stack entry pointing at id "st1.extra-x_9".
        self.assertEqual(is_id, [True, False, False, False, True, False,
                                 True, False, False, False])
        is_entry = r["isEntry"]
        self.assertEqual(is_entry, [False, True, False, False, False,
                                    True, False, False, False, True])
        self.assertEqual(r["idFrom"],
                         ["", "st1", "", "", "", "st42", "", "", "", "st1.extra-x_9"])
        self.assertEqual(r["entryFor"], "stack:st7")
        self.assertEqual(r["next"], "st1")

    def test_next_stack_id_finds_gap(self):
        r = run_node({"op": "ids", "cases": [], "existing": [],
                      "dedupe": ["st1", "st2", "st3"], "entryFor": ""})
        self.assertEqual(r["dedupe"], "st4")
        r = run_node({"op": "ids", "cases": [], "existing": [],
                      "gap": ["st1", "st3"], "entryFor": ""})
        self.assertEqual(r["gap"], "st2")

    def test_sanitize_title(self):
        r = run_node({"op": "title", "cases": [
            {"value": "  My Stack  ", "fallback": ""},
            {"value": "", "fallback": "Folder"},
            {"value": "   ", "fallback": "   "},
            {"value": "x" * 80, "fallback": ""},
        ]})
        self.assertEqual(r["titles"][0], "My Stack")
        self.assertEqual(r["titles"][1], "Folder")
        self.assertEqual(r["titles"][2], "")
        self.assertEqual(len(r["titles"][3]), 64)

    def test_sanitize_path(self):
        r = run_node({"op": "path", "cases": [
            "/tmp", "relative/path", "", "/tmp/../etc", "/tmp//x///y",
            "/tmp\ninject", "/tmp\rcrlf", "/", "//", "x" * 5000,
            "/home/user/Downloads",
        ]})
        self.assertEqual(r["paths"], [
            "/tmp", "", "", "", "/tmp/x/y", "", "", "/", "/", "",
            "/home/user/Downloads",
        ])

    def test_sanitize_app_ids(self):
        r = run_node({"op": "appids",
                      "list": ["firefox", "Firefox", " sh ", "org.kde.konsole.desktop",
                               "has space", "", "code"],
                      "capList": ["app%02d" % i for i in range(40)]})
        self.assertEqual(r["appIds"], ["firefox", "org.kde.konsole", "code"])
        self.assertEqual(r["noFn"], [])
        self.assertEqual(len(r["cap"]), 24)

    def test_sanitize_stacks_drops_invalid_and_keeps_first_duplicate(self):
        r = run_node({"op": "sanitize", "list": SEED_STACKS + [
            # Duplicate id: the first occurrence (folder) wins.
            {"id": "seed-folder", "type": "apps", "title": "Dup", "appIds": ["code"]},
        ]})
        self.assertEqual(len(r["stacks"]), 2)
        folder = r["stacks"][0]
        self.assertEqual(folder["id"], "seed-folder")
        self.assertEqual(folder["type"], "folder")
        self.assertEqual(folder["path"], "/tmp")
        # Folder stacks carry an (always empty) appIds array by design: one
        # uniform stack object shape.
        self.assertEqual(folder["appIds"], [])
        apps = r["stacks"][1]
        self.assertEqual(apps["id"], "seed-apps")
        self.assertEqual(apps["appIds"], ["firefox", "org.kde.konsole"])

    def test_sanitize_stacks_strips_and_caps_icon(self):
        r = run_node({"op": "sanitize", "list": [
            {"id": "st1", "type": "apps", "title": "S", "icon": "  folder-git  ",
             "appIds": []},
            {"id": "st2", "type": "apps", "title": "S", "icon": "x" * 200,
             "appIds": []},
        ]})
        self.assertEqual(r["stacks"][0]["icon"], "folder-git")
        self.assertNotIn("icon", r["stacks"][1])

    def test_find_stack(self):
        stacks = [{"id": "st1", "type": "apps", "title": "S", "appIds": []}]
        r = run_node({"op": "find", "stacks": stacks, "id": "st1", "bad": "st2"})
        self.assertEqual(r["found"]["id"], "st1")
        self.assertIsNone(r["bad"])

    def test_build_dock_entries_order_and_filtering(self):
        stacks = [
            {"id": "stf", "type": "folder", "title": "F", "path": "/tmp"},
            {"id": "sta", "type": "apps", "title": "A", "appIds": ["firefox"]},
        ]
        pinned = ["org.kde.dolphin", "stack:stf", "firefox",
                  "stack:ghost", "stack:sta", "unresolvable!", "code",
                  "Firefox.desktop"]
        r = run_node({"op": "entries", "pinned": pinned, "stacks": stacks,
                      "resolveApp": {"org.kde.dolphin": DOLPHIN_APP,
                                     "firefox": FIREFOX_APP,
                                     "Firefox.desktop": FIREFOX_APP,
                                     "code": CODE_APP}})
        entries = r["entries"]
        # Order preserved; dangling markers and unresolvable apps dropped;
        # canonical-duplicate apps deduped (first wins, raw id preserved).
        self.assertEqual([(e["kind"], e.get("appId", e.get("stack", {}).get("id")))
                          for e in entries],
                         [("app", "org.kde.dolphin"), ("stack", "stf"),
                          ("app", "firefox"), ("stack", "sta"), ("app", "code")])
        by_kind = {}
        for e in entries:
            by_kind.setdefault(e["kind"], []).append(e)
        # App entries keep the RAW pinned id (resolvePinnedKey compatibility).
        self.assertEqual(by_kind["app"][1]["key"], "firefox")
        # Stack entries carry the live stack object.
        self.assertEqual(by_kind["stack"][0]["stack"]["path"], "/tmp")
        self.assertEqual(by_kind["stack"][1]["stack"]["appIds"], ["firefox"])

    def test_stack_icon_fallbacks(self):
        r = run_node({"op": "icon"})
        self.assertEqual(r["icons"], ["application-x-executable", "folder",
                                      "applications-all", "x-y", "applications-all"])


class TestMetaShortcutsStackInteraction(unittest.TestCase):
    """Stack markers never consume a Meta+N slot (apps keep dock positions)."""

    META_DRIVER = (
        "const vm=require('vm'),fs=require('fs');\n"
        "const ctx={};vm.createContext(ctx);vm.runInContext("
        "fs.readFileSync(process.argv[1],'utf8').replace(/^\\.pragma.*$/m,''),ctx);\n"
        "const M=ctx;\n"
        "const input=JSON.parse(process.argv[2]);\n"
        "const resolver=function(spec){if(!spec)return function(){return null;};"
        "return function(id){return (spec[id]!==undefined)?spec[id]:null;};};\n"
        "console.log(JSON.stringify({entries:M.buildPinnedEntries("
        "input.list,resolver(input.resolveApp))}));\n"
    )

    def test_stack_markers_are_skipped(self):
        p = subprocess.run(
            ["node", "-e", self.META_DRIVER, META_JS,
             json.dumps({"list": ["org.kde.dolphin", "stack:st1", "firefox",
                                  "stack:st2", "code"],
                         "resolveApp": {"org.kde.dolphin": DOLPHIN_APP,
                                        "firefox": FIREFOX_APP}})],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        entries = json.loads(p.stdout)["entries"]
        # Three apps in three slots; stacks did not consume indices.
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0], ["org.kde.dolphin", "dolphin"])
        self.assertEqual(entries[1], ["firefox"])
        self.assertEqual(entries[2], ["code"])


class TestStaticContracts(unittest.TestCase):
    """Source contracts for the QML integration (no runtime)."""

    def test_dock_item_stack_bindings_null_safe(self):
        """Every DockItem (stack or plain app) evaluates the member-count
        Badge's count binding: it must not dereference root.stack when the
        item is not a stack (TypeError warning spam otherwise)."""
        src = read(os.path.join(REPO, "modules/dock/DockItem.qml"))
        self.assertIn(
            "count: (root.stack && root.stack.appIds) ? root.stack.appIds.length : 0", src)

    def test_config_service_stack_api(self):
        src = read(CONFIG_SERVICE)
        self.assertIn('import "DockStacks.js" as DockStacks', src)
        self.assertIn("property var dockStacks: []", src)
        for fn in ("function getDockStack(",
                   "function isDockStackEntry(",
                   "function addDockStack(",
                   "function removeDockStack(",
                   "function renameDockStack(",
                   "function setDockStackPath(",
                   "function addAppToDockStack(",
                   "function removeAppFromDockStack("):
            self.assertIn(fn, src, fn)
        # Load: stacks are sanitized with the real normalizer and assigned
        # BEFORE the pinned list (dangling markers must be droppable).
        stacks_line = src.index("root.dockStacks = DockStacks.sanitizeStacks(parsed.stacks, root.normalizeDockAppId);")
        pinned_line = src.index("root.dockPinned = root.sanitizeDockPinned(")
        self.assertLess(stacks_line, pinned_line)
        # Save: stacks are persisted alongside the pinned row.
        self.assertIn('"stacks": root.dockStacks', src)
        # sanitizeDockPinned keeps stack markers only while the stack exists.
        self.assertIn("if (DockStacks.isStackEntry(raw)) {", src)
        # Every mutation reassigns the whole array (QVariant-signal gotcha).
        self.assertIn("root.dockStacks = nextStacks;", src)

    def test_config_service_normalizer_contract(self):
        """The node-driver normalizer in this file mirrors the QML rules."""
        src = read(CONFIG_SERVICE)
        start = src.index("function normalizeDockAppId(appId)")
        end = src.index("function resolveCanonicalDockAppKey")
        body = src[start:end]
        for needle in ('\\.desktop$', "^[a-zA-Z0-9._-]+$", '"env"', '"flatpak"',
                       '"xdg-open"', '"gio"', '"gtk-launch"', '"electron"',
                       '"application-x-executable"', "window-"):
            self.assertIn(needle, body, needle)

    def test_application_service_dock_entries_and_open_paths(self):
        src = read(APP_SERVICE)
        self.assertIn("readonly property var dockEntries:", src)
        self.assertIn("DockStacks.buildDockEntries(raw, stacks", src)
        self.assertIn("function openPaths(paths)", src)
        # gio open with an argv array only; never a shell string.
        self.assertIn('["gio", "open"]', src)
        self.assertIn("Quickshell.execDetached(cmd)", src)
        self.assertNotIn("sh -c", src)
        # Dry-run aware (same convention as launch()).
        self.assertIn("if (!root.launchDryRun) {", src)

    def test_dock_uses_merged_entries(self):
        src = read(DOCK_QML)
        self.assertEqual(src.count("model: ApplicationService.dockEntries"), 2)
        self.assertEqual(src.count("stack: modelData.kind === \"stack\" ? modelData.stack : null"), 2)
        self.assertEqual(src.count("app: modelData.kind === \"stack\" ? null : ApplicationService.getAppById(modelData.appId)"), 2)

    def test_dock_item_stack_mode(self):
        src = read(DOCK_ITEM_QML)
        self.assertIn("property var stack: null", src)
        self.assertIn("readonly property bool isPopupOpen: menuOpen || chooserOpen || stackOpen", src)
        # Stack activation toggles the stack popup instead of launching.
        self.assertIn("root.stackOpen = !root.stackOpen;", src)
        # Popup exclusivity covers all three popup kinds in both directions.
        for frag in ("onStackOpenChanged", "if (stackOpen) {", "if (menuOpen) {",
                     "if (chooserOpen) {"):
            self.assertIn(frag, src, frag)
        # Drops onto an apps stack join it; pinned apps leave the flat row.
        self.assertIn("ConfigService.addAppToDockStack(info.stackTarget, root.appId)", src)
        self.assertIn("ApplicationService.togglePin(root.appId)", src)
        # Stack reorder goes through the pinned-row machinery by marker id.
        self.assertIn("ConfigService.reorderDockPinnedByAppId(root.appId, info.targetAppId)", src)
        # Stacks are never "running" and never report windows.
        self.assertIn("property bool isRunning: isStack ? false :", src)
        # The stack loader is lazy like the menu/chooser loaders.
        self.assertIn("id: stackLoader", src)
        self.assertIn("active: root.stackOpen", src)

    def test_qmldir_registers_stack_modules(self):
        src = read(DOCK_QMLDIR)
        self.assertIn("StackPopup 1.0 StackPopup.qml", src)
        self.assertIn("StackMenu 1.0 StackMenu.qml", src)

    def test_stack_popup_uses_live_folder_model(self):
        src = read(STACK_POPUP)
        # Live listing via Qt.labs.folderlistmodel (watched by Qt, no polling).
        self.assertIn("FolderListModel {", src)
        self.assertNotIn("Timer {", src)
        # Missing/unreadable folders show a visible empty state, never a
        # fabricated listing.
        self.assertIn("folderModel.status === FolderListModel.Error", src)
        # Files open through the same sanitized path helper (gio, argv).
        self.assertIn("ApplicationService.openPaths([path])", src)
        # Up-navigation is confined to the stack's own subtree.
        self.assertIn("root.currentFolderPath.indexOf(root.baseFolderPath + \"/\") === 0", src)
        # Member removal goes through the config API, not ad-hoc mutation.
        self.assertIn("ConfigService.removeAppFromDockStack(root.stack.id, appId)", src)

    def test_stack_menu_actions(self):
        src = read(STACK_MENU)
        self.assertIn("ConfigService.removeDockStack(root.stack.id)", src)
        self.assertIn("ApplicationService.openPaths([root.stack.path])", src)

    def test_settings_ui_stack_management(self):
        src = read(SETTINGS_WINDOW)
        self.assertIn("Dock Stacks", src)
        for frag in ('ConfigService.addDockStack("folder"',
                     'ConfigService.addDockStack("apps"',
                     "ConfigService.removeDockStack(stackRow.modelData.id)",
                     "ConfigService.addAppToDockStack(",
                     "ConfigService.removeAppFromDockStack(",
                     "ConfigService.setDockStackPath("):
            self.assertIn(frag, src, frag)

    def test_meta_shortcuts_source_skips_markers(self):
        src = read(META_JS)
        self.assertIn('if (typeof raw === "string" && raw.indexOf("stack:") === 0) continue;', src)

    def test_first_launch_defaults_untouched(self):
        dock = json.loads(read(os.path.join(REPO, "config/dock_config.json")))
        self.assertEqual(dock["pinned"],
                         ["org.kde.dolphin", "org.kde.konsole", "firefox",
                          "code", "systemsettings"])
        self.assertNotIn("stacks", dock)

    def test_qml_lint(self):
        res = subprocess.run(
            ["qmllint", "modules/dock/StackPopup.qml",
             "modules/dock/StackMenu.qml",
             "modules/dock/DockItem.qml",
             "modules/dock/Dock.qml",
             "services/config/ConfigService.qml",
             "services/applications/ApplicationService.qml",
             "modules/settings/SettingsWindow.qml"],
            cwd=REPO, capture_output=True, text=True)
        warnings = [ln for ln in (res.stdout + res.stderr).splitlines()
                    if "arning" in ln or "rror" in ln]
        self.assertEqual(warnings, [], "qmllint reported issues: " + "\n".join(warnings))


# ---------------------------------------------------------------------------
# Isolated headless runtime E2E (offscreen quickshell + private XDG dirs +
# private D-Bus session). ConfigService-level only: no KWin rig, no app
# scanning, no live session access.
# ---------------------------------------------------------------------------

PROBE_QML = """import QtQuick
import Quickshell
import "./services"

Scope {
    id: root
    // Phases: "load" (seeded config must sanitize in), "mutate" (exercise
    // the stack mutation API), "verify" (fresh process: reload persisted).
    property string phase: Quickshell.env("STACKS_PHASE") || "load"
    property int tries: 0
    property bool done: false

    function snap() {
        return {
            pinned: ConfigService.dockPinned,
            stacks: ConfigService.dockStacks,
            findFolder: ConfigService.getDockStack("seed-folder"),
            findGhost: ConfigService.getDockStack("ghost"),
            isEntry: ConfigService.isDockStackEntry("stack:st1"),
            isEntryBad: ConfigService.isDockStackEntry("st1")
        };
    }

    function log(marker, obj) {
        console.log(marker + ":" + JSON.stringify(obj));
    }

    function markerIn(list, id) {
        return list.indexOf("stack:" + id) !== -1;
    }

    Timer {
        interval: 200; running: true; repeat: true
        onTriggered: {
            if (root.done) return;
            if (root.phase === "load" || root.phase === "mutate") {
                // Wait until the seeded config has been loaded (seeded
                // pinned row contains the folder stack marker).
                if (!root.markerIn(ConfigService.dockPinned, "seed-folder")) {
                    if (++root.tries < 60) return;
                    root.log("STACKS-FAIL", {step: "seed-load-timeout", snap: root.snap()});
                    root.done = true; // terminal: never fall through
                    Qt.exit(1);
                    return;
                }
                if (root.phase === "load") {
                    root.log("STACKS-LOAD", root.snap());
                    root.done = true;
                    exitTimer.start();
                    return;
                }
                // --- mutation phase ---
                const res = {};
                res.addApps = ConfigService.addDockStack("apps", "  Media Group  ", "");
                res.addFolderBadPath = ConfigService.addDockStack("folder", "Bad", "/tmp/../etc");
                res.addFolderBadType = ConfigService.addDockStack("widget", "Bad", "");
                res.addFolder = ConfigService.addDockStack("folder", "Tmp", "/tmp//stacks-e2e");
                res.addMember = ConfigService.addAppToDockStack(res.addApps, "VLC");
                res.addMemberDup = ConfigService.addAppToDockStack(res.addApps, "vlc");
                res.addMemberToFolder = ConfigService.addAppToDockStack(res.addFolder, "VLC");
                res.rename = ConfigService.renameDockStack(res.addApps, "Media Apps");
                res.renameSame = ConfigService.renameDockStack(res.addApps, "Media Apps");
                res.setPathOnApps = ConfigService.setDockStackPath(res.addApps, "/var/tmp");
                res.setPath = ConfigService.setDockStackPath(res.addFolder, "/var/tmp//x");
                res.removeMember = ConfigService.removeAppFromDockStack(res.addApps, "vlc");
                res.removeMissingMember = ConfigService.removeAppFromDockStack(res.addApps, "nope");
                res.removeGhost = ConfigService.removeDockStack("ghost");
                res.removeApps = ConfigService.removeDockStack(res.addApps);
                res.after = root.snap();
                // The apps stack marker must be gone with the stack; the
                // folder stack marker (added at the row end) must remain.
                res.appsMarkerGone = !root.markerIn(res.after.pinned, res.addApps);
                res.folderMarkerKept = root.markerIn(res.after.pinned, res.addFolder);
                // Seed apps stack still intact after unrelated mutations.
                res.seedAppsKept = root.markerIn(res.after.pinned, "seed-apps");
                root.log("STACKS-MUTATE", res);
                root.done = true;
                exitTimer.start();
            } else {
                // verify: fresh process, persisted state must reload.
                if (!root.markerIn(ConfigService.dockPinned, "seed-folder")) {
                    if (++root.tries < 60) return;
                    root.log("STACKS-FAIL", {step: "verify-load-timeout", snap: root.snap()});
                    root.done = true;
                    Qt.exit(1);
                    return;
                }
                root.log("STACKS-VERIFY", root.snap());
                root.done = true;
                Qt.exit(0);
            }
        }
    }

    Timer {
        id: exitTimer
        interval: 2500
        onTriggered: {
            root.log("STACKS-FINAL", {phase: root.phase, snap: root.snap()});
            Qt.exit(0);
        }
    }

    Timer {
        interval: 30000; running: true; repeat: false
        onTriggered: { root.log("STACKS-FAIL", {step: "global-timeout"}); Qt.exit(1); }
    }
}
"""

SEED_DOCK = {
    "enabled": True, "floating": False, "edge": "bottom", "edgeOffset": 8,
    "iconSize": 48, "monitors": "all", "windowFilter": "all",
    "pinned": ["org.kde.dolphin", "stack:seed-folder", "firefox",
               "stack:seed-apps", "stack:ghost", "code"],
    "stacks": SEED_STACKS,
}


class TestStacksRuntimeE2E(unittest.TestCase):
    """Isolated quickshell runtime: load -> mutate -> persist -> reload."""

    @classmethod
    def setUpClass(cls):
        if shutil.which("quickshell") is None or shutil.which("dbus-run-session") is None:
            raise unittest.SkipTest("quickshell or dbus-run-session not available")
        cls.testroot = tempfile.mkdtemp(prefix="qs-stacks-e2e-")
        cls.probe = os.path.join(REPO, "_test_dock_stacks_probe.qml")
        with open(cls.probe, "w") as f:
            f.write(PROBE_QML)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.probe):
            os.remove(cls.probe)
        if hasattr(cls, "testroot"):
            shutil.rmtree(cls.testroot, ignore_errors=True)

    def _run_phase(self, phase, config_home):
        env = dict(os.environ)
        env.pop("WAYLAND_DISPLAY", None)
        env.pop("DISPLAY", None)
        runtime_dir = os.path.join(self.testroot, "runtime-" + phase)
        env.update({
            "QT_QPA_PLATFORM": "offscreen",
            "XDG_RUNTIME_DIR": runtime_dir,
            "XDG_CONFIG_HOME": config_home,
            "STACKS_PHASE": phase,
        })
        os.makedirs(runtime_dir, mode=0o700, exist_ok=True)
        proc = subprocess.run(
            ["dbus-run-session", "--", "quickshell", "-p", self.probe, "--no-duplicate"],
            cwd=REPO, env=env, capture_output=True, text=True, timeout=90)
        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
        return proc.returncode, combined

    def _seed(self, config_home):
        cfgdir = os.path.join(config_home, "quickshell-kde")
        os.makedirs(cfgdir, exist_ok=True)
        with open(os.path.join(cfgdir, "dock_config.json"), "w") as f:
            json.dump(SEED_DOCK, f)

    def _marker(self, combined, marker):
        lines = [ln for ln in combined.splitlines() if marker in ln]
        self.assertTrue(lines, f"missing {marker} in output:\n{combined}")
        raw = lines[-1].split(marker, 1)[1].strip().lstrip(":").strip()
        return json.loads(raw)

    def _persisted(self, config_home):
        with open(os.path.join(config_home, "quickshell-kde", "dock_config.json")) as f:
            return json.load(f)

    def _assert_loaded_state(self, snap):
        # Invalid seed stacks dropped; valid ones sanitized in.
        stacks = snap["stacks"]
        self.assertEqual(len(stacks), 2)
        self.assertEqual(stacks[0], {"id": "seed-folder", "type": "folder",
                                     "title": "Tmp Folder", "path": "/tmp",
                                     "appIds": []})
        self.assertEqual(stacks[1], {"id": "seed-apps", "type": "apps",
                                     "title": "Browsers",
                                     "appIds": ["firefox", "org.kde.konsole"]})
        # Dangling "stack:ghost" marker dropped; valid markers kept in order.
        self.assertEqual(snap["pinned"], ["org.kde.dolphin", "stack:seed-folder",
                                          "firefox", "stack:seed-apps", "code"])
        self.assertEqual(snap["findFolder"]["path"], "/tmp")
        self.assertIsNone(snap["findGhost"])
        self.assertTrue(snap["isEntry"])
        self.assertFalse(snap["isEntryBad"])

    def test_load_mutate_persist_reload(self):
        config_home = os.path.join(self.testroot, "config-main")
        os.makedirs(config_home, exist_ok=True)
        self._seed(config_home)

        # Phase 1: seeded config loads with sanitization.
        code, out = self._run_phase("load", config_home)
        self.assertEqual(code, 0, out)
        self._assert_loaded_state(self._marker(out, "STACKS-LOAD"))

        # Phase 2: mutations on a fresh process over the same config.
        code, out = self._run_phase("mutate", config_home)
        self.assertEqual(code, 0, out)
        res = self._marker(out, "STACKS-MUTATE")
        self.assertTrue(res["addApps"], res)            # "st1"
        self.assertEqual(res["addApps"], "st1", res)
        self.assertEqual(res["addFolderBadPath"], "", res)
        self.assertEqual(res["addFolderBadType"], "", res)
        self.assertTrue(res["addFolder"], res)          # "st2"
        self.assertEqual(res["addFolder"], "st2", res)
        self.assertTrue(res["addMember"], res)
        self.assertFalse(res["addMemberDup"], res)      # case-insensitive dup
        self.assertFalse(res["addMemberToFolder"], res)
        self.assertTrue(res["rename"], res)
        self.assertFalse(res["renameSame"], res)
        self.assertFalse(res["setPathOnApps"], res)
        self.assertTrue(res["setPath"], res)
        self.assertTrue(res["removeMember"], res)
        self.assertFalse(res["removeMissingMember"], res)
        self.assertFalse(res["removeGhost"], res)
        self.assertTrue(res["removeApps"], res)
        self.assertTrue(res["appsMarkerGone"], res)
        self.assertTrue(res["folderMarkerKept"], res)
        self.assertTrue(res["seedAppsKept"], res)
        after = res["after"]
        # Persisted in-memory state: folder stack with cleaned path, renamed
        # stack gone, seeded stacks intact.
        by_id = {s["id"]: s for s in after["stacks"]}
        self.assertEqual(by_id["st2"], {"id": "st2", "type": "folder",
                                        "title": "Tmp", "path": "/var/tmp/x",
                                        "appIds": []})
        self.assertNotIn("st1", by_id)
        self.assertEqual(by_id["seed-apps"]["title"], "Browsers")
        self.assertIn("stack:st2", after["pinned"])
        self.assertNotIn("stack:st1", after["pinned"])
        self.assertNotIn("stack:ghost", after["pinned"])

        # Persisted file on disk matches the final in-memory state.
        final = self._marker(out, "STACKS-FINAL")
        disk = self._persisted(config_home)
        self.assertEqual(disk["stacks"], final["snap"]["stacks"])
        self.assertEqual(disk["pinned"], final["snap"]["pinned"])
        disk_by_id = {s["id"]: s for s in disk["stacks"]}
        self.assertEqual(disk_by_id["st2"], {"id": "st2", "type": "folder",
                                             "title": "Tmp", "path": "/var/tmp/x",
                                             "appIds": []})
        self.assertIn("stack:st2", disk["pinned"])
        self.assertNotIn("stack:ghost", disk["pinned"])
        # User preferences survive verbatim.
        self.assertEqual(disk["pinned"][0], "org.kde.dolphin")
        self.assertEqual(disk["iconSize"], 48)

        # Phase 3: fresh process — persisted stacks reload cleanly.
        code, out = self._run_phase("verify", config_home)
        self.assertEqual(code, 0, out)
        snap = self._marker(out, "STACKS-VERIFY")
        self.assertEqual(snap["stacks"], final["snap"]["stacks"])
        self.assertEqual(snap["pinned"], final["snap"]["pinned"])
        self.assertEqual(snap["findFolder"]["path"], "/tmp")

    def test_fresh_defaults_have_no_stacks(self):
        """No seeded config: first-launch defaults load with zero stacks."""
        config_home = os.path.join(self.testroot, "config-fresh")
        os.makedirs(config_home, exist_ok=True)
        code, out = self._run_phase("verify", config_home)
        # The verify phase waits for the seeded marker which never comes;
        # use the global snapshot from the failure marker instead.
        self.assertNotEqual(code, 0)
        fail = self._marker(out, "STACKS-FAIL")
        self.assertEqual(fail["step"], "verify-load-timeout")
        snap = fail["snap"]
        self.assertEqual(snap["stacks"], [])
        self.assertEqual(snap["pinned"], ["org.kde.dolphin", "org.kde.konsole",
                                          "firefox", "code", "systemsettings"])


if __name__ == "__main__":
    unittest.main()
