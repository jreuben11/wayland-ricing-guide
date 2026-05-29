# Chapter 13 — The Full Zoo: dwl, Jay, cosmic-comp, KWin, GNOME Mutter, gamescope

## Overview

Beyond the "big four" ricing compositors (Sway, Hyprland, River, Niri — covered in Chapters 9–12), the
Wayland compositor ecosystem in 2025 is remarkably diverse. Some compositors are stripped-down tools
targeting hackers who want total control over every line of code. Others are the heavyweight, feature-complete
backends for major desktop environments. A few are highly specialized: one wraps games in a micro-compositor
for latency reduction, another boots a single application in kiosk mode for embedded hardware.

Understanding the full landscape matters for two reasons. First, the "right compositor" is workload-dependent —
a tiling-enthusiast who games heavily might combine two compositors (e.g., gamescope nested inside Hyprland).
Second, knowing *why* each compositor exists, what protocols it supports, and where its codebase lives helps
you predict how it will evolve and whether its community will sustain it.

This chapter surveys every notable compositor in the Wayland zoo as of mid-2025. For each entry you will
find: architectural description, feature table, installation instructions, core configuration patterns,
and links to related chapters. See Ch 3 for Wayland protocol fundamentals, Ch 6 for wlroots internals,
and Ch 53 for session startup and display-manager integration.

---

## 13.1 dwl — dwm for Wayland

dwl is a minimal wlroots-based compositor intentionally kept below 2,000 lines of C, mirroring the
philosophy of its X11 ancestor dwm. The design is deliberately hostile to feature creep: if you want
something, you apply a patch from the community patch repository or write the C yourself. The binary
has no configuration file — everything is done in `config.h` before compilation, which is then recompiled.
This is not a quirk; it is the intended workflow. dwl's codebase is small enough that an experienced C
programmer can hold it entirely in their head.

Window management in dwl uses the tag model inherited from dwm rather than workspaces. Each window is
assigned one or more tags (think bitmasks, not workspaces), and the view mask selects which tags are
visible simultaneously. This allows fluid multi-tag views that have no direct equivalent in most tiling
WMs. The default keybinds, layout algorithms (tile, monocle, floating), and the status bar protocol are
all defined in `config.h`.

Patching is the primary customization path. The community maintains patches for: rounded corners,
per-tag layouts, swallow (terminal replaced by launched child), scratchpads, focus follows mouse,
IPC via a Unix socket, and more. Patches are unified diffs against specific tagged releases; applying
multiple patches to the same source tree requires manual conflict resolution, exactly as with dwm.

Who should use dwl: C programmers comfortable with the source-as-config model who want the smallest
possible compositor surface area. It is not suitable for users who expect a GUI settings panel or
who are unwilling to recompile on every configuration change.

### Installation

```bash
# Dependencies (Arch Linux)
sudo pacman -S wlroots wayland wayland-protocols libxkbcommon libinput \
               pixman xcb-util-wm xcb-util-renderutil

# Clone and build
git clone https://codeberg.org/dwl/dwl.git
cd dwl
cp config.def.h config.h
# Edit config.h to set your terminal, mod key, etc.
$EDITOR config.h
make
sudo make install
```

```bash
# Applying a patch (example: rounded corners)
cd dwl
curl -LO https://codeberg.org/dwl/dwl-patches/raw/branch/main/patches/rounded-corners/rounded-corners.patch
patch -p1 < rounded-corners.patch
# Resolve conflicts if any, then:
make
```

### Minimal config.h excerpt

```c
/* config.h — dwl user configuration */
static const char *termcmd[]  = { "foot", NULL };
static const char *menucmd[]  = { "fuzzel", NULL };

#define MODKEY WLR_MODIFIER_LOGO  /* Super key */

static const Key keys[] = {
    /* modifier                  key          function        argument */
    { MODKEY,                    XKB_KEY_Return, spawn,       {.v = termcmd} },
    { MODKEY,                    XKB_KEY_p,      spawn,       {.v = menucmd} },
    { MODKEY|WLR_MODIFIER_SHIFT, XKB_KEY_q,      quit,        {0} },
    { MODKEY,                    XKB_KEY_j,      focusstack,  {.i = +1} },
    { MODKEY,                    XKB_KEY_k,      focusstack,  {.i = -1} },
    { MODKEY,                    XKB_KEY_h,      setmfact,    {.f = -0.05} },
    { MODKEY,                    XKB_KEY_l,      setmfact,    {.f = +0.05} },
    { MODKEY,                    XKB_KEY_t,      setlayout,   {.v = &layouts[0]} },
    { MODKEY,                    XKB_KEY_m,      setlayout,   {.v = &layouts[1]} },
};
```

### Key properties

| Property            | dwl                          |
|---------------------|------------------------------|
| Backend             | wlroots                      |
| Language            | C (<2000 LOC)                |
| Config method       | config.h + recompile         |
| IPC                 | Optional patch (dwl-ipc)     |
| XWayland            | Optional (compile flag)      |
| Status bar protocol | dwl-ipc or wlr-foreign-toplevel |
| Tiling model        | Tag-based (dwm heritage)     |

See Ch 6 for wlroots internals, Ch 19 for compatible status bars, and Ch 37 for writing dwl patches.

---

## 13.2 Jay — Wayland in Rust

Jay is a Wayland compositor written entirely in Rust on top of the Smithay compositor framework. It
targets correctness-first design: protocol compliance is prioritized over performance shortcuts, and the
Rust type system is used aggressively to prevent whole classes of bugs that plague C compositors (use-after-free
in wlroots surfaces, for example). The project targets experienced Wayland users who want a modern
language foundation without surrendering customizability to a desktop environment.

Jay uses a TOML-based configuration file and supports a scripting layer through an embedded Lua runtime.
This gives it a more accessible configuration path than dwl while remaining far more hackable than KWin
or GNOME Mutter. The Smithay dependency means Jay benefits from upstream protocol implementations
(xdg-decoration, wp-drm-lease, ext-session-lock) maintained by the broader Smithay community rather
than duplicated in Jay's own tree.

Feature completeness as of mid-2025: Jay supports multi-monitor with independent refresh rates, VRR,
HDR output management, xdg-shell, layer-shell, screencopy (wlr-screencopy-v1 and ext-image-copy-capture),
input-method (virtual keyboard), and ext-session-lock. XWayland support landed in 0.2 and is considered
stable. The compositor lacks a built-in panel, relying instead on external bars via layer-shell.

### Installation

```bash
# Arch Linux — AUR
paru -S jay-compositor

# From source (requires Rust 1.78+)
git clone https://github.com/mahkoh/jay.git
cd jay
cargo build --release
sudo install -Dm755 target/release/jay /usr/local/bin/jay
```

```bash
# Generate default config
jay generate-config
# Config lands at ~/.config/jay/config.toml
```

### Minimal jay config.toml

```toml
# ~/.config/jay/config.toml

[keyboard]
layout = "us"
variant = ""
repeat-rate = 25
repeat-delay = 200

[cursor]
theme = "Bibata-Modern-Classic"
size = 24

[[keymap]]
mod = ["super"]
key = "Return"
action = { type = "exec", command = ["foot"] }

[[keymap]]
mod = ["super"]
key = "d"
action = { type = "exec", command = ["fuzzel"] }

[[keymap]]
mod = ["super", "shift"]
key = "q"
action = { type = "close-window" }

[output.eDP-1]
scale = 2.0
mode = "2560x1600@60"
```

### Key properties

| Property            | Jay                          |
|---------------------|------------------------------|
| Backend             | Smithay                      |
| Language            | Rust                         |
| Config method       | TOML + Lua scripting         |
| IPC                 | jay-msg CLI                  |
| XWayland            | Yes (0.2+)                   |
| HDR                 | Yes                          |
| VRR                 | Yes                          |

See Ch 7 for Smithay architecture, Ch 21 for Lua scripting in compositors.

---

## 13.3 cosmic-comp — The COSMIC Desktop Compositor

cosmic-comp is the compositor powering System76's COSMIC desktop environment, built in Rust on Smithay.
Unlike Jay (which is compositor-first), cosmic-comp is designed as an integral component of a full DE,
with deep integration into cosmic-settings, cosmic-panel, cosmic-applets, and the broader COSMIC
application ecosystem. It was publicly released as a stable 1.0 in early 2025.

The layout system is cosmic-comp's defining characteristic. It implements a hybrid tiling/stacking model
where every workspace begins with a "Tiling" or "Floating" toggle. In tiling mode, windows auto-tile
into a binary tree similar to i3/Sway, but COSMIC exposes tree manipulation through a graphical overlay
that new users find approachable. Stacking mode is conventional floating. Users switch between modes
per-workspace on the fly. Gaps, borders, and corner radii are all adjustable from cosmic-settings without
touching config files.

cosmic-comp implements several protocols that most wlroots compositors lack: cosmic-toplevel-info (an
internal evolution of wlr-foreign-toplevel used by cosmic-panel), cosmic-workspace-unstable-v1, and the
upstream ext-workspace-v1. It is also one of the earliest compositors to ship a usable ICC/color-profile
pipeline through the wp-color-management protocol, making it attractive for color-critical workflows.

### Installation

```bash
# Pop!_OS (System76 official distro) — pre-installed

# Arch Linux
sudo pacman -S cosmic-comp cosmic-session

# NixOS — add to configuration.nix
# services.desktopManager.cosmic.enable = true;

# From source (entire COSMIC stack — takes ~20 min)
git clone https://github.com/pop-os/cosmic-epoch.git
cd cosmic-epoch
just build-all
sudo just install
```

```bash
# Launch a standalone cosmic-comp session
cosmic-session
# Or select "COSMIC" in GDM/SDDM
```

### Key properties

| Property            | cosmic-comp                  |
|---------------------|------------------------------|
| Backend             | Smithay                      |
| Language            | Rust                         |
| Config method       | cosmic-settings GUI          |
| IPC                 | COSMIC D-Bus APIs            |
| XWayland            | Yes                          |
| HDR / color mgmt    | Yes (wp-color-management)    |
| Tiling model        | Hybrid tile/float per workspace |

See Ch 7 for Smithay, Ch 44 for COSMIC applets and panel customization.

---

## 13.4 KWin on Wayland

KWin is KDE Plasma's compositor and window manager, and it is widely regarded as the most feature-complete
Wayland compositor available on Linux. Unlike wlroots-based compositors that implement Wayland protocols
directly, KWin builds on Qt's KWayland library and the KDE Frameworks stack, which provides abstractions
for monitor management (KScreen), input handling (libinput via KWin's own wrapper), and the KDE-specific
protocol set. The trade-off is a substantially larger codebase and dependency tree.

On the ricing side, KWin exposes three extension points: KWin scripts (JavaScript running in Qt's QJS engine
with access to the KWin scripting API), KWin effects (C++/QML plugins compiled against KWin headers), and
KDE's global theme system (plasma-styles + window decorations + color schemes). KWin scripts can manipulate
window placement, assign windows to virtual desktops, override focus policies, and hook into KWin's D-Bus
interface. Effects provide GPU-accelerated visual enhancements (blur, dim-inactive, morphing-popups).

KWin's protocol support is consistently ahead of the wlroots ecosystem in areas tied to KDE priorities:
HDR and wide-gamut color management, presentation-time, KDE's own color-scheme-v1 protocol, explicit sync
(DMA-BUF with fences, critical for NVIDIA under Wayland), and the KDE-specific appmenu protocol that
exposes GTK/Qt application menu bars in the plasma-panel. As of Plasma 6.2, KWin's Wayland session is
considered fully stable and is the default on a fresh KDE install.

KWin vs. wlroots: the choice is essentially DE integration vs. minimalism. KWin gives you Spectacle, KDE
Connect, Discover, Dolphin, and a fully coherent theming pipeline out of the box. wlroots compositors give
you a smaller attack surface, faster startup, and the freedom to compose your own stack. For NVIDIA users
in 2025, KWin's explicit sync support often means better stability than Hyprland or Sway.

### KWin script — tile new windows to the right half

```javascript
// ~/.local/share/kwin/scripts/tile-right/contents/code/main.js
var client = workspace.activeClient;
workspace.clientAdded.connect(function(client) {
    if (client.normalWindow) {
        var screen = workspace.clientArea(KWin.MaximizeArea, client);
        client.geometry = Qt.rect(
            screen.x + screen.width / 2,
            screen.y,
            screen.width / 2,
            screen.height
        );
    }
});
```

```bash
# Install and enable a KWin script via CLI
mkdir -p ~/.local/share/kwin/scripts/tile-right/contents/code
# (place main.js from above)
# Create metadata.json
cat > ~/.local/share/kwin/scripts/tile-right/metadata.json <<'EOF'
{
  "KPlugin": {
    "Name": "Tile Right",
    "Description": "Auto-tiles new windows to the right half",
    "Id": "tile-right",
    "Version": "1.0"
  }
}
EOF
qdbus org.kde.KWin /Scripting org.kde.kwin.Scripting.loadScript \
    "$HOME/.local/share/kwin/scripts/tile-right/contents/code/main.js" \
    "tile-right"
```

```bash
# KWin compositor settings via kwriteconfig6
kwriteconfig6 --file kwinrc --group Compositing --key LatencyPolicy Low
kwriteconfig6 --file kwinrc --group Compositing --key MaxFPS 240
kwriteconfig6 --file kwinrc --group Compositing --key VSync true
qdbus org.kde.KWin /Compositor reconfigure
```

### Key properties

| Property            | KWin (Wayland)               |
|---------------------|------------------------------|
| Backend             | KWayland / Qt                |
| Language            | C++ / QML                    |
| Config method       | System Settings GUI + kwinrc |
| Scripting           | JavaScript (QJS engine)      |
| XWayland            | Yes                          |
| HDR / color mgmt    | Yes (Plasma 6.1+)            |
| Explicit sync       | Yes (NVIDIA-friendly)        |
| VRR                 | Yes                          |

See Ch 15 for KDE Plasma ricing depth, Ch 47 for KWin effects authoring.

---

## 13.5 GNOME Mutter/Shell

Mutter is GNOME's compositor and window manager, serving as the backend to GNOME Shell. Unlike KWin (which
can run standalone), Mutter is not designed for independent use — it only makes sense as the renderer
beneath GNOME Shell's JavaScript process. GNOME Shell runs on GJS (GNOME's SpiderMonkey-based JS runtime)
and communicates with Mutter through its C-based libmutter API, making GNOME Shell extensions the primary
ricing surface.

GNOME's approach to Wayland is architecturally conservative. Mutter does not expose wlroots protocols
(no wlr-layer-shell, no wlr-screencopy), instead implementing only the upstream Wayland protocols and
GNOME-specific ones (gnome-shell-screenshot, remote-desktop via PipeWire). This breaks most wlroots-based
ricing tools. Waybar's GNOME support, for example, requires the gnome-shell-extension-appindicator
extension bridge. Tools like wl-paste, wtype, and wlr-randr do not work under GNOME without workarounds.

GNOME Shell extensions (installed via extensions.gnome.org or gnome-extensions CLI) are the canonical GNOME
ricing path. Prominent extensions for ricing: Just Perfection (remove UI chrome), Blur my Shell (blur
background of panel/overview), Dash to Panel (taskbar-style panel), Pop Shell (tiling window management
developed by System76 before COSMIC). Extension compatibility is tied to the GNOME Shell major version,
making upgrades a perennial pain point.

GNOME 47+ significantly improved Wayland-specific features: triple-buffering merged upstream (faster redraws
on variable-latency content), HDR experimental support via libei, explicit sync via the linux-drm-syncobj
protocol. These improvements make GNOME a viable option for gaming and creative work that previously required
KDE or a wlroots compositor.

### Key GNOME extension management commands

```bash
# List installed extensions
gnome-extensions list

# Enable/disable
gnome-extensions enable just-perfection-desktop@just-perfection
gnome-extensions disable just-perfection-desktop@just-perfection

# Install from CLI (requires gnome-shell-extension-manager or curl)
# Via the extensions.gnome.org API:
EXT_UUID="blur-my-shell@aunetx"
curl -s "https://extensions.gnome.org/extension-query/?search=${EXT_UUID}" | \
    python3 -c "import sys,json; d=json.load(sys.stdin); print(d['extensions'][0]['pk'])"
```

```bash
# gsettings — tune GNOME compositor behavior
# Disable animations (faster feel)
gsettings set org.gnome.desktop.interface enable-animations false

# Enable fractional scaling (Wayland)
gsettings set org.gnome.mutter experimental-features "['scale-monitor-framebuffer']"

# Enable variable refresh rate
gsettings set org.gnome.mutter experimental-features \
    "['variable-refresh-rate', 'scale-monitor-framebuffer']"

# Force Wayland backend for all apps (disables X11 fallback)
gsettings set org.gnome.desktop.session session-type 'wayland'
```

```bash
# Pop Shell (tiling for GNOME) quick setup
sudo pacman -S gnome-shell-extension-pop-shell   # Arch
# Or from source:
git clone https://github.com/pop-os/shell.git
cd shell
make local-install
```

### Key properties

| Property            | GNOME Mutter/Shell           |
|---------------------|------------------------------|
| Backend             | libmutter (custom)           |
| Language            | C (Mutter) + JS (Shell)      |
| Config method       | gsettings / extensions       |
| Scripting           | GJS (SpiderMonkey)           |
| XWayland            | Yes                          |
| wlr-layer-shell     | No                           |
| HDR                 | Experimental (GNOME 47+)     |
| Tiling              | Via Pop Shell extension      |

See Ch 16 for GNOME Shell extension development, Ch 48 for GNOME theming in depth.

---

## 13.6 gamescope — The Gaming Compositor

gamescope is a micro-compositor developed by Valve for SteamOS. Its job is to wrap a single game (or Steam
itself) in a Wayland compositor that has full control over the display pipeline, enabling features
impossible to reliably achieve when running games as normal windows inside a general-purpose compositor:
sub-millisecond VRR control, consistent HDR tone-mapping via color LUTs, forced resolution scaling with
FSR or NIS upscaling, and guaranteed low-latency scanout by bypassing the desktop compositor entirely.

The architecture is deliberately nested-compositor-first: on the desktop, gamescope runs as a nested
Wayland compositor (inside your existing session), displaying itself in a window. On SteamOS's game mode,
it runs as the sole compositor in a dedicated DRM/KMS session. This dual-mode design means you can test
gamescope behavior on your ricing desktop and then deploy the identical configuration to a living-room
SteamOS machine.

gamescope's feature set as of version 3.15 (mid-2025): HDR10 output with per-game tone-mapping overrides,
AMD FidelityFX Super Resolution (FSR 1/2/3) and NVIDIA Image Scaling (NIS) as post-process upscalers,
frame limiter with precise timing (not vsync-tied), Linux-specific low-latency submit path via
adaptive sync, Reshade/vkBasalt integration for post-processing, Steam overlay compatibility, and MangHUD
passthrough (gamescope exposes MANGOHUD_CONFIG to the child process).

The ricing angle is subtle but real: gamescope can act as a window inside your tiling WM, letting you
manage game sessions like any other container. You can assign gamescope windows to specific workspaces,
apply corner-radius styling, and pipe gamescope's output into OBS via wlr-screencopy.

### Basic usage patterns

```bash
# Launch a single game in a gamescope window (nested, 1080p upscaled to native)
gamescope -W 2560 -H 1440 -w 1920 -h 1080 --fsr-upscaling -- %command%

# Steam launch option (paste into Properties > Launch Options)
gamescope -W 2560 -H 1440 -w 1920 -h 1080 -f --adaptive-sync -- %command%

# HDR mode (requires HDR-capable display and kernel 6.7+ amdgpu)
gamescope -W 3840 -H 2160 --hdr-enabled --hdr-itm-enable -- %command%

# Use FSR2 upscaling (AMD)
gamescope -W 2560 -H 1440 -w 1280 -h 720 --fsr-upscaling --fsr-sharpness 3 -- %command%

# Frame-limited to 60fps (useful for battery on deck)
gamescope -W 1280 -H 800 -r 60 -- %command%
```

```bash
# gamescope wrapping all of Steam (desktop replacement mode)
gamescope -e --steam -- steam -gamepadui

# With MangHUD overlay enabled inside gamescope
MANGOHUD=1 gamescope -W 1920 -H 1080 -f -- %command%
```

```bash
# gamescope as a standalone session (SteamOS-style)
# /etc/systemd/system/gamescope-session.service
[Unit]
Description=Gamescope Session
After=systemd-user-sessions.service

[Service]
User=deck
PAMName=login
TTYPath=/dev/tty2
ExecStart=/usr/bin/gamescope -e --steam -- /usr/bin/steam -gamepadui
Restart=on-failure
StandardInput=tty
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical.target
```

### Key properties

| Property            | gamescope                    |
|---------------------|------------------------------|
| Backend             | wlroots (minimal)            |
| Language            | C++                          |
| Purpose             | Gaming micro-compositor      |
| HDR                 | Yes (amdgpu kernel 6.7+)     |
| VRR / Adaptive sync | Yes                          |
| Upscaling           | FSR 1/2/3, NIS               |
| Nesting             | Yes (Wayland nested mode)    |
| MangHUD integration | Yes                          |

See Ch 38 for GPU optimization, Ch 52 for gaming session management on SteamOS.

---

## 13.7 cage — Kiosk Compositor

cage is a single-window Wayland compositor designed for kiosk and embedded deployments. When launched,
it starts one application, displays it full-screen, and terminates when that application exits. There is
no window management, no layer-shell support, no virtual desktops — just one app and the display. This
extreme minimalism is a feature: cage's attack surface is tiny, its startup time is under 50ms, and it
provides a reliable, predictable environment for unattended displays.

Typical use cases: point-of-sale terminals, museum kiosk displays, digital signage, Raspberry Pi-based
info boards, ATM interfaces, vehicle infotainment systems, and embedded control panels. cage runs on any
wlroots-compatible GPU and handles touch input correctly, making it suitable for touchscreen kiosks.

cage also serves as a convenient tool for running single X11/Wayland applications from scripts without
needing a full compositor session — useful in CI pipelines that need to snapshot a GUI app.

### Installation and usage

```bash
# Arch Linux
sudo pacman -S cage

# Ubuntu/Debian
sudo apt install cage

# Run a kiosk session with Chromium in kiosk mode
cage -- chromium --kiosk https://dashboard.example.com

# Run a Python/Tkinter app as a kiosk
cage -- python3 /opt/kiosk/app.py

# Auto-start cage on tty1 via getty override (systemd)
sudo systemctl edit getty@tty1.service
```

```ini
# /etc/systemd/system/getty@tty1.service.d/override.conf
[Service]
ExecStart=
ExecStart=-/usr/bin/cage -- /opt/kiosk/browser.sh
StandardInput=tty
User=kiosk
```

```bash
# cage with touchscreen calibration
LIBINPUT_CALIBRATION_MATRIX="1 0 0 0 1 0" cage -- your-app
```

| Property            | cage                         |
|---------------------|------------------------------|
| Backend             | wlroots                      |
| Window management   | None — single full-screen app|
| XWayland            | Optional                     |
| Use case            | Kiosk / embedded             |

---

## 13.8 weston — The Reference Compositor

weston is freedesktop.org's reference Wayland compositor, maintained primarily by Collabora engineers. Its
purpose is not daily use but protocol development and testing: when a new Wayland protocol is being designed,
weston is usually the first implementation, and compositors like KWin and Mutter look to weston's reference
implementation when integrating new extensions. weston's codebase is the closest thing the Wayland ecosystem
has to canonical documentation-in-code.

weston ships three shells: the default desktop-shell (a simple panel + wallpaper), kiosk-shell (similar to
cage — one app, full screen), and fullscreen-shell (used by Wayland-native games and embedded systems to
take exclusive control of a screen). None of these are competitive with KWin or Sway for daily use. The
desktop-shell in particular is visually minimal and lacks virtual desktops, tiling, or application-level
theming.

For ricers, weston is useful in exactly two contexts: protocol debugging (if your application misbehaves
on Hyprland but you need to isolate whether the bug is compositor-specific, run it under weston first)
and protocol development (if you are writing a Wayland client that uses a new protocol, test compliance
against weston's implementation). weston's --log flag produces extremely detailed protocol-level tracing.

### Installation and diagnostic use

```bash
# Arch Linux
sudo pacman -S weston

# Run weston nested (inside your existing compositor)
weston --backend=wayland-backend.so

# Run weston on bare DRM/KMS (VT switch required)
weston --backend=drm-backend.so --seat=seat0

# Protocol debug logging
weston --log=/tmp/weston.log WAYLAND_DEBUG=1 weston

# Test a specific application under weston
weston &
WAYLAND_DISPLAY=wayland-1 your-application
```

```ini
# ~/.config/weston.ini — minimal working config
[core]
idle-time=300
use-pixman=false

[output]
name=HDMI-A-1
mode=1920x1080@60
transform=normal

[keyboard]
keymap_layout=us
keymap_variant=intl

[shell]
background-image=/usr/share/backgrounds/gnome/adwaita-l.jpg
background-type=scale
```

| Property            | weston                       |
|---------------------|------------------------------|
| Purpose             | Protocol reference / testing |
| Backend             | DRM, wayland, X11, RDP       |
| Shells              | desktop, kiosk, fullscreen   |
| Daily driver        | No                           |

See Ch 3 for Wayland protocol anatomy, Ch 34 for compositor debugging techniques.

---

## 13.9 Emerging Compositors (2025/2026)

The Wayland compositor space is not static. Several new compositors reached usability thresholds in 2025
and deserve tracking even if they are not yet production-ready for most users.

**waywall** is a container-based compositor that wraps other Wayland compositors in an isolated namespace,
enabling per-application compositor environments. The primary use case is running applications that require
different compositor behavior (e.g., a legacy app that needs XWayland hacks) without contaminating the
entire session. waywall is written in Rust and uses Linux namespaces + wlroots for its sandboxing layer.

**Smithay-based projects** continue to proliferate. The Smithay framework itself graduated to a stable 0.5
API in early 2025, reducing the friction of building new compositors. Notable Smithay projects besides
Jay and cosmic-comp: **pinnacle** (a Lua-scripted compositor with an Awesome WM-inspired API, targeting
power users who prefer dynamic configuration over static config files), and **niri** (covered in depth in
Ch 12, but built on Smithay). The Smithay ecosystem is becoming to Wayland what wlroots was in 2020.

**greetd + ReGreet / tuigreet** are not compositors themselves but compositor-adjacent: they are session
managers that launch compositors for login, replacing display managers like GDM/SDDM with minimal
footprint solutions. tuigreet provides a TUI login prompt; ReGreet provides a Wayland GTK4 greeter that
runs under a minimal wlroots session. Both are common in riced setups to avoid pulling in a full DE just
for the login screen.

### Compositor comparison table (2025 snapshot)

| Compositor   | Backend   | Language | Tiling       | HDR  | VRR  | Config       | Target use case             |
|--------------|-----------|----------|--------------|------|------|--------------|------------------------------|
| dwl          | wlroots   | C        | Tag-based    | No   | Yes  | config.h     | C hackers, minimal setup     |
| Jay          | Smithay   | Rust     | Manual       | Yes  | Yes  | TOML+Lua     | Correctness-focused ricers   |
| cosmic-comp  | Smithay   | Rust     | Hybrid       | Yes  | Yes  | GUI          | COSMIC DE users              |
| KWin         | KWayland  | C++/QML  | Via KWin scripts | Yes | Yes | kwinrc/GUI  | KDE Plasma users             |
| Mutter       | libmutter | C+JS     | Via Pop Shell| Exp  | Yes  | gsettings    | GNOME users                  |
| gamescope    | wlroots   | C++      | N/A          | Yes  | Yes  | CLI flags    | Gaming sessions              |
| cage         | wlroots   | C        | None         | No   | No   | None         | Kiosk / embedded             |
| weston       | Various   | C        | None         | No   | Yes  | weston.ini   | Protocol dev / testing       |
| Hyprland     | Aquamarine | C++      | Dynamic      | Yes  | Yes  | hyprland.conf| Ricing power users           |
| Sway         | wlroots   | C        | i3-style     | No   | Yes  | sway config  | i3 migrants                  |
| niri         | Smithay   | Rust     | Scrollable   | Yes  | Yes  | KDL          | Scrollable-tiling aficionados|

### Pinnacle quick start

```bash
# Pinnacle — Lua-scripted Smithay compositor
# AUR
paru -S pinnacle-comp-git

# Example Lua config (~/.config/pinnacle/init.lua)
local pinnacle = require("pinnacle")
local input    = require("pinnacle.input")
local window   = require("pinnacle.window")
local output   = require("pinnacle.output")

pinnacle.setup(function()
    input.keybind({"super"}, "Return", function()
        pinnacle.process.spawn("foot")
    end)
    input.keybind({"super", "shift"}, "q", function()
        window.get_focused():close()
    end)
    output.setup({
        ["eDP-1"] = { scale = 2.0 },
    })
end)
```

```bash
# greetd + tuigreet setup
sudo pacman -S greetd greetd-tuigreet

# /etc/greetd/config.toml
[terminal]
vt = 1

[default_session]
command = "tuigreet --time --remember --cmd Hyprland"
user = "greeter"

sudo systemctl enable greetd
sudo systemctl start greetd
```

See Ch 53 for full session startup and display-manager selection, Ch 7 for Smithay deep-dive.

---

## Troubleshooting

### Compositor fails to start — no outputs detected

```bash
# Check that DRM/KMS node is accessible
ls -la /dev/dri/
# Ensure your user is in the video group
groups $USER | grep video
sudo usermod -aG video $USER
# Log out and back in, then retry
```

### XWayland not working (dwl, Jay, cage)

```bash
# Check Xwayland is installed
which Xwayland
sudo pacman -S xorg-xwayland   # Arch

# For dwl: rebuild with XWayland enabled
# In config.mk, ensure:
# XWAYLAND = -DXWAYLAND
# Then recompile: make clean && make
```

### gamescope black screen / no HDR

```bash
# Verify kernel DRM HDR support (AMD requires 6.7+)
uname -r
dmesg | grep -i hdr

# Test without HDR first
gamescope -W 1920 -H 1080 -f -- glxgears

# Enable AMD HDR kernel parameter
# Add to /etc/kernel/cmdline or GRUB_CMDLINE_LINUX:
# amdgpu.freesync_video=1
```

### KWin Wayland crashes on NVIDIA

```bash
# Enable explicit sync (Plasma 6.1+, kernel 6.8+, driver 555+)
kwriteconfig6 --file kwinrc --group Compositing --key ExplicitSync true
# Restart KWin
kwin_wayland --replace &

# Check driver version
nvidia-smi --query-gpu=driver_version --format=csv,noheader
# Need 555.x+ for Wayland explicit sync
```

### GNOME extensions breaking after upgrade

```bash
# Check extension compatibility
gnome-extensions list --enabled
# Each extension must declare supported GNOME shell versions in metadata.json
# Temporarily disable all extensions to isolate crash
gnome-extensions disable --all   # (not available in all versions)
# Or via dconf:
gsettings set org.gnome.shell disable-user-extensions true
```

### Weston nested mode compositor conflict

```bash
# If WAYLAND_DISPLAY is not exported correctly when nesting
export WAYLAND_DISPLAY=wayland-0   # your host compositor's socket
weston --backend=wayland-backend.so --socket=wayland-1
# Then in a new terminal:
export WAYLAND_DISPLAY=wayland-1
your-test-app
```

### cage: application exits immediately

```bash
# cage exits when its child exits — wrap in a script if needed
cat > /opt/kiosk/launch.sh <<'EOF'
#!/bin/bash
while true; do
    chromium --kiosk https://dashboard.example.com
    sleep 2
done
EOF
chmod +x /opt/kiosk/launch.sh
cage -- /opt/kiosk/launch.sh
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
