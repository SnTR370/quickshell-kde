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

        // Layout preset preview state (session-only, never persisted)
        property string pendingPresetId: ""
        property string presetResultMessage: ""
        // DOCK-011: stack management session state (never persisted)
        property string newStackTitle: ""
        property string newStackPath: ""
        property string stackMessage: ""
        property string expandedStackId: ""
        property string stackQueryText: ""
        // DOCK-012: per-monitor profile editor session state (never persisted)
        property string expandedProfileScreen: ""

        function toggleExpandedStack(id) {
            if (settingsWin.expandedStackId === id) {
                settingsWin.expandedStackId = "";
            } else {
                settingsWin.expandedStackId = id;
                settingsWin.stackQueryText = "";
            }
        }

        function toggleExpandedProfileScreen(name) {
            settingsWin.expandedProfileScreen =
                (settingsWin.expandedProfileScreen === name) ? "" : name;
        }

        function addFolderStack() {
            const id = ConfigService.addDockStack("folder", settingsWin.newStackTitle, settingsWin.newStackPath);
            if (id) {
                settingsWin.stackMessage = "Folder stack added.";
                settingsWin.newStackTitle = "";
                settingsWin.newStackPath = "";
            } else {
                settingsWin.stackMessage = "Folder stack needs a title and an absolute folder path.";
            }
        }

        function addAppsStack() {
            const id = ConfigService.addDockStack("apps", settingsWin.newStackTitle, "");
            if (id) {
                settingsWin.stackMessage = "App stack added — drag applications onto it, or expand it below to add some.";
                settingsWin.newStackTitle = "";
            } else {
                settingsWin.stackMessage = "App stack needs a title.";
            }
        }

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

                        // 0. Layout Presets
                        Surface {
                            id: presetCard
                            Layout.fillWidth: true
                            implicitHeight: presetCol.implicitHeight + 20
                            radius: Theme.radiusMedium
                            color: Theme.alpha(Theme.surface, 0.6)

                            ColumnLayout {
                                id: presetCol
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 10

                                Text {
                                    text: "Layout Presets"
                                    color: Theme.foreground
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeMedium
                                    font.bold: true
                                }

                                Text {
                                    text: "Ready-to-use starting points for the Bar and Dock. Select a preset to preview exactly what will change — pinned applications, display selection, theme and other preferences are always preserved, and everything stays fully customizable afterwards."
                                    color: Theme.foregroundMuted
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeSmall
                                    wrapMode: Text.Wrap
                                    Layout.fillWidth: true
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    Repeater {
                                        model: ConfigService.layoutPresetList

                                        Rectangle {
                                            id: presetBtn
                                            required property var modelData
                                            readonly property bool isActive: ConfigService.layoutPresetMatches(modelData.id)
                                            readonly property bool isPending: settingsWin.pendingPresetId === modelData.id
                                            Layout.fillWidth: true
                                            implicitHeight: 78
                                            radius: Theme.radiusSmall
                                            color: presetBtn.isPending ? Theme.primary
                                                 : (presetBtn.isActive ? Theme.alpha(Theme.primary, 0.25)
                                                 : (prMouse.containsMouse ? Theme.hover : Theme.surfaceVariant))
                                            Accessible.role: Accessible.Button
                                            Accessible.name: "Layout preset " + modelData.name

                                            ColumnLayout {
                                                anchors.fill: parent
                                                anchors.margins: 8
                                                spacing: 2

                                                Item { Layout.fillHeight: true }

                                                RowLayout {
                                                    Layout.fillWidth: true
                                                    spacing: 4

                                                    SvgIcon {
                                                        icon: presetBtn.modelData.icon
                                                        size: 14
                                                        color: presetBtn.isPending ? Theme.contrastColor(Theme.primary) : Theme.primary
                                                    }

                                                    Text {
                                                        text: presetBtn.modelData.name
                                                        color: presetBtn.isPending ? Theme.contrastColor(Theme.primary) : Theme.foreground
                                                        font.family: Theme.fontFamily
                                                        font.pixelSize: Theme.fontSizeSmall
                                                        font.bold: true
                                                        elide: Text.ElideRight
                                                        Layout.fillWidth: true
                                                    }
                                                }

                                                Text {
                                                    text: presetBtn.modelData.description
                                                    color: presetBtn.isPending ? Theme.contrastColor(Theme.primary) : Theme.foregroundMuted
                                                    font.family: Theme.fontFamily
                                                    font.pixelSize: Theme.fontSizeCaption - 1
                                                    wrapMode: Text.Wrap
                                                    elide: Text.ElideRight
                                                    maximumLineCount: 3
                                                    Layout.fillWidth: true
                                                }

                                                Item { Layout.fillHeight: true }
                                            }

                                            MouseArea {
                                                id: prMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: {
                                                    settingsWin.presetResultMessage = "";
                                                    settingsWin.pendingPresetId = presetBtn.modelData.id;
                                                }
                                            }
                                        }
                                    }
                                }

                                // Change preview: shows precisely what applying the
                                // pending preset will change before anything is applied.
                                Rectangle {
                                    id: presetPreview
                                    visible: settingsWin.pendingPresetId !== ""
                                    Layout.fillWidth: true
                                    implicitHeight: previewCol.implicitHeight + 16
                                    radius: Theme.radiusSmall
                                    color: Theme.alpha(Theme.surface, 0.6)
                                    border.color: Theme.border
                                    border.width: 1

                                    readonly property var pendingChanges: settingsWin.pendingPresetId !== ""
                                        ? (ConfigService.getLayoutPresetDiff(settingsWin.pendingPresetId) || [])
                                        : []

                                    ColumnLayout {
                                        id: previewCol
                                        anchors.fill: parent
                                        anchors.margins: 10
                                        spacing: 8

                                        Text {
                                            readonly property var pendingPreset: settingsWin.pendingPresetId !== ""
                                                ? ConfigService.getLayoutPreset(settingsWin.pendingPresetId)
                                                : null
                                            text: "What will change — " + (pendingPreset ? pendingPreset.name : "")
                                            color: Theme.foreground
                                            font.family: Theme.fontFamily
                                            font.pixelSize: Theme.fontSizeSmall
                                            font.bold: true
                                        }

                                        Text {
                                            visible: presetPreview.pendingChanges.length === 0
                                            text: "This layout is already active. Nothing to change."
                                            color: Theme.foregroundMuted
                                            font.family: Theme.fontFamily
                                            font.pixelSize: Theme.fontSizeSmall
                                            wrapMode: Text.Wrap
                                            Layout.fillWidth: true
                                        }

                                        Repeater {
                                            model: presetPreview.pendingChanges

                                            RowLayout {
                                                id: changeRow
                                                required property var modelData
                                                Layout.fillWidth: true
                                                spacing: 6

                                                Text {
                                                    text: changeRow.modelData.label
                                                    color: Theme.foregroundMuted
                                                    font.family: Theme.fontFamily
                                                    font.pixelSize: Theme.fontSizeCaption
                                                    elide: Text.ElideRight
                                                    Layout.fillWidth: true
                                                }

                                                Text {
                                                    text: changeRow.modelData.fromText
                                                    color: Theme.foregroundMuted
                                                    font.family: Theme.fontFamily
                                                    font.pixelSize: Theme.fontSizeCaption
                                                    elide: Text.ElideMiddle
                                                }

                                                Text {
                                                    text: "→"
                                                    color: Theme.foregroundMuted
                                                    font.family: Theme.fontFamily
                                                    font.pixelSize: Theme.fontSizeCaption
                                                }

                                                Text {
                                                    text: changeRow.modelData.toText
                                                    color: Theme.foreground
                                                    font.family: Theme.fontFamily
                                                    font.pixelSize: Theme.fontSizeCaption
                                                    font.bold: true
                                                    elide: Text.ElideMiddle
                                                }
                                            }
                                        }

                                        Text {
                                            visible: settingsWin.presetResultMessage !== ""
                                            text: settingsWin.presetResultMessage
                                            color: Theme.primary
                                            font.family: Theme.fontFamily
                                            font.pixelSize: Theme.fontSizeSmall
                                            wrapMode: Text.Wrap
                                            Layout.fillWidth: true
                                        }

                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: 8

                                            Item { Layout.fillWidth: true }

                                            IconButton {
                                                text: "Cancel"
                                                size: 28
                                                backgroundColor: Theme.surfaceVariant
                                                onClicked: {
                                                    settingsWin.pendingPresetId = "";
                                                    settingsWin.presetResultMessage = "";
                                                }
                                            }

                                            IconButton {
                                                text: "Apply Preset"
                                                size: 28
                                                enabled: presetPreview.pendingChanges.length > 0
                                                backgroundColor: enabled ? Theme.primary : Theme.surfaceVariant
                                                iconColor: enabled ? Theme.contrastColor(Theme.primary) : Theme.foregroundMuted
                                                onClicked: {
                                                    const res = ConfigService.applyLayoutPreset(settingsWin.pendingPresetId);
                                                    settingsWin.presetResultMessage = res.ok
                                                        ? (res.alreadyActive ? "This layout is already active." : "Preset applied.")
                                                        : ("Could not apply preset: " + res.reason);
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

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
                                        text: "Dock Opacity (" + Math.round(ConfigService.dockOpacity * 100) + "%)"
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
                                        value: ConfigService.dockOpacity
                                        onValueModified: val => ConfigService.setDockOpacity(parseFloat(val.toFixed(2)))
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true

                                    Text {
                                        text: "Magnify Dock Icons (pointer-follow parabolic zoom)"
                                        color: Theme.foregroundMuted
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fontSizeSmall
                                        Layout.fillWidth: true
                                    }

                                    IconButton {
                                        text: ConfigService.dockMagnification ? "Magnification On" : "Magnification Off"
                                        size: 28
                                        backgroundColor: ConfigService.dockMagnification ? Theme.primary : Theme.surfaceVariant
                                        iconColor: ConfigService.dockMagnification ? Theme.contrastColor(Theme.primary) : Theme.foregroundMuted
                                        onClicked: ConfigService.setDockMagnification(!ConfigService.dockMagnification)
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    visible: ConfigService.dockMagnification

                                    Text {
                                        text: "Magnification Strength (" + ConfigService.dockMagnifyMaxScale.toFixed(2) + "x max)"
                                        color: Theme.foregroundMuted
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fontSizeSmall
                                        Layout.fillWidth: true
                                    }

                                    Slider {
                                        implicitWidth: 180
                                        minimumValue: 1.1
                                        maximumValue: 2.5
                                        stepSize: 0.05
                                        value: ConfigService.dockMagnifyMaxScale
                                        onValueModified: val => ConfigService.setDockMagnifyMaxScale(val)
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    visible: ConfigService.dockMagnification

                                    Text {
                                        text: "Magnification Radius (" + ConfigService.dockMagnifyRadius + " px)"
                                        color: Theme.foregroundMuted
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fontSizeSmall
                                        Layout.fillWidth: true
                                    }

                                    Slider {
                                        implicitWidth: 180
                                        minimumValue: 24
                                        maximumValue: 240
                                        stepSize: 2
                                        value: ConfigService.dockMagnifyRadius
                                        onValueModified: val => ConfigService.setDockMagnifyRadius(Math.round(val))
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

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    Text {
                                        text: "Intellihide (hide only when a window overlaps; overrides Auto-hide)"
                                        color: Theme.foregroundMuted
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fontSizeSmall
                                        wrapMode: Text.WordWrap
                                        Layout.fillWidth: true
                                    }

                                    IconButton {
                                        text: ConfigService.dockIntellihide ? "Intellihide On" : "Intellihide Off"
                                        size: 28
                                        backgroundColor: ConfigService.dockIntellihide ? Theme.primary : Theme.surfaceVariant
                                        iconColor: ConfigService.dockIntellihide ? Theme.contrastColor(Theme.primary) : Theme.foregroundMuted
                                        onClicked: ConfigService.setDockIntellihide(!ConfigService.dockIntellihide)
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    Text {
                                        text: "Meta+1..9 Activate Pinned Applications (KWin global shortcuts; activate or cycle windows)"
                                        color: Theme.foregroundMuted
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fontSizeSmall
                                        wrapMode: Text.WordWrap
                                        Layout.fillWidth: true
                                    }

                                    IconButton {
                                        text: ConfigService.dockMetaShortcuts ? "Meta Shortcuts On" : "Meta Shortcuts Off"
                                        size: 28
                                        backgroundColor: ConfigService.dockMetaShortcuts ? Theme.primary : Theme.surfaceVariant
                                        iconColor: ConfigService.dockMetaShortcuts ? Theme.contrastColor(Theme.primary) : Theme.foregroundMuted
                                        onClicked: ConfigService.setDockMetaShortcuts(!ConfigService.dockMetaShortcuts)
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

                        // 3b. Dock Stacks (DOCK-011)
                        Surface {
                            id: stacksCard
                            Layout.fillWidth: true
                            implicitHeight: stacksCol.implicitHeight + 20
                            radius: Theme.radiusMedium
                            color: Theme.alpha(Theme.surface, 0.6)

                            ColumnLayout {
                                id: stacksCol
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 10

                                Text {
                                    text: "Dock Stacks"
                                    color: Theme.foreground
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeMedium
                                    font.bold: true
                                }

                                Text {
                                    text: "Folder shortcuts and application groups pinned in the Dock. Click a stack in the Dock to open it; drag applications onto an app stack to add them; right-click a stack to remove it."
                                    color: Theme.foregroundMuted
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeSmall
                                    wrapMode: Text.WordWrap
                                    Layout.fillWidth: true
                                }

                                // Existing stacks
                                Repeater {
                                    model: ConfigService.dockStacks

                                    Surface {
                                        id: stackRow
                                        required property var modelData
                                        readonly property bool isFolderStack: modelData.type === "folder"
                                        readonly property bool expanded: settingsWin.expandedStackId === modelData.id
                                        Layout.fillWidth: true
                                        implicitHeight: stackRowCol.implicitHeight + 16
                                        radius: Theme.radiusSmall
                                        color: Theme.alpha(Theme.background, 0.5)

                                        ColumnLayout {
                                            id: stackRowCol
                                            anchors.fill: parent
                                            anchors.margins: 8
                                            spacing: 8

                                            RowLayout {
                                                Layout.fillWidth: true
                                                spacing: 8

                                                SvgIcon {
                                                    icon: stackRow.modelData.icon
                                                        || (stackRow.isFolderStack ? "folder" : "applications-all")
                                                    size: 20
                                                    color: Theme.primary
                                                }

                                                Text {
                                                    text: stackRow.modelData.title
                                                        + (stackRow.isFolderStack ? " (folder)" : " (apps)")
                                                    color: Theme.foreground
                                                    font.family: Theme.fontFamily
                                                    font.pixelSize: Theme.fontSizeSmall
                                                    font.bold: true
                                                    elide: Text.ElideRight
                                                }

                                                Text {
                                                    visible: stackRow.isFolderStack
                                                    text: stackRow.modelData.path || ""
                                                    color: Theme.foregroundMuted
                                                    font.family: Theme.fontFamily
                                                    font.pixelSize: Theme.fontSizeSmall
                                                    elide: Text.ElideMiddle
                                                    Layout.fillWidth: true
                                                }

                                                Item { Layout.fillWidth: !stackRow.isFolderStack }

                                                Text {
                                                    visible: !stackRow.isFolderStack
                                                    text: (stackRow.modelData.appIds ? stackRow.modelData.appIds.length : 0) + " apps"
                                                    color: Theme.foregroundMuted
                                                    font.family: Theme.fontFamily
                                                    font.pixelSize: Theme.fontSizeSmall
                                                }

                                                IconButton {
                                                    size: 24
                                                    icon: stackRow.expanded ? "arrow-up" : "arrow-down"
                                                    iconColor: Theme.foreground
                                                    onClicked: settingsWin.toggleExpandedStack(stackRow.modelData.id)
                                                }

                                                IconButton {
                                                    size: 24
                                                    icon: "edit-delete"
                                                    iconColor: Theme.error
                                                    onClicked: {
                                                        if (ConfigService.removeDockStack(stackRow.modelData.id)) {
                                                            settingsWin.stackMessage = "Stack removed.";
                                                        }
                                                    }
                                                }
                                            }

                                            // Expanded: app stack membership + search-add
                                            ColumnLayout {
                                                visible: stackRow.expanded && !stackRow.isFolderStack
                                                Layout.fillWidth: true
                                                spacing: 6

                                                Repeater {
                                                    model: stackRow.modelData.appIds || []

                                                    RowLayout {
                                                        id: memberRow
                                                        required property var modelData
                                                        readonly property var memberApp: ApplicationService.getAppById(modelData)
                                                        spacing: 6

                                                        SvgIcon {
                                                            icon: memberRow.memberApp ? memberRow.memberApp.icon : "application-x-executable"
                                                            size: 16
                                                        }

                                                        Text {
                                                            text: ApplicationService.cleanAppName(
                                                                memberRow.memberApp ? memberRow.memberApp.name : memberRow.modelData)
                                                            color: Theme.foreground
                                                            font.family: Theme.fontFamily
                                                            font.pixelSize: Theme.fontSizeSmall
                                                        }

                                                        IconButton {
                                                            size: 20
                                                            icon: "window-close"
                                                            iconColor: Theme.error
                                                            onClicked: ConfigService.removeAppFromDockStack(
                                                                stackRow.modelData.id, memberRow.modelData)
                                                        }

                                                        Item { Layout.fillWidth: true }
                                                    }
                                                }

                                                Text {
                                                    visible: !(stackRow.modelData.appIds && stackRow.modelData.appIds.length > 0)
                                                    text: "No applications yet — search below or drag icons onto the stack in the Dock."
                                                    color: Theme.foregroundMuted
                                                    font.family: Theme.fontFamily
                                                    font.pixelSize: Theme.fontSizeSmall
                                                    wrapMode: Text.WordWrap
                                                    Layout.fillWidth: true
                                                }

                                                TextField {
                                                    Layout.fillWidth: true
                                                    placeholderText: "Search applications to add…"
                                                    color: Theme.foreground
                                                    font.family: Theme.fontFamily
                                                    font.pixelSize: Theme.fontSizeSmall
                                                    text: settingsWin.stackQueryText
                                                    onTextChanged: settingsWin.stackQueryText = text
                                                }

                                                Flow {
                                                    visible: settingsWin.stackQueryText.trim().length > 1
                                                    Layout.fillWidth: true
                                                    spacing: 6

                                                    Repeater {
                                                        model: settingsWin.stackQueryText.trim().length > 1
                                                            ? ApplicationService.search(settingsWin.stackQueryText, "all").slice(0, 6)
                                                            : []

                                                        Rectangle {
                                                            id: resultChip
                                                            required property var modelData
                                                            readonly property bool alreadyMember: (stackRow.modelData.appIds || []).indexOf(modelData.id) !== -1
                                                            implicitWidth: chipRow.implicitWidth + 16
                                                            implicitHeight: 28
                                                            radius: Theme.radiusSmall
                                                            color: chipMouse.containsMouse ? Theme.hover : Theme.surfaceVariant

                                                            RowLayout {
                                                                id: chipRow
                                                                anchors.centerIn: parent
                                                                spacing: 6

                                                                SvgIcon {
                                                                    icon: resultChip.modelData.icon || "application-x-executable"
                                                                    size: 14
                                                                }

                                                                Text {
                                                                    text: resultChip.alreadyMember
                                                                        ? "✓ " + resultChip.modelData.name
                                                                        : "+ " + resultChip.modelData.name
                                                                    color: Theme.foreground
                                                                    font.family: Theme.fontFamily
                                                                    font.pixelSize: Theme.fontSizeSmall
                                                                }
                                                            }

                                                            MouseArea {
                                                                id: chipMouse
                                                                anchors.fill: parent
                                                                hoverEnabled: true
                                                                cursorShape: Qt.PointingHandCursor
                                                                onClicked: {
                                                                    if (!resultChip.alreadyMember) {
                                                                        ConfigService.addAppToDockStack(
                                                                            stackRow.modelData.id, resultChip.modelData.id);
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }

                                            // Expanded: folder stack path editor
                                            ColumnLayout {
                                                visible: stackRow.expanded && stackRow.isFolderStack
                                                Layout.fillWidth: true
                                                spacing: 6

                                                TextField {
                                                    id: folderPathField
                                                    Layout.fillWidth: true
                                                    placeholderText: "Absolute folder path (e.g. /home/user/Downloads)"
                                                    color: Theme.foreground
                                                    font.family: Theme.fontFamily
                                                    font.pixelSize: Theme.fontSizeSmall
                                                    text: stackRow.modelData.path || ""
                                                }

                                                RowLayout {
                                                    spacing: 8

                                                    IconButton {
                                                        size: 26
                                                        text: "Save Path"
                                                        icon: "document-save"
                                                        iconColor: Theme.foreground
                                                        onClicked: {
                                                            if (ConfigService.setDockStackPath(stackRow.modelData.id, folderPathField.text)) {
                                                                settingsWin.stackMessage = "Stack folder updated.";
                                                            } else {
                                                                settingsWin.stackMessage = "Invalid folder path (must be absolute, no ..).";
                                                            }
                                                        }
                                                    }

                                                    Item { Layout.fillWidth: true }
                                                }
                                            }
                                        }
                                    }
                                }

                                Text {
                                    visible: (ConfigService.dockStacks || []).length === 0
                                    text: "No stacks yet."
                                    color: Theme.foregroundMuted
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeSmall
                                }

                                // Create new stacks
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    TextField {
                                        Layout.fillWidth: true
                                        placeholderText: "Stack title"
                                        color: Theme.foreground
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fontSizeSmall
                                        text: settingsWin.newStackTitle
                                        onTextChanged: settingsWin.newStackTitle = text
                                    }

                                    TextField {
                                        Layout.fillWidth: true
                                        placeholderText: "Folder path (folder stacks only)"
                                        color: Theme.foreground
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fontSizeSmall
                                        text: settingsWin.newStackPath
                                        onTextChanged: settingsWin.newStackPath = text
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    IconButton {
                                        text: "Add Folder Stack"
                                        size: 28
                                        icon: "folder-new"
                                        iconColor: Theme.foreground
                                        onClicked: settingsWin.addFolderStack()
                                    }

                                    IconButton {
                                        text: "Add App Stack"
                                        size: 28
                                        icon: "list-add"
                                        iconColor: Theme.foreground
                                        onClicked: settingsWin.addAppsStack()
                                    }

                                    Item { Layout.fillWidth: true }
                                }

                                Text {
                                    visible: settingsWin.stackMessage.length > 0
                                    text: settingsWin.stackMessage
                                    color: Theme.foregroundMuted
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeSmall
                                    wrapMode: Text.WordWrap
                                    Layout.fillWidth: true
                                }
                            }
                        }

                        // 3c. Per-Monitor Dock Profiles (DOCK-012)
                        Surface {
                            id: profilesCard
                            Layout.fillWidth: true
                            implicitHeight: profilesCol.implicitHeight + 20
                            radius: Theme.radiusMedium
                            color: Theme.alpha(Theme.surface, 0.6)

                            ColumnLayout {
                                id: profilesCol
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 10

                                Text {
                                    text: "Per-Monitor Dock Profiles"
                                    color: Theme.foreground
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeMedium
                                    font.bold: true
                                }

                                Text {
                                    text: "Independent Dock layout and appearance per display. The global settings above stay the defaults; each display can override edge, floating, offset, icon size, auto-hide and intellihide. Pinned applications, stacks and display selection stay shared across all Docks."
                                    color: Theme.foregroundMuted
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeSmall
                                    wrapMode: Text.WordWrap
                                    Layout.fillWidth: true
                                }

                                Repeater {
                                    model: Quickshell.screens

                                    Surface {
                                        id: profRow
                                        required property var modelData
                                        readonly property string screenName: modelData ? modelData.name : ""
                                        // Live override set / effective values for this output.
                                        readonly property var overrides: ConfigService.getDockMonitorProfile(profRow.screenName)
                                        readonly property var eff: ConfigService.effectiveDockProfile(profRow.screenName)
                                        readonly property bool hasOverride: overrides !== null
                                        readonly property bool expanded: settingsWin.expandedProfileScreen === profRow.screenName
                                        Layout.fillWidth: true
                                        implicitHeight: profRowCol.implicitHeight + 16
                                        radius: Theme.radiusSmall
                                        color: Theme.alpha(Theme.background, 0.5)

                                        ColumnLayout {
                                            id: profRowCol
                                            anchors.fill: parent
                                            anchors.margins: 8
                                            spacing: 8

                                            RowLayout {
                                                Layout.fillWidth: true
                                                spacing: 8

                                                Text {
                                                    text: profRow.screenName
                                                        + (profRow.modelData && profRow.modelData.model ? (" (" + profRow.modelData.model + ")") : "")
                                                    color: Theme.foreground
                                                    font.family: Theme.fontFamily
                                                    font.pixelSize: Theme.fontSizeSmall
                                                    font.bold: true
                                                    elide: Text.ElideRight
                                                }

                                                Text {
                                                    text: profRow.hasOverride ? "Overrides: " + Object.keys(profRow.overrides).join(", ") : "Using global settings"
                                                    color: profRow.hasOverride ? Theme.primary : Theme.foregroundMuted
                                                    font.family: Theme.fontFamily
                                                    font.pixelSize: Theme.fontSizeSmall
                                                    elide: Text.ElideMiddle
                                                    Layout.fillWidth: true
                                                }

                                                IconButton {
                                                    size: 24
                                                    icon: profRow.expanded ? "arrow-up" : "arrow-down"
                                                    iconColor: Theme.foreground
                                                    onClicked: settingsWin.toggleExpandedProfileScreen(profRow.screenName)
                                                }

                                                IconButton {
                                                    visible: profRow.hasOverride
                                                    size: 24
                                                    icon: "edit-delete"
                                                    iconColor: Theme.error
                                                    onClicked: ConfigService.clearDockMonitorProfile(profRow.screenName)
                                                }
                                            }

                                            // Per-output override editor
                                            ColumnLayout {
                                                visible: profRow.expanded
                                                Layout.fillWidth: true
                                                spacing: 8

                                                Text {
                                                    text: "Edge Placement (effective: " + profRow.eff.edge + ")"
                                                    color: Theme.foregroundMuted
                                                    font.family: Theme.fontFamily
                                                    font.pixelSize: Theme.fontSizeSmall
                                                }

                                                RowLayout {
                                                    Layout.fillWidth: true
                                                    spacing: 6

                                                    Repeater {
                                                        model: [
                                                            { id: "", name: "Default", key: "edge" },
                                                            { id: "bottom", name: "Bottom", key: "edge" },
                                                            { id: "top", name: "Top", key: "edge" },
                                                            { id: "left", name: "Left", key: "edge" },
                                                            { id: "right", name: "Right", key: "edge" }
                                                        ]

                                                        Rectangle {
                                                            id: mpEdgeBtn
                                                            required property var modelData
                                                            Layout.fillWidth: true
                                                            implicitHeight: 28
                                                            radius: Theme.radiusSmall
                                                            readonly property bool selected: (mpEdgeBtn.modelData.id === "")
                                                                ? !(profRow.overrides && profRow.overrides.edge !== undefined)
                                                                : (profRow.overrides && profRow.overrides.edge === mpEdgeBtn.modelData.id)
                                                            color: selected ? Theme.primary : (mpEdgeMouse.containsMouse ? Theme.hover : Theme.surfaceVariant)

                                                            Text {
                                                                anchors.centerIn: parent
                                                                text: mpEdgeBtn.modelData.name
                                                                color: mpEdgeBtn.selected ? Theme.contrastColor(Theme.primary) : Theme.foreground
                                                                font.family: Theme.fontFamily
                                                                font.pixelSize: Theme.fontSizeSmall
                                                                font.bold: mpEdgeBtn.selected
                                                            }

                                                            MouseArea {
                                                                id: mpEdgeMouse
                                                                anchors.fill: parent
                                                                hoverEnabled: true
                                                                cursorShape: Qt.PointingHandCursor
                                                                onClicked: {
                                                                    if (mpEdgeBtn.modelData.id === "") {
                                                                        ConfigService.clearDockMonitorProfileKey(profRow.screenName, "edge");
                                                                    } else {
                                                                        ConfigService.setDockMonitorProfileKey(profRow.screenName, "edge", mpEdgeBtn.modelData.id);
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    }
                                                }

                                                RowLayout {
                                                    Layout.fillWidth: true

                                                    Text {
                                                        text: "Floating (effective: " + (profRow.eff.floating ? "floating" : "attached") + ")"
                                                        color: Theme.foregroundMuted
                                                        font.family: Theme.fontFamily
                                                        font.pixelSize: Theme.fontSizeSmall
                                                        Layout.fillWidth: true
                                                    }

                                                    IconButton {
                                                        text: (profRow.overrides && profRow.overrides.floating !== undefined)
                                                            ? (profRow.overrides.floating ? "Floating (override)" : "Attached (override)")
                                                            : ("Use " + (profRow.eff.floating ? "Floating" : "Attached"))
                                                        size: 26
                                                        backgroundColor: (profRow.overrides && profRow.overrides.floating !== undefined) ? Theme.primary : Theme.surfaceVariant
                                                        iconColor: (profRow.overrides && profRow.overrides.floating !== undefined) ? Theme.contrastColor(Theme.primary) : Theme.foregroundMuted
                                                        onClicked: ConfigService.setDockMonitorProfileKey(profRow.screenName, "floating", !profRow.eff.floating)
                                                    }

                                                    IconButton {
                                                        visible: profRow.overrides && profRow.overrides.floating !== undefined
                                                        text: "Default"
                                                        size: 26
                                                        iconColor: Theme.foregroundMuted
                                                        onClicked: ConfigService.clearDockMonitorProfileKey(profRow.screenName, "floating")
                                                    }
                                                }

                                                RowLayout {
                                                    Layout.fillWidth: true
                                                    Text {
                                                        text: "Icon Size (" + profRow.eff.iconSize + " px)"
                                                        color: Theme.foregroundMuted
                                                        font.family: Theme.fontFamily
                                                        font.pixelSize: Theme.fontSizeSmall
                                                        Layout.fillWidth: true
                                                    }
                                                    Slider {
                                                        implicitWidth: 150
                                                        minimumValue: 20
                                                        maximumValue: 128
                                                        stepSize: 2
                                                        value: profRow.eff.iconSize
                                                        onValueModified: val => ConfigService.setDockMonitorProfileKey(profRow.screenName, "iconSize", Math.round(val))
                                                    }
                                                    IconButton {
                                                        visible: profRow.overrides && profRow.overrides.iconSize !== undefined
                                                        text: "Default"
                                                        size: 26
                                                        iconColor: Theme.foregroundMuted
                                                        onClicked: ConfigService.clearDockMonitorProfileKey(profRow.screenName, "iconSize")
                                                    }
                                                }

                                                RowLayout {
                                                    Layout.fillWidth: true
                                                    Text {
                                                        text: "Floating Edge Offset (" + profRow.eff.edgeOffset + " px)"
                                                        color: Theme.foregroundMuted
                                                        font.family: Theme.fontFamily
                                                        font.pixelSize: Theme.fontSizeSmall
                                                        Layout.fillWidth: true
                                                    }
                                                    Slider {
                                                        implicitWidth: 150
                                                        minimumValue: 0
                                                        maximumValue: 64
                                                        stepSize: 1
                                                        value: profRow.eff.edgeOffset
                                                        onValueModified: val => ConfigService.setDockMonitorProfileKey(profRow.screenName, "edgeOffset", Math.round(val))
                                                    }
                                                    IconButton {
                                                        visible: profRow.overrides && profRow.overrides.edgeOffset !== undefined
                                                        text: "Default"
                                                        size: 26
                                                        iconColor: Theme.foregroundMuted
                                                        onClicked: ConfigService.clearDockMonitorProfileKey(profRow.screenName, "edgeOffset")
                                                    }
                                                }

                                                RowLayout {
                                                    Layout.fillWidth: true

                                                    Text {
                                                        text: "Auto-hide / Intellihide (effective: " + (profRow.eff.autoHide ? (profRow.eff.intellihide ? "intellihide" : "auto-hide") : "off") + ")"
                                                        color: Theme.foregroundMuted
                                                        font.family: Theme.fontFamily
                                                        font.pixelSize: Theme.fontSizeSmall
                                                        Layout.fillWidth: true
                                                    }

                                                    IconButton {
                                                        text: profRow.eff.autoHide ? "Auto-hide On" : "Auto-hide Off"
                                                        size: 26
                                                        backgroundColor: (profRow.overrides && profRow.overrides.autoHide !== undefined) ? Theme.primary : Theme.surfaceVariant
                                                        iconColor: (profRow.overrides && profRow.overrides.autoHide !== undefined) ? Theme.contrastColor(Theme.primary) : Theme.foregroundMuted
                                                        onClicked: ConfigService.setDockMonitorProfileKey(profRow.screenName, "autoHide", !profRow.eff.autoHide)
                                                    }

                                                    IconButton {
                                                        text: profRow.eff.intellihide ? "Intellihide On" : "Intellihide Off"
                                                        size: 26
                                                        backgroundColor: (profRow.overrides && profRow.overrides.intellihide !== undefined) ? Theme.primary : Theme.surfaceVariant
                                                        iconColor: (profRow.overrides && profRow.overrides.intellihide !== undefined) ? Theme.contrastColor(Theme.primary) : Theme.foregroundMuted
                                                        onClicked: ConfigService.setDockMonitorProfileKey(profRow.screenName, "intellihide", !profRow.eff.intellihide)
                                                    }

                                                    IconButton {
                                                        visible: profRow.overrides && (profRow.overrides.autoHide !== undefined || profRow.overrides.intellihide !== undefined)
                                                        text: "Default"
                                                        size: 26
                                                        iconColor: Theme.foregroundMuted
                                                        onClicked: {
                                                            ConfigService.clearDockMonitorProfileKey(profRow.screenName, "autoHide");
                                                            ConfigService.clearDockMonitorProfileKey(profRow.screenName, "intellihide");
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }

                                Text {
                                    visible: Quickshell.screens.length === 0
                                    text: "No displays detected."
                                    color: Theme.foregroundMuted
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeSmall
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
