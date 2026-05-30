# Chapter 45 — Debugging Wayland: WAYLAND_DEBUG, weston-info, wldbg

## Contents

- [Overview](#overview)
- [45.1 WAYLAND_DEBUG — Protocol Tracing](#451-waylanddebug-protocol-tracing)
- [45.2 weston-info — Output and Capability Inspection](#452-weston-info-output-and-capability-inspection)
- [45.3 wldbg — Interactive Protocol Debugger](#453-wldbg-interactive-protocol-debugger)
- [45.4 Compositor Logs and State Inspection](#454-compositor-logs-and-state-inspection)
  - [Hyprland](#hyprland)
  - [Sway](#sway)
  - [GNOME / Mutter](#gnome-mutter)
  - [KDE Plasma / KWin](#kde-plasma-kwin)
- [45.5 Environment Variable Debugging](#455-environment-variable-debugging)
- [45.6 XWayland Debugging](#456-xwayland-debugging)
- [45.7 xdg-desktop-portal Debugging](#457-xdg-desktop-portal-debugging)
- [45.8 Common Issues and Fixes](#458-common-issues-and-fixes)
- [45.9 GPU and Rendering Debugging](#459-gpu-and-rendering-debugging)
- [45.10 Quickshell-Specific Debugging](#4510-quickshell-specific-debugging)
- [45.11 Systematic Debugging Workflow](#4511-systematic-debugging-workflow)
- [Troubleshooting](#troubleshooting)

---


## Overview

Debugging on Wayland requires a fundamentally different mindset than X11. On X11, tools like `xev`, `xwininfo`, and `xprop` gave you omniscient access to window state — any process could inspect any window. Wayland's security model deliberately breaks this: clients are isolated from each other, the compositor mediates all communication, and there is no ambient "display" you can query arbitrarily.

The trade-off is that Wayland debugging requires more targeted tooling. You need to know which layer is misbehaving — the protocol itself, the compositor, the toolkit (GTK/Qt), the portal, or XWayland — before choosing the right instrument. This chapter covers the complete debugging toolkit from protocol-level tracing down to GPU and rendering diagnostics.

A key principle: when a Wayland application misbehaves, always start by confirming it is actually running under Wayland (not silently falling back to XWayland), then verify the session environment variables are correct, and only then reach for protocol-level tracing. Most user-facing bugs are environment misconfiguration, not protocol errors.

Cross-reference: for session startup and environment variable injection, see Ch 12 (Session Management). For toolkit-specific Wayland flags, see Ch 22 (GTK/Qt Wayland Backends). For portal configuration, see Ch 52 (xdg-desktop-portal Setup).

---

## Installation

**Project:** `WAYLAND_DEBUG` is a built-in environment variable provided by libwayland — no installation required. The additional inspection tools below need separate packages.

```bash
# Arch Linux
sudo pacman -S weston          # provides weston-info (compositor-agnostic protocol inspector)
sudo pacman -S wayland-utils   # provides wayland-info (alternative to weston-info)
paru -S wldbg                  # AUR: interactive Wayland protocol debugger/proxy

# Nix (nixpkgs)
nix-env -iA nixpkgs.weston        # weston-info
nix-env -iA nixpkgs.wayland-utils # wayland-info
nix-env -iA nixpkgs.wldbg         # wldbg
# home-manager: no canonical module — install via environment.systemPackages
```

---

## 45.1 WAYLAND_DEBUG — Protocol Tracing

`WAYLAND_DEBUG` is the most fundamental Wayland debugging tool. It instructs the client-side libwayland to print every protocol message it sends or receives to stderr. This gives you a complete trace of the Wayland wire protocol in human-readable form, which is invaluable when diagnosing protocol errors, unexpected object destruction sequences, or missing capability negotiations.

The variable accepts three values: `1` (or any non-empty string) enables both client and server tracing for client processes; `client` restricts output to client-originated messages; `server` is intended for compositor processes to log all server-side traffic. In practice, you almost always want `1` when debugging a specific application, and `server` only when running a compositor you control (like a development build of Sway or wlroots-based compositors).

The output format is: `[timestamp in microseconds] ID -> interface@version.method(arg0, arg1, ...)` for requests (client to server), and `[timestamp] ID <- interface@version.event(arg0, arg1, ...)` for events (server to client). Object IDs are integers; the interface name maps the ID to a type, making the trace mostly self-explanatory once you are familiar with the core Wayland protocol and extension protocols like `xdg-shell`.

```bash
# Basic: trace all protocol messages for a single app
WAYLAND_DEBUG=1 kitty 2>&1 | head -100

# Filter to just surface-related messages
WAYLAND_DEBUG=1 firefox 2>&1 | grep wl_surface

# Filter for XDG shell negotiation (window creation sequence)
WAYLAND_DEBUG=1 alacritty 2>&1 | grep -E 'xdg_(wm_base|surface|toplevel)'

# Trace and save to file for post-analysis
WAYLAND_DEBUG=1 obs 2>&1 | tee /tmp/obs-wayland-debug.log

# Client-only messages (less noise from event callbacks)
WAYLAND_DEBUG=client mpv --vo=gpu video.mkv 2>&1 | grep -v wl_display

# Run compositor with server-side tracing (for development compositors)
WAYLAND_DEBUG=server ./my-wlroots-compositor 2>&1 | tee /tmp/compositor-trace.log
```

When reading WAYLAND_DEBUG output, watch for these patterns:

- **Protocol errors**: `wl_display@1.error(object_id, code, message)` — the compositor is terminating the client for a protocol violation
- **Object not found**: messages referencing an object ID that was already destroyed indicate a use-after-free in the application's Wayland handling
- **Version mismatch**: if a client requests an interface version higher than the compositor supports, you will see a bind error followed by disconnection
- **Missing globals**: if an application silently fails, trace its startup and look for `wl_registry.bind` calls — if a required global (e.g. `zwp_linux_dmabuf_v1`) is missing, that explains the failure

```bash
# Grep specifically for protocol errors
WAYLAND_DEBUG=1 broken-app 2>&1 | grep -E '(error|fatal|destroyed)'

# Look at only the first 2 seconds of startup (protocol negotiation phase)
WAYLAND_DEBUG=1 electron-app 2>&1 &
PID=$!
sleep 2
kill $PID
```

The performance cost of `WAYLAND_DEBUG=1` is significant — it serializes every protocol message through a string formatter and write call. Never ship or benchmark with this enabled. For production tracing needs, `wldbg` (section 45.3) offers lower-overhead interception.

---

## 45.2 weston-info — Output and Capability Inspection

`weston-info` is a small utility from the Weston project that connects to the running Wayland compositor as a client and enumerates all advertised globals, outputs, and input devices. Despite the name, it works with any Wayland compositor that follows the standard registry protocol — Sway, Hyprland, KDE Plasma, GNOME Shell, etc.

The primary use case is answering "what does my compositor actually support?" before writing configuration or debugging why a feature is unavailable. It shows each global interface name, its version, and its object ID. If `zwlr_layer_shell_v1` does not appear in the output, your compositor does not support layer-shell, and no amount of Waybar or Ags configuration will make it work. If `wp_fractional_scale_v1` is missing, fractional scaling through that protocol is unavailable.

```bash
# List all compositor globals with versions
weston-info

# Filter for specific protocol families
weston-info 2>/dev/null | grep -i 'layer\|shell\|dmabuf\|drm\|fractional'

# Check if a specific protocol is available
weston-info 2>/dev/null | grep zwlr_layer_shell_v1

# Show output (monitor) information
weston-info 2>/dev/null | grep -A 20 'wl_output'

# Check protocol version supported (important for newer features)
weston-info 2>/dev/null | grep -E 'interface|version'
```

Example output for a Hyprland session might show:

```
interface: 'wl_compositor', version: 6, name: 1
interface: 'wl_subcompositor', version: 1, name: 2
interface: 'wl_data_device_manager', version: 3, name: 3
interface: 'xdg_wm_base', version: 6, name: 4
interface: 'zwlr_layer_shell_v1', version: 4, name: 5
interface: 'wp_fractional_scale_manager_v1', version: 1, name: 6
interface: 'zwp_linux_dmabuf_v1', version: 4, name: 7
```

The version numbers matter. `xdg_wm_base` version 6 added `wm_capabilities` events; `zwp_linux_dmabuf_v1` version 4 added format/modifier negotiation that many GPU-accelerated clients require. If you see version 2 where version 4 is expected, your compositor is outdated relative to what the application needs.

For output inspection, `weston-info` shows the physical dimensions, current mode, refresh rate, subpixel arrangement, and transformation:

```bash
# Detailed output info including current mode and scale
weston-info 2>/dev/null | grep -A 30 'wl_output@'
```

If `weston-info` is not installed, the equivalent can be obtained from `wayland-info` (part of `wayland-utils` on most distributions), which provides identical functionality:

```bash
# Equivalent tool on most distros
wayland-info

# Or using wl-info from wlroots tools
wlr-randr  # for output info specifically
```

---

## 45.3 wldbg — Interactive Protocol Debugger

`wldbg` is a developer-grade Wayland protocol interceptor that sits between a client and the compositor as a transparent proxy. Unlike `WAYLAND_DEBUG`, which only logs, `wldbg` can filter, modify, and break on specific protocol messages, making it suitable for interactive debugging sessions when you need to understand the exact sequence of events that leads to a bug.

The architecture: `wldbg` creates a fake Wayland socket, runs your target application against it, and forwards messages to the real compositor. It can be run in interactive mode (like a debugger prompt), pass-through mode (trace only), or with a Lua script for programmatic filtering and modification.

```bash
# Install (Arch Linux)
paru -S wldbg-git

# Basic pass-through mode: log all messages
wldbg run -- kitty

# Interactive mode: get a prompt to set filters
wldbg -i run -- alacritty

# Filter to only surface and buffer events
wldbg run -f wl_surface,wl_buffer -- obs

# Save trace to file in binary format
wldbg record output.wldbg -- firefox
# Replay and analyze
wldbg replay output.wldbg
```

In interactive mode, the following commands are most useful:

```
# At the wldbg> prompt:
info                    # show current state
filter add wl_surface   # add interface filter
filter add xdg_toplevel
run                     # resume execution
break wl_buffer.release # break when buffer is released
continue                # continue after breakpoint
```

For scripted analysis, wldbg supports Lua plugins:

```lua
-- /tmp/trace-surfaces.lua
-- Log every wl_surface.commit with timestamp
function message(m)
    if m.interface == "wl_surface" and m.name == "commit" then
        wldbg.log(string.format("[%s] surface@%d committed",
            m.time, m.id))
    end
    return true  -- pass through
end
```

```bash
wldbg -s /tmp/trace-surfaces.lua run -- my-app
```

`wldbg` is particularly valuable when debugging:

- Double-free or use-after-free of Wayland objects (you can break exactly when the destroy request is sent)
- Unexpected disconnections (capture the last few messages before the connection drops)
- Protocol version negotiation issues (trace the registry bind sequence)
- Compositor-side crashes triggered by specific client message sequences

Note that `wldbg` requires running the application through its proxy, which means environment-injected applications (via systemd units, D-Bus activation) may need special handling to route through the proxy socket.

---

## 45.4 Compositor Logs and State Inspection

Each major compositor has its own logging and state inspection commands. The first step after witnessing a crash or misbehavior is always to check the compositor log — not the application log. Compositor logs contain protocol error reports, DRM/KMS failures, and rendering pipeline errors that appear nowhere else.

### Hyprland

```bash
# Live log following (if running as systemd user service)
journalctl --user -u hyprland -f

# Log file location (when started from a TTY or display manager)
tail -f ~/.local/share/hyprland/hyprland.log

# Version and commit hash (important for bug reports)
hyprctl version

# Full compositor state
hyprctl monitors          # output configuration with current mode, scale, transform
hyprctl clients           # all open windows with their Wayland class, pid, workspace
hyprctl workspaces        # workspace list with window counts
hyprctl activewindow      # focused window details
hyprctl devices           # input devices (keyboard, mouse, tablet)
hyprctl animations        # current animation state
hyprctl layers            # layer-shell surfaces (bars, notifications, wallpaper)
hyprctl binds             # active keybindings

# Specific debugging flags in hyprland.conf
debug {
    disable_logs = false
    enable_stdout_logs = true   # print to stdout in addition to log file
    damage_tracking = 2         # 0=none, 1=monitor, 2=full (very verbose)
    disable_scale_checks = false
    colored_stdout_logs = true
}

# Force reload config and watch for errors
hyprctl reload
journalctl --user -u hyprland -f --since "5 seconds ago"
```

### Sway

```bash
# Sway logs via journald
journalctl --user -u sway -f
journalctl --user -u sway --since "10 minutes ago" | grep -i error

# Real-time state queries (all return JSON)
swaymsg -t get_tree                 # full window tree
swaymsg -t get_outputs              # output list with current mode
swaymsg -t get_workspaces           # workspace list
swaymsg -t get_seats                # input seat configuration
swaymsg -t get_inputs               # input devices
swaymsg -t get_marks                # window marks
swaymsg -t get_bar_config           # bar configuration

# Pretty-print the window tree
swaymsg -t get_tree | python3 -m json.tool | grep -E '"name"|"app_id"|"pid"'

# Check IPC socket
echo $SWAYSOCK
ls -la $SWAYSOCK

# Enable debug logging (add to sway config)
# sway -d 2>&1 | tee ~/sway-debug.log
```

### GNOME / Mutter

```bash
# GNOME Shell logs
journalctl /usr/bin/gnome-shell -f
journalctl /usr/bin/gnome-shell --since "1 minute ago" | grep -i 'error\|warning\|crash'

# GNOME Shell introspection via D-Bus
gdbus call --session \
    --dest org.gnome.Shell \
    --object-path /org/gnome/Shell \
    --method org.gnome.Shell.Eval \
    "global.get_window_actors().map(w => w.meta_window.get_title())"

# Reload GNOME Shell (X11 only — on Wayland this restarts the session)
# Instead, use the Looking Glass debugger: Alt+F2, type 'lg'
```

### KDE Plasma / KWin

```bash
# KWin logs
journalctl /usr/bin/kwin_wayland -f

# KWin D-Bus interface
qdbus org.kde.KWin /KWin supportInformation

# KWin debug console (opens in-session window)
qdbus org.kde.KWin /KWin showDebugConsole
```

---

## 45.5 Environment Variable Debugging

The most common class of Wayland bugs is not protocol errors — it is misconfigured environment variables causing applications to run in the wrong mode, at the wrong scale, or with the wrong backend. Always verify the environment before deep-diving into protocol traces.

```bash
# Confirm the session is Wayland
echo "WAYLAND_DISPLAY: $WAYLAND_DISPLAY"       # e.g. wayland-1
echo "XDG_SESSION_TYPE: $XDG_SESSION_TYPE"     # must be "wayland"
echo "XDG_RUNTIME_DIR: $XDG_RUNTIME_DIR"       # e.g. /run/user/1000
echo "DISPLAY: $DISPLAY"                        # X11 display (for XWayland)
echo "XDG_CURRENT_DESKTOP: $XDG_CURRENT_DESKTOP"  # e.g. Hyprland, sway, GNOME

# Verify the Wayland socket exists
ls -la "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY"

# Check what environment a running process sees
PID=$(pgrep -f firefox | head -1)
cat /proc/$PID/environ | tr '\0' '\n' | grep -E 'WAYLAND|XDG|GDK|QT|MOZ'

# Force Wayland for common toolkits
# GTK3/4
GDK_BACKEND=wayland app
# Qt5/6
QT_QPA_PLATFORM=wayland app
QT_WAYLAND_DISABLE_WINDOWDECORATION=1 app  # use CSD instead of SSD
# Firefox / Electron
MOZ_ENABLE_WAYLAND=1 firefox
# Electron (newer apps that respect this)
ELECTRON_OZONE_PLATFORM_HINT=wayland code

# Scaling environment variables
GDK_SCALE=2                    # GTK integer scaling
GDK_DPI_SCALE=1.5              # GTK fractional (font) scaling
QT_SCALE_FACTOR=1.5            # Qt scaling
XCURSOR_SIZE=24                 # cursor size (also set in compositor config)
XCURSOR_THEME=Adwaita           # cursor theme name

# Set these permanently in ~/.config/hypr/hyprland.conf (Hyprland)
# env = QT_QPA_PLATFORM,wayland
# env = GDK_BACKEND,wayland,x11,*  (fallback chain)
# env = MOZ_ENABLE_WAYLAND,1
```

A useful diagnostic: compare the environment of a working application against a broken one.

```bash
# Dump environment of working app
cat /proc/$(pgrep kitty)/environ | tr '\0' '\n' | sort > /tmp/kitty-env.txt

# Dump environment of broken app
cat /proc/$(pgrep broken-app)/environ | tr '\0' '\n' | sort > /tmp/broken-env.txt

# Diff them
diff /tmp/kitty-env.txt /tmp/broken-env.txt
```

---

## 45.6 XWayland Debugging

XWayland is the compatibility layer that runs X11 applications inside a Wayland session. Many apparent "Wayland" bugs are actually XWayland bugs, or the application has silently fallen back to X11 via XWayland. Distinguishing XWayland from native Wayland clients is the first diagnostic step.

```bash
# List all X11 clients currently using XWayland
xlsclients -l

# Identify if a specific window is X11 or native Wayland
# In Hyprland: check hyprctl clients output
hyprctl clients | grep -A 10 "class: discord"
# If "xwayland: 1" appears, it's running via XWayland

# In Sway: check the tree
swaymsg -t get_tree | python3 -m json.tool | grep -B5 -A15 '"discord"'
# app_id: null and shell: "xwayland" means XWayland

# Inspect X11 window properties (useful for WM_CLASS, _NET_WM_NAME, etc.)
xprop -root                          # root window properties
xprop -id $(xdotool getactivewindow) # active window properties
xprop WM_CLASS                       # application class/instance

# List XWayland virtual display
xrandr --display $DISPLAY

# XWayland rendering fallbacks
XWAYLAND_NO_GLAMOR=1 app            # disable EGL/GL acceleration in XWayland (software rendering)
LIBGL_ALWAYS_SOFTWARE=1 app         # force Mesa software rasterizer (llvmpipe/softpipe)

# Check XWayland process
ps aux | grep Xwayland
# Note the -displayfd and -rootless flags
# -rootless: normal embedded mode
# Without -rootless: full X11 screen takeover (unusual)

# XWayland DPI for HiDPI screens
# The virtual display always reports 96 DPI; override with:
xrandr --dpi 192 --display :0  # for 2x HiDPI (set in startup script)
# Or use Xresources:
echo "Xft.dpi: 192" | xrdb -merge
```

Common XWayland-specific issues:

| Symptom | Cause | Diagnosis | Fix |
|---------|-------|-----------|-----|
| Blurry X11 app on HiDPI | XWayland 96 DPI assumption | `xrandr --display :0` shows 96 DPI | `xrandr --dpi 192 --display :0` |
| X11 app input lag | No relative pointer support | Check for `xwayland_seat_grab` in logs | Use native Wayland version if available |
| X11 copy-paste broken | X11/Wayland clipboard bridge | `xclip -o` fails | Ensure `xwayland-satellite` or compositor sync is running |
| Window won't go fullscreen | XWayland decoration conflict | `xprop _MOTIF_WM_HINTS` | Set `_NET_WM_STATE_FULLSCREEN` explicitly |

---

## 45.7 xdg-desktop-portal Debugging

The `xdg-desktop-portal` (XDP) is the D-Bus service that mediates access to system resources for sandboxed and unsandboxed applications alike — file chooser dialogs, screenshots, screen sharing (PipeWire), settings, print dialogs, and more. When screenshots are blank, screen sharing fails, or file dialogs show the wrong theme, XDP is almost always involved.

The portal architecture: a central `xdg-desktop-portal` process dispatches requests to desktop-environment-specific backend implementations. On Hyprland you want `xdg-desktop-portal-hyprland`; on Sway/wlroots you want `xdg-desktop-portal-wlr`; on GNOME you want `xdg-desktop-portal-gnome`. Having the wrong backend active, or multiple backends conflicting, is the most common failure mode.

```bash
# Check portal service status
systemctl --user status xdg-desktop-portal
systemctl --user status xdg-desktop-portal-hyprland
systemctl --user status xdg-desktop-portal-wlr
systemctl --user status xdg-desktop-portal-gnome

# View recent portal logs
journalctl --user -u xdg-desktop-portal -n 50 --no-pager
journalctl --user -u xdg-desktop-portal-hyprland -n 50 --no-pager

# Check which portals are registered
ls /usr/share/xdg-desktop-portal/portals/
# Each .portal file declares which interfaces it handles

# Check the portal configuration for your desktop
cat /usr/share/xdg-desktop-portal/hyprland-portals.conf
# Or create an override:
mkdir -p ~/.config/xdg-desktop-portal/
cat > ~/.config/xdg-desktop-portal/hyprland-portals.conf << 'EOF'
[preferred]
default=hyprland;gtk
org.freedesktop.impl.portal.ScreenCast=hyprland
org.freedesktop.impl.portal.Screenshot=hyprland
org.freedesktop.impl.portal.Settings=gtk
EOF

# Restart portals after config change
systemctl --user restart xdg-desktop-portal
systemctl --user restart xdg-desktop-portal-hyprland

# Enable debug output (run manually to see all D-Bus traffic)
XDG_DESKTOP_PORTAL_DEBUG=1 /usr/libexec/xdg-desktop-portal 2>&1 | tee /tmp/xdp-debug.log

# Check XDG_CURRENT_DESKTOP — this is how the portal selects its backend
echo $XDG_CURRENT_DESKTOP
# For Hyprland it should be: Hyprland
# For Sway: sway (lowercase)
# Must be set before the portal starts

# Test screen sharing manually via D-Bus
gdbus call --session \
    --dest org.freedesktop.portal.Desktop \
    --object-path /org/freedesktop/portal/desktop \
    --method org.freedesktop.portal.ScreenCast.CreateSession \
    "{'session_handle_token': <'session1'>, 'handle_token': <'request1'>}"
```

For PipeWire-based screen sharing (used by OBS, browsers, etc.):

```bash
# Verify PipeWire is running
systemctl --user status pipewire pipewire-pulse wireplumber

# Check for active PipeWire screenshare streams
pw-cli list-objects | grep -A5 'Stream\|ScreenShare'

# Monitor PipeWire graph for screen capture nodes
pw-top

# Test PipeWire screen capture
gst-launch-1.0 pipewiresrc ! videoconvert ! autovideosink
```

---

## 45.8 Common Issues and Fixes

This table covers the most frequently encountered Wayland configuration and compatibility issues. When a symptom matches, follow the fix column before proceeding to deeper debugging.

| Symptom | Cause | Fix |
|---------|-------|-----|
| App starts on X11 not Wayland | Missing toolkit env vars | `QT_QPA_PLATFORM=wayland`, `GDK_BACKEND=wayland,x11,*`, `MOZ_ENABLE_WAYLAND=1` |
| Blurry apps on HiDPI | Wrong scale factor | `GDK_SCALE=2`, `QT_SCALE_FACTOR=2`, check compositor `monitor_scale` setting |
| No clipboard after app closes | No clipboard manager daemon | Start `wl-paste --watch cliphist store` or `clipman` on login |
| Screenshot black/empty | Wrong or missing portal backend | Install `xdg-desktop-portal-hyprland`/`-wlr`, verify `XDG_CURRENT_DESKTOP` |
| Cursor disappears over certain windows | Hardware cursor compositing bug | `WLR_NO_HARDWARE_CURSORS=1` in environment |
| App crashes immediately on Wayland | Protocol error at startup | `WAYLAND_DEBUG=1 app 2>&1 \| head -50` — look for `wl_display.error` |
| Screen share black in browser | Wrong portal or PipeWire issue | Reinstall correct `xdg-desktop-portal-*`, restart portals and PipeWire |
| Keyboard layout wrong in X11 apps | XKB not propagated to XWayland | Set `XKB_DEFAULT_LAYOUT` env var; check compositor `input.kb_layout` |
| Window decorations missing or doubled | CSD/SSD mismatch | `QT_WAYLAND_DISABLE_WINDOWDECORATION=1` for Qt, or configure `xdg-decoration-manager` |
| Tearing in fullscreen | Direct scanout failure | Disable direct scanout: `WLR_DRM_NO_ATOMIC=1` or compositor `allow_tearing = false` |
| Mouse input lag in games | Relative pointer protocol missing | Enable `mouse:relative_motion` in compositor; check `zwp_relative_pointer_manager_v1` |
| Fractional scaling blurry | No fractional scale protocol | Enable `wp_fractional_scale_v1` in compositor; use `GDK_SCALE=1` + compositor-side scaling |
| IME/input method broken | Missing `text-input-v3` implementation | Install `fcitx5-qt` and `fcitx5-gtk`, set `GTK_IM_MODULE=fcitx`, `QT_IM_MODULE=fcitx` |
| Drag and drop fails between apps | DnD proxy issue in XWayland | Ensure `xwayland-satellite` or compositor DnD proxying is enabled |

---

## 45.9 GPU and Rendering Debugging

GPU and rendering issues on Wayland are distinct from the protocol layer — they involve DRM/KMS, Mesa/Vulkan drivers, and hardware composition. The key insight is that Wayland compositors communicate with the GPU via DRM (Direct Rendering Manager), and clients communicate with the GPU via EGL/Vulkan directly; protocol errors and GPU errors are separate diagnostic domains.

```bash
# Identify GPU devices
ls /dev/dri/
# card0, card1: DRM display devices (connected to display)
# renderD128, renderD129: render-only nodes (for offloading)

# Inspect DRM device capabilities
drm_info                            # detailed DRM driver and device info
drm_info -j | python3 -m json.tool  # JSON format for scripting

# Check which GPU is being used by a process
# For Mesa-based drivers:
MESA_DEBUG=1 app 2>&1 | grep -i 'driver\|device\|GL version'

# Force discrete GPU (PRIME offloading)
DRI_PRIME=1 app                     # select discrete GPU
DRI_PRIME=pci-0000_01_00_0 app      # select by PCI address (from drm_info)

# Mesa debugging levels
MESA_DEBUG=1 app                    # enable Mesa debug messages
MESA_DEBUG=incomplete app           # warn on incomplete features
LIBGL_DEBUG=verbose app             # verbose OpenGL error output
MESA_GLSL_CACHE_DISABLE=true app    # disable shader cache (test compilation bugs)

# Vulkan debugging
VK_LOADER_DEBUG=all app             # Vulkan loader debug (layer loading, ICD selection)
VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/radeon_icd.x86_64.json app  # force ICD
vulkaninfo                          # enumerate Vulkan devices, layers, extensions
vulkaninfo --summary                # brief device summary

# Check if DMA-BUF import/export works (zero-copy buffer sharing)
WAYLAND_DEBUG=1 app 2>&1 | grep -i 'dmabuf\|linux_dmabuf'
# Should see zwp_linux_dmabuf_v1 messages if zero-copy is working

# EGL debugging
EGL_LOG_LEVEL=debug app 2>&1 | grep -i egl    # EGL initialization trace
EGL_PLATFORM=wayland app                        # force EGL Wayland platform

# Check for software rendering fallback (very slow)
LIBGL_DEBUG=verbose app 2>&1 | grep -i 'softpipe\|llvmpipe\|software'

# GPU memory and power
cat /sys/class/drm/card0/device/mem_info_vram_used  # VRAM used (AMD)
cat /sys/class/drm/card0/device/power_dpm_state      # power state
intel_gpu_top                                         # Intel GPU utilization
radeontop                                             # AMD GPU utilization
nvtop                                                 # NVIDIA/AMD unified top
```

For rendering artifact debugging (tearing, glitches, wrong colors):

```bash
# Check DRM atomic modesetting (preferred, enables advanced features)
cat /sys/module/amdgpu/parameters/atomic  # should be 'Y'
# Disable for debugging:
WLR_DRM_NO_ATOMIC=1 sway

# Test direct scanout (compositor bypasses GPU for fullscreen apps)
# Hyprland:
# misc:allow_tearing = true / false
# Sway: no_focus [direct scanout]

# Check color depth and HDR support
weston-info 2>/dev/null | grep -E 'bpc|hdr|color'

# Debugging screen flicker (check DRM vblank events)
WAYLAND_DEBUG=1 weston-simple-damage 2>&1 | grep frame

# Test compositing with software rendering (eliminate GPU as variable)
WLR_RENDERER=pixman sway            # wlroots: use CPU-side Pixman renderer
WLR_RENDERER=gles2 sway             # wlroots: use OpenGL ES 2 renderer (default)
WLR_RENDERER=vulkan sway            # wlroots: use Vulkan renderer (experimental)
```

---

## 45.10 Quickshell-Specific Debugging

Quickshell is a QML-based shell framework for Wayland. Debugging it requires understanding both the Wayland layer (layer-shell protocol, surface positioning) and the QML/Qt layer (object lifecycle, signal/slot connections, property bindings). Errors can originate at either level.

```bash
# Enable all debug output
quickshell --log-rules "*.debug=true" &> /tmp/qs-debug.log

# Module-specific debug (less noisy)
quickshell --log-rules "Quickshell.Hyprland.debug=true"
quickshell --log-rules "Quickshell.Wayland.debug=true"
quickshell --log-rules "Quickshell.Service.*.debug=true"

# Combine multiple module rules
quickshell --log-rules "Quickshell.Hyprland.debug=true;Quickshell.Io.debug=true"

# Reload shell config without restart (if supported by your config)
pkill -USR1 quickshell
# Or use the IPC socket if configured

# Live config reload with error output
quickshell --log-rules "*.warning=true;*.critical=true" 2>&1 | tee /tmp/qs-errors.log
```

For QML-level debugging:

```qml
// Log any value in QML (shows in terminal output)
Component.onCompleted: {
    console.log("Widget loaded:", JSON.stringify({
        x: x, y: y, width: width, height: height
    }))
}

// Watch a property for changes
onWidthChanged: console.log("Width changed to:", width)

// Debug signal connections
Connections {
    target: someObject
    onSomeSignal: {
        console.log("Signal fired:", JSON.stringify(arguments))
    }
}

// Inspect object tree at runtime
Component.onCompleted: {
    var obj = parent
    while (obj) {
        console.log("Parent:", obj, obj.objectName)
        obj = obj.parent
    }
}
```

Common Quickshell issues:

```bash
# Layer surface not appearing — check layer-shell protocol
weston-info 2>/dev/null | grep zwlr_layer_shell_v1
# Must be present for Quickshell surfaces to work

# Anchoring issues — verify screen geometry
hyprctl monitors | grep -E 'Monitor|resolution|at'

# QML property binding loops (causes CPU spike)
# Symptom: 100% CPU, no visible output
# Find: look for "QML Binding loop detected" in output
quickshell 2>&1 | grep -i 'binding loop'

# Service not connecting (e.g. Hyprland IPC)
# Test Hyprland socket manually
echo -n '{"type":"activewindow"}' | nc -U $XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket.sock

# Font rendering issues in QML
# Force font backend
QT_QPA_PLATFORM=wayland QT_FONT_DPI=96 quickshell
```

---

## 45.11 Systematic Debugging Workflow

When encountering an unfamiliar Wayland bug, apply this structured workflow rather than random tool invocation:

**Step 1: Identify the layer**

```bash
# Is the session actually Wayland?
echo $XDG_SESSION_TYPE                    # must be "wayland"
echo $WAYLAND_DISPLAY                     # must be non-empty

# Is the app using Wayland or XWayland?
hyprctl clients | grep -A5 "class: myapp" | grep xwayland
# xwayland: 0 = native Wayland; xwayland: 1 = XWayland
```

**Step 2: Check compositor health**

```bash
# Any errors in compositor log in the last minute?
journalctl --user -u hyprland --since "1 minute ago" | grep -iE 'error|warn|critical'

# Compositor state consistent?
hyprctl monitors   # any outputs missing or with wrong mode?
hyprctl clients    # are all expected windows present?
```

**Step 3: Verify environment**

```bash
cat /proc/$(pgrep -f myapp | head -1)/environ | tr '\0' '\n' | \
    grep -E 'WAYLAND|XDG|GDK|QT|MOZ|ELECTRON' | sort
```

**Step 4: Protocol trace**

```bash
# Run with protocol tracing, capture first 100 lines (startup negotiation)
WAYLAND_DEBUG=1 myapp 2>&1 | head -100
# Look for: wl_display.error, unexpected object destruction, missing globals
```

**Step 5: Portal check (if desktop integration fails)**

```bash
systemctl --user status xdg-desktop-portal xdg-desktop-portal-hyprland
journalctl --user -u xdg-desktop-portal -n 20 --no-pager
```

**Step 6: GPU/rendering check (if visual artifacts)**

```bash
MESA_DEBUG=1 LIBGL_DEBUG=verbose myapp 2>&1 | grep -iE 'error|warn|software|llvmpipe'
```

---

## Troubleshooting

**Problem: `WAYLAND_DEBUG=1` produces no output**

The application may have dropped privileges (suid binary) or is using a system Wayland connection (not the user session). Check `$WAYLAND_DISPLAY` is set, and that the socket exists at `$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY`. If the app is Flatpak, it runs in a sandbox with its own socket relay — use Flatpak's `--env` flag or `flatpak override`.

**Problem: `weston-info` reports nothing / connection refused**

The `WAYLAND_DISPLAY` environment variable is not set or points to a non-existent socket. Run `ls -la $XDG_RUNTIME_DIR/wayland-*` to see which sockets exist. If none exist, the compositor is not running or did not create its socket. Check compositor logs.

**Problem: Portal services crash on startup**

Missing backend implementation — e.g. `xdg-desktop-portal-hyprland` is not installed, so the portal fails trying to load it. Install the correct backend package for your compositor and verify `XDG_CURRENT_DESKTOP` is set correctly in your session environment (must be set before the portal starts, typically in your compositor's `exec-once` or systemd user environment).

**Problem: Protocol trace shows `wl_display@1.error` followed by disconnect**

This is a hard protocol violation — the compositor is terminating the client. The error message includes the object ID, error code, and a string message. Common causes: requesting an interface version higher than what the compositor supports (fix: update compositor); using an object after it was destroyed (fix: update the application or report a bug); sending requests in the wrong order (application bug).

**Problem: GPU apps render black window on Wayland**

The application cannot establish an EGL Wayland surface. Check: (1) `EGL_PLATFORM=wayland` is not conflicting with an explicit `DISPLAY` variable; (2) Mesa EGL Wayland extensions are present (`eglinfo | grep wayland`); (3) `zwp_linux_dmabuf_v1` is advertised by the compositor (`weston-info | grep dmabuf`). As a fallback, try `LIBGL_ALWAYS_SOFTWARE=1` to rule out hardware EGL issues.

**Problem: Screen sharing works in OBS but not in browser**

Browsers typically require `xdg-desktop-portal` version 1.17+ with PipeWire screen cast. The portal version in your distribution may be too old. Check `pkg-config --modversion xdg-desktop-portal`. Also ensure `ENABLE_MEDIA_STREAM_DESKTOP_CAPTURE` is enabled in browser flags (Chromium: `chrome://flags/#enable-webrtc-pipewire-capturer`).

**Problem: Quickshell surfaces appear on wrong monitor**

Check that monitor names in your QML `ShellLayer.screens` match the names reported by `hyprctl monitors` (e.g. `DP-1`, `HDMI-A-1`). Screen names changed between Hyprland versions — what was `DP-1` may become `eDP-1`. Use `wlr-randr` or `weston-info` to list current output names.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
