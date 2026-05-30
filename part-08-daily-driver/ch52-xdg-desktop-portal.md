# Chapter 52 — xdg-desktop-portal: Screen Sharing, File Chooser, Settings

## Contents

- [Overview](#overview)
- [52.1 What xdg-desktop-portal Is](#521-what-xdg-desktop-portal-is)
- [52.2 The Backend Architecture](#522-the-backend-architecture)
- [52.3 Installation](#523-installation)
  - [Arch Linux](#arch-linux)
  - [Fedora / RHEL](#fedora-rhel)
  - [NixOS (declarative)](#nixos-declarative)
  - [Manual / Source Build (advanced)](#manual-source-build-advanced)
- [52.4 Portal Configuration File](#524-portal-configuration-file)
- [52.5 Portal Interfaces Reference](#525-portal-interfaces-reference)
- [52.6 The Settings Portal and Dark Mode](#526-the-settings-portal-and-dark-mode)
- [52.7 Screen Sharing Setup (WebRTC and OBS)](#527-screen-sharing-setup-webrtc-and-obs)
  - [Prerequisites](#prerequisites)
  - [Firefox Configuration](#firefox-configuration)
  - [Chromium / Chrome Configuration](#chromium-chrome-configuration)
  - [OBS Studio](#obs-studio)
  - [Testing Screen Share from CLI](#testing-screen-share-from-cli)
- [52.8 Session Startup and Service Ordering](#528-session-startup-and-service-ordering)
- [52.9 Flatpak and Portal Permissions](#529-flatpak-and-portal-permissions)
- [52.10 Writing a Custom Portal Backend](#5210-writing-a-custom-portal-backend)
- [52.11 Advanced: PipeWire Integration for ScreenCast](#5211-advanced-pipewire-integration-for-screencast)
- [52.12 Troubleshooting](#5212-troubleshooting)
  - [Step 1: Check Service Status](#step-1-check-service-status)
  - [Step 2: Verify Environment Variables](#step-2-verify-environment-variables)
  - [Step 3: Run Portal in Debug Mode](#step-3-run-portal-in-debug-mode)
  - [Step 4: Test Portal Interfaces Directly via D-Bus](#step-4-test-portal-interfaces-directly-via-d-bus)
  - [Step 5: Inspect portals.conf Routing](#step-5-inspect-portalsconf-routing)
  - [Common Failure Patterns](#common-failure-patterns)
  - [Hard Reset Procedure](#hard-reset-procedure)
- [Summary](#summary)

---


## Overview

xdg-desktop-portal (XDP) is the D-Bus middleware layer that sandboxed and native Wayland
applications use to request OS services: file picking, screenshots, screen sharing,
dark-mode preference, print dialogs, notifications, and more. Getting XDP configured
correctly is non-negotiable for a fully functional Wayland desktop. Without it, screen
sharing in browsers fails silently, GTK4 apps render in light mode regardless of your
theme, and Flatpak apps cannot access files outside their sandbox.

XDP was originally introduced to support Flatpak sandboxing, but its scope has grown
substantially. Modern non-sandboxed Wayland applications — Firefox, OBS Studio, pipewire
screen recorders — also route through portals because the portal interfaces provide a
clean, compositor-agnostic ABI for operations that require compositor cooperation (like
screencasting) or user confirmation dialogs (like file picking).

This chapter covers every portal interface, all major backends, the portals.conf routing
system, PipeWire integration, dark mode wiring, and a step-by-step troubleshooting
methodology. It is structured as a reference you will return to whenever portals behave
unexpectedly.

See Ch 53 for session startup ordering (portals must start after the compositor but before
applications that consume them), and Ch 56 for PipeWire configuration details that affect
the ScreenCast portal.

---

## 52.1 What xdg-desktop-portal Is

xdg-desktop-portal is a D-Bus service that exposes a set of well-defined interfaces under
the `org.freedesktop.portal.*` namespace. Each interface corresponds to a capability: file
choosing, screen casting, printing, and so on. Applications that need one of these
capabilities send a D-Bus method call to the portal broker rather than accessing the
underlying resource directly. The broker then delegates to a backend implementation suited
to the running desktop environment.

The portal model exists because Wayland compositors do not expose global input or display
state the way X11 did. There is no `XGrabPointer`, no `XCompositeGetOverlayWindow`, no
`XGetImage` across windows. Applications that need to capture the screen must ask the
compositor through a well-defined channel. The portal is that channel. Similarly, a
sandboxed Flatpak app running in a bubblewrap container has no access to `$HOME` directly;
the FileChooser portal mediates access and returns a FUSE-based path under
`/run/user/$UID/doc/` that the sandbox can read.

The broker process is `xdg-desktop-portal` itself. It is a generic process that parses
`portals.conf` and proxies requests to backend processes. The backend processes (e.g.
`xdg-desktop-portal-hyprland`) implement the `org.freedesktop.impl.portal.*` interfaces —
note the `impl` in the namespace — and do the actual work. This split means you can mix
backends: use the Hyprland backend for screencasting and the GTK backend for file chooser
dialogs.

A critical detail: `xdg-desktop-portal` is a user session service, not a system service.
It runs as your user via systemd user units. Its socket appears at
`/run/user/$UID/bus` (the user D-Bus socket). Applications discover it through the normal
D-Bus service activation mechanism: when an app calls
`org.freedesktop.portal.Desktop`, systemd activates `xdg-desktop-portal.service` if it
is not already running.

---

## 52.2 The Backend Architecture

The portal stack has three tiers. Understanding the tier boundaries prevents most
configuration mistakes.

```
Tier 1: Application
  Firefox, OBS, Flatpak app, any Wayland client
  ↓  D-Bus call to org.freedesktop.portal.*

Tier 2: Portal Broker (xdg-desktop-portal)
  Parses portals.conf to route each interface to the correct backend
  Manages tokens, handles app identity, enforces permissions
  ↓  D-Bus call to org.freedesktop.impl.portal.*

Tier 3: Backend Implementation
  xdg-desktop-portal-hyprland   — Hyprland compositor
  xdg-desktop-portal-wlr        — generic wlroots (Sway, river, labwc)
  xdg-desktop-portal-gnome      — GNOME Shell
  xdg-desktop-portal-kde        — KWin / Plasma
  xdg-desktop-portal-gtk        — any compositor, GTK dialogs
  ↓  Wayland protocol calls (ext-screencopy, xdg-activation, etc.)
     or direct GTK dialog windows

Tier 4: Compositor + PipeWire (for ScreenCast)
  The screencopy Wayland protocol captures frames
  PipeWire streams deliver them to the requesting application
```

Each backend registers which portal interfaces it implements in a `.portal` descriptor
file under `/usr/share/xdg-desktop-portal/portals/`. The broker reads these at startup
and builds a routing table. `portals.conf` then allows you to override the automatic
routing.

**Available backends and their coverage:**

| Backend | Compositor Target | ScreenCast | FileChooser | Settings | Screenshot | Camera |
|---------|-------------------|:----------:|:-----------:|:--------:|:----------:|:------:|
| `xdg-desktop-portal-hyprland` | Hyprland | Yes | No | No | Yes | No |
| `xdg-desktop-portal-wlr` | wlroots (Sway, river) | Yes | No | No | Yes | No |
| `xdg-desktop-portal-gnome` | GNOME Mutter | Yes | Yes | Yes | Yes | Yes |
| `xdg-desktop-portal-kde` | KWin | Yes | Yes | Yes | Yes | Yes |
| `xdg-desktop-portal-gtk` | Any | No | Yes | Yes | No | No |
| `xdg-desktop-portal-lxqt` | LXQt | No | Yes | No | No | No |

The practical consequence: on Hyprland or Sway you always need two backends. The
compositor-specific backend handles ScreenCast and Screenshot; `xdg-desktop-portal-gtk`
handles FileChooser and Settings. They run as separate D-Bus services simultaneously with
no conflict.

---

## 52.3 Installation

### Arch Linux

```bash
# Hyprland
sudo pacman -S xdg-desktop-portal xdg-desktop-portal-hyprland xdg-desktop-portal-gtk

# Sway / wlroots compositors
sudo pacman -S xdg-desktop-portal xdg-desktop-portal-wlr xdg-desktop-portal-gtk

# Verify the .portal descriptor files are present
ls /usr/share/xdg-desktop-portal/portals/
# hyprland.portal  gtk.portal  (and any others you installed)
```

If you previously had `xdg-desktop-portal-kde` or `xdg-desktop-portal-gnome` installed
from a prior DE, remove them — they will conflict with backend routing:

```bash
sudo pacman -Rns xdg-desktop-portal-gnome xdg-desktop-portal-kde
```

### Fedora / RHEL

```bash
# Hyprland (requires RPM Fusion or COPR)
sudo dnf install xdg-desktop-portal xdg-desktop-portal-gtk
# xdg-desktop-portal-hyprland may need the Solopasha COPR:
sudo dnf copr enable solopasha/hyprland
sudo dnf install xdg-desktop-portal-hyprland

# Sway
sudo dnf install xdg-desktop-portal xdg-desktop-portal-wlr xdg-desktop-portal-gtk
```

### NixOS (declarative)

```nix
# In configuration.nix or home-manager module

# For Hyprland
xdg.portal = {
  enable = true;
  extraPortals = with pkgs; [
    xdg-desktop-portal-hyprland
    xdg-desktop-portal-gtk
  ];
  config.hyprland.default = [ "hyprland" "gtk" ];
  # Route specific interfaces explicitly
  config.hyprland = {
    "org.freedesktop.impl.portal.FileChooser"  = [ "gtk" ];
    "org.freedesktop.impl.portal.Settings"     = [ "gtk" ];
    "org.freedesktop.impl.portal.ScreenCast"   = [ "hyprland" ];
    "org.freedesktop.impl.portal.Screenshot"   = [ "hyprland" ];
  };
};

# For Sway
xdg.portal = {
  enable = true;
  wlr.enable = true;
  extraPortals = with pkgs; [ xdg-desktop-portal-gtk ];
};
```

### Manual / Source Build (advanced)

```bash
# Dependencies: meson, ninja, glib, dbus, pipewire, libportal
git clone https://github.com/flatpak/xdg-desktop-portal
cd xdg-desktop-portal
meson setup builddir --prefix=/usr --buildtype=release
ninja -C builddir
sudo ninja -C builddir install
```

---

## 52.4 Portal Configuration File

The routing logic lives in `portals.conf`. The broker reads files from these locations in
precedence order (first match wins):

1. `~/.config/xdg-desktop-portal/portals.conf` — user override
2. `/etc/xdg/xdg-desktop-portal/portals.conf` — system override
3. `/usr/share/xdg-desktop-portal/$XDG_CURRENT_DESKTOP-portals.conf` — distro default per DE
4. `/usr/share/xdg-desktop-portal/portals.conf` — global fallback

The file format uses `.ini`-style syntax with a `[preferred]` section. Each key is a
portal interface name; each value is a semicolon-separated list of backend names to try in
order.

**Complete portals.conf for Hyprland:**

```ini
# ~/.config/xdg-desktop-portal/portals.conf

[preferred]
# Default: try hyprland first, fall back to gtk for anything it doesn't handle
default=hyprland;gtk

# Explicit per-interface routing (overrides default)
org.freedesktop.impl.portal.ScreenCast=hyprland
org.freedesktop.impl.portal.Screenshot=hyprland
org.freedesktop.impl.portal.FileChooser=gtk
org.freedesktop.impl.portal.Settings=gtk
org.freedesktop.impl.portal.AppChooser=gtk
org.freedesktop.impl.portal.Print=gtk
org.freedesktop.impl.portal.OpenURI=gtk
org.freedesktop.impl.portal.Inhibit=gtk
org.freedesktop.impl.portal.Notification=gtk
```

**Complete portals.conf for Sway:**

```ini
[preferred]
default=wlr;gtk

org.freedesktop.impl.portal.ScreenCast=wlr
org.freedesktop.impl.portal.Screenshot=wlr
org.freedesktop.impl.portal.FileChooser=gtk
org.freedesktop.impl.portal.Settings=gtk
org.freedesktop.impl.portal.AppChooser=gtk
```

The `XDG_CURRENT_DESKTOP` environment variable is the key autodetection signal. The broker
uses it to locate the distro-provided defaults and also passes it to backends so they know
which compositor is running. It must be set before the portal services start — ideally
in your compositor's environment propagation block:

```bash
# In Hyprland's exec-once or environment
exec-once = systemctl --user import-environment XDG_CURRENT_DESKTOP
env = XDG_CURRENT_DESKTOP,Hyprland

# In Sway config
exec systemctl --user import-environment XDG_CURRENT_DESKTOP WAYLAND_DISPLAY DISPLAY
exec dbus-update-activation-environment --systemd XDG_CURRENT_DESKTOP WAYLAND_DISPLAY
```

---

## 52.5 Portal Interfaces Reference

Every XDP interface corresponds to a real user-visible capability. The table below covers
all stable interfaces as of xdg-desktop-portal 1.18.

| Interface | D-Bus Name | What it does | Typical callers |
|-----------|-----------|--------------|-----------------|
| FileChooser | `org.freedesktop.portal.FileChooser` | Open/save file dialogs, returns FUSE paths | All apps with file pickers |
| ScreenCast | `org.freedesktop.portal.ScreenCast` | Screen recording, window/monitor sharing streams | OBS, browsers (WebRTC), Teams, Zoom |
| Screenshot | `org.freedesktop.portal.Screenshot` | One-shot screen captures | Flatpak screenshot tools |
| Camera | `org.freedesktop.portal.Camera` | Webcam access via PipeWire | Video call apps (sandboxed) |
| Settings | `org.freedesktop.portal.Settings` | Dark mode, accent color, font preferences | GTK4/libadwaita apps, Chromium, Firefox |
| OpenURI | `org.freedesktop.portal.OpenURI` | Open URLs/files with default handler | Everything that opens links |
| AppChooser | `org.freedesktop.portal.AppChooser` | "Open With" dialog | File managers, OpenURI fallback |
| Print | `org.freedesktop.portal.Print` | Print dialogs | GTK print-aware apps |
| Inhibit | `org.freedesktop.portal.Inhibit` | Prevent idle/sleep/logout | Video players, music apps |
| Notification | `org.freedesktop.portal.Notification` | Send desktop notifications | Flatpak apps without notify-send access |
| Account | `org.freedesktop.portal.Account` | Query username, real name, avatar | Some productivity apps |
| Secret | `org.freedesktop.portal.Secret` | Access to secret service / keyring | Password manager integration |
| Background | `org.freedesktop.portal.Background` | Request background execution | Apps that need to run without a window |
| Wallpaper | `org.freedesktop.portal.Wallpaper` | Set desktop wallpaper | Wallpaper apps |
| Location | `org.freedesktop.portal.Location` | GPS / geolocation | Navigation, weather apps |
| Email | `org.freedesktop.portal.Email` | Compose emails | "mailto:" handlers |
| Trash | `org.freedesktop.portal.Trash` | Move files to trash | File manager ops from sandboxed apps |
| NetworkMonitor | `org.freedesktop.portal.NetworkMonitor` | Query network connectivity | Apps that adapt to online/offline state |
| ProxyResolver | `org.freedesktop.portal.ProxyResolver` | Proxy config for sandboxed apps | Browsers, network tools |

For sandboxed apps, these interfaces are the only way to access restricted resources.
For native Wayland apps, they provide a compositor-agnostic API that works across GNOME,
KDE, Hyprland, and Sway without any app-level changes.

---

## 52.6 The Settings Portal and Dark Mode

The Settings portal is how GTK4, libadwaita, and Chromium-based applications detect
system appearance preferences. Without it, apps either default to light mode or fail to
follow your theme.

The portal exposes a `Read` method and a `SettingChanged` signal. Applications read the
`org.freedesktop.appearance` namespace, particularly the `color-scheme` key:

- `0` = no preference
- `1` = prefer dark
- `2` = prefer light

**Verify the current setting via D-Bus:**

```bash
gdbus call --session \
    --dest org.freedesktop.portal.Desktop \
    --object-path /org/freedesktop/portal/desktop \
    --method org.freedesktop.portal.Settings.Read \
    org.freedesktop.appearance color-scheme
```

Expected output for dark mode: `(<uint32 1>,)`

**Setting dark mode on non-GNOME desktops:**

The GTK portal backend reads from `gsettings`. You can write the preference even without
GNOME installed:

```bash
# Ensure dconf is installed (it provides the gsettings backend)
gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'
gsettings set org.gnome.desktop.interface gtk-theme 'Adwaita-dark'

# Verify it took effect
gsettings get org.gnome.desktop.interface color-scheme
```

**Forcing the value at portal level (portals.conf approach):**

Some minimal setups lack gsettings entirely. In that case, set the environment variable
that the GTK portal backend reads:

```bash
# In ~/.config/environment.d/gtk.conf or your shell init
export GTK_THEME=Adwaita:dark
```

**Monitoring Settings changes in real time:**

```bash
# Watch for portal settings signals (useful when debugging theming)
dbus-monitor --session "type=signal,interface=org.freedesktop.portal.Settings"
```

**Chromium / Electron dark mode via portal:**

Chromium requires explicit flags to use the portal Settings interface:

```bash
# ~/.config/electron-flags.conf  (applies to many Electron apps)
--enable-features=WebRTCPipeWireCapturer
--ozone-platform=wayland
--gtk-version=4

# For chromium specifically:
chromium --enable-features=UseOzonePlatform --ozone-platform=wayland \
         --enable-features=PreferSystemVisuals
```

---

## 52.7 Screen Sharing Setup (WebRTC and OBS)

Screen sharing on Wayland requires the ScreenCast portal backed by the PipeWire camera/
screencopy infrastructure. When a browser initiates a WebRTC screen share, the call
chain is:

```
Browser (Firefox/Chromium)
  → XDP ScreenCast.CreateSession
  → xdg-desktop-portal-hyprland (or -wlr)
  → Hyprland compositor (ext-screencopy-v1 or wlr-screencopy-unstable-v1)
  → PipeWire stream (video/x-raw, format=BGRA)
  → Browser WebRTC encoder
```

### Prerequisites

```bash
# Confirm PipeWire is running and wireplumber session manager is active
systemctl --user status pipewire pipewire-pulse wireplumber

# Confirm the pipewire-camera portal is available (for Camera interface)
pactl info | grep "Server Name"
```

### Firefox Configuration

Firefox ships with Wayland screen sharing support but requires environment variables:

```bash
# /etc/environment or ~/.config/environment.d/wayland.conf
MOZ_ENABLE_WAYLAND=1
MOZ_DBUS_REMOTE=1

# Optional: hardware video acceleration
MOZ_WEBRENDER=1
```

In `about:config`:
- `media.webrtc.hw.h264.enabled` → `true`
- `media.webrtc.platform.linux.screencast` → `true` (Firefox 116+)
- `widget.use-xdg-desktop-portal.file-picker` → `1`
- `widget.use-xdg-desktop-portal.mime-handler` → `1`

### Chromium / Chrome Configuration

```bash
# /etc/chromium/default or ~/.config/chromium-flags.conf
--enable-features=WebRTCPipeWireCapturer,UseOzonePlatform
--ozone-platform=wayland
--use-gl=egl
```

### OBS Studio

OBS uses the portal ScreenCast interface via the PipeWire source plugin. In OBS:

1. Add Source → PipeWire Video Capture
2. A portal dialog will appear to select window or monitor
3. The stream persists for the session (restore token is saved)

**OBS restore token for persistent streams:**

```bash
# OBS saves restore tokens at:
~/.config/obs-studio/plugin_config/linux-pipewire/

# To clear a stale session and force a new selection dialog:
rm -rf ~/.config/obs-studio/plugin_config/linux-pipewire/
```

### Testing Screen Share from CLI

```bash
# Test the ScreenCast portal directly using xdg-desktop-portal-test tool
# (part of xdg-desktop-portal dev package on some distros)
/usr/lib/xdg-desktop-portal --replace &

# Or use the portal-test binary if available:
xdg-desktop-portal-test screencast

# Simpler: use a Flatpak app that exercises the portal
flatpak install flathub org.gnome.Snapshot
flatpak run org.gnome.Snapshot  # Should show a portal dialog for camera access
```

---

## 52.8 Session Startup and Service Ordering

Portal services are systemd user units with `After=graphical-session.target`. They depend
on `dbus.socket` being active and `WAYLAND_DISPLAY` being set. Startup ordering problems
are a leading cause of portal failures on minimalist compositors.

**Correct startup sequence:**

```bash
# In your compositor startup (e.g., Hyprland's exec-once):

# 1. Propagate essential environment variables to systemd user session
exec-once = systemctl --user import-environment WAYLAND_DISPLAY XDG_CURRENT_DESKTOP
exec-once = dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP DISPLAY

# 2. Start portals explicitly (optional — they auto-start on first use, but explicit
#    startup ensures they're ready before apps that need them)
exec-once = systemctl --user start xdg-desktop-portal
exec-once = systemctl --user start xdg-desktop-portal-hyprland
```

**Sway equivalent:**

```bash
# ~/.config/sway/config
exec systemctl --user import-environment DISPLAY WAYLAND_DISPLAY SWAYSOCK
exec hash dbus-update-activation-environment 2>/dev/null && \
     dbus-update-activation-environment --systemd DISPLAY WAYLAND_DISPLAY SWAYSOCK
```

**Check that environment was propagated correctly:**

```bash
systemctl --user show-environment | grep -E 'WAYLAND|XDG_CURRENT|DISPLAY'
```

If `WAYLAND_DISPLAY` is missing from the systemd user environment, the ScreenCast backend
cannot connect to the compositor and will fail silently. This is the single most common
source of "screen share doesn't work" reports.

---

## 52.9 Flatpak and Portal Permissions

Flatpak apps request portal access via their AppStream/Flatpak manifest. At runtime,
`xdg-desktop-portal` enforces permissions using the `org.freedesktop.impl.portal.PermissionStore`
interface, backed by `~/.local/share/flatpak/db/`.

**Query and manage Flatpak portal permissions:**

```bash
# List all stored portal permissions
flatpak permission-list

# Show permissions for a specific app
flatpak permission-show com.obsproject.Studio

# Check what portals a Flatpak app declares it needs
flatpak info --show-permissions com.obsproject.Studio

# Reset portal permissions for an app (will re-ask on next launch)
flatpak permission-reset com.obsproject.Studio

# Grant filesystem access (circumvents FileChooser portal for that path)
flatpak override --user --filesystem=home com.example.App
flatpak override --user --filesystem=/mnt/data:ro com.example.App

# List per-app overrides
flatpak override --user --show com.example.App
```

**The document portal and FUSE mount:**

When a Flatpak app opens a file through the FileChooser portal, the broker creates a
FUSE-mounted entry under `/run/user/$UID/doc/$HEXID/filename`. This gives the sandbox
read (or read-write) access to exactly one file without broad filesystem access.

```bash
# Inspect current document portal mounts
ls /run/user/$UID/doc/

# The portal DB is here:
ls ~/.local/share/flatpak/db/
# Files: documents  notifications  permissions  screenshot  screencast
```

---

## 52.10 Writing a Custom Portal Backend

You may want a custom backend for a proprietary screen capture API, a custom file picker,
or a headless test environment. A backend is a D-Bus service that implements
`org.freedesktop.impl.portal.*` interfaces.

**Step 1: Write the `.portal` descriptor file**

```ini
# /usr/share/xdg-desktop-portal/portals/myportal.portal

[portal]
DBusName=org.example.MyPortal
Interfaces=org.freedesktop.impl.portal.FileChooser;org.freedesktop.impl.portal.Screenshot;
UseIn=mycustomde;
```

`UseIn` controls which `XDG_CURRENT_DESKTOP` values activate this backend automatically.

**Step 2: Implement the D-Bus service (Python example using dbus-python)**

```python
#!/usr/bin/env python3
# myportal.py — minimal FileChooser backend skeleton

import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

class FileChooserPortal(dbus.service.Object):
    def __init__(self, bus):
        bus_name = dbus.service.BusName("org.example.MyPortal", bus)
        dbus.service.Object.__init__(
            self, bus_name, "/org/freedesktop/portal/desktop"
        )

    @dbus.service.method(
        "org.freedesktop.impl.portal.FileChooser",
        in_signature="osssa{sv}",
        out_signature="ua{sv}",
        async_callbacks=("return_cb", "error_cb"),
    )
    def OpenFile(self, handle, app_id, parent_window, title, options,
                 return_cb, error_cb):
        # Show your custom file picker here
        # Call return_cb(0, {"uris": [dbus.Array(["file:///chosen/file"])]})
        return_cb(dbus.UInt32(0), {
            "uris": dbus.Array(["file:///tmp/example.txt"], signature="s")
        })

session_bus = dbus.SessionBus()
portal = FileChooserPortal(session_bus)
loop = GLib.MainLoop()
loop.run()
```

**Step 3: Install as a systemd user service**

```ini
# ~/.config/systemd/user/myportal.service
[Unit]
Description=My Custom Portal Backend
After=dbus.socket

[Service]
Type=dbus
BusName=org.example.MyPortal
ExecStart=/usr/local/lib/myportal/myportal.py

[Install]
WantedBy=xdg-desktop-portal.service
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now myportal.service
```

---

## 52.11 Advanced: PipeWire Integration for ScreenCast

The ScreenCast portal creates PipeWire streams that expose screen content as video
sources. Understanding the PipeWire side helps debug capture failures.

**Monitor active PipeWire streams during a screen share:**

```bash
# List all nodes — look for xdpw-stream entries
pw-cli list-objects | grep -A5 "xdpw"

# Or use pw-dump for JSON output
pw-dump | python3 -m json.tool | grep -B2 -A10 "xdpw"

# Use pw-top for live stream monitoring
pw-top
```

**Inspect stream parameters:**

```bash
# pw-cli info gives detailed node properties
pw-cli info $(pw-cli list-objects | grep -B5 "xdpw-stream" | grep "id=" | head -1 | grep -o '[0-9]*')
```

**PipeWire configuration for screen sharing quality:**

```conf
# ~/.config/pipewire/pipewire.conf.d/screencast.conf
context.properties = {
    # Increase quantum for lower screen share latency (at cost of audio latency)
    default.clock.quantum = 1024
    default.clock.min-quantum = 32
    default.clock.max-quantum = 8192
}
```

**DMABUF hardware acceleration for screen capture:**

When the screencopy protocol returns DMABUF handles instead of shared memory, capture is
essentially zero-copy. Check if DMABUF screencopy is active:

```bash
# xdg-desktop-portal-hyprland logs to stderr — check systemd journal
journalctl --user -u xdg-desktop-portal-hyprland -f

# Look for: "Using DMA-BUF" vs "Falling back to SHM"
```

---

## 52.12 Troubleshooting

Portal issues typically manifest as silent failures: screen share produces a black window,
file dialogs never appear, or dark mode doesn't apply. Methodical diagnosis starting with
service state catches most issues.

### Step 1: Check Service Status

```bash
# All portal-related services
systemctl --user status xdg-desktop-portal.service
systemctl --user status xdg-desktop-portal-hyprland.service
systemctl --user status xdg-desktop-portal-gtk.service

# If a service failed, inspect the log
journalctl --user -u xdg-desktop-portal -n 50
journalctl --user -u xdg-desktop-portal-hyprland -n 50
```

### Step 2: Verify Environment Variables

```bash
# These must be in the systemd user environment
systemctl --user show-environment | grep -E 'WAYLAND_DISPLAY|XDG_CURRENT_DESKTOP|DISPLAY|DBUS'

# If WAYLAND_DISPLAY is missing, propagate it:
systemctl --user import-environment WAYLAND_DISPLAY XDG_CURRENT_DESKTOP
# Then restart portals:
systemctl --user restart xdg-desktop-portal xdg-desktop-portal-hyprland
```

### Step 3: Run Portal in Debug Mode

```bash
# Kill existing portal broker and run manually with debug output
systemctl --user stop xdg-desktop-portal
G_MESSAGES_DEBUG=all XDG_DESKTOP_PORTAL_DEBUG=1 \
    /usr/lib/xdg-desktop-portal 2>&1 | tee /tmp/portal-debug.log

# In another terminal, trigger the failing operation, then examine:
grep -i "error\|warn\|fail\|backend" /tmp/portal-debug.log
```

### Step 4: Test Portal Interfaces Directly via D-Bus

```bash
# Test FileChooser portal
gdbus call --session \
    --dest org.freedesktop.portal.Desktop \
    --object-path /org/freedesktop/portal/desktop \
    --method org.freedesktop.portal.FileChooser.OpenFile \
    "" "test-app" "" "Open File" \
    "{'handle_token': <'test1'>}"

# Test Settings portal (dark mode)
gdbus call --session \
    --dest org.freedesktop.portal.Desktop \
    --object-path /org/freedesktop/portal/desktop \
    --method org.freedesktop.portal.Settings.Read \
    org.freedesktop.appearance color-scheme

# Check which backends are registered
gdbus introspect --session \
    --dest org.freedesktop.portal.Desktop \
    --object-path /org/freedesktop/portal/desktop \
    | grep -i interface
```

### Step 5: Inspect portals.conf Routing

```bash
# Which portals.conf file is actually being read?
find /usr/share/xdg-desktop-portal/ -name "*.conf" -o -name "*.portal" | sort
cat /usr/share/xdg-desktop-portal/portals.conf 2>/dev/null || echo "No global fallback"
cat /usr/share/xdg-desktop-portal/${XDG_CURRENT_DESKTOP,,}-portals.conf 2>/dev/null
cat ~/.config/xdg-desktop-portal/portals.conf 2>/dev/null

# What .portal files are installed?
cat /usr/share/xdg-desktop-portal/portals/hyprland.portal
cat /usr/share/xdg-desktop-portal/portals/gtk.portal
```

### Common Failure Patterns

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Screen share black / empty | Wrong backend or `WAYLAND_DISPLAY` not set | Check `XDG_CURRENT_DESKTOP`; run `systemctl --user import-environment WAYLAND_DISPLAY` |
| File chooser dialog never appears | Missing `-gtk` backend | Install `xdg-desktop-portal-gtk` |
| GTK4 apps always render light | Settings portal not using gtk backend | Set `org.freedesktop.impl.portal.Settings=gtk` in `portals.conf` |
| Screen share works once, then black | PipeWire session expired | Restart backend: `systemctl --user restart xdg-desktop-portal-hyprland` |
| Firefox WebRTC fails | `MOZ_ENABLE_WAYLAND=1` not in environment | Add to `/etc/environment` or `~/.config/environment.d/` |
| OBS PipeWire source crashes | Stale restore token | Delete `~/.config/obs-studio/plugin_config/linux-pipewire/` |
| Portal dialog appears on wrong monitor | `HYPRLAND_INSTANCE_SIGNATURE` missing | Export it: `systemctl --user import-environment HYPRLAND_INSTANCE_SIGNATURE` |
| FileChooser returns sandbox path | Expected for Flatpak — FUSE mount at `/run/user/$UID/doc/` | No action needed; this is correct behavior |
| `xdg-desktop-portal-hyprland` not found | COPR / AUR package not installed | Check package name for your distro |
| Multiple backends respond | Stale conflicting backend service running | `systemctl --user stop xdg-desktop-portal-gnome` etc. |

### Hard Reset Procedure

When portals are in an unrecoverable state (e.g., after a compositor crash or upgrade):

```bash
# Stop all portal services
systemctl --user stop xdg-desktop-portal \
                      xdg-desktop-portal-hyprland \
                      xdg-desktop-portal-gtk \
                      xdg-desktop-portal-wlr 2>/dev/null

# Clear any leftover D-Bus services
rm -f /tmp/xdg-desktop-portal* /run/user/$UID/.xdg-desktop-portal*

# Re-propagate environment
systemctl --user import-environment WAYLAND_DISPLAY XDG_CURRENT_DESKTOP DISPLAY
dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP DISPLAY

# Restart
systemctl --user start xdg-desktop-portal
systemctl --user start xdg-desktop-portal-hyprland

# Confirm both are running
systemctl --user is-active xdg-desktop-portal xdg-desktop-portal-hyprland
```

---

## Summary

xdg-desktop-portal is a mandatory component of any functional Wayland desktop. The key
configuration points are: install the compositor-specific backend plus `xdg-desktop-portal-gtk`
for dialogs and settings; write `~/.config/xdg-desktop-portal/portals.conf` to route each
interface to the correct backend; export `XDG_CURRENT_DESKTOP` and `WAYLAND_DISPLAY` into
the systemd user environment before portals start; and ensure PipeWire is running for
ScreenCast and Camera interfaces.

See Ch 53 for session startup ordering details, Ch 56 for PipeWire configuration, and
Ch 53 for Hyprland environment variable management.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
