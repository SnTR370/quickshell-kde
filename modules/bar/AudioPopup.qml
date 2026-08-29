import QtQuick
import QtQuick.Layouts
import Quickshell
import "../../services"
import "../../components"

AnchoredPopup {
    id: root

    implicitWidth: 280
    implicitHeight: popupLayout.implicitHeight + 16

    ColumnLayout {
        id: popupLayout
        anchors.fill: parent
        anchors.margins: 12
        spacing: 12

        // Output Header
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            SvgIcon {
                icon: AudioService.isHeadphone ? "audio-headphones" : "audio-speakers"
                size: 20
                color: AudioService.muted ? Theme.error : Theme.primary
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                Text {
                    text: "Playback Device"
                    color: Theme.foregroundMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall - 1
                }

                Text {
                    text: AudioService.sinkDescription
                    color: Theme.foreground
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                    font.bold: true
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
            }

            IconButton {
                size: 28
                icon: "preferences-system"
                iconSize: 16
                tooltip: "Audio Settings"
                onClicked: {
                    AudioService.openVolumeControl();
                    root.close();
                }
            }
        }

        // Output Volume Control
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            IconButton {
                size: 28
                icon: AudioService.muted ? "audio-volume-muted" : "audio-volume-high"
                iconSize: 16
                iconColor: AudioService.muted ? Theme.error : Theme.primary
                tooltip: AudioService.muted ? "Unmute" : "Mute"
                onClicked: AudioService.toggleMute()
            }

            Slider {
                Layout.fillWidth: true
                value: AudioService.volume
                minimumValue: 0.0
                maximumValue: 1.0
                stepSize: 0.02
                progressColor: AudioService.muted ? Theme.error : Theme.primary
                onValueModified: val => AudioService.setVolume(val)
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

        // Separator
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.border
            opacity: 0.5
        }

        // Input Header & Control
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            IconButton {
                size: 28
                icon: AudioService.inputMuted ? "microphone-sensitivity-muted" : "audio-input-microphone"
                iconSize: 16
                iconColor: AudioService.inputMuted ? Theme.error : Theme.accent
                tooltip: AudioService.inputMuted ? "Unmute Mic" : "Mute Mic"
                onClicked: AudioService.toggleInputMute()
            }

            Slider {
                Layout.fillWidth: true
                value: AudioService.inputVolume
                minimumValue: 0.0
                maximumValue: 1.0
                stepSize: 0.02
                progressColor: AudioService.inputMuted ? Theme.error : Theme.accent
                onValueModified: val => AudioService.setInputVolume(val)
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
