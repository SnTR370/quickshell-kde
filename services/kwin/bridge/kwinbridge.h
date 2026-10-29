#pragma once

#include <QDBusContext>
#include <QDBusServiceWatcher>
#include <QObject>
#include <QtQml/qqml.h>

class QTimer;

/*
 * KWinEventBridge — in-process QtDBus QML element for Quickshell.
 *
 * Receives authoritative window-state records from a resident KWin script
 * (generated from services/kwin/scripts/kwin-event-bridge.js) that calls the
 * exported `record` D-Bus method on this object's unique session-bus name.
 *
 * Security/lifecycle contract (see docs/development/P0_9_EVENT_BRIDGE_DESIGN.md):
 *  - only the current unique owner of org.kde.KWin may deliver records
 *    (checked through QDBusContext against a QDBusServiceWatcher-tracked owner)
 *  - payloads are bounded; envelope (version/generation/sequence) is validated;
 *    a generation or sequence mismatch emits `desynchronized` and reloads the
 *    owned KWin script for a fresh snapshot
 *  - accepted records are coalesced with a 0 ms single-shot flush timer and
 *    emitted as `batchReceived` (JSON array of payload strings)
 *  - the script is loaded/run/unloaded only through the public
 *    org.kde.KWin /Scripting D-Bus interface; the per-instance pluginName is a
 *    stable hash of the script template path so orphans from a crashed shell
 *    are positively identified and removed on the next start
 *  - KWin owner loss invalidates the stream (desynchronized) and owner return
 *    reloads the script; nothing is exported except the `record` method
 */
class KWinEventBridge : public QObject, protected QDBusContext
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.quickshell.kwinbridge")
    QML_NAMED_ELEMENT(KWinEventBridge)
    Q_PROPERTY(bool active READ active NOTIFY activeChanged)
    Q_PROPERTY(bool connected READ connected NOTIFY connectedChanged)
    Q_PROPERTY(QString busName READ busName NOTIFY busNameChanged)

public:
    explicit KWinEventBridge(QObject *parent = nullptr);
    ~KWinEventBridge() override;

    bool active() const { return m_active; }
    bool connected() const { return m_connected; }
    QString busName() const { return m_busName; }

    // Reads the template, registers the bus endpoint and loads the script.
    // Returns false only for local, non-recoverable failures (unreadable
    // template, unwritable runtime dir, bus registration failure).
    Q_INVOKABLE bool start(const QString &scriptTemplatePath);
    // Unloads the owned script and unregisters the endpoint.
    Q_INVOKABLE void stop();

signals:
    void activeChanged();
    void connectedChanged();
    void busNameChanged();
    // JSON array of validated KWin script payload strings, in order.
    void batchReceived(const QString &jsonArray);
    // The event stream is no longer trustworthy (KWin restart, generation or
    // sequence mismatch, overflow). Consumers must discard cached window
    // state until the next snapshot arrives. The bridge reloads its script.
    void desynchronized(const QString &reason);

public Q_SLOTS:
    // Exported D-Bus method (scriptable slot): the only bus-reachable method.
    Q_SCRIPTABLE QString record(const QString &payload);

private Q_SLOTS:
    void handleKWinOwnerChanged(const QString &service, const QString &oldOwner, const QString &newOwner);
    void flushPending();
    void reloadNow();

private:
    bool ensureScriptFile();
    bool loadScriptIntoKWin();
    void scheduleReload();
    void resetStreamState();
    void setConnected(bool connected);

    QString m_busName;
    QString m_pluginName;
    QString m_scriptPath;
    QString m_templatePath;
    QString m_kwinOwner;
    QTimer *m_flushTimer = nullptr;
    QTimer *m_reloadTimer = nullptr;
    QDBusServiceWatcher *m_ownerWatcher = nullptr;
    QStringList m_pending;
    qint64 m_lastSeq = 0;
    int m_generation = 0;
    int m_reloadBackoffMs = 200;
    bool m_active = false;
    bool m_connected = false;
    bool m_scriptLoaded = false;
    bool m_reloadQueued = false;
};
