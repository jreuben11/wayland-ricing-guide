# Chapter 30 — Screen Locking: hyprlock, swaylock, gtklock

## Overview
Screen lockers on Wayland use the `ext-session-lock-v1` protocol to cover all
outputs and prevent access until authenticated. Compositor-enforced means no
bypass attacks possible.

## Sections

### 30.1 The Session Lock Protocol
- `ext-session-lock-v1`: standardized, supported by all major compositors
- `zwlr_input_inhibitor_v1`: older alternative, less secure
- How compositor enforcement works: protocol-level, not app-level
- Security vs. X11: why Wayland lockers are fundamentally more secure

### 30.2 hyprlock — GPU-Accelerated and Beautiful
- Hyprland's native lockscreen
- Config: `~/.config/hypr/hyprlock.conf` (hyprlang)
- Shapes: `background`, `image`, `label`, `input-field`, `shape`
- Background options: path, color, blur (sigma, passes)
- Input field: customizable password box
- Label: supports `$TIME`, `$DATE`, `$USER`, custom shell commands
- Animations via Hyprland's animation engine
- Multi-monitor: automatic per-output surfaces
- `hypridle` integration for auto-lock

### 30.3 swaylock — The Standard
- Simple, reliable, works on any wlroots compositor
- CLI flags for configuration or `~/.config/swaylock/config`
- Basic options: `--color`, `--image`, `--blur`, `--indicator`
- `swaylock-effects` fork: blur, image, clock display
- `swayidle` integration:
  ```
  swayidle -w \
    timeout 300 'swaylock -f -c 000000' \
    timeout 600 'swaymsg "output * dpms off"' \
    resume 'swaymsg "output * dpms on"'
  ```

### 30.4 gtklock — GTK-Based with Modules
- GTK4 lockscreen with module system
- Modules: clock, playerctl (media controls), user-info, power-bar
- CSS theming with GTK CSS
- `gtklock-config.ini` configuration
- `gtklock-playerctl-module.so`: control music while locked

### 30.5 Quickshell Lockscreen (Chapter 24 Recap)
- Full QML freedom for lockscreen design
- PAM integration
- Quickshell lockscreen vs. dedicated tools: tradeoffs

### 30.6 Idle Management
- `hypridle` config:
  ```
  listener {
      timeout = 300
      on-timeout = hyprlock
      on-resume = notify-send "Welcome back"
  }
  listener {
      timeout = 600
      on-timeout = hyprctl dispatch dpms off
      on-resume = hyprctl dispatch dpms on
  }
  ```
- `swayidle` equivalent for non-Hyprland setups
- `wayland-idle-inhibit`: per-app inhibition (video players)
- `xdg-desktop-portal` idle inhibit integration

### 30.7 DPMS and Screen Blanking
- `hyprctl dispatch dpms off/on`
- `wlr-output-power-management-unstable-v1` protocol
- Preventing screen blank during presentations
