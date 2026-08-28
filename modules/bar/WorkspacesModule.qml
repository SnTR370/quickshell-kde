import QtQuick
import QtQuick.Layouts
import "../../services"
import "../../components"

Surface {
    id: root

    implicitHeight: 34
    implicitWidth: rowLayout.implicitWidth + 8
    radius: Theme.radiusSmall
    color: Theme.alpha(Theme.surfaceVariant, 0.6)

    RowLayout {
        id: rowLayout
        anchors.centerIn: parent
        spacing: 4

        Repeater {
            model: KWinService.desktops

            Rectangle {
                id: wsItem
                required property var modelData
                required property int index

                implicitWidth: modelData.active ? 28 : 22
                implicitHeight: 22
                radius: Theme.radiusSmall
                color: modelData.active ? Theme.primary : (wsMouse.containsMouse ? Theme.hover : "transparent")

                Behavior on implicitWidth { NumberAnimation { duration: Theme.animDurationFast; easing.type: Easing.OutCubic } }
                Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

                Text {
                    anchors.centerIn: parent
                    text: String(modelData.index !== undefined ? (modelData.index + 1) : (index + 1))
                    color: modelData.active ? Theme.contrastColor(Theme.primary) : (wsMouse.containsMouse ? Theme.foreground : Theme.foregroundMuted)
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                    font.bold: modelData.active
                }

                MouseArea {
                    id: wsMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (modelData.id) {
                            KWinService.setCurrentDesktop(modelData.id);
                        } else {
                            KWinService.setCurrentDesktop(modelData.index !== undefined ? modelData.index : index);
                        }
                    }
                }
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        z: -1
        onWheel: wheel => {
            if (wheel.angleDelta.y > 0) {
                KWinService.previousDesktop();
            } else {
                KWinService.nextDesktop();
            }
        }
    }
}
