import QtQuick
import "../services"
import "."

Item {
    id: root

    property string icon: ""
    property string text: ""
    property color iconColor: Theme.foreground
    property color backgroundColor: "transparent"
    property color hoverColor: Theme.hover
    property color activeColor: Theme.active
    property real size: 34
    property real iconSize: 0
    property real radius: Theme.radiusSmall
    property string tooltip: ""
    property var parentWindow: null
    property string edge: "bottom"
    property int badgeCount: 0
    property bool active: false
    property string accessibleName: root.tooltip.length > 0 ? root.tooltip : root.text
    property string accessibleDescription: ""
    readonly property bool isVerticalEdge: (root.parentWindow && root.parentWindow.isVertical !== undefined)
        ? root.parentWindow.isVertical
        : (root.edge === "left" || root.edge === "right")

    signal clicked(var mouse)
    signal rightClicked(var mouse)

    activeFocusOnTab: root.visible && root.enabled
    Accessible.role: Accessible.Button
    Accessible.name: root.accessibleName
    Accessible.description: root.accessibleDescription
    Accessible.focusable: true
    Accessible.focused: root.activeFocus
    Accessible.onPressAction: root.activate()

    onActiveFocusChanged: {
        if (root.parentWindow && root.parentWindow.focusedDockItem !== undefined) {
            if (root.activeFocus) {
                root.parentWindow.focusedDockItem = root;
            } else if (root.parentWindow.focusedDockItem === root) {
                root.parentWindow.focusedDockItem = null;
            }
        }
    }

    function activate() {
        if (!root.enabled || !root.visible) return false;
        root.clicked(null);
        return true;
    }

    function getFocusableSiblings() {
        if (root.parentWindow && typeof root.parentWindow.getFocusableDockItems === "function") {
            const dockItems = root.parentWindow.getFocusableDockItems();
            if (dockItems && dockItems.length > 0) return dockItems;
        }
        if (!root.parent || !root.parent.children) return [root];
        const list = [];
        const kids = root.parent.children;
        for (let i = 0; i < kids.length; i++) {
            const c = kids[i];
            if (c && c.visible && c.enabled && c.activeFocusOnTab) {
                list.push(c);
            }
        }
        return list;
    }

    function moveSiblingFocus(step) {
        const items = getFocusableSiblings();
        if (items.length === 0) return false;
        const idx = items.indexOf(root);
        const nextIdx = idx >= 0
            ? ((idx + step + items.length) % items.length)
            : (step >= 0 ? 0 : items.length - 1);
        const target = items[nextIdx];
        if (target && target !== root) {
            target.forceActiveFocus();
            return true;
        }
        return false;
    }

    function focusBoundarySibling(last) {
        const items = getFocusableSiblings();
        if (items.length === 0) return false;
        const target = items[last ? (items.length - 1) : 0];
        if (target) {
            target.forceActiveFocus();
            return true;
        }
        return false;
    }

    Keys.onPressed: event => {
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space) {
            event.accepted = true;
            root.activate();
        } else if (event.key === Qt.Key_Menu || (event.key === Qt.Key_F10 && (event.modifiers & Qt.ShiftModifier))) {
            event.accepted = true;
            root.rightClicked(null);
        } else if (!root.isVerticalEdge && event.key === Qt.Key_Right) {
            event.accepted = true;
            root.moveSiblingFocus(1);
        } else if (!root.isVerticalEdge && event.key === Qt.Key_Left) {
            event.accepted = true;
            root.moveSiblingFocus(-1);
        } else if (root.isVerticalEdge && event.key === Qt.Key_Down) {
            event.accepted = true;
            root.moveSiblingFocus(1);
        } else if (root.isVerticalEdge && event.key === Qt.Key_Up) {
            event.accepted = true;
            root.moveSiblingFocus(-1);
        } else if (event.key === Qt.Key_Home) {
            event.accepted = true;
            root.focusBoundarySibling(false);
        } else if (event.key === Qt.Key_End) {
            event.accepted = true;
            root.focusBoundarySibling(true);
        } else if (event.key === Qt.Key_Escape) {
            event.accepted = true;
            if (root.parentWindow && root.parentWindow.activePopupItem) {
                root.parentWindow.activePopupItem = null;
            } else if (root.parentWindow && typeof root.parentWindow.releaseKeyboardFocus === "function") {
                root.parentWindow.releaseKeyboardFocus();
            } else {
                root.focus = false;
            }
        }
    }

    implicitWidth: text.length > 0 ? (contentRow.implicitWidth + 16) : size
    implicitHeight: size
    width: implicitWidth
    height: implicitHeight

    Rectangle {
        id: bgRect
        anchors.fill: parent
        radius: root.radius
        color: root.active ? root.activeColor : ((mouseArea.containsMouse || root.activeFocus) ? root.hoverColor : root.backgroundColor)
        border.color: root.activeFocus ? Theme.accent : Theme.border
        border.width: root.activeFocus ? 2 : (root.active ? 1 : 0)
        scale: mouseArea.pressed ? 0.92 : (mouseArea.containsMouse ? 1.05 : 1.0)

        Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }
        Behavior on scale { NumberAnimation { duration: Theme.animDurationFast; easing.type: Easing.OutCubic } }

        Row {
            id: contentRow
            anchors.centerIn: parent
            spacing: 6

            SvgIcon {
                icon: root.icon
                size: root.iconSize > 0 ? root.iconSize : (root.size * 0.55)
                color: root.active ? Theme.contrastColor(root.activeColor) : (mouseArea.containsMouse ? Qt.lighter(root.iconColor, 1.1) : root.iconColor)
                visible: root.icon.length > 0
                anchors.verticalCenter: parent.verticalCenter
            }

            Text {
                text: root.text
                color: root.active ? Theme.contrastColor(root.activeColor) : root.iconColor
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeMedium
                font.bold: true
                visible: root.text.length > 0
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }

    Badge {
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.topMargin: -4
        anchors.rightMargin: -4
        count: root.badgeCount
        visible: root.badgeCount > 0
    }

    Tooltip {
        parentWindow: root.parentWindow
        anchorItem: root
        edge: root.edge
        text: root.tooltip
        show: root.tooltip.length > 0 && mouseArea.containsMouse && !mouseArea.pressed
    }

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton

        onClicked: mouse => {
            if (mouse.button === Qt.RightButton) {
                root.rightClicked(mouse);
            } else {
                root.clicked(mouse);
            }
        }
    }
}
