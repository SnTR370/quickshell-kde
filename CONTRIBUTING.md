# Contributing to quickshell-kde

Thank you for your interest in improving **quickshell-kde**! We welcome contributions that align with our design philosophy and quality standards.

---

## Code of Conduct & Development Philosophy

1. **KDE / KWin First**: This project is built specifically for KDE Plasma 6 / KWin Wayland. Avoid adding hard dependencies on other compositors (e.g. Hyprland, Sway, Niri).
2. **Layered Compositor Abstraction**: Never invoke compositor shell commands or DBus calls directly within UI modules. Place all compositor-specific logic inside `services/kwin/`.
3. **No Unsafe / Root Operations**: Never introduce scripts that modify `/etc`, `/boot`, `fstab`, or run with `sudo` / `pkexec`.
4. **No Hardcoded Machine Paths**: Never hardcode username paths, specific monitor names (`eDP-1`), or app IDs. Use dynamic discovery and XDG paths.
5. **Permissive Licensing Only**: Only integrate code with an explicit, compatible permissive open-source license (MIT, BSD, Apache 2.0). Always preserve copyright notices and document upstream origins in `ATTRIBUTION.md`.

---

## Development Workflow

1. Fork and clone the repository.
2. Create a feature branch: `git checkout -b feat/my-feature`.
3. Make small, focused commits with descriptive messages.
4. Test changes locally with `quickshell -p ./shell.qml`.
5. Run linting: `qmllint shell.qml components/*.qml modules/**/*.qml services/**/*.qml`.
6. Submit a Pull Request targeting the development branch.
