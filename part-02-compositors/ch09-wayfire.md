# Chapter 9 — Wayfire: Plugin Architecture and 3D Effects

## Overview
Wayfire is a 3D-capable, plugin-driven Wayland compositor. Rather than baking in
window management policy, Wayfire delegates almost everything to plugins, making it
uniquely extensible — but also requiring more initial configuration.

## Sections

### 9.1 History and Design Goals
- Derived from compiz-like design philosophy
- Plugin-first architecture: even basic window management is a plugin
- The `wf-config` configuration system
- Relationship to wlroots

### 9.2 Installation and First Run
- Building from source (CMake)
- Distribution packages
- `wayfire.ini` location and initial configuration
- WCM (Wayfire Config Manager): the GTK configuration GUI

### 9.3 The Plugin System
- Plugin loading: `[core] plugins = ...`
- Built-in plugins overview: `move`, `resize`, `place`, `grid`, `vswitch`
- `wcm` plugin categories: general, desktop, window management, effects, utilities

### 9.4 Core Window Management Plugins
- `move`, `resize`: basic manipulation
- `place`: window placement strategies
- `grid`: snap-to-grid tiling (like mutter snap)
- `simple-tile`: basic tiling layout
- `wm-actions`: minimize, maximize, fullscreen keybindings

### 9.5 Visual Effects Plugins
- `wobbly`: wobbly windows (Compiz classic)
- `blur`: background blur
- `animate`: window open/close animations
- `cube`: rotating cube workspace switcher
- `fisheye`: zoom effect
- `fire`: burning window close effect
- `expo`: expose-style workspace overview
- `scale`: application switcher

### 9.6 Workspace Switcher Plugins
- `vswitch`: grid-based workspace switching
- `oswitch`: output (monitor) switching
- Gesture support for workspace navigation

### 9.7 Writing a Wayfire Plugin
- Plugin API: `wf::plugin_interface_t`
- Registering hooks and signal handlers
- Accessing compositor state
- Build system integration

### 9.8 Wayfire Compared to Hyprland
- When to choose Wayfire: 3D effects, plugin customization
- When to choose Hyprland: community, dotfiles ecosystem, Quickshell integration
- Performance comparison
- Stability comparison (2025/2026)
