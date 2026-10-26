import QtQuick
import QtQuick.Layouts
import "../../services"
import "../../components"

Surface {
    id: root

    signal actionTriggered()

    Layout.fillWidth: true
    implicitHeight: mainLayout.implicitHeight + 20
    radius: Theme.radiusMedium
    color: Theme.alpha(Theme.surface, 0.7)
    border.color: Theme.alpha(Theme.border, 0.6)

    ColumnLayout {
        id: mainLayout
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        // Header
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            SvgIcon {
                icon: AudioService.isHeadphone ? "audio-headphones" : "audio-speakers"
                size: 16
                color: AudioService.muted ? Theme.error : Theme.primary
            }

            Text {
                text: "Volume"
                color: Theme.foreground
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                font.bold: true
            }

            Text {
                text: "• " + AudioService.sinkDescription
                color: Theme.foregroundMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall - 1
                elide: Text.ElideRight
                Layout.fillWidth: true
            }

            IconButton {
                size: 24
                icon: "preferences-system"
                iconSize: 14
                tooltip: "Audio Settings"
                onClicked: {
                    root.actionTriggered();
                    AudioService.openVolumeControl();
                }
            }
        }

        // Output Slider Row
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            IconButton {
                size: 28
                icon: AudioService.muted ? "audio-volume-muted" : (AudioService.volume > 0.5 ? "audio-volume-high" : (AudioService.volume > 0 ? "audio-volume-low" : "audio-volume-muted"))
                iconSize: 16
                iconColor: AudioService.muted ? Theme.error : Theme.primary
                tooltip: AudioService.muted ? "Unmute Output" : "Mute Output"
                onClicked: AudioService.toggleMute()
            }

            Slider {
                Layout.fillWidth: true
                value: AudioService.volume
                minimumValue: 0.0
                maximumValue: 1.5
                stepSize: 0.02
                progressColor: AudioService.muted ? Theme.error : Theme.primary
                onValueModified: val => AudioService.setVolume(val, false)
            }

            Text {
                text: AudioService.muted ? "Muted" : (Math.round(AudioService.volume * 100) + "%")
                color: AudioService.muted ? Theme.error : Theme.foregroundMuted
                font.family: Theme.fontFamilyMono
                font.pixelSize: Theme.fontSizeSmall
                font.bold: true
                Layout.preferredWidth: 42
                horizontalAlignment: Text.AlignRight
            }
        }

        // Separator for input
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.alpha(Theme.border, 0.4)
        }

        // Input / Microphone Slider Row
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            IconButton {
                size: 28
                icon: AudioService.inputMuted ? "microphone-sensitivity-muted" : "audio-input-microphone"
                iconSize: 16
                iconColor: AudioService.inputMuted ? Theme.error : Theme.accent
                tooltip: AudioService.inputMuted ? "Unmute Microphone" : "Mute Microphone"
                onClicked: AudioService.toggleInputMute()
            }

            Slider {
                Layout.fillWidth: true
                value: AudioService.inputVolume
                minimumValue: 0.0
                maximumValue: 1.0
                stepSize: 0.02
                progressColor: AudioService.inputMuted ? Theme.error : Theme.accent
                onValueModified: val => AudioService.setInputVolume(val, false)
            }

            Text {
                text: AudioService.inputMuted ? "Muted" : (Math.round(AudioService.inputVolume * 100) + "%")
                color: AudioService.inputMuted ? Theme.error : Theme.foregroundMuted
                font.family: Theme.fontFamilyMono
                font.pixelSize: Theme.fontSizeSmall
                font.bold: true
                Layout.preferredWidth: 42
                horizontalAlignment: Text.AlignRight
            }
        }
    }
}
