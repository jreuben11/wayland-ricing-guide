# Chapter 134 — Miracle-WM: Ubuntu's Tiling Wayland Compositor

## Overview

Miracle-WM is a tiling Wayland compositor built on Mir (the display server library maintained by Canonical) and designed to bring i3-compatible tiling to the Ubuntu ecosystem. Unlike wlroots-based compositors (Sway, Hyprland, River), it uses Mir as its compositor backend, giving it first-class Ubuntu/Snap support while maintaining i3-style keybinding conventions. This chapter covers installation, configuration, keybinding layout, status bar integration, and a comparison to Sway — the most natural point of reference.

**Cross-references:** Ch 06 — compositor taxonomy. Ch 07 — Sway (closest conceptual peer). Ch 13 — compositor zoo (overview entry). Ch 14 — compositor selection guide.

---

## 134.1 What is Miracle-WM?

Miracle-WM positions itself as an i3-for-Ubuntu story:

- **Backend**: Mir (Canonical's display server library), not wlroots
- **Configuration**: YAML-based (not i3's native format, but conceptually similar)
- **Tiling**: Manual tiling with splits (vertical/horizontal), like i3/Sway
- **Workspaces**: Named workspaces, binding to outputs
- **Keybindings**: Similar to i3 by default (Super+Enter for terminal, etc.)
- **XWayland**: Supported via Mir's XWayland integration
- **Status bar**: i3bar JSON protocol support (works with i3status, i3status-rust, bumblebee-status)

### Why it exists

Canonical uses Mir as the foundation for Ubuntu Frame (IoT/kiosk displays) and Ubuntu Core. Miracle-WM extends this toward a desktop compositor, targeting Ubuntu users who want tiling without moving to Arch-centric compositors. In 2025 it reached a usable 0.x release.

---

## 134.2 Installation

### Snap (recommended on Ubuntu)

```bash
# Install from Snap Store
sudo snap install miracle-wm --classic

# Verify
miracle-wm --version
```

### PPA (Ubuntu 24.04+)

```bash
sudo add-apt-repository ppa:mir-team/release
sudo apt update
sudo apt install miracle-wm

# Optional: i3status for the bar
sudo apt install i3status
```

### Arch AUR

```bash
yay -S miracle-wm
```

### From Source

```bash
# Dependencies
sudo apt install cmake libmir-dev libglib2.0-dev \
    libxkbcommon-dev libinput-dev libudev-dev \
    libpixman-1-dev libcairo2-dev pkg-config

git clone https://github.com/canonical/miracle-wm
cd miracle-wm
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)
sudo cmake --install build
```

---

## 134.3 Starting Miracle-WM

```bash
# From a TTY (start a new Wayland session)
miracle-wm

# From a display manager (GDM/SDDM)
# Miracle-WM installs a .desktop session file:
# /usr/share/wayland-sessions/miracle-wm.desktop

# Test in a nested window (within another compositor)
WAYLAND_DISPLAY=wayland-99 miracle-wm --nested

# With a custom config file
miracle-wm --config ~/.config/miracle-wm/config.yaml
```

---

## 134.4 Configuration

```yaml
# ~/.config/miracle-wm/config.yaml

# Action key (modifier)
action_key: meta   # "meta" = Super/Windows key, "alt" = Alt

# Terminal emulator
terminal: foot    # used by action_key+Enter

# Startup applications
startup_apps:
  - command: waybar
    type: wayland    # or "x11"
  - command: swaybg -i ~/Pictures/wallpaper.jpg -m fill
    type: wayland

# Workspaces (named)
workspaces:
  - 1
  - 2
  - 3
  - 4
  - 5
  - 6
  - 7
  - 8
  - 9
  - 0

# Default gap between windows (pixels)
gap_size: 8

# Border
border:
  size: 2
  focus_color:   "#7aa2f7"   # active window border
  unfocus_color: "#292e42"   # inactive window border

# Animation
animation:
  enabled: true
  duration: 250   # ms
```

### Custom Keybindings

```yaml
# ~/.config/miracle-wm/config.yaml (keybindings section)
keybindings:
  # Launch terminal
  - key: enter
    modifiers: [meta]
    action: terminal

  # Launch launcher (any dmenu-compatible)
  - key: d
    modifiers: [meta]
    action:
      command: fuzzel

  # Close focused window
  - key: q
    modifiers: [meta, shift]
    action: close

  # Toggle floating
  - key: space
    modifiers: [meta, shift]
    action: toggle_floating

  # Focus direction (vim keys)
  - key: h
    modifiers: [meta]
    action: focus_left
  - key: j
    modifiers: [meta]
    action: focus_down
  - key: k
    modifiers: [meta]
    action: focus_up
  - key: l
    modifiers: [meta]
    action: focus_right

  # Move window
  - key: h
    modifiers: [meta, shift]
    action: move_left
  - key: j
    modifiers: [meta, shift]
    action: move_down
  - key: k
    modifiers: [meta, shift]
    action: move_up
  - key: l
    modifiers: [meta, shift]
    action: move_right

  # Split direction
  - key: b
    modifiers: [meta]
    action: split_horizontal
  - key: v
    modifiers: [meta]
    action: split_vertical

  # Fullscreen
  - key: f
    modifiers: [meta]
    action: fullscreen

  # Workspace switching
  - key: "1"
    modifiers: [meta]
    action: workspace 1
  - key: "2"
    modifiers: [meta]
    action: workspace 2
  # ... repeat for 3-0

  # Move window to workspace
  - key: "1"
    modifiers: [meta, shift]
    action: move_to_workspace 1
  # ... repeat for 2-0

  # Resize mode
  - key: r
    modifiers: [meta]
    action: resize_mode

  # Quit compositor
  - key: Escape
    modifiers: [meta, shift]
    action: quit
```

---

## 134.5 Status Bar Integration

Miracle-WM supports the i3bar JSON protocol, making it compatible with any bar that speaks i3bar:

### waybar (recommended)

```json
// ~/.config/waybar/config — miracle-wm sections
{
    "layer": "top",
    "position": "top",
    "height": 36,

    "modules-left":   ["miracle-wm/workspaces"],
    "modules-center": ["clock"],
    "modules-right":  ["cpu", "memory", "pulseaudio", "battery", "clock"],

    "miracle-wm/workspaces": {
        "format":          "{name}",
        "on-click":        "activate",
        "format-icons": {
            "urgent":  "",
            "focused": "",
            "default": ""
        }
    }
}
```

### i3status-rust

```toml
# ~/.config/i3status-rust/config.toml
# (standard config — miracle-wm reads via i3bar protocol)

[[block]]
block = "time"
format = " $timestamp.datetime(f:'%H:%M  %a %d %b') "

[[block]]
block = "cpu"
format = " $utilization "

[[block]]
block = "memory"

[[block]]
block = "battery"
```

Launch with miracle-wm's bar configuration in `config.yaml`:
```yaml
startup_apps:
  - command: i3bar --bar_id=bar0 -c ~/.config/miracle-wm/i3bar.json
    type: wayland
```

---

## 134.6 Layout Model

Miracle-WM uses the same binary space partitioning as i3/Sway:

```
Workspace 1:
┌─────────────────────────────────────┐
│ Terminal            │ Browser       │
│                     │               │
│  (focused)          │               │
├─────────────────────┼───────────────┤
│ File Manager        │ Editor        │
│                     │               │
└─────────────────────┴───────────────┘
```

- **Split horizontal** (`meta+b`): Next window appears to the right
- **Split vertical** (`meta+v`): Next window appears below
- **Layout toggle** (`meta+e`): Toggle between split-h and split-v for container
- **Stacking** (`meta+s`): Stack windows in a container (like i3 stacking)
- **Tabbed** (`meta+w`): Tab container

Floating windows:
```yaml
# Float specific apps via keybinding
- key: space
  modifiers: [meta, shift]
  action: toggle_floating
```

Or via app rules (in 0.x, rules are limited; check current release for `window_rules` support):
```yaml
window_rules:
  - app_id: "pavucontrol"
    floating: true
  - app_id: ".*dialog.*"
    floating: true
```

---

## 134.7 Output Configuration

```yaml
outputs:
  - name: eDP-1            # laptop screen
    mode: 1920x1080@60
    scale: 1.0
    position: "0,0"

  - name: HDMI-A-1         # external monitor
    mode: 2560x1440@144
    scale: 1.0
    position: "1920,0"

  # Workspace-to-output binding
workspace_output:
  "1": eDP-1
  "2": eDP-1
  "3": HDMI-A-1
  "4": HDMI-A-1
```

---

## 134.8 Comparison: Miracle-WM vs Sway vs Hyprland

| Feature | Miracle-WM | Sway | Hyprland |
|---|---|---|---|
| Backend | Mir | wlroots | wlroots (custom) |
| Config format | YAML | i3-like text | INI-like text |
| Tiling model | Manual (BSP) | Manual (BSP) | Manual + auto |
| Animations | Basic | None (plugin needed) | Full system |
| Blur / effects | Planned | Via wf-comp patches | Yes |
| XWayland | Yes (Mir) | Yes | Yes |
| Status bar | i3bar + Waybar | Swaybar + Waybar | Waybar + all |
| Plugin system | No | No | Yes (hyprpm) |
| Window rules | Basic (0.x) | Full | Full (v2) |
| Ubuntu integration | First-class | Good | Requires config |
| Snap support | Native | Limited | Limited |
| GPU drivers | Mesa / Mir | Mesa | Mesa |
| Community size | Small (2025) | Large | Very large |
| Stability | Beta (0.x) | Stable | Stable |

### When to choose Miracle-WM

- Running Ubuntu and want tight snap/Ubuntu integration
- Already familiar with i3 and don't want to relearn
- Want to avoid wlroots dependency tree
- Contributing to the Canonical Mir ecosystem

### When to choose Sway instead

- Need a proven, stable compositor
- Large configuration community and examples
- Requires full Waybar ecosystem compatibility
- Need advanced window rules

---

## 134.9 Known Limitations (2025)

As of the 0.x releases:

- No blur or transparency effects (Mir doesn't expose wlroots shader pipeline)
- Window rules are basic — no per-title rules comparable to Hyprland windowrulev2
- No scratchpad (in development)
- Limited layer-shell support for custom bars
- No screen magnification
- Status bar integration requires i3bar protocol (Waybar has experimental support)
- No equivalent of Hyprland's `hyprctl dispatch` IPC richness

Check the [GitHub releases](https://github.com/canonical/miracle-wm/releases) for the current feature set, as it evolves rapidly.

---

## 134.10 Troubleshooting

```bash
# Launch with verbose logging
miracle-wm --log-level=debug 2>~/miracle-wm.log

# Check Mir environment
echo $WAYLAND_DISPLAY   # should be set after startup

# Verify XWayland
DISPLAY=:0 xterm   # should open in miracle-wm

# Check i3bar connection
miracle-wm --version
# If bar doesn't appear, check startup_apps command path

# Reset config to defaults
mv ~/.config/miracle-wm/config.yaml ~/.config/miracle-wm/config.yaml.bak
miracle-wm   # starts with built-in defaults
```
