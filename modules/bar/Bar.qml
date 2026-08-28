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

    PanelWindow {
        id: barWindow
        required property var modelData

        screen: modelData
        color: "transparent"

        anchors {
            top: ConfigService.barPosition === "top"
            bottom: ConfigService.barPosition === "bottom"
            left: ConfigService.barPosition !== "right"
            right: ConfigService.barPosition !== "left"
        }

        readonly property bool isVertical: ConfigService.barPosition === "left" || ConfigService.barPosition === "right"
        implicitHeight: isVertical ? -1 : ConfigService.barHeight
        implicitWidth: isVertical ? ConfigService.barHeight : -1
        exclusiveZone: ConfigService.barHeight

        WlrLayershell.layer: WlrLayer.Top

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

                    LauncherButton {}
                    WorkspacesModule {}
                }

                // Center Section (Expanding space to center the clock)
                Item { Layout.fillWidth: true }

                ClockModule {
                    Layout.alignment: Qt.AlignHCenter | Qt.AlignVCenter
                }

                Item { Layout.fillWidth: true }

                // Right Section
                RowLayout {
                    Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                    spacing: 8

                    MediaModule {}
                    TrayModule {}
                    NetworkModule {}
                    BatteryModule {}
                    AudioModule {}
                    PowerButton {}
                }
            }

            // Vertical Bar Layout
            ColumnLayout {
                visible: barWindow.isVertical
                anchors.fill: parent
                anchors.topMargin: 8
                anchors.bottomMargin: 8
                spacing: 8

                LauncherButton {
                    Layout.alignment: Qt.AlignHCenter
                }

                WorkspacesModule {
                    Layout.alignment: Qt.AlignHCenter
                }

                Item { Layout.fillHeight: true }

                ClockModule {
                    Layout.alignment: Qt.AlignHCenter
                }

                Item { Layout.fillHeight: true }

                AudioModule {
                    Layout.alignment: Qt.AlignHCenter
                }

                PowerButton {
                    Layout.alignment: Qt.AlignHCenter
                }
            }
        }
    }
}
