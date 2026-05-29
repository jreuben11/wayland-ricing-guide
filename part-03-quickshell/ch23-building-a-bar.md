# Chapter 23 — Building a Complete Status Bar

## Overview
End-to-end tutorial: build a production-quality multi-monitor status bar from
scratch using Quickshell. Each section adds a module to the bar.

## Sections

### 23.1 Project Structure
```
~/.config/quickshell/
├── shell.qml
├── bar/
│   ├── Bar.qml
│   ├── modules/
│   │   ├── Clock.qml
│   │   ├── Workspaces.qml
│   │   ├── WindowTitle.qml
│   │   ├── Media.qml
│   │   ├── Volume.qml
│   │   ├── Battery.qml
│   │   ├── Network.qml
│   │   └── SystemTray.qml
│   └── components/
│       ├── Icon.qml
│       └── Pill.qml
└── theme/
    └── Theme.qml   (singleton)
```

### 23.2 The Shell Entry Point
```qml
// shell.qml
import Quickshell

ShellRoot {
    Variants {
        model: Quickshell.screens
        Bar { required property var modelData; screen: modelData }
    }
}
```

### 23.3 The Bar Container
```qml
// bar/Bar.qml
PanelWindow {
    required property QsScreen screen
    anchors { top: true; left: true; right: true }
    height: 36
    exclusiveZone: height
    layer: WlrLayer.Top
    color: Theme.barBackground

    RowLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 8

        Workspaces { screen: parent.screen }
        WindowTitle {}
        Item { Layout.fillWidth: true }  // spacer
        Media {}
        Volume {}
        Battery {}
        SystemTray {}
        Clock {}
    }
}
```

### 23.4 Clock Module
- `SystemClock` with locale-aware formatting
- Date tooltip on hover
- Custom format strings: 24h vs. 12h

### 23.5 Workspace Indicator Module
- `Hyprland.workspaces` filtered by monitor
- Active workspace highlighting
- Occupied vs. empty visual distinction
- Click to switch: `Hyprland.dispatch("workspace " + id)`
- Scroll to switch workspaces

### 23.6 Focused Window Title
- `Hyprland.focusedClient.title` with fallback
- Truncation with ellipsis
- App icon from `appId`

### 23.7 Volume Module
- `PipeWire.defaultAudioSink.audio.volume` display
- Scroll wheel to adjust
- Click to mute
- Icon changes: muted / low / medium / high

### 23.8 Battery Module
- `UPower.devices` for battery
- Percentage text + icon
- Charging animation
- Color coding: critical/warning/ok

### 23.9 Media Controls Module
- `MprisController.players[0]` guard
- Song title (truncated), artist
- Play/pause button
- Album art thumbnail option

### 23.10 Network Status Module
- Reading from `NetworkManager` via `Process` + `nmcli`
- Or reading `/proc/net/wireless` for signal strength
- Wired vs. WiFi icons

### 23.11 System Tray
- Full `SystemTray.items` implementation
- Icon rendering with `IconImage`
- Right-click menu with `DBusMenu`

### 23.12 Theming the Bar
- `Theme.qml` singleton with colors, radii, fonts
- Dark/light mode toggle
- pywal integration: reading colors from `~/.cache/wal/colors.json`

### 23.13 Animations
- Bar slide-in on startup
- Module fade on change
- `Behavior { NumberAnimation { duration: 150 } }`

### 23.14 Complete Source Code
Full `shell.qml` + all modules — annotated, copy-paste ready.
