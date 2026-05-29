# Chapter 9 — Wayfire: Plugin Architecture and 3D Effects

## Overview

Wayfire is a 3D-capable, plugin-driven Wayland compositor built on the wlroots library. Unlike
Hyprland or Sway, which ship with integrated window management and opinionated defaults, Wayfire
delegates nearly all behaviour to a plugin system. Window movement, tiling, workspaces, animations,
and even mouse cursor handling are separate plugins that you opt into. The result is a compositor
that can be stripped down to a bare rendering engine or loaded up with every Compiz-era effect ever
imagined — sometimes simultaneously.

This plugin-first design has a practical consequence: the default `wayfire.ini` you get after
installation will appear to do almost nothing until you enumerate the plugins you actually want. This
chapter walks through every layer of that system, from installation through plugin authorship, with
complete working configurations at each stage.

Wayfire targets users who want either (a) maximum visual expressiveness — rotating cube workspaces,
wobbly windows, fire-on-close — or (b) a completely programmable compositor where every policy
decision lives in a swappable plugin rather than compiled-in logic. If you are coming from a heavily
themed Compiz or KWin setup and want parity on Wayland, Wayfire is the closest match available.

Cross-reference: Chapter 8 covers Hyprland for users who prioritise ecosystem size and dotfile
availability. Chapter 11 covers Sway for a strictly tiling, i3-compatible workflow. See Chapter 53
for session startup and display manager integration across all compositors.

---

## 9.1 History and Design Goals

Wayfire's conceptual lineage traces back to Compiz, the OpenGL compositor that defined "desktop
effects" on Linux in the mid-2000s. Compiz's plugin model — where each effect, window manager
behaviour, and desk management strategy was a loadable shared object — was hugely popular but
ultimately stalled because Compiz ran on X11 and accumulated irreversible technical debt. When the
Wayland ecosystem matured enough to support serious compositor development, Wayfire's author
(Ilia Bozhinov, known as ammen99) designed a Wayland compositor that captured the extensibility
philosophy while building on clean wlroots foundations.

The key design decisions that distinguish Wayfire from peers are: (1) every non-trivial behaviour is
a plugin, meaning you can read or replace the source for almost any feature; (2) the configuration
system (`wf-config`) is strongly typed and self-documenting, so each plugin declares its options with
types and defaults that tooling like WCM can introspect; (3) rendering is OpenGL-first, which is what
makes 3D transforms like the cube workspace and wobbly windows practical without special-casing.

Wayfire does not use `libinput` directly — it delegates to wlroots's input stack, which itself wraps
libinput. This means all the wlroots touchpad gesture and pointer configuration you find in other
compositors applies here, though some gesture-specific routing is handled by dedicated plugins
(`gesture`, `pin`). The project is written in C++17 and its plugin API is a set of C++ interfaces
rather than a C ABI, which means plugins must be compiled against a matching Wayfire version.

Understanding the plugin boundary is essential before you write config. In Wayfire, even
`[core] plugins = ...` is where you register window decoration handling. If you omit `decoration` from
the plugin list, windows have no server-side chrome at all. This differs fundamentally from
compositors where decoration is implicit. The design gives you complete control but requires
explicit intent for every feature.

---

## 9.2 Installation and First Run

### Packages

Most rolling-release distributions carry Wayfire. On Arch Linux it is available in the official
`extra` repository along with `wayfire-plugins-extra` for the additional effect plugins:

```bash
# Arch Linux
sudo pacman -S wayfire wcm wayfire-plugins-extra wf-shell

# Ubuntu 24.04 / Debian Sid (package may lag upstream)
sudo apt install wayfire

# Fedora (may require enabling a COPR)
sudo dnf copr enable erikreider/SwayNotificationCenter
sudo dnf install wayfire

# Check installed version
wayfire --version
```

`wf-shell` provides a Wayfire-native panel and background daemon. `wcm` is the GTK-based
Wayfire Config Manager. Neither is strictly required but both significantly reduce initial
configuration friction.

### Building from Source

Building from source is necessary when you want plugins from `wayfire-plugins-extra` at a version
that matches a freshly built Wayfire, or when you are writing your own plugins:

```bash
# Dependencies (Arch names; adapt for your distro)
sudo pacman -S cmake ninja wlroots glm libevdev pixman wayland-protocols \
               libxkbcommon libdrm mesa cairo pango

# Clone and build Wayfire itself
git clone https://github.com/WayfireWM/wayfire.git
cd wayfire
meson setup build --prefix=/usr --buildtype=release \
    -Duse_system_wlroots=enabled \
    -Dxwayland=enabled
ninja -C build
sudo ninja -C build install

# Clone and build extra plugins against the installed Wayfire
cd ..
git clone https://github.com/WayfireWM/wayfire-plugins-extra.git
cd wayfire-plugins-extra
meson setup build --prefix=/usr --buildtype=release
ninja -C build
sudo ninja -C build install
```

### Initial Configuration

Wayfire reads `~/.config/wayfire/wayfire.ini` by default. The environment variable
`WAYFIRE_CONFIG_FILE` overrides this. A minimal config that produces a usable desktop:

```ini
# ~/.config/wayfire/wayfire.ini

[core]
plugins = \
    alpha animate autostart \
    command decoration expo \
    fast-switcher grid \
    idle move place resize \
    scale simple-tile switcher \
    vswitch window-rules \
    wm-actions wobbly wrot \
    xdg-activation zoom

xwayland = true

[output:eDP-1]
mode = 2560x1600@60000
scale = 1.5
transform = normal

[output:HDMI-A-1]
mode = 1920x1080@60000
scale = 1.0
position = 2560,0

[decoration]
border_size = 2
active_color = 0.3 0.5 0.9 1.0
inactive_color = 0.2 0.2 0.2 1.0
title_height = 28
font = Iosevka 11

[move]
activate = <super> BTN_LEFT

[resize]
activate = <super> BTN_RIGHT

[vswitch]
binding_left  = <super> KEY_LEFT
binding_right = <super> KEY_RIGHT
binding_up    = <super> KEY_UP
binding_down  = <super> KEY_DOWN
with_win_left  = <super> <shift> KEY_LEFT
with_win_right = <super> <shift> KEY_RIGHT

[command]
binding_terminal = <super> KEY_ENTER
command_terminal = foot

binding_launcher = <super> KEY_D
command_launcher = fuzzel

binding_screenshot = KEY_PRINT
command_screenshot = grim -g "$(slurp)" - | wl-copy

[wm-actions]
toggle_fullscreen = <super> KEY_F
toggle_maximized  = <super> KEY_M
minimize          = <super> KEY_H

[autostart]
background = swaybg -i ~/Pictures/wallpaper.jpg -m fill
panel      = wf-panel
nm-applet  = nm-applet --indicator

[idle]
screensaver_timeout = 300
dpms_timeout        = 600
```

Launch Wayfire from a TTY with `wayfire` or configure your display manager to start it. For a
login-manager entry see Chapter 53. When starting from TTY, export the required variables:

```bash
export XDG_SESSION_TYPE=wayland
export XDG_CURRENT_DESKTOP=Wayfire
export MOZ_ENABLE_WAYLAND=1
export QT_QPA_PLATFORM=wayland
exec wayfire > ~/.local/share/wayfire.log 2>&1
```

---

## 9.3 The Plugin System

### Loading Plugins

The entire plugin list lives in `[core] plugins`. Wayfire loads each named plugin as a shared object
from its plugin directory (typically `/usr/lib/wayfire/`). Unrecognised names produce a warning but
do not crash the compositor. Order within the list generally does not matter for correctness, but
can affect which plugin "wins" when two plugins handle the same input event.

```ini
[core]
plugins = move resize place grid vswitch wm-actions \
          animate wobbly blur cube expo scale \
          command decoration idle autostart
```

List the available installed plugins:

```bash
ls /usr/lib/wayfire/
# or, if built locally:
ls ~/.local/lib/wayfire/

# Check which plugins are currently active (requires the ipc plugin)
wfipc.py list-plugins 2>/dev/null || echo "ipc plugin not loaded"
```

### Plugin Categories

WCM organises plugins into five categories. The table below maps category to common plugins and
their primary purpose:

| Category          | Plugin(s)                              | Purpose                                      |
|-------------------|----------------------------------------|----------------------------------------------|
| General           | `core`, `decoration`, `xdg-activation`| Compositor essentials                        |
| Desktop           | `vswitch`, `oswitch`, `expo`, `cube`  | Workspace and output management              |
| Window Management | `move`, `resize`, `place`, `grid`,    | How windows move, size, tile, are placed     |
|                   | `simple-tile`, `wm-actions`           |                                              |
| Effects           | `animate`, `wobbly`, `blur`, `fire`,  | Visual transformations                       |
|                   | `fisheye`, `scale`, `wrot`, `zoom`    |                                              |
| Utilities         | `command`, `idle`, `autostart`,       | Input bindings, lifecycle, IPC               |
|                   | `ipc`, `pin`, `sticky`                |                                              |

### Configuration Schema

Every plugin declares its options through the `wf-config` typed option system. Options are keyed by
`[section]/option_name` and carry a type (`int`, `double`, `bool`, `string`, `color`,
`key`, `button`, `touch`, `gesture`). You can inspect all declared options with WCM's GUI or by
reading plugin source headers. The schema means misspelled option names silently fall back to
defaults rather than erroring, so a typo in a keybinding produces no error message — it simply
doesn't register.

```bash
# Use WCM to browse and edit all options graphically
wcm

# Alternatively, dump config to stdout for inspection
cat ~/.config/wayfire/wayfire.ini
```

---

## 9.4 Core Window Management Plugins

### move and resize

The `move` and `resize` plugins provide drag-to-move and drag-to-resize using configurable button
bindings. Both support modifier+button combinations common in tiling workflows:

```ini
[move]
activate          = <super> BTN_LEFT
activate_preserve_aspect = false

[resize]
activate = <super> BTN_RIGHT
```

`move` also exposes `move-snap-to-workarea` to prevent dragging windows off-screen.

### place

The `place` plugin controls where new windows appear. Strategies available:

```ini
[place]
mode = center          # options: cascade | random | center | under-cursor
```

`cascade` places each new window offset from the previous, mimicking traditional desktop behaviour.
`under-cursor` places windows at the pointer position, useful when launching apps from a launcher
directly below the cursor.

### grid

`grid` provides Aero/Mutter-style snap zones: drag a window to a screen edge or corner to snap it
to a half or quarter of the display. Keyboard bindings also trigger snapping:

```ini
[grid]
duration    = 300
type        = simple

slot_bl     = <super> KEY_KP1
slot_b      = <super> KEY_KP2
slot_br     = <super> KEY_KP3
slot_l      = <super> KEY_KP4
slot_c      = <super> KEY_KP5
slot_r      = <super> KEY_KP6
slot_tl     = <super> KEY_KP7
slot_t      = <super> KEY_KP8
slot_tr     = <super> KEY_KP9
restore     = <super> KEY_KP0
```

### simple-tile

`simple-tile` is a lightweight automatic tiling plugin. It is not a full tiling layout engine —
it does not implement master/stack or BSP — but it provides a usable manual tiling flow where new
windows split the focused window's area:

```ini
[simple-tile]
tile_by_default_include = terminal|editor|browser
tile_by_default_exclude = *
keep_fullscreen_on_adjacent = true

key_toggle         = <super> KEY_T
key_focus_left     = <super> KEY_H
key_focus_right    = <super> KEY_L
key_focus_above    = <super> KEY_K
key_focus_below    = <super> KEY_J
```

For more sophisticated tiling (master/stack, Fibonacci spiral), look at the community plugin
`wayfire-firedecor` or use a dedicated layout manager like `paperwm` as a client-side layer.

### wm-actions

`wm-actions` is the plugin that binds compositor-level window operations (minimize, maximize,
fullscreen, send-to-back) to keyboard shortcuts:

```ini
[wm-actions]
toggle_fullscreen  = <super> KEY_F
toggle_maximized   = <super> KEY_M
minimize           = <super> KEY_H
send_to_back       = <super> KEY_B
close              = <super> KEY_Q
```

---

## 9.5 Visual Effects Plugins

### animate

`animate` handles the open, close, and minimize animations for windows. It supports several
built-in animation types and per-effect duration control:

```ini
[animate]
open_animation  = zoom        # zoom | fade | fire | none
close_animation = fire
minimize_animation = minimize
duration        = 300
enabled_for     = all
```

The `fire` close animation sets windows ablaze as they close. The `zoom` open animation scales the
window up from a small point. All animations honour the `duration` setting in milliseconds.

To disable animations entirely for specific windows (e.g., terminals where you want instant
feedback) use `window-rules`:

```ini
[window-rules]
rule_0 = on created if app_id is foot then set animation none
```

### wobbly

`wobbly` applies a spring-mass simulation to the window surface mesh during drags, producing the
elastic "wobbly window" effect from Compiz. It has no dependencies beyond OpenGL:

```ini
[wobbly]
spring_k      = 8.0
friction      = 3.0
mass          = 50.0
grid_resolution = 6
```

Higher `spring_k` values produce stiffer, snappier motion. Lower `friction` makes windows ring
longer after you release them. `grid_resolution` controls the density of the mesh deformation — 6
is a good balance between visual quality and GPU cost.

### blur

The `blur` plugin blurs content beneath semi-transparent windows or applies a blur to the entire
background. It supports two algorithms:

```ini
[blur]
method    = kawase    # box | kawase
iterations = 2
offset    = 2
degrade   = 1
saturation = 1.0
```

`kawase` is a dual-pass Kawase blur that is substantially faster than a naive Gaussian and
produces aesthetically similar results. `iterations` controls quality; 2–4 is typical. Higher
`degrade` values render the blur at a lower internal resolution for GPU headroom.

### cube

`cube` arranges virtual workspaces on the faces of a rotating 3D cube. It is the most visually
distinctive Wayfire effect:

```ini
[cube]
activate         = <super> BTN_LEFT
rotate_left      = <super> KEY_LEFT
rotate_right     = <super> KEY_RIGHT
deform           = cylinder   # cube | cylinder | sphere
background       = 0.05 0.05 0.1 1.0
background_mode  = solid       # solid | skydome
skydome_texture  = ~/Pictures/skydome.png
skydome_mirror   = true
initial_animation = 350
cubemap_expand    = false
```

`cylinder` deform wraps workspaces around a cylinder rather than a cube, which can look more natural
on ultrawide displays. `skydome_texture` accepts an equirectangular panorama image for a 3D
background visible during rotation.

### expo

`expo` zooms out to show all workspaces as a grid — a bird's-eye overview — then lets you click a
workspace to switch to it:

```ini
[expo]
toggle           = <super> KEY_E
background       = 0.05 0.05 0.1 1.0
zoom_speed       = 300
offset           = 10
transition_length = 300
```

This is the recommended workspace switcher for most users; it is faster to trigger than the cube
and easier to navigate on keyboard-heavy workflows.

### scale

`scale` is an application switcher similar to macOS Exposé: it tiles all open windows on the
current workspace and lets you focus one by clicking or typing:

```ini
[scale]
toggle           = <super> KEY_A
toggle_all       = <super> <shift> KEY_A
include_minimized = false
spacing          = 10
duration         = 300
title_overlay    = true
allow_zoom       = false
```

`toggle_all` scales windows from all workspaces simultaneously, useful as a session-wide overview.

### Additional Effects

```ini
# fisheye — zoom the area around the cursor
[fisheye]
toggle   = <super> KEY_Z
radius   = 200.0
zoom     = 7.0

# wrot — rotate individual windows arbitrarily
[wrot]
activate = <super> <ctrl> BTN_RIGHT
reset    = <super> <ctrl> KEY_DELETE
angle_step = 15.0

# zoom — full-screen magnifier
[zoom]
modifier = <super>
speed    = 0.1
smoothing_duration = 300
```

---

## 9.6 Workspace Switcher Plugins

### vswitch

`vswitch` is the standard virtual workspace plugin. Wayfire models workspaces as a 2D grid; `vswitch`
provides directional navigation through that grid:

```ini
[vswitch]
binding_left   = <super> KEY_LEFT
binding_right  = <super> KEY_RIGHT
binding_up     = <super> KEY_UP
binding_down   = <super> KEY_DOWN
with_win_left  = <super> <shift> KEY_LEFT
with_win_right = <super> <shift> KEY_RIGHT
with_win_up    = <super> <shift> KEY_UP
with_win_down  = <super> <shift> KEY_DOWN

# Direct workspace access
binding_1 = <super> KEY_1
binding_2 = <super> KEY_2
binding_3 = <super> KEY_3
binding_4 = <super> KEY_4

gap = 0
duration = 300
background = 0.1 0.1 0.1 1.0
```

### oswitch

`oswitch` handles focus and window movement between physical outputs (monitors):

```ini
[oswitch]
next_output      = <super> KEY_O
next_output_with_win = <super> <shift> KEY_O
```

### Gesture Support

Wayfire supports libinput multi-touch gestures for workspace navigation via the `gesture` plugin
(from `wayfire-plugins-extra`):

```ini
[gesture]
# 3-finger swipe left/right to switch workspace
action_swipe_left_3  = vswitch/binding_left
action_swipe_right_3 = vswitch/binding_right
action_swipe_up_3    = expo/toggle
action_swipe_down_3  = scale/toggle
threshold            = 0.5
speed_factor         = 10.0
```

Pinch gestures can trigger zoom or scale:

```ini
action_pinch_in_2  = zoom/modifier
action_pinch_out_2 = zoom/modifier
```

---

## 9.7 Writing a Wayfire Plugin

### Plugin Interface

All Wayfire plugins implement `wf::plugin_interface_t`, a C++ abstract base class declared in
`<wayfire/plugin.hpp>`. The interface requires two methods: `init()` called when the plugin loads,
and `fini()` called on unload. Hooks into compositor events are registered inside `init()`:

```cpp
// src/my-effect.cpp
#include <wayfire/plugin.hpp>
#include <wayfire/view.hpp>
#include <wayfire/output.hpp>
#include <wayfire/signal-definitions.hpp>

class my_effect_t : public wf::plugin_interface_t
{
    wf::signal::connection_t<wf::view_mapped_signal> on_view_mapped;

public:
    void init() override
    {
        on_view_mapped = [this](wf::view_mapped_signal *ev) {
            auto view = ev->view;
            LOGI("New view mapped: ", view->get_app_id());
            // Apply a custom alpha to newly opened windows
            view->set_output(output);
        };
        output->connect(&on_view_mapped);
    }

    void fini() override
    {
        // Connections are RAII and disconnect on destruction
    }
};

DECLARE_WAYFIRE_PLUGIN(my_effect_t)
```

### Build System

Wayfire installs a `WayfirePluginConfig.cmake` package config that CMake can find. The canonical
CMakeLists for a plugin:

```cmake
cmake_minimum_required(VERSION 3.13)
project(my-effect VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
find_package(WayfirePlugin REQUIRED)

add_library(my-effect SHARED src/my-effect.cpp)
target_link_libraries(my-effect PRIVATE Wayfire::WayfirePlugin)
install(TARGETS my-effect LIBRARY DESTINATION ${WAYFIRE_PLUGIN_INSTALL_PREFIX})
```

Build and install:

```bash
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
sudo make install
# Reload config to pick up new plugin
echo "reload" | wfipc.py 2>/dev/null || pkill -HUP wayfire
```

### Accessing Compositor State

Plugins receive a pointer to their `wf::output_t` via the inherited `output` member. From the
output you can iterate views, query workspace geometry, access the input device list, and attach
render hooks:

```cpp
// List all mapped views on the current workspace
auto views = output->workspace->get_views_in_layer(wf::LAYER_WORKSPACE);
for (auto& view : views) {
    LOGI(view->get_title(), " at ", view->get_output_geometry());
}

// Register a post-render hook to overlay custom OpenGL
wf::effect_hook_t render_hook;
render_hook = [this]() { draw_overlay(); };
output->render->add_effect(&render_hook, wf::OUTPUT_EFFECT_POST);
```

### Key and Button Bindings

Use `wf::key_callback` and `wf::button_callback` with the activator system:

```cpp
wf::option_wrapper_t<wf::activatorbinding_t> activate_key
    {"my-effect/activate"};

wf::activator_callback on_activate = [=](auto) -> bool {
    do_the_thing();
    return true;   // consume the input event
};

output->add_activator(activate_key, &on_activate);
```

The `wf::option_wrapper_t<T>` template automatically re-reads the ini value when the config file
changes, so live config reload updates keybindings without a compositor restart.

---

## 9.8 window-rules: Per-App Behaviour

`window-rules` is the scripting layer for per-application overrides. Rules are evaluated in
declaration order, and multiple rules can match the same window:

```ini
[window-rules]
# Float all GTK file choosers
rule_0 = on created if (app_id contains "portal") then float

# Open Signal on workspace 3
rule_1 = on created if app_id is signal-desktop then \
         set-workspace 0 2

# Disable wobbly for Electron apps (performance)
rule_2 = on created if app_id contains "electron" then \
         set-wobbly-mode none

# Pin Picture-in-Picture windows to all workspaces
rule_3 = on created if title contains "Picture-in-Picture" then \
         set-sticky true

# Give maximised terminals full opacity; semi-transparent when floating
rule_4 = on state-change if app_id is foot then \
         if maximized then set-alpha 1.0 else set-alpha 0.85
```

Conditions available: `app_id`, `title`, `type`, `role`, `maximized`, `fullscreen`, `minimized`,
`tiled`, `floating`. Actions: `float`, `tile`, `maximize`, `fullscreen`, `minimize`,
`set-workspace`, `set-sticky`, `set-alpha`, `set-animation`, `close`.

---

## 9.9 Wayfire Compared to Hyprland

| Dimension              | Wayfire                              | Hyprland                              |
|------------------------|--------------------------------------|---------------------------------------|
| Architecture           | Plugin-first, OpenGL-native          | Monolithic with hyprctl scripting     |
| 3D effects             | Excellent (cube, wobbly, fire)       | Limited (borderless, blur, shadows)   |
| Tiling                 | simple-tile + grid (basic)           | Built-in dwindle/master (richer)      |
| Config format          | INI (wayfire.ini)                    | Custom DSL (hyprland.conf)            |
| Dotfile ecosystem      | Smaller                              | Very large (r/unixporn dominant)      |
| Quickshell / EWW       | Works but less documented            | First-class (Quickshell targets it)   |
| Plugin language        | C++17 (compile-time)                 | C++ plugins + hyprpm runtime          |
| Touchpad gestures      | Via gesture plugin                   | Built-in gesture config               |
| Screencasting (wlr-sc) | Supported                            | Supported                             |
| Stability (2026)       | Stable, slower development           | Active, more frequent releases        |
| GPU requirement        | OpenGL 3.0+                          | OpenGL / Vulkan path                  |

**Choose Wayfire when** you want authentic Compiz-era 3D effects, maximum per-plugin configurability,
or are building a specialised kiosk or embedded desktop where a locked-down plugin set is a feature.

**Choose Hyprland when** you want a large dotfile community, rich first-party tiling, the Quickshell
widget system, or frequent upstream improvements. See Chapter 8 for the full Hyprland chapter.

---

## 9.10 wf-shell: Panel and Wallpaper

`wf-shell` provides two components: `wf-panel` (a Wayfire-native taskbar) and `wf-background` (a
wallpaper daemon that integrates with the output configuration Wayfire exposes). Configuration lives
in `~/.config/wf-shell.ini`:

```ini
[panel]
position     = bottom
size         = 30
font         = Iosevka 10
autohide     = false

[panel-clock]
format       = %a %b %d  %H:%M

[panel-launchers]
launchers    = terminal:foot browser:firefox files:thunar

[panel-workspaces-4]
# Shows 4 workspace indicators
display = all

[background]
color        = 0.05 0.05 0.1 1.0
image        = ~/Pictures/wallpaper.jpg
mode         = fit       # fit | fill | stretch | center | tile
```

For a more feature-rich bar, Wayfire works with Waybar since it exposes a standard Wayland shell
protocol surface. See Chapter 21 for Waybar configuration.

---

## 9.11 IPC and Scripting

Wayfire ships an optional `ipc` plugin that exposes a Unix socket for external control. The
`wfipc.py` helper (from the Wayfire repository's `ipc-scripts/` directory) wraps the socket
protocol:

```bash
# Load the ipc plugin first
# [core]
# plugins = ... ipc ...

# List outputs
wfipc.py list-outputs

# Get focused view
wfipc.py get-focused-view

# Move focused view to workspace 1,0
wfipc.py set-workspace 1 0

# Send a custom event to trigger a plugin action
wfipc.py send-custom '{"method": "vswitch/binding_right", "data": {}}'
```

You can also drive Wayfire from shell scripts via direct socket communication:

```bash
WAYFIRE_SOCKET="${XDG_RUNTIME_DIR}/wayfire-wayland-0.socket"

send_ipc() {
    echo "$1" | nc -U "$WAYFIRE_SOCKET"
}

# Toggle expo
send_ipc '{"method":"expo/toggle","data":{}}'
```

This enables integration with status bars, rofi scripts, and polyglot desktop automation.

---

## Troubleshooting

### Compositor Does Not Start

Check the log at `~/.local/share/wayfire.log` (or wherever you redirected stderr). Common causes:

```bash
# Missing wlroots or OpenGL support
wayfire 2>&1 | grep -i "error\|failed\|missing"

# Test OpenGL availability
glxinfo | grep "OpenGL version"
# On pure Wayland:
EGL_PLATFORM=surfaceless eglinfo 2>/dev/null | head -20

# Wrong DRM device permissions
ls -l /dev/dri/
# Your user must be in the 'video' group
groups $USER | grep video
sudo usermod -aG video $USER
```

### Plugin Not Loading

```bash
# Check the plugin file exists
ls /usr/lib/wayfire/ | grep my-plugin

# Check for symbol errors
ldd /usr/lib/wayfire/my-plugin.so

# Increase log verbosity
WAYFIRE_DEBUG_LEVEL=2 wayfire 2>&1 | grep -i plugin
```

### Wobbly / Cube Causes GPU Glitches

These effects require a properly functioning OpenGL implementation. Mesa software rasterizers
(llvmpipe) will produce glitches or extreme slowness:

```bash
# Verify hardware acceleration
glxinfo | grep "renderer string"
# Should show your GPU, not llvmpipe

# Check mesa driver in use
LIBGL_DEBUG=verbose wayfire 2>&1 | grep -i mesa
```

If you are on a hybrid GPU (NVIDIA + Intel), ensure Wayfire uses the correct GPU:

```bash
# Force Intel (default on most systems)
DRI_PRIME=0 wayfire

# Force NVIDIA (with proprietary driver + GBM patch)
DRI_PRIME=1 __VK_LAYER_NV_optimus=NVIDIA_only wayfire
```

### XWayland Windows Not Appearing

```ini
# Ensure XWayland is enabled in config
[core]
xwayland = true
```

```bash
# Verify Xwayland binary is installed
which Xwayland

# Check that it started
ps aux | grep Xwayland
```

### Keybindings Not Working

1. Verify the plugin containing the binding is listed in `[core] plugins`.
2. Check for typos — option names are case-sensitive and silently ignored if wrong.
3. Use `wev` to confirm that key events reach Wayfire:

```bash
# Install wev, then run in a terminal inside Wayfire:
wev
# Press the key combination and check the output
```

4. Check for conflicts: two plugins bound to the same key will silently compete; the plugin listed
   later in the `plugins` list typically wins.

### Scale / Expo Shows Black Screen

Usually a framebuffer allocation issue. Try disabling hardware cursor and see if that helps:

```bash
WLR_NO_HARDWARE_CURSORS=1 wayfire
```

Or check for compositor-level errors:

```bash
WAYLAND_DEBUG=1 wayfire 2>&1 | grep -i "buffer\|attach\|commit" | head -40
```

---

*See also: Chapter 8 (Hyprland), Chapter 11 (Sway), Chapter 21 (Waybar), Chapter 53 (Session Startup and Display Managers)*

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
