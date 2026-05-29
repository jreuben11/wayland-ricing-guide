# Chapter 61 — Screen Sharing and Video Calls: Portal Setup, WebRTC, OBS

## Overview
Screen sharing is a daily need for remote workers. On Wayland it requires
the xdg-desktop-portal stack to be correctly set up. When it works, it's
seamless; when it breaks, it's silent. This chapter makes it work.

## Sections

### 61.1 How Screen Sharing Works on Wayland
```
Browser/App
  → WebRTC/PipeWire API
    → xdg-desktop-portal (ScreenCast interface)
      → xdg-desktop-portal-hyprland (compositor backend)
        → wlr-screencopy-unstable-v1 protocol
          → Compositor captures frames
            → PipeWire stream
              → Back to the app
```

All screen capture goes through PipeWire. The portal shows a selection UI.
The compositor captures frames via the screencopy protocol.

### 61.2 Required Packages
```bash
# Hyprland
sudo pacman -S \
    xdg-desktop-portal \
    xdg-desktop-portal-hyprland \
    xdg-desktop-portal-gtk \
    pipewire pipewire-pulse wireplumber

# Sway
sudo pacman -S \
    xdg-desktop-portal \
    xdg-desktop-portal-wlr \
    xdg-desktop-portal-gtk \
    pipewire pipewire-pulse wireplumber
```

### 61.3 Startup Configuration (The Critical Part)
```conf
# hyprland.conf — in correct order
exec-once = dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP XDG_SESSION_TYPE
exec-once = systemctl --user import-environment WAYLAND_DISPLAY XDG_CURRENT_DESKTOP
exec-once = sleep 1 && /usr/lib/xdg-desktop-portal-hyprland
exec-once = sleep 2 && /usr/lib/xdg-desktop-portal --replace
```

The `sleep` values matter: the compositor must be fully ready before the portal
starts, otherwise screencopy initialization fails.

### 61.4 Firefox Screen Sharing

**about:config settings:**
```
media.webrtc.hw.h264.enabled = true
media.peerconnection.video.h264_enabled = true
```

**Test screen sharing:**
1. Go to https://web-rtc-experiments.appspot.com/getDisplayMedia/
2. Click "Share Screen" — you should get a window/screen selection dialog
3. If you get a blank black screen: portal is not working (see debugging below)

**Firefox-specific portal fix:**
```bash
# Ensure this env is set
export XDG_CURRENT_DESKTOP=Hyprland
# And Firefox knows to use portal
export MOZ_ENABLE_WAYLAND=1
```

### 61.5 Chromium / Chrome Screen Sharing
```bash
# Launch flags
chromium --ozone-platform=wayland \
    --enable-features=UseOzonePlatform \
    --enable-webrtc-pipewire-capturer
```

Alternatively in `~/.config/chromium-flags.conf`:
```
--enable-webrtc-pipewire-capturer
--ozone-platform=wayland
```

### 61.6 Video Call Apps

**Discord:**
```bash
# Install via AUR: discord-wayland or use vesktop
vesktop --ozone-platform=wayland
```
Vesktop (Discord fork): better Wayland support than official Discord.

**Zoom:**
```bash
zoom --platform xcb   # runs XWayland (most reliable)
# or native Wayland:
zoom --enable-webrtc-pipewire-capturer
```

**Teams (Linux app):**
```bash
teams-for-linux --ozone-platform=wayland
```

**Google Meet / Jitsi:** Work via browser with proper portal setup (§61.4).

### 61.7 OBS Studio Screen Capture

OBS on Wayland uses PipeWire for screen capture:
1. Install OBS: `sudo pacman -S obs-studio`
2. Start OBS: `obs` (it detects Wayland automatically)
3. Add source: `+` → `Screen Capture (PipeWire)`
4. Select window or screen in the portal dialog
5. For window capture: select specific window (not full screen)

**OBS PipeWire plugin** (if built-in capture doesn't work):
```bash
sudo pacman -S obs-pipewire-audio-capture
```

**Virtual camera (for video calls):**
```bash
sudo modprobe v4l2loopback devices=1 video_nr=10 card_label="OBS Virtual Camera"
# In OBS: Tools → Virtual Camera → Start
```

### 61.8 xdg-desktop-portal-wlr for Sway

`xdg-desktop-portal-wlr` requires manual output/window selection via slurp:
```conf
# /etc/xdg/xdg-desktop-portal-wlr/config (or ~/.config/...)
[screencast]
output_name=DP-1
max_fps=30
chooser_type=simple
chooser_cmd=slurp -f %o -o
# or: chooser_cmd=wofi --show=dmenu
```

### 61.9 Debugging Screen Sharing

**Step-by-step diagnosis:**
```bash
# 1. Check portals are running
systemctl --user status xdg-desktop-portal
systemctl --user status xdg-desktop-portal-hyprland

# 2. Check PipeWire
systemctl --user status pipewire
pw-cli list-objects | grep video  # should show video streams when sharing

# 3. Check environment
systemctl --user show-environment | grep -E "WAYLAND|DESKTOP"

# 4. Test portal directly
dbus-send --session --print-reply \
    --dest=org.freedesktop.portal.Desktop \
    /org/freedesktop/portal/desktop \
    org.freedesktop.portal.ScreenCast.CreateSession \
    dict:string:variant:""

# 5. Enable debug logging
systemctl --user stop xdg-desktop-portal xdg-desktop-portal-hyprland
/usr/lib/xdg-desktop-portal-hyprland --verbose 2>&1 &
/usr/lib/xdg-desktop-portal --verbose 2>&1 &
```

**Common fixes:**
| Problem | Fix |
|---------|-----|
| No selection dialog appears | Restart portal services |
| Black screen in video call | `XDG_CURRENT_DESKTOP` not set correctly |
| Screen share works in OBS but not browser | Browser missing WebRTC PipeWire flag |
| Selection dialog appears but no stream | PipeWire not running |
| Works once then breaks | Add `sleep 1-2` before portal in exec-once |

### 61.10 PipeWire Screen Share on NixOS
```nix
services.pipewire.enable = true;
xdg.portal = {
    enable = true;
    extraPortals = [ pkgs.xdg-desktop-portal-hyprland pkgs.xdg-desktop-portal-gtk ];
    config.hyprland.default = [ "hyprland" "gtk" ];
};
# Ensure dbus session is started
services.dbus.enable = true;
```
