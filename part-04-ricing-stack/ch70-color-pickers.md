# Chapter 70 — Color Picker Tools: hyprpicker, wl-color-picker, gpick

## Overview
Sampling colors from the screen is a core step in theming. X11 had `gcolor2`,
`xcolor`, `gpick` — Wayland needs tools that work with the screencopy protocol.

## Sections

### 70.1 hyprpicker — The Standard

hyprpicker is the de-facto Wayland color picker for Hyprland (and any wlroots compositor):

```bash
sudo pacman -S hyprpicker  # or AUR
```

**Usage:**
```bash
hyprpicker              # click anywhere, copies hex to clipboard
hyprpicker -a           # auto-accept (no Enter needed)
hyprpicker -f hex       # output format: hex, rgb, hsl
hyprpicker -n           # no newline (for scripting)
```

**Integration with a keybind:**
```conf
# hyprland.conf
bind = SUPER, C, exec, hyprpicker -a -n | wl-copy
```

**With notification:**
```bash
#!/bin/bash
color=$(hyprpicker -a -n)
echo -n "$color" | wl-copy
notify-send "Color Picked" "$color" --expire-time=2000
```

### 70.2 wl-color-picker

A simple GTK color picker dialog that outputs the picked color:
```bash
paru -S wl-color-picker
wl-color-picker  # opens dialog, copies result
```

More GUI-friendly than hyprpicker — shows a color wheel.

### 70.3 gpick — Advanced GUI Color Picker

gpick is a powerful color picker with sampling modes, palette management, and history:
```bash
sudo pacman -S gpick
```

**Features:**
- Magnifier zoom on cursor area
- Multiple sampling modes
- Save palette as GPL/CSS/JSON
- Color difference viewer
- Runs via XWayland on Wayland (works but not native)

### 70.4 kcolorchooser — KDE Color Picker

```bash
sudo pacman -S kcolorchooser
```
Qt6, native Wayland. KDE-integrated. Useful for Qt/KDE theming workflows.

### 70.5 Color Picking in Quickshell

For an always-on-screen color loupe:
```qml
// Launch hyprpicker and capture result
Process {
    id: picker
    command: ["hyprpicker", "-a", "-n"]
    stdout: StdioCollector {
        onStreamFinished: {
            colorResult = text.trim()
            // copy to clipboard
            Process { command: ["wl-copy", colorResult]; running: true }
        }
    }
}
```

### 70.6 Color Format Conversion

```bash
# hex to rgb
python3 -c "h='#89b4fa'; print(tuple(int(h[i:i+2],16) for i in (1,3,5)))"

# rgb to hex
printf '#%02x%02x%02x\n' 137 180 250

# Useful tool: pastel (Rust)
sudo pacman -S pastel
pastel color 137 180 250      # show color info
pastel mix "#89b4fa" "#cba6f7"  # mix two colors
pastel lighten 0.1 "#89b4fa"   # lighten
pastel darken 0.1 "#89b4fa"    # darken
pastel gradient "#89b4fa" "#cba6f7" 5  # generate gradient
```

### 70.7 Integrating Color Pickers into the Ricing Workflow

**Typical workflow:**
1. Find a wallpaper you like
2. `hyprpicker` to sample 2–3 dominant colors
3. Feed into `pastel` to build a palette
4. Use as accent colors in Quickshell bar, Hyprland border colors, terminal

**Extracting from image (automated):**
```bash
# matugen (Material You from image — Ch 38)
matugen image wallpaper.jpg

# imagemagick histogram (top 10 colors)
convert wallpaper.jpg -format %c -depth 8 histogram:info:- | \
    sort -rn | head -10 | grep -oP '#[0-9A-Fa-f]{6}'
```
