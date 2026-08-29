import QtQuick
import QtQuick.Layouts
import "../../services"
import "../../components"

Surface {
    id: root

    property var barWindowRef: null
    property string surfaceEdge: "top"

    implicitHeight: Math.max(20, ConfigService.barHeight - 6)
    implicitWidth: rowLayout.implicitWidth + 4
    radius: Theme.radiusSmall
    color: "transparent"

    RowLayout {
        id: rowLayout
        anchors.centerIn: parent
        spacing: 3

        Repeater {
            model: KWinService.desktops

            Rectangle {
                id: wsItem
                required property var modelData
                required property int index

                implicitWidth: modelData.active ? 24 : 18
                implicitHeight: Math.min(root.implicitHeight - 6, 20)
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
