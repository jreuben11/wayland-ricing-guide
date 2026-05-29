# Chapter 48 — Building a Compositor in Rust with Smithay

## Overview

Smithay is a pure-Rust library for building Wayland compositors. Unlike the C-based wlroots (covered in Chapter 47), Smithay provides memory-safe abstractions over the Wayland protocol stack, DRM/KMS output management, and input handling — all within Rust's ownership model. Real-world compositors built on Smithay include `niri`, `Jay`, and COSMIC's `cosmic-comp`, making it a proven foundation for production-grade work.

This chapter walks through building the same minimal compositor as Chapter 47, but using Smithay's idiomatic Rust APIs. You will learn how Smithay structures state management, how it uses delegate macros for protocol dispatch, how to wire up the calloop event loop, and how to integrate DRM/libinput backends for bare-metal execution. By the end you will have a working compositor skeleton that maps XDG toplevels and renders them with an OpenGL ES renderer.

For session startup wiring and systemd socket activation, see Ch 53. For writing custom Wayland protocols in Rust, see Ch 51. For layer-shell (status bars, overlays) integration, see Ch 50.

---

## 48.1 Why Smithay vs. wlroots (in Rust)

Choosing between Smithay and wlroots for a Rust compositor project is the first architectural decision you will make. Both cover the same domain — Wayland protocol dispatch, KMS/DRM output, input — but they expose very different philosophies.

`wlroots-rs` wraps the C library with `unsafe` bindings. Every call crosses the FFI boundary, and the binding layer is thin enough that you still need to understand wlroots internals to avoid use-after-free bugs in the C heap. The bindings have historically lagged behind wlroots releases by months, and the project has cycled through maintainers. For Rust code, this means your `unsafe` surface is large and auditing it is labour-intensive.

Smithay is written from scratch in safe Rust. Its abstractions are higher-level: instead of managing raw `wlr_surface` pointers you work with Smithay's `WlSurface` and `Window` types, which enforce lifetimes at compile time. The trade-off is that Smithay's API is more opinionated and its version compatibility with the broader Wayland ecosystem must be maintained by the Smithay team rather than delegated to the underlying C library.

| Dimension | wlroots-rs | Smithay |
|---|---|---|
| Language | Unsafe Rust over C | Pure safe Rust |
| API stability | Follows wlroots C releases | Smithay crate on crates.io |
| Real-world users | sway (C), river (C) | niri, Jay, cosmic-comp |
| Learning curve | Need wlroots C knowledge | Rust-native concepts |
| Test backend | Headless via wlroots | `WinitBackend` (winit, nested) |
| DRM/KMS | Via wlroots | `DrmBackend` + `GbmAllocator` |
| Rendering | wlr_renderer (C) | `GlesRenderer`, `PixmanRenderer` |

Unless you are extending an existing wlroots compositor from the C side, Smithay is the recommended choice for new Rust compositor projects in 2024+.

---

## 48.2 Project Setup

Create the project and configure the `Cargo.toml` with the correct feature flags. Smithay's features are numerous but composable — only enable what you need to keep compile times manageable.

```bash
cargo new --bin my-compositor
cd my-compositor
```

```toml
# Cargo.toml
[package]
name = "my-compositor"
version = "0.1.0"
edition = "2021"
rust-version = "1.75"

[dependencies]
# Core Smithay: Wayland frontend + DRM/libinput backends + OpenGL ES renderer
smithay = { version = "0.7", features = [
    "desktop",
    "wayland_frontend",
    "backend_drm",
    "backend_gbm",
    "backend_libinput",
    "backend_udev",
    "renderer_gl",
    "renderer_pixman",
    "use_system_lib",
] }

# Event loop used internally by Smithay
calloop = { version = "0.13", features = ["executor"] }
calloop-wayland-source = "0.3"

# Wayland server-side protocol types
wayland-server = "0.31"
wayland-protocols = { version = "0.31", features = ["server"] }

# Logging
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter"] }

# Linux DRM/GBM bindings
drm = "0.13"
gbm = "0.15"

# Input
input = "0.8"  # libinput Rust bindings

# Utilities
anyhow = "1"
```

After adding the dependencies, run `cargo fetch` to populate the local registry. The first full build will take several minutes because Smithay pulls in EGL and libdrm bindings; subsequent incremental builds are much faster.

```bash
# Verify everything compiles before writing code
cargo check
```

If you see linker errors about missing `libEGL` or `libgbm`, install the system packages:

```bash
# Debian/Ubuntu
sudo apt install libegl-dev libgbm-dev libdrm-dev libinput-dev

# Arch
sudo pacman -S mesa libdrm libinput
```

---

## 48.3 The Calloop Event Loop

Smithay delegates all I/O multiplexing to `calloop`, a structured event loop library built around Linux `epoll`. Understanding calloop's model is prerequisite to understanding how Smithay's internals work.

The fundamental types are `EventLoop<D>` (owns the epoll fd and all sources), `LoopHandle<D>` (a cheaply cloneable handle for inserting sources from anywhere), and `LoopSignal` (used to stop the loop from a signal handler or another thread). The type parameter `D` is your compositor state — calloop passes `&mut D` to every event callback, which is how Smithay gets mutable access to your state from all its internal handlers.

Wayland's `Display` is integrated via `calloop-wayland-source`, which wraps the Wayland socket fd as a calloop event source. When a client sends a request, calloop reads it off the socket and dispatches it through Smithay's protocol handler infrastructure, eventually calling your `XdgShellHandler`, `CompositorHandler`, etc. implementations.

```rust
use calloop::{EventLoop, LoopHandle, LoopSignal};
use calloop_wayland_source::WaylandSource;
use smithay::reexports::wayland_server::Display;

fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter("my_compositor=debug,smithay=warn")
        .init();

    // Create the wayland display (the server socket)
    let mut display: Display<MyCompositor> = Display::new()?;

    // Create the calloop event loop
    let mut event_loop: EventLoop<MyCompositor> = EventLoop::try_new()?;
    let loop_handle: LoopHandle<MyCompositor> = event_loop.handle();

    // Integrate the Wayland display into the event loop
    WaylandSource::new(display.handle(), display)
        .insert(loop_handle.clone())?;

    // Build our compositor state
    let mut state = MyCompositor::new(&loop_handle)?;

    // Run the loop — blocks until loop_signal.stop() is called
    event_loop.run(None, &mut state, |_| {})?;
    Ok(())
}
```

For timer-based tasks (frame scheduling, animation, idle timeouts) you insert a `calloop::timer::Timer` source. For UNIX signal handling you use `calloop::signals::Signals`. All of these interact with the same `LoopHandle`, so your signal handler can call `loop_handle.insert_idle(|state| state.request_repaint())` to schedule work on the next loop iteration without locking.

---

## 48.4 State Management in Smithay

Smithay's architecture requires a single top-level struct that holds all compositor state. Smithay's protocol handlers are implemented as traits on this struct, and every delegate macro establishes the connection between an incoming Wayland request and the corresponding trait method.

The state struct grows large quickly — a minimal but functional compositor needs at least a dozen fields. The pattern is to group related state into sub-structs and use Smithay's `*State` types (e.g., `CompositorState`, `XdgShellState`) which cache protocol-level bookkeeping so your handler methods stay clean.

```rust
use smithay::{
    delegate_compositor, delegate_shm, delegate_xdg_shell,
    delegate_seat, delegate_output,
    desktop::{Space, Window},
    input::{Seat, SeatState, keyboard::KeyboardHandle, pointer::PointerHandle},
    reexports::wayland_server::{Display, DisplayHandle},
    wayland::{
        compositor::CompositorState,
        output::OutputManagerState,
        shell::xdg::XdgShellState,
        shm::ShmState,
        socket::ListeningSocketSource,
    },
};
use calloop::LoopHandle;

pub struct MyCompositor {
    // The Wayland display handle (does not own the display)
    pub display_handle: DisplayHandle,

    // Window layout manager
    pub space: Space<Window>,

    // Input devices
    pub seat: Seat<Self>,
    pub pointer: PointerHandle<Self>,
    pub keyboard: KeyboardHandle<Self>,

    // Protocol state bookkeeping (Smithay-managed)
    pub compositor_state: CompositorState,
    pub xdg_shell_state: XdgShellState,
    pub shm_state: ShmState,
    pub output_manager_state: OutputManagerState,
    pub seat_state: SeatState<Self>,

    // Compositor-specific
    pub loop_handle: LoopHandle<'static, Self>,
    pub should_stop: bool,
}

impl MyCompositor {
    pub fn new(loop_handle: &LoopHandle<'static, Self>) -> anyhow::Result<Self> {
        // Build a temporary display to extract the handle
        // (display is owned by the calloop WaylandSource)
        let display: Display<Self> = Display::new()?;
        let dh = display.handle();

        let compositor_state = CompositorState::new::<Self>(&dh);
        let xdg_shell_state = XdgShellState::new::<Self>(&dh);
        let shm_state = ShmState::new::<Self>(&dh, vec![]);
        let output_manager_state = OutputManagerState::new_with_xdg_output::<Self>(&dh);
        let mut seat_state = SeatState::new();
        let seat = seat_state.new_wl_seat(&dh, "seat0");
        let pointer = seat.add_pointer();
        let keyboard = seat.add_keyboard(Default::default(), 200, 25)?;

        Ok(Self {
            display_handle: dh,
            space: Space::default(),
            seat,
            pointer,
            keyboard,
            compositor_state,
            xdg_shell_state,
            shm_state,
            output_manager_state,
            seat_state,
            loop_handle: loop_handle.clone(),
            should_stop: false,
        })
    }
}
```

Smithay enforces that only one `&mut MyCompositor` exists at a time, which guarantees that protocol handlers cannot accidentally run concurrently. If you need to share state across threads (e.g., a GPU render thread), wrap it in `Arc<Mutex<_>>` and store the `Arc` inside the state struct.

---

## 48.5 Delegate Macros

Smithay uses Rust procedural macros to wire Wayland protocol requests to trait implementations on your state struct. Each `delegate_*!` macro expands to the `Dispatch` impl for the relevant protocol objects. Without these macros Smithay does not know which type to call for incoming requests.

The macros live in `smithay` and follow a consistent naming pattern: `delegate_<protocol_name>!(YourState)`. Most compositors need at least the five shown below; add more as you implement additional protocols.

```rust
// Wire Wayland core compositor protocol (wl_surface, wl_region, wl_compositor)
delegate_compositor!(MyCompositor);

// Wire XDG shell (xdg_surface, xdg_toplevel, xdg_popup)
delegate_xdg_shell!(MyCompositor);

// Wire shared memory buffers (wl_shm, wl_shm_pool, wl_buffer)
delegate_shm!(MyCompositor);

// Wire seats and input (wl_seat, wl_keyboard, wl_pointer, wl_touch)
delegate_seat!(MyCompositor);

// Wire output advertisements (wl_output, xdg_output_manager_v1)
delegate_output!(MyCompositor);
```

Each macro requires that your state type implements the corresponding handler trait. For example, `delegate_compositor!` requires `CompositorHandler`, `delegate_xdg_shell!` requires `XdgShellHandler`, and so on. If you add the delegate macro but forget the trait impl, you get a compile error at the macro expansion site pointing to the missing `impl` block — Smithay's error messages here are descriptive.

For protocols you do not implement yourself, Smithay provides default no-op impls for some common cases. Check the Smithay docs before writing empty handler bodies — you may be able to `#[derive]` or use a blanket impl.

---

## 48.6 XDG Shell Handler

The XDG shell protocol is the primary protocol through which applications create resizable, titled windows. Implementing `XdgShellHandler` is the minimum required to display app windows. You need to handle at least `new_toplevel`, `new_popup`, and `grab` to be spec-compliant.

When a client creates an `xdg_toplevel` Smithay calls `new_toplevel` with a `ToplevelSurface` handle. At this point the surface has no committed buffer yet — it is not safe to render it. The standard pattern is to wrap it in Smithay's `Window` type and map it into the `Space` at some position; the `Space` will handle culling un-committed windows on its own.

```rust
use smithay::{
    desktop::Window,
    wayland::shell::xdg::{
        XdgShellHandler, XdgShellState, ToplevelSurface, PopupSurface,
        PopupKind, PositionerState, XdgToplevelSurfaceData,
    },
    utils::{Serial, SERIAL_COUNTER},
    reexports::wayland_server::protocol::wl_seat::WlSeat,
};

impl XdgShellHandler for MyCompositor {
    fn xdg_shell_state(&mut self) -> &mut XdgShellState {
        &mut self.xdg_shell_state
    }

    fn new_toplevel(&mut self, surface: ToplevelSurface) {
        // Wrap in desktop::Window for Space management
        let window = Window::new_wayland_window(surface);
        // Map at origin; a real compositor would apply tiling/floating logic
        self.space.map_element(window, (0, 0), true);
    }

    fn new_popup(&mut self, surface: PopupSurface, _positioner: PositionerState) {
        // Smithay's PopupManager handles popup tree stacking
        // For minimal impl: just track it
        let _ = surface;
    }

    fn reposition_request(
        &mut self,
        surface: PopupSurface,
        positioner: PositionerState,
        token: u32,
    ) {
        surface.with_pending_state(|s| {
            s.geometry = positioner.get_geometry();
            s.positioner = positioner;
        });
        surface.send_repositioned(token);
        let _ = surface.send_configure();
    }

    fn grab(&mut self, _surface: PopupSurface, _seat: WlSeat, _serial: Serial) {
        // Implement popup grab for menus — omitted for minimal compositor
    }

    fn toplevel_destroyed(&mut self, surface: ToplevelSurface) {
        // Find and remove from space
        let window = self.space
            .elements()
            .find(|w| {
                w.wl_surface()
                    .map(|s| &s == surface.wl_surface())
                    .unwrap_or(false)
            })
            .cloned();
        if let Some(w) = window {
            self.space.unmap_elem(&w);
        }
    }
}
```

After mapping the window you must send an initial configure so the client knows its allocated size. For a floating compositor the configure carries the compositor's preferred size (or `(0,0)` to let the client choose). Tiling compositors send the tile dimensions.

```rust
// In new_toplevel, after map_element:
surface.send_configure();
```

---

## 48.7 Backend: DRM/libinput

The backend layer is where Smithay bridges Linux kernel APIs (KMS, evdev) to the compositor's abstract event model. Smithay provides three backends you will commonly use together:

- `UdevBackend`: scans `/dev/dri/` for DRM devices, subscribes to udev hotplug events via `calloop`, and notifies you when a GPU becomes available or is removed.
- `DrmBackend` + `GbmAllocator`: opens the DRM device, enumerates CRTCs/connectors/encoders, allocates GBM surfaces as scanout buffers, and drives page-flip timing.
- `LibinputInputBackend`: wraps libinput for keyboard, pointer, and touch events, converting them into Smithay's `InputEvent` types.

```rust
use smithay::{
    backend::{
        drm::{DrmDevice, DrmDeviceFd, DrmEvent},
        udev::{UdevBackend, UdevEvent},
        libinput::{LibinputInputBackend, LibinputSessionInterface},
        session::{Session, libseat::LibSeatSession},
        input::InputEvent,
        renderer::gles::GlesRenderer,
    },
};
use input::Libinput;

fn init_backend(
    state: &mut MyCompositor,
    loop_handle: &LoopHandle<'static, MyCompositor>,
) -> anyhow::Result<()> {
    // Open a logind/libseat session for device access without root
    let (session, notifier) = LibSeatSession::new()?;

    // Set up libinput
    let mut libinput_context = Libinput::new_with_udev(
        LibinputSessionInterface::from(session.clone())
    );
    libinput_context.udev_assign_seat(&session.seat())?;
    let libinput_backend = LibinputInputBackend::new(libinput_context);

    // Insert libinput into the event loop
    loop_handle.insert_source(libinput_backend, move |event, _, state| {
        state.process_input_event(event);
    })?;

    // Enumerate DRM devices via udev
    let udev_backend = UdevBackend::new(&session.seat())?;
    for (dev_id, path) in udev_backend.device_list() {
        state.device_added(dev_id, path.to_owned(), &session)?;
    }

    loop_handle.insert_source(udev_backend, move |event, _, state| {
        match event {
            UdevEvent::Added { device_id, path } => {
                let _ = state.device_added(device_id, path, &session.clone());
            }
            UdevEvent::Removed { device_id } => {
                state.device_removed(device_id);
            }
            _ => {}
        }
    })?;

    Ok(())
}
```

For testing inside an existing compositor (Sway, COSMIC, etc.) replace the DRM/libinput setup with the winit backend (`WinitBackend`), which opens a window inside the host Wayland or X11 session and routes input through it. This is invaluable during development. Note that `WinitEventLoop` is **not** a calloop event source; dispatch it directly each frame by calling `dispatch_new_events`.

```rust
// Nested/testing backend
use smithay::backend::winit::{self, WinitEvent};

let (backend, mut winit_evt_loop) = winit::init()?;
// WinitEventLoop is NOT a calloop source — dispatch it manually each frame:
winit_evt_loop.dispatch_new_events(|event| {
    match event {
        WinitEvent::Resized { size, .. } => { /* update output geometry */ }
        WinitEvent::Input(input_event) => state.process_input_event(input_event),
        WinitEvent::Redraw => state.render(),
        WinitEvent::CloseRequested => state.should_stop = true,
        _ => {}
    }
});
```

---

## 48.8 Rendering with Smithay

Smithay's renderer layer is built around the `Renderer` trait, which abstracts over `GlesRenderer` (OpenGL ES 2.0), `PixmanRenderer` (software), and any custom renderer you implement. The `GlesRenderer` is the default choice for hardware-accelerated compositing.

The `damage_tracked_renderer` utility tracks which screen regions changed since the last frame. On KMS outputs this feeds directly into partial buffer updates (`DRM_IOCTL_MODE_ADDFB2` with explicit damage), reducing GPU bandwidth — essential for power efficiency on laptops.

```rust
use smithay::{
    backend::renderer::{
        gles::GlesRenderer,
        damage::{OutputDamageTracker, Error as DamageError},
        element::{
            surface::WaylandSurfaceRenderElement,
            utils::select_dmabuf_feedback,
            AsRenderElements,
        },
    },
    desktop::space::SpaceRenderElements,
    output::Output,
    utils::Transform,
};

fn render_frame(
    renderer: &mut GlesRenderer,
    damage_tracker: &mut OutputDamageTracker,
    output: &Output,
    space: &Space<Window>,
) -> anyhow::Result<()> {
    // Collect render elements from all windows in the space
    let elements: Vec<SpaceRenderElements<GlesRenderer>> =
        space.render_elements_for_output(renderer, output, 1.0);

    // Obtain a framebuffer and buffer age from the backend (KMS/winit), then render.
    // OutputDamageTracker::from_output(&output) constructs the tracker before this call.
    // render_output requires an explicit framebuffer and buffer age for partial damage.
    damage_tracker.render_output(
        renderer,
        &mut framebuffer,  // R::Framebuffer obtained from the backend swap-chain
        age,               // buffer age (0 = full redraw) from the backend
        &elements,
        [0.1, 0.1, 0.1, 1.0],  // clear colour (dark grey)
    )?;

    Ok(())
}
```

Custom render elements let you draw compositor-owned UI (cursors, window decorations, screen tearing indicators) without going through the Wayland surface protocol. Implement the `RenderElement<R>` trait:

```rust
use smithay::backend::renderer::element::{RenderElement, Id, Element};

struct CursorElement {
    id: Id,
    position: smithay::utils::Point<i32, smithay::utils::Physical>,
    // texture handle etc.
}

impl Element for CursorElement {
    fn id(&self) -> &Id { &self.id }
    fn current_commit(&self) -> smithay::backend::renderer::utils::CommitCounter {
        smithay::backend::renderer::utils::CommitCounter::default()
    }
    fn src(&self) -> smithay::utils::Rectangle<f64, smithay::utils::Buffer> {
        todo!()
    }
    fn geometry(&self, _scale: smithay::utils::Scale<f64>)
        -> smithay::utils::Rectangle<i32, smithay::utils::Physical> {
        todo!()
    }
}

impl RenderElement<GlesRenderer> for CursorElement {
    fn draw(
        &self,
        frame: &mut smithay::backend::renderer::gles::GlesFrame<'_>,
        _src: smithay::utils::Rectangle<f64, smithay::utils::Buffer>,
        dst: smithay::utils::Rectangle<i32, smithay::utils::Physical>,
        _damage: &[smithay::utils::Rectangle<i32, smithay::utils::Physical>],
    ) -> Result<(), smithay::backend::renderer::gles::GlesError> {
        // Draw cursor texture into dst using frame.render_texture_at(...)
        Ok(())
    }
}
```

---

## 48.9 Desktop Utilities

Smithay's `desktop` module provides high-level abstractions that sit above the raw protocol handlers. These are optional but save significant reimplementation effort.

`Space<E>` is a 2D coordinate system that tracks window positions, handles z-ordering, and provides hit-testing (pointer-to-window mapping). Windows are typed as a generic `E` so you can use Smithay's built-in `Window` type or wrap it in your own enum to support both Wayland and XWayland surfaces.

`PopupManager` tracks the parent-child relationship between toplevels and popups (menus, tooltips, context menus) and handles the popup grab stack — the input capture that routes keyboard/pointer events to the frontmost popup until it is dismissed.

```rust
use smithay::desktop::{
    Space, Window,
    layer_map_for_output, LayerSurface,
    PopupManager,
};
use smithay::utils::Point;

// Map a window at a specific position in global compositor coordinates
let position: Point<i32, smithay::utils::Logical> = (100, 100).into();
space.map_element(window.clone(), position, true /* activate */);

// Move an existing window
space.map_element(window.clone(), (200, 150).into(), false);

// Raise to top of z-order
space.raise_element(&window, true);

// Hit test: which window is at this pointer position?
let pointer_pos = (350.0_f64, 200.0_f64).into();
if let Some((w, surface, local_pos)) = space.element_under(pointer_pos) {
    // deliver pointer events to `surface` at `local_pos`
}

// Layer shell: each output has its own layer map
let layer_map = layer_map_for_output(&output);
// Map a layer surface (status bar, notification, etc.)
// layer_map.map_layer(&layer_surface)?;
```

The `WindowElement` enum pattern used in niri and Anvil is worth studying — it lets `Space` hold a unified type that dispatches to either Wayland windows or XWayland windows:

```rust
#[derive(Debug, Clone, PartialEq)]
pub enum WindowElement {
    Wayland(Window),
    // X11(X11Surface),  // add when XWayland support is needed
}

impl smithay::desktop::space::SpaceElement for WindowElement {
    // delegate all methods to the inner type
    fn geometry(&self) -> smithay::utils::Rectangle<i32, smithay::utils::Logical> {
        match self {
            WindowElement::Wayland(w) => w.geometry(),
        }
    }
    // ... other SpaceElement methods
}
```

---

## 48.10 Keyboard and Pointer Input Handling

Input event handling bridges the raw `LibinputInputBackend` events to Smithay's seat/keyboard/pointer abstractions, which then forward the events to the focused Wayland client via the wire protocol.

```rust
use smithay::{
    backend::input::{
        InputEvent, KeyboardKeyEvent, PointerMotionEvent,
        PointerButtonEvent, PointerAxisEvent, AbsolutePositionEvent,
    },
    input::{
        keyboard::{FilterResult, Keysym, ModifiersState},
        pointer::{AxisFrame, ButtonEvent, MotionEvent, RelativeMotionEvent},
    },
    utils::SERIAL_COUNTER,
};

impl MyCompositor {
    pub fn process_input_event<B: InputBackend>(&mut self, event: InputEvent<B>) {
        match event {
            InputEvent::Keyboard { event } => self.on_keyboard(event),
            InputEvent::PointerMotion { event } => self.on_pointer_motion(event),
            InputEvent::PointerButton { event } => self.on_pointer_button(event),
            InputEvent::PointerAxis { event } => self.on_pointer_axis(event),
            _ => {}
        }
    }

    fn on_keyboard<E: KeyboardKeyEvent>(&mut self, event: E) {
        let serial = SERIAL_COUNTER.next_serial();
        let time = event.time_msec();
        let press = event.state();

        self.keyboard.input::<(), _>(
            self,
            event.key_code(),
            press,
            serial,
            time,
            |state, modifiers, handle| {
                // Compositor-level keybindings (Mod+Q to quit, etc.)
                let sym = handle.modified_sym();
                if modifiers.logo && sym == Keysym::q {
                    state.should_stop = true;
                    return FilterResult::Intercept(());
                }
                FilterResult::Forward
            },
        );
    }

    fn on_pointer_motion<E: PointerMotionEvent<B>, B: InputBackend>(&mut self, event: E) {
        let serial = SERIAL_COUNTER.next_serial();
        // Update pointer position within output bounds
        let delta = event.delta();
        // ... clamp to output rect ...
        self.pointer.motion(
            self,
            None, // focus: compute from space.element_under(new_pos)
            &MotionEvent { location: (0.0, 0.0).into(), serial, time: event.time_msec() },
        );
    }

    fn on_pointer_button<E: PointerButtonEvent<B>, B: InputBackend>(&mut self, event: E) {
        let serial = SERIAL_COUNTER.next_serial();
        self.pointer.button(
            self,
            &ButtonEvent {
                serial,
                time: event.time_msec(),
                button: event.button_code(),
                state: event.state().into(),
            },
        );
        self.pointer.frame(self);
    }
}
```

---

## 48.11 Study Resources and Real-World Compositors

Learning from production Smithay compositors is the fastest way to understand the patterns the library encourages. Both niri and Anvil (Smithay's own example compositor) are well-commented.

| Resource | URL | Notes |
|---|---|---|
| Smithay book | https://smithay.github.io/smithay/ | Official architecture guide |
| Smithay crate docs | https://docs.rs/smithay | API reference |
| Anvil (example) | https://github.com/Smithay/smithay/tree/master/anvil | Complete DRM + winit + X11 backend example |
| niri | https://github.com/YaLTeR/niri | Scrolling tiling compositor, production quality |
| Jay | https://github.com/mahkoh/jay | Another production Smithay compositor |
| cosmic-comp | https://github.com/pop-os/cosmic-comp | COSMIC DE compositor, complex real-world usage |
| calloop docs | https://docs.rs/calloop | Event loop API reference |

When reading Anvil, start with `anvil/src/state.rs` (state struct), then `anvil/src/shell/` (protocol handlers), then `anvil/src/drawing.rs` (render pipeline). This mirrors the structure of every Smithay compositor.

---

## Troubleshooting

**`Display::new()` panics or returns an error about `WAYLAND_DISPLAY`**
You are probably running with `WAYLAND_DISPLAY` already set (inside an existing compositor). Smithay's `Display::new()` creates a server socket and sets `WAYLAND_DISPLAY` in the environment. If the env var is already set, some versions of the library will fail. Unset it before launching your compositor in a VT: `unset WAYLAND_DISPLAY && cargo run`.

**Blank screen / no windows rendered**
Check that you are calling `surface.send_configure()` after `new_toplevel`. Clients wait for the initial configure before committing buffers. Without it, `space.elements()` returns items but their surfaces have no buffers and the render call skips them silently.

**`delegate_*!` macro gives "the trait X is not implemented for MyCompositor"**
Each delegate macro requires a corresponding handler trait `impl`. Read the error: it will name the exact trait. Add the missing `impl` block — even empty `fn` bodies are fine for traits with optional methods.

**GBM/EGL errors at startup (`EGL_BAD_DISPLAY`)**
Your user must be in the `video` and `render` groups, or you must use a libseat/logind session (see `LibSeatSession::new()`). Running as root works but is not recommended. Check group membership with `groups $USER`.

**High CPU usage in the render loop**
Ensure you are waiting for page-flip events before queuing the next frame. In the DRM backend, insert your re-render trigger inside the `DrmEvent::VBlank` handler, not in a tight loop. Smithay's `DrmCompositor` helper manages this automatically if you use it.

**Keyboard input not reaching clients**
Verify that `seat.add_keyboard(...)` succeeded and that you are calling `keyboard.set_focus(self, surface, serial)` when a window receives pointer focus. Clients that do not have keyboard focus will not receive key events regardless of the seat's keyboard state.

**`cargo build` fails with linker errors on Wayland symbols**
Add `wayland-client` to `[dependencies]` even if you only use server-side Smithay — some feature combinations pull in the client library transitively and require it to be explicitly listed for the linker.

---

*See also: Ch 47 (wlroots compositor in C), Ch 49 (XWayland integration), Ch 50 (layer-shell and bars), Ch 51 (custom Wayland protocols), Ch 53 (session startup and systemd socket activation).*

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
