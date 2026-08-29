import QtQuick
import QtQuick.Layouts
import "../../services"
import "../../components"

Surface {
    id: root

    property var barWindowRef: null
    property string surfaceEdge: "top"

    implicitHeight: Math.max(20, ConfigService.barHeight - 6)
    implicitWidth: layout.implicitWidth + 10
    radius: Theme.radiusSmall
    color: clockMouse.containsMouse ? Theme.hover : "transparent"

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
        spacing: 6

        SvgIcon {
            icon: "preferences-system-time"
            size: 14
            color: Theme.accent
        }

        Text {
            text: root.currentTime
            color: Theme.foreground
            font.family: Theme.fontFamilyMono
            font.pixelSize: Theme.fontSizeSmall
            font.bold: true
        }

        Text {
            text: root.currentDate
            color: Theme.foregroundMuted
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeSmall - 1
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
