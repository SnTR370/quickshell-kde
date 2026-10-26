import QtQuick
import Quickshell
import Quickshell.Wayland
import "../services"

PopupWindow {
    id: root

    property var parentWindow: null
    property Item anchorItem: null
    property string edge: "top"
    property int offset: 8
    property string initialDesktopId: ""
    property string initialActiveWindow: ""
    property string accessibleName: ""

    visible: true
    grabFocus: false

    function close() {
        root.visible = false;
        root.closed();
    }

    // ---- Keyboard navigation ------------------------------------------------------
    // Popups are xdg_popups without a keyboard grab, so keys normally arrive through the
    // owner (e.g. the focused DockItem) which forwards them to handleKeyEvent(). The same
    // handler is bound to the popup surface for the case where the popup receives keys itself.
    // Actionable rows are the enabled, visible MouseAreas in popup content (tree order =
    // visual order). Disabled actions are skipped.
    property Item keyboardTarget: null
    property Item keyboardRing: null

    Component {
        id: keyboardRingComponent
        Rectangle {
            anchors.fill: parent
            anchors.margins: -1
            radius: Theme.radiusSmall
            color: "transparent"
            border.width: 2
            border.color: Theme.accent
            z: 100
        }
    }

    function isKeyboardAction(item) {
        return item.acceptedButtons !== undefined && item.containsMouse !== undefined && typeof item.clicked === "function";
    }

    function collectKeyboardActions(item, out) {
        const kids = item.children;
        for (let i = 0; i < kids.length; i++) {
            const c = kids[i];
            if (!c || !c.visible || c.enabled === false) continue;
            if (root.isKeyboardAction(c)) out.push(c);
            root.collectKeyboardActions(c, out);
        }
        return out;
    }

    function keyboardActions() {
        return root.collectKeyboardActions(popupContent, []);
    }

    function setKeyboardTarget(target) {
        if (root.keyboardRing) {
            root.keyboardRing.destroy();
            root.keyboardRing = null;
        }
        root.keyboardTarget = target;
        if (target) {
            root.keyboardRing = keyboardRingComponent.createObject(target);
        }
    }

    function focusFirstKeyboardAction() {
        const list = root.keyboardActions();
        if (list.length === 0) return false;
        root.setKeyboardTarget(list[0]);
        return true;
    }

    function moveKeyboardFocus(step) {
        const list = root.keyboardActions();
        if (list.length === 0) return false;
        const idx = list.indexOf(root.keyboardTarget);
        const next = idx >= 0 ? ((idx + step + list.length) % list.length) : (step >= 0 ? 0 : list.length - 1);
        root.setKeyboardTarget(list[next]);
        return true;
    }

    function focusKeyboardBoundary(last) {
        const list = root.keyboardActions();
        if (list.length === 0) return false;
        root.setKeyboardTarget(list[last ? list.length - 1 : 0]);
        return true;
    }

    function activateKeyboardTarget() {
        const t = root.keyboardTarget;
        if (!t || !t.visible || t.enabled === false) {
            return root.focusFirstKeyboardAction();
        }
        t.clicked(null);
        return true;
    }

    function handleKeyEvent(event) {
        if (!event) return false;
        const key = event.key;
        let handled = true;
        if (key === Qt.Key_Escape) {
            root.close();
        } else if (key === Qt.Key_Down || key === Qt.Key_Right || (key === Qt.Key_Tab && !(event.modifiers & Qt.ShiftModifier))) {
            root.moveKeyboardFocus(1);
        } else if (key === Qt.Key_Up || key === Qt.Key_Left || key === Qt.Key_Backtab || key === Qt.Key_Tab) {
            root.moveKeyboardFocus(-1);
        } else if (key === Qt.Key_Home) {
            root.focusKeyboardBoundary(false);
        } else if (key === Qt.Key_End) {
            root.focusKeyboardBoundary(true);
        } else if (key === Qt.Key_Return || key === Qt.Key_Enter || key === Qt.Key_Space) {
            if (!event.isAutoRepeat) root.activateKeyboardTarget();
        } else {
            handled = false;
        }
        if (handled) event.accepted = true;
        return handled;
    }

    onVisibleChanged: {
        if (visible) {
            root.initialDesktopId = KWinService.currentDesktopId;
            root.initialActiveWindow = KWinService.activeWindowId;
            KWinService.refreshActiveWindow();
        } else {
            root.setKeyboardTarget(null);
            root.initialDesktopId = "";
            root.initialActiveWindow = "";
            root.closed();
        }
    }

    Connections {
        target: KWinService
        function onDesktopChanged(index, id) {
            if (!root.visible) return;
            if (root.initialDesktopId !== "" && id !== "" && id !== root.initialDesktopId) {
                root.close();
            }
        }
        function onShowingDesktopChanged() {
            root.close();
        }
        function onActiveWindowChanged(winId) {
            if (!root.visible) return;
            if (root.initialActiveWindow === "") {
                root.initialActiveWindow = winId;
            } else if (winId !== "" && winId !== root.initialActiveWindow) {
                root.close();
            }
        }
    }

    Timer {
        id: activeWinPollTimer
        interval: 200
        repeat: true
        running: root.visible
        onTriggered: KWinService.refreshActiveWindow()
    }

    anchor.window: root.parentWindow
    anchor.item: root.anchorItem

    anchor.edges: {
        switch (root.edge) {
            case "top": return Edges.Bottom;
            case "bottom": return Edges.Top;
            case "left": return Edges.Right;
            case "right": return Edges.Left;
            default: return Edges.Bottom;
        }
    }

    anchor.gravity: {
        switch (root.edge) {
            case "top": return Edges.Bottom;
            case "bottom": return Edges.Top;
            case "left": return Edges.Right;
            case "right": return Edges.Left;
            default: return Edges.Bottom;
        }
    }

    anchor.adjustment: PopupAdjustment.Slide | PopupAdjustment.Flip

    anchor.margins.top: root.edge === "top" ? root.offset : 0
    anchor.margins.bottom: root.edge === "bottom" ? root.offset : 0
    anchor.margins.left: root.edge === "left" ? root.offset : 0
    anchor.margins.right: root.edge === "right" ? root.offset : 0

    color: "transparent"

    BackgroundEffect.blurRegion: Region {
        item: ConfigService.blurEnabled ? popupSurface : null
    }

    default property alias content: popupContent.data
    property alias surface: popupSurface

    Surface {
        id: popupSurface
        anchors.fill: parent
        radius: Theme.radiusLarge
        color: Theme.alpha(Theme.background, Theme.popupOpacity)
        border.color: Theme.border
        border.width: 1
        focus: root.visible
        Keys.onEscapePressed: root.close()
        Keys.onPressed: event => {
            root.handleKeyEvent(event);
        }
        Accessible.role: Accessible.PopupMenu
        Accessible.name: root.accessibleName

        Item {
            id: popupContent
            anchors.fill: parent
        }
    }
}
