import QtQuick
import QtQuick.Layouts
import Quickshell
import "../../services"
import "../../components"
import "../../services/config/DockStacks.js" as DockStacks

// DOCK-011: context menu for dock stacks (right-click on a stack icon).
// Folder stacks can be opened in the file manager; both types can be
// removed from the dock. Removal drops the stack and its dock-row marker
// (member apps of an apps stack go with it - they live in the stack).
AnchoredPopup {
    id: root

    property var stack: null
    accessibleName: (stack ? stack.title : "Stack") + " context menu"

    readonly property bool isFolderStack: stack !== null && stack.type === "folder"

    signal actionTriggered()

    function openInFileManager() {
        if (!root.isFolderStack || !root.stack.path) return false;
        const ok = ApplicationService.openPaths([root.stack.path]);
        if (ok) {
            root.actionTriggered();
        }
        return ok;
    }

    function removeStack() {
        if (!root.stack) return false;
        const ok = ConfigService.removeDockStack(root.stack.id);
        if (ok) {
            root.actionTriggered();
        }
        return ok;
    }

    implicitWidth: 240
    implicitHeight: menuLayout.implicitHeight + 16

    ColumnLayout {
        id: menuLayout
        anchors.fill: parent
        anchors.margins: 8
        spacing: 4

        // Header
        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 4
            Layout.rightMargin: 4
            Layout.bottomMargin: 4
            spacing: 8

            SvgIcon {
                icon: DockStacks.stackIcon(root.stack)
                size: 20
            }

            Text {
                text: root.stack ? root.stack.title : ""
                color: Theme.foreground
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                font.bold: true
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: Theme.border
            opacity: 0.5
        }

        // Open folder in file manager (folder stacks only)
        Rectangle {
            visible: root.isFolderStack
            Layout.fillWidth: true
            implicitHeight: 28
            radius: Theme.radiusSmall
            color: openFmMouse.containsMouse ? Theme.hover : "transparent"
            Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 8

                SvgIcon {
                    icon: "folder-open"
                    size: 14
                    color: Theme.foreground
                }

                Text {
                    text: "Open in File Manager"
                    color: Theme.foreground
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                }
            }

            MouseArea {
                id: openFmMouse
                Accessible.role: Accessible.MenuItem
                Accessible.name: "Open stack folder in file manager"
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.openInFileManager()
            }
        }

        // Remove stack from the dock
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 28
            radius: Theme.radiusSmall
            color: removeMouse.containsMouse ? Theme.alpha(Theme.error, 0.18) : "transparent"
            Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 8

                SvgIcon {
                    icon: "edit-delete"
                    size: 14
                    color: Theme.error
                }

                Text {
                    text: "Remove Stack"
                    color: Theme.error
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                }
            }

            MouseArea {
                id: removeMouse
                Accessible.role: Accessible.MenuItem
                Accessible.name: "Remove stack from dock"
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.removeStack()
            }
        }
    }
}
