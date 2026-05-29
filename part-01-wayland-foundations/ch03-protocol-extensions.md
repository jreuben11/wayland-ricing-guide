# Chapter 3 — Protocol Extensions: xdg-shell, layer-shell, wlr-protocols

## Overview
The core Wayland protocol is intentionally bare. Almost everything useful for a
desktop is in the extension ecosystem. This chapter surveys the essential
extensions every ricer needs to understand.

## Sections

### 3.1 The wayland-protocols Repository
- Stable, staging, and unstable protocol tiers
- `wayland-scanner` and the XML → C/C++ pipeline
- How compositors advertise extension support via the registry

### 3.2 xdg-shell — The Standard Window Protocol
- `xdg_wm_base`: the toplevel shell manager
- `xdg_surface` and `xdg_toplevel`: normal application windows
- `xdg_popup`: menus, tooltips, and context menus
- Configure/ack_configure handshake: why it matters
- Maximize, fullscreen, minimize, and decoration negotiation
- `xdg-decoration-unstable-v1`: client vs. server-side decorations (CSD vs. SSD)

### 3.3 xdg-output — Multi-Monitor Metadata
- Logical vs. physical coordinates
- Why this matters for multi-monitor setups and fractional scaling

### 3.4 wlr-layer-shell — The Ricing Protocol
- `zwlr_layer_shell_v1`: the protocol that enables bars, widgets, wallpapers
- Four layers: BACKGROUND, BOTTOM, TOP, OVERLAY
- Anchoring, margins, and exclusive zones
- Keyboard interactivity modes
- How Waybar, Quickshell, eww, and swww all use this

### 3.5 wlr-protocols Suite
- `wlr-output-management-unstable-v1`: kanshi, wdisplays
- `wlr-screencopy-unstable-v1`: grim, wf-recorder, Quickshell ScreencopyView
- `wlr-data-control-unstable-v1`: wl-clipboard, cliphist
- `wlr-foreign-toplevel-management-unstable-v1`: taskbars, window switchers
- `wlr-gamma-control-unstable-v1`: night-light tools
- `wlr-input-inhibitor-unstable-v1`: lockscreens

### 3.6 Other Important Extensions
- `wp-viewporter`: scaling and cropping surfaces
- `wp-presentation-time`: precise vsync timing feedback
- `wp-fractional-scale-v1`: proper HiDPI fractional scaling
- `wp-cursor-shape-v1`: cursor themes
- `zwp-linux-dmabuf-v1`: GPU buffer sharing (zero-copy rendering)
- `ext-session-lock-v1`: the standardized lockscreen protocol
- `xdg-activation-v1`: focus stealing prevention

### 3.7 Hyprland-Specific Protocols
- `hyprland-global-shortcuts-v1`
- `hyprland-toplevel-export-v1`
- `hyprland-ctm-control-v1` (color transform matrices)

## Resources
- https://wayland.app/protocols/ — browsable protocol explorer
- https://gitlab.freedesktop.org/wayland/wayland-protocols
- https://gitlab.freedesktop.org/wlroots/wlr-protocols
