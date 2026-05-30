# Chapter 143 — Window Decorations: xdg-decoration-v1, CSD vs SSD

## Contents

- [Overview](#overview)
- [143.1 Client-Side vs Server-Side Decorations](#1431-client-side-vs-server-side-decorations)
- [143.2 xdg-decoration-v1 Protocol](#1432-xdg-decoration-v1-protocol)
  - [Negotiation flow](#negotiation-flow)
- [143.3 Compositor Behavior](#1433-compositor-behavior)
  - [Hyprland: CSD-first](#hyprland-csd-first)
  - [Sway: SSD default, respects client preference](#sway-ssd-default-respects-client-preference)
  - [KWin (KDE Plasma): full SSD with Breeze theme](#kwin-kde-plasma-full-ssd-with-breeze-theme)
  - [Niri: CSD-only](#niri-csd-only)
- [143.4 libdecor: CSD for Decoration-Unaware Clients](#1434-libdecor-csd-for-decoration-unaware-clients)
  - [libdecor plugins](#libdecor-plugins)
- [143.5 Forcing SSD or CSD for Specific Apps](#1435-forcing-ssd-or-csd-for-specific-apps)
  - [Sway: force no titlebar for specific apps](#sway-force-no-titlebar-for-specific-apps)
  - [Hyprland: remove compositor border for specific windows](#hyprland-remove-compositor-border-for-specific-windows)
- [143.6 zwp_server_decoration_manager_v1 (Legacy KWin Protocol)](#1436-zwpserverdecorationmanagerv1-legacy-kwin-protocol)
- [143.7 Debugging Decoration Issues](#1437-debugging-decoration-issues)
- [143.8 GTK and Qt Decoration Behavior Summary](#1438-gtk-and-qt-decoration-behavior-summary)

---


## Overview

The question of who draws the window titlebar — the application (client-side
decorations, CSD) or the compositor (server-side decorations, SSD) — is one
of the most visible and most argued-over aspects of Wayland desktop integration.
The `xdg-decoration-unstable-v1` protocol formalizes the negotiation. This chapter
explains the protocol, how each compositor handles it, how to force SSD or CSD
for specific applications, and how to use `libdecor` for CSD-unaware toolkits.

---

## 143.1 Client-Side vs Server-Side Decorations

**Server-Side Decorations (SSD)**: The compositor draws the titlebar, border, and
close/minimize/maximize buttons. All windows on the desktop have visually uniform
decorations matching the compositor theme. Window chrome is controlled by a single
set of compositor rules, not per-application code.

**Client-Side Decorations (CSD)**: The application draws its own titlebar inside
its window content area. The application has full creative control (custom fonts,
rounded corners, custom buttons). GNOME applications have used CSD since GTK3.
The compositor has no say in the visual appearance of individual window headers.

| Aspect | SSD | CSD |
|---|---|---|
| Visual consistency | Enforced by compositor | Per-toolkit, may differ |
| Compositor control | Full | None (app draws its own) |
| Borderless windows | Compositor handles | App requests `undecorated` |
| HiDPI scaling | Compositor handles | App must implement |
| Rounded corners | Compositor handles | App must implement |
| Shadows | Compositor handles | App must implement (or libdecor) |
| GTK4/libadwaita apps | CSD always | N/A |
| Qt apps (KDE) | Can use either | Depends on qtwayland |

---

## 143.2 xdg-decoration-v1 Protocol

The `zxdg_decoration_manager_v1` (stable in practice) protocol defines:

```
zxdg_decoration_manager_v1
  └─ get_toplevel_decoration(toplevel) → zxdg_toplevel_decoration_v1

zxdg_toplevel_decoration_v1
  ├─ set_mode(mode)      — client requests: NONE|CLIENT_SIDE|SERVER_SIDE
  ├─ unset_mode()        — client defers to compositor preference
  └─ [event] configure(mode) — compositor sends its decision
```

The `mode` values:
- `1` — CLIENT_SIDE: application draws its own decorations
- `2` — SERVER_SIDE: compositor draws decorations

### Negotiation flow

1. Client binds `zxdg_decoration_manager_v1`
2. After getting a `xdg_toplevel`, client calls `get_toplevel_decoration(toplevel)`
3. Client calls `set_mode(SERVER_SIDE)` if it prefers SSD, or `unset_mode()` to defer
4. Compositor sends `configure(mode)` with its final decision
5. Client must accept the compositor's decision — it cannot override it

A well-behaved application:
- Calls `unset_mode()` or `set_mode(CLIENT_SIDE)` if it has its own decorations
- Calls `set_mode(SERVER_SIDE)` if it has no decorations (terminal emulators, games)
- Respects whatever the compositor sends back in `configure`

---

## 143.3 Compositor Behavior

### Hyprland: CSD-first

Hyprland does not implement server-side decorations itself. All window titlebars
you see on Hyprland are drawn by applications (CSD) or by libraries like `libdecor`.
Hyprland adds its own compositor-level borders around windows, but these are accent
lines, not full titlebars.

```conf
# hyprland.conf — border settings are Hyprland's compositor borders, not SSD
general {
    border_size = 2
    col.active_border = rgba(7aa2f7ff)
    col.inactive_border = rgba(3b4261ff)
}

# To remove borders entirely:
windowrulev2 = noborder, class:^(.*) $
# Or for a specific app:
windowrulev2 = noborder, class:^(mpv)$
```

To check if an app is using CSD or requesting SSD from Hyprland:
```bash
# Hyprland reports "decora" for window decorations
hyprctl clients | grep -A5 "class: mpv"
```

### Sway: SSD default, respects client preference

Sway implements SSD and draws titlebars by default. Applications that request
CSD (via `set_mode(CLIENT_SIDE)`) will have their preference honored — Sway
won't add a titlebar on top. GTK4/libadwaita apps always get CSD since they
never request SSD.

```conf
# sway/config
# Default titlebar settings (SSD)
titlebar_border_thickness 2
titlebar_padding 6 4
font pango:JetBrainsMono Nerd Font 10

# Colors for SSD titlebars
# class                 border  bg       text     indicator child_border
client.focused          #7aa2f7 #24283b  #c0caf5  #7aa2f7   #7aa2f7
client.unfocused        #3b4261 #1a1b26  #565f89  #3b4261   #3b4261
client.focused_inactive #3b4261 #1f2335  #a9b1d6  #3b4261   #3b4261
client.urgent           #f7768e #f7768e  #1a1b26  #f7768e   #f7768e

# Disable titlebars for all windows (borders only, no title text)
default_border pixel 2

# Disable decorations entirely for a specific app
for_window [app_id="mpv"] border none
for_window [app_id="firefox"] border pixel 2
```

### KWin (KDE Plasma): full SSD with Breeze theme

KWin draws full SSD titlebars using the active Plasma window decoration theme.
Applications that set `CLIENT_SIDE` (GTK4 apps) still get CSD — KWin honors the request.

```bash
# KWin window decoration theme (set via System Settings)
# or via kwinrc:
# ~/.config/kwinrc
# [org.kde.kdecoration2]
# library=org.kde.breeze
# theme=Breeze

# Force SSD for a GTK app (overrides app preference) via KWin rules:
# System Settings → Window Management → Window Rules → Force decoration: Yes
```

### Niri: CSD-only

Like Hyprland, niri does not implement SSD. Niri draws its own compositor-level
focus indicator (colored border) but does not add titlebars.

```kdl
// ~/.config/niri/config.kdl
// Border settings (compositor borders, not SSD)
window-rule {
    geometry-corner-radius 8
    clip-to-geometry true
}

focus-ring {
    enable
    width 2
    active-color "#7aa2f7"
    inactive-color "#3b4261"
}

border {
    off
}
```

---

## 143.4 libdecor: CSD for Decoration-Unaware Clients

Some applications (SDL2 games, older toolkit apps) don't implement their own
CSD and don't request SSD via the protocol. On a CSD-only compositor like
Hyprland, these windows render borderless and titlebar-less with no way to
move or resize them by dragging a decoration.

`libdecor` solves this: it's a shared library that intercepts `xdg_toplevel`
creation and attaches CSD automatically to applications that link against it.

```bash
# Install
sudo pacman -S libdecor

# Check if an app uses libdecor
ldd /usr/bin/app-name | grep libdecor

# Force libdecor for apps that don't use it natively (SDL2 example)
SDL_VIDEODRIVER=wayland \
LIBDECOR_PLUGIN_DIR=/usr/lib/libdecor/plugins-1 \
/usr/bin/game
```

### libdecor plugins

libdecor has a plugin API. The default plugin draws GTK3-style decorations.
Distribution packages usually install the default plugin automatically:

```
/usr/lib/libdecor/plugins-1/libdecor-gtk.so
```

If you compile custom themes, drop them in `~/.local/lib/libdecor/plugins-1/`.

---

## 143.5 Forcing SSD or CSD for Specific Apps

### Sway: force no titlebar for specific apps

```conf
# sway/config
# CSD app: disable Sway's own titlebar overlay (it already has one)
for_window [app_id="org.gnome.Nautilus"] border pixel 1

# SSD-capable app that looks better without titlebars:
for_window [app_id="com.mitchellh.ghostty"] border none

# Force a window decoration even for CSD apps:
for_window [app_id="xdg-desktop-portal-gtk"] border pixel 2
```

### Hyprland: remove compositor border for specific windows

```conf
# hyprland.conf
# Remove the accent border (Hyprland's substitute for SSD) from specific apps
windowrulev2 = noborder, class:^(mpv)$
windowrulev2 = noborder, class:^(com.obsproject.Studio)$

# Add a specific border color to an app (override global)
windowrulev2 = bordercolor rgba(f7768eff) rgba(f7768e55), class:^(Gimp-2.10)$
```

---

## 143.6 zwp_server_decoration_manager_v1 (Legacy KWin Protocol)

Before `xdg-decoration-v1` was standardized, KWin used its own
`org_kde_kwin_server_decoration_manager` protocol. This is still supported by
KWin for backwards compatibility and by some Qt apps:

```
org_kde_kwin_server_decoration_manager_v1
  └─ create(surface) → org_kde_kwin_server_decoration
      ├─ request_mode(mode)  — NONE|CLIENT_SIDE|SERVER_SIDE
      └─ [event] mode(mode)  — compositor response
```

Modern Qt6/KDE applications use `xdg-decoration-v1` and fall back to the KWin
protocol only on older compositors. You normally don't need to interact with this
directly unless debugging a Qt5 app's decoration behavior.

---

## 143.7 Debugging Decoration Issues

```bash
# Check which protocols a compositor advertises
wayland-info | grep -i "decoration\|kwin_server"
# → zxdg_decoration_manager_v1 (version 1)

# Watch decoration negotiation in real time
WAYLAND_DEBUG=1 some-app 2>&1 | grep -i "decoration\|configure"

# For a specific app, check if it's CSD or SSD
# Hyprland: clients output includes "decora" field
hyprctl clients -j | python3 -c "
import json,sys
for c in json.load(sys.stdin):
    print(c['class'], 'mapped:', c['mapped'], 'decora:', c.get('decora', 'N/A'))
"

# Sway: check window properties
swaymsg -t get_tree | python3 -c "
import json,sys

def walk(node):
    if node.get('type') == 'con' and node.get('app_id'):
        print(node['app_id'], 'border:', node.get('current_border_width'))
    for n in node.get('nodes', []) + node.get('floating_nodes', []):
        walk(n)
walk(json.load(sys.stdin))
"
```

---

## 143.8 GTK and Qt Decoration Behavior Summary

| Toolkit | Default | Protocol used | Can be overridden |
|---|---|---|---|
| GTK3 (libadwaita-free) | CSD | xdg-decoration-v1 | Via `GTK_CSD=0` (limited) |
| GTK4 + libadwaita | CSD always | sets CLIENT_SIDE | No — hardcoded in libadwaita |
| Qt5 (qtwayland ≥5.15) | Follows compositor | xdg-decoration-v1 | `QT_WAYLAND_DECORATION=adwaita` |
| Qt6 (qtwayland ≥6.2) | Follows compositor | xdg-decoration-v1 | `QT_WAYLAND_DECORATION=material` |
| SDL2 | None (requests SSD) | xdg-decoration-v1 | Handled by compositor or libdecor |
| GTK3 (non-CSD apps) | Depends on `GtkSettings` | xdg-decoration-v1 | `GTK_CSD=0` disables for some |

```bash
# Force Qt to use a specific decoration plugin
QT_WAYLAND_DECORATION=adwaita my-qt-app

# Available Qt decoration plugins (on most distros):
# adwaita  — GTK-style decorations
# material — Material Design style
# none     — no decorations (your compositor draws them)
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
