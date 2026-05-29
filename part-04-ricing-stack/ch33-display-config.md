# Chapter 33 — Display Configuration: kanshi, wdisplays, wlr-randr, shikane

## Overview

Multi-monitor configuration on Wayland is fundamentally different from the X11 era. Under X11, `xrandr` directly manipulated the display server's state by issuing RandR protocol requests. Under Wayland, the compositor owns exclusive control of output configuration — clients can only request changes through standardized protocols. The primary protocol for this is `wlr-output-management`, originally pioneered by the wlroots compositor library and now widely adopted.

Tools discussed in this chapter — kanshi, wdisplays, wlr-randr, and shikane — all communicate through `wlr-output-management`. They translate your configuration intent into atomic transactions that the compositor either accepts or rejects as a unit. This transactional model prevents partial misconfigurations (e.g., setting an invalid mode on one monitor out of four).

For a riced desktop, the goal is deterministic, automatic display setup regardless of which monitors are plugged in. This chapter covers: understanding the protocol, writing robust kanshi profiles, using GUI tools for discovery, scripting with wlr-randr, and handling edge cases like fractional scaling, rotation, VRR, and HDR. For session startup integration, see Ch 53. For per-application display overrides using environment variables, see Ch 41.

---

## 33.1 wlr-output-management Protocol

The `wlr-output-management-v1` protocol exposes two primary interfaces: `zwlr_output_manager_v1` (the manager, for enumerating and configuring outputs) and `zwlr_output_head_v1` (representing each connected display with its advertised modes and current state). Clients receive notifications of head additions and removals so they can react to hotplug events in real time.

The configuration workflow follows a test-and-apply pattern. A client creates a `zwlr_output_configuration_v1` object, attaches per-head configurations (each specifying mode, position, scale, transform, and whether the head is enabled), then calls either `test` (dry-run, compositor validates without applying) or `apply` (commit atomically). The compositor responds with `succeeded`, `failed`, or `cancelled`. This atomicity is critical: if any head's requested mode is invalid, the entire transaction fails, leaving the current state intact.

Key properties exposed per output head:

| Property | Protocol Name | Description |
|---|---|---|
| Mode | `zwlr_output_mode_v1` | Width, height, refresh (mHz), preferred flag |
| Position | `x`, `y` | Logical pixel coordinates of the output origin |
| Scale | `scale` | Fractional scale factor (fixed-point 24.8) |
| Transform | `transform` | Rotation+flip enum (normal, 90, 180, 270, flipped, …) |
| Adaptive Sync | `adaptive_sync` | VRR enable/disable |
| Name | `name` | Connector name, e.g. `DP-1`, `eDP-1`, `HDMI-A-1` |
| Description | `description` | Human-readable: `Make Model Serial` |

The `description` field is the stable identifier for physical monitors. Connector names (`DP-1`) are assigned by the compositor and can shift when devices are added or removed. Robust configurations use description matching rather than connector name matching whenever possible.

To inspect what your compositor currently reports:

```bash
# List all outputs with modes and properties (requires wlr-randr):
wlr-randr

# Sample output:
# DP-1 "Dell Inc. Dell U2722D 4N25CT3" (connected)
#   2560x1440 px, 27" (597x336 mm), scale 1.00
#   Modes:
#     2560x1440 @ 143.974 Hz (preferred, current)
#     2560x1440 @ 99.946 Hz
#     1920x1080 @ 143.981 Hz
#   Position: 0,0
#   Transform: normal
#   VRR: disabled
```

---

## 33.2 kanshi — Profile-Based Auto-Configuration

kanshi is the standard profile manager for wlroots-based compositors (sway, Hyprland, river, niri with the wlr-output-management backend). It runs as a daemon, listens for output hotplug events, and automatically applies the first matching profile from your configuration file.

### Installation

```bash
# Arch Linux
sudo pacman -S kanshi

# Fedora
sudo dnf install kanshi

# Ubuntu/Debian (may need backports or manual build)
sudo apt install kanshi

# From source (requires Wayland dev libraries)
git clone https://github.com/emersion/kanshi.git
cd kanshi
meson setup build && ninja -C build
sudo ninja -C build install
```

### Configuration File Format

The config file lives at `~/.config/kanshi/config`. Each `profile` block describes a set of outputs that must all be present for the profile to match. If multiple profiles match, the first one wins.

```
# ~/.config/kanshi/config

# Home desk: 1440p primary + 1080p secondary
profile home {
    output "Dell Inc. Dell U2722D 4N25CT3" position 0,0 mode 2560x1440@144Hz scale 1
    output "LG Electronics LG ULTRAGEAR 310NTXS000001" position 2560,0 mode 2560x1440@144Hz scale 1
}

# Laptop-only (lid open)
profile laptop_solo {
    output eDP-1 position 0,0 mode 1920x1200@60Hz scale 1.5
}

# Laptop docked to external monitor, lid closed
profile docked {
    output "Dell Inc. Dell U2722D 4N25CT3" position 0,0 mode 2560x1440@144Hz scale 1
    output eDP-1 disable
}

# Conference room projector
profile projector {
    output "Generic BNQ BenQ PD3220U 74K06628SL0" position 0,0 mode 3840x2160@60Hz scale 2
    output eDP-1 position 0,2160 mode 1920x1200@60Hz scale 1.5
}

# Wildcard: any single monitor at any resolution (fallback)
profile fallback {
    output * enable
}
```

Key syntax details:
- **Quoted strings** in `output` match by monitor description (Make Model Serial). This survives cable replugging.
- **Unquoted connector names** (e.g., `eDP-1`) match by connector. Use for internal displays that never move.
- `*` is a wildcard matching any output — useful for unknown monitors.
- `mode WxH@RHz` — omit the refresh to use the preferred mode.
- `scale F` — floating-point fractional scale. The compositor must support fractional scaling (see §33.6).
- `disable` — turn the output off without disconnecting.
- `exec` — run a command after the profile is applied (e.g., rearranging workspaces).

### Running kanshi as a Systemd User Service

```ini
# ~/.config/systemd/user/kanshi.service
[Unit]
Description=Kanshi display configuration daemon
PartOf=graphical-session.target
After=graphical-session.target

[Service]
ExecStart=/usr/bin/kanshi
Restart=on-failure
RestartSec=2s

[Install]
WantedBy=graphical-session.target
```

```bash
systemctl --user enable --now kanshi
systemctl --user status kanshi
journalctl --user -u kanshi -f   # tail the logs
```

### Reloading and Switching Profiles Manually

```bash
# Reload config from disk (pick up edits without restarting daemon):
kanshictl reload

# Force a specific profile regardless of connected outputs:
kanshictl switch-profile home

# List currently active profile:
kanshictl status
```

### exec Directive: Running Commands After Profile Switch

The `exec` directive fires after the output configuration is applied. Use it to reposition waybar, rearrange sway/Hyprland workspaces, or change wallpaper:

```
profile home {
    output "Dell Inc. Dell U2722D 4N25CT3" position 0,0 mode 2560x1440@144Hz scale 1
    output eDP-1 disable
    exec sh -c 'swaymsg "workspace 1, move workspace to output DP-1"'
    exec pkill -SIGUSR1 waybar
}

profile laptop_solo {
    output eDP-1 position 0,0 mode 1920x1200@60Hz scale 1.5
    exec sh -c 'feh --bg-scale ~/wallpapers/laptop.jpg'
}
```

---

## 33.3 wdisplays — GUI Configuration

wdisplays provides a GTK-based graphical interface for Wayland compositors supporting `wlr-output-management`. It is invaluable for initial setup: drag monitors to arrange them spatially, select resolutions from dropdowns, and visually confirm scaling — then export the result to a kanshi config snippet.

### Installation

```bash
sudo pacman -S wdisplays          # Arch
sudo dnf install wdisplays        # Fedora
sudo apt install wdisplays        # Ubuntu 22.04+
```

### Workflow

Launch `wdisplays` from a terminal or launcher. Each detected monitor appears as a colored rectangle. Operations:

1. **Drag** rectangles to set relative positions. The tool snaps to edges.
2. **Click** a monitor to open its settings panel: resolution, refresh rate, scale, rotation, and enable/disable toggle.
3. Click **Apply** to send the configuration to the compositor immediately (does not persist across sessions).
4. Click **Save** (in some builds) to write a kanshi-compatible snippet to stdout or a file.

wdisplays reads the current compositor state on launch, so what you see reflects what is active. It is particularly useful for discovering monitor description strings to copy into your kanshi config — open a terminal alongside it and run `wlr-randr` to cross-reference connector names with descriptions.

### Limitations

wdisplays does not persist configuration. It applies changes only for the current session; on next login, kanshi (or whatever daemon you have) will override it. Treat wdisplays as a discovery and testing tool, then copy the settings into your permanent kanshi config.

```bash
# Quick one-liner to get description strings for all connected outputs:
wlr-randr | grep '"'
# Output: "Dell Inc. Dell U2722D 4N25CT3" "LG Electronics LG HDR 4K 0x00047002"
```

---

## 33.4 wlr-randr — xrandr for Wayland

wlr-randr is a command-line tool analogous to `xrandr`. It communicates over `wlr-output-management` and is ideal for scripting, one-shot configuration, and diagnosis. Unlike kanshi, it does not persist state — changes last only until the next configuration event.

### Installation

```bash
sudo pacman -S wlr-randr     # Arch
sudo dnf install wlr-randr   # Fedora (may be in copr)
# Build from source:
git clone https://gitlab.freedesktop.org/emersion/wlr-randr
cd wlr-randr && meson setup build && ninja -C build
```

### Common Commands

```bash
# List all outputs with full detail (modes, position, scale, VRR):
wlr-randr

# Set a specific mode and position on one output:
wlr-randr --output DP-1 --mode 2560x1440@144Hz --pos 0,0 --scale 1

# Enable an output at its preferred mode:
wlr-randr --output HDMI-A-1 --on

# Disable an output:
wlr-randr --output HDMI-A-1 --off

# Set fractional scale:
wlr-randr --output eDP-1 --scale 1.5

# Rotate output 90 degrees:
wlr-randr --output DP-2 --transform 90

# Set position in logical pixel space:
wlr-randr --output DP-1 --pos 0,0 --output HDMI-A-1 --pos 2560,0

# Enable adaptive sync (VRR) on a specific output:
wlr-randr --output DP-1 --adaptive-sync enabled
```

### Scripting Example: Presentation Mode Toggle

```bash
#!/bin/bash
# ~/bin/toggle-projector.sh
# Detects if a projector is connected and toggles it

PROJECTOR_DESC="BNQ BenQ"

if wlr-randr | grep -q "$PROJECTOR_DESC"; then
    STATUS=$(wlr-randr | grep -A2 "$PROJECTOR_DESC" | grep "Enabled" | awk '{print $2}')
    if [ "$STATUS" = "yes" ]; then
        echo "Disabling projector..."
        wlr-randr --output HDMI-A-1 --off
    else
        echo "Enabling projector..."
        wlr-randr --output HDMI-A-1 --on --mode 1920x1080@60Hz --pos 2560,0
    fi
else
    echo "No projector detected."
fi
```

```bash
chmod +x ~/bin/toggle-projector.sh
# Bind to a key in sway:
# bindsym $mod+p exec ~/bin/toggle-projector.sh
```

---

## 33.5 shikane — Advanced Profile Manager

shikane is an alternative to kanshi that offers more powerful matching semantics, a JSON/TOML configuration format, and stricter output ordering guarantees. It targets users who need exact control over multi-monitor setups where kanshi's fuzzy matching causes unexpected profile switches.

### Key Differences from kanshi

| Feature | kanshi | shikane |
|---|---|---|
| Config format | Custom text | TOML |
| Matching | First match wins | Explicit priority ordering |
| Output ordering | Any order | Exact order required |
| Regex matching | Limited glob (`*`) | Full regex on description |
| Exec directive | Yes | Yes |
| Daemon protocol | wlr-output-management | wlr-output-management |
| Stability | Stable, widely used | Stable, less widespread |

### Installation

```bash
# AUR (Arch):
paru -S shikane

# Cargo (from source):
cargo install shikane

# Or from releases:
# https://github.com/hw0lff/shikane
```

### Configuration Example

```toml
# ~/.config/shikane/config.toml

[[profile]]
name = "home_desk"

[[profile.output]]
match = "Dell Inc. Dell U2722D.*"
enable = true
mode = { width = 2560, height = 1440, refresh = 143.974 }
position = { x = 0, y = 0 }
scale = 1.0
transform = "normal"
adaptive_sync = "enabled"

[[profile.output]]
match = "LG Electronics LG ULTRAGEAR.*"
enable = true
mode = { width = 2560, height = 1440, refresh = 143.974 }
position = { x = 2560, y = 0 }
scale = 1.0

[[profile]]
name = "laptop_only"

[[profile.output]]
match = ".*"
enable = true
mode = { width = 1920, height = 1200, refresh = 60.0 }
scale = 1.5

exec = ["notify-send", "shikane", "Switched to laptop_only profile"]
```

### Running shikane

```bash
# Start as a daemon:
shikane

# Reload config:
shikanectl reload

# Switch to a named profile:
shikanectl switch laptop_only

# Show current active profile:
shikanectl current
```

Integrate with systemd exactly as shown for kanshi in §33.2, substituting `shikane` for `kanshi` in the service file.

---

## 33.6 Fractional Scaling

Fractional scaling allows outputs to render at non-integer scale factors (e.g., 1.25×, 1.5×, 1.75×) to accommodate HiDPI displays that are not quite 2× density. The protocol backing this is `wp-fractional-scale-v1`, introduced in 2023 and now supported by major compositors.

### Protocol Mechanics

Under fractional scaling, the compositor tells each surface what scale factor to use. Native Wayland clients (GTK4, Qt6, wlroots apps) render at the logical size and the compositor scales the output. XWayland clients are trickier — they receive integer-scaled buffers and XWayland applies its own scaling heuristic.

```
Logical size: 1000×600 px (what the app thinks it has)
Scale factor: 1.5
Physical pixels: 1500×900 px (what the GPU scans out)
```

### Enabling in kanshi / wlr-randr

```bash
# In kanshi profile:
output eDP-1 position 0,0 mode 1920x1200@60Hz scale 1.5

# With wlr-randr one-shot:
wlr-randr --output eDP-1 --scale 1.5
```

### Compositor-Specific Notes

**Sway**: Fractional scaling is supported via `output <name> scale <factor>` in `~/.config/sway/config`. Enable the fractional scale protocol:

```
# ~/.config/sway/config
output eDP-1 scale 1.5

# For apps to use wp-fractional-scale-v1:
exec_always {
    xwayland force_scale 1
}
```

**Hyprland**: Fractional scaling is enabled by default when you set a scale in the monitor config:

```
# ~/.config/hypr/hyprland.conf
monitor=eDP-1,1920x1200@60,0x0,1.5
```

Additionally, enable the xwayland override for fractional scaling fidelity:

```
xwayland {
    force_zero_scaling = true
}
```

And set environment variables for toolkit scaling:

```
env = GDK_SCALE,1
env = GDK_DPI_SCALE,1
env = QT_AUTO_SCREEN_SCALE_FACTOR,1
env = QT_SCALE_FACTOR,1
```

### Cursor Scaling

Cursor size must be explicitly set to remain consistent at fractional scales:

```bash
# In ~/.config/hypr/hyprland.conf or sway config:
# Set cursor size for the compositor:
env = XCURSOR_SIZE,24

# For GTK apps:
env = XCURSOR_THEME,Nordzy-cursors

# ~/.config/gtk-3.0/settings.ini
[Settings]
gtk-cursor-size = 24
```

### Known Fractional Scaling Issues

| Issue | Cause | Workaround |
|---|---|---|
| Blurry XWayland windows | Integer upscaling | Set `Xft.dpi` in Xresources, use `xwayland force_scale` |
| Blurry Electron apps | Missing `--enable-features=WaylandWindowDecorations,UseOzonePlatform` | Add flags to app launch or `~/.config/<app>/flags` |
| Wrong cursor size in Qt | Qt ignores `XCURSOR_SIZE` in some versions | Set `QT_QPA_PLATFORMTHEME=qt5ct` and configure there |
| Wrong DPI in Firefox | Firefox overrides scale | `layout.css.devPixelsPerPx` in `about:config` |

---

## 33.7 Rotation and Transform

Wayland's `wlr-output-management` protocol supports 8 transform values for monitor rotation and flipping. These are compositor-level operations applied during scanout, not content transforms.

### Transform Values

| Value | Degrees CW | Flip |
|---|---|---|
| `normal` | 0° | No |
| `90` | 90° | No |
| `180` | 180° | No |
| `270` | 270° | No |
| `flipped` | 0° | Horizontal |
| `flipped-90` | 90° | Horizontal |
| `flipped-180` | 180° | Horizontal |
| `flipped-270` | 270° | Horizontal |

### Applying Rotation

```bash
# kanshi config — portrait monitor on the right:
profile home {
    output "Dell Inc. Dell U2722D 4N25CT3" position 0,0 mode 2560x1440@144Hz scale 1
    output "ASUS ASCQ MG279QR SN123456" position 2560,0 mode 2560x1440@144Hz scale 1 transform 90
}

# Note: after 90° rotation, the logical dimensions swap.
# A 2560x1440 monitor becomes 1440x2560 in the logical layout.
# Adjust position accordingly.
```

```bash
# Hyprland inline rotation:
# monitor=DP-2,2560x1440@144,2560x0,1,transform,1
# transform: 0=normal, 1=90CW, 2=180, 3=270, 4=flipped, 5=flipped-90, ...
monitor=DP-2,2560x1440@144,2560x0,1,transform,1

# wlr-randr one-shot:
wlr-randr --output DP-2 --transform 90
```

### Touchscreen Coordinate Mapping with Rotation

When a touchscreen's physical orientation doesn't match the display rotation, touches will register at wrong coordinates. The mapping lives in libinput and must be configured per-device:

```bash
# Find the touchscreen device name:
libinput list-devices | grep -A5 -i touch

# In sway config — map touchscreen to a specific output and apply transform:
input "1267:12360:ELAN1200:00_04F3:3048" {
    map_to_output eDP-1
    calibration_matrix 0 1 0 -1 0 1 0 0 1
    # Matrix for 90° rotation. See libinput docs for other angles.
}
```

For Hyprland, use the `input` section in `hyprland.conf`:

```
device {
    name = elan1200:00-04f3:3048
    output = eDP-1
    transform = 1
}
```

---

## 33.8 Variable Refresh Rate (VRR / Adaptive Sync)

Variable Refresh Rate (VRR) allows the display's refresh rate to dynamically match the compositor's frame output rate, eliminating tearing without the latency penalty of traditional V-Sync. Under Wayland, this is exposed as `adaptive_sync` in the `wlr-output-management` protocol.

### Enabling VRR by Compositor

**Sway:**

```
# ~/.config/sway/config
output DP-1 adaptive_sync on
```

**Hyprland:**

```
# ~/.config/hypr/hyprland.conf
misc {
    vrr = 1  # 0 = off, 1 = on, 2 = fullscreen only
}
```

Or per-monitor via `monitor` directive:

```
monitor=DP-1,2560x1440@144,0x0,1,vrr,1
```

**KWin (KDE Plasma on Wayland):**

Settings > Display and Monitor > Advanced > Adaptive Sync: Enabled

**kanshi** — set in profile:

```
profile home {
    output "Dell Inc. Dell U2722D 4N25CT3" position 0,0 mode 2560x1440@144Hz scale 1 adaptive_sync enabled
}
```

### Compositor VRR Support Matrix (2025/2026)

| Compositor | VRR Support | Notes |
|---|---|---|
| Sway | Yes (stable) | `output <name> adaptive_sync on` |
| Hyprland | Yes (stable) | `misc.vrr`, per-monitor flag |
| KWin | Yes (stable) | GUI + KScreen config |
| river | Partial | Via wlr-output-management clients |
| niri | Yes | `variable-refresh-rate` in config |
| labwc | Yes | wlr-output-management delegation |

### VRR Caveats

VRR at the compositor level applies globally to the display, not per-window. Some monitors flicker at very low frame rates (below their minimum VRR range). Check your monitor's specs for its VRR range (e.g., 48–144 Hz for many gaming monitors). The `vrr = 2` Hyprland mode (fullscreen only) is a practical compromise: you get smooth gaming without potential artifacts in desktop use.

```bash
# Check if your display supports adaptive sync:
wlr-randr | grep -i "adaptive\|vrr\|gsync\|freesync"
# Look for: VRR: supported (or disabled/enabled)
```

---

## 33.9 HDR Status (2025/2026)

High Dynamic Range (HDR) on Linux Wayland is in active development. The relevant protocol is `wp-color-management-v1`, which standardizes color space negotiation between compositors and clients.

### Current State by Compositor

| Compositor | HDR Status | Protocol |
|---|---|---|
| KWin (KDE 6.x) | Stable, production-ready | wp-color-management-v1 + proprietary KDE extensions |
| Hyprland | Experimental (behind flag) | wp-color-management-v1 (partial) |
| Sway | Not planned | N/A |
| Niri | In development | wp-color-management-v1 (WIP) |
| Mutter/GNOME | Experimental | color-management (internal) |

### KDE Plasma HDR Setup

KDE has the most mature HDR implementation on Linux as of 2025. Setup requires an HDR-capable monitor connected over DisplayPort 1.4 or HDMI 2.1.

```bash
# Enable HDR in KDE Plasma:
# Settings > Display and Monitor > HDR: On
# Or via kscreen-doctor:
kscreen-doctor output.DP-1.hdr.enable

# Check current color state:
kscreen-doctor output.DP-1.info
```

### Hyprland Experimental HDR

```
# ~/.config/hypr/hyprland.conf
# Requires Hyprland build with color management support
render {
    cm_fs_passthrough = 1
}
```

```bash
# Check if hyprland was compiled with color management:
hyprctl version | grep -i color
```

### wp-color-management-v1 Protocol Basics

The color management protocol allows surfaces to declare their color space and compositors to perform correct tone mapping. Supported color spaces include sRGB (default), DCI-P3, and BT.2020 (HDR10). Clients that are HDR-aware will negotiate BT.2020 with PQ (Perceptual Quantizer) transfer function.

```bash
# Applications that support wp-color-management in 2025:
# - mpv (with --vo=gpu-next --target-colorspace-hint=yes)
# - VLC (experimental HDR passthrough)
# - GIMP 3.0+ (wide-gamut preview)
# - Firefox (limited, canvas API)
```

---

## 33.10 Multi-Monitor Layout Planning

Before writing kanshi configs, plan your logical layout on paper or using an online monitor arrangement tool. The key concept is **logical pixel space**: each monitor occupies a rectangle, and positions are specified in logical pixels (pre-scale). A 4K monitor at scale 2.0 occupies 1920×1080 logical pixels even though it physically displays 3840×2160.

### Layout Calculation Example

```
Setup: Three monitors
- DP-1: 3840x2160 @ scale 2.0  → logical 1920x1080 at position (0,0)
- DP-2: 2560x1440 @ scale 1.0  → logical 2560x1440 at position (1920,0)
- eDP-1: 1920x1200 @ scale 1.5 → logical 1280x800 at position (4480,0)
                                              (1920+2560=4480)
```

```
# kanshi config for above layout:
profile triple_monitor {
    output "LG Electronics 27UD88-W 0x00000001" position 0,0 mode 3840x2160@60Hz scale 2
    output "Dell Inc. Dell U2722D 4N25CT3" position 1920,0 mode 2560x1440@144Hz scale 1
    output eDP-1 position 4480,0 mode 1920x1200@60Hz scale 1.5
}
```

```bash
# Verify the layout after applying:
wlr-randr
# Check that positions and logical sizes add up as expected.
```

---

## Troubleshooting

### kanshi Profile Not Matching

**Symptom:** kanshi starts but does not apply any profile; outputs remain in default or previous state.

**Diagnosis:**

```bash
# Check kanshi logs:
journalctl --user -u kanshi -n 50

# Verify output descriptions match exactly:
wlr-randr | grep '"'
# Compare against your kanshi profile's output strings.
```

**Common causes:**
- Description string has extra whitespace or different quoting.
- Profile requires outputs that are not all connected simultaneously.
- kanshi is not running when the compositor starts (timing issue).

**Fix for timing:**

```ini
# ~/.config/systemd/user/kanshi.service
[Service]
ExecStartPre=/bin/sleep 1   # Wait for compositor output enumeration
ExecStart=/usr/bin/kanshi
```

### wlr-randr: "compositor does not support wlr-output-management"

**Symptom:** `wlr-randr` exits with an error about missing protocol.

**Cause:** Your compositor does not implement `wlr-output-management-v1`. GNOME (Mutter) does not support this protocol — use `gnome-randr-rust` or KScreen tools instead.

```bash
# Check what protocols your compositor advertises:
wayland-info | grep output
```

### Fractional Scaling: Blurry Applications

**Symptom:** Some applications appear blurry or poorly scaled at non-integer scales.

```bash
# For Electron apps (e.g., VS Code, Discord):
# Add to ~/.config/code-flags.conf (or app equivalent):
--enable-features=WaylandWindowDecorations
--ozone-platform=wayland
--force-device-scale-factor=1.5

# For Firefox:
# about:config → layout.css.devPixelsPerPx = 1.5
# (set to your desired fractional scale)

# For Java/Swing apps:
# Add to JAVA_TOOL_OPTIONS:
export JAVA_TOOL_OPTIONS="-Dsun.java2d.uiScale=1.5"
```

### Monitor Detected but Black Screen

**Symptom:** `wlr-randr` shows the monitor as connected and enabled, but the display is black.

```bash
# Try forcing a mode explicitly:
wlr-randr --output HDMI-A-1 --mode 1920x1080@60Hz

# Check kernel modesetting:
sudo dmesg | grep -i "drm\|hdmi\|dp" | tail -20

# If using AMD/Intel, check connector status in sysfs:
cat /sys/class/drm/card*/card*-HDMI*/status
cat /sys/class/drm/card*/card*-DP*/status
```

### VRR Causing Screen Flickering

**Symptom:** Display flickers at idle or in low-framerate scenarios.

**Fix:** Set VRR to fullscreen-only mode, or check if the compositor allows setting a minimum refresh rate:

```
# Hyprland — fullscreen only:
misc {
    vrr = 2
}
```

Also ensure your monitor's minimum VRR range covers typical desktop frame rates (e.g., 48 Hz+).

### Rotation Not Persisting After Reboot

**Symptom:** Rotation applied with `wlr-randr` reverts on next login.

**Fix:** Rotation must be specified in your kanshi profile or compositor config — wlr-randr changes are not persistent. Add `transform 90` (or appropriate value) to your kanshi output line:

```
output "ASUS ASCQ MG279QR SN123456" position 2560,0 mode 2560x1440@144Hz scale 1 transform 90
```

---

## Cross-References

- **Ch 31** — Compositor configuration basics (sway, Hyprland, niri); where output config sections live in each compositor's config file.
- **Ch 41** — Per-application environment variables for scaling, DPI, and Wayland/X11 backend selection.
- **Ch 52** — Waybar multi-monitor configuration and output assignment.
- **Ch 53** — Session startup: ordering kanshi, waybar, and other daemons with systemd user services.
- **Ch 58** — Input device configuration (libinput, touchscreen mapping, tablet output assignment).

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
