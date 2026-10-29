import QtQuick

// Loader host for the compiled KWinEventBridge module.
//
// WindowService loads this file with a Loader; if the committed plugin binary
// does not match the local Qt/ABI, the Loader reports an error and the shell
// keeps the snapshot-based sync path (graceful degradation).
KWinEventBridge {
    id: bridge

    // Called by WindowService after the Loader finished loading.
    function enable(scriptTemplatePath) {
        return bridge.start(scriptTemplatePath);
    }
}
