# Chapter 22 — System Services: Notifications, MPRIS, UPower, SystemTray

## Overview
Quickshell's service modules integrate with standard D-Bus services to build
notification popups, media controls, battery indicators, and system tray support.

## Sections

### 22.1 Notifications — Quickshell.Services.Notifications
```qml
NotificationServer {
    onNotification: notif => notifModel.insert(0, notif)
}
```
- `NotificationServer`: listens on `org.freedesktop.Notifications`
- Replaces external daemons like mako/dunst when active
- `Notification` properties: `summary`, `body`, `appName`, `appIcon`
- `urgency`: `NotificationUrgency.Low/Normal/Critical`
- `actions`: list of `NotificationAction` with `id` and `text`
- `expire_timeout`: auto-dismiss after N ms
- `notification.dismiss()` / `notification.invoke(actionId)`

#### Building a Notification Popup
```qml
PanelWindow {
    layer: WlrLayer.Overlay
    anchors.top: true; anchors.right: true
    ListView {
        model: notifModel
        delegate: NotificationCard { required property var modelData }
    }
}
```

### 22.2 MPRIS — Media Player Control
```qml
import Quickshell.Services.Mpris

Text {
    visible: MprisController.players.length > 0
    text: MprisController.players[0].trackTitle
}
Button {
    text: "⏭"
    onClicked: MprisController.players[0].next()
}
```
- `MprisController.players`: list of active MPRIS2 players
- `MprisPlayer` properties: `trackTitle`, `trackArtist`, `trackAlbum`
- `canPlay/canPause/canNext/canPrevious`: capability flags
- `playbackState`: `MprisPlaybackState.Playing/Paused/Stopped`
- `position` / `length`: current position and track length
- `loopState`, `shuffleState`
- Methods: `play()`, `pause()`, `playPause()`, `next()`, `previous()`, `seek(delta)`
- Album art: `trackArtUrl` as an image source

### 22.3 UPower — Battery and Power
```qml
import Quickshell.Services.UPower

Repeater {
    model: UPower.devices
    BatteryIndicator {
        required property var modelData
        level: modelData.percentage
        charging: modelData.state === UPowerDeviceState.Charging
    }
}
```
- `UPower.devices`: all power devices (batteries, UPS)
- `UPowerDevice` properties: `percentage`, `state`, `timeToEmpty`, `timeToFull`
- `UPowerDeviceType`: Battery, LinePower, UPS, etc.
- `UPowerDeviceState`: Charging, Discharging, FullyCharged, etc.
- `UPower.onBatteryStatus`: global power status
- Power profiles: `UPower.powerProfiles` for performance/balanced/saver

### 22.4 SystemTray
```qml
import Quickshell.Services.SystemTray

Repeater {
    model: SystemTray.items
    TrayIcon {
        required property SystemTrayItem modelData
        icon: modelData.icon
        tooltip: modelData.tooltip
        onClicked: modelData.activate(mouseX, mouseY)
        onRightClicked: modelData.menu?.open(mouseX, mouseY)
    }
}
```
- `SystemTray.items`: reactive list of tray items
- `SystemTrayItem` properties: `title`, `icon`, `tooltip`, `status`
- `SystemTrayItemStatus`: Active, Passive, NeedsAttention
- `menu`: `DBusMenuHandle` for right-click menus
- `activate(x, y)`: left-click action
- `secondaryActivate(x, y)`: middle-click action

### 22.5 Composing a Full Info Bar
- Clock + Workspaces + Media + Volume + Battery + Tray
- Layout patterns: `RowLayout`, spacers, `Repeater`
- Responsive sizing for different screen widths
- Per-module visibility toggles
