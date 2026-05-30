# Chapter 103 — Cursor Theme Creation: xcursor and hyprcursor

## Contents

- [Overview](#overview)
- [103.1 Cursor Theme Formats](#1031-cursor-theme-formats)
- [103.2 xcursor Format](#1032-xcursor-format)
  - [Directory structure](#directory-structure)
  - [cursor.theme](#cursortheme)
  - [xcursor binary format](#xcursor-binary-format)
- [103.3 Creating xcursor with xcursorgen](#1033-creating-xcursor-with-xcursorgen)
  - [Prerequisites](#prerequisites)
  - [Source SVG → PNG → xcursor](#source-svg-png-xcursor)
  - [Creating symlinks for cursor name aliases](#creating-symlinks-for-cursor-name-aliases)
- [103.4 Automation Script](#1034-automation-script)
- [103.5 hyprcursor Format](#1035-hyprcursor-format)
  - [Directory structure](#directory-structure)
  - [manifest.hl](#manifesthl)
  - [meta.hl (per cursor)](#metahl-per-cursor)
  - [SVG requirements](#svg-requirements)
- [103.6 hyprcursor-util — Conversion and Packaging](#1036-hyprcursor-util-conversion-and-packaging)
- [103.7 Installing and Applying](#1037-installing-and-applying)
  - [System-wide](#system-wide)
  - [User-local](#user-local)
  - [Hyprland config](#hyprland-config)
  - [GTK / GNOME settings](#gtk-gnome-settings)
  - [Home Manager (NixOS)](#home-manager-nixos)
- [103.8 Essential Cursor Shapes](#1038-essential-cursor-shapes)
- [103.9 Colouring Existing Themes with resvg / inkscape](#1039-colouring-existing-themes-with-resvg-inkscape)
- [103.10 Troubleshooting](#10310-troubleshooting)

---


## Overview

The cursor is one of the first things visible on your desktop. Most rices pick
an existing theme (Catppuccin cursors, Bibata, Volantes) but creating your own
gives complete control over shape, animation, and colour. This chapter covers
both the traditional xcursor format (works everywhere) and hyprcursor (Hyprland's
SVG-based format that scales perfectly at any DPI).

---

## 103.1 Cursor Theme Formats

| Format | Files | Scaling | Supported by |
|--------|-------|---------|--------------|
| xcursor | PNG sprites at fixed sizes | Nearest-neighbour upscale | All compositors |
| hyprcursor | SVG + manifest | Perfect vector scaling | Hyprland only (falls back to xcursor) |

For maximum compatibility: create xcursor. For Hyprland with fractional scaling:
create hyprcursor (xcursor fallback is automatic).

---

## 103.2 xcursor Format

### Directory structure

```
MyCursor/
├── cursor.theme          ← theme metadata
└── cursors/
    ├── default           ← binary xcursor file (arrow)
    ├── text              ← I-beam
    ├── pointer           ← hand/link
    ├── crosshair
    ├── wait              ← animated spinner
    ├── progress
    ├── move
    ├── n-resize
    ├── s-resize
    ├── e-resize
    ├── w-resize
    ├── ne-resize
    ├── nw-resize
    ├── se-resize
    ├── sw-resize
    └── ...               ← symlinks for aliases
```

### cursor.theme

```ini
[Icon Theme]
Name=MyCursor
Comment=My custom cursor theme
```

### xcursor binary format

Each file in `cursors/` is a binary containing one or more PNG frames at
one or more sizes. The standard sizes are 24, 32, 48, 64, 96, 128 px.

The easiest workflow is to create SVGs then rasterise them.

---

## 103.3 Creating xcursor with xcursorgen

### Prerequisites

```bash
sudo pacman -S xorg-xcursorgen inkscape  # or: imagemagick for rasterising
```

### Source SVG → PNG → xcursor

For each cursor shape, create an SVG (e.g., `arrow.svg`) then:

```bash
# Rasterise at multiple sizes
for size in 24 32 48 64 96 128; do
  inkscape -w $size -h $size arrow.svg -o cursor-pngs/arrow-${size}.png
done
```

Create a `.cursor` config file for xcursorgen:

```
# arrow.cursor
# Format: SIZE HOTSPOT_X HOTSPOT_Y FILENAME [DELAY_MS]
24  4  4  cursor-pngs/arrow-24.png
32  5  5  cursor-pngs/arrow-32.png
48  8  8  cursor-pngs/arrow-48.png
64 10 10  cursor-pngs/arrow-64.png
96 15 15  cursor-pngs/arrow-96.png
128 20 20 cursor-pngs/arrow-128.png
```

The hotspot is the pixel that registers as the actual click point.

```bash
# Generate the binary cursor file
xcursorgen arrow.cursor MyCursor/cursors/default

# Animated cursor (multiple frames with delay):
# DELAY_MS is the frame duration in milliseconds
# 24  12 12  spinner-frame-0-24.png 50
# 24  12 12  spinner-frame-1-24.png 50
# ...
xcursorgen wait.cursor MyCursor/cursors/wait
```

### Creating symlinks for cursor name aliases

Many applications request cursors by different names. Create symlinks:

```bash
cd MyCursor/cursors

# Arrow aliases
ln -s default arrow
ln -s default left_ptr
ln -s default top_left_arrow

# Pointer (hand) aliases
ln -s pointer hand
ln -s pointer hand1
ln -s pointer hand2
ln -s pointer pointing_hand

# Text aliases
ln -s text xterm
ln -s text ibeam

# Wait aliases
ln -s wait watch
ln -s wait clock

# Resize aliases
ln -s n-resize top_side
ln -s s-resize bottom_side
ln -s e-resize right_side
ln -s w-resize left_side
```

For a complete alias list, refer to the X cursor name specification or copy
the symlinks from an existing theme like Adwaita:

```bash
ls -la /usr/share/icons/Adwaita/cursors/ | grep ' -> ' | awk '{print $9, $11}'
```

---

## 103.4 Automation Script

```bash
#!/bin/bash
# build-xcursor.sh — build a complete xcursor theme from SVGs

THEME_NAME="MyCursor"
SVG_DIR="./src/svg"
OUT_DIR="./${THEME_NAME}/cursors"
SIZES=(24 32 48 64 96 128)

mkdir -p "$OUT_DIR" ./tmp/pngs

# For each cursor SVG in src/svg/
for svg in "$SVG_DIR"/*.svg; do
  name=$(basename "$svg" .svg)
  cursor_file="./tmp/${name}.cursor"
  echo "" > "$cursor_file"

  for size in "${SIZES[@]}"; do
    png="./tmp/pngs/${name}-${size}.png"
    inkscape -w "$size" -h "$size" "$svg" -o "$png" 2>/dev/null
    # Read hotspot from SVG metadata (or hardcode per cursor)
    hx=$(( size / 6 ))
    hy=$(( size / 6 ))
    echo "$size $hx $hy $png" >> "$cursor_file"
  done

  xcursorgen "$cursor_file" "$OUT_DIR/$name"
  echo "Built: $name"
done

# Apply symlinks
ln -sf default "$OUT_DIR/left_ptr"
ln -sf default "$OUT_DIR/arrow"
ln -sf pointer "$OUT_DIR/hand"
ln -sf pointer "$OUT_DIR/hand2"
ln -sf text    "$OUT_DIR/xterm"
ln -sf wait    "$OUT_DIR/watch"

# Create index.theme
cat > "${THEME_NAME}/index.theme" << EOF
[Icon Theme]
Name=${THEME_NAME}
Comment=Custom cursor theme
EOF

echo "Done: ${THEME_NAME}/"
```

---

## 103.5 hyprcursor Format

hyprcursor is Hyprland's SVG-based cursor format. Because cursors are stored as
SVG, they scale perfectly to any DPI without pixelation — critical for HiDPI
and fractional scaling.

### Directory structure

```
MyCursor-hyprcursor/
├── manifest.hl           ← theme manifest
└── hyprcursors/
    ├── default/
    │   ├── meta.hl       ← cursor metadata (hotspot, sizes, delay)
    │   └── default.svg   ← SVG shape
    ├── text/
    │   ├── meta.hl
    │   └── text.svg
    ├── pointer/
    │   ├── meta.hl
    │   └── pointer.svg
    └── wait/
        ├── meta.hl
        ├── wait-0.svg    ← animation frames
        ├── wait-1.svg
        └── ...
```

### manifest.hl

```
name = MyCursor
description = My custom hyprcursor theme
version = 0.1
cursors_directory = hyprcursors
```

### meta.hl (per cursor)

```
resize_algorithm = none       # or: bilinear, nearest, lanczos

define_size = 0, 24          # size 0 = use at any size (SVG scales)
hotspot_x = 4
hotspot_y = 4
```

For an animated cursor (e.g., `wait`):
```
resize_algorithm = none

define_size = 0, 24

hotspot_x = 12
hotspot_y = 12

# Frames: filename delay_ms
define_override = wait-0.svg, 50
define_override = wait-1.svg, 50
define_override = wait-2.svg, 50
define_override = wait-3.svg, 50
define_override = wait-4.svg, 50
define_override = wait-5.svg, 50
define_override = wait-6.svg, 50
define_override = wait-7.svg, 50
```

### SVG requirements

- ViewBox should be square (e.g., `viewBox="0 0 24 24"`)
- Use CSS variables for colours if you want theme-able cursors:
  ```svg
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
    <style>
      .cursor-fill   { fill:   var(--cursor-color, #cdd6f4); }
      .cursor-stroke { stroke: var(--cursor-outline, #1e1e2e); }
    </style>
    <path class="cursor-fill cursor-stroke" stroke-width="1.5"
          d="M4 4 L4 20 L8 16 L12 24 L14 23 L10 15 L16 15 Z"/>
  </svg>
  ```

---

## 103.6 hyprcursor-util — Conversion and Packaging

```bash
# Install
paru -S hyprcursor   # includes hyprcursor-util

# Convert an existing xcursor theme to hyprcursor
hyprcursor-util --extract /usr/share/icons/Adwaita ./extracted/
hyprcursor-util --create ./extracted/ ./Adwaita-hyprcursor

# Verify a hyprcursor theme
hyprcursor-util --verify ./MyCursor-hyprcursor

# Test a cursor shape
hyprcursor-util --preview ./MyCursor-hyprcursor default
```

The `--extract` and `--create` pipeline is the fastest way to start: extract
an existing theme you like, swap out the SVGs you want to customise, and
repackage.

---

## 103.7 Installing and Applying

### System-wide

```bash
sudo cp -r MyCursor /usr/share/icons/
sudo cp -r MyCursor-hyprcursor /usr/share/icons/
```

### User-local

```bash
cp -r MyCursor ~/.local/share/icons/
cp -r MyCursor-hyprcursor ~/.local/share/icons/
```

### Hyprland config

```conf
# hyprland.conf
env = XCURSOR_THEME,MyCursor
env = XCURSOR_SIZE,24
env = HYPRCURSOR_THEME,MyCursor-hyprcursor
env = HYPRCURSOR_SIZE,24

# Apply to running session:
exec-once = hyprctl setcursor MyCursor-hyprcursor 24
```

### GTK / GNOME settings

```bash
gsettings set org.gnome.desktop.interface cursor-theme "MyCursor"
gsettings set org.gnome.desktop.interface cursor-size 24
```

### Home Manager (NixOS)

```nix
home.pointerCursor = {
    package    = pkgs.my-cursor-theme;
    name       = "MyCursor";
    size       = 24;
    gtk.enable = true;
    x11.enable = true;
};
```

---

## 103.8 Essential Cursor Shapes

A minimal theme needs these shapes (many are aliases of a few base shapes):

| Shape | Description | Common aliases |
|-------|-------------|----------------|
| `default` | Arrow pointer | `left_ptr`, `arrow`, `top_left_arrow` |
| `text` | I-beam for text | `xterm`, `ibeam` |
| `pointer` | Hand for links | `hand`, `hand1`, `hand2`, `pointing_hand` |
| `crosshair` | Precision cross | `cross`, `crosshair` |
| `move` | Move icon | `fleur`, `all-scroll` |
| `wait` | Spinner (animated) | `watch`, `clock` |
| `progress` | Arrow + spinner | `half-busy` |
| `not-allowed` | Crossed circle | `forbidden`, `no-drop` |
| `grab` | Open hand | `openhand`, `hand1` |
| `grabbing` | Closed hand | `closedhand`, `dnd-move` |
| `zoom-in` | Magnifier + | `zoom_in` |
| `zoom-out` | Magnifier − | `zoom_out` |
| `n-resize` | North resize | `top_side`, `top_tee` |
| `s-resize` | South resize | `bottom_side`, `bottom_tee` |
| `e-resize` | East resize | `right_side`, `right_tee` |
| `w-resize` | West resize | `left_side`, `left_tee` |
| `ne-resize` | Northeast resize | `top_right_corner` |
| `nw-resize` | Northwest resize | `top_left_corner` |
| `se-resize` | Southeast resize | `bottom_right_corner` |
| `sw-resize` | Southwest resize | `bottom_left_corner` |
| `col-resize` | Horizontal split | `h_double_arrow`, `sb_h_double_arrow` |
| `row-resize` | Vertical split | `v_double_arrow`, `sb_v_double_arrow` |

---

## 103.9 Colouring Existing Themes with resvg / inkscape

A quick way to make a custom theme: grab an existing SVG-based theme, replace
colours with a script:

```bash
# Replace a colour across all SVGs in a hyprcursor theme
find ./hyprcursors -name "*.svg" | while read f; do
  sed -i 's/#c0caf5/#89b4fa/g' "$f"   # replace text blue with accent blue
  sed -i 's/#1a1b26/#1e1e2e/g' "$f"   # replace background
done
```

Or use a Python script for more control:

```python
#!/usr/bin/env python3
import re, sys, os
from pathlib import Path

REPLACEMENTS = {
    "#c0caf5": "#cdd6f4",  # text
    "#1a1b26": "#1e1e2e",  # base
    "#bb9af7": "#cba6f7",  # mauve
}

for svg in Path("./hyprcursors").rglob("*.svg"):
    content = svg.read_text()
    for old, new in REPLACEMENTS.items():
        content = content.replace(old, new)
        content = content.replace(old.upper(), new.upper())
    svg.write_text(content)
    print(f"Updated: {svg}")
```

---

## 103.10 Troubleshooting

**Cursor appears wrong in some apps:**
- GTK apps read `XCURSOR_THEME`; Qt apps may read `XCURSOR_THEME` or their own setting
- Check: `echo $XCURSOR_THEME` and `gsettings get org.gnome.desktop.interface cursor-theme`
- Force: `gsettings set org.gnome.desktop.interface cursor-theme "MyCursor"`

**hyprcursor not applying:**
- Verify with `hyprctl getoption cursor:no_hardware_cursors`
- Check `HYPRCURSOR_THEME` is set before Hyprland starts (in `hyprland.conf` env block)
- Run `hyprctl setcursor MyCursor-hyprcursor 24` in a running session

**XWayland apps using wrong cursor:**
- XWayland reads `XCURSOR_THEME`/`XCURSOR_SIZE` from the environment
- Add to `~/.profile` or Hyprland `env =` lines

**Cursor too small on HiDPI:**
- For hyprcursor: size is in logical pixels, compositor handles DPI scaling
- For xcursor: set `XCURSOR_SIZE` to the physical pixel size you want
  (e.g., 48 for a 24pt cursor at 2× scale)

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
