import QtQuick
import Quickshell.Widgets
import "../services"

Item {
    id: root

    property string icon: ""
    property color color: Theme.foreground
    property real size: 20

    implicitWidth: size
    implicitHeight: size
    width: size
    height: size

    readonly property bool hasScheme: icon.indexOf("://") !== -1 || icon.startsWith("qspixmap:")
    readonly property bool isPath: icon.startsWith("/")

    IconImage {
        id: iconImg
        anchors.fill: parent
        source: root.icon ? (root.hasScheme ? root.icon : (root.isPath ? ("file://" + root.icon) : ("image://icon/" + root.icon))) : ""
        visible: status === Image.Ready
    }

    // Text fallback if icon image fails or if icon is text/nerd font
    Text {
        anchors.centerIn: parent
        visible: !iconImg.visible && root.icon.length > 0 && root.icon.length <= 4
        text: root.icon
        color: root.color
        font.pixelSize: root.size * 0.8
        font.family: Theme.fontFamilyMono
    }
}
