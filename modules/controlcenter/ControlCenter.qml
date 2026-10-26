import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "../../services"
import "../../components"
import "."

Surface {
    id: root

    property bool embeddedInPopup: false
    property real maxHeight: 0
    signal closeRequested()

    implicitWidth: 360
    readonly property real naturalHeight: headerRow.implicitHeight + mainCol.implicitHeight + 36
    implicitHeight: maxHeight > 0 ? Math.min(naturalHeight, maxHeight) : naturalHeight
    radius: embeddedInPopup ? 0 : Theme.radiusLarge
    color: embeddedInPopup ? "transparent" : Theme.alpha(Theme.background, Theme.popupOpacity)
    border.color: embeddedInPopup ? "transparent" : Theme.alpha(Theme.border, 0.8)
    border.width: embeddedInPopup ? 0 : 1

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 12

        // Top Header Row
        RowLayout {
            id: headerRow
            Layout.fillWidth: true
            spacing: 8

            SvgIcon {
                icon: "configure"
                size: 18
                color: Theme.primary
            }

            Text {
                text: "Control Center"
                color: Theme.foreground
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeMedium
                font.bold: true
                Layout.fillWidth: true
            }

            IconButton {
                size: 24
                icon: "window-close"
                iconSize: 14
                iconColor: Theme.foregroundMuted
                tooltip: "Close"
                onClicked: root.closeRequested()
            }
        }

        ScrollView {
            id: contentScroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

            ColumnLayout {
                id: mainCol
                width: contentScroll.availableWidth
                spacing: 12

                // Quick Settings 2x2 Grid
                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    rowSpacing: 8
                    columnSpacing: 8

                    // 1. Network Tile
                    QuickTile {
                        icon: !NetworkService.connected ? "network-disconnect" : (NetworkService.connectionType === "ethernet" ? "network-wired" : "network-wireless")
                        iconColor: NetworkService.connected ? Theme.primary : Theme.error
                        title: "Network"
                        subtitle: !NetworkService.connected ? "Disconnected" : (NetworkService.connectionType === "ethernet" ? (NetworkService.activeDeviceName || "Ethernet") : (NetworkService.ssid || "Wi-Fi"))
                        active: NetworkService.connected
                        activeColor: Theme.primary
                        badgeText: (NetworkService.connected && NetworkService.signalStrength >= 0) ? (NetworkService.signalStrength + "%") : ""
                        badgeColor: Theme.primary
                        tooltip: "Network Settings (kcm_networkmanagement)"
                        onClicked: {
                            root.closeRequested();
                            NetworkService.openNetworkSettings();
                        }
                    }

                    // 2. Power / Battery Tile
                    QuickTile {
                        icon: PowerService.isCharging ? "battery-charging" : (PowerService.percentage > 0.8 ? "battery-100" : (PowerService.percentage > 0.6 ? "battery-080" : (PowerService.percentage > 0.4 ? "battery-060" : (PowerService.percentage > 0.2 ? "battery-040" : "battery-020"))))
                        iconColor: PowerService.isCharging ? Theme.success : (PowerService.percentage <= 0.2 ? Theme.error : (PowerService.percentage <= 0.4 ? Theme.warning : Theme.foreground))
                        title: PowerService.isPresent ? "Battery" : "Power"
                        subtitle: PowerService.isPresent ? (Math.round(PowerService.percentage * 100) + "% • " + (PowerService.isCharging ? "Charging" : (PowerService.isPluggedIn ? "Full" : "On Battery"))) : "AC Connected"
                        active: PowerService.isCharging
                        activeColor: Theme.success
                        tooltip: "Power Management (kcm_powerdevilprofilesconfig)"
                        onClicked: {
                            root.closeRequested();
                            KWinService.toggleKdeSettings("kcm_powerdevilprofilesconfig");
                        }
                    }

                    // 3. Audio Tile
                    QuickTile {
                        icon: AudioService.isHeadphone ? "audio-headphones" : "audio-speakers"
                        iconColor: AudioService.muted ? Theme.error : Theme.primary
                        title: "Audio"
                        subtitle: AudioService.muted ? "Muted" : (Math.round(AudioService.volume * 100) + "%")
                        active: !AudioService.muted
                        activeColor: Theme.primary
                        tooltip: "Audio Settings (kcm_pulseaudio)"
                        onClicked: {
                            root.closeRequested();
                            AudioService.openVolumeControl();
                        }
                    }

                    // 4. Display Tile
                    QuickTile {
                        icon: "video-display"
                        iconColor: Theme.warning
                        title: "Display"
                        subtitle: BrightnessService.supported ? (BrightnessService.percentage + "%") : "KScreen"
                        active: BrightnessService.supported
                        activeColor: Theme.warning
                        tooltip: "Display Settings (kcm_kscreen)"
                        onClicked: {
                            root.closeRequested();
                            KWinService.toggleKdeSettings("kcm_kscreen");
                        }
                    }
                }

                // Sliders
                VolumeControl {
                    Layout.fillWidth: true
                    onActionTriggered: root.closeRequested()
                }

                BrightnessControl {
                    Layout.fillWidth: true
                    onActionTriggered: root.closeRequested()
                }

                // Media Widget (Dynamic MPRIS player)
                MediaControl {
                    Layout.fillWidth: true
                }

                // Footer Separator
                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: Theme.alpha(Theme.border, 0.4)
                }

                // Session and Power Controls
                SessionRow {
                    Layout.fillWidth: true
                    onActionTriggered: root.closeRequested()
                }
            }
        }
    }
}
