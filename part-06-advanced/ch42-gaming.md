# Chapter 42 — Gaming on Wayland: XWayland, gamescope, VRR, HDR

## Overview

Gaming on Wayland is now production-ready for the vast majority of users as of 2025/2026. The
ecosystem has matured significantly: XWayland provides seamless backwards compatibility for the
enormous catalog of X11 games, gamescope adds a Valve-engineered microcompositor layer with
upscaling and HDR, and the kernel-level VRR/FreeSync infrastructure is solid across AMD and
Intel hardware. NVIDIA support has stabilized substantially with explicit sync patches landing in
mainline compositors.

This chapter covers the complete gaming stack from the bottom up: XWayland internals, gamescope
configuration, Variable Refresh Rate setup, HDR pipelines, input latency optimization, performance
monitoring, and per-vendor NVIDIA/AMD/Intel considerations. By the end you will be able to build a
gaming-optimized Wayland desktop that matches or exceeds X11 in every measurable way.

Cross-references: See Ch 15 for Hyprland compositor fundamentals, Ch 33 for display server
protocol deep-dives, Ch 53 for session startup and environment variables, and Ch 38 for GPU
driver setup.

---

## 42.1 Wayland Gaming Status (2025/2026)

The question "is Wayland ready for gaming?" has a clear answer in 2026: yes, with narrow
exceptions. The Proton team at Valve shipped native Wayland support across the full DXVK/VKD3D
stack. SDL3 (the successor to SDL2) defaults to the Wayland backend. Unity's HDRP pipeline gained
native Wayland output in late 2024. The remaining X11-only code paths are legacy anti-cheat
kernel modules that introspect window system internals — a problem specific to a handful of
competitive multiplayer titles, not a general Wayland limitation.

Native Wayland games use `wl_surface` directly and benefit from true zero-copy buffer sharing
(DMA-BUF), eliminating the copy that X11's shared memory segments require. They also receive
accurate high-resolution timestamps from the compositor's presentation feedback protocol
(`wp_presentation`), enabling precise frame pacing. SDL3 games compiled with
`-DSDL_VIDEO_DRIVER=wayland` default to the Wayland backend unless `SDL_VIDEODRIVER=x11` is
explicitly set. You can verify a game's backend by checking `/proc/<pid>/environ` or observing
`WAYLAND_DISPLAY` in its environment.

| Category | Status | Examples |
|---|---|---|
| Native SDL3/SDL2 Wayland | Production ready | Most indie titles |
| XWayland (legacy X11) | Fully functional | Most Steam back-catalog |
| Proton with Wayland backend | Production (Proton 9+) | AAA Steam titles |
| Unity (HDRP) | Partial (Linux export needed) | Varies by title |
| Unreal Engine 5 | Works via XWayland/Proton | Most UE5 titles |
| EAC/BattlEye anti-cheat | Game-specific opt-in | Apex, Fortnite (varies) |

Performance parity with X11 is now achieved or exceeded for nearly all workloads. The primary
remaining latency differentiator is compositor overhead: a well-tuned Hyprland or KWin setup
with `vblank_mode=0` (Xorg-style) and direct scan-out enabled will match raw X11 numbers within
the margin of frame time variance.

---

## 42.2 XWayland for Games

XWayland is an X11 server implementation that runs as a Wayland client, presenting X11 windows
as Wayland surfaces. When a Steam game launches without a native Wayland path, it connects to
the XWayland instance that your compositor started automatically. From the game's perspective,
it sees a perfectly normal X11 display — the `DISPLAY` variable is set (typically `:0` or `:1`),
and all X11 API calls work as expected. The compositor handles compositing XWayland windows
alongside native Wayland surfaces transparently.

For gaming, the critical XWayland feature is fullscreen passthrough. When a game requests
exclusive fullscreen mode via `_NET_WM_STATE_FULLSCREEN`, a modern compositor (Hyprland 0.36+,
KWin 6.2+) can grant the XWayland window direct hardware plane access — bypassing the compositor
render loop entirely. This is called "direct scan-out" or "XWayland unredirection" and eliminates
the compositing overhead, matching X11's bare-metal frame delivery. Enable it in Hyprland with:

```ini
# ~/.config/hypr/hyprland.conf
misc {
    # Enable direct scanout for fullscreen clients (eliminates compositor overhead)
    no_direct_scanout = false
}

# Fullscreen optimization rule for all games
windowrule = fullscreen, class:^(steam_app_.*)$
windowrule = fullscreenstate, class:^(steam_app_.*)$, 3
```

Input latency in XWayland is comparable to native X11 in fullscreen, because the compositor
removes itself from the input path during direct scan-out. In windowed mode there is a small
additional round-trip through the Wayland protocol. For competitive gaming in windowed mode,
prefer native Wayland games or use gamescope's embedded mode (section 42.3).

XWayland cursor scaling mismatch is a common pain point on HiDPI displays. Set:

```bash
# In your session startup (see Ch 53)
export XWAYLAND_NO_GLAMOR=0
export GDK_SCALE=2          # For GTK apps in XWayland
export QT_AUTO_SCREEN_SCALE_FACTOR=1

# Force XWayland cursor size to match Wayland
export XCURSOR_SIZE=24
export XCURSOR_THEME=Breeze  # or your theme
```

To verify which games are running under XWayland vs native Wayland, use `xwininfo -tree -root`
to list all X11 windows, or run `xlsclients` from a terminal after launching the game.

---

## 42.3 gamescope — The Gaming Compositor

gamescope is Valve's dedicated gaming microcompositor, built on wlroots. It wraps a single
application (or a handful of them, in SteamOS's case) in its own compositor instance, providing
a controlled rendering environment independent of your desktop compositor. This gives you per-game
upscaling, VRR, HDR tonemapping, frame limiting, and MangoHud integration without any of those
features needing to be implemented in your desktop compositor.

gamescope can run in two modes. **Nested mode** runs gamescope as a Wayland window inside your
existing compositor — useful for windowed gaming and testing. **Embedded mode** (also called
direct/kiosk mode) takes over the KMS/DRM device directly, bypassing the desktop compositor
entirely for maximum performance. Embedded mode requires no running compositor and is how SteamOS
uses gamescope on the Steam Deck.

### Basic gamescope Launch Options

Add gamescope to Steam's per-game launch options via right-click → Properties → Launch Options:

```bash
# Nested mode: game renders at 1080p, display at 1440p with FSR upscaling
gamescope -w 1920 -h 1080 -W 2560 -H 1440 --fsr-upscaling --fsr-sharpness 5 -f -- %command%

# Embedded/direct mode: full display takeover, 165Hz, VRR enabled
gamescope -W 2560 -H 1440 -r 165 --adaptive-sync --hdr-enabled --embedded -- %command%

# Nested, force 1080p output to a 4K display with FSR, with MangoHud
gamescope -w 1920 -h 1080 -W 3840 -H 2160 --fsr-upscaling --fsr-sharpness 3 --mangoapp -f -- %command%

# Cap frames for battery savings on a laptop
gamescope -w 1920 -h 1080 -f -r 60 -- %command%

# NIS (Nvidia Image Scaling) upscaling as alternative to FSR
gamescope -w 1280 -h 720 -W 1920 -H 1080 --nis-upscaling -- %command%
```

### Complete gamescope Flag Reference

| Flag | Description |
|---|---|
| `-w`, `-h` | Game/internal render resolution (width, height) |
| `-W`, `-H` | Output/display resolution (width, height) |
| `-f` | Start in fullscreen mode |
| `-b` | Start in borderless windowed mode |
| `-r <fps>` | Frame rate limit |
| `--adaptive-sync` | Enable VRR/FreeSync on output |
| `--hdr-enabled` | Enable HDR output pipeline |
| `--hdr-itm-enabled` | Inverse tone mapping for SDR→HDR |
| `--fsr-upscaling` | AMD FidelityFX Super Resolution upscaling |
| `--nis-upscaling` | NVIDIA Image Scaling upscaling |
| `--fsr-sharpness N` | FSR sharpness 0 (sharp) to 20 (soft), default 2 |
| `--mangoapp` | Integrate MangoHud overlay |
| `--expose-wayland` | Expose Wayland display to child processes |
| `--steam` | Enable Steam overlay integration |
| `--backend drm` | Force DRM/KMS backend (embedded mode) |
| `--backend sdl` | Force SDL backend (nested mode) |
| `--force-grab-cursor` | Keep cursor locked inside gamescope window |
| `--cursor-scale-height N` | Scale cursor to this height in pixels |
| `--xwayland-count N` | Number of XWayland instances to start |
| `--immediate-flips` | Immediate page flips (reduces latency, may tear) |
| `--prefer-output <name>` | Prefer a specific DRM output connector |

### gamescope Upscaling Deep Dive

FSR 1.0 (the version integrated in gamescope) is a spatial upscaler — it does not use temporal
information like FSR 2/3. Despite that, it produces visibly cleaner results than simple bilinear
scaling. The quality tiers map to render scale percentages:

| FSR Quality Mode | Render Scale | `-w/-h` for 1440p output |
|---|---|---|
| Ultra Quality | 77% | 1970×1108 |
| Quality | 67% | 1706×960 |
| Balanced | 59% | 1506×847 |
| Performance | 50% | 1280×720 |

For a 1440p monitor (`-W 2560 -H 1440`), FSR Quality mode:
```bash
gamescope -w 1706 -h 960 -W 2560 -H 1440 --fsr-upscaling --fsr-sharpness 3 -f -- %command%
```

NIS is an alternative sharpening-based upscaler from NVIDIA that also works on AMD hardware
under gamescope. It tends to produce slightly softer results but handles fine detail differently.
Benchmark both on your specific titles and monitor.

---

## 42.4 Variable Refresh Rate for Gaming

Variable Refresh Rate (VRR) synchronizes the monitor's refresh rate to the GPU's output frame
rate, eliminating tearing without the input latency cost of traditional vsync. The Linux DRM
subsystem has supported VRR since kernel 5.0 (via the `drm_connector` VRR property), and
compositor support has matured through 2024-2025 to the point where it works reliably on AMD
and Intel hardware. FreeSync (AMD's VRR implementation) and HDMI VRR (consumer monitors) both
use the same kernel interface.

### Compositor VRR Configuration

**Hyprland:**
```ini
# ~/.config/hypr/hyprland.conf
monitor = DP-1, 2560x1440@165, 0x0, 1, vrr, 2
# VRR modes: 0=off, 1=on, 2=fullscreen only (recommended for gaming)

# Alternatively set globally:
# misc { vrr = 2 }
```

**KWin (Plasma 6):**
```bash
# Via kscreen-doctor:
kscreen-doctor output.DP-1.vrr.automatic

# Or via KDE System Settings → Display → Variable Refresh Rate
# Set to "Automatic" to enable only for fullscreen apps
```

**Sway:**
```ini
# ~/.config/sway/config
output DP-1 adaptive_sync on
```

**wlroots compositors (general):**
```ini
# Most wlroots compositors expose VRR via their monitor config
# Check your compositor's documentation; the underlying call is:
# wlr_output_set_adaptive_sync_enabled(output, true)
```

### VRR Requirements and Verification

VRR requires: (1) a FreeSync/G-Sync Compatible monitor, (2) DisplayPort or HDMI 2.1 connection,
(3) an AMD or Intel GPU with FreeSync driver support, or an NVIDIA GPU with G-Sync Compatible
driver. Check if your system supports VRR:

```bash
# Check connector VRR support
cat /sys/class/drm/card0-DP-1/vrr_capable
# Output: 1 = capable, 0 = not supported

# Check if VRR is currently enabled on the connector
cat /sys/class/drm/card0-DP-1/vrr_enabled

# View current VRR status via drminfo
sudo drminfo | grep -A5 "VRR\|adaptive"

# Use drm_info (rust tool, more readable)
sudo drm_info | grep -i "vrr\|sync\|freesync"

# AMD-specific: check FreeSync support
cat /sys/bus/pci/drivers/amdgpu/*/freesync_capable 2>/dev/null
```

For gamescope VRR, add `--adaptive-sync` to the launch command. gamescope directly programs the
DRM VRR property and does not depend on the desktop compositor's VRR implementation, making it
the most reliable path for VRR gaming even on compositors with incomplete VRR support.

---

## 42.5 HDR Gaming

HDR on Linux has followed two development paths: KWin/Plasma's production-ready HDR pipeline
(shipping in Plasma 6.1) and the gamescope-based HDR path (shipping in gamescope 3.14+). Both
require a kernel with proper HDR metadata support (6.3+), a DRM driver with HDR connector
properties, and an HDR-capable display connected via DisplayPort 1.4 or HDMI 2.1.

### KWin/Plasma 6 HDR Setup

KDE Plasma 6.1+ ships a complete HDR pipeline that handles SDR app tonemapping, HDR passthrough
for supported games, and per-output HDR calibration. Enable it:

```bash
# Via KDE System Settings → Display → HDR toggle (per monitor)
# Or via kscreen-doctor CLI:
kscreen-doctor output.DP-1.hdr.enable

# Verify HDR metadata is being sent:
sudo cat /sys/class/drm/card0-DP-1/hdr_output_metadata
```

Plasma's HDR implementation uses `VK_EXT_hdr_metadata` for Vulkan apps that declare HDR
output, and applies SDR→HDR tone mapping for apps that don't. This means older games look
correct (not washed out) even without explicit HDR support.

### gamescope HDR Setup

gamescope implements its own HDR pipeline and is the recommended path for HDR gaming on
non-Plasma compositors (Hyprland, Sway, etc.):

```bash
# Basic HDR passthrough (game must output HDR)
gamescope -W 3840 -H 2160 --hdr-enabled -f -- %command%

# HDR with inverse tone mapping (upconverts SDR games to HDR)
gamescope -W 3840 -H 2160 --hdr-enabled --hdr-itm-enabled \
  --hdr-itm-target-nits 400 -f -- %command%

# Full HDR setup with VRR and FSR
gamescope -w 1920 -h 1080 -W 3840 -H 2160 \
  --fsr-upscaling --fsr-sharpness 3 \
  --hdr-enabled --adaptive-sync \
  -r 120 -f -- %command%
```

### Kernel and Driver Prerequisites

```bash
# Check kernel HDR support
grep -r "HDR" /sys/class/drm/card0-DP-1/ 2>/dev/null | head -20

# Enable HDR kernel parameter (some older kernels/drivers need this)
# Add to /etc/kernel/cmdline or GRUB_CMDLINE_LINUX:
# amdgpu.hdr=1

# Check EDID for HDR capability
edid-decode /sys/class/drm/card0-DP-1/edid 2>/dev/null | grep -i "hdr\|luminance"

# Alternatively, use read-edid:
get-edid | parse-edid | grep -i "hdr"

# Monitor peak brightness (for tone mapping calibration)
# Find this in your monitor's spec sheet or OSD menu
```

### Proton HDR Support

Proton 9.0+ with DXVK 2.3+ supports HDR output via `VK_EXT_hdr_metadata`. For games that
have Windows HDR support, the HDR path works through the full Proton stack:

```bash
# Enable HDR in Steam launch options with gamescope:
DXVK_HDR=1 gamescope --hdr-enabled --expose-wayland -f -- %command%

# For direct Proton (no gamescope), experimental:
PROTON_ENABLE_WAYLAND=1 DXVK_HDR=1 %command%
```

---

## 42.6 Input and Latency

Input latency in gaming Wayland setups comes from several independent sources: compositor frame
delivery scheduling, XWayland protocol overhead (for X11 games), libinput's pointer acceleration
pipeline, and hardware-level cursor planes. Each can be independently tuned.

### Pointer and Mouse Configuration

For competitive gaming, disable pointer acceleration entirely and use flat pointer profile:

```ini
# ~/.config/hypr/hyprland.conf
input {
    accel_profile = flat
    sensitivity = 0          # -1.0 to 1.0, 0 = no change to DPI
    force_no_accel = true    # Force disable any acceleration
}

# Per-device overrides (use hyprctl devices to find device names):
device {
    name = logitech-g-pro-x-superlight-2
    accel_profile = flat
    sensitivity = 0
}
```

```ini
# Sway / wlroots compositors:
# ~/.config/sway/config
input "type:pointer" {
    accel_profile flat
    pointer_accel 0
}

# Per-device:
input "1133:49306:Logitech_G_Pro" {
    accel_profile flat
    pointer_accel 0
}
```

To find your device names for per-device config:
```bash
hyprctl devices       # Hyprland
swaymsg -t get_inputs # Sway
libinput list-devices # Generic
```

### Pointer Locking and Relative Motion

Games that require mouse capture (FPS games, RTS pan-to-edge) use two Wayland protocols:
- `zwp_pointer_constraints_v1` for cursor locking/confining
- `zwp_relative_pointer_manager_v1` for relative (delta) motion events

Both are implemented in all major compositors. If a game fails to lock the cursor, it likely
hasn't been ported to Wayland and is running via XWayland — in which case the `_NET_WM_STATE_FULLSCREEN`
hint triggers the compositor's grab path instead. Force a game to use the XWayland cursor grab:

```bash
# Test pointer lock protocol support:
wayland-info | grep -i "pointer_constraints\|relative_pointer"

# For XWayland games failing to capture mouse:
# Ensure the window has focus and is fullscreen, or use gamescope --force-grab-cursor
```

### NVIDIA Cursor Workarounds

NVIDIA hardware cursors have historically had issues with XWayland on Wayland. If you see
cursor flickering or ghost cursors:

```bash
# Add to session startup:
export WLR_NO_HARDWARE_CURSORS=1   # Disable HW cursor (compositor renders in SW)

# Hyprland-specific cursor fix:
# ~/.config/hypr/hyprland.conf
cursor {
    no_hardware_cursors = true
    # Or: use_cpu_buffer = 1  (older syntax)
}
```

This has a negligible performance impact — the cursor is a single small surface rendered once
per frame.

### Measuring Input Latency

```bash
# Install latencytest for Wayland input latency measurement:
# (builds from source: https://github.com/yurikhan/latencytest)

# Use MangoHud's FPS counter to indirectly measure frame timing:
MANGOHUD=1 MANGOHUD_CONFIG="fps,frametime,gpu_time,cpu_time" gamename

# Frame time histogram with MangoHud:
MANGOHUD_CONFIG="histogram,fps" MANGOHUD=1 gamename

# For X11/XWayland latency, use the classic xte latency test:
sudo apt install xautomation  # or pacman -S xdotool
```

---

## 42.7 Performance Monitoring

### MangoHud

MangoHud is the standard performance overlay for Linux gaming. It hooks into Vulkan and OpenGL
via layer/library injection, reading GPU/CPU stats via `sysfs` and `hwmon`, and rendering an
overlay directly in the game's frame buffer. It works identically on Wayland and X11.

**Installation:**
```bash
# Arch:
sudo pacman -S mangohud

# Fedora:
sudo dnf install mangohud

# Ubuntu (via PPA or flatpak):
flatpak install flathub com.valvesoftware.Steam  # includes MangoHud for Flatpak Steam
sudo add-apt-repository ppa:kisak/kisak-mesa && sudo apt install mangohud
```

**Configuration** (`~/.config/MangoHud/MangoHud.conf`):
```ini
# Full gaming overlay configuration
fps
frametime
frame_timing=1
gpu_stats
gpu_temp
gpu_power
gpu_name
cpu_stats
cpu_temp
cpu_power
ram
vram
io_stats
wine
engine_version
vulkan_driver
resolution
present_mode
show_fps_limit

# Visual config
font_size=22
background_alpha=0.5
position=top-left
width=260
toggle_hud=F12
toggle_fps_limit=F1

# FPS limits (cycle with toggle key)
fps_limit=0,60,120,165

# Logging (useful for benchmarks)
# log_duration=10
# output_folder=/tmp/mangohud
```

**Usage:**
```bash
# Launch any game with MangoHud:
MANGOHUD=1 gamename

# Via Steam launch options:
mangohud %command%

# MangoHud with gamescope (use --mangoapp for gamescope integration):
gamescope --mangoapp -f -- mangohud game

# Config override on command line:
MANGOHUD_CONFIG="fps,frametime,gpu_temp,cpu_temp" MANGOHUD=1 gamename
```

### GOverlay

GOverlay is a Qt-based GUI for creating and editing MangoHud (and vkBasalt) config files:

```bash
sudo pacman -S goverlay      # Arch
sudo flatpak install flathub net.davidotek.pupgui2  # Flatpak alternative
```

### DXVK HUD

For games running through DXVK (DirectX → Vulkan translation), DXVK's built-in HUD provides
internal draw call, frame time, and API-level data that MangoHud cannot:

```bash
# Full DXVK HUD:
DXVK_HUD=full gamename

# Specific stats:
DXVK_HUD=fps,devinfo,frametimes,submissions,drawcalls,pipelines gamename

# Add to Steam launch options:
DXVK_HUD=fps,frametimes %command%
```

### Benchmarking with Frame Time Capture

```bash
# MangoHud CSV log of a benchmark run:
MANGOHUD=1 MANGOHUD_CONFIG="fps,frametime,log_duration=60,output_folder=/tmp" gamename

# View captured data:
ls /tmp/MangoHud/
# Plot with python or mango-plot:
pip install pandas matplotlib
python3 -c "
import pandas as pd, matplotlib.pyplot as plt
df = pd.read_csv('/tmp/MangoHud/gamename_*.csv')
plt.plot(df['frametime'])
plt.ylabel('Frame Time (ms)'); plt.xlabel('Frame')
plt.savefig('/tmp/frametimes.png')
"
```

---

## 42.8 NVIDIA-Specific Gaming Setup

NVIDIA on Wayland requires specific kernel parameters and environment variables that differ from
AMD/Intel. The driver's KMS implementation (required for Wayland) was not enabled by default
until relatively recently, and explicit sync support (needed to prevent tearing/corruption with
async rendering) landed in kernel and compositor code through 2024.

### Kernel Parameters

```bash
# /etc/modprobe.d/nvidia.conf  (or equivalent for your distro)
options nvidia-drm modeset=1 fbdev=1

# /etc/modprobe.d/nvidia.conf for NVIDIA open kernel modules (>= 560):
options nvidia NVreg_EnableGpuFirmware=1
options nvidia-drm modeset=1

# Rebuild initramfs after changes:
sudo mkinitcpio -P          # Arch
sudo update-initramfs -u    # Debian/Ubuntu
sudo dracut --force         # Fedora
```

### Environment Variables

```bash
# ~/.config/environment.d/nvidia-gaming.conf
# (see Ch 53 for environment.d usage)

# Required for XWayland on NVIDIA:
LIBVA_DRIVER_NAME=nvidia

# VRR/G-Sync:
__GL_GSYNC_ALLOWED=1
__GL_VRR_ALLOWED=1

# Prevent NVIDIA-specific Vulkan validation noise:
VK_DRIVER_FILES=/usr/share/vulkan/icd.d/nvidia_icd.json

# Explicit sync (Hyprland 0.38+, KWin 6.1+, eliminates corruption):
# No env var needed — compositor auto-detects via DRM props

# For older compositors without explicit sync:
HYPRLAND_NO_DIRECT_SCANOUT=1  # Hyprland < 0.38
```

### Explicit Sync

The biggest NVIDIA gaming improvement in 2024 was explicit sync support. Before explicit sync,
NVIDIA's driver used implicit fence synchronization that was incompatible with the Wayland/DRM
protocol's assumptions, causing frame corruption, screen tearing, and random rendering artifacts.
Explicit sync patches landed in:

- Mesa/Wayland protocols: May 2024
- Hyprland: 0.38 (June 2024)
- KWin: Plasma 6.1 (June 2024)
- NVIDIA driver: 555.58 (June 2024)

Verify explicit sync is active:
```bash
# Hyprland: check compositor log
journalctl --user -u hyprland | grep -i "explicit\|sync"

# Or check hyprland.log:
grep -i "explicit" ~/.local/share/hyprland/hyprland.log

# NVIDIA driver version check:
nvidia-smi --query-gpu=driver_version --format=csv,noheader
# Should be >= 555.58 for explicit sync
```

### Vulkan ICD Configuration

```bash
# List available Vulkan ICDs:
ls /usr/share/vulkan/icd.d/
# Example output:
# nvidia_icd.json  intel_icd.x86_64.json  radeon_icd.x86_64.json

# Force a specific ICD (useful on hybrid laptops):
VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json gamename

# Check which Vulkan device a game is using:
VK_LOADER_DEBUG=all gamename 2>&1 | grep "GPU\|device\|icd" | head -20
```

---

## 42.9 Proton and Wine on Wayland

Proton is Valve's Wine fork with DXVK, VKD3D-Proton, Steam Linux Runtime container
integration, and patches for Linux gaming compatibility. Since Proton 8.0, experimental
native Wayland support has been available; Proton 9.0 made it the default path for games
that work with it.

### Enabling the Proton Wayland Backend

```bash
# Per-game in Steam launch options:
PROTON_ENABLE_WAYLAND=1 %command%

# Or globally in ~/.steam/steam/steam_dev.cfg (Steam beta):
# Not recommended globally — some games break with native Wayland

# Verify the game is using Wayland backend (check Wine environment):
# In game launch output or steam log:
# grep "wayland\|DISPLAY" ~/.steam/steam/logs/steam_bootstrap.log
```

When `PROTON_ENABLE_WAYLAND=1` is set, Wine uses the `wine-wayland` display driver instead of
the X11 driver. The game window appears as a native `wl_surface` — your compositor sees it as
a Wayland client with no XWayland involvement. This eliminates XWayland overhead and enables
native HDR passthrough.

### wine-wayland (Standalone Wine)

For games run outside Steam, `wine-wayland` is the native Wayland backend for Wine:

```bash
# Install wine-wayland (Arch: wine-wayland AUR package, or compile from source):
paru -S wine-wayland

# Run a Windows executable with Wayland backend:
DISPLAY= WAYLAND_DISPLAY=wayland-1 wine game.exe

# With DXVK installed (auto-installed by winetricks):
DISPLAY= WAYLAND_DISPLAY=wayland-1 DXVK_HUD=fps wine game.exe

# Verify Wayland backend is active (should see no DISPLAY= fallback):
WINELOADER=wine WINEFSYNC=1 DISPLAY= wine winecfg 2>&1 | grep -i "wayland\|display"
```

### DXVK and VKD3D-Proton

DXVK translates DirectX 9/10/11 to Vulkan. VKD3D-Proton translates DirectX 12 to Vulkan.
Both work identically on Wayland since they interface with the GPU via Vulkan, not the display
server. Key environment variables:

```bash
# DXVK state cache: dramatically speeds up shader compilation
DXVK_STATE_CACHE=1
DXVK_STATE_CACHE_PATH=~/.cache/dxvk

# DXVK async shader compilation (reduces stutter):
DXVK_ASYNC=1

# VKD3D-Proton: enable DXR (raytracing) if GPU supports it
VKD3D_CONFIG=dxr gamename

# Disable DXVK for OpenGL games (use Wine's OpenGL → DXVK path):
# (no special variable; DXVK only intercepts D3D calls, not OpenGL)
```

---

## 42.10 Controller Support

Controller support on Linux is handled by the kernel's input subsystem (`evdev`), `udev` for
device permissions, and optionally `SDL_GameControllerDB` for button mapping. Wayland compositors
consume input via `libinput` but pass raw controller events to applications via `evdev` directly
— controllers do not go through the Wayland input protocol (which covers keyboard, mouse, touch,
and tablet). This means controller support is compositor-agnostic and identical between Wayland
and X11.

### udev Rules for Controller Access

Without proper udev rules, controller device nodes (`/dev/input/js*`, `/dev/input/event*`) are
root-only. Most distributions ship rules for common controllers, but you may need to add rules
for newer or unusual devices:

```ini
# /etc/udev/rules.d/99-game-controllers.rules

# Xbox One/Series controller (wired and wireless adapter):
SUBSYSTEM=="input", ATTRS{idVendor}=="045e", ATTRS{idProduct}=="02fd", MODE="0664", GROUP="input"
SUBSYSTEM=="input", ATTRS{idVendor}=="045e", ATTRS{idProduct}=="0b12", MODE="0664", GROUP="input"

# PlayStation 5 DualSense:
SUBSYSTEM=="input", ATTRS{idVendor}=="054c", ATTRS{idProduct}=="0ce6", MODE="0664", GROUP="input"
SUBSYSTEM=="usb", ATTRS{idVendor}=="054c", ATTRS{idProduct}=="0ce6", MODE="0664", GROUP="input"
KERNEL=="hidraw*", ATTRS{idVendor}=="054c", ATTRS{idProduct}=="0ce6", MODE="0664", GROUP="input"

# Steam Controller:
SUBSYSTEM=="input", ATTRS{idVendor}=="28de", MODE="0664", GROUP="input"
KERNEL=="uinput", MODE="0660", GROUP="input", OPTIONS+="static_node=uinput"

# Generic: allow all input devices for users in the input group:
# (use cautiously on multi-user systems)
# SUBSYSTEM=="input", GROUP="input", MODE="0664"
```

```bash
# Apply udev rules:
sudo udevadm control --reload-rules
sudo udevadm trigger

# Add your user to the input group:
sudo usermod -aG input $USER
# Log out and back in for group change to take effect

# Verify controller is accessible:
ls -la /dev/input/js*
ls -la /dev/input/event* | grep -i "xbox\|xbox\|sony\|ps5"
```

### Testing Controllers

```bash
# Test raw evdev events:
sudo evtest
# Select your controller device, press buttons to verify

# Test joystick via jstest:
sudo pacman -S jstest-gtk   # Arch
jstest /dev/input/js0

# SDL2 controller test tool:
sudo pacman -S sdl2-test    # Arch (build from SDL2 source if not available)
sdl2-jstest --list

# Comprehensive controller info:
cat /proc/bus/input/devices | grep -A10 "Xbox\|DualSense\|Steam"
```

### Steam Input and Controller Remapping

Steam Input is a comprehensive controller remapping layer built into Steam. It intercepts
controller events at the Steam layer and presents a virtual controller to the game. It handles:

- Button remapping and action layer switching
- Gyroscope-to-mouse mapping (DualSense/Switch Pro)
- Trackpad simulation (Steam Controller)
- Per-game configuration profiles shared via Steam Workshop

Steam Input works via the `uinput` kernel module (which creates virtual input devices) and
requires the `uinput` device to be writable. The udev rule above enables this.

For non-Steam games or when Steam Input is disabled, use `xboxdrv` (Xbox-specific) or
`ds4drv`/`dualsensectl` for PlayStation controllers:

```bash
# dualsensectl for PS5 DualSense:
sudo pacman -S dualsensectl   # or pip install dualsensectl
dualsensectl status          # Show battery, microphone, lightbar state
dualsensectl lightbar 0 0 255  # Set lightbar to blue
dualsensectl microphone mute  # Mute mic
```

### Bluetooth Controller Pairing

```bash
# bluetoothctl pairing (standard for all controllers):
bluetoothctl
# Inside bluetoothctl:
[bluetooth]# power on
[bluetooth]# agent on
[bluetooth]# scan on
# Put controller in pairing mode, then:
[bluetooth]# pair XX:XX:XX:XX:XX:XX
[bluetooth]# trust XX:XX:XX:XX:XX:XX
[bluetooth]# connect XX:XX:XX:XX:XX:XX

# Xbox controller pairing note: requires xpadneo kernel module for full feature support:
sudo dkms install -m xpadneo -v 0.9.4  # Check current version at github.com/atar-axis/xpadneo

# Check Bluetooth controller latency:
hcitool con  # List active connections
# For Xbox via BT: use USB dongle + xow for lowest latency option
```

---

## 42.11 AMD-Specific Gaming Optimizations

AMD on Wayland is the reference platform — AMD GPUs with the `amdgpu` kernel driver and Mesa
provide the most complete Wayland gaming feature set, including FreeSync VRR, HDR, and zero
additional configuration for most features.

```bash
# Enable performance power profile for gaming:
echo performance | sudo tee /sys/class/drm/card0/device/power_dpm_force_performance_level

# Or use gamemode (recommended — automatically applies and reverts):
sudo pacman -S gamemode lib32-gamemode
# Add to Steam launch options:
gamemoderun %command%

# ~/.config/gamemode.ini
[general]
renice=10
ioprio=0

[cpu]
governor=performance
park_cores=no

[gpu]
apply_gpu_optimisations=accept-responsibility
gpu_device=0
amd_performance_level=high

# ROCm for AMD compute (not needed for gaming, but for AI/ML adjacent work):
sudo pacman -S rocm-opencl-runtime
```

```bash
# Check AMD GPU clocks and thermals while gaming:
watch -n 1 cat /sys/class/drm/card0/device/hwmon/hwmon*/temp1_input
# Output is in millidegrees Celsius

# Using radeontop for real-time AMD GPU utilization:
sudo pacman -S radeontop
radeontop -c

# AMD GPU overdrive (manual clock/voltage tuning — advanced, use carefully):
# Requires amdgpu.ppfeaturemask=0xffffffff kernel parameter
echo "s 1 2200 1050" | sudo tee /sys/class/drm/card0/device/pp_od_clk_voltage
echo "c" | sudo tee /sys/class/drm/card0/device/pp_od_clk_voltage
```

---

## Troubleshooting

### Game fails to launch / black screen

```bash
# Check if the game process is running:
pgrep -a steam_app
pgrep -a wine

# Try removing problematic env vars one by one:
# Remove PROTON_ENABLE_WAYLAND=1 if set, fall back to XWayland
# Remove DXVK_ASYNC=1 (can cause issues with some games)

# Check Steam log for Proton errors:
~/.steam/steam/logs/steam_bootstrap.log

# Run game with verbose Proton logging:
PROTON_LOG=1 %command%
# Log appears at ~/steam-<appid>.log

# For Wine games:
WINEDEBUG=+all wine game.exe 2>&1 | head -100
```

### gamescope fails to start / crashes

```bash
# Test gamescope with a simple X11 client:
gamescope -w 800 -h 600 -f -- xterm

# Check for missing Wayland socket:
echo $WAYLAND_DISPLAY    # Should be set (e.g., wayland-1)
ls $XDG_RUNTIME_DIR/     # Should contain wayland-1 socket

# gamescope DRM backend fails (embedded mode):
# Ensure no other compositor is running if using --backend drm
# Check DRM permissions: sudo gpasswd -a $USER video

# gamescope verbose logging:
GAMESCOPE_LOG=debug gamescope -w 1920 -h 1080 -f -- game 2>&1 | head -50
```

### VRR not working

```bash
# Step 1: Verify hardware support
cat /sys/class/drm/card0-DP-1/vrr_capable
# Must be 1; if 0, check cable (must be DP, not HDMI < 2.1) and monitor specs

# Step 2: Verify compositor has VRR enabled
# Hyprland: check hyprctl monitors
hyprctl monitors | grep -i "vrr\|adaptive"

# Step 3: Check if kernel allows VRR
sudo cat /sys/kernel/debug/dri/0/amdgpu_dm_dp_link_settings  # AMD-specific

# Step 4: Force VRR via sysfs (temporary test):
echo 1 | sudo tee /sys/class/drm/card0-DP-1/vrr_enabled

# Step 5: AMD FreeSync must be enabled in monitor OSD
# Most FreeSync monitors have it disabled by default in OSD settings
```

### NVIDIA artifacts / screen corruption

```bash
# Verify explicit sync is active (driver >= 555.58 required):
nvidia-smi --query-gpu=driver_version --format=csv,noheader

# Check that modeset is enabled:
cat /sys/module/nvidia_drm/parameters/modeset
# Must output: Y

# Rebuild initramfs if you just changed modprobe options:
sudo mkinitcpio -P    # Arch

# Disable direct scan-out as a workaround:
# ~/.config/hypr/hyprland.conf
# misc { no_direct_scanout = true }

# Force software cursor:
export WLR_NO_HARDWARE_CURSORS=1
# Add to ~/.config/environment.d/nvidia.conf for persistence
```

### MangoHud not showing overlay

```bash
# Vulkan: verify MangoHud layer is installed
vulkaninfo | grep -i mango
ls /usr/share/vulkan/implicit_layer.d/MangoHud*

# OpenGL: verify library is present
ls /usr/lib/libMangoHud*
ls /usr/lib32/libMangoHud*  # 32-bit games need 32-bit MangoHud

# Test with a known-good Vulkan app:
MANGOHUD=1 vkcube

# If overlay shows with vkcube but not in-game:
# The game may be disabling Vulkan layers (anti-cheat)
# Try: MANGOHUD_CONFIG="no_display" and toggle with F12 key
```

### Controller not recognized by game

```bash
# Check udev permissions:
ls -la /dev/input/js* /dev/input/event*
# Should be group-writable with group=input

# Verify user is in input group:
groups $USER | grep input
# If not: sudo usermod -aG input $USER && re-login

# Check uinput for Steam Input:
ls -la /dev/uinput
# Should exist and be group-writable

# Force controller reconnect without replug:
sudo udevadm trigger --subsystem-match=input

# Test the controller in a simple way:
cat /dev/input/js0 | od -tx1  # Raw bytes should change when pressing buttons
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
