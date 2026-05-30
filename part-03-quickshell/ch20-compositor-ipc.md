# Chapter 20 — Compositor IPC: Hyprland and i3/Sway Modules

## Contents

- [Overview](#overview)
- [20.1 Quickshell.Hyprland Module Overview](#201-quickshellhyprland-module-overview)
- [20.2 HyprlandMonitor](#202-hyprlandmonitor)
- [20.3 HyprlandWorkspace](#203-hyprlandworkspace)
- [20.4 HyprlandToplevel (Window Objects)](#204-hyprlandtoplevel-window-objects)
- [20.5 HyprlandEvent (Raw Event Stream)](#205-hyprlandevent-raw-event-stream)
- [20.6 HyprlandFocusGrab](#206-hyprlandfocusgrab)
- [20.7 GlobalShortcut](#207-globalshortcut)
- [20.8 Dispatching Hyprland Commands](#208-dispatching-hyprland-commands)
- [20.9 The i3/Sway Module](#209-the-i3sway-module)
- [20.10 Writing a Workspace Bar: Complete Example](#2010-writing-a-workspace-bar-complete-example)
- [Troubleshooting](#troubleshooting)

---


## Overview

Quickshell ships with first-class IPC modules for the two most popular tiling Wayland compositors:
Hyprland and Sway (with its i3-compatible protocol). These modules expose compositor state — workspaces,
monitors, focused windows, running clients, and raw event streams — as reactive QML objects. Instead
of shelling out to `hyprctl` or `swaymsg` and parsing JSON in a timer loop, your shell components
subscribe to live data that updates the instant the compositor emits an event.

The two modules share the same design philosophy: typed singleton objects (`Hyprland`, `I3`) act as
entry points that own lists of monitors, workspaces, and clients. Individual items within those lists
are also reactive — when a workspace name changes on the compositor side, any QML binding that reads
`workspace.name` updates automatically. This chapter walks through every object in both modules,
shows complete working code for common ricing patterns, and closes with a full multi-monitor workspace
bar that you can drop into any Quickshell config.

Cross-references: For the Quickshell component model and `PanelWindow` positioning, see Ch 15. For
IPC-driven launch commands and session startup, see Ch 53. For styling the workspace buttons produced
here, see Ch 29 (theme engine integration).

---

## 20.1 Quickshell.Hyprland Module Overview

Hyprland exposes two Unix domain sockets in `$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/`.
The first (`/tmp/hypr/…/.socket.sock`) accepts JSON request/response commands identical to `hyprctl`
queries. The second (`/tmp/hypr/…/.socket2.sock`) streams newline-delimited events in real time.
Quickshell's `Quickshell.Hyprland` module manages both connections transparently — you never handle
file descriptors or parse JSON yourself.

When Quickshell starts, the module connects to both sockets, issues an initial batch of queries to
populate its object lists, and then transitions to event-driven updates. Every event received on
socket2 is parsed and routed to the relevant typed object. For example, a `workspace` event updates
the active workspace on the relevant `HyprlandMonitor`; an `activewindow` event updates
`Hyprland.activeToplevel`. Because QML property bindings are evaluated lazily on the next animation
frame, you get batched, glitch-free UI updates even when a rapid sequence of events arrives.

The module is available after a single import line. No additional setup, no daemon, no config:

```qml
import Quickshell.Hyprland
```

The singleton `Hyprland` exposes the following top-level properties:

| Property | Type | Description |
|---|---|---|
| `monitors` | `list<HyprlandMonitor>` | All connected monitors |
| `workspaces` | `list<HyprlandWorkspace>` | All existing workspaces |
| `toplevels` | `ObjectModel<HyprlandToplevel>` | All open windows |
| `focusedMonitor` | `HyprlandMonitor` | Monitor with keyboard focus |
| `activeToplevel` | `HyprlandToplevel` | Currently focused window (null if none) |
| `usingLua` | `bool` | Whether the Hyprland config uses Lua |
| `requestSocketPath` | `string` | Path to the IPC request socket |
| `eventSocketPath` | `string` | Path to the IPC event socket |

---

## 20.2 HyprlandMonitor

`HyprlandMonitor` represents one physical display. It is automatically populated from
`hyprctl monitors -j` on startup and kept in sync via events. In a multi-monitor setup, iterating
`Hyprland.monitors` is the canonical way to build per-screen panels — Quickshell ties each
`PanelWindow` to a screen by index, and `HyprlandMonitor.id` corresponds to that index.

The most important property is `activeWorkspace`, which is itself a `HyprlandWorkspace` reference.
When the user switches workspaces on a monitor, `activeWorkspace` changes and any bindings that
read it are re-evaluated. `focused` tells you which monitor currently holds the keyboard; this is
useful for highlighting the active screen indicator in a multi-monitor taskbar.

Full property reference for `HyprlandMonitor`:

| Property | Type | Description |
|---|---|---|
| `id` | `int` | Numeric monitor ID (matches Quickshell screen index) |
| `name` | `string` | Connector name, e.g. `DP-1`, `HDMI-A-1` |
| `description` | `string` | Human-readable monitor description |
| `width` | `int` | Horizontal resolution in pixels |
| `height` | `int` | Vertical resolution in pixels |
| `x` | `int` | X offset in the global coordinate space |
| `y` | `int` | Y offset in the global coordinate space |
| `scale` | `real` | HiDPI scale factor |
| `transform` | `int` | Rotation/flip transform (0–7, matching wl_output_transform) |
| `activeWorkspace` | `HyprlandWorkspace` | Workspace currently shown on this monitor |
| `focused` | `bool` | Whether this monitor has keyboard focus |

Example — a monitor info overlay for a diagnostic panel:

```qml
import Quickshell
import Quickshell.Hyprland

Repeater {
    model: Hyprland.monitors

    Column {
        required property HyprlandMonitor modelData

        Text {
            text: modelData.name
            font.bold: true
            color: modelData.focused ? "#cba6f7" : "#cdd6f4"
        }
        Text {
            text: "%1×%2 @%3× | ws: %4"
                .arg(modelData.width)
                .arg(modelData.height)
                .arg(modelData.scale)
                .arg(modelData.activeWorkspace.name)
            font.pixelSize: 11
            color: "#a6adc8"
        }
    }
}
```

When building a multi-monitor bar, pair each `HyprlandMonitor` with the corresponding Quickshell
screen. The `Quickshell.screens` list and `Hyprland.monitors` are ordered identically, so index
lookups are safe:

```qml
Variants {
    model: Quickshell.screens

    PanelWindow {
        required property QuickshellScreen modelData
        screen: modelData

        property HyprlandMonitor hyprMonitor:
            Hyprland.monitors[Quickshell.screens.indexOf(modelData)] ?? null

        WorkspaceBar { monitor: hyprMonitor }
    }
}
```

---

## 20.3 HyprlandWorkspace

`HyprlandWorkspace` models a single Hyprland workspace. The `Hyprland.workspaces` list contains
every workspace that currently exists — Hyprland creates workspaces lazily, so a workspace only
appears here after it has been used at least once (or was pre-created with `hyprctl dispatch
workspace`). Named workspaces and numeric workspaces are treated identically.

The `monitor` back-reference tells you which `HyprlandMonitor` a workspace is currently assigned
to. In Hyprland, workspaces can be moved between monitors at runtime, so this reference can change.
The `toplevels` list gives the windows on the workspace, and its `count` is useful for rendering
workspace occupancy indicators.

Full property reference for `HyprlandWorkspace`:

| Property | Type | Description |
|---|---|---|
| `id` | `int` | Numeric workspace ID |
| `name` | `string` | Workspace name (equals `id` for unnamed workspaces) |
| `monitor` | `HyprlandMonitor` | Monitor currently hosting this workspace |
| `toplevels` | `ObjectModel` | List of `HyprlandToplevel` on this workspace |
| `active` | `bool` | Whether this workspace is active on its monitor |
| `focused` | `bool` | Whether this workspace is on the focused monitor |
| `urgent` | `bool` | Whether any toplevel on this workspace has urgency |
| `hasFullscreen` | `bool` | Whether any toplevel on this workspace is fullscreen |
| `lastIpcObject` | `object` | Raw last IPC data object |

A workspace indicator button that shows occupancy and highlights the active workspace:

```qml
import Quickshell
import Quickshell.Hyprland
import QtQuick
import QtQuick.Controls

Repeater {
    // Filter to workspaces on the current monitor only
    model: Hyprland.workspaces.filter(ws => ws.monitor === targetMonitor)

    Button {
        required property HyprlandWorkspace modelData

        property bool isActive:
            modelData.id === targetMonitor.activeWorkspace.id

        width: 28
        height: 28

        background: Rectangle {
            radius: 4
            color: isActive
                ? "#cba6f7"
                : modelData.toplevels.count > 0 ? "#45475a" : "transparent"
            border.color: isActive ? "#cba6f7" : "#585b70"
            border.width: 1
        }

        contentItem: Text {
            text: modelData.name
            color: isActive ? "#1e1e2e" : "#cdd6f4"
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            font.pixelSize: 11
            font.bold: isActive
        }

        onClicked: Hyprland.dispatch("workspace " + modelData.id)
        onPressed: (event) => {
            if (event.button === Qt.RightButton)
                Hyprland.dispatch("movetoworkspace " + modelData.id)
        }

        ToolTip.visible: hovered
        ToolTip.text: modelData.name + " (" + modelData.toplevels.count + " windows)"
    }
}
```

To build a 1–10 fixed workspace bar (always showing all slots even if empty), use a `ListModel`
preloaded with IDs and look up the live workspace by ID:

```qml
ListView {
    model: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    orientation: ListView.Horizontal
    spacing: 4
    width: contentWidth

    delegate: WorkspaceButton {
        required property int modelData
        workspace: Hyprland.workspaces.find(ws => ws.id === modelData) ?? null
        id: modelData
    }
}
```

---

## 20.4 HyprlandToplevel (Window Objects)

`HyprlandToplevel` models an open window managed by Hyprland. The `Hyprland.toplevels` list is
kept current as windows open, close, move between workspaces, and change titles. The most commonly
accessed object is `Hyprland.activeToplevel`, which reflects the window currently holding keyboard
focus. When no window is focused (e.g., focus is on a Quickshell layer surface), `activeToplevel`
is null.

The `title` property holds the window title and updates live as applications change it (e.g., vim
changing the title to reflect the current file). The `workspace` back-reference tells you which
workspace a window lives on. The window's app-id / class can be accessed via the `.wayland`
sub-object's `appId` property.

Full property reference for `HyprlandToplevel`:

| Property | Type | Description |
|---|---|---|
| `handle` | `string` | Unique handle (stable for the window's lifetime) |
| `address` | `string` | Hex address of the window |
| `title` | `string` | Current window title |
| `workspace` | `HyprlandWorkspace` | Workspace containing this window |
| `monitor` | `HyprlandMonitor` | Monitor the window is on |
| `activated` | `bool` | Whether this toplevel is currently activated/focused |
| `urgent` | `bool` | Whether this window has urgency set |
| `wayland` | `Toplevel` | Wayland toplevel sub-object (exposes `appId`, etc.) |
| `lastIpcObject` | `object` | Raw last IPC data object |

A focused-window title display with app-id-based icon lookup:

```qml
import Quickshell
import Quickshell.Hyprland
import QtQuick

Row {
    spacing: 6
    visible: Hyprland.activeToplevel !== null

    Image {
        width: 16; height: 16
        source: Hyprland.activeToplevel
            ? "image://xdg-icon/" + Hyprland.activeToplevel.wayland.appId
            : ""
        fillMode: Image.PreserveAspectFit
    }

    Text {
        text: Hyprland.activeToplevel?.title ?? ""
        color: "#cdd6f4"
        font.pixelSize: 12
        elide: Text.ElideRight
        maximumLineCount: 1
        // Truncate very long titles
        width: Math.min(implicitWidth, 300)
    }
}
```

Building a taskbar that groups windows by workspace is straightforward with a filter:

```qml
Repeater {
    model: Hyprland.toplevels.filter(
        c => c.workspace.id === Hyprland.focusedMonitor.activeWorkspace.id
    )

    Button {
        required property HyprlandToplevel modelData
        text: modelData.wayland.appId
        highlighted: Hyprland.activeToplevel?.address === modelData.address
        onClicked: Hyprland.dispatch("focuswindow address:" + modelData.address)
    }
}
```

---

## 20.5 HyprlandEvent (Raw Event Stream)

`HyprlandEvent` exposes Hyprland's socket2 event stream as QML signals. Each signal corresponds
to one event type from the Hyprland IPC documentation. Because Quickshell's typed objects handle
most events internally, you typically only reach for `HyprlandEvent` when you need event data that
the high-level objects don't surface — for example, reacting to submap changes, pin/fullscreen
state transitions, or custom dispatch results.

`HyprlandEvent` is an instantiable QML type, not a singleton. Place one in your component tree
and connect to whichever signals you need. The `data` string passed to each signal contains the raw
comma-delimited payload from the socket, formatted identically to the output described in the
Hyprland wiki IPC page.

Commonly used signals on `HyprlandEvent`:

| Signal | Payload (`data`) | Description |
|---|---|---|
| `onActiveWindowV2Changed(data)` | `class,title` | Focus changed |
| `onWorkspaceChanged(data)` | `workspaceName` | Active workspace switched |
| `onMonitorFocused(data)` | `monitorName` | Focus moved to another monitor |
| `onWindowOpened(data)` | `addr,workspaceName,class,title` | New window created |
| `onWindowClosed(data)` | `addr` | Window destroyed |
| `onWindowMoved(data)` | `addr,workspaceName` | Window moved to another workspace |
| `onSubmapChanged(data)` | `submapName` | Hyprland submap changed |
| `onFullscreenChanged(data)` | `1` or `0` | Fullscreen state toggle |
| `onLayerOpened(data)` | `namespace` | Layer surface appeared |
| `onLayerClosed(data)` | `namespace` | Layer surface closed |

Example — submap indicator in the status bar:

```qml
import Quickshell
import Quickshell.Hyprland
import QtQuick

Item {
    property string activeSubmap: ""

    HyprlandEvent {
        onSubmapChanged: (data) => {
            activeSubmap = data   // empty string = reset to default
        }
    }

    Text {
        visible: activeSubmap !== ""
        text: "[ " + activeSubmap + " ]"
        color: "#f38ba8"
        font.bold: true
        font.pixelSize: 12
    }
}
```

Example — logging all events for debugging during development:

```qml
HyprlandEvent {
    onActiveWindowV2Changed: (d) => console.log("focus:", d)
    onWorkspaceChanged:      (d) => console.log("ws:", d)
    onWindowOpened:          (d) => console.log("open:", d)
    onWindowClosed:          (d) => console.log("close:", d)
    onSubmapChanged:         (d) => console.log("submap:", d)
}
```

---

## 20.6 HyprlandFocusGrab

`HyprlandFocusGrab` implements the `hyprland-focus-grab-v1` Wayland protocol extension. When
active, it captures all pointer and keyboard input on behalf of the Quickshell surface, preventing
clicks from reaching other windows. This is the correct mechanism for modal overlays — launcher
dialogs, confirmation prompts, context menus — that must capture input until dismissed.

Activating a focus grab requires that a Quickshell layer surface is currently visible. The grab
releases automatically when the surface is hidden, or you can call `grab.release()` explicitly.
Attempting a grab when no Quickshell surface is focused will silently fail, so always activate the
overlay surface first.

```qml
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland

FloatingWindow {
    id: launcher
    visible: false

    HyprlandFocusGrab {
        id: grab
        windows: [launcher]
        // Grab is active whenever `windows` list is non-empty and visible
    }

    function open() {
        launcher.visible = true
        grab.active = true
    }

    function close() {
        grab.active = false
        launcher.visible = false
    }

    // Close on Escape
    Keys.onEscapePressed: close()

    // Close on click outside
    onClickedOutside: close()

    LauncherContent {}
}
```

Note that `HyprlandFocusGrab` is specific to Hyprland and has no i3/Sway equivalent — on Sway,
modal input capture is handled at the application level via the `zwlr-layer-shell-v1` keyboard
interactivity mode. See Ch 17 for layer-shell keyboard interaction details.

---

## 20.7 GlobalShortcut

`GlobalShortcut` registers a keyboard shortcut using the `hyprland-global-shortcuts-v1` protocol.
This is the only Wayland-native mechanism for global hotkeys in Hyprland — it does not depend on
`xdg-open`, `ydotool`, or X11 hacks. The shortcut is registered as a named action that appears in
`hyprctl globalshortcuts` and is bound in `hyprland.conf` using the `global` dispatcher.

One `GlobalShortcut` instance registers one action. The binding in `hyprland.conf` can assign any
key combination. Multiple shortcuts for the same Quickshell process are supported.

```qml
import Quickshell.Hyprland

// In your root ShellRoot or a persistent component:
GlobalShortcut {
    name: "toggleBar"
    description: "Toggle the status bar visibility"
    onPressed: bar.visible = !bar.visible
    onReleased: { /* optional */ }
}

GlobalShortcut {
    name: "openLauncher"
    description: "Open the application launcher"
    onPressed: launcher.open()
}

GlobalShortcut {
    name: "openCalendar"
    description: "Toggle calendar popup"
    onPressed: calendar.toggle()
}
```

Corresponding `hyprland.conf` bindings:

```ini
# hyprland.conf
bind = SUPER, B,      global, quickshell:toggleBar
bind = SUPER, Space,  global, quickshell:openLauncher
bind = SUPER, C,      global, quickshell:openCalendar
```

The `quickshell:` prefix is the Quickshell process's registered namespace. The `name` field in QML
must match the part after the colon exactly. To discover all registered shortcuts at runtime:

```bash
hyprctl globalshortcuts
```

---

## 20.8 Dispatching Hyprland Commands

The `Hyprland` singleton provides a `dispatch` method for sending commands to the compositor at
runtime. It communicates over the request socket and returns asynchronously — QML bindings and the
event loop remain unblocked.

| Method | Equivalent hyprctl call | Description |
|---|---|---|
| `Hyprland.dispatch(cmd)` | `hyprctl dispatch <cmd>` | Run a Hyprland dispatcher |

Common dispatcher invocations:

```qml
// Workspace navigation
Hyprland.dispatch("workspace 3")
Hyprland.dispatch("workspace name:browser")
Hyprland.dispatch("workspace e+1")          // next relative workspace
Hyprland.dispatch("workspace e-1")          // previous relative workspace

// Move window to workspace
Hyprland.dispatch("movetoworkspace 5")
Hyprland.dispatch("movetoworkspacesilent 5") // without switching focus

// Window manipulation
Hyprland.dispatch("togglefloating")
Hyprland.dispatch("fullscreen 1")
Hyprland.dispatch("exec kitty")
Hyprland.dispatch("killactive")

// Focus
Hyprland.dispatch("focuswindow address:0x55a1234")
Hyprland.dispatch("focusmonitor 1")

// Submap
Hyprland.dispatch("submap reset")
Hyprland.dispatch("submap resize")
```

Live config changes via `keyword` dispatch (useful for toggle switches in a settings panel):

```qml
Switch {
    text: "Gaps"
    onCheckedChanged: {
        Hyprland.dispatch("keyword general:gaps_out " + (checked ? "8" : "0"))
        Hyprland.dispatch("keyword general:gaps_in " + (checked ? "4" : "0"))
    }
}

Switch {
    text: "Animations"
    onCheckedChanged:
        Hyprland.dispatch("keyword animations:enabled " + (checked ? "yes" : "no"))
}
```

---

## 20.9 The i3/Sway Module

Quickshell's `Quickshell.I3` module provides the same reactive pattern for compositors speaking
the i3 IPC protocol — primarily Sway, but also i3 itself when running under XWayland. The module
connects to the i3/Sway IPC socket discovered from `$SWAYSOCK` or `$I3SOCK`. Like the Hyprland
module, it populates its objects on startup and keeps them current via the subscription event socket.

The `I3` singleton's top-level API:

| Property / Method | Type | Description |
|---|---|---|
| `workspaces` | `list<I3Workspace>` | All workspaces |
| `monitors` | `list<I3Monitor>` | All monitors |
| `focusedWorkspace` | `I3Workspace` | Currently focused workspace |
| `dispatch(cmd)` | method | Run a Sway/i3 command |

`I3Workspace` properties:

| Property | Type | Description |
|---|---|---|
| `id` | `int` | Workspace numeric ID |
| `name` | `string` | Workspace name |
| `number` | `int` | Workspace number |
| `monitor` | `I3Monitor` | Monitor the workspace is on |
| `focused` | `bool` | Whether this is the active workspace on its monitor |
| `active` | `bool` | Whether this workspace is currently active on its monitor |
| `urgent` | `bool` | Whether any window on this workspace has urgency |
| `lastIpcObject` | `object` | Raw last IPC data object |

`I3Monitor` (monitor) properties:

| Property | Type | Description |
|---|---|---|
| `id` | `int` | Monitor numeric ID |
| `name` | `string` | Monitor name, e.g. `DP-1` |
| `power` | `bool` | Whether the monitor is powered on |
| `focused` | `bool` | Whether the monitor has keyboard focus |
| `activeWorkspace` | `I3Workspace` | Currently active workspace on this monitor |
| `x` | `int` | X position in global coordinate space |
| `y` | `int` | Y position in global coordinate space |
| `width` | `int` | Monitor width in pixels |
| `height` | `int` | Monitor height in pixels |
| `scale` | `real` | HiDPI scale factor |
| `lastIpcObject` | `object` | Raw last IPC data object |

A minimal Sway workspace bar — structurally identical to the Hyprland equivalent:

```qml
import Quickshell
import Quickshell.I3
import QtQuick
import QtQuick.Controls

Repeater {
    model: I3.workspaces.filter(ws => ws.monitor === targetMonitor)

    Button {
        required property I3Workspace modelData

        background: Rectangle {
            color: modelData.focused  ? "#cba6f7"
                 : modelData.urgent   ? "#f38ba8"
                 : modelData.active   ? "#45475a"
                 : "transparent"
            radius: 4
        }

        contentItem: Text {
            text: modelData.name
            color: modelData.focused ? "#1e1e2e" : "#cdd6f4"
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }

        onClicked: I3.dispatch("workspace " + modelData.name)
    }
}
```

Running arbitrary Sway commands from QML:

```qml
// Switch workspace
I3.dispatch("workspace 3")
I3.dispatch("workspace browser")

// Move window
I3.dispatch("move container to workspace 5")

// Focus monitor
I3.dispatch("focus output DP-1")

// Launch application
I3.dispatch("exec kitty")

// Reload config
I3.dispatch("reload")
```

Key differences between the Hyprland and i3/Sway modules:

| Feature | Hyprland Module | i3/Sway Module |
|---|---|---|
| Window object | `HyprlandToplevel` with full props | No per-window reactive object |
| Global shortcuts | `GlobalShortcut` QML type | Not available (use `bindsym` only) |
| Focus grab | `HyprlandFocusGrab` | Not available |
| Live config | `Hyprland.dispatch("keyword …")` | Not available |
| Raw events | `HyprlandEvent` signals | `I3Event` signals |
| Monitor type | `HyprlandMonitor` | `I3Monitor` |

The `I3Event` type mirrors `HyprlandEvent` in concept:

```qml
import Quickshell.I3

I3Event {
    onWorkspaceChanged: (data) => console.log("sway ws event:", JSON.stringify(data))
    onWindowFocused: (data) => console.log("focused:", data.name)
    onOutputChanged: updateMonitorBar()
}
```

---

## 20.10 Writing a Workspace Bar: Complete Example

This section assembles all the patterns from this chapter into a production-quality, multi-monitor
workspace bar. It works with Hyprland and can be adapted to Sway by swapping the module import and
type references. The bar spawns one `PanelWindow` per monitor via `Variants`, renders workspace
buttons filtered to that monitor, shows the focused window title on the primary monitor, and
supports both left-click (switch) and middle-click (move focused window) interactions.

The full implementation:

```qml
// File: workspace-bar/root.qml
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import QtQuick
import QtQuick.Layouts

ShellRoot {
    // Register global shortcuts
    GlobalShortcut {
        name: "toggleBar"
        description: "Toggle workspace bar"
        onPressed: {
            for (let w of barWindows.instances)
                w.visible = !w.visible
        }
    }

    Variants {
        id: barWindows
        model: Quickshell.screens

        PanelWindow {
            id: barWindow
            required property QuickshellScreen modelData

            screen: modelData
            anchors.top: true
            anchors.left: true
            anchors.right: true
            height: 32
            color: "#1e1e2e"

            // Map screen to Hyprland monitor by index
            property int screenIndex: Quickshell.screens.indexOf(modelData)
            property HyprlandMonitor monitor:
                Hyprland.monitors[screenIndex] ?? null

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 4

                // ── Workspace buttons ──────────────────────────────────
                Repeater {
                    model: Hyprland.workspaces.filter(
                        ws => ws.monitor?.id === barWindow.monitor?.id
                    ).sort((a, b) => a.id - b.id)

                    delegate: WorkspaceButton {
                        required property HyprlandWorkspace modelData
                        workspace: modelData
                        activeWorkspace: barWindow.monitor?.activeWorkspace ?? null
                    }
                }

                // ── Spacer ─────────────────────────────────────────────
                Item { Layout.fillWidth: true }

                // ── Focused window title (primary monitor only) ────────
                Text {
                    visible: barWindow.screenIndex === 0
                          && Hyprland.activeToplevel !== null
                    text: Hyprland.activeToplevel?.title ?? ""
                    color: "#cdd6f4"
                    font.pixelSize: 12
                    elide: Text.ElideRight
                    Layout.maximumWidth: 400
                }
            }
        }
    }
}
```

The `WorkspaceButton` component:

```qml
// File: workspace-bar/WorkspaceButton.qml
import Quickshell
import Quickshell.Hyprland
import QtQuick
import QtQuick.Controls

Button {
    id: root

    required property HyprlandWorkspace workspace
    required property HyprlandWorkspace activeWorkspace

    property bool isActive: workspace?.id === activeWorkspace?.id
    property bool hasWindows: (workspace?.toplevels.count ?? 0) > 0

    width: 26
    height: 26

    background: Rectangle {
        radius: 4
        color: root.isActive  ? "#cba6f7"
             : root.hasWindows ? "#313244"
             : "transparent"
        border.color: root.isActive ? "#cba6f7"
                    : root.hovered  ? "#585b70"
                    : "transparent"
        border.width: 1
        Behavior on color { ColorAnimation { duration: 80 } }
    }

    contentItem: Text {
        text: root.workspace?.name ?? ""
        color: root.isActive ? "#1e1e2e" : "#cdd6f4"
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        font.pixelSize: 11
        font.bold: root.isActive
    }

    // Left click: switch workspace
    onClicked: Hyprland.dispatch("workspace " + workspace.id)

    // Middle click: move focused window here silently
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.MiddleButton
        onClicked: Hyprland.dispatch(
            "movetoworkspacesilent " + root.workspace.id
        )
    }

    ToolTip.visible: hovered
    ToolTip.delay: 600
    ToolTip.text: root.workspace?.name + " · " + (root.workspace?.toplevels.count ?? 0) + " windows"
}
```

To use this bar, place both files in a directory and point Quickshell at the root:

```bash
quickshell -p ./workspace-bar
```

Or reference from your main `shell.qml` via a `Loader`:

```qml
Loader { source: "workspace-bar/root.qml" }
```

---

## Troubleshooting

**Quickshell fails to connect to Hyprland IPC at startup**

Verify that `$HYPRLAND_INSTANCE_SIGNATURE` is set in the environment where Quickshell launches.
If you start Quickshell from a systemd user service, the variable may not be inherited. Add an
`Environment=` or `ExecStartPre=` line that sources the Hyprland env file:

```ini
# ~/.config/systemd/user/quickshell.service
[Service]
ExecStartPre=/bin/sh -c 'systemctl --user import-environment HYPRLAND_INSTANCE_SIGNATURE'
ExecStart=/usr/bin/quickshell -p %h/.config/quickshell
```

Alternatively, launch via `hyprland.conf`:

```ini
exec-once = quickshell -p ~/.config/quickshell
```

**`Hyprland.monitors` is empty or stale**

This usually means the IPC socket path resolved to an old or dead instance. Check:

```bash
ls -la /tmp/hypr/
echo $HYPRLAND_INSTANCE_SIGNATURE
hyprctl monitors -j   # should return JSON
```

If `hyprctl` works but Quickshell doesn't, file a bug with `quickshell --log-rules "*.Hyprland=debug"` output.

**`Hyprland.workspaces` filter returns an empty list when filtering by monitor**

The `ws.monitor` back-reference may be null for workspaces that were recently created and haven't
yet received the full workspace event. Guard against this:

```qml
model: Hyprland.workspaces.filter(
    ws => ws.monitor !== null && ws.monitor.id === targetMonitor.id
)
```

**GlobalShortcut not firing**

Run `hyprctl globalshortcuts` and confirm your shortcut appears. Check that the `bind` line in
`hyprland.conf` uses `global` (not `globalshortcut`) and that the namespace matches the Quickshell
process name (default: `quickshell`). If you renamed the process with `--name`, use that name
instead:

```ini
bind = SUPER, B, global, myshell:toggleBar
```

```bash
quickshell --name myshell -p ~/.config/myshell
```

**i3/Sway module: `I3.workspaces` not updating**

Confirm `$SWAYSOCK` is exported. Sway does not always export this to child processes started via
`exec-once` equivalents. Add to `~/.config/sway/config`:

```
exec systemctl --user import-environment SWAYSOCK WAYLAND_DISPLAY DISPLAY
```

Then restart your Quickshell service.

**Performance: workspace bar causes frame drops**

If `Hyprland.toplevels.filter(...)` is called in a binding that fires on every event, the O(n)
filter runs on each rerender. Cache the filtered list in a property and use a `Connections` or
`onChanged` handler to refresh it only when `Hyprland.toplevels` actually changes:

```qml
property var visibleToplevels: []
Connections {
    target: Hyprland
    function onToplevelsChanged() {
        visibleToplevels = Hyprland.toplevels.filter(
            c => c.workspace.id === targetWorkspace.id
        )
    }
}
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
