#include "kwinbridge.h"

#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusInterface>
#include <QDBusReply>
#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRandomGenerator>
#include <QTimer>

#include <sys/stat.h>

namespace {
constexpr const char *kObjectPath = "/org/quickshell/kwinbridge";
constexpr const char *kKWinService = "org.kde.KWin";
constexpr const char *kScriptingPath = "/Scripting";
constexpr const char *kScriptingIface = "org.kde.kwin.Scripting";
constexpr const char *kScriptIface = "org.kde.kwin.Script";
constexpr int kDbusTimeoutMs = 2000;
constexpr int kMaxPayloadBytes = 2 * 1024 * 1024;
constexpr int kMaxPendingRecords = 4096;

QString hashHex(const QString &source)
{
    return QString::fromLatin1(
        QCryptographicHash::hash(source.toUtf8(), QCryptographicHash::Sha256).toHex().left(8));
}
} // namespace

KWinEventBridge::KWinEventBridge(QObject *parent)
    : QObject(parent)
{
    m_flushTimer = new QTimer(this);
    m_flushTimer->setSingleShot(true);
    m_flushTimer->setInterval(0);
    connect(m_flushTimer, &QTimer::timeout, this, &KWinEventBridge::flushPending);

    m_reloadTimer = new QTimer(this);
    m_reloadTimer->setSingleShot(true);
    connect(m_reloadTimer, &QTimer::timeout, this, &KWinEventBridge::reloadNow);

    m_ownerWatcher = new QDBusServiceWatcher(
        kKWinService, QDBusConnection::sessionBus(),
        QDBusServiceWatcher::WatchForOwnerChange, this);
    connect(m_ownerWatcher, &QDBusServiceWatcher::serviceOwnerChanged,
            this, &KWinEventBridge::handleKWinOwnerChanged);
}

KWinEventBridge::~KWinEventBridge()
{
    stop();
}

bool KWinEventBridge::start(const QString &scriptTemplatePath)
{
    if (m_active)
        return true;

    m_templatePath = QFileInfo(scriptTemplatePath).canonicalFilePath();
    if (m_templatePath.isEmpty() || !QFileInfo(m_templatePath).isReadable()) {
        qWarning() << "KWinEventBridge: script template not readable:" << scriptTemplatePath;
        return false;
    }

    // Stable per-checkout identity: orphans left in KWin by a crashed shell are
    // positively identified and unloaded on the next start.
    m_pluginName = QStringLiteral("quickshell-kwineventbridge-") + hashHex(m_templatePath);

    // Private runtime dir (0700) for the generated script instance.
    const QString runtimeBase =
        QDir(qEnvironmentVariable("XDG_RUNTIME_DIR", QDir::tempPath()))
            .filePath(QStringLiteral("quickshell-kwin-bridge"));
    const QString instanceDir = QDir(runtimeBase).filePath(m_pluginName);
    if (!QDir().mkpath(instanceDir)) {
        qWarning() << "KWinEventBridge: cannot create runtime dir:" << instanceDir;
        return false;
    }
    ::chmod(QFile::encodeName(instanceDir).constData(), 0700);
    m_scriptPath = QDir(instanceDir).filePath(QStringLiteral("bridge.js"));

    // Bus endpoint: deterministic name per checkout (so a stale script from a
    // crashed shell cannot deliver to a different instance), collision-suffixed
    // if a second Quickshell from the same checkout is running.
    QDBusConnection bus = QDBusConnection::sessionBus();
    const QString baseName = QStringLiteral("org.quickshell.kwineventbridge.") + hashHex(m_templatePath);
    m_busName = baseName;
    for (int attempt = 2; !bus.registerService(m_busName); ++attempt) {
        if (attempt > 8) {
            qWarning() << "KWinEventBridge: cannot register bus service" << m_busName;
            return false;
        }
        m_busName = baseName + QString::number(attempt);
    }
    if (!bus.registerObject(QLatin1String(kObjectPath), this,
                            QDBusConnection::ExportScriptableSlots)) {
        qWarning() << "KWinEventBridge: cannot register object" << kObjectPath;
        bus.unregisterService(m_busName);
        return false;
    }

    m_active = true;
    emit busNameChanged();
    emit activeChanged();

    // Current KWin owner; the watcher covers later changes.
    const QDBusReply<QString> owner =
        bus.interface()->serviceOwner(QLatin1String(kKWinService));
    m_kwinOwner = (owner.isValid() && !owner.value().isEmpty()) ? owner.value() : QString();
    setConnected(!m_kwinOwner.isEmpty());

    reloadNow(); // assigns a fresh generation, writes the script, loads it
    if (!m_connected)
        return true; // deferred: the owner watcher reloads when KWin appears
    if (!m_scriptLoaded) {
        scheduleReload();
    }
    return true;
}

void KWinEventBridge::stop()
{
    if (!m_active)
        return;

    m_reloadTimer->stop();
    m_reloadQueued = false;
    resetStreamState();

    if (m_scriptLoaded && m_connected) {
        QDBusInterface scripting(kKWinService, kScriptingPath, kScriptingIface,
                                 QDBusConnection::sessionBus());
        scripting.setTimeout(kDbusTimeoutMs);
        scripting.call(QStringLiteral("unloadScript"), m_pluginName);
    }
    m_scriptLoaded = false;

    QDBusConnection bus = QDBusConnection::sessionBus();
    bus.unregisterObject(QLatin1String(kObjectPath));
    bus.unregisterService(m_busName);
    QFile::remove(m_scriptPath);

    m_active = false;
    emit activeChanged();
}

QString KWinEventBridge::record(const QString &payload)
{
    if (!m_active)
        return QStringLiteral("inactive");
    if (m_reloadQueued)
        return QStringLiteral("reload");

    // Only the current KWin owner may deliver records.
    const QString sender = message().service();
    if (sender.isEmpty() || sender != m_kwinOwner)
        return QStringLiteral("error:sender");
    if (payload.size() > kMaxPayloadBytes)
        return QStringLiteral("error:size");

    QJsonParseError parseError;
    const QJsonDocument doc = QJsonDocument::fromJson(payload.toUtf8(), &parseError);
    if (parseError.error != QJsonParseError::NoError || !doc.isObject())
        return QStringLiteral("error:json");
    const QJsonObject obj = doc.object();
    if (obj.value(QStringLiteral("v")).toInt(-1) != 1)
        return QStringLiteral("error:version");
    const QString type = obj.value(QStringLiteral("type")).toString();
    if (type != QLatin1String("snapshot") && type != QLatin1String("update")
        && type != QLatin1String("remove") && type != QLatin1String("desktop")) {
        return QStringLiteral("error:type");
    }

    const int generation = obj.value(QStringLiteral("gen")).toInt(-1);
    if (generation != m_generation) {
        emit desynchronized(QStringLiteral("generation"));
        scheduleReload();
        return QStringLiteral("reload");
    }

    const qint64 seq = qint64(obj.value(QStringLiteral("seq")).toDouble(0));
    if (seq != m_lastSeq + 1) {
        if (seq > 0 && seq <= m_lastSeq)
            return QStringLiteral("ok"); // duplicate delivery, already applied
        emit desynchronized(QStringLiteral("sequence"));
        scheduleReload();
        return QStringLiteral("reload");
    }

    m_lastSeq = seq;
    m_reloadBackoffMs = 200; // healthy traffic resets reload backoff
    m_pending.append(payload);
    if (m_pending.size() > kMaxPendingRecords) {
        emit desynchronized(QStringLiteral("overflow"));
        scheduleReload();
        return QStringLiteral("reload");
    }
    if (!m_flushTimer->isActive())
        m_flushTimer->start();
    return QStringLiteral("ok");
}

void KWinEventBridge::handleKWinOwnerChanged(const QString &service, const QString &oldOwner,
                                             const QString &newOwner)
{
    Q_UNUSED(service);
    Q_UNUSED(oldOwner);

    if (newOwner.isEmpty()) {
        // KWin went away: the stream and every derived window state are invalid.
        m_kwinOwner.clear();
        m_scriptLoaded = false;
        setConnected(false);
        if (m_active) {
            resetStreamState();
            emit desynchronized(QStringLiteral("kwin-owner-lost"));
        }
        return;
    }

    m_kwinOwner = newOwner;
    setConnected(true);
    if (m_active)
        scheduleReload(); // load a fresh script into the new KWin instance
}

void KWinEventBridge::flushPending()
{
    if (m_pending.isEmpty())
        return;
    const QStringList batch = m_pending;
    m_pending.clear();
    emit batchReceived(QStringLiteral("[") + batch.join(QLatin1Char(',')) + QStringLiteral("]"));
}

void KWinEventBridge::reloadNow()
{
    m_reloadQueued = false;
    if (!m_active)
        return;

    resetStreamState();
    m_generation = int(QRandomGenerator::global()->bounded(1u, 2000000000u));
    if (!ensureScriptFile()) {
        scheduleReload();
        return;
    }
    if (!m_connected) {
        m_scriptLoaded = false;
        return; // deferred: the owner watcher reloads when KWin appears
    }
    if (!loadScriptIntoKWin()) {
        scheduleReload();
        return;
    }
    m_reloadBackoffMs = 200;
}

bool KWinEventBridge::ensureScriptFile()
{
    QFile templateFile(m_templatePath);
    if (!templateFile.open(QIODevice::ReadOnly))
        return false;
    QString content = QString::fromUtf8(templateFile.readAll());
    templateFile.close();
    content.replace(QStringLiteral("__BUS_NAME__"), m_busName)
        .replace(QStringLiteral("__GENERATION__"), QString::number(m_generation));

    QFile out(m_scriptPath);
    if (!out.open(QIODevice::WriteOnly | QIODevice::Truncate))
        return false;
    out.write(content.toUtf8());
    out.close();
    out.setPermissions(QFileDevice::ReadOwner | QFileDevice::WriteOwner);
    return true;
}

bool KWinEventBridge::loadScriptIntoKWin()
{
    QDBusConnection bus = QDBusConnection::sessionBus();
    QDBusInterface scripting(kKWinService, kScriptingPath, kScriptingIface, bus);
    scripting.setTimeout(kDbusTimeoutMs);
    if (!scripting.isValid())
        return false;

    // Remove any previous instance under our stable pluginName (orphan cleanup
    // after a shell crash, or our own previous generation before a reload).
    scripting.call(QStringLiteral("unloadScript"), m_pluginName);

    const QDBusReply<int> id =
        scripting.call(QStringLiteral("loadScript"), m_scriptPath, m_pluginName);
    if (!id.isValid() || id.value() < 0)
        return false;

    QDBusInterface scriptObject(
        kKWinService, QLatin1String(kScriptingPath) + QStringLiteral("/Script")
                          + QString::number(id.value()),
        kScriptIface, bus);
    scriptObject.setTimeout(kDbusTimeoutMs);
    const QDBusReply<void> ran = scriptObject.call(QStringLiteral("run"));
    if (!ran.isValid())
        return false;

    m_scriptLoaded = true;
    return true;
}

void KWinEventBridge::scheduleReload()
{
    resetStreamState();
    if (m_reloadQueued)
        return;
    m_reloadQueued = true;
    m_reloadTimer->start(m_reloadBackoffMs);
    m_reloadBackoffMs = qMin(m_reloadBackoffMs * 2, 5000);
}

void KWinEventBridge::resetStreamState()
{
    m_pending.clear();
    m_flushTimer->stop();
}

void KWinEventBridge::setConnected(bool connected)
{
    if (m_connected == connected)
        return;
    m_connected = connected;
    emit connectedChanged();
}
