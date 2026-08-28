import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import "../../services"
import "../../components"
import "."

Variants {
    id: root

    model: Quickshell.screens

    PanelWindow {
        id: dockWindow
        required property var modelData

        screen: modelData
        color: "transparent"
        visible: ConfigService.dockEnabled && ConfigService.isScreenAllowed(modelData, ConfigService.dockMonitors)

        readonly property bool isVertical: ConfigService.dockPosition === "left" || ConfigService.dockPosition === "right"
        readonly property bool autoHide: ConfigService.dockAutoHide
        property bool mouseInside: dockHoverArea.containsMouse || edgeTriggerMouse.containsMouse
        readonly property bool isRevealed: !autoHide || mouseInside || hideTimer.running

        readonly property var unpinnedRunningApps: {
            const pinned = ApplicationService.pinnedApps || [];
            const running = WindowService.runningAppIds || [];
            const res = [];
            for (let i = 0; i < running.length; i++) {
                const r = running[i];
                if (pinned.indexOf(r) === -1) {
                    res.push(r);
                }
            }
            return res;
        }

        anchors {
            bottom: ConfigService.dockPosition === "bottom"
            top: ConfigService.dockPosition === "top"
            left: ConfigService.dockPosition === "left"
            right: ConfigService.dockPosition === "right"
        }

        implicitHeight: isVertical ? (dockSurface.implicitHeight + 24) : (ConfigService.dockIconSize + 20)
        implicitWidth: isVertical ? (ConfigService.dockIconSize + 20) : (dockSurface.implicitWidth + 24)
        exclusiveZone: autoHide ? 0 : (ConfigService.dockIconSize + 16)

        WlrLayershell.layer: WlrLayer.Top

        BackgroundEffect.blurRegion: ConfigService.blurEnabled ? Region { item: dockSurface } : null

        Timer {
            id: hideTimer
            interval: 350
            repeat: false
        }

        // Screen Edge Hotspot Trigger for Autohide Reveal
        Item {
            id: edgeTrigger
            visible: dockWindow.autoHide
            anchors {
                bottom: ConfigService.dockPosition === "bottom" ? parent.bottom : undefined
                top: ConfigService.dockPosition === "top" ? parent.top : undefined
                left: ConfigService.dockPosition === "left" ? parent.left : (dockWindow.isVertical ? undefined : parent.left)
                right: ConfigService.dockPosition === "right" ? parent.right : (dockWindow.isVertical ? undefined : parent.right)
            }
            height: dockWindow.isVertical ? parent.height : 6
            width: dockWindow.isVertical ? 6 : parent.width

            MouseArea {
                id: edgeTriggerMouse
                anchors.fill: parent
                hoverEnabled: true
                onEntered: hideTimer.restart()
            }
        }

        Surface {
            id: dockSurface
            anchors.centerIn: parent
            implicitHeight: dockWindow.isVertical ? (colLayout.implicitHeight + 16) : (ConfigService.dockIconSize + 16)
            implicitWidth: dockWindow.isVertical ? (ConfigService.dockIconSize + 16) : (rowLayout.implicitWidth + 16)
            radius: Theme.radiusLarge
            color: Theme.alpha(Theme.background, ConfigService.barOpacity)

            // Autohide Sliding Offset
            y: {
                if (!dockWindow.autoHide || dockWindow.isRevealed) return 0;
                if (ConfigService.dockPosition === "bottom") return dockSurface.implicitHeight - 2;
                if (ConfigService.dockPosition === "top") return -dockSurface.implicitHeight + 2;
                return 0;
            }
            x: {
                if (!dockWindow.autoHide || dockWindow.isRevealed) return 0;
                if (ConfigService.dockPosition === "left") return -dockSurface.implicitWidth + 2;
                if (ConfigService.dockPosition === "right") return dockSurface.implicitWidth - 2;
                return 0;
            }

            Behavior on y { NumberAnimation { duration: Theme.animDurationNormal; easing.type: Theme.animEasing } }
            Behavior on x { NumberAnimation { duration: Theme.animDurationNormal; easing.type: Theme.animEasing } }

            MouseArea {
                id: dockHoverArea
                anchors.fill: parent
                hoverEnabled: true
                onExited: {
                    if (dockWindow.autoHide) hideTimer.restart();
                }
            }

            // Horizontal Dock Layout
            RowLayout {
                id: rowLayout
                visible: !dockWindow.isVertical
                anchors.centerIn: parent
                spacing: Theme.spacingSmall

                // Launcher toggle
                IconButton {
                    size: ConfigService.dockIconSize
                    icon: "start-here-kde"
                    iconColor: Theme.primary
                    backgroundColor: Theme.alpha(Theme.primary, 0.12)
                    tooltip: "Applications"
                    onClicked: ConfigService.toggleLauncher()
                }

                DockSeparator { isVertical: false }

                // Pinned apps
                Repeater {
                    model: ApplicationService.pinnedApps

                    DockItem {
                        required property var modelData
                        appId: modelData
                        app: ApplicationService.getAppById(modelData)
                    }
                }

                // Separator for unpinned running apps
                DockSeparator {
                    isVertical: false
                    visible: dockWindow.unpinnedRunningApps.length > 0
                }

                // Unpinned running apps
                Repeater {
                    model: dockWindow.unpinnedRunningApps

                    DockItem {
                        required property var modelData
                        appId: modelData
                        app: ApplicationService.getAppById(modelData)
                    }
                }

                DockSeparator { isVertical: false }

                // Settings toggle
                IconButton {
                    size: ConfigService.dockIconSize
                    icon: "preferences-system"
                    iconColor: Theme.foreground
                    tooltip: "Settings"
                    onClicked: ConfigService.toggleSettings()
                }
            }

            // Vertical Dock Layout
            ColumnLayout {
                id: colLayout
                visible: dockWindow.isVertical
                anchors.centerIn: parent
                spacing: Theme.spacingSmall

                // Launcher toggle
                IconButton {
                    size: ConfigService.dockIconSize
                    icon: "start-here-kde"
                    iconColor: Theme.primary
                    backgroundColor: Theme.alpha(Theme.primary, 0.12)
                    tooltip: "Applications"
                    onClicked: ConfigService.toggleLauncher()
                }

                DockSeparator { isVertical: true }

                // Pinned apps
                Repeater {
                    model: ApplicationService.pinnedApps

                    DockItem {
                        required property var modelData
                        appId: modelData
                        app: ApplicationService.getAppById(modelData)
                    }
                }

                // Separator for unpinned running apps
                DockSeparator {
                    isVertical: true
                    visible: dockWindow.unpinnedRunningApps.length > 0
                }

                // Unpinned running apps
                Repeater {
                    model: dockWindow.unpinnedRunningApps

                    DockItem {
                        required property var modelData
                        appId: modelData
                        app: ApplicationService.getAppById(modelData)
                    }
                }

                DockSeparator { isVertical: true }

                // Settings toggle
                IconButton {
                    size: ConfigService.dockIconSize
                    icon: "preferences-system"
                    iconColor: Theme.foreground
                    tooltip: "Settings"
                    onClicked: ConfigService.toggleSettings()
                }
            }
        }
    }
}
