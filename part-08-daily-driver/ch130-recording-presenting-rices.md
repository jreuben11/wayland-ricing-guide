# Chapter 130 — Recording, Presenting, and Sharing Your Rice

## Contents

- [Overview](#overview)
- [130.1 fastfetch: System Info for Rice Screenshots](#1301-fastfetch-system-info-for-rice-screenshots)
  - [Installation](#installation)
  - [Config File](#config-file)
  - [Custom ASCII Logo](#custom-ascii-logo)
  - [Color Palette Block](#color-palette-block)
- [130.2 neofetch vs fastfetch vs pfetch](#1302-neofetch-vs-fastfetch-vs-pfetch)
- [130.3 The Standard Rice Screenshot Composition](#1303-the-standard-rice-screenshot-composition)
- [130.4 Screen Recording with wf-recorder](#1304-screen-recording-with-wf-recorder)
- [130.5 Animated GIF Creation](#1305-animated-gif-creation)
  - [ffmpeg pipeline](#ffmpeg-pipeline)
  - [gifsicle optimization](#gifsicle-optimization)
  - [One-shot GIF capture script](#one-shot-gif-capture-script)
- [130.6 r/unixporn Submission Guide](#1306-runixporn-submission-guide)
  - [What to include](#what-to-include)
  - [Software list comment template](#software-list-comment-template)
  - [Image requirements](#image-requirements)
- [130.7 GitHub README Showcase](#1307-github-readme-showcase)
  - [README badge strip](#readme-badge-strip)
- [130.8 Video Codec Recommendations](#1308-video-codec-recommendations)

---


## Overview

A rice only exists in the community's imagination until you share it. This chapter covers the full pipeline from live desktop to shareable artifact: `fastfetch` and `neofetch` configuration for the canonical fetch screenshot, screen recording with `wf-recorder` and OBS, animated GIF creation with `ffmpeg`, and the r/unixporn submission workflow. Every step is Wayland-native.

**Cross-references:** Ch 31 — screenshot tools (grim, swappy). Ch 127 — OBS Studio on Wayland. Ch 112 — aesthetic ricing meta-chapter (the desktop to showcase). Ch 55 — dotfile management (sharing the config behind the rice).

---

## 130.1 fastfetch: System Info for Rice Screenshots

`fastfetch` is the modern replacement for `neofetch` — faster (written in C), actively maintained, and modular via a JSON config. Every rice showcase on r/unixporn since 2023 uses it.

### Installation

```bash
# Arch Linux
sudo pacman -S fastfetch

# Ubuntu 24.04+
sudo add-apt-repository ppa:zhangsongcui3371/fastfetch
sudo apt install fastfetch

# From source
git clone https://github.com/fastfetch-cli/fastfetch
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)
sudo cmake --install build
```

### Config File

```bash
# Generate default config to edit
fastfetch --gen-config
# → ~/.config/fastfetch/config.jsonc
```

The config is JSON with comments (`jsonc`). A rice-focused config:

```jsonc
// ~/.config/fastfetch/config.jsonc
{
  "$schema": "https://github.com/fastfetch-cli/fastfetch/raw/dev/doc/json_schema.json",
  "logo": {
    "source": "~/.config/fastfetch/logo.txt",
    "color": {
      "1": "blue",
      "2": "cyan"
    },
    "padding": {
      "right": 2
    }
  },
  "display": {
    "separator": "  ",
    "color": {
      "keys": "blue",
      "title": "blue"
    }
  },
  "modules": [
    {
      "type": "title",
      "format": "{6}@{7}",
      "color": {
        "user": "cyan",
        "at": "white",
        "host": "blue"
      }
    },
    "separator",
    { "type": "os",          "key": " OS",       "keyColor": "blue" },
    { "type": "kernel",      "key": " Kernel",   "keyColor": "blue" },
    { "type": "wm",          "key": "󰨈 WM",       "keyColor": "purple" },
    { "type": "wmtheme",     "key": " Theme",    "keyColor": "purple" },
    { "type": "terminal",    "key": " Terminal", "keyColor": "green" },
    { "type": "shell",       "key": " Shell",    "keyColor": "green" },
    { "type": "editor",      "key": "󰠮 Editor",   "keyColor": "green" },
    { "type": "font",        "key": " Font",     "keyColor": "yellow" },
    { "type": "icons",       "key": "󰀻 Icons",    "keyColor": "yellow" },
    { "type": "cursor",      "key": " Cursor",   "keyColor": "yellow" },
    { "type": "cpu",         "key": " CPU",      "keyColor": "red" },
    { "type": "gpu",         "key": " GPU",      "keyColor": "red" },
    { "type": "memory",      "key": " Memory",   "keyColor": "red" },
    { "type": "disk",        "key": "󰋊 Disk",     "keyColor": "red", "folders": "/" },
    { "type": "uptime",      "key": "󰔟 Uptime",   "keyColor": "white" },
    { "type": "packages",    "key": "󰏖 Packages", "keyColor": "white" },
    "separator",
    { "type": "colors",      "symbol": "block",  "paddingLeft": 0 }
  ]
}
```

### Custom ASCII Logo

```bash
# Create a custom logo file
cat > ~/.config/fastfetch/logo.txt << 'EOF'
    ／|、
   (˚ˎ。7  
    |、˜〵          
   じしˍ,)ノ
EOF
```

Or use a colored multi-line logo with ANSI codes:
```bash
# Generate from image (requires chafa)
chafa --format=symbols --size=30x15 ~/Pictures/logo.png \
  > ~/.config/fastfetch/logo.txt
```

For the distro logo with custom colors, use the `logo.type` and `logo.color` fields:
```jsonc
"logo": {
  "type": "arch",        // built-in distro logo
  "color": {
    "1": "38;2;122;162;247",   // Tokyo Night blue (RGB escape)
    "2": "38;2;187;154;247"    // Tokyo Night purple
  }
}
```

### Color Palette Block

The `colors` module at the bottom of the output renders a row of terminal color swatches — the signature element of rice screenshots:

```jsonc
{ "type": "colors", "symbol": "block",   "paddingLeft": 0 }  // solid blocks
{ "type": "colors", "symbol": "circle",  "paddingLeft": 0 }  // circles
{ "type": "colors", "symbol": "diamond", "paddingLeft": 0 }  // diamonds
```

---

## 130.2 neofetch vs fastfetch vs pfetch

| Tool | Language | Maintained | Speed | Config | Best for |
|---|---|---|---|---|---|
| **fastfetch** | C | Yes (2024+) | Fast | JSON | Modern rices, Wayland |
| **neofetch** | Bash | No (archived 2024) | Slow | Bash | Legacy configs |
| **pfetch** | POSIX sh | Minimal | Very fast | Env vars | Minimal rices |
| **macchina** | Rust | Yes | Fast | TOML | Rust ecosystem |
| **hyfetch** | Python | Yes | Medium | JSON | Pride flags, fun |

Migrating from neofetch:
```bash
# neofetch flags map to fastfetch as follows:
neofetch --off          → fastfetch --logo none
neofetch --ascii_distro → fastfetch --logo <distro>
neofetch --color_blocks → fastfetch module: {type: "colors"}
neofetch --config file  → fastfetch --config file
```

---

## 130.3 The Standard Rice Screenshot Composition

The canonical r/unixporn screenshot shows:

1. **Full desktop** — wallpaper, bar, open windows in a tiled layout
2. **Terminal with fetch** — `fastfetch` output showing OS/WM/theme info
3. **Terminal with some code** — neovim, helix, or similar (optional but common)
4. **File manager or browser** (optional)

Layout recipe for Hyprland:
```bash
# Open a 2-window layout for the screenshot
hyprctl dispatch splitratio 0.55          # terminal takes 55% width
foot -e fastfetch &                        # fetch terminal
foot -e nvim ~/.config/hypr/hyprland.conf  # config in editor
sleep 0.5
grim ~/Screenshots/rice-$(date +%Y%m%d).png
```

For a scripted rice screenshot:
```bash
#!/bin/bash
# ~/.local/bin/rice-shot
OUTDIR=~/Screenshots/rices
mkdir -p "$OUTDIR"
OUT="$OUTDIR/rice-$(date +%Y%m%d-%H%M%S).png"

# Ensure layout is set
hyprctl dispatch workspace 1
sleep 0.2

# Screenshot entire workspace
grim "$OUT"
echo "Saved: $OUT"

# Optional: copy to clipboard
wl-copy < "$OUT"
```

---

## 130.4 Screen Recording with wf-recorder

`wf-recorder` is a lightweight Wayland screen recorder using PipeWire — ideal for short clips (10–60s) without OBS overhead.

```bash
# Install
sudo pacman -S wf-recorder          # Arch
sudo apt install wf-recorder        # Ubuntu

# Record entire screen
wf-recorder -o HDMI-A-1 -f ~/Videos/rice.mp4

# Record a selected region (uses slurp)
wf-recorder -g "$(slurp)" -f ~/Videos/rice-region.mp4

# With GPU encoding (AMD/Intel VAAPI)
wf-recorder -c h264_vaapi -d /dev/dri/renderD128 -f ~/Videos/rice.mp4

# With NVIDIA NVENC
wf-recorder -c h264_nvenc -f ~/Videos/rice.mp4

# High quality for sharing
wf-recorder -c libx264 -p preset=slow -p crf=18 -f ~/Videos/rice-hq.mp4

# Stop recording
pkill -SIGINT wf-recorder
```

Hyprland keybind:
```ini
bind = SUPER SHIFT, R, exec, \
  pkill -SIGINT wf-recorder || \
  wf-recorder -o $(hyprctl monitors -j | jq -r '.[] | select(.focused) | .name') \
              -f ~/Videos/rice-$(date +%Y%m%d-%H%M%S).mp4
```

---

## 130.5 Animated GIF Creation

GIFs are the standard format for showcasing desktop animations on GitHub READMEs and some Reddit posts.

### ffmpeg pipeline

```bash
# Step 1: Record a short clip (10–20s max for GIF)
wf-recorder -g "$(slurp)" -f /tmp/rice-raw.mp4

# Step 2: Generate an optimal palette (critical for quality)
ffmpeg -i /tmp/rice-raw.mp4 \
  -vf "fps=15,scale=1200:-1:flags=lanczos,palettegen=max_colors=256:stats_mode=diff" \
  /tmp/palette.png

# Step 3: Convert to GIF using the palette
ffmpeg -i /tmp/rice-raw.mp4 -i /tmp/palette.png \
  -filter_complex "fps=15,scale=1200:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
  ~/Pictures/rice-demo.gif

# Check file size
du -sh ~/Pictures/rice-demo.gif
```

### gifsicle optimization

```bash
# Install
sudo pacman -S gifsicle

# Optimize (lossy compression, significant size reduction)
gifsicle --optimize=3 --lossy=80 \
  --resize-width 800 \
  ~/Pictures/rice-demo.gif \
  -o ~/Pictures/rice-demo-optimized.gif

# Target specific file size via lossy level
# --lossy=30  → minimal quality loss (~30% smaller)
# --lossy=80  → noticeable but acceptable (~60% smaller)
# --lossy=200 → heavy compression (~75% smaller)
```

### One-shot GIF capture script

```bash
#!/bin/bash
# ~/.local/bin/gifcap
# Usage: gifcap [fps] [width]
FPS=${1:-15}
WIDTH=${2:-1000}
TMP=$(mktemp -d)
REGION=$(slurp)
OUT=~/Pictures/rices/gif-$(date +%Y%m%d-%H%M%S).gif

wf-recorder -g "$REGION" -f "$TMP/raw.mp4"  # Ctrl+C to stop

ffmpeg -i "$TMP/raw.mp4" \
  -vf "fps=$FPS,scale=$WIDTH:-1:flags=lanczos,palettegen" \
  "$TMP/palette.png" -y 2>/dev/null

ffmpeg -i "$TMP/raw.mp4" -i "$TMP/palette.png" \
  -filter_complex "fps=$FPS,scale=$WIDTH:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5" \
  "$TMP/out.gif" -y 2>/dev/null

gifsicle --optimize=3 --lossy=60 "$TMP/out.gif" -o "$OUT"
rm -rf "$TMP"
echo "Saved: $OUT ($(du -sh "$OUT" | cut -f1))"
wl-copy < "$OUT"
```

---

## 130.6 r/unixporn Submission Guide

### What to include

A standard submission has:
1. **Title format**: `[WM] Short description of the rice`  
   Example: `[Hyprland] Tokyo Night minimal — Kitty + Neovim + eww`
2. **Top-level image**: Full desktop screenshot (PNG, under 20MB)
3. **Comment with**: fastfetch output, dotfiles link, software list

### Software list comment template

```markdown
**OS**: Arch Linux
**WM**: Hyprland 0.41.2
**Bar**: Waybar + custom CSS
**Terminal**: Kitty with JetBrains Mono Nerd Font
**Shell**: zsh + starship
**Editor**: Neovim (LazyVim)
**File Manager**: Yazi
**Launcher**: fuzzel
**Notifications**: mako
**Wallpaper**: [artist name / source](url)
**GTK Theme**: Catppuccin-Mocha-Standard-Blue-Dark
**Icon Theme**: Papirus-Dark
**Cursor**: Bibata-Modern-Classic
**Fetch**: fastfetch
**Dotfiles**: [github link]
```

### Image requirements

- PNG format preferred (no JPEG compression artifacts on text)
- Full resolution (don't downscale — Reddit serves it at native resolution)
- Under 20MB (grim output is fine; compress only if needed)
- Multiple shots: full desktop + closeup of bar/terminal

```bash
# Compress if over 20MB
convert ~/Screenshots/rice.png -quality 92 ~/Screenshots/rice-compressed.jpg
# Or keep PNG but crush it
optipng -o7 ~/Screenshots/rice.png
```

---

## 130.7 GitHub README Showcase

For a dotfiles repository README:

```bash
# Embed a static screenshot
![Rice Screenshot](assets/screenshots/rice-main.png)

# Embed a GIF demo (animations, transitions)
![Demo](assets/rice-demo.gif)
```

Directory structure for a dotfiles repo:
```
dotfiles/
├── README.md
├── assets/
│   ├── screenshots/
│   │   ├── rice-main.png      # Full desktop
│   │   ├── rice-terminal.png  # Terminal closeup
│   │   └── rice-fetch.png     # fastfetch output
│   └── rice-demo.gif          # Animated demo
└── .config/
    ├── hypr/
    ├── waybar/
    └── ...
```

### README badge strip

```markdown
![OS](https://img.shields.io/badge/OS-Arch_Linux-1793D1?style=flat&logo=arch-linux)
![WM](https://img.shields.io/badge/WM-Hyprland-58E1FF?style=flat)
![Theme](https://img.shields.io/badge/Theme-Tokyo_Night-7AA2F7?style=flat)
```

---

## 130.8 Video Codec Recommendations

For YouTube/Twitch/Vimeo showcases:

| Use case | Codec | Settings | wf-recorder flag |
|---|---|---|---|
| High-quality archival | H.264 | CRF 18, preset slow | `-c libx264 -p crf=18` |
| Fast encode (GPU) | H.264 VAAPI | QP 20 | `-c h264_vaapi` |
| Web streaming | H.264 | CRF 23, preset fast | `-c libx264 -p crf=23 -p preset=fast` |
| Modern quality | H.265/HEVC | CRF 22 | `-c libx265 -p crf=22` |
| Open source | AV1 | CRF 30 (slow encode) | `-c libaom-av1` |

For Discord (8MB limit for non-Nitro):
```bash
# Target ~7MB for a 30-second clip
ffmpeg -i input.mp4 \
  -b:v 1500k -maxrate 1500k -bufsize 3000k \
  -vf "scale=1280:-2" \
  -c:a aac -b:a 128k \
  output-discord.mp4
```
