# Chapter 60 — Night Light and Color Temperature: wlsunset, gammastep, hyprsunset

## Contents

- [Overview](#overview)
- [The Wayland Gamma Control Protocol](#the-wayland-gamma-control-protocol)
  - [Protocol Landscape](#protocol-landscape)
  - [How Gamma Curves Work](#how-gamma-curves-work)
- [wlsunset — Location-Based Automatic Dimming](#wlsunset-location-based-automatic-dimming)
  - [Overview and Installation](#overview-and-installation)
  - [Basic Usage](#basic-usage)
  - [Autostart Integration](#autostart-integration)
  - [Automatic Location via GeoClue2](#automatic-location-via-geoclue2)
- [gammastep — Redshift for Wayland](#gammastep-redshift-for-wayland)
  - [Overview](#overview)
  - [Installation](#installation)
  - [Configuration](#configuration)
  - [Autostart](#autostart)
  - [One-Shot Manual Override](#one-shot-manual-override)
- [hyprsunset — Hyprland-Native](#hyprsunset-hyprland-native)
  - [Overview](#overview)
  - [Installation](#installation)
  - [Basic Usage and Configuration](#basic-usage-and-configuration)
  - [Hyprctl Runtime Control](#hyprctl-runtime-control)
- [Manual Gamma Adjustment](#manual-gamma-adjustment)
  - [wlr-randr and wl-gammarelay](#wlr-randr-and-wl-gammarelay)
  - [gammastep One-Shot (Recommended for Scripting)](#gammastep-one-shot-recommended-for-scripting)
- [Temperature Reference](#temperature-reference)
  - [Kelvin Scale and Use Cases](#kelvin-scale-and-use-cases)
  - [Choosing Your Temperatures](#choosing-your-temperatures)
- [Integration with Status Bars](#integration-with-status-bars)
  - [Waybar Integration](#waybar-integration)
  - [Quickshell Night Light Widget](#quickshell-night-light-widget)
- [Integration with Idle Daemon](#integration-with-idle-daemon)
  - [hypridle Temperature Ramping](#hypridle-temperature-ramping)
  - [swayidle Integration (Sway / river)](#swayidle-integration-sway-river)
- [HDR and Color Temperature Compatibility](#hdr-and-color-temperature-compatibility)
  - [Current Limitations](#current-limitations)
  - [KWin Built-In Night Light](#kwin-built-in-night-light)
- [Troubleshooting](#troubleshooting)
  - [Daemon Starts but Screen Does Not Change](#daemon-starts-but-screen-does-not-change)
  - [Tool Runs but Temperature Does Not Transition](#tool-runs-but-temperature-does-not-transition)
  - [gammastep Crashes at Startup](#gammastep-crashes-at-startup)
  - [Temperature Resets to 6500K Unexpectedly](#temperature-resets-to-6500k-unexpectedly)
  - [XWayland Applications Show Incorrect Colors](#xwayland-applications-show-incorrect-colors)

---


## Overview

Reducing blue light in the evening is one of the most impactful ergonomic tweaks available to a power user. Extended exposure to high-color-temperature light (5500K–6500K) in the hours before sleep suppresses melatonin production and disrupts circadian rhythms. On X11, tools like Redshift and f.lux solved this problem by adjusting the display gamma curves through the X RANDR extension. On Wayland, the equivalent protocol is `zwlr-gamma-control-unstable-v1`, a wlroots extension that gives privileged clients direct access to per-output gamma LUTs.

This chapter covers every major night-light tool available on Wayland as of 2025: `wlsunset` for minimal location-based adjustment, `gammastep` as the direct Redshift successor, `hyprsunset` for Hyprland-native control, and manual approaches via `wlr-randr`. It also covers geolocation via GeoClue2, desktop integration, HDR compatibility caveats, and scripted control through Quickshell and waybar.

Night light is not just aesthetics — it is part of your daily workflow. Integrating it cleanly with session startup (see Ch 53), idle management (see Ch 30), and your status bar (see Ch 45) turns a standalone tool into an ambient, automatic feature of your rice that you never have to think about again.

## The Wayland Gamma Control Protocol

### Protocol Landscape

Wayland separates display hardware control from the compositor protocol far more strictly than X11 did. Rather than every application being able to set gamma tables directly, Wayland uses privileged protocols that only a designated client (your night-light daemon) can access. Two protocols are relevant here:

`zwlr-gamma-control-unstable-v1` is the wlroots extension introduced alongside Sway. It allows a client to submit a per-output gamma LUT (Red/Green/Blue curves) to the compositor. The compositor applies this to the scanout pipeline before presenting frames to the display. This protocol is supported by Hyprland, Sway, river, labwc, niri, and most wlroots-derived compositors. It is **not** supported by KWin natively, though KWin has its own `wp-color-management-v1` path and built-in night light.

`wp-color-management-v1` is the newer Wayland standard that emerged from KWin and the broader Wayland protocol community in 2024. It provides richer color space management, ICC profile support, and HDR tone mapping. Night-light tools are beginning to adopt it, but as of early 2025 the majority still use the wlr protocol. If you run KWin (Plasma 6), use the built-in night light in System Settings rather than any of the external tools described here.

| Protocol | Compositors | HDR-safe | Tools |
|---|---|---|---|
| `zwlr-gamma-control-unstable-v1` | Hyprland, Sway, river, labwc, niri | No | wlsunset, gammastep, hyprsunset |
| `wp-color-management-v1` | KWin (Plasma 6+) | Yes | KWin built-in |
| X11 XRandR gamma | XWayland (indirect) | No | Redshift (legacy) |

### How Gamma Curves Work

A gamma LUT maps each input intensity value (0–1023 for 10-bit, 0–65535 for 16-bit) to an output value for each channel. By reducing the blue channel curve and shifting the red/green balance, you produce a warmer color temperature. The correlated color temperature (CCT) is measured in Kelvin: 6500K matches daylight, 3000K approximates warm incandescent light.

Most tools compute gamma LUTs using a standard blackbody radiation model. Given a target CCT in Kelvin, they compute the corresponding RGB scaling factors using either the Tanner Helland algorithm or a table-lookup approach. These factors are then applied as multiplicative adjustments across the full gamma LUT, not just a single brightness scalar.

Understanding this matters when diagnosing issues: if your night-light tool is not working, use `wl-gammarelay-rs` as a diagnostic proxy — it exposes a DBus interface and logs gamma changes, so you can confirm the compositor is accepting gamma table updates at all.

## wlsunset — Location-Based Automatic Dimming

### Overview and Installation

`wlsunset` is a minimal, zero-dependency night-light daemon for wlroots-based Wayland compositors. It takes latitude/longitude coordinates, queries system time to determine sunrise/sunset, and gradually transitions the screen color temperature between a daytime and nighttime value. It is the simplest tool to deploy and has almost no configuration surface — which is also its main limitation.

```bash
# Arch Linux
sudo pacman -S wlsunset

# Fedora / COPR
sudo dnf install wlsunset

# Ubuntu / Debian (build from source if not packaged)
sudo apt install build-essential meson ninja-build libwayland-dev
git clone https://git.sr.ht/~kennylevinsen/wlsunset
cd wlsunset && meson build && ninja -C build && sudo ninja -C build install
```

### Basic Usage

```bash
# By latitude/longitude (Berlin example)
wlsunset -l 52.5 -L 13.4

# Manual temperature range (no location needed)
wlsunset -t 3500 -T 6500  # night: 3500K, day: 6500K

# Override gamma value (default 1.0)
wlsunset -l 52.5 -L 13.4 -g 0.9

# Verbose mode for debugging
wlsunset -l 52.5 -L 13.4 -v
```

wlsunset transitions the color temperature smoothly over the 30-minute period around calculated sunrise and sunset. During daytime it applies the `-T` temperature (day temperature); during nighttime it applies the `-t` temperature. The `-g` flag sets gamma correction for both periods identically — useful for slightly reducing the eye strain even during the day.

### Autostart Integration

```ini
# ~/.config/hypr/hyprland.conf
exec-once = wlsunset -l 52.5 -L 13.4 -t 3000 -T 6500

# Sway: ~/.config/sway/config
exec wlsunset -l 52.5 -L 13.4 -t 3000 -T 6500

# Systemd user service (works for any compositor)
# ~/.config/systemd/user/wlsunset.service
```

```ini
# ~/.config/systemd/user/wlsunset.service
[Unit]
Description=wlsunset night light daemon
PartOf=graphical-session.target
After=graphical-session.target

[Service]
ExecStart=/usr/bin/wlsunset -l 52.5 -L 13.4 -t 3000 -T 6500
Restart=on-failure
RestartSec=3

[Install]
WantedBy=graphical-session.target
```

```bash
systemctl --user enable --now wlsunset.service
```

See Ch 53 for details on `graphical-session.target` and how to ensure Wayland environment variables are correctly inherited by systemd user services.

### Automatic Location via GeoClue2

GeoClue2 is a D-Bus location service that aggregates location data from WiFi geolocation, GPS, and IP-based lookups. wlsunset can query it automatically, eliminating the need to hardcode coordinates.

```bash
sudo pacman -S geoclue

# Enable the GeoClue system daemon
sudo systemctl enable --now geoclue

# Authorize wlsunset to access location (add to agent allow list)
# Edit /etc/geoclue/geoclue.conf and add under [wlsunset] section:
```

```ini
# /etc/geoclue/geoclue.conf  (add at end of file)
[wlsunset]
allowed=true
system=false
users=
```

```bash
# Now run without coordinates — GeoClue provides them
wlsunset
```

If GeoClue cannot determine your location (no GPS, WiFi disabled), it falls back to IP-based geolocation using Mozilla's location service. For privacy-conscious setups, you can install `geoclue-demo-agent` to manually approve each location request, or simply hardcode your coordinates and skip GeoClue entirely.

## gammastep — Redshift for Wayland

### Overview

`gammastep` is a direct fork of Redshift targeting Wayland via the `zwlr-gamma-control-unstable-v1` protocol. It supports the same INI configuration format as Redshift, making migration trivial. Where `wlsunset` is minimal, `gammastep` is configurable: per-period brightness adjustments, gamma correction, and multiple location providers including GeoClue2.

### Installation

```bash
# Arch Linux
sudo pacman -S gammastep

# Arch AUR (development builds)
yay -S gammastep-git

# Fedora
sudo dnf install gammastep gammastep-indicator

# Ubuntu 22.04+
sudo apt install gammastep gammastep-indicator
```

`gammastep-indicator` provides a system tray icon with a toggle and status display. On Wayland, this requires a tray-capable bar (Waybar with `tray` module, or a standalone tray daemon like `stalonetray` with XWayland).

### Configuration

```ini
# ~/.config/gammastep/config.ini

[general]
# Location provider: manual, geoclue2
location-provider=manual
# Adjustment method: wayland, drm, randr, vidmode
adjustment-method=wayland
# Transition speed: fast (5min), normal (30min), slow (60min)
# (gammastep uses its own internal curve — no direct speed setting)

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
# Applied on top of temperature correction
day=0.9
night=0.9

# Per-period gamma (overrides [gamma] if specified)
# day-r=0.9
# day-g=0.9
# day-b=0.9
# night-r=0.85
# night-g=0.85
# night-b=0.7
```

GeoClue2-based location is also supported:

```ini
[general]
location-provider=geoclue2
adjustment-method=wayland
```

### Autostart

```bash
# Hyprland — with tray indicator
exec-once = gammastep-indicator

# Without tray (pure daemon)
exec-once = gammastep

# Sway
exec gammastep-indicator

# Systemd user service
```

```ini
# ~/.config/systemd/user/gammastep.service
[Unit]
Description=gammastep colour temperature adjuster
Documentation=https://gitlab.com/chinstrap/gammastep
PartOf=graphical-session.target
After=graphical-session.target

[Service]
ExecStart=/usr/bin/gammastep
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical-session.target
```

### One-Shot Manual Override

gammastep supports a one-shot mode useful for scripted overrides:

```bash
# Set to specific temperature and exit (gamma table persists in compositor)
gammastep -O 4000

# Reset gamma to neutral (6500K / no filter)
gammastep -x

# Temporarily apply night mode regardless of time (until process killed)
gammastep -m wayland -t 3500:3500  # same day/night temp = constant

# Print current period and expected temperature
gammastep -v -m wayland -l 52.5:13.4 2>&1 | head -20
```

This one-shot mode is especially useful in keybinding scripts: bind a key to toggle between neutral and a fixed warm temperature using `gammastep -O 3500` / `gammastep -x`.

## hyprsunset — Hyprland-Native

### Overview

`hyprsunset` is Hyprland's official color temperature utility, designed to work tightly with the Hyprland compositor via its native IPC. Unlike `wlsunset` and `gammastep` which use the wlr gamma protocol as external clients, `hyprsunset` can leverage Hyprland's internal plugin and IPC surface, enabling runtime control via `hyprctl`.

### Installation

```bash
# Arch Linux (official extra repo as of late 2024)
sudo pacman -S hyprsunset

# AUR development build
yay -S hyprsunset-git
```

### Basic Usage and Configuration

```bash
# Set temperature immediately and exit (one-shot mode)
hyprsunset -t 3000

# Daemon mode with location-based scheduling
hyprsunset --latitude 52.5 --longitude 13.4

# Daemon mode with explicit day/night temperatures
hyprsunset --latitude 52.5 --longitude 13.4 --day-temp 6500 --night-temp 3000
```

```ini
# ~/.config/hypr/hyprland.conf

# One-shot on startup (sets temperature, does not auto-transition)
exec-once = hyprsunset -t 3000

# Location-aware daemon (auto-transitions with sunrise/sunset)
exec-once = hyprsunset --latitude 52.5 --longitude 13.4 --day-temp 6500 --night-temp 3000
```

### Hyprctl Runtime Control

A key advantage of `hyprsunset` is that Hyprland exposes the current night-light temperature as a configurable keyword, settable at runtime without restarting the daemon:

```bash
# Set temperature via hyprctl (takes effect immediately)
hyprctl keyword misc:hyprsunset_temp 3000

# Query current value
hyprctl getoption misc:hyprsunset_temp

# Reset to neutral
hyprctl keyword misc:hyprsunset_temp 6500
```

This enables clean keybinding integration without needing process management:

```ini
# ~/.config/hypr/hyprland.conf

# Toggle night light: SUPER+SHIFT+N
bind = SUPER SHIFT, N, exec, hyprctl keyword misc:hyprsunset_temp 3000

# Reset to day temperature: SUPER+SHIFT+D
bind = SUPER SHIFT, D, exec, hyprctl keyword misc:hyprsunset_temp 6500

# Cycle through temperatures
bind = SUPER SHIFT, T, exec, ~/.config/hypr/scripts/cycle-temperature.sh
```

```bash
#!/usr/bin/env bash
# ~/.config/hypr/scripts/cycle-temperature.sh
TEMPS=(6500 5000 4000 3000 2700)
CURRENT=$(hyprctl getoption misc:hyprsunset_temp | grep -oP '\d+')
NEXT_IDX=$(( ($(echo "${TEMPS[@]}" | tr ' ' '\n' | grep -n "^${CURRENT}$" | cut -d: -f1) % ${#TEMPS[@]}) ))
hyprctl keyword misc:hyprsunset_temp "${TEMPS[$NEXT_IDX]}"
notify-send "Night Light" "Temperature: ${TEMPS[$NEXT_IDX]}K"
```

## Manual Gamma Adjustment

### wlr-randr and wl-gammarelay

For situations where you want quick, temporary gamma adjustments without a daemon running, a few one-shot approaches exist. `wlr-randr` does not expose a gamma API on its command line, but `wl-gammarelay-rs` (a Rust rewrite of `wl-gammarelay`) provides a D-Bus interface and a command-line client:

```bash
# Install wl-gammarelay-rs (AUR)
yay -S wl-gammarelay-rs

# Start the relay daemon (exposes D-Bus interface)
wl-gammarelay-rs run &

# Set temperature via busctl
busctl --user call rs.wl-gammarelay / rs.wl.GammaRelay.Ddc SetTemperature q 4000

# Set brightness
busctl --user set-property rs.wl-gammarelay / rs.wl.GammaRelay.Ddc Brightness d 0.9

# Reset
busctl --user call rs.wl-gammarelay / rs.wl.GammaRelay.Ddc SetTemperature q 6500
```

`wl-gammarelay-rs` is especially valuable for Waybar integration: the D-Bus interface allows the bar to read the current temperature and display it without polling a process.

### gammastep One-Shot (Recommended for Scripting)

For simplicity, the gammastep one-shot mode is the best scripting interface:

```bash
# Persistent warm filter (until next reset or daemon takes over)
gammastep -O 3500

# Remove all filters
gammastep -x

# Script: toggle warm/neutral
TEMP_FILE="/tmp/nightlight_state"
if [ -f "$TEMP_FILE" ]; then
    rm "$TEMP_FILE"
    gammastep -x
    notify-send "Night Light" "Disabled" --icon=display-brightness
else
    touch "$TEMP_FILE"
    gammastep -O 3500
    notify-send "Night Light" "Enabled (3500K)" --icon=night-light
fi
```

## Temperature Reference

### Kelvin Scale and Use Cases

| Temperature | Description | Use Case |
|---|---|---|
| 6500K | D65 daylight standard | Color grading, design work, photography editing |
| 6000K | Neutral white | General daytime computing |
| 5500K | Overcast daylight | Reduced blue-channel eye strain during daytime |
| 5000K | Warm white | Transition: early morning or late afternoon |
| 4500K | Incandescent-adjacent | Evening computing, 2 hours before sunset |
| 4000K | Warm lamp | Evening, 1 hour before bed |
| 3500K | Warm amber | Nighttime use, 1–2 hours before sleep |
| 3000K | Deep amber | Late night, significant blue reduction |
| 2700K | Candlelight | Maximum warmth; very late night reading |

### Choosing Your Temperatures

The day temperature (`-T` in wlsunset, `[temperature] day=` in gammastep) affects the display during daylight hours. If you do color-critical work (photo editing, design), keep this at 6500K and compensate with monitor hardware calibration. For general coding and browsing, 5500K–6000K day temperature reduces fatigue without visibly distorting UI colors.

The night temperature should be set based on your target sleep time minus 2 hours. If you sleep at midnight, begin the transition at 10 PM to a temperature of 3500K. Most users find 3000K–3500K optimal — warm enough to suppress melatonin effectively without making the display feel unusably orange.

## Integration with Status Bars

### Waybar Integration

Display the current night-light state in Waybar using a custom module:

```json
// ~/.config/waybar/config
{
    "custom/nightlight": {
        "exec": "~/.config/waybar/scripts/nightlight-status.sh",
        "interval": 30,
        "format": "{}",
        "on-click": "~/.config/waybar/scripts/nightlight-toggle.sh",
        "tooltip": true
    }
}
```

```bash
#!/usr/bin/env bash
# ~/.config/waybar/scripts/nightlight-status.sh
# Reads temperature from gammastep/wlsunset via wl-gammarelay-rs D-Bus

if pgrep -x gammastep > /dev/null; then
    TEMP=$(busctl --user get-property rs.wl-gammarelay / rs.wl.GammaRelay.Ddc Temperature 2>/dev/null | awk '{print $2}')
    if [ -n "$TEMP" ] && [ "$TEMP" -lt 6000 ]; then
        echo "{\"text\": \"🌙 ${TEMP}K\", \"tooltip\": \"Night light active: ${TEMP}K\", \"class\": \"active\"}"
    else
        echo "{\"text\": \"☀ 6500K\", \"tooltip\": \"Day mode\", \"class\": \"inactive\"}"
    fi
elif pgrep -x wlsunset > /dev/null; then
    echo "{\"text\": \"🌙 wlsunset\", \"tooltip\": \"wlsunset running\"}"
else
    echo "{\"text\": \"☀\", \"tooltip\": \"No night light daemon\"}"
fi
```

```css
/* ~/.config/waybar/style.css */
#custom-nightlight.active {
    color: #e8a045;
    background: rgba(232, 160, 69, 0.15);
    border-radius: 4px;
    padding: 0 6px;
}

#custom-nightlight.inactive {
    color: #89dceb;
}
```

### Quickshell Night Light Widget

For Quickshell-based status bars (see Ch 23), you can embed a live night-light toggle with temperature readout:

```qml
// ~/.config/quickshell/nightlight.qml
import Quickshell
import Quickshell.Io

property bool nightLightActive: false
property int currentTemp: 6500

Process {
    id: gammaReset
    command: ["gammastep", "-x"]
}

Process {
    id: gammaSet
    property int targetTemp: 3500
    command: ["gammastep", "-O", targetTemp.toString()]
}

// Auto-restart daemon if it exits unexpectedly
Process {
    id: gammaDaemon
    command: ["gammastep"]
    onRunningChanged: {
        if (!running && nightLightActive) {
            // Small delay before restart to avoid rapid cycling
            Qt.callLater(() => { running = true })
        }
    }
}

Button {
    text: nightLightActive ? ("🌙 " + currentTemp + "K") : "☀ Day"
    onClicked: {
        nightLightActive = !nightLightActive
        if (nightLightActive) {
            currentTemp = 3500
            gammaSet.targetTemp = currentTemp
            gammaSet.running = true
        } else {
            currentTemp = 6500
            gammaReset.running = true
        }
    }
}
```

## Integration with Idle Daemon

### hypridle Temperature Ramping

You can tie color temperature to idle state using `hypridle`, creating a gradual warm-down as the system becomes idle (Ch 59):

```ini
# ~/.config/hypr/hypridle.conf

# After 20 minutes idle: ramp to warm
listener {
    timeout = 1200
    on-timeout = hyprsunset -t 3500
    on-resume   = hyprsunset -t 6500
}

# After 30 minutes: ramp to very warm
listener {
    timeout = 1800
    on-timeout = hyprsunset -t 2700
    on-resume   = hyprsunset -t 6500
}
```

The `on-resume` handler resets temperature when activity is detected. This means returning from an idle state always restores day temperature — which may not be what you want if it is already nighttime. A smarter approach checks the current time:

```bash
#!/usr/bin/env bash
# ~/.config/hypr/scripts/idle-resume-temp.sh
# Restore temperature appropriate for current time of day
HOUR=$(date +%H)
if [ "$HOUR" -ge 20 ] || [ "$HOUR" -lt 7 ]; then
    hyprsunset -t 3000   # It's nighttime — restore night temp
else
    hyprsunset -t 6500   # Daytime — restore to full brightness
fi
```

```ini
# ~/.config/hypr/hypridle.conf
listener {
    timeout = 1800
    on-timeout = hyprsunset -t 2700
    on-resume   = ~/.config/hypr/scripts/idle-resume-temp.sh
}
```

### swayidle Integration (Sway / river)

```bash
# ~/.config/sway/config or executed via exec
swayidle -w \
    timeout 1200 'gammastep -O 3500' \
    resume  'gammastep -O 6500' \
    timeout 1800 'gammastep -O 2700' \
    resume  'gammastep -O 6500'
```

## HDR and Color Temperature Compatibility

### Current Limitations

HDR (High Dynamic Range) displays present a fundamental challenge for the `zwlr-gamma-control-unstable-v1` protocol. The protocol operates on the gamma LUT in the display pipeline before tone mapping, and modifying the gamma LUT while HDR tone mapping is active can produce incorrect results: colors may saturate incorrectly, or the temperature shift may be applied twice (once in software, once by the display's own HDR processing).

As of Hyprland 0.45+ and the stable release of `wp-color-management-v1` in late 2024, the correct approach for HDR setups is:

- **KWin (Plasma 6)**: Use the built-in Night Light in System Settings → Display & Monitor → Night Light. It is fully HDR-aware and uses `wp-color-management-v1`.
- **Hyprland with HDR**: `hyprsunset` on Hyprland with HDR enabled may produce visible artifacts on some displays. Test with your monitor. File Hyprland issues if you encounter incorrect tonemapping.
- **Non-HDR outputs alongside HDR**: per-output gamma control works correctly on non-HDR outputs even if another output is HDR.

```bash
# Check if HDR is active on your output
hyprctl monitors | grep -i hdr

# Check which outputs support gamma control
# wlsunset -v will print "gamma supported" or "gamma not supported" per output
wlsunset -l 52.5 -L 13.4 -v 2>&1 | grep -i gamma
```

### KWin Built-In Night Light

For KDE Plasma 6 users, external tools are unnecessary and contraindicated. KWin's built-in night light integrates with the color management pipeline:

```bash
# Check current night light settings via kreadconfig
kreadconfig6 --group NightColor --key Mode
kreadconfig6 --group NightColor --key NightTemperature
kreadconfig6 --group NightColor --key DayTemperature

# Set via kwriteconfig (requires plasmashell restart or DBus call)
kwriteconfig6 --group NightColor --key NightTemperature --type int 3000

# Toggle via DBus
qdbus org.kde.KWin /ColorCorrect setEnabled true
qdbus org.kde.KWin /ColorCorrect setEnabled false
```

## Troubleshooting

### Daemon Starts but Screen Does Not Change

The most common cause is that the compositor does not support the `zwlr-gamma-control-unstable-v1` protocol, or the protocol is disabled. Verify:

```bash
# List supported Wayland protocols
wayland-info 2>/dev/null | grep gamma
# or
weston-info 2>/dev/null | grep gamma

# Alternatively, check with wl-info
wl-info | grep -i gamma
```

If the protocol is absent, you are likely running a compositor that does not support it (e.g., KWin without Wayland extensions, GNOME Mutter). On GNOME, use the `Night Light` toggle in Settings → Displays instead.

### Tool Runs but Temperature Does Not Transition

`wlsunset` and `gammastep` calculate sunrise/sunset based on your provided latitude/longitude and current system time. If your system clock is wrong, transitions will happen at the wrong time or not at all:

```bash
# Verify system time is correct
timedatectl status

# Check if NTP is synced
timedatectl show | grep NTPSynchronized

# Enable NTP if not active
sudo timedatectl set-ntp true

# Manual debug: print what wlsunset calculates
wlsunset -l 52.5 -L 13.4 -v 2>&1 | head -30
```

### gammastep Crashes at Startup

gammastep can crash if another process holds the gamma control protocol (e.g., a leftover daemon from a previous session, or another instance of gammastep):

```bash
# Kill any existing gammastep processes
pkill -x gammastep; pkill -x gammastep-indicator

# Also kill wlsunset if running
pkill -x wlsunset

# Restart clean
gammastep &
```

Only one client can hold `zwlr-gamma-control-unstable-v1` per output at a time. If both `wlsunset` and `gammastep` are autostarted, one will silently fail or crash. Pick one daemon and ensure the other is not in any autostart configuration.

### Temperature Resets to 6500K Unexpectedly

This typically happens when:

1. The daemon crashed and was not restarted — use a systemd user service with `Restart=on-failure`
2. Another application reset the gamma table — screensavers, screen lockers (swaylock, hyprlock) may reset gamma on lock/unlock. Configure your locker to not reset gamma, or add a post-unlock hook that restarts the night-light daemon.
3. A monitor hot-plug event — unplugging and replugging a display resets its gamma state. Configure your compositor's monitor rules to trigger a daemon restart.

```bash
# Hyprland: react to monitor connection events
# ~/.config/hypr/hyprland.conf
exec-once = ~/.config/hypr/scripts/watch-monitor-events.sh
```

```bash
#!/usr/bin/env bash
# ~/.config/hypr/scripts/watch-monitor-events.sh
# Restart night-light daemon when monitors change
socat - UNIX-CONNECT:/tmp/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock | \
while read -r line; do
    if echo "$line" | grep -q "monitoradded\|monitorremoved"; then
        sleep 1
        pkill -x hyprsunset
        hyprsunset --latitude 52.5 --longitude 13.4 &
    fi
done
```

### XWayland Applications Show Incorrect Colors

The gamma correction applied by night-light daemons affects the entire display output, including XWayland windows. However, some applications implement their own color management that may conflict with the gamma table adjustment. This is expected behavior — the display gamma applies globally and uniformly. There is no per-window color temperature on Wayland (and doing so would require application-level cooperation via `wp-color-management-v1`).

If you run color-critical applications (GIMP, Inkscape, Darktable), temporarily disable night light before working:

```bash
# Disable for a color session
gammastep -x

# Re-enable after work
gammastep -O 3500  # or restart the daemon
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
