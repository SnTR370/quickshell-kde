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

    visible: true

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

        Item {
            id: popupContent
            anchors.fill: parent
        }
    }
}
