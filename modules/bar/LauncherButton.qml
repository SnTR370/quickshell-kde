import QtQuick
import "../../services"
import "../../components"

Item {
    id: root

    implicitWidth: 36
    implicitHeight: 36

    IconButton {
        anchors.centerIn: parent
        size: 34
        icon: "start-here-kde"
        iconColor: Theme.primary
        backgroundColor: Theme.alpha(Theme.primary, 0.15)
        hoverColor: Theme.alpha(Theme.primary, 0.25)
        tooltip: "Application Launcher"
        active: ConfigService.launcherVisible
        onClicked: ConfigService.toggleLauncher()
    }
}
