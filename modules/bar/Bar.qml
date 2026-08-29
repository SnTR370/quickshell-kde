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

    Component { id: modLauncher; LauncherButton {} }
    Component { id: modWorkspaces; WorkspacesModule {} }
    Component { id: modClock; ClockModule {} }
    Component { id: modMedia; MediaModule {} }
    Component { id: modTray; TrayModule {} }
    Component { id: modNetwork; NetworkModule {} }
    Component { id: modBattery; BatteryModule {} }
    Component { id: modAudio; AudioModule {} }
    Component { id: modBrightness; BrightnessModule {} }
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
            case "brightness": return modBrightness;
            case "power": return modPower;
            default: return null;
        }
    }

    PanelWindow {
        id: barWindow
        required property var modelData

        screen: modelData
        color: "transparent"
        visible: ConfigService.barEnabled && ConfigService.isScreenAllowed(modelData, ConfigService.barMonitors)

        readonly property string edge: ConfigService.barEdge
        readonly property bool isVertical: edge === "left" || edge === "right"
        readonly property bool isFloating: ConfigService.barFloating
        readonly property int offset: isFloating ? ConfigService.barEdgeOffset : 0

        anchors {
            top: barWindow.isVertical || barWindow.edge === "top"
            bottom: barWindow.isVertical || barWindow.edge === "bottom"
            left: !barWindow.isVertical || barWindow.edge === "left"
            right: !barWindow.isVertical || barWindow.edge === "right"
        }

        margins {
            top: (!barWindow.isFloating) ? 0 : ((barWindow.edge === "top" || barWindow.isVertical) ? barWindow.offset : 0)
            bottom: (!barWindow.isFloating) ? 0 : ((barWindow.edge === "bottom" || barWindow.isVertical) ? barWindow.offset : 0)
            left: (!barWindow.isFloating) ? 0 : ((barWindow.edge === "left" || !barWindow.isVertical) ? barWindow.offset : 0)
            right: (!barWindow.isFloating) ? 0 : ((barWindow.edge === "right" || !barWindow.isVertical) ? barWindow.offset : 0)
        }

        implicitHeight: isVertical ? -1 : ConfigService.barHeight
        implicitWidth: isVertical ? ConfigService.barHeight : -1
        exclusiveZone: ConfigService.barReserveSpace ? (ConfigService.barHeight + (isFloating ? offset : 0)) : 0

        WlrLayershell.layer: WlrLayer.Top
        WlrLayershell.namespace: "quickshell:bar"

        BackgroundEffect.blurRegion: Region {
            item: ConfigService.blurEnabled ? barSurface : null
        }

        mask: Region {
            item: barSurface
        }

        Surface {
            id: barSurface
            anchors.fill: parent
            radius: barWindow.isFloating ? Theme.radiusMedium : 0
            borderVisible: barWindow.isFloating
            color: Theme.alpha(Theme.background, ConfigService.barOpacity)

            // Horizontal Bar Layout
            RowLayout {
                visible: !barWindow.isVertical
                anchors.fill: parent
                anchors.leftMargin: 6
                anchors.rightMargin: 6
                spacing: 4

                // Left Section
                RowLayout {
                    Layout.alignment: Qt.AlignLeft | Qt.AlignVCenter
                    Layout.fillHeight: true
                    spacing: 4

                    Repeater {
                        model: ConfigService.barLeft
                        Loader {
                            required property var modelData
                            sourceComponent: root.getModuleComponent(modelData)
                            Layout.alignment: Qt.AlignVCenter
                            Layout.fillHeight: true
                            onLoaded: {
                                if (item && item.hasOwnProperty("barWindowRef")) item.barWindowRef = barWindow;
                                if (item && item.hasOwnProperty("surfaceEdge")) item.surfaceEdge = barWindow.edge;
                            }
                        }
                    }
                }

                // Center Spacer
                Item { Layout.fillWidth: true }

                // Center Section
                RowLayout {
                    Layout.alignment: Qt.AlignHCenter | Qt.AlignVCenter
                    Layout.fillHeight: true
                    spacing: 4

                    Repeater {
                        model: ConfigService.barCenter
                        Loader {
                            required property var modelData
                            sourceComponent: root.getModuleComponent(modelData)
                            Layout.alignment: Qt.AlignVCenter
                            Layout.fillHeight: true
                            onLoaded: {
                                if (item && item.hasOwnProperty("barWindowRef")) item.barWindowRef = barWindow;
                                if (item && item.hasOwnProperty("surfaceEdge")) item.surfaceEdge = barWindow.edge;
                            }
                        }
                    }
                }

                // Right Spacer
                Item { Layout.fillWidth: true }

                // Right Section
                RowLayout {
                    Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                    Layout.fillHeight: true
                    spacing: 4

                    Repeater {
                        model: ConfigService.barRight
                        Loader {
                            required property var modelData
                            sourceComponent: root.getModuleComponent(modelData)
                            Layout.alignment: Qt.AlignVCenter
                            Layout.fillHeight: true
                            onLoaded: {
                                if (item && item.hasOwnProperty("barWindowRef")) item.barWindowRef = barWindow;
                                if (item && item.hasOwnProperty("surfaceEdge")) item.surfaceEdge = barWindow.edge;
                            }
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
                    Layout.fillWidth: true
                    spacing: 8

                    Repeater {
                        model: ConfigService.barLeft
                        Loader {
                            required property var modelData
                            sourceComponent: root.getModuleComponent(modelData)
                            Layout.alignment: Qt.AlignHCenter
                            Layout.fillWidth: true
                            onLoaded: {
                                if (item && item.hasOwnProperty("barWindowRef")) item.barWindowRef = barWindow;
                                if (item && item.hasOwnProperty("surfaceEdge")) item.surfaceEdge = barWindow.edge;
                            }
                        }
                    }
                }

                // Center Spacer
                Item { Layout.fillHeight: true }

                // Center Section
                ColumnLayout {
                    Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                    Layout.fillWidth: true
                    spacing: 8

                    Repeater {
                        model: ConfigService.barCenter
                        Loader {
                            required property var modelData
                            sourceComponent: root.getModuleComponent(modelData)
                            Layout.alignment: Qt.AlignHCenter
                            Layout.fillWidth: true
                            onLoaded: {
                                if (item && item.hasOwnProperty("barWindowRef")) item.barWindowRef = barWindow;
                                if (item && item.hasOwnProperty("surfaceEdge")) item.surfaceEdge = barWindow.edge;
                            }
                        }
                    }
                }

                // Bottom Spacer
                Item { Layout.fillHeight: true }

                // Bottom Section
                ColumnLayout {
                    Layout.alignment: Qt.AlignBottom | Qt.AlignHCenter
                    Layout.fillWidth: true
                    spacing: 8

                    Repeater {
                        model: ConfigService.barRight
                        Loader {
                            required property var modelData
                            sourceComponent: root.getModuleComponent(modelData)
                            Layout.alignment: Qt.AlignHCenter
                            Layout.fillWidth: true
                            onLoaded: {
                                if (item && item.hasOwnProperty("barWindowRef")) item.barWindowRef = barWindow;
                                if (item && item.hasOwnProperty("surfaceEdge")) item.surfaceEdge = barWindow.edge;
                            }
                        }
                    }
                }
            }
        }
    }
}
