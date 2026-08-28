pragma Singleton
import QtQuick
import Quickshell

Singleton {
    id: root

    // Theme identification
    property string activeThemeId: "breeze-dark"

    // Colors
    property color background: "#232629"
    property color surface: "#31363b"
    property color surfaceVariant: "#3a4047"
    property color primary: "#3daee9"
    property color primaryText: "#ffffff"
    property color secondary: "#2980b9"
    property color accent: "#1d99f3"
    property color foreground: "#eff0f1"
    property color foregroundMuted: "#bdc3c7"
    property color border: "#474e54"
    property color card: "#2a2e32"
    property color hover: "#3f464c"
    property color active: "#3daee9"
    property color success: "#27ae60"
    property color warning: "#f67400"
    property color error: "#da4453"
    property color info: "#3daee9"

    // Geometry / Radii
    property real radiusSmall: 6
    property real radiusMedium: 12
    property real radiusLarge: 18
    property real radiusFull: 9999

    // Spacing & Sizes
    property real barHeight: 44
    property real dockIconSize: 44
    property real spacingSmall: 6
    property real spacingMedium: 10
    property real spacingLarge: 16
    property real paddingSmall: 6
    property real paddingMedium: 10
    property real paddingLarge: 16

    // Transparency / Blur
    property real barOpacity: 0.88
    property real dockOpacity: 0.90
    property real popupOpacity: 0.95
    property bool blurEnabled: true

    // Typography
    property string fontFamily: "Noto Sans, sans-serif"
    property string fontFamilyMono: "Hack, monospace"
    property int fontSizeSmall: 11
    property int fontSizeMedium: 13
    property int fontSizeLarge: 16
    property int fontSizeHeading: 20

    // Animation Timers & Curves
    property int animDurationFast: 150
    property int animDurationNormal: 250
    property int animDurationSlow: 400

    // Utility functions for color adjustments
    function alpha(c, a) {
        return Qt.rgba(c.r, c.g, c.b, a);
    }

    function lighten(c, amount) {
        return Qt.lighter(c, 1.0 + (amount || 0.1));
    }

    function darken(c, amount) {
        return Qt.darker(c, 1.0 + (amount || 0.1));
    }

    function isDark(c) {
        // Luminance calculation
        return (0.299 * c.r + 0.587 * c.g + 0.114 * c.b) < 0.5;
    }

    function contrastColor(bg) {
        return isDark(bg) ? "#ffffff" : "#111111";
    }

    function applyTheme(data) {
        if (!data) return;
        if (data.id) root.activeThemeId = data.id;
        if (data.background) root.background = data.background;
        if (data.surface) root.surface = data.surface;
        if (data.surfaceVariant) root.surfaceVariant = data.surfaceVariant;
        if (data.primary) root.primary = data.primary;
        if (data.primaryText) root.primaryText = data.primaryText;
        if (data.secondary) root.secondary = data.secondary;
        if (data.accent) root.accent = data.accent;
        if (data.foreground) root.foreground = data.foreground;
        if (data.foregroundMuted) root.foregroundMuted = data.foregroundMuted;
        if (data.border) root.border = data.border;
        if (data.card) root.card = data.card;
        if (data.hover) root.hover = data.hover;
        if (data.active) root.active = data.active;
        if (data.success) root.success = data.success;
        if (data.warning) root.warning = data.warning;
        if (data.error) root.error = data.error;
        if (data.info) root.info = data.info;
        if (data.radiusSmall !== undefined) root.radiusSmall = data.radiusSmall;
        if (data.radiusMedium !== undefined) root.radiusMedium = data.radiusMedium;
        if (data.radiusLarge !== undefined) root.radiusLarge = data.radiusLarge;
        if (data.fontFamily) root.fontFamily = data.fontFamily;
        if (data.fontFamilyMono) root.fontFamilyMono = data.fontFamilyMono;
    }
}
