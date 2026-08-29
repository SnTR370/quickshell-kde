pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Services.Pipewire
import "../core/Log.js" as Log

Singleton {
    id: root

    PwObjectTracker {
        objects: [Pipewire.defaultAudioSink, Pipewire.defaultAudioSource]
    }

    readonly property var defaultSink: Pipewire.defaultAudioSink
    readonly property var defaultSource: Pipewire.defaultAudioSource

    readonly property real volume: (defaultSink && defaultSink.audio) ? defaultSink.audio.volume : 0.0
    readonly property bool muted: (defaultSink && defaultSink.audio) ? defaultSink.audio.muted : false
    readonly property string sinkDescription: (defaultSink && defaultSink.description) ? defaultSink.description : "Default Output"

    readonly property real inputVolume: (defaultSource && defaultSource.audio) ? defaultSource.audio.volume : 0.0
    readonly property bool inputMuted: (defaultSource && defaultSource.audio) ? defaultSource.audio.muted : false

    readonly property bool isHeadphone: {
        const desc = sinkDescription.toLowerCase();
        return desc.includes("headphone") || desc.includes("headset") || desc.includes("earphone");
    }

    function triggerNativeVolumeOSD(percent, maxPercent) {
        const max = maxPercent !== undefined ? maxPercent : 150;
        Quickshell.execDetached(["qdbus6", "org.kde.plasmashell", "/org/kde/osdService", "org.kde.osdService.volumeChanged", String(percent), String(max)]);
    }

    function triggerNativeMicOSD(percent) {
        Quickshell.execDetached(["qdbus6", "org.kde.plasmashell", "/org/kde/osdService", "org.kde.osdService.microphoneVolumeChanged", String(percent)]);
    }

    function setVolume(val, showOsd) {
        const clamped = Math.max(0.0, Math.min(1.5, val));
        if (defaultSink && defaultSink.audio) {
            defaultSink.audio.volume = clamped;
        } else {
            Quickshell.execDetached(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", String(clamped)]);
        }
        if (showOsd) {
            triggerNativeVolumeOSD(Math.round(clamped * 100), 150);
        }
    }

    function increaseVolume(step) {
        // Invoke KDE native KMix shortcut for system volume stepping and native 0..150 OSD feedback
        Quickshell.execDetached(["qdbus6", "org.kde.kglobalaccel", "/component/kmix", "org.kde.kglobalaccel.Component.invokeShortcut", "increase_volume"]);
    }

    function decreaseVolume(step) {
        // Invoke KDE native KMix shortcut for system volume stepping and native 0..150 OSD feedback
        Quickshell.execDetached(["qdbus6", "org.kde.kglobalaccel", "/component/kmix", "org.kde.kglobalaccel.Component.invokeShortcut", "decrease_volume"]);
    }

    function toggleMute() {
        Quickshell.execDetached(["qdbus6", "org.kde.kglobalaccel", "/component/kmix", "org.kde.kglobalaccel.Component.invokeShortcut", "mute"]);
    }

    function toggleInputMute() {
        Quickshell.execDetached(["qdbus6", "org.kde.kglobalaccel", "/component/kmix", "org.kde.kglobalaccel.Component.invokeShortcut", "mic_mute"]);
    }

    function setInputVolume(val) {
        const clamped = Math.max(0.0, Math.min(1.0, val));
        if (defaultSource && defaultSource.audio) {
            defaultSource.audio.volume = clamped;
        } else {
            Quickshell.execDetached(["wpctl", "set-volume", "@DEFAULT_AUDIO_SOURCE@", String(clamped)]);
        }
        triggerNativeMicOSD(Math.round(clamped * 100));
    }

    function openVolumeControl() {
        Quickshell.execDetached(["kcmshell6", "kcm_pulseaudio"]);
    }
}
