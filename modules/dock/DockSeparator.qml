import QtQuick
import QtQuick.Layouts
import "../../services"

Rectangle {
    property bool isVertical: false

    implicitWidth: isVertical ? 24 : 1
    implicitHeight: isVertical ? 1 : 24
    color: Theme.alpha(Theme.border, 0.6)
    Layout.alignment: Qt.AlignCenter
}
