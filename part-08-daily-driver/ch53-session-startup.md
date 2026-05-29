# Chapter 53 — Session Startup and Environment: exec-once, dbus, systemd user

## Overview
The most common category of Wayland breakage is startup order: apps launched
before their dependencies, D-Bus services not yet ready, environment variables
missing. This chapter explains the correct startup sequence.

## Sections

### 53.1 The Startup Problem
On X11, `.xinitrc` ran sequentially and most things just worked. Wayland requires:
- D-Bus user session active before most services
- Environment exported to D-Bus and systemd before launching apps
- PipeWire/WirePlumber running before audio consumers
- xdg-desktop-portal after the compositor is ready

Getting this wrong means: silent failures, no audio, broken screen sharing,
missing system tray items, race conditions on login.

### 53.2 The Three Startup Layers

```
Layer 1: systemd user session (pre-login, managed by systemd)
   ↓
Layer 2: Compositor (Hyprland/Sway/etc) — sets env, starts via Layer 1 or DM
   ↓
Layer 3: exec-once / exec (your apps — started after compositor is running)
```

### 53.3 systemd User Session
- Starts automatically on login via the display manager or `systemd --user`
- Manages: D-Bus session bus, `XDG_RUNTIME_DIR`, user services
- Check it's running: `systemctl --user status`
- Key services started here: `pipewire`, `wireplumber`, `polkit-gnome-authentication-agent-1`

**Hyprland as a systemd service** (recommended):
```ini
# ~/.config/systemd/user/hyprland-session.target
[Unit]
Description=Hyprland compositor session
BindsTo=graphical-session.target
Wants=graphical-session-pre.target
After=graphical-session-pre.target
```

### 53.4 Environment Variable Propagation

The critical step that most rices get wrong: environment variables set in the
compositor config are NOT automatically visible to systemd user services or D-Bus.

**Hyprland — the correct way:**
```conf
# hyprland.conf
env = WAYLAND_DISPLAY,wayland-1
env = XDG_SESSION_TYPE,wayland
env = XDG_CURRENT_DESKTOP,Hyprland

# After setting envs, propagate them
exec-once = dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP XDG_SESSION_TYPE
exec-once = systemctl --user import-environment WAYLAND_DISPLAY XDG_CURRENT_DESKTOP
```

**Sway — equivalent:**
```conf
exec systemctl --user import-environment DISPLAY WAYLAND_DISPLAY SWAYSOCK
exec hash dbus-update-activation-environment 2>/dev/null && \
     dbus-update-activation-environment --systemd DISPLAY WAYLAND_DISPLAY SWAYSOCK
```

**Why this matters:** Without these lines, xdg-desktop-portal and other D-Bus
services start without knowing the Wayland socket, and screen sharing/portals fail.

### 53.5 Hyprland exec-once Reference

```conf
# ~/.config/hypr/hyprland.conf — startup section

# 1. Environment propagation (FIRST — before anything else)
exec-once = dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP

# 2. Authentication agent (needed for sudo GUI prompts)
exec-once = /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1

# 3. Audio (may already be a systemd service)
exec-once = pipewire
exec-once = pipewire-pulse
exec-once = wireplumber

# 4. XDG portal (after compositor is ready)
exec-once = sleep 1 && /usr/lib/xdg-desktop-portal-hyprland
exec-once = sleep 2 && /usr/lib/xdg-desktop-portal --replace

# 5. Shell / bar / widgets
exec-once = quickshell
exec-once = waybar  # if not using Quickshell

# 6. Background services
exec-once = hypridle
exec-once = wl-paste --type text --watch cliphist store
exec-once = wl-paste --type image --watch cliphist store
exec-once = /usr/lib/geoclue-2.0/demos/agent  # geolocation (for night light)

# 7. Wallpaper
exec-once = swww-daemon && swww img ~/wallpapers/default.jpg

# 8. Apps to restore
exec-once = [workspace 1 silent] firefox
exec-once = [workspace 2 silent] kitty
```

### 53.6 Sway exec vs exec-once
- Sway uses `exec` (runs once at startup) and `exec_always` (runs on reload too)
- No built-in `exec-once` equivalent — scripts handle it:
```conf
exec dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP SWAYSOCK
exec_always pkill kanshi; exec kanshi    # reload on sway config reload
```

### 53.7 Startup Order Best Practices
1. **Environment first** — `dbus-update-activation-environment` before anything
2. **Auth agent second** — polkit must be up before any privileged operations
3. **Audio third** — PipeWire/WirePlumber if not systemd services
4. **Portal fourth** — slight delay after compositor is fully ready (`sleep 1`)
5. **Shell/bar fifth** — after portals (bars may query portal for tray icons)
6. **Background services** — clipboard, idle daemon, geolocation
7. **Wallpaper** — after render is ready
8. **Apps last** — restore previous session apps

### 53.8 Using systemd User Services Instead of exec-once

For reliability, move services out of exec-once and into systemd:
```ini
# ~/.config/systemd/user/hyprpaper.service
[Unit]
Description=Hyprland wallpaper daemon
PartOf=graphical-session.target

[Service]
ExecStart=/usr/bin/hyprpaper
Restart=on-failure

[Install]
WantedBy=graphical-session.target
```
```bash
systemctl --user enable --now hyprpaper.service
```

This gives you: proper dependency ordering, restart-on-crash, `journalctl` logs.

### 53.9 The ~/.profile / ~/.zprofile Layer
For non-systemd environments or TTY autologin:
```bash
# ~/.zprofile (zsh) or ~/.bash_profile (bash)
if [ -z "$WAYLAND_DISPLAY" ] && [ "$XDG_VTNR" = "1" ]; then
    export XDG_SESSION_TYPE=wayland
    export XDG_CURRENT_DESKTOP=Hyprland
    export MOZ_ENABLE_WAYLAND=1
    export QT_QPA_PLATFORM=wayland
    exec Hyprland
fi
```

### 53.10 Debugging Startup Issues
```bash
# Check journalctl for your session
journalctl --user -b --since "10 minutes ago"

# Check if env is in systemd
systemctl --user show-environment | grep -E "WAYLAND|DISPLAY|DESKTOP"

# Test portal manually
/usr/lib/xdg-desktop-portal --replace --verbose 2>&1 | grep -i error
```
