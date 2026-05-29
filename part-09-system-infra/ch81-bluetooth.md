# Chapter 81 — Bluetooth Management: bluetui, blueman, bluetoothctl

## Overview

Bluetooth on Linux is built on the BlueZ stack, which has been the dominant open-source Bluetooth implementation for well over a decade. In a minimal Wayland environment — a tiling window manager like Hyprland, Sway, or River, without a full desktop environment like GNOME or KDE — you lose the automatic Bluetooth tooling that DEs provide. This chapter covers everything you need to replace that functionality: the BlueZ stack itself, command-line tools, TUI and GUI front-ends, audio profile management, automated reconnection, and a comprehensive troubleshooting guide.

Unlike many "just install blueman" guides, this chapter treats Bluetooth as a subsystem you need to understand and control. You'll learn to manage devices from scripts, configure auto-connect behavior, profile-switch programmatically for podcasts versus calls, and diagnose the surprisingly varied failure modes of Bluetooth audio on Linux.

This chapter assumes you have PipeWire installed as your audio backend. If you're still on PulseAudio, most audio commands will differ; see Ch 79 for the PipeWire migration path. For session startup of these services, see Ch 53 on session management and exec-once patterns.

---

## 81.1 The BlueZ Stack

Understanding the full stack prevents a lot of confusion when troubleshooting. Bluetooth on Linux is not a single monolithic system — it's a layered architecture where each layer has distinct responsibilities.

```
Bluetooth hardware (USB dongle / PCIe card / embedded)
         ↓
   HCI (Host Controller Interface) — kernel driver
         ↓
   BlueZ kernel modules (btusb, btintel, etc.)
         ↓
   bluetoothd (userspace daemon, manages protocol stack)
         ↓
   D-Bus interface (org.bluez)
         ↓
┌────────────────────────────────────────────────────┐
│  bluetoothctl   bluetui   blueman   custom scripts │
└────────────────────────────────────────────────────┘
         ↓ (audio only)
   PipeWire / WirePlumber (via bluez-monitor plugin)
         ↓
   Audio outputs / sources
```

The `bluetoothd` daemon exposes the entire Bluetooth API over D-Bus. Every tool — whether bluetoothctl, blueman, or a Python script using `dbus-python` — talks to `bluetoothd` through this interface. This means all tools have the same underlying capabilities; they differ only in UX.

BlueZ uses profiles to define device capabilities. Key profiles you'll encounter:

| Profile | Full Name | Use Case |
|---------|-----------|----------|
| A2DP | Advanced Audio Distribution Profile | Stereo music, high quality, no mic |
| HFP | Hands-Free Profile | Calls, mic active, narrow-band audio |
| HSP | Headset Profile | Basic headset, legacy |
| AVRCP | Audio/Video Remote Control Profile | Media key passthrough |
| HID | Human Interface Device | Keyboards, mice, game controllers |
| PAN | Personal Area Network | Bluetooth tethering |
| OPP | Object Push Profile | File transfer |

On a Wayland/WM setup, A2DP and HFP are the profiles you'll manage most actively, particularly for wireless headphones.

---

## 81.2 Installation

BlueZ is split into the kernel-managed daemon and userspace utilities. Both are needed. The package names vary slightly across distributions.

### Arch Linux / Manjaro / EndeavourOS

```bash
sudo pacman -S bluez bluez-utils
sudo systemctl enable --now bluetooth
```

### Debian / Ubuntu / Pop!_OS

```bash
sudo apt install bluez bluez-tools
sudo systemctl enable --now bluetooth
```

### Fedora / RHEL-based

```bash
sudo dnf install bluez
sudo systemctl enable --now bluetooth
```

### Verifying the installation

After enabling the service, confirm the adapter is visible and the daemon is running:

```bash
# Check daemon status
systemctl status bluetooth

# Verify adapter is present
bluetoothctl show

# Check kernel modules are loaded
lsmod | grep -E "btusb|btintel|btbcm|btrsi"
```

The `bluetoothctl show` output will display the adapter's MAC address, name, and current power state. If no adapter is shown, see the Troubleshooting section.

### Audio profile support (A2DP, HFP)

BlueZ alone is not enough for audio. Bluetooth audio routing requires a PipeWire integration package that bridges BlueZ profiles to the PipeWire graph. Without this, your headphones may pair but produce no sound.

```bash
# Arch Linux
sudo pacman -S pipewire-bluetooth

# Debian / Ubuntu (PipeWire ships this differently)
sudo apt install libspa-0.2-bluetooth

# Fedora
sudo dnf install pipewire-codec-aptx pipewire-libs
```

After installing the Bluetooth audio bridge, restart the user PipeWire session:

```bash
systemctl --user restart pipewire pipewire-pulse wireplumber
```

Confirm PipeWire sees the Bluetooth backend:

```bash
pw-cli info all | grep -i bluez
# or
wpctl status | grep -A 5 "Bluetooth"
```

---

## 81.3 bluetoothctl — The Primary CLI

`bluetoothctl` is the official BlueZ command-line front-end. It is the most important tool in this chapter because it underlies everything else. Understanding it well means you can script any Bluetooth operation and diagnose anything the GUIs obscure.

### Interactive mode

```bash
bluetoothctl
```

Inside the prompt, the essential commands:

```
[bluetooth]# power on                    # Enable the adapter
[bluetooth]# agent on                    # Enable pairing agent (accepts PIN prompts)
[bluetooth]# default-agent              # Make this the default pairing agent
[bluetooth]# scan on                     # Begin discovery
[bluetooth]# devices                     # List discovered + paired devices
[bluetooth]# pair XX:XX:XX:XX:XX:XX     # Initiate pairing
[bluetooth]# trust XX:XX:XX:XX:XX:XX    # Mark device trusted (enables auto-connect)
[bluetooth]# connect XX:XX:XX:XX:XX:XX  # Connect to a paired device
[bluetooth]# disconnect XX:XX:XX:XX:XX:XX
[bluetooth]# remove XX:XX:XX:XX:XX:XX   # Unpair and forget device
[bluetooth]# scan off
[bluetooth]# exit
```

### Non-interactive (scriptable) mode

`bluetoothctl` accepts commands via stdin or as a piped sequence, which is essential for scripting:

```bash
# One-liner: connect to a known device
bluetoothctl connect AA:BB:CC:DD:EE:FF

# Power cycle the adapter
bluetoothctl power off
bluetoothctl power on

# Pipe multiple commands (useful in scripts)
echo -e "power on\nagent on\ndefault-agent\nscan on" | bluetoothctl

# Show detailed info about a paired device
bluetoothctl info AA:BB:CC:DD:EE:FF
```

The output of `bluetoothctl info` is particularly useful for scripting — it shows UUID, connected state, trusted flag, and RSSI:

```
Device AA:BB:CC:DD:EE:FF (public)
        Name: My Headphones
        Alias: My Headphones
        Class: 0x00240414
        Icon: audio-headset
        Paired: yes
        Trusted: yes
        Blocked: no
        Connected: yes
        UUIDs: Advanced Audio Distribu.. (0000110d-0000-1000-8000-00805f9b34fb)
               Audio Sink              (0000110b-0000-1000-8000-00805f9b34fb)
               Handsfree               (0000111e-0000-1000-8000-00805f9b34fb)
```

### Scripted full pairing workflow

This script handles scanning and pairing in an automated fashion — useful for headless setups or provisioning scripts:

```bash
#!/usr/bin/env bash
# bt-pair.sh — Scan and pair a device by name substring
# Usage: bt-pair.sh "My Headphones"

TARGET_NAME="$1"
TIMEOUT=30

bluetoothctl power on
bluetoothctl agent on

# Start scan and collect output for TIMEOUT seconds
DEVICE_MAC=$(timeout "$TIMEOUT" bluetoothctl scan on 2>&1 | \
  grep -m 1 "$TARGET_NAME" | \
  grep -oE '([0-9A-F]{2}:){5}[0-9A-F]{2}')

if [[ -z "$DEVICE_MAC" ]]; then
  echo "Device '$TARGET_NAME' not found within ${TIMEOUT}s"
  bluetoothctl scan off
  exit 1
fi

echo "Found: $DEVICE_MAC — pairing..."
bluetoothctl scan off
bluetoothctl pair "$DEVICE_MAC"
bluetoothctl trust "$DEVICE_MAC"
bluetoothctl connect "$DEVICE_MAC"
echo "Done."
```

### Listing all paired devices programmatically

```bash
# List only paired devices with their MAC addresses
bluetoothctl devices Paired

# Extract just MACs for use in scripts
bluetoothctl devices Paired | awk '{print $2}'

# Check whether a specific device is connected
HEADPHONE_MAC="AA:BB:CC:DD:EE:FF"
CONNECTED=$(bluetoothctl info "$HEADPHONE_MAC" | grep "Connected:" | awk '{print $2}')
echo "Connected: $CONNECTED"
```

---

## 81.4 bluetui — Terminal UI

`bluetui` is a keyboard-driven TUI (terminal user interface) built in Rust. It wraps `bluetoothctl` in a ncurses-style interface that makes scanning, pairing, and connecting intuitive without a graphical environment. It's particularly well-suited for a tmux or zellij pane in a tiling WM workflow.

### Installation

```bash
# Arch Linux (AUR)
paru -S bluetui
# or:
yay -S bluetui

# From source (requires Rust toolchain)
git clone https://github.com/pythops/bluetui
cd bluetui
cargo build --release
sudo install -m 755 target/release/bluetui /usr/local/bin/
```

### Usage

```bash
bluetui
```

The interface is divided into panes: Adapter info at the top, paired Devices, and Scanned Devices. Navigation:

| Key | Action |
|-----|--------|
| `Tab` / `Shift+Tab` | Switch between panes |
| `↑` / `↓` | Navigate device list |
| `p` | Pair selected device |
| `c` | Connect / Disconnect selected device |
| `t` | Toggle trust on selected device |
| `d` | Delete / unpair device |
| `s` | Start / stop scan |
| `q` | Quit |
| `?` | Show help |

bluetui refreshes the device list in real-time as BlueZ events arrive. This makes it more responsive than running `bluetoothctl` commands one by one for device discovery. For a system tray-less Hyprland setup where you want quick Bluetooth management, a keybinding to open bluetui in a floating terminal is a clean workflow:

```conf
# hyprland.conf
bind = $mainMod SHIFT, B, exec, kitty --class="btmanager" bluetui
windowrulev2 = float,class:(btmanager)
windowrulev2 = size 800 500,class:(btmanager)
windowrulev2 = center,class:(btmanager)
```

---

## 81.5 blueman — GTK GUI

blueman is a full GTK3 Bluetooth manager targeting desktop environments, but it works well on standalone WMs. It provides a graphical device manager and a system tray applet. The applet integrates with any tray host: Waybar's tray module, Quickshell's SystemTray, or `nm-applet`-style trays.

### Installation

```bash
# Arch Linux
sudo pacman -S blueman

# Debian / Ubuntu
sudo apt install blueman

# Fedora
sudo dnf install blueman
```

### Components

```bash
blueman-manager   # Full device manager window
blueman-applet    # System tray icon + quick-connect menu
blueman-adapters  # Adapter settings (visibility, name, etc.)
blueman-assistant # First-time pairing wizard
blueman-sendto    # File transfer via OPP
```

### Autostart in Hyprland

```conf
# ~/.config/hypr/hyprland.conf
exec-once = blueman-applet
```

For Sway:

```conf
# ~/.config/sway/config
exec --no-startup-id blueman-applet
```

The tray icon requires a working tray. In Waybar:

```json
// ~/.config/waybar/config
{
  "modules-right": ["tray", "network", "battery", "clock"],
  "tray": {
    "spacing": 10
  }
}
```

### Disabling blueman's power management interference

blueman has an aggressive power management feature that can interfere with other Bluetooth tools. If you're using bluetoothctl or bluetui alongside blueman, disable the plugin:

```bash
# Edit blueman's local config
mkdir -p ~/.config/blueman
cat > ~/.config/blueman/blueman.conf << 'EOF'
[plugins]
PowerManager = false
EOF
```

Or via the GUI: blueman-manager → Edit → Plugins → uncheck PowerManager.

### Setting blueman as the default file transfer handler

```bash
# Associate blueman-sendto with Bluetooth MIME type
xdg-mime default blueman-sendto.desktop x-scheme-handler/bluetooth
```

---

## 81.6 Auto-Connect on Login

One of the most common complaints about Bluetooth on a WM setup is that trusted devices don't reconnect after reboot. There are two layers to configure: the BlueZ policy layer (which handles reconnection when the device initiates) and an active connect call during session startup (which handles devices that wait for the host to initiate).

### BlueZ global auto-enable policy

```ini
# /etc/bluetooth/main.conf
[Policy]
AutoEnable=true

[General]
# Optional: improve A2DP stability
FastConnectable=true
```

After editing:

```bash
sudo systemctl restart bluetooth
```

`AutoEnable=true` powers on the adapter after every reboot and after `rfkill` events, which ensures BlueZ is always ready to handle incoming connection requests from trusted devices.

### Per-device trust

A device must be both `paired` and `trusted` for BlueZ to accept its reconnection attempts:

```bash
bluetoothctl trust AA:BB:CC:DD:EE:FF
```

Verify:

```bash
bluetoothctl info AA:BB:CC:DD:EE:FF | grep -E "Paired|Trusted"
```

### Proactive connect on session start

Many Bluetooth devices (particularly headphones) sit passively and wait for the host. For these, you need to actively initiate the connection during session startup. The delay is necessary because `bluetoothd` takes a few seconds to fully initialize after login.

```bash
# ~/.config/hypr/hyprland.conf
exec-once = sleep 4 && bluetoothctl connect AA:BB:CC:DD:EE:FF
```

For more reliability, use a script that retries:

```bash
#!/usr/bin/env bash
# ~/.local/bin/bt-autoconnect.sh
# Attempt to connect a Bluetooth device with retries
# Usage: bt-autoconnect.sh AA:BB:CC:DD:EE:FF [max_attempts]

MAC="$1"
MAX="${2:-5}"
DELAY=3

for i in $(seq 1 "$MAX"); do
  echo "Attempt $i/$MAX: connecting $MAC..."
  bluetoothctl connect "$MAC" && exit 0
  sleep "$DELAY"
done

echo "Failed to connect $MAC after $MAX attempts"
exit 1
```

```bash
chmod +x ~/.local/bin/bt-autoconnect.sh
```

```conf
# hyprland.conf
exec-once = sleep 4 && ~/.local/bin/bt-autoconnect.sh AA:BB:CC:DD:EE:FF
```

### Systemd user service for auto-connect

For a cleaner solution, use a systemd user service with a `bluetooth.target` dependency:

```ini
# ~/.config/systemd/user/bt-headphones.service
[Unit]
Description=Auto-connect Bluetooth headphones
After=bluetooth.target
Wants=bluetooth.target

[Service]
Type=oneshot
ExecStartPre=/bin/sleep 5
ExecStart=/usr/bin/bluetoothctl connect AA:BB:CC:DD:EE:FF
RemainAfterExit=no

[Install]
WantedBy=default.target
```

```bash
systemctl --user enable bt-headphones.service
systemctl --user start bt-headphones.service
```

---

## 81.7 Bluetooth Audio Profiles

Bluetooth headsets support multiple audio profiles with different trade-offs. Switching between them on Linux is done via PipeWire/WirePlumber or directly via `pactl`. Understanding which profile to use and when is essential for daily use.

| Profile | Codec | Sample Rate | Latency | Mic Available |
|---------|-------|-------------|---------|---------------|
| A2DP (SBC) | SBC | 44.1kHz | ~150ms | No |
| A2DP (AAC) | AAC | 44.1–48kHz | ~150ms | No |
| A2DP (aptX) | aptX | 44.1kHz | ~80ms | No |
| A2DP (LDAC) | LDAC | up to 96kHz | ~150ms | No |
| HFP (mSBC) | mSBC | 16kHz | ~50ms | Yes |
| HFP (CVSD) | CVSD | 8kHz | ~50ms | Yes |

### Listing cards and current profile

```bash
# Show all cards — Bluetooth devices appear as bluez_card.*
pactl list cards

# Filter for Bluetooth card
pactl list cards | grep -A 30 "bluez_card"

# Or with WirePlumber
wpctl status
```

The card name uses underscores instead of colons in the MAC address:
`bluez_card.AA_BB_CC_DD_EE_FF`

### Switching profiles with pactl

```bash
# Get the exact card name
CARD=$(pactl list cards short | grep bluez | awk '{print $2}')

# Switch to A2DP (high quality, no mic)
pactl set-card-profile "$CARD" a2dp-sink

# Switch to HFP with mSBC codec (calls, with mic)
pactl set-card-profile "$CARD" headset-head-unit-msbc

# Switch to HFP with CVSD (older devices, wider compatibility)
pactl set-card-profile "$CARD" headset-head-unit

# List all available profiles for this card
pactl list cards | grep -A 50 "bluez_card" | grep "profile:"
```

### Switching profiles with WirePlumber

```bash
# List available profiles
wpctl inspect $(wpctl status | grep -i "bluetooth\|headphone" | head -1 | awk '{print $2}')

# Profile switching via wpctl (WirePlumber 0.4.11+)
# First find the node ID
wpctl status | grep -i "headphones"

# Set default sink
wpctl set-default SINK_ID
```

### Automated profile switcher script

This script toggles between A2DP and HFP, useful for binding to a hotkey:

```bash
#!/usr/bin/env bash
# ~/.local/bin/bt-profile-toggle.sh
# Toggle Bluetooth headset between A2DP and HFP

CARD=$(pactl list cards short | grep bluez | awk '{print $2}' | head -1)
if [[ -z "$CARD" ]]; then
  notify-send "Bluetooth" "No Bluetooth audio device connected"
  exit 1
fi

CURRENT=$(pactl list cards | grep -A 50 "$CARD" | grep "Active Profile:" | awk '{print $NF}')

if [[ "$CURRENT" == *"a2dp"* ]]; then
  pactl set-card-profile "$CARD" headset-head-unit-msbc
  notify-send "Bluetooth Audio" "Switched to HFP (mic enabled)"
else
  pactl set-card-profile "$CARD" a2dp-sink
  notify-send "Bluetooth Audio" "Switched to A2DP (high quality)"
fi
```

```conf
# hyprland.conf — bind toggle to Super+Alt+B
bind = $mainMod ALT, B, exec, ~/.local/bin/bt-profile-toggle.sh
```

### Enabling higher-quality codecs (LDAC, aptX)

By default on Arch, only SBC is guaranteed. For LDAC and aptX support:

```bash
# Arch Linux — install codec support
paru -S pipewire-aptx   # aptX and aptX HD
# LDAC is included in pipewire-bluetooth on recent versions

# Check available codecs after restart
pactl list cards | grep -i "codec\|ldac\|aptx\|aac"
```

Restart PipeWire after installing:

```bash
systemctl --user restart pipewire wireplumber
```

---

## 81.8 D-Bus Direct Interaction

For advanced scripting without spawning `bluetoothctl`, you can talk to BlueZ directly over D-Bus. This is useful for custom scripts, status bar integrations, and event-driven automation.

### Using busctl (systemd)

```bash
# List all BlueZ managed objects
busctl tree org.bluez

# Get adapter properties
busctl get-property org.bluez /org/bluez/hci0 org.bluez.Adapter1 Powered
busctl get-property org.bluez /org/bluez/hci0 org.bluez.Adapter1 Discovering

# Power on via busctl
busctl set-property org.bluez /org/bluez/hci0 org.bluez.Adapter1 Powered b true

# Get device Connected state
MAC_PATH=$(echo "AA:BB:CC:DD:EE:FF" | tr ':' '_')
busctl get-property org.bluez /org/bluez/hci0/dev_${MAC_PATH} org.bluez.Device1 Connected
```

### Python D-Bus script for Waybar integration

This script outputs JSON for Waybar's custom module, showing the first connected Bluetooth device:

```python
#!/usr/bin/env python3
# ~/.local/bin/bt-waybar.py
# Output Bluetooth status for Waybar custom module
import json
import subprocess

def get_connected_devices():
    result = subprocess.run(
        ["bluetoothctl", "devices", "Connected"],
        capture_output=True, text=True
    )
    devices = []
    for line in result.stdout.strip().splitlines():
        parts = line.split(" ", 2)
        if len(parts) >= 3:
            devices.append({"mac": parts[1], "name": parts[2]})
    return devices

devices = get_connected_devices()
if devices:
    names = ", ".join(d["name"] for d in devices)
    print(json.dumps({
        "text": f"󰂱 {names}",
        "tooltip": "\n".join(f"{d['mac']} — {d['name']}" for d in devices),
        "class": "connected"
    }))
else:
    print(json.dumps({
        "text": "󰂲",
        "tooltip": "No Bluetooth devices connected",
        "class": "disconnected"
    }))
```

```json
// ~/.config/waybar/config — custom Bluetooth module
"custom/bluetooth": {
  "exec": "~/.local/bin/bt-waybar.py",
  "interval": 10,
  "return-type": "json",
  "on-click": "blueman-manager"
}
```

---

## 81.9 rfkill and Kernel-Level Blocking

`rfkill` is the kernel interface for hard- and soft-blocking wireless interfaces. Bluetooth can be blocked at this level independently of BlueZ.

```bash
# List all rf devices with their block status
rfkill list

# Expected output for unblocked Bluetooth:
# 1: hci0: Bluetooth
#         Soft blocked: no
#         Hard blocked: no

# Unblock Bluetooth if soft-blocked
rfkill unblock bluetooth

# Unblock all wireless interfaces
rfkill unblock all

# Block Bluetooth (useful for airplane mode scripts)
rfkill block bluetooth
```

If `Hard blocked: yes` appears, this is a hardware kill switch (laptop keyboard button or BIOS setting). Software cannot override a hard block.

### udev rule to auto-unblock on resume

Laptops sometimes re-block Bluetooth after suspend/resume. A udev rule or systemd hook can address this:

```ini
# /etc/systemd/system/rfkill-bluetooth.service
[Unit]
Description=Unblock Bluetooth on resume
After=suspend.target hibernate.target

[Service]
Type=oneshot
ExecStart=/usr/sbin/rfkill unblock bluetooth

[Install]
WantedBy=suspend.target hibernate.target
```

```bash
sudo systemctl enable rfkill-bluetooth.service
```

---

## Troubleshooting

### No Bluetooth adapter found

```bash
# Check if adapter is physically present
lsusb | grep -i bluetooth
lspci | grep -i bluetooth

# Check kernel modules
dmesg | grep -i bluetooth
lsmod | grep bt

# Force load common modules
sudo modprobe btusb
sudo modprobe bluetooth

# Check rfkill
rfkill list bluetooth
```

If `lsusb`/`lspci` shows the adapter but `bluetoothctl show` shows nothing, the issue is a missing or blacklisted kernel module. Check `dmesg` immediately after plugging in (for USB dongles) or after boot for built-in adapters.

### bluetoothd fails to start

```bash
systemctl status bluetooth
journalctl -u bluetooth -n 100 --no-pager
```

Common causes and fixes:

| Error in journal | Fix |
|------------------|-----|
| `Failed to obtain handles for interface` | `sudo modprobe btusb && systemctl restart bluetooth` |
| `Bluetooth daemon cannot start` | Check `/var/lib/bluetooth/` permissions: `sudo chown -R root:root /var/lib/bluetooth` |
| `sap-server: Operation not permitted` | Add `--noplugin=sap` to `/etc/bluetooth/main.conf` under `[General] ExperimentalFeatures` or disable SAP plugin |

### Device pairs but won't connect

```bash
# Remove and re-pair
bluetoothctl remove AA:BB:CC:DD:EE:FF
# Put device in pairing mode, then:
bluetoothctl pair AA:BB:CC:DD:EE:FF
bluetoothctl trust AA:BB:CC:DD:EE:FF
bluetoothctl connect AA:BB:CC:DD:EE:FF
```

If the device connects momentarily then disconnects, check for an auth rejection in the journal:

```bash
journalctl -u bluetooth -f
```

### A2DP not available, only HFP offered

This is almost always a missing `pipewire-bluetooth` (or `libspa-bluetooth`) package, or WirePlumber hasn't loaded the Bluetooth monitor:

```bash
# Verify package installed
pacman -Q pipewire-bluetooth 2>/dev/null || echo "NOT INSTALLED"

# Verify WirePlumber loads BT monitor
journalctl --user -u wireplumber | grep -i bluez

# Restart the full audio stack
systemctl --user restart pipewire pipewire-pulse wireplumber

# Re-connect the device after restart
bluetoothctl disconnect AA:BB:CC:DD:EE:FF
sleep 2
bluetoothctl connect AA:BB:CC:DD:EE:FF
```

### Audio cuts out / stutters

Bluetooth audio stuttering on Linux is usually caused by Wi-Fi/Bluetooth RF interference (both use 2.4GHz) or inadequate PipeWire buffer settings.

```bash
# Check if Wi-Fi is on the same band — 5GHz Wi-Fi avoids conflict
iw dev wlan0 info | grep channel

# Increase PipeWire quantum (buffer size) for Bluetooth
mkdir -p ~/.config/pipewire/pipewire.conf.d/
cat > ~/.config/pipewire/pipewire.conf.d/10-bluetooth-latency.conf << 'EOF'
context.properties = {
  default.clock.min-quantum = 1024
}
EOF
systemctl --user restart pipewire wireplumber
```

### Adapter disappears after suspend

```bash
# Immediate fix
sudo rfkill unblock bluetooth
sudo systemctl restart bluetooth

# For Intel adapters, the btintel module sometimes needs a reload
sudo rmmod btintel btusb
sudo modprobe btusb btintel
sudo systemctl restart bluetooth
```

For persistent fix, use the systemd resume hook from section 81.9.

### Reset all Bluetooth state (nuclear option)

When device pairing state is corrupted and nothing else works:

```bash
sudo systemctl stop bluetooth
sudo rm -rf /var/lib/bluetooth/
sudo systemctl start bluetooth
# All devices must be re-paired from scratch
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
