import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import "../../services"
import "../../components"
import "."

Variants {
    id: root

    // Multi-monitor variant discovery
    model: Quickshell.screens

    Component { id: modLauncher; LauncherButton {} }
    Component { id: modWorkspaces; WorkspacesModule {} }
    Component { id: modClock; ClockModule {} }
    Component { id: modMedia; MediaModule {} }
    Component { id: modTray; TrayModule {} }
    Component { id: modNetwork; NetworkModule {} }
    Component { id: modBattery; BatteryModule {} }
    Component { id: modAudio; AudioModule {} }
    Component { id: modPower; PowerButton {} }

    function getModuleComponent(name) {
        switch (name) {
            case "launcher": return modLauncher;
            case "workspaces": return modWorkspaces;
            case "clock": return modClock;
            case "media": return modMedia;
            case "tray": return modTray;
            case "network": return modNetwork;
            case "battery": return modBattery;
            case "audio": return modAudio;
            case "power": return modPower;
            default: return null;
        }
    }

    PanelWindow {
        id: barWindow
        required property var modelData

        screen: modelData
        color: "transparent"
        visible: ConfigService.isScreenAllowed(modelData, ConfigService.barMonitors)

        readonly property bool isVertical: ConfigService.barPosition === "left" || ConfigService.barPosition === "right"

        anchors {
            top: barWindow.isVertical || ConfigService.barPosition === "top"
            bottom: barWindow.isVertical || ConfigService.barPosition === "bottom"
            left: !barWindow.isVertical || ConfigService.barPosition === "left"
            right: !barWindow.isVertical || ConfigService.barPosition === "right"
        }

        implicitHeight: isVertical ? -1 : ConfigService.barHeight
        implicitWidth: isVertical ? ConfigService.barHeight : -1
        exclusiveZone: ConfigService.barHeight

        WlrLayershell.layer: WlrLayer.Top

        BackgroundEffect.blurRegion: ConfigService.blurEnabled ? Region { item: barSurface } : null

        Surface {
            id: barSurface
            anchors.fill: parent
            anchors.margins: 4
            radius: Theme.radiusMedium
            color: Theme.alpha(Theme.background, ConfigService.barOpacity)

            // Horizontal Bar Layout
            RowLayout {
                visible: !barWindow.isVertical
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 8

                // Left Section
                RowLayout {
                    Layout.alignment: Qt.AlignLeft | Qt.AlignVCenter
                    spacing: 8

                    Repeater {
                        model: ConfigService.barLeft
                        Loader {
                            required property var modelData
                            sourceComponent: root.getModuleComponent(modelData)
                        }
                    }
                }

                // Center Spacer
                Item { Layout.fillWidth: true }

                // Center Section
                RowLayout {
                    Layout.alignment: Qt.AlignHCenter | Qt.AlignVCenter
                    spacing: 8

                    Repeater {
                        model: ConfigService.barCenter
                        Loader {
                            required property var modelData
                            sourceComponent: root.getModuleComponent(modelData)
                        }
                    }
                }

                // Right Spacer
                Item { Layout.fillWidth: true }

                // Right Section
                RowLayout {
                    Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                    spacing: 8

                    Repeater {
                        model: ConfigService.barRight
                        Loader {
                            required property var modelData
                            sourceComponent: root.getModuleComponent(modelData)
                        }
                    }
                }
            }

            // Vertical Bar Layout
            ColumnLayout {
                visible: barWindow.isVertical
                anchors.fill: parent
                anchors.topMargin: 8
                anchors.bottomMargin: 8
                spacing: 8

                // Top Section
                ColumnLayout {
                    Layout.alignment: Qt.AlignTop | Qt.AlignHCenter
                    spacing: 8

                    Repeater {
                        model: ConfigService.barLeft
                        Loader {
                            required property var modelData
                            sourceComponent: root.getModuleComponent(modelData)
                        }
                    }
                }

                // Center Spacer
                Item { Layout.fillHeight: true }

                // Center Section
                ColumnLayout {
                    Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                    spacing: 8

                    Repeater {
                        model: ConfigService.barCenter
                        Loader {
                            required property var modelData
                            sourceComponent: root.getModuleComponent(modelData)
                        }
                    }
                }

                // Bottom Spacer
                Item { Layout.fillHeight: true }

                // Bottom Section
                ColumnLayout {
                    Layout.alignment: Qt.AlignBottom | Qt.AlignHCenter
                    spacing: 8

                    Repeater {
                        model: ConfigService.barRight
                        Loader {
                            required property var modelData
                            sourceComponent: root.getModuleComponent(modelData)
                        }
                    }
                }
            }
        }
    }
}
