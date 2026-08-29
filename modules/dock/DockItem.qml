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
    readonly property var appWindows: WindowService.getWindowsForApp(root.appId)
    readonly property int windowCount: appWindows.length
    property real baseSize: ConfigService.dockIconSize
    property bool menuOpen: false
    property bool chooserOpen: false

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

        // Multi-window / Running indicator
        RowLayout {
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 2
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 2
            visible: root.isRunning

            // Dot 1 (Single window or first of multi)
            Rectangle {
                width: root.windowCount >= 3 ? 3 : (root.windowCount === 2 ? 4 : 6)
                height: 3
                radius: 1.5
                color: Theme.primary
            }

            // Dot 2 (for 2+ windows)
            Rectangle {
                width: root.windowCount >= 3 ? 3 : 4
                height: 3
                radius: 1.5
                color: Theme.primary
                visible: root.windowCount >= 2
            }

            // Dot 3 (for 3+ windows)
            Rectangle {
                width: 3
                height: 3
                radius: 1.5
                color: Theme.primary
                visible: root.windowCount >= 3
            }
        }
    }

    Tooltip {
        text: root.appName + (root.windowCount > 1 ? (" (" + root.windowCount + " Windows)") : (root.isRunning ? " (Running)" : ""))
        show: dockItemMouse.containsMouse && !dockItemMouse.pressed && !root.menuOpen && !root.chooserOpen
    }

    // Lazy-loaded Multi-Window Chooser Popup
    Loader {
        id: chooserLoader
        active: root.chooserOpen && root.windowCount > 1
        sourceComponent: WindowChooserPopup {
            parentWindow: root.parentWindowRef || root.Window.window
            anchorItem: iconContainer
            edge: ConfigService.dockEdge
            appId: root.appId
            app: root.app
            onWindowSelected: root.chooserOpen = false
            onClosed: root.chooserOpen = false
        }
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
                root.chooserOpen = false;
                root.menuOpen = !root.menuOpen;
            } else if (mouse.button === Qt.MiddleButton) {
                root.chooserOpen = false;
                root.menuOpen = false;
                ApplicationService.launchAppId(root.appId);
            } else {
                root.menuOpen = false;
                if (root.windowCount === 0) {
                    root.chooserOpen = false;
                    if (root.app) {
                        ApplicationService.launch(root.app);
                    } else {
                        ApplicationService.launchAppId(root.appId);
                    }
                } else if (root.windowCount === 1) {
                    root.chooserOpen = false;
                    WindowService.activateWindow(root.appWindows[0].id);
                } else {
                    root.chooserOpen = !root.chooserOpen;
                }
            }
        }
    }
}
