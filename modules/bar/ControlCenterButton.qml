import QtQuick
import "../../services"
import "../../components"
import "../controlcenter"

Item {
    id: root

    property var barWindowRef: null
    property string surfaceEdge: "top"
    property bool popupOpen: false

    implicitWidth: Math.max(20, ConfigService.barHeight - 6)
    implicitHeight: Math.max(20, ConfigService.barHeight - 6)

    IconButton {
        id: ccIcon
        anchors.centerIn: parent
        parentWindow: root.barWindowRef
        edge: root.surfaceEdge
        size: Math.min(root.implicitHeight, 26)
        icon: "configure"
        iconColor: root.popupOpen ? Theme.contrastColor(Theme.primary) : Theme.primary
        active: root.popupOpen
        activeColor: Theme.primary
        hoverColor: Theme.alpha(Theme.primary, 0.15)
        tooltip: "Control Center"
        onClicked: root.popupOpen = !root.popupOpen
    }

    // Lazy-loaded Control Center Popup (starts closed, only instantiated when popupOpen is true)
    Loader {
        id: ccPopupLoader
        active: root.popupOpen
        sourceComponent: ControlCenterPopup {
            parentWindow: root.barWindowRef || root.Window.window
            anchorItem: ccIcon
            edge: root.surfaceEdge
            onClosed: root.popupOpen = false
        }
    }
}
