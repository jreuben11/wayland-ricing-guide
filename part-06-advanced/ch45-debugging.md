# Chapter 45 — Debugging Wayland: WAYLAND_DEBUG, weston-info, wldbg

## Overview
When things break on Wayland, the debugging tools are different from X11.
This chapter covers the complete debugging toolkit.

## Sections

### 45.1 WAYLAND_DEBUG — Protocol Tracing
```bash
WAYLAND_DEBUG=1 kitty 2>&1 | grep wl_surface
```
- Logs all Wayland protocol messages to stderr
- Format: `[timestamp] ID -> interface.method(args)`
- `WAYLAND_DEBUG=client`: only client-side messages
- `WAYLAND_DEBUG=server`: only server-side (run compositor with this)
- Filter with grep: find specific interface traffic
- Performance cost: significant — only use for debugging

### 45.2 weston-info — Output and Capability Inspection
```bash
weston-info
```
- Lists all Wayland globals the compositor exposes
- Shows output configuration: resolution, refresh, transform, scale
- Shows supported protocols and their versions
- Useful for: "does my compositor support this protocol?"

### 45.3 wldbg — Interactive Protocol Debugger
- Intercepts between client and compositor
- Interactive: set breakpoints on specific messages
- Filter and inspect protocol traffic
- More developer-focused than WAYLAND_DEBUG

### 45.4 Compositor Logs
#### Hyprland
- `journalctl --user -u hyprland` or `~/.local/share/hyprland/hyprland.log`
- `hyprctl version`: check version and commit hash
- `hyprctl monitors`, `hyprctl clients`, `hyprctl workspaces`: state inspection

#### Sway
- `journalctl --user -u sway`
- `swaymsg -t get_tree`: full window tree as JSON
- `swaymsg -t get_outputs`: output state
- `swaymsg -t get_workspaces`

### 45.5 Environment Variable Debugging
```bash
# Check Wayland is active
echo $WAYLAND_DISPLAY              # should be wayland-1 or similar
echo $XDG_SESSION_TYPE            # should be "wayland"
echo $XDG_RUNTIME_DIR             # socket directory

# Force Wayland for specific apps
MOZ_ENABLE_WAYLAND=1 firefox
QT_QPA_PLATFORM=wayland slack
GDK_BACKEND=wayland gimp
```

### 45.6 XWayland Debugging
- `xlsclients`: list X11 clients on XWayland
- `xprop`: inspect X11 window properties
- `xrandr`: see XWayland virtual display
- `XWAYLAND_NO_GLAMOR=1`: software rendering for XWayland (debugging)

### 45.7 xdg-desktop-portal Debugging
- Portal mediates: screenshots, file chooser, screen sharing, settings
- `systemctl --user status xdg-desktop-portal`
- `systemctl --user status xdg-desktop-portal-hyprland`
- Debug: `XDG_DESKTOP_PORTAL_DEBUG=1 xdg-desktop-portal`
- Common issue: wrong portal implementation selected (check `XDG_CURRENT_DESKTOP`)

### 45.8 Common Issues and Fixes
| Symptom | Cause | Fix |
|---------|-------|-----|
| App starts on X11 not Wayland | Missing env vars | Set `QT_QPA_PLATFORM=wayland`, `GDK_BACKEND=wayland` |
| Blurry apps | Wrong scale | Check `GDK_SCALE`, `QT_SCALE_FACTOR` |
| No clipboard on app close | No daemon | Start `wl-paste --watch cliphist store` |
| Screenshot black/empty | Wrong portal | Install correct `xdg-desktop-portal-*` |
| Cursor disappears | Hardware cursor bug | `WLR_NO_HARDWARE_CURSORS=1` |
| App crashes on Wayland | Bad Wayland support | Try `WAYLAND_DEBUG=1` to find protocol error |
| Screen share doesn't work | Portal missing | Install `xdg-desktop-portal-wlr` or `-hyprland` |
| Keyboard layout wrong | XKB issue | Check `input.kb_layout` in compositor config |

### 45.9 GPU and Rendering Debugging
- `DRI_PRIME=1`: force discrete GPU
- `MESA_DEBUG=1`: Mesa OpenGL debugging
- `LIBGL_DEBUG=verbose`: verbose OpenGL errors
- `VK_LOADER_DEBUG=all`: Vulkan loader debugging
- `drm_info`: DRM device capability inspector
- `vulkaninfo`: Vulkan driver and device info

### 45.10 Quickshell-Specific Debugging
- `quickshell --log-rules "*.debug=true"`
- `quickshell --log-rules "Quickshell.Hyprland.debug=true"` (module-specific)
- QML syntax errors: shown in terminal output
- `console.log(JSON.stringify(obj))`: inspect QML objects
- `Qt.quit()` in unexpected places: look for unhandled signals
