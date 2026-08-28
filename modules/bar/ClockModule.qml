import QtQuick
import QtQuick.Layouts
import "../../services"
import "../../components"

Surface {
    id: root

    implicitHeight: 34
    implicitWidth: layout.implicitWidth + 16
    radius: Theme.radiusSmall
    color: clockMouse.containsMouse ? Theme.hover : Theme.alpha(Theme.surfaceVariant, 0.6)

    property string currentTime: ""
    property string currentDate: ""

    function updateTime() {
        const now = new Date();
        root.currentTime = Qt.formatDateTime(now, "hh:mm:ss");
        root.currentDate = Qt.formatDateTime(now, "ddd, d MMM");
    }

    Timer {
        interval: 1000
        running: true
        repeat: true
        onTriggered: root.updateTime()
    }

    Component.onCompleted: updateTime()

    RowLayout {
        id: layout
        anchors.centerIn: parent
        spacing: 8

        SvgIcon {
            icon: "preferences-system-time"
            size: 16
            color: Theme.accent
        }

        Text {
            text: root.currentTime
            color: Theme.foreground
            font.family: Theme.fontFamilyMono
            font.pixelSize: Theme.fontSizeMedium
            font.bold: true
        }

        Text {
            text: root.currentDate
            color: Theme.foregroundMuted
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeSmall
        }
    }

    MouseArea {
        id: clockMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: KWinService.openKdeSettings("kcm_clock")
    }
}
