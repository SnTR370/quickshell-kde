# Module Reference

## 1. Bar (`modules/bar/`)
* **Bar.qml**: Multi-screen `PanelWindow` adapting dynamically to top, bottom, left, or right edges with configurable `left`, `center`, and `right` module slots.
* **WorkspacesModule.qml**: Virtual desktop indicators with click-to-switch and scroll-to-cycle powered by KWin DBus.
* **ClockModule.qml**: Formatted time/date with settings launcher.
* **AudioModule.qml**: Volume level, mute status, quick mixer launcher, and wheel volume control.
* **MediaModule.qml**: Mini MPRIS player with track artist, title, and play/pause button.
* **TrayModule.qml**: Embedded system tray icons with StatusNotifierItem actions and DBus menus.
* **NetworkModule.qml**: Event-driven network connection state, SSID, and signal strength indicator via `Quickshell.Networking`.
* **BatteryModule.qml**: Battery percentage and charging indicator via UPower.
* **LauncherButton.qml**: Application launcher toggle button.
* **PowerButton.qml**: Quick session shutdown/reboot/lock action menu.

## 2. Dock (`modules/dock/`)
* **Dock.qml**: Customizable dock adapting to bottom, top, left, or right screen edges with configurable icon size.
* **DockItem.qml**: Magnifying application icon with active running dot and right-click pin/unpin action.
* **DockSeparator.qml**: Horizontal / vertical layout divider.

## 3. Application Launcher (`modules/launcher/`)
* **LauncherWindow.qml**: Centered application dashboard with keyboard focus, fast in-memory search, and backdrop dismissal.
* **AppGridItem.qml**: Application card with icon, title, description tooltip, and launch action.

## 4. Notifications (`modules/notifications/`)
* **ToastHost.qml**: Floating notification toast host (active when notification server is enabled via configuration for standalone session mode).
* **NotificationCard.qml**: Individual toast card with app icon, title, body, and action buttons.

## 5. On-Screen Display (`modules/osd/`)
* **OSDHost.qml**: Animated overlay HUD for volume adjustments reacting to PipeWire changes.
* **VolumeOSD.qml**: Volume level bar and icon.

## 6. Media Player (`modules/media/`)
* **MediaPopup.qml**: Floating music card with album art, title, artist, and full playback controls.

## 7. Settings (`modules/settings/`)
* **SettingsWindow.qml**: Configuration interface for live theme selection, bar position, and dock customization.
