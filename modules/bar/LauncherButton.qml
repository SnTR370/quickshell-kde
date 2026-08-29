import QtQuick
import "../../services"
import "../../components"

Item {
    id: root

    property var barWindowRef: null
    property string surfaceEdge: "top"

    implicitWidth: Math.max(20, ConfigService.barHeight - 6)
    implicitHeight: Math.max(20, ConfigService.barHeight - 6)

    IconButton {
        anchors.centerIn: parent
        size: Math.min(root.implicitHeight, 26)
        icon: "start-here-kde"
        iconColor: Theme.primary
        active: ConfigService.launcherVisible
        activeColor: Theme.alpha(Theme.primary, 0.2)
        hoverColor: Theme.alpha(Theme.primary, 0.12)
        tooltip: "Application Launcher"
        onClicked: ConfigService.toggleLauncher(root.barWindowRef ? root.barWindowRef.screen : null)
    }
}
