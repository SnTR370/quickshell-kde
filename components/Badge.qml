import QtQuick
import "../services"

Rectangle {
    id: root

    property int count: 0
    property color badgeColor: Theme.error

    implicitWidth: Math.max(16, countText.implicitWidth + 8)
    implicitHeight: 16
    radius: height / 2
    color: root.badgeColor
    visible: count > 0

    Text {
        id: countText
        anchors.centerIn: parent
        text: root.count > 99 ? "99+" : String(root.count)
        color: "#ffffff"
        font.family: Theme.fontFamily
        font.pixelSize: 9
        font.bold: true
    }
}
