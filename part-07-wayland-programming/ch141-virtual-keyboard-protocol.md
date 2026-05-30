# Chapter 141 — Virtual Keyboard Protocol: zwp_virtual_keyboard_v1

## Contents

- [Overview](#overview)
- [141.1 Why X11 Input Injection No Longer Works](#1411-why-x11-input-injection-no-longer-works)
- [141.2 zwp_virtual_keyboard_v1 Protocol](#1412-zwpvirtualkeyboardv1-protocol)
  - [Keymap Upload](#keymap-upload)
- [141.3 wtype — Type Text and Send Keys](#1413-wtype-type-text-and-send-keys)
  - [Common wtype use cases](#common-wtype-use-cases)
- [141.4 ydotool — Kernel-Level Input Injection](#1414-ydotool-kernel-level-input-injection)
- [141.5 kanata — Software Key Remapper](#1415-kanata-software-key-remapper)
  - [Basic kanata configuration](#basic-kanata-configuration)
  - [Layer switching example](#layer-switching-example)
  - [Running kanata as a systemd service](#running-kanata-as-a-systemd-service)
- [141.6 keyd — Kernel-Level Key Remapping](#1416-keyd-kernel-level-key-remapping)
- [141.7 Python: Using the Protocol Directly](#1417-python-using-the-protocol-directly)
- [141.8 Compositor Support Matrix](#1418-compositor-support-matrix)
  - [Debugging virtual keyboard issues](#debugging-virtual-keyboard-issues)

---


## Overview

Programmatic key injection on Wayland is radically different from X11. Under X11,
`xdotool key ctrl+c` worked because any client could send synthetic input events to
the X server. Wayland's security model prohibits this by default: a normal Wayland
client cannot inject input events into another window. The `zwp_virtual_keyboard_v1`
protocol provides a controlled way around this restriction, enabling tools like
`wtype`, `ydotool`, `kanata`, and `keyd` to generate key events as if they came
from a real keyboard. This chapter explains the protocol, its constraints, and
the user-space tools built on top of it.

---

## 141.1 Why X11 Input Injection No Longer Works

Under X11, `XSendEvent` and tools like `xdotool` worked because the X server
provided a shared memory space for events; any client with a connection could
send synthetic events. The Wayland design philosophy is compositor-mediated:
every input event originates at the kernel (via libinput / evdev), passes through
the compositor, and is routed to exactly one focused surface. No client can
intercept or inject into another client's input stream by default.

`xdotool type "hello"` inside an XWayland session still works because XWayland
runs its own X server — but it only affects XWayland windows, not native Wayland
applications.

---

## 141.2 zwp_virtual_keyboard_v1 Protocol

The `zwp_virtual_keyboard_unstable_v1` protocol (stable in practice since wlroots 0.15)
defines two interfaces:

```
zwp_virtual_keyboard_manager_v1
  └─ create_virtual_keyboard(seat, id) → zwp_virtual_keyboard_v1

zwp_virtual_keyboard_v1
  ├─ keymap(format, fd, size)        — send an XKB keymap to the compositor
  ├─ key(time, key, state)           — send a key press/release
  └─ modifiers(mods_depressed,       — update modifier state
               mods_latched,
               mods_locked,
               group)
```

The protocol requires that the virtual keyboard be created on a `wl_seat`. The
compositor may restrict which clients can create virtual keyboards — on most
wlroots compositors (Hyprland, Sway, river) this is allowed for any local
process. Compositor-side policy is configurable.

### Keymap Upload

Before sending keys, the client must upload a keymap that maps key codes to
X keysyms. This is an XKB keymap in `XKB_KEYMAP_FORMAT_TEXT_V1` format,
transferred as a shared memory file descriptor:

```c
// Pseudocode — real implementation uses xkbcommon
struct xkb_context *ctx = xkb_context_new(XKB_CONTEXT_NO_FLAGS);
struct xkb_keymap *map = xkb_keymap_new_from_names(ctx, NULL, 0);
char *keymap_str = xkb_keymap_get_as_string(map, XKB_KEYMAP_FORMAT_TEXT_V1);
// Write keymap_str to a memfd, pass fd to keymap()
```

---

## 141.3 wtype — Type Text and Send Keys

`wtype` is the simplest high-level tool: it wraps `zwp_virtual_keyboard_v1` and
lets you type text or send individual keysyms from the command line.

```bash
# Install
sudo pacman -S wtype
# or: paru -S wtype

# Type a string into the focused window
wtype "Hello, Wayland"

# Send a key combination
wtype -k ctrl+c

# Send modifier + key
wtype -M ctrl -P c    # press Ctrl+C
wtype -m ctrl -p c    # release

# Send keys with delay (ms between keys)
wtype -d 50 "slow typing"

# Type special characters
wtype -s 65     # XKeySym decimal: space (= 0x41 → 'A')
wtype -s 0xff0d # Return
wtype -s 0xff1b # Escape

# Paste clipboard content (pipe to wtype)
wl-paste | wtype -
```

### Common wtype use cases

```bash
# Autofill a password from a password manager
pass show mysite | head -1 | wtype -

# Automate a TUI that expects keyboard input
wtype "q"         # quit many TUI apps
wtype -k Return   # confirm a dialog

# Form fill with tab navigation
wtype "username" -k Tab "password" -k Return
```

---

## 141.4 ydotool — Kernel-Level Input Injection

`ydotool` operates at the kernel level via `uinput` rather than through the
Wayland virtual keyboard protocol. This makes it compositor-independent and
able to inject input even when no Wayland compositor is running, but requires
the `ydotoold` daemon and appropriate permissions.

```bash
# Install
sudo pacman -S ydotool

# Start the daemon (needs uinput access)
sudo systemctl start ydotoold
# Or as user (if you have uinput group membership):
systemctl --user enable --now ydotoold

# Add yourself to the input group for uinput access
sudo usermod -aG input $USER
# Reload: newgrp input  (or re-login)

# Type text
ydotool type "Hello from ydotool"

# Send a key
ydotool key 29:1 46:1 46:0 29:0  # Ctrl+C (press ctrl, press c, release c, release ctrl)

# Use keycodes (evdev codes, not X keysyms)
ydotool key ctrl+c     # shorthand syntax

# Click mouse
ydotool click 0xC0     # left click
ydotool mousemove 100 200
```

**When to use ydotool vs wtype:**
- `wtype`: Wayland-only, simpler, Wayland-aware (respects focus)
- `ydotool`: works in TTY, X11, and Wayland; affects globally, not focus-aware

---

## 141.5 kanata — Software Key Remapper

kanata is a software keyboard remapper that uses `zwp_virtual_keyboard_v1`
(on Wayland) or `uinput` (on Linux bare metal) to intercept physical key events
and re-emit transformed events. It runs as a daemon and handles complex remap
scenarios: tap-hold, layers, combos, macros.

```bash
# Install
paru -S kanata

# Start
kanata --cfg ~/.config/kanata/kanata.kbd
```

### Basic kanata configuration

```lisp
;; ~/.config/kanata/kanata.kbd

(defcfg
  ;; On Wayland, kanata uses virtual keyboard protocol
  ;; Detect input device automatically:
  process-unmapped-keys yes
)

(defsrc
  caps  a  s  d  f  j  k  l  scln
)

(defalias
  ;; Caps Lock → Escape when tapped, Ctrl when held
  cap (tap-hold 200 200 esc lctl)
  
  ;; Home row mods (ASDFJKL;)
  a   (tap-hold-release 200 200 a lmet)
  s   (tap-hold-release 200 200 s lalt)
  d   (tap-hold-release 200 200 d lctl)
  f   (tap-hold-release 200 200 f lsft)
  j   (tap-hold-release 200 200 j rsft)
  k   (tap-hold-release 200 200 k rctl)
  l   (tap-hold-release 200 200 l ralt)
  scl (tap-hold-release 200 200 scln rmet)
)

(deflayer base
  @cap  @a  @s  @d  @f  @j  @k  @l  @scl
)
```

### Layer switching example

```lisp
(defalias
  nav (layer-toggle navigation)
)

(deflayer navigation
  ;;      h     j     k     l
  _  _  _  _  left  down  up  rght  _
)
```

### Running kanata as a systemd service

```ini
# ~/.config/systemd/user/kanata.service
[Unit]
Description=kanata keyboard remapper
After=graphical-session.target

[Service]
ExecStart=/usr/bin/kanata --cfg %h/.config/kanata/kanata.kbd
Restart=on-failure

[Install]
WantedBy=graphical-session.target
```

```bash
systemctl --user enable --now kanata
```

---

## 141.6 keyd — Kernel-Level Key Remapping

keyd operates at the kernel level (before Wayland sees events) using `/dev/uinput`.
It requires root access or a `keyd` system service. Unlike kanata, it intercepts
events at the input layer — useful for remapping even in TTY or before login.

```bash
# Install
sudo pacman -S keyd     # AUR: paru -S keyd

# Enable the system service
sudo systemctl enable --now keyd
```

```ini
# /etc/keyd/default.conf

[ids]
*           # Apply to all keyboards

[main]
# Caps Lock → Escape / Ctrl (dual function)
capslock = overload(control, escape)

# Make Escape also act as Caps Lock when held
# (optional inversion)

[control]
# Ctrl+[ → Escape (Vim-friendly)
[ = escape
```

```bash
# Reload after config change
sudo keyd reload

# Debug: show keynames as you type
sudo keyd monitor
```

---

## 141.7 Python: Using the Protocol Directly

For custom automation, you can drive `zwp_virtual_keyboard_v1` directly with
`pywayland`:

```python
#!/usr/bin/env python3
"""Minimal virtual keyboard: type a string via zwp_virtual_keyboard_v1"""

import os, mmap, time
import xkbcommon.xkb as xkb
from pywayland.client import Display
from pywayland.protocol.wayland import WlSeat
from pywayland.protocol.virtual_keyboard_unstable_v1 import (
    ZwpVirtualKeyboardManagerV1,
)

class VirtualKeyboard:
    def __init__(self):
        self.display = Display()
        self.display.connect()
        self.registry = self.display.get_registry()
        self.seat = None
        self.vk_manager = None
        self.vk = None

        self.registry.dispatcher["global"] = self._handle_global
        self.display.dispatch(block=True)
        self.display.roundtrip()

        ctx = xkb.Context()
        keymap = ctx.keymap_new_from_names()
        keymap_str = keymap.get_as_string()
        keymap_bytes = keymap_str.encode()

        # Upload keymap via shared memory
        fd = os.memfd_create("keymap", 0)
        os.ftruncate(fd, len(keymap_bytes))
        mm = mmap.mmap(fd, len(keymap_bytes))
        mm.write(keymap_bytes)
        mm.seek(0)

        self.vk.keymap(1, fd, len(keymap_bytes))  # format=XKB_TEXT_V1
        self.display.roundtrip()
        os.close(fd)

        self._keymap = keymap

    def _handle_global(self, registry, name, interface, version):
        if interface == "wl_seat":
            self.seat = registry.bind(name, WlSeat, version)
        elif interface == "zwp_virtual_keyboard_manager_v1":
            self.vk_manager = registry.bind(name, ZwpVirtualKeyboardManagerV1, version)
            if self.seat:
                self.vk = self.vk_manager.create_virtual_keyboard(self.seat)

    def send_key(self, keycode: int, pressed: bool):
        """Send a key event. keycode is evdev scancode - 8 (XKB offset)."""
        state = 1 if pressed else 0
        t = int(time.monotonic() * 1000)
        self.vk.key(t, keycode, state)
        self.display.flush()

    def type_char(self, char: str):
        """Type a single character using the active keymap."""
        keysym = xkb.keysym_from_name(char)
        key = self._keymap.key_by_name(char)
        if key:
            self.send_key(key - 8, True)
            time.sleep(0.02)
            self.send_key(key - 8, False)

if __name__ == "__main__":
    vk = VirtualKeyboard()
    for ch in "hello wayland\n":
        vk.type_char(ch)
        time.sleep(0.05)
```

---

## 141.8 Compositor Support Matrix

| Compositor | Virtual keyboard support | Notes |
|---|---|---|
| **Hyprland** | Yes | Full zwp_virtual_keyboard_v1 |
| **Sway** | Yes | Full support |
| **river** | Yes | Full support |
| **niri** | Yes | Full support |
| **KWin/KDE** | Yes (limited) | Via KWin virtual input plugin |
| **GNOME Mutter** | No | Blocked for security; use AT-SPI instead |
| **Weston** | Yes | Reference implementation |

### Debugging virtual keyboard issues

```bash
# Check if the protocol is advertised by your compositor
wayland-info 2>/dev/null | grep virtual_keyboard
# or:
WAYLAND_DEBUG=1 wtype "test" 2>&1 | grep "virtual_keyboard"

# Check ydotoold is running (for ydotool)
systemctl --user status ydotoold

# Check kanata can open the input device
journalctl --user -u kanata --since "1 minute ago"
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
