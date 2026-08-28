# Configuration Guide

Configuration files are loaded from:
`~/.config/quickshell-kde/`

If user configuration files do not exist, the shell automatically uses defaults from `config/`.

---

## 1. Bar Configuration (`bar_config.json`)

```json
{
  "position": "top",
  "height": 44,
  "left": ["launcher", "workspaces"],
  "center": ["clock"],
  "right": ["media", "tray", "network", "battery", "audio", "power"],
  "opacity": 0.92,
  "notificationsEnabled": false
}
```

* `position`: `"top"`, `"bottom"`, `"left"`, or `"right"` (screen edge placement)
* `height`: Thickness in pixels (panel height in horizontal mode, panel width in vertical mode)
* `left`: List of module identifiers to render on the start side (`launcher`, `workspaces`, `clock`, `media`, `tray`, `network`, `battery`, `audio`, `power`)
* `center`: List of module identifiers to render in the center
* `right`: List of module identifiers to render on the end side
* `opacity`: Background opacity value between `0.0` and `1.0`
* `notificationsEnabled`: `false` (default; enables built-in notification server for standalone compositor sessions)

*Note: Per-monitor output filtering and KWin background blur integration are planned for Milestone 2.*

---

## 2. Dock Configuration (`dock_config.json`)

```json
{
  "enabled": true,
  "position": "bottom",
  "iconSize": 44,
  "pinned": [
    "org.kde.dolphin",
    "org.kde.konsole",
    "firefox",
    "code",
    "systemsettings"
  ]
}
```

*Note: Dock autohide is planned for Milestone 2.*

---

## 3. Theme Configuration (`theme_config.json`)

```json
{
  "activeTheme": "breeze-dark"
}
```

Available theme presets:
* `breeze-dark`
* `catppuccin-mocha`
* `nord`
* `tokyo-night`
