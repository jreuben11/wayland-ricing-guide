# Chapter 76 — Quickshell OSD: Volume, Brightness, and Media On-Screen Displays

## Overview
On-screen displays (OSDs) — the translucent overlays showing volume level when
you press a media key — are in nearly every rice. Quickshell can replace external
OSD daemons (dunst-based, swayosd) with a fully custom QML implementation.

## Sections

### 76.1 OSD Architecture

```
Hardware key press
    → Hyprland keybind → pactl / brightnessctl
        → PipeWire volume change (reactive in Quickshell)
        → OSD visible = true → auto-hide timer
```

The OSD doesn't run shell commands — it reacts to PipeWire/system events.

### 76.2 OSD State Singleton

```qml
// osd/OsdState.qml
pragma Singleton
import Quickshell
import Quickshell.Services.Pipewire

Singleton {
    property var activeOsd: null   // "volume", "brightness", "mic", "media"
    property real value: 0         // 0.0 – 1.0
    property bool muted: false
    property string icon: ""

    // React to volume changes
    Connections {
        target: PipeWire.defaultAudioSink?.audio
        function onVolumeChanged() {
            OsdState.value = PipeWire.defaultAudioSink.audio.volume
            OsdState.muted = PipeWire.defaultAudioSink.audio.muted
            OsdState.icon = OsdState.muted ? "audio-volume-muted-symbolic"
                           : OsdState.value > 0.66 ? "audio-volume-high-symbolic"
                           : OsdState.value > 0.33 ? "audio-volume-medium-symbolic"
                           : "audio-volume-low-symbolic"
            OsdState.activeOsd = "volume"
            hideTimer.restart()
        }
    }

    Timer {
        id: hideTimer
        interval: 2000
        onTriggered: OsdState.activeOsd = null
    }
}
```

### 76.3 Volume OSD Window

```qml
// osd/VolumeOsd.qml
PanelWindow {
    screen: Quickshell.screens[0]
    layer: WlrLayer.Overlay
    anchors { bottom: true }
    margins.bottom: 96
    color: "transparent"
    exclusiveZone: -1

    width: 280
    height: 72
    visible: OsdState.activeOsd === "volume"

    // Slide up / fade in animation
    property real targetOpacity: visible ? 1 : 0
    Behavior on targetOpacity { NumberAnimation { duration: 150 } }
    opacity: targetOpacity

    Rectangle {
        anchors.centerIn: parent
        width: parent.width
        height: 64
        radius: 16
        color: "#cc1e1e2e"   // semi-transparent background

        RowLayout {
            anchors { fill: parent; margins: 16 }
            spacing: 16

            IconImage {
                source: OsdState.icon
                implicitSize: 24
                color: OsdState.muted ? "#f38ba8" : "#cdd6f4"
            }

            // Progress bar
            Rectangle {
                Layout.fillWidth: true
                height: 6
                radius: 3
                color: "#313244"

                Rectangle {
                    width: parent.width * Math.min(OsdState.value, 1.0)
                    height: parent.height
                    radius: parent.radius
                    color: OsdState.muted ? "#f38ba8"
                           : OsdState.value > 1.0 ? "#f9e2af"  // overdrive warning
                           : "#89b4fa"
                    Behavior on width { NumberAnimation { duration: 80 } }
                }
            }

            Text {
                text: Math.round(OsdState.value * 100) + "%"
                color: "#cdd6f4"
                font.pixelSize: 14
                Layout.minimumWidth: 36
                horizontalAlignment: Text.AlignRight
            }
        }
    }
}
```

### 76.4 Brightness OSD

For brightness, read from `/sys/class/backlight/*/brightness`:

```qml
// In OsdState.qml
FileView {
    id: brightnessFile
    path: "/sys/class/backlight/intel_backlight/brightness"
    watchChanges: true
    onTextChanged: {
        const maxFile = Qt.resolvedUrl("/sys/class/backlight/intel_backlight/max_brightness")
        // Read max and compute ratio
        OsdState.brightnessValue = parseInt(text) / OsdState.maxBrightness
        OsdState.activeOsd = "brightness"
        hideTimer.restart()
    }
}
```

Or trigger from a keybind script:
```conf
# hyprland.conf
bind = , XF86MonBrightnessUp, exec, brightnessctl set +5% && quickshell ipc call showBrightnessOsd
```

### 76.5 Mic Mute Indicator

```qml
Connections {
    target: PipeWire.defaultAudioSource?.audio
    function onMutedChanged() {
        OsdState.icon = PipeWire.defaultAudioSource.audio.muted
            ? "microphone-sensitivity-muted-symbolic"
            : "audio-input-microphone-symbolic"
        OsdState.activeOsd = "mic"
        hideTimer.restart()
    }
}
```

Show as a small persistent badge (not a slider) since mic mute is binary.

### 76.6 Capslock / NumLock Indicator

```qml
// React to Hyprland keyboard state
HyprlandEvent {
    onActiveLayoutChanged: {
        // Check modifiers if needed
    }
}
// Or: Process running xkb-switch or reading /dev/input
```

### 76.7 Keybinds That Trigger the OSD

```conf
# hyprland.conf — media keys that change volume AND show OSD
bind = , XF86AudioRaiseVolume, exec, pactl set-sink-volume @DEFAULT_SINK@ +5%
bind = , XF86AudioLowerVolume, exec, pactl set-sink-volume @DEFAULT_SINK@ -5%
bind = , XF86AudioMute, exec, pactl set-sink-mute @DEFAULT_SINK@ toggle

# OSD is triggered automatically by PipeWire volume change event in Quickshell
# No extra IPC calls needed
```

### 76.8 swayosd — Alternative (External OSD Daemon)

If you don't want to build an OSD in Quickshell:
```bash
sudo pacman -S swayosd-git   # or AUR
exec-once = swayosd-server

# In hyprland.conf
bind = , XF86AudioRaiseVolume, exec, swayosd-client --output-volume raise
bind = , XF86AudioMute, exec, swayosd-client --output-volume mute-toggle
bind = , XF86MonBrightnessUp, exec, swayosd-client --brightness raise
```

swayosd handles D-Bus signals and shows its own themed OSD popup.
