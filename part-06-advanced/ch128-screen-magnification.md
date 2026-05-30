# Chapter 128 — Screen Magnification on Wayland

## Overview

Screen magnification on Wayland lacks a single universal solution — unlike X11's `xmag` or GNOME's built-in zoom, each compositor has a different approach. This chapter covers the main options: Hyprland's cursor zoom, Sway's magnification workarounds, the standalone `magnus` tool, and the accessibility-grade magnification via `at-spi2` for GNOME.

**Cross-references:** Ch 44 — accessibility on Wayland. Ch 41 — HiDPI scaling (distinct from magnification). Ch 90 — touchscreen and tablet input (zoom gestures).

---

## 128.1 Hyprland: cursor:zoom_factor

Hyprland has built-in zoom centered on the cursor, controlled by `cursor:zoom_factor` in the config and IPC commands.

### Configuration

```ini
# ~/.config/hypr/hyprland.conf
cursor {
    zoom_factor = 1.0   # 1.0 = no zoom (default)
    zoom_rigid = false  # false = zoom follows cursor, true = fixed center
}
```

### Runtime Control via Keybinds

```ini
# Zoom in/out with Ctrl+scroll
bind = CTRL, mouse_up,   exec, hyprctl keyword cursor:zoom_factor $(echo "$(hyprctl getoption cursor:zoom_factor | grep float | awk '{print $2}') 1.2" | awk '{printf "%.1f", $1 * $2}')
bind = CTRL, mouse_down, exec, hyprctl keyword cursor:zoom_factor $(echo "$(hyprctl getoption cursor:zoom_factor | grep float | awk '{print $2}') 1.2" | awk '{printf "%.1f", $1 / $2}')

# Or simpler — toggle between 1.0 and 2.0
bind = SUPER, Z, exec, hyprctl keyword cursor:zoom_factor 2.0
bind = SUPER SHIFT, Z, exec, hyprctl keyword cursor:zoom_factor 1.0
```

### Zoom Script

```bash
#!/bin/bash
# ~/.local/bin/hypr-zoom
# Usage: hypr-zoom [in|out|reset] [factor]

CURRENT=$(hyprctl getoption cursor:zoom_factor | grep float | awk '{print $2}')
STEP=1.25

case "$1" in
    in)    NEW=$(echo "$CURRENT * $STEP" | bc -l | xargs printf "%.2f") ;;
    out)   NEW=$(echo "$CURRENT / $STEP" | bc -l | xargs printf "%.2f") ;;
    reset) NEW=1.0 ;;
    *)     echo "Current zoom: ${CURRENT}x"; exit 0 ;;
esac

# Clamp to [1.0, 5.0]
NEW=$(echo "$NEW 1.0 5.0" | awk '{if ($1<$2) $1=$2; if ($1>$3) $1=$3; print $1}')
hyprctl keyword cursor:zoom_factor "$NEW"
```

```ini
# Keybinds using the script
bind = SUPER, equal, exec, ~/.local/bin/hypr-zoom in
bind = SUPER, minus, exec, ~/.local/bin/hypr-zoom out
bind = SUPER, 0,     exec, ~/.local/bin/hypr-zoom reset
```

---

## 128.2 magnus: Floating Magnifier Window

`magnus` is a small GTK application that shows a magnified view of the area around the cursor in a floating window. It uses `zwlr_screencopy_manager_v1` to capture screen content.

### Installation

```bash
# Arch AUR
yay -S magnus

# From source
git clone https://github.com/stuartlangridge/magnus
cd magnus && meson build && ninja -C build
sudo ninja -C build install
```

### Usage

```bash
# Start with 2× zoom (default)
magnus

# Specify zoom level
magnus --zoom 3

# Specify window size
magnus --zoom 2 --width 400 --height 300
```

magnus opens a small window that follows your cursor with a magnified view. Bind it to a keybind for on-demand use:

```ini
# Hyprland
bind = SUPER, M, exec, magnus --zoom 3
```

### Limitations

magnus uses screencopy which has a latency of 1–3 frames. It is not suitable for pixel-precise work but is useful for reading small text. For zero-latency magnification, Hyprland's `cursor:zoom_factor` is preferable.

---

## 128.3 Sway: No Built-in Zoom

Sway does not have built-in zoom. Workarounds:

**Option A:** Use `magnus` (§128.2) — works on Sway via wlr-screencopy.

**Option B:** Compositor zoom via `wl-zoom` (if available in AUR):
```bash
yay -S wl-zoom   # community tool, availability varies
```

**Option C:** Create a virtual magnified output using `wlr-virtual-output` and a mirroring tool:
```bash
# Create a small virtual output
wlr-virtual-output create --name MAG --width 400 --height 300

# Mirror the area around cursor onto it using wl-mirror
wl-mirror eDP-1 &   # shows full screen; combine with crop filter
```

---

## 128.4 GNOME: Built-in Universal Access Zoom

GNOME Shell has first-class magnification via Universal Access:

```bash
# Enable from settings
gsettings set org.gnome.desktop.a11y.applications screen-magnifier-enabled true

# Set zoom factor
gsettings set org.gnome.desktop.a11y.magnifier mag-factor 2.0

# Follow mouse mode
gsettings set org.gnome.desktop.a11y.magnifier mouse-tracking "centered"
# Options: "none", "proportional", "push", "centered"

# Keyboard shortcut to toggle (Super+Alt+8 by default)
# Or enable via: Settings → Accessibility → Zoom
```

---

## 128.5 Accessibility vs. Ricing Zoom

| Use case | Best tool | Why |
|---|---|---|
| Quickly read small text | Hyprland `zoom_factor` | Zero latency, compositor-native |
| Pixel-level inspection | `magnus` | Floating window, stays visible |
| Permanent low-vision aid | GNOME zoom / KDE zoom | Full-featured accessibility magnifier |
| Presentation zoom-in | Hyprland zoom + keybind | Live, follows cursor |
| Screenshot magnification | `swappy` or `imagemagick` | Post-capture, not live |

For ricing presentations (screen recording, streaming), Hyprland's `cursor:zoom_factor` is the most polished option: it magnifies the entire compositor output including the cursor, with no visible artifacts or latency.
