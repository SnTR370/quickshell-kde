import QtQuick
import QtQuick.Layouts
import "../../services"
import "../../components"

Surface {
    id: root

    implicitHeight: 34
    implicitWidth: layout.implicitWidth + 14
    radius: Theme.radiusSmall
    color: audioMouse.containsMouse ? Theme.hover : Theme.alpha(Theme.surfaceVariant, 0.6)

    readonly property string iconName: {
        if (AudioService.muted) return "audio-volume-muted";
        if (AudioService.isHeadphone) return "audio-headphones";
        if (AudioService.volume > 0.66) return "audio-volume-high";
        if (AudioService.volume > 0.33) return "audio-volume-medium";
        if (AudioService.volume > 0.0) return "audio-volume-low";
        return "audio-volume-muted";
    }

    RowLayout {
        id: layout
        anchors.centerIn: parent
        spacing: 6

        SvgIcon {
            icon: root.iconName
            size: 16
            color: AudioService.muted ? Theme.error : Theme.primary
        }

        Text {
            text: AudioService.muted ? "Muted" : (Math.round(AudioService.volume * 100) + "%")
            color: AudioService.muted ? Theme.error : Theme.foreground
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeMedium
            font.bold: true
        }
    }

    MouseArea {
        id: audioMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton

        onClicked: mouse => {
            if (mouse.button === Qt.RightButton) {
                AudioService.openVolumeControl();
            } else {
                AudioService.toggleMute();
            }
        }

        onWheel: wheel => {
            if (wheel.angleDelta.y > 0) {
                AudioService.increaseVolume(0.05);
            } else {
                AudioService.decreaseVolume(0.05);
            }
        }
    }
}
