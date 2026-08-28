//@ pragma UseQApplication
import QtQuick
import Quickshell
import Quickshell.Wayland

import "./services"
import "./modules/bar"
import "./modules/dock"
import "./modules/launcher"
import "./modules/notifications"
import "./modules/osd"
import "./modules/media"
import "./modules/settings"

ShellRoot {
    id: root

    // Top / Side Bar
    Bar {}

    // Bottom Dock
    Dock {}

    // Application Launcher Window
    LauncherWindow {}

    // Toast Notifications Host
    ToastHost {}

    // Volume / Brightness OSD Host
    OSDHost {}

    // Floating Media Popup
    MediaPopup {}

    // Settings Dashboard
    SettingsWindow {}
}
