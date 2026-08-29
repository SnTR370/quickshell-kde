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

### PowerDevil / Session Management
* **Service**: `org.kde.Shutdown`
* **Path**: `/Shutdown`
* **Interface**: `org.kde.Shutdown`
  * `logout()`
  * `logoutAndReboot()`
  * `logoutAndShutdown()`
