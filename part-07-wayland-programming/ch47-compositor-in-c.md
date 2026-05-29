# Chapter 47 — Building a Minimal Compositor with wlroots (C)

## Overview
Build a real, working Wayland compositor from scratch using wlroots. Based on the
`tinywl` reference and extended with common features.

## Sections

### 47.1 Project Setup
```c
// Dependencies: wlroots, wayland-server, xkbcommon
// Meson build system
project('my-compositor', 'c')
wlroots_dep = dependency('wlroots-0.18')
wayland_server_dep = dependency('wayland-server')
xkbcommon_dep = dependency('xkbcommon')
```

### 47.2 Core Structures
```c
struct my_server {
    struct wl_display *wl_display;
    struct wlr_backend *backend;
    struct wlr_renderer *renderer;
    struct wlr_allocator *allocator;
    struct wlr_scene *scene;
    struct wlr_scene_output_layout *scene_layout;

    struct wlr_xdg_shell *xdg_shell;
    struct wlr_layer_shell_v1 *layer_shell;
    struct wlr_cursor *cursor;
    struct wlr_xcursor_manager *cursor_mgr;
    struct wlr_seat *seat;
    struct wlr_output_layout *output_layout;

    struct wl_list outputs;
    struct wl_list toplevels;

    // listeners...
};
```

### 47.3 Initialization
```c
server.wl_display = wl_display_create();
server.backend = wlr_backend_autocreate(server.wl_display, NULL);
server.renderer = wlr_renderer_autocreate(server.backend);
wlr_renderer_init_wl_display(server.renderer, server.wl_display);
server.allocator = wlr_allocator_autocreate(server.backend, server.renderer);
server.scene = wlr_scene_create();
```

### 47.4 Output Handling
- `new_output` event: a monitor was connected
- Creating `wlr_output_state`, setting mode, enabling
- `wlr_scene_output_create`: attach output to scene
- `wlr_output_layout_add_auto`: arrange outputs automatically
- Frame event: when compositor should render a frame

### 47.5 The XDG Shell: Window Management
- `wlr_xdg_shell_create`: enable xdg-shell support
- `new_surface` event: new app window
- `xdg_toplevel.map/unmap`: window becomes visible/hidden
- `xdg_toplevel.request_move/resize`: user dragging a window
- Configure-ack loop implementation
- Surface focus: `wlr_seat_keyboard_notify_enter`

### 47.6 Input: Cursor and Keyboard
```c
// Cursor
server.cursor = wlr_cursor_create();
wlr_cursor_attach_output_layout(server.cursor, server.output_layout);
server.cursor_mgr = wlr_xcursor_manager_create(NULL, 24);

// Seat
server.seat = wlr_seat_create(server.wl_display, "seat0");
```
- `cursor_motion` event: move the cursor
- `cursor_button` event: click handling, focus management
- `keyboard_key` event: forward to focused client
- XKB: `xkb_context_new`, `xkb_keymap_new_from_names`

### 47.7 Adding Tiling Layout
- Window tree: list of mapped toplevels
- Layout function: calculate each window's position and size
- `wlr_xdg_toplevel_set_size`: tell window its new size
- `wlr_scene_node_set_position`: move in scene graph
- Full dwindle algorithm implementation

### 47.8 Layer Shell for Bars and Widgets
- `wlr_layer_shell_v1_create`
- `new_layer_surface` event
- Applying exclusive zones: reducing usable area
- Z-ordering layers in scene graph
- Keyboard interactivity per layer

### 47.9 The Render Loop
- `frame` event on output: time to render
- `wlr_scene_output_commit`: render scene graph to output
- `wlr_output_present`: flip the buffer
- Frame scheduling: callback timing

### 47.10 Study Resources
- `tinywl`: https://gitlab.freedesktop.org/wlroots/wlroots/-/tree/master/tinywl
- `way-cooler` book: http://way-cooler.org/book/
- `simplewc`: https://github.com/kcirick/simplewc
- wlroots Doxygen docs
