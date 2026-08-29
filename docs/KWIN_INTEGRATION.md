# KWin Wayland Integration

## DBus Interfaces

**quickshell-kde** communicates with KWin Wayland using standard KDE Plasma 6 DBus interfaces.

### Virtual Desktop Manager
* **Service**: `org.kde.KWin`
* **Path**: `/VirtualDesktopManager`
* **Interface**: `org.kde.KWin.VirtualDesktopManager`
* **Methods**:
  * `createDesktop(uint position, QString name)`
  * `removeDesktop(QString id)`
  * `setDesktopName(QString id, QString name)`
* **Properties**:
  * `count` (`uint`): Number of active virtual desktops.
  * `current` (`QString`): Unique UUID of current desktop.
  * `desktops` (`a(uss)`): Array of `(index, id, name)` tuples.
* **Signals**:
  * `currentChanged(QString id)`
  * `countChanged(uint count)`
  * `desktopCreated(QString id, ...)`
  * `desktopRemoved(QString id)`

### Session & Window Controls
* **Service**: `org.kde.KWin`
* **Path**: `/KWin`
* **Interface**: `org.kde.KWin`
* **Methods**:
  * `activeOutputName()` -> `QString` (Returns name of currently active monitor)
  * `setCurrentDesktop(int desktop)`
  * `nextDesktop()`
  * `previousDesktop()`
  * `showDesktop(bool showing)`
  * `showDebugConsole()`

### Window Management & Running Task Resolution
* **Service**: `org.kde.KWin`
* **Path**: `/WindowsRunner`
* **Interface**: `org.kde.krunner1`
* **Methods**:
  * `Match(QString query)` -> `a(sssuda{sv})` (Queries live open toplevel windows, extracting window UUID, title, icon/appId, desktop index, and activation metadata)
  * `Run(QString matchId, QString actionId)` (Directly activates and raises the target window by UUID)

### KWin Wayland Thumbnail Protocol Research Result
* **Protocol Availability**: KWin Wayland does not expose an unprivileged, public Wayland window thumbnail protocol (`org_kde_kwin_thumbnail` or `zwlr_screencopy_v1` are compositor-internal or specific to wlroots compositors).
* **Plasma Architecture**: In KDE Plasma 6, window live thumbnails are provided via internal compositor-private bindings (`KWin::ThumbnailItem` texture sharing inside the compositor process) and PipeWire portal screencasting per window (which requires user permission prompts).
* **Truthful Capabilities Tenet**: In alignment with Core Principle 8 (*Truthful Capabilities: Never fake unsupported KWin or Wayland protocols*), the multi-window chooser popup truthfully displays actual window titles, icons, and activation controls without generating faked mockups or unreliable preview boxes.

### KWin Layer-Shell Behavior during Alt+Tab and Show Desktop (Verified Limitation)
* **Compositor Architecture**: When running with `reserveSpace: false` (`exclusiveZone: 0`), KWin's built-in `TabBox` (Alt+Tab effect) and `ShowDesktop` (Win+D) effects treat unreserved `WlrLayer.Top` layer-shell surfaces as floating desktop widgets and temporarily hide or occlude them to present the full-screen window switcher and reveal the background wallpaper canvas.
* **Plasma vs External Layer-Shell Surfaces**: Native Plasma panels remain visible because they bind to KDE's private `org_kde_plasma_surface` protocol or reserve exclusive screen struts. External Wayland layer-shell implementations (Quickshell, Waybar, AGS) adhere strictly to standard `zwlr_layer_shell_v1`.
* **Layering Integrity**: Moving Bar/Dock to `WlrLayer.Overlay` to bypass this effect is deliberately rejected as it would place shell panels above the screen locker, full-screen applications, and Spectacle screenshot region selectors. Space reservation remains user-configurable (`reserveSpace: true` retains panel struts). This is documented as a known upstream KWin Wayland effect behavior for floating layer-shell surfaces.

### Native OSD Feedback Service
* **Service**: `org.kde.plasmashell`
* **Path**: `/org/kde/osdService`
* **Interface**: `org.kde.osdService`
* **Methods**:
  * `volumeChanged(int percent)` (Triggers KDE Plasma native transient volume OSD)
  * `microphoneVolumeChanged(int percent)` (Triggers KDE Plasma native microphone volume OSD)
  * `mediaPlayerVolumeChanged(int percent, QString playerName, QString playerIconName)`

### PowerDevil / Session Management
* **Service**: `org.kde.Shutdown`
* **Path**: `/Shutdown`
* **Interface**: `org.kde.Shutdown`
  * `logout()`
  * `logoutAndReboot()`
  * `logoutAndShutdown()`
