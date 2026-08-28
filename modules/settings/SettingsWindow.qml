import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import Quickshell
import Quickshell.Wayland
import "../../services"
import "../../components"

Variants {
    id: root

    model: Quickshell.screens

    PanelWindow {
        id: settingsWin
        required property var modelData

        screen: modelData
        visible: ConfigService.settingsVisible
        color: "transparent"

        anchors {
            top: true
            bottom: true
            left: true
            right: true
        }

        exclusiveZone: 0
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.keyboardFocus: (visible && (KWinService.activeOutputName === "" || modelData.name === KWinService.activeOutputName || KWinService.screenCount === 1)) ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None

        function closeSettings() {
            ConfigService.settingsVisible = false;
        }

        MouseArea {
            anchors.fill: parent
            onClicked: settingsWin.closeSettings()
        }

        Surface {
            id: mainContainer
            anchors.centerIn: parent
            width: Math.min(640, parent.width - 40)
            height: Math.min(520, parent.height - 60)
            radius: Theme.radiusLarge
            color: Theme.alpha(Theme.background, Theme.popupOpacity)
            border.color: Theme.border
            border.width: 1

            MouseArea {
                anchors.fill: parent
                onClicked: {}
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 16

                // Header
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    SvgIcon {
                        icon: "preferences-system"
                        size: 24
                        color: Theme.primary
                    }

                    Text {
                        text: "Quickshell KDE Settings"
                        color: Theme.foreground
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeHeading
                        font.bold: true
                    }

                    Item { Layout.fillWidth: true }

                    IconButton {
                        size: 28
                        icon: "window-close"
                        iconColor: Theme.error
                        onClicked: settingsWin.closeSettings()
                    }
                }

                // Tabs / Sections
                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true

                    ColumnLayout {
                        width: parent.width - 16
                        spacing: 16

                        // Theme Section
                        Surface {
                            Layout.fillWidth: true
                            implicitHeight: themeCol.implicitHeight + 20
                            radius: Theme.radiusMedium
                            color: Theme.alpha(Theme.surface, 0.6)

                            ColumnLayout {
                                id: themeCol
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 10

                                Text {
                                    text: "Theme Preset"
                                    color: Theme.foreground
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeMedium
                                    font.bold: true
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    Repeater {
                                        model: ThemeService.availableThemes

                                        Rectangle {
                                            id: themeBtn
                                            required property var modelData
                                            Layout.fillWidth: true
                                            implicitHeight: 36
                                            radius: Theme.radiusSmall
                                            color: (Theme.activeThemeId === modelData.id) ? Theme.primary : (tMouse.containsMouse ? Theme.hover : Theme.surfaceVariant)

                                            Text {
                                                anchors.centerIn: parent
                                                text: themeBtn.modelData.name
                                                color: (Theme.activeThemeId === themeBtn.modelData.id) ? Theme.contrastColor(Theme.primary) : Theme.foreground
                                                font.family: Theme.fontFamily
                                                font.pixelSize: Theme.fontSizeSmall
                                                font.bold: Theme.activeThemeId === themeBtn.modelData.id
                                            }

                                            MouseArea {
                                                id: tMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: ThemeService.saveThemeSelection(themeBtn.modelData.id)
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // Bar Position Section
                        Surface {
                            Layout.fillWidth: true
                            implicitHeight: barCol.implicitHeight + 20
                            radius: Theme.radiusMedium
                            color: Theme.alpha(Theme.surface, 0.6)

                            ColumnLayout {
                                id: barCol
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 10

                                Text {
                                    text: "Bar Position"
                                    color: Theme.foreground
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeMedium
                                    font.bold: true
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    Repeater {
                                        model: [
                                            { id: "top", name: "Top" },
                                            { id: "bottom", name: "Bottom" },
                                            { id: "left", name: "Left" },
                                            { id: "right", name: "Right" }
                                        ]

                                        Rectangle {
                                            id: posBtn
                                            required property var modelData
                                            Layout.fillWidth: true
                                            implicitHeight: 36
                                            radius: Theme.radiusSmall
                                            color: (ConfigService.barPosition === modelData.id) ? Theme.primary : (pMouse.containsMouse ? Theme.hover : Theme.surfaceVariant)

                                            Text {
                                                anchors.centerIn: parent
                                                text: posBtn.modelData.name
                                                color: (ConfigService.barPosition === posBtn.modelData.id) ? Theme.contrastColor(Theme.primary) : Theme.foreground
                                                font.family: Theme.fontFamily
                                                font.pixelSize: Theme.fontSizeSmall
                                                font.bold: ConfigService.barPosition === posBtn.modelData.id
                                            }

                                            MouseArea {
                                                id: pMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: ConfigService.setBarPosition(posBtn.modelData.id)
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // Dock Configuration Section
                        Surface {
                            Layout.fillWidth: true
                            implicitHeight: dockCol.implicitHeight + 20
                            radius: Theme.radiusMedium
                            color: Theme.alpha(Theme.surface, 0.6)

                            ColumnLayout {
                                id: dockCol
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 10

                                RowLayout {
                                    Layout.fillWidth: true

                                    Text {
                                        text: "Dock Configuration"
                                        color: Theme.foreground
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fontSizeMedium
                                        font.bold: true
                                        Layout.fillWidth: true
                                    }

                                    IconButton {
                                        text: ConfigService.dockEnabled ? "Enabled" : "Disabled"
                                        size: 30
                                        backgroundColor: ConfigService.dockEnabled ? Theme.primary : Theme.surfaceVariant
                                        iconColor: ConfigService.dockEnabled ? Theme.contrastColor(Theme.primary) : Theme.foregroundMuted
                                        onClicked: ConfigService.setDockEnabled(!ConfigService.dockEnabled)
                                    }
                                }

                                Text {
                                    text: "Dock Position"
                                    color: Theme.foregroundMuted
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeSmall
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    Repeater {
                                        model: [
                                            { id: "bottom", name: "Bottom" },
                                            { id: "top", name: "Top" },
                                            { id: "left", name: "Left" },
                                            { id: "right", name: "Right" }
                                        ]

                                        Rectangle {
                                            id: dPosBtn
                                            required property var modelData
                                            Layout.fillWidth: true
                                            implicitHeight: 32
                                            radius: Theme.radiusSmall
                                            color: (ConfigService.dockPosition === modelData.id) ? Theme.primary : (dpMouse.containsMouse ? Theme.hover : Theme.surfaceVariant)

                                            Text {
                                                anchors.centerIn: parent
                                                text: dPosBtn.modelData.name
                                                color: (ConfigService.dockPosition === dPosBtn.modelData.id) ? Theme.contrastColor(Theme.primary) : Theme.foreground
                                                font.family: Theme.fontFamily
                                                font.pixelSize: Theme.fontSizeSmall
                                                font.bold: ConfigService.dockPosition === dPosBtn.modelData.id
                                            }

                                            MouseArea {
                                                id: dpMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: ConfigService.setDockPosition(dPosBtn.modelData.id)
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // Compositor Status Section
                        Surface {
                            Layout.fillWidth: true
                            implicitHeight: kwinCol.implicitHeight + 20
                            radius: Theme.radiusMedium
                            color: Theme.alpha(Theme.surface, 0.6)

                            ColumnLayout {
                                id: kwinCol
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 8

                                Text {
                                    text: "Compositor & Session"
                                    color: Theme.foreground
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeMedium
                                    font.bold: true
                                }

                                Text {
                                    text: "Compositor: KWin Wayland (KDE Plasma 6)"
                                    color: Theme.foregroundMuted
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeSmall
                                }

                                Text {
                                    text: "Monitors: " + KWinService.screenCount + " | Active Output: " + (KWinService.activeOutputName || "Default")
                                    color: Theme.foregroundMuted
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeSmall
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    IconButton {
                                        text: "KDE System Settings"
                                        icon: "systemsettings"
                                        size: 34
                                        backgroundColor: Theme.surfaceVariant
                                        onClicked: { KWinService.openKdeSettings(); settingsWin.closeSettings(); }
                                    }

                                    IconButton {
                                        text: "Display Settings"
                                        icon: "preferences-desktop-display"
                                        size: 34
                                        backgroundColor: Theme.surfaceVariant
                                        onClicked: { KWinService.openKdeSettings("kcm_kscreen"); settingsWin.closeSettings(); }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
