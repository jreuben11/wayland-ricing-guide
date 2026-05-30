# Chapter 96 — Workspace Automation: pyprland, Scratchpads, Persistent Layouts

## Contents

- [Overview](#overview)
- [96.1 pyprland — Plugin Host for Hyprland](#961-pyprland-plugin-host-for-hyprland)
  - [Available pyprland plugins](#available-pyprland-plugins)
- [96.2 Scratchpads](#962-scratchpads)
  - [Configuration](#configuration)
  - [Hyprland keybinds for scratchpads](#hyprland-keybinds-for-scratchpads)
  - [Multi-instance scratchpads](#multi-instance-scratchpads)
- [96.3 Expose — All Windows on Current Workspace](#963-expose-all-windows-on-current-workspace)
- [96.4 Hyprexpo — Workspace Grid Overview (Plugin)](#964-hyprexpo-workspace-grid-overview-plugin)
- [96.5 Persistent Workspace Layouts](#965-persistent-workspace-layouts)
  - [Named workspaces](#named-workspaces)
  - [Auto-assign apps to workspaces](#auto-assign-apps-to-workspaces)
- [96.6 Per-Workspace Wallpaper (via pyprland)](#966-per-workspace-wallpaper-via-pyprland)
- [96.7 Layout Automation Scripts](#967-layout-automation-scripts)
  - [Save and restore window layout](#save-and-restore-window-layout)
  - [Focus recent windows (like Alt+Tab)](#focus-recent-windows-like-alttab)
- [96.8 Special Workspaces](#968-special-workspaces)

---


## Overview

Beyond basic workspace switching, Hyprland's IPC and tools like pyprland enable
sophisticated workspace behaviour: scratchpad terminals that slide in and out,
expose-style overviews, per-workspace app pinning, and persistent layouts that
survive across sessions.

---

## 96.1 pyprland — Plugin Host for Hyprland

pyprland (Python Hyprland daemon) listens on the event socket and provides
high-level features as plugins.

```bash
paru -S pyprland

# Start at login
# hyprland.conf
exec-once = pypr
```

Config: `~/.config/hypr/pyprland.toml`

### Available pyprland plugins

| Plugin | Function |
|--------|----------|
| `scratchpads` | Floating terminals/apps that toggle in/out |
| `expose` | Show all windows on the current workspace |
| `shift_monitors` | Swap workspaces between monitors |
| `magnify` | Temporary zoom in |
| `layout_center` | Center the active window with others as backdrop |
| `lost_windows` | Recover windows that fell off-screen |
| `monitors` | Reorder/rename monitors |
| `workspaces_follow_focus` | Keep focus on the same workspace across monitors |
| `toggle_dpms` | Toggle monitor power |
| `wall` | Set wallpaper per workspace |

---

## 96.2 Scratchpads

A scratchpad is a window that hides to a special workspace and slides in on
demand. The paradigm: one keybind toggles a tool (terminal, music player,
file manager) into view, then hides it again.

### Configuration

```toml
# ~/.config/hypr/pyprland.toml
[pyprland]
plugins = ["scratchpads"]

# Floating terminal (slides from top)
[scratchpads.term]
command = "kitty --class scratchpad-term"
class = "scratchpad-term"
size = "75% 55%"
position = "12.5% 0%"
animation = "fromTop"
# animation options: fromTop | fromBottom | fromLeft | fromRight | fade

# Music player (slides from right)
[scratchpads.music]
command = "spotify-launcher"
class = "Spotify"
size = "30% 100%"
position = "70% 0%"
animation = "fromRight"

# File manager (centered)
[scratchpads.files]
command = "thunar"
class = "thunar"
size = "60% 70%"
position = "20% 15%"
animation = "fade"

# Calculator
[scratchpads.calc]
command = "qalculate-gtk"
class = "qalculate-gtk"
size = "400 600"
position = "calc(50% - 200px) calc(50% - 300px)"  # centered

# Note-taking app with hyprland lazy-start
[scratchpads.notes]
command = "obsidian"
class = "obsidian"
size = "80% 80%"
position = "10% 10%"
lazy = true   # don't start until first toggle
```

### Hyprland keybinds for scratchpads

```conf
# hyprland.conf
bind = SUPER, grave,  exec, pypr toggle term
bind = SUPER, m,      exec, pypr toggle music
bind = SUPER, e,      exec, pypr toggle files
bind = SUPER, c,      exec, pypr toggle calc
bind = SUPER, n,      exec, pypr toggle notes

# Optional: hide all scratchpads at once
bind = SUPER, escape, exec, pypr hide "*"
```

### Multi-instance scratchpads

```toml
[scratchpads.term1]
command = "kitty --class scratch-1"
class = "scratch-1"
...

[scratchpads.term2]
command = "kitty --class scratch-2"
class = "scratch-2"
...
```

---

## 96.3 Expose — All Windows on Current Workspace

```toml
[pyprland]
plugins = ["expose"]
```

```conf
# hyprland.conf
bind = SUPER, tab, exec, pypr expose
```

When triggered, all windows on the current workspace spread out for selection.
Click a window to focus it; press Escape to cancel.

---

## 96.4 Hyprexpo — Workspace Grid Overview (Plugin)

The `hyprexpo` Hyprland plugin (ch89) provides a grid of all workspaces:

```conf
plugin:hyprexpo:columns = 3
plugin:hyprexpo:gap_size = 5
plugin:hyprexpo:bg_col = rgb(1e1e2e)
plugin:hyprexpo:workspace_method = center current

bind = SUPER, grave, hyprexpo:expo, toggle
# Navigate in expo:
# Click to select, Escape to cancel, Enter to confirm
```

---

## 96.5 Persistent Workspace Layouts

Hyprland workspaces are ephemeral by default — they disappear when all
windows close. Make them persistent:

```conf
# hyprland.conf — always-existing workspaces
workspace = 1, persistent:true, default:true
workspace = 2, persistent:true
workspace = 3, persistent:true, on-created-empty:kitty   # auto-open kitty when empty
workspace = special:scratch, on-created-empty:kitty
```

### Named workspaces

```conf
workspace = name:code,    persistent:true, monitor:DP-1
workspace = name:browser, persistent:true, monitor:HDMI-1
workspace = name:chat,    persistent:true, monitor:HDMI-1
workspace = name:music,   persistent:true
```

Switch by name:
```conf
bind = SUPER, F1, workspace, name:code
bind = SUPER, F2, workspace, name:browser
bind = SUPER, F3, workspace, name:chat
```

### Auto-assign apps to workspaces

```conf
# windowrulev2 approach
windowrulev2 = workspace name:browser silent, class:^(firefox)$
windowrulev2 = workspace name:chat silent,    class:^(discord)$
windowrulev2 = workspace name:music silent,   class:^(Spotify)$
windowrulev2 = workspace name:code,           class:^(kitty)$
```

`silent` means don't switch to that workspace when the app opens.

---

## 96.6 Per-Workspace Wallpaper (via pyprland)

```toml
[pyprland]
plugins = ["wall"]

[wall]
backend = "swww"

[wall.workspaces]
1 = "~/wallpapers/code.jpg"
2 = "~/wallpapers/browser.jpg"
3 = "~/wallpapers/chat.jpg"
"*" = "~/wallpapers/default.jpg"  # fallback
```

Or use the shell script approach from ch88:
```conf
exec-once = ~/.config/hypr/scripts/workspace-wallpaper.sh
```

---

## 96.7 Layout Automation Scripts

### Save and restore window layout

```bash
#!/bin/bash
# save-layout.sh — save current workspace → window mapping
hyprctl -j clients | jq '[.[] | {
  class: .class,
  workspace: .workspace.id,
  position: .at,
  size: .size,
  floating: .floating
}]' > ~/.config/hypr/layout-$(date +%Y%m%d).json

echo "Saved layout snapshot"
```

```bash
#!/bin/bash
# restore-layout.sh — launch apps on their saved workspaces
LAYOUT="${1:-$(ls ~/.config/hypr/layout-*.json | tail -1)}"

jq -r '.[] | "\(.workspace) \(.class)"' "$LAYOUT" | while read -r ws class; do
  cmd=$(grep -r "Exec=" /usr/share/applications/ \
    | grep -i "$class" | head -1 | cut -d= -f2-)
  [ -n "$cmd" ] && \
    hyprctl dispatch "exec [workspace $ws silent] $cmd"
done
```

### Focus recent windows (like Alt+Tab)

pyprland's `hyprfocus` or a simple IPC script:
```bash
#!/bin/bash
# Cycle through recent windows on current workspace
ws=$(hyprctl -j activeworkspace | jq -r '.id')
windows=$(hyprctl -j clients | jq -r \
  ".[] | select(.workspace.id==$ws) | .address" | tac)
# Pick via rofi
chosen=$(echo "$windows" | \
  while read -r addr; do
    hyprctl -j clients | jq -r ".[] | select(.address==\"$addr\") | .title"
  done | rofi -dmenu -p "Switch to")
addr=$(hyprctl -j clients | jq -r ".[] | select(.title==\"$chosen\") | .address")
[ -n "$addr" ] && hyprctl dispatch focuswindow "address:$addr"
```

---

## 96.8 Special Workspaces

Special workspaces are Hyprland's built-in scratchpad layer — they overlay on
any workspace:

```conf
# Define special workspaces
workspace = special:magic
workspace = special:code

# Send window to special
bind = SUPER, S,      movetoworkspacesilent, special:magic
bind = SUPER SHIFT, S, togglespecialworkspace, magic

# Multiple special workspaces
bind = SUPER, F4, togglespecialworkspace, code
bind = SUPER, F5, togglespecialworkspace, magic
```

Special workspaces stack — you can have several open simultaneously.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
