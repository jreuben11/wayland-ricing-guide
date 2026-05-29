# Chapter 36 — Qt and KDE Theming: Kvantum, qt5ct/qt6ct

## Overview
Qt apps need separate theming from GTK. The Kvantum theme engine + qt5ct/qt6ct
is the standard non-KDE approach for Qt theming on Wayland.

## Sections

### 36.1 Qt Theme Mechanisms
- Qt style: Fusion, Windows, Breeze, GTK2 (deprecated)
- Platform theme: provides defaults (icons, colors, dialogs)
- `QT_STYLE_OVERRIDE` environment variable
- KDE's Breeze: default in Plasma, available standalone

### 36.2 qt5ct and qt6ct
- Purpose: configure Qt5/Qt6 apps outside of KDE
- Installation: `qt5ct`, `qt6ct` packages
- Required env: `QT_QPA_PLATFORMTHEME=qt5ct` (or qt6ct)
- GUI: style, color palette, fonts, icons
- Config location: `~/.config/qt5ct/qt5ct.conf`

### 36.3 Kvantum — SVG-Based Qt Theme Engine
- SVG-defined widget shapes: fully customizable
- Install: `kvantum` package + theme SVGs
- Manager: `kvantummanager` GUI for theme selection
- `QT_STYLE_OVERRIDE=kvantum` to activate
- Popular Kvantum themes:
  - Catppuccin-Kvantum
  - Gruvbox-Kvantum
  - Nordic-Kvantum
  - Orchid
- Writing a custom Kvantum theme: SVG + INI config

### 36.4 Environment Variables for Qt on Wayland
```bash
# ~/.config/hypr/env.conf or shell profile
env = QT_QPA_PLATFORM,wayland
env = QT_QPA_PLATFORMTHEME,qt5ct
env = QT_STYLE_OVERRIDE,kvantum
env = QT_WAYLAND_DISABLE_WINDOWDECORATION,1
env = QT_AUTO_SCREEN_SCALE_FACTOR,1
```

### 36.5 Breeze for Non-KDE Setups
- `breeze`, `breeze-gtk` packages
- Breeze Dark/Light color schemes
- Breeze icon theme
- Using Breeze without full Plasma

### 36.6 Home Manager Qt Configuration
```nix
qt = {
    enable = true;
    platformTheme.name = "qtct";
    style = {
        name = "kvantum";
        package = pkgs.catppuccin-kvantum;
    };
};
```

### 36.7 Fonts for Qt and GTK
- System font configuration: `~/.config/fontconfig/fonts.conf`
- `fc-cache -fv`: rebuild font cache
- Popular fonts for ricing:
  - JetBrains Mono (code)
  - Inter, Geist (UI)
  - Noto Sans (Unicode coverage)
  - Nerd Fonts: icon glyphs for terminals/bars
- DPI and hinting: `hintstyle`, `antialias`, `rgba` in fontconfig

### 36.8 Consistent Look Across GTK and Qt
- Use the same color palette for both
- Stylix (Ch 40) automates this
- Manual approach: match colors in gtk.css and Kvantum SVG
- Icon theme should support both GTK and Qt apps
