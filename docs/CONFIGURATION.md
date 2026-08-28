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
  "monitors": "all",
  "blur": true,
  "notificationsEnabled": false
}
```

* `position`: `"top"`, `"bottom"`, `"left"`, or `"right"` (screen edge placement)
* `height`: Thickness in pixels (panel height in horizontal mode, panel width in vertical mode)
* `left`: List of module identifiers to render on the start side (`launcher`, `workspaces`, `clock`, `media`, `tray`, `network`, `battery`, `audio`, `power`)
* `center`: List of module identifiers to render in the center
* `right`: List of module identifiers to render on the end side
* `opacity`: Background opacity value between `0.0` and `1.0`
* `monitors`: `"all"`, `"primary"`, or array of display names (e.g. `["eDP-1"]`)
* `blur`: `true` or `false` (enables KWin hardware background blur via `ext_background_effect_manager_v1`)
* `notificationsEnabled`: `false` (default; enables built-in notification server for standalone compositor sessions)

---

## 2. Dock Configuration (`dock_config.json`)

```json
{
  "enabled": true,
  "position": "bottom",
  "iconSize": 44,
  "autoHide": false,
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

* `enabled`: `true` or `false`
* `position`: `"bottom"`, `"top"`, `"left"`, or `"right"`
* `iconSize`: Pixel size of dock icons (36, 44, 52, 64)
* `autoHide`: `true` or `false` (smooth pointer edge reveal and slide-out)
* `monitors`: `"all"`, `"primary"`, or array of display names
* `pinned`: List of desktop application IDs displayed in the dock

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
