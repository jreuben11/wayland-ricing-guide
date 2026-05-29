# Chapter 4 — libwayland Programming: Writing Wayland Clients in C

## Overview
Hands-on guide to writing a Wayland client from scratch using libwayland-client.
Covers everything from connecting to the compositor through rendering a window.

## Sections

### 4.1 Setting Up the Build Environment
- Required packages: `wayland-devel`, `wayland-protocols`, `xkbcommon-devel`
- `pkg-config` integration
- Meson build system basics for Wayland projects
- `wayland-scanner` in the build pipeline

### 4.2 Connecting to the Compositor
- `wl_display_connect()` and `$WAYLAND_DISPLAY`
- Event queue architecture and `wl_display_dispatch()`
- `wl_display_roundtrip()` for synchronous initialization

### 4.3 The Registry Dance
- Implementing `wl_registry_listener`
- Binding `wl_compositor`, `wl_shm`, `xdg_wm_base`
- Capability-based feature detection

### 4.4 Creating a Surface and Window
- `wl_compositor_create_surface()`
- `xdg_wm_base` → `xdg_surface` → `xdg_toplevel`
- Handling configure events and acking them
- Setting window title, app-id, and min/max size

### 4.5 Shared Memory Rendering with wl_shm
- Creating a memfd/shm file
- `wl_shm_pool` and `wl_buffer` creation
- Double buffering pattern
- Frame callbacks for vsync-paced rendering

### 4.6 Input Handling
- `wl_seat`: pointer, keyboard, touch
- `wl_keyboard`: keymap (XKB), key events, modifiers
- `wl_pointer`: motion, button, scroll
- `xkbcommon` for key symbol lookup

### 4.7 Using the Layer Shell (wlr-layer-shell)
- Binding `zwlr_layer_shell_v1`
- Creating a layer surface for a bar/widget
- Setting anchor, margin, and exclusive zone
- Keyboard interactivity

### 4.8 Building a Minimal Status Bar in C
- Full worked example: clock bar using shm rendering
- Pango/Cairo for text rendering
- Integrating with `wl_output` for multi-monitor

## Code Repository
Full source code examples at: (to be filled)
