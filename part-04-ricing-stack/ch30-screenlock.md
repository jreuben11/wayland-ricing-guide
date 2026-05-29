# Chapter 30 — Screen Locking: hyprlock, swaylock, gtklock

## Overview

Screen locking is one of the most security-sensitive aspects of a desktop environment, and Wayland's protocol design makes it fundamentally more robust than anything achievable on X11. On X11, any sufficiently privileged process could theoretically draw over a lock screen or intercept input; on Wayland, the compositor itself enforces the locked state at the protocol level, making bypass attacks structurally impossible without exploiting the compositor binary itself.

The `ext-session-lock-v1` protocol, ratified and merged into the Wayland protocols repository, is the canonical interface for session locking on Wayland. When a lock client requests a session lock, the compositor grants exclusive control of all outputs and blocks all input routing to other clients until the lock is explicitly unlocked or the locker crashes. Crash recovery is specified in the protocol: the compositor may choose to remain locked if the locker dies unexpectedly, preventing a forced-crash bypass.

This chapter covers the three dominant screen lockers in active use — hyprlock, swaylock, and gtklock — along with their idle management companions (hypridle and swayidle), DPMS control, and advanced patterns like per-application idle inhibition. Whether you are on a wlroots compositor, Hyprland specifically, or something else, you will find a solution here. For session startup configuration that launches these daemons at login, see Ch 53. For integrating lock state with status bars, see Ch 26 (Waybar, eww, AGS/Astal).

---

## 30.1 The Session Lock Protocol

The `ext-session-lock-v1` protocol is the result of collaboration between the sway, Hyprland, and KDE communities and supersedes the earlier and less secure `zwlr_input_inhibitor_v1` approach. Understanding the protocol is important for anyone who wants to write a custom locker, audit security guarantees, or debug locking failures.

When a locker calls `ext_session_lock_manager_v1::lock`, the compositor creates an `ext_session_lock_v1` object and, if successful, sends the `locked` event. From that moment, the compositor routes all keyboard/pointer/touch input exclusively to surfaces created by the locker via `get_lock_surface`. The locker is responsible for covering every output with a lock surface; the compositor will not render anything beneath an uncovered output. If the locker exits without calling `unlock_and_destroy`, a compliant compositor keeps the session locked indefinitely — this is the crash-safe design.

The older `zwlr_input_inhibitor_v1` protocol only inhibited input but did not create exclusive surfaces, meaning the desktop was still visible behind the locker window. It is deprecated and should not be used in new tooling.

Security comparison with X11 lockers is stark. On X11, `xscreensaver`, `i3lock`, and `slock` all relied on `XGrabKeyboard`/`XGrabPointer`, which could be defeated by sending synthetic events, by VT-switching (on some configurations), or by killing the locker process and having the desktop immediately accessible. On Wayland, killing the locker process leaves the screen locked by the compositor. There is no equivalent of the X11 override-redirect trick.

| Feature                         | `ext-session-lock-v1` | `zwlr_input_inhibitor_v1` | X11 (XGrab)    |
|---------------------------------|----------------------|---------------------------|----------------|
| Compositor-enforced lock        | Yes                  | Partial                   | No             |
| Crash-safe (stays locked)       | Yes (compositor opt) | No                        | No             |
| Exclusive output surfaces       | Yes                  | No                        | No             |
| Input blocked outside locker    | Yes                  | Yes                       | Partial        |
| Standardized across compositors | Yes                  | Yes (wlroots only)        | N/A            |

To inspect which protocol is in use by a running locker, you can use `wayland-spy` or enable protocol logging in your compositor. In Hyprland:

```bash
# Enable protocol debug logging (verbose)
HYPRLAND_LOG_WLR=1 Hyprland 2>&1 | grep -i "session_lock"
```

For wlroots compositors, the `wlr-session-lock-v1` implementation predates the standardized protocol. Most modern compositors now support both, but prefer `ext-session-lock-v1`.

---

## 30.2 hyprlock — GPU-Accelerated and Beautiful

hyprlock is the native lockscreen for Hyprland, written by vaxerski (the Hyprland author). It is implemented as a standalone binary that uses the `ext-session-lock-v1` protocol and renders via OpenGL, leveraging Hyprland's rendering infrastructure for smooth animations, blurs, and shader effects. It is the recommended choice for Hyprland users and one of the most visually capable lockers available on any platform.

Configuration lives at `~/.config/hypr/hyprlock.conf` and uses hyprlang, the same configuration language as `hyprland.conf`. The top-level stanzas are `general`, `background`, `image`, `label`, `input-field`, and `shape`. Each visual element is positioned absolutely or with anchored offsets, and multiple monitors are handled automatically — each output gets its own lock surface with independent rendering.

### Installation

```bash
# Arch Linux
sudo pacman -S hyprlock hypridle

# From source (requires hyprland-protocols, wayland-protocols)
git clone https://github.com/hyprwm/hyprlock
cd hyprlock
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
sudo cmake --install build
```

### Basic Configuration

```ini
# ~/.config/hypr/hyprlock.conf

general {
    disable_loading_bar = false
    hide_cursor = true
    grace = 0          # seconds before lock takes effect (useful for testing)
    no_fade_in = false
}

background {
    monitor =             # empty = all monitors
    path = ~/Pictures/wallpapers/lock.jpg
    blur_passes = 3
    blur_size = 7
    brightness = 0.5
    vibrancy = 0.1696
    vibrancy_darkness = 0.0
}

input-field {
    monitor =
    size = 300, 60
    outline_thickness = 3
    dots_size = 0.33
    dots_spacing = 0.15
    dots_center = true
    outer_color = rgb(151515)
    inner_color = rgb(200, 200, 200)
    font_color = rgb(10, 10, 10)
    fade_on_empty = true
    fade_timeout = 1000   # milliseconds
    placeholder_text = <i>Password...</i>
    hide_input = false
    rounding = -1         # -1 = fully rounded
    check_color = rgb(204, 136, 34)
    fail_color = rgb(204, 34, 34)
    fail_text = <i>$FAIL <b>($ATTEMPTS)</b></i>
    capslock_color = -1
    numlock_color = -1
    bothlock_color = -1
    invert_numlock = false

    position = 0, -20
    halign = center
    valign = center
}

label {
    monitor =
    text = $TIME
    color = rgba(200, 200, 200, 1.0)
    font_size = 72
    font_family = JetBrains Mono Nerd Font

    position = 0, 300
    halign = center
    valign = center
}

label {
    monitor =
    text = cmd[update:1000] date +"%A, %B %d"
    color = rgba(200, 200, 200, 0.7)
    font_size = 24
    font_family = JetBrains Mono Nerd Font

    position = 0, 220
    halign = center
    valign = center
}
```

### Dynamic Labels and Shell Commands

The `cmd[update:ms]` syntax in labels allows polling a shell command. This enables displaying battery percentage, network state, or custom status:

```ini
label {
    monitor =
    text = cmd[update:5000] bash -c "echo '  ' $(cat /sys/class/power_supply/BAT0/capacity)%"
    color = rgba(200, 200, 200, 0.8)
    font_size = 16
    font_family = JetBrains Mono Nerd Font
    position = -20, 20
    halign = right
    valign = top
}

label {
    monitor =
    text = cmd[update:30000] nmcli -t -f NAME,TYPE connection show --active | awk -F: 'NR==1{print $1}'
    color = rgba(200, 200, 200, 0.7)
    font_size = 14
    font_family = JetBrains Mono Nerd Font
    position = 20, 20
    halign = left
    valign = top
}
```

### Per-Monitor Backgrounds

For a multi-monitor setup where each screen should show a different background:

```ini
background {
    monitor = DP-1
    path = ~/Pictures/wallpapers/left-monitor.jpg
    blur_passes = 2
}

background {
    monitor = HDMI-A-1
    path = ~/Pictures/wallpapers/right-monitor.jpg
    blur_passes = 2
}
```

### Shape Elements

The `shape` stanza draws rectangles and rounded rectangles. Use these for card-style layouts around the clock or input field:

```ini
shape {
    monitor =
    size = 360, 90
    color = rgba(0, 0, 0, 0.5)
    rounding = 15
    border_size = 2
    border_color = rgba(255, 255, 255, 0.2)
    position = 0, -20
    halign = center
    valign = center
}
```

---

## 30.3 swaylock — The Standard

swaylock is the reference-quality screen locker for wlroots-based compositors. It is minimal, rock-solid, and highly portable — if your compositor implements `ext-session-lock-v1` or the older wlroots session lock, swaylock will work. It has none of hyprlock's visual flair by default, but the `swaylock-effects` fork adds blur, image support, and a clock indicator.

The configuration file at `~/.config/swaylock/config` mirrors the CLI flags exactly — any `--flag value` becomes `flag=value` in the file. This makes it easy to prototype on the command line and then commit a working config.

### Installation

```bash
# Arch Linux (mainline)
sudo pacman -S swaylock

# swaylock-effects (AUR — more visual features)
paru -S swaylock-effects

# swayidle (idle management companion)
sudo pacman -S swayidle
```

### Basic CLI Usage

```bash
# Solid color lock
swaylock -c 1e1e2e

# Image background (scaled and cropped)
swaylock -i ~/Pictures/wallpapers/lock.jpg --scaling fill

# Image with blur (swaylock-effects only)
swaylock -i ~/Pictures/wallpapers/lock.jpg --effect-blur 7x5

# Fork to background immediately
swaylock -f -c 1e1e2e

# Show typing indicator as circle
swaylock -f --indicator --indicator-radius 100 --indicator-thickness 7
```

### Configuration File

```ini
# ~/.config/swaylock/config

# Background
image=~/Pictures/wallpapers/lock.jpg
scaling=fill

# Colors — ring indicator
color=1e1e2e
ring-color=cba6f7
inside-color=1e1e2e
line-color=cba6f7
key-hl-color=a6e3a1
bs-hl-color=f38ba8
separator-color=00000000

# Verification state
ring-ver-color=89b4fa
inside-ver-color=1e1e2edd
line-ver-color=89b4fa

# Wrong password state
ring-wrong-color=f38ba8
inside-wrong-color=1e1e2edd
line-wrong-color=f38ba8
text-wrong-color=f38ba8

# Text
text-color=cdd6f4
text-ver-color=89b4fa

# Layout
indicator
indicator-radius=100
indicator-thickness=7

# Misc
font=JetBrains Mono Nerd Font
font-size=24
ignore-empty-password
show-failed-attempts
```

### swaylock-effects: Blur and Clock

With the `swaylock-effects` fork, additional visual capabilities are available:

```bash
# Pixelate the current desktop and show a clock
swaylock \
  --screenshots \
  --clock \
  --indicator \
  --indicator-radius 100 \
  --indicator-thickness 7 \
  --effect-blur 7x5 \
  --effect-vignette 0.5:0.5 \
  --grace 2 \
  --fade-in 0.2
```

```ini
# ~/.config/swaylock/config (swaylock-effects)
screenshots
clock
indicator
indicator-radius=100
indicator-thickness=7
effect-blur=7x5
effect-vignette=0.5:0.5
color=1e1e2e
font=JetBrains Mono Nerd Font
grace=2
fade-in=0.2
```

### swayidle Integration

swayidle monitors for user inactivity and dispatches commands at configurable timeouts. It uses the `ext-idle-notify-v1` or `org_kde_kwin_idle` protocols to receive idle notifications from the compositor without polling:

```bash
# ~/.config/sway/config (or launch from autostart)
exec swayidle -w \
    timeout 300  'swaylock -f' \
    timeout 600  'swaymsg "output * power off"' \
    resume       'swaymsg "output * power on"' \
    before-sleep 'swaylock -f'
```

For a standalone swayidle service (for non-sway wlroots compositors):

```ini
# ~/.config/systemd/user/swayidle.service
[Unit]
Description=Idle manager for Wayland
Documentation=man:swayidle(1)
PartOf=graphical-session.target
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/swayidle -w \
    timeout 300  'swaylock -f' \
    timeout 600  'wlr-randr --output DP-1 --off' \
    resume       'wlr-randr --output DP-1 --on' \
    before-sleep 'swaylock -f'
Restart=on-failure
RestartSec=1

[Install]
WantedBy=graphical-session.target
```

```bash
systemctl --user enable --now swayidle.service
```

---

## 30.4 gtklock — GTK-Based with Modules

gtklock is a screen locker written in C using GTK4. Its primary differentiator is a module system: shared libraries that add panels and widgets to the lock screen UI. Out of the box, you can display a media player controller, system information, and a power menu without writing custom code. If you are already invested in GTK theming (Adwaita, catppuccin-gtk), gtklock will inherit your color scheme automatically.

The configuration file uses INI syntax at `~/.config/gtklock/config.ini`. Modules are specified as paths to `.so` files compiled separately.

### Installation

```bash
# Arch Linux
sudo pacman -S gtklock

# Modules (AUR)
paru -S gtklock-playerctl-module gtklock-powerbar-module gtklock-userinfo-module
```

### Base Configuration

```ini
# ~/.config/gtklock/config.ini

[main]
time-format=%H:%M:%S
date-format=%A, %B %e
gtk-theme=Catppuccin-Mocha-Standard-Mauve-Dark
icon-theme=Papirus-Dark
modules=/usr/lib/gtklock/playerctl-module.so;/usr/lib/gtklock/userinfo-module.so

[playerctl]
# Show media controls for the active player
art-size=80

[userinfo]
# Show avatar and username in the top panel
```

### CSS Theming

gtklock exposes widget names and CSS classes for full stylesheet control:

```css
/* ~/.config/gtklock/style.css */

window {
    background-image: url("/home/user/Pictures/wallpapers/lock.jpg");
    background-size: cover;
}

#clock-label {
    font-family: "JetBrains Mono Nerd Font";
    font-size: 72px;
    font-weight: bold;
    color: rgba(205, 214, 244, 1.0);
    text-shadow: 2px 2px 8px rgba(0,0,0,0.8);
}

#date-label {
    font-family: "JetBrains Mono Nerd Font";
    font-size: 24px;
    color: rgba(205, 214, 244, 0.7);
}

#input-field {
    background-color: rgba(30, 30, 46, 0.8);
    border: 2px solid rgba(203, 166, 247, 0.6);
    border-radius: 12px;
    padding: 8px 16px;
    color: #cdd6f4;
    font-family: "JetBrains Mono Nerd Font";
    font-size: 18px;
}

#input-field:focus {
    border-color: rgba(166, 227, 161, 1.0);
}
```

To apply the stylesheet:

```bash
gtklock --style ~/.config/gtklock/style.css
```

Or in `config.ini`:

```ini
[main]
style=/home/user/.config/gtklock/style.css
```

### Launching gtklock with Modules at Runtime

```bash
gtklock \
    --style ~/.config/gtklock/style.css \
    --modules /usr/lib/gtklock/playerctl-module.so \
    --modules /usr/lib/gtklock/powerbar-module.so
```

The powerbar module adds shutdown/reboot/suspend buttons directly on the lock screen, useful on devices where you want to power off without unlocking.

---

## 30.5 Quickshell Lockscreen (See Ch 24)

Quickshell (covered in depth in Ch 24) can implement a full lockscreen using QML and PAM integration. This is the most flexible option — you can build any UI imaginable — but it requires more configuration work than the dedicated tools above. The key integration point is the `Quickshell.Wayland.SessionLock` component, which wraps `ext-session-lock-v1`.

The tradeoffs vs. dedicated lockers:

| Criterion             | hyprlock        | swaylock        | gtklock         | Quickshell      |
|-----------------------|-----------------|-----------------|-----------------|-----------------|
| Visual flexibility    | High            | Low-Medium      | Medium          | Unlimited       |
| Setup complexity      | Low             | Very Low        | Low-Medium      | High            |
| Module ecosystem      | None            | None            | Good            | DIY             |
| Multi-monitor support | Automatic       | Automatic       | Automatic       | Manual          |
| Compositor dependency | Hyprland ideal  | wlroots         | Any             | Any             |
| GTK theme integration | No              | No              | Yes             | No              |

For most users, the dedicated tools are preferable. Quickshell shines when you want deeply integrated status information (live system metrics, custom animations) on the lock screen and are already using it as your shell framework.

---

## 30.6 Idle Management

Idle management on Wayland is handled by daemon processes that listen for compositor-reported inactivity via the `ext-idle-notify-v1` protocol (or the older `org_kde_kwin_idle`). These daemons fire shell commands at configurable timeouts, enabling patterns like: lock after 5 minutes, blank after 10 minutes, suspend after 30 minutes.

### hypridle

hypridle is the Hyprland-ecosystem idle daemon. Its configuration uses hyprlang and lives at `~/.config/hypr/hypridle.conf`:

```ini
# ~/.config/hypr/hypridle.conf

general {
    lock_cmd = pidof hyprlock || hyprlock       # run hyprlock, skip if already running
    before_sleep_cmd = loginctl lock-session    # lock before suspend
    after_sleep_cmd = hyprctl dispatch dpms on  # turn screens on after wake
}

listener {
    timeout = 150                               # 2.5 min: dim the screen
    on-timeout = brightnessctl -s set 10
    on-resume = brightnessctl -r
}

listener {
    timeout = 300                               # 5 min: lock
    on-timeout = loginctl lock-session
    on-resume = notify-send -t 3000 "Welcome back, $USER"
}

listener {
    timeout = 380                               # ~6 min: turn off screen
    on-timeout = hyprctl dispatch dpms off
    on-resume = hyprctl dispatch dpms on
}

listener {
    timeout = 1800                              # 30 min: suspend
    on-timeout = systemctl suspend
}
```

Launch hypridle as a systemd user service:

```ini
# ~/.config/systemd/user/hypridle.service
[Unit]
Description=Hyprland Idle Daemon
Documentation=https://wiki.hyprland.org/Hypr-Ecosystem/hypridle/
PartOf=graphical-session.target
After=graphical-session.target

[Service]
ExecStart=/usr/bin/hypridle
Restart=on-failure
RestartSec=1

[Install]
WantedBy=graphical-session.target
```

```bash
systemctl --user enable --now hypridle.service
```

### swayidle (Non-Hyprland)

On sway or other wlroots compositors, use swayidle. The syntax is event-driven rather than configuration-file-based:

```bash
swayidle -w \
    timeout 150  'brightnessctl -s set 10' \
    resume       'brightnessctl -r' \
    timeout 300  'swaylock -f' \
    timeout 380  'swaymsg "output * power off"' \
    resume       'swaymsg "output * power on"' \
    timeout 1800 'systemctl suspend' \
    before-sleep 'swaylock -f'
```

Wrap this in a systemd unit as shown in section 30.3.

### Idle Inhibition

Some applications (video players, presentations) should prevent the screen from blanking. Wayland provides `zwp_idle_inhibit_manager_v1` for this. Most Wayland-native applications (mpv, vlc, firefox during video playback) already use it. You can also inhibit manually:

```bash
# Install wayland-utils or systemd-inhibit equivalent
# Using wayland-idle-inhibit (from wl-utils or dedicated package)
wayland-idle-inhibit sleep 3600  # inhibit for 1 hour

# For mpv: add to ~/.config/mpv/mpv.conf
# mpv handles idle inhibition automatically on Wayland
wayland-idle-inhibit=yes
```

To check which applications are currently inhibiting idle:

```bash
# With Hyprland
hyprctl clients | grep -A5 "inhibit"

# Generic: check compositor debug output
WAYLAND_DEBUG=1 hyprlock 2>&1 | grep idle_inhibit
```

### `loginctl lock-session` vs Direct Locker

A best practice is to trigger locking via `loginctl lock-session` rather than calling the locker directly. This sends the `org.freedesktop.login1.Session.Lock` D-Bus signal, which logind intercepts. Your locker daemon should listen for this signal (hyprlock and swaylock both support `--lock-cmd` in conjunction with `pam_systemd`). This avoids race conditions and ensures the session is marked locked in the systemd session state:

```bash
# Check lock state
loginctl show-session $(loginctl | grep $(whoami) | awk '{print $1}') | grep LockedHint
```

---

## 30.7 DPMS and Screen Blanking

DPMS (Display Power Management Signaling) allows the compositor to command the display to enter low-power states. On Wayland, this is done via compositor-specific APIs rather than the X11 `xset dpms` command.

### Hyprland

```bash
# Turn off all outputs immediately
hyprctl dispatch dpms off

# Turn on all outputs
hyprctl dispatch dpms on

# Turn off a specific monitor
hyprctl dispatch dpms off DP-1

# Query current DPMS state
hyprctl monitors | grep -i dpms
```

To set automatic DPMS timeout in Hyprland (without hypridle):

```ini
# ~/.config/hypr/hyprland.conf
misc {
    mouse_move_enables_dpms = true
    key_press_enables_dpms = true
}

# Use hypridle instead for full control (preferred)
```

### wlroots / sway

```bash
# sway: power off all outputs
swaymsg "output * power off"
swaymsg "output * power on"

# wlr-randr (any wlroots compositor)
wlr-randr --output DP-1 --off
wlr-randr --output DP-1 --on
```

### Preventing Blanking During Presentations

The canonical approach is to use `wayland-idle-inhibit` or ensure your presentation software uses the idle inhibit protocol. For tools that don't, use a manual inhibitor:

```bash
# Keep display alive for the duration of a command
wayland-idle-inhibit -- libreoffice --impress presentation.pptx

# Or as a background process, killed manually
wayland-idle-inhibit &
INHIBIT_PID=$!
# ... give presentation ...
kill $INHIBIT_PID
```

In Hyprland, you can also bind a key to toggle DPMS:

```ini
# ~/.config/hypr/hyprland.conf
bind = $mainMod SHIFT, P, exec, hyprctl dispatch dpms off
bind = $mainMod SHIFT, O, exec, hyprctl dispatch dpms on
```

### wlr-output-power-management Protocol

The `zwlr_output_power_management_v1` protocol is the wlroots interface for output power state. Tools like `wlopm` expose it directly:

```bash
# Install wlopm
paru -S wlopm

# Turn off all outputs
wlopm --off '*'

# Turn on all outputs
wlopm --on '*'

# Toggle specific output
wlopm --toggle DP-1
```

This is particularly useful in scripts that need fine-grained output control without depending on compositor-specific commands.

---

## 30.8 Locking on Suspend and Before Sleep

A critical security requirement is locking the screen before the machine suspends, so that the session is not accessible when the lid is opened on a laptop. This is handled differently depending on the init system.

### systemd-inhibit + logind

systemd's logind can execute a lock command before sleep by listening on the `PrepareForSleep` signal. hypridle and swayidle handle this via `before-sleep`. For a manual implementation:

```bash
# /etc/systemd/system/lock-on-sleep@.service
[Unit]
Description=Lock screen before sleep for user %i
Before=sleep.target

[Service]
User=%i
Type=oneshot
ExecStart=/usr/bin/loginctl lock-session

[Install]
WantedBy=sleep.target
```

Or using `systemd-inhibit` in a user service:

```ini
# ~/.config/systemd/user/lock-on-sleep.service
[Unit]
Description=Lock on sleep
Before=sleep.target
StopWhenUnneeded=yes

[Service]
Type=oneshot
ExecStart=/usr/bin/swaylock -f
ExecStartPost=/usr/bin/sleep 1

[Install]
WantedBy=sleep.target
```

### PAM Configuration

Screen lockers use PAM for authentication. The relevant PAM service is typically `swaylock` or `hyprlock`. Verify your PAM config is in place:

```bash
# Should exist for swaylock
ls /etc/pam.d/swaylock

# If missing (Arch), the package installs it; otherwise create:
cat /etc/pam.d/swaylock
# auth include login
```

For fingerprint authentication integration (fprintd):

```
# /etc/pam.d/swaylock (with fingerprint)
auth sufficient pam_fprintd.so
auth include login
```

```
# /etc/pam.d/hyprlock (with fingerprint)
auth sufficient pam_fprintd.so
auth include system-auth
```

---

## Troubleshooting

### hyprlock / swaylock fails to lock — "session lock not supported"

Check that your compositor supports `ext-session-lock-v1`:

```bash
# List advertised globals
wayland-info | grep -i session_lock

# Or use weston-info
weston-info 2>/dev/null | grep session
```

If the protocol is absent, your compositor version may predate support. Update the compositor or use `swaylock` with the older `zwlr_input_inhibitor_v1` path if available.

### Lock screen appears but input is not captured

This usually means the locker created its surface before receiving the `locked` event. Check the locker's output for protocol errors:

```bash
WAYLAND_DEBUG=1 swaylock -f 2>&1 | grep -E "error|locked"
```

### hyprlock exits immediately / crashes on startup

Verify that hyprlock's OpenGL requirements are met:

```bash
# Check OpenGL renderer
glxinfo | grep "OpenGL renderer"
# Or for Wayland-native GL
eglinfo | head -20

# hyprlock requires EGL + OpenGL 3.3+
# If using a VM, ensure 3D acceleration is enabled
```

Check for config parse errors:

```bash
hyprlock --config ~/.config/hypr/hyprlock.conf 2>&1
```

### swayidle / hypridle not triggering

Confirm the idle notification protocol is available:

```bash
wayland-info | grep -i idle
# Should show: ext_idle_notify_v1 or org_kde_kwin_idle
```

Check that the service is running and connected to the correct `WAYLAND_DISPLAY`:

```bash
systemctl --user status hypridle.service
# Look for: WAYLAND_DISPLAY=wayland-1 (or wayland-0)
```

If hypridle was started before the compositor set `WAYLAND_DISPLAY`, it won't connect. Ensure the service has `After=graphical-session.target` and that the target is reached:

```bash
systemctl --user status graphical-session.target
```

### Screen does not lock before suspend

Check that the before-sleep handler is firing:

```bash
# Test: manually trigger the suspend signal (does not actually suspend)
journalctl --user -u hypridle -f &
systemd-inhibit --what=sleep --who=test --why=test --mode=block sleep 5
```

Verify `loginctl lock-session` works:

```bash
loginctl lock-session
# Should immediately lock the screen if the locker is running
```

### gtklock modules not loading

Module `.so` files must match the gtklock ABI version. After updating gtklock, reinstall modules:

```bash
paru -S gtklock-playerctl-module gtklock-powerbar-module
# Verify the .so exists
ls /usr/lib/gtklock/
```

Run gtklock from terminal to see module load errors:

```bash
gtklock --modules /usr/lib/gtklock/playerctl-module.so 2>&1
```

---

## Summary

| Tool       | Best For                              | Config Location                        | Compositor       |
|------------|---------------------------------------|----------------------------------------|------------------|
| hyprlock   | Hyprland, GPU effects, dynamic labels | `~/.config/hypr/hyprlock.conf`         | Hyprland         |
| swaylock   | Any wlroots compositor, reliability   | `~/.config/swaylock/config`            | sway, wlroots    |
| gtklock    | GTK theme integration, modules        | `~/.config/gtklock/config.ini`         | Any              |
| Quickshell | Fully custom QML lockscreen           | QML files (see Ch 24)                  | Any              |
| hypridle   | Idle management for Hyprland          | `~/.config/hypr/hypridle.conf`         | Hyprland         |
| swayidle   | Idle management for wlroots           | CLI / systemd unit                     | sway, wlroots    |

For session startup integration that ensures your idle daemon and locker are launched correctly at login, see Ch 53. For status bar indicators that reflect lock/idle state, see Ch 26 (Waybar, eww, AGS/Astal). For PAM and authentication hardening beyond screen locking, see Ch 55 (Security Hardening).

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
