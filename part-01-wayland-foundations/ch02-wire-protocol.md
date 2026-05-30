# Chapter 2 — The Wire Protocol: Messages, Objects, and Interfaces

## Contents

- [Overview](#overview)
- [2.1 The Unix Socket Transport](#21-the-unix-socket-transport)
  - [Binary Header Format](#binary-header-format)
  - [Argument Types](#argument-types)
  - [Inspecting the Socket](#inspecting-the-socket)
- [2.2 The Object Model](#22-the-object-model)
  - [The `wl_display` Root Object](#the-wldisplay-root-object)
  - [Interface Versioning](#interface-versioning)
- [2.3 Requests and Events](#23-requests-and-events)
  - [`wl_display.sync` and Roundtrip Semantics](#wldisplaysync-and-roundtrip-semantics)
- [2.4 The Global Registry Pattern](#24-the-global-registry-pattern)
  - [Complete Global Enumeration Example (C)](#complete-global-enumeration-example-c)
  - [Binding a Global](#binding-a-global)
- [2.5 Surfaces and the Rendering Pipeline](#25-surfaces-and-the-rendering-pipeline)
  - [`wl_buffer`: Attaching Pixel Data](#wlbuffer-attaching-pixel-data)
  - [`wl_shm` Buffer from Scratch](#wlshm-buffer-from-scratch)
  - [Commit Semantics: Double-Buffered State](#commit-semantics-double-buffered-state)
  - [Frame Callbacks: Pacing Rendering to Vsync](#frame-callbacks-pacing-rendering-to-vsync)
  - [Damage Tracking: Partial Surface Updates](#damage-tracking-partial-surface-updates)
- [2.6 Debugging the Wire Protocol](#26-debugging-the-wire-protocol)
  - [`WAYLAND_DEBUG`](#waylanddebug)
  - [`wldbg` — Interactive Protocol Debugger](#wldbg-interactive-protocol-debugger)
  - [`weston-info` and `wayland-info`](#weston-info-and-wayland-info)
  - [Decoding Hex Dumps](#decoding-hex-dumps)
  - [Protocol Error Messages](#protocol-error-messages)
- [Troubleshooting](#troubleshooting)
  - [Client cannot connect to the compositor](#client-cannot-connect-to-the-compositor)
  - [`WAYLAND_DEBUG` floods with pointer/keyboard noise](#waylanddebug-floods-with-pointerkeyboard-noise)
  - [Buffer not appearing on screen after commit](#buffer-not-appearing-on-screen-after-commit)
  - [Protocol error: "object already has a role"](#protocol-error-object-already-has-a-role)
  - [Interface not found in globals](#interface-not-found-in-globals)
- [Summary](#summary)

---


## Overview

Wayland's wire protocol is the backbone of every interaction between a client application and the compositor. Unlike X11's notoriously sprawling protocol—which grew organically over decades and carries enormous legacy baggage—Wayland's wire protocol was designed from scratch with simplicity, safety, and performance as primary goals. Understanding it at the binary level is essential for advanced ricing work: when you write a custom compositor extension, debug a misbehaving client, or profile rendering latency, you are working directly with these primitives.

This chapter dissects the Wayland wire protocol in depth. We start with the Unix domain socket transport layer, move through the binary message format, examine the object model and lifecycle, and conclude with the global registry pattern that underpins all capability negotiation. By the end you will be able to read raw protocol dumps, write a minimal client from scratch in C, and understand exactly why Wayland behaves the way it does.

All material here builds on Chapter 1's overview of the compositor architecture. The protocol extensions discussed in Chapter 3 (xdg-shell) and Chapter 3 (wlr-layer-shell) are implemented as layers on top of the foundations described here. See Chapter 53 for session startup and how the `WAYLAND_DISPLAY` socket path is established before any client connects.

## Installation

**Project:** https://wayland.freedesktop.org · https://gitlab.freedesktop.org/wayland/wayland-protocols

```bash
# Arch Linux — libwayland, scanner, and protocol XML files
sudo pacman -S wayland wayland-protocols

# Development headers (for writing clients in C)
sudo pacman -S libwayland-dev  # or: wayland is sufficient on Arch

# Debugging tools
sudo pacman -S wayland-utils   # provides wayland-info

# Nix
nix-env -iA nixpkgs.wayland nixpkgs.wayland-protocols nixpkgs.wayland-utils
```

---

## 2.1 The Unix Socket Transport

Wayland communication uses Unix domain sockets exclusively—there is no TCP transport and no network transparency by design. This is a deliberate trade-off: the compositor and all its clients run on the same machine, and Unix sockets provide both the lowest latency IPC mechanism available on Linux and, crucially, the ability to pass file descriptors between processes via `SCM_RIGHTS` ancillary messages.

The socket path is determined at runtime. The compositor creates a socket whose name defaults to `wayland-0` (or `wayland-1`, etc.) inside the directory pointed to by `$XDG_RUNTIME_DIR`. Clients connect by calling `wl_display_connect(NULL)`, which reads `$WAYLAND_DISPLAY` to find the socket name and then opens `$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY`. If `$WAYLAND_DISPLAY` is already an absolute path, the client connects directly to that path.

File descriptor passing (`SCM_RIGHTS`) is what makes zero-copy buffer sharing possible. When a client wants to share a shared-memory buffer (`wl_shm`) or a DMA-BUF (`zwp_linux_dmabuf_v1`), it sends the file descriptor as ancillary data alongside the regular message bytes. The kernel transfers the descriptor across the process boundary, incrementing the reference count without copying any pixel data. This is the mechanism behind Wayland's "zero-copy" reputation.

Message framing on the socket is straightforward. Every Wayland message—whether a request from client to compositor or an event from compositor to client—begins with an 8-byte header. The remaining bytes are the serialized arguments. Messages are not length-prefixed at the socket level because the header encodes the total size; the receiver reads the header, parses the size field, and reads exactly that many additional bytes.

### Binary Header Format

```
Bytes 0–3:  Object ID  (uint32, little-endian)
Bytes 4–5:  Message size in bytes, including this header (uint16, little-endian)
Bytes 6–7:  Opcode (uint16, little-endian)
Bytes 8–N:  Arguments (variable, aligned to 32-bit boundaries)
```

The object ID identifies which object on the receiving side should handle this message. Opcodes are per-interface and start at 0; the same opcode number has a completely different meaning on `wl_surface` versus `wl_keyboard`. The size field includes the 8-byte header, so a message with no arguments has `size = 8`.

### Argument Types

| Type      | Wire Size          | Description                                      |
|-----------|--------------------|--------------------------------------------------|
| `int`     | 4 bytes            | Signed 32-bit integer                            |
| `uint`    | 4 bytes            | Unsigned 32-bit integer                          |
| `fixed`   | 4 bytes            | 24.8 fixed-point (24 integer bits, 8 fractional) |
| `string`  | 4 + N + padding    | Length-prefixed UTF-8, null-terminated, 32-bit aligned |
| `object`  | 4 bytes            | Object ID (uint32); 0 means null                 |
| `new_id`  | 4 bytes (+ extras) | Client-allocated ID for a newly created object   |
| `array`   | 4 + N + padding    | Length-prefixed raw bytes, 32-bit aligned        |
| `fd`      | 0 bytes (OOB)      | File descriptor sent via `SCM_RIGHTS`            |

Fixed-point numbers appear frequently for surface coordinates and pointer positions. To convert: divide the raw int32 by 256.0 to get the floating-point value.

### Inspecting the Socket

You can observe the raw socket traffic with `strace`:

```bash
# Trace all recvmsg/sendmsg calls for a running client
strace -e trace=recvmsg,sendmsg -p $(pgrep foot) 2>&1 | head -50

# Or attach to a new process
strace -e trace=network foot 2>&1 | grep -E 'sendmsg|recvmsg'
```

For a more ergonomic view, use `WAYLAND_DEBUG=1`:

```bash
WAYLAND_DEBUG=1 weston-terminal 2>&1 | head -80
# Output format: [timestamp] interface@id.method(args)
```

---

## 2.2 The Object Model

Every entity in the Wayland protocol is an **object**: a `wl_compositor`, a `wl_surface`, a `wl_seat`, a `xdg_toplevel`. Objects are identified by a 32-bit unsigned integer ID. These IDs are local to the connection—the same number can refer to entirely different objects in different client connections.

The ID space is partitioned by convention. Client-allocated IDs occupy the range `[1, 0xFEFFFFFF]`; server-allocated IDs occupy `[0xFF000000, 0xFFFFFFFF]`. In practice most clients never approach the client-allocated ceiling. The ID 0 is the null object and is never valid as a target.

Object creation happens when either side sends a message containing a `new_id` argument. The sender picks an unused ID from its range and records the mapping locally. The receiver creates the corresponding implementation and associates it with that ID. There is no acknowledgment—both sides must agree that the ID is now in use. This is possible because the protocol is strictly ordered: messages from a single sender arrive in sequence, and the sender knows exactly which `new_id` messages it has emitted.

Object destruction is more nuanced. Some interfaces have an explicit destructor request (e.g., `wl_surface.destroy`, `wl_buffer.destroy`). When the client sends the destructor, it must not send any further messages to that ID, and it can immediately recycle the ID. Other interfaces are destroyed implicitly when a parent object is destroyed—the protocol XML marks these with `destructor="true"` on the relevant request. Server-side, when a global is removed via `wl_registry.global_remove`, any objects bound to it continue to function until explicitly destroyed by the client.

### The `wl_display` Root Object

Object ID 1 is always the `wl_display` interface—the root of every Wayland connection. It is pre-allocated; no `new_id` message is needed. `wl_display` provides:

- `wl_display.sync(callback_id)` — creates a `wl_callback` that fires after the compositor processes all preceding requests. Indispensable for roundtrip synchronization.
- `wl_display.get_registry(registry_id)` — creates the `wl_registry` object used to enumerate compositor capabilities.
- `wl_display::error` event — sent by the compositor when a protocol error occurs, immediately followed by connection termination.
- `wl_display::delete_id` event — tells the client that the server has finished with a server-allocated ID, allowing it to be recycled.

### Interface Versioning

Every interface has a version number. When a global is advertised via `wl_registry.global`, the compositor reports the maximum version it supports. When the client binds the global, it requests a specific version (at most the advertised maximum). The negotiated version determines which requests and events are available. Attempting to use a feature from a version higher than negotiated results in a protocol error and connection termination.

```c
// Binding wl_compositor at version 4
struct wl_compositor *compositor = wl_registry_bind(
    registry,
    name,           // global name from registry.global event
    &wl_compositor_interface,
    4               // request version 4
);
```

Version negotiation is one-way: the client can request any version up to the compositor's maximum, but cannot request a version the compositor doesn't support. Always query at runtime rather than hardcoding a version.

---

## 2.3 Requests and Events

The Wayland protocol distinguishes two message directions: **requests** flow from client to compositor, and **events** flow from compositor to client. Both use the same binary format described in §2.1. The distinction is purely semantic and encoded in the protocol XML (`<request>` vs `<event>`).

Requests represent the client's intentions—creating a surface, submitting a buffer, asking for keyboard focus. Requests are not immediately processed; the compositor queues them and dispatches them on its main loop. This means a sequence of requests sent in a single `write()` to the socket will be processed atomically from the compositor's perspective, which is central to Wayland's double-buffered state model.

Events are asynchronous state updates pushed by the compositor: a new global appeared, the pointer moved, a surface gained focus, a frame was completed. The client must call `wl_display_dispatch()` or `wl_display_dispatch_pending()` to drain the event queue and invoke the registered listener callbacks. In a typical application built on `libwayland-client`, the main loop looks like:

```c
while (wl_display_dispatch(display) != -1) {
    // callbacks fire inside wl_display_dispatch
}
```

For non-blocking or multiplexed I/O (e.g., in a game loop or an event-driven server), use the file-descriptor approach:

```c
int fd = wl_display_get_fd(display);
struct pollfd pfd = { .fd = fd, .events = POLLIN };

while (running) {
    wl_display_flush(display);   // send any pending requests
    poll(&pfd, 1, -1);
    if (pfd.revents & POLLIN)
        wl_display_dispatch(display);
    // ... application rendering logic ...
}
```

### `wl_display.sync` and Roundtrip Semantics

`wl_display.sync` is the protocol's synchronization primitive. The client sends `sync` with a new `wl_callback` ID; the compositor, upon processing all previously queued requests, sends a `wl_callback.done` event back and then destroys the callback object. The client blocks (or waits in its event loop) until it receives this event, guaranteeing that everything sent before the sync has been processed.

`wl_display_roundtrip(display)` wraps this pattern conveniently:

```c
// After this call returns, all requests sent before it have been processed
// and all resulting events have been dispatched.
wl_display_roundtrip(display);
```

Roundtrips are expensive—each one introduces a full round-trip latency. Use them sparingly: once during initialization to populate the globals list, once after binding to confirm the binding succeeded, and rarely thereafter.

---

## 2.4 The Global Registry Pattern

The global registry is Wayland's capability advertisement mechanism. When a client connects, it creates a `wl_registry` object and registers a listener for `wl_registry.global` events. The compositor immediately sends one `global` event for each currently available global. After all existing globals have been advertised, subsequent `global` events arrive as new globals appear (uncommon at runtime; mostly a compositor plugin feature).

Each `global` event carries three fields:

| Field       | Type     | Description                                      |
|-------------|----------|--------------------------------------------------|
| `name`      | uint32   | Opaque numeric handle used for binding           |
| `interface` | string   | Interface name, e.g. `"wl_compositor"`           |
| `version`   | uint32   | Maximum version the compositor supports          |

The `name` is not the same as the object ID. It is an opaque numeric key used only in `wl_registry.bind`. After binding, the client receives an object ID it chooses and the `name` is no longer relevant.

### Complete Global Enumeration Example (C)

```c
#include <stdio.h>
#include <stdlib.h>
#include <wayland-client.h>

static void registry_global(void *data, struct wl_registry *registry,
                             uint32_t name, const char *interface,
                             uint32_t version)
{
    printf("Global: name=%u  interface=%s  version=%u\n",
           name, interface, version);
}

static void registry_global_remove(void *data, struct wl_registry *registry,
                                   uint32_t name)
{
    printf("Global removed: name=%u\n", name);
}

static const struct wl_registry_listener registry_listener = {
    .global        = registry_global,
    .global_remove = registry_global_remove,
};

int main(void)
{
    struct wl_display  *display  = wl_display_connect(NULL);
    if (!display) { fprintf(stderr, "Cannot connect to Wayland display\n"); return 1; }

    struct wl_registry *registry = wl_display_get_registry(display);
    wl_registry_add_listener(registry, &registry_listener, NULL);

    wl_display_roundtrip(display);  // receive all existing globals

    wl_registry_destroy(registry);
    wl_display_disconnect(display);
    return 0;
}
```

Compile and run:

```bash
gcc -o list-globals list-globals.c $(pkg-config --cflags --libs wayland-client)
./list-globals
```

Example output on a typical Sway session:

```
Global: name=1   interface=wl_compositor          version=6
Global: name=2   interface=wl_subcompositor        version=1
Global: name=3   interface=wl_shm                  version=2
Global: name=4   interface=wl_seat                 version=9
Global: name=5   interface=wl_output               version=4
Global: name=6   interface=xdg_wm_base             version=6
Global: name=7   interface=wl_data_device_manager  version=3
Global: name=8   interface=zwlr_layer_shell_v1      version=5
...
```

### Binding a Global

Binding converts a `name` into a live proxy object. The interface pointer and version you pass must match what the compositor advertised (or be lower):

```c
static struct wl_compositor *compositor = NULL;
static struct wl_shm        *shm        = NULL;

static void registry_global(void *data, struct wl_registry *registry,
                             uint32_t name, const char *interface,
                             uint32_t version)
{
    if (strcmp(interface, wl_compositor_interface.name) == 0) {
        compositor = wl_registry_bind(registry, name,
                                      &wl_compositor_interface,
                                      MIN(version, 5));
    } else if (strcmp(interface, wl_shm_interface.name) == 0) {
        shm = wl_registry_bind(registry, name,
                               &wl_shm_interface,
                               MIN(version, 1));
    }
}
```

Always take the minimum of the compositor's advertised version and the highest version your client was compiled against. This ensures forward compatibility when the compositor is newer than the client.

---

## 2.5 Surfaces and the Rendering Pipeline

The `wl_surface` is the central abstraction in Wayland rendering. Every pixel a client draws on screen is associated with a `wl_surface`. A surface has no role on its own—it must be assigned a role (toplevel window, subsurface, layer-shell surface, cursor, etc.) before it becomes visible. Assigning conflicting roles to the same surface is a fatal protocol error.

Creating a surface is straightforward:

```c
struct wl_surface *surface = wl_compositor_create_surface(compositor);
```

### `wl_buffer`: Attaching Pixel Data

A `wl_buffer` wraps a region of memory containing rendered pixels. The two common buffer backends are:

**`wl_shm` (shared memory):** Allocates a `memfd` or `shm_open` file, maps it in both the client and compositor, and passes the fd via `SCM_RIGHTS`. Simple and universally supported. Involves a CPU memory copy when the compositor composites.

**`zwp_linux_dmabuf_v1` (DMA-BUF):** Uses a GPU-allocated buffer represented by a DMA-BUF file descriptor. Enables true zero-copy rendering when the compositor also uses the GPU. Required for hardware-accelerated clients. Covered in depth in Chapter 63.

### `wl_shm` Buffer from Scratch

```c
#include <sys/mman.h>
#include <fcntl.h>
#include <unistd.h>
#include <wayland-client.h>
#include <string.h>
#include <stdlib.h>

static int create_shm_file(size_t size)
{
    int fd = memfd_create("wayland-shm", MFD_CLOEXEC | MFD_ALLOW_SEALING);
    if (fd < 0) return -1;
    if (ftruncate(fd, (off_t)size) < 0) { close(fd); return -1; }
    return fd;
}

struct wl_buffer *make_shm_buffer(struct wl_shm *shm,
                                   int width, int height,
                                   uint32_t **pixels_out)
{
    int stride = width * 4;                  // XRGB8888: 4 bytes per pixel
    size_t size = (size_t)(stride * height);

    int fd = create_shm_file(size);
    if (fd < 0) return NULL;

    uint32_t *data = mmap(NULL, size, PROT_READ | PROT_WRITE,
                          MAP_SHARED, fd, 0);
    if (data == MAP_FAILED) { close(fd); return NULL; }

    struct wl_shm_pool *pool = wl_shm_create_pool(shm, fd, (int32_t)size);
    struct wl_buffer   *buf  = wl_shm_pool_create_buffer(pool, 0,
                                    width, height, stride,
                                    WL_SHM_FORMAT_XRGB8888);
    wl_shm_pool_destroy(pool);
    close(fd);  // compositor now holds the fd via SCM_RIGHTS

    if (pixels_out) *pixels_out = data;
    return buf;
}
```

### Commit Semantics: Double-Buffered State

Wayland uses a double-buffered state model. Changes to a surface—attaching a new buffer, setting a damage region, changing the input region—are **pending** until the client calls `wl_surface.commit`. Only after commit does the compositor apply the changes atomically. This eliminates the tearing artifacts common in X11's immediate-mode model.

The commit sequence for a frame:

```c
// 1. Attach a buffer (the new front buffer)
wl_surface_attach(surface, buffer, 0, 0);

// 2. Mark the entire surface as damaged (compositor must repaint it)
wl_surface_damage_buffer(surface, 0, 0, width, height);

// 3. Commit: all pending state becomes current atomically
wl_surface_commit(surface);
```

After commit, the buffer is "in use" by the compositor until it sends a `wl_buffer.release` event. The client must not modify or destroy the buffer until release arrives.

### Frame Callbacks: Pacing Rendering to Vsync

Rendering as fast as possible wastes CPU/GPU and causes unnecessary power consumption. Frame callbacks let the compositor tell the client when to render the next frame:

```c
static void frame_done(void *data, struct wl_callback *cb, uint32_t time)
{
    wl_callback_destroy(cb);
    render_frame();              // draw next frame
    schedule_next_frame();       // re-register callback
}

static const struct wl_callback_listener frame_listener = {
    .done = frame_done,
};

static void schedule_next_frame(void)
{
    struct wl_callback *cb = wl_surface_frame(surface);
    wl_callback_add_listener(cb, &frame_listener, NULL);
    wl_surface_commit(surface);  // commit triggers the callback
}
```

The `time` argument to `frame_done` is a millisecond timestamp that can be used for animation timing.

### Damage Tracking: Partial Surface Updates

For efficiency, the client should tell the compositor exactly which regions of the surface have changed. Two requests exist:

- `wl_surface.damage(x, y, w, h)` — coordinates in surface-local space (affected by buffer scale and transform)
- `wl_surface.damage_buffer(x, y, w, h)` — coordinates in buffer space (preferred; added in `wl_surface` version 4)

```c
// After drawing only a 100x20 pixel status bar region at the top:
wl_surface_damage_buffer(surface, 0, 0, width, 20);
wl_surface_commit(surface);
```

Sending `damage_buffer` for the full surface area is always safe but suboptimal. For ricing projects that update small overlay elements frequently (clocks, system monitors), tight damage regions are a meaningful optimization.

---

## 2.6 Debugging the Wire Protocol

Understanding what is actually being sent over the socket is invaluable when developing compositor extensions, writing custom clients, or diagnosing protocol errors.

### `WAYLAND_DEBUG`

The simplest tool. Set `WAYLAND_DEBUG=1` before launching any Wayland client:

```bash
WAYLAND_DEBUG=1 foot 2>&1 | grep -v 'wl_keyboard\|wl_pointer' | head -60
```

Each line shows the direction (`->` for outgoing, `<-` for incoming), timestamp, and the decoded message:

```
[1748511234.123456] ->  wl_display@1.get_registry(new id wl_registry@2)
[1748511234.124001] <-  wl_registry@2.global(1, "wl_compositor", 6)
[1748511234.124003] <-  wl_registry@2.global(2, "wl_subcompositor", 1)
[1748511234.124891] ->  wl_registry@2.bind(1, "wl_compositor", 5, new id wl_compositor@3)
```

Filter to only interesting interfaces:

```bash
WAYLAND_DEBUG=1 my-client 2>&1 | grep -E 'xdg_|zwlr_|wl_surface'
```

### `wldbg` — Interactive Protocol Debugger

`wldbg` sits between the client and compositor as a transparent proxy, decoding messages in real time:

```bash
# Install
git clone https://github.com/mclasen/wldbg && cd wldbg
meson build && ninja -C build && sudo ninja -C build install

# Run a client under wldbg
wldbg run foot

# Interactive mode: set breakpoints on specific messages
wldbg -i run foot
# Inside wldbg:
# (wldbg) b wl_surface::commit
# (wldbg) continue
```

`wldbg` is essential for debugging protocol state machines in custom compositor extensions.

### `weston-info` and `wayland-info`

These tools enumerate all globals and their supported formats/capabilities:

```bash
# weston-info (from weston package)
weston-info

# wayland-info (from wayland-utils package — preferred on non-weston compositors)
wayland-info

# Example: check advertised DRM formats for dmabuf
wayland-info | grep -A5 'zwp_linux_dmabuf'
```

### Decoding Hex Dumps

When debugging at the socket level, you sometimes need to decode raw bytes. Given the header format from §2.1:

```
Hex dump: 01 00 00 00  0c 00 01 00  02 00 00 00
          ^^^^^^^^^^^  ^^^^^^^^^^^^^  ^^^^^^^^^^^
          Object ID=1  size=12, op=1  arg: new_id=2
```

This decodes as: `wl_display@1.get_registry(new id @2)` — object 1 (wl_display), opcode 1 (get_registry), argument is a new_id 2.

A Python snippet to decode Wayland message headers from a pcap or raw bytes:

```python
import struct, sys

def decode_header(data: bytes, offset: int = 0):
    obj_id, size_op = struct.unpack_from('<II', data, offset)
    size   = (size_op >> 16) & 0xFFFF
    opcode = size_op & 0xFFFF
    return {'object_id': obj_id, 'opcode': opcode, 'size': size,
            'payload': data[offset+8 : offset+size]}

# Read raw bytes from a socket capture:
with open('wayland.dump', 'rb') as f:
    raw = f.read()

pos = 0
while pos + 8 <= len(raw):
    msg = decode_header(raw, pos)
    print(f"obj={msg['object_id']}  op={msg['opcode']}  size={msg['size']}")
    pos += msg['size']
```

To capture the raw socket, use `socat` as a tap:

```bash
# Rename the real socket, create a tap
REAL="$XDG_RUNTIME_DIR/wayland-0"
mv "$REAL" "${REAL}.real"
socat -x UNIX-LISTEN:"$REAL",fork,reuseaddr \
          UNIX-CONNECT:"${REAL}.real" 2>&1 | tee wayland-tap.log
```

### Protocol Error Messages

When the compositor detects a violation, it sends `wl_display.error` and closes the connection. The error event carries:

| Field         | Meaning                                             |
|---------------|-----------------------------------------------------|
| `object_id`   | The object that triggered the error                 |
| `code`        | Interface-specific error code (see protocol XML)    |
| `message`     | Human-readable description                          |

In `WAYLAND_DEBUG=1` output you will see something like:

```
<-  wl_display@1.error(wl_surface@5, 1, "wl_surface already has a role")
```

Protocol errors are fatal. To catch them programmatically:

```c
void display_error(void *data, struct wl_display *display,
                   void *object_proxy, uint32_t code, const char *message)
{
    fprintf(stderr, "Protocol error: code=%u  msg=%s\n", code, message);
    abort();
}

static const struct wl_display_listener display_listener = {
    .error     = display_error,
    .delete_id = NULL,
};
wl_display_add_listener(display, &display_listener, NULL);
```

---

## Troubleshooting

### Client cannot connect to the compositor

```bash
# Verify the socket exists
ls -la "$XDG_RUNTIME_DIR"/wayland-*

# Check WAYLAND_DISPLAY is set correctly
echo $WAYLAND_DISPLAY      # should be "wayland-0" or similar
echo $XDG_RUNTIME_DIR      # should be /run/user/$(id -u)

# If running nested (e.g., weston inside Sway), the socket name changes
# Nested weston creates wayland-1; export it explicitly:
export WAYLAND_DISPLAY=wayland-1
foot
```

### `WAYLAND_DEBUG` floods with pointer/keyboard noise

```bash
# Filter out high-frequency input events
WAYLAND_DEBUG=1 my-client 2>&1 | grep -Ev 'wl_(keyboard|pointer|touch)'

# Or use a temporary function
wldebug() { WAYLAND_DEBUG=1 "$@" 2>&1; }
wldebug my-client | grep xdg_
```

### Buffer not appearing on screen after commit

Common causes:
1. **No role assigned** — surfaces without a role (xdg_toplevel, layer_surface, etc.) are silently ignored. Assign a role before committing.
2. **Buffer still in use** — you reused or destroyed the buffer before the `wl_buffer.release` event. Enable `WAYLAND_DEBUG=1` and check for the release event.
3. **Missing damage** — without a `wl_surface.damage` or `wl_surface.damage_buffer` call, the compositor may not repaint. Always damage before commit.
4. **wl_display.flush not called** — requests accumulate in the client-side buffer until flushed. Call `wl_display_flush(display)` after committing.

### Protocol error: "object already has a role"

Each `wl_surface` may be assigned exactly one role for its lifetime. If you call both `xdg_wm_base.get_xdg_surface` and `wlr_layer_shell.get_layer_surface` on the same `wl_surface`, the compositor terminates the connection. Always create a fresh `wl_surface` for each role.

### Interface not found in globals

If a required global (e.g., `zwlr_layer_shell_v1`) is absent:
- Verify the compositor supports it: `wayland-info | grep zwlr_layer_shell`
- Check you are running on the right compositor (layer-shell is wlroots-specific)
- Ensure your client was compiled against the correct protocol XML version

---

## Summary

The Wayland wire protocol is compact and well-structured. Every message is an 8-byte header plus typed arguments. Objects are numeric IDs with lifecycles governed by `new_id` and destructor requests. The global registry is the universal capability discovery mechanism, with version negotiation built in. Surfaces are the rendering primitive; their state is double-buffered and committed atomically. Frame callbacks pace rendering to vsync, and damage regions minimize compositor work.

With these foundations, you can understand every subsequent chapter's protocol interactions. Chapter 4 introduces `libwayland-client` programming in depth. Chapter 7 builds on this to explain the `xdg-shell` role protocol for standard windows. Chapter 12 covers `wlr-layer-shell` for status bars and overlay surfaces—the bread and butter of Wayland ricing.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
