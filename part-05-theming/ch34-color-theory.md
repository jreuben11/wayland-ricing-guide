# Chapter 34 — Color Theory for Desktop Ricing

## Overview
A great rice starts with a coherent color story. This chapter covers color systems,
popular palettes, and how to evaluate whether a rice looks "good."

## Sections

### 34.1 Color Systems Used in Ricing
- **base16**: 16-color palette scheme (base00–base0F) — background to foreground
- **base24**: extended base16 with more accent shades
- **Material You / Material Design 3**: Google's dynamic color system
- **Catppuccin**: 4 flavors (Latte, Frappé, Macchiato, Mocha) — most popular 2024-2026
- **Nord**: arctic-inspired cool blues
- **Gruvbox**: warm retro palette (dark/light variants)
- **Tokyo Night**: cool purple-blue, extremely popular

### 34.2 Popular Palette Collections (2025)
| Palette | Character | Base tone | Best for |
|---------|-----------|-----------|----------|
| Catppuccin Mocha | Soft, pastel | Dark | General purpose |
| Gruvbox Dark | Warm, retro | Dark | Coding |
| Nord | Cool, minimal | Dark | Productivity |
| Tokyo Night | Purple-toned | Dark | Modern/anime |
| Everforest | Earth tones | Dark/Light | Nature feel |
| Rosé Pine | Warm muted | Dark | Elegant |
| One Dark | High contrast | Dark | Editors |
| Solarized | Precision crafted | Both | Classic |

### 34.3 Color Relationships
- Complementary: opposite hues (blue + orange)
- Analogous: adjacent hues (blue + teal + green)
- Triadic: three equidistant hues
- Accent colors: 1-2 vivid colors against muted backgrounds
- The "60-30-10" rule: 60% background, 30% secondary, 10% accent

### 34.4 Contrast and Accessibility
- WCAG AA: 4.5:1 contrast ratio for normal text
- WCAG AAA: 7:1 for enhanced readability
- Tools: `contrast-ratio.com`, `coolors.co` contrast checker
- Why low-contrast rices look beautiful in screenshots but hurt in daily use

### 34.5 Automatic Color Extraction
- **pywal**: extract palette from wallpaper (k-means clustering)
- **matugen**: Material You palette from wallpaper
- **wallust**: pywal alternative with more backends
- **wpgtk**: GUI front-end for pywal

### 34.6 Where Colors Are Applied
- Terminal emulator (the most visible element)
- Shell prompt (starship, oh-my-posh)
- Editor (neovim, vscode, emacs)
- Bar (Waybar/Quickshell)
- GTK theme (app windows)
- Qt theme (Qt app windows)
- Firefox/Chromium theme
- Cursor and icon theme (accent color)
- Wallpaper (source of truth in dynamic theming)

### 34.7 Building a Cohesive Rice
- Start with the wallpaper
- Extract or match a palette
- Apply consistently: don't mix base16 in one place and Material in another
- Test in actual usage, not just screenshots
- Dark room vs. daylight: check both

### 34.8 Resources
- https://github.com/catppuccin/catppuccin — port list
- https://github.com/chriskempson/base16 — base16 schemes
- https://lospec.com/palette-list — pixel art palettes
- https://coolors.co — palette generator
- tinted-theming.github.io — base16 builder ecosystem
