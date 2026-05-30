# Chapter 78 — Laptop Power Management: tlp, auto-cpufreq, power-profiles-daemon

## Contents

- [Overview](#overview)
- [Sections](#sections)
  - [78.1 Power Management Stack](#781-power-management-stack)
  - [78.2 power-profiles-daemon (Recommended)](#782-power-profiles-daemon-recommended)
  - [78.3 tlp — Fine-Grained Battery Tuning](#783-tlp-fine-grained-battery-tuning)
  - [78.4 auto-cpufreq — Automatic CPU Frequency Scaling](#784-auto-cpufreq-automatic-cpu-frequency-scaling)
  - [78.5 Suspend and Hibernate](#785-suspend-and-hibernate)
  - [78.6 Hyprland-Specific Power Settings](#786-hyprland-specific-power-settings)
  - [78.7 Backlight Control](#787-backlight-control)
  - [78.8 Battery Status in Quickshell / Status Bars](#788-battery-status-in-quickshell-status-bars)
  - [78.9 Thermal Management](#789-thermal-management)
  - [78.10 Putting It All Together: Example Battery Profile Script](#7810-putting-it-all-together-example-battery-profile-script)
- [Troubleshooting](#troubleshooting)

---


## Overview

Wayland compositors — especially those with always-on animations — can drain laptop
batteries faster than X11. The GPU-accelerated rendering pipeline that makes Wayland
so smooth also means that every idle frame, every animated widget, and every unoptimized
compositor setting burns extra milliwatts. This chapter covers the full power optimization
stack: kernel-level frequency scaling, battery charge thresholds, suspend and hibernate
configuration, brightness control, and Wayland-compositor-specific settings that are
critical for battery life.

The goal is not just "battery lasts longer" — it's maintaining full performance when
plugged in, keeping the system responsive under load on battery, and enabling seamless
suspend/resume that doesn't break your Wayland session. Getting this right requires
understanding the full stack from CPU governors to compositor frame pacing. See Ch 22
for UPower D-Bus integration and Ch 53 for session startup hooks where power profiles
can be applied at login.

## Sections

### 78.1 Power Management Stack

The Linux power management stack has several layers, each controlled independently:

```
Hardware → ACPI events → upower      → power-profiles-daemon / tlp
                      → logind       → suspend/hibernate/lid actions
                      → backlight    → brightnessctl / light
                      ↓
                CPU scaling: cpufreq → governors (schedutil, powersave, performance)
                      ↓
                Platform drivers:  intel_pstate / amd-pstate / acpi-cpufreq
```

Understanding which layer owns which concern prevents conflicts. The two main conflicts
to avoid are: running both `tlp` and `power-profiles-daemon` simultaneously (they
both set CPU energy-performance preferences and will fight each other), and using
`auto-cpufreq` alongside `power-profiles-daemon` without understanding how each
delegates to the kernel's cpufreq subsystem.

Use `tlp-stat -s` to see which power management tools are active and whether any
conflicts exist. The command will warn explicitly if it detects competing services.

For a clean modern setup on a recent kernel (6.x), the recommended stack is:

| Scenario | Recommended Tool | Notes |
|---|---|---|
| GNOME/KDE with system integration | power-profiles-daemon | D-Bus API, desktop-aware |
| ThinkPad / ASUS with charge thresholds | tlp | Better hardware-specific tuning |
| Maximum battery life, AMD/Intel CPU | auto-cpufreq + tlp (no ppd) | Aggressive scaling |
| Quick setup, simple laptop | power-profiles-daemon only | Good defaults |

### 78.2 power-profiles-daemon (Recommended)

`power-profiles-daemon` is the modern, integrated approach that works with GNOME, KDE,
and custom Wayland setups. It exposes a D-Bus API that desktop components (bars,
status widgets, GNOME Control Center) can query and control, making it the best choice
for a cohesive riced desktop where the status bar shows and switches power profiles.

```bash
sudo pacman -S power-profiles-daemon
sudo systemctl enable --now power-profiles-daemon
```

The daemon communicates with kernel power interfaces via `intel_pstate` or `amd-pstate`
energy performance preference (EPP) hints. Under the hood, switching to `power-saver`
sets the EPP to `power` and the CPU scaling governor to `powersave`, while `performance`
sets EPP to `performance` and may trigger a `performance` governor. The `balanced`
profile maps to `balance_performance` EPP and `schedutil` governor — the best default
for unpredictable workloads.

**Switching profiles from the command line:**
```bash
powerprofilesctl list              # show available: performance, balanced, power-saver
powerprofilesctl set balanced      # switch profile
powerprofilesctl get               # current profile
powerprofilesctl set power-saver   # enable power saving
```

**D-Bus query (for scripting and status bars):**
```bash
# Get current profile via D-Bus
dbus-send --print-reply --system \
  --dest=net.hadess.PowerProfiles \
  /net/hadess/PowerProfiles \
  org.freedesktop.DBus.Properties.Get \
  string:net.hadess.PowerProfiles \
  string:ActiveProfile

# Set profile via D-Bus (useful in scripts without powerprofilesctl)
dbus-send --system \
  --dest=net.hadess.PowerProfiles \
  /net/hadess/PowerProfiles \
  org.freedesktop.DBus.Properties.Set \
  string:net.hadess.PowerProfiles \
  string:ActiveProfile \
  variant:string:power-saver
```

**Quickshell integration** — subscribe to profile changes and display/switch from your bar:
```qml
// In your bar's QML, use a Process to read/set profiles
// Read current profile:
// Process { command: ["powerprofilesctl", "get"]; onExited: currentProfile = stdout.trim() }

// Switch via keybind action:
Process {
    id: setPowerSaver
    command: ["powerprofilesctl", "set", "power-saver"]
}

// Trigger with: setPowerSaver.start()
```

**Hyprland keybinds for quick profile switching:**
```conf
# hyprland.conf
bind = SUPER, F9,  exec, powerprofilesctl set power-saver   && notify-send "Power" "Power Saver mode"
bind = SUPER, F10, exec, powerprofilesctl set balanced       && notify-send "Power" "Balanced mode"
bind = SUPER, F11, exec, powerprofilesctl set performance    && notify-send "Power" "Performance mode"
```

**Auto-switch on AC/battery events** via udev rule:
```bash
# /etc/udev/rules.d/99-power-profile.rules
SUBSYSTEM=="power_supply", ATTR{online}=="0", RUN+="/usr/bin/powerprofilesctl set power-saver"
SUBSYSTEM=="power_supply", ATTR{online}=="1", RUN+="/usr/bin/powerprofilesctl set balanced"
```

Reload udev rules with `sudo udevadm control --reload-rules` after creating this file.

### 78.3 tlp — Fine-Grained Battery Tuning

`tlp` provides deeper control than `power-profiles-daemon`, especially for hardware-
specific features: battery charge thresholds on ThinkPads and some ASUS/Dell machines,
PCIe ASPM tuning, runtime PM for USB devices, and disk APM levels. If you have a
ThinkPad, tlp is almost mandatory for protecting battery longevity through charge
thresholds.

```bash
sudo pacman -S tlp tlp-rdw
sudo systemctl enable --now tlp
# Mask rfkill services to prevent conflicts
sudo systemctl mask systemd-rfkill.service systemd-rfkill.socket
```

`tlp-rdw` is the Radio Device Wizard — it can automatically disable WiFi when Ethernet
is connected and re-enable it on disconnect. Enable it with:
```bash
sudo systemctl enable --now NetworkManager-dispatcher.service
# tlp-rdw hooks into NetworkManager dispatcher
```

**Complete annotated `/etc/tlp.conf` for a ThinkPad-style setup:**
```ini
# /etc/tlp.conf — copy to /etc/tlp.d/99-custom.conf to override defaults cleanly

# ── CPU ──────────────────────────────────────────────────────────────────────
# Scaling governor: powersave (intel_pstate EPP) or schedutil (acpi-cpufreq)
CPU_SCALING_GOVERNOR_ON_AC=performance
CPU_SCALING_GOVERNOR_ON_BAT=powersave

# Intel/AMD energy performance preference
CPU_ENERGY_PERF_POLICY_ON_AC=performance
CPU_ENERGY_PERF_POLICY_ON_BAT=power

# CPU boost on battery (0=disable, 1=enable)
CPU_BOOST_ON_AC=1
CPU_BOOST_ON_BAT=0

# HWP dynamic boost (Intel only)
CPU_HWP_DYN_BOOST_ON_AC=1
CPU_HWP_DYN_BOOST_ON_BAT=0

# ── Battery Charge Thresholds ─────────────────────────────────────────────────
# ThinkPad, some Lenovo IdeaPad, ASUS: extend battery life by not charging to 100%
START_CHARGE_THRESH_BAT0=20   # start charging when below 20%
STOP_CHARGE_THRESH_BAT0=80    # stop charging at 80% (prevents degradation)
# For a second battery:
# START_CHARGE_THRESH_BAT1=20
# STOP_CHARGE_THRESH_BAT1=80

# ── Disk ──────────────────────────────────────────────────────────────────────
# APM level: 1-127 = spin down, 128-254 = no spin down; 255 = disabled
DISK_APM_LEVEL_ON_AC="254 254"
DISK_APM_LEVEL_ON_BAT="128 128"

# Disk spindown timeout (hdparm -S value; 0=disable)
DISK_SPINDOWN_TIMEOUT_ON_AC="0 0"
DISK_SPINDOWN_TIMEOUT_ON_BAT="60 60"

# ── WiFi / Bluetooth ──────────────────────────────────────────────────────────
WIFI_PWR_ON_AC=off
WIFI_PWR_ON_BAT=on

# ── PCIe ASPM ─────────────────────────────────────────────────────────────────
# default/performance/powersave/powersupersave
PCIE_ASPM_ON_AC=performance
PCIE_ASPM_ON_BAT=powersupersave

# ── Runtime PM ────────────────────────────────────────────────────────────────
RUNTIME_PM_ON_AC=on
RUNTIME_PM_ON_BAT=on

# ── USB ───────────────────────────────────────────────────────────────────────
USB_AUTOSUSPEND=1
# Exclude specific USB device IDs from autosuspend (e.g. keyboard, mouse)
# USB_DENYLIST="046d:c52b 1234:5678"
```

After editing, apply settings immediately without rebooting:
```bash
sudo tlp start          # re-apply all settings
sudo tlp-stat -s        # show status summary
sudo tlp-stat -b        # battery info and thresholds
sudo tlp-stat -d        # disk power management status
sudo tlp-stat -p        # processor/CPU info
```

**Note:** Do not use tlp AND power-profiles-daemon simultaneously — they conflict.
If you installed both, disable one: `sudo systemctl disable --now power-profiles-daemon`
before enabling tlp.

### 78.4 auto-cpufreq — Automatic CPU Frequency Scaling

`auto-cpufreq` monitors CPU load and switches between performance and powersave
governors automatically, more aggressively and intelligently than the kernel's default
`schedutil` governor alone. It's a Python daemon that samples CPU usage periodically
and uses heuristics to determine the appropriate frequency scaling policy.

```bash
paru -S auto-cpufreq
sudo auto-cpufreq --install   # installs systemd service
sudo systemctl enable --now auto-cpufreq
```

When installed, `auto-cpufreq` takes over CPU governor management. It will set
`performance` when load is high (even on battery) and `powersave` when idle. This
produces better interactive responsiveness on battery compared to a static `powersave`
governor while still saving power during idle periods.

**Monitoring auto-cpufreq decisions in real time:**
```bash
sudo auto-cpufreq --monitor   # live view of governor and frequency decisions
sudo auto-cpufreq --stats     # summary statistics
journalctl -u auto-cpufreq -f # follow the systemd journal
```

**Configuration** (`/etc/auto-cpufreq.conf`):
```ini
[charger]
governor = performance
energy_performance_preference = performance
scaling_min_freq = 800000
scaling_max_freq = 5000000

[battery]
governor = powersave
energy_performance_preference = power
scaling_min_freq = 400000
scaling_max_freq = 3000000
# turbo = auto   # let auto-cpufreq decide when to enable turbo
```

**Compatibility note:** Do not run `auto-cpufreq` alongside `power-profiles-daemon`
without understanding the interaction. `auto-cpufreq` will override the governor set
by `ppd`. If using `auto-cpufreq`, disable `power-profiles-daemon`.

### 78.5 Suspend and Hibernate

Wayland session suspend/resume must be handled carefully. The compositor needs to
release DRM/KMS resources before the system sleeps and reclaim them on wake. Hyprland
and most modern Wayland compositors handle this automatically via `logind` signals,
but there are edge cases — particularly with `swaylock`/`hyprlock` and GPU drivers.

**Suspend to RAM (S3 sleep):**
```bash
systemctl suspend    # immediate suspend via systemd
loginctl suspend     # same, routed through logind
# Check available sleep states:
cat /sys/power/state      # should show: freeze mem disk
cat /sys/power/mem_sleep  # s2idle [deep] — [deep] is S3
```

**Force S3 (deep) sleep if defaulting to s2idle:**
```bash
# In /etc/systemd/sleep.conf:
[Sleep]
MemorySleepMode=deep
```

Or as a kernel parameter in your bootloader (`mem_sleep_default=deep`).

**Hibernate (swap-based):**

Hibernate writes RAM to swap and powers off. Resume reads it back. Requires swap space
at least equal to RAM size.

```bash
# 1. Create a swap file (if no swap partition):
sudo dd if=/dev/zero of=/swapfile bs=1G count=32 status=progress
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap defaults 0 0' | sudo tee -a /etc/fstab

# 2. Find the resume offset (for swap file; not needed for swap partition):
sudo filefrag -v /swapfile | awk 'NR==4{print $4}' | tr -d '.'
# Note: the first physical_offset value from filefrag output

# 3. Add kernel parameters (GRUB example):
# GRUB_CMDLINE_LINUX_DEFAULT="... resume=/dev/sdaX resume_offset=<offset>"
# (for swap file; for partition just resume=/dev/sdaX)

# 4. Add 'resume' hook to /etc/mkinitcpio.conf:
# HOOKS=(base udev autodetect modconf kms keyboard keymap consolefont block filesystems resume fsck)
sudo mkinitcpio -P

# 5. Update bootloader:
sudo grub-mkconfig -o /boot/grub/grub.cfg   # GRUB
# or for systemd-boot: edit /boot/loader/entries/<entry>.conf

# 6. Test:
systemctl hibernate
```

**Hybrid suspend** (suspend + hibernate backup — if power is lost during sleep, restore
from hibernate):
```bash
systemctl hybrid-sleep
# Or: suspend-then-hibernate (suspend first, hibernate after a timeout)
```

**Configure suspend-then-hibernate timeout:**
```ini
# /etc/systemd/sleep.conf
[Sleep]
HibernateDelaySec=3600   # hibernate after 1 hour of suspend
```

**Lid close behavior** — configure in `/etc/systemd/logind.conf`:
```ini
[Login]
HandleLidSwitch=suspend              # lid close on battery = suspend
HandleLidSwitchExternalPower=lock    # lid close while plugged in = just lock screen
HandleLidSwitchDocked=ignore         # lid close while docked = do nothing
IdleAction=suspend                   # action after IdleActionSec
IdleActionSec=30min                  # idle timeout
```

After editing logind.conf: `sudo systemctl restart systemd-logind`
(Note: this will terminate your session — make sure to save work first, or use
`sudo kill -HUP $(pidof systemd-logind)` to reload without restart.)

**Pre/post-suspend hooks** — run scripts on suspend/resume:
```bash
# /etc/systemd/system/resume@.service  (template for user-specific resume actions)
# Or simpler: drop scripts in /usr/lib/systemd/system-sleep/

# /usr/lib/systemd/system-sleep/my-hook.sh
#!/bin/bash
case "$1" in
    pre)
        # Actions before sleep (e.g., stop a service, save state)
        systemctl stop bluetooth.service
        ;;
    post)
        # Actions after resume (e.g., restart services, refresh keyrings)
        systemctl start bluetooth.service
        # Restart pipewire in case audio broke on resume:
        su -c "systemctl --user restart pipewire wireplumber" your_username
        ;;
esac
```
```bash
sudo chmod +x /usr/lib/systemd/system-sleep/my-hook.sh
```

### 78.6 Hyprland-Specific Power Settings

Hyprland has several settings that directly affect power consumption on laptops.
Getting these right can extend battery life by 20-40% compared to default settings.

```conf
# hyprland.conf — power optimization settings

misc {
    # Variable Frame Rate: compositor renders only when needed (idle = near 0 fps)
    # This is the single most important battery setting for Hyprland
    vfr = true

    # Allow direct scanout for fullscreen apps (bypasses compositor, saves GPU work)
    no_direct_scanout = false

    # Disable force full framerate (related to VFR)
    # If VFR is on, this should not need changing
}

animations {
    enabled = true
    # Shorter, simpler animations = less GPU work on battery
    # Consider a battery-profile that disables animations via hypridle
}

# Reduce rendering work
decoration {
    shadow {
        enabled = true
        # Fewer shadow passes = less GPU
        passes = 1
    }
    blur {
        enabled = true
        size = 3        # smaller blur = less GPU work
        passes = 1
        # Consider disabling blur entirely on battery:
        # enabled = false
    }
}
```

**VFR is the single most important setting for battery life on Hyprland.** Without it,
the GPU renders at full display refresh rate (e.g., 60 or 144 fps) even on a completely
static desktop. With VFR enabled, the GPU can drop to near-zero frame rate when nothing
is animating, saving significant power.

**hypridle** — idle management with power-aware actions:
```conf
# ~/.config/hypr/hypridle.conf
general {
    lock_cmd = pidof hyprlock || hyprlock       # run hyprlock if not already running
    before_sleep_cmd = loginctl lock-session    # lock before sleep
    after_sleep_cmd = hyprctl dispatch dpms on  # turn display on after wake
    ignore_dbus_inhibit = false
}

listener {
    timeout = 150                                 # 2.5 min: dim screen
    on-timeout = brightnessctl -s set 10%        # save current brightness, set 10%
    on-resume = brightnessctl -r                 # restore saved brightness
}

listener {
    timeout = 300                                 # 5 min: screen off
    on-timeout = hyprctl dispatch dpms off
    on-resume = hyprctl dispatch dpms on
}

listener {
    timeout = 600                                 # 10 min: suspend
    on-timeout = systemctl suspend
}
```

**Per-workspace power profiles** — if you work on battery with heavy apps in specific
workspaces, trigger profile changes via Hyprland workspace events (see Ch 53):
```bash
# In a hyprland event script listening on the hyprland socket:
# When switching to workspace 3 (e.g., video editing):
# powerprofilesctl set performance
# When leaving workspace 3:
# powerprofilesctl set balanced
```

### 78.7 Backlight Control

Backlight control on Wayland is handled through kernel sysfs interfaces, exposed via
tools like `brightnessctl` and `light`. Direct `/sys/class/backlight` writes require
root, so these tools use udev rules or the `video` group for unprivileged access.

```bash
sudo pacman -S brightnessctl

# Add your user to the video group for unprivileged backlight control:
sudo usermod -aG video $USER
# Log out and back in for group change to take effect

# Basic usage:
brightnessctl set 50%       # set to exactly 50%
brightnessctl set +10%      # increase by 10%
brightnessctl set 10%-      # decrease by 10%
brightnessctl get           # current raw value
brightnessctl max           # maximum raw value
brightnessctl -m            # machine-readable output (device,name,type,current,max,current%)

# List all backlight/LED devices:
brightnessctl --list

# Target a specific device:
brightnessctl -d intel_backlight set 70%
```

**Keyboard backlight:**
```bash
# List keyboard backlight devices:
brightnessctl --list | grep kbd

# Set keyboard backlight:
brightnessctl -d *::kbd_backlight set 50%
brightnessctl -d *::kbd_backlight set +25%
brightnessctl -d *::kbd_backlight set 0%    # off
```

**Hyprland key bindings:**
```conf
# hyprland.conf — media key bindings for brightness
bind = , XF86MonBrightnessUp,   exec, brightnessctl set +5%
bind = , XF86MonBrightnessDown, exec, brightnessctl set 5%-
bind = , XF86KbdBrightnessUp,   exec, brightnessctl -d *::kbd_backlight set +10%
bind = , XF86KbdBrightnessDown, exec, brightnessctl -d *::kbd_backlight set 10%-
```

**OSD notification on brightness change** — combine with `dunst` or `mako`:
```bash
# Script: /usr/local/bin/brightness-change
#!/bin/bash
brightnessctl set "$1"
LEVEL=$(brightnessctl -m | cut -d, -f4 | tr -d '%')
notify-send -h string:x-dunst-stack-tag:brightness \
            -h int:value:"$LEVEL" \
            -i display-brightness-symbolic \
            "Brightness" "${LEVEL}%"
```
```conf
# hyprland.conf
bind = , XF86MonBrightnessUp,   exec, /usr/local/bin/brightness-change +5%
bind = , XF86MonBrightnessDown, exec, /usr/local/bin/brightness-change 5%-
```

**`light` as an alternative to `brightnessctl`:**
```bash
sudo pacman -S light
light -A 10     # increase 10%
light -U 10     # decrease 10%
light -S 50     # set to 50%
light -G        # get current percentage
```

### 78.8 Battery Status in Quickshell / Status Bars

Battery information can be sourced from UPower D-Bus (Ch 22), or by directly reading
`/sys/class/power_supply/`. The sysfs approach is simpler and has no D-Bus dependency;
the UPower approach provides richer data including time-to-empty estimates, health
percentage, and proper charging state detection.

**Direct sysfs reading in Quickshell QML:**
```qml
// Battery capacity and status watcher
FileView {
    id: batteryCapacity
    path: "/sys/class/power_supply/BAT0/capacity"
    watchChanges: true
    onTextChanged: batteryLevel = parseInt(text.trim())
}

FileView {
    id: batteryStatus
    path: "/sys/class/power_supply/BAT0/status"
    watchChanges: true
    // Values: "Charging", "Discharging", "Full", "Not charging", "Unknown"
    onTextChanged: charging = text.trim() === "Charging"
}

FileView {
    id: acAdapter
    path: "/sys/class/power_supply/AC/online"
    watchChanges: true
    onTextChanged: onAC = parseInt(text.trim()) === 1
}
```

**Reading additional battery info from sysfs:**
```bash
# Useful files in /sys/class/power_supply/BAT0/
cat /sys/class/power_supply/BAT0/capacity          # percent 0-100
cat /sys/class/power_supply/BAT0/status            # Charging/Discharging/Full
cat /sys/class/power_supply/BAT0/energy_now        # current energy (µWh)
cat /sys/class/power_supply/BAT0/energy_full       # current full capacity (µWh)
cat /sys/class/power_supply/BAT0/energy_full_design # original capacity (µWh)
cat /sys/class/power_supply/BAT0/power_now         # current draw (µW)
cat /sys/class/power_supply/BAT0/voltage_now       # voltage (µV)
cat /sys/class/power_supply/BAT0/cycle_count       # charge cycles
cat /sys/class/power_supply/BAT0/technology        # Li-ion, etc.

# Calculate battery health:
# health = energy_full / energy_full_design * 100
```

**Time-to-empty estimation script:**
```bash
#!/bin/bash
# /usr/local/bin/battery-time
ENERGY=$(cat /sys/class/power_supply/BAT0/energy_now)
POWER=$(cat /sys/class/power_supply/BAT0/power_now)
STATUS=$(cat /sys/class/power_supply/BAT0/status)

if [[ "$STATUS" == "Discharging" && "$POWER" -gt 0 ]]; then
    HOURS=$(echo "scale=1; $ENERGY / $POWER" | bc)
    echo "${HOURS}h remaining"
elif [[ "$STATUS" == "Charging" ]]; then
    FULL=$(cat /sys/class/power_supply/BAT0/energy_full)
    REMAINING=$((FULL - ENERGY))
    HOURS=$(echo "scale=1; $REMAINING / $POWER" | bc)
    echo "${HOURS}h to full"
else
    echo "Full"
fi
```

**waybar battery module configuration:**
```json
// ~/.config/waybar/config
"battery": {
    "bat": "BAT0",
    "adapter": "AC",
    "interval": 30,
    "states": {
        "warning": 30,
        "critical": 15
    },
    "format": "{capacity}% {icon}",
    "format-charging": "{capacity}% ",
    "format-plugged": "{capacity}% ",
    "format-full": "Full ",
    "format-icons": ["", "", "", "", ""],
    "tooltip-format": "{timeTo} | {power:.1f}W | Health: {health:.0f}%"
}
```

### 78.9 Thermal Management

Thermal management prevents CPU throttling from degrading performance and protects
hardware longevity. The kernel's own thermal framework (CONFIG_THERMAL) handles basic
throttling, but additional userspace tools provide finer control and AMD/Intel-specific
TDP limits.

```bash
# Install sensor monitoring tools:
sudo pacman -S lm_sensors

# Detect available sensors:
sudo sensors-detect    # interactive; accept defaults for most systems

# Read temperatures:
sensors                 # current readings for all chips
watch -n 1 sensors      # live monitoring

# CPU-specific temp (usually easier):
cat /sys/class/thermal/thermal_zone*/temp   # values in millidegrees Celsius
# e.g., 45000 = 45°C
```

**`thermald` for Intel laptops:**
```bash
sudo pacman -S thermald
sudo systemctl enable --now thermald

# thermald uses Intel DPTF/RAPL data to proactively throttle before the hardware does
# This produces smoother thermal behavior vs. sudden hard throttling
```

**`s-tui` — TUI for thermal/CPU monitoring:**
```bash
sudo pacman -S s-tui   # or: paru -S s-tui
s-tui                   # interactive TUI with frequency, utilization, temp graphs
```

**AMD laptops — RyzenAdj for custom TDP:**
```bash
sudo pacman -S ryzenadj

# Set 15W total TDP (good for ultrabook battery life):
sudo ryzenadj --stapm-limit=15000 --slow-limit=15000 --fast-limit=15000

# Set 25W for balanced:
sudo ryzenadj --stapm-limit=25000 --slow-limit=25000 --fast-limit=25000

# Query current TDP values:
sudo ryzenadj --info

# View all adjustable parameters:
sudo ryzenadj --help
```

**Persistent RyzenAdj via systemd service:**
```ini
# /etc/systemd/system/ryzenadj.service
[Unit]
Description=RyzenAdj TDP Limits
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/ryzenadj --stapm-limit=15000 --slow-limit=15000 --fast-limit=15000
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable --now ryzenadj.service
```

**Intel RAPL power limits** (Intel laptops, kernel 5.x+):
```bash
# View current RAPL limits (values in µW):
cat /sys/class/powercap/intel-rapl:0/constraint_0_power_limit_uw   # PL1
cat /sys/class/powercap/intel-rapl:0/constraint_1_power_limit_uw   # PL2

# Set PL1 to 15W, PL2 to 20W (values in µW):
echo 15000000 | sudo tee /sys/class/powercap/intel-rapl:0/constraint_0_power_limit_uw
echo 20000000 | sudo tee /sys/class/powercap/intel-rapl:0/constraint_1_power_limit_uw
```

**Fan control** — for laptops with controllable fans:
```bash
sudo pacman -S nbfc-linux   # NoteBook FanControl, Linux port
sudo systemctl enable --now nbfc.service
nbfc config -l              # list known laptop configs
nbfc config -a "Lenovo ThinkPad X1 Carbon 6th"   # apply a config
nbfc status                 # current fan speed and temp
nbfc set -s 50              # set fan to 50%
nbfc set -a                 # re-enable automatic control
```

### 78.10 Putting It All Together: Example Battery Profile Script

For a riced Wayland setup, a single script or service that applies a coherent set of
settings on AC/battery transitions ties everything together. This example script can
be triggered by the udev rule from section 78.2 or called from Hyprland keybinds.

```bash
#!/bin/bash
# /usr/local/bin/power-mode
# Usage: power-mode [battery|ac|performance]
# Configures a complete power profile across all subsystems

MODE=${1:-battery}

case "$MODE" in
    battery)
        # CPU
        powerprofilesctl set power-saver 2>/dev/null || true
        # Screen
        brightnessctl set 40% >/dev/null 2>&1
        # Keyboard backlight off
        brightnessctl -d *::kbd_backlight set 0% >/dev/null 2>&1
        # Hyprland VFR (should already be on)
        hyprctl keyword misc:vfr true
        # Notify
        notify-send -i battery-low "Power Mode" "Battery saving mode active"
        ;;
    ac|balanced)
        powerprofilesctl set balanced 2>/dev/null || true
        brightnessctl set 70% >/dev/null 2>&1
        brightnessctl -d *::kbd_backlight set 50% >/dev/null 2>&1
        notify-send -i battery "Power Mode" "Balanced mode active"
        ;;
    performance)
        powerprofilesctl set performance 2>/dev/null || true
        brightnessctl set 100% >/dev/null 2>&1
        notify-send -i battery-full "Power Mode" "Performance mode active"
        ;;
esac
```

```bash
sudo chmod +x /usr/local/bin/power-mode

# Hyprland keybinds:
# bind = SUPER SHIFT, F9,  exec, /usr/local/bin/power-mode battery
# bind = SUPER SHIFT, F10, exec, /usr/local/bin/power-mode ac
# bind = SUPER SHIFT, F11, exec, /usr/local/bin/power-mode performance
```

## Troubleshooting

**Suspend doesn't work / system wakes immediately:**
```bash
# Find what's preventing sleep or causing immediate wake:
journalctl -b -1 | grep -i "suspend\|wake\|sleep"
# Check for wake events:
cat /proc/acpi/wakeup    # lists devices and their wake enable state
# Disable USB wake (common culprit):
echo disabled | sudo tee /proc/acpi/wakeup    # (use the device name from the file)
```

**Hyprlock doesn't engage before suspend:**
```bash
# Verify hypridle is running:
pgrep hypridle
# Check hypridle log:
journalctl --user -u hypridle -f
# Verify the before_sleep_cmd in hypridle.conf is correct
```

**Brightness keys not working on Wayland:**
```bash
# Check if the keys generate events:
sudo libinput debug-events | grep -i bright
# Check kernel driver:
ls /sys/class/backlight/
# If using intel_backlight and it's not responding, try acpi_video0:
brightnessctl -d acpi_video0 set 50%
# May need kernel parameter: acpi_backlight=vendor or acpi_backlight=native
```

**tlp-stat reports conflicts:**
```bash
sudo tlp-stat -s   # shows conflicts with power-profiles-daemon or other tools
# Disable conflicting services:
sudo systemctl disable --now power-profiles-daemon
sudo systemctl disable --now auto-cpufreq
sudo tlp start
```

**Battery not charging to 100% (stuck at threshold):**
```bash
# This is intentional if charge thresholds are set in tlp.conf
# To temporarily override and charge to 100%:
sudo tlp fullcharge BAT0   # charge to 100% this once
# Or to charge to threshold:
sudo tlp charge BAT0
```

**Hibernate fails or doesn't resume:**
```bash
# Check swap is active:
swapon --show
cat /proc/swaps

# Verify kernel resume parameter:
cat /proc/cmdline | grep resume

# Check initramfs has resume hook:
sudo lsinitcpio /boot/initramfs-linux.img | grep resume

# Check if hibernate is available:
systemctl hibernate   # look at the error output carefully
cat /sys/power/state  # should include 'disk'
```

**GPU high power draw at idle (Nvidia):**
```bash
# Nvidia on Wayland may not properly idle
# Check power state:
cat /sys/bus/pci/devices/0000:01:00.0/power/runtime_status
# Enable runtime PM for Nvidia (if using open/nouveau):
echo auto | sudo tee /sys/bus/pci/devices/0000:01:00.0/power/control
# For proprietary Nvidia driver, enable fine-grained power control:
# Options nvidia NVreg_DynamicPowerManagement=0x02
# Add to /etc/modprobe.d/nvidia.conf
```

**auto-cpufreq not applying expected governor:**
```bash
sudo auto-cpufreq --monitor   # watch live decisions
# Check current governor:
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
# If another service is overriding auto-cpufreq, disable it:
sudo systemctl status cpupower.service
```

---

*See also: Ch 22 (UPower D-Bus integration), Ch 53 (session startup and autostart),
Ch 60 (Hyprland idle management with hypridle), Ch 33 (display and monitor management).*

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
