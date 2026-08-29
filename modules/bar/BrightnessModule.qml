import QtQuick
import QtQuick.Layouts
import "../../services"
import "../../components"
import "."

Surface {
    id: root

    property var barWindowRef: null
    property string surfaceEdge: "top"
    property bool popupOpen: false

    implicitHeight: parent ? parent.height : 26
    implicitWidth: layout.implicitWidth + 8
    radius: Theme.radiusSmall
    color: (brightMouse.containsMouse || root.popupOpen) ? Theme.hover : "transparent"
    visible: BrightnessService.supported

    readonly property string iconName: {
        if (BrightnessService.brightness > 0.66) return "display-brightness-high";
        if (BrightnessService.brightness > 0.33) return "display-brightness-medium";
        if (BrightnessService.brightness > 0.0) return "display-brightness-low";
        return "display-brightness-off";
    }

    RowLayout {
        id: layout
        anchors.centerIn: parent
        spacing: 4

        SvgIcon {
            icon: root.iconName
            size: 14
            color: Theme.warning
        }

        Text {
            text: BrightnessService.percentage + "%"
            color: Theme.foreground
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeSmall
            font.bold: true
        }
    }

    Loader {
        id: popupLoader
        active: root.popupOpen
        sourceComponent: BrightnessPopup {
            parentWindow: root.barWindowRef || root.Window.window
            anchorItem: root
            edge: root.surfaceEdge
            onClosed: root.popupOpen = false
        }
    }

    Tooltip {
        text: BrightnessService.isReadOnly ? "Backlight Telemetry (Read-Only)" : (BrightnessService.controlledDisplayName ? (BrightnessService.controlledDisplayName + ": " + BrightnessService.percentage + "%") : "Display Brightness")
        show: brightMouse.containsMouse && !root.popupOpen
    }

    MouseArea {
        id: brightMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton

        onClicked: mouse => {
            if (mouse.button === Qt.RightButton) {
                Quickshell.execDetached(["kcmshell6", "kcm_kscreen"]);
            } else {
                root.popupOpen = !root.popupOpen;
            }
        }

        onWheel: wheel => {
            if (!BrightnessService.controllable) return;
            if (wheel.angleDelta.y > 0) {
                BrightnessService.increaseBrightness(0.05);
            } else {
                BrightnessService.decreaseBrightness(0.05);
            }
        }
    }
}
