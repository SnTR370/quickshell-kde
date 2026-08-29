import QtQuick
import QtQuick.Layouts
import "../../services"
import "../../components"
import "."

Item {
    id: root

    property var parentWindowRef: null
    property var app: null
    property string appId: ""
    property string appName: app ? app.name : appId
    property string appIcon: app ? app.icon : appId
    property bool isRunning: WindowService.isAppRunning(root.appId)
    property bool isPinned: ConfigService.isDockPinned(root.appId)
    property real baseSize: ConfigService.dockIconSize
    property bool menuOpen: false

    implicitWidth: baseSize + 8
    implicitHeight: baseSize + 8

    Rectangle {
        id: iconContainer
        anchors.centerIn: parent
        width: root.baseSize
        height: root.baseSize
        radius: Theme.radiusSmall
        color: dockItemMouse.containsMouse ? Theme.hover : "transparent"
        scale: dockItemMouse.pressed ? 0.92 : (dockItemMouse.containsMouse ? 1.16 : 1.0)

        Behavior on scale { NumberAnimation { duration: Theme.animDurationFast; easing.type: Theme.animEasingBack } }
        Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

        SvgIcon {
            anchors.centerIn: parent
            icon: root.appIcon || "application-x-executable"
            size: root.baseSize * 0.8
        }

        // Running indicator dot
        Rectangle {
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 2
            anchors.horizontalCenter: parent.horizontalCenter
            width: 6
            height: 3
            radius: 1.5
            color: Theme.primary
            visible: root.isRunning

            Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }
        }
    }

    Tooltip {
        text: root.appName + (root.isRunning ? " (Running)" : "")
        show: dockItemMouse.containsMouse && !dockItemMouse.pressed && !root.menuOpen
    }

    // Lazy-loaded Context Menu Popup
    Loader {
        id: menuLoader
        active: root.menuOpen
        sourceComponent: DockMenu {
            parentWindow: root.parentWindowRef || root.Window.window
            anchorItem: iconContainer
            edge: ConfigService.dockEdge
            appId: root.appId
            app: root.app
            isRunning: root.isRunning
            isPinned: root.isPinned
            onActionTriggered: root.menuOpen = false
            onClosed: root.menuOpen = false
        }
    }

    MouseArea {
        id: dockItemMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton

        onClicked: mouse => {
            if (mouse.button === Qt.RightButton) {
                root.menuOpen = !root.menuOpen;
            } else if (mouse.button === Qt.MiddleButton) {
                ApplicationService.launchAppId(root.appId);
            } else {
                root.menuOpen = false;
                if (root.isRunning) {
                    WindowService.activateApp(root.appId);
                } else if (root.app) {
                    ApplicationService.launch(root.app);
                } else {
                    ApplicationService.launchAppId(root.appId);
                }
            }
        }
    }
}
