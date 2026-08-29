# Composable Shell UX Specification (v1.0)
**Milestone 3A Design & Architecture Reference**

---

## 1. Product Vision & Core Principles

The overarching vision of **quickshell-kde** is:
> **"Your desktop, your layout."**

Desktop environments should adapt to user workflows, not the other way around. The shell provides a modern, composable, and lightweight desktop interface for KDE Plasma 6 on Wayland, adhering to the following tenets:

1. **Independent, Optional Surfaces**: The Bar and Dock are completely independent surfaces. Users may run a Top Bar only, a Bottom Dock only, both simultaneously, or disable surfaces on specific displays.
2. **Floating by Default (Zero Strut Reservation)**: Floating surfaces are preferred for modern aesthetics. By default, surfaces do not reserve exclusive screen space (`reserveSpace: false`, `exclusiveZone: 0`), allowing maximized application windows to use 100% of the display area without being shrunk. Space reservation is an explicit opt-in.
3. **Decoupled Module Ownership**: No module is permanently owned by a single surface. Clock, Workspaces, Media, Audio, Battery, Network, Tray, and Power can exist in the Bar, in the Dock, or in future panel containers.
4. **Reusable Slot-Based Module Placement**: Surfaces organize content through reusable slot arrays (`left`, `center`, `right` or `start`, `center`, `end`).
5. **Contextual Popup Anchoring**: Contextual controls, flyouts, and menus MUST open anchored directly to their trigger element with proper Wayland edge alignment and collision adjustment, rather than popping up randomly centered or clipping inside parent panel boundaries.
6. **KDE-Native Infrastructure**: Leverage standard KDE Plasma 6 D-Bus interfaces (KWin, VirtualDesktopManager, PowerDevil, KCMShell6) rather than reimplementing or fighting compositor functionality.
7. **High Customizability without Cognitive Overload**: Sensible defaults provide an out-of-the-box polished desktop experience while exposing fine-grained configuration for power users.
8. **Truthful Capabilities**: Never fake unsupported KWin or Wayland protocols. If a compositor feature is unavailable, fail gracefully with clear fallback states.
9. **Configuration Isolation**: Never touch or corrupt user Plasma configurations or unrelated directories. Maintain configuration exclusively under `$XDG_CONFIG_HOME/quickshell-kde/`.

---

## 2. Composable Surface Model

Every desktop surface (Bar, Dock, future sidebars) is governed by a unified surface configuration model:

| Property | Type | Default (Bar) | Default (Dock) | Description |
|---|---|---|---|---|
| `enabled` | `boolean` | `true` | `true` | Enables or disables the surface globally or per-screen. |
| `floating` | `boolean` | `true` | `true` | If `true`, rendered as a detached floating island with rounded corners; if `false`, attached to the screen edge. |
| `edge` | `string` | `"top"` | `"bottom"` | Screen edge placement: `"top"`, `"bottom"`, `"left"`, `"right"`. |
| `edgeOffset` | `integer` | `8` | `8` | Margin distance (in pixels) from the monitor edge when `floating` is enabled. |
| `reserveSpace` | `boolean` | `false` | `false` | When `false`, `exclusiveZone = 0` (maximized windows fill screen). When `true`, reserves struts matching surface thickness. |
| `thickness` / `height` | `integer` | `44` | *(derived)* | Surface thickness along its perpendicular axis. |
| `iconSize` | `integer` | `24` | `44` | Primary icon size for launchers and item delegates. |
| `opacity` | `real` | `0.92` | `0.92` | Surface background opacity (0.1 to 1.0). |
| `blur` | `boolean` | `true` | `true` | KWin hardware background blur via Wayland layer-shell background effect. |
| `monitors` | `string \| array` | `"all"` | `"all"` | Target displays (`"all"` or array of monitor names, e.g. `["eDP-1", "DP-2"]`). |

### 2.1 Screen Space & Maximized Window Geometry
* **Default Mode (`reserveSpace: false`)**:
  * `exclusiveZone: 0`
  * Maximized windows take full screen dimensions ($W \times H$).
  * The floating Bar and Dock float on `WlrLayer.Top` over maximized windows.
* **Tiling / Reserved Mode (`reserveSpace: true`)**:
  * `exclusiveZone: thickness + (floating ? edgeOffset : 0)`
  * KWin shrinks the usable work area for maximized applications so they do not overlap the surface.

### 2.2 Four-Edge Geometry & Orientation Matrix

The surface dynamically configures its Wayland anchors, layout flow, and coordinate transforms based on `edge`:

```
                    TOP EDGE
       ┌────────────────────────────────┐
       │   [Left]   [Center]   [Right]  │  (Horizontal Layout)
       └────────────────────────────────┘
  ┌──┐                                    ┌──┐
  │T │                                    │T │
L │o │                                    │o │ R
E │p │                                    │p │ I
F │  │                                    │  │ G
T │C │                                    │C │ H
  │t │                                    │t │ T
E │r │                                    │r │
D │  │                                    │  │ E
G │B │                                    │B │ D
E │t │                                    │t │ G
  │m │                                    │m │ E
  └──┘                                    └──┘
       ┌────────────────────────────────┐
       │   [Left]   [Center]   [Right]  │  (Horizontal Layout)
       └────────────────────────────────┘
                   BOTTOM EDGE
```

* **Horizontal (`top` / `bottom`)**:
  * Anchors: Top or Bottom true; Left and Right false (for floating island) or true (for attached panel).
  * Flow: `RowLayout` with Left, Center, Right module groups.
  * Size: Fixed `implicitHeight` = `height`, dynamic `implicitWidth` fitted to content or island width.
* **Vertical (`left` / `right`)**:
  * Anchors: Left or Right true; Top and Bottom false or true.
  * Flow: `ColumnLayout` with Top, Center, Bottom module groups.
  * Size: Fixed `implicitWidth` = `height`, dynamic `implicitHeight`.

---

## 3. Reusable Module Placement Data Model

Modules are self-contained, stateless-presentation components that consume shared services.

### 3.1 Registered Module Identifiers
* `launcher`: Application search & launcher trigger button
* `workspaces`: KWin virtual desktop indicator & switcher
* `clock`: Time and date readout with timezone & settings trigger
* `media`: Active MPRIS player status & media control trigger
* `tray`: System tray / StatusNotifierItem host
* `network`: Network connection status & manager trigger
* `battery`: UPower battery level & power profiles
* `audio`: PipeWire master sink volume & mute toggle
* `brightness`: Display backlight level indicator
* `power`: Session power management (lock, logout, restart, poweroff)

### 3.2 Placement Configuration Schema
Surfaces define their module layout via slot arrays:
```json
{
  "left": ["launcher", "workspaces"],
  "center": ["clock"],
  "right": ["media", "tray", "network", "battery", "audio", "power"]
}
```
A central `ModuleRegistry` resolves module identifiers into QML components for any surface slot.

---

## 4. Contextual Popup Anchoring Infrastructure

To prevent popups from floating disconnected in the center of the screen or being clipped inside panel boundaries:

1. **Wayland Popup Architecture**:
   * Uses Quickshell's native `PopupWindow` attached to parent surfaces.
   * Leverages `anchor.window`, `anchor.item`, `anchor.edges`, `anchor.gravity`, and `anchor.adjustment`.
2. **Anchor Alignment Rules**:
   * When surface is at `edge: "top"`: Popup anchors to `Edges.Bottom`, `gravity: Edges.Bottom`.
   * When surface is at `edge: "bottom"`: Popup anchors to `Edges.Top`, `gravity: Edges.Top`.
   * When surface is at `edge: "left"`: Popup anchors to `Edges.Right`, `gravity: Edges.Right`.
   * When surface is at `edge: "right"`: Popup anchors to `Edges.Left`, `gravity: Edges.Left`.
3. **Collision & Adjustment**:
   * `adjustment: PopupAdjustment.Slide | PopupAdjustment.Flip` ensures popups near screen corners flip or slide to remain fully on-screen.
4. **Dismissal & Focus**:
   * Context menus and flyouts automatically close on click-outside (`onClosed`), item deactivation, or Escape key.

---

## 5. Compositor Layering & Screenshot Safety

KWin Wayland organizes surfaces into well-defined layers (`zwlr_layer_shell_v1`):

```
┌────────────────────────────────────────────────────────┐
│ WlrLayer.Overlay                                       │
│ - Full-screen Launcher Overlay                         │
│ - On-Screen Display HUD (OSDHost)                      │
│ - Toast Notifications (ToastHost)                      │
│ - Spectacle Interactive Region Screenshot Overlay      │
├────────────────────────────────────────────────────────┤
│ WlrLayer.Top                                           │
│ - Floating Top/Side Bar                                │
│ - Floating Bottom/Side Dock                            │
│ - Anchored Contextual Popups & Flyouts                 │
├────────────────────────────────────────────────────────┤
│ Normal Application Windows (Wayland Toplevels)         │
│ - Maximized Applications, Firefox, Konsole, etc.       │
├────────────────────────────────────────────────────────┤
│ WlrLayer.Bottom & WlrLayer.Background                  │
│ - Desktop Wallpaper & Canvas                           │
└────────────────────────────────────────────────────────┘
```

* **Screenshot Overlay Stacking**:
  * Bar and Dock live in `WlrLayer.Top`.
  * Spectacle and system screen grabbers operate on `WlrLayer.Overlay`.
  * As a result, screenshot selection UI cleanly overlays all shell panels without visual glitches or focus hijacking.
* **Fullscreen Application Handling**:
  * When an application goes fullscreen, KWin displays the fullscreen toplevel above `WlrLayer.Top`, cleanly hiding floating panels without manual visibility polling.

---

## 6. Configuration & Migration Specification

### 6.1 Unified Schema
Both `bar_config.json` and `dock_config.json` conform to the surface specification:

#### `bar_config.json`
```json
{
  "enabled": true,
  "floating": true,
  "edge": "top",
  "edgeOffset": 8,
  "reserveSpace": false,
  "height": 44,
  "opacity": 0.92,
  "blur": true,
  "monitors": "all",
  "notificationsEnabled": false,
  "left": ["launcher", "workspaces"],
  "center": ["clock"],
  "right": ["media", "tray", "network", "battery", "audio", "power"]
}
```

#### `dock_config.json`
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

### 6.2 Milestone 2 Migration Guarantees
The configuration engine automatically translates Milestone 2 files:
* `position` -> `edge` (e.g. `"position": "top"` -> `edge: "top"`).
* Missing `enabled` in Bar config -> defaults to `true`.
* Missing `floating` -> defaults to `true`.
* Missing `reserveSpace` -> defaults to `false`.
* Missing `edgeOffset` -> defaults to `8`.
* Legacy `monitors: "primary"` or `"default"` -> normalized to `"all"`.
