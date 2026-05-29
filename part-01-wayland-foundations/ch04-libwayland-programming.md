# Chapter 4 — libwayland Programming: Writing Wayland Clients in C

## Overview

This chapter provides a hands-on, from-scratch guide to writing Wayland clients using
`libwayland-client`. Rather than relying on a toolkit like GTK or Qt to abstract the
protocol, you will directly call the wire-level C API, giving you complete control over
every surface, buffer, and event. This is the foundation for understanding how all
higher-level Wayland software ultimately works, and it is an essential skill for ricing
at the protocol level — writing custom bars, overlays, wallpaper daemons, or lock screens.

The chapter follows a single progressive example: a minimal window that renders colored
pixels using shared memory, responds to keyboard events, and eventually evolves into a
functional clock bar using the `wlr-layer-shell` protocol. Every code snippet is complete
and compilable; headers and linking flags are explicit throughout. By the end you will
understand the complete client lifecycle from `wl_display_connect()` to `wl_display_disconnect()`.

Cross-references: See Ch 2 for the Wayland wire protocol internals that underpin everything
here. See Ch 73 for the Rust
`wayland-client` crate if you prefer a memory-safe alternative. See Ch 53 for session
startup and how `WAYLAND_DISPLAY` gets set in your login environment.

---

## 4.1 Setting Up the Build Environment

Before writing a single line of client code you need the correct development headers,
protocol XML files, and build system integration. On Arch Linux the relevant packages are
`wayland`, `wayland-protocols`, `libxkbcommon`, and `pkg-config`. On Debian/Ubuntu they
are named `libwayland-dev`, `wayland-protocols`, `libxkbcommon-dev`, and `pkgconf`. Fedora
users want `wayland-devel`, `wayland-protocols-devel`, `libxkbcommon-devel`.

```bash
# Arch
sudo pacman -S wayland wayland-protocols libxkbcommon pkg-config meson ninja

# Debian/Ubuntu
sudo apt install libwayland-dev wayland-protocols libxkbcommon-dev \
    pkg-config meson ninja-build

# Fedora
sudo dnf install wayland-devel wayland-protocols-devel libxkbcommon-devel \
    pkgconf meson ninja-build
```

The `wayland-protocols` package installs stable and unstaged protocol XML files under
`/usr/share/wayland-protocols/`. Check which protocols are available:

```bash
find /usr/share/wayland-protocols -name '*.xml' | sort
```

The `wayland-scanner` tool converts XML protocol definitions into C header/source pairs.
It ships with the `wayland` package itself. There are two output modes:

| Mode | Command flag | Output |
|------|-------------|--------|
| Client header | `client-header` | `protocol-name-client-protocol.h` |
| Private code | `private-code` | `protocol-name-protocol.c` |
| Public code (deprecated) | `code` | Avoid; use `private-code` |

A typical Meson `meson.build` that handles this automatically:

```meson
project('my-wayland-client', 'c',
  version: '0.1',
  default_options: ['c_std=c11', 'warning_level=2'])

wayland_client = dependency('wayland-client')
wayland_protocols = dependency('wayland-protocols')
xkbcommon = dependency('xkbcommon')

wayland_scanner_dep = dependency('wayland-scanner', native: true)
wayland_scanner = find_program(
  wayland_scanner_dep.get_variable(pkgconfig: 'wayland_scanner'))

wl_protocols_dir = wayland_protocols.get_variable(pkgconfig: 'pkgdatadir')

# Generate xdg-shell bindings from the stable protocol XML
xdg_shell_xml = wl_protocols_dir / 'stable/xdg-shell/xdg-shell.xml'

xdg_shell_client_h = custom_target('xdg-shell-client-header',
  input:   xdg_shell_xml,
  output:  'xdg-shell-client-protocol.h',
  command: [wayland_scanner, 'client-header', '@INPUT@', '@OUTPUT@'])

xdg_shell_c = custom_target('xdg-shell-private-code',
  input:   xdg_shell_xml,
  output:  'xdg-shell-protocol.c',
  command: [wayland_scanner, 'private-code', '@INPUT@', '@OUTPUT@'])

# Layer shell (wlroots extension protocol, vendor-supplied)
layer_shell_xml = 'protocols/wlr-layer-shell-unstable-v1.xml'

layer_shell_client_h = custom_target('layer-shell-client-header',
  input:   layer_shell_xml,
  output:  'wlr-layer-shell-client-protocol.h',
  command: [wayland_scanner, 'client-header', '@INPUT@', '@OUTPUT@'])

layer_shell_c = custom_target('layer-shell-private-code',
  input:   layer_shell_xml,
  output:  'wlr-layer-shell-protocol.c',
  command: [wayland_scanner, 'private-code', '@INPUT@', '@OUTPUT@'])

executable('my-client',
  sources: [
    'src/main.c',
    xdg_shell_c,
    layer_shell_c,
  ],
  dependencies: [wayland_client, xkbcommon],
  include_directories: include_directories('.'))
```

Non-standard protocols like `wlr-layer-shell` are not in the system `wayland-protocols`
package. Download them directly from the wlroots repository:

```bash
mkdir -p protocols
curl -o protocols/wlr-layer-shell-unstable-v1.xml \
  https://gitlab.freedesktop.org/wlroots/wlr-protocols/-/raw/master/unstable/wlr-layer-shell-unstable-v1.xml
```

For quick one-off compilation without Meson, `pkg-config` provides the exact flags:

```bash
cc -o myclient main.c xdg-shell-protocol.c \
    $(pkg-config --cflags --libs wayland-client xkbcommon) \
    -Wall -Wextra -std=c11
```

---

## 4.2 Connecting to the Compositor

The entry point for every Wayland client is `wl_display_connect()`. This function opens
a Unix domain socket to the compositor whose path is constructed from `$XDG_RUNTIME_DIR`
and `$WAYLAND_DISPLAY`. If `WAYLAND_DISPLAY` is unset it defaults to `wayland-0`. The
function returns `NULL` on failure — always check it.

```c
#include <stdio.h>
#include <stdlib.h>
#include <wayland-client.h>

int main(void) {
    struct wl_display *display = wl_display_connect(NULL);
    if (!display) {
        fprintf(stderr, "Failed to connect to Wayland compositor\n");
        return 1;
    }
    printf("Connected to compositor on: %s/%s\n",
           getenv("XDG_RUNTIME_DIR"), getenv("WAYLAND_DISPLAY") ?: "wayland-0");

    /* ... application logic ... */

    wl_display_disconnect(display);
    return 0;
}
```

The event queue is the beating heart of the client. `wl_display_dispatch()` reads events
from the socket and dispatches them to registered listeners synchronously in the calling
thread. It blocks if no events are available. For non-blocking behaviour use
`wl_display_dispatch_pending()` after priming the queue with
`wl_display_prepare_read()` / `wl_display_read_events()` on a background thread. For
simple single-threaded clients the plain dispatch loop suffices:

```c
while (wl_display_dispatch(display) != -1) {
    /* listeners are called from here */
}
```

`wl_display_roundtrip()` sends a `wl_display.sync` request and blocks until the compositor
acknowledges it. Any events queued before the sync are dispatched synchronously. This is
essential during startup: after binding global objects (see §4.3), you call roundtrip to
ensure the compositor has processed your binding requests and sent back any initial events
before you proceed:

```c
/* After registry binds — wait for compositor to process them */
wl_display_roundtrip(display);
```

Error handling: `wl_display_get_error()` returns the last error code (an errno value for
connection errors, or a protocol error code for Wayland-level errors).
`wl_display_get_protocol_error()` provides the interface, error code, and object ID
involved in a protocol violation. Always wrap your main loop:

```c
int ret;
while ((ret = wl_display_dispatch(display)) != -1)
    ;
if (ret == -1) {
    uint32_t ec;
    const struct wl_interface *iface;
    uint32_t id;
    int err = wl_display_get_error(display);
    if (err == EPROTO) {
        ec = wl_display_get_protocol_error(display, &iface, &id);
        fprintf(stderr, "Protocol error %u on %s@%u\n",
                ec, iface ? iface->name : "unknown", id);
    } else {
        fprintf(stderr, "Connection error: %s\n", strerror(err));
    }
}
```

---

## 4.3 The Registry Dance

The Wayland global registry is how clients discover what interfaces the compositor
provides. When you bind the `wl_registry`, the compositor immediately fires a `global`
event for every available interface, listing its name (an opaque `uint32_t` ID), interface
string, and version. You store the names you care about and bind them with
`wl_registry_bind()`. When a global disappears (e.g., a monitor is unplugged), a
`global_remove` event fires.

```c
#include <string.h>
#include <wayland-client.h>
#include "xdg-shell-client-protocol.h"

struct client_state {
    struct wl_display    *display;
    struct wl_registry   *registry;
    struct wl_compositor *compositor;
    struct wl_shm        *shm;
    struct xdg_wm_base   *xdg_wm_base;
    struct wl_seat       *seat;
    struct wl_output     *output;
};

static void registry_handle_global(void *data,
    struct wl_registry *registry,
    uint32_t name,
    const char *interface,
    uint32_t version)
{
    struct client_state *state = data;

    if (strcmp(interface, wl_compositor_interface.name) == 0) {
        state->compositor = wl_registry_bind(registry, name,
            &wl_compositor_interface, 4);
    } else if (strcmp(interface, wl_shm_interface.name) == 0) {
        state->shm = wl_registry_bind(registry, name,
            &wl_shm_interface, 1);
    } else if (strcmp(interface, xdg_wm_base_interface.name) == 0) {
        state->xdg_wm_base = wl_registry_bind(registry, name,
            &xdg_wm_base_interface, 1);
    } else if (strcmp(interface, wl_seat_interface.name) == 0) {
        state->seat = wl_registry_bind(registry, name,
            &wl_seat_interface, 7);
    } else if (strcmp(interface, wl_output_interface.name) == 0 &&
               !state->output) {
        /* Bind the first output only for now */
        state->output = wl_registry_bind(registry, name,
            &wl_output_interface, 4);
    }
}

static void registry_handle_global_remove(void *data,
    struct wl_registry *registry,
    uint32_t name)
{
    /* Handle dynamic removal — important for output hotplug */
    (void)data; (void)registry; (void)name;
}

static const struct wl_registry_listener registry_listener = {
    .global        = registry_handle_global,
    .global_remove = registry_handle_global_remove,
};

/* In main(): */
state.registry = wl_display_get_registry(state.display);
wl_registry_add_listener(state.registry, &registry_listener, &state);
wl_display_roundtrip(state.display);  /* collect all globals */

if (!state.compositor || !state.shm || !state.xdg_wm_base) {
    fprintf(stderr, "Compositor missing required globals\n");
    return 1;
}
```

Version negotiation is critical: `wl_registry_bind()` takes a version argument. You
should request the minimum version you need, not the maximum the compositor advertises.
Requesting a version the compositor does not support results in an immediate protocol
error. A safe pattern: `MIN(advertised_version, your_max_supported_version)`. Store the
advertised version in your registry handler if you need runtime capability checks.

Common globals and recommended bind versions:

| Interface | Typical version | Purpose |
|-----------|----------------|---------|
| `wl_compositor` | 4 | Surface creation |
| `wl_shm` | 1 | Shared memory buffers |
| `xdg_wm_base` | 2 | Toplevel windows |
| `wl_seat` | 7 | Input devices |
| `wl_output` | 4 | Monitor information |
| `zwlr_layer_shell_v1` | 4 | Bars, overlays |
| `wp_viewporter` | 1 | Scaling/cropping |
| `wp_fractional_scale_v1` | 1 | HiDPI fractional scaling |
| `zxdg_output_manager_v1` | 3 | Logical output geometry |

---

## 4.4 Creating a Surface and Window

A `wl_surface` is the fundamental rendering unit in Wayland. It represents a rectangular
region of pixels in the compositor's scene graph. On its own it has no position or role.
To become a visible window it must be given a role. For regular application windows, the
role is `xdg_toplevel` via the XDG shell protocol. For panels and overlays, the role is
`zwlr_layer_surface_v1` (covered in §4.7).

```c
/* Create a bare wl_surface */
state->surface = wl_compositor_create_surface(state->compositor);

/* Wrap it in an xdg_surface to participate in XDG shell lifecycle */
state->xdg_surface = xdg_wm_base_get_xdg_surface(state->xdg_wm_base,
                                                   state->surface);
xdg_surface_add_listener(state->xdg_surface, &xdg_surface_listener, state);

/* Give it the toplevel role (resizable application window) */
state->xdg_toplevel = xdg_surface_get_toplevel(state->xdg_surface);
xdg_toplevel_add_listener(state->xdg_toplevel, &xdg_toplevel_listener, state);

/* Metadata */
xdg_toplevel_set_title(state->xdg_toplevel, "My Wayland Client");
xdg_toplevel_set_app_id(state->xdg_toplevel, "com.example.myclient");
xdg_toplevel_set_min_size(state->xdg_toplevel, 200, 150);

/* Commit the surface to trigger the initial configure event */
wl_surface_commit(state->surface);
wl_display_roundtrip(state->display);
```

The XDG shell configure/ack dance is mandatory. The compositor sends a `configure` event
specifying the desired size and state flags (maximized, fullscreen, activated, etc.). You
must respond with `xdg_surface_ack_configure()` using the serial from the configure event,
then render a frame and commit the surface. Failing to ack causes the compositor to
withhold displaying your window.

```c
static void xdg_surface_handle_configure(void *data,
    struct xdg_surface *xdg_surface,
    uint32_t serial)
{
    struct client_state *state = data;
    xdg_surface_ack_configure(xdg_surface, serial);
    /* Now safe to render and commit */
    render_frame(state);
}

static const struct xdg_surface_listener xdg_surface_listener = {
    .configure = xdg_surface_handle_configure,
};

static void xdg_toplevel_handle_configure(void *data,
    struct xdg_toplevel *toplevel,
    int32_t width, int32_t height,
    struct wl_array *states)
{
    struct client_state *state = data;
    /* width/height == 0 means "pick your own size" */
    if (width > 0)  state->width  = width;
    if (height > 0) state->height = height;
    /* Inspect states for maximized/fullscreen if needed */
}

static void xdg_toplevel_handle_close(void *data,
    struct xdg_toplevel *toplevel)
{
    struct client_state *state = data;
    state->running = false;
}

static const struct xdg_toplevel_listener xdg_toplevel_listener = {
    .configure = xdg_toplevel_handle_configure,
    .close     = xdg_toplevel_handle_close,
};
```

To respond to `wl_output` scale changes (HiDPI), listen on `wl_surface.preferred_buffer_scale`
(available from `wl_surface` version 6) and set the buffer scale accordingly:

```c
wl_surface_set_buffer_scale(state->surface, state->scale);
/* Render at width*scale x height*scale, display at width x height */
```

---

## 4.5 Shared Memory Rendering with wl_shm

`wl_shm` is the simplest way to present pixels: you allocate a chunk of shared memory,
write pixel data into it from the CPU, and hand a `wl_buffer` wrapping that memory to the
compositor. No GPU is involved. Performance is adequate for static or text-heavy UIs; for
animated content, EGL/Vulkan (Ch 5) is more appropriate.

The preferred approach on Linux is `memfd_create()`, which avoids the `/tmp`-based shm
files that are vulnerable to races and require cleanup:

```c
#include <sys/mman.h>
#include <fcntl.h>
#include <unistd.h>

static int create_shm_file(size_t size) {
    int fd = memfd_create("wl-shm", MFD_CLOEXEC | MFD_ALLOW_SEALING);
    if (fd < 0) {
        /* Fallback: POSIX shm */
        char name[64];
        snprintf(name, sizeof(name), "/wl-shm-XXXXXX");
        /* mkstemp-style: not shown for brevity */
        return -1;
    }
    if (ftruncate(fd, (off_t)size) < 0) {
        close(fd);
        return -1;
    }
    return fd;
}
```

With the fd in hand, create the pool and buffers. A double-buffer setup allocates two
buffers in a single pool so the compositor can display one while you write to the other:

```c
#define WIDTH  800
#define HEIGHT 600
#define STRIDE (WIDTH * 4)          /* 4 bytes per pixel: ARGB8888 */
#define POOL_SIZE (STRIDE * HEIGHT * 2)  /* two buffers */

struct shm_state {
    int      fd;
    void    *data;
    struct wl_shm_pool *pool;
    struct wl_buffer   *buffers[2];
    int      current;               /* which buffer is being written */
};

static void shm_init(struct shm_state *shm, struct wl_shm *wl_shm) {
    shm->fd   = create_shm_file(POOL_SIZE);
    shm->data = mmap(NULL, POOL_SIZE, PROT_READ | PROT_WRITE,
                     MAP_SHARED, shm->fd, 0);

    shm->pool = wl_shm_create_pool(wl_shm, shm->fd, POOL_SIZE);

    /* Buffer 0: offset 0; Buffer 1: offset STRIDE*HEIGHT */
    shm->buffers[0] = wl_shm_pool_create_buffer(shm->pool,
        0,                      /* offset */
        WIDTH, HEIGHT, STRIDE,
        WL_SHM_FORMAT_XRGB8888);
    shm->buffers[1] = wl_shm_pool_create_buffer(shm->pool,
        STRIDE * HEIGHT,
        WIDTH, HEIGHT, STRIDE,
        WL_SHM_FORMAT_XRGB8888);

    shm->current = 0;
}
```

Rendering into the buffer and submitting it:

```c
static void render_frame(struct client_state *state) {
    struct shm_state *shm = &state->shm;
    int idx    = shm->current;
    uint32_t *pixels = (uint32_t *)((char *)shm->data + idx * STRIDE * HEIGHT);

    /* Fill with a solid color: XRGB 0x002244 (dark blue) */
    for (int y = 0; y < HEIGHT; y++)
        for (int x = 0; x < WIDTH; x++)
            pixels[y * WIDTH + x] = 0xFF002244;

    /* Attach the buffer to the surface */
    wl_surface_attach(state->surface, shm->buffers[idx], 0, 0);
    /* Mark the entire surface as damaged */
    wl_surface_damage_buffer(state->surface, 0, 0, WIDTH, HEIGHT);
    wl_surface_commit(state->surface);

    /* Flip */
    shm->current ^= 1;
}
```

Frame callbacks ensure you only render when the compositor is ready, preventing tearing
and wasted CPU on invisible windows:

```c
static void frame_callback_done(void *data,
    struct wl_callback *callback,
    uint32_t time)
{
    struct client_state *state = data;
    wl_callback_destroy(callback);
    state->frame_callback = NULL;
    render_frame_with_callback(state);  /* schedule next frame */
}

static const struct wl_callback_listener frame_listener = {
    .done = frame_callback_done,
};

static void render_frame_with_callback(struct client_state *state) {
    /* ... write pixels ... */
    state->frame_callback = wl_surface_frame(state->surface);
    wl_callback_add_listener(state->frame_callback, &frame_listener, state);
    wl_surface_attach(state->surface, shm->buffers[idx], 0, 0);
    wl_surface_damage_buffer(state->surface, 0, 0, WIDTH, HEIGHT);
    wl_surface_commit(state->surface);
    shm->current ^= 1;
}
```

Common pixel formats and their `wl_shm_format` constants:

| Format | Constant | Bytes/pixel | Notes |
|--------|----------|-------------|-------|
| ARGB pre-multiplied | `WL_SHM_FORMAT_ARGB8888` | 4 | Most common for compositing |
| XRGB (opaque) | `WL_SHM_FORMAT_XRGB8888` | 4 | No alpha; slightly faster |
| ABGR | `WL_SHM_FORMAT_ABGR8888` | 4 | For some Cairo surfaces |
| RGB565 | `WL_SHM_FORMAT_RGB565` | 2 | Embedded / low-memory |

Query supported formats at runtime by listening on `wl_shm.format` events before creating
any buffers. XRGB8888 and ARGB8888 are mandated by the protocol; everything else is optional.

---

## 4.6 Input Handling

Input in Wayland is mediated through `wl_seat`, which represents a group of input devices
(a logical user — one keyboard, one pointer, optionally one touch surface). You bind the
seat from the registry, then obtain individual device objects from it.

```c
static void seat_handle_capabilities(void *data,
    struct wl_seat *seat,
    uint32_t capabilities)
{
    struct client_state *state = data;

    if (capabilities & WL_SEAT_CAPABILITY_KEYBOARD) {
        state->keyboard = wl_seat_get_keyboard(seat);
        wl_keyboard_add_listener(state->keyboard, &keyboard_listener, state);
    }
    if (capabilities & WL_SEAT_CAPABILITY_POINTER) {
        state->pointer = wl_seat_get_pointer(seat);
        wl_pointer_add_listener(state->pointer, &pointer_listener, state);
    }
}

static const struct wl_seat_listener seat_listener = {
    .capabilities = seat_handle_capabilities,
    .name         = NULL,  /* optional: compositor seat name */
};
```

Keyboard handling via XKB: the compositor sends a keymap file descriptor, which you pass
to `xkbcommon` to interpret key symbols. This handles the full complexity of international
layouts, modifier states, and dead keys without you implementing any of it:

```c
#include <xkbcommon/xkbcommon.h>
#include <sys/mman.h>

struct kb_state {
    struct xkb_context *ctx;
    struct xkb_keymap  *keymap;
    struct xkb_state   *state;
};

static void keyboard_handle_keymap(void *data,
    struct wl_keyboard *keyboard,
    uint32_t format,
    int32_t  fd,
    uint32_t size)
{
    struct client_state *cs = data;
    if (format != WL_KEYBOARD_KEYMAP_FORMAT_XKB_V1) { close(fd); return; }

    char *map_str = mmap(NULL, size, PROT_READ, MAP_PRIVATE, fd, 0);
    close(fd);

    cs->kb.ctx    = xkb_context_new(XKB_CONTEXT_NO_FLAGS);
    cs->kb.keymap = xkb_keymap_new_from_string(cs->kb.ctx, map_str,
        XKB_KEYMAP_FORMAT_TEXT_V1, XKB_KEYMAP_COMPILE_NO_FLAGS);
    cs->kb.state  = xkb_state_new(cs->kb.keymap);
    munmap(map_str, size);
}

static void keyboard_handle_key(void *data,
    struct wl_keyboard *keyboard,
    uint32_t serial, uint32_t time,
    uint32_t key, uint32_t key_state)
{
    struct client_state *cs = data;
    if (key_state != WL_KEYBOARD_KEY_STATE_PRESSED) return;

    /* key is a Linux evdev scancode; add 8 for XKB */
    xkb_keysym_t sym = xkb_state_key_get_one_sym(cs->kb.state, key + 8);

    char buf[32];
    xkb_keysym_get_name(sym, buf, sizeof(buf));
    printf("Key pressed: %s (sym 0x%x)\n", buf, sym);

    if (sym == XKB_KEY_q || sym == XKB_KEY_Escape)
        cs->running = false;
}

static void keyboard_handle_modifiers(void *data,
    struct wl_keyboard *keyboard,
    uint32_t serial,
    uint32_t mods_depressed,
    uint32_t mods_latched,
    uint32_t mods_locked,
    uint32_t group)
{
    struct client_state *cs = data;
    xkb_state_update_mask(cs->kb.state,
        mods_depressed, mods_latched, mods_locked,
        0, 0, group);
}

static const struct wl_keyboard_listener keyboard_listener = {
    .keymap     = keyboard_handle_keymap,
    .enter      = NULL,  /* surface received keyboard focus */
    .leave      = NULL,
    .key        = keyboard_handle_key,
    .modifiers  = keyboard_handle_modifiers,
    .repeat_info = NULL,
};
```

Pointer events follow a begin/update/end pattern. `enter` fires when the pointer moves
into your surface, providing the surface-local coordinates. `motion` gives continuous
position updates. `button` gives press/release with the Linux button code:

```c
static void pointer_handle_motion(void *data,
    struct wl_pointer *pointer,
    uint32_t time,
    wl_fixed_t x, wl_fixed_t y)
{
    struct client_state *cs = data;
    cs->mouse_x = wl_fixed_to_double(x);
    cs->mouse_y = wl_fixed_to_double(y);
}

static void pointer_handle_button(void *data,
    struct wl_pointer *pointer,
    uint32_t serial, uint32_t time,
    uint32_t button, uint32_t state)
{
    /* button: BTN_LEFT=0x110, BTN_RIGHT=0x111, BTN_MIDDLE=0x112 */
    if (button == BTN_LEFT && state == WL_POINTER_BUTTON_STATE_PRESSED)
        printf("Left click at (%.1f, %.1f)\n",
               ((struct client_state *)data)->mouse_x,
               ((struct client_state *)data)->mouse_y);
}
```

---

## 4.7 Using the Layer Shell (wlr-layer-shell)

The `wlr-layer-shell-unstable-v1` protocol is the standard mechanism for creating desktop
UI elements that float above or below regular windows: taskbars, notification daemons,
wallpaper renderers, lock screens, and screenshot overlays. It is supported by wlroots-based
compositors (Sway, Hyprland, river, niri) and by KWin since Plasma 6. GNOME Shell has
partial support via a compatibility shim.

A layer surface replaces the `xdg_toplevel` role on a `wl_surface`. Instead of
`xdg_wm_base_get_xdg_surface()` you call `zwlr_layer_shell_v1_get_layer_surface()`:

```c
#include "wlr-layer-shell-client-protocol.h"

static void create_layer_surface(struct client_state *state) {
    state->layer_surface = zwlr_layer_shell_v1_get_layer_surface(
        state->layer_shell,
        state->surface,
        state->output,                          /* NULL = current output */
        ZWLR_LAYER_SHELL_V1_LAYER_TOP,          /* layer */
        "my-bar");                              /* namespace */

    zwlr_layer_surface_v1_add_listener(state->layer_surface,
        &layer_surface_listener, state);

    /* Anchor to top edge, full width */
    zwlr_layer_surface_v1_set_anchor(state->layer_surface,
        ZWLR_LAYER_SURFACE_V1_ANCHOR_TOP |
        ZWLR_LAYER_SURFACE_V1_ANCHOR_LEFT |
        ZWLR_LAYER_SURFACE_V1_ANCHOR_RIGHT);

    /* 30px tall; width is determined by anchoring */
    zwlr_layer_surface_v1_set_size(state->layer_surface, 0, 30);

    /* Reserve 30px at the top so windows don't overlap the bar */
    zwlr_layer_surface_v1_set_exclusive_zone(state->layer_surface, 30);

    /* Margin from screen edges */
    zwlr_layer_surface_v1_set_margin(state->layer_surface, 4, 4, 0, 4);

    /* No keyboard input for a status bar */
    zwlr_layer_surface_v1_set_keyboard_interactivity(state->layer_surface,
        ZWLR_LAYER_SURFACE_V1_KEYBOARD_INTERACTIVITY_NONE);

    wl_surface_commit(state->surface);
    wl_display_roundtrip(state->display);
}
```

The four available layers and their typical use cases:

| Layer constant | Value | Use case |
|----------------|-------|----------|
| `LAYER_BACKGROUND` | 0 | Wallpaper renderers |
| `LAYER_BOTTOM` | 1 | Desktop icons, bottom decorations |
| `LAYER_TOP` | 2 | Status bars, docks (typical choice) |
| `LAYER_OVERLAY` | 3 | Lock screens, screenshot overlays, OSD |

The `configure` event for a layer surface provides the actual width/height the compositor
assigned (since you may have set one dimension to 0 to mean "fill"):

```c
static void layer_surface_handle_configure(void *data,
    struct zwlr_layer_surface_v1 *surface,
    uint32_t serial,
    uint32_t width, uint32_t height)
{
    struct client_state *state = data;
    state->width  = (int)width;
    state->height = (int)height;
    zwlr_layer_surface_v1_ack_configure(surface, serial);
    render_frame(state);
}

static void layer_surface_handle_closed(void *data,
    struct zwlr_layer_surface_v1 *surface)
{
    ((struct client_state *)data)->running = false;
}

static const struct zwlr_layer_surface_v1_listener layer_surface_listener = {
    .configure = layer_surface_handle_configure,
    .closed    = layer_surface_handle_closed,
};
```

For a lock screen, use `LAYER_OVERLAY` with full-screen size and
`KEYBOARD_INTERACTIVITY_EXCLUSIVE` so all input is captured:

```c
zwlr_layer_surface_v1_set_size(layer_surface, 0, 0);  /* fill output */
zwlr_layer_surface_v1_set_exclusive_zone(layer_surface, -1); /* cover everything */
zwlr_layer_surface_v1_set_keyboard_interactivity(layer_surface,
    ZWLR_LAYER_SURFACE_V1_KEYBOARD_INTERACTIVITY_EXCLUSIVE);
```

---

## 4.8 Building a Minimal Status Bar in C

This section ties all previous sections together into a working clock bar: a 30-pixel
strip anchored to the top of the screen that displays the current time, updates every
second, uses Cairo/Pango for text rendering, and exits cleanly on Ctrl+C.

First, add the Cairo and Pango dependencies to `meson.build`:

```meson
cairo  = dependency('cairo')
pango  = dependency('pango')
pangocairo = dependency('pangocairo')

executable('clockbar',
  sources: ['clockbar.c', xdg_shell_c, layer_shell_c],
  dependencies: [wayland_client, xkbcommon, cairo, pango, pangocairo])
```

The rendering function using Cairo on the shm buffer:

```c
#include <cairo/cairo.h>
#include <pango/pangocairo.h>
#include <time.h>

static void render_clock(struct client_state *state) {
    struct shm_state *shm = &state->shm;
    int idx = shm->current;
    int W = state->width, H = state->height;
    int stride = W * 4;

    /* Wrap the shm buffer in a Cairo surface */
    unsigned char *pixels = (unsigned char *)shm->data + idx * stride * H;
    cairo_surface_t *cs = cairo_image_surface_create_for_data(
        pixels, CAIRO_FORMAT_ARGB32, W, H, stride);
    cairo_t *cr = cairo_create(cs);

    /* Background: semi-transparent dark */
    cairo_set_source_rgba(cr, 0.1, 0.1, 0.1, 0.9);
    cairo_paint(cr);

    /* Current time as string */
    time_t now = time(NULL);
    char tbuf[64];
    strftime(tbuf, sizeof(tbuf), "%a %d %b  %H:%M:%S", localtime(&now));

    /* Pango layout for font rendering */
    PangoLayout *layout = pango_cairo_create_layout(cr);
    PangoFontDescription *font = pango_font_description_from_string(
        "Noto Sans Mono 11");
    pango_layout_set_font_description(layout, font);
    pango_font_description_free(font);
    pango_layout_set_text(layout, tbuf, -1);

    /* Measure and right-align */
    int text_w, text_h;
    pango_layout_get_pixel_size(layout, &text_w, &text_h);
    cairo_move_to(cr, W - text_w - 8, (H - text_h) / 2.0);

    cairo_set_source_rgba(cr, 0.9, 0.9, 0.9, 1.0);
    pango_cairo_show_layout(cr, layout);

    g_object_unref(layout);
    cairo_destroy(cr);
    cairo_surface_destroy(cs);

    /* Submit */
    wl_surface_attach(state->surface, shm->buffers[idx], 0, 0);
    wl_surface_damage_buffer(state->surface, 0, 0, W, H);

    /* Request next frame callback */
    state->frame_callback = wl_surface_frame(state->surface);
    wl_callback_add_listener(state->frame_callback, &frame_listener, state);

    wl_surface_commit(state->surface);
    shm->current ^= 1;
}
```

Integrating `wl_output` geometry for multi-monitor setups: listen for `wl_output.geometry`
and `wl_output.mode` events to know each output's resolution. Create one
`zwlr_layer_surface_v1` per output, passing the specific `wl_output` object:

```c
struct output_entry {
    struct wl_output   *output;
    uint32_t            name;       /* registry name for removal */
    int32_t             width, height;
    struct wl_list      link;
};

/* In registry_handle_global, for each wl_output: */
struct output_entry *entry = calloc(1, sizeof(*entry));
entry->name   = name;
entry->output = wl_registry_bind(registry, name, &wl_output_interface, 4);
wl_output_add_listener(entry->output, &output_listener, entry);
wl_list_insert(&state->outputs, &entry->link);
```

Then during `registry_handle_global_remove`, find the entry by name, destroy its layer
surface, and free it. This keeps the bar present on all connected monitors and cleanly
handles hotplug.

Signal handling for clean shutdown — install a `SIGTERM`/`SIGINT` handler that sets the
`running` flag:

```c
#include <signal.h>
static volatile sig_atomic_t running = 1;
static void handle_signal(int sig) { running = 0; }

/* In main(): */
signal(SIGINT,  handle_signal);
signal(SIGTERM, handle_signal);

while (running && wl_display_dispatch(state.display) != -1)
    ;
```

---

## Troubleshooting

**`wl_display_connect()` returns NULL**
Verify `$WAYLAND_DISPLAY` is set (`echo $WAYLAND_DISPLAY`) and the socket exists:
`ls -la $XDG_RUNTIME_DIR/`. If running from a TTY without a Wayland session, start one
first. If the variable is set but the socket is missing, the compositor crashed or was not
started with that socket name.

**Protocol error "invalid object" or "version too new"**
You requested a higher version than the compositor supports in `wl_registry_bind()`. Add
version clamping: `MIN(advertised_version, MY_MAX_VERSION)`. Print all globals at startup
to diagnose:
```c
static void registry_handle_global(...) {
    printf("  global: %s version %u name %u\n", interface, version, name);
    /* ... */
}
```

**Surface is never mapped / window doesn't appear**
You forgot to call `wl_surface_commit()` after setting up the xdg_surface, or you forgot
to ack the configure event before the first commit. Add `wl_display_roundtrip()` after
attaching and committing to force synchronous processing while debugging.

**Shared memory buffer shows garbage or crashes**
Ensure `ftruncate()` succeeded before `mmap()`. Verify you are writing to the correct
offset when double buffering (`idx * STRIDE * HEIGHT`). Check the stride: always
`width * bytes_per_pixel`, not `width * 3` for ARGB.

**Layer shell surface not appearing on the correct monitor**
Pass the specific `wl_output *` rather than `NULL` to `zwlr_layer_shell_v1_get_layer_surface()`.
Wait for at least one `wl_display_roundtrip()` after binding the output before using it.

**Keyboard events not arriving**
The surface must have keyboard focus. For layer shell surfaces, set
`KEYBOARD_INTERACTIVITY_ON_DEMAND` and ensure the surface has been entered. For xdg_toplevel
windows, click on the window first. Check that `wl_seat_get_keyboard()` was called after
the `capabilities` event confirmed `WL_SEAT_CAPABILITY_KEYBOARD`.

**High CPU usage / spinning without vsync**
You are not using frame callbacks. Without them, `wl_display_dispatch()` returns
immediately and you render as fast as possible. Always gate rendering on the `wl_callback.done`
event (see §4.5).

---

## Code Repository

Full, compilable source code for all examples in this chapter is maintained at:
`https://github.com/jreuben11/wayland-ricing-bible-examples` under `ch04/`.

Each example has its own `meson.build` and can be built with:

```bash
meson setup build && ninja -C build
./build/myclient
```

See Ch 5 for EGL/OpenGL rendering as an alternative to `wl_shm`. See Ch 7 for advanced
`xkbcommon` usage (compose keys, dead keys, per-seat layouts). See Ch 9 for the
`wp_presentation` protocol for precise frame timing. See Ch 53 for configuring
`WAYLAND_DISPLAY` and `XDG_RUNTIME_DIR` in session startup scripts.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
