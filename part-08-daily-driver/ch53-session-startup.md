# Chapter 53 — Session Startup and Environment: exec-once, dbus, systemd user

## Overview

The most common category of Wayland breakage is startup order: apps launched
before their dependencies, D-Bus services not yet ready, environment variables
missing. This chapter explains the correct startup sequence, the mechanism behind
each layer, and how to diagnose the silent failures that plague poorly ordered
configurations.

Unlike X11, where `.xinitrc` ran sequentially in a single shell context, Wayland
sessions span multiple process trees, IPC buses, and init systems. A configuration
that "mostly works" on a fresh boot may silently fail screen sharing, break portal
integrations, or leave the system tray empty — not because the apps are wrong,
but because they arrived before their environment was ready.

This chapter covers Hyprland and Sway in depth, with notes on niri and river where
their approaches diverge. For display manager configuration, see Ch 50. For
portal-specific debugging (screen share, file picker), see Ch 55.

---

## 53.1 The Startup Problem

On X11, `.xinitrc` ran sequentially and most things just worked. Wayland requires
a much more careful ordering because the session involves at minimum three
independent process trees:

- The systemd user session (started at login, manages D-Bus and runtime dirs)
- The compositor (Hyprland, Sway, niri — owns the Wayland socket)
- User-space services and apps (launched by exec-once or systemd units)

Getting this wrong means: silent failures, no audio, broken screen sharing,
missing system tray items, race conditions on login. The failures are often
non-deterministic — a fast machine may succeed where a slow one fails, masking
the root cause.

The core principle is **environment-before-services**: nothing that depends on
`WAYLAND_DISPLAY`, `XDG_SESSION_TYPE`, or `XDG_CURRENT_DESKTOP` should start
before those variables are both set and propagated to the D-Bus activation
environment and the systemd user manager. Many hours of debugging dissolve once
this single rule is understood and enforced.

Four common failure modes and their root causes:

| Symptom | Root cause |
|---|---|
| No audio on first login | PipeWire started before `XDG_RUNTIME_DIR` was exported |
| Screen sharing returns black | `xdg-desktop-portal` launched without `WAYLAND_DISPLAY` |
| System tray icons missing | Bar started before D-Bus `StatusNotifierWatcher` registered |
| GTK apps use wrong theme | `GTK_THEME` not propagated to D-Bus activation environment |

---

## 53.2 The Three Startup Layers

Every well-functioning Wayland session has a clear layered structure. Treat each
layer as a dependency boundary: nothing in a lower layer should assume that
anything from a higher layer is ready.

```
Layer 1: systemd user session (pre-login, managed by systemd)
   ↓  provides: D-Bus session bus, XDG_RUNTIME_DIR, pipewire.service
   ↓
Layer 2: Compositor (Hyprland/Sway/etc) — sets env, starts via Layer 1 or DM
   ↓  provides: WAYLAND_DISPLAY socket, compositor protocol extensions
   ↓
Layer 3: exec-once / exec (your apps — started after compositor is running)
          provides: visible UI, portals, bars, background services
```

**Layer 1** is managed entirely by `systemd --user`. It starts at login (via PAM,
before any display manager session begins) and provides the D-Bus session bus, the
`XDG_RUNTIME_DIR` (usually `/run/user/$(id -u)`), and any user services marked
`WantedBy=default.target`. On most distributions, `pipewire.service`,
`pipewire-pulse.service`, and `wireplumber.service` are already wired into this
layer via socket activation or explicit `WantedBy` declarations.

**Layer 2** is the compositor. Whether started by a display manager (SDDM, GDM,
greetd) or a TTY autologin script, the compositor's job at startup is to: create
the Wayland socket, set critical environment variables, and then propagate those
variables upward into the D-Bus activation environment and systemd user manager.
This propagation step is the most commonly omitted and the source of most failures.

**Layer 3** is everything you put in `exec-once` (Hyprland) or `exec` (Sway):
bars, portals, clipboard managers, idle daemons, wallpaper engines, notification
daemons, and finally the apps you want to restore on login. Ordering within this
layer still matters — portals must come before anything that invokes them, and the
auth agent must come before any privileged GUI operation.

---

## 53.3 systemd User Session

The systemd user session starts automatically on first login via the `user@.service`
unit (one per UID). It runs independently of the graphical session and manages its
own set of units under `~/.config/systemd/user/` and the distribution's drop-in
directories. Check it is active and healthy before diagnosing anything else:

```bash
# Overall session health
systemctl --user status

# List all active user units
systemctl --user list-units --state=active

# Show the environment as systemd sees it
systemctl --user show-environment

# Follow live logs from this boot
journalctl --user -b -f
```

On a healthy system, `systemctl --user status` reports `State: running` and you
should see `pipewire.service`, `pipewire-pulse.service`, and `wireplumber.service`
among the active units. If PipeWire units are not active, check whether they are
masked (`systemctl --user status pipewire`) or whether the socket file exists in
`XDG_RUNTIME_DIR`:

```bash
ls -la "$XDG_RUNTIME_DIR"/pipewire*
# Expected: pipewire-0, pipewire-0.lock
```

**Hyprland as a systemd service target** (recommended approach — avoids environment
propagation races by using systemd ordering):

```ini
# ~/.config/systemd/user/hyprland-session.target
[Unit]
Description=Hyprland compositor session
Documentation=man:systemd.special(7)
BindsTo=graphical-session.target
Wants=graphical-session-pre.target
After=graphical-session-pre.target
```

With this target in place, you can then order other services relative to
`hyprland-session.target` rather than against a fixed `sleep` delay. This is
strictly better than `exec-once = sleep 1 && ...` hacks.

```ini
# ~/.config/systemd/user/xdg-desktop-portal-hyprland.service
[Unit]
Description=Hyprland XDG Desktop Portal
Requires=hyprland-session.target
After=hyprland-session.target
PartOf=graphical-session.target

[Service]
Type=dbus
BusName=org.freedesktop.impl.portal.desktop.hyprland
ExecStart=/usr/lib/xdg-desktop-portal-hyprland
Restart=on-failure
RestartSec=1
TimeoutStopSec=10

[Install]
WantedBy=graphical-session.target
```

Enable it: `systemctl --user enable --now xdg-desktop-portal-hyprland.service`

---

## 53.4 Environment Variable Propagation

The critical step that most rices get wrong: environment variables set in the
compositor config are NOT automatically visible to systemd user services or D-Bus
activated processes. The compositor runs in its own process context; unless you
explicitly push variables upward, services that start later via D-Bus activation
inherit the bare environment from the systemd user session, which predates the
compositor's existence.

Two commands accomplish the propagation, and you should run **both**:

- `dbus-update-activation-environment` — pushes variables into the D-Bus session
  daemon, which passes them to any service D-Bus activates thereafter
- `systemctl --user import-environment` — pushes variables into the systemd user
  manager, so units started after this point inherit them via `Environment=`
  passthrough

**Hyprland — the correct way:**

```conf
# hyprland.conf — near the top, before any exec-once lines
env = WAYLAND_DISPLAY,wayland-1
env = XDG_SESSION_TYPE,wayland
env = XDG_CURRENT_DESKTOP,Hyprland
env = XDG_SESSION_DESKTOP,Hyprland

# GTK / Qt / Electron app settings
env = GDK_BACKEND,wayland,x11,*
env = QT_QPA_PLATFORM,wayland;xcb
env = QT_QPA_PLATFORMTHEME,qt6ct
env = QT_WAYLAND_DISABLE_WINDOWDECORATION,1
env = SDL_VIDEODRIVER,wayland
env = CLUTTER_BACKEND,wayland
env = MOZ_ENABLE_WAYLAND,1
env = MOZ_DBUS_REMOTE,1
env = ELECTRON_OZONE_PLATFORM_HINT,wayland

# Critical: propagate to D-Bus and systemd BEFORE starting any services
exec-once = dbus-update-activation-environment --systemd --all
exec-once = systemctl --user import-environment WAYLAND_DISPLAY XDG_CURRENT_DESKTOP XDG_SESSION_TYPE XDG_SESSION_DESKTOP
```

**Sway — equivalent approach:**

```conf
# ~/.config/sway/config

# Set env for child processes
set $mod Mod4

# Propagate to D-Bus activation and systemd
exec systemctl --user import-environment DISPLAY WAYLAND_DISPLAY SWAYSOCK XDG_CURRENT_DESKTOP
exec hash dbus-update-activation-environment 2>/dev/null && \
     dbus-update-activation-environment --systemd \
       DISPLAY WAYLAND_DISPLAY SWAYSOCK \
       XDG_CURRENT_DESKTOP XDG_SESSION_TYPE
```

**niri — equivalent approach:**

```kdl
// ~/.config/niri/config.kdl
spawn-at-startup "systemctl" "--user" "import-environment" "WAYLAND_DISPLAY" "XDG_CURRENT_DESKTOP"
spawn-at-startup "dbus-update-activation-environment" "--systemd" "WAYLAND_DISPLAY" "XDG_CURRENT_DESKTOP" "XDG_SESSION_TYPE"
```

**Why `--all` vs explicit list:** Using `--all` with `dbus-update-activation-environment`
propagates everything in the compositor's environment, which can accidentally
propagate garbage or override existing correct values. The explicit list is safer
and more predictable. The important variables are:

| Variable | Purpose |
|---|---|
| `WAYLAND_DISPLAY` | Socket name for apps to connect to the compositor |
| `XDG_SESSION_TYPE` | Tells apps (GTK, Qt, SDL) to use Wayland backend |
| `XDG_CURRENT_DESKTOP` | Portal selects correct backend based on this |
| `XDG_SESSION_DESKTOP` | Used by some apps and by GNOME session logic |
| `DISPLAY` | Still needed for XWayland clients |
| `SWAYSOCK` | Sway-specific IPC socket path |

---

## 53.5 Hyprland exec-once Reference

The `exec-once` directive runs a command once when Hyprland starts (not on
config reload). The `exec` directive (without `-once`) runs on every config
reload — use it for things that should restart when you change their config.
The `exec-once` runs in the context of Hyprland's environment, so variables
you set with `env =` are available to these processes.

Window rule flags like `[workspace 1 silent]` can prefix exec-once commands to
place restored apps without stealing focus.

```conf
# ~/.config/hypr/hyprland.conf — complete startup section

##############################################
# STEP 1: Environment propagation
# Must be FIRST — before any service that needs WAYLAND_DISPLAY
##############################################
exec-once = dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP XDG_SESSION_TYPE XDG_SESSION_DESKTOP DISPLAY
exec-once = systemctl --user import-environment WAYLAND_DISPLAY XDG_CURRENT_DESKTOP XDG_SESSION_TYPE XDG_SESSION_DESKTOP

##############################################
# STEP 2: Authentication agent
# Must be up before any privileged GUI operation (package managers, mount, etc.)
##############################################
exec-once = /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1
# Alternative: lxqt-policykit-agent, or kwallet-pam for KDE

##############################################
# STEP 3: Audio (skip if managed by systemd socket activation)
##############################################
exec-once = pipewire
exec-once = pipewire-pulse
exec-once = wireplumber

##############################################
# STEP 4: XDG Desktop Portal
# Must start after compositor is ready; a short delay prevents race
# With hyprland-session.target this sleep is not needed
##############################################
exec-once = sleep 1 && /usr/lib/xdg-desktop-portal-hyprland
exec-once = sleep 2 && /usr/lib/xdg-desktop-portal --replace

##############################################
# STEP 5: Notification daemon
##############################################
exec-once = dunst
# Alternative: mako, swaync

##############################################
# STEP 6: Shell / bar / widgets
# After portals are up (bars query portal for StatusNotifierWatcher etc.)
##############################################
exec-once = quickshell
# exec-once = waybar  # if not using Quickshell
# exec-once = eww open bar  # if using EWW

##############################################
# STEP 7: Background services
##############################################
exec-once = hypridle
exec-once = wl-paste --type text --watch cliphist store
exec-once = wl-paste --type image --watch cliphist store
exec-once = /usr/lib/geoclue-2.0/demos/agent     # geolocation for night light
exec-once = gammastep-indicator                    # night light
exec-once = nm-applet --indicator                  # network manager tray

##############################################
# STEP 8: Wallpaper
##############################################
exec-once = swww-daemon
exec-once = sleep 0.5 && swww img ~/wallpapers/default.jpg --transition-type fade

##############################################
# STEP 9: Workspace restoration
# [workspace N silent] prevents focus steal
##############################################
exec-once = [workspace 1 silent] firefox
exec-once = [workspace 2 silent] kitty
exec-once = [workspace 3 silent] obsidian
```

Hyprland also supports `exec-shutdown` for cleanup on exit (added in Hyprland
0.40.0):

```conf
# Run on Hyprland exit (save session, clean up lock files, etc.)
exec-shutdown = pkill -f hyprpaper
exec-shutdown = ~/.config/hypr/save-session.sh
```

---

## 53.6 Sway exec vs exec-once

Sway uses `exec` (runs once at startup) and `exec_always` (runs on every reload
including `swaymsg reload`). There is no built-in `exec-once` equivalent — Sway's
philosophy is that `exec_always` commands should be idempotent (safe to re-run).
The common pattern for services that should not be duplicated on reload is to `pkill`
and restart them inside an `exec_always`:

```conf
# ~/.config/sway/config

# Environment propagation (runs once — fine for exec)
exec systemctl --user import-environment DISPLAY WAYLAND_DISPLAY SWAYSOCK XDG_CURRENT_DESKTOP XDG_SESSION_TYPE
exec hash dbus-update-activation-environment 2>/dev/null && \
     dbus-update-activation-environment --systemd \
       DISPLAY WAYLAND_DISPLAY SWAYSOCK XDG_CURRENT_DESKTOP XDG_SESSION_TYPE

# Auth agent (only needs to run once)
exec /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1

# Services that should restart on reload (pkill + restart pattern)
exec_always pkill -x mako; exec mako
exec_always pkill -x kanshi; exec kanshi      # output layout manager
exec_always pkill -x waybar; exec waybar

# Run once (will be duplicated on reload — acceptable for most session apps)
exec swayidle -w \
    timeout 300 'swaylock -f' \
    timeout 600 'swaymsg "output * power off"' \
    resume 'swaymsg "output * power on"' \
    before-sleep 'swaylock -f'

# Clipboard
exec wl-paste --type text --watch cliphist store
exec wl-paste --type image --watch cliphist store

# Wallpaper (swaybg or swww)
exec swaybg -i ~/wallpapers/default.jpg -m fill

# Workspace restoration
exec [app_id="firefox"] move container to workspace 1
for_window [app_id="firefox"] move to workspace 1
exec firefox
```

A cleaner alternative for services that must run exactly once is to move them
to systemd user units (see Section 53.8). This also gives you crash recovery.

---

## 53.7 Startup Order Best Practices

The following ordering is derived from the dependency graph of typical Wayland
session components. Violating these ordering constraints produces the failure
modes described in Section 53.1.

1. **Environment propagation first** — `dbus-update-activation-environment` and
   `systemctl --user import-environment` before anything else. No exceptions.
   Without this, every D-Bus activated service starts with a stale environment.

2. **Authentication agent second** — `polkit-gnome-authentication-agent-1` or
   equivalent must be running before any app attempts a privileged operation.
   Package managers, `gparted`, `nm-connection-editor`, mounting — all require
   a running polkit agent. Starting it late produces confusing "authentication
   failed" errors.

3. **Audio third** — PipeWire and WirePlumber if they are not already managed as
   systemd socket-activated services. Verify first:
   ```bash
   systemctl --user is-active pipewire.service
   # If "active", remove these from exec-once
   ```

4. **XDG Desktop Portal fourth** — with a small delay if not using systemd
   target ordering. The portal backends (`xdg-desktop-portal-hyprland`,
   `xdg-desktop-portal-wlr`) must start after the compositor's Wayland socket
   exists and `WAYLAND_DISPLAY` is in the D-Bus environment. The generic
   `xdg-desktop-portal` wrapper should start after the backends.

5. **Notification daemon fifth** — before the bar, since bars like waybar
   query the notification daemon's D-Bus name on startup.

6. **Bar/shell sixth** — after portals and notification daemon. Bars that
   implement `StatusNotifierItem` (system tray) register a watcher that other
   services then advertise to; starting the bar late means tray icons from
   earlier services are lost.

7. **Background services** — clipboard managers, idle daemon, geolocation,
   night light, network applet. These have no ordering requirements among
   themselves.

8. **Wallpaper** — after the compositor's render pipeline is fully up. `swww`
   needs the Wayland socket and a brief stabilization period.

9. **Session apps last** — browser, terminal, note-taking apps. Use workspace
   placement flags to avoid focus stealing.

| Priority | Component | Reason for ordering |
|---|---|---|
| 1 | `dbus-update-activation-environment` | Everything else depends on correct env |
| 2 | `systemctl --user import-environment` | systemd units need env at spawn time |
| 3 | polkit agent | Privileged ops need auth agent before they're attempted |
| 4 | PipeWire/WirePlumber | Apps check for audio on first connection |
| 5 | xdg-desktop-portal-* | Portal backends need compositor socket |
| 6 | xdg-desktop-portal | Needs backends to be registered first |
| 7 | Notification daemon | Bar queries it on startup |
| 8 | Bar/shell | Needs portal + notification daemon |
| 9 | Idle daemon | Independent, just needs Wayland socket |
| 10 | Clipboard daemon | Needs Wayland socket (wl-clipboard) |
| 11 | Wallpaper | Needs stable compositor render |
| 12 | Session apps | Last — user-visible, no others depend on them |

---

## 53.8 Using systemd User Services Instead of exec-once

For services that must be reliable — audio, portals, the auth agent — the
correct long-term approach is to move them out of `exec-once` and into systemd
user units. This provides: proper dependency ordering via `After=/Requires=`,
automatic restart on crash, `journalctl` log aggregation, and `systemctl --user
status` introspection.

**Wallpaper daemon example (hyprpaper):**

```ini
# ~/.config/systemd/user/hyprpaper.service
[Unit]
Description=Hyprland wallpaper daemon
Documentation=https://github.com/hyprwm/hyprpaper
PartOf=graphical-session.target
After=graphical-session.target

[Service]
ExecStart=/usr/bin/hyprpaper
Restart=on-failure
RestartSec=2
TimeoutStopSec=10

[Install]
WantedBy=graphical-session.target
```

**Clipboard monitor example:**

```ini
# ~/.config/systemd/user/cliphist.service
[Unit]
Description=Clipboard history daemon (wl-paste + cliphist)
PartOf=graphical-session.target
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/wl-paste --type text --watch /usr/bin/cliphist store
Restart=on-failure
RestartSec=1

[Install]
WantedBy=graphical-session.target
```

**Enable and start both:**

```bash
systemctl --user daemon-reload
systemctl --user enable --now hyprpaper.service
systemctl --user enable --now cliphist.service

# Verify
systemctl --user status hyprpaper cliphist
```

**Auth agent as a user service:**

```ini
# ~/.config/systemd/user/polkit-gnome.service
[Unit]
Description=GNOME PolicyKit Authentication Agent
Documentation=https://gitlab.gnome.org/GNOME/polkit
PartOf=graphical-session.target
After=graphical-session.target

[Service]
ExecStart=/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1
Restart=on-failure
RestartSec=1
TimeoutStopSec=5

[Install]
WantedBy=graphical-session.target
```

This gives you: proper dependency ordering, restart-on-crash, and `journalctl`
logs. If the auth agent crashes mid-session (rare but it happens), systemd
restarts it automatically rather than leaving the session in a permanently
broken state.

---

## 53.9 The ~/.profile / ~/.zprofile Layer

For non-systemd environments or TTY autologin (common on minimal installs or
when using a simple display manager like `greetd` with `agreety`), environment
must be set in the shell profile before the compositor is `exec`'d. Using
`exec` (not a bare invocation) is critical: it replaces the shell process,
ensuring that the compositor is the session leader and that logout is clean.

```bash
# ~/.zprofile (zsh) or ~/.bash_profile (bash)
# Auto-start Hyprland on TTY1 if no compositor is already running
if [ -z "$WAYLAND_DISPLAY" ] && [ "$XDG_VTNR" = "1" ]; then
    # Core session identification
    export XDG_SESSION_TYPE=wayland
    export XDG_CURRENT_DESKTOP=Hyprland
    export XDG_SESSION_DESKTOP=Hyprland

    # App platform hints
    export MOZ_ENABLE_WAYLAND=1
    export MOZ_DBUS_REMOTE=1
    export QT_QPA_PLATFORM=wayland
    export QT_QPA_PLATFORMTHEME=qt6ct
    export QT_WAYLAND_DISABLE_WINDOWDECORATION=1
    export GDK_BACKEND=wayland,x11,*
    export SDL_VIDEODRIVER=wayland
    export ELECTRON_OZONE_PLATFORM_HINT=wayland
    export CLUTTER_BACKEND=wayland

    # XWayland / DISPLAY fallback
    export DISPLAY=:0

    # Logging
    export HYPRLAND_LOG_WLR=1

    exec Hyprland
fi
```

For **Sway** on TTY autologin:

```bash
# ~/.zprofile
if [ -z "$WAYLAND_DISPLAY" ] && [ "$XDG_VTNR" = "1" ]; then
    export XDG_SESSION_TYPE=wayland
    export XDG_CURRENT_DESKTOP=sway
    export MOZ_ENABLE_WAYLAND=1
    export QT_QPA_PLATFORM=wayland
    exec sway
fi
```

For **greetd with tuigreet**, the environment is set in `/etc/greetd/config.toml`
and inherited by the compositor:

```toml
# /etc/greetd/config.toml
[terminal]
vt = 1

[default_session]
command = "tuigreet --time --remember --cmd Hyprland"
user = "greeter"
```

Combined with a `/etc/environment` or PAM-sourced `/etc/profile.d/wayland.sh`
file for the variables that must be set before greetd launches:

```bash
# /etc/profile.d/wayland.sh
export XDG_SESSION_TYPE=wayland
export GDK_BACKEND=wayland,x11,*
export QT_QPA_PLATFORM=wayland;xcb
export MOZ_ENABLE_WAYLAND=1
```

---

## 53.10 Debugging Startup Issues

When something fails to start or behaves incorrectly at session start, the
following diagnostic sequence covers 90% of cases. Work top-down: verify each
layer before blaming the layer below.

**Verify the environment was propagated:**

```bash
# Check what systemd user manager sees
systemctl --user show-environment

# Filter for the critical variables
systemctl --user show-environment | grep -E 'WAYLAND|DISPLAY|DESKTOP|SESSION'

# Expected output:
# WAYLAND_DISPLAY=wayland-1
# XDG_CURRENT_DESKTOP=Hyprland
# XDG_SESSION_TYPE=wayland
# XDG_SESSION_DESKTOP=Hyprland
# DISPLAY=:0
```

If `WAYLAND_DISPLAY` is missing from `show-environment`, your propagation
commands either did not run or ran too late. Check the exec-once ordering.

**Check session logs:**

```bash
# All user-session events since boot
journalctl --user -b

# Filter to just failures
journalctl --user -b -p err..crit

# Follow live (useful while triggering the failure)
journalctl --user -b -f

# Specific service
journalctl --user -b -u xdg-desktop-portal-hyprland.service
```

**Test portal manually:**

```bash
# Kill existing portal instances
pkill -f xdg-desktop-portal

# Start with verbose output in foreground
/usr/lib/xdg-desktop-portal --replace --verbose 2>&1 | grep -iE 'error|warn|portal'

# In a second terminal, start the Hyprland backend
/usr/lib/xdg-desktop-portal-hyprland 2>&1
```

**Verify Wayland socket:**

```bash
# Should show the socket file
ls -la "$XDG_RUNTIME_DIR"/wayland-*
# Expected: wayland-0 (or wayland-1), wayland-0.lock

# Test socket connectivity from a new shell
WAYLAND_DISPLAY=wayland-1 weston-info 2>/dev/null || echo "socket not connectable"
```

**Check PipeWire:**

```bash
# Service status
systemctl --user status pipewire pipewire-pulse wireplumber

# PipeWire introspection
pw-cli info all | grep -E 'state|version'

# Audio devices
pactl list sinks short
```

**Check D-Bus services:**

```bash
# List all registered D-Bus names (session bus)
busctl --user list

# Check if portal is registered
busctl --user status org.freedesktop.portal.Desktop 2>/dev/null || echo "portal not on D-Bus"

# Check if StatusNotifierWatcher is up (needed for system tray)
busctl --user status org.kde.StatusNotifierWatcher 2>/dev/null || echo "tray watcher not registered"
```

**Common fixes table:**

| Problem | Diagnostic | Fix |
|---|---|---|
| Portal fails | `WAYLAND_DISPLAY` absent in `show-environment` | Move env propagation to exec-once line 1 |
| No audio | `pipewire.service` inactive | `systemctl --user enable --now pipewire` |
| Black screen share | Portal started before compositor socket | Add `sleep 1` or use systemd target ordering |
| Auth prompts fail | No polkit agent in process list | Add polkit agent to exec-once step 2 |
| Bar tray empty | Bar started before `StatusNotifierWatcher` | Bar must register watcher; restart bar after services |
| GTK apps use X11 | `GDK_BACKEND` not set or `XDG_SESSION_TYPE` missing | Add to env = block and re-propagate |
| Electron apps X11 | `ELECTRON_OZONE_PLATFORM_HINT` missing | Add env variable and restart apps |

**Nuclear option — reset session and trace:**

```bash
# Kill compositor (will restart if managed by DM) and capture a clean boot log
systemctl --user stop graphical-session.target
sleep 2
# Restart from DM or TTY and immediately:
journalctl --user -b -f > /tmp/session-startup.log &
```

---

## Cross-References

- **Ch 50** — Display managers (SDDM, GDM, greetd): how the session is launched
  and where to set environment before the compositor starts.
- **Ch 52** — Hyprland configuration deep-dive: `env =` syntax, monitor setup,
  input device configuration.
- **Ch 54** — XDG Desktop Portal in depth: backend selection, portal API
  capabilities, screen sharing configuration for OBS and browser.
- **Ch 55** — PipeWire and WirePlumber: audio graph management, device routing,
  Bluetooth audio, replacing PulseAudio.
- **Ch 58** — Idle and lock screen: `hypridle`, `swayidle`, `hyprlock`,
  `swaylock` configuration and systemd inhibit integration.
- **Ch 61** — systemd user services for the full rice: converting all background
  daemons to properly ordered user units.

---

## Troubleshooting

**`dbus-update-activation-environment` command not found**
The command is provided by the `dbus` package. On Arch Linux it is always
present; on some minimal Debian/Ubuntu installs you may need `dbus-x11`. Verify:
`pacman -Ql dbus | grep activation` or `dpkg -L dbus-x11 | grep activation`.

**`systemctl --user import-environment` has no effect**
This means the systemd user session is not running (rare on modern systems).
Check: `systemctl --user status`. If it shows `State: degraded` or is not
running, check PAM configuration — `pam_systemd.so` must be in the login PAM
stack to start the user session.

**Portal backend crashes immediately**
Usually caused by `WAYLAND_DISPLAY` not being set at the time the backend starts.
Verify with `journalctl --user -u xdg-desktop-portal-hyprland -n 50`. If you see
"failed to connect to Wayland display", the backend started before your propagation
commands ran. Either reorder exec-once or migrate to systemd target ordering.

**PipeWire starts but apps see no audio**
WirePlumber is the session manager that connects applications to PipeWire. Without
it, PipeWire runs but does nothing. Check: `systemctl --user status wireplumber`.
If it failed, check for `~/.local/state/wireplumber/` for state corruption:
`rm -rf ~/.local/state/wireplumber && systemctl --user restart wireplumber`.

**polkit agent does not appear for sudo operations**
Multiple polkit agents cannot run simultaneously. Check for a pre-existing agent:
`pgrep -a polkit`. If `gnome-shell` or `plasma-pa` is running, they embed their
own agents and your exec-once agent will silently fail to register. Remove the
duplicate or use a different agent compatible with your environment.

**Screen sharing black in browsers (Chrome/Firefox)**
This is almost always a portal issue. Verify: `busctl --user call org.freedesktop.portal.Desktop /org/freedesktop/portal/desktop org.freedesktop.portal.ScreenCast GetAvailableCursorModes u 0` — if this returns a number, the portal is functional. If it fails, the portal is not running or not on D-Bus. Also check that `XDPW_SCD_DMABUF_ENABLED=1` is not set for non-dmabuf hardware.

**exec-once commands not running at all**
Check Hyprland log: `cat /tmp/hypr/$(ls -t /tmp/hypr/ | head -1)/hyprland.log | grep -i exec`.
Missing binary in PATH is the most common cause; remember that Hyprland's PATH
is the login shell PATH, not your interactive shell PATH. Use absolute paths for
binaries not guaranteed to be in the login PATH.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
