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
        visible: ConfigService.settingsVisible && KWinService.isTargetOverlayScreen(modelData)
        color: "transparent"

        anchors {
            top: true
            bottom: true
            left: true
            right: true
        }

        exclusiveZone: 0
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.keyboardFocus: visible ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None

        BackgroundEffect.blurRegion: Region {
            item: ConfigService.blurEnabled ? mainContainer : null
        }

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
            width: Math.min(680, parent.width - 40)
            height: Math.min(620, parent.height - 60)
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
                spacing: 14

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

                // Scrollable Settings Sections
                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true

                    ColumnLayout {
                        width: parent.width - 16
                        spacing: 14

                        // 1. Appearance Section
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
                                    text: "Appearance & Themes"
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
                                            implicitHeight: 34
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

                                RowLayout {
                                    Layout.fillWidth: true

                                    Text {
                                        text: "KWin Background Blur"
                                        color: Theme.foregroundMuted
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fontSizeSmall
                                        Layout.fillWidth: true
                                    }

                                    IconButton {
                                        text: ConfigService.blurEnabled ? "Enabled" : "Disabled"
                                        size: 28
                                        backgroundColor: ConfigService.blurEnabled ? Theme.primary : Theme.surfaceVariant
                                        iconColor: ConfigService.blurEnabled ? Theme.contrastColor(Theme.primary) : Theme.foregroundMuted
                                        onClicked: ConfigService.setBlurEnabled(!ConfigService.blurEnabled)
                                    }
                                }
                            }
                        }

                        // 2. Bar Configuration
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
                                    text: "Panel Bar"
                                    color: Theme.foreground
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeMedium
                                    font.bold: true
                                }

                                Text {
                                    text: "Bar Edge Position"
                                    color: Theme.foregroundMuted
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeSmall
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
                                            implicitHeight: 32
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

                                // Bar Displays Selection UI
                                Text {
                                    text: "Bar Output Displays"
                                    color: Theme.foregroundMuted
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeSmall
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 6

                                    Rectangle {
                                        id: barAllBtn
                                        Layout.fillWidth: true
                                        implicitHeight: 30
                                        radius: Theme.radiusSmall
                                        color: (ConfigService.barMonitors === "all") ? Theme.primary : (bAllMouse.containsMouse ? Theme.hover : Theme.surfaceVariant)

                                        Text {
                                            anchors.centerIn: parent
                                            text: "All Displays"
                                            color: (ConfigService.barMonitors === "all") ? Theme.contrastColor(Theme.primary) : Theme.foreground
                                            font.family: Theme.fontFamily
                                            font.pixelSize: Theme.fontSizeSmall
                                            font.bold: ConfigService.barMonitors === "all"
                                        }

                                        MouseArea {
                                            id: bAllMouse
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: ConfigService.setBarMonitors("all")
                                        }
                                    }

                                    Repeater {
                                        model: Quickshell.screens

                                        Rectangle {
                                            id: bScrBtn
                                            required property var modelData
                                            Layout.fillWidth: true
                                            implicitHeight: 30
                                            radius: Theme.radiusSmall
                                            readonly property bool isAllowed: ConfigService.isScreenAllowed(modelData, ConfigService.barMonitors)
                                            color: (ConfigService.barMonitors !== "all" && isAllowed) ? Theme.primary : (bScrMouse.containsMouse ? Theme.hover : Theme.surfaceVariant)

                                            Text {
                                                anchors.centerIn: parent
                                                text: bScrBtn.modelData.name + (bScrBtn.modelData.model ? (" (" + bScrBtn.modelData.model + ")") : "")
                                                color: (ConfigService.barMonitors !== "all" && bScrBtn.isAllowed) ? Theme.contrastColor(Theme.primary) : Theme.foreground
                                                font.family: Theme.fontFamily
                                                font.pixelSize: Theme.fontSizeSmall
                                                font.bold: ConfigService.barMonitors !== "all" && bScrBtn.isAllowed
                                                elide: Text.ElideRight
                                            }

                                            MouseArea {
                                                id: bScrMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: ConfigService.toggleBarMonitor(bScrBtn.modelData.name)
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // 3. Dock Configuration
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
                                        text: "Application Dock"
                                        color: Theme.foreground
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fontSizeMedium
                                        font.bold: true
                                        Layout.fillWidth: true
                                    }

                                    IconButton {
                                        text: ConfigService.dockEnabled ? "Enabled" : "Disabled"
                                        size: 28
                                        backgroundColor: ConfigService.dockEnabled ? Theme.primary : Theme.surfaceVariant
                                        iconColor: ConfigService.dockEnabled ? Theme.contrastColor(Theme.primary) : Theme.foregroundMuted
                                        onClicked: ConfigService.setDockEnabled(!ConfigService.dockEnabled)
                                    }
                                }

                                Text {
                                    text: "Dock Edge Position"
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

                                RowLayout {
                                    Layout.fillWidth: true

                                    Text {
                                        text: "Auto-hide Dock on Inactivity"
                                        color: Theme.foregroundMuted
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fontSizeSmall
                                        Layout.fillWidth: true
                                    }

                                    IconButton {
                                        text: ConfigService.dockAutoHide ? "Auto-hide On" : "Auto-hide Off"
                                        size: 28
                                        backgroundColor: ConfigService.dockAutoHide ? Theme.primary : Theme.surfaceVariant
                                        iconColor: ConfigService.dockAutoHide ? Theme.contrastColor(Theme.primary) : Theme.foregroundMuted
                                        onClicked: ConfigService.setDockAutoHide(!ConfigService.dockAutoHide)
                                    }
                                }

                                // Dock Displays Selection UI
                                Text {
                                    text: "Dock Output Displays"
                                    color: Theme.foregroundMuted
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeSmall
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 6

                                    Rectangle {
                                        id: dockAllBtn
                                        Layout.fillWidth: true
                                        implicitHeight: 30
                                        radius: Theme.radiusSmall
                                        color: (ConfigService.dockMonitors === "all") ? Theme.primary : (dAllMouse.containsMouse ? Theme.hover : Theme.surfaceVariant)

                                        Text {
                                            anchors.centerIn: parent
                                            text: "All Displays"
                                            color: (ConfigService.dockMonitors === "all") ? Theme.contrastColor(Theme.primary) : Theme.foreground
                                            font.family: Theme.fontFamily
                                            font.pixelSize: Theme.fontSizeSmall
                                            font.bold: ConfigService.dockMonitors === "all"
                                        }

                                        MouseArea {
                                            id: dAllMouse
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: ConfigService.setDockMonitors("all")
                                        }
                                    }

                                    Repeater {
                                        model: Quickshell.screens

                                        Rectangle {
                                            id: dScrBtn
                                            required property var modelData
                                            Layout.fillWidth: true
                                            implicitHeight: 30
                                            radius: Theme.radiusSmall
                                            readonly property bool isAllowed: ConfigService.isScreenAllowed(modelData, ConfigService.dockMonitors)
                                            color: (ConfigService.dockMonitors !== "all" && isAllowed) ? Theme.primary : (dScrMouse.containsMouse ? Theme.hover : Theme.surfaceVariant)

                                            Text {
                                                anchors.centerIn: parent
                                                text: dScrBtn.modelData.name + (dScrBtn.modelData.model ? (" (" + dScrBtn.modelData.model + ")") : "")
                                                color: (ConfigService.dockMonitors !== "all" && dScrBtn.isAllowed) ? Theme.contrastColor(Theme.primary) : Theme.foreground
                                                font.family: Theme.fontFamily
                                                font.pixelSize: Theme.fontSizeSmall
                                                font.bold: ConfigService.dockMonitors !== "all" && dScrBtn.isAllowed
                                                elide: Text.ElideRight
                                            }

                                            MouseArea {
                                                id: dScrMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: ConfigService.toggleDockMonitor(dScrBtn.modelData.name)
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // 4. Notifications Opt-in Section
                        Surface {
                            Layout.fillWidth: true
                            implicitHeight: notifCol.implicitHeight + 20
                            radius: Theme.radiusMedium
                            color: Theme.alpha(Theme.surface, 0.6)

                            ColumnLayout {
                                id: notifCol
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 8

                                RowLayout {
                                    Layout.fillWidth: true

                                    Text {
                                        text: "Desktop Notifications"
                                        color: Theme.foreground
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fontSizeMedium
                                        font.bold: true
                                        Layout.fillWidth: true
                                    }

                                    IconButton {
                                        text: ConfigService.notificationsEnabled ? "Server Active" : "Server Inactive"
                                        size: 28
                                        backgroundColor: ConfigService.notificationsEnabled ? Theme.primary : Theme.surfaceVariant
                                        iconColor: ConfigService.notificationsEnabled ? Theme.contrastColor(Theme.primary) : Theme.foregroundMuted
                                        onClicked: ConfigService.setNotificationsEnabled(!ConfigService.notificationsEnabled)
                                    }
                                }

                                Text {
                                    text: "Built-in Freedesktop notification server for standalone compositor sessions. When running in a standard KDE Plasma session, this remains disabled so KDE Plasma handles notifications without conflict."
                                    color: Theme.foregroundMuted
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeSmall
                                    wrapMode: Text.Wrap
                                    Layout.fillWidth: true
                                }
                            }
                        }

                        // 5. Compositor & Session Status
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
                                    text: "Compositor: KWin Wayland (KDE Plasma 6) | Running Windows: " + WindowService.windowCount
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
