import QtQuick
import QtQuick.Layouts
import Quickshell.Services.SystemTray
import "../../services"
import "../../components"

Surface {
    id: root

    property var barWindowRef: null
    property string surfaceEdge: "top"

    visible: SystemTray.items && SystemTray.items.values.length > 0
    implicitHeight: Math.max(20, ConfigService.barHeight - 6)
    implicitWidth: trayLayout.implicitWidth + 8
    radius: Theme.radiusSmall
    color: Theme.alpha(Theme.surfaceVariant, 0.6)

    RowLayout {
        id: trayLayout
        anchors.centerIn: parent
        spacing: 4

        Repeater {
            model: SystemTray.items ? SystemTray.items.values : []

            Item {
                id: trayDelegate
                required property var modelData

                implicitWidth: Math.max(16, ConfigService.barHeight - 8)
                implicitHeight: Math.max(16, ConfigService.barHeight - 8)

                Rectangle {
                    anchors.fill: parent
                    radius: Theme.radiusSmall
                    color: trayItemMouse.containsMouse ? Theme.hover : "transparent"

                    SvgIcon {
                        anchors.centerIn: parent
                        icon: (trayDelegate.modelData.icon && String(trayDelegate.modelData.icon).length > 0) ? String(trayDelegate.modelData.icon) : (trayDelegate.modelData.iconName || "application-x-executable")
                        size: Math.max(14, ConfigService.barHeight - 12)
                    }

                    MouseArea {
                        id: trayItemMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton

                        onClicked: mouse => {
                            if (mouse.button === Qt.RightButton) {
                                if (trayDelegate.modelData.hasMenu) {
                                    trayDelegate.modelData.display(root.barWindowRef || root.Window.window, mouse.x, mouse.y);
                                } else {
                                    trayDelegate.modelData.secondaryActivate();
                                }
                            } else if (mouse.button === Qt.MiddleButton) {
                                trayDelegate.modelData.secondaryActivate();
                            } else {
                                trayDelegate.modelData.activate();
                            }
                        }

                        onWheel: wheel => {
                            trayDelegate.modelData.scroll(wheel.angleDelta.y, false);
                        }
                    }
                }
            }
        }
    }
}
