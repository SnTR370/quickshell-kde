# Development Guide & Architecture

This document details the internal architecture, service abstractions, KWin integration, and development workflow for **quickshell-kde**.

---

## 1. Architectural Principles

### Compositor Isolation via Service Adapters
UI components in `modules/` MUST NOT directly invoke compositor-specific shell commands (`hyprctl`, `niri msg`, `qdbus`, etc.). All compositor interactions must be mediated by the singleton `KWinService` located in `services/kwin/KWinService.qml`.

This provides three key advantages:
1. **Maintainability**: When KDE / KWin DBus interfaces change or new Wayland protocols land, only the service layer needs modification.
2. **Testability**: UI modules can be inspected independently from specific compositor states.
3. **Safety**: No arbitrary shell command injection across UI files.

```
┌────────────────────────────────────────────────────────┐
│                      UI Modules                        │
│   (Bar, Dock, Launcher, OSD, Notifications, Media)     │
└───────────────────────────┬────────────────────────────┘
                            │ QML Property Bindings / Signals
┌───────────────────────────▼────────────────────────────┐
│                    Services Layer                      │
│ (KWinService, AudioService, MprisService, Theme, etc.) │
└─────────────┬────────────────────────────┬─────────────┘
              │ DBus / Protocols           │ Native QML / C++
┌─────────────▼─────────────┐   ┌──────────▼─────────────┐
│    KWin / KDE Plasma 6    │   │  Quickshell Native     │
│   (VirtualDesktops, etc.) │   │  (Pipewire, Wayland)   │
└───────────────────────────┘   └────────────────────────┘
```

### Decoupled Reactive State
All core services export reactive QML properties and signals. UI components declare data bindings rather than polling or invoking imperative fetch loops.

### Zero Root / Safe Storage
* The shell never modifies root filesystems (`/etc`, `fstab`, `/boot`).
* Configuration is loaded from `$XDG_CONFIG_HOME/quickshell-kde/` (falling back to built-in defaults in `config/`).
* User caches are kept in `$XDG_CACHE_HOME/quickshell-kde/`.

---

## 2. Module & Service Structure

### `services/`
* **`services/kwin/KWinService.qml`**:
  * Manages virtual desktop synchronization via `org.kde.KWin.VirtualDesktopManager`.
  * Handles dynamic monitor output detection via `Quickshell.screens` and `org.kde.KWin.activeOutputName`.
  * Exposes desktop switching (`setCurrentDesktop`, `nextDesktop`, `previousDesktop`), desktop creation, show-desktop toggling, and KDE settings launcher.
  * Employs an event debounce timer plus a lightweight 3000ms polling fallback to sync desktop changes made outside Quickshell (e.g. compositor shortcuts).
* **`services/kwin/WindowService.qml`**:
  * Tracks running windows, active window focus, and application groupings via KWin DBus (`org.kde.KWin /WindowsRunner`) and `Quickshell.Wayland.ToplevelManager`.
  * Exposes window activation (`activateWindow`, `activateApp`), closing (`closeWindow`), and running state queries (`isAppRunning`, `isAppActive`).
* **`services/brightness/BrightnessService.qml`**:
  * Tracks display brightness level and adjust ratios via KDE `org.kde.ScreenBrightness` D-Bus service with sysfs fallback.
  * Dispatches `osdPulse()` signal on brightness changes to trigger on-screen display overlay.
* **`services/audio/AudioService.qml`**:
  * Interacts with `Quickshell.Services.Pipewire` for default sink/source volume, mute state, and description.
  * Dispatches `osdPulse()` signal on volume changes to trigger the on-screen display overlay.
* **`services/mpris/MprisService.qml`**:
  * Tracks media players via `Quickshell.Services.Mpris`.
  * Selects the currently active/playing media session.
  * Exposes playback controls (`playPause`, `next`, `previous`, `seek`) and track metadata.
* **`services/applications/ApplicationService.qml`**:
  * Manages indexed applications parsed from XDG desktop directories by `scan_apps.py`.
  * Offers instant in-memory search and category filtering.
  * Launches applications safely via `gio launch` / `gtk-launch` or tokenized argument execution without invoking `sh -c`.
  * Uses `ConfigService` as the single source of truth for dock pinned applications (loaded dynamically from configuration defaults).
* **`services/notifications/NotificationService.qml`**:
  * Implements `Quickshell.Services.Notifications.NotificationServer` via conditional dynamic `Loader`.
  * Disabled by default (`notificationsEnabled: false`) so it does not attempt to register `org.freedesktop.Notifications` while KDE Plasma's notification daemon is active.
  * Activates cleanly when enabled for standalone KWin compositor sessions.
* **`services/network/NetworkService.qml`**:
  * 100% declarative and event-driven network state tracking via native `Quickshell.Networking` (Ethernet / Wi-Fi / Disconnected), active device name, hardware MAC address, Wi-Fi SSID, and signal strength (0–100%) with zero polling timers.
* **`services/battery/PowerService.qml`**:
  * Tracks battery charge level and AC power status via `Quickshell.Services.UPower` with sysfs fallback.
* **`services/theme/Theme.qml` & `ThemeService.qml`**:
  * Comprehensive design token system: spacing scale, radius scale, icon sizes, typography, and animation curves.
  * Real-time loading of theme presets (`breeze-dark`, `catppuccin-mocha`, `nord`, `tokyo-night`).
* **`services/config/ConfigService.qml`**:
  * Persistent JSON settings store for bar position, height, opacity, output filtering, dock autohide, and theme settings.
  * Loads default schemas from `config/` via `JsonStore.fallbackPath` without hardcoding user/app IDs in QML.

### `components/`
* `SvgIcon.qml`: Universal icon delegate supporting freedesktop system theme icons and SVG files.
* `IconButton.qml`: Animated button with hover magnification, ripple feedback, tooltips, and badge counts.
* `Surface.qml`: Background container with theme-driven background, border, and opacity.
* `Card.qml`: Structured container for lists and notifications.
* `Slider.qml`: Smooth slider with click, drag, and mouse wheel adjustments.
* `Tooltip.qml`: Lightweight hover tooltip.
* `Badge.qml`: Pill count badge.

### `modules/`
* `modules/bar/`: Multi-screen top/side bar with dynamic slot rendering, per-monitor output selection, and hardware blur.
* `modules/dock/`: Magnifying dock with real autohide, pointer edge triggers, running app indicators, unpinned running tasks, and right-click context menu.
* `modules/launcher/`: Spotlight application dashboard with category filtering, search input, and power management actions.
* `modules/notifications/`: Floating toast popup notifications.
* `modules/osd/`: HUD overlay for PipeWire volume and KDE display brightness adjustments.
* `modules/media/`: Extended popup player with album art and track details.
* `modules/settings/`: Comprehensive settings configuration window.

---

## 3. Running & Testing Safely

### Isolated Launch
Never install or copy development files directly into your primary `~/.config/quickshell/` directory.

Run the shell directly from the repository using:
```bash
quickshell -p ./shell.qml
```

### Checking Running Instances & Logs
```bash
# List active quickshell instances
quickshell list

# Terminate running quickshell instances
quickshell kill
```

### Static Analysis & Validation
```bash
# Run QML syntax check
qmllint shell.qml components/*.qml modules/**/*.qml services/**/*.qml
```

---

## 4. Milestone 2 Implementation & Milestone 3 Roadmap

### Milestone 2 Achievements
* **KWin Window & Task Management**: Reactive window tracking, active window highlighting, and task activation via `WindowService.qml`.
* **Complete Dock Experience**: Running app indicator pills, active focus highlight, unpinned running apps display, middle-click launch, right-click context menu, and true autohide with pointer edge triggers.
* **Display Brightness & OSD**: D-Bus brightness service integrated with dynamic on-screen HUD overlay.
* **Per-Monitor Output Selection**: Configurable per-module display filters (`all`, `primary`, or output names).
* **Hardware Blur Integration**: Native KWin Wayland blur protocol integration via `ext_background_effect_manager_v1` / `BackgroundEffect.blurRegion`.
* **Design System & Settings UX**: Centralized design tokens and structured in-shell settings dashboard.

### Milestone 3 Objectives
1. Layout presets (macOS floating dock, Windows/KDE classic taskbar, Minimalist top panel).
2. Wallpaper color extraction (Material You / pywal color palette generation).
3. Window preview tooltips on dock hover.
4. Comprehensive automated test suite and CI workflow.
