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
  * Uses `ConfigService` as the single source of truth for dock pinned applications.
* **`services/notifications/NotificationService.qml`**:
  * Implements `Quickshell.Services.Notifications.NotificationServer`.
  * Maintains notification history and tracks active toast cards (when running in standalone session mode; yields cleanly to Plasma notification daemon when active).
* **`services/network/NetworkService.qml`**:
  * Event-driven network monitoring via native `Quickshell.Networking` (Ethernet / Wi-Fi / Disconnected), SSID, and signal strength.
* **`services/battery/PowerService.qml`**:
  * Tracks battery charge level and AC power status via `Quickshell.Services.UPower` with sysfs fallback.
* **`services/theme/Theme.qml` & `ThemeService.qml`**:
  * Reactive color palette, geometry tokens, and font specifications.
  * Real-time loading of theme presets (`breeze-dark`, `catppuccin-mocha`, `nord`, `tokyo-night`).
* **`services/config/ConfigService.qml`**:
  * Persistent JSON settings store for bar position, dock configuration, and UI toggles.

### `components/`
* `SvgIcon.qml`: Universal icon delegate supporting freedesktop system theme icons and SVG files.
* `IconButton.qml`: Animated button with hover magnification, ripple feedback, tooltips, and badge counts.
* `Surface.qml`: Background container with theme-driven background, border, and opacity.
* `Card.qml`: Structured container for lists and notifications.
* `Slider.qml`: Smooth slider with click, drag, and mouse wheel adjustments.
* `Tooltip.qml`: Lightweight hover tooltip.
* `Badge.qml`: Pill count badge.

### `modules/`
* `modules/bar/`: Multi-screen top/side bar with dynamic slot rendering for Workspaces, Launcher button, Clock, Media, Tray, Network, Battery, and Audio.
* `modules/dock/`: Magnifying dock adapting to top/bottom/left/right screen positions with pinned applications and running indicators.
* `modules/launcher/`: Spotlight application dashboard with category filtering, search input, and power management actions.
* `modules/notifications/`: Floating toast popup notifications.
* `modules/osd/`: HUD overlay for volume and brightness adjustments.
* `modules/media/`: Extended popup player with album art and track details.
* `modules/settings/`: In-shell settings configuration window.

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

## 4. Current Limitations & Milestone 2 Roadmap

### Current Limitations in Milestone 1
* **Window Taskbar / Foreign Toplevel in KWin**: Milestone 1 exposes pinned apps and basic window controls; full dynamic active window tracking and grouping under KWin Wayland will be expanded via enhanced foreign-toplevel tracking in Milestone 2.
* **Hardware Brightness Control**: Brightness control currently maps to OSD display hooks; direct DDC/sysfs backends will be added in Milestone 2.
* **KWin Blur Protocol**: KWin Wayland layer-shell background blur uses layer-shell backdrop heuristics. Full native shader blur integration is planned for Milestone 2.

### Milestone 2 Objectives
1. Add full KWin Window Taskbar module (live tasklist with minimized/active states).
2. Implement Brightness control service (`ddcutil` / `brightnessctl` integration).
3. Expand Settings UI with layout presets (KDE Traditional, macOS Floating, Minimalist Top).
4. Add customizable color palette creator / Material You wallpaper color extraction.
5. Create comprehensive automated test suite and continuous integration workflow.
