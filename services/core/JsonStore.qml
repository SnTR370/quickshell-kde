import QtQuick
import Quickshell
import Quickshell.Io
import "Log.js" as Log

Item {
    id: root

    property string path: ""
    property var defaultValue: ({})
    property var value: defaultValue
    property string rawContent: ""
    property bool loaded: false

    signal loadedValue(var parsedJson, string rawText)
    signal savedValue(var data)
    signal failed(string phase, int exitCode, string details)

    function load() {
        if (!path || path.length === 0) return;
        readProc.command = ["cat", path];
        readProc.buf = "";
        readProc.running = true;
    }

    function save(data) {
        if (!path || path.length === 0) return;
        try {
            const jsonStr = JSON.stringify(data, null, 2);
            root.value = data;
            root.rawContent = jsonStr;
            writeProc.command = ["sh", "-c", "mkdir -p \"$(dirname \"$1\")\" && printf '%s' \"$2\" > \"$1.tmp\" && mv \"$1.tmp\" \"$1\"", "sh", root.path, jsonStr];
            writeProc.running = true;
        } catch (e) {
            Log.error("JsonStore", "Failed to serialize JSON for " + path + ": " + e);
            root.failed("serialize", -1, String(e));
        }
    }

    Process {
        id: readProc
        property string buf: ""
        stdout: SplitParser {
            onRead: data => { readProc.buf += data; }
        }
        onExited: exitCode => {
            if (exitCode === 0 && readProc.buf.trim().length > 0) {
                try {
                    root.rawContent = readProc.buf;
                    root.value = JSON.parse(readProc.buf);
                    root.loaded = true;
                    root.loadedValue(root.value, root.rawContent);
                } catch (e) {
                    Log.warn("JsonStore", "Failed to parse JSON from " + root.path + ": " + e);
                    root.value = root.defaultValue;
                    root.loaded = true;
                    root.failed("parse", exitCode, String(e));
                }
            } else {
                root.value = root.defaultValue;
                root.loaded = true;
                root.failed("read", exitCode, "File not found or empty");
            }
            readProc.buf = "";
        }
    }

    Process {
        id: writeProc
        onExited: exitCode => {
            if (exitCode === 0) {
                root.savedValue(root.value);
            } else {
                Log.error("JsonStore", "Failed to write file " + root.path);
                root.failed("write", exitCode, "Write process failed");
            }
        }
    }

    Component.onCompleted: {
        if (path && path.length > 0) {
            load();
        }
    }
}
