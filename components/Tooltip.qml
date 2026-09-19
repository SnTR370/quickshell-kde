import QtQuick
import Quickshell
import "../services"

Item {
    id: root

    property string text: ""
    property bool show: false
    property var parentWindow: null
    property Item anchorItem: null
    property string edge: "bottom"
    property int offset: 4

    // When parentWindow is provided, render as an unclipped Wayland PopupWindow (Qt::ToolTip)
    Loader {
        id: popupLoader
        active: root.parentWindow !== null && root.show && root.text.length > 0
        sourceComponent: PopupWindow {
            id: pop
            anchor.window: root.parentWindow
            anchor.item: root.anchorItem || root.parent
            anchor.edges: {
                switch (root.edge) {
                    case "top": return Edges.Bottom;
                    case "bottom": return Edges.Top;
                    case "left": return Edges.Right;
                    case "right": return Edges.Left;
                    default: return Edges.Top;
                }
            }
            anchor.gravity: {
                switch (root.edge) {
                    case "top": return Edges.Bottom;
                    case "bottom": return Edges.Top;
                    case "left": return Edges.Right;
                    case "right": return Edges.Left;
                    default: return Edges.Top;
                }
            }
            anchor.adjustment: PopupAdjustment.Slide | PopupAdjustment.Flip
            anchor.margins.top: root.edge === "top" ? root.offset : 0
            anchor.margins.bottom: root.edge === "bottom" ? root.offset : 0
            anchor.margins.left: root.edge === "left" ? root.offset : 0
            anchor.margins.right: root.edge === "right" ? root.offset : 0

            visible: root.show && root.text.length > 0
            grabFocus: false
            color: "transparent"

            Rectangle {
                width: Math.min(popupLabel.implicitWidth + 16, 360)
                height: popupLabel.implicitHeight + 8
                radius: Theme.radiusSmall
                color: Theme.card
                border.color: Theme.border
                border.width: 1

                Text {
                    id: popupLabel
                    anchors.centerIn: parent
                    width: Math.min(implicitWidth, 344)
                    text: root.text
                    color: Theme.foreground
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                    elide: Text.ElideRight
                }
            }
        }
    }

    // Inline fallback when parentWindow is null (e.g. within full application windows)
    Item {
        id: inlineBubbleHost
        visible: root.parentWindow === null && root.show && root.text.length > 0
        anchors.horizontalCenter: parent ? parent.horizontalCenter : undefined
        anchors.bottom: parent ? parent.top : undefined
        anchors.bottomMargin: root.offset
        z: 9999

        Rectangle {
            id: bubble
            anchors.centerIn: parent
            width: Math.min(label.implicitWidth + 16, 360)
            height: label.implicitHeight + 8
            radius: Theme.radiusSmall
            color: Theme.card
            border.color: Theme.border
            border.width: 1
            opacity: inlineBubbleHost.visible ? 1.0 : 0.0
            scale: inlineBubbleHost.visible ? 1.0 : 0.85

            Behavior on opacity { NumberAnimation { duration: Theme.animDurationFast } }
            Behavior on scale { NumberAnimation { duration: Theme.animDurationFast; easing.type: Easing.OutBack } }

            Text {
                id: label
                anchors.centerIn: parent
                width: Math.min(implicitWidth, 344)
                text: root.text
                color: Theme.foreground
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                elide: Text.ElideRight
            }
        }
    }
}
