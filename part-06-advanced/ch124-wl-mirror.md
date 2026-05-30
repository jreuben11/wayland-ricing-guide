# Chapter 124 — wl-mirror: Screen Mirroring Between Outputs

## Overview

`wl-mirror` is a Wayland client that displays the contents of one Wayland output inside a window on another output. Common uses: presenting a laptop screen on a projector without configuring a clone/mirror mode in the compositor, sharing a specific monitor's content in a video call without screen capture, or creating a preview window of a secondary display.

**Cross-references:** Ch 33 — display configuration (kanshi, wlr-randr). Ch 61 — screen sharing. Ch 119 — virtual monitors.

---

## 124.1 Installation

```bash
# Arch Linux
sudo pacman -S wl-mirror   # or AUR: wl-mirror-git

# From source
git clone https://github.com/Ferdi265/wl-mirror
cd wl-mirror && cmake -B build && cmake --build build
sudo cmake --install build
```

---

## 124.2 Basic Usage

```bash
# Mirror your primary output (DP-1) in a window
wl-mirror DP-1

# Mirror HDMI-A-1 output
wl-mirror HDMI-A-1

# List available outputs
wl-mirror --list-outputs

# Mirror with specific window size
wl-mirror --width 960 --height 540 DP-1   # half 1080p preview
```

The mirror window is a live copy of the output's content, including all windows and the cursor. It updates at the output's refresh rate.

---

## 124.3 Presentation Mode (Laptop + Projector)

The canonical use case: your laptop screen shows presenter notes, the projector shows slides. Configure the projector as a separate output in the compositor, then use wl-mirror to send one application's window to it:

```bash
# Configure outputs (compositor handles projector as separate output)
# Hyprland: the projector appears as HDMI-A-1

# Option A: Mirror the entire laptop screen to projector
wl-mirror eDP-1 --output HDMI-A-1

# Option B: Move the presentation window to HDMI-A-1
# and mirror that output back to a preview on eDP-1
wl-mirror HDMI-A-1
```

For a one-command presentation mode toggle:

```bash
#!/bin/bash
# ~/.local/bin/present-toggle
# Toggle presentation mirroring on HDMI-A-1

if pgrep -x wl-mirror > /dev/null; then
    pkill wl-mirror
    notify-send "Presentation" "Mirror stopped"
else
    wl-mirror eDP-1 &
    notify-send "Presentation" "Mirroring eDP-1 → HDMI-A-1"
fi
```

---

## 124.4 Compositor Mirror Mode vs. wl-mirror

| Approach | Pros | Cons |
|---|---|---|
| Compositor `mirror=` config | Zero overhead, OS-level | Fixed; can't turn off without reconfiguring |
| `wl-mirror` | Toggle on/off, configurable window | Slight CPU overhead (screencopy) |
| `wf-recorder` + mpv | Record + playback | High latency, not real-time |

For permanent clone mode, use the compositor's built-in mirror:
```ini
# Hyprland — permanent mirror of DP-1 on HDMI-A-1
monitor = HDMI-A-1, preferred, auto, 1, mirror, DP-1
```

For on-demand mirroring, `wl-mirror` is cleaner.

---

## 124.5 wl-mirror in a Hyprland Keybind

```ini
# Toggle presentation mirror with Super+P
bind = SUPER, P, exec, ~/.local/bin/present-toggle
```

---

## 124.6 Troubleshooting

**"No such output":** Run `wl-mirror --list-outputs` and use the exact name from the list.

**Black window:** The compositor may not expose the `zwlr_screencopy_manager_v1` or `ext_image_copy_capture_manager_v1` protocol needed by wl-mirror. Check:
```bash
wayland-info | grep -E "screencopy|image_copy"
```

**High CPU usage:** wl-mirror uses the screencopy protocol which is CPU-intensive on some GPUs. Use compositor mirror mode for sustained use.
