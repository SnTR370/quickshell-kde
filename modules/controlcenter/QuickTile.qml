import QtQuick
import QtQuick.Layouts
import "../../services"
import "../../components"

Rectangle {
    id: root

    property string icon: ""
    property color iconColor: Theme.foreground
    property string title: ""
    property string subtitle: ""
    property bool active: false
    property color activeColor: Theme.primary
    property string badgeText: ""
    property color badgeColor: Theme.primary
    property string tooltip: ""
    property var parentWindow: null
    property string surfaceEdge: "top"

    signal clicked()

    Layout.fillWidth: true
    implicitHeight: 54
    radius: Theme.radiusMedium
    color: root.active ? Theme.alpha(root.activeColor, 0.20) : (mouseArea.containsMouse ? Theme.hover : Theme.alpha(Theme.surfaceVariant, 0.6))
    border.color: root.active ? root.activeColor : Theme.alpha(Theme.border, 0.5)
    border.width: root.active ? 1.5 : 1

    scale: mouseArea.pressed ? 0.98 : 1.0

    Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }
    Behavior on border.color { ColorAnimation { duration: Theme.animDurationFast } }
    Behavior on scale { NumberAnimation { duration: Theme.animDurationFast; easing.type: Easing.OutCubic } }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 10
        anchors.rightMargin: 10
        spacing: 10

        // Circular Icon Badge
        Rectangle {
            id: iconBadge
            Layout.preferredWidth: 34
            Layout.preferredHeight: 34
            radius: 17
            color: root.active ? root.activeColor : Theme.alpha(Theme.surface, 0.8)
            border.color: root.active ? Qt.lighter(root.activeColor, 1.2) : Theme.alpha(Theme.border, 0.6)
            border.width: 1

            Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

            SvgIcon {
                anchors.centerIn: parent
                icon: root.icon
                size: 18
                color: root.active ? Theme.contrastColor(root.activeColor) : root.iconColor
                visible: root.icon.length > 0
            }
        }

        // Title and Subtitle Text Column
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 1

            Text {
                text: root.title
                color: root.active ? Theme.contrastColor(Theme.background) : Theme.foreground
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall + 1
                font.bold: true
                elide: Text.ElideRight
                Layout.fillWidth: true
            }

            Text {
                text: root.subtitle
                color: root.active ? Theme.contrastColor(Theme.background) : Theme.foregroundMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall - 1
                elide: Text.ElideRight
                Layout.fillWidth: true
                visible: root.subtitle.length > 0
            }
        }

        // Optional Trailing Badge
        Badge {
            text: root.badgeText
            badgeColor: root.badgeColor
            visible: root.badgeText.length > 0
        }
    }

    Tooltip {
        parentWindow: root.parentWindow
        anchorItem: root
        edge: root.surfaceEdge
        text: root.tooltip
        show: root.tooltip.length > 0 && mouseArea.containsMouse && !mouseArea.pressed
    }

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
