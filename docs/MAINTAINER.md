# Maintainer Guide & Showcase Assets

This guide contains operational standards for project maintainers, covering screenshot capture requirements, asset specifications, and GitHub repository configuration.

---

## 1. Screenshot Capture Checklist

Visual assets must be captured from a live KDE Plasma 6 / KWin Wayland session running the shell. Do not use synthetic mockups, cropped window borders, or simulated elements.

Save all images to `docs/screenshots/` as optimized PNGs at `1920x1080` (or `2560x1440` @ 100% or 125% scale):

| Filename | View Description | Key Visual Elements |
| :--- | :--- | :--- |
| `01-desktop-overview.png` | Desktop overview | Floating Top Bar (`height: 30`, `edgeOffset: 8`) and Floating Bottom Dock with KWin hardware blur, active running indicator pills, and an open application window layout. |
| `02-anchored-popups.png` | Anchored Bar flyouts | `AudioPopup` or `BrightnessPopup` anchored to the Top Bar showing per-device sliders, mute/brightness toggles, and single-instance KDE Settings shortcuts. |
| `03-tray-overflow.png` | System tray & overflow | `TrayModule` with chevron indicator expanded, displaying the overflow popup alongside an open native StatusNotifierItem context menu. |
| `04-dock-window-actions.png` | Dock context menu & window chooser | Right-click `DockMenu` on a multi-window application showing per-window **Focus**, **Move to `<Output>`**, and **Close** actions, alongside `WindowChooserPopup` (activation / new-window selector). |
| `05-launcher-spotlight.png` | Application launcher | Fullscreen `LauncherWindow` overlay with category filter chips and active search results. |
| `06-settings-themes.png` | Settings dashboard | `SettingsWindow` showing the Tray Visibility & Surface Configuration tabs, or a composite showcase comparing *Breeze Dark*, *Catppuccin Mocha*, *Nord*, and *Tokyo Night*. |

---

## 2. GitHub Repository Metadata

Maintainers should configure the following repository settings on GitHub:

* **About Description**:
  ```text
  Composable, KDE-native desktop shell (Bar, Dock, Launcher, OSD & Popups) built with Quickshell (Qt6/QML) for KDE Plasma 6 and KWin Wayland.
  ```
* **Topics**:
  `quickshell`, `kde-plasma-6`, `kwin`, `wayland`, `qml`, `qt6`, `linux-desktop`, `desktop-shell`, `wayland-layer-shell`, `kde`
* **Social Preview Image (`1280x640` PNG)**:
  Dark background (`#181825`) featuring the floating Top Bar and Bottom Dock over a blurred KDE Plasma 6 desktop canvas, with clear typographic branding:
  **quickshell-kde — Composable Quickshell UX for KDE Plasma 6 & KWin Wayland**.
