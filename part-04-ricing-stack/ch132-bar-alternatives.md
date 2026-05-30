# Chapter 132 — Bar Alternatives: yambar, sfwbar, HEMBar, i3status-rust

## Contents

- [Overview](#overview)
- [132.1 Comparison Table](#1321-comparison-table)
- [132.2 yambar](#1322-yambar)
  - [Installation](#installation)
  - [Config Structure](#config-structure)
  - [Module Reference](#module-reference)
  - [Particles (rendering primitives)](#particles-rendering-primitives)
  - [Running yambar](#running-yambar)
- [132.3 sfwbar](#1323-sfwbar)
  - [Installation](#installation)
  - [Config File](#config-file)
  - [Running sfwbar](#running-sfwbar)
- [132.4 HEMBar](#1324-hembar)
  - [Installation](#installation)
  - [Config Structure](#config-structure)
- [132.5 i3status-rust](#1325-i3status-rust)
  - [Installation](#installation)
  - [Config](#config)
  - [Integrating with Sway](#integrating-with-sway)
- [132.6 When to Choose Each Bar](#1326-when-to-choose-each-bar)
- [132.7 Script Module Pattern (all bars)](#1327-script-module-pattern-all-bars)

---


## Overview

Waybar dominates the Wayland bar ecosystem, but it is not the only option. `yambar` offers a declarative particle-based model that composes complex modules from primitives. `sfwbar` takes an S-expression config and targets Sway-family compositors. `HEMBar` is a newer Rust/GTK4 bar optimized for Hyprland. `i3status-rust` implements the i3bar JSON protocol and works with any compositor that has i3bar support. This chapter covers installation, configuration, and a comparison to help you choose.

**Cross-references:** Ch 26 — bars and panels (Waybar, eww comparison). Ch 104 — Waybar CSS deep dive. Ch 115 — nwg-shell (nwg-panel alternative). Ch 108 — eww deep dive.

---

## 132.1 Comparison Table

| Feature | Waybar | yambar | sfwbar | HEMBar | i3status-rust |
|---|---|---|---|---|---|
| Language | C++ | C | C | Rust | Rust |
| Config format | JSON + CSS | YAML | S-expressions | TOML/JSON | TOML |
| Toolkit | GTK3 | cairo | GTK3 | GTK4 | (backend only) |
| Wayland | Yes | Yes | Yes | Yes | i3bar protocol |
| Custom modules | Script / IPC | Script + event | Script / IPC | DBUS + script | IPC blocks |
| Multi-monitor | Yes | Yes | Yes | Yes | Yes |
| MPRIS | Plugin | Module | Module | Module | Block |
| Hot-reload | `pkill -SIGUSR2` | Restart | `SIGHUP` | Restart | Restart |
| Theme integration | CSS | YAML colors | GTK CSS | GTK4 CSS | Pango markup |
| Best for | General Wayland | Precise control | Sway | Hyprland | i3bar compositors |

---

## 132.2 yambar

`yambar` is a modular, declarative bar written in C. Its key concept is **particles** — composable rendering primitives (text, progress bars, decoration lines) that modules emit. This gives fine-grained control over how information is displayed without writing custom widgets.

### Installation

```bash
# Arch AUR
yay -S yambar

# From source
git clone https://codeberg.org/dnkl/yambar
mkdir -p yambar/build
cd yambar && meson setup build --buildtype=release
ninja -C build
sudo ninja -C build install
```

### Config Structure

```yaml
# ~/.config/yambar/config.yml

# Color palette
colors: &colors
  bg:       "1a1b26ff"   # Tokyo Night bg (RRGGBBAA)
  fg:       "a9b1d6ff"
  blue:     "7aa2f7ff"
  purple:   "bb9af7ff"
  green:    "9ece6aff"
  red:      "f7768eff"
  border:   "292e42ff"

bar:
  height: 36
  location: top
  background: *{colors.bg}
  border:
    width: 0
    bottom: 1
    color: *{colors.border}

  left:
    - tag: &tag_style
        foreground: *{colors.blue}
        tag: workspaces            # compositor workspace integration

  center:
    - clock:
        time-format: "%H:%M"
        date-format: "%a %d %b"
        left-spacing: 8
        right-spacing: 8
        content:
          - string:
              text: "{date}  {time}"
              font: "JetBrains Mono:size=11"
              foreground: *{colors.fg}

  right:
    - battery:
        name: BAT0
        content:
          map:
            tag: state
            values:
              discharging:
                - string:
                    text: "󰁹 {capacity}%"
                    foreground: *{colors.green}
              charging:
                - string:
                    text: "󰂄 {capacity}%"
                    foreground: *{colors.blue}
              full:
                - string:
                    text: "󰁹 Full"
                    foreground: *{colors.green}

    - cpu:
        poll-interval: 2000   # ms
        content:
          - string:
              text: " {mean:2}%"
              foreground: *{colors.fg}

    - mem:
        content:
          - string:
              text: " {used:mb:.0f}M"
              foreground: *{colors.fg}

    - alsa:
        card: default
        mixer: Master
        content:
          map:
            tag: muted
            values:
              true:
                - string: {text: "󰝟", foreground: *{colors.red}}
              false:
                - string: {text: "󰕾 {volume}%", foreground: *{colors.fg}}
```

### Module Reference

| Module | Key features |
|---|---|
| `clock` | Strftime format, timezone |
| `battery` | State (charging/discharging), capacity, time |
| `cpu` | Per-core, mean, load |
| `mem` | Used, available, percent |
| `alsa` | Volume, muted, per-card |
| `pipewire` | Volume via libpipewire |
| `network` | Interface state, TX/RX rates |
| `mpd` | MPD playback (title, artist, state) |
| `script` | Shell script output (polling or event) |
| `i3` / `sway` | Workspace integration |
| `river` | River tag integration |
| `niri` | Niri workspace integration |
| `removables` | USB drives |
| `xkb` | Keyboard layout indicator |

### Particles (rendering primitives)

```yaml
# Text
- string:
    text: "Hello {tag}"
    font: "Font Name:size=12"
    foreground: "ffffffff"

# Progress bar
- progress-bar:
    tag: volume
    width: 60
    foreground: "7aa2f7ff"
    background: "292e42ff"

# Horizontal list of particles
- list:
    spacing: 4
    items:
      - string: {text: "A"}
      - string: {text: "B"}

# Conditional
- map:
    tag: state
    values:
      active:   - string: {text: "Active", foreground: "9ece6aff"}
      inactive: - string: {text: "Idle",   foreground: "565f89ff"}

# Decoration: underline
- decorated:
    margin: 2
    foreground: "7aa2f7ff"
    underline:  {size: 2, color: "7aa2f7ff"}
    content:
      - string: {text: "Underlined"}
```

### Running yambar

```bash
# Start
yambar &

# Reload config
pkill -SIGHUP yambar

# Systemd user service
cat > ~/.config/systemd/user/yambar.service << 'EOF'
[Unit]
Description=yambar status bar
After=graphical-session.target

[Service]
ExecStart=%h/.local/bin/yambar-launch.sh
ExecReload=/usr/bin/pkill -SIGHUP yambar
Restart=on-failure

[Install]
WantedBy=graphical-session.target
EOF
```

---

## 132.3 sfwbar

`sfwbar` is a Sway-focused bar written in C with a compact S-expression config syntax. It integrates natively with Sway IPC and supports Wayland layer-shell.

### Installation

```bash
# Arch AUR
yay -S sfwbar

# From source
git clone https://github.com/LBCrion/sfwbar
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
sudo cmake --install build
```

### Config File

```
# ~/.config/sfwbar/sfwbar.config

Set Term = "foot"

Scanner {
  Exec("cat /proc/loadavg", NoGlob)
  File("/sys/class/power_supply/BAT0/capacity")
  File("/sys/class/power_supply/BAT0/status")
}

Layout {
  Style = "* { font-family: JetBrains Mono; font-size: 11pt; }"

  # Left: taskbar / window list
  TaskBar {
    Style = "* { min-width: 100px; }"
    Cols = 10
  }

  # Center: clock
  Label {
    Value = Time("%H:%M  %a %d %b")
    Style = "* { color: #a9b1d6; }"
  }

  # Right: battery + CPU
  Grid {
    Cols = 2

    Label {
      Value = Grab("/sys/class/power_supply/BAT0/capacity") + "%"
      Trigger = "interval(30)"
      Style = "* { color: #9ece6a; }"
    }

    Label {
      Value = Extract(Grab("cat /proc/loadavg"), " ", 1)
      Trigger = "interval(2)"
      Style = "* { color: #a9b1d6; }"
    }
  }
}

# Sway workspace switcher
SwitcherPanel {
  Cols = 10
  Filter = ".*"
  Action[1] = SwayCmd("workspace ", SwayWinTitle())
}
```

### Running sfwbar

```bash
# Launch
sfwbar &

# Reload
pkill -SIGHUP sfwbar

# Sway exec block
exec sfwbar
```

sfwbar's strength is tight Sway integration — it gets window list and workspace data directly from Sway IPC without external scripts.

---

## 132.4 HEMBar

HEMBar is a Rust/GTK4 bar aimed at Hyprland with a clean TOML config and built-in D-Bus integration for Hyprland events.

### Installation

```bash
# Arch AUR
yay -S hembar

# From source (requires Rust)
git clone https://github.com/elkowar/hembar   # check current URL
cargo build --release
install -Dm755 target/release/hembar ~/.local/bin/hembar
```

> Note: HEMBar is an emerging project; verify the GitHub URL and stability before use in production rices.

### Config Structure

```toml
# ~/.config/hembar/config.toml

[general]
height     = 36
location   = "top"
font       = "JetBrains Mono 11"
background = "#1a1b26"
foreground = "#a9b1d6"

[[left]]
type   = "workspaces"
active_fg   = "#7aa2f7"
inactive_fg = "#565f89"
urgent_fg   = "#f7768e"

[[center]]
type   = "clock"
format = "%H:%M  %a %d %b"
fg     = "#a9b1d6"

[[right]]
type   = "cpu"
format = " {usage:.0}%"
interval = 2

[[right]]
type   = "memory"
format = " {used_mb:.0}M"

[[right]]
type   = "battery"
charging_format    = "󰂄 {capacity}%"
discharging_format = "󰁹 {capacity}%"
full_format        = "󰁹 Full"
charging_fg    = "#7aa2f7"
discharging_fg = "#9ece6a"

[[right]]
type   = "volume"
format = "󰕾 {volume}%"
muted_format = "󰝟 Muted"
muted_fg = "#f7768e"

[[right]]
type   = "custom"
command  = "~/.local/bin/bar-mpris.sh"
interval = 5
format   = "{stdout}"
```

---

## 132.5 i3status-rust

`i3status-rust` is a Rust reimplementation of `i3status` that outputs the i3bar JSON protocol. Any compositor that reads i3bar JSON (Sway, i3, River with i3bar support) can use it as a bar backend.

### Installation

```bash
# Arch Linux
sudo pacman -S i3status-rust

# Cargo
cargo install i3status-rs
```

### Config

```toml
# ~/.config/i3status-rust/config.toml

[theme]
theme = "ctp-mocha"   # Catppuccin Mocha (built-in)
# Other built-ins: plain, solarized-dark, gruvbox-dark, native

[icons]
icons = "material-nf"   # Material Design Nerd Font icons

[[block]]
block = "focused_window"
format = " $title.str(max_w:50)|Missing "

[[block]]
block = "cpu"
interval = 2
format = " $barchart $utilization "

[[block]]
block = "memory"
format = " $mem_used.eng(prefix_si:true)/$mem_total.eng(prefix_si:true) "
interval = 5

[[block]]
block = "disk_space"
path = "/"
format = " $icon $available.eng(prefix_si:true) "
interval = 60

[[block]]
block = "net"
device = "wlan0"
format = " $icon {$signal_strength $ssid|Disconnected} "

[[block]]
block = "battery"
format = " $icon $percentage $time "
full_format = " $icon Full "

[[block]]
block = "sound"
format = " $icon {$volume.eng(w:2)|} "

[[block]]
block = "music"
format = " $icon {$title.str(max_w:25) - $artist.str(max_w:20)|No music} "
interface_name = "org.mpris.MediaPlayer2.spotify"

[[block]]
block = "time"
format = " $icon $timestamp.datetime(f:'%H:%M  %a %d %b') "
interval = 10
```

### Integrating with Sway

```bash
# ~/.config/sway/config
bar {
    status_command i3status-rs ~/.config/i3status-rust/config.toml
    font pango:JetBrains Mono 11
    colors {
        background #1a1b26
        focused_workspace  #7aa2f7 #7aa2f7 #1a1b26
        active_workspace   #292e42 #292e42 #a9b1d6
        inactive_workspace #1a1b26 #1a1b26 #565f89
    }
    position top
    height 36
}
```

For River (using `i3bar-river`):
```bash
# Install i3bar-river
yay -S i3bar-river

# In River init
riverctl spawn "i3bar-river -c ~/.config/i3status-rust/config.toml"
```

---

## 132.6 When to Choose Each Bar

| Scenario | Best choice | Why |
|---|---|---|
| Hyprland, want theming flexibility | Waybar | Widest plugin ecosystem, most community CSS |
| Want QML/reactive UI | eww or Quickshell | Proper widget model |
| Sway, want tight WM integration | sfwbar | Native Sway IPC, taskbar built-in |
| Precise rendering control | yambar | Particle system, no magic |
| Hyprland with GTK4 native | HEMBar | GTK4 rendering, Hyprland events |
| River or i3bar compositor | i3status-rust | Portable, excellent built-in modules |
| Minimal / terminal-only rice | i3status-rust | Low overhead, no GTK required |
| Learning / custom modules | yambar | Script module is simple and powerful |

---

## 132.7 Script Module Pattern (all bars)

All bars support running shell scripts for custom data. The pattern is the same:

```bash
# ~/.local/bin/bar-gpu-temp.sh
#!/bin/bash
# Output current GPU temperature for any bar's script module
TEMP=$(cat /sys/class/drm/card0/device/hwmon/hwmon*/temp1_input 2>/dev/null)
if [ -n "$TEMP" ]; then
    echo "󰻠 $((TEMP / 1000))°C"
else
    echo ""
fi
```

```yaml
# yambar script module
- script:
    path: ~/.local/bin/bar-gpu-temp.sh
    poll-interval: 5000
    content:
      - string: {text: "{stdout}"}
```

```bash
# sfwbar custom block
Label {
  Value = Exec("~/.local/bin/bar-gpu-temp.sh")
  Trigger = "interval(5)"
}
```

```toml
# i3status-rust custom block
[[block]]
block = "custom"
command = "~/.local/bin/bar-gpu-temp.sh"
interval = 5
```
