# Chapter 112 — Aesthetic Ricing: From Palette to Pixel

## Overview

A rice is built in layers. You can pick a wallpaper, adjust terminal colors, and call it done — or you can build a fully coherent *aesthetic*: every surface, border, glyph, shadow, and animation tuned to express a single visual idea. The difference between a finished rice and an assembled one is that a finished rice was designed top-down from an aesthetic intent, not assembled bottom-up from whatever themes were available.

This chapter teaches the general method for constructing a desktop aesthetic from scratch, then applies it to three distinct aesthetics as fully worked case studies:

- **Tokyo Night** — the ur-example of a polished dark blue rice; teaches how to work with an existing theme ecosystem and achieve consistency across all layers
- **Cyberpunk Neon** — neon on near-black with blur, glow effects, and animated elements; teaches CSS glow, compositor effects, and wallpaper motion
- **Tron / Synthwave** — electric blue geometric minimalism with scanline shaders; teaches compositor shaders, geometric icon selection, and the "clean" variant of dark ricing

Each case study delivers: a complete color palette in base16 format, terminal configuration, Waybar CSS, Hyprland configuration, GTK and Qt theme selection, icon pack, font stack, cursor, and a wallpaper sourcing guide.

**Cross-references:** Ch 34 — color theory and base16 palette fundamentals. Ch 35/36 — GTK and Qt theme application mechanics. Ch 38 — dynamic theming from wallpaper (pywal/matugen). Ch 92 — GLSL shaders in compositors (used in Tron case study). Ch 40/106 — Stylix and automated theme switching.

---

## 112.1 The Seven Layers of a Rice

Every Wayland rice has seven visual layers. A coherent aesthetic means all seven speak the same color language. Work top-down: decide the palette first, then apply it.

```
Layer 7 │ Applications (browser, editor, file manager)
Layer 6 │ Notifications (mako/dunst popup style)
Layer 5 │ Bar / Panel (Waybar, Quickshell, eww)
Layer 4 │ Terminal (colors, font, padding, opacity)
Layer 3 │ Compositor (borders, shadows, blur, animations, gaps)
Layer 2 │ Wallpaper (sets the emotional tone of everything above)
Layer 1 │ Color palette (the single source of truth)
```

Design mistakes almost always come from skipping Layer 1 — jumping straight to GTK themes or Waybar CSS without a palette definition. When every component has its own slightly different shade of "blue", the result reads as incomplete even if no individual component is badly configured.

---

## 112.2 The General Method

### Step 1: Define the Anchor Emotion

Before picking a single color, answer: *what should this desktop feel like?* Tokyo Night feels calm and professional. Cyberpunk feels electric and urgent. Tron feels precise and cold. The emotion determines the hue family, the value range (how dark), and the saturation level (how vivid).

| Feeling | Hue family | Value | Saturation |
|---|---|---|---|
| Calm / professional | Blue, blue-violet | Very dark (5–15% L) | Low–medium (40–60%) |
| Electric / urgent | Cyan, magenta, yellow | Near-black + neon (90%+ S) | Maximum |
| Precise / cold | Monochrome blue | Very dark | Medium with one vivid accent |
| Warm / cozy | Amber, orange, brown | Dark (15–25% L) | Medium |
| Natural / earthy | Green, brown, tan | Mid-dark (20–30% L) | Low |

### Step 2: Build a Palette in base16

Define 16 slots using the semantics from Ch 34. Every tool that accepts base16 can consume this directly; tools that do not can be manually mapped to these names.

```yaml
# Template — replace values for your aesthetic
palette:
  base00: ""   # darkest background (main window bg)
  base01: ""   # darker background (statusbar, line numbers)
  base02: ""   # selection background, border
  base03: ""   # comments, invisible chars, dim text
  base04: ""   # dark foreground, secondary text
  base05: ""   # default foreground (body text)
  base06: ""   # light foreground (titles)
  base07: ""   # lightest foreground (special highlights)
  base08: ""   # red (errors, deleted)
  base09: ""   # orange (warnings, modified)
  base0A: ""   # yellow (strings, classes)
  base0B: ""   # green (success, inserted)
  base0C: ""   # cyan (escape chars, special)
  base0D: ""   # blue (functions, primary accent)
  base0E: ""   # purple/violet (keywords)
  base0F: ""   # brown/pink (deprecated, secondary accent)
```

### Step 3: Select a Wallpaper

The wallpaper must contain the palette's dominant color. An aesthetically perfect config can be ruined by a wallpaper that fights the colors. Rules:

- The wallpaper's most saturated hue should match `base0D` (primary accent)
- The wallpaper's overall luminosity should match your background range (base00–base02)
- For animated aesthetics (Cyberpunk), the motion should be subtle — slow drifting particles or very slow loops; fast-moving wallpapers are distracting during work

### Step 4: Apply in Layer Order

Apply from bottom up: palette → wallpaper → compositor → terminal → bar → notifications → apps. This order prevents re-doing work: a compositor border color that looks wrong in isolation almost always resolves when the terminal and bar are in place.

### Step 5: Validate Consistency

Check every layer against the same anchor color:
```bash
# Quick contrast check: foreground on background must be ≥ 4.5:1 for WCAG AA
# Install contrast-ratio from AUR or use an online tool

# Check that all configs reference only palette colors (no stray hex values)
grep -rh '#[0-9a-fA-F]\{6\}' ~/.config/waybar ~/.config/hypr \
  ~/.config/alacritty ~/.config/kitty \
  | sort -u
# Any hex that is NOT in your palette.yaml is a consistency error
```

---

## 112.3 Case Study: Tokyo Night

### Identity

Tokyo Night is the dark-blue aesthetic that dominated r/unixporn from 2022–2024. Its defining properties: a deep blue-black background in the #16161e–#1a1b26 range, muted pastel accents (nothing neon), and a sense of depth created by having four distinct background shades. It has a large existing theme ecosystem, making it the best aesthetic for learning how to *wire themes together* rather than how to create them.

**Palette feel:** calm, professional, late-night coding session, city seen through a rain-streaked window.

### 112.3.1 Palette Definition

```yaml
# ~/.config/tinted-theming/schemes/tokyo-night.yaml
system: base16
name: "Tokyo Night"
author: "enkia (adapted)"
variant: dark
palette:
  base00: "1a1b26"   # main bg — deep blue-black
  base01: "16161e"   # darker bg — titlebar, statusline bg
  base02: "2f3549"   # selection, border, inactive
  base03: "444b6a"   # comments, dim text
  base04: "787c99"   # secondary text
  base05: "c0caf5"   # default foreground — cool lavender-white
  base06: "cbccd1"   # light foreground
  base07: "d5d6db"   # lightest foreground
  base08: "f7768e"   # red — errors
  base09: "ff9e64"   # orange — warnings
  base0A: "e0af68"   # yellow — strings
  base0B: "9ece6a"   # green — success
  base0C: "7dcfff"   # cyan — escape chars
  base0D: "7aa2f7"   # blue — functions (primary accent)
  base0E: "bb9af7"   # purple — keywords
  base0F: "9d7cd8"   # dark violet — secondary accent
```

### 112.3.2 Wallpaper

Source: [tokyo-night wallpaper pack on GitHub](https://github.com/enkia/tokyo-night-vscode-theme) (the README has links) or search `site:github.com tokyo-night wallpaper`. Target: a dark cityscape at night, predominantly in the #1a1b26 value range, with blue and purple neon reflections.

```bash
# Set with hyprpaper
hyprctl hyprpaper preload "~/wallpapers/tokyo-night-city.png"
hyprctl hyprpaper wallpaper ", ~/wallpapers/tokyo-night-city.png"

# Or with swww (cross-fade on application)
swww img ~/wallpapers/tokyo-night-city.png \
  --transition-type fade --transition-duration 1.5
```

### 112.3.3 Hyprland Configuration

```ini
# ~/.config/hypr/hyprland.conf — Tokyo Night aesthetics

general {
    gaps_in = 4
    gaps_out = 8
    border_size = 2
    col.active_border   = rgba(7aa2f7ee) rgba(bb9af7ee) 45deg
    col.inactive_border = rgba(2f3549aa)
    resize_on_border = true
}

decoration {
    rounding = 8
    active_opacity   = 1.0
    inactive_opacity = 0.92

    shadow {
        enabled  = true
        range    = 20
        render_power = 3
        color    = rgba(7aa2f710)   # very faint blue shadow
        color_inactive = rgba(0a0a1a08)
    }

    blur {
        enabled  = true
        size     = 6
        passes   = 3
        new_optimizations = true
        xray     = false
    }
}

animations {
    enabled = true
    bezier = tokyoSnap, 0.16, 1, 0.3, 1    # fast attack, slow settle

    animation = windows,   1, 4,  tokyoSnap, slide
    animation = windowsOut,1, 4,  default,   popin 80%
    animation = border,    1, 8,  default
    animation = fade,      1, 4,  default
    animation = workspaces,1, 5,  tokyoSnap, slidevert
}
```

### 112.3.4 Terminal (Kitty)

```ini
# ~/.config/kitty/kitty.conf — Tokyo Night colors
background            #1a1b26
foreground            #c0caf5
selection_background  #2f3549
selection_foreground  #c0caf5
cursor                #c0caf5

# 16 ANSI colors
color0  #15161e    color8  #414868
color1  #f7768e    color9  #f7768e
color2  #9ece6a    color10 #9ece6a
color3  #e0af68    color11 #e0af68
color4  #7aa2f7    color12 #7aa2f7
color5  #bb9af7    color13 #bb9af7
color6  #7dcfff    color14 #7dcfff
color7  #a9b1d6    color15 #c0caf5

# Typography
font_family      JetBrains Mono
font_size        13.0
modify_font cell_height 2px
window_padding_width 12

# Transparency — subtle, not distracting
background_opacity 0.94
```

### 112.3.5 Waybar

```css
/* ~/.config/waybar/style.css — Tokyo Night */
* {
    font-family: "JetBrains Mono Nerd Font", monospace;
    font-size: 13px;
}

window#waybar {
    background: rgba(26, 27, 38, 0.90);  /* #1a1b26 @ 90% */
    color: #c0caf5;
    border-bottom: 1px solid rgba(122, 162, 247, 0.15);
}

.modules-right { margin-right: 8px; }
.modules-left  { margin-left:  8px; }

#workspaces button {
    color: #444b6a;
    padding: 0 8px;
    border-radius: 6px;
    transition: all 200ms ease;
}
#workspaces button.active {
    color: #7aa2f7;
    background: rgba(122, 162, 247, 0.15);
}
#workspaces button:hover {
    color: #c0caf5;
    background: rgba(47, 53, 73, 0.6);
}

#clock        { color: #7dcfff; }
#battery      { color: #9ece6a; }
#battery.warning  { color: #e0af68; }
#battery.critical { color: #f7768e; animation: pulse 1s ease infinite; }
#cpu          { color: #bb9af7; }
#memory       { color: #7aa2f7; }
#network      { color: #9ece6a; }
#pulseaudio   { color: #7dcfff; }
#tray         { margin: 0 4px; }

@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }
```

### 112.3.6 Toolkit Themes

```bash
# GTK — tokyo-night-gtk (AUR)
yay -S tokyo-night-gtk-theme-git

# Apply
gsettings set org.gnome.desktop.interface gtk-theme "Tokyonight-Dark-BL"
# or in ~/.config/gtk-3.0/settings.ini:
# gtk-theme-name = Tokyonight-Dark-BL

# Qt — use Kvantum with the tokyo-night theme
yay -S kvantum-theme-tokyo-night-git
kvantummanager --set TokyoNight

# Icons — Papirus Dark with folder color override
sudo pacman -S papirus-icon-theme
papirus-folders -C teal --theme Papirus-Dark
gsettings set org.gnome.desktop.interface icon-theme "Papirus-Dark"

# Cursor — Bibata-Modern-Classic (neutral, reads well on dark)
yay -S bibata-cursor-theme
gsettings set org.gnome.desktop.interface cursor-theme "Bibata-Modern-Classic"
```

### 112.3.7 Font Stack

| Role | Font | Size |
|---|---|---|
| Terminal / code | JetBrains Mono | 13–14px |
| Bar / UI | JetBrains Mono Nerd Font | 13px |
| GTK apps | Inter | 10–11pt |
| Document body | Source Serif 4 | 12pt |

---

## 112.4 Case Study: Cyberpunk Neon

### Identity

Cyberpunk Neon puts maximum-saturation accent colors — cyan, magenta, yellow — against a near-black background. The defining visual techniques are: CSS `text-shadow` glow on bar labels, blur + high-transparency on panels, and either an animated wallpaper or a high-contrast static neon cityscape. This aesthetic is the hardest to make comfortable for long sessions; the design challenge is restraint — using neon as accent, not as fill color.

**Palette feel:** urgent, electric, dystopian night market, rain-soaked neon reflections.

### 112.4.1 Palette Definition

```yaml
# ~/.config/tinted-theming/schemes/cyberpunk-neon.yaml
system: base16
name: "Cyberpunk Neon"
author: "custom"
variant: dark
palette:
  base00: "0a0a0f"   # near-black main bg
  base01: "0d0d1a"   # slightly lighter bg
  base02: "1a0033"   # dark purple surface (selection, borders)
  base03: "3d1a5c"   # dim purple (comments)
  base04: "7a7a9e"   # secondary text
  base05: "e0e0ff"   # cool near-white foreground
  base06: "f0f0ff"   # light foreground
  base07: "ffffff"   # white (rare, only for emphasis)
  base08: "ff003c"   # hot red — errors, danger
  base09: "ff6e00"   # neon orange — warnings
  base0A: "ffff00"   # electric yellow — strings, highlight
  base0B: "00ff88"   # neon green — success
  base0C: "00ffff"   # pure cyan — primary accent (THE cyberpunk color)
  base0D: "00aaff"   # electric blue — secondary accent
  base0E: "ff00ff"   # pure magenta — keywords, special
  base0F: "ff0080"   # neon pink — tertiary accent
```

### 112.4.2 Wallpaper

Target: rain-slicked city street at night, neon signs reflecting in puddles, predominantly dark background with cyan and magenta light sources. Search for "cyberpunk city night 1920x1080" on Unsplash, WallpaperEngine alternatives, or `site:github.com cyberpunk wallpaper pack`.

For animated wallpapers use `swww` with a looping video converted to GIF or WebP:

```bash
# Convert a video clip to optimized GIF for swww
ffmpeg -i cyberpunk-rain.mp4 \
  -vf "fps=24,scale=1920:-1:flags=lanczos" \
  -loop 0 cyberpunk-rain.gif

# Set the animated wallpaper
swww img ~/wallpapers/cyberpunk-rain.gif \
  --transition-type none   # no cross-fade; animated files loop immediately
```

For a static wallpaper with swww transition on a theme toggle (day→night):
```bash
swww img ~/wallpapers/cyberpunk-night.png \
  --transition-type wipe \
  --transition-angle 30 \
  --transition-duration 1.0
```

### 112.4.3 Hyprland Configuration

```ini
# ~/.config/hypr/hyprland.conf — Cyberpunk Neon

general {
    gaps_in  = 3
    gaps_out = 6
    border_size = 1
    # Cyan → magenta gradient border (the defining visual)
    col.active_border   = rgba(00ffffee) rgba(ff00ffee) 90deg
    col.inactive_border = rgba(1a003366)
    resize_on_border = true
}

decoration {
    rounding = 4   # slightly less rounded than Tokyo Night — more angular

    active_opacity   = 1.0
    inactive_opacity = 0.85   # high transparency for inactive = very cyberpunk

    shadow {
        enabled  = true
        range    = 30
        render_power = 2
        # Cyan glow shadow — the key effect
        color    = rgba(00ffff22)
        color_inactive = rgba(00000000)
    }

    blur {
        enabled = true
        size    = 12      # heavier blur than Tokyo Night
        passes  = 4
        noise   = 0.02
        contrast = 1.1
        brightness = 0.85   # slightly darken blurred content
        new_optimizations = true
        special = true
    }
}

animations {
    enabled = true
    bezier = cyber, 0.05, 0.9, 0.1, 1.0   # sharp, slightly bouncy

    animation = windows,   1, 3, cyber, slide
    animation = windowsOut,1, 2, default, popin 60%
    animation = border,    1, 4, default
    animation = fade,      1, 3, default
    animation = workspaces,1, 3, cyber, slidefade 20%
}
```

### 112.4.4 Terminal (Alacritty)

```toml
# ~/.config/alacritty/alacritty.toml — Cyberpunk Neon

[colors.primary]
background = "#0a0a0f"
foreground = "#e0e0ff"

[colors.cursor]
text   = "#0a0a0f"
cursor = "#00ffff"

[colors.selection]
text       = "#0a0a0f"
background = "#00ffff"

[colors.normal]
black   = "#0d0d1a"
red     = "#ff003c"
green   = "#00ff88"
yellow  = "#ffff00"
blue    = "#00aaff"
magenta = "#ff00ff"
cyan    = "#00ffff"
white   = "#e0e0ff"

[colors.bright]
black   = "#3d1a5c"
red     = "#ff4466"
green   = "#44ffaa"
yellow  = "#ffff55"
blue    = "#44ccff"
magenta = "#ff44ff"
cyan    = "#44ffff"
white   = "#ffffff"

[window]
opacity      = 0.85
padding      = { x = 14, y = 12 }
decorations  = "None"

[font]
# Cyberpunk fonts: Share Tech Mono for body, Orbitron for headers (in apps)
normal = { family = "Share Tech Mono", style = "Regular" }
size   = 13.0
```

### 112.4.5 Waybar with Glow Effects

The key technique: `text-shadow` in Waybar CSS produces a glow effect on text and icons. Use it sparingly — only on the most important elements.

```css
/* ~/.config/waybar/style.css — Cyberpunk Neon */
* {
    font-family: "Share Tech Mono", "JetBrains Mono Nerd Font", monospace;
    font-size: 13px;
}

window#waybar {
    background: rgba(10, 10, 15, 0.75);   /* near-transparent */
    border-bottom: 1px solid rgba(0, 255, 255, 0.2);
    color: #e0e0ff;
}

/* Cyan glow on active workspace */
#workspaces button.active {
    color: #00ffff;
    background: rgba(0, 255, 255, 0.08);
    text-shadow: 0 0 8px rgba(0, 255, 255, 0.8),
                 0 0 16px rgba(0, 255, 255, 0.4);
    border-bottom: 1px solid #00ffff;
}

#workspaces button {
    color: #3d1a5c;
    padding: 0 8px;
    transition: all 150ms ease;
}
#workspaces button:hover {
    color: #e0e0ff;
    background: rgba(0, 255, 255, 0.05);
}

#clock {
    color: #00ffff;
    text-shadow: 0 0 10px rgba(0, 255, 255, 0.6);
    font-weight: bold;
    letter-spacing: 2px;
}

#battery      { color: #00ff88; }
#battery.warning  { color: #ffff00; text-shadow: 0 0 6px rgba(255,255,0,0.5); }
#battery.critical { color: #ff003c; text-shadow: 0 0 8px rgba(255,0,60,0.8);
                    animation: cyberpulse 0.8s ease infinite; }
#cpu          { color: #ff00ff; }
#memory       { color: #00aaff; }
#network.ethernet { color: #00ff88; }
#network.wifi     { color: #00ffff; }
#pulseaudio   { color: #ff00ff; }

/* Separator bars use neon color */
.modules-right > widget:not(:last-child) {
    border-right: 1px solid rgba(0, 255, 255, 0.12);
    margin-right: 4px;
    padding-right: 8px;
}

@keyframes cyberpulse {
    0%,100% { text-shadow: 0 0 8px rgba(255,0,60,0.8); }
    50%     { text-shadow: 0 0 20px rgba(255,0,60,1.0), 0 0 40px rgba(255,0,60,0.5); }
}
```

### 112.4.6 GTK Theme

No mainstream GTK theme perfectly nails the Cyberpunk aesthetic. The closest approaches:

```bash
# Option A: Colloid Dark + manual color override
yay -S colloid-gtk-theme-git
# Set base theme to Colloid-Dark, then override with custom colors in ~/.config/gtk-4.0/gtk.css

# Option B: Adwaita Dark + full CSS override
# ~/.config/gtk-4.0/gtk.css
@define-color accent_color #00ffff;
@define-color accent_bg_color rgba(0, 255, 255, 0.15);
@define-color window_bg_color #0a0a0f;
@define-color window_fg_color #e0e0ff;
@define-color view_bg_color #0d0d1a;
@define-color headerbar_bg_color #0d0d1a;
@define-color sidebar_bg_color #0a0a0f;
```

### 112.4.7 Font Stack

| Role | Font | Reasoning |
|---|---|---|
| Terminal / code | Share Tech Mono | Slightly condensed, sci-fi feel |
| Bar labels | Share Tech Mono | Consistent with terminal |
| GTK apps | Exo 2 | Geometric sans, slightly futuristic |
| Headers (Waybar title) | Orbitron | Sci-fi display font — use only for large text |
| Icons in bar | Symbols Nerd Font | Keeps icon rendering clean |

```bash
# Install fonts
yay -S ttf-share-tech-mono ttf-exo-2 ttf-orbitron
sudo pacman -S ttf-jetbrains-mono-nerd
```

---

## 112.5 Case Study: Tron / Synthwave

### Identity

The Tron aesthetic is defined by a single dominant color — electric blue in the #00d4ff range — on a near-black background, with geometric shapes, clean lines, and zero organic curves. Where Cyberpunk uses three neons fighting each other, Tron uses one neon with near-monochrome supporting tones. The defining application is a scanline or grid shader overlay that makes the entire desktop look like it is rendered on a vector display.

**Palette feel:** precise, cold, mechanical, digital realm without a sky.

### 112.5.1 Palette Definition

```yaml
# ~/.config/tinted-theming/schemes/tron.yaml
system: base16
name: "Tron"
author: "custom"
variant: dark
palette:
  base00: "0a0c10"   # near-black main bg
  base01: "0d1117"   # slightly lighter bg
  base02: "0d2137"   # dark blue surface
  base03: "1a3a5c"   # dim blue (grid lines, comments)
  base04: "5a7d9e"   # medium blue (secondary text)
  base05: "c8d8e8"   # cool blue-white (default fg)
  base06: "dceeff"   # light foreground
  base07: "f0f8ff"   # near-white
  base08: "ff4444"   # red (danger — rare)
  base09: "ff8800"   # orange (warning — rare)
  base0A: "88ddff"   # light blue-cyan (strings, highlight)
  base0B: "00ffcc"   # cyan-teal (success — Grid programs)
  base0C: "00d4ff"   # electric blue-cyan (primary accent)
  base0D: "0080ff"   # deep blue (functions, links)
  base0E: "3d9bd4"   # medium blue (keywords)
  base0F: "66ccff"   # soft blue (secondary)
```

### 112.5.2 Wallpaper

Target: a dark surface with geometric blue grid lines, light cycles, or the Tron cityscape. The wallpaper should be predominantly base00 (`#0a0c10`) with thin base0C lines. Static works better than animated for Tron because the aesthetic is about clean stillness.

Recommended sources: search "tron grid wallpaper 4K" or "synthwave retrowave grid wallpaper". The classic is a dark ground plane receding to a glowing horizon with a gradient from near-black at top to dark blue at the horizon.

### 112.5.3 Hyprland Configuration

```ini
# ~/.config/hypr/hyprland.conf — Tron

general {
    gaps_in  = 2      # tighter gaps — geometry-forward
    gaps_out = 4
    border_size = 1   # thin, precise border (not thick like Tokyo Night)
    col.active_border   = rgba(00d4ffff)   # solid electric blue — no gradient
    col.inactive_border = rgba(0d213766)
}

decoration {
    rounding = 0   # ZERO rounding — Tron has no organic curves

    active_opacity   = 1.0
    inactive_opacity = 0.90

    shadow {
        enabled  = true
        range    = 15
        render_power = 3
        color    = rgba(00d4ff18)   # faint blue glow shadow
        color_inactive = rgba(00000000)
    }

    blur {
        enabled = false   # Tron has no blur — everything is crisp
    }
}

animations {
    enabled = true
    bezier = tronLinear, 0.0, 0.0, 1.0, 1.0   # perfectly linear — no easing

    animation = windows,    1, 2, tronLinear, slide
    animation = windowsOut, 1, 2, tronLinear, slide
    animation = border,     1, 4, default
    animation = fade,       1, 2, tronLinear
    animation = workspaces, 1, 2, tronLinear, slide
}
```

The **zero rounding** and **no blur** are the most important settings. They are what separates Tron from other blue rices.

### 112.5.4 Scanline Shader

A scanline or grid-overlay shader is the signature effect of the Tron aesthetic. Apply it via Hyprland's `screen_shader` option (Ch 92):

```glsl
// ~/.config/hypr/shaders/tron-grid.glsl
precision mediump float;
varying vec2 v_texcoord;
uniform sampler2D tex;

void main() {
    vec4 color = texture2D(tex, v_texcoord);

    // Subtle horizontal scanlines — every 2px row is slightly dimmer
    float scanline = mod(floor(v_texcoord.y * 1080.0), 2.0);
    float scanFactor = 1.0 - (scanline * 0.04);   // 4% dim on every other line

    // Very faint blue tint to the whole screen
    vec4 tint = vec4(0.0, 0.02, 0.06, 0.0);

    gl_FragColor = (color * scanFactor) + tint;
    gl_FragColor.a = color.a;
}
```

```ini
# ~/.config/hypr/hyprland.conf
decoration {
    screen_shader = ~/.config/hypr/shaders/tron-grid.glsl
}
```

Adjust the `0.04` scanline factor to taste — values above 0.08 become visible and fatiguing; values below 0.02 are invisible but still add the blue tint.

### 112.5.5 Terminal (Foot)

Foot is a natural fit for Tron: minimal, no rounded window chrome, starts fast.

```ini
# ~/.config/foot/foot.ini — Tron colors
[colors]
background=0a0c10
foreground=c8d8e8
selection-background=0d2137
selection-foreground=c8d8e8
regular0=0d1117    # black
regular1=ff4444    # red
regular2=00ffcc    # green
regular3=88ddff    # yellow (mapped to light blue in Tron)
regular4=0080ff    # blue
regular5=3d9bd4    # magenta (mapped to medium blue)
regular6=00d4ff    # cyan — primary electric blue
regular7=c8d8e8    # white
bright0=1a3a5c
bright1=ff6666
bright2=44ffdd
bright3=aaeeff
bright4=3399ff
bright5=66aadd
bright6=44e4ff
bright7=f0f8ff

[main]
font=JetBrains Mono:size=13
pad=12x10

[cursor]
color=0a0c10 00d4ff   # bg cursor_fg — electric blue cursor
```

### 112.5.6 Waybar

```css
/* ~/.config/waybar/style.css — Tron */
* {
    font-family: "JetBrains Mono Nerd Font", monospace;
    font-size: 12px;
    border-radius: 0;   /* No rounding anywhere */
}

window#waybar {
    background: rgba(10, 12, 16, 0.95);
    border-bottom: 1px solid #00d4ff;   /* solid line, no blur, no gradient */
    color: #c8d8e8;
}

#workspaces button {
    color: #1a3a5c;
    border-radius: 0;
    padding: 0 10px;
    border-right: 1px solid #0d2137;
    transition: color 100ms linear, background 100ms linear;
}
#workspaces button.active {
    color: #00d4ff;
    background: rgba(0, 212, 255, 0.08);
    border-bottom: 2px solid #00d4ff;
}
#workspaces button:hover {
    color: #88ddff;
    background: rgba(0, 212, 255, 0.05);
}

#clock        { color: #00d4ff; letter-spacing: 3px; font-weight: bold; }
#cpu          { color: #3d9bd4; }
#memory       { color: #00ffcc; }
#network      { color: #88ddff; }
#pulseaudio   { color: #00d4ff; }
#battery      { color: #66ccff; }
#battery.warning  { color: #ff8800; }
#battery.critical { color: #ff4444; }

/* Right-side module separator using the grid-line color */
.modules-right > widget { border-left: 1px solid rgba(0, 212, 255, 0.15); }
```

### 112.5.7 Font Stack

| Role | Font | Reasoning |
|---|---|---|
| Terminal / code | JetBrains Mono | Clean monospace, good bitmap rendering at low sizes |
| Bar | JetBrains Mono Nerd Font | Consistent; Nerd Font for icons |
| GTK apps | Exo 2 Light | Geometric, narrow, slightly futuristic |
| Display (titles) | Exo 2 Medium | Same family, more weight |

Tron does not use display fonts like Orbitron — the aesthetic is about the code terminal being the UI, not styled headers.

### 112.5.8 Icon Theme

```bash
# Flat Remix — geometric, monochrome-adjacent icon pack
yay -S flat-remix
gsettings set org.gnome.desktop.interface icon-theme "Flat-Remix-Blue-Dark"

# Cursor — Bibata Modern Ice (cold blue tones)
yay -S bibata-cursor-theme
gsettings set org.gnome.desktop.interface cursor-theme "Bibata-Modern-Ice"
```

---

## 112.6 Cross-Aesthetic Techniques

### Enforcing Palette Consistency with tinty

```bash
# Generate all theme files from a single palette definition
cargo install tinty
tinty init

# Point to your custom scheme
mkdir -p ~/.config/tinted-theming/schemes
cp ~/your-scheme.yaml ~/.config/tinted-theming/schemes/

# Apply to all configured templates at once
tinty apply your-scheme-name

# Re-apply after adding a new application template
tinty apply --sync your-scheme-name
```

tinty supports templates for: Alacritty, Foot, Kitty, WezTerm, Helix, Neovim, Vim, Emacs, Waybar, rofi, fzf, bat, delta, and dozens more. Adding a new application means writing one template file, not editing the application's config directly.

### Opacity Recommendations by Aesthetic

| Aesthetic | Terminal bg opacity | Bar opacity | Inactive window opacity |
|---|---|---|---|
| Tokyo Night | 0.92–0.95 | 0.88–0.92 | 0.88–0.92 |
| Cyberpunk Neon | 0.80–0.88 | 0.70–0.80 | 0.80–0.85 |
| Tron | 0.95–1.00 | 0.94–0.97 | 0.90–0.95 |

Higher opacity = cleaner, more readable, less "rice". Lower opacity = more effect-heavy, wallpaper bleeds through. Tron's aesthetic demands high opacity because blur is disabled — the wallpaper behind a blurless transparent window is visually distracting.

### Animation Speed by Aesthetic

| Aesthetic | Window open (ms) | Workspace switch (ms) | Character |
|---|---|---|---|
| Tokyo Night | 200–280 | 300–400 | Smooth, slightly floaty |
| Cyberpunk Neon | 100–150 | 150–200 | Fast, snappy, electric |
| Tron | 80–120 | 80–120 | Near-instant, mechanical |

```ini
# Fast Tron animations
animation = windows, 1, 2, tronLinear, slide
# Slow Tokyo Night animations
animation = windows, 1, 5, tokyoSnap, slide
# Medium Cyberpunk
animation = windows, 1, 3, cyber, slide
```

### Adapting Existing Themes

Most established rices use one of these three as a starting template before customizing:

```
Catppuccin Mocha → Tokyo Night (reduce blue saturation, shift hue from purple toward blue)
Dracula          → Cyberpunk Neon (push magenta to 100% saturation, desaturate green/yellow)
Nord             → Tron (rotate hue from cool gray-blue toward pure cyan, darken backgrounds)
```

---

## 112.7 Consistency Checklist

Run this before calling a rice finished:

```bash
#!/bin/bash
# ~/.local/bin/rice-audit

PALETTE_COLORS=(
    "1a1b26" "16161e" "2f3549" "444b6a"   # Tokyo Night — replace with yours
    "787c99" "c0caf5" "cbccd1" "d5d6db"
    "f7768e" "ff9e64" "e0af68" "9ece6a"
    "7dcfff" "7aa2f7" "bb9af7" "9d7cd8"
)

CONFIG_DIRS=(
    ~/.config/hypr
    ~/.config/waybar
    ~/.config/kitty
    ~/.config/alacritty
    ~/.config/foot
    ~/.config/mako
    ~/.config/dunst
    ~/.config/rofi
)

echo "=== Hex colors found outside palette ==="
for dir in "${CONFIG_DIRS[@]}"; do
    grep -roh '#[0-9a-fA-F]\{6\}' "$dir" 2>/dev/null
done | tr '[:upper:]' '[:lower:]' | sort -u | while read -r color; do
    bare="${color#'#'}"
    found=false
    for palette_color in "${PALETTE_COLORS[@]}"; do
        if [ "$bare" = "$palette_color" ]; then
            found=true; break
        fi
    done
    if ! $found; then
        echo "  UNLISTED: $color"
    fi
done
```

Any color printed as `UNLISTED` is either a stray value that should be replaced with the nearest palette color, or a deliberate exception (transparency `00` suffix, truly neutral grays) that should be documented.

---

## Summary

The three aesthetics in this chapter teach three distinct ricing philosophies:

- **Tokyo Night** — work *with* the theme ecosystem; wire existing well-crafted themes together; achieve consistency through base16 tooling
- **Cyberpunk Neon** — work *against* restraint; every effect turned up, but intentionally; CSS glow and blur do the heavy lifting; the wallpaper sets the energy
- **Tron** — work *through subtraction*; the absence of blur, rounded corners, and animation speed creates the aesthetic; one color does everything

The meta-lesson: a rice is not a collection of themes — it is a design decision expressed through configuration. Decide the feeling first, build the palette from that feeling, apply systematically from the wallpaper up, and verify consistency before shipping.

**Further reading:**
- Ch 34 — color theory and base16 palette mathematics
- Ch 38 — pywal/matugen for wallpaper-driven palette generation
- Ch 92 — GLSL shaders in compositors (scanline effects, color grading)
- Ch 106 — automated theme switching (day/night variants of the same aesthetic)
- Ch 40 — Stylix for NixOS declarative aesthetic application
