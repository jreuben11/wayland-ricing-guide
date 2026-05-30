# Chapter 136 — UWSM and Wayland Session Managers

## Contents

- [Overview](#overview)
- [136.1 The Problem with Plain Compositor Launch](#1361-the-problem-with-plain-compositor-launch)
- [136.2 UWSM: Universal Wayland Session Manager](#1362-uwsm-universal-wayland-session-manager)
  - [Installation](#installation)
  - [Starting a Compositor with UWSM](#starting-a-compositor-with-uwsm)
  - [Display Manager Integration](#display-manager-integration)
  - [Compositor .desktop Entry](#compositor-desktop-entry)
  - [Environment Export](#environment-export)
  - [Stopping and Restarting](#stopping-and-restarting)
- [136.3 dbus-run-session](#1363-dbus-run-session)
- [136.4 systemd-run for Compositor Launch](#1364-systemd-run-for-compositor-launch)
- [136.5 Comparison: Session Management Approaches](#1365-comparison-session-management-approaches)
- [136.6 Waybar and Other Services as Systemd Units](#1366-waybar-and-other-services-as-systemd-units)
- [136.7 Autostart File for Non-UWSM Compositors](#1367-autostart-file-for-non-uwsm-compositors)

---


## Overview

Starting a Wayland compositor correctly is more complex than running a single binary. Environment variables must reach D-Bus and systemd user services, the compositor must be a proper systemd unit so that child services can depend on it, and the session must survive compositor restarts without orphaning processes. The Universal Wayland Session Manager (UWSM) solves all of this in a compositor-agnostic way. This chapter covers UWSM, the `dbus-run-session` pattern, `systemd-run` for compositors, and a comparison to the `exec-once` + manual `import-environment` approach covered in Chapter 53.

**Cross-references:** Ch 53 — session startup and environment (exec-once, basic systemd user session). Ch 54 — display managers and greeters (SDDM, greetd). Ch 109 — idle management (hypridle as a systemd unit).

---

## 136.1 The Problem with Plain Compositor Launch

When a compositor is launched directly from a TTY or display manager without session management:

```
Problems:
  - D-Bus session bus may not be running
  - WAYLAND_DISPLAY, XDG_SESSION_TYPE etc. may not reach systemd user services
  - systemctl --user status shows services as "not activated"
  - Desktop portals may fail to connect (missing env vars)
  - On compositor crash, child processes become orphans
  - No clean "compositor unit" for other services to After=/BindsTo=
```

The traditional workaround:
```bash
# In compositor startup (e.g., Hyprland exec-once)
exec-once = systemctl --user import-environment WAYLAND_DISPLAY XDG_CURRENT_DESKTOP
exec-once = dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP
```

This works but is fragile: variables must be manually listed, there is a race between the import and portal startup, and the compositor itself is not a proper systemd unit.

---

## 136.2 UWSM: Universal Wayland Session Manager

UWSM wraps any Wayland compositor in a systemd unit hierarchy:

```
systemd user session
└── wayland-session@compositor.service
    ├── wayland-wm@compositor.service   (the compositor itself)
    └── wayland-session.target
        ├── xdg-desktop-portal.service
        ├── waybar.service
        └── ... (all graphical-session services)
```

This gives:
- Compositor as a proper systemd unit with `Type=notify`
- All environment variables exported before any dependent service starts
- `graphical-session.target` activated correctly
- Compositor restart without orphaning session services
- `systemctl --user stop wayland-wm@hyprland` to stop compositor cleanly

### Installation

```bash
# Arch AUR
yay -S uwsm

# From source
git clone https://github.com/Vladimir-csp/uwsm
cd uwsm
# Python package — no build step
pip install --user .
# or: just copy uwsm to ~/.local/bin/

# Verify
uwsm --version
```

### Starting a Compositor with UWSM

```bash
# Start Hyprland via UWSM (from TTY or display manager)
uwsm start hyprland

# Start Sway
uwsm start sway

# Start with a specific .desktop session entry
uwsm start hyprland.desktop

# Stop the session
uwsm stop
```

### Display Manager Integration

For greetd:
```toml
# /etc/greetd/config.toml
[terminal]
vt = 1

[default_session]
command = "uwsm start hyprland"
user = "alice"
```

For SDDM with a custom session file:
```ini
# /usr/share/wayland-sessions/hyprland-uwsm.desktop
[Desktop Entry]
Name=Hyprland (UWSM)
Comment=Hyprland compositor via UWSM
Exec=uwsm start hyprland
Type=Application
```

### Compositor .desktop Entry

UWSM reads compositor metadata from `.desktop` files in `/usr/share/wayland-sessions/`. For compositors that don't have one:

```ini
# ~/.local/share/wayland-sessions/my-compositor.desktop
[Desktop Entry]
Name=My Compositor
Exec=/usr/local/bin/my-compositor
DesktopNames=my-compositor
Type=Application
```

### Environment Export

UWSM automatically exports the compositor's environment to systemd and D-Bus before starting dependent services. No manual `import-environment` is needed.

To add extra variables:
```bash
# In ~/.config/uwsm/env (loaded before compositor starts)
# or in compositor-specific env file:
# ~/.config/uwsm/env-hyprland

export MOZ_ENABLE_WAYLAND=1
export QT_QPA_PLATFORM=wayland
export ELECTRON_OZONE_PLATFORM_HINT=auto
export NIXOS_OZONE_WL=1
```

### Stopping and Restarting

```bash
# Stop the compositor (and all session services)
uwsm stop

# Restart just the compositor (services stay running)
systemctl --user restart wayland-wm@hyprland.service

# Check compositor status
systemctl --user status wayland-wm@hyprland.service

# View compositor logs
journalctl --user -u wayland-wm@hyprland.service -f
```

---

## 136.3 dbus-run-session

`dbus-run-session` is a simpler utility that starts a D-Bus session bus and runs the compositor as a child, exiting when the compositor exits:

```bash
# Basic usage — ensures D-Bus session exists
dbus-run-session hyprland

# With environment setup
dbus-run-session -- sh -c '
    export MOZ_ENABLE_WAYLAND=1
    export QT_QPA_PLATFORM=wayland
    exec hyprland
'
```

This is lighter than UWSM — useful if you only need D-Bus and don't care about systemd integration. It does **not** propagate variables to existing systemd user services.

When to use `dbus-run-session`:
- Simple setups without systemd user services
- Development/testing a compositor
- Situations where UWSM is unavailable

---

## 136.4 systemd-run for Compositor Launch

`systemd-run --user` launches the compositor as a transient systemd unit:

```bash
# Run Hyprland as a transient user service
systemd-run --user \
    --unit=wayland-compositor \
    --collect \
    --service-type=notify \
    -- hyprland

# Check status
systemctl --user status wayland-compositor

# Stop
systemctl --user stop wayland-compositor
```

For environment propagation, combine with `systemd-cat` or pre-set via `systemctl --user set-environment`:

```bash
# Set env vars in the systemd user manager before launching
systemctl --user set-environment \
    WAYLAND_DISPLAY=wayland-1 \
    QT_QPA_PLATFORM=wayland \
    MOZ_ENABLE_WAYLAND=1

# Then start compositor as a unit
systemd-run --user --unit=compositor -- hyprland
```

---

## 136.5 Comparison: Session Management Approaches

| Approach | D-Bus | systemd integration | Env propagation | Auto-restart | Complexity |
|---|---|---|---|---|---|
| **Direct launch** (TTY) | Maybe | None | Manual | No | Minimal |
| **exec-once + import-environment** | Inherited | Partial (manual) | Manual list | No | Low |
| **dbus-run-session** | Yes (new bus) | None | None | No | Low |
| **systemd-run --user** | Inherited | Transient unit | Pre-set only | Optional | Medium |
| **UWSM** | Yes | Full (proper unit) | Automatic | Via systemd | Medium |
| **GNOME/KDE session managers** | Yes | Full | Automatic | Yes | High (DE-specific) |

---

## 136.6 Waybar and Other Services as Systemd Units

When using UWSM, bar and applet services can depend properly on the compositor unit:

```ini
# ~/.config/systemd/user/waybar.service
[Unit]
Description=Waybar
PartOf=graphical-session.target
After=graphical-session.target

[Service]
ExecStart=/usr/bin/waybar
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical-session.target
```

```bash
# Enable so it starts with every UWSM session
systemctl --user enable waybar.service

# UWSM activates graphical-session.target → Waybar starts
uwsm start hyprland
```

This is cleaner than `exec-once = waybar` because:
- Waybar restarts automatically if it crashes
- `systemctl --user restart waybar` works without touching the compositor config
- Logs go to journald: `journalctl --user -u waybar -f`

---

## 136.7 Autostart File for Non-UWSM Compositors

If UWSM is not available, a hardened startup script that replicates most of its behavior:

```bash
#!/bin/bash
# ~/.local/bin/start-hyprland
# Hardened Hyprland launcher with proper env propagation

set -euo pipefail

# Export Wayland session type
export XDG_SESSION_TYPE=wayland
export XDG_SESSION_DESKTOP=hyprland
export XDG_CURRENT_DESKTOP=Hyprland

# App compatibility
export MOZ_ENABLE_WAYLAND=1
export QT_QPA_PLATFORM=wayland
export ELECTRON_OZONE_PLATFORM_HINT=auto
export SDL_VIDEODRIVER=wayland
export NIXOS_OZONE_WL=1

# Start D-Bus session if not already running
if [ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ]; then
    eval "$(dbus-launch --sh-syntax --exit-with-session)"
fi

# Start the compositor
exec systemd-cat --identifier=hyprland hyprland
```

```ini
# /usr/share/wayland-sessions/hyprland-hardened.desktop
[Desktop Entry]
Name=Hyprland (Hardened)
Exec=~/.local/bin/start-hyprland
Type=Application
```
