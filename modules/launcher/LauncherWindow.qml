import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import Quickshell
import Quickshell.Wayland
import "../../services"
import "../../components"
import "."

Variants {
    id: root

    model: Quickshell.screens

    PanelWindow {
        id: launcherWin
        required property var modelData

        screen: modelData
        visible: ConfigService.launcherVisible && KWinService.isTargetOverlayScreen(modelData)
        color: "transparent"

        anchors {
            top: true
            bottom: true
            left: true
            right: true
        }

        exclusiveZone: 0
        WlrLayershell.layer: WlrLayer.Top
        WlrLayershell.namespace: "quickshell:launcher"
        WlrLayershell.keyboardFocus: visible ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None

        BackgroundEffect.blurRegion: Region {
            item: ConfigService.blurEnabled ? mainContainer : null
        }

        property string selectedCategory: "all"
        property var searchResults: ApplicationService.search(searchInput.text, selectedCategory)

        function closeLauncher() {
            ConfigService.launcherVisible = false;
            searchInput.text = "";
        }

        // Backdrop click to close
        MouseArea {
            anchors.fill: parent
            onClicked: launcherWin.closeLauncher()
        }

        // Centered Card Container
        Surface {
            id: mainContainer
            anchors.centerIn: parent
            width: Math.min(760, parent.width - 40)
            height: Math.min(540, parent.height - 60)
            radius: Theme.radiusLarge
            color: Theme.alpha(Theme.background, Theme.popupOpacity)
            border.color: Theme.primary
            border.width: 1

            // Prevent backdrop click inside the card
            MouseArea {
                anchors.fill: parent
                onClicked: {}
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 14

                // Search Bar Row
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Surface {
                        Layout.fillWidth: true
                        implicitHeight: 44
                        radius: Theme.radiusMedium
                        color: Theme.surfaceVariant

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 12
                            anchors.rightMargin: 12
                            spacing: 8

                            SvgIcon {
                                icon: "search"
                                size: 20
                                color: Theme.primary
                            }

                            TextInput {
                                id: searchInput
                                Layout.fillWidth: true
                                color: Theme.foreground
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.fontSizeLarge
                                selectByMouse: true
                                focus: launcherWin.visible

                                Text {
                                    text: "Type to search applications..."
                                    color: Theme.foregroundMuted
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeLarge
                                    visible: !searchInput.text && !searchInput.activeFocus
                                }

                                Keys.onEscapePressed: launcherWin.closeLauncher()
                                Keys.onReturnPressed: {
                                    if (launcherWin.searchResults.length > 0) {
                                        ApplicationService.launch(launcherWin.searchResults[0]);
                                        launcherWin.closeLauncher();
                                    }
                                }
                            }

                            IconButton {
                                size: 28
                                icon: "edit-clear"
                                visible: searchInput.text.length > 0
                                onClicked: searchInput.text = ""
                            }
                        }
                    }

                    IconButton {
                        size: 40
                        icon: "window-close"
                        iconColor: Theme.error
                        tooltip: "Close (Esc)"
                        onClicked: launcherWin.closeLauncher()
                    }
                }

                // Main Content (Category Sidebar + App Grid)
                RowLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 12

                    // Category Sidebar
                    Surface {
                        Layout.preferredWidth: 160
                        Layout.fillHeight: true
                        radius: Theme.radiusMedium
                        color: Theme.alpha(Theme.surface, 0.6)

                        ScrollView {
                            anchors.fill: parent
                            anchors.margins: 6
                            clip: true

                            ColumnLayout {
                                width: parent.width - 8
                                spacing: 4

                                Repeater {
                                    model: ApplicationService.categories

                                    Rectangle {
                                        id: catItem
                                        required property var modelData
                                        Layout.fillWidth: true
                                        implicitHeight: 34
                                        radius: Theme.radiusSmall
                                        color: (launcherWin.selectedCategory === modelData.id) ? Theme.primary : (catMouse.containsMouse ? Theme.hover : "transparent")

                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.leftMargin: 10
                                            spacing: 8

                                            SvgIcon {
                                                icon: catItem.modelData.icon || "folder"
                                                size: 16
                                                color: (launcherWin.selectedCategory === catItem.modelData.id) ? Theme.contrastColor(Theme.primary) : Theme.foreground
                                            }

                                            Text {
                                                text: catItem.modelData.name
                                                color: (launcherWin.selectedCategory === catItem.modelData.id) ? Theme.contrastColor(Theme.primary) : Theme.foreground
                                                font.family: Theme.fontFamily
                                                font.pixelSize: Theme.fontSizeSmall
                                                font.bold: launcherWin.selectedCategory === catItem.modelData.id
                                            }
                                        }

                                        MouseArea {
                                            id: catMouse
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: launcherWin.selectedCategory = catItem.modelData.id
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Applications Grid
                    Surface {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: Theme.radiusMedium
                        color: Theme.alpha(Theme.surface, 0.4)

                        GridView {
                            id: appGrid
                            anchors.fill: parent
                            anchors.margins: 10
                            cellWidth: 110
                            cellHeight: 115
                            clip: true
                            model: launcherWin.searchResults

                            delegate: AppGridItem {
                                required property var modelData
                                app: modelData
                                onLaunched: launcherWin.closeLauncher()
                            }
                        }

                        // Empty search state
                        Text {
                            anchors.centerIn: parent
                            visible: launcherWin.searchResults.length === 0
                            text: "No applications found"
                            color: Theme.foregroundMuted
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSizeMedium
                        }
                    }
                }

                // Footer / Power session row
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Text {
                        text: launcherWin.searchResults.length + " applications"
                        color: Theme.foregroundMuted
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                    }

                    Item { Layout.fillWidth: true }

                    IconButton {
                        icon: "system-lock-screen"
                        tooltip: "Lock Screen"
                        size: 32
                        onClicked: { KWinService.lockSession(); launcherWin.closeLauncher(); }
                    }

                    IconButton {
                        icon: "system-log-out"
                        tooltip: "Log Out"
                        size: 32
                        onClicked: { Quickshell.execDetached(["qdbus6", "org.kde.Shutdown", "/Shutdown", "org.kde.Shutdown.logout"]); launcherWin.closeLauncher(); }
                    }

                    IconButton {
                        icon: "system-reboot"
                        tooltip: "Restart"
                        size: 32
                        onClicked: { Quickshell.execDetached(["qdbus6", "org.kde.Shutdown", "/Shutdown", "org.kde.Shutdown.logoutAndReboot"]); launcherWin.closeLauncher(); }
                    }

                    IconButton {
                        icon: "system-shutdown"
                        tooltip: "Shut Down"
                        size: 32
                        iconColor: Theme.error
                        onClicked: { Quickshell.execDetached(["qdbus6", "org.kde.Shutdown", "/Shutdown", "org.kde.Shutdown.logoutAndShutdown"]); launcherWin.closeLauncher(); }
                    }
                }
            }
        }
    }
}
