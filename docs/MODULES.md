# Desktop Modules Specification

Modules in **quickshell-kde** are composable, self-contained widgets organized by `ModuleRegistry` and placeable into surface slots (`left`, `center`, `right`).

---

## Module Directory

| Module Identifier | Description | Contextual Trigger Action |
|---|---|---|
| `launcher` | Application menu button | Opens full-screen Spotlight application launcher (`LauncherWindow`) |
| `workspaces` | KWin virtual desktop indicator | Switches active virtual desktop; creates new desktops on `+` |
| `clock` | Digital clock & date | Opens KDE date & time settings (`kcm_clock`) |
| `media` | Active MPRIS media controller | Play/pause toggle; left-click opens anchored `MediaPopup` player |
| `tray` | Freedesktop SNI system tray | Displays StatusNotifierItem indicators; middle/right click menus |
| `network` | Network connectivity indicator | Shows Wi-Fi / Ethernet state and SSID |
| `battery` | Battery level & power status | Shows percentage and charging indicator |
| `audio` | PipeWire master sink volume | Scroll to adjust volume; left-click to toggle mute; right-click volume control |
| `power` | Session management trigger | Left-click opens anchored `PowerPopup` (Lock, Logout, Reboot, Shutdown) |

---

## Contextual Popup Anchoring

Flyouts and contextual popups (`DockMenu`, `MediaPopup`, `PowerPopup`) extend `AnchoredPopup` to dynamically attach to their parent `PanelWindow` and triggering widget. Popups adapt their anchor edge, gravity, and sliding adjustments to match the host surface's screen edge (`top`, `bottom`, `left`, `right`).
