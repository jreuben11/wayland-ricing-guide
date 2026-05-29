# Chapter 31 — Screenshots and Recording: grim, slurp, wf-recorder, OBS

## Overview
Screenshot and screen recording on Wayland requires compositor cooperation via
the screencopy protocol. The native toolchain is now mature and feature-complete.

## Sections

### 31.1 The Screencopy Protocol Stack
- `wlr-screencopy-unstable-v1`: the underlying mechanism
- `xdg-desktop-portal-wlr` / `xdg-desktop-portal-hyprland`: portal bridge for apps
- Why X11 screenshot tools (scrot, maim) don't work on Wayland

### 31.2 grim — The Screenshot Foundation
- `grim screenshot.png`: full screenshot of all outputs
- `grim -o DP-1 monitor.png`: specific output
- `grim -g "0,0 1920x1080" region.png`: specific geometry
- `-t png/jpeg/ppm`: output format
- `-s 0.5`: scale factor
- Piping to clipboard: `grim - | wl-copy`

### 31.3 slurp — Region Selection
```bash
# Interactive region screenshot
grim -g "$(slurp)" screenshot.png

# Window screenshot (via Hyprland)
grim -g "$(hyprctl activewindow -j | jq -r '"\(.at[0]),\(.at[1]) \(.size[0])x\(.size[1])"')" window.png
```
- Interactive crosshair selection UI
- `-d`: display mode (full output selection)
- `-o`: output selection mode
- Integration with grim pipeline

### 31.4 hyprshot — Hyprland-Integrated Screenshots
- `hyprshot -m region`: slurp-based region capture
- `hyprshot -m window`: active/clicked window
- `hyprshot -m output`: full monitor
- `--clipboard-only`: copy without saving
- Output folder configuration

### 31.5 Screenshot Scripting
```bash
#!/bin/bash
# Full-featured screenshot script
case $1 in
    region) grim -g "$(slurp -d)" - | tee ~/Pictures/$(date +%Y%m%d_%H%M%S).png | wl-copy ;;
    full) grim ~/Pictures/$(date +%Y%m%d_%H%M%S).png ;;
    window) grim -g "$(hyprctl activewindow -j | jq -r ...)" - | wl-copy ;;
esac
notify-send "Screenshot" "Saved to ~/Pictures"
```

### 31.6 wf-recorder — Screen Recording
- `wf-recorder -f output.mp4`: record entire screen
- `wf-recorder -g "$(slurp)"`: record selected region
- `-c libx264 -x yuv420p`: codec and pixel format
- `--audio`: include audio (PipeWire)
- `-a "device_name"`: specific audio device
- Stop recording: `pkill -INT wf-recorder`

### 31.7 OBS Studio on Wayland
- `obs --enable-media-stream` (pipewire backend)
- PipeWire screen capture source
- `xdg-desktop-portal-hyprland` or `-wlr` for portal-based capture
- Window capture: `xdg-desktop-portal` window selection
- Virtual camera output to PipeWire

### 31.8 wl-screenrec — Fast Hardware-Accelerated Recording
- Uses DMA-BUF for zero-copy GPU capture
- H.264/H.265/AV1 encoding with hardware acceleration
- Lower CPU usage than wf-recorder for high-res captures

### 31.9 Flameshot on Wayland
- Status: partial Wayland support
- `flameshot gui` for annotated screenshots
- Portal-based capture mode

### 31.10 Annotating Screenshots
- `swappy`: draw/annotate on grim output
  ```bash
  grim -g "$(slurp)" - | swappy -f -
  ```
- satty: modern GTK4 annotation tool
