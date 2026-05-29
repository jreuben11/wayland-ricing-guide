# Chapter 25 — Real-World Quickshell Configurations

## Overview
Analysis of exemplary community Quickshell configurations. Learn patterns,
architecture decisions, and aesthetic approaches from real rices.

## Sections

### 25.1 end_4/dots-hyprland
- Repository: https://github.com/end-4/dots-hyprland
- Architecture: modular, multiple independent shells
- Notable features: AI integration, beautiful animations, comprehensive theming
- Key patterns: singleton state management, matugen color extraction
- Lessons: component encapsulation, theme propagation

### 25.2 outfoxxed's Configurations
- The Quickshell author's own configs
- Patterns that reflect the library's intended idioms
- Advanced use of `Variants`, `Scope`, `LazyLoader`

### 25.3 ekremx25/quickshell
- Multi-compositor: Hyprland, Niri, MangoWC support
- Material You theming
- 10-band EQ via PipeWire
- Multi-monitor architecture

### 25.4 doannc2212/quickshell-config
- Complete: bar + launcher + notifications + theme switcher
- 206-theme switcher implementation
- Modular "take what you like" design

### 25.5 Common Architecture Patterns

#### Pattern: The Theme Singleton
```qml
// theme/Theme.qml
pragma Singleton
import Quickshell

Singleton {
    property color background: "#1e1e2e"
    property color foreground: "#cdd6f4"
    property color accent: "#89b4fa"
    // load from pywal: read ~/.cache/wal/colors.json
}
```

#### Pattern: Reactive Wallpaper-Based Colors
- Matugen: generate Material You colors from wallpaper
- Pywal: extract palette from wallpaper
- FileView watching color file changes
- Hot-reload colors without restarting Quickshell

#### Pattern: Reveal Animations
```qml
PanelWindow {
    property bool revealed: false
    height: revealed ? fullHeight : 0
    Behavior on height { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
}
```

#### Pattern: Conditional Modules
```qml
LazyLoader {
    active: batteryDevice !== null  // only show battery if device exists
    BatteryWidget { device: batteryDevice }
}
```

#### Pattern: Per-Monitor State
```qml
Variants {
    model: Quickshell.screens
    QtObject {
        required property var modelData
        property int activeWorkspace: 1
        property string windowTitle: ""
        // Hyprland events update per-screen state
    }
}
```

### 25.6 Performance Tuning
- `visible: false` vs. destroying components
- `LazyLoader` for expensive components
- `liveUpdates: false` on ScreencopyView when not visible
- Avoiding binding loops
- Property aliasing patterns

### 25.7 Debugging Production Configs
- `quickshell --log-rules "*.warning=true"`
- Finding binding loops with console.trace
- Profiling with Qt's built-in tools

### 25.8 Config Organization Recommendations
```
~/.config/quickshell/
├── shell.qml            ← ShellRoot only
├── bar/                 ← status bar components
├── notifications/       ← notification popups
├── osd/                 ← volume/brightness OSD
├── overview/            ← workspace overview
├── launcher/            ← app launcher
├── lockscreen/          ← session lock
├── widgets/             ← desktop widgets
├── theme/               ← Theme singleton
└── services/            ← shared state singletons
```
