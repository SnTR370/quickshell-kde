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

### PowerDevil / Session Management
* **Service**: `org.kde.Shutdown`
* **Path**: `/Shutdown`
* **Interface**: `org.kde.Shutdown`
  * `logout()`
  * `logoutAndReboot()`
  * `logoutAndShutdown()`
