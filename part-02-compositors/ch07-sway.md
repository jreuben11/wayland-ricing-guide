# Chapter 7 — Sway: i3 on Wayland

## Overview
Sway is a drop-in i3 replacement for Wayland. The most mature wlroots-based
compositor, with a stable config format and large ecosystem.

## Sections

### 7.1 History and Philosophy
- Drew DeVault's creation as an i3 port
- "If it doesn't work like i3, it's a bug" policy
- Relationship with wlroots (Sway project maintains wlroots)
- Current maintainership and status (2025/2026)

### 7.2 Installation and Initial Setup
- Distribution packages vs. building from source
- First launch: `sway` command, default config location
- `~/.config/sway/config` structure

### 7.3 Configuration Deep Dive
- Syntax: `set`, `exec`, `bindsym`, `bindcode`
- `input` block: libinput configuration
- `output` block: monitors, resolution, position, scale
- `seat` configuration
- Bar configuration: the built-in `swaybar` vs. Waybar

### 7.4 Layout and Window Management
- Container tree model (identical to i3)
- `splith`, `splitv`, `tabbed`, `stacking` layouts
- Marks, `focus`, `move`, `resize`
- Floating windows and their rules
- `for_window` criteria: `app_id`, `title`, `class`

### 7.5 IPC and Scripting
- `swaymsg` command-line tool
- IPC socket: `$SWAYSOCK`
- Python `i3ipc` library for Sway
- `swayidle` and `swaylock` integration

### 7.6 Sway-Specific Ecosystem
- `waybar`: the canonical Sway bar
- `mako`: notification daemon designed for Sway
- `wofi`: application launcher
- `swayimg`: image viewer
- `swaybg`: wallpaper tool

### 7.7 Configuration Examples
- Minimal functional config
- Development workflow config with workspaces
- Multi-monitor setup
- Gaming-mode toggle

### 7.8 Sway vs. Hyprland: Choosing Your Path
- Stability vs. features tradeoff
- Config syntax complexity
- Performance characteristics
- Ecosystem maturity
