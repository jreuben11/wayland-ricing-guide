# Chapter 90 — Touchscreen and Drawing Tablet Support

## Overview

Wayland handles touch and stylus input through libinput, with compositors
exposing it via the `wl_touch` and `zwp_tablet_v2` protocols. This chapter
covers touchscreen gesture configuration, Wacom/OpenTabletDriver for drawing
tablets, on-screen keyboards, and tablet mode switching.

---

## 90.1 Touchscreen Gestures in Hyprland

Hyprland's `gestures` block configures multi-finger swipe gestures on touchpads
and touchscreens:

```conf
gestures {
    workspace_swipe = on
    workspace_swipe_fingers = 3
    workspace_swipe_distance = 300
    workspace_swipe_invert = yes        # swipe direction
    workspace_swipe_min_speed_to_force = 30
    workspace_swipe_cancel_ratio = 0.5
    workspace_swipe_create_new = yes    # create new workspace at boundary
    workspace_swipe_direction_lock = yes
    workspace_swipe_direction_lock_threshold = 10
    workspace_swipe_forever = no        # if yes, keep swiping past boundary
    workspace_swipe_numbered = no       # use workspace numbers not e+/-1
    workspace_swipe_use_r = no          # use r+1/r-1 (relative)
}
```

### Touchscreen-specific input device config

```conf
# Target a specific touchscreen device
device {
    name = elan-touchscreen-rmi      # from hyprctl devices
    enabled = true
    transform = 0                    # 0=none, 1=90°, 2=180°, 3=270°
    output = eDP-1                   # map touch to this output
}
```

Map touch events to a specific output (critical on multi-monitor setups):
```conf
device {
    name = wacom-touch
    output = HDMI-1    # touch events go to this monitor
}
```

Find device names: `hyprctl devices | grep -A3 "Touch"`

---

## 90.2 Touchscreen in Sway

```conf
# sway config
input "1386:21588:Wacom_Pen_and_multitouch_sensor_Finger" {
    map_to_output HDMI-1       # map touchscreen to monitor
    events enabled
}

# Multi-touch gestures (sway uses libinput gestures directly)
# swipe gestures for workspaces — use swayr or a gesture daemon
```

### libinput-gestures (touchpad/touchscreen gesture daemon)

```bash
paru -S libinput-gestures

# ~/.config/libinput-gestures.conf
gesture swipe right 3  swaymsg workspace next
gesture swipe left  3  swaymsg workspace prev
gesture swipe up    4  swaymsg fullscreen toggle
gesture pinch in    2  swaymsg gaps inner all plus 5
gesture pinch out   2  swaymsg gaps inner all minus 5

# Autostart
libinput-gestures-setup autostart start
```

---

## 90.3 Drawing Tablets

### Wacom tablets (libwacom + kernel driver)

Most Wacom tablets work with the kernel's `wacom` driver and `libwacom`:

```bash
sudo pacman -S libwacom
# Verify detection:
libwacom-list-local-devices
```

#### Hyprland tablet configuration

```conf
# Map tablet to a specific output
device {
    name = wacom-intuos-pro-m-pen    # from hyprctl devices
    output = HDMI-1
    # Tablet area mapping (0.0–1.0 of tablet surface)
    # active_area_start = 0.0 0.0
    # active_area_size = 1.0 1.0
}

# Bind stylus buttons
bindl = , XF86TouchpadToggle, exec, toggle-tablet-mode.sh
```

#### Stylus button mapping in Hyprland

```conf
# Pen button 1 (side switch near tip)
bind = , button8, exec, hyprctl dispatch exec krita

# Pen eraser end
bind = , Stylus Eraser, exec, hyprctl dispatch exec xournalpp
```

### OpenTabletDriver — universal tablet driver

For tablets not well-supported by the kernel driver (Huion, XP-Pen, Gaomon,
some Wacom):

```bash
paru -S opentabletdriver
# Enable the service
systemctl --user enable --now opentabletdriver
```

#### OpenTabletDriver Wayland setup

OTD requires the `UClogic` or `Wacom` kernel driver to be blacklisted for
the specific device, then uses its own userspace driver:

```bash
# Find your tablet's kernel module
lsmod | grep -i "wacom\|uclogic\|hid_"

# Blacklist example for Huion tablet:
echo "blacklist hid_uclogic" | sudo tee /etc/modprobe.d/opentabletdriver.conf
sudo mkinitcpio -P

# Verify OTD sees the tablet:
otd-gui   # GUI configuration tool
```

OTD output mode: set to **Absolute** mode for Wayland native operation.

#### Area mapping and sensitivity

In the OTD GUI or config file (`~/.config/OpenTabletDriver/`):
- **Input area**: subset of the tablet surface to use
- **Output area**: map to specific monitor coordinates
- **Tip pressure curve**: adjust pen pressure response
- **Scroll speed**: for scroll wheel on pen

---

## 90.4 On-Screen Keyboards

### squeekboard (GNOME/GTK, phone-oriented)

```bash
paru -S squeekboard
```

squeekboard uses `zwp_input_method_v2` and `zwp_text_input_v3`. It is the
keyboard used on Phosh (GNOME mobile) and works on desktop Wayland sessions
when those protocols are supported.

**Hyprland/wlroots support:** limited — `zwp_input_method_v2` is not
implemented in wlroots. squeekboard does not work on Hyprland/Sway as of 2025.

### wvkbd — wlroots on-screen keyboard

wvkbd uses the `virtual-keyboard-v1` protocol and works on any wlroots compositor:

```bash
paru -S wvkbd

# Show keyboard
wvkbd-mobintl &   # mobile/international layout
wvkbd-desk &      # desktop layout

# Toggle visibility
pkill -USR1 wvkbd-mobintl   # toggle show/hide
```

```conf
# hyprland.conf — bind keyboard toggle
bind = SUPER, k, exec, pkill -USR1 wvkbd-mobintl || wvkbd-mobintl
```

Custom keyboard layout (`~/.config/wvkbd/keyboard.csv`):
```
Q,W,E,R,T,Y,U,I,O,P
A,S,D,F,G,H,J,K,L
Z,X,C,V,B,N,M
SPACE,RETURN
```

### Layer-shell positioning for wvkbd

wvkbd draws as a layer-shell surface at the bottom of the screen.
Configure its height and width:
```bash
wvkbd-mobintl -L 200   # 200px tall
wvkbd-mobintl -w 1920  # full width
```

---

## 90.5 Tablet Mode (Laptop/Convertible)

### Detection

```bash
# Check if device is in tablet mode (hinge/orientation sensor)
cat /sys/bus/platform/drivers/intel-hid/*/events 2>/dev/null
# or:
udevadm monitor --property | grep -i "tablet\|hinge"
```

### Auto-switch script for Hyprland

```bash
#!/bin/bash
# /etc/udev/rules.d/90-tablet-mode.rules trigger:
# ACTION=="change", SUBSYSTEM=="platform", KERNEL=="INT33D3:00", \
#   RUN+="/usr/local/bin/tablet-mode.sh"

TABLET_MODE=$(cat /sys/bus/platform/devices/*/tablet_mode 2>/dev/null)

if [ "$TABLET_MODE" = "1" ]; then
    # Tablet mode — show OSK, disable touchpad, enable touch
    hyprctl keyword input:touchpad:enabled false
    wvkbd-mobintl &
    # Optionally rotate display
    hyprctl keyword monitor "eDP-1,preferred,auto,1,transform,1"
else
    # Laptop mode — hide OSK, enable touchpad
    pkill wvkbd-mobintl
    hyprctl keyword input:touchpad:enabled true
    hyprctl keyword monitor "eDP-1,preferred,auto,1,transform,0"
fi
```

### iio-sensor-proxy for auto-rotate

```bash
sudo pacman -S iio-sensor-proxy
sudo systemctl enable --now iio-sensor-proxy

# Monitor orientation changes:
monitor-sensor   # shows current orientation
```

Use with a script to rotate the compositor output when the device is flipped:

```bash
#!/bin/bash
# Watch for orientation changes
monitor-sensor | while read -r line; do
  case "$line" in
    *"normal"*)      hyprctl keyword monitor "eDP-1,preferred,auto,1,transform,0" ;;
    *"bottom-up"*)   hyprctl keyword monitor "eDP-1,preferred,auto,1,transform,2" ;;
    *"right-up"*)    hyprctl keyword monitor "eDP-1,preferred,auto,1,transform,3" ;;
    *"left-up"*)     hyprctl keyword monitor "eDP-1,preferred,auto,1,transform,1" ;;
  esac
done
```

---

## 90.6 Touch Input Debugging

```bash
# Show raw input events (including touch)
wev   # Wayland event viewer — shows all input events in a test window

# libinput debug
sudo libinput debug-events | grep -i touch

# Check which devices libinput sees
sudo libinput list-devices

# Test stylus axes (pressure, tilt)
wev   # create a window, move stylus over it, watch pressure/tilt events
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
