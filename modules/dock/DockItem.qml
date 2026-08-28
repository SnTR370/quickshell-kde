import QtQuick
import QtQuick.Layouts
import "../../services"
import "../../components"

Item {
    id: root

    property var app: null
    property string appId: ""
    property string appName: app ? app.name : appId
    property string appIcon: app ? app.icon : appId
    property bool isRunning: false
    property real baseSize: ConfigService.dockIconSize

    implicitWidth: baseSize + 8
    implicitHeight: baseSize + 8

    Rectangle {
        id: iconContainer
        anchors.centerIn: parent
        width: root.baseSize
        height: root.baseSize
        radius: Theme.radiusSmall
        color: dockItemMouse.containsMouse ? Theme.hover : "transparent"
        scale: dockItemMouse.pressed ? 0.9 : (dockItemMouse.containsMouse ? 1.18 : 1.0)

        Behavior on scale { NumberAnimation { duration: Theme.animDurationFast; easing.type: Easing.OutBack } }
        Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

        SvgIcon {
            anchors.centerIn: parent
            icon: root.appIcon || "application-x-executable"
            size: root.baseSize * 0.8
        }

        // Active indicator dot
        Rectangle {
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 2
            anchors.horizontalCenter: parent.horizontalCenter
            width: 4
            height: 4
            radius: 2
            color: Theme.primary
            visible: root.isRunning
        }
    }

    Tooltip {
        text: root.appName
        show: dockItemMouse.containsMouse && !dockItemMouse.pressed
    }

    MouseArea {
        id: dockItemMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton

        onClicked: mouse => {
            if (mouse.button === Qt.RightButton) {
                ApplicationService.togglePin(root.appId);
            } else {
                if (root.app) {
                    ApplicationService.launch(root.app);
                } else {
                    ApplicationService.launchAppId(root.appId);
                }
            }
        }
    }
}
