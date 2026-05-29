# Chapter 32 — Clipboard Management: wl-clipboard, cliphist

## Overview
Wayland's clipboard model differs from X11: there's no persistent clipboard server.
Tools like wl-clipboard and cliphist bridge this gap.

## Sections

### 32.1 Wayland Clipboard Architecture
- `wl_data_device_manager` protocol: source and offer model
- Selection types: clipboard, primary selection, drag-and-drop
- Why the clipboard disappears when an app closes (no persistent server)
- Primary selection on Wayland: `wl-paste -p`

### 32.2 wl-clipboard — The Core Tool
- `wl-copy "text"`: set clipboard content
- `wl-copy < file.png`: set image to clipboard
- `wl-paste`: read clipboard
- `wl-paste --list-types`: show available MIME types
- `wl-copy --primary "text"`: set primary selection
- Piping: `cat file.txt | wl-copy`

### 32.3 cliphist — Clipboard History
```bash
# Setup: pipe all clipboard changes to cliphist
wl-paste --type text --watch cliphist store
wl-paste --type image --watch cliphist store

# Show history picker (with wofi/fuzzel/rofi)
cliphist list | wofi --dmenu | cliphist decode | wl-copy
```
- `cliphist store`: add entry to history
- `cliphist list`: show all history entries
- `cliphist decode`: decode entry by ID
- `cliphist delete-query`: remove matching entries
- `cliphist wipe`: clear all history
- Database location: `~/.cache/cliphist/db`
- Image clipboard support

### 32.4 copyq — Cross-Platform GUI Manager
- GTK-based clipboard manager with history
- Wayland support via `wl-clipboard` backend
- Scripting via built-in JavaScript engine

### 32.5 Hyprland Clipboard Setup
```conf
# hyprland.conf
exec-once = wl-paste --type text --watch cliphist store
exec-once = wl-paste --type image --watch cliphist store
bind = SUPER, V, exec, cliphist list | rofi -dmenu | cliphist decode | wl-copy
```

### 32.6 Primary Selection (Middle-Click Paste)
- `xsel --primary` compatibility layer for XWayland apps
- `wl-paste --primary` in scripts
- Primary selection in terminals

### 32.7 Quickshell Clipboard Widget
- Reading clipboard via `Process { command: ["wl-paste"] }`
- Clipboard history display panel
- Integration with cliphist list + decode
