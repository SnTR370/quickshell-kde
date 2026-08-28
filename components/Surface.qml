import QtQuick
import "../services"

Rectangle {
    id: root

    property real elevation: 1
    property bool borderVisible: true

    color: Theme.alpha(Theme.surface, Theme.barOpacity)
    radius: Theme.radiusMedium
    border.color: Theme.alpha(Theme.border, 0.7)
    border.width: borderVisible ? 1 : 0

    Behavior on color { ColorAnimation { duration: Theme.animDurationNormal } }
    Behavior on border.color { ColorAnimation { duration: Theme.animDurationNormal } }
}
