# Chapter 3 — Protocol Extensions: xdg-shell, layer-shell, wlr-protocols

## Contents

- [Overview](#overview)
- [3.1 The wayland-protocols Repository](#31-the-wayland-protocols-repository)
  - [wayland-scanner: The XML-to-C Pipeline](#wayland-scanner-the-xml-to-c-pipeline)
  - [How Compositors Advertise Extensions: The Registry](#how-compositors-advertise-extensions-the-registry)
- [3.2 xdg-shell — The Standard Window Protocol](#32-xdg-shell-the-standard-window-protocol)
  - [xdg_wm_base: The Toplevel Shell Manager](#xdgwmbase-the-toplevel-shell-manager)
  - [xdg_surface and xdg_toplevel: The Configure Handshake](#xdgsurface-and-xdgtoplevel-the-configure-handshake)
  - [xdg_popup: Menus, Tooltips, and Context Menus](#xdgpopup-menus-tooltips-and-context-menus)
  - [CSD vs. SSD: xdg-decoration-unstable-v1](#csd-vs-ssd-xdg-decoration-unstable-v1)
- [3.3 xdg-output — Multi-Monitor Metadata](#33-xdg-output-multi-monitor-metadata)
  - [Fractional Scaling and wp-fractional-scale-v1](#fractional-scaling-and-wp-fractional-scale-v1)
- [3.4 wlr-layer-shell — The Ricing Protocol](#34-wlr-layer-shell-the-ricing-protocol)
  - [The Four Layers](#the-four-layers)
  - [Anchoring and Exclusive Zones](#anchoring-and-exclusive-zones)
  - [Keyboard Interactivity Modes](#keyboard-interactivity-modes)
  - [How swww Uses BACKGROUND Layer](#how-swww-uses-background-layer)
  - [How Waybar Uses the TOP Layer](#how-waybar-uses-the-top-layer)
- [3.5 wlr-protocols Suite](#35-wlr-protocols-suite)
  - [wlr-output-management-unstable-v1](#wlr-output-management-unstable-v1)
  - [wlr-screencopy-unstable-v1](#wlr-screencopy-unstable-v1)
  - [wlr-data-control-unstable-v1](#wlr-data-control-unstable-v1)
  - [wlr-foreign-toplevel-management-unstable-v1](#wlr-foreign-toplevel-management-unstable-v1)
  - [wlr-gamma-control-unstable-v1](#wlr-gamma-control-unstable-v1)
  - [wlr-input-inhibitor-unstable-v1](#wlr-input-inhibitor-unstable-v1)
- [3.6 Other Important Extensions](#36-other-important-extensions)
  - [wp-viewporter](#wp-viewporter)
  - [wp-presentation-time](#wp-presentation-time)
  - [wp-cursor-shape-v1](#wp-cursor-shape-v1)
  - [zwp-linux-dmabuf-v1](#zwp-linux-dmabuf-v1)
  - [ext-session-lock-v1](#ext-session-lock-v1)
  - [xdg-activation-v1](#xdg-activation-v1)
- [3.7 Hyprland-Specific Protocols](#37-hyprland-specific-protocols)
  - [hyprland-global-shortcuts-v1](#hyprland-global-shortcuts-v1)
  - [hyprland-toplevel-export-v1](#hyprland-toplevel-export-v1)
  - [hyprland-ctm-control-v1](#hyprland-ctm-control-v1)
  - [hyprland-focus-grab-v1](#hyprland-focus-grab-v1)
- [Troubleshooting](#troubleshooting)
  - ["Protocol not supported" / Client refuses to launch](#protocol-not-supported-client-refuses-to-launch)
  - [Layer surface not appearing / wrong size](#layer-surface-not-appearing-wrong-size)
  - [Screencopy / screenshot produces blank output](#screencopy-screenshot-produces-blank-output)
  - [Clipboard tools fail silently](#clipboard-tools-fail-silently)
  - [Fractional scaling blurry / artifacts](#fractional-scaling-blurry-artifacts)
  - [Protocol version mismatch](#protocol-version-mismatch)
- [Resources](#resources)

---


## Overview

The core Wayland protocol is intentionally bare. It defines a display server
abstraction, a surface model, and an input event system — but nothing more.
There are no windows, no desktop shells, no screenshotting facilities, no
clipboard management. All of that lives in the **extension ecosystem**: a
collection of XML-described protocol files that compositors advertise, clients
request, and code generators compile into usable C/C++ bindings.

Understanding protocol extensions is the prerequisite for understanding every
ricing tool in this book. Waybar, eww, swww, grim, wl-clipboard, hyprctl — all
of them work by requesting specific protocol extensions from the compositor at
startup. If an extension is absent, the tool either falls back gracefully or
refuses to launch entirely. Knowing which extensions exist, which compositors
implement them, and how they work at a mechanical level turns mysterious failures
into solvable problems.

This chapter walks through the essential extensions in depth: xdg-shell (normal
windows), wlr-layer-shell (the ricing workhorse), the full wlr-protocols suite,
and the growing `wp-*` and `ext-*` namespaces from the freedesktop standards
track. It closes with Hyprland-specific extensions that enable features no other
compositor currently exposes. Code examples throughout are drawn from real
tooling you will use every day.

*Cross-references: Chapter 2 covers the Wayland display model and surface
lifecycle. Chapter 8 covers Waybar and layer-shell in production. Chapter 14
covers screencopy and recording pipelines. Chapter 53 covers session startup and
protocol negotiation at login.*

---

## 3.1 The wayland-protocols Repository

The canonical home for cross-compositor protocol extensions is
`wayland-protocols`, hosted at
`https://gitlab.freedesktop.org/wayland/wayland-protocols`. Protocols move
through three tiers before reaching widespread adoption:

| Tier | Directory | Meaning |
|------|-----------|---------|
| **stable** | `stable/` | Frozen. ABI-stable. All conformant compositors must implement if they claim support. |
| **staging** | `staging/` | Feature-complete but may have minor tweaks before stabilization. Widely implemented. |
| **unstable** | `unstable/` | Under active design. Expect breaking changes between versions. |

The naming convention encodes the tier: stable protocols have no suffix
(`xdg-shell`), staging protocols carry a `-v1` suffix in their interface names,
and unstable protocols are prefixed with `z` (for "unstable") and carry both a
name and a version suffix — e.g. `zwlr_layer_shell_v1`. When you see a `z`
prefix in source code, you are looking at a protocol that was considered
unstable at the time the interface names were frozen. Many "unstable" protocols
like `zwlr_layer_shell_v1` have been effectively stable in practice for years;
the naming is a historical artifact.

### wayland-scanner: The XML-to-C Pipeline

Every Wayland protocol is described in an XML file. The `wayland-scanner` tool
compiles these XML files into C headers and glue code. Desktop distributions
ship pre-generated headers in their development packages, so you rarely need to
run `wayland-scanner` manually, but understanding what it produces clarifies the
structure of any Wayland client or compositor code you read.

```bash
# Install wayland-scanner (Arch Linux)
sudo pacman -S wayland

# Generate a client-side header from a protocol XML
wayland-scanner client-header \
  /usr/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml \
  /tmp/xdg-shell-client-protocol.h

# Generate server-side code (for compositor developers)
wayland-scanner server-header \
  /usr/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml \
  /tmp/xdg-shell-server-protocol.h

# Generate the implementation code (private code, not the header)
wayland-scanner private-code \
  /usr/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml \
  /tmp/xdg-shell-protocol.c

# List all installed stable protocols
ls /usr/share/wayland-protocols/stable/
ls /usr/share/wayland-protocols/staging/
ls /usr/share/wayland-protocols/unstable/
```

### How Compositors Advertise Extensions: The Registry

When a client connects to the Wayland compositor it receives a `wl_display`
object. The first thing any client does is bind the global `wl_registry` and
listen for `global` events. Each event announces one interface name, one
version, and one numeric name (the "global name" — a slot identifier):

```c
// Minimal C example: discovering available protocols
#include <stdio.h>
#include <wayland-client.h>

static void registry_global(void *data, struct wl_registry *registry,
                             uint32_t name, const char *interface,
                             uint32_t version) {
    printf("global: %s (version %u, name %u)\n", interface, version, name);
}

static void registry_global_remove(void *data, struct wl_registry *registry,
                                   uint32_t name) {
    printf("global removed: name %u\n", name);
}

static const struct wl_registry_listener registry_listener = {
    .global        = registry_global,
    .global_remove = registry_global_remove,
};

int main(void) {
    struct wl_display  *display  = wl_display_connect(NULL);
    struct wl_registry *registry = wl_display_get_registry(display);
    wl_registry_add_listener(registry, &registry_listener, NULL);
    wl_display_roundtrip(display);   // flush + wait for all globals
    wl_display_disconnect(display);
    return 0;
}
```

Compile and run this on any Wayland session to see exactly which protocols your
compositor exposes. The output is your ground truth; no documentation is more
accurate.

```bash
# Alternatively, use the wlrctl or wayland-info utilities
wayland-info        # ships with wayland-utils on Arch
# or
wlr-randr --list    # implicitly prints globals for its protocols
```

A quick shell-script equivalent that avoids writing C:

```bash
# Use weston-info or wayland-info to dump globals
wayland-info 2>/dev/null | grep 'interface:' | awk '{print $2}' | sort
```

---

## 3.2 xdg-shell — The Standard Window Protocol

`xdg-shell` is the protocol that turns a raw `wl_surface` into a window that
users can move, resize, maximize, and close. Before xdg-shell the desktop shell
space was fragmented between `wl_shell` (now deprecated) and compositor-specific
hacks. Since its stabilization in 2019, virtually every toolkit (GTK4, Qt6,
SDL2, EFL, libadwaita) uses xdg-shell exclusively. As a ricer you will rarely
write against it directly, but understanding its handshake model is essential for
diagnosing application misbehavior.

### xdg_wm_base: The Toplevel Shell Manager

The client binds `xdg_wm_base` from the registry. The compositor sends periodic
`ping` requests; the client must respond with `pong`. Failure to pong causes the
compositor to mark the client as "not responding." This is the mechanism behind
the spinning cursor / frozen window treatment in compositors like Hyprland.

```c
// Binding xdg_wm_base in a real client
#include <xdg-shell-client-protocol.h>

struct xdg_wm_base *xdg_wm_base = NULL;

static void wm_base_ping(void *data, struct xdg_wm_base *wm_base,
                         uint32_t serial) {
    xdg_wm_base_pong(wm_base, serial);
}

static const struct xdg_wm_base_listener wm_base_listener = {
    .ping = wm_base_ping,
};

// In registry_global handler:
if (strcmp(interface, xdg_wm_base_interface.name) == 0) {
    xdg_wm_base = wl_registry_bind(registry, name,
                                   &xdg_wm_base_interface,
                                   MIN(version, 4));
    xdg_wm_base_add_listener(xdg_wm_base, &wm_base_listener, NULL);
}
```

### xdg_surface and xdg_toplevel: The Configure Handshake

The critical design of xdg-shell is its **configure/ack_configure handshake**.
The compositor sends `configure` events (with a serial number) to tell the
client what geometry and state to use. The client must call `ack_configure` with
that serial before attaching a buffer. This prevents races between compositor
state changes and client rendering.

```c
// Configure handshake skeleton
static void toplevel_configure(void *data, struct xdg_toplevel *toplevel,
                               int32_t width, int32_t height,
                               struct wl_array *states) {
    // width/height of 0 means "use your own preferred size"
    if (width > 0 && height > 0) {
        app.width  = width;
        app.height = height;
    }
    // Inspect states array for MAXIMIZED, FULLSCREEN, RESIZING, ACTIVATED
}

static void toplevel_close(void *data, struct xdg_toplevel *toplevel) {
    app.running = false;
}

static const struct xdg_toplevel_listener toplevel_listener = {
    .configure = toplevel_configure,
    .close     = toplevel_close,
};

static void surface_configure(void *data, struct xdg_surface *surface,
                              uint32_t serial) {
    xdg_surface_ack_configure(surface, serial);
    // Now safe to attach a new buffer
    render_and_commit();
}

static const struct xdg_surface_listener surface_listener = {
    .configure = surface_configure,
};
```

### xdg_popup: Menus, Tooltips, and Context Menus

`xdg_popup` is the protocol object for transient overlay windows — right-click
context menus, dropdown menus, autocomplete popups. It requires a `positioner`
object that describes where the popup should appear relative to its parent
surface, plus fallback rules for when it would go off-screen.

Popups grab keyboard and pointer input from their parent. The compositor manages
dismissal: clicking outside sends a `popup_done` event, at which point the
client destroys the popup.

### CSD vs. SSD: xdg-decoration-unstable-v1

The `xdg_decoration_manager_v1` extension (in the staging tier as
`xdg-decoration-unstable-v1`) allows negotiation of who draws the window
titlebar and border:

| Mode | Who draws decorations | Example |
|------|-----------------------|---------|
| `CLIENT_SIDE` (CSD) | The application toolkit | GTK4, libadwaita apps |
| `SERVER_SIDE` (SSD) | The compositor | KWin, Sway (optionally) |

In Hyprland the default is CSD. You can request SSD globally or per-window:

```ini
# ~/.config/hypr/hyprland.conf
# Force server-side decorations for all windows
windowrulev2 = nodecoration, class:(.*)   # disable CSD chrome
# Or use xwayland-satellite for XWayland windows
```

Niri, Sway, and River each have their own decoration flags. The `gtk-4.0`
settings key `gtk-decoration-layout` controls which buttons GTK4 renders in CSD
mode — relevant when you want a minimal titlebar without close/minimize buttons.

---

## 3.3 xdg-output — Multi-Monitor Metadata

The base Wayland `wl_output` interface exposes physical display properties
(make, model, physical size, subpixel layout) but uses **physical pixel
coordinates** for everything. In a multi-monitor, mixed-DPI setup these
coordinates become unusable: a 4K monitor at 2x scaling occupies 3840x2160
physical pixels but should present a 1920x1080 logical workspace. Surface
placement in physical coordinates would require every client to know every
monitor's scale factor.

`xdg_output` (from `xdg-output-unstable-v1`, now in the staging tier) adds
**logical coordinates** to each output: the position and size in the
compositor's unified logical coordinate space. Clients use logical coordinates
for window positioning; compositors internally map these to physical pixels.

```c
// Listening for xdg_output data
#include <xdg-output-unstable-v1-client-protocol.h>

static void xdg_output_logical_position(void *data,
                                        struct zxdg_output_v1 *xdg_output,
                                        int32_t x, int32_t y) {
    struct monitor *m = data;
    m->logical_x = x;
    m->logical_y = y;
}

static void xdg_output_logical_size(void *data,
                                    struct zxdg_output_v1 *xdg_output,
                                    int32_t width, int32_t height) {
    struct monitor *m = data;
    m->logical_width  = width;
    m->logical_height = height;
}
```

The `name` event (added in version 2) gives the output its connector name
(`DP-1`, `HDMI-A-1`, `eDP-1`). Tools like Waybar and wl-mirror use this name to
target specific monitors.

### Fractional Scaling and wp-fractional-scale-v1

The `wp-fractional-scale-v1` protocol (stable since 2023) allows compositors to
request fractional scale factors like 1.5x or 1.25x without forcing integer
overscaling. The client receives a `preferred_scale` event carrying the scale
factor as a fixed-point integer (scale * 120). GTK4 and Qt6 both handle this
natively; SDL2 requires opt-in via the `SDL_HINT_VIDEO_WAYLAND_PREFER_LIBDECOR`
hint.

```bash
# Check if your compositor sends fractional-scale globals
wayland-info | grep fractional

# In Hyprland — set fractional scale per monitor
monitor = DP-1, 2560x1440@144, 0x0, 1.5
monitor = eDP-1, 1920x1200@60, 2560x0, 1.25
```

---

## 3.4 wlr-layer-shell — The Ricing Protocol

`zwlr_layer_shell_v1` is, without exaggeration, the most important extension for
desktop customization on Wayland. It allows clients to place surfaces in one of
four fixed **layers** that the compositor renders in a defined Z-order, with
precise control over anchoring, margins, and whether the surface excludes other
content from its area. Every status bar, wallpaper daemon, notification widget,
and on-screen overlay in the Wayland ecosystem depends on this protocol.

`wlr-layer-shell` was designed by the wlroots team and lives in the
`wlr-protocols` repository rather than `wayland-protocols`. It is implemented
by Sway, Hyprland, River, Wayfire, Niri, Cosmic, and most other compositors
that target the wlroots ecosystem. KWin (KDE) implements it as of Plasma 6.
Mutter (GNOME) does not implement it by default; GNOME Shell's own bar and
overlay system uses internal protocols.

### The Four Layers

| Layer | Enum value | Typical use |
|-------|-----------|-------------|
| `BACKGROUND` | 0 | Wallpaper renderers (swww, swaybg, mpvpaper) |
| `BOTTOM` | 1 | Desktop icons, subtle underlay widgets |
| `TOP` | 2 | Status bars (Waybar, ironbar), notification daemons |
| `OVERLAY` | 3 | Lockscreens, screenshot overlays, OSD popups |

Windows managed by xdg-toplevel sit between BOTTOM and TOP. An application
window can never appear above a TOP-layer surface unless the user specifically
requests fullscreen mode, at which point the compositor may choose to cover TOP
surfaces.

### Anchoring and Exclusive Zones

A layer surface can anchor to any combination of edges (left, right, top,
bottom). When anchored to two opposite edges the surface **stretches** to fill
that dimension. The **exclusive zone** tells the compositor how many pixels to
reserve adjacent to the anchored edge — normal windows will not be placed in
that strip.

```c
// Creating a bottom status bar using wlr-layer-shell
#include <wlr-layer-shell-unstable-v1-client-protocol.h>

struct zwlr_layer_shell_v1  *layer_shell = NULL;
struct zwlr_layer_surface_v1 *layer_surface = NULL;

// After binding layer_shell from registry...
layer_surface = zwlr_layer_shell_v1_get_layer_surface(
    layer_shell,
    wl_surface,            // the wl_surface to promote
    NULL,                  // NULL = use the focused output
    ZWLR_LAYER_SHELL_V1_LAYER_TOP,
    "statusbar"            // namespace string (arbitrary, for compositor use)
);

// Anchor to bottom edge, stretch horizontally
zwlr_layer_surface_v1_set_anchor(layer_surface,
    ZWLR_LAYER_SURFACE_V1_ANCHOR_BOTTOM |
    ZWLR_LAYER_SURFACE_V1_ANCHOR_LEFT   |
    ZWLR_LAYER_SURFACE_V1_ANCHOR_RIGHT);

// 32 pixels tall
zwlr_layer_surface_v1_set_size(layer_surface, 0, 32);

// Reserve 32 pixels at the bottom — windows won't overlap
zwlr_layer_surface_v1_set_exclusive_zone(layer_surface, 32);

// Keyboard interactivity: none (bar doesn't need keyboard focus)
zwlr_layer_surface_v1_set_keyboard_interactivity(
    layer_surface,
    ZWLR_LAYER_SURFACE_V1_KEYBOARD_INTERACTIVITY_NONE);

wl_surface_commit(wl_surface);
```

### Keyboard Interactivity Modes

| Mode | Behavior |
|------|---------|
| `NONE` | Surface never receives keyboard events. Use for passive bars. |
| `EXCLUSIVE` | Surface takes exclusive keyboard focus. Use for lockscreens, launchers while open. |
| `ON_DEMAND` | Surface receives focus only when clicked (added in v4). Use for interactive bars. |

Waybar uses `NONE` by default (pure display), but activates `ON_DEMAND` when a
module spawns a popup (e.g. clicking the clock to open a calendar). Fuzzel
(launcher) uses `EXCLUSIVE` on the OVERLAY layer to capture all keystrokes while
the launcher window is open.

### How swww Uses BACKGROUND Layer

`swww` implements wallpaper transitions by placing a layer surface on the
BACKGROUND layer for each monitor. The surface is sized to the full output,
anchored to all four edges, and given an exclusive zone of -1 (which means "do
not reserve any space — overlap with the window area freely").

```bash
# Verify swww is using the BACKGROUND layer
wayland-info | grep -A5 "zwlr_layer_shell"

# swww workflow
swww-daemon &
swww img ~/wallpapers/current.jpg
swww img ~/wallpapers/next.jpg --transition-type wave --transition-duration 2
```

### How Waybar Uses the TOP Layer

```ini
# ~/.config/waybar/config  (abbreviated)
{
    "layer": "top",           // maps to ZWLR_LAYER_SHELL_V1_LAYER_TOP
    "position": "top",
    "height": 30,
    "exclusive": true,        // sets exclusive zone = height
    "output": "DP-1",         // target a specific monitor
    ...
}
```

*For a full Waybar configuration walkthrough, see Chapter 8.*

---

## 3.5 wlr-protocols Suite

The wlr-protocols repository (`https://gitlab.freedesktop.org/wlroots/wlr-protocols`)
hosts compositor-control protocols that do not fit the general-purpose freedesktop
track. These protocols tend to expose compositor internals — output configuration,
screen capture, input blocking — that require privileged access in many designs.

### wlr-output-management-unstable-v1

This protocol allows clients to **read and modify display configuration**: which
outputs are enabled, their resolutions, refresh rates, positions, scale factors,
and transforms. It is the backbone of `kanshi` (dynamic display profiles) and
`wdisplays` (GUI display configurator).

```bash
# kanshi: automatic output reconfiguration on monitor hotplug
# ~/.config/kanshi/config

profile dock {
    output eDP-1 disable
    output "Dell U2722D" mode 2560x1440@60Hz position 0,0 scale 1.0
    output "LG 27UK850" mode 3840x2160@60Hz position 2560,0 scale 2.0
    exec notify-send "Dock profile activated"
}

profile laptop {
    output eDP-1 enable mode 1920x1200@60Hz position 0,0 scale 1.25
    exec notify-send "Laptop profile activated"
}
```

```bash
# Start kanshi as a systemd user service
systemctl --user enable --now kanshi.service

# Or manually
kanshi &

# wdisplays: graphical output manager
wdisplays
```

### wlr-screencopy-unstable-v1

`wlr-screencopy` lets privileged clients copy the compositor's framebuffer —
enabling screenshots, screen recording, and live screen-sharing. It is used by
`grim`, `wf-recorder`, OBS (via the wlrobs plugin), and Quickshell's
`ScreencopyView` component.

```bash
# grim: screenshot a specific monitor
grim -o DP-1 ~/screenshots/$(date +%Y%m%d_%H%M%S).png

# grim + slurp: interactive region selection
grim -g "$(slurp)" ~/screenshots/$(date +%Y%m%d_%H%M%S).png

# wf-recorder: screen recording with audio
wf-recorder -a -f ~/recordings/$(date +%Y%m%d_%H%M%S).mp4

# wf-recorder: record a specific geometry
wf-recorder -g "$(slurp)" -f ~/recordings/region_$(date +%Y%m%d_%H%M%S).mp4

# Stop recording
pkill -INT wf-recorder
```

The protocol works by creating a `zwlr_screencopy_frame_v1` for a given output
or region, waiting for the `ready` event, then reading the pixel data from the
shared memory buffer the compositor has filled. Hyprland additionally implements
`hyprland-toplevel-export-v1` which allows capturing a single window rather than
a full output — used by window thumbnail previews.

*See Chapter 14 for a complete screen recording pipeline with encoding options.*

### wlr-data-control-unstable-v1

The standard Wayland clipboard (`wl_data_device`) requires an active seat focus
— you can only read or write clipboard contents when your window is focused. The
`wlr-data-control` protocol breaks this restriction, allowing background
clipboard managers to operate without a window.

```bash
# wl-clipboard: command-line clipboard access
echo "hello world" | wl-copy
wl-paste                    # paste current clipboard
wl-paste --primary          # paste from primary selection (middle-click buffer)
wl-copy --primary < file.txt

# cliphist: clipboard history manager
# Add to Hyprland startup:
wl-paste --watch cliphist store &

# Recall from history via wofi:
cliphist list | wofi --dmenu | cliphist decode | wl-copy

# Or via rofi:
cliphist list | rofi -dmenu | cliphist decode | wl-copy
```

*See Chapter 31 for a complete clipboard manager setup.*

### wlr-foreign-toplevel-management-unstable-v1

This protocol exposes the compositor's window list to external clients —
enabling taskbars, window switchers, and window-aware widgets that don't need
to embed inside a specific application. Each `zwlr_foreign_toplevel_handle_v1`
represents one toplevel window and carries its title, application ID, and
current state (maximized, minimized, fullscreen, activated).

Waybar's `wlr/taskbar` module, ironbar's taskbar, and nwg-taskbar all use this
protocol. It also enables the window-picker widget in Quickshell.

```bash
# Check if your compositor exposes this global
wayland-info | grep foreign_toplevel

# nwg-taskbar: standalone taskbar using foreign-toplevel
nwg-taskbar -d 5   # dock position 5 (bottom center)
```

### wlr-gamma-control-unstable-v1

Allows setting per-output gamma ramps — the underpinning for night-light and
display color temperature tools. `wlsunset` and `gammastep` (Wayland backend)
use this protocol.

```bash
# wlsunset: automatic sunrise/sunset color temperature
# ~/.config/hypr/hyprland.conf exec-once
exec-once = wlsunset -l 37.7 -L -122.4   # San Francisco coordinates

# Manual temperature with wl-gammarelay-rs
# First, start the D-Bus service
wl-gammarelay-rs &
# Then control via D-Bus
busctl --user set-property rs.wl-gammarelay / rs.wl.GammaRelay Temperature q 3500
busctl --user set-property rs.wl-gammarelay / rs.wl.GammaRelay Brightness d 0.9
```

### wlr-input-inhibitor-unstable-v1

A client holding the input inhibitor lock receives **all** keyboard and pointer
input, bypassing normal window focus rules. This is the original lockscreen
mechanism for wlroots compositors. Note: `ext-session-lock-v1` (see Section 3.6)
has superseded it for lockscreens, but the input inhibitor remains useful for
kiosk-mode applications.

```bash
# swaylock uses ext-session-lock-v1 on modern compositors
# but falls back to wlr-input-inhibitor on older ones
swaylock --color 1e1e2e

# Verify which protocol is in use
WAYLAND_DEBUG=1 swaylock 2>&1 | grep -E "inhibitor|session_lock"
```

---

## 3.6 Other Important Extensions

### wp-viewporter

The `wp-viewporter` (stable) protocol adds two operations to any `wl_surface`:
**crop** (select a subrectangle of the buffer as the source) and **scale**
(render it at a different destination size). This enables efficient video
rendering (crop letterbox borders before scaling), HiDPI buffer management, and
custom scaling for layer surfaces.

```bash
# mpv uses wp-viewporter for hardware video scaling on Wayland
mpv --gpu-api=vulkan --hwdec=vaapi video.mkv
```

### wp-presentation-time

Applications doing latency-sensitive rendering (games, media players, drawing
apps) need to know exactly when each frame was displayed. `wp-presentation-time`
delivers a `presented` feedback event per committed buffer containing the exact
presentation timestamp (CLOCK_MONOTONIC), the refresh interval, and flags
indicating whether the frame used VSync. This is what allows Godot, SDL2, and
Vulkan-based apps to implement frame pacing on Wayland.

### wp-cursor-shape-v1

Instead of requiring every client to create a cursor surface and upload pixel
data, `wp-cursor-shape-v1` (staging, widely implemented since 2023) lets a
client request a named cursor shape directly from the compositor. The compositor
renders the correct shape from the system cursor theme, automatically handling
theme changes and HiDPI scaling.

```bash
# Force cursor theme for all Wayland clients (Hyprland)
# ~/.config/hypr/hyprland.conf
env = XCURSOR_THEME,Bibata-Modern-Ice
env = XCURSOR_SIZE,24

# GTK4 apps on Wayland use wp-cursor-shape-v1 automatically
# Check that the cursor protocol is available
wayland-info | grep cursor_shape
```

### zwp-linux-dmabuf-v1

This is the zero-copy GPU buffer sharing protocol. Instead of a client copying
pixel data to shared memory, it shares a DMA-BUF file descriptor directly with
the compositor. The compositor imports the buffer into its own GPU context with
no CPU involvement. Every Vulkan, OpenGL, and VA-API application on Wayland
benefits from this when it is available.

```bash
# Diagnose DMA-BUF issues with WAYLAND_DEBUG
WAYLAND_DEBUG=1 glxinfo 2>&1 | grep -i dmabuf

# In Hyprland, explicit sync (requires linux-dmabuf v4+) can be enabled:
render {
    explicit_sync = 2   # 0=off, 1=on, 2=auto (Hyprland 0.40+)
}
```

### ext-session-lock-v1

The `ext-session-lock-v1` protocol (in the `ext` namespace, meaning it targets
cross-compositor standardization) is the modern lockscreen protocol. A client
claiming the session lock takes over all outputs with full-coverage surfaces on
the OVERLAY layer and receives exclusive input. The compositor blocks all other
rendering until the locker either unlocks or crashes (in which case the
compositor may fall back to a built-in lockscreen).

```bash
# swaylock >= 1.7 uses ext-session-lock-v1
swaylock

# hyprlock is a Hyprland-native locker using the same protocol
exec = hyprlock

# Check if the protocol is available
wayland-info | grep ext_session_lock

# Verify the lockscreen is using the correct protocol
WAYLAND_DEBUG=1 swaylock 2>&1 | grep session_lock
```

*See Chapter 53 for integrating the lockscreen into the session startup sequence.*

### xdg-activation-v1

Focus stealing — one application taking keyboard focus from another without user
intent — is a frequent annoyance. `xdg-activation-v1` solves this with a
token-based system: the application requesting focus must present a token issued
by the compositor at the time of the triggering user event. Without a valid
token, the compositor may refuse the focus request or only flash the taskbar.

```bash
# xdg-activation is handled transparently by GTK4, Qt6, and SDL2
# For shell scripts launching applications:
xdg-open file.pdf            # respects activation tokens when possible

# Hyprland: allow focus stealing for specific apps
windowrulev2 = focusonactivate, class:^(Spotify)$
```

---

## 3.7 Hyprland-Specific Protocols

Hyprland exposes several protocols that have no equivalent in the wlroots or
freedesktop ecosystems. These are documented in the Hyprland wiki and their XML
sources live in the Hyprland source tree under `protocols/`.

### hyprland-global-shortcuts-v1

Allows clients to register global keyboard shortcuts through the compositor
rather than through the compositor's configuration file. This is used by
`hyprshade` (shader overlays), `hyprpicker` (color picker), and third-party
media control daemons.

```bash
# Enable in hyprland.conf
bind = SUPER, F10, global, hyprshade:toggle

# A client can request a shortcut at runtime via the protocol
# hyprshade uses this to toggle shaders without modifying hyprland.conf
hyprshade toggle blue-light-filter
```

### hyprland-toplevel-export-v1

Extends screencopy to individual windows. While `wlr-screencopy` can only
capture an entire output, `hyprland-toplevel-export-v1` captures a specific
toplevel surface. This enables per-window thumbnail previews (used in Hyprland's
own overview mode) and selective window recording.

```bash
# hyprshot uses both wlr-screencopy and hyprland-toplevel-export-v1
# Screenshot a window interactively
hyprshot -m window

# Screenshot a specific window by address
hyprctl clients | grep -A5 "class: kitty"
# then use hyprshot with --addr
```

### hyprland-ctm-control-v1

The Color Transform Matrix control protocol allows clients to apply a 3x3 color
matrix to an entire output — enabling per-output color grading, accessibility
color blindness filters, and night-light effects without using the gamma ramp
protocol. `hyprshade` uses this for its shader overlay system.

```bash
# hyprshade: apply a built-in shader
hyprshade on vibrance
hyprshade on blue-light-filter
hyprshade off

# List available shaders
hyprshade ls

# Schedule automatic shader activation (sunset/sunrise)
# ~/.config/hyprshade/config.toml
[[shades]]
name = "blue-light-filter"
start_time = 19:00:00
end_time = 07:00:00
```

### hyprland-focus-grab-v1

Added in Hyprland 0.41, this protocol allows popup-like surfaces to grab pointer
and keyboard input while remaining in the normal window stack. It is used by
Quickshell's interactive popup widgets and custom launcher overlays that need
input focus without using the OVERLAY layer.

---

## Troubleshooting

Protocol issues manifest in several common failure modes. This section gives
you the diagnostic tools and remediation steps for each.

### "Protocol not supported" / Client refuses to launch

The tool checked for an extension in the registry and did not find it. Verify:

```bash
# Step 1: confirm the protocol is in the registry
wayland-info | grep <protocol_name>
# e.g.:
wayland-info | grep zwlr_layer_shell
wayland-info | grep ext_session_lock

# Step 2: check if WAYLAND_DISPLAY is set correctly
echo $WAYLAND_DISPLAY           # should be wayland-1 or similar
ls /run/user/$(id -u)/          # should contain the socket file

# Step 3: verify you are running the correct compositor
echo $XDG_CURRENT_DESKTOP       # should match your compositor
ps aux | grep -E 'hyprland|sway|river|wayfire'
```

### Layer surface not appearing / wrong size

```bash
# Run the client with WAYLAND_DEBUG to trace all protocol messages
WAYLAND_DEBUG=1 waybar 2>&1 | grep -E "layer_surface|configure|error"

# For swww
WAYLAND_DEBUG=1 swww-daemon 2>&1 | grep -E "layer_shell|error"

# Hyprland: check if a window rule is interfering
hyprctl clients | grep -i namespace   # layer surfaces appear as clients
hyprctl layers                        # show active layer surfaces
```

### Screencopy / screenshot produces blank output

```bash
# Ensure no screencopy inhibitor is active (some lockscreens leave one)
wayland-info | grep screencopy_inhibitor

# Try grim with explicit output name
wayland-info | grep wl_output    # find output name
grim -o "$(hyprctl monitors -j | jq -r '.[0].name')" /tmp/test.png

# Hyprland: check if security context rejects the client
journalctl --user -u hyprland --since "5 minutes ago" | grep -i screencopy
```

### Clipboard tools fail silently

```bash
# Check that wlr-data-control is available
wayland-info | grep data_control

# Test wl-paste basic function
wl-paste --list-types   # lists MIME types in current clipboard

# If cliphist is not receiving events, restart the watch process
pkill -f "wl-paste --watch"
wl-paste --watch cliphist store &

# Debug wl-clipboard protocol traffic
WAYLAND_DEBUG=1 wl-paste 2>&1 | grep -E "data_control|error"
```

### Fractional scaling blurry / artifacts

```bash
# Confirm the compositor is sending wp-fractional-scale events
wayland-info | grep fractional_scale

# GTK4 environment variables that affect scaling
export GDK_BACKEND=wayland
export GDK_SCALE=1              # let fractional-scale handle it; don't force integer

# Qt applications
export QT_AUTO_SCREEN_SCALE_FACTOR=1
export QT_SCALE_FACTOR=1

# Electron applications
# Add to electron app's flags file, e.g. ~/.config/electron-flags.conf:
--ozone-platform=wayland
--enable-features=WaylandWindowDecorations
```

### Protocol version mismatch

Tools sometimes require a minimum version of a protocol interface. The
compositor may advertise version 1 but the tool needs version 3:

```bash
# WAYLAND_DEBUG will show the version negotiation
WAYLAND_DEBUG=1 some-tool 2>&1 | grep "zwlr_layer_shell"
# Look for: bind interface 'zwlr_layer_shell_v1', version X, name Y

# Update your compositor — protocol version support is added incrementally
# On Arch Linux:
sudo pacman -Syu hyprland   # or sway, wayfire, etc.

# Check compositor version
hyprctl version
sway --version
```

---

## Resources

| Resource | URL |
|----------|-----|
| Interactive protocol explorer | https://wayland.app/protocols/ |
| wayland-protocols repository | https://gitlab.freedesktop.org/wayland/wayland-protocols |
| wlr-protocols repository | https://gitlab.freedesktop.org/wlroots/wlr-protocols |
| Hyprland protocol sources | https://github.com/hyprwm/Hyprland/tree/main/protocols |
| wayland-info (wayland-utils) | `sudo pacman -S wayland-utils` |
| Protocol XML browser (offline) | `/usr/share/wayland-protocols/` |
| wlroots protocol tracker | https://gitlab.freedesktop.org/wlroots/wlroots/-/tree/master/protocol |

*Next: Chapter 4 — libwayland Programming: Writing Wayland Clients in C*

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
