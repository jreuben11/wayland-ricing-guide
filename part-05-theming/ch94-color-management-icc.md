# Chapter 94 — Color Management and ICC Profiles

## Overview

Color management ensures that what you see on screen matches the intent of the
content creator — and that your display's quirks (yellow tint, blue oversaturation,
narrow color gamut) are compensated for. This is distinct from night-light
(ch60), which shifts the color temperature for circadian rhythm. Color management
is about accuracy: ICC profiles, display calibration, wide-gamut, and HDR.

---

## 94.1 Why It Matters for Ricing

- Photo editing, digital art: wrong colors in GIMP/Krita/Inkscape
- Wide-gamut displays (DCI-P3, AdobeRGB): oversaturated default output
  that makes everything look garish without a profile
- Budget displays: factory calibration is often 10+ ΔE off
- Matching colors between displays: what looks great on one monitor
  looks wrong on another without profiles

---

## 94.2 Color Concepts

| Term | Meaning |
|------|---------|
| Color gamut | Range of colors a display can produce |
| sRGB | Standard gamut (roughly 35% of visible spectrum) |
| DCI-P3 | Digital cinema gamut (~45% visible; common on Apple, OLED screens) |
| AdobeRGB | Wide gamut for print photography |
| ICC profile | File mapping display output to a reference color space |
| ΔE (Delta-E) | Perceptual color difference; <2 is imperceptible, >5 is obvious |
| HDR | High dynamic range: luminance from ~0.001 to 10,000 nits |
| SDR → HDR tonemapping | Converting content intended for 100nit displays to HDR |

---

## 94.3 colord — The Color Management Daemon

`colord` manages ICC profiles and display device associations on Linux:

```bash
sudo pacman -S colord
sudo systemctl enable --now colord

# List known devices
colormgr get-devices

# List installed profiles
colormgr get-profiles

# Get profiles for a specific device
colormgr device-get-default-profile \
  "xrandr-$(xrandr --listmonitors | grep '\*' | awk '{print $NF}')"
```

### Assigning a profile manually

```bash
# Add a profile to colord
colormgr import-profile ~/Downloads/my-monitor.icc

# Get the device ID for your monitor
colormgr get-devices | grep -A3 "display"

# Assign profile to device
colormgr device-add-profile \
  "xrandr-HDMI-1" \
  "icc-$(colormgr get-profiles | grep 'my-monitor' | head -1 | grep -o 'icc-[0-9a-f]*')"

colormgr device-make-profile-default \
  "xrandr-HDMI-1" \
  "icc-..."
```

---

## 94.4 Applying ICC Profiles on Wayland

The color management protocol landscape for Wayland is in flux in 2025–2026:
- `wp-color-management-v1` is the emerging standard (merged into wayland-protocols)
- KDE Plasma 6.4+ implements it
- GNOME 47+ has experimental support
- Hyprland/wlroots: in progress; not stable as of 2025

**Current working approach for Hyprland/Sway: use xcalib or dispwin at session start.**

### xcalib (applies gamma/LUT from ICC)

```bash
sudo pacman -S xcalib

# Apply an ICC profile's gamma curve to the display
# Note: xcalib uses the X11 color calibration path via XWayland
# On pure Wayland, this only works if XWayland is running
DISPLAY=:0 xcalib -d :0 -s 0 ~/icc/my-monitor.icc
```

### dispwin (ArgyllCMS, more complete)

```bash
paru -S argyllcms

# Apply ICC profile to display (Wayland via DRM gamma)
dispwin -d 1 ~/icc/my-monitor.icc

# Verify it was applied
dispwin -r   # read back applied profile
```

`dispwin` can write to the DRM gamma LUT directly on some systems, bypassing
the need for XWayland.

### Apply at session start

```conf
# hyprland.conf
exec-once = dispwin -d 1 ~/.config/icc/monitor-srgb.icc
```

---

## 94.5 Display Calibration with DisplayCAL

DisplayCAL is a GUI frontend for ArgyllCMS that guides you through a full
calibration workflow with a colorimeter.

```bash
paru -S displaycal
# Requires a colorimeter: X-Rite i1Display, Datacolor Spyder, etc.
```

### Calibration workflow

1. Launch DisplayCAL, select your colorimeter
2. Select your display, create a measurement profile
3. Run the calibration (white point, tone response, black point)
4. DisplayCAL generates an `.icc` file
5. Apply with colord or dispwin (see above)

Without a colorimeter, use community-shared profiles from:
- `icc.directory` — community database
- Monitor manufacturer downloads
- `notebookcheck.net` — many laptop display profiles

### ArgyllCMS CLI (no GUI)

```bash
# List displays
dispwin -?

# Quick characterization (no colorimeter, measures factory settings)
dispcal -d 1 -v -qh -t 6500 -g 2.2 my-calibration
# → generates my-calibration.icc and my-calibration.cal

# Apply calibration
dispwin -d 1 my-calibration.icc

# Load LUT from calibration
applycal -v my-calibration.cal
```

---

## 94.6 ICC Profiles for Common Scenarios

### sRGB clamp for wide-gamut displays

Wide-gamut displays (DCI-P3, AdobeRGB) oversaturate content that targets sRGB.
An sRGB-emulation profile tells the system to limit output to sRGB gamut:

```bash
# Most displays ship an sRGB mode; enable it in OSD first
# If not available, use a software profile:
paru -S icc-profiles    # includes sRGB IEC61966-2.1 reference profile
```

### NightColor / night light vs. ICC

Night light (wlsunset, hyprsunset — ch60) modifies the display LUT to
reduce blue light. ICC calibration also modifies the LUT. **Applying both
simultaneously overwrites one with the other** — the last one written wins.

Recommended approach:
1. Apply ICC calibration at startup
2. Use night light software that composites on top (KDE Plasma's night light
   does this correctly; wlsunset may conflict — disable one)

---

## 94.7 HDR Color Management

HDR on Wayland requires:
1. A compositor that supports `wp-color-management-v1` (KDE Plasma 6.4+)
2. An HDR-capable display (DisplayHDR 400/600/True Black)
3. The display connected via DisplayPort 1.4 or HDMI 2.1

### KDE Plasma HDR setup

```
System Settings → Display & Monitor → HDR → Enable
                                    → SDR Color Intensity
                                    → Peak Brightness
```

KDE auto-detects HDR capability and applies BT.2100 PQ tone mapping.

### Hyprland HDR (preview)

```conf
# Hyprland 0.42+ with experimental HDR
monitor = DP-1, 3840x2160@144, 0x0, 1, bitdepth, 10
misc:vrr = 1
```

Full HDR support in Hyprland/wlroots is not production-ready in 2025 — the
`wp-color-management-v1` implementation is in progress. Use KDE Plasma 6 for
production HDR workflows.

---

## 94.8 Color Profiles for Applications

### Firefox

```
about:config
  gfx.color_management.mode = 1       # enable color management
  gfx.color_management.display_profile  = /path/to/profile.icc
```

### GIMP

```
Edit → Preferences → Color Management
  → Monitor Profile: select your ICC file
  → RGB Working Space: sRGB (for web) or AdobeRGB (for print)
```

### Krita

```
Settings → Krita Preferences → Color Management
  → Use system monitor profile
```

---

## 94.9 Checking Display Gamut

```bash
# Check if your display reports wide-gamut via EDID
sudo cat /sys/class/drm/card0-*/edid | edid-decode 2>/dev/null | grep -i "color\|gamut"

# Or use edid-decode directly
sudo pacman -S edid-decode
sudo cat /sys/class/drm/card0-HDMI-A-1/edid | edid-decode | grep -A10 "Chromaticity"
```

The chromaticity coordinates tell you the gamut. If the red primary is around
0.640, 0.330 and blue is 0.150, 0.060 — it's sRGB. Values outside this
indicate wide-gamut.

---

## 94.10 HDR Step-by-Step: KDE Plasma 6

KDE Plasma 6.1+ has the most complete HDR implementation on Linux Wayland. Here is a verified end-to-end setup:

### Prerequisites

```bash
# Kernel 6.4+ (check)
uname -r

# Check display HDR capability
cat /sys/class/drm/card0-DP-1/hdr_sink_metadata 2>/dev/null | head -5
# If the file exists and has content, your display supports HDR metadata

# Check EDID for HDR capability
sudo pacman -S edid-decode
sudo cat /sys/class/drm/card0-DP-1/edid | edid-decode 2>/dev/null | grep -A5 "HDR"

# Verify DisplayPort 1.4 or HDMI 2.1 cable (required for HDR10)
# HDMI 2.0 = no HDR metadata; HDMI 2.1 or DP 1.4 = HDR metadata support
```

### Enable in KDE Plasma

```bash
# Via System Settings (GUI):
# System Settings → Display & Monitor → select your display → HDR → ON
# Set SDR Brightness: 100–200 nits (ambient light dependent)
# Set SDR Color Intensity: 1.0 (default)

# Via kscreen-doctor (CLI):
kscreen-doctor output.DP-1.hdr.enable

# Verify HDR is active
kscreen-doctor --json | python3 -c "
import json,sys
data = json.load(sys.stdin)
for out in data.get('outputs',[]):
    print(out.get('name'), 'HDR:', out.get('hdr', {}).get('enabled', False))
"
```

### Verify HDR Metadata Transmission

```bash
# Check that HDR metadata is being sent to the display
sudo cat /sys/class/drm/card0-DP-1/hdr_output_metadata
# Non-zero output = HDR active

# KWin debug log
journalctl --user -u plasma-kwin_wayland | grep -i "hdr\|color" | tail -20

# In an HDR-capable Vulkan app, verify it's using VK_EXT_hdr_metadata:
vulkaninfo 2>/dev/null | grep -i "hdr\|color_space"
```

### SDR Application Tonemapping

When HDR is active, KWin applies SDR→HDR tonemapping to apps that don't declare HDR output. The tonemapping curve is configurable:

```bash
# kwin HDR tonemapping brightness (0.0–1.0, default 0.5)
# Via System Settings → Display → HDR → SDR Color Intensity
# Higher = more vivid SDR content on HDR display
```

### Testing with an HDR Video

```bash
# mpv with HDR passthrough (when KWin/gamescope handles tonemapping)
mpv --vo=gpu-next --gpu-api=vulkan \
    --target-colorspace-hint=yes \
    ~/Videos/hdr-sample.mkv

# mpv with built-in tonemapping (when compositor does NOT handle HDR)
mpv --vo=gpu-next --hdr-compute-peak=yes \
    --tone-mapping=mobius \
    ~/Videos/hdr-sample.mkv
```

---

## 94.11 Per-Monitor ICC Profiles (Dual Monitor Setup)

When using two monitors with different color characteristics, assign separate ICC profiles:

```bash
# Identify monitor device IDs
colormgr get-devices
# Output example:
# Device ID: xrandr-HDMI-1
# Device ID: xrandr-DP-1

# Import both profiles
colormgr import-profile ~/icc/left-monitor.icc
colormgr import-profile ~/icc/right-monitor.icc

# List imported profiles and get their IDs
colormgr get-profiles | grep -A2 "icc-"

# Assign profiles to devices
colormgr device-make-profile-default \
    "xrandr-HDMI-1" \
    "icc-<id-of-left-profile>"

colormgr device-make-profile-default \
    "xrandr-DP-1" \
    "icc-<id-of-right-profile>"
```

### Per-Monitor via dispwin (direct DRM gamma)

```bash
# Apply different ICC to each monitor using dispwin
# -d 1 = first display, -d 2 = second display
dispwin -d 1 ~/icc/left-monitor.icc &
dispwin -d 2 ~/icc/right-monitor.icc &

# In session startup (Hyprland):
exec-once = dispwin -d 1 ~/.config/icc/hdmi-monitor.icc
exec-once = dispwin -d 2 ~/.config/icc/dp-monitor.icc
```

### Night Light + ICC Coexistence

The conflict between night light tools (wlsunset, hyprsunset) and ICC profiles comes from both modifying the DRM CRTC gamma LUT:

```bash
# Strategy: apply ICC at startup, let night light override in evening
# (last write wins — night light will override ICC at sunset)

# Hyprland exec-once order:
exec-once = dispwin -d 1 ~/.config/icc/monitor.icc   # runs once at startup
exec-once = hyprsunset -t 4500                         # runs continuously, overrides at sunset

# To restore ICC after night light disables in the morning:
# Add a systemd timer that re-applies ICC at 8 AM
# ~/.config/systemd/user/icc-restore.service
[Unit]
Description=Restore ICC profile after night light
[Service]
ExecStart=/usr/bin/dispwin -d 1 %h/.config/icc/monitor.icc
Type=oneshot

# ~/.config/systemd/user/icc-restore.timer
[Unit]
Description=Restore ICC at sunrise
[Timer]
OnCalendar=07:00:00
Persistent=true
[Install]
WantedBy=timers.target
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
