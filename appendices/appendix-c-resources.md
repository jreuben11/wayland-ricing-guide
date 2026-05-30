# Appendix C — Resource Index

## Overview

This appendix is a curated, annotated reference to every major resource, repository, tool, and community hub relevant to Wayland desktop customization. It is structured so you can navigate by what you need: official protocol documentation, compositor source trees, per-tool quick-references, community forums, and a cheat-sheet of commands you will run constantly while ricing. Every URL has been verified against the project's canonical hosting location; where a project has moved or forked, the canonical location is listed. The Tooling Reference section organizes ecosystem tools by functional category (wallpaper daemons, screen lockers, bars, notification daemons, launchers, screenshot tools, clipboard managers, monitor management, and color/theming), making it easy to compare alternatives at a glance. A Troubleshooting section at the end covers the six most common setup failures with diagnostic commands. See Ch 1 for a conceptual overview of the Wayland protocol stack, Ch 53 for session startup and environment variable injection, Appendix A for the protocol extension taxonomy, and Appendix D for the Quickshell API cheat-sheet.

---

## Contents

- [Official Documentation](#official-documentation)
- [Key Repositories](#key-repositories)
- [Tooling Reference](#tooling-reference)
  - [Wallpaper Daemons](#wallpaper-daemons)
  - [Screen Lockers](#screen-lockers)
  - [Status Bars](#status-bars)
  - [Notification Daemons](#notification-daemons)
  - [Launchers](#launchers)
  - [Screenshot and Recording](#screenshot-and-recording)
  - [Clipboard Management](#clipboard-management)
  - [Monitor Management](#monitor-management)
  - [Color and Theming](#color-and-theming)
- [Learning Resources](#learning-resources)
- [Useful Commands Cheat Sheet](#useful-commands-cheat-sheet)
  - [Environment Verification](#environment-verification)
  - [Protocol Debug Tracing](#protocol-debug-tracing)
  - [Compositor Inspection (Hyprland)](#compositor-inspection-hyprland)
  - [Compositor Inspection (Sway)](#compositor-inspection-sway)
  - [Wallpaper and Color Workflow](#wallpaper-and-color-workflow)
  - [Screenshot Pipeline](#screenshot-pipeline)
  - [Clipboard Operations](#clipboard-operations)
  - [Monitor Hotplug and Scaling](#monitor-hotplug-and-scaling)
- [Troubleshooting](#troubleshooting)
  - [Application Runs Under XWayland Instead of Native Wayland](#application-runs-under-xwayland-instead-of-native-wayland)
  - [`wl-copy` / `wl-paste` Returns Empty](#wl-copy-wl-paste-returns-empty)
  - [`grim` Fails with "no outputs"](#grim-fails-with-no-outputs)
  - [`kanshi` Profile Not Switching on Hotplug](#kanshi-profile-not-switching-on-hotplug)
  - [Waybar Modules Showing "N/A" or Not Updating](#waybar-modules-showing-na-or-not-updating)
  - [`swww` Daemon Not Starting](#swww-daemon-not-starting)

---


## Official Documentation

The authoritative sources below are the primary references for understanding the protocol, compositor APIs, and the major shell ecosystems. When in doubt, always prefer these over third-party tutorials, which frequently lag behind protocol changes by six months or more.

**The Wayland Book** (`https://wayland-book.com`) by Drew DeVault is the definitive introduction to writing Wayland clients and compositors from first principles. It covers the wire protocol, `wl_display` connection bootstrapping, the object model, globals enumeration via `wl_registry`, and the surface/buffer model that everything else builds on. The prose is dense but precise. Read chapters 1–5 before attempting any direct `libwayland-client` work.

**Wayland Protocol Explorer** (`https://wayland.app/protocols/`) renders all stable and staging protocol XML files as browsable HTML with per-request and per-event documentation. When you encounter an unfamiliar interface name in a `WAYLAND_DEBUG=1` trace, this site is your first stop. It covers both the core `wayland.xml` interfaces and the entire `wayland-protocols` staging and stable trees, plus the `wlr-protocols` extension set that underpins most wlroots-based compositors.

**wlroots documentation** lives in the source tree at `https://gitlab.freedesktop.org/wlroots/wlroots`. The header files in `include/wlr/` are the primary API reference; Doxygen output is available but the headers themselves are more reliable. When writing a wlroots-based compositor (or customizing Hyprland/Sway internals), treat the headers as the spec. Pay particular attention to `wlr_scene`, `wlr_output_layout`, and `wlr_xdg_shell` — these three subsystems touch almost every customization point.

**Compositor-specific wikis** are essential because each compositor exposes unique IPC mechanisms, configuration syntax, and extension protocols. The Hyprland wiki (`https://wiki.hyprland.org`) is comprehensive and actively maintained, covering keywords, dispatchers, window rules, and the Hyprland socket2 protocol. The Sway wiki (`https://github.com/swaywm/sway/wiki`) documents its i3-compatible IPC and the SwayFX fork extensions. The Niri wiki (`https://github.com/YaLTeR/niri/wiki`) is the canonical reference for its scrollable-tiling model.

| Resource | URL | Best For |
|----------|-----|----------|
| Wayland Book | https://wayland-book.com | Protocol fundamentals, client dev |
| Wayland Protocol Explorer | https://wayland.app/protocols/ | Interface/event lookup |
| wlroots docs | https://gitlab.freedesktop.org/wlroots/wlroots | Compositor internals |
| Quickshell docs | https://quickshell.org/docs/ | QML widget authoring |
| Hyprland wiki | https://wiki.hyprland.org | Hyprland config/IPC |
| Sway wiki | https://github.com/swaywm/sway/wiki | Sway IPC, SwayFX |
| Niri wiki | https://github.com/YaLTeR/niri/wiki | Scrollable-tiling model |
| Stylix docs | https://stylix.danth.me | NixOS theming pipeline |
| Home Manager manual | https://nix-community.github.io/home-manager/ | Declarative dotfiles |
| Arch Wiki Wayland | https://wiki.archlinux.org/title/Wayland | Distro-agnostic setup |
| Smithay Book | https://smithay.github.io/smithay/ | Rust compositor dev |

---

## Key Repositories

Understanding where to file issues, submit patches, and read changelogs requires knowing each project's canonical repository. Several important projects host on GitLab (freedesktop.org) rather than GitHub. The `awesome-wayland` list is the best single aggregation point for discovering new tools.

**wayland-protocols** (`https://gitlab.freedesktop.org/wayland/wayland-protocols`) is the upstream home of all stable and staging protocol extensions. The `stable/` subdirectory contains `xdg-shell`, `xdg-output`, and `presentation-time` — the interfaces every compositor must implement for compliance. The `staging/` tree contains drafts like `ext-session-lock-v1`, `xdg-activation-v1`, and `cursor-shape-v1` that are widely adopted before formal promotion. Watching the commit log here is the best way to track what is coming in the next protocol cycle.

**wlr-protocols** (`https://gitlab.freedesktop.org/wlroots/wlr-protocols`) contains the `zwlr_*` namespace extensions that wlroots-based compositors implement. These include `wlr-layer-shell-v1` (used by every bar and overlay), `wlr-screencopy-v1` (used by screenshot and recording tools), and `wlr-output-management-v1` (used by `kanshi` and `wdisplays`). Note that wlr-protocols is frozen: new compositor-extension protocols now go into `wayland-protocols/staging/` or the `ext-*` namespace. See Ch 7 for a full discussion of layer shell anchoring and exclusive zones.

**Smithay** (`https://github.com/Smithay/smithay`) is the Rust compositor framework that powers Cosmic Desktop and several experimental projects. Its `examples/` directory contains a minimal working compositor (anvil) that is an excellent reference for understanding how a modern Rust compositor is structured. The `smithay-client-toolkit` subcrate provides a safe Rust client API that mirrors `libwayland-client`.

| Project | Repository | Notes |
|---------|-----------|-------|
| wayland-protocols | https://gitlab.freedesktop.org/wayland/wayland-protocols | Upstream stable/staging |
| wlroots | https://gitlab.freedesktop.org/wlroots/wlroots | Core compositor library |
| wlr-protocols | https://gitlab.freedesktop.org/wlroots/wlr-protocols | Frozen; zwlr_* namespace |
| Quickshell | https://git.outfoxxed.me/quickshell/quickshell | QML shell framework |
| Hyprland | https://github.com/hyprwm/Hyprland | wlroots C++ compositor |
| Sway | https://github.com/swaywm/sway | i3-compatible tiling |
| Niri | https://github.com/YaLTeR/niri | Scrollable-tiling |
| River | https://codeberg.org/river/river | Lua-scriptable |
| labwc | https://github.com/labwc/labwc | Openbox-style floating |
| Wayfire | https://github.com/WayfireWM/wayfire | Plugin-based compositor |
| Smithay | https://github.com/Smithay/smithay | Rust compositor framework |
| cosmic-comp | https://github.com/pop-os/cosmic-comp | Smithay-based |
| awesome-wayland | https://github.com/rcalixte/awesome-wayland | Curated tool list |

---

## Tooling Reference

The Wayland tooling ecosystem is fragmented by design: each compositor exposes different IPC, different extension protocols, and different configuration surfaces. The table below organizes tools by functional category. When multiple tools serve the same purpose, the "Notes" column identifies the key differentiators.

### Wallpaper Daemons

`swww` and `hyprpaper` are the two dominant wallpaper daemons. `swww` is compositor-agnostic (uses `wlr-layer-shell`) and supports animated transitions via a client-server IPC. `hyprpaper` is Hyprland-only (uses the Hyprland socket directly) and has near-zero startup latency. For scripted wallpaper rotation with crossfade, `swww` is the correct choice. For declarative static wallpaper in a Hyprland config, `hyprpaper` is simpler.

```bash
# swww: daemon + transition example
swww-daemon &
swww img ~/wallpapers/forest.jpg \
  --transition-type wipe \
  --transition-angle 30 \
  --transition-duration 1.5

# hyprpaper: declarative config (~/.config/hypr/hyprpaper.conf)
preload = ~/wallpapers/forest.jpg
wallpaper = DP-1,~/wallpapers/forest.jpg
wallpaper = HDMI-A-1,~/wallpapers/forest.jpg
splash = false
```

### Screen Lockers

`hyprlock` is the native Hyprland locker and integrates directly with `hypridle` for idle-triggered locking. `swaylock` is the reference wlroots locker used by Sway and River. Both implement `ext-session-lock-v1`.

```bash
# hyprlock invocation
hyprlock

# swaylock with blur
swaylock \
  --image ~/wallpapers/forest.jpg \
  --scaling fill \
  --effect-blur 10x3 \
  --effect-vignette 0.5:0.5 \
  --clock \
  --indicator

# hypridle config (~/.config/hypr/hypridle.conf)
general {
  lock_cmd = hyprlock
  before_sleep_cmd = hyprlock
  after_sleep_cmd = hyprctl dispatch dpms on
}
listener {
  timeout = 300
  on-timeout = hyprlock
}
listener {
  timeout = 600
  on-timeout = hyprctl dispatch dpms off
  on-resume = hyprctl dispatch dpms on
}
```

### Status Bars

Waybar is the dominant status bar for wlroots compositors. It is configured in JSON with CSS theming. Yambar is a lighter alternative with a YAML configuration format. The Astal/AGS ecosystem (discussed in Appendix B) provides a TypeScript-scriptable alternative that is increasingly popular for complex dynamic widgets.

```jsonc
// ~/.config/waybar/config (minimal example)
{
  "layer": "top",
  "position": "top",
  "height": 30,
  "modules-left": ["hyprland/workspaces"],
  "modules-center": ["clock"],
  "modules-right": ["pulseaudio", "network", "battery", "tray"],
  "clock": {
    "format": "{:%H:%M  %a %b %d}",
    "tooltip-format": "<big>{:%Y %B}</big>\n<tt><small>{calendar}</small></tt>"
  },
  "battery": {
    "states": { "warning": 30, "critical": 15 },
    "format": "{capacity}% {icon}",
    "format-icons": ["", "", "", "", ""]
  },
  "network": {
    "format-wifi": " {essid} ({signalStrength}%)",
    "format-ethernet": "󰈀 {ipaddr}",
    "format-disconnected": "󰤭 Disconnected"
  }
}
```

```css
/* ~/.config/waybar/style.css */
* { font-family: "JetBrainsMono Nerd Font"; font-size: 13px; }
window#waybar { background: rgba(26,27,38,0.9); color: #c0caf5; }
#workspaces button { padding: 0 6px; color: #565f89; }
#workspaces button.active { color: #7aa2f7; border-bottom: 2px solid #7aa2f7; }
#clock { padding: 0 12px; color: #bb9af7; }
```

### Notification Daemons

`mako` is minimal, configured with a single file, and has no persistent history. `dunst` is more feature-rich with action callbacks. `swaync` (SwayNotificationCenter) adds a sliding notification panel and Do-Not-Disturb mode, making it suitable for full desktop environments.

```ini
# ~/.config/mako/config
background-color=#1a1b26
text-color=#c0caf5
border-color=#7aa2f7
border-radius=8
border-size=2
default-timeout=5000
max-visible=5
font=JetBrainsMono Nerd Font 11

[urgency=critical]
border-color=#f7768e
default-timeout=0
```

### Launchers

`fuzzel` is a fast, minimal Wayland-native launcher. `rofi` (Wayland fork) provides compatibility with the large ecosystem of rofi scripts and themes.

```ini
# ~/.config/fuzzel/fuzzel.ini
[main]
font=JetBrainsMono Nerd Font:size=12
dpi-aware=no
prompt=" "
terminal=foot

[colors]
background=1a1b26ff
text=c0caf5ff
match=7aa2f7ff
selection=364a82ff
selection-text=c0caf5ff
border=7aa2f7ff

[border]
width=2
radius=8
```

```bash
# rofi Wayland launch (requires lbonn/rofi fork)
rofi -show drun -theme ~/.config/rofi/launcher.rasi
```

### Screenshot and Recording

`grim` captures Wayland outputs via `wlr-screencopy`. `slurp` provides interactive region selection and is typically piped into `grim`. `wf-recorder` wraps `wlr-screencopy` for screen recording.

```bash
# Full-screen screenshot to clipboard
grim - | wl-copy

# Region screenshot to file with timestamp
grim -g "$(slurp)" ~/screenshots/$(date +%Y%m%d_%H%M%S).png

# Active window screenshot (Hyprland)
hyprctl -j activewindow | jq -r '"\(.at[0]),\(.at[1]) \(.size[0])x\(.size[1])"' \
  | grim -g - ~/screenshots/window_$(date +%Y%m%d_%H%M%S).png

# Screen recording to mp4
wf-recorder -g "$(slurp)" -f ~/recordings/$(date +%Y%m%d_%H%M%S).mp4

# Screen recording with audio (PipeWire)
wf-recorder -g "$(slurp)" --audio -f ~/recordings/$(date +%Y%m%d_%H%M%S).mp4
```

### Clipboard Management

`wl-clipboard` provides `wl-copy` and `wl-paste`, the fundamental Wayland clipboard primitives. `cliphist` stores a clipboard history database and integrates with any `--dmenu`-compatible launcher.

```bash
# Clipboard pipeline for launcher integration
cliphist list | fuzzel --dmenu | cliphist decode | wl-copy

# Rofi clipboard picker
cliphist list | rofi -dmenu | cliphist decode | wl-copy

# Wipe clipboard history
cliphist wipe

# Store clipboard events (run in session startup)
wl-paste --watch cliphist store
```

### Monitor Management

`kanshi` reads `~/.config/kanshi/config` and applies output profiles when monitor topology changes. It uses `wlr-output-management-v1`. `wdisplays` provides a GTK GUI for the same protocol.

```
# ~/.config/kanshi/config
profile laptop {
  output eDP-1 enable scale 1.5 position 0,0
}

profile docked {
  output eDP-1 disable
  output DP-1 enable mode 2560x1440@144Hz position 0,0 scale 1
  output HDMI-A-1 enable mode 1920x1080@60Hz position 2560,180 scale 1
}

profile desktop_only {
  output DP-1 enable mode 2560x1440@144Hz position 0,0 scale 1
}
```

### Color and Theming

`matugen` generates Material You color palettes from a wallpaper image and writes them to template files. `pywal` generates palettes from any image using color quantization. `Catppuccin` is a hand-crafted palette available for nearly every application.

```bash
# matugen: generate palette and write templates
matugen image ~/wallpapers/forest.jpg --mode dark
# Output written to ~/.config/matugen/colors/ and any configured templates

# pywal: generate palette and reload terminals
wal -i ~/wallpapers/forest.jpg --backend colorz
# Templates in ~/.config/wal/templates/ are rendered to ~/.cache/wal/

# Apply wal colors to current shell (add to ~/.zshrc)
(cat ~/.cache/wal/sequences &)
```

| Tool | Purpose | Protocol/IPC | Repository |
|------|---------|-------------|-----------|
| swww | Wallpaper + transitions | wlr-layer-shell | https://github.com/LGFae/swww |
| hyprpaper | Hyprland wallpaper | Hyprland socket | https://github.com/hyprwm/hyprpaper |
| hyprlock | Hyprland lockscreen | ext-session-lock-v1 | https://github.com/hyprwm/hyprlock |
| hypridle | Idle daemon | ext-idle-notify-v1 | https://github.com/hyprwm/hypridle |
| swaylock | wlroots lockscreen | ext-session-lock-v1 | https://github.com/swaywm/swaylock |
| Waybar | Status bar | wlr-layer-shell | https://github.com/Alexays/Waybar |
| yambar | Status bar | wlr-layer-shell | https://codeberg.org/dnkl/yambar |
| eww | Widgets | wlr-layer-shell | https://github.com/elkowar/eww |
| Astal/AGS | TS widgets | wlr-layer-shell | https://github.com/aylur/astal |
| mako | Notifications | xdg-popup / custom | https://github.com/emersion/mako |
| dunst | Notifications | xdg-popup | https://github.com/dunst-project/dunst |
| swaync | Notif center | wlr-layer-shell | https://github.com/ErikReider/SwayNotificationCenter |
| fuzzel | Launcher | xdg-shell / layer | https://codeberg.org/dnkl/fuzzel |
| rofi (Wayland) | Launcher | xdg-shell | https://github.com/lbonn/rofi |
| tofi | Launcher | wlr-layer-shell | https://github.com/philj56/tofi |
| grim | Screenshots | wlr-screencopy-v1 | https://sr.ht/~emersion/grim/ |
| slurp | Region selection | xdg-shell | https://github.com/emersion/slurp |
| wf-recorder | Recording | wlr-screencopy-v1 | https://github.com/ammen99/wf-recorder |
| wl-clipboard | Clipboard | wl-data-device | https://github.com/bugaevc/wl-clipboard |
| cliphist | Clipboard history | wl-clipboard wrapper | https://github.com/sentriz/cliphist |
| kanshi | Monitor profiles | wlr-output-management | https://sr.ht/~emersion/kanshi/ |
| wdisplays | Monitor GUI | wlr-output-management | https://github.com/artizirk/wdisplays |
| kanata | Key remapper | kernel input | https://github.com/jtroo/kanata |
| keyd | Key remapper | kernel input | https://github.com/rvaiya/keyd |
| pywal | Color extraction | filesystem templates | https://github.com/dylanaraps/pywal |
| matugen | Material You colors | filesystem templates | https://github.com/InioX/matugen |
| Stylix | NixOS auto-theme | Home Manager | https://github.com/nix-community/stylix |
| Catppuccin | Color palette | per-app configs | https://github.com/catppuccin/catppuccin |
| nwg-look | GTK theme setter | gsettings | https://github.com/nwg-piotr/nwg-look |
| xsettingsd | X11 settings bridge | X11/Wayland | https://github.com/derat/xsettingsd |
| qt5ct / qt6ct | Qt theme config | environment vars | https://github.com/desktop-app/qt5ct |

---

## Learning Resources

The resources below are organized by learning goal. The Wayland Book and Way-Cooler book are the two most rigorous treatments of the protocol. The Arch Wiki is the best single reference for practical setup. Community forums are valuable for debugging compositor-specific issues where documentation is sparse.

The **Way-Cooler book** (`https://way-cooler.org/book/`) documents the construction of a wlroots compositor in Rust and is an excellent complement to the Wayland Book for those who want to understand compositor internals without reading C. Even if you never write a compositor, the architectural chapters clarify why certain Wayland behaviors (implicit grab, surface coordinate spaces, dmabuf import) work the way they do.

The **Arch Wiki Wayland article** (`https://wiki.archlinux.org/title/Wayland`) is distro-agnostic despite its provenance. It covers environment variable requirements (`XDG_SESSION_TYPE`, `WAYLAND_DISPLAY`, `MOZ_ENABLE_WAYLAND`, `QT_QPA_PLATFORM`), toolkit-specific Wayland enablement flags, and XWayland setup. This should be your first stop for "application X is running under XWayland instead of native Wayland."

The **deepwiki Quickshell mirror** (`https://deepwiki.com/quickshell-mirror/quickshell`) is an AI-generated but surprisingly accurate rendering of the Quickshell internals, useful for understanding how `ProxyShell`, `Variants`, and `PersistentSystemTray` are implemented. Cross-reference with the official docs at `https://quickshell.org/docs/` for authoritative API details.

**r/unixporn** (`https://reddit.com/r/unixporn`) is the primary showcase forum for Linux desktop customization. The top posts in the "Wayland" or "Hyprland" flair are useful for discovering new tools and dotfile configurations. Most top posts link to a GitHub dotfiles repository that you can study directly. The monthly "Simple Desktops" threads often contain the most technically refined setups.

| Resource | Type | Focus |
|----------|------|-------|
| https://wayland-book.com | Book | Protocol fundamentals |
| https://way-cooler.org/book/ | Book | wlroots compositor in Rust |
| https://smithay.github.io/smithay/ | Book | Smithay (Rust) compositor |
| https://wiki.archlinux.org/title/Wayland | Wiki | Practical setup, env vars |
| https://deepwiki.com/quickshell-mirror/quickshell | Wiki | Quickshell internals |
| https://reddit.com/r/unixporn | Community | Rice showcase |
| https://reddit.com/r/hyprland | Community | Hyprland support |
| https://reddit.com/r/swaywm | Community | Sway support |
| https://discourse.nixos.org | Forum | NixOS/Home Manager |
| https://matrix.to/#/#wayland:matrix.org | Chat | Wayland developer Matrix |
| https://github.com/rcalixte/awesome-wayland | List | Curated tool discovery |

---

## Useful Commands Cheat Sheet

The commands below cover the most frequent diagnostic and operational tasks during a ricing session. They are grouped by function and annotated with the underlying protocol mechanism. See Ch 53 for how to inject these into your session startup.

### Environment Verification

```bash
# Verify Wayland session is active
echo "WAYLAND_DISPLAY=$WAYLAND_DISPLAY"
echo "XDG_SESSION_TYPE=$XDG_SESSION_TYPE"
echo "XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR"

# Check which socket file exists
ls -la "$XDG_RUNTIME_DIR"/wayland-*

# Verify an application is running natively (not XWayland)
# If it shows in `xlsclients`, it is running under XWayland
xlsclients -display :0

# Check with hyprctl (Hyprland)
hyprctl clients -j | jq '.[] | {class, xwayland}'
```

### Protocol Debug Tracing

```bash
# Full protocol trace (very verbose — pipe through grep)
WAYLAND_DEBUG=1 foot 2>&1 | grep -E 'wl_surface|xdg_toplevel'

# Trace only a specific interface
WAYLAND_DEBUG=client foot 2>&1 | grep xdg_shell

# weston-info: enumerate all globals advertised by the compositor
weston-info

# wayland-info (from wayland-utils package)
wayland-info

# List available protocols by scanning the registry
# (requires a running Wayland compositor)
wayland-info | grep -E 'interface|version'
```

### Compositor Inspection (Hyprland)

```bash
# JSON output of all monitors
hyprctl monitors -j | jq '.[] | {name, width, height, refreshRate, scale}'

# All open windows with geometry
hyprctl clients -j | jq '.[] | {class, title, at, size, workspace}'

# Active window
hyprctl activewindow -j

# All workspaces
hyprctl workspaces -j

# Reload config without restart
hyprctl reload

# Kill active window
hyprctl dispatch killactive

# Send notification via Hyprland
hyprctl notify 1 3000 "rgb(7aa2f7)" "Hello from hyprctl"

# Watch hyprland socket2 events
socat - "UNIX-CONNECT:${XDG_RUNTIME_DIR}/hypr/${HYPRLAND_INSTANCE_SIGNATURE}/.socket2.sock"
```

### Compositor Inspection (Sway)

```bash
# All outputs
swaymsg -t get_outputs | jq '.[] | {name, current_mode, scale}'

# All windows
swaymsg -t get_tree | jq '.. | .nodes? // empty | .[] | select(.type=="con") | {name,app_id}'

# Reload config
swaymsg reload

# Subscribe to Sway IPC events
swaymsg -t subscribe '["window","workspace"]'
```

### Wallpaper and Color Workflow

```bash
# swww animated transition
swww-daemon &
sleep 0.5
swww img ~/wallpapers/city_night.jpg \
  --transition-type grow \
  --transition-pos 0.5,0.5 \
  --transition-duration 2

# pywal: generate scheme and export to all templates
wal -i ~/wallpapers/forest.jpg --backend colorz --saturate 0.8
# Reload all wal-aware apps (kitty, waybar, etc.)
wal --theme current

# matugen: full dark palette from image
matugen image ~/wallpapers/forest.jpg \
  --mode dark \
  --type scheme-content \
  --json hex > /tmp/palette.json
cat /tmp/palette.json | jq '.colors.primary'
```

### Screenshot Pipeline

```bash
# Full display screenshot to clipboard
grim - | wl-copy

# Interactive region to file
grim -g "$(slurp)" ~/screenshots/$(date +%Y%m%d_%H%M%S).png

# Region to clipboard immediately
grim -g "$(slurp)" - | wl-copy

# Screenshot with annotation (requires satty)
grim -g "$(slurp)" - | satty --filename - --copy-command wl-copy

# Active window (Hyprland)
GEOM=$(hyprctl -j activewindow | jq -r '"\(.at[0]),\(.at[1]) \(.size[0])x\(.size[1])"')
grim -g "$GEOM" ~/screenshots/window_$(date +%H%M%S).png
```

### Clipboard Operations

```bash
# Paste primary selection to clipboard
wl-paste --primary | wl-copy

# Watch clipboard changes (for debugging)
wl-paste --watch sh -c 'echo "Clipboard changed: $(wl-paste | head -c 80)"'

# Clipboard history picker (fuzzel)
cliphist list | fuzzel --dmenu | cliphist decode | wl-copy

# Clipboard history picker (rofi)
cliphist list | rofi -dmenu -p "Clipboard" | cliphist decode | wl-copy

# Count history entries
cliphist list | wc -l

# Wipe entire history
cliphist wipe
```

### Monitor Hotplug and Scaling

```bash
# List connected outputs and their modes
wlr-randr

# Set output scale
wlr-randr --output DP-1 --scale 1.5

# Rotate output
wlr-randr --output HDMI-A-1 --transform 90

# Apply kanshi profile manually
kanshictl switch docked

# Reload kanshi config
kanshictl reload
```

---

## Troubleshooting

This section covers the most common failures encountered when setting up the tools referenced in this appendix. For compositor-startup failures, see Ch 53. For XWayland compatibility issues, see Ch 8.

### Application Runs Under XWayland Instead of Native Wayland

Most toolkits default to X11 unless explicitly configured otherwise. Check these environment variables and application-specific flags:

```bash
# GTK 3/4: force Wayland backend
export GDK_BACKEND=wayland

# Qt 5/6: force Wayland backend
export QT_QPA_PLATFORM=wayland

# Firefox/Thunderbird: force Wayland
export MOZ_ENABLE_WAYLAND=1

# Electron apps (Electron 28+): force Wayland
# Add to ~/.config/electron-flags.conf:
--enable-features=UseOzonePlatform
--ozone-platform=wayland

# Java/Swing apps
export _JAVA_AWT_WM_NONREPARENTING=1
```

Verify with: `hyprctl clients -j | jq '.[] | select(.class=="app_name") | .xwayland'`

### `wl-copy` / `wl-paste` Returns Empty

The clipboard in Wayland is "lazy" — data is only transferred when requested, and it disappears when the source application exits. To persist clipboard contents after an app closes, run `wl-paste --watch cliphist store` in your session startup (see Ch 53). `cliphist` stores data in a local database and survives the source application exiting.

```bash
# Persist clipboard contents after source app closes
# Add to session startup:
wl-paste --watch cliphist store &

# Test persistence
echo "test" | wl-copy
# close terminal — clipboard now survives because cliphist captured it
```

### `grim` Fails with "no outputs"

`grim` queries the compositor for outputs via `zwlr_screencopy_manager_v1`. If the compositor does not advertise this protocol, or if it is disabled, `grim` will fail with a "no outputs" error. Hyprland disables screencopy for security reasons when `misc:disable_hyprland_logo = false` is not set (this is a misconception — the real gate is the `screencopy_allow_overlay = true` keyword, which was removed in later versions). The actual fix is:

```bash
# Verify the protocol is advertised
wayland-info | grep screencopy

# If using Hyprland, ensure xdg-portal-hyprland is running
systemctl --user status xdg-desktop-portal-hyprland

# Restart portals
systemctl --user restart xdg-desktop-portal xdg-desktop-portal-hyprland
```

### `kanshi` Profile Not Switching on Hotplug

`kanshi` relies on `wlr-output-management-v1`. If your compositor does not advertise this protocol, or `kanshi` cannot connect to the Wayland socket, profiles will not switch. Check with:

```bash
# Verify kanshi service is running
systemctl --user status kanshi

# Check compositor advertises the protocol
wayland-info | grep output-management

# Manually trigger a profile switch
kanshictl switch laptop

# View kanshi logs
journalctl --user -u kanshi -f
```

### Waybar Modules Showing "N/A" or Not Updating

Waybar modules communicate via D-Bus (for media players, network), `hyprctl` socket (for workspaces), or `swaymsg` (for Sway workspaces). Common causes of stale/missing data:

```bash
# Check Waybar is using the correct compositor backend
# In config, set "layer": "top" and confirm the correct IPC is used

# Restart Waybar in-place
killall -SIGUSR2 waybar

# Debug a specific module
waybar --log-level trace 2>&1 | grep "network\|battery"

# Check D-Bus services for media player
dbus-send --session --print-reply \
  --dest=org.freedesktop.DBus /org/freedesktop/DBus \
  org.freedesktop.DBus.ListNames | grep -i mpris
```

### `swww` Daemon Not Starting

`swww-daemon` must be started before `swww img` is called. In some init scripts the timing is tight. Add a wait loop:

```bash
# Robust swww startup
swww-daemon &
SWWW_DAEMON_PID=$!
# Wait for the socket to appear
until swww query 2>/dev/null; do sleep 0.1; done
swww img ~/wallpapers/default.jpg --transition-type none
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
