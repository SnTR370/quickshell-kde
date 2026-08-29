import QtQuick
import "../../services"
import "../../components"
import "."

Item {
    id: root

    property var barWindowRef: null
    property string surfaceEdge: "top"
    property bool popupOpen: false

    implicitWidth: 34
    implicitHeight: 34

    IconButton {
        id: powerIcon
        anchors.centerIn: parent
        size: 32
        icon: "system-shutdown"
        iconColor: root.popupOpen ? Theme.contrastColor(Theme.error) : Theme.error
        backgroundColor: root.popupOpen ? Theme.error : "transparent"
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
