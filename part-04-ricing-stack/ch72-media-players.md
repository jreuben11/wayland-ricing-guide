# Chapter 72 — Media Players: mpv, VLC, and Wayland Playback

## Overview
mpv is the media player of the ricing world — scriptable, GPU-accelerated,
Wayland-native, and used as the backend for everything from video wallpapers
to anime watching stations. This chapter covers mpv configuration and theming,
plus VLC's Wayland mode.

## Sections

### 72.1 mpv — The Ricing Standard

```bash
sudo pacman -S mpv
```

**Why mpv dominates ricing setups:**
- Native Wayland backend (no XWayland needed)
- Zero-copy DMA-BUF rendering via VA-API/VDPAU
- Scripted with Lua (mpv scripts)
- Themeable via `osc.lua` (on-screen controls)
- Used by: `mpvpaper`, `celluloid` (GUI frontend), `yazi` previews, `ueberzugpp`

### 72.2 mpv Configuration

`~/.config/mpv/mpv.conf`:
```ini
# Wayland backend
gpu-api=vulkan
gpu-context=waylandvk   # or: wayland

# Hardware video decode
hwdec=vaapi             # AMD/Intel; use nvdec for NVIDIA
hwdec-codecs=all

# Quality
profile=gpu-hq          # high quality scaling
scale=ewa_lanczossharp  # best upscaling
cscale=ewa_lanczos      # chroma scaling
video-sync=display-resample

# Subtitles
sub-font="JetBrainsMono Nerd Font"
sub-font-size=40
sub-color="#FFFFFF"
sub-border-color="#000000"
sub-border-size=2

# UI
osc=no                  # disable default OSC (use custom or modernx)
osd-font="Inter"
osd-font-size=36
keep-open=yes           # don't close after playback ends
save-position-on-quit=yes
```

### 72.3 Custom OSC Themes

**modernx** (popular replacement OSC):
```bash
mkdir -p ~/.config/mpv/scripts
wget -O ~/.config/mpv/scripts/modernx.lua \
    https://raw.githubusercontent.com/cyl0/ModernX/master/modernx.lua
```

**uosc** (feature-rich OSC with seekbar, chapters):
```bash
# Install via script-opts
# ~/.config/mpv/script-opts/uosc.conf
```

### 72.4 mpv Shaders and Upscaling

For anime (line art) upscaling with `Anime4K`:
```bash
# Download shaders
mkdir -p ~/.config/mpv/shaders
# From: github.com/bloc97/Anime4K/releases

# ~/.config/mpv/input.conf — toggle with CTRL+1/2/3
CTRL+1 no-osd change-list glsl-shaders set "~~/shaders/Anime4K_Clamp_Highlights.glsl:..."
```

For live action upscaling with `FSRCNNX`:
```ini
# mpv.conf
glsl-shaders="~~/shaders/FSRCNNX_x2_16-0-4-1.glsl"
```

### 72.5 mpv Scripts

`~/.config/mpv/scripts/`:

**autoload.lua**: automatically load playlist from directory
**mpv-cut**: cut video segments
**quality-menu**: change YouTube quality mid-playback
**mpv-sponsorblock**: skip sponsors in YouTube videos
**thumbfast**: fast thumbnail previews on seekbar hover

### 72.6 mpv as a Video Wallpaper Backend

`mpvpaper` uses mpv to display video on the wallpaper layer:
```bash
sudo pacman -S mpvpaper

# Basic use
mpvpaper DP-1 ~/Videos/wallpaper.mp4

# With mpv options
mpvpaper -o "no-audio loop panscan=1.0" DP-1 wallpaper.mp4

# autostart
exec-once = mpvpaper -o "no-audio loop" DP-1 ~/Videos/wallpaper.mp4
```

### 72.7 mpv with yt-dlp (YouTube)

```bash
sudo pacman -S yt-dlp

# Play YouTube URL
mpv "https://youtube.com/watch?v=..."

# Best quality
mpv --ytdl-format="bestvideo[height<=1080]+bestaudio" URL

# Download instead
yt-dlp URL
```

### 72.8 Celluloid — mpv GUI Frontend

Celluloid wraps mpv with a GTK4 interface for users who want a traditional media player:
```bash
sudo pacman -S celluloid
```
Full mpv config passthrough — your `mpv.conf` applies inside Celluloid.

### 72.9 VLC on Wayland

```bash
sudo pacman -S vlc
vlc --qt-wayland-decoration none  # no window decorations
```

VLC uses Qt for its UI; set `QT_QPA_PLATFORM=wayland` to run natively.
VA-API: Tools → Preferences → Input/Codecs → Hardware-accelerated decoding = VA-API.

### 72.10 MPRIS Integration with Quickshell

mpv exposes MPRIS2 via `mpv-mpris` script:
```bash
sudo pacman -S mpv-mpris
# Automatically loaded if in ~/.config/mpv/scripts/
```
Then Ch 22's `MprisPlayer` type picks it up automatically in Quickshell.
