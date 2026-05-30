# Chapter 119 — Virtual and Headless Monitors

## Overview

Virtual monitors — outputs that exist in the compositor but have no physical display connected — solve several real problems: a second "screen" for a remote desktop session, a persistent workspace when a laptop's external monitor is unplugged, an offscreen render target for OBS scene composition, or a stable layout for a headless CI compositor. Each compositor has its own mechanism for creating virtual outputs, and the `wlr-virtual-output-manager-unstable-v1` protocol provides a compositor-independent path for tools that need one.

**Cross-references:** Ch 33 — kanshi and display configuration. Ch 80 — remote desktop (wayvnc + virtual output). Ch 41 — multi-monitor and HiDPI. Ch 85 — headless compositor for testing (`WLR_BACKENDS=headless`).

---

## 119.1 Use Cases

| Use case | Tool | Notes |
|---|---|---|
| Persistent workspace when monitor unplugged | Compositor native | Keep apps on virtual output, re-attach when monitor returns |
| Remote desktop target | wayvnc + virtual output | VNC client connects to a virtual screen |
| OBS scene composition | wlr-virtual-output + OBS | Arrange scenes on a virtual screen |
| Headless CI testing | `WLR_BACKENDS=headless` | Full compositor, no real display |
| Mirror output | Compositor `mirror=` | Copy one output's content to another |

---

## 119.2 Hyprland Virtual Monitors

### Defining a Persistent Virtual Monitor

```ini
# ~/.config/hypr/monitors.conf

# Real monitors
monitor = DP-1, 1920x1080@144, 0x0, 1
monitor = HDMI-A-1, 2560x1440@60, 1920x0, 1

# Virtual monitor — always present even when no display connected
monitor = HEADLESS-1, 1920x1080@60, 3840x0, 1

# Catch-all: any unknown display gets auto-configured
monitor = , preferred, auto, 1
```

Assign workspaces to the virtual monitor:
```ini
workspace = 9,  monitor:HEADLESS-1, default:true
workspace = 10, monitor:HEADLESS-1
```

### Creating a Virtual Monitor at Runtime

```bash
# Create via IPC (no config change required)
hyprctl output create headless

# List outputs (shows new HEADLESS-N)
hyprctl monitors

# Move a workspace to the virtual monitor
hyprctl dispatch moveworkspacetomonitor 9 HEADLESS-1

# Remove the virtual monitor
hyprctl output remove HEADLESS-1
```

### Mirror Mode

```ini
# ~/.config/hypr/monitors.conf
# Mirror DP-1 on HDMI-A-1 (presentation to projector)
monitor = DP-1,   1920x1080@60, 0x0, 1
monitor = HDMI-A-1, 1920x1080@60, 0x0, 1, mirror, DP-1
```

---

## 119.3 Sway Virtual Outputs

```bash
# Create a virtual output via IPC (requires sway-ipc-create_output)
swaymsg create_output

# Move workspaces to the virtual output
swaymsg "workspace 9, move workspace to output HEADLESS-1"

# List outputs (includes HEADLESS-1)
swaymsg -t get_outputs

# Remove
swaymsg "output HEADLESS-1 disable"
```

For persistent virtual outputs in Sway config:
```
# ~/.config/sway/config
# Virtual output — no real hardware needed
output HEADLESS-1 resolution 1920x1080 position 1920,0
```

---

## 119.4 wlr-virtual-output-manager Protocol

`zwlr_virtual_output_manager_v1` is a wlroots protocol (not yet stable/standardized) that allows any Wayland client to create virtual compositor outputs programmatically. The standalone `wlr-virtual-output` tool uses it:

```bash
# Install
yay -S wlr-virtual-output   # AUR

# Create a virtual 1920x1080 output
wlr-virtual-output create --name VIRTUAL-1 --width 1920 --height 1080 --refresh 60

# Remove it
wlr-virtual-output remove VIRTUAL-1
```

This tool works with any wlroots-based compositor that exposes `zwlr_virtual_output_manager_v1`: Sway, Hyprland (with experimental protocols enabled), River, labwc.

---

## 119.5 Virtual Output for Remote Desktop (wayvnc)

The standard pattern for a remote desktop target: create a virtual output, point wayvnc at it, connect from a VNC client.

```bash
# 1. Create virtual output (Hyprland)
hyprctl output create headless
# Note the name: HEADLESS-1

# 2. Move desired workspaces to virtual output
hyprctl dispatch moveworkspacetomonitor 9 HEADLESS-1
hyprctl dispatch moveworkspacetomonitor 10 HEADLESS-1

# 3. Start wayvnc on the virtual output
wayvnc --output HEADLESS-1 0.0.0.0 5900

# 4. Connect from another machine
vncviewer 192.168.1.100:5900
# or: tigervnc, remmina, etc.
```

For persistent remote desktop via systemd:

```ini
# ~/.config/systemd/user/wayvnc.service
[Unit]
Description=wayvnc remote desktop
After=graphical-session.target

[Service]
ExecStartPre=hyprctl output create headless
ExecStart=wayvnc --output HEADLESS-1 0.0.0.0 5900
ExecStopPost=hyprctl output remove HEADLESS-1
Restart=on-failure

[Install]
WantedBy=graphical-session.target
```

---

## 119.6 Headless Compositor (No Physical Display)

For CI testing, automated screenshot generation, or server-side rendering:

```bash
# Run Hyprland in headless mode (no real display required)
WLR_BACKENDS=drm,libinput Hyprland &  # normal
# vs
WLR_BACKENDS=headless WLR_RENDERER=pixman Hyprland &  # fully headless

# Or with a DRM virtual device (requires kernel module)
sudo modprobe vkms   # Virtual Kernel Mode Setting
WLR_BACKENDS=drm Hyprland &   # uses /dev/dri/card0 (vkms)
```

The `vkms` kernel module creates a virtual DRM device that behaves like a real GPU. The compositor gets a real rendering pipeline, enabling hardware acceleration tests without physical hardware.

---

## 119.7 Persistent Layout on Monitor Unplug

A common laptop use case: external monitor is primary, laptop lid closed. When the external monitor is unplugged (e.g., taking the laptop to a meeting), you want windows preserved, not destroyed.

```bash
#!/bin/bash
# ~/.local/bin/monitor-hotplug
# Run via udev rule or kanshi on monitor events

if hyprctl monitors | grep -q "HEADLESS-1"; then
    # Already have virtual monitor
    :
else
    # Create virtual monitor when external monitor disconnects
    hyprctl output create headless
    hyprctl dispatch moveworkspacetomonitor 1 HEADLESS-1
    hyprctl dispatch moveworkspacetomonitor 2 HEADLESS-1
fi
```

```ini
# kanshi config — create virtual output when DP-1 disconnects
profile docked {
    output DP-1 enable resolution 2560x1440 position 0,0
    output eDP-1 disable
}

profile undocked {
    output eDP-1 enable resolution 1920x1080 position 0,0
    # Virtual output created via exec
    exec hyprctl output create headless
}
```

---

## 119.8 Troubleshooting

### `hyprctl output create headless` returns error

Ensure `allow_tearing = false` and no explicit backend restriction. On some setups, add to hyprland.conf:
```ini
misc {
    vfr = true
    vrr = 0
}
```

### Virtual output appears but no windows move to it

Move windows explicitly via IPC:
```bash
hyprctl dispatch movewindow mon:HEADLESS-1
# or move workspace:
hyprctl dispatch moveworkspacetomonitor 9 HEADLESS-1
```

### wayvnc shows blank screen

The workspace may not have been moved to the virtual output before wayvnc started. Check that workspaces are on `HEADLESS-1` before connecting:
```bash
hyprctl workspaces | grep HEADLESS
```
