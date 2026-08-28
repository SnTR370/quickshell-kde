pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Services.Notifications
import "../core/Log.js" as Log

Singleton {
    id: root

    property var notificationsHistory: []
    property var activeToasts: []
    property int maxHistory: 50

    signal toastAdded(var notification)
    signal toastRemoved(var id)

    NotificationServer {
        id: server
        keepOnReload: true
        bodySupported: true
        bodyMarkupSupported: true
        bodyHyperlinksSupported: true
        bodyImagesSupported: true
        actionsSupported: true
        actionIconsSupported: true
        imageSupported: true

        onNotification: notification => {
            root.handleNotification(notification);
        }
    }

    function handleNotification(n) {
        if (!n) return;
        Log.info("NotificationService", "New notification from: " + n.appName + " - " + n.summary);

        const item = {
            id: n.id,
            raw: n,
            appName: n.appName || "Application",
            appIcon: n.appIcon || "dialog-information",
            summary: n.summary || "",
            body: n.body || "",
            urgency: n.urgency,
            timestamp: new Date(),
            actions: n.actions || []
        };

        // Add to history
        const hist = [item].concat(root.notificationsHistory);
        if (hist.length > root.maxHistory) hist.pop();
        root.notificationsHistory = hist;

        // Add to active toasts
        const toasts = [item].concat(root.activeToasts);
        root.activeToasts = toasts;
        root.toastAdded(item);
    }

    function dismissToast(id) {
        const next = [];
        for (let i = 0; i < root.activeToasts.length; i++) {
            if (root.activeToasts[i].id !== id) {
                next.push(root.activeToasts[i]);
            }
        }
        root.activeToasts = next;
        root.toastRemoved(id);
    }

    function clearAllToasts() {
        root.activeToasts = [];
    }

    function clearHistory() {
        root.notificationsHistory = [];
    }
}
