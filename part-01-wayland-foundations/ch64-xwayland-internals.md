# Chapter 64 — XWayland Internals: How X11 Apps Run on Wayland

## Overview
XWayland is a compatibility layer that lets X11 applications run on a Wayland
compositor. It's not a hack — it's a full X11 server that is itself a Wayland client.
Understanding it explains why some apps behave differently and how to fix them.

## Sections

### 64.1 What XWayland Is
- XWayland is an X11 server (`/usr/bin/Xwayland`) that runs as a Wayland client
- The compositor launches it and connects it to a `DISPLAY` socket (`:0`, `:1`, etc.)
- X11 apps connect to `$DISPLAY`, not `$WAYLAND_DISPLAY`
- XWayland translates X11 protocol → Wayland protocol for rendering

```
X11 app → DISPLAY=:0 → Xwayland → WAYLAND_DISPLAY=wayland-1 → Compositor
```

### 64.2 Rootless XWayland
- Modern XWayland runs in "rootless" mode: no visible root window
- Each X11 toplevel window becomes a Wayland `xdg_surface`
- The compositor manages them alongside native Wayland windows
- From the user's perspective: X11 apps look like any other window

### 64.3 How the Compositor Launches XWayland

**wlroots compositors (Sway, Hyprland):**
```c
// wlr_xwayland_create() in wlroots
// Spawns Xwayland, creates a display socket
// wlr_xwayland.new_surface event → maps X11 windows as wlr_surface
```

**Lazy launch (default in Hyprland):**
- XWayland not started until first X11 app runs
- Saves memory (~20 MB) on purely native setups
- `hyprland.conf`: `misc.disable_xwayland = true` to disable entirely

### 64.4 The WM_CLASS / app_id Mapping
X11 apps have `WM_CLASS` (resource + class), not `app_id`.
wlroots maps: `WM_CLASS` resource → `app_id` in foreign toplevel protocol.

```bash
# Find WM_CLASS of an X11 app
xprop WM_CLASS   # click on the window
# Output: WM_CLASS = "Navigator", "firefox"
# The first string is the instance, second is the class
# Hyprland window rules use: class:^(firefox)$
```

This matters for window rules — X11 apps need `class:` not `title:` in most cases.

### 64.5 Clipboard Between X11 and Wayland
- X11 uses XSELECTION (PRIMARY and CLIPBOARD)
- Wayland uses `wl_data_device` for clipboard
- XWayland bridges them via `xclip`/`xsel` compatibility
- `wl-clipboard` works for Wayland clipboard; X11 apps see it via XWayland bridge
- PRIMARY (middle-click paste): available via `wl-paste --primary`

### 64.6 DPI and Scaling in XWayland
- XWayland uses a single scale factor for all X11 apps
- Hyprland: sets XWayland DPI based on the first monitor's scale
- `xrdb -merge <<< 'Xft.dpi: 192'` — set DPI for X11 apps explicitly
- `GDK_SCALE=2` for GTK2/GTK3 X11 apps on HiDPI
- Fractional scaling: X11 apps may look slightly blurry on fractional displays

```conf
# Hyprland: force XWayland scale
xwayland {
    force_zero_scaling = true  # let apps handle their own scaling
}
```

### 64.7 Input in XWayland
- Keyboard: XWayland receives key events via `wl_seat`; translates to X11 key events
- Pointer: translated through the XWayland root window coordinate system
- Key remappers (kanata, keyd): work transparently since they operate below XWayland
- `setxkbmap` still works for XWayland keyboard layout (separate from Wayland layout)

### 64.8 Security Differences
X11 security model vs. Wayland in XWayland context:
- XWayland apps CAN still take screenshots of other X11 apps via `XGetImage`
- XWayland apps CAN keylog other X11 apps
- Wayland apps are isolated from both each other AND from X11 apps
- XWayland is a security perimeter: treat all X11 apps as less trusted

### 64.9 Identifying X11 vs Wayland Windows

```bash
# Check if a window is X11 or native Wayland
xprop -root  # lists X11 windows if XWayland is running

# Hyprland: check in client info
hyprctl clients | grep -A5 "xwayland"

# Look for the xwayland field in hyprctl clients -j output
hyprctl clients -j | jq '.[] | {title, xwayland}'
```

### 64.10 Disabling XWayland
For maximum security or minimal memory:
```conf
# Hyprland
misc {
    disable_xwayland = true
}
```
Consequences: Steam (partially), some games, older GTK2 apps, electron apps without Wayland flags, xterm, etc. won't work.

### 64.11 Troubleshooting X11 Apps on Wayland
| Problem | Cause | Fix |
|---------|-------|-----|
| App starts X11 instead of Wayland | Missing env vars | Set `QT_QPA_PLATFORM=wayland`, `GDK_BACKEND=wayland` |
| Blurry X11 app | DPI mismatch | Set `Xft.dpi` via `xrdb` |
| X11 app crashes | Missing X display | Ensure XWayland is running |
| Clipboard doesn't paste to X11 app | Bridge not active | Restart XWayland |
| Mouse offset in X11 app | Coordinate mapping | Hyprland: check `xwayland` section |
