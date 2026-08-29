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
    implicitHeight: 34
    implicitWidth: layout.implicitWidth + 12
    radius: Theme.radiusSmall
    color: (mediaMouse.containsMouse || ConfigService.mediaPopupVisible) ? Theme.hover : Theme.alpha(Theme.surfaceVariant, 0.6)

    RowLayout {
        id: layout
        anchors.centerIn: parent
        spacing: 6

        IconButton {
            size: 24
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

    MouseArea {
        id: mediaMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        z: -1
        onClicked: ConfigService.toggleMediaPopup()
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
