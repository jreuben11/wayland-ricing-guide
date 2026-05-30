# Chapter 87 — Font Rendering Deep Dive: fontconfig, Hinting, CJK

## Contents

- [Overview](#overview)
- [87.1 The Font Stack](#871-the-font-stack)
- [87.2 fontconfig Configuration Files](#872-fontconfig-configuration-files)
  - [Minimal user fonts.conf](#minimal-user-fontsconf)
- [87.3 Rendering Parameters](#873-rendering-parameters)
  - [antialias](#antialias)
  - [hinting and hintstyle](#hinting-and-hintstyle)
  - [rgba (subpixel rendering)](#rgba-subpixel-rendering)
  - [lcdfilter](#lcdfilter)
  - [Complete rendering block](#complete-rendering-block)
- [87.4 Font Preference and Aliases](#874-font-preference-and-aliases)
  - [Setting preferred fonts by generic family](#setting-preferred-fonts-by-generic-family)
  - [Substituting one font for another](#substituting-one-font-for-another)
  - [Per-application font overrides](#per-application-font-overrides)
- [87.5 CJK Fallback Chains](#875-cjk-fallback-chains)
  - [The CJK problem](#the-cjk-problem)
  - [Proper CJK fallback configuration](#proper-cjk-fallback-configuration)
  - [Emoji font](#emoji-font)
- [87.6 Nerd Font Installation and Configuration](#876-nerd-font-installation-and-configuration)
  - [Verify the font is installed](#verify-the-font-is-installed)
  - [fontconfig for Nerd Fonts](#fontconfig-for-nerd-fonts)
- [87.7 DPI and HiDPI on Wayland](#877-dpi-and-hidpi-on-wayland)
  - [Checking DPI](#checking-dpi)
  - [Forcing font DPI for specific apps](#forcing-font-dpi-for-specific-apps)
- [87.8 fontconfig Debugging](#878-fontconfig-debugging)
  - [Common mismatches to check](#common-mismatches-to-check)
- [87.9 Complete Recommended fonts.conf](#879-complete-recommended-fontsconf)
- [87.10 Nerd Font Glyph Verification](#8710-nerd-font-glyph-verification)
  - [Verifying in Different Applications](#verifying-in-different-applications)
  - [Bitmap Fonts on Wayland](#bitmap-fonts-on-wayland)

---


## Overview

Every character on your desktop passes through fontconfig before it reaches
the screen. Getting it right means crisp text at any DPI; getting it wrong
means blurry or jagged glyphs that make an otherwise beautiful rice ugly.
This chapter covers the full pipeline: fontconfig XML, rendering parameters,
CJK fallback chains, Nerd Font patching, and Wayland-specific DPI handling.

---

## 87.1 The Font Stack

```
Application (GTK/Qt/QML)
    ↓ requests font family + size
fontconfig (font selection + substitution rules)
    ↓ returns font file path + rendering hints
FreeType2 (rasterisation: hinting, antialiasing, subpixel)
    ↓ returns bitmap
HarfBuzz (complex shaping: Arabic, Devanagari, ligatures)
    ↓ returns glyph positions
Cairo / Pango / Qt text engine
    ↓
Wayland client surface → compositor → display
```

fontconfig controls font selection and rendering parameters. FreeType2 does
the actual pixel rendering. On Wayland, DPI comes from `wl_output.scale` and
`wp_fractional_scale` rather than X11's 96dpi assumption.

---

## 87.2 fontconfig Configuration Files

fontconfig loads files in order:

```
/etc/fonts/fonts.conf           ← distro base (do not edit)
/etc/fonts/conf.d/*.conf        ← distro presets (symlinks)
~/.config/fontconfig/fonts.conf ← user config (primary editing target)
~/.config/fontconfig/conf.d/    ← user drop-in files
```

The user file is the correct place for all customization. The distro files
are replaced on package updates.

### Minimal user fonts.conf

```xml
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>
  <!-- Your rules go here -->
</fontconfig>
```

---

## 87.3 Rendering Parameters

These are the four parameters that define how text looks:

### antialias

```xml
<match target="font">
  <edit name="antialias" mode="assign">
    <bool>true</bool>    <!-- almost always true; false = 1-bit aliased -->
  </edit>
</match>
```

### hinting and hintstyle

Hinting adjusts glyph outlines to align with the pixel grid:

```xml
<match target="font">
  <edit name="hinting" mode="assign"><bool>true</bool></edit>
  <edit name="hintstyle" mode="assign">
    <const>hintslight</const>   <!-- hintnone | hintslight | hintmedium | hintfull -->
  </edit>
</match>
```

| hintstyle | Description | Best for |
|-----------|-------------|----------|
| `hintnone` | No hinting — pure outline | HiDPI (1.5x+), vector fonts |
| `hintslight` | Subtle adjustment | HiDPI, retains letter shapes |
| `hintmedium` | Moderate | 1x standard DPI |
| `hintfull` | Strong pixel-grid alignment | Low DPI bitmap-like look |

**Rule of thumb:** `hintslight` for HiDPI displays (fractional scale ≥ 1.5),
`hintmedium` or `hintfull` for 1:1 pixel density.

### rgba (subpixel rendering)

Subpixel rendering exploits the R/G/B layout of LCD pixels for 3× horizontal
resolution. Only works on LCD; useless on OLED:

```xml
<match target="font">
  <edit name="rgba" mode="assign">
    <const>rgb</const>   <!-- none | rgb | bgr | vrgb | vbgr -->
  </edit>
</match>
```

Most monitors are `rgb` (red-green-blue left to right). Rotated monitors may
need `vrgb`. OLED/CRT: use `none`.

### lcdfilter

Reduces color fringing from subpixel rendering:

```xml
<match target="font">
  <edit name="lcdfilter" mode="assign">
    <const>lcddefault</const>   <!-- lcdnone | lcddefault | lcdlight | lcdlegacy -->
  </edit>
</match>
```

`lcddefault` is correct for most displays. `lcdlight` for sharper text at
the cost of more fringing.

### Complete rendering block

```xml
<!-- ~/.config/fontconfig/fonts.conf -->
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>

  <!-- Global rendering defaults -->
  <match target="font">
    <edit name="antialias"  mode="assign"><bool>true</bool></edit>
    <edit name="hinting"    mode="assign"><bool>true</bool></edit>
    <edit name="hintstyle"  mode="assign"><const>hintslight</const></edit>
    <edit name="rgba"       mode="assign"><const>rgb</const></edit>
    <edit name="lcdfilter"  mode="assign"><const>lcddefault</const></edit>
    <edit name="embeddedbitmap" mode="assign"><bool>false</bool></edit>
  </match>

</fontconfig>
```

`embeddedbitmap false` prevents fonts that ship with bitmap strikes from using
them at small sizes — the vector outlines render better at modern DPI.

---

## 87.4 Font Preference and Aliases

### Setting preferred fonts by generic family

```xml
<!-- Prefer JetBrains Mono for monospace -->
<alias>
  <family>monospace</family>
  <prefer>
    <family>JetBrainsMono Nerd Font</family>
    <family>JetBrains Mono</family>
    <family>Iosevka</family>
    <family>DejaVu Sans Mono</family>
  </prefer>
</alias>

<!-- Prefer Inter for sans-serif -->
<alias>
  <family>sans-serif</family>
  <prefer>
    <family>Inter</family>
    <family>Noto Sans</family>
    <family>DejaVu Sans</family>
  </prefer>
</alias>

<!-- Prefer Source Serif 4 for serif -->
<alias>
  <family>serif</family>
  <prefer>
    <family>Source Serif 4</family>
    <family>Noto Serif</family>
    <family>DejaVu Serif</family>
  </prefer>
</alias>
```

### Substituting one font for another

```xml
<!-- Use Noto Sans when Liberation Sans is requested (common in PDFs) -->
<match target="pattern">
  <test name="family" compare="eq"><string>Liberation Sans</string></test>
  <edit name="family" mode="assign_replace"><string>Noto Sans</string></edit>
</match>
```

### Per-application font overrides

```xml
<!-- Use hintfull for terminal emulators (small text, 1:1 pixels) -->
<match target="pattern">
  <test name="prgname" compare="eq"><string>foot</string></test>
  <edit name="hintstyle" mode="assign"><const>hintfull</const></edit>
</match>

<!-- Disable subpixel for Firefox (renders its own text) -->
<match target="pattern">
  <test name="prgname" compare="eq"><string>firefox</string></test>
  <edit name="rgba" mode="assign"><const>none</const></edit>
</match>
```

---

## 87.5 CJK Fallback Chains

Without proper CJK configuration, Chinese/Japanese/Korean characters fall
back to whatever font fontconfig finds first — often the wrong one (a Chinese
font rendering Japanese text, for example).

### The CJK problem

Several Unicode code points exist in all three scripts but look different
per language. The correct glyph depends on which language the user is reading.
fontconfig uses the `lang` property to select the right font.

### Proper CJK fallback configuration

```xml
<!-- Simplified Chinese (zh-CN, zh-SG) -->
<match target="pattern">
  <test name="lang" compare="contains"><string>zh-CN</string></test>
  <edit name="family" mode="prepend">
    <string>Noto Sans CJK SC</string>
  </edit>
</match>
<match target="pattern">
  <test name="lang" compare="contains"><string>zh-SG</string></test>
  <edit name="family" mode="prepend">
    <string>Noto Sans CJK SC</string>
  </edit>
</match>

<!-- Traditional Chinese (zh-TW, zh-HK) -->
<match target="pattern">
  <test name="lang" compare="contains"><string>zh-TW</string></test>
  <edit name="family" mode="prepend">
    <string>Noto Sans CJK TC</string>
  </edit>
</match>

<!-- Japanese -->
<match target="pattern">
  <test name="lang" compare="contains"><string>ja</string></test>
  <edit name="family" mode="prepend">
    <string>Noto Sans CJK JP</string>
  </edit>
</match>

<!-- Korean -->
<match target="pattern">
  <test name="lang" compare="contains"><string>ko</string></test>
  <edit name="family" mode="prepend">
    <string>Noto Sans CJK KR</string>
  </edit>
</match>
```

Install all variants: `sudo pacman -S noto-fonts-cjk`

### Emoji font

```xml
<!-- Emoji — must come after CJK, before generic fallback -->
<alias>
  <family>sans-serif</family>
  <prefer>
    <family>Inter</family>
    <family>Noto Sans CJK SC</family>
    <family>Noto Color Emoji</family>
  </prefer>
</alias>
```

`sudo pacman -S noto-fonts-emoji`

---

## 87.6 Nerd Font Installation and Configuration

Nerd Fonts patch icon glyphs into existing fonts. The patched family name
appends " Nerd Font" or " NF".

```bash
# Via AUR (pre-patched)
paru -S ttf-jetbrains-mono-nerd
paru -S ttf-nerd-fonts-symbols    # symbols only, if you already have the base font

# Manual: download from nerdfonts.com, place in:
mkdir -p ~/.local/share/fonts
cp *.ttf ~/.local/share/fonts/
fc-cache -fv   # rebuild font cache
```

### Verify the font is installed

```bash
fc-list | grep -i "JetBrains"
# JetBrainsMono Nerd Font:style=Regular
# JetBrainsMono Nerd Font Mono:style=Regular   ← Mono variant (fixed icon width)
```

Use the **Mono** variant in terminals — it forces all icons to a single cell width,
preventing layout shifts in status bars and prompts.

### fontconfig for Nerd Fonts

```xml
<!-- Ensure NF icons don't fall back to another font -->
<alias>
  <family>monospace</family>
  <prefer>
    <family>JetBrainsMono Nerd Font Mono</family>
    <family>Symbols Nerd Font Mono</family>
    <family>Noto Color Emoji</family>
  </prefer>
</alias>
```

---

## 87.7 DPI and HiDPI on Wayland

Wayland communicates display scale through `wl_output.scale` (integer) and
`wp_fractional_scale_v1` (fractional). Applications receive this and scale
their font rendering accordingly — no `Xft.dpi` resource needed.

### Checking DPI

```bash
# DPI from monitor EDID (physical size)
wlr-randr                    # shows WxH and physical mm dimensions

# Calculate: DPI = pixels / (mm / 25.4)
# Example: 2560×1440 on a 310mm wide display
# DPI = 2560 / (310/25.4) = 2560 / 12.2 = ~210 ppi

# What applications see:
WAYLAND_DISPLAY=wayland-1 weston-info | grep -i dpi
```

### Forcing font DPI for specific apps

Some apps (older GTK3, some Electron) ignore Wayland scale and need explicit
DPI. Set via `FONT_DPI` or GTK settings:

```bash
# ~/.config/gtk-3.0/settings.ini
[Settings]
gtk-xft-dpi=192        # 192 = 2× 96dpi (for 2× HiDPI)
gtk-xft-antialias=1
gtk-xft-hinting=1
gtk-xft-hintstyle=hintslight
gtk-xft-rgba=rgb
```

```bash
# For QT apps:
export QT_FONT_DPI=192
```

---

## 87.8 fontconfig Debugging

```bash
# Which font does fontconfig actually select?
fc-match "JetBrainsMono Nerd Font"
fc-match monospace
fc-match "sans-serif:lang=ja"    # Japanese sans-serif

# Verbose: show full match chain
fc-match -v monospace | head -40

# List all fonts matching a pattern
fc-list "Noto*" | sort

# What properties does a font file have?
fc-query /usr/share/fonts/TTF/JetBrainsMono-Regular.ttf | head -30

# Show which rule matched (slow but complete)
FC_DEBUG=1 fc-match monospace 2>&1 | grep -E "family|hintstyle|rgba"

# Rebuild cache after installing fonts
fc-cache -fv
```

### Common mismatches to check

```bash
# Is the Nerd Font variant actually being used?
fc-match "JetBrainsMono Nerd Font Mono:style=Regular"
# Should show: JetBrainsMono Nerd Font Mono... (not a fallback)

# Is Japanese using the right font?
fc-match "sans-serif:lang=ja"
# Should show: NotoSansCJK-Regular.ttc... (not a Chinese variant)

# Is emoji being found?
fc-match "Noto Color Emoji"
```

---

## 87.9 Complete Recommended fonts.conf

```xml
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>

  <!-- Rendering: optimised for HiDPI LCD -->
  <match target="font">
    <edit name="antialias"      mode="assign"><bool>true</bool></edit>
    <edit name="hinting"        mode="assign"><bool>true</bool></edit>
    <edit name="hintstyle"      mode="assign"><const>hintslight</const></edit>
    <edit name="rgba"           mode="assign"><const>rgb</const></edit>
    <edit name="lcdfilter"      mode="assign"><const>lcddefault</const></edit>
    <edit name="embeddedbitmap" mode="assign"><bool>false</bool></edit>
  </match>

  <!-- Prefer sharper hinting for terminal -->
  <match target="pattern">
    <test name="prgname" compare="contains"><string>term</string></test>
    <edit name="hintstyle" mode="assign"><const>hintmedium</const></edit>
  </match>

  <!-- Sans-serif family preference -->
  <alias>
    <family>sans-serif</family>
    <prefer>
      <family>Inter</family>
      <family>Noto Sans CJK SC</family>
      <family>Noto Color Emoji</family>
      <family>Noto Sans</family>
    </prefer>
  </alias>

  <!-- Monospace family preference -->
  <alias>
    <family>monospace</family>
    <prefer>
      <family>JetBrainsMono Nerd Font Mono</family>
      <family>Symbols Nerd Font Mono</family>
      <family>Noto Color Emoji</family>
    </prefer>
  </alias>

  <!-- CJK per-language selection -->
  <match target="pattern">
    <test name="lang" compare="contains"><string>zh-CN</string></test>
    <edit name="family" mode="prepend"><string>Noto Sans CJK SC</string></edit>
  </match>
  <match target="pattern">
    <test name="lang" compare="contains"><string>zh-TW</string></test>
    <edit name="family" mode="prepend"><string>Noto Sans CJK TC</string></edit>
  </match>
  <match target="pattern">
    <test name="lang" compare="contains"><string>ja</string></test>
    <edit name="family" mode="prepend"><string>Noto Sans CJK JP</string></edit>
  </match>
  <match target="pattern">
    <test name="lang" compare="contains"><string>ko</string></test>
    <edit name="family" mode="prepend"><string>Noto Sans CJK KR</string></edit>
  </match>

</fontconfig>
```

---

## 87.10 Nerd Font Glyph Verification

After installing a Nerd Font, verify that glyph rendering works end-to-end:

```bash
# Check the font is registered with fontconfig
fc-list | grep -i "JetBrains"
# Should show: JetBrainsMono Nerd Font, JetBrainsMono Nerd Font Mono

# Verify glyph coverage using fc-query
fc-query /usr/share/fonts/TTF/JetBrainsMonoNerdFont-Regular.ttf | grep -i "char\|coverage"

# Quick glyph test — paste this into your terminal
echo "  ✓ ✗ ★ ⚡ 󰀫 󰄛 󰊿 󰌒 󰌓 󰌰 󰏖 󰣇 󰦗 󰧑"
#     nf-fa nf-dev nf-oct nf-cod ... icons

# Powerline symbols test
echo "               "
# Should show filled/empty triangles and arrows (Powerline glyphs)

# Systematic glyph range test script
python3 << 'EOF'
ranges = [
    (0xE0A0, 0xE0A3, "Powerline extra"),
    (0xE0B0, 0xE0BF, "Powerline symbols"),
    (0xF0000, 0xF1000, "Custom Private Use"),
    (0xE000, 0xE00D, "Pomicons"),
    (0xEA60, 0xEB30, "Codicons"),
]
for start, end, name in ranges:
    glyphs = ''.join(chr(i) for i in range(start, min(end, start+16)))
    print(f"{name}: {glyphs}")
EOF

# Check specific glyph by Unicode codepoint
python3 -c "print(chr(0xf013))"   # nf-fa-cog (gear icon)
python3 -c "print(chr(0xe0b0))"   # Powerline right arrow
```

### Verifying in Different Applications

```bash
# In waybar — if icons are squares/question marks, the font is not loading
# Check waybar with:
waybar &
# If you see □ instead of icons, the font config in waybar/config is wrong

# Common waybar font config mistake:
# Wrong:  "font-family": "JetBrains Mono"           ← no Nerd Font glyphs
# Right:  "font-family": "JetBrainsMono Nerd Font"  ← correct family name

# Verify exact family name for waybar/CSS:
fc-list | grep -i "jetbrains" | awk -F: '{print $2}' | sort -u
```

### Bitmap Fonts on Wayland

Bitmap fonts (`.pcf`, `.bdf`) are fixed-pixel fonts with no vector scaling. They are used for retro ricing aesthetics and ultra-small sizes.

```bash
# Install classic bitmap fonts
sudo pacman -S bdf-unifont terminus-font

# Terminus — the most popular bitmap font for ricing
fc-list | grep -i "terminus"
# Terminus:style=Regular,Bold  (at specific sizes)
```

```xml
<!-- fontconfig: allow bitmap fonts (disabled by default in most distros) -->
<!-- ~/.config/fontconfig/fonts.conf -->
<match target="font">
  <edit name="embeddedbitmap" mode="assign"><bool>true</bool></edit>
</match>

<!-- Allow specific bitmap font family -->
<selectfont>
  <acceptfont>
    <pattern>
      <patelt name="family"><string>Terminus</string></patelt>
    </pattern>
  </acceptfont>
</selectfont>
```

```bash
# Use Terminus in kitty (specify exact pixel size)
# kitty.conf
# font_family Terminus
# font_size   16.0    # must match a bitmap strike size: 8, 12, 14, 16, 20, 24, 28, 32

# Verify bitmap strikes available in a font
fc-query /usr/share/fonts/misc/ter-x16b.pcf.gz | grep -i "size\|pixel"

# Foot with terminus
# foot.ini
# [main]
# font=Terminus:size=16
```

Bitmap fonts do not scale — they look sharp at their designed size and terrible at others. For retro ricing, pair with a terminal configured to exactly match the strike size and a compositor with no DPI scaling (scale=1.0).

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
