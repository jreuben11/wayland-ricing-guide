# Chapter 137 — Touch Gestures on Wayland: Native and libinput

## Contents

- [Overview](#overview)
- [137.1 Native Gestures: Hyprland](#1371-native-gestures-hyprland)
  - [Four-Finger Gestures (via hyprexpo)](#four-finger-gestures-via-hyprexpo)
  - [Pinch-to-Zoom (via cursor:zoom_factor)](#pinch-to-zoom-via-cursorzoomfactor)
- [137.2 Native Gestures: Niri](#1372-native-gestures-niri)
- [137.3 Sway: No Native Gestures](#1373-sway-no-native-gestures)
- [137.4 libinput-gestures (Universal Fallback)](#1374-libinput-gestures-universal-fallback)
  - [Installation](#installation)
  - [Configuration](#configuration)
  - [Compositor-Specific Swipe Commands](#compositor-specific-swipe-commands)
  - [Running as a Service](#running-as-a-service)
- [137.5 touchegg (X11-Style Gesture Daemon)](#1375-touchegg-x11-style-gesture-daemon)
- [137.6 libinput Touchpad Configuration Reference](#1376-libinput-touchpad-configuration-reference)
- [137.7 Gesture Conflict: Compositor vs Userspace](#1377-gesture-conflict-compositor-vs-userspace)

---


## Overview

Touchpad gesture support on Wayland comes in two flavors: compositor-native gestures built directly into the compositor (zero latency, no extra daemon) and userspace tools like `libinput-gestures` that translate raw libinput events into actions. This chapter covers Hyprland's native gesture system, Sway's workarounds, Niri's gestures, and how to configure `libinput-gestures` and `touchegg` as fallbacks for compositors without native support.

**Cross-references:** Ch 43 — input customization (libinput config, tapclick, natural scroll). Ch 90 — touchscreen and tablet support. Ch 44 — accessibility (pinch-to-zoom). Ch 128 — screen magnification (cursor zoom).

---

## 137.1 Native Gestures: Hyprland

Hyprland has built-in gesture support for workspace switching via three-finger swipe, configurable directly in `hyprland.conf`:

```ini
# ~/.config/hypr/hyprland.conf

gestures {
    workspace_swipe         = true
    workspace_swipe_fingers = 3            # 3 fingers (default)
    workspace_swipe_distance = 300         # pixels of travel to trigger switch
    workspace_swipe_invert   = true        # swipe left = go right (natural scroll)
    workspace_swipe_min_speed_to_force = 30  # px/s to force switch mid-swipe
    workspace_swipe_cancel_ratio = 0.5     # how far back to cancel a swipe
    workspace_swipe_create_new  = true     # create new workspace at end
    workspace_swipe_forever     = false    # keep scrolling past last workspace
    workspace_swipe_numbered_end = false   # wrap to workspace 1 at end
    workspace_swipe_direction_lock = true  # lock horizontal after initial movement
    workspace_swipe_direction_lock_threshold = 10  # px before locking direction
}
```

With `workspace_swipe = true`, a three-finger horizontal swipe switches workspaces with live animation — the swipe drives the workspace animation in real time.

### Four-Finger Gestures (via hyprexpo)

Hyprland doesn't natively support four-finger gestures, but the `hyprexpo` plugin adds a four-finger pinch → overview effect:

```ini
# ~/.config/hypr/hyprland.conf (with hyprexpo loaded via hyprpm)
plugin {
    hyprexpo {
        columns = 3
        gap_size = 5
        bg_col = rgb(111111)
        workspace_method = center current

        enable_gesture = true          # enable 4-finger pinch
        gesture_fingers = 4            # number of fingers
        gesture_distance = 300         # swipe distance to open
        gesture_positive = true        # pinch open (not close)
    }
}

bind = SUPER, grave, hyprexpo:expo, toggle   # keyboard fallback
```

### Pinch-to-Zoom (via cursor:zoom_factor)

There is no native pinch-to-zoom compositor gesture in Hyprland as of 2025, but you can map it via `libinput-gestures` + `hyprctl`:

```bash
# ~/.config/libinput-gestures.conf
gesture pinch in  4  hyprctl keyword cursor:zoom_factor 0.8
gesture pinch out 4  hyprctl keyword cursor:zoom_factor 1.25
```

---

## 137.2 Native Gestures: Niri

Niri has built-in touchpad gesture support for workspace and column switching:

```kdl
// ~/.config/niri/config.kdl

gestures {
    // Three-finger swipe switches workspaces (horizontal)
    hot-edge {
        enable true
    }
}
```

Niri's gesture bindings for three-finger swipe are automatic when gestures are enabled — left/right switches workspaces, up/down switches between columns in the scrollable workspace model.

Check Niri documentation for the current gesture config schema as it evolves with each release:
```bash
niri --help | grep gesture
```

---

## 137.3 Sway: No Native Gestures

Sway does not have built-in touchpad gesture support. The two options are:

1. **`libinput-gestures`** — userspace daemon (§137.4)
2. **`swayr`** — Sway window switcher that can be triggered via gestures

---

## 137.4 libinput-gestures (Universal Fallback)

`libinput-gestures` reads raw libinput events from the `/dev/input` device and executes configured commands. It works on any Wayland compositor that doesn't block the input device.

### Installation

```bash
# Arch Linux
sudo pacman -S libinput-gestures

# Ubuntu
sudo apt install libinput-gestures

# Add user to input group (required for device access)
sudo usermod -aG input $USER
# Log out and back in for group to take effect

# Verify access
libinput debug-events --verbose 2>&1 | head -20
```

### Configuration

```bash
# ~/.config/libinput-gestures.conf

# Default gesture speed threshold (0.0–1.0)
gesture_threshold 0.5

# Three-finger swipe: workspace switching (Hyprland)
gesture swipe right 3  hyprctl dispatch workspace e-1
gesture swipe left  3  hyprctl dispatch workspace e+1

# Three-finger swipe: workspace switching (Sway)
# gesture swipe right 3  swaymsg workspace prev
# gesture swipe left  3  swaymsg workspace next

# Three-finger swipe up: show overview / launcher
gesture swipe up    3  fuzzel

# Three-finger swipe down: close window
gesture swipe down  3  hyprctl dispatch killactive

# Four-finger swipe: volume
gesture swipe up    4  pactl set-sink-volume @DEFAULT_SINK@ +5%
gesture swipe down  4  pactl set-sink-volume @DEFAULT_SINK@ -5%

# Pinch in/out: zoom (Hyprland)
gesture pinch in    2  hyprctl keyword cursor:zoom_factor 0.8
gesture pinch out   2  hyprctl keyword cursor:zoom_factor 1.25

# Pinch reset
gesture pinch in    2  hyprctl keyword cursor:zoom_factor 1.0
```

### Compositor-Specific Swipe Commands

```bash
# Hyprland
hyprctl dispatch workspace e+1   # next workspace (relative)
hyprctl dispatch workspace e-1   # prev workspace (relative)
hyprctl dispatch movetoworkspace e+1  # move window to next workspace

# Sway
swaymsg workspace next_on_output
swaymsg workspace prev_on_output

# River
riverctl set-focused-tags $(($(riverctl get-focused-tags) << 1))  # next tag

# Niri
niri msg action focus-workspace-down
niri msg action focus-workspace-up
```

### Running as a Service

```bash
# Start manually
libinput-gestures-setup start

# Add to compositor startup
# Hyprland:
exec-once = libinput-gestures

# Or as a systemd user service:
cat > ~/.config/systemd/user/libinput-gestures.service << 'EOF'
[Unit]
Description=libinput-gestures
After=graphical-session.target

[Service]
ExecStart=/usr/bin/libinput-gestures
Restart=on-failure

[Install]
WantedBy=graphical-session.target
EOF

systemctl --user enable --now libinput-gestures.service
```

---

## 137.5 touchegg (X11-Style Gesture Daemon)

`touchegg` is a gesture daemon originally written for X11 but with Wayland support via a compositor plugin. On Hyprland and wlroots compositors, it works through an input method bridge.

```bash
# Arch AUR
yay -S touchegg

# Ubuntu
sudo add-apt-repository ppa:touchegg/stable
sudo apt install touchegg
```

```xml
<!-- ~/.config/touchegg/touchegg.conf -->
<touchégg>
  <settings>
    <property name="animation_delay">150</property>
    <property name="action_execute_threshold">20</property>
  </settings>

  <application name="All">
    <!-- Three-finger swipe left/right = workspace switch -->
    <gesture type="SWIPE" fingers="3" direction="LEFT">
      <action type="CHANGE_DESKTOP">
        <direction>next</direction>
        <animate>true</animate>
      </action>
    </gesture>
    <gesture type="SWIPE" fingers="3" direction="RIGHT">
      <action type="CHANGE_DESKTOP">
        <direction>previous</direction>
        <animate>true</animate>
      </action>
    </gesture>

    <!-- Four-finger pinch = fullscreen -->
    <gesture type="PINCH" fingers="4" direction="IN">
      <action type="FULLSCREEN_WINDOW" />
    </gesture>

    <!-- Three-finger tap = middle click -->
    <gesture type="TAP" fingers="3">
      <action type="MOUSE_CLICK">
        <button>2</button>
      </action>
    </gesture>
  </application>
</touchégg>
```

> **Note:** `touchegg` Wayland support depends on a Hyprland plugin (`hyprland-touchegg`) being available. As of 2025, `libinput-gestures` with direct IPC calls is more reliable for wlroots compositors.

---

## 137.6 libinput Touchpad Configuration Reference

While not gestures per se, these libinput settings affect the gesture detection quality:

```bash
# Hyprland
input {
    touchpad {
        natural_scroll     = true    # two-finger scroll: invert direction
        disable_while_typing = true
        tap-to-click       = true    # tap = click
        drag_lock          = false
        scroll_method      = two_finger  # two_finger | edge | none
        middle_button_emulation = false
        clickfinger_behavior = false    # false = area-based, true = finger-count
    }
    scroll_factor = 0.4    # touchpad scroll speed (0.1–1.0)
    sensitivity   = -0.2   # pointer speed (-1.0 to 1.0)
}

# Sway
input "type:touchpad" {
    natural_scroll    enabled
    tap               enabled
    tap_button_map    lrm       # one/two/three finger = left/right/middle
    dwt               enabled   # disable while typing
    scroll_method     two_finger
    accel_profile     adaptive
    pointer_accel     -0.2
}
```

```bash
# Verify gestures are detected at libinput level
libinput debug-events --verbose 2>&1 | grep -i gesture

# Check touchpad capabilities
libinput list-devices | grep -A10 "Touchpad"
```

---

## 137.7 Gesture Conflict: Compositor vs Userspace

When using both native compositor gestures and `libinput-gestures`, conflicts may arise (both react to the same gesture). Resolution:

| Compositor | Three-finger swipe | Recommendation |
|---|---|---|
| Hyprland | Native (preferred) | Disable in libinput-gestures; use native |
| Sway | No native | Use libinput-gestures fully |
| Niri | Native | Disable in libinput-gestures |
| River | No native | Use libinput-gestures |
| KWin | Native | Use KDE System Settings; disable libinput-gestures |

```bash
# If running Hyprland with native gestures, comment out conflicting lines:
# ~/.config/libinput-gestures.conf
# gesture swipe right 3  ...   ← comment out; Hyprland handles this
# gesture swipe left  3  ...   ← comment out

# Keep pinch and four-finger gestures that Hyprland doesn't handle:
gesture pinch out 2  hyprctl keyword cursor:zoom_factor 1.25
gesture pinch in  2  hyprctl keyword cursor:zoom_factor 0.8
gesture swipe up  4  fuzzel    # four-finger = launcher
```
