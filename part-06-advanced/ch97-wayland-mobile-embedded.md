# Chapter 97 — Wayland on Mobile and Embedded: Phosh, Sxmo, Weston Kiosk

## Overview

Wayland was designed with mobile and embedded in mind from the start. The same
protocol stack that drives a Hyprland desktop runs on PinePhones, Raspberry Pis,
car infotainment systems, and kiosks. This chapter covers the mobile Wayland
ecosystem and embedded compositor patterns.

---

## 97.1 The Mobile Wayland Stack

```
Hardware (ARM SoC — Snapdragon, Rockchip, Allwinner, BCM)
    ↓
Mesa (panfrost/freedreno/lima for open-source ARM GPU drivers)
    ↓
wlroots or libhandy/Mutter (compositor layer)
    ↓
Phosh / Sxmo / KDE Plasma Mobile / GNOME Mobile
    ↓
Adaptive GTK4/Qt6 apps + phone-specific apps
```

---

## 97.2 Phosh — GNOME Mobile Shell

Phosh (Phone Shell) is a Wayland compositor and shell for GNU/Linux phones.
It wraps Mutter (GNOME's compositor) with a phone-oriented UI: swipe-up home
gesture, notification shade, quick settings, lock screen, call UI.

**Primary platforms:**
- **Librem 5** (Purism) — the reference hardware
- **PinePhone / PinePhone Pro** (Pine64)
- **postmarketOS** on many Android devices

**Desktop environments built on Phosh:**
- Phosh itself (GTK4/libadwaita)
- GNOME Mobile initiative apps (`gnome-calls`, `chatty`, `gnome-contacts`)

### Installing Phosh (on postmarketOS)

```bash
# postmarketOS uses apk
apk add phosh phosh-config

# Or build from source (Arch ARM / Manjaro ARM):
paru -S phosh
```

### Phosh compositor internals

Phosh is a `phoc` (Phone Compositor) + `phosh` (Shell) split:

```
phoc      ← wlroots-based compositor (handles display, input)
  ↑
phosh     ← GTK4 shell layer (panels, lock screen, quick settings)
```

```bash
# Start phoc + phosh session
exec phoc -C /etc/phoc.ini phosh
```

`phoc.ini`:
```ini
[core]
xwayland=true

[output:DSI-1]
scale=2.0

[input:touchscreen]
output=DSI-1
```

### Phosh quick settings and notification shade

Phosh implements a swipe-down notification shade with quick settings tiles
(toggle WiFi, Bluetooth, Do Not Disturb, rotation lock). Tiles are implemented
as GLib settings plugins and follow the `org.gnome.Shell.Extensions.*` D-Bus
pattern.

### Adaptive app development for Phosh

Apps should use `libadwaita` responsive widgets:
```python
# Python / GTK4 adaptive app
import gi
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

class MyApp(Adw.Application):
    def do_activate(self):
        win = Adw.ApplicationWindow(application=self)
        # AdwNavigationView adapts to phone vs tablet layout
        nav = Adw.NavigationView()
        win.set_content(nav)
        win.present()
```

---

## 97.3 Sxmo — Minimalist Mobile UX on Sway

Sxmo (Simple X Mobile) uses Sway as its compositor and a collection of shell
scripts as the UI. It is the most hackable mobile Linux UX — everything is a
bash script.

**Hardware:** PinePhone, PinePhone Pro (primary targets)

### Sxmo architecture

```
sway (compositor)
  ↑
dmenu / bemenu (menus)
  ↑
Shell scripts (~/.config/sxmo/) — fully customizable
  ↑
Physical buttons (volume up/down/power = context actions)
```

### Installing Sxmo

```bash
# postmarketOS:
apk add sxmo-utils sxmo-sway

# Alpine Linux:
apk add sxmo-utils

# Arch ARM:
paru -S sxmo-utils-sway
```

### Sxmo button map (PinePhone)

```
Volume Up (short)    = context menu (depends on current app)
Volume Down (short)  = go back / switch
Power (short)        = toggle screen
Volume Up (hold)     = launch dmenu app launcher
Volume Down (hold)   = notifications
Power (hold)         = power menu
```

### Customizing Sxmo scripts

All UI is in `~/.config/sxmo/`:
```bash
# Custom app launcher
~/.config/sxmo/appmenu.sh

# Custom notifications handler
~/.config/sxmo/notifications_handler.sh

# Custom status bar (foot + cat from a FIFO)
~/.config/sxmo/sway.config  # extends base sway config
```

---

## 97.4 KDE Plasma Mobile

Plasma Mobile uses KWin as its compositor (same as desktop KDE, with mobile
input handling) and Kirigami for adaptive Qt/QML apps.

```bash
# Arch ARM:
paru -S plasma-mobile

# Start session:
exec dbus-run-session startplasma-wayland
```

Plasma Mobile and desktop Plasma share the same config system (`~/.config/kwinrc`)
and theming infrastructure (Kvantum, Plasma themes). Responsive layouts are
handled by Kirigami's page stack.

---

## 97.5 postmarketOS — Mobile Linux Distribution

postmarketOS is the primary distribution for running mainline Linux on Android
devices. It uses Alpine Linux (musl libc) as a base.

```bash
# Create a postmarketOS image for a supported device
pip install pmbootstrap

# Initialize
pmbootstrap init
# Choose: device (e.g., pine64-pinephone), UI (phosh/sxmo/plasma-mobile)

# Build and flash
pmbootstrap install
pmbootstrap flasher flash_rootfs
```

**Device support**: 250+ devices including many Qualcomm, MediaTek, and Rockchip
SoCs. Most use downstream kernels; mainline kernel support is a project goal.

---

## 97.6 Weston — Reference Compositor for Embedded

Weston is the reference Wayland compositor. Unlike Hyprland/Sway which target
desktop power users, Weston targets embedded/kiosk scenarios where the whole
compositor is a controlled environment.

### Kiosk mode — single-app compositor

`cage` is a dedicated kiosk compositor (simpler than Weston kiosk):

```bash
sudo pacman -S cage

# Run a single app fullscreen
cage -- chromium --kiosk https://dashboard.example.com
cage -- mpv --loop=inf /media/signage.mp4
cage -- kivy-app
```

### Weston kiosk shell

```bash
# /etc/weston.ini
[core]
shell=kiosk-shell.so
xwayland=false

[output]
name=HDMI-A-1
mode=1920x1080
transform=normal
scale=1

[kiosk]
```

```bash
# Launch Weston in kiosk mode
DISPLAY= weston --config=/etc/weston.ini &
WAYLAND_DISPLAY=wayland-1 chromium --ozone-platform=wayland --kiosk https://app.example.com
```

### Weston RDP backend (remote kiosk)

```bash
# /etc/weston.ini
[core]
backend=rdp-backend.so

[rdp]
address=0.0.0.0
port=3389
```

Allows remote desktop access to the Weston compositor over RDP — useful for
headless signage displays managed over the network.

---

## 97.7 Raspberry Pi Wayland Setup

The Raspberry Pi (4, 5, Zero 2W) runs Wayland well with the `v3d` Mesa driver:

```bash
# Raspberry Pi OS (bookworm) — Wayland is the default
# Check display server:
echo $XDG_SESSION_TYPE   # should be "wayland"

# Labwc is the default compositor on RPi OS Bookworm
# Config: ~/.config/labwc/

# For Wayfire (more visual effects):
sudo apt install wayfire
```

### Performance on RPi 4/5

```conf
# /boot/firmware/config.txt
# GPU memory allocation (min 128MB for Wayland)
gpu_mem=256

# Enable KMS (Direct Rendering Manager)
dtoverlay=vc4-kms-v3d
max_framebuffers=2
```

RPi 5 runs a 4K desktop at 60fps with Wayfire/Labwc. RPi 4 is comfortable
at 1080p60. Both support VA-API via `libcamera`/`mmal` pipelines.

---

## 97.8 Embedded Compositor with cage

For a product (signage display, POS terminal, car infotainment):

```bash
# Minimal cage + app setup
sudo pacman -S cage

# /etc/systemd/system/kiosk.service
[Unit]
Description=Kiosk Application
After=graphical.target
Wants=graphical.target

[Service]
Type=simple
User=kiosk
Environment=HOME=/home/kiosk
ExecStart=/usr/bin/cage -s -- /usr/bin/chromium \
  --ozone-platform=wayland \
  --kiosk \
  --no-first-run \
  --disable-infobars \
  --disable-session-crashed-bubble \
  https://kiosk.example.com
Restart=always
RestartSec=5

[Install]
WantedBy=graphical.target
```

cage's `-s` flag enables Seatd/logind seat management (no root required).

---

## 97.9 Input Method on Mobile

Mobile input requires:

1. **Virtual keyboard** — squeekboard (Phosh), wvkbd (Sxmo/wlroots)
2. **`zwp_input_method_v2`** — the Wayland protocol for OSKs (Phosh/squeekboard use this)
3. **`zwp_text_input_v3`** — apps announce text input focus to the compositor

wlroots compositors (Sway, Hyprland) partially implement `zwp_input_method_v2`
as of 2025 — squeekboard works on some wlroots compositors, wvkbd works on all.

---

## 97.10 Cross-Compiling for ARM

For building Wayland apps targeting mobile:

```bash
# Arch Linux cross-compile setup
paru -S aarch64-linux-gnu-gcc

# Meson cross-file for aarch64
cat > aarch64.ini << 'EOF'
[binaries]
c = 'aarch64-linux-gnu-gcc'
cpp = 'aarch64-linux-gnu-g++'
pkg-config = 'aarch64-linux-gnu-pkg-config'
strip = 'aarch64-linux-gnu-strip'

[host_machine]
system = 'linux'
cpu_family = 'aarch64'
cpu = 'cortex-a72'
endian = 'little'
EOF

meson setup build --cross-file aarch64.ini
ninja -C build
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
