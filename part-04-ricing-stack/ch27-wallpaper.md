# Chapter 27 — Wallpaper Management: swww, hyprpaper, swaybg, mpvpaper

## Overview
Wallpaper tools on Wayland use the layer-shell protocol to place images on the
BACKGROUND layer. Each has different capabilities for transitions, video, and IPC.

## Sections

### 27.1 swww — The Transition King
- Animated wallpaper transitions (fade, wipe, grow, wave, etc.)
- IPC-based: `swww img path/to/image.jpg`
- `swww-daemon`: background process
- Transition parameters: `--transition-type`, `--transition-fps`, `--transition-duration`
- `--transition-bezier` for custom easing
- Multi-monitor: per-output wallpaper assignment
- Filter modes: `Lanczos`, `CatmullRom`, `Mitchell`, `Bilinear`, `Nearest`
- Resize modes: `crop`, `fit`, `no`
- Integration with pywal/matugen

### 27.2 hyprpaper — Hyprland-Native
- Configuration in `hyprpaper.conf` or Hyprland config
- IPC via hyprctl: `hyprctl hyprpaper wallpaper "monitor,path"`
- Preloading wallpapers for fast switching
- No transition effects (Hyprland animations handle fades)
- Tight integration with Hyprland's socket

### 27.3 swaybg — Simple and Reliable
- Simple CLI: `swaybg -i image.jpg -m fill`
- No IPC, no transitions — restart to change
- Modes: `fill`, `fit`, `stretch`, `center`, `tile`
- The default bar for Sway users
- Lightweight: ideal for minimal setups

### 27.4 wpaperd — Timed Wallpaper Cycling
- Configuration file: cycle through wallpapers on a timer
- `duration`: how long each wallpaper shows
- `mode`: display scaling mode
- Useful for dynamic setups without scripting

### 27.5 mpvpaper — Video Wallpapers
- Use mpv to render video/GIF as wallpaper
- `mpvpaper -o "no-audio loop" DP-1 video.mp4`
- Supports all mpv-compatible formats
- Performance considerations: GPU load, battery impact
- `--mpv-options` for mpv flags

### 27.6 Quickshell Wallpaper (via ScreencopyView or Image)
- Setting a static image with `Image` on `WlrLayer.Background`
- Dynamic color gradient wallpapers in pure QML
- Animated shader wallpapers with `ShaderEffect`

### 27.7 Wallpaper Automation Scripts
- Random wallpaper picker with swww
- Time-of-day wallpaper switching
- Integration with pywal: `wal -i wallpaper.jpg && swww img wallpaper.jpg`
- Matugen integration: `matugen image wallpaper.jpg`

### 27.8 Wallpaper Sources and Management
- `wallust` as a pywal alternative
- `imv` and `nsxiv` for browsing and selecting
- Directory structure for wallpaper collections
