# Chapter 44 — Accessibility on Wayland

## Overview
Wayland accessibility is catching up to X11. This chapter covers screen readers,
magnification, on-screen keyboards, and the AT-SPI2 stack.

## Sections

### 44.1 Accessibility Architecture
- AT-SPI2 (Assistive Technology Service Provider Interface): the D-Bus accessibility stack
- Orca: screen reader that uses AT-SPI2
- `at-spi2-core` package: the bridge
- GTK4 and Qt6: good AT-SPI2 support
- Wayland complicates: screen readers need compositor cooperation

### 44.2 Orca Screen Reader
- Status on Wayland: functional for GTK/Qt apps, limited for custom UI
- `orca &` to start
- Works best with GNOME Shell (full Mutter integration)
- On Hyprland/Sway: partial — apps work, but global speech limited
- Self-voicing apps (Firefox, LibreOffice) work well

### 44.3 Screen Magnification
- No universal magnifier on Wayland (unlike Xzoom / GNOME Magnifier on X11)
- KDE Plasma: `kwin-wayland-accessibility` magnifier
- GNOME: `gnome-shell` has a built-in magnifier
- Hyprland workaround: custom magnifier with `ScreencopyView` in Quickshell
- `wayland-accessibility-tools`: community efforts

### 44.4 On-Screen Keyboard
- `wvkbd`: Wayland virtual keyboard using layer-shell
  - Touch-friendly, scriptable
  - `wvkbd-mobintl &`
- `squeekboard`: GNOME's on-screen keyboard
- `onboard`: GTK on-screen keyboard (XWayland compatibility mode)
- Input method integration: `zwp-virtual-keyboard-manager-v1` protocol

### 44.5 High Contrast and Visual Accessibility
- GTK high contrast themes: `HighContrast`, `HighContrastInverse`
- `gsettings set org.gnome.desktop.a11y.interface high-contrast true`
- Font size scaling: `gsettings set org.gnome.desktop.interface text-scaling-factor 1.5`
- Cursor size: `XCURSOR_SIZE=48`

### 44.6 Color Blindness Accommodations
- Color filter shaders in compositor (Hyprland CTM protocol)
- Daltonize: red-green colorblind correction
- `wl-gammarelay`: color temperature adjustment accessible to scripts

### 44.7 Focus and Navigation
- `sway accessibility` features: focus follows cursor options
- Large window borders for visibility
- Focus ring theming in GTK

### 44.8 Status and Roadmap (2025/2026)
- GNOME has best accessibility on Wayland (mature)
- KDE Plasma: improving rapidly
- wlroots-based compositors: basic AT-SPI2 works, magnifier missing
- `ext-session-lock-v1` accessibility: locked screens now accessible
- Community projects: wayland-a11y initiatives
