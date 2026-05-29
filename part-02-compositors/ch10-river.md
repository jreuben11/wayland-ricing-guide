# Chapter 10 — River: Tag-Based Minimalism

## Overview

River is a dynamic Wayland compositor written in Zig that embodies the Unix philosophy more
thoroughly than any of its peers. Where Sway wraps i3's ideology in a Wayland shell and
Hyprland chases desktop-environment levels of feature completeness, River draws a hard line:
the compositor manages rendering, input, and IPC; everything else — layout, status, even
keyboard-shortcut philosophy — is delegated to external programs communicating over
well-defined Wayland protocols.

This design makes River simultaneously the most spartan and the most composable compositor
covered in this book. A working River session requires at least one external layout generator
and a startup script, but the ceiling for customisation is essentially unlimited: layouts are
arbitrary programs, and River's IPC surface is a wayland protocol rather than a domain-
specific language, so any language that can open a Wayland socket can control it.

The audience for River is the power user who has already worn out several tiling compositors
and wants to own the entire stack. If that sounds like you, this chapter will reward careful
reading. If you are looking for sane defaults out of the box, consider Sway (Ch 08) or
niri (Ch 11) first and return here when you're ready.

> Cross-reference: Session startup automation is covered in Ch 53. Status bars
> (Waybar, eww, yambar) are covered in Part 04. Theming GTK and Qt apps is in Part 05.

---

## 10.1 Philosophy: The River Way

River inherits its conceptual DNA directly from dwm, the suckless window manager for X11.
The central idea is that windows carry a set of *tags* (bit-flags) rather than being
assigned to exactly one numbered workspace. A tag is like a label; a window can carry
multiple tags, and the user focuses a *set* of tags rather than a single workspace. This
unlocks combinations that workspace-based compositors make awkward: show all terminals
plus the browser, hide everything except the reference document you're annotating, or
display your editor on the left monitor while terminals float across both monitors.

The second pillar is the external layout generator model. River implements the
`river-layout-v3` Wayland protocol extension. A layout generator is simply a process that
listens on this protocol namespace, receives notifications about the size of the output and
the number of windows to arrange, and replies with a list of `(x, y, width, height)` tuples
— one per window. Because this is a regular Wayland protocol message exchange, the layout
generator can be written in any language that has a Wayland client library: C, Zig, Rust,
Python, or even shell via `wl-msg`. This decoupling means River never needs a built-in
tiling algorithm: users swap, patch, or rewrite layout generators without touching the
compositor.

The third pillar is `riverctl`, a CLI tool that is the sole configuration surface for the
compositor. There is no config file format to parse, no embedded Lua interpreter, no
declarative schema. Instead, your `~/.config/river/init` is an executable shell script
(or any executable) that calls `riverctl` repeatedly to register keybindings, set options,
and spawn programs. If you want to change a setting at runtime you run `riverctl` again —
from a terminal, a keybinding, or a D-Bus triggered script. This uniformity means the
same commands you type to experiment interactively are exactly what you put in the init
script, with zero translation layer.

Configuration is therefore explicit. River ships with no default keybindings. A fresh
River session on a bare system is a black screen with a cursor. This is intentional: the
compositor makes no assumptions about your preferred terminal emulator, application
launcher, or modifier key. The worked example init script in section 10.4 is a solid
starting point, and the upstream `example/` directory in the River repository is the
canonical reference.

---

## 10.2 Installation and Setup

### Building from Source

River is written in Zig, which means you need a compatible Zig toolchain. The River project
follows Zig's release cadence closely; as of River 0.4.x the required Zig version is tracked
in the repository's `build.zig.zon`. Always check the `README` for the exact version before
building — mismatched Zig versions produce cryptic compilation errors.

```bash
# Install Zig via the official tarball (replace version as needed)
ZIG_VERSION=0.13.0
curl -L "https://ziglang.org/download/${ZIG_VERSION}/zig-linux-x86_64-${ZIG_VERSION}.tar.xz" \
  | tar -xJ -C ~/.local/share/
echo 'export PATH="$HOME/.local/share/zig-linux-x86_64-'"${ZIG_VERSION}"':$PATH"' \
  >> ~/.zshrc
source ~/.zshrc
zig version   # should print 0.13.0

# Runtime dependencies (Debian/Ubuntu)
sudo apt install \
  libwayland-dev wayland-protocols \
  libwlroots-dev \
  libxkbcommon-dev \
  pkg-config cmake meson ninja-build

# Clone and build River
git clone https://codeberg.org/river/river.git
cd river
zig build -Doptimize=ReleaseSafe
sudo zig build -Doptimize=ReleaseSafe install --prefix /usr/local
```

On Arch Linux, River is in the official `extra` repository and the AUR hosts git builds:

```bash
# Stable release
sudo pacman -S river

# Latest git build (AUR)
paru -S river-git
```

On Fedora/RHEL derivatives:

```bash
sudo dnf install river
```

### Verify the Installation

```bash
which river        # /usr/local/bin/river or /usr/bin/river
which riverctl     # should be in the same prefix
river --version    # e.g. river 0.4.0
```

### The Init Script

River reads `$XDG_CONFIG_HOME/river/init` (defaults to `~/.config/river/init`) at startup.
The file must be executable. River executes it as a subprocess; the init process can be any
executable — a shell script, a compiled binary, a Python script — as long as it calls
`riverctl` commands (directly or via exec). River does not wait for the init process to
exit; commands are dispatched as fast as the compositor can process IPC messages.

```bash
mkdir -p ~/.config/river
touch ~/.config/river/init
chmod +x ~/.config/river/init
```

A minimal sanity-check init that just spawns a terminal:

```bash
#!/bin/sh
riverctl spawn foot
```

### Starting River

From a TTY (recommended for reproducibility):

```bash
river
```

From a display manager such as greetd + tuigreet, create a session file:

```ini
# /usr/local/share/wayland-sessions/river.desktop
[Desktop Entry]
Name=River
Comment=A dynamic Wayland compositor
Exec=river
Type=Application
```

To pass environment variables or perform pre-launch setup, wrap River in a script:

```bash
#!/bin/sh
# /usr/local/bin/start-river
export MOZ_ENABLE_WAYLAND=1
export QT_QPA_PLATFORM=wayland
export SDL_VIDEODRIVER=wayland
export _JAVA_AWT_WM_NONREPARENTING=1
exec river
```

See Ch 53 for integrating River with systemd user sessions and for `river.service`
unit file patterns that ensure D-Bus activation and XDG portal startup.

---

## 10.3 The Tag System

### Tags as Bit-Flags

River provides 32 tags per output, numbered 1 through 32. Internally they are represented
as a 32-bit unsigned integer where bit N corresponds to tag N+1. This means:

| Human label | Bit position | Decimal value | Hex    |
|-------------|-------------|---------------|--------|
| Tag 1       | bit 0       | 1             | 0x0001 |
| Tag 2       | bit 1       | 2             | 0x0002 |
| Tag 3       | bit 2       | 4             | 0x0004 |
| Tags 1+2    | bits 0-1    | 3             | 0x0003 |
| All tags    | bits 0-31   | 4294967295    | 0xFFFF |

Every view (window) has a tag set. Every output has a *focused tags* set. A window is
visible on an output if and only if the bitwise AND of its tag set and the output's focused
tag set is non-zero. Assigning a window to multiple tags means it appears whenever any of
those tags is focused. This is the key difference from workspaces: a window can be
simultaneously "in" the terminal workspace and the reference workspace.

### Assigning and Focusing Tags

`riverctl` uses decimal integers for tag arguments:

```bash
# Focus tag 1 (show only windows tagged with tag 1)
riverctl set-focused-tags 1

# Focus tags 1 and 3 simultaneously
riverctl set-focused-tags $(( (1 << 0) | (1 << 2) ))   # = 5

# Assign the focused view to tag 2
riverctl set-view-tags 2

# Toggle tag 3 in the focused-tags set (show/hide tag-3 windows)
riverctl toggle-focused-tags 4   # 4 = 1 << 2

# Toggle tag 2 on the focused view (add/remove without changing other tags)
riverctl toggle-view-tags 2
```

### Keybindings for a Full Tag Workflow

The following snippet (from the init script) wires Super+1..9 to focus tags and
Super+Shift+1..9 to assign the focused window to a tag — the classic dwm-style layout:

```bash
#!/bin/sh

# Tags 1-9: focus and assign
for i in $(seq 1 9); do
    tags=$(( 1 << (i - 1) ))
    # Super+N: focus tag N
    riverctl map normal Super "$i" set-focused-tags $tags
    # Super+Shift+N: assign focused view to tag N
    riverctl map normal Super+Shift "$i" set-view-tags $tags
    # Super+Control+N: toggle tag N in focused-tags
    riverctl map normal Super+Control "$i" toggle-focused-tags $tags
    # Super+Shift+Control+N: toggle tag N on focused view
    riverctl map normal Super+Shift+Control "$i" toggle-view-tags $tags
done

# Super+0: focus all tags
riverctl map normal Super 0 set-focused-tags $(( (1 << 32) - 1 ))
# Super+Shift+0: assign focused view to all tags (sticky window)
riverctl map normal Super+Shift 0 set-view-tags $(( (1 << 32) - 1 ))
```

### Comparison: River Tags vs. i3/Sway Workspaces

| Feature                         | River tags           | Sway/i3 workspaces         |
|---------------------------------|----------------------|----------------------------|
| Window on multiple spaces       | Yes (multi-tag)      | No (one workspace only)    |
| Simultaneous multi-space view   | Yes (tag union)      | No                         |
| Named spaces                    | No (numeric only)    | Yes (arbitrary names)      |
| Per-output independent sets     | Yes                  | Yes                        |
| Scratchpad / floating scratch   | Float + hidden tag   | Native scratchpad           |
| Maximum spaces                  | 32 per output        | Unlimited                  |

The main trade-off is discoverability: i3/Sway display workspace names in the bar which
makes it obvious where things are. With River tags, status bar integration (section 10.6)
is necessary to see which tags are occupied and which is focused.

---

## 10.4 Configuration via `riverctl`

### Keybindings

`riverctl map` registers a keybinding. The general form is:

```
riverctl map <mode> <modifiers> <key> <action> [<args>...]
```

`<mode>` is typically `normal` (the default mode). River supports modal operation: you can
create custom modes with `riverctl declare-mode` and switch between them, enabling Vim-
style modal keybinding layers. `<modifiers>` is a `+`-separated list of `Super`, `Shift`,
`Control`, `Alt`, `Mod5`, etc. `<key>` is an XKB keysym name (e.g., `Return`, `space`, `h`).

```bash
# Terminal
riverctl map normal Super Return spawn foot

# Application launcher (wofi)
riverctl map normal Super D spawn "wofi --show drun"

# Close focused view
riverctl map normal Super+Shift Q close

# Focus next/previous view
riverctl map normal Super J focus-view next
riverctl map normal Super K focus-view previous

# Swap focused view with next/previous in layout
riverctl map normal Super+Shift J swap next
riverctl map normal Super+Shift K swap previous

# Move focused view to previous/next output
riverctl map normal Super+Shift Period send-to-output next
riverctl map normal Super+Shift Comma send-to-output previous

# Toggle float on focused view
riverctl map normal Super+Shift Space toggle-float

# Toggle fullscreen
riverctl map normal Super F toggle-fullscreen

# Quit River
riverctl map normal Super+Shift E exit
```

### Pointer Bindings (Mouse)

```bash
# Super + left click: move float
riverctl map-pointer normal Super BTN_LEFT move-view
# Super + right click: resize float
riverctl map-pointer normal Super BTN_RIGHT resize-view
# Super + middle click: toggle float
riverctl map-pointer normal Super BTN_MIDDLE toggle-float
```

### Keyboard Repeat and XKB

```bash
# Key repeat: 50 ms delay, 300 cps
riverctl set-repeat 300 50

# XKB: layout, options, variant
riverctl keyboard-layout -options "caps:escape,compose:ralt" us
```

For multi-layout setups (e.g., us + de with Super+Space to toggle):

```bash
riverctl keyboard-layout -options "grp:win_space_toggle" "us,de"
```

### Input Configuration (libinput)

`riverctl input` targets a specific device. List your devices with:

```bash
riverctl list-inputs
```

Then configure by the device identifier reported:

```bash
TOUCHPAD="pointer-1234-5678-SynPS/2_Synaptics_TouchPad"
riverctl input "$TOUCHPAD" tap enabled
riverctl input "$TOUCHPAD" natural-scroll enabled
riverctl input "$TOUCHPAD" accel-profile flat
riverctl input "$TOUCHPAD" pointer-accel 0.3
riverctl input "$TOUCHPAD" disable-while-typing enabled
riverctl input "$TOUCHPAD" tap-button-map left-right-middle

MOUSE="pointer-1234-abcd-Logitech_G502"
riverctl input "$MOUSE" accel-profile flat
riverctl input "$MOUSE" pointer-accel 0.0
```

### Window Rules

`riverctl rule-add` applies compositor-level rules to windows identified by
`app-id` (Wayland) or `title` globs. Rules fire when a view is mapped.

```bash
# Float specific apps
riverctl rule-add -app-id "pavucontrol"  float
riverctl rule-add -app-id "nm-connection-editor" float
riverctl rule-add -title "Picture-in-Picture" float

# Assign specific apps to tags on map
riverctl rule-add -app-id "org.mozilla.firefox" tags 2   # tag 2 = bit 1
riverctl rule-add -app-id "discord" tags 8               # tag 4 = bit 3
riverctl rule-add -app-id "Spotify" tags 16              # tag 5 = bit 4

# CSD / SSD control
riverctl rule-add -app-id "foot" ssd
```

### Output Configuration

```bash
# Set primary output mode (requires wlr-output-management or kanshi for persistence)
# Direct riverctl output config is done via wlr-output-management protocol tools

# Preferred: use kanshi for declarative output management (see Ch 52)
# Quick override in init:
riverctl spawn "wlr-randr --output DP-1 --mode 2560x1440@165Hz --pos 0,0 \
  --output HDMI-A-1 --mode 1920x1080@60Hz --pos 2560,180"
```

---

## 10.5 Layout Generators

### rivertile: The Built-In Generator

`rivertile` is the reference layout generator bundled with River. It implements a
classic master-stack layout: N windows in the "main" pane on one edge, the rest in a
stack on the opposite edge. It is sparse but complete.

Start rivertile in the init script:

```bash
riverctl default-layout rivertile
rivertile -view-padding 6 -outer-padding 6 &
```

Configure rivertile via keybindings:

```bash
# Move the main area between edges
riverctl map normal Super+Alt H send-layout-cmd rivertile "main-location left"
riverctl map normal Super+Alt L send-layout-cmd rivertile "main-location right"
riverctl map normal Super+Alt K send-layout-cmd rivertile "main-location top"
riverctl map normal Super+Alt J send-layout-cmd rivertile "main-location bottom"

# Adjust number of main views
riverctl map normal Super+Shift H send-layout-cmd rivertile "main-count +1"
riverctl map normal Super+Shift L send-layout-cmd rivertile "main-count -1"

# Adjust main ratio (proportion of screen given to main area)
riverctl map normal Super H send-layout-cmd rivertile "main-ratio -0.05"
riverctl map normal Super L send-layout-cmd rivertile "main-ratio +0.05"
```

### External Layout Generators

The community has produced a rich ecosystem of layout generators. Here is a comparison:

| Generator        | Algorithm              | Language | Notable features                      |
|------------------|------------------------|----------|---------------------------------------|
| rivertile        | Master-stack           | Zig      | Built-in, minimal                     |
| stacktile        | Multi-stack            | Zig      | Multiple configurable stacks          |
| river-bsp-layout | BSP binary-space-part. | Python   | Auto-splits like bspwm                |
| kile             | Multi-layout suite     | Zig      | Tab, grid, full, deck, recursive      |
| rivercarro       | Column-based           | Rust     | Inspired by PaperWM, scrollable cols  |
| luatile          | Lua-scriptable         | Lua/C    | Arbitrary layouts in Lua              |

Installing `kile` (AUR / from source):

```bash
git clone https://github.com/nicolo-ribaudo/kile.git
cd kile
zig build -Doptimize=ReleaseSafe
sudo zig build install --prefix /usr/local
```

Using `kile` in init:

```bash
riverctl default-layout kile
kile &

# Switch layout modes
riverctl map normal Super+Alt T send-layout-cmd kile "layout_mode tile"
riverctl map normal Super+Alt G send-layout-cmd kile "layout_mode grid"
riverctl map normal Super+Alt F send-layout-cmd kile "layout_mode full"
riverctl map normal Super+Alt D send-layout-cmd kile "layout_mode deck"
```

Installing `rivercarro`:

```bash
cargo install rivercarro
```

Using `rivercarro`:

```bash
riverctl default-layout rivercarro
rivercarro &

riverctl map normal Super+Alt H send-layout-cmd rivercarro "main-location left"
riverctl map normal Super+Alt L send-layout-cmd rivercarro "main-location right"
riverctl map normal Super H      send-layout-cmd rivercarro "main-ratio -0.05"
riverctl map normal Super L      send-layout-cmd rivercarro "main-ratio +0.05"
```

### Writing a Custom Layout Generator

The `river-layout-v3` protocol is documented in River's source under
`protocol/river-layout-v3.xml`. A layout generator must:

1. Connect to the Wayland display.
2. Bind the `river_layout_manager_v3` global.
3. Receive `layout_demand` events (containing output dimensions and view count).
4. Reply with `push_view_dimensions` for each view, then `commit`.

A minimal Python example using `pywayland`:

```python
#!/usr/bin/env python3
"""Minimal River layout generator: always tiles views vertically."""
import sys
from pywayland.client import Display
from pywayland.protocol.river_layout_v3 import RiverLayoutManagerV3

def handle_layout_demand(layout, view_count, usable_w, usable_h, tags, serial):
    if view_count == 0:
        layout.commit("columns", serial)
        return
    h = usable_h // view_count
    for i in range(view_count):
        layout.push_view_dimensions(0, i * h, usable_w, h, serial)
    layout.commit("columns", serial)

display = Display()
display.connect()
registry = display.get_registry()
layout_manager = None

@registry.dispatcher["global"]
def handle_global(registry, name, interface, version):
    global layout_manager
    if interface == "river_layout_manager_v3":
        layout_manager = registry.bind(name, RiverLayoutManagerV3, version)

display.roundtrip()
assert layout_manager, "river_layout_manager_v3 not available"

output = None  # In production: enumerate wl_outputs and create a layout per output
layout = layout_manager.get_layout(output, "columns")
layout.dispatcher["layout_demand"] = handle_layout_demand

while display.dispatch() != -1:
    pass
```

For production use, consult the `river-layout-v3` XML spec and reference implementation
in C from `river-bsp-layout`. The Zig bindings in River's own `rivertile` source are also
exemplary.

---

## 10.6 Scripting River

### Status Bar Integration via Wayland Protocol

River implements `river-status-unstable-v1`, which provides per-output and per-seat
status events: which tags are focused, which tags are occupied (have at least one view),
the title of the focused view, and the current mode. Status bars use this protocol to
render River-aware widgets.

### Waybar River Module

Waybar ships a first-class `river/tags` module. Example configuration:

```jsonc
// ~/.config/waybar/config
{
  "layer": "top",
  "position": "top",
  "modules-left": ["river/tags", "river/mode"],
  "modules-center": ["river/window"],
  "modules-right": ["pulseaudio", "network", "clock"],

  "river/tags": {
    "num-tags": 9,
    "tag-labels": ["1", "2", "3", "4", "5", "6", "7", "8", "9"],
    "set-tags": [1, 2, 4, 8, 16, 32, 64, 128, 256]
  },

  "river/mode": {
    "format": "<span style='italic'>{}</span>"
  },

  "river/window": {
    "max-length": 80
  }
}
```

Corresponding Waybar style for River tag states:

```css
/* ~/.config/waybar/style.css */
#tags button {
    padding: 0 6px;
    color: #888888;
}
#tags button.occupied {
    color: #cccccc;
}
#tags button.focused {
    color: #ffffff;
    background-color: #444466;
    border-bottom: 2px solid #8888ff;
}
#tags button.urgent {
    color: #ff6666;
}
#mode {
    color: #ffaa00;
    font-style: italic;
    padding: 0 8px;
}
```

Start Waybar from the River init script:

```bash
riverctl spawn "waybar"
```

### yambar River Module

If you prefer yambar (a simpler bar with a clean YAML config):

```yaml
# ~/.config/yambar/config.yml
bar:
  location: top
  background: 1a1a2eff
  font: "JetBrainsMono Nerd Font:size=12"

  left:
    - river:
        anchors:
          - occupied: &occupied {foreground: cccccfff}
          - focused:  &focused  {foreground: 8888ffff, deco: {underline: {size: 2, color: 8888ffff}}}
          - urgent:   &urgent   {foreground: ff6666ff}
        content:
          tags:
            map:
              conditions:
                state == occupied: {string: {text: "{id}", <<: *occupied}}
                state == focused:  {string: {text: "{id}", <<: *focused}}
                state == urgent:   {string: {text: "{id}", <<: *urgent}}
                ~: {empty: {}}
```

### Event-Driven Scripting with `riverctl`

Because `riverctl` is a CLI, you can hook it into any event-driven framework. For example,
using `inotifywait` to reload config on file change during development:

```bash
#!/bin/sh
# reload-on-change.sh — re-run the init script when it is saved
inotifywait -m -e close_write ~/.config/river/init | while read; do
    ~/.config/river/init
done
```

A more robust approach uses `systemd --user` path units:

```ini
# ~/.config/systemd/user/river-init-watch.path
[Path]
PathModified=%h/.config/river/init

[Install]
WantedBy=default.target
```

```ini
# ~/.config/systemd/user/river-init-watch.service
[Service]
ExecStart=%h/.config/river/init
```

```bash
systemctl --user enable --now river-init-watch.path
```

### Modal Keybindings

River supports custom modes, enabling Vim-style layers:

```bash
# Declare a "resize" mode
riverctl declare-mode resize

# In normal mode: Super+R enters resize mode
riverctl map normal Super R enter-mode resize

# In resize mode: h/j/k/l resize the focused float
riverctl map resize None H resize-view horizontal -20
riverctl map resize None L resize-view horizontal  20
riverctl map resize None K resize-view vertical   -20
riverctl map resize None J resize-view vertical    20

# Return to normal with Escape or Enter
riverctl map resize None Escape enter-mode normal
riverctl map resize None Return enter-mode normal
```

---

## 10.7 A Complete Init Script

The following is a production-quality `~/.config/river/init` suitable as a starting point:

```bash
#!/bin/sh
# River init script — edit to taste

## --- Appearance ---
riverctl background-color 0x1a1a2e
riverctl border-color-focused 0x8888ff
riverctl border-color-unfocused 0x444466
riverctl border-color-urgent 0xff6666
riverctl border-width 2
riverctl focus-follows-cursor normal

## --- Keyboard ---
riverctl set-repeat 300 50
riverctl keyboard-layout -options "caps:escape,compose:ralt" us

## --- Input ---
TOUCHPAD=$(riverctl list-inputs 2>/dev/null | grep -i touchpad | head -1)
if [ -n "$TOUCHPAD" ]; then
    riverctl input "$TOUCHPAD" tap enabled
    riverctl input "$TOUCHPAD" natural-scroll enabled
    riverctl input "$TOUCHPAD" disable-while-typing enabled
    riverctl input "$TOUCHPAD" accel-profile flat
fi

## --- Core keybindings ---
riverctl map normal Super Return spawn foot
riverctl map normal Super D      spawn "wofi --show drun"
riverctl map normal Super+Shift Q close
riverctl map normal Super+Shift E exit

riverctl map normal Super J focus-view next
riverctl map normal Super K focus-view previous
riverctl map normal Super+Shift J swap next
riverctl map normal Super+Shift K swap previous

riverctl map normal Super Period  focus-output next
riverctl map normal Super Comma   focus-output previous
riverctl map normal Super+Shift Period send-to-output next
riverctl map normal Super+Shift Comma  send-to-output previous

riverctl map normal Super H send-layout-cmd rivertile "main-ratio -0.05"
riverctl map normal Super L send-layout-cmd rivertile "main-ratio +0.05"
riverctl map normal Super+Shift H send-layout-cmd rivertile "main-count +1"
riverctl map normal Super+Shift L send-layout-cmd rivertile "main-count -1"

riverctl map normal Super+Alt H send-layout-cmd rivertile "main-location left"
riverctl map normal Super+Alt L send-layout-cmd rivertile "main-location right"
riverctl map normal Super+Alt K send-layout-cmd rivertile "main-location top"
riverctl map normal Super+Alt J send-layout-cmd rivertile "main-location bottom"

riverctl map normal Super+Shift Space toggle-float
riverctl map normal Super F           toggle-fullscreen
riverctl map normal Super+Shift F     send-layout-cmd rivertile "main-location monocle" 2>/dev/null

## --- Pointer bindings ---
riverctl map-pointer normal Super BTN_LEFT  move-view
riverctl map-pointer normal Super BTN_RIGHT resize-view

## --- Tags 1-9 ---
for i in $(seq 1 9); do
    tags=$(( 1 << (i - 1) ))
    riverctl map normal Super          "$i" set-focused-tags $tags
    riverctl map normal Super+Shift    "$i" set-view-tags $tags
    riverctl map normal Super+Control  "$i" toggle-focused-tags $tags
    riverctl map normal Super+Shift+Control "$i" toggle-view-tags $tags
done
all_tags=$(( (1 << 32) - 1 ))
riverctl map normal Super          0 set-focused-tags $all_tags
riverctl map normal Super+Shift    0 set-view-tags $all_tags

## --- Window rules ---
riverctl rule-add -app-id "pavucontrol"            float
riverctl rule-add -app-id "nm-connection-editor"   float
riverctl rule-add -title  "Picture-in-Picture"     float
riverctl rule-add -app-id "org.mozilla.firefox"    tags 2
riverctl rule-add -app-id "discord"                tags 8

## --- Layout ---
riverctl default-layout rivertile
rivertile -view-padding 6 -outer-padding 6 &

## --- Autostart ---
riverctl spawn "waybar"
riverctl spawn "mako"
riverctl spawn "wl-paste --type text --watch cliphist store"
riverctl spawn "wl-paste --type image --watch cliphist store"
riverctl spawn "swayidle -w \
  timeout 300 'swaylock -f -c 000000' \
  timeout 600 'wlopm --off \\*' \
  resume 'wlopm --on \\*' \
  before-sleep 'swaylock -f -c 000000'"
```

---

## 10.8 River in 2025/2026

### Stability and Feature Completeness

River reached 0.4.0 in 2024 and is considered production-stable for daily use. The API
surface (both `riverctl` and the Wayland protocol extensions) is versioned and breaking
changes are announced in advance. The `river-layout-v3` protocol is stable. The
`river-status-unstable-v1` and `river-control-unstable-v1` protocols are mature but carry
the `-unstable-` suffix per Wayland convention while the upstream `xdg-wm-base` replacement
discussions proceed.

Notable recent additions include fractional scaling support (via `wp-fractional-scale-v1`),
improved multi-monitor handling, and first-class `xwayland-satellite` support for XWayland
without embedding it in the compositor process. River delegates XWayland to `xwayland-
satellite`, keeping the compositor itself X11-free — a cleaner architecture than Sway's
embedded XWayland.

### Community Size vs. Hyprland/Sway

River occupies a deliberate niche. It does not compete with Hyprland on eye-candy or
Sway on out-of-the-box ergonomics. Its community is smaller but technically deep: users
tend to write their own layout generators, contribute protocol extensions, and publish
detailed configuration articles. The Codeberg issues tracker and the IRC channel
`#river` on Libera.Chat are the primary support venues.

| Compositor  | GitHub Stars (2025) | Config language  | XWayland  | Default layout  |
|-------------|---------------------|------------------|-----------|-----------------|
| Sway        | ~15k                | sway-config DSL  | Embedded  | i3-compatible   |
| Hyprland    | ~22k                | Hyprland DSL     | Embedded  | Dynamic tiling  |
| River       | ~4k                 | Shell + riverctl | Satellite | None (external) |
| niri        | ~8k                 | KDL              | Satellite | Scrolling cols  |

### Use Cases Where River Shines

River is the right tool when:

- You want total control over layout without learning a compositor-specific language.
  Your layout generator is a program in your favourite language.
- You do serious keyboard-driven work and want 32 tags per monitor with multi-tag views.
- You want to minimise the compositor's attack surface (no embedded XWayland, no
  scripting engine, no built-in bar protocol).
- You are building tools that need to query or control the compositor from external
  programs: `riverctl` provides a uniform IPC CLI that is easily scripted.
- You appreciate reading the full source of your compositor in a weekend. River's core is
  under 15k lines of Zig.

River is the wrong tool when:

- You want animations, blur, rounded corners, or other visual effects (use Hyprland).
- You want workspace names, scratchpads, and per-workspace layouts without writing code
  (use Sway).
- You want a scrollable, paper-like layout out of the box (use niri, Ch 11).

> Cross-reference: For comparing all compositors covered in Part 02 side-by-side, see
> the Compositor Comparison Table in Ch 15. For XWayland configuration with
> xwayland-satellite, see Ch 48.

---

## Troubleshooting

### River starts but the screen is black and nothing responds

The init script either did not execute or exited before calling `riverctl`. Check that:

```bash
ls -la ~/.config/river/init   # must show -rwxr-xr-x
head -1 ~/.config/river/init  # must be a valid shebang: #!/bin/sh
```

Run River with verbose logging to see init errors:

```bash
RIVER_LOG=debug river 2>&1 | tee /tmp/river-debug.log
```

### `riverctl` commands fail with "no compositor running"

`riverctl` communicates via the `WAYLAND_DISPLAY` socket. If you run it from a TTY outside
River, the variable is unset. Inside a River session, always use `echo $WAYLAND_DISPLAY`
to confirm it is set (e.g., `wayland-1`).

### Layout generator does not appear / windows not tiled

Verify that:

1. `riverctl default-layout <name>` uses exactly the name the generator registers.
   For `rivertile`, the name is `rivertile`. For `kile`, it is `kile`. Check the
   generator's `--help` or source for its registered namespace string.
2. The layout generator process is running: `pgrep rivertile`.
3. There is no error in the generator's stderr: `rivertile 2>/tmp/rivertile.log &`.

### Tags seem to behave unexpectedly — windows disappear

Remember that tags are bit-flags. If you `set-focused-tags 1` and a window has
`tags 2` (bit 1), it will not be visible. Use:

```bash
# Show all windows regardless of tag (debugging)
riverctl set-focused-tags $(( (1 << 32) - 1 ))
```

Also check `riverctl rule-add` entries: a rule that assigns `tags N` fires at map time
and can override the tag the window was opened with.

### High CPU from a layout generator

Some Python-based generators poll rather than waiting on Wayland events. Confirm with
`top` or `htop`. The Zig and Rust generators (`rivertile`, `rivercarro`, `kile`) are
event-driven and idle at ~0% CPU when no layout recomputation is needed.

### Waybar River module shows all tags grey / no status

Ensure Waybar is started *after* River has initialised the output. Add a short wait or
use a `river/tags` `set-tags` that matches your actual tag count:

```bash
# In init, defer Waybar start slightly
riverctl spawn "sh -c 'sleep 1; waybar'"
```

Also confirm that `river-status-unstable-v1` is available:

```bash
wayland-info 2>/dev/null | grep river_status
```

If missing, you are running an older River build; update to 0.3.0 or later.

### XWayland apps do not appear (when using xwayland-satellite)

`xwayland-satellite` must be running before any XWayland client connects. Start it from
the init script before any X11 app:

```bash
riverctl spawn "xwayland-satellite"
```

Verify with:

```bash
echo $DISPLAY        # should print :0 or similar once satellite is running
xterm &              # test X11 app
```

See Ch 48 for full xwayland-satellite configuration.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
