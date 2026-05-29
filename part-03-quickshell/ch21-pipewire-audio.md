# Chapter 21 — Audio with PipeWire

## Overview
The Quickshell.Services.Pipewire module gives direct access to the PipeWire audio
graph, enabling volume controls, device indicators, and audio routing widgets.

## Sections

### 21.1 PipeWire Architecture Primer
- PipeWire as the universal audio/video graph
- Nodes, ports, and links
- Session management: WirePlumber
- PipeWire vs. PulseAudio API compatibility

### 21.2 PwNode — Audio Nodes
```qml
import Quickshell.Services.Pipewire

Repeater {
    model: PipeWire.nodes
    Text { text: modelData.name + " vol: " + modelData.audio.volume }
}
```
- Node properties: `id`, `name`, `description`, `type` (sink/source/stream)
- `PwNodeAudio`: volume, mute, channel count, peak levels
- `PwNode.running`: whether the node is active

### 21.3 Default Sink and Source
```qml
Text {
    text: "Volume: " + Math.round(PipeWire.defaultAudioSink.audio.volume * 100) + "%"
}

MouseArea {
    onWheel: event => {
        const vol = PipeWire.defaultAudioSink.audio.volume
        PipeWire.defaultAudioSink.audio.volume = Math.max(0, Math.min(1, vol + event.angleDelta.y / 1200))
    }
}
```
- `PipeWire.defaultAudioSink`: the system default output
- `PipeWire.defaultAudioSource`: microphone/input
- Setting volume: direct property assignment
- Mute toggle: `node.audio.muted = !node.audio.muted`

### 21.4 PwLink — Audio Routing
- `PwLink`: a connection between two nodes' ports
- `PwLink.output` / `PwLink.input`: connected ports
- Reading the current audio graph
- Use case: routing visualization widget

### 21.5 Audio Level Meters
- `PwNodeAudio.volumeFor(channel)`: per-channel volume
- Peak level monitoring for VU meters
- Smooth animations: QML `Behavior { NumberAnimation {} }`

### 21.6 OSD (On-Screen Display) for Volume
```qml
// Quickshell's OSD triggers automatically on PipeWire changes
// Custom OSD pattern:
Connections {
    target: PipeWire.defaultAudioSink.audio
    onVolumeChanged: showOsd(PipeWire.defaultAudioSink.audio.volume)
}
```
- Auto-OSD pattern: timer-based hide after change
- Animation: slide-in/fade-out
- Multi-screen OSD deployment

### 21.7 Device Enumeration
- Listing all available sinks and sources
- Device switcher widget
- `PipeWire.nodes` filtering by `type`

### 21.8 Microphone Indicator
- Detecting active audio capture streams
- Privacy indicator pattern (similar to browser mic indicator)
