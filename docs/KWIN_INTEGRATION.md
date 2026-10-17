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

### Window Management, Metadata Caching & Native Window Actions
* **Runner Enumeration**:
  * **Service**: `org.kde.KWin`
  * **Path**: `/WindowsRunner`
  * **Interface**: `org.kde.krunner1`
  * **Methods**:
    * `Match(QString query)` -> `a(sssuda{sv})` (Queries live open toplevel windows, extracting immutable window UUID, title, icon, desktop index, and activation state)
    * `Run(QString matchId, QString actionId)` (Activates and raises the target window by UUID)
* **Window Metadata Resolution (`org.kde.KWin.getWindowInfo`)**:
  * Queries `org.kde.KWin /KWin org.kde.KWin.getWindowInfo(QString uuid)` once per newly discovered window UUID and caches `desktopFile`, `resourceClass`, and `resourceName` across scans (with bounded retries on transient empty responses).
  * Matches desktop entries deterministically via exact ID, `StartupWMClass`, `Exec` binary stem, and reverse-DNS suffix without inferring application identity from window title content.
* **KWin 6 Scripting Actions (`org.kde.kwin.Scripting`)**:
  * Executes transient, self-unloading KWin 6 workspace scripts (`services/kwin/scripts/kwin-toggle-window.sh` and `services/kwin/scripts/kwin-window-action.sh`) targeting exact window UUIDs (`workspace.windowList()`):
    * **Activate / Toggle Minimize**: Restores and activates unfocused/minimized windows or minimizes the currently active window.
    * **Graceful Close**: Calls `win.closeWindow()` on the target UUID (allowing applications to prompt for unsaved changes; local state is only updated once KWin confirms closure).
    * **Move to Screen**: Resolves connected outputs from `workspace.screens` and moves the target window via `workspace.sendClientToScreen(win, targetScreen)` (reconciling output placement from KWin state).

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
