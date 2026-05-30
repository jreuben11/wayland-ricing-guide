# Chapter 88 — Hyprland IPC Scripting

## Contents

- [Overview](#overview)
- [88.1 Socket Locations](#881-socket-locations)
- [88.2 Querying via hyprctl](#882-querying-via-hyprctl)
  - [jq patterns for common queries](#jq-patterns-for-common-queries)
- [88.3 Dispatching Actions](#883-dispatching-actions)
  - [Targeting specific windows](#targeting-specific-windows)
- [88.4 The Event Socket — Real-Time Automation](#884-the-event-socket-real-time-automation)
  - [Event format](#event-format)
  - [Full event reference](#full-event-reference)
- [88.5 Automation Scripts](#885-automation-scripts)
  - [Per-workspace wallpaper](#per-workspace-wallpaper)
  - [Focus-follows-mouse with exclusions](#focus-follows-mouse-with-exclusions)
  - [Window picker (rofi-based)](#window-picker-rofi-based)
  - [Auto-tile newly opened windows](#auto-tile-newly-opened-windows)
  - [Idle inhibit based on fullscreen media](#idle-inhibit-based-on-fullscreen-media)
- [88.6 Python Automation with pyprland](#886-python-automation-with-pyprland)
  - [pyprland config (`~/.config/hypr/pyprland.toml`)](#pyprland-config-confighyprpyprlandtoml)
  - [Using pyprland's Python API](#using-pyprlands-python-api)
- [88.7 Batch Dispatch](#887-batch-dispatch)
- [88.8 Hyprland IPC in Quickshell](#888-hyprland-ipc-in-quickshell)

---


## Overview

Hyprland exposes two Unix sockets: a command socket for queries and dispatches, and an event socket that streams real-time compositor events. Together they let you build workspace automation, window-focus hooks, per-workspace wallpapers, window pickers, and reactive status scripts entirely from shell or Python — no C++ plugin required. The `hyprctl` command-line tool is a thin wrapper around the command socket and is the primary interface for both interactive use and scripting. Because both sockets and `hyprctl` ship as part of Hyprland itself, no additional packages are needed beyond the compositor.

> **Installation note:** `hyprctl` is bundled with Hyprland (`pacman -S hyprland`). No separate package is required for IPC scripting.

---

## 88.1 Socket Locations

```bash
# The instance signature is set in the environment by Hyprland
echo $HYPRLAND_INSTANCE_SIGNATURE

# Command socket (request/response)
/tmp/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket.sock

# Event socket (streaming, one event per line)
/tmp/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock
```

`hyprctl` is a thin wrapper around the command socket. For scripting, you can
call it directly or use `socat` for more control.

---

## 88.2 Querying via hyprctl

```bash
# JSON output with -j flag (before the subcommand)
hyprctl -j clients
hyprctl -j workspaces
hyprctl -j monitors
hyprctl -j activewindow
hyprctl -j activeworkspace
hyprctl -j layers
hyprctl -j devices        # keyboards, mice, tablets

# Plain text
hyprctl version
hyprctl configerrors

# Live config reload
hyprctl reload
hyprctl reload config-only   # skip plugin reload

# Runtime keyword changes (no reload needed)
hyprctl keyword general:gaps_out 20
hyprctl keyword decoration:rounding 15
hyprctl keyword monitor "HDMI-1,2560x1440@165,0x0,1"
```

### jq patterns for common queries

```bash
# Focused window class
hyprctl -j activewindow | jq -r '.class'

# All window classes on workspace 1
hyprctl -j clients | jq -r '.[] | select(.workspace.id==1) | .class'

# Count floating windows
hyprctl -j clients | jq '[.[] | select(.floating==true)] | length'

# Window addresses (for dispatch targeting)
hyprctl -j clients | jq -r '.[] | select(.class=="kitty") | .address'

# Current workspace name
hyprctl -j activeworkspace | jq -r '.name'

# Monitor resolution
hyprctl -j monitors | jq -r '.[0] | "\(.width)x\(.height)"'
```

---

## 88.3 Dispatching Actions

```bash
# Open apps
hyprctl dispatch exec kitty
hyprctl dispatch exec "[float; size 800 600] kitty"

# Window management
hyprctl dispatch killactive
hyprctl dispatch togglefloating
hyprctl dispatch fullscreen 0    # 0=fullscreen, 1=maximized
hyprctl dispatch pin             # pin floating window

# Focus
hyprctl dispatch movefocus l
hyprctl dispatch focuswindow "address:0x123abc"
hyprctl dispatch focuswindow "class:firefox"

# Workspaces
hyprctl dispatch workspace 3
hyprctl dispatch workspace name:code
hyprctl dispatch movetoworkspace 2
hyprctl dispatch movetoworkspacesilent special:scratch

# Move/resize
hyprctl dispatch movewindow l
hyprctl dispatch resizeactive 50 0

# Special workspace (scratchpad)
hyprctl dispatch togglespecialworkspace scratch
```

### Targeting specific windows

```bash
# Dispatch to a window by address
addr=$(hyprctl -j clients | jq -r '.[] | select(.class=="kitty") | .address' | head -1)
hyprctl dispatch focuswindow "address:$addr"

# Dispatch to focused window (default)
hyprctl dispatch killactive
```

---

## 88.4 The Event Socket — Real-Time Automation

The event socket streams one event per line. Subscribe with `socat` or `nc`:

```bash
socat - UNIX-CONNECT:/tmp/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock
```

### Event format

```
eventname>>data
```

Examples:
```
workspace>>2
activewindow>>firefox,Mozilla Firefox
focusedmon>>HDMI-1,2
openwindow>>0x123abc,2,kitty,kitty
closewindow>>0x123abc
movewindow>>0x123abc,3
fullscreen>>1
screencast>>1,0
```

### Full event reference

| Event | Data format | Meaning |
|-------|------------|---------|
| `workspace` | `id` | Active workspace changed |
| `workspacev2` | `id,name` | Active workspace (with name) |
| `focusedmon` | `monname,wsid` | Monitor focus changed |
| `activewindow` | `class,title` | Window focus changed |
| `activewindowv2` | `address` | Window focus (address only) |
| `openwindow` | `addr,wsid,class,title` | New window opened |
| `closewindow` | `address` | Window closed |
| `movewindow` | `addr,wsid` | Window moved to workspace |
| `fullscreen` | `0/1` | Fullscreen toggled |
| `screencast` | `state,owner` | Screenshare started/stopped |
| `monitoradded` | `name` | Monitor connected |
| `monitorremoved` | `name` | Monitor disconnected |
| `createworkspace` | `id` | New workspace created |
| `destroyworkspace` | `id` | Workspace destroyed |
| `renameworkspace` | `id,newname` | Workspace renamed |
| `urgent` | `address` | Window requested urgency |

---

## 88.5 Automation Scripts

### Per-workspace wallpaper

```bash
#!/bin/bash
# ~/.config/hypr/scripts/workspace-wallpaper.sh
# Run via: exec-once = ~/.config/hypr/scripts/workspace-wallpaper.sh

declare -A WALLPAPERS=(
  [1]="$HOME/wallpapers/coding.jpg"
  [2]="$HOME/wallpapers/browser.jpg"
  [3]="$HOME/wallpapers/music.jpg"
  [4]="$HOME/wallpapers/terminal.jpg"
)

DEFAULT_WALLPAPER="$HOME/wallpapers/default.jpg"

socat - UNIX-CONNECT:/tmp/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock \
| while read -r line; do
  event="${line%%>>*}"
  data="${line##*>>}"

  if [ "$event" = "workspace" ] || [ "$event" = "workspacev2" ]; then
    wsid="${data%%,*}"
    wall="${WALLPAPERS[$wsid]:-$DEFAULT_WALLPAPER}"
    [ -f "$wall" ] && swww img "$wall" --transition-type fade --transition-duration 0.5
  fi
done
```

### Focus-follows-mouse with exclusions

```bash
#!/bin/bash
# Follow mouse focus but exclude certain window classes
socat - UNIX-CONNECT:/tmp/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock \
| while read -r line; do
  event="${line%%>>*}"
  data="${line##*>>}"

  if [ "$event" = "activewindow" ]; then
    class="${data%%,*}"
    # Don't steal focus from these classes
    case "$class" in
      rofi|fuzzel|wofi|mako|dunst) continue ;;
    esac
    # Any custom focus logic here
  fi
done
```

### Window picker (rofi-based)

```bash
#!/bin/bash
# ~/.config/hypr/scripts/window-picker.sh
# Bind to: bind = SUPER, w, exec, ~/.config/hypr/scripts/window-picker.sh

# Build a list of windows for rofi
choice=$(hyprctl -j clients | jq -r '.[] | 
  "\(.address)\t[\(.workspace.name)] \(.class): \(.title)"' \
  | rofi -dmenu -i -p "Window" -format 'd' -sep '\t' \
  | cut -f1)

[ -n "$choice" ] && hyprctl dispatch focuswindow "address:$choice"
```

### Auto-tile newly opened windows

```bash
#!/bin/bash
# Ensure floating apps get tiled when moved to a tiling workspace
socat - UNIX-CONNECT:/tmp/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock \
| while read -r line; do
  event="${line%%>>*}"
  data="${line##*>>}"

  if [ "$event" = "openwindow" ]; then
    addr=$(echo "$data" | cut -d, -f1)
    class=$(echo "$data" | cut -d, -f3)
    # Auto-move certain apps to specific workspaces
    case "$class" in
      Spotify) hyprctl dispatch movetoworkspacesilent "name:music,address:0x$addr" ;;
      discord) hyprctl dispatch movetoworkspacesilent "name:chat,address:0x$addr"  ;;
    esac
  fi
done
```

### Idle inhibit based on fullscreen media

```bash
#!/bin/bash
# Prevent screen blanking when a video player is fullscreen
INHIBITOR_PID=""

socat - UNIX-CONNECT:/tmp/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock \
| while read -r line; do
  event="${line%%>>*}"
  data="${line##*>>}"

  if [ "$event" = "fullscreen" ]; then
    if [ "$data" = "1" ]; then
      # Fullscreen on — inhibit idle
      class=$(hyprctl -j activewindow | jq -r '.class')
      case "$class" in
        mpv|vlc|celluloid)
          hypridle inhibit &
          INHIBITOR_PID=$!
          ;;
      esac
    else
      # Fullscreen off — restore idle
      [ -n "$INHIBITOR_PID" ] && kill "$INHIBITOR_PID" 2>/dev/null
      INHIBITOR_PID=""
    fi
  fi
done
```

---

## 88.6 Python Automation with pyprland

pyprland is a plugin host that wraps the IPC socket with higher-level
features. It's also usable as a library for Python automation.

```bash
paru -S pyprland
```

### pyprland config (`~/.config/hypr/pyprland.toml`)

```toml
[pyprland]
plugins = ["scratchpads", "expose", "monitors", "lost_windows"]

[scratchpads.term]
command = "kitty --class scratchpad"
class = "scratchpad"
size = "75% 60%"
position = "12.5% 20%"

[scratchpads.music]
command = "spotify"
class = "Spotify"
size = "80% 70%"

[scratchpads.files]
command = "thunar"
class = "thunar"
size = "60% 70%"
```

Launch the daemon:
```conf
# hyprland.conf
exec-once = pypr
```

Bind scratchpad toggles:
```conf
bind = SUPER, F, exec, pypr toggle term
bind = SUPER, M, exec, pypr toggle music
bind = SUPER, E, exec, pypr toggle files
```

### Using pyprland's Python API

```python
#!/usr/bin/env python3
import asyncio
from pyprland.ipc import get_hyprland_info, send_command

async def main():
    # Get all clients
    clients = await get_hyprland_info("clients")
    for c in clients:
        print(f"{c['class']}: {c['title']} (ws {c['workspace']['id']})")

    # Dispatch a command
    await send_command("dispatch exec kitty")

asyncio.run(main())
```

---

## 88.7 Batch Dispatch

```bash
# Execute multiple dispatches atomically (reduces flickering)
hyprctl --batch "dispatch workspace 2 ; dispatch exec kitty"

# Or use a here-doc for longer sequences
hyprctl --batch "$(cat <<'EOF'
dispatch killactive
dispatch workspace 3
dispatch exec [float; size 800 600] foot
EOF
)"
```

---

## 88.8 Hyprland IPC in Quickshell

Quickshell's `Quickshell.Hyprland` module wraps the IPC socket natively
(see Ch 20), but for scripts that need to run outside Quickshell, the socket
approach above is the correct tool. Use `IpcHandler` in Quickshell for QML
components, shell scripts for system-level automation.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
