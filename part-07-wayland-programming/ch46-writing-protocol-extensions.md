# Chapter 46 — Writing a Wayland Protocol Extension

Wayland's extensibility model is one of its strongest architectural properties. Rather than baking every conceivable feature into the core protocol, Wayland separates the wire protocol layer from higher-level functionality, allowing compositors, toolkits, and applications to negotiate capabilities at runtime through protocol extensions. This chapter walks through the entire lifecycle of a custom Wayland protocol extension: design, XML authoring, code generation, client implementation, server implementation in wlroots, versioning strategy, and the path to upstreaming. By the end you will have a working blur-level protocol that a custom compositor can implement and a client application can consume.

The mechanisms described here are the same ones used to build `xdg-shell`, `wlr-layer-shell`, `ext-idle-notify-v1`, and Hyprland's private protocols. Understanding them gives you full control over the compositor-client contract. See Ch 43 for the Wayland object model and Ch 44 for the wlroots compositor infrastructure that server-side code builds upon.

---

## 46.1 When to Write a Protocol Extension

The first question to ask before writing a new protocol is whether an existing one already covers your use case. The `wayland-protocols` repository provides stable, staging, and deprecated protocol definitions maintained by the freedesktop.org community. The `wlr-protocols` repository covers wlroots-specific extensions such as `wlr-layer-shell-unstable-v1` and `wlr-screencopy-unstable-v1`. Hyprland maintains its own `hyprland-protocols` repository for compositor-private extensions. Only write a new protocol when none of these adequately address your requirements.

Good reasons to write a private protocol extension include: exposing compositor-specific rendering parameters (e.g., blur strength, corner radius, or shadow spread) that have no analogue in upstream protocols; enabling application-compositor communication for hardware-accelerated features on a specific GPU stack; implementing developer tooling like debug overlays, frame timing introspection, or live shader reloading; or prototyping an idea that you intend to propose upstream after gathering real-world implementation experience.

Poor reasons include: working around an existing protocol you have not read carefully, duplicating functionality from `xdg-activation-v1` or `wlr-foreign-toplevel-management`, or implementing session management features already covered by `ext-session-lock-v1`. Check those first. The cost of maintaining a private protocol is paid every time the Wayland version negotiation logic changes.

The scope of a protocol directly affects its complexity. A protocol that adds a single request to a surface (e.g., "set blur level") is trivial. A protocol that manages a hierarchy of objects with lifecycle events, error codes, and state synchronization across multiple roundtrips requires careful design work. Start with the smallest protocol surface that satisfies your use case; you can always add requests in a version bump.

Consider also the security model. Unlike X11, Wayland requires clients to explicitly bind a global interface to use it. Compositors can refuse to advertise a global to unprivileged clients, which is a powerful sandbox primitive. If your extension is intended only for privileged processes (e.g., a status bar), do not advertise the global to general clients. The access control model should be part of your protocol design, not an afterthought.

---

## 46.2 Protocol XML Anatomy

Wayland protocols are defined in XML following the schema enforced by `wayland-scanner`. The XML is the canonical source of truth: it defines every interface, request, event, argument, error, and enum. Generated C code is a derivative artifact. Understand the XML first.

Every protocol file begins with a `<protocol>` root element containing a required `name` attribute. The name becomes a C identifier prefix. Nested `<interface>` elements define individual object types. Each interface has a `version` attribute that must start at 1 and may only increase. Interfaces contain `<request>` (client-to-server) and `<event>` (server-to-client) children, plus optional `<enum>` definitions for typed integer arguments.

Arguments (`<arg>`) carry a `type` attribute that must be one of: `int`, `uint`, `fixed` (24.8 fixed-point), `string`, `object`, `new_id`, `array`, or `fd` (file descriptor). The `new_id` type is special: it allocates a new object on both sides of the connection simultaneously without a roundtrip. The `fd` type allows passing file descriptors over the Unix socket, which is how shared memory (`wl_shm`) and GPU buffer handles work.

Error codes are declared with `<enum name="error">` inside an interface. Every error enum value maps to a protocol error that destroys the offending resource and disconnects the client if unhandled. Declare errors for every invalid state transition or argument constraint violation.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<protocol name="my_compositor_blur">
  <copyright>
    Copyright (C) 2024 Example Author

    Permission is hereby granted, free of charge, to any person obtaining a
    copy of this software and associated documentation files (the "Software"),
    to deal in the Software without restriction, including without limitation
    the rights to use, copy, modify, merge, publish, distribute, sublicense,
    and/or sell copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
    DEALINGS IN THE SOFTWARE.
  </copyright>

  <!-- Manager interface: one per compositor, clients bind this global -->
  <interface name="my_blur_manager_v1" version="1">
    <description summary="surface blur manager">
      This interface allows clients to request per-surface background blur
      from a compositor that supports it. The compositor may ignore requests
      if the hardware or render backend does not support blur.
    </description>

    <enum name="error">
      <entry name="already_constructed" value="0"
        summary="a blur object already exists for this surface"/>
      <entry name="bad_surface" value="1"
        summary="the surface is not a valid wl_surface"/>
    </enum>

    <request name="destroy" type="destructor">
      <description summary="destroy the manager"/>
    </request>

    <request name="get_blur">
      <description summary="request blur control for a surface">
        Create a blur control object for the given surface. Only one blur
        object may exist per surface at a time; creating a second one will
        raise the already_constructed error.
      </description>
      <arg name="id"      type="new_id" interface="my_blur_surface_v1"/>
      <arg name="surface" type="object"  interface="wl_surface"
        summary="the surface to apply blur to"/>
    </request>
  </interface>

  <!-- Per-surface blur control object -->
  <interface name="my_blur_surface_v1" version="1">
    <description summary="blur control for a single surface"/>

    <enum name="error">
      <entry name="bad_radius" value="0"
        summary="blur radius is outside the allowed range [0, 128]"/>
    </enum>

    <request name="set_radius">
      <description summary="set the blur radius in pixels">
        Sets the Gaussian blur radius applied behind this surface. A value
        of 0 disables blur. Changes take effect on the next surface commit.
        Values outside [0, 128] raise the bad_radius error.
      </description>
      <arg name="radius" type="uint" summary="blur radius in pixels"/>
    </request>

    <request name="set_passes">
      <description summary="set the number of blur passes">
        Multiple passes improve quality at the cost of GPU bandwidth. Typical
        values are 1 (fast) to 3 (high quality). Clamped to [1, 8] silently.
      </description>
      <arg name="passes" type="uint" summary="number of blur passes"/>
    </request>

    <event name="compositor_capabilities">
      <description summary="advertise compositor blur capabilities">
        Sent once immediately after object creation. Reports the maximum blur
        radius and pass count the compositor supports.
      </description>
      <arg name="max_radius" type="uint" summary="maximum supported radius"/>
      <arg name="max_passes" type="uint" summary="maximum supported passes"/>
    </event>

    <request name="destroy" type="destructor">
      <description summary="destroy blur control, disabling blur on the surface"/>
    </request>
  </interface>
</protocol>
```

Save this file as `my-compositor-blur-v1.xml`. The naming convention `<name>-v<version>.xml` reflects the interface version, not the file revision. Keep one protocol per file.

---

## 46.3 Generating Code with wayland-scanner

`wayland-scanner` is the official code generator shipped with the `wayland` package. It reads protocol XML and emits C headers and implementation glue. Every Wayland compositor and toolkit project invokes it at build time; there is no runtime dependency on the XML file.

The scanner produces three output modes relevant to extension authors:

| Mode | Output | Used by |
|---|---|---|
| `client-header` | `<protocol>-client.h` | Client applications |
| `server-header` | `<protocol>-server.h` | Compositor server code |
| `private-code` | `<protocol>.c` | Both, compiled into the binary |
| `public-code` | `<protocol>.c` | Shared libraries exposing the protocol |

For a private in-tree protocol, use `private-code`. For a shared library that multiple binaries link against (e.g., a toolkit providing a protocol wrapper), use `public-code`.

```bash
# Verify scanner version (must be >= 1.20 for some modern features)
wayland-scanner --version

# Generate client-side header
wayland-scanner client-header \
    my-compositor-blur-v1.xml \
    my-compositor-blur-v1-client-protocol.h

# Generate server-side header
wayland-scanner server-header \
    my-compositor-blur-v1.xml \
    my-compositor-blur-v1-server-protocol.h

# Generate implementation (used by both client and server)
wayland-scanner private-code \
    my-compositor-blur-v1.xml \
    my-compositor-blur-v1-protocol.c
```

The generated client header declares `extern const struct wl_interface my_blur_manager_v1_interface;`, proxy structs, and inline wrapper functions like `my_blur_manager_v1_get_blur(manager, surface)`. The server header declares `wl_resource_create` helpers and `send_*` event functions. The private code implements the serialization tables (`wl_message` arrays) that the Wayland library uses to marshal and unmarshal arguments on the socket.

For Meson-based projects, integrate the scanner with a custom target:

```meson
# meson.build
wayland_scanner = find_program('wayland-scanner')
wayland_dep     = dependency('wayland-client')  # or wayland-server

blur_xml = files('protocol/my-compositor-blur-v1.xml')

blur_client_h = custom_target(
  'blur-client-header',
  input:   blur_xml,
  output:  'my-compositor-blur-v1-client-protocol.h',
  command: [wayland_scanner, 'client-header', '@INPUT@', '@OUTPUT@'],
)

blur_server_h = custom_target(
  'blur-server-header',
  input:   blur_xml,
  output:  'my-compositor-blur-v1-server-protocol.h',
  command: [wayland_scanner, 'server-header', '@INPUT@', '@OUTPUT@'],
)

blur_proto_c = custom_target(
  'blur-protocol-code',
  input:   blur_xml,
  output:  'my-compositor-blur-v1-protocol.c',
  command: [wayland_scanner, 'private-code', '@INPUT@', '@OUTPUT@'],
)

# Reference generated targets in your executable
executable('myapp',
  ['src/main.c', blur_proto_c],
  dependencies: [wayland_dep],
  include_directories: include_directories('.'),
  # Make generated headers findable
  sources: [blur_client_h],
)
```

For CMake projects, an equivalent approach uses `add_custom_command`. See the wlroots `protocol/` directory for real-world CMake examples.

---

## 46.4 Client-Side Implementation

The client side of a Wayland protocol extension follows a fixed pattern: discover the global via the registry, bind to it, attach listeners for events, call request functions, and handle the roundtrip/dispatch loop. The generated proxy functions make this straightforward, but the lifecycle management (binding version, checking for null, destroying in the right order) requires careful attention.

A complete client-side implementation for the blur protocol:

```c
/* blur_client.c — minimal client using my_compositor_blur_v1 */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wayland-client.h>
#include "my-compositor-blur-v1-client-protocol.h"

struct client_state {
    struct wl_display    *display;
    struct wl_registry   *registry;
    struct wl_compositor *compositor;
    struct wl_surface    *surface;
    struct my_blur_manager_v1 *blur_manager;
    struct my_blur_surface_v1 *blur_surface;
    uint32_t max_radius;
    uint32_t max_passes;
};

/* ── Blur surface event listener ─────────────────────────────── */

static void blur_capabilities(void *data,
    struct my_blur_surface_v1 *blur_surface,
    uint32_t max_radius, uint32_t max_passes)
{
    struct client_state *state = data;
    state->max_radius = max_radius;
    state->max_passes = max_passes;
    fprintf(stderr, "Compositor blur: max_radius=%u max_passes=%u\n",
            max_radius, max_passes);
}

static const struct my_blur_surface_v1_listener blur_surface_listener = {
    .compositor_capabilities = blur_capabilities,
};

/* ── Registry listener ───────────────────────────────────────── */

static void registry_handle_global(void *data,
    struct wl_registry *registry, uint32_t name,
    const char *interface, uint32_t version)
{
    struct client_state *state = data;

    if (strcmp(interface, wl_compositor_interface.name) == 0) {
        state->compositor = wl_registry_bind(registry, name,
            &wl_compositor_interface, 4);
    } else if (strcmp(interface, my_blur_manager_v1_interface.name) == 0) {
        /* Bind at version 1; clamp to the lower of offered and supported */
        uint32_t bind_ver = version < 1 ? version : 1;
        state->blur_manager = wl_registry_bind(registry, name,
            &my_blur_manager_v1_interface, bind_ver);
    }
}

static void registry_handle_global_remove(void *data,
    struct wl_registry *registry, uint32_t name)
{
    /* Handle dynamic global removal if needed */
    (void)data; (void)registry; (void)name;
}

static const struct wl_registry_listener registry_listener = {
    .global        = registry_handle_global,
    .global_remove = registry_handle_global_remove,
};

/* ── Main ────────────────────────────────────────────────────── */

int main(int argc, char *argv[])
{
    struct client_state state = {0};

    state.display = wl_display_connect(NULL);
    if (!state.display) {
        fprintf(stderr, "Failed to connect to Wayland display\n");
        return 1;
    }

    state.registry = wl_display_get_registry(state.display);
    wl_registry_add_listener(state.registry, &registry_listener, &state);

    /* First roundtrip: populates globals */
    wl_display_roundtrip(state.display);

    if (!state.compositor) {
        fprintf(stderr, "No wl_compositor global\n");
        return 1;
    }
    if (!state.blur_manager) {
        fprintf(stderr, "Compositor does not support my_blur_manager_v1\n");
        return 1;
    }

    /* Create a surface and attach blur control to it */
    state.surface = wl_compositor_create_surface(state.compositor);
    state.blur_surface = my_blur_manager_v1_get_blur(
        state.blur_manager, state.surface);
    my_blur_surface_v1_add_listener(state.blur_surface,
        &blur_surface_listener, &state);

    /* Second roundtrip: receive compositor_capabilities event */
    wl_display_roundtrip(state.display);

    /* Apply blur: clamp to compositor limits */
    uint32_t desired_radius = 20;
    uint32_t desired_passes = 2;
    if (desired_radius > state.max_radius) desired_radius = state.max_radius;
    if (desired_passes > state.max_passes) desired_passes = state.max_passes;

    my_blur_surface_v1_set_radius(state.blur_surface, desired_radius);
    my_blur_surface_v1_set_passes(state.blur_surface, desired_passes);

    /* Commit the surface to apply the double-buffered blur state */
    wl_surface_commit(state.surface);
    wl_display_roundtrip(state.display);

    fprintf(stderr, "Blur applied: radius=%u passes=%u\n",
            desired_radius, desired_passes);

    /* Teardown in reverse creation order */
    my_blur_surface_v1_destroy(state.blur_surface);
    wl_surface_destroy(state.surface);
    my_blur_manager_v1_destroy(state.blur_manager);
    wl_registry_destroy(state.registry);
    wl_display_disconnect(state.display);
    return 0;
}
```

Compile and link against the generated protocol code:

```bash
gcc -o blur_client blur_client.c my-compositor-blur-v1-protocol.c \
    $(pkg-config --cflags --libs wayland-client)
```

The two-roundtrip pattern is standard: the first roundtrip processes all `wl_registry.global` events, letting you bind all required globals; the second roundtrip dispatches the initial events sent by newly created objects (here, `compositor_capabilities`). For event-driven applications using `wl_display_dispatch` in a poll loop, replace the second roundtrip with normal event dispatching.

---

## 46.5 Server-Side Implementation in wlroots

The server side requires more bookkeeping: creating the global, managing resource lifetimes, validating arguments, emitting events, and hooking into the compositor's surface commit path. wlroots provides helpers that reduce boilerplate, but the core pattern is standard `libwayland-server` API.

The following example implements the full server side of the blur protocol inside a wlroots-based compositor. It assumes you have a `struct server` with a `wl_display` and a `wlr_scene` (see Ch 44).

```c
/* blur_server.c — server side of my_compositor_blur_v1 */
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <wayland-server-core.h>
#include <wlr/types/wlr_compositor.h>
#include <wlr/util/log.h>
#include "my-compositor-blur-v1-server-protocol.h"

/* ── Data structures ─────────────────────────────────────────── */

struct my_blur_manager {
    struct wl_global    *global;
    struct wl_list       surfaces; /* list of my_blur_surface */
    struct wl_listener   display_destroy;
};

struct my_blur_surface {
    struct wl_resource       *resource;       /* my_blur_surface_v1 resource */
    struct wlr_surface       *wlr_surface;
    uint32_t                  radius;         /* pending, applied on commit */
    uint32_t                  passes;
    uint32_t                  current_radius; /* committed state */
    uint32_t                  current_passes;
    struct wl_listener        surface_commit;
    struct wl_listener        surface_destroy;
    struct wl_list            link;           /* in my_blur_manager.surfaces */
};

/* Maximum values advertised to clients */
#define MAX_BLUR_RADIUS 64
#define MAX_BLUR_PASSES  4

/* ── my_blur_surface_v1 request handlers ─────────────────────── */

static void surface_handle_set_radius(struct wl_client *client,
    struct wl_resource *resource, uint32_t radius)
{
    struct my_blur_surface *surf = wl_resource_get_user_data(resource);
    if (radius > MAX_BLUR_RADIUS) {
        wl_resource_post_error(resource,
            MY_BLUR_SURFACE_V1_ERROR_BAD_RADIUS,
            "blur radius %u exceeds maximum %u",
            radius, MAX_BLUR_RADIUS);
        return;
    }
    surf->radius = radius;
}

static void surface_handle_set_passes(struct wl_client *client,
    struct wl_resource *resource, uint32_t passes)
{
    struct my_blur_surface *surf = wl_resource_get_user_data(resource);
    /* Silently clamp per the protocol description */
    if (passes < 1) passes = 1;
    if (passes > MAX_BLUR_PASSES) passes = MAX_BLUR_PASSES;
    surf->passes = passes;
}

static void surface_handle_destroy(struct wl_client *client,
    struct wl_resource *resource)
{
    wl_resource_destroy(resource);
}

static const struct my_blur_surface_v1_interface blur_surface_impl = {
    .set_radius = surface_handle_set_radius,
    .set_passes = surface_handle_set_passes,
    .destroy    = surface_handle_destroy,
};

/* ── Surface lifecycle callbacks ─────────────────────────────── */

static void handle_surface_commit(struct wl_listener *listener, void *data)
{
    struct my_blur_surface *surf =
        wl_container_of(listener, surf, surface_commit);
    /* Atomically apply double-buffered state on commit */
    surf->current_radius = surf->radius;
    surf->current_passes = surf->passes;
    wlr_log(WLR_DEBUG, "blur commit: surface=%p radius=%u passes=%u",
            (void*)surf->wlr_surface,
            surf->current_radius, surf->current_passes);
    /* Hook into your render pass here to apply the blur */
}

static void handle_surface_destroy(struct wl_listener *listener, void *data)
{
    struct my_blur_surface *surf =
        wl_container_of(listener, surf, surface_destroy);
    wl_resource_destroy(surf->resource);
}

static void blur_surface_resource_destroy(struct wl_resource *resource)
{
    struct my_blur_surface *surf = wl_resource_get_user_data(resource);
    wl_list_remove(&surf->surface_commit.link);
    wl_list_remove(&surf->surface_destroy.link);
    wl_list_remove(&surf->link);
    free(surf);
}

/* ── my_blur_manager_v1 request handlers ─────────────────────── */

static void manager_handle_get_blur(struct wl_client *client,
    struct wl_resource *manager_resource,
    uint32_t id, struct wl_resource *surface_resource)
{
    struct my_blur_manager *mgr =
        wl_resource_get_user_data(manager_resource);
    struct wlr_surface *wlr_surface =
        wlr_surface_from_resource(surface_resource);

    /* Check for duplicate */
    struct my_blur_surface *existing;
    wl_list_for_each(existing, &mgr->surfaces, link) {
        if (existing->wlr_surface == wlr_surface) {
            wl_resource_post_error(manager_resource,
                MY_BLUR_MANAGER_V1_ERROR_ALREADY_CONSTRUCTED,
                "blur object already exists for this surface");
            return;
        }
    }

    struct my_blur_surface *surf = calloc(1, sizeof(*surf));
    if (!surf) {
        wl_client_post_no_memory(client);
        return;
    }

    int version = wl_resource_get_version(manager_resource);
    surf->resource = wl_resource_create(client,
        &my_blur_surface_v1_interface, version, id);
    if (!surf->resource) {
        free(surf);
        wl_client_post_no_memory(client);
        return;
    }

    surf->wlr_surface = wlr_surface;
    surf->radius       = 0;
    surf->passes       = 1;

    wl_resource_set_implementation(surf->resource, &blur_surface_impl,
        surf, blur_surface_resource_destroy);

    surf->surface_commit.notify = handle_surface_commit;
    wl_signal_add(&wlr_surface->events.commit, &surf->surface_commit);

    surf->surface_destroy.notify = handle_surface_destroy;
    wl_signal_add(&wlr_surface->events.destroy, &surf->surface_destroy);

    wl_list_insert(&mgr->surfaces, &surf->link);

    /* Send initial capabilities event */
    my_blur_surface_v1_send_compositor_capabilities(surf->resource,
        MAX_BLUR_RADIUS, MAX_BLUR_PASSES);
}

static void manager_handle_destroy(struct wl_client *client,
    struct wl_resource *resource)
{
    wl_resource_destroy(resource);
}

static const struct my_blur_manager_v1_interface blur_manager_impl = {
    .get_blur = manager_handle_get_blur,
    .destroy  = manager_handle_destroy,
};

/* ── Global bind callback ────────────────────────────────────── */

static void blur_manager_bind(struct wl_client *client,
    void *data, uint32_t version, uint32_t id)
{
    struct my_blur_manager *mgr = data;

    struct wl_resource *resource = wl_resource_create(client,
        &my_blur_manager_v1_interface, version, id);
    if (!resource) {
        wl_client_post_no_memory(client);
        return;
    }

    wl_resource_set_implementation(resource, &blur_manager_impl,
        mgr, NULL /* manager resource has no per-resource state to free */);
}

/* ── Public constructor/destructor ───────────────────────────── */

static void handle_display_destroy(struct wl_listener *listener, void *data)
{
    struct my_blur_manager *mgr =
        wl_container_of(listener, mgr, display_destroy);
    wl_list_remove(&mgr->display_destroy.link);
    wl_global_destroy(mgr->global);
    free(mgr);
}

struct my_blur_manager *my_blur_manager_create(struct wl_display *display)
{
    struct my_blur_manager *mgr = calloc(1, sizeof(*mgr));
    if (!mgr) return NULL;

    wl_list_init(&mgr->surfaces);

    mgr->global = wl_global_create(display,
        &my_blur_manager_v1_interface, 1,
        mgr, blur_manager_bind);
    if (!mgr->global) {
        free(mgr);
        return NULL;
    }

    mgr->display_destroy.notify = handle_display_destroy;
    wl_display_add_destroy_listener(display, &mgr->display_destroy);

    wlr_log(WLR_INFO, "my_blur_manager_v1 global created");
    return mgr;
}
```

Call `my_blur_manager_create(server->wl_display)` during compositor startup, after `wlr_compositor_create`. The `handle_surface_commit` callback is where you hook your actual render logic — read `surf->current_radius` and `surf->current_passes` in your blur render pass. See Ch 45 for wlroots render pass integration.

---

## 46.6 Protocol Versioning

Wayland versioning is additive only. You may add new requests and events to an existing interface in a version bump; you may never remove or reorder them. The wire protocol uses integer opcode indices, so adding a request at opcode 3 when the interface previously had opcodes 0–2 is safe. Removing opcode 2 and renumbering would break all existing clients.

The version negotiation happens at bind time: the client calls `wl_registry_bind` with a version number, and the compositor creates the resource at `min(offered_version, requested_version)`. Code that uses a feature introduced in version 2 must check `wl_resource_get_version(resource) >= 2` before calling the corresponding `send_*` function or accepting the new request.

| Version bump type | What you can add |
|---|---|
| Patch (internal) | Nothing wire-visible; only implementation fixes |
| Minor (version N+1) | New requests and events at the end of each interface |
| Major (new interface) | Completely new interface name (e.g., `my_blur_manager_v2`) |

When adding a feature in version 2, annotate the XML with `since="2"`:

```xml
<interface name="my_blur_surface_v1" version="2">
  <!-- existing v1 requests and events ... -->

  <request name="set_noise_strength" since="2">
    <description summary="add film grain noise to the blur (v2 feature)"/>
    <arg name="strength" type="uint" summary="noise strength 0-100"/>
  </request>

  <event name="noise_applied" since="2">
    <arg name="actual_strength" type="uint"/>
  </event>
</interface>
```

In server code, guard the new request handler:

```c
static void surface_handle_set_noise(struct wl_client *client,
    struct wl_resource *resource, uint32_t strength)
{
    /* This handler is only reachable if the client bound version >= 2,
       so no explicit version check is needed here. wl_resource_get_version()
       is used when conditionally SENDING new events to old clients. */
    struct my_blur_surface *surf = wl_resource_get_user_data(resource);
    surf->noise_strength = strength > 100 ? 100 : strength;
}
```

When sending a version-gated event from the server:

```c
if (wl_resource_get_version(surf->resource) >= 2) {
    my_blur_surface_v1_send_noise_applied(surf->resource,
        surf->noise_strength);
}
```

For major version breaks, create a new interface (`my_blur_manager_v2`) and advertise both globals in parallel during a transition period. This is how `wlr-layer-shell-unstable-v1` eventually became `zwlr_layer_shell_v1` as it stabilized, and how upstream protocols moved from `xdg-shell-v5` to `xdg-shell-v6` to the stable `xdg-wm-base`.

---

## 46.7 Real-World Example: Full Blur Protocol Walkthrough

This section stitches together all the pieces into a complete build. The directory structure for an in-tree compositor that ships the blur protocol:

```
my-compositor/
├── meson.build
├── protocol/
│   └── my-compositor-blur-v1.xml
├── src/
│   ├── main.c
│   ├── server.h
│   ├── blur_server.c          # §46.5 code
│   └── render.c               # uses current_radius/current_passes
└── test-client/
    └── blur_client.c          # §46.4 code
```

Top-level `meson.build` excerpt:

```meson
project('my-compositor', 'c', default_options: ['c_std=c11'])

wayland_server  = dependency('wayland-server',  version: '>=1.22')
wayland_client  = dependency('wayland-client',  version: '>=1.22')
wlroots         = dependency('wlroots',         version: '>=0.17')
wayland_scanner = find_program('wayland-scanner')

blur_xml = files('protocol/my-compositor-blur-v1.xml')

blur_server_h = custom_target('blur-server-h',
  input: blur_xml, output: 'my-compositor-blur-v1-server-protocol.h',
  command: [wayland_scanner, 'server-header', '@INPUT@', '@OUTPUT@'])

blur_client_h = custom_target('blur-client-h',
  input: blur_xml, output: 'my-compositor-blur-v1-client-protocol.h',
  command: [wayland_scanner, 'client-header', '@INPUT@', '@OUTPUT@'])

blur_proto_c = custom_target('blur-proto-c',
  input: blur_xml, output: 'my-compositor-blur-v1-protocol.c',
  command: [wayland_scanner, 'private-code', '@INPUT@', '@OUTPUT@'])

compositor_srcs = ['src/main.c', 'src/blur_server.c', 'src/render.c',
                   blur_proto_c]
executable('my-compositor', compositor_srcs,
  dependencies: [wayland_server, wlroots],
  sources: [blur_server_h],
  install: true)

test_client_srcs = ['test-client/blur_client.c', blur_proto_c]
executable('blur-test-client', test_client_srcs,
  dependencies: [wayland_client],
  sources: [blur_client_h],
  install: false)
```

Build and run:

```bash
# Configure (requires Meson >= 0.60)
meson setup build --buildtype=debugoptimized

# Build everything
ninja -C build

# Launch the compositor (assumes a seat is available, e.g., via wlr-dev-env)
WAYLAND_DEBUG=1 ./build/my-compositor &

# In a second terminal, test the client
WAYLAND_DISPLAY=wayland-1 ./build/blur-test-client
```

Set `WAYLAND_DEBUG=1` to see every request and event on the socket; this is invaluable for debugging new protocols. Each line shows the object ID, opcode, and decoded arguments.

In `src/render.c`, integrate the blur into the render pass. With wlroots and `wlr_scene`:

```c
/* In your output frame handler, before scene render */
struct my_blur_surface *surf;
wl_list_for_each(surf, &server->blur_manager->surfaces, link) {
    if (surf->current_radius == 0) continue;
    struct wlr_box box;
    wlr_surface_get_extends(surf->wlr_surface, &box);
    /* Call your GPU blur pass with box + current_radius + current_passes */
    render_blur_region(renderer, &box,
                       surf->current_radius, surf->current_passes);
}
```

The blur state is read after commit, so it is always synchronized with the surface buffer — the double-buffered commit model ensures no tearing between buffer updates and blur parameter changes.

---

## 46.8 Protocol Versioning Best Practices

Practical versioning rules observed in well-maintained compositor protocols:

- **Never break wire compatibility.** If you need to remove a request, add a new interface version. Old request handlers remain in the implementation; route old-version resources to a no-op.
- **Document the since version in comments.** Generated code does not surface `since` annotations well in C; add explicit comments.
- **Use error codes generously.** Post protocol errors rather than silently ignoring bad input. Clients catch protocol errors in `wl_display_dispatch` error callbacks.
- **Test with old clients.** When adding a version 2 feature, ensure version 1 clients still function by running them against a server that supports both versions.
- **Coordinate version bumps with protocol consumers.** If multiple applications use your protocol, tag a release before bumping the version to give them time to update.

---

## 46.9 Upstreaming Protocols

If your protocol extension is general enough to benefit the broader Wayland ecosystem, consider submitting it to `wayland-protocols` or `wlr-protocols`.

The `wayland-protocols` repository at `gitlab.freedesktop.org/wayland/wayland-protocols` organizes protocols into three tiers:

| Tier | Stability guarantee | Path to promotion |
|---|---|---|
| `staging/` | Implemented by two independent compositors | Two implementations + no breaking changes |
| `stable/` | Final; will not change | Graduation from staging after review period |
| `deprecated/` | Superseded; no new implementations | N/A |

Submission process:

```bash
# 1. Fork the repo
git clone https://gitlab.freedesktop.org/wayland/wayland-protocols.git
cd wayland-protocols

# 2. Create a branch
git checkout -b add-my-blur-protocol

# 3. Copy your XML into staging/
mkdir -p staging/my-blur/
cp ~/my-compositor-blur-v1.xml staging/my-blur/my-blur-v1.xml
echo 'my-blur-v1.xml' > staging/my-blur/meson.build  # simplified

# 4. Follow the contribution template (CONTRIBUTING.md)
# 5. Open a merge request with a rationale, two compositor implementations,
#    and a link to a real-world application using the protocol.
```

Requirements for staging submission per the contributing guide:
- At least one working compositor implementation (ideally two independent ones)
- At least one working client implementation
- No stable alternatives already in the repository
- Clear description of the use case and why existing protocols are insufficient
- Protocol follows naming conventions: `<noun>-<v1/v2>` in snake_case

For `wlr-protocols` (at `gitlab.freedesktop.org/wlroots/wlr-protocols`), the bar is lower: one wlroots implementation and one client. This is the right target for wlroots-specific features that are not compositer-agnostic.

---

## 46.10 Testing and Debugging Protocol Extensions

Robust testing of a new protocol involves both unit-level argument validation and integration tests with a real compositor and client.

Use `weston-info` or `wayland-info` to inspect globals advertised by a running compositor:

```bash
# List all advertised Wayland globals and their versions
WAYLAND_DISPLAY=wayland-1 wayland-info

# Example output line for your protocol:
#   interface: 'my_blur_manager_v1', version: 1, name: 14
```

Use `WAYLAND_DEBUG=1` for wire-level tracing:

```bash
WAYLAND_DEBUG=1 WAYLAND_DISPLAY=wayland-1 ./blur-test-client 2>&1 | head -60
# Shows each message: [timestamp] id@interface.request_or_event(args)
```

For structured fuzz testing of the server-side request handlers, `wl-shm-fuzz` and custom libfuzzer harnesses can send arbitrary opcodes and argument combinations. At minimum, write a test client that sends out-of-range values and confirms the expected error codes:

```bash
# Verify the bad_radius error is sent for radius=999
# (requires a test client that calls set_radius(999) and catches the error)
WAYLAND_DISPLAY=wayland-1 ./blur-test-client --test-bad-radius 2>&1
# Expected: wl_display error: my_blur_surface_v1@5: bad_radius (0)
```

Check that the protocol code compiles cleanly without warnings at `-Wall -Wextra`:

```bash
ninja -C build 2>&1 | grep -E 'warning:|error:'
```

Use `valgrind` or `sanitizers` to catch resource leaks in the server:

```bash
ASAN_OPTIONS=detect_leaks=1 ./build/my-compositor &
WAYLAND_DISPLAY=wayland-1 ./build/blur-test-client
# Then kill the compositor and check for leak reports
```

---

## Troubleshooting

**`wl_registry_bind` returns NULL for my interface.**
The compositor is not advertising the global. Confirm `my_blur_manager_create` is being called at compositor startup, before any clients connect. Use `wayland-info` to see what globals are actually advertised. Also check that you are comparing interface names with `strcmp`, not pointer equality.

**Client crashes with `wl_proxy_marshal_flags: assertion failed`.**
The proxy is NULL, meaning the `wl_registry_bind` call failed or was not reached. Add a NULL guard after binding and print a clear error. Also check that the interface version you pass to `wl_registry_bind` does not exceed what the compositor offers.

**`my_blur_surface_v1_send_compositor_capabilities` causes a compositor segfault.**
The resource pointer is invalid or has already been destroyed. Check that the `compositor_capabilities` event is sent inside the `manager_handle_get_blur` function before any other operations on the resource, and that the resource was successfully created (`!= NULL`).

**`WAYLAND_DEBUG` shows the request being sent but the server never calls the handler.**
The `wl_message` dispatch table in the generated private code does not match your implementation table. This happens when the XML and generated code are out of sync — regenerate `*-protocol.c` and headers, then rebuild.

**Protocol error `already_constructed` fires even though I only call `get_blur` once.**
A previous client connection left a resource alive (possible if the client crashed without calling `destroy`). The compositor should clean up resources when the client disconnects; verify that `surface_destroy` and `surface_commit` listeners remove the entry from `mgr->surfaces` before freeing.

**Version mismatch: server supports v2 features but client only binds v1.**
This is expected and correct. The server guards v2 events with `wl_resource_get_version(resource) >= 2`. If the client needs v2 features, it must bind at version 2 in `wl_registry_bind`. Update the client-side bind call to request the desired version, and check `wl_proxy_get_version(proxy)` at runtime to confirm.

---

*See also:*
- *Ch 43 — The Wayland Object Model and Wire Protocol*
- *Ch 44 — Building a Compositor with wlroots*
- *Ch 45 — wlroots Render Passes and Scene Graph*
- *Ch 47 — xdg-shell Deep Dive*
- *Ch 53 — Session Startup and Compositor Autolaunch*

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
