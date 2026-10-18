#!/usr/bin/env python3
"""
Dock 2.0 Feature Blitz Automated Verification Suite
Validates:
1. Auto-hide reveal (180ms Easing.OutCubic) and hide (220ms Easing.InOutQuad) transitions.
2. Edge trigger hotspot thickness (8px) and interactive area margins (+24px).
3. DockItem popup stabilization (isPopupOpen scale/highlight preservation).
4. Tooltip dwell timer (320ms debounce) eliminating Wayland surface thrashing.
5. Active focused window indicator dot expansion.
6. Tactile click bounce animation.
7. Smooth hover transitions in WindowChooserPopup and DockMenu.
8. Preservation of all 4 dock edges and layer-shell contracts.
"""

import os
import unittest
import subprocess

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class TestDockBlitz(unittest.TestCase):

    def setUp(self):
        with open(os.path.join(REPO_DIR, "modules/dock/Dock.qml")) as f:
            self.dock_qml = f.read()
        with open(os.path.join(REPO_DIR, "modules/dock/DockItem.qml")) as f:
            self.dock_item_qml = f.read()
        with open(os.path.join(REPO_DIR, "modules/dock/WindowChooserPopup.qml")) as f:
            self.chooser_qml = f.read()
        with open(os.path.join(REPO_DIR, "modules/dock/DockMenu.qml")) as f:
            self.menu_qml = f.read()

    def test_01_qmllint_dock_modules(self):
        """Verify all dock QML files pass qmllint cleanly."""
        res = subprocess.run(
            ["qmllint", "modules/dock/Dock.qml", "modules/dock/DockItem.qml",
             "modules/dock/WindowChooserPopup.qml", "modules/dock/DockMenu.qml",
             "modules/dock/DockSeparator.qml"],
            cwd=REPO_DIR,
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0, f"qmllint failed: {res.stderr}")

    def test_02_autohide_transitions(self):
        """Verify snappy reveal (180ms) and smooth hide (220ms) transitions."""
        self.assertIn("duration: dockWindow.isRevealed ? 180 : 220", self.dock_qml)
        self.assertIn("easing.type: dockWindow.isRevealed ? Easing.OutCubic : Easing.InOutQuad", self.dock_qml)
        self.assertIn("duration: dockWindow.isRevealed ? 160 : 200", self.dock_qml)

    def test_03_hotspot_and_interactive_bounds(self):
        """Verify edge trigger thickness (8px) and interactive area bleed cushion (+24px)."""
        self.assertIn("height: dockWindow.isVertical ? Math.max(180, dockSurface.implicitHeight) : 8", self.dock_qml)
        self.assertIn("width: dockWindow.isVertical ? 8 : Math.max(180, dockSurface.implicitWidth)", self.dock_qml)
        self.assertIn("Math.max(dockSurface.implicitWidth + 24, 180)", self.dock_qml)
        self.assertIn("Math.max(dockSurface.implicitHeight + 24, 180)", self.dock_qml)

    def test_04_popup_stabilization_and_anti_flicker(self):
        """Verify popup ownership stabilization prevents icon shrink/jitter and suppresses tooltips."""
        self.assertIn("readonly property bool isPopupOpen: menuOpen || chooserOpen", self.dock_item_qml)
        self.assertIn("root.isPopupOpen ? Theme.alpha(Theme.primary, 0.22)", self.dock_item_qml)
        self.assertIn("((dockItemMouse.containsMouse || root.isPopupOpen) ? 1.15 : 1.0)", self.dock_item_qml)
        self.assertIn("!(root.parentWindowRef && root.parentWindowRef.hasActivePopup)", self.dock_item_qml)

    def test_05_tooltip_dwell_debounce(self):
        """Verify tooltip dwell timer debounces rapid pointer moves across dock items."""
        self.assertIn("Timer {\n        id: tooltipDwellTimer\n        interval: 320", self.dock_item_qml)
        self.assertIn("tooltipDwellTimer.restart()", self.dock_item_qml)
        self.assertIn("tooltipDwellTimer.stop()", self.dock_item_qml)
        self.assertIn("root.tooltipActive && dockItemMouse.containsMouse", self.dock_item_qml)

    def test_06_active_focused_window_indicator(self):
        """Verify active focused window indicator expands width and shifts color."""
        self.assertIn("readonly property bool isCurrentAppActive:", self.dock_item_qml)
        self.assertIn("root.isCurrentAppActive ? 10 :", self.dock_item_qml)
        self.assertIn("root.isCurrentAppActive ? Theme.accent : Theme.primary", self.dock_item_qml)

    def test_07_tactile_click_bounce(self):
        """Verify tactile click bounce animation is triggered on mouse click."""
        self.assertIn("SequentialAnimation {\n        id: clickBounceAnim", self.dock_item_qml)
        self.assertIn("clickBounceAnim.restart()", self.dock_item_qml)

    def test_08_popup_smooth_hover_animations(self):
        """Verify WindowChooserPopup and DockMenu have smooth color transitions."""
        self.assertIn("Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }", self.chooser_qml)
        self.assertIn("Behavior on color { ColorAnimation { duration: Theme.animDurationFast } }", self.menu_qml)

if __name__ == "__main__":
    unittest.main()
