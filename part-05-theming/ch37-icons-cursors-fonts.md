# Chapter 37 — Icon Packs, Cursors, and Fonts

## Overview
Icons, cursors, and fonts are the finishing touches that unify a rice.
This chapter covers selection, installation, and configuration.

## Sections

### 37.1 Icon Themes
#### How Icon Themes Work
- `~/.local/share/icons/ThemeName/` hierarchy
- Icon name spec: `applications-graphics`, `folder`, `go-up`, etc.
- Fallback chain: theme → parent theme → hicolor
- SVG vs. PNG icons: scalability tradeoffs
- Dark/light icon variants: `~/.local/share/icons/ThemeName-Dark/`

#### Popular Icon Themes
| Theme | Style | Notes |
|-------|-------|-------|
| Papirus | Flat, colorful | Massive coverage, color variants |
| Papirus-Dark | Dark Papirus | Most used in dark rices |
| Tela | Minimal flat | Clean look |
| Fluent | Windows-inspired | |
| WhiteSur | macOS Big Sur | |
| Numix Circle | Circle icons | Classic |
| candy-icons | Gradient, vivid | Eye-candy |
| Gruvbox Plus | Gruvbox palette | |
| Catppuccin (papirus-folders) | Catppuccin accent folders | |

#### Setting Icon Theme
```bash
gsettings set org.gnome.desktop.interface icon-theme "Papirus-Dark"
# or in gtk settings.ini:
gtk-icon-theme-name=Papirus-Dark
```

### 37.2 Cursor Themes
#### Cursor Theme Structure
- `~/.local/share/icons/CursorTheme/cursors/` + `cursor.theme`
- Size: typically 24, 32, 48
- `XCURSOR_THEME` and `XCURSOR_SIZE` environment variables

#### Popular Cursor Themes
| Theme | Style |
|-------|-------|
| Catppuccin-Mocha-Dark | Catppuccin-styled |
| Nordzy-cursors | Nord palette |
| Bibata-Modern-Classic | Clean, material |
| Vimix-cursors | Minimal |
| Phinger-cursors | Cute/kawaii |
| macOS-BigSur | macOS replica |

#### Setting Cursors on Wayland
```bash
# In hyprland.conf:
env = XCURSOR_THEME,Catppuccin-Mocha-Dark-Cursors
env = XCURSOR_SIZE,24

# In GTK settings.ini:
gtk-cursor-theme-name=Catppuccin-Mocha-Dark-Cursors
gtk-cursor-theme-size=24
```

#### XWayland cursor size mismatch fix
- `XCURSOR_SIZE` must be set for XWayland apps
- Hyprland `cursor { no_hardware_cursors = true }` for NVIDIA

### 37.3 Font Selection for Ricing
#### Categories
- **UI Font**: clean, readable at small sizes (Inter, Geist, IBM Plex Sans)
- **Monospace/Code Font**: for terminals and editors
- **Display Font**: stylized, for clocks and titles
- **Icon Font**: Nerd Fonts glyph-augmented monospace fonts

#### Nerd Fonts
- Add thousands of icon glyphs to any font
- Required for icon-based prompts (oh-my-posh, starship)
- Required for bars using `  ` icon syntax
- Popular base fonts: JetBrainsMono Nerd Font, FiraCode Nerd Font, CaskaydiaCove
- Installation: download from nerdfonts.com or `nerd-fonts` AUR package

#### Font Configuration
```xml
<!-- ~/.config/fontconfig/fonts.conf -->
<match target="font">
    <edit name="antialias" mode="assign"><bool>true</bool></edit>
    <edit name="hinting" mode="assign"><bool>true</bool></edit>
    <edit name="hintstyle" mode="assign"><const>hintslight</const></edit>
    <edit name="rgba" mode="assign"><const>rgb</const></edit>
    <edit name="lcdfilter" mode="assign"><const>lcddefault</const></edit>
</match>
```

### 37.4 Terminal Font Rendering
- Kitty: `font_family JetBrainsMono Nerd Font`
- Alacritty: `family: "JetBrainsMono Nerd Font"`
- Foot: `font=JetBrainsMono Nerd Font:size=11`
- Font size recommendations: 10–13pt for 1080p, 12–16pt for HiDPI

### 37.5 Emoji Support
- `noto-fonts-emoji` or `twemoji` for emoji rendering
- Fontconfig emoji fallback configuration
- Color emoji in terminals: depends on terminal support
