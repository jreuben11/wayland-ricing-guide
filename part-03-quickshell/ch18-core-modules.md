# Chapter 18 — Core Modules: Io, DBusMenu, Singletons

## Overview
The Quickshell.Io module is how your shell talks to the rest of the system:
spawning processes, reading files, parsing JSON, and communicating over sockets.

## Sections

### 18.1 Process — Running Commands
```qml
Process {
    id: proc
    command: ["hyprctl", "monitors", "-j"]
    running: true
    stdout: StdioCollector { onStreamFinished: parseOutput(text) }
}
```
- `command`: string list (always — never a shell string)
- `running`: set true to start, false to stop
- `stdin`, `stdout`, `stderr`: `StdioCollector` or `SplitParser`
- `onExited(exitCode, exitStatus)` signal
- Restart on change patterns

### 18.2 StdioCollector and SplitParser
- `StdioCollector`: accumulates all output until process exits
- `SplitParser`: splits on a delimiter (newline by default) — great for streaming
- `DataStream` + `JsonAdapter`: parse JSON output from processes
- `FileViewAdapter`: parse file content

### 18.3 FileView — Reading Files
```qml
FileView {
    path: "/sys/class/power_supply/BAT0/capacity"
    watchChanges: true
    onTextChanged: batteryLevel = parseInt(text)
}
```
- `path`: file to watch
- `watchChanges: true`: re-read when file changes (inotify-based)
- `text`: the file content as a string
- Use cases: `/proc/`, `/sys/`, config files, named pipes

### 18.4 Socket and SocketServer
- `Socket`: connect to a Unix domain socket (e.g., Hyprland socket2)
- `SocketServer`: listen for incoming socket connections
- Building a custom IPC endpoint
- Use case: controlling Quickshell from scripts

### 18.5 IpcHandler
- Expose Quickshell functions to external processes
- `quickshell ipc call <function>` from shell scripts
- Function declaration: `IpcHandler.defineFunction("toggleBar", () => {...})`

### 18.6 JsonAdapter — Parsing JSON
```qml
Process {
    command: ["hyprctl", "clients", "-j"]
    stdout: StdioCollector {
        onStreamFinished: {
            const clients = JSON.parse(text)
            // work with the array
        }
    }
}
```
- Direct `JSON.parse()` in JavaScript
- `JsonAdapter` for reactive binding to JSON properties
- Error handling patterns for malformed JSON

### 18.7 DBusMenu
- `DBusMenuHandle`: connect to a D-Bus menu (e.g., system tray menus)
- `DBusMenuItem`: individual menu item with label, icon, submenu
- Use case: right-click menus on tray icons

### 18.8 SystemClock and ElapsedTimer
```qml
Text {
    text: SystemClock.time.toLocaleTimeString(Qt.locale(), "HH:mm")
}
```
- `SystemClock.time`: updates every second by default
- `SystemClock.date`: the current date
- `SystemClock.updateInterval`: customize refresh rate
- `ElapsedTimer`: measure duration since start

### 18.9 ObjectModel and ObjectRepeater
- `ObjectModel`: a list of QML objects (not data)
- `ObjectRepeater`: instantiate from an ObjectModel
- Pattern for dynamic widget lists (notification stack, window buttons)
