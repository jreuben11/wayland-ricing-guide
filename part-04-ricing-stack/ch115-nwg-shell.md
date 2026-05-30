# Chapter 115 — The nwg-shell Ecosystem

## Contents

- [Overview](#overview)
- [115.1 Component Overview](#1151-component-overview)
- [115.2 Installation](#1152-installation)
- [115.3 nwg-panel](#1153-nwg-panel)
  - [Basic Configuration](#basic-configuration)
  - [Module Configuration](#module-configuration)
  - [CSS Theming](#css-theming)
  - [Starting nwg-panel](#starting-nwg-panel)
- [115.4 nwg-dock](#1154-nwg-dock)
- [115.5 nwg-drawer](#1155-nwg-drawer)
- [115.6 nwg-look](#1156-nwg-look)
- [115.7 nwg-displays](#1157-nwg-displays)
- [115.8 nwg-hello (greetd greeter)](#1158-nwg-hello-greetd-greeter)
- [115.9 When to Choose nwg-shell](#1159-when-to-choose-nwg-shell)

---


## Overview

nwg-shell is a collection of GTK-based Wayland tools authored by Piotr Miller (nwg-piotr), designed to give wlroots compositors (Sway, Hyprland, River, labwc) a cohesive application layer without depending on a full desktop environment. Where Waybar provides a single bar and Quickshell provides a QML runtime, nwg-shell provides an opinionated but configurable suite: a bar, a dock, a full-screen app drawer, a display management GUI, a GTK settings manager, a screen locker, and a login greeter.

The suite's defining characteristic is that every component is written in Python + GTK3/GTK4 using `gtk-layer-shell`, making it trivially themeable with standard GTK CSS and compatible with any compositor that supports `zwlr-layer-shell-v1`.

**Cross-references:** Ch 26 — bar comparison (nwg-panel vs Waybar vs eww). Ch 33 — display config (nwg-displays as a GUI frontend). Ch 54 — display managers (nwg-hello as a greetd greeter).

---

## 115.1 Component Overview

| Tool | Purpose | Replaces |
|---|---|---|
| `nwg-panel` | Configurable GTK bar with built-in modules | Waybar (GTK-native alternative) |
| `nwg-dock` | Auto-hide application dock (bottom/side) | Plank, Cairo-Dock |
| `nwg-drawer` | Fullscreen application drawer/launcher | Rofi (app drawer mode) |
| `nwg-look` | GTK theme/icon/cursor/font settings GUI | lxappearance |
| `nwg-displays` | Monitor layout GUI (drag-and-drop) | arandr (Wayland-native) |
| `nwg-hello` | greetd login greeter | tuigreet, ReGreet |
| `nwg-bar` | Simple vertical/horizontal icon bar | — |
| `nwg-clipman` | Clipboard manager | cliphist |
| `nwg-readme-help` | Per-compositor keybinds help overlay | — |

---

## 115.2 Installation

```bash
# Arch Linux — individual packages
sudo pacman -S nwg-panel nwg-dock nwg-drawer nwg-look nwg-displays

# AUR extras
yay -S nwg-hello nwg-bar nwg-clipman

# Ubuntu — build from source (not in Ubuntu repos)
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 \
     libgtk-layer-shell-dev python3-psutil python3-i3ipc
pip install nwg-panel  # installs nwg-panel and dependencies
```

---

## 115.3 nwg-panel

nwg-panel reads `~/.config/nwg-panel/config` (JSON) and renders a bar composed of configurable modules. Unlike Waybar's JSON, nwg-panel's config uses a list of panel definitions, each with a list of modules.

### Basic Configuration

```json
[
  {
    "name": "panel-top",
    "output": "",
    "layer": "top",
    "position": "top",
    "height": 36,
    "width": 0,
    "margin-top": 0,
    "margin-bottom": 0,
    "padding-horizontal": 6,
    "padding-vertical": 0,
    "spacing": 0,
    "items-padding": 0,
    "icons": "light",
    "css-name": "panel-top",
    "modules-left": ["hyprland-workspaces", "hyprland-taskbar"],
    "modules-center": ["clock"],
    "modules-right": ["playerctl", "tray", "sway-mode", "battery",
                       "brightness", "pvol", "net-interface"]
  }
]
```

### Module Configuration

Each module has its own config section (JSON file in `~/.config/nwg-panel/`):

```json
// ~/.config/nwg-panel/hyprland-workspaces
{
  "show-icon": false,
  "image-size": 16,
  "show-name": true,
  "mark-autotiling": true,
  "mark-content": true,
  "show-empty": true,
  "num-ws": 10
}
```

```json
// ~/.config/nwg-panel/clock
{
  "format": "%H:%M  %a, %d %b",
  "tooltip-text": "",
  "on-left-click": "",
  "on-middle-click": "",
  "on-right-click": "",
  "on-scroll-up": "",
  "on-scroll-down": "",
  "css-name": "clock",
  "interval": 30,
  "tooltip-date-format": false
}
```

### CSS Theming

nwg-panel uses standard GTK CSS at `~/.config/nwg-panel/style.css`:

```css
/* Tokyo Night theme for nwg-panel */
* {
    font-family: "JetBrains Mono Nerd Font";
    font-size: 13px;
    background: transparent;
}

#panel-top {
    background-color: rgba(26, 27, 38, 0.90);
    border-bottom: 1px solid rgba(122, 162, 247, 0.15);
    color: #c0caf5;
}

#clock {
    color: #7dcfff;
    padding: 0 12px;
    font-weight: bold;
}

button.workspace-button {
    color: #444b6a;
    border-radius: 6px;
    padding: 2px 8px;
    margin: 2px;
    transition: all 200ms ease;
}

button.workspace-button:active,
button.workspace-button.focused {
    color: #7aa2f7;
    background-color: rgba(122, 162, 247, 0.15);
}

#battery { color: #9ece6a; }
#brightness { color: #e0af68; }
```

### Starting nwg-panel

```bash
# Direct launch
nwg-panel &

# Hyprland exec-once
exec-once = nwg-panel
```

---

## 115.4 nwg-dock

nwg-dock is a taskbar-style dock that shows pinned launchers and running applications. It auto-hides when a window approaches it.

```bash
nwg-dock \
    --layer top \
    --position bottom \
    --icon-size 48 \
    --items-padding 4 \
    --margin 8 \
    --autohide 200   # hide after 200ms out-of-focus
```

Pin applications in `~/.config/nwg-dock/dock.json`:

```json
[
    {"name": "thunar", "exec": "thunar"},
    {"name": "firefox", "exec": "firefox"},
    {"name": "kitty", "exec": "kitty"},
    {"name": "code", "exec": "code"}
]
```

CSS theming at `~/.config/nwg-dock/style.css`:

```css
#box {
    background-color: rgba(26, 27, 38, 0.88);
    border-radius: 12px;
    border: 1px solid rgba(122, 162, 247, 0.12);
    padding: 4px;
    margin: 4px;
}

button {
    border-radius: 8px;
    padding: 4px;
    margin: 2px;
    transition: background-color 150ms ease;
}

button:hover {
    background-color: rgba(122, 162, 247, 0.15);
}
```

---

## 115.5 nwg-drawer

nwg-drawer is a fullscreen application launcher that reads from `.desktop` files. It shows all installed applications with category filtering.

```bash
# Open the drawer (bind to a key)
nwg-drawer \
    --columns 6 \
    --item-size 72 \
    --icon-size 48 \
    --search   # show search box immediately

# Hyprland keybind
bind = SUPER, A, exec, nwg-drawer
```

Configuration at `~/.config/nwg-drawer/drawer.json`:

```json
{
  "columns": 6,
  "icon-size": 64,
  "icon-size-small": 16,
  "margin": 20,
  "padding": 2,
  "categories": true,
  "resident": false,
  "no-search": false,
  "source": "",
  "term": "foot",
  "lang": ""
}
```

CSS theming at `~/.config/nwg-drawer/style.css`:

```css
window {
    background-color: rgba(26, 27, 38, 0.92);
    color: #c0caf5;
}

entry {
    background-color: rgba(47, 53, 73, 0.6);
    color: #c0caf5;
    border: 1px solid rgba(122, 162, 247, 0.3);
    border-radius: 8px;
    padding: 6px 12px;
}

button.app-btn {
    border-radius: 10px;
    padding: 8px;
    transition: background-color 150ms;
}

button.app-btn:hover {
    background-color: rgba(122, 162, 247, 0.12);
}

label.app-label { font-size: 11px; color: #787c99; }
```

---

## 115.6 nwg-look

nwg-look is a GTK settings manager for Wayland — the lxappearance equivalent. It writes to `~/.config/gtk-3.0/settings.ini` and `~/.config/gtk-4.0/settings.ini` and applies changes live.

```bash
# Launch
nwg-look
```

nwg-look provides GUI controls for:
- GTK theme selection (reads themes from `~/.local/share/themes/` and `/usr/share/themes/`)
- Icon theme selection
- Cursor theme and size
- Font (family, size)
- Antialiasing and hinting options

For ricing purposes, nwg-look is the quickest way to preview GTK themes without editing config files manually. It does not replace the programmatic configuration in Ch 35 but is a useful companion tool.

---

## 115.7 nwg-displays

nwg-displays is a graphical monitor layout manager. It reads from and writes to kanshi configuration, making it the GUI frontend for monitor arrangement.

```bash
# Launch
nwg-displays

# Apply a layout after arranging monitors in the GUI
nwg-displays --apply
```

It generates `~/.config/kanshi/config` entries from the GUI layout. For compositors with native display management (Hyprland's `monitor =` directives), nwg-displays can also write directly to the compositor's format via its output adapter.

---

## 115.8 nwg-hello (greetd greeter)

nwg-hello is a GTK-based greeter for greetd. It renders a login screen with user selection, session selector (Wayland compositors), and optional background image.

```toml
# /etc/greetd/config.toml
[terminal]
vt = 1

[default_session]
command = "nwg-hello"
user = "greeter"
```

```ini
# /etc/nwg-hello/nwg-hello.toml
[general]
background = "/usr/share/backgrounds/nwg-hello/background.jpg"
form-background = true
timeout = 0

[[user]]
name = "alice"
session = "hyprland"
```

---

## 115.9 When to Choose nwg-shell

| Scenario | Best choice |
|---|---|
| Sway user who wants GTK-native tools | nwg-panel + nwg-dock |
| Hyprland user who wants Waybar features | Waybar (better Hyprland IPC integration) |
| Hyprland user who wants QML animations | Quickshell |
| Need a display management GUI | nwg-displays (any compositor) |
| Need to configure GTK themes interactively | nwg-look (any compositor) |
| greetd + themed login screen | nwg-hello |
| Minimal KISS compositor (labwc, River) | nwg-panel + nwg-drawer |

nwg-shell tools have lighter resource footprints than Quickshell (no QML engine) and are easier to theme for GTK-native consistency than Waybar (they *are* GTK). The tradeoff is that nwg-panel has fewer modules than Waybar and nwg-drawer's animation capabilities are limited compared to Quickshell's QML scene graph.
