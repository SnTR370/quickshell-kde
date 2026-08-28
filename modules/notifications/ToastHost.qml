import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import "../../services"
import "."

Variants {
    id: root

    model: Quickshell.screens

    PanelWindow {
        id: toastWin
        required property var modelData

        screen: modelData
        color: "transparent"
        visible: ConfigService.notificationsEnabled && NotificationService.activeToasts.length > 0

        anchors {
            top: true
            right: true
        }

        margins {
            top: 54
            right: 16
        }

        implicitWidth: 340
        implicitHeight: toastColumn.implicitHeight + 20
        exclusiveZone: 0

        WlrLayershell.layer: WlrLayer.Overlay

        ColumnLayout {
            id: toastColumn
            anchors.top: parent.top
            anchors.right: parent.right
            spacing: 8

            Repeater {
                model: NotificationService.activeToasts

                NotificationCard {
                    required property var modelData
                    notification: modelData
                    onDismissed: id => NotificationService.dismissToast(id)
                }
            }
        }
    }
}
