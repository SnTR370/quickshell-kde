import QtQuick
import QtQuick.Layouts
import Quickshell
import "../../services"
import "../../components"

AnchoredPopup {
    id: root

    property string appId: ""
    property var app: null
    property bool isRunning: false
    property bool isPinned: false
    readonly property var appWindows: WindowService.getWindowsForApp(root.appId)
    readonly property var appActions: {
        const _apps = ApplicationService.applications;
        return ApplicationService.getAppActions(root.app || root.appId);
    }
    readonly property bool hasCustomNewWindowAction: {
        const acts = root.appActions || [];
        for (let i = 0; i < acts.length; i++) {
            const aid = String(acts[i].id || "").toLowerCase();
            const aname = String(acts[i].name || "").toLowerCase();
            if (aid === "new-window" || aname === "new window") {
                return true;
            }
        }
        return false;
    }
    readonly property bool isVerticalDock: root.edge === "left" || root.edge === "right"
    readonly property bool canMoveLeft: root.isPinned && ApplicationService.canMovePinned(root.appId, "left")
    readonly property bool canMoveRight: root.isPinned && ApplicationService.canMovePinned(root.appId, "right")

    signal actionTriggered()

    function triggerQuickAction(actionId) {
        const ok = ApplicationService.launchAppAction(root.app || root.appId, actionId);
        if (ok) {
            root.actionTriggered();
        }
        return ok;
    }

    function moveLeft() {
        if (!root.canMoveLeft) return false;
        const ok = ApplicationService.movePinnedApp(root.appId, "left");
        if (ok) {
            root.actionTriggered();
        }
        return ok;
    }

    function moveRight() {
        if (!root.canMoveRight) return false;
        const ok = ApplicationService.movePinnedApp(root.appId, "right");
        if (ok) {
            root.actionTriggered();
        }
        return ok;
    }

    function triggerWindowAction(windowId, actionName, targetArg) {
        let ok = false;
        if (actionName === "activate") {
            ok = WindowService.activateWindow(windowId);
        } else if (actionName === "close") {
            ok = WindowService.closeWindow(windowId);
        } else if (actionName === "minimize" || actionName === "toggle-minimize") {
            ok = WindowService.toggleMinimizeWindow(windowId);
        } else if (actionName === "maximize" || actionName === "toggle-maximize") {
            ok = WindowService.toggleMaximizeWindow(windowId);
        } else if (actionName === "fullscreen" || actionName === "toggle-fullscreen") {
            ok = WindowService.toggleFullScreenWindow(windowId);
        } else if (actionName === "keep-above" || actionName === "toggle-keep-above") {
            ok = WindowService.toggleKeepAboveWindow(windowId);
        } else if (actionName === "move-output") {
            ok = WindowService.moveWindowToOutput(windowId, targetArg);
        } else if (actionName === "move-desktop") {
            ok = WindowService.moveWindowToDesktop(windowId, targetArg);
        }
        if (ok) {
            root.actionTriggered();
        }
        return ok;
    }

    Component.onCompleted: {
        WindowService.refreshWindowOutputs();
        KWinService.refreshDesktops();
    }

    implicitWidth: Math.max(220, Math.min(340, menuLayout.implicitWidth + 24))
    implicitHeight: menuLayout.implicitHeight + 16

    ColumnLayout {
        id: menuLayout
        anchors.fill: parent
        anchors.margins: 8
        spacing: 4

        // App Header
        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 4
            Layout.rightMargin: 4
            Layout.bottomMargin: 4
            spacing: 8

            SvgIcon {
                icon: root.app ? root.app.icon : root.appId
                size: 20
            }

            Text {
                text: ApplicationService.cleanAppName(root.app ? root.app.name : root.appId)
                color: Theme.foreground
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                font.bold: true
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: Theme.border
            opacity: 0.5
        }

        // Open Windows List (if multi-window or running)
        Repeater {
            model: root.appWindows

            ColumnLayout {
                id: winItem
                required property var modelData
                readonly property string windowId: modelData ? (modelData.id || "") : ""
                readonly property var windowState: WindowService.getWindowState(windowId)
                readonly property bool isMinimized: windowState ? Boolean(windowState.minimized) : false
                readonly property bool isMaximized: windowState ? Boolean(windowState.maximized) : false
                readonly property bool isFullScreen: windowState ? Boolean(windowState.fullScreen) : false
                readonly property bool isKeepAbove: windowState ? Boolean(windowState.keepAbove) : false
                readonly property bool isOnAllDesktops: windowState ? Boolean(windowState.onAllDesktops) : false
                readonly property bool canMinimize: WindowService.canMinimizeWindow(windowId)
                readonly property bool canMaximize: WindowService.canMaximizeWindow(windowId)
                readonly property bool canFullScreen: WindowService.canFullScreenWindow(windowId)
                readonly property bool canKeepAbove: WindowService.canKeepAboveWindow(windowId)
                readonly property bool canClose: WindowService.canCloseWindow(windowId)
                readonly property var targetOutputs: WindowService.getTargetOutputsForWindow(windowId)
                readonly property var targetDesktops: WindowService.getTargetDesktopsForWindow(windowId)
                Layout.fillWidth: true
                spacing: 3

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 28
                    radius: Theme.radiusSmall
                    color: winActivateMouse.containsMouse ? Theme.hover : "transparent"
                    Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        anchors.rightMargin: 4
                        spacing: 6

                        Item {
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            RowLayout {
                                anchors.fill: parent
                                spacing: 8

                                SvgIcon {
                                    icon: "window-duplicate"
                                    size: 14
                                    color: Theme.accent
                                }

                                Text {
                                    text: (winItem.modelData && winItem.modelData.title) ? winItem.modelData.title : (root.app ? root.app.name : root.appId)
                                    color: Theme.foreground
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeSmall
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                            }

                            MouseArea {
                                id: winActivateMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (WindowService.activateWindow(winItem.windowId)) {
                                        root.actionTriggered();
                                    }
                                }
                            }
                        }

                        // Move to Screen buttons (only shown when >1 output and valid targets exist)
                        Repeater {
                            model: winItem.targetOutputs

                            Rectangle {
                                id: moveOutBtn
                                required property string modelData
                                visible: winItem.targetOutputs.length > 0
                                implicitWidth: moveOutLabel.implicitWidth + 10
                                implicitHeight: 20
                                radius: Theme.radiusSmall
                                color: moveOutMouse.containsMouse ? Theme.alpha(Theme.primary, 0.22) : Theme.alpha(Theme.surface, 0.6)
                                border.width: 1
                                border.color: moveOutMouse.containsMouse ? Theme.primary : Theme.border
                                Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }
                                Behavior on border.color { ColorAnimation { duration: Theme.animDurationFast } }

                                Text {
                                    id: moveOutLabel
                                    anchors.centerIn: parent
                                    text: "→ " + moveOutBtn.modelData
                                    color: Theme.foreground
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fontSizeSmall - 2
                                }

                                MouseArea {
                                    id: moveOutMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (WindowService.moveWindowToOutput(winItem.windowId, moveOutBtn.modelData)) {
                                            root.actionTriggered();
                                        }
                                    }
                                }
                            }
                        }

                        // Graceful Close Window button
                        Rectangle {
                            id: closeWinBtn
                            implicitWidth: 22
                            implicitHeight: 22
                            radius: Theme.radiusSmall
                            opacity: winItem.canClose ? 1.0 : 0.45
                            color: (winItem.canClose && closeWinMouse.containsMouse) ? Theme.alpha(Theme.error, 0.22) : "transparent"
                            Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

                            SvgIcon {
                                anchors.centerIn: parent
                                icon: "window-close"
                                size: 13
                                color: (winItem.canClose && closeWinMouse.containsMouse) ? Theme.error : (winItem.canClose ? Theme.foreground : Theme.foregroundMuted)
                            }

                            MouseArea {
                                id: closeWinMouse
                                anchors.fill: parent
                                enabled: winItem.canClose
                                hoverEnabled: true
                                cursorShape: winItem.canClose ? Qt.PointingHandCursor : Qt.ArrowCursor
                                onClicked: {
                                    if (WindowService.closeWindow(winItem.windowId)) {
                                        root.actionTriggered();
                                    }
                                }
                            }
                        }
                    }
                }

                // Native KWin Window State Actions Row (Minimize, Maximize, Fullscreen, Keep Above)
                RowLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: 8
                    Layout.rightMargin: 4
                    spacing: 4

                    // Minimize / Restore
                    Rectangle {
                        id: minimizeWinBtn
                        implicitWidth: minimizeWinLabel.implicitWidth + 10
                        implicitHeight: 20
                        radius: Theme.radiusSmall
                        opacity: winItem.canMinimize ? 1.0 : 0.45
                        color: (winItem.canMinimize && minimizeWinMouse.containsMouse)
                            ? Theme.alpha(Theme.primary, 0.22)
                            : (winItem.isMinimized ? Theme.alpha(Theme.accent, 0.2) : Theme.alpha(Theme.surface, 0.6))
                        border.width: 1
                        border.color: (winItem.canMinimize && minimizeWinMouse.containsMouse)
                            ? Theme.primary
                            : (winItem.isMinimized ? Theme.accent : Theme.border)
                        Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

                        Text {
                            id: minimizeWinLabel
                            anchors.centerIn: parent
                            text: winItem.isMinimized ? "Restore" : "Minimize"
                            color: winItem.canMinimize ? Theme.foreground : Theme.foregroundMuted
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSizeSmall - 2
                        }

                        MouseArea {
                            id: minimizeWinMouse
                            anchors.fill: parent
                            enabled: winItem.canMinimize
                            hoverEnabled: true
                            cursorShape: winItem.canMinimize ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: {
                                if (WindowService.toggleMinimizeWindow(winItem.windowId)) {
                                    root.actionTriggered();
                                }
                            }
                        }
                    }

                    // Maximize / Unmaximize
                    Rectangle {
                        id: maximizeWinBtn
                        implicitWidth: maximizeWinLabel.implicitWidth + 10
                        implicitHeight: 20
                        radius: Theme.radiusSmall
                        opacity: winItem.canMaximize ? 1.0 : 0.45
                        color: (winItem.canMaximize && maximizeWinMouse.containsMouse)
                            ? Theme.alpha(Theme.primary, 0.22)
                            : (winItem.isMaximized ? Theme.alpha(Theme.accent, 0.2) : Theme.alpha(Theme.surface, 0.6))
                        border.width: 1
                        border.color: (winItem.canMaximize && maximizeWinMouse.containsMouse)
                            ? Theme.primary
                            : (winItem.isMaximized ? Theme.accent : Theme.border)
                        Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

                        Text {
                            id: maximizeWinLabel
                            anchors.centerIn: parent
                            text: winItem.isMaximized ? "Unmaximize" : "Maximize"
                            color: winItem.canMaximize ? Theme.foreground : Theme.foregroundMuted
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSizeSmall - 2
                        }

                        MouseArea {
                            id: maximizeWinMouse
                            anchors.fill: parent
                            enabled: winItem.canMaximize
                            hoverEnabled: true
                            cursorShape: winItem.canMaximize ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: {
                                if (WindowService.toggleMaximizeWindow(winItem.windowId)) {
                                    root.actionTriggered();
                                }
                            }
                        }
                    }

                    // Fullscreen toggle
                    Rectangle {
                        id: fullscreenWinBtn
                        implicitWidth: fullscreenWinLabel.implicitWidth + 10
                        implicitHeight: 20
                        radius: Theme.radiusSmall
                        opacity: winItem.canFullScreen ? 1.0 : 0.45
                        color: (winItem.canFullScreen && fullscreenWinMouse.containsMouse)
                            ? Theme.alpha(Theme.primary, 0.22)
                            : (winItem.isFullScreen ? Theme.alpha(Theme.accent, 0.2) : Theme.alpha(Theme.surface, 0.6))
                        border.width: 1
                        border.color: (winItem.canFullScreen && fullscreenWinMouse.containsMouse)
                            ? Theme.primary
                            : (winItem.isFullScreen ? Theme.accent : Theme.border)
                        Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

                        Text {
                            id: fullscreenWinLabel
                            anchors.centerIn: parent
                            text: winItem.isFullScreen ? "Exit Fullscreen" : "Fullscreen"
                            color: winItem.canFullScreen ? Theme.foreground : Theme.foregroundMuted
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSizeSmall - 2
                        }

                        MouseArea {
                            id: fullscreenWinMouse
                            anchors.fill: parent
                            enabled: winItem.canFullScreen
                            hoverEnabled: true
                            cursorShape: winItem.canFullScreen ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: {
                                if (WindowService.toggleFullScreenWindow(winItem.windowId)) {
                                    root.actionTriggered();
                                }
                            }
                        }
                    }

                    // Keep Above / Always on Top toggle
                    Rectangle {
                        id: keepAboveWinBtn
                        implicitWidth: keepAboveWinLabel.implicitWidth + 10
                        implicitHeight: 20
                        radius: Theme.radiusSmall
                        opacity: winItem.canKeepAbove ? 1.0 : 0.45
                        color: (winItem.canKeepAbove && keepAboveWinMouse.containsMouse)
                            ? Theme.alpha(Theme.primary, 0.22)
                            : (winItem.isKeepAbove ? Theme.alpha(Theme.accent, 0.2) : Theme.alpha(Theme.surface, 0.6))
                        border.width: 1
                        border.color: (winItem.canKeepAbove && keepAboveWinMouse.containsMouse)
                            ? Theme.primary
                            : (winItem.isKeepAbove ? Theme.accent : Theme.border)
                        Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

                        Text {
                            id: keepAboveWinLabel
                            anchors.centerIn: parent
                            text: "Keep Above"
                            color: winItem.canKeepAbove ? Theme.foreground : Theme.foregroundMuted
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSizeSmall - 2
                        }

                        MouseArea {
                            id: keepAboveWinMouse
                            anchors.fill: parent
                            enabled: winItem.canKeepAbove
                            hoverEnabled: true
                            cursorShape: winItem.canKeepAbove ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: {
                                if (WindowService.toggleKeepAboveWindow(winItem.windowId)) {
                                    root.actionTriggered();
                                }
                            }
                        }
                    }
                }

                // Move to Virtual Desktop Row (only shown when >1 virtual desktop exists)
                RowLayout {
                    visible: winItem.targetDesktops.length > 0 || (WindowService.availableDesktops.length > 1 && !winItem.isOnAllDesktops)
                    Layout.fillWidth: true
                    Layout.leftMargin: 8
                    Layout.rightMargin: 4
                    spacing: 4

                    Repeater {
                        model: winItem.targetDesktops

                        Rectangle {
                            id: moveDeskBtn
                            required property var modelData
                            implicitWidth: moveDeskLabel.implicitWidth + 10
                            implicitHeight: 20
                            radius: Theme.radiusSmall
                            color: moveDeskMouse.containsMouse ? Theme.alpha(Theme.primary, 0.22) : Theme.alpha(Theme.surface, 0.6)
                            border.width: 1
                            border.color: moveDeskMouse.containsMouse ? Theme.primary : Theme.border
                            Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

                            Text {
                                id: moveDeskLabel
                                anchors.centerIn: parent
                                text: "→ " + (moveDeskBtn.modelData ? moveDeskBtn.modelData.name : "")
                                color: Theme.foreground
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.fontSizeSmall - 2
                            }

                            MouseArea {
                                id: moveDeskMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (moveDeskBtn.modelData && WindowService.moveWindowToDesktop(winItem.windowId, moveDeskBtn.modelData.id)) {
                                        root.actionTriggered();
                                    }
                                }
                            }
                        }
                    }

                    Rectangle {
                        id: allDesksBtn
                        visible: WindowService.availableDesktops.length > 1 && !winItem.isOnAllDesktops
                        implicitWidth: allDesksLabel.implicitWidth + 10
                        implicitHeight: 20
                        radius: Theme.radiusSmall
                        color: allDesksMouse.containsMouse ? Theme.alpha(Theme.primary, 0.22) : Theme.alpha(Theme.surface, 0.6)
                        border.width: 1
                        border.color: allDesksMouse.containsMouse ? Theme.primary : Theme.border
                        Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

                        Text {
                            id: allDesksLabel
                            anchors.centerIn: parent
                            text: "All Desktops"
                            color: Theme.foreground
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSizeSmall - 2
                        }

                        MouseArea {
                            id: allDesksMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (WindowService.moveWindowToDesktop(winItem.windowId, "all")) {
                                    root.actionTriggered();
                                }
                            }
                        }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: Theme.border
            opacity: 0.5
            visible: root.appWindows.length > 0
        }

        // Action: Launch / New Window (hidden only when running and an explicit desktop 'New Window' quick action replaces it)
        Rectangle {
            id: launchRow
            visible: !root.isRunning || !root.hasCustomNewWindowAction
            Layout.fillWidth: true
            implicitHeight: 28
            radius: Theme.radiusSmall
            color: launchMouse.containsMouse ? Theme.hover : "transparent"
            Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 8

                SvgIcon {
                    icon: "list-add"
                    size: 14
                    color: Theme.foreground
                }

                Text {
                    text: root.isRunning ? "New Window" : "Open"
                    color: Theme.foreground
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                }
            }

            MouseArea {
                id: launchMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    ApplicationService.launchAppId(root.appId);
                    root.actionTriggered();
                }
            }
        }

        // XDG Desktop Entry Quick Actions (in declared Actions= order)
        Repeater {
            id: quickActionsRepeater
            model: root.appActions

            Rectangle {
                id: quickActionRow
                required property var modelData
                Layout.fillWidth: true
                implicitHeight: 28
                radius: Theme.radiusSmall
                color: quickActionMouse.containsMouse ? Theme.hover : "transparent"
                Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    spacing: 8

                    SvgIcon {
                        icon: (quickActionRow.modelData && quickActionRow.modelData.icon) ? quickActionRow.modelData.icon : "list-add"
                        size: 14
                        color: Theme.foreground
                    }

                    Text {
                        text: quickActionRow.modelData ? quickActionRow.modelData.name : ""
                        color: Theme.foreground
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                }

                MouseArea {
                    id: quickActionMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (quickActionRow.modelData) {
                            root.triggerQuickAction(quickActionRow.modelData.id);
                        }
                    }
                }
            }
        }

        // Action: Move Left / Up (for pinned apps)
        Rectangle {
            id: moveLeftRow
            visible: root.isPinned
            Layout.fillWidth: true
            implicitHeight: 28
            radius: Theme.radiusSmall
            color: (root.canMoveLeft && moveLeftMouse.containsMouse) ? Theme.hover : "transparent"
            Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 8

                SvgIcon {
                    icon: root.isVerticalDock ? "go-up" : "go-previous"
                    size: 14
                    color: root.canMoveLeft ? Theme.foreground : Theme.foregroundMuted
                }

                Text {
                    text: root.isVerticalDock ? "Move Up" : "Move Left"
                    color: root.canMoveLeft ? Theme.foreground : Theme.foregroundMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                }
            }

            MouseArea {
                id: moveLeftMouse
                anchors.fill: parent
                enabled: root.canMoveLeft
                hoverEnabled: true
                cursorShape: root.canMoveLeft ? Qt.PointingHandCursor : Qt.ArrowCursor
                onClicked: {
                    root.moveLeft();
                }
            }
        }

        // Action: Move Right / Down (for pinned apps)
        Rectangle {
            id: moveRightRow
            visible: root.isPinned
            Layout.fillWidth: true
            implicitHeight: 28
            radius: Theme.radiusSmall
            color: (root.canMoveRight && moveRightMouse.containsMouse) ? Theme.hover : "transparent"
            Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 8

                SvgIcon {
                    icon: root.isVerticalDock ? "go-down" : "go-next"
                    size: 14
                    color: root.canMoveRight ? Theme.foreground : Theme.foregroundMuted
                }

                Text {
                    text: root.isVerticalDock ? "Move Down" : "Move Right"
                    color: root.canMoveRight ? Theme.foreground : Theme.foregroundMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                }
            }

            MouseArea {
                id: moveRightMouse
                anchors.fill: parent
                enabled: root.canMoveRight
                hoverEnabled: true
                cursorShape: root.canMoveRight ? Qt.PointingHandCursor : Qt.ArrowCursor
                onClicked: {
                    root.moveRight();
                }
            }
        }

        // Action: Pin / Unpin
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 28
            radius: Theme.radiusSmall
            color: pinMouse.containsMouse ? Theme.hover : "transparent"
            Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 8

                SvgIcon {
                    icon: root.isPinned ? "bookmark-remove" : "bookmark-new"
                    size: 14
                    color: Theme.foreground
                }

                Text {
                    text: root.isPinned ? "Unpin from Dock" : "Pin to Dock"
                    color: Theme.foreground
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                }
            }

            MouseArea {
                id: pinMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    ApplicationService.togglePin(root.appId);
                    root.actionTriggered();
                }
            }
        }
    }
}
