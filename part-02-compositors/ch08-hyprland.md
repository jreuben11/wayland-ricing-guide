# Chapter 8 — Hyprland: Dynamic Tiling with Animation DNA

## Overview
Hyprland is the dominant ricing compositor of 2024–2026. Written from scratch in C++
on top of wlroots/Aquamarine, it prioritizes animations, customization depth, and
visual polish at the cost of some stability. It has its own plugin ecosystem, IPC
protocol, and an enormous dotfiles community.

## Sections

### 8.1 History and Philosophy
- vaxry's creation; not a fork of anything
- Aquamarine: Hyprland's custom backend library replacing wlroots backends
- Community growth: r/hyprland, the "hyprland aesthetic"
- Subscription service controversy and community dynamics (2025)
- Stability improvements in 2025/2026 release series

### 8.2 Installation
- Official packages: Arch (AUR), NixOS, Fedora, Ubuntu PPAs
- Building from source: `CMake`, `Aquamarine`, `hyprlang`
- NVIDIA considerations: `nvidia-drm.modeset=1`, `LIBVA_DRIVER_NAME`
- First launch checklist

### 8.3 The hyprlang Configuration Language
- `hyprland.conf` structure and includes
- `monitor` directive: `name,resolution@refreshrate,position,scale`
- `general` block: gaps, border sizes, layout
- `decoration` block: rounding, blur, shadows, opacity
- `animations` block: curves, durations, styles
- `input` block: sensitivity, accel profile, touchpad
- `gestures` block
- `misc` block: VFR, logo, splash, focus behavior

### 8.4 Layout Algorithms
- Dwindle layout: golden ratio recursive splitting
  - `pseudotile`, `preserve_split`, `smart_split`
- Master layout: one master, N stack windows
  - `mfact`, `new_is_master`, orientation
- hyprscroller plugin (scrollable workspace extension)

### 8.5 Window Rules and Layer Rules
- `windowrulev2` syntax: predicates and actions
- Common rules: float, tile, opacity, workspace, monitor, nofocus
- `layerrule`: animating layer shell surfaces (bars, widgets)

### 8.6 Keybindings and Dispatchers
- `bind`, `bindm`, `binde`, `bindr`, `bindn`
- Dispatcher reference: `exec`, `killactive`, `movewindow`, `workspace`, `submap`
- Submaps: modal keybinding layers
- `hyprctl dispatch` for scripting

### 8.7 Animations
- Curve definitions: bezier splines
- Animation types: windows, workspaces, layers, fade, border
- `animation = windows, 1, 7, myBezier, slide`
- Performance tuning: `no_direct_scanout`, VFR

### 8.8 Hyprland IPC
- Socket path: `$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket.sock`
- `hyprctl` command reference
- Event socket: `/.socket2.sock` — real-time event stream
- JSON output parsing
- Python `pyprland` and shell script integration

### 8.9 The Plugin Ecosystem
- `hyprpm`: the official plugin manager
- Notable plugins: hyprexpo, hyprspace, hy3, hyprscroller
- Writing a plugin in C++: `HyprlandAPI` hooks

### 8.10 Hyprland Utilities
- `hyprpaper`: wallpaper manager with IPC
- `hyprlock`: GPU-accelerated lockscreen
- `hypridle`: idle management daemon
- `hyprshot`: screenshot tool
- `hyprsunset`: color temperature

### 8.11 Configuration Gallery
- Minimal + fast config
- Heavy eye-candy config
- Productivity-focused config
- NixOS/home-manager Hyprland module
