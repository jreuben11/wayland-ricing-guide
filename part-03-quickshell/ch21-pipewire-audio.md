# Chapter 21 — Audio with PipeWire

## Overview

The `Quickshell.Services.Pipewire` module provides direct, reactive access to the PipeWire audio
graph from within QML. Rather than shelling out to `pactl` or parsing the output of
`wpctl status`, your shell code subscribes to live property changes and receives updates
the moment the graph changes — no polling, no race conditions.

This chapter covers everything from PipeWire's internal object model to complete, production-ready
widgets: volume sliders, per-channel VU meters, device switchers, OSD overlays, and a microphone
privacy indicator. All code in this chapter is copy-paste-ready and tested against Quickshell 0.1.x
with PipeWire 1.x and WirePlumber 0.5.x.

**Prerequisites:** A running PipeWire session with WirePlumber as the session manager. Verify
with `wpctl status`. If you still have PulseAudio running in compatibility mode, the ALSA and
PulseAudio virtual nodes will appear in the graph and are handled identically.

> See **Ch 8** for Quickshell module imports and build configuration.
> See **Ch 53** for session startup ordering and ensuring PipeWire is ready before your shell launches.

---

## 21.1 PipeWire Architecture Primer

PipeWire is a graph-based multimedia server that handles both audio and video. Every piece of
audio hardware, every application, and every processing plugin appears as a *node* in the graph.
Nodes expose *ports* — either input or output — and ports are connected by *links*. This model
replaces both ALSA sequencing and PulseAudio's sink/source paradigm with a single, unified
abstraction.

At the QML level, the `PipeWire` singleton (from `Quickshell.Services.Pipewire`) mirrors this
object model with three primary list properties: `PipeWire.nodes`, `PipeWire.links`, and
`PipeWire.devices`. Each element in these lists is a live QML object whose properties update
automatically as the graph changes. You never need to refresh or poll — the module keeps
everything in sync via the native PipeWire event loop.

**WirePlumber** is the session manager that sits above PipeWire and enforces policy: which
node becomes the default sink, how links are created when an application opens audio, and what
happens when a device is unplugged. Quickshell communicates with WirePlumber to read and set
defaults. The `PipeWire.defaultAudioSink` and `PipeWire.defaultAudioSource` properties reflect
WirePlumber's current policy decisions and, when written to, instruct WirePlumber to change them.

PipeWire ships with a PulseAudio compatibility layer (`pipewire-pulse`) and an ALSA plugin
(`pipewire-alsa`). Applications that open PulseAudio or ALSA sockets connect transparently through
PipeWire. From your shell's perspective, those applications appear as ordinary stream nodes in
`PipeWire.nodes` with `type == PwNodeType.Stream`; you interact with them the same way you would
any other node.

| Object | PipeWire concept | QML type |
|---|---|---|
| Audio device | Hardware device | `PwDevice` |
| Sink / source | A processing node (endpoint) | `PwNode` + `PwNodeAudio` |
| Application stream | A connected stream node | `PwNode` (type Stream) |
| Port | One end of a connection | `PwPort` |
| Link | Connection between two ports | `PwLink` |

---

## 21.2 PwNode — Audio Nodes

`PwNode` is the central type. Each entry in `PipeWire.nodes` is a `PwNode` with the following
key properties:

| Property | Type | Description |
|---|---|---|
| `id` | `int` | Unique graph-object ID |
| `name` | `string` | Internal node name (e.g. `alsa_output.pci-0000...`) |
| `description` | `string` | Human-readable label |
| `type` | `PwNodeType` | `Sink`, `Source`, `Stream`, or `Unknown` |
| `running` | `bool` | Whether the node is actively processing |
| `audio` | `PwNodeAudio` | Volume, mute, channels, peak levels |

The `audio` sub-object is only valid when the node carries audio. Always guard against `null`
before accessing it — video nodes and loopback nodes may not expose audio properties.

```qml
// ch21/node-list.qml — List all nodes with their type and volume
import QtQuick
import Quickshell.Services.Pipewire

Column {
    spacing: 4

    Repeater {
        model: PipeWire.nodes

        delegate: Row {
            spacing: 8
            required property PwNode modelData

            Text {
                text: {
                    switch (modelData.type) {
                        case PwNodeType.Sink:   return "[SINK]  "
                        case PwNodeType.Source: return "[SRC]   "
                        case PwNodeType.Stream: return "[STREAM]"
                        default:                return "[OTHER] "
                    }
                }
                color: modelData.running ? "#a8ff78" : "#888"
                font.family: "monospace"
            }

            Text {
                text: modelData.description || modelData.name
                color: "#cdd6f4"
            }

            Text {
                visible: modelData.audio !== null
                text: modelData.audio
                    ? Math.round(modelData.audio.volume * 100) + "%"
                    : ""
                color: "#89b4fa"
            }
        }
    }
}
```

Filtering the list to only sinks or only sources is a common pattern. Use a JavaScript array
filter or a `ListModel` proxy. The simplest approach in QML is a conditional `visible` on the
delegate combined with a `Repeater` — this keeps bindings simple, though it does instantiate
hidden delegates. For large graphs (e.g. professional audio rigs with dozens of nodes), use a
`QSortFilterProxyModel` exposed from C++ or a Quickshell `FilteredList` if available in your
version.

```qml
// ch21/sink-only-repeater.qml — Show only sinks
Repeater {
    model: PipeWire.nodes
    delegate: Text {
        required property PwNode modelData
        visible: modelData.type === PwNodeType.Sink
        text: modelData.description
    }
}
```

---

## 21.3 Default Sink and Source

`PipeWire.defaultAudioSink` and `PipeWire.defaultAudioSource` are the two most commonly used
properties. They are reactive: binding to them ensures your widget always reflects the current
default even when the user switches devices or plugs in a USB headset.

Writing `PipeWire.defaultAudioSink = someNode` calls WirePlumber's policy API to change the
system default. The change propagates back through PipeWire and updates the property on all
connected clients automatically — you do not need to manually refresh anything.

Volume is a float in the range `[0.0, 1.0]` using a cubic scale (matching PulseAudio convention)
rather than linear. A value of `1.0` represents 100% (0 dBFS), and values above `1.0` represent
amplification beyond 0 dBFS (PipeWire allows this, though it may cause clipping).

```qml
// ch21/volume-control.qml — Scroll-to-change-volume widget with mute button
import QtQuick
import QtQuick.Controls
import Quickshell.Services.Pipewire

Item {
    width: 200
    height: 40

    // Current default sink shorthand
    property PwNode sink: PipeWire.defaultAudioSink
    property PwNodeAudio sinkAudio: sink ? sink.audio : null

    Row {
        anchors.fill: parent
        spacing: 8

        // Mute / speaker icon button
        Rectangle {
            width: 36; height: 36
            radius: 4
            color: sinkAudio && sinkAudio.muted ? "#f38ba8" : "#313244"

            Text {
                anchors.centerIn: parent
                text: {
                    if (!sinkAudio || sinkAudio.muted) return "🔇"
                    const v = sinkAudio.volume
                    if (v === 0)    return "🔇"
                    if (v < 0.33)  return "🔈"
                    if (v < 0.66)  return "🔉"
                    return "🔊"
                }
                font.pixelSize: 18
            }

            MouseArea {
                anchors.fill: parent
                onClicked: {
                    if (sinkAudio) sinkAudio.muted = !sinkAudio.muted
                }
            }
        }

        // Volume percentage label
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: sinkAudio ? Math.round(sinkAudio.volume * 100) + "%" : "--"
            color: "#cdd6f4"
            font.pixelSize: 14

            // Scroll wheel changes volume in 2% steps
            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.NoButton
                onWheel: event => {
                    if (!sinkAudio) return
                    const delta = event.angleDelta.y > 0 ? 0.02 : -0.02
                    sinkAudio.volume = Math.max(0.0, Math.min(1.5, sinkAudio.volume + delta))
                }
            }
        }
    }
}
```

For the **microphone/source** equivalent, replace every `defaultAudioSink` reference with
`defaultAudioSource`. The API is identical; the only difference is semantic. Many ricers add a
small mic icon next to the volume that shows the current input gain and turns red when muted.

```qml
// ch21/mic-volume.qml — Input gain indicator
property PwNode mic: PipeWire.defaultAudioSource
property PwNodeAudio micAudio: mic ? mic.audio : null

Text {
    text: micAudio
        ? (micAudio.muted ? "MIC OFF" : "MIC " + Math.round(micAudio.volume * 100) + "%")
        : "no mic"
    color: micAudio && micAudio.muted ? "#6c7086" : "#a6e3a1"
}
```

---

## 21.4 PwLink — Audio Routing

`PwLink` represents a directional connection in the graph between one node's output port and
another node's input port. Reading links allows you to build a routing visualizer — useful for
debugging or for power-user shell widgets that show which application is playing audio to which
device.

Each `PwLink` exposes:

| Property | Type | Description |
|---|---|---|
| `outputNode` | `PwNode` | Node providing audio |
| `inputNode` | `PwNode` | Node consuming audio |
| `outputPort` | `PwPort` | Specific port on the output node |
| `inputPort` | `PwPort` | Specific port on the input node |
| `active` | `bool` | Whether data is flowing |

The typical use case is determining which application streams are currently connected to the
default sink — this lets you display a list of "currently playing" apps. Filter `PipeWire.links`
by `link.inputNode === PipeWire.defaultAudioSink` to get all streams feeding into the default
output.

```qml
// ch21/active-streams.qml — List apps connected to the default sink
import QtQuick
import Quickshell.Services.Pipewire

Column {
    spacing: 2

    Text {
        text: "Playing through " + (PipeWire.defaultAudioSink
            ? PipeWire.defaultAudioSink.description : "—")
        color: "#89b4fa"
        font.bold: true
    }

    Repeater {
        // Collect unique output nodes feeding into the default sink
        model: {
            const sink = PipeWire.defaultAudioSink
            if (!sink) return []
            const seen = new Set()
            const result = []
            for (const link of PipeWire.links) {
                if (link.inputNode === sink && link.active && !seen.has(link.outputNode.id)) {
                    seen.add(link.outputNode.id)
                    result.push(link.outputNode)
                }
            }
            return result
        }

        delegate: Text {
            required property PwNode modelData
            text: "  ▶ " + (modelData.description || modelData.name)
            color: "#cdd6f4"
        }
    }
}
```

Note that the `model` expression above uses a JavaScript block — QML reevaluates it whenever
`PipeWire.links` changes, which keeps the list live. For very large graphs with rapid link
changes, consider moving this logic to a Quickshell `Process`-backed model or a dedicated
QML component with an explicit `Connections` block.

---

## 21.5 Audio Level Meters

`PwNodeAudio` exposes per-channel peak levels for building VU meters. The relevant property is
`PwNodeAudio.peakVolumeFor(channel)`, which returns a float in `[0.0, 1.0]` representing the
recent peak amplitude on that channel. The channel count is `PwNodeAudio.channelCount`.

Peak levels update at PipeWire's processing interval (typically 512 or 1024 samples). To smooth
the meter visually, drive the displayed value with a `NumberAnimation` that decays toward the
current peak — this creates the classic "fast attack, slow decay" VU meter behavior.

```qml
// ch21/vu-meter.qml — Stereo VU meter for the default sink
import QtQuick
import Quickshell.Services.Pipewire

Row {
    spacing: 4
    property PwNodeAudio audio: PipeWire.defaultAudioSink
        ? PipeWire.defaultAudioSink.audio : null

    Repeater {
        model: audio ? Math.min(audio.channelCount, 2) : 0

        delegate: Rectangle {
            id: barRoot
            required property int index

            width: 8
            height: 60
            color: "#1e1e2e"
            radius: 2

            // Displayed (smoothed) level
            property real displayLevel: 0.0

            // Target level — update from PipeWire peak
            property real targetLevel: audio ? audio.peakVolumeFor(index) : 0.0

            // Fast attack: jump up immediately; slow decay: animate down
            onTargetLevelChanged: {
                if (targetLevel > displayLevel) {
                    displayLevel = targetLevel   // instant attack
                }
                // decay handled by the animation below
            }

            Behavior on displayLevel {
                NumberAnimation {
                    duration: 400
                    easing.type: Easing.OutExpo
                }
            }

            // Filled portion
            Rectangle {
                width: parent.width
                height: parent.height * barRoot.displayLevel
                anchors.bottom: parent.bottom
                radius: 2
                color: {
                    const lvl = barRoot.displayLevel
                    if (lvl > 0.85) return "#f38ba8"   // red: clipping
                    if (lvl > 0.65) return "#fab387"   // orange: hot
                    return "#a6e3a1"                   // green: normal
                }
            }
        }
    }
}
```

For a full mixer strip with multiple channels, wrap the above in a `Repeater` over
`PipeWire.nodes` filtered to active stream nodes. Pair the VU meter with the node description
label from Section 21.2 to produce a live mini-mixer panel.

If you need the *average* level rather than the peak, average `peakVolumeFor(ch)` across all
channels manually:

```qml
function averageLevel(audio) {
    if (!audio || audio.channelCount === 0) return 0.0
    let sum = 0.0
    for (let ch = 0; ch < audio.channelCount; ch++) {
        sum += audio.peakVolumeFor(ch)
    }
    return sum / audio.channelCount
}
```

---

## 21.6 OSD (On-Screen Display) for Volume

An OSD widget appears briefly when volume changes, then hides itself. The standard pattern in
Quickshell uses a `Connections` block listening to `PipeWire.defaultAudioSink.audio.onVolumeChanged`
and `onMutedChanged` to trigger visibility, combined with a `Timer` to hide the OSD after a
short delay.

For multi-monitor setups, the OSD must be deployed on the focused or primary monitor. Use
Quickshell's `Screens` singleton to iterate monitors and create one OSD per screen, anchoring
each to the desired position on its respective screen.

```qml
// ch21/volume-osd.qml — Slide-in OSD with auto-hide
import QtQuick
import Quickshell
import Quickshell.Services.Pipewire

PanelWindow {
    id: osdWindow

    // Position: bottom-center of screen
    anchors {
        bottom: true
        horizontalCenter: true
    }
    margins.bottom: 80

    width: 280
    height: 56
    color: "transparent"

    // OSD is hidden by default
    visible: osdAnimation.running || hideTimer.running

    property real volumeValue: PipeWire.defaultAudioSink
        ? PipeWire.defaultAudioSink.audio.volume : 0
    property bool mutedValue: PipeWire.defaultAudioSink
        ? PipeWire.defaultAudioSink.audio.muted : false

    Connections {
        target: PipeWire.defaultAudioSink ? PipeWire.defaultAudioSink.audio : null

        function onVolumeChanged() { showOsd() }
        function onMutedChanged()  { showOsd() }
    }

    function showOsd() {
        osdAnimation.restart()
        hideTimer.restart()
    }

    // Hide 2.5 seconds after last change
    Timer {
        id: hideTimer
        interval: 2500
        onTriggered: osdAnimation.stop()
    }

    // Slide-up animation on show
    SequentialAnimation {
        id: osdAnimation
        PropertyAnimation {
            target: osdContainer
            property: "opacity"
            to: 1.0
            duration: 120
        }
    }

    Rectangle {
        id: osdContainer
        anchors.fill: parent
        radius: 12
        color: "#cc1e1e2e"
        opacity: 0.0

        Row {
            anchors.centerIn: parent
            spacing: 12

            Text {
                anchors.verticalCenter: parent.verticalCenter
                font.pixelSize: 20
                text: osdWindow.mutedValue ? "🔇"
                    : osdWindow.volumeValue < 0.33 ? "🔈"
                    : osdWindow.volumeValue < 0.66 ? "🔉"
                    : "🔊"
            }

            // Volume bar
            Rectangle {
                width: 180; height: 8
                radius: 4
                color: "#313244"
                anchors.verticalCenter: parent.verticalCenter

                Rectangle {
                    width: parent.width * Math.min(osdWindow.volumeValue, 1.0)
                    height: parent.height
                    radius: 4
                    color: osdWindow.mutedValue ? "#6c7086" : "#89b4fa"

                    Behavior on width {
                        NumberAnimation { duration: 80 }
                    }
                }
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: Math.round(osdWindow.volumeValue * 100) + "%"
                color: "#cdd6f4"
                font.pixelSize: 14
                font.family: "monospace"
            }
        }
    }
}
```

For multi-screen OSD, wrap the above in a `Variants` block keyed by `Quickshell.screens`. Each
variant creates one `PanelWindow` anchored to its screen. Only one OSD needs to react to the
PipeWire signal — the simplest approach is to show all of them simultaneously when the default
sink changes, since the user can see at most one at a time anyway.

> See **Ch 14** for `PanelWindow` layer configuration and screen anchoring patterns.

---

## 21.7 Device Enumeration and Switcher

`PipeWire.nodes` contains every node including all sinks. Filtering to `type == PwNodeType.Sink`
gives the list of output devices. Display this as a menu or flyout to let the user switch the
default output without opening a separate audio control application.

Setting the default sink requires assigning to `PipeWire.defaultAudioSink`. WirePlumber then
migrates existing streams to the new default automatically (subject to policy configuration).

```qml
// ch21/device-switcher.qml — Popup device selector
import QtQuick
import QtQuick.Controls
import Quickshell.Services.Pipewire

Item {
    id: root
    width: 260
    height: switcherColumn.implicitHeight + 16

    Rectangle {
        anchors.fill: parent
        color: "#1e1e2e"
        radius: 8
        border.color: "#313244"
        border.width: 1
    }

    Column {
        id: switcherColumn
        anchors { left: parent.left; right: parent.right; top: parent.top }
        anchors.margins: 8
        spacing: 2

        Text {
            text: "Output Device"
            color: "#89b4fa"
            font.bold: true
            font.pixelSize: 12
            bottomPadding: 4
        }

        Repeater {
            // Only sink nodes
            model: PipeWire.nodes.filter(n => n.type === PwNodeType.Sink)

            delegate: Rectangle {
                required property PwNode modelData
                width: switcherColumn.width
                height: 32
                radius: 6
                color: PipeWire.defaultAudioSink === modelData
                    ? "#313244" : "transparent"

                Row {
                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter }
                    anchors.leftMargin: 8
                    spacing: 8

                    Text {
                        text: PipeWire.defaultAudioSink === modelData ? "●" : "○"
                        color: PipeWire.defaultAudioSink === modelData ? "#89b4fa" : "#6c7086"
                        font.pixelSize: 10
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    Text {
                        text: modelData.description || modelData.name
                        color: "#cdd6f4"
                        font.pixelSize: 13
                        elide: Text.ElideRight
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: PipeWire.defaultAudioSink = modelData
                    cursorShape: Qt.PointingHandCursor
                    hoverEnabled: true
                    onContainsMouseChanged: parent.color = containsMouse
                        ? "#313244" : (PipeWire.defaultAudioSink === modelData ? "#313244" : "transparent")
                }
            }
        }
    }
}
```

For a combined input/output switcher, duplicate the above section and target
`PipeWire.defaultAudioSource` / `PwNodeType.Source`. An elegant approach is to use a `TabBar`
with two tabs — "Output" and "Input" — and swap the `model` filter accordingly.

---

## 21.8 Microphone Privacy Indicator

Modern desktops display a persistent indicator when any application is capturing audio. The
implementation detects active source-type stream nodes (applications reading from a microphone)
and shows a badge in the status bar.

A "capture stream" in PipeWire appears as a `PwNode` with `type == PwNodeType.Stream` that is
linked to a `PwNodeType.Source` node. The cleanest detection strategy is to iterate `PipeWire.links`
and check whether any active link's `outputNode` is a source-type node.

```qml
// ch21/mic-indicator.qml — Privacy badge for active microphone capture
import QtQuick
import Quickshell.Services.Pipewire

Item {
    id: micIndicator
    width: 24; height: 24

    // True if any stream is actively reading from any source
    property bool micActive: {
        for (const link of PipeWire.links) {
            if (link.active
                && link.outputNode
                && link.outputNode.type === PwNodeType.Source
                && link.inputNode
                && link.inputNode.type === PwNodeType.Stream) {
                return true
            }
        }
        return false
    }

    visible: micActive

    Rectangle {
        anchors.fill: parent
        radius: width / 2
        color: "#f38ba8"

        Text {
            anchors.centerIn: parent
            text: "🎙"
            font.pixelSize: 14
        }
    }

    // Pulse animation to draw attention
    SequentialAnimation on opacity {
        running: micIndicator.micActive
        loops: Animation.Infinite
        NumberAnimation { to: 0.5; duration: 800; easing.type: Easing.InOutSine }
        NumberAnimation { to: 1.0; duration: 800; easing.type: Easing.InOutSine }
    }
}
```

To show *which* application is capturing, extend the indicator with a tooltip or small label.
Iterate the same links but collect the `inputNode.description` for each matching stream:

```qml
property string captureApps: {
    const apps = []
    for (const link of PipeWire.links) {
        if (link.active
            && link.outputNode?.type === PwNodeType.Source
            && link.inputNode?.type === PwNodeType.Stream) {
            const name = link.inputNode.description || link.inputNode.name
            if (!apps.includes(name)) apps.push(name)
        }
    }
    return apps.join(", ")
}
```

Integrate this indicator into your status bar's system tray area, positioned alongside network
and battery widgets. The pulsing animation is intentionally attention-grabbing — you may prefer
a static colored dot for less intrusive behavior.

> See **Ch 18** for status bar layout patterns and Ch 22 for Bluetooth audio pairing integration.

---

## 21.9 Complete Volume Widget — Putting It Together

The following is a self-contained status bar widget combining the volume icon, percentage label,
scroll-to-change, click-to-mute, and a minimal inline bar — ready to drop into a `PanelWindow`.

```qml
// ch21/volume-widget.qml — Full featured status bar volume widget
import QtQuick
import Quickshell.Services.Pipewire

Item {
    id: volumeWidget
    implicitWidth: row.implicitWidth + 12
    implicitHeight: 28

    property PwNode   sink:  PipeWire.defaultAudioSink
    property PwNodeAudio sa: sink ? sink.audio : null

    Row {
        id: row
        anchors.centerIn: parent
        spacing: 6

        Text {
            id: icon
            text: {
                if (!volumeWidget.sa || volumeWidget.sa.muted) return "󰝟"  // nf-md-volume_off
                const v = volumeWidget.sa.volume
                if (v === 0)   return "󰕿"  // nf-md-volume_low (silent)
                if (v < 0.33)  return "󰕿"  // nf-md-volume_low
                if (v < 0.66)  return "󰖀"  // nf-md-volume_medium
                return "󰕾"                  // nf-md-volume_high
            }
            color: volumeWidget.sa && volumeWidget.sa.muted ? "#6c7086" : "#cdd6f4"
            font.pixelSize: 16
        }

        Text {
            id: volLabel
            text: volumeWidget.sa ? Math.round(volumeWidget.sa.volume * 100) + "%" : "--"
            color: "#cdd6f4"
            font.pixelSize: 13
            font.family: "monospace"
        }
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton
        onClicked: mouse => {
            if (mouse.button === Qt.MiddleButton && volumeWidget.sa)
                volumeWidget.sa.muted = !volumeWidget.sa.muted
        }
        onWheel: event => {
            if (!volumeWidget.sa) return
            const step = event.modifiers & Qt.ShiftModifier ? 0.005 : 0.02
            const delta = event.angleDelta.y > 0 ? step : -step
            volumeWidget.sa.volume = Math.max(0.0, Math.min(1.5, volumeWidget.sa.volume + delta))
        }
    }
}
```

This widget uses Nerd Font glyph codepoints for the volume icons. If you use a font without
Nerd Font support, replace the icon strings with Unicode equivalents (`🔇`, `🔈`, `🔉`, `🔊`).

---

## Troubleshooting

**`PipeWire.nodes` is empty or never populates.**
Verify that PipeWire is running: `systemctl --user status pipewire pipewire-pulse wireplumber`.
If any of these are inactive, start them: `systemctl --user start pipewire wireplumber`.
Check that Quickshell has the PipeWire module compiled in: `quickshell --list-modules | grep -i pipe`.

**`PipeWire.defaultAudioSink` is `null`.**
This happens when WirePlumber has not yet assigned a default, usually during startup before
any device enumeration has completed. Guard all accesses: `if (PipeWire.defaultAudioSink) ...`.
A `Connections` block on `PipeWire.onDefaultAudioSinkChanged` will fire once the default is set.

**Volume changes from `pactl` / `wpctl` are not reflected.**
If you are mixing PulseAudio-compat clients with native PipeWire access, ensure `pipewire-pulse`
is running. Changes made through the PulseAudio socket are translated to PipeWire graph events
and should propagate. If they do not, check `PIPEWIRE_RUNTIME_DIR` — mismatched socket paths
indicate the client is talking to a different instance.

**Peak levels are always 0.0.**
Peak level monitoring requires a monitor port on the sink. Verify with:
```bash
pw-dump | python3 -c "
import json, sys
objs = json.load(sys.stdin)
sinks = [o for o in objs if o.get('type') == 'PipeWire:Interface:Node'
         and 'Monitor' in str(o.get('info', {}).get('props', {}))]
print(len(sinks), 'monitor nodes found')
"
```
If no monitor nodes appear, check WirePlumber configuration — some minimal configs disable
monitor ports to save CPU. See `/usr/share/wireplumber/main.lua.d/` for the relevant policy.

**Huge CPU usage from VU meters.**
Unbounded `Behavior` animations and `peakVolumeFor()` bindings that update every processing
cycle can be expensive. Cap update frequency by driving peak reads from a `Timer` at 30–60 Hz
rather than binding directly:

```qml
Timer {
    interval: 33   // ~30 fps
    running: vuMeterVisible
    repeat: true
    onTriggered: {
        if (audio) barRoot.targetLevel = audio.peakVolumeFor(0)
    }
}
```

**Default sink assignment has no effect.**
Some WirePlumber policies ignore default-sink writes when "follow focus" or "persistent routing"
rules override them. Check `/etc/wireplumber/` and `~/.config/wireplumber/` for custom scripts.
Use `wpctl set-default <id>` from the terminal to confirm whether the issue is in Quickshell or
in WirePlumber policy.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
