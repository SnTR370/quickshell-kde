# quickshell-kde

> **Composable, KDE-native desktop shell surfaces (Bar, Dock, Launcher, Popups, and OSD) built with [Quickshell](https://quickshell.outfoxxed.me) for KDE Plasma 6 and KWin Wayland.**
>
> *Created and maintained by [Sena](https://github.com/SnTR370).*

[English](README.md) · [Türkçe](README.tr.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: KDE Plasma 6 | KWin Wayland](https://img.shields.io/badge/Platform-KDE%20Plasma%206%20%7C%20KWin%20Wayland-1d99f3)](https://kde.org/plasma-desktop/)
[![Quickshell: 0.3.0+](https://img.shields.io/badge/Quickshell-0.3.0%2B-7c3aed)](https://quickshell.outfoxxed.me)
[![Qt6 / QML](https://img.shields.io/badge/Qt6-QML-41cd52)](https://www.qt.io/)

[**Overview**](#what-makes-this-kdekwin-native) · [**Features & Status**](#feature-highlights--verification-status) · [**Comparison**](#ecosystem-comparison) · [**Architecture**](#architecture-overview) · [**Quick Start**](#quick-start) · [**Configuration**](#configuration--customization) · [**Docs**](#documentation)

---

## Overview

**quickshell-kde** brings declarative QML/Quickshell customization—floating bars, slot-based modules, magnifying docks, anchored flyouts, and JSON-driven themes—directly to **KDE Plasma 6 on KWin Wayland**, without requiring you to migrate to a standalone tiling compositor such as Hyprland, Niri, or Sway.

### Branch Availability (`feat/composable-shell-ux` vs `main`)

| Branch | Milestone | Summary of Included Capabilities |
| :--- | :--- | :--- |
| **`feat/composable-shell-ux`** *(Active Development)* | **Milestone 3A** | Composable 4-edge Bar/Dock surfaces, zero-strut floating defaults, `ModuleRegistry` slot placement, `AnchoredPopup` flyouts (`AudioPopup`, `BrightnessPopup`, `MediaPopup`, `PowerPopup`, `WindowChooserPopup`), SNI system tray per-item visibility policies (`auto`/`always`/`hidden`) & overflow popup, deterministic KWin window identity & metadata cache, UUID-targeted KWin 6 window actions (activate, toggle minimize, graceful close, move to screen), and 20 automated unit/runtime regression tests. |
| **`main`** *(Baseline Release)* | **Milestone 2** | Initial KWin Wayland D-Bus integration, top/side bar, magnifying dock with autohide, Spotlight launcher, PipeWire audio, UPower battery, MPRIS media popup, display brightness OSD, 4 theme presets, and settings window. |

---

## What Makes This KDE/KWin-Native?

Most Quickshell, AGS, and Waybar desktop suites target `wlroots` or standalone tiling compositors (`hyprctl`, `niri msg`, `swaymsg`) and rely on compositor-specific protocols such as `zwlr_foreign_toplevel_manager_v1` or `wlr-data-control`. Running them inside a KDE Plasma Wayland session typically results in broken workspace widgets, missing taskbar state, or conflicting notification daemons.

**quickshell-kde** is engineered specifically around KDE Plasma 6 and KWin 6 interfaces:

* **KWin Virtual Desktops (`org.kde.KWin /VirtualDesktopManager`)**: Event-driven desktop switching, creation, removal, and wheel cycling synchronized via D-Bus signals with debounced fallback reconciliation.
* **KWin Window Discovery & Metadata Caching (`org.kde.KWin /WindowsRunner` & `getWindowInfo`)**: Tracks open Wayland windows by immutable KWin UUID, caches `desktopFile` and `resourceClass` metadata per UUID to avoid redundant D-Bus spawns, and resolves desktop entries via `StartupWMClass`, `Exec`, and reverse-DNS aliases without ever guessing application identity from window titles.
* **UUID-Exact Native Window Actions (`org.kde.kwin.Scripting`)**: Executes transient, self-unloading KWin 6 JavaScript workspace actions targeting exact window UUIDs for single-window minimize/restore toggling, multi-window active minimize, graceful client close (`win.closeWindow()`), and multi-monitor movement (`workspace.sendClientToScreen()`). Local state is never mutated optimistically before KWin confirms the change.
* **KDE Display Brightness & Native OSD Delegation (`org.kde.ScreenBrightness` & `org.kde.osdService`)**: Adjusts per-display hardware backlight via KDE PowerDevil D-Bus APIs (with read-only `/sys/class/backlight` fallback) and delegates master volume OSD feedback to Plasma's native `osdService` while providing a dedicated HUD for display brightness.
* **KDE System Settings Integration (`kcmshell6`)**: Bar modules (`clock`, `network`, `battery`, `audio`, `brightness`) launch or toggle single-instance KDE Control Modules (`kcm_clock`, `kcm_networkmanagement`, `kcm_powerdevilprofilesconfig`, `kcm_pulseaudio`, `kcm_kscreen`) with live active-process highlighting.
* **KWin Hardware Background Blur (`ext_background_effect_manager_v1`)**: Uses Quickshell's `BackgroundEffect.blurRegion` to request native KWin blur behind floating surfaces.
* **Coexistence with Plasma Daemons**: The built-in `org.freedesktop.Notifications` server is opt-in (`notificationsEnabled: false` by default) so it never collides with KDE Plasma's notification daemon unless explicitly enabled.

---

## Screenshots & Visual Showcase

> [!NOTE]
> Repository screenshots are pending capture on a live desktop session following Milestone 3A (`feat/composable-shell-ux`) UI stabilization. In accordance with project documentation standards, no simulated mockups or synthetic placeholders are used.
>
> Maintainers and contributors: see the [Screenshot Capture Checklist & Repository Metadata Guide](docs/MAINTAINER.md) for required views, resolutions, and GitHub repository configuration.

---

## Feature Highlights & Verification Status

Capabilities are categorized below by their verification level in the repository test suite (`tests/test_milestone_3a.py` and `tests/test_runtime_ux.py`):

| Subsystem | Capability | Branch | Status | Verification Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Composable Bar** | 4-edge placement (`top`/`bottom`/`left`/`right`), floating or attached, configurable height, opacity, blur, and `left`/`center`/`right` module slots via `ModuleRegistry` | `feat/composable-shell-ux` | **Implemented (Verified)** | Verified by `qmllint` & automated tests (`test_02`, `test_06`, `test_09`). |
| **Dynamic Dock** | 4-edge placement, hover magnification, true autohide (`revealDelay`/`hideDelay`), contiguous input mask, running indicators, and unpinned running apps | `feat/composable-shell-ux` | **Implemented (Verified)** | Geometry, autohide state machine, and hover stability verified (`test_04`, `tst_dock_autohide.qml`). |
| **KWin Window Identity** | Immutable UUID tracking, cached `getWindowInfo` D-Bus metadata, desktop entry matching (`StartupWMClass`/`Exec`/aliases), uninstalled pinned app filtering | `feat/composable-shell-ux` | **Implemented (Verified)** | Verified against title-spoofing, blank-title windows, and cache retry bounds (`test_11`, `test_12`). |
| **KWin Window Actions** | Per-window UUID activate, single/multi-window minimize toggle, graceful close (`closeWindow`), and multi-output move (`sendClientToScreen`) | `feat/composable-shell-ux` | **Implemented (Verified / GUI Partial)** | State safety, rejected close/move reconciliation, and KWin script generation verified (`test_13`); physical multi-monitor window move requires manual dual-display check. |
| **System Tray & Overflow** | Freedesktop SNI integration, per-item visibility policies (`auto`, `always`, `hidden`), `_status_icon_N` collision handling, overflow chevron & popup | `feat/composable-shell-ux` | **Implemented (Verified / GUI Partial)** | Policy persistence, status transitions, and ID collision transitions verified (`test_10`); live Wayland pointer grabs on third-party SNI menus require manual click verification. |
| **Contextual Popups** | `AnchoredPopup` flyouts (`AudioPopup`, `BrightnessPopup`, `MediaPopup`, `PowerPopup`, `DockMenu`, `WindowChooserPopup`) with exclusivity and Escape/outside-click dismissal | `feat/composable-shell-ux` | **Implemented (Verified)** | Anchor edges, popup exclusivity, and KWin layer stacking verified (`test_05`, `test_07`, `test_runtime_ux.py`). |
| **Audio & Brightness** | PipeWire sink/source controls + KDE native volume OSD delegation; `org.kde.ScreenBrightness` per-display backlight control + custom `BrightnessOSD` | `feat/composable-shell-ux` | **Implemented (Verified)** | Service state, sysfs fallback, and OSD triggers verified in runtime tests. |
| **Network & Battery** | Event-driven `Quickshell.Networking` status (Wi-Fi SSID/signal, Ethernet) and `UPower` + `/sys/class/power_supply` battery state (`Charging`/`Full`/`Discharging`) | `feat/composable-shell-ux` | **Implemented (Verified)** | Declarative bindings and battery `Full` vs `Charging` fallback verified. |
| **App Launcher** | Spotlight overlay (`LauncherWindow`) with non-blocking Python XDG indexer (`scan_apps.py`), category filtering, and safe tokenized launch | `main` & `feat/composable-shell-ux` | **Implemented (Verified)** | Indexed search, launch argument safety, and screen ownership verified. |
| **Theming & Settings UI** | Live theme switching (*Breeze Dark*, *Catppuccin Mocha*, *Nord*, *Tokyo Night*) and graphical `SettingsWindow` for surface, monitor, and tray policy management | `feat/composable-shell-ux` | **Implemented (Verified)** | Config persistence, migration from Milestone 2, and narrow/normal layout verified (`test_03`, `test_08`, `test_10`). |
| **Multi-Monitor Filtering** | Per-surface monitor selection (`"all"` or explicit output list) with lockout prevention when displays disconnect | `main` & `feat/composable-shell-ux` | **Code Complete (Manual Multi-Monitor Unverified)** | Filtering logic and fallback rules verified in synthetic multi-screen tests (`test_08`); physical multi-monitor hotplug is not verified in headless CI. |
| **Toast Notifications** | Built-in `org.freedesktop.Notifications` server and `ToastHost` overlay | `main` & `feat/composable-shell-ux` | **Opt-in (`false` by default)** | Disabled by default to avoid conflicting with KDE Plasma's native notification service. |
| **Layout Presets** | One-click ready-to-use layouts (*Everyday*, *Classic*, *Minimal*) in the Settings UI with an exact change preview before applying; Bar/Dock geometry, module slots and visibility only — pinned apps, displays, theme and other preferences are always preserved | `feat/beta-layout-presets` | **Implemented (Verified)** | Preset validation (surface/Settings lockout prevention), persistence, restart survival, preservation of unrelated settings, and the apply-before-load race verified (`tests/test_layout_presets.py`). |
| **Dynamic Wallpaper Palettes** | Automatic Material You / wallpaper color extraction | *Planned* | **Planned (Roadmap)** | Scheduled for Milestone 3B/3C. |

---

## Why Choose `quickshell-kde`?

1. **Stay on KDE Plasma 6 & KWin Wayland**: Keep KDE's display management, fractional scaling, HDR/color management, Polkit agent, KWallet, XDG portals, and hardware compatibility while replacing or supplementing standard panels with a modern Quickshell UI.
2. **Composable & Declarative**: Move modules (`launcher`, `workspaces`, `clock`, `media`, `tray`, `network`, `battery`, `audio`, `brightness`, `power`) across `left`, `center`, and `right` bar slots via JSON or the settings UI, and position Bar or Dock independently on any screen edge.
3. **Zero System Mutation**: Runs entirely in userspace (`quickshell -p ./shell.qml`). Never touches `/etc`, `fstab`, root privileges, or your existing `~/.config/plasma*` files.
4. **Clean Layer-Shell Discipline**: All bars, docks, launchers, and settings windows live in `WlrLayer.Top`, leaving `WlrLayer.Overlay` unobstructed for Spectacle rectangular screenshot selection and screen lockers.

---

## Ecosystem Comparison

> *Research & source verification date: **October 17, 2026**. The comparison below reflects publicly documented architectures and target compositors from each project's official repository and documentation.*

| Project | Primary Target Compositors | UI Toolkit / Stack | KDE Plasma 6 / KWin Wayland Support | Scope & Trade-offs |
| :--- | :--- | :--- | :--- | :--- |
| **quickshell-kde** *(This Project)* | **KDE Plasma 6 (KWin Wayland)** | Quickshell (Qt6 / QML) + Python XDG scanner + KWin D-Bus / JS scripts | **Purpose-Built**: Native KWin `/VirtualDesktopManager`, `/WindowsRunner`, `getWindowInfo`, `org.kde.ScreenBrightness`, `kcmshell6`, and KWin 6 scripting. | Focused on composable Bar, Dock, Launcher, Popups, OSD, and Settings inside a KDE Plasma session. Does not replace KDE's lock screen, Polkit agent, or display daemon. |
| [**KDE Plasma Native Panels**](https://invent.kde.org/plasma/plasma-workspace) (`plasma-workspace`) | **KDE Plasma 6 (KWin Wayland & X11)** | Qt6 / QML, Kirigami, C++ Plasma Frameworks (`plasmashell`) | **First-Class Reference**: Uses internal compositor protocols (`org_kde_plasma_surface`, `KWin::ThumbnailItem`) unavailable to external layer-shell clients. | Complete desktop environment with live window thumbnails, widgets (Plasmoids), and full Alt+Tab/Show Desktop panel persistence, but tied to `plasmashell` containment architecture. |
| [**Noctalia**](https://github.com/noctalia-dev/noctalia) ([Docs](https://docs.noctalia.dev)) | Hyprland, Niri, Sway, Labwc, MangoWC, Scroll, **KDE Plasma** | Custom Wayland + OpenGL ES shell (no Qt/GTK dependency in current mainline; legacy v4 used Quickshell) | **Documented Support (Non-First-Class)**: Officially documents KDE Plasma settings ([KDE Docs](https://docs.noctalia.dev/noctalia/compositor-settings/kde/)). Bars, dock, OSD, launcher, control center, workspaces (`org_kde_plasma_virtual_desktop`), taskbar (`KWin` scripting bridge), and system tray work via layer-shell; features requiring `wlroots` protocols (clipboard history, auto-paste, screenshots, lock screen backdrop, and night light) are unavailable on stock KWin. | Comprehensive standalone Wayland shell including bar, dock, launcher, lock screen, wallpaper daemon, control center, and desktop widgets. |
| [**DankMaterialShell**](https://github.com/AvengeMedia/DankMaterialShell) ([Docs](https://danklinux.com/docs)) | **Niri, Hyprland, Sway**, MangoWC, labwc, Scroll, Miracle WM | Quickshell (QtQuick/QML) + Go backend (`dms` CLI) | **Not Targeted**: Designed to replace `waybar`, `swaylock`, `swayidle`, `mako`, `fuzzel`, and `polkit` on standalone Wayland compositors rather than KWin/Plasma. | Full Material 3 desktop suite with Go system daemons, dynamic wallpaper theming (`matugen`), lock screen, and distro packaging. |
| [**Caelestia Shell**](https://github.com/caelestia-dots/shell) | **Hyprland** | Quickshell (`quickshell-git`) + C++/CMake QML plugins + `caelestia-cli` | **Not Targeted Upstream**: Relies on `hyprctl` IPC and Hyprland global shortcuts (separate third-party community ports exist for KDE). | Fluid morphing shell tightly integrated with the Caelestia Hyprland dotfiles, Cava audio visualizer, and Material 3 shapes. |
| [**HyprPanel**](https://github.com/Jas-SinghFSU/HyprPanel) | **Hyprland** | Astal / AGS (GTK3, GJS/TypeScript) | **Not Supported**: Explicitly coupled to Hyprland IPC sockets, workspaces, and client state. | Feature-rich Hyprland bar/panel; currently in maintenance mode as upstream development transitions to [Wayle](https://github.com/wayle-rs/wayle) (Rust/GTK4). |

---

## Key Advantages & Current Limitations

### Key Advantages
* **Compositor Isolation Layer**: UI modules in `modules/` never execute shell commands or `qdbus6` calls directly; all KWin interactions pass through `KWinService` and `WindowService`.
* **Non-Optimistic Window Action Safety**: Requesting window close or monitor move via the Dock never mutates local state prematurely. If an application shows an "Unsaved Changes" prompt or rejects a close request, the dock indicator remains accurate until KWin's `/WindowsRunner` enumeration confirms removal.
* **Resilient System Tray Identity**: Per-item tray policies (`auto`, `always`, `hidden`) normalize Chromium/Electron `_status_icon_N` suffixes when a single instance is present and automatically disambiguate when multiple instances of the same application register simultaneously, preserving saved user preferences across restarts.
* **Fast, Low-Overhead Window Scanning**: `WindowService` caches KWin `getWindowInfo` metadata per immutable window UUID so steady-state 1000ms scans spawn only a single `/WindowsRunner` query without per-window D-Bus process storms or unbounded failure retry loops.

### Current Limitations (Truthful Capabilities)
* **No Live Window Preview Thumbnails in Dock**: KWin Wayland does not expose an unprivileged public Wayland protocol for live window textures (`zwlr_screencopy_v1` is wlroots-specific, and PipeWire screencasting triggers interactive portal permission dialogs per window). Clicking an app with multiple open windows opens `WindowChooserPopup` displaying accurate window titles, icons, and activation / new-window actions instead of mocked thumbnails (per-window Close and Move to Screen actions are available in the `DockMenu` right-click context menu).
* **Floating Surface Behavior During `Alt+Tab` and `Show Desktop`**: When `reserveSpace: false` (`exclusiveZone: 0`), KWin's full-screen `TabBox` (`Alt+Tab`) and `ShowDesktop` (`Meta+D`) effects treat unreserved `WlrLayer.Top` layer-shell windows as floating surfaces and temporarily hide or occlude them. Moving panels to `WlrLayer.Overlay` was rejected because it would render panels over screen lockers and Spectacle screenshot selectors. Users who prefer persistent panel struts can enable `reserveSpace: true`.
* **Polling Fallback for Window Enumeration**: Because standard KWin Wayland restricts external clients from binding `zwlr_foreign_toplevel_manager_v1`, window list synchronization uses a 1000ms `/WindowsRunner` D-Bus poll (supplemented by immediate 180ms reconciliation after dock window actions).
* **Manual Multi-Monitor & Native Grab Verification**: While multi-monitor filtering and popup coordinate mapping are covered by automated QML unit tests, physical multi-monitor hardware hotplugging and real-mouse Wayland native menu grabs (`QsWindow` / SNI `DbusMenu`) must be verified interactively on a live desktop session.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                            UI Presentation                           │
│  modules/bar · modules/dock · modules/launcher · modules/settings    │
│  modules/media · modules/osd · modules/notifications                 │
│  components/ (AnchoredPopup, Surface, IconButton, Slider, Tooltip)   │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │ Declarative QML Bindings & Signals
┌──────────────────────────────────▼───────────────────────────────────┐
│                          Singleton Services                          │
│  KWinService · WindowService · ConfigService · ThemeService          │
│  ApplicationService · AudioService · BrightnessService · MprisService│
│  NetworkService · PowerService · NotificationService · ModuleRegistry│
└────────────────┬───────────────────────────────────┬─────────────────┘
                 │ D-Bus / KWin Scripting / Wayland  │ Local JSON / XDG
┌────────────────▼─────────────────┐ ┌───────────────▼─────────────────┐
│      KDE Plasma 6 / KWin 6       │ │    Quickshell & System APIs     │
│  /VirtualDesktopManager, /KWin,  │ │  PipeWire, UPower, Mpris, SNI,  │
│  /WindowsRunner, ScreenBrightness│ │  Quickshell.Networking, JSON    │
└──────────────────────────────────┘ └─────────────────────────────────┘
```

### Repository Structure

```text
quickshell-kde/
├── shell.qml                                # Root Quickshell entrypoint
├── components/                              # Reusable UI primitives
│   ├── AnchoredPopup.qml                    # Edge-aware Wayland PopupWindow base
│   ├── Badge.qml                            # Pill count/status indicator
│   ├── Card.qml                             # Structured content container
│   ├── IconButton.qml                       # Interactive button with hover/ripple/tooltip
│   ├── Slider.qml                           # Click/drag/wheel value slider
│   ├── Surface.qml                          # Theme-aware container with KWin blur support
│   ├── SvgIcon.qml                          # Freedesktop theme & SVG icon loader
│   ├── Tooltip.qml                          # PopupWindow-backed hover tooltip
│   └── qmldir
├── modules/                                 # Composable shell surfaces & popups
│   ├── bar/                                 # Bar surface, slot modules, and anchored popups
│   │   ├── Bar.qml
│   │   ├── AudioModule.qml & AudioPopup.qml
│   │   ├── BrightnessModule.qml & BrightnessPopup.qml
│   │   ├── ClockModule.qml, LauncherButton.qml, MediaModule.qml
│   │   ├── NetworkModule.qml, BatteryModule.qml, WorkspacesModule.qml
│   │   ├── PowerButton.qml & PowerPopup.qml
│   │   └── TrayModule.qml                   # SNI host with visibility policies & overflow
│   ├── dock/                                # Floating/attached Dock & window controls
│   │   ├── Dock.qml, DockItem.qml, DockSeparator.qml
│   │   ├── DockMenu.qml                     # Per-window Focus, Move to Screen, Close menu
│   │   └── WindowChooserPopup.qml           # Multi-window selector popup
│   ├── launcher/                            # Fullscreen Spotlight application launcher
│   ├── media/                               # Expanded MPRIS media player popup
│   ├── notifications/                       # Opt-in Freedesktop notification toast host
│   ├── osd/                                 # Display brightness on-screen HUD
│   └── settings/                            # Live graphical settings window
├── services/                                # Singleton business logic & compositor adapters
│   ├── applications/                        # XDG desktop entry scanner (scan_apps.py) & launcher
│   ├── audio/                               # PipeWire audio + KDE native OSD trigger
│   ├── battery/                             # UPower & sysfs power state service
│   ├── brightness/                          # KDE ScreenBrightness D-Bus + sysfs service
│   ├── config/                              # Persistent JSON config & schema migration
│   ├── core/                                # JsonStore, Log.js, and ModuleRegistry
│   ├── kwin/                                # KWinService, WindowService, and KWin JS scripts
│   ├── mpris/                               # Active media player controller
│   ├── network/                             # Declarative Quickshell.Networking service
│   ├── notifications/                       # Conditional NotificationServer loader
│   └── theme/                               # Design tokens & live theme engine
├── themes/                                  # Built-in JSON color themes
│   ├── breeze-dark.json
│   ├── catppuccin-mocha.json
│   ├── nord.json
│   └── tokyo-night.json
├── config/                                  # Default fallback configurations
│   ├── bar_config.json
│   ├── dock_config.json
│   └── theme_config.json
├── tests/                                   # Automated QML lint, unit, and runtime tests
│   ├── test_milestone_3a.py
│   ├── test_runtime_ux.py
│   └── tst_dock_autohide.qml
└── docs/                                    # Architecture and subsystem specifications
```

---

## Tested Platforms & Dependencies

### Verified Reference Environment
* **OS**: Arch Linux (`x86_64`, rolling)
* **Desktop / Compositor**: KDE Plasma `6.8.1` / KWin Wayland (`kwin_wayland 6.8.1`)
* **Shell Host**: Quickshell `0.3.2` (`0.3.2` required — the notification badge/urgency/progress indicators use the `Quickshell.Services.Notifications` API as of that release)
* **Qt / Python**: Qt6 (`qdbus6`, `qmllint`, `qmltestrunner`) / Python `3.14` (`>= 3.9` required)

### Runtime Dependencies

Audited against the actual process/D-Bus calls in `services/` and `modules/`
(P1-4). Everything the shell spawns at runtime:

| Component | Package / Binary (Arch Linux) | Role | Requirement |
| :--- | :--- | :--- | :--- |
| **Quickshell** | `quickshell` (`0.3.2`) | Wayland layer-shell QML host & native service bindings (system tray, notifications, networking) | **Required** |
| **KWin Wayland** | `kwin` / `plasma-workspace` (6.8+) | Compositor; `/VirtualDesktopManager`, `/WindowsRunner`, KWin Scripting D-Bus, `kglobalaccel` (embedded since KWin 6.8, used by Meta+1..9) | **Required** |
| **Qt6 D-Bus Tools** | `qt6-tools` (`qdbus6`) | D-Bus IPC for KWin workspace, window metadata, desktops, brightness and KCM dispatch | **Required** |
| **kdotool** | `kdotool` | Active-window query (`getactivewindow`) and KWin script actions (`kwinscript --inline`) | **Required** |
| **GLib** | `glib2` (`gio`) | Application launching (`gio launch`) and URI/file opening | **Required** |
| **Python 3** | `python` (`>= 3.9`, stdlib only) | XDG `.desktop` parser (`scan_apps.py`), brightness display discovery (`discover_displays.py`) | **Required** |
| **D-Bus** | `dbus` (`dbus-monitor`) | Brightness change signals (`org.kde.ScreenBrightness`) | **Required** |
| **WirePlumber** | `wireplumber` (`wpctl`) | Audio sink/source volume and mute control over PipeWire | **Required** |
| **coreutils / sed** | `coreutils`, `sed` (`cat`, `sh`, `sed`, `tr`, …) | JSON config/theme reads and the KWin script loader helpers | **Required** (implicit) |
| **systemd** | `systemd` (`loginctl`) | Session lock from the power menu | **Required** |
| **Fonts** | `noto-fonts`, a Hack font package | Theme typography defaults (`Noto Sans`, `Hack`) | **Recommended** |
| **KDE CLI Tools** | `kde-cli-tools` (`kcmshell6`), `systemsettings` | Opening KDE Control Modules and System Settings from the shell UI | **Recommended** |
| **UPower** | `upower` | Battery percentage and AC power state via `Quickshell.Services.UPower` | **Recommended** (Laptops) |
| **NetworkManager** | `networkmanager` | Network connectivity state via `Quickshell.Networking` | **Recommended** |
| **KWin Event Bridge** | compiled locally, see [`services/kwin/bridge/README.md`](services/kwin/bridge/README.md) | Optional compiled Qt6 QML plugin (event-driven Intellihide + bridge-based window state). Not shipped: build it with CMake + Qt6 Qml/DBus dev headers; without it the shell falls back to snapshot-based sync | **Optional** |

D-Bus services consumed (provided by the Plasma/PipeWire stack, no extra
packages): `org.kde.KWin`, `org.kde.kglobalaccel`, `org.kde.ScreenBrightness`
(KWin 6+), `org.mpris.MediaPlayer2.*` (running media players),
`org.kde.StatusNotifierItem` / `org.freedesktop.Notifications` (via
Quickshell's built-in tray and notification server).

### Development & Test Dependencies
* `qt6-declarative` (`qmllint`, `qmlformat`, `qmltestrunner`, `qml` runtime)
* `python3` (`unittest` runner — all suites in `tests/`)
* `dbus` (`dbus-run-session`) — private D-Bus sessions for isolated runtime tests
* `kwin` (`kwin_wayland --virtual`) — isolated compositor rigs (bridge E2E, Meta+1..9 E2E, full-shell startup smoke)
* `node` — pure-JS logic tests (`BridgeRecords.js`, `Intellihide.js`, …)
* `glib2` (`gdbus`) — notification badge E2E driver
* CMake >= 3.21, C++17 compiler, Qt6 Qml/DBus dev headers — building the optional KWin event bridge plugin

---

## Quick Start

Running **quickshell-kde** from a local checkout is completely isolated—it reads defaults from `./config/`, stores user overrides solely in `~/.config/quickshell-kde/`, and never alters your KDE Plasma configuration.

### 1. Clone and Select Branch

```bash
git clone https://github.com/SnTR370/quickshell-kde.git
cd quickshell-kde

# Recommended: switch to the active Milestone 3A composable shell branch
git checkout feat/composable-shell-ux

# Or stay on 'main' for the Milestone 2 baseline release
```

### 2. Run the Shell in Isolated Mode

```bash
quickshell -p ./shell.qml
```

To stop the running shell instance at any time:

```bash
quickshell kill
```

### 3. Run Linting & Automated Verification Tests

```bash
# Full regression suite. Every test is session-safe: runtime probes run
# offscreen inside private D-Bus sessions, and compositor tests spawn
# their own nested kwin_wayland --virtual — your active Plasma session is
# never touched. Live-session tests are opt-in (QS_KDE_LIVE_SESSION_TESTS=1).
python3 -m unittest discover -s tests -v

# Individual suites, e.g. the Milestone 3A suite (static contracts +
# qmllint + isolated full-shell startup smoke)
python3 -m unittest tests.test_milestone_3a -v
```

---

## Configuration & Customization

User configuration files are stored in `~/.config/quickshell-kde/` and fall back automatically to [`config/`](config/) if absent. Most settings can be adjusted live through the in-shell **Settings Dashboard** (accessible from the Application Launcher or Bar).

### Composable Bar (`~/.config/quickshell-kde/bar_config.json`)

```json
{
  "enabled": true,
  "floating": true,
  "edge": "top",
  "edgeOffset": 8,
  "reserveSpace": false,
  "height": 30,
  "left": ["launcher", "workspaces"],
  "center": ["clock"],
  "right": ["media", "tray", "network", "battery", "audio", "brightness", "power"],
  "opacity": 0.92,
  "monitors": "all",
  "blur": true,
  "notificationsEnabled": false,
  "trayPolicies": {
    "discord": "always",
    "nm-applet": "hidden"
  }
}
```

* **Slot Modules**: Place any registered module ID (`launcher`, `workspaces`, `clock`, `media`, `tray`, `network`, `battery`, `audio`, `brightness`, `power`) into `left`, `center`, or `right`.
* **Surface Geometry**: Set `edge` (`"top"`, `"bottom"`, `"left"`, `"right"`), `floating` (`true`/`false`), and `reserveSpace` (`false` for zero-strut full-screen apps, `true` to reserve exclusive screen space).
* **System Tray Policies (`trayPolicies`)**: Per-item visibility map supporting `"auto"` (follows SNI `Active`/`NeedsAttention` vs `Passive` status), `"always"` (always shown in bar), and `"hidden"` (moved to the tray overflow popup).

### Dynamic Dock (`~/.config/quickshell-kde/dock_config.json`)

```json
{
  "enabled": true,
  "floating": true,
  "edge": "bottom",
  "edgeOffset": 8,
  "reserveSpace": false,
  "iconSize": 44,
  "autoHide": false,
  "hideDelay": 350,
  "revealDelay": 120,
  "monitors": "all",
  "pinned": [
    "org.kde.dolphin",
    "org.kde.konsole",
    "firefox",
    "code",
    "systemsettings"
  ]
}
```

### Theme Presets (`~/.config/quickshell-kde/theme_config.json`)

Switch themes live in the Settings UI or via `activeTheme` in `theme_config.json`:
* `breeze-dark` *(Default — matches KDE Breeze Dark)*
* `catppuccin-mocha`
* `nord`
* `tokyo-night`

---

## Development Status & Roadmap

* [x] **Milestone 1 — KWin Foundation**: Decoupled `KWinService` adapter, virtual desktops, XDG app scanner, PipeWire audio, UPower battery, MPRIS media, and theme engine.
* [x] **Milestone 2 — Shell Experience (`main`)**: Dock autohide & magnification, display brightness service & OSD, per-monitor filtering, KWin hardware blur, and Settings GUI.
* [x] **Milestone 3A — Composable Shell UX (`feat/composable-shell-ux`)**:
  * [x] 4-edge composable Bar & Dock surface geometry with zero-strut floating defaults
  * [x] `ModuleRegistry` slot-based module placement & automatic Milestone 2 config migration
  * [x] `AnchoredPopup` contextual flyouts (`AudioPopup`, `BrightnessPopup`, `MediaPopup`, `PowerPopup`, `WindowChooserPopup`)
  * [x] System tray per-item visibility policies (`auto`/`always`/`hidden`), overflow popup, and `_status_icon_N` collision safety
  * [x] Deterministic KWin window identity resolution & cached `getWindowInfo` metadata
  * [x] UUID-targeted KWin 6 window actions (activate, toggle minimize, graceful close, move to screen) with non-optimistic state reconciliation
* [x] **Layout Presets (`feat/beta-layout-presets`)**:
  * [x] Three ready-to-use presets — *Everyday* (top Bar + bottom Dock), *Classic* (attached bottom taskbar panel, Dock off), *Minimal* (compact Bar + small auto-hiding Dock)
  * [x] Exact change preview before applying; pinned apps, monitor choices, theme and other preferences always preserved
  * [x] Validation preventing invalid layouts and surface/Settings lockout; Shell Settings entry in the Control Center
* [ ] **Milestone 3B / 3C — Planned**:
  * [ ] Dynamic wallpaper color extraction (Material You / `matugen` palette generation)
  * [ ] GitHub Actions CI workflow for automated `qmllint` and headless QML unit tests

---

## Documentation

* [Composable Shell UX Specification (v1.0)](docs/UX_SPEC_V1.md) — Milestone 3A surface model, 4-edge geometry, popup anchoring, and KWin layer stacking.
* [System Architecture](docs/ARCHITECTURE.md) — Model-View-Service layering and singleton data flow.
* [KWin Wayland Integration](docs/KWIN_INTEGRATION.md) — D-Bus interfaces, KWin 6 scripting, window thumbnail protocol findings, and layer-shell behavior.
* [Module Reference](docs/MODULES.md) — Slot module identifiers, interactions, and contextual popups.
* [Configuration Guide](docs/CONFIGURATION.md) — Full JSON schema for `bar_config.json`, `dock_config.json`, `theme_config.json`, and migration rules.
* [Development Guide](DEVELOPMENT.md) — Service contracts, coding standards, and verification workflows.
* [Maintainer & Showcase Guide](docs/MAINTAINER.md) — Screenshot capture checklist and GitHub repository metadata.

---

## Contributing, License & Attribution

* **Contributing**: Pull requests and bug reports are welcome. Please review [CONTRIBUTING.md](CONTRIBUTING.md) for architectural rules (strict KWin service isolation, zero root scripts, no hardcoded paths).
* **License**: Released under the [MIT License](LICENSE).
* **Attribution**: Upstream inspirations and architectural adaptations are documented with full copyright and license notices in [ATTRIBUTION.md](ATTRIBUTION.md).
