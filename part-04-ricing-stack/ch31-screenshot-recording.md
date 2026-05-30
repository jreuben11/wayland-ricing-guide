# Chapter 31 — Screenshots and Recording: grim, slurp, wf-recorder, OBS

## Contents

- [Overview](#overview)
- [31.1 The Screencopy Protocol Stack](#311-the-screencopy-protocol-stack)
- [31.2 grim — The Screenshot Foundation](#312-grim-the-screenshot-foundation)
- [31.3 slurp — Region Selection](#313-slurp-region-selection)
- [31.4 hyprshot — Hyprland-Integrated Screenshots](#314-hyprshot-hyprland-integrated-screenshots)
- [31.5 Screenshot Scripting](#315-screenshot-scripting)
- [31.6 wf-recorder — Screen Recording](#316-wf-recorder-screen-recording)
- [31.7 OBS Studio on Wayland](#317-obs-studio-on-wayland)
- [31.8 wl-screenrec — Fast Hardware-Accelerated Recording](#318-wl-screenrec-fast-hardware-accelerated-recording)
- [31.9 Flameshot on Wayland](#319-flameshot-on-wayland)
- [31.10 Annotating Screenshots](#3110-annotating-screenshots)
- [31.11 wl-copy and Clipboard Integration](#3111-wl-copy-and-clipboard-integration)
- [Troubleshooting](#troubleshooting)

---


## Overview

Screenshot and screen recording on Wayland requires compositor cooperation via the screencopy protocol. Unlike X11, where any application could read pixel data from the display via the `XGetImage` call or similar X11 requests, Wayland enforces strict surface isolation — a client cannot read another client's pixel data without explicit compositor permission. This fundamental security improvement means the entire screenshot/recording toolchain had to be reimagined from scratch.

The native Wayland toolchain is now mature and feature-complete for most use cases. The dominant protocol is `wlr-screencopy-unstable-v1`, originally developed by the wlroots project and supported by compositors like Hyprland, Sway, and Wayfire. For applications that need portal-based access (Flatpak apps, OBS, browsers), `xdg-desktop-portal` bridges the gap through portal backends like `xdg-desktop-portal-wlr` and `xdg-desktop-portal-hyprland`.

This chapter covers the full stack: from low-level protocol mechanisms, through the grim/slurp pipeline for scripted screenshots, to wf-recorder and OBS for recording, and hardware-accelerated alternatives for high-performance capture. Practical scripting examples and keybind integration patterns are included throughout. See Ch 14 for compositor-level permissions and Ch 53 for wiring these scripts into session startup.

---

## 31.1 The Screencopy Protocol Stack

Wayland's security model prohibits direct framebuffer access from unprivileged clients. Screencopy protocols work differently: a client asks the compositor to copy surface pixels into a buffer the client controls. This copy is done under compositor authority, which means the compositor can enforce access policies, redact certain surfaces (e.g., lock screens, secure input fields), and throttle capture rates.

The `wlr-screencopy-unstable-v1` protocol, used by grim and wf-recorder, is a wlroots-specific extension. It allows capturing individual outputs (monitors) or arbitrary regions. This protocol is not part of the official Wayland spec, but it has de facto become the standard for wlroots-based compositors. Compositors like GNOME and KDE implement their own screencopy mechanisms accessed via `xdg-desktop-portal` with different backends.

`xdg-desktop-portal` (XDG portal) provides a D-Bus interface that applications use to request screen captures through a portal dialog. The actual implementation is delegated to a backend: `xdg-desktop-portal-wlr` handles wlroots compositors using the `wlr-screencopy-unstable-v1` protocol under the hood, while `xdg-desktop-portal-hyprland` is the recommended backend for Hyprland, adding support for window selection and workspace capture. Without a properly configured portal backend, applications like Firefox, Chromium, OBS, and any Flatpak app requiring screen capture will either fail silently or fall back to broken X11 paths.

| Component | Role | Compositor Support |
|-----------|------|--------------------|
| `wlr-screencopy-unstable-v1` | Low-level pixel copy | Sway, Hyprland, Wayfire, River |
| `zwlr-export-dmabuf-v1` | DMA-BUF zero-copy export | Hyprland, Sway (partial) |
| `xdg-desktop-portal-wlr` | Portal backend for wlroots | All wlroots compositors |
| `xdg-desktop-portal-hyprland` | Portal backend with extras | Hyprland only |
| `xdg-desktop-portal-gnome` | Portal backend | GNOME/Mutter |

Verify your portal setup before debugging screenshot tools:

```bash
# Check running portal processes
systemctl --user status xdg-desktop-portal.service
systemctl --user status xdg-desktop-portal-hyprland.service

# Test portal access (requires pipewire-portal)
dbus-send --session --print-reply \
  --dest=org.freedesktop.portal.Desktop \
  /org/freedesktop/portal/desktop \
  org.freedesktop.DBus.Properties.GetAll \
  string:org.freedesktop.portal.ScreenCast

# Check which portal backend is active
cat /usr/share/xdg-desktop-portal/portals/hyprland.portal
```

---

## 31.2 grim — The Screenshot Foundation

`grim` is the canonical Wayland screenshot tool for wlroots compositors. It communicates directly with the compositor via `wlr-screencopy-unstable-v1` and writes the result to a file or stdout. It is intentionally minimal — no GUI, no region selection UI — making it ideal as a scripting building block.

Install grim on major distributions:

```bash
# Arch Linux
sudo pacman -S grim

# Ubuntu/Debian (24.04+)
sudo apt install grim

# Fedora
sudo dnf install grim

# Build from source
git clone https://gitlab.freedesktop.org/emersion/grim.git
cd grim && meson setup build && ninja -C build && sudo ninja -C build install
```

Basic usage patterns cover the most common screenshot scenarios:

```bash
# Full screenshot of all outputs, saved to file
grim screenshot.png

# Capture specific output (monitor)
grim -o DP-1 monitor.png
grim -o eDP-1 laptop-screen.png

# List available outputs
grim --help  # outputs are shown via wlr-output-management or swaymsg

# Capture specific geometry (x,y widthxheight)
grim -g "0,0 1920x1080" left-monitor.png
grim -g "1920,0 2560x1440" right-monitor.png

# Scale factor (0.5 = half resolution, useful for HiDPI)
grim -s 0.5 scaled.png
grim -s 2.0 supersampled.png  # upscale

# Output formats
grim -t png screenshot.png       # PNG (lossless, default)
grim -t jpeg -q 90 screenshot.jpg  # JPEG with quality 0-100
grim -t ppm screenshot.ppm       # PPM (raw pixels, useful for piping)

# Output to stdout (use - as filename) and pipe to clipboard
grim - | wl-copy

# Combine with convert for additional processing
grim - | convert - -resize 50% thumbnail.png

# Pipe to multiple destinations simultaneously
grim - | tee ~/Pictures/backup.png | wl-copy
```

The `-s` scale factor is particularly important on HiDPI setups. If your monitor is configured at 2x scale in the compositor, `grim` by default captures at the logical resolution. Use `-s 2.0` to capture at the full physical pixel resolution when you need maximum detail.

---

## 31.3 slurp — Region Selection

`slurp` provides the interactive region selection UI that `grim` lacks. It renders a crosshair and selection rectangle on top of the compositor output, letting the user draw a region. The selected geometry is printed to stdout in `x,y widthxheight` format, which is exactly what `grim -g` expects.

```bash
# Install
sudo pacman -S slurp  # Arch
sudo apt install slurp  # Ubuntu 24.04+

# Basic interactive region selection
grim -g "$(slurp)" screenshot.png

# Selection with display mode (shows output labels, click to select whole output)
grim -g "$(slurp -d)" screenshot.png

# Output selection mode (click anywhere on an output to select the whole monitor)
grim -g "$(slurp -o)" screenshot.png

# Pipe slurp output to inspect the selection format
slurp
# Output: 450,320 800x600

# Pass pre-defined regions to slurp for guided selection
# (slurp highlights matching regions)
echo "0,0 1920x1080\n1920,0 2560x1440" | slurp
```

`slurp` can also read a list of candidate rectangles from stdin and highlight them, making it ideal for window-aware selection. Combine it with compositor IPC to list all window geometries:

```bash
# Hyprland: select from all open windows
grim -g "$(hyprctl clients -j | jq -r '.[] | "\(.at[0]),\(.at[1]) \(.size[0])x\(.size[1])"' | slurp)" window.png

# Sway: select from all open windows
grim -g "$(swaymsg -t get_tree | jq -r '.. | select(.pid? and .visible?) | .rect | "\(.x),\(.y) \(.width)x\(.height)"' | slurp)" window.png

# Hyprland: select active window directly (no slurp needed)
GEOM=$(hyprctl activewindow -j | jq -r '"\(.at[0]),\(.at[1]) \(.size[0])x\(.size[1])"')
grim -g "$GEOM" active-window.png
```

Customize slurp appearance to match your rice:

```bash
# Custom colors: border, selection fill, label
slurp -b '#1e1e2e80' -c '#cba6f7' -s '#89b4fa40' -d

# Persistent style in ~/.config/slurp/config (if your version supports it)
# Most configuration is done via command-line flags in scripts
```

---

## 31.4 hyprshot — Hyprland-Integrated Screenshots

`hyprshot` is a wrapper script that integrates `grim` and `slurp` with Hyprland's IPC, providing a user-friendly interface for the three most common screenshot modes. It handles window geometry queries, output detection, and optional clipboard copy automatically.

```bash
# Install via AUR
yay -S hyprshot
# or
paru -S hyprshot

# Region capture (interactive slurp selection)
hyprshot -m region

# Active window capture
hyprshot -m window

# Full output/monitor capture
hyprshot -m output

# Copy to clipboard only, do not save file
hyprshot -m region --clipboard-only
hyprshot -m window --clipboard-only

# Specify output directory
hyprshot -m region -o ~/Pictures/Screenshots

# Specify filename (without extension)
hyprshot -m window -f mywindow

# Silent mode (no notifications)
hyprshot -m output -s

# Combined: clipboard + save + silent
hyprshot -m region -o ~/Pictures -s
```

Configure hyprshot defaults in `~/.config/hypr/hyprshot.conf` if your version supports it, or by setting environment variables:

```bash
# In your hyprland.conf or shell profile
export HYPRSHOT_DIR="$HOME/Pictures/Screenshots"

# Bind in hyprland.conf
bind = , Print, exec, hyprshot -m output
bind = SHIFT, Print, exec, hyprshot -m region
bind = CTRL, Print, exec, hyprshot -m window --clipboard-only
bind = CTRL SHIFT, Print, exec, hyprshot -m region --clipboard-only
```

---

## 31.5 Screenshot Scripting

Production screenshot scripts combine grim, slurp, compositor IPC, clipboard tools, and notifications into unified workflows. The following is a full-featured script suitable for binding to keyboard shortcuts:

```bash
#!/usr/bin/env bash
# ~/.config/hypr/scripts/screenshot.sh
# Usage: screenshot.sh [region|full|window|monitor] [--clip]

set -euo pipefail

SAVE_DIR="${SCREENSHOT_DIR:-$HOME/Pictures/Screenshots}"
mkdir -p "$SAVE_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTFILE="$SAVE_DIR/screenshot_$TIMESTAMP.png"
CLIP_ONLY=false

[[ "${2:-}" == "--clip" ]] && CLIP_ONLY=true

notify() {
    notify-send -i "$SAVE_DIR/screenshot_$TIMESTAMP.png" \
        "Screenshot" "$1" -t 3000
}

case "${1:-region}" in
    region)
        GEOM=$(slurp -d) || exit 1
        if $CLIP_ONLY; then
            grim -g "$GEOM" - | wl-copy
            notify-send "Screenshot" "Region copied to clipboard" -t 2000
        else
            grim -g "$GEOM" "$OUTFILE"
            wl-copy < "$OUTFILE"
            notify "Saved: $(basename "$OUTFILE")"
        fi
        ;;

    full)
        if $CLIP_ONLY; then
            grim - | wl-copy
            notify-send "Screenshot" "Full screen copied to clipboard" -t 2000
        else
            grim "$OUTFILE"
            wl-copy < "$OUTFILE"
            notify "Saved: $(basename "$OUTFILE")"
        fi
        ;;

    window)
        GEOM=$(hyprctl activewindow -j | \
            jq -r '"\(.at[0]),\(.at[1]) \(.size[0])x\(.size[1])"') || exit 1
        if $CLIP_ONLY; then
            grim -g "$GEOM" - | wl-copy
            notify-send "Screenshot" "Window copied to clipboard" -t 2000
        else
            grim -g "$GEOM" "$OUTFILE"
            wl-copy < "$OUTFILE"
            notify "Saved: $(basename "$OUTFILE")"
        fi
        ;;

    monitor)
        OUTPUT=$(hyprctl monitors -j | jq -r '.[0].name') || exit 1
        if $CLIP_ONLY; then
            grim -o "$OUTPUT" - | wl-copy
        else
            grim -o "$OUTPUT" "$OUTFILE"
            wl-copy < "$OUTFILE"
            notify "Saved: $(basename "$OUTFILE")"
        fi
        ;;

    *)
        echo "Usage: $0 [region|full|window|monitor] [--clip]"
        exit 1
        ;;
esac
```

Bind in `~/.config/hypr/hyprland.conf`:

```ini
# hyprland.conf keybinds for screenshot script
bind = , Print,             exec, ~/.config/hypr/scripts/screenshot.sh region
bind = SHIFT, Print,        exec, ~/.config/hypr/scripts/screenshot.sh full
bind = CTRL, Print,         exec, ~/.config/hypr/scripts/screenshot.sh window
bind = ALT, Print,          exec, ~/.config/hypr/scripts/screenshot.sh monitor
bind = SUPER, Print,        exec, ~/.config/hypr/scripts/screenshot.sh region --clip
bind = SUPER SHIFT, Print,  exec, ~/.config/hypr/scripts/screenshot.sh window --clip
```

For Sway, replace the Hyprland IPC calls:

```bash
# Sway equivalent for window geometry
GEOM=$(swaymsg -t get_tree | \
    jq -r '.. | select(.focused? == true) | .rect | "\(.x),\(.y) \(.width)x\(.height)"')
```

---

## 31.6 wf-recorder — Screen Recording

`wf-recorder` is the wlroots-native screen recorder, using `wlr-screencopy-unstable-v1` for capture and FFmpeg for encoding. It is simpler to configure than OBS and well-suited for quick recordings, tutorials, and bug reports.

```bash
# Install
sudo pacman -S wf-recorder       # Arch
sudo apt install wf-recorder     # Ubuntu 24.04+
yay -S wf-recorder               # AUR (latest)

# Record entire screen (all outputs) to file
wf-recorder -f output.mp4

# Record specific output
wf-recorder -o DP-1 -f monitor.mp4

# Record selected region (interactive slurp)
wf-recorder -g "$(slurp)" -f region.mp4

# Stop recording gracefully (sends SIGINT)
pkill -INT wf-recorder

# Record with H.264 and compatible pixel format (recommended for compatibility)
wf-recorder -c libx264 -x yuv420p -f output.mp4

# Record with H.265/HEVC (smaller files, less compatible)
wf-recorder -c libx265 -x yuv420p -f output.mp4

# Record with VP9 (open format, good compression)
wf-recorder -c libvpx-vp9 -f output.webm

# Hardware-accelerated H.264 via VAAPI (AMD/Intel)
wf-recorder -c h264_vaapi -d /dev/dri/renderD128 -x yuv420p -f hw.mp4

# Hardware-accelerated H.264 via NVENC (NVIDIA)
wf-recorder -c h264_nvenc -f hw-nvidia.mp4

# Record with audio (PipeWire)
wf-recorder -f output.mp4 --audio

# Record with specific audio device
# List devices: pactl list sources | grep Name
wf-recorder -f output.mp4 -a "alsa_output.pci-0000_00_1f.3.analog-stereo.monitor"

# Set custom framerate (default: output refresh rate)
wf-recorder --framerate 60 -f output.mp4

# Lower quality for smaller files (CRF: lower = better quality)
wf-recorder -c libx264 -p crf=28 -f output.mp4

# Lossless recording (large files, perfect for editing)
wf-recorder -c libx264 -p crf=0 -f lossless.mp4

# Record to stdout and pipe to ffmpeg for custom processing
wf-recorder -c rawvideo -x bgr0 -f pipe:1 2>/dev/null | \
    ffmpeg -f rawvideo -pix_fmt bgr0 -s 1920x1080 -r 60 -i - \
    -c:v libx264 -crf 18 output.mp4
```

A practical recording toggle script for keybind use:

```bash
#!/usr/bin/env bash
# ~/.config/hypr/scripts/record.sh
# Toggle recording on/off, with region or full-screen modes

PIDFILE="/tmp/wf-recorder.pid"
SAVE_DIR="${RECORD_DIR:-$HOME/Videos/Recordings}"
mkdir -p "$SAVE_DIR"

if pgrep -x wf-recorder > /dev/null; then
    pkill -INT wf-recorder
    notify-send "Recording" "Stopped — saved to $SAVE_DIR" -i video-x-generic
    rm -f "$PIDFILE"
else
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    OUTFILE="$SAVE_DIR/recording_$TIMESTAMP.mp4"

    case "${1:-full}" in
        region)
            GEOM=$(slurp) || exit 1
            wf-recorder -g "$GEOM" -c libx264 -x yuv420p \
                --audio -f "$OUTFILE" &
            ;;
        full)
            wf-recorder -c libx264 -x yuv420p \
                --audio -f "$OUTFILE" &
            ;;
    esac
    echo $! > "$PIDFILE"
    notify-send "Recording" "Started — saving to $(basename "$OUTFILE")" -i media-record
fi
```

---

## 31.7 OBS Studio on Wayland

OBS Studio has had solid Wayland support since version 29 (2023), using PipeWire for screen capture. The key requirement is a functioning `xdg-desktop-portal` backend — without it, OBS cannot enumerate capture sources.

```bash
# Install OBS (Arch)
sudo pacman -S obs-studio

# Install OBS (Flatpak — recommended, gets updates faster)
flatpak install flathub com.obsproject.Studio

# For Flatpak, also install portal backend permissions
flatpak override --user --filesystem=xdg-run/pipewire-0 com.obsproject.Studio

# Launch with Wayland/PipeWire backend explicitly
obs --enable-media-stream

# If using X11 fallback (XWayland), force native Wayland:
QT_QPA_PLATFORM=wayland obs
```

Configure OBS for Wayland capture:

1. Add a "Screen Capture (PipeWire)" source in OBS.
2. OBS will trigger an `xdg-desktop-portal` screen selection dialog.
3. Select the window or output to capture.
4. The portal backend (`xdg-desktop-portal-hyprland` or `-wlr`) handles the actual screencopy.

For virtual camera output (useful for video calls):

```bash
# Load the v4l2loopback kernel module (required for virtual camera)
sudo modprobe v4l2loopback devices=1 video_nr=10 card_label="OBS Virtual Camera" exclusive_caps=1

# Make it persistent
echo "v4l2loopback" | sudo tee /etc/modules-load.d/v4l2loopback.conf
echo 'options v4l2loopback devices=1 video_nr=10 card_label="OBS Virtual Camera" exclusive_caps=1' | \
    sudo tee /etc/modprobe.d/v4l2loopback.conf

# In OBS: Tools → Virtual Camera → Start
# In video call app, select "OBS Virtual Camera" as webcam source
```

Autostart portal services needed by OBS (add to your session startup — see Ch 53):

```bash
# ~/.config/hypr/scripts/start-portals.sh
# Kill stale portal instances
pkill -x xdg-desktop-portal-hyprland || true
pkill -x xdg-desktop-portal || true
sleep 1

# Start Hyprland portal first, then the main portal
/usr/lib/xdg-desktop-portal-hyprland &
sleep 0.5
/usr/lib/xdg-desktop-portal --replace &
```

Or manage via systemd user services:

```ini
# ~/.config/systemd/user/xdg-desktop-portal-hyprland.service
[Unit]
Description=Portal service (Hyprland backend)
After=graphical-session.target

[Service]
Type=dbus
BusName=org.freedesktop.impl.portal.desktop.hyprland
ExecStart=/usr/lib/xdg-desktop-portal-hyprland
Restart=on-failure

[Install]
WantedBy=graphical-session.target
```

---

## 31.8 wl-screenrec — Fast Hardware-Accelerated Recording

`wl-screenrec` uses the `zwlr-export-dmabuf-v1` protocol to obtain GPU DMA-BUF handles directly, enabling zero-copy capture. This means the frame data never leaves GPU memory until encoding, dramatically reducing CPU load compared to `wf-recorder`'s software path.

```bash
# Install (AUR)
yay -S wl-screenrec

# Basic recording (auto-detects hardware encoder)
wl-screenrec -f output.mp4

# Select region
wl-screenrec -g "$(slurp)" -f region.mp4

# Specify encoder explicitly
wl-screenrec --encode-pixfmt nv12 -f output.mp4  # H.264 via VA-API (default)
wl-screenrec --encode-pixfmt nv12 --codec h265 -f output.mp4  # H.265

# Force software encoding (fallback if hardware unavailable)
wl-screenrec --no-hw-encode -f output.mp4

# Record audio simultaneously
wl-screenrec -f output.mp4 --audio=default

# Low-latency mode (for real-time preview/streaming scenarios)
wl-screenrec --low-power -f output.mp4

# Stop recording
pkill -INT wl-screenrec
```

| Tool | Capture Method | CPU Usage | GPU Required | Audio | Region Select |
|------|---------------|-----------|--------------|-------|---------------|
| `wf-recorder` | wlr-screencopy (CPU copy) | Medium-High | No | Yes | Yes (slurp) |
| `wl-screenrec` | DMA-BUF (zero-copy) | Low | Yes (VA-API) | Yes | Yes (slurp) |
| OBS (PipeWire) | Portal screencopy | Medium | Optional | Yes | Per-source |
| `grim` | wlr-screencopy | Low (still) | No | N/A | Yes (slurp) |

---

## 31.9 Flameshot on Wayland

Flameshot is a feature-rich screenshot tool with built-in annotation, drawing, blur, and upload capabilities. Its Wayland support has improved significantly since version 12.1 but remains portal-dependent and has some limitations compared to its X11 behavior.

```bash
# Install
sudo pacman -S flameshot
sudo apt install flameshot

# Launch GUI (annotation tool with region selection)
flameshot gui

# Full screen capture
flameshot full -p ~/Pictures

# Capture with delay (seconds)
flameshot gui --delay 3000  # 3 second delay

# Capture to clipboard directly
flameshot gui --clipboard

# Configure portal mode explicitly (required on pure Wayland)
# Set in ~/.config/flameshot/flameshot.ini:
# [General]
# usePortal=true
```

Configure `~/.config/flameshot/flameshot.ini` for Wayland:

```ini
[General]
checkForUpdates=false
contrastOpacity=188
copyAndCloseAfterUpload=true
copyPathAfterSave=false
drawColor=#ff0000
drawThickness=2
historyConfDir=/home/user/.config/flameshot/history
saveAfterCopy=false
savePath=/home/user/Pictures/Screenshots
savePathFixed=false
showHelp=false
showMagnifier=false
showStartupLaunchMessage=false
squareMagnifier=false
startupLaunch=false
uiColor=#1793d0
undoLimit=100
useJpgForClipboard=false
usePortal=true
```

---

## 31.10 Annotating Screenshots

After capturing a screenshot, annotation tools let you mark up, highlight, and share with annotations. Two tools dominate the wlroots ecosystem.

`swappy` is a lightweight annotation tool that reads from stdin or a file, presents a drawing canvas, and writes the annotated result to a file or clipboard:

```bash
# Install
sudo pacman -S swappy
sudo apt install swappy

# Capture region and immediately annotate
grim -g "$(slurp)" - | swappy -f -

# Annotate existing file
swappy -f ~/Pictures/screenshot.png

# Save annotated output to specific file
grim -g "$(slurp)" - | swappy -f - -o ~/Pictures/annotated.png

# Full pipeline: capture, annotate, copy to clipboard
grim -g "$(slurp)" /tmp/shot.png && swappy -f /tmp/shot.png -o - | wl-copy
```

Configure `~/.config/swappy/config`:

```ini
[Default]
save_dir=$HOME/Pictures/Screenshots
save_filename_format=swappy-%Y%m%d-%H%M%S.png
show_panel=true
line_size=5
text_size=20
text_font=sans-serif
paint_mode=brush
early_exit=true
fill_shape=false
```

`satty` is a modern GTK4 annotation tool with a more polished UI:

```bash
# Install
yay -S satty          # AUR
cargo install satty   # from source

# Annotate screenshot (capture first, then annotate)
grim -g "$(slurp)" /tmp/shot.png && satty --filename /tmp/shot.png

# Pipe from grim
grim -g "$(slurp)" - | satty --filename -

# Save to specific output
grim -g "$(slurp)" - | satty --filename - --output-filename ~/Pictures/annotated.png

# Copy to clipboard after annotation (close satty with save action)
# Configure default copy action in ~/.config/satty/config.toml
```

Configure `~/.config/satty/config.toml`:

```toml
[general]
early-exit = true
initial-tool = "brush"
copy-command = "wl-copy"
output-filename = "/home/user/Pictures/Screenshots/satty-%Y%m%d-%H%M%S.png"
save-after-copy = false

[color-palette]
first = "#f38ba8"
second = "#a6e3a1"
third = "#89b4fa"
fourth = "#fab387"
fifth = "#cba6f7"
```

---

## 31.11 wl-copy and Clipboard Integration

Clipboard integration is critical for a smooth screenshot workflow. `wl-copy` (from `wl-clipboard`) is the standard tool for piping image data to the Wayland clipboard.

```bash
# Install
sudo pacman -S wl-clipboard
sudo apt install wl-clipboard

# Copy PNG file to clipboard
wl-copy < screenshot.png
cat screenshot.png | wl-copy

# Copy with explicit MIME type (important for image data)
wl-copy --type image/png < screenshot.png

# Paste clipboard contents to file
wl-paste > pasted.png

# Copy text
echo "hello" | wl-copy

# Clear clipboard
wl-copy --clear

# Copy to primary selection (middle-click paste)
wl-copy --primary < screenshot.png

# Check what's in clipboard
wl-paste --list-types   # list available MIME types
wl-paste --type image/png > clipboard-image.png
```

---

## Troubleshooting

**`grim` exits with "compositor doesn't support wlr-screencopy-unstable-v1"**

Your compositor does not implement the wlroots screencopy protocol. On Hyprland, ensure you are running a recent version. On GNOME/KDE, use `gnome-screenshot`/`spectacle` instead, or use the portal path via `xdg-desktop-portal`.

```bash
# Verify protocol support
wayland-info | grep screencopy
# or
weston-info 2>/dev/null | grep screencopy
```

**OBS shows no capture sources / portal dialog never appears**

The `xdg-desktop-portal` backend is not running or is misconfigured.

```bash
# Check running services
systemctl --user status xdg-desktop-portal
systemctl --user status xdg-desktop-portal-hyprland

# Restart portals
systemctl --user restart xdg-desktop-portal-hyprland
systemctl --user restart xdg-desktop-portal

# Check for portal config (determines which backend handles which interface)
cat /usr/share/xdg-desktop-portal/hyprland-portals.conf

# Debug portal dbus traffic
G_MESSAGES_DEBUG=all /usr/lib/xdg-desktop-portal-hyprland 2>&1 | head -50
```

**slurp selection immediately exits / crosshair not visible**

This can happen when a compositor layer or fullscreen application blocks input. Ensure no fullscreen application has keyboard grab. Also check for conflicting `wl-roots` layer-shell applications covering the screen.

```bash
# Kill any stale slurp instances
pkill -x slurp

# Test slurp in isolation
slurp
```

**wf-recorder produces corrupt/incomplete files after force-kill**

Always stop wf-recorder with `SIGINT` (not `SIGKILL`):

```bash
pkill -INT wf-recorder   # correct — graceful stop, finalizes MP4
pkill -9 wf-recorder     # wrong — truncates file, breaks moov atom
kill -SIGINT $(pgrep wf-recorder)  # explicit alternative
```

If you have a corrupt file, attempt recovery with FFmpeg:

```bash
ffmpeg -i corrupted.mp4 -c copy recovered.mp4
```

**Hardware encoding fails with VA-API errors**

```bash
# Check VA-API device availability
ls /dev/dri/renderD*
vainfo --display drm --device /dev/dri/renderD128

# Ensure user is in the 'render' and 'video' groups
groups $USER
sudo usermod -aG render,video $USER
# log out and back in

# Test VA-API encoding manually
ffmpeg -vaapi_device /dev/dri/renderD128 -i input.mp4 \
    -vf format=nv12,hwupload -c:v h264_vaapi test_vaapi.mp4
```

**Screenshot keybinds not firing in Hyprland**

Check `hyprland.log` for bind parsing errors:

```bash
cat ~/.cache/hyprland/hyprland.log | grep -i "bind\|screenshot\|error"
# or live
journalctl --user -u hyprland -f
```

Ensure the script is executable:

```bash
chmod +x ~/.config/hypr/scripts/screenshot.sh
```

**wl-copy doesn't retain clipboard after script exits**

`wl-copy` forks a clipboard daemon that holds the content. If your script runs `wl-copy` and the daemon is killed by a process manager, clipboard contents are lost. Use `wl-copy --foreground` inside a persistent process, or use `cliphist` to persist clipboard history:

See Ch 32 for cliphist installation, watcher setup, and picker integration patterns.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
