# Chapter 80 — Remote Desktop and Game Streaming: wayvnc, RDP, Sunshine

## Overview
Accessing your Wayland desktop remotely or streaming games to another device
requires Wayland-aware tools. This chapter covers VNC, RDP, and game streaming
(Sunshine/Moonlight) on Wayland.

## Sections

### 80.1 The Remote Desktop Landscape on Wayland

| Protocol | Tool | Use case | Wayland support |
|----------|------|----------|----------------|
| VNC | wayvnc | Simple remote access | Yes (screencopy) |
| RDP | gnome-remote-desktop, freerdp | Enterprise, Windows clients | Yes (GNOME/KDE) |
| Proprietary | Sunshine/Moonlight | Low-latency game streaming | Yes (KMS/DRM) |
| Reverse proxy | rustdesk | Cross-platform remote support | Partial |

### 80.2 wayvnc — VNC for Wayland

wayvnc is a VNC server for wlroots-based compositors:
```bash
sudo pacman -S wayvnc
```

**Starting:**
```bash
# Basic: no auth, localhost only
wayvnc 127.0.0.1 5900

# With TLS and password
wayvnc --certificate /path/to/cert.pem --private-key /path/to/key.pem \
       --authentication 0.0.0.0 5900
```

**Config:** `~/.config/wayvnc/config`
```ini
address=0.0.0.0
port=5900
enable_auth=true
username=myuser
password=mypassword
private_key_file=/path/to/key.pem
certificate_file=/path/to/cert.pem
```

**Autostart:**
```conf
# hyprland.conf
exec-once = wayvnc 127.0.0.1 5900
```

**wayvnc limitations:**
- Requires screencopy (`zwlr-screencopy-v1`)
- Works on wlroots compositors; not on GNOME/KWin
- No audio forwarding (use PipeWire network for that)
- Cursor rendering may be imperfect

**Connecting from client:**
```bash
vncviewer 192.168.1.100:5900  # tigervnc
# or: remmina, vinagre, virt-viewer
```

### 80.3 GNOME Remote Desktop (RDP)

GNOME 42+ includes a built-in RDP server:
```
System Settings → System → Remote Desktop
Toggle: Enable Remote Desktop
Set username and password
```

Protocol: RDP with PipeWire-based screen capture.

```bash
# Connect from Windows:
# mstsc → hostname:3389
# Linux:
remmina -c rdp://192.168.1.100
freerdp /v:192.168.1.100 /u:username /p:password /dynamic-resolution
```

### 80.4 KDE Remote Desktop (RDP)

KDE Plasma 6 includes RDP via `kde-remote-desktop`:
```
System Settings → System → Remote Desktop
```

Alternatively, `krfb` for VNC.

### 80.5 Sunshine + Moonlight — Game Streaming

Sunshine is an open-source GameStream host (NVIDIA Shield replacement):

**Installation:**
```bash
# Arch AUR
paru -S sunshine-bin
# or build from source
```

**Setup:**
```bash
# Start Sunshine
sunshine

# Web UI for configuration
# Open: https://localhost:47990 in browser
# Add your username and password in the setup wizard
```

**Wayland configuration in Sunshine:**
```toml
# ~/.config/sunshine/sunshine.conf
[general]
capture = kms      # Direct KMS capture (best quality, requires root or cap_sys_admin)
# or:
capture = wlr      # wayland screencopy (no root needed, slightly lower quality)
```

**KMS capture (recommended for performance):**
```bash
# Allow Sunshine to capture DRM without root:
sudo setcap cap_sys_admin+p $(which sunshine)
```

**Moonlight client** (any device):
- Android, iOS, macOS, Windows, Linux, Raspberry Pi
- Install from app store or https://moonlight-stream.org
- Add host → enter your PC's IP → pair with PIN → play

**Performance settings:**
- Resolution: match your desktop
- Framerate: 60 or 120 fps
- Bitrate: 20-50 Mbps for local network, 10-15 Mbps for internet
- Codec: H.265 (HEVC) for best quality/bandwidth ratio

### 80.6 SSH X11 Forwarding (Legacy)

For running single X11 apps remotely:
```bash
ssh -X user@host  # insecure, X11 forwarding
ssh -Y user@host  # trusted X11 forwarding
```
Not for Wayland apps. Use Wayland-native remote solutions above.

### 80.7 PipeWire Audio Over Network

Stream audio alongside remote desktop:
```bash
# On host:
pactl load-module module-native-protocol-tcp auth-ip-acl=192.168.1.0/24

# On client:
pactl load-module module-tunnel-sink server=192.168.1.100
```

Or use PipeWire's own network module (`module-protocol-native`).

### 80.8 rustdesk — Cross-Platform Remote Support

```bash
paru -S rustdesk-bin
rustdesk  # start; shows your device ID and password
```

Wayland support via portal (screenshare dialog required per session).
Good for one-off remote support rather than persistent access.
