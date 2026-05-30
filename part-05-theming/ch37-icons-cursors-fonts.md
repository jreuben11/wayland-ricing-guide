# Chapter 37 — Icon Packs, Cursors, and Fonts

## Contents

- [Overview](#overview)
- [37.1 Icon Themes](#371-icon-themes)
  - [How Icon Themes Work](#how-icon-themes-work)
  - [Popular Icon Themes](#popular-icon-themes)
  - [Installing Icon Themes](#installing-icon-themes)
  - [Setting the Icon Theme](#setting-the-icon-theme)
- [37.2 Cursor Themes](#372-cursor-themes)
  - [Cursor Theme Structure](#cursor-theme-structure)
  - [Popular Cursor Themes](#popular-cursor-themes)
  - [Installing Cursor Themes](#installing-cursor-themes)
  - [Setting Cursors on Wayland](#setting-cursors-on-wayland)
  - [XWayland Cursor Size Mismatch Fix](#xwayland-cursor-size-mismatch-fix)
- [37.3 Font Selection for Ricing](#373-font-selection-for-ricing)
  - [Font Categories and Their Roles](#font-categories-and-their-roles)
  - [Nerd Fonts](#nerd-fonts)
  - [Fontconfig Configuration](#fontconfig-configuration)
  - [Font Rendering on HiDPI](#font-rendering-on-hidpi)
- [37.4 Terminal Font Rendering](#374-terminal-font-rendering)
  - [Kitty](#kitty)
  - [Alacritty](#alacritty)
  - [Foot](#foot)
  - [WezTerm](#wezterm)
  - [Font Size Guidelines](#font-size-guidelines)
- [37.5 Emoji Support](#375-emoji-support)
  - [Installing Emoji Fonts](#installing-emoji-fonts)
  - [Fontconfig Emoji Fallback](#fontconfig-emoji-fallback)
  - [Terminal Emoji Rendering](#terminal-emoji-rendering)
- [37.6 Managing Fonts with fc-query and fc-list](#376-managing-fonts-with-fc-query-and-fc-list)
- [37.7 Applying Themes with nwg-look](#377-applying-themes-with-nwg-look)
- [Troubleshooting](#troubleshooting)
  - [Icons Not Updating After Theme Change](#icons-not-updating-after-theme-change)
  - [Wrong Icon Theme in Flatpak Apps](#wrong-icon-theme-in-flatpak-apps)
  - [Cursor Theme Not Applying to Some Apps](#cursor-theme-not-applying-to-some-apps)
  - [Cursor Too Small/Large on HiDPI](#cursor-too-smalllarge-on-hidpi)
  - [Font Not Found in Terminal](#font-not-found-in-terminal)
  - [Fontconfig Cache Stale](#fontconfig-cache-stale)
  - [Emoji Showing as Boxes or Monochrome](#emoji-showing-as-boxes-or-monochrome)
  - [GTK Apps Ignoring settings.ini](#gtk-apps-ignoring-settingsini)

---


## Overview

Icons, cursors, and fonts are the finishing touches that unify a rice. Together they form the visual language of the desktop: icons communicate application identity and action semantics, cursors provide haptic-like feedback for pointer interactions, and fonts govern readability and aesthetic tone across every surface. Getting these three elements to harmonize — and to render consistently across GTK apps, Qt apps, Electron shells, terminals, and Wayland-native clients — requires understanding several layered subsystems that often interact in non-obvious ways.

This chapter takes a bottom-up approach. We examine the directory specifications and metadata formats that govern each asset type, explore tools for installation and selection, and work through per-compositor and per-toolkit configuration. Special attention is paid to Wayland-specific wrinkles: cursor protocol differences between compositors, XCURSOR environment variable scope, fontconfig cache management, and HiDPI scaling edge cases. We close with a structured Troubleshooting section covering the failure modes you are most likely to encounter.

*Cross-references: See Ch 34 for GTK/Qt theming pipelines, Ch 38 for applying themes in Hyprland, Ch 53 for session environment variables at startup, Ch 61 for HiDPI and fractional scaling.*

---

## 37.1 Icon Themes

### How Icon Themes Work

The freedesktop.org Icon Theme Specification defines a directory hierarchy under which icon images are stored, organized first by context category (apps, devices, mimetypes, places, status, actions) and then by size. Each theme root directory contains an `index.theme` file that names the theme, specifies its parent (the fallback chain), and enumerates its subdirectories.

When a toolkit resolves an icon name such as `text-editor` or `folder-open`, it walks the current theme's directories from highest to lowest resolution until it finds a matching filename. If nothing is found in the current theme, it ascends to the parent theme listed in `index.theme`, and so on until reaching the mandatory `hicolor` theme, which every compliant theme must eventually chain to. This means `hicolor` serves as the universal backstop — any icon not found elsewhere will fall back there. Installing a new application typically drops its icons in `/usr/share/icons/hicolor/`.

User-level icon themes live in `~/.local/share/icons/`, while system-wide themes go in `/usr/share/icons/`. Both paths are consulted, with user paths taking precedence. Within each path, the structure is:

```
ThemeName/
├── index.theme
├── 16x16/
│   ├── apps/
│   ├── actions/
│   ├── devices/
│   ├── mimetypes/
│   ├── places/
│   └── status/
├── 32x32/
├── 48x48/
├── 64x64/
├── 128x128/
└── scalable/
    ├── apps/
    └── ...
```

SVG icons in `scalable/` are resolution-independent and preferred for HiDPI setups, but they require a vector renderer at draw time. PNG icons in fixed-size directories are pre-rasterized and render faster. Many themes ship both. Toolkits like GTK 4 prefer SVG when available; older GTK 2 applications often only use PNGs. Check `gtk4-icon-browser` (part of `gtk4-demos`) to inspect what icons a theme actually provides.

Dark and light icon variants are handled differently depending on the theme. Some themes ship a companion `ThemeName-Dark` directory; others use the `AdaptiveIconVariants` key in `index.theme` (a newer extension). Still others embed dark variants in a dedicated subdirectory such as `symbolic/` using single-color SVGs that toolkits recolor at runtime based on the current foreground color. Symbolic icons are always preferred in context menus and notifications because they adapt to dark and light backgrounds automatically.

### Popular Icon Themes

| Theme | Style | Size of Coverage | Best For |
|-------|-------|-----------------|----------|
| Papirus | Flat, colorful | Enormous (~12 000 icons) | General use, dark rices |
| Papirus-Dark | Dark variant of Papirus | Same | Dark GTK themes |
| Papirus-Light | Light variant | Same | Light themes |
| Tela | Minimal flat, rounded | Large | Clean/minimal setups |
| Fluent | Windows 11 inspired | Large | Win-lookalike rices |
| WhiteSur | macOS Big Sur | Large | macOS-lookalike rices |
| Numix Circle | Circular icons | Medium | Classic, retro feel |
| candy-icons | Gradient, vivid | Medium | Eye-candy/vibrant rices |
| Gruvbox Plus | Gruvbox palette | Large | Gruvbox color scheme setups |
| Catppuccin (papirus-folders) | Catppuccin accent folders | Papirus base + colored folders | Catppuccin theme setups |
| Colloid | Rounded modern | Large | Nord/Everforest rices |

`papirus-folders` is a utility that recolors the folder icons inside an existing Papirus installation to a custom accent color, making it trivial to match any color scheme without a separate theme:

```bash
# Install papirus-folders (AUR or manual from GitHub)
paru -S papirus-folders-git

# List available color targets
papirus-folders -l

# Apply Catppuccin Mocha Mauve accent
papirus-folders -C cat-mocha-mauve --theme Papirus-Dark

# Revert to default
papirus-folders -C default --theme Papirus-Dark
```

### Installing Icon Themes

Most popular themes are available in distribution repositories or the AUR. For maximum flexibility, install from source so you can pin versions and patch palettes:

```bash
# Arch Linux: install from official repos / AUR
sudo pacman -S papirus-icon-theme
paru -S tela-icon-theme-git

# Debian/Ubuntu
sudo apt install papirus-icon-theme

# Manual install from GitHub into user directory
git clone https://github.com/vinceliuice/Tela-icon-theme.git /tmp/tela
cd /tmp/tela
./install.sh -d ~/.local/share/icons -n Tela

# After any manual installation, rebuild the icon cache:
gtk-update-icon-cache -f -t ~/.local/share/icons/Tela
```

Rebuilding the icon cache (`gtk-update-icon-cache`) is mandatory after manual installs; without it GTK will not discover the new theme even if the files are present.

### Setting the Icon Theme

GTK 3/4 applications read the icon theme from GSettings at runtime. Set it with `gsettings` or by editing `~/.config/gtk-3.0/settings.ini` and `~/.config/gtk-4.0/settings.ini`:

```bash
# Via gsettings (applies immediately to running GTK apps if xdg-desktop-portal is active)
gsettings set org.gnome.desktop.interface icon-theme "Papirus-Dark"

# Verify the setting
gsettings get org.gnome.desktop.interface icon-theme
```

```ini
# ~/.config/gtk-3.0/settings.ini
[Settings]
gtk-icon-theme-name=Papirus-Dark
gtk-font-name=Inter 10
gtk-cursor-theme-name=Catppuccin-Mocha-Dark-Cursors
gtk-cursor-theme-size=24
gtk-toolbar-style=GTK_TOOLBAR_ICONS
gtk-toolbar-icon-size=GTK_ICON_SIZE_SMALL_TOOLBAR
gtk-button-images=0
gtk-menu-images=0
gtk-enable-event-sounds=0
gtk-enable-input-feedback-sounds=0
gtk-xft-antialias=1
gtk-xft-hinting=1
gtk-xft-hintstyle=hintslight
gtk-xft-rgba=rgb
```

```ini
# ~/.config/gtk-4.0/settings.ini
[Settings]
gtk-icon-theme-name=Papirus-Dark
gtk-font-name=Inter 10
gtk-cursor-theme-name=Catppuccin-Mocha-Dark-Cursors
gtk-cursor-theme-size=24
```

Qt applications use a separate mechanism. Under a Wayland session you typically configure Qt via `qt5ct` or `qt6ct`:

```bash
# Install qt5ct and qt6ct
sudo pacman -S qt5ct qt6ct

# Add to environment (e.g., in ~/.config/hypr/hyprland.conf or your session env file)
env = QT_QPA_PLATFORMTHEME,qt5ct
```

Then launch `qt5ct`, navigate to the Icon Theme tab, and select your preferred theme. Settings are written to `~/.config/qt5ct/qt5ct.conf`.

---

## 37.2 Cursor Themes

### Cursor Theme Structure

A cursor theme is an X Cursor theme stored under an icons directory entry, making it structurally part of the icon theme hierarchy. The root of a cursor theme looks like:

```
CursorThemeName/
├── cursors/            # xcursor binary files, one per cursor shape
│   ├── left_ptr
│   ├── text
│   ├── watch
│   ├── crosshair
│   └── ... (50+ shapes)
└── cursor.theme        # INO file listing Name and optional Inherits
```

The `cursors/` directory contains X Cursor format files (the `Xcursor` library format). Each file can store multiple sizes of the same cursor, and animated cursors store multiple frames at each size. Typical sizes shipped are 24, 32, 48, and 64 pixels; the compositor or toolkit selects the closest match to the requested size.

The `cursor.theme` file is minimal:

```ini
[Icon Theme]
Name=Catppuccin-Mocha-Dark-Cursors
Comment=Catppuccin Mocha Dark cursors
Inherits=Adwaita
```

`Inherits` provides the fallback — any cursor shape not found in this theme will be sourced from the named parent.

### Popular Cursor Themes

| Theme | Style | Sizes Available | Notes |
|-------|-------|----------------|-------|
| Catppuccin-Mocha-Dark-Cursors | Soft, pastel dark | 24, 32, 48, 64 | Multiple color flavors |
| Nordzy-cursors | Nord-palette inspired | 24, 32, 48 | Clean, geometric |
| Bibata-Modern-Classic | Clean, material black | 24, 32, 48 | Also Ice/Amber variants |
| Bibata-Modern-Ice | Like above, white | 24, 32, 48 | Good on dark backgrounds |
| Vimix-cursors | Minimal, thin | 24, 32, 48 | Multiple color options |
| Phinger-cursors | Cute, rounded | 24, 32, 48, 64 | Eye-catching |
| macOS-BigSur | macOS replica | 24, 32, 48 | Familiar to macOS users |
| Adwaita | GNOME default | Many | Always present as fallback |
| Breeze | KDE Plasma default | Many | Available on most distros |

### Installing Cursor Themes

```bash
# AUR installs
paru -S catppuccin-cursors-git
paru -S bibata-cursor-theme
paru -S nordzy-cursors-git

# Manual installation into user directory
git clone https://github.com/ful1e5/Bibata_Cursor.git /tmp/bibata
cp -r /tmp/bibata/themes/Bibata-Modern-Classic ~/.local/share/icons/

# Verify installation
ls ~/.local/share/icons/Bibata-Modern-Classic/cursors/ | head -10
```

### Setting Cursors on Wayland

Cursor configuration on Wayland requires setting it in multiple places because different surfaces are owned by different components: the compositor handles the root cursor, GTK apps handle their own, XWayland handles X11-emulated windows.

**Hyprland** (`~/.config/hypr/hyprland.conf`):

```ini
# Environment variables for cursor — set early so GTK apps pick them up
env = XCURSOR_THEME,Catppuccin-Mocha-Dark-Cursors
env = XCURSOR_SIZE,24

# Compositor-level cursor configuration (Hyprland >= 0.35)
cursor {
    no_hardware_cursors = false   # set true for NVIDIA if cursor glitches
    hotspot_padding = 1
    inactive_timeout = 0          # 0 = never hide
    no_break_fs_vrr = false
}
```

**Sway** (`~/.config/sway/config`):

```
seat seat0 xcursor_theme Catppuccin-Mocha-Dark-Cursors 24
```

**nwg-look / lxappearance** — These GUI tools write cursor settings to GTK config files and optionally set the default cursor symlink, which is the most robust cross-toolkit approach:

```bash
# Set default cursor symlink — resolves cursor for all X11/Xwayland apps
mkdir -p ~/.local/share/icons/default
cat > ~/.local/share/icons/default/index.theme <<'EOF'
[Icon Theme]
Name=default
Comment=Default cursor theme
Inherits=Catppuccin-Mocha-Dark-Cursors
EOF
```

**GTK settings** (required alongside compositor settings):

```ini
# ~/.config/gtk-3.0/settings.ini
gtk-cursor-theme-name=Catppuccin-Mocha-Dark-Cursors
gtk-cursor-theme-size=24
```

**Electron / Chromium-based apps** on Wayland often ignore the GTK cursor setting. Pass the cursor theme via environment instead:

```bash
# In your session environment or hyprland.conf env block:
env = XCURSOR_THEME,Catppuccin-Mocha-Dark-Cursors
env = XCURSOR_SIZE,24
```

### XWayland Cursor Size Mismatch Fix

XWayland apps inherit cursor themes through the `XCURSOR_THEME` and `XCURSOR_SIZE` environment variables, not through Wayland protocols. If these are not set, XWayland falls back to the `default` cursor theme, which is usually `Adwaita` at size 24. This causes a visible mismatch on HiDPI or when using a custom theme.

The definitive fix is to ensure both variables are set before any XWayland client starts — i.e., in your compositor's `env` block or in `~/.config/environment.d/cursor.conf`:

```ini
# ~/.config/environment.d/cursor.conf
XCURSOR_THEME=Catppuccin-Mocha-Dark-Cursors
XCURSOR_SIZE=24
```

On NVIDIA GPUs, hardware cursor rendering can produce visual artifacts. Disable it:

```ini
# hyprland.conf
cursor {
    no_hardware_cursors = true
}
```

If you use fractional scaling (e.g., 1.5x), multiply your intended logical cursor size by the scale factor so the cursor renders at the correct physical pixel size. For a 1.5x scale and desired 24px logical cursor, set `XCURSOR_SIZE=36`.

---

## 37.3 Font Selection for Ricing

### Font Categories and Their Roles

Fonts in a riced desktop serve distinct roles, and mixing families that clash will undermine the aesthetic even when colors and icons are perfect. The four categories to think about are:

**UI Font** — used in window titles, menu labels, GTK/Qt widget text, notifications. Needs to be highly legible at 9–12pt, support a wide Unicode range, and have both regular and bold weights. Strong choices: `Inter`, `Geist`, `IBM Plex Sans`, `Noto Sans`, `Rubik`, `Nunito`.

**Monospace/Code Font** — used in terminals, text editors, and any fixed-width context. Ligature support is optional but fashionable. Nerd Font variants add icon glyphs. Strong choices: `JetBrains Mono`, `Fira Code`, `Cascadia Code`, `Iosevka`, `Hack`, `Commit Mono`.

**Display Font** — used in eww/AGS widgets, Waybar clock labels, lockscreen text, or desktop conky-style overlays where readability at large sizes matters more than small-size clarity. Choose something that matches your theme's personality: geometric sans (IBM Plex Mono), slab serif (Roboto Slab), or stylized (Orbitron for a tech aesthetic).

**Icon Font** — Nerd Fonts glyph-augmented monospace fonts. Technically a subtype of monospace, but treated separately because bars and prompts depend on specific codepoint coverage. Required for `starship`, `oh-my-posh`, most Waybar configurations, and any tool using `󰀀`-style icon syntax.

### Nerd Fonts

Nerd Fonts patches existing typefaces with over 3,600 additional glyphs drawn from Font Awesome, Material Design Icons, Devicons, Codicons, Octicons, and others. The project maintains a collection of ~50 pre-patched font families available from [nerdfonts.com](https://www.nerdfonts.com/).

Popular Nerd Font choices:

| Base Font | Nerd Font Name | Ligatures | Notes |
|-----------|---------------|-----------|-------|
| JetBrains Mono | JetBrainsMono Nerd Font | Yes | Most popular for terminals |
| Fira Code | FiraCode Nerd Font | Yes | Classic programming font |
| Cascadia Code | CaskaydiaCove Nerd Font | Yes | Microsoft's open-source font |
| Iosevka | IosevkaTerm Nerd Font | Yes | Ultra-configurable, narrow |
| Hack | Hack Nerd Font | No | Designed for source code |
| Inconsolata | InconsolataNerdFont | No | Clean, wide glyphs |
| Ubuntu Mono | UbuntuMono Nerd Font | No | Familiar on Ubuntu systems |

Installation options:

```bash
# Arch — AUR packages for individual fonts
paru -S ttf-jetbrains-mono-nerd
paru -S ttf-firacode-nerd
paru -S ttf-cascadia-code-nerd

# Or install the entire Nerd Fonts collection (large!)
paru -S nerd-fonts

# Manual: download a specific family from GitHub releases
mkdir -p ~/.local/share/fonts/JetBrainsMonoNerd
cd ~/.local/share/fonts/JetBrainsMonoNerd
wget "https://github.com/ryanoasis/nerd-fonts/releases/latest/download/JetBrainsMono.tar.xz"
tar -xf JetBrainsMono.tar.xz
fc-cache -fv ~/.local/share/fonts/
```

Verify a Nerd Font glyph renders correctly:

```bash
# Print a sample icon (nf-dev-linux) in the terminal
echo -e "  Linux"

# List all installed Nerd Font families
fc-list | grep -i "nerd"
```

### Fontconfig Configuration

Fontconfig (`/etc/fonts/` and `~/.config/fontconfig/`) controls font lookup, substitution, and rendering hints system-wide and per-user. The user config file at `~/.config/fontconfig/fonts.conf` (or `~/.config/fontconfig/conf.d/*.conf`) overrides system defaults.

A complete, well-tuned baseline configuration:

```xml
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>

  <!-- Rendering quality for LCD displays -->
  <match target="font">
    <edit name="antialias"  mode="assign"><bool>true</bool></edit>
    <edit name="hinting"    mode="assign"><bool>true</bool></edit>
    <edit name="hintstyle"  mode="assign"><const>hintslight</const></edit>
    <edit name="rgba"       mode="assign"><const>rgb</const></edit>
    <edit name="lcdfilter"  mode="assign"><const>lcddefault</const></edit>
    <edit name="autohint"   mode="assign"><bool>false</bool></edit>
  </match>

  <!-- Prefer user fonts over system fonts -->
  <dir>~/.local/share/fonts</dir>

  <!-- Set preferred sans-serif family -->
  <alias>
    <family>sans-serif</family>
    <prefer>
      <family>Inter</family>
      <family>Noto Sans</family>
    </prefer>
  </alias>

  <!-- Set preferred serif family -->
  <alias>
    <family>serif</family>
    <prefer>
      <family>IBM Plex Serif</family>
      <family>Noto Serif</family>
    </prefer>
  </alias>

  <!-- Set preferred monospace family -->
  <alias>
    <family>monospace</family>
    <prefer>
      <family>JetBrainsMono Nerd Font</family>
      <family>Noto Sans Mono</family>
    </prefer>
  </alias>

  <!-- Emoji fallback — ensure color emoji renders everywhere -->
  <alias>
    <family>emoji</family>
    <prefer>
      <family>Noto Color Emoji</family>
      <family>Twitter Color Emoji</family>
    </prefer>
  </alias>

  <!-- Prevent emoji font from hijacking normal text ranges -->
  <match target="pattern">
    <test qual="any" name="family"><string>serif</string></test>
    <edit name="family" mode="prepend_first"><string>Noto Color Emoji</string></edit>
  </match>

</fontconfig>
```

After editing fontconfig files, rebuild the cache:

```bash
fc-cache -fv
# Verify the preferred monospace resolved correctly:
fc-match monospace
```

### Font Rendering on HiDPI

On HiDPI displays (2x, 1.5x fractional scaling), fonts render at higher physical pixel densities. GTK 4 and Qt 6 handle this correctly when compositor scaling is set. Terminal emulators typically need their font size tuned independently.

For fractional scaling with Hyprland, set the monitor scale and ensure `GDK_SCALE` and `GDK_DPI_SCALE` are not set (they interfere with Wayland fractional scaling):

```ini
# hyprland.conf — 27-inch 2560x1440 monitor at 1.25x scale
monitor=DP-1,2560x1440@144,0x0,1.25

# Do NOT set GDK_SCALE on Wayland — it double-scales
# env = GDK_SCALE,2   ← only needed on X11 HiDPI
```

Fontconfig `dpi` can be overridden if fonts appear too small or large:

```xml
<!-- In ~/.config/fontconfig/fonts.conf -->
<match target="pattern">
  <edit name="dpi" mode="assign"><double>96</double></edit>
</match>
```

---

## 37.4 Terminal Font Rendering

Terminal emulators each have their own font configuration syntax. Below are production-ready snippets for the four most popular Wayland-native terminals.

### Kitty

```ini
# ~/.config/kitty/kitty.conf

font_family      JetBrainsMono Nerd Font
bold_font        JetBrainsMono Nerd Font Bold
italic_font      JetBrainsMono Nerd Font Italic
bold_italic_font JetBrainsMono Nerd Font Bold Italic

font_size        11.0

# Disable ligatures (uncomment to keep them)
# font_features JetBrainsMonoNF-Regular +liga +calt

# Adjust for HiDPI (set to 2 for 2x displays, leave at 1 for fractional)
# macos_thicken_font 0.75   # macOS only

# Symbol map: use NerdFonts symbols for icon ranges
symbol_map U+E000-U+E00A,U+EA60-U+EBEB,U+E0A0-U+E0C8 Symbols Nerd Font Mono
```

```bash
# Reload kitty config without restart
kill -SIGUSR1 $(pgrep kitty)

# List all fonts kitty can see
kitty +list-fonts | grep -i "jetbrains"
```

### Alacritty

```toml
# ~/.config/alacritty/alacritty.toml  (Alacritty >= 0.12 uses TOML)

[font]
size = 11.0

[font.normal]
family = "JetBrainsMono Nerd Font"
style  = "Regular"

[font.bold]
family = "JetBrainsMono Nerd Font"
style  = "Bold"

[font.italic]
family = "JetBrainsMono Nerd Font"
style  = "Italic"

[font.bold_italic]
family = "JetBrainsMono Nerd Font"
style  = "Bold Italic"

# Offset fine-tunes spacing between glyphs
[font.offset]
x = 0
y = 1

[font.glyph_offset]
x = 0
y = 0
```

### Foot

```ini
# ~/.config/foot/foot.ini

[main]
font=JetBrainsMono Nerd Font:size=11
font-bold=JetBrainsMono Nerd Font:weight=bold:size=11
font-italic=JetBrainsMono Nerd Font:slant=italic:size=11
font-bold-italic=JetBrainsMono Nerd Font:weight=bold:slant=italic:size=11

dpi-aware=yes           # respect the Wayland output scale
pad=4x4                 # padding in pixels
```

### WezTerm

```lua
-- ~/.config/wezterm/wezterm.lua
local wezterm = require 'wezterm'

return {
  font = wezterm.font_with_fallback({
    { family = 'JetBrainsMono Nerd Font', weight = 'Regular' },
    { family = 'Symbols Nerd Font Mono',  scale = 0.9 },
    { family = 'Noto Color Emoji' },
  }),
  font_size = 11.0,
  line_height = 1.1,
  -- HiDPI: let Wayland handle scaling, don't set dpi manually
  dpi = 96.0,
}
```

### Font Size Guidelines

| Display | Resolution | Recommended Size | Notes |
|---------|-----------|-----------------|-------|
| 24-inch 1080p | 1920×1080 | 10–12pt | Standard |
| 27-inch 1440p | 2560×1440 | 11–13pt | Slightly larger |
| 4K without scaling | 3840×2160 | 16–20pt | Or use 2x scaling |
| 4K at 2x scale | 3840×2160 | 10–12pt | Compositor handles scaling |
| 13-inch FHD laptop | 1920×1080 | 10–11pt | PPI is high |
| 14-inch 2.8K laptop | 2880×1800 | 12–14pt | Or 1.5x scale + 11pt |

---

## 37.5 Emoji Support

### Installing Emoji Fonts

Full emoji rendering requires a color emoji font. The two most common choices are `noto-fonts-emoji` (Google's Noto Color Emoji) and `ttf-twemoji` (Twitter/X's open-source set):

```bash
# Arch
sudo pacman -S noto-fonts-emoji
paru -S ttf-twemoji

# Debian/Ubuntu
sudo apt install fonts-noto-color-emoji
```

After installation, rebuild fontconfig cache:

```bash
fc-cache -fv
```

### Fontconfig Emoji Fallback

Without explicit configuration, fontconfig may select a monochrome emoji font or fail to find one at all. The recommended approach is to create a dedicated config file:

```xml
<!-- ~/.config/fontconfig/conf.d/75-noto-color-emoji.conf -->
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <alias>
    <family>emoji</family>
    <prefer>
      <family>Noto Color Emoji</family>
    </prefer>
  </alias>

  <!-- Ensure emoji renders in all families by appending as fallback -->
  <match target="pattern">
    <test qual="any" name="family"><string>sans-serif</string></test>
    <edit name="family" mode="append_last">
      <string>Noto Color Emoji</string>
    </edit>
  </match>

  <match target="pattern">
    <test qual="any" name="family"><string>serif</string></test>
    <edit name="family" mode="append_last">
      <string>Noto Color Emoji</string>
    </edit>
  </match>

  <match target="pattern">
    <test qual="any" name="family"><string>monospace</string></test>
    <edit name="family" mode="append_last">
      <string>Noto Color Emoji</string>
    </edit>
  </match>
</fontconfig>
```

### Terminal Emoji Rendering

Color emoji rendering in terminals depends on both terminal support and the font rendering path:

| Terminal | Color Emoji | Notes |
|----------|------------|-------|
| Kitty | Yes (native) | Renders emoji cells via its own rasterizer |
| WezTerm | Yes (native) | Full color emoji support |
| Foot | Yes (via fontconfig) | Since ~1.13, requires color emoji font |
| Alacritty | Partial | Monochrome only; color requires a workaround |
| ghostty | Yes (native) | Full color emoji |

For Alacritty, a common workaround is to set the emoji font explicitly:

```toml
# alacritty.toml — use a symbol map workaround via fontconfig
# No direct emoji override; rely on fontconfig fallback
```

Test emoji rendering in any terminal:

```bash
echo "Standard emoji: 😀 🚀 🎉 🦀"
echo "ZWJ sequence:   👨‍💻 👩‍🔬"
echo "Flags:           🏴‍☠️ 🇩🇪"
```

---

## 37.6 Managing Fonts with fc-query and fc-list

Beyond installation, several fontconfig command-line tools help diagnose and inspect the font system:

```bash
# List all installed fonts with paths
fc-list

# List fonts matching a pattern
fc-list | grep -i "inter"

# Show what font would actually be selected for a given query
fc-match "Inter:style=Regular"
fc-match "monospace:size=11"
fc-match "emoji"

# Inspect all properties of a font file
fc-query /usr/share/fonts/TTF/Inter-Regular.ttf

# Scan a directory and print discovered fonts
fc-scan ~/.local/share/fonts/

# Force full cache rebuild for all font directories
fc-cache -fv

# Verify cache is fresh (no output = up to date)
fc-cache -r
```

To find the exact PostScript/family name that fontconfig uses (important for getting terminal config right):

```bash
fc-list | grep -i "jetbrains" | awk -F: '{print $2}' | sort -u
```

---

## 37.7 Applying Themes with nwg-look

`nwg-look` is a GTK settings editor designed for wlroots-based compositors where GNOME tools like `gnome-tweak-tool` are unavailable. It writes to GTK 3/4 settings files and provides a GUI for icon themes, cursor themes, and fonts.

```bash
# Install
paru -S nwg-look

# Launch (can be added to a Hyprland keybind)
nwg-look
```

Within `nwg-look`:
1. Navigate to the **Icons** tab — select your theme from the dropdown.
2. Navigate to **Cursors** — select theme and size.
3. Navigate to **Fonts** — set widget font, anti-aliasing, and hinting.
4. Click **Apply** — writes `~/.config/gtk-3.0/settings.ini` and `~/.config/gtk-4.0/settings.ini`.

After applying, restart any running GTK applications to pick up the changes. Some apps (Nautilus, Thunar) respond to gsettings signals and update live.

---

## Troubleshooting

### Icons Not Updating After Theme Change

**Symptom**: Changed icon theme via `gsettings` or settings.ini but apps still show old icons.

**Fixes**:
1. Ensure the icon cache is built: `gtk-update-icon-cache -f -t ~/.local/share/icons/ThemeName`
2. Confirm the correct theme name (case-sensitive): `ls ~/.local/share/icons/`
3. Restart the affected application — most GTK apps do not hot-reload icon themes.
4. If using Flatpak apps, they use their own bundled GTK; pass the icon theme in: `flatpak override --user --env=GTK_THEME=Adwaita --filesystem=~/.local/share/icons`

### Wrong Icon Theme in Flatpak Apps

```bash
# Grant Flatpak apps access to user icon themes
flatpak override --user --filesystem=~/.local/share/icons:ro
# Verify
flatpak override --user --show | grep filesystem
```

### Cursor Theme Not Applying to Some Apps

**Symptom**: Cursor shows correctly in Hyprland itself but reverts to default in some windows.

**Fixes**:
1. Verify `XCURSOR_THEME` and `XCURSOR_SIZE` are in the environment: `env | grep XCURSOR`
2. Ensure `~/.local/share/icons/default/index.theme` points to the correct theme (see §37.2).
3. For XWayland apps: verify variables are set before compositor starts (in `~/.config/environment.d/`, not in `.bashrc`).
4. For Electron apps: add `--ozone-platform=wayland` to the launch flags — some Electron apps use X11 backend by default even on Wayland and ignore Wayland cursor settings.

### Cursor Too Small/Large on HiDPI

```bash
# Quick test: what size is actually being used?
echo $XCURSOR_SIZE

# For fractional scale 1.5x, set physical size = logical * scale
# logical 24px * 1.5 = 36px physical
env = XCURSOR_SIZE,36
```

### Font Not Found in Terminal

**Symptom**: Terminal shows fallback font instead of specified Nerd Font.

**Diagnosis**:
```bash
# Check the exact name fontconfig uses
fc-list | grep -i "jetbrains"
# Output might be: /path/to/font: JetBrainsMono Nerd Font:style=Regular
# Use EXACTLY "JetBrainsMono Nerd Font" in terminal config, not "JetBrains Mono NF"
```

**Fix**: Match the family name character-for-character as reported by `fc-list`. Different packages use slightly different names (`JetBrainsMono Nerd Font` vs. `JetBrains Mono Nerd Font`).

### Fontconfig Cache Stale

```bash
# Full rebuild
fc-cache -fv 2>&1 | tail -5

# If problems persist, delete cached files and rebuild
rm -rf ~/.cache/fontconfig
fc-cache -fv
```

### Emoji Showing as Boxes or Monochrome

1. Install `noto-fonts-emoji`: `sudo pacman -S noto-fonts-emoji`
2. Run `fc-cache -fv`
3. Verify: `fc-match emoji` — should show `NotoColorEmoji`
4. If using Alacritty, switch to Kitty or WezTerm for full color emoji support.

### GTK Apps Ignoring settings.ini

Some GTK 4 apps (particularly GNOME-stack applications like Nautilus) ignore `settings.ini` and read exclusively from GSettings dconf. Ensure GSettings is also set:

```bash
gsettings set org.gnome.desktop.interface icon-theme "Papirus-Dark"
gsettings set org.gnome.desktop.interface cursor-theme "Catppuccin-Mocha-Dark-Cursors"
gsettings set org.gnome.desktop.interface cursor-size 24
gsettings set org.gnome.desktop.interface font-name "Inter 10"
gsettings set org.gnome.desktop.interface monospace-font-name "JetBrainsMono Nerd Font 11"
```

Under compositors without a running GNOME settings daemon, `xdg-desktop-portal-gtk` propagates GSettings to Wayland apps. Ensure it is running:

```bash
systemctl --user status xdg-desktop-portal-gtk
# If not running:
systemctl --user enable --now xdg-desktop-portal-gtk
```

*See Ch 53 for session startup and environment variable propagation order, and Ch 38 for per-application theme overrides in Hyprland window rules.*

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
