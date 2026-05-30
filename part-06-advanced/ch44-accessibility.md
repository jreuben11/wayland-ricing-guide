# Chapter 44 — Accessibility on Wayland

## Overview

Wayland's accessibility story is a tale of two epochs: the X11 era, where a single `DISPLAY` variable gave every tool uniform access to pixels, keyboard events, and window geometry; and the Wayland era, where protocol isolation, per-compositor extensions, and D-Bus mediation have forced a rethink of how assistive technologies operate at the system level. This chapter documents the current state of accessibility on Wayland compositors — what works, what requires workarounds, and how to configure a fully accessible Wayland desktop from scratch. It surveys the AT-SPI2 D-Bus registry that underpins all Linux accessibility tooling, the Orca screen reader and speech-dispatcher pipeline, screen magnification options on compositors that lack a built-in magnifier, on-screen keyboards using the `zwp_virtual_keyboard_manager_v1` protocol, and color correction mechanisms including Hyprland's native CTM and KDE's color-blindness KWin effect.

The audience is assumed to be comfortable with compositor configuration, D-Bus introspection, and compiling software from source when necessary. We cover GNOME, KDE Plasma, Sway, and Hyprland as representative targets, noting divergences where the compositor matters.

---

## Contents

- [44.1 Accessibility Architecture on Wayland](#441-accessibility-architecture-on-wayland)
- [44.2 Orca Screen Reader](#442-orca-screen-reader)
- [44.3 Screen Magnification](#443-screen-magnification)
- [44.4 On-Screen Keyboard](#444-on-screen-keyboard)
- [44.5 High Contrast and Visual Accessibility](#445-high-contrast-and-visual-accessibility)
- [44.6 Color Blindness Accommodations](#446-color-blindness-accommodations)
- [44.7 Focus and Navigation Accessibility](#447-focus-and-navigation-accessibility)
- [44.8 Status and Roadmap (2025–2026)](#448-status-and-roadmap-2025-2026)
- [44.9 Sticky Keys and Input Accessibility](#449-sticky-keys-and-input-accessibility)
- [Troubleshooting](#troubleshooting)

---


## 44.1 Accessibility Architecture on Wayland

The foundation of Linux desktop accessibility is AT-SPI2 (Assistive Technology Service Provider Interface version 2), the D-Bus-based successor to CORBA-era AT-SPI. Every GTK4, Qt6, and Electron application exposes an accessibility tree over D-Bus at the well-known bus name `org.a11y.Bus`. Screen readers, automation tools, and testing frameworks query this bus to navigate UI hierarchies, read widget labels, and synthesize input events without direct X11 access.

Under X11, `at-spi2-atk` served as a bridge between the GTK accessibility API (ATK) and AT-SPI2. Under Wayland, GTK4 speaks AT-SPI2 natively through `libatk-adaptor`, eliminating the intermediate bridge for modern toolkits. Qt6 ships with `qt-at-spi` providing equivalent coverage. Applications that still use GTK3 or older Qt versions continue to require the bridge package, typically `at-spi2-atk` or its distro equivalent.

The accessibility registry daemon (`at-spi2-registryd`) must be running before any accessible application launches. On systemd-based desktops, the unit `at-spi-dbus-bus.service` starts automatically when the user session initializes. You can verify the daemon is reachable:

```bash
# Check the accessibility bus socket
busctl --user list | grep a11y

# Inspect accessible application list
busctl --user call org.a11y.Bus /org/a11y/bus org.a11y.Bus GetAddress

# Enumerate all AT-SPI2 accessible applications
python3 -c "
import subprocess
result = subprocess.run(['busctl', '--user', 'list'], capture_output=True, text=True)
for line in result.stdout.splitlines():
    if 'atspi' in line.lower() or 'a11y' in line.lower():
        print(line)
"
```

Wayland complicates the architecture in one critical area: global accessibility actions. X11 tools could inject synthetic key events and warp the pointer freely; Wayland compositors mandate that such privileged operations go through explicit protocols. Screen readers that relied on `XSendEvent` for focus traversal now need compositor-level support. GNOME Mutter exposes a private `org.gnome.Shell.Magnifier` D-Bus interface and cooperates with Orca through a dedicated accessible compositor API. wlroots compositors like Sway and Hyprland lack this integration today, meaning global speech announcement of focus changes outside of AT-SPI2-instrumented applications is not yet reliable.

| Layer | Component | Wayland Status |
|---|---|---|
| D-Bus registry | `at-spi2-registryd` | Works on all compositors |
| GTK4 accessibility | Built-in AT-SPI2 | Works on all compositors |
| Qt6 accessibility | `qt-at-spi` plugin | Works on all compositors |
| Global keyboard hook | Compositor extension | GNOME/KDE only |
| Screen magnification | Compositor extension | GNOME/KDE only |
| Pointer warp | `zwp_relative_pointer` | Limited, app-initiated only |
| Virtual keyboard | `zwp_virtual_keyboard_v1` | Most compositors |

See Ch 12 for a deep dive into Wayland protocol extensions and how to probe compositor capabilities at runtime.

---

## 44.2 Orca Screen Reader

Orca is the primary screen reader for the Linux desktop and the most mature accessibility tool in the Wayland ecosystem. It is authored in Python, communicates with AT-SPI2, and delegates speech synthesis to `speech-dispatcher`, which in turn drives backends such as eSpeak-NG, Festival, or cloud TTS services. On GNOME with Mutter, Orca receives full compositor cooperation for global focus tracking; on other compositors, it works reliably within individual accessible applications.

Install Orca and its speech backend:

```bash
# Debian/Ubuntu
sudo apt install orca speech-dispatcher espeak-ng

# Fedora
sudo dnf install orca speech-dispatcher espeak-ng

# Arch
sudo pacman -S orca speech-dispatcher espeak-ng

# Enable and start speech-dispatcher for the user session
systemctl --user enable --now speech-dispatcher.service
```

Configure speech-dispatcher to use eSpeak-NG as the default module:

```
# ~/.config/speech-dispatcher/speechd.conf
AddModule "espeak-ng"  "sd_espeak-ng" "espeak-ng.conf"
DefaultModule espeak-ng
DefaultRate 50
DefaultPitch 50
DefaultLanguage "en"
DefaultVoiceType MALE1
```

Launch Orca in a Wayland session:

```bash
# Foreground (for initial configuration)
orca --setup

# Background (normal use — add to session autostart)
orca &

# Restart Orca if it hangs
pkill -f orca && sleep 0.5 && orca &
```

Orca's key bindings use the `Orca Modifier` key (Insert or Caps Lock). The full binding set is documented in `/usr/share/orca/doc/`; the most critical ones for initial orientation:

| Key | Action |
|---|---|
| `Orca+F2` | Learn mode (announces next key pressed) |
| `Orca+F1` | Read the current item |
| `Orca+Up` | Read current line |
| `Orca+Left/Right` | Previous/next word |
| `Orca+F3` | Focus next accessible item |
| `Orca+H` | List of headings (web mode) |

On Hyprland and Sway, Orca announces focus changes within a GTK4 or Qt6 application correctly because that path is pure AT-SPI2. What does not work is Orca announcing which application became focused when you `Alt+Tab` — that event is compositor-generated and not exposed over AT-SPI2. A partial workaround uses an IPC hook to notify Orca via its D-Bus interface:

```bash
# ~/.config/hypr/scripts/a11y-focus-announce.sh
#!/usr/bin/env bash
# Run via hyprland event listener; called with window title as $1
TITLE="$1"
gdbus call --session \
  --dest org.gnome.Orca \
  --object-path /org/gnome/Orca \
  --method org.gnome.Orca.sayMessage \
  "Focused: $TITLE" \
  "true" 2>/dev/null || true
```

```bash
# In hyprland.conf — trigger on active window change
exec-once = socat - UNIX-CONNECT:/tmp/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock \
  | while read -r line; do \
      if [[ "$line" == activewindow* ]]; then \
        title=$(echo "$line" | cut -d',' -f2); \
        ~/.config/hypr/scripts/a11y-focus-announce.sh "$title"; \
      fi; \
    done &
```

See Ch 38 for full Hyprland IPC event documentation and socket protocol details.

---

## 44.3 Screen Magnification

Screen magnification is the accessibility feature most fragmented across Wayland compositors. X11 provided `XRandR` and raw framebuffer access that tools like `xzoom` exploited freely. Wayland's security model prohibits arbitrary screen capture without compositor consent, meaning each compositor must implement its own magnification protocol or extension.

**GNOME Shell** ships a built-in magnifier activated via the accessibility settings or keyboard shortcut:

```bash
# Enable GNOME magnifier programmatically
gsettings set org.gnome.desktop.a11y.magnifier active true

# Set magnification factor (1.0 = 100%)
gsettings set org.gnome.desktop.a11y.magnifier mag-factor 2.0

# Choose lens mode: full-screen, left-half, right-half, top-half, bottom-half, corner
gsettings set org.gnome.desktop.a11y.magnifier lens-mode full-screen

# Enable mouse tracking
gsettings set org.gnome.desktop.a11y.magnifier mouse-tracking centered

# Keyboard shortcut: Super+Alt+8 by default
# Toggle via dconf
gsettings set org.gnome.desktop.a11y.applications screen-magnifier-enabled true
```

**KDE Plasma (kwin-wayland)** implements magnification as a KWin effect:

```bash
# Enable the zoom effect from CLI
kwriteconfig6 --file kwinrc --group Plugins --key zoomEnabled true
qdbus6 org.kde.KWin /KWin reconfigure

# Keyboard bindings: Meta+= to zoom in, Meta+- to zoom out
# Configure zoom step:
kwriteconfig6 --file kwinrc --group Effect-Zoom --key ZoomFactor 0.2
```

**Sway** has no built-in magnifier. The `wlr-screencopy-unstable-v1` protocol used by `grim` and similar tools enables third-party implementations. The most practical workaround today is `wl-mirror`, which creates a real-time copy of a portion of the screen in a floating window that can be zoomed:

```bash
# Install wl-mirror (AUR: wl-mirror, or build from source)
# https://github.com/Ferdi265/wl-mirror

# Mirror the primary output at 2x scale in a floating window
wl-mirror -S 2.0 eDP-1 &

# For a cropped region around the cursor, pair with a cursor-tracking wrapper
# (community script: https://github.com/Ferdi265/wl-mirror/wiki/Usage)

# In sway config: float the mirror window and pin it
for_window [app_id="at.yrlf.wl_mirror"] floating enable, sticky enable
```

**Hyprland** can use a similar approach, with `wl-mirror` assigned to a scratchpad:

```
# hyprland.conf
bind = $mod, M, exec, wl-mirror -S 2.0 $(hyprctl monitors -j | jq -r '.[0].name')
windowrulev2 = float, class:^(at.yrlf.wl_mirror)$
windowrulev2 = pin, class:^(at.yrlf.wl_mirror)$
windowrulev2 = size 640 360, class:^(at.yrlf.wl_mirror)$
windowrulev2 = move 1270 710, class:^(at.yrlf.wl_mirror)$
```

A more capable solution under development is `wayfreeze` combined with `swayimg`, which freezes the screen and provides a zoomable lens — useful for reading small text in screenshots even on compositors without protocol magnification support.

---

## 44.4 On-Screen Keyboard

On-screen keyboards on Wayland use the `zwp_virtual_keyboard_manager_v1` protocol to inject keystrokes as if from a physical device, bypassing the X11 `XSendEvent` path entirely. This is architecturally cleaner and more secure, but requires the compositor to support the protocol. All major compositors (GNOME, KDE, Sway, Hyprland) support it.

**wvkbd** is the lightest-weight option: a layer-shell application that renders a configurable keyboard layout and emits keycodes through the virtual keyboard protocol.

```bash
# Install from AUR or build from source
# https://github.com/jjsullivan5196/wvkbd
git clone https://github.com/jjsullivan5196/wvkbd
cd wvkbd
make
sudo make install

# Launch with the mobile-international layout
wvkbd-mobintl &

# Launch in a specific geometry (bottom of a 1920×1080 screen)
wvkbd-mobintl -L 300 --landscape &

# Toggle visibility (useful for binding a key)
pkill -USR1 wvkbd-mobintl

# Sway integration: toggle with $mod+k
bindsym $mod+k exec pkill -USR1 wvkbd-mobintl || wvkbd-mobintl &
```

Custom wvkbd layouts are defined in C header files in the source tree. For production use, define a layout and rebuild:

```c
// keyboards/custom.h — example layout fragment
static struct key_list custom_keyboard = {
  .keys = (struct key[]){
    {.label = "q", .keysym = XKB_KEY_q, .width = 1},
    {.label = "w", .keysym = XKB_KEY_w, .width = 1},
    // ... full row
    {.end_row = true},
  },
  .n_keys = ...,
};
```

**Squeekboard** is the GTK4-based on-screen keyboard developed for GNOME Mobile / Phosh:

```bash
sudo apt install squeekboard    # Debian/Ubuntu
sudo pacman -S squeekboard      # Arch

# Squeekboard is activated via input-method D-Bus API;
# most desktop environments auto-launch it when a text field gains focus.
# Manually show/hide:
gdbus call --session \
  --dest sm.puri.OSK0 \
  --object-path /sm/puri/OSK0 \
  --method sm.puri.OSK0.SetVisible true
```

**Onboard** requires XWayland and works with limitations:

```bash
sudo apt install onboard
# Launch under XWayland (requires Xwayland running)
DISPLAY=:0 onboard &
# Note: cannot overlay Wayland-native windows; restricted to XWayland clients
```

For Hyprland, a robust toggle script using wvkbd with window management:

```bash
#!/usr/bin/env bash
# ~/.config/hypr/scripts/toggle-osk.sh
OSK_PID=$(pgrep -x wvkbd-mobintl)
if [ -n "$OSK_PID" ]; then
    kill "$OSK_PID"
else
    wvkbd-mobintl -L 280 &
fi
```

```
# hyprland.conf
bind = , XF86TouchpadToggle, exec, ~/.config/hypr/scripts/toggle-osk.sh
bind = $mod, K, exec, ~/.config/hypr/scripts/toggle-osk.sh
```

---

## 44.5 High Contrast and Visual Accessibility

High-contrast modes reduce cognitive load and improve legibility for users with low vision or photosensitivity. On Wayland, the toolkit-level theme system (GTK, Qt) handles most of this independently of the compositor, meaning high-contrast configurations travel with the user's dotfiles.

**GTK high contrast** uses the `HighContrast` or `HighContrastInverse` themes. On GTK4, the portal-based color scheme preference is the preferred mechanism:

```bash
# Enable high contrast via GNOME accessibility settings
gsettings set org.gnome.desktop.a11y.interface high-contrast true

# Verify the active GTK theme
gsettings get org.gnome.desktop.interface gtk-theme

# Force GTK_THEME for non-GNOME environments
export GTK_THEME=HighContrast
# Add to ~/.profile or the compositor's exec-env mechanism

# In Sway — set environment variable for all children
exec_always systemctl --user import-environment GTK_THEME
set $GTK_THEME HighContrast
exec_always { export GTK_THEME=$GTK_THEME; }
```

**Text scaling** multiplies all rendered text sizes without changing the screen resolution, preserving sharpness on HiDPI displays:

```bash
# GNOME
gsettings set org.gnome.desktop.interface text-scaling-factor 1.5

# KDE Plasma
kwriteconfig6 --file kdeglobals --group General --key forceFontDPI 144
qdbus6 org.kde.KWin /KWin reconfigure

# GTK applications in non-GNOME environments via Xresources mirror
echo "Xft.dpi: 144" >> ~/.Xresources
# And for Wayland-native apps, use GDK_DPI_SCALE
export GDK_DPI_SCALE=1.5
```

**Cursor size** is critical for users with tracking difficulties:

```bash
# GNOME
gsettings set org.gnome.desktop.interface cursor-size 48

# Sway / wlroots
# In sway config:
seat seat0 xcursor_theme Adwaita 48

# Environment variable (affects most toolkits)
export XCURSOR_SIZE=48

# Hyprland
# In hyprland.conf:
env = XCURSOR_SIZE,48
cursor {
  no_hardware_cursors = false
  # hardware cursor size is set by the seat
}
# Also set:
exec-once = gsettings set org.gnome.desktop.interface cursor-size 48
```

For environments without GNOME settings integration, write cursor theme and size to `~/.config/gtk-3.0/settings.ini` and `~/.config/gtk-4.0/settings.ini`:

```ini
# ~/.config/gtk-3.0/settings.ini
[Settings]
gtk-cursor-theme-name = Adwaita
gtk-cursor-theme-size = 48
gtk-font-name = Sans 14
gtk-theme-name = HighContrast
gtk-icon-theme-name = HighContrast

# ~/.config/gtk-4.0/settings.ini
[Settings]
gtk-cursor-theme-name = Adwaita
gtk-cursor-theme-size = 48
gtk-font-name = Sans 14
gtk-theme-name = Adwaita:dark
```

---

## 44.6 Color Blindness Accommodations

Color blindness (affecting approximately 8% of males) requires either recoloring the entire framebuffer or adjusting application color palettes. Wayland compositors that expose a Color Transformation Matrix (CTM) or shader pipeline can apply software filters.

**Hyprland CTM** (Color Transformation Matrix) allows per-output color correction matrices applied at the compositor level — every pixel on screen passes through the matrix:

```bash
# Apply a deuteranopia (green-blind) correction matrix
# Matrix values from Daltonize algorithm
hyprctl keyword monitor eDP-1,ctm,\
  0.625 0.375 0.000 \
  0.700 0.300 0.000 \
  0.000 0.300 0.700

# Protanopia (red-blind) correction
hyprctl keyword monitor eDP-1,ctm,\
  0.567 0.433 0.000 \
  0.558 0.442 0.000 \
  0.000 0.242 0.758

# Reset to identity
hyprctl keyword monitor eDP-1,ctm,\
  1.0 0.0 0.0 \
  0.0 1.0 0.0 \
  0.0 0.0 1.0
```

Persist a CTM in `hyprland.conf`:

```
monitor = eDP-1, preferred, auto, 1, ctm, 0.625 0.375 0 0.7 0.3 0 0 0.3 0.7
```

**KDE Plasma** uses the Color Blindness Correction KWin effect:

```bash
kwriteconfig6 --file kwinrc --group Plugins --key colorblindnessEnabled true
# Then set the deficiency type (0=Protanopia, 1=Deuteranopia, 2=Tritanopia)
kwriteconfig6 --file kwinrc --group Effect-ColorBlindness --key Deficiency 1
qdbus6 org.kde.KWin /KWin reconfigure
```

**wl-gammarelay** provides a D-Bus interface to per-output gamma, brightness, and temperature controls, scriptable from any language:

```bash
# Install from AUR: wl-gammarelay-rs
# Start the service
wl-gammarelay &

# Reduce blue light (accessibility for photosensitivity)
busctl --user set-property rs.wl-gammarelay / rs.wl-gammarelay Temperature q 4500

# Increase brightness programmatically
busctl --user set-property rs.wl-gammarelay / rs.wl-gammarelay Brightness d 1.2

# Example: bind a key to toggle warm mode in Sway
bindsym $mod+shift+w exec busctl --user set-property rs.wl-gammarelay / \
  rs.wl-gammarelay Temperature q 3500
```

For users who need the Daltonize algorithm applied as a live shader rather than a static CTM, the `hyprland-plugin-daltonize` AUR package wraps Daltonize's OpenGL shader into a Hyprland plugin:

```bash
yay -S hyprland-plugin-daltonize
# In hyprland.conf:
plugin = /usr/lib/hyprland/daltonize.so
# Configuration in hyprland.conf:
plugin:daltonize {
    type = deuteranopia    # protanopia | deuteranopia | tritanopia
    strength = 0.8         # 0.0–1.0
}
```

---

## 44.7 Focus and Navigation Accessibility

Keyboard navigation and visual focus indicators are accessibility requirements that compositors and toolkits share responsibility for. A riced desktop must not sacrifice keyboard navigability for visual aesthetics.

**Sway focus follows cursor** options are configurable per workspace:

```
# sway config
# Disable focus-follows-mouse for users who cannot control pointing devices precisely
focus_follows_mouse no

# Alternatively: focus follows mouse only when moving into a window
focus_follows_mouse always  # or: yes | no | always

# Mouse warping: keep pointer over focused window (useful for screen reader sync)
mouse_warping container   # or: output | none

# Large, high-contrast window borders
default_border normal 4
client.focused          #5294E2 #5294E2 #FFFFFF #5294E2 #5294E2
client.unfocused        #333333 #222222 #888888 #292D2E #222222
client.urgent           #FF0000 #FF0000 #FFFFFF #FF0000 #FF0000

# Title bars improve spatial orientation for screen reader users
default_border normal 3
titlebar_padding 6 4
```

**Hyprland** equivalent focus and border configuration:

```
# hyprland.conf
general {
    border_size = 4
    col.active_border = rgba(5294E2ff) rgba(5294E2ff) 45deg
    col.inactive_border = rgba(333333aa)
    gaps_in = 4
    gaps_out = 8
}

# Disable focus-follows-mouse
input {
    follow_mouse = 0    # 0=disabled, 1=full, 2=loose, 3=full force
}

# Focus ring animation (makes focus changes more visible)
animations {
    enabled = true
    bezier = focusCurve, 0.05, 0.9, 0.1, 1.0
    animation = border, 1, 5, focusCurve
}
```

**GTK focus ring** styling for apps that use custom GTK CSS (e.g., apps with Adwaita overrides):

```css
/* ~/.config/gtk-4.0/gtk.css — increase focus visibility */
*:focus {
    outline: 3px solid #5294E2;
    outline-offset: 2px;
}

button:focus, entry:focus, treeview:focus {
    box-shadow: 0 0 0 3px alpha(@accent_bg_color, 0.5);
}
```

**Keyboard-only navigation in wlroots compositors** benefits from explicit focus cycling modes. In Sway, configure directional focus to wrap at screen edges:

```
# sway config
# Move focus wraps around at edges
focus_wrapping yes

# Assign workspaces to QWERTY home row for minimal hand travel
bindsym $mod+a workspace 1
bindsym $mod+s workspace 2
bindsym $mod+d workspace 3
bindsym $mod+f workspace 4
bindsym $mod+g workspace 5
```

See Ch 22 for full keyboard navigation configuration and Ch 31 for focus management in multi-monitor setups.

---

## 44.8 Status and Roadmap (2025–2026)

The accessibility landscape on Wayland compositors in mid-2026 shows clear stratification. GNOME has achieved mature accessibility through tight Mutter–Orca integration maintained since GNOME 40. KDE Plasma 6 has closed most gaps with KWin Wayland effects and the Plasma accessibility service. wlroots-based compositors (Sway, Hyprland, River, Niri) provide AT-SPI2 support for individual applications but lack compositor-level magnification and global screen reader hooks.

| Feature | GNOME | KDE Plasma | Sway | Hyprland |
|---|---|---|---|---|
| AT-SPI2 (app-level) | Full | Full | Full | Full |
| Screen magnifier | Built-in | KWin effect | wl-mirror workaround | wl-mirror workaround |
| Orca global focus | Full | Partial | App-only | App-only |
| On-screen keyboard | Squeekboard | Maliit | wvkbd | wvkbd |
| Color CTM | Via KMS | KWin effect | wl-gammarelay | Native CTM |
| High contrast theme | Portal | Portal | GTK env | GTK env |
| Sticky keys / filter keys | GNOME a11y | KDE a11y | N/A | N/A |

The `ext-session-lock-v1` protocol extension, adopted in Wayland 1.22, ensures that lock screens are accessible — the locked surface can receive AT-SPI2 events, allowing screen reader users to authenticate without sighted assistance. All major lock screen implementations (`swaylock`, `hyprlock`, `waylock`) support this protocol.

Active community developments to watch:

- **wayland-a11y project** (freedesktop.org): Drafting a `wp_accessibility_manager_v1` protocol that would provide compositor-level focus notifications accessible to screen readers on any Wayland compositor.
- **Orca 47+ on wlroots**: The Orca team is experimenting with a `wlr-foreign-toplevel-management-v1`-based plugin that reads toplevel window change events and synthesizes focus announcements without requiring the compositor's private API.
- **Mutter accessibility interface in upstream Wayland**: GNOME's private accessibility protocol is being proposed for standardization as a wl-protocols extension.
- **KDE AccessKit integration**: The AccessKit Rust crate (used by egui, Tauri, and Floem) is being evaluated as a cross-platform AT-SPI2 backend for non-GTK/Qt applications.

To track the state of accessibility in your specific compositor build:

```bash
# Check AT-SPI2 bus availability
dbus-send --session --print-reply --dest=org.freedesktop.DBus \
  /org/freedesktop/DBus org.freedesktop.DBus.ListNames \
  | grep -i a11y

# Enumerate all accessible applications in the current session
python3 - << 'EOF'
import subprocess
import json

result = subprocess.run(
    ["busctl", "--user", "--json=short", "list"],
    capture_output=True, text=True
)
data = json.loads(result.stdout)
for entry in data.get("interfaces", [data]):
    name = entry if isinstance(entry, str) else entry.get("name", "")
    if "atspi" in name.lower():
        print(name)
EOF

# Check if a specific app is accessible (replace com.example.App with actual name)
gdbus introspect --session --dest org.a11y.atspi.Registry \
  --object-path /org/a11y/atspi/accessible/root 2>/dev/null | head -40
```

See Ch 53 for session startup sequencing, including how to ensure `at-spi2-registryd` launches before graphical applications. See Ch 52 for XDG portals and how `xdg-desktop-portal-accessibility` interfaces with the AT-SPI2 stack on non-GNOME compositors.

---

## 44.9 Sticky Keys and Input Accessibility

Sticky Keys, Slow Keys, and Bounce Keys are physical accessibility features that modify keyboard behavior to assist users with motor disabilities. On GNOME, these are managed through `org.gnome.desktop.a11y.keyboard` GSettings:

```bash
# Enable sticky keys (modifier keys latch on single press)
gsettings set org.gnome.desktop.a11y.keyboard enable true
gsettings set org.gnome.desktop.a11y.keyboard stickykeys-enable true

# Audible feedback when modifier latches
gsettings set org.gnome.desktop.a11y.keyboard stickykeys-modifier-beep true

# Disable sticky keys when pressing a modifier twice (toggle)
gsettings set org.gnome.desktop.a11y.keyboard stickykeys-two-key-off true

# Slow Keys: key must be held for N milliseconds before registering
gsettings set org.gnome.desktop.a11y.keyboard slowkeys-enable true
gsettings set org.gnome.desktop.a11y.keyboard slowkeys-delay 300

# Bounce Keys: ignore repeated keypresses within N milliseconds
gsettings set org.gnome.desktop.a11y.keyboard bouncekeys-enable true
gsettings set org.gnome.desktop.a11y.keyboard bouncekeys-delay 400

# Mouse Keys: control the pointer with the numeric keypad
gsettings set org.gnome.desktop.a11y.keyboard mousekeys-enable true
gsettings set org.gnome.desktop.a11y.keyboard mousekeys-max-speed 750
gsettings set org.gnome.desktop.a11y.keyboard mousekeys-accel-time 1200
```

For Sway and Hyprland, libinput handles some input filtering. Sticky Keys are not natively supported; the closest approximation uses `xkeyboard-config` XKB options:

```bash
# XKB option for sticky modifiers (latch behavior)
# In sway config:
input "type:keyboard" {
    xkb_options "lv3:ralt_switch,compose:ralt,grp:alt_shift_toggle"
    # For accessibility options specifically:
    xkb_options "a11y:stickykeys"
}

# Hyprland:
input {
    kb_options = a11y:stickykeys
}
```

Mouse pointer acceleration profiles in libinput can assist users with fine motor control difficulties:

```
# sway config — flat profile for predictable pointer movement
input "type:pointer" {
    accel_profile flat
    pointer_accel 0.0
}

# Hyprland
input {
    accel_profile = flat
    sensitivity = 0.0
}
```

---

## Troubleshooting

**AT-SPI2 registry not found / Orca cannot find accessible applications**

The most common cause is `at-spi2-registryd` not starting before applications launch. Verify:

```bash
# Check if daemon is running
pgrep -a at-spi2-registryd

# Manually start it
/usr/lib/at-spi2-core/at-spi2-registryd &

# Set environment variable that tells apps to use accessibility bus
export AT_SPI_BUS_ADDRESS=$(dbus-send --session --print-reply \
  --dest=org.a11y.Bus /org/a11y/bus org.a11y.Bus.GetAddress \
  2>/dev/null | grep -oP '".*"' | tr -d '"')
echo "AT_SPI_BUS_ADDRESS=$AT_SPI_BUS_ADDRESS"
```

**Orca speaks nothing but the desktop loads**

Check that `speech-dispatcher` is running and `spd-say` produces audio:

```bash
systemctl --user status speech-dispatcher
spd-say "test"
# If silent, check audio output:
pactl list sinks short
pactl set-default-sink <sink-name>
```

**wvkbd keys do not register in focused window**

The compositor may not support `zwp_virtual_keyboard_manager_v1`. Check:

```bash
wayland-info | grep virtual_keyboard
# If absent, the compositor does not support the protocol
# Sway requires sway >= 1.7; Hyprland supports it natively
```

**High contrast theme not applying to Qt applications**

Qt applications need the `kvantum` theme engine or explicit Qt theme settings:

```bash
export QT_QPA_PLATFORMTHEME=qt5ct
# In qt5ct, select a high-contrast color scheme
# Or force the Fusion style which respects palette:
export QT_STYLE_OVERRIDE=Fusion
# Set high-contrast palette in ~/.config/qt5ct/qt5ct.conf
```

**Cursor size not applying in XWayland applications**

XWayland applications read cursor size from `~/.Xresources`:

```bash
echo "Xcursor.size: 48" >> ~/.Xresources
echo "Xcursor.theme: Adwaita" >> ~/.Xresources
xrdb -merge ~/.Xresources   # apply without restarting XWayland
```

**wl-mirror shows black screen on NVIDIA**

NVIDIA proprietary drivers require explicit `GBM_BACKEND` and `__GL_GSYNC_ALLOWED` settings. Also ensure `wl-mirror` is built with EGL support:

```bash
export GBM_BACKEND=nvidia-drm
export __GL_GSYNC_ALLOWED=0
export WLR_RENDERER=vulkan   # for wlroots compositors
wl-mirror eDP-1 &
```

**Orca not reading window title on Hyprland after focus change**

Ensure the IPC listener script from section 44.2 is running and has permission to call `gdbus`. Debug by testing the gdbus call manually:

```bash
gdbus call --session \
  --dest org.gnome.Orca \
  --object-path /org/gnome/Orca \
  --method org.gnome.Orca.sayMessage \
  "Test announcement" "true"
# If this fails with "service not running", Orca is not started
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
