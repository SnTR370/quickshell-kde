#!/usr/bin/env python3
"""
DOCK-010 File-drop tests: drop files (URI lists from other applications,
e.g. Dolphin) onto a dock icon to open them with that application.

SAFE: pure JS (URI/path filtering + launch-argument building) executed under
node (vm), static source contracts for the QML wiring (coexistence with the
intra-dock drag-and-drop, sanctioned launch mechanism, no focus stealing),
and an offscreen Quickshell runtime probe exercising the real DockItem
drop-handling logic in dry-run mode - the built command/args are asserted,
nothing is executed. No quickshell/KWin/Wayland is launched against the
live session.
"""
import json
import os
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(REPO, "services/applications/FileDrop.js")


def read(rel):
    with open(os.path.join(REPO, rel)) as f:
        return f.read()


DRIVER = r"""
const vm=require('vm'),fs=require('fs');
const ctx={};vm.createContext(ctx);vm.runInContext(fs.readFileSync(process.argv[1],'utf8').replace(/^\.pragma.*$/m,''),ctx);
const F=ctx;
const input=JSON.parse(process.argv[2]);
const out={};
if (input.uriListFromText) out.uriListFromText=input.uriListFromText.map(c=>F.uriListFromText(c));
if (input.localPathFromUri) out.localPathFromUri=input.localPathFromUri.map(u=>F.localPathFromUri(u));
if (input.localPathsFromUrls) out.localPathsFromUrls=input.localPathsFromUrls.map(c=>F.localPathsFromUrls(c.urls));
if (input.buildLaunchCommand) out.buildLaunchCommand=input.buildLaunchCommand.map(c=>F.buildLaunchCommand(c.app,c.paths,c.tokenizedExecArgs===undefined?[]:c.tokenizedExecArgs));
console.log(JSON.stringify(out));
"""


def run_node(payload):
    p = subprocess.run(["node", "-e", DRIVER, JS, json.dumps(payload)],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


class TestUriFiltering(unittest.TestCase):
    """Pure URI/path filtering properties (node vm, no QML)."""

    def test_uri_list_from_text(self):
        r = run_node({"uriListFromText": [
            "file:///a\nfile:///b\r\n",
            "# a comment\n\n  file:///c  \nfile:///d",
            "",
            None,
            "file:///x",
        ]})["uriListFromText"]
        self.assertEqual(r[0], ["file:///a", "file:///b"])
        self.assertEqual(r[1], ["file:///c", "file:///d"])  # comments/blanks dropped, trimmed
        self.assertEqual(r[2], [])
        self.assertEqual(r[3], [])
        self.assertEqual(r[4], ["file:///x"])

    def test_local_path_from_uri_file_scheme(self):
        r = run_node({"localPathFromUri": [
            "file:///home/user/photo.png",
            "file:///home/user/my%20file.txt",
            "file:///tmp/50%25off.txt",
            "file://localhost/etc/hosts",
            "file:///",
        ]})["localPathFromUri"]
        self.assertEqual(r[0], "/home/user/photo.png")
        self.assertEqual(r[1], "/home/user/my file.txt")   # percent-decoded
        self.assertEqual(r[2], "/tmp/50%off.txt")          # literal % round-trips when encoded
        self.assertEqual(r[3], "/etc/hosts")               # localhost authority is local
        self.assertEqual(r[4], "/")

    def test_local_path_from_uri_rejects_non_local(self):
        r = run_node({"localPathFromUri": [
            "http://example.com/x",
            "https://example.com/y",
            "ftp://example.com/z",
            "trash:///deleted-file",
            "file://nas/media/remote.mkv",   # remote file authority
            "relative.txt",                  # relative path
            "file:README",                   # file: without a path component
            "file:///bad/%zz",               # malformed percent escape
            "file:///bad/%",                 # trailing lone percent
            "",                              # empty
            None,
        ]})["localPathFromUri"]
        for v in r:
            self.assertEqual(v, "")

    def test_local_path_from_uri_plain_paths(self):
        r = run_node({"localPathFromUri": [
            "/plain/abs/path.txt",
            "/tmp/50%off literal.txt",       # plain paths are never decoded
            "C:\\not\\unix",
        ]})["localPathFromUri"]
        self.assertEqual(r[0], "/plain/abs/path.txt")
        self.assertEqual(r[1], "/tmp/50%off literal.txt")
        self.assertEqual(r[2], "")

    def test_local_paths_from_urls_filters_and_dedupes(self):
        r = run_node({"localPathsFromUrls": [
            {"urls": ["file:///a", "file:///a", "http://x/y", "/plain/b", "file://host/c"]},
            {"urls": []},
            {"urls": None},
            {"urls": "file:///a"},           # non-list input: safe empty
        ]})["localPathsFromUrls"]
        self.assertEqual(r[0], ["/a", "/plain/b"])  # dedup + non-file rejected, order kept
        self.assertEqual(r[1], [])
        self.assertEqual(r[2], [])
        self.assertEqual(r[3], [])


class TestLaunchCommandBuilding(unittest.TestCase):
    """Mechanism choice and argv construction (node vm, no QML)."""

    def test_gio_launch_preferred_with_desktop_file(self):
        r = run_node({"buildLaunchCommand": [{
            "app": {"id": "org.kde.gwenview",
                    "desktopFile": "/usr/share/applications/org.kde.gwenview.desktop",
                    "exec": "gwenview %U"},
            "paths": ["/tmp/a.png", "/tmp/b.png"],
        }]})["buildLaunchCommand"][0]
        # (a) gio launch resolves the desktop entry; Exec is never parsed here.
        self.assertEqual(r, ["gio", "launch",
                             "/usr/share/applications/org.kde.gwenview.desktop",
                             "/tmp/a.png", "/tmp/b.png"])

    def test_gtk_launch_fallback_without_exec(self):
        r = run_node({"buildLaunchCommand": [{
            "app": {"id": "org.custom.viewer", "exec": ""},
            "paths": ["/tmp/a.txt"],
        }]})["buildLaunchCommand"][0]
        self.assertEqual(r, ["gtk-launch", "org.custom.viewer", "/tmp/a.txt"])

    def test_tokenized_exec_args_with_files_appended(self):
        r = run_node({"buildLaunchCommand": [{
            "app": {"id": "org.custom.editor", "exec": "custom-editor --wait %F"},
            "paths": ["/tmp/a.txt", "/tmp/b.txt"],
            "tokenizedExecArgs": ["custom-editor", "--wait"],
        }]})["buildLaunchCommand"][0]
        # (c) caller-parsed argv only; all files in ONE invocation.
        self.assertEqual(r, ["custom-editor", "--wait", "/tmp/a.txt", "/tmp/b.txt"])

    def test_gtk_launch_fallback_when_exec_unparseable(self):
        r = run_node({"buildLaunchCommand": [{
            "app": {"id": "org.custom.editor", "exec": "custom-editor --wait %F"},
            "paths": ["/tmp/a.txt"],
            "tokenizedExecArgs": [],
        }]})["buildLaunchCommand"][0]
        self.assertEqual(r, ["gtk-launch", "org.custom.editor", "/tmp/a.txt"])

    def test_rejects_when_no_safe_mechanism(self):
        r = run_node({"buildLaunchCommand": [
            {"app": {"exec": "ghost-binary"}, "paths": ["/tmp/a"]},          # no id, no desktopFile
            {"app": {"id": "x"}, "paths": []},                               # no files
            {"app": {"id": "x"}, "paths": ["/tmp/a", ""]},                   # empty path entry
            {"app": {"id": "x"}, "paths": ["/tmp/a", 42]},                   # non-string entry
            {"app": None, "paths": ["/tmp/a"]},                              # no app
            {"app": {"id": "x"}, "paths": "/tmp/a"},                         # non-array paths
        ]})["buildLaunchCommand"]
        for v in r:
            self.assertIsNone(v)

    def test_no_shell_interpolation_surface(self):
        # Everything is an argv array; no shell entry point ever appears.
        cases = run_node({"buildLaunchCommand": [
            {"app": {"id": "a", "desktopFile": "/d.desktop"}, "paths": ["/f"]},
            {"app": {"id": "b", "exec": ""}, "paths": ["/f"]},
            {"app": {"id": "c", "exec": "c %F"}, "paths": ["/f"],
             "tokenizedExecArgs": ["c"]},
        ]})["buildLaunchCommand"]
        for cmd in cases:
            self.assertNotIn("sh", cmd)
            self.assertNotIn("-c", cmd)
            self.assertIsInstance(cmd, list)
        src = read("services/applications/FileDrop.js")
        self.assertNotIn("sh -c", src)
        # Purity: no execution/timing surface in the library's CODE
        # (doc comments may mention the execution conventions).
        code = "\n".join(line for line in src.splitlines()
                         if not line.strip().startswith("//"))
        self.assertNotRegex(code, r"Timer|setInterval|setTimeout|execDetached|Process\b")

    def test_tokenized_args_not_mutated(self):
        # The caller's argv must be copied, never mutated in place.
        DRIVER_MUT = DRIVER + """
const app={id:'x',exec:'x --flag'};
const tok=['x','--flag'];
const cmd=F.buildLaunchCommand(app,['/f'],tok);
console.log(JSON.stringify({cmd:cmd,tok:tok}));
"""
        p = subprocess.run(["node", "-e", DRIVER_MUT, JS, "{}"],
                           capture_output=True, text=True, timeout=30)
        assert p.returncode == 0, p.stderr
        d = json.loads(p.stdout.strip().splitlines()[-1])
        self.assertEqual(d["tok"], ["x", "--flag"])
        self.assertEqual(d["cmd"], ["x", "--flag", "/f"])


class TestStaticWiring(unittest.TestCase):
    """Static source contracts: coexistence with intra-dock DnD, sanctioned
    launch mechanism, and Wayland focus safety (no window activation on drop)."""

    def setUp(self):
        self.item = read("modules/dock/DockItem.qml")
        self.appsvc = read("services/applications/ApplicationService.qml")
        self.filedrop = read("services/applications/FileDrop.js")

    def test_dockitem_external_drop_area_exists_and_is_separate(self):
        self.assertIn('id: externalFileDropArea', self.item)
        self.assertIn('import "../../services/applications/FileDrop.js" as FileDrop', self.item)
        # Exactly two DropAreas: the keyed intra-dock one + the external one.
        self.assertEqual(self.item.count("DropArea {"), 2)
        # The intra-dock key contract is untouched (tests 13-18 of the blitz):
        # the keyed DropArea plus the dragProxy Drag.keys declaration.
        self.assertEqual(self.item.count('keys: ["quickshell-dock-item"]'), 2)
        self.assertEqual(self.item.count("Drag.keys:"), 1)
        # External drop area is keyless by design (OS drags carry no keys).
        ext = self.item[self.item.index("id: externalFileDropArea"):self.item.index("id: itemDropArea")]
        self.assertNotIn("keys:", ext)

    def test_dockitem_external_drop_guards(self):
        self.assertIn("function handleExternalFileDrop(rawUrls)", self.item)
        self.assertIn("ApplicationService.launchFiles(root.app, paths)", self.item)
        # Intra-dock drags (Quick drag source / active dock drag) are never
        # intercepted by the external path.
        self.assertIn("if (drop.source || root.dragging || (root.parentWindowRef && root.parentWindowRef.isDragging))",
                      self.item)
        # External drops are only accepted on launchable app icons.
        self.assertIn("(root.isPinned || root.isRunning) && root.app !== null", self.item)
        # Drop-target highlight reuses the existing visual language and now
        # reacts to both drop sources.
        self.assertIn("itemDropArea.containsDrag", self.item)
        self.assertIn("externalFileDropArea.containsDrag", self.item)

    def test_dockitem_drop_path_has_no_focus_stealing(self):
        # Launching is the ONLY side effect of an external drop: no window
        # activation, no toggling, no keyboard focus requests.
        start = self.item.index("function handleExternalFileDrop")
        end = self.item.index("DropArea {\n        id: itemDropArea")
        block = self.item[start:end]
        self.assertNotRegex(block, r"activateWindow|toggleWindow|pickActivation|requestKeyboardFocus|releaseKeyboardFocus|focus =")

    def test_application_service_launch_files_contract(self):
        self.assertIn('import "FileDrop.js" as FileDrop', self.appsvc)
        self.assertIn("function launchFiles(app, paths)", self.appsvc)
        self.assertIn("FileDrop.buildLaunchCommand(app, paths, tokenized)", self.appsvc)
        self.assertIn('root.lastLaunchedCommand = { type: "files", appId: app.id || "", args: cmd }', self.appsvc)
        # Same execution + dry-run conventions as launch(): argv array only.
        block = self.appsvc[self.appsvc.index("function launchFiles"):self.appsvc.index("function resolvePinnedKey")]
        self.assertIn("Quickshell.execDetached(cmd);", block)
        self.assertIn("if (!root.launchDryRun) {", block)
        self.assertIn("Array.isArray(paths)", block)
        self.assertNotIn("sh -c", block)
        self.assertNotRegex(block, r"\"sh\"|'sh'")

    def test_intra_dock_dnd_contracts_untouched(self):
        # The blitz DnD contract strings must survive verbatim.
        for contract in (
            'keys: ["quickshell-dock-item"]',
            "Drag.active: root.dragging",
            "Drag.source: root",
            "dragProxy.Drag.drop()",
            "dragProxy.Drag.cancel()",
            "ApplicationService.reorderPinnedApps",
            "ApplicationService.pinAppAt",
        ):
            self.assertIn(contract, self.item)
        sep = read("modules/dock/DockSeparator.qml")
        self.assertIn('keys: ["quickshell-dock-item"]', sep)


class TestRuntimeFileDrop(unittest.TestCase):
    """Offscreen Quickshell runtime probe: real DockItem + ApplicationService
    in launchDryRun mode. The built command/args are asserted; nothing is
    executed (no real gio/gtk-launch process is spawned)."""

    def test_runtime_drop_handling_logic(self):
        probe_path = os.path.join(REPO, "_test_dock_file_drop_probe.qml")
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["XDG_CONFIG_HOME"] = tmpdir
            env["QT_QPA_PLATFORM"] = "offscreen"
            try:
                with open(probe_path, "w") as pf:
                    pf.write("""import QtQuick
import Quickshell
import "./services"
import "./services/applications/FileDrop.js" as FileDrop
import "./modules/dock"

Scope {
    QtObject {
        id: mockWin
        property var activePopupItem: null
        readonly property bool hasActivePopup: activePopupItem !== null
        property var activeDragItem: null
        readonly property bool isDragging: activeDragItem !== null
        property bool isVertical: false
    }

    DockItem {
        id: gwenItem
        parentWindowRef: mockWin
        appId: "org.kde.gwenview"
        app: ApplicationService.getAppById("org.kde.gwenview")
    }

    DockItem {
        id: viewerItem
        parentWindowRef: mockWin
        appId: "org.custom.viewer"
        app: ApplicationService.getAppById("org.custom.viewer")
    }

    DockItem {
        id: editorItem
        parentWindowRef: mockWin
        appId: "org.custom.editor"
        app: ApplicationService.getAppById("org.custom.editor")
    }

    DockItem {
        id: ghostItem
        parentWindowRef: mockWin
        appId: "unknown.ghost.app"
        app: ApplicationService.getAppById("unknown.ghost.app")
    }

    Timer {
        interval: 250
        running: true
        repeat: false
        onTriggered: {
            let payload = null;
            try {
                ApplicationService.launchDryRun = true;
                ApplicationService.applications = [
                    { id: "org.kde.gwenview", name: "Gwenview", icon: "gwenview",
                      desktopFile: "/usr/share/applications/org.kde.gwenview.desktop",
                      exec: "gwenview %U", aliases: ["org.kde.gwenview", "gwenview"] },
                    { id: "org.custom.viewer", name: "Viewer", icon: "viewer",
                      aliases: ["org.custom.viewer"] },
                    { id: "org.custom.editor", name: "Editor", icon: "editor",
                      exec: "custom-editor --wait %F", execArgs: ["custom-editor", "--wait"],
                      aliases: ["org.custom.editor"] }
                ];
                ApplicationService.loading = false;
                ConfigService.dockPinned = ["org.kde.gwenview", "org.custom.viewer", "org.custom.editor"];
                ApplicationService.lastLaunchedCommand = null;

                const gwenPinned = gwenItem.isPinned;
                const ghostResolved = ghostItem.app === null;

                // 1. Mixed URI list drop on a pinned app with a desktop file:
                //    local file URIs (percent-decoded) pass, http is filtered out.
                const drop1 = gwenItem.handleExternalFileDrop([
                    "file:///tmp/photo one.png",
                    "file:///tmp/photo%20two.png",
                    "http://evil.example/not-a-file"
                ]);
                const cmd1 = ApplicationService.lastLaunchedCommand;

                // 2. Multi-file drop in ONE invocation on the id-only app.
                const drop2 = viewerItem.handleExternalFileDrop([
                    "file:///tmp/notes.txt", "/tmp/plain.txt"
                ]);
                const cmd2 = ApplicationService.lastLaunchedCommand;

                // 3. Tokenized exec fallback (execArgs + files).
                const drop3 = editorItem.handleExternalFileDrop(["file:///tmp/a.txt", "file:///tmp/b.txt"]);
                const cmd3 = ApplicationService.lastLaunchedCommand;

                // 4. All-remote drop: visible no-op, command unchanged.
                ApplicationService.lastLaunchedCommand = null;
                const drop4 = gwenItem.handleExternalFileDrop(["http://a.example/x", "ftp://b.example/y"]);
                const cmd4 = ApplicationService.lastLaunchedCommand;

                // 5. Malformed / empty entries only: no-op.
                const drop5 = gwenItem.handleExternalFileDrop(["", "file:///bad/%zz", "relative.txt"]);
                const cmd5 = ApplicationService.lastLaunchedCommand;

                // 6. Non-launchable item (unknown app, not pinned/running): no-op.
                const drop6 = ghostItem.handleExternalFileDrop(["file:///tmp/x"]);
                const cmd6 = ApplicationService.lastLaunchedCommand;

                // 7. Intra-dock drag in progress: external drop must be ignored.
                mockWin.activeDragItem = gwenItem;
                const drop7 = gwenItem.handleExternalFileDrop(["file:///tmp/x"]);
                mockWin.activeDragItem = null;
                const cmd7 = ApplicationService.lastLaunchedCommand;

                // 8. Item mid-drag: ignored.
                gwenItem.dragging = true;
                const drop8 = gwenItem.handleExternalFileDrop(["file:///tmp/x"]);
                gwenItem.dragging = false;
                const cmd8 = ApplicationService.lastLaunchedCommand;

                // 9. text/uri-list parsing fallback (pure JS, same module the
                //    DropArea uses when urls are absent).
                const parsedText = FileDrop.uriListFromText("# comment\r\nfile:///tmp/c.txt\n\nfile:///tmp/d.txt");

                // 10. Drop-target highlight composition stays available.
                const highlightOk = (gwenItem.dropTargeted === false);

                payload = {
                    gwenPinned: gwenPinned,
                    ghostResolved: ghostResolved,
                    drop1: drop1, cmd1: cmd1,
                    drop2: drop2, cmd2: cmd2,
                    drop3: drop3, cmd3: cmd3,
                    drop4: drop4, cmd4: cmd4,
                    drop5: drop5, cmd5: cmd5,
                    drop6: drop6, cmd6: cmd6,
                    drop7: drop7, cmd7: cmd7,
                    drop8: drop8, cmd8: cmd8,
                    parsedText: parsedText,
                    highlightOk: highlightOk
                };
            } catch (err) {
                payload = { probeError: String(err) };
            }
            console.log("DOCK_FILE_DROP_RUNTIME:" + JSON.stringify(payload));
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
                marker = "DOCK_FILE_DROP_RUNTIME:"
                self.assertIn(marker, combined, f"Missing marker in output:\n{combined}")
                payload_line = [line for line in combined.splitlines() if marker in line][-1]
                data = json.loads(payload_line.split(marker, 1)[1].strip())

                self.assertNotIn("probeError", data)
                self.assertTrue(data["gwenPinned"])
                self.assertTrue(data["ghostResolved"])

                # 1. gio launch preferred; percent-decoding; http filtered.
                self.assertTrue(data["drop1"])
                self.assertEqual(data["cmd1"]["type"], "files")
                self.assertEqual(data["cmd1"]["appId"], "org.kde.gwenview")
                self.assertEqual(data["cmd1"]["args"], [
                    "gio", "launch", "/usr/share/applications/org.kde.gwenview.desktop",
                    "/tmp/photo one.png", "/tmp/photo two.png"])

                # 2. gtk-launch fallback; plain local paths and file URIs both
                #    accepted; all files in one invocation.
                self.assertTrue(data["drop2"])
                self.assertEqual(data["cmd2"]["args"], [
                    "gtk-launch", "org.custom.viewer", "/tmp/notes.txt", "/tmp/plain.txt"])

                # 3. Tokenized exec argv fallback with files appended.
                self.assertTrue(data["drop3"])
                self.assertEqual(data["cmd3"]["args"], [
                    "custom-editor", "--wait", "/tmp/a.txt", "/tmp/b.txt"])

                # 4-8. Rejections are visible no-ops (no command built).
                for key in ("drop4", "drop5", "drop6", "drop7", "drop8"):
                    self.assertFalse(data[key], key)
                for key in ("cmd4", "cmd5", "cmd6", "cmd7", "cmd8"):
                    self.assertIsNone(data[key], key)

                # 9. uri-list text parsing.
                self.assertEqual(data["parsedText"], ["file:///tmp/c.txt", "file:///tmp/d.txt"])

                # 10. Highlight property composes without a drag present.
                self.assertTrue(data["highlightOk"])
            finally:
                if os.path.exists(probe_path):
                    os.remove(probe_path)

    def test_qmllint_changed_modules(self):
        res = subprocess.run(
            ["qmllint", "modules/dock/DockItem.qml",
             "services/applications/ApplicationService.qml"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"qmllint failed: {res.stderr}")


if __name__ == "__main__":
    unittest.main()
