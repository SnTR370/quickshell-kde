import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import "../../services"
import "../../components"

Variants {
    id: root

    model: Quickshell.screens

    PanelWindow {
        id: mediaWin
        required property var modelData

        screen: modelData
        visible: ConfigService.mediaPopupVisible && MprisService.hasPlayers
        color: "transparent"

        anchors {
            top: true
            right: true
        }

        margins {
            top: 52
            right: 16
        }

        implicitWidth: 320
        implicitHeight: 180
        exclusiveZone: 0

        WlrLayershell.layer: WlrLayer.Overlay

        Surface {
            anchors.fill: parent
            radius: Theme.radiusLarge
            color: Theme.alpha(Theme.background, Theme.popupOpacity)
            border.color: Theme.border
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 10

                // Header: Player identity and close button
                RowLayout {
                    Layout.fillWidth: true

                    SvgIcon {
                        icon: "media-playback-start"
                        size: 16
                        color: Theme.accent
                    }

                    Text {
                        text: MprisService.playerIdentity
                        color: Theme.foregroundMuted
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                        font.bold: true
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    IconButton {
                        size: 20
                        icon: "window-close"
                        iconColor: Theme.foregroundMuted
                        onClicked: ConfigService.mediaPopupVisible = false
                    }
                }

                // Track info
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Rectangle {
                        implicitWidth: 48
                        implicitHeight: 48
                        radius: Theme.radiusSmall
                        color: Theme.surfaceVariant

                        Image {
                            anchors.fill: parent
                            source: MprisService.trackArtUrl
                            visible: source.toString().length > 0 && status === Image.Ready
                            fillMode: Image.PreserveAspectCrop
                        }

                        SvgIcon {
                            anchors.centerIn: parent
                            icon: "audio-x-generic"
                            size: 24
                            visible: !MprisService.trackArtUrl || MprisService.trackArtUrl.length === 0
                            color: Theme.foregroundMuted
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        Text {
                            text: MprisService.trackTitle
                            color: Theme.foreground
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSizeMedium
                            font.bold: true
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }

                        Text {
                            text: MprisService.trackArtist || "Unknown Artist"
                            color: Theme.foregroundMuted
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSizeSmall
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }
                }

                // Playback controls
                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 16

                    IconButton {
                        size: 32
                        icon: "media-skip-backward"
                        iconColor: Theme.foreground
                        enabled: MprisService.canGoPrevious
                        onClicked: MprisService.previous()
                    }

                    IconButton {
                        size: 40
                        icon: MprisService.isPlaying ? "media-playback-pause" : "media-playback-start"
                        iconColor: Theme.contrastColor(Theme.primary)
                        backgroundColor: Theme.primary
                        hoverColor: Qt.lighter(Theme.primary, 1.1)
                        radius: 20
                        onClicked: MprisService.playPause()
                    }

                    IconButton {
                        size: 32
                        icon: "media-skip-forward"
                        iconColor: Theme.foreground
                        enabled: MprisService.canGoNext
                        onClicked: MprisService.next()
                    }
                }
            }
        }
    }
}
