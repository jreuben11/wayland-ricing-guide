# Chapter 61 — Screen Sharing and Video Calls: Portal Setup, WebRTC, OBS

## Overview

Screen sharing is a daily need for remote workers, streamers, and anyone participating
in video calls. On Wayland it requires the xdg-desktop-portal stack to be correctly
assembled and started in the right order. When it works, it is entirely seamless — apps
get a system-native window picker and a high-quality PipeWire video stream. When it
breaks, it is usually silent: the app either shows a black screen or displays no
selection dialog at all, with no obvious error message.

This chapter walks through the entire stack from compositor protocol to browser flag.
It covers Hyprland, Sway, and NixOS configurations; every major video-call client;
OBS Studio screen capture and virtual camera; and a systematic debugging methodology.
After working through this chapter, screen sharing on Wayland should be as reliable as
on X11.

Cross-references: Ch 53 covers session environment setup and `exec-once` ordering; Ch 58
covers PipeWire audio configuration that shares the same daemon; Ch 64 covers remote
desktop (RDP/VNC) as an alternative to WebRTC for internal use.

---

## 61.1 How Screen Sharing Works on Wayland

On X11, any application could call `XGetImage` to read arbitrary pixel data from the
display, making screen capture trivial but also a security hazard. Wayland eliminates
that: the compositor is the only entity that can read framebuffer contents. Applications
must ask the compositor politely, via a defined protocol, and the compositor decides
whether to grant the request and which output or surface to expose.

The complete call chain looks like this:

```
Browser/App
  → WebRTC / PipeWire video API
    → xdg-desktop-portal  (D-Bus: org.freedesktop.portal.ScreenCast)
      → xdg-desktop-portal-hyprland (or -wlr, -gnome, -kde)
        → wlr-screencopy-unstable-v1  (Wayland protocol)
          → Compositor captures frames into a DMA-BUF / shared memory buffer
            → PipeWire video stream (spa format: video/x-raw or video/x-h264)
              → Back to requesting app
```

The portal layer is crucial: it provides both the permission UI (the window/screen picker
dialog) and the translation from the D-Bus ScreenCast interface to whatever compositor
protocol the backend understands. That is why `xdg-desktop-portal` itself is not enough
— you need a compositor-specific backend (e.g. `-hyprland`, `-wlr`) that speaks the
compositor's native screencopy protocol.

PipeWire is the transport mechanism for the raw video frames. Once the portal opens a
ScreenCast session, it creates a PipeWire node. The requesting app (browser, OBS, etc.)
links to that node and receives frames as a PipeWire stream, exactly as if the screen
were an audio output. This means all the PipeWire graph tooling (`pw-top`, `pw-dump`,
`helvum`) can be used to inspect and debug screen share streams alongside audio streams.

The `wlr-screencopy-unstable-v1` protocol (implemented by wlroots-based compositors
such as Hyprland and Sway) is the low-level Wayland extension that actually lets the
portal backend ask the compositor for a copy of an output or a specific surface. Hyprland
additionally implements `hyprland-toplevel-export-v1`, which enables per-window capture
without exposing the whole screen. The KDE and GNOME backends use their own compositors'
respective capture APIs.

---

## 61.2 Required Packages

Getting the right package set is the single most common stumbling block. The base portal
(`xdg-desktop-portal`) provides the D-Bus interface but no UI and no compositor
knowledge — it is a router. The compositor backend provides the actual capture. The
widget toolkit portal (`-gtk` or `-kde`) provides file choosers, screenshot confirmations,
and other UI surfaces. All three layers must be present.

### Arch Linux / Hyprland

```bash
sudo pacman -S \
    xdg-desktop-portal \
    xdg-desktop-portal-hyprland \
    xdg-desktop-portal-gtk \
    pipewire \
    pipewire-pulse \
    pipewire-alsa \
    wireplumber \
    gst-plugin-pipewire \
    libpipewire

# AUR: slurp is needed by xdpw's chooser on wlroots compositors
# Not required for Hyprland but useful for region selection tools
yay -S slurp
```

### Arch Linux / Sway

```bash
sudo pacman -S \
    xdg-desktop-portal \
    xdg-desktop-portal-wlr \
    xdg-desktop-portal-gtk \
    pipewire \
    pipewire-pulse \
    wireplumber \
    slurp
```

### Ubuntu 24.04 / Hyprland (PPA)

```bash
sudo add-apt-repository ppa:hyprland/staging
sudo apt update
sudo apt install \
    xdg-desktop-portal \
    xdg-desktop-portal-hyprland \
    xdg-desktop-portal-gtk \
    pipewire \
    pipewire-audio \
    wireplumber \
    libspa-0.2-bluetooth
```

### Fedora 40+

```bash
sudo dnf install \
    xdg-desktop-portal \
    xdg-desktop-portal-hyprland \
    xdg-desktop-portal-gtk \
    pipewire \
    pipewire-pulseaudio \
    wireplumber
```

### Package Version Requirements

| Package | Minimum Version | Notes |
|---------|----------------|-------|
| xdg-desktop-portal | 1.16 | Required for PipeWire camera portal |
| xdg-desktop-portal-hyprland | 1.3.0 | Adds per-window capture |
| xdg-desktop-portal-wlr | 0.7.0 | Adds PipeWire 0.3 support |
| pipewire | 0.3.48 | DMA-BUF video support |
| wireplumber | 0.4.14 | Stable session manager |

Check installed versions with:

```bash
pacman -Q xdg-desktop-portal xdg-desktop-portal-hyprland pipewire wireplumber
```

---

## 61.3 Startup Configuration (The Critical Part)

The order in which environment variables are exported and portals are launched is the
most common source of screen sharing failures. The compositor must fully initialize its
Wayland socket before the portal backend connects to it. The portal backend must export
its D-Bus service before applications try to call it. Failure to respect this ordering
produces intermittent failures that can appear random.

The fundamental requirement is that `WAYLAND_DISPLAY`, `XDG_CURRENT_DESKTOP`, and
`XDG_SESSION_TYPE` are present in the systemd user session environment — not just the
shell environment. Applications launched via `systemctl --user start` or via D-Bus
activation inherit the systemd environment, not the shell that ran `hyprland`. If these
variables are missing from the systemd environment, portals cannot find the compositor.

### Hyprland (`hyprland.conf`)

```conf
# hyprland.conf — environment export and portal startup in correct order
# Step 1: export compositor variables into systemd and dbus environments
exec-once = dbus-update-activation-environment --systemd \
    WAYLAND_DISPLAY \
    XDG_CURRENT_DESKTOP \
    XDG_SESSION_TYPE \
    DISPLAY

exec-once = systemctl --user import-environment \
    WAYLAND_DISPLAY \
    XDG_CURRENT_DESKTOP \
    XDG_SESSION_TYPE

# Step 2: kill stale portal instances that may have started before env was ready
exec-once = sleep 1 && \
    systemctl --user stop xdg-desktop-portal-hyprland xdg-desktop-portal; \
    sleep 1 && \
    systemctl --user start xdg-desktop-portal-hyprland; \
    sleep 1 && \
    systemctl --user start xdg-desktop-portal
```

Alternatively, if you do not use systemd user services for portals:

```conf
# Manual launch variant (useful for debugging)
exec-once = dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP XDG_SESSION_TYPE
exec-once = sleep 1 && /usr/lib/xdg-desktop-portal-hyprland
exec-once = sleep 2 && /usr/lib/xdg-desktop-portal --replace
```

The `sleep` delays matter: the compositor socket takes ~200–500 ms to be ready after the
Hyprland process starts. The portal backend needs to find that socket. Without the delay,
the backend starts, fails to connect to the compositor, and silently falls back to a
non-functional state.

### Sway (`~/.config/sway/config`)

```conf
# Sway: environment export
exec systemctl --user import-environment WAYLAND_DISPLAY XDG_CURRENT_DESKTOP
exec dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP XDG_SESSION_TYPE

# Start portals after a brief delay
exec sleep 1 && systemctl --user restart xdg-desktop-portal-wlr
exec sleep 2 && systemctl --user restart xdg-desktop-portal
```

### Portal Priority Configuration

When multiple portal backends are installed (e.g. `-hyprland` and `-gtk` are both
present), the base portal must know which backend handles which interface:

```ini
# ~/.config/xdg-desktop-portal/hyprland-portals.conf
[preferred]
default=hyprland;gtk
org.freedesktop.impl.portal.ScreenCast=hyprland
org.freedesktop.impl.portal.Screenshot=hyprland
org.freedesktop.impl.portal.RemoteDesktop=hyprland
org.freedesktop.impl.portal.FileChooser=gtk
org.freedesktop.impl.portal.Settings=gtk
```

```ini
# ~/.config/xdg-desktop-portal/sway-portals.conf
[preferred]
default=wlr;gtk
org.freedesktop.impl.portal.ScreenCast=wlr
org.freedesktop.impl.portal.Screenshot=wlr
org.freedesktop.impl.portal.FileChooser=gtk
```

The filename must match the value of `XDG_CURRENT_DESKTOP` (lowercased). If
`XDG_CURRENT_DESKTOP=Hyprland` the file must be named `hyprland-portals.conf`.

---

## 61.4 Firefox Screen Sharing

Firefox has had Wayland PipeWire screen-capture support since version 86, but several
flags must be enabled for it to use the portal path rather than falling back to a broken
X11 code path. As of Firefox 120+, most of these are enabled by default on Wayland
builds, but older installs or custom builds may still need manual configuration.

The two most impactful `about:config` settings are:

```
media.webrtc.hw.h264.enabled = true
media.peerconnection.video.h264_enabled = true
media.navigator.mediadatadecoder_vpx_enabled = true
widget.use-xdg-desktop-portal.screencast = 1
widget.use-xdg-desktop-portal.file-picker = 1
```

The `widget.use-xdg-desktop-portal.screencast = 1` key explicitly forces Firefox to
request screen capture through the portal rather than the legacy X11 path. On a pure
Wayland session it should default to `1`, but verifying this is worth doing when
debugging.

### Launch Environment

```bash
# ~/.config/environment.d/wayland.conf  (applied to all systemd user units)
MOZ_ENABLE_WAYLAND=1
XDG_CURRENT_DESKTOP=Hyprland
XDG_SESSION_TYPE=wayland
```

Or in your shell profile for interactive Firefox launches:

```bash
# ~/.zshenv or ~/.bashrc
export MOZ_ENABLE_WAYLAND=1
export XDG_CURRENT_DESKTOP=Hyprland   # must match portal config filename
```

### Testing Firefox Screen Share

```bash
# 1. Navigate to a WebRTC test page
# https://web-rtc-experiments.appspot.com/getDisplayMedia/
# https://janus.conf.meetecho.com/screensharingtest.html

# 2. Watch the portal log in real time while triggering the share
journalctl --user -f -u xdg-desktop-portal -u xdg-desktop-portal-hyprland

# 3. Confirm a PipeWire video node appears
pw-cli list-objects | grep -A3 "media.class.*video"
# Expected output when sharing is active:
# id 45, type PipeWire:Interface:Node/3
#   media.class = "Video/Source"
#   node.name = "xdg-desktop-portal"
```

If the selection dialog appears but the video is black, the PipeWire stream is being
created but no frames are arriving. This usually means the compositor backend started
before the compositor fully initialized. Restart portals and try again.

---

## 61.5 Chromium / Chrome Screen Sharing

Chromium-based browsers require explicit flags to activate the PipeWire WebRTC capture
path. Without `--enable-webrtc-pipewire-capturer`, Chromium attempts to use X11 screen
capture which either fails silently on a Wayland session or captures through XWayland
with degraded performance and no window list.

### Per-User Flags Files

```bash
# Chromium
mkdir -p ~/.config/chromium
cat >> ~/.config/chromium-flags.conf << 'EOF'
--enable-webrtc-pipewire-capturer
--ozone-platform=wayland
--enable-features=UseOzonePlatform,WaylandWindowDecorations
--enable-gpu-rasterization
EOF

# Google Chrome
mkdir -p ~/.config/google-chrome
cat >> ~/.config/chrome-flags.conf << 'EOF'
--enable-webrtc-pipewire-capturer
--ozone-platform=wayland
--enable-features=UseOzonePlatform
EOF

# Brave
cat >> ~/.config/brave-flags.conf << 'EOF'
--enable-webrtc-pipewire-capturer
--ozone-platform=wayland
EOF
```

### Electron App Base Flags

Many video-call Electron apps (Slack, Discord, Teams) inherit the same underlying
Chromium WebRTC stack. The pattern is identical:

```bash
# Generic Electron app with PipeWire screen share
app-name \
    --ozone-platform=wayland \
    --enable-webrtc-pipewire-capturer \
    --enable-features=UseOzonePlatform
```

Most Electron apps accept a flags file at `~/.config/<appname>-flags.conf` using the
same format as Chromium.

### Feature Flag Comparison

| Flag | Effect | Required Since |
|------|--------|---------------|
| `--enable-webrtc-pipewire-capturer` | Activates PipeWire capture backend | Chromium 94 |
| `--ozone-platform=wayland` | Use Wayland backend (not XWayland) | Chromium 88 |
| `--enable-features=UseOzonePlatform` | Enable Ozone platform selection | Chromium 87 |
| `--enable-gpu-rasterization` | GPU-accelerated compositing | All versions |
| `--disable-features=WaylandFractionalScaleV1` | Fix blurry UI on fractional scale | Chromium 118+ |

---

## 61.6 Video Call Applications

Different video call applications have varying levels of native Wayland support. The
practical approach is: prefer native Wayland when the app supports it well; fall back to
XWayland for apps with poor Wayland support. XWayland screen sharing captures the entire
XWayland X11 surface, not individual Wayland windows — this often results in sharing a
black screen or the wrong content.

### Discord / Vesktop

The official Discord Linux client is an older Electron build with inconsistent Wayland
support. [Vesktop](https://github.com/Vencord/Vesktop) is a community fork that
packages Discord's web app in a more current Electron with proper Wayland support:

```bash
# AUR: vesktop-bin (binary) or vesktop (from source)
yay -S vesktop-bin

# Launch with Wayland flags
vesktop --ozone-platform=wayland --enable-webrtc-pipewire-capturer

# Or set persistently:
mkdir -p ~/.config/vesktop
echo '--ozone-platform=wayland
--enable-webrtc-pipewire-capturer' >> ~/.config/vesktop/flags.conf
```

For the official Discord flatpak with Wayland screen share:

```bash
flatpak install flathub com.discordapp.Discord
# Grant screen share permission
flatpak override --user --socket=wayland com.discordapp.Discord
```

### Zoom

Zoom's Linux client as of 5.17+ has experimental native Wayland support, but it remains
less stable than the XWayland path. For most users, XWayland is the reliable choice:

```bash
# XWayland mode (most reliable, uses X11 screen capture)
zoom

# Native Wayland mode (experimental, uses PipeWire)
WAYLAND_DISPLAY=$WAYLAND_DISPLAY zoom --enable-webrtc-pipewire-capturer

# Desktop entry override for native Wayland:
mkdir -p ~/.local/share/applications
cp /usr/share/applications/zoom.desktop ~/.local/share/applications/
# Edit the Exec line:
sed -i 's|Exec=zoom|Exec=env WAYLAND_DISPLAY=$WAYLAND_DISPLAY zoom --enable-webrtc-pipewire-capturer|' \
    ~/.local/share/applications/zoom.desktop
```

### Microsoft Teams

The `teams-for-linux` community client (AUR) is the recommended approach since
Microsoft dropped the native Linux Teams app:

```bash
yay -S teams-for-linux-bin

# Wayland launch
teams-for-linux \
    --ozone-platform=wayland \
    --enable-webrtc-pipewire-capturer \
    --enable-features=UseOzonePlatform

# Config file
mkdir -p ~/.config/teams-for-linux
cat > ~/.config/teams-for-linux/config.json << 'EOF'
{
  "chromeFlags": [
    "--ozone-platform=wayland",
    "--enable-webrtc-pipewire-capturer",
    "--enable-features=UseOzonePlatform"
  ]
}
EOF
```

### Slack

Slack distributes a flatpak and an AUR package, both based on Electron:

```bash
# Flatpak
flatpak install flathub com.slack.Slack
flatpak override --user --env=OZONE_PLATFORM=wayland com.slack.Slack
flatpak override --user --env=ELECTRON_OZONE_PLATFORM_HINT=wayland com.slack.Slack

# Native package flags
echo '--ozone-platform=wayland
--enable-webrtc-pipewire-capturer' >> ~/.config/slack-flags.conf
```

### Google Meet / Jitsi / Whereby

Browser-based solutions work natively through the portal setup in §61.3 and §61.4.
No additional application configuration is needed beyond proper Firefox or Chromium
setup. Google Meet specifically works better in Chromium than Firefox due to H.264
hardware encoding support.

### Application Support Matrix

| Application | Native Wayland | Screen Share | Recommended Method |
|-------------|---------------|-------------|-------------------|
| Vesktop (Discord) | Yes | PipeWire portal | `--ozone-platform=wayland` |
| Discord (official) | Partial | Limited | Use Vesktop instead |
| Zoom 5.17+ | Experimental | PipeWire | XWayland fallback |
| Teams-for-Linux | Yes | PipeWire portal | Config JSON |
| Slack flatpak | Yes | PipeWire portal | flatpak override |
| Google Meet (Firefox) | Via browser | PipeWire portal | §61.4 setup |
| Google Meet (Chromium) | Via browser | PipeWire portal | §61.5 setup |
| Jitsi Meet (browser) | Via browser | PipeWire portal | §61.4 setup |

---

## 61.7 OBS Studio Screen Capture

OBS Studio 27.0+ has native PipeWire screen capture support via the `obs-pipewire`
plugin (included by default in most distributions' OBS package). On Wayland, OBS uses
this path exclusively — the legacy X11 window capture source is still present but
captures XWayland surfaces only.

### Installation and Initial Setup

```bash
# Arch
sudo pacman -S obs-studio

# Fedora
sudo dnf install obs-studio

# Launch — OBS detects Wayland automatically via WAYLAND_DISPLAY
obs

# Verify PipeWire capture is available
obs --help 2>&1 | grep -i pipewire
```

### Adding a Screen Capture Source

1. In OBS, click `+` in the Sources panel
2. Select "Screen Capture (PipeWire)"
3. Click OK — this triggers the xdg-desktop-portal ScreenCast dialog
4. In the portal dialog, choose "Entire Screen", "Single Window", or select specific
   outputs
5. Click "Share" to confirm

For persistent scene sources (so the portal dialog doesn't re-appear on each OBS
restart), OBS stores the PipeWire node ID in the scene collection. If the compositor
restarts, the node ID changes and OBS must re-request the session.

### Window vs. Output Capture

```bash
# OBS source type capabilities by compositor backend

# xdg-desktop-portal-hyprland: supports
#   - Full output (monitor) capture
#   - Per-window (toplevel) capture   <- requires hyprland-toplevel-export-v1
#   - Region selection

# xdg-desktop-portal-wlr: supports
#   - Full output (monitor) capture only
#   - No per-window capture (wlroots limitation without ext-image-copy-capture)
#   - Region via slurp chooser
```

### Virtual Camera for Video Calls

OBS virtual camera allows feeding OBS output (with scenes, overlays, backgrounds) into
any video call app as if it were a webcam:

```bash
# Load the v4l2loopback kernel module
sudo modprobe v4l2loopback \
    devices=1 \
    video_nr=10 \
    card_label="OBS Virtual Camera" \
    exclusive_caps=1

# Make it persistent across reboots
echo "v4l2loopback" | sudo tee /etc/modules-load.d/v4l2loopback.conf
echo 'options v4l2loopback devices=1 video_nr=10 card_label="OBS Virtual Camera" exclusive_caps=1' \
    | sudo tee /etc/modprobe.d/v4l2loopback.conf

# In OBS: Tools → Virtual Camera → Start
# The virtual camera appears as /dev/video10 in all apps
```

Verify the virtual camera device:

```bash
v4l2-ctl --list-devices
# Output should include:
# OBS Virtual Camera (platform:v4l2loopback-000):
#         /dev/video10

# Test the feed
mpv /dev/video10
```

### OBS PipeWire Audio Capture

```bash
# Install audio capture plugin
sudo pacman -S obs-pipewire-audio-capture  # Arch
sudo dnf install obs-studio-plugin-pipewire-audio  # Fedora

# In OBS: + → "Audio Output Capture (PipeWire)"
# Select the audio sink to capture (desktop audio, application audio, etc.)
```

### Recording with Hardware Encoding

```bash
# In OBS Settings → Output → Recording:
# Encoder: VAAPI H.264 (AMD/Intel) or NVENC H.264 (NVIDIA)

# Verify hardware encoder availability
vainfo 2>/dev/null | grep H264
# or
obs-vaapi --help  # if obs-vaapi plugin is installed
```

---

## 61.8 xdg-desktop-portal-wlr for Sway

`xdg-desktop-portal-wlr` (xdpw) is the wlroots-based backend used with Sway and other
pure wlroots compositors. Unlike the Hyprland backend, it does not support per-window
capture (only full output capture), because wlroots does not expose the per-toplevel
screencopy protocol. Region selection is possible via an external command.

### Configuration File

```ini
# ~/.config/xdg-desktop-portal-wlr/config
# (or /etc/xdg/xdg-desktop-portal-wlr/config for system-wide defaults)

[screencast]
# Specific output to capture (run `swaymsg -t get_outputs` for names)
output_name=DP-1
max_fps=60
# exec_before: command run before screencopy (optional)
# exec_after: command run after screencopy closes (optional)

# How to present a selection UI to the user:
# simple: use the first available output matching output_name
# dmenu: pipe output list through a dmenu-compatible launcher
# wofi: pipe through wofi
# slurp: use slurp for region/output selection
chooser_type=dmenu
chooser_cmd=wofi --show=dmenu
```

For slurp-based output selection (user clicks on a monitor to select it):

```ini
[screencast]
chooser_type=simple
chooser_cmd=slurp -f %o -o
```

### Multi-Monitor Output Selection with Wofi

```bash
# The chooser_cmd receives output names on stdin and the user picks one
# Example: pipe to wofi for a searchable picker
chooser_cmd=wofi --show=dmenu --prompt="Select screen:"

# Example: pipe to fuzzel
chooser_cmd=fuzzel --dmenu --prompt="Select screen: "
```

### Checking Available Outputs for xdpw

```bash
# List available Sway outputs
swaymsg -t get_outputs | jq '.[].name'
# Example output:
# "DP-1"
# "HDMI-A-1"

# Match output_name in config to one of these values
```

---

## 61.9 NixOS Configuration

NixOS requires declarative configuration for the entire portal stack. Imperative setup
(installing packages manually, setting env vars in shell profiles) does not work
reliably because NixOS manages service activation differently.

### NixOS with Hyprland (Home Manager + System Config)

```nix
# /etc/nixos/configuration.nix

{ config, pkgs, ... }:
{
  # PipeWire audio/video stack
  security.rtkit.enable = true;
  services.pipewire = {
    enable = true;
    alsa.enable = true;
    alsa.support32Bit = true;
    pulse.enable = true;
    jack.enable = false;
    wireplumber.enable = true;
  };

  # D-Bus is required for portal operation
  services.dbus.enable = true;

  # Portal configuration
  xdg.portal = {
    enable = true;
    # Hyprland portal + GTK portal for file pickers
    extraPortals = with pkgs; [
      xdg-desktop-portal-hyprland
      xdg-desktop-portal-gtk
    ];
    # Route ScreenCast to hyprland backend, FileChooser to gtk
    config.hyprland = {
      default = [ "hyprland" "gtk" ];
      "org.freedesktop.impl.portal.ScreenCast" = "hyprland";
      "org.freedesktop.impl.portal.Screenshot" = "hyprland";
      "org.freedesktop.impl.portal.FileChooser" = "gtk";
    };
  };

  # Hyprland compositor
  programs.hyprland = {
    enable = true;
    xwayland.enable = true;
  };

  environment.systemPackages = with pkgs; [
    pipewire
    wireplumber
    xdg-desktop-portal
    xdg-desktop-portal-hyprland
    xdg-desktop-portal-gtk
  ];
}
```

### NixOS with Sway

```nix
# /etc/nixos/configuration.nix  (Sway variant)

{
  programs.sway = {
    enable = true;
    wrapperFeatures.gtk = true;
    extraSessionCommands = ''
      export XDG_CURRENT_DESKTOP=sway
      export XDG_SESSION_TYPE=wayland
    '';
  };

  xdg.portal = {
    enable = true;
    extraPortals = with pkgs; [
      xdg-desktop-portal-wlr
      xdg-desktop-portal-gtk
    ];
    config.sway = {
      default = [ "wlr" "gtk" ];
      "org.freedesktop.impl.portal.ScreenCast" = "wlr";
      "org.freedesktop.impl.portal.FileChooser" = "gtk";
    };
    wlr.settings.screencast = {
      output_name = "DP-1";
      max_fps = 30;
      chooser_type = "simple";
      chooser_cmd = "slurp -f %o -o";
    };
  };
}
```

### Home Manager Environment Variables

```nix
# home.nix
{ config, pkgs, ... }:
{
  home.sessionVariables = {
    MOZ_ENABLE_WAYLAND = "1";
    XDG_CURRENT_DESKTOP = "Hyprland";
    XDG_SESSION_TYPE = "wayland";
    WAYLAND_DISPLAY = "wayland-1";
  };

  # Ensure portal env is available to systemd user units
  systemd.user.sessionVariables = {
    WAYLAND_DISPLAY = "wayland-1";
    XDG_CURRENT_DESKTOP = "Hyprland";
    XDG_SESSION_TYPE = "wayland";
  };
}
```

---

## 61.10 Troubleshooting

Screen sharing failures fall into several distinct categories. The systematic approach
below eliminates each layer in sequence so that failures are isolated quickly rather than
guessed at.

### Diagnostic Checklist

```bash
# === STEP 1: Verify PipeWire is running ===
systemctl --user status pipewire pipewire-pulse wireplumber
# All three must show "active (running)"
# If not: systemctl --user start pipewire pipewire-pulse wireplumber

# === STEP 2: Verify portal services are running ===
systemctl --user status xdg-desktop-portal
systemctl --user status xdg-desktop-portal-hyprland   # or -wlr

# Check which backend is actually handling ScreenCast:
gdbus introspect --session \
    --dest org.freedesktop.portal.Desktop \
    --object-path /org/freedesktop/portal/desktop \
    --only-properties 2>&1 | grep version

# === STEP 3: Verify environment variables are in systemd session ===
systemctl --user show-environment | grep -E "WAYLAND_DISPLAY|XDG_CURRENT_DESKTOP|XDG_SESSION_TYPE"
# Required output:
# WAYLAND_DISPLAY=wayland-1
# XDG_CURRENT_DESKTOP=Hyprland
# XDG_SESSION_TYPE=wayland

# If missing, run and then restart portals:
systemctl --user import-environment WAYLAND_DISPLAY XDG_CURRENT_DESKTOP XDG_SESSION_TYPE

# === STEP 4: Watch portal logs in real time while triggering a share ===
journalctl --user -f \
    -u xdg-desktop-portal \
    -u xdg-desktop-portal-hyprland \
    -u xdg-desktop-portal-wlr

# === STEP 5: Check for active PipeWire video nodes ===
# Trigger a screen share in your browser, then run:
pw-cli list-objects | grep -B2 -A10 "Video/Source"
# A node should appear while sharing; absence means portal never created the stream

# === STEP 6: D-Bus portal interface test ===
busctl --user call \
    org.freedesktop.portal.Desktop \
    /org/freedesktop/portal/desktop \
    org.freedesktop.portal.ScreenCast \
    GetAvailableTypes \
    u 0
# Expected: some non-zero type flags
```

### Verbose Portal Debugging

```bash
# Kill automatic portal instances
systemctl --user stop xdg-desktop-portal xdg-desktop-portal-hyprland

# Run backend manually with verbose output
/usr/lib/xdg-desktop-portal-hyprland --verbose 2>&1 | tee /tmp/xdph.log &
sleep 1
/usr/lib/xdg-desktop-portal --verbose 2>&1 | tee /tmp/xdp.log &

# Trigger a screen share, then inspect the logs
grep -E "error|fail|ScreenCast|PipeWire" /tmp/xdph.log /tmp/xdp.log
```

### Common Problems and Fixes

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| No selection dialog appears | Portal not running or env vars missing | Restart portals; check `systemctl --user show-environment` |
| Dialog appears, then black screen | Portal started before compositor was ready | Add `sleep 2` before portal launch in `exec-once` |
| "Permission denied" in portal log | `WAYLAND_DISPLAY` missing from systemd env | Run `systemctl --user import-environment WAYLAND_DISPLAY` |
| Works in OBS but not browser | Browser missing `--enable-webrtc-pipewire-capturer` | Add flag to browser flags file |
| Works once, breaks after compositor restart | PipeWire node IDs are stale | Restart portals after compositor restart |
| Screen share freezes after 30s | Portal timeout due to inactivity | Check `inhibit_screensaver` or PipeWire keepalive settings |
| xdpw: "No outputs available" | `output_name` in xdpw config doesn't match actual output | Run `swaymsg -t get_outputs` and update config |
| Hyprland: per-window capture missing | Old version of `-hyprland` backend | Update to `xdg-desktop-portal-hyprland >= 1.3.0` |
| Flatpak app can't share screen | Missing Wayland socket permission | `flatpak override --user --socket=wayland <appid>` |
| Screen sharing works but cursor missing | Cursor capture not supported by wlroots backend | Use full-output capture; per-window never includes cursor |

### Confirming a Working Setup End-to-End

```bash
# Full verification script
#!/usr/bin/env bash
set -euo pipefail

echo "=== PipeWire ==="
systemctl --user is-active pipewire && echo "OK" || echo "FAIL"
systemctl --user is-active wireplumber && echo "OK" || echo "FAIL"

echo "=== Portals ==="
systemctl --user is-active xdg-desktop-portal && echo "OK" || echo "FAIL"
(systemctl --user is-active xdg-desktop-portal-hyprland || \
 systemctl --user is-active xdg-desktop-portal-wlr) && echo "backend OK" || echo "backend FAIL"

echo "=== Environment ==="
systemctl --user show-environment | grep -E "WAYLAND_DISPLAY=|XDG_CURRENT_DESKTOP=" || echo "MISSING"

echo "=== D-Bus Portal ==="
busctl --user list | grep -q org.freedesktop.portal.Desktop && echo "OK" || echo "FAIL"

echo "=== PipeWire nodes ==="
pw-cli list-objects | grep -c "PipeWire:Interface:Node" && echo "nodes present" || echo "no nodes"
```

Save as `~/bin/check-screen-share.sh`, make it executable, and run before debugging
further.

### Portal Restart Helper

Add this to your Hyprland config for a quick portal restart bind:

```conf
# hyprland.conf
bind = $mod, F9, exec, \
    systemctl --user restart xdg-desktop-portal-hyprland && \
    sleep 1 && \
    systemctl --user restart xdg-desktop-portal && \
    notify-send "Portals restarted"
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
