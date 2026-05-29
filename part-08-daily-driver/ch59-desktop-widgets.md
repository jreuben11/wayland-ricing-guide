# Chapter 59 — Desktop Widgets, Overview Effects, and Conky Equivalents

## Overview

Desktop widgets — clocks, system monitors, calendars, and network meters rendered
directly on the wallpaper — and expose-style workspace overview effects are among the
most visually impactful ricing techniques available to Linux desktop users. Under X11,
tools like Conky exploited the root window, and compositors like KWin provided built-in
overview modes. Under Wayland the model changed completely: the root window is gone,
and every widget must be a proper Wayland surface anchored to a layer via the
`wlr-layer-shell` protocol extension.

This chapter covers the full toolkit: Quickshell for production-quality QML widgets,
the conky configuration language for users who already know it, compositor-native
overview and expose plugins (Hyprland hyprexpo, KWin), and custom window-switcher
implementations. It also addresses desktop icon grids, animated shader wallpapers, and
notification toasts styled as persistent desktop overlays.

Prerequisites: You should be comfortable with QML basics and have Quickshell installed
(see Ch 55). For Hyprland-specific features you need a recent git build of Hyprland
with `hyprpm` available. For animated wallpapers see Ch 27 (mpvpaper/swww).

---

## 59.1 Layer Shell Widgets vs. True Desktop Widgets

Under X11, "desktop widget" frameworks (Conky, Rainmeter) drew their output directly
onto the X root window (`_NET_WM_WINDOW_TYPE_DESKTOP`). The window manager treated
these surfaces as the desktop background, so windows would never overlap them without
explicit compositor intervention. Any X11 application could create such a surface, and
toolkits like GTK and Qt had built-in support for the `desktop` window type.

Wayland abolishes the root window entirely. Every on-screen surface must be created
through a specific Wayland protocol. The closest equivalent to X11 desktop widgets is
the `wlr-layer-shell` protocol, which defines four conceptual "layers" that surfaces
can occupy:

| Layer | z-order | Typical Use |
|-------|---------|-------------|
| `WlrLayer.Background` | Below wallpaper tools | Shader / video wallpapers |
| `WlrLayer.Bottom` | Above wallpaper, below windows | Clocks, monitors, calendar |
| `WlrLayer.Top` | Above windows | Persistent HUDs, status bars |
| `WlrLayer.Overlay` | Above everything | Screen lockers, OSD, overview |

Quickshell exposes these layers via the `PanelWindow.layer` property. Raw access is
also possible through `zwlr_layer_shell_v1` if you write a custom wayland client in C
or Rust, but Quickshell is the practical choice for most ricing work.

Note that not all compositors implement `wlr-layer-shell`. GNOME uses its own
`gtk-layer-shell` library. KDE Plasma has native widget support through Plasmoids. For
compositors in the `wlroots` family (Hyprland, Sway, niri, river, labwc) the protocol
is universally available.

An important difference from X11: `WlrLayer.Bottom` surfaces are **not** click-through
by default. To let mouse events pass through to the desktop below, set
`exclusiveZone: -1` and `input.passthrough: ShellLayerInput.Passthrough.Always` (or
the equivalent `Quickshell.layer_shell` keyboard-interactivity flag).

---

## 59.2 Quickshell Desktop Widgets

Quickshell is a QML-based Wayland shell toolkit built on top of Qt 6. Its
`PanelWindow` type wraps `wlr-layer-shell` with a clean QML API. This section builds
several production-ready widgets from scratch.

### Installation

```bash
# Arch Linux (AUR)
paru -S quickshell-git

# Build from source (requires Qt 6.6+, cmake, ninja)
git clone https://github.com/quickshell-mirror/quickshell
cd quickshell
cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build
sudo cmake --install build
```

Quickshell loads a root QML file, typically `~/.config/quickshell/shell.qml`, and
re-exports all `PanelWindow` instances as Wayland layer surfaces. Start it from your
session init script or `exec-once` directive (see Ch 53 for session startup patterns).

```bash
# Add to hyprland.conf
exec-once = quickshell
```

### Desktop Clock

The following clock widget anchors to the bottom-right corner of the primary screen,
renders a large time string in a Nerd Font, and uses text shadowing via Qt's
`Text.Outline` style for readability on any wallpaper:

```qml
// ~/.config/quickshell/widgets/DesktopClock.qml
import Quickshell
import Quickshell.Wayland
import QtQuick

PanelWindow {
    id: clockWindow
    screen: Quickshell.screens[0]
    layer: WlrLayer.Bottom
    anchors {
        bottom: true
        right: true
    }
    margins {
        bottom: 48
        right: 48
    }
    width: 320
    height: 110
    color: "transparent"
    exclusiveZone: 0
    input.passthrough: ShellLayerInput.Passthrough.Always

    Text {
        anchors.centerIn: parent
        text: Qt.formatTime(new Date(), "HH:mm")
        font {
            pixelSize: 72
            family: "JetBrainsMono Nerd Font"
            weight: Font.Light
        }
        color: "#cdd6f4"
        style: Text.Outline
        styleColor: "#80000000"
    }

    // Update every second via a Timer
    Timer {
        interval: 1000
        running: true
        repeat: true
        onTriggered: parent.requestUpdate()
    }
}
```

### System Monitor Widget

This widget reads CPU, memory, and network data from the Linux `/proc` filesystem via
Quickshell's `FileView` and a small helper `Process` call. The background uses a
semi-transparent dark fill so the meters remain legible over any wallpaper:

```qml
// ~/.config/quickshell/widgets/SysMonitor.qml
import Quickshell
import Quickshell.Wayland
import QtQuick
import QtQuick.Layouts

PanelWindow {
    id: sysmon
    screen: Quickshell.screens[0]
    layer: WlrLayer.Bottom
    anchors { top: true; left: true }
    margins { top: 64; left: 64 }
    width: 220
    height: 140
    color: "#cc1e1e2e"   // Catppuccin Mocha base, 80% opacity
    exclusiveZone: 0
    input.passthrough: ShellLayerInput.Passthrough.Always

    ColumnLayout {
        anchors { fill: parent; margins: 12 }
        spacing: 6

        StatRow { label: "CPU"; value: cpuPercent; color: "#89b4fa" }
        StatRow { label: "RAM"; value: memPercent; color: "#a6e3a1" }
        StatRow { label: "↑";  value: netUpKbps + " KB/s"; color: "#fab387" }
        StatRow { label: "↓";  value: netDnKbps + " KB/s"; color: "#89dceb" }
    }

    property real cpuPercent: 0
    property real memPercent: 0
    property string netUpKbps: "0"
    property string netDnKbps: "0"

    Process {
        id: statProc
        command: ["bash", "-c",
            "awk '/^cpu / {u=$2+$4; t=$2+$3+$4+$5; print u/t*100}' /proc/stat; " +
            "awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}END{print (t-a)/t*100}' /proc/meminfo"]
        running: false
        stdout: SplitParser {
            onRead: (line) => {
                if (sysmon.cpuPercent === 0) sysmon.cpuPercent = parseFloat(line)
                else sysmon.memPercent = parseFloat(line)
            }
        }
    }

    Timer {
        interval: 2000
        running: true
        repeat: true
        onTriggered: statProc.running = true
    }
}
```

### Calendar Widget

A minimal monthly calendar that highlights today's date uses QML's `GridLayout` and
standard JavaScript `Date` arithmetic:

```qml
// ~/.config/quickshell/widgets/DesktopCalendar.qml
import Quickshell
import Quickshell.Wayland
import QtQuick
import QtQuick.Layouts

PanelWindow {
    layer: WlrLayer.Bottom
    anchors { bottom: true; left: true }
    margins { bottom: 48; left: 48 }
    width: 240
    height: 200
    color: "#cc1e1e2e"
    exclusiveZone: 0
    input.passthrough: ShellLayerInput.Passthrough.Always

    property var today: new Date()
    property int year: today.getFullYear()
    property int month: today.getMonth()

    ColumnLayout {
        anchors { fill: parent; margins: 10 }

        Text {
            text: Qt.formatDate(today, "MMMM yyyy")
            color: "#cba6f7"
            font { pixelSize: 14; weight: Font.Bold }
            Layout.alignment: Qt.AlignHCenter
        }

        GridLayout {
            columns: 7
            columnSpacing: 4
            rowSpacing: 2

            Repeater {
                model: ["Su","Mo","Tu","We","Th","Fr","Sa"]
                Text { text: modelData; color: "#6c7086"; font.pixelSize: 11 }
            }

            Repeater {
                model: 42   // 6 weeks × 7 days
                delegate: Text {
                    property var d: dayForCell(index)
                    text: d.getMonth() === month ? d.getDate() : ""
                    color: d.toDateString() === today.toDateString()
                           ? "#f38ba8" : "#cdd6f4"
                    font.pixelSize: 12
                }
            }
        }
    }

    function dayForCell(index) {
        var firstDay = new Date(year, month, 1).getDay()
        var d = new Date(year, month, 1)
        d.setDate(d.getDate() - firstDay + index)
        return d
    }
}
```

---

## 59.3 conky on Wayland

Conky is a long-running system monitor that outputs formatted text and simple bar
graphs. Its Lua-based configuration language is well known in the ricing community.
Conky gained experimental Wayland support in version 1.19 via a native Wayland backend
that creates a `wlr-layer-shell` surface instead of an X11 window. As of 2025 the
support is functional for basic use but less feature-complete than the X11 backend.

### Installation

```bash
# Arch: the main package includes Wayland support
sudo pacman -S conky

# Ubuntu 24.04+
sudo apt install conky-all

# Verify Wayland support is compiled in
conky --version | grep -i wayland
```

### Minimal Wayland Config

```lua
-- ~/.config/conky/conky.conf
conky.config = {
    -- Wayland output (required)
    out_to_wayland    = true,
    out_to_x          = false,

    -- Window appearance
    own_window        = true,
    own_window_type   = 'desktop',   -- maps to WlrLayer.Bottom
    own_window_hints  = 'undecorated,below,skip_taskbar,skip_pager',
    own_window_transparent = true,
    own_window_colour = '000000',
    own_window_argb_visual = true,
    own_window_argb_value  = 180,

    -- Position (top-right)
    alignment         = 'top_right',
    gap_x             = 48,
    gap_y             = 64,

    -- Font
    use_xft           = false,    -- not relevant under Wayland
    font              = 'JetBrainsMono Nerd Font:size=10',

    -- Update interval (seconds)
    update_interval   = 2,
    double_buffer     = true,
}
```

### System Information Template

```lua
conky.text = [[
${color #cba6f7}┌─ SYSTEM ────────────────────────────${color}
${color #89b4fa}Host  ${color}${nodename}
${color #89b4fa}Uptime${color}  ${uptime_short}
${color #89b4fa}Kernel${color}  ${kernel}

${color #cba6f7}┌─ CPU ───────────────────────────────${color}
${color #89b4fa}Load  ${color}${cpu cpu0}%  ${cpubar 8,200 cpu0}
${color #89b4fa}Freq  ${color}${freq_g}GHz
${color #89b4fa}Temp  ${color}${hwmon 0 temp 1}°C

${color #cba6f7}┌─ MEMORY ────────────────────────────${color}
${color #a6e3a1}RAM   ${color}${mem} / ${memmax}  ${membar 8,200}
${color #a6e3a1}Swap  ${color}${swap} / ${swapmax}  ${swapbar 8,200}

${color #cba6f7}┌─ DISK ──────────────────────────────${color}
${color #f9e2af}/     ${color}${fs_used /} / ${fs_size /}  ${fs_bar 8,200 /}
${color #f9e2af}/home ${color}${fs_used /home} / ${fs_size /home}

${color #cba6f7}┌─ NETWORK ───────────────────────────${color}
${color #89dceb}enp3s0${color}  ↑${upspeed enp3s0}  ↓${downspeed enp3s0}
${color #89dceb}IP    ${color}${addr enp3s0}

${color #cba6f7}┌─ TOP PROCESSES ─────────────────────${color}
${color #f38ba8}${top name 1}${color}  ${top pid 1}  ${top cpu 1}%
${color #f38ba8}${top name 2}${color}  ${top pid 2}  ${top cpu 2}%
${color #f38ba8}${top name 3}${color}  ${top pid 3}  ${top cpu 3}%
]]
```

### Limitations of conky on Wayland

Conky's Wayland backend has several known limitations compared to the X11 version:

- **No Lua Cairo drawing** — Cairo-based custom graphs are not supported in the
  Wayland backend. Use Quickshell with a `Canvas` item instead.
- **Single monitor** — Conky cannot yet be pinned to a specific output by name; it
  defaults to the primary output.
- **No transparency compositing on all compositors** — ARGB transparency requires the
  compositor to support per-pixel alpha on `wlr-layer-shell` surfaces.
- **Font rendering** — `use_xft` has no effect; font selection uses Cairo/Pango
  directly.

For production ricing work, Quickshell is the recommended replacement. Use conky for
quick prototyping or when porting an existing conky config.

---

## 59.4 Workspace Overview / Expose Effects

The "Expose" effect (named after macOS Mission Control's predecessor) shows all open
windows as scaled thumbnails, allowing fast navigation. Implementation approaches
differ significantly between compositors.

### Hyprland hyprexpo Plugin

`hyprexpo` is a first-party Hyprland plugin that renders a grid of workspace thumbnails
using the compositor's internal frame capture. It is the most polished option for
Hyprland users.

```bash
# Install hyprpm and enable the plugin
hyprpm update
hyprpm add https://github.com/hyprwm/hyprland-plugins
hyprpm enable hyprexpo

# Verify
hyprpm list | grep hyprexpo
```

Add the following to `~/.config/hypr/hyprland.conf`:

```conf
plugin {
    hyprexpo {
        columns          = 3
        gap_size         = 5
        bg_col           = rgb(111111)
        workspace_method = center current   # or "first 1"
        enable_gesture   = true
        gesture_fingers  = 3
        gesture_distance = 300
        gesture_positive = true
    }
}

# Toggle with Super+Tab
bind = SUPER, TAB, hyprexpo:expo, toggle
# Or open only (useful for a dedicated expose key)
bind = SUPER, E, hyprexpo:expo, open
bind = SUPER, E, hyprexpo:expo, close
```

### KWin Overview Effect

On KDE Plasma/KWin the overview effect is built in:

```bash
# Enable via kwriteconfig (no restart needed after qdbus call)
kwriteconfig6 --file kwinrc --group Effect-overview --key Enabled true
qdbus6 org.kde.KWin /Effects reconfigureEffect overview
```

Bind a key:

```bash
kwriteconfig6 --file kglobalshortcutsrc \
    --group kwin --key "Overview" "Meta+Tab,none,Toggle Overview"
qdbus6 org.kde.kglobalaccel /component/kwin invokeShortcut "Overview"
```

### Quickshell Custom Overview (wlroots Compositors)

For compositors without a built-in overview (Sway, niri, river, labwc), Quickshell
provides `ToplevelManager` and `ScreencopyView` to build one from scratch:

```qml
// ~/.config/quickshell/overview/Overview.qml
import Quickshell
import Quickshell.Wayland
import Quickshell.Wayland.Screencopy
import QtQuick
import QtQuick.Layouts

PanelWindow {
    id: overview
    layer: WlrLayer.Overlay
    anchors { top: true; bottom: true; left: true; right: true }
    color: "#cc000000"
    visible: overviewActive
    exclusiveZone: -1

    property bool overviewActive: false

    Shortcut {
        sequence: "Super+Tab"
        onActivated: overview.overviewActive = !overview.overviewActive
    }

    MouseArea {
        anchors.fill: parent
        onClicked: overview.overviewActive = false
    }

    GridLayout {
        anchors.centerIn: parent
        columns: Math.ceil(Math.sqrt(ToplevelManager.toplevels.length))
        columnSpacing: 12
        rowSpacing: 12

        Repeater {
            model: ToplevelManager.toplevels
            delegate: Item {
                required property ToplevelHandle modelData
                width: 280
                height: 180

                Rectangle {
                    anchors.fill: parent
                    color: "#1e1e2e"
                    radius: 8

                    ScreencopyView {
                        anchors { fill: parent; margins: 4 }
                        captureSource: ScreencopySource.Toplevel {
                            toplevel: modelData
                        }
                        liveUpdates: overview.overviewActive
                    }

                    Text {
                        anchors { bottom: parent.bottom; horizontalCenter: parent.horizontalCenter }
                        anchors.bottomMargin: 4
                        text: modelData.title
                        color: "#cdd6f4"
                        font.pixelSize: 11
                        elide: Text.ElideRight
                        width: parent.width - 8
                        horizontalAlignment: Text.AlignHCenter
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: {
                            modelData.activate()
                            overview.overviewActive = false
                        }
                    }
                }
            }
        }
    }
}
```

---

## 59.5 Window Switcher (Alt+Tab)

The Alt+Tab window switcher is a closely related concept: an overlay that cycles
through open windows with keyboard navigation. Implementations range from simple
compositor built-ins to fully custom QML surfaces.

### Hyprland Built-in Cycling

Hyprland's `focuscurrentorlast` cycles between the two most recent windows, which
serves as a minimal Alt+Tab:

```conf
bind = ALT, Tab, cyclenext
bind = ALT SHIFT, Tab, cyclenext, prev
# Or use focuscurrentorlast for two-window toggle
bind = ALT, Tab, focuscurrentorlast
```

### hyprswitch

`hyprswitch` is a dedicated Hyprland window switcher that renders window thumbnails:

```bash
# Install
paru -S hyprswitch

# Daemon mode (must be running before the keybind fires)
exec-once = hyprswitch init --show-title &
```

```conf
# hyprland.conf — hold Alt, press Tab repeatedly, release Alt to confirm
bindr = ALT, Alt_L, exec, hyprswitch close --kill
binde = ALT, Tab,   exec, hyprswitch open --mod-key alt --key tab \
    --close mod-key-release --max-switch-offset 9
```

### Quickshell Window Switcher

```qml
// ~/.config/quickshell/switcher/WindowSwitcher.qml
import Quickshell
import Quickshell.Wayland
import QtQuick
import QtQuick.Layouts

PanelWindow {
    id: switcher
    layer: WlrLayer.Overlay
    anchors { top: true; bottom: true; left: true; right: true }
    color: "#cc000000"
    visible: false
    exclusiveZone: -1

    property int selectedIdx: 0

    function show() {
        selectedIdx = 0
        visible = true
    }

    function confirm() {
        var items = ToplevelManager.toplevels
        if (selectedIdx < items.length)
            items[selectedIdx].activate()
        visible = false
    }

    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Tab) {
            selectedIdx = (selectedIdx + 1) % ToplevelManager.toplevels.length
        } else if (event.key === Qt.Key_Escape) {
            visible = false
        } else if (event.key === Qt.Key_Return) {
            confirm()
        }
        event.accepted = true
    }

    ListView {
        id: listView
        anchors.centerIn: parent
        width: 500
        height: Math.min(contentHeight, 400)
        model: ToplevelManager.toplevels
        currentIndex: switcher.selectedIdx

        delegate: Rectangle {
            required property ToplevelHandle modelData
            required property int index
            width: listView.width
            height: 54
            color: index === switcher.selectedIdx ? "#313244" : "transparent"
            radius: 6

            RowLayout {
                anchors { fill: parent; leftMargin: 12; rightMargin: 12 }
                spacing: 12

                Image {
                    source: "image://xdgicon/" + modelData.appId
                    width: 32; height: 32
                    Layout.alignment: Qt.AlignVCenter
                }

                ColumnLayout {
                    spacing: 2
                    Text {
                        text: modelData.title
                        color: "#cdd6f4"
                        font.pixelSize: 13
                        elide: Text.ElideRight
                    }
                    Text {
                        text: modelData.appId
                        color: "#6c7086"
                        font.pixelSize: 11
                    }
                }
            }

            MouseArea {
                anchors.fill: parent
                onClicked: { switcher.selectedIdx = index; switcher.confirm() }
            }
        }
    }
}
```

---

## 59.6 Desktop Icon Grid

Wayland has no built-in desktop icon standard equivalent to the freedesktop
`_NET_WM_DESKTOP` approach. The options are:

| Approach | Compositor | Dependency | Notes |
|----------|-----------|------------|-------|
| `nemo --desktop` | Any | Nemo (Cinnamon) | Full drag-and-drop, thumbnails |
| `pcmanfm --desktop` | Any | PCManFM | Lightweight; needs `--profile` flag on Wayland |
| `nautilus --gapplication-service` | GNOME/Mutter | Nautilus | Only works under GNOME Wayland |
| Quickshell custom | wlroots | Quickshell | Fully custom layout |

### PCManFM Desktop on Wayland

```bash
# ~/.config/hypr/hyprland.conf
exec-once = pcmanfm --desktop --profile default

# Disable if using a standalone wallpaper tool (they conflict)
# exec-once = swww-daemon
```

PCManFM on Wayland requires GTK4 and `gtk-layer-shell`. The `--desktop` flag creates
a `WlrLayer.Bottom` surface that renders `~/Desktop/` contents. Right-click menus and
drag operations work, but live icon updates are slower than under X11.

### Quickshell Icon Grid

```qml
// ~/.config/quickshell/desktop/IconGrid.qml
import Quickshell
import Quickshell.Wayland
import QtQuick
import QtQuick.Layouts

PanelWindow {
    layer: WlrLayer.Bottom
    anchors { top: true; left: true; right: true; bottom: true }
    color: "transparent"
    exclusiveZone: 0
    input.passthrough: ShellLayerInput.Passthrough.Always

    Flow {
        anchors { top: parent.top; left: parent.left; margins: 24 }
        spacing: 16

        Repeater {
            model: DesktopEntries.desktopFiles("~/Desktop")
            delegate: DesktopIcon {
                required property var modelData
                size: 64
                label: modelData.name
                icon: modelData.icon
                onDoubleClicked: Qt.openUrlExternally(modelData.path)
            }
        }
    }
}
```

---

## 59.7 Animated and Shader Wallpapers

### GLSL Shader Wallpapers via Quickshell

Quickshell's `ShaderEffect` item renders a GLSL fragment shader at full frame rate,
making it suitable for generative art wallpapers. Place the shader in
`~/.config/quickshell/shaders/plasma.frag`:

```glsl
// plasma.frag — classic plasma effect
#version 440
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float time;
    vec2  resolution;
} ubuf;

void main() {
    vec2 uv = qt_TexCoord0;
    float t = ubuf.time * 0.5;
    float v = sin(uv.x * 10.0 + t)
            + sin(uv.y * 10.0 + t)
            + sin((uv.x + uv.y) * 10.0 + t)
            + sin(sqrt(uv.x*uv.x + uv.y*uv.y) * 10.0);
    vec3 col = 0.5 + 0.5 * cos(vec3(0,2,4) + v * 3.14159);
    fragColor = vec4(col * ubuf.qt_Opacity, ubuf.qt_Opacity);
}
```

```qml
// ~/.config/quickshell/wallpaper/ShaderWallpaper.qml
import Quickshell
import Quickshell.Wayland
import QtQuick

PanelWindow {
    id: wall
    layer: WlrLayer.Background
    anchors { top: true; bottom: true; left: true; right: true }
    color: "black"
    exclusiveZone: -1

    ShaderEffect {
        anchors.fill: parent
        fragmentShader: Qt.resolvedUrl("../shaders/plasma.frag")
        property real time: 0.0
        property vector2d resolution: Qt.vector2d(wall.width, wall.height)

        NumberAnimation on time {
            from: 0; to: 3600
            duration: 3600000   // 1 hour loop
            loops: Animation.Infinite
        }
    }
}
```

### mpvpaper (Video Wallpaper)

`mpvpaper` is a dedicated video wallpaper tool for wlroots compositors (see Ch 27 for
full setup). Quick reference:

```bash
# Install
paru -S mpvpaper

# Start with a looping video on all outputs
mpvpaper -o "loop" '*' ~/Videos/wallpaper.mp4

# Exec from Hyprland config
exec-once = mpvpaper -o "loop --no-audio" '*' ~/Videos/wallpaper.mp4
```

---

## 59.8 Notification Toasts as Desktop Widgets

Standard Wayland notification daemons (mako, dunst, SwayNotificationCenter) display
ephemeral popups that disappear after a timeout. There are scenarios where you want
persistent, large, or permanently visible status panels using the same notification
data. Quickshell can subscribe to the D-Bus `org.freedesktop.Notifications` interface
and render custom notification surfaces.

### Persistent Corner Notifications

```qml
// ~/.config/quickshell/notifications/ToastArea.qml
import Quickshell
import Quickshell.Wayland
import Quickshell.DBus
import QtQuick
import QtQuick.Layouts

PanelWindow {
    layer: WlrLayer.Top
    anchors { bottom: true; right: true }
    margins { bottom: 16; right: 16 }
    width: 340
    height: toastColumn.implicitHeight + 16
    color: "transparent"
    exclusiveZone: 0

    DBusServiceWatcher {
        watchedServices: ["org.freedesktop.Notifications"]
        onServiceRegistered: notifProxy.connectToService()
    }

    ColumnLayout {
        id: toastColumn
        anchors { bottom: parent.bottom; right: parent.right }
        spacing: 8

        Repeater {
            model: notificationModel
            delegate: ToastCard {
                required property var modelData
                summary: modelData.summary
                body:    modelData.body
                urgency: modelData.urgency
                // urgency == 2 (Critical) gets a red border
                borderColor: urgency === 2 ? "#f38ba8" : "#313244"
            }
        }
    }
}
```

### Urgency-Based Layer Selection

A common pattern is to display critical notifications on `WlrLayer.Overlay` (above
full-screen applications) while non-critical ones use `WlrLayer.Top`:

```qml
PanelWindow {
    id: critAlert
    layer: WlrLayer.Overlay
    visible: hasCriticalNotification
    anchors { top: true; horizontalCenter: true }
    margins.top: 0
    width: 600
    height: 80
    color: "#cc1e1e2e"

    Text {
        anchors.centerIn: parent
        text: "⚠ " + criticalMessage
        color: "#f38ba8"
        font { pixelSize: 20; weight: Font.Bold }
    }
}
```

---

## 59.9 Comparison Table: Widget Toolkits

| Feature | Quickshell (QML) | Conky | PCManFM Desktop | Plasmoids |
|---------|-----------------|-------|-----------------|-----------|
| Layer-shell native | Yes | Partial (1.19+) | Via GTK layer shell | Yes (Plasma) |
| Custom rendering | Full Qt/QML | Template text + bars | No | Full QML |
| Live data sources | Process, DBus, FileView | Built-in variables | No | DataSource plugins |
| Multi-monitor | Per-screen PanelWindow | Primary only | All outputs | Per-screen |
| Animations | Qt animations, shaders | No | No | Qt animations |
| Configuration language | QML / JavaScript | Lua | GUI / config file | QML |
| Wayland stability | Excellent | Experimental | Good | Excellent (KDE) |
| Resource usage | Medium (Qt 6) | Low | Medium | Medium |

---

## Troubleshooting

### Widget not appearing on screen

1. Confirm your compositor supports `wlr-layer-shell`:
   ```bash
   wayland-info | grep zwlr_layer_shell
   # Should print: zwlr_layer_shell_v1  version 4 (or higher)
   ```
2. Check that `quickshell` is running and has not crashed:
   ```bash
   pgrep -a quickshell
   journalctl --user -u quickshell -n 50
   ```
3. Ensure the `screen` property references a valid screen object; if you have multiple
   monitors and the referenced screen is disconnected the window is silently suppressed.

### Widget appears but is not transparent

Transparency on `WlrLayer.Bottom` requires the compositor to support alpha blending
for layer surfaces. Hyprland does this by default. On Sway, set:
```conf
# ~/.config/sway/config
output * bg #000000 solid_color
```
and ensure no opaque background is painted by swww or swaybg on top of the widget.

### conky shows nothing on Wayland

- Verify `out_to_wayland = true` and `out_to_x = false` are both set.
- Check conky version: `conky --version` must be ≥ 1.19.
- Run conky in a terminal to see error output: `conky -c ~/.config/conky/conky.conf`.
- If `own_window_type = 'desktop'` causes errors, try `'normal'` as a workaround.

### hyprexpo plugin not loading

```bash
# Rebuild plugin cache after Hyprland update
hyprpm update
hyprpm reload

# Check plugin status
hyprpm list

# Manually load at runtime for testing
hyprctl dispatch exec -- "hyprctl keyword plugin:hyprexpo:columns 3"
```

### Quickshell QML import errors

```bash
# Run quickshell from terminal to see QML errors
quickshell --config ~/.config/quickshell/shell.qml

# Common fix: update Quickshell after a Qt 6 upgrade
paru -Syu quickshell-git

# If Qt version mismatch:
quickshell --version   # shows Qt version it was compiled against
```

### High CPU usage from ShaderEffect

GPU shader wallpapers use the GPU for rendering but `liveUpdates: true` on
`ScreencopyView` items causes constant frame capture. Disable live updates when the
overview is hidden:

```qml
ScreencopyView {
    liveUpdates: overview.overviewActive   // only capture when visible
}
```

For shader wallpapers, limit the animation frame rate:

```qml
NumberAnimation on time {
    // 30 fps is imperceptible for slow plasma effects
    duration: 3600000
}
// Or cap Qt rendering rate in quickshell invocation:
// QSG_RENDER_LOOP=basic quickshell
```

---

*See also:*
- *Ch 53 — Session Startup and exec-once Patterns*
- *Ch 27 — Animated Wallpapers with mpvpaper and swww*
- *Ch 55 — Quickshell Introduction and PanelWindow Basics*
- *Ch 58 — Status Bars and Waybar Configuration*
- *Ch 61 — Notification Daemons: mako, dunst, SwayNotificationCenter*

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
