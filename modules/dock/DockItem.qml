import QtQuick
import "../../services"
import "../../components"
import "."

Item {
    id: root

    property var parentWindowRef: null
    property var app: null
    property string appId: ""
    property string appName: ApplicationService.cleanAppName(app ? app.name : appId)
    property string appIcon: app ? app.icon : appId
    property bool isRunning: WindowService.isAppRunning(root.appId)
    property bool isPinned: ConfigService.isDockPinned(root.appId)
    readonly property var appWindows: WindowService.getWindowsForApp(root.appId)
    readonly property int windowCount: appWindows.length
    readonly property bool isCurrentAppActive: WindowService.activeWindowId !== "" && appWindows.some(w => w.id === WindowService.activeWindowId)
    property real baseSize: ConfigService.dockIconSize
    property bool menuOpen: false
    property bool chooserOpen: false
    readonly property bool isPopupOpen: menuOpen || chooserOpen
    property bool tooltipActive: false
    property real bounceScale: 1.0
    readonly property real targetScale: (dockItemMouse.pressed ? 0.92 : ((dockItemMouse.containsMouse || root.isPopupOpen) ? 1.15 : 1.0)) * root.bounceScale

    Timer {
        id: tooltipDwellTimer
        interval: 320
        repeat: false
        onTriggered: {
            if (dockItemMouse.containsMouse && !dockItemMouse.pressed && !root.isPopupOpen && !(root.parentWindowRef && root.parentWindowRef.hasActivePopup)) {
                root.tooltipActive = true;
            }
        }
    }

    SequentialAnimation {
        id: clickBounceAnim
        NumberAnimation { target: root; property: "bounceScale"; to: 0.86; duration: 80; easing.type: Easing.OutQuad }
        NumberAnimation { target: root; property: "bounceScale"; to: 1.04; duration: 110; easing.type: Easing.OutQuad }
        NumberAnimation { target: root; property: "bounceScale"; to: 1.0; duration: 100; easing.type: Easing.OutCubic }
    }

    onMenuOpenChanged: {
        if (menuOpen && chooserOpen) {
            chooserOpen = false;
        }
        if (parentWindowRef && parentWindowRef.activePopupItem !== undefined) {
            if (menuOpen) {
                parentWindowRef.activePopupItem = root;
            } else if (parentWindowRef.activePopupItem === root && !root.chooserOpen) {
                parentWindowRef.activePopupItem = null;
            }
        }
    }

    onChooserOpenChanged: {
        if (chooserOpen && menuOpen) {
            menuOpen = false;
        }
        if (parentWindowRef && parentWindowRef.activePopupItem !== undefined) {
            if (chooserOpen) {
                parentWindowRef.activePopupItem = root;
            } else if (parentWindowRef.activePopupItem === root && !root.menuOpen) {
                parentWindowRef.activePopupItem = null;
            }
        }
    }

    Connections {
        target: root.parentWindowRef
        function onActivePopupItemChanged() {
            if (root.parentWindowRef && root.parentWindowRef.activePopupItem !== root) {
                root.menuOpen = false;
                root.chooserOpen = false;
            }
        }
    }

    Component.onDestruction: {
        tooltipDwellTimer.stop();
        clickBounceAnim.stop();
        if (parentWindowRef && parentWindowRef.activePopupItem === root) {
            parentWindowRef.activePopupItem = null;
        }
    }

    implicitWidth: baseSize + 8
    implicitHeight: baseSize + 8

    Rectangle {
        id: iconContainer
        anchors.centerIn: parent
        width: root.baseSize
        height: root.baseSize
        radius: Theme.radiusSmall
        color: dockItemMouse.pressed ? Theme.alpha(Theme.primary, 0.28)
             : root.isPopupOpen ? Theme.alpha(Theme.primary, 0.22)
             : dockItemMouse.containsMouse ? Theme.hover
             : "transparent"
        border.width: root.isPopupOpen ? 1 : 0
        border.color: Theme.alpha(Theme.primary, 0.45)
        scale: root.targetScale

        Behavior on scale {
            enabled: !clickBounceAnim.running
            NumberAnimation {
                duration: iconContainer.scale > 1.0 ? 160 : 130
                easing.type: iconContainer.scale > 1.0 ? Easing.OutBack : Easing.OutCubic
            }
        }
        Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }
        Behavior on border.color { ColorAnimation { duration: Theme.animDurationFast } }

        SvgIcon {
            anchors.centerIn: parent
            icon: root.appIcon || "application-x-executable"
            size: root.baseSize * 0.8
        }

        // Multi-window / Running indicator
        Row {
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 2
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 2
            visible: root.isRunning
            opacity: root.isRunning ? 1.0 : 0.0
            Behavior on opacity { NumberAnimation { duration: Theme.animDurationFast } }

            // Dot 1 (Single window or first of multi)
            Rectangle {
                width: root.isCurrentAppActive ? 10 : (root.windowCount >= 3 ? 3 : (root.windowCount === 2 ? 4 : 6))
                height: 3
                radius: 1.5
                color: root.isCurrentAppActive ? Theme.accent : Theme.primary
                Behavior on width { NumberAnimation { duration: Theme.animDurationFast; easing.type: Easing.OutCubic } }
                Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }
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
        parentWindow: root.parentWindowRef
        anchorItem: iconContainer
        edge: ConfigService.dockEdge
        offset: 4
        text: root.appName + (root.windowCount > 1 ? (" (" + root.windowCount + " Windows)") : "")
        show: root.tooltipActive && dockItemMouse.containsMouse && !dockItemMouse.pressed && !root.isPopupOpen && !(root.parentWindowRef && root.parentWindowRef.hasActivePopup) && (root.parentWindowRef ? root.parentWindowRef.isRevealed : true)
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

        onEntered: {
            WindowService.refreshActiveWindow();
            if (!root.isPopupOpen && !(root.parentWindowRef && root.parentWindowRef.hasActivePopup)) {
                tooltipDwellTimer.restart();
            }
        }

        onExited: {
            tooltipDwellTimer.stop();
            root.tooltipActive = false;
        }

        onClicked: mouse => {
            tooltipDwellTimer.stop();
            root.tooltipActive = false;
            if (mouse.button === Qt.RightButton) {
                root.menuOpen = !root.menuOpen;
            } else if (mouse.button === Qt.MiddleButton) {
                clickBounceAnim.restart();
                root.chooserOpen = false;
                root.menuOpen = false;
                if (root.parentWindowRef && root.parentWindowRef.activePopupItem) {
                    root.parentWindowRef.activePopupItem = null;
                }
                ApplicationService.launchAppId(root.appId);
            } else {
                clickBounceAnim.restart();
                if (root.windowCount === 0) {
                    root.menuOpen = false;
                    root.chooserOpen = false;
                    if (root.parentWindowRef && root.parentWindowRef.activePopupItem) {
                        root.parentWindowRef.activePopupItem = null;
                    }
                    if (root.app) {
                        ApplicationService.launch(root.app);
                    } else {
                        ApplicationService.launchAppId(root.appId);
                    }
                } else if (root.windowCount === 1) {
                    root.menuOpen = false;
                    root.chooserOpen = false;
                    if (root.parentWindowRef && root.parentWindowRef.activePopupItem) {
                        root.parentWindowRef.activePopupItem = null;
                    }
                    WindowService.toggleWindow(root.appWindows[0].id);
                } else {
                    const activeWin = WindowService.getActiveWindowForApp(root.appId);
                    if (activeWin && !root.chooserOpen) {
                        root.menuOpen = false;
                        if (root.parentWindowRef && root.parentWindowRef.activePopupItem) {
                            root.parentWindowRef.activePopupItem = null;
                        }
                        WindowService.toggleWindow(activeWin.id);
                    } else {
                        root.chooserOpen = !root.chooserOpen;
                    }
                }
            }
        }
    }
}
