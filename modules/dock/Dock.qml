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

        readonly property string edge: ConfigService.dockEdge
        readonly property bool isVertical: edge === "left" || edge === "right"
        readonly property bool isFloating: ConfigService.dockFloating
        readonly property int offset: isFloating ? ConfigService.dockEdgeOffset : 0
        readonly property bool autoHide: ConfigService.dockAutoHide
        property bool hoverRevealed: false
        readonly property bool isRevealed: !autoHide || hoverRevealed || dockHoverArea.containsMouse

        readonly property var unpinnedRunningApps: {
            const pinned = ApplicationService.pinnedApps || [];
            const running = WindowService.runningAppIds || [];
            const res = [];
            for (let i = 0; i < running.length; i++) {
                const r = running[i];
                const app = ApplicationService.getAppById(r);
                const canonId = app ? app.id : r;
                let isPinned = false;
                for (let p = 0; p < pinned.length; p++) {
                    const pApp = ApplicationService.getAppById(pinned[p]);
                    const pCanon = pApp ? pApp.id : pinned[p];
                    if (pCanon === canonId || pinned[p] === r || pinned[p] === canonId) {
                        isPinned = true;
                        break;
                    }
                }
                if (!isPinned && res.indexOf(canonId) === -1) {
                    res.push(canonId);
                }
            }
            return res;
        }

        anchors {
            bottom: dockWindow.edge === "bottom"
            top: dockWindow.edge === "top"
            left: dockWindow.edge === "left"
            right: dockWindow.edge === "right"
        }

        // PanelWindow spans to physical screen edge so autohide trigger is always on screen border
        margins {
            top: 0
            bottom: 0
            left: 0
            right: 0
        }

        implicitHeight: isVertical ? (dockSurface.implicitHeight + 24) : (dockSurface.implicitHeight + (isFloating ? offset : 0))
        implicitWidth: isVertical ? (dockSurface.implicitWidth + (isFloating ? offset : 0)) : (dockSurface.implicitWidth + 24)
        exclusiveZone: (autoHide || !ConfigService.dockReserveSpace) ? 0 : (ConfigService.dockIconSize + 16 + (isFloating ? offset : 0))

        WlrLayershell.layer: WlrLayer.Top
        WlrLayershell.namespace: "quickshell:dock"

        // Disable blur region completely when dock is hidden to prevent ghost blur artifacts
        BackgroundEffect.blurRegion: Region {
            item: (ConfigService.blurEnabled && dockWindow.isRevealed) ? dockSurface : null
        }

        // Mask region for click-through: when hidden, ONLY physical edge trigger intercepts pointer
        mask: Region {
            item: dockWindow.isRevealed ? dockSurface : (dockWindow.autoHide ? edgeTrigger : null)
        }

        Timer {
            id: revealTimer
            interval: Math.max(10, ConfigService.dockRevealDelay)
            repeat: false
            onTriggered: {
                dockWindow.hoverRevealed = true;
            }
        }

        Timer {
            id: hideTimer
            interval: Math.max(50, ConfigService.dockHideDelay)
            repeat: false
            onTriggered: {
                dockWindow.hoverRevealed = false;
            }
        }

        // Screen Edge Hotspot Trigger for Autohide Reveal - sits at physical display boundary
        Item {
            id: edgeTrigger
            visible: dockWindow.autoHide
            anchors {
                bottom: dockWindow.edge === "bottom" ? parent.bottom : undefined
                top: dockWindow.edge === "top" ? parent.top : undefined
                left: dockWindow.edge === "left" ? parent.left : undefined
                right: dockWindow.edge === "right" ? parent.right : undefined
                horizontalCenter: !dockWindow.isVertical ? parent.horizontalCenter : undefined
                verticalCenter: dockWindow.isVertical ? parent.verticalCenter : undefined
            }
            height: dockWindow.isVertical ? Math.max(160, dockSurface.implicitHeight) : 6
            width: dockWindow.isVertical ? 6 : Math.max(160, dockSurface.implicitWidth)

            MouseArea {
                id: edgeTriggerMouse
                anchors.fill: parent
                hoverEnabled: true
                onEntered: {
                    hideTimer.stop();
                    revealTimer.restart();
                }
                onExited: {
                    revealTimer.stop();
                    if (!dockHoverArea.containsMouse) {
                        hideTimer.restart();
                    }
                }
            }
        }

        Surface {
            id: dockSurface
            anchors {
                horizontalCenter: !dockWindow.isVertical ? parent.horizontalCenter : undefined
                verticalCenter: dockWindow.isVertical ? parent.verticalCenter : undefined
                bottom: dockWindow.edge === "bottom" ? parent.bottom : undefined
                top: dockWindow.edge === "top" ? parent.top : undefined
                left: dockWindow.edge === "left" ? parent.left : undefined
                right: dockWindow.edge === "right" ? parent.right : undefined
                bottomMargin: (dockWindow.isFloating && dockWindow.edge === "bottom") ? dockWindow.offset : 0
                topMargin: (dockWindow.isFloating && dockWindow.edge === "top") ? dockWindow.offset : 0
                leftMargin: (dockWindow.isFloating && dockWindow.edge === "left") ? dockWindow.offset : 0
                rightMargin: (dockWindow.isFloating && dockWindow.edge === "right") ? dockWindow.offset : 0
            }
            implicitHeight: dockWindow.isVertical ? (colLayout.implicitHeight + 16) : (ConfigService.dockIconSize + 16)
            implicitWidth: dockWindow.isVertical ? (ConfigService.dockIconSize + 16) : (rowLayout.implicitWidth + 16)
            radius: dockWindow.isFloating ? Theme.radiusLarge : 0
            borderVisible: dockWindow.isFloating
            color: Theme.alpha(Theme.background, ConfigService.barOpacity)

            // Autohide Sliding Offset via Translate to avoid anchor conflicts
            transform: Translate {
                id: slideTrans
                y: {
                    if (!dockWindow.autoHide || dockWindow.isRevealed) return 0;
                    if (dockWindow.edge === "bottom") return dockSurface.height + dockWindow.offset + 24;
                    if (dockWindow.edge === "top") return -(dockSurface.height + dockWindow.offset + 24);
                    return 0;
                }
                x: {
                    if (!dockWindow.autoHide || dockWindow.isRevealed) return 0;
                    if (dockWindow.edge === "left") return -(dockSurface.width + dockWindow.offset + 24);
                    if (dockWindow.edge === "right") return dockSurface.width + dockWindow.offset + 24;
                    return 0;
                }

                Behavior on y { NumberAnimation { duration: Theme.animDurationNormal; easing.type: Theme.animEasing } }
                Behavior on x { NumberAnimation { duration: Theme.animDurationNormal; easing.type: Theme.animEasing } }
            }

            opacity: (!dockWindow.autoHide || dockWindow.isRevealed) ? 1.0 : 0.0
            Behavior on opacity { NumberAnimation { duration: Theme.animDurationNormal } }

            MouseArea {
                id: dockHoverArea
                anchors.fill: parent
                hoverEnabled: true
                onEntered: {
                    revealTimer.stop();
                    hideTimer.stop();
                    dockWindow.hoverRevealed = true;
                }
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
                    onClicked: ConfigService.toggleLauncher(dockWindow.modelData)
                }

                DockSeparator { isVertical: false }

                // Pinned apps
                Repeater {
                    model: ApplicationService.pinnedApps

                    DockItem {
                        required property var modelData
                        parentWindowRef: dockWindow
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
                        parentWindowRef: dockWindow
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
                    onClicked: ConfigService.toggleSettings(dockWindow.modelData)
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
                    onClicked: ConfigService.toggleLauncher(dockWindow.modelData)
                }

                DockSeparator { isVertical: true }

                // Pinned apps
                Repeater {
                    model: ApplicationService.pinnedApps

                    DockItem {
                        required property var modelData
                        parentWindowRef: dockWindow
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
                        parentWindowRef: dockWindow
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
                    onClicked: ConfigService.toggleSettings(dockWindow.modelData)
                }
            }
        }
    }
}
