# Chapter 5 — wlroots: The Compositor Building Blocks

## Contents

- [Overview](#overview)
- [5.1 wlroots Philosophy](#51-wlroots-philosophy)
- [5.2 Architecture Overview](#52-architecture-overview)
- [5.3 Backends](#53-backends)
- [5.4 Protocol Implementations in wlroots](#54-protocol-implementations-in-wlroots)
- [5.5 The Scene Graph API](#55-the-scene-graph-api)
- [5.6 Input Handling in wlroots](#56-input-handling-in-wlroots)
- [5.7 wlroots vs. Smithay (Rust)](#57-wlroots-vs-smithay-rust)
- [5.8 Getting Started: Building a Minimal Compositor](#58-getting-started-building-a-minimal-compositor)
  - [Building wlroots from source](#building-wlroots-from-source)
  - [Running tinywl](#running-tinywl)
  - [Reading the source](#reading-the-source)
  - [Checking protocol support at runtime](#checking-protocol-support-at-runtime)
- [Troubleshooting](#troubleshooting)
  - [Compositor fails to start with "failed to open DRM device"](#compositor-fails-to-start-with-failed-to-open-drm-device)
  - [Cursor is invisible or corrupted](#cursor-is-invisible-or-corrupted)
  - [Screen is black, no output rendered](#screen-is-black-no-output-rendered)
  - [Application uses wrong scale factor](#application-uses-wrong-scale-factor)
  - [XWayland windows do not appear](#xwayland-windows-do-not-appear)
  - [Debugging wlroots internals](#debugging-wlroots-internals)

---


## Overview

wlroots is a modular C library that provides the low-level building blocks required
to write a Wayland compositor. It powers Sway, river, labwc, cage, and many others.
Rather than shipping a complete compositor, wlroots deliberately exposes its internals
so that compositor authors can pick the pieces they need, replace the ones they don't,
and avoid re-implementing the hard parts: KMS/DRM output management, libinput event
processing, protocol implementations, and renderer abstraction.

Understanding wlroots is essential for any serious ricing effort because every
configuration knob you tweak in Sway or labwc ultimately exercises a wlroots code
path. When something misbehaves — a surface fails to render, a Wayland protocol is
unimplemented, a cursor lags — the root cause is almost always in wlroots. This
chapter walks through the library's architecture, backend system, protocol
implementations, scene graph API, and input model so you can debug with confidence
and, if you want to, write your own compositor.

Cross-references: See Ch 01–02 (Wayland Protocol Architecture and Wire Protocol) for the protocol layer that
wlroots implements, Ch 06 (Sway) for the most mature wlroots consumer, and Ch 53
(Session Startup) for how a wlroots compositor is launched by a display manager or
login shell.


## 5.1 wlroots Philosophy

wlroots was created in 2017 by Drew DeVault and the swaywm team specifically to
extract the generic compositor infrastructure from Sway so that other projects could
reuse it. The guiding principle is "compositors, not compositor." wlroots ships no
window management policy. There is no built-in tiling logic, no default keybindings,
and no opinion about how windows should be arranged. Every policy decision is left to
the compositor author, who writes the glue code that calls wlroots APIs.

The library is written in C99 and targets Linux (and, experimentally, FreeBSD via
evdev). The public API is a collection of opaque structs and functions grouped by
feature area: `wlr_output`, `wlr_surface`, `wlr_keyboard`, etc. Most structs expose
a `wl_signal` field for every event they emit (e.g., `wlr_output.events.frame`) so
that compositors subscribe with `wl_signal_add`. This signal/listener model is
inherited from `libwayland-server` and pervades the whole library.

Version stability is important to understand. wlroots follows a "no stable ABI"
policy: each release (0.17, 0.18, …) may break the API, and compositor authors are
expected to pin to a specific wlroots version and update explicitly. The version
number roughly tracks the year of release — 0.17 in late 2023, 0.18 in mid-2024.
Sway pins wlroots in its own source tree. Hyprland historically vendored a heavily
patched fork before switching to its own Aquamarine backend library. River and labwc
follow upstream wlroots closely.

| Compositor  | wlroots usage          | Notes                                  |
|-------------|------------------------|----------------------------------------|
| Sway        | Pinned submodule       | Most conservative; stable tracking    |
| river       | System wlroots         | Tracks upstream closely                |
| labwc       | System wlroots         | stacking WM, Openbox-inspired          |
| cage        | System wlroots         | Single-app kiosk compositor            |
| Hyprland    | Aquamarine (own lib)   | Forked away for proprietary extensions |
| gamescope   | No wlroots             | Custom compositor for Steam gaming     |


## 5.2 Architecture Overview

wlroots is layered. At the bottom sits the **backend** layer, which abstracts the
physical hardware: DRM/KMS for outputs, libinput for input devices, or a nested
Wayland/X11 window for development. Above that is the **renderer** layer, which talks
to the GPU via OpenGL ES 2 or Vulkan. Above the renderer is the **allocator** layer,
which hands out shared memory (GBM, DUMB buffers, or DMA-BUF). At the top are the
protocol implementations — xdg-shell, layer-shell, screencopy, xdg-output — and the
scene graph API that connects surfaces to outputs.

The scene graph (`wlr_scene`) was added in wlroots 0.15 as a high-level rendering
tree. Before it existed, every compositor had to manually track surface damage, walk
the surface tree, and submit draw calls. The scene graph encapsulates that complexity:
you add nodes (buffers, subsurfaces, rectangles) to the tree, mark them as
visible/invisible, reposition them, and wlroots handles damage tracking, z-ordering,
and present calls automatically. Compositors that adopt the scene graph (river,
labwc, cage) are substantially simpler to maintain than those that predate it (Sway
0.x before its migration).

The allocator and renderer are intentionally separated. The allocator picks where in
memory a buffer lives (system RAM, GPU VRAM, a DMA-BUF shared with a video decoder).
The renderer picks how to interpret that buffer (shaders, texture formats). This
separation makes it possible to render via Vulkan while allocating with GBM, or to
use software rendering (pixman) in a headless test environment.

```
┌─────────────────────────────────────────────┐
│              Your Compositor                │
│  (window management policy, keybindings)    │
├─────────────────────────────────────────────┤
│            Protocol Implementations         │
│  xdg_shell  layer_shell  screencopy  seat   │
├─────────────────────────────────────────────┤
│              Scene Graph API                │
│    wlr_scene_tree / wlr_scene_buffer        │
├───────────────┬─────────────────────────────┤
│   Renderer    │        Allocator            │
│  GLES2/Vulkan │     GBM / DMA-BUF           │
├───────────────┴─────────────────────────────┤
│                 Backend                     │
│   DRM   │  libinput  │  Wayland  │   X11    │
└─────────────────────────────────────────────┘
```

Initialising the stack in a real compositor looks like:

```c
struct wlr_backend *backend = wlr_backend_autocreate(wl_display, NULL);
struct wlr_renderer *renderer = wlr_renderer_autocreate(backend);
struct wlr_allocator *allocator = wlr_allocator_autocreate(backend, renderer);
wlr_renderer_init_wl_display(renderer, wl_display);
```

`wlr_backend_autocreate` inspects the environment: if `WAYLAND_DISPLAY` is set it
creates a nested Wayland backend; if `DISPLAY` is set it creates an X11 backend;
otherwise it falls back to DRM. This makes development on a desktop seamless — you
run your compositor inside Sway or KDE Plasma and see it in a window.


## 5.3 Backends

The backend layer is the first point of contact between wlroots and the hardware.
Each backend emits `new_output` and `new_input` signals when it discovers devices.
Your compositor listens to those signals and configures the devices.

**`wlr_drm_backend`** is the production backend. It uses the Linux Direct Rendering
Manager (DRM) subsystem via KMS (Kernel Mode Setting) to drive physical monitors.
It reads EDID data from connected displays and populates `wlr_output.modes` with the
supported video modes. When you call `wlr_output_commit`, the backend submits a
DRM atomic commit that atomically updates all planes on that CRTC. Hardware
cursor planes are used automatically when available, reducing CPU load from cursor
movement to nearly zero.

**`wlr_libinput_backend`** wraps libinput to handle keyboards, mice, touchpads,
drawing tablets, and touchscreens. The backend emits typed events
(`wlr_event_pointer_motion`, `wlr_event_keyboard_key`, etc.) that your seat code
processes. libinput's own configuration surface (tap-to-click, natural scrolling,
acceleration profiles) is exposed through `wlr_input_device` → `wlr_pointer` →
`wlr_libinput_get_device_handle`, from which you obtain a `struct libinput_device *`
to call `libinput_device_config_*` functions directly.

**`wlr_wayland_backend`** and **`wlr_x11_backend`** create a window in an existing
compositor or X server and present your compositor inside it. They are invaluable for
development: you can test your compositor without a VT switch, attach gdb, and use
your normal desktop environment's clipboard.

**`wlr_headless_backend`** creates virtual outputs and inputs with no display. It is
used by compositor test suites and CI pipelines. Combined with `wlr_renderer_autocreate`
in software mode (pixman), a headless compositor can render to offscreen buffers for
screenshot-based regression tests.

```bash
# Run your compositor nested under the current Sway session for development
WLR_BACKENDS=wayland ./my-compositor

# Force headless for CI
WLR_BACKENDS=headless WLR_RENDERER=pixman ./my-compositor --no-lockscreen
```

Useful environment variables for debugging backend selection:

| Variable               | Values              | Effect                                     |
|------------------------|---------------------|--------------------------------------------|
| `WLR_BACKENDS`         | `drm,libinput`      | Override auto-detection                    |
| `WLR_DRM_DEVICES`      | `/dev/dri/card1`    | Force a specific GPU                       |
| `WLR_RENDERER`         | `gles2`, `vulkan`, `pixman` | Override renderer selection        |
| `WLR_RENDERER_ALLOW_SOFTWARE` | `1`        | Allow pixman on real hardware              |
| `WLR_NO_HARDWARE_CURSORS` | `1`             | Disable hardware cursor planes (workaround for cursor corruption) |
| `LIBSEAT_BACKEND`      | `logind`, `seatd`   | Session backend (affects DRM access)       |


## 5.4 Protocol Implementations in wlroots

wlroots bundles implementations of the most important Wayland extension protocols.
Each implementation is a self-contained struct you create and then wire into your
compositor's event loop. They do not interact with each other unless you explicitly
connect them — there is no global state.

**`wlr_compositor`** is the foundation. It implements `wl_compositor` (the core
protocol interface for creating surfaces) and `wl_subcompositor`. Every Wayland
compositor must initialise this. In wlroots:

```c
struct wlr_compositor *compositor =
    wlr_compositor_create(wl_display, 5, renderer);
```

The second argument is the maximum protocol version your compositor supports.
`wlr_compositor` manages the surface state machine: pending state, committed state,
frame callbacks, and damage regions for every client surface.

**`wlr_xdg_shell`** implements `xdg_wm_base`, which is how normal application windows
announce their existence, request decorations, and respond to configure events. When a
client calls `xdg_wm_base.get_xdg_surface` and then creates a toplevel, wlroots
emits `wlr_xdg_shell.events.new_toplevel`. Your compositor listens to that signal and
decides where to place the window, whether to tile it, etc.

```c
struct wlr_xdg_shell *xdg_shell = wlr_xdg_shell_create(wl_display, 3);
wl_signal_add(&xdg_shell->events.new_toplevel, &server.new_xdg_toplevel);
```

**`wlr_layer_shell_v1`** implements `zwlr_layer_shell_v1`, the protocol used by
status bars (waybar, swaybar), notification daemons (mako, dunst), and wallpaper
daemons (swaybg, swww). A layer surface declares its anchor (top/bottom/left/right),
layer (background/bottom/top/overlay), and exclusive zone (how many pixels of screen
space it reserves). Your compositor must honour these when positioning windows.

**`wlr_output_layout`** is not a protocol but a data structure. It tracks the
geometric arrangement of multiple monitors (their positions and scales) and provides
coordinate-space conversion helpers. `wlr_output_layout_add_auto` appends a new
output to the right of the last one; `wlr_output_layout_add` places it at an exact
pixel coordinate.

```c
struct wlr_output_layout *layout = wlr_output_layout_create();
wlr_output_layout_add_auto(layout, output);  // auto-arrange outputs
```

**`wlr_screencopy_manager_v1`** implements `zwlr_screencopy_manager_v1`, which is how
`grim` and other screenshot tools copy the framebuffer. It does not require any GPU
tricks — it uses DMA-BUF or CPU copies depending on the renderer.

**`wlr_data_device_manager`** and **`wlr_primary_selection_v1`** implement clipboard
and primary selection. `wlr_seat` must be created before these because they reference
the seat.

**`wlr_xwayland`** wraps the XWayland binary to give legacy X11 apps a way to run
under your Wayland compositor. wlroots starts the XWayland process, sets up a
Unix-domain socket, and translates X11 events to Wayland surfaces on your behalf.
Paired with `wlr_xwayland_surface.events.map`, your compositor receives legacy windows
as if they were native Wayland surfaces.

```c
struct wlr_xwayland *xwayland =
    wlr_xwayland_create(wl_display, compositor, true /* lazy */);
wl_signal_add(&xwayland->events.new_surface, &server.new_xwayland_surface);
setenv("DISPLAY", xwayland->display_name, true);
```


## 5.5 The Scene Graph API

The scene graph (`wlr_scene`) was the single biggest productivity improvement in
wlroots 0.15. Before the scene graph, compositor authors spent hundreds of lines
manually walking the `wlr_surface` tree, computing damage regions, calling
`wlr_renderer_begin`, drawing each surface with `wlr_render_texture_with_matrix`,
and calling `wlr_output_commit` with a hand-built damage rectangle. Any mistake in
that pipeline produced visual corruption, missed repaints, or unnecessary full-frame
redraws. The scene graph eliminates all of that boilerplate.

A scene is a tree of `wlr_scene_node` values. The node types are:

| Node type             | Struct                  | Purpose                             |
|-----------------------|-------------------------|-------------------------------------|
| Scene root            | `wlr_scene`             | Root of the entire tree             |
| Tree node             | `wlr_scene_tree`        | Grouping / z-ordering container     |
| Buffer node           | `wlr_scene_buffer`      | Renders a wlr_buffer (surface)      |
| Rect node             | `wlr_scene_rect`        | Solid color rectangle               |
| XDG surface tree      | `wlr_scene_xdg_surface` | Convenience: subtree for an xdg surface |
| Layer surface tree    | `wlr_scene_layer_surface_v1` | Convenience: subtree for layer-shell |

Creating a scene and attaching an XDG toplevel to it:

```c
struct wlr_scene *scene = wlr_scene_create();
struct wlr_scene_output_layout *sol =
    wlr_scene_attach_output_layout(scene, output_layout);

// When a toplevel maps:
struct wlr_scene_xdg_surface *scene_surface =
    wlr_scene_xdg_surface_create(&scene->tree, xdg_toplevel->base);
struct wlr_scene_node *node = &scene_surface->tree->node;
wlr_scene_node_set_position(node, x, y);
wlr_scene_node_raise_to_top(node);
```

Attaching the scene to an output triggers automatic per-frame rendering:

```c
wlr_scene_output_commit(scene_output, NULL);
```

Damage tracking is automatic: wlroots keeps a `pixman_region32_t` of dirty pixels per
output. Only the changed regions are repainted, which is crucial for battery life and
for compositors running on weak hardware. You can opt out of damage tracking by
calling `wlr_scene_output_set_damage_tracking(scene_output, false)` if your hardware
has partial update issues (some embedded panels with strange EDID behaviour).

Frame scheduling integrates with the output's refresh cycle. Listen to
`wlr_output.events.frame` and call `wlr_scene_output_commit` in that handler. The
backend drives the frame signal at the display's vblank, so you get automatic vsync
without polling or timers.

```c
// Frame listener
static void on_output_frame(struct wl_listener *listener, void *data) {
    struct my_output *output = wl_container_of(listener, output, frame);
    struct wlr_scene_output *scene_output =
        wlr_scene_get_scene_output(output->server->scene, output->wlr_output);
    wlr_scene_output_commit(scene_output, NULL);

    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    wlr_scene_output_send_frame_done(scene_output, &now);
}
```

`wlr_scene_output_send_frame_done` walks every surface in the scene and sends
`wl_surface.frame` callbacks to clients that requested one, telling them it is safe
to produce the next frame. Missing this call causes animated apps to freeze or spin
endlessly waiting for feedback.


## 5.6 Input Handling in wlroots

Input in wlroots is modelled around the **seat** concept from the Wayland protocol. A
`wlr_seat` represents a user's set of input devices (keyboard, pointer, touch). It
maintains focus state: which surface has keyboard focus, which surface is under the
pointer. Only one client at a time can hold keyboard focus, and only one surface can
be the pointer focus. `wlr_seat` enforces these invariants and generates the correct
Wayland protocol events (`wl_keyboard.enter`, `wl_pointer.enter/leave`, etc.).

**Pointer handling**: The `wlr_cursor` struct provides a virtual cursor that can be
driven by multiple input devices simultaneously (two mice, a touchpad, a tablet).
You attach devices with `wlr_cursor_attach_input_device`. The cursor emits transformed
events in output-layout coordinates; you do not need to convert from per-device raw
coordinates yourself.

```c
struct wlr_cursor *cursor = wlr_cursor_create();
wlr_cursor_attach_output_layout(cursor, output_layout);

// Attach every new pointer device
static void on_new_pointer(struct wl_listener *listener, void *data) {
    struct wlr_input_device *device = data;
    wlr_cursor_attach_input_device(server.cursor, device);
}

// In cursor_motion handler: update seat pointer focus
static void on_cursor_motion(struct wl_listener *listener, void *data) {
    struct wlr_pointer_motion_event *event = data;
    wlr_cursor_move(server.cursor, &event->pointer->base,
                    event->delta_x, event->delta_y);
    // Find surface under cursor, call wlr_seat_pointer_notify_enter/motion
    process_cursor_motion(server, event->time_msec);
}
```

**Keyboard handling**: `wlr_keyboard` wraps a libinput keyboard device and integrates
with `xkbcommon` for keymap handling. You set the XKB rules once after device
creation:

```c
static void on_new_keyboard(struct wl_listener *listener, void *data) {
    struct wlr_input_device *device = data;
    struct wlr_keyboard *kb = wlr_keyboard_from_input_device(device);

    struct xkb_context *ctx = xkb_context_new(XKB_CONTEXT_NO_FLAGS);
    struct xkb_rule_names rules = {
        .layout  = "us",
        .variant = "dvp",
        .options = "caps:escape",
    };
    struct xkb_keymap *keymap =
        xkb_keymap_new_from_names(ctx, &rules, XKB_KEYMAP_COMPILE_NO_FLAGS);
    wlr_keyboard_set_keymap(kb, keymap);
    xkb_keymap_unref(keymap);
    xkb_context_unref(ctx);

    wlr_seat_set_keyboard(server.seat, kb);
    wl_signal_add(&kb->events.key, &server.keyboard_key);
}
```

**Focus management**: When a toplevel is clicked or raised, you grant it keyboard
focus with:

```c
wlr_seat_keyboard_notify_enter(seat, surface,
    keysyms.data, keysyms.size, &kb->modifiers);
```

This sends `wl_keyboard.enter` to the new client and `wl_keyboard.leave` to the
previously focused client. Forgetting the `leave` causes keyboard state to get stuck
in applications, a common beginner bug.

**Pointer constraints**: For games and 3D applications that need relative mouse
motion and cursor capture, wlroots provides `wlr_pointer_constraints_v1`. When a
client calls `zwp_pointer_constraints_v1.lock_pointer`, wlroots emits
`wlr_pointer_constraints_v1.events.new_constraint`. Your compositor decides whether
to honour the constraint (typically when the window is focused and not obscured):

```c
wlr_pointer_constraint_v1_send_activated(constraint);
// From this point, cursor motion events go to the client as relative motion,
// and the cursor position is not updated on screen.
```

Unlocking happens when the window loses focus or the client releases the lock.


## 5.7 wlroots vs. Smithay (Rust)

Smithay is a Rust framework that serves the same purpose as wlroots: it provides
building blocks for writing a Wayland compositor. It powers cosmic-comp (the COSMIC
desktop compositor), anvil (the Smithay reference compositor), and several niche
projects. The two frameworks make different trade-offs.

| Dimension           | wlroots (C)                       | Smithay (Rust)                     |
|---------------------|-----------------------------------|------------------------------------|
| Language            | C99                               | Rust (2021 edition)                |
| API stability       | Breaks each minor release         | Breaks each minor release          |
| Memory safety       | Manual, prone to use-after-free   | Enforced by borrow checker         |
| Ecosystem           | Mature; Sway, river, labwc, cage  | Growing; cosmic-comp, niri         |
| GPU backend         | GLES2, Vulkan                     | GLES2, Vulkan                      |
| XWayland            | wlr_xwayland wrapper              | xwayland-rs (separate crate)       |
| DRM leasing         | wlr_drm_lease_v1                  | In progress                        |
| Scene graph         | wlr_scene (stable)                | Space8 (in development)            |
| Documentation       | Incomplete, read the source        | Rustdoc, incomplete but improving  |
| Learning curve      | Low if you know C                 | Higher if unfamiliar with Rust     |

For a ricing workflow — where you are customising an existing compositor rather than
writing your own — the choice is irrelevant: Sway and labwc are wlroots-based, niri
and cosmic-comp are Smithay-based, and you interact with all of them through the same
Wayland protocols. The distinction matters if you want to contribute patches or write
your own compositor from scratch.

If you are comfortable with Rust and want memory safety guarantees from the start,
Smithay is a strong choice. If you want to study working production code, the wlroots
ecosystem has more compositors to learn from. Many developers experiment with wlroots
first (via tinywl) because the reference material is more abundant.


## 5.8 Getting Started: Building a Minimal Compositor

The canonical starting point is `tinywl`, the reference implementation that ships
inside the wlroots source tree. It is approximately 600 lines of C and implements
just enough to tile windows horizontally, move them, and handle keyboard/pointer
input. It is deliberately minimal — no layer shell, no screencopy, no XWayland — so
you can read it top to bottom in an afternoon.

### Building wlroots from source

```bash
# Dependencies on Arch Linux
sudo pacman -S --needed \
    wayland wayland-protocols libdrm mesa libxkbcommon pixman \
    libinput seatd xorg-xwayland meson ninja cmake

# Dependencies on Debian/Ubuntu
sudo apt install \
    libwayland-dev libwayland-egl1 wayland-protocols \
    libdrm-dev libgles2-mesa-dev libegl-dev libgbm-dev \
    libxkbcommon-dev libpixman-1-dev libinput-dev \
    libseat-dev libxcb-dev libxcb-icccm4-dev \
    libxcb-render-util0-dev meson ninja-build pkg-config

git clone https://gitlab.freedesktop.org/wlroots/wlroots.git
cd wlroots
meson setup build -Dexamples=true -Dbackends=drm,libinput,wayland,x11
ninja -C build

# tinywl is built as part of the examples
ls build/tinywl
```

### Running tinywl

```bash
# Inside an existing Wayland session (nested):
./build/tinywl -s "foot"   # -s launches a startup command

# On a VT (bare metal):
# Ensure you are in the 'seat' or 'video'/'input' groups, or seatd is running
sudo systemctl start seatd
./build/tinywl
```

Inside tinywl, `Alt+F` fullscreens the focused window, `Alt+Q` closes it, and
`Alt+Escape` quits the compositor. Modifier and keybindings are hardcoded — that is
intentional; tinywl is a study example, not a daily driver.

### Reading the source

The tinywl source is at `tinywl/tinywl.c` in the wlroots repository. The key
sections to study, in order:

1. `server_init` — how every protocol and backend is wired up
2. `output_frame` — the render loop
3. `xdg_toplevel_map/unmap` — window lifecycle
4. `cursor_motion` / `process_cursor_motion` — hit testing and focus
5. `keyboard_handle_key` — key dispatch and compositor shortcuts

A heavily commented version of tinywl is maintained at
https://gitlab.freedesktop.org/wlroots/wlroots/-/tree/master/tinywl and the
way-cooler book at https://way-cooler.org/book/ walks through building a similar
compositor step by step (though it targets an older wlroots API, so expect API
changes).

### Checking protocol support at runtime

To verify which protocols your wlroots compositor exposes, use `wayland-info`:

```bash
# Install:
sudo pacman -S wayland-utils   # Arch
sudo apt install wayland-utils  # Debian/Ubuntu

# Run inside the compositor:
wayland-info | grep -E 'zwlr|xdg_|zwp_'
```

Expected output for a full-featured wlroots compositor:

```
interface: 'zwlr_layer_shell_v1',                version:  4
interface: 'xdg_wm_base',                        version:  3
interface: 'zwlr_screencopy_manager_v1',          version:  3
interface: 'zwp_pointer_constraints_v1',          version:  1
interface: 'zwlr_output_manager_v1',              version:  4
interface: 'xdg_output_manager_v1',               version:  3
interface: 'zwp_linux_dmabuf_v1',                 version:  4
```

If `zwlr_layer_shell_v1` is missing, waybar and other layer-shell clients will fail
to start. If `zwp_linux_dmabuf_v1` is missing, hardware video decode will fall back
to CPU copies.


## Troubleshooting

### Compositor fails to start with "failed to open DRM device"

This is a permissions problem. The compositor process needs access to `/dev/dri/cardN`
and `/dev/input/eventN`. The cleanest solution is to use `seatd`:

```bash
sudo pacman -S seatd          # Arch
sudo apt install seatd         # Debian/Ubuntu

sudo systemctl enable --now seatd
sudo usermod -aG seat $USER
# Log out and back in, then retry
```

Alternatively, if you are using systemd-logind:

```bash
# Verify logind is running and your session is active
loginctl session-status
# Should show: State: active   Type: tty

# Set LIBSEAT_BACKEND explicitly
LIBSEAT_BACKEND=logind ./my-compositor
```

### Cursor is invisible or corrupted

Hardware cursor planes are sometimes buggy on certain GPU drivers (especially older
Intel i915 and some NVIDIA drivers in modesetting mode). Disable hardware cursors:

```bash
WLR_NO_HARDWARE_CURSORS=1 ./my-compositor
```

If you are using Sway, add `WLR_NO_HARDWARE_CURSORS=1` to `/etc/environment` or to
`~/.config/sway/config` via `exec_always export WLR_NO_HARDWARE_CURSORS=1`.

### Screen is black, no output rendered

First check `dmesg` for DRM errors:

```bash
dmesg | grep -E 'drm|kms|modeset' | tail -30
```

Common causes:

1. **Wrong GPU selected**: `WLR_DRM_DEVICES=/dev/dri/card1 ./my-compositor` to force
   the correct card.
2. **DPMS state**: The output may be off. Call `wlr_output_enable(output, true)` and
   `wlr_output_commit` in your `new_output` handler.
3. **No mode set**: If `wlr_output.modes` is empty, the EDID could not be read.
   Try `wlr_output_set_custom_mode(output, 1920, 1080, 60000 /* mHz */)`.

### Application uses wrong scale factor

If a HiDPI application renders blurry, check:

```bash
# Inspect output scale being advertised
wayland-info | grep -A5 'wl_output'
```

In your compositor, ensure you call:

```c
wlr_output_set_scale(output, 2.0);  // for a 2x HiDPI display
wlr_output_commit(output);
```

And that `xdg_output_manager_v1` is initialised so clients can read logical geometry:

```c
wlr_xdg_output_manager_v1_create(wl_display, output_layout);
```

### XWayland windows do not appear

Verify XWayland is initialised and `DISPLAY` is exported before clients start:

```bash
# Inside compositor: check that Xwayland is running
pgrep -a Xwayland
# Should show: Xwayland :1 -rootless -terminate ...
```

If XWayland crashes immediately, run it manually with `WAYLAND_DEBUG=1` to see
protocol errors:

```bash
WAYLAND_DEBUG=1 Xwayland :99 -rootless 2>&1 | head -50
```

### Debugging wlroots internals

wlroots uses the `wlr_log` system. Enable verbose logging by setting:

```bash
WLR_LOG_FILE=/tmp/wlroots.log WLR_LOG_VERBOSITY=debug ./my-compositor
```

Log levels are `silent`, `error`, `info`, `debug`. The `debug` level is very verbose
(every event and object lifecycle) and is invaluable when tracking down protocol
errors or renderer crashes.

For protocol-level debugging, `WAYLAND_DEBUG=1` on the client side prints every
request and event, which helps correlate client behaviour with compositor logs.

```bash
# Launch foot with full Wayland debug output
WAYLAND_DEBUG=1 foot 2>&1 | grep -v wl_surface | less
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
