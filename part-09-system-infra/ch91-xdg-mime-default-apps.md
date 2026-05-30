# Chapter 91 — XDG MIME Types and Default Applications

## Contents

- [Overview](#overview)
- [91.1 The MIME Type System](#911-the-mime-type-system)
- [91.2 mimeapps.list — Application Associations](#912-mimeappslist-application-associations)
  - [File locations (checked in order)](#file-locations-checked-in-order)
  - [Format](#format)
- [91.3 xdg-mime — Setting Defaults](#913-xdg-mime-setting-defaults)
  - [Setting defaults for an application's supported types](#setting-defaults-for-an-applications-supported-types)
- [91.4 xdg-open](#914-xdg-open)
  - [Debugging xdg-open](#debugging-xdg-open)
- [91.5 .desktop Files and App-IDs](#915-desktop-files-and-app-ids)
  - [Minimal .desktop file](#minimal-desktop-file)
  - [App-ID on Wayland](#app-id-on-wayland)
  - [Custom .desktop entries](#custom-desktop-entries)
- [91.6 update-desktop-database](#916-update-desktop-database)
- [91.7 Common Default App Configuration](#917-common-default-app-configuration)
  - [Minimal complete mimeapps.list](#minimal-complete-mimeappslist)
- [91.8 Portal Integration](#918-portal-integration)

---


## Overview

`xdg-open file.pdf` works by looking up MIME type → application association. On Wayland, the same mechanism drives portal file pickers, "open with" dialogs, and compositor app-id matching for window rules. Associations are stored in `~/.config/mimeapps.list` and managed with `xdg-mime`; `.desktop` files declare which MIME types each application handles. The `handlr` tool provides a friendlier CLI alternative to `xdg-mime` with faster lookup and batch-setting support. This chapter explains the whole chain from MIME detection through portal integration.

## Installation

**xdg-utils:** https://freedesktop.org/wiki/Software/xdg-utils  
**handlr:** https://github.com/nicohman/handlr

```bash
# Arch Linux
sudo pacman -S xdg-utils
paru -S handlr-regex      # AUR

# Nix (nixpkgs)
nix-env -iA nixpkgs.xdg-utils
nix-env -iA nixpkgs.handlr-regex
# home-manager: xdg.enable = true; (enables mimeapps.list management)
```

---

## 91.1 The MIME Type System

MIME types identify file content: `text/html`, `application/pdf`,
`image/png`, `audio/flac`. The shared MIME database at
`/usr/share/mime/` maps file extensions and magic bytes to MIME types.

```bash
# Query MIME type of a file
xdg-mime query filetype document.pdf
# → application/pdf

xdg-mime query filetype image.jpg
# → image/jpeg

# Use file(1) for a second opinion
file --mime-type document.pdf
```

---

## 91.2 mimeapps.list — Application Associations

`mimeapps.list` maps MIME types to `.desktop` file names.

### File locations (checked in order)

```
~/.config/mimeapps.list                           ← user overrides (primary)
~/.local/share/applications/mimeapps.list         ← legacy location
/usr/share/applications/mimeapps.list             ← system defaults
```

### Format

```ini
[Default Applications]
application/pdf=org.pwmt.zathura.desktop
text/html=firefox.desktop
image/jpeg=imv.desktop
image/png=imv.desktop
image/gif=imv.desktop
audio/flac=mpv.desktop
audio/mpeg=mpv.desktop
video/mp4=mpv.desktop
video/mkv=mpv.desktop
text/plain=nvim.desktop
inode/directory=yazi.desktop
x-scheme-handler/http=firefox.desktop
x-scheme-handler/https=firefox.desktop
x-scheme-handler/magnet=qbittorrent.desktop

[Added Associations]
image/jpeg=imv.desktop;gimp.desktop;
image/png=imv.desktop;gimp.desktop;
```

`[Default Applications]` sets the default. `[Added Associations]` adds apps
to the "open with" list without changing the default.

---

## 91.3 xdg-mime — Setting Defaults

```bash
# Query the current default for a MIME type
xdg-mime query default application/pdf
# → org.pwmt.zathura.desktop

# Set a new default
xdg-mime default zathura.desktop application/pdf
xdg-mime default firefox.desktop x-scheme-handler/http
xdg-mime default firefox.desktop x-scheme-handler/https
xdg-mime default mpv.desktop video/mp4
xdg-mime default mpv.desktop video/x-matroska

# Set default for multiple MIME types at once
xdg-mime default imv.desktop image/jpeg image/png image/gif image/webp image/tiff
```

### Setting defaults for an application's supported types

```bash
# Get all MIME types a desktop file supports
grep MimeType /usr/share/applications/firefox.desktop

# Set Firefox as default for all of them at once
mime_types=$(grep -oP '(?<=MimeType=)[^;]+' /usr/share/applications/firefox.desktop \
  | tr '\n' ' ')
# Then apply individually or edit mimeapps.list directly
```

---

## 91.4 xdg-open

`xdg-open` reads MIME associations and launches the default app:

```bash
xdg-open document.pdf      # opens in default PDF viewer
xdg-open https://archlinux.org  # opens in default browser
xdg-open .                 # opens current directory in file manager
xdg-open music.flac        # opens in default audio player
```

On Wayland with a portal-based environment, `xdg-open` delegates to the
portal's `xdg-desktop-portal` file handler for Flatpak apps. For native apps
it reads `mimeapps.list` directly.

### Debugging xdg-open

```bash
# Verbose output
XDG_UTILS_DEBUG_LEVEL=2 xdg-open document.pdf

# Manual lookup chain:
xdg-mime query default application/pdf
# → zathura.desktop
which zathura
```

---

## 91.5 .desktop Files and App-IDs

`.desktop` files define applications. They live in:
```
/usr/share/applications/     ← system-installed apps
~/.local/share/applications/ ← user-installed or custom entries
```

### Minimal .desktop file

```ini
[Desktop Entry]
Type=Application
Name=My Image Viewer
Exec=imv %F
Icon=imv
MimeType=image/jpeg;image/png;image/gif;image/webp;image/bmp;
Categories=Graphics;Viewer;
StartupWMClass=imv          # X11 WM_CLASS
StartupNotify=false
```

### App-ID on Wayland

On Wayland, the `app_id` is what compositors use for window rules and portal
matching — not `WM_CLASS`. The `app_id` is set by the application itself, and
for well-behaved apps it matches the `.desktop` file name (without extension).

```bash
# See app_ids of running windows (Hyprland)
hyprctl -j clients | jq -r '.[].class'

# See app_ids (Sway)
swaymsg -t get_tree | jq -r '.. | .app_id? // empty'
```

### Custom .desktop entries

If an app has the wrong app_id or you need a custom launcher:

```bash
# ~/.local/share/applications/custom-kitty-float.desktop
[Desktop Entry]
Type=Application
Name=Kitty (Float)
Exec=kitty --class kitty-float
Icon=kitty
NoDisplay=true    # hide from app launcher
```

Then set a window rule:
```conf
windowrulev2 = float, class:^(kitty-float)$
```

---

## 91.6 update-desktop-database

After adding or editing `.desktop` files, rebuild the application cache:

```bash
# Rebuild user application cache
update-desktop-database ~/.local/share/applications/

# Rebuild MIME cache
update-mime-database ~/.local/share/mime/

# Force-update the XDG open database
xdg-mime default my-app.desktop application/x-custom-type
```

---

## 91.7 Common Default App Configuration

### Minimal complete mimeapps.list

```ini
[Default Applications]
# Browser
x-scheme-handler/http=firefox.desktop
x-scheme-handler/https=firefox.desktop
x-scheme-handler/ftp=firefox.desktop
text/html=firefox.desktop
application/xhtml+xml=firefox.desktop

# PDF / Documents
application/pdf=org.pwmt.zathura.desktop
application/epub+zip=org.pwmt.zathura.desktop

# Images
image/jpeg=imv.desktop
image/png=imv.desktop
image/gif=imv.desktop
image/webp=imv.desktop
image/svg+xml=inkscape.desktop

# Video
video/mp4=mpv.desktop
video/x-matroska=mpv.desktop
video/webm=mpv.desktop
video/avi=mpv.desktop

# Audio
audio/flac=mpv.desktop
audio/mpeg=mpv.desktop
audio/ogg=mpv.desktop
audio/x-wav=mpv.desktop

# Text
text/plain=nvim.desktop
text/x-script.python=nvim.desktop
text/x-shellscript=nvim.desktop

# Archives
application/zip=org.gnome.FileRoller.desktop
application/x-tar=org.gnome.FileRoller.desktop

# Directories
inode/directory=yazi.desktop

# Email
x-scheme-handler/mailto=thunderbird.desktop

# Torrents
application/x-bittorrent=org.qbittorrent.qBittorrent.desktop
x-scheme-handler/magnet=org.qbittorrent.qBittorrent.desktop
```

---

## 91.8 Portal Integration

The xdg-desktop-portal's `OpenURI` portal uses the same MIME association chain.
When a Flatpak app calls `org.freedesktop.portal.OpenURI.OpenURI()`, the portal
reads `mimeapps.list` to determine the handler — so your associations apply
inside sandboxed apps too.

Test portal opening:

```bash
# Test that the portal finds the right handler for a URL
gdbus call --session \
  --dest org.freedesktop.portal.Desktop \
  --object-path /org/freedesktop/portal/desktop \
  --method org.freedesktop.portal.OpenURI.OpenURI \
  "" "https://archlinux.org" {}
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
