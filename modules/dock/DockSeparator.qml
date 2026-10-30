import QtQuick
import QtQuick.Layouts
import "../../services"

Rectangle {
    id: root
    property bool isVertical: false
    property bool acceptPinDrop: false
    // DOCK-004: lateral displacement along the layout axis, assigned by the
    // Dock magnification controller so separators move apart with the icons.
    property real magnifiedOffset: 0
    readonly property real appliedMagnifiedOffset: root.isVertical ? sepTranslate.y : sepTranslate.x
    readonly property bool dropTargeted: separatorDropArea.containsDrag

    implicitWidth: isVertical ? 24 : 1
    implicitHeight: isVertical ? 1 : 24

    // Transform-only displacement: rest layout geometry never changes.
    transform: Translate {
        id: sepTranslate
        x: root.isVertical ? 0 : root.magnifiedOffset
        y: root.isVertical ? root.magnifiedOffset : 0
        Behavior on x {
            NumberAnimation {
                duration: Theme.animDurationFast
                easing.type: Theme.animEasing
            }
        }
        Behavior on y {
            NumberAnimation {
                duration: Theme.animDurationFast
                easing.type: Theme.animEasing
            }
        }
    }
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
