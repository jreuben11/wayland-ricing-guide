# Chapter 12 — labwc: The OpenBox Successor

## Overview
labwc is a stacking Wayland compositor inspired by OpenBox, designed for traditional
floating desktop use. Pairs well with a panel and file manager to replicate the
classic LXDE/LXQT desktop feel on Wayland.

## Sections

### 12.1 Design Goals
- OpenBox-compatible configuration (Openbox XML format subset)
- Minimal and lightweight
- Compositor only: pairs with external panels, docks, file managers

### 12.2 Installation and Setup
- Package availability
- Starting labwc: session configuration
- `autostart` file and environment setup

### 12.3 Configuration
- `~/.config/labwc/rc.xml`: window management rules, keybindings
- `~/.config/labwc/menu.xml`: right-click desktop menu
- `~/.config/labwc/autostart`: startup programs
- `~/.config/labwc/environment`: environment variables

### 12.4 Theming labwc
- Openbox-compatible GTK themes
- Decorations configuration
- Font settings

### 12.5 Building a Complete Desktop with labwc
- Pairing with `sfwbar` or `waybar` for a panel
- `pcmanfm-qt` for file management and desktop icons
- `lxqt-policykit` for privilege escalation
- Full LXQT-on-Wayland setup guide

### 12.6 labwc vs. Other Stacking Compositors
- vs. KWin: feature richness vs. simplicity
- vs. GNOME Mutter: extensibility vs. integration
- vs. Wayfire in stacking mode

### 12.7 labwc in 2025/2026
- Feature completeness status
- LXQt project's official adoption
- Community and distribution support
