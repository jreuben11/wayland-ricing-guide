# Chapter 118 — Flatpak on Wayland

## Contents

- [Overview](#overview)
- [118.1 Socket Permissions](#1181-socket-permissions)
- [118.2 Portal Setup](#1182-portal-setup)
- [118.3 Forcing Wayland Backend in Specific Apps](#1183-forcing-wayland-backend-in-specific-apps)
  - [Electron Apps (Discord, Slack, VS Code, Obsidian)](#electron-apps-discord-slack-vs-code-obsidian)
  - [GTK Apps](#gtk-apps)
  - [Qt Apps](#qt-apps)
  - [Firefox](#firefox)
- [118.4 Flatseal: GUI Permission Manager](#1184-flatseal-gui-permission-manager)
- [118.5 GTK Theme Access](#1185-gtk-theme-access)
  - [Option A: Grant filesystem access to themes](#option-a-grant-filesystem-access-to-themes)
  - [Option B: Install themes as Flatpak extensions](#option-b-install-themes-as-flatpak-extensions)
  - [Option C: Use `~/.config/gtk-3.0/` (already accessible)](#option-c-use-configgtk-30-already-accessible)
- [118.6 Wayland App Compatibility Table](#1186-wayland-app-compatibility-table)
- [118.7 Troubleshooting](#1187-troubleshooting)
  - [App appears on XWayland despite override](#app-appears-on-xwayland-despite-override)
  - [File picker opens an X11 dialog](#file-picker-opens-an-x11-dialog)
  - [App crashes on startup with Wayland](#app-crashes-on-startup-with-wayland)
  - [Screen sharing not working from Flatpak](#screen-sharing-not-working-from-flatpak)

---


## Overview

Flatpak packages most major Linux applications — Firefox, Brave, Obsidian, Spotify, Discord, LibreOffice, GIMP, Inkscape, Steam, VLC — in sandboxed containers that run on any distribution. On Wayland, Flatpak apps work correctly when configured properly, but many ship with X11 as default or require explicit portal setup. Misconfigured Flatpak apps either silently fall back to XWayland, fail to render, or show theming inconsistencies because their sandbox cannot reach your GTK theme files.

This chapter covers the three configuration layers for Flatpak on Wayland: the socket permissions that grant Wayland access, the portal backend that bridges sandbox to compositor, and the per-app environment overrides that force Wayland rendering in stubborn apps.

**Cross-references:** Ch 52 — xdg-desktop-portal overview and screen sharing. Ch 35/36 — GTK and Qt theming (Flatpak apps need theme access). Ch 85 — containerization and sandboxing fundamentals.

---

## 118.1 Socket Permissions

Flatpak apps access Wayland via a Unix socket. The relevant permission is `--socket=wayland`, which bind-mounts the Wayland socket from `$XDG_RUNTIME_DIR` into the sandbox.

```bash
# Check if an app has Wayland socket access
flatpak info --show-permissions org.mozilla.firefox | grep wayland

# Grant Wayland socket access to a specific app
flatpak override --user --socket=wayland org.mozilla.firefox

# Also remove X11 fallback (optional — may break some apps)
flatpak override --user --nosocket=x11 --nosocket=fallback-x11 org.mozilla.firefox

# Check current overrides
flatpak override --user --show org.mozilla.firefox

# Reset all overrides
flatpak override --user --reset org.mozilla.firefox
```

Common socket configuration for a pure-Wayland setup:

```bash
# Native Wayland — no X11 fallback
flatpak override --user --socket=wayland --nosocket=x11 APP_ID

# Wayland with X11 fallback (safer for unstable apps)
flatpak override --user --socket=wayland --socket=fallback-x11 APP_ID
```

---

## 118.2 Portal Setup

xdg-desktop-portal translates sandbox requests (file picker, screenshot, screen share, settings, remote desktop) into compositor-native calls. Each compositor has a portal backend:

```bash
# Hyprland — install the Hyprland portal
sudo pacman -S xdg-desktop-portal-hyprland

# Sway / wlroots — use the wlr portal
sudo pacman -S xdg-desktop-portal-wlr

# GNOME
sudo pacman -S xdg-desktop-portal-gnome

# KDE
sudo pacman -S xdg-desktop-portal-kde

# GTK-based fallback (for any compositor)
sudo pacman -S xdg-desktop-portal-gtk
```

The portal selection is configured in `/usr/share/xdg-desktop-portal/portals/`:

```ini
# /usr/share/xdg-desktop-portal/portals/hyprland.portal
[portal]
DBusName=org.freedesktop.impl.portal.desktop.hyprland
Interfaces=org.freedesktop.impl.portal.FileChooser;org.freedesktop.impl.portal.Screenshot;...
UseIn=Hyprland
```

For compositors not matching any portal's `UseIn` list, set `XDG_CURRENT_DESKTOP` explicitly:

```bash
# Hyprland (exec-once or environment.d)
export XDG_CURRENT_DESKTOP=Hyprland

# Sway
export XDG_CURRENT_DESKTOP=sway
```

Verify portal is active:
```bash
busctl --user status org.freedesktop.portal.Desktop
systemctl --user status xdg-desktop-portal xdg-desktop-portal-hyprland
```

---

## 118.3 Forcing Wayland Backend in Specific Apps

### Electron Apps (Discord, Slack, VS Code, Obsidian)

```bash
# Global Electron Wayland flag
flatpak override --user \
    --env=ELECTRON_OZONE_PLATFORM_HINT=auto \
    org.example.ElectronApp

# Or force Wayland explicitly (disables X11 fallback)
flatpak override --user \
    --env=ELECTRON_OZONE_PLATFORM_HINT=wayland \
    org.example.ElectronApp
```

For specific apps:
```bash
# Discord
flatpak override --user --socket=wayland \
    --env=ELECTRON_OZONE_PLATFORM_HINT=auto com.discordapp.Discord

# VS Code
flatpak override --user --socket=wayland \
    --env=ELECTRON_OZONE_PLATFORM_HINT=auto com.visualstudio.code

# Obsidian
flatpak override --user --socket=wayland \
    --env=ELECTRON_OZONE_PLATFORM_HINT=auto md.obsidian.Obsidian
```

### GTK Apps

```bash
# Force GTK Wayland backend
flatpak override --user \
    --env=GDK_BACKEND=wayland \
    org.gimp.GIMP

# GTK with X11 fallback
flatpak override --user \
    --env=GDK_BACKEND=wayland,x11 \
    org.inkscape.Inkscape
```

### Qt Apps

```bash
# Qt Wayland platform plugin
flatpak override --user \
    --env=QT_QPA_PLATFORM=wayland \
    --socket=wayland \
    org.kde.dolphin

# Qt with X11 fallback
flatpak override --user \
    --env=QT_QPA_PLATFORM=wayland\;xcb \
    org.kde.kdenlive
```

### Firefox

```bash
flatpak override --user \
    --socket=wayland \
    --nosocket=x11 \
    --env=MOZ_ENABLE_WAYLAND=1 \
    org.mozilla.firefox
```

Verify Firefox is running on Wayland (check title bar: pure Wayland shows client-side decorations; X11 shows server-side decorations from XWayland):
```bash
# In Firefox address bar: about:support
# Look for "Window Protocol: wayland"
```

---

## 118.4 Flatseal: GUI Permission Manager

Flatseal is a GTK application that provides a GUI for all Flatpak permissions, including socket access and environment variables. It is the recommended tool for non-scripted per-app configuration:

```bash
# Install
flatpak install flathub com.github.tchx84.Flatseal
# or native:
sudo pacman -S flatpak-flatseal   # AUR
```

In Flatseal, per-app settings include:
- Socket toggles (Wayland, X11, PulseAudio, D-Bus, SSH auth)
- Filesystem access (home, specific paths)
- Device access (GPU, DRI, input)
- Environment variables (arbitrary key=value pairs)

For the Wayland configuration covered in §118.3, Flatseal's "Environment" section under each app provides the same control without command-line syntax.

---

## 118.5 GTK Theme Access

Sandboxed Flatpak apps cannot read themes from `~/.local/share/themes/` by default. Options:

### Option A: Grant filesystem access to themes

```bash
flatpak override --user \
    --filesystem=~/.local/share/themes:ro \
    --filesystem=~/.local/share/icons:ro \
    APP_ID
```

### Option B: Install themes as Flatpak extensions

For widely-used themes, Flatpak runtime extensions exist:
```bash
# Adwaita (default — usually pre-installed)
flatpak install org.gtk.Gtk3theme.Adwaita

# Catppuccin GTK theme (if available)
flatpak install org.gtk.Gtk3theme.Catppuccin-Mocha-Standard-Blue-Dark

# List available GTK themes as extensions
flatpak search Gtk3theme | head -20
```

### Option C: Use `~/.config/gtk-3.0/` (already accessible)

Flatpak apps have read access to `~/.config/gtk-3.0/gtk.css` by default. Place theme overrides there:
```css
/* ~/.config/gtk-3.0/gtk.css — global GTK3 override */
@import url("/home/username/.local/share/themes/Tokyonight-Dark-BL/gtk-3.0/gtk.css");
```

---

## 118.6 Wayland App Compatibility Table

| App | Flatpak ID | Default | Fix needed |
|---|---|---|---|
| Firefox | org.mozilla.firefox | X11 | `MOZ_ENABLE_WAYLAND=1`, `--socket=wayland` |
| Brave | com.brave.Browser | X11 | `ELECTRON_OZONE_PLATFORM_HINT=auto` |
| VS Code | com.visualstudio.code | X11 | `ELECTRON_OZONE_PLATFORM_HINT=auto` |
| Discord | com.discordapp.Discord | X11 | `ELECTRON_OZONE_PLATFORM_HINT=auto` |
| Obsidian | md.obsidian.Obsidian | X11 | `ELECTRON_OZONE_PLATFORM_HINT=auto` |
| GIMP | org.gimp.GIMP | GTK (auto) | `GDK_BACKEND=wayland` |
| Inkscape | org.inkscape.Inkscape | auto | `GDK_BACKEND=wayland,x11` |
| VLC | org.videolan.VLC | auto | Usually works; set `--socket=wayland` |
| Spotify | com.spotify.Client | Electron/X11 | `ELECTRON_OZONE_PLATFORM_HINT=auto` |
| Kdenlive | org.kde.kdenlive | Qt/auto | `QT_QPA_PLATFORM=wayland` |
| OBS | com.obsproject.Studio | Qt/auto | `QT_QPA_PLATFORM=wayland` |
| Steam | com.valvesoftware.Steam | X11 | Partial; use native package for best results |

---

## 118.7 Troubleshooting

### App appears on XWayland despite override

Check `WAYLAND_DISPLAY` is set inside the sandbox:
```bash
flatpak run --env=WAYLAND_DEBUG=1 APP_ID 2>&1 | head -20
```

If `WAYLAND_DISPLAY` is empty, the Wayland socket wasn't passed. Verify `--socket=wayland` is in the override:
```bash
flatpak info --show-permissions APP_ID | grep socket
```

### File picker opens an X11 dialog

The portal's file chooser isn't configured. Check:
```bash
busctl --user introspect org.freedesktop.portal.Desktop \
    /org/freedesktop/portal/desktop \
    org.freedesktop.impl.portal.FileChooser
```

### App crashes on startup with Wayland

Force X11 fallback temporarily to verify it's not a portal issue:
```bash
flatpak run --env=GDK_BACKEND=x11 APP_ID
# or
flatpak run --env=ELECTRON_OZONE_PLATFORM_HINT=x11 APP_ID
```

### Screen sharing not working from Flatpak

Screen sharing requires the portal's ScreenCast interface. Install the compositor-specific portal and ensure `pipewire-session-manager` (WirePlumber) is running:
```bash
systemctl --user status wireplumber
systemctl --user status xdg-desktop-portal
```
