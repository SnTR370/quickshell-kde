import QtQuick
import QtQuick.Layouts
import "../../services"
import "../../components"

Surface {
    id: root

    implicitWidth: 220
    implicitHeight: 64
    radius: Theme.radiusLarge
    color: Theme.alpha(Theme.card, 0.95)
    border.color: Theme.border
    border.width: 1

    readonly property string iconName: {
        if (AudioService.muted) return "audio-volume-muted";
        if (AudioService.isHeadphone) return "audio-headphones";
        if (AudioService.volume > 0.66) return "audio-volume-high";
        if (AudioService.volume > 0.33) return "audio-volume-medium";
        if (AudioService.volume > 0.0) return "audio-volume-low";
        return "audio-volume-muted";
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 12

        SvgIcon {
            icon: root.iconName
            size: 28
            color: AudioService.muted ? Theme.error : Theme.primary
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4

            RowLayout {
                Layout.fillWidth: true

                Text {
                    text: AudioService.muted ? "Muted" : "Volume"
                    color: Theme.foreground
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                    font.bold: true
                }

                Item { Layout.fillWidth: true }

                Text {
                    text: Math.round(AudioService.volume * 100) + "%"
                    color: Theme.foregroundMuted
                    font.family: Theme.fontFamilyMono
                    font.pixelSize: Theme.fontSizeSmall
                }
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 6
                radius: 3
                color: Theme.surfaceVariant

                Rectangle {
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: Math.min(parent.width, parent.width * AudioService.volume)
                    radius: 3
                    color: AudioService.muted ? Theme.error : Theme.primary
                }
            }
        }
    }
}
