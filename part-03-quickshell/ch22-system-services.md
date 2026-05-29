# Chapter 22 — System Services: Notifications, MPRIS, UPower, SystemTray

## Overview

Quickshell's service modules bridge your QML shell to the living ecosystem of D-Bus services
that desktop Linux depends on. Rather than spawning separate daemon processes and parsing their
output, these modules speak the underlying protocols directly, giving you reactive QML bindings
that update the moment a notification arrives, a media player changes track, a battery crosses a
threshold, or a tray item changes state.

This chapter covers the four primary service integrations shipped with Quickshell:
`Quickshell.Services.Notifications`, `Quickshell.Services.Mpris`,
`Quickshell.Services.UPower`, and `Quickshell.Services.SystemTray`. Each integrates with
well-defined freedesktop.org or KDE specifications, so the patterns you learn here apply
across virtually any modern Wayland compositor. By the end of the chapter you will have all
the building blocks to assemble a full, always-correct info bar.

Before diving in, ensure the Quickshell services module is available. On most distributions
you install it alongside the main Quickshell package. The import paths used throughout this
chapter assume Quickshell 0.1.0 or later:

```bash
# Arch / CachyOS
pacman -S quickshell

# Nix (flake)
inputs.quickshell.url = "github:quickshell-mirror/quickshell";
```

Cross-references: Ch 17 covers Quickshell window anchoring, Ch 18 covers the Quickshell.Io module (Process, Socket, IpcHandler),
and Ch 53 covers session startup and service ordering.

---

## 22.1 Notifications — `Quickshell.Services.Notifications`

Quickshell can act as the system-wide notification daemon by instantiating a
`NotificationServer` in your shell's QML tree. When the server is live it registers on the
`org.freedesktop.Notifications` D-Bus name, replacing any external daemon (mako, dunst,
swaync) for the life of the shell process. This is a significant difference from wrappers that
merely subscribe to a bus monitor — Quickshell owns the seat.

The `NotificationServer` is a singleton singleton-like singleton object: you create exactly
one per session. All incoming notifications fire the `onNotification` signal, which receives a
`Notification` object. That object is a live QML item: its properties update if the sending
application later calls the `org.freedesktop.Notifications.Notify` method with a replacement
ID, and it becomes invalid when dismissed.

### Notification Properties Reference

| Property | Type | Description |
|---|---|---|
| `id` | `int` | D-Bus notification ID |
| `appName` | `string` | Sending application name |
| `appIcon` | `string` | Icon name or path |
| `summary` | `string` | Title line |
| `body` | `string` | Body markup (may contain `<b>`, `<i>`, `<a href>`) |
| `urgency` | `NotificationUrgency` | Low, Normal, Critical |
| `expireTimeout` | `int` | Auto-dismiss after N ms; `-1` means server default |
| `actions` | `list<NotificationAction>` | List of action buttons |
| `hints` | `object` | Raw hint map from the sender |
| `image` | `string` | Inline image URI (e.g. album art via notify-send) |
| `resident` | `bool` | Do not close after action invocation |

### Minimal Notification Server

```qml
// shell.qml
import QtQuick
import Quickshell
import Quickshell.Services.Notifications

ShellRoot {
    // The server must be instantiated at the top level so it is always active.
    NotificationServer {
        id: notifServer
        onNotification: notif => {
            notifModel.insert(0, { notification: notif })
        }
    }

    ListModel { id: notifModel }

    // Popup layer anchored to the top-right corner of each screen
    Variants {
        model: Quickshell.screens
        PanelWindow {
            required property var modelData
            screen: modelData
            layer: WlrLayer.Overlay
            anchors.top: true
            anchors.right: true
            margins { top: 8; right: 8 }
            width: 380
            height: notifList.contentHeight + 16

            ListView {
                id: notifList
                anchors.fill: parent
                anchors.margins: 8
                spacing: 6
                model: notifModel
                delegate: NotificationCard {
                    required property var modelData
                    notification: modelData.notification
                    width: notifList.width
                }
            }
        }
    }
}
```

### Full Notification Card Component

```qml
// NotificationCard.qml
import QtQuick
import QtQuick.Layouts
import Quickshell.Services.Notifications

Rectangle {
    id: root
    required property Notification notification

    radius: 8
    color: "#1e1e2e"
    border.color: urgencyColor
    border.width: 2
    height: cardLayout.implicitHeight + 20

    readonly property color urgencyColor: {
        switch (notification.urgency) {
        case NotificationUrgency.Critical: return "#f38ba8"
        case NotificationUrgency.Low:      return "#585b70"
        default:                           return "#cba6f7"
        }
    }

    // Auto-dismiss timer
    Timer {
        id: dismissTimer
        interval: notification.expireTimeout > 0 ? notification.expireTimeout : 5000
        running: notification.expireTimeout !== 0
        onTriggered: notification.dismiss()
    }

    ColumnLayout {
        id: cardLayout
        anchors { left: parent.left; right: parent.right; top: parent.top }
        anchors.margins: 10
        spacing: 4

        RowLayout {
            Image {
                source: notification.appIcon
                width: 22; height: 22
                sourceSize: Qt.size(22, 22)
                fillMode: Image.PreserveAspectFit
                visible: notification.appIcon !== ""
            }
            Text {
                text: notification.appName
                color: "#a6adc8"
                font.pixelSize: 11
                Layout.fillWidth: true
            }
            Text {
                text: notification.summary
                color: "#cdd6f4"
                font.pixelSize: 13
                font.bold: true
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }
        }

        Text {
            text: notification.body
            color: "#bac2de"
            font.pixelSize: 12
            textFormat: Text.RichText
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
            visible: notification.body !== ""
        }

        // Action buttons
        RowLayout {
            visible: notification.actions.length > 0
            Repeater {
                model: notification.actions
                delegate: Rectangle {
                    required property NotificationAction modelData
                    color: actionMouse.containsMouse ? "#313244" : "#181825"
                    radius: 4
                    width: actionLabel.implicitWidth + 16
                    height: 26
                    Text {
                        id: actionLabel
                        anchors.centerIn: parent
                        text: modelData.text
                        color: "#cba6f7"
                        font.pixelSize: 11
                    }
                    MouseArea {
                        id: actionMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: notification.invoke(modelData.id)
                    }
                }
            }
        }
    }

    // Swipe to dismiss
    MouseArea {
        anchors.fill: parent
        drag.target: root
        drag.axis: Drag.XAxis
        onReleased: if (Math.abs(root.x) > 80) notification.dismiss()
    }
}
```

### Persisting Notification History

Many users want a notification center that shows past notifications even after they expire.
Because `Notification` objects become invalid after dismissal, you must copy relevant fields
into a persistent model before calling `dismiss()`:

```qml
NotificationServer {
    onNotification: notif => {
        historyModel.insert(0, {
            summary:  notif.summary,
            body:     notif.body,
            appName:  notif.appName,
            appIcon:  notif.appIcon,
            urgency:  notif.urgency,
            timestamp: new Date().toLocaleTimeString()
        })
        // Cap history at 50 entries
        if (historyModel.count > 50)
            historyModel.remove(50, historyModel.count - 50)
    }
}
ListModel { id: historyModel }
```

For persistent storage across shell restarts, pipe the model into a `JsonFileStorage` backed
by `~/.local/share/quickshell/notifications.json` (see Ch 18 for the storage pattern).

---

## 22.2 MPRIS — Media Player Control

The MPRIS2 specification (`org.mpris.MediaPlayer2` on D-Bus) is the standard interface for
controlling media players on Linux. Quickshell's `MprisController` singleton auto-discovers
every running player that registers an MPRIS2 service name and exposes them as a reactive
QML list. You never write bus code; you write data bindings.

`MprisController.players` is a live `QAbstractListModel`. When Spotify launches it appears in
the list. When you close it, it disappears. Each entry is an `MprisPlayer` with bound
properties that update as playback progresses — including `position`, which Quickshell
refreshes on a polling interval so you can drive a smooth progress bar.

### MprisPlayer Properties Reference

| Property | Type | Description |
|---|---|---|
| `identity` | `string` | Human-readable player name (e.g. "Spotify") |
| `desktopEntry` | `string` | `.desktop` file base name for icons |
| `trackTitle` | `string` | Current track title |
| `trackArtist` | `string` | Comma-joined artist string |
| `trackAlbum` | `string` | Album name |
| `trackArtUrl` | `string` | URI to album art image |
| `playbackState` | `MprisPlaybackState` | Playing, Paused, Stopped |
| `loopState` | `MprisLoopState` | None, Track, Playlist |
| `shuffleState` | `bool` | Shuffle active flag |
| `position` | `real` | Current position in microseconds |
| `length` | `real` | Track length in microseconds |
| `volume` | `real` | Player volume 0.0–1.0 |
| `canPlay` | `bool` | Player can accept Play |
| `canPause` | `bool` | Player can accept Pause |
| `canNext` | `bool` | Player can skip forward |
| `canPrevious` | `bool` | Player can skip back |
| `canSeek` | `bool` | Player accepts Seek calls |

### Minimal Now-Playing Widget

```qml
import QtQuick
import QtQuick.Layouts
import Quickshell.Services.Mpris

RowLayout {
    visible: MprisController.players.length > 0
    spacing: 8

    readonly property MprisPlayer player:
        MprisController.players.length > 0
            ? MprisController.players[0]
            : null

    Image {
        source: parent.player?.trackArtUrl ?? ""
        width: 40; height: 40
        fillMode: Image.PreserveAspectCrop
        visible: source !== ""
    }

    ColumnLayout {
        spacing: 1
        Text {
            text: parent.parent.player?.trackTitle ?? "—"
            color: "#cdd6f4"
            font.pixelSize: 12
            font.bold: true
            elide: Text.ElideRight
            Layout.maximumWidth: 180
        }
        Text {
            text: parent.parent.player?.trackArtist ?? ""
            color: "#a6adc8"
            font.pixelSize: 11
            elide: Text.ElideRight
            Layout.maximumWidth: 180
        }
    }

    RowLayout {
        spacing: 2
        readonly property MprisPlayer p: parent.player

        IconButton {
            icon: "media-skip-backward"
            enabled: parent.p?.canPrevious ?? false
            onClicked: parent.p?.previous()
        }
        IconButton {
            icon: parent.p?.playbackState === MprisPlaybackState.Playing
                  ? "media-playback-pause"
                  : "media-playback-start"
            enabled: parent.p?.canPlay ?? false
            onClicked: parent.p?.playPause()
        }
        IconButton {
            icon: "media-skip-forward"
            enabled: parent.p?.canNext ?? false
            onClicked: parent.p?.next()
        }
    }
}
```

### Progress Bar with Smooth Animation

Because `position` is polled rather than streamed, animating it requires a small local timer:

```qml
Item {
    width: 220; height: 4
    readonly property MprisPlayer player: MprisController.players[0] ?? null
    readonly property real progress:
        player && player.length > 0 ? player.position / player.length : 0

    Rectangle {
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
        color: "#cba6f7"
        width: parent.width * parent.progress

        Behavior on width {
            NumberAnimation { duration: 1000; easing.type: Easing.Linear }
        }
    }

    Rectangle {
        anchors.fill: parent
        color: "#313244"
        z: -1
        radius: 2
    }

    // Force a position refresh every second while playing
    Timer {
        interval: 1000
        running: player?.playbackState === MprisPlaybackState.Playing
        repeat: true
        onTriggered: { /* accessing player.position re-evaluates the binding */ }
    }
}
```

### Multi-Player Selector

When multiple players are active (e.g. Firefox + Spotify), you may want a chooser:

```qml
ListView {
    id: playerPicker
    orientation: ListView.Horizontal
    model: MprisController.players
    spacing: 4
    delegate: Rectangle {
        required property MprisPlayer modelData
        width: 28; height: 28
        radius: 4
        color: playerPicker.currentIndex === index ? "#313244" : "transparent"
        Image {
            anchors.centerIn: parent
            source: "image://icon/" + (modelData.desktopEntry || "audio-x-generic")
            width: 20; height: 20
        }
        MouseArea {
            anchors.fill: parent
            onClicked: playerPicker.currentIndex = index
        }
    }
}
// Bind your now-playing widget to:
// MprisController.players[playerPicker.currentIndex]
```

### Seeking

The `seek(delta)` method takes a delta in microseconds. For absolute positioning use
`setPosition(trackId, position)`. The `trackId` is available as `player.trackId`:

```qml
Slider {
    from: 0; to: player?.length ?? 1
    value: player?.position ?? 0
    onMoved: {
        var delta = value - (player?.position ?? 0)
        player?.seek(delta)
    }
}
```

---

## 22.3 UPower — Battery and Power Management

UPower is the Linux abstraction layer for power devices: laptop batteries, UPS units, mouse
batteries, keyboard batteries — anything that has a charge level and a state. Quickshell's
`UPower` singleton reflects the entire `org.freedesktop.UPower` D-Bus tree as a reactive QML
model. Updates arrive via D-Bus signals so there is no polling overhead.

For typical laptop shells the primary concern is the main battery. `UPower.displayDevice` is a
convenience property pointing to the "display" device that UPower designates as the composite
system battery — the most reliable way to get "the battery level" on multi-battery systems.

### UPowerDevice Properties Reference

| Property | Type | Description |
|---|---|---|
| `percentage` | `real` | Charge level 0–100 |
| `state` | `UPowerDeviceState` | Charging, Discharging, FullyCharged, Empty, PendingCharge, PendingDischarge |
| `deviceType` | `UPowerDeviceType` | Battery, LinePower, UPS, Mouse, Keyboard, etc. |
| `timeToEmpty` | `real` | Estimated seconds until empty |
| `timeToFull` | `real` | Estimated seconds until full |
| `energy` | `real` | Current energy in Wh |
| `energyFull` | `real` | Full design capacity in Wh |
| `voltage` | `real` | Current voltage in V |
| `isPresent` | `bool` | Physical battery present |
| `isRechargeable` | `bool` | Battery is rechargeable |

### Battery Icon Component

```qml
// BatteryIndicator.qml
import QtQuick
import Quickshell.Services.UPower

Row {
    spacing: 4

    readonly property UPowerDevice dev: UPower.displayDevice

    Text {
        text: {
            var lvl = dev?.percentage ?? 0
            if (dev?.state === UPowerDeviceState.Charging)        return "󰂄"
            if (dev?.state === UPowerDeviceState.FullyCharged)    return "󰁹"
            if (lvl >= 90) return "󰁹"
            if (lvl >= 70) return "󰂀"
            if (lvl >= 50) return "󰁾"
            if (lvl >= 30) return "󰁼"
            if (lvl >= 10) return "󰁺"
            return "󰂎"  // critical
        }
        color: {
            var lvl = dev?.percentage ?? 100
            if (lvl <= 10 && dev?.state !== UPowerDeviceState.Charging)
                return "#f38ba8"
            if (dev?.state === UPowerDeviceState.Charging)
                return "#a6e3a1"
            return "#cdd6f4"
        }
        font.family: "Nerd Fonts Symbols Only"
        font.pixelSize: 14
    }

    Text {
        text: (dev?.percentage?.toFixed(0) ?? "?") + "%"
        color: "#cdd6f4"
        font.pixelSize: 12
    }

    Text {
        visible: dev?.state === UPowerDeviceState.Discharging
                 && (dev?.timeToEmpty ?? 0) > 0
        text: {
            var secs = dev?.timeToEmpty ?? 0
            var h = Math.floor(secs / 3600)
            var m = Math.floor((secs % 3600) / 60)
            return h > 0 ? h + "h " + m + "m" : m + "m"
        }
        color: "#a6adc8"
        font.pixelSize: 11
    }
}
```

### All Devices (Peripherals)

```qml
import Quickshell.Services.UPower

Repeater {
    model: UPower.devices
    delegate: Row {
        required property UPowerDevice modelData
        visible: modelData.isPresent
                 && modelData.deviceType !== UPowerDeviceType.LinePower

        spacing: 4

        Text {
            text: {
                switch (modelData.deviceType) {
                case UPowerDeviceType.Mouse:    return "󰍽"
                case UPowerDeviceType.Keyboard: return "󰌌"
                case UPowerDeviceType.Headset:  return "󰋎"
                default:                        return "󰁹"
                }
            }
            font.family: "Nerd Fonts Symbols Only"
        }

        Text {
            text: modelData.percentage.toFixed(0) + "%"
            color: modelData.percentage < 15 ? "#f38ba8" : "#cdd6f4"
        }
    }
}
```

### Power Profile Integration

UPower exposes power profiles via `UPower.powerProfiles`. On systems with
`power-profiles-daemon` installed you can cycle between performance, balanced, and
power-saver:

```qml
import Quickshell.Services.UPower

Text {
    text: {
        switch (UPower.powerProfiles.activeProfile) {
        case "performance":  return "󱐌"
        case "power-saver":  return "󰌪"
        default:             return "󰓅"
        }
    }
    font.family: "Nerd Fonts Symbols Only"
    font.pixelSize: 14
    color: "#cdd6f4"

    MouseArea {
        anchors.fill: parent
        onClicked: {
            var profiles = ["balanced", "performance", "power-saver"]
            var cur = UPower.powerProfiles.activeProfile
            var next = profiles[(profiles.indexOf(cur) + 1) % profiles.length]
            UPower.powerProfiles.activeProfile = next
        }
    }
}
```

### Low Battery Notification Bridge

You can wire UPower events into Quickshell's own notification system or directly show a
dedicated overlay:

```qml
Connections {
    target: UPower.displayDevice
    function onPercentageChanged() {
        var dev = UPower.displayDevice
        if (dev.percentage <= 10
                && dev.state === UPowerDeviceState.Discharging) {
            lowBatteryPopup.visible = true
        }
    }
}

Rectangle {
    id: lowBatteryPopup
    visible: false
    // ... critical battery overlay UI
}
```

---

## 22.4 SystemTray

The `org.kde.StatusNotifierWatcher` protocol (also called SNI or AppIndicator) is the modern
replacement for the ancient XEMBED system tray. Applications like network managers, clipboard
managers, Discord, Telegram, and update notifiers register themselves as status notifier items
on this bus name. Quickshell's `SystemTray` singleton tracks all registered items as a
reactive list.

Unlike the old XEmbed protocol, SNI items provide vector-quality icons, rich D-Bus menu trees,
tooltips with markup, and three separate activation types (left, middle, right). Quickshell
exposes all of these cleanly.

### SystemTrayItem Properties Reference

| Property | Type | Description |
|---|---|---|
| `id` | `string` | Unique SNI item identifier |
| `title` | `string` | Item title |
| `icon` | `string` | Icon name or `image://` URI |
| `overlayIcon` | `string` | Overlay icon |
| `attentionIcon` | `string` | Attention state icon |
| `tooltip` | `string` | Tooltip text |
| `tooltipTitle` | `string` | Tooltip title line |
| `tooltipBody` | `string` | Tooltip body |
| `status` | `SystemTrayItemStatus` | Active, Passive, NeedsAttention |
| `category` | `string` | ApplicationStatus, Communications, etc. |
| `menu` | `DBusMenuHandle` | Right-click context menu |

### Minimal Tray Strip

```qml
import QtQuick
import QtQuick.Layouts
import Quickshell.Services.SystemTray

RowLayout {
    spacing: 2

    Repeater {
        model: SystemTray.items
        delegate: TrayItem {
            required property SystemTrayItem modelData
        }
    }
}
```

### Full TrayItem Component

```qml
// TrayItem.qml
import QtQuick
import Quickshell.Services.SystemTray

Rectangle {
    id: root
    required property SystemTrayItem modelData

    width: 26; height: 26
    radius: 4
    color: trayMouse.containsMouse ? "#313244" : "transparent"

    // Blink when attention is needed
    SequentialAnimation on opacity {
        running: modelData.status === SystemTrayItemStatus.NeedsAttention
        loops: Animation.Infinite
        NumberAnimation { to: 0.3; duration: 500 }
        NumberAnimation { to: 1.0; duration: 500 }
    }

    Image {
        anchors.centerIn: parent
        source: modelData.status === SystemTrayItemStatus.NeedsAttention
                    && modelData.attentionIcon !== ""
                ? modelData.attentionIcon
                : modelData.icon
        width: 18; height: 18
        sourceSize: Qt.size(18, 18)
        fillMode: Image.PreserveAspectFit
    }

    // Tooltip
    ToolTip.visible: trayMouse.containsMouse
    ToolTip.text: modelData.tooltipTitle !== ""
                  ? modelData.tooltipTitle
                  : modelData.title
    ToolTip.delay: 600

    MouseArea {
        id: trayMouse
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
        hoverEnabled: true

        onClicked: mouse => {
            switch (mouse.button) {
            case Qt.LeftButton:
                modelData.activate(mapToGlobal(mouse.x, mouse.y).x,
                                   mapToGlobal(mouse.x, mouse.y).y)
                break
            case Qt.MiddleButton:
                modelData.secondaryActivate(mapToGlobal(mouse.x, mouse.y).x,
                                            mapToGlobal(mouse.x, mouse.y).y)
                break
            case Qt.RightButton:
                if (modelData.menu)
                    modelData.menu.open(mapToGlobal(mouse.x, mouse.y).x,
                                        mapToGlobal(mouse.x, mouse.y).y)
                break
            }
        }
    }
}
```

### Filtering by Status

Many shells only show passive items on hover or in an overflow drawer. The
`SystemTrayItemStatus.Passive` state means "I exist but have nothing to say right now":

```qml
// Show only Active + NeedsAttention; fold Passive behind a toggle
property bool showAll: false

Repeater {
    model: SystemTray.items
    delegate: TrayItem {
        required property SystemTrayItem modelData
        visible: showAll
                 || modelData.status !== SystemTrayItemStatus.Passive
    }
}

Text {
    text: showAll ? "‹" : "›"
    MouseArea {
        anchors.fill: parent
        onClicked: showAll = !showAll
    }
}
```

### Requesting the Watcher Service

Some applications only register with the tray if `org.kde.StatusNotifierWatcher` is already
on the bus when they start. Quickshell registers the watcher automatically when
`SystemTray` is first instantiated, but if you are running a bare compositor without KDE or
GNOME, you may need to start the watcher before your application launcher:

```bash
# In your session startup (see Ch 53):
# Quickshell registers the watcher; just ensure it starts before apps that use the tray.
exec quickshell &
sleep 0.5
exec nm-applet --indicator &
exec blueman-applet &
```

---

## 22.5 Composing a Full Info Bar

With all four service modules understood, composing a production-quality bar is a matter of
assembling the components into a `PanelWindow` that persists across workspaces and screens.
The canonical Catppuccin Mocha bar shown here combines clock, workspaces (Ch 20), media,
volume (Ch 23), battery, and tray in a single `RowLayout`.

### Full Bar Shell

```qml
// bar.qml
import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import Quickshell.Services.Mpris
import Quickshell.Services.UPower
import Quickshell.Services.SystemTray
import Quickshell.Services.Notifications

ShellRoot {
    NotificationServer {
        id: notifServer
        onNotification: notif => notifModel.insert(0, { notification: notif })
    }
    ListModel { id: notifModel }

    Variants {
        model: Quickshell.screens
        PanelWindow {
            required property var modelData
            screen: modelData
            layer: WlrLayer.Top
            anchors { top: true; left: true; right: true }
            height: 34
            exclusiveZone: height
            color: "#1e1e2e"

            RowLayout {
                anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                spacing: 6

                // Left: Launcher + Workspaces (see Ch 20)
                WorkspaceStrip { screen: parent.screen }

                Item { Layout.fillWidth: true }

                // Center: Media
                MediaWidget { visible: MprisController.players.length > 0 }

                Item { Layout.fillWidth: true }

                // Right: Systray, Volume, Battery, Clock
                Repeater {
                    model: SystemTray.items
                    TrayItem { required property SystemTrayItem modelData }
                }

                VolumeSlider {}   // Ch 23

                BatteryIndicator {}

                ClockWidget {}
            }
        }
    }
}
```

### Layout Tips

- Use `Layout.fillWidth: true` on a single `Item` spacer to create a left/center/right split,
  or two spacers for a three-region layout.
- Wrap the tray `Repeater` in a `Row` with `clip: true` and a maximum width to prevent
  overflow on screens with many tray items.
- Use `Quickshell.screens` via `Variants` so each monitor gets its own bar instance. Each
  `PanelWindow` is independent and can be sized differently based on `screen.width`.
- For per-module visibility toggles, store booleans in a `QtObject` configuration block
  and bind each component's `visible` property to the flag.

### Per-Screen Responsive Sizing

```qml
PanelWindow {
    required property var modelData
    screen: modelData

    // Compact layout for small screens (e.g. a 13" laptop in portrait)
    readonly property bool compact: screen.width < 1400

    height: compact ? 28 : 34

    MediaWidget {
        visible: MprisController.players.length > 0 && !compact
    }
    BatteryIndicator {
        showTime: !compact
    }
}
```

### Notification Popup Overlay

Tie the notification server from 22.1 into the same `ShellRoot` so popups appear above the
bar on each screen:

```qml
Variants {
    model: Quickshell.screens
    PanelWindow {
        required property var modelData
        screen: modelData
        layer: WlrLayer.Overlay
        anchors { top: true; right: true }
        margins { top: 42; right: 8 }   // clear the bar
        width: 360
        height: notifList.contentHeight

        ListView {
            id: notifList
            anchors.fill: parent
            spacing: 6
            model: notifModel
            delegate: NotificationCard {
                required property var modelData
                notification: modelData.notification
                width: notifList.width
            }
        }
    }
}
```

---

## Troubleshooting

### NotificationServer does not receive any notifications

Verify that no other daemon owns `org.freedesktop.Notifications` before Quickshell starts.
Run `dbus-send --session --print-reply --dest=org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus.GetNameOwner string:org.freedesktop.Notifications`
and check which PID owns the name. Kill the competing daemon or remove it from autostart
(see Ch 53).

```bash
# Check who owns the notifications bus name
dbus-send --session --print-reply \
  --dest=org.freedesktop.DBus \
  /org/freedesktop/DBus \
  org.freedesktop.DBus.GetNameOwner \
  string:org.freedesktop.Notifications
```

### MprisController.players is always empty

MPRIS2 players must register a bus name matching `org.mpris.MediaPlayer2.*`. Confirm the
player is actually registered:

```bash
dbus-send --session --print-reply \
  --dest=org.freedesktop.DBus \
  /org/freedesktop/DBus \
  org.freedesktop.DBus.ListNames \
  | grep mpris
```

If the name appears but Quickshell does not reflect it, restart the shell — occasionally a
race during startup causes the watcher to miss the initial registration.

### UPower.displayDevice is null

This means UPower reported no display device. Check that `upowerd` is running:

```bash
systemctl status upower
# If inactive:
sudo systemctl start upower
sudo systemctl enable upower
```

On desktop machines without batteries, `UPower.displayDevice` is intentionally null. Guard
all battery UI with `visible: UPower.displayDevice !== null`.

### SystemTray shows no items even though nm-applet is running

`nm-applet` with the `--indicator` flag requires `org.kde.StatusNotifierWatcher` to already
be registered on the session bus. Launch Quickshell before `nm-applet` in your session startup
script. Alternatively, install `snixembed` as a fallback watcher that bridges old XEmbed
items to SNI.

```bash
# Verify the watcher is registered
dbus-send --session --print-reply \
  --dest=org.freedesktop.DBus \
  /org/freedesktop/DBus \
  org.freedesktop.DBus.GetNameOwner \
  string:org.kde.StatusNotifierWatcher
```

### Tray icons appear blurry or wrong size

SNI icons can be provided as themed icon names, raw pixel data, or URIs. If `modelData.icon`
is a raw `image://sni/...` URI, set `sourceSize` to the actual pixel dimensions of the icon
to prevent Qt from scaling a small bitmap:

```qml
Image {
    source: modelData.icon
    width: 20; height: 20
    sourceSize: Qt.size(20, 20)
    smooth: true
    mipmap: true
}
```

For theme icons, ensure the active icon theme is set via `QT_QPA_PLATFORM` or the Qt platform
theme. On non-KDE sessions, set `QT_QPA_PLATFORMTHEME=gtk3` in your environment (Ch 53).

### Notification body markup renders as raw HTML

`Text` items in Qt render HTML only when `textFormat: Text.RichText` is set. The
`notification.body` field from the freedesktop spec may contain `<b>`, `<i>`, `<a href>`, and
`<img>` tags. Always set `textFormat: Text.RichText` on body text and `textFormat:
Text.PlainText` on summary text to prevent injection via the summary field.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
