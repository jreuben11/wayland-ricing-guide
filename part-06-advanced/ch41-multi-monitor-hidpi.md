# Chapter 41 — Multi-Monitor, HiDPI, and Fractional Scaling

## Overview

Multi-monitor setups on Wayland represent one of the protocol's genuine architectural improvements over X11. Rather than treating all connected displays as a single logical screen (the X11 model), Wayland exposes each physical output as an independent object with its own resolution, refresh rate, position, scale factor, and transform. This clean per-output model eliminates entire categories of X11 bugs — gamma ramps, per-output color management, and per-output scaling all work without global hacks.

The tradeoff is complexity: you must explicitly configure each output, and legacy XWayland applications remain a persistent source of blurriness on fractional-scale setups. This chapter gives you the complete picture: integer scaling for pixel-perfect rendering, fractional scaling with the modern `wp-fractional-scale-v1` protocol, XWayland mitigation strategies, mixed-DPI multi-monitor workflows, and compositor-level tooling for every major Wayland compositor.

All examples in this chapter use Hyprland as the primary compositor because it has the most expressive monitor configuration syntax, but equivalent configuration for Sway/i3-on-Wayland, River, and Niri is provided in sidebars. For automatic output profile switching based on which monitors are connected, see **Ch 33 (kanshi and Output Management)**. For session startup and `systemd --user` service ordering around output readiness, see **Ch 53 (Session Startup Architecture)**.

---

## 41.1 Wayland's Per-Output Model

In X11, the entire screen is a single drawable surface. `xrandr` carved that surface into virtual outputs, but from the application's perspective there was always one DISPLAY with one coordinate space. Fractional scaling required the infamous `Xft.dpi` and `GDK_SCALE` dance — integers multiplied against a global DPI, with inconsistent results across toolkits.

Wayland inverts this. The `wl_output` interface exposes each physical connector as a first-class protocol object. Compositors advertise the output's physical dimensions, logical resolution, subpixel layout, and transformation. The `xdg-output-unstable-v1` protocol extends this with logical position and name, allowing clients to understand how outputs are arranged. When an application creates a `wl_surface` and a window system integration layer (e.g., `xdg_toplevel`) assigns it to an output, the compositor can tell the app exactly what scale factor to render at.

The key data per output is:

| Property       | Protocol Field        | Example Value           |
|----------------|-----------------------|-------------------------|
| Physical size  | `wl_output.geometry`  | 527mm × 296mm           |
| Pixel mode     | `wl_output.mode`      | 3840×2160 @ 60Hz        |
| Scale factor   | `wl_output.scale`     | 2 (integer only here)   |
| Transform      | `wl_output.transform` | `normal`, `90`, `180`   |
| Logical pos    | `xdg_output.logical_position` | 0, 0            |
| Logical size   | `xdg_output.logical_size`     | 1920×1080       |

The `wl_output.scale` field in the base protocol is integer-only. Fractional scaling requires the `wp-fractional-scale-v1` extension protocol, described in section 41.3.

XWayland sits outside this clean model. It presents all outputs as a single X11 screen, picks one DPI for the whole thing, and applications never see Wayland output events. This is the root cause of XWayland blurriness on multi-monitor fractional setups and is discussed at length in section 41.4.

To inspect your current output state from within a Wayland session:

```bash
# Wayland-native output inspection
wlr-randr                        # wlroots-based compositors (Hyprland, Sway, River)
hyprctl monitors                 # Hyprland-specific, JSON-friendly
swaymsg -t get_outputs           # Sway
niri msg outputs                 # Niri

# More detail with xdg-output info
wayland-info | grep -A 20 'wl_output'
```

Sample `hyprctl monitors` output for a dual-monitor setup:

```json
[
  {
    "id": 0,
    "name": "DP-1",
    "description": "Dell U2722D 27\" @ 2560x1440",
    "width": 2560,
    "height": 1440,
    "refreshRate": 165.0,
    "x": 0,
    "y": 0,
    "scale": 1.5,
    "transform": 0,
    "focused": true,
    "dpmsStatus": true
  },
  {
    "id": 1,
    "name": "DP-2",
    "description": "LG 27UK850 4K @ 3840x2160",
    "width": 3840,
    "height": 2160,
    "refreshRate": 60.0,
    "x": 1707,
    "y": 0,
    "scale": 2.0,
    "transform": 0,
    "focused": false,
    "dpmsStatus": true
  }
]
```

Note the `x: 1707` for the second monitor — that is the logical position (2560 / 1.5 = 1706.67, rounded to 1707) rather than the physical pixel offset of 2560.

---

## 41.2 Integer Scaling (1x, 2x, 3x)

Integer scaling is the gold standard: the compositor tells apps to render at an integer multiple of the base resolution, every pixel maps exactly to N×N physical pixels, and the result is perfectly sharp regardless of which toolkit the application uses. If you have a 4K display and can afford the logical resolution reduction, integer scaling is always preferable.

The common integer-scale choices and their logical resolutions:

| Physical Resolution | Scale | Logical Resolution | Best For                          |
|---------------------|-------|--------------------|-----------------------------------|
| 3840×2160 (4K)      | 2     | 1920×1080          | 27" 4K, 32" 4K                    |
| 3840×2160 (4K)      | 1     | 3840×2160          | 43"+ 4K, very dense UI preference |
| 2560×1600 (16:10)   | 2     | 1280×800           | 13" laptop Retina panels          |
| 5120×2880 (5K)      | 2     | 2560×1440          | 27" 5K iMac-style panels          |
| 1920×1080 (FHD)     | 1     | 1920×1080          | 24" 1080p, 27" 1080p              |

In Hyprland, integer scaling uses the fourth field of the `monitor` directive:

```ini
# ~/.config/hypr/monitors.conf

# 4K 27" at 2x scale — logical 1920×1080 equivalent
monitor = DP-1,3840x2160@60,0x0,2

# 4K 32" at 1x — full 4K logical space (for dense layouts)
monitor = DP-2,3840x2160@60,1920x0,1

# Laptop panel at 1x (1080p, 14" — comfortable without scaling)
monitor = eDP-1,1920x1080@60,0x1080,1
```

In Sway, the syntax is different but the semantics are identical:

```
# ~/.config/sway/outputs
output DP-1 {
    resolution 3840x2160
    position 0 0
    scale 2
    refresh_rate 60
}

output eDP-1 {
    resolution 1920x1080
    position 1920 1080
    scale 1
}
```

For River, use `wlr-randr` at startup or in the `init` script:

```bash
# ~/.config/river/init  (excerpt)
wlr-randr --output DP-1 --mode 3840x2160@60Hz --scale 2 --pos 0,0
wlr-randr --output eDP-1 --mode 1920x1080@60Hz --scale 1 --pos 1920,1080
```

After changing scale, you must restart or reload the bar (Waybar, eww, etc.) because bar instances cache their geometry at startup. Waybar typically handles this automatically via `wl_output` events if compiled with `--enable-sway` or run under a wlroots compositor.

---

## 41.3 Fractional Scaling

When your display's native resolution and physical size don't cleanly align with a 2x scale — the most common case being a 1440p (2560×1440) monitor at 24"–27" — fractional scaling fills the gap. A scale of 1.5 gives you a logical resolution of 1706×960, which has more screen real estate than 1080p while still being comfortably readable.

There are two fundamentally different approaches to fractional scaling on Wayland:

**Compositor-side scaling (legacy approach):** The compositor renders the entire scene at 1x and then upscales the result to fill the display. This is fast and universally compatible, but the upscaling introduces bilinear blur. Text especially suffers: subpixel rendering is destroyed by the scale step. This is what happens when you set `scale = 1.5` on an older compositor without `wp-fractional-scale-v1` support.

**Protocol-side fractional scaling (`wp-fractional-scale-v1`):** Introduced in 2022 and merged into wayland-protocols, this protocol sends each surface its exact fractional scale factor. The application renders at the higher resolution and the compositor composites the pre-scaled result. Text is sharp because the app performed the scaling during rasterization with full knowledge of the target pixels. GTK4 (4.4+) and Qt6 (6.3+) support this protocol natively. The protocol is defined in `staging/fractional-scale/fractional-scale-v1.xml`.

Hyprland enables `wp-fractional-scale-v1` automatically when you set a fractional scale:

```ini
# ~/.config/hypr/monitors.conf

# 1440p at 165Hz, 1.5x scale — logical 1706×960
monitor = DP-1,2560x1440@165,0x0,1.5

# 1440p at 144Hz, 1.25x scale — logical 2048×1152
monitor = DP-2,2560x1440@144,2560x0,1.25

# 4K laptop panel at 1.75x scale — logical 2194×1234
monitor = eDP-1,3840x2160@120,0x960,1.75
```

To verify fractional scale protocol support from within a running session:

```bash
# Check advertised protocols — look for wp_fractional_scale_manager_v1
wayland-info | grep fractional

# Using weston-info if available
weston-info 2>/dev/null | grep -i fraction

# Programmatic check (useful in scripts)
python3 -c "
import subprocess, re
out = subprocess.check_output(['wayland-info'], text=True)
print('fractional scale v1:', 'wp_fractional_scale_manager_v1' in out)
"
```

Toolkit-specific fractional scaling behavior and configuration:

```bash
# GTK4: uses wp-fractional-scale-v1 automatically when available
# Force a specific scale for testing (overrides protocol):
GDK_SCALE=2 some-gtk4-app

# GTK3: no fractional support, integers only
GDK_SCALE=2 some-gtk3-app         # integer upscale, sharp
GDK_DPI_SCALE=1.5 some-gtk3-app  # DPI hint only, fonts scale but UI may not

# Qt6: reads Wayland fractional scale natively (Qt6.3+)
# Force for testing:
QT_SCALE_FACTOR=1.5 some-qt6-app

# Qt5: set scale factor explicitly
QT_SCALE_FACTOR=1.5 QT_AUTO_SCREEN_SCALE_FACTOR=0 some-qt5-app

# Electron (Chromium-based): pass --force-device-scale-factor
code --force-device-scale-factor=1.5
# Or set permanently in ~/.config/code-flags.conf:
# --force-device-scale-factor=1.5
```

For Electron apps that use the `ELECTRON_OZONE_PLATFORM_HINT` variable:

```bash
# ~/.config/environment.d/wayland.conf
ELECTRON_OZONE_PLATFORM_HINT=auto
# This tells Electron to detect Wayland and use native scaling
```

---

## 41.4 XWayland Fractional Scaling

XWayland is a compatibility shim that runs an X11 server inside your Wayland session, translating X11 protocol requests into Wayland surface operations. It is invaluable for legacy apps (Steam, WINE, some IDEs) but architecturally incompatible with per-output scaling: X11 has a single DPI for the entire display, and XWayland must pick one value.

By default, Hyprland and Sway set XWayland's DPI to 96 (scale 1) or to `floor(min_scale) * 96` across all connected outputs. On a mixed 1x/2x setup, this means your XWayland apps will use 1x DPI and appear tiny on the 4K monitor, or you scale XWayland up and it looks blurry on the 1080p monitor.

Hyprland offers the most complete XWayland scaling mitigation:

```ini
# ~/.config/hypr/hyprland.conf

# Force XWayland to present itself at a higher DPI
# This makes X11 apps draw at 2x and then Hyprland downsamples them
xwayland {
    force_zero_scaling = true
}

# Set XWayland scale — apps render crisply at 2x
# Then place on a monitor with scale=2 for 1:1 pixel mapping
exec-once = xprop -root -f _XWAYLAND_GLOBAL_OUTPUT_SCALE 32c -set _XWAYLAND_GLOBAL_OUTPUT_SCALE 2
```

The `force_zero_scaling = true` option tells Hyprland to advertise scale 1 to XWayland applications, preventing the compositor from double-scaling. Combined with setting the `_XWAYLAND_GLOBAL_OUTPUT_SCALE` root property, X11 apps draw at the right size.

For Sway, the approach uses environment variables and `xrdb`:

```bash
# ~/.config/sway/config  (exec section)

# Set X resource DPI for XWayland apps
exec_always xrdb -merge <<EOF
Xft.dpi: 192
Xft.antialias: true
Xft.hinting: true
Xft.hintstyle: hintfull
Xft.rgba: rgb
EOF

# Tell GTK2/GTK3 X11 apps about scaling
exec_always gsettings set org.gnome.desktop.interface scaling-factor 2
exec_always gsettings set org.gnome.desktop.interface text-scaling-factor 1.0
```

The `XWAYLAND_SCALE_FACTOR` environment variable (supported since XWayland 22.1) is a cleaner solution when available:

```bash
# ~/.config/environment.d/xwayland.conf
# Note: this is read by systemd --user, not by all compositors directly

# Tell XWayland to scale by 2x globally
# (requires XWayland >= 22.1)
XWAYLAND_SCALE_FACTOR=2
```

Reality check table for XWayland scaling approaches:

| Approach                         | Sharpness | App Compat | Notes                                  |
|----------------------------------|-----------|------------|----------------------------------------|
| Default (no config)              | Blurry    | 100%       | Small on HiDPI                         |
| `force_zero_scaling` + root prop | Sharp     | ~95%       | Best for Hyprland 4K setups            |
| `Xft.dpi: 192` via xrdb          | Partially | 90%        | Font size correct, UI elements may not |
| `XWAYLAND_SCALE_FACTOR=2`        | Sharp     | ~98%       | Cleanest, requires XWayland >= 22.1    |
| Run apps natively on Wayland     | Perfect   | N/A        | Best long-term solution                |

Check your XWayland version:

```bash
Xwayland -version
# Xwayland 23.2.1 → supports XWAYLAND_SCALE_FACTOR
# Xwayland 21.x  → use root property workaround
```

To force individual legacy apps to run natively on Wayland instead of through XWayland:

```bash
# GTK apps
GDK_BACKEND=wayland gimp

# Qt apps
QT_QPA_PLATFORM=wayland kdenlive

# Firefox (Wayland native since Firefox 81)
MOZ_ENABLE_WAYLAND=1 firefox

# Check if a process is on Wayland or XWayland
# (look for WAYLAND_DISPLAY vs DISPLAY in /proc/PID/environ)
cat /proc/$(pgrep -f firefox | head -1)/environ | tr '\0' '\n' | grep -E 'WAYLAND|DISPLAY'
```

---

## 41.5 Mixed DPI Multi-Monitor Setup

The most challenging configuration is a laptop with a HiDPI panel connected to a 1080p external monitor. The laptop panel wants scale 2 (or 1.5); the external monitor wants scale 1. Applications that span both monitors or move between them must re-render at a different scale, and the cursor must look consistent regardless of which output it sits on.

A complete mixed-DPI Hyprland configuration:

```ini
# ~/.config/hypr/monitors.conf

# External 1080p monitor (left, main workspace)
monitor = HDMI-A-1,1920x1080@60,0x0,1

# Laptop HiDPI panel (right, scale 2x, positioned at logical x=1920)
monitor = eDP-1,2560x1600@120,1920x0,2

# Cursor size must be chosen carefully:
# At scale 1: XCURSOR_SIZE=24 shows 24px cursor
# At scale 2: XCURSOR_SIZE=24 shows 24px cursor (compositor doubles it)
# Use a single value; compositor handles per-output rendering

env = XCURSOR_SIZE,24
env = XCURSOR_THEME,Bibata-Modern-Classic
```

For Sway with mixed DPI:

```
# ~/.config/sway/config

output HDMI-A-1 {
    resolution 1920x1080
    position 0 0
    scale 1
    background ~/wallpapers/dark.png fill
}

output eDP-1 {
    resolution 2560x1600
    position 1920 0
    scale 2
    background ~/wallpapers/dark.png fill
}

# Cursor theme consistent across outputs
seat seat0 xcursor_theme Bibata-Modern-Classic 24
```

When a window moves from the 1x external monitor to the 2x laptop panel, properly implemented Wayland clients will receive a `wl_surface.preferred_buffer_scale` event (or `wp_fractional_scale_v1.preferred_scale`) and re-render at the new scale. You can observe this with GTK4 apps — they re-rasterize text as you drag the window across the boundary. Qt6 does the same. Electron apps may lag by one frame.

Cursor consistency is a known pain point. The seat cursor is rendered by the compositor and correctly scaled per-output, but the hotspot coordinates must still match. If using a cursor theme that provides multiple sizes (24, 32, 48), set `XCURSOR_SIZE` to the value matching your lowest-DPI monitor:

```bash
# For a 1x external + 2x laptop setup:
# At XCURSOR_SIZE=24, the 1x monitor shows 24px cursor
# The compositor renders 48px on the 2x monitor (24 * 2)
# This is the intended behavior — set for the lowest scale

export XCURSOR_SIZE=24
export XCURSOR_THEME=Bibata-Modern-Classic

# Verify cursor theme is found at the right path:
find /usr/share/icons/$XCURSOR_THEME /home/$USER/.local/share/icons/$XCURSOR_THEME \
    -name "cursors" -type d 2>/dev/null
```

For Qt5 applications that do not honor Wayland scale events correctly, force per-app scale with a wrapper:

```bash
#!/usr/bin/env bash
# ~/bin/qt5-hidpi-wrapper
# Usage: qt5-hidpi-wrapper <app> [args...]
export QT_SCALE_FACTOR=1.5
export QT_AUTO_SCREEN_SCALE_FACTOR=0
export QT_SCREEN_SCALE_FACTORS="eDP-1=2;HDMI-A-1=1"
exec "$@"
```

---

## 41.6 Refresh Rate Management

Wayland's per-output model handles heterogeneous refresh rates natively — one monitor can run at 165Hz while another runs at 60Hz with no global framerate cap. The compositor renders each output on its own timeline. This is a fundamental improvement over X11 where mixed refresh rates often caused tearing or forced the high-refresh monitor to sync down.

Variable Refresh Rate (VRR / Adaptive Sync) is exposed through the `wp-presentation-feedback` protocol and compositor-specific APIs:

```ini
# ~/.config/hypr/hyprland.conf

# Global VRR setting
misc {
    vrr = 1           # 0 = off, 1 = on for all, 2 = fullscreen only (default 0)
    no_direct_scanout = false   # allow direct scanout when possible (better latency)
}

# Per-monitor VRR (Hyprland 0.36+)
monitor = DP-1,2560x1440@165,0x0,1,vrr,1    # VRR on DP-1 only
monitor = DP-2,3840x2160@60,2560x0,2,vrr,0  # VRR off on DP-2
```

For Sway, VRR support depends on the kernel and GPU driver:

```
# ~/.config/sway/config
output DP-1 adaptive_sync on
output DP-2 adaptive_sync off
```

Check VRR support for connected outputs:

```bash
# Check kernel-level VRR support per connector
for conn in /sys/class/drm/card*-DP-*/vrr_capable; do
    echo "$conn: $(cat $conn 2>/dev/null || echo 'not found')"
done

# AMD FreeSync / NVIDIA G-Sync compatible check
cat /sys/class/drm/card1-DP-1/vrr_capable

# Hyprland: verify VRR is active
hyprctl monitors | grep -i vrr
```

Refresh rate can be changed at runtime without restarting the compositor:

```bash
# Hyprland: switch DP-1 to 60Hz temporarily (e.g., screencasting)
hyprctl keyword monitor DP-1,2560x1440@60,0x0,1.5

# Restore high refresh
hyprctl keyword monitor DP-1,2560x1440@165,0x0,1.5

# Sway: change refresh at runtime
swaymsg output DP-1 mode 2560x1440@60Hz

# wlr-randr: compositor-agnostic for wlroots compositors
wlr-randr --output DP-1 --mode 2560x1440@60Hz
```

Frame pacing — the consistency of frame delivery intervals — can degrade with mismatched refresh rates on multi-monitor setups. Hyprland uses per-output render loops, so a 165Hz and 60Hz monitor render independently. The 165Hz monitor is not throttled to 60Hz. However, some games and applications that target a specific frame budget may behave unexpectedly; use `gamescope` as a nested compositor for those (see **Ch 42 — Gaming on Wayland**).

---

## 41.7 Monitor Arrangement and Transforms

The logical coordinate system in Wayland uses a top-left origin, with X increasing right and Y increasing down. When you place monitors at specific positions, you specify the top-left corner of each monitor's logical bounding box. The logical dimensions are physical pixels divided by scale factor.

Example geometry calculation for a 3-monitor horizontal arrangement:

```
Monitor 1: DP-1, 2560×1440 @ scale 1.5 → logical 1707×960
Monitor 2: DP-2, 3840×2160 @ scale 2   → logical 1920×1080
Monitor 3: eDP-1, 2560×1600 @ scale 2  → logical 1280×800

Arrangement (side by side):
  DP-1: x=0,     y=0
  DP-2: x=1707,  y=0
  eDP-1: x=3627, y=0
```

Hyprland configuration for this arrangement:

```ini
monitor = DP-1,2560x1440@165,0x0,1.5
monitor = DP-2,3840x2160@60,1707x0,2
monitor = eDP-1,2560x1600@120,3627x0,2
```

Portrait mode monitors (vertical orientation) require transforms. Hyprland uses numeric transform values matching the `wl_output_transform` enum:

| Transform | Value | Description         |
|-----------|-------|---------------------|
| normal    | 0     | No rotation         |
| 90°       | 1     | Rotated 90° CW      |
| 180°      | 2     | Rotated 180°        |
| 270°      | 3     | Rotated 270° CW     |
| flipped   | 4     | Horizontally flipped|
| flipped+90| 5     | Flipped + 90° CW    |

```ini
# Portrait monitor: 1080×1920 logical (from 1920×1080 rotated 90°)
monitor = DP-3,1920x1080@60,3627x0,1,transform,1

# The logical size becomes 1080×1920 after transform
# Position subsequent monitors at x = 3627 + 1080 = 4707
monitor = DP-4,1920x1080@60,4707x0,1
```

For Sway:

```
output DP-3 {
    resolution 1920x1080
    position 3627 0
    transform 90
    scale 1
}
```

Hotplug handling — automatically applying the right configuration when monitors are connected or disconnected — is covered comprehensively in **Ch 33 (kanshi)**. The brief summary: kanshi watches `wl_output` events and applies named profiles. A minimal `~/.config/kanshi/config`:

```
profile laptop_only {
    output eDP-1 enable mode 2560x1600@120 scale 2 position 0,0
}

profile docked {
    output DP-1 enable mode 2560x1440@165 scale 1.5 position 0,0
    output DP-2 enable mode 3840x2160@60 scale 2 position 1707,0
    output eDP-1 enable mode 2560x1600@120 scale 2 position 3627,0
}

profile presentation {
    output HDMI-A-1 enable mode 1920x1080@60 scale 1 position 0,0
    output eDP-1 enable mode 2560x1600@120 scale 2 position 1920,0
}
```

---

## 41.8 Waybar / Quickshell Multi-Monitor

Status bars on multi-monitor Wayland setups need to appear on each output independently. Both Waybar and Quickshell/eww support this via compositor output events, but configuration differs.

Waybar spawns one instance per output when configured with `"output"` arrays or uses the `"all"` keyword. A minimal multi-monitor Waybar config:

```json
// ~/.config/waybar/config
[
  {
    "output": "DP-1",
    "layer": "top",
    "position": "top",
    "height": 32,
    "modules-left": ["hyprland/workspaces"],
    "modules-center": ["clock"],
    "modules-right": ["network", "pulseaudio", "battery"],
    "hyprland/workspaces": {
      "format": "{name}",
      "on-scroll-up": "hyprctl dispatch workspace e-1",
      "on-scroll-down": "hyprctl dispatch workspace e+1",
      "persistent-workspaces": {
        "DP-1": [1, 2, 3, 4, 5]
      }
    }
  },
  {
    "output": "DP-2",
    "layer": "top",
    "position": "top",
    "height": 32,
    "modules-left": ["hyprland/workspaces"],
    "modules-center": ["clock"],
    "modules-right": ["cpu", "memory"],
    "hyprland/workspaces": {
      "format": "{name}",
      "persistent-workspaces": {
        "DP-2": [6, 7, 8, 9, 10]
      }
    }
  }
]
```

Quickshell's multi-monitor support uses `Variants` with `Quickshell.screens` to spawn one bar per screen:

```qml
// ~/.config/quickshell/bar/Bar.qml
import Quickshell
import Quickshell.Wayland

ShellRoot {
    Variants {
        model: Quickshell.screens

        PanelWindow {
            required property var modelData
            screen: modelData

            anchors {
                top: true
                left: true
                right: true
            }
            height: 32

            // Access screen properties for per-monitor logic
            Text {
                text: parent.screen.name + " — " + parent.screen.width + "×" + parent.screen.height
            }
        }
    }
}
```

The `screen.name` property (e.g., `"DP-1"`) allows conditional module loading per output:

```qml
// Show different modules based on which output this bar is on
Loader {
    active: modelData.name === "eDP-1"  // laptop panel only
    sourceComponent: BatteryModule {}
}

Loader {
    active: modelData.name !== "eDP-1"  // external monitors only
    sourceComponent: ExternalDisplayInfo {}
}
```

Bar height consistency across different scale factors is automatic when using physical pixel values — the bar is rendered at the native scale of each output. However, if you specify heights in logical pixels in your config, verify that the visual height appears consistent. For Waybar, `height` is in logical pixels; on a 2x output a `height: 32` bar will consume 64 physical pixels and look the same size as on a 1x monitor.

Eww (Elkowars Wacky Widgets) requires a separate window definition per output, typically generated via a shell script that queries `hyprctl monitors` or `wlr-randr`:

```bash
#!/usr/bin/env bash
# ~/bin/launch-eww-bars.sh
# Spawn one eww bar per connected monitor

# Kill existing bars
eww kill-server 2>/dev/null
eww daemon

# Get monitor names
hyprctl monitors -j | jq -r '.[].name' | while read -r monitor; do
    eww open "bar-$monitor" --arg "monitor=$monitor" &
done
```

---

## 41.9 Screen Layout in Practice

A complete, annotated real-world Hyprland multi-monitor configuration combining all the techniques from this chapter:

```ini
# ~/.config/hypr/monitors.conf
# 3-monitor setup: 1440p left, 4K right, laptop panel below

# Left monitor: 27" 1440p 165Hz — fractional 1.5x
monitor = DP-1,2560x1440@165,0x0,1.5

# Right monitor: 27" 4K 60Hz — integer 2x
monitor = DP-2,3840x2160@60,1707x0,2

# Laptop panel: 14" 2560x1600 120Hz — integer 2x, positioned below left monitor
monitor = eDP-1,2560x1600@120,0x960,2

# Fallback for any unknown monitors connected later
monitor = ,preferred,auto,1


# ~/.config/hypr/hyprland.conf  (relevant sections)

general {
    cursor_inactive_timeout = 5
}

misc {
    vrr = 2               # VRR only in fullscreen
    no_direct_scanout = false
    mouse_move_enables_dpms = true
}

xwayland {
    force_zero_scaling = true
}

# Per-monitor workspace assignment
workspace = 1, monitor:DP-1, persistent:true
workspace = 2, monitor:DP-1, persistent:true
workspace = 3, monitor:DP-1, persistent:true
workspace = 4, monitor:DP-1, persistent:true
workspace = 5, monitor:DP-1, persistent:true
workspace = 6, monitor:DP-2, persistent:true
workspace = 7, monitor:DP-2, persistent:true
workspace = 8, monitor:DP-2, persistent:true
workspace = 9, monitor:DP-2, persistent:true
workspace = 10, monitor:eDP-1, persistent:true
```

Environment variables to set globally for all applications in the session:

```bash
# ~/.config/environment.d/wayland-scaling.conf
# Loaded by systemd --user for all processes in the session

# Force Wayland backend for GTK4
GDK_BACKEND=wayland,x11

# Force Wayland for Qt
QT_QPA_PLATFORM=wayland;xcb
QT_WAYLAND_DISABLE_WINDOWDECORATION=1

# Firefox Wayland
MOZ_ENABLE_WAYLAND=1
MOZ_WEBRENDER=1

# Electron apps: auto-detect Wayland
ELECTRON_OZONE_PLATFORM_HINT=auto

# Cursor
XCURSOR_THEME=Bibata-Modern-Classic
XCURSOR_SIZE=24

# XWayland DPI hint (backup for apps ignoring Wayland scaling)
GDK_DPI_SCALE=1
```

---

## 41.10 Color Management and HDR (Emerging)

As of 2024–2025, the `xx-color-management-v4` and `frog-color-management-v1` protocols are stabilizing in wayland-protocols. Hyprland 0.41+ has experimental HDR support behind a flag:

```ini
# ~/.config/hypr/hyprland.conf
# Experimental — may cause issues with non-HDR apps
render {
    hdr_enabled = true
    hdr_sdr_maximum_nits = 300   # SDR content peak brightness in HDR mode
}

# Per-monitor HDR
monitor = DP-1,3840x2160@60,0x0,2,hdr,1
```

ICC profile loading for color-accurate work is handled through `colord` on Wayland; the compositor reads profiles via the color management protocol:

```bash
# Install colord
sudo apt install colord     # Debian/Ubuntu
sudo pacman -S colord        # Arch

# List devices and profiles
colormgr get-devices
colormgr get-profiles

# Assign ICC profile to an output
colormgr device-add-profile \
    "xrandr-$(hyprctl monitors -j | jq -r '.[0].name')" \
    "/path/to/monitor.icc"

# Verify assignment
colormgr device-get-default-profile \
    "xrandr-$(hyprctl monitors -j | jq -r '.[0].name')"
```

For now, ICC profile support in Wayland compositors is incomplete compared to X11's `xcalib`/`xcm` ecosystem. If you require color-accurate work, consider using `gammactl` or the compositor's built-in color correction as a stopgap.

---

## Troubleshooting

**Apps appear blurry on a fractional-scale monitor**

First, identify whether the app is running on Wayland or XWayland:

```bash
# Check if PID is using Wayland socket directly
ls -la /proc/$(pgrep -f "app-name")/fd | grep wayland

# Or check environment
cat /proc/$(pgrep -f "app-name" | head -1)/environ | tr '\0' '\n' | grep -E '^(WAYLAND_DISPLAY|DISPLAY)='
```

If it shows only `DISPLAY=:0`, the app is running through XWayland. Try forcing Wayland backend (see section 41.4). If it is already on Wayland but still blurry, the app's toolkit may not support `wp-fractional-scale-v1`. Check toolkit version:

```bash
python3 -c "import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk; print(Gtk.get_major_version(), Gtk.get_minor_version())"
# GTK 4.4+ required for fractional scale
```

**Cursor is huge or tiny on one monitor**

This is almost always a mismatch between `XCURSOR_SIZE` and the monitor's scale factor. The cursor size set in `XCURSOR_SIZE` is in logical pixels; the compositor renders it at physical pixels per the output scale. Verify:

```bash
echo "XCURSOR_SIZE=$XCURSOR_SIZE, XCURSOR_THEME=$XCURSOR_THEME"

# Test correct cursor size
XCURSOR_SIZE=24 weston-terminal 2>/dev/null || foot

# Check Hyprland sees the right cursor config
hyprctl getoption general:cursor_inactive_timeout
```

**Monitor not detected or wrong mode selected**

```bash
# List all connected outputs and their supported modes
wlr-randr                    # shows all outputs and modes
hyprctl monitors all         # includes disconnected

# Force a specific mode (useful when EDID reports wrong capabilities)
# In Hyprland, use modeline:
monitor = DP-1,2560x1440@143.97,0x0,1   # specify exact refresh

# Generate modeline with cvt
cvt 2560 1440 144
# Output: Modeline "2560x1440_144.00"  ...use the values in monitor directive
```

**Bar appears on wrong monitor or at wrong scale**

```bash
# Reload Waybar completely (picks up new output config)
pkill waybar && waybar &

# Check Waybar sees the right outputs
waybar --log-level debug 2>&1 | grep -i output

# For Quickshell, check screen list
quickshell -e 'Quickshell.screens.forEach(s => print(s.name, s.width, s.height))'
```

**VRR (adaptive sync) not activating**

```bash
# Check GPU driver supports VRR
cat /sys/class/drm/card*/vrr_capable        # 1 = supported
cat /sys/class/drm/card*/content_protection # should not be blocking

# Check kernel parameter (AMD)
cat /sys/module/amdgpu/parameters/freesync_video

# Enable FreeSync at the driver level if not already on
echo 1 | sudo tee /sys/class/drm/card1-DP-1/vrr_capable

# Hyprland debug VRR
hyprctl keyword debug:disable_scale_checks 0
```

**High CPU usage on multi-monitor setups**

Multi-monitor at different refresh rates can cause compositing overhead if the compositor renders to all outputs in a single pass. Hyprland uses per-output render loops, but verify:

```bash
# Check compositor CPU usage broken down by thread
htop -p $(pgrep Hyprland)

# Disable hardware cursor acceleration as a test (sometimes helps)
hyprctl keyword cursor:no_hardware_cursors true

# Check if direct scanout is failing (forces full composite pass)
HYPRLAND_LOG_WLR=1 Hyprland 2>&1 | grep -i scanout
```

---

*Related chapters: Ch 33 (kanshi output profiles), Ch 42 (gaming and gamescope), Ch 53 (session startup).*

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
