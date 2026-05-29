# Chapter 33 — Display Configuration: kanshi, wdisplays, wlr-randr, shikane

## Overview
Multi-monitor configuration on Wayland uses the `wlr-output-management` protocol.
Tools like kanshi enable profile-based automatic configuration.

## Sections

### 33.1 wlr-output-management Protocol
- `zwlr_output_manager_v1`: enumerate and configure outputs
- Apply/test transaction model
- Properties: mode, position, scale, transform, adaptive sync

### 33.2 kanshi — Profile-Based Auto-Configuration
```
# ~/.config/kanshi/config
profile home {
    output DP-1 position 0,0 resolution 2560x1440@144Hz scale 1
    output HDMI-A-1 position 2560,0 resolution 1920x1080@60Hz scale 1
}

profile laptop {
    output eDP-1 position 0,0 resolution 1920x1080@60Hz scale 1.5
}
```
- Profiles matched by connected output combinations
- `kanshi` daemon: automatically applies matching profile
- `kanshictl reload`: reload config
- `kanshictl switch-profile profilename`: force a profile
- Wildcard matching for flexible profiles

### 33.3 wdisplays — GUI Configuration
- GTK-based display arrangement GUI
- Drag-and-drop monitor positioning
- Resolution and refresh rate selection
- Scale and rotation
- Writes a kanshi-compatible config or applies immediately

### 33.4 wlr-randr — xrandr for Wayland
```bash
wlr-randr --output DP-1 --mode 2560x1440@144Hz --pos 0,0 --scale 1
wlr-randr --output HDMI-A-1 --off
```
- `wlr-randr`: list connected outputs
- One-shot configuration (not persistent)
- Useful for scripting and troubleshooting

### 33.5 shikane — Advanced Profile Manager
- More powerful than kanshi: regex matching, exact output ordering
- `shikanectl`: reload and profile switching
- JSON-based config

### 33.6 Fractional Scaling
- `wp-fractional-scale-v1` protocol
- Compositor-side: `scale 1.5` in kanshi/hyprland.conf
- Application-side rendering at fractional scales
- `XCURSOR_SIZE` and cursor scaling
- Known issues: blurry apps, GTK/Qt scaling environment variables

### 33.7 Rotation and Transform
- Transform values: `normal`, `90`, `180`, `270`, `flipped`, `flipped-90`, etc.
- Portrait mode monitors
- Touchscreen coordinate mapping with rotation

### 33.8 Variable Refresh Rate (VRR/Adaptive Sync)
- `vrr = 1` in hyprland.conf
- `adaptive_sync = enabled` in kanshi
- Compositor support matrix (2025)
- Gaming benefit: reduced tearing without vsync latency

### 33.9 HDR Status (2025/2026)
- KWin: HDR stable and production-ready
- Hyprland: HDR in development/experimental
- Niri: not yet supported
- Sway: not planned
- Color management protocols: `wp-color-management-v1`
