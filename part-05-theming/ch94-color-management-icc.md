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

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
