# Chapter 13 — The Full Zoo: dwl, Jay, cosmic-comp, KWin, GNOME Mutter, gamescope

## Overview
Beyond the "big four" ricing compositors, the Wayland ecosystem has many specialized
and DE-integrated compositors worth knowing about.

## Sections

### 13.1 dwl — dwm for Wayland
- Minimal wlroots compositor in <2000 lines of C
- Patch-based customization (identical to dwm philosophy)
- Tag-based window management
- Who should use it: C hackers who want full ownership

### 13.2 Jay — Wayland in Rust
- Built on Smithay
- Focuses on correctness and modern Rust idioms
- Status and feature completeness (2025)

### 13.3 cosmic-comp — The COSMIC Desktop Compositor
- System76's Rust/Smithay-based compositor
- Tiling + stacking hybrid with COSMIC's unique layout system
- Integration with the full COSMIC DE
- Status: stable release timeline

### 13.4 KWin on Wayland
- KDE Plasma's compositor: the most feature-complete Wayland compositor
- KWin scripts: JavaScript/QML extensions
- KDE-specific protocols and integrations
- KWin vs. wlroots-based: stability, HDR, color management
- When to use KWin: DE completeness, HDR, accessibility

### 13.5 GNOME Mutter/Shell
- Mutter as both compositor and window manager
- GNOME Shell extensions: the GNOME ricing approach
- Wayland-specific GNOME extensions landscape (2025)
- Limitations for heavy ricing vs. vanilla ricing

### 13.6 gamescope — The Gaming Compositor
- Valve's embedded compositor for SteamOS
- Micro-compositor that wraps games
- VRR support, latency optimization, HDR pipeline
- Using gamescope on the desktop: `gamescope -e -- steam`
- Integration with Mangohud

### 13.7 cage — Kiosk Compositor
- Single-window kiosk mode
- Use cases: media centers, embedded displays, ATMs

### 13.8 weston — The Reference Compositor
- Maintained by freedesktop.org
- Primary use: protocol development and testing
- weston shell, kiosk shell, fullscreen shell
- Not for daily use: why

### 13.9 Emerging Compositors (2025/2026)
- waywall: container-based compositor
- Smithay-based projects: landscape overview
- Potential future compositors from the Rust ecosystem
