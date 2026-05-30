# Chapter 127 — OBS Studio on Wayland: Deep Setup Guide

## Overview

OBS Studio runs natively on Wayland (Qt Wayland backend) and captures screen content via PipeWire's screencopy protocol, making it fully functional without XWayland for recording and streaming. The path from a default OBS install to a fully configured Wayland recording setup requires three configuration layers: the Qt platform backend, the PipeWire screen capture source, and (optionally) a virtual camera via `v4l2loopback`. This chapter covers all three, plus performance profiling, the obs-pipewire plugin, and a scene configuration for showcasing a riced desktop.

**Cross-references:** Ch 31 — screenshot and recording tools overview. Ch 56 — PipeWire setup (required for OBS screen capture). Ch 61 — screen sharing and xdg-desktop-portal (used by OBS PipeWire source).

---

## 127.1 Installation

```bash
# Arch Linux — OBS with PipeWire support (included in main package)
sudo pacman -S obs-studio

# Ubuntu 24.04+ — official PPA for latest version
sudo add-apt-repository ppa:obsproject/obs-studio
sudo apt install obs-studio

# Flatpak (most up to date, includes all plugins)
flatpak install flathub com.obsproject.Studio
flatpak override --user --socket=wayland com.obsproject.Studio
```

Verify PipeWire support is compiled in:
```bash
obs --version   # Should show version ≥ 30.0
# Check for PipeWire capture plugin
ls /usr/lib/obs-plugins/ | grep pipewire
# → linux-pipewire.so (or similar)
```

---

## 127.2 Running OBS on Wayland

```bash
# Native Wayland (no XWayland)
QT_QPA_PLATFORM=wayland obs

# Wayland with X11 fallback (safer for compatibility)
QT_QPA_PLATFORM=wayland;xcb obs

# Create a desktop entry override for permanent Wayland launch
mkdir -p ~/.local/share/applications
cp /usr/share/applications/com.obsproject.Studio.desktop \
   ~/.local/share/applications/
# Edit the Exec= line:
sed -i 's|^Exec=obs|Exec=env QT_QPA_PLATFORM=wayland obs|' \
    ~/.local/share/applications/com.obsproject.Studio.desktop
```

For the Flatpak version:
```bash
flatpak override --user \
    --env=QT_QPA_PLATFORM=wayland \
    com.obsproject.Studio
```

---

## 127.3 PipeWire Screen Capture Source

OBS on Wayland uses the PipeWire Screen Capture source (not the Display Capture or Window Capture sources, which require X11).

### Adding the Source

1. In OBS: **Sources → Add → Screen Capture (PipeWire)**
2. Click **Create New**
3. A portal dialog appears (from `xdg-desktop-portal`) — select the output or window to capture
4. Click **Share** in the portal dialog
5. The source now shows the selected screen/window

The portal dialog is provided by your compositor's desktop portal backend:
- Hyprland: `xdg-desktop-portal-hyprland`
- Sway: `xdg-desktop-portal-wlr`
- GNOME: `xdg-desktop-portal-gnome`

### Troubleshooting the Portal

```bash
# Verify portal is running
systemctl --user status xdg-desktop-portal
systemctl --user status xdg-desktop-portal-hyprland   # or -wlr, -gnome

# Check portal responds to ScreenCast requests
busctl --user introspect org.freedesktop.portal.Desktop \
    /org/freedesktop/portal/desktop \
    org.freedesktop.impl.portal.ScreenCast

# Restart portal if needed
systemctl --user restart xdg-desktop-portal xdg-desktop-portal-hyprland
```

### obs-pipewire: Alternative Capture Plugin

The `obs-pipewire` plugin provides finer-grained PipeWire node selection (choose specific PipeWire nodes by name, useful for window capture):

```bash
# Arch AUR
yay -S obs-pipewire-audio-capture

# GitHub: https://github.com/dimtpap/obs-pipewire-audio-capture
# Also handles PipeWire audio sources in OBS
```

---

## 127.4 Audio Configuration

OBS on Wayland captures audio via PipeWire's JACK or ALSA compatibility layers:

```bash
# In OBS: Settings → Audio → Devices
# Desktop Audio: use "default" (routes through PipeWire)
# Mic/Auxiliary Audio: select your microphone device

# Check PipeWire is presenting ALSA devices to OBS
pw-cli list-objects | grep "alsa"

# If OBS can't find audio devices, restart PipeWire ALSA bridge
systemctl --user restart pipewire-pulse
```

For capturing individual application audio (e.g., only the game, not system sounds), use PipeWire virtual nodes:

```bash
# Create a virtual audio sink for the game
pactl load-module module-null-sink \
    sink_name=game-audio \
    sink_properties=device.description="Game Audio"

# In OBS: add Audio Input Capture → select "game-audio.monitor"
# In game: set audio output to "Game Audio" sink
```

---

## 127.5 Virtual Camera (v4l2loopback)

The virtual camera feature in OBS creates a `/dev/video*` device that other apps (Zoom, Teams, browsers) can use as a webcam source, showing your OBS scene.

### Setup

```bash
# Install v4l2loopback kernel module
sudo pacman -S v4l2loopback-dkms   # Arch
sudo apt install v4l2loopback-dkms  # Ubuntu

# Load the module
sudo modprobe v4l2loopback \
    devices=1 \
    video_nr=10 \
    card_label="OBS Virtual Camera" \
    exclusive_caps=1

# Make it persistent
echo "v4l2loopback" | sudo tee /etc/modules-load.d/v4l2loopback.conf
echo 'options v4l2loopback devices=1 video_nr=10 card_label="OBS Virtual Camera" exclusive_caps=1' \
    | sudo tee /etc/modprobe.d/v4l2loopback.conf

# Verify
ls /dev/video*   # /dev/video10 should appear
```

### Using the Virtual Camera

1. In OBS: **Tools → Start Virtual Camera**
2. In Zoom/Teams/browser: select "OBS Virtual Camera" as webcam
3. The video call sees your OBS scene (with all its sources, filters, and effects)

### udev Rule for Non-root Access (Flatpak)

```
# /etc/udev/rules.d/99-v4l2loopback.rules
KERNEL=="video[0-9]*", SUBSYSTEM=="video4linux", \
    ATTR{index}=="0", GROUP="video", MODE="0666"
```

```bash
sudo usermod -aG video $USER
sudo udevadm control --reload-rules
```

---

## 127.6 Performance Profiling and Settings

### Encoder Selection

```
OBS Settings → Output → Recording
  Encoder: FFMPEG VAAPI (AMD/Intel GPU) or NVENC (NVIDIA)
  Rate Control: CQP (constant quality) for recording
  CQ Level: 18–23 (lower = higher quality, larger file)
```

```bash
# Verify GPU encoder is available
vainfo | grep -i encode   # AMD/Intel: VAAPI
nvidia-smi | grep NVENC   # NVIDIA
```

### CPU Usage Reduction

```
Settings → Output → Recording
  Encoder: GPU (VAAPI/NVENC) — offloads from CPU
  
Settings → Video
  Base (Canvas) Resolution: 1920×1080
  Output (Scaled) Resolution: 1920×1080 (no scaling)
  FPS: 60 (match monitor refresh)

Settings → Advanced
  Process Priority: High (may need to run OBS as nice -n -5)
```

### Frame Drop Debugging

```bash
# Check OBS stats (View → Stats in OBS)
# or watch via the OBS WebSocket API:
# obs-websocket-py or obs-cli

# If frames drop: check GPU usage
radeontop         # AMD
nvidia-smi dmon   # NVIDIA
intel_gpu_top     # Intel
```

---

## 127.7 Scene for Desktop Showcase (Rice Screenshot)

A scene layout for recording a polished desktop showcase:

```
Scene: "Rice Showcase"
├── Source: Screen Capture (PipeWire) — full desktop
├── Source: Audio Output Capture (cava output or music)
└── Filter: Color Correction (slight saturation boost)

Scene: "Code Session"  
├── Source: Window Capture — terminal (foot/kitty)
├── Source: Window Capture — editor (neovim/helix)
├── Source: Audio Input — microphone (with noise suppression filter)
└── Transition: Fade (500ms)

Scene: "Floating"
├── Source: Screen Capture — main monitor
├── Filter: Crop/Pad — remove borders
└── Filter: Color Grade — match aesthetic palette
```

### Adding Filters

OBS filters for ricing aesthetics:
- **Color Correction**: boost saturation 10–15% to make colors "pop" in recordings
- **Sharpen**: 0.05–0.10 for crisp text in recordings
- **LUT** (Lookup Table): apply a DaVinci-style color grade matching your aesthetic

```bash
# Find free LUTs matching your aesthetic
# "Tokyo Night LUT", "Cyberpunk LUT", "Moody Film LUT"
# Place in ~/Documents/obs-luts/ and add as LUT filter
```

---

## 127.8 Streaming Configuration

```
Settings → Stream
  Service: Twitch (or Custom RTMP)
  Server: auto (or nearest region)
  Stream Key: [from dashboard]

Settings → Output → Streaming
  Encoder: FFMPEG VAAPI / NVENC (GPU)
  Bitrate: 6000 kbps (1080p60) / 4500 kbps (1080p30)
  Rate Control: CBR
  Keyframe Interval: 2s
```

Twitch, YouTube, and Kick all accept RTMP streams from OBS on Wayland without modification.

---

## 127.9 Troubleshooting

### Black screen in Screen Capture source

The portal negotiation failed. Reset:
```bash
systemctl --user restart xdg-desktop-portal xdg-desktop-portal-hyprland
# Re-add the Screen Capture source in OBS (the portal token must be refreshed)
```

### OBS crashes on startup with Wayland

Try the X11 fallback to isolate:
```bash
QT_QPA_PLATFORM=xcb obs
```
If that works, install missing Wayland Qt plugins:
```bash
sudo pacman -S qt6-wayland
```

### Virtual camera not appearing in browsers

Chromium requires an extra flag:
```bash
chromium --use-fake-ui-for-media-stream
# or in flags: chrome://flags/ → enable "Virtual Camera"
```

Firefox recognizes `/dev/video10` automatically if `v4l2loopback` is loaded with `exclusive_caps=1`.
