import QtQuick
import QtQuick.Layouts
import Quickshell
import "../../services"
import "../../components"

AnchoredPopup {
    id: root

    implicitWidth: 190
    implicitHeight: powerCol.implicitHeight + 16

    signal actionTriggered()

    ColumnLayout {
        id: powerCol
        anchors.fill: parent
        anchors.margins: 8
        spacing: 4

        Text {
            text: "Session Actions"
            color: Theme.foregroundMuted
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeSmall
            font.bold: true
            Layout.leftMargin: 6
            Layout.bottomMargin: 2
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.border
            opacity: 0.5
        }

        // Lock
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 30
            radius: Theme.radiusSmall
            color: lockMouse.containsMouse ? Theme.hover : "transparent"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                spacing: 8

                SvgIcon {
                    icon: "system-lock-screen"
                    size: 16
                    color: Theme.foreground
                }

                Text {
                    text: "Lock Screen"
                    color: Theme.foreground
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                }
            }

            MouseArea {
                id: lockMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    root.actionTriggered();
                    KWinService.lockSession();
                }
            }
        }

        // Log Out
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 30
            radius: Theme.radiusSmall
            color: logoutMouse.containsMouse ? Theme.hover : "transparent"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                spacing: 8

                SvgIcon {
                    icon: "system-log-out"
                    size: 16
                    color: Theme.foreground
                }

                Text {
                    text: "Log Out"
                    color: Theme.foreground
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                }
            }

            MouseArea {
                id: logoutMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    root.actionTriggered();
                    Quickshell.execDetached(["qdbus6", "org.kde.Shutdown", "/Shutdown", "org.kde.Shutdown.logout"]);
                }
            }
        }

        // Restart
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 30
            radius: Theme.radiusSmall
            color: rebootMouse.containsMouse ? Theme.hover : "transparent"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                spacing: 8

                SvgIcon {
                    icon: "system-reboot"
                    size: 16
                    color: Theme.foreground
                }

                Text {
                    text: "Restart..."
                    color: Theme.foreground
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                }
            }

            MouseArea {
                id: rebootMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    root.actionTriggered();
                    Quickshell.execDetached(["qdbus6", "org.kde.Shutdown", "/Shutdown", "org.kde.Shutdown.logoutAndReboot"]);
                }
            }
        }

        // Shut Down
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 30
            radius: Theme.radiusSmall
            color: shutdownMouse.containsMouse ? Theme.hover : "transparent"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                spacing: 8

                SvgIcon {
                    icon: "system-shutdown"
                    size: 16
                    color: Theme.error
                }

                Text {
                    text: "Shut Down..."
                    color: Theme.error
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                    font.bold: true
                }
            }

            MouseArea {
                id: shutdownMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    root.actionTriggered();
                    Quickshell.execDetached(["qdbus6", "org.kde.Shutdown", "/Shutdown", "org.kde.Shutdown.logoutAndShutdown"]);
                }
            }
        }
    }
}
