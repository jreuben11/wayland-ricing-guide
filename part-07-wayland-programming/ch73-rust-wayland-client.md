# Chapter 73 — Writing Wayland Clients in Rust: wayland-client

## Contents

- [Overview](#overview)
- [Sections](#sections)
  - [73.1 The Rust Wayland Ecosystem](#731-the-rust-wayland-ecosystem)
  - [73.2 Connecting and the Global Registry](#732-connecting-and-the-global-registry)
  - [73.3 The Dispatch Trait](#733-the-dispatch-trait)
  - [73.4 Creating a Surface and XDG Window](#734-creating-a-surface-and-xdg-window)
  - [73.5 Shared Memory Rendering](#735-shared-memory-rendering)
  - [73.6 Smithay Client Toolkit (SCTK)](#736-smithay-client-toolkit-sctk)
  - [73.7 Layer Shell in Rust](#737-layer-shell-in-rust)
  - [73.8 Real-World Rust Wayland Projects](#738-real-world-rust-wayland-projects)
  - [73.9 Async Wayland with Tokio](#739-async-wayland-with-tokio)

---


## Overview
The `wayland-client` crate provides safe Rust bindings to the Wayland client
library. This chapter builds the same minimal window from Ch 4 (C), but in
idiomatic Rust, showing why Rust is increasingly used for Wayland tooling.

---

## Installation

**Project:** https://github.com/Smithay/wayland-rs

```bash
# Arch Linux — install the Rust toolchain
sudo pacman -S rust             # rustc, cargo

# Add wayland-client as a Cargo dependency (in Cargo.toml)
# cargo add wayland-client wayland-protocols

# Nix (nixpkgs) — Rust toolchain
nix-env -iA nixpkgs.rustToolchain
# Or in a devShell: pkgs.rustToolchain / pkgs.cargo
```

---

## Sections

### 73.1 The Rust Wayland Ecosystem

```
wayland-client   → low-level: mirrors libwayland-client API
wayland-protocols → auto-generated protocol bindings (xdg-shell, etc.)
wayland-scanner  → build-time code generation from XML
smithay-client-toolkit (sctk) → high-level: handles registry, seat, etc.
```

**Cargo.toml:**
```toml
[dependencies]
wayland-client = "0.31"
wayland-protocols = { version = "0.31", features = ["client", "unstable"] }
wayland-protocols-wlr = { version = "0.2", features = ["client"] }

[build-dependencies]
wayland-scanner = "0.31"
```

### 73.2 Connecting and the Global Registry

```rust
use wayland_client::{
    Connection, Dispatch, QueueHandle,
    protocol::{wl_compositor, wl_registry, wl_shm, wl_surface},
};

struct AppData {
    compositor: Option<wl_compositor::WlCompositor>,
    shm: Option<wl_shm::WlShm>,
}

impl Dispatch<wl_registry::WlRegistry, ()> for AppData {
    fn event(
        state: &mut Self,
        registry: &wl_registry::WlRegistry,
        event: wl_registry::Event,
        _: &(),
        _: &Connection,
        qh: &QueueHandle<Self>,
    ) {
        if let wl_registry::Event::Global { name, interface, version } = event {
            match interface.as_str() {
                "wl_compositor" => {
                    state.compositor = Some(registry.bind(name, version, qh, ()));
                }
                "wl_shm" => {
                    state.shm = Some(registry.bind(name, version, qh, ()));
                }
                _ => {}
            }
        }
    }
}

fn main() {
    let conn = Connection::connect_to_env().unwrap();
    let mut event_queue = conn.new_event_queue();
    let qh = event_queue.handle();
    let display = conn.display();
    display.get_registry(&qh, ());

    let mut state = AppData { compositor: None, shm: None };
    event_queue.roundtrip(&mut state).unwrap();
    // Now state.compositor and state.shm are populated
}
```

### 73.3 The Dispatch Trait

Every Wayland object type requires a `Dispatch<ObjectType, UserData>` implementation:
```rust
impl Dispatch<wl_compositor::WlCompositor, ()> for AppData {
    fn event(_: &mut Self, _: &wl_compositor::WlCompositor,
             _: wl_compositor::Event, _: &(), _: &Connection,
             _: &QueueHandle<Self>) {
        // WlCompositor has no events — empty impl
    }
}
```

Wayland objects without events still need the trait (zero-event objects).

### 73.4 Creating a Surface and XDG Window

```rust
use wayland_protocols::xdg::shell::client::{
    xdg_surface, xdg_toplevel, xdg_wm_base,
};

impl Dispatch<xdg_wm_base::XdgWmBase, ()> for AppData {
    fn event(_: &mut Self, wm_base: &xdg_wm_base::XdgWmBase,
             event: xdg_wm_base::Event, _: &(), _: &Connection,
             _: &QueueHandle<Self>) {
        if let xdg_wm_base::Event::Ping { serial } = event {
            wm_base.pong(serial);  // required: respond to keep-alive pings
        }
    }
}

// Creating a window
let surface = compositor.create_surface(&qh, ());
let xdg_surface = wm_base.get_xdg_surface(&surface, &qh, ());
let toplevel = xdg_surface.get_toplevel(&qh, ());
toplevel.set_title("My Rust Window".to_string());
surface.commit();
```

### 73.5 Shared Memory Rendering

```rust
use memmap2::MmapMut;
use std::os::unix::io::FromRawFd;

fn create_shm_buffer(shm: &wl_shm::WlShm, width: u32, height: u32,
                     qh: &QueueHandle<AppData>) -> (wl_buffer::WlBuffer, MmapMut) {
    let stride = width * 4;
    let size = stride * height;

    // Create anonymous shared memory
    let fd = unsafe { libc::memfd_create(b"wl-buffer\0" as *const _, 0) };
    unsafe { libc::ftruncate(fd, size as i64) };

    let mmap = unsafe { MmapMut::map_mut(&std::fs::File::from_raw_fd(fd)).unwrap() };

    let pool = shm.create_pool(unsafe { BorrowedFd::borrow_raw(fd) }, size as i32, qh, ());
    let buffer = pool.create_buffer(0, width as i32, height as i32,
                                    stride as i32, wl_shm::Format::Argb8888, qh, ());
    (buffer, mmap)
}
```

### 73.6 Smithay Client Toolkit (SCTK)

SCTK handles the boilerplate — registry, seat, output — so you focus on app logic:

```rust
use smithay_client_toolkit::{
    compositor::CompositorHandler,
    shell::xdg::window::{Window, WindowConfigure, WindowHandler},
    delegate_compositor, delegate_xdg_window,
};

struct MyApp { window: Option<Window> }

impl WindowHandler for MyApp {
    fn request_close(&mut self, _: &Connection, _: &QueueHandle<Self>, _: &Window) {
        std::process::exit(0);
    }
    fn configure(&mut self, _: &Connection, qh: &QueueHandle<Self>,
                 _: &Window, _: WindowConfigure, _: u32) {
        // Handle resize
    }
}
delegate_xdg_window!(MyApp);
```

### 73.7 Layer Shell in Rust

For bars and widgets using `wlr-layer-shell`:
```rust
use wayland_protocols_wlr::layer_shell::v1::client::{
    zwlr_layer_shell_v1, zwlr_layer_surface_v1,
};

let layer_surface = layer_shell.get_layer_surface(
    &surface,
    Some(&output),
    zwlr_layer_shell_v1::Layer::Top,
    "my-bar".to_string(),
    &qh,
    ()
);
layer_surface.set_anchor(Anchor::TOP | Anchor::LEFT | Anchor::RIGHT);
layer_surface.set_size(0, 36);      // width=0 → stretch to anchor width
layer_surface.set_exclusive_zone(36);
surface.commit();
```

### 73.8 Real-World Rust Wayland Projects

Study these for production patterns:
- **niri** (Smithay compositor): https://github.com/YaLTeR/niri
- **swayidle** has a Rust port: https://github.com/Smithay/swayidle-rs
- **wayrs** (alternative client library): https://github.com/MaxVerevkin/wayrs
- **client-toolkit examples**: https://github.com/Smithay/client-toolkit/tree/master/examples

### 73.9 Async Wayland with Tokio

```rust
use wayland_client::Connection;
use tokio::io::unix::AsyncFd;

// Non-blocking event dispatch with tokio
let conn = Connection::connect_to_env().unwrap();
let fd = conn.prepare_read().unwrap();
let async_fd = AsyncFd::new(fd).unwrap();
async_fd.readable().await.unwrap().retain_ready();
conn.read_events().unwrap();
```


---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).