# Chapter 7 — Sway: i3 on Wayland

## Overview

Sway is the most mature and widely deployed wlroots-based Wayland compositor. Created by Drew DeVault in 2015 as a faithful re-implementation of i3 for Wayland, it has become the go-to compositor for users migrating from X11 who want stability, a proven configuration model, and a rich ecosystem of supporting tools.

Unlike many Wayland compositors that introduce entirely new configuration systems, Sway's explicit design goal is compatibility: if a valid i3 config does not work in Sway, that is treated as a bug. This compatibility guarantee makes migration from i3 essentially frictionless for the vast majority of configurations. The project also maintains the wlroots library — the foundational Wayland compositor toolkit used by Wayfire, River, and many others.

This chapter covers Sway from first boot through advanced scripting and multi-monitor configurations. Readers already familiar with i3 can skip to Section 7.3 for Wayland-specific differences and Section 7.5 for IPC scripting. For session startup and PAM/logind integration, see **Ch 53: Session Management on Wayland**.

---

## 7.1 History and Philosophy

Sway was born from frustration. In 2015 Drew DeVault was a dedicated i3 user who wanted to move to Wayland but found no compositor that matched i3's keyboard-driven tiling workflow. Rather than wait, he wrote one. The name "Sway" (Sway Window mAnager, Yeah) deliberately mirrors i3's own recursive acronym tradition.

The "if it doesn't work like i3, it's a bug" policy is not marketing — it is a documented development constraint enforced during code review. This means that when you read an i3 user guide, nearly all configuration directives translate directly. The only deliberate exceptions are features that are architecturally impossible under Wayland's security model (such as global X11 hotkeys for arbitrary windows) or that have been superseded by Wayland-native equivalents.

Critically, Sway's team also maintains **wlroots**, the compositor toolkit library. This dual role means Sway gets first access to new wlroots features and that wlroots APIs are shaped partly by Sway's needs. Other compositors (River, Wayfire) consume wlroots but do not control its roadmap in the same way. As of 2026, Sway runs on wlroots 0.18+ and requires a kernel with DRM/KMS support (5.15+ recommended, 6.1 LTS or newer preferred).

Current maintainership has stabilized around a small core team after Drew DeVault stepped back from day-to-day development. The project follows a conservative release cadence: major releases ship when stable, not on a calendar schedule. This makes Sway a dependable foundation for production ricing work where you don't want a compositor update to break your workflow mid-project.

### Key Design Principles

| Principle | Implication |
|-----------|-------------|
| i3 compatibility | Existing i3 configs work with minimal changes |
| wlroots-based | Benefits from upstream security and protocol work |
| Minimal scope | Does one thing well; delegates to ecosystem tools |
| Stable ABI/config | No breaking config changes within a major version |
| Security model | Per-seat input; no global keylogging by design |

---

## 7.2 Installation and Initial Setup

Most major distributions ship Sway in their official repositories. Package names are consistently `sway` with optional companion packages for the ecosystem tools.

### Distribution Packages

```bash
# Arch Linux / Manjaro
sudo pacman -S sway swayidle swaylock swaybg

# Fedora 39+
sudo dnf install sway swayidle swaylock

# Ubuntu 24.04 LTS
sudo apt install sway swayidle swaylock

# NixOS (configuration.nix)
programs.sway = {
  enable = true;
  wrapperFeatures.gtk = true;   # fixes GTK apps under Sway
  extraPackages = with pkgs; [
    swaylock swayidle swaybg waybar mako wofi
  ];
};

# openSUSE Tumbleweed
sudo zypper install sway
```

For bleeding-edge features or to track `main`, build from source:

```bash
# Install build dependencies (Arch example)
sudo pacman -S meson ninja wayland wayland-protocols \
  wlroots libxkbcommon pixman cairo pango gdk-pixbuf2 \
  json-c pcre2 libevdev libinput

git clone https://github.com/swaywm/sway.git
cd sway
meson setup build --prefix=/usr/local
ninja -C build
sudo ninja -C build install
```

### First Launch

Sway is launched from a TTY or via a display manager. From TTY:

```bash
sway
# Or with a debug log
sway -d 2>~/.local/share/sway/debug.log
```

On first launch with no config file, Sway copies a default configuration from `/etc/sway/config` to `~/.config/sway/config`. The default config is functional: it sets `$mod` to the Super key, configures basic keybindings, and launches a status bar.

```bash
# Verify Sway is running and check the socket
echo $SWAYSOCK          # /run/user/1000/sway-ipc.1000.NNN.sock
swaymsg -t get_version  # {"human_readable": "1.10-...", ...}
```

### Config File Locations

Sway searches for its config in this order:

1. `~/.config/sway/config`
2. `$XDG_CONFIG_HOME/sway/config`
3. `/etc/sway/config`
4. `/usr/local/etc/sway/config`

You can also specify a config explicitly: `sway -c /path/to/config`

For modular configs, use the `include` directive:

```
# ~/.config/sway/config
include ~/.config/sway/conf.d/*.conf
include ~/.config/sway/themes/catppuccin.conf
```

---

## 7.3 Configuration Deep Dive

Sway's configuration language is line-oriented: one directive per line, with blocks delimited by `{` and `}`. Comments begin with `#`. Variable assignment uses `set $varname value` and substitution uses `$varname`.

### Variable Substitution and Modifiers

```
# ~/.config/sway/config

# Define modifier (Mod4 = Super/Win, Mod1 = Alt)
set $mod Mod4
set $left h
set $down j
set $up k
set $right l

# Terminal and launcher variables
set $term foot
set $menu wofi --show drun --allow-images

# Color palette (Catppuccin Mocha)
set $rosewater #f5e0dc
set $flamingo  #f2cdcd
set $pink      #f38ba8
set $mauve     #cba6f7
set $red       #f38ba8
set $peach     #fab387
set $green     #a6e3a1
set $teal      #94e2d5
set $sky       #89dceb
set $sapphire  #74c7ec
set $blue      #89b4fa
set $lavender  #b4befe
set $text      #cdd6f4
set $overlay0  #6c7086
set $surface0  #313244
set $base      #1e1e2e
set $mantle    #181825
set $crust     #11111b
```

### Output Configuration

The `output` block controls monitors. Use `swaymsg -t get_outputs` to discover output names:

```
# Single monitor
output HDMI-A-1 resolution 2560x1440 refresh 144 position 0,0 scale 1

# Laptop + external monitor setup
output eDP-1 resolution 1920x1080 refresh 60 position 0,1080 scale 1
output DP-1   resolution 2560x1440 refresh 144 position 0,0    scale 1

# Disable the laptop screen when lid is closed
bindswitch --reload --locked lid:on  output eDP-1 disable
bindswitch --reload --locked lid:off output eDP-1 enable

# Wallpaper per output
output eDP-1 background ~/Pictures/wallpapers/forest.jpg fill
output DP-1  background ~/Pictures/wallpapers/city.png  fill

# Rotation
output HDMI-A-2 transform 90
```

### Input Configuration

The `input` block wraps libinput. Use `swaymsg -t get_inputs` to list input device identifiers:

```
# Touchpad (wildcard match on device type)
input type:touchpad {
    dwt enabled                   # disable while typing
    tap enabled                   # tap to click
    natural_scroll enabled
    middle_emulation enabled
    accel_profile adaptive
    pointer_accel 0.2
}

# Keyboard: layout, variant, options
input type:keyboard {
    xkb_layout us,il
    xkb_variant ,
    xkb_options grp:alt_shift_toggle,caps:escape
    repeat_delay 300
    repeat_rate 40
}

# Specific device by ID (from swaymsg -t get_inputs)
input "1739:52781:SYNA8024:00_06CB:CE2D_Touchpad" {
    scroll_method two_finger
    tap_button_map lrm
}
```

### Seat Configuration

Seats represent collections of input devices. Most setups use a single seat:

```
seat seat0 {
    xcursor_theme Bibata-Modern-Classic 24
    hide_cursor 8000         # hide after 8 seconds of inactivity
    hide_cursor when-typing enable
}
```

### Window Decoration

```
# Title bar font and colors
font pango:JetBrains Mono Nerd Font 10

# Border widths
default_border          pixel 2
default_floating_border pixel 2
smart_borders           on    # remove border when only one window

# Gaps (requires sway-gaps or recent sway)
gaps inner 6
gaps outer 4
smart_gaps on

# Color scheme: <border> <background> <text> <indicator> <child_border>
client.focused          $blue    $base   $text  $teal    $blue
client.focused_inactive $surface0 $base  $text  $surface0 $surface0
client.unfocused        $surface0 $base  $overlay0 $surface0 $surface0
client.urgent           $red     $base   $text  $red     $red
```

---

## 7.4 Layout and Window Management

Sway uses the same container tree model as i3. Every visible area of the screen is a node in a tree: the root is the output, its children are workspaces, and workspace children are containers or leaf windows. Layouts — horizontal split, vertical split, tabbed, stacking — are properties of container nodes.

### Core Keybindings

```
# Application launchers
bindsym $mod+Return exec $term
bindsym $mod+d      exec $menu
bindsym $mod+Shift+q kill

# Focus movement (vi-style)
bindsym $mod+$left  focus left
bindsym $mod+$down  focus down
bindsym $mod+$up    focus up
bindsym $mod+$right focus right
bindsym $mod+Left   focus left
bindsym $mod+Down   focus down
bindsym $mod+Up     focus up
bindsym $mod+Right  focus right

# Window movement
bindsym $mod+Shift+$left  move left
bindsym $mod+Shift+$down  move down
bindsym $mod+Shift+$up    move up
bindsym $mod+Shift+$right move right

# Layout selection
bindsym $mod+b       splith
bindsym $mod+v       splitv
bindsym $mod+s       layout stacking
bindsym $mod+w       layout tabbed
bindsym $mod+e       layout toggle split

# Fullscreen and floating
bindsym $mod+f       fullscreen
bindsym $mod+Shift+space floating toggle
bindsym $mod+space       focus mode_toggle
bindsym $mod+a           focus parent
```

### Workspaces

```
# Assign workspaces to outputs
workspace 1 output DP-1
workspace 2 output DP-1
workspace 3 output DP-1
workspace 4 output DP-1
workspace 5 output DP-1
workspace 6 output eDP-1
workspace 7 output eDP-1
workspace 8 output eDP-1

# Switch workspaces
bindsym $mod+1 workspace number 1
bindsym $mod+2 workspace number 2
bindsym $mod+3 workspace number 3
bindsym $mod+4 workspace number 4
bindsym $mod+5 workspace number 5
bindsym $mod+6 workspace number 6
bindsym $mod+7 workspace number 7
bindsym $mod+8 workspace number 8
bindsym $mod+9 workspace number 9
bindsym $mod+0 workspace number 10

# Move window to workspace
bindsym $mod+Shift+1 move container to workspace number 1
bindsym $mod+Shift+2 move container to workspace number 2
# ... etc.

# Scratchpad
bindsym $mod+Shift+minus move scratchpad
bindsym $mod+minus       scratchpad show
```

### Window Rules with `for_window`

The `for_window` directive applies rules based on criteria. In Sway, Wayland-native apps expose `app_id`; XWayland apps expose `class` and `instance`.

```
# Float specific apps
for_window [app_id="pavucontrol"]           floating enable, resize set 700 500
for_window [app_id="nm-connection-editor"]  floating enable
for_window [app_id="org.gnome.Calculator"]  floating enable
for_window [title="Firefox — Sharing Indicator"] floating enable, move scratchpad

# XWayland apps (use class instead of app_id)
for_window [class="Steam" title="Steam - News"] floating enable
for_window [class="Gimp"]                       floating enable

# Assign apps to workspaces
for_window [app_id="firefox"]         move to workspace 2
for_window [class="Slack"]            move to workspace 7
for_window [app_id="org.telegram.*"]  move to workspace 8

# Inhibit idle for fullscreen video
for_window [app_id="mpv"] inhibit_idle fullscreen
for_window [class="vlc"]  inhibit_idle fullscreen

# Mark windows for IPC scripting
for_window [app_id="kitty" title="^scratch$"] mark scratch_term

# Borders
for_window [shell="xwayland"] title_format "[XWayland] %title"
for_window [app_id="firefox"] border pixel 2
```

### Resize Mode

```
mode "resize" {
    bindsym $left  resize shrink width  10px
    bindsym $down  resize grow   height 10px
    bindsym $up    resize shrink height 10px
    bindsym $right resize grow   width  10px

    bindsym Left   resize shrink width  10px
    bindsym Down   resize grow   height 10px
    bindsym Up     resize shrink height 10px
    bindsym Right  resize grow   width  10px

    # Fine-grained with Shift
    bindsym Shift+$left  resize shrink width  2px
    bindsym Shift+$right resize grow   width  2px
    bindsym Shift+$up    resize shrink height 2px
    bindsym Shift+$down  resize grow   height 2px

    bindsym Return mode "default"
    bindsym Escape mode "default"
    bindsym $mod+r mode "default"
}
bindsym $mod+r mode "resize"
```

---

## 7.5 IPC and Scripting

Sway exposes a Unix domain socket IPC interface identical (with minor extensions) to i3's. Every running Sway instance creates a socket at `$SWAYSOCK`. The `swaymsg` command-line tool is the primary interface.

### swaymsg Reference

```bash
# Query current state
swaymsg -t get_version          # compositor version
swaymsg -t get_outputs          # monitor info as JSON
swaymsg -t get_workspaces       # workspace list
swaymsg -t get_tree             # full container tree (large JSON)
swaymsg -t get_inputs           # input devices
swaymsg -t get_seats            # seat configuration
swaymsg -t get_marks            # marked windows

# Send commands
swaymsg "workspace 3"
swaymsg "exec firefox"
swaymsg "[app_id=firefox] focus"
swaymsg "output HDMI-A-1 disable"

# Pretty-print JSON tree
swaymsg -t get_tree | python3 -m json.tool | less

# Get focused window app_id
swaymsg -t get_tree | \
  python3 -c "
import json, sys
def find_focused(node):
    if node.get('focused'):
        print(node.get('app_id', node.get('window_properties', {}).get('class', 'unknown')))
        return
    for n in node.get('nodes', []) + node.get('floating_nodes', []):
        find_focused(n)
find_focused(json.load(sys.stdin))
"
```

### Python i3ipc: Event-Driven Scripting

The `i3ipc` library works with Sway. Install with: `uv pip install i3ipc`

```python
#!/usr/bin/env python3
"""
Auto-rename workspaces based on their window contents.
Run: python3 ~/.config/sway/scripts/workspace-namer.py &
"""
import i3ipc

ICONS = {
    "firefox":          "󰈹",
    "kitty":            "",
    "foot":             "",
    "code":             "󰨞",
    "code-oss":         "󰨞",
    "spotify":          "󰓇",
    "slack":            "󰒱",
    "org.telegram.desktop": "󰔁",
    "mpv":              "󰎁",
    "gimp":             "󰋩",
    "thunar":           "󰉋",
    "discord":          "󰙯",
}

def get_icon(window) -> str:
    app_id = (window.app_id or "").lower()
    wclass = (window.window_class or "").lower()
    for key, icon in ICONS.items():
        if key in app_id or key in wclass:
            return icon
    return "󰣆"

def rename_workspaces(ipc):
    tree = ipc.get_tree()
    for ws in tree.workspaces():
        leaves = ws.leaves()
        if not leaves:
            name = str(ws.num)
        else:
            icons = " ".join(dict.fromkeys(get_icon(w) for w in leaves))
            name = f"{ws.num}: {icons}"
        if ws.name != name:
            ipc.command(f'rename workspace "{ws.name}" to "{name}"')

def on_window(ipc, event):
    rename_workspaces(ipc)

sway = i3ipc.Connection()
sway.on(i3ipc.Event.WINDOW_FOCUS,  on_window)
sway.on(i3ipc.Event.WINDOW_CLOSE,  on_window)
sway.on(i3ipc.Event.WINDOW_MOVE,   on_window)
sway.on(i3ipc.Event.WINDOW_NEW,    on_window)
rename_workspaces(sway)
sway.main()
```

### swayidle: Idle Management

`swayidle` triggers commands after periods of inactivity:

```bash
# ~/.config/sway/config
exec swayidle -w \
    timeout 300  'swaylock -f -c 000000' \
    timeout 600  'swaymsg "output * dpms off"' \
    resume       'swaymsg "output * dpms on"' \
    before-sleep 'swaylock -f -c 000000' \
    lock         'swaylock -f -c 000000'
```

### swaylock: Lock Screen

```bash
# Basic lock
swaylock -f -c 1e1e2e

# Fancy lock with blur (swaylock-effects)
swaylock \
  --screenshots \
  --clock \
  --indicator \
  --indicator-radius 100 \
  --indicator-thickness 7 \
  --effect-blur 7x5 \
  --effect-vignette 0.5:0.5 \
  --ring-color bb00cc \
  --key-hl-color 880033 \
  --line-color 00000000 \
  --inside-color 00000088 \
  --separator-color 00000000 \
  --fade-in 0.2
```

### Gaming Mode Toggle Script

```bash
#!/usr/bin/env bash
# ~/.config/sway/scripts/gaming-mode.sh
# Toggle: disable compositor effects, set performance governor
GAMING_MARKER="/tmp/sway-gaming-mode"

if [[ -f "$GAMING_MARKER" ]]; then
    rm "$GAMING_MARKER"
    swaymsg "gaps inner all set 6"
    swaymsg "gaps outer all set 4"
    swaymsg "default_border pixel 2"
    echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
    notify-send "Gaming mode OFF" "Compositor effects restored"
else
    touch "$GAMING_MARKER"
    swaymsg "gaps inner all set 0"
    swaymsg "gaps outer all set 0"
    swaymsg "default_border none"
    echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
    notify-send "Gaming mode ON" "Gaps and borders disabled"
fi
```

```
# In sway config
bindsym $mod+g exec ~/.config/sway/scripts/gaming-mode.sh
```

---

## 7.6 The Sway Ecosystem

Sway has the most mature ecosystem of any wlroots compositor. These tools are either Sway-specific or designed with Sway as the primary target.

### Waybar

Waybar is the canonical status bar for Sway and the de facto standard for wlroots compositors. It is configured via JSON (modules) and CSS (appearance).

```json
// ~/.config/waybar/config
{
    "layer": "top",
    "position": "top",
    "height": 30,
    "spacing": 4,
    "modules-left":   ["sway/workspaces", "sway/mode", "sway/scratchpad"],
    "modules-center": ["sway/window"],
    "modules-right":  ["mpris", "pulseaudio", "network", "cpu", "memory",
                       "temperature", "battery", "clock", "tray"],
    "sway/workspaces": {
        "disable-scroll": true,
        "all-outputs": true,
        "format": "{icon}",
        "format-icons": {
            "1": "", "2": "󰈹", "3": "", "urgent": "", "default": ""
        }
    },
    "sway/window": { "max-length": 60 },
    "clock": {
        "format": "{:%H:%M}",
        "format-alt": "{:%Y-%m-%d %H:%M:%S}",
        "tooltip-format": "<big>{:%Y %B}</big>\n<tt><small>{calendar}</small></tt>"
    },
    "cpu": { "format": " {usage}%", "tooltip": false },
    "memory": { "format": " {}%" },
    "battery": {
        "states": { "warning": 30, "critical": 15 },
        "format": "{icon} {capacity}%",
        "format-charging": " {capacity}%",
        "format-icons": ["", "", "", "", ""]
    },
    "pulseaudio": {
        "format": "{icon} {volume}%",
        "format-muted": "󰝟",
        "format-icons": { "default": ["", "", ""] },
        "on-click": "pavucontrol"
    },
    "network": {
        "format-wifi": "󰤨 {essid} ({signalStrength}%)",
        "format-ethernet": "󰈀 {ipaddr}",
        "format-disconnected": "󰤭 Disconnected"
    }
}
```

```css
/* ~/.config/waybar/style.css — Catppuccin Mocha theme */
* {
    font-family: "JetBrains Mono Nerd Font", monospace;
    font-size: 13px;
    min-height: 0;
}
window#waybar {
    background-color: rgba(30, 30, 46, 0.95);
    color: #cdd6f4;
    border-bottom: 2px solid #313244;
}
#workspaces button {
    padding: 0 8px;
    color: #6c7086;
    border-radius: 4px;
    margin: 2px;
}
#workspaces button.focused {
    color: #89b4fa;
    background-color: #313244;
}
#workspaces button.urgent {
    color: #f38ba8;
    background-color: #45475a;
}
#clock, #battery, #cpu, #memory, #network, #pulseaudio {
    padding: 0 10px;
    color: #cdd6f4;
}
#battery.warning { color: #fab387; }
#battery.critical { color: #f38ba8; }
```

### Mako: Notification Daemon

Mako is a minimal Wayland notification daemon built for Sway workflows.

```ini
# ~/.config/mako/config
sort=-time
layer=overlay
background-color=#1e1e2eb3
width=320
height=110
border-size=2
border-color=#89b4fa
border-radius=8
icons=1
max-icon-size=48
default-timeout=5000
ignore-timeout=1
font=JetBrains Mono Nerd Font 11
margin=10

[urgency=low]
border-color=#94e2d5

[urgency=normal]
border-color=#89b4fa

[urgency=high]
border-color=#f38ba8
default-timeout=0

[app-name=Spotify]
border-color=#a6e3a1
default-timeout=3000
```

### Wofi: Application Launcher

```ini
# ~/.config/wofi/config
width=600
height=400
location=center
show=drun
prompt=Search...
filter_rate=100
allow_markup=true
no_actions=true
halign=fill
orientation=vertical
content_halign=fill
insensitive=true
allow_images=true
image_size=24
gtk_dark=true
```

```css
/* ~/.config/wofi/style.css */
window { background-color: #1e1e2e; border-radius: 12px; border: 2px solid #313244; }
#input { background-color: #313244; color: #cdd6f4; border: none; border-radius: 8px; padding: 8px 12px; margin: 8px; }
#scroll { margin: 0 8px 8px 8px; }
#entry { padding: 6px 10px; border-radius: 6px; }
#entry:selected { background-color: #313244; }
#text { color: #cdd6f4; }
#text:selected { color: #89b4fa; }
```

### swaybg and Wallpaper Management

```bash
# Set a static wallpaper per output in config
output "*" background ~/Pictures/wallpapers/default.jpg fill

# Dynamic wallpaper rotation script
#!/usr/bin/env bash
# ~/.config/sway/scripts/wallpaper-rotate.sh
WALLPAPER_DIR="$HOME/Pictures/wallpapers"
while true; do
    WALL=$(find "$WALLPAPER_DIR" -type f \( -name "*.jpg" -o -name "*.png" \) | shuf -n1)
    swaymsg "output \"*\" background \"$WALL\" fill"
    sleep 1800  # rotate every 30 minutes
done
```

### Tool Summary Table

| Tool | Purpose | Config Location |
|------|---------|----------------|
| waybar | Status bar | `~/.config/waybar/` |
| mako | Notifications | `~/.config/mako/config` |
| wofi | App launcher | `~/.config/wofi/` |
| swayidle | Idle management | inline in sway config |
| swaylock | Screen lock | CLI args or `~/.config/swaylock/config` |
| swaybg | Wallpaper | inline in sway config |
| swayimg | Image viewer | `~/.config/swayimg/config` |
| foot | Terminal (fast) | `~/.config/foot/foot.ini` |
| wl-clipboard | Clipboard tools | CLI: `wl-copy`, `wl-paste` |
| grim + slurp | Screenshots | CLI |

---

## 7.7 Complete Configuration Examples

### Minimal Functional Config

This config is self-contained: save to `~/.config/sway/config` and launch Sway.

```
# Minimal Sway configuration
set $mod Mod4
set $term foot
set $menu wofi --show drun

# Output
output "*" background #1e1e2e solid_color

# Font
font pango:monospace 10

# Borders and gaps
default_border pixel 2
gaps inner 4

# Core bindings
bindsym $mod+Return exec $term
bindsym $mod+d      exec $menu
bindsym $mod+Shift+q kill
bindsym $mod+Shift+c reload
bindsym $mod+Shift+e exec swaynag -t warning -m 'Exit?' \
    -B 'Yes' 'swaymsg exit'

# Focus
bindsym $mod+h focus left
bindsym $mod+j focus down
bindsym $mod+k focus up
bindsym $mod+l focus right

# Move
bindsym $mod+Shift+h move left
bindsym $mod+Shift+j move down
bindsym $mod+Shift+k move up
bindsym $mod+Shift+l move right

# Workspaces
bindsym $mod+1 workspace number 1
bindsym $mod+2 workspace number 2
bindsym $mod+3 workspace number 3
bindsym $mod+Shift+1 move container to workspace number 1
bindsym $mod+Shift+2 move container to workspace number 2
bindsym $mod+Shift+3 move container to workspace number 3

# Layouts
bindsym $mod+f fullscreen
bindsym $mod+Space floating toggle
bindsym $mod+e layout toggle split
bindsym $mod+b splith
bindsym $mod+v splitv

# Input
input type:touchpad { tap enabled; natural_scroll enabled }
input type:keyboard { xkb_options caps:escape }

# Status bar
bar {
    position top
    status_command while date +'%Y-%m-%d %H:%M:%S'; do sleep 1; done
    colors { statusline #cdd6f4; background #1e1e2e; focused_workspace #89b4fa #313244 #cdd6f4 }
}
```

### Multi-Monitor Development Setup

```
# ~/.config/sway/conf.d/monitors.conf
output DP-1   resolution 2560x1440 refresh 144 position 0,0     scale 1
output eDP-1  resolution 1920x1080 refresh 60  position 320,1440 scale 1

workspace 1  output DP-1   # browser
workspace 2  output DP-1   # editor
workspace 3  output DP-1   # terminal
workspace 4  output DP-1   # docs
workspace 9  output eDP-1  # comms
workspace 10 output eDP-1  # music

for_window [app_id="firefox"]         move to workspace 1
for_window [app_id="code-oss"]        move to workspace 2
for_window [app_id="kitty"]           move to workspace 3
for_window [class="Slack"]            move to workspace 9
for_window [app_id="org.spotify.*"]   move to workspace 10

# Quick workspace switching with mouse buttons
bindsym --whole-window $mod+button4 workspace prev
bindsym --whole-window $mod+button5 workspace next

# Move workspace between outputs
bindsym $mod+ctrl+Left  move workspace to output left
bindsym $mod+ctrl+Right move workspace to output right
```

### Screenshot Bindings

```bash
# Install: pacman -S grim slurp
```

```
# In sway config
bindsym Print                  exec grim ~/Pictures/Screenshots/$(date +%F_%T).png
bindsym $mod+Print             exec grim -g "$(slurp)" ~/Pictures/Screenshots/$(date +%F_%T).png
bindsym $mod+Shift+Print       exec grim -g "$(slurp)" - | wl-copy
bindsym ctrl+Print             exec grim -g "$(swaymsg -t get_tree | \
    python3 -c "import json,sys; \
    t=json.load(sys.stdin); \
    [print(f'{n[\"rect\"][\"x\"]},{n[\"rect\"][\"y\"]} {n[\"rect\"][\"width\"]}x{n[\"rect\"][\"height\"]}') \
    for n in [next(l for l in t[\"nodes\"] if l.get(\"focused\"))]]")" \
    ~/Pictures/Screenshots/$(date +%F_%T).png
```

---

## 7.8 Sway vs. Hyprland: Choosing Your Path

Sway is wlroots-based; Hyprland uses its own Aquamarine backend. Both are tiling compositors with active communities. The choice is not about which is "better" — it is about which tradeoffs serve your workflow.

### Feature Comparison

| Feature | Sway | Hyprland |
|---------|------|----------|
| Config language | i3-compatible text | Custom declarative DSL |
| Animations | None (by design) | Rich, GPU-accelerated |
| Window blur | No | Yes (blur for floating) |
| Rounding | No (not supported natively) | Native border-radius |
| Multi-monitor | Excellent, battle-tested | Excellent, but historically buggier |
| XWayland | Stable | Stable (optional rootful XWayland) |
| Stability | Very high | High (occasional regressions) |
| i3 migration | Drop-in (mostly) | Config rewrite required |
| Plugin system | No (core is frozen) | Yes (C++ ABI plugins) |
| Config hot-reload | Yes (`sway reload`) | Yes |
| Fractional scaling | Limited | Excellent |
| Touch gestures | Basic | Configurable |
| Community | Large, mature | Large, fast-growing |
| Release cadence | Conservative | Frequent |

### When to Choose Sway

- Migrating from i3 and want minimal friction
- Using Sway in a professional or shared environment where stability is critical
- Building automation with i3ipc (full library support)
- Server or headless compositor use cases
- Strongly prefer "works and stays working" over "latest features"

### When to Choose Hyprland

- Starting fresh with no i3 muscle memory to preserve
- Want eye candy: animations, blur, rounded corners
- Need fine-grained per-window animation and rule control
- Running on modern hardware where GPU effects have no cost
- Want a plugin ecosystem to extend the compositor itself

For users who want Hyprland aesthetics but Sway stability: configure Sway with good font rendering (see **Ch 21: Font Rendering and Subpixel Hinting**), use Waybar for a polished bar, and accept that compositor-level blur and animations require a compositor switch. There is no plugin path to add animations to Sway — that is intentional.

See **Ch 08: Hyprland — Eye Candy Compositor** for a deep dive into Hyprland's configuration model, and **Ch 42: Migrating from i3 to Wayland** for a structured migration guide.

---

## 7.9 XWayland Support

XWayland provides backwards compatibility for applications that have not been ported to Wayland. Sway ships with XWayland enabled by default (if built with XWayland support).

```
# Verify XWayland is running
swaymsg -t get_outputs | grep -i xwayland
ps aux | grep Xwayland

# Disable XWayland (for hardened setups)
xwayland disable
```

To identify whether a window is running via XWayland:

```bash
# All windows: XWayland ones show shell="xwayland"
swaymsg -t get_tree | python3 -c "
import json, sys

def walk(node, depth=0):
    if node.get('shell') == 'xwayland':
        print('  ' * depth + f\"XWayland: {node.get('name', '?')} [{node.get('window_properties', {}).get('class', '?')}]\")
    for child in node.get('nodes', []) + node.get('floating_nodes', []):
        walk(child, depth + 1)

walk(json.load(sys.stdin))
"
```

For title bar annotation of XWayland windows (visible reminder):

```
for_window [shell="xwayland"] title_format "[X] %title"
```

---

## Troubleshooting

### Sway Fails to Start

```bash
# Check the log for errors
sway -d 2>&1 | head -50

# Common causes:
# 1. No DRM/KMS device found (check GPU driver)
ls /dev/dri/
modprobe drm

# 2. LIBSEAT not available (logind/seatd not running)
systemctl status logind
systemctl status seatd   # alternative seat manager

# 3. WAYLAND_DISPLAY conflict (Sway already running or stale socket)
echo $WAYLAND_DISPLAY
rm -f /run/user/$UID/wayland-*

# 4. Missing wlroots features (outdated build)
sway --version
```

### Black Screen After Login

This is almost always a missing or wrong environment variable. Ensure these are set before launching Sway from TTY or your display manager:

```bash
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export XDG_SESSION_TYPE=wayland
export XDG_CURRENT_DESKTOP=sway
export MOZ_ENABLE_WAYLAND=1      # Firefox native Wayland
export QT_QPA_PLATFORM=wayland   # Qt apps
export SDL_VIDEODRIVER=wayland   # SDL2 apps (games)
export _JAVA_AWT_WM_NONREPARENTING=1  # Java apps (IntelliJ, etc.)
```

Place these in `~/.config/sway/env` and source from your shell profile, or set them in the sway config with `exec`:

```
exec systemctl --user import-environment WAYLAND_DISPLAY XDG_CURRENT_DESKTOP
exec dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP=sway
```

### GTK Apps Look Wrong / Wrong Theme

```bash
# Install and configure xdg-desktop-portal-wlr for screen sharing
sudo pacman -S xdg-desktop-portal-wlr

# In sway config, ensure GTK wrapper is active (NixOS sets this automatically)
# For other distros: install sway-gtk-cursor-fix or use:
seat seat0 xcursor_theme Adwaita 24

# gsettings for GTK3/4 theme
gsettings set org.gnome.desktop.interface gtk-theme 'adw-gtk3-dark'
gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'
gsettings set org.gnome.desktop.interface cursor-theme 'Bibata-Modern-Classic'
gsettings set org.gnome.desktop.interface cursor-size 24
```

### Waybar Not Showing

```bash
# Check for config syntax errors
waybar --log-level debug 2>&1 | head -30

# Verify the bar is not hidden behind another layer
# In sway config, ensure no other bar directive conflicts
swaymsg -t get_bar_config

# Reload after config edit
swaymsg reload
pkill waybar; waybar &
```

### Input Device Not Responding

```bash
# List all inputs and their identifiers
swaymsg -t get_inputs | python3 -m json.tool

# Test libinput directly
sudo libinput debug-events

# If touchpad not detected, check kernel module
lsmod | grep hid_multitouch
lsmod | grep i2c_hid
```

### Screen Tearing (XWayland apps)

Sway/wlroots uses atomic modesetting which eliminates tearing for Wayland-native apps. XWayland apps may still tear in some driver configurations:

```bash
# Force full-composition pipeline (NVIDIA)
# In /etc/environment or sway config exec:
export __GL_SYNC_TO_VBLANK=1

# For AMD/Intel: ensure DRM vsync is not disabled
cat /sys/module/drm/parameters/vblankoffdelay  # should not be -1
```

### High CPU from sway

```bash
# Profile with perf
sudo perf top -p $(pgrep sway)

# Common causes:
# - Animated terminal (glitchterm, etc) at high frame rate: cap to 60fps
# - Waybar polling too frequently: increase interval values in config
# - i3ipc script in a tight loop: add asyncio.sleep or rate-limit events
```

---

*See also:*
- **Ch 08: Hyprland** — alternative compositor with animation support
- **Ch 21: Font Rendering** — subpixel hinting and font config for Wayland
- **Ch 42: Migrating from i3** — structured migration checklist
- **Ch 53: Session Management** — PAM, logind, and startup ordering
- **Ch 61: Screen Sharing on Wayland** — xdg-desktop-portal-wlr setup
- **Ch 71: Clipboard Management** — wl-clipboard, cliphist, and clipboard history

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
