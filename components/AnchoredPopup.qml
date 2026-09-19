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

    visible: true
    grabFocus: false

    function close() {
        root.visible = false;
        root.closed();
    }

    onVisibleChanged: {
        if (visible) {
            root.initialDesktopId = KWinService.currentDesktopId;
            root.initialActiveWindow = KWinService.activeWindowId;
            KWinService.refreshActiveWindow();
        } else {
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

        Item {
            id: popupContent
            anchors.fill: parent
        }
    }
}
