# Chapter 78 — Laptop Power Management: tlp, auto-cpufreq, power-profiles-daemon

## Overview
Wayland compositors — especially those with always-on animations — can drain laptop
batteries faster than X11. This chapter covers power optimization, suspend/hibernate,
and brightness control specific to Wayland setups.

## Sections

### 78.1 Power Management Stack

```
Hardware → ACPI events → upower → power-profiles-daemon / tlp
                      → logind  → suspend/hibernate/lid actions
                      → backlight → brightnessctl / light
```

### 78.2 power-profiles-daemon (Recommended)

The modern, integrated approach — works with GNOME, KDE, and custom setups:
```bash
sudo pacman -S power-profiles-daemon
sudo systemctl enable --now power-profiles-daemon
```

**Switching profiles:**
```bash
powerprofilesctl list              # show available: performance, balanced, power-saver
powerprofilesctl set balanced      # switch profile
powerprofilesctl get               # current profile
```

**Quickshell integration:**
```qml
// UPower.powerProfiles gives the current profile
// Switch via Process { command: ["powerprofilesctl", "set", "power-saver"] }
```

**Keybind for quick toggle:**
```conf
bind = SUPER, F9, exec, powerprofilesctl set power-saver && notify-send "Power Saver"
bind = SUPER, F10, exec, powerprofilesctl set balanced && notify-send "Balanced"
bind = SUPER, F11, exec, powerprofilesctl set performance && notify-send "Performance"
```

### 78.3 tlp — Fine-Grained Battery Tuning

tlp provides deeper control than power-profiles-daemon:
```bash
sudo pacman -S tlp tlp-rdw
sudo systemctl enable --now tlp
sudo systemctl mask systemd-rfkill.service systemd-rfkill.socket
```

**Key `tlp.conf` settings:**
```ini
# /etc/tlp.conf

# CPU governor on battery
CPU_SCALING_GOVERNOR_ON_BAT=powersave
CPU_SCALING_GOVERNOR_ON_AC=performance

# CPU energy/performance preference
CPU_ENERGY_PERF_POLICY_ON_BAT=power
CPU_ENERGY_PERF_POLICY_ON_AC=performance

# Battery charge thresholds (ThinkPad/some Lenovo/ASUS)
START_CHARGE_THRESH_BAT0=20   # start charging at 20%
STOP_CHARGE_THRESH_BAT0=80    # stop charging at 80% (extends battery lifespan)

# WiFi power save
WIFI_PWR_ON_BAT=on

# Disk spindown
DISK_APM_LEVEL_ON_BAT="128 128"
```

**Note:** Don't use tlp AND power-profiles-daemon simultaneously — they conflict.

### 78.4 auto-cpufreq — Automatic CPU Frequency Scaling

```bash
paru -S auto-cpufreq
sudo systemctl enable --now auto-cpufreq
```

auto-cpufreq monitors CPU load and switches between performance/powersave automatically,
more aggressively than the kernel's default `schedutil` governor.

### 78.5 Suspend and Hibernate

**Suspend to RAM (S3):**
```bash
systemctl suspend    # immediate suspend
loginctl suspend     # same, via logind
```

**Hibernate (swap-based):**
```bash
# 1. Create swap partition >= RAM size, OR swap file
# 2. Add to kernel params: resume=/dev/sdaX
# 3. Add 'resume' hook to mkinitcpio.conf HOOKS
systemctl hibernate
```

**Hybrid suspend (suspend + hibernate backup):**
```bash
systemctl hybrid-sleep
```

**Lid close behavior** (`/etc/systemd/logind.conf`):
```ini
[Login]
HandleLidSwitch=suspend
HandleLidSwitchExternalPower=lock    # lid close while plugged in = just lock
HandleLidSwitchDocked=ignore         # lid close while docked = do nothing
```

### 78.6 Hyprland-Specific Power Settings

```conf
# hyprland.conf — reduce power usage
misc {
    vfr = true           # Variable Frame Rate — crucial for battery life
                         # compositor renders at display refresh only when needed
    no_direct_scanout = false  # allow direct scanout for fullscreen apps
}

animations {
    enabled = true
    # Reduce animation complexity on battery via hypridle
}
```

**VFR is the single most important setting for battery life on Hyprland.**
Without it, the GPU renders at full speed even on a static desktop.

### 78.7 Backlight Control

```bash
sudo pacman -S brightnessctl

# Usage
brightnessctl set 50%       # set to 50%
brightnessctl set +10%      # increase by 10%
brightnessctl set 10%-      # decrease by 10%
brightnessctl get           # current value
brightnessctl max           # maximum value
```

```conf
# hyprland.conf
bind = , XF86MonBrightnessUp, exec, brightnessctl set +5%
bind = , XF86MonBrightnessDown, exec, brightnessctl set 5%-
```

**Keyboard backlight:**
```bash
brightnessctl -d *::kbd_backlight set 50%
```

### 78.8 Battery Status in Quickshell

Via `UPower.devices` (Ch 22), or directly reading `/sys`:
```qml
FileView {
    path: "/sys/class/power_supply/BAT0/capacity"
    watchChanges: true
    onTextChanged: batteryLevel = parseInt(text)
}
FileView {
    path: "/sys/class/power_supply/BAT0/status"
    watchChanges: true
    onTextChanged: charging = text.trim() === "Charging"
}
```

### 78.9 Thermal Management

```bash
# Monitor temps
watch -n 1 sensors    # requires lm_sensors

# Thermal throttle protection
sudo pacman -S thermald
sudo systemctl enable --now thermald
```

For AMD laptops with custom TDP:
```bash
sudo pacman -S ryzenadj
# Set 15W power limit:
sudo ryzenadj --stapm-limit=15000 --slow-limit=15000 --fast-limit=15000
```
