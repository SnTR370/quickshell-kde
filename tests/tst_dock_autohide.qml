import QtQuick
import QtTest

TestCase {
    name: "DockAutohideTest"
    width: 800
    height: 600
    visible: true

    Item {
        id: rootWindow
        width: 800
        height: 600

        property bool autoHide: true
        property bool hoverRevealed: false
        property var activePopupItem: null
        readonly property bool hasActivePopup: activePopupItem !== null
        onHasActivePopupChanged: {
            if (!hasActivePopup && !dockHoverHandler.hovered && autoHide) {
                hideTimer.restart();
            }
        }
        readonly property bool isRevealed: !autoHide || hoverRevealed || dockAreaHover.hovered || dockHoverHandler.hovered || hasActivePopup

        Item {
            id: dockInteractiveArea
            anchors.fill: dockSurface
            HoverHandler {
                id: dockAreaHover
                onHoveredChanged: {
                    if (hovered) {
                        hideTimer.stop();
                        rootWindow.hoverRevealed = true;
                    } else {
                        if (rootWindow.autoHide && !rootWindow.hasActivePopup && !dockHoverHandler.hovered) {
                            hideTimer.restart();
                        }
                    }
                }
            }
        }

        Timer {
            id: hideTimer
            interval: 100
            repeat: false
            onTriggered: {
                if (!dockAreaHover.hovered && !dockHoverHandler.hovered && !rootWindow.hasActivePopup) {
                    rootWindow.hoverRevealed = false;
                }
            }
        }

        Rectangle {
            id: dockSurface
            anchors.bottom: parent.bottom
            anchors.horizontalCenter: parent.horizontalCenter
            width: 400
            height: 60

            HoverHandler {
                id: dockHoverHandler
                onHoveredChanged: {
                    if (hovered) {
                        hideTimer.stop();
                        rootWindow.hoverRevealed = true;
                    } else {
                        if (rootWindow.autoHide && !rootWindow.hasActivePopup) {
                            hideTimer.restart();
                        }
                    }
                }
            }

            Row {
                anchors.centerIn: parent
                spacing: 10

                Repeater {
                    id: iconRepeater
                    model: 3
                    Item {
                        id: dockItem
                        width: 40
                        height: 40
                        property bool menuOpen: false

                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            onClicked: {
                                dockItem.menuOpen = !dockItem.menuOpen;
                                if (dockItem.menuOpen) {
                                    rootWindow.activePopupItem = dockItem;
                                } else if (rootWindow.activePopupItem === dockItem) {
                                    rootWindow.activePopupItem = null;
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    function test_dock_hover_over_icons() {
        // Initially revealed is false when autoHide is on and not hovered
        compare(rootWindow.isRevealed, false, "Initial state: dock not revealed");

        // Hover over the dock surface (outside icons: x=250, y=550)
        mouseMove(rootWindow, 250, 550);
        wait(50);
        compare(rootWindow.isRevealed, true, "Dock revealed when surface hovered");

        // Hover directly over the first icon (x=360, y=570)
        mouseMove(rootWindow, 360, 570);
        wait(50);
        compare(rootWindow.isRevealed, true, "Dock must STAY revealed when child icon MouseArea is hovered");

        // Wait longer than hideTimer interval (150ms > 100ms)
        wait(150);
        compare(rootWindow.isRevealed, true, "Dock must NOT autohide while hovering over child icon!");

        // Open popup on icon
        mouseClick(rootWindow, 360, 570);
        wait(50);
        compare(rootWindow.hasActivePopup, true, "Popup is now open");

        // Move mouse away from dock completely (x=100, y=100)
        mouseMove(rootWindow, 100, 100);
        wait(150);
        compare(rootWindow.isRevealed, true, "Dock must STAY revealed while active popup is open even if mouse left surface");

        // Close popup
        rootWindow.activePopupItem = null;
        wait(150); // wait for hideTimer
        compare(rootWindow.isRevealed, false, "Dock autohides after popup is closed and mouse is away");
    }
}
