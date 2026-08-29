import QtQuick
import QtQuick.Layouts
import Quickshell
import "../../services"
import "../../components"

AnchoredPopup {
    id: root

    property string appId: ""
    property var app: null
    readonly property var appWindows: WindowService.getWindowsForApp(root.appId)

    signal windowSelected()

    implicitWidth: Math.max(240, Math.min(380, chooserLayout.implicitWidth + 24))
    implicitHeight: chooserLayout.implicitHeight + 16

    ColumnLayout {
        id: chooserLayout
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

            Badge {
                text: root.appWindows.length + (root.appWindows.length === 1 ? " window" : " windows")
                color: Theme.primary
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.border
            opacity: 0.5
        }

        // Active Windows List
        Repeater {
            model: root.appWindows

            Rectangle {
                id: winRow
                required property var modelData
                Layout.fillWidth: true
                implicitHeight: 34
                radius: Theme.radiusSmall
                color: winMouse.containsMouse ? Theme.hover : "transparent"

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    spacing: 8

                    SvgIcon {
                        icon: winRow.modelData.icon || (root.app ? root.app.icon : "window-duplicate")
                        size: 16
                        color: Theme.accent
                    }

                    Text {
                        text: winRow.modelData.title || (root.app ? root.app.name : root.appId)
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
                        WindowService.activateWindow(winRow.modelData.id);
                        root.windowSelected();
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.border
            opacity: 0.5
        }

        // Action: New Window
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 28
            radius: Theme.radiusSmall
            color: newWinMouse.containsMouse ? Theme.hover : "transparent"

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
                    text: "New Window"
                    color: Theme.foreground
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                }
            }

            MouseArea {
                id: newWinMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    ApplicationService.launchAppId(root.appId);
                    root.windowSelected();
                }
            }
        }
    }
}
