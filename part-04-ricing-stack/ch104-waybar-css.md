# Chapter 104 — Waybar CSS Theming Deep Dive

## Contents

- [Overview](#overview)
- [104.1 How GTK CSS Applies to Waybar](#1041-how-gtk-css-applies-to-waybar)
- [104.2 GTK CSS vs Standard CSS](#1042-gtk-css-vs-standard-css)
- [104.3 Bar Layout and Appearance](#1043-bar-layout-and-appearance)
- [104.4 Workspace Module](#1044-workspace-module)
- [104.5 Clock Module](#1045-clock-module)
- [104.6 Battery Module](#1046-battery-module)
- [104.7 Network Module](#1047-network-module)
- [104.8 Audio / PipeWire Module](#1048-audio-pipewire-module)
- [104.9 System Tray](#1049-system-tray)
- [104.10 Custom Module Styling](#10410-custom-module-styling)
- [104.11 Pill / Island Design](#10411-pill-island-design)
- [104.12 Blur Integration (Hyprland)](#10412-blur-integration-hyprland)
- [104.13 Animations](#10413-animations)
- [104.14 pywal / matugen Integration](#10414-pywal-matugen-integration)
  - [pywal colours in Waybar CSS](#pywal-colours-in-waybar-css)
  - [matugen colours in Waybar CSS](#matugen-colours-in-waybar-css)
- [104.15 Complete Minimal style.css](#10415-complete-minimal-stylecss)
- [104.16 Debugging Waybar CSS](#10416-debugging-waybar-css)

---


## Overview

Waybar is styled with GTK CSS — a superset of standard CSS with GTK-specific
properties and a widget selector hierarchy that maps directly to Waybar's
JSON config. This chapter covers the full selector model, colour variables,
animation patterns, per-module styling, and integrating pywal/matugen palettes
so the bar recolours automatically when your wallpaper changes.

---

## 104.1 How GTK CSS Applies to Waybar

Waybar loads `~/.config/waybar/style.css` (or the path in `style` in
`config.jsonc`). Widgets in Waybar map to CSS selectors:

```
window#waybar            — the bar window itself
.modules-left            — left module container
.modules-center          — center module container
.modules-right           — right module container
#clock                   — a module by its name in config
#workspaces              — the workspaces module
#workspaces button       — each workspace button
#workspaces button.active — the active workspace button
#battery.charging        — battery module when charging
#battery.warning         — battery below warning threshold
#battery.critical        — battery below critical threshold
```

The selector name comes from the module's key in `config.jsonc`:
```jsonc
"modules-right": ["clock", "battery", "network"]
// → #clock, #battery, #network selectors
```

---

## 104.2 GTK CSS vs Standard CSS

GTK CSS supports most CSS3 features plus extensions:

```css
/* GTK-specific: named colours from theme */
color: @theme_fg_color;
background: @theme_bg_color;

/* GTK-specific: icon sizes */
-gtk-icon-size: 16px;

/* GTK-specific: min dimensions (preferred over width/height) */
min-width: 20px;
min-height: 20px;

/* Standard CSS that works: */
border-radius, padding, margin, font-*, color, background,
border, box-shadow, opacity, transition, animation, @keyframes,
@define-color (GTK's version of CSS custom properties)
```

GTK CSS does **not** support: `var()`, `calc()` in all contexts, flexbox,
grid layout, most pseudo-elements (only `::before`/`::after` in newer GTK4).

Use `@define-color` instead of CSS custom properties:

```css
/* Define colours once */
@define-color base    #1e1e2e;
@define-color surface #313244;
@define-color text    #cdd6f4;
@define-color accent  #89b4fa;
@define-color mauve   #cba6f7;
@define-color red     #f38ba8;
@define-color green   #a6e3a1;
@define-color yellow  #f9e2af;

/* Use with @name syntax */
.module {
    color: @text;
    background: @surface;
    border: 1px solid @accent;
}
```

---

## 104.3 Bar Layout and Appearance

```css
* {
    font-family: "JetBrainsMono Nerd Font", monospace;
    font-size: 13px;
    min-height: 0;
    border: none;
    border-radius: 0;
}

window#waybar {
    background: alpha(@base, 0.85);
    color: @text;
    /* GTK blur (requires compositor blur layer rule): */
    /* background: transparent; */
}

/* Module containers */
.modules-left,
.modules-center,
.modules-right {
    padding: 0 4px;
}

/* Base style for all modules */
.module {
    padding: 0 10px;
    margin: 4px 2px;
    border-radius: 8px;
    background: @surface;
    color: @text;
    transition: background 200ms ease, color 200ms ease;
}

/* Hover effect */
.module:hover {
    background: @accent;
    color: @base;
}
```

---

## 104.4 Workspace Module

```css
#workspaces {
    margin: 4px 6px;
}

#workspaces button {
    min-width: 24px;
    min-height: 24px;
    padding: 0 6px;
    margin: 0 2px;
    border-radius: 6px;
    background: transparent;
    color: @subtext0;
    transition: all 200ms ease;
}

#workspaces button:hover {
    background: alpha(@accent, 0.2);
    color: @text;
}

#workspaces button.active {
    background: @accent;
    color: @base;
    font-weight: bold;
    min-width: 32px;
}

#workspaces button.urgent {
    background: @red;
    color: @base;
    animation: urgent-blink 1s steps(1, end) infinite;
}

@keyframes urgent-blink {
    0%, 100% { background: @red; }
    50%       { background: alpha(@red, 0.5); }
}

/* Sway: occupied workspaces */
#workspaces button.focused {
    background: @accent;
    color: @base;
}

#workspaces button.visible:not(.focused) {
    background: alpha(@accent, 0.3);
}
```

---

## 104.5 Clock Module

```css
#clock {
    padding: 0 14px;
    font-weight: 600;
    color: @text;
    background: transparent;
}

/* Tooltip (date shown on hover) */
tooltip {
    background: @surface;
    border: 1px solid @surface2;
    border-radius: 8px;
    color: @text;
}

tooltip label {
    padding: 6px 10px;
}
```

---

## 104.6 Battery Module

```css
#battery {
    padding: 0 10px;
    border-radius: 8px;
    background: @surface;
    color: @text;
    transition: all 300ms ease;
}

#battery.charging {
    color: @green;
    background: alpha(@green, 0.15);
}

#battery.warning:not(.charging) {
    color: @yellow;
    background: alpha(@yellow, 0.15);
}

#battery.critical:not(.charging) {
    color: @red;
    background: alpha(@red, 0.15);
    animation: critical-pulse 2s ease infinite;
}

@keyframes critical-pulse {
    0%, 100% { background: alpha(@red, 0.15); }
    50%       { background: alpha(@red, 0.35); }
}
```

---

## 104.7 Network Module

```css
#network {
    padding: 0 10px;
    border-radius: 8px;
    background: @surface;
    color: @text;
}

#network.disconnected {
    color: @red;
    background: alpha(@red, 0.1);
}

#network.wifi {
    color: @blue;
}

#network.ethernet {
    color: @green;
}
```

---

## 104.8 Audio / PipeWire Module

```css
#pulseaudio,
#wireplumber {
    padding: 0 10px;
    border-radius: 8px;
    background: @surface;
    color: @text;
    transition: color 200ms ease;
}

#pulseaudio.muted,
#wireplumber.muted {
    color: @overlay0;
    background: alpha(@base, 0.5);
}
```

---

## 104.9 System Tray

```css
#tray {
    padding: 0 6px;
}

#tray > .passive {
    -gtk-icon-effect: dim;
}

#tray > .needs-attention {
    -gtk-icon-effect: highlight;
    background: alpha(@yellow, 0.2);
    border-radius: 4px;
}

/* Spacing between tray icons */
#tray .tray-icon {
    margin: 0 2px;
}
```

---

## 104.10 Custom Module Styling

```jsonc
// config.jsonc — custom CPU module
"custom/cpu": {
    "exec": "bash -c \"grep -o '^[^ ]*' /proc/loadavg\"",
    "interval": 2,
    "format": "󰻠 {}",
    "tooltip": false
}
```

```css
/* Style by the module name */
#custom-cpu {
    padding: 0 10px;
    border-radius: 8px;
    background: @surface;
    color: @text;
}

/* Style based on content using format classes */
/* Add "format-class" logic in config if needed */
```

---

## 104.11 Pill / Island Design

Popular ricing style: modules grouped into floating pill shapes with gaps
between them:

```css
window#waybar {
    background: transparent;   /* transparent bar window */
}

/* Left group */
.modules-left {
    margin: 6px 0 6px 8px;
    background: alpha(@base, 0.90);
    border-radius: 12px;
    padding: 0 4px;
    /* Compositor blur via layerrule = blur, waybar */
}

/* Center group */
.modules-center {
    margin: 6px 0;
    background: alpha(@base, 0.90);
    border-radius: 12px;
    padding: 0 12px;
}

/* Right group */
.modules-right {
    margin: 6px 8px 6px 0;
    background: alpha(@base, 0.90);
    border-radius: 12px;
    padding: 0 4px;
}

/* No background on individual modules in island mode */
.module {
    background: transparent;
    padding: 0 8px;
    margin: 0;
}

/* Separator between islands */
#separator {
    color: alpha(@overlay0, 0.5);
    padding: 0;
    margin: 0 4px;
}
```

In `config.jsonc`, add a `"separator"` module between groups:
```jsonc
"custom/separator": {
    "format": "|",
    "tooltip": false
}
```

---

## 104.12 Blur Integration (Hyprland)

For a translucent, blurred bar:

```conf
# hyprland.conf
layerrule = blur,          waybar
layerrule = ignorezero,    waybar   # skip fully transparent pixels
layerrule = blurpopups,    waybar   # blur popup menus too
layerrule = xray 1,        waybar   # blur doesn't obscure windows behind
```

```css
/* style.css */
window#waybar {
    background: alpha(@base, 0.70);   /* semi-transparent so blur shows */
}
```

---

## 104.13 Animations

```css
/* Slide-in animation for the entire bar */
@keyframes slide-down {
    from { margin-top: -36px; opacity: 0; }
    to   { margin-top:   0px; opacity: 1; }
}

window#waybar {
    animation: slide-down 400ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

/* Pulse animation for notifications */
@keyframes notif-pulse {
    0%, 100% { transform: scale(1);    }
    50%       { transform: scale(1.1); }
}

#custom-notification.unread {
    animation: notif-pulse 1.5s ease infinite;
    color: @mauve;
}

/* Transition for workspace changes */
#workspaces button {
    transition: all 200ms cubic-bezier(0.34, 1.56, 0.64, 1);
}
```

---

## 104.14 pywal / matugen Integration

Auto-recolour Waybar when your wallpaper changes.

### pywal colours in Waybar CSS

pywal writes `~/.cache/wal/colors.css`:
```css
/* ~/.cache/wal/colors.css (pywal output) */
:root {
    --wallpaper: url('/home/user/.cache/wal/wal');
    --background: #1e1e2e;
    --foreground: #cdd6f4;
    --color0: #1e1e2e;
    ...
    --color15: #cdd6f4;
}
```

Since GTK CSS doesn't support `var()`, import pywal colours by including its
GTK-specific output:

```bash
# pywal generates: ~/.cache/wal/colors-gtk.css
# Content: @define-color color0 #1e1e2e; etc.
```

In `style.css`:
```css
/* Import pywal colours */
@import url("/home/user/.cache/wal/colors-gtk.css");

/* Now use pywal colours */
window#waybar {
    background: alpha(@color0, 0.85);
    color: @color15;
}

#workspaces button.active {
    background: @color4;
    color: @color0;
}
```

Run `wal -i wallpaper.jpg` to regenerate colours, then restart Waybar:
```bash
pkill waybar && waybar &
```

Or use `inotifywait` to hot-reload automatically:
```bash
#!/bin/bash
# ~/.config/waybar/hot-reload.sh
while inotifywait -e modify ~/.cache/wal/colors-gtk.css; do
    pkill -SIGUSR2 waybar   # SIGUSR2 reloads Waybar's style without restart
done
```

```conf
# hyprland.conf
exec-once = ~/.config/waybar/hot-reload.sh
```

### matugen colours in Waybar CSS

matugen (Material You) outputs to `~/.config/matugen/colors.css`:
```bash
# matugen generates colours at:
~/.config/matugen/colors.css

# Template: add to ~/.config/matugen/templates/waybar.css
# {{ colors.primary.default.hex }} → the primary colour
```

---

## 104.15 Complete Minimal style.css

```css
@define-color base    #1e1e2e;
@define-color surface #313244;
@define-color overlay #45475a;
@define-color text    #cdd6f4;
@define-color subtext #bac2de;
@define-color accent  #89b4fa;
@define-color mauve   #cba6f7;
@define-color red     #f38ba8;
@define-color yellow  #f9e2af;
@define-color green   #a6e3a1;

* {
    font-family: "JetBrainsMono Nerd Font", monospace;
    font-size: 13px;
    min-height: 0;
    border: none;
    border-radius: 0;
}

window#waybar {
    background: alpha(@base, 0.88);
    color: @text;
}

.modules-left, .modules-right { padding: 2px 8px; }
.modules-center                { padding: 2px 16px; }

/* Default module style */
label, button { padding: 0 8px; color: @text; }

/* Workspaces */
#workspaces button {
    padding: 0 6px;
    margin: 2px 1px;
    border-radius: 6px;
    background: transparent;
    color: @subtext;
    transition: all 150ms ease;
}
#workspaces button.active {
    background: @accent;
    color: @base;
    font-weight: 600;
    padding: 0 10px;
}
#workspaces button.urgent  { background: @red;    color: @base; }
#workspaces button:hover   { background: alpha(@accent, 0.25); color: @text; }

/* Clock */
#clock { font-weight: 600; padding: 0 14px; }

/* Battery */
#battery                      { color: @text; }
#battery.charging             { color: @green; }
#battery.warning:not(.charging){ color: @yellow; }
#battery.critical:not(.charging){ color: @red; }

/* Network */
#network.disconnected { color: @red; }

/* Muted audio */
#pulseaudio.muted, #wireplumber.muted { color: @overlay; }

/* Tray */
#tray { padding: 0 4px; }

/* Tooltip */
tooltip {
    background: @surface;
    border: 1px solid @overlay;
    border-radius: 8px;
}
tooltip label { color: @text; padding: 4px 8px; }
```

---

## 104.16 Debugging Waybar CSS

```bash
# Check for CSS parse errors (printed to stderr)
waybar 2>&1 | grep -i css

# Watch the style file and reload on change:
while inotifywait -e modify ~/.config/waybar/style.css; do
    pkill -SIGUSR2 waybar
done

# GTK inspector (see the widget tree and live-edit CSS):
GTK_DEBUG=interactive waybar

# Print all GTK named colours available:
python3 -c "
import gi; gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
c = Gtk.CssProvider(); c.load_from_data(b'')
print('GTK loaded')
"

# Reload waybar config (not just style):
pkill -SIGUSR1 waybar   # reload config
pkill -SIGUSR2 waybar   # reload style only
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
