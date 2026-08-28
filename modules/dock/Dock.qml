import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import "../../services"
import "../../components"
import "."

Variants {
    id: root

    model: Quickshell.screens

    PanelWindow {
        id: dockWindow
        required property var modelData

        screen: modelData
        color: "transparent"
        visible: ConfigService.dockEnabled

        readonly property bool isVertical: ConfigService.dockPosition === "left" || ConfigService.dockPosition === "right"

        anchors {
            bottom: ConfigService.dockPosition === "bottom"
            top: ConfigService.dockPosition === "top"
            left: ConfigService.dockPosition === "left"
            right: ConfigService.dockPosition === "right"
        }

        implicitHeight: isVertical ? (dockSurface.implicitHeight + 24) : (ConfigService.dockIconSize + 20)
        implicitWidth: isVertical ? (ConfigService.dockIconSize + 20) : (dockSurface.implicitWidth + 24)
        exclusiveZone: ConfigService.dockAutoHide ? 0 : (ConfigService.dockIconSize + 16)

        WlrLayershell.layer: WlrLayer.Top

        Surface {
            id: dockSurface
            anchors.centerIn: parent
            implicitHeight: dockWindow.isVertical ? (colLayout.implicitHeight + 16) : (ConfigService.dockIconSize + 16)
            implicitWidth: dockWindow.isVertical ? (ConfigService.dockIconSize + 16) : (rowLayout.implicitWidth + 16)
            radius: Theme.radiusLarge
            color: Theme.alpha(Theme.background, ConfigService.barOpacity)

            // Horizontal Dock Layout
            RowLayout {
                id: rowLayout
                visible: !dockWindow.isVertical
                anchors.centerIn: parent
                spacing: 6

                // Launcher toggle
                IconButton {
                    size: ConfigService.dockIconSize
                    icon: "start-here-kde"
                    iconColor: Theme.primary
                    backgroundColor: Theme.alpha(Theme.primary, 0.12)
                    tooltip: "Applications"
                    onClicked: ConfigService.toggleLauncher()
                }

                DockSeparator { isVertical: false }

                // Pinned apps
                Repeater {
                    model: ApplicationService.pinnedApps

                    DockItem {
                        required property var modelData
                        appId: modelData
                        app: ApplicationService.getAppById(modelData)
                    }
                }

                DockSeparator { isVertical: false }

                // Settings toggle
                IconButton {
                    size: ConfigService.dockIconSize
                    icon: "preferences-system"
                    iconColor: Theme.foreground
                    tooltip: "Settings"
                    onClicked: ConfigService.toggleSettings()
                }
            }

            // Vertical Dock Layout
            ColumnLayout {
                id: colLayout
                visible: dockWindow.isVertical
                anchors.centerIn: parent
                spacing: 6

                // Launcher toggle
                IconButton {
                    size: ConfigService.dockIconSize
                    icon: "start-here-kde"
                    iconColor: Theme.primary
                    backgroundColor: Theme.alpha(Theme.primary, 0.12)
                    tooltip: "Applications"
                    onClicked: ConfigService.toggleLauncher()
                }

                DockSeparator { isVertical: true }

                // Pinned apps
                Repeater {
                    model: ApplicationService.pinnedApps

                    DockItem {
                        required property var modelData
                        appId: modelData
                        app: ApplicationService.getAppById(modelData)
                    }
                }

                DockSeparator { isVertical: true }

                // Settings toggle
                IconButton {
                    size: ConfigService.dockIconSize
                    icon: "preferences-system"
                    iconColor: Theme.foreground
                    tooltip: "Settings"
                    onClicked: ConfigService.toggleSettings()
                }
            }
        }
    }
}
