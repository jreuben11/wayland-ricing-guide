# Chapter 38 — pywal, matugen, and Automatic Color Extraction

## Overview
Dynamic theming extracts a color palette from your wallpaper and applies it
everywhere simultaneously. This enables "set wallpaper, everything matches" workflows.

## Sections

### 38.1 pywal — The Original
- `wal -i wallpaper.jpg`: extract palette, generate themes
- `wal -l`: light mode palette
- Output files in `~/.cache/wal/`:
  - `colors`: shell export file
  - `colors.json`: palette JSON
  - `colors.css`: CSS variables
  - `colors-waybar.css`: Waybar-specific CSS
  - `colors-wal-st.h`, `colors-wal-kitty.conf`, etc.
- `wal --theme base16-monokai`: use a base16 scheme instead of extracting
- Backend selection: `--backend colorz/colorthief/haishoku/schemer2`
- `wal -R`: restore last generated palette at login

#### Applying pywal to Applications
- Kitty: `include ~/.cache/wal/colors-kitty.conf`
- Waybar: `@import "~/.cache/wal/colors-waybar.css";`
- Dunst: source `~/.cache/wal/colors` in launch script
- GTK: pywal generates a GTK theme in `~/.themes/wal/`
- Quickshell: `FileView { path: Qt.resolvedUrl("~/.cache/wal/colors.json") }`

### 38.2 matugen — Material You Extraction
- Extracts a full Material You color system from an image
- Multiple output modes: `json`, `template` files
- `matugen image wallpaper.jpg --mode dark`
- Output: full Material Design 3 color roles (primary, secondary, tertiary, surface, error, etc.)
- Template system: write any config file template
- Popular for Quickshell + Hyprland setups (end_4 dots use matugen)

#### matugen Template Example
```
# ~/.config/matugen/config.toml
[config.templates.waybar]
input_path = "~/.config/waybar/style.css.tera"
output_path = "~/.config/waybar/style.css"
```
```css
/* style.css.tera */
:root {
    --primary: {{colors.primary.default.hex}};
    --background: {{colors.background.default.hex}};
}
```

### 38.3 wallust — pywal Alternative
- Faster, more modern codebase
- Same output format as pywal (drop-in for scripts)
- Additional colorscheme backends
- Better color saturation control

### 38.4 wpgtk — GUI Front-End
- GTK GUI for managing pywal palettes
- Live preview of color changes
- Theme management: save and switch palettes

### 38.5 End-to-End Dynamic Theming Script
```bash
#!/bin/bash
WALL="$1"

# Set wallpaper
swww img "$WALL" --transition-type wipe --transition-duration 1

# Extract colors
matugen image "$WALL" --mode dark

# Reload bar
pkill -SIGUSR2 waybar || waybar &

# Reload Quickshell (if using FileView watching)
# It auto-detects the file change

# Reload terminal theme (kitty example)
kitty @ set-colors --all ~/.cache/matugen/colors-kitty.conf

notify-send "Theme" "Applied colors from $(basename $WALL)"
```

### 38.6 Applying Palettes to Firefox
- Firefox Color extension: apply theme via pywal Firefox output
- `wal-firefox` integration
- Pywalfox: apply pywal palette to Firefox CSS

### 38.7 Applying Palettes to Terminals
- **Kitty**: `~/.cache/wal/colors-kitty.conf` (live reload: `kitty @ set-colors --all`)
- **Alacritty**: template in `~/.config/alacritty/colors.toml`
- **Foot**: template generation
- **Wezterm**: Lua + FileView watching

### 38.8 Systemwide Palette Consistency
- The problem: 20+ apps each with their own color config
- Solution hierarchy:
  1. Stylix (NixOS) — automated, declarative (Chapter 40)
  2. matugen templates — most flexible for non-NixOS
  3. pywal — simpler, less Material-accurate
  4. Manual — complete control, high maintenance
