# Chapter 71 — Network Management and Polkit: nmtui, nm-applet, pkexec

## Overview
Two things silently break every new Hyprland/Sway setup: no network manager UI
(can't connect to WiFi) and no polkit agent (apps fail without error). This chapter
fixes both.

## Sections

### 71.1 The Problem

On a fresh wlroots-based compositor setup:
- No system tray → `nm-applet` doesn't visually appear
- No polkit agent → mounting USB drives fails silently, sudo GUI apps crash
- NetworkManager is installed but has no UI
- Result: users Google "Hyprland no internet" and "Thunar can't mount"

### 71.2 NetworkManager TUI: nmtui

The fastest solution — works without any graphical tools:
```bash
sudo pacman -S networkmanager
sudo systemctl enable --now NetworkManager
nmtui  # launch the TUI
```

`nmtui` provides:
- **Activate a connection**: connect to WiFi or ethernet
- **Edit a connection**: configure IP, DNS, VPN
- **Set system hostname**

Works in any terminal, no graphical dependencies.

### 71.3 nm-applet — System Tray Widget

```bash
sudo pacman -S network-manager-applet
exec-once = nm-applet --indicator
```

`nm-applet` shows in the system tray (requires SystemTray in Quickshell or Waybar).
Click to connect to WiFi, see signal strength, manage VPNs.

**In Quickshell SystemTray (Ch 22):** nm-applet appears automatically once running.

### 71.4 iwgtk — Lightweight WiFi Manager

For setups using `iwd` instead of NetworkManager:
```bash
sudo pacman -S iwd iwgtk
sudo systemctl enable --now iwd
iwgtk  # launch GUI
# or: iwctl  (iwd CLI)
```

`iwd` is faster and more reliable than `wpa_supplicant` for WiFi.

### 71.5 CLI Network Management Reference

```bash
# NetworkManager CLI
nmcli device wifi list                    # scan for networks
nmcli device wifi connect "SSID" password "pass"
nmcli connection show                     # list saved connections
nmcli connection up "connection-name"     # activate saved connection
nmcli device status                       # interface status

# iwd CLI
iwctl
  station wlan0 scan
  station wlan0 get-networks
  station wlan0 connect SSID
  quit
```

### 71.6 DNS Configuration

```bash
# Check current DNS
resolvectl status
cat /etc/resolv.conf

# Set custom DNS via NetworkManager
nmcli connection modify "WiFi-name" ipv4.dns "1.1.1.1 8.8.8.8"
nmcli connection modify "WiFi-name" ipv4.ignore-auto-dns yes
```

For systemd-resolved:
```bash
sudo systemctl enable --now systemd-resolved
sudo ln -sf /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf
```

---

## Polkit Authentication Agents

### 71.7 What Polkit Is

Polkit (formerly PolicyKit) is the privilege escalation framework for Linux desktops.
When a GUI app needs root access (mounting drives, installing packages, changing system
settings), it sends a request to polkit, which asks the user for authentication via an
**authentication agent** — a dialog that appears asking for your password.

**Without a polkit agent running:**
- Thunar cannot mount USB drives → silently fails
- NetworkManager cannot manage system-wide connections → silently fails
- Flatpak GUI package managers cannot install → silently fails
- System settings apps that need root cannot apply changes → silently fails

### 71.8 Available Polkit Agents

| Agent | Toolkit | Notes |
|-------|---------|-------|
| `polkit-gnome-authentication-agent-1` | GTK3 | Most common, works everywhere |
| `lxqt-policykit` | Qt | Good for Qt rices |
| `kauth` | Qt/KDE | Integrated in KDE |
| `mate-polkit` | GTK3 | MATE desktop agent |
| `pantheon-agent-polkit` | GTK3 | elementary OS |

### 71.9 Starting a Polkit Agent

```conf
# hyprland.conf — MUST be in exec-once
exec-once = /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1
```

```conf
# sway config
exec /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1
```

**NixOS:**
```nix
security.polkit.enable = true;
# For GNOME agent:
systemd.user.services.polkit-gnome-authentication-agent-1 = {
    description = "polkit-gnome-authentication-agent-1";
    wantedBy = [ "graphical-session.target" ];
    serviceConfig = {
        ExecStart = "${pkgs.polkit_gnome}/libexec/polkit-gnome-authentication-agent-1";
        Restart = "on-failure";
    };
};
```

### 71.10 Testing Polkit

```bash
# Should trigger a password dialog:
pkexec ls /root

# Mount a USB drive in Thunar → should ask for password, not silently fail
# Or test with:
udisksctl mount -b /dev/sdb1  # (no polkit needed for this — but GUI apps use it)
```

### 71.11 Polkit Rules (Advanced)

Allow specific actions without a password prompt:
```javascript
// /etc/polkit-1/rules.d/10-no-password-mount.rules
polkit.addRule(function(action, subject) {
    if (action.id == "org.freedesktop.udisks2.filesystem-mount" &&
        subject.local && subject.active && subject.isInGroup("users")) {
        return polkit.Result.YES;
    }
});
```

### 71.12 VPN Setup

```bash
# OpenVPN
sudo pacman -S networkmanager-openvpn
nmcli connection import type openvpn file client.ovpn

# WireGuard
sudo pacman -S networkmanager-wireguard  # or just use wg-quick
sudo wg-quick up wg0  # /etc/wireguard/wg0.conf

# NetworkManager GUI for VPN
nm-applet  # right-click → VPN connections
```
