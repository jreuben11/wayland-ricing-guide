# Chapter 69 — File Managers: Yazi, Thunar, Dolphin, lf

## Overview
File managers on Wayland work like any other GTK/Qt app — no protocol issues.
The ricing dimension is: TUI (Yazi, lf) vs. GUI (Thunar, Dolphin), and
integrating image/video previews with the terminal protocol.

## Sections

### 69.1 The Landscape

| Manager | Type | Toolkit | Wayland | Previews | Notes |
|---------|------|---------|---------|----------|-------|
| Yazi | TUI | Ratatui (Rust) | Terminal | Kitty/sixel/chafa | The 2024/2025 standard |
| lf | TUI | Go | Terminal | Configurable | Veteran choice |
| nnn | TUI | C | Terminal | Plugin-based | Extremely minimal |
| ranger | TUI | Python | Terminal | w3m/ueberzug | Older, Python |
| Thunar | GUI | GTK3 | Yes | Thumbnails | XFCE, lightweight |
| Dolphin | GUI | Qt6 | Yes | Thumbnails | KDE, feature-rich |
| Nautilus | GUI | GTK4 | Yes | Thumbnails | GNOME, clean |
| PCManFM-Qt | GUI | Qt5 | Yes | Thumbnails | LXQT, lightweight |

### 69.2 Yazi — The Modern TUI File Manager

Yazi (written in Rust, 2023+) has become the dominant choice in ricing setups:

**Installation:**
```bash
sudo pacman -S yazi ffmpegthumbnailer unar jq poppler fd ripgrep fzf zoxide imagemagick
```

**Config:** `~/.config/yazi/`
```toml
# yazi.toml
[manager]
ratio          = [1, 3, 4]   # parent:current:preview column widths
sort_by        = "natural"
sort_dir_first = true
show_hidden    = false

[preview]
tab_size       = 2
max_width      = 600
max_height     = 900
cache_dir      = ""

[opener]
edit = [{ run = 'nvim "$@"', block = true }]
open = [{ run = 'xdg-open "$@"' }]
```

**Theme:** `~/.config/yazi/theme.toml`
```toml
[manager]
cwd = { fg = "#89b4fa" }
hovered = { fg = "#1e1e2e", bg = "#89b4fa" }
preview_hovered = { underline = true }

[status]
separator_open  = ""
separator_close = ""
```

**Image previews in Kitty:**
Yazi uses the Kitty graphics protocol for inline image previews — zero configuration
needed if you're in Kitty. For other terminals:
```toml
# yazi.toml
[preview]
image_protocol = "half-block"   # for terminals without graphics protocol
# or: "sixel", "kitty", "iterm2"
```

**Shell integration:**
```bash
# ~/.zshrc or ~/.config/fish/config.fish — "ya" changes directory on exit
function ya() {
    local tmp=$(mktemp -t "yazi-cwd.XXXXX")
    yazi "$@" --cwd-file="$tmp"
    local cwd=$(cat "$tmp")
    [[ -n "$cwd" && "$cwd" != "$PWD" ]] && cd "$cwd"
    rm -f "$tmp"
}
```

**Plugins:** `~/.config/yazi/plugins/`
Popular: `glow.yazi` (markdown preview), `miller.yazi` (CSV), `starship.yazi`

### 69.3 lf — The Veteran TUI Manager

```bash
sudo pacman -S lf
```

**Config:** `~/.config/lf/lfrc`
```
set previewer ~/.config/lf/previewer
set cleaner ~/.config/lf/cleaner
set ratios 1:2:3
set hidden true
set icons true

# Keybindings
map <enter> open
map D delete
map R rename
map Y copy
map P paste
map . set hidden!
```

**Image preview with chafa/kitty:**
```bash
#!/bin/bash
# ~/.config/lf/previewer
case "$1" in
    *.jpg|*.jpeg|*.png|*.gif|*.webp)
        kitty +kitten icat --silent --stdin no --transfer-mode file \
              --place "${2}x${3}@${4}x${5}" "$1" >/dev/tty; exit 1 ;;
    *) bat --color=always "$1" ;;
esac
```

### 69.4 Thunar — Lightweight GUI Manager

```bash
sudo pacman -S thunar thunar-volman tumbler gvfs gvfs-mtp
```

**Thunar custom actions:**
Edit → Configure Custom Actions:
- Open Terminal Here: `kitty --working-directory %f`
- Open as Root: `pkexec thunar %f`

**Thunar theming:**
Uses GTK3 — follow Ch 35. Set icons via `gsettings set org.gnome.desktop.interface icon-theme "Papirus-Dark"`.

**Polkit note:** Thunar needs `polkit-gnome-authentication-agent-1` running to mount drives without a root password dialog. See Ch 71.

### 69.5 Dolphin — Qt Feature-Rich Manager

```bash
sudo pacman -S dolphin ffmpegthumbs kdegraphics-thumbnailers
```

Dolphin settings:
- View → Show Hidden Files
- Control → Configure Dolphin → Startup → default folder
- Panels → Terminal (split-pane terminal below)
- Thumbnails: Settings → Configure Dolphin → General → Previews

Theming: follows Qt/Kvantum theming (Ch 36). Set icon theme in System Settings.

### 69.6 Mounting Drives Without Polkit

If polkit agent isn't running, mounting fails silently in all GUI managers:
```bash
# Manual mount
udisksctl mount -b /dev/sdb1

# Or install polkit agent (see Ch 71)
exec-once = /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1
```

### 69.7 File Association on Wayland

`xdg-open` routes to `xdg-mime` for file type → application mapping:
```bash
# Check current association
xdg-mime query default image/png

# Set association
xdg-mime default imv.desktop image/png
xdg-mime default mpv.desktop video/mp4

# Or via GUI: Thunar → right-click → Properties → Open With
```
