# Chapter 69 — File Managers: Yazi, Thunar, Dolphin, lf

## Overview

File managers on Wayland behave like any other GTK/Qt application — there are no
Wayland-specific protocol obstacles to running them. What makes them interesting
from a ricing perspective is the split between TUI managers (Yazi, lf, nnn) that
live inside your terminal emulator and GUI managers (Thunar, Dolphin, Nautilus)
that present native windowed interfaces. Each camp has its own theming story, its
own approach to image previews, and its own integration points with the rest of
your Wayland stack.

The dominant shift in 2024-2025 has been toward Yazi as the TUI standard, largely
because of its Rust-native performance, first-class Kitty/sixel graphics protocol
support, and an active plugin ecosystem. That said, lf remains the choice for
users who prefer a minimal, script-driven configuration, and Dolphin is
unbeatable for those who want a GUI manager with full KDE Plasma integration.
This chapter covers all of them in depth.

**Chapter dependencies:** Theming covered in Ch 35 (GTK) and Ch 36 (Qt/Kvantum).
Polkit agents discussed in Ch 71. Session startup patterns in Ch 53. Terminal
emulator graphics protocols covered in Ch 42.

---

## Sections

### 69.1 The Landscape

The table below summarises the major choices available on a modern Arch/Wayland
system. "Wayland" in the TUI rows means "runs inside any Wayland-native terminal
with no Xwayland required." GUI managers are native Wayland when launched under a
Wayland compositor; the toolkit column indicates which rendering stack is used.

| Manager    | Type | Toolkit        | Wayland | Previews           | Notes                        |
|------------|------|----------------|---------|--------------------|------------------------------|
| Yazi       | TUI  | Ratatui (Rust) | Terminal| Kitty/sixel/chafa  | The 2024/2025 standard       |
| lf         | TUI  | Go             | Terminal| Configurable       | Veteran choice, scriptable   |
| nnn        | TUI  | C              | Terminal| Plugin-based       | Extremely minimal             |
| ranger     | TUI  | Python         | Terminal| w3m/ueberzug       | Older, heavier deps           |
| Thunar     | GUI  | GTK3           | Yes     | Thumbnails         | XFCE, lightweight             |
| Dolphin    | GUI  | Qt6            | Yes     | Thumbnails         | KDE, feature-rich             |
| Nautilus   | GUI  | GTK4           | Yes     | Thumbnails         | GNOME, opinionated            |
| PCManFM-Qt | GUI  | Qt5            | Yes     | Thumbnails         | LXQt, lightweight             |

When choosing between TUI and GUI, consider your workflow. TUI managers are fast
to navigate via keyboard and integrate naturally with shell pipelines, but require
a running terminal. GUI managers provide drag-and-drop, thumbnail grids, and are
easier to hand to a non-power-user. Many ricers run both: Yazi for day-to-day
navigation and Thunar or Dolphin bound to a super-key shortcut for occasional
GUI browsing.

---

### 69.2 Yazi — The Modern TUI File Manager

Yazi (written in Rust, first released 2023) has become the dominant ricing choice
because of its performance, integrated async preview engine, and first-class
support for modern terminal graphics protocols. It ships as a single binary and
its configuration is split across four TOML files in `~/.config/yazi/`.

**Installation (Arch):**
```bash
sudo pacman -S yazi ffmpegthumbnailer unar jq poppler fd ripgrep fzf zoxide imagemagick
# Optional: font with Nerd Font icons
sudo pacman -S ttf-nerd-fonts-symbols
```

**Installation (build from source, always latest):**
```bash
cargo install --locked yazi-fm yazi-cli
```

#### 69.2.1 Core Configuration

All four config files live in `~/.config/yazi/`. Create the directory and start
with `yazi.toml`:

```toml
# ~/.config/yazi/yazi.toml
[manager]
ratio          = [1, 3, 4]   # parent : current : preview column widths
sort_by        = "natural"
sort_dir_first = true
sort_sensitive = false
sort_reverse   = false
show_hidden    = false
show_symlink   = true

[preview]
tab_size       = 2
max_width      = 600
max_height     = 900
cache_dir      = ""           # empty = ~/.cache/yazi/
image_delay    = 30           # ms before showing image (debounce scroll)
image_filter   = "lanczos3"   # "nearest" | "triangle" | "catmull-rom" | "lanczos3"
image_quality  = 75

[opener]
edit   = [{ run = 'nvim "$@"',                block = true }]
open   = [{ run = 'xdg-open "$@"' }]
reveal = [{ run = 'xdg-open "$(dirname "$@")"' }]
extract = [
    { run = 'unar "$@"', desc = "Extract here" },
]
play = [
    { run = 'mpv "$@"', orphan = true },
]

[open]
rules = [
    { mime = "text/*",           use = ["edit", "reveal"] },
    { mime = "image/*",          use = ["open", "reveal"] },
    { mime = "video/*",          use = ["play",  "reveal"] },
    { mime = "audio/*",          use = ["play",  "reveal"] },
    { mime = "inode/directory",  use = ["edit"] },
    { mime = "application/pdf",  use = ["open", "reveal"] },
]

[tasks]
micro_workers    = 10
macro_workers    = 25
bizarre_retry    = 5
image_alloc      = 536870912  # 512 MiB
image_bound      = [0, 0]
suppress_preload = false

[log]
enabled = false
```

#### 69.2.2 Keymap Configuration

```toml
# ~/.config/yazi/keymap.toml
[manager]
keymap = [
    { on = ["q"],            run = "quit",            desc = "Quit Yazi" },
    { on = ["Q"],            run = "quit --no-cwd-file", desc = "Quit without cwd change" },

    # Navigation
    { on = ["k"],            run = "arrow -1",         desc = "Up" },
    { on = ["j"],            run = "arrow 1",          desc = "Down" },
    { on = ["K"],            run = "arrow -5",         desc = "Up 5" },
    { on = ["J"],            run = "arrow 5",          desc = "Down 5" },
    { on = ["h"],            run = "leave",            desc = "Parent dir" },
    { on = ["l"],            run = "enter",            desc = "Enter dir" },
    { on = ["g", "g"],       run = "arrow -99999999",  desc = "Top" },
    { on = ["G"],            run = "arrow 99999999",   desc = "Bottom" },
    { on = ["<Enter>"],      run = "open",             desc = "Open file" },
    { on = ["<Space>"],      run = "select --state=none", desc = "Toggle select" },

    # File operations
    { on = ["y"],            run = "yank",             desc = "Yank (copy)" },
    { on = ["x"],            run = "yank --cut",       desc = "Yank (cut)" },
    { on = ["p"],            run = "paste",            desc = "Paste" },
    { on = ["P"],            run = "paste --force",    desc = "Paste (overwrite)" },
    { on = ["d"],            run = "remove",           desc = "Trash file" },
    { on = ["D"],            run = "remove --permanently", desc = "Delete permanently" },
    { on = ["r"],            run = "rename --cursor=before_ext", desc = "Rename" },
    { on = ["a"],            run = "create",           desc = "Create file/dir" },

    # Tabs
    { on = ["t"],            run = "tab_create --current", desc = "New tab" },
    { on = ["["],            run = "tab_switch -1 --relative", desc = "Prev tab" },
    { on = ["]"],            run = "tab_switch 1  --relative", desc = "Next tab" },

    # Misc
    { on = ["."],            run = "hidden toggle",    desc = "Toggle hidden files" },
    { on = ["/"],            run = "find",             desc = "Find in current dir" },
    { on = ["f"],            run = "plugin fzf",       desc = "fzf jump" },
    { on = ["z"],            run = "plugin zoxide",    desc = "Zoxide jump" },
    { on = ["S"],            run = "shell --block --confirm", desc = "Open shell here" },
]
```

#### 69.2.3 Theming

Yazi themes map directly to Catppuccin, Gruvbox, Nord, and other popular
palettes. Either grab a pre-built theme or write your own in
`~/.config/yazi/theme.toml`:

```toml
# ~/.config/yazi/theme.toml  — Catppuccin Mocha palette
[flavor]
use = "catppuccin-mocha"   # requires flavors/ directory (see below)

# Or configure manually:
[manager]
cwd             = { fg = "#89b4fa" }                    # blue
hovered         = { fg = "#1e1e2e", bg = "#89b4fa" }
preview_hovered = { underline = true }

[status]
separator_open  = ""
separator_close = ""
separator_style = { fg = "#45475a", bg = "#313244" }

[icon]
# Nerd Font icon mappings — partial example
rules = [
    { name = "*.rs",   text = "",  fg = "#f38ba8" },
    { name = "*.py",   text = "",  fg = "#f9e2af" },
    { name = "*.toml", text = "",  fg = "#a6e3a1" },
    { name = "*.json", text = "",  fg = "#f9e2af" },
    { name = "*.md",   text = "",  fg = "#89b4fa" },
    { name = "*.pdf",  text = "",  fg = "#f38ba8" },
    { name = "*.zip",  text = "",  fg = "#cba6f7" },
    { name = "*.mp4",  text = "",  fg = "#cba6f7" },
    { name = "*.png",  text = "",  fg = "#a6e3a1" },
    { name = "*.jpg",  text = "",  fg = "#a6e3a1" },
]
```

To use a Catppuccin flavor directly:
```bash
mkdir -p ~/.config/yazi/flavors
git clone https://github.com/catppuccin/yazi ~/.config/yazi/flavors/catppuccin-mocha.yazi
```

#### 69.2.4 Image Previews and Terminal Protocol Selection

Yazi uses the Kitty graphics protocol for inline image previews when running
under Kitty. For other terminals, set the protocol explicitly:

```toml
# ~/.config/yazi/yazi.toml  [preview] section
[preview]
# "kitty"    — Kitty terminal graphics protocol (best quality)
# "iterm2"   — iTerm2/WezTerm inline images
# "sixel"    — sixel graphics (foot, mlterm, xterm with sixel)
# "half-block" — Unicode half-block fallback (works everywhere)
image_protocol = "kitty"
```

For WezTerm users, the iterm2 protocol works well:
```toml
[preview]
image_protocol = "iterm2"
```

For foot or any sixel-capable terminal:
```toml
[preview]
image_protocol = "sixel"
```

Verify sixel support with: `foot --version` (must say sixel-enabled) or test
with `convert -size 100x100 xc:blue sixel:- | cat`.

#### 69.2.5 Shell Integration (cd on Exit)

The canonical shell integration spawns a temporary file for Yazi to write its
CWD into on exit, then `cd`s to it. Add to your shell's rc:

```bash
# ~/.zshrc — bash-compatible version also works
function ya() {
    local tmp
    tmp="$(mktemp -t yazi-cwd.XXXXX)"
    yazi "$@" --cwd-file="$tmp"
    local cwd
    cwd="$(cat "$tmp")"
    [[ -n "$cwd" && "$cwd" != "$PWD" ]] && builtin cd -- "$cwd"
    rm -f "$tmp"
}
```

```fish
# ~/.config/fish/config.fish
function ya
    set tmp (mktemp -t yazi-cwd.XXXXX)
    yazi $argv --cwd-file="$tmp"
    set cwd (cat "$tmp")
    if test -n "$cwd" -a "$cwd" != "$PWD"
        builtin cd "$cwd"
    end
    rm -f "$tmp"
end
```

#### 69.2.6 Plugins

Plugins live in `~/.config/yazi/plugins/` as `.yazi` directories. Install with
`ya pack` (the Yazi CLI) or manually via git:

```bash
# Install the official package manager helper
ya pack -a yazi-rs/plugins#chmod
ya pack -a yazi-rs/plugins#diff
ya pack -a yazi-rs/plugins#fzf
ya pack -a yazi-rs/plugins#smart-filter
ya pack -a yazi-rs/plugins#zoxide
ya pack -a yazi-rs/plugins#starship

# Markdown preview via glow
ya pack -a Reledia/glow.yazi

# CSV/table preview
ya pack -a Reledia/miller.yazi
```

Activate plugins in `keymap.toml`:
```toml
{ on = ["f"],  run = "plugin fzf",           desc = "fzf jump" },
{ on = ["z"],  run = "plugin zoxide",        desc = "Zoxide jump" },
{ on = ["-"],  run = "plugin starship",      desc = "Starship prompt" },
```

---

### 69.3 lf — The Veteran TUI Manager

lf (written in Go) has been the TUI file manager of choice for shell-scripting
enthusiasts since 2017. Its configuration is a mix of a custom `lfrc` script and
external shell scripts for previewing, opening, and cleaning up. Unlike Yazi,
every preview behaviour is handled by shell scripts you write yourself — which
is a feature, not a bug, if you want fine-grained control.

**Installation:**
```bash
sudo pacman -S lf
# Or latest via Go:
env CGO_ENABLED=0 go install -ldflags="-s -w" github.com/gokcehan/lf@latest
```

#### 69.3.1 Core Configuration

```
# ~/.config/lf/lfrc
set shell bash
set shellopts '-eu'
set ifs "\n"
set scrolloff 10
set icons true
set period 1
set hidden true
set drawbox true
set ratios 1:2:3
set cleaner ~/.config/lf/cleaner
set previewer ~/.config/lf/previewer

# Keybindings
map <enter>  open
map q        quit
map D        delete
map R        rename
map Y        $lf -remote "send $id copy $(pwd)/$(basename $f)"
map .        set hidden!
map <c-r>    reload
map <c-s>    set sortby size; set info size

# Jump to home/root
map g/ cd /
map gh cd ~
map gd cd ~/Downloads
map gc cd ~/.config

# Bulk rename with vimv/vidir
map B $vidir

# Create file or directory
map a $touch "$(echo | fzf --print-query)"
map A $mkdir -p "$(echo | fzf --print-query)"

# Open terminal in current dir
map <c-t> $kitty &
```

#### 69.3.2 Preview Script with Kitty/chafa Fallback

```bash
#!/usr/bin/env bash
# ~/.config/lf/previewer — make executable: chmod +x ~/.config/lf/previewer

set -eu

FILE="$1"
W="$2"
H="$3"
X="$4"
Y="$5"

MIMETYPE="$(file --dereference --brief --mime-type -- "$FILE")"

case "$MIMETYPE" in
    image/*)
        if [[ "$TERM" == "xterm-kitty" ]]; then
            kitty +kitten icat \
                --silent \
                --stdin no \
                --transfer-mode file \
                --place "${W}x${H}@${X}x${Y}" \
                -- "$FILE" </dev/null >/dev/tty
            exit 1  # signal lf not to clear
        else
            chafa --format symbols --size "${W}x${H}" -- "$FILE"
        fi
        ;;
    video/*)
        CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/lf/thumb.$(stat --printf '%n\0%i\0%F\0%s\0%W\0%Y' \
            -- "$FILE" | sha256sum | cut -d' ' -f1)"
        [[ -f "$CACHE" ]] || ffmpegthumbnailer -i "$FILE" -o "$CACHE" -s 0 -q 5
        if [[ "$TERM" == "xterm-kitty" ]]; then
            kitty +kitten icat --silent --stdin no --transfer-mode file \
                --place "${W}x${H}@${X}x${Y}" -- "$CACHE" </dev/null >/dev/tty
            exit 1
        else
            chafa --format symbols --size "${W}x${H}" -- "$CACHE"
        fi
        ;;
    text/*)
        bat --color=always --style=numbers,changes --line-range=:200 -- "$FILE"
        ;;
    application/pdf)
        pdftotext -l 5 -nopgbrk -q -- "$FILE" -
        ;;
    application/zip|application/x-tar|application/x-bzip2|application/gzip)
        atool --list -- "$FILE"
        ;;
    *)
        file --dereference --brief -- "$FILE"
        ;;
esac
```

```bash
#!/usr/bin/env bash
# ~/.config/lf/cleaner — clears kitty image when navigating away
[[ "$TERM" == "xterm-kitty" ]] && kitty +kitten icat --clear --silent
exit 0
```

Make both executable:
```bash
chmod +x ~/.config/lf/previewer ~/.config/lf/cleaner
```

#### 69.3.3 Icon Support

lf reads icons from the `LF_ICONS` environment variable. Add to your shell:
```bash
# ~/.zshrc
export LF_ICONS="\
di=:\
fi=:\
ln=:\
or=:\
ex=:\
*.vimrc=:\
*.viminfo=:\
*.gitconfig=:\
*.py=:\
*.rs=:\
*.toml=:\
*.json=:\
*.md=:\
*.pdf=:\
*.png=:\
*.jpg=:\
*.mp4=:\
*.zip=:\
"
```

---

### 69.4 Thunar — Lightweight GUI Manager

Thunar is the XFCE file manager. It is GTK3-based, extremely lightweight (~30 MB
RSS idle), and integrates cleanly into any GTK-themed Wayland setup. It does not
require a running XFCE session — just the binary and its dependencies.

**Installation:**
```bash
sudo pacman -S thunar thunar-volman thunar-archive-plugin thunar-media-tags-plugin
sudo pacman -S tumbler ffmpegthumbnailer gvfs gvfs-mtp gvfs-smb gvfs-nfs
```

`tumbler` provides the thumbnail daemon. Without it, no preview thumbnails appear.
`gvfs` provides virtual filesystem support (MTP devices, network shares).

#### 69.4.1 Theming

Thunar inherits from the active GTK3 theme. Configure via:
```bash
# Icon theme
gsettings set org.gnome.desktop.interface icon-theme "Papirus-Dark"

# GTK theme (if not managed by nwg-look / lxappearance)
gsettings set org.gnome.desktop.interface gtk-theme "Catppuccin-Mocha-Standard-Blue-Dark"

# Font
gsettings set org.gnome.desktop.interface font-name "Inter 10"
```

See Ch 35 for full GTK theming; the same settings apply.

#### 69.4.2 Custom Actions

Custom actions appear in the right-click menu. Access via Edit → Configure
Custom Actions. Useful entries:

| Name | Command | Condition |
|------|---------|-----------|
| Open Terminal Here | `kitty --working-directory %f` | Directories |
| Open as Root | `pkexec thunar %f` | Directories |
| Set Wallpaper | `swww img %f` | Image files |
| Copy Path | `wl-copy %f` | All files |
| Open in Neovim | `kitty nvim %f` | Text files |

Add via the GUI, or manipulate the XML file directly:
```bash
# Actions file location
~/.config/Thunar/uca.xml
```

Example `uca.xml` entry for "Open Terminal Here":
```xml
<action>
    <icon>utilities-terminal</icon>
    <name>Open Terminal Here</name>
    <submenu></submenu>
    <unique-id>1700000000000000-1</unique-id>
    <command>kitty --working-directory %f</command>
    <description>Open a Kitty terminal in this directory</description>
    <range></range>
    <patterns>*</patterns>
    <directories/>
</action>
```

#### 69.4.3 Autostart and Daemon Mode

Thunar can run as a daemon (useful for fast startup and auto-mounting):
```bash
# Add to Hyprland/Sway exec-once or systemd user service
thunar --daemon &
```

Hyprland example (see Ch 53):
```ini
# ~/.config/hypr/hyprland.conf
exec-once = thunar --daemon
```

#### 69.4.4 Polkit for Drive Mounting

Thunar requires a running polkit authentication agent to mount removable drives
without a root password prompt. See Ch 71 for full polkit setup. Minimal:
```bash
exec-once = /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1
# or, for KDE polkit agent:
exec-once = /usr/lib/kde/polkit-kde-authentication-agent-1
```

---

### 69.5 Dolphin — Qt6 Feature-Rich Manager

Dolphin is the KDE Plasma file manager. It is the most feature-complete GUI
option: split-pane views, inline terminal, extensive thumbnail support, service
menus, and deep integration with KIO (KDE I/O workers) for network and remote
filesystem access. It runs perfectly outside a full Plasma session.

**Installation:**
```bash
sudo pacman -S dolphin ffmpegthumbs kdegraphics-thumbnailers kimageformats
# KIO workers for network/remote filesystems
sudo pacman -S kio-extras kio-fuse
```

#### 69.5.1 Essential Settings

All Dolphin preferences are stored in `~/.config/dolphinrc` (KConfig format).
Key UI configuration:

```ini
# ~/.config/dolphinrc  — partial, can be edited directly
[General]
ShowFullPath=true
ShowFullPathInTitlebar=false
SortingChoice=NaturalSorting
UseTabForSwitchingSplitView=true

[IconsMode]
PreviewSize=64
TextWidthIndex=1

[MainWindow]
MenuBar=Disabled
ToolBar=Disabled
```

Via the GUI:
- View → Show Hidden Files (`Ctrl+H`)
- Control → Configure Dolphin → Startup → Default Folder → `$HOME`
- View → Panels → Terminal (embedded Konsole below file pane — works with any
  Konsole-based terminal)
- Settings → Configure Dolphin → General → Previews → enable all desired types

#### 69.5.2 Theming

Dolphin uses Qt6/Kvantum theming (see Ch 36). Set icon theme through:
```bash
# Using KDE's configuration tool (works outside Plasma session)
kwriteconfig5 --file kdeglobals --group Icons --key Theme "Papirus-Dark"
# Reload KDE icon cache
kbuildsycoca5 --noincremental
```

Or via environment variables in your Wayland session startup:
```bash
export QT_QPA_PLATFORMTHEME=gtk3   # inherit GTK theme (simple approach)
# or:
export QT_STYLE_OVERRIDE=kvantum   # use Kvantum theme engine
```

#### 69.5.3 Service Menus

Service menus add entries to Dolphin's right-click context menu. They live in
`~/.local/share/kservices5/ServiceMenus/` as `.desktop` files:

```ini
# ~/.local/share/kservices5/ServiceMenus/open-terminal.desktop
[Desktop Entry]
Type=Service
ServiceTypes=KonqPopupMenu/Plugin
MimeType=inode/directory;
Actions=openTerminal

[Desktop Action openTerminal]
Name=Open Kitty Here
Icon=utilities-terminal
Exec=kitty --working-directory %f
```

#### 69.5.4 Split View and Keyboard Navigation

Dolphin's split view (`F3`) is particularly useful for file operations. Key
bindings:
- `F3` — toggle split view
- `Ctrl+T` — new tab
- `Alt+Left/Right` — navigate history
- `F4` — toggle embedded terminal
- `Ctrl+L` — edit location bar (type paths directly)

---

### 69.6 nnn — Ultraminimal TUI Manager

nnn is written in C and compiles to a ~100 KB binary with zero runtime
dependencies (apart from ncurses). It is the right choice when you need a file
manager on a minimal server, inside a container, or in an environment where even
Go is too heavy.

**Installation:**
```bash
sudo pacman -S nnn
```

**Basic configuration via environment variables:**
```bash
# ~/.zshrc
export NNN_OPTS="dEHr"      # d=detail, E=edit in EDITOR, H=show hidden, r=use readline
export NNN_PLUG="p:preview-tui;f:fzcd;z:autojump"
export NNN_FCOLORS="0B0B04060006060009060B06"
export NNN_BMS="d:$HOME/Downloads;D:$HOME/Documents;c:$HOME/.config"
export EDITOR=nvim
```

**cd on exit (like Yazi):**
```bash
function n() {
    local tmp
    tmp="$(mktemp -t nnn-cwd.XXXXX)"
    nnn -p "$tmp" "$@"
    local dir
    dir="$(cat "$tmp")"
    [[ -n "$dir" ]] && [[ -d "$dir" ]] && builtin cd "$dir"
    rm -f "$tmp"
}
```

---

### 69.7 Mounting Drives Without Polkit

If no polkit authentication agent is running, mounting removable drives fails
silently in all GUI file managers. The GUI simply does nothing, or shows a
cryptic permission error. There are three solutions:

**Option A — Launch a polkit agent at session startup (recommended):**
```bash
# Hyprland — ~/.config/hypr/hyprland.conf
exec-once = /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1

# Sway — ~/.config/sway/config
exec /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1
```

**Option B — Manual mount via udisksctl (no polkit needed):**
```bash
# List available block devices
lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT

# Mount by device path
udisksctl mount -b /dev/sdb1

# Mount by UUID
udisksctl mount -b /dev/disk/by-uuid/XXXX-YYYY

# Unmount
udisksctl unmount -b /dev/sdb1

# Power off (safe removal for USB drives)
udisksctl power-off -b /dev/sdb
```

**Option C — udevil (mount without polkit at all):**
```bash
sudo pacman -S udevil
# udevil mounts based on /etc/udevil/udevil.conf rules
udevil mount /dev/sdb1
devmon --no-gui &   # auto-mount daemon
```

See Ch 71 for comprehensive polkit configuration including rule files and
allowed operations.

---

### 69.8 File Association on Wayland

`xdg-open` is the universal file-opener on freedesktop systems. It consults
`xdg-mime` to map MIME types to application `.desktop` files. On Wayland, the
mechanism is identical to X11.

**Query and set associations:**
```bash
# Check what MIME type a file is
xdg-mime query filetype ~/pictures/foo.png
# → image/png

# Check current application for a MIME type
xdg-mime query default image/png
# → imv.desktop

# Set association
xdg-mime default imv.desktop    image/png
xdg-mime default imv.desktop    image/jpeg
xdg-mime default imv.desktop    image/webp
xdg-mime default mpv.desktop    video/mp4
xdg-mime default mpv.desktop    video/x-matroska
xdg-mime default zathura.desktop application/pdf
xdg-mime default nvim.desktop   text/plain
```

Associations are stored per-user in `~/.config/mimeapps.list`:
```ini
# ~/.config/mimeapps.list
[Default Applications]
image/png=imv.desktop
image/jpeg=imv.desktop
image/webp=imv.desktop
video/mp4=mpv.desktop
video/x-matroska=mpv.desktop
application/pdf=zathura.desktop
text/plain=nvim.desktop
text/x-python=nvim.desktop
text/x-rust=nvim.desktop
```

**Finding a MIME type for a new file extension:**
```bash
# Look up registered types
grep -r "\.mkv" /usr/share/mime/
# or
mimetype ~/video.mkv   # from perl-file-mimeinfo package
```

**Registering a custom `.desktop` file:**
```bash
# ~/.local/share/applications/mpv.desktop  (already exists usually)
# After modifying, update the desktop database:
update-desktop-database ~/.local/share/applications/
```

---

### 69.9 Thumbnail Caching and Management

All GUI managers use the freedesktop thumbnail specification: thumbnails are
stored as PNG files in `~/.cache/thumbnails/` with filenames derived from a
URI hash. Tumbler generates them on demand for Thunar; Dolphin uses its own
thumbnail plugins; Nautilus generates them inline.

**Manually generate thumbnails:**
```bash
# Force tumbler to generate for a directory (Thunar)
tumbler-generator ~/.local/share/wallpapers/

# Check thumbnail cache size
du -sh ~/.cache/thumbnails/

# Clear stale thumbnails
find ~/.cache/thumbnails/ -mtime +30 -delete
```

**Dolphin thumbnail plugins** are separate packages:
```bash
sudo pacman -S ffmpegthumbs           # video thumbnails
sudo pacman -S kdegraphics-thumbnailers  # PDF, PS, raw images
sudo pacman -S kimageformats          # extra image formats (HEIF, AVIF, JXL)
```

Enable them in Dolphin → Settings → Configure Dolphin → General → Previews.

---

### 69.10 Integrating File Managers with Your Wayland Compositor

Bind a key to open your preferred file manager from the compositor. Examples:

**Hyprland (`~/.config/hypr/hyprland.conf`):**
```ini
# Open Thunar with Super+E
bind = $mainMod, E, exec, thunar

# Open Yazi in a Kitty float window with Super+Shift+E
bind = $mainMod SHIFT, E, exec, kitty --class floating-yazi -e ya

# Floating rule for Yazi window
windowrulev2 = float, class:floating-yazi
windowrulev2 = size 1200 800, class:floating-yazi
windowrulev2 = center, class:floating-yazi
```

**Sway (`~/.config/sway/config`):**
```
bindsym $mod+e exec thunar
bindsym $mod+shift+e exec kitty --class=floating-yazi -e yazi
for_window [app_id="floating-yazi"] floating enable, resize set 1200 800
```

For session startup (daemon mode), see Ch 53.

---

## Troubleshooting

**Yazi shows no image previews**

1. Confirm the terminal supports the configured protocol:
   ```bash
   # Test Kitty protocol
   kitty +kitten icat /path/to/image.png
   # Test sixel
   convert -size 80x24 xc:blue sixel:- | cat
   ```
2. Check `image_protocol` in `~/.config/yazi/yazi.toml` matches your terminal.
3. Ensure `imagemagick` and `ffmpegthumbnailer` are installed.
4. Run `yazi` with `RUST_LOG=debug yazi 2>/tmp/yazi.log` and inspect the log.

**lf previewer script not executing**

```bash
# Verify it's executable
ls -la ~/.config/lf/previewer
# If not:
chmod +x ~/.config/lf/previewer ~/.config/lf/cleaner
# Test manually
~/.config/lf/previewer ~/Pictures/test.png 80 40 0 0
```

**Thunar shows no thumbnails**

1. Confirm tumbler is running: `pgrep tumblerd`
2. Start it: `tumblerd &`
3. Clear corrupted cache: `rm -rf ~/.cache/thumbnails/`
4. Ensure `ffmpegthumbnailer` is installed for video thumbnails.
5. Check `~/.config/tumbler/tumbler.rc` — all desired thumbnailer sections must
   have `Disabled=false`.

**Thunar / Dolphin cannot mount drives (silent failure)**

Run `journalctl -xe | grep -i polkit` to see polkit denials. Launch a polkit
agent (see §69.7 Option A). Verify with: `udisksctl info -b /dev/sdb1`.

**Dolphin opens very slowly outside Plasma**

KDE services start lazily. Pre-start the required services:
```bash
# Add to session startup (Ch 53)
exec-once = /usr/lib/kf5/kded5 &
exec-once = /usr/lib/kf5/kcookiejar5 --daemonize
```

Or use `kquitapp5 dolphin` and relaunch — subsequent opens are fast once KIO
workers are cached.

**xdg-open opens the wrong application**

Check priority order in `mimeapps.list`:
```bash
cat ~/.config/mimeapps.list
# System-level defaults (lower priority):
cat /usr/share/applications/mimeinfo.cache | grep "image/png"
```

Update with `xdg-mime default <app>.desktop <mime/type>` and verify:
```bash
xdg-mime query default image/png
```

**nnn: no icons showing**

nnn requires a Nerd Font. Set your terminal's font to one (e.g. JetBrainsMono
Nerd Font) and set `NNN_OPTS` to not include the `N` flag (which disables icons).

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
