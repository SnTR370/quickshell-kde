import QtQuick
import QtQuick.Layouts
import Quickshell
import "../../services"
import "../../components"

AnchoredPopup {
    id: root

    implicitWidth: 300
    implicitHeight: popupLayout.implicitHeight + 16

    ColumnLayout {
        id: popupLayout
        anchors.fill: parent
        anchors.margins: 12
        spacing: 12

        // Header
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            SvgIcon {
                icon: "display-brightness-high"
                size: 20
                color: Theme.warning
            }

            Text {
                text: "Display Brightness"
                color: Theme.foreground
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                font.bold: true
                Layout.fillWidth: true
            }

            IconButton {
                size: 28
                icon: "preferences-system"
                iconSize: 16
                tooltip: "Display Settings"
                onClicked: {
                    Quickshell.execDetached(["kcmshell6", "kcm_kscreen"]);
                    root.close();
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.border
            opacity: 0.5
        }

        // List of Valid Connected Displays
        Repeater {
            model: BrightnessService.displays

            ColumnLayout {
                id: displayRow
                required property var modelData
                Layout.fillWidth: true
                spacing: 6

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    SvgIcon {
                        icon: displayRow.modelData.isInternal ? "video-display-brightness" : "video-display"
                        size: 16
                        color: Theme.warning
                    }

                    Text {
                        text: displayRow.modelData.label || displayRow.modelData.dbusName
                        color: Theme.foreground
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                        font.bold: true
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    Badge {
                        text: displayRow.modelData.isInternal ? "Internal" : "External"
                        color: displayRow.modelData.isInternal ? Theme.primary : Theme.accent
                    }

                    Text {
                        text: Math.round((displayRow.modelData.maxBrightness > 0 ? (displayRow.modelData.brightness / displayRow.modelData.maxBrightness) : 0) * 100) + "%"
                        color: Theme.foregroundMuted
                        font.family: Theme.fontFamilyMono
                        font.pixelSize: Theme.fontSizeSmall
                        font.bold: true
                        Layout.preferredWidth: 38
                        horizontalAlignment: Text.AlignRight
                    }
                }

                Slider {
                    Layout.fillWidth: true
                    value: displayRow.modelData.maxBrightness > 0 ? (displayRow.modelData.brightness / displayRow.modelData.maxBrightness) : 0.0
                    minimumValue: 0.0
                    maximumValue: 1.0
                    stepSize: 0.02
                    progressColor: Theme.warning
                    onValueModified: val => BrightnessService.setBrightnessForDisplay(displayRow.modelData.dbusName, val)
                }
            }
        }

        // Fallback if no dynamic displays detected
        ColumnLayout {
            visible: !BrightnessService.displays || BrightnessService.displays.length === 0
            Layout.fillWidth: true
            spacing: 6

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                SvgIcon {
                    icon: "video-display-brightness"
                    size: 16
                    color: Theme.warning
                }

                Badge {
                    visible: BrightnessService.isReadOnly
                    text: "Telemetry Only"
                    badgeColor: Theme.foregroundMuted
                }

                Text {
                    text: BrightnessService.percentage + "%"
                    color: Theme.foregroundMuted
                    font.family: Theme.fontFamilyMono
                    font.pixelSize: Theme.fontSizeSmall
                    font.bold: true
                }
            }

            // Static non-interactive bar for read-only mode
            Rectangle {
                visible: BrightnessService.isReadOnly
                Layout.fillWidth: true
                implicitHeight: 6
                radius: 3
                color: Theme.surfaceVariant

                Rectangle {
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: Math.min(parent.width, parent.width * BrightnessService.brightness)
                    radius: 3
                    color: Theme.foregroundMuted
                }
            }

            Text {
                visible: BrightnessService.isReadOnly
                text: "Backlight write controls unavailable without KDE ScreenBrightness D-Bus service"
                color: Theme.foregroundMuted
                font.family: Theme.fontFamily
                font.pixelSize: 10
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }

            // Interactive slider only when writable
            Slider {
                visible: !BrightnessService.isReadOnly
                Layout.fillWidth: true
                value: BrightnessService.brightness
                minimumValue: 0.0
                maximumValue: 1.0
                stepSize: 0.02
                progressColor: Theme.warning
                onValueModified: val => BrightnessService.setBrightness(val)
            }
        }
    }
}
