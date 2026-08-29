import QtQuick
import "../services"

Rectangle {
    id: root

    property string text: ""
    property int count: 0
    property color badgeColor: Theme.error

    implicitWidth: Math.max(16, badgeText.implicitWidth + 8)
    implicitHeight: 16
    radius: height / 2
    color: root.badgeColor
    visible: root.text.length > 0 || root.count > 0

    Text {
        id: badgeText
        anchors.centerIn: parent
        text: root.text.length > 0 ? root.text : (root.count > 99 ? "99+" : String(root.count))
        color: "#ffffff"
        font.family: Theme.fontFamily
        font.pixelSize: 9
        font.bold: true
    }
}
