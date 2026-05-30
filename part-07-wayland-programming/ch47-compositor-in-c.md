# Chapter 47 — Building a Minimal Compositor with wlroots (C)

## Contents

- [Overview](#overview)
- [47.1 Project Setup](#471-project-setup)
- [47.2 Core Structures](#472-core-structures)
- [47.3 Initialization](#473-initialization)
- [47.4 Output Handling](#474-output-handling)
- [47.5 The XDG Shell: Window Management](#475-the-xdg-shell-window-management)
- [47.6 Input: Cursor and Keyboard](#476-input-cursor-and-keyboard)
- [47.7 Adding Tiling Layout](#477-adding-tiling-layout)
- [47.8 Layer Shell for Bars and Widgets](#478-layer-shell-for-bars-and-widgets)
- [47.9 The Render Loop](#479-the-render-loop)
- [47.10 Protocol Compliance and Debugging](#4710-protocol-compliance-and-debugging)
- [47.11 Study Resources](#4711-study-resources)
- [Troubleshooting](#troubleshooting)

---


## Overview

Building a Wayland compositor from scratch is one of the most technically demanding tasks in the Linux desktop ecosystem. Unlike X11 window managers, which could hook into an existing server, a Wayland compositor must simultaneously implement the display server, the window manager, and the compositing engine. The wlroots library exists to make this tractable: it abstracts away DRM/KMS, libinput, EGL, Vulkan, and dozens of Wayland protocol extensions into a coherent, well-documented API that you can build on top of in a few thousand lines of C.

This chapter takes you from zero to a working, interactive compositor. You will handle real monitor output, keyboard and pointer input, XDG shell windows, layer-shell bars, and a simple tiling layout — all the building blocks of a production compositor like Sway, Wayfire, or Hyprland. The canonical reference implementation is `tinywl`, shipped with wlroots itself; we follow its structure closely and then extend it.

Refer to **Ch 45** for background on the Wayland wire protocol and object model. See **Ch 46** for building Wayland clients with libwayland-client, which provides useful context for what your compositor's clients expect. Session startup integration is covered in **Ch 53**.

---

## 47.1 Project Setup

wlroots is a compositor toolkit maintained by the freedesktop.org community. As of wlroots 0.18, it ships as a pkg-config library and requires a relatively recent kernel (6.1+ recommended for DRM leasing and explicit sync). On Arch Linux, install `wlroots` from the official repos; on Ubuntu 24.04+, install `libwlroots-dev`. You also need `wayland-server`, `xkbcommon`, and `libdrm` development headers.

The recommended build system for wlroots-based compositors is Meson. It integrates cleanly with pkg-config dependency discovery and generates compile_commands.json for IDE/LSP support. Here is a minimal `meson.build` that compiles a single-file compositor:

```meson
# meson.build
project('my-compositor', 'c',
  version : '0.1.0',
  default_options : ['c_std=c11', 'warning_level=2'])

wlroots_dep    = dependency('wlroots-0.18')
wayland_dep    = dependency('wayland-server')
xkbcommon_dep  = dependency('xkbcommon')
math_dep       = meson.get_compiler('c').find_library('m', required: false)

executable('my-compositor',
  sources : ['main.c', 'output.c', 'input.c', 'xdg.c', 'layer.c'],
  dependencies : [wlroots_dep, wayland_dep, xkbcommon_dep, math_dep])
```

Set up and build the project with:

```bash
# Install dependencies (Arch)
sudo pacman -S wlroots wayland wayland-protocols xkbcommon meson ninja libdrm

# Install dependencies (Ubuntu 24.04+)
sudo apt install libwlroots-dev libwayland-dev libxkbcommon-dev \
     meson ninja-build libdrm-dev wayland-protocols

# Bootstrap the build
meson setup build --buildtype=debugoptimized
ninja -C build

# Run inside an existing Wayland session or a virtual KMS device
WLR_BACKENDS=headless ./build/my-compositor
# Or, to use a real DRM device without a nested session:
sudo ./build/my-compositor
```

For rapid iteration, set `WLR_RENDERER=pixman` to bypass GPU rendering entirely and `WLR_BACKENDS=headless` to run without real hardware. Once things work, remove those overrides and test against real DRM/KMS output.

---

## 47.2 Core Structures

Every wlroots compositor revolves around a central server struct that aggregates all wlroots object pointers and wayland-server listeners. Listeners are the event-driven backbone of the compositor: rather than polling, you attach `wl_listener` members to your struct and call `wl_signal_add()` to subscribe to events emitted by wlroots objects.

The struct below captures the full state of a minimal but feature-complete compositor. Each field corresponds to a distinct subsystem. Keep it in a header so all translation units can see it:

```c
/* server.h */
#ifndef SERVER_H
#define SERVER_H

#include <wayland-server-core.h>
#include <wlr/backend.h>
#include <wlr/render/allocator.h>
#include <wlr/render/wlr_renderer.h>
#include <wlr/scene/scene.h>
#include <wlr/types/wlr_compositor.h>
#include <wlr/types/wlr_cursor.h>
#include <wlr/types/wlr_data_device.h>
#include <wlr/types/wlr_idle_notify_v1.h>
#include <wlr/types/wlr_input_device.h>
#include <wlr/types/wlr_keyboard.h>
#include <wlr/types/wlr_layer_shell_v1.h>
#include <wlr/types/wlr_output.h>
#include <wlr/types/wlr_output_layout.h>
#include <wlr/types/wlr_pointer.h>
#include <wlr/types/wlr_seat.h>
#include <wlr/types/wlr_subcompositor.h>
#include <wlr/types/wlr_xcursor_manager.h>
#include <wlr/types/wlr_xdg_shell.h>

struct my_server {
    /* Wayland core */
    struct wl_display          *wl_display;
    struct wl_event_loop       *wl_event_loop;

    /* wlroots backend + rendering pipeline */
    struct wlr_backend         *backend;
    struct wlr_renderer        *renderer;
    struct wlr_allocator       *allocator;

    /* Scene graph: the retained-mode rendering tree */
    struct wlr_scene           *scene;
    struct wlr_scene_output_layout *scene_layout;
    /* One scene tree per ZWLR_LAYER_SHELL_V1_LAYER_* value (0–3) */
    struct wlr_scene_tree      *layers[4];

    /* Shell protocols */
    struct wlr_xdg_shell       *xdg_shell;
    struct wlr_layer_shell_v1  *layer_shell;

    /* Output geometry */
    struct wlr_output_layout   *output_layout;

    /* Cursor + seat */
    struct wlr_cursor          *cursor;
    struct wlr_xcursor_manager *cursor_mgr;
    struct wlr_seat            *seat;

    /* Connected object lists */
    struct wl_list outputs;     /* my_output.link */
    struct wl_list toplevels;   /* my_toplevel.link */
    struct wl_list keyboards;   /* my_keyboard.link */

    /* Global listeners */
    struct wl_listener new_output;
    struct wl_listener new_input;
    struct wl_listener new_xdg_toplevel;
    struct wl_listener new_layer_surface;
    struct wl_listener cursor_motion;
    struct wl_listener cursor_motion_absolute;
    struct wl_listener cursor_button;
    struct wl_listener cursor_axis;
    struct wl_listener cursor_frame;
    struct wl_listener request_cursor;
    struct wl_listener request_set_selection;
};

struct my_output {
    struct wl_list link;
    struct my_server *server;
    struct wlr_output *wlr_output;
    struct wl_listener frame;
    struct wl_listener request_state;
    struct wl_listener destroy;
};

struct my_toplevel {
    struct wl_list link;
    struct my_server *server;
    struct wlr_xdg_toplevel *xdg_toplevel;
    struct wlr_scene_tree *scene_tree;
    struct wl_listener map;
    struct wl_listener unmap;
    struct wl_listener commit;
    struct wl_listener destroy;
    struct wl_listener request_move;
    struct wl_listener request_resize;
    struct wl_listener request_maximize;
};

struct my_keyboard {
    struct wl_list link;        /* my_server.keyboards */
    struct my_server *server;
    struct wlr_keyboard *wlr_keyboard;
    struct wl_listener modifiers;
    struct wl_listener key;
    struct wl_listener destroy;
};

#endif /* SERVER_H */
```

Notice the pattern: each struct embeds `wl_listener` members directly, and wlroots helper macros (`wl_container_of`) recover the containing struct from a listener pointer at event time. This zero-allocation approach is idiomatic wlroots code.

---

## 47.3 Initialization

The initialization sequence must follow a strict ordering: create the Wayland display, then the backend (which discovers DRM devices and libinput), then the renderer and allocator (which depend on the backend knowing which GPU to use), then the scene graph, and finally register all global Wayland interfaces. Deviating from this order causes cryptic null-pointer crashes.

```c
/* main.c — initialization */
#include "server.h"
#include <wlr/util/log.h>
#include <stdlib.h>
#include <unistd.h>

int main(int argc, char *argv[]) {
    wlr_log_init(WLR_DEBUG, NULL);

    struct my_server server = {0};

    /* 1. Wayland display + event loop */
    server.wl_display    = wl_display_create();
    server.wl_event_loop = wl_display_get_event_loop(server.wl_display);

    /* 2. Backend: auto-detects DRM+libinput or falls back to X11/Wayland nesting */
    server.backend = wlr_backend_autocreate(server.wl_event_loop, NULL);
    if (!server.backend) {
        wlr_log(WLR_ERROR, "failed to create backend");
        return 1;
    }

    /* 3. Renderer + display integration */
    server.renderer = wlr_renderer_autocreate(server.backend);
    wlr_renderer_init_wl_display(server.renderer, server.wl_display);

    /* 4. Allocator: bridges renderer and backend buffer formats */
    server.allocator = wlr_allocator_autocreate(server.backend, server.renderer);

    /* 5. Output layout: tracks monitor geometry in compositor-space */
    server.output_layout = wlr_output_layout_create(server.wl_display);

    /* 6. Scene graph: retained-mode rendering tree */
    server.scene = wlr_scene_create();
    server.scene_layout = wlr_scene_attach_output_layout(
        server.scene, server.output_layout);
    /* Create one child tree per layer-shell layer (background/bottom/top/overlay) */
    for (int i = 0; i < 4; i++) {
        server.layers[i] = wlr_scene_tree_create(&server.scene->tree);
    }

    /* 7. Register core Wayland globals */
    wlr_compositor_create(server.wl_display, 5, server.renderer);
    wlr_subcompositor_create(server.wl_display);
    wlr_data_device_manager_create(server.wl_display);

    /* 8. Shell protocols */
    server.xdg_shell = wlr_xdg_shell_create(server.wl_display, 3);
    server.layer_shell = wlr_layer_shell_v1_create(server.wl_display, 4);

    /* 9. Cursor + seat */
    server.cursor = wlr_cursor_create();
    wlr_cursor_attach_output_layout(server.cursor, server.output_layout);
    server.cursor_mgr = wlr_xcursor_manager_create(NULL, 24);
    wlr_xcursor_manager_load(server.cursor_mgr, 1.0f);
    server.seat = wlr_seat_create(server.wl_display, "seat0");

    /* 10. Wire up listeners (defined in other TUs) */
    server_setup_output_listeners(&server);
    server_setup_input_listeners(&server);
    server_setup_xdg_listeners(&server);
    server_setup_layer_listeners(&server);

    /* 11. Start backend: opens DRM device, begins libinput polling */
    if (!wlr_backend_start(server.backend)) {
        wlr_log(WLR_ERROR, "failed to start backend");
        wl_display_destroy(server.wl_display);
        return 1;
    }

    /* 12. Bind a UNIX socket and set WAYLAND_DISPLAY */
    const char *socket = wl_display_add_socket_auto(server.wl_display);
    setenv("WAYLAND_DISPLAY", socket, true);
    wlr_log(WLR_INFO, "Running on WAYLAND_DISPLAY=%s", socket);

    /* 13. Optionally launch a terminal */
    if (fork() == 0) {
        execl("/bin/sh", "/bin/sh", "-c", "foot", NULL);
    }

    /* 14. Enter the event loop */
    wl_display_run(server.wl_display);

    wl_display_destroy_clients(server.wl_display);
    wl_display_destroy(server.wl_display);
    return 0;
}
```

Key insight: `wlr_backend_autocreate` inspects the environment at runtime. If `WAYLAND_DISPLAY` is already set, it creates a nested Wayland backend. If `DISPLAY` is set, it uses X11. Otherwise, it opens the DRM device directly. This lets you develop and test your compositor inside an existing session, then deploy it on bare hardware with no code changes.

---

## 47.4 Output Handling

Outputs in wlroots represent physical or virtual displays. The `new_output` signal fires whenever the backend discovers a monitor — at startup for all currently connected displays, and again whenever a hotplug event arrives. Your listener must configure the output's mode and attach it to the scene graph before the first frame can be rendered.

The `request_state` signal is wlroots's unified way of delivering mode-switch requests, VRR enable/disable, and power-state changes. In a minimal compositor you can honour them unconditionally:

```c
/* output.c */
#include "server.h"
#include <wlr/types/wlr_output.h>
#include <wlr/types/wlr_output_layout.h>
#include <wlr/scene/scene.h>

static void output_frame(struct wl_listener *listener, void *data) {
    struct my_output *output = wl_container_of(listener, output, frame);
    struct wlr_scene *scene  = output->server->scene;

    struct wlr_scene_output *scene_output =
        wlr_scene_get_scene_output(scene, output->wlr_output);

    /* Render the scene graph to this output's framebuffer */
    wlr_scene_output_commit(scene_output, NULL);

    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    wlr_scene_output_send_frame_done(scene_output, &now);
}

static void output_request_state(struct wl_listener *listener, void *data) {
    struct my_output *output = wl_container_of(listener, output, request_state);
    const struct wlr_output_event_request_state *event = data;
    wlr_output_commit_state(output->wlr_output, event->state);
}

static void output_destroy(struct wl_listener *listener, void *data) {
    struct my_output *output = wl_container_of(listener, output, destroy);
    wl_list_remove(&output->frame.link);
    wl_list_remove(&output->request_state.link);
    wl_list_remove(&output->destroy.link);
    wl_list_remove(&output->link);
    free(output);
}

static void server_new_output(struct wl_listener *listener, void *data) {
    struct my_server *server      = wl_container_of(listener, server, new_output);
    struct wlr_output *wlr_output = data;

    /* Assign the renderer+allocator pair to this output */
    wlr_output_init_render(wlr_output, server->allocator, server->renderer);

    /* Pick the preferred mode (highest resolution + refresh the driver reports) */
    struct wlr_output_state state;
    wlr_output_state_init(&state);
    wlr_output_state_set_enabled(&state, true);

    struct wlr_output_mode *mode = wlr_output_preferred_mode(wlr_output);
    if (mode) {
        wlr_output_state_set_mode(&state, mode);
    }
    wlr_output_commit_state(wlr_output, &state);
    wlr_output_state_finish(&state);

    /* Allocate and register the output wrapper */
    struct my_output *output = calloc(1, sizeof(*output));
    output->wlr_output = wlr_output;
    output->server     = server;

    output->frame.notify          = output_frame;
    output->request_state.notify  = output_request_state;
    output->destroy.notify         = output_destroy;
    wl_signal_add(&wlr_output->events.frame,         &output->frame);
    wl_signal_add(&wlr_output->events.request_state, &output->request_state);
    wl_signal_add(&wlr_output->events.destroy,       &output->destroy);

    wl_list_insert(&server->outputs, &output->link);

    /* Place the output at the next available position in layout-space */
    struct wlr_output_layout_output *lo =
        wlr_output_layout_add_auto(server->output_layout, wlr_output);

    /* Register the output with the scene graph so wlr_scene_get_scene_output
     * (called in output_frame) can find it; without this, output_frame renders
     * nothing. */
    struct wlr_scene_output *scene_output =
        wlr_scene_output_create(server->scene, wlr_output);
    wlr_scene_output_layout_add_output(server->scene_layout, lo, scene_output);
}

void server_setup_output_listeners(struct my_server *server) {
    wl_list_init(&server->outputs);
    server->new_output.notify = server_new_output;
    wl_signal_add(&server->backend->events.new_output, &server->new_output);
}
```

`wlr_output_layout_add_auto` places the new monitor immediately to the right of existing monitors in compositor-space. You can replace this with explicit positioning — `wlr_output_layout_add(layout, output, x, y)` — when reading monitor configurations from a config file.

---

## 47.5 The XDG Shell: Window Management

XDG shell is the primary protocol through which desktop applications create toplevel windows. It is a two-stage process: a client first creates an `xdg_surface` wrapper around a `wl_surface`, then promotes it to an `xdg_toplevel` (a regular window) or an `xdg_popup` (a dropdown or context menu). Your compositor must handle both.

The `map`/`unmap` events are the moment a surface becomes visible or is hidden. Only mapped surfaces should receive input or be included in the scene graph's visible set. The `commit` event fires every time the client submits a new buffer; you may need to re-run layout here.

```c
/* xdg.c */
#include "server.h"
#include <wlr/types/wlr_xdg_shell.h>
#include <wlr/scene/scene.h>

/* Focus a toplevel: raise it in z-order, set keyboard focus */
static void focus_toplevel(struct my_toplevel *toplevel,
                           struct wlr_surface *surface) {
    struct my_server *server = toplevel->server;
    struct wlr_seat  *seat   = server->seat;

    struct wlr_surface *prev = seat->keyboard_state.focused_surface;
    if (prev == surface) return;

    /* Deactivate previously focused toplevel */
    if (prev) {
        struct wlr_xdg_toplevel *prev_top =
            wlr_xdg_toplevel_try_from_wlr_surface(prev);
        if (prev_top) {
            wlr_xdg_toplevel_set_activated(prev_top, false);
        }
    }

    /* Raise the new toplevel in the scene tree */
    wlr_scene_node_raise_to_top(&toplevel->scene_tree->node);
    /* Move to front of our list so hit-testing finds it first */
    wl_list_remove(&toplevel->link);
    wl_list_insert(&server->toplevels, &toplevel->link);

    wlr_xdg_toplevel_set_activated(toplevel->xdg_toplevel, true);

    /* Transfer keyboard focus */
    struct wlr_keyboard *keyboard = wlr_seat_get_keyboard(seat);
    if (keyboard) {
        wlr_seat_keyboard_notify_enter(seat, surface,
            keyboard->keycodes, keyboard->num_keycodes,
            &keyboard->modifiers);
    }
}

static void toplevel_map(struct wl_listener *listener, void *data) {
    struct my_toplevel *toplevel = wl_container_of(listener, toplevel, map);
    wl_list_insert(&toplevel->server->toplevels, &toplevel->link);
    focus_toplevel(toplevel, toplevel->xdg_toplevel->base->surface);
}

static void toplevel_unmap(struct wl_listener *listener, void *data) {
    struct my_toplevel *toplevel = wl_container_of(listener, toplevel, unmap);
    wl_list_remove(&toplevel->link);
}

static void toplevel_commit(struct wl_listener *listener, void *data) {
    struct my_toplevel *toplevel = wl_container_of(listener, toplevel, commit);
    /* In a tiling compositor, re-run layout when window size changes */
    if (toplevel->xdg_toplevel->base->initial_commit) {
        wlr_xdg_toplevel_set_size(toplevel->xdg_toplevel, 0, 0);
    }
}

static void toplevel_destroy(struct wl_listener *listener, void *data) {
    struct my_toplevel *toplevel = wl_container_of(listener, toplevel, destroy);
    wl_list_remove(&toplevel->map.link);
    wl_list_remove(&toplevel->unmap.link);
    wl_list_remove(&toplevel->commit.link);
    wl_list_remove(&toplevel->destroy.link);
    wl_list_remove(&toplevel->request_move.link);
    wl_list_remove(&toplevel->request_resize.link);
    free(toplevel);
}

static void toplevel_request_move(struct wl_listener *listener, void *data) {
    struct my_toplevel *toplevel = wl_container_of(listener, toplevel, request_move);
    /* In a floating compositor: initiate interactive move */
    /* In a tiling compositor: ignore or convert to float */
    (void)toplevel;
}

static void toplevel_request_resize(struct wl_listener *listener, void *data) {
    struct my_toplevel *toplevel = wl_container_of(listener, toplevel, request_resize);
    const struct wlr_xdg_toplevel_resize_event *event = data;
    (void)toplevel; (void)event;
    /* Implement resize drag handling here */
}

static void server_new_xdg_toplevel(struct wl_listener *listener, void *data) {
    struct my_server       *server      = wl_container_of(listener, server, new_xdg_toplevel);
    struct wlr_xdg_toplevel *xdg_toplevel = data;

    struct my_toplevel *toplevel = calloc(1, sizeof(*toplevel));
    toplevel->server       = server;
    toplevel->xdg_toplevel = xdg_toplevel;

    /* Insert surface into scene graph under the root tree */
    toplevel->scene_tree = wlr_scene_xdg_surface_create(
        &server->scene->tree, xdg_toplevel->base);
    toplevel->scene_tree->node.data = toplevel;
    xdg_toplevel->base->data        = toplevel->scene_tree;

    toplevel->map.notify            = toplevel_map;
    toplevel->unmap.notify          = toplevel_unmap;
    toplevel->commit.notify         = toplevel_commit;
    toplevel->destroy.notify        = toplevel_destroy;
    toplevel->request_move.notify   = toplevel_request_move;
    toplevel->request_resize.notify = toplevel_request_resize;

    wl_signal_add(&xdg_toplevel->base->surface->events.map,     &toplevel->map);
    wl_signal_add(&xdg_toplevel->base->surface->events.unmap,   &toplevel->unmap);
    wl_signal_add(&xdg_toplevel->base->surface->events.commit,  &toplevel->commit);
    wl_signal_add(&xdg_toplevel->events.destroy,                &toplevel->destroy);
    wl_signal_add(&xdg_toplevel->events.request_move,           &toplevel->request_move);
    wl_signal_add(&xdg_toplevel->events.request_resize,         &toplevel->request_resize);
}

void server_setup_xdg_listeners(struct my_server *server) {
    wl_list_init(&server->toplevels);
    server->new_xdg_toplevel.notify = server_new_xdg_toplevel;
    wl_signal_add(&server->xdg_shell->events.new_toplevel,
                  &server->new_xdg_toplevel);
}
```

The configure-ack loop is implicit in wlroots when using `wlr_scene_xdg_surface_create`: the scene graph tracks pending and acknowledged sizes automatically. If you place surfaces manually, you must call `wlr_xdg_surface_schedule_configure` and wait for the client's `ack_configure` before repositioning scene nodes to the new geometry.

---

## 47.6 Input: Cursor and Keyboard

Input handling in wlroots is split across three layers: `wlr_backend` discovers raw input devices (mice, keyboards, tablets); `wlr_cursor` aggregates pointer motion from all pointer devices into a single compositor-space position; and `wlr_seat` implements the `wl_seat` Wayland protocol, which is the interface clients use to receive keyboard, pointer, and touch events.

```c
/* input.c */
#include "server.h"
#include <wlr/types/wlr_keyboard.h>
#include <wlr/types/wlr_pointer.h>
#include <xkbcommon/xkbcommon.h>

/* ---- Keyboard ---- */

static bool handle_keybinding(struct my_server *server, xkb_keysym_t sym) {
    switch (sym) {
    case XKB_KEY_Escape:
        wl_display_terminate(server->wl_display);
        return true;
    case XKB_KEY_F1: {
        /* Cycle focus to next toplevel */
        if (wl_list_length(&server->toplevels) < 2) break;
        struct my_toplevel *next = wl_container_of(
            server->toplevels.prev, next, link);
        focus_toplevel(next, next->xdg_toplevel->base->surface);
        return true;
    }
    default:
        break;
    }
    return false;
}

static void keyboard_handle_modifiers(struct wl_listener *listener, void *data) {
    struct my_keyboard *keyboard = wl_container_of(listener, keyboard, modifiers);
    wlr_seat_set_keyboard(keyboard->server->seat, keyboard->wlr_keyboard);
    wlr_seat_keyboard_notify_modifiers(keyboard->server->seat,
        &keyboard->wlr_keyboard->modifiers);
}

static void keyboard_handle_key(struct wl_listener *listener, void *data) {
    struct my_keyboard *keyboard = wl_container_of(listener, keyboard, key);
    struct my_server   *server   = keyboard->server;
    const struct wlr_keyboard_key_event *event = data;

    /* Translate from evdev scancode to XKB keysym */
    uint32_t keycode = event->keycode + 8;
    const xkb_keysym_t *syms;
    int nsyms = xkb_state_key_get_syms(
        keyboard->wlr_keyboard->xkb_state, keycode, &syms);

    bool handled = false;
    uint32_t mods = wlr_keyboard_get_modifiers(keyboard->wlr_keyboard);

    if ((mods & WLR_MODIFIER_ALT) && event->state == WL_KEYBOARD_KEY_STATE_PRESSED) {
        for (int i = 0; i < nsyms; i++) {
            handled = handle_keybinding(server, syms[i]);
        }
    }

    if (!handled) {
        wlr_seat_set_keyboard(server->seat, keyboard->wlr_keyboard);
        wlr_seat_keyboard_notify_key(server->seat, event->time_msec,
            event->keycode, event->state);
    }
}

static void keyboard_handle_destroy(struct wl_listener *listener, void *data) {
    struct my_keyboard *keyboard = wl_container_of(listener, keyboard, destroy);
    wl_list_remove(&keyboard->modifiers.link);
    wl_list_remove(&keyboard->key.link);
    wl_list_remove(&keyboard->destroy.link);
    wl_list_remove(&keyboard->link);
    free(keyboard);
}

static void server_new_keyboard(struct my_server *server,
                                struct wlr_input_device *device) {
    struct wlr_keyboard *wlr_keyboard = wlr_keyboard_from_input_device(device);

    struct my_keyboard *keyboard = calloc(1, sizeof(*keyboard));
    keyboard->server       = server;
    keyboard->wlr_keyboard = wlr_keyboard;

    /* Configure XKB keymap */
    struct xkb_context *context = xkb_context_new(XKB_CONTEXT_NO_FLAGS);
    struct xkb_keymap  *keymap  = xkb_keymap_new_from_names(
        context, NULL, XKB_KEYMAP_COMPILE_NO_FLAGS);
    wlr_keyboard_set_keymap(wlr_keyboard, keymap);
    xkb_keymap_unref(keymap);
    xkb_context_unref(context);
    wlr_keyboard_set_repeat_info(wlr_keyboard, 25, 600);

    keyboard->modifiers.notify = keyboard_handle_modifiers;
    keyboard->key.notify       = keyboard_handle_key;
    keyboard->destroy.notify   = keyboard_handle_destroy;
    wl_signal_add(&wlr_keyboard->events.modifiers, &keyboard->modifiers);
    wl_signal_add(&wlr_keyboard->events.key,       &keyboard->key);
    wl_signal_add(&device->events.destroy,         &keyboard->destroy);

    wlr_seat_set_keyboard(server->seat, wlr_keyboard);
    wl_list_insert(&server->keyboards, &keyboard->link);
}

/* ---- Pointer / Cursor ---- */

/* Hit-test: find which toplevel is under the cursor */
static struct my_toplevel *
desktop_toplevel_at(struct my_server *server, double lx, double ly,
                    struct wlr_surface **surface, double *sx, double *sy) {
    struct wlr_scene_node *node =
        wlr_scene_node_at(&server->scene->tree.node, lx, ly, sx, sy);
    if (!node || node->type != WLR_SCENE_NODE_BUFFER) return NULL;

    struct wlr_scene_buffer *scene_buffer = wlr_scene_buffer_from_node(node);
    struct wlr_scene_surface *scene_surface =
        wlr_scene_surface_try_from_buffer(scene_buffer);
    if (!scene_surface) return NULL;

    *surface = scene_surface->surface;
    struct wlr_scene_tree *tree = node->parent;
    while (tree && !tree->node.data) tree = tree->node.parent;
    return tree ? tree->node.data : NULL;
}

static void server_cursor_motion(struct wl_listener *listener, void *data) {
    struct my_server *server = wl_container_of(listener, server, cursor_motion);
    const struct wlr_pointer_motion_event *event = data;
    wlr_cursor_move(server->cursor, &event->pointer->base,
                    event->delta_x, event->delta_y);
    /* Update seat pointer focus */
    double sx, sy;
    struct wlr_surface *surface = NULL;
    struct my_toplevel *toplevel = desktop_toplevel_at(server,
        server->cursor->x, server->cursor->y, &surface, &sx, &sy);
    if (toplevel) {
        wlr_seat_pointer_notify_enter(server->seat, surface, sx, sy);
        wlr_seat_pointer_notify_motion(server->seat, event->time_msec, sx, sy);
    } else {
        wlr_cursor_set_xcursor(server->cursor, server->cursor_mgr, "default");
        wlr_seat_pointer_clear_focus(server->seat);
    }
}

static void server_cursor_button(struct wl_listener *listener, void *data) {
    struct my_server *server = wl_container_of(listener, server, cursor_button);
    const struct wlr_pointer_button_event *event = data;
    wlr_seat_pointer_notify_button(server->seat,
        event->time_msec, event->button, event->state);

    if (event->state == WL_POINTER_BUTTON_STATE_PRESSED) {
        double sx, sy;
        struct wlr_surface *surface = NULL;
        struct my_toplevel *toplevel = desktop_toplevel_at(server,
            server->cursor->x, server->cursor->y, &surface, &sx, &sy);
        if (toplevel) focus_toplevel(toplevel, surface);
    }
}

static void server_cursor_axis(struct wl_listener *listener, void *data) {
    struct my_server *server = wl_container_of(listener, server, cursor_axis);
    const struct wlr_pointer_axis_event *event = data;
    wlr_seat_pointer_notify_axis(server->seat, event->time_msec,
        event->orientation, event->delta, event->delta_discrete, event->source,
        event->relative_direction);
}

static void server_cursor_frame(struct wl_listener *listener, void *data) {
    struct my_server *server = wl_container_of(listener, server, cursor_frame);
    wlr_seat_pointer_notify_frame(server->seat);
}

static void server_new_input(struct wl_listener *listener, void *data) {
    struct my_server       *server = wl_container_of(listener, server, new_input);
    struct wlr_input_device *device = data;
    switch (device->type) {
    case WLR_INPUT_DEVICE_KEYBOARD:
        server_new_keyboard(server, device);
        break;
    case WLR_INPUT_DEVICE_POINTER:
        wlr_cursor_attach_input_device(server->cursor, device);
        break;
    default:
        break;
    }
    uint32_t caps = WL_SEAT_CAPABILITY_POINTER;
    if (!wl_list_empty(&server->keyboards)) {
        caps |= WL_SEAT_CAPABILITY_KEYBOARD;
    }
    wlr_seat_set_capabilities(server->seat, caps);
}

void server_setup_input_listeners(struct my_server *server) {
    wl_list_init(&server->keyboards);
    server->new_input.notify              = server_new_input;
    server->cursor_motion.notify          = server_cursor_motion;
    server->cursor_motion_absolute.notify = server_cursor_motion; /* reuse */
    server->cursor_button.notify          = server_cursor_button;
    server->cursor_axis.notify            = server_cursor_axis;
    server->cursor_frame.notify           = server_cursor_frame;

    wl_signal_add(&server->backend->events.new_input,     &server->new_input);
    wl_signal_add(&server->cursor->events.motion,         &server->cursor_motion);
    wl_signal_add(&server->cursor->events.button,         &server->cursor_button);
    wl_signal_add(&server->cursor->events.axis,           &server->cursor_axis);
    wl_signal_add(&server->cursor->events.frame,          &server->cursor_frame);
}
```

The XKB configuration above creates a keymap with the system defaults (reading `$XKB_DEFAULT_LAYOUT`, etc.). To hard-code a layout — e.g., `us` variant `dvorak` — pass a populated `struct xkb_rule_names` to `xkb_keymap_new_from_names`.

---

## 47.7 Adding Tiling Layout

Tiling is implemented as a pure layout function: given the list of mapped toplevels and the available screen geometry, compute each window's `(x, y, width, height)` and apply it. wlroots provides `wlr_xdg_toplevel_set_size` to negotiate the new size with the client via a configure event, and `wlr_scene_node_set_position` to place the scene node once the client acknowledges.

The simplest useful layout is a master–stack arrangement. The first toplevel takes half the screen; remaining toplevels share the other half vertically:

```c
/* layout.c */
#include "server.h"
#include <wlr/types/wlr_output_layout.h>
#include <wlr/types/wlr_xdg_shell.h>
#include <wlr/scene/scene.h>

void apply_tiling_layout(struct my_server *server) {
    /* Find the primary output */
    struct wlr_output *output = wlr_output_layout_get_center_output(
        server->output_layout);
    if (!output) return;

    struct wlr_box usable;
    wlr_output_layout_get_box(server->output_layout, output, &usable);

    int n = wl_list_length(&server->toplevels);
    if (n == 0) return;

    struct my_toplevel *toplevel;
    int i = 0;
    wl_list_for_each(toplevel, &server->toplevels, link) {
        int x, y, w, h;
        if (n == 1) {
            x = usable.x; y = usable.y;
            w = usable.width; h = usable.height;
        } else if (i == 0) {
            /* Master: left half */
            x = usable.x; y = usable.y;
            w = usable.width / 2; h = usable.height;
        } else {
            /* Stack: right half, divided equally */
            int stack_count = n - 1;
            int slot = i - 1;
            x = usable.x + usable.width / 2;
            y = usable.y + (usable.height * slot / stack_count);
            w = usable.width / 2;
            h = usable.height / stack_count;
        }
        wlr_xdg_toplevel_set_size(toplevel->xdg_toplevel, w, h);
        wlr_scene_node_set_position(&toplevel->scene_tree->node, x, y);
        i++;
    }
}
```

Call `apply_tiling_layout` from `toplevel_map`, `toplevel_unmap`, and after any monitor hotplug event. For dwindle layout (like Hyprland's default), recursively bisect the remaining area: the first window takes the left/top half; recurse into the right/bottom half for the remaining windows, alternating split direction at each level.

---

## 47.8 Layer Shell for Bars and Widgets

The `wlr-layer-shell` protocol is used by status bars (Waybar, Yambar), notification daemons, and desktop widget layers. Each layer surface declares which screen edge it anchors to, how much space it reserves (exclusive zone), and which of the four z-layers it occupies (`background`, `bottom`, `top`, `overlay`).

```c
/* layer.c */
#include "server.h"
#include <wlr/types/wlr_layer_shell_v1.h>

struct my_layer_surface {
    struct wlr_layer_surface_v1 *layer_surface;
    struct wlr_scene_layer_surface_v1 *scene_layer;
    struct wl_listener map;
    struct wl_listener unmap;
    struct wl_listener destroy;
};

static void layer_surface_map(struct wl_listener *listener, void *data) {
    struct my_layer_surface *ls = wl_container_of(listener, ls, map);
    wlr_scene_node_set_enabled(&ls->scene_layer->tree->node, true);
}

static void layer_surface_unmap(struct wl_listener *listener, void *data) {
    struct my_layer_surface *ls = wl_container_of(listener, ls, unmap);
    wlr_scene_node_set_enabled(&ls->scene_layer->tree->node, false);
}

static void layer_surface_destroy(struct wl_listener *listener, void *data) {
    struct my_layer_surface *ls = wl_container_of(listener, ls, destroy);
    wl_list_remove(&ls->map.link);
    wl_list_remove(&ls->unmap.link);
    wl_list_remove(&ls->destroy.link);
    free(ls);
}

static void server_new_layer_surface(struct wl_listener *listener, void *data) {
    struct my_server *server = wl_container_of(listener, server, new_layer_surface);
    struct wlr_layer_surface_v1 *layer_surface = data;

    /* Assign to appropriate scene tree layer (compositor-owned, not wlr_scene) */
    struct wlr_scene_tree *layer_tree =
        server->layers[layer_surface->pending.layer];

    struct my_layer_surface *ls = calloc(1, sizeof(*ls));
    ls->layer_surface = layer_surface;
    ls->scene_layer   = wlr_scene_layer_surface_v1_create(layer_tree, layer_surface);
    ls->scene_layer->tree->node.data = ls;

    ls->map.notify     = layer_surface_map;
    ls->unmap.notify   = layer_surface_unmap;
    ls->destroy.notify = layer_surface_destroy;
    wl_signal_add(&layer_surface->surface->events.map,    &ls->map);
    wl_signal_add(&layer_surface->surface->events.unmap,  &ls->unmap);
    wl_signal_add(&layer_surface->events.destroy,         &ls->destroy);

    /* Negotiate the initial size by sending a configure */
    struct wlr_output *output = layer_surface->output;
    if (!output) {
        output = wlr_output_layout_get_center_output(server->output_layout);
        layer_surface->output = output;
    }
    struct wlr_box output_box;
    wlr_output_layout_get_box(server->output_layout, output, &output_box);
    wlr_layer_surface_v1_configure(layer_surface,
        output_box.width, output_box.height);
}

void server_setup_layer_listeners(struct my_server *server) {
    server->new_layer_surface.notify = server_new_layer_surface;
    wl_signal_add(&server->layer_shell->events.new_surface,
                  &server->new_layer_surface);
}
```

In a production compositor, exclusive zones must be computed and subtracted from the usable area before running the tiling layout. wlroots 0.18 ships `wlr_scene_layer_surface_v1` which handles scene placement, but you still need to track the exclusive zone deltas and apply them to `apply_tiling_layout`'s usable-area calculation.

---

## 47.9 The Render Loop

wlroots uses a pull-based render model: the kernel (via the DRM vsync interrupt) fires the `frame` event on each `wlr_output` at the appropriate time. Your compositor should only render when this event fires. Rendering outside the frame event — e.g., in response to client commits — will cause tearing or missed vsyncs.

`wlr_scene_output_commit` does all the work: it walks the scene graph, determines what changed since the last frame, and issues the minimal set of GPU commands to produce the output image. With wlroots's damage tracking, unchanged regions are not redrawn. After commit, `wlr_scene_output_send_frame_done` sends the `wl_surface.frame` callback to all surfaces that were rendered, informing clients that they may submit the next frame.

| Function | Purpose |
|---|---|
| `wlr_scene_output_commit` | Render the scene graph to one output's framebuffer |
| `wlr_scene_output_send_frame_done` | Notify clients their frame was composited |
| `wlr_output_commit_state` | Apply a pending output-state change (mode, transform) |
| `wlr_scene_node_set_position` | Move a scene node without a full redraw |
| `wlr_scene_node_set_enabled` | Show/hide a scene node |
| `wlr_scene_rect_create` | Draw a solid-color rectangle (e.g., borders) |

For VRR (variable refresh rate) support, set `WLR_OUTPUT_STATE_ADAPTIVE_SYNC_ENABLED` in your `wlr_output_state` before commit. The backend will enable freesync/g-sync if the driver supports it for that output.

---

## 47.10 Protocol Compliance and Debugging

A compliant compositor must implement several Wayland protocols beyond XDG shell. The table below lists the most important ones and their wlroots helpers:

| Protocol | wlroots API | Purpose |
|---|---|---|
| `wl_compositor` | `wlr_compositor_create` | Surface creation |
| `wl_subcompositor` | `wlr_subcompositor_create` | Sub-surfaces |
| `wl_data_device_manager` | `wlr_data_device_manager_create` | Clipboard |
| `xdg-output-unstable-v1` | `wlr_xdg_output_manager_v1_create` | Output info for clients |
| `wlr-screencopy-unstable-v1` | `wlr_screencopy_manager_v1_create` | Screen capture |
| `wlr-foreign-toplevel-management` | `wlr_foreign_toplevel_manager_v1_create` | Taskbar integration |
| `ext-idle-notify-v1` | `wlr_idle_notifier_v1_create` | Idle inhibition |
| `wp-cursor-shape-v1` | `wlr_cursor_shape_manager_v1_create` | Client-driven cursor icons |
| `xdg-decoration-unstable-v1` | `wlr_xdg_decoration_manager_v1_create` | CSD/SSD negotiation |

Add these to your init sequence after the core protocols. Each requires only a one-line create call and the wlroots scene graph handles the rest automatically for most of them.

---

## 47.11 Study Resources

The best way to learn is to read working code alongside the wlroots headers. The resources below are ordered from most to least essential:

- **`tinywl`** — the official minimal compositor, ~700 lines: `https://gitlab.freedesktop.org/wlroots/wlroots/-/tree/master/tinywl`
- **`simplewc`** — a single-file compositor with tiling: `https://github.com/kcirick/simplewc`
- **`dwl`** — a dwm port to Wayland, very readable: `https://codeberg.org/dwl/dwl`
- **wlroots Doxygen** — generated from source, always in sync: `https://gitlab.freedesktop.org/wlroots/wlroots`
- **`way-cooler` book** — conceptual overview of compositor design: `http://way-cooler.org/book/`
- **Wayland book** — protocol internals: `https://wayland-book.com/`

Cross-reference: **Ch 45** covers the Wayland wire protocol. **Ch 48** extends this compositor with XWayland support. **Ch 53** covers session startup with `systemd --user` and `dinit`.

---

## Troubleshooting

**Compositor crashes immediately with "failed to create backend"**
Set `WLR_BACKENDS=headless` to test without hardware, or check that `/dev/dri/card0` is accessible. If running as non-root, add your user to the `video` and `input` groups: `sudo usermod -aG video,input $USER`.

**Black screen / no output rendered**
Ensure `wlr_output_init_render` is called before `wlr_output_commit_state` in `server_new_output`. Missing this call means the output has no renderer attached and commit silently fails.

**Keyboard input not forwarded to clients**
Verify `wlr_seat_set_keyboard` is called before `wlr_seat_keyboard_notify_enter`. The seat must know which keyboard device to associate with the focused surface.

**`wlr_scene_xdg_surface_create` returns NULL**
This happens if `wlr_compositor_create` was not called before the XDG shell created surfaces. Check initialization order.

**Clients crash with "xdg_wm_base: no ack_configure"**
The client sent a configure serial and expects acknowledgment before the next commit. wlroots handles this automatically when using the scene-graph integration; if you manage surfaces manually, call `wlr_xdg_surface_schedule_configure` and await `ack_configure`.

**High CPU usage / no damage tracking**
Confirm `wlr_scene_output_send_frame_done` is called after every `wlr_scene_output_commit`. Without it, clients keep submitting frames as fast as possible because they never receive the frame callback.

**Nested compositor works but DRM fails**
Check kernel logs with `dmesg | grep drm`. Common causes: another compositor holds the DRM master lock, or the GPU is not supported by the selected renderer. Try `WLR_RENDERER=pixman` to force software rendering.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
