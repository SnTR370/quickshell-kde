import QtQuick
import QtQuick.Layouts
import Quickshell
import "../../services"
import "../../components"

AnchoredPopup {
    id: root

    property string appId: ""
    property var app: null
    property bool isRunning: false
    property bool isPinned: false
    readonly property var appWindows: WindowService.getWindowsForApp(root.appId)

    signal actionTriggered()

    Component.onCompleted: {
        WindowService.refreshWindowOutputs();
    }

    implicitWidth: Math.max(200, Math.min(320, menuLayout.implicitWidth + 24))
    implicitHeight: menuLayout.implicitHeight + 16

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
                text: ApplicationService.cleanAppName(root.app ? root.app.name : root.appId)
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

            ColumnLayout {
                id: winItem
                required property var modelData
                readonly property string windowId: modelData ? (modelData.id || "") : ""
                readonly property var targetOutputs: WindowService.getTargetOutputsForWindow(windowId)
                Layout.fillWidth: true
                spacing: 2

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 28
                    radius: Theme.radiusSmall
                    color: winActivateMouse.containsMouse ? Theme.hover : "transparent"
                    Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        anchors.rightMargin: 4
                        spacing: 6

                        Item {
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            RowLayout {
                                anchors.fill: parent
                                spacing: 8

                                SvgIcon {
                                    icon: "window-duplicate"
                                    size: 14
                                    color: Theme.accent
                                }

                                Text {
                                    text: (winItem.modelData && winItem.modelData.title) ? winItem.modelData.title : (root.app ? root.app.name : root.appId)
                                    color: Theme.foreground
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeSmall
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                            }

                            MouseArea {
                                id: winActivateMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    WindowService.activateWindow(winItem.windowId);
                                    root.actionTriggered();
                                }
                            }
                        }

                        // Move to Screen buttons (only shown when >1 output and valid targets exist)
                        Repeater {
                            model: winItem.targetOutputs

                            Rectangle {
                                id: moveOutBtn
                                required property string modelData
                                visible: winItem.targetOutputs.length > 0
                                implicitWidth: moveOutLabel.implicitWidth + 10
                                implicitHeight: 20
                                radius: Theme.radiusSmall
                                color: moveOutMouse.containsMouse ? Theme.alpha(Theme.primary, 0.22) : Theme.alpha(Theme.surface, 0.6)
                                border.width: 1
                                border.color: moveOutMouse.containsMouse ? Theme.primary : Theme.border
                                Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }
                                Behavior on border.color { ColorAnimation { duration: Theme.animDurationFast } }

                                Text {
                                    id: moveOutLabel
                                    anchors.centerIn: parent
                                    text: "→ " + moveOutBtn.modelData
                                    color: Theme.foreground
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeSmall - 2
                                }

                                MouseArea {
                                    id: moveOutMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        WindowService.moveWindowToOutput(winItem.windowId, moveOutBtn.modelData);
                                        root.actionTriggered();
                                    }
                                }
                            }
                        }

                        // Graceful Close Window button
                        Rectangle {
                            id: closeWinBtn
                            implicitWidth: 22
                            implicitHeight: 22
                            radius: Theme.radiusSmall
                            color: closeWinMouse.containsMouse ? Theme.alpha(Theme.error, 0.22) : "transparent"
                            Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

                            SvgIcon {
                                anchors.centerIn: parent
                                icon: "window-close"
                                size: 13
                                color: closeWinMouse.containsMouse ? Theme.error : Theme.foreground
                            }

                            MouseArea {
                                id: closeWinMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    WindowService.closeWindow(winItem.windowId);
                                    root.actionTriggered();
                                }
                            }
                        }
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
            Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

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
