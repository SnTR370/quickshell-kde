import QtQuick
import Quickshell
import "../../services"
import "../../components"
import "."

AnchoredPopup {
    id: root

    implicitWidth: controlCenter.implicitWidth
    implicitHeight: controlCenter.implicitHeight

    ControlCenter {
        id: controlCenter
        anchors.fill: parent
        embeddedInPopup: true
        onCloseRequested: root.close()
    }
}
