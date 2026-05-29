# Chapter 59 — Desktop Widgets, Overview Effects, and Conky Equivalents

## Overview
Desktop widgets (clocks, system monitors, calendars on the wallpaper) and
expose-style overview effects are what many people mean by "ricing." This chapter
covers all approaches: Quickshell, conky-NG, and compositor built-ins.

## Sections

### 59.1 Layer Shell Widgets vs. True Desktop Widgets
- X11 "desktop widgets" (conky, Rainmeter) drew on the root window
- Wayland equivalent: layer-shell surfaces on `WlrLayer.Background` or `WlrLayer.Bottom`
- These sit above the wallpaper but below windows
- Quickshell is the primary tool; conky has partial Wayland support

### 59.2 Quickshell Desktop Widgets

**Desktop clock:**
```qml
// widgets/DesktopClock.qml
PanelWindow {
    screen: Quickshell.screens[0]
    layer: WlrLayer.Bottom
    anchors { bottom: true; right: true }
    margins { bottom: 48; right: 48 }
    width: 300; height: 100
    color: "transparent"

    Text {
        anchors.centerIn: parent
        text: SystemClock.time.toLocaleTimeString(Qt.locale(), "HH:mm")
        font { pixelSize: 64; family: "JetBrainsMono Nerd Font" }
        color: "#cdd6f4"
        style: Text.Outline
        styleColor: "#00000080"
    }
}
```

**System monitor widget:**
```qml
PanelWindow {
    layer: WlrLayer.Bottom
    anchors { top: true; left: true }
    margins { top: 64; left: 64 }
    color: "#80000000"   // semi-transparent background
    width: 200; height: 120

    ColumnLayout {
        CpuBar { /* reads /proc/stat via Process */ }
        MemoryBar { /* reads /proc/meminfo via FileView */ }
        NetworkSpeed { /* reads /proc/net/dev */ }
    }
}
```

**Calendar widget:**
- `SystemClock.date` for current date
- QML `GridLayout` for month grid
- Highlight today's cell

### 59.3 conky on Wayland
Conky has experimental Wayland support via its `wayland` output target:
```lua
-- ~/.config/conky/conky.conf
conky.config = {
    out_to_wayland = true,
    own_window = true,
    own_window_type = 'desktop',
    -- colors, fonts, position...
}
```

**Limitations:** conky Wayland is less stable than X11 mode. Consider Quickshell
widgets for production use and conky for quick experiments.

**conky system info:**
```lua
conky.text = [[
${color #89b4fa}CPU: ${color}${cpu}% ${cpubar}
${color #89b4fa}RAM: ${color}${mem}/${memmax} ${membar}
${color #89b4fa}Disk: ${color}${fs_used /}/${fs_size /}
${color #89b4fa}Net:${color} ↑${upspeed} ↓${downspeed}
]]
```

### 59.4 Workspace Overview / Expose Effects

**Hyprland hyprexpo plugin:**
```bash
hyprpm add https://github.com/hyprwm/hyprland-plugins
hyprpm enable hyprexpo
```
```conf
# hyprland.conf
plugin:hyprexpo {
    columns = 3
    gap_size = 5
    bg_col = rgb(111111)
    workspace_method = center current
    enable_gesture = true
    gesture_fingers = 3
    gesture_distance = 300
    gesture_positive = true
}
bind = SUPER, TAB, hyprexpo:expo, toggle
```

**Quickshell workspace overview (from scratch):**
```qml
// overview/Overview.qml
PanelWindow {
    layer: WlrLayer.Overlay
    anchors.fill: true  // fullscreen overlay
    visible: overviewActive

    GridLayout {
        Repeater {
            model: Hyprland.workspaces
            WorkspacePreview {
                // ScreencopyView for live preview
                ScreencopyView {
                    captureSource: ...
                    liveUpdates: parent.visible
                }
            }
        }
    }
}
```

**Sway / niri / river:** No built-in expose. Use Quickshell `ToplevelManager` + `ScreencopyView` for a custom implementation.

### 59.5 Window Switcher (Alt+Tab)

Hyprland built-in: uses `focuscurrentorlast` or `hyprswitch` plugin.

**Quickshell window switcher:**
```qml
PanelWindow {
    layer: WlrLayer.Overlay
    visible: switcherActive

    ListView {
        model: ToplevelManager.toplevels
        delegate: WindowSwitcherItem {
            required property Toplevel modelData
            title: modelData.title
            appId: modelData.appId
            onActivated: {
                modelData.activate()
                switcherActive = false
            }
        }
    }
}
```

**hyprswitch:** dedicated Hyprland window switcher with thumbnails.

### 59.6 Desktop Icon Grid
Wayland has no built-in desktop icon standard. Options:
- `nemo --desktop` (Cinnamon file manager desktop mode)
- `pcmanfm --desktop` (PCManFM)
- Custom Quickshell `WlrLayer.Background` surface listing `~/Desktop/`

### 59.7 Animated / Shader Wallpapers
Using Quickshell with GLSL shaders:
```qml
PanelWindow {
    layer: WlrLayer.Background
    ShaderEffect {
        anchors.fill: parent
        fragmentShader: "qrc:/shaders/plasma.glsl"
        property real time: SystemClock.time.getSeconds()
    }
}
```

Or `mpvpaper` for video wallpapers (Ch 27).

### 59.8 Notification Toasts as Desktop Widgets
- Notification popups can be styled as desktop widgets (large, center-screen)
- `layer: WlrLayer.Bottom` for non-intrusive notifications in a corner
- `urgency = Critical` → `layer: WlrLayer.Overlay` for can't-miss alerts
