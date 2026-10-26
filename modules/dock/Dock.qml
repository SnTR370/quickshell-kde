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
        property var activePopupItem: null
        readonly property bool hasActivePopup: activePopupItem !== null
        property var activeDragItem: null
        readonly property bool isDragging: activeDragItem !== null
        onHasActivePopupChanged: {
            if (!hasActivePopup && !isDragging && !dockAreaHover.hovered && !dockHoverHandler.hovered && !edgeTriggerHover.hovered && autoHide) {
                hideTimer.restart();
            }
        }
        onIsDraggingChanged: {
            if (isDragging) {
                hideTimer.stop();
            } else if (!hasActivePopup && !dockAreaHover.hovered && !dockHoverHandler.hovered && !edgeTriggerHover.hovered && autoHide) {
                hideTimer.restart();
            }
        }
        onVisibleChanged: {
            if (!dockWindow.visible) {
                if (dockWindow.activeDragItem && dockWindow.activeDragItem.cancelDrag) {
                    dockWindow.activeDragItem.cancelDrag();
                }
                dockWindow.activeDragItem = null;
                dockWindow.activePopupItem = null;
                dockWindow.hoverRevealed = false;
            }
        }
        Connections {
            target: ConfigService
            function onLauncherVisibleChanged() {
                if (ConfigService.launcherVisible) dockWindow.activePopupItem = null;
            }
            function onSettingsVisibleChanged() {
                if (ConfigService.settingsVisible) dockWindow.activePopupItem = null;
            }
        }
        readonly property bool isRevealed: !autoHide || hoverRevealed || dockAreaHover.hovered || dockHoverHandler.hovered || hasActivePopup || isDragging

        readonly property var unpinnedRunningApps: {
            const pinned = ApplicationService.pinnedApps || [];
            const running = WindowService.runningAppIds || [];
            const res = [];
            const seenCanon = {};
            for (let i = 0; i < running.length; i++) {
                const r = running[i];
                if (!r) continue;
                const app = ApplicationService.getAppById(r);
                const canonId = app ? app.id : r;
                const canonKey = String(canonId).toLowerCase().replace(/\.desktop$/, "");
                const rKey = String(r).toLowerCase().replace(/\.desktop$/, "");
                let isPinned = false;
                for (let p = 0; p < pinned.length; p++) {
                    const pRaw = pinned[p];
                    if (!pRaw) continue;
                    const pApp = ApplicationService.getAppById(pRaw);
                    const pCanonKey = String(pApp ? pApp.id : pRaw).toLowerCase().replace(/\.desktop$/, "");
                    const pRawKey = String(pRaw).toLowerCase().replace(/\.desktop$/, "");
                    if (pCanonKey === canonKey || pRawKey === rKey || pRawKey === canonKey || pCanonKey === rKey) {
                        isPinned = true;
                        break;
                    }
                }
                if (!isPinned && canonKey.length > 0 && !seenCanon[canonKey]) {
                    seenCanon[canonKey] = true;
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

        // Mask region for click-through: when hidden, ONLY physical edge trigger intercepts pointer.
        // When revealed, dockInteractiveArea keeps edge, offset gap, and surface active to prevent pointer-leave flicker.
        mask: Region {
            item: !dockWindow.autoHide ? dockSurface : (dockWindow.isRevealed ? dockInteractiveArea : edgeTrigger)
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
                if (!dockAreaHover.hovered && !dockHoverHandler.hovered && !edgeTriggerHover.hovered && !dockWindow.hasActivePopup && !dockWindow.isDragging) {
                    dockWindow.hoverRevealed = false;
                }
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
            height: dockWindow.isVertical ? Math.max(180, dockSurface.implicitHeight) : 8
            width: dockWindow.isVertical ? 8 : Math.max(180, dockSurface.implicitWidth)

            HoverHandler {
                id: edgeTriggerHover
                onHoveredChanged: {
                    if (hovered) {
                        hideTimer.stop();
                        revealTimer.restart();
                    } else {
                        revealTimer.stop();
                        if (!dockAreaHover.hovered && !dockHoverHandler.hovered && !dockWindow.hasActivePopup && !dockWindow.isDragging) {
                            hideTimer.restart();
                        }
                    }
                }
            }
        }

        // Interactive Region spanning from physical screen edge across floating offset to dock surface
        Item {
            id: dockInteractiveArea
            anchors {
                horizontalCenter: !dockWindow.isVertical ? parent.horizontalCenter : undefined
                verticalCenter: dockWindow.isVertical ? parent.verticalCenter : undefined
                bottom: dockWindow.edge === "bottom" ? parent.bottom : undefined
                top: dockWindow.edge === "top" ? parent.top : undefined
                left: dockWindow.edge === "left" ? parent.left : undefined
                right: dockWindow.edge === "right" ? parent.right : undefined
            }
            width: dockWindow.isVertical
                ? (dockSurface.implicitWidth + (dockWindow.isFloating ? dockWindow.offset : 0))
                : Math.max(dockSurface.implicitWidth + 24, 180)
            height: dockWindow.isVertical
                ? Math.max(dockSurface.implicitHeight + 24, 180)
                : (dockSurface.implicitHeight + (dockWindow.isFloating ? dockWindow.offset : 0))

            HoverHandler {
                id: dockAreaHover
                onHoveredChanged: {
                    if (hovered) {
                        revealTimer.stop();
                        hideTimer.stop();
                        dockWindow.hoverRevealed = true;
                    } else {
                        if (dockWindow.autoHide && !dockWindow.hasActivePopup && !dockWindow.isDragging && !dockHoverHandler.hovered && !edgeTriggerHover.hovered) {
                            hideTimer.restart();
                        }
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

                Behavior on y {
                    NumberAnimation {
                        duration: dockWindow.isRevealed ? 180 : 220
                        easing.type: dockWindow.isRevealed ? Easing.OutCubic : Easing.InOutQuad
                    }
                }
                Behavior on x {
                    NumberAnimation {
                        duration: dockWindow.isRevealed ? 180 : 220
                        easing.type: dockWindow.isRevealed ? Easing.OutCubic : Easing.InOutQuad
                    }
                }
            }

            opacity: (!dockWindow.autoHide || dockWindow.isRevealed) ? 1.0 : 0.0
            Behavior on opacity {
                NumberAnimation {
                    duration: dockWindow.isRevealed ? 160 : 200
                    easing.type: Easing.OutQuad
                }
            }

            HoverHandler {
                id: dockHoverHandler
                onHoveredChanged: {
                    if (hovered) {
                        revealTimer.stop();
                        hideTimer.stop();
                        dockWindow.hoverRevealed = true;
                    } else {
                        if (dockWindow.autoHide && !dockWindow.hasActivePopup && !dockWindow.isDragging && !dockAreaHover.hovered && !edgeTriggerHover.hovered) {
                            hideTimer.restart();
                        }
                    }
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
                    parentWindow: dockWindow
                    edge: dockWindow.edge
                    size: ConfigService.dockIconSize
                    icon: "start-here-kde"
                    iconColor: Theme.primary
                    backgroundColor: Theme.alpha(Theme.primary, 0.12)
                    tooltip: "Applications"
                    active: ConfigService.launcherVisible && (ConfigService.launcherScreenName === "" || ConfigService.launcherScreenName === (dockWindow.modelData ? dockWindow.modelData.name : ""))
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
                    acceptPinDrop: true
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
                    parentWindow: dockWindow
                    edge: dockWindow.edge
                    size: ConfigService.dockIconSize
                    icon: "preferences-system"
                    iconColor: Theme.foreground
                    tooltip: "Settings"
                    active: ConfigService.settingsVisible && (ConfigService.settingsScreenName === "" || ConfigService.settingsScreenName === (dockWindow.modelData ? dockWindow.modelData.name : ""))
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
                    parentWindow: dockWindow
                    edge: dockWindow.edge
                    size: ConfigService.dockIconSize
                    icon: "start-here-kde"
                    iconColor: Theme.primary
                    backgroundColor: Theme.alpha(Theme.primary, 0.12)
                    tooltip: "Applications"
                    active: ConfigService.launcherVisible && (ConfigService.launcherScreenName === "" || ConfigService.launcherScreenName === (dockWindow.modelData ? dockWindow.modelData.name : ""))
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
                    acceptPinDrop: true
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
                    parentWindow: dockWindow
                    edge: dockWindow.edge
                    size: ConfigService.dockIconSize
                    icon: "preferences-system"
                    iconColor: Theme.foreground
                    tooltip: "Settings"
                    active: ConfigService.settingsVisible && (ConfigService.settingsScreenName === "" || ConfigService.settingsScreenName === (dockWindow.modelData ? dockWindow.modelData.name : ""))
                    onClicked: ConfigService.toggleSettings(dockWindow.modelData)
                }
            }
        }
    }
}
