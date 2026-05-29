# Chapter 70 — Color Picker Tools: hyprpicker, wl-color-picker, gpick

## Overview

Sampling colors from the screen is a fundamental step in building cohesive desktop themes. On X11, tools like `gcolor2`, `xcolor`, `xdotool`, and `gpick` used XQueryPointer and XGetImage to capture pixel data — mechanisms that simply do not exist in the Wayland security model. On Wayland, a client cannot read from another client's surface without compositor cooperation via the `wlr-screencopy-v1` or `ext-image-capture-source-v1` protocols.

This chapter covers the full color-picking toolkit available for Wayland-native and wlroots-based compositors: CLI pickers with screencopy integration, GUI tools running natively or via XWayland, and the `pastel` color manipulation library that bridges them all. You will also learn to build a complete color-extraction pipeline from wallpaper to palette to applied theme config.

The tools covered here integrate tightly with the theming chapters: hyprpicker feeds naturally into pywal (Ch 37), matugen (Ch 38), and wpgtk (Ch 39). If you are building a dynamic theming pipeline, read those chapters alongside this one. For keybind setup to launch pickers, see Ch 53 (Hyprland keybinding reference). For clipboard integration (`wl-copy`/`wl-paste`), see Ch 45.

---

## Tool Comparison

| Tool | Backend | Wayland Native | GUI | Output Formats | Palette Save |
|---|---|---|---|---|---|
| hyprpicker | wlr-screencopy | Yes | No (CLI) | hex, rgb, hsl | No |
| wl-color-picker | portal / GTK | Yes | Yes | hex | No |
| gpick | XWayland | No (XWayland) | Yes | GPL, CSS, JSON | Yes |
| kcolorchooser | Qt6/KWin | Yes | Yes | hex, rgb, cmyk | Yes |
| wf-color-picker | wlr-screencopy | Yes | Minimal | hex | No |
| pastel | (offline) | N/A | No (CLI) | hex, rgb, hsl, lab | Palette |
| colorpicker (Rust) | wlr-screencopy | Yes | No (CLI) | hex, rgb | No |

For most ricing workflows, `hyprpicker` + `pastel` covers 90% of use cases on a wlroots compositor. `gpick` remains valuable when you need an interactive session building a multi-color palette.

---

## 70.1 hyprpicker — The Standard

hyprpicker is the de-facto Wayland color picker for Hyprland and any wlroots compositor. It uses the `wlr-screencopy-v1` protocol to freeze a screenshot of the whole screen into a fullscreen overlay, then tracks your cursor with a magnifier loupe until you click. The picked pixel's color is written to stdout. Because the overlay is a compositor surface and screencopy is explicitly granted, this is fully Wayland-native with no XWayland dependency.

Installation is straightforward on Arch-based systems; hyprpicker is available in the official extra repository as of 2024:

```bash
# Arch / EndeavourOS / Manjaro
sudo pacman -S hyprpicker

# If not yet in extra, use AUR
paru -S hyprpicker
# or
yay -S hyprpicker

# From source (requires wlroots headers, cmake, ninja)
git clone https://github.com/hyprwm/hyprpicker
cd hyprpicker
cmake -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr
cmake --build build
sudo cmake --install build
```

On non-Arch distros, check your package manager or build from source. Fedora users can find it in COPR `sentry/hyprland`. Debian/Ubuntu users will likely need to build from source as packaging lags behind.

### Basic Usage

```bash
# Click a pixel, prints hex to stdout, copies to clipboard automatically
hyprpicker

# Auto-accept: pick color on click without pressing Enter to confirm
hyprpicker -a

# Output format selection
hyprpicker -f hex      # #89b4fa  (default)
hyprpicker -f rgb      # rgb(137, 180, 250)
hyprpicker -f hsl      # hsl(217, 92%, 76%)
hyprpicker -f cmyk     # cmyk(45%, 28%, 0%, 2%)
hyprpicker -f oklch    # oklch(73.89% 0.1412 253.89)

# No trailing newline — useful in subshells
hyprpicker -a -n

# Render under cursor as magnified loupe at specific zoom
hyprpicker --zoom-factor=3.0

# Cancel with Escape or right-click
```

### Shell Integration

The most useful pattern is to capture the color into a variable and pipe it both to the clipboard and a notification daemon:

```bash
#!/usr/bin/env bash
# ~/.local/bin/pick-color
# Requires: hyprpicker, wl-copy, notify-send (libnotify)

color=$(hyprpicker -a -n -f hex)

if [[ -n "$color" ]]; then
    printf '%s' "$color" | wl-copy
    notify-send "Color Picked" "$color" \
        --icon=color-picker \
        --expire-time=3000 \
        --hint=string:x-canonical-private-synchronous:pick-color
fi
```

Make the script executable and wire it to a keybind:

```conf
# ~/.config/hypr/hyprland.conf
bind = SUPER, C, exec, ~/.local/bin/pick-color
```

For a format-cycling workflow — different bindings pick in different formats:

```bash
#!/usr/bin/env bash
# ~/.local/bin/pick-color-format
# Usage: pick-color-format [hex|rgb|hsl|oklch]
FORMAT="${1:-hex}"
color=$(hyprpicker -a -n -f "$FORMAT")
if [[ -n "$color" ]]; then
    printf '%s' "$color" | wl-copy
    notify-send "Color ($FORMAT)" "$color" --expire-time=2000
fi
```

```conf
# hyprland.conf keybinds
bind = SUPER, C,       exec, ~/.local/bin/pick-color-format hex
bind = SUPER SHIFT, C, exec, ~/.local/bin/pick-color-format rgb
bind = SUPER ALT, C,   exec, ~/.local/bin/pick-color-format hsl
```

### Saving to a Color Log

For building a persistent color history you can reference later:

```bash
#!/usr/bin/env bash
# ~/.local/bin/pick-and-log
LOGFILE="$HOME/.local/share/color-picks.log"
mkdir -p "$(dirname "$LOGFILE")"

color=$(hyprpicker -a -n -f hex)
if [[ -n "$color" ]]; then
    printf '%s' "$color" | wl-copy
    echo "$(date -Iseconds) $color" >> "$LOGFILE"
    notify-send "Picked & Saved" "$color" --expire-time=2000
fi
```

View your color history with a fzf preview:

```bash
# Browse color history with fzf, re-copy selected
cat ~/.local/share/color-picks.log | \
    fzf --preview 'echo {2}' | \
    awk '{print $2}' | \
    tr -d '\n' | \
    wl-copy
```

---

## 70.2 wl-color-picker

wl-color-picker provides a GTK4 dialog-based color picker that also integrates with the XDG desktop portal's screenshot capability. Rather than a fullscreen overlay, it presents a color wheel and slider interface, making it more approachable for users who prefer GUI interaction or who need to fine-tune a color before committing.

The tool supports both direct screen sampling (click anywhere) and the GTK color chooser dialog for manual entry. Output is written to stdout and optionally copied to clipboard.

```bash
# Install from AUR
paru -S wl-color-picker
# or
yay -S wl-color-picker

# Basic usage — opens GUI, copies result
wl-color-picker

# Print to stdout only (no clipboard copy)
wl-color-picker --no-copy

# Start with a specific color pre-loaded
wl-color-picker --color "#89b4fa"
```

wl-color-picker is more GUI-friendly than hyprpicker — it shows a color wheel, RGB/HSL sliders, and a hex input field. This makes it useful when you have an approximate color in mind and want to dial it in precisely, rather than sampling a specific pixel. It runs natively on GNOME (via the portal) and on wlroots compositors.

Integration with a keybind:

```conf
# hyprland.conf
bind = SUPER SHIFT, P, exec, wl-color-picker
```

For GNOME users who want a portal-based picker instead of the fullscreen overlay approach:

```bash
# Uses xdg-desktop-portal-gnome for screen sampling on GNOME
wl-color-picker
```

---

## 70.3 gpick — Advanced GUI Color Picker

gpick is a powerful desktop color picker with magnifier zoom, multiple sampling modes, a built-in palette manager, and export to GPL (GIMP palette), CSS, and JSON. It predates Wayland and runs via XWayland on non-X11 compositors, but the functionality it provides — especially interactive palette building over a session — is unmatched by CLI tools.

```bash
# Arch
sudo pacman -S gpick

# Debian / Ubuntu
sudo apt install gpick

# Fedora
sudo dnf install gpick
```

Running gpick under Wayland requires XWayland to be running. On Hyprland, XWayland is typically enabled by default. On sway, ensure `xwayland enable` is in your config:

```conf
# ~/.config/sway/config
xwayland enable
```

gpick will launch as an XWayland window and is fully functional. The limitation is that it cannot sample from native Wayland surfaces without XWayland compositing them first — you may see incorrect colors on HDR surfaces or surfaces with non-standard color spaces.

### gpick Feature Walkthrough

gpick's main window has several functional panels:

**Sampler panel** — The main color picking area. Press `Space` to pick the color under the cursor. The magnifier shows a zoomed view of the area around the cursor.

**Palette panel** — A scrollable list of saved colors. Right-click to rename, reorder, or delete. Drag colors between palette slots.

**Color difference panel** — Compare two colors side by side with Delta-E (CIE76/94/2000) perceptual distance calculations.

**Export formats:**

```
File > Export > GIMP Palette (.gpl)   — for GIMP, Inkscape
File > Export > CSS                   — var(--color-name: #hex)
File > Export > JSON                  — {"name": "#hex", ...}
File > Export > Plain text            — one hex per line
```

**Keyboard shortcuts in gpick:**

| Key | Action |
|---|---|
| Space | Pick color under cursor |
| A | Add current color to palette |
| Ctrl+Z | Undo last palette add |
| Ctrl+C | Copy hex to clipboard |
| D | Show color difference |
| M | Change sampling mode |
| +/- | Zoom magnifier in/out |

### gpick Configuration

gpick stores its config in `~/.config/gpick/gpick.conf` (INI format):

```ini
[Sampler]
oversample_quality = 1
oversample_size = 15
zoom_size = 150
magnified_brightness = 100

[Floats]
enable = true
always_on_top = true

[Display]
transformation = srgb
colorspaceconversion = true
```

### Exporting a gpick Palette to Hyprland

After building a palette in gpick, export as plain text and use it in your Hyprland config:

```bash
# gpick-to-hyprland.sh
# Reads a plain text palette (one #hex per line) and prints Hyprland color vars
while IFS= read -r line; do
    [[ "$line" =~ ^#[0-9A-Fa-f]{6}$ ]] || continue
    hex="${line#\#}"
    echo "# rgb(0x${hex:0:2}, 0x${hex:2:2}, 0x${hex:4:2})"
    echo "# $line"
done < palette.txt
```

---

## 70.4 kcolorchooser — KDE Color Picker

kcolorchooser is a Qt6 color picker from the KDE Frameworks ecosystem. It runs natively on Wayland via KWayland and is useful outside of KDE/Plasma in any Qt-friendly environment.

```bash
# Arch
sudo pacman -S kcolorchooser

# Also available as part of kde-graphics group
sudo pacman -S kde-graphics
```

kcolorchooser supports CMYK, RGB, HSV, and hex input modes in addition to screen sampling. The screen sampling on native Wayland uses the KWin screencopy path and works correctly on Plasma. On wlroots compositors, the screen-pick button may be non-functional (it falls back to XWayland portal behavior), but the manual color entry and history features work fine.

The tool maintains a recently-used color history across launches via `~/.config/kcolorchooserrc`:

```ini
[Recent colors]
History=#89b4fa,#cba6f7,#f38ba8,#a6e3a1
MaxColors=12
```

Launch from command line with a preset color:

```bash
kcolorchooser --color "#89b4fa"
```

kcolorchooser is particularly useful in KDE/Plasma-integrated ricing workflows where you also use KDE color scheme files (`.colors`). See Ch 62 for KDE color scheme management.

---

## 70.5 Color Picking in Quickshell

Quickshell (Ch 71) can embed a color picking workflow directly into the bar or as a floating panel. Since Quickshell uses Qt Quick (QML), you can spawn `hyprpicker` as a child process and handle its output reactively.

```qml
// ColorPickerButton.qml
// A button in the Quickshell bar that launches hyprpicker and displays the result

import Quickshell
import Quickshell.Io
import QtQuick
import QtQuick.Controls

Item {
    id: root
    property string lastColor: "#89b4fa"
    property bool picking: false

    Rectangle {
        width: 24; height: 24
        radius: 12
        color: root.lastColor
        border.color: "#ffffff"
        border.width: 1

        MouseArea {
            anchors.fill: parent
            onClicked: pickerProcess.running = true
        }
    }

    Process {
        id: pickerProcess
        command: ["hyprpicker", "-a", "-n", "-f", "hex"]
        running: false

        onRunningChanged: {
            if (running) root.picking = true
        }

        stdout: StdioCollector {
            onStreamFinished: {
                var color = text.trim()
                if (color.length > 0) {
                    root.lastColor = color
                    root.picking = false
                    // Copy to clipboard via wl-copy
                    clipboardProcess.running = true
                }
            }
        }
    }

    Process {
        id: clipboardProcess
        command: ["wl-copy", root.lastColor]
        running: false
    }
}
```

For a color history swatch panel in Quickshell:

```qml
// ColorHistory.qml
// Shows last N picked colors as swatches

import Quickshell
import QtQuick
import QtQuick.Layouts

RowLayout {
    id: root
    spacing: 4

    property var colorHistory: []
    property int maxHistory: 8

    function addColor(hex) {
        // Prepend new color, trim to maxHistory
        colorHistory = [hex].concat(colorHistory).slice(0, maxHistory)
    }

    Repeater {
        model: root.colorHistory
        delegate: Rectangle {
            width: 18; height: 18
            radius: 3
            color: modelData
            border.color: "#44ffffff"
            border.width: 1

            ToolTip.text: modelData
            ToolTip.visible: swatchHover.containsMouse
            ToolTip.delay: 500

            MouseArea {
                id: swatchHover
                anchors.fill: parent
                hoverEnabled: true
                onClicked: {
                    // Re-copy to clipboard on click
                    copyProc.running = true
                }
            }

            Process {
                id: copyProc
                command: ["wl-copy", modelData]
                running: false
            }
        }
    }
}
```

---

## 70.6 Color Format Conversion with pastel

pastel is a Rust CLI tool for color manipulation. It understands named colors, hex, RGB, HSL, Lab, LCh, and ANSI terminal colors, and can perform mixing, lightening, darkening, gradient generation, and colorblindness simulation. It is indispensable in automated ricing pipelines.

```bash
# Arch / AUR
sudo pacman -S pastel
# or
paru -S pastel

# Cargo (if Rust toolchain available)
cargo install pastel
```

### pastel Core Operations

```bash
# Show full info about a color (all representations + terminal preview)
pastel color "#89b4fa"
pastel color "steelblue"
pastel color "rgb(137, 180, 250)"

# Convert between formats
pastel format hex "#89b4fa"           # #89b4fa
pastel format rgb "#89b4fa"           # rgb(137, 180, 250)
pastel format hsl "#89b4fa"           # hsl(216.9, 92.1%, 76.1%)
pastel format lab "#89b4fa"           # Lab(73.9, 4.7, -36.8)
pastel format ansi-8bit "#89b4fa"     # ANSI 256-color nearest equivalent

# Lighten / darken by percentage (0.0–1.0)
pastel lighten 0.15 "#89b4fa"
pastel darken  0.15 "#89b4fa"

# Adjust saturation
pastel saturate   0.2 "#89b4fa"
pastel desaturate 0.2 "#89b4fa"

# Rotate hue by degrees
pastel rotate 30 "#89b4fa"

# Complement (opposite hue)
pastel complement "#89b4fa"

# Mix two colors (default 50/50)
pastel mix "#89b4fa" "#cba6f7"
pastel mix --fraction 0.3 "#89b4fa" "#cba6f7"

# Generate a gradient between two colors (N steps)
pastel gradient "#89b4fa" "#cba6f7" 7

# Show colorblindness simulation
pastel colorblind protanopia "#89b4fa"
pastel colorblind deuteranopia "#89b4fa"

# Compute perceptual contrast ratio (WCAG)
pastel textcolor "#89b4fa"   # suggests black or white text
pastel contrast "#89b4fa" "#1e1e2e"
```

### Shell Format Conversion Without pastel

If pastel is not available:

```bash
# hex to rgb (bash arithmetic)
hex_to_rgb() {
    local hex="${1#\#}"
    printf 'rgb(%d, %d, %d)\n' \
        "0x${hex:0:2}" "0x${hex:2:2}" "0x${hex:4:2}"
}
hex_to_rgb "#89b4fa"   # rgb(137, 180, 250)

# rgb to hex
rgb_to_hex() {
    printf '#%02x%02x%02x\n' "$1" "$2" "$3"
}
rgb_to_hex 137 180 250   # #89b4fa

# hex to Hyprland rgba() format (with alpha)
hex_to_hypr_rgba() {
    local hex="${1#\#}"
    local alpha="${2:-ff}"
    printf 'rgba(%sff)\n' "$hex"
    # Or with custom alpha:
    printf 'rgba(%s%s)\n' "$hex" "$alpha"
}
hex_to_hypr_rgba "#89b4fa"        # rgba(89b4faff)
hex_to_hypr_rgba "#89b4fa" "cc"   # rgba(89b4facc)

# Python one-liner: hex to (r, g, b) tuple
python3 -c "h='#89b4fa'; print(tuple(int(h[i:i+2],16) for i in (1,3,5)))"
# (137, 180, 250)
```

### Generating a Full Palette with pastel

```bash
#!/usr/bin/env bash
# generate-palette.sh
# Takes a base color and generates a full tonal palette
# Output: shell variable declarations suitable for sourcing

BASE="${1:-#89b4fa}"

echo "# Auto-generated palette from base: $BASE"
echo "BASE=\"$BASE\""
echo "BASE_LIGHT=\"$(pastel lighten 0.15 "$BASE" | pastel format hex)\""
echo "BASE_LIGHTER=\"$(pastel lighten 0.30 "$BASE" | pastel format hex)\""
echo "BASE_DARK=\"$(pastel darken 0.15 "$BASE" | pastel format hex)\""
echo "BASE_DARKER=\"$(pastel darken 0.30 "$BASE" | pastel format hex)\""
echo "ACCENT=\"$(pastel rotate 30 "$BASE" | pastel format hex)\""
echo "COMPLEMENT=\"$(pastel complement "$BASE" | pastel format hex)\""
echo "MUTED=\"$(pastel desaturate 0.4 "$BASE" | pastel format hex)\""
```

Run it:

```bash
chmod +x generate-palette.sh
./generate-palette.sh "#89b4fa"
# BASE="#89b4fa"
# BASE_LIGHT="#b5ccfb"
# BASE_LIGHTER="#dce8fd"
# BASE_DARK="#5e96f9"
# ...
```

---

## 70.7 Integrating Color Pickers into the Ricing Workflow

Building a cohesive color theme from scratch follows a repeatable pipeline:

1. **Start with a wallpaper or reference image** — visual anchor for the palette
2. **Extract dominant colors** — either from the image (automated) or by sampling with hyprpicker
3. **Refine the palette** — use pastel to derive backgrounds, foregrounds, and accents
4. **Apply to config files** — feed colors into Hyprland, waybar, terminal, GTK theme

### Extracting Colors from a Wallpaper

```bash
# Method 1: matugen (Material You derivation — see Ch 38)
matugen image ~/Pictures/wallpapers/current.jpg
# Writes colors to ~/.config/matugen/colors.json and template outputs

# Method 2: imagemagick histogram (top dominant colors)
convert ~/Pictures/wallpapers/current.jpg \
    -format "%c" -depth 8 histogram:info:- | \
    sort -rn | \
    head -20 | \
    grep -oP '#[0-9A-Fa-f]{6}' | \
    sort -u

# Method 3: pywal (see Ch 37) — generates full 16-color terminal palette
wal -i ~/Pictures/wallpapers/current.jpg --backend wal
cat ~/.cache/wal/colors        # one hex per line
cat ~/.cache/wal/colors.json   # full JSON with color names

# Method 4: colorz (pypi, ML-based dominant color extraction)
pip install colorz   # or: uv tool install colorz
colorz ~/Pictures/wallpapers/current.jpg --n 6
```

### Full Pipeline Script

```bash
#!/usr/bin/env bash
# rice-from-wallpaper.sh
# Complete pipeline: wallpaper -> palette -> Hyprland config patch

WALLPAPER="${1:?Usage: $0 <wallpaper_path>}"
HYPR_CONF="$HOME/.config/hypr/colors.conf"
WAYBAR_CSS="$HOME/.config/waybar/colors.css"

echo "[1/4] Setting wallpaper with swww..."
swww img "$WALLPAPER" --transition-type grow --transition-duration 1.5

echo "[2/4] Generating palette with matugen..."
matugen image "$WALLPAPER" --json > /tmp/rice-colors.json

# Extract key colors from matugen output
PRIMARY=$(jq -r '.colors.light.primary' /tmp/rice-colors.json)
BACKGROUND=$(jq -r '.colors.dark.background' /tmp/rice-colors.json)
SURFACE=$(jq -r '.colors.dark.surface' /tmp/rice-colors.json)
ON_BG=$(jq -r '.colors.dark.on_background' /tmp/rice-colors.json)

echo "[3/4] Writing Hyprland color overrides..."
cat > "$HYPR_CONF" <<EOF
# Auto-generated from: $WALLPAPER
# $(date -Iseconds)

\$primary    = rgb(${PRIMARY#\#})
\$background = rgb(${BACKGROUND#\#})
\$surface    = rgb(${SURFACE#\#})
\$on_bg      = rgb(${ON_BG#\#})
EOF

echo "[4/4] Writing waybar CSS variables..."
cat > "$WAYBAR_CSS" <<EOF
/* Auto-generated from: $WALLPAPER */
:root {
    --color-primary:    $PRIMARY;
    --color-background: $BACKGROUND;
    --color-surface:    $SURFACE;
    --color-on-bg:      $ON_BG;
}
EOF

# Reload Hyprland colors (source the colors.conf from hyprland.conf)
hyprctl reload

echo "Done. Palette applied from $WALLPAPER"
```

To source `colors.conf` from your main Hyprland config:

```conf
# ~/.config/hypr/hyprland.conf
source = ~/.config/hypr/colors.conf

general {
    col.active_border   = $primary $surface 45deg
    col.inactive_border = $background
}
```

### Sampling Colors Interactively for Theme Tuning

When adjusting a theme live, this interactive loop is useful:

```bash
#!/usr/bin/env bash
# interactive-sample.sh
# Pick colors one at a time, build a named palette

declare -A PALETTE
ROLES=("background" "surface" "primary" "secondary" "accent" "text" "muted")

for role in "${ROLES[@]}"; do
    echo "Pick color for role: $role (press Escape to skip)"
    color=$(hyprpicker -a -n -f hex)
    if [[ -n "$color" ]]; then
        PALETTE[$role]="$color"
        notify-send "$role" "$color" --expire-time=1500
    fi
done

echo ""
echo "# Palette summary"
for role in "${!PALETTE[@]}"; do
    printf '%-12s = %s\n' "$role" "${PALETTE[$role]}"
done
```

---

## 70.8 Additional Wayland-Compatible Color Tools

### wf-color-picker

A minimal wlroots-native color picker written for Wayfire. Works on any wlroots compositor:

```bash
paru -S wf-color-picker
wf-color-picker    # outputs hex to stdout
```

### colorpicker (Rust, wlr-screencopy)

A fast Rust implementation with minimal dependencies:

```bash
paru -S colorpicker
colorpicker --one-shot --short  # single pick, short hex output
```

### GNOME Color Picker (Eye of GNOME extension / Picker applet)

On GNOME 45+, the built-in color picker is available via the system menu or keyboard shortcut. It uses the org.freedesktop.portal.Screenshot portal:

```bash
# Trigger GNOME's built-in color picker via dbus
gdbus call \
    --session \
    --dest org.gnome.Shell \
    --object-path /org/gnome/Shell \
    --method org.gnome.Shell.Eval \
    'Main.overview._controls._appDisplay._pageIndicators; 0'
# (Use the GNOME Color Picker extension instead for a clean interface)

# Install via GNOME Extensions
# https://extensions.gnome.org/extension/3396/color-picker/
```

### xcalib and Display Calibration Colors

Not a color picker per se, but useful for understanding how color profile transformations affect sampled values:

```bash
# Check current ICC profile loaded for display
xcalib -p

# Load a specific ICC profile
xcalib /usr/share/color/icc/colord/sRGB.icc

# Note: on Wayland, ICC profiles are managed by colord / KWin / mutter
# hyprpicker samples post-compositor, so values reflect the actual displayed pixels
```

---

## Troubleshooting

### hyprpicker exits immediately without showing overlay

**Symptom:** `hyprpicker` returns immediately with no output and no overlay appears.

**Cause 1:** Your compositor does not support `wlr-screencopy-v1`. Verify:
```bash
wayland-info | grep wlr_screencopy
# If empty, your compositor lacks the protocol
```

**Cause 2:** A second instance is already running (rare deadlock). Kill it:
```bash
pkill hyprpicker
```

**Cause 3:** Missing `wlr-screencopy` support in the build (verify your package is not a stripped binary from an unofficial source):
```bash
hyprpicker --version
ldd $(which hyprpicker) | grep -i wayland
```

---

### hyprpicker color values look wrong (off by a shade)

**Symptom:** The hex value from hyprpicker doesn't match what you see visually.

**Cause:** Night-light / blue-light filter (gammastep, wlsunset, Hyprland's built-in temperature) is active. hyprpicker samples the composited buffer including color transformations.

**Fix:** Disable the color filter before picking, or account for the gamma shift:
```bash
# Temporarily disable Hyprland temperature adjustment
hyprctl keyword decoration:screen_shader ""
# pick color
color=$(hyprpicker -a -n)
# re-enable
hyprctl keyword decoration:screen_shader "path/to/shader.glsl"
```

Or disable wlsunset:
```bash
pkill wlsunset
color=$(hyprpicker -a -n)
# restart wlsunset with your systemd unit or directly
wlsunset -l 37.8 -L -122.4 &
```

---

### gpick cannot sample colors on Wayland surfaces

**Symptom:** gpick's sampler picks wrong colors or returns black for native Wayland surfaces.

**Cause:** gpick uses X11 `XGetImage` which only sees what is composited into the X11 frame buffer via XWayland. Native Wayland surfaces that are not composited into XWayland's space appear as black or show stale data.

**Fix:** Use `hyprpicker` for sampling from native Wayland surfaces. Use gpick only for its palette management and color dialog features, not for pixel sampling in a Wayland session.

---

### wl-color-picker: "no screencast portal available"

**Symptom:** `wl-color-picker` shows an error about missing screencast portal.

**Cause:** `xdg-desktop-portal` or the compositor-specific portal backend is not running.

**Fix:**

```bash
# Check portal status
systemctl --user status xdg-desktop-portal
systemctl --user status xdg-desktop-portal-hyprland   # or -wlr, -gtk

# Restart if needed
systemctl --user restart xdg-desktop-portal
systemctl --user restart xdg-desktop-portal-hyprland

# Ensure correct portal is configured
cat ~/.config/xdg-desktop-portal/hyprland-portals.conf
# Should contain:
# [preferred]
# default=hyprland;gtk
# org.freedesktop.impl.portal.Screenshot=hyprland
```

See Ch 48 for full XDG portal configuration on Hyprland.

---

### pastel: "command not found" after cargo install

**Symptom:** `pastel` installed via cargo but not found in PATH.

**Fix:** Ensure `~/.cargo/bin` is in your PATH:

```bash
# Add to ~/.zshrc or ~/.bashrc
export PATH="$HOME/.cargo/bin:$PATH"

# Reload
source ~/.zshrc

# Verify
which pastel
pastel --version
```

---

### Colors differ between hyprpicker and screenshot tools

**Symptom:** hyprpicker and `grim` pick different values for the same pixel.

**Cause:** hyprpicker samples the live composited buffer at the moment of click, while `grim` takes a full screenshot. If any animation or compositor effect is mid-frame, values can diverge.

**Fix:** This is expected behavior — both are correct at their respective sampling moments. For reproducible sampling of static UI elements, add a small settle delay:
```bash
# Wait for animations to complete before launching picker
sleep 0.3 && hyprpicker -a -n | wl-copy
```

---

## Summary

| Use Case | Recommended Tool |
|---|---|
| Quick one-shot hex pick | `hyprpicker -a -n` |
| Pick with GUI dialog | `wl-color-picker` |
| Build and save a palette interactively | `gpick` (via XWayland) |
| KDE/Qt theming workflow | `kcolorchooser` |
| Color format conversion | `pastel` |
| Extract palette from image | `matugen` or `wal` |
| Embed picking in Quickshell bar | `Process { command: ["hyprpicker"...] }` |

Color picking is one of the smallest but most used tools in a ricer's workflow. Invest time in a solid script around `hyprpicker` and a working `pastel` installation — those two together handle the entire color lifecycle from sampling to palette derivation. For applying the resulting palette, continue to Ch 37 (pywal), Ch 38 (matugen), and Ch 71 (Quickshell theming).

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
