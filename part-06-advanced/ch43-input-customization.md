# Chapter 43 — Input Customization: libinput, kanata, keyd, wev

## Overview

Wayland input handling is architecturally cleaner than X11's. Every compositor
receives input events through libinput, which acts as the single authoritative
layer between raw kernel input devices (`/dev/input/event*`) and higher-level
compositor logic. This means there is no `xorg.conf`, no per-device driver
configuration scattered across the system — instead, all pointer, touchpad,
keyboard, and tablet settings live in the compositor's own configuration file.

This centralization is a feature, not a limitation. Under X11, touchpad behavior
was controlled by `xinput` properties set in shell scripts that had to run after
login. Under Wayland, settings are baked into the compositor config, applied
before the first frame is rendered, and persist without any session startup
magic. The tradeoff is that each compositor exposes its own dialect for libinput
settings — Hyprland's `hyprland.conf` syntax differs from Sway's `config` syntax,
but the underlying libinput option names map one-to-one.

For keyboard remapping beyond what compositors expose natively, the ecosystem
offers several layers: XKB for layout-level changes, keyd for kernel-level
event rewriting that works in TTY and every DE simultaneously, kanata for
sophisticated tap-hold and layer-based remapping, and xremap for
application-aware remapping on supported compositors. Understanding which layer
to use for which problem is half the battle — this chapter covers all of them
with production-ready configurations.

See Ch 12 for an overview of Wayland architecture and how compositor, libinput,
and the kernel interact. See Ch 53 for session startup patterns to auto-launch
daemons like kanata.

---

## 43.1 libinput Configuration

libinput is the standard Linux input library used by every Wayland compositor.
It sits between the kernel's evdev layer and the compositor, normalizing events
from hundreds of device types into a consistent API. The library handles pointer
acceleration, touchpad gesture recognition, palm rejection, scroll source
discrimination, and more — all in one place.

Configuration under Wayland does not use an input configuration file like
`/etc/X11/xorg.conf.d/`. Instead, compositor configuration files carry libinput
settings inline. This means that if you run two compositors (e.g. Sway as your
daily driver and Cage for kiosk testing), you maintain separate copies of the
same logical settings in each compositor's config. The libinput option names are
stable, but the syntax varies.

The most impactful settings for pointer devices are `accel_profile` and
`accel_speed`. The `flat` profile applies a constant scaling factor with no
velocity-dependent acceleration — preferred by gamers and power users who want
predictable one-to-one movement. The `adaptive` profile (the default) applies
more acceleration at high velocities, which can feel more natural for general
desktop use but makes precise cursor placement harder. For tablets and drawing
devices, always use `flat`.

For touchpads, libinput's software button area and clickfinger methods differ
significantly in feel. `buttonareas` divides the touchpad into physical zones
(left third = left click, right third = right click). `clickfinger` uses the
number of fingers on the pad to determine button (1 finger = left, 2 = right,
3 = middle) — this is the default on most hardware and more ergonomic on large
glass pads. `tap-to-click` enables recognizing a quick single-finger tap as a
left click, which on Wayland is enabled or disabled atomically at the libinput
level and does not require `synclient` hacks.

### Key libinput Settings Reference

| Setting | Values | Description |
|---|---|---|
| `accel_profile` | `flat`, `adaptive` | Pointer acceleration curve |
| `accel_speed` / `sensitivity` | -1.0 to 1.0 | Acceleration tuning |
| `natural_scroll` | bool | Inverts scroll direction (macOS-style) |
| `tap-to-click` / `tap` | bool | Single-finger tap as left click |
| `tap-and-drag` | bool | Tap then drag to select |
| `dwt` / `disable_while_typing` | bool | Disable touchpad while typing |
| `click_method` | `buttonareas`, `clickfinger` | Software button method |
| `scroll_method` | `two_finger`, `edge`, `on_button_down` | Scroll gesture |
| `left_handed` | bool | Mirror buttons for left-hand use |
| `middle_emulation` | bool | L+R simultaneous = middle click |

### Hyprland libinput Config

In Hyprland, libinput settings live inside the `input {}` block in
`~/.config/hypr/hyprland.conf`. Touchpad-specific settings go in the nested
`touchpad {}` block. Mouse-specific settings go in `mouse {}`.

```ini
input {
    # Keyboard layout — XKB settings
    kb_layout = us
    kb_variant =
    kb_options = caps:escape_shifted_capslock

    # Pointer acceleration
    accel_profile = flat
    sensitivity = 0        # -1.0 to 1.0; 0 = no scaling in flat mode

    # Scroll direction
    natural_scroll = false

    # Follow mouse focus behavior (0=off, 1=on, 2=no refocus, 3=always)
    follow_mouse = 1

    touchpad {
        natural_scroll = true
        tap-to-click = true
        tap-and-drag = true
        drag_lock = true
        disable_while_typing = true
        scroll_factor = 0.8
        middle_button_emulation = false
        clickfinger_behavior = true   # 2-finger = right click
    }

    # Tablet input area restriction (optional)
    # tablet { ... }
}
```

To apply changes without restarting: `hyprctl reload`

### Sway libinput Config

Sway uses `input` blocks that can target a specific device by its identifier
or use a wildcard. Get device identifiers from `swaymsg -t get_inputs`.

```bash
# List all input devices and their exact identifiers
swaymsg -t get_inputs | jq '.[].identifier'
```

```
# ~/.config/sway/config

# Global pointer settings (wildcard matches all pointers)
input type:pointer {
    accel_profile flat
    pointer_accel 0
}

# Per-device touchpad settings
input "2:7:SynPS/2_Synaptics_TouchPad" {
    accel_profile flat
    natural_scroll enabled
    tap enabled
    tap_button_map lrm     # 1-finger=L, 2-finger=R, 3-finger=M
    drag enabled
    drag_lock enabled
    dwt enabled
    scroll_method two_finger
    click_method clickfinger
    middle_emulation disabled
}

# Left-handed mouse
input "1133:49297:Logitech_MX_Master_3" {
    left_handed enabled
}
```

Reload Sway config without restart: `swaymsg reload`

### niri libinput Config

niri uses `~/.config/niri/config.kdl` with a libinput section:

```kdl
input {
    touchpad {
        tap
        natural-scroll
        accel-speed 0.2
        accel-profile "flat"
        scroll-method "two-finger"
        disabled-on-external-mouse
    }

    mouse {
        accel-profile "flat"
        accel-speed 0.0
    }

    keyboard {
        xkb {
            layout "us"
            options "caps:escape_shifted_capslock,compose:ralt"
        }
    }
}
```

---

## 43.2 wev — Input Event Inspector

`wev` (Wayland event viewer) is the essential debugging tool for Wayland input.
It opens a small window and prints every input event the Wayland compositor
sends to it, including exact keycodes, button numbers, axis values, and
timestamps. This is the Wayland replacement for `xev` — but it only reports
events that the compositor delivers to a window, so it cannot inspect
suppressed events (e.g. events consumed by a compositor keybind).

Install wev from your distribution package manager:

```bash
# Arch Linux
sudo pacman -S wev

# Fedora
sudo dnf install wev

# Debian/Ubuntu
sudo apt install wev

# Build from source
git clone https://git.sr.ht/~sircmpwn/wev && cd wev
make && sudo make install
```

Basic usage prints all events. Use `-f` to filter to a specific interface:

```bash
# All events (keyboard + mouse + touch)
wev

# Keyboard events only
wev -f wl_keyboard

# Pointer events only (mouse movement, clicks, scroll)
wev -f wl_pointer

# Touch events only (touchscreen)
wev -f wl_touch

# Tablet events (for Wacom/drawing tablets)
wev -f zwp_tablet_pad_v2
```

### Reading wev Output

When you press a key, wev prints two events: key press and key release. The
`sym` field is the XKB keysym name, and `code` is the raw evdev keycode.
For remapping with keyd or kanata, the `code` value is what matters at the
kernel level.

```
[14:          wl_keyboard] key, serial 12345, time 1234567, key 58, state KEY_STATE_PRESS
                           sym: Caps_Lock (0xff08), utf8: ''
[14:          wl_keyboard] key, serial 12346, time 1234668, key 58, state KEY_STATE_RELEASE
                           sym: Caps_Lock (0xff08), utf8: ''
```

For mouse buttons, the button number maps to Linux input event codes. Button 272
is BTN_LEFT, 273 is BTN_RIGHT, 274 is BTN_MIDDLE. Side buttons on mice typically
appear as 275 (BTN_SIDE) and 276 (BTN_EXTRA).

```bash
# Find the exact device name to use in Sway's input block
wev -f wl_keyboard 2>/dev/null | grep -E "^\\[|name"

# Log a wev session to file for analysis
wev 2>/dev/null | tee ~/input-events.log
```

### Using wev to Diagnose Remapping Issues

If a key you remapped does not behave as expected, run wev and press the key.
If the original keysym appears, your remapper (keyd/kanata) is not intercepting
the event — check that the daemon is running and targeting the correct device.
If no event appears at all, the compositor is consuming the key before it
reaches windows (check compositor keybinds). If the remapped keysym appears
correctly in wev but the application ignores it, the issue is application-level
input handling, not remapping.

---

## 43.3 kanata — Powerful Cross-Platform Remapper

kanata is a software keyboard remapper written in Rust that operates at the
`/dev/input/` level using the `evdev` kernel interface. Because it intercepts
events below the compositor, it is completely transparent to Wayland, X11, and
TTY sessions — the compositor receives already-remapped events and has no
knowledge of the transformation. This makes kanata uniquely powerful for users
who want consistent behavior across all contexts.

kanata requires access to `/dev/input/` devices, which typically means running
as root or adding your user to the `input` group. The `uinput` module must also
be loaded for kanata to create the virtual output device:

```bash
# Add user to input group (requires logout/login to take effect)
sudo usermod -aG input $USER

# Load uinput module now
sudo modprobe uinput

# Load uinput at boot
echo "uinput" | sudo tee /etc/modules-load.d/uinput.conf

# Verify uinput is available
ls -la /dev/uinput
```

Install kanata:

```bash
# Arch Linux (AUR)
yay -S kanata

# Or download a pre-built binary from GitHub releases
curl -L https://github.com/jtroo/kanata/releases/latest/download/kanata -o ~/.local/bin/kanata
chmod +x ~/.local/bin/kanata

# Build from source (requires Rust toolchain)
cargo install kanata
```

### kanata Configuration Syntax

kanata uses a Lisp-like syntax (`.kbd` files). The structure is:
1. `defsrc` — declare which physical keys kanata intercepts
2. `deflayer` — define what those keys do in each layer
3. `defalias` — define complex behaviors referenced in layers

```scheme
;; ~/.config/kanata/kanata.kbd

;; --- Source Keys ---
;; Only keys listed here are intercepted by kanata.
;; Other keys pass through unmodified.
(defsrc
    caps  lalt  ralt  lmet  rmet
    a     s     d     f
    j     k     l     scolon)

;; --- Base Layer ---
(deflayer base
    @caps @la   @ra   lmet  rmet
    @a    @s    @d    @f
    @j    @k    @l    @sc)

;; --- Navigation Layer ---
;; Activated while holding caps (via @caps alias)
(deflayer navigation
    _     _     _     _     _
    _     _     _     _
    left  down  up    right)

;; --- Symbol Layer ---
(deflayer symbols
    _     _     _     _     _
    !     @     \#    $
    %     ^     &     *  )

;; --- Aliases ---
(defalias
    ;; Caps Lock: tap = Escape, hold = Navigation layer
    caps (tap-hold 200 200 esc (layer-while-held navigation))

    ;; Home row mods: tap = letter, hold = modifier
    ;; (tap-hold-release is more precise than tap-hold for fast typists)
    a    (tap-hold-release 200 200 a    lctl)
    s    (tap-hold-release 200 200 s    lalt)
    d    (tap-hold-release 200 200 d    lsft)
    f    (tap-hold-release 200 200 f    lmet)
    j    (tap-hold-release 200 200 j    rmet)
    k    (tap-hold-release 200 200 k    rsft)
    l    (tap-hold-release 200 200 l    ralt)
    sc   (tap-hold-release 200 200 scolon rctl)

    ;; Alt keys: tap = alt, hold = switch to symbols layer
    la   (tap-hold 200 200 lalt (layer-while-held symbols))
    ra   (tap-hold 200 200 ralt (layer-while-held symbols))
)
```

### Advanced kanata Features

kanata supports macros, Unicode output, and sequence-based input:

```scheme
;; Send a Unicode character (requires fcitx5 or ibus for some compositors)
(defalias
    euro  (unicode €)
    copy  C-c
    paste C-v
    snip  (macro lmet lsft s)   ;; Win+Shift+S = screenshot snip
)

;; One-shot modifiers: modifier active only for the next key
(defalias
    os-sft (one-shot 2000 lsft)   ;; Shift active for 2 seconds or next key
    os-ctl (one-shot 2000 lctl)
)

;; Combos: press two keys simultaneously for a third action
(defchords chords-base 50
    (j k) esc          ;; j+k simultaneously = Escape
)

;; Fork: different action depending on which modifiers are held
(defalias
    dot-fork (fork . (shifted >) (lsft rsft))
)
```

### Running kanata as a systemd Service

```ini
# ~/.config/systemd/user/kanata.service
[Unit]
Description=Kanata keyboard remapper
After=local-fs.target

[Service]
Type=simple
ExecStart=/usr/bin/kanata --cfg %h/.config/kanata/kanata.kbd
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
```

```bash
systemctl --user enable --now kanata
systemctl --user status kanata
journalctl --user -u kanata -f    # Live logs
```

If kanata exits with "permission denied on /dev/input/...", your user is not in
the `input` group or uinput is not accessible. See the Troubleshooting section.

---

## 43.4 keyd — System-Level Key Remapper

keyd operates at the kernel level via a dedicated daemon (`keyd`) that intercepts
`/dev/input/` events and creates virtual devices using `uinput`. Unlike kanata,
keyd is oriented toward system-wide simplicity: it is configured in
`/etc/keyd/default.conf` (root-owned), applies to all users and all sessions
including the TTY login prompt, and uses a more readable INI-like syntax.

keyd is ideal when you want remappings that are truly universal — no matter which
user logs in, no matter whether you are in a TTY, SDDM, a Wayland session, or
an X11 session, the remapping is active. This makes it excellent for ergonomic
remappings (Caps Lock to Control/Escape) that you want to be reliable everywhere.

```bash
# Arch Linux (AUR)
yay -S keyd

# Build from source
git clone https://github.com/rvaiya/keyd && cd keyd
make && sudo make install

# Enable and start the daemon
sudo systemctl enable --now keyd
```

### keyd Configuration

```ini
# /etc/keyd/default.conf

[ids]
# Apply to all keyboards (use specific IDs to limit scope)
*

[main]
# Caps Lock: tap = Escape, hold = Control
capslock = overload(control, esc)

# Right Alt as Compose key
rightalt = compose

# Swap Alt and Meta on a specific keyboard
# leftalt = leftmeta
# leftmeta = leftalt

[control]
# Custom Control+key bindings
# (These override system defaults — use carefully)

[meta]
# Windows/Super key overrides
```

### keyd with Per-Device Config

```ini
# /etc/keyd/laptop.conf
# Target only the internal laptop keyboard

[ids]
0001:0001

[main]
capslock = overload(control, esc)
insert = S-insert      # Insert = Shift+Insert (paste in terminal)

[shift]
capslock = capslock    # Shift+Caps = actual Caps Lock
```

```bash
# List device IDs to use in [ids]
sudo keyd -m         # Monitor mode: shows device IDs + events in real time

# Reload config without restart
sudo keyd reload

# Check service status
sudo systemctl status keyd
```

---

## 43.5 xremap — Application-Aware Remapper

xremap adds a capability that kanata and keyd lack: awareness of which
application currently has focus. Using compositor-specific IPC (Hyprland's
socket, Sway's IPC, GNOME's D-Bus), xremap can apply different remapping
layers depending on the focused window's class or title. This is invaluable
for Emacs-style bindings (Control+P/N for navigation) that you want only in
terminals but not in text editors, or browser-specific shortcuts.

```bash
# Arch Linux (AUR)
yay -S xremap-hypr    # Hyprland variant
yay -S xremap-wlroots # Generic wlroots (Sway, river, etc.)

# Or build with compositor feature flag
cargo install xremap --features hypr    # Hyprland
cargo install xremap --features sway    # Sway
cargo install xremap --features wlroots # Generic wlroots
```

### xremap Configuration

xremap uses YAML:

```yaml
# ~/.config/xremap/config.yaml

modmap:
  - name: Global CapsLock remap
    remap:
      CapsLock:
        held: Control_L
        alone: Escape
        alone_timeout_millis: 200

keymap:
  - name: Emacs-style navigation everywhere except Emacs
    application:
      not: [emacs, Emacs]
    remap:
      C-p: Up
      C-n: Down
      C-b: Left
      C-f: Right
      C-a: Home
      C-e: End
      C-d: Delete

  - name: Browser shortcuts
    application:
      only: [firefox, Firefox, chromium, Chromium]
    remap:
      Super-l: C-l      # Super+L = focus address bar
      Super-t: C-t      # Super+T = new tab
      Super-w: C-w      # Super+W = close tab
      Super-r: C-r      # Super+R = reload
```

```bash
# Run xremap in foreground (for testing)
xremap ~/.config/xremap/config.yaml

# systemd user service
systemctl --user enable --now xremap
```

---

## 43.6 Keyboard Layouts with XKB

XKB (X Keyboard Extension) is the standard keyboard layout system on Linux,
used by both X11 and Wayland (via `libxkbcommon`). Wayland compositors use
`libxkbcommon` to interpret keycodes into keysyms, apply layout-level
transformations (shift, AltGr, dead keys), and handle Compose sequences.

Under Wayland, layout configuration goes directly in the compositor config
rather than in `setxkbmap` commands. The XKB model/layout/variant/options
system is identical — only the syntax for specifying them changes.

### Setting Layout in Hyprland

```ini
# ~/.config/hypr/hyprland.conf
input {
    kb_layout = us,de,il        # Comma-separated layout list
    kb_variant = ,nodeadkeys,   # Per-layout variants
    kb_model = pc105
    kb_options = grp:alt_shift_toggle,caps:escape_shifted_capslock,compose:ralt
    kb_rules =
}
```

### Setting Layout in Sway

```
# ~/.config/sway/config
input type:keyboard {
    xkb_layout us,de
    xkb_variant ,nodeadkeys
    xkb_options grp:alt_shift_toggle,caps:escape,compose:ralt
}
```

### Custom XKB Layout

Place custom layouts in `~/.config/xkb/` (user-local, no root needed):

```bash
mkdir -p ~/.config/xkb/symbols
```

```
// ~/.config/xkb/symbols/custom
// A custom layout extending US with extra AltGr mappings

partial alphanumerics
xkb_symbols "custom" {
    include "us"

    // AltGr+e = €, AltGr+p = π, AltGr+d = δ
    key <AE05> { [ 5, percent, EuroSign, onehalf ] };
    key <AD03> { [ e, E, EuroSign, cent ] };
    key <AD10> { [ p, P, Greek_pi, Greek_PI ] };
    key <AC04> { [ f, F, function, partialderivative ] };
};
```

Reference it in your compositor config:

```ini
# Hyprland
input {
    kb_layout = custom
    kb_rules = evdev
}
```

### Compose Key and ~/.XCompose

The Compose key allows typing characters through sequential key combinations.
GTK and Qt apps on Wayland honor `~/.XCompose` via `libxkbcommon`'s compose
table support (GTK requires `GTK_IM_MODULE=` unset or set to `gtk-im-context-simple`).

```bash
# Set compose key to Right Alt in compositor, then use:
# Compose + o + c = ©
# Compose + 1 + 2 = ½
# Compose + ' + e = é

# Custom ~/.XCompose entries
cat >> ~/.XCompose << 'EOF'
include "%L"

<Multi_key> <a> <i>    : "🤖" U1F916  # Compose+a+i = robot emoji
<Multi_key> <s> <h>    : "ℏ"  U210F   # Compose+s+h = h-bar
<Multi_key> <l> <a>    : "λ"  U03BB   # Compose+l+a = lambda
EOF
```

---

## 43.7 Wacom Tablet Configuration

Wacom tablets and other drawing tablets are handled by libinput under Wayland,
which provides basic functionality: pressure sensitivity, tilt, and multi-button
support. For fine-grained control — custom pressure curves, area restrictions,
button remapping — the recommended tool is OpenTabletDriver, which is
compositor-agnostic and offers a GUI configurator.

### OpenTabletDriver Installation

```bash
# Arch Linux (AUR)
yay -S opentabletdriver

# Enable and start the user service
systemctl --user enable --now opentabletdriver

# Open the GUI configurator
otd-gui &
```

### OpenTabletDriver CLI Configuration

```bash
# List detected tablets
otd tablets

# Set tablet area (x y width height in tablet units)
otd area 0 0 15200 9500

# Set absolute positioning mode (recommended for drawing)
otd mode absolute

# Set pointer positioning mode (mouse-like relative movement)
otd mode relative

# Apply a pressure curve (cubic bezier control points)
# Format: x1,y1 x2,y2 — endpoints are implicitly 0,0 and 1,1
otd penSettings --tipPressure "0.1,0.0 0.9,1.0"

# Export current config
otd config > ~/tablet-profile.json

# Import config
otd config < ~/tablet-profile.json
```

### libinput Tablet Calibration (without OpenTabletDriver)

For basic area mapping without OTD:

```bash
# Get the tablet device name
libinput list-devices | grep -A5 -i wacom

# Calibration matrix for area restriction
# Format: [scale_x, 0, offset_x, 0, scale_y, offset_y]
# Restrict to top-left quadrant:
xinput set-prop "Wacom Intuos Pro M Pen" "libinput Calibration Matrix" \
    0.5 0 0 0 0.5 0
```

Note: `xinput` only works under XWayland. For pure Wayland tablet configuration
without OTD, compositor-specific options are limited — OpenTabletDriver is the
robust solution. See Ch 47 for graphics tablet workflows.

---

## 43.8 Mouse Button Remapping

Mouse button remapping under Wayland lacks the convenience of X11's `xbindkeys`
and `xinput` tools, which do not function in pure Wayland sessions. The
available alternatives depend on what you want to achieve.

For compositor-level actions (assigning a side button to "close window" or
"switch workspace"), use your compositor's bind system. For general OS-level
remapping (send different key events when a mouse button is pressed), use kanata
or xremap. For simple button number remapping, evdev-based tools work universally.

### Hyprland Mouse Button Binds

Hyprland's `bindm` directive binds mouse buttons to compositor window
management actions. Button codes use Linux input constants (272=left,
273=right, 274=middle, 275=side, 276=extra).

```ini
# ~/.config/hypr/hyprland.conf

# Hold Super+LMB to drag windows
bindm = SUPER, mouse:272, movewindow

# Hold Super+RMB to resize windows
bindm = SUPER, mouse:273, resizewindow

# Side buttons for workspace switching
bind = , mouse:275, workspace, e-1    # Back button = previous workspace
bind = , mouse:276, workspace, e+1    # Forward button = next workspace

# Extra button to toggle floating
bind = SUPER, mouse:274, togglefloating

# Mouse scroll on title bar to change opacity
bind = SUPER, mouse_down, exec, hyprctl dispatch changeblur 1
```

### Sway Mouse Button Binds

```
# ~/.config/sway/config

# Drag windows by holding Super+LMB
floating_modifier Super normal

# Extra binds
bindsym --to-code button8 workspace prev
bindsym --to-code button9 workspace next
```

### evdev Button Remapping with evdev-remap

`evdev-remap` is a lightweight daemon for remapping mouse buttons at the evdev
level, working on Wayland and TTY:

```bash
# Install
cargo install evdev-remap   # or check AUR: yay -S evdev-remap

# Remap BTN_SIDE (275) to Ctrl+Alt+Left (for back navigation)
evdev-remap /dev/input/event5 \
    --remap BTN_SIDE=KEY_LEFTCTRL,KEY_LEFTALT,KEY_LEFT
```

### kanata for Mouse Buttons

kanata can intercept mouse button events using the `--include-devices` flag.
Add the mouse to `defsrc` with button names `mlft`, `mrgt`, `mmid`, `mbck`, `mfwd`:

```scheme
;; ~/.config/kanata/kanata.kbd (mouse buttons section)

(defsrc
    mlft mrgt mmid mbck mfwd)

(deflayer base
    mlft mrgt mmid
    @back @fwd)

(defalias
    back (macro lalt left)    ;; Side back button = Alt+Left (browser back)
    fwd  (macro lalt right)   ;; Side forward button = Alt+Right (browser forward)
)
```

---

## 43.9 Input Device Debugging with libinput Debug Tools

Beyond `wev`, libinput ships its own debug utilities that operate at the library
level rather than the Wayland protocol level. These tools require read access to
`/dev/input/` (add user to `input` group or run with sudo).

```bash
# List all detected input devices with libinput metadata
sudo libinput list-devices

# Monitor all input events in real time (very verbose)
sudo libinput debug-events

# Monitor specific device
sudo libinput debug-events --device /dev/input/event3

# Filter to specific event types
sudo libinput debug-events | grep -E "POINTER_MOTION|KEYBOARD_KEY"

# Graphical gesture debugger (requires running in a terminal outside Wayland)
sudo libinput debug-gui

# Record events for replay/bug reports
sudo libinput record /dev/input/event3 > recording.yml
sudo libinput replay /dev/input/event3 recording.yml

# Measure pointer acceleration (shows speed vs displacement graph)
sudo libinput measure pointer-acceleration --device /dev/input/event3
```

### Checking libinput Version and Feature Support

```bash
libinput --version

# Check if a tablet device is supported
sudo libinput list-devices | grep -A20 "Wacom\|tablet"

# Check touchpad features detected
sudo libinput list-devices | grep -A30 "Touchpad"
```

---

## 43.10 Gaming Input: Raw Input and High-Precision Mice

Gaming scenarios require flat acceleration, the highest possible poll rate, and
in some cases raw input bypass. Under Wayland, games running natively receive
pointer events through the Wayland relative pointer protocol
(`zwp_relative_pointer_manager_v1`), which delivers raw delta values without
any compositor-side acceleration — provided the compositor respects the protocol
and the game uses it correctly.

For games running under Wine/Proton, raw input is handled through the XWayland
layer or through Wine's own raw input implementation. Performance varies.

```bash
# Check current mouse poll rate (reports events per second)
sudo evhz /dev/input/event0    # Install from AUR: yay -S evhz

# Lock pointer to a Wayland surface for game (wl_pointer.set_cursor trick)
# Games using SDL2, libSDL, or GLFW handle this automatically

# For Wine games, set DXVK environment variables
DXVK_FILTER_DEVICE_NAME="RTX" gamemoderun wine game.exe
```

### Hyprland Game Mode

Hyprland has a built-in game mode that reduces compositor overhead and disables
some effects:

```bash
# Toggle game mode for focused window
hyprctl dispatch setprop address:0x... immediate true 1

# Via hyprland.conf rule
windowrulev2 = immediate, class:^(steam_app)
windowrulev2 = allowsinput, class:^(steam_app)
```

---

## Troubleshooting

### kanata: "Permission denied" on /dev/input/

```bash
# Verify group membership (requires logout to take effect after adding)
groups $USER | grep input

# Temporary workaround without relogin
sudo -g input kanata --cfg ~/.config/kanata/kanata.kbd

# Check uinput permissions
ls -la /dev/uinput
sudo chmod 660 /dev/uinput
sudo chown root:input /dev/uinput

# Permanent udev rule for uinput
echo 'KERNEL=="uinput", GROUP="input", MODE="0660"' | \
    sudo tee /etc/udev/rules.d/99-uinput.rules
sudo udevadm control --reload && sudo udevadm trigger
```

### keyd: Service Fails to Start

```bash
# Check for syntax errors in config
sudo keyd -c /etc/keyd/default.conf --check

# Common issue: [ids] section missing or empty
# Fix: ensure either * or specific device IDs are listed

sudo journalctl -u keyd --no-pager -n 50
```

### Compositor Ignores libinput Settings

If touchpad settings seem to have no effect:

```bash
# Verify the compositor is actually using libinput (not evdev directly)
sudo libinput list-devices    # Device must appear here

# Check that config syntax is correct (no typos in option names)
# For Hyprland, check logs:
cat ~/.local/share/hyprland/hyprland.log | grep -i "input\|libinput\|error"

# For Sway, run in debug mode:
sway -d 2>&1 | grep -i "input"
```

### wev Shows No Events for Specific Keys

If certain keys produce no output in wev:

1. The compositor is consuming the key (check compositor keybinds)
2. The key is suppressed by a remapper daemon (keyd/kanata)
3. The key is on a device wev doesn't have access to (rare)

```bash
# Check compositor keybinds for the missing key
grep -r "caps\|capslock" ~/.config/hypr/    # Hyprland
grep -r "caps\|capslock" ~/.config/sway/    # Sway

# Check if kanata is intercepting it
sudo libinput debug-events | grep -i "caps"
```

### XKB Options Not Applied

```bash
# Test XKB options directly with setxkbmap (works under XWayland)
setxkbmap -option caps:escape

# Verify libxkbcommon can parse your options
xkbcli compile-keymap --layout us --options "caps:escape,compose:ralt"

# Check for typos in option names
localectl list-x11-keymap-options | grep caps
```

### OpenTabletDriver Not Detecting Tablet

```bash
# Check if OTD daemon is running
systemctl --user status opentabletdriver

# Check kernel driver conflict (libwacom/hid-wacom may claim the device)
sudo rmmod hid_wacom  # Temporarily remove competing driver (TEST ONLY)

# Verify udev permissions
ls -la /dev/hidraw*
sudo udevadm info /dev/hidraw0 | grep -E "ID_VENDOR|ID_MODEL"

# OTD diagnostic info
otd detect
```

---

*See also:*
- *Ch 12 — Wayland Architecture: how libinput fits into the compositor stack*
- *Ch 41 — Multi-Monitor, HiDPI, and Fractional Scaling*
- *Ch 45 — Debugging Wayland: WAYLAND_DEBUG, weston-info, wldbg*
- *Ch 47 — Drawing Tablet Workflows: pressure curves and stylus configuration*
- *Ch 53 — Session Startup: autostarting daemons with systemd user services*

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
