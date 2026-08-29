import QtQuick
import Quickshell
import Quickshell.Wayland
import "../../services"
import "."

Variants {
    id: root

    model: Quickshell.screens

    PanelWindow {
        id: osdWindow
        required property var modelData

        screen: modelData
        color: "transparent"
        visible: osdTimer.running && KWinService.isTargetOverlayScreen(modelData)

        anchors {
            bottom: true
        }

        margins {
            bottom: 100
        }

        implicitWidth: 240
        implicitHeight: 80
        exclusiveZone: 0

        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.namespace: "quickshell:osd"

        BrightnessOSD {
            anchors.centerIn: parent
            visible: osdWindow.visible
            opacity: osdWindow.visible ? 1.0 : 0.0
            scale: osdWindow.visible ? 1.0 : 0.9

            Behavior on opacity { NumberAnimation { duration: Theme.animDurationFast } }
            Behavior on scale { NumberAnimation { duration: Theme.animDurationFast; easing.type: Easing.OutBack } }
        }

        Timer {
            id: osdTimer
            interval: 1800
            repeat: false
        }

        Connections {
            target: BrightnessService
            function onOsdPulse() {
                osdTimer.restart();
            }
        }
    }
}
