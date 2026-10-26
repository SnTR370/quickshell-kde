import QtQuick
import QtQuick.Layouts
import "../../services"

Rectangle {
    id: root
    property bool isVertical: false
    property bool acceptPinDrop: false
    readonly property bool dropTargeted: separatorDropArea.containsDrag

    implicitWidth: isVertical ? 24 : 1
    implicitHeight: isVertical ? 1 : 24
    color: dropTargeted ? Theme.primary : Theme.alpha(Theme.border, 0.6)
    Layout.alignment: Qt.AlignCenter
    activeFocusOnTab: false
    Accessible.role: Accessible.Separator
    Accessible.ignored: true

    DropArea {
        id: separatorDropArea
        visible: root.acceptPinDrop && root.visible
        enabled: root.acceptPinDrop && root.visible
        keys: ["quickshell-dock-item"]
        x: root.isVertical ? -14 : (ApplicationService.pinnedApps.length === 0 ? -52 : -14)
        y: root.isVertical ? (ApplicationService.pinnedApps.length === 0 ? -52 : -14) : -14
        width: root.isVertical ? 52 : (ApplicationService.pinnedApps.length === 0 ? 68 : 29)
        height: root.isVertical ? (ApplicationService.pinnedApps.length === 0 ? 68 : 29) : 52

        onDropped: drop => {
            if (!root.acceptPinDrop || !root.visible || !drop.source) {
                drop.accepted = false;
                return;
            }
            const src = drop.source;
            if (!src.appId || src.isPinned || !src.isRunning) {
                drop.accepted = false;
                return;
            }
            if (!ApplicationService.getAppById(src.appId) || ApplicationService.isPinned(src.appId)) {
                drop.accepted = false;
                return;
            }
            if (src.acceptDropTarget) {
                src.acceptDropTarget({
                    targetIndex: ApplicationService.pinnedApps.length,
                    targetAppId: ""
                });
                drop.accept(Qt.MoveAction);
            } else {
                drop.accepted = false;
            }
        }
    }
}
