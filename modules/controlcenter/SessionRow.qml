import QtQuick
import QtQuick.Layouts
import Quickshell
import "../../services"
import "../../components"

RowLayout {
    id: root

    signal actionTriggered()

    spacing: 8
    Layout.fillWidth: true

    IconButton {
        size: 34
        icon: "preferences-system"
        iconSize: 18
        iconColor: Theme.foreground
        tooltip: "KDE System Settings"
        onClicked: {
            root.actionTriggered();
            KWinService.toggleKdeSettings("");
        }
    }

    Item {
        Layout.fillWidth: true
    }

    IconButton {
        size: 34
        icon: "system-lock-screen"
        iconSize: 18
        iconColor: Theme.foreground
        tooltip: "Lock Screen"
        onClicked: {
            root.actionTriggered();
            KWinService.lockSession();
        }
    }

    IconButton {
        size: 34
        icon: "system-log-out"
        iconSize: 18
        iconColor: Theme.foreground
        tooltip: "Log Out"
        onClicked: {
            root.actionTriggered();
            Quickshell.execDetached(["qdbus6", "org.kde.Shutdown", "/Shutdown", "org.kde.Shutdown.logout"]);
        }
    }

    IconButton {
        size: 34
        icon: "system-reboot"
        iconSize: 18
        iconColor: Theme.warning
        tooltip: "Restart"
        onClicked: {
            root.actionTriggered();
            Quickshell.execDetached(["qdbus6", "org.kde.Shutdown", "/Shutdown", "org.kde.Shutdown.logoutAndReboot"]);
        }
    }

    IconButton {
        size: 34
        icon: "system-shutdown"
        iconSize: 18
        iconColor: Theme.error
        tooltip: "Shut Down"
        onClicked: {
            root.actionTriggered();
            Quickshell.execDetached(["qdbus6", "org.kde.Shutdown", "/Shutdown", "org.kde.Shutdown.logoutAndShutdown"]);
        }
    }
}
