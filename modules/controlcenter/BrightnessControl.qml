import QtQuick
import QtQuick.Layouts
import "../../services"
import "../../components"

Surface {
    id: root

    property bool showWhenUnsupported: true

    visible: BrightnessService.supported || showWhenUnsupported
    Layout.fillWidth: true
    implicitHeight: mainLayout.implicitHeight + 20
    radius: Theme.radiusMedium
    color: Theme.alpha(Theme.surface, 0.7)
    border.color: Theme.alpha(Theme.border, 0.6)

    ColumnLayout {
        id: mainLayout
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        // Header
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            SvgIcon {
                icon: "display-brightness-high"
                size: 16
                color: BrightnessService.supported ? Theme.warning : Theme.foregroundMuted
            }

            Text {
                text: "Brightness"
                color: Theme.foreground
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                font.bold: true
            }

            Text {
                text: BrightnessService.controlledDisplayName ? ("• " + BrightnessService.controlledDisplayName) : ""
                color: Theme.foregroundMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall - 1
                elide: Text.ElideRight
                Layout.fillWidth: true
                visible: BrightnessService.controlledDisplayName.length > 0
            }

            Item {
                Layout.fillWidth: true
                visible: !BrightnessService.controlledDisplayName || BrightnessService.controlledDisplayName.length === 0
            }

            IconButton {
                size: 24
                icon: "preferences-system"
                iconSize: 14
                tooltip: "Display Settings"
                onClicked: KWinService.toggleKdeSettings("kcm_kscreen")
            }
        }

        // State 1: Unsupported
        RowLayout {
            visible: !BrightnessService.supported
            Layout.fillWidth: true
            spacing: 8

            Text {
                text: "Backlight control unavailable on this display"
                color: Theme.foregroundMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                Layout.fillWidth: true
            }

            Badge {
                text: "Unsupported"
                color: Theme.foregroundMuted
            }
        }

        // State 2: Multiple detected displays
        ColumnLayout {
            visible: BrightnessService.supported && BrightnessService.displays && BrightnessService.displays.length > 1
            Layout.fillWidth: true
            spacing: 8

            Repeater {
                model: BrightnessService.displays

                ColumnLayout {
                    id: dispItem
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 4

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        Text {
                            text: dispItem.modelData.label || dispItem.modelData.dbusName
                            color: Theme.foreground
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSizeSmall - 1
                            font.bold: true
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }

                        Badge {
                            text: dispItem.modelData.isInternal ? "Internal" : "External"
                            color: dispItem.modelData.isInternal ? Theme.primary : Theme.accent
                        }

                        Text {
                            text: Math.round((dispItem.modelData.maxBrightness > 0 ? (dispItem.modelData.brightness / dispItem.modelData.maxBrightness) : 0) * 100) + "%"
                            color: Theme.foregroundMuted
                            font.family: Theme.fontFamilyMono
                            font.pixelSize: Theme.fontSizeSmall
                            font.bold: true
                            Layout.preferredWidth: 38
                            horizontalAlignment: Text.AlignRight
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        SvgIcon {
                            icon: dispItem.modelData.isInternal ? "video-display-brightness" : "video-display"
                            size: 16
                            color: Theme.warning
                        }

                        Slider {
                            Layout.fillWidth: true
                            value: dispItem.modelData.maxBrightness > 0 ? (dispItem.modelData.brightness / dispItem.modelData.maxBrightness) : 0.0
                            minimumValue: 0.0
                            maximumValue: 1.0
                            stepSize: 0.02
                            progressColor: Theme.warning
                            onValueModified: val => BrightnessService.setBrightnessForDisplay(dispItem.modelData.dbusName, val)
                        }
                    }
                }
            }
        }

        // State 3: Single display or fallback display
        ColumnLayout {
            visible: BrightnessService.supported && (!BrightnessService.displays || BrightnessService.displays.length <= 1)
            Layout.fillWidth: true
            spacing: 6

            // Read-Only Sysfs Notice
            RowLayout {
                visible: BrightnessService.isReadOnly
                Layout.fillWidth: true
                spacing: 8

                Badge {
                    text: "Telemetry Only"
                    color: Theme.foregroundMuted
                }

                Text {
                    text: "Backlight write control unavailable without KDE ScreenBrightness service"
                    color: Theme.foregroundMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: 10
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
            }

            // Slider or static bar
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                SvgIcon {
                    icon: "video-display-brightness"
                    size: 16
                    color: Theme.warning
                }

                // Interactive slider
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

                // Static progress bar if read-only
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
                    text: BrightnessService.percentage + "%"
                    color: Theme.foregroundMuted
                    font.family: Theme.fontFamilyMono
                    font.pixelSize: Theme.fontSizeSmall
                    font.bold: true
                    Layout.preferredWidth: 38
                    horizontalAlignment: Text.AlignRight
                }
            }
        }
    }
}
