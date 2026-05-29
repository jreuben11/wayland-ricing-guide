# Appendix D — Quickshell API Quick Reference

## Import Map

```qml
import Quickshell                              // Core: ShellRoot, PanelWindow, Variants, etc.
import Quickshell.Io                           // Process, FileView, Socket, IpcHandler
import Quickshell.Wayland                      // ToplevelManager, WlSessionLock, ScreencopyView
import Quickshell.Hyprland                     // HyprlandMonitor, HyprlandWorkspace, GlobalShortcut
import Quickshell.I3                           // I3, I3Workspace (for Sway)
import Quickshell.Widgets                      // ClippingRectangle, IconImage
import Quickshell.DBusMenu                     // DBusMenuHandle, DBusMenuItem
import Quickshell.Services.Notifications       // NotificationServer, Notification
import Quickshell.Services.Mpris               // MprisController, MprisPlayer
import Quickshell.Services.Pipewire            // PipeWire, PwNode, PwNodeAudio
import Quickshell.Services.UPower              // UPower, UPowerDevice
import Quickshell.Services.SystemTray          // SystemTray, SystemTrayItem
import Quickshell.Services.Pam                 // PamContext (lockscreen auth)
import Quickshell.Services.Greetd              // Greetd (login greeter)
```

---

## Entry Point

Every Quickshell config must have a single `ShellRoot` at the top level of `shell.qml`:

```qml
// ~/.config/quickshell/shell.qml
import Quickshell

ShellRoot {
    // All top-level components go here
    Variants {
        model: Quickshell.screens
        Bar { screen: modelData }
    }
}
```

---

## Quickshell (Core)

### Global Singleton: `Quickshell`

| Property/Method | Type | Description |
|----------------|------|-------------|
| `screens` | `list<QsScreen>` | All connected outputs (reactive, updates on connect/disconnect) |
| `workingDirectory` | `string` | Path to the config directory |
| `reload()` | method | Hot-reload the entire configuration |
| `env(name)` | method | Read environment variable |

### QsScreen

| Property | Type | Description |
|----------|------|-------------|
| `name` | `string` | Output name (e.g. "DP-1", "eDP-1") |
| `width`, `height` | `int` | Resolution in logical pixels |
| `x`, `y` | `int` | Position in compositor space |
| `model` | `string` | Monitor model string |
| `refreshRate` | `real` | Refresh rate in Hz |
| `devicePixelRatio` | `real` | Scale factor (e.g. 1.5 for 150%) |

### Window Types

| Type | Protocol | Use case |
|------|----------|----------|
| `PanelWindow` | zwlr-layer-shell-v1 | Bars, overlays, wallpapers, OSDs |
| `FloatingWindow` | xdg-toplevel | Regular app windows from the shell |
| `PopupWindow` | xdg-popup | Transient menus, tooltips |

### PanelWindow

```qml
PanelWindow {
    screen: Quickshell.screens[0]
    anchors {
        top: true
        left: true
        right: true
    }
    exclusiveZone: height          // reserve space equal to bar height
    height: 36
    layer: WlrLayer.Top            // Background | Bottom | Top | Overlay
    keyboardFocus: WlrKeyboardFocus.None   // None | OnDemand | Exclusive

    // Content
    Rectangle {
        anchors.fill: parent
        color: "#1e1e2e"
    }
}
```

| Property | Type | Description |
|----------|------|-------------|
| `screen` | `QsScreen` | Target output (null = all outputs) |
| `anchors.top/bottom/left/right` | `bool` | Edge anchoring |
| `margins.top/bottom/left/right` | `int` | Margin from anchored edges (pixels) |
| `exclusiveZone` | `int` | Pixels to reserve (-1 = push others, 0 = no reserve) |
| `layer` | `WlrLayer` | Z-layer enum |
| `keyboardFocus` | `WlrKeyboardFocus` | Keyboard focus policy |
| `visible` | `bool` | Show/hide the surface |
| `width`, `height` | `int` | Surface dimensions |

### Multi-monitor with Variants

```qml
// Create one bar per connected monitor
Variants {
    model: Quickshell.screens

    Bar {
        required property var modelData    // the QsScreen
        screen: modelData
    }
}
```

### Utility Types

| Type | Key Properties | Description |
|------|---------------|-------------|
| `Variants` | `model: list` | One instance of `delegate` per item in model |
| `LazyLoader` | `active: bool`, `item` | Deferred component creation |
| `Scope` | — | Non-visual logical grouping; good for singletons |
| `SystemClock` | `time`, `date`, `format`, `updateInterval` | Reactive clock |
| `PersistentProperties` | — | Wraps properties that survive hot-reload |

```qml
// Lazy-load the notification center only when needed
LazyLoader {
    id: ncLoader
    active: false
    NotificationCenter { }
}

// Toggle:
// ncLoader.active = !ncLoader.active
```

### pragma Singleton

```qml
// Theme.qml — global theme object accessible from anywhere
pragma Singleton
import Quickshell

Singleton {
    readonly property color bg:      "#1e1e2e"
    readonly property color surface: "#313244"
    readonly property color text:    "#cdd6f4"
    readonly property color accent:  "#89b4fa"
    readonly property int radius:    8
    readonly property int barHeight: 36
}
```

```qml
// Any other file:
import ".."     // import parent directory
// Theme.bg, Theme.accent, etc. are available
```

---

## Quickshell.Io

### Process

```qml
// Run a command and read output
Process {
    id: volumeProc
    command: ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"]
    running: false

    stdout: StdioCollector {
        onStreamFinished: {
            // text contains full stdout
            console.log(text)
        }
    }

    onExited: (code, signal) => {
        if (code !== 0) console.log("Error: " + code)
    }
}

// Trigger: volumeProc.running = true  (or startDetached() for fire-and-forget)
```

| Property/Method | Type | Description |
|----------------|------|-------------|
| `command` | `list<string>` | Command and arguments |
| `running` | `bool` | Set true to start; set false to kill |
| `stdout` | `StdioCollector \| SplitParser` | Stdout handler |
| `stderr` | `StdioCollector` | Stderr handler |
| `stdin` | `string` | Data to write to stdin |
| `startDetached()` | method | Run without tracking |
| `onExited(code, signal)` | signal | Fires on process exit |

### StdioCollector vs SplitParser

```qml
// StdioCollector: accumulates all output, fires onStreamFinished when done
stdout: StdioCollector {
    onStreamFinished: doSomethingWith(text)
}

// SplitParser: fires onRead for each line (streaming, good for daemons)
stdout: SplitParser {
    splitMarker: "\n"
    onRead: data => {
        // data is one line
        parseEvent(data)
    }
}
```

### FileView

```qml
// Watch a file and react to changes
FileView {
    id: cpuTemp
    path: "/sys/class/hwmon/hwmon2/temp1_input"
    watchChanges: true

    onTextChanged: {
        root.temperature = parseInt(text.trim()) / 1000
    }
}

// Manually reload:
// cpuTemp.reload()
```

| Property | Type | Description |
|----------|------|-------------|
| `path` | `string` | Absolute path to the file |
| `text` | `string` | File contents (reactive) |
| `watchChanges` | `bool` | Reload when file changes on disk |
| `reload()` | method | Manually re-read the file |

### Socket (Unix Socket Client)

```qml
// Connect to Hyprland IPC socket directly
Socket {
    id: hyprSocket
    path: "/tmp/hypr/" + Quickshell.env("HYPRLAND_INSTANCE_SIGNATURE") + "/.socket.sock"

    onConnected: {
        send("j/clients\n")
    }

    onDisconnected: {
        console.log("Socket disconnected")
    }

    Component.onCompleted: connected = true
}
```

### IpcHandler (External IPC Server)

```qml
// Expose a function callable from shell scripts
IpcHandler {
    target: "myshell"   // maps to: qs ipc call myshell functionName args

    function setShader(name) {
        Process {
            command: ["hyprctl", "keyword", "decoration:screen_shader",
                      name ? "/path/shaders/" + name + ".frag" : ""]
            running: true
        }
    }
}
```

Call from shell: `qs ipc call myshell setShader crt`

---

## Quickshell.Wayland

### ToplevelManager — Window Taskbar

```qml
// List all open windows
ToplevelManager {
    id: toplevelMgr
}

Repeater {
    model: toplevelMgr.toplevels

    TaskButton {
        required property var modelData   // Toplevel
        text: modelData.title
        active: modelData.activated
        onClicked: modelData.activate()
    }
}
```

| Type | Property/Method | Description |
|------|----------------|-------------|
| `ToplevelManager` | `.toplevels: list<Toplevel>` | All open windows |
| `Toplevel` | `title`, `appId` | Window identity |
| `Toplevel` | `activated`, `maximized`, `minimized`, `fullscreen` | Window state |
| `Toplevel` | `activate()`, `close()`, `minimize()`, `requestSize(w,h)` | Control |

### WlSessionLock — Lockscreen

```qml
WlSessionLock {
    id: sessionLock
    locked: false

    onUnlocked: {
        locked = false
    }

    // One surface per monitor
    Variants {
        model: Quickshell.screens

        WlSessionLockSurface {
            required property var modelData
            screen: modelData

            LockScreen {
                anchors.fill: parent
                onUnlocked: sessionLock.locked = false
            }
        }
    }
}
```

### ScreencopyView — Live Screen Capture

```qml
// Show a live preview of a monitor
ScreencopyView {
    width: 320
    height: 180
    captureSource: Quickshell.screens[0]
    liveUpdates: true    // false = single capture
}
```

---

## Quickshell.Hyprland

### Accessing Hyprland State

```qml
// Import and use the Hyprland singleton
import Quickshell.Hyprland

// In any component:
Text {
    text: Hyprland.focusedClient ? Hyprland.focusedClient.class : ""
}

Repeater {
    model: Hyprland.focusedMonitor.workspaces
    WorkspaceButton {
        required property var modelData   // HyprlandWorkspace
        active: modelData === Hyprland.focusedMonitor.activeWorkspace
        onClicked: Hyprland.dispatch("workspace " + modelData.id)
    }
}
```

### HyprlandMonitor

| Property | Type | Description |
|----------|------|-------------|
| `id` | `int` | Monitor ID |
| `name` | `string` | Output name ("DP-1") |
| `width`, `height` | `int` | Resolution |
| `scale` | `real` | Scale factor |
| `activeWorkspace` | `HyprlandWorkspace` | Currently visible workspace |
| `workspaces` | `list<HyprlandWorkspace>` | All workspaces on this monitor |
| `focused` | `bool` | Whether this monitor has focus |

### HyprlandWorkspace

| Property | Type | Description |
|----------|------|-------------|
| `id` | `int` | Workspace number |
| `name` | `string` | Workspace name |
| `monitor` | `HyprlandMonitor` | Containing monitor |
| `windows` | `int` | Number of windows |
| `lastWindow` | `HyprlandWindow` | Most recently focused window |

### HyprlandWindow

| Property | Type | Description |
|----------|------|-------------|
| `address` | `string` | Unique hex address |
| `title` | `string` | Window title |
| `class` | `string` | App class (e.g. "kitty") |
| `workspace` | `HyprlandWorkspace` | Current workspace |
| `floating` | `bool` | Is floating |
| `fullscreen` | `bool` | Is fullscreen |
| `at` | `list<int>` | Position [x, y] |
| `size` | `list<int>` | Size [w, h] |
| `xwayland` | `bool` | Is an XWayland window |

### Dispatching and Keywords

```qml
// Dispatch actions
Hyprland.dispatch("exec kitty")
Hyprland.dispatch("workspace 2")
Hyprland.dispatch("movetoworkspace 3")
Hyprland.dispatch("killactive")

// Change config values live
Hyprland.keyword("general:gaps_out", "20")
Hyprland.keyword("decoration:rounding", "15")
```

### Global Shortcuts

```qml
GlobalShortcut {
    name: "toggleBar"
    description: "Toggle the status bar"
    onPressed: barWindow.visible = !barWindow.visible
}
```

Register via `hyprland.conf`: `bind = SUPER SHIFT, B, global, quickshell:toggleBar`

### HyprlandEvent — Raw Events

```qml
HyprlandEvent {
    onWorkspaceChanged: ws => console.log("Workspace: " + ws)
    onActiveWindowV2Changed: addr => console.log("Window: " + addr)
    onMonitorAdded: name => console.log("Monitor added: " + name)
}
```

---

## Quickshell.I3 (Sway)

```qml
import Quickshell.I3

// Workspace bar for Sway
Repeater {
    model: I3.workspaces

    WorkspaceButton {
        required property var modelData
        text: modelData.name
        active: modelData.focused
        urgent: modelData.urgent
        onClicked: I3.command("workspace " + modelData.name)
    }
}
```

| Type | Property/Method | Description |
|------|----------------|-------------|
| `I3` | `.workspaces`, `.monitors`, `.focusedWorkspace` | Global state |
| `I3` | `.command(cmd)` | Send i3/sway IPC command |
| `I3Monitor` | `name`, `rect`, `focused`, `currentWorkspace` | Output info |
| `I3Workspace` | `id`, `name`, `focused`, `urgent`, `visible` | Workspace state |

---

## Quickshell.Services.Notifications

```qml
NotificationServer {
    id: notifServer

    onNotification: notif => {
        toastPopup.show(notif)

        // Auto-dismiss normal urgency after 5 seconds
        if (notif.urgency !== NotificationUrgency.Critical) {
            Qt.callLater(() => notif.dismiss())
        }
    }
}
```

| Type | Property/Method | Description |
|------|----------------|-------------|
| `NotificationServer` | `onNotification(notif)` | New notification signal |
| `Notification` | `summary`, `body`, `appName`, `appIcon` | Content |
| `Notification` | `urgency`, `expireTimeout`, `actions` | Metadata |
| `Notification` | `image`, `hints` | Extra data |
| `Notification` | `dismiss()`, `invoke(actionId)` | Control |
| `NotificationUrgency` | Low / Normal / Critical | Enum |

---

## Quickshell.Services.Mpris

```qml
// Media info display
Text {
    text: {
        const player = MprisController.players[0]
        if (!player) return ""
        return player.trackTitle + " – " + player.trackArtist
    }
}

// Controls
Row {
    IconButton { onClicked: MprisController.players[0]?.previous() }
    IconButton { onClicked: MprisController.players[0]?.playPause() }
    IconButton { onClicked: MprisController.players[0]?.next() }
}
```

| Type | Property/Method | Description |
|------|----------------|-------------|
| `MprisController` | `.players: list<MprisPlayer>` | All active MPRIS players |
| `MprisPlayer` | `trackTitle`, `trackArtist`, `trackAlbum` | Track metadata |
| `MprisPlayer` | `trackArtUrl` | Album art URL |
| `MprisPlayer` | `position`, `length` | Playback position (ms) |
| `MprisPlayer` | `playbackState` | MprisPlaybackState enum |
| `MprisPlayer` | `play()`, `pause()`, `playPause()`, `next()`, `previous()` | Transport |
| `MprisPlayer` | `seek(deltaMs)`, `setPosition(ms)` | Position control |
| `MprisPlayer` | `volume`, `setVolume(v)` | Player volume (0.0–1.0) |
| `MprisPlaybackState` | Playing / Paused / Stopped | Enum |

---

## Quickshell.Services.Pipewire

```qml
// Volume OSD that reacts to default sink changes
Connections {
    target: PipeWire.defaultAudioSink?.audio

    function onVolumeChanged() {
        osd.showVolume(PipeWire.defaultAudioSink.audio.volume)
    }
    function onMutedChanged() {
        osd.showMute(PipeWire.defaultAudioSink.audio.muted)
    }
}

// Volume display
Text {
    text: {
        const sink = PipeWire.defaultAudioSink
        if (!sink?.audio) return "—"
        const pct = Math.round(sink.audio.volume * 100)
        return sink.audio.muted ? "󰝟 muted" : "󰕾 " + pct + "%"
    }
}
```

| Type | Property/Method | Description |
|------|----------------|-------------|
| `PipeWire` | `.nodes: list<PwNode>` | All PipeWire nodes |
| `PipeWire` | `.defaultAudioSink: PwNode` | Default speaker/headphones |
| `PipeWire` | `.defaultAudioSource: PwNode` | Default microphone |
| `PwNode` | `id`, `name`, `description` | Node identity |
| `PwNode` | `type: PwNodeType` | Sink / Source / Stream |
| `PwNode` | `running: bool` | Node active state |
| `PwNode` | `audio: PwNodeAudio` | Audio properties (null if not audio) |
| `PwNodeAudio` | `volume: real` | Volume 0.0–1.0 (can exceed 1.0 for boost) |
| `PwNodeAudio` | `muted: bool` | Mute state |
| `PwNodeAudio` | `channels: list<PwAudioChannel>` | Per-channel info |
| `PwLink` | `output: PwNode`, `input: PwNode` | Graph connection |

---

## Quickshell.Services.UPower

```qml
// Battery indicator
Text {
    text: {
        const bat = UPower.devices.find(d => d.type === UPowerDeviceType.Battery)
        if (!bat) return ""
        const pct = Math.round(bat.percentage)
        const icon = bat.state === UPowerDeviceState.Charging ? "󰂄" : "󰁹"
        return icon + " " + pct + "%"
    }
}
```

| Type | Property/Method | Description |
|------|----------------|-------------|
| `UPower` | `.devices: list<UPowerDevice>` | All power devices |
| `UPower` | `.onBattery: bool` | System on battery power |
| `UPower` | `.lidIsClosed: bool` | Laptop lid state |
| `UPowerDevice` | `percentage: real` | Charge percentage 0–100 |
| `UPowerDevice` | `state: UPowerDeviceState` | Charging/Discharging/Full/etc |
| `UPowerDevice` | `type: UPowerDeviceType` | Battery/LinePower/Ups/etc |
| `UPowerDevice` | `timeToEmpty: real` | Seconds until empty |
| `UPowerDevice` | `timeToFull: real` | Seconds until full |
| `UPowerDevice` | `energy`, `energyFull`, `energyRate` | Wh and W values |

---

## Quickshell.Services.SystemTray

```qml
// System tray
Row {
    Repeater {
        model: SystemTray.items

        TrayIcon {
            required property var modelData   // SystemTrayItem
            icon: modelData.icon
            tooltip: modelData.tooltip

            MouseArea {
                anchors.fill: parent
                onClicked: modelData.activate(mouseX, mouseY)
                onRightClicked: modelData.menu?.open(mouseX, mouseY)
            }
        }
    }
}
```

| Type | Property | Description |
|------|----------|-------------|
| `SystemTray` | `.items: list<SystemTrayItem>` | All registered tray items |
| `SystemTrayItem` | `title`, `tooltip`, `status` | Item metadata |
| `SystemTrayItem` | `icon: string` | Icon name or path |
| `SystemTrayItem` | `menu: DBusMenuHandle` | Context menu |
| `SystemTrayItem` | `activate(x,y)` | Primary click action |
| `SystemTrayItem` | `secondaryActivate(x,y)` | Middle click action |
| `SystemTrayItemStatus` | Active / Passive / NeedsAttention | Visibility hint |

---

## Quickshell.Services.Pam (Lockscreen)

```qml
PamContext {
    id: pam
    configurationName: "system-auth"   // PAM service name

    onConversationRequest: msg => {
        if (msg.type === PamMessageType.PromptEcho || msg.type === PamMessageType.Prompt) {
            // Show password field, then:
            // msg.respond(passwordField.text)
        }
    }

    onAuthComplete: (success, message) => {
        if (success) sessionLock.locked = false
        else shakeAnimation.start()
    }
}

// Start auth:
// pam.authenticate()
```

---

## Quickshell.Services.Greetd (Login Greeter)

```qml
Greetd {
    id: greetd

    onRequestSecret: msg => {
        // Show password input, then: greetd.respond(password)
    }

    onAuthComplete: {
        greetd.startSession(["Hyprland"])
    }

    onError: err => {
        errorLabel.text = err
    }
}

// Start login:
// greetd.createSession(usernameField.text)
```

---

## Quickshell.Widgets

```qml
// ClippingRectangle: clip children to rounded corners
ClippingRectangle {
    radius: 8
    color: "#1e1e2e"

    Image {
        anchors.fill: parent
        source: albumArtUrl
    }
}

// IconImage: resolve system icon by name
IconImage {
    source: "audio-volume-high"   // from icon theme
    implicitSize: 16
}
```

---

## DBusMenu

```qml
// Right-click context menu from a tray item
MouseArea {
    acceptedButtons: Qt.RightButton
    onClicked: {
        trayItem.menu?.open(mouseX, mouseY)
    }
}

// Render a menu manually:
DBusMenuHandle {
    id: menuHandle
    rootItem: trayItem.menu?.rootItem

    Repeater {
        model: menuHandle.rootItem?.children ?? []
        MenuItem {
            required property var modelData
            text: modelData.label
            enabled: modelData.enabled
            onTriggered: modelData.activate()
        }
    }
}
```

---

## Common Reactive Patterns

### Null-safe chaining
```qml
// Use ?. for nullable properties
text: PipeWire.defaultAudioSink?.audio?.volume ?? 0
```

### Computed property with complex logic
```qml
property string batteryIcon: {
    const bat = UPower.devices.find(d => d.type === UPowerDeviceType.Battery)
    if (!bat) return "󰂑"
    if (bat.state === UPowerDeviceState.Charging) return "󰂄"
    if (bat.percentage > 80) return "󰁹"
    if (bat.percentage > 50) return "󰁾"
    if (bat.percentage > 20) return "󰁼"
    return "󰁺"
}
```

### Polling with a Timer
```qml
Timer {
    interval: 2000
    running: true
    repeat: true
    onTriggered: cpuFile.reload()
}
```

### One-liner Process output
```qml
property string cpuTemp: ""

Process {
    command: ["bash", "-c", "cat /sys/class/hwmon/hwmon2/temp1_input"]
    running: true
    stdout: StdioCollector { onStreamFinished: cpuTemp = (parseInt(text)/1000).toFixed(0) + "°C" }
}
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
