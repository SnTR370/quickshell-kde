# Module Reference

## 1. Bar (`modules/bar/`)
* **Bar.qml**: Multi-screen `PanelWindow` adapting dynamically to top, bottom, left, or right edges with configurable `left`, `center`, and `right` module slots, output selection filtering, and hardware background blur.
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
* **Dock.qml**: Customizable dock adapting to bottom, top, left, or right screen edges with real autohide, pointer edge reveal, unpinned running apps display, and output selection.
* **DockItem.qml**: Magnifying application icon with active running/focus indicator, middle-click new instance launch, and right-click context menu.
* **DockMenu.qml**: Floating right-click context menu with Pin/Unpin, New Window, and Close All Windows actions.
* **DockSeparator.qml**: Horizontal / vertical layout divider.

## 3. Application Launcher (`modules/launcher/`)
* **LauncherWindow.qml**: Centered application dashboard with keyboard focus, fast in-memory search, and backdrop dismissal.
* **AppGridItem.qml**: Application card with icon, title, description tooltip, and launch action.

## 4. Notifications (`modules/notifications/`)
* **ToastHost.qml**: Floating notification toast host (active when notification server is enabled via configuration for standalone session mode).
* **NotificationCard.qml**: Individual toast card with app icon, title, body, and action buttons.

## 5. On-Screen Display (`modules/osd/`)
* **OSDHost.qml**: Animated overlay HUD reacting to PipeWire volume changes and KDE ScreenBrightness adjustments.
* **VolumeOSD.qml**: Volume level bar and icon.
* **BrightnessOSD.qml**: Display brightness level bar and icon.

## 6. Media Player (`modules/media/`)
* **MediaPopup.qml**: Floating music card with album art, title, artist, and full playback controls.

## 7. Settings (`modules/settings/`)
* **SettingsWindow.qml**: Unified configuration interface for theme presets, KWin background blur, bar edge position, dock autohide, output selection, and session controls.
