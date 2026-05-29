# Chapter 41 — Multi-Monitor, HiDPI, and Fractional Scaling

## Overview
Multi-monitor setups on Wayland are more capable than X11 (per-output scaling,
independent refresh rates) but require careful configuration to avoid blurry apps.

## Sections

### 41.1 Wayland's Per-Output Model
- Each output is an independent Wayland object
- Per-output: resolution, refresh rate, position, scale, transform
- No more Xrandr global scale hack
- XWayland: single shared scale (the weakest link)

### 41.2 Integer Scaling (1x, 2x, 3x)
- `scale = 2` for 4K monitors: pixel-perfect, no blurring
- All apps render at 2x, compositor downsamples
- Recommended for: 4K at 27", 5K at 27", Retina displays
- Config in Hyprland: `monitor = DP-1,3840x2160@60,0x0,2`

### 41.3 Fractional Scaling
- `scale = 1.5` for 1440p at 24": not pixel-perfect
- Two approaches:
  1. **Compositor-side**: render at 1x, compositor scales (blurry)
  2. **Protocol-side** (`wp-fractional-scale-v1`): apps render at correct fraction
- Hyprland: `monitor = DP-1,2560x1440@144,0x0,1.5`
- Applications need to support `wp-fractional-scale-v1` for sharp rendering
- GTK4 and Qt6: support fractional scale natively
- GTK3: uses environment variable `GDK_SCALE=2` (integers only)

### 41.4 XWayland Fractional Scaling
- XWayland uses a single scale (typically floor of smallest output)
- `XWAYLAND_SCALE_FACTOR` workaround
- Hyprland `xwaylandproperty scale` setting
- `xrdb -merge` for X11 DPI settings
- Known limitation: XWayland apps always look slightly off on fractional displays

### 41.5 Mixed DPI Multi-Monitor Setup
- Different scale per monitor in Hyprland/Sway
- Cursor size consistency: `XCURSOR_SIZE` must match expected size
- Moving windows between monitors: app re-renders at new scale
- Known issues with older Qt apps

### 41.6 Refresh Rate Management
- VRR (Adaptive Sync): `vrr = 1` in Hyprland
- Different refresh rates per monitor: Wayland handles natively
- Frame pacing across monitors: compositor-dependent

### 41.7 Monitor Arrangement
- Logical vs. physical position: `monitor = DP-1,1920x1080,0x0,1`
- The coordinate system: top-left origin, x increases right, y increases down
- Portrait monitors: `transform,1` (90°) or `transform,3` (270°)
- Hotplug: kanshi for automatic profile switching (Ch 33)

### 41.8 Waybar / Quickshell Multi-Monitor
- One bar instance per output via `Variants { model: Quickshell.screens }`
- Each bar knows its screen's properties
- Workspace filtering: show only workspaces for this monitor
- Consistent bar height across different scale factors

### 41.9 Screen Layout in Practice
```
# Hyprland multi-monitor config example
monitor = DP-1,2560x1440@165,0x0,1         # left: 1440p 165Hz
monitor = DP-2,3840x2160@60,2560x0,2       # right: 4K scaled to 1080p equivalent
monitor = eDP-1,1920x1200@60,0x1440,1.5    # laptop below, 1.5x scale
```
