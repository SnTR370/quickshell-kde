import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import "../../services"
import "../../components"
import "../../services/kwin/Intellihide.js" as Intellihide
import "Magnification.js" as Magnification
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
        // autoHide = hide-capable (legacy auto-hide OR intellihide). Intellihide wins when both set.
        readonly property bool intellihide: ConfigService.dockIntellihide
        readonly property bool autoHide: ConfigService.dockAutoHide || ConfigService.dockIntellihide
        // Revealed footprint: uses implicit surface size, never the animated Translate.
        readonly property var footprint: Intellihide.dockFootprint(
            modelData ? { x: modelData.x, y: modelData.y, width: modelData.width, height: modelData.height } : null,
            edge, dockSurface.implicitWidth, dockSurface.implicitHeight, offset)
        readonly property bool intellihideObstructed: {
            if (!intellihide) return false;
            void(WindowService.windowStateRevision);
            const sts = WindowService.windowStates || {};
            const arr = [];
            for (const k in sts) arr.push(sts[k]);
            return Intellihide.isObstructed(footprint, arr, KWinService.currentDesktopId);
        }
        property bool hoverRevealed: false
        property var activePopupItem: null
        readonly property bool hasActivePopup: activePopupItem !== null
        property var activeDragItem: null
        readonly property bool isDragging: activeDragItem !== null

        // DOCK-004 pointer-driven magnification (parabolic zoom + neighbor
        // displacement). Pure math lives in Magnification.js; this controller
        // only measures rest geometry, resolves, and assigns imperatively.
        // Driven exclusively by the surface HoverHandler's point updates -
        // no timers, no polling. magnifiedGrowth widens the surface so the
        // displaced icons stay inside the dock background; the surface grows
        // symmetrically around its (anchored) center, so the layout's rest
        // positions and the dock's centering never jump.
        property real magnifiedGrowth: 0
        property var lastMagnifyPoint: null

        function magnificationEntries() {
            const layout = dockWindow.isVertical ? colLayout : rowLayout;
            const res = [];
            const kids = layout ? layout.children : [];
            for (let i = 0; i < kids.length; i++) {
                const c = kids[i];
                if (c && c.visible && c.magnifiedOffset !== undefined) res.push(c);
            }
            return res;
        }

        function resetMagnification() {
            const entries = dockWindow.magnificationEntries();
            for (let i = 0; i < entries.length; i++) {
                const e = entries[i];
                e.magnifiedOffset = 0;
                if (e.magnifiedScale !== undefined) e.magnifiedScale = 1.0;
            }
            dockWindow.magnifiedGrowth = 0;
        }

        function updateMagnification(surfacePos) {
            dockWindow.lastMagnifyPoint = surfacePos || null;
            if (!ConfigService.dockMagnification || dockWindow.isDragging) {
                dockWindow.resetMagnification();
                return;
            }
            const entries = dockWindow.magnificationEntries();
            if (entries.length === 0) {
                dockWindow.magnifiedGrowth = 0;
                return;
            }
            const vert = dockWindow.isVertical;
            const pointer = surfacePos ? (vert ? surfacePos.y : surfacePos.x) : NaN;
            const centers = [];
            const extents = [];
            const magnifiable = [];
            for (let i = 0; i < entries.length; i++) {
                const e = entries[i];
                const mapped = e.mapToItem(dockSurface, e.width / 2, e.height / 2);
                // mapToItem includes the applied (animated) displacement
                // transform; subtract it to measure the stable REST center.
                centers.push((vert ? mapped.y : mapped.x) - e.appliedMagnifiedOffset);
                extents.push(vert ? e.height : e.width);
                magnifiable.push(e.magnifiedScale !== undefined);
            }
            const res = Magnification.resolve(centers, extents, magnifiable, pointer,
                ConfigService.dockMagnifyRadius, ConfigService.dockMagnifyMaxScale, Theme.spacingSmall);
            for (let i = 0; i < entries.length; i++) {
                const e = entries[i];
                e.magnifiedOffset = res.offsets[i];
                if (e.magnifiedScale !== undefined) e.magnifiedScale = res.scales[i];
            }
            dockWindow.magnifiedGrowth = Math.max(0, res.growth);
        }

        // Keyboard accessibility (local to this Dock surface). The Dock never requests
        // keyboard focus by itself: keyboardNavActive is only set through the explicit
        // requestKeyboardFocus() entry point (IPC: `qs ipc call dock focus`).
        property bool keyboardNavActive: false
        property var focusedDockItem: null
        onFocusedDockItemChanged: {
            if (focusedDockItem) dockNav.lastItem = focusedDockItem;
        }
        onKeyboardNavActiveChanged: {
            if (!keyboardNavActive && autoHide && !hasActivePopup && !isDragging && !dockAreaHover.hovered && !dockHoverHandler.hovered && !edgeTriggerHover.hovered) {
                hideTimer.restart();
            }
        }

        function getFocusableDockItems() { return dockNav.items(); }
        function moveDockFocus(from, step) { return dockNav.move(from, step); }
        function focusDockBoundary(last) { return dockNav.boundary(last); }

        // Tab / Shift+Tab: walk the Dock; leaving either end hands focus back (no trap).
        function tabDockFocus(from, step) {
            if (dockNav.tabStep(from, step)) return true;
            dockWindow.releaseKeyboardFocus();
            return false;
        }

        function requestKeyboardFocus() {
            if (!dockWindow.visible) return false;
            dockWindow.keyboardNavActive = true;
            return dockNav.focusInitial();
        }

        function releaseKeyboardFocus() {
            if (dockWindow.focusedDockItem) {
                dockWindow.focusedDockItem.focus = false;
            }
            dockWindow.focusedDockItem = null;
            dockWindow.activePopupItem = null;
            dockWindow.keyboardNavActive = false;
        }

        DockKeyboardNav {
            id: dockNav
            layout: dockWindow.isVertical ? colLayout : rowLayout
        }

        IpcHandler {
            // First screen: `dock`; additional screens: `dock-<screen name>`.
            target: (Quickshell.screens.length > 0 && Quickshell.screens[0] === dockWindow.modelData) ? "dock" : ("dock-" + (dockWindow.modelData ? dockWindow.modelData.name : "unknown"))
            function focus(): bool { return dockWindow.requestKeyboardFocus(); }
            function release(): bool { dockWindow.releaseKeyboardFocus(); return true; }
        }
        onHasActivePopupChanged: {
            if (!hasActivePopup && !isDragging && !dockAreaHover.hovered && !dockHoverHandler.hovered && !edgeTriggerHover.hovered && autoHide) {
                hideTimer.restart();
            }
        }
        onIsDraggingChanged: {
            if (isDragging) {
                hideTimer.stop();
                dockWindow.resetMagnification();
            } else {
                // Drop finished with the pointer still over the dock: restore
                // magnification from the last known pointer position.
                if (dockHoverHandler.hovered && dockWindow.lastMagnifyPoint) {
                    dockWindow.updateMagnification(dockWindow.lastMagnifyPoint);
                }
                if (!hasActivePopup && !dockAreaHover.hovered && !dockHoverHandler.hovered && !edgeTriggerHover.hovered && autoHide) {
                    hideTimer.restart();
                }
            }
        }
        onEdgeChanged: {
            // Layout axis switched (horizontal <-> vertical): clear stale state.
            dockWindow.resetMagnification();
        }
        onVisibleChanged: {
            if (!dockWindow.visible) {
                if (dockWindow.activeDragItem && dockWindow.activeDragItem.cancelDrag) {
                    dockWindow.activeDragItem.cancelDrag();
                }
                dockWindow.activeDragItem = null;
                dockWindow.activePopupItem = null;
                dockWindow.hoverRevealed = false;
                dockWindow.keyboardNavActive = false;
                dockWindow.focusedDockItem = null;
                dockWindow.resetMagnification();
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
            function onDockMagnificationChanged() {
                if (!ConfigService.dockMagnification) dockWindow.resetMagnification();
            }
        }
        readonly property bool isRevealed: Intellihide.isRevealed(ConfigService.dockAutoHide, intellihide, intellihideObstructed,
            hoverRevealed || dockAreaHover.hovered || dockHoverHandler.hovered || hasActivePopup || isDragging || keyboardNavActive)

        readonly property var unpinnedRunningApps: {
            const pinned = ApplicationService.pinnedApps || [];
            const running = WindowService.getFilteredRunningAppIds(ConfigService.dockWindowFilter, dockWindow.modelData ? dockWindow.modelData.name : "") || [];
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
        // None by default (never steals focus). OnDemand only after an explicit local request.
        WlrLayershell.keyboardFocus: keyboardNavActive ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None

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
            // DOCK-004: + magnifiedGrowth so displaced/magnified icons stay inside
            // the background. The surface is anchored at its center and the layout
            // is centered in the surface, so this growth is symmetric and the
            // layout's rest geometry does not move.
            implicitHeight: dockWindow.isVertical ? (colLayout.implicitHeight + 16 + dockWindow.magnifiedGrowth) : (ConfigService.dockIconSize + 16)
            implicitWidth: dockWindow.isVertical ? (ConfigService.dockIconSize + 16) : (rowLayout.implicitWidth + 16 + dockWindow.magnifiedGrowth)
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

            // Compositor moved keyboard focus elsewhere (click on another window): drop nav state.
            Window.onActiveChanged: {
                if (!Window.active && dockWindow.keyboardNavActive) {
                    dockWindow.releaseKeyboardFocus();
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
                        dockWindow.resetMagnification();
                        if (dockWindow.autoHide && !dockWindow.hasActivePopup && !dockWindow.isDragging && !dockAreaHover.hovered && !edgeTriggerHover.hovered) {
                            hideTimer.restart();
                        }
                    }
                }
                // DOCK-004: continuous pointer tracking on the layout axis.
                // Event-driven only (no timers); point.position is in
                // dockSurface coordinates.
                onPointChanged: {
                    if (hovered) dockWindow.updateMagnification(point.position);
                }
            }

            // Horizontal Dock Layout
            RowLayout {
                id: rowLayout
                visible: !dockWindow.isVertical
                anchors.centerIn: parent
                spacing: Theme.spacingSmall

                // Launcher toggle
                MagnifySlot {
                    dockWindowRef: dockWindow
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
                MagnifySlot {
                    dockWindowRef: dockWindow
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

            // Vertical Dock Layout
            ColumnLayout {
                id: colLayout
                visible: dockWindow.isVertical
                anchors.centerIn: parent
                spacing: Theme.spacingSmall

                // Launcher toggle
                MagnifySlot {
                    dockWindowRef: dockWindow
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
                MagnifySlot {
                    dockWindowRef: dockWindow
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
}
