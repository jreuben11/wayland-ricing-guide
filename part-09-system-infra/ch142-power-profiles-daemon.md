# Chapter 142 — Power Management: power-profiles-daemon, CPU Governors, and Thermal

## Overview

Linux power management in 2025 has converged on two models: the simple
three-profile model from `power-profiles-daemon` (PPD), which is the systemd
and GNOME/KDE standard, and the deep-control model from `TLP`, which predates
PPD and remains popular for ThinkPads and battery-first laptops. Ch78 covers
the TLP approach. This chapter covers PPD — the approach integrated into
Waybar, KDE Plasma, and GNOME Shell — plus CPU frequency governors, thermal
throttling, and per-workload power mode switching via compositor keybinds.

---

## 142.1 power-profiles-daemon Overview

`power-profiles-daemon` (PPD) is a D-Bus system service that exposes three power
profiles to userspace:

| Profile | CPU behavior | When to use |
|---|---|---|
| `performance` | Max boost, no throttle | Gaming, compiling, video export |
| `balanced` | Platform defaults | General desktop use |
| `power-saver` | Reduced clock speed, disable boost | Battery preservation, thermals |

PPD talks directly to:
- `cpufreq` via `/sys/devices/system/cpu/cpufreq/`
- Platform power profiles (Intel HWP, AMD P-state, ACPI platform profile)
- `amd-pstate` and `intel_pstate` kernel drivers

PPD does **not** conflict with the kernel scheduler or governor selection when
running in `passive` mode — it delegates actual frequency choices to the
hardware-managed P-state driver.

```bash
# Install
sudo pacman -S power-profiles-daemon

# Enable and start the service
sudo systemctl enable --now power-profiles-daemon

# Verify it's running
systemctl status power-profiles-daemon
```

---

## 142.2 powerprofilesctl — CLI Usage

```bash
# Show current profile and available profiles
powerprofilesctl

# Output example:
# * balanced:
#     Driver:     amd-pstate-epb
#     Degraded:   no
# 
#   performance:
#     Driver:     amd-pstate-epb
#     Degraded:   no
# 
#   power-saver:
#     Driver:     amd-pstate-epb
#     Degraded:   no

# Set a profile
powerprofilesctl set performance
powerprofilesctl set balanced
powerprofilesctl set power-saver

# Get current profile (for scripting)
powerprofilesctl get
# → balanced

# Hold a profile temporarily (releases on process exit)
# Useful for scripts: profile reverts when script finishes
powerprofilesctl launch --profile=performance -- make -j$(nproc)
```

---

## 142.3 D-Bus Interface

PPD exposes `net.hadess.PowerProfiles` on the system bus:

```bash
# List profiles via D-Bus
gdbus call --system \
  --dest net.hadess.PowerProfiles \
  --object-path /net/hadess/PowerProfiles \
  --method org.freedesktop.DBus.Properties.Get \
  net.hadess.PowerProfiles Profiles

# Get active profile
gdbus call --system \
  --dest net.hadess.PowerProfiles \
  --object-path /net/hadess/PowerProfiles \
  --method org.freedesktop.DBus.Properties.Get \
  net.hadess.PowerProfiles ActiveProfile

# Set active profile via D-Bus
gdbus call --system \
  --dest net.hadess.PowerProfiles \
  --object-path /net/hadess/PowerProfiles \
  --method org.freedesktop.DBus.Properties.Set \
  net.hadess.PowerProfiles ActiveProfile \
  '<"performance">'
```

---

## 142.4 Waybar power-profiles Module

Waybar has a built-in `power-profiles-daemon` module:

```jsonc
// ~/.config/waybar/config.jsonc
{
  "modules-right": ["power-profiles-daemon", "battery", "clock"],

  "power-profiles-daemon": {
    "format": "{icon}",
    "tooltip-format": "Power profile: {profile}\nDriver: {driver}",
    "format-icons": {
      "default": "",
      "performance": "",
      "balanced": "",
      "power-saver": ""
    }
  }
}
```

Style it in Waybar CSS:

```css
/* ~/.config/waybar/style.css */
#power-profiles-daemon {
    padding: 0 10px;
    color: #a9b1d6;
    background: transparent;
}

#power-profiles-daemon.performance {
    color: #f7768e;
    background: rgba(247, 118, 142, 0.15);
    border-radius: 6px;
}

#power-profiles-daemon.balanced {
    color: #9ece6a;
}

#power-profiles-daemon.power-saver {
    color: #7aa2f7;
}
```

---

## 142.5 Keybind-Driven Profile Switching

Switch profiles from your compositor keybinds for instant workflow transitions:

### Hyprland

```conf
# hyprland.conf — cycle through profiles with Super+P
bind = SUPER, P, exec, ~/.config/hypr/scripts/power-cycle.sh
```

```bash
#!/usr/bin/env bash
# ~/.config/hypr/scripts/power-cycle.sh
CURRENT=$(powerprofilesctl get)
case "$CURRENT" in
  power-saver)  NEXT=balanced     ;;
  balanced)     NEXT=performance  ;;
  performance)  NEXT=power-saver  ;;
  *)            NEXT=balanced     ;;
esac
powerprofilesctl set "$NEXT"
notify-send "Power Profile" "→ $NEXT" --icon=battery-symbolic --expire-time=2000
```

### Sway

```conf
# sway/config
bindsym $mod+p exec ~/.config/sway/scripts/power-cycle.sh
```

---

## 142.6 CPU Frequency Governors (Manual Control)

When PPD is not running (or on systems it doesn't support), the Linux `cpufreq`
subsystem exposes governors directly:

```bash
# Check current governor on all CPUs
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor | sort -u

# Available governors:
# performance  — always max frequency
# powersave    — always min frequency
# schedutil    — scheduler-driven (recommended for modern kernels)
# ondemand     — legacy demand-based scaling
# conservative — gradual ramp up/down

# Set governor on all CPUs (requires root)
sudo cpupower frequency-set -g schedutil
# Or manually:
echo schedutil | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Check frequency limits
cpupower frequency-info
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq

# Set max frequency to 2.4GHz (for thermal management)
sudo cpupower frequency-set -u 2400MHz
```

### Persist governor across reboots

```ini
# /etc/tmpfiles.d/cpufreq-governor.conf
w /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor - - - - schedutil
w /sys/devices/system/cpu/cpu1/cpufreq/scaling_governor - - - - schedutil
# (one line per CPU core, or use a udev rule)
```

---

## 142.7 Intel and AMD P-State Drivers

Modern CPUs use hardware-managed P-state drivers that make traditional software
governors mostly irrelevant:

```bash
# Intel: check if HWP (Hardware-managed P-states) is active
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver
# → intel_pstate  (software-managed)
# → intel_cpufreq (hwp mode, schedule-driven)

# AMD: check P-state driver
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver
# → amd-pstate         (software-managed)
# → amd-pstate-epp     (energy performance preference)
# → amd-pstate-epb     (energy performance bias — newer)

# Energy Performance Preference for AMD EPP
cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference
# Available: default | performance | balance_performance | balance_power | power

# Set EPP (more nuanced than governor):
echo balance_performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference
```

PPD automatically sets the right EPP value when you switch profiles — this is
the mechanism behind `powerprofilesctl set performance` having real hardware effect.

---

## 142.8 Thermal Management

### Checking thermal zones

```bash
# List thermal zones
paste /sys/class/thermal/thermal_zone*/type /sys/class/thermal/thermal_zone*/temp \
  | awk '{printf "%-20s %d°C\n", $1, $2/1000}'

# Watch CPU temperature in real time
watch -n1 "cat /sys/class/thermal/thermal_zone*/temp | awk '{print \$1/1000\"°C\"}'"

# Using sensors (lm_sensors)
sudo pacman -S lm_sensors
sudo sensors-detect --auto
sensors
```

### thermald (Intel thermal daemon)

```bash
# Install (Intel systems)
sudo pacman -S thermald

sudo systemctl enable --now thermald
# thermald automatically throttles when approaching thermal limits
# Works alongside PPD without conflict
```

### Manual thermal throttle point

```bash
# Set thermal trip point for throttling (in millidegrees)
# Example: throttle at 85°C for cpu-thermal zone
echo 85000 | sudo tee /sys/class/thermal/thermal_zone0/trip_point_1_temp
```

---

## 142.9 Battery Threshold (Charging Limit)

Many laptops expose charge thresholds via sysfs:

```bash
# Check if your laptop supports charge thresholds
ls /sys/class/power_supply/BAT*/charge_control_end_threshold 2>/dev/null

# Set charge limit to 80% (extend battery longevity)
echo 80 | sudo tee /sys/class/power_supply/BAT0/charge_control_end_threshold
echo 20 | sudo tee /sys/class/power_supply/BAT0/charge_control_start_threshold

# Persist across reboots (udev rule)
# /etc/udev/rules.d/90-battery-charge-limit.rules:
# SUBSYSTEM=="power_supply", KERNEL=="BAT0", \
#   ATTR{charge_control_end_threshold}="80"

# For ThinkPads: use TLP which handles this with:
# START_CHARGE_THRESH_BAT0=20
# STOP_CHARGE_THRESH_BAT0=80
```

---

## 142.10 PPD vs TLP Comparison

| Feature | power-profiles-daemon | TLP |
|---|---|---|
| Interface | D-Bus, `powerprofilesctl` | `/etc/tlp.conf`, `tlp-stat` |
| Profiles | 3 fixed (perf/balanced/saver) | Fully configurable |
| AC/Battery auto-switch | Yes (via systemd-logind) | Yes (major feature) |
| Charge thresholds | No (use udev) | Yes (built-in) |
| Per-device USB power | No | Yes |
| GNOME/KDE integration | Native | Via tlp-ui / manual |
| Waybar module | `power-profiles-daemon` | Custom script |
| Intel EPP/EPB | Yes | Yes (separate config) |
| AMD P-state | Yes | Limited |
| Recommended for | Desktops, GNOME/KDE Plasma | ThinkPads, battery-first |

**Do not run both simultaneously** — they conflict on CPU frequency decisions.
Check which is active: `systemctl status power-profiles-daemon tlp`.

---

## 142.11 upower Integration

`upower` tracks battery state and power changes, used by status bars and desktops:

```bash
# List all power devices
upower -e

# Inspect battery details
upower -i /org/freedesktop/UPower/devices/battery_BAT0

# Watch power events (plug/unplug charger)
upower --monitor

# Get battery percentage (for scripts)
upower -i $(upower -e | grep BAT) | grep -E "percentage" | awk '{print $2}'
```

### Waybar battery module with upower events

```jsonc
"battery": {
    "states": {
        "warning": 30,
        "critical": 15
    },
    "format": "{capacity}% {icon}",
    "format-charging": "{capacity}%  {icon}",
    "format-icons": ["", "", "", "", ""],
    "tooltip-format": "{timeTo} — {power:.1f}W"
}
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
