import QtQuick
import Quickshell
import Quickshell.Io
import "Log.js" as Log

Item {
    id: root

    property string path: ""
    property string fallbackPath: ""
    property var defaultValue: ({})
    property var value: defaultValue
    property string rawContent: ""
    property bool loaded: false
    property bool readingFallback: false
    property bool saveInFlight: false
    property bool hasPendingSave: false
    property var pendingSaveData: null
    property string pendingSaveJson: ""
    property var inFlightData: null
    property string inFlightJson: ""
    property var lastPersistedValue: defaultValue
    property string lastPersistedRaw: ""
    property bool loadPendingAfterSave: false
    property bool readSuperseded: false
    property bool hadParseError: false

    signal loadedValue(var parsedJson, string rawText)
    signal savedValue(var data)
    signal failed(string phase, int exitCode, string details)

    function load() {
        if (!path || path.length === 0) return false;
        if (root.saveInFlight || writeProc.running) {
            root.loadPendingAfterSave = true;
            return true;
        }
        if (readProc.running) {
            readProc.running = false;
        }
        root.readingFallback = false;
        root.readSuperseded = false;
        readProc.command = ["cat", path];
        readProc.buf = "";
        readProc.running = true;
        return true;
    }

    function _startWrite(data, jsonStr) {
        root.saveInFlight = true;
        root.inFlightData = data;
        root.inFlightJson = jsonStr;
        writeProc.command = [
            "sh", "-c",
            "mkdir -p \"$(dirname \"$1\")\" && " +
            "if [ \"$3\" = \"1\" ] && [ -f \"$1\" ] && [ ! -f \"$1.bak\" ]; then cp -f \"$1\" \"$1.bak\" 2>/dev/null || true; fi && " +
            "printf '%s' \"$2\" > \"$1.tmp.$$\" && mv -f \"$1.tmp.$$\" \"$1\" || { rm -f \"$1.tmp.$$\" 2>/dev/null; exit 1; }",
            "sh", root.path, jsonStr, root.hadParseError ? "1" : "0"
        ];
        writeProc.running = true;
    }

    function save(data) {
        if (!path || path.length === 0) {
            root.failed("serialize", -1, "Empty path");
            return false;
        }
        try {
            if (data === undefined || typeof data === "function") {
                throw new Error("Cannot serialize undefined or function");
            }
            const jsonStr = JSON.stringify(data, null, 2);
            if (typeof jsonStr !== "string" || jsonStr.length === 0) {
                throw new Error("Serialization produced empty output");
            }
            if (readProc.running) {
                root.readSuperseded = true;
                readProc.running = false;
                root.loaded = true;
            }
            root.value = data;
            root.rawContent = jsonStr;
            if (root.saveInFlight || writeProc.running) {
                root.pendingSaveData = data;
                root.pendingSaveJson = jsonStr;
                root.hasPendingSave = true;
                return true;
            }
            root._startWrite(data, jsonStr);
            return true;
        } catch (e) {
            Log.error("JsonStore", "Failed to serialize JSON for " + path + ": " + e);
            root.failed("serialize", -1, String(e));
            return false;
        }
    }

    Process {
        id: readProc
        property string buf: ""
        stdout: SplitParser {
            onRead: data => { readProc.buf += data; }
        }
        onExited: exitCode => {
            if (root.readSuperseded) {
                readProc.buf = "";
                root.readSuperseded = false;
                return;
            }
            if (exitCode === 0) {
                const raw = readProc.buf;
                readProc.buf = "";
                if (raw.trim().length > 0) {
                    try {
                        const parsed = JSON.parse(raw);
                        if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
                            throw new Error("Root JSON value must be an object");
                        }
                        root.rawContent = raw;
                        root.value = parsed;
                        root.lastPersistedValue = parsed;
                        root.lastPersistedRaw = raw;
                        root.hadParseError = false;
                        root.loaded = true;
                        root.loadedValue(root.value, root.rawContent);
                    } catch (e) {
                        Log.warn("JsonStore", "Failed to parse JSON from " + (root.readingFallback ? root.fallbackPath : root.path) + ": " + e);
                        root.hadParseError = !root.readingFallback;
                        root.value = root.defaultValue;
                        root.loaded = true;
                        root.failed("parse", exitCode, String(e));
                    }
                } else {
                    Log.warn("JsonStore", "Empty JSON file at " + (root.readingFallback ? root.fallbackPath : root.path));
                    root.hadParseError = !root.readingFallback;
                    root.value = root.defaultValue;
                    root.loaded = true;
                    root.failed("parse", exitCode, "Empty JSON file");
                }
            } else if (!root.readingFallback && root.fallbackPath && root.fallbackPath.length > 0) {
                // Try fallback default configuration file when user config does not exist yet
                root.readingFallback = true;
                readProc.command = ["cat", root.fallbackPath];
                readProc.buf = "";
                readProc.running = true;
                return;
            } else {
                readProc.buf = "";
                root.value = root.defaultValue;
                root.loaded = true;
                root.failed("read", exitCode, "File not found or empty");
            }
        }
    }

    Process {
        id: writeProc
        onExited: exitCode => {
            if (exitCode === 0) {
                const savedData = root.inFlightData;
                root.lastPersistedValue = savedData;
                root.lastPersistedRaw = root.inFlightJson;
                root.value = savedData;
                root.rawContent = root.inFlightJson;
                root.hadParseError = false;
                if (root.hasPendingSave) {
                    const nextData = root.pendingSaveData;
                    const nextJson = root.pendingSaveJson;
                    root.hasPendingSave = false;
                    root.pendingSaveData = null;
                    root.pendingSaveJson = "";
                    root._startWrite(nextData, nextJson);
                    root.savedValue(savedData);
                } else {
                    root.saveInFlight = false;
                    root.savedValue(savedData);
                    if (root.loadPendingAfterSave) {
                        root.loadPendingAfterSave = false;
                        root.load();
                    }
                }
            } else {
                Log.error("JsonStore", "Failed to write file " + root.path);
                if (root.hasPendingSave) {
                    const nextData = root.pendingSaveData;
                    const nextJson = root.pendingSaveJson;
                    root.hasPendingSave = false;
                    root.pendingSaveData = null;
                    root.pendingSaveJson = "";
                    root.failed("write", exitCode, "Write process failed");
                    root._startWrite(nextData, nextJson);
                } else {
                    root.value = root.lastPersistedValue;
                    root.rawContent = root.lastPersistedRaw;
                    root.saveInFlight = false;
                    root.failed("write", exitCode, "Write process failed");
                    if (root.loadPendingAfterSave) {
                        root.loadPendingAfterSave = false;
                        root.load();
                    }
                }
            }
        }
    }

    Component.onCompleted: {
        if (path && path.length > 0) {
            load();
        }
    }
}
