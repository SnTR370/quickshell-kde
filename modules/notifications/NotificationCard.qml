import QtQuick
import QtQuick.Layouts
import "../../services"
import "../../components"

Surface {
    id: root

    property var notification: null
    signal dismissed(var id)

    implicitWidth: 320
    implicitHeight: layout.implicitHeight + 20
    radius: Theme.radiusMedium
    color: Theme.alpha(Theme.card, 0.95)
    border.color: root.notification && root.notification.urgency === 2 ? Theme.error : Theme.border
    border.width: 1

    Timer {
        id: autoDismissTimer
        interval: 5000
        running: true
        repeat: false
        onTriggered: {
            if (root.notification) {
                root.dismissed(root.notification.id);
            }
        }
    }

    ColumnLayout {
        id: layout
        anchors.fill: parent
        anchors.margins: 12
        spacing: 8

        // Header: App icon, name, and dismiss button
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            SvgIcon {
                icon: (root.notification && root.notification.appIcon) ? root.notification.appIcon : "dialog-information"
                size: 20
            }

            Text {
                text: (root.notification && root.notification.appName) ? root.notification.appName : "Notification"
                color: Theme.foregroundMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeSmall
                font.bold: true
                elide: Text.ElideRight
                Layout.fillWidth: true
            }

            IconButton {
                size: 20
                icon: "window-close"
                iconColor: Theme.foregroundMuted
                onClicked: {
                    if (root.notification) {
                        root.dismissed(root.notification.id);
                    }
                }
            }
        }

        // Summary Title
        Text {
            text: (root.notification && root.notification.summary) ? root.notification.summary : ""
            color: Theme.foreground
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeMedium
            font.bold: true
            wrapMode: Text.Wrap
            Layout.fillWidth: true
            visible: text.length > 0
        }

        // Body Text
        Text {
            text: (root.notification && root.notification.body) ? root.notification.body : ""
            color: Theme.foregroundMuted
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSizeSmall
            wrapMode: Text.Wrap
            maximumLineCount: 3
            elide: Text.ElideRight
            Layout.fillWidth: true
            visible: text.length > 0
        }

        // Action buttons
        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            visible: root.notification && root.notification.actions && root.notification.actions.length > 0

            Repeater {
                model: (root.notification && root.notification.actions) ? root.notification.actions : []

                Rectangle {
                    id: actBtn
                    required property var modelData
                    implicitHeight: 24
                    implicitWidth: actLabel.implicitWidth + 16
                    radius: Theme.radiusSmall
                    color: actMouse.containsMouse ? Theme.hover : Theme.surfaceVariant

                    Text {
                        id: actLabel
                        anchors.centerIn: parent
                        text: actBtn.modelData.text || actBtn.modelData.identifier || "Action"
                        color: Theme.foreground
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSizeSmall
                    }

                    MouseArea {
                        id: actMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            actBtn.modelData.invoke();
                            root.dismissed(root.notification.id);
                        }
                    }
                }
            }
        }
    }
}
