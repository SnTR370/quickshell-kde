import QtQuick
import "../services"

Item {
    id: root

    property string text: ""
    property bool show: false

    visible: show && text.length > 0
    anchors.horizontalCenter: parent.horizontalCenter
    anchors.bottom: parent.top
    anchors.bottomMargin: 8
    z: 9999

    Rectangle {
        id: bubble
        anchors.centerIn: parent
        width: label.implicitWidth + 16
        height: label.implicitHeight + 8
        radius: Theme.radiusSmall
        color: Theme.card
        border.color: Theme.border
        border.width: 1
        opacity: root.visible ? 1.0 : 0.0
        scale: root.visible ? 1.0 : 0.85

        Behavior on opacity { NumberAnimation { duration: Theme.animDurationFast } }
        Behavior on scale { NumberAnimation { duration: Theme.animDurationFast; easing.type: Easing.OutBack } }

        Text {
            id: label
            anchors.centerIn: parent
            text: root.text
            color: Theme.foreground
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeSmall
        }
    }
}
