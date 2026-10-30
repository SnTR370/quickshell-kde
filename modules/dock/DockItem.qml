import QtQuick
import "../../services"
import "../../components"
import "../../services/applications/FileDrop.js" as FileDrop
import "."

Item {
    id: root

    property var parentWindowRef: null
    property var app: null
    property string appId: ""
    property string appName: ApplicationService.cleanAppName(app ? app.name : appId)
    property string appIcon: app ? app.icon : appId
    property bool isRunning: WindowService.isAppRunning(root.appId)
    property bool isPinned: ApplicationService.isPinned(root.appId)
    readonly property int pinnedIndex: ApplicationService.getPinnedIndex(root.appId)
    readonly property bool canMoveLeft: isPinned && ApplicationService.canMovePinned(root.appId, "left")
    readonly property bool canMoveRight: isPinned && ApplicationService.canMovePinned(root.appId, "right")
    // Filtered view for THIS dock surface's own screen (not the Dock-visibility monitor list).
    readonly property string filterScreenName: (root.parentWindowRef && root.parentWindowRef.modelData) ? root.parentWindowRef.modelData.name : ""
    readonly property var appWindows: WindowService.getFilteredWindowsForApp(root.appId, ConfigService.dockWindowFilter, root.filterScreenName)
    readonly property int windowCount: appWindows.length
    readonly property bool isCurrentAppActive: WindowService.activeWindowId !== "" && appWindows.some(w => WindowService.cleanWindowId(w.id) === WindowService.activeWindowId || w.id === WindowService.activeWindowId)
    property real baseSize: ConfigService.dockIconSize
    property bool menuOpen: false
    property bool chooserOpen: false
    readonly property bool isPopupOpen: menuOpen || chooserOpen
    property bool tooltipActive: false
    property real bounceScale: 1.0
    property bool dragging: false
    property bool dragCancelled: false
    property bool suppressClick: false
    property var acceptedDropInfo: null
    // DOCK-010: the drop-target highlight reacts to BOTH drop sources:
    // intra-dock item drags (keyed DropArea below) and external file drops.
    readonly property bool dropTargeted: itemDropArea.containsDrag
        || (externalFileDropArea.enabled && externalFileDropArea.containsDrag)
    // DOCK-004 pointer-driven magnification state, assigned imperatively by
    // the Dock controller (see Dock.qml updateMagnification). Defaults keep
    // the classic single-icon contract when magnification is disabled or no
    // controller is present (bare-item tests, drag mocks).
    property real magnifiedScale: 1.0
    property real magnifiedOffset: 0.0
    readonly property real appliedMagnifiedOffset: root.isVerticalDock ? magTranslate.y : magTranslate.x
    // Magnified curve scale composes with the preserved single-icon contracts:
    // pressed (0.92) still wins, hover/popup floor (1.15) still applies, and the
    // parabolic neighbor curve can only raise the scale above the floor.
    readonly property real targetScale: (dockItemMouse.pressed ? 0.92 : Math.max(((dockItemMouse.containsMouse || root.isPopupOpen) ? 1.15 : 1.0), root.magnifiedScale)) * root.bounceScale
    z: root.dragging ? 10 : (root.dropTargeted ? 5 : 0)

    // Keyboard accessibility
    readonly property string accessibleLabel: root.appName
        + (root.windowCount > 1 ? (", " + root.windowCount + " windows")
           : (root.windowCount === 1 ? ", running" : ""))
        + (root.isPinned ? ", pinned" : "")
    readonly property bool isVerticalDock: root.parentWindowRef && root.parentWindowRef.isVertical !== undefined
        ? root.parentWindowRef.isVertical
        : (ConfigService.dockEdge === "left" || ConfigService.dockEdge === "right")
    activeFocusOnTab: root.visible && root.enabled && !root.dragging && (root.isPinned || root.isRunning)
    Accessible.role: Accessible.Button
    Accessible.name: root.accessibleLabel
    Accessible.description: root.menuOpen ? "Context menu open" : (root.chooserOpen ? "Window chooser open" : "")
    Accessible.focusable: true
    Accessible.focused: root.activeFocus
    Accessible.onPressAction: root.activateItem()

    onActiveFocusChanged: {
        if (root.parentWindowRef && root.parentWindowRef.focusedDockItem !== undefined) {
            if (root.activeFocus) {
                root.parentWindowRef.focusedDockItem = root;
            } else if (root.parentWindowRef.focusedDockItem === root) {
                root.parentWindowRef.focusedDockItem = null;
            }
        }
    }

    Timer {
        id: tooltipDwellTimer
        interval: 320
        repeat: false
        onTriggered: {
            if (dockItemMouse.containsMouse && !dockItemMouse.pressed && !root.isPopupOpen && !(root.parentWindowRef && root.parentWindowRef.hasActivePopup)) {
                root.tooltipActive = true;
            }
        }
    }

    SequentialAnimation {
        id: clickBounceAnim
        NumberAnimation { target: root; property: "bounceScale"; to: 0.86; duration: 80; easing.type: Easing.OutQuad }
        NumberAnimation { target: root; property: "bounceScale"; to: 1.04; duration: 110; easing.type: Easing.OutQuad }
        NumberAnimation { target: root; property: "bounceScale"; to: 1.0; duration: 100; easing.type: Easing.OutCubic }
    }

    onMenuOpenChanged: {
        if (menuOpen && chooserOpen) {
            chooserOpen = false;
        }
        if (parentWindowRef && parentWindowRef.activePopupItem !== undefined) {
            if (menuOpen) {
                parentWindowRef.activePopupItem = root;
            } else if (parentWindowRef.activePopupItem === root && !root.chooserOpen) {
                parentWindowRef.activePopupItem = null;
            }
        }
    }

    onChooserOpenChanged: {
        if (chooserOpen && menuOpen) {
            menuOpen = false;
        }
        if (parentWindowRef && parentWindowRef.activePopupItem !== undefined) {
            if (chooserOpen) {
                parentWindowRef.activePopupItem = root;
            } else if (parentWindowRef.activePopupItem === root && !root.menuOpen) {
                parentWindowRef.activePopupItem = null;
            }
        }
    }

    Connections {
        target: root.parentWindowRef
        function onActivePopupItemChanged() {
            if (root.parentWindowRef && root.parentWindowRef.activePopupItem !== root) {
                root.menuOpen = false;
                root.chooserOpen = false;
            }
        }
    }

    onVisibleChanged: {
        if (!root.visible && root.dragging) {
            root.cancelDrag();
        }
    }

    onEnabledChanged: {
        if (!root.enabled && root.dragging) {
            root.cancelDrag();
        }
    }

    onIsRunningChanged: {
        if (!root.isRunning && !root.isPinned && root.dragging) {
            root.cancelDrag();
        }
        if (!root.isRunning && root.chooserOpen) {
            root.chooserOpen = false;
        }
    }

    onWindowCountChanged: {
        if (root.windowCount <= 1 && root.chooserOpen) {
            root.chooserOpen = false;
        }
    }

    onIsPinnedChanged: {
        if (root.dragging) {
            root.cancelDrag();
        }
    }

    onAppIdChanged: {
        if (root.dragging) {
            root.cancelDrag();
        }
    }

    onAppChanged: {
        if (root.dragging && !root.app && !root.isRunning) {
            root.cancelDrag();
        }
    }

    Component.onDestruction: {
        if (root.dragging) {
            root.cancelDrag();
        }
        tooltipDwellTimer.stop();
        clickBounceAnim.stop();
        if (parentWindowRef && parentWindowRef.activePopupItem === root) {
            parentWindowRef.activePopupItem = null;
        }
        if (parentWindowRef && parentWindowRef.activeDragItem === root) {
            parentWindowRef.activeDragItem = null;
        }
    }

    implicitWidth: baseSize + 8
    implicitHeight: baseSize + 8
    width: implicitWidth
    height: implicitHeight

    // DOCK-004: lateral displacement along the layout axis, making room for
    // magnified neighbors. Applied as a transform on the WHOLE item (mouse,
    // drop and popup anchor areas included) so hit targets follow the visual
    // while the layout's rest geometry - which the magnification math measures
    // against - stays stable (no feedback loop, no centering jumps).
    transform: Translate {
        id: magTranslate
        x: root.isVerticalDock ? 0 : root.magnifiedOffset
        y: root.isVerticalDock ? root.magnifiedOffset : 0
        Behavior on x {
            NumberAnimation {
                duration: Theme.animDurationFast
                easing.type: Theme.animEasing
            }
        }
        Behavior on y {
            NumberAnimation {
                duration: Theme.animDurationFast
                easing.type: Theme.animEasing
            }
        }
    }

    function acceptDropTarget(info) {
        root.acceptedDropInfo = info;
    }

    function startDrag() {
        if (root.dragging || root.dragCancelled || !root.visible || !root.enabled) return;
        if (!root.isPinned && !root.isRunning) return;
        root.dragging = true;
        root.suppressClick = true;
        tooltipDwellTimer.stop();
        root.tooltipActive = false;
        root.menuOpen = false;
        root.chooserOpen = false;
        if (root.parentWindowRef) {
            if (root.parentWindowRef.activePopupItem !== undefined) {
                root.parentWindowRef.activePopupItem = null;
            }
            if (root.parentWindowRef.activeDragItem !== undefined) {
                root.parentWindowRef.activeDragItem = root;
            }
        }
    }

    function resetDragVisuals() {
        root.dragging = false;
        dragProxy.x = 0;
        dragProxy.y = 0;
        if (root.parentWindowRef && root.parentWindowRef.activeDragItem === root) {
            root.parentWindowRef.activeDragItem = null;
        }
    }

    function cancelDrag() {
        root.dragCancelled = true;
        root.acceptedDropInfo = null;
        if (root.dragging) {
            root.suppressClick = true;
            dragProxy.Drag.cancel();
        }
        dockItemMouse.drag.target = null;
        root.resetDragVisuals();
    }

    function commitDrop(info) {
        if (!info || root.dragCancelled || !root.appId || !root.visible || !root.enabled) return false;
        if (root.isPinned) {
            if (!ApplicationService.isPinned(root.appId)) return false;
            if (info.targetAppId) {
                if (!ApplicationService.isPinned(info.targetAppId)) return false;
                return ApplicationService.reorderPinnedApps(root.appId, info.targetAppId);
            }
            if (typeof info.targetIndex === "number" && info.targetIndex >= 0) {
                const fromIdx = ApplicationService.getPinnedIndex(root.appId);
                if (fromIdx >= 0 && fromIdx !== info.targetIndex) {
                    return ApplicationService.reorderPinnedApps(fromIdx, info.targetIndex);
                }
            }
            return false;
        } else if (root.isRunning) {
            if (!WindowService.isAppRunning(root.appId) || ApplicationService.isPinned(root.appId)) return false;
            let resolvedIdx = info.targetIndex;
            if (info.targetAppId) {
                if (!ApplicationService.isPinned(info.targetAppId)) return false;
                const baseIdx = ApplicationService.getPinnedIndex(info.targetAppId);
                if (baseIdx < 0) return false;
                resolvedIdx = info.insertAfter ? (baseIdx + 1) : baseIdx;
            } else if (info.targetAppId === "") {
                resolvedIdx = ApplicationService.pinnedApps.length;
            }
            return ApplicationService.pinAppAt(root.appId, resolvedIdx);
        }
        return false;
    }

    function finishDrag() {
        if (!root.dragging) return false;
        root.acceptedDropInfo = null;
        const dropAction = dragProxy.Drag.drop();
        const info = root.acceptedDropInfo;
        root.acceptedDropInfo = null;
        root.resetDragVisuals();
        if (dropAction === Qt.MoveAction && info) {
            return root.commitDrop(info);
        }
        return false;
    }

    // DOCK-010: external (inter-process) file drop - open the dropped files
    // with this item's application. Takes the raw URI list (QUrl strings,
    // or text/uri-list text), filters it to local paths (FileDrop.js) and
    // dispatches ONE launch via ApplicationService.launchFiles. Returns true
    // when a launch command was built; rejected drops (non-file URIs,
    // non-launchable items, active intra-dock drag) are visible no-ops.
    // Launching is the ONLY side effect: no window activation, no focus
    // requests (Wayland focus-safety).
    function handleExternalFileDrop(rawUrls) {
        if (root.dragging || !root.visible || !root.enabled) return false;
        if (root.parentWindowRef && root.parentWindowRef.isDragging) return false;
        if (!(root.isPinned || root.isRunning) || !root.app) return false;
        const paths = FileDrop.localPathsFromUrls(rawUrls);
        if (paths.length === 0) return false;
        return ApplicationService.launchFiles(root.app, paths);
    }

    // DOCK-010: external file-drop target. Sits BELOW the keyed itemDropArea
    // in stacking order and is disabled during any intra-dock drag, so the
    // reordering/pinning DnD contract is untouched: internal drags carry the
    // "quickshell-dock-item" key and a Quick drag source and are handled
    // exclusively by itemDropArea; external OS drags (Dolphin, etc.) have no
    // keys/source and fall through to this area. Keyless by design - the
    // guards reject anything that is not a local-file drop on a launchable
    // app icon.
    DropArea {
        id: externalFileDropArea
        anchors.fill: parent
        enabled: root.visible && root.enabled && !root.dragging
            && !(root.parentWindowRef && root.parentWindowRef.isDragging)
            && (root.isPinned || root.isRunning) && root.app !== null

        onDropped: drop => {
            // Never intercept intra-dock (or any Quick-internal) drags.
            if (drop.source || root.dragging || (root.parentWindowRef && root.parentWindowRef.isDragging)) {
                drop.accepted = false;
                return;
            }
            const raw = (drop.hasUrls && drop.urls && drop.urls.length > 0)
                ? drop.urls
                : FileDrop.uriListFromText(drop.text);
            drop.accepted = root.handleExternalFileDrop(raw);
        }
    }

    DropArea {
        id: itemDropArea
        anchors.fill: parent
        enabled: root.isPinned && root.visible && !root.dragging
        keys: ["quickshell-dock-item"]

        onDropped: drop => {
            if (!root.isPinned || !root.visible || !drop.source) {
                drop.accepted = false;
                return;
            }
            const src = drop.source;
            if (src === root || !src.appId || root.pinnedIndex < 0) {
                drop.accepted = false;
                return;
            }
            if (src.isPinned) {
                if (ConfigService.dockAppIdsMatch(src.appId, root.appId) ||
                    src.pinnedIndex < 0 || src.pinnedIndex === root.pinnedIndex) {
                    drop.accepted = false;
                    return;
                }
                if (src.acceptDropTarget) {
                    src.acceptDropTarget({
                        targetIndex: root.pinnedIndex,
                        targetAppId: root.appId
                    });
                    drop.accept(Qt.MoveAction);
                } else {
                    drop.accepted = false;
                }
            } else if (src.isRunning) {
                if (!ApplicationService.getAppById(src.appId) || ApplicationService.isPinned(src.appId)) {
                    drop.accepted = false;
                    return;
                }
                let targetIdx = root.pinnedIndex;
                const isVert = root.parentWindowRef ? root.parentWindowRef.isVertical : (ConfigService.dockEdge === "left" || ConfigService.dockEdge === "right");
                const pos = isVert ? drop.y : drop.x;
                const span = isVert ? height : width;
                const insertAfter = (span > 0 && pos > span * 0.75);
                if (insertAfter) {
                    targetIdx = targetIdx + 1;
                }
                if (src.acceptDropTarget) {
                    src.acceptDropTarget({
                        targetIndex: targetIdx,
                        targetAppId: root.appId,
                        insertAfter: insertAfter
                    });
                    drop.accept(Qt.MoveAction);
                } else {
                    drop.accepted = false;
                }
            } else {
                drop.accepted = false;
            }
        }
    }

    Item {
        id: dragProxy
        width: root.width
        height: root.height
        Drag.active: root.dragging
        Drag.source: root
        Drag.hotSpot.x: width / 2
        Drag.hotSpot.y: height / 2
        Drag.keys: ["quickshell-dock-item"]
    }

    Rectangle {
        id: iconContainer
        anchors.centerIn: parent
        width: root.baseSize
        height: root.baseSize
        radius: Theme.radiusSmall
        color: dockItemMouse.pressed ? Theme.alpha(Theme.primary, 0.28)
             : root.isPopupOpen ? Theme.alpha(Theme.primary, 0.22)
             : dockItemMouse.containsMouse ? Theme.hover
             : "transparent"
        border.width: (root.isPopupOpen || root.dropTargeted) ? 1 : 0
        border.color: root.dropTargeted ? Theme.primary : Theme.alpha(Theme.primary, 0.45)
        scale: root.targetScale

        transform: Translate {
            x: root.dragging ? dragProxy.x : 0
            y: root.dragging ? dragProxy.y : 0
        }

        Behavior on scale {
            enabled: !clickBounceAnim.running
            NumberAnimation {
                duration: iconContainer.scale > 1.0 ? 160 : 130
                easing.type: iconContainer.scale > 1.0 ? Easing.OutBack : Easing.OutCubic
            }
        }
        Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }
        Behavior on border.color { ColorAnimation { duration: Theme.animDurationFast } }

        // Visible keyboard focus indicator
        Rectangle {
            id: focusRing
            anchors.fill: parent
            anchors.margins: -2
            radius: Theme.radiusSmall + 2
            color: "transparent"
            border.width: 2
            border.color: Theme.accent
            visible: root.activeFocus
        }

        SvgIcon {
            anchors.centerIn: parent
            icon: root.appIcon || "application-x-executable"
            size: root.baseSize * 0.8
        }

        // Multi-window / Running indicator
        Row {
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 2
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 2
            visible: root.windowCount > 0
            opacity: root.windowCount > 0 ? 1.0 : 0.0
            Behavior on opacity { NumberAnimation { duration: Theme.animDurationFast } }

            // Dot 1 (Single window or first of multi)
            Rectangle {
                width: root.isCurrentAppActive ? 10 : (root.windowCount >= 3 ? 3 : (root.windowCount === 2 ? 4 : 6))
                height: 3
                radius: 1.5
                color: root.isCurrentAppActive ? Theme.accent : Theme.primary
                Behavior on width { NumberAnimation { duration: Theme.animDurationFast; easing.type: Easing.OutCubic } }
                Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }
            }

            // Dot 2 (for 2+ windows)
            Rectangle {
                width: root.windowCount >= 3 ? 3 : 4
                height: 3
                radius: 1.5
                color: Theme.primary
                visible: root.windowCount >= 2
            }

            // Dot 3 (for 3+ windows)
            Rectangle {
                width: 3
                height: 3
                radius: 1.5
                color: Theme.primary
                visible: root.windowCount >= 3
            }
        }
    }

    Tooltip {
        parentWindow: root.parentWindowRef
        anchorItem: iconContainer
        edge: ConfigService.dockEdge
        offset: 4
        text: root.appName + (root.windowCount > 1 ? (" (" + root.windowCount + " Windows)") : "")
        show: root.tooltipActive && dockItemMouse.containsMouse && !dockItemMouse.pressed && !root.dragging && !root.isPopupOpen && !(root.parentWindowRef && root.parentWindowRef.hasActivePopup) && !(root.parentWindowRef && root.parentWindowRef.isDragging) && (root.parentWindowRef ? root.parentWindowRef.isRevealed : true)
    }

    // Lazy-loaded Multi-Window Chooser Popup
    Loader {
        id: chooserLoader
        active: root.chooserOpen && root.windowCount > 1
        sourceComponent: WindowChooserPopup {
            parentWindow: root.parentWindowRef || root.Window.window
            anchorItem: iconContainer
            edge: ConfigService.dockEdge
            appId: root.appId
            filterScreenName: root.filterScreenName
            app: root.app
            onWindowSelected: root.chooserOpen = false
            onClosed: root.chooserOpen = false
        }
    }

    // Lazy-loaded Context Menu Popup
    Loader {
        id: menuLoader
        active: root.menuOpen
        sourceComponent: DockMenu {
            parentWindow: root.parentWindowRef || root.Window.window
            anchorItem: iconContainer
            edge: ConfigService.dockEdge
            appId: root.appId
            filterScreenName: root.filterScreenName
            app: root.app
            isRunning: root.isRunning
            isPinned: root.isPinned
            onActionTriggered: root.menuOpen = false
            onClosed: root.menuOpen = false
        }
    }

    // Primary activation (left click / Enter / Space): launch, toggle window, or window chooser.
    function activateItem() {
        if (root.dragging) return false;
        clickBounceAnim.restart();
        if (root.windowCount === 0 && root.isRunning) {
            // App runs globally but has no window in the filtered view: never launch a duplicate.
            root.chooserOpen = false;
            const pick = WindowService.pickActivation(root.appId, root.appWindows);
            if (pick.action === "activate") WindowService.activateWindow(pick.id);
        } else if (root.windowCount === 0) {
            root.menuOpen = false;
            root.chooserOpen = false;
            if (root.parentWindowRef && root.parentWindowRef.activePopupItem) {
                root.parentWindowRef.activePopupItem = null;
            }
            if (root.app) {
                ApplicationService.launch(root.app);
            } else {
                ApplicationService.launchAppId(root.appId);
            }
        } else if (root.windowCount === 1) {
            root.menuOpen = false;
            root.chooserOpen = false;
            if (root.parentWindowRef && root.parentWindowRef.activePopupItem) {
                root.parentWindowRef.activePopupItem = null;
            }
            WindowService.toggleWindow(root.appWindows[0].id);
        } else {
            const pick = WindowService.pickActivation(root.appId, root.appWindows);
            if (pick.action === "toggle" && !root.chooserOpen) {
                root.menuOpen = false;
                if (root.parentWindowRef && root.parentWindowRef.activePopupItem) {
                    root.parentWindowRef.activePopupItem = null;
                }
                WindowService.toggleWindow(pick.id);
            } else {
                root.chooserOpen = !root.chooserOpen;
            }
        }
        return true;
    }

    function toggleContextMenu() {
        if (root.dragging) return false;
        root.menuOpen = !root.menuOpen;
        return true;
    }

    function launchNewInstance() {
        clickBounceAnim.restart();
        root.chooserOpen = false;
        root.menuOpen = false;
        if (root.parentWindowRef && root.parentWindowRef.activePopupItem) {
            root.parentWindowRef.activePopupItem = null;
        }
        ApplicationService.launchAppId(root.appId);
    }

    function currentPopupItem() {
        if (root.menuOpen && menuLoader.item) return menuLoader.item;
        if (root.chooserOpen && chooserLoader.item) return chooserLoader.item;
        return null;
    }

    // Popups are xdg_popups without keyboard grab, so the focused Dock item forwards keys to them.
    function startPopupKeyboardNav() {
        Qt.callLater(function() {
            const popup = root.currentPopupItem();
            if (popup && popup.focusFirstKeyboardAction) popup.focusFirstKeyboardAction();
        });
    }

    function handleKeyEvent(event) {
        if (root.isPopupOpen) {
            const popup = root.currentPopupItem();
            if (popup && popup.handleKeyEvent && popup.handleKeyEvent(event)) {
                event.accepted = true;
                return true;
            }
        }
        const win = root.parentWindowRef;
        const canNav = win && typeof win.moveDockFocus === "function";
        const key = event.key;
        if (key === Qt.Key_Return || key === Qt.Key_Enter || key === Qt.Key_Space) {
            event.accepted = true;
            if (!event.isAutoRepeat) {
                root.activateItem();
                if (root.isPopupOpen) root.startPopupKeyboardNav();
            }
        } else if (key === Qt.Key_Menu || (key === Qt.Key_F10 && (event.modifiers & Qt.ShiftModifier))) {
            event.accepted = true;
            if (root.toggleContextMenu() && root.isPopupOpen) root.startPopupKeyboardNav();
        } else if (canNav && ((!root.isVerticalDock && key === Qt.Key_Right) || (root.isVerticalDock && key === Qt.Key_Down))) {
            event.accepted = true;
            win.moveDockFocus(root, 1);
        } else if (canNav && ((!root.isVerticalDock && key === Qt.Key_Left) || (root.isVerticalDock && key === Qt.Key_Up))) {
            event.accepted = true;
            win.moveDockFocus(root, -1);
        } else if (canNav && (key === Qt.Key_Home || key === Qt.Key_End)) {
            event.accepted = true;
            win.focusDockBoundary(key === Qt.Key_End);
        } else if (canNav && typeof win.tabDockFocus === "function" && (key === Qt.Key_Tab || key === Qt.Key_Backtab)) {
            event.accepted = true;
            win.tabDockFocus(root, key === Qt.Key_Tab ? 1 : -1);
        } else if (key === Qt.Key_Escape) {
            event.accepted = true;
            if (win && win.activePopupItem) {
                win.activePopupItem = null;
            } else if (win && typeof win.releaseKeyboardFocus === "function") {
                win.releaseKeyboardFocus();
            } else {
                root.focus = false;
            }
        }
        return event.accepted;
    }

    Keys.onPressed: event => root.handleKeyEvent(event)

    function handleWheel(delta) {
        if (!delta) return false;
        tooltipDwellTimer.stop();
        root.tooltipActive = false;
        if (root.windowCount === 0) return false;
        return WindowService.cycleAppWindows(root.appId, delta < 0, root.filterScreenName);
    }

    MouseArea {
        id: dockItemMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: root.dragging ? Qt.ClosedHandCursor : Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
        drag.target: (!root.dragCancelled && (root.isPinned || root.isRunning)) ? dragProxy : null
        drag.axis: Drag.XAndYAxis
        drag.threshold: 4
        drag.filterChildren: false

        Connections {
            target: dockItemMouse.drag
            function onActiveChanged() {
                if (dockItemMouse.drag.active && !root.dragCancelled) {
                    root.startDrag();
                }
            }
        }

        onPressed: mouse => {
            tooltipDwellTimer.stop();
            root.tooltipActive = false;
            root.suppressClick = false;
            root.acceptedDropInfo = null;
            if (mouse.button === Qt.LeftButton && (root.isPinned || root.isRunning)) {
                root.dragCancelled = false;
                dockItemMouse.drag.target = dragProxy;
            } else {
                root.dragCancelled = true;
                dockItemMouse.drag.target = null;
            }
        }

        onReleased: mouse => {
            if (root.dragging && !root.dragCancelled) {
                root.finishDrag();
            } else {
                root.resetDragVisuals();
            }
        }

        onCanceled: {
            root.cancelDrag();
        }

        onWheel: wheel => {
            if (root.dragging) return;
            const delta = wheel.angleDelta.y !== 0 ? wheel.angleDelta.y : wheel.angleDelta.x;
            if (delta === 0) return;
            wheel.accepted = true;
            root.handleWheel(delta);
        }

        onEntered: {
            WindowService.refreshActiveWindow();
            if (!root.dragging && !root.isPopupOpen && !(root.parentWindowRef && root.parentWindowRef.hasActivePopup) && !(root.parentWindowRef && root.parentWindowRef.isDragging)) {
                tooltipDwellTimer.restart();
            }
        }

        onExited: {
            tooltipDwellTimer.stop();
            root.tooltipActive = false;
        }

        onClicked: mouse => {
            tooltipDwellTimer.stop();
            root.tooltipActive = false;
            if (root.suppressClick || root.dragging || root.dragCancelled && mouse.button === Qt.LeftButton) {
                root.suppressClick = false;
                return;
            }
            if (mouse.button === Qt.RightButton) {
                root.toggleContextMenu();
            } else if (mouse.button === Qt.MiddleButton) {
                root.launchNewInstance();
            } else {
                root.activateItem();
            }
        }
    }
}
