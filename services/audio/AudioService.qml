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

    function triggerNativeVolumeOSD(percent) {
        Quickshell.execDetached(["qdbus6", "org.kde.plasmashell", "/org/kde/osdService", "org.kde.osdService.volumeChanged", String(percent)]);
    }

    function triggerNativeMicOSD(percent) {
        Quickshell.execDetached(["qdbus6", "org.kde.plasmashell", "/org/kde/osdService", "org.kde.osdService.microphoneVolumeChanged", String(percent)]);
    }

    function setVolume(val) {
        const clamped = Math.max(0.0, Math.min(1.5, val));
        if (defaultSink && defaultSink.audio) {
            defaultSink.audio.volume = clamped;
        } else {
            Quickshell.execDetached(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", String(clamped)]);
        }
        triggerNativeVolumeOSD(Math.round(clamped * 100));
    }

    function increaseVolume(step) {
        const delta = step !== undefined ? step : 0.05;
        setVolume(root.volume + delta);
    }

    function decreaseVolume(step) {
        const delta = step !== undefined ? step : 0.05;
        setVolume(root.volume - delta);
    }

    function toggleMute() {
        let isMuted = false;
        if (defaultSink && defaultSink.audio) {
            defaultSink.audio.muted = !defaultSink.audio.muted;
            isMuted = defaultSink.audio.muted;
        } else {
            Quickshell.execDetached(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"]);
            isMuted = !root.muted;
        }
        triggerNativeVolumeOSD(isMuted ? 0 : Math.round(root.volume * 100));
    }

    function toggleInputMute() {
        let isMuted = false;
        if (defaultSource && defaultSource.audio) {
            defaultSource.audio.muted = !defaultSource.audio.muted;
            isMuted = defaultSource.audio.muted;
        } else {
            Quickshell.execDetached(["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle"]);
            isMuted = !root.inputMuted;
        }
        triggerNativeMicOSD(isMuted ? 0 : Math.round(root.inputVolume * 100));
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
