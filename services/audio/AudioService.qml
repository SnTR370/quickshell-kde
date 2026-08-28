pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Services.Pipewire
import "../core/Log.js" as Log

Singleton {
    id: root

    signal osdPulse()

    PwObjectTracker {
        objects: [Pipewire.defaultAudioSink, Pipewire.defaultAudioSource]
    }

    readonly property var defaultSink: Pipewire.defaultAudioSink
    readonly property var defaultSource: Pipewire.defaultAudioSource

    property real volume: (defaultSink && defaultSink.audio) ? defaultSink.audio.volume : 0.5
    property bool muted: (defaultSink && defaultSink.audio) ? defaultSink.audio.muted : false
    property string sinkDescription: (defaultSink && defaultSink.description) ? defaultSink.description : "Default Output"

    property real inputVolume: (defaultSource && defaultSource.audio) ? defaultSource.audio.volume : 0.5
    property bool inputMuted: (defaultSource && defaultSource.audio) ? defaultSource.audio.muted : false

    property bool isHeadphone: {
        const desc = sinkDescription.toLowerCase();
        return desc.includes("headphone") || desc.includes("headset") || desc.includes("earphone");
    }

    function setVolume(val) {
        const clamped = Math.max(0.0, Math.min(1.5, val));
        if (defaultSink && defaultSink.audio) {
            defaultSink.audio.volume = clamped;
            root.volume = clamped;
        } else {
            Quickshell.execDetached(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", String(clamped)]);
        }
        root.osdPulse();
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
        if (defaultSink && defaultSink.audio) {
            defaultSink.audio.muted = !defaultSink.audio.muted;
            root.muted = defaultSink.audio.muted;
        } else {
            Quickshell.execDetached(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"]);
        }
        root.osdPulse();
    }

    function toggleInputMute() {
        if (defaultSource && defaultSource.audio) {
            defaultSource.audio.muted = !defaultSource.audio.muted;
            root.inputMuted = defaultSource.audio.muted;
        } else {
            Quickshell.execDetached(["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle"]);
        }
    }

    function openVolumeControl() {
        Quickshell.execDetached(["kcmshell6", "kcm_pulseaudio"]);
    }
}
