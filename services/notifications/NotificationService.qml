pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Services.Notifications
import "../config"
import "../applications"
import "../core/Log.js" as Log
import "NotificationBadges.js" as Badges

Singleton {
    id: root

    property var notificationsHistory: []
    property var activeToasts: []
    property int maxHistory: 50

    // DOCK-009: active-notification set. A notification is ACTIVE from the
    // moment the shell's own NotificationServer receives it until its
    // native closed() signal fires. The shell closes notifications only
    // through real close paths:
    //   - the user dismisses the toast (close button or action) -> dismiss()
    //   - a client-supplied positive expireTimeout elapses  -> expire()
    //   - the sending client withdraws it (CloseNotification) -> closed(3)
    //   - the user activates the app's dock icon (attention given) -> dismiss()
    // Transient notifications (freedesktop: do not persist after display)
    // are expired by the shell once their toast hides, and -1/0 expire
    // timeouts persist until attended (documented server default).
    // Counts are exact server state, never estimates. When
    // ConfigService.notificationsEnabled is false the shell runs no
    // notification server, so this set stays empty and the dock shows no
    // badges (honest degradation — Plasma's own daemon owns the data).
    property var activeNotifications: []

    signal toastAdded(var notification)
    signal toastRemoved(var id)

    // Merged per-app badge state (canonical app key -> {count, critical,
    // progress}). Recomputed whenever the active set or the application
    // list changes (both are referenced directly so a late app scan
    // re-matches already-active notifications); matching goes through
    // ApplicationService.getAppById so unmatched notifications badge
    // nothing.
    readonly property var notificationBadges: {
        const _apps = ApplicationService.applications;
        const _active = root.activeNotifications;
        return Badges.buildBadges(_active,
            function(candidate) { return ApplicationService.getAppById(candidate); });
    }

    // Disabling the shell's notification server drops its tracked
    // notifications (the objects are destroyed with the server), so the
    // active set is cleared to match the new server state exactly.
    Connections {
        target: ConfigService
        function onNotificationsEnabledChanged() {
            if (!ConfigService.notificationsEnabled) {
                root.activeNotifications = [];
            }
        }
    }

    Loader {
        id: serverLoader
        active: ConfigService.notificationsEnabled
        sourceComponent: Component {
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
        }
    }

    function handleNotification(n) {
        if (!n) return;
        Log.info("NotificationService", "New notification from: " + n.appName + " - " + n.summary);

        // DOCK-009: keep the notification alive in the server and follow
        // its native lifecycle (verified against Quickshell 0.3.2): tracked
        // objects emit closed(reason) for every close path, and a client
        // replacement (replaces_id) updates the SAME object in place via
        // hintsChanged/urgencyChanged/expireTimeoutChanged without a new
        // notification signal.
        try {
            n.tracked = true;
            n.closed.connect(function(reason) { root.handleClosed(n.id, reason); });
            n.hintsChanged.connect(function() { root.refreshActive(n); });
            n.urgencyChanged.connect(function() { root.refreshActive(n); });
            n.expireTimeoutChanged.connect(function() { root.refreshActive(n); });
        } catch (e) {
            Log.warn("NotificationService", "Notification lifecycle tracking failed: " + e);
        }

        const item = Badges.makeBadgeItem(n, Date.now());

        // Add to history
        const hist = [item].concat(root.notificationsHistory);
        if (hist.length > root.maxHistory) hist.pop();
        root.notificationsHistory = hist;

        // Track in the active set (id upsert: replacements never add counts)
        root.activeNotifications = Badges.upsertActive(root.activeNotifications, item);

        // Add to active toasts
        const toasts = [item].concat(root.activeToasts);
        root.activeToasts = toasts;
        root.toastAdded(item);
    }

    // A tracked notification closed (any reason). The server state is
    // authoritative: drop it from the active set and any visible toast.
    function handleClosed(id, _reason) {
        const nid = Number(id);
        root.activeNotifications = Badges.removeActive(root.activeNotifications, nid);
        const toasts = [];
        for (let i = 0; i < root.activeToasts.length; i++) {
            if (root.activeToasts[i].id !== nid) {
                toasts.push(root.activeToasts[i]);
            }
        }
        root.activeToasts = toasts;
        root.toastRemoved(id);
    }

    // A tracked notification was replaced in place by its client: rebuild
    // its snapshot so progress/urgency/summary state stays live.
    function refreshActive(n) {
        if (!n) return;
        const nid = Number(n.id);
        const next = root.activeNotifications.slice();
        for (let i = 0; i < next.length; i++) {
            if (next[i] && next[i].id === nid) {
                next[i] = Badges.makeBadgeItem(n, Date.now());
                root.activeNotifications = next;
                return;
            }
        }
    }

    // Route a close through the native Notification object. "mode" is
    // "dismiss" (user/attention) or "expire" (timeout). If the closed
    // signal is unavailable the entry is removed directly so state never
    // leaks; removal is idempotent.
    function closeNotification(id, mode) {
        const nid = Number(id);
        for (let i = 0; i < root.activeNotifications.length; i++) {
            const it = root.activeNotifications[i];
            if (it && it.id === nid && it.raw) {
                try {
                    if (mode === "expire") it.raw.expire();
                    else it.raw.dismiss();
                } catch (e) {
                    Log.warn("NotificationService", "Failed to close notification: " + e);
                }
            }
        }
        root.activeNotifications = Badges.removeActive(root.activeNotifications, nid);
    }

    // Hide a toast. closeNotification routes user dismissals to the server
    // (the notification is dealt with); the toast auto-timeout passes false
    // so the notification stays active and its dock badge persists until
    // attended. Transient notifications are the exception: the freedesktop
    // transient hint means "do not persist after display", so hiding their
    // toast expires them server-side.
    function dismissToast(id, closeNotification = true) {
        const nid = Number(id);
        const next = [];
        for (let i = 0; i < root.activeToasts.length; i++) {
            if (root.activeToasts[i].id !== nid) {
                next.push(root.activeToasts[i]);
            }
        }
        root.activeToasts = next;
        root.toastRemoved(id);
        if (closeNotification) {
            root.closeNotification(nid, "dismiss");
        } else {
            for (let i = 0; i < root.activeNotifications.length; i++) {
                if (root.activeNotifications[i]
                    && root.activeNotifications[i].id === nid
                    && root.activeNotifications[i].transient) {
                    root.closeNotification(nid, "expire");
                    break;
                }
            }
        }
    }

    // DOCK-009: attention given — activating an app's dock icon dismisses
    // that app's active notifications. Returns the dismissed count.
    function dismissAppNotifications(appKey) {
        if (!appKey) return 0;
        const ids = Badges.activeIdsForApp(root.activeNotifications, appKey,
            function(candidate) { return ApplicationService.getAppById(candidate); });
        for (let i = 0; i < ids.length; i++) {
            root.closeNotification(ids[i], "dismiss");
        }
        return ids.length;
    }

    // Honor client-supplied positive expireTimeouts (freedesktop
    // expire_timeout) through the native expire() path. One low-rate
    // sweeper; -1 (never) and 0 (server default: persist until attended)
    // never trigger it.
    Timer {
        id: expireSweeper
        interval: 1000
        repeat: true
        running: root.activeNotifications.length > 0
        onTriggered: {
            const ids = Badges.expiredIds(root.activeNotifications, Date.now());
            for (let i = 0; i < ids.length; i++) {
                root.closeNotification(ids[i], "expire");
            }
        }
    }

    // DOCK-009: badge lookups for the dock row.
    function badgeForApp(appKey) {
        return Badges.badgeForApp(root.notificationBadges, appKey);
    }

    function badgeForStack(memberAppKeys) {
        return Badges.aggregateStackBadge(root.notificationBadges, memberAppKeys);
    }

    function clearAllToasts() {
        root.activeToasts = [];
    }

    function clearHistory() {
        root.notificationsHistory = [];
    }
}
