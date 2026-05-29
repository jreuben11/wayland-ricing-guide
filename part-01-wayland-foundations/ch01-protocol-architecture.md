# Chapter 1 — The Wayland Protocol: Architecture and Philosophy

## Overview
Why Wayland exists, what problems it solves over X11, and how its architecture
fundamentally differs. The "every frame is perfect" philosophy.

## Sections

### 1.1 The X11 Legacy Problem
- X11's network-transparent design and why that became a liability
- The display server vs. compositor split in X11 (Xorg + Mutter/KWin)
- Security implications of the shared X11 model (keyloggers, screenshot leaks)
- Performance bottlenecks: tearing, latency, protocol round-trips

### 1.2 Wayland's Design Goals
- Direct rendering model — compositor owns the screen
- Security isolation — clients cannot spy on each other
- Every frame is perfect — no tearing by design
- Simplicity: the core protocol is intentionally minimal
- Extension-based growth model

### 1.3 The Wayland Architecture
- Three-party model: clients, compositor, hardware
- Role of the compositor as display server + window manager + compositor
- The Wayland socket (`$WAYLAND_DISPLAY`, `/run/user/$UID/wayland-0`)
- How clients connect and negotiate capabilities
- Comparison with Mir and other alternatives

### 1.4 Key Actors in the Ecosystem
- `libwayland-client` and `libwayland-server`
- `wayland-scanner` — generating glue code from XML
- `xkbcommon` — keyboard handling
- `libdrm` / `Mesa` — GPU access
- `libinput` — input device abstraction
- `pixman` — software rendering fallback

### 1.5 Wayland vs. X11: Practical Differences for Users
- Application compatibility matrix
- XWayland: running X11 apps on Wayland
- Known limitations still being resolved (2025/2026 status)
- Protocol coverage: what's in core vs. extensions

## Key References
- Wayland Book: https://wayland-book.com
- freedesktop.org protocol XML: wayland.xml
- Drew DeVault's original Wayland advocacy posts
