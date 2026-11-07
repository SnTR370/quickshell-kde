import QtQuick
import "../services"

Item {
    id: root

    property real value: 0.5
    property real minimumValue: 0.0
    property real maximumValue: 1.0
    property real stepSize: 0.05
    property color trackColor: Theme.surfaceVariant
    property color progressColor: Theme.primary
    property color handleColor: Theme.foreground
    property real trackHeight: 6
    property real handleSize: 14

    signal valueModified(real newValue)

    implicitWidth: 150
    implicitHeight: 24

    // Internal interaction state.
    //
    // `value` is deliberately never assigned from inside this component: an
    // imperative assignment from QML replaces a consumer's declarative binding
    // (e.g. `value: AudioService.volume`), after which later external updates
    // would no longer move the slider. While the user drives the slider we
    // render `_interactiveValue`; as soon as `value` changes from outside we
    // adopt it and fall back to the declarative value.
    property real _interactiveValue: 0.0
    property bool _userInteracting: false
    readonly property real _displayValue: _userInteracting ? _interactiveValue : value

    onValueChanged: {
        if (_userInteracting) {
            _interactiveValue = value;
            _userInteracting = false;
        }
    }

    function clamp(val) {
        return Math.max(root.minimumValue, Math.min(root.maximumValue, val));
    }

    function beginInteraction(newValue) {
        root._interactiveValue = newValue;
        root._userInteracting = true;
        root.valueModified(newValue);
    }

    // Background track
    Rectangle {
        id: track
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        height: root.trackHeight
        radius: height / 2
        color: root.trackColor

        // Active fill
        Rectangle {
            id: progress
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: Math.max(0, Math.min(parent.width, parent.width * ((root._displayValue - root.minimumValue) / (root.maximumValue - root.minimumValue))))
            radius: parent.radius
            color: root.progressColor
        }
    }

    // Handle
    Rectangle {
        id: handle
        x: progress.width - (width / 2)
        anchors.verticalCenter: parent.verticalCenter
        width: root.handleSize
        height: root.handleSize
        radius: width / 2
        color: root.handleColor
        border.color: Theme.border
        border.width: 1
        scale: sliderMouse.containsMouse || sliderMouse.pressed ? 1.25 : 1.0

        Behavior on scale { NumberAnimation { duration: Theme.animDurationFast } }
    }

    MouseArea {
        id: sliderMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor

        function updateFromMouse(mouseX) {
            const ratio = Math.max(0.0, Math.min(1.0, mouseX / root.width));
            const range = root.maximumValue - root.minimumValue;
            const rawVal = root.minimumValue + (ratio * range);
            const stepped = Math.round(rawVal / root.stepSize) * root.stepSize;
            const finalVal = root.clamp(stepped);
            root.beginInteraction(finalVal);
        }

        onPressed: mouse => updateFromMouse(mouse.x)
        onPositionChanged: mouse => {
            if (pressed) updateFromMouse(mouse.x);
        }
        onWheel: wheel => {
            const delta = wheel.angleDelta.y > 0 ? root.stepSize : -root.stepSize;
            const next = root.clamp(root._displayValue + delta);
            root.beginInteraction(next);
        }
    }
}
