# Chapter 60 — Night Light and Color Temperature: wlsunset, gammastep, hyprsunset

## Overview
Reducing blue light in the evening improves sleep. Wayland's gamma control protocol
enables f.lux/Redshift equivalents. This chapter covers all tools and their
integration with the rest of the rice.

## Sections

### 60.1 The Gamma Control Protocol
- `zwlr-gamma-control-unstable-v1`: wlroots protocol for setting gamma curves per output
- `wp-color-management-v1`: newer standard (2024+, KWin focus initially)
- Most tools use the wlr protocol — works with Hyprland, Sway, river, labwc, niri

### 60.2 wlsunset — Location-Based Automatic Dimming

**Installation:**
```bash
sudo pacman -S wlsunset
```

**Usage:**
```bash
# By latitude/longitude (Berlin example)
wlsunset -l 52.5 -L 13.4

# Manual temperature range
wlsunset -t 3500 -T 6500  # night: 3500K, day: 6500K
```

**Autostart:**
```conf
# hyprland.conf
exec-once = wlsunset -l 52.5 -L 13.4 -t 3000 -T 6500
```

**With geoclue2 (automatic location):**
```bash
sudo pacman -S geoclue
systemctl --user enable --now geoclue
# Then wlsunset picks up location automatically
wlsunset  # no flags needed
```

### 60.3 gammastep — Redshift for Wayland

gammastep is the direct Wayland successor to Redshift:

**Installation:**
```bash
sudo pacman -S gammastep
# or: gammastep-git from AUR
```

**Config:** `~/.config/gammastep/config.ini`
```ini
[general]
location-provider=manual
adjustment-method=wayland

[manual]
lat=52.5
lon=13.4

[temperature]
day=6500
night=3500

[brightness]
day=1.0
night=0.8

[gamma]
day=0.9
night=0.9
```

**Autostart:**
```bash
exec-once = gammastep-indicator  # system tray icon + daemon
# or without tray:
exec-once = gammastep
```

### 60.4 hyprsunset — Hyprland-Native

Hyprland's official color temperature tool:

```bash
sudo pacman -S hyprsunset  # or AUR: hyprsunset-git
```

```conf
# hyprland.conf
exec-once = hyprsunset -t 3000  # target night temperature

# Control via hyprctl
bind = SUPER SHIFT, N, exec, hyprctl keyword misc:hyprsunset_temp 3000
```

Or daemon mode with sunrise/sunset:
```bash
hyprsunset --latitude 52.5 --longitude 13.4
```

### 60.5 Manual Gamma Adjustment

For quick ad-hoc gamma tweaks:
```bash
# wlr-randr gamma (per output)
wlr-randr --output DP-1 --custom-mode 1920x1080@60Hz  # no gamma CLI directly

# Better: use gammastep one-shot
gammastep -O 4000  # set to 4000K and exit (stays set)
gammastep -x       # reset to default
```

### 60.6 Quickshell Night Light Integration
```qml
// Read current temperature and provide toggle
Process {
    id: gammastep
    command: ["gammastep", "-l", "52.5:13.4"]
    onRunningChanged: if (!running) running = true   // restart if crashes
}

// Toggle with a bar button
Button {
    text: nightLightActive ? "🌙" : "☀️"
    onClicked: {
        nightLightActive = !nightLightActive
        if (nightLightActive) gammastep.running = true
        else {
            gammastep.running = false
            // Reset gamma
            Process { command: ["gammastep", "-x"]; running: true }
        }
    }
}
```

### 60.7 Temperature Reference
| Temperature | Description | Use case |
|------------|-------------|----------|
| 6500K | Daylight (no filter) | Daytime, color work |
| 5500K | Cloudy day | Reduced blue, still bright |
| 4500K | Incandescent | Evening |
| 3500K | Warm lamp | Night |
| 2700K | Candlelight | Very late night |

### 60.8 Integration with Idle Daemon

```conf
# hypridle.conf — ramp temperature with idle time
listener {
    timeout = 1800        # 30 min
    on-timeout = hyprsunset -t 3000
    on-resume = hyprsunset -t 6500
}
```

### 60.9 HDR and Color Temperature
- HDR displays: color temperature tools may not work correctly via `wp-color-management-v1`
- KWin: built-in night light in system settings (full HDR-aware)
- Hyprland HDR: hyprsunset compatibility is compositor-version dependent
