import QtQuick
import QtQuick.Layouts
import "../../services"
import "../../components"

Surface {
    id: root

    implicitWidth: 220
    implicitHeight: 64
    radius: Theme.radiusLarge
    color: Theme.alpha(Theme.card, 0.95)
    border.color: Theme.border
    border.width: 1

    readonly property string iconName: {
        if (BrightnessService.brightness > 0.66) return "display-brightness-high";
        if (BrightnessService.brightness > 0.33) return "display-brightness-medium";
        if (BrightnessService.brightness > 0.0) return "display-brightness-low";
        return "display-brightness-off";
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 12

        SvgIcon {
            icon: root.iconName
            size: 28
            color: Theme.warning
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4

            RowLayout {
                Layout.fillWidth: true

                Text {
                    text: "Brightness"
                    color: Theme.foreground
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                    font.bold: true
                }

                Item { Layout.fillWidth: true }

                Text {
                    text: BrightnessService.percentage + "%"
                    color: Theme.foregroundMuted
                    font.family: Theme.fontFamilyMono
                    font.pixelSize: Theme.fontSizeSmall
                }
            }

            Rectangle {
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
                    color: Theme.warning
                }
            }
        }
    }
}
