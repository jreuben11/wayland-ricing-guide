# Chapter 109 — Idle Management: hypridle, swayidle, DPMS, and the Idle-Inhibit Protocol

## Contents

- [Overview](#overview)
- [109.1 The Protocol Stack](#1091-the-protocol-stack)
  - [ext-idle-notify-v1 (2023+, compositor-independent)](#ext-idle-notify-v1-2023-compositor-independent)
  - [org_kde_kwin_idle (legacy)](#orgkdekwinidle-legacy)
  - [idle-inhibit-unstable-v1](#idle-inhibit-unstable-v1)
- [109.2 hypridle (Hyprland)](#1092-hypridle-hyprland)
  - [Installation](#installation)
  - [Configuration](#configuration)
  - [Session Startup](#session-startup)
- [109.3 swayidle (wlroots compositors: Sway, River, labwc, niri)](#1093-swayidle-wlroots-compositors-sway-river-labwc-niri)
  - [Installation](#installation)
  - [Basic Configuration](#basic-configuration)
  - [As a Sway exec](#as-a-sway-exec)
  - [River / labwc / niri](#river-labwc-niri)
- [109.4 DPMS Control](#1094-dpms-control)
  - [Compositor-specific commands](#compositor-specific-commands)
  - [wlopm](#wlopm)
- [109.5 The Idle-Inhibit Protocol in Detail](#1095-the-idle-inhibit-protocol-in-detail)
  - [How Inhibitors Work](#how-inhibitors-work)
  - [Testing Inhibitors](#testing-inhibitors)
  - [Programmatic Inhibitor (Python, for scripts)](#programmatic-inhibitor-python-for-scripts)
- [109.6 Inhibitors for Non-Compliant Apps](#1096-inhibitors-for-non-compliant-apps)
  - [xdg-screensaver Shim](#xdg-screensaver-shim)
  - [systemd-inhibit](#systemd-inhibit)
  - [Fullscreen Detection Script](#fullscreen-detection-script)
- [109.7 logind vs. Idle Daemon: Avoiding Conflicts](#1097-logind-vs-idle-daemon-avoiding-conflicts)
- [109.8 Quickshell Integration](#1098-quickshell-integration)
- [109.9 Troubleshooting](#1099-troubleshooting)
  - [Screen locks but DPMS doesn't turn off](#screen-locks-but-dpms-doesnt-turn-off)
  - [Screen never locks on battery](#screen-never-locks-on-battery)
  - [Suspend fires but screen is not locked on resume](#suspend-fires-but-screen-is-not-locked-on-resume)
  - [hypridle not starting](#hypridle-not-starting)
  - [Inhibitors not working for a specific app](#inhibitors-not-working-for-a-specific-app)
- [Summary](#summary)

---


## Overview

Idle management on Wayland is the system that decides what happens when you stop touching your keyboard and mouse: dim the screen after 60 seconds, lock after 5 minutes, suspend after 15. Getting it right is one of the first things a new rice needs and one of the first things that breaks when you upgrade. Getting it wrong means either your screen never sleeps (draining a laptop battery) or your screen locks mid-presentation during a video call.

The Wayland idle stack has three layers:

1. **The idle-notification protocol** — the compositor detects idleness and notifies an idle daemon
2. **The idle daemon** — runs user-defined actions at idle thresholds (dim, lock, DPMS off, suspend)
3. **The idle-inhibit protocol** — apps that must stay awake (video players, screen share sessions) request an inhibitor that suppresses the idle daemon's actions

This chapter covers all three layers in full, for both Hyprland (`hypridle`) and wlroots-based compositors (`swayidle`), including DPMS control, per-app inhibitors, integration with screen lockers (ch 30), and systemd's competing `logind` idle handling.

**Cross-references:** Ch 30 — screen lockers (hyprlock, swaylock). Ch 53 — session startup, where idle daemons are launched. Ch 56 — PipeWire/media session, which affects inhibitor state. Ch 78 — laptop power management (suspend/hibernate on lid close).

---

## 109.1 The Protocol Stack

### ext-idle-notify-v1 (2023+, compositor-independent)

The `ext-idle-notify-v1` protocol is the modern, stable standard. Any compositor implementing it can notify idle daemons without custom IPC. It works by:

1. The idle daemon binds `ext_idle_notifier_v1` from the compositor
2. For each timeout, it creates an `ext_idle_notification_v1` object specifying a seat and a millisecond threshold
3. The compositor emits `idled` when the seat has been idle for that duration, and `resumed` on any input event

```
ext_idle_notifier_v1
  └── get_idle_notification(timeout_ms, seat) → ext_idle_notification_v1
        ├── event: idled   → run lock/dim/DPMS-off command
        └── event: resumed → run unlock/undim/DPMS-on command
```

Both `hypridle` (Hyprland ≥ 0.41) and `swayidle` (≥ 1.8) implement the client side of this protocol. Older Hyprland versions used a proprietary IPC; always use `hypridle` with a recent Hyprland to get `ext-idle-notify-v1` semantics.

### org_kde_kwin_idle (legacy)

The KDE idle protocol predates `ext-idle-notify-v1`. KWin still advertises it for compatibility with older tools. If you are on Plasma 6 and not using any custom idle daemon, KWin handles idle actions internally through System Settings → Screen Locking.

### idle-inhibit-unstable-v1

The inhibitor protocol is a client-side API — apps call it, not daemons. A client creates an `zwp_idle_inhibitor_v1` object attached to a `wl_surface`. While the surface exists and the inhibitor is attached, the compositor suppresses idle notifications for the inhibiting seat. When the inhibitor is destroyed (or the surface is unmapped), idle resumes.

```
zwp_idle_inhibit_manager_v1
  └── create_inhibitor(surface) → zwp_idle_inhibitor_v1
        └── destroy() → idle resumes
```

Apps that implement this correctly: `mpv`, `VLC`, Firefox (during video), `zoom`, `teams`, `obs-studio`. Apps that do not: most Electron apps, many Qt apps older than 2022. For non-compliant apps, §109.6 covers workarounds.

---

## 109.2 hypridle (Hyprland)

`hypridle` is the official Hyprland idle daemon. It reads from `~/.config/hypr/hypridle.conf` and uses the `ext-idle-notify-v1` protocol.

### Installation

```bash
# Arch Linux
sudo pacman -S hypridle

# Nix
home.packages = [ pkgs.hypridle ];
```

### Configuration

```ini
# ~/.config/hypr/hypridle.conf

general {
    lock_cmd = pidof hyprlock || hyprlock   # only one hyprlock instance at a time
    before_sleep_cmd = loginctl lock-session # lock before systemd suspend
    after_sleep_cmd = hyprctl dispatch dpms on   # DPMS on after resume
    ignore_dbus_inhibit = false              # respect xdg-screensaver inhibit calls
    ignore_systemd_inhibit = false           # respect systemd-inhibit locks
}

# Step 1: dim the screen after 2.5 minutes
listener {
    timeout = 150
    on-timeout = brightnessctl -s set 20%   # save current brightness, set to 20%
    on-resume = brightnessctl -r             # restore saved brightness
}

# Step 2: lock after 5 minutes
listener {
    timeout = 300
    on-timeout = loginctl lock-session
    on-resume = hyprctl dispatch dpms on
}

# Step 3: DPMS off after 5.5 minutes (30s after lock)
listener {
    timeout = 330
    on-timeout = hyprctl dispatch dpms off
    on-resume = hyprctl dispatch dpms on
}

# Step 4: suspend after 30 minutes
listener {
    timeout = 1800
    on-timeout = systemctl suspend
    on-resume = hyprctl dispatch dpms on
}
```

The `lock_cmd` field in `general {}` also fires when `loginctl lock-session` is called by other tools (e.g., a keybind or lid-close event from logind). This makes hypridle the single choke-point for all lock requests.

### Session Startup

```ini
# ~/.config/hypr/hyprland.conf
exec-once = hypridle
```

Or via a systemd user unit (preferred — lets other units depend on it):

```ini
# ~/.config/systemd/user/hypridle.service
[Unit]
Description=Hyprland idle daemon
PartOf=graphical-session.target
After=graphical-session.target

[Service]
ExecStart=/usr/bin/hypridle
Restart=on-failure

[Install]
WantedBy=graphical-session.target
```

```bash
systemctl --user enable --now hypridle
```

---

## 109.3 swayidle (wlroots compositors: Sway, River, labwc, niri)

`swayidle` is the reference idle daemon for the wlroots ecosystem. Its configuration is all on the command line (no config file), which makes it easy to compose with shell scripts.

### Installation

```bash
# Arch
sudo pacman -S swayidle

# Ubuntu 24.04+
sudo apt install swayidle
```

### Basic Configuration

```bash
# Minimal swayidle invocation for a Sway session
swayidle -w \
    timeout 150  'brightnessctl -s set 20%' \
        resume   'brightnessctl -r' \
    timeout 300  'loginctl lock-session' \
    timeout 330  'swaymsg "output * dpms off"' \
        resume   'swaymsg "output * dpms on"' \
    timeout 1800 'systemctl suspend' \
    before-sleep 'loginctl lock-session'
```

The `-w` flag makes swayidle wait for each command to finish before moving on — important when locking, since you want the locker running before DPMS turns off.

`before-sleep` fires on `PrepareForSleep(true)` from logind, immediately before the system suspends. Always lock here to prevent the screen from briefly showing before swaylock activates on resume.

### As a Sway exec

```
# ~/.config/sway/config
exec swayidle -w \
    timeout 150  'brightnessctl -s set 20%' resume 'brightnessctl -r' \
    timeout 300  'swaylock -f' \
    timeout 330  'swaymsg "output * dpms off"' resume 'swaymsg "output * dpms on"' \
    timeout 1800 'systemctl suspend' \
    before-sleep 'swaylock -f'
```

### River / labwc / niri

swayidle works on any compositor that implements `ext-idle-notify-v1`. Adjust the DPMS command to the compositor's IPC:

```bash
# River
timeout 330 'riverctl output-power off' resume 'riverctl output-power on'

# labwc (no IPC for DPMS; use wlopm)
timeout 330 'wlopm --off \*' resume 'wlopm --on \*'

# niri
timeout 330 'niri msg action power-off-monitors' resume 'niri msg action power-on-monitors'
```

---

## 109.4 DPMS Control

DPMS (Display Power Management Signaling) switches the monitor into a standby/off power state without suspending the system. On Wayland, DPMS is compositor-controlled — there is no global `xset dpms` equivalent.

### Compositor-specific commands

```bash
# Hyprland
hyprctl dispatch dpms off          # all outputs
hyprctl dispatch dpms off DP-1     # specific output

# Sway
swaymsg "output * dpms off"
swaymsg "output DP-1 dpms off"

# River
riverctl output-power off

# niri
niri msg action power-off-monitors

# Generic (wlroots compositors): wlopm
wlopm --off '*'            # all outputs
wlopm --on  'DP-1'
wlopm --toggle 'HDMI-A-1'
```

### wlopm

`wlopm` is a standalone tool that uses the `wlr-output-power-management-unstable-v1` protocol. Install it from the AUR (`wlopm`) or from source. It works with any wlroots-based compositor and is the cleanest option for swayidle's `resume` callbacks since it does not require IPC knowledge:

```bash
wlopm --off \*          # off
wlopm --on  \*          # on
```

---

## 109.5 The Idle-Inhibit Protocol in Detail

### How Inhibitors Work

When an app creates an inhibitor, the compositor sets a flag on the seat that prevents `ext-idle-notify-v1` `idled` events from firing. The inhibitor is tied to a surface (window), not the process, so:

- If the video player is fullscreen on one monitor and you switch to another workspace, the inhibitor may or may not still apply depending on compositor policy (Hyprland suppresses idle globally; Sway suppresses per-seat)
- Minimized/unmapped surfaces lose their inhibitor automatically
- A crash that drops the Wayland connection destroys all inhibitors

### Testing Inhibitors

```bash
# Verify an inhibitor is active using wayland-info (wayland-utils package)
wayland-info | grep -A5 idle_inhibit

# Or watch compositor logs for inhibitor events
HYPRLAND_LOG_WLR=1 Hyprland 2>&1 | grep -i inhibit
```

### Programmatic Inhibitor (Python, for scripts)

```python
#!/usr/bin/env python3
"""Hold an idle inhibitor for the lifetime of this process."""
import subprocess, signal, sys, time

# Use wayland-idle-inhibitor from crates.io as a convenient wrapper:
proc = subprocess.Popen(['wayland-idle-inhibitor'])
signal.signal(signal.SIGTERM, lambda *_: (proc.terminate(), sys.exit(0)))
try:
    proc.wait()
except KeyboardInterrupt:
    proc.terminate()
```

Or using the `pywayland` library directly:

```python
from pywayland.client import Display
from pywayland.protocol.idle_inhibit_unstable_v1 import ZwpIdleInhibitManagerV1
from pywayland.protocol.wayland import WlCompositor, WlSurface

def hold_inhibitor():
    display = Display()
    display.connect()
    registry = display.get_registry()

    manager = None
    compositor = None

    @registry.dispatcher['global']
    def on_global(registry, name, interface, version):
        nonlocal manager, compositor
        if interface == 'zwp_idle_inhibit_manager_v1':
            manager = registry.bind(name, ZwpIdleInhibitManagerV1, version)
        elif interface == 'wl_compositor':
            compositor = registry.bind(name, WlCompositor, version)

    display.roundtrip()
    surface = compositor.create_surface()
    inhibitor = manager.create_inhibitor(surface)
    display.roundtrip()
    print("Idle inhibitor active. Ctrl-C to release.")
    try:
        while True:
            display.dispatch()
    except KeyboardInterrupt:
        inhibitor.destroy()
        surface.destroy()
        display.roundtrip()

hold_inhibitor()
```

---

## 109.6 Inhibitors for Non-Compliant Apps

### xdg-screensaver Shim

Some apps (especially older GTK2/Qt5 apps) call `xdg-screensaver suspend <window-id>` — an X11 mechanism. `hypridle` and `swayidle` both support this via `ignore_dbus_inhibit = false` (hypridle) which reads `org.freedesktop.ScreenSaver.Inhibit` D-Bus calls.

Verify with:
```bash
busctl monitor --system org.freedesktop.ScreenSaver
```

### systemd-inhibit

Some apps call systemd inhibitors (`systemd-inhibit --what=idle`). Both hypridle (via `ignore_systemd_inhibit`) and swayidle respect these when built with systemd support.

```bash
# Check active systemd inhibitors
systemd-inhibit --list
```

### Fullscreen Detection Script

For apps that implement neither protocol, a polling script can detect fullscreen windows and toggle an inhibitor:

```bash
#!/bin/bash
# ~/.local/bin/fullscreen-inhibit
# Run this alongside swayidle. Holds an inhibitor while any fullscreen window exists.

INHIBITOR_PID=""

while true; do
    # Hyprland: check for fullscreen window
    FULLSCREEN=$(hyprctl -j activewindow | jq '.fullscreen')

    if [ "$FULLSCREEN" = "true" ] && [ -z "$INHIBITOR_PID" ]; then
        wayland-idle-inhibitor &
        INHIBITOR_PID=$!
    elif [ "$FULLSCREEN" != "true" ] && [ -n "$INHIBITOR_PID" ]; then
        kill "$INHIBITOR_PID" 2>/dev/null
        INHIBITOR_PID=""
    fi
    sleep 5
done
```

For Sway, replace the Hyprland IPC call with:
```bash
FULLSCREEN=$(swaymsg -t get_tree | jq '[.. | objects | select(.focused==true and .fullscreen_mode==1)] | length > 0')
```

---

## 109.7 logind vs. Idle Daemon: Avoiding Conflicts

`systemd-logind` has its own idle and lock logic controlled by `/etc/systemd/logind.conf` and `~/.config/systemd/logind.conf.d/`. The relevant options:

```ini
# /etc/systemd/logind.conf
[Login]
IdleAction=suspend           # action when idle: ignore, poweroff, reboot, halt, kexec, suspend, hibernate, hybrid-sleep, suspend-then-hibernate, lock
IdleActionSec=30min          # timeout before IdleAction
HandleLidSwitch=suspend      # what to do on lid close
HandleLidSwitchExternalPower=ignore  # override when on AC
HandleSuspendKey=suspend
HandleHibernateKey=hibernate
HandlePowerKey=poweroff
```

**Conflict to avoid:** if both logind and swayidle/hypridle watch for idle, they will both fire at different times. The correct setup is:

- Disable logind's `IdleAction` (set to `ignore`) and manage everything in the idle daemon
- Keep logind's `HandleLidSwitch` and `HandleSuspendKey` — these are hardware events logind handles correctly
- Use `before-sleep` in swayidle / `before_sleep_cmd` in hypridle to lock before logind suspends

```bash
# Disable logind idle (keep hardware event handling)
mkdir -p /etc/systemd/logind.conf.d
cat > /etc/systemd/logind.conf.d/idle.conf << 'EOF'
[Login]
IdleAction=ignore
EOF
systemctl restart systemd-logind
```

---

## 109.8 Quickshell Integration

If you use Quickshell, the `IdleInhibitor` QML type lets you hold an inhibitor declaratively:

```qml
import Quickshell
import Quickshell.Wayland

// Hold an inhibitor while a video is playing
IdleInhibitor {
    active: mediaPlayer.playing
}
```

The inhibitor is created and destroyed as `active` changes, with no script subprocess needed.

---

## 109.9 Troubleshooting

### Screen locks but DPMS doesn't turn off

DPMS command fires before the locker's surface is mapped. Solution: increase the gap between lock timeout and DPMS timeout (30 seconds is usually enough), or use `swayidle -w` to wait for lock to complete.

### Screen never locks on battery

Check that logind's `IdleAction` is not set to `ignore` on battery while you expect hypridle to handle it. Also verify `ignore_dbus_inhibit = false` in hypridle — a browser with an open video tab may be inhibiting.

### Suspend fires but screen is not locked on resume

`before_sleep_cmd` / `before-sleep` must run *synchronously* and wait for the locker to draw its first frame. Add `-f` (fork-and-exit after auth surface is shown) to swaylock/hyprlock, and add `sleep 0.5` after the lock command if the window takes time to map.

### hypridle not starting

Verify `WAYLAND_DISPLAY` is set in the service environment:
```bash
systemctl --user show-environment | grep WAYLAND
# If missing:
systemctl --user import-environment WAYLAND_DISPLAY XDG_RUNTIME_DIR
```

### Inhibitors not working for a specific app

```bash
# Check what inhibit calls the app makes
WAYLAND_DEBUG=1 app_name 2>&1 | grep inhibit
# Or check D-Bus screensaver calls
dbus-monitor --session "interface='org.freedesktop.ScreenSaver'"
```

---

## Summary

The idle stack is three independent layers: the compositor detects idleness via `ext-idle-notify-v1`, the daemon (`hypridle` or `swayidle`) translates timeouts into lock/dim/DPMS/suspend commands, and apps hold back the daemon via the `zwp_idle_inhibit_manager_v1` protocol. Keep logind's `IdleAction=ignore` to prevent double-firing, use `before_sleep_cmd` to lock before suspend, and use a fullscreen-detection script for apps that don't implement the inhibitor protocol.

**Further reading:**
- Ch 30 — screen lockers (hyprlock, swaylock, gtklock)
- Ch 53 — session startup and service management
- Ch 78 — laptop power management and suspend/hibernate
- Ch 56 — PipeWire session management (media inhibitors)
