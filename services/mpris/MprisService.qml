pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Services.Mpris
import "../core/Log.js" as Log

Singleton {
    id: root

    readonly property var players: Mpris.players ? Mpris.players.values : []
    readonly property int playerCount: players ? players.length : 0
    readonly property bool hasPlayers: playerCount > 0

    // Active player resolution (prefers currently playing player, otherwise first player)
    readonly property var activePlayer: {
        if (!players || players.length === 0) return null;
        for (let i = 0; i < players.length; i++) {
            if (players[i] && players[i].playbackState === MprisPlaybackState.Playing) {
                return players[i];
            }
        }
        return players[0];
    }

    readonly property bool isPlaying: activePlayer ? (activePlayer.playbackState === MprisPlaybackState.Playing) : false
    readonly property string trackTitle: activePlayer ? (activePlayer.trackTitle || "Unknown Track") : ""
    readonly property string trackArtist: {
        if (!activePlayer) return "";
        if (activePlayer.trackArtists && activePlayer.trackArtists.length > 0) {
            return activePlayer.trackArtists.join(", ");
        }
        return activePlayer.trackArtist || "";
    }
    readonly property string trackArtUrl: activePlayer ? (activePlayer.trackArtUrl || "") : ""
    readonly property real trackLength: activePlayer ? (activePlayer.length || 0) : 0
    readonly property real trackPosition: activePlayer ? (activePlayer.position || 0) : 0
    readonly property bool canGoNext: activePlayer ? activePlayer.canGoNext : false
    readonly property bool canGoPrevious: activePlayer ? activePlayer.canGoPrevious : false
    readonly property bool canControl: activePlayer ? activePlayer.canControl : false
    readonly property string playerIdentity: activePlayer ? (activePlayer.identity || "Media Player") : ""

    function playPause() {
        if (activePlayer) {
            activePlayer.togglePlaying();
        }
    }

    function next() {
        if (activePlayer && activePlayer.canGoNext) {
            activePlayer.next();
        }
    }

    function previous() {
        if (activePlayer && activePlayer.canGoPrevious) {
            activePlayer.previous();
        }
    }

    function seek(position) {
        if (activePlayer && activePlayer.canSeek) {
            activePlayer.position = position;
        }
    }
}
