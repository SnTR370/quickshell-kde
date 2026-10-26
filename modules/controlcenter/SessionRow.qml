import QtQuick
import QtQuick.Layouts
import Quickshell
import "../../services"
import "../../components"

RowLayout {
    id: root

    property bool dryRun: false
    property var parentWindow: null
    signal actionTriggered()
    signal sessionActionRequested(string action)

    function dispatchSessionAction(action, cmd) {
        root.sessionActionRequested(action);
        root.actionTriggered();
        if (root.dryRun || Quickshell.env("QUICKSHELL_TEST_MODE") === "1") {
            return;
        }
        if (action === "lock") {
            KWinService.lockSession();
        } else if (action === "settings") {
            KWinService.toggleKdeSettings("");
        } else if (cmd && cmd.length > 0) {
            Quickshell.execDetached(cmd);
        }
    }

    spacing: 8
    Layout.fillWidth: true

    IconButton {
        parentWindow: root.parentWindow
        size: 34
        icon: "preferences-system"
        iconSize: 18
        iconColor: Theme.foreground
        tooltip: "KDE System Settings"
        onClicked: root.dispatchSessionAction("settings", [])
    }

    Item {
        Layout.fillWidth: true
    }

    IconButton {
        parentWindow: root.parentWindow
        size: 34
        icon: "system-lock-screen"
        iconSize: 18
        iconColor: Theme.foreground
        tooltip: "Lock Screen"
        onClicked: root.dispatchSessionAction("lock", [])
    }

    IconButton {
        parentWindow: root.parentWindow
        size: 34
        icon: "system-log-out"
        iconSize: 18
        iconColor: Theme.foreground
        tooltip: "Log Out"
        onClicked: root.dispatchSessionAction("logout", ["qdbus6", "org.kde.Shutdown", "/Shutdown", "org.kde.Shutdown.logout"])
    }

    IconButton {
        parentWindow: root.parentWindow
        size: 34
        icon: "system-reboot"
        iconSize: 18
        iconColor: Theme.warning
        tooltip: "Restart"
        onClicked: root.dispatchSessionAction("reboot", ["qdbus6", "org.kde.Shutdown", "/Shutdown", "org.kde.Shutdown.logoutAndReboot"])
    }

    IconButton {
        parentWindow: root.parentWindow
        size: 34
        icon: "system-shutdown"
        iconSize: 18
        iconColor: Theme.error
        tooltip: "Shut Down"
        onClicked: root.dispatchSessionAction("shutdown", ["qdbus6", "org.kde.Shutdown", "/Shutdown", "org.kde.Shutdown.logoutAndShutdown"])
    }
}
