# Chapter 5 — wlroots: The Compositor Building Blocks

## Overview
wlroots is the modular C library that powers Sway, Hyprland (historically), river,
labwc, and dozens of other compositors. Understanding its architecture explains
how compositors are built and maintained.

## Sections

### 5.1 wlroots Philosophy
- "Unopinionated" compositor building blocks
- What wlroots provides vs. what you write yourself
- Version history and major milestones
- The relationship between wlroots and the swaywm organization

### 5.2 Architecture Overview
- Scene graph API (`wlr_scene`): the high-level rendering tree
- Backend abstraction layer
- Renderer abstraction (OpenGL ES 2, Vulkan)
- Allocator abstraction (GBM, DMA-BUF)

### 5.3 Backends
- `wlr_drm_backend`: direct KMS/DRM access (production)
- `wlr_libinput_backend`: real hardware input
- `wlr_wayland_backend`: nested compositor (development/testing)
- `wlr_x11_backend`: nested under X11
- `wlr_headless_backend`: CI, virtual compositors

### 5.4 Protocol Implementations in wlroots
- `wlr_compositor`: core surface management
- `wlr_xdg_shell`: xdg-shell implementation
- `wlr_layer_shell_v1`: layer shell for bars/widgets
- `wlr_output_layout`: multi-monitor management
- `wlr_seat`: input seat abstraction
- `wlr_screencopy_manager_v1`: screenshot protocol
- `wlr_data_device_manager`: clipboard
- `wlr_xwayland`: XWayland integration

### 55 The Scene Graph API
- `wlr_scene_node`, `wlr_scene_tree`, `wlr_scene_buffer`
- Damage tracking in the scene graph
- Output presentation and frame scheduling
- Migrating from manual rendering to scene graph

### 5.6 Input Handling in wlroots
- `wlr_cursor` and cursor images
- `wlr_keyboard` with XKB integration
- Focus management: `wlr_seat_keyboard_notify_key`
- Pointer constraints for games

### 5.7 wlroots vs. Smithay (Rust)
- When to choose the C library vs. the Rust alternative
- API stability comparison
- Ecosystem maturity

## Getting Started
- Building a minimal wlroots compositor
- The `tinywl` reference implementation (study source)
- way-cooler book: https://way-cooler.org/book/
