import QtQuick
import QtQuick.Layouts
import "../../services"
import "../../components"

Surface {
    id: root

    property string appId: ""
    property var app: null
    property bool isRunning: false
    property bool isPinned: false
    readonly property var appWindows: WindowService.getWindowsForApp(root.appId)

    signal actionTriggered()

    implicitWidth: Math.max(200, Math.min(320, menuLayout.implicitWidth + 24))
    implicitHeight: menuLayout.implicitHeight + 16
    radius: Theme.radiusMedium
    color: Theme.alpha(Theme.card, 0.98)
    border.color: Theme.border
    border.width: 1

    ColumnLayout {
        id: menuLayout
        anchors.fill: parent
        anchors.margins: 8
        spacing: 4

        // App Header
        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 4
            Layout.rightMargin: 4
            Layout.bottomMargin: 4
            spacing: 8

            SvgIcon {
                icon: root.app ? root.app.icon : root.appId
                size: 20
            }

            Text {
                text: root.app ? root.app.name : root.appId
                color: Theme.foreground
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                font.bold: true
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.border
            opacity: 0.5
        }

        // Open Windows List (if multi-window or running)
        Repeater {
            model: root.appWindows

            Rectangle {
                id: winItem
                required property var modelData
                Layout.fillWidth: true
                implicitHeight: 28
                radius: Theme.radiusSmall
                color: winMouse.containsMouse ? Theme.hover : "transparent"

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    spacing: 8

                    SvgIcon {
                        icon: "window-duplicate"
                        size: 14
                        color: Theme.accent
                    }

                    Text {
                        text: winItem.modelData.title || (root.app ? root.app.name : root.appId)
                        color: Theme.foreground
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                }

                MouseArea {
                    id: winMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        WindowService.activateWindow(winItem.modelData.id);
                        root.actionTriggered();
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.border
            opacity: 0.5
            visible: root.appWindows.length > 0
        }

        // Action: Launch / New Window
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 28
            radius: Theme.radiusSmall
            color: launchMouse.containsMouse ? Theme.hover : "transparent"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 8

                SvgIcon {
                    icon: "list-add"
                    size: 14
                    color: Theme.foreground
                }

                Text {
                    text: root.isRunning ? "New Window" : "Open"
                    color: Theme.foreground
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                }
            }

            MouseArea {
                id: launchMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    ApplicationService.launchAppId(root.appId);
                    root.actionTriggered();
                }
            }
        }

        // Action: Pin / Unpin
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 28
            radius: Theme.radiusSmall
            color: pinMouse.containsMouse ? Theme.hover : "transparent"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 8

                SvgIcon {
                    icon: root.isPinned ? "bookmark-remove" : "bookmark-new"
                    size: 14
                    color: Theme.foreground
                }

                Text {
                    text: root.isPinned ? "Unpin from Dock" : "Pin to Dock"
                    color: Theme.foreground
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                }
            }

            MouseArea {
                id: pinMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    ApplicationService.togglePin(root.appId);
                    root.actionTriggered();
                }
            }
        }
    }
}
