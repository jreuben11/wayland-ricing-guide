# Chapter 102 — Wine Wayland: Native Windows Apps Without XWayland

## Overview

Wine 9.0 merged a native Wayland backend that renders Windows applications
directly to Wayland surfaces — no X server, no XWayland, no rootless X11.
The result: Wine apps that obey Wayland's security model, respect compositor
window rules by `app_id`, and avoid the DPI/scaling friction of XWayland.
This chapter covers setup, Steam/Proton integration, window rule targeting,
and current limitations.

---

## 102.1 The Old Problem

Before the Wayland driver, every Wine application ran through XWayland:

```
Wine app → Win32 GDI/D3D → X11 driver → XWayland → Wayland compositor
```

This meant:
- Window rules couldn't target Wine windows by Wayland `app_id`
- Fractional scaling broken (XWayland renders at 1× then upscales)
- Security perimeter expanded (all Wine apps share the X11 seat)
- Clipboard, input method, and IME issues

The Wayland driver replaces the X11 path:
```
Wine app → Win32 GDI/D3D → Wayland driver → Wayland compositor
```

---

## 102.2 Installation

### Arch Linux

```bash
# Enable multilib repository first (/etc/pacman.conf):
# [multilib]
# Include = /etc/pacman.d/mirrorlist

# Wine with Wayland support (mainline Wine 9.0+)
sudo pacman -S wine wine-mono wine-gecko

# Or: wine-staging for additional patches
paru -S wine-staging

# Verify Wayland driver is present
ls /usr/lib/wine/x86_64-unix/winewayland.drv
```

### Verifying the driver build

```bash
wine --version   # should be 9.0 or newer

# Check available Wine drivers
ls /usr/lib/wine/x86_64-unix/ | grep drv
# Should include: winex11.drv  winewayland.drv  wineandroid.drv
```

---

## 102.3 Running Wine Apps on Wayland

### Method 1: WAYLAND_DISPLAY environment variable

```bash
# Unset DISPLAY so Wine won't try X11
DISPLAY= WAYLAND_DISPLAY=wayland-1 wine myapp.exe

# Or explicitly select the Wayland driver:
DISPLAY= WINE_WAYLAND_DRIVER=1 wine myapp.exe
```

### Method 2: winecfg per-prefix configuration

```bash
# Create a Wayland-native Wine prefix
WINEPREFIX=~/.wine-wayland DISPLAY= wine winecfg
```

In winecfg → Graphics tab → set the "Desktop" to use Wayland (if option is present).

### Method 3: Shell wrapper

```bash
#!/bin/bash
# ~/.local/bin/winewayland
unset DISPLAY
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-1}"
exec wine "$@"
```

```bash
chmod +x ~/.local/bin/winewayland
winewayland myapp.exe
```

---

## 102.4 Hyprland Window Rules for Wine Apps

With the Wayland driver, Wine apps have a real `app_id`. By default it is
`wine` or the executable name. Target them in `hyprland.conf`:

```conf
# Float all Wine apps
windowrulev2 = float, class:^(wine)$

# Float a specific app
windowrulev2 = float, class:^(explorer.exe)$
windowrulev2 = float, class:^(notepad.exe)$

# Specific sizing
windowrulev2 = float,        class:^(winecfg.exe)$
windowrulev2 = size 800 600, class:^(winecfg.exe)$
windowrulev2 = center,       class:^(winecfg.exe)$

# Move to a specific workspace
windowrulev2 = workspace 5 silent, class:^(steam_app_)(.*)$
```

Check the actual `class` of your Wine app:
```bash
hyprctl clients -j | jq '.[] | select(.xwayland==false) | {class, title}'
```

---

## 102.5 Steam and Proton

Steam itself runs natively on Wayland when launched with:
```bash
STEAM_FORCE_DESKTOP_CLIENT=1 steam
# or:
DISPLAY= steam
```

### Proton with Wayland

For Steam games using Proton, the Wayland backend is enabled via launch options:

```
# In Steam game properties → Launch Options:
PROTON_ENABLE_WAYLAND=1 %command%
```

Or globally in `~/.config/environment.d/wayland.conf`:
```ini
PROTON_ENABLE_WAYLAND=1
```

### Which Proton version

Proton-GE (community build) often has better Wayland support than stock Proton:
```bash
paru -S protonup-qt
# Use ProtonUp-Qt to install Proton-GE
```

Select Proton-GE in Steam → Settings → Compatibility → Proton version.

### gamescope as fallback

For games that don't work with the Wayland driver, use gamescope (a nested
compositor — see Ch 42):
```bash
gamescope -W 1920 -H 1080 -f -- wine game.exe
```

---

## 102.6 DXVK and VKD3D-Proton

DXVK (DirectX 9/10/11 → Vulkan) and VKD3D-Proton (DirectX 12 → Vulkan) work
unchanged with the Wayland driver — they translate at the D3D API level before
presentation, so the display backend doesn't matter.

```bash
# Install DXVK manually for a prefix:
paru -S dxvk-bin
setup_dxvk install --symlink

# Check DXVK is active:
DXVK_LOG_LEVEL=info DISPLAY= wine dxdiag 2>&1 | grep DXVK
```

### Vulkan layer for frame timing

```bash
# MangoHud (FPS overlay) works on Wayland Wine:
paru -S mangohud
MANGOHUD=1 DISPLAY= wine game.exe
```

---

## 102.7 HiDPI and Fractional Scaling

The Wayland driver receives the correct scale factor from the compositor via
`wl_output.scale` and `wp_fractional_scale_v1`. Wine DPI is set automatically:

```bash
# Verify Wine DPI matches compositor scale
DISPLAY= wine reg query "HKCU\Control Panel\Desktop" /v LogPixels
```

If Wine apps appear too small/large, force DPI:
```bash
# 96 DPI = 1× scale, 144 DPI = 1.5× scale, 192 DPI = 2× scale
DISPLAY= wine reg add "HKCU\Control Panel\Desktop" /v LogPixels /t REG_DWORD /d 144 /f
```

---

## 102.8 Clipboard and IME

With the Wayland driver, clipboard integration uses `wl_data_device` — the
same protocol as native Wayland apps. No special setup is needed.

Input method (Fcitx5, IBus — Ch 79) works via `zwp_text_input_v3` for Wine
apps using the Wayland driver, whereas XWayland apps required
`GTK_IM_MODULE=fcitx` workarounds.

---

## 102.9 Lutris Configuration

```yaml
# In Lutris game settings → System options:
# Add to environment variables:
DISPLAY: ""
WAYLAND_DISPLAY: "wayland-1"
PROTON_ENABLE_WAYLAND: "1"   # if using Proton runner
```

Or set globally in Lutris → Preferences → System → Default environment variables.

---

## 102.10 Current Limitations (Wine 9.x)

| Feature | Status |
|---------|--------|
| Basic 2D rendering | ✅ Stable |
| OpenGL (via DXVK/Zink) | ✅ Works |
| Vulkan (DXVK/VKD3D) | ✅ Works |
| Direct3D presentation | ✅ Works |
| Multi-monitor | ⚠️ Partial |
| Clipboard | ✅ Works |
| DPI/fractional scaling | ✅ Works |
| Input method (IME) | ✅ Works |
| Drag and drop | ⚠️ Partial |
| System tray icons | ❌ Not supported |
| Window decorations | ⚠️ CSD only (no SSD) |
| Alt+Tab integration | ✅ Works (compositor handles it) |
| XWayland fallback | Available (`DISPLAY=:0 wine ...`) |

For apps that require X11-specific features (certain overlay tools, hardware
DRM checks), XWayland remains available as a fallback by setting `DISPLAY=:0`.

---

## 102.11 Debugging

```bash
# See what Wine is doing
WINEDEBUG=+wndproc,+winediag DISPLAY= wine app.exe 2>&1 | head -50

# Check if Wayland driver is active
WINEDEBUG=+winewayland DISPLAY= wine app.exe 2>&1 | grep wayland

# List active Wayland connections from Wine
ls /proc/$(pgrep wine)/fd | xargs -I{} readlink /proc/$(pgrep wine)/fd/{} 2>/dev/null \
  | grep wayland

# Fall back to XWayland for a specific app
DISPLAY=:0 wine problem-app.exe
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
