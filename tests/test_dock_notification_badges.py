#!/usr/bin/env python3
"""
DOCK-009 notification, urgency and progress indicator tests.

SAFE: pure badge helpers executed under node (vm), static wiring contracts
for the QML integration, qmllint of the touched files, and an isolated
headless runtime E2E (private XDG dirs + private D-Bus session, offscreen
quickshell) that drives the shell's REAL freedesktop notification server
over D-Bus (gdbus org.freedesktop.Notifications.Notify / CloseNotification):
badge count from active server state, critical urgency flag, live progress
via the freedesktop "value" hint, in-place replacement (replaces_id),
client withdrawal, client-supplied expiry, dismiss-on-attention, and the
honest no-server degradation when ConfigService.notificationsEnabled is
false. The live Plasma session is never touched; no notification data is
ever estimated or fabricated.

Run with: python3 -m unittest tests.test_dock_notification_badges
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BADGES_JS = os.path.join(REPO, "services/notifications/NotificationBadges.js")
NOTIF_SERVICE = os.path.join(REPO, "services/notifications/NotificationService.qml")
NOTIF_CARD = os.path.join(REPO, "modules/notifications/NotificationCard.qml")
TOAST_HOST = os.path.join(REPO, "modules/notifications/ToastHost.qml")
DOCK_ITEM_QML = os.path.join(REPO, "modules/dock/DockItem.qml")
KWIN_BRIDGE_JS = os.path.join(REPO, "services/kwin/scripts/kwin-event-bridge.js")


def read(path):
    with open(path) as f:
        return f.read()


DRIVER = (
    "const vm=require('vm'),fs=require('fs');\n"
    "const ctx={};vm.createContext(ctx);vm.runInContext("
    "fs.readFileSync(process.argv[1],'utf8').replace(/^\\.pragma.*$/m,''),ctx);\n"
    "const D=ctx;\n"
    "const input=JSON.parse(process.argv[2]);\n"
    "const out={};\n"
    "const resolver=function(spec){"
    "return function(id){return (spec&&spec[id]!==undefined)?spec[id]:null;};};\n"
    # QVariant-marshalled sequence: array-like, Array.isArray() === false.
    "if(input.op==='toArraySeq'){"
    "const seq={length:2};seq[0]='a';seq[1]='b';"
    "out.seq=D.toArray(seq);out.isArray=Array.isArray(out.seq);}\n"
    "else if(input.op==='progress'){"
    "out.values=input.cases.map(c=>D.normalizeProgress(c));}\n"
    "else if(input.op==='item'){"
    "out.item=D.makeBadgeItem(input.n,input.now);}\n"
    "else if(input.op==='match'){"
    "out.candidates=input.cases.map(c=>D.matchCandidates(c));"
    "out.keys=input.cases.map(c=>D.matchAppKey(c,resolver(input.apps)));\n"
    "out.noFn=D.matchAppKey(input.cases[0],null);}\n"
    "else if(input.op==='upsert'){"
    "let list=[];"
    "for(const it of input.items){list=D.upsertActive(list,D.makeBadgeItem(it.n,it.now));}"
    "out.ids=list.map(i=>i.id);"
    "out.removed=D.removeActive(list,input.remove).map(i=>i.id);}\n"
    "else if(input.op==='badges'){"
    "let list=[];"
    "for(const it of input.items){list=D.upsertActive(list,D.makeBadgeItem(it.n,it.now));}"
    "out.badges=D.buildBadges(list,resolver(input.apps));}\n"
    "else if(input.op==='agg'){"
    "out.agg=D.aggregateStackBadge(input.badges,input.keys);"
    "out.none=D.aggregateStackBadge(input.badges,[]);"
    "out.missing=D.aggregateStackBadge(input.badges,['ghost']);"
    "out.one=D.badgeForApp(input.badges,'firefox');"
    "out.ghost=D.badgeForApp(input.badges,'ghost');}\n"
    "else if(input.op==='idsForApp'){"
    "let list=[];"
    "for(const it of input.items){list=D.upsertActive(list,D.makeBadgeItem(it.n,it.now));}"
    "out.ids=D.activeIdsForApp(list,'firefox',resolver(input.apps));"
    "out.none=D.activeIdsForApp(list,'ghost',resolver(input.apps));}\n"
    "else if(input.op==='expired'){"
    "let list=[];"
    "for(const it of input.items){list=D.upsertActive(list,D.makeBadgeItem(it.n,it.now));}"
    "out.expired=D.expiredIds(list,input.now);}\n"
    "console.log(JSON.stringify(out));\n"
)


def run_node(payload, lib=BADGES_JS):
    p = subprocess.run(["node", "-e", DRIVER, lib, json.dumps(payload)],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


# Realistic ApplicationService app objects (scan_apps.py output shape).
FIREFOX_APP = {"id": "firefox", "startupWMClass": "firefox", "icon": "firefox",
               "name": "Firefox"}
DOLPHIN_APP = {"id": "org.kde.dolphin", "startupWMClass": "dolphin",
               "icon": "org.kde.dolphin", "name": "Dolphin"}
APPS = {"firefox": FIREFOX_APP, "Firefox": FIREFOX_APP,
        "org.kde.dolphin": DOLPHIN_APP, "dolphin": DOLPHIN_APP}


def notif(id, app="Firefox", icon="firefox", urgency=1, hints=None,
          desktop_entry="", expire=0, transient=False):
    return {"id": id, "appName": app, "appIcon": icon, "summary": "S" + str(id),
            "body": "B", "urgency": urgency, "actions": [],
            "hints": hints if hints is not None else {},
            "desktopEntry": desktop_entry, "expireTimeout": expire,
            "transient": transient}


class TestBadgeHelpersPure(unittest.TestCase):
    """Pure NotificationBadges.js helpers under node (no QML/KWin/D-Bus)."""

    def test_toarray_handles_qvariant_sequences(self):
        """Qt marshals signal-hopped arrays as sequence objects."""
        r = run_node({"op": "toArraySeq"})
        self.assertEqual(r["seq"], ["a", "b"])
        self.assertTrue(r["isArray"])

    def test_normalize_progress(self):
        """freedesktop "value" hint: 0..1 doubles and 0..100 percent both
        normalize; anything else is no-progress (never guessed)."""
        r = run_node({"op": "progress", "cases": [
            {"value": 42}, {"value": 0.5}, {"value": 1}, {"value": 0},
            {"value": 150}, {"value": -3}, {"value": "x"}, {}, None,
            {"value": None},
        ]})
        self.assertEqual(r["values"], [0.42, 0.5, 1.0, 0.0, 1.0, 0.0,
                                       None, None, None, None])

    def test_make_badge_item_shape(self):
        r = run_node({"op": "item", "now": 1234,
                      "n": notif(7, urgency=2, hints={"value": 30},
                                 desktop_entry="firefox", expire=-1)})
        item = r["item"]
        self.assertEqual(item["id"], 7)
        self.assertEqual(item["appName"], "Firefox")
        self.assertEqual(item["appIcon"], "firefox")
        self.assertEqual(item["desktopEntry"], "firefox")
        self.assertEqual(item["summary"], "S7")
        self.assertEqual(item["body"], "B")
        self.assertEqual(item["urgency"], 2)
        self.assertEqual(item["actions"], [])
        self.assertFalse(item["transient"])
        self.assertEqual(item["expireTimeout"], -1)
        self.assertEqual(item["progress"], 0.3)
        self.assertEqual(item["timestamp"], 1234)
        self.assertIsNotNone(item["raw"])

    def test_match_candidates_skip_generic_icons_and_paths(self):
        r = run_node({"op": "match", "apps": APPS, "cases": [
            {"desktopEntry": "firefox", "appIcon": "whatever", "appName": "X"},
            {"desktopEntry": "", "appIcon": "/usr/share/icons/x.png", "appName": "Firefox"},
            {"desktopEntry": "", "appIcon": "dialog-information", "appName": "System"},
            {"desktopEntry": "", "appIcon": "org.kde.dolphin", "appName": "Weird"},
        ]})
        # desktop-entry hint wins; absolute paths and generic dialog icons
        # are never identity candidates.
        self.assertEqual(r["candidates"][0], ["firefox", "whatever", "x"])
        self.assertEqual(r["candidates"][1], ["firefox"])
        self.assertEqual(r["candidates"][2], ["system"])
        self.assertEqual(r["candidates"][3], ["org.kde.dolphin", "weird"])
        self.assertEqual(r["keys"], ["firefox", "firefox", "", "org.kde.dolphin"])
        # No resolver -> never match (no guessing).
        self.assertEqual(r["noFn"], "")

    def test_upsert_replaces_in_place(self):
        """freedesktop replaces_id semantics: a replacement updates the
        existing entry, it never adds a count."""
        r = run_node({"op": "upsert", "remove": 2, "items": [
            {"n": notif(1), "now": 100},
            {"n": notif(2), "now": 200},
            {"n": notif(1, hints={"value": 80}, urgency=2), "now": 300},
        ]})
        self.assertEqual(r["ids"], [2, 1])       # newest-first; replaced in place, not appended
        self.assertEqual(r["removed"], [1])      # removal by id

    def test_build_badges_counts_urgency_progress(self):
        r = run_node({"op": "badges", "apps": APPS, "items": [
            {"n": notif(1, urgency=2, hints={"value": 42}), "now": 100},
            {"n": notif(2, urgency=1), "now": 200},
            # Transient notifications never badge.
            {"n": notif(3, transient=True, urgency=2), "now": 300},
            # Unmatched notifications never badge.
            {"n": notif(4, app="Unknown", icon="dialog-warning",
                        hints={"value": 9}), "now": 400},
            # Dolphin via desktop-entry hint.
            {"n": notif(5, app="Dolphin", icon="org.kde.dolphin",
                        desktop_entry="org.kde.dolphin"), "now": 500},
        ]})
        self.assertEqual(r["badges"], {
            "firefox": {"count": 2, "critical": True, "progress": 0.42},
            "org.kde.dolphin": {"count": 1, "critical": False, "progress": None},
        })

    def test_build_badges_progress_latest_wins(self):
        r = run_node({"op": "badges", "apps": APPS, "items": [
            {"n": notif(1, hints={"value": 10}), "now": 100},
            {"n": notif(2, hints={"value": 70}), "now": 200},
            # Replacement of notification 1 is newer than notification 2.
            {"n": notif(1, hints={"value": 90}), "now": 300},
        ]})
        self.assertEqual(r["badges"]["firefox"],
                         {"count": 2, "critical": False, "progress": 0.9})

    def test_stack_aggregation(self):
        badges = {"firefox": {"count": 2, "critical": True, "progress": 0.4},
                  "org.kde.dolphin": {"count": 1, "critical": False,
                                      "progress": 0.1}}
        r = run_node({"op": "agg", "badges": badges,
                      "keys": ["firefox", "org.kde.dolphin", "ghost"]})
        # Counts sum, critical ORs; progress is deliberately NOT aggregated.
        self.assertEqual(r["agg"], {"count": 3, "critical": True, "progress": None})
        self.assertIsNone(r["none"])
        self.assertIsNone(r["missing"])
        self.assertEqual(r["one"], badges["firefox"])
        self.assertIsNone(r["ghost"])

    def test_active_ids_for_app(self):
        r = run_node({"op": "idsForApp", "apps": APPS, "items": [
            {"n": notif(1), "now": 100},
            {"n": notif(2, app="Dolphin", icon="org.kde.dolphin",
                        desktop_entry="org.kde.dolphin"), "now": 200},
            {"n": notif(3, transient=True), "now": 300},
        ]})
        self.assertEqual(r["ids"], [1])
        self.assertEqual(r["none"], [])

    def test_expired_ids_only_positive_timeouts(self):
        """-1 (never) and 0 (shell default: persist until attended) never
        expire; positive client timeouts do, boundary inclusive."""
        r = run_node({"op": "expired", "now": 5000, "items": [
            {"n": notif(1, expire=-1), "now": 0},
            {"n": notif(2, expire=0), "now": 0},
            {"n": notif(3, expire=2000), "now": 2500},
            {"n": notif(4, expire=6000), "now": 0},
        ]})
        self.assertEqual(r["expired"], [3])


class TestStaticContracts(unittest.TestCase):
    """Source contracts for the QML integration (no runtime)."""

    def test_notification_service_lifecycle_wiring(self):
        src = read(NOTIF_SERVICE)
        self.assertIn('import "NotificationBadges.js" as Badges', src)
        # Native server lifecycle: tracked notifications + close signals.
        self.assertIn("n.tracked = true", src)
        self.assertIn("n.closed.connect", src)
        self.assertIn("n.hintsChanged.connect", src)
        self.assertIn("n.urgencyChanged.connect", src)
        self.assertIn("n.expireTimeoutChanged.connect", src)
        # Server is the shell's own, gated on the notifications toggle.
        self.assertIn("active: ConfigService.notificationsEnabled", src)
        # Exact-state API for the dock.
        for fn in ("function dismissAppNotifications(appKey)",
                   "function badgeForApp(appKey)",
                   "function badgeForStack(memberAppKeys)",
                   "function closeNotification(id, mode)",
                   "function refreshActive(n)"):
            self.assertIn(fn, src, fn)
        # Toast dismissal keeps the notification active (badge persists).
        self.assertIn("function dismissToast(id, closeNotification = true)", src)
        # Client-supplied positive timeouts expire through the native path.
        self.assertIn("Badges.expiredIds", src)
        # Badge map recomputed from active set + live application list.
        self.assertIn("const _apps = ApplicationService.applications;", src)
        # Honest degradation: server off -> active set cleared.
        self.assertIn("function onNotificationsEnabledChanged()", src)

    def test_notification_card_distinguishes_user_dismissal(self):
        src = read(NOTIF_CARD)
        self.assertIn("signal dismissed(var id, bool byUser)", src)
        # Auto-timeout keeps the notification active (byUser false)...
        self.assertIn("root.dismissed(root.notification.id, false)", src)
        # ...while explicit dismissals close it (byUser true).
        self.assertEqual(src.count("root.dismissed(root.notification.id, true)"), 2)

    def test_toast_host_routes_by_user(self):
        src = read(TOAST_HOST)
        self.assertIn(
            "onDismissed: (id, byUser) => NotificationService.dismissToast(id, byUser)",
            src)

    def test_dock_item_badge_wiring(self):
        src = read(DOCK_ITEM_QML)
        self.assertIn("readonly property var badge:", src)
        # No server -> no badges (honest degradation).
        self.assertIn("if (!ConfigService.notificationsEnabled) return null;", src)
        # App and stack lookups through the service's exact-state map.
        self.assertIn("NotificationService.badgeForStack(keys)", src)
        self.assertIn("NotificationService.badgeForApp(", src)
        # Attention given: activation clears the app's notifications.
        self.assertEqual(src.count("root.attendToNotifications();"), 2)
        self.assertIn("NotificationService.dismissAppNotifications(", src)
        # Visuals: count badge, critical urgency dot, progress ring.
        self.assertIn("id: progressRing", src)
        self.assertIn("id: urgencyDot", src)
        self.assertIn("visible: root.badge !== null && root.badge.critical", src)
        self.assertIn("visible: root.badge !== null && root.badge.count > 0", src)
        # Notification badge outranks the DOCK-011 member-count badge.
        self.assertIn("!(root.badge !== null && root.badge.count > 0)", src)
        # Accessibility label carries the notification state.
        self.assertIn("notifications\")", src)

    def test_kwin_window_attention_is_scoped_out(self):
        """DOCK-009 scope record: the resident KWin event bridge does not
        forward demandsAttention, so window-attention indicators are
        blocked-on-bridge (see the backlog evidence note). This asserts the
        bridge really does not expose it — nobody may assume it does."""
        src = read(KWIN_BRIDGE_JS)
        self.assertNotIn("demandsAttention", src)

    def test_qml_lint(self):
        res = subprocess.run(
            ["qmllint", "modules/dock/DockItem.qml",
             "modules/notifications/NotificationCard.qml",
             "modules/notifications/ToastHost.qml",
             "services/notifications/NotificationService.qml"],
            cwd=REPO, capture_output=True, text=True)
        warnings = [ln for ln in (res.stdout + res.stderr).splitlines()
                    if "arning" in ln or "rror" in ln]
        self.assertEqual(warnings, [], "qmllint reported issues: " + "\n".join(warnings))


# ---------------------------------------------------------------------------
# Isolated headless runtime E2E (offscreen quickshell + private XDG dirs +
# private D-Bus session). Drives the shell's REAL notification server over
# org.freedesktop.Notifications; no KWin rig, no live session access.
# ---------------------------------------------------------------------------

PROBE_QML = """import QtQuick
import Quickshell
import "./services"

Scope {
    id: root
    // Phases: "live" (server on, real notifications over D-Bus) and
    // "disabled" (server off: honest no-badge degradation).
    property string phase: Quickshell.env("NB_PHASE") || "live"
    property string target: Quickshell.env("NB_TARGET") || "org.kde.dolphin"
    property int tries: 0
    property bool done: false
    property bool appsReady: false
    property bool attended: false
    property string lastSnap: ""

    function canonical(app) {
        return app && app.id ? String(app.id).toLowerCase().replace(/\\.desktop$/, "") : "";
    }

    function snap() {
        const act = [];
        const list = NotificationService.activeNotifications;
        for (let i = 0; i < list.length; i++) act.push(list[i].id);
        return {
            enabled: ConfigService.notificationsEnabled,
            active: act,
            badges: NotificationService.notificationBadges
        };
    }

    function log(marker, obj) {
        console.log(marker + ":" + JSON.stringify(obj));
    }

    Timer {
        interval: 200; running: true; repeat: true
        onTriggered: {
            if (root.done) return;
            if (root.phase === "disabled") {
                // Give the config file a moment to load, then report state.
                if (++root.tries < 10) return;
                root.log("NB-STATE", root.snap());
                root.done = true;
                Qt.exit(0);
                return;
            }
            if (!root.appsReady) {
                const app = ApplicationService.getAppById(root.target);
                if (app && app.id) {
                    root.appsReady = true;
                    root.log("NB-APPS", {
                        canonical: root.canonical(app),
                        count: ApplicationService.applications.length
                    });
                } else if (++root.tries > 150) {
                    root.log("NB-FAIL", {step: "apps-timeout", snap: root.snap()});
                    root.done = true;
                    Qt.exit(1);
                    return;
                } else {
                    return;
                }
            }
            // Snapshot first (the pre-attention badge state is part of the
            // evidence), then attend: the driver marks a notification with
            // the x-rush-attend hint; observing it dismisses the app's set.
            const s = JSON.stringify(root.snap());
            if (s !== root.lastSnap) {
                root.lastSnap = s;
                root.log("NB-STATE", root.snap());
            }
            // Simulate the ToastHost auto-dismiss (compressed to 2s here;
            // NotificationCard uses 5s): hiding a toast keeps non-transient
            // notifications active (badge persists) but expires transient
            // ones (freedesktop: never persisted after display).
            const now = Date.now();
            const toasts = NotificationService.activeToasts;
            for (let i = 0; i < toasts.length; i++) {
                if (toasts[i] && now - toasts[i].timestamp >= 2000) {
                    NotificationService.dismissToast(toasts[i].id, false);
                }
            }
            if (!root.attended) {
                const list = NotificationService.activeNotifications;
                for (let i = 0; i < list.length; i++) {
                    const it = list[i];
                    if (it && it.raw && it.raw.hints
                        && it.raw.hints["x-rush-attend"] === true) {
                        root.attended = true;
                        const key = root.canonical(ApplicationService.getAppById(root.target));
                        const dismissed = NotificationService.dismissAppNotifications(key);
                        root.log("NB-ATTENDED", {dismissed: dismissed, key: key});
                        break;
                    }
                }
            }
        }
    }

    Timer {
        interval: 45000; running: true; repeat: false
        onTriggered: {
            root.log("NB-FAIL", {step: "global-timeout", snap: root.snap()});
            Qt.exit(1);
        }
    }
}
"""

SEED_BAR = {
    # notificationsEnabled is a bar/module setting (bar_config.json); the
    # shell's notification server follows it, and so do the dock badges.
    "enabled": True, "notificationsEnabled": True,
}

# gdbus hint dictionaries for the E2E notifications. Hints arrive as
# literal single-quoted GVariant text inside a double-quoted bash argument;
# {de} is the desktop-entry value.
HINT_CRITICAL = "\"{{'urgency': <byte 2>, 'value': <int64 42>, 'desktop-entry': <{de}>}}\""
HINT_PROGRESS = "\"{{'urgency': <byte 1>, 'value': <int64 {value}>, 'desktop-entry': <{de}>}}\""
HINT_ATTEND = "\"{{'urgency': <byte 1>, 'desktop-entry': <{de}>, 'x-rush-attend': <true>}}\""
HINT_TRANSIENT = "\"{{'transient': <true>, 'desktop-entry': <{de}>}}\""


def gdbus_notify(replaces, hints, expire):
    return (
        "gdbus call --session --dest org.freedesktop.Notifications "
        "--object-path /org/freedesktop/Notifications "
        "--method org.freedesktop.Notifications.Notify -- "
        "'Dolphin' {replaces} 'org.kde.dolphin' 'E2E' 'Body' '[]' "
        "{hints} {expire} > /dev/null\n"
    ).format(replaces=replaces, hints=hints, expire=expire)


def gdbus_notify_capture(replaces, hints, expire, outfile):
    """Same as gdbus_notify but captures the reply for inspection."""
    return gdbus_notify(replaces, hints, expire).replace(
        "> /dev/null", "> " + outfile + " 2>&1")


def gdbus_close(nid):
    return (
        "gdbus call --session --dest org.freedesktop.Notifications "
        "--object-path /org/freedesktop/Notifications "
        "--method org.freedesktop.Notifications.CloseNotification {nid}"
        " > /dev/null 2>&1\n"
    ).format(nid=nid)


def gdbus_name_owner(outfile):
    return (
        "gdbus call --session --dest org.freedesktop.DBus "
        "--object-path /org/freedesktop/DBus "
        "--method org.freedesktop.DBus.GetNameOwner org.freedesktop.Notifications"
        " > {outfile} 2>&1\n"
    ).format(outfile=outfile)


class TestNotificationBadgesRuntimeE2E(unittest.TestCase):
    """Isolated quickshell runtime: real D-Bus notifications through the
    shell's own freedesktop notification server."""

    TARGET = "org.kde.dolphin"

    @classmethod
    def setUpClass(cls):
        if shutil.which("quickshell") is None or shutil.which("dbus-run-session") is None:
            raise unittest.SkipTest("quickshell or dbus-run-session not available")
        if not os.path.exists("/usr/share/applications/org.kde.dolphin.desktop"):
            raise unittest.SkipTest("org.kde.dolphin desktop entry not available")
        cls.testroot = tempfile.mkdtemp(prefix="qs-notifbadges-e2e-")
        cls.probe = os.path.join(REPO, "_test_dock_notification_badges_probe.qml")
        with open(cls.probe, "w") as f:
            f.write(PROBE_QML)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.probe):
            os.remove(cls.probe)
        if hasattr(cls, "testroot"):
            shutil.rmtree(cls.testroot, ignore_errors=True)

    def _run_probe(self, phase, config_home, extra_script=""):
        """Run quickshell in a private D-Bus session; extra_script runs
        inside the same session once the probe is up. Returns the probe
        log."""
        runtime_dir = os.path.join(self.testroot, "runtime-" + phase)
        os.makedirs(runtime_dir, mode=0o700, exist_ok=True)
        logfile = os.path.join(self.testroot, "qs-" + phase + ".log")
        script = os.path.join(self.testroot, "driver-" + phase + ".sh")
        with open(script, "w") as f:
            f.write(
                "#!/bin/bash\n"
                "rm -f {log}\n"
                "QT_QPA_PLATFORM=offscreen XDG_RUNTIME_DIR={rt} "
                "XDG_CONFIG_HOME={cfg} NB_PHASE={ph} NB_TARGET={tg} "
                "quickshell -p {probe} --no-duplicate > {log} 2>&1 &\n"
                "QSPID=$!\n".format(log=logfile, rt=runtime_dir, cfg=config_home,
                                    ph=phase, tg=self.TARGET, probe=self.probe)
                + extra_script
                + "\nkill $QSPID 2>/dev/null\n"
                "for i in $(seq 1 20); do kill -0 $QSPID 2>/dev/null || break; sleep 0.3; done\n"
                "kill -9 $QSPID 2>/dev/null\nwait $QSPID 2>/dev/null\nexit 0\n")
        os.chmod(script, 0o755)
        env = dict(os.environ)
        env.pop("WAYLAND_DISPLAY", None)
        env.pop("DISPLAY", None)
        subprocess.run(["dbus-run-session", "--", script], cwd=REPO, env=env,
                       capture_output=True, text=True, timeout=180)
        with open(logfile, errors="replace") as f:
            return f.read()

    def _seed(self, config_home, notifications_enabled):
        cfgdir = os.path.join(config_home, "quickshell-kde")
        os.makedirs(cfgdir, exist_ok=True)
        seed = dict(SEED_BAR)
        seed["notificationsEnabled"] = notifications_enabled
        with open(os.path.join(cfgdir, "bar_config.json"), "w") as f:
            json.dump(seed, f)

    def _states(self, log):
        """All NB-STATE snapshots in order."""
        out = []
        for ln in log.splitlines():
            if "NB-STATE:" in ln:
                raw = ln.split("NB-STATE:", 1)[1].strip()
                out.append(json.loads(raw))
        return out

    def _badge(self, state):
        return state["badges"].get(self.TARGET)

    def test_live_server_badge_lifecycle(self):
        config_home = os.path.join(self.testroot, "config-live")
        os.makedirs(config_home, exist_ok=True)
        self._seed(config_home, True)

        de = "'org.kde.dolphin'"
        logfile = os.path.join(self.testroot, "qs-live.log")
        ownerfile = os.path.join(self.testroot, "owner-live.txt")
        wait_apps = (
            "for i in $(seq 1 100); do grep -q NB-APPS " + logfile
            + " && break; sleep 0.3; done\n")
        wait_attend = (
            "for i in $(seq 1 60); do grep -q NB-ATTENDED " + logfile
            + " && break; sleep 0.3; done\n")
        driver = (
            # Wait for the probe to report a resolved application list.
            wait_apps
            + "sleep 1\n"
            # The shell's server must own the freedesktop notification name.
            + gdbus_name_owner(ownerfile)
            # 1) Critical notification with a 42% progress hint.
            + gdbus_notify(0, HINT_CRITICAL.format(de=de), "-1")
            + "sleep 1.5\n"
            # 2) Withdraw it from the client side (CloseNotification).
            + gdbus_close(1)
            + "sleep 1.5\n"
            # 3) Progress notification with a 2s client expiry...
            + gdbus_notify(0, HINT_PROGRESS.format(de=de, value=30), "2000")
            + "sleep 1\n"
            # 4) ...replaced in place (same id) with 90%.
            + gdbus_notify(2, HINT_PROGRESS.format(de=de, value=90), "2000")
            + "sleep 4.5\n"
            # 5) Plain notification carrying the attend marker, plus a
            #    transient one that must never badge.
            + gdbus_notify(0, HINT_ATTEND.format(de=de), "-1")
            + "sleep 1\n"
            + gdbus_notify(0, HINT_TRANSIENT.format(de=de), "-1")
            + wait_attend
            + "sleep 4\n"
        )

        log = self._run_probe("live", config_home, driver)
        self.assertNotIn("NB-FAIL", log)
        self.assertIn("NB-APPS:", log)
        with open(ownerfile) as f:
            self.assertIn(":1.", f.read())  # server owns the bus name

        states = self._states(log)
        self.assertTrue(states, log)
        # Every snapshot comes from the enabled server.
        for s in states:
            self.assertTrue(s["enabled"])

        def find(pred, start=0):
            for i in range(start, len(states)):
                if pred(states[i]):
                    return i
            return -1

        # 1) Critical + 42% progress badge from the first notification.
        i1 = find(lambda s: self._badge(s) == {"count": 1, "critical": True,
                                               "progress": 0.42})
        self.assertGreaterEqual(i1, 0, log)
        self.assertEqual(states[i1]["active"], [1])
        # 2) Client withdrawal clears the badge.
        i2 = find(lambda s: self._badge(s) is None, i1 + 1)
        self.assertGreaterEqual(i2, 0, log)
        self.assertEqual(states[i2]["active"], [])
        # 3) Progress notification with 30%.
        i3 = find(lambda s: self._badge(s) == {"count": 1, "critical": False,
                                               "progress": 0.3}, i2 + 1)
        self.assertGreaterEqual(i3, 0, log)
        # 4) In-place replacement updates progress to 90% without a new count.
        i4 = find(lambda s: self._badge(s) == {"count": 1, "critical": False,
                                               "progress": 0.9}, i3 + 1)
        self.assertGreaterEqual(i4, 0, log)
        self.assertEqual(states[i4]["active"], [2])
        # 5) Client-supplied 2s expiry closes it (sweeper honors it).
        i5 = find(lambda s: self._badge(s) is None and s["active"] == [],
                  i4 + 1)
        self.assertGreaterEqual(i5, 0, log)
        # 6) Attend-marker notification badges once; the transient one never
        #    adds a count; attending dismisses the app's set.
        i6 = find(lambda s: self._badge(s) == {"count": 1, "critical": False,
                                               "progress": None}, i5 + 1)
        self.assertGreaterEqual(i6, 0, log)
        self.assertIn([3], [states[j]["active"] for j in range(i6, len(states))])
        self.assertIn("NB-ATTENDED:", log)
        attended = [ln for ln in log.splitlines() if "NB-ATTENDED:" in ln][-1]
        self.assertEqual(json.loads(attended.split("NB-ATTENDED:", 1)[1])["dismissed"], 1)
        # Final state: nothing active, no badges.
        last = states[-1]
        self.assertEqual(last["active"], [])
        self.assertIsNone(self._badge(last))

    def test_disabled_server_shows_no_badges(self):
        """notificationsEnabled false: no notification server, no badges
        (honest degradation — Plasma's daemon owns the data instead)."""
        config_home = os.path.join(self.testroot, "config-disabled")
        os.makedirs(config_home, exist_ok=True)
        self._seed(config_home, False)

        de = "'org.kde.dolphin'"
        ownerfile = os.path.join(self.testroot, "owner-disabled.txt")
        notifyfile = os.path.join(self.testroot, "notify-disabled.txt")
        driver = (
            "sleep 2\n"
            # No server: the freedesktop name has no owner and Notify never
            # gets a reply (D-Bus may attempt the installed plasma_waitforname
            # activation helper inside this private session; it never serves
            # the name, so the call just times out — no shell is touched).
            + gdbus_name_owner(ownerfile)
            + gdbus_notify_capture(0, HINT_CRITICAL.format(de=de), "-1",
                                   notifyfile)
            + "sleep 1\n"
        )

        log = self._run_probe("disabled", config_home, driver)
        self.assertNotIn("NB-FAIL", log)
        states = self._states(log)
        self.assertTrue(states, log)
        for s in states:
            self.assertFalse(s["enabled"])
            self.assertEqual(s["active"], [])
            self.assertEqual(s["badges"], {})
        # Locale-independent success markers must be absent: the name has no
        # owner and no notification was ever delivered to the shell.
        with open(ownerfile) as f:
            self.assertNotIn(":1.", f.read())  # no bus name owner
        with open(notifyfile) as f:
            self.assertNotIn("uint32", f.read())  # Notify got no reply


if __name__ == "__main__":
    unittest.main()
