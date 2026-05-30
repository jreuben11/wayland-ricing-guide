# Chapter 106 — Automated Theme Switching

## Contents

- [Overview](#overview)
- [106.1 Theme Directory Structure](#1061-theme-directory-structure)
  - [`theme.env` — theme variables](#themeenv-theme-variables)
- [106.2 The Switch Script](#1062-the-switch-script)
  - [Hyprland keybind](#hyprland-keybind)
- [106.3 Hyprland Colour Config Files](#1063-hyprland-colour-config-files)
- [106.4 Alacritty with Theme Include](#1064-alacritty-with-theme-include)
- [106.5 Time-Based Auto-Switching with systemd](#1065-time-based-auto-switching-with-systemd)
  - [Timers for dark/light mode](#timers-for-darklight-mode)
  - [Geoclue-aware switching (sunrise/sunset by location)](#geoclue-aware-switching-sunrisesunset-by-location)
- [106.6 Quickshell Reactive Theme](#1066-quickshell-reactive-theme)
- [106.7 NixOS: Declarative Theme Switching](#1067-nixos-declarative-theme-switching)

---


## Overview

A static rice is good. A rice that flips between a light and dark theme in one
keypress — and correctly updates every running app at once — is better. This
chapter covers the architecture for multi-theme setups: per-theme directories,
an atomic switch script, time-based auto-switching with systemd timers, and
reactive Quickshell components that follow theme changes.

## Installation

Most tools used in this chapter are built into your existing compositor or desktop environment (`hyprctl`, `gsettings`, `systemctl`). The optional geolocation-aware switching requires:

**Projects:** https://gitlab.freedesktop.org/geoclue/geoclue · https://github.com/nwg-piotr/nwg-look

```bash
# Arch Linux
sudo pacman -S geoclue    # geolocation daemon for sunrise/sunset switching
sudo pacman -S glib2      # provides gsettings (usually already installed)
# hyprctl is bundled with: sudo pacman -S hyprland

# Nix
nix-env -iA nixpkgs.geoclue
# home-manager: services.geoclue2.enable = true;
```

---

## 106.1 Theme Directory Structure

Organise themes as named directories, each containing config files or symlink
targets for every theming layer:

```
~/.config/themes/
├── active -> mocha/           ← symlink to currently active theme
├── mocha/                     ← Catppuccin Mocha (dark)
│   ├── theme.env              ← shell variables for this theme
│   ├── hyprland-colors.conf   ← border/decoration colours
│   ├── waybar.css             ← bar stylesheet
│   ├── mako.conf              ← notification colours
│   ├── alacritty.toml         ← terminal colours
│   ├── quickshell-theme.qml   ← Quickshell palette
│   └── wallpaper.jpg          ← wallpaper for this theme
├── latte/                     ← Catppuccin Latte (light)
│   ├── theme.env
│   ├── hyprland-colors.conf
│   └── ...
├── gruvbox-dark/
│   └── ...
└── tokyo-night/
    └── ...
```

### `theme.env` — theme variables

```bash
# ~/.config/themes/mocha/theme.env
THEME_NAME="catppuccin-mocha"
THEME_VARIANT="dark"

# Colours (used by scripts and templates)
BASE="#1e1e2e"
SURFACE="#313244"
TEXT="#cdd6f4"
ACCENT="#89b4fa"
MAUVE="#cba6f7"
RED="#f38ba8"
GREEN="#a6e3a1"
YELLOW="#f9e2af"

WALLPAPER="$HOME/.config/themes/mocha/wallpaper.jpg"
WAYBAR_CSS="$HOME/.config/themes/mocha/waybar.css"
MAKO_CONF="$HOME/.config/themes/mocha/mako.conf"
ALACRITTY_TOML="$HOME/.config/themes/mocha/alacritty.toml"
CURSOR_THEME="Catppuccin-Mocha-Dark-Cursors"
CURSOR_SIZE=24
```

---

## 106.2 The Switch Script

```bash
#!/bin/bash
# ~/.config/themes/switch-theme.sh
# Usage: switch-theme.sh <theme-name>
#        switch-theme.sh --toggle   (cycles through a list)
#        switch-theme.sh --next / --prev

set -euo pipefail

THEMES_DIR="$HOME/.config/themes"
ACTIVE_LINK="$THEMES_DIR/active"
TOGGLE_ORDER=(mocha latte gruvbox-dark tokyo-night)
STATE_FILE="/tmp/theme-current"

# ── resolve target theme ────────────────────────────────────────────────────

case "${1:-}" in
    --toggle|--next)
        current=$(cat "$STATE_FILE" 2>/dev/null || echo "${TOGGLE_ORDER[0]}")
        idx=0
        for i in "${!TOGGLE_ORDER[@]}"; do
            [[ "${TOGGLE_ORDER[$i]}" == "$current" ]] && idx=$i
        done
        next_idx=$(( (idx + 1) % ${#TOGGLE_ORDER[@]} ))
        TARGET="${TOGGLE_ORDER[$next_idx]}"
        ;;
    --prev)
        current=$(cat "$STATE_FILE" 2>/dev/null || echo "${TOGGLE_ORDER[0]}")
        idx=0
        for i in "${!TOGGLE_ORDER[@]}"; do
            [[ "${TOGGLE_ORDER[$i]}" == "$current" ]] && idx=$i
        done
        prev_idx=$(( (idx - 1 + ${#TOGGLE_ORDER[@]}) % ${#TOGGLE_ORDER[@]} ))
        TARGET="${TOGGLE_ORDER[$prev_idx]}"
        ;;
    --dark)  TARGET="mocha" ;;
    --light) TARGET="latte" ;;
    *)       TARGET="${1:?Usage: switch-theme.sh <theme>}" ;;
esac

THEME_DIR="$THEMES_DIR/$TARGET"
[[ -d "$THEME_DIR" ]] || { echo "Theme '$TARGET' not found"; exit 1; }

# Load theme variables
# shellcheck source=/dev/null
source "$THEME_DIR/theme.env"

echo "Switching to: $THEME_NAME"

# ── 1. Update symlink ────────────────────────────────────────────────────────
ln -sfn "$THEME_DIR" "$ACTIVE_LINK"
echo "$TARGET" > "$STATE_FILE"

# ── 2. Wallpaper ─────────────────────────────────────────────────────────────
if command -v swww &>/dev/null && swww query &>/dev/null; then
    swww img "$WALLPAPER" \
        --transition-type wipe \
        --transition-duration 1.0 \
        --transition-angle 30
else
    hyprctl keyword misc:wallpaper "$WALLPAPER" 2>/dev/null || true
fi

# ── 3. Hyprland border colours ───────────────────────────────────────────────
if [[ -f "$THEME_DIR/hyprland-colors.conf" ]]; then
    # Source the colour config and apply via hyprctl keyword
    while IFS='=' read -r key value; do
        [[ "$key" =~ ^[[:space:]]*# ]] && continue
        [[ -z "$key" ]] && continue
        hyprctl keyword "$key" "$value" 2>/dev/null || true
    done < "$THEME_DIR/hyprland-colors.conf"
fi

# Direct colour application:
hyprctl keyword "general:col.active_border"   "rgba(${ACCENT:1}ee) rgba(${MAUVE:1}ee) 45deg"
hyprctl keyword "general:col.inactive_border" "rgba(${SURFACE:1}aa)"

# ── 4. Waybar ────────────────────────────────────────────────────────────────
if [[ -f "$WAYBAR_CSS" ]]; then
    ln -sf "$WAYBAR_CSS" "$HOME/.config/waybar/style.css"
    pkill -SIGUSR2 waybar 2>/dev/null || true   # reload style without restart
fi

# ── 5. Mako (notifications) ──────────────────────────────────────────────────
if [[ -f "$MAKO_CONF" ]]; then
    ln -sf "$MAKO_CONF" "$HOME/.config/mako/config"
    makoctl reload 2>/dev/null || true
fi

# ── 6. Terminal (Alacritty) ──────────────────────────────────────────────────
if [[ -f "$ALACRITTY_TOML" ]]; then
    ln -sf "$ALACRITTY_TOML" "$HOME/.config/alacritty/active-theme.toml"
    # Alacritty hot-reloads file changes automatically
fi

# ── 7. GTK theme ─────────────────────────────────────────────────────────────
if [[ "$THEME_VARIANT" == "dark" ]]; then
    gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'
else
    gsettings set org.gnome.desktop.interface color-scheme 'prefer-light'
fi

# ── 8. Cursor ────────────────────────────────────────────────────────────────
hyprctl setcursor "$CURSOR_THEME" "$CURSOR_SIZE" 2>/dev/null || true
gsettings set org.gnome.desktop.interface cursor-theme "$CURSOR_THEME"
gsettings set org.gnome.desktop.interface cursor-size  "$CURSOR_SIZE"

# ── 9. pywal re-generation (optional, if using pywal) ────────────────────────
if command -v wal &>/dev/null; then
    wal -i "$WALLPAPER" --backend colorz -q &
fi

# ── 10. Quickshell hot-reload ────────────────────────────────────────────────
if command -v qs &>/dev/null; then
    qs msg reload 2>/dev/null || true
fi

# ── 11. Write current theme to a file Quickshell can watch ──────────────────
echo "$TARGET" > /tmp/active-theme
echo "$THEME_NAME" >> /tmp/active-theme-info
cat "$THEME_DIR/theme.env" >> /tmp/active-theme-info

notify-send "Theme" "Switched to $THEME_NAME" --icon preferences-desktop-theme 2>/dev/null || true
echo "Done: $THEME_NAME"
```

```bash
chmod +x ~/.config/themes/switch-theme.sh
```

### Hyprland keybind

```conf
# hyprland.conf
bind = SUPER SHIFT, T, exec, ~/.config/themes/switch-theme.sh --toggle
bind = SUPER CTRL,  D, exec, ~/.config/themes/switch-theme.sh --dark
bind = SUPER CTRL,  L, exec, ~/.config/themes/switch-theme.sh --light
```

---

## 106.3 Hyprland Colour Config Files

Each theme has a `hyprland-colors.conf` with colour-only settings:

```conf
# ~/.config/themes/mocha/hyprland-colors.conf
general:col.active_border   = rgba(89b4faee) rgba(cba6f7ee) 45deg
general:col.inactive_border = rgba(313244aa)
decoration:col.shadow       = rgba(1e1e2eee)
```

```conf
# ~/.config/themes/latte/hyprland-colors.conf
general:col.active_border   = rgba(1e66f5ee) rgba(8839efee) 45deg
general:col.inactive_border = rgba(9ca0b0aa)
decoration:col.shadow       = rgba(eff1f5ee)
```

Source from main `hyprland.conf`:
```conf
# hyprland.conf
source = ~/.config/themes/active/hyprland-colors.conf
```

---

## 106.4 Alacritty with Theme Include

Alacritty supports `import` for splitting config:

```toml
# ~/.config/alacritty/alacritty.toml
import = ["~/.config/alacritty/active-theme.toml"]

[font]
normal = { family = "JetBrainsMono Nerd Font Mono", style = "Regular" }
size = 13.0
```

The switch script symlinks `active-theme.toml` to the correct file. Alacritty
watches the import and reloads automatically when the symlink target changes.

---

## 106.5 Time-Based Auto-Switching with systemd

### Timers for dark/light mode

```ini
# ~/.config/systemd/user/theme-dark.service
[Unit]
Description=Switch to dark theme

[Service]
Type=oneshot
Environment=WAYLAND_DISPLAY=wayland-1
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
ExecStart=%h/.config/themes/switch-theme.sh --dark
```

```ini
# ~/.config/systemd/user/theme-dark.timer
[Unit]
Description=Switch to dark theme at sunset

[Timer]
OnCalendar=*-*-* 20:00:00   # 8 PM daily
Persistent=true

[Install]
WantedBy=timers.target
```

```ini
# ~/.config/systemd/user/theme-light.service
[Unit]
Description=Switch to light theme

[Service]
Type=oneshot
Environment=WAYLAND_DISPLAY=wayland-1
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
ExecStart=%h/.config/themes/switch-theme.sh --light
```

```ini
# ~/.config/systemd/user/theme-light.timer
[Unit]
Description=Switch to light theme at sunrise

[Timer]
OnCalendar=*-*-* 07:30:00   # 7:30 AM daily
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
systemctl --user enable --now theme-dark.timer
systemctl --user enable --now theme-light.timer
```

### Geoclue-aware switching (sunrise/sunset by location)

```bash
#!/bin/bash
# ~/.config/themes/auto-theme.sh
# Called from a timer; uses redshift-like location awareness

LATITUDE=40.7
LONGITUDE=-74.0

# Calculate current sun position (simplified)
HOUR=$(date +%H)
MONTH=$(date +%m)

# Simple heuristic: summer vs winter hours
if [[ $MONTH -ge 4 && $MONTH -le 9 ]]; then
    SUNRISE=6; SUNSET=20
else
    SUNRISE=7; SUNSET=17
fi

if [[ $HOUR -ge $SUNRISE && $HOUR -lt $SUNSET ]]; then
    ~/.config/themes/switch-theme.sh --light
else
    ~/.config/themes/switch-theme.sh --dark
fi
```

---

## 106.6 Quickshell Reactive Theme

Write the current theme name to `/tmp/active-theme` (the switch script does
this) and have Quickshell watch it:

```qml
// Theme.qml
pragma Singleton
import Quickshell
import Quickshell.Io

Singleton {
    id: root

    property string name:    "mocha"
    property bool   isDark:  true

    // Colours (updated when theme changes)
    property color base:    "#1e1e2e"
    property color surface: "#313244"
    property color text:    "#cdd6f4"
    property color accent:  "#89b4fa"
    property color mauve:   "#cba6f7"
    property color red:     "#f38ba8"
    property color green:   "#a6e3a1"

    FileView {
        path: "/tmp/active-theme"
        watchChanges: true
        onTextChanged: root._applyTheme(text.trim())
    }

    function _applyTheme(themeName) {
        name = themeName
        // Load colours for the new theme
        _loadThemeColors.running = true
    }

    Process {
        id: _loadThemeColors
        command: ["bash", "-c",
            "source ~/.config/themes/" + root.name + "/theme.env && " +
            "echo $BASE $SURFACE $TEXT $ACCENT $MAUVE $RED $GREEN"
        ]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                const parts = text.trim().split(" ")
                if (parts.length >= 7) {
                    root.base    = parts[0]
                    root.surface = parts[1]
                    root.text    = parts[2]
                    root.accent  = parts[3]
                    root.mauve   = parts[4]
                    root.red     = parts[5]
                    root.green   = parts[6]
                    root.isDark  = (root.name !== "latte")
                }
            }
        }
    }
}
```

Use in any Quickshell component:
```qml
import ".."
Rectangle {
    color: Theme.base
    Text { color: Theme.text; text: "Hello" }
}
```

---

## 106.7 NixOS: Declarative Theme Switching

With Home Manager and Stylix, theme switching is a `nixos-rebuild switch` away:

```nix
# flake.nix — parameterise the theme
let
  theme = "dark";   # change this and rebuild
in {
  stylix.image = if theme == "dark"
    then ./wallpapers/mocha.jpg
    else ./wallpapers/latte.jpg;

  stylix.base16Scheme = if theme == "dark"
    then "${pkgs.base16-schemes}/share/themes/catppuccin-mocha.yaml"
    else "${pkgs.base16-schemes}/share/themes/catppuccin-latte.yaml";
}
```

For live switching on NixOS without a full rebuild, use the script approach
above alongside `nh home switch` to update only non-Stylix components.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
