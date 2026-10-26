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

    implicitWidth: 260
    implicitHeight: chooserLayout.implicitHeight + 20

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
                text: ApplicationService.cleanAppName(root.app ? root.app.name : root.appId)
                color: Theme.foreground
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                font.bold: true
                elide: Text.ElideRight
                Layout.fillWidth: true
            }

            Badge {
                text: root.appWindows.length + (root.appWindows.length === 1 ? " window" : " windows")
                badgeColor: Theme.primary
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: Theme.border
            opacity: 0.5
        }

        // Active Windows List
        Repeater {
            model: root.appWindows

            Rectangle {
                id: winRow
                required property var modelData
                readonly property string windowId: modelData ? (modelData.id || "") : ""
                readonly property bool canClose: WindowService.canCloseWindow(windowId)
                Layout.fillWidth: true
                implicitHeight: 34
                radius: Theme.radiusSmall
                color: winMouse.containsMouse ? Theme.hover : "transparent"
                Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 6
                    spacing: 8

                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true

                        RowLayout {
                            anchors.fill: parent
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

                    Rectangle {
                        id: chooserCloseBtn
                        implicitWidth: 22
                        implicitHeight: 22
                        radius: Theme.radiusSmall
                        opacity: winRow.canClose ? 1.0 : 0.45
                        color: (winRow.canClose && chooserCloseMouse.containsMouse) ? Theme.alpha(Theme.error, 0.22) : "transparent"
                        Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

                        SvgIcon {
                            anchors.centerIn: parent
                            icon: "window-close"
                            size: 13
                            color: (winRow.canClose && chooserCloseMouse.containsMouse) ? Theme.error : (winRow.canClose ? Theme.foreground : Theme.foregroundMuted)
                        }

                        MouseArea {
                            id: chooserCloseMouse
                            anchors.fill: parent
                            enabled: winRow.canClose
                            hoverEnabled: true
                            cursorShape: winRow.canClose ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: {
                                if (WindowService.closeWindow(winRow.windowId)) {
                                    root.windowSelected();
                                }
                            }
                        }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: Theme.border
            opacity: 0.5
        }

        // Action: New Window
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 28
            radius: Theme.radiusSmall
            color: newWinMouse.containsMouse ? Theme.hover : "transparent"
            Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

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
