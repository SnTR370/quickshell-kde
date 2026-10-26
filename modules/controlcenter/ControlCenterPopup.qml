import QtQuick
import Quickshell
import "../../services"
import "../../components"
import "."

AnchoredPopup {
    id: root

    readonly property real screenMaxHeight: {
        const scr = (root.parentWindow && root.parentWindow.screen) ? root.parentWindow.screen : null;
        if (scr && scr.height > 0) {
            return Math.max(260, scr.height - (ConfigService.barHeight + (ConfigService.barFloating ? ConfigService.barEdgeOffset : 0) + 28));
        }
        return 620;
    }

    implicitWidth: controlCenter.implicitWidth
    implicitHeight: controlCenter.implicitHeight

    ControlCenter {
        id: controlCenter
        anchors.fill: parent
        embeddedInPopup: true
        maxHeight: root.screenMaxHeight
        onCloseRequested: root.close()
    }
}
