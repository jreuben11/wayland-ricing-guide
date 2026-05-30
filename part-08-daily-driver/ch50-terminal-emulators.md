# Chapter 50 — Terminal Emulators: Kitty, Alacritty, Foot, WezTerm, Ghostty

## Overview
The terminal is the most-looked-at element in any rice. All major modern
terminals are Wayland-native; the differences lie in GPU backend, font rendering,
extensibility, and special protocol support.

## 50.1 The Wayland Terminal Landscape
- All terminals covered here use either OpenGL/Vulkan or Wayland SHM rendering
- Key differentiators: GPU vs CPU rendering, protocol extras, config language
- XWayland terminals (xterm, rxvt): avoid unless debugging

## 50.2 Kitty — The Feature King

**Why Kitty:** GPU-accelerated, rich feature set, extensible with "kittens"

**Installation:** `kitty` package everywhere

**Config:** `~/.config/kitty/kitty.conf`
```conf
font_family      JetBrainsMono Nerd Font
font_size        12.0
background_opacity 0.95
window_padding_width 12

# Colors (example — or use a theme)
background  #1e1e2e
foreground  #cdd6f4
cursor      #f5e0dc

# Tabs
tab_bar_style powerline
tab_powerline_style angled
```

**Kitty-specific features:**
- **Kitty Graphics Protocol**: display images inline in terminal (used by `ranger`, `yazi`, `neovim` image plugins)
- **Remote control**: `kitty @ --to unix:$KITTY_LISTEN_ON` — control running instances
- **Kittens**: mini-programs — `icat` (image display), `diff`, `panel` (sidebar), `broadcast` (multi-pane input)
- **Sessions**: `kitty --session session.conf` — restore window/tab layout
- **Layouts**: tall, fat, grid, splits — built-in window management
- **Unicode input**: `ctrl+shift+u` then hex codepoint
- **Hyperlinks**: `open_url_with` — clickable URLs in terminal

**Theming kitty:**
- `kitty +kitten themes` — built-in theme browser (300+ themes)
- Direct: append color block to `kitty.conf`
- Pywal: `include ~/.cache/wal/colors-kitty.conf`

## 50.3 Alacritty — Minimal and Fast

**Why Alacritty:** The fastest terminal, zero features beyond rendering, TOML config

**Config:** `~/.config/alacritty/alacritty.toml`
```toml
[font]
normal = { family = "JetBrainsMono Nerd Font", style = "Regular" }
size = 12.0

[window]
padding = { x = 12, y = 12 }
opacity = 0.95
decorations = "none"

[colors.primary]
background = "#1e1e2e"
foreground = "#cdd6f4"
```

**Alacritty philosophy:**
- No tabs, no splits, no scrollback search (use tmux/zellij)
- IPC: `alacritty msg` for runtime config changes (since 0.13)
- Very fast startup: good for scripts that spawn terminals
- Vi mode: keyboard-driven selection and copy

**What Alacritty lacks:** images, sixel, hyperlinks, GPU compute features

## 50.4 Foot — Wayland-Native and Lightweight

**Why Foot:** Designed specifically for Wayland, low resource usage, fast

**Config:** `~/.config/foot/foot.ini`
```ini
[main]
font=JetBrainsMono Nerd Font:size=12
pad=12x12

[colors]
background=1e1e2e
foreground=cdd6f4
```

**Foot-specific features:**
- `footclient` + `foot --server` daemon mode: sub-millisecond startup
- Sixel graphics support
- PGO (profile-guided optimization) build: fastest Wayland terminal
- Scrollback search built-in
- URL detection and launching
- `foot.ini` supports `[colors]` with full palette

**foot daemon pattern:**
```bash
# Start server in hyprland.conf exec-once
exec-once = foot --server
# Launch clients instantly
bind = SUPER, Return, exec, footclient
```

## 50.5 WezTerm — Programmable in Lua

**Why WezTerm:** Full Lua scripting, multiplexing, SSH domains, GPU-accelerated

**Config:** `~/.config/wezterm/wezterm.lua`
```lua
local wezterm = require 'wezterm'
local config = wezterm.config_builder()

config.font = wezterm.font('JetBrainsMono Nerd Font')
config.font_size = 12.0
config.color_scheme = 'Catppuccin Mocha'
config.window_background_opacity = 0.95
config.enable_tab_bar = false
config.window_padding = { left = 12, right = 12, top = 12, bottom = 12 }

return config
```

**WezTerm-specific features:**
- **Multiplexer**: tabs, panes, splits — built-in (no tmux needed)
- **SSH domains**: `wezterm ssh user@host` with full multiplexing
- **Lua events**: `wezterm.on('gui-startup', function() ... end)`
- **Dynamic config**: hot-reload without restart
- **Image protocol**: Kitty graphics + iTerm2 inline images
- **Hyperlinks**: automatic detection and clicking
- **Sixel**: full support
- **Conditional config**: different settings per OS/host

## 50.6 Ghostty — The New Challenger (2024+)

**Why Ghostty:** Fast, native, written in Zig, cross-platform (macOS + Linux)

**Config:** `~/.config/ghostty/config`
```
font-family = JetBrainsMono Nerd Font
font-size = 12
background-opacity = 0.95
theme = catppuccin-mocha
window-padding-x = 12
window-padding-y = 12
```

**Ghostty-specific features:**
- Extremely fast rendering (Zig + Metal/OpenGL)
- Built-in theme library
- GTK on Linux (native-looking)
- Kitty keyboard protocol support
- Liberation Fonts bundled — works out of box
- Still maturing: some features WezTerm/Kitty have are pending

## 50.7 Terminal Comparison Matrix

| Feature | Kitty | Alacritty | Foot | WezTerm | Ghostty |
|---------|-------|-----------|------|---------|---------|
| GPU rendering | OpenGL | OpenGL | OpenGL | OpenGL | OpenGL/Metal |
| Config language | Python-like conf | TOML | INI | Lua | Custom |
| Images (Kitty protocol) | Yes (native) | No | No | Yes | Yes |
| Sixel | No | No | Yes | Yes | Pending |
| Tabs/splits built-in | Yes | No | No | Yes | No |
| Daemon mode | No | No | Yes | Yes | No |
| Font ligatures | Yes | Yes | Yes | Yes | Yes |
| Hot reload | Yes | Partial | Yes | Yes | Yes |
| Wayland native | Yes | Yes | Yes (only) | Yes | Yes |
| Scripting/extensibility | Python kittens | None | None | Lua | Limited |

## 50.8 Terminal-Agnostic Configuration Tips

**Nerd Fonts verification:**
```bash
echo -e " ♥  "  # should show powerline + icons
```

**True color verification:**
```bash
curl -s https://gist.githubusercontent.com/.../24bit.sh | bash
```

**Undercurl support (for Neovim diagnostics):**
- Supported: Kitty, WezTerm, Ghostty, Foot
- Not supported: Alacritty (use underline instead)

**Shell integration:**
- Kitty: `source <(kitty + complete setup zsh)`
- WezTerm: `source ~/.config/wezterm/shell-integration.sh`
- Enables semantic zones, OSC 133 prompt marking, cwd tracking

## 50.9 Transparency and Blur
- Terminal opacity: set in terminal config (`background_opacity`)
- Blur behind terminal: set in compositor
  - Hyprland blur for terminal windows uses `windowrulev2 = blur, class:^(kitty)$` (not `layerrule`, which applies only to layer surfaces)
  - Hyprland: `windowrulev2 = opacity 0.9 0.9, class:^(kitty)$`
  - Hyprland blur: `decoration.blur.enabled = true`
- The terminal must use a background with alpha < 1 for blur to show through

---

## 50.10 Terminal Graphics Protocols: Sixel, Kitty, and iTerm2

Modern terminals support inline image display via dedicated graphics protocols. Each works differently and has different application support.

### Protocol Comparison

| Protocol | Terminals | Images | Animation | Transparency |
|---|---|---|---|---|
| **Kitty Graphics** | Kitty, WezTerm, Ghostty | PNG, JPEG, RGB raw | Yes | Yes (alpha) |
| **Sixel** | Foot, WezTerm, xterm | All (converted) | Limited | No |
| **iTerm2** | WezTerm, iTerm2 (macOS) | PNG, JPEG | Yes | No |

### Sixel in Foot

Foot has native sixel support with no plugins needed:

```bash
# Test sixel support
curl -s https://www.vt100.net/docs/vt3xx-gp/sixel.gif | img2sixel

# Install image-to-sixel converters
sudo pacman -S libsixel     # provides img2sixel

# Display an image inline
img2sixel ~/Pictures/wallpaper.jpg

# Scale to fit terminal width
img2sixel -w 800 ~/Pictures/wallpaper.jpg

# From a URL
curl -s https://example.com/image.png | img2sixel

# In ranger file manager (sixel preview)
# ~/.config/ranger/rc.conf:
# set preview_images true
# set preview_images_method sixel
```

```bash
# Verify sixel support in your terminal
printf '\033Pq#0;2;0;0;0#0~~@@vv@@~~@@~~$#1;2;100;100;0#1@@~~vv~~@@~~@@\033\\'
# Should display a small test pattern (visible pixels, not escape codes)
```

### Kitty Graphics Protocol (icat)

The Kitty graphics protocol transmits raw pixel data over the terminal and supports animations, transparency, and virtual placements:

```bash
# icat is a Kitty kitten (plugin)
# Display an image
kitty +kitten icat ~/Pictures/photo.jpg

# Scale to specific width in pixels
kitty +kitten icat --scale-up --place 80x24@0x0 ~/Pictures/photo.jpg

# Display in a specific area (columns x rows @ col x row)
kitty +kitten icat --place 40x20@10x2 ~/Pictures/wallpaper.jpg

# From stdin
curl -s https://example.com/image.png | kitty +kitten icat /dev/stdin

# Clear all images from the screen
kitty +kitten icat --clear

# Show in ranger (kitty only)
# ~/.config/ranger/rc.conf:
# set preview_images true
# set preview_images_method kitty
```

```bash
# Test kitty graphics protocol support in any terminal
# (WezTerm and Ghostty also support this protocol)
python3 -c "
import base64, zlib, struct, sys

# Create a tiny 4x4 RGBA image (red square)
def rgba(r,g,b,a=255): return bytes([r,g,b,a])
pixels = rgba(255,0,0) * 16   # 4x4 red

# Encode as PNG
import io, struct, zlib

def png4x4(pixels):
    def chunk(name, data):
        c = name + data
        return struct.pack('>I', len(data)) + name + data + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    raw = b''.join(b'\x00' + pixels[i*16:(i+1)*16] for i in range(4))
    compressed = zlib.compress(raw)
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', 4, 4, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', compressed)
            + chunk(b'IEND', b''))

png = png4x4(pixels)
b64 = base64.b64encode(png).decode()
# Kitty graphics protocol APC sequence
print(f'\x1b_Ga=T,f=100,q=2;{b64}\x1b\\', end='')
"
```

### WezTerm: Both Protocols

WezTerm supports both Kitty graphics and sixel. For sixel:
```bash
# In wezterm.lua — sixel is enabled by default
# Verify:
img2sixel -w 60 ~/Pictures/test.png
```

For Kitty protocol in WezTerm:
```bash
# WezTerm exposes TERM=xterm-256color but supports kitty protocol
# Use icat via:
TERM=xterm-kitty kitty +kitten icat ~/Pictures/test.png
# Or check via wezterm CLI:
wezterm imgcat ~/Pictures/test.png
```

### yazi: Terminal File Manager with Image Preview

`yazi` is a terminal file manager with protocol-aware image preview:

```bash
# Install
sudo pacman -S yazi

# ~/.config/yazi/yazi.toml
[preview]
image_filter   = "lanczos3"
image_quality  = 75
max_width      = 600
max_height     = 900

# yazi auto-detects the protocol (kitty > sixel > iterm2 > chafa fallback)
# To force a protocol:
# YAZI_LOG=debug yazi 2>&1 | grep -i "proto\|preview"
```

### Per-Terminal Ligature Support

| Terminal | Ligatures | Notes |
|---|---|---|
| **Kitty** | Yes | Full OpenType ligature support |
| **WezTerm** | Yes | Full OpenType, configurable disable per-font |
| **Ghostty** | Yes | Full OpenType |
| **Foot** | Yes | FreeType ligature support |
| **Alacritty** | No | Explicitly unsupported by design |
| **xterm** | No | Too old |

```bash
# Test ligature rendering — these should render as single glyphs with a ligature font
echo "-> => !== === <> <= >= ++ -- ..."
# With JetBrains Mono / Fira Code / Cascadia Code, arrows become unified glyphs
```

Disable ligatures in WezTerm for a specific font:
```lua
-- wezterm.lua
config.font = wezterm.font('JetBrainsMono', {
    harfbuzz_features = { 'calt=0', 'clig=0', 'liga=0' }
})
```

Disable in Kitty:
```conf
# kitty.conf
font_features JetBrainsMono-Regular -calt -clig -liga
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).