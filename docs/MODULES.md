# Desktop Modules Specification

Modules in **quickshell-kde** are composable, self-contained widgets organized by `ModuleRegistry` and placeable into surface slots (`left`, `center`, `right`).

---

## Module Directory

| Module Identifier | Description | Contextual Trigger Action |
|---|---|---|
| `launcher` | Application menu button | Opens full-screen Spotlight application launcher (`LauncherWindow`) |
| `workspaces` | KWin virtual desktop indicator | Switches active virtual desktop; wheel cycles desktops; `+` creates a new desktop |
| `clock` | Digital clock & date | Toggles KDE date & time settings (`kcm_clock`) with active state highlight |
| `media` | Active MPRIS media controller | Play/pause toggle; left-click opens anchored `MediaPopup` player |
| `tray` | Freedesktop SNI system tray | Displays StatusNotifierItem icons with `auto`/`always`/`hidden` policies, overflow chevron popup, and native SNI menus |
| `network` | Network connectivity indicator | Shows Wi-Fi / Ethernet state and SSID; left-click toggles `kcm_networkmanagement` |
| `battery` | Battery level & power status | Shows percentage and charging/full state; left-click toggles `kcm_powerdevilprofilesconfig` |
| `audio` | PipeWire master sink volume | Scroll to adjust volume; left-click opens anchored `AudioPopup`; right-click toggles KDE volume settings (`kcm_pulseaudio`) |
| `brightness` | Display backlight level indicator | Scroll to adjust brightness; left-click opens anchored `BrightnessPopup` with per-display sliders; right-click toggles KDE display settings (`kcm_kscreen`) |
| `power` | Session management trigger | Left-click opens anchored `PowerPopup` (Lock, Logout, Reboot, Shutdown) |

---

## Contextual Popup Anchoring

Flyouts and contextual popups (`AudioPopup`, `BrightnessPopup`, `WindowChooserPopup`, `DockMenu`, `MediaPopup`, `PowerPopup`) extend `AnchoredPopup` to dynamically attach to their parent `PanelWindow` and triggering widget. Popups adapt their anchor edge, gravity, and sliding adjustments to match the host surface's screen edge (`top`, `bottom`, `left`, `right`).
