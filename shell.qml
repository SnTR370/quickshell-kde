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
import "./modules/settings"

ShellRoot {
    id: root

    // Top / Side Bar
    Bar {}

    // Bottom / Side Dock
    Dock {}

    // Application Launcher Window
    LauncherWindow {}

    // Toast Notifications Host
    ToastHost {}

    // Volume / Brightness OSD Host
    OSDHost {}

    // Settings Dashboard
    SettingsWindow {}
}
