# Appendix A — Protocol Quick Reference

## Overview

This appendix is the field guide you keep open while ricing. It covers every protocol that matters to a Wayland compositor user: the stable core, the standardized extensions, the wlroots ecosystem extras, and the Hyprland-specific additions. For each protocol group you will find a table, a prose explanation of what the protocol actually does and why it exists, and concrete shell commands or C code snippets that demonstrate real usage. Cross-references point you back to the chapters where each protocol is discussed in full context. The appendix is organized in four layers — core Wayland, wayland-protocols extensions, wlr-protocols (wlroots ecosystem), and Hyprland-specific protocols — followed by sections on versioning, source locations, and error troubleshooting. Understanding which protocol does what prevents the most common class of debugging mistakes: blaming the compositor when the real problem is a missing global, or patching your bar tool when the issue is actually a buffer negotiation failure. Read this appendix once carefully; return to it whenever you see a `wl_display_dispatch` error or a "protocol error, object not found" message in your log.

## Installation

The protocols themselves are specifications — nothing to install to *read* this appendix. To *use* or *browse* the protocol XML files on your system:

**Projects:** https://wayland.freedesktop.org · https://gitlab.freedesktop.org/wayland/wayland-protocols · https://gitlab.freedesktop.org/wlroots/wlr-protocols

```bash
# Arch Linux — protocol XML files land in /usr/share/wayland-protocols/
sudo pacman -S wayland-protocols

# Browse installed protocols
ls /usr/share/wayland-protocols/stable/
ls /usr/share/wayland-protocols/unstable/
ls /usr/share/wayland-protocols/staging/

# wayland-scanner: generate C bindings from XML
sudo pacman -S wayland          # includes wayland-scanner

# Nix
nix-env -iA nixpkgs.wayland-protocols nixpkgs.wayland
```

---

## Contents

- [Core Wayland Protocols (wayland.xml)](#core-wayland-protocols-waylandxml)
- [Standard Extensions (wayland-protocols)](#standard-extensions-wayland-protocols)
- [wlr-protocols (wlroots ecosystem)](#wlr-protocols-wlroots-ecosystem)
- [Hyprland Custom Protocols](#hyprland-custom-protocols)
- [Protocol Versioning and Compatibility](#protocol-versioning-and-compatibility)
- [Protocol Explorer and Source Locations](#protocol-explorer-and-source-locations)
- [Troubleshooting Protocol Errors](#troubleshooting-protocol-errors)

---


## Core Wayland Protocols (wayland.xml)

The core protocol, defined in `wayland.xml` inside the `wayland` package itself, is the lowest level of the stack. Every Wayland client that ever draws a pixel must use these objects. They are not extensions — they are the protocol. Clients do not opt into them; they are the vocabulary of the connection.

The `wl_display` object is the root of everything. It is created implicitly when you call `wl_display_connect()`. It provides two things that everything else depends on: the `sync` request (which lets you wait until all pending server-side events have been processed) and error reporting. Every fatal protocol error from the compositor arrives as a `wl_display.error` event followed by connection termination. When a client crashes with "fatal error: wl_display.error — invalid object 17", it is the compositor telling you that you sent a request on a destroyed or never-created object.

The `wl_registry` is the capability advertisement system. On connect, the compositor emits a `global` event for every interface it supports, together with the interface name string (e.g. `"zwlr_layer_shell_v1"`) and the maximum supported version. Clients bind to globals they need by sending `wl_registry.bind`. If a global your tool needs is absent, the compositor simply does not support that protocol — no error, just silence, which is why checking for globals is the first debugging step for any misbehaving Wayland tool.

The surface pipeline — `wl_compositor` → `wl_surface` → `wl_buffer` — is how pixels actually reach the screen. A surface is an abstract rendering target. A buffer holds the actual pixel data. You attach a buffer to a surface, then commit the surface. The compositor schedules the new content for display on the next frame. This double-buffered, commit-based model is fundamental; it is what gives Wayland its tear-free guarantees.

| Protocol | Purpose |
|----------|---------|
| `wl_display` | Root object, sync, error reporting |
| `wl_registry` | Global capability advertisement |
| `wl_compositor` | Create surfaces |
| `wl_surface` | Rendering unit (attach buffer, commit) |
| `wl_buffer` | Pixel data (shm or dmabuf) |
| `wl_shm` | Shared memory buffer creation |
| `wl_seat` | Input device group |
| `wl_keyboard` | Keyboard input |
| `wl_pointer` | Pointer input |
| `wl_touch` | Touch input |
| `wl_output` | Monitor/display representation |
| `wl_subcompositor` | Sub-surfaces |
| `wl_data_device_manager` | Clipboard / drag-and-drop |

**Introspecting globals at runtime.** The single most useful diagnostic command for any Wayland problem is `weston-info` or, on systems without weston, the `wayland-info` tool from the `wayland-utils` package:

```bash
# List every global the compositor advertises, with version numbers
wayland-info

# Filter for a specific protocol family
wayland-info | grep -i layer

# On Hyprland, the built-in dispatch also reports supported protocols
hyprctl clients -j | jq '.[].pid'
hyprctl monitors -j | jq '.[].name'
```

**Writing a minimal wl_registry listener in C.** This is the skeleton every Wayland client starts with. Ricing tool authors who write their own bars or notification daemons will write this code:

```c
#include <wayland-client.h>
#include <stdio.h>
#include <string.h>

static struct wl_compositor *compositor = NULL;
static struct wl_shm        *shm        = NULL;

static void registry_handle_global(void *data,
    struct wl_registry *registry, uint32_t name,
    const char *interface, uint32_t version)
{
    if (strcmp(interface, wl_compositor_interface.name) == 0) {
        compositor = wl_registry_bind(registry, name,
                         &wl_compositor_interface, 4);
    } else if (strcmp(interface, wl_shm_interface.name) == 0) {
        shm = wl_registry_bind(registry, name,
                  &wl_shm_interface, 1);
    }
    printf("global: %s v%u (name=%u)\n", interface, version, name);
}

static void registry_handle_global_remove(void *data,
    struct wl_registry *registry, uint32_t name) {}

static const struct wl_registry_listener registry_listener = {
    .global        = registry_handle_global,
    .global_remove = registry_handle_global_remove,
};

int main(void) {
    struct wl_display  *display  = wl_display_connect(NULL);
    struct wl_registry *registry = wl_display_get_registry(display);
    wl_registry_add_listener(registry, &registry_listener, NULL);
    wl_display_roundtrip(display);   /* wait for all globals */
    wl_display_disconnect(display);
    return 0;
}
```

See Chapter 3 for the full surface creation and buffer attachment pipeline, and Chapter 12 for shared-memory buffer management with `wl_shm`.

---

## Standard Extensions (wayland-protocols)

The `wayland-protocols` repository, maintained at `gitlab.freedesktop.org/wayland/wayland-protocols`, holds protocols that have cross-compositor consensus. They are split into three stability tiers: **stable** (frozen API, no breaking changes), **staging** (mostly stable, minor adjustments possible), and **unstable** (marked `z` prefix, may break). When you see `xdg_` it is stable; when you see `zwp_` or `zxdg_` it is unstable/staging.

The `xdg-shell` protocol is the standard way applications create top-level windows and popups. It defines `xdg_surface` (a role applied to a `wl_surface`) and `xdg_toplevel` (the actual window). The configure/ack_configure handshake in xdg-shell is what allows the compositor to tell an application "resize to 800×600" and wait for confirmation before committing the new size — eliminating the race conditions that plagued X11 window resizing. Nearly every GTK4, Qt6, and SDL2 application uses xdg-shell under the hood. See Chapter 7 for xdg-shell deep-dive with xdg-decoration negotiation.

Fractional scaling (`wp_fractional_scale_manager_v1`) is the solution to the HiDPI problem on displays that do not have an integer scale factor — 1.5× on a 2560×1600 laptop panel being the canonical example. Without it, compositors had to either render at 1× (blurry) or 2× (oversized). With it, clients receive the exact fractional scale factor and can render at the correct logical resolution using the `wp_viewporter` protocol for cropping the result to the wire pixel dimensions. This combination eliminates the blurriness that plagued Wayland HiDPI for years. See Chapter 22 for the full HiDPI ricing workflow.

The `ext-session-lock` protocol replaced the older `zwlr_input_inhibitor_v1` approach to lockscreens. It is the protocol used by `swaylock`, `hyprlock`, and `waylock`. It gives the locker exclusive surface rendering rights and input, preventing any other client from receiving events while locked. The critical security property is that the compositor must not unlock until the locker explicitly signals success — a crashed locker leaves the session locked, not unlocked.

| Protocol | Namespace | Stability | Purpose |
|----------|-----------|-----------|---------|
| xdg-shell | `xdg_wm_base` | Stable | Window management (applications) |
| xdg-popup | `xdg_popup` | Stable | Menus and popups |
| xdg-output | `zxdg_output_manager_v1` | Unstable | Logical output metadata |
| xdg-decoration | `zxdg_decoration_manager_v1` | Unstable | CSD vs SSD negotiation |
| xdg-activation | `xdg_activation_v1` | Staging | Focus stealing prevention |
| presentation-time | `wp_presentation` | Stable | Precise frame timing |
| viewporter | `wp_viewporter` | Stable | Surface scaling/cropping |
| fractional-scale | `wp_fractional_scale_manager_v1` | Staging | Fractional HiDPI |
| cursor-shape | `wp_cursor_shape_manager_v1` | Staging | Cursor themes |
| linux-dmabuf | `zwp_linux_dmabuf_v1` | Unstable | GPU buffer sharing |
| pointer-constraints | `zwp_pointer_constraints_v1` | Unstable | Pointer lock/confine |
| relative-pointer | `zwp_relative_pointer_manager_v1` | Unstable | Raw mouse motion |
| virtual-keyboard | `zwp_virtual_keyboard_manager_v1` | Unstable | Software keyboard |
| input-method | `zwp_input_method_manager_v2` | Unstable | IME |
| ext-session-lock | `ext_session_lock_manager_v1` | Staging | Session lockscreen |
| color-management | `wp_color_manager_v1` | Staging | HDR and color spaces |

**Checking xdg-shell configure/ack flow with wlhax.** `wlhax` is a Wayland protocol fuzzer and spy that lets you observe real protocol traffic:

```bash
# Install wlhax (build from source on most distros)
git clone https://github.com/emersion/wlhax
cd wlhax && meson build && ninja -C build

# Spy on all messages between a client and the compositor
./build/wlhax -- firefox
# Output includes every configure/ack_configure exchange
```

**Generating protocol bindings from XML.** When writing a tool that uses staging or unstable protocols, you must generate the C glue from the XML yourself:

```bash
# Install wayland-protocols (provides the XML files)
# Location varies: /usr/share/wayland-protocols/ or similar
PKG_DATADIR=$(pkg-config --variable=pkgdatadir wayland-protocols)

# Generate client-side header and glue C file for xdg-shell
wayland-scanner client-header \
    "$PKG_DATADIR/stable/xdg-shell/xdg-shell.xml" \
    xdg-shell-client-protocol.h

wayland-scanner private-code \
    "$PKG_DATADIR/stable/xdg-shell/xdg-shell.xml" \
    xdg-shell-protocol.c

# For fractional-scale (staging):
wayland-scanner client-header \
    "$PKG_DATADIR/staging/fractional-scale/fractional-scale-v1.xml" \
    fractional-scale-client-protocol.h
```

**Forcing SSD vs CSD via xdg-decoration.** Some compositors default to server-side decorations; others to client-side. You can observe and influence this at the application level:

```bash
# Force GTK4 apps to use CSD (ignore SSD from compositor)
export GTK_CSD=1

# Force Qt apps to use client-side decorations
export QT_WAYLAND_DISABLE_WINDOWDECORATION=1

# On Sway, configure SSD globally in sway config:
# default_border pixel 2
# titlebar_border_thickness 0

# On Hyprland, use window rules:
# windowrulev2 = nodecoration, class:^(foot)$
```

See Chapter 7 for decoration negotiation in depth, and Chapter 29 for Hyprland window rules.

---

## wlr-protocols (wlroots ecosystem)

The wlroots project, which powers Sway, Hyprland, Cage, and many other compositors, ships its own protocol extensions under the `zwlr_` namespace. These protocols were developed because the freedesktop standardization process is slow and compositors needed practical capabilities immediately. Many `zwlr_` protocols have since been superseded by or are on the path to standardization (e.g. `ext-session-lock` replaced `zwlr_input_inhibitor_v1`), but as of 2026 most ricing tools still use the wlr variants because compositor support is broader.

The `zwlr_layer_shell_v1` protocol is the **foundation of all desktop ricing on Wayland**. It allows clients to create surfaces that are positioned relative to outputs (monitors), not relative to the application window stack. A layer-shell surface can be pinned to the top, bottom, left, or right edge of an output, can request exclusive zones (telling the compositor to not place other windows in that area — how a status bar reserves its strip), and can be assigned to one of four z-order layers: `background`, `bottom`, `top`, and `overlay`. Wallpaper renderers (swaybg, swww), status bars (waybar, eww, ags), and on-screen keyboards all use layer-shell. See Chapter 15 for the complete layer-shell ricing chapter.

The `zwlr_screencopy_manager_v1` protocol enables screen capture without root access or X11 hacks. Tools like `grim`, `slurp`, `wf-recorder`, and `obs-studio` (via the Pipewire portal) use it to read framebuffer contents. It works by the compositor copying the rendered output into a client-provided `wl_shm` buffer on request. Framerate for recording is capped by the output's refresh rate and the time it takes to copy, which is why DMA-BUF capture (`zwlr_export_dmabuf_manager_v1`) exists for zero-copy GPU-to-GPU recording. See Chapter 41 for screen capture pipelines.

The `zwlr_output_manager_v1` protocol is the configuration interface used by `wlr-randr` and `kanshi`. It is entirely separate from `wl_output`, which is read-only. Through the output manager you can move, rotate, scale, enable, and disable outputs, and you can atomically apply a configuration across multiple monitors to prevent intermediate states where resolutions do not match. This is what `kanshi` uses to apply your monitor profiles when you dock or undock. See Chapter 19 for multi-monitor management.

| Protocol | Purpose | Key Tools |
|----------|---------|-----------|
| `zwlr_layer_shell_v1` | Bars, widgets, wallpapers | waybar, eww, swww, ags |
| `zwlr_screencopy_manager_v1` | Screenshots, recording | grim, wf-recorder |
| `zwlr_output_manager_v1` | Monitor configuration | wlr-randr, kanshi |
| `zwlr_foreign_toplevel_management_v1` | Window list/taskbar | waybar taskbar, nwg-taskbar |
| `zwlr_data_control_manager_v1` | Clipboard access from non-focused apps | wl-clipboard, cliphist |
| `zwlr_input_inhibitor_v1` | Lockscreen input inhibition (older) | swaylock (legacy) |
| `zwlr_gamma_control_manager_v1` | Night light/gamma | wlsunset, gammastep |
| `zwlr_virtual_pointer_manager_v1` | Synthetic pointer events | ydotool, dotool |
| `zwlr_export_dmabuf_manager_v1` | DMA-BUF screen capture | obs-studio, wf-recorder |

**Taking a screenshot with grim (zwlr_screencopy under the hood):**

```bash
# Full-screen screenshot
grim ~/screenshots/$(date +%Y%m%d-%H%M%S).png

# Interactive region selection with slurp
grim -g "$(slurp)" ~/screenshots/region.png

# Capture a specific output by name
grim -o DP-1 ~/screenshots/dp1.png

# Pipe directly to clipboard
grim -g "$(slurp)" - | wl-copy

# Capture with swappy for immediate annotation
grim -g "$(slurp)" - | swappy -f -
```

**Configuring monitors with wlr-randr:**

```bash
# List all outputs and their current modes
wlr-randr

# Set a specific mode and scale
wlr-randr --output DP-1 --mode 2560x1440@144Hz --scale 1.0

# Enable fractional scaling on a 2560x1600 panel
wlr-randr --output eDP-1 --mode 2560x1600@120Hz --scale 1.5

# Move output to a position (for multi-monitor layout)
wlr-randr --output HDMI-A-1 --pos 2560,0

# Rotate output
wlr-randr --output DP-2 --transform 90
```

**Clipboard management with zwlr_data_control (cliphist + wl-paste):**

```bash
# Install cliphist (stores clipboard history via zwlr_data_control)
# Start the daemon (add to your compositor autostart)
wl-paste --type text --watch cliphist store &
wl-paste --type image --watch cliphist store &

# Query clipboard history
cliphist list

# Select and restore a history entry with rofi/wofi
cliphist list | wofi --dmenu | cliphist decode | wl-copy

# Clear history
cliphist wipe

# In Hyprland config (exec-once section):
# exec-once = wl-paste --type text --watch cliphist store
# exec-once = wl-paste --type image --watch cliphist store
```

**Night light with wlsunset (zwlr_gamma_control):**

```bash
# Start wlsunset for Tel Aviv coordinates
# Temperature: 6500K daytime, 3500K night
wlsunset -l 32.1 -L 34.8 -t 3500 -T 6500

# Run as a systemd user service
cat > ~/.config/systemd/user/wlsunset.service << 'EOF'
[Unit]
Description=Day/night gamma adjustments
After=graphical-session.target

[Service]
ExecStart=/usr/bin/wlsunset -l 32.1 -L 34.8 -t 3500 -T 6500
Restart=on-failure

[Install]
WantedBy=graphical-session.target
EOF
systemctl --user enable --now wlsunset
```

See Chapter 15 for layer-shell deep dive, Chapter 19 for kanshi and multi-monitor automation, and Chapter 41 for the full screen-capture and recording pipeline.

---

## Hyprland Custom Protocols

Hyprland ships several protocols that are not in wayland-protocols or wlr-protocols. They are defined in the Hyprland source tree under `protocols/` and are compiled into the compositor itself. Their XML definitions are installed to `/usr/share/hyprland/protocols/` (or the equivalent prefix) and can be inspected directly. These protocols expose capabilities that Hyprland implements and that other compositors may not, so tools that depend on them will not function on Sway or other non-Hyprland compositors without fallback paths.

The `hyprland_global_shortcuts_v1` protocol is the mechanism used by tools like `hyprkeys` and directly by Hyprdim/Hyprpaper to register compositor-level keyboard shortcuts that fire even when no application has focus. This is distinct from `xdg-activation`; it is closer to X11's `XGrabKey`. Applications use it by requesting a shortcut with a trigger description, then receiving an `activated` event when the user presses the key. See Chapter 29 for global shortcut configuration and keybinding management.

The `hyprland_toplevel_export_v1` protocol allows capturing window thumbnails — individual application window framebuffers, not whole outputs. This is used by `hyprshot` when invoked in window-capture mode, and by taskbar/overview plugins that need per-window previews. It fills a gap that `zwlr_screencopy_manager_v1` does not cover, since screencopy operates on entire outputs. The security implication is that any client that can bind this global can capture the contents of any window, including terminals and browser windows.

The `hyprland_ctm_control_v1` protocol exposes per-output color transform matrices. A CTM is a 3×3 matrix applied to RGB values before they reach the display hardware, enabling software color correction, color-blindness filters, and artistic color grading independently of the ICC/color-management stack. This is the protocol used by tools like `hyprcal` and custom color-temperature scripts that want finer control than `zwlr_gamma_control`. See Chapter 44 for color calibration and HDR workflows.

| Protocol | Purpose | Tools |
|----------|---------|-------|
| `hyprland_global_shortcuts_v1` | Register global hotkeys | hyprkeys, custom daemons |
| `hyprland_toplevel_export_v1` | Per-window thumbnail capture | hyprshot, overview plugins |
| `hyprland_ctm_control_v1` | Color transform matrices | hyprcal, color scripts |
| `hyprland_focus_grab_v1` | Input focus grab for overlays | rofi, wofi, custom launchers |

**Capturing a window with hyprshot:**

```bash
# Interactive window capture (uses hyprland_toplevel_export internally)
hyprshot -m window

# Capture a specific window by class
hyprshot -m window --class "firefox"

# Save to a specific path
hyprshot -m window -o ~/screenshots/ -f "firefox-$(date +%s).png"

# Copy directly to clipboard
hyprshot -m window --clipboard-only
```

**Applying a CTM for warm color tones:**

```bash
# hyprctl supports CTM via the keyword interface
# Matrix values are row-major R,G,B → R',G',B'
# This example reduces blue channel by 20%
hyprctl keyword monitor "DP-1,addreserved,0,0,0,0"

# Direct CTM via hyprland_ctm_control (using hyprcal if installed):
hyprcal --monitor DP-1 --temperature 4000

# Manual CTM via hyprctl (3x3 matrix flattened, identity = 1 0 0 0 1 0 0 0 1):
hyprctl keyword ctm "1.0 0.0 0.0 0.0 1.0 0.0 0.0 0.0 0.8"
```

**Listing all Hyprland-specific globals with hyprctl:**

```bash
# Show complete compositor state including protocol versions
hyprctl version

# Show active window protocols in use
hyprctl activewindow -j | jq '{class: .class, pid: .pid, mapped: .mapped}'

# Dump all compositor globals (requires wayland-info)
WAYLAND_DISPLAY=$(hyprctl -j monitors | jq -r '.[0].name // "wayland-1"')
wayland-info | grep -i hyprland
```

See Chapter 29 for the full Hyprland configuration reference, Chapter 44 for CTM and color management, and Chapter 53 for session startup and autostart configuration.

---

## Protocol Versioning and Compatibility

Wayland protocols use integer versioning. When a compositor advertises `zwlr_layer_shell_v1` at version 4, it means it supports all requests and events defined up to version 4 of that protocol. Clients should bind at the minimum version they need, not necessarily the maximum the compositor advertises. Binding at a version higher than what the compositor supports is a protocol error.

The version you bind at determines which features are available. For `zwlr_layer_shell_v1`, version 1 gives you basic layer surfaces; version 2 adds the `keyboard_interactivity` enum value `on_demand`; version 4 adds the `layer` request to change layers after creation. If your bar tool needs `on_demand` keyboard interactivity (so it can focus an input field without stealing global keyboard focus), you must bind at version 2 or higher.

| Protocol | Min Useful Version | Version Adding Key Feature |
|----------|--------------------|---------------------------|
| `zwlr_layer_shell_v1` | 1 | v2: `keyboard_interactivity on_demand` |
| `zwlr_screencopy_manager_v1` | 1 | v3: damage region, cursor option |
| `xdg_wm_base` | 1 | v5: `wm_capabilities` advisory |
| `zwp_linux_dmabuf_v1` | 3 | v4: `zwp_linux_dmabuf_feedback_v1` |
| `ext_session_lock_manager_v1` | 1 | v1 only (simple protocol) |
| `wp_fractional_scale_manager_v1` | 1 | v1 only |

**Checking what version a compositor supports:**

```bash
# wayland-info shows version for each global
wayland-info | grep layer_shell
# Example output: zwlr_layer_shell_v1 version 4

# In C, bind at the minimum of what you need and what's available:
uint32_t version = MIN(offered_version, MAX_SUPPORTED_VERSION);
layer_shell = wl_registry_bind(registry, name,
    &zwlr_layer_shell_v1_interface, version);
```

---

## Protocol Explorer and Source Locations

Knowing where to find protocol XML files is essential when you need to understand exactly what requests and events are available, their argument types, and any documentation comments embedded in the XML.

The canonical online browser at `https://wayland.app/protocols/` renders every protocol in a searchable, hyperlinked format with inline documentation. It is the fastest way to look up an event or request signature without leaving the browser.

For offline work, protocol XML files are installed by their respective packages:

```bash
# Core Wayland protocol
find /usr/share/wayland -name "*.xml" 2>/dev/null
# Typically: /usr/share/wayland/wayland.xml

# Standard extensions (wayland-protocols package)
find /usr/share/wayland-protocols -name "*.xml" | sort

# wlr-protocols (may be in a separate package or submodule)
find /usr/share/wlr-protocols -name "*.xml" 2>/dev/null
# Alternatively, clone the repo:
git clone https://gitlab.freedesktop.org/wlroots/wlr-protocols

# Hyprland protocols
find /usr/share/hyprland -name "*.xml" 2>/dev/null
# Or from the Hyprland source:
# https://github.com/hyprwm/Hyprland/tree/main/protocols
```

**Quick reference for online resources:**

| Resource | URL |
|----------|-----|
| Protocol browser | https://wayland.app/protocols/ |
| wayland-protocols repo | https://gitlab.freedesktop.org/wayland/wayland-protocols |
| wlr-protocols repo | https://gitlab.freedesktop.org/wlroots/wlr-protocols |
| Hyprland protocols | https://github.com/hyprwm/Hyprland/tree/main/protocols |
| xdg-portal (AppArmor/Flatpak) | https://github.com/flatpak/xdg-desktop-portal |

---

## Troubleshooting Protocol Errors

Protocol errors are the most confusing class of Wayland bugs because they terminate the connection without an explanatory error message beyond an opaque object ID and error code. This section catalogues the errors you will most frequently encounter when ricing.

**"wl_display error: invalid object N"** means your client sent a request on an object that the compositor does not recognise. Common causes: binding a protocol at a version higher than what the compositor advertises; using a destroyed object; using an object created by a different `wl_registry.bind` call than expected. Fix: always check the version returned by `wl_registry.global` and bind at `MIN(offered, needed)`.

**"Protocol error — zwlr_layer_shell_v1: invalid layer"** means you tried to create a layer surface with a `layer` enum value not supported at the version you bound. Binding at version 1 and using `LAYER_TOP` is fine; if you want to change the layer after creation you need version 4.

**"XDG surface not configured"** happens when a client commits a surface that received a `configure` event but never sent `ack_configure`. Every `xdg_surface.configure` must be acknowledged before the next commit. This is the most common mistake when porting X11 toolkits to Wayland.

```bash
# Enable Wayland debug logging to see protocol traffic
WAYLAND_DEBUG=1 waybar 2>&1 | head -100

# Log only client-to-server messages (requests)
WAYLAND_DEBUG=client waybar 2>&1 | grep "-> "

# Log only server-to-client messages (events)
WAYLAND_DEBUG=server waybar 2>&1 | grep "<- "

# For Hyprland compositor-side debug output
HYPRLAND_LOG_WLR=1 Hyprland 2>&1 | grep -i "protocol\|error\|fatal"

# Check if a global is missing (e.g. layer_shell absent = compositor doesn't support it)
wayland-info 2>&1 | grep -c "zwlr_layer_shell"
# If output is 0, your compositor does not support layer-shell
```

**Compositor does not expose a required global.** If `wayland-info` shows no entry for a protocol your tool needs, the options are: (1) your compositor genuinely does not support it (e.g. GNOME does not support `zwlr_layer_shell_v1`); (2) the compositor package was compiled without that protocol support; (3) you are connecting to the wrong `WAYLAND_DISPLAY` socket.

```bash
# Check which socket you are connected to
echo $WAYLAND_DISPLAY
ls /run/user/$UID/

# If running nested (e.g. Hyprland inside a Sway session for testing),
# the inner compositor uses a different socket:
WAYLAND_DISPLAY=wayland-2 wayland-info | grep layer_shell

# Verify Hyprland compiled with wlr-protocols support
hyprctl version | grep -i "compile"
```

**Permission denied on zwlr_export_dmabuf.** Some compositors gate DMA-BUF export behind a security check (user must be in a specific group or the client must have a valid app-id). On Sway and Hyprland this is not gated, but on compositors using xdg-desktop-portal for screen capture you need to go through the portal:

```bash
# Check if xdg-desktop-portal-hyprland is running
systemctl --user status xdg-desktop-portal-hyprland

# Restart portal if screen share is broken
systemctl --user restart xdg-desktop-portal
systemctl --user restart xdg-desktop-portal-hyprland

# Verify pipewire is running (needed for portal screen share)
systemctl --user status pipewire pipewire-pulse
```

See Chapter 3 for surface lifecycle and protocol error recovery, Chapter 53 for session startup and portal configuration, and Chapter 15 for layer-shell troubleshooting specific to bar and widget placement.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
