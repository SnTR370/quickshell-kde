import QtQuick
import "../../services"
import "../../components"

Item {
    id: root

    implicitWidth: 34
    implicitHeight: 34

    IconButton {
        anchors.centerIn: parent
        size: 32
        icon: "system-shutdown"
        iconColor: Theme.error
        tooltip: "Power / Session"
        onClicked: ConfigService.toggleSettings()
    }
}
