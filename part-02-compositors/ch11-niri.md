# Chapter 11 — Niri: The Scrollable Workspace Pioneer

## Overview
Niri implements an infinite scrollable column layout, making it uniquely suited to
wide-monitor and multi-tasking workflows. Written in Rust with Smithay, it's a
leading example of the post-wlroots compositor generation.

## Sections

### 11.1 The Scrollable Layout Concept
- Why infinite columns rather than fixed workspaces
- Visual comparison: Niri vs. PaperWM vs. Hyprscroller
- Keyboard navigation model: focus follows spatial position

### 11.2 Installation
- Cargo build from source
- NixOS flake
- Distribution packages (Arch AUR, Fedora)

### 11.3 Configuration: kdl Format
- `~/.config/niri/config.kdl`
- KDL document language: nodes, arguments, properties, children
- `output` block: monitor configuration
- `layout` block: gaps, struts, focus-ring, preset-column-widths
- `input` block: keyboard, pointer, touchpad
- `binds` block: keybindings
- `window-rule` block: per-app settings

### 11.4 Layout Deep Dive
- Column widths: `proportional`, `fixed`, preset cycling
- `center-focused-column`: keeping focus centered
- Workspaces in Niri: per-output, dynamic
- Overview mode: see all workspaces

### 11.5 Animations and Visual Polish
- Built-in animation configuration
- Window open/close animations
- Workspace switch animations

### 11.6 Niri's Limitations (2025 Status)
- Missing HDR support
- Missing DRM sync objects
- Feature gap vs. Hyprland: what's not there yet
- Development roadmap

### 11.7 Niri Ecosystem
- `niri-ipc`: the IPC protocol
- Waybar niri module
- Quickshell compatibility

### 11.8 Niri vs. Hyprland: When Scrollable Wins
- Wide-monitor workflows
- Document-heavy work
- Users coming from PaperWM / i3-gaps
