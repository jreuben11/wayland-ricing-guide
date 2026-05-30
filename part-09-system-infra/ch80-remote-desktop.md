# Chapter 80 — Remote Desktop and Game Streaming: wayvnc, RDP, Sunshine

## Contents

- [Overview](#overview)
- [80.1 The Remote Desktop Landscape on Wayland](#801-the-remote-desktop-landscape-on-wayland)
- [80.2 wayvnc — VNC for Wayland](#802-wayvnc-vnc-for-wayland)
  - [Installation](#installation)
  - [Basic Usage](#basic-usage)
  - [Configuration File](#configuration-file)
  - [Autostarting with Hyprland](#autostarting-with-hyprland)
  - [Autostarting as a systemd User Service](#autostarting-as-a-systemd-user-service)
  - [Connecting from Clients](#connecting-from-clients)
  - [Known Limitations](#known-limitations)
- [80.3 GNOME Remote Desktop (RDP)](#803-gnome-remote-desktop-rdp)
  - [Enabling via Settings](#enabling-via-settings)
  - [Enabling via CLI (headless setup)](#enabling-via-cli-headless-setup)
  - [Firewall Configuration](#firewall-configuration)
  - [Connecting from Clients](#connecting-from-clients)
  - [GNOME RDP Certificate Pinning](#gnome-rdp-certificate-pinning)
- [80.4 KDE Remote Desktop (RDP)](#804-kde-remote-desktop-rdp)
  - [Enabling RDP on KDE Plasma 6](#enabling-rdp-on-kde-plasma-6)
  - [krfb — KDE VNC Server](#krfb-kde-vnc-server)
  - [Connecting to KDE Remote Desktop](#connecting-to-kde-remote-desktop)
- [80.5 Sunshine + Moonlight — Game Streaming](#805-sunshine-moonlight-game-streaming)
  - [Installation](#installation)
  - [Initial Setup](#initial-setup)
  - [Sunshine Configuration File](#sunshine-configuration-file)
  - [KMS Capture — Privilege Setup](#kms-capture-privilege-setup)
  - [wlr Screencopy Capture (no root)](#wlr-screencopy-capture-no-root)
  - [Adding Applications to Stream](#adding-applications-to-stream)
  - [systemd Service for Sunshine](#systemd-service-for-sunshine)
  - [Moonlight Client Setup](#moonlight-client-setup)
  - [Performance Tuning](#performance-tuning)
  - [Firewall Rules for Sunshine](#firewall-rules-for-sunshine)
- [80.6 Waypipe — Remote Wayland Applications](#806-waypipe-remote-wayland-applications)
- [80.7 SSH X11 Forwarding (Legacy Reference)](#807-ssh-x11-forwarding-legacy-reference)
- [80.8 PipeWire Audio Over Network](#808-pipewire-audio-over-network)
  - [PipeWire Native Network Sink](#pipewire-native-network-sink)
  - [PipeWire Zeroconf / Avahi Auto-Discovery](#pipewire-zeroconf-avahi-auto-discovery)
  - [Audio via SSH Tunnel](#audio-via-ssh-tunnel)
- [80.9 rustdesk — Cross-Platform Remote Support](#809-rustdesk-cross-platform-remote-support)
  - [Self-Hosted rustdesk Server](#self-hosted-rustdesk-server)
- [80.10 Headless Wayland Sessions for Remote-Only Use](#8010-headless-wayland-sessions-for-remote-only-use)
  - [Headless Hyprland](#headless-hyprland)
  - [Headless sway](#headless-sway)
  - [Combining Headless with wayvnc](#combining-headless-with-wayvnc)
- [80.11 Security Hardening for Remote Desktop](#8011-security-hardening-for-remote-desktop)
  - [SSH Tunnel Wrapping (Recommended for All Protocols)](#ssh-tunnel-wrapping-recommended-for-all-protocols)
  - [VPN Access (WireGuard)](#vpn-access-wireguard)
  - [Fail2ban for RDP](#fail2ban-for-rdp)
- [Troubleshooting](#troubleshooting)
  - [wayvnc fails to start with "no screencopy support"](#wayvnc-fails-to-start-with-no-screencopy-support)
  - [Sunshine KMS capture fails with permission error](#sunshine-kms-capture-fails-with-permission-error)
  - [Moonlight connects but shows black screen](#moonlight-connects-but-shows-black-screen)
  - [High latency or stuttering in Sunshine streaming](#high-latency-or-stuttering-in-sunshine-streaming)
  - [GNOME Remote Desktop — client cannot connect](#gnome-remote-desktop-client-cannot-connect)
  - [Clipboard not syncing in wayvnc](#clipboard-not-syncing-in-wayvnc)
  - [PipeWire audio tunnel drops or has high latency](#pipewire-audio-tunnel-drops-or-has-high-latency)

---


## Overview

Accessing a Wayland desktop remotely is fundamentally different from X11 remote access. Under X11, the display server protocol was inherently networked — `DISPLAY=remote:0` was all you needed for trivial forwarding. Wayland is designed as a local protocol; there is no built-in concept of network transparency. Remote access therefore requires compositor-specific extensions (`zwlr-screencopy-v1`, PipeWire screen capture portals, or KMS/DRM frame grabbing) that vary by compositor family.

This chapter covers three tiers of remote desktop use: lightweight VNC via wayvnc for wlroots compositors, standards-based RDP built into GNOME and KDE, and low-latency game streaming with Sunshine/Moonlight. Each tier serves different performance and interoperability requirements. Understanding the capture path — screencopy extension, PipeWire portal, or KMS — is essential for diagnosing issues and tuning performance.

The chapter also covers auxiliary topics: PipeWire audio forwarding, rustdesk for ad-hoc remote support, SSH tunneling strategies, and systemd service integration for headless or semi-headless remote servers.

See Ch 53 for compositor session startup, Ch 56 for PipeWire audio fundamentals, and Ch 71 for firewall and network configuration that affects remote access ports.

---

## 80.1 The Remote Desktop Landscape on Wayland

The Wayland ecosystem has converged on several capture mechanisms. wlroots compositors expose the `zwlr-screencopy-v1` unstable protocol; GNOME and KDE use PipeWire screen capture via `xdg-desktop-portal`; any compositor that runs on a KMS device can in principle be captured at the DRM layer directly (bypassing the compositor entirely). Your tool choice follows directly from which capture path your compositor provides.

| Protocol   | Tool                        | Capture mechanism        | Compositor support      | Use case                          |
|------------|-----------------------------|--------------------------|-------------------------|-----------------------------------|
| VNC        | wayvnc                      | zwlr-screencopy-v1       | wlroots (Hyprland, sway, river) | Lightweight remote access   |
| RDP        | gnome-remote-desktop        | PipeWire portal          | GNOME 42+               | Enterprise, Windows clients       |
| RDP        | kde-remote-desktop          | PipeWire portal          | KDE Plasma 6+           | Enterprise, Windows clients       |
| GameStream | Sunshine                    | KMS/DRM or zwlr-screencopy-v1 | Any (with right cap)   | Low-latency game streaming        |
| Multi-proto | rustdesk                   | xdg-portal / screencopy  | Any (with portal)       | Ad-hoc remote support             |
| Tunnel     | SSH + Waypipe               | Wayland protocol proxy   | Any                     | Running remote Wayland apps locally|
| Legacy     | SSH X11 forwarding          | X11 only                 | X11 apps via XWayland   | Legacy X11 app forwarding         |

Key terms you will encounter throughout this chapter:

- **screencopy**: The `zwlr-screencopy-v1` Wayland protocol extension that lets privileged clients capture compositor frames. Requires a wlroots compositor.
- **KMS capture**: Capturing frames directly from the kernel DRM/KMS layer via `/dev/dri/cardN`, bypassing the compositor. Requires `CAP_SYS_ADMIN` or a group ACL on the DRM device.
- **PipeWire portal**: Screen capture routed through `xdg-desktop-portal` with user consent dialogs. The compositor-agnostic approach used by GNOME and KDE.

---

## 80.2 wayvnc — VNC for Wayland

wayvnc is the canonical VNC server for wlroots compositors. It listens on a standard VNC port and serves frames obtained via the `zwlr-screencopy-v1` protocol. Input (keyboard, mouse, clipboard) is injected back into the compositor via `zwlr-virtual-keyboard-v1` and `zwlr-input-inhibitor-v1`. Because it relies on wlroots protocols, it does not work on GNOME or KDE — use the RDP solutions in sections 80.3 and 80.4 for those.

### Installation

```bash
# Arch Linux
sudo pacman -S wayvnc

# Fedora
sudo dnf install wayvnc

# Ubuntu/Debian (may need PPA or manual build)
sudo apt install wayvnc

# Build from source (latest features)
git clone https://github.com/any1/wayvnc.git
cd wayvnc
meson setup build --buildtype=release
ninja -C build
sudo ninja -C build install
```

wayvnc depends on `neatvnc` (its VNC library) and `aml` (event loop). These are pulled in automatically from packages, or as subprojects when building from source.

### Basic Usage

```bash
# Listen on loopback only — safest default
wayvnc 127.0.0.1 5900

# Listen on all interfaces (LAN access without auth — dangerous on untrusted networks)
wayvnc 0.0.0.0 5900

# With TLS and password authentication
wayvnc --certificate /etc/wayvnc/cert.pem \
       --private-key /etc/wayvnc/key.pem \
       --authentication \
       0.0.0.0 5900

# Choose a specific output (monitor) to capture
wayvnc --output DP-1 127.0.0.1 5900

# List available outputs
wayvnc --list-outputs
```

### Configuration File

The persistent configuration lives at `~/.config/wayvnc/config`. Options set here take effect on every start without requiring command-line flags.

```ini
# ~/.config/wayvnc/config

address=0.0.0.0
port=5900

# TLS (strongly recommended for LAN/internet exposure)
enable_auth=true
username=myuser
password=s3cr3tpassword
private_key_file=/home/myuser/.config/wayvnc/key.pem
certificate_file=/home/myuser/.config/wayvnc/cert.pem

# Capture target (comment out to auto-select first output)
output_name=DP-1

# Relax cursor rendering — helps on some compositors
#relax_zorder=true
```

Generate a self-signed TLS certificate for encrypted VNC:

```bash
mkdir -p ~/.config/wayvnc
openssl req -x509 -newkey rsa:4096 -keyout ~/.config/wayvnc/key.pem \
    -out ~/.config/wayvnc/cert.pem -days 3650 -nodes \
    -subj "/CN=$(hostname)"
chmod 600 ~/.config/wayvnc/key.pem
```

### Autostarting with Hyprland

```ini
# ~/.config/hypr/hyprland.conf
exec-once = wayvnc 127.0.0.1 5900

# Or with full auth via config file:
exec-once = wayvnc
```

For sway:

```bash
# ~/.config/sway/config
exec wayvnc 127.0.0.1 5900
```

### Autostarting as a systemd User Service

For a headless or server-style setup where wayvnc should start independently of the compositor, create a user service:

```ini
# ~/.config/systemd/user/wayvnc.service
[Unit]
Description=wayvnc VNC server
After=graphical-session.target
PartOf=graphical-session.target

[Service]
ExecStart=/usr/bin/wayvnc 127.0.0.1 5900
Restart=on-failure
RestartSec=3

[Install]
WantedBy=graphical-session.target
```

```bash
systemctl --user enable --now wayvnc.service
systemctl --user status wayvnc.service
journalctl --user -u wayvnc.service -f
```

### Connecting from Clients

```bash
# TigerVNC (recommended, supports TLS/encryption)
vncviewer 192.168.1.100:5900

# Remmina (GUI, supports many protocols)
remmina -c vnc://192.168.1.100:5900

# TigerVNC with specific options
vncviewer -SecurityTypes TLSVnc -passwd /tmp/vncpass 192.168.1.100:5900

# SSH tunnel first (avoid exposing VNC port)
ssh -L 5900:127.0.0.1:5900 user@192.168.1.100
vncviewer 127.0.0.1:5900
```

### Known Limitations

- Requires `zwlr-screencopy-v1` — wlroots compositors only (Hyprland, sway, river, labwc, cage)
- Does not work on GNOME (Mutter) or KDE (KWin) — use GNOME/KDE RDP instead
- No audio forwarding (add PipeWire network streaming separately; see 80.7)
- Cursor may appear doubled or offset on some compositors
- Frame rate is limited by screencopy protocol overhead; 30 fps is typical, 60 fps possible on fast hardware
- Clipboard sync requires `wl-clipboard` to be installed

---

## 80.3 GNOME Remote Desktop (RDP)

GNOME 42 and later ships `gnome-remote-desktop`, a built-in RDP server using PipeWire for screen capture and libfreerdp for the protocol stack. This is the recommended remote access method for GNOME on Wayland. It requires no additional packages on most GNOME distributions and integrates with the GNOME keyring for credential storage.

### Enabling via Settings

Navigate to: **System Settings → System → Remote Desktop**

Toggle "Enable Remote Desktop" to on. Set a username and password. The service starts automatically at login. GNOME stores the RDP TLS certificate in `~/.local/share/gnome-remote-desktop/` and credentials in the keyring.

### Enabling via CLI (headless setup)

```bash
# Check if gnome-remote-desktop is installed
systemctl --user status gnome-remote-desktop.service

# Enable and start
systemctl --user enable --now gnome-remote-desktop.service

# Configure credentials via gsettings
gsettings set org.gnome.desktop.remote-desktop.rdp screen-share-mode mirror-primary
gsettings set org.gnome.desktop.remote-desktop.rdp enable true

# Set username and password using grdctl (GNOME 43+)
grdctl rdp enable
grdctl rdp set-credentials myuser mypassword
grdctl rdp disable-view-only   # allow full control, not read-only
```

### Firewall Configuration

```bash
# Open RDP port (3389) in firewalld
sudo firewall-cmd --add-service=rdp --permanent
sudo firewall-cmd --reload

# Or with nftables/iptables
sudo nft add rule inet filter input tcp dport 3389 accept
```

### Connecting from Clients

```bash
# From Windows: Start → mstsc → enter hostname:3389

# FreeRDP on Linux (full-featured)
xfreerdp /v:192.168.1.100 /u:myuser /p:mypassword \
    /dynamic-resolution /gfx:AVC444 /network:lan

# FreeRDP with clipboard and drive sharing
xfreerdp /v:192.168.1.100 /u:myuser /p:mypassword \
    /dynamic-resolution /clipboard /drive:home,$HOME

# Remmina (GUI)
remmina -c rdp://myuser@192.168.1.100

# FreeRDP with specific resolution
xfreerdp /v:192.168.1.100 /u:myuser /size:1920x1080
```

### GNOME RDP Certificate Pinning

The GNOME RDP server generates a self-signed certificate. Clients will warn on first connect; pin the certificate fingerprint to avoid repeated warnings:

```bash
# Get the certificate fingerprint
openssl x509 -in ~/.local/share/gnome-remote-desktop/rdp-tls.crt \
    -fingerprint -sha256 -noout
```

Pin the fingerprint in your RDP client's known hosts file or trust store.

---

## 80.4 KDE Remote Desktop (RDP)

KDE Plasma 6 integrates remote desktop support directly in System Settings. The backend uses PipeWire for screen capture and a KDE-maintained RDP server. The configuration path is: **System Settings → System → Remote Desktop**.

### Enabling RDP on KDE Plasma 6

```bash
# Check for plasma-remotedesktop package
sudo pacman -S plasma-remotedesktop       # Arch
sudo dnf install plasma-remotedesktop     # Fedora
sudo apt install plasma-remotedesktop     # Debian/Ubuntu

# Enable via kded or systemd user service
systemctl --user enable --now plasma-remotedesktop.service
```

### krfb — KDE VNC Server

For VNC-based access on KDE (useful when the client supports VNC only):

```bash
sudo pacman -S krfb
krfb           # launches GUI configurator
krfb --no-gui  # headless, uses existing config
```

krfb uses the KWin screencopy API and works on both X11 and Wayland sessions in KDE. It does not support the `zwlr-screencopy-v1` protocol; it uses KDE-specific interfaces. Configure the listen address and password through its GUI before running headless.

### Connecting to KDE Remote Desktop

Clients are the same as for GNOME RDP:

```bash
xfreerdp /v:192.168.1.100 /u:myuser /p:mypassword /dynamic-resolution
remmina -c rdp://myuser@192.168.1.100
```

---

## 80.5 Sunshine + Moonlight — Game Streaming

Sunshine is an open-source GameStream host, originally a drop-in replacement for NVIDIA's proprietary GeForce Experience streaming. It streams your desktop at game-grade latency over a local network or the internet. Moonlight is the companion client, available on virtually every platform. Together they form the best-in-class low-latency streaming stack for Wayland.

Sunshine captures frames either via KMS/DRM (directly from the kernel framebuffer — lowest latency, but requires privilege) or via `zwlr-screencopy-v1` (compositor-mediated — no privilege needed, slightly higher latency). Hardware video encoding is used if available (NVENC, VAAPI, AMF).

### Installation

```bash
# Arch Linux (AUR)
paru -S sunshine-bin        # pre-built binary
# or
paru -S sunshine            # build from source (takes a while)

# Fedora (Copr)
sudo dnf copr enable lizardbyte/stable
sudo dnf install sunshine

# Debian/Ubuntu (.deb from GitHub releases)
wget https://github.com/LizardByte/Sunshine/releases/latest/download/sunshine-ubuntu-22.04-amd64.deb
sudo dpkg -i sunshine-ubuntu-22.04-amd64.deb
sudo apt -f install   # fix dependencies if needed

# Flatpak (universal, recommended for non-Arch)
flatpak install flathub dev.lizardbyte.sunshine
```

### Initial Setup

```bash
# First launch — Sunshine prints a setup URL
sunshine

# Open the Web UI in your browser
xdg-open https://localhost:47990

# The first run wizard prompts for username/password for the web UI
# Set these before exposing Sunshine to the network
```

The web UI (port 47990) is the primary configuration interface. It shows streaming statistics, lets you add/edit applications, configure audio/video settings, and pair Moonlight clients.

### Sunshine Configuration File

```toml
# ~/.config/sunshine/sunshine.conf

[general]
# Capture backend: kms (best), wlr (fallback), nvfbc (NVIDIA only)
capture = kms

# Logging verbosity: none, fatal, error, warning, info, verbose, debug
min_log_level = warning

# Web UI credentials
username = admin
password = changeme

[video]
# Default encoder: auto, nvenc, vaapi, amdvce, software
encoder = auto

# Minimum frames per second
min_fps = 10

# Maximum FPS cap (client setting also applies)
max_fps = 120

[audio]
# Audio device to capture (PipeWire sink name)
# Leave blank to use system default
audio_sink =
```

### KMS Capture — Privilege Setup

KMS capture reads directly from `/dev/dri/card0` (or your active card). This requires either `CAP_SYS_ADMIN` or membership in the `video` group with DRM device permissions.

```bash
# Method 1: setcap (preferred — no root required at runtime)
sudo setcap cap_sys_admin+p $(which sunshine)

# Verify
getcap $(which sunshine)
# Expected output: /usr/bin/sunshine cap_sys_admin=p

# Method 2: Add user to video group (may not be sufficient alone on all distros)
sudo usermod -aG video $USER
# Re-login for group membership to take effect

# Method 3: udev rule for DRM device
echo 'SUBSYSTEM=="drm", GROUP="video", MODE="0660"' \
    | sudo tee /etc/udev/rules.d/99-drm-sunshine.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

For Flatpak installations, KMS capture requires additional portal permissions:

```bash
flatpak override --user --device=dri dev.lizardbyte.sunshine
```

### wlr Screencopy Capture (no root)

If KMS is not available or not permitted, fall back to wlr screencopy:

```toml
# ~/.config/sunshine/sunshine.conf
[general]
capture = wlr
```

This works on Hyprland, sway, and other wlroots compositors without elevated privileges. Latency is typically 2–5 ms higher than KMS capture.

### Adding Applications to Stream

Through the web UI at `https://localhost:47990`, navigate to **Applications** → **Add New**. For streaming the full desktop:

```json
{
  "name": "Desktop",
  "output": "",
  "cmd": "",
  "detached": []
}
```

For launching a specific game or application directly:

```json
{
  "name": "Steam Big Picture",
  "cmd": "steam -bigpicture",
  "detached": []
}
```

### systemd Service for Sunshine

```ini
# ~/.config/systemd/user/sunshine.service
[Unit]
Description=Sunshine GameStream host
After=graphical-session.target

[Service]
ExecStart=/usr/bin/sunshine
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical-session.target
```

```bash
systemctl --user enable --now sunshine.service
systemctl --user status sunshine.service
```

### Moonlight Client Setup

Moonlight is the client-side viewer. Install it on your streaming device:

```bash
# Linux
sudo pacman -S moonlight-qt          # Arch
sudo dnf install moonlight-qt        # Fedora
flatpak install flathub com.moonlight_stream.Moonlight  # Universal

# Android/iOS: install from Google Play / App Store
# Windows/macOS: download from https://moonlight-stream.org
```

Pairing:

1. Open Moonlight → **Add Host** → enter your PC's IP address
2. Moonlight displays a PIN
3. In the Sunshine web UI → **PIN** tab → enter the PIN
4. Select the application to stream

### Performance Tuning

```toml
# ~/.config/sunshine/sunshine.conf — performance section

[video]
# Use HEVC (H.265) for better quality at lower bandwidth
# Requires client hardware decoder support
encoder = auto

# Bitrate is set per-client in Moonlight settings:
# Local network: 30–50 Mbps for 1080p60, 80–120 Mbps for 4K60
# Internet: 10–15 Mbps for 1080p60

# HDR passthrough (requires compatible display chain)
# enable_hdr = true
```

Moonlight client settings (set in Moonlight's settings panel):

| Setting          | Local Network       | Internet (100 Mbps+) |
|------------------|---------------------|----------------------|
| Resolution       | 1920x1080 or native | 1920x1080            |
| Frame rate       | 60 or 120           | 60                   |
| Video bitrate    | 30–50 Mbps          | 10–15 Mbps           |
| Audio quality    | High                | Medium               |
| Codec            | HEVC (H.265)        | H.264 (compatibility)|

### Firewall Rules for Sunshine

Sunshine uses several ports:

```bash
# Sunshine default ports:
# 47984 TCP  — HTTPS stream control
# 47989 TCP  — HTTP stream control
# 47990 TCP  — Web UI
# 48010 TCP  — RTSP
# 47998 UDP  — Video
# 47999 UDP  — Control
# 48000 UDP  — Audio

# Open with firewalld
sudo firewall-cmd --add-port=47984/tcp --add-port=47989/tcp \
    --add-port=47990/tcp --add-port=48010/tcp \
    --add-port=47998/udp --add-port=47999/udp \
    --add-port=48000/udp --permanent
sudo firewall-cmd --reload

# Or create a firewalld service file
cat <<'EOF' | sudo tee /etc/firewalld/services/sunshine.xml
<?xml version="1.0" encoding="utf-8"?>
<service>
  <short>Sunshine</short>
  <description>Sunshine GameStream host</description>
  <port port="47984" protocol="tcp"/>
  <port port="47989" protocol="tcp"/>
  <port port="47990" protocol="tcp"/>
  <port port="48010" protocol="tcp"/>
  <port port="47998" protocol="udp"/>
  <port port="47999" protocol="udp"/>
  <port port="48000" protocol="udp"/>
</service>
EOF
sudo firewall-cmd --add-service=sunshine --permanent && sudo firewall-cmd --reload
```

---

## 80.6 Waypipe — Remote Wayland Applications

Waypipe is a proxy that forwards Wayland protocol messages over SSH. Unlike X11 forwarding (which forwards a low-level display protocol), Waypipe forwards high-level Wayland compositor messages. Individual Wayland applications run on the remote machine but their windows appear locally, with input going back over SSH.

```bash
# Install on both client and server
sudo pacman -S waypipe        # Arch
sudo dnf install waypipe      # Fedora

# Run a remote Wayland application locally
waypipe ssh user@192.168.1.100 firefox

# Waypipe handles the SSH invocation and protocol proxy automatically
# The remote machine must have waypipe installed as well
```

Waypipe is best for forwarding single applications, not full desktop sessions. It supports DMA-BUF buffer sharing for GPU-accelerated rendering when both sides have compatible GPU drivers, which significantly reduces latency compared to naive pixel copying.

```bash
# Force software rendering if DMA-BUF sharing fails
waypipe --no-gpu ssh user@192.168.1.100 mpv /path/to/video.mkv

# Use a specific compression algorithm (zstd is fast)
waypipe --compress zstd ssh user@192.168.1.100 gedit
```

---

## 80.7 SSH X11 Forwarding (Legacy Reference)

For completeness: SSH X11 forwarding runs X11 apps on a remote machine and displays them locally via the X protocol over SSH. This does not work for native Wayland applications. Under XWayland, some applications may be coerced into X11 mode and forwarded, but this is fragile.

```bash
ssh -X user@host app-name    # untrusted X11 forwarding (sandbox restrictions)
ssh -Y user@host app-name    # trusted X11 forwarding (fewer restrictions, less safe)
```

For Wayland-native apps, use Waypipe (80.6) instead. For full desktop access, use wayvnc (80.2) or RDP (80.3/80.4). X11 forwarding is relevant only when you need a specific legacy X11 application and cannot run a full remote desktop solution.

---

## 80.8 PipeWire Audio Over Network

Remote desktop tools generally handle video capture but leave audio forwarding as a separate concern. PipeWire has first-class network audio support through its own network protocol or via PulseAudio compatibility modules.

### PipeWire Native Network Sink

```bash
# On the server (the machine you're remoting into):
# Load the network sink — allows remote clients to connect to PipeWire
pactl load-module module-native-protocol-tcp \
    auth-ip-acl=192.168.1.0/24 \
    auth-anonymous=1

# To make this persistent, add to /etc/pulse/default.pa or
# ~/.config/pulse/default.pa:
# load-module module-native-protocol-tcp auth-ip-acl=192.168.1.0/24

# On the client (the machine you're viewing from):
pactl load-module module-tunnel-sink \
    server=192.168.1.100 \
    sink_name=remote_audio

# Set the tunnel sink as default output
pactl set-default-sink remote_audio
```

### PipeWire Zeroconf / Avahi Auto-Discovery

PipeWire can advertise and discover network sinks automatically via Avahi (mDNS):

```bash
# Install avahi and nss-mdns
sudo pacman -S avahi nss-mdns

# Enable avahi daemon
sudo systemctl enable --now avahi-daemon.service

# Load PipeWire Avahi module — enables automatic discovery
pactl load-module module-zeroconf-publish
pactl load-module module-zeroconf-discover
```

### Audio via SSH Tunnel

For secure audio forwarding without opening PipeWire to the network:

```bash
# Forward PipeWire/PulseAudio socket over SSH
ssh -R /run/user/1000/pulse/native:/run/user/1000/pulse/native \
    user@192.168.1.100

# On the remote machine, set PULSE_SERVER to the forwarded socket
export PULSE_SERVER=unix:/run/user/1000/pulse/native
# Applications on the remote machine will now play audio locally
```

---

## 80.9 rustdesk — Cross-Platform Remote Support

rustdesk is a cross-platform remote desktop tool written in Rust, suitable for ad-hoc remote support scenarios. It provides both a self-hosted relay server and a hosted relay option. On Wayland, it uses `xdg-desktop-portal` for screen capture, which means a permission dialog appears per session.

```bash
# Install
paru -S rustdesk-bin          # Arch AUR
sudo dnf install rustdesk     # Fedora (Copr or direct RPM)
sudo dpkg -i rustdesk.deb     # Debian/Ubuntu (from GitHub releases)
flatpak install flathub com.rustdesk.RustDesk  # Universal

# Start
rustdesk
# The UI displays your device ID and a one-time password
# Share these with the support technician
```

### Self-Hosted rustdesk Server

```bash
# Install rustdesk-server
paru -S rustdesk-server-bin

# Start the relay and signaling servers
hbbr &    # relay server, port 21117
hbbs &    # signaling server, ports 21115-21116

# Configure clients to use your relay:
# In rustdesk settings → ID/Relay Server → enter your server IP
```

rustdesk is better suited for occasional remote support than for persistent headless access. The per-session portal consent dialog is by design (security) but unsuitable for unattended scenarios.

---

## 80.10 Headless Wayland Sessions for Remote-Only Use

A common pattern is running a Wayland compositor in a headless mode (no physical display attached) purely to serve remote desktop connections. This is useful for home servers or NUCs used as remote workstations.

### Headless Hyprland

```bash
# Hyprland supports virtual outputs via hyprland-virtual-desktop or wlr-randr
# Install wlr-randr
sudo pacman -S wlr-randr

# In hyprland.conf, create a virtual monitor:
monitor=HEADLESS-1,1920x1080@60,0x0,1

# Or at runtime:
wlr-randr --output HEADLESS-1 --mode 1920x1080 --on
```

### Headless sway

```bash
# sway supports WL_HEADLESS backend
WLR_BACKENDS=headless WLR_LIBINPUT_NO_DEVICES=1 sway &

# Create a virtual output
swaymsg create_output

# Set resolution on the virtual output
wlr-randr --output HEADLESS-1 --mode 1920x1080
```

### Combining Headless with wayvnc

```bash
# Full headless + VNC in one script
cat > ~/.local/bin/headless-wayland.sh << 'EOF'
#!/bin/bash
export WLR_BACKENDS=headless
export WLR_LIBINPUT_NO_DEVICES=1
sway &
SWAY_PID=$!
sleep 1
wlr-randr --output HEADLESS-1 --mode 1920x1080
wayvnc 0.0.0.0 5900 &
wait $SWAY_PID
EOF
chmod +x ~/.local/bin/headless-wayland.sh
```

Start this from a systemd service using a DRM/KMS virtual backend or the headless renderer.

---

## 80.11 Security Hardening for Remote Desktop

Exposing remote desktop services requires careful attention to security. The following hardening steps apply broadly.

### SSH Tunnel Wrapping (Recommended for All Protocols)

Never expose VNC or unencrypted RDP directly to the internet. Wrap everything in SSH:

```bash
# VNC over SSH tunnel
ssh -L 5900:127.0.0.1:5900 user@your-server.example.com
vncviewer 127.0.0.1:5900

# RDP over SSH tunnel
ssh -L 3389:127.0.0.1:3389 user@your-server.example.com
xfreerdp /v:127.0.0.1 /u:myuser /p:mypassword

# Persistent SSH tunnel via autossh
sudo pacman -S autossh
autossh -M 0 -f -N \
    -L 5900:127.0.0.1:5900 \
    -o ServerAliveInterval=30 \
    user@your-server.example.com
```

### VPN Access (WireGuard)

For permanent remote access, a WireGuard VPN is more robust than per-connection SSH tunnels. See Ch 71 for WireGuard setup. Once the VPN is established, all remote desktop protocols operate over the VPN's encrypted tunnel without additional SSH wrapping.

### Fail2ban for RDP

If RDP must be internet-exposed, protect it with fail2ban:

```bash
sudo pacman -S fail2ban

cat <<'EOF' | sudo tee /etc/fail2ban/jail.d/rdp.local
[rdp]
enabled = true
port = 3389
filter = rdp
logpath = /var/log/auth.log
maxretry = 5
bantime = 3600
EOF

sudo systemctl enable --now fail2ban.service
```

---

## Troubleshooting

### wayvnc fails to start with "no screencopy support"

```
error: compositor does not support zwlr-screencopy-v1
```

**Cause**: Your compositor does not support the wlroots screencopy protocol. GNOME (Mutter) and KDE (KWin) do not implement this protocol.

**Fix**: Use GNOME Remote Desktop (80.3) or KDE Remote Desktop (80.4) instead. If you are on Hyprland/sway and still see this error, ensure you are running a recent version:

```bash
wayvnc --version
# Check compositor protocol support:
wayland-info | grep screencopy
```

### Sunshine KMS capture fails with permission error

```
error: failed to open /dev/dri/card0: Permission denied
```

**Fix**:

```bash
# Apply setcap
sudo setcap cap_sys_admin+p $(which sunshine)

# Verify group membership
groups $USER | grep -E 'video|render'

# Add to render group (required on some distros)
sudo usermod -aG render $USER
# Log out and back in
```

### Moonlight connects but shows black screen

**Causes and fixes**:

1. KMS capture is working but output selection is wrong:
   ```bash
   # List DRM devices
   ls /dev/dri/
   # In sunshine.conf, specify the card
   # [general]
   # adapter_name = /dev/dri/renderD128
   ```

2. Switch to wlr capture as a diagnostic:
   ```toml
   [general]
   capture = wlr
   ```

3. Hardware encoder not initializing — check Sunshine logs:
   ```bash
   journalctl --user -u sunshine.service -n 50
   # Look for encoder initialization errors
   # Try forcing software encoder as a test:
   # [video]
   # encoder = software
   ```

### High latency or stuttering in Sunshine streaming

1. Check encoder: hardware encoding (NVENC/VAAPI) dramatically reduces CPU load and latency vs. software.
2. Verify network: `iperf3 -c <server>` — streaming needs low jitter, not just throughput.
3. Reduce bitrate in Moonlight settings; excessive bitrate causes bufferbloat.
4. Enable FEC (forward error correction) in Moonlight if on Wi-Fi.

### GNOME Remote Desktop — client cannot connect

```bash
# Check service status
systemctl --user status gnome-remote-desktop.service

# Check that port 3389 is listening
ss -tlnp | grep 3389

# Ensure firewall allows the port
sudo firewall-cmd --list-all | grep rdp

# Re-generate credentials if forgotten
grdctl rdp set-credentials newuser newpassword
```

### Clipboard not syncing in wayvnc

```bash
# Ensure wl-clipboard is installed
sudo pacman -S wl-clipboard

# Restart wayvnc with clipboard debug
WAYVNC_LOG=debug wayvnc 127.0.0.1 5900 2>&1 | grep -i clipboard
```

### PipeWire audio tunnel drops or has high latency

```bash
# Check PipeWire status
pw-cli info all | grep -A5 tunnel

# Increase quantum (buffer size) for network stability
# In /etc/pipewire/pipewire.conf.d/10-network.conf:
# context.properties = {
#   default.clock.quantum = 2048
#   default.clock.min-quantum = 1024
# }

sudo systemctl restart pipewire pipewire-pulse
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
