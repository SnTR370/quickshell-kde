import QtQuick
import QtTest
import "."

TestCase {
    id: root
    name: "ControlCenterModuleTest"
    width: 600
    height: 800
    visible: true

    Component {
        id: quickTileComp
        QuickTile {
            title: "Test Tile"
            subtitle: "Test Subtitle"
            icon: "network-wireless"
            active: true
        }
    }

    Component {
        id: sessionRowComp
        SessionRow {}
    }

    Component {
        id: volumeControlComp
        VolumeControl {}
    }

    Component {
        id: brightnessControlComp
        BrightnessControl {}
    }

    Component {
        id: mediaControlComp
        MediaControl {}
    }

    Component {
        id: controlCenterComp
        ControlCenter {}
    }

    function test_01_quicktile_instantiation() {
        const tile = createTemporaryObject(quickTileComp, null, {
            title: "Wi-Fi",
            subtitle: "Connected",
            active: true
        });
        verify(tile !== null, "QuickTile component instantiated");
        compare(tile.title, "Wi-Fi", "QuickTile title matches");
        compare(tile.subtitle, "Connected", "QuickTile subtitle matches");
        compare(tile.active, true, "QuickTile active state matches");

        let clickedFired = false;
        tile.clicked.connect(function() {
            clickedFired = true;
        });
        tile.clicked();
        compare(clickedFired, true, "QuickTile emits clicked signal");
    }

    function test_02_session_row_signals() {
        const row = createTemporaryObject(sessionRowComp, null);
        verify(row !== null, "SessionRow component instantiated");

        let actionFired = false;
        row.actionTriggered.connect(function() {
            actionFired = true;
        });
        row.actionTriggered();
        compare(actionFired, true, "SessionRow emits actionTriggered signal");
    }

    function test_03_volume_control_structure() {
        const vol = createTemporaryObject(volumeControlComp, null);
        verify(vol !== null, "VolumeControl component instantiated");
        verify(vol.implicitHeight > 0, "VolumeControl has valid implicit height");
    }

    function test_04_brightness_control_structure() {
        const bright = createTemporaryObject(brightnessControlComp, null);
        verify(bright !== null, "BrightnessControl component instantiated");
        verify(bright.implicitHeight > 0, "BrightnessControl has valid implicit height");
    }

    function test_05_media_control_structure() {
        const media = createTemporaryObject(mediaControlComp, null);
        verify(media !== null, "MediaControl component instantiated");
    }

    function test_06_controlcenter_instantiation_and_signals() {
        const cc = createTemporaryObject(controlCenterComp, null);
        verify(cc !== null, "ControlCenter component instantiated");
        compare(cc.implicitWidth, 360, "ControlCenter has compact width suitable for desktop popup");
        verify(cc.implicitHeight > 200, "ControlCenter has responsive height");

        let closeFired = false;
        cc.closeRequested.connect(function() {
            closeFired = true;
        });
        cc.closeRequested();
        compare(closeFired, true, "ControlCenter emits closeRequested signal");
    }
}
