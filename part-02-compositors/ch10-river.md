# Chapter 10 — River: Tag-Based Minimalism

## Overview
River takes a Unix philosophy approach: the compositor handles rendering and input,
but layout is delegated entirely to external layout generators. Tagged window
management (not workspaces) gives flexible window organization.

## Sections

### 10.1 Philosophy: The River Way
- Inspired by dwm's tag-based model
- External layout generators: separation of concerns
- `riverctl`: the configuration and control CLI
- No config file: configuration is an executable script

### 10.2 Installation and Setup
- Building from Zig source
- The init script: `~/.config/river/init` (executable shell script)
- Starting River

### 10.3 Tag System
- 32 available tags (bit-flags)
- Assigning windows to tags with `set-view-tags`
- Focusing tags: `set-focused-tags`
- Multi-tag views and multi-tag focus
- Comparison to i3 workspaces

### 10.4 Configuration via riverctl
- `riverctl map` — keybinding definition
- `riverctl spawn` — launching applications
- `riverctl set-repeat` — keyboard repeat rate
- `riverctl input` — libinput configuration
- `riverctl rule-add` — window rules

### 10.5 Layout Generators
- `rivertile`: the built-in layout generator
  - `main-location`, `main-count`, `main-ratio`
- External generators: `river-bsp-layout`, `stacktile`, `kile`
- Writing your own layout generator (protocol: `river-layout-v3`)

### 10.6 Scripting River
- Status bar integration via `river-status-unstable-v1`
- Waybar River module
- Event-driven scripting patterns

### 10.7 River in 2025/2026
- Stability and feature completeness
- Community size vs. Hyprland/Sway
- Use cases where River shines
