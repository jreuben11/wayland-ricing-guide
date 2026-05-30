# Chapter 135 — Multiple Keyboard Layouts and XKB Switching

## Contents

- [Overview](#overview)
- [135.1 XKB Fundamentals](#1351-xkb-fundamentals)
- [135.2 Hyprland](#1352-hyprland)
- [135.3 Sway](#1353-sway)
- [135.4 Niri](#1354-niri)
- [135.5 River](#1355-river)
- [135.6 Waybar Layout Indicator](#1356-waybar-layout-indicator)
  - [Hyprland](#hyprland)
  - [Sway](#sway)
  - [Universal script (River, Niri, any compositor)](#universal-script-river-niri-any-compositor)
- [135.7 Compose Key](#1357-compose-key)
- [135.8 Per-Window Layout (Application-Level)](#1358-per-window-layout-application-level)
- [135.9 Interaction with IME (Fcitx5 / IBus)](#1359-interaction-with-ime-fcitx5-ibus)

---


## Overview

Multi-layout keyboard configuration is a daily need for anyone writing in more than one language, using special characters, or following non-QWERTY conventions. On Wayland, all layout state lives in the compositor via XKB (X Keyboard Extension — kept as the standard despite Wayland's break from X11). This chapter covers per-compositor configuration, keybind switching, Waybar layout indicators, compose key setup, and interaction with input method editors.

**Cross-references:** Ch 43 — input customization (libinput, kanata, keyd). Ch 79 — IME with Fcitx5 and IBus (for CJK and complex scripts). Ch 26 — Waybar (layout indicator module).

## Installation

XKB is built into `libxkbcommon` (always present on Wayland). `localectl` and `busctl` are part of systemd. `fcitx5` requires a separate install for IME support.

```bash
# Arch Linux
sudo pacman -S libxkbcommon   # XKB library (Wayland compositor dependency)
# localectl is part of systemd-utils — already installed
sudo pacman -S fcitx5         # only needed for CJK / IME input (§135.9)

# Nix (nixpkgs)
nix-env -iA nixpkgs.libxkbcommon
nix-env -iA nixpkgs.fcitx5
# home-manager: i18n.inputMethod.enabled = "fcitx5";
```

---

## 135.1 XKB Fundamentals

XKB configuration is a 5-tuple: `layout`, `variant`, `options`, `model`, `rules`.

| Field | Purpose | Example |
|---|---|---|
| `layout` | Comma-separated list of layouts | `us,de,ru` |
| `variant` | Variant per layout (comma-separated) | `colemak,,phonetic` |
| `options` | Modifier/behaviour options | `grp:alt_shift_toggle,caps:escape` |
| `model` | Keyboard hardware model (usually `pc105`) | `pc105` |

Find layout names:
```bash
# List all available layouts
localectl list-x11-keymap-layouts

# List variants for a layout
localectl list-x11-keymap-variants de

# List all XKB options (grouped by prefix)
localectl list-x11-keymap-options | grep "^grp:"
```

Common XKB options:

| Option | Action |
|---|---|
| `grp:alt_shift_toggle` | Left Alt+Shift switches layout |
| `grp:win_space_toggle` | Super+Space switches layout |
| `grp:ctrl_shift_toggle` | Ctrl+Shift switches layout |
| `grp:caps_toggle` | Caps Lock switches layout |
| `grp:lwin_toggle` | Left Super switches layout |
| `caps:escape` | Caps Lock acts as Escape |
| `caps:ctrl_modifier` | Caps Lock acts as Ctrl |
| `compose:ralt` | Right Alt is Compose key |
| `compose:menu` | Menu key is Compose key |
| `terminate:ctrl_alt_bksp` | Ctrl+Alt+Backspace kills compositor |

---

## 135.2 Hyprland

```ini
# ~/.config/hypr/hyprland.conf

input {
    kb_layout  = us,de,ru
    kb_variant = ,nodeadkeys,phonetic
    kb_model   = pc105
    kb_options = grp:alt_shift_toggle,caps:escape
    kb_rules   = evdev

    # Switch layout on a per-window basis (false = global)
    # Hyprland always uses global layout state
}
```

For runtime layout switching:
```bash
# Switch to the next layout group
hyprctl switchxkblayout all next

# Switch to a specific layout by index (0-based)
hyprctl switchxkblayout all 0   # us
hyprctl switchxkblayout all 1   # de
hyprctl switchxkblayout all 2   # ru

# Switch layout on a specific device (get device name first)
hyprctl devices    # shows keyboard device names
hyprctl switchxkblayout "at-translated-set-2-keyboard" next
```

Bind layout switching:
```ini
# In addition to the XKB option (grp:alt_shift_toggle), add explicit binds:
bind = SUPER, SPACE, exec, hyprctl switchxkblayout all next
```

---

## 135.3 Sway

```bash
# ~/.config/sway/config

input "type:keyboard" {
    xkb_layout  "us,de,ru"
    xkb_variant ",nodeadkeys,phonetic"
    xkb_options "grp:alt_shift_toggle,caps:escape"
    xkb_model   "pc105"
}

# Or target a specific device
input "1:1:AT_Translated_Set_2_keyboard" {
    xkb_layout "us,de"
    xkb_options "grp:win_space_toggle"
}
```

```bash
# List input device identifiers
swaymsg -t get_inputs | jq '.[].identifier'

# Switch layout at runtime
swaymsg 'input type:keyboard xkb_switch_layout next'
swaymsg 'input type:keyboard xkb_switch_layout 0'   # first layout

# Bind in config
bindsym $mod+space exec swaymsg 'input type:keyboard xkb_switch_layout next'
```

---

## 135.4 Niri

```kdl
// ~/.config/niri/config.kdl

input {
    keyboard {
        xkb {
            layout "us,ru"
            variant ",phonetic"
            options "grp:alt_shift_toggle,caps:escape"
        }
    }
}
```

Niri doesn't have a runtime layout-switch IPC command as of 0.1.x — the XKB `grp:` options are the primary mechanism.

---

## 135.5 River

```bash
# ~/.config/river/init

# Set layouts for all keyboards
riverctl keyboard-layout-all \
    -variant ",nodeadkeys" \
    -options "grp:alt_shift_toggle,caps:escape" \
    "us,de"

# Or per-device
riverctl keyboard-layout \
    "AT Translated Set 2 keyboard" \
    -options "grp:win_space_toggle" \
    "us,ru"
```

---

## 135.6 Waybar Layout Indicator

### Hyprland

```json
// ~/.config/waybar/config
{
    "hyprland/language": {
        "format": "  {}",
        "format-en": "EN",
        "format-de": "DE",
        "format-ru": "RU",
        "on-click": "hyprctl switchxkblayout all next",
        "tooltip": false
    }
}
```

```css
/* ~/.config/waybar/style.css */
#language {
    color: #7aa2f7;
    font-weight: bold;
    padding: 0 8px;
    border-radius: 4px;
    background: rgba(122,162,247,0.1);
}
```

### Sway

```json
{
    "sway/language": {
        "format": "  {}",
        "on-click": "swaymsg 'input type:keyboard xkb_switch_layout next'"
    }
}
```

### Universal script (River, Niri, any compositor)

For compositors without a Waybar module, use a custom script that reads from `/proc` or `xkbcli`:

```bash
#!/bin/bash
# ~/.local/bin/waybar-xkb-layout
# Reads current layout name via xkbcli or a state file

# Method 1: Use xkbcli info (requires libxkbcommon-tools)
LAYOUT=$(xkbcli interactive-wayland 2>/dev/null | grep "layout" | head -1 | awk '{print $NF}')

# Method 2: Monitor a state file written by a layout-switch script
# Update the file whenever layout changes:
# echo "DE" > /tmp/xkb-layout
cat /tmp/xkb-layout 2>/dev/null || echo "EN"
```

```json
// Waybar custom module
{
    "custom/xkb-layout": {
        "exec": "~/.local/bin/waybar-xkb-layout",
        "interval": 1,
        "format": "  {}",
        "on-click": "~/.local/bin/toggle-layout"
    }
}
```

---

## 135.7 Compose Key

The Compose key allows multi-keystroke special character input without a full IME:

```ini
# ~/.config/hypr/hyprland.conf
input {
    kb_options = compose:ralt   # Right Alt as Compose
}

# ~/.config/sway/config
input "type:keyboard" {
    xkb_options "compose:ralt"
}
```

Usage examples (press Compose, then the sequence):
```
Compose + " + a  → ä  (a umlaut)
Compose + ' + e  → é  (e acute)
Compose + ~ + n  → ñ  (n tilde)
Compose + - + -  → — (em dash... actually: Compose + - + - + - → —)
Compose + < + <  → «  (left guillemet)
Compose + c + o  → ©  (copyright)
Compose + t + m  → ™  (trademark)
Compose + 1 + 2  → ½  (one-half)
```

Custom Compose sequences:
```
# ~/.XCompose
include "%L"   # include system locale sequences

<Multi_key> <w> <l>   : "Wayland"
<Multi_key> <h> <y>   : "Hyprland"
<Multi_key> <period> <period> <period> : "…"
```

---

## 135.8 Per-Window Layout (Application-Level)

XKB on Wayland is global state — all windows share the same layout. There is no compositor-level per-window layout tracking in the Wayland protocol (unlike some X11 IME setups).

**Workaround for per-window layout memory:** Use a script that tracks which window is focused and switches layout:

```python
#!/usr/bin/env python3
# ~/.local/bin/hypr-per-window-layout
# Remembers layout per window class and restores on focus change

import subprocess, json, sys

LAYOUTS = {}   # {window_addr: layout_index}
CURRENT = [0]  # [current_layout_index]

def get_active():
    r = subprocess.run(["hyprctl", "activewindow", "-j"],
                       capture_output=True, text=True)
    return json.loads(r.stdout)

def set_layout(idx):
    subprocess.run(["hyprctl", "switchxkblayout", "all", str(idx)])

def switch():
    win = get_active()
    addr = win.get("address", "")
    new_idx = (LAYOUTS.get(addr, 0) + 1) % 3   # 3 layouts
    LAYOUTS[addr] = new_idx
    set_layout(new_idx)

# Hook into hyprland events for focus change
import socket, os
sock_path = f"/tmp/hypr/{os.environ['HYPRLAND_INSTANCE_SIGNATURE']}/.socket2.sock"
with socket.socket(socket.AF_UNIX) as s:
    s.connect(sock_path)
    buf = ""
    while True:
        data = s.recv(4096).decode()
        buf += data
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            if line.startswith("activewindow>>"):
                addr = line.split(">>")[1].split(",")[0]
                if addr in LAYOUTS:
                    set_layout(LAYOUTS[addr])
```

---

## 135.9 Interaction with IME (Fcitx5 / IBus)

When using Fcitx5 or IBus for CJK input (Ch 79), the IME handles its own layout within a single XKB layout:

- Set XKB to your base Latin layout (`us` or `en`)
- Fcitx5 provides its own toggle (usually Ctrl+Space) for CJK input
- The XKB `grp:` option and Fcitx5 toggle are independent — both can coexist

```ini
# Hyprland — Latin + Fcitx5 CJK
input {
    kb_layout  = us         # base layout (Latin)
    kb_options = caps:escape # no grp: needed; Fcitx5 handles CJK toggle
}
```

For layouts that truly need XKB + IME together (e.g., Japanese romaji + US symbols):
```ini
# Use Fcitx5's XKB integration — set layout inside Fcitx5 config
# ~/.config/fcitx5/config
[Hotkey]
TriggerKeys=Control+space
```
