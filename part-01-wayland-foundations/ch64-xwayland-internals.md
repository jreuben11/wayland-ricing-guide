# Chapter 64 — XWayland Internals: How X11 Apps Run on Wayland

> **Related chapters:** Ch 53 (Session startup and environment variables), Ch 55 (Compositor configuration),
> Ch 58 (HiDPI and fractional scaling), Ch 71 (Clipboard management), Ch 79 (Window rules deep dive),
> Ch 82 (Security model and sandboxing).

## Overview

XWayland is a compatibility layer that allows X11 applications to run inside a Wayland session without
modification. It is not a shim or a hack bolted on as an afterthought — it is a full, functional X11
server that itself runs as a Wayland client. Understanding XWayland's architecture is essential for any
serious Wayland setup because it explains a wide range of behaviors that confuse newcomers: why some
apps look blurry on HiDPI displays, why clipboard paste sometimes fails, why window rules need a
different syntax for legacy apps, and why X11 programs remain a security liability even in an otherwise
Wayland-native session.

This chapter covers the full lifecycle of an X11 application in a Wayland session: how XWayland is
started by the compositor, how protocol translation works at a technical level, how input and clipboard
are bridged, and the concrete steps you can take to fix the most common problems. By the end you will
have a clear mental model of where XWayland sits in the display stack and the tools to debug it when
something goes wrong.

---

## 64.1 What XWayland Is

XWayland ships as the binary `/usr/bin/Xwayland` (or `/usr/lib/xorg/Xwayland` on some distributions)
and is maintained as part of the X.Org project, though it depends on a Wayland compositor to run. When
launched it creates a standard X11 UNIX socket — `/tmp/.X11-unix/X0`, `/tmp/.X11-unix/X1`, and so on —
and listens for X11 clients exactly as a traditional X server would. Applications connect to the socket
by reading `$DISPLAY`, which remains set to `:0` or `:1` for the duration of the session.

What makes XWayland different from a traditional X server is that it renders entirely through Wayland.
Instead of driving a GPU directly, it allocates DMA-BUF or SHM buffers and presents them to the
Wayland compositor via `wl_surface` and related protocols. The compositor treats XWayland exactly the
same as any other Wayland client; from the GPU's point of view there is no X11 at all. The translation
layer lives inside the XWayland process itself.

```
X11 app  ─DISPLAY=:0──►  Xwayland process  ─WAYLAND_DISPLAY=wayland-1──►  Compositor
          (X11 protocol)     (translates)         (Wayland protocol)         (renders)
```

This architecture has important consequences. First, there is only one X server per Wayland session
(not one per application), so all X11 apps share the same X11 security domain. Second, XWayland's
performance is constrained by both the X11 protocol overhead and the Wayland round-trip, which is why
some legacy apps feel slightly less responsive than their native Wayland equivalents. Third, anything
that manipulates the X11 server state — `xrandr`, `xrdb`, `setxkbmap` — affects all X11 applications
in the session, not just one.

To verify XWayland is running and see which display it is using:

```bash
# Check if Xwayland is in the process list
pgrep -a Xwayland

# Example output:
# 12345 /usr/bin/Xwayland :0 -rootless -terminate -core ...

# Verify the socket exists
ls -la /tmp/.X11-unix/

# Confirm DISPLAY is exported in your session
echo $DISPLAY        # should print :0 or similar
echo $WAYLAND_DISPLAY  # should print wayland-1 or wayland-0
```

---

## 64.2 Rootless XWayland

Early versions of XWayland used a full-screen root window that covered the entire display, which meant
the compositor had to composite X11 output as a single opaque layer. Modern XWayland (Xwayland 21.1+)
runs in **rootless** mode, which is the default in every major compositor. In rootless mode there is no
visible root window. Each X11 toplevel window is individually mapped as a Wayland `xdg_surface` (via
the `xdg-shell` protocol), and each is composited independently by the Wayland compositor.

The practical consequence is that X11 windows integrate visually with native Wayland windows. They can
be tiled, floated, moved, and stacked interchangeably. The compositor applies its own decorations, blur,
shadows, and animations to them just as it would to a native client. From the user's perspective, an
X11 window and a Wayland window are indistinguishable unless you explicitly query the compositor.

Rootless mode also enables transparency and compositing effects for X11 apps. XWayland exposes the
COMPOSITE extension and sends per-pixel alpha channels to the compositor via ARGB buffers. This is why
`xterm` with a transparent background works correctly under a modern compositor — the alpha is
preserved through the entire pipeline.

There is one edge case to know: X11 **override-redirect** windows (tooltips, menus, some popup
windows) bypass the normal `xdg_surface` path and are mapped as `wl_subsurface` objects anchored to
their parent. This sometimes causes positioning bugs, especially under fractional scaling. If you see a
tooltip appearing in the wrong location, override-redirect handling is usually the culprit.

```bash
# Verify rootless mode is active (look for -rootless flag in Xwayland args)
pgrep -a Xwayland | grep rootless

# List all override-redirect windows (mapped without WM control)
xwininfo -root -tree | grep -i "override"

# Use xprop to check a specific window's attributes
xprop -id $(xdotool selectwindow) | grep OVERRIDE
```

---

## 64.3 How the Compositor Launches XWayland

The compositor is responsible for spawning and managing the XWayland process. Different compositors
do this in slightly different ways, but the underlying mechanism in wlroots-based compositors is
`wlr_xwayland_create()`, which forks the Xwayland binary, sets up a socket pair, and waits for the
`new_surface` event that fires when an X11 app creates a toplevel window.

**wlroots compositors (Sway, Hyprland, wayfire):**

Sway and Hyprland both use wlroots' built-in XWayland support. Hyprland adds a "lazy launch" option:
XWayland is not started at all until the first X11 application tries to connect. This saves roughly
15–25 MB of RAM and avoids running an X server if your setup is purely Wayland-native.

```bash
# Hyprland configuration (~/.config/hypr/hyprland.conf)

# Option 1: lazy XWayland (default since Hyprland 0.27)
misc {
    # XWayland starts on first X11 app, not at compositor launch
    # This is the default — no config needed to enable it
}

# Option 2: disable XWayland entirely (maximum security, breaks X11 apps)
misc {
    disable_xwayland = true
}

# Option 3: force XWayland to start immediately at compositor launch
# (useful to avoid the ~500ms startup delay on the first X11 app)
# Add to hyprland.conf exec-once:
exec-once = Xwayland :0 -rootless &
```

**KWin (KDE Plasma Wayland):**

KWin manages XWayland through a separate `kwin_wayland_wrapper` process. It does not use wlroots.
The configuration is handled in KDE's system settings under Display & Monitor > Compositor.

```bash
# Check KWin XWayland status
qdbus org.kde.KWin /KWin org.kde.KWin.supportInformation | grep -i xwayland

# Restart KWin XWayland without logging out
qdbus org.kde.KWin /KWin org.kde.KWin.replace
```

**GNOME Mutter:**

GNOME Mutter launches XWayland on demand and can terminate it when no X11 clients remain
(the `--terminate` flag). GNOME 45+ supports XWayland on-demand by default, reducing idle
memory usage on GNOME Wayland sessions that never open an X11 app.

```bash
# Check GNOME XWayland status
gsettings get org.gnome.mutter experimental-features
# Look for 'xwayland-grab-keyboard-focus' or similar

# On GNOME, force disable XWayland via gsettings (GNOME 43+)
gsettings set org.gnome.mutter experimental-features "['no-xwayland']"
# Note: this is unofficial and may break things; prefer KWin for fine-grained control
```

---

## 64.4 The WM_CLASS / app_id Mapping

One of the most practically important XWayland details for ricing is how X11 window identities map
to Wayland concepts. Native Wayland apps identify themselves with an `app_id` string, typically
matching their `.desktop` filename (e.g., `org.mozilla.firefox`). X11 apps use a different system:
`WM_CLASS`, which is a pair of strings — the **instance name** (resource) and the **class name**.

wlroots compositors map the `WM_CLASS` resource field to the Wayland foreign-toplevel `app_id`. This
means that window rules targeting X11 apps must use the `WM_CLASS` values, not a reverse-DNS
app_id, and in Hyprland the correct filter keyword is `class:` not `app_id:`.

```bash
# Find WM_CLASS for any X11 window (click the window when prompted)
xprop WM_CLASS
# Example output: WM_CLASS = "Navigator", "firefox"
# "Navigator" is the instance (first), "firefox" is the class (second)

# Alternative: use xdotool to get WM_CLASS without clicking
xdotool selectwindow getwindowname
xprop -id $(xdotool selectwindow) WM_CLASS

# Alternative: use wmctrl to list all windows with their classes
wmctrl -lx

# Hyprland: verify what app_id/class Hyprland sees
hyprctl clients | grep -E "class|title|xwayland"

# Hyprland clients in JSON (most reliable)
hyprctl clients -j | jq '.[] | {title, class, xwayland}'
```

Window rules in Hyprland for X11 apps:

```conf
# ~/.config/hypr/hyprland.conf

# Float a specific X11 app by class (WM_CLASS second field)
windowrulev2 = float, class:^(matplotlib)$

# Float by instance (WM_CLASS first field)
windowrulev2 = float, class:^(Navigator)$

# Pin picture-in-picture Firefox window (X11 instance)
windowrulev2 = pin, class:^(firefox)$, title:^(Picture-in-Picture)$

# Force X11 Steam to a specific workspace
windowrulev2 = workspace 9, class:^(Steam)$
```

Sway uses a similar syntax with `app_id` for Wayland apps and `class` for X11:

```conf
# ~/.config/sway/config

# X11 app rule (uses class)
for_window [class="Steam"] move to workspace 9

# Native Wayland app rule (uses app_id)
for_window [app_id="org.mozilla.firefox"] move to workspace 2
```

---

## 64.5 Clipboard Between X11 and Wayland

Clipboard interoperability is one of the most frequently broken things in mixed Wayland/X11 setups.
The root cause is that X11 and Wayland use fundamentally different clipboard models. X11 has two
selection buffers — `CLIPBOARD` (Ctrl+C / Ctrl+V) and `PRIMARY` (select-to-copy, middle-click paste)
— implemented as X properties with an owner-based protocol. Wayland uses the `wl_data_device` protocol,
which has a similar owner-based model but is completely incompatible at the wire level.

XWayland bridges these by running a built-in clipboard manager that watches both the X11 CLIPBOARD
selection and the Wayland data device, copying content between them whenever ownership changes. In
practice this works well for plain text but can fail for large binary clipboard contents or
complex MIME types.

```bash
# Test clipboard bridge: copy from a Wayland app, paste into an X11 app
# 1. Copy text in a native Wayland terminal (e.g., foot, alacritty in Wayland mode)
# 2. Paste in an X11 app (e.g., xterm)
# If it fails, the XWayland clipboard bridge is broken

# Check Wayland clipboard content
wl-paste

# Check X11 clipboard content (requires xclip or xsel)
xclip -selection clipboard -o
xsel --clipboard --output

# Check X11 PRIMARY selection
xclip -selection primary -o
xsel --primary --output

# Manually sync Wayland clipboard → X11 CLIPBOARD
wl-paste | xclip -selection clipboard

# Sync X11 clipboard → Wayland
xclip -selection clipboard -o | wl-copy

# PRIMARY selection via wl-clipboard
wl-paste --primary
wl-copy --primary < somefile.txt
```

When the automatic bridge fails (a known issue in some compositor versions), you can run a dedicated
clipboard synchronizer:

```bash
# Install and run xclip-wl-sync (or cliphist with X11 bridge)
# Option 1: autocutsel — syncs X11 CLIPBOARD and PRIMARY
autocutsel -fork &
autocutsel -selection PRIMARY -fork &

# Option 2: clipnotify + wl-clipboard polling (lightweight)
# Add to your session startup:
exec-once = sh -c 'while clipnotify; do xclip -o | wl-copy; done'

# Option 3: cliphist with wl-paste piped back to X11
exec-once = wl-paste --watch cliphist store
exec-once = wl-paste --watch xclip -selection clipboard
```

See Ch 71 for a complete treatment of clipboard managers including `cliphist`, `copyq`, and `rofi`
clipboard integration.

---

## 64.6 DPI and Scaling in XWayland

HiDPI scaling under XWayland is arguably its weakest point. The core problem is that X11 has no
concept of per-output scaling — an X11 application gets a single logical screen and must handle
DPI itself. XWayland bridges this by presenting a virtual screen to X11 clients whose pixel
dimensions are scaled by the compositor's scale factor. However, this only works correctly for
integer scales (2×, 3×). Fractional scales (1.25×, 1.5×, 1.75×) require workarounds.

**How XWayland applies scaling:**

```
Physical display: 3840×2160 at scale 2
XWayland presents: 1920×1080 virtual screen (pixels halved)
X11 app renders: 1920×1080 pixels
XWayland scales up: 2× before handing to compositor
```

For fractional scaling (e.g., 1.5×), the compositor rounds or uses nearest-integer, and XWayland
content may appear slightly blurry because the pixel dimensions don't divide evenly.

```bash
# Check current XWayland screen dimensions
DISPLAY=:0 xrandr --query

# Force a specific DPI for all X11 apps via Xresources
xrdb -merge - <<EOF
Xft.dpi: 192
Xft.antialias: true
Xft.hinting: true
Xft.hintstyle: hintfull
Xft.rgba: rgb
EOF

# Or write to ~/.Xresources and load at session start
cat >> ~/.Xresources << 'EOF'
Xft.dpi: 192
Xft.antialias: true
Xft.hinting: true
Xft.hintstyle: hintfull
EOF
# Load in session startup (add to ~/.profile or hyprland exec-once):
exec-once = xrdb -merge ~/.Xresources
```

**Hyprland XWayland scaling configuration:**

```conf
# ~/.config/hypr/hyprland.conf

xwayland {
    # Set to true on fractional-scale setups to avoid blur:
    # tells X11 apps to render at 1:1 scale, then the compositor
    # handles the upscaling at the display level
    force_zero_scaling = true
}

# For HiDPI with force_zero_scaling, also set:
exec-once = xrdb -merge - <<< "Xft.dpi: 192"
```

**Per-toolkit environment variables for X11 apps:**

| Variable | Toolkit | Effect |
|---|---|---|
| `GDK_SCALE=2` | GTK2/GTK3 | Integer scale factor |
| `GDK_DPI_SCALE=1.5` | GTK3/4 | DPI multiplier (fractional OK) |
| `QT_SCALE_FACTOR=2` | Qt5/Qt6 | Integer or fractional scale |
| `QT_AUTO_SCREEN_SCALE_FACTOR=1` | Qt5/Qt6 | Use screen DPI automatically |
| `XCURSOR_SIZE=32` | libXcursor | Cursor size in pixels |
| `Xft.dpi: 192` | Xft (fonts) | Font DPI for X11 Xft rendering |

```bash
# Set environment variables globally in session startup
# Add to ~/.config/hypr/hyprland.conf or your session .profile:
export GDK_SCALE=2
export GDK_DPI_SCALE=1
export QT_AUTO_SCREEN_SCALE_FACTOR=1
export XCURSOR_SIZE=32
export XCURSOR_THEME=Adwaita
```

See Ch 58 for a complete guide to HiDPI and fractional scaling across both Wayland-native and
X11-via-XWayland applications.

---

## 64.7 Input in XWayland

Input handling in XWayland is a multi-layer translation process. Physical input events flow from
the kernel evdev interface through the compositor's input handling (libinput), then through the
Wayland seat protocol to XWayland, which translates them into X11 input events that legacy apps
understand.

**Keyboard events:**

XWayland receives keyboard events via `wl_keyboard` on the Wayland seat. It translates keycodes
using XKB (X Keyboard Extension), maintaining its own keymap that is separate from — but usually
synchronized with — the Wayland compositor's keymap. This means `setxkbmap` can change the
keyboard layout for X11 apps without affecting native Wayland apps.

```bash
# Check current X11 keyboard layout
setxkbmap -query

# Set X11 keyboard layout (affects only X11/XWayland apps)
setxkbmap -layout us -variant colemak

# Set Wayland compositor layout (affects native Wayland apps)
# Hyprland:
hyprctl keyword input:kb_layout "us"
# Sway:
swaymsg input type:keyboard xkb_layout us

# To keep both in sync, set both in your compositor config:
# Hyprland:
input {
    kb_layout = us
    kb_variant = colemak
    kb_options = caps:escape
}
# The compositor pushes this to XWayland automatically on Hyprland 0.38+
```

Key remappers like `kanata` and `keyd` operate at the evdev layer, below XWayland, so they work
transparently for both X11 and Wayland apps. Tools that operate at the X11 level (like `xdotool
key`) only affect X11 apps.

**Pointer events:**

Mouse cursor position in XWayland is translated through the XWayland root window coordinate
system. The compositor tracks the cursor and translates global Wayland pointer coordinates into
XWayland-local coordinates before delivering them to the X11 window. Under fractional scaling,
this translation can produce sub-pixel offsets that accumulate into visible mouse lag or incorrect
click targets.

```bash
# Test pointer coordinate accuracy in XWayland
DISPLAY=:0 xdotool getmouselocation
# Compare to actual visual cursor position — should match

# If mouse clicks register at wrong position in X11 apps,
# check for stale XWayland scale settings:
hyprctl keyword xwayland:force_zero_scaling true
# Then restart XWayland by killing it (compositor will respawn it):
pkill Xwayland
```

---

## 64.8 Security Model and Threat Surface

The security implications of XWayland are serious and deserve explicit attention. Wayland's core
security model is isolation: a Wayland client cannot observe input events destined for another
client, cannot read the framebuffer contents of another window, and cannot inject input. X11 has
no such guarantees — any X11 client can read keystrokes destined for any other X11 client, capture
screenshots of any X11 window, and forge input events.

XWayland runs a single X11 server. All X11 applications share the same X11 security domain,
regardless of how isolated your Wayland session is. A malicious or compromised X11 application
can keylog any other X11 application, capture clipboard contents from X11 apps, and take screenshots
of any X11 window. It cannot, however, directly observe Wayland-native apps.

**Practical security boundaries:**

| Action | X11 app → X11 app | X11 app → Wayland app | Wayland app → Wayland app |
|---|---|---|---|
| Read keystrokes | YES (XGetImage) | NO | NO |
| Screenshot window | YES | NO | NO (portal required) |
| Inject pointer events | YES (XSendEvent) | NO | NO |
| Read clipboard | YES | Via XWayland bridge | Via portal only |
| Enumerate windows | YES | YES (foreign-toplevel) | YES (foreign-toplevel) |

```bash
# Audit which X11 clients are connected to XWayland
DISPLAY=:0 xlsclients -l

# Check for X11 clients listening for key events (potential keyloggers)
DISPLAY=:0 xdotool behave_screen_edge --delay 0 top echo

# Use xev to monitor X11 events on the root window
DISPLAY=:0 xev -root

# Identify if a specific app is running as X11 or native Wayland
hyprctl clients -j | jq '.[] | select(.title | test("AppName"; "i")) | {title, xwayland, pid}'
```

The correct security posture is: minimize the set of X11 applications you run. Every X11 app in
your session is part of a shared, unprotected X11 security domain. See Ch 82 for sandboxing
strategies and Flatpak portal usage to further isolate legacy applications.

---

## 64.9 Identifying X11 vs Wayland Windows

Being able to quickly determine whether a window is running as an X11 client or a native Wayland
client is a fundamental debugging skill. The compositor tracks this information and exposes it
through its IPC interface.

```bash
# Hyprland: list all clients showing their xwayland status
hyprctl clients | grep -E "(class|title|xwayland)"

# More structured output with jq
hyprctl clients -j | jq '.[] | {title: .title, class: .class, is_x11: .xwayland}'

# Find all X11 (XWayland) clients only
hyprctl clients -j | jq '.[] | select(.xwayland == true) | .title'

# Find all native Wayland clients only
hyprctl clients -j | jq '.[] | select(.xwayland == false) | .title'

# Sway: list windows with their type
swaymsg -t get_tree | jq '.. | objects | select(.shell?) | {name, shell}'
# shell will be "xdg_shell" for Wayland, "xwayland" for X11

# GNOME (using gdbus or xprop)
# If the window responds to xprop, it's X11
xprop -id $(xdotool selectwindow) | head -5

# Universal check: if DISPLAY=:0 xprop can get info, it's X11
DISPLAY=:0 xprop -id $(DISPLAY=:0 xdotool selectwindow) WM_CLASS 2>/dev/null \
    && echo "X11 window" || echo "Not an X11 window (or xdotool failed)"
```

A useful script to show a window's backend with a click:

```bash
#!/usr/bin/env bash
# ~/bin/check-window-backend.sh
# Click a window to see if it's X11 or Wayland

WIN_ID=$(DISPLAY=:0 xdotool selectwindow 2>/dev/null)
if [ -n "$WIN_ID" ]; then
    CLASS=$(DISPLAY=:0 xprop -id "$WIN_ID" WM_CLASS 2>/dev/null | awk -F'"' '{print $4}')
    echo "X11 window (WM_CLASS class: $CLASS)"
else
    echo "Could not select window via X11 — may be native Wayland"
fi
```

---

## 64.10 XWayland and GPU Acceleration

By default, XWayland uses the same GPU as the Wayland compositor. On systems with multiple GPUs
(e.g., a laptop with integrated Intel and discrete NVIDIA), there can be a mismatch: the compositor
runs on the integrated GPU, but NVIDIA drivers only export DMA-BUF from the discrete GPU. This
causes XWayland to fall back to software rendering, producing poor performance.

```bash
# Check if XWayland is using hardware acceleration
DISPLAY=:0 glxinfo | grep -E "(renderer|vendor|direct)"
# "direct rendering: Yes" confirms hardware acceleration
# "llvmpipe" or "softpipe" in renderer = software rendering

# Check which GPU XWayland is using
DISPLAY=:0 glxinfo | grep "OpenGL renderer"

# On NVIDIA + wlroots setups, set explicit rendernode
# Hyprland: set LIBVA_DRI_DRIVER environment for XWayland
env {
    LIBVA_DRIVER_NAME = nvidia
    __GLX_VENDOR_LIBRARY_NAME = nvidia
    NVD_BACKEND = direct
}

# Force XWayland to use a specific DRM render node
Xwayland :0 -rootless -glamor -dri3 -listen unix -rendernode /dev/dri/renderD128
```

**Glamor acceleration:**

Xwayland uses Glamor (GL-accelerated 2D rendering) by default when a compatible EGL device is
available. If Glamor initialization fails, XWayland falls back to software rendering silently.
Check the compositor log for XWayland initialization messages:

```bash
# Hyprland: check compositor log for XWayland Glamor status
journalctl --user -u hyprland -b | grep -i "xwayland\|glamor"

# Or check the Hyprland debug log
cat ~/.local/share/hyprland/hyprland.log | grep -i "xwayland\|glamor"
```

---

## 64.11 Forcing Applications to Use Native Wayland

Many applications that ship with X11 as their default backend support native Wayland via a flag
or environment variable. Switching them away from XWayland improves HiDPI rendering, reduces
latency, and removes them from the shared X11 security domain.

**GTK applications:**

```bash
# Force GTK apps to use Wayland backend
export GDK_BACKEND=wayland

# Per-app: launch with backend override
GDK_BACKEND=wayland gimp

# If app crashes with Wayland backend, allow fallback
export GDK_BACKEND=wayland,x11
```

**Qt applications:**

```bash
# Qt5 Wayland backend
export QT_QPA_PLATFORM=wayland

# Qt6 (same variable)
export QT_QPA_PLATFORM=wayland

# Allow fallback to X11 if Wayland fails
export QT_QPA_PLATFORM=wayland;xcb

# Qt apps that need Wayland decorations (KDE)
export QT_WAYLAND_DISABLE_WINDOWDECORATION=1
```

**Electron / Chromium applications:**

```bash
# Electron apps (VS Code, Discord, Obsidian, etc.)
# Add flags to the app's .desktop file or launch wrapper:
--enable-features=UseOzonePlatform --ozone-platform=wayland

# Example: VS Code native Wayland
code --enable-features=UseOzonePlatform --ozone-platform=wayland

# Or set via environment variable (Electron 20+):
export ELECTRON_OZONE_PLATFORM_HINT=wayland

# Example Hyprland exec-once for Electron apps:
exec-once = env ELECTRON_OZONE_PLATFORM_HINT=wayland code
```

**Mozilla Firefox:**

```bash
# Firefox native Wayland (about:config or environment)
export MOZ_ENABLE_WAYLAND=1

# Or in Hyprland config:
exec-once = env MOZ_ENABLE_WAYLAND=1 firefox

# Verify Firefox is running native Wayland:
# Open about:support in Firefox, look for "Window Protocol: wayland"
```

Add all the above to your session environment to maximize the number of apps using native Wayland:

```conf
# ~/.config/hypr/hyprland.conf — environment block
env = GDK_BACKEND,wayland,x11
env = QT_QPA_PLATFORM,wayland;xcb
env = MOZ_ENABLE_WAYLAND,1
env = ELECTRON_OZONE_PLATFORM_HINT,wayland
env = XCURSOR_THEME,Adwaita
env = XCURSOR_SIZE,24
```

See Ch 53 for how session environment variables are exported and inherited by child processes.

---

## 64.12 Disabling XWayland

For maximum security or resource minimization, XWayland can be disabled entirely. This breaks
any application that does not support native Wayland, so audit your application list first.

Common applications that still require XWayland (as of 2025):

| Application | Status | Alternative |
|---|---|---|
| Steam (UI) | X11 (some parts) | `STEAM_FORCE_DESKTOPUI_SCALING` + native mode |
| Wine / Proton | X11 | Use `WAYLAND_DISPLAY` in Wine 9.x experimental |
| GIMP < 3.0 | X11 | GIMP 3.0 has GTK4 Wayland support |
| xterm | X11 only | foot, alacritty, kitty |
| Many Electron apps | X11 default | Use `--ozone-platform=wayland` flag |
| xdotool | X11 only | `ydotool` for Wayland input injection |
| Older Java apps (AWT) | X11 | `_JAVA_AWT_WM_NONREPARENTING=1` helps |

```conf
# Hyprland: disable XWayland
misc {
    disable_xwayland = true
}
```

```bash
# Sway: disable XWayland (pass --no-xwayland flag)
sway --no-xwayland

# Or in sway config:
xwayland disable
```

---

## 64.13 Troubleshooting

This section covers the most common XWayland problems and their solutions.

**Problem: X11 app starts but renders as X11 instead of native Wayland**

Cause: Application is using its X11 backend because the Wayland environment variables are not set.

```bash
# Check which backend the app is using
hyprctl clients -j | jq '.[] | select(.title | test("AppName"; "i")) | .xwayland'
# true = X11, false = native Wayland

# Fix: set the appropriate backend variable before launching
GDK_BACKEND=wayland app-name
QT_QPA_PLATFORM=wayland app-name
ELECTRON_OZONE_PLATFORM_HINT=wayland app-name
```

**Problem: X11 app window is blurry or fonts look wrong on HiDPI**

Cause: DPI not set correctly for X11 apps.

```bash
# Set DPI via xrdb
xrdb -merge - <<< "Xft.dpi: 192"

# Check current Xft DPI setting
xrdb -query | grep Xft.dpi

# Hyprland: enable force_zero_scaling
hyprctl keyword xwayland:force_zero_scaling true
```

**Problem: Clipboard paste fails between X11 and Wayland apps**

Cause: XWayland clipboard bridge is not running or has stalled.

```bash
# Restart XWayland (compositor will respawn it automatically)
pkill Xwayland

# Manual sync: pull from Wayland and push to X11
wl-paste | xclip -selection clipboard

# Install autocutsel for persistent sync
autocutsel -fork &

# Check if X11 clipboard has any content
xclip -selection clipboard -o
```

**Problem: Mouse clicks land in wrong position in X11 app**

Cause: Coordinate translation bug, often related to fractional scaling.

```bash
# Enable force_zero_scaling to normalize coordinates
hyprctl keyword xwayland:force_zero_scaling true

# Restart XWayland after changing scale settings
pkill Xwayland

# Verify with xdotool
DISPLAY=:0 xdotool getmouselocation --shell
```

**Problem: XWayland not starting / `$DISPLAY` is empty**

Cause: Compositor did not launch XWayland (may be disabled), or startup race condition.

```bash
# Check compositor log for XWayland errors
journalctl --user -b | grep -i "xwayland\|display\|socket"

# Check if socket exists
ls /tmp/.X11-unix/

# Manually test: can Xwayland start at all?
Xwayland :99 -rootless &
DISPLAY=:99 xterm &  # should open an xterm if Xwayland starts OK

# Hyprland: check misc.disable_xwayland
grep -i xwayland ~/.config/hypr/hyprland.conf
```

**Problem: X11 app has no window decorations or appears as a popup**

Cause: Override-redirect window handled differently, or XDG decoration negotiation failed.

```bash
# Check window type
DISPLAY=:0 xprop -id $(DISPLAY=:0 xdotool selectwindow) _NET_WM_WINDOW_TYPE

# Force server-side decorations for X11 windows in Hyprland
windowrulev2 = decorate on, xwayland:1

# Add a border to all X11 windows for visibility
windowrulev2 = bordersize 3, xwayland:1
```

**Problem: XWayland using software rendering (slow, high CPU)**

Cause: Glamor initialization failed, usually a DRM/EGL device mismatch.

```bash
# Confirm software rendering
DISPLAY=:0 glxinfo | grep "direct rendering"

# Check Xwayland logs
journalctl --user -b | grep -i "glamor\|xwayland\|egl"

# Try explicit DRI3 rendernode
Xwayland :0 -rootless -dri3 -rendernode /dev/dri/renderD128

# On NVIDIA: ensure nvidia-drm.modeset=1 kernel parameter
cat /proc/cmdline | grep nvidia
```

| Problem | Cause | Fix |
|---|---|---|
| App starts as X11 instead of Wayland | Missing env vars | Set `QT_QPA_PLATFORM=wayland`, `GDK_BACKEND=wayland`, `ELECTRON_OZONE_PLATFORM_HINT=wayland` |
| Blurry X11 app on HiDPI | DPI mismatch | `xrdb -merge <<< "Xft.dpi: 192"` + `force_zero_scaling = true` |
| X11 app crashes, no display | XWayland not running | Check `misc.disable_xwayland`, check `/tmp/.X11-unix/` |
| Clipboard paste fails X11 ↔ Wayland | Bridge stalled | `pkill Xwayland` or run `autocutsel -fork` |
| Mouse click offset in X11 app | Fractional scale coordinates | `hyprctl keyword xwayland:force_zero_scaling true` |
| XWayland software rendering | Glamor/EGL failure | Check journal for EGL errors, specify `-rendernode` |
| No window decorations on X11 app | Override-redirect or CSD | `windowrulev2 = decorate on, xwayland:1` |
| `DISPLAY` not set | XWayland disabled or slow start | Check `misc.disable_xwayland = false`, check compositor log |

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
