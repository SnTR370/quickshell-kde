import QtQuick
import QtQuick.Layouts
import "../../services"
import "../../components"

Surface {
    id: root

    visible: PowerService.isPresent
    implicitHeight: 34
    implicitWidth: layout.implicitWidth + 12
    radius: Theme.radiusSmall
    color: batMouse.containsMouse ? Theme.hover : Theme.alpha(Theme.surfaceVariant, 0.6)

    readonly property string iconName: {
        if (PowerService.isCharging) return "battery-charging";
        if (PowerService.percentage > 0.8) return "battery-100";
        if (PowerService.percentage > 0.6) return "battery-080";
        if (PowerService.percentage > 0.4) return "battery-060";
        if (PowerService.percentage > 0.2) return "battery-040";
        return "battery-020";
    }

    readonly property color iconColor: {
        if (PowerService.isCharging) return Theme.success;
        if (PowerService.percentage <= 0.2) return Theme.error;
        if (PowerService.percentage <= 0.4) return Theme.warning;
        return Theme.foreground;
    }

    RowLayout {
        id: layout
        anchors.centerIn: parent
        spacing: 6

        SvgIcon {
            icon: root.iconName
            size: 16
            color: root.iconColor
        }

        Text {
            text: Math.round(PowerService.percentage * 100) + "%"
            color: Theme.foreground
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeSmall
            font.bold: true
        }
    }

    MouseArea {
        id: batMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: KWinService.openKdeSettings("kcm_powerdevilprofilesconfig")
    }
}
