# Chapter 113 — wlogout and Power Menus

## Contents

- [Overview](#overview)
- [113.1 Installation](#1131-installation)
- [113.2 Layout File](#1132-layout-file)
- [113.3 CSS Styling](#1133-css-styling)
  - [Minimal dark style](#minimal-dark-style)
  - [Cyberpunk neon style](#cyberpunk-neon-style)
- [113.4 Command-Line Flags](#1134-command-line-flags)
- [113.5 Compositor Keybinding](#1135-compositor-keybinding)
- [113.6 Quickshell Power Menu Alternative](#1136-quickshell-power-menu-alternative)
- [113.7 Troubleshooting](#1137-troubleshooting)

---


## Overview

A power menu is the overlay that appears when you press a session-end keybind and presents buttons for shutdown, reboot, lock, suspend, logout, and hibernate. On X11, tools like `rofi -show p` or standalone utilities handled this. On Wayland the canonical solution is **wlogout**: a layer-shell application that renders a fullscreen or panel-style grid of styled buttons, each mapped to a system command.

This chapter covers wlogout installation, layout and CSS configuration, per-aesthetic styling (minimal, Tokyo Night, Cyberpunk), integration into compositor keybindings, and two alternative approaches: a Quickshell QML power menu overlay and nwg-bar for wlroots compositors.

**Cross-references:** Ch 30 — screen lockers invoked by wlogout's lock button. Ch 109 — idle management (wlogout integrates with `loginctl lock-session`). Ch 53 — session startup (compositor keybind to open wlogout).

---

## 113.1 Installation

```bash
# Arch Linux
sudo pacman -S wlogout

# AUR (git version with more button icons)
yay -S wlogout-git

# Ubuntu 24.04+ (build from source — not in Ubuntu repos)
sudo apt install libgtk-layer-shell-dev libgtk-3-dev
git clone https://github.com/ArtsyMacaw/wlogout
cd wlogout && meson build && ninja -C build
sudo install -Dm755 build/wlogout /usr/local/bin/wlogout
```

---

## 113.2 Layout File

wlogout reads `~/.config/wlogout/layout` for button definitions. Each button is a JSON object:

```json
{
    "label" : "lock",
    "action" : "loginctl lock-session",
    "text" : "Lock",
    "keybind" : "l"
}
{
    "label" : "hibernate",
    "action" : "systemctl hibernate",
    "text" : "Hibernate",
    "keybind" : "h"
}
{
    "label" : "logout",
    "action" : "loginctl terminate-user $USER",
    "text" : "Logout",
    "keybind" : "e"
}
{
    "label" : "shutdown",
    "action" : "systemctl poweroff",
    "text" : "Shutdown",
    "keybind" : "s"
}
{
    "label" : "suspend",
    "action" : "systemctl suspend",
    "text" : "Suspend",
    "keybind" : "u"
}
{
    "label" : "reboot",
    "action" : "systemctl reboot",
    "text" : "Reboot",
    "keybind" : "r"
}
```

The `label` value maps to the button's CSS class AND determines which icon wlogout looks for in `~/.config/wlogout/icons/` (PNG files named `lock.png`, `shutdown.png`, etc.). Standard icon names that ship with wlogout: `lock`, `logout`, `suspend`, `hibernate`, `shutdown`, `reboot`.

---

## 113.3 CSS Styling

wlogout uses GTK3 CSS. The full stylesheet lives at `~/.config/wlogout/style.css`.

### Minimal dark style

```css
/* ~/.config/wlogout/style.css — minimal */
* {
    background-image: none;
    box-shadow: none;
}

window {
    background-color: rgba(12, 12, 18, 0.92);
}

button {
    color: #c0caf5;
    background-color: transparent;
    border: 1px solid rgba(122, 162, 247, 0.15);
    border-radius: 8px;
    margin: 8px;
    padding: 12px 24px;
    font-family: "JetBrains Mono Nerd Font";
    font-size: 14px;
    transition: background-color 200ms ease, border-color 200ms ease;
}

button:focus,
button:active,
button:hover {
    background-color: rgba(122, 162, 247, 0.12);
    border-color: rgba(122, 162, 247, 0.5);
    outline: none;
}

/* Individual button accent colors */
#lock     { color: #7dcfff; }
#logout   { color: #e0af68; }
#suspend  { color: #9ece6a; }
#hibernate{ color: #bb9af7; }
#shutdown { color: #f7768e; }
#reboot   { color: #ff9e64; }

#lock:hover     { border-color: rgba(125, 207, 255, 0.5); }
#shutdown:hover { border-color: rgba(247, 118, 142, 0.5); }
#reboot:hover   { border-color: rgba(255, 158, 100, 0.5); }
```

### Cyberpunk neon style

```css
/* ~/.config/wlogout/style.css — cyberpunk */
window {
    background-color: rgba(10, 10, 15, 0.88);
}

button {
    color: #e0e0ff;
    background-color: transparent;
    border: 1px solid rgba(0, 255, 255, 0.2);
    border-radius: 2px;   /* angular — no organic rounding */
    margin: 6px;
    padding: 16px 32px;
    font-family: "Share Tech Mono";
    font-size: 13px;
    letter-spacing: 2px;
    text-transform: uppercase;
    transition: all 120ms linear;
}

button:hover {
    color: #00ffff;
    background-color: rgba(0, 255, 255, 0.08);
    border-color: #00ffff;
    /* GTK doesn't support text-shadow but border glow is achievable */
    box-shadow: 0 0 8px rgba(0, 255, 255, 0.3),
                inset 0 0 8px rgba(0, 255, 255, 0.05);
}

#shutdown:hover { color: #ff003c; border-color: #ff003c;
                  box-shadow: 0 0 8px rgba(255, 0, 60, 0.3); }
#reboot:hover   { color: #ff6e00; border-color: #ff6e00;
                  box-shadow: 0 0 8px rgba(255, 110, 0, 0.3); }
```

---

## 113.4 Command-Line Flags

```bash
# Fullscreen (default)
wlogout

# Panel at the top, 60px tall
wlogout --protocol layer-shell --layout ~/.config/wlogout/layout \
        --css ~/.config/wlogout/style.css \
        --buttons-per-row 6 \
        --column-spacing 10 --row-spacing 10 \
        --margin-top 200 --margin-bottom 200 \
        --margin-left 400 --margin-right 400

# Show margins around the overlay (useful during styling)
wlogout -m 200
```

---

## 113.5 Compositor Keybinding

```ini
# Hyprland — Super+Shift+E opens wlogout
bind = SUPER SHIFT, E, exec, wlogout

# Sway
bindsym $mod+Shift+e exec wlogout
```

To prevent accidental activation, require a confirmation key or add a delay:

```bash
# Wrapper script with brief delay (prevents accidental press)
#!/bin/bash
sleep 0.1
wlogout
```

---

## 113.6 Quickshell Power Menu Alternative

For setups already using Quickshell, a QML overlay avoids spawning a separate process:

```qml
// PowerMenu.qml
import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland

PanelWindow {
    id: powerMenu
    visible: false
    anchors.fill: true   // fullscreen
    color: Qt.rgba(0.05, 0.05, 0.08, 0.92)

    // Close on Escape or click outside buttons
    Keys.onEscapePressed: powerMenu.visible = false

    RowLayout {
        anchors.centerIn: parent
        spacing: 24

        Repeater {
            model: [
                { icon: "󰌾", label: "Lock",     cmd: "loginctl lock-session" },
                { icon: "󰤄", label: "Suspend",  cmd: "systemctl suspend" },
                { icon: "󰍃", label: "Logout",   cmd: "loginctl terminate-user " + Qt.platform.pluginName },
                { icon: "",  label: "Reboot",   cmd: "systemctl reboot" },
                { icon: "⏻",  label: "Shutdown", cmd: "systemctl poweroff" },
            ]

            delegate: Rectangle {
                width: 100; height: 100
                radius: 12
                color: hovered ? Qt.rgba(0.48, 0.64, 0.97, 0.15)
                               : Qt.rgba(1, 1, 1, 0.04)
                border.color: hovered ? "#7aa2f7" : Qt.rgba(1,1,1,0.08)
                border.width: 1
                property bool hovered: false

                Column {
                    anchors.centerIn: parent
                    spacing: 8
                    Text { text: modelData.icon; font.pixelSize: 32;
                           color: "#c0caf5"; anchors.horizontalCenter: parent.horizontalCenter }
                    Text { text: modelData.label; font.pixelSize: 12;
                           color: "#7a7a9e"; anchors.horizontalCenter: parent.horizontalCenter }
                }

                HoverHandler { onHoveredChanged: parent.hovered = hovered }
                TapHandler { onTapped: { Qt.openUrlExternally(""); /* exec the command */
                    Quickshell.exec(modelData.cmd) } }
            }
        }
    }
}
```

---

## 113.7 Troubleshooting

**wlogout opens but buttons are invisible:** GTK icon theme is missing wlogout's icon names. Either install `wlogout-git` (includes bundled icons) or add PNG icons manually to `~/.config/wlogout/icons/`.

**Keybind opens wlogout inside an existing window:** wlogout requires layer-shell support. Verify the compositor supports `zwlr-layer-shell-v1`:
```bash
wayland-info | grep layer_shell
```

**Buttons activate immediately on hover:** A misconfigured `margin` value can cause hover events to fire at the wrong position. Increase `--margin-*` values or add explicit button padding in CSS.
