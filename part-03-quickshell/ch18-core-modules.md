# Chapter 18 — Core Modules: Io, DBusMenu, Singletons

## Overview

The `Quickshell.Io` module is the primary interface between your Quickshell shell and the rest of the Linux system. It covers spawning external processes, reading files reactively, communicating over Unix sockets, parsing JSON, and integrating with D-Bus. Understanding these building blocks is essential before you can build anything non-trivial: a clock widget, a workspaces bar, a system tray, or a notification daemon all depend on one or more of these mechanisms.

This chapter walks through every major type in the `Io` module with complete, copy-paste-ready examples. Each section builds on the previous: you will see how `Process` feeds into `StdioCollector`, how `StdioCollector` feeds into `JsonAdapter`, and how `IpcHandler` lets external scripts drive your running shell. Readers who are already comfortable with QML property bindings will find these APIs natural; newcomers should first read Chapter 14 (QML Fundamentals) before proceeding.

Cross-references: Chapter 17 covers the Quickshell object lifecycle and `ShellRoot`. Chapter 19 covers the `Widgets` module. Chapter 22 covers Hyprland-specific IPC helpers built on top of these primitives. Chapter 53 covers session startup and service dependencies.

---

## 18.1 Process — Running Commands

`Process` is the fundamental mechanism for executing external programs from within a QML component. Unlike a raw `Qt.exec` call, `Process` is a declarative QML type: you describe what you want to run and under what conditions, and Quickshell manages the lifecycle. Every `Process` instance corresponds to exactly one child process at a time.

The `command` property must be a JavaScript string array — never a shell-interpolated string. This is not merely convention: it prevents shell injection vulnerabilities and avoids the ambiguity that arises when arguments contain spaces. If you need shell features like pipes or redirects, spawn `/bin/sh` explicitly with `-c` and a single argument string.

The `running` property controls whether the process is live. Setting it to `true` starts the process; setting it to `false` sends `SIGTERM`. The `onExited(exitCode, exitStatus)` signal fires when the process terminates. `exitStatus` is one of `Process.NormalExit` or `Process.CrashExit`. You can restart a process by toggling `running` off and on, or by using a `Timer` to poll on a fixed interval.

`stdin`, `stdout`, and `stderr` each accept a stdio handler object. For one-shot commands that produce a bounded amount of output, use `StdioCollector`; for long-running commands that stream line-by-line events, use `SplitParser`. Both are covered in Section 18.2.

```qml
// Fetch monitor layout from Hyprland on startup
import Quickshell
import Quickshell.Io

Process {
    id: monitorQuery
    command: ["hyprctl", "monitors", "-j"]
    running: true

    stdout: StdioCollector {
        onStreamFinished: {
            try {
                const monitors = JSON.parse(text)
                monitors.forEach(m => console.log(m.name, m.width + "x" + m.height))
            } catch (e) {
                console.warn("Failed to parse hyprctl output:", e)
            }
        }
    }

    onExited: (code, status) => {
        if (code !== 0)
            console.warn("hyprctl exited with", code)
    }
}
```

```qml
// Periodically run a command using a Timer
import Quickshell
import Quickshell.Io
import QtQuick

Item {
    property string cpuTemp: "?"

    Timer {
        interval: 5000
        running: true
        repeat: true
        onTriggered: tempProc.running = true
    }

    Process {
        id: tempProc
        command: ["cat", "/sys/class/thermal/thermal_zone0/temp"]
        stdout: StdioCollector {
            onStreamFinished: {
                const raw = parseInt(text.trim())
                cpuTemp = (raw / 1000).toFixed(1) + "°C"
                tempProc.running = false
            }
        }
    }
}
```

```qml
// Pipe through shell to use redirection or pipe operators
Process {
    id: shellCmd
    command: ["/bin/sh", "-c", "pactl get-sink-volume @DEFAULT_SINK@ | grep -oP '\\d+(?=%)' | head -1"]
    running: true
    stdout: StdioCollector {
        onStreamFinished: volumeLevel = parseInt(text.trim())
    }
}
```

Key properties summary:

| Property | Type | Notes |
|---|---|---|
| `command` | `list<string>` | Argv array. Index 0 is the executable. |
| `running` | `bool` | Start/stop the process |
| `workingDirectory` | `string` | CWD for the child process |
| `environment` | `var` | Map of env var overrides |
| `stdin` | `StdioHandler` | Input feed |
| `stdout` | `StdioHandler` | Output capture |
| `stderr` | `StdioHandler` | Error capture |

---

## 18.2 StdioCollector and SplitParser

`StdioCollector` and `SplitParser` are the two `StdioHandler` subtypes you will use most often. They serve different use-cases depending on whether the process is short-lived and produces a single chunk of output, or long-running and streams data incrementally.

`StdioCollector` accumulates all bytes written to the stream into a single `text` property. The `onStreamFinished` signal fires once, when the process closes that stream (either by exiting or explicitly closing stdout). This is the right choice for `hyprctl`, `jq`, `pactl`, `wpctl`, and any other command that runs, writes output, and exits. Do not use `StdioCollector` for daemons or long-running processes: memory will grow without bound.

`SplitParser` splits the stream on a configurable delimiter (default: `\n`) and emits `onRead(data)` for each chunk. This is the right choice for event streams: Hyprland's `socat` socket listener, `journalctl -f`, `inotifywait`, or any other command that continuously writes newline-terminated records. Each call to `onRead` delivers exactly one record, already stripped of the delimiter.

```qml
// StdioCollector: capture complete output
Process {
    id: wpctlQuery
    command: ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"]
    running: true
    stdout: StdioCollector {
        onStreamFinished: {
            // Output: "Volume: 0.65\n"
            const match = text.match(/Volume:\s*([\d.]+)/)
            if (match) root.volume = Math.round(parseFloat(match[1]) * 100)
        }
    }
}
```

```qml
// SplitParser: handle streaming events from Hyprland socket
import Quickshell
import Quickshell.Io

Process {
    id: hyprEventStream
    command: ["socat", "-U", "UNIX-CONNECT:/tmp/hypr/" + Hyprland.socketPath + "/.socket2.sock", "STDOUT"]
    running: true

    stdout: SplitParser {
        // onRead fires once per newline-delimited event
        onRead: (line) => {
            const sep = line.indexOf(">>");
            if (sep === -1) return
            const event = line.substring(0, sep)
            const data  = line.substring(sep + 2)
            EventRouter.dispatch(event, data)
        }
    }

    onExited: {
        // Auto-restart if the compositor restarts
        Qt.callLater(() => { running = true })
    }
}
```

```qml
// SplitParser with a custom delimiter (null-byte for NUL-separated records)
Process {
    command: ["find", "/home/user/.config", "-name", "*.conf", "-print0"]
    running: true
    stdout: SplitParser {
        separator: "\0"
        onRead: (path) => configFiles.append({ path: path })
    }
}
```

`DataStream` is a lower-level handler that gives you raw `ArrayBuffer` chunks via `onReceived(data)`. Use it when you need binary protocol parsing — for example, reading from a custom IPC daemon that sends length-prefixed binary frames.

---

## 18.3 FileView — Reading Files

`FileView` reads a file from disk and exposes its content as the `text` property. When `watchChanges` is `true`, it uses `inotify` under the hood to detect modifications and updates `text` automatically, triggering any dependent bindings. This makes it ideal for `/proc` and `/sys` pseudo-files that change in response to hardware events, as well as ordinary config files you want to reflect without restarting the shell.

The update is asynchronous: after the inotify event, Quickshell re-reads the file on the next event loop iteration. For files that change at very high frequency (e.g., `/proc/net/dev`), you may prefer a `Timer`-driven `Process { command: ["cat", ...] }` with a controlled interval so you can throttle reads explicitly.

`FileView` only reads files. It does not write. For writing, use `Process` with a command like `tee` or a custom script, or use `Socket` / `IpcHandler` to communicate with a daemon that owns the file.

```qml
// Battery level widget
import Quickshell
import Quickshell.Io
import QtQuick

Rectangle {
    property int level: 0
    property bool charging: false

    FileView {
        id: batCapacity
        path: "/sys/class/power_supply/BAT0/capacity"
        watchChanges: true
        onTextChanged: level = parseInt(text.trim())
    }

    FileView {
        id: batStatus
        path: "/sys/class/power_supply/BAT0/status"
        watchChanges: true
        onTextChanged: charging = (text.trim() === "Charging")
    }

    Text {
        text: (charging ? "⚡ " : "") + level + "%"
        color: level < 20 ? "red" : "white"
    }
}
```

```qml
// Read kernel parameters from /proc
FileView {
    id: loadAvg
    path: "/proc/loadavg"
    watchChanges: true
    onTextChanged: {
        const parts = text.trim().split(" ")
        root.load1  = parseFloat(parts[0])
        root.load5  = parseFloat(parts[1])
        root.load15 = parseFloat(parts[2])
    }
}
```

```qml
// Watch a config file and reload settings on change
FileView {
    id: themeFile
    path: StandardPaths.home + "/.config/myshell/theme.json"
    watchChanges: true
    onTextChanged: {
        try {
            const cfg = JSON.parse(text)
            Theme.accent  = cfg.accent  ?? "#88c0d0"
            Theme.bg      = cfg.bg      ?? "#2e3440"
            Theme.fg      = cfg.fg      ?? "#eceff4"
        } catch (e) {
            console.warn("theme.json parse error:", e)
        }
    }
}
```

If the file does not exist, `text` will be an empty string and `FileView` will log a warning. Check `FileView.error` (a `FileView.Error` enum) to distinguish "file not found" from "permission denied" from "no error".

---

## 18.4 Socket and SocketServer

`Socket` connects to an existing Unix domain socket. It is the building block for integrating with compositor IPC protocols, pipewire, DBus socket bridges, or any custom daemon that exposes a socket interface. You can both read from and write to the connected socket through its `stdio`-style handlers.

`SocketServer` creates a new Unix domain socket that other processes can connect to. Use it to make your shell scriptable: bind a socket, then have your shell scripts talk to it with `socat` or `nc`. Each incoming connection is represented as a `SocketConnection` object delivered to `onConnectionAdded`.

```qml
// Connect to Hyprland's control socket
import Quickshell.Io

Socket {
    id: hyprCtl
    path: "/tmp/hypr/" + Hyprland.instanceSignature + "/.socket.sock"

    // Send a command and read the one-shot response
    function dispatch(cmd) {
        hyprCtl.write(cmd + "\n")
    }

    stdout: SplitParser {
        onRead: (line) => console.log("hypr response:", line)
    }
}
```

```qml
// SocketServer: expose a control socket for shell scripts
import Quickshell.Io

SocketServer {
    id: controlSocket
    path: "/run/user/" + SystemInfo.userId + "/myshell.sock"
    listening: true

    onConnectionAdded: (conn) => {
        conn.stdout.onRead = (line) => handleCommand(line.trim(), conn)
    }

    function handleCommand(cmd, conn) {
        switch (cmd) {
        case "toggle-bar":
            barVisible = !barVisible
            conn.write("ok\n")
            break
        case "reload-config":
            configFile.reload()
            conn.write("ok\n")
            break
        default:
            conn.write("unknown command: " + cmd + "\n")
        }
        conn.close()
    }
}
```

```qml
// Write to a socket (e.g., send a command to swaymsg socket)
Socket {
    id: swaySocket
    path: Sway.socketPath

    function sendMsg(payload) {
        // sway IPC has a binary framing header; use DataStream for real usage
        write(payload)
    }

    onConnected: sendMsg(initialCommand)
}
```

Both `Socket` and `SocketServer` expose `connected` / `listening` boolean properties and `onError` signals. Always handle the error signal: sockets can fail to connect if the compositor hasn't started yet (see Chapter 53 for startup sequencing).

---

## 18.5 IpcHandler — Calling Into Quickshell from Scripts

`IpcHandler` exposes named JavaScript functions from your Quickshell instance to the outside world via the `quickshell ipc call` CLI subcommand. This is the recommended approach for scripting your shell without maintaining a persistent socket connection. The overhead is one fork/exec per call, which is acceptable for interactive use but not for tight loops.

Functions are registered by name and can accept string arguments. The return value (if any) is printed to stdout by the `quickshell ipc call` invocation. All registered functions run in the QML engine's main thread, so they have full access to your component tree.

```qml
// In your ShellRoot or a top-level Singleton
import Quickshell
import Quickshell.Io

IpcHandler {
    target: "bar"   // namespace for this handler

    function toggleBar() {
        barLayer.visible = !barLayer.visible
        return barLayer.visible ? "shown" : "hidden"
    }

    function setWorkspace(num) {
        HyprlandIpc.dispatch("workspace " + num)
    }

    function notify(title, body) {
        NotificationOverlay.push(title, body)
    }
}
```

Then from a shell script or keybind:

```bash
# Toggle the bar
quickshell ipc call bar toggleBar

# Switch to workspace 3
quickshell ipc call bar setWorkspace 3

# Push a notification
quickshell ipc call bar notify "Build done" "cargo build succeeded"
```

```qml
// Multiple IpcHandlers with different namespaces
IpcHandler {
    target: "volume"
    function up()   { VolumeControl.step(+5) }
    function down() { VolumeControl.step(-5) }
    function mute() { VolumeControl.toggleMute() }
}

IpcHandler {
    target: "brightness"
    function up()   { BrightnessControl.step(+10) }
    function down() { BrightnessControl.step(-10) }
}
```

You can discover available IPC targets with `quickshell ipc list`. Each `IpcHandler` must have a unique `target` string within a running Quickshell instance. If two handlers share a target, the second registration wins and a warning is logged.

---

## 18.6 JsonAdapter — Reactive JSON Parsing

While `JSON.parse()` inside a `StdioCollector.onStreamFinished` callback works for one-shot queries, `JsonAdapter` provides a reactive binding path. When paired with a `DataStream`, it parses JSON and exposes a `data` property that updates the QML binding graph whenever new JSON arrives. This is particularly useful for long-running processes that emit a stream of JSON objects.

For most common workflows — querying `hyprctl`, reading a config file, parsing `pactl` output — plain `JSON.parse()` is sufficient and easier to understand. Reach for `JsonAdapter` when you have a daemon process that emits JSON events on stdout and you want reactive QML properties without manual plumbing.

```qml
// One-shot JSON parsing (recommended for most cases)
Process {
    command: ["hyprctl", "clients", "-j"]
    running: true
    stdout: StdioCollector {
        onStreamFinished: {
            let clients
            try {
                clients = JSON.parse(text)
            } catch (e) {
                console.warn("JSON parse failed:", e, "\nRaw:", text.substring(0, 200))
                return
            }
            windowModel.clear()
            clients.forEach(c => windowModel.append({
                title:     c.title,
                workspace: c.workspace.id,
                address:   c.address,
                floating:  c.floating
            }))
        }
    }
}
```

```qml
// Streaming JSON events using JsonAdapter
import Quickshell.Io

Process {
    id: eventDaemon
    command: ["/usr/local/bin/myeventd", "--json-stream"]
    running: true

    stdout: SplitParser {
        onRead: (line) => {
            let obj
            try { obj = JSON.parse(line) } catch { return }
            EventBus.emit(obj.type, obj.payload)
        }
    }
}
```

```qml
// Robust JSON helper function — use this pattern throughout your shell
function safeParseJson(str, fallback) {
    try {
        return JSON.parse(str)
    } catch (e) {
        console.warn("safeParseJson failed:", e.message, "| input:", str.slice(0, 80))
        return fallback
    }
}

// Usage
Process {
    command: ["hyprctl", "workspaces", "-j"]
    running: true
    stdout: StdioCollector {
        onStreamFinished: {
            const ws = safeParseJson(text, [])
            workspaceModel.fromArray(ws)
        }
    }
}
```

Error handling is critical. `hyprctl` can return error strings instead of JSON when the compositor is busy or restarting. Always wrap `JSON.parse()` in a try-catch and provide a fallback.

---

## 18.7 DBusMenu — System Tray Menus

`DBusMenu` is the D-Bus protocol used by system tray applications to expose context menus. When you right-click a tray icon in a traditional desktop, the tray host requests the application's menu via the `com.canonical.dbusmenu` D-Bus interface. Quickshell implements this as a `DBusMenuHandle` that you attach to a tray icon, and a recursive `DBusMenuItem` tree that you render with a `Repeater`.

`DBusMenuHandle` takes a `service` (e.g., `"org.kde.StatusNotifierItem-12345-1"`) and an `objectPath` (e.g., `"/MenuBar"`), which you discover from the `StatusNotifierItem` D-Bus object. The handle fetches the menu asynchronously and exposes a `rootItem` of type `DBusMenuItem`.

Each `DBusMenuItem` has:

| Property | Type | Description |
|---|---|---|
| `label` | `string` | Display text (may contain `_` mnemonics) |
| `icon` | `string` | Icon name or path |
| `enabled` | `bool` | Grayed out if false |
| `visible` | `bool` | Hidden if false |
| `checkState` | `int` | 0=unchecked, 1=checked, 2=indeterminate |
| `children` | `list<DBusMenuItem>` | Submenu items |
| `isSeparator` | `bool` | Render as a visual separator |

```qml
// Minimal tray icon with right-click menu
import Quickshell
import Quickshell.DBus
import QtQuick
import QtQuick.Controls

Item {
    id: trayIcon
    property var notifierItem   // populated from StatusNotifierWatcher

    DBusMenuHandle {
        id: menuHandle
        service:    notifierItem.service
        objectPath: notifierItem.menuPath
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.RightButton
        onClicked: contextMenu.popup()
    }

    Menu {
        id: contextMenu
        Instantiator {
            model: menuHandle.rootItem ? menuHandle.rootItem.children : []
            delegate: MenuItem {
                required property var modelData
                text:    modelData.label.replace("_", "")
                enabled: modelData.enabled
                visible: !modelData.isSeparator
                onTriggered: modelData.activate()
            }
            onObjectAdded: (idx, obj) => contextMenu.insertItem(idx, obj)
            onObjectRemoved: (idx, obj) => contextMenu.removeItem(obj)
        }
    }
}
```

```qml
// Recursive submenu rendering
component DbusMenuEntry: MenuItem {
    required property var item

    text:    item.label.replace(/_([^_])/g, "$1")
    enabled: item.enabled

    // Attach submenu if this item has children
    menu: item.children.length > 0 ? subMenu : null

    Menu {
        id: subMenu
        Instantiator {
            model: item.children
            delegate: DbusMenuEntry { item: modelData }
            onObjectAdded: (i, obj) => subMenu.insertItem(i, obj)
            onObjectRemoved: (i, obj) => subMenu.removeItem(obj)
        }
    }

    onTriggered: item.activate()
}
```

Note: DBusMenu requires `quickshell-dbus` to be installed (it is a separate optional module on some distributions). See Chapter 31 for full system tray implementation including `StatusNotifierWatcher` and icon rendering.

---

## 18.8 SystemClock and ElapsedTimer

`SystemClock` is a Quickshell singleton that exposes the current date and time as reactive QML properties. It updates on a configurable interval (default: 1000 ms) and is far more efficient than spawning a `date` process on a timer, because all bindings share a single underlying `QTimer`.

`ElapsedTimer` measures the time elapsed since it was started. Use it for profiling, for computing "N seconds ago" timestamps on notifications, or for implementing progress bars with a time limit.

```qml
// Digital clock widget
import Quickshell
import QtQuick

Text {
    id: clockText
    // Format: "14:35" or "14:35:07" — adjust to taste
    text: SystemClock.time.toLocaleTimeString(Qt.locale(), "HH:mm")
    color: Theme.fg
    font.pixelSize: 14
    font.family: "JetBrains Mono"
}
```

```qml
// Full date + time widget with day-of-week
Column {
    Text {
        text: SystemClock.time.toLocaleTimeString(Qt.locale(), "HH:mm:ss")
        font.pixelSize: 16
    }
    Text {
        text: SystemClock.date.toLocaleDateString(Qt.locale(), "ddd dd MMM yyyy")
        font.pixelSize: 11
        opacity: 0.7
    }
}
```

```qml
// Higher-frequency update for a seconds display
SystemClock {
    id: fastClock
    updateInterval: 1000   // milliseconds; default is 1000
}

// For a sub-second display you would use updateInterval: 100
// but consider CPU cost — most users do not need sub-second clocks
```

```qml
// ElapsedTimer: show "N seconds ago" for a notification
import Quickshell

Item {
    property real notificationTime: 0

    ElapsedTimer {
        id: age
        running: true
    }

    Text {
        property real secondsAgo: (age.elapsed - notificationTime) / 1000
        text: secondsAgo < 60
            ? Math.round(secondsAgo) + "s ago"
            : Math.round(secondsAgo / 60) + "m ago"
    }

    Component.onCompleted: {
        notificationTime = age.elapsed
    }
}
```

`SystemClock` properties:

| Property | Type | Notes |
|---|---|---|
| `time` | `Date` | Current time, updated every `updateInterval` ms |
| `date` | `Date` | Current date (same object as `time`) |
| `updateInterval` | `int` | Update period in ms. Default 1000. |

---

## 18.9 ObjectModel and ObjectRepeater

`ObjectModel` stores a list of QML component instances (not plain data). `ObjectRepeater` instantiates components from an `ObjectModel` and inserts them into the visual tree. This pattern is appropriate when each item in a list is a complex, stateful QML object that should persist independently of list reordering — for example, the stack of active notifications, the list of open windows, or a dynamic set of workspace buttons.

Contrast with `ListModel` + `Repeater` (data-driven, items are recreated on change) and `Instantiator` (creates objects without placing them in a layout). Use `ObjectModel` when you need:
- Stable object identity across reorders
- Sharing object references between multiple views
- Inserting existing objects into a view

```qml
// Notification stack with ObjectModel
import Quickshell
import QtQuick

ObjectModel {
    id: notifStack

    function push(title, body, timeout) {
        const item = notifComponent.createObject(null, {
            title: title,
            body: body,
            timeout: timeout
        })
        notifStack.append(item)
        return item
    }

    function remove(item) {
        const idx = notifStack.indexOf(item)
        if (idx >= 0) notifStack.remove(idx)
        item.destroy()
    }
}

Component {
    id: notifComponent
    Rectangle {
        property string title: ""
        property string body: ""
        property int timeout: 5000
        // ... notification UI
    }
}

// Render the stack
Column {
    ObjectRepeater {
        model: notifStack
        // No delegate needed — ObjectRepeater directly parents each item here
    }
}
```

```qml
// Window buttons with stable order
ObjectModel {
    id: windowButtons
}

// Add a button when a window opens
Connections {
    target: HyprlandIpc
    function onClientAdded(client) {
        const btn = windowBtnComponent.createObject(null, { client: client })
        windowButtons.append(btn)
    }
    function onClientRemoved(address) {
        for (let i = 0; i < windowButtons.count; i++) {
            if (windowButtons.get(i).client.address === address) {
                const obj = windowButtons.get(i)
                windowButtons.remove(i)
                obj.destroy()
                break
            }
        }
    }
}

Row {
    ObjectRepeater { model: windowButtons }
}
```

Unlike `ListModel`, `ObjectModel` does not support `move()` without destroying and re-inserting items. For sortable lists, sort the backing array and reassign a new `ObjectModel` (or use `ListModel` with `Repeater`).

---

## 18.10 Putting It All Together — A Working Bar Module

The following is a minimal but real implementation of a bar that queries Hyprland for workspaces and displays them, using several of the patterns from this chapter.

```qml
// ~/.config/quickshell/bar/WorkspaceBar.qml
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import QtQuick
import QtQuick.Layouts

PanelWindow {
    id: root
    anchors { top: true; left: true; right: true }
    height: 32
    color: "#2e3440"

    // --- Workspace data ---
    property var workspaces: []
    property int activeWs: 1

    // Initial fetch
    Process {
        id: wsFetch
        command: ["hyprctl", "workspaces", "-j"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    root.workspaces = JSON.parse(text)
                } catch (e) {
                    console.warn("workspace fetch failed:", e)
                }
            }
        }
    }

    // Track active workspace from event stream
    Process {
        id: eventStream
        command: [
            "socat", "-U",
            "UNIX-CONNECT:/tmp/hypr/" + Qt.getenv("HYPRLAND_INSTANCE_SIGNATURE") + "/.socket2.sock",
            "STDOUT"
        ]
        running: true
        stdout: SplitParser {
            onRead: (line) => {
                if (line.startsWith("workspace>>")) {
                    root.activeWs = parseInt(line.split(">>")[1])
                    wsFetch.running = false
                    wsFetch.running = true   // re-query
                }
            }
        }
        onExited: Qt.callLater(() => { running = true })
    }

    // --- Clock ---
    FileView {
        id: batFile
        path: "/sys/class/power_supply/BAT0/capacity"
        watchChanges: true
    }

    // --- IPC: toggle bar from hyprland keybind ---
    IpcHandler {
        target: "bar"
        function toggle() { root.visible = !root.visible }
    }

    // --- Layout ---
    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 8
        anchors.rightMargin: 8

        Repeater {
            model: root.workspaces
            delegate: Rectangle {
                required property var modelData
                width: 24; height: 24
                radius: 4
                color: modelData.id === root.activeWs ? "#88c0d0" : "transparent"
                Text {
                    anchors.centerIn: parent
                    text: modelData.id
                    color: modelData.id === root.activeWs ? "#2e3440" : "#eceff4"
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        const p = hyprDispatch.createObject(null, {
                            command: ["hyprctl", "dispatch", "workspace", String(modelData.id)]
                        })
                        p.running = true
                    }
                }
            }
        }

        Item { Layout.fillWidth: true }

        Text {
            text: SystemClock.time.toLocaleTimeString(Qt.locale(), "HH:mm")
            color: "#eceff4"
            font.pixelSize: 13
        }

        Text {
            text: batFile.text.trim() + "%"
            color: "#eceff4"
            font.pixelSize: 13
            visible: batFile.text !== ""
        }
    }

    Component {
        id: hyprDispatch
        Process { running: false }
    }
}
```

---

## Troubleshooting

**Process never starts / `running: true` has no effect**

Verify the executable is on the shell's `PATH`. Quickshell does not inherit the interactive shell's `PATH`; it uses the systemd/DBus session environment. Check with:
```bash
quickshell ipc call debug dumpEnv
# or look at the process environment from Quickshell logs:
journalctl --user -u quickshell -n 50
```

If the binary is in `/usr/local/bin` or `~/.local/bin`, ensure those paths are in `$PATH` in your `~/.config/environment.d/*.conf` file (for systemd sessions) or `~/.pam_environment`.

**StdioCollector.onStreamFinished never fires**

The signal fires when the process closes stdout. Some programs buffer stdout when not connected to a terminal. Add `-u` flag (Python), use `stdbuf -oL`, or redirect through `unbuffer`. For processes that never exit (daemons), use `SplitParser` instead of `StdioCollector`.

**FileView shows empty text / doesn't update**

Check the file path is absolute. `~` is not expanded. Use `StandardPaths.home` for the home directory. For `/proc` and `/sys` files, ensure `watchChanges: true` — but note that some pseudo-files do not generate inotify events. For those, use a `Timer` + `Process { command: ["cat", ...] }` pattern.

**Socket.connected is false / won't connect**

The compositor socket may not exist yet at startup. Wrap the connection in a `Timer` with an initial delay, or use a `Connections` block on a compositor-ready signal. See Chapter 53 for the correct service ordering pattern.

**IpcHandler functions not found**

Run `quickshell ipc list` to see registered handlers. The Quickshell instance must be running. If you have multiple instances (multiple monitors with separate processes), the IPC command targets a specific instance by PID — see `quickshell ipc --help`.

**JSON parse errors from hyprctl**

Hyprland occasionally returns `"err"` or an error string instead of JSON when the compositor is initializing. Always guard with try-catch and treat a failed parse as an empty result rather than a fatal error. Retry on the next tick with `Qt.callLater`.

**DBusMenu shows no items**

The `service` and `objectPath` must match exactly what the `StatusNotifierItem` advertises. Use `busctl --user introspect <service> <path>` to inspect the available D-Bus interfaces. The menu path is often `/MenuBar` or `/com/canonical/menu/<pid>`.

---

## Summary

This chapter covered the complete `Quickshell.Io` toolkit:

- `Process` + `StdioCollector` / `SplitParser` for one-shot and streaming subprocess communication
- `FileView` with `watchChanges` for reactive file reading via inotify
- `Socket` / `SocketServer` for Unix domain socket IPC
- `IpcHandler` for exposing shell functions to external scripts via the `quickshell ipc` CLI
- `JsonAdapter` and safe `JSON.parse()` patterns for structured data
- `DBusMenu` for system tray context menus
- `SystemClock` and `ElapsedTimer` for time-based widgets
- `ObjectModel` / `ObjectRepeater` for stable, stateful lists

The patterns established here — especially the `Process` + `SplitParser` event-stream loop and the `IpcHandler` namespace — recur throughout the rest of the book. Chapter 19 builds on them to implement the full widget library. Chapter 22 encapsulates the Hyprland event stream into a proper singleton. Chapter 31 assembles the complete system tray.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
