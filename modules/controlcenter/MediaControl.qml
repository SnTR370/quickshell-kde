import QtQuick
import QtQuick.Layouts
import "../../services"
import "../../components"

Surface {
    id: root

    visible: MprisService.hasPlayers
    Layout.fillWidth: true
    implicitHeight: MprisService.hasPlayers ? (mediaLayout.implicitHeight + 20) : 0
    radius: Theme.radiusMedium
    color: Theme.alpha(Theme.surface, 0.7)
    border.color: Theme.alpha(Theme.border, 0.6)

    ColumnLayout {
        id: mediaLayout
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        // Header
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            SvgIcon {
                icon: "media-playback-start"
                size: 14
                color: Theme.accent
            }

            Text {
                text: MprisService.playerIdentity || "Media Player"
                color: Theme.foregroundMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall - 1
                font.bold: true
                elide: Text.ElideRight
                Layout.fillWidth: true
            }

            Badge {
                text: MprisService.isPlaying ? "Playing" : "Paused"
                badgeColor: MprisService.isPlaying ? Theme.success : Theme.foregroundMuted
            }
        }

        // Body: Album art + Track Details + Playback Controls
        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            // Album Art Thumbnail
            Rectangle {
                Layout.preferredWidth: 44
                Layout.preferredHeight: 44
                radius: Theme.radiusSmall
                color: Theme.surfaceVariant
                clip: true

                Image {
                    id: artImage
                    anchors.fill: parent
                    source: MprisService.trackArtUrl
                    sourceSize: Qt.size(88, 88)
                    asynchronous: true
                    visible: source.toString().length > 0 && status === Image.Ready
                    fillMode: Image.PreserveAspectCrop
                }

                SvgIcon {
                    anchors.centerIn: parent
                    icon: "audio-x-generic"
                    size: 22
                    color: Theme.foregroundMuted
                    visible: !artImage.visible
                }
            }

            // Track info
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                Text {
                    text: MprisService.trackTitle || "No Track Playing"
                    color: Theme.foreground
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                    font.bold: true
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                Text {
                    text: MprisService.trackArtist || "Unknown Artist"
                    color: Theme.foregroundMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall - 1
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
            }

            // Controls
            RowLayout {
                spacing: 4

                IconButton {
                    size: 28
                    icon: "media-skip-backward"
                    iconSize: 14
                    iconColor: Theme.foreground
                    enabled: MprisService.canGoPrevious
                    onClicked: MprisService.previous()
                }

                IconButton {
                    size: 32
                    icon: MprisService.isPlaying ? "media-playback-pause" : "media-playback-start"
                    iconSize: 16
                    iconColor: Theme.contrastColor(Theme.primary)
                    backgroundColor: Theme.primary
                    hoverColor: Qt.lighter(Theme.primary, 1.1)
                    radius: 16
                    onClicked: MprisService.playPause()
                }

                IconButton {
                    size: 28
                    icon: "media-skip-forward"
                    iconSize: 14
                    iconColor: Theme.foreground
                    enabled: MprisService.canGoNext
                    onClicked: MprisService.next()
                }
            }
        }
    }
}
