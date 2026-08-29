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

        property string osdType: "volume"

        VolumeOSD {
            anchors.centerIn: parent
            visible: osdWindow.osdType === "volume"
            opacity: osdWindow.visible && osdWindow.osdType === "volume" ? 1.0 : 0.0
            scale: osdWindow.visible ? 1.0 : 0.9

            Behavior on opacity { NumberAnimation { duration: Theme.animDurationFast } }
            Behavior on scale { NumberAnimation { duration: Theme.animDurationFast; easing.type: Easing.OutBack } }
        }

        BrightnessOSD {
            anchors.centerIn: parent
            visible: osdWindow.osdType === "brightness"
            opacity: osdWindow.visible && osdWindow.osdType === "brightness" ? 1.0 : 0.0
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
            target: AudioService
            function onOsdPulse() {
                osdWindow.osdType = "volume";
                osdTimer.restart();
            }
        }

        Connections {
            target: BrightnessService
            function onOsdPulse() {
                osdWindow.osdType = "brightness";
                osdTimer.restart();
            }
        }
    }
}
