import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import Quickshell
import Quickshell.Wayland
import Quickshell.Services.SystemTray
import "../../services"
import "../../components"

Variants {
    id: root

    model: Quickshell.screens

    PanelWindow {
        id: settingsWin
        required property var modelData

        screen: modelData
        visible: ConfigService.settingsVisible && ConfigService.settingsScreenName !== "" && modelData.name === ConfigService.settingsScreenName
        color: "transparent"

        anchors {
            top: true
            bottom: true
            left: true
            right: true
        }

        exclusiveZone: 0
        WlrLayershell.layer: WlrLayer.Top
        WlrLayershell.namespace: "quickshell:settings"
        WlrLayershell.keyboardFocus: visible ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None

        BackgroundEffect.blurRegion: Region {
            item: (ConfigService.blurEnabled && settingsWin.visible) ? mainContainer : null
        }

        function closeSettings() {
            ConfigService.settingsVisible = false;
            ConfigService.settingsScreenName = "";
        }

        MouseArea {
            anchors.fill: parent
            onClicked: settingsWin.closeSettings()
        }

        Surface {
            id: mainContainer
            anchors.centerIn: parent
            width: Math.min(700, parent.width - 40)
            height: Math.min(640, parent.height - 60)
            radius: Theme.radiusLarge
            color: Theme.alpha(Theme.background, Theme.popupOpacity)
            border.color: Theme.border
            border.width: 1
            focus: settingsWin.visible
            Keys.onEscapePressed: settingsWin.closeSettings()

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

                                RowLayout {
                                    Layout.fillWidth: true

                                    Text {
                                        text: "Panel Bar"
                                        color: Theme.foreground
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fontSizeMedium
                                        font.bold: true
                                        Layout.fillWidth: true
                                    }

                                    IconButton {
                                        text: ConfigService.barEnabled ? "Bar Enabled" : "Bar Disabled"
                                        size: 28
                                        backgroundColor: ConfigService.barEnabled ? Theme.primary : Theme.surfaceVariant
                                        iconColor: ConfigService.barEnabled ? Theme.contrastColor(Theme.primary) : Theme.foregroundMuted
                                        onClicked: ConfigService.setBarEnabled(!ConfigService.barEnabled)
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true

                                    Text {
                                        text: "Surface Mode"
                                        color: Theme.foregroundMuted
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fontSizeSmall
                                        Layout.fillWidth: true
                                    }

                                    IconButton {
                                        text: ConfigService.barFloating ? "Floating Island" : "Attached Panel"
                                        size: 28
                                        backgroundColor: ConfigService.barFloating ? Theme.primary : Theme.surfaceVariant
                                        iconColor: ConfigService.barFloating ? Theme.contrastColor(Theme.primary) : Theme.foregroundMuted
                                        onClicked: ConfigService.setBarFloating(!ConfigService.barFloating)
                                    }
                                }

                                Text {
                                    text: "Bar Edge Placement"
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
                                            color: (ConfigService.barEdge === modelData.id) ? Theme.primary : (pMouse.containsMouse ? Theme.hover : Theme.surfaceVariant)

                                            Text {
                                                anchors.centerIn: parent
                                                text: posBtn.modelData.name
                                                color: (ConfigService.barEdge === posBtn.modelData.id) ? Theme.contrastColor(Theme.primary) : Theme.foreground
                                                font.family: Theme.fontFamily
                                                font.pixelSize: Theme.fontSizeSmall
                                                font.bold: ConfigService.barEdge === posBtn.modelData.id
                                            }

                                            MouseArea {
                                                id: pMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: ConfigService.setBarEdge(posBtn.modelData.id)
                                            }
                                        }
                                    }
                                }

                                RowLayout {
                                    visible: ConfigService.barFloating
                                    Layout.fillWidth: true
                                    Text {
                                        text: "Floating Edge Offset (" + ConfigService.barEdgeOffset + " px)"
                                        color: Theme.foregroundMuted
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fontSizeSmall
                                        Layout.fillWidth: true
                                    }
                                    Slider {
                                        implicitWidth: 180
                                        minimumValue: 0
                                        maximumValue: 32
                                        stepSize: 1
                                        value: ConfigService.barEdgeOffset
                                        onValueModified: val => ConfigService.setBarEdgeOffset(Math.round(val))
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true

                                    Text {
                                        text: "Reserve Screen Space (Struts)"
                                        color: Theme.foregroundMuted
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fontSizeSmall
                                        Layout.fillWidth: true
                                    }

                                    IconButton {
                                        text: ConfigService.barReserveSpace ? "Reserved (Shrinks Apps)" : "Zero Strut (Maximized Apps Fill Screen)"
                                        size: 28
                                        backgroundColor: ConfigService.barReserveSpace ? Theme.primary : Theme.surfaceVariant
                                        iconColor: ConfigService.barReserveSpace ? Theme.contrastColor(Theme.primary) : Theme.foregroundMuted
                                        onClicked: ConfigService.setBarReserveSpace(!ConfigService.barReserveSpace)
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    Text {
                                        text: "Bar Thickness (" + ConfigService.barHeight + " px)"
                                        color: Theme.foregroundMuted
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fontSizeSmall
                                        Layout.fillWidth: true
                                    }
                                    Slider {
                                        implicitWidth: 180
                                        minimumValue: 24
                                        maximumValue: 72
                                        stepSize: 2
                                        value: ConfigService.barHeight
                                        onValueModified: val => ConfigService.setBarHeight(Math.round(val))
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    Text {
                                        text: "Bar Opacity (" + Math.round(ConfigService.barOpacity * 100) + "%)"
                                        color: Theme.foregroundMuted
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fontSizeSmall
                                        Layout.fillWidth: true
                                    }
                                    Slider {
                                        implicitWidth: 180
                                        minimumValue: 0.40
                                        maximumValue: 1.00
                                        stepSize: 0.02
                                        value: ConfigService.barOpacity
                                        onValueModified: val => ConfigService.setBarOpacity(parseFloat(val.toFixed(2)))
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

                        // System Tray Visibility Management
                        Surface {
                            id: traySettingsCard
                            Layout.fillWidth: true
                            implicitHeight: traySettingsCol.implicitHeight + 20
                            radius: Theme.radiusMedium
                            color: Theme.alpha(Theme.surface, 0.6)

                            readonly property var trayEntries: {
                                const _policies = ConfigService.trayItemPolicies || {};
                                const liveItems = SystemTray.items ? SystemTray.items.values : [];
                                const seen = {};
                                const list = [];

                                for (let i = 0; i < liveItems.length; i++) {
                                    const it = liveItems[i];
                                    if (!it) continue;
                                    const st = it.status;
                                    const key = ConfigService.getTrayItemId(it, liveItems);
                                    if (!key || seen[key]) continue;
                                    seen[key] = true;
                                    const stLower = String(st).toLowerCase();
                                    const isPassive = (st === Status.Passive || st === 0 || stLower === "passive");
                                    const isAttention = (st === Status.NeedsAttention || st === 2 || stLower === "needsattention");
                                    const stLabel = isPassive ? "Passive" : (isAttention ? "Needs Attention" : "Active");
                                    list.push({
                                        key: key,
                                        label: it.tooltipTitle || it.title || key,
                                        icon: (it.icon && String(it.icon).length > 0) ? String(it.icon) : (it.iconName || "application-x-executable"),
                                        connected: true,
                                        statusText: stLabel
                                    });
                                }

                                for (const savedKey in _policies) {
                                    if (!seen[savedKey] && !ConfigService.isLegacyTrayKeyCovered(savedKey, liveItems)) {
                                        seen[savedKey] = true;
                                        list.push({
                                            key: savedKey,
                                            label: savedKey,
                                            icon: "application-x-executable",
                                            connected: false,
                                            statusText: "Disconnected"
                                        });
                                    }
                                }

                                return list;
                            }

                            ColumnLayout {
                                id: traySettingsCol
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 10

                                Text {
                                    text: "System Tray Visibility"
                                    color: Theme.foreground
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeMedium
                                    font.bold: true
                                }

                                Text {
                                    text: "Configure per-item tray policy. Auto shows Active and Needs Attention items in the bar and moves Passive items into the overflow popup."
                                    color: Theme.foregroundMuted
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeSmall
                                    wrapMode: Text.Wrap
                                    Layout.fillWidth: true
                                }

                                Text {
                                    visible: traySettingsCard.trayEntries.length === 0
                                    text: "No system tray items currently registered."
                                    color: Theme.foregroundMuted
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeSmall
                                }

                                Repeater {
                                    model: traySettingsCard.trayEntries

                                    RowLayout {
                                        id: trayEntryRow
                                        required property var modelData
                                        Layout.fillWidth: true
                                        spacing: 8

                                        SvgIcon {
                                            icon: trayEntryRow.modelData.icon
                                            size: 18
                                        }

                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            spacing: 1

                                            Text {
                                                text: trayEntryRow.modelData.label
                                                color: trayEntryRow.modelData.connected ? Theme.foreground : Theme.foregroundMuted
                                                font.family: Theme.fontFamily
                                                font.pixelSize: Theme.fontSizeSmall
                                                font.bold: true
                                                elide: Text.ElideRight
                                                Layout.fillWidth: true
                                            }

                                            Text {
                                                text: trayEntryRow.modelData.key + " • " + trayEntryRow.modelData.statusText
                                                color: Theme.foregroundMuted
                                                font.family: Theme.fontFamily
                                                font.pixelSize: Theme.fontSizeCaption - 1
                                                elide: Text.ElideRight
                                                Layout.fillWidth: true
                                            }
                                        }

                                        Repeater {
                                            model: [
                                                { id: "auto", name: "Auto" },
                                                { id: "always", name: "Always Visible" },
                                                { id: "hidden", name: "Hidden" }
                                            ]

                                            Rectangle {
                                                id: trayPolBtn
                                                required property var modelData
                                                readonly property string activePolicy: {
                                                    const _p = ConfigService.trayItemPolicies;
                                                    return ConfigService.getTrayItemPolicy(trayEntryRow.modelData.key);
                                                }
                                                readonly property bool isSelected: activePolicy === modelData.id
                                                implicitWidth: trayPolText.implicitWidth + 16
                                                implicitHeight: 28
                                                radius: Theme.radiusSmall
                                                color: isSelected ? Theme.primary : (trayPolMouse.containsMouse ? Theme.hover : Theme.surfaceVariant)

                                                Text {
                                                    id: trayPolText
                                                    anchors.centerIn: parent
                                                    text: trayPolBtn.modelData.name
                                                    color: trayPolBtn.isSelected ? Theme.contrastColor(Theme.primary) : Theme.foreground
                                                    font.family: Theme.fontFamily
                                                    font.pixelSize: Theme.fontSizeSmall
                                                    font.bold: trayPolBtn.isSelected
                                                }

                                                MouseArea {
                                                    id: trayPolMouse
                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: ConfigService.setTrayItemPolicy(trayEntryRow.modelData.key, trayPolBtn.modelData.id)
                                                }
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
                                        text: ConfigService.dockEnabled ? "Dock Enabled" : "Dock Disabled"
                                        size: 28
                                        backgroundColor: ConfigService.dockEnabled ? Theme.primary : Theme.surfaceVariant
                                        iconColor: ConfigService.dockEnabled ? Theme.contrastColor(Theme.primary) : Theme.foregroundMuted
                                        onClicked: ConfigService.setDockEnabled(!ConfigService.dockEnabled)
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true

                                    Text {
                                        text: "Surface Mode"
                                        color: Theme.foregroundMuted
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fontSizeSmall
                                        Layout.fillWidth: true
                                    }

                                    IconButton {
                                        text: ConfigService.dockFloating ? "Floating Island" : "Attached Dock"
                                        size: 28
                                        backgroundColor: ConfigService.dockFloating ? Theme.primary : Theme.surfaceVariant
                                        iconColor: ConfigService.dockFloating ? Theme.contrastColor(Theme.primary) : Theme.foregroundMuted
                                        onClicked: ConfigService.setDockFloating(!ConfigService.dockFloating)
                                    }
                                }

                                Text {
                                    text: "Dock Edge Placement"
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
                                            color: (ConfigService.dockEdge === modelData.id) ? Theme.primary : (dpMouse.containsMouse ? Theme.hover : Theme.surfaceVariant)

                                            Text {
                                                anchors.centerIn: parent
                                                text: dPosBtn.modelData.name
                                                color: (ConfigService.dockEdge === dPosBtn.modelData.id) ? Theme.contrastColor(Theme.primary) : Theme.foreground
                                                font.family: Theme.fontFamily
                                                font.pixelSize: Theme.fontSizeSmall
                                                font.bold: ConfigService.dockEdge === dPosBtn.modelData.id
                                            }

                                            MouseArea {
                                                id: dpMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: ConfigService.setDockEdge(dPosBtn.modelData.id)
                                            }
                                        }
                                    }
                                }

                                RowLayout {
                                    visible: ConfigService.dockFloating
                                    Layout.fillWidth: true
                                    Text {
                                        text: "Floating Edge Offset (" + ConfigService.dockEdgeOffset + " px)"
                                        color: Theme.foregroundMuted
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fontSizeSmall
                                        Layout.fillWidth: true
                                    }
                                    Slider {
                                        implicitWidth: 180
                                        minimumValue: 0
                                        maximumValue: 32
                                        stepSize: 1
                                        value: ConfigService.dockEdgeOffset
                                        onValueModified: val => ConfigService.setDockEdgeOffset(Math.round(val))
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true

                                    Text {
                                        text: "Reserve Screen Space (Struts)"
                                        color: Theme.foregroundMuted
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fontSizeSmall
                                        Layout.fillWidth: true
                                    }

                                    IconButton {
                                        text: ConfigService.dockReserveSpace ? "Reserved (Shrinks Apps)" : "Zero Strut (Maximized Apps Fill Screen)"
                                        size: 28
                                        backgroundColor: ConfigService.dockReserveSpace ? Theme.primary : Theme.surfaceVariant
                                        iconColor: ConfigService.dockReserveSpace ? Theme.contrastColor(Theme.primary) : Theme.foregroundMuted
                                        onClicked: ConfigService.setDockReserveSpace(!ConfigService.dockReserveSpace)
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    Text {
                                        text: "Dock Icon Size (" + ConfigService.dockIconSize + " px)"
                                        color: Theme.foregroundMuted
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fontSizeSmall
                                        Layout.fillWidth: true
                                    }
                                    Slider {
                                        implicitWidth: 180
                                        minimumValue: 28
                                        maximumValue: 72
                                        stepSize: 2
                                        value: ConfigService.dockIconSize
                                        onValueModified: val => ConfigService.setDockIconSize(Math.round(val))
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

                                // Dock Window Filter selector (default: all)
                                Text {
                                    text: "Dock Window Filter"
                                    color: Theme.foregroundMuted
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeSmall
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 6

                                    Repeater {
                                        model: [
                                            { mode: "all", label: "All" },
                                            { mode: "desktop", label: "Desktop" },
                                            { mode: "monitor", label: "Monitor" },
                                            { mode: "desktop-and-monitor", label: "Both" }
                                        ]

                                        Rectangle {
                                            id: wfBtn
                                            required property var modelData
                                            readonly property bool selected: ConfigService.dockWindowFilter === modelData.mode
                                            Layout.fillWidth: true
                                            implicitHeight: 30
                                            radius: Theme.radiusSmall
                                            color: wfBtn.selected ? Theme.primary : (wfMouse.containsMouse ? Theme.hover : Theme.surfaceVariant)
                                            Accessible.role: Accessible.Button
                                            Accessible.name: "Window filter " + modelData.label
                                            Accessible.checked: wfBtn.selected

                                            Text {
                                                anchors.centerIn: parent
                                                text: wfBtn.modelData.label
                                                color: wfBtn.selected ? Theme.contrastColor(Theme.primary) : Theme.foreground
                                                font.family: Theme.fontFamily
                                                font.pixelSize: Theme.fontSizeSmall
                                                font.bold: wfBtn.selected
                                            }

                                            MouseArea {
                                                id: wfMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: ConfigService.setDockWindowFilter(wfBtn.modelData.mode)
                                            }
                                        }
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
