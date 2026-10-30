import QtQuick
import QtQuick.Layouts
import Qt.labs.folderlistmodel
import Quickshell
import "../../services"
import "../../components"
import "../../services/config/DockStacks.js" as DockStacks

// DOCK-011: stack popup. Two modes sharing one surface:
//  - "apps"  : grid of member applications; click launches, the hover "x"
//              removes the app from the stack.
//  - "folder": live folder listing (Qt.labs.folderlistmodel, watched by Qt -
//              no polling); directories navigate deeper, files open with the
//              user's default associations (ApplicationService.openPaths).
// AnchoredPopup's keyboard machinery collects the row/tile MouseAreas in
// tree order, so arrow/Tab/Enter navigation works without extra code.
AnchoredPopup {
    id: root

    property var stack: null
    // Folder stacks only: current navigation target (starts at stack.path).
    property string currentFolderPath: stack ? String(stack.path || "") : ""
    accessibleName: (stack ? stack.title : "Stack") + " stack"

    readonly property bool isFolderStack: stack !== null && stack.type === "folder"
    readonly property var stackAppIds: (stack === null || stack.type !== "apps") ? [] : DockStacks.toArray(stack.appIds)
    readonly property string baseFolderPath: stack ? String(stack.path || "") : ""
    readonly property bool canGoUp: root.isFolderStack && root.baseFolderPath.length > 0
        && root.currentFolderPath.length > root.baseFolderPath.length
        && root.currentFolderPath.indexOf(root.baseFolderPath + "/") === 0
    readonly property string currentFolderName: {
        if (!root.isFolderStack) return "";
        const p = root.currentFolderPath;
        if (!p || p === "/") return "/";
        const parts = p.split("/").filter(function(s) { return s.length > 0; });
        return parts.length > 0 ? parts[parts.length - 1] : "/";
    }

    // Live folder-model state (exposed for tests and future consumers).
    readonly property int folderEntryCount: folderModel.count
    readonly property int folderModelStatus: folderModel.status

    function launchStackApp(appId) {
        return ApplicationService.launchAppId(appId);
    }

    function removeStackApp(appId) {
        if (!root.stack) return false;
        return ConfigService.removeAppFromDockStack(root.stack.id, appId);
    }

    function openInFileManager() {
        if (!root.isFolderStack) return false;
        return ApplicationService.openPaths([root.baseFolderPath]);
    }

    function openPath(path) {
        return ApplicationService.openPaths([path]);
    }

    function navigateTo(path) {
        const clean = String(path || "").trim();
        if (clean.length === 0) return false;
        root.currentFolderPath = clean;
        return true;
    }

    function parentOf(path) {
        const p = String(path || "");
        if (p === "/" || p.length === 0) return "";
        const idx = p.lastIndexOf("/");
        if (idx <= 0) return "/";
        return p.slice(0, idx);
    }

    onStackChanged: {
        if (stack && stack.type === "folder") {
            root.currentFolderPath = String(stack.path || "");
        } else {
            root.currentFolderPath = "";
        }
    }

    implicitWidth: 320
    implicitHeight: stackCol.implicitHeight + 20

    ColumnLayout {
        id: stackCol
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
                text: root.isFolderStack ? root.currentFolderName : (root.stack ? root.stack.title : "")
                color: Theme.foreground
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                font.bold: true
                elide: Text.ElideRight
                Layout.fillWidth: true
            }

            Badge {
                visible: root.stack !== null && !root.isFolderStack
                text: root.stackAppIds.length + (root.stackAppIds.length === 1 ? " app" : " apps")
                badgeColor: Theme.primary
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: Theme.border
            opacity: 0.5
        }

        // ---- Apps stack: grid of member applications ----------------------
        Flow {
            visible: !root.isFolderStack
            Layout.fillWidth: true
            spacing: 6

            Repeater {
                model: root.stackAppIds

                Rectangle {
                    id: appTile
                    required property var modelData
                    readonly property var app: ApplicationService.getAppById(modelData)
                    implicitWidth: 76
                    implicitHeight: 86
                    radius: Theme.radiusSmall
                    color: tileMouse.containsMouse ? Theme.hover : "transparent"
                    Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

                    ColumnLayout {
                        anchors.centerIn: parent
                        spacing: 4

                        SvgIcon {
                            icon: appTile.app ? appTile.app.icon : "application-x-executable"
                            size: 36
                            Layout.alignment: Qt.AlignHCenter
                        }

                        Text {
                            text: ApplicationService.cleanAppName(appTile.app ? appTile.app.name : appTile.modelData)
                            color: Theme.foreground
                            font.family: Theme.fontFamily
                            font.pixelSize: 10
                            elide: Text.ElideRight
                            Layout.maximumWidth: 70
                            horizontalAlignment: Text.AlignHCenter
                        }
                    }

                    Rectangle {
                        id: tileRemoveBtn
                        visible: tileMouse.containsMouse
                        anchors.top: parent.top
                        anchors.right: parent.right
                        anchors.margins: 2
                        implicitWidth: 18
                        implicitHeight: 18
                        radius: Theme.radiusSmall
                        color: tileRemoveMouse.containsMouse ? Theme.alpha(Theme.error, 0.22) : "transparent"

                        SvgIcon {
                            anchors.centerIn: parent
                            icon: "window-close"
                            size: 11
                            color: tileRemoveMouse.containsMouse ? Theme.error : Theme.foregroundMuted
                        }

                        MouseArea {
                            id: tileRemoveMouse
                            Accessible.role: Accessible.MenuItem
                            Accessible.name: "Remove " + (appTile.app ? appTile.app.name : appTile.modelData) + " from stack"
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.removeStackApp(appTile.modelData)
                        }
                    }

                    MouseArea {
                        id: tileMouse
                        Accessible.role: Accessible.MenuItem
                        Accessible.name: "Launch " + (appTile.app ? appTile.app.name : appTile.modelData)
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.launchStackApp(appTile.modelData)
                    }
                }
            }

            Text {
                visible: root.stackAppIds.length === 0
                Layout.fillWidth: true
                text: "Empty stack — drag applications onto the stack icon, or add them in Settings."
                color: Theme.foregroundMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                wrapMode: Text.WordWrap
            }
        }

        // ---- Folder stack: live directory listing -------------------------
        ColumnLayout {
            visible: root.isFolderStack
            Layout.fillWidth: true
            spacing: 4

            // Up-navigation (only inside the stack's own subtree).
            Rectangle {
                visible: root.canGoUp
                Layout.fillWidth: true
                implicitHeight: 28
                radius: Theme.radiusSmall
                color: upMouse.containsMouse ? Theme.hover : "transparent"
                Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    spacing: 8

                    SvgIcon {
                        icon: "go-up"
                        size: 14
                        color: Theme.foreground
                    }

                    Text {
                        text: "Up"
                        color: Theme.foreground
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                    }

                    Item { Layout.fillWidth: true }

                    Text {
                        text: root.parentOf(root.currentFolderPath)
                        color: Theme.foregroundMuted
                        font.family: Theme.fontFamily
                        font.pixelSize: 10
                        elide: Text.ElideMiddle
                        Layout.maximumWidth: 180
                    }
                }

                MouseArea {
                    id: upMouse
                    Accessible.role: Accessible.MenuItem
                    Accessible.name: "Go to parent folder"
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.navigateTo(root.parentOf(root.currentFolderPath))
                }
            }

            FolderListModel {
                id: folderModel
                folder: root.isFolderStack ? ("file://" + root.currentFolderPath) : ""
                sortField: FolderListModel.Name
                showDirsFirst: true
            }

            ListView {
                id: folderList
                Layout.fillWidth: true
                implicitHeight: Math.min(300, folderModel.count > 0 ? (folderModel.count * 30 + 8) : 96)
                clip: true
                spacing: 2
                model: folderModel

                // Missing/unreadable directory: visible empty state, never a
                // fabricated listing.
                Text {
                    visible: folderModel.status === FolderListModel.Error || (folderModel.status === FolderListModel.Ready && folderModel.count === 0)
                    anchors.centerIn: parent
                    width: parent.width - 16
                    text: folderModel.status === FolderListModel.Error
                        ? "Folder unavailable: " + root.currentFolderPath
                        : "Empty folder"
                    color: Theme.foregroundMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                }

                delegate: Rectangle {
                    id: fileRow
                    required property string fileName
                    required property string filePath
                    required property bool isDir
                    width: folderList.width
                    height: 30
                    radius: Theme.radiusSmall
                    color: fileMouse.containsMouse ? Theme.hover : "transparent"
                    Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        anchors.rightMargin: 8
                        spacing: 8

                        SvgIcon {
                            icon: fileRow.isDir ? "folder" : "text-x-generic"
                            size: 14
                            color: fileRow.isDir ? Theme.primary : Theme.foregroundMuted
                        }

                        Text {
                            text: fileRow.fileName
                            color: Theme.foreground
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSizeSmall
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }

                    MouseArea {
                        id: fileMouse
                        Accessible.role: Accessible.MenuItem
                        Accessible.name: (fileRow.isDir ? "Open folder " : "Open file ") + fileRow.fileName
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (fileRow.isDir) {
                                root.navigateTo(fileRow.filePath);
                            } else {
                                root.openPath(fileRow.filePath);
                            }
                        }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: Theme.border
            opacity: 0.5
        }

        // Footer action (folder stacks): open the base folder in the file manager.
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
    }
}
