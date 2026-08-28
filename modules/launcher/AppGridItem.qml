import QtQuick
import QtQuick.Layouts
import "../../services"
import "../../components"

Item {
    id: root

    property var app: null
    property bool isSelected: false

    signal launched()

    implicitWidth: 100
    implicitHeight: 105

    Rectangle {
        id: bgRect
        anchors.fill: parent
        radius: Theme.radiusMedium
        color: root.isSelected ? Theme.primary : (appMouse.containsMouse ? Theme.hover : "transparent")
        scale: appMouse.pressed ? 0.95 : (appMouse.containsMouse ? 1.05 : 1.0)

        Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }
        Behavior on scale { NumberAnimation { duration: Theme.animDurationFast; easing.type: Easing.OutBack } }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 8
            spacing: 6

            SvgIcon {
                icon: (root.app && root.app.icon) ? root.app.icon : "application-x-executable"
                size: 44
                Layout.alignment: Qt.AlignHCenter
            }

            Text {
                text: (root.app && root.app.name) ? root.app.name : ""
                color: root.isSelected ? Theme.contrastColor(Theme.primary) : Theme.foreground
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
                Layout.fillWidth: true
                maximumLineCount: 2
                wrapMode: Text.Wrap
            }
        }
    }

    Tooltip {
        text: (root.app && root.app.comment) ? root.app.comment : (root.app ? root.app.name : "")
        show: (root.app && root.app.comment && root.app.comment.length > 0) && appMouse.containsMouse && !appMouse.pressed
    }

    MouseArea {
        id: appMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton

        onClicked: mouse => {
            if (mouse.button === Qt.RightButton) {
                if (root.app) ApplicationService.togglePin(root.app.id);
            } else {
                if (root.app) {
                    ApplicationService.launch(root.app);
                    root.launched();
                }
            }
        }
    }
}
