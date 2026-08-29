import QtQuick
import QtQuick.Layouts
import "../../services"
import "../../components"

Surface {
    id: root

    readonly property var activeDisplay: BrightnessService.lastChangedDisplay || BrightnessService.controlledDisplay
    readonly property string displayLabel: activeDisplay ? activeDisplay.label : "Brightness"
    readonly property real displayRatio: (activeDisplay && activeDisplay.ratio !== undefined) ? activeDisplay.ratio : (BrightnessService.brightness || 0.0)
    readonly property int displayPercentage: Math.round(displayRatio * 100)
    readonly property bool isInternal: activeDisplay ? activeDisplay.isInternal : true

    implicitWidth: Math.max(220, Math.min(340, 140 + displayLabel.length * 7))
    implicitHeight: 64
    radius: Theme.radiusLarge
    color: Theme.alpha(Theme.card, 0.95)
    border.color: Theme.border
    border.width: 1

    readonly property string iconName: {
        if (displayRatio > 0.66) return "display-brightness-high";
        if (displayRatio > 0.33) return "display-brightness-medium";
        if (displayRatio > 0.0) return "display-brightness-low";
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
                spacing: 8

                Text {
                    text: root.displayLabel
                    color: Theme.foreground
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                    font.bold: true
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                Text {
                    text: root.displayPercentage + "%"
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
                    width: Math.min(parent.width, parent.width * root.displayRatio)
                    radius: 3
                    color: Theme.warning
                }
            }
        }
    }
}
