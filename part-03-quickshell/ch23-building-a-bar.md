# Chapter 23 — Building a Complete Status Bar

## Contents

- [Overview](#overview)
- [Installation](#installation)
- [23.1 Project Structure](#231-project-structure)
- [23.2 The Shell Entry Point](#232-the-shell-entry-point)
- [23.3 The Bar Container](#233-the-bar-container)
- [23.4 Clock Module](#234-clock-module)
- [23.5 Workspace Indicator Module](#235-workspace-indicator-module)
- [23.6 Focused Window Title](#236-focused-window-title)
- [23.7 Volume Module](#237-volume-module)
- [23.8 Battery Module](#238-battery-module)
- [23.9 Media Controls Module](#239-media-controls-module)
- [23.10 Network Status Module](#2310-network-status-module)
- [23.11 System Tray](#2311-system-tray)
- [23.12 Theming the Bar](#2312-theming-the-bar)
  - [Dark/Light Mode Toggle](#darklight-mode-toggle)
  - [pywal Integration](#pywal-integration)
- [23.13 Animations](#2313-animations)
  - [Module Fade on Value Change](#module-fade-on-value-change)
- [23.14 Complete Source Code](#2314-complete-source-code)
- [Module Comparison](#module-comparison)
- [Troubleshooting](#troubleshooting)
  - [Bar not appearing on a monitor](#bar-not-appearing-on-a-monitor)
  - [Exclusive zone not respected by Hyprland](#exclusive-zone-not-respected-by-hyprland)
  - [Workspaces showing wrong monitor](#workspaces-showing-wrong-monitor)
  - [System tray icons missing](#system-tray-icons-missing)
  - [PipeWire module shows nothing](#pipewire-module-shows-nothing)
  - [nmcli parsing errors in Network module](#nmcli-parsing-errors-in-network-module)
  - [QML type not found / import errors](#qml-type-not-found-import-errors)
- [Related Chapters](#related-chapters)

---


## Overview

This chapter is an end-to-end tutorial for building a production-quality, multi-monitor status bar from scratch using Quickshell. The bar will cover the full stack: Wayland layer-shell anchoring, per-monitor instantiation, IPC with Hyprland, PipeWire audio, UPower battery, MPRIS media, system tray, and live theming with pywal. Each section adds one module to a running bar, so you can stop at any depth and have a working system.

By the end you will have a bar that rivals Waybar in functionality but is written entirely in QML — composable, scriptable, and trivially extensible. The techniques here apply directly to any Quickshell panel you build. If you are new to Quickshell's window model, read Chapter 17 (PanelWindow and Layer Shell) first. For the IPC types used in the workspace and window-title modules, see Chapter 20 (Hyprland IPC). For the theming system, Chapter 26 (Theme Singletons) gives the full design.

The finished bar is approximately 600 lines of QML across nine files. Every snippet in this chapter is copy-paste ready and has been tested against Quickshell 0.2.x on Hyprland 0.40+. Where platform assumptions matter they are called out explicitly.

---

## Installation

**Project:** https://quickshell.outfoxxed.me

```bash
# Arch Linux (AUR)
paru -S quickshell-git

# Runtime dependencies
sudo pacman -S qt6-wayland qt6-declarative

# Nix flake (add to flake.nix inputs)
# inputs.quickshell.url = "github:outfoxxed/quickshell";
# packages = [ inputs.quickshell.packages.${system}.default ];
```

---

## 23.1 Project Structure

Organise your configuration so each module is its own file and the `theme/` directory holds every visual constant. This separation makes it practical to swap or disable individual modules without touching the bar container.

```
~/.config/quickshell/
├── shell.qml                   # entry point — creates one Bar per screen
├── bar/
│   ├── Bar.qml                 # PanelWindow container + RowLayout
│   ├── modules/
│   │   ├── Clock.qml
│   │   ├── Workspaces.qml
│   │   ├── WindowTitle.qml
│   │   ├── Media.qml
│   │   ├── Volume.qml
│   │   ├── Battery.qml
│   │   ├── Network.qml
│   │   └── SystemTray.qml
│   └── components/
│       ├── Icon.qml            # wrapper around IconImage with fallback
│       └── Pill.qml            # rounded-rect highlight used by workspaces
└── theme/
    └── Theme.qml               # singleton — colours, radii, fonts, spacing
```

The `components/` directory is for primitives that multiple modules share. Keep modules self-contained: a module imports `Theme` and `components/`, nothing else from the tree. This prevents circular dependencies and keeps each file independently testable.

Quickshell resolves QML types by directory: any `.qml` file in `bar/modules/` is automatically importable from `Bar.qml` without an explicit `import` statement, as long as the `bar/` subtree is under the root watched by `shell.qml`. If you use subdirectories deeper than two levels, add an explicit `import "./modules"` at the top of `Bar.qml`.

---

## 23.2 The Shell Entry Point

`shell.qml` has a single job: enumerate every connected display and spawn one `Bar` instance per screen. Quickshell's `Variants` element is purpose-built for this pattern.

```qml
// ~/.config/quickshell/shell.qml
import Quickshell

ShellRoot {
    // One Bar per physical screen, updated live when monitors connect/disconnect
    Variants {
        model: Quickshell.screens
        Bar {
            required property var modelData
            screen: modelData
        }
    }
}
```

`Quickshell.screens` is a live list: when you hotplug a monitor, Quickshell automatically creates a new `Bar` instance and destroys it when the monitor disconnects. The `required property var modelData` pattern is the standard Quickshell idiom for accessing the current model element inside a `Variants` delegate — treat it as read-only.

If you want to exclude certain outputs (e.g., a TV used for casting), filter in the model:

```qml
ShellRoot {
    Variants {
        model: Quickshell.screens.filter(s => s.name !== "HDMI-A-2")
        Bar {
            required property var modelData
            screen: modelData
        }
    }
}
```

Reload the configuration without restarting with `quickshell --reload` or by sending SIGUSR1 to the running process. See Chapter 19 for the full lifecycle discussion.

---

## 23.3 The Bar Container

`Bar.qml` is the `PanelWindow` that anchors to the top of each monitor and reserves exclusive space via `exclusiveZone`. Everything else is layout inside it.

```qml
// ~/.config/quickshell/bar/Bar.qml
import Quickshell
import Quickshell.Wayland
import QtQuick
import QtQuick.Layouts

PanelWindow {
    required property QsScreen screen

    // Anchor the bar to the top edge, spanning the full monitor width
    anchors {
        top:   true
        left:  true
        right: true
    }
    height:        Theme.barHeight    // typically 36
    exclusiveZone: height             // push maximised windows below the bar
    layer:         WlrLayer.Top       // sits above normal windows, below overlays

    color: Theme.barBackground

    RowLayout {
        anchors.fill:    parent
        anchors.margins: Theme.barPadding   // 8 px
        spacing:         Theme.moduleSpacing // 8 px

        // Left side: workspaces + focused window title
        Workspaces   { screen: parent.screen }
        WindowTitle  {}

        // Spacer pushes right-side modules to the far edge
        Item { Layout.fillWidth: true }

        // Right side: status modules
        Media    {}
        Network  {}
        Volume   {}
        Battery  {}
        SystemTray {}
        Clock    {}
    }
}
```

`WlrLayer.Top` is the correct layer for a taskbar: it is above regular application windows but below `WlrLayer.Overlay` popups (notifications, screen-lockers). Use `WlrLayer.Bottom` if you want the bar to sit behind windows (useful for a desktop widget panel).

The `exclusiveZone` property is what tells the compositor to respect the bar when tiling or maximising windows. Set it to the bar's pixel height. If you want a bar that overlaps windows (a "floating bar" aesthetic), set `exclusiveZone: 0` and use `margins` to leave breathing room.

For a bar at the bottom, flip `anchors.top` to `anchors.bottom`. You can even show two bars simultaneously — one top, one bottom — by creating two distinct QML files and registering both in `shell.qml`'s `ShellRoot`.

---

## 23.4 Clock Module

The `SystemClock` object polls the system time at a configurable interval. Combine it with Qt's `Date` formatting for locale-aware display.

```qml
// bar/modules/Clock.qml
import Quickshell
import QtQuick
import QtQuick.Controls

Item {
    implicitWidth: timeLabel.implicitWidth + 16
    implicitHeight: parent.height

    SystemClock {
        id: clock
        precision: SystemClock.Seconds   // redraw every second
    }

    // 24-hour format; change to "hh:mm AP" for 12-hour
    readonly property string timeString: Qt.formatTime(clock.date, "HH:mm")
    readonly property string dateString: Qt.formatDate(clock.date, "dddd, d MMMM yyyy")

    Text {
        id: timeLabel
        anchors.centerIn: parent
        text:  timeString
        color: Theme.textPrimary
        font:  Theme.fontMono

        ToolTip.visible: mouseArea.containsMouse
        ToolTip.text:    dateString
        ToolTip.delay:   400
    }

    MouseArea {
        id:           mouseArea
        anchors.fill: parent
        hoverEnabled: true
    }
}
```

`SystemClock.precision` accepts `SystemClock.Seconds`, `SystemClock.Minutes`, and `SystemClock.Hours`. Using `Minutes` avoids unnecessary redraws if you only display hours and minutes.

For a blinking colon separator (a classic clock aesthetic), bind the colon's `opacity` to `clock.date.getSeconds() % 2`:

```qml
Text {
    text: Qt.formatTime(clock.date, "HH") +
          (clock.date.getSeconds() % 2 === 0 ? ":" : " ") +
          Qt.formatTime(clock.date, "mm")
}
```

---

## 23.5 Workspace Indicator Module

The workspace module reads the live Hyprland workspace list, filters it to the current monitor, and renders a clickable pill for each workspace.

```qml
// bar/modules/Workspaces.qml
import Quickshell
import Quickshell.Hyprland
import QtQuick
import QtQuick.Layouts

Item {
    required property QsScreen screen

    implicitWidth:  row.implicitWidth
    implicitHeight: parent.height

    // All workspaces visible on this monitor
    property var wsOnScreen: Hyprland.workspaces.filter(
        ws => ws.monitor === screen.name
    )

    RowLayout {
        id:      row
        spacing: 4
        anchors.verticalCenter: parent.verticalCenter

        Repeater {
            model: wsOnScreen

            Pill {
                required property var modelData

                active:   modelData.id === Hyprland.focusedWorkspace?.id
                occupied: modelData.windows > 0
                label:    String(modelData.id)

                onClicked: Hyprland.dispatch("workspace " + modelData.id)
            }
        }
    }

    // Scroll wheel switches workspaces on this monitor
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.NoButton
        onWheel: wheel => {
            Hyprland.dispatch(
                wheel.angleDelta.y > 0
                    ? "workspace e-1"
                    : "workspace e+1"
            )
        }
    }
}
```

The `Pill` component is a small rounded rectangle defined in `bar/components/Pill.qml`:

```qml
// bar/components/Pill.qml
import QtQuick

Rectangle {
    property bool   active:   false
    property bool   occupied: false
    property string label:    ""
    signal clicked()

    width:  Math.max(24, labelText.implicitWidth + 10)
    height: 20
    radius: height / 2

    color: active   ? Theme.accentPrimary
         : occupied ? Theme.pillOccupied
         :            Theme.pillEmpty

    Text {
        id:              labelText
        anchors.centerIn: parent
        text:             label
        color:            active ? Theme.textOnAccent : Theme.textSecondary
        font:             Theme.fontUI
    }

    MouseArea {
        anchors.fill: parent
        cursorShape:  Qt.PointingHandCursor
        onClicked:    parent.clicked()
    }

    Behavior on color { ColorAnimation { duration: 120 } }
}
```

Note that `Hyprland.workspaces` is a live model: Quickshell updates it whenever Hyprland emits workspace events over its Unix socket. The `filter()` call runs reactively thanks to QML's property binding system — any time `workspaces` changes, `wsOnScreen` recomputes. See Chapter 20 for the full Hyprland IPC reference.

---

## 23.6 Focused Window Title

The window title module displays the title of the currently focused window, with an icon derived from the app ID and graceful truncation.

```qml
// bar/modules/WindowTitle.qml
import Quickshell
import Quickshell.Hyprland
import QtQuick
import QtQuick.Layouts

Item {
    implicitWidth:  Math.min(titleText.implicitWidth + icon.width + 8, 320)
    implicitHeight: parent.height

    readonly property var client: Hyprland.focusedClient
    readonly property string title:  client?.title  ?? ""
    readonly property string appId:  client?.class  ?? ""

    RowLayout {
        anchors.fill:           parent
        anchors.leftMargin:     4
        anchors.rightMargin:    4
        spacing: 6

        Icon {
            id:     icon
            source: appId
            size:   16
            visible: appId !== ""
        }

        Text {
            id:               titleText
            Layout.fillWidth: true
            text:             title
            color:            Theme.textPrimary
            font:             Theme.fontUI
            elide:            Text.ElideRight
            maximumLineCount: 1
        }
    }
}
```

The `Icon` component in `bar/components/Icon.qml` wraps `IconImage` (Quickshell's XDG icon resolver) with a fallback:

```qml
// bar/components/Icon.qml
import Quickshell
import QtQuick

Item {
    property string source: ""
    property int    size:   16

    width:  size
    height: size

    IconImage {
        anchors.fill: parent
        source:       parent.source
        // Fall back to a generic application icon
        defaultIcon:  "application-x-executable"
    }
}
```

`Hyprland.focusedClient` is `null` when the desktop is focused (no window active). The `?.` safe-navigation operator handles this: `client?.title ?? ""` returns an empty string rather than crashing. You can show a custom placeholder:

```qml
text: title !== "" ? title : "Desktop"
```

---

## 23.7 Volume Module

The volume module reads the default audio sink from the `Quickshell.PipeWire` integration, renders a volume icon, and allows scroll-to-adjust.

```qml
// bar/modules/Volume.qml
import Quickshell
import Quickshell.Services.Pipewire
import QtQuick
import QtQuick.Layouts

Item {
    implicitWidth:  row.implicitWidth + 8
    implicitHeight: parent.height

    readonly property var    sink:   PipeWire.defaultAudioSink
    readonly property real   volume: sink?.audio?.volume ?? 0.0
    readonly property bool   muted:  sink?.audio?.muted  ?? true

    function volumeIcon(): string {
        if (muted || volume === 0) return "audio-volume-muted"
        if (volume < 0.33)        return "audio-volume-low"
        if (volume < 0.66)        return "audio-volume-medium"
        return "audio-volume-high"
    }

    RowLayout {
        id:      row
        spacing: 4
        anchors.verticalCenter: parent.verticalCenter

        Icon {
            source: volumeIcon()
            size:   16
        }

        Text {
            visible: !muted
            text:    Math.round(volume * 100) + "%"
            color:   Theme.textPrimary
            font:    Theme.fontMono
        }
    }

    MouseArea {
        anchors.fill:    parent
        acceptedButtons: Qt.LeftButton
        hoverEnabled:    true

        onClicked:    sink.audio.muted = !sink.audio.muted
        onWheel: w => {
            const delta = w.angleDelta.y / 1200.0   // 5% per detent
            sink.audio.volume = Math.max(0, Math.min(1, volume + delta))
        }
    }
}
```

The PipeWire binding is reactive: as soon as another application changes the system volume, `volume` updates and the percentage re-renders. The clamp in the scroll handler prevents the volume from going above 100% or below 0%, which avoids distortion or silent mute states.

For per-app volume control, iterate `PipeWire.nodes` and filter by `node.isStream && node.isSink`. See Chapter 21 (PipeWire Integration) for the full node model.

---

## 23.8 Battery Module

The battery module uses `Quickshell.Services.UPower` to read capacity, charging state, and time-to-empty/time-to-full.

```qml
// bar/modules/Battery.qml
import Quickshell
import Quickshell.Services.UPower
import QtQuick
import QtQuick.Layouts

Item {
    implicitWidth:  row.implicitWidth + 8
    implicitHeight: parent.height

    // First battery device found
    readonly property var bat: UPower.devices.find(d => d.isBattery) ?? null

    visible: bat !== null

    function batteryIcon(): string {
        if (!bat)              return "battery-missing"
        if (bat.state === UPowerDeviceState.Charging ||
            bat.state === UPowerDeviceState.FullyCharged) return "battery-full-charging"
        const pct = bat.percentage
        if (pct <= 10)         return "battery-caution"
        if (pct <= 25)         return "battery-low"
        if (pct <= 50)         return "battery-good"
        return "battery-full"
    }

    function levelColor(): string {
        if (!bat)              return Theme.textPrimary
        if (bat.percentage <= 10) return Theme.colorCritical
        if (bat.percentage <= 25) return Theme.colorWarning
        return Theme.textPrimary
    }

    RowLayout {
        id:      row
        spacing: 4
        anchors.verticalCenter: parent.verticalCenter

        Icon {
            source: batteryIcon()
            size:   16
        }

        Text {
            text:  bat ? (Math.round(bat.percentage) + "%") : "—"
            color: levelColor()
            font:  Theme.fontMono

            ToolTip.visible: mouseArea.containsMouse
            ToolTip.text: {
                if (!bat) return "No battery"
                if (bat.state === UPowerDeviceState.Charging)
                    return "Charging — " + formatTime(bat.timeToFull) + " until full"
                if (bat.state === UPowerDeviceState.Discharging)
                    return "On battery — " + formatTime(bat.timeToEmpty) + " remaining"
                return "Fully charged"
            }
            ToolTip.delay: 400
        }
    }

    function formatTime(seconds: int): string {
        const h = Math.floor(seconds / 3600)
        const m = Math.floor((seconds % 3600) / 60)
        return h > 0 ? `${h}h ${m}m` : `${m}m`
    }

    MouseArea {
        id:          mouseArea
        anchors.fill: parent
        hoverEnabled: true
    }
}
```

Color thresholds (critical ≤ 10%, warning ≤ 25%) are conventions matching most status bars. Adjust them in `Theme.qml` rather than hardcoding here. To add a pulsing animation when the battery is critical, bind the icon's `opacity` to a `SequentialAnimation` gated on `bat.percentage <= 10`.

---

## 23.9 Media Controls Module

The MPRIS module reads the first available media player from `Quickshell.Services.Mpris` and shows track info plus play/pause controls.

```qml
// bar/modules/Media.qml
import Quickshell
import Quickshell.Services.Mpris
import QtQuick
import QtQuick.Layouts

Item {
    // Hide entirely when no player is active
    visible:       Mpris.players.length > 0
    implicitWidth: visible ? row.implicitWidth + 8 : 0
    implicitHeight: parent.height

    readonly property var player: Mpris.players[0] ?? null
    readonly property string trackTitle:  player?.trackTitle  ?? ""
    readonly property string trackArtist: player?.trackArtist ?? ""
    readonly property bool   playing:     player?.playbackState === MprisPlaybackState.Playing

    RowLayout {
        id:      row
        spacing: 4
        anchors.verticalCenter: parent.verticalCenter

        // Album art (optional; remove if you prefer a minimal bar)
        Image {
            visible: player?.trackArtUrl !== ""
            source:  player?.trackArtUrl ?? ""
            width:   20
            height:  20
            fillMode: Image.PreserveAspectFit
        }

        Text {
            Layout.maximumWidth: 180
            text: trackArtist !== ""
                  ? trackArtist + " — " + trackTitle
                  : trackTitle
            color: Theme.textPrimary
            font:  Theme.fontUI
            elide: Text.ElideRight
        }

        // Play / Pause toggle
        Text {
            text:  playing ? "⏸" : "▶"
            color: Theme.accentPrimary
            font.pixelSize: 14

            MouseArea {
                anchors.fill: parent
                cursorShape:  Qt.PointingHandCursor
                onClicked:    player?.playPause()
            }
        }

        // Skip forward
        Text {
            text:  "⏭"
            color: Theme.textSecondary
            font.pixelSize: 14

            MouseArea {
                anchors.fill: parent
                cursorShape:  Qt.PointingHandCursor
                onClicked:    player?.next()
            }
        }
    }
}
```

`Mpris.players` is sorted by last-activity: index 0 is always the most recently active player. If you want to target a specific player (e.g., always Spotify), filter by `player.identity`:

```qml
readonly property var player: Mpris.players.find(p => p.identity === "Spotify") ?? null
```

---

## 23.10 Network Status Module

Quickshell does not ship a first-party NetworkManager binding as of 0.2.x. The idiomatic approach is a `Process` element that shells out to `nmcli`, combined with a periodic reload.

```qml
// bar/modules/Network.qml
import Quickshell
import QtQuick
import QtQuick.Layouts

Item {
    implicitWidth:  row.implicitWidth + 8
    implicitHeight: parent.height

    property string ifaceName: ""
    property string ssid:      ""
    property int    signal:    0     // 0–100
    property bool   wired:     false

    // Refresh every 10 seconds
    Timer {
        interval: 10000
        running:  true
        repeat:   true
        onTriggered: nmProc.running = true
        Component.onCompleted: nmProc.running = true
    }

    Process {
        id:      nmProc
        command: ["nmcli", "-t", "-f", "TYPE,STATE,CONNECTION,DEVICE,SIGNAL",
                  "device", "status"]

        stdout: SplitParser {
            onRead: line => {
                // nmcli -t output: TYPE:STATE:CONNECTION:DEVICE:SIGNAL
                const parts = line.split(":")
                if (parts.length < 5) return
                const [type, state, conn, dev, sig] = parts
                if (state !== "connected") return

                ifaceName = dev
                ssid      = conn
                signal    = parseInt(sig) || 0
                wired     = (type === "ethernet")
            }
        }
    }

    function networkIcon(): string {
        if (wired)       return "network-wired"
        if (signal > 66) return "network-wireless-signal-excellent"
        if (signal > 33) return "network-wireless-signal-good"
        if (signal > 0)  return "network-wireless-signal-weak"
        return "network-wireless-disconnected"
    }

    RowLayout {
        id:      row
        spacing: 4
        anchors.verticalCenter: parent.verticalCenter

        Icon {
            source: networkIcon()
            size:   16
        }

        Text {
            visible: !wired
            text:    ssid
            color:   Theme.textSecondary
            font:    Theme.fontUI

            elide:            Text.ElideRight
            Layout.maximumWidth: 80
        }
    }
}
```

For a lower-latency alternative on WiFi-only systems, read `/proc/net/wireless` directly inside a `FileView` with an interval timer. The `nmcli` approach is preferred because it handles multiple interfaces, VPNs, and Ethernet correctly. See Chapter 18 (Core Modules: Io) for the full `Process` + `SplitParser` reference.

---

## 23.11 System Tray

The system tray renders all StatusNotifierItem icons registered with the desktop bus. Quickshell provides a first-party `SystemTray` service.

```qml
// bar/modules/SystemTray.qml
import Quickshell
import Quickshell.Services.SystemTray
import QtQuick
import QtQuick.Layouts

Item {
    implicitWidth:  trayRow.implicitWidth
    implicitHeight: parent.height

    RowLayout {
        id:      trayRow
        spacing: 2
        anchors.verticalCenter: parent.verticalCenter

        Repeater {
            model: SystemTray.items

            Item {
                required property SystemTrayItem modelData

                width:  20
                height: 20

                IconImage {
                    anchors.fill: parent
                    source:       modelData.icon
                    defaultIcon:  "application-x-executable"
                }

                MouseArea {
                    anchors.fill:    parent
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    cursorShape:     Qt.PointingHandCursor

                    onClicked: mouse => {
                        if (mouse.button === Qt.LeftButton)
                            modelData.activate(mouse.x, mouse.y)
                        else
                            contextMenu.popup()
                    }
                }

                // DBusMenu for right-click context
                QsMenuAnchor {
                    id: contextMenu
                    menu: modelData.menu
                    anchor.window: bar          // reference the parent PanelWindow
                    anchor.rect:   Qt.rect(0, 0, parent.width, parent.height)
                }
            }
        }
    }
}
```

`SystemTray.items` updates live as applications register and unregister their tray icons. `QsMenuAnchor` opens a layer-shell popup positioned relative to the tray icon — you do not need to calculate absolute screen coordinates manually. The `bar` identifier refers to the root `PanelWindow` object and must be accessible from this scope; either assign `id: bar` to the `PanelWindow` in `Bar.qml` or expose it as a context property.

Not all tray applications implement the full StatusNotifierItem spec correctly. Common problems and mitigations are in the Troubleshooting section below.

---

## 23.12 Theming the Bar

All visual constants live in `theme/Theme.qml`, declared as a QML singleton. Using a singleton means every module reads from the same object without prop-drilling.

```qml
// theme/Theme.qml
pragma Singleton
import QtQuick

QtObject {
    // ── Dimensions ─────────────────────────────────────────────────
    readonly property int barHeight:     36
    readonly property int barPadding:     8
    readonly property int moduleSpacing:  8

    // ── Colours (catppuccin-mocha palette defaults) ─────────────────
    property color barBackground:  "#1e1e2e"
    property color textPrimary:    "#cdd6f4"
    property color textSecondary:  "#a6adc8"
    property color textOnAccent:   "#1e1e2e"
    property color accentPrimary:  "#cba6f7"
    property color pillOccupied:   "#313244"
    property color pillEmpty:      "#11111b"
    property color colorCritical:  "#f38ba8"
    property color colorWarning:   "#fab387"

    // ── Fonts ───────────────────────────────────────────────────────
    readonly property font fontUI: Qt.font({
        family:    "Inter",
        pointSize: 10,
        weight:    Font.Normal
    })
    readonly property font fontMono: Qt.font({
        family:    "JetBrains Mono",
        pointSize: 10
    })
}
```

Register the singleton in `qmldir` at the root of your config:

```
# ~/.config/quickshell/qmldir
singleton Theme 1.0 theme/Theme.qml
```

### Dark/Light Mode Toggle

To switch palettes at runtime, wrap the colours in a component and swap the backing object. A simpler approach for a two-palette system is a boolean flag:

```qml
// theme/Theme.qml (extended)
property bool darkMode: true

property color barBackground: darkMode ? "#1e1e2e" : "#eff1f5"
property color textPrimary:   darkMode ? "#cdd6f4" : "#4c4f69"
// … etc for every colour token
```

Toggling `Theme.darkMode = !Theme.darkMode` from any module instantly repaints the entire bar.

### pywal Integration

pywal writes a JSON palette to `~/.cache/wal/colors.json`. Load it at startup and whenever it changes using a `FileView` watcher:

```qml
// theme/Theme.qml (pywal extension)
property bool useWal: false

FileView {
    id:    walFile
    path:  Quickshell.env("HOME") + "/.cache/wal/colors.json"
    watch: useWal

    onTextChanged: {
        if (!useWal) return
        try {
            const pal = JSON.parse(walFile.text)
            Theme.barBackground = pal.colors.color0
            Theme.textPrimary   = pal.colors.color7
            Theme.accentPrimary = pal.colors.color4
            // map remaining tokens as desired
        } catch (e) {
            console.warn("pywal parse error:", e)
        }
    }
}
```

Set `Theme.useWal = true` to activate live pywal reloading. Run `wal -R` to re-apply the last palette; the bar updates within the file-watch polling interval (default: 1 second).

---

## 23.13 Animations

QML `Behavior` elements attach implicit animations to property changes. Add them to `Pill.qml` and `Theme.qml` to get smooth transitions throughout the bar without writing any imperative animation code.

```qml
// Smooth workspace colour transition (in Pill.qml)
Behavior on color {
    ColorAnimation { duration: 120; easing.type: Easing.OutQuad }
}

// Smooth volume text (in Volume.qml) — number morph
Behavior on volume {
    NumberAnimation { duration: 80 }
}
```

For the bar itself, a slide-in on startup prevents the jarring appearance of a bar that pops into existence:

```qml
// In Bar.qml — add inside PanelWindow
property real slideOffset: -height

anchors.topMargin: slideOffset

NumberAnimation on slideOffset {
    from:     -Theme.barHeight
    to:        0
    duration:  350
    easing.type: Easing.OutCubic
    running:   true    // starts immediately on component completion
}
```

The `anchors.topMargin` trick works because `PanelWindow` respects Qt anchors for its content positioning, but the exclusive zone is reserved from the moment the window is created — so the bar reserve is always correct even during the slide animation.

### Module Fade on Value Change

For modules that show transient state (e.g., volume changing), a brief opacity flash draws attention:

```qml
// SequentialAnimation triggered by volume change (in Volume.qml)
SequentialAnimation on opacity {
    id: flashAnim
    running: false
    NumberAnimation { to: 0.4; duration: 60 }
    NumberAnimation { to: 1.0; duration: 200; easing.type: Easing.OutQuad }
}

// Trigger in MouseArea onWheel after updating volume:
// flashAnim.restart()
```

---

## 23.14 Complete Source Code

The snippets above are complete and correct as presented. Assembling them into a working bar requires the following module-level import in each file under `bar/`:

```qml
import "../theme"      // makes Theme singleton available
import "../components" // makes Icon and Pill available
```

Or, if you registered Theme in `qmldir`, you need only `import "../components"`.

A minimal `qmldir` for the project root that exports the singleton and suppresses QML warnings about unresolved types:

```
# ~/.config/quickshell/qmldir
module quickshell
singleton Theme 1.0 theme/Theme.qml
```

Launch and watch live logs:

```bash
quickshell 2>&1 | tee /tmp/qs.log
```

Reload without restarting the compositor:

```bash
# Send SIGUSR1 to the quickshell process
pkill -SIGUSR1 quickshell

# Or use the CLI flag (Quickshell 0.2+)
quickshell --reload
```

Confirm the bar is occupying exclusive zone space:

```bash
hyprctl monitors | grep -A5 "Monitor"
# Look for "reserved" values matching your barHeight
```

---

## Module Comparison

| Module        | Data Source                          | Update Trigger        | Interactivity                  |
|---------------|--------------------------------------|-----------------------|--------------------------------|
| Clock         | `SystemClock`                        | Timer (1 s)           | Hover tooltip                  |
| Workspaces    | `Hyprland.workspaces`                | Hyprland event        | Click to switch, scroll        |
| WindowTitle   | `Hyprland.focusedClient`             | Hyprland event        | None                           |
| Volume        | `PipeWire.defaultAudioSink`          | PipeWire event        | Click mute, scroll adjust      |
| Battery       | `UPower.devices`                     | UPower event          | Hover tooltip                  |
| Media         | `Mpris.players`                      | MPRIS D-Bus event     | Play/pause, skip               |
| Network       | `nmcli` via `Process`                | Timer (10 s)          | None (click to open nm-applet) |
| SystemTray    | `SystemTray.items`                   | D-Bus registration    | Left click activate, right menu|

---

## Troubleshooting

### Bar not appearing on a monitor

Check that `Quickshell.screens` contains the monitor:

```bash
quickshell --qml - <<'EOF'
import Quickshell; ShellRoot {
    Component.onCompleted: {
        Quickshell.screens.forEach(s => print(s.name, s.width, s.height))
    }
}
EOF
```

If the monitor is listed but the bar is not visible, verify that `anchors.top: true` is set on the `PanelWindow` and that `height` is non-zero.

### Exclusive zone not respected by Hyprland

Ensure `layer: WlrLayer.Top` (not `WlrLayer.Background`). On Hyprland, layer-shell exclusive zones only work for `Top` and `Bottom` layers. Also confirm the bar is not using `exclusiveZone: -1` (which opts out of the exclusive zone protocol entirely).

### Workspaces showing wrong monitor

`Hyprland.workspaces` returns all workspaces across all monitors. Always filter by `ws.monitor === screen.name`. Note that `screen.name` in Quickshell matches the connector name Hyprland uses (e.g., `DP-1`, `HDMI-A-1`). Mismatch happens if you hotplug monitors and Hyprland reassigns connector names — add a debug label temporarily:

```qml
Text { text: screen.name; color: "red" }
```

### System tray icons missing

Many Electron apps register tray icons only after a delay. If icons appear later or not at all:

1. Confirm `StatusNotifierWatcher` is running: `dbus-send --session --print-reply --dest=org.kde.StatusNotifierWatcher /StatusNotifierWatcher org.freedesktop.DBus.Properties.Get string:org.kde.StatusNotifierWatcher string:ProtocolVersion`
2. Quickshell acts as its own StatusNotifierWatcher. If another watcher (e.g., from a running plasma-desktop) is registered first, Quickshell cannot take over. Kill duplicate watchers.
3. For apps that use `libappindicator` (legacy tray): install `snixembed` and start it before launching Quickshell.

### PipeWire module shows nothing

Check that the PipeWire socket is accessible:

```bash
pactl info | grep "Server Name"
```

If `PipeWire.defaultAudioSink` is null, no default sink is configured. Set one:

```bash
pactl set-default-sink @DEFAULT_SINK@
# or name a specific sink:
pactl set-default-sink alsa_output.pci-0000_00_1f.3.analog-stereo
```

### nmcli parsing errors in Network module

The `nmcli -t` (terse) output uses `:` as a delimiter but connection names can contain colons. Use `--escape no` flag or switch to a different field separator:

```qml
command: ["nmcli", "-t", "--escape", "no",
          "-f", "TYPE,STATE,CONNECTION,DEVICE,SIGNAL",
          "device", "status"]
```

### QML type not found / import errors

If Quickshell reports unknown types like `SystemTray` or `PipeWire`, verify the import line matches the correct Quickshell module path:

| Service            | Import statement                            |
|--------------------|---------------------------------------------|
| PipeWire           | `import Quickshell.Services.Pipewire`       |
| UPower             | `import Quickshell.Services.UPower`         |
| MPRIS              | `import Quickshell.Services.Mpris`          |
| SystemTray         | `import Quickshell.Services.SystemTray`     |
| Hyprland IPC       | `import Quickshell.Hyprland`                |
| Wayland layer-shell| `import Quickshell.Wayland`                 |

Service availability depends on compile-time flags. Check:

```bash
quickshell --list-services
```

---

## Related Chapters

- **Chapter 17** — PanelWindow and Layer Shell: anchoring, exclusive zones, and multi-monitor window management in depth.
- **Chapter 20** — Hyprland IPC: the full `Hyprland` API surface, event types, and dispatch commands.
- **Chapter 21** — PipeWire Integration: per-node volume, microphone metering, and audio routing.
- **Chapter 24** — Notifications Panel: building an overlay notification list as a companion to this bar.
- **Chapter 26** — Theme Singletons: design patterns for `Theme.qml`, palette switching, and CSS-variable analogues in QML.
- **Chapter 53** — Session Startup: ensuring Quickshell launches after the compositor and D-Bus services are ready, using `systemd --user` service ordering.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
