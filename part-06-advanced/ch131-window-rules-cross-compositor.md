# Chapter 131 — Per-Window Rules: Cross-Compositor Deep Dive

## Contents

- [Overview](#overview)
- [131.1 How Compositors Match Windows](#1311-how-compositors-match-windows)
- [131.2 Hyprland: windowrulev2](#1312-hyprland-windowrulev2)
  - [Match Criteria](#match-criteria)
  - [Actions Reference](#actions-reference)
  - [Layer Rules (for bars, overlays)](#layer-rules-for-bars-overlays)
- [131.3 Sway: for_window](#1313-sway-forwindow)
- [131.4 River: Rule-Add](#1314-river-rule-add)
- [131.5 Niri: window-rules](#1315-niri-window-rules)
- [131.6 KWin Rules](#1316-kwin-rules)
- [131.7 Common Recipes](#1317-common-recipes)
  - [Float all system dialogs](#float-all-system-dialogs)
  - [Firefox Picture-in-Picture](#firefox-picture-in-picture)
  - [Steam — float launcher, tile games](#steam-float-launcher-tile-games)
  - [Dropdown terminal (scratchpad)](#dropdown-terminal-scratchpad)
  - [Media players — float and idle inhibit](#media-players-float-and-idle-inhibit)
  - [OBS on secondary monitor](#obs-on-secondary-monitor)
  - [Prevent focus stealing](#prevent-focus-stealing)
- [131.8 Debugging Window Rules](#1318-debugging-window-rules)

---

> **No additional installation required.** Window rules are built into Hyprland, Sway, River, Niri, and KWin. Install your compositor of choice (see Part II) and the rules are available immediately.

---


## Overview

Window rules are the backbone of a functional rice: they ensure media players float, PiP windows stay pinned, game launchers don't steal focus, and terminals open on the right workspace. Every compositor has its own syntax, but the concepts map 1:1. This chapter provides the complete rule reference for Hyprland, Sway, River, Niri, and KWin, followed by a recipe library of cross-compositor patterns.

**Cross-references:** Ch 08 — Hyprland config overview. Ch 07 — Sway config. Ch 10 — River. Ch 11 — Niri. Ch 66 — KDE Plasma 6. Ch 96 — workspace automation (rules + scripts).

---

## 131.1 How Compositors Match Windows

All compositors match windows against **criteria** (what the window is) and apply **actions** (what to do with it). The criteria differ in name but draw from the same sources:

| Criteria source | Hyprland | Sway | Niri | KWin |
|---|---|---|---|---|
| App identifier | `class` | `app_id` (Wayland) / `class` (X11) | `app-id` | `resourceClass` |
| Window title | `title` | `title` | `title` | `caption` |
| Instance name | `initialClass` | — | — | `resourceName` |
| Window type | — | `window_type` | — | `type` |
| Workspace | `workspace` | `workspace` | `workspace` | — |
| Floating state | `floating` | `floating` | `is-floating` | — |

Find a window's class and title:
```bash
# Hyprland
hyprctl clients | grep -A5 "class\|title"

# Sway
swaymsg -t get_tree | jq '.. | select(.type?=="con") | {app_id, name}'

# Any compositor — from the terminal
xprop WM_CLASS WM_NAME   # X11 windows only (via XWayland)
```

---

## 131.2 Hyprland: windowrulev2

Hyprland's `windowrulev2` is the current (v2) syntax. All rules follow:
```ini
windowrulev2 = action, criteria1:value1, criteria2:value2
```

### Match Criteria

```ini
# By application class (use regex)
windowrulev2 = float, class:^(mpv|vlc|celluloid)$

# By window title
windowrulev2 = float, title:^(Picture-in-Picture)$

# Class AND title (both must match)
windowrulev2 = float, class:^firefox$, title:^Picture-in-Picture$

# Initial class/title (set at creation, doesn't change)
windowrulev2 = workspace 3, initialClass:^steam$

# Workspace
windowrulev2 = opacity 0.9 0.85, workspace:^3$

# Floating windows only
windowrulev2 = center, floating:1

# Fullscreen windows
windowrulev2 = noanim, fullscreen:1

# Tag-based (tag with windowrule first)
windowrulev2 = tag +media, class:^(mpv|vlc)$
windowrulev2 = float, tag:media
```

### Actions Reference

**Positioning & sizing:**
```ini
windowrulev2 = float,              class:^pavucontrol$
windowrulev2 = center,             class:^pavucontrol$
windowrulev2 = size 800 500,       class:^pavucontrol$
windowrulev2 = move 100 100,       class:^pavucontrol$    # absolute
windowrulev2 = move cursor -50 -50, class:^pavucontrol$   # relative to cursor
windowrulev2 = minsize 400 300,    class:^pavucontrol$
windowrulev2 = maxsize 1200 800,   class:^pavucontrol$
```

**Workspace & monitor:**
```ini
windowrulev2 = workspace 2,        class:^firefox$
windowrulev2 = workspace 2 silent, class:^firefox$       # don't switch to it
windowrulev2 = workspace special:scratch, class:^scratch$
windowrulev2 = monitor HDMI-A-1,   class:^obs$
```

**Appearance:**
```ini
windowrulev2 = opacity 0.92 0.85,  class:^kitty$         # active inactive
windowrulev2 = noblur,             class:^firefox$
windowrulev2 = noshadow,           class:^waybar$
windowrulev2 = noborder,           class:^waybar$
windowrulev2 = rounding 0,         class:^steam$
windowrulev2 = rounding 16,        class:^kitty$
```

**Animation:**
```ini
windowrulev2 = animation slide,    class:^rofi$
windowrulev2 = animation popin 80%, class:^pavucontrol$
windowrulev2 = noanim,             class:^waybar$
```

**Focus & input:**
```ini
windowrulev2 = noinitialfocus,     class:^steam$          # don't steal focus
windowrulev2 = nofocus,            class:^waybar$
windowrulev2 = pin,                class:^mpv$, title:^Picture-in-Picture$
windowrulev2 = stayfocused,        class:^rofi$
```

**Other:**
```ini
windowrulev2 = immediate,          class:^cs2$            # tearing (gaming)
windowrulev2 = idleinhibit focus,  class:^(mpv|vlc)$      # prevent idle while focused
windowrulev2 = idleinhibit fullscreen, class:.*           # prevent idle when fullscreen
windowrulev2 = fullscreen,         class:^kodi$
windowrulev2 = group deny,         class:^steam$          # exclude from groups
```

### Layer Rules (for bars, overlays)

```ini
layerrule = noanim, waybar
layerrule = blur, waybar
layerrule = ignorealpha 0.5, waybar    # don't blur below 50% alpha
layerrule = noblur, rofi
```

---

## 131.3 Sway: for_window

Sway uses `for_window` with criteria in square brackets:

```ini
# ~/.config/sway/config

# Float dialogs
for_window [window_type="dialog"]         floating enable
for_window [window_type="utility"]        floating enable
for_window [window_type="toolbar"]        floating enable
for_window [window_type="splash"]         floating enable

# By app_id (Wayland native apps)
for_window [app_id="pavucontrol"]         floating enable, resize set 800 500
for_window [app_id="nm-connection-editor"] floating enable
for_window [app_id="org.gnome.Nautilus"]  floating enable, resize set 900 600

# By class (X11 / XWayland apps)
for_window [class="Steam" title="Steam"]  floating enable
for_window [class="Gimp"]                 floating enable

# Title matching
for_window [title="Picture-in-Picture"]   floating enable, sticky enable

# Workspace assignment
for_window [app_id="firefox"]    assign to workspace 2
for_window [app_id="thunderbird"] assign to workspace 4
for_window [class="Steam"]       assign to workspace 5

# Opacity
for_window [app_id="kitty"]      opacity 0.92

# Inhibit idle
for_window [app_id="mpv"]        inhibit_idle focus
for_window [app_id="firefox" title=".*YouTube.*"] inhibit_idle focus
```

Sway criteria reference:

| Criterion | Description | Example |
|---|---|---|
| `app_id` | Wayland app identifier (regex) | `app_id="^kitty$"` |
| `class` | X11 WM_CLASS | `class="^Steam$"` |
| `instance` | X11 WM_CLASS instance | `instance="..."` |
| `title` | Window title (regex) | `title="Picture-in-Picture"` |
| `window_type` | X11 type | `window_type="dialog"` |
| `window_role` | X11 WM_WINDOW_ROLE | `window_role="pop-up"` |
| `workspace` | Current workspace | `workspace="^2$"` |
| `floating` | Floating state | `floating` |
| `tiling` | Tiling state | `tiling` |

---

## 131.4 River: Rule-Add

River 0.3+ added `riverctl rule-add` for per-window rules:

```bash
# Float by app-id
riverctl rule-add -app-id "pavucontrol"       float
riverctl rule-add -app-id "nm-connection-editor" float

# Float by title
riverctl rule-add -title  "Picture-in-Picture"  float

# Assign to tag (River uses tag bitmasks, not workspaces)
# Tag 4 = 1<<3 = 8
riverctl rule-add -app-id "firefox"    tags $((1 << 1))   # tag 2
riverctl rule-add -app-id "thunderbird" tags $((1 << 3))  # tag 4

# Assign to output
riverctl rule-add -app-id "obs"  output HDMI-A-1

# CSD/SSD mode
riverctl rule-add -app-id "firefox"  ssd   # server-side decorations
```

Add these to `~/.config/river/init`:
```bash
# Floating windows
riverctl rule-add -app-id "float"             float
riverctl rule-add -title  "^(Open|Save).*"    float
riverctl rule-add -app-id "xdg-desktop-portal*" float
```

---

## 131.5 Niri: window-rules

Niri uses a `window-rules` section in `~/.config/niri/config.kdl`:

```kdl
// ~/.config/niri/config.kdl

window-rule {
    // Float pavucontrol
    match app-id="org.pulseaudio.pavucontrol"
    open-floating true
    default-floating-size width=800 height=500
}

window-rule {
    // PiP always on top, floating
    match title="Picture-in-Picture"
    open-floating true
    open-on-output "HDMI-A-1"
}

window-rule {
    // Open Firefox on workspace "web"
    match app-id="org.mozilla.firefox"
    open-on-workspace "web"
}

window-rule {
    // Opacity for terminals
    match app-id="foot"
    opacity 0.92
}

window-rule {
    // Fullscreen games
    match app-id="cs2"
    open-fullscreen true
}

window-rule {
    // Block out scratchpad terminal from snapping
    match is-floating true
    // (no snapping for floaters)
}

window-rule {
    // OBS on second monitor
    match app-id="com.obsproject.Studio"
    open-on-output "HDMI-A-1"
    open-maximized true
}
```

Niri match properties:

| Property | Description |
|---|---|
| `app-id` | Wayland app ID (glob pattern) |
| `title` | Window title (glob pattern) |
| `is-focused` | Currently focused window |
| `is-floating` | Floating state |
| `at-startup` | Only applies during session startup |

Niri actions:

| Action | Description |
|---|---|
| `open-on-output "name"` | Target monitor |
| `open-on-workspace "name"` | Target named workspace |
| `open-fullscreen true` | Open fullscreen |
| `open-floating true` | Open floating |
| `open-centered true` | Center on screen |
| `default-floating-size width=N height=M` | Default float size |
| `opacity N` | Window opacity (0.0–1.0) |

---

## 131.6 KWin Rules

KDE Plasma's KWin stores rules in `~/.config/kwinrulesrc`. The GUI is at System Settings → Window Management → Window Rules.

```ini
# ~/.config/kwinrulesrc
[1]
Description=Float mpv
above=true
aboverule=2
clientmachine=localhost
clientmachinematch=0
floating=true
floatingrule=2
noborder=true
noborderrule=2
title=mpv
titlematch=1
wmclass=mpv
wmclasscomplete=false
wmclassmatch=1

[2]
Description=Assign Firefox to desktop 2
desktop=2
desktoprule=2
wmclass=firefox
wmclasscomplete=false
wmclassmatch=1

[General]
count=2
```

Rules are most easily created via:
```
System Settings → Window Management → Window Rules → Add Rule
```
Then right-click any window → More Actions → Configure Special Window Settings.

---

## 131.7 Common Recipes

### Float all system dialogs

```ini
# Hyprland
windowrulev2 = float, class:^(xdg-desktop-portal|xdg-desktop-portal-gtk)$
windowrulev2 = float, title:^(Open File|Open Folder|Save File|Save As)$
windowrulev2 = center, title:^(Open File|Open Folder|Save File|Save As)$

# Sway
for_window [window_type="dialog"]          floating enable, border pixel 2
for_window [title="^(Open|Save).*"]        floating enable
for_window [app_id="xdg-desktop-portal*"]  floating enable
```

### Firefox Picture-in-Picture

```ini
# Hyprland
windowrulev2 = float,   class:^firefox$, title:^Picture-in-Picture$
windowrulev2 = pin,     class:^firefox$, title:^Picture-in-Picture$
windowrulev2 = size 480 270, class:^firefox$, title:^Picture-in-Picture$
windowrulev2 = move 1430 800, class:^firefox$, title:^Picture-in-Picture$
windowrulev2 = noinitialfocus, class:^firefox$, title:^Picture-in-Picture$

# Sway
for_window [app_id="firefox" title="Picture-in-Picture"] \
    floating enable, sticky enable, resize set 480 270, \
    move position 1430 800
```

### Steam — float launcher, tile games

```ini
# Hyprland
windowrulev2 = float,              class:^steam$, title:^Steam$
windowrulev2 = noinitialfocus,     class:^steam$
windowrulev2 = workspace 5 silent, class:^steam$
windowrulev2 = fullscreen,         class:^cs2$
windowrulev2 = immediate,          class:^cs2$    # tearing control
windowrulev2 = idleinhibit always, class:^cs2$

# Sway
for_window [class="Steam" title="Steam"]  floating enable
for_window [class="Steam"]                assign to workspace 5
```

### Dropdown terminal (scratchpad)

```ini
# Hyprland — create a named scratchpad
bind = SUPER, grave, togglespecialworkspace, dropdown
windowrulev2 = workspace special:dropdown, class:^(dropdown)$
windowrulev2 = float,  class:^(dropdown)$
windowrulev2 = size 1200 500, class:^(dropdown)$
windowrulev2 = move center, class:^(dropdown)$
windowrulev2 = animation slide, class:^(dropdown)$

# Launch with class "dropdown":
bind = SUPER, grave, exec, [workspace special:dropdown] foot --app-id=dropdown
```

```bash
# Sway — scratchpad
for_window [app_id="dropdown"] move to scratchpad, resize set 1200 500
bindsym $mod+grave exec --no-startup-id \
    swaymsg '[app_id="dropdown"] scratchpad show' || \
    foot --app-id=dropdown
```

### Media players — float and idle inhibit

```ini
# Hyprland
windowrulev2 = float,              class:^(mpv|vlc|celluloid|stremio)$
windowrulev2 = size 1280 720,      class:^(mpv|vlc|celluloid)$
windowrulev2 = center,             class:^(mpv|vlc|celluloid)$
windowrulev2 = idleinhibit focus,  class:^(mpv|vlc|celluloid)$
windowrulev2 = idleinhibit fullscreen, class:.*

# Sway
for_window [app_id="mpv"]           floating enable, resize set 1280 720
for_window [app_id="vlc"]           floating enable
bindsym $mod+i inhibit_idle focus   # toggle per-window idle inhibit
```

### OBS on secondary monitor

```ini
# Hyprland
windowrulev2 = monitor HDMI-A-1,         class:^com.obsproject.Studio$
windowrulev2 = workspace 9 silent,       class:^com.obsproject.Studio$
windowrulev2 = noblur,                   class:^com.obsproject.Studio$

# Niri
window-rule {
    match app-id="com.obsproject.Studio"
    open-on-output "HDMI-A-1"
    open-maximized true
}
```

### Prevent focus stealing

```ini
# Hyprland — apps that should not steal focus
windowrulev2 = noinitialfocus, class:^(steam|discord|slack|telegram-desktop)$

# Also useful: focus urgency without switching
misc {
    focus_on_activate = false  # don't switch to urgent windows
}
```

---

## 131.8 Debugging Window Rules

```bash
# Hyprland — which rules apply to the focused window?
hyprctl activewindow   # shows class, title, workspace, floating state

# Test a regex match
echo "com.obsproject.Studio" | grep -P "^com\.obsproject\.Studio$"

# Hyprland — live window event log (shows class/title as windows open)
socat - UNIX-CONNECT:/tmp/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock \
  | grep --line-buffered "openwindow"

# Sway — list all open windows with criteria info
swaymsg -t get_tree | jq -r '
  .. | select(.type?=="con" and .name!=null) |
  "\(.app_id // .window_properties.class)\t\(.name)"
'
```
