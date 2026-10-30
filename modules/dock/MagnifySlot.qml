import QtQuick
import "../../services"

// DOCK-004: transparent layout slot that can be laterally displaced by the
// dock's pointer-driven magnification. Used for the launcher/settings
// IconButtons, which are shared components without dock-specific properties.
// The displacement is a transform on the whole slot (hit areas included), so
// the underlying layout geometry - the rest positions the magnification math
// measures against - never changes.
Item {
    id: root

    // Owning dock window; mirrors its edge so the displacement follows the
    // layout axis (x for horizontal edges, y for vertical edges).
    property var dockWindowRef: null
    // Target displacement along the layout axis, set by Dock.qml's controller.
    property real magnifiedOffset: 0
    readonly property bool isVerticalDock: root.dockWindowRef && root.dockWindowRef.isVertical !== undefined
        ? root.dockWindowRef.isVertical
        : false
    // Currently applied (Behavior-animated) displacement, so the controller
    // can subtract it when measuring rest centers.
    readonly property real appliedMagnifiedOffset: root.isVerticalDock ? slotTranslate.y : slotTranslate.x

    default property alias contentData: root.data

    implicitWidth: childrenRect.width
    implicitHeight: childrenRect.height

    transform: Translate {
        id: slotTranslate
        x: root.isVerticalDock ? 0 : root.magnifiedOffset
        y: root.isVerticalDock ? root.magnifiedOffset : 0
        Behavior on x {
            NumberAnimation {
                duration: Theme.animDurationFast
                easing.type: Theme.animEasing
            }
        }
        Behavior on y {
            NumberAnimation {
                duration: Theme.animDurationFast
                easing.type: Theme.animEasing
            }
        }
    }
}
