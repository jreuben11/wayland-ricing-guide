# Chapter 43 — Input Customization: libinput, kanata, keyd, wev

## Overview
Wayland input handling goes through libinput, giving compositors clean access to
all devices. Tools like kanata enable powerful keyboard remapping at the kernel level.

## Sections

### 43.1 libinput Configuration
- libinput: the standard Linux input library, used by all Wayland compositors
- Configuration in compositor config (not xorg.conf)
- Key settings:
  - `accel_profile`: `flat` (no acceleration) / `adaptive` (default)
  - `accel_speed`: -1.0 to 1.0
  - `natural_scroll`: inverted scroll direction
  - `tap-to-click`, `tap-and-drag`
  - `dwt`: disable while typing
  - `click_method`: `buttonareas` / `clickfinger`

#### Hyprland libinput Config
```
input {
    accel_profile = flat
    sensitivity = 0
    natural_scroll = false
    touchpad {
        natural_scroll = true
        tap-to-click = true
        disable_while_typing = true
    }
}
```

#### Sway libinput Config
```
input "1739:0:Synaptics_TM3276-022" {
    accel_profile flat
    tap enabled
    natural_scroll enabled
}
```

### 43.2 wev — Input Event Inspector
- `wev`: Wayland event viewer — shows all input events
- Useful for: finding exact device names, key codes, button numbers
- `wev -f wl_keyboard`: keyboard events only
- `wev -f wl_pointer`: mouse events only
- Essential debugging tool for input remapping

### 43.3 kanata — Powerful Cross-Platform Remapper
- Runs as a daemon, intercepts at `/dev/input/` level (not Wayland-specific)
- Works on Wayland and X11 transparently
- Config: `~/.config/kanata/kanata.kbd`
- Capabilities:
  - Layer system (modal keyboard modes)
  - Tap-hold: key behaves differently on tap vs hold
  - One-shot modifiers
  - Key combos and sequences
  - Macros
  - Unicode output

#### kanata Example
```
(defsrc
    caps lalt ralt)

(deflayer base
    @caps-esc @lalt-met @ralt-met)

(defalias
    caps-esc (tap-hold 150 150 esc (layer-while-held nav))
    lalt-met (tap-hold 150 150 @la met)
    nav      (layer-toggle navigation))

(deflayer navigation
    _ h j k l)
```

### 43.4 keyd — System-Level Key Remapper
- Kernel-level: works before any user-space (works in TTY, Wayland, X11)
- Config: `/etc/keyd/default.conf`
- Simpler than kanata: good for basic remapping
- Caps Lock → Escape/Control depending on use

### 43.5 xremap — X11 and Wayland Remapper
- Similar to kanata but with better Wayland window-context awareness
- Application-specific remapping: different layers per app
- `hyprland` feature: react to Hyprland window focus changes

### 43.6 Keyboard Layouts with XKB
- `setxkbmap` equivalent: compositor `input` block
- Custom XKB layouts in `~/.config/xkb/`
- Compose key sequences: `~/.XCompose` (works on Wayland via GTK)
- Dead keys and accent composition

### 43.7 Wacom Tablet Configuration
- `libinput` handles Wacom tablets
- Area mapping, pressure curves via libinput configuration
- `opentabletdriver`: better alternative for many tablets on Wayland

### 43.8 Mouse Button Remapping
- `libinput` doesn't remap buttons
- `xbindkeys` doesn't work on Wayland
- Alternatives: `ydotool`, `kanata` for button remapping
- Hyprland `bindm`: bind mouse buttons to compositor actions
