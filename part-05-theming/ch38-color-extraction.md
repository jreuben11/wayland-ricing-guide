# Chapter 38 — pywal, matugen, and Automatic Color Extraction

## Overview

Dynamic theming extracts a color palette from your wallpaper and applies it
everywhere simultaneously. This enables "set wallpaper, everything matches"
workflows without the tedium of editing dozens of config files by hand. The
core insight is that any sufficiently complex image already contains a visually
coherent set of colors; extracting those colors and distributing them as
variables yields a desktop that is perceptually unified by construction.

The ecosystem has matured considerably since pywal first popularized the idea.
Today you have a spectrum of tools — from the lean and scriptable pywal/wallust
family to the full Material You design-system extraction of matugen — each
making different trade-offs between output fidelity, integration depth, and
runtime overhead. Choosing among them depends on how much of the Material
Design 3 color-role vocabulary you need versus how simple you want your
bootstrap scripts to be.

This chapter covers the four main extraction tools, shows how to wire them into
Waybar, terminals, Dunst, and Quickshell, and ends with a production-grade
end-to-end dynamic theming script and a troubleshooting guide. For static
theming declarations on NixOS see **Chapter 40 (Stylix)**. For Quickshell
`FileView`-based live reloading see **Chapter 29**. For session-startup
sequencing of theme application see **Chapter 53**.

---

## 38.1 pywal — The Original

pywal (simply `wal` on the command line) is a Python utility that runs a
color-quantization backend against an image and writes the resulting palette to
a tree of output files under `~/.cache/wal/`. Every downstream config that
can import a file or source a shell script can consume those files with no
further work. The project is deliberately small: it does one thing and writes
generic output formats that other tools read.

The core invocation is `wal -i <image>`. pywal detects the most visually
prominent colors, assigns them to the 16-terminal-color slots (colors 0–15),
and generates theme files for a dozen applications. The `-l` flag inverts the
brightness mapping to produce a light-mode palette. The `-R` flag restores the
last generated palette without re-running the backend — useful in session
startup before a wallpaper daemon is ready.

Backend selection controls the quantization algorithm. The default backend is
`wal` (ImageMagick), which is reliable but slow. `colorz` and `colorthief` are
faster Python implementations. `haishoku` and `schemer2` are alternatives with
different saturation characteristics. Install the extras you want:

```bash
# Install pywal with optional backends
pip install pywal          # or: uv tool install pywal
pip install colorz colorthief haishoku

# Basic usage
wal -i ~/Pictures/wallpapers/mountain.jpg

# Light mode
wal -i ~/Pictures/wallpapers/mountain.jpg -l

# Explicit backend
wal -i ~/Pictures/wallpapers/mountain.jpg --backend colorz

# Use a pre-defined base16 scheme instead of extracting
wal --theme base16-monokai

# Restore last palette (fast, no image re-processing)
wal -R
```

### Output Files Written by pywal

| File | Format | Purpose |
|------|--------|---------|
| `~/.cache/wal/colors` | Shell `export` statements | Source in shell RC or scripts |
| `~/.cache/wal/colors.json` | JSON object | General-purpose palette JSON |
| `~/.cache/wal/colors.css` | CSS custom properties | Web content, GTK WebKit views |
| `~/.cache/wal/colors-waybar.css` | CSS `@define-color` | Waybar stylesheet |
| `~/.cache/wal/colors-kitty.conf` | Kitty `include`-able config | Kitty terminal |
| `~/.cache/wal/colors-wal-st.h` | C header | st terminal |
| `~/.cache/wal/colors-alacritty.toml` | TOML | Alacritty |
| `~/.cache/wal/colors-rofi.rasi` | Rofi rasi fragment | Rofi launcher |
| `~/.cache/wal/wal` | Plain text | Current wallpaper path |
| `~/.cache/wal/sequences` | Terminal escape sequences | Recolor running terminals |

### Applying pywal to Applications

Each application integration is a one-liner that points at the relevant cache
file. For terminals the integration is usually a single `include` or `source`
directive. For GTK, pywal writes a full GTK theme to `~/.themes/wal/` which
you then activate with `gsettings` or your GTK theme manager.

**Kitty** reads the generated file at startup via a top-level `include`
directive. For live reloading of a running Kitty instance, send the config
via the Kitty socket:

```ini
# ~/.config/kitty/kitty.conf
include ~/.cache/wal/colors-kitty.conf
```

```bash
# Live-reload colors into every running Kitty window
kitty @ set-colors --all --configured ~/.cache/wal/colors-kitty.conf
```

**Waybar** accepts a CSS `@import` at the top of `style.css`. The generated
`colors-waybar.css` uses GTK's `@define-color` syntax:

```css
/* ~/.config/waybar/style.css */
@import "colors-waybar.css";   /* resolves relative to $HOME/.cache/wal/ if symlinked */

window#waybar {
    background-color: @background;
    color: @foreground;
}

#workspaces button.active {
    background-color: @color4;
    color: @background;
}
```

```bash
# Because Waybar reads style.css at startup, reload it after wal runs
pkill -SIGUSR2 waybar
```

**Dunst** does not support live CSS injection, so supply colors as command-line
arguments in a wrapper script, or source `~/.cache/wal/colors` before calling
dunstctl:

```bash
#!/bin/bash
# ~/.config/dunst/launch-dunst.sh
source ~/.cache/wal/colors

dunst \
  -background  "$color0" \
  -foreground  "$foreground" \
  -highlight   "$color4" \
  -frame_color "$color8" &
```

**GTK apps** use the generated GTK theme. Apply it without a desktop-manager
restart:

```bash
gsettings set org.gnome.desktop.interface gtk-theme 'wal'
```

**Quickshell** can read `colors.json` using a `FileView` block and reload
automatically whenever pywal regenerates the file:

```qml
// In your Quickshell QML
import Quickshell
import Quickshell.Io

FileView {
    id: walColors
    path: Qt.resolvedUrl(Quickshell.env("HOME") + "/.cache/wal/colors.json")
    onTextChanged: {
        let palette = JSON.parse(walColors.text);
        root.bgColor  = palette.colors.color0.hex;
        root.fgColor  = palette.special.foreground.hex;
        root.accent   = palette.colors.color4.hex;
    }
}
```

---

## 38.2 matugen — Material You Extraction

matugen implements Google's Material You (Material Design 3) dynamic color
algorithm in Rust. Rather than mapping quantized image colors directly to
terminal slots, it derives a full set of Material color roles — primary,
secondary, tertiary, error, surface, and all their on-/container- variants —
from a single seed color extracted from the image. The result is a
perceptually coherent color system suitable for modern UI components, not just
terminal recoloring.

matugen is the extraction engine of choice for setups built on Quickshell and
Hyprland, particularly the popular `end_4` dotfiles. Its template system
handles arbitrary output formats: you provide Tera templates and matugen
substitutes color-role tokens, writing each output file in a single pass.

```bash
# Install matugen (binary from GitHub releases or cargo)
cargo install matugen
# or download from https://github.com/InioX/matugen/releases

# Extract from an image, dark scheme
matugen image ~/Pictures/wallpapers/mountain.jpg --mode dark

# Light scheme
matugen image ~/Pictures/wallpapers/mountain.jpg --mode light

# Amoled (pure-black surfaces)
matugen image ~/Pictures/wallpapers/mountain.jpg --mode dark --type fruit-salad-dark

# Output only JSON (for scripting)
matugen image ~/Pictures/wallpapers/mountain.jpg --json hex > /tmp/palette.json

# Use a hex seed color directly instead of an image
matugen color hex "#6750A4" --mode dark
```

### Material You Color Roles

| Role | Typical Use |
|------|-------------|
| `primary` | Key interactive components, FABs |
| `on-primary` | Text/icons on primary surfaces |
| `primary-container` | Less prominent, tinted fill |
| `secondary` | Alternative interactive accents |
| `tertiary` | Contrasting accent for special UI |
| `surface` | Default backgrounds |
| `surface-variant` | Slightly tinted surface (cards) |
| `error` | Destructive actions, alerts |
| `outline` | Borders, dividers |

### matugen Config and Template System

The config file at `~/.config/matugen/config.toml` maps template input files
to output paths. After running `matugen image ...`, every listed template is
rendered and written atomically:

```toml
# ~/.config/matugen/config.toml

[config]
reload_gtk_theme = true          # run gsettings after generation
set_wallpaper = false            # let swww handle wallpaper separately

[config.templates.waybar]
input_path  = "~/.config/waybar/style.css.tera"
output_path = "~/.config/waybar/style.css"

[config.templates.dunst]
input_path  = "~/.config/dunst/dunstrc.tera"
output_path = "~/.config/dunst/dunstrc"

[config.templates.kitty]
input_path  = "~/.config/kitty/colors.conf.tera"
output_path = "~/.cache/matugen/colors-kitty.conf"

[config.templates.hyprland_colors]
input_path  = "~/.config/hypr/colors.conf.tera"
output_path = "~/.config/hypr/colors.conf"

[config.templates.rofi]
input_path  = "~/.config/rofi/colors.rasi.tera"
output_path = "~/.config/rofi/colors.rasi"
```

Tera template syntax uses `{{colors.<role>.default.hex}}` for hex values and
`{{colors.<role>.default.rgb.r}}` / `.g` / `.b` for RGB components:

```css
/* ~/.config/waybar/style.css.tera */
:root {
    --primary:           {{colors.primary.default.hex}};
    --on-primary:        {{colors.on_primary.default.hex}};
    --primary-container: {{colors.primary_container.default.hex}};
    --secondary:         {{colors.secondary.default.hex}};
    --surface:           {{colors.surface.default.hex}};
    --on-surface:        {{colors.on_surface.default.hex}};
    --error:             {{colors.error.default.hex}};
    --outline:           {{colors.outline.default.hex}};
}

window#waybar {
    background-color: var(--surface);
    color:            var(--on-surface);
}

#workspaces button.active {
    background-color: var(--primary-container);
    color:            var(--on-primary);
}
```

```ini
# ~/.config/kitty/colors.conf.tera — generated kitty color config
foreground           {{colors.on_surface.default.hex}}
background           {{colors.surface.default.hex}}
selection_foreground {{colors.on_primary_container.default.hex}}
selection_background {{colors.primary_container.default.hex}}

color0   {{colors.surface_variant.default.hex}}
color1   {{colors.error.default.hex}}
color2   {{colors.tertiary.default.hex}}
color3   {{colors.secondary.default.hex}}
color4   {{colors.primary.default.hex}}
color5   {{colors.tertiary_container.default.hex}}
color6   {{colors.secondary_container.default.hex}}
color7   {{colors.on_surface.default.hex}}
color8   {{colors.outline.default.hex}}
color9   {{colors.error_container.default.hex}}
color10  {{colors.tertiary.default.hex}}
color11  {{colors.secondary.default.hex}}
color12  {{colors.primary_container.default.hex}}
color13  {{colors.tertiary_container.default.hex}}
color14  {{colors.secondary_container.default.hex}}
color15  {{colors.surface.default.hex}}
```

---

## 38.3 wallust — Modern pywal Alternative

wallust is a Rust rewrite of pywal's output layer with an improved color
engine. It is binary-compatible with pywal's cache layout, so any script that
sources `~/.cache/wal/colors` works identically with wallust. The primary
advantages over pywal are speed (no Python startup overhead), better handling
of low-saturation source images, and a richer built-in colorscheme library.

```bash
# Install
cargo install wallust
# or from AUR: paru -S wallust

# Generate palette from image (writes to ~/.cache/wal/ like pywal)
wallust run ~/Pictures/wallpapers/mountain.jpg

# Light/dark override
wallust run --colorspace lch ~/Pictures/wallpapers/mountain.jpg

# Apply a built-in scheme instead of extracting
wallust cs catppuccin-mocha

# List built-in colorschemes
wallust cs --list

# Check current palette
wallust check
```

wallust supports the same downstream integrations as pywal because it writes
the same files to `~/.cache/wal/`. Swap `wal -i` for `wallust run` in any
pywal-based script and nothing else changes.

```bash
# ~/.config/wallust/wallust.toml
[wallust]
backend       = "kmeans"         # kmeans | dark | light | saturate | ...
colorspace    = "lch"            # lab | lch | rgb
filter        = "dark"           # dark | light | (empty)
check_contrast = true
```

---

## 38.4 wpgtk — GUI Front-End for pywal

wpgtk is a GTK GUI wrapper around pywal that adds palette management, a live
preview panel, and a library of saved themes. It does not replace pywal; it
calls `wal` internally and augments it with persistence and interactivity. For
users who prefer a point-and-click workflow or need to compare multiple saved
palettes, wpgtk provides a polished interface. For scripted or daemon-driven
workflows, invoking `wal`/`wallust`/`matugen` directly is simpler.

```bash
# Install
pip install wpgtk   # or via AUR: paru -S wpgtk

# Launch GUI
wpg

# CLI: add an image to the wpgtk library and generate its palette
wpg -a ~/Pictures/wallpapers/mountain.jpg

# Set theme by image name
wpg -s mountain.jpg

# Export current palette to a named theme file
wpg -x my-mountain-theme

# Apply a saved theme
wpg -m my-mountain-theme
```

wpgtk persists palette data in `~/.config/wpg/` and maintains a GTK theme at
`~/.themes/FlatColor`. It can apply color changes to GTK apps in real-time via
`gsettings` hooks, making it particularly useful when you want to preview a
palette before committing it to your startup flow.

---

## 38.5 Applying Palettes to Terminals

Every major Wayland-era terminal supports dynamic color injection either
through config file reloading or a live IPC socket. The distinction matters:
config-reload-only terminals (Alacritty, Foot) require a process restart or a
SIGHUP to pick up new colors, while socket-capable terminals (Kitty, WezTerm)
accept color changes without closing open sessions.

| Terminal | Mechanism | Live Reload? |
|----------|-----------|-------------|
| Kitty | `kitty @ set-colors` | Yes, via socket |
| WezTerm | Lua `wezterm.reload_configuration()` + FileView | Yes, on config change |
| Alacritty | Edit `colors.toml`, send SIGHUP | Yes (SIGHUP) |
| Foot | Source new `colors.ini` section, restart | No socket API |
| ghostty | `ghostty +reload-config` | Partial |

```bash
# Kitty — instant recolor of all open windows
kitty @ set-colors --all --configured ~/.cache/wal/colors-kitty.conf

# Alacritty — write colors section, then signal
# First generate ~/.config/alacritty/colors.toml from template, then:
pkill -HUP alacritty

# Foot — colors are set via footrc [colors] section; restart required
foot --config ~/.config/foot/foot.ini &
```

For Alacritty, maintain a Tera or envsubst template and regenerate it as part
of your theme script:

```toml
# ~/.config/alacritty/colors.toml.template
[colors.primary]
background = "${color0}"
foreground = "${foreground}"

[colors.normal]
black   = "${color0}"
red     = "${color1}"
green   = "${color2}"
yellow  = "${color3}"
blue    = "${color4}"
magenta = "${color5}"
cyan    = "${color6}"
white   = "${color7}"

[colors.bright]
black   = "${color8}"
red     = "${color9}"
green   = "${color10}"
yellow  = "${color11}"
blue    = "${color12}"
magenta = "${color13}"
cyan    = "${color14}"
white   = "${color15}"
```

```bash
# Substitute from pywal-sourced environment
source ~/.cache/wal/colors
envsubst < ~/.config/alacritty/colors.toml.template \
         > ~/.config/alacritty/colors.toml
pkill -HUP alacritty
```

---

## 38.6 Applying Palettes to Firefox

Firefox applies custom CSS via a user-installed extension. The two main
approaches are `pywalfox` for pywal output and the **Firefox Color** extension
for a click-through GUI.

```bash
# Install pywalfox
pip install pywalfox

# Install the native messaging host (run once)
pywalfox install

# After pywalfox is installed and the Firefox extension is active:
# Running wal automatically triggers Firefox recolor via the native host.
# You can also trigger it manually:
pywalfox update
```

For the native host to work, Firefox must be fully started before pywalfox
attempts a connection. In a session-startup script, add a short guard:

```bash
# Wait until Firefox socket is ready
until pywalfox update 2>/dev/null; do sleep 1; done
```

Alternatively, use `wal-firefox` which writes a `userChrome.css`-compatible
file to the Firefox profile:

```bash
pip install wal-firefox

# After wal runs:
wal-firefox         # reads ~/.cache/wal/colors.json, writes to FF profile
```

---

## 38.7 Applying Palettes to GTK and Qt Apps

pywal writes a GTK 2/3 theme to `~/.themes/wal/` and a GTK 3 CSS file. Activate
it once; subsequent `wal` runs overwrite the theme files and the color change is
visible on next GTK app launch or after an xsettings reload:

```bash
# Activate the wal GTK theme
gsettings set org.gnome.desktop.interface gtk-theme 'wal'
gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'

# For GTK 4 apps you may also need:
gsettings set org.gnome.desktop.interface gtk-theme 'wal'
ln -sf ~/.themes/wal ~/.config/gtk-4.0/gtk.css 2>/dev/null || true
```

For Qt apps, use `qt5ct` / `qt6ct` with the Kvantum theme engine. matugen can
generate a Kvantum theme file via a template:

```ini
# ~/.config/matugen/templates/kvantum.kvconfig.tera
[General]
author=matugen
comment=Dynamic Material You theme

[Hacks]
transparent_ktitle_label=false

[PanelButtonCommand]
frame=true
frame.element=button
interior=true
interior.element=button
text.normal.color={{colors.on_surface.default.hex}}
text.focus.color={{colors.on_primary_container.default.hex}}
```

---

## 38.8 Systemwide Palette Consistency

The core challenge of dynamic theming is that each application reads its colors
from a different source and in a different format. A consistent workflow
requires a single authoritative palette source that fans out to every
application. The four main strategies, ranked by integration depth:

| Approach | Tool | Consistency | Maintenance |
|----------|------|-------------|-------------|
| Declarative, whole-system | Stylix (NixOS) | Highest | Config-driven |
| Template-based fan-out | matugen templates | Very high | Template per app |
| pywal output files | pywal / wallust | High (where supported) | Low |
| Manual per-app editing | Any editor | Total control | Very high |

For non-NixOS setups, matugen's template system is the closest to Stylix-level
automation. Define one template per application, run `matugen image` once, and
every output file is updated atomically before any reload signal is sent.

```toml
# Full matugen config.toml for a consistent setup
[config]
reload_gtk_theme = true

[config.templates.waybar]
input_path  = "~/.config/waybar/style.css.tera"
output_path = "~/.config/waybar/style.css"

[config.templates.hyprland]
input_path  = "~/.config/hypr/colors.conf.tera"
output_path = "~/.config/hypr/colors.conf"

[config.templates.kitty]
input_path  = "~/.config/kitty/colors.conf.tera"
output_path = "~/.cache/matugen/colors-kitty.conf"

[config.templates.dunst]
input_path  = "~/.config/dunst/dunstrc.tera"
output_path = "~/.config/dunst/dunstrc"

[config.templates.rofi]
input_path  = "~/.config/rofi/colors.rasi.tera"
output_path = "~/.config/rofi/colors.rasi"

[config.templates.alacritty]
input_path  = "~/.config/alacritty/colors.toml.tera"
output_path = "~/.config/alacritty/colors.toml"
```

Hyprland can source a colors file with `source = colors.conf`. The template
produces `$primary`, `$surface` etc. as Hyprland variables:

```ini
# ~/.config/hypr/colors.conf.tera
$primary    = rgb({{colors.primary.default.hex | replace(from="#", to="")}})
$on_primary = rgb({{colors.on_primary.default.hex | replace(from="#", to="")}})
$surface    = rgb({{colors.surface.default.hex | replace(from="#", to="")}})
$error      = rgb({{colors.error.default.hex | replace(from="#", to="")}})
```

```ini
# ~/.config/hypr/hyprland.conf
source = ~/.config/hypr/colors.conf

general {
    col.active_border   = $primary
    col.inactive_border = $surface
}
```

---

## 38.9 End-to-End Dynamic Theming Script

The script below ties together swww (wallpaper), matugen (extraction and
template rendering), reload signals, and notifications. It is designed to be
called as `~/.local/bin/wallpaper-set <image>` and is suitable for binding to
a keyboard shortcut or calling from a wallpaper picker.

```bash
#!/usr/bin/env bash
# ~/.local/bin/wallpaper-set
# Usage: wallpaper-set <path-to-image>
set -euo pipefail

WALL="${1:?Usage: wallpaper-set <image>}"
WALL="$(realpath "$WALL")"

if [[ ! -f "$WALL" ]]; then
    echo "Error: file not found: $WALL" >&2
    exit 1
fi

# ── 1. Set wallpaper via swww ────────────────────────────────────────────
swww img "$WALL" \
    --transition-type  wipe \
    --transition-angle 30 \
    --transition-duration 1.2 \
    --transition-fps 60

# ── 2. Extract Material You palette and render all templates ─────────────
matugen image "$WALL" --mode dark

# ── 3. Reload Waybar ─────────────────────────────────────────────────────
pkill -SIGUSR2 waybar 2>/dev/null || true

# ── 4. Reload Dunst ──────────────────────────────────────────────────────
pkill dunst 2>/dev/null || true
dunst &

# ── 5. Reload Kitty colors (all open windows) ────────────────────────────
if command -v kitty &>/dev/null && kitty @ --to unix:/tmp/kitty-listen ls &>/dev/null; then
    kitty @ --to unix:/tmp/kitty-listen \
        set-colors --all --configured \
        ~/.cache/matugen/colors-kitty.conf 2>/dev/null || true
fi

# ── 6. Reload Alacritty (SIGHUP) ─────────────────────────────────────────
pkill -HUP alacritty 2>/dev/null || true

# ── 7. Reload Hyprland border colors ─────────────────────────────────────
# hyprland.conf sources colors.conf; reload config
hyprctl reload 2>/dev/null || true

# ── 8. Notify ─────────────────────────────────────────────────────────────
notify-send --icon "$WALL" \
    "Theme Applied" \
    "Colors extracted from $(basename "$WALL")"

echo "Done: $(basename "$WALL")"
```

Make the script executable and add an optional pywal fallback for terminals
that need the pywal cache format:

```bash
chmod +x ~/.local/bin/wallpaper-set

# If you also need pywal-format output (e.g. for pywalfox):
# Add to the script after matugen:
wal -i "$WALL" -n --backend colorz 2>/dev/null || true
# -n skips setting the wallpaper (swww already did it)
```

For a pywal-only workflow (simpler, no Material You):

```bash
#!/usr/bin/env bash
# ~/.local/bin/wallpaper-set-wal
set -euo pipefail
WALL="${1:?Usage: wallpaper-set-wal <image>}"

swww img "$WALL" --transition-type fade --transition-duration 1

wal -i "$WALL" --backend colorz -n

# Reload consumers
pkill -SIGUSR2 waybar 2>/dev/null || true
kitty @ set-colors --all ~/.cache/wal/colors-kitty.conf 2>/dev/null || true
pywalfox update 2>/dev/null || true

notify-send "Wallpaper" "$(basename "$WALL")"
```

---

## 38.10 Quickshell Integration

Quickshell's `FileView` QML type watches a file for changes and exposes its
content as a string. Because matugen and pywal both write JSON palette files,
you can drive your entire Quickshell UI from the dynamically generated palette
with zero explicit IPC. See **Chapter 29** for full `FileView` documentation.

```qml
// PaletteProvider.qml — singleton that exposes dynamic colors
import Quickshell
import Quickshell.Io
import QtQuick

QtObject {
    id: root

    // Exposed palette properties
    property color primary:   "#6750A4"
    property color onPrimary: "#FFFFFF"
    property color surface:   "#1C1B1F"
    property color onSurface: "#E6E1E5"
    property color error:     "#F2B8B5"

    // FileView watching matugen JSON output
    property FileView _view: FileView {
        path: Quickshell.env("HOME") + "/.cache/matugen/colors.json"
        onTextChanged: root._apply(text)
    }

    function _apply(text) {
        try {
            let p = JSON.parse(text).colors;
            root.primary   = p.primary.default.hex;
            root.onPrimary = p.on_primary.default.hex;
            root.surface   = p.surface.default.hex;
            root.onSurface = p.on_surface.default.hex;
            root.error     = p.error.default.hex;
        } catch(e) {
            console.warn("PaletteProvider: parse error:", e);
        }
    }
}
```

```qml
// Bar.qml — consuming palette colors
import Quickshell

Item {
    anchors.fill: parent

    Rectangle {
        color: PaletteProvider.surface
        // ...
    }
}
```

For pywal JSON format the structure differs slightly:

```qml
// pywal JSON structure: { "colors": { "color0": { "hex": "#..." } },
//                         "special": { "foreground": { "hex": "#..." } } }
function _applyWal(text) {
    let p = JSON.parse(text);
    root.surface   = p.colors.color0.hex;
    root.primary   = p.colors.color4.hex;
    root.onSurface = p.special.foreground.hex;
}
```

---

## Troubleshooting

**matugen produces no output files**
Check that `~/.config/matugen/config.toml` exists and the `input_path` files
exist. Run `matugen image <file> --verbose` to see which templates are being
processed. Template paths must be absolute or use `~` expansion.

```bash
matugen image ~/Pictures/test.jpg --mode dark --verbose 2>&1 | head -40
```

**pywal colors look washed out or too dark**
The default `wal` backend (ImageMagick) sometimes clips saturation. Try
`--backend colorz` or `--backend colorthief`. You can also use `--saturate 0.8`
to boost saturation of the output:

```bash
wal -i wallpaper.jpg --backend colorz --saturate 0.8
```

**Waybar does not pick up new colors after reloading**
Verify that `@import` in `style.css` resolves correctly. If the path uses
`~/.cache/...`, GTK `@import` may not expand `~`. Use an absolute path or a
symlink inside `~/.config/waybar/`:

```bash
ln -sf ~/.cache/wal/colors-waybar.css ~/.config/waybar/colors-waybar.css
# In style.css:
@import "colors-waybar.css";
```

Then: `pkill -SIGUSR2 waybar`.

**Kitty `@ set-colors` fails with "Connection refused"**
Kitty's remote-control socket is disabled by default. Enable it:

```ini
# ~/.config/kitty/kitty.conf
allow_remote_control yes
listen_on unix:/tmp/kitty-listen
```

Then restart Kitty and use `kitty @ --to unix:/tmp/kitty-listen set-colors ...`.

**hyprctl reload resets keybinds or other settings**
`hyprctl reload` re-reads the entire `hyprland.conf`. If colors are in a
`source`d file, only that file changes — but `hyprctl reload` still replays
everything. The workaround is to keep color variables in their own sourced file
and accept the full reload, or use `hyprctl keyword` to update individual
properties:

```bash
# Read generated color and apply without full reload
PRIMARY=$(grep '^\$primary' ~/.config/hypr/colors.conf | awk '{print $3}')
hyprctl keyword general:col.active_border "$PRIMARY" 2>/dev/null
```

**Firefox native host not connecting (pywalfox)**
Run `pywalfox install` again after any Firefox update. Check that the native
messaging manifest is present:

```bash
ls ~/.mozilla/native-messaging-hosts/pywalfox.json
# If missing:
pywalfox install
```

**swww transition flickers before colors are applied**
The transition completes before matugen finishes and reloads are sent.
Add a short wait after swww returns, or chain matugen as a post-transition
hook:

```bash
swww img "$WALL" --transition-duration 1 && \
    matugen image "$WALL" --mode dark && \
    pkill -SIGUSR2 waybar 2>/dev/null
```

**wallust generates low-saturation colors from muted wallpapers**
Use the `saturate` filter:

```bash
wallust run --filter saturate ~/Pictures/wallpapers/foggy.jpg
```

Or switch the colorspace: `--colorspace lch` tends to preserve perceptual
saturation better than the default `lab` for muted images.

---

*Related chapters: **Ch 29** (Quickshell FileView and live config), **Ch 40**
(Stylix declarative theming on NixOS), **Ch 53** (session startup and daemon
ordering), **Ch 20** (swww wallpaper daemon).*

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
