# Chapter 81 — Bluetooth Management: bluetui, blueman, bluetoothctl

## Overview
Bluetooth on Linux uses BlueZ. This chapter covers pairing, managing audio
devices, and GUI/TUI tools for daily use in a tiling WM without a full DE.

## Sections

### 81.1 Stack

```
Bluetooth hardware → HCI → BlueZ (kernel + bluez daemon) → D-Bus
                                                             ↓
                                      bluetoothctl / blueman / bluetui
```

### 81.2 Installation

```bash
sudo pacman -S bluez bluez-utils
sudo systemctl enable --now bluetooth
```

**For audio profiles (A2DP, HFP):**
```bash
sudo pacman -S pipewire-bluetooth  # or: libspa-bluetooth
# Restart PipeWire after installing:
systemctl --user restart pipewire wireplumber
```

### 81.3 bluetoothctl — CLI

```bash
bluetoothctl

# Inside the prompt:
power on           # enable adapter
scan on            # start scanning (wait ~10 seconds)
devices            # list found devices
pair XX:XX:XX:XX:XX:XX
trust XX:XX:XX:XX:XX:XX
connect XX:XX:XX:XX:XX:XX
scan off
exit
```

**One-line connect to a known device:**
```bash
bluetoothctl connect XX:XX:XX:XX:XX:XX
```

### 81.4 bluetui — Terminal UI

```bash
paru -S bluetui
bluetui  # interactive TUI
```

bluetui provides a keyboard-driven TUI with device list, pairing, and connection status.

### 81.5 blueman — GTK GUI

```bash
sudo pacman -S blueman
blueman-manager  # full manager GUI
blueman-applet   # system tray applet
```

```conf
# hyprland.conf
exec-once = blueman-applet
```

blueman-applet appears in the system tray (requires Quickshell SystemTray or Waybar tray).
Right-click → connect to paired devices.

### 81.6 Auto-Connect on Login

```bash
# /etc/bluetooth/main.conf
[Policy]
AutoEnable=true

# or per-device trust:
bluetoothctl trust XX:XX:XX:XX:XX:XX
```

For headphones that don't auto-connect:
```bash
# In hyprland.conf exec-once (with delay for BT stack to start):
exec-once = sleep 3 && bluetoothctl connect XX:XX:XX:XX:XX:XX
```

### 81.7 Bluetooth Audio Profiles

```bash
# Check current profile
pactl list cards | grep -A 20 "bluez_card"

# Switch to A2DP (music, no mic)
pactl set-card-profile bluez_card.XX_XX_XX_XX_XX_XX a2dp-sink

# Switch to HFP (calls, with mic — lower quality)
pactl set-card-profile bluez_card.XX_XX_XX_XX_XX_XX headset-head-unit

# Or via wpctl (WirePlumber)
wpctl status  # find the card ID
```

### 81.8 Troubleshooting

```bash
# Check BlueZ status
systemctl status bluetooth
journalctl -u bluetooth -n 50

# Reset bluetooth adapter
sudo rfkill list bluetooth
sudo rfkill unblock bluetooth
bluetoothctl power off && bluetoothctl power on

# Fix "No default controller available"
sudo systemctl restart bluetooth

# A2DP not available (only HFP offered)
# → Ensure pipewire-bluetooth is installed
# → Restart PipeWire: systemctl --user restart pipewire wireplumber
```
