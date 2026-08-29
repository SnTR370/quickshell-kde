import QtQuick
import "../../services"
import "../../components"

Item {
    id: root

    implicitWidth: parent ? parent.height : 26
    implicitHeight: parent ? parent.height : 26

    IconButton {
        anchors.centerIn: parent
        size: Math.min(root.implicitHeight - 2, 26)
        icon: "start-here-kde"
        iconColor: Theme.primary
        backgroundColor: (mouseArea.containsMouse || ConfigService.launcherVisible) ? Theme.alpha(Theme.primary, 0.2) : "transparent"
        tooltip: "Application Launcher"
        active: ConfigService.launcherVisible
        onClicked: ConfigService.toggleLauncher()
    }
}
