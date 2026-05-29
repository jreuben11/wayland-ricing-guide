# Chapter 48 — Building a Compositor in Rust with Smithay

## Overview
Smithay is a Rust library for Wayland compositors, used by cosmic-comp, niri, and
Jay. This chapter builds the same minimal compositor as Chapter 47, but in Rust.

## Sections

### 48.1 Why Smithay vs. wlroots (in Rust)
- wlroots-rs: unsafe Rust bindings to C library (less popular)
- Smithay: pure Rust, safe abstractions, growing ecosystem
- Smithay users: niri, Jay, cosmic-comp, winit
- API stability: `smithay` crate on crates.io

### 48.2 Project Setup
```toml
# Cargo.toml
[dependencies]
smithay = { version = "0.3", features = ["desktop", "wayland_frontend", "backend_drm", "backend_libinput", "renderer_gl"] }
calloop = "0.13"
wayland-server = "0.31"
```

### 48.3 The Calloop Event Loop
- Smithay uses `calloop` for event dispatch
- `EventLoop::try_new()`, `LoopHandle`, `LoopSignal`
- Inserting event sources: signals, wayland display, libinput
- The main loop: `event_loop.run(timeout, &mut state, None)`

### 48.4 State Management in Smithay
```rust
struct MyCompositor {
    display: Display<Self>,
    space: Space<WindowElement>,
    seat: Seat<Self>,
    pointer: PointerHandle<Self>,
    keyboard: KeyboardHandle<Self>,
    // delegated handlers
    compositor_state: CompositorState,
    xdg_shell_state: XdgShellState,
    shm_state: ShmState,
    output_manager_state: OutputManagerState,
    seat_state: SeatState<Self>,
    // ...
}
```

### 48.5 Delegate Macros
```rust
// Smithay uses delegate! macros for protocol dispatch
delegate_compositor!(MyCompositor);
delegate_xdg_shell!(MyCompositor);
delegate_shm!(MyCompositor);
delegate_seat!(MyCompositor);
delegate_output!(MyCompositor);
```

### 48.6 XDG Shell Handler
```rust
impl XdgShellHandler for MyCompositor {
    fn xdg_shell_state(&mut self) -> &mut XdgShellState {
        &mut self.xdg_shell_state
    }
    fn new_toplevel(&mut self, surface: ToplevelSurface) {
        let window = Window::new_wayland_window(surface);
        self.space.map_element(window, (0, 0), false);
    }
    fn toplevel_destroyed(&mut self, surface: ToplevelSurface) {
        // remove from space
    }
}
```

### 48.7 Backend: DRM/libinput
- `LibinputInputBackend`: wraps libinput for input events
- `DrmBackend` + `GbmAllocator`: KMS rendering
- `UdevBackend`: scan for DRM devices, handle hotplug
- Nested backend: `WaylandBackend` for testing inside another compositor

### 48.8 Rendering with Smithay
- `GlesRenderer`: OpenGL ES renderer
- `damage_tracked_renderer`: efficient partial updates
- `draw_render_elements!` macro: render windows, cursors
- Custom render elements for special effects

### 48.9 Desktop Utilities
```rust
use smithay::desktop::{Space, Window, layer_map_for_output};

// Space: manages window positioning
let space = Space::<Window>::default();
space.map_element(window, location, activate);

// Layer map: layer shell surfaces per output
let layer_map = layer_map_for_output(&output);
```

### 48.10 Study Resources
- Smithay book: https://smithay.github.io/smithay/
- Smithay examples: `examples/` in the crate
- niri source: https://github.com/YaLTeR/niri (real-world Smithay compositor)
- cosmic-comp source: https://github.com/pop-os/cosmic-comp
