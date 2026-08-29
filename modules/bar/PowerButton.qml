import QtQuick
import "../../services"
import "../../components"
import "."

Item {
    id: root

    property var barWindowRef: null
    property string surfaceEdge: "top"
    property bool popupOpen: false

    implicitWidth: parent ? parent.height : 26
    implicitHeight: parent ? parent.height : 26

    IconButton {
        id: powerIcon
        anchors.centerIn: parent
        size: Math.min(root.implicitHeight - 2, 26)
        icon: "system-shutdown"
        iconColor: root.popupOpen ? Theme.contrastColor(Theme.error) : Theme.error
        backgroundColor: root.popupOpen ? Theme.error : (mouseArea.containsMouse ? Theme.alpha(Theme.error, 0.15) : "transparent")
        tooltip: "Power / Session"
        onClicked: root.popupOpen = !root.popupOpen
    }

    // Lazy-loaded Power Menu Popup
    Loader {
        id: powerPopupLoader
        active: root.popupOpen
        sourceComponent: PowerPopup {
            parentWindow: root.barWindowRef || root.Window.window
            anchorItem: powerIcon
            edge: root.surfaceEdge
            onActionTriggered: root.popupOpen = false
            onClosed: root.popupOpen = false
        }
    }
}
