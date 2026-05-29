# Chapter 26 — Bars and Panels: Waybar, eww, AGS/Astal

## Overview
Before Quickshell dominated, other bar frameworks shaped the Wayland ricing scene.
Understanding them helps when reading dotfiles or working on compositors without
Hyprland-level IPC.

## Sections

### 26.1 Waybar — The Workhorse Bar
- JSON config: `~/.config/waybar/config.jsonc`
- CSS theming: `~/.config/waybar/style.css`
- Module system: built-in modules + custom scripts
- Built-in modules: `clock`, `workspaces`, `window`, `network`, `pulseaudio`,
  `battery`, `tray`, `cpu`, `memory`, `temperature`, `backlight`
- Sway-specific vs. Hyprland-specific vs. generic modules
- `custom/` modules: shell script output in bar
- `interval`: polling vs. signal-triggered updates
- Multiple bars: `bars` array in config
- `layer-shell` positioning: `top`, `bottom`, `left`, `right`
- Multi-monitor: `output` field in bar config

### 26.2 Waybar CSS Theming
- Selectors: `#module-name`, `window#waybar`, `.modules-left`
- CSS variables for theming: `@define-color accent #89b4fa;`
- GTK CSS extensions: `border-radius`, `box-shadow`
- Example: Catppuccin Mocha theme for Waybar

### 26.3 eww (Elkowar's Wacky Widgets)
- Yuck language: S-expression syntax
- Widget primitives: `box`, `label`, `button`, `image`, `slider`
- `deflisten`: subscribing to shell command output
- `defvar` + `defwidget`: state and reusable components
- Windows: `defwindow` with layer-shell positioning
- CSS styling in eww
- Real-world use cases: sidebars, dashboards, desktop widgets
- Status: mature but superseded by AGS/Astal for new projects

### 26.4 AGS / Astal — TypeScript Widgets
- AGS v1: GJS + TypeScript widget system
- Astal (AGS v2): complete rewrite, library-first approach
- Languages: TypeScript, Lua, Python, Vala via GObject introspection
- Astal libraries: hyprland, niri, mpris, network, bluetooth, battery, etc.
- Bar example in TypeScript
- Comparison to Quickshell: when to choose Astal

### 26.5 Choosing Your Bar Framework in 2025/2026
| | Waybar | eww | AGS/Astal | Quickshell |
|--|--------|-----|-----------|-----------|
| Language | JSON+CSS | Yuck | TypeScript | QML |
| Learning curve | Low | Medium | Medium | Medium |
| Programmability | Low | High | High | Highest |
| Hot reload | No | No | Yes | Yes |
| Wayland protocols | Good | Good | Good | Best |
| Compositor IPC | Good | Via script | Good | Native |
| LSP support | Limited | Limited | Yes | Yes |

**Verdict 2025**: Quickshell for new projects; Waybar for quick setups; AGS/Astal
for TypeScript fans.
