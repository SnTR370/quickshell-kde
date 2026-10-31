# Configuration Guide

Configuration files are loaded from:
`~/.config/quickshell-kde/`

If user configuration files do not exist, the shell automatically uses defaults from `config/`.

---

## 1. Bar Configuration (`bar_config.json`)

```json
{
  "enabled": true,
  "floating": true,
  "edge": "top",
  "position": "top",
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
  "trayPolicies": {}
}
```

* `enabled`: `true` or `false` (Bar can be independently enabled or disabled)
* `floating`: `true` or `false` (floating island vs attached panel)
* `edge` / `position`: `"top"`, `"bottom"`, `"left"`, or `"right"` (screen edge placement)
* `edgeOffset`: Distance in pixels from screen edge when floating (default: `8`)
* `reserveSpace`: `false` (default: zero exclusive zone so maximized apps fill screen) or `true` (reserves struts)
* `height`: Panel thickness in pixels (default: `30`)
* `left`: List of module identifiers for start slot (`launcher`, `workspaces`, `clock`, `media`, `tray`, `network`, `battery`, `audio`, `brightness`, `power`)
* `center`: List of module identifiers for center slot
* `right`: List of module identifiers for end slot
* `opacity`: Background opacity value between `0.1` and `1.0`
* `monitors`: `"all"` or array of display names (e.g. `["eDP-1"]`)
* `blur`: `true` or `false` (enables KWin hardware background blur via `ext_background_effect_manager_v1`)
* `notificationsEnabled`: `false` (default; enables built-in notification server for standalone compositor sessions)
* `trayPolicies`: Object mapping normalized or exact SNI item IDs to `"auto"`, `"always"`, or `"hidden"` visibility policies

---

## 2. Dock Configuration (`dock_config.json`)

```json
{
  "enabled": true,
  "floating": true,
  "edge": "bottom",
  "position": "bottom",
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

* `enabled`: `true` or `false` (Dock can be independently enabled or disabled)
* `floating`: `true` or `false` (floating island vs attached dock)
* `edge` / `position`: `"bottom"`, `"top"`, `"left"`, or `"right"`
* `edgeOffset`: Distance in pixels from screen edge when floating (default: `8`)
* `reserveSpace`: `false` (default: zero exclusive zone) or `true` (reserves struts when not autohidden)
* `iconSize`: Pixel size of dock icons (20 to 128 px)
* `autoHide`: `true` or `false` (smooth pointer edge reveal and slide-out)
* `hideDelay`: Inactivity delay in milliseconds before sliding out (default: `350`)
* `revealDelay`: Edge hotspot hover delay in milliseconds before sliding in (default: `120`)
* `monitors`: `"all"` or array of display names
* `pinned`: List of desktop application IDs displayed in the dock
* `monitorProfiles`: Per-display dock profile overrides (DOCK-012), e.g. `{"DP-1": {"edge": "left", "iconSize": 32}}`. Valid override keys: `edge`, `floating`, `edgeOffset` (0–64), `iconSize` (20–128), `autoHide`, `intellihide`. Missing or invalid overrides fall back to the global values; the section is optional and absent on first launch. Pinned applications, stacks and display selection stay global.

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

---

## 4. Milestone 2 to Milestone 3A Migration

The shell includes automatic backward compatibility:
* Legacy `position` fields are seamlessly mapped to `edge`.
* Missing `enabled`, `floating`, `reserveSpace`, and `edgeOffset` fields automatically receive their safe defaults (`enabled: true`, `floating: true`, `reserveSpace: false`, `edgeOffset: 8`).
* Legacy `"primary"` or `"default"` monitor strings are automatically converted to `"all"`.
