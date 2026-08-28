import QtQuick
import QtQuick.Layouts
import Quickshell.Services.SystemTray
import "../../services"
import "../../components"

Surface {
    id: root

    visible: SystemTray.items && SystemTray.items.values.length > 0
    implicitHeight: 34
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

                implicitWidth: 26
                implicitHeight: 26

                Rectangle {
                    anchors.fill: parent
                    radius: Theme.radiusSmall
                    color: trayItemMouse.containsMouse ? Theme.hover : "transparent"

                    SvgIcon {
                        anchors.centerIn: parent
                        icon: modelData.icon || "application-x-executable"
                        size: 18
                    }

                    MouseArea {
                        id: trayItemMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton

                        onClicked: mouse => {
                            if (mouse.button === Qt.RightButton) {
                                if (modelData.hasMenu) {
                                    modelData.display(barWindow, mouse.x, mouse.y);
                                } else {
                                    modelData.secondaryActivate();
                                }
                            } else if (mouse.button === Qt.MiddleButton) {
                                modelData.secondaryActivate();
                            } else {
                                modelData.activate();
                            }
                        }

                        onWheel: wheel => {
                            modelData.scroll(wheel.angleDelta.y, false);
                        }
                    }
                }
            }
        }
    }
}
