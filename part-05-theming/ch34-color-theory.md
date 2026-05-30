# Chapter 34 — Color Theory for Desktop Ricing

> "A rice is only as cohesive as its color story." — r/unixporn community ethos

Color is the single most recognizable attribute of any desktop rice. Two setups with identical layouts but different palettes feel worlds apart. This chapter builds a rigorous understanding of color systems, palette mechanics, contrast engineering, and the practical toolchain for applying and maintaining a coherent color story across every layer of a Wayland desktop.

**Prerequisites:** Familiarity with terminal emulators, Waybar, and GTK/Qt theming basics (see Ch 28–33). You should have a working Wayland compositor (Hyprland, Sway, or River).

---

## Contents

- [34.1 Color Systems Used in Ricing](#341-color-systems-used-in-ricing)
  - [base16 / base24](#base16-base24)
  - [Material You / Material Design 3](#material-you-material-design-3)
  - [Catppuccin](#catppuccin)
  - [Other Major Palettes](#other-major-palettes)
- [34.2 Popular Palette Collections (2025)](#342-popular-palette-collections-2025)
- [34.3 Color Relationships](#343-color-relationships)
  - [Harmony Types](#harmony-types)
  - [The 60-30-10 Rule Applied to Ricing](#the-60-30-10-rule-applied-to-ricing)
- [34.4 Contrast and Accessibility](#344-contrast-and-accessibility)
  - [Why Low-Contrast Rices Fail Daily Use](#why-low-contrast-rices-fail-daily-use)
  - [Contrast Tools](#contrast-tools)
- [34.5 Automatic Color Extraction](#345-automatic-color-extraction)
  - [pywal](#pywal)
  - [wallust](#wallust)
  - [matugen (Material You)](#matugen-material-you)
  - [wpgtk](#wpgtk)
- [34.6 Where Colors Are Applied](#346-where-colors-are-applied)
  - [Terminal Emulator](#terminal-emulator)
  - [Shell Prompt (Starship)](#shell-prompt-starship)
  - [Waybar](#waybar)
  - [GTK Theme](#gtk-theme)
  - [Qt Theme](#qt-theme)
  - [Firefox / Chromium](#firefox-chromium)
- [34.7 Building a Cohesive Rice](#347-building-a-cohesive-rice)
  - [Phase 1: Choose or Extract the Palette](#phase-1-choose-or-extract-the-palette)
  - [Phase 2: Generate Application Configs](#phase-2-generate-application-configs)
  - [Phase 3: Test in Real Conditions](#phase-3-test-in-real-conditions)
  - [Palette Consistency Checklist](#palette-consistency-checklist)
- [34.8 Resources](#348-resources)
  - [Online Tools](#online-tools)
  - [Repositories and Wikis](#repositories-and-wikis)
  - [Related Chapters](#related-chapters)
- [Troubleshooting](#troubleshooting)
  - [Terminal colors look wrong or washed out](#terminal-colors-look-wrong-or-washed-out)
  - [pywal/wallust colors are muddy or too similar](#pywalwallust-colors-are-muddy-or-too-similar)
  - [GTK apps ignore the theme after applying](#gtk-apps-ignore-the-theme-after-applying)
  - [Colors not updating after running pywal](#colors-not-updating-after-running-pywal)
  - [Waybar CSS colors not updating](#waybar-css-colors-not-updating)
  - [Inconsistent colors between X11 and Wayland apps running via XWayland](#inconsistent-colors-between-x11-and-wayland-apps-running-via-xwayland)

---


## 34.1 Color Systems Used in Ricing

The ricing community has converged on a small number of color specification systems. Understanding which system a tool expects is essential for consistent theming — mixing systems across components produces jarring visual discontinuities.

### base16 / base24

Base16 is the foundational palette specification in desktop ricing. Introduced by Chris Kempson, it defines exactly 16 named slots (base00 through base0F) arranged semantically: base00–base03 are background shades from darkest to lightest, base04–base07 are foreground shades, and base08–base0F are accent colors (red, orange, yellow, green, cyan, blue, indigo, violet). Every terminal, editor, and bar theme that claims base16 support maps to these same 16 slots, making cross-component consistency achievable with a single palette definition.

Base24 extends the specification with 8 additional slots (base10–base17) to expose more nuanced background shades, addressing the limitation that base16 forces all applications to share only four background values. This matters in terminals where the difference between a focused and unfocused window's background is a key visual signal.

The practical benefit of base16 is **portability**: a single `scheme.yaml` file can generate themes for Alacritty, Kitty, Neovim, Rofi, Waybar, and dozens of other tools through a template engine. The tinted-theming project (successor to the original base16-builder) maintains the canonical ecosystem.

```yaml
# ~/.config/tinted-theming/schemes/my-custom.yaml
# base16 scheme definition — all values are hex without leading #
system: base16
name: "My Custom Scheme"
author: "Your Name"
variant: dark
palette:
  base00: "1e1e2e"   # darkest background (Catppuccin-inspired)
  base01: "181825"   # alt background
  base02: "313244"   # selection background
  base03: "45475a"   # comments, invisibles
  base04: "585b70"   # dark foreground
  base05: "cdd6f4"   # default foreground
  base06: "f5c2e7"   # light foreground
  base07: "b4befe"   # lightest foreground
  base08: "f38ba8"   # red (errors)
  base09: "fab387"   # orange (warnings)
  base0A: "f9e2af"   # yellow (strings)
  base0B: "a6e3a1"   # green (success)
  base0C: "94e2d5"   # cyan (special)
  base0D: "89b4fa"   # blue (functions)
  base0E: "cba6f7"   # violet (keywords)
  base0F: "f2cdcd"   # pink (deprecated)
```

```bash
# Install tinted-theming CLI (tinty)
cargo install tinty

# Initialize and apply a built-in scheme
tinty init
tinty apply catppuccin-mocha

# List available schemes
tinty list | grep catppuccin

# Apply your custom scheme defined above
tinty apply my-custom
```

### Material You / Material Design 3

Material You is Google's dynamic color system introduced with Android 12. It generates a full palette from a single seed color (typically extracted from the wallpaper), using a perceptually-uniform color space (HCT — Hue, Chroma, Tone) to produce tonal palettes that are mathematically guaranteed to meet contrast ratios. On the Linux desktop, Material You is primarily consumed through **matugen**, which generates colors compatible with AGS/Quickshell, Hyprland, and GTK4.

```bash
# Install matugen
cargo install matugen

# Generate Material You palette from wallpaper
matugen image ~/Pictures/wallpaper.jpg

# Generate and output in JSON for scripting
matugen image ~/Pictures/wallpaper.jpg --json scheme-content

# Generate with specific color scheme type
# Options: scheme-content, scheme-expressive, scheme-fidelity, scheme-fruit-salad,
#          scheme-monochrome, scheme-neutral, scheme-rainbow, scheme-tonal-spot
matugen image ~/Pictures/wallpaper.jpg --type scheme-tonal-spot --json

# Use a hex seed color instead of wallpaper
matugen color hex "#89b4fa"
```

### Catppuccin

Catppuccin is the most popular palette family in the 2024–2026 ricing community. It provides four flavors — Latte (light), Frappé (medium-dark), Macchiato (dark), and Mocha (darkest) — each using the same 26 named colors across slightly different base tones. The palette is warm and pastel rather than harsh, making it comfortable for extended daily use. The project maintains official ports for over 300 applications, meaning you can achieve near-perfect consistency with minimal manual work.

```bash
# Clone the Catppuccin base16 schemes for use with tinty
git clone https://github.com/catppuccin/base16 \
  ~/.config/tinted-theming/schemes/catppuccin

# Catppuccin Mocha color hex reference (copy-paste ready)
# Background:  base = #1e1e2e, mantle = #181825, crust = #11111b
# Surface:     s0 = #313244, s1 = #45475a, s2 = #585b70
# Overlay:     o0 = #6c7086, o1 = #7f849c, o2 = #9399b2
# Foreground:  subtext1 = #bac2de, subtext0 = #a6adc8, text = #cdd6f4
# Accents:     rosewater=#f5e0dc, flamingo=#f2cdcd, pink=#f5c2e7,
#              mauve=#cba6f7, red=#f38ba8, maroon=#eba0ac,
#              peach=#fab387, yellow=#f9e2af, green=#a6e3a1,
#              teal=#94e2d5, sky=#89dceb, sapphire=#74c7ec,
#              blue=#89b4fa, lavender=#b4befe
```

### Other Major Palettes

**Nord** uses a 16-color palette organized into four groups: Polar Night (dark backgrounds), Snow Storm (light foregrounds), Frost (cool accent blues/teals), and Aurora (five warm accents). Its defining characteristic is the near-total absence of warm browns or oranges, giving a consistent arctic coldness.

**Gruvbox** by morhetz takes the opposite direction: warm amber backgrounds with earthy accent colors. The dark variant uses a `#282828` base with warm yellow-greens and oranges, while the light variant inverts to a soft cream background. Gruvbox has exceptional editor support given its age.

**Tokyo Night** bridges the gap with deep blue-purple backgrounds and pastel neon accents. It maps naturally to urban night photography aesthetics and is particularly popular with Neovim users.

---

## 34.2 Popular Palette Collections (2025)

The following table covers the most actively maintained palettes with community port coverage as of 2025–2026. "Coverage" refers to the number of official application ports.

| Palette | Character | Base tone | Dark/Light | Community ports | Best for |
|---------|-----------|-----------|------------|-----------------|----------|
| Catppuccin Mocha | Soft, pastel | `#1e1e2e` | Dark | 300+ | General purpose daily use |
| Catppuccin Latte | Soft, pastel | `#eff1f5` | Light | 300+ | Daytime work |
| Gruvbox Dark | Warm, retro | `#282828` | Dark | 200+ | Coding, vim users |
| Gruvbox Light | Warm, retro | `#fbf1c7` | Light | 200+ | Print-like reading |
| Nord | Cool, minimal | `#2e3440` | Dark | 250+ | Productivity, clean |
| Tokyo Night | Purple-toned | `#1a1b26` | Dark | 150+ | Modern/anime aesthetic |
| Everforest | Earth tones | `#2d353b` | Dark/Light | 100+ | Nature/outdoor feel |
| Rosé Pine | Warm muted | `#191724` | Dark | 120+ | Elegant, editorial |
| Rosé Pine Dawn | Warm muted | `#faf4ed` | Light | 120+ | Warm daytime |
| One Dark Pro | High contrast | `#282c34` | Dark | 180+ | Editors, VS Code refugees |
| Solarized Dark | Precision crafted | `#002b36` | Dark | 200+ | Classic, scientifically designed |
| Solarized Light | Precision crafted | `#fdf6e3` | Light | 200+ | Print simulation |
| Dracula | Vivid, high-saturation | `#282a36` | Dark | 200+ | Streaming, screenshots |
| Kanagawa | Japanese ink-painting | `#1f1f28` | Dark | 80+ | Subtle elegance |
| Material Deep Ocean | Material-inspired | `#0f111a` | Dark | 60+ | Material design fans |

Most of these are available as base16 schemes via `tinty list`. For Catppuccin specifically, the upstream project provides direct configuration files for virtually every app.

```bash
# Browse and preview palettes using flavours (older base16 tool)
# Install: cargo install flavours
flavours list | column -c 80

# Preview a palette in the terminal (base16 color test)
curl -s https://raw.githubusercontent.com/chriskempson/base16-shell/master/scripts/base16-catppuccin-mocha.sh | bash
base16_test_script  # if base16-shell is installed
```

---

## 34.3 Color Relationships

Understanding how colors relate to each other allows you to evaluate whether a palette is visually harmonious and to construct custom palettes from scratch. The principles below come from traditional color theory but map directly to palette construction.

### Harmony Types

**Complementary** colors sit opposite each other on the color wheel (e.g., blue and orange, purple and yellow-green). In ricing, this shows up as a muted blue background with orange or amber accents — the combination creates visual tension that draws the eye to important elements. Gruvbox is essentially a complementary palette: warm amber backgrounds with cool green/blue accents.

**Analogous** palettes use adjacent hues (e.g., blue, teal, cyan). The result is calm and easy on the eyes. Nord is a classic analogous palette: all accents live in the blue–cyan–teal band with only the Aurora colors breaking the pattern. Analogous rices tend to photograph well and feel cohesive even when applied unevenly.

**Triadic** palettes use three hues spaced 120 degrees apart on the wheel. They are vibrant and balanced but harder to apply subtly. Dracula achieves a soft triadic effect with its pink/purple/cyan triad.

**Split-complementary** uses a base hue and two hues adjacent to its complement, producing a vibrant-but-balanced result. Tokyo Night approximates this with its blue-purple base and warm yellow/orange accents.

### The 60-30-10 Rule Applied to Ricing

The 60-30-10 rule from interior design translates well to desktop color allocation:

- **60%**: Background (base00, base01) — the terminal background, compositor blur tint, wallpaper average tone
- **30%**: Secondary surfaces (base02, base03) — inactive title bars, sidebar backgrounds, popup backgrounds
- **10%**: Accent (base08–base0F) — focused borders, active highlights, notification colors, cursor

Violating this ratio by making accents too dominant (e.g., vivid borders on every element) produces visual fatigue. The most visually successful rices on r/unixporn typically have muted backgrounds and restrained use of a single accent color, with a secondary accent appearing only for contrast or status indication.

```python
#!/usr/bin/env python3
# color_ratio.py — analyze the color distribution of a screenshot
# Requires: pip install Pillow colorthief
from colorthief import ColorThief
from PIL import Image
import sys

def analyze_palette(img_path, n=10):
    ct = ColorThief(img_path)
    palette = ct.get_palette(color_count=n, quality=1)
    print(f"Dominant colors in {img_path}:")
    for i, (r, g, b) in enumerate(palette):
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        print(f"  {i+1:2d}. {hex_color}  rgb({r:3d},{g:3d},{b:3d})")

if __name__ == "__main__":
    analyze_palette(sys.argv[1])
```

---

## 34.4 Contrast and Accessibility

Contrast ratio is the ratio of relative luminance between two colors. It determines whether text is readable against a background. WCAG (Web Content Accessibility Guidelines) defines two tiers:

- **AA (minimum):** 4.5:1 for normal text, 3:1 for large text (18pt+ or 14pt+ bold)
- **AAA (enhanced):** 7:1 for normal text, 4.5:1 for large text

The formula for relative luminance (L) is defined in sRGB space. For a channel value C (0–255):

```
C_linear = C/255
if C_linear <= 0.04045:
    C_relative = C_linear / 12.92
else:
    C_relative = ((C_linear + 0.055) / 1.055) ^ 2.4

L = 0.2126 * R_relative + 0.7152 * G_relative + 0.0722 * B_relative
contrast = (L_lighter + 0.05) / (L_darker + 0.05)
```

```bash
# Calculate contrast ratio between two hex colors using Python
python3 - << 'EOF'
def srgb_to_linear(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def luminance(r, g, b):
    return 0.2126 * srgb_to_linear(r) + 0.7152 * srgb_to_linear(g) + 0.0722 * srgb_to_linear(b)

def contrast(hex1, hex2):
    r1, g1, b1 = int(hex1[1:3], 16), int(hex1[3:5], 16), int(hex1[5:7], 16)
    r2, g2, b2 = int(hex2[1:3], 16), int(hex2[3:5], 16), int(hex2[5:7], 16)
    l1 = luminance(r1, g1, b1)
    l2 = luminance(r2, g2, b2)
    lighter, darker = max(l1, l2), min(l1, l2)
    ratio = (lighter + 0.05) / (darker + 0.05)
    print(f"Contrast: {ratio:.2f}:1  ", end="")
    if ratio >= 7.0:
        print("WCAG AAA (excellent)")
    elif ratio >= 4.5:
        print("WCAG AA (good)")
    elif ratio >= 3.0:
        print("WCAG AA large text only (marginal)")
    else:
        print("FAIL — not accessible")

# Catppuccin Mocha: text on background
contrast("#cdd6f4", "#1e1e2e")  # text / base
# Catppuccin Mocha: comment color readability
contrast("#585b70", "#1e1e2e")  # overlay2 / base (dimmed comments)
EOF
```

### Why Low-Contrast Rices Fail Daily Use

The ricing community has a well-documented aesthetic bias: screenshots favor low-contrast palettes because cameras and display profiles boost perceived saturation. A rice with 2.5:1 contrast looks gorgeous at 1920x1080 in a Reddit post but causes measurable eye strain after 4 hours of use. The rule of thumb is: **if you can't read it under fluorescent office lighting, it will hurt at home too.**

A particularly common mistake is styling comments in editors with near-background colors (e.g., `#45475a` on `#1e1e2e` = 1.9:1 contrast). This looks "subtle" in screenshots but makes code review physically uncomfortable. Keep comment contrast above 3:1 at minimum.

```bash
# Batch-check all base16 accent colors against background using the script above
python3 - << 'EOF'
def srgb_to_linear(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
def luminance(r, g, b):
    return 0.2126 * srgb_to_linear(r) + 0.7152 * srgb_to_linear(g) + 0.0722 * srgb_to_linear(b)
def contrast(hex1, hex2):
    r1,g1,b1 = int(hex1[1:3],16),int(hex1[3:5],16),int(hex1[5:7],16)
    r2,g2,b2 = int(hex2[1:3],16),int(hex2[3:5],16),int(hex2[5:7],16)
    l1=luminance(r1,g1,b1); l2=luminance(r2,g2,b2)
    lighter,darker = max(l1,l2),min(l1,l2)
    return (lighter+0.05)/(darker+0.05)

bg = "#1e1e2e"
accents = {
    "red":       "#f38ba8",
    "orange":    "#fab387",
    "yellow":    "#f9e2af",
    "green":     "#a6e3a1",
    "teal":      "#94e2d5",
    "blue":      "#89b4fa",
    "mauve":     "#cba6f7",
    "flamingo":  "#f2cdcd",
    "overlay0":  "#6c7086",
    "overlay1":  "#7f849c",
    "subtext0":  "#a6adc8",
    "text":      "#cdd6f4",
}
print(f"{'Name':<12} {'Hex':<10} {'Ratio':>7}  Grade")
print("-" * 40)
for name, hex_color in accents.items():
    r = contrast(hex_color, bg)
    grade = "AAA" if r>=7 else ("AA" if r>=4.5 else ("AA-lg" if r>=3 else "FAIL"))
    print(f"{name:<12} {hex_color:<10} {r:>6.2f}:1  {grade}")
EOF
```

### Contrast Tools

| Tool | Type | Notes |
|------|------|-------|
| `contrast-ratio.com` | Web | Instant check, keyboard-accessible |
| `coolors.co/contrast-checker` | Web | Side-by-side preview |
| `wcag-contrast-checker` | CLI (npm) | Scriptable |
| `colorcontrast` | CLI (Go) | `go install github.com/gre-ory/colorcontrast@latest` |
| GNOME Color Viewer | GUI | `gnome-color-manager` |
| Colour Contrast Analyser | GUI (Electron) | Download from TPGi |

---

## 34.5 Automatic Color Extraction

Dynamic color extraction derives a palette from the wallpaper. This makes color changes automatic when switching wallpapers, producing a unified look without manually tweaking dozens of config files.

### pywal

pywal (wal) is the oldest and most widely used tool. It runs k-means clustering on a resized wallpaper image to find N dominant colors (default 16), then maps them to terminal/app template variables. The generated palette is stored in `~/.cache/wal/colors*` in multiple formats.

```bash
# Install pywal
uv tool install pywal

# Basic usage — sets wallpaper and generates palette
wal -i ~/Pictures/wallpaper.jpg

# Generate palette only, don't set wallpaper
wal -i ~/Pictures/wallpaper.jpg -n

# Use a specific color backend
wal -i ~/Pictures/wallpaper.jpg --backend colorz

# Available backends: wal (default), colorz, colorthief, haishoku, fast_colorthief
# List them:
wal --backend list

# Generate light theme variant
wal -i ~/Pictures/wallpaper.jpg -l

# Apply colors to new terminal without regenerating (fast, for new terminals)
cat ~/.cache/wal/sequences

# View generated colors
cat ~/.cache/wal/colors.json | python3 -m json.tool

# Use wal colors in a shell script
source ~/.cache/wal/colors.sh
echo "Wallpaper: $wallpaper"
echo "Background: $background"
echo "Foreground: $foreground"
echo "Color 1 (red): $color1"
```

```bash
# ~/.config/hypr/hyprpaper.conf integration
# Run wal after wallpaper change — add to hyprpaper hook or use swww

# swww with automatic wal update
swww img ~/Pictures/wallpaper.jpg --transition-type fade --transition-duration 1 \
  && wal -i ~/Pictures/wallpaper.jpg -n --saturate 0.8
```

### wallust

wallust is a modern pywal replacement written in Rust, with better performance and more output format flexibility. It supports multiple color extraction algorithms and custom palette schemas.

```bash
# Install
cargo install wallust

# Basic usage
wallust run ~/Pictures/wallpaper.jpg

# Use a specific color scheme (palette mapping)
wallust run ~/Pictures/wallpaper.jpg --palette dark16

# Available palettes: dark16, hard16, light16, softdark16, pastel16, etc.
wallust run ~/Pictures/wallpaper.jpg --palette pastel16

# Output only the colorscheme JSON
wallust run ~/Pictures/wallpaper.jpg --check-contrast

# Configure default palette and quality
# ~/.config/wallust/wallust.toml
```

```toml
# ~/.config/wallust/wallust.toml
backend = "kmeans"        # or "colorthief", "wal"
palette = "dark16"
quality = 1               # 1 = highest quality, slower; 10 = fastest
filter = "dark"           # force dark colors
check_contrast = true     # auto-adjust colors that fail contrast
contrast_ratio = 4.5      # minimum ratio to enforce

[custom_keywords]
# Make wallust output vars that other tools consume
color16 = "{{ color0 }}"  # often used as terminal bold black
color17 = "{{ color1 }}"
```

### matugen (Material You)

matugen derives a full Material You palette from a seed color, producing named semantic variables rather than indexed colors. This is the preferred tool for AGS/Quickshell/Aylur's GTK Shell setups.

```bash
# Install
cargo install matugen

# Generate and write config files using templates
matugen image ~/Pictures/wallpaper.jpg

# matugen config with templates
# ~/.config/matugen/config.toml
```

```toml
# ~/.config/matugen/config.toml
[config]
reload_gtk_theme = true
set_wallpaper = true
wallpaper_tool = "swww"

[templates.waybar]
input_path = "~/.config/matugen/templates/waybar-colors.css"
output_path = "~/.config/waybar/colors.css"

[templates.hyprland]
input_path = "~/.config/matugen/templates/hyprland-colors.conf"
output_path = "~/.config/hypr/colors.conf"

[templates.alacritty]
input_path = "~/.config/matugen/templates/alacritty-colors.toml"
output_path = "~/.config/alacritty/colors.toml"
```

```
# ~/.config/matugen/templates/hyprland-colors.conf
# Matugen template syntax: {{colors.primary.default.hex}}
$primary          = {{colors.primary.default.hex}}
$on_primary       = {{colors.primary.on.hex}}
$primary_container= {{colors.primary.container.hex}}
$secondary        = {{colors.secondary.default.hex}}
$background       = {{colors.background.default.hex}}
$surface          = {{colors.surface.default.hex}}
$error            = {{colors.error.default.hex}}
```

### wpgtk

wpgtk provides a GTK GUI for pywal, including a theme manager, template editor, and color picker. It is useful for users who prefer a visual workflow.

```bash
# Install
uv tool install wpgtk

# Launch GUI
wpg

# CLI usage — add wallpaper to collection
wpg -a ~/Pictures/wallpaper.jpg

# Apply a previously added wallpaper
wpg -s wallpaper.jpg

# List managed wallpapers
wpg -l
```

---

## 34.6 Where Colors Are Applied

Understanding the full surface area of color application is essential for planning a cohesive rice. Missing any layer produces jarring inconsistencies.

### Terminal Emulator

The terminal is the most color-visible component on a riced desktop. Terminal colors are specified as 16 ANSI colors (color0–color15) plus a background and foreground. Colors 0–7 are normal, 8–15 are bright. The mapping to base16:

| base16 slot | Terminal color | Semantic use |
|-------------|----------------|--------------|
| base00 | Background | Terminal background |
| base05 | Foreground | Default text |
| base08 | color1 | Red / errors |
| base09 | color9 | Bright orange |
| base0A | color3 | Yellow / warnings |
| base0B | color2 | Green / success |
| base0C | color6 | Cyan / special |
| base0D | color4 | Blue / info |
| base0E | color5 | Magenta / keywords |
| base0F | color13 | Bright magenta |

```toml
# ~/.config/alacritty/colors.toml — Catppuccin Mocha manual config
[colors.primary]
background = "#1e1e2e"
foreground = "#cdd6f4"

[colors.cursor]
text = "#1e1e2e"
cursor = "#f5e0dc"

[colors.normal]
black   = "#45475a"
red     = "#f38ba8"
green   = "#a6e3a1"
yellow  = "#f9e2af"
blue    = "#89b4fa"
magenta = "#f5c2e7"
cyan    = "#94e2d5"
white   = "#bac2de"

[colors.bright]
black   = "#585b70"
red     = "#f38ba8"
green   = "#a6e3a1"
yellow  = "#f9e2af"
blue    = "#89b4fa"
magenta = "#f5c2e7"
cyan    = "#94e2d5"
white   = "#a6adc8"
```

```
# ~/.config/kitty/kitty.conf — equivalent in Kitty format
background            #1e1e2e
foreground            #cdd6f4
cursor                #f5e0dc
selection_background  #313244
selection_foreground  #cdd6f4

color0  #45475a
color1  #f38ba8
color2  #a6e3a1
color3  #f9e2af
color4  #89b4fa
color5  #f5c2e7
color6  #94e2d5
color7  #bac2de
color8  #585b70
color9  #f38ba8
color10 #a6e3a1
color11 #f9e2af
color12 #89b4fa
color13 #f5c2e7
color14 #94e2d5
color15 #a6adc8
```

### Shell Prompt (Starship)

Starship reads colors from its config. You can reference palette colors by hex value or use a named palette (Starship 1.17+ supports base16 via `palette`).

```toml
# ~/.config/starship.toml — palette-aware config
palette = "catppuccin_mocha"

[palettes.catppuccin_mocha]
rosewater = "#f5e0dc"
flamingo  = "#f2cdcd"
pink      = "#f5c2e7"
mauve     = "#cba6f7"
red       = "#f38ba8"
maroon    = "#eba0ac"
peach     = "#fab387"
yellow    = "#f9e2af"
green     = "#a6e3a1"
teal      = "#94e2d5"
sky       = "#89dceb"
sapphire  = "#74c7ec"
blue      = "#89b4fa"
lavender  = "#b4befe"
text      = "#cdd6f4"
subtext1  = "#bac2de"
subtext0  = "#a6adc8"
overlay2  = "#9399b2"
overlay1  = "#7f849c"
overlay0  = "#6c7086"
surface2  = "#585b70"
surface1  = "#45475a"
surface0  = "#313244"
base      = "#1e1e2e"
mantle    = "#181825"
crust     = "#11111b"

[character]
success_symbol = "[](bold green)"
error_symbol   = "[](bold red)"

[directory]
style = "bold blue"

[git_branch]
style = "bold mauve"
```

### Waybar

Waybar uses CSS for all styling. The recommended approach is to define CSS custom properties in a separate colors file that Waybar imports, so the palette can be swapped without touching layout CSS.

```css
/* ~/.config/waybar/colors.css — Catppuccin Mocha */
@define-color base      #1e1e2e;
@define-color mantle    #181825;
@define-color crust     #11111b;
@define-color surface0  #313244;
@define-color surface1  #45475a;
@define-color surface2  #585b70;
@define-color overlay0  #6c7086;
@define-color text      #cdd6f4;
@define-color subtext1  #bac2de;
@define-color blue      #89b4fa;
@define-color mauve     #cba6f7;
@define-color red       #f38ba8;
@define-color peach     #fab387;
@define-color yellow    #f9e2af;
@define-color green     #a6e3a1;
@define-color teal      #94e2d5;
```

```css
/* ~/.config/waybar/style.css — imports colors */
@import "colors.css";

* {
    font-family: "JetBrainsMono Nerd Font", monospace;
    font-size: 13px;
}

window#waybar {
    background-color: @base;
    color: @text;
    border-bottom: 2px solid @surface0;
}

#workspaces button.active {
    background-color: @surface0;
    color: @blue;
    border-bottom: 2px solid @blue;
}

#clock { color: @blue; }
#battery { color: @green; }
#battery.warning { color: @yellow; }
#battery.critical { color: @red; }
#network { color: @teal; }
#pulseaudio { color: @mauve; }
```

### GTK Theme

GTK applications read colors from the active GTK theme. For Adwaita-based GTK4 apps, the relevant mechanism is libadwaita's color variables (see Ch 35). For GTK3, you write a custom `gtk.css` or use nwg-look.

```bash
# Install Catppuccin GTK theme
git clone --depth 1 https://github.com/catppuccin/gtk \
  /tmp/catppuccin-gtk
cd /tmp/catppuccin-gtk
# Requires python3-catppuccin-gtk builder or pre-built releases
pip install catppuccin-gtk
catppuccin-gtk install Mocha Blue  # flavor + accent

# Apply theme
gsettings set org.gnome.desktop.interface gtk-theme "catppuccin-mocha-blue-standard+default"
# Or with nwg-look for Wayland-native setting
nwg-look
```

### Qt Theme

Qt apps use Kvantum or qt5ct/qt6ct for theming (see Ch 36). The palette is applied through Kvantum's SVG-based theme engine.

```bash
# Set Qt platform theme environment variables
# Add to ~/.config/hypr/env.conf or session environment file:
# env = QT_QPA_PLATFORMTHEME,kvantum
# env = XCURSOR_THEME,Catppuccin-Mocha-Dark

# Install Catppuccin Kvantum theme
git clone --depth 1 https://github.com/catppuccin/Kvantum \
  ~/.config/Kvantum/catppuccin

# Apply with kvantummanager (GUI) or kvantummanager --set KvCatppuccinMocha
kvantummanager --set KvCatppuccinMocha
```

### Firefox / Chromium

Firefox supports userChrome.css for UI customization and user.js for about:config settings. The Catppuccin Firefox extension handles the toolbar; userChrome.css handles chrome elements.

```bash
# Install Catppuccin Firefox theme via addons or direct CSS
mkdir -p ~/.mozilla/firefox/*.default-release/chrome/

# Download and use the CSS-based theme
curl -Lo ~/.mozilla/firefox/*.default-release/chrome/userChrome.css \
  https://raw.githubusercontent.com/catppuccin/firefox/main/userChrome.css
```

---

## 34.7 Building a Cohesive Rice

The practical workflow for building a consistent rice follows a top-down approach: start with a single source of truth (the wallpaper or a chosen palette), then propagate that palette outward to every component systematically.

### Phase 1: Choose or Extract the Palette

Either select a community palette (Catppuccin, Nord, etc.) or extract one from a wallpaper using pywal/wallust/matugen. If using an extracted palette, run the contrast checker from Section 34.4 on the generated colors before applying them — k-means extraction often produces background-colored accents that fail readability tests.

```bash
# Automated palette extraction and contrast validation pipeline
#!/usr/bin/env bash
set -euo pipefail

WALLPAPER="${1:-$HOME/Pictures/wallpaper.jpg}"

echo "==> Extracting palette from: $WALLPAPER"
wallust run "$WALLPAPER" --palette dark16 --check-contrast

echo "==> Colors written to: ~/.cache/wallust/"
ls -la ~/.cache/wallust/

echo "==> Applying to terminals via wal sequences"
cat ~/.cache/wal/sequences 2>/dev/null || echo "(pywal sequences not found)"

echo "==> Reloading Waybar"
pkill -SIGUSR2 waybar 2>/dev/null && echo "Waybar reloaded" || echo "Waybar not running"

echo "==> Done."
```

### Phase 2: Generate Application Configs

Use tinty, wal templates, or matugen templates to propagate the palette to all application configs. Maintain a single script that regenerates all targets:

```bash
#!/usr/bin/env bash
# ~/bin/apply-theme — apply palette everywhere
# Usage: apply-theme <wallpaper.jpg>

WALLPAPER="${1:-$(cat ~/.cache/wal/wal)}"

# 1. Extract palette + set wallpaper
wal -i "$WALLPAPER" -n --saturate 0.8
swww img "$WALLPAPER" --transition-type fade --transition-duration 0.8

# 2. Apply base16 via tinty (covers: alacritty, neovim, bat, fzf, rofi)
tinty apply "$(cat ~/.config/tinty/current_scheme)" 2>/dev/null || true

# 3. Apply Material You via matugen (covers: AGS widgets, GTK4 apps)
matugen image "$WALLPAPER" 2>/dev/null || true

# 4. Reload Waybar
pkill -SIGUSR2 waybar 2>/dev/null || true

# 5. Reload Hyprland colors
hyprctl reload 2>/dev/null || true

# 6. Reload dunst
pkill -SIGHUP dunst 2>/dev/null || true
notify-send "Theme" "Palette applied from $(basename "$WALLPAPER")"
```

### Phase 3: Test in Real Conditions

Screenshots lie. Validate your rice under real usage conditions:

1. Open a terminal with `htop`, `neofetch`, and code in nvim side-by-side
2. Open a browser with a dark-themed site and a light-content site
3. Trigger a notification
4. Switch workspaces and observe the bar state colors
5. Open a GTK dialog (file picker, settings app) and a Qt app (mpv, VLC)
6. Check the rice under daylight lighting conditions

```bash
# Quick visual test: render all 256 terminal colors
for i in $(seq 0 255); do
    printf "\e[38;5;%dm%3d \e[0m" "$i" "$i"
    [[ $((i % 16)) -eq 15 ]] && echo
done

# Test bold and italic rendering
echo -e "\e[1mBold text\e[0m  \e[3mItalic text\e[0m  \e[1;3mBold italic\e[0m"

# Test 24-bit true color support
python3 -c "
for r in range(0, 256, 32):
    for b in range(0, 256, 32):
        print(f'\033[48;2;{r};0;{b}m  \033[0m', end='')
    print()
"
```

### Palette Consistency Checklist

| Component | Configuration location | Format | Auto-reloadable? |
|-----------|------------------------|--------|------------------|
| Alacritty | `~/.config/alacritty/colors.toml` | TOML | Yes (inotify) |
| Kitty | `~/.config/kitty/current-theme.conf` | KV pairs | `kill -SIGUSR1` |
| Foot | `~/.config/foot/foot.ini` | INI | `footctl` |
| Waybar | `~/.config/waybar/colors.css` | CSS | `kill -SIGUSR2` |
| Hyprland | `~/.config/hypr/colors.conf` | Hyprland conf | `hyprctl reload` |
| Dunst | `~/.config/dunst/dunstrc` | INI | `kill -SIGHUP` |
| Rofi | `~/.config/rofi/colors.rasi` | Rofi theme | No (restart) |
| Neovim | `~/.config/nvim/lua/colors.lua` | Lua | `:colorscheme` |
| GTK3 | `~/.config/gtk-3.0/gtk.css` | CSS | Automatic |
| GTK4 | `~/.config/gtk-4.0/gtk.css` | CSS | Automatic |
| Qt/Kvantum | `~/.config/Kvantum/kvantum.kvconfig` | INI | No (restart apps) |

---

## 34.8 Resources

### Online Tools

| Tool | URL | Purpose |
|------|-----|---------|
| Catppuccin ports | `github.com/catppuccin/catppuccin` | 300+ official ports |
| base16 schemes | `github.com/tinted-theming/schemes` | Canonical scheme index |
| tinted-theming | `tinted-theming.github.io` | tinty, base16-builder |
| lospec palette list | `lospec.com/palette-list` | Pixel art / retro palettes |
| coolors | `coolors.co` | Palette generator + contrast |
| paletton | `paletton.com` | Color wheel relationships |
| realtime colors | `realtimecolors.com` | Live CSS variable preview |
| huemint | `huemint.com` | AI-assisted palette generation |
| tints.dev | `tints.dev` | Material-style tonal generation |

### Repositories and Wikis

```bash
# Clone scheme collection locally for offline use
git clone --depth 1 https://github.com/tinted-theming/schemes \
  ~/.local/share/tinted-theming/schemes

# Explore with fzf + bat preview
find ~/.local/share/tinted-theming/schemes -name "*.yaml" \
  | fzf --preview 'bat --color=always {}'

# Check current tinty-applied scheme
cat ~/.local/share/tinted-theming/tinty/current_scheme
```

### Related Chapters

- **Ch 28 — GTK Theming Fundamentals**: applying GTK3/GTK4 themes from the palette defined here
- **Ch 35 — Libadwaita Color Variables**: Material-style CSS variables for GTK4/GNOME apps
- **Ch 36 — Kvantum and Qt Theming**: translating your palette to Qt application colors
- **Ch 37 — Waybar Deep Dive**: full Waybar CSS structure for palette-aware configs
- **Ch 40 — Neovim Colorscheme Integration**: base16.nvim, lush.nvim, and custom colorscheme creation
- **Ch 47 — Dynamic Wallpaper and pywal Pipelines**: automated wallpaper-to-palette workflows
- **Ch 53 — Session Startup Ordering**: ensuring theme tools run before applications on login

---

## Troubleshooting

### Terminal colors look wrong or washed out

The most common cause is a mismatch between the terminal's color depth setting and the actual palette. Check true-color support:

```bash
# Test 24-bit color — if you see a smooth gradient, true color is working
python3 -c "
import sys
for i in range(80):
    r = int(255 * i / 79)
    sys.stdout.write(f'\033[48;2;{r};50;150m ')
sys.stdout.write('\033[0m\n')
"

# If the gradient shows banding (only 8 or 16 colors), set TERM correctly
# For Alacritty:
echo $TERM    # should be: alacritty or xterm-256color
# Fix: add to alacritty.toml:
# [env]
# TERM = "alacritty"
```

### pywal/wallust colors are muddy or too similar

The k-means algorithm tends to produce near-duplicate colors when the wallpaper has a narrow color range (e.g., a single-sky photo). Solutions:

```bash
# Increase saturation during extraction
wal -i wallpaper.jpg --saturate 1.0

# Try a different backend
wal -i wallpaper.jpg --backend colorthief
wal -i wallpaper.jpg --backend haishoku

# For wallust, try a different palette mapping
wallust run wallpaper.jpg --palette hard16  # higher contrast variant

# Force specific colors by editing the generated palette
$EDITOR ~/.cache/wal/colors.json
# Then re-run templates without re-extracting:
wal -R
```

### GTK apps ignore the theme after applying

GTK4/libadwaita apps may bypass the GTK theme entirely. Check:

```bash
# Force GTK4 to use the system theme (not Adwaita)
gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'
gsettings get org.gnome.desktop.interface gtk-theme

# Check if app uses libadwaita (bypasses GTK theme)
ldd $(which gedit 2>/dev/null || which gnome-text-editor) | grep -i adwaita

# For libadwaita apps, use gtk.css overrides (see Ch 35)
mkdir -p ~/.config/gtk-4.0
# Place overrides in ~/.config/gtk-4.0/gtk.css
```

### Colors not updating after running pywal

Existing terminal windows do not automatically receive new colors. New windows opened after running `wal` will have the correct colors (via shell profile sourcing). For existing windows:

```bash
# Apply colors to current terminal session immediately
(cat ~/.cache/wal/sequences)

# Add to shell RC for automatic application in new sessions
# ~/.bashrc or ~/.zshrc:
# (cat ~/.cache/wal/sequences &)

# Alternatively, use the wal daemon
wal -i wallpaper.jpg  # includes sequence application
```

### Waybar CSS colors not updating

```bash
# Reload Waybar after changing colors.css
pkill -SIGUSR2 waybar

# If Waybar doesn't reload CSS (bug in some versions), restart it
pkill waybar && waybar &

# Verify the @import path is correct
# In style.css, the path must be absolute or relative to the config directory:
# @import "/home/USER/.config/waybar/colors.css";  ← absolute (always works)
# @import "colors.css";                             ← relative (works in most versions)
```

### Inconsistent colors between X11 and Wayland apps running via XWayland

XWayland apps (e.g., older Electron apps, Wine) use X11 color management, which ignores Wayland color protocols. For terminal emulators running under XWayland:

```bash
# Check if a window is XWayland or native Wayland
# In Hyprland: hover over window, then:
hyprctl activewindow | grep -E "class|xwayland"

# Force Electron apps to run as native Wayland
# Add to the app's .desktop file Exec line:
# --ozone-platform=wayland --enable-features=WaylandWindowDecorations

# Or set globally:
export ELECTRON_OZONE_PLATFORM_HINT=auto
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
