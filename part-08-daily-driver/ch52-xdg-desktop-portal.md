# Chapter 52 — xdg-desktop-portal: Screen Sharing, File Chooser, Settings

## Overview
xdg-desktop-portal (XDP) is the D-Bus layer that sandboxed and Wayland apps use
to request OS services: file picking, screenshots, screen sharing, dark mode,
print dialogs. Getting it configured correctly is non-negotiable for a functional
Wayland desktop.

## Sections

### 52.1 What xdg-desktop-portal Is
- A D-Bus service at `org.freedesktop.portal.*`
- Sandboxed apps (Flatpak, snap, browsers) must go through portals — they cannot
  directly access files, the camera, or the screen
- Non-sandboxed apps also use portals for screen sharing, file chooser
- The portal broker (`xdg-desktop-portal`) delegates to a backend implementation

### 52.2 The Backend Architecture
```
App (e.g. Firefox) 
  → D-Bus → xdg-desktop-portal (broker)
              → xdg-desktop-portal-hyprland  (or -wlr, -gnome, -kde)
                  → Wayland compositor (screencopy, file chooser GTK dialog)
```

**Available backends:**
| Backend | Compositor | Notes |
|---------|-----------|-------|
| `xdg-desktop-portal-hyprland` | Hyprland | Recommended for Hyprland |
| `xdg-desktop-portal-wlr` | wlroots compositors | Sway, river, labwc |
| `xdg-desktop-portal-gnome` | GNOME Mutter | Full portal coverage |
| `xdg-desktop-portal-kde` | KWin | Full portal coverage |
| `xdg-desktop-portal-gtk` | Any | Fallback for file chooser, settings |

### 52.3 Installation

**Hyprland:**
```bash
# Arch
sudo pacman -S xdg-desktop-portal-hyprland xdg-desktop-portal-gtk

# NixOS
xdg.portal = {
    enable = true;
    extraPortals = [ pkgs.xdg-desktop-portal-hyprland pkgs.xdg-desktop-portal-gtk ];
    config.hyprland.default = [ "hyprland" "gtk" ];
};
```

**Sway:**
```bash
sudo pacman -S xdg-desktop-portal-wlr xdg-desktop-portal-gtk
```

### 52.4 Portal Configuration File
`~/.config/xdg-desktop-portal/portals.conf` (or `/usr/share/xdg-desktop-portal/portals.conf`):
```ini
[preferred]
default=hyprland;gtk
org.freedesktop.impl.portal.FileChooser=gtk
org.freedesktop.impl.portal.Settings=gtk
org.freedesktop.impl.portal.ScreenCast=hyprland
org.freedesktop.impl.portal.Screenshot=hyprland
```

The `XDG_CURRENT_DESKTOP` environment variable drives automatic backend selection.
Always set it to your compositor name:
```bash
export XDG_CURRENT_DESKTOP=Hyprland  # or sway, etc.
```

### 52.5 Portal Interfaces Reference

| Interface | What it does | Who uses it |
|-----------|-------------|-------------|
| `FileChooser` | Open/save file dialogs | Every app with file pickers |
| `ScreenCast` | Screen recording and sharing | OBS, browsers (WebRTC), Teams |
| `Screenshot` | Take screenshots | Flatpak screenshot apps |
| `Camera` | Webcam access | Video call apps (sandboxed) |
| `Settings` | Dark mode, accent color, fonts | GTK4 apps, browsers |
| `OpenURI` | Open URLs/files with default app | Everything |
| `Print` | Print dialogs | GTK apps |
| `Inhibit` | Prevent idle/sleep | Video players |
| `Notification` | Sandbox notification proxy | Flatpak apps |
| `Account` | User info | Some apps |
| `AppChooser` | "Open with" dialogs | File managers |

### 52.6 The Settings Portal and Dark Mode
The Settings portal is how GTK4/libadwaita apps detect your dark/light preference:
```bash
# Check current setting
gdbus call --session \
    --dest org.freedesktop.portal.Desktop \
    --object-path /org/freedesktop/portal/desktop \
    --method org.freedesktop.portal.Settings.Read \
    org.freedesktop.appearance color-scheme

# 0 = no preference, 1 = dark, 2 = light
```

Setting it on non-GNOME:
```bash
gsettings set org.gnome.desktop.interface color-scheme prefer-dark
```
Or in the portal config: backends like `xdg-desktop-portal-gtk` read `gsettings`.

### 52.7 Screen Sharing Setup (WebRTC)
For browser video calls and OBS to work:
1. Install `xdg-desktop-portal-hyprland` (or `-wlr`)
2. Set `XDG_CURRENT_DESKTOP=Hyprland`
3. Ensure PipeWire is running
4. In browser: `about:config` → `media.webrtc.hw.h264.enabled = true`
5. Firefox: `MOZ_ENABLE_WAYLAND=1` must be set

**Testing screen share:**
```bash
# Should show a window selection dialog
flatpak run org.gnome.Cheese  # or any camera/screen app
```

### 52.8 Debugging Portal Issues

**Check portal service status:**
```bash
systemctl --user status xdg-desktop-portal
systemctl --user status xdg-desktop-portal-hyprland
```

**Restart portals:**
```bash
systemctl --user restart xdg-desktop-portal
systemctl --user restart xdg-desktop-portal-hyprland
```

**Debug logging:**
```bash
G_MESSAGES_DEBUG=all /usr/lib/xdg-desktop-portal --replace 2>&1 | grep -i portal
```

**Common failures:**
| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Screen share black/empty | Wrong backend | Check `XDG_CURRENT_DESKTOP` |
| File chooser doesn't open | Missing `-gtk` backend | Install `xdg-desktop-portal-gtk` |
| App doesn't respect dark mode | Settings portal misconfigured | Check `portals.conf` |
| Screen share works once then fails | Portal crashed | `systemctl --user restart xdg-desktop-portal-hyprland` |
| Firefox WebRTC broken | `MOZ_ENABLE_WAYLAND` not set | Set in env config |

### 52.9 Flatpak and Portal Permissions
```bash
# List app's portal permissions
flatpak permission-list

# Grant screen capture to a specific app
flatpak override --user --filesystem=xdg-run/portal:ro com.example.App

# Check what a Flatpak app is asking for
flatpak info --show-permissions com.obsproject.Studio
```

### 52.10 Writing a Custom Portal Implementation
- Implement `org.freedesktop.impl.portal.*` interfaces on D-Bus
- Register in `/usr/share/xdg-desktop-portal/portals/myportal.portal`
- Use cases: custom file pickers, proprietary screen capture
