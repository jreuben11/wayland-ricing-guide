# Chapter 1 — The Wayland Protocol: Architecture and Philosophy

> *"Every frame is perfect."* — The Wayland design manifesto

This chapter lays the conceptual groundwork for everything that follows in this book. Before you can rice a Wayland desktop effectively, you need to understand why Wayland was built the way it was, what problems it solves, and how the protocol machinery works beneath the compositor you will configure. Superficial knowledge leads to configurations that break mysteriously; architectural understanding lets you reason from first principles.

---

## Contents

- [1.1 The X11 Legacy Problem](#11-the-x11-legacy-problem)
- [1.2 Wayland's Design Goals](#12-waylands-design-goals)
- [1.3 The Wayland Architecture](#13-the-wayland-architecture)
- [1.4 Key Actors in the Ecosystem](#14-key-actors-in-the-ecosystem)
- [1.5 Wayland vs. X11: Practical Differences for Users](#15-wayland-vs-x11-practical-differences-for-users)
- [1.6 The Wayland Object Model in Detail](#16-the-wayland-object-model-in-detail)
- [1.7 Protocol Namespaces and Extension Stability](#17-protocol-namespaces-and-extension-stability)
- [1.8 Ricing-Relevant Protocols at a Glance](#18-ricing-relevant-protocols-at-a-glance)
- [Key References](#key-references)
- [Troubleshooting](#troubleshooting)
  - [Application starts under XWayland instead of native Wayland](#application-starts-under-xwayland-instead-of-native-wayland)
  - [`WAYLAND_DISPLAY` not set after login](#waylanddisplay-not-set-after-login)
  - [Compositor crashes with `EGL_BAD_ALLOC` or `DRM_IOCTL failed`](#compositor-crashes-with-eglbadalloc-or-drmioctl-failed)
  - [Protocol version mismatch errors](#protocol-version-mismatch-errors)
  - [`WAYLAND_DEBUG` output is overwhelming](#waylanddebug-output-is-overwhelming)
  - [Application renders blurry on HiDPI display](#application-renders-blurry-on-hidpi-display)

---


## 1.1 The X11 Legacy Problem

The X Window System was designed in 1984 at MIT and first released in 1987. It was engineered around the assumption that display hardware would live on a remote machine and that the protocol needed to be fully network-transparent. This was genuinely visionary for its era: X allowed a program running on a VAX in the machine room to display windows on a workstation across the building, all through TCP/IP sockets. The network transparency was not an accident — it was the primary design goal.

By the mid-2000s, however, that assumption had inverted. Over 99% of X11 usage occurred on machines where the application and the display server ran on the same physical hardware. The network-transparency machinery — the round-trip latency, the serialisation overhead, the complexity of X11's 200+ protocol extensions — became pure cost with no corresponding benefit. More critically, X11's security model had not aged well. The X server is a trusted oracle that all clients share: any client can send synthetic input events to any other client's window, and any client can capture screenshots of the entire screen without privilege escalation. These are not theoretical attack vectors; they are exploited by screen-capture malware and keyloggers that run completely in userspace.

The split between the display server and the compositor further compounded the problem. Xorg handles input and drives the hardware. Compositing window managers like Mutter (GNOME) and KWin (KDE Plasma) run as ordinary X11 clients that intercept redirection to off-screen buffers, composite those buffers, and display the result. This double-render path means every frame touches the GPU twice. Tearing — the visible artefact where the top half of the screen shows one frame and the bottom half shows the previous frame — occurs because Xorg and the compositing window manager are not synchronised with the hardware vertical-blank interval.

The canonical demonstration of X11's latency problem is the `xeyes` experiment: move the mouse and watch the eyes track with a perceptible lag. The lag is not the hardware's fault. It is the protocol: the mouse movement travels from the kernel through `libinput` to Xorg, then Xorg serialises an event, sends it to the compositor, the compositor wakes up and sends it to the client, the client computes a new frame, sends that back to Xorg, and Xorg sends it to the GPU. There are four IPC hops where Wayland requires one.

```bash
# Visualise X11 round-trip latency with xdotool
# Install: sudo apt install xdotool xeyes
xeyes &
# In another terminal, record input latency
sudo cat /dev/input/event4 | hexdump -C | head -40
# Compare timestamps in kernel events vs. when xeyes repaints
```

---

## 1.2 Wayland's Design Goals

Wayland's specification was started by Kristian Høgsberg at Red Hat in 2008. The core insight was that for the local-only case, the entire X11 protocol stack could be replaced by a much simpler mechanism: shared memory buffers plus a minimal IPC protocol for coordinating who owns which buffer at any given moment. The compositor — which already had to exist to do compositing — could talk directly to the kernel's DRM/KMS subsystem to drive the display without an intermediary display server.

The "every frame is perfect" philosophy means that by design, the compositor only presents a frame to the hardware once it is complete. Clients write into their own private buffers. When a client is done painting, it commits the buffer to the compositor via a `wl_surface.commit` call. The compositor waits for the next hardware vblank, composites all pending committed surfaces, and hands the complete framebuffer to the GPU. The client never sees a partially-rendered frame from another client, and the hardware never sees a partially-updated framebuffer. Tearing is structurally impossible.

Security isolation follows directly from the architecture. In Wayland, each client has a private connection to the compositor over a Unix socket. There is no shared global namespace analogous to the X11 root window. A client cannot enumerate other clients' surfaces, cannot inject synthetic events into another client's input stream, and cannot capture another client's pixels without the compositor's explicit cooperation. Screen capture and remote desktop require purpose-built protocols (`wlr-screencopy-v1`, `ext-remote-access-v1`) that the compositor controls, not capabilities that every client inherits.

The protocol is intentionally minimal. The core `wayland.xml` protocol covers only the primitives that every compositor must implement: object lifecycle, surface creation, input seat management, and output geometry. Everything else — window decorations, fullscreen, layer-shell surfaces, screenshotting, gamma control — is defined in separate extension protocol XML files. This means a tiling compositor for embedded kiosks can implement only what it needs, while a full desktop compositor can implement the rich set of extension protocols that ricing depends on.

Extension-based growth has been formalised through two mechanisms. First, the `xdg-shell` protocol, maintained at freedesktop.org, defines the standard window management interface used by all major toolkits (GTK4, Qt6, SDL2, etc.). Second, `wlr-protocols` (maintained by the sway/wlroots project) and `ext-protocols` (the newer freedesktop.org namespace) provide higher-level interfaces. The distinction matters: `xdg-*` protocols are stable and widely supported; `wlr-*` protocols are wlroots-compositor-specific; `ext-*` protocols are the emerging cross-compositor standard.

```bash
# Inspect the extension protocols installed on your system
ls /usr/share/wayland-protocols/
# Output structure:
# stable/    — ratified, no breaking changes
# staging/   — in progress, may break
# unstable/  — legacy name for staging

ls /usr/share/wlr-protocols/
# wlroots-specific protocols (wlr-layer-shell, wlr-screencopy, etc.)
```

---

## 1.3 The Wayland Architecture

The Wayland architecture has exactly three parties: clients, the compositor, and the kernel (hardware). There is no separate display server process. The compositor is simultaneously the display server, the window manager, and the compositor — three roles that were split across separate processes under X11 now unified into a single process that can make all rendering decisions atomically.

The client-compositor communication channel is a Unix domain socket, typically `/run/user/$UID/wayland-0`. The `$WAYLAND_DISPLAY` environment variable names the socket (relative to `$XDG_RUNTIME_DIR`). When a client starts, it opens this socket, sends a `wl_display.get_registry` request, and receives back a list of all global objects the compositor advertises. A global is an interface the compositor implements — `wl_compositor`, `wl_shm`, `wl_seat`, `wl_output`, `xdg_wm_base`, `zwlr_layer_shell_v1`, etc. The client binds only the globals it needs.

```bash
# Inspect what globals your compositor advertises
# wayland-info is in the wayland-utils / libwayland-bin package
wayland-info

# Example output excerpt:
# interface: 'wl_compositor', version: 6, name: 1
# interface: 'wl_shm', version: 2, name: 2
# interface: 'xdg_wm_base', version: 6, name: 10
# interface: 'zwlr_layer_shell_v1', version: 5, name: 23
# interface: 'wp_fractional_scale_manager_v1', version: 1, name: 31

# Check which compositor-specific protocols are available
weston-info 2>/dev/null || wayland-info
```

The Wayland IPC model is fundamentally asynchronous and object-oriented. The client sends *requests* (client-to-compositor messages) and receives *events* (compositor-to-client messages). Every object has an integer ID. The client allocates new object IDs locally (they never conflict because client-allocated IDs are in one range and server-allocated IDs are in another). The wire format is compact: a 4-byte object ID, a 4-byte combined opcode+size, followed by arguments. File descriptors are passed out-of-band via `SCM_RIGHTS` ancillary data on the socket.

The compositor's relationship with the kernel goes through two subsystems. The **DRM/KMS** (Direct Rendering Manager / Kernel Mode Setting) subsystem gives the compositor exclusive control over scanout: it configures CRTCs (display controllers), planes (hardware layers for overlays), and connectors (physical output ports). The **GBM** (Generic Buffer Management) library provides an API for allocating GPU-native buffers that can be scanned out directly — a zero-copy path from client rendering to display. The **libinput** library sits between the kernel's `evdev` input events and the compositor's seat management, handling device enumeration, gesture recognition, and touchpad configuration.

```
┌─────────────────────────────────────────────────────────────────┐
│                         COMPOSITOR                              │
│   ┌───────────┐    ┌──────────────┐    ┌─────────────────────┐ │
│   │  wl_seat  │    │ wl_compositor│    │   DRM/KMS output    │ │
│   │ (input)   │    │  (surfaces)  │    │   (scanout)         │ │
│   └─────┬─────┘    └──────┬───────┘    └──────────┬──────────┘ │
│         │                 │                       │             │
└─────────┼─────────────────┼───────────────────────┼─────────────┘
          │  Unix socket    │                       │ DRM ioctl
     ┌────▼────┐      ┌─────▼─────┐          ┌─────▼──────┐
     │ Client  │      │  Client   │          │   Kernel   │
     │ (gtk4)  │      │  (qt6)    │          │ (DRM/KMS)  │
     └─────────┘      └───────────┘          └────────────┘
          │                 │
          └── /run/user/1000/wayland-0
```

Comparing Wayland with **Mir** (Canonical's display server, now primarily used on Ubuntu Frame for embedded systems): Mir has a similar architecture but a different protocol design philosophy. Where Wayland delegates window management entirely to extensions, Mir includes more opinionated window management primitives in its core protocol. For desktop ricing, Mir is largely irrelevant — the entire tooling ecosystem (waybar, swaylock, rofi-wayland, wlr-randr, etc.) targets Wayland.

---

## 1.4 Key Actors in the Ecosystem

Understanding the libraries that mediate between your applications and the compositor is essential for troubleshooting. When a Wayland application fails to start, the failure is almost always in one of these layers.

**`libwayland-client`** is the reference implementation of the client side of the Wayland IPC protocol. It handles socket connection, object marshalling, event dispatch, and the proxy object model. Almost every toolkit uses it, either directly (GTK4, SDL2) or via a higher-level abstraction. The library version on your system must be compatible with the protocol version the compositor advertises; mismatches produce cryptic errors. Relevant env vars: `WAYLAND_DEBUG=1` enables full protocol trace logging.

```bash
# Enable Wayland protocol debug tracing for any application
WAYLAND_DEBUG=1 foot 2>&1 | head -60
# Shows all requests and events as:
# [1234567.890] -> wl_compositor@1.create_surface(new id wl_surface@5)
# [1234567.891] -> xdg_wm_base@10.get_xdg_surface(new id xdg_surface@6, wl_surface@5)

# Check library versions
pkg-config --modversion wayland-client
pkg-config --modversion wayland-server

# List installed Wayland-related packages (Debian/Ubuntu)
dpkg -l | grep -E 'wayland|wlr' | awk '{print $2, $3}'
```

**`wayland-scanner`** is the code generator that reads Wayland protocol XML files and produces C header/source files containing the request/event marshalling code and opcode constants. If you are writing a compositor or a client that uses unstable protocols, you will run `wayland-scanner` as part of your build. Understanding its output helps when reading compositor source code.

```bash
# Generate client-side header for a protocol
wayland-scanner client-header \
  /usr/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml \
  /tmp/xdg-shell-client-protocol.h

# Generate implementation code
wayland-scanner private-code \
  /usr/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml \
  /tmp/xdg-shell-protocol.c

# Inspect protocol interface names and versions from XML
grep -E 'interface name|version=' \
  /usr/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml
```

**`xkbcommon`** handles keyboard layout parsing and state tracking. X11 used the XKB extension inside the X server; Wayland moved this logic into a standalone library that both compositors and clients link against. The compositor sends keymap data to clients as a shared memory file descriptor. Clients use `xkbcommon` to parse the keymap and track modifier state. Keyboard layout mismatches between compositor and application are almost always an `xkbcommon` configuration problem.

**`libdrm`** and **Mesa** together form the GPU stack. `libdrm` is a thin userspace wrapper around the DRM kernel subsystem — it provides the `ioctl` calls for buffer allocation (via GBM), mode setting (via KMS), and DMA-BUF sharing. Mesa provides the OpenGL, Vulkan, and EGL implementations. The `gbm_surface` / `EGL` path is how most Wayland compositors get GPU-accelerated rendering. The `DRM_FORMAT_*` constants from `libdrm/drm_fourcc.h` appear throughout compositor and protocol code.

```bash
# Check Mesa version and driver in use
glxinfo | grep -E 'OpenGL renderer|OpenGL version'  # may need glx fallback
eglinfo 2>/dev/null | head -20  # from mesa-utils or egl-utils

# List DRM devices
ls -la /dev/dri/
# card0, card1 — display controllers
# renderD128, renderD129 — render-only nodes (no KMS)

# Check kernel DRM driver
cat /sys/class/drm/card0/device/driver/module/version 2>/dev/null || \
  dmesg | grep -i drm | head -10

# Vulkan device info (needed for Vulkan-composited backends)
vulkaninfo --summary 2>/dev/null | head -20
```

**`libinput`** abstracts raw kernel input events into a higher-level model with gesture support, palm rejection, and device-specific quirks. Compositors use it via `wl_seat` to manage keyboard, pointer, and touch objects. The `libinput debug-events` tool is invaluable for diagnosing input problems.

```bash
# Debug all input events (run as root or with appropriate group membership)
sudo libinput debug-events

# List input devices libinput sees
sudo libinput list-devices

# Test touchpad gesture recognition
sudo libinput debug-events --device /dev/input/event4 2>&1 | grep -i gesture

# Check if user is in input group (required for some configurations)
groups $USER | grep -q input && echo "input group OK" || \
  echo "Missing: sudo usermod -aG input $USER"
```

**`pixman`** is a CPU-side pixel manipulation library used as the software rendering fallback. When GPU acceleration is unavailable (VM without GPU passthrough, certain embedded targets), compositors like Weston fall back to pixman for compositing operations. For day-to-day desktop ricing this rarely matters, but it surfaces in headless CI environments.

---

## 1.5 Wayland vs. X11: Practical Differences for Users

The practical compatibility landscape in 2025/2026 has improved dramatically compared to 2021. The major desktop applications have all landed native Wayland support, and XWayland — the compatibility layer that runs X11 applications inside a Wayland session — handles the remaining long tail reliably. However, there are still meaningful differences that affect how you configure your system.

**Application compatibility matrix:**

| Application category | Native Wayland support | Notes |
|---|---|---|
| GTK4 applications | Yes (default) | Explicit `GDK_BACKEND=wayland` not needed |
| GTK3 applications | Yes (Wayland backend) | Set `GDK_BACKEND=wayland` to force |
| Qt6 applications | Yes | Via `QT_QPA_PLATFORM=wayland` |
| Qt5 applications | Yes | `qt5-wayland` plugin required |
| Electron (≥28) | Yes | `--enable-features=UseOzonePlatform --ozone-platform=wayland` |
| Electron (< 28) | XWayland | Blurry on HiDPI |
| Firefox | Yes (default since 121) | `MOZ_ENABLE_WAYLAND=1` legacy env |
| Chromium | Yes | `--ozone-platform=wayland` |
| SDL2 games | Yes | `SDL_VIDEODRIVER=wayland` |
| Steam client | XWayland | Planned native, timeline unclear |
| Wine / Proton | XWayland | WSIInfo/VK_KHR_display path |
| Java Swing/AWT | XWayland | No native Wayland backend |
| LibreOffice | Yes (7.6+) | Uses GTK3/GTK4 Wayland backend |
| OBS Studio | Yes (31+) | `wlr-screencopy` or PipeWire |
| `xterm` / `rxvt` | XWayland only | Pure X11 terminals |
| `foot` / `Alacritty` | Yes | Native Wayland terminals |

**XWayland** is a modified X11 server that runs as a Wayland client. It creates a single Wayland surface and multiplexes all X11 client windows onto it. From the Wayland compositor's perspective, XWayland is just another client. From X11 clients' perspective, there is a fully functional X server. The performance overhead of XWayland is small for regular applications — the main penalty is HiDPI scaling (XWayland has to scale the entire surface at once, leading to blurry output at non-integer scale factors) and the absence of Wayland-specific features like adaptive sync (VRR) for games.

```bash
# Check if XWayland is running
pgrep -a Xwayland

# Force a specific application to use XWayland
WAYLAND_DISPLAY="" GDK_BACKEND=x11 gedit

# Force an application to use native Wayland
GDK_BACKEND=wayland QT_QPA_PLATFORM=wayland my-app

# Environment variables cheat sheet
cat <<'EOF'
# GTK applications
GDK_BACKEND=wayland          # force Wayland (or x11)

# Qt applications
QT_QPA_PLATFORM=wayland      # force Wayland
QT_WAYLAND_DISABLE_WINDOWDECORATION=1  # use compositor-side decorations
XCURSOR_THEME=Adwaita        # cursor theme for Wayland Qt
XCURSOR_SIZE=24

# Electron applications (Electron 20+)
ELECTRON_OZONE_PLATFORM_HINT=wayland

# SDL2
SDL_VIDEODRIVER=wayland

# Clutter / GNOME legacy
CLUTTER_BACKEND=wayland

# Java AWT (no native backend, but can reduce XWayland blurriness)
_JAVA_AWT_WM_NONREPARENTING=1
EOF
```

**Known limitations as of 2025/2026:**

The main remaining gaps in the Wayland ecosystem are:

1. **Global hotkeys**: The `ext-global-shortcut-v1` protocol is in staging; full cross-compositor support is not yet universal. Workarounds using `xdg-desktop-portal` exist but are compositor-specific.

2. **Screen recording from multiple windows**: PipeWire's `xdg-desktop-portal-wlr` (for wlroots compositors) and `xdg-desktop-portal-gnome` handle this but require compositor cooperation. OBS must use the PipeWire source rather than direct screen capture.

3. **Input method editors (IME)**: The `text-input-v3` protocol works well for GTK4 and Qt6 but some legacy IM frameworks (old fcitx versions) require XWayland. Use `fcitx5` with the Wayland plugin.

4. **Colour management**: The `xx-color-management-v4` protocol has landed in staging but compositor support is still rolling out in 2025. ICC profiles for individual outputs require compositor-specific configuration today.

5. **VRR / adaptive sync**: The `wp-fifo-v1` and `ext-vrr-v1` protocols are available; compositor support (sway, Hyprland, KDE Plasma 6) is now mainstream.

```bash
# Check XDG portal availability (important for screen recording, file chooser)
systemctl --user status xdg-desktop-portal.service
systemctl --user status xdg-desktop-portal-wlr.service  # wlroots
systemctl --user status xdg-desktop-portal-hyprland.service  # Hyprland
systemctl --user status xdg-desktop-portal-gnome.service  # GNOME

# Verify PipeWire is running (required for portal screen capture)
pactl info | grep 'Server Name'  # should show PipeWire
pw-cli info all | grep -c node   # count PipeWire nodes

# Diagnose portal issues
G_MESSAGES_DEBUG=all /usr/lib/xdg-desktop-portal 2>&1 | head -30
```

---

## 1.6 The Wayland Object Model in Detail

The Wayland protocol is built on a typed object system that persists across the lifetime of a connection. Every interface (a named set of requests and events) has a version number. Clients must negotiate a maximum version when binding a global. The compositor advertises its maximum supported version; the client binds at `min(client_max, compositor_max)`. This means newer clients can run on older compositors (degraded functionality) and older clients on newer compositors (full stability).

The lifecycle of a surface in Wayland illustrates the object model concretely. A client performs the following sequence to display a window:

```
1. wl_registry.bind("wl_compositor", version) → wl_compositor
2. wl_compositor.create_surface() → wl_surface
3. wl_registry.bind("xdg_wm_base", version) → xdg_wm_base
4. xdg_wm_base.get_xdg_surface(wl_surface) → xdg_surface
5. xdg_surface.get_toplevel() → xdg_toplevel
6. xdg_toplevel.set_title("My App")
7. xdg_toplevel.set_app_id("my.app.id")
8. wl_surface.commit()          ← initial commit, no buffer yet
   [compositor sends xdg_surface.configure event]
9. xdg_surface.ack_configure(serial)
10. wl_registry.bind("wl_shm", version) → wl_shm (or use GBM/EGL)
11. wl_shm.create_pool(fd, size) → wl_shm_pool
12. wl_shm_pool.create_buffer(offset, w, h, stride, format) → wl_buffer
    [client paints into shared memory]
13. wl_surface.attach(wl_buffer, 0, 0)
14. wl_surface.damage_buffer(0, 0, w, h)
15. wl_surface.commit()          ← presents the frame
```

The double-buffer/commit mechanism is key to "every frame is perfect": the compositor applies all pending state (buffer, damage, opaque region, input region, sub-surface positions) atomically at commit time. There is never a partial state visible to the compositor.

```bash
# Trace this sequence live with WAYLAND_DEBUG
WAYLAND_DEBUG=1 foot --app-id=debug.term 2>&1 | grep -E 'xdg_|wl_surface' | head -30

# Inspect the protocol XML to understand message definitions
python3 - <<'EOF'
import xml.etree.ElementTree as ET
tree = ET.parse('/usr/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml')
root = tree.getroot()
for iface in root.findall('interface'):
    print(f"\n=== {iface.get('name')} v{iface.get('version')} ===")
    for req in iface.findall('request'):
        args = ', '.join(a.get('type','') for a in req.findall('arg'))
        print(f"  REQ  {req.get('name')}({args})")
    for evt in iface.findall('event'):
        args = ', '.join(a.get('type','') for a in evt.findall('arg'))
        print(f"  EVT  {evt.get('name')}({args})")
EOF
```

---

## 1.7 Protocol Namespaces and Extension Stability

Understanding the naming conventions for Wayland protocol interfaces prevents confusion when reading documentation or compositor configuration files. The prefix of an interface name indicates its origin and stability guarantee.

| Prefix | Origin | Stability | Example |
|---|---|---|---|
| `wl_` | Core wayland.xml | Stable, frozen | `wl_surface`, `wl_seat` |
| `xdg_` | xdg-shell (freedesktop) | Stable | `xdg_toplevel`, `xdg_popup` |
| `zwp_` | Unstable wayland-protocols | Deprecated path | `zwp_linux_dmabuf_v1` |
| `zwlr_` | wlr-protocols (unstable) | wlroots only | `zwlr_layer_shell_v1` |
| `ext_` | New freedesktop staging | Cross-compositor | `ext_session_lock_v1` |
| `wp_` | wayland-protocols staging | Cross-compositor | `wp_fractional_scale_v1` |
| `xx_` | Experimental | Unstable | `xx_color_management_v4` |
| `kde_` | KDE-specific | KDE compositors | `kde_output_device_v2` |
| `zcr_` | ChromeOS/Exo | Exo compositor | `zcr_remote_surface_v1` |

The `z` prefix (as in `zwp_`, `zwlr_`) is a historical convention meaning "unstable" — it was prefixed so that if an interface is later stabilised and renamed, the old and new versions can coexist without name collision. New unstable protocols use `ext_` or compositor-specific prefixes without the `z`.

```bash
# Enumerate all protocols on your system with their prefixes
find /usr/share/wayland-protocols /usr/share/wlr-protocols \
  -name '*.xml' 2>/dev/null | sort | while read f; do
    version=$(grep -m1 'interface name' "$f" | grep -oP 'version="\K[^"]+')
    iface=$(grep -m1 'interface name' "$f" | grep -oP 'name="\K[^"]+')
    echo "$iface (v$version) — $f"
done

# Check which protocols your compositor actually implements
# For Hyprland:
hyprctl protocols 2>/dev/null

# For sway / wlroots:
wayland-info | grep interface | awk '{print $3}' | tr -d "'" | sort
```

---

## 1.8 Ricing-Relevant Protocols at a Glance

Not all Wayland protocols are relevant to desktop ricing. The following are the ones you will encounter most often in subsequent chapters of this book.

**`zwlr_layer_shell_v1`** — The most important protocol for ricing. It allows clients to create surfaces that are pinned to screen edges, rendered above or below regular windows, and excluded from the tiling layout. Bars (waybar, eww, ironbar), wallpaper daemons (swww, hyprpaper), notification daemons (dunst, mako), and lock screens (swaylock) all use this protocol. See **Ch 3** (§3.4) for layer-shell surface configuration.

**`xdg_output_unstable_v1`** / **`wl_output`** — Describes monitor geometry including logical vs. physical coordinates, scale factor, and refresh rate. Essential for multi-monitor configurations. See **Ch 5** for output management.

**`zwlr_screencopy_v1`** — Allows clients to capture the screen. Used by screenshot tools (`grim`), screen recorders, and remote desktop implementations. See **Ch 31** (Screenshots and Recording: grim, slurp, wf-recorder, OBS) for screen capture tooling.

**`wp_fractional_scale_v1`** / **`wp_viewport`** — Enables non-integer HiDPI scaling (e.g., 1.5×, 1.75×) without blurriness. Requires compositor support and toolkit support (GTK4 ≥ 4.10, Qt6 ≥ 6.4). See **Ch 41** for HiDPI and fractional scaling configuration.

**`ext_session_lock_v1`** — Standardised screen lock protocol, replacing the wlroots-specific `zwlr_input_inhibitor_v1`. Swaylock 1.7+, hyprlock use this. See **Ch 53** for session startup and lock screen configuration.

**`xdg_decoration_unstable_v1`** — Negotiates who draws window title bars: server-side (compositor draws them, unified look) or client-side (application draws them, matches app theme). See **Ch 12** for decoration configuration.

**`wp_cursor_shape_v1`** — Allows clients to request named cursor shapes without loading cursor images themselves, reducing cursor theme inconsistency. Supported in GTK4 4.14+ and Qt 6.6+.

---

## Key References

- **The Wayland Book** (official, free): https://wayland-book.com — authoritative reference for protocol internals
- **freedesktop.org wayland-protocols**: https://gitlab.freedesktop.org/wayland/wayland-protocols — the canonical protocol XML files
- **wlr-protocols**: https://gitlab.freedesktop.org/wlroots/wlr-protocols — wlroots extension protocols
- **Kristian Høgsberg's original Wayland announcement** (2008): https://lists.freedesktop.org/archives/wayland-devel/2008-October/000000.html
- **Drew DeVault's "Status of Wayland in 2019"**: https://drewdevault.com/2019/01/17/Status-of-Wayland.html
- **wayland.xml** on your system: `/usr/share/wayland/wayland.xml`
- **DRM/KMS documentation**: https://dri.freedesktop.org/docs/drm/
- **libinput documentation**: https://wayland.freedesktop.org/libinput/doc/latest/

---

## Troubleshooting

### Application starts under XWayland instead of native Wayland

Check `$WAYLAND_DISPLAY` is set in the process environment. Applications launched from XWayland terminals inherit an X-centric environment.

```bash
# Check environment of a running process
cat /proc/$(pgrep -n firefox)/environ | tr '\0' '\n' | grep -E 'WAYLAND|DISPLAY'

# If WAYLAND_DISPLAY is missing, re-source session environment
systemctl --user import-environment WAYLAND_DISPLAY XDG_RUNTIME_DIR DISPLAY
```

### `WAYLAND_DISPLAY` not set after login

This is a session startup ordering issue. See **Ch 53** for correct session environment propagation. Quick check:

```bash
echo $WAYLAND_DISPLAY         # should be "wayland-0" or similar
ls -la $XDG_RUNTIME_DIR/      # socket file should exist here
loginctl show-session $(loginctl | awk '/jreuben/{print $1}') | grep -E 'Type|Active'
```

### Compositor crashes with `EGL_BAD_ALLOC` or `DRM_IOCTL failed`

GPU memory exhaustion or DRM lease conflict. Check:

```bash
# Check for zombie DRM masters
sudo fuser /dev/dri/card0

# Check GPU memory usage (NVIDIA)
nvidia-smi --query-gpu=memory.used,memory.total --format=csv

# Check GPU memory usage (AMD/Intel via Mesa)
sudo cat /sys/kernel/debug/dri/0/clients 2>/dev/null || \
  sudo intel_gpu_top -l 1 2>/dev/null | head -5
```

### Protocol version mismatch errors

When a client requests a protocol version higher than the compositor supports, you see errors like `wl_registry: invalid version for interface 'zwlr_layer_shell_v1'`.

```bash
# Check what version the compositor advertises
wayland-info | grep zwlr_layer_shell

# Check what version a package was compiled against
pkg-config --modversion wlr-protocols 2>/dev/null
objdump -p /usr/lib/libwlroots.so* | grep SONAME
```

### `WAYLAND_DEBUG` output is overwhelming

Filter by object type:

```bash
# Only show surface and toplevel messages
WAYLAND_DEBUG=1 my-app 2>&1 | grep -E 'wl_surface|xdg_toplevel'

# Count messages by type (find the noisy interfaces)
WAYLAND_DEBUG=1 my-app 2>&1 | grep -oP '\] \K\w+@\d+\.\w+' | \
  cut -d. -f1 | sort | uniq -c | sort -rn | head -10
```

### Application renders blurry on HiDPI display

This is almost always XWayland scaling. Confirm with:

```bash
# Check if the application is running under XWayland
xlsclients 2>/dev/null | grep my-app    # appears → XWayland
wayland-info | grep wl_surface          # won't show app surfaces directly

# Force GTK application to Wayland backend
GDK_BACKEND=wayland my-gtk-app

# For Electron apps (add to /usr/share/applications/*.desktop Exec line)
# --enable-features=UseOzonePlatform --ozone-platform=wayland
```

---

*Next chapter: **Ch 2 — Compositor Landscape: sway, Hyprland, niri, and the wlroots family** — choosing and installing your compositor.*

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
