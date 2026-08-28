# Attribution & Upstream Heritage

This project builds upon architectural concepts and UI inspiration from the Quickshell ecosystem while maintaining a clean, modular foundation tailored specifically for **KDE Plasma 6** and **KWin Wayland**.

## Upstream References

### 1. `ekremx25/quickshell`
* **Repository**: [https://github.com/ekremx25/quickshell](https://github.com/ekremx25/quickshell)
* **Author / Copyright**: Copyright (c) 2026 ekremx25
* **License**: MIT License ([Upstream License](https://github.com/ekremx25/quickshell/blob/main/LICENSE))
* **Adapted Architectural Concepts**:
  * Visual styling patterns for panel bars, dock magnification, and OSD HUDs.
  * Theme color token design and contrast calculation helpers.
* **Modifications & KWin Porting**:
  * **Removed compositor lock-in**: Replaced all Hyprland (`hyprctl`), Niri (`niri msg`), and MangoWC (`mmsg`) commands with a clean, decoupled `KWinService` adapter.
  * **Removed unsafe scripts**: Completely discarded root-modifying scripts (`disk_fstab_helper.sh`), custom filter chain injecters (`eq_filter_chain.sh`), and compositor config modifiers.
  * **Native Quickshell APIs**: Leveraged Quickshell 0.3 native services (`Quickshell.Services.Pipewire`, `Quickshell.Services.Mpris`, `Quickshell.Services.SystemTray`, `Quickshell.Services.UPower`, `Quickshell.Services.Notifications`) instead of ad-hoc subprocess polling.
  * **Clean Modular Architecture**: Organized into strictly decoupled `components/`, `modules/`, `services/`, and `themes/` with `qmldir` singleton interfaces.

## License Compliance Notice

All reused code and design patterns from MIT-licensed repositories preserve original copyright notices in accordance with the terms of the MIT License.
