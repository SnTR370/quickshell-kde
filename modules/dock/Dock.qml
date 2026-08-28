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

        anchors {
            bottom: true
        }

        implicitHeight: ConfigService.dockIconSize + 20
        implicitWidth: dockSurface.implicitWidth + 24
        exclusiveZone: ConfigService.dockAutoHide ? 0 : (ConfigService.dockIconSize + 16)

        WlrLayershell.layer: WlrLayer.Top

        Surface {
            id: dockSurface
            anchors.centerIn: parent
            implicitHeight: ConfigService.dockIconSize + 16
            implicitWidth: rowLayout.implicitWidth + 16
            radius: Theme.radiusLarge
            color: Theme.alpha(Theme.background, ConfigService.barOpacity)

            RowLayout {
                id: rowLayout
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

                DockSeparator {}

                // Pinned apps
                Repeater {
                    model: ApplicationService.pinnedApps

                    DockItem {
                        required property var modelData
                        appId: modelData
                        app: ApplicationService.getAppById(modelData)
                    }
                }

                DockSeparator {}

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
