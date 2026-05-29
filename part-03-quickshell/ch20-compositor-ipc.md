# Chapter 20 — Compositor IPC: Hyprland and i3/Sway Modules

## Overview
Quickshell has first-class IPC modules for Hyprland and i3/Sway, giving your
shell components live access to workspaces, monitors, focused windows, and events.

## Sections

### 20.1 Quickshell.Hyprland Module Overview
- Connects to Hyprland's IPC socket automatically
- Two sockets: request socket (JSON commands) and event socket (stream)
- All types update reactively on events

### 20.2 HyprlandMonitor
```qml
import Quickshell.Hyprland

Repeater {
    model: Hyprland.monitors
    Text { text: modelData.name + ": " + modelData.activeWorkspace.name }
}
```
- Properties: `id`, `name`, `width`, `height`, `x`, `y`, `scale`, `transform`
- `activeWorkspace`: the currently visible workspace
- `focused`: whether this monitor has keyboard focus

### 20.3 HyprlandWorkspace
```qml
Repeater {
    model: Hyprland.workspaces
    WorkspaceButton {
        required property var modelData
        active: modelData.id === Hyprland.focusedMonitor.activeWorkspace.id
        onClicked: Hyprland.dispatch("workspace " + modelData.id)
    }
}
```
- Properties: `id`, `name`, `monitor`, `windows` (count), `lastWindow`
- `Hyprland.workspaces`: all workspaces across all monitors
- Per-monitor workspace filtering pattern

### 20.4 HyprlandWindow
- Properties: `address`, `title`, `class`, `workspace`, `monitor`, `floating`
- `Hyprland.focusedClient`: the currently focused window
- Window class icons: mapping `class` to icon names

### 20.5 HyprlandEvent
```qml
HyprlandEvent {
    onActiveWindowV2Changed: console.log("focus:", data)
    onWorkspaceChanged: updateWorkspaceIndicator()
    onMonitorFocused: updateMonitorHighlight()
}
```
- Raw event stream from Hyprland's socket2
- Full event type list from Hyprland docs
- Use case: custom event handling not covered by typed objects

### 20.6 HyprlandFocusGrab
- Grabs all input for a Quickshell surface
- Use case: modal overlay that captures everything
- Releases on close

### 20.7 GlobalShortcut
```qml
GlobalShortcut {
    name: "toggleBar"
    description: "Toggle the status bar"
    onPressed: bar.visible = !bar.visible
}
```
- Registers a global shortcut via `hyprland-global-shortcuts-v1`
- Bound in `hyprland.conf`: `bind = SUPER, B, global, quickshell:toggleBar`

### 20.8 Dispatching Hyprland Commands
```qml
Hyprland.dispatch("movetoworkspace 3")
Hyprland.dispatch("exec kitty")
Hyprland.dispatch("submap reset")
```
- `Hyprland.dispatch(cmd)`: sends to request socket
- `Hyprland.keyword(key, value)`: set a config value at runtime
- `Hyprland.reload()`: reload Hyprland config

### 20.9 The i3/Sway Module
- `I3.workspaces`, `I3.monitors`, `I3.focusedWorkspace`
- `I3Monitor`, `I3Workspace`: same pattern as Hyprland module
- `I3Event`: raw i3 IPC event stream
- Running commands: `I3.command("workspace 3")`
- Differences from Hyprland module: what's missing/different

### 20.10 Writing a Workspace Bar: Complete Example
Full QML example combining HyprlandMonitor + HyprlandWorkspace + click dispatch
for a multi-monitor-aware workspace indicator.
