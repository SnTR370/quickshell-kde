#!/usr/bin/env python3
"""
Behavioral regression suite for services/core/JsonStore.qml — the JSON
persistence primitive underneath ConfigService and ThemeService.

Layers:
1. Static source contracts (public API surface, atomic write, .bak gating,
   root-object restriction on load) + qmllint.
2. Isolated runtime E2E: every scenario runs `quickshell -p` offscreen inside
   a private D-Bus session with private XDG_RUNTIME_DIR/XDG_CONFIG_HOME and a
   temp store path. The live Plasma session is never touched.

Covered runtime behavior:
- load(): valid JSON, fallback file, missing file, corrupt JSON, empty file,
  non-object root (array)
- save(): roundtrip incl. nested directory creation, undefined/function
  rejection, empty-path rejection, rapid-save coalescing (last write wins),
  load-during-save deferral, read-superseded-by-save
- parse-error recovery: .bak backup of the corrupt file, clean rewrite,
  clean reload; no .bak without a prior parse error
- DOCUMENTED DEFECT (found 2026-11-06, see
  test_save_array_roundtrip_documented_defect): save() accepts non-object
  roots (arrays/scalars) and persists them, but load() rejects the very same
  file ("Root JSON value must be an object"), permanently locking the store
  back to defaults on the next start.
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
JSON_STORE_QML = os.path.join(REPO, "services/core/JsonStore.qml")

DEFAULT_VALUE = {"d": True}

PROBE_QML = """import QtQuick
import Quickshell
import "./services/core"

Scope {
    id: root

    property string scenario: Quickshell.env("JSON_STORE_SCENARIO") || ""
    property string storePath: Quickshell.env("JSON_STORE_PATH") || ""
    property string storeFallback: Quickshell.env("JSON_STORE_FALLBACK") || ""
    property var events: []
    property int tries: 0
    property int settleTicks: 0
    property bool done: false

    readonly property var defaultValue: ({"d": true})

    function record(ev) {
        root.events.push(ev);
    }

    function hasEvent(type) {
        for (let i = 0; i < root.events.length; i++) {
            if (root.events[i].type === type) return true;
        }
        return false;
    }

    function eventCount(type) {
        let n = 0;
        for (let i = 0; i < root.events.length; i++) {
            if (root.events[i].type === type) n++;
        }
        return n;
    }

    function result() {
        return {
            scenario: root.scenario,
            events: root.events,
            value: store.value,
            loaded: store.loaded,
            hadParseError: store.hadParseError,
            rawContent: store.rawContent,
            lastPersistedRaw: store.lastPersistedRaw
        };
    }

    function finish() {
        if (root.done) return;
        root.done = true;
        console.log("JS-RESULT:" + JSON.stringify(result()));
        Qt.exit(0);
    }

    function fail(stepName, detail) {
        if (root.done) return;
        root.done = true;
        console.log("JS-FAIL:" + JSON.stringify({
            scenario: root.scenario, step: stepName, detail: detail,
            result: result()}));
        Qt.exit(1);
    }

    JsonStore {
        id: store
        path: root.storePath
        fallbackPath: root.storeFallback
        defaultValue: root.defaultValue
        onLoadedValue: (parsed, raw) => root.record({type: "loaded", value: parsed, raw: raw})
        onSavedValue: data => root.record({type: "saved", value: data})
        onFailed: (phase, code, details) => root.record({type: "failed", phase: phase, code: code, details: details})
    }

    // Second instance without a path: load()/save() must fail safely.
    JsonStore {
        id: emptyStore
        path: ""
        defaultValue: root.defaultValue
        onFailed: (phase, code, details) => root.record({type: "empty-store-failed", phase: phase, details: details})
    }

    Timer {
        interval: 150; running: true; repeat: true
        onTriggered: root.tick()
    }

    Timer {
        interval: 15000; running: true; repeat: false
        onTriggered: root.fail("global-timeout", "")
    }

    function tick() {
        if (root.done) return;
        root.tries++;
        if (root.tries > 80) { root.fail("scenario-timeout", ""); return; }

        switch (root.scenario) {

        // Pure load scenarios: the store auto-loads on completion and
        // settles into a terminal event (loaded or failed).
        case "load-valid":
        case "load-fallback":
        case "load-missing":
        case "load-corrupt":
        case "load-empty":
        case "load-array-root":
            if (store.loaded) root.finish();
            return;

        case "save-roundtrip":
            if (!store.loaded) return;
            if (!hasEvent("save-called")) {
                record({type: "save-called", returned: store.save({"x": "y", "n": 2})});
            }
            if (hasEvent("saved")) root.finish();
            return;

        case "save-invalid-data":
            if (!store.loaded) return;
            record({type: "save-undefined", returned: store.save(undefined)});
            record({type: "save-function", returned: store.save(function() { return 1; })});
            record({type: "empty-path-save", returned: emptyStore.save({"a": 1})});
            record({type: "empty-path-load", returned: emptyStore.load()});
            root.finish();
            return;

        case "save-coalesce":
            if (!store.loaded) return;
            if (!hasEvent("save-called")) {
                record({type: "save-called",
                        first: store.save({"which": "A"}),
                        second: store.save({"which": "B"})});
            }
            if (eventCount("saved") >= 2) root.finish();
            return;

        case "load-during-save":
            if (!store.loaded) return;
            if (!hasEvent("save-called")) {
                record({type: "save-called", returned: store.save({"z": 26})});
                record({type: "load-called", returned: store.load()});
            }
            if (hasEvent("saved") && hasEvent("loaded")) root.finish();
            return;

        case "read-superseded":
            if (!hasEvent("loaded")) return;
            if (!hasEvent("save-called")) {
                record({type: "load-called", returned: store.load()});
                record({type: "save-called", returned: store.save({"s": 1})});
                root.settleTicks = 0;
                return;
            }
            if (!hasEvent("saved")) return;
            // A few extra ticks: the superseded read must NOT deliver a
            // second loaded event with the stale on-disk content.
            root.settleTicks++;
            if (root.settleTicks >= 6) root.finish();
            return;

        case "parse-error-recovery":
            if (!store.loaded) return;
            if (!hasEvent("save-called")) {
                // hadParseError is only true between the failed parse and
                // the successful clean write (which resets it), so this
                // check must gate exactly the pre-save tick.
                if (!store.hadParseError) { root.fail("expected-parse-error", ""); return; }
                record({type: "save-called", returned: store.save({"clean": 1})});
                return;
            }
            if (!hasEvent("saved")) return;
            if (!hasEvent("reload-called")) {
                record({type: "reload-called", returned: store.load()});
                return;
            }
            if (eventCount("loaded") >= 1) root.finish();
            return;

        case "save-array-root":
            if (!store.loaded) return;
            if (!hasEvent("save-called")) {
                record({type: "save-called", returned: store.save([1, 2, 3])});
                return;
            }
            if (!hasEvent("saved")) return;
            if (!hasEvent("reload-called")) {
                record({type: "reload-called", returned: store.load()});
                return;
            }
            // Terminal either way: a loaded event (array accepted) or a
            // failed(parse) event (array rejected) — Python asserts which.
            root.finish();
            return;

        default:
            root.fail("unknown-scenario", root.scenario);
            return;
        }
    }
}
"""


def read(rel):
    with open(os.path.join(REPO, rel)) as f:
        return f.read()


class TestJsonStoreStaticContracts(unittest.TestCase):
    """Source-level contracts of the persistence primitive."""

    def test_api_surface(self):
        src = read("services/core/JsonStore.qml")
        for prop in ("property string path", "property string fallbackPath",
                     "property var defaultValue", "property var value",
                     "property bool loaded", "property bool hadParseError"):
            self.assertIn(prop, src, prop)
        for sig in ("signal loadedValue(var parsedJson, string rawText)",
                    "signal savedValue(var data)",
                    "signal failed(string phase, int exitCode, string details)"):
            self.assertIn(sig, src, sig)
        for fn in ("function load()", "function save(data)"):
            self.assertIn(fn, src, fn)
        # Auto-load on completion when a path is set.
        self.assertIn("Component.onCompleted:", src)
        self.assertRegex(src, re.compile(r"if \(path && path\.length > 0\) \{\s*\n\s*load\(\);", re.M))

    def test_atomic_write_contract(self):
        """Writes must be tmp-file + atomic rename; parent dirs are created.

        The shell command is embedded in a QML string literal, so the
        source text carries escaped quotes (\\\")."""
        src = read("services/core/JsonStore.qml")
        self.assertIn("mkdir -p", src)
        self.assertIn("mv -f \\\"$1.tmp.$$\\\" \\\"$1\\\"", src)
        # A failed write must clean up its temporary file.
        self.assertIn("rm -f \\\"$1.tmp.$$\\\"", src)

    def test_parse_error_backup_contract(self):
        """The corrupt-file .bak backup is gated on the hadParseError flag."""
        src = read("services/core/JsonStore.qml")
        self.assertIn("[ \\\"$3\\\" = \\\"1\\\" ]", src)
        self.assertIn("[ -f \\\"$1\\\" ] && [ ! -f \\\"$1.bak\\\" ]", src)
        self.assertIn("cp -f \\\"$1\\\" \\\"$1.bak\\\"", src)
        self.assertIn("root.hadParseError ? \"1\" : \"0\"", src)

    def test_load_rejects_non_object_root(self):
        src = read("services/core/JsonStore.qml")
        self.assertIn("Root JSON value must be an object", src)

    def test_qml_lint(self):
        res = subprocess.run(["qmllint", "services/core/JsonStore.qml"],
                             cwd=REPO, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"qmllint failed: {res.stderr}")


class TestJsonStoreRuntime(unittest.TestCase):
    """Isolated quickshell runtime: one scenario per process, private XDG dirs."""

    @classmethod
    def setUpClass(cls):
        if shutil.which("quickshell") is None or shutil.which("dbus-run-session") is None:
            raise unittest.SkipTest("quickshell or dbus-run-session not available")
        cls.testroot = tempfile.mkdtemp(prefix="qs-jsonstore-e2e-")
        cls.probe = os.path.join(REPO, "_test_json_store_probe.qml")
        with open(cls.probe, "w") as f:
            f.write(PROBE_QML)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.probe):
            os.remove(cls.probe)
        if hasattr(cls, "testroot"):
            shutil.rmtree(cls.testroot, ignore_errors=True)

    def _run(self, scenario, seed=None, fallback_seed=None,
             store_rel="state.json", fallback_rel="fallback.json"):
        """Run one probe process. Returns (result dict, store path)."""
        config_home = tempfile.mkdtemp(prefix="cfg-", dir=self.testroot)
        cfgdir = os.path.join(config_home, "quickshell-kde")
        os.makedirs(cfgdir, exist_ok=True)
        store_path = os.path.join(cfgdir, store_rel)
        if seed is not None:
            os.makedirs(os.path.dirname(store_path), exist_ok=True)
            with open(store_path, "w") as f:
                f.write(seed)
        fallback_path = ""
        if fallback_seed is not None:
            fallback_path = os.path.join(cfgdir, fallback_rel)
            with open(fallback_path, "w") as f:
                f.write(fallback_seed)

        runtime_dir = os.path.join(self.testroot,
                                   "runtime-" + scenario + "-" + os.path.basename(config_home))
        os.makedirs(runtime_dir, mode=0o700, exist_ok=True)
        env = dict(os.environ)
        env.pop("WAYLAND_DISPLAY", None)
        env.pop("DISPLAY", None)
        env.update({
            "QT_QPA_PLATFORM": "offscreen",
            "XDG_RUNTIME_DIR": runtime_dir,
            "XDG_CONFIG_HOME": config_home,
            "JSON_STORE_SCENARIO": scenario,
            "JSON_STORE_PATH": store_path,
            "JSON_STORE_FALLBACK": fallback_path,
        })
        proc = subprocess.run(
            ["dbus-run-session", "--", "quickshell", "-p", self.probe, "--no-duplicate"],
            cwd=REPO, env=env, capture_output=True, text=True, timeout=60)
        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
        self.assertEqual(proc.returncode, 0,
                         f"probe failed for {scenario}:\n{combined}\nSTORE PATH: {store_path}")
        lines = [ln for ln in combined.splitlines() if "JS-RESULT:" in ln]
        self.assertTrue(lines, f"missing JS-RESULT for {scenario}:\n{combined}")
        return json.loads(lines[-1].split("JS-RESULT:", 1)[1].strip()), store_path

    def _events(self, data, ev_type):
        return [e for e in data["events"] if e["type"] == ev_type]

    def _failed_phases(self, data):
        return [e["phase"] for e in self._events(data, "failed")]

    def _read_store_file(self, store_path):
        with open(store_path) as f:
            return json.load(f)

    # ---- load() ----

    def test_load_valid_json(self):
        seed = json.dumps({"a": 1, "b": "x"})
        data, store_path = self._run("load-valid", seed=seed)
        loaded = self._events(data, "loaded")
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["value"], {"a": 1, "b": "x"})
        self.assertEqual(data["value"], {"a": 1, "b": "x"})
        self.assertEqual(data["rawContent"], seed)
        self.assertFalse(data["hadParseError"])
        self.assertEqual(self._failed_phases(data), [])

    def test_load_fallback_file(self):
        """A missing user config falls back to the bundled default file."""
        fallback = json.dumps({"fb": True})
        data, store_path = self._run("load-fallback", fallback_seed=fallback)
        loaded = self._events(data, "loaded")
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["value"], {"fb": True})
        self.assertEqual(data["value"], {"fb": True})
        self.assertFalse(data["hadParseError"])
        # The user file did not exist and must not have been created by a read.
        self.assertFalse(os.path.exists(store_path))
        self.assertEqual(self._failed_phases(data), [])

    def test_load_missing_file_without_fallback(self):
        data, store_path = self._run("load-missing")
        self.assertEqual(self._failed_phases(data), ["read"])
        self.assertEqual(data["value"], DEFAULT_VALUE)
        self.assertTrue(data["loaded"])
        self.assertEqual(self._events(data, "loaded"), [])

    def test_load_corrupt_json(self):
        data, store_path = self._run("load-corrupt", seed="CORRUPT-not-json{")
        self.assertEqual(self._failed_phases(data), ["parse"])
        self.assertEqual(data["value"], DEFAULT_VALUE)
        self.assertTrue(data["hadParseError"])
        self.assertEqual(self._events(data, "loaded"), [])
        # The corrupt file must be left untouched by a failed read.
        with open(store_path) as f:
            self.assertEqual(f.read(), "CORRUPT-not-json{")

    def test_load_empty_file(self):
        data, store_path = self._run("load-empty", seed="")
        self.assertEqual(self._failed_phases(data), ["parse"])
        self.assertEqual(data["value"], DEFAULT_VALUE)
        self.assertTrue(data["hadParseError"])

    def test_load_array_root_rejected(self):
        data, store_path = self._run("load-array-root", seed="[1, 2, 3]")
        self.assertEqual(self._failed_phases(data), ["parse"])
        self.assertEqual(data["value"], DEFAULT_VALUE)
        self.assertTrue(data["hadParseError"])

    # ---- save() ----

    def test_save_roundtrip_creates_nested_dir_and_persists(self):
        data, store_path = self._run("save-roundtrip",
                                     store_rel="deep/nested/state.json")
        save_called = self._events(data, "save-called")
        self.assertEqual(len(save_called), 1)
        self.assertTrue(save_called[0]["returned"])
        saved = self._events(data, "saved")
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["value"], {"x": "y", "n": 2})
        self.assertEqual(data["value"], {"x": "y", "n": 2})
        # Directory auto-created, pretty-printed JSON on disk.
        self.assertEqual(self._read_store_file(store_path), {"x": "y", "n": 2})
        with open(store_path) as f:
            self.assertIn("\n", f.read())  # JSON.stringify(data, null, 2)
        # No parse error before the save -> no .bak file.
        self.assertFalse(os.path.exists(store_path + ".bak"))
        # The only failure is the initial read of the missing file.
        self.assertEqual(self._failed_phases(data), ["read"])

    def test_save_valid_existing_file_creates_no_bak(self):
        data, store_path = self._run("save-roundtrip",
                                     seed=json.dumps({"v": 1}))
        self.assertEqual(self._events(data, "save-called")[0]["returned"], True)
        self.assertEqual(self._read_store_file(store_path), {"x": "y", "n": 2})
        self.assertFalse(os.path.exists(store_path + ".bak"))
        self.assertEqual(self._failed_phases(data), [])
        self.assertFalse(data["hadParseError"])

    def test_save_rejects_undefined_and_function(self):
        data, store_path = self._run("save-invalid-data")
        by_type = {e["type"]: e for e in data["events"]}
        self.assertIs(by_type["save-undefined"]["returned"], False)
        self.assertIs(by_type["save-function"]["returned"], False)
        self.assertEqual(self._failed_phases(data).count("serialize"), 2)
        # Nothing may be written by a rejected save.
        self.assertFalse(os.path.exists(store_path))

    def test_save_and_load_reject_empty_path(self):
        data, store_path = self._run("save-invalid-data")
        by_type = {e["type"]: e for e in data["events"]}
        self.assertIs(by_type["empty-path-save"]["returned"], False)
        self.assertIs(by_type["empty-path-load"]["returned"], False)
        # The empty-path save failure is reported through failed() with a
        # distinct reason (no process is ever spawned).
        empty_failed = self._events(data, "empty-store-failed")
        self.assertEqual(len(empty_failed), 1)
        self.assertEqual(empty_failed[0]["phase"], "serialize")
        self.assertIn("Empty path", empty_failed[0]["details"])

    def test_rapid_saves_coalesce_last_write_wins(self):
        """Two saves in the same tick: the in-flight write finishes, then the
        pending second write lands; the file ends up with the second data."""
        data, store_path = self._run("save-coalesce")
        save_called = self._events(data, "save-called")[0]
        self.assertTrue(save_called["first"])
        self.assertTrue(save_called["second"])
        saved = self._events(data, "saved")
        self.assertEqual(len(saved), 2)
        self.assertEqual(saved[0]["value"], {"which": "A"})
        self.assertEqual(saved[1]["value"], {"which": "B"})
        self.assertEqual(self._read_store_file(store_path), {"which": "B"})
        self.assertEqual(data["value"], {"which": "B"})

    def test_load_during_save_deferred_until_write_completes(self):
        """load() while a write is in flight is deferred and re-reads the
        file the write just persisted."""
        data, store_path = self._run("load-during-save")
        by_type = {e["type"]: e for e in data["events"]}
        self.assertTrue(by_type["save-called"]["returned"])
        self.assertTrue(by_type["load-called"]["returned"])
        events = data["events"]
        saved_idx = next(i for i, e in enumerate(events) if e["type"] == "saved")
        loaded_idx = next(i for i, e in enumerate(events) if e["type"] == "loaded")
        self.assertGreater(loaded_idx, saved_idx, events)
        self.assertEqual(events[loaded_idx]["value"], {"z": 26})
        self.assertEqual(data["value"], {"z": 26})
        self.assertEqual(self._read_store_file(store_path), {"z": 26})

    def test_read_superseded_by_save(self):
        """A save issued while a read is running kills the read; the stale
        on-disk content must never surface as a loaded event."""
        data, store_path = self._run("read-superseded",
                                     seed=json.dumps({"old": 1}))
        loaded = self._events(data, "loaded")
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["value"], {"old": 1})  # startup auto-load only
        saved = self._events(data, "saved")
        self.assertEqual(len(saved), 1)
        self.assertEqual(data["value"], {"s": 1})
        self.assertEqual(self._read_store_file(store_path), {"s": 1})

    # ---- parse-error recovery ----

    def test_parse_error_recovery_creates_bak_and_reloads_clean(self):
        corrupt = "CORRUPT-not-json{"
        data, store_path = self._run("parse-error-recovery", seed=corrupt)
        self.assertEqual(self._failed_phases(data), ["parse"])  # startup only
        save_called = self._events(data, "save-called")
        self.assertEqual(len(save_called), 1)
        self.assertTrue(save_called[0]["returned"])
        # Clean rewrite + clean reload.
        self.assertEqual(self._read_store_file(store_path), {"clean": 1})
        loaded = self._events(data, "loaded")
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["value"], {"clean": 1})
        # The .bak preserves the original corrupt bytes.
        with open(store_path + ".bak") as f:
            self.assertEqual(f.read(), corrupt)

    def test_save_array_roundtrip_documented_defect(self):
        """DOCUMENTED DEFECT (2026-11-06, core reliability marathon):
        JsonStore.save() does not validate the JSON root shape, so it happily
        persists an array; JsonStore.load() then rejects that same file
        ("Root JSON value must be an object") and the store silently falls
        back to defaults on the next start. Every in-repo caller
        (ConfigService x2, ThemeService) saves plain objects, so today this
        only bites on a caller regression — which is exactly what this test
        pins. Fix direction (out of scope for the test-only marathon
        commit): reject non-object roots in save() like load() does.
        Until then, this test asserts the current behavior so it cannot
        drift further silently."""
        data, store_path = self._run("save-array-root")
        # The save itself is accepted...
        self.assertTrue(self._events(data, "save-called")[0]["returned"])
        self.assertEqual(len(self._events(data, "saved")), 1)
        self.assertEqual(self._read_store_file(store_path), [1, 2, 3])
        # ...but the store cannot load its own file back: the reload fails
        # with a parse error and the value silently resets to defaults.
        self.assertEqual(self._failed_phases(data), ["read", "parse"])
        self.assertEqual(data["value"], DEFAULT_VALUE)
        self.assertTrue(data["hadParseError"])


if __name__ == "__main__":
    unittest.main()
