# Chapter 72 — Media Players: mpv, VLC, and Wayland Playback

## Contents

- [Overview](#overview)
- [Why mpv Dominates Ricing Setups](#why-mpv-dominates-ricing-setups)
- [Sections](#sections)
  - [72.1 mpv — The Ricing Standard](#721-mpv-the-ricing-standard)
  - [72.2 mpv Configuration](#722-mpv-configuration)
  - [72.3 Custom OSC Themes](#723-custom-osc-themes)
  - [72.4 mpv Shaders and Upscaling](#724-mpv-shaders-and-upscaling)
  - [72.5 mpv Scripts](#725-mpv-scripts)
  - [72.6 mpv IPC and External Control](#726-mpv-ipc-and-external-control)
  - [72.7 mpv as a Video Wallpaper Backend](#727-mpv-as-a-video-wallpaper-backend)
  - [72.8 mpv with yt-dlp (YouTube and Streaming)](#728-mpv-with-yt-dlp-youtube-and-streaming)
  - [72.9 Celluloid — mpv GUI Frontend](#729-celluloid-mpv-gui-frontend)
  - [72.10 VLC on Wayland](#7210-vlc-on-wayland)
  - [72.11 MPRIS Integration with Status Bars](#7211-mpris-integration-with-status-bars)
  - [72.12 Audio-Only Playback and Music Integration](#7212-audio-only-playback-and-music-integration)
- [Troubleshooting](#troubleshooting)
  - [mpv opens on the wrong monitor / wrong scale](#mpv-opens-on-the-wrong-monitor-wrong-scale)
  - [Black screen / no video with VA-API](#black-screen-no-video-with-va-api)
  - [mpv crashes with Vulkan / waylandvk](#mpv-crashes-with-vulkan-waylandvk)
  - [VLC does not start on Wayland (crashes at launch)](#vlc-does-not-start-on-wayland-crashes-at-launch)
  - [mpvpaper causes compositor lag](#mpvpaper-causes-compositor-lag)
  - [MPRIS2 / playerctl not showing mpv](#mpris2-playerctl-not-showing-mpv)
  - [yt-dlp not finding videos / format errors](#yt-dlp-not-finding-videos-format-errors)
- [Cross-References](#cross-references)

---


## Overview

mpv is the media player of the ricing world — scriptable, GPU-accelerated,
Wayland-native, and used as the backend for everything from video wallpapers
to anime watching stations. This chapter covers mpv configuration and theming,
hardware video decoding, shader pipelines, Lua scripting, VLC's Wayland mode,
and MPRIS2 integration for status bars. By the end of this chapter you will have
a fully tuned, aesthetically coherent media playback stack that integrates
cleanly with Hyprland, Niri, or any other Wayland compositor.

This chapter assumes you have a functioning Wayland session, a working GPU
driver stack (Mesa for AMD/Intel, or the proprietary NVIDIA driver with GBM
support for NVIDIA), and a compositor-specific configuration directory already
in place. See Ch 5 for GPU driver setup, Ch 10 for Hyprland configuration
basics, and Ch 53 for session startup and autostart configuration.

## Why mpv Dominates Ricing Setups

mpv occupies a unique niche: it is simultaneously a minimal command-line tool
and an infinitely extensible platform. Unlike VLC or SMPlayer, mpv has no
permanent GUI of its own; its on-screen controls are rendered by Lua scripts
that you can replace entirely. Every frame of video passes through a
configurable shader pipeline. Every keybind, every OSD element, every decode
path is user-controlled.

On Wayland specifically, mpv's advantage is its zero-copy rendering path. When
VA-API or NVDEC decodes a frame directly to GPU memory, mpv can hand that
frame buffer to the compositor via DMA-BUF without a round-trip through CPU
memory. The result is lower latency, lower power consumption, and no tearing
even without VSync tricks. XWayland players like the classic MPlayer fork
cannot achieve this without significant patching.

The scripting ecosystem amplifies mpv's utility beyond playback. `mpvpaper`
turns mpv into a live video wallpaper engine. `ueberzugpp` uses mpv as a
video preview renderer inside terminal file managers. `ytdl-hook` (bundled)
and quality-menu scripts turn mpv into a full YouTube client. Thumbfast
provides near-instant seekbar thumbnails. These integrations depend on mpv's
internal IPC socket — a Unix domain socket that accepts JSON commands while
mpv is running.

| Feature | mpv | VLC | Celluloid |
|---|---|---|---|
| Wayland-native | Yes (waylandvk) | Yes (Qt Wayland) | Via mpv |
| DMA-BUF zero-copy | Yes | No | Via mpv |
| Lua scripting | Yes | No | No |
| GLSL shader pipeline | Yes | No | Via mpv |
| MPRIS2 | Via script | Yes | Via mpv |
| GUI | OSC only | Full Qt GUI | GTK4 |
| CLI playback control | Full | Limited | No |
| Video wallpaper | Via mpvpaper | No | No |

## Sections

### 72.1 mpv — The Ricing Standard

Install mpv from your distribution's package manager. On Arch-based systems
the `mpv` package in the official repositories is built with Vulkan, VA-API,
and Wayland support. On Debian/Ubuntu, the distro package may lag behind; use
the `mpv-build` AUR-equivalent or a PPA for a recent build.

```bash
# Arch / Manjaro / EndeavourOS
sudo pacman -S mpv yt-dlp

# Fedora
sudo dnf install mpv yt-dlp

# Ubuntu (via PPA for recent build)
sudo add-apt-repository ppa:mc3man/mpv-tests
sudo apt update
sudo apt install mpv yt-dlp

# NixOS — in configuration.nix or home.nix
programs.mpv.enable = true;
```

Verify the build includes the backends you need before relying on hardware
decode. The `--version` flag lists compiled features; the `--vo=help` flag
lists available video output drivers:

```bash
mpv --version | grep -E "Vulkan|Wayland|VA-API|VDPAU"
mpv --vo=help
# Look for: gpu, gpu-next, wlshm, vaapi

# Test Wayland rendering immediately (no config needed)
mpv --vo=gpu --gpu-context=waylandvk /path/to/test.mkv
```

**Why mpv dominates ricing setups:**
- Native Wayland backend (no XWayland needed)
- Zero-copy DMA-BUF rendering via VA-API/VDPAU
- Scripted with Lua (mpv scripts)
- Themeable via `osc.lua` (on-screen controls)
- Used by: `mpvpaper`, `celluloid` (GUI frontend), `yazi` previews, `ueberzugpp`

### 72.2 mpv Configuration

mpv reads its primary configuration from `~/.config/mpv/mpv.conf`. Every
command-line option mpv accepts can appear in this file without the leading
`--`. The file is read top to bottom; later lines override earlier ones. The
`~~/` path prefix resolves to `~/.config/mpv/` and is used in glsl-shaders
references.

Profile stacking is one of the most powerful features of mpv's config system.
You can define named profiles and apply them conditionally (by file extension,
by resolution, or manually). The built-in `gpu-hq` profile enables
high-quality scaling presets. Custom `protocol.http` and `protocol.ytdl`
profiles allow different settings for streaming versus local files.

`~/.config/mpv/mpv.conf`:
```ini
# ── Wayland backend ─────────────────────────────────────────────────────────
vo=gpu-next                  # newer rendering backend (replaces "gpu")
gpu-api=vulkan               # Vulkan > OpenGL on modern hardware
gpu-context=waylandvk        # Wayland + Vulkan; use "wayland" for OpenGL

# ── Hardware video decode ────────────────────────────────────────────────────
hwdec=vaapi                  # AMD/Intel iGPU/dGPU; use "nvdec" for NVIDIA
hwdec-codecs=all             # hw-decode every codec the driver supports

# On NVIDIA with proprietary driver:
# hwdec=nvdec
# gpu-api=opengl             # Vulkan on NVIDIA can have issues; OpenGL safer

# ── Quality preset ───────────────────────────────────────────────────────────
profile=gpu-hq               # activates several high-quality scaling options
scale=ewa_lanczossharp       # best upscaling for live action
cscale=ewa_lanczos           # chroma upscaling
dscale=mitchell              # downscaling
video-sync=display-resample  # resample audio to match display refresh rate
interpolation=yes            # motion interpolation (smoother 24fps content)
tscale=oversample            # temporal interpolation method

# ── Deband ───────────────────────────────────────────────────────────────────
deband=yes                   # removes banding in gradients (streaming content)
deband-iterations=4
deband-threshold=48
deband-range=16
deband-grain=48

# ── Subtitle rendering ───────────────────────────────────────────────────────
sub-auto=fuzzy               # load subtitles with similar filename
sub-font="JetBrainsMono Nerd Font"
sub-font-size=40
sub-color="#FFFFFF"
sub-border-color="#000000"
sub-border-size=2
sub-shadow-offset=1
sub-shadow-color="#000000"

# ── OSD ──────────────────────────────────────────────────────────────────────
osc=no                       # disable default OSC (replaced by uosc or modernx)
osd-font="Inter"
osd-font-size=36
osd-color="#FFFFFF"
osd-border-color="#000000"
osd-border-size=2

# ── Behaviour ────────────────────────────────────────────────────────────────
keep-open=yes                # pause at end instead of closing
save-position-on-quit=yes    # remember playback position
resume-playback=yes
autofit-larger=90%x90%       # never exceed 90% of screen
force-window=yes             # open window even for audio-only files
audio-file-auto=fuzzy        # load audio tracks with similar filenames

# ── Streaming (yt-dlp) ───────────────────────────────────────────────────────
[protocol.http]
hls-bitrate=max              # highest bitrate HLS stream
cache=yes
demuxer-max-bytes=150MiB
demuxer-max-back-bytes=75MiB

[protocol.ytdl]
ytdl-format=bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]
```

The `[protocol.http]` and `[protocol.ytdl]` blocks at the bottom are
conditional profiles that activate only when mpv opens an HTTP or yt-dlp URL.
This prevents the large demuxer cache from wasting memory during local
playback.

### 72.3 Custom OSC Themes

mpv's built-in OSC (`osc.lua`) is functional but visually minimal. The ricing
community has produced several drop-in replacements. The two most popular are
`modernx` (a flat, translucent bar with chapter markers) and `uosc` (a
feature-complete OSC with context menus, chapter navigation, and playlist
management). Both are installed by dropping a single Lua file into
`~/.config/mpv/scripts/`.

`script-opts/` files configure each script. mpv loads `script-opts/<script-name>.conf`
automatically when the script starts. You do not need to reference the
configuration file in `mpv.conf`; naming alone provides the connection.

**modernx** (popular replacement OSC):
```bash
mkdir -p ~/.config/mpv/scripts ~/.config/mpv/script-opts
wget -O ~/.config/mpv/scripts/modernx.lua \
    https://raw.githubusercontent.com/cyl0/ModernX/master/modernx.lua
```

`~/.config/mpv/script-opts/modernx.conf`:
```ini
# modernx visual configuration
font=Inter
fontsize=14
osc_color=#000000
seekbarfg_color=#89B4FA      # Catppuccin Mocha Blue
seekbarbg_color=#313244
seekbarcache_color=#6C7086
titlestyle=scroll            # scroll long filenames
showwindowed=yes
showfullscreen=yes
showtitle=yes
hidetimeout=2000
fadeduration=200
```

**uosc** (feature-rich OSC with seekbar, chapters, context menus):
```bash
# Install uosc
mkdir -p ~/.config/mpv/scripts ~/.config/mpv/script-opts
curl -fsSL https://github.com/tomasklaen/uosc/releases/latest/download/uosc.zip \
    -o /tmp/uosc.zip
unzip -o /tmp/uosc.zip -d ~/.config/mpv/
```

`~/.config/mpv/script-opts/uosc.conf`:
```ini
timeline_size=40
timeline_persistency=paused,audio
controls=menu,gap,subtitles,<has_many_audio_tracks>audio,<has_many_video_tracks>video,gap,speed,gap,<stream>stream-quality,gap,prev,items,next
progress=windowed
color=foreground=ffffff,background=000000,foreground_text=000000,background_text=ffffff
font_bold=no
refine=text_width
top_bar=no-border
top_bar_controls=no
top_bar_title=no
```

Note that `osc=no` must be set in `mpv.conf` for both modernx and uosc to
work correctly. The default `osc.lua` and any replacement OSC will conflict if
both are active simultaneously.

### 72.4 mpv Shaders and Upscaling

mpv's GLSL shader system is one of its most powerful features. The
`glsl-shaders` option accepts a colon-separated list of `.glsl` files that are
applied as post-processing passes to each decoded frame. This enables
neural-network upscaling, sharpening, denoising, and color grading entirely on
the GPU.

The two dominant shader packs are **Anime4K** (neural upscaling optimized for
animated line art) and **FSRCNNX** (convolutional neural network for
photographic content). Both run on the GPU and require a reasonably powerful
discrete GPU for real-time 1080p playback; on integrated graphics you may need
to use lighter presets.

**Anime4K installation:**
```bash
mkdir -p ~/.config/mpv/shaders
# Download from: https://github.com/bloc97/Anime4K/releases
# Extract the .glsl files into ~/.config/mpv/shaders/
# Example with wget (check release page for current URL):
wget -P ~/.config/mpv/shaders/ \
    https://github.com/bloc97/Anime4K/releases/latest/download/Anime4K_v4.0.zip
cd /tmp && unzip ~/.config/mpv/shaders/Anime4K_v4.0.zip
cp /tmp/Anime4K_v4.0/*.glsl ~/.config/mpv/shaders/
```

`~/.config/mpv/input.conf` — toggle Anime4K presets with keybinds:
```ini
# Anime4K: toggle presets (Mode A = fast, Mode C = quality)
CTRL+1 no-osd change-list glsl-shaders set "~~/shaders/Anime4K_Clamp_Highlights.glsl:~~/shaders/Anime4K_Restore_CNN_M.glsl:~~/shaders/Anime4K_Upscale_CNN_x2_M.glsl:~~/shaders/Anime4K_AutoDownscalePre_x2.glsl:~~/shaders/Anime4K_AutoDownscalePre_x4.glsl:~~/shaders/Anime4K_Upscale_CNN_x2_S.glsl"; show-text "Anime4K: Mode A (Fast)"
CTRL+2 no-osd change-list glsl-shaders set "~~/shaders/Anime4K_Clamp_Highlights.glsl:~~/shaders/Anime4K_Restore_CNN_Soft_M.glsl:~~/shaders/Anime4K_Upscale_CNN_x2_M.glsl:~~/shaders/Anime4K_AutoDownscalePre_x2.glsl:~~/shaders/Anime4K_AutoDownscalePre_x4.glsl:~~/shaders/Anime4K_Upscale_CNN_x2_S.glsl"; show-text "Anime4K: Mode B (Balanced)"
CTRL+3 no-osd change-list glsl-shaders set "~~/shaders/Anime4K_Clamp_Highlights.glsl:~~/shaders/Anime4K_Upscale_Denoise_CNN_x2_M.glsl:~~/shaders/Anime4K_AutoDownscalePre_x2.glsl:~~/shaders/Anime4K_AutoDownscalePre_x4.glsl:~~/shaders/Anime4K_Upscale_CNN_x2_S.glsl"; show-text "Anime4K: Mode C (Quality)"
CTRL+0 no-osd change-list glsl-shaders clr ""; show-text "Shaders cleared"
```

**FSRCNNX for live-action upscaling:**
```bash
# Download FSRCNNX from: https://github.com/igv/FSRCNN-TensorFlow/releases
wget -P ~/.config/mpv/shaders/ \
    https://github.com/igv/FSRCNN-TensorFlow/releases/latest/download/FSRCNNX_x2_16-0-4-1.glsl
```

`~/.config/mpv/mpv.conf` — apply FSRCNNX for all non-anime content:
```ini
# In a separate profile activated manually or by file type:
[live-action-hq]
glsl-shaders="~~/shaders/FSRCNNX_x2_16-0-4-1.glsl"
scale=ewa_lanczos            # must not use ewa_lanczossharp with FSRCNNX
```

Activate the profile manually: `mpv --profile=live-action-hq video.mkv`

You can also add **SSimDownscaler** and **KrigBilateral** for improved
downscaling and chroma reconstruction respectively. These are lightweight and
can safely be left on permanently:

```ini
# In mpv.conf (always-on)
glsl-shaders-append="~~/shaders/SSimDownscaler.glsl"
glsl-shaders-append="~~/shaders/KrigBilateral.glsl"
```

Download both from the `mpv-wiki-user-shaders` repository on GitHub.

### 72.5 mpv Scripts

mpv's Lua scripting API exposes every internal state variable, every playback
event, and the IPC socket. Scripts placed in `~/.config/mpv/scripts/` are
loaded automatically at startup. Scripts communicate with mpv via the `mp`
module and with each other via shared properties.

`~/.config/mpv/scripts/` — recommended scripts:

| Script | Purpose | Install |
|---|---|---|
| `autoload.lua` | Auto-populate playlist from directory | bundled (copy from source) |
| `thumbfast.lua` | Instant seekbar thumbnails | GitHub: po5/thumbfast |
| `quality-menu.lua` | Change YT quality mid-stream | GitHub: christoph-heinrich/mpv-quality-menu |
| `mpv-sponsorblock` | Skip sponsors in YouTube videos | GitHub: po5/mpv-sponsorblock |
| `mpv-cut` | Trim video segments to new files | GitHub: familyfriendlymikey/mpv-cut |
| `reload.lua` | Reload stream on stall | AUR: mpv-reload |
| `mpv-webm` | Export WebM clips in-player | GitHub: ekisu/mpv-webm |

**thumbfast installation and configuration:**
```bash
wget -O ~/.config/mpv/scripts/thumbfast.lua \
    https://raw.githubusercontent.com/po5/thumbfast/master/thumbfast.lua
```

`~/.config/mpv/script-opts/thumbfast.conf`:
```ini
socket=/tmp/thumbfast        # IPC socket for thumbnail requests
spawn_first=yes              # generate thumbnails immediately on file open
max_height=200               # max thumbnail height in pixels
max_width=200
```

**mpv-sponsorblock configuration:**
```bash
wget -O ~/.config/mpv/scripts/sponsorblock.lua \
    https://raw.githubusercontent.com/po5/mpv-sponsorblock/master/sponsorblock.lua
wget -O ~/.config/mpv/scripts/sponsorblock_shared \
    https://raw.githubusercontent.com/po5/mpv-sponsorblock/master/sponsorblock_shared.lua
```

`~/.config/mpv/script-opts/sponsorblock.conf`:
```ini
# Skip categories (comma-separated)
categories=sponsor,selfpromo,interaction
skip=yes
```

**autoload.lua** (load all files in the same directory into the playlist):
```bash
# Copy from mpv source tree or GitHub
wget -O ~/.config/mpv/scripts/autoload.lua \
    https://raw.githubusercontent.com/mpv-player/mpv/master/TOOLS/lua/autoload.lua
```

`~/.config/mpv/script-opts/autoload.conf`:
```ini
disabled=no
images=no                    # don't load images into video playlist
videos=yes
audio=yes
ignore_hidden=yes
```

### 72.6 mpv IPC and External Control

mpv's IPC socket enables external programs to query state and send commands
while mpv is running. This is the mechanism used by status bars (via
mpv-mpris), by thumbfast, and by quality-menu. You can also use it directly
from shell scripts.

Enable the IPC socket globally in `mpv.conf`:
```ini
input-ipc-server=/tmp/mpvsocket
```

Or pass it per-invocation:
```bash
mpv --input-ipc-server=/tmp/mpvsocket video.mkv
```

Communicate with the socket using `socat` or `nc`:
```bash
# Get current playback position
echo '{ "command": ["get_property", "time-pos"] }' | socat - /tmp/mpvsocket

# Pause/unpause
echo '{ "command": ["cycle", "pause"] }' | socat - /tmp/mpvsocket

# Seek forward 30 seconds
echo '{ "command": ["seek", 30] }' | socat - /tmp/mpvsocket

# Get current filename
echo '{ "command": ["get_property", "filename"] }' | socat - /tmp/mpvsocket

# Set volume
echo '{ "command": ["set_property", "volume", 80] }' | socat - /tmp/mpvsocket
```

A minimal shell wrapper for common operations:
```bash
#!/usr/bin/env bash
# ~/.local/bin/mpvctl
SOCKET=/tmp/mpvsocket
cmd() { echo "{ \"command\": $* }" | socat - "$SOCKET" 2>/dev/null; }

case "$1" in
    pause)   cmd '["cycle", "pause"]' ;;
    next)    cmd '["playlist-next"]' ;;
    prev)    cmd '["playlist-prev"]' ;;
    vol+)    cmd '["add", "volume", 5]' ;;
    vol-)    cmd '["add", "volume", -5]' ;;
    status)  cmd '["get_property", "filename"]' | jq -r '.data' ;;
    *)       echo "Usage: mpvctl pause|next|prev|vol+|vol-|status" ;;
esac
```

### 72.7 mpv as a Video Wallpaper Backend

`mpvpaper` is a Wayland layer-surface application that uses libmpv to render
video directly to the desktop background layer. It supports all mpv options,
hardware decoding, and multiple monitors. Unlike `swaybg` or `hyprpaper` it
can play any media format mpv supports, including looping GIFs and live
streams.

```bash
sudo pacman -S mpvpaper

# Basic use (single monitor)
mpvpaper DP-1 ~/Videos/wallpaper.mp4

# Auto-detect all outputs
mpvpaper '*' ~/Videos/wallpaper.mp4

# With mpv options: no audio, loop, fill screen
mpvpaper -o "no-audio loop panscan=1.0" DP-1 ~/Videos/wallpaper.mp4

# Hardware decode (VA-API) for low power usage
mpvpaper -o "no-audio loop hwdec=vaapi panscan=1.0" DP-1 ~/Videos/wallpaper.mp4

# Pause when window is fullscreen (saves GPU)
mpvpaper -p -o "no-audio loop" DP-1 ~/Videos/wallpaper.mp4
```

The `-p` flag tells mpvpaper to pause when any window is fullscreen. This is
strongly recommended for battery-powered systems and for any setup where you
play full-screen video, as otherwise mpvpaper and your video player compete for
the same GPU resources.

**Hyprland autostart** (in `hyprland.conf`):
```ini
# See Ch 53 for session startup configuration
exec-once = mpvpaper -p -o "no-audio loop hwdec=vaapi panscan=1.0" '*' ~/Videos/wallpaper.mp4
```

**Rotating wallpapers with a shell script:**
```bash
#!/usr/bin/env bash
# ~/.local/bin/wallpaper-daemon
WALLPAPER_DIR=~/Pictures/Wallpapers/video
INTERVAL=300  # rotate every 5 minutes

while true; do
    VIDEO=$(find "$WALLPAPER_DIR" -type f \( -name "*.mp4" -o -name "*.webm" \) | shuf -n1)
    pkill -f mpvpaper
    mpvpaper -p -o "no-audio loop hwdec=vaapi panscan=1.0" '*' "$VIDEO" &
    sleep "$INTERVAL"
done
```

For still images as wallpaper, use `hyprpaper` (see Ch 71) or `swaybg`.
mpvpaper is specifically for animated/video backgrounds.

### 72.8 mpv with yt-dlp (YouTube and Streaming)

yt-dlp is the actively maintained fork of youtube-dl. mpv bundles a `ytdl-hook`
script that calls yt-dlp transparently whenever a URL is passed as the filename.
You do not need to manually invoke yt-dlp for playback; only for downloading.

```bash
sudo pacman -S yt-dlp

# Play any YouTube/Twitch/Bilibili/etc URL directly
mpv "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Force best 1080p quality (overrides mpv.conf profile)
mpv --ytdl-format="bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]" URL

# Play audio-only (podcast, music)
mpv --no-video URL

# Download instead of playing (yt-dlp directly)
yt-dlp --format "bestvideo[height<=1080]+bestaudio" URL

# Download with embedded thumbnail and metadata
yt-dlp --embed-thumbnail --embed-metadata --format "bestvideo+bestaudio" URL

# Download entire playlist
yt-dlp --yes-playlist --format best URL

# Download subtitles
yt-dlp --write-sub --sub-lang en URL
```

The `quality-menu` script allows changing the stream quality interactively
without restarting playback. After installing, press `f` during YouTube
playback to open the quality selection menu in the OSD:

```bash
wget -O ~/.config/mpv/scripts/quality-menu.lua \
    https://raw.githubusercontent.com/christoph-heinrich/mpv-quality-menu/master/quality-menu.lua
```

`~/.config/mpv/script-opts/quality-menu.conf`:
```ini
# Default format string (mirrors ytdl-format in mpv.conf)
ytdl_format_default=bestvideo[height<=1080]+bestaudio/best
# Available quality levels shown in menu
formats=4320,2160,1440,1080,720,480,360
```

For Twitch streams, use `streamlink` as an intermediary to handle
authentication and quality selection, then pipe the stream URL to mpv:

```bash
# Install streamlink
sudo pacman -S streamlink

# Play Twitch stream at best quality via mpv
streamlink --player mpv twitch.tv/channelname best

# With mpv options passthrough
streamlink --player "mpv --no-border" --player-continuous-http \
    twitch.tv/channelname best
```

### 72.9 Celluloid — mpv GUI Frontend

Celluloid (formerly GNOME MPV) wraps libmpv with a GTK4 interface following
the GNOME Human Interface Guidelines. It provides a traditional media player
experience — drag-and-drop, file-picker menus, a visible playlist sidebar —
while passing all rendering through the underlying mpv engine. Your
`~/.config/mpv/mpv.conf` applies inside Celluloid without any extra
configuration.

```bash
sudo pacman -S celluloid
```

Celluloid respects the XDG portal stack for file picking, making it integrate
cleanly with Wayland portals. Run with `GDK_BACKEND=wayland` to ensure it does
not fall back to XWayland:

```bash
GDK_BACKEND=wayland celluloid
```

For a persistent launch alias:
```bash
# ~/.local/bin/celluloid-wayland
#!/usr/bin/env bash
exec env GDK_BACKEND=wayland celluloid "$@"
```

Celluloid's preferences expose most common mpv options through a GUI. For
advanced configuration, use the "Extra mpv options" field in Preferences, which
accepts any `mpv.conf` syntax. All mpv scripts in `~/.config/mpv/scripts/` load
automatically, including uosc — though uosc's context menus may conflict with
Celluloid's own menus.

Full mpv config passthrough — your `mpv.conf` applies inside Celluloid.

### 72.10 VLC on Wayland

VLC 3.x and later support native Wayland rendering via the Qt Wayland platform
plugin. Setting `QT_QPA_PLATFORM=wayland` forces VLC to use the Wayland
backend instead of XWayland. On most Wayland compositors this happens
automatically if `WAYLAND_DISPLAY` is set and `QT_QPA_PLATFORM` is not
overridden.

```bash
sudo pacman -S vlc

# Force Wayland backend
QT_QPA_PLATFORM=wayland vlc

# Disable Qt window decorations (use compositor decorations)
vlc --qt-wayland-decoration none

# Both together — typical ricing invocation
QT_QPA_PLATFORM=wayland vlc --qt-wayland-decoration none

# For a desktop entry, edit /usr/share/applications/vlc.desktop or create:
# ~/.local/share/applications/vlc.desktop
```

`~/.local/share/applications/vlc.desktop`:
```ini
[Desktop Entry]
Name=VLC media player
Exec=env QT_QPA_PLATFORM=wayland vlc --qt-wayland-decoration none %U
Icon=vlc
Type=Application
Categories=AudioVideo;Player;Recorder;
MimeType=video/mpeg;video/x-mpeg;audio/mpeg;...
```

**VA-API hardware decoding in VLC:**
Tools → Preferences → Show settings: All → Input/Codecs → Hardware-accelerated
decoding → VA-API (for AMD/Intel) or NVDEC (for NVIDIA). On a CLI-only system:

```bash
# VLC config file: ~/.config/vlc/vlcrc
# Find and set:
# avcodec-hw=vaapi
```

Or pass it on the command line:
```bash
vlc --avcodec-hw=vaapi video.mkv
```

VLC's theming support on Wayland is limited compared to mpv. The Qt interface
theme follows the system Qt theme (see Ch 68 for Qt theming with Kvantum). For
a fully custom look, mpv with a custom OSC is the superior choice. VLC's main
advantage is its broader codec support out of the box and its built-in
streaming server (`cvlc --sout`), making it useful for network streaming tasks
that mpv does not natively support.

| Capability | mpv | VLC |
|---|---|---|
| Custom OSC/UI | Full (Lua) | Qt theme only |
| GLSL shaders | Yes | No |
| Lua scripting | Yes | No (LuaIntf limited) |
| Built-in streaming server | No | Yes |
| Codec support out of box | Broad | Broadest |
| DVD/Blu-ray menus | No | Yes |
| MPRIS2 | Via script | Native |
| Wayland native | waylandvk | Qt Wayland |

### 72.11 MPRIS Integration with Status Bars

MPRIS2 (Media Player Remote Interfacing Specification version 2) is the
D-Bus interface standard for media player control. Status bars (Waybar,
Quickshell, AGS, Eww) query MPRIS2 to display the currently playing track
and provide playback controls. Most audio players implement MPRIS2 natively;
mpv requires an additional script.

**mpv-mpris installation:**
```bash
sudo pacman -S mpv-mpris
# The package installs mpv-mpris.so to /usr/lib/mpv/
# mpv auto-loads .so scripts from that directory at startup
# No further configuration needed
```

Alternatively, install as a Lua script for systems where the C extension is
unavailable:
```bash
wget -O ~/.config/mpv/scripts/mpris.lua \
    https://raw.githubusercontent.com/hoyon/mpv-mpris/master/mpris.lua
```

Verify MPRIS2 is working with `playerctl`:
```bash
sudo pacman -S playerctl

# List all MPRIS2 players
playerctl --list-all

# Control mpv via MPRIS2
playerctl --player=mpv play-pause
playerctl --player=mpv next
playerctl --player=mpv volume 0.8

# Get current track info
playerctl --player=mpv metadata
playerctl --player=mpv metadata title
playerctl --player=mpv metadata artist
```

**Waybar MPRIS configuration** (in `~/.config/waybar/config`):
```json
"mpris": {
    "format": "{player_icon} {dynamic}",
    "format-paused": "{status_icon} {dynamic}",
    "player-icons": {
        "default": "▶",
        "mpv": "",
        "vlc": "辶",
        "spotify": ""
    },
    "status-icons": {
        "paused": "⏸"
    },
    "dynamic-len": 40,
    "dynamic-importance-order": ["title", "artist", "album"],
    "interval": 2
}
```

**Quickshell MPRIS integration** — See Ch 22 for the `MprisPlayer` type in
Quickshell's QML API. The `mpv-mpris` script exposes mpv as a standard
MPRIS2 D-Bus service; Quickshell's built-in `MprisPlayer` and `Mpris`
singleton pick it up automatically without any additional glue code.

For AGS (Ags v2 / Astal), use the `Mpris` service from `@astal/mpris`:
```javascript
// In your AGS widget
import Mpris from "gi://AstalMpris"

const mpris = Mpris.get_default()
mpris.connect("notify::players", () => {
    const players = mpris.players
    // players[0] is the active player (mpv, VLC, etc.)
    console.log(players[0]?.title)
})
```

### 72.12 Audio-Only Playback and Music Integration

mpv handles audio-only files gracefully. Combined with a Lua script or a
dedicated TUI frontend it becomes a capable music player that feeds MPRIS2 to
your status bar. For dedicated music ricing, also see Ch 73 (ncmpcpp and MPD).

```bash
# Play audio file with album art display
mpv --force-window=yes --video=no audio.flac

# Play with album art extracted from tags
mpv --force-window=yes audio.flac

# Shuffle a music directory
mpv --shuffle --loop-playlist ~/Music/

# Use as a daemon music player with IPC
mpv --input-ipc-server=/tmp/mpvsocket --idle --force-window=yes \
    --loop-playlist ~/Music/ &

# Add files to running instance
echo '{"command":["loadfile","~/Music/new.flac","append-play"]}' \
    | socat - /tmp/mpvsocket
```

For a more complete TUI music workflow, `musikcube` and `cmus` are alternatives
that integrate with mpv via MPRIS2 (see Ch 73). If you want mpv itself as the
engine, the `mpv-control` script and `SWYH` (simple wayland youtube helper)
provide playlist management overlays without leaving the terminal.

## Troubleshooting

### mpv opens on the wrong monitor / wrong scale

Wayland compositors respect `WAYLAND_DISPLAY` and the output name in
`gpu-context=waylandvk`. If mpv opens on the wrong output, set the
`screen` option:

```bash
# Force open on specific output (number corresponds to xrandr/wlr-randr output order)
mpv --screen=1 video.mkv

# Or set the Wayland output directly via env (compositor-specific)
# For Hyprland — not applicable; use window rules instead
# ~/.config/hypr/hyprland.conf:
# windowrule = monitor DP-1, class:mpv
```

### Black screen / no video with VA-API

```bash
# Verify VA-API is working
vainfo

# If vainfo fails, check driver
# AMD: sudo pacman -S mesa libva-mesa-driver
# Intel (modern): sudo pacman -S intel-media-driver
# Intel (legacy): sudo pacman -S libva-intel-driver
# NVIDIA: sudo pacman -S nvidia-utils libva-nvidia-driver

# Test VA-API decode without mpv
mpv --hwdec=vaapi --vo=gpu --gpu-context=waylandvk test.mkv
```

### mpv crashes with Vulkan / waylandvk

Vulkan support requires `vulkan-icd-loader` and a Vulkan driver. Fall back to
OpenGL if Vulkan is unstable on your GPU:

```bash
# Test with OpenGL
mpv --gpu-api=opengl --gpu-context=wayland video.mkv

# If that works, update mpv.conf:
# gpu-api=opengl
# gpu-context=wayland
```

On NVIDIA with proprietary driver, OpenGL is often more stable than Vulkan for
mpv. Use `hwdec=nvdec` and `gpu-api=opengl`.

### VLC does not start on Wayland (crashes at launch)

```bash
# Check if Qt Wayland plugin is installed
pacman -Q qt6-wayland qt5-wayland

# If missing:
sudo pacman -S qt6-wayland qt5-wayland

# Test with explicit backend
QT_QPA_PLATFORM=xcb vlc  # forces X11 (sanity check)
QT_QPA_PLATFORM=wayland vlc  # forces Wayland
```

### mpvpaper causes compositor lag

mpvpaper with shaders or high-resolution video can saturate the GPU and cause
frame drops in the compositor. Mitigations:

```bash
# Use hardware decode and lower quality settings
mpvpaper -p -o "no-audio loop hwdec=vaapi profile=fast panscan=1.0" '*' wallpaper.mp4

# Limit to 30fps (reduces GPU load)
mpvpaper -p -o "no-audio loop hwdec=vaapi vf=fps=30 panscan=1.0" '*' wallpaper.mp4

# Use a pre-encoded lower-resolution wallpaper
ffmpeg -i original.mp4 -vf scale=1920:1080 -r 30 -c:v h264 -crf 23 wallpaper-1080p.mp4
```

The `-p` (pause-when-fullscreen) flag is essential; see section 72.7.

### MPRIS2 / playerctl not showing mpv

```bash
# Verify mpv-mpris is loaded
mpv --script-opts=mpris-dummy=1 /dev/null 2>&1 | grep mpris

# Check D-Bus service
dbus-send --print-reply --dest=org.freedesktop.DBus \
    /org/freedesktop/DBus org.freedesktop.DBus.ListNames \
    | grep -i mpris

# If mpv-mpris is installed as .so but not loading:
ls /usr/lib/mpv/mpv-mpris.so
# Verify mpv loads scripts from /usr/lib/mpv/ (default on Arch)
mpv --list-options | grep script-dir
```

### yt-dlp not finding videos / format errors

```bash
# Update yt-dlp (format strings change with YouTube API updates)
sudo pacman -S yt-dlp
# or if installed via pipx:
pipx upgrade yt-dlp

# Test yt-dlp independently
yt-dlp --list-formats "URL"

# Common fix: cookies for age-restricted content
yt-dlp --cookies-from-browser firefox "URL"
mpv --ytdl-raw-options="cookies-from-browser=firefox" "URL"
```

---

## Cross-References

- **Ch 5** — GPU driver setup (Mesa, NVIDIA proprietary, VA-API stack)
- **Ch 10** — Hyprland configuration and window rules
- **Ch 22** — Quickshell `MprisPlayer` and media widget QML
- **Ch 53** — Session startup, `exec-once`, and autostart configuration
- **Ch 68** — Qt theming with Kvantum (affects VLC appearance)
- **Ch 71** — Static wallpapers with hyprpaper and swaybg
- **Ch 73** — ncmpcpp, MPD, and dedicated music player ricing

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
