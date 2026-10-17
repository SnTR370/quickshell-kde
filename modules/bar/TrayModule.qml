import QtQuick
import QtQuick.Layouts
import Quickshell.Services.SystemTray
import "../../services"
import "../../components"

Surface {
    id: root

    property var barWindowRef: null
    property string surfaceEdge: "top"
    property bool overflowOpen: false

    readonly property var rawItems: SystemTray.items ? SystemTray.items.values : []

    function isItemVisibleInBar(item) {
        if (!item) return false;
        const _policies = ConfigService.trayItemPolicies;
        const st = item.status;
        const policy = ConfigService.getTrayItemPolicy(item, root.rawItems);
        if (policy === "always") return true;
        if (policy === "hidden") return false;
        if (st === Status.Passive || st === 0 || String(st).toLowerCase() === "passive") {
            return false;
        }
        return true;
    }

    readonly property var visibleItems: {
        const _policies = ConfigService.trayItemPolicies;
        const list = root.rawItems || [];
        const res = [];
        for (let i = 0; i < list.length; i++) {
            const it = list[i];
            if (it && root.isItemVisibleInBar(it)) {
                res.push(it);
            }
        }
        return res;
    }

    readonly property var hiddenItems: {
        const _policies = ConfigService.trayItemPolicies;
        const list = root.rawItems || [];
        const res = [];
        for (let i = 0; i < list.length; i++) {
            const it = list[i];
            if (it && !root.isItemVisibleInBar(it)) {
                res.push(it);
            }
        }
        return res;
    }

    readonly property bool hasHiddenItems: root.hiddenItems.length > 0

    onHasHiddenItemsChanged: {
        if (!root.hasHiddenItems && root.overflowOpen) {
            root.overflowOpen = false;
        }
    }

    onVisibleChanged: {
        if (!root.visible && root.overflowOpen) {
            root.overflowOpen = false;
        }
    }

    visible: root.visibleItems.length > 0 || root.hasHiddenItems
    implicitHeight: Math.max(20, ConfigService.barHeight - 6)
    implicitWidth: trayLayout.implicitWidth + 8
    radius: Theme.radiusSmall
    color: Theme.alpha(Theme.surfaceVariant, 0.6)

    RowLayout {
        id: trayLayout
        anchors.centerIn: parent
        spacing: 4

        Repeater {
            model: root.visibleItems

            Item {
                id: trayDelegate
                required property var modelData

                implicitWidth: Math.max(16, ConfigService.barHeight - 8)
                implicitHeight: Math.max(16, ConfigService.barHeight - 8)

                Rectangle {
                    anchors.fill: parent
                    radius: Theme.radiusSmall
                    color: trayItemMouse.containsMouse ? Theme.hover : "transparent"

                    SvgIcon {
                        anchors.centerIn: parent
                        icon: (trayDelegate.modelData && trayDelegate.modelData.icon && String(trayDelegate.modelData.icon).length > 0) ? String(trayDelegate.modelData.icon) : ((trayDelegate.modelData && trayDelegate.modelData.iconName) || "application-x-executable")
                        size: Math.max(14, ConfigService.barHeight - 12)
                    }

                    MouseArea {
                        id: trayItemMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton

                        onClicked: mouse => {
                            if (!trayDelegate.modelData) return;
                            if (mouse.button === Qt.RightButton) {
                                if (trayDelegate.modelData.hasMenu) {
                                    const win = root.barWindowRef || root.Window.window;
                                    const targetItem = win && win.contentItem ? win.contentItem : null;
                                    const pt = trayItemMouse.mapToItem(targetItem, mouse.x, mouse.y);
                                    trayDelegate.modelData.display(win, Math.round(pt.x), Math.round(pt.y));
                                } else {
                                    trayDelegate.modelData.secondaryActivate();
                                }
                            } else if (mouse.button === Qt.MiddleButton) {
                                trayDelegate.modelData.secondaryActivate();
                            } else {
                                trayDelegate.modelData.activate();
                            }
                        }

                        onWheel: wheel => {
                            if (!trayDelegate.modelData) return;
                            trayDelegate.modelData.scroll(wheel.angleDelta.y, false);
                        }
                    }
                }
            }
        }

        Item {
            id: chevronBtn
            visible: root.hasHiddenItems
            implicitWidth: Math.max(16, ConfigService.barHeight - 8)
            implicitHeight: Math.max(16, ConfigService.barHeight - 8)

            Rectangle {
                anchors.fill: parent
                radius: Theme.radiusSmall
                color: (chevronMouse.containsMouse || root.overflowOpen) ? Theme.hover : "transparent"

                SvgIcon {
                    anchors.centerIn: parent
                    icon: root.overflowOpen ? "arrow-up" : "arrow-down"
                    size: Math.max(12, ConfigService.barHeight - 14)
                    color: root.overflowOpen ? Theme.primary : Theme.foregroundMuted
                }

                MouseArea {
                    id: chevronMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    acceptedButtons: Qt.LeftButton
                    onClicked: {
                        root.overflowOpen = !root.overflowOpen;
                    }
                }
            }
        }
    }

    Loader {
        id: overflowPopupLoader
        active: root.overflowOpen && root.hasHiddenItems
        sourceComponent: AnchoredPopup {
            id: overflowPopup
            parentWindow: root.barWindowRef || root.Window.window
            anchorItem: chevronBtn
            edge: root.surfaceEdge
            onClosed: root.overflowOpen = false

            implicitWidth: Math.max(48, overflowGrid.implicitWidth + 16)
            implicitHeight: Math.max(48, overflowGrid.implicitHeight + 16)

            GridLayout {
                id: overflowGrid
                anchors.centerIn: parent
                columns: Math.min(4, Math.max(1, root.hiddenItems.length))
                rowSpacing: 4
                columnSpacing: 4

                Repeater {
                    model: root.hiddenItems

                    Rectangle {
                        id: overflowDelegate
                        required property var modelData

                        implicitWidth: 32
                        implicitHeight: 32
                        radius: Theme.radiusSmall
                        color: overflowItemMouse.containsMouse ? Theme.hover : "transparent"

                        SvgIcon {
                            anchors.centerIn: parent
                            icon: (overflowDelegate.modelData && overflowDelegate.modelData.icon && String(overflowDelegate.modelData.icon).length > 0) ? String(overflowDelegate.modelData.icon) : ((overflowDelegate.modelData && overflowDelegate.modelData.iconName) || "application-x-executable")
                            size: 20
                        }

                        MouseArea {
                            id: overflowItemMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton

                            onClicked: mouse => {
                                if (!overflowDelegate.modelData) return;
                                if (mouse.button === Qt.RightButton) {
                                    if (overflowDelegate.modelData.hasMenu) {
                                        const win = overflowPopup;
                                        const targetItem = win && win.contentItem ? win.contentItem : null;
                                        const pt = overflowItemMouse.mapToItem(targetItem, mouse.x, mouse.y);
                                        overflowDelegate.modelData.display(win, Math.round(pt.x), Math.round(pt.y));
                                    } else {
                                        overflowDelegate.modelData.secondaryActivate();
                                    }
                                } else if (mouse.button === Qt.MiddleButton) {
                                    overflowDelegate.modelData.secondaryActivate();
                                } else {
                                    overflowDelegate.modelData.activate();
                                }
                            }

                            onWheel: wheel => {
                                if (!overflowDelegate.modelData) return;
                                overflowDelegate.modelData.scroll(wheel.angleDelta.y, false);
                            }
                        }
                    }
                }
            }
        }
    }
}
