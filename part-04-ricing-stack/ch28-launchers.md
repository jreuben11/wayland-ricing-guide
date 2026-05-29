# Chapter 28 — Application Launchers: fuzzel, rofi, wofi, Anyrun, walker, tofi

## Overview
Application launchers use layer-shell to overlay a search interface. The Wayland
ecosystem has produced several excellent replacements for dmenu and rofi-X11.

## Sections

### 28.1 fuzzel — Fast and Minimal
- Written in C, minimal dependencies
- Wayland-native (layer-shell)
- Config: `~/.config/fuzzel/fuzzel.ini`
- Features: app launcher, dmenu mode, custom lists
- Font config, colors, border radius, padding
- Very fast startup time
- `fuzzel --dmenu` for scripted use

### 28.2 rofi (Wayland fork) — The Feature-Complete Option
- `lbonn/rofi` fork adds Wayland support
- Modes: `drun` (apps), `run` (commands), `window` (window switcher), `ssh`
- Themes: `.rasi` format, extensive community themes
- Custom modi: extend with scripts
- `rofi -show drun -theme ~/.config/rofi/theme.rasi`
- Power menu example with rofi

### 28.3 wofi — GTK Wayland Launcher
- Native Wayland, GTK-based
- CSS theming via `~/.config/wofi/style.css`
- Modes: `drun`, `run`, `dmenu`
- `--style`, `--color` flags
- Less maintained than alternatives (2025 status)

### 28.4 tofi — Minimal dmenu Replacement
- Extremely minimal: no dependencies beyond Cairo/Pango
- Single-purpose: fast text filtering
- Config in `~/.config/tofi/config`
- Ideal for power-menu, clipboard, emoji pickers

### 28.5 Anyrun — CSS-Customizable Plugin Launcher
- Plugin architecture: custom result sources
- CSS theming with full GTK CSS support
- Built-in plugins: Applications, Websearch, Translate, Dictionary, Rink (calculator)
- Writing custom Anyrun plugins in Rust
- Hot-reload config support

### 28.6 walker — GTK4 Launcher
- GTK4 with CSS theming
- Built-in: apps, files, web search, calculator, SSH, clipboard, emojis
- Custom runners via config
- Plugin system
- TypeScript theming variant

### 28.7 bemenu — Dynamic Menu Library
- API + CLI tool: acts as dmenu replacement
- Wayland-native rendering
- Embeddable as a library in custom tools

### 28.8 Power Menu Patterns
```bash
# rofi power menu
chosen=$(printf "Shutdown\nReboot\nLogout\nSuspend\nLock" | rofi -dmenu -p "Power")
case $chosen in
    Shutdown) systemctl poweroff ;;
    Reboot) systemctl reboot ;;
    Logout) hyprctl dispatch exit ;;
    Suspend) systemctl suspend ;;
    Lock) loginctl lock-session ;;
esac
```

### 28.9 Quickshell App Launcher
- Building an app launcher in QML
- `.desktop` file parsing via `Process` + `gio`
- Fuzzy search with JavaScript
- Icon resolution with `IconImage`
- Full example: modal overlay launcher
