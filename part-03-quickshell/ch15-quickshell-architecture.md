# Chapter 15 — Quickshell Architecture and Philosophy

## Overview
Quickshell is a QML/QtQuick-based shell framework that has emerged as the leading
choice for custom desktop shells in 2024–2026. This chapter explains why it exists,
how it compares to alternatives, and what its architecture looks like.

## Sections

### 15.1 The Shell Framework Landscape
- What a "shell framework" is vs. a bar program vs. a widget toolkit
- Historical tools: xmobar, polybar (X11-only or limited)
- eww (Elkowar's Wacky Widgets): Yuck language, GTK-based
- AGS/Astal: TypeScript/GJS-based, now Astal framework
- Waybar: config-file-driven, less programmable
- Quickshell: QtQuick + QML, most flexible

### 15.2 Why Quickshell Wins
- QML: declarative, reactive, proven in embedded/mobile UI
- LSP support: autocomplete, type checking in editors
- Hot reload: changes apply on save without restart
- Qt ecosystem: access to all Qt modules (animation, networking, etc.)
- Native C++ integration: can write custom C++ backends
- Multimonitor-first design
- Wayland-native: layer shell, screencopy, toplevel management built in

### 15.3 Architecture Overview
```
~/.config/quickshell/
└── shell.qml          ← entry point (or any named config)
    ├── Bar.qml
    ├── Notifications.qml
    ├── Lockscreen.qml
    └── components/
        └── *.qml
```

- QML engine: Qt's JavaScript-powered declarative UI runtime
- The `Quickshell` singleton: global state and screen management
- Process model: single process, multiple windows/surfaces
- IPC: `IpcHandler` for external control

### 15.4 Module Namespace Map
| Namespace | Purpose |
|-----------|---------|
| `Quickshell` | Core: windows, singletons, variants, utilities |
| `Quickshell.Io` | Processes, sockets, files, parsers |
| `Quickshell.Wayland` | Layer shell, toplevel, screencopy, session lock |
| `Quickshell.Hyprland` | Hyprland IPC: monitors, workspaces, windows |
| `Quickshell.I3` | i3/Sway IPC |
| `Quickshell.Services.Notifications` | D-Bus notification server |
| `Quickshell.Services.Mpris` | Media player control |
| `Quickshell.Services.Pipewire` | Audio node/link management |
| `Quickshell.Services.UPower` | Battery, power profiles |
| `Quickshell.Services.SystemTray` | System tray items |
| `Quickshell.Services.Pam` | PAM authentication |
| `Quickshell.Services.Greetd` | Login greeter |
| `Quickshell.Widgets` | Reusable UI components |
| `Quickshell.DBusMenu` | D-Bus menu items |

### 15.5 Installation and Building
- Distribution packages: Arch (AUR: `quickshell-git`), NixOS flake
- Building from source: Qt6, cmake, required Qt modules
- `BUILD.md` build options and feature flags
- Runtime dependencies

### 15.6 Community and Resources
- Official docs: https://quickshell.org/docs/
- Notable configs: end_4/dots-hyprland, outfoxxed's configs
- Discord/Matrix community
- DeepWiki: https://deepwiki.com/quickshell-mirror/quickshell
