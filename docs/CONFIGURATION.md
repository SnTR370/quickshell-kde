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
  "monitors": "all",
  "left": ["launcher", "workspaces"],
  "center": ["clock"],
  "right": ["media", "tray", "network", "battery", "audio", "power"],
  "opacity": 0.92,
  "blur": true
}
```

* `position`: `"top"`, `"bottom"`, `"left"`, or `"right"`
* `height`: Pixel height (or width in vertical mode)
* `monitors`: `"all"` or specific monitor list

---

## 2. Dock Configuration (`dock_config.json`)

```json
{
  "enabled": true,
  "position": "bottom",
  "iconSize": 44,
  "autoHide": false,
  "pinned": [
    "org.kde.dolphin",
    "org.kde.konsole",
    "firefox",
    "code",
    "systemsettings"
  ]
}
```

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
