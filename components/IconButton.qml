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
    property int badgeCount: 0
    property bool active: false

    signal clicked(var mouse)
    signal rightClicked(var mouse)

    implicitWidth: text.length > 0 ? (contentRow.implicitWidth + 16) : size
    implicitHeight: size
    width: implicitWidth
    height: implicitHeight

    Rectangle {
        id: bgRect
        anchors.fill: parent
        radius: root.radius
        color: root.active ? root.activeColor : (mouseArea.containsMouse ? root.hoverColor : root.backgroundColor)
        border.color: Theme.border
        border.width: root.active ? 1 : 0
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
