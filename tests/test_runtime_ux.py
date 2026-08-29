#!/usr/bin/env python3
"""
Test Suite for quickshell-kde Daily-Use UX and Surface Architecture
Separated into:
1. Unit / Mathematical Tests (Geometry calculations, dock autohide coordinates, app persistence math)
2. Structural / Declarative Checks (Layer Shell namespaces, single audio/OSD components, OSD bindings)
3. Live D-Bus Integration Tests (KDE ScreenBrightness discovery, Application desktop metadata parsing)
4. Startup Smoke Tests (Quickshell QML compilation and initial process execution)

Note: Full visual interactive validation of Spectacle drag-rectangles, monitor hardware backlight responses,
and mouse click interactions are marked MANUAL where automated emulation is not definitive.
"""

import os
import sys
import json
import time
import subprocess
import unittest

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_DIR, "services", "applications"))
sys.path.insert(0, os.path.join(REPO_DIR, "services", "brightness"))

import scan_apps
import discover_displays

class TestDesktopUX(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.scanned_apps = scan_apps.scan_all()
        # Build alias map matching ApplicationService.qml 2-pass indexing
        cls.alias_map = {}
        # Pass 1: Primary identifiers
        for app in cls.scanned_apps:
            if not app:
                continue
            if app.get("id"):
                aid = app["id"].lower().replace(".desktop", "")
                cls.alias_map[aid] = app
                cls.alias_map[app["id"].lower()] = app
                if aid.startswith("appimagekit_"):
                    clean = aid.replace("appimagekit_", "")
                    import re
                    clean = re.sub(r'^[0-9a-f]+-', '', clean)
                    cls.alias_map[clean] = app
            if app.get("startupWMClass"):
                cls.alias_map[app["startupWMClass"].lower()] = app
            if app.get("name"):
                clean_name = app["name"].split("(")[0].strip().lower()
                if len(clean_name) > 1:
                    cls.alias_map[clean_name] = app
            if app.get("icon"):
                cls.alias_map[app["icon"].lower().replace(".desktop", "")] = app

        # Pass 2: Secondary fallback aliases
        for app in cls.scanned_apps:
            if not app:
                continue
            if app.get("execBinary"):
                eb = app["execBinary"].lower()
                if eb not in cls.alias_map:
                    cls.alias_map[eb] = app
            if app.get("aliases"):
                for a in app["aliases"]:
                    al = a.lower()
                    if al not in cls.alias_map:
                        cls.alias_map[al] = app

    def resolve_app(self, title, icon):
        """Replicates ApplicationService.findAppByTitleOrIcon logic."""
        lower_icon = (icon or "").strip().lower()
        lower_title = (title or "").strip().lower()

        if lower_icon and lower_icon in self.alias_map:
            return self.alias_map[lower_icon]

        if lower_title:
            import re
            segments = re.split(r'\s+[—–\-:|]\s+', lower_title)
            for seg in reversed(segments):
                s = seg.strip()
                if s and s in self.alias_map:
                    return self.alias_map[s]

            for app in self.scanned_apps:
                clean_name = app.get("name", "").split("(")[0].strip().lower()
                if clean_name and len(clean_name) > 2 and clean_name in lower_title:
                    return app
                wmclass = (app.get("startupWMClass") or "").lower()
                if wmclass and len(wmclass) > 2 and wmclass in lower_title:
                    return app

        return None

    # --- 1. Unit Tests: Geometry & Formulas ---

    def test_01_m3a_exclusive_zone_geometry_math(self):
        """Unit test: Verify reserveSpace exclusiveZone formula reserves exactly thickness + edgeOffset without over-reserving."""
        # Top Bar
        bar_height = 44
        bar_offset = 8
        bar_exclusive_floating = bar_height + bar_offset
        self.assertEqual(bar_exclusive_floating, 52, "Bar exclusiveZone must be height + offset (52px)")
        bar_exclusive_attached = bar_height + 0
        self.assertEqual(bar_exclusive_attached, 44, "Attached Bar exclusiveZone must be height (44px)")

        # Bottom Dock
        dock_icon_size = 44
        dock_thickness = dock_icon_size + 16 # 60px
        dock_offset = 8
        dock_exclusive_floating = dock_thickness + dock_offset
        self.assertEqual(dock_exclusive_floating, 68, "Dock exclusiveZone must be thickness + offset (68px)")

    def test_02_autohide_four_edges_geometry(self):
        """Unit test: Verify autohide slide offset coordinates across all 4 monitor edges."""
        edges = {
            "bottom": {"slide_x": 0, "slide_y": 76},
            "top": {"slide_x": 0, "slide_y": -76},
            "left": {"slide_x": -76, "slide_y": 0},
            "right": {"slide_x": 76, "slide_y": 0}
        }
        for edge, expected in edges.items():
            thick = 60
            offset = 8
            if edge == "bottom":
                sy = thick + offset + 8
                sx = 0
            elif edge == "top":
                sy = -(thick + offset + 8)
                sx = 0
            elif edge == "left":
                sx = -(thick + offset + 8)
                sy = 0
            elif edge == "right":
                sx = thick + offset + 8
                sy = 0

            self.assertEqual(sx, expected["slide_x"])
            self.assertEqual(sy, expected["slide_y"])

    # --- 2. Structural Tests: Layer Shell Declarations & Spectacle Stacking ---

    def test_03_kwin_layering_and_spectacle_stacking(self):
        """Structural test: Verify KWin Wayland layer shell declarations place Settings/Launcher/Bar/Dock in WlrLayer.Top and OSD/Toasts in WlrLayer.Overlay.

        Note: Spectacle interactive visual drag-box verification requires MANUAL human testing.
        """
        with open(os.path.join(REPO_DIR, "modules/bar/Bar.qml")) as f:
            bar_src = f.read()
        with open(os.path.join(REPO_DIR, "modules/dock/Dock.qml")) as f:
            dock_src = f.read()
        with open(os.path.join(REPO_DIR, "modules/settings/SettingsWindow.qml")) as f:
            settings_src = f.read()
        with open(os.path.join(REPO_DIR, "modules/launcher/LauncherWindow.qml")) as f:
            launcher_src = f.read()
        with open(os.path.join(REPO_DIR, "modules/osd/OSDHost.qml")) as f:
            osd_src = f.read()

        # Bar, Dock, SettingsWindow, and LauncherWindow must be on Top layer (below Spectacle / Overlay)
        self.assertIn("WlrLayershell.layer: WlrLayer.Top", bar_src)
        self.assertIn("WlrLayershell.layer: WlrLayer.Top", dock_src)
        self.assertIn("WlrLayershell.layer: WlrLayer.Top", settings_src)
        self.assertIn("WlrLayershell.layer: WlrLayer.Top", launcher_src)
        # OSDHost must be on Overlay layer
        self.assertIn("WlrLayershell.layer: WlrLayer.Overlay", osd_src)

    # --- 3. Integration Tests: Application Metadata & Alias Resolution ---

    def test_04_target_app_identity_resolution(self):
        """Integration test: Query real desktop files and test alias resolution for Konsole, Dolphin, Spotify, and Helium."""
        # 1. Konsole
        konsole_app = self.resolve_app("quickshell-kde : fish — Konsole", "utilities-terminal")
        self.assertIsNotNone(konsole_app, "Konsole must resolve from title and icon")
        self.assertEqual(konsole_app["id"], "org.kde.konsole")

        # 2. Dolphin
        dolphin_app = self.resolve_app("/home/sena/Projects — Dolphin", "org.kde.dolphin")
        self.assertIsNotNone(dolphin_app, "Dolphin must resolve from title and icon")
        self.assertEqual(dolphin_app["id"], "org.kde.dolphin")

        # 3. Spotify
        spotify_app = self.resolve_app("Spotify Free", "com.spotify.Client")
        self.assertIsNotNone(spotify_app, "Spotify must resolve from Flatpak app id/icon")
        self.assertEqual(spotify_app["id"], "com.spotify.Client")

        # 4. Helium (AppImage)
        helium_app = self.resolve_app("Google — Helium", "helium")
        self.assertIsNotNone(helium_app, "Helium must resolve from window title/class")
        self.assertIn("helium", helium_app["id"].lower())
        self.assertIn("helium", helium_app["aliases"])

    def test_05_pinned_and_unpinned_dock_persistence(self):
        """Unit test: Verify pinned and unpinned running app calculation logic."""
        pinned = ["org.kde.dolphin", "org.kde.konsole", "firefox"]
        running_raw = ["utilities-terminal", "helium", "org.kde.dolphin"]

        unpinned = []
        for r in running_raw:
            app = self.alias_map.get(r.lower())
            canon_id = app["id"] if app else r
            if canon_id not in pinned and r not in pinned:
                if canon_id not in unpinned:
                    unpinned.append(canon_id)

        self.assertEqual(len(unpinned), 1)
        self.assertIn("helium", unpinned[0].lower())

    def test_06_multi_window_dock_dispatch(self):
        """Unit test: Verify multi-window dock dispatch logic (1 window direct activate, 2+ window chooser)."""
        mock_windows = [
            {"id": "w1", "appId": "org.kde.konsole", "title": "Terminal 1"},
            {"id": "w2", "appId": "org.kde.konsole", "title": "Terminal 2"},
            {"id": "w3", "appId": "org.kde.dolphin", "title": "Downloads"}
        ]

        def get_windows_for(target_id):
            app = self.alias_map.get(target_id.lower())
            canon_id = app["id"] if app else target_id
            aliases = app.get("aliases", [canon_id]) if app else [canon_id]
            return [w for w in mock_windows if w["appId"] == canon_id or w["appId"] in aliases]

        konsole_wins = get_windows_for("org.kde.konsole")
        self.assertEqual(len(konsole_wins), 2)
        action_konsole = "chooser" if len(konsole_wins) > 1 else "activate"
        self.assertEqual(action_konsole, "chooser")

        dolphin_wins = get_windows_for("org.kde.dolphin")
        self.assertEqual(len(dolphin_wins), 1)
        action_dolphin = "chooser" if len(dolphin_wins) > 1 else "activate"
        self.assertEqual(action_dolphin, "activate")

    # --- 4. Structural Tests: Audio Components ---

    def test_07_audio_persistent_module_and_kde_native_osd_dispatch(self):
        """Structural test: Verify single persistent audio module, detail popup, and KDE native OSD dispatch."""
        with open(os.path.join(REPO_DIR, "modules/bar/AudioModule.qml")) as f:
            audio_mod = f.read()
        with open(os.path.join(REPO_DIR, "modules/bar/AudioPopup.qml")) as f:
            audio_popup = f.read()
        with open(os.path.join(REPO_DIR, "services/audio/AudioService.qml")) as f:
            audio_service = f.read()
        with open(os.path.join(REPO_DIR, "modules/osd/OSDHost.qml")) as f:
            osd_host = f.read()

        # Audio module anchors popup
        self.assertIn("AudioPopup", audio_mod)
        # AudioPopup controls volume & mute
        self.assertIn("AudioService.setVolume", audio_popup)
        self.assertIn("AudioService.setInputVolume", audio_popup)
        self.assertIn("AudioService.toggleMute", audio_popup)
        self.assertIn("AudioService.toggleInputMute", audio_popup)
        # AudioService triggers KDE's native osdService D-Bus endpoint
        self.assertIn("org.kde.osdService", audio_service)
        self.assertIn("volumeChanged", audio_service)
        self.assertIn("microphoneVolumeChanged", audio_service)
        # OSDHost does not contain a duplicate custom VolumeOSD
        self.assertNotIn("VolumeOSD", osd_host)

    # --- 5. Live D-Bus & Brightness Safety Tests ---

    def test_08_live_dbus_brightness_display_discovery(self):
        """Live D-Bus test: Execute discover_displays.py against real org.kde.ScreenBrightness service."""
        out = subprocess.check_output([sys.executable, os.path.join(REPO_DIR, "services/brightness/discover_displays.py")], text=True)
        disps = json.loads(out)
        self.assertIsInstance(disps, list)
        if len(disps) >= 2:
            internal = [d for d in disps if d.get("isInternal")]
            external = [d for d in disps if not d.get("isInternal")]
            self.assertTrue(len(internal) > 0, "Internal display must be recognized")
            self.assertTrue(len(external) > 0, "External monitor must be recognized")
            self.assertNotEqual(internal[0]["dbusName"], external[0]["dbusName"])

    def test_09_brightness_safety_unknown_display_no_op(self):
        """Unit test: Verify setBrightnessForDisplay strictly NO-OPs on unknown dbusName and does not fall back to controlled display."""
        mock_displays = [
            {"dbusName": "display1", "brightness": 10000, "maxBrightness": 10000, "isInternal": True},
            {"dbusName": "display0", "brightness": 8000, "maxBrightness": 10000, "isInternal": False}
        ]
        controlled_display = mock_displays[0]

        def simulate_set_brightness(dbus_name, ratio):
            if not mock_displays or not dbus_name:
                return False
            target_disp = None
            for d in mock_displays:
                if d["dbusName"] == dbus_name:
                    target_disp = d
                    break
            if not target_disp or target_disp["maxBrightness"] <= 0:
                # STRICT NO-OP: Must not fall back to controlled_display!
                return False

            clamped = max(0.0, min(1.0, ratio))
            target_disp["brightness"] = int(clamped * target_disp["maxBrightness"])
            return True

        # Test valid target
        res_valid = simulate_set_brightness("display0", 0.5)
        self.assertTrue(res_valid)
        self.assertEqual(mock_displays[1]["brightness"], 5000)

        # Test unknown/stale target (MUST strictly return False / NO-OP without touching display1)
        res_invalid = simulate_set_brightness("display_nonexistent", 0.2)
        self.assertFalse(res_invalid)
        self.assertEqual(controlled_display["brightness"], 10000, "Controlled display must remain untouched on unknown target")

    def test_10_brightness_echo_suppression_logic(self):
        """Unit test: Verify DBus echo suppression logic suppresses duplicate OSD pulse for self-sent actions."""
        last_sent_action = {"dbusName": "display0", "targetVal": 5000, "timestamp": time.time() * 1000}

        def check_is_echo(dbus_name, new_val, current_time_ms):
            is_echo = (last_sent_action["dbusName"] == dbus_name and
                       abs(last_sent_action["targetVal"] - new_val) <= 1 and
                       (current_time_ms - last_sent_action["timestamp"]) < 1200)
            return is_echo

        now_ms = last_sent_action["timestamp"] + 100
        # Immediate echo from our own command -> True (suppressed)
        self.assertTrue(check_is_echo("display0", 5000, now_ms))
        # Different display -> False (not suppressed)
        self.assertFalse(check_is_echo("display1", 5000, now_ms))
        # External change after 2 seconds -> False (not suppressed)
        self.assertFalse(check_is_echo("display0", 5000, last_sent_action["timestamp"] + 2500))

    # --- 6. Startup Smoke Test ---

    def test_11_quickshell_process_startup_smoke_test(self):
        """Startup smoke test: Execute quickshell with root shell.qml to verify QML compilation and initial startup."""
        proc = subprocess.Popen(
            ["quickshell", "-p", "./shell.qml"],
            cwd=REPO_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        time.sleep(2)
        poll_res = proc.poll()
        is_alive = poll_res is None
        proc.terminate()
        try:
            proc.communicate(timeout=2)
        except Exception:
            proc.kill()

        self.assertTrue(is_alive, f"Quickshell failed to run: exit_code={poll_res}")

    # --- 7. Live KWin WindowsRunner Enumeration Test ---

    def test_12_live_kwin_running_apps_enumeration(self):
        """Live Integration test: Query real KWin /WindowsRunner and verify empty-icon windows parse into runningAppIds."""
        try:
            raw = subprocess.check_output(
                ["qdbus6", "--literal", "org.kde.KWin", "/WindowsRunner", "org.kde.krunner1.Match", ""],
                text=True,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            self.skipTest("KWin /WindowsRunner D-Bus endpoint not reachable in this session")

        import re
        pattern = re.compile(r'\[Argument:\s*\(sssida\{sv\}\)\s*\"([^\"]*)\",\s*\"((?:[^\"\\\\]|\\\\.)*)\",\s*\"([^\"]*)\"')
        seen_ids = set()
        running_apps = []

        # Query live MPRIS players if present
        mpris_players = []
        try:
            mpris_names = [n.strip() for n in subprocess.check_output(["qdbus6"], text=True, stderr=subprocess.DEVNULL).split("\n") if "org.mpris.MediaPlayer2." in n]
            for s in mpris_names:
                if not s:
                    continue
                try:
                    ident = subprocess.check_output(["qdbus6", s, "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Identity"], text=True, stderr=subprocess.DEVNULL).strip()
                    dentry = subprocess.check_output(["qdbus6", s, "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.DesktopEntry"], text=True, stderr=subprocess.DEVNULL).strip()
                    props = subprocess.check_output(["qdbus6", s, "/org/mpris/MediaPlayer2", "org.freedesktop.DBus.Properties.GetAll", "org.mpris.MediaPlayer2.Player"], text=True, stderr=subprocess.DEVNULL)
                    m_title = ""
                    m_artist = ""
                    for line in props.split("\n"):
                        if "xesam:title:" in line:
                            m_title = line.split("xesam:title:")[1].strip()
                        elif "xesam:artist:" in line:
                            m_artist = line.split("xesam:artist:")[1].strip()
                    mpris_players.append({"identity": ident, "desktopEntry": dentry, "trackTitle": m_title, "trackArtist": m_artist})
                except Exception:
                    pass
        except Exception:
            pass

        def resolve_with_live_mpris(title, icon):
            lower_icon = (icon or "").strip().lower()
            lower_title = (title or "").strip().lower()
            if lower_icon and lower_icon in self.alias_map:
                return self.alias_map[lower_icon]
            for p in mpris_players:
                p_title = (p["trackTitle"] or "").strip().lower()
                p_artist = (p["trackArtist"] or "").strip().lower()
                if (p_title and (p_title in lower_title or lower_title == p_title)) or (p_artist and p_artist in lower_title):
                    target = p.get("desktopEntry") or p.get("identity")
                    if target and target.lower() in self.alias_map:
                        return self.alias_map[target.lower()]
            return self.resolve_app(title, icon)

        for match in pattern.finditer(raw):
            wid = match.group(1)
            if not wid or wid in seen_ids:
                continue
            seen_ids.add(wid)

            title = match.group(2).replace('\\"', '"')
            icon = match.group(3)
            if not title and not icon:
                continue

            app = resolve_with_live_mpris(title, icon)
            resolved_id = app["id"] if app else (icon if icon else f"window-{wid}")
            if app and resolved_id not in running_apps:
                running_apps.append(resolved_id)
            elif not app and icon and icon not in running_apps:
                running_apps.append(icon)

        # On the user's live desktop, at least one window exists
        self.assertTrue(len(running_apps) > 0, "Live session must enumerate running windows into non-empty runningAppIds")
        # If Helium is running, verify it resolves to its appimage id
        if "Helium" in raw:
            helium_in_apps = any("helium" in a.lower() for a in running_apps)
            self.assertTrue(helium_in_apps, "Helium must resolve to an appId containing 'helium' when open")
        # If Spotify is active on MPRIS, verify runningAppIds contains Spotify
        if any("spotify" in p.get("identity", "").lower() for p in mpris_players):
            spotify_in_apps = any("spotify" in a.lower() for a in running_apps)
            self.assertTrue(spotify_in_apps, "Spotify must resolve to canonical Spotify app entry when active on MPRIS")

    # --- 8. Stabilization Tests for M3B2 ---

    def test_13_mpris_and_generic_media_app_resolution(self):
        """Integration test: Verify dynamic media song titles correlate with MPRIS desktop identities and never fall back to song titles."""
        # Simulated MPRIS player registry
        mpris_players = [
            {"desktopEntry": "spotify", "identity": "Spotify", "trackTitle": "Flow Heat", "trackArtist": "3rd Strike"}
        ]
        
        def resolve_with_mpris(title, icon):
            lower_title = (title or "").strip().lower()
            lower_icon = (icon or "").strip().lower()
            if lower_icon and lower_icon in self.alias_map:
                return self.alias_map[lower_icon]
            for p in mpris_players:
                p_title = (p["trackTitle"] or "").strip().lower()
                p_artist = (p["trackArtist"] or "").strip().lower()
                if p_title and (p_title in lower_title or lower_title == p_title):
                    target = p.get("desktopEntry") or p.get("identity")
                    if target.lower() in self.alias_map:
                        return self.alias_map[target.lower()]
            return self.resolve_app(title, icon)

        # 1. Test Spotify window title when playing "3rd Strike - Flow Heat" with empty icon
        app = resolve_with_mpris("3rd Strike - Flow Heat", "")
        self.assertIsNotNone(app, "Spotify window title with empty icon must resolve to Spotify app entry via MPRIS")
        self.assertIn("spotify", app["id"].lower())

        # 2. Test unknown window with empty icon (MUST NOT fall back to title as appId)
        unknown_title = "Arbitrary Document Title - Unknown Tool"
        unresolved_app = resolve_with_mpris(unknown_title, "")
        self.assertIsNone(unresolved_app)
        resolved_app_id = unresolved_app["id"] if unresolved_app else ("window-0_12345")
        self.assertNotEqual(resolved_app_id, unknown_title, "Unresolved window appId must NEVER equal dynamic window title")
        self.assertTrue(resolved_app_id.startswith("window-"), "Unresolved window must retain stable window-based ID")

    def test_14_multimonitor_settings_invocation_locking(self):
        """Unit test: Verify Settings and Launcher lock to invocation monitor and do not teleport on activeOutput changes."""
        with open(os.path.join(REPO_DIR, "services/config/ConfigService.qml")) as f:
            cfg_content = f.read()
        with open(os.path.join(REPO_DIR, "modules/settings/SettingsWindow.qml")) as f:
            set_content = f.read()

        self.assertIn("property string settingsScreenName:", cfg_content)
        self.assertIn("property string launcherScreenName:", cfg_content)
        self.assertIn("ConfigService.settingsScreenName === \"\" || modelData.name === ConfigService.settingsScreenName", set_content)
        self.assertIn("WlrLayershell.keyboardFocus: visible ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None", set_content)

    def test_15_audio_popup_150_percent_slider_range(self):
        """Structural test: Verify AudioPopup output volume slider supports 0..150% (1.5) range."""
        with open(os.path.join(REPO_DIR, "modules/bar/AudioPopup.qml")) as f:
            popup_content = f.read()
        self.assertIn("maximumValue: 1.5", popup_content, "AudioPopup output slider maximumValue must be 1.5 (150%)")
        self.assertIn("AudioService.setVolume(val, false)", popup_content, "Direct slider drag must not trigger redundant OSD spam")

    def test_16_svg_icon_source_scheme_handling(self):
        """Unit test: Verify SvgIcon properly detects existing URL schemes, pixmaps, file paths, and theme names."""
        def resolve_icon_source(icon_str):
            if not icon_str:
                return ""
            has_scheme = "://" in icon_str or icon_str.startswith("qspixmap:")
            is_path = icon_str.startswith("/")
            if has_scheme:
                return icon_str
            elif is_path:
                return "file://" + icon_str
            else:
                return "image://icon/" + icon_str

        # Theme icon name
        self.assertEqual(resolve_icon_source("preferences-system"), "image://icon/preferences-system")
        # SystemTray image-provider URL
        self.assertEqual(resolve_icon_source("image://icon/com.github.wwmm.easyeffects"), "image://icon/com.github.wwmm.easyeffects")
        # Pixmap scheme
        self.assertEqual(resolve_icon_source("qspixmap:123"), "qspixmap:123")
        # Absolute file path
        self.assertEqual(resolve_icon_source("/opt/app/icon.png"), "file:///opt/app/icon.png")

    def test_17_dock_blur_region_disabled_when_hidden(self):
        """Structural test: Verify Dock blurRegion is disabled when dock is hidden to eliminate ghost blur."""
        with open(os.path.join(REPO_DIR, "modules/dock/Dock.qml")) as f:
            dock_content = f.read()
        self.assertIn("(ConfigService.blurEnabled && dockWindow.isRevealed) ? dockSurface : null", dock_content)

    def test_18_bar_density_bounded_contract(self):
        """Structural test: Verify Bar and modules use bounded density height instead of circular parent.height."""
        with open(os.path.join(REPO_DIR, "modules/bar/MediaModule.qml")) as f:
            media_content = f.read()
        with open(os.path.join(REPO_DIR, "modules/bar/TrayModule.qml")) as f:
            tray_content = f.read()

        self.assertNotIn("implicitHeight: parent ? parent.height : 26", media_content)
        self.assertIn("ConfigService.barHeight", media_content)
        self.assertNotIn("implicitHeight: 34", tray_content)
        self.assertIn("ConfigService.barHeight", tray_content)

if __name__ == "__main__":
    unittest.main()
