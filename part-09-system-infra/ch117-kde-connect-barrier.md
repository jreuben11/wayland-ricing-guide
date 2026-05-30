# Chapter 117 — Multi-Device Integration: KDE Connect and Barrier/InputLeap

## Contents

- [Overview](#overview)
- [117.1 KDE Connect](#1171-kde-connect)
  - [Installation](#installation)
  - [Session Startup](#session-startup)
  - [Device Pairing](#device-pairing)
  - [Clipboard Sync](#clipboard-sync)
  - [Notification Mirroring](#notification-mirroring)
  - [Remote Touchpad/Keyboard](#remote-touchpadkeyboard)
  - [File Transfer](#file-transfer)
  - [Media Controls](#media-controls)
  - [GSConnect (GNOME Shell Extension)](#gsconnect-gnome-shell-extension)
- [117.2 Barrier / InputLeap](#1172-barrier-inputleap)
  - [The Wayland Problem](#the-wayland-problem)
  - [Installation](#installation)
  - [Server Configuration (machine with keyboard/mouse)](#server-configuration-machine-with-keyboardmouse)
  - [Client Configuration (machine being controlled)](#client-configuration-machine-being-controlled)
  - [Wayland Input Injection: uinput Method](#wayland-input-injection-uinput-method)
  - [Wayland Input Injection: Virtual Input Protocol](#wayland-input-injection-virtual-input-protocol)
  - [Autostart](#autostart)
  - [Troubleshooting](#troubleshooting)

---


## Overview

Two categories of multi-device tools fill different needs on a riced Wayland desktop. **KDE Connect** links your Linux desktop to a phone: notification mirroring, clipboard sync, file transfer, remote touchpad/keyboard, and media controls. **Barrier** (now forked as **InputLeap**) links multiple computers together, sharing a single keyboard and mouse across machines over a network — a software KVM switch.

Both require workarounds on Wayland because neither X11's global pointer control nor X11's global keyboard grab is available. This chapter covers working configurations for both tools in 2024.

**Cross-references:** Ch 32 — Wayland clipboard (used by KDE Connect clipboard sync). Ch 43 — input customization (overlaps with InputLeap's input interception). Ch 61 — screen sharing (KDE Connect remote input uses similar portal access).

---

## 117.1 KDE Connect

KDE Connect is a protocol and application suite for Android and Linux. On Wayland, it uses D-Bus, network sockets, and xdg-desktop-portal for features that require compositor access.

### Installation

```bash
# Arch — full package including daemon and optional indicator
sudo pacman -S kdeconnect

# Ubuntu 24.04+
sudo apt install kdeconnect

# Android: install KDE Connect from F-Droid or Google Play
```

The desktop daemon is `kdeconnectd`. The CLI tool is `kdeconnect-cli`. There is also `kdeconnect-app` (Qt GUI) and the GNOME Shell extension **GSConnect** (for GNOME-based setups).

### Session Startup

```bash
# Hyprland / Sway / any compositor
exec-once = /usr/lib/kdeconnect/kdeconnected
# or via systemd user unit (recommended):
systemctl --user enable --now kdeconnect
```

### Device Pairing

```bash
# List discoverable devices
kdeconnect-cli --list-available

# Pair by device ID
kdeconnect-cli --pair --device DEVICE_ID

# Accept pairing on phone (notification appears on Android)

# Verify paired devices
kdeconnect-cli --list-devices
```

Pairing requires both devices on the same local network. On isolated networks or VPNs, add the phone's IP manually:
```bash
kdeconnect-cli --refresh   # trigger mDNS rediscovery
```

### Clipboard Sync

KDE Connect clipboard sync works on Wayland via the `zwlr-data-control-v1` protocol (see Ch 125):

```bash
# Send phone clipboard → desktop
kdeconnect-cli --device DEVICE_ID --share-clipboard "text to send"

# Get desktop clipboard → phone
kdeconnect-cli --device DEVICE_ID --receive-clipboard
```

For automatic bidirectional sync, enable the "Clipboard sync" plugin in KDE Connect settings (GUI) or:
```bash
kdeconnect-cli --device DEVICE_ID --plugin clipboard --enable
```

### Notification Mirroring

Phone notifications appear as desktop notifications via the freedesktop notification daemon (mako, dunst, swaync). Ensure `org.freedesktop.Notifications` is available:

```bash
# Test that your notification daemon is running
notify-send "Test" "From kdeconnect"

# Check KDE Connect notification plugin
kdeconnect-cli --device DEVICE_ID --plugin notifications --enable
```

### Remote Touchpad/Keyboard

This is the feature most affected by Wayland restrictions. KDE Connect's remote input uses `org.freedesktop.portal.RemoteDesktop` (xdg-desktop-portal):

```bash
# Verify portal support
busctl --user introspect org.freedesktop.portal.Desktop \
    /org/freedesktop/portal/desktop \
    org.freedesktop.portal.RemoteDesktop
```

Required portals for compositors:
- **Hyprland**: `xdg-desktop-portal-hyprland`
- **Sway**: `xdg-desktop-portal-wlr`
- **GNOME**: `xdg-desktop-portal-gnome` (built-in)
- **KDE**: `xdg-desktop-portal-kde` (built-in)

```bash
# Install the Hyprland portal
sudo pacman -S xdg-desktop-portal-hyprland

# Ensure it's running
systemctl --user status xdg-desktop-portal-hyprland
```

### File Transfer

```bash
# Send file to phone
kdeconnect-cli --device DEVICE_ID --share /path/to/file.pdf

# List phone files (if SFTP plugin enabled)
kdeconnect-cli --device DEVICE_ID --mount
ls /run/user/1000/kdeconnect/DEVICE_ID/

# Unmount
kdeconnect-cli --device DEVICE_ID --unmount
```

### Media Controls

KDE Connect's media control plugin mirrors the desktop's MPRIS player to the phone and allows phone volume buttons to control desktop volume:

```bash
# Show active MPRIS players visible to KDE Connect
kdeconnect-cli --device DEVICE_ID --plugin mpriscontrol

# Send play/pause from CLI (phone does this via the app)
kdeconnect-cli --device DEVICE_ID --play-pause
kdeconnect-cli --device DEVICE_ID --next-song
```

### GSConnect (GNOME Shell Extension)

On GNOME Wayland, **GSConnect** is the recommended frontend — it integrates KDE Connect into the GNOME Shell top bar, system menu, and file manager:

```bash
# Install from extensions.gnome.org or:
yay -S gnome-shell-extension-gsconnect
gnome-extensions enable gsconnect@andyholmes.github.io
```

GSConnect uses the same KDE Connect protocol and pairs with the same Android app.

---

## 117.2 Barrier / InputLeap

Barrier (now superseded by the more actively maintained **InputLeap** fork) shares one keyboard and mouse across multiple computers over a TCP connection. Server = the machine with the real keyboard/mouse. Clients = machines controlled remotely.

### The Wayland Problem

X11 allowed any privileged process to inject input events globally. Wayland has no such mechanism — input injection requires either the compositor's explicit permission (via `zwp_virtual_keyboard_v1` and `zwp_pointer_gestures_v4`) or root access to `/dev/uinput`. InputLeap supports both paths on Wayland.

### Installation

```bash
# Arch AUR (InputLeap, the maintained fork)
yay -S input-leap

# Barrier (older, still functional)
sudo pacman -S barrier   # if available, else AUR

# Ubuntu
sudo apt install barrier   # Barrier
# InputLeap: build from source
```

### Server Configuration (machine with keyboard/mouse)

```bash
# Start InputLeap server (GUI)
input-leap &

# Or CLI server
inputleaps --config ~/.config/inputleap/inputleap.conf \
           --no-daemon --log-level DEBUG 2>&1 | tee /tmp/inputleap.log
```

Config file `~/.config/inputleap/inputleap.conf`:

```
section: screens
    mydesktop:
    laptop:
end

section: links
    mydesktop:
        right = laptop     # laptop is to the right of mydesktop
    laptop:
        left = mydesktop
end

section: options
    heartbeat = 5000
    switchCorners = none
    switchCornerSize = 0
end
```

### Client Configuration (machine being controlled)

```bash
# Start InputLeap client — connect to server at 192.168.1.100
inputleapc --no-daemon 192.168.1.100

# With TLS (recommended for security)
inputleapc --no-daemon --enable-crypto 192.168.1.100
```

### Wayland Input Injection: uinput Method

On Wayland, InputLeap uses `/dev/uinput` to inject events at the kernel level, bypassing Wayland's security model with a privileged device node:

```bash
# Allow your user to access uinput (requires udev rule)
echo 'KERNEL=="uinput", MODE="0660", GROUP="input"' \
    | sudo tee /etc/udev/rules.d/60-inputleap.rules
sudo udevadm control --reload-rules
sudo usermod -aG input $USER
# Log out and back in for group membership to take effect
```

After adding the udev rule, InputLeap client on Wayland injects events via `uinput` without needing root.

### Wayland Input Injection: Virtual Input Protocol

Compositors that implement `zwp_virtual_keyboard_v1` allow userspace input injection through the Wayland socket without `/dev/uinput`. InputLeap supports this on recent Wayland builds:

```bash
# Use Wayland portal method (requires compositor support)
inputleapc --wayland --no-daemon 192.168.1.100
```

Hyprland and Sway both implement `zwp_virtual_keyboard_v1`. labwc and River may require the uinput method.

### Autostart

```ini
# ~/.config/systemd/user/inputleap-client.service
[Unit]
Description=InputLeap client
After=graphical-session.target

[Service]
ExecStart=inputleapc --no-daemon 192.168.1.100
Restart=on-failure
RestartSec=3s

[Install]
WantedBy=graphical-session.target
```

```bash
systemctl --user enable --now inputleap-client
```

### Troubleshooting

**Connection refused:** Check server firewall allows port 24800 TCP.
```bash
sudo firewall-cmd --add-port=24800/tcp --permanent   # firewalld
sudo ufw allow 24800/tcp                              # ufw
```

**Keyboard input works but mouse doesn't (Wayland client):** InputLeap may be using XWayland for mouse but not keyboard. Ensure `--wayland` flag is set or uinput permissions are correct.

**Screen jump on cursor edge:** Adjust `switchCornerSize` in server config to reduce accidental switches.
