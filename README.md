# quickshell-kde

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-KDE%20Plasma%206%20%7C%20KWin%20Wayland-informational)](https://kde.org)
[![Quickshell](https://img.shields.io/badge/Quickshell-0.3.0%2B-purple)](https://quickshell.outfoxxed.me)

A modern, polished, modular desktop shell built for **KDE Plasma 6** and **KWin Wayland** users using [Quickshell](https://quickshell.outfoxxed.me).

Designed for Linux desktop enthusiasts who want a fluid, highly customizable, Wayland-native shell experience without giving up the stability, hardware compatibility, and multi-monitor management of KDE Plasma and KWin.

---

## Highlights

* **Pure KDE / KWin Wayland Architecture**: All compositor-specific functionality is isolated behind a clean `KWinService` adapter. No Hyprland, Niri, or Sway dependencies.
* **Modular Layered Design**: Separated cleanly into `components/`, `modules/`, `services/`, and `themes/` with reactive QML singleton exports.
* **Zero Root / Unsafe Scripts**: Strictly adheres to desktop security principles. No `/etc` modification, no `fstab` editing, no root privileges required.
* **Multi-Monitor First**: Dynamically discovers and adapts to multi-monitor configurations without hardcoding monitor names (`eDP-1`, `HDMI-A-1`, etc.).
* **Integrated Initial Modules**:
  * **Top / Side Bar**: Configurable layout (left/center/right slots), supports top, bottom, left, and right screen edges.
  * **Interactive Virtual Desktops**: Live desktop status, seamless switching, and scroll-to-cycle powered by KWin DBus.
  * **Application Launcher**: Fullscreen spotlight-style overlay with sub-millisecond search, category filtering, and session control buttons.
  * **Dynamic Dock**: macOS / Plasma-style dock with smooth hover magnification, pinned apps management, and app launching.
  * **Audio Mixer & OSD**: Native PipeWire audio volume slider, mute toggling, sink switcher, and animated volume overlay HUD.
  * **MPRIS Media Player**: Live playback status, album artwork, track information, and media controls for Spotify, browsers, VLC, etc.
  * **System Tray**: Freedesktop StatusNotifierItem integration with interactive DBus menus.
  * **Notifications Center**: Native Freedesktop notification server with floating toast popups and action callbacks.
  * **Live Theming Engine**: Switch between built-in themes (*Breeze Dark*, *Catppuccin Mocha*, *Nord*, *Tokyo Night*) with real-time UI updates.
  * **Settings Dashboard**: Graphical UI for live configuration of bar positions, themes, and compositor integration.

---

## Screenshots

> *(Screenshots placeholder — visual preview will be added in milestone 2)*

---

## System Requirements & Dependencies

### Runtime Dependencies

| Dependency | Purpose | Status |
| :--- | :--- | :--- |
| `quickshell` (>= 0.3.0) | Wayland QML shell host and service framework | Required |
| `plasma-workspace` / `kwin` | KDE Plasma 6 Wayland compositor | Required |
| `pipewire` / `pipewire-pulse` | Audio server for volume and sink management | Required |
| `upower` | Battery and power management | Recommended (Laptops) |
| `networkmanager` / `nmcli` | Network status and connection monitoring | Recommended |
| `python` (>= 3.9) | Fast non-blocking XDG desktop entry indexer | Required |
| `qdbus6` / `qt6-tools` | KWin DBus IPC tool for workspace/session control | Required |

### Development Dependencies

* `qmllint` (Qt6 QML linter)
* `qmlformat` (Qt6 QML formatter)
* `git`

---

## Safe Development & Testing

This project is completely isolated and will **never** overwrite or touch existing user configurations (`~/.config/quickshell/sena` or standard Plasma defaults).

To run and test the development shell safely:

```bash
# Clone the repository
git clone https://github.com/SnTR370/quickshell-kde.git
cd quickshell-kde

# Switch to development branch
git checkout feat/kwin-foundation

# Run the shell in isolated development mode
quickshell -p ./shell.qml
```

To stop the shell, press `Ctrl+C` in the terminal or run `quickshell kill`.

---

## Project Structure

```
quickshell-kde/
├── shell.qml                     # Main entrypoint
├── components/                   # Reusable UI primitives
│   ├── SvgIcon.qml               # Vector icon loader
│   ├── IconButton.qml            # Interactive button
│   ├── Surface.qml               # Theme-aware surface container
│   ├── Card.qml                  # Structured content card
│   ├── Slider.qml                # Volume/brightness slider
│   ├── Tooltip.qml               # Animated tooltip
│   ├── Badge.qml                 # Count/status badge
│   └── qmldir
├── modules/                      # Shell UI modules
│   ├── bar/                      # Top/Side Panel bar
│   ├── dock/                     # Floating centered Dock
│   ├── launcher/                 # Spotlight Application Launcher
│   ├── notifications/            # Toast notifications host
│   ├── osd/                      # Volume/Brightness HUD
│   ├── media/                    # Expanded MPRIS media popup
│   ├── systemtray/               # System tray popup
│   └── settings/                 # Graphical settings window
├── services/                     # Business logic and adapters
│   ├── kwin/                     # KWin Wayland DBus & session adapter
│   ├── audio/                    # PipeWire native audio service
│   ├── mpris/                    # MPRIS player service
│   ├── network/                  # NetworkManager status service
│   ├── battery/                  # UPower power & battery service
│   ├── applications/             # XDG desktop applications service
│   ├── notifications/            # Freedesktop notification service
│   ├── theme/                    # Theme & color palette manager
│   ├── config/                   # Configuration store & schema
│   ├── core/                     # JSON storage & structured logger
│   └── qmldir                    # Singleton exports
├── themes/                       # Theme JSON presets
│   ├── breeze-dark.json
│   ├── catppuccin-mocha.json
│   ├── nord.json
│   └── tokyo-night.json
├── config/                       # Default configuration files
├── docs/                         # Detailed architecture documentation
├── DEVELOPMENT.md                # Development guide & limitations
├── CONTRIBUTING.md               # Guidelines for contributors
├── ATTRIBUTION.md                # Upstream heritage & attribution
└── LICENSE                       # MIT License
```

---

## Documentation

* [Architecture & Data Flow](docs/ARCHITECTURE.md)
* [KWin Wayland Integration](docs/KWIN_INTEGRATION.md)
* [Module Reference](docs/MODULES.md)
* [Configuration Guide](docs/CONFIGURATION.md)
* [Development & Roadmap](DEVELOPMENT.md)

---

## License & Attribution

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.

Components and UI concepts adapted from upstream open-source projects are documented with full attribution in [ATTRIBUTION.md](ATTRIBUTION.md).
