import QtQuick
import QtQuick.Layouts
import "../services"
import "."

Surface {
    id: root

    property string title: ""
    property string subtitle: ""
    property string icon: ""
    property bool clickable: false

    signal clicked()

    implicitWidth: 240
    implicitHeight: layout.implicitHeight + 20

    ColumnLayout {
        id: layout
        anchors.fill: parent
        anchors.margins: 10
        spacing: 6

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            SvgIcon {
                icon: root.icon
                size: 24
                visible: root.icon.length > 0
                Layout.alignment: Qt.AlignVCenter
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                Text {
                    text: root.title
                    color: Theme.foreground
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeMedium
                    font.bold: true
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                    visible: root.title.length > 0
                }

                Text {
                    text: root.subtitle
                    color: Theme.foregroundMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeSmall
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                    visible: root.subtitle.length > 0
                }
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        enabled: root.clickable
        cursorShape: root.clickable ? Qt.PointingHandCursor : Qt.ArrowCursor
        hoverEnabled: true
        onClicked: root.clicked()
    }
}
