import QtQuick
import QtQuick.Layouts
import "../../services"
import "../../components"
import "../media"

Surface {
    id: root

    property var barWindowRef: null
    property string surfaceEdge: "top"

    visible: MprisService.hasPlayers
    implicitHeight: Math.max(20, ConfigService.barHeight - 6)
    implicitWidth: layout.implicitWidth + 8
    radius: Theme.radiusSmall
    color: (mediaMouse.containsMouse || ConfigService.mediaPopupVisible) ? Theme.hover : "transparent"

    MouseArea {
        id: mediaMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: ConfigService.toggleMediaPopup()
    }

    RowLayout {
        id: layout
        anchors.centerIn: parent
        spacing: 4

        IconButton {
            size: Math.min(root.implicitHeight - 4, 20)
            icon: MprisService.isPlaying ? "media-playback-pause" : "media-playback-start"
            iconColor: Theme.accent
            onClicked: MprisService.playPause()
        }

        Text {
            text: (MprisService.trackArtist ? (MprisService.trackArtist + " - ") : "") + MprisService.trackTitle
            color: Theme.foreground
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeSmall
            elide: Text.ElideRight
            Layout.maximumWidth: 160
        }
    }

    // Lazy-loaded Media Popup
    Loader {
        id: mediaPopupLoader
        active: ConfigService.mediaPopupVisible && MprisService.hasPlayers
        sourceComponent: MediaPopup {
            parentWindow: root.barWindowRef || root.Window.window
            anchorItem: root
            edge: root.surfaceEdge
            onClosed: ConfigService.mediaPopupVisible = false
        }
    }
}
