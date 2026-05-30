# Chapter 28 — Application Launchers: fuzzel, rofi, wofi, Anyrun, walker, tofi

## Contents

- [Overview](#overview)
- [28.1 fuzzel — Fast and Minimal](#281-fuzzel-fast-and-minimal)
- [28.2 rofi (Wayland fork) — The Feature-Complete Option](#282-rofi-wayland-fork-the-feature-complete-option)
- [28.3 wofi — GTK Wayland Launcher](#283-wofi-gtk-wayland-launcher)
- [28.4 tofi — Minimal dmenu Replacement](#284-tofi-minimal-dmenu-replacement)
- [28.5 Anyrun — CSS-Customizable Plugin Launcher](#285-anyrun-css-customizable-plugin-launcher)
- [28.6 walker — GTK4 Launcher](#286-walker-gtk4-launcher)
- [28.7 bemenu — Dynamic Menu Library](#287-bemenu-dynamic-menu-library)
- [28.8 Launcher Comparison Table](#288-launcher-comparison-table)
- [28.9 Power Menu Patterns](#289-power-menu-patterns)
- [28.10 Clipboard and Emoji Pickers](#2810-clipboard-and-emoji-pickers)
- [28.11 Quickshell App Launcher](#2811-quickshell-app-launcher)
- [28.12 Session Startup Integration](#2812-session-startup-integration)
- [Troubleshooting](#troubleshooting)

---


## Overview

Application launchers are one of the most visible components of a riced desktop. On Wayland, they
use the `wlr-layer-shell` protocol to render a floating overlay that intercepts keyboard input and
displays a filtered list of results. Unlike X11 launchers that relied on EWMH hints or root-window
tricks, Wayland launchers must explicitly request exclusive keyboard grab from the compositor, which
makes them protocol-aware by design.

The ecosystem that has grown around Wayland launchers spans everything from ultra-minimal single-
binary tools written in C (fuzzel, tofi) to plugin-heavy GTK4 applications (walker, Anyrun) and the
venerable rofi with its Wayland-native fork. Choosing the right launcher depends on startup latency
requirements, theming preference (CSS vs INI vs rasi), and whether you need to extend the launcher
with custom result sources.

This chapter covers the six most widely used launchers in the Wayland ricing community as of 2025,
explains how each integrates with Sway, Hyprland, and niri, walks through their configuration
formats in detail, provides ready-to-use power-menu and clipboard-picker patterns, and closes with a
full QML app launcher built inside Quickshell. Cross-references to compositor keybinding setup
appear in Ch 15 (Sway keybindings), Ch 8 (Hyprland binds), and Ch 53 (session startup scripts).

---

## 28.1 fuzzel — Fast and Minimal

fuzzel is a Wayland-native application launcher written in C with no runtime dependencies beyond
`libwayland-client`, `libxkbcommon`, `cairo`, `pango`, and optionally `libpng`/`librsvg` for icons.
Its primary design goal is startup latency: on a modern machine fuzzel typically presents its window
within 20–40 ms of invocation, beating most GTK and Qt-based alternatives by an order of magnitude.

Configuration lives in `~/.config/fuzzel/fuzzel.ini` and uses a familiar INI-style format with
clearly named sections. fuzzel supports two distinct operational modes: the default application
launcher mode (reads `.desktop` files via XDG lookup) and `--dmenu` mode, which reads lines from
stdin and returns the selected line to stdout, making it a drop-in dmenu replacement for scripts.
In `--dmenu` mode fuzzel does not parse `.desktop` files at all, so startup is even faster.

Icon rendering in fuzzel uses the GTK icon theme lookup algorithm but without loading GTK itself —
it implements the lookup spec directly. You specify the icon theme by name and fuzzel searches the
standard XDG data directories. Scalable (SVG) icons require `librsvg` at compile time; most distro
packages include it. If an icon is missing fuzzel falls back to a text-only entry rather than
breaking the layout.

```ini
# ~/.config/fuzzel/fuzzel.ini
[main]
font=JetBrainsMono Nerd Font:size=13
icon-theme=Papirus-Dark
icons-enabled=yes
terminal=foot
layer=overlay
exit-on-keyboard-focus-loss=yes
fuzzy=yes
width=35
lines=10
horizontal-pad=16
vertical-pad=10
inner-pad=6
image-size-ratio=0.5
anchor=center
prompt=❯ 

[colors]
background=1e1e2eff
text=cdd6f4ff
match=89b4faff
selection=313244ff
selection-text=cdd6f4ff
selection-match=89b4faff
border=89b4faff

[border]
width=2
radius=10

[dmenu]
mode=text
```

```bash
# Bind in Hyprland (hyprland.conf)
bind = $mainMod, D, exec, fuzzel

# Bind in Sway (config)
bindsym $mod+d exec fuzzel

# dmenu-style clipboard picker with cliphist
cliphist list | fuzzel --dmenu | cliphist decode | wl-copy

# Emoji picker — requires a newline-delimited emoji list
cat ~/.local/share/emoji.txt | fuzzel --dmenu --prompt="emoji > " | wl-copy
```

fuzzel supports a `--log-level` flag (`none`, `quiet`, `warning`, `error`, `info`, `debug`) which
is invaluable when debugging icon lookup failures or font rendering issues. Run
`fuzzel --log-level=debug 2>&1 | head -60` to see the full icon theme resolution path.

---

## 28.2 rofi (Wayland fork) — The Feature-Complete Option

The upstream `davatorium/rofi` never gained Wayland support before development slowed. The
`lbonn/rofi` fork (also packaged as `rofi-wayland` in many distros) adds a Wayland backend using
`wlr-layer-shell` while keeping full API and theme compatibility with upstream. As of 2025 the fork
is essentially the de facto standard and is what most distributions ship when you install `rofi` on
a Wayland system.

rofi's power comes from its mode system. Built-in modes include `drun` (scans `.desktop` files),
`run` (PATH executables), `window` (lists open windows via `_NET_WM_DESKTOP` on X11 or
`hyprland/clients` on Hyprland), `ssh` (reads `~/.ssh/config` and `known_hosts`), and `filebrowser`
(interactive directory navigation). Each mode can be layered using the `combi` meta-mode:
`rofi -show combi -combi-modes drun,ssh` presents a merged result list with a mode badge on each
entry.

Themes in rofi use the `.rasi` format (Rofi Advanced Style Information), a CSS-inspired language
that supports variables, inheritance, and conditional element visibility. The community repository
at `github.com/newmanls/rofi-themes-collection` and `adi1090x/rofi` have hundreds of production-
quality themes. Writing your own `.rasi` theme gives you pixel-level control over every element:
input box, list container, scrollbar, mode switcher, and message box.

```rasi
/* ~/.config/rofi/theme.rasi — Catppuccin Mocha single-column */
* {
    bg:       #1e1e2e;
    bg-alt:   #313244;
    fg:       #cdd6f4;
    fg-dark:  #a6adc8;
    accent:   #89b4fa;
    urgent:   #f38ba8;

    background-color:   transparent;
    text-color:         @fg;
    border-color:       @accent;
    font:               "JetBrainsMono Nerd Font 12";
}

window {
    background-color: @bg;
    border:           2px;
    border-radius:    12px;
    padding:          16px;
    width:            500px;
}

mainbox { children: [inputbar, listview]; spacing: 8px; }

inputbar {
    background-color: @bg-alt;
    border-radius:    8px;
    padding:          8px 12px;
    children:         [prompt, entry];
}

prompt { text-color: @accent; }
entry  { placeholder: "Search…"; placeholder-color: @fg-dark; }

listview {
    lines:      10;
    scrollbar:  false;
    spacing:    4px;
}

element {
    border-radius:    6px;
    padding:          6px 12px;
    children:         [element-icon, element-text];
    spacing:          8px;
}

element selected { background-color: @bg-alt; text-color: @accent; }
element-icon     { size: 1.5em; }
```

```bash
# Launch app launcher
rofi -show drun -theme ~/.config/rofi/theme.rasi

# Window switcher
rofi -show window -theme ~/.config/rofi/theme.rasi

# Run arbitrary command
rofi -show run -theme ~/.config/rofi/theme.rasi

# Custom script modi — results from a shell script
rofi -show mymodi -modi "mymodi:~/.config/rofi/scripts/bookmarks.sh" \
     -theme ~/.config/rofi/theme.rasi
```

Custom modi scripts must handle two invocation patterns: when called with no arguments, they print
a newline-delimited result list; when called with the selected entry as the argument, they execute
the associated action. The script sets the return code to 0 on success or 1 to reopen the menu.
This bidirectional protocol allows full state machines (e.g., a nested file browser that changes
directory on selection).

---

## 28.3 wofi — GTK Wayland Launcher

wofi was created as a GTK3 Wayland-native launcher during the early days of the Wayland ecosystem
when alternatives were scarce. It uses `gtk-layer-shell` for overlay rendering and GTK's built-in
CSS theming engine, which means styling is done with standard CSS applied to GTK widget names. The
CSS selectors that wofi exposes (`#window`, `#input`, `#scroll`, `#inner-box`, `#entry`, `#text`,
`#img`) are well-documented and familiar to web developers.

wofi supports three modes: `drun` (`.desktop` file launcher), `run` (PATH search), and `dmenu`
(stdin-to-stdout filtering). It does not have a plugin or scripting system beyond these three. For
simple use cases wofi is perfectly adequate; however, active development has slowed significantly
since 2022 and several long-standing bugs (emoji rendering, multi-monitor positioning) remain
unfixed. For new ricing setups in 2025 fuzzel or tofi are generally recommended for minimal use and
walker or Anyrun for feature-complete use.

```css
/* ~/.config/wofi/style.css — Gruvbox dark */
window {
    background-color: #282828;
    border:           2px solid #d79921;
    border-radius:    10px;
    font-family:      "JetBrainsMono Nerd Font";
    font-size:        13px;
}

#input {
    margin:           8px;
    padding:          6px 12px;
    background-color: #3c3836;
    color:            #ebdbb2;
    border:           1px solid #504945;
    border-radius:    6px;
}

#scroll { margin: 0 8px 8px 8px; }

#entry { padding: 6px 12px; border-radius: 4px; }
#entry:selected { background-color: #3c3836; }

#text { color: #ebdbb2; }
#text:selected { color: #d79921; }
```

```bash
# ~/.config/wofi/config
width=400
height=400
location=center
show=drun
prompt=Search
filter_rate=100
allow_markup=true
no_actions=true
halign=fill
orientation=vertical
content_halign=fill
insensitive=true
allow_images=true
image_size=24
gtk_dark=true
```

```bash
# Launch wofi app launcher
wofi --show drun --style ~/.config/wofi/style.css

# dmenu mode for scripted use
printf "option1\noption2\noption3" | wofi --show dmenu --prompt "Pick:"
```

---

## 28.4 tofi — Minimal dmenu Replacement

tofi occupies the extreme minimalist end of the launcher spectrum. It has zero runtime library
dependencies beyond `libwayland-client`, `libxkbcommon`, `cairo`, and `pango`. There is no GTK,
no Qt, no icon loading (unless the `--icon-theme` build option is enabled), and no plugin system.
It renders a simple text list in a layer-shell surface and returns the selected entry to stdout.
This design means tofi starts in under 10 ms on typical hardware — fast enough to feel instant
even when bound to a frequently used shortcut.

Despite its simplicity tofi's configuration is surprisingly rich. The `~/.config/tofi/config` file
(or any path passed via `--config`) accepts options for colours, font, padding, corner radius,
border, anchor point, width/height (absolute or percentage), horizontal vs vertical layout,
fuzzy vs exact matching, result count, and ASCII/Unicode prompt. The full option reference is
in `man 5 tofi`.

```tofi
# ~/.config/tofi/config
font = JetBrainsMono Nerd Font
font-size = 13
prompt-text = " run: "
num-results = 8
fuzzy-match = true
width = 480
height = 0
horizontal = false
background-color = #1e1e2e
text-color = #cdd6f4
prompt-color = #89b4fa
selection-color = #f5c2e7
selection-background = #313244
border-width = 2
border-color = #89b4facc
corner-radius = 10
padding-top = 8
padding-bottom = 8
padding-left = 12
padding-right = 12
result-spacing = 4
min-input-width = 0
outline-width = 0
anchor = center
```

```bash
# App launcher
tofi-drun

# dmenu replacement
tofi-run

# Power menu
chosen=$(printf "Shutdown\nReboot\nLogout\nSuspend\nLock" | tofi --prompt-text " power: ")
case "$chosen" in
    Shutdown) systemctl poweroff ;;
    Reboot)   systemctl reboot ;;
    Logout)   loginctl terminate-session "$XDG_SESSION_ID" ;;
    Suspend)  systemctl suspend ;;
    Lock)     loginctl lock-session ;;
esac

# Clipboard with cliphist
cliphist list | tofi --prompt-text " clip: " | cliphist decode | wl-copy

# Emoji picker
cat /usr/share/unicode/emoji/emoji-sequences.txt \
  | grep -v '^#' | awk '{print $1}' \
  | tofi --prompt-text " emoji: " | wl-copy
```

tofi ships two pre-built entry points: `tofi-drun` (reads `.desktop` files and launches via
`gio open` or direct `Exec` field) and `tofi-run` (searches `$PATH`). Both are thin wrappers that
invoke `tofi` with appropriate flags. For custom use you invoke `tofi` directly with stdin data.

---

## 28.5 Anyrun — CSS-Customizable Plugin Launcher

Anyrun takes a radically different architecture from the launchers above. Rather than being a
monolithic tool with built-in modes, Anyrun is a launcher framework: it provides a GTK4 window
with layer-shell integration, CSS theming support, and a Rust plugin API. All result sources —
applications, web search, calculator, dictionary, clipboard — are separate `.so` shared libraries
loaded at runtime from a configured directory.

The plugin architecture means you can add arbitrary result sources without forking the main binary.
Official plugins live in the Anyrun repository: `applications` (`.desktop` file launcher),
`websearch` (configurable search engines), `translate` (LibreTranslate API), `dictionary`
(offline lookup), `rink` (a Rust unit calculator), `shell` (runs shell commands directly), and
`symbols` (Unicode character search). Each plugin has its own TOML config file in
`~/.config/anyrun/`.

Writing a custom Anyrun plugin requires implementing the `anyrun_interface::Plugin` trait in Rust,
compiling it as `cdylib`, and placing the resulting `.so` in the plugin directory. The trait has
three required methods: `info()` returns metadata (name, description), `get_matches(input)` returns
a `Vec<Match>` for the current query, and `handler(selection)` executes the chosen result. Anyrun
calls `get_matches` asynchronously so plugins can perform network requests or file I/O without
blocking the UI.

```toml
# ~/.config/anyrun/config.toml
width = { fraction = 0.3 }
y_offset = 160
x_offset = { fraction = 0.35 }
layer = "overlay"
hide_icons = false
ignore_exclusive_zones = false
steal_focus = true
plugins = [
  "libapplications.so",
  "librink.so",
  "libshell.so",
  "libwebsearch.so",
  "libsymbols.so",
]
```

```toml
# ~/.config/anyrun/applications.toml
desktop_actions = true
max_entries = 8
terminal = "foot"
```

```toml
# ~/.config/anyrun/websearch.toml
[[engines]]
name = "DuckDuckGo"
prefix = "?"
url = "https://duckduckgo.com/?q={}"

[[engines]]
name = "GitHub"
prefix = "gh"
url = "https://github.com/search?q={}"
```

```css
/* ~/.config/anyrun/style.css */
#window, #match, #container, #main {
    background: transparent;
}

#outer-box {
    background: rgba(30,30,46,0.95);
    border: 2px solid #89b4fa;
    border-radius: 12px;
    padding: 16px;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 13px;
}

#entry {
    background: rgba(49,50,68,0.8);
    border: none;
    border-radius: 8px;
    color: #cdd6f4;
    padding: 8px 12px;
    margin-bottom: 8px;
}

#match {
    border-radius: 6px;
    padding: 6px 12px;
    color: #cdd6f4;
}

#match:selected { background: rgba(49,50,68,0.9); color: #89b4fa; }
#match-desc     { font-size: 11px; color: #a6adc8; }
```

```bash
# Launch anyrun
anyrun

# Bind in Hyprland
bind = $mainMod, SPACE, exec, anyrun
```

---

## 28.6 walker — GTK4 Launcher

walker is a modern GTK4 application launcher that targets feature-completeness combined with GTK4's
improved rendering pipeline. It ships a wide array of built-in modules activated via configuration:
applications (`.desktop` files), files (fd-based search), websearch, commands (shell), clipboard
(wl-clipboard / cliphist integration), emojis, SSH hosts, and a built-in calculator using
libqalculate. Modules can be individually enabled, disabled, and reordered; the result list merges
all active modules with configurable per-module weights.

walker uses a TOML configuration file at `~/.config/walker/config.toml` and a separate CSS file
for theming. The GTK4 CSS engine is more capable than GTK3's — it supports CSS transitions and
`:hover` pseudo-classes that actually work — though the trade-off is a slightly higher baseline
startup time compared to fuzzel or tofi. walker mitigates this by shipping a background daemon mode
(`walker --gapplication-service`) that keeps the process warm; the keybinding then sends a signal
to the daemon to reveal the window rather than spawning a new process.

```toml
# ~/.config/walker/config.toml
[ui]
width        = 500
height       = 0          # auto-size to results
halign       = "center"
valign       = "center"
fullscreen   = false
css          = "~/.config/walker/style.css"

[search]
placeholder  = "Search…"
delay        = 0          # ms before triggering search

[list]
max_entries  = 10

[[modules]]
name    = "applications"
prefix  = ""
weight  = 1

[[modules]]
name    = "clipboard"
prefix  = "cc"
weight  = 2
max     = 10

[[modules]]
name    = "emojis"
prefix  = "em"
weight  = 3

[[modules]]
name    = "commands"
prefix  = "!"
weight  = 4

[[modules]]
name    = "websearch"
prefix  = "?"
weight  = 5
```

```css
/* ~/.config/walker/style.css — Tokyo Night */
window, .window {
    background: transparent;
}

.box {
    background: rgba(26,27,38,0.96);
    border: 2px solid #7aa2f7;
    border-radius: 14px;
    padding: 14px;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 13px;
}

entry {
    background: rgba(36,40,59,0.9);
    border: none;
    border-radius: 8px;
    color: #c0caf5;
    padding: 8px 14px;
}

.item { border-radius: 6px; padding: 6px 12px; color: #c0caf5; }
.item:selected { background: rgba(36,40,59,0.9); color: #7aa2f7; }
.item-sub { color: #565f89; font-size: 11px; }
```

```bash
# One-shot launch
walker

# Daemon mode (add to session startup — see Ch 53)
walker --gapplication-service &

# Signal the daemon to show the window
walker

# Hyprland keybind with daemon pre-warmed
bind = $mainMod, SPACE, exec, walker
```

---

## 28.7 bemenu — Dynamic Menu Library

bemenu positions itself not just as a launcher but as a reusable library. The package ships both a
command-line tool (`bemenu`) that behaves like dmenu and a C library (`libbemenu`) that embeds the
same rendering engine into any C program. This makes bemenu unique among the tools in this chapter:
it can be used as both a scriptable CLI tool and as a UI primitive inside a larger application.

The rendering layer in bemenu is backend-agnostic: a Wayland backend uses `wlr-layer-shell`, an X11
backend uses Xlib, and a curses backend runs inside a terminal. Switching backends at compile time
or via the `BEMENU_BACKEND` environment variable allows the same script to work on both X11 and
Wayland sessions. This portability is valuable for system scripts that need to run in heterogeneous
environments.

```bash
# Install (Arch)
paru -S bemenu bemenu-wayland

# Basic usage — equivalent to dmenu
printf "option1\noption2\noption3" | bemenu -p "Choose:"

# Style flags
bemenu -p "Power:" \
    --fn "JetBrainsMono Nerd Font 13" \
    --tb "#1e1e2e" --tf "#89b4fa" \
    --fb "#1e1e2e" --ff "#cdd6f4" \
    --nb "#1e1e2e" --nf "#cdd6f4" \
    --hb "#313244" --hf "#89b4fa" \
    --bdr "#89b4fa" --border 2 \
    --center --width-factor 0.25

# Use as app launcher via j4-dmenu-desktop
j4-dmenu-desktop --dmenu='bemenu -i -p "run:"'
```

---

## 28.8 Launcher Comparison Table

| Launcher  | Language | Wayland backend       | Theming      | Plugin system | Startup   | Daemon mode |
|-----------|---------|-----------------------|--------------|---------------|-----------|-------------|
| fuzzel    | C       | wlr-layer-shell       | INI colors   | No            | ~30 ms    | No          |
| rofi-wl   | C       | wlr-layer-shell       | .rasi CSS    | Script modi   | ~80 ms    | No          |
| wofi      | C       | gtk-layer-shell (G3)  | GTK3 CSS     | No            | ~90 ms    | No          |
| tofi      | C       | wlr-layer-shell       | config file  | No            | ~10 ms    | No          |
| Anyrun    | Rust    | gtk-layer-shell (G4)  | GTK4 CSS     | Rust .so      | ~120 ms   | No          |
| walker    | Go      | gtk-layer-shell (G4)  | GTK4 CSS     | Module config | ~150 ms   | Yes         |
| bemenu    | C       | wlr-layer-shell / X11 | CLI flags    | No            | ~20 ms    | No          |

Startup times are approximate cold-start figures on an NVMe SSD system. Warm starts (daemon mode or
kernel page cache hot) are typically under 5 ms for all tools. If launch latency is critical,
prefer fuzzel or tofi. If you need clipboard history, emoji, web search, and calculator in one
tool with a single keybinding, walker or Anyrun are more ergonomic.

---

## 28.9 Power Menu Patterns

A power menu is one of the most common launcher scripts on a riced desktop. The pattern is
identical across launchers: pipe a newline-delimited list of options into the launcher's dmenu
interface, capture the selection, and dispatch to systemd or the compositor.

```bash
#!/usr/bin/env bash
# ~/.local/bin/powermenu — works with fuzzel, tofi, or rofi

LAUNCHER="${1:-fuzzel}"   # override via argument

options="  Shutdown\n  Reboot\n  Logout\n  Suspend\n  Lock\n  Hibernate"

case "$LAUNCHER" in
    fuzzel)  chosen=$(printf "$options" | fuzzel --dmenu --prompt=" power: ") ;;
    tofi)    chosen=$(printf "$options" | tofi --prompt-text " power: ") ;;
    rofi)    chosen=$(printf "$options" | rofi -dmenu -p " power") ;;
    bemenu)  chosen=$(printf "$options" | bemenu -p " power:") ;;
    *)       echo "Unknown launcher: $LAUNCHER"; exit 1 ;;
esac

[[ -z "$chosen" ]] && exit 0

case "${chosen##* }" in   # strip Nerd Font icon prefix
    Shutdown)  systemctl poweroff ;;
    Reboot)    systemctl reboot ;;
    Logout)
        # Detect compositor and dispatch appropriately
        if   pgrep -x sway    >/dev/null; then swaymsg exit
        elif pgrep -x Hyprland>/dev/null; then hyprctl dispatch exit
        elif pgrep -x niri    >/dev/null; then niri msg action quit --skip-confirmation
        else loginctl terminate-session "$XDG_SESSION_ID"
        fi ;;
    Suspend)   systemctl suspend ;;
    Lock)      loginctl lock-session ;;
    Hibernate) systemctl hibernate ;;
esac
```

```bash
# Bind in Hyprland
bind = $mainMod SHIFT, P, exec, ~/.local/bin/powermenu fuzzel

# Bind in Sway
bindsym $mod+Shift+p exec ~/.local/bin/powermenu fuzzel
```

For a more polished power menu with confirmation dialogs, combine the launcher with a second
`--dmenu` call:

```bash
#!/usr/bin/env bash
# With confirmation for destructive actions
chosen=$(printf "  Shutdown\n  Reboot\n  Logout\n  Suspend\n  Lock" \
    | fuzzel --dmenu --prompt=" power: ")
[[ -z "$chosen" ]] && exit 0

case "${chosen##* }" in
    Shutdown|Reboot|Logout)
        confirm=$(printf "Yes\nNo" | fuzzel --dmenu --prompt=" ${chosen##* }? ")
        [[ "$confirm" != "Yes" ]] && exit 0 ;;
esac

case "${chosen##* }" in
    Shutdown)  systemctl poweroff ;;
    Reboot)    systemctl reboot ;;
    Logout)    loginctl terminate-session "$XDG_SESSION_ID" ;;
    Suspend)   systemctl suspend ;;
    Lock)      loginctl lock-session ;;
esac
```

---

## 28.10 Clipboard and Emoji Pickers

The clipboard picker is arguably used even more frequently than the power menu. The canonical stack
on Wayland is `wl-clipboard` (provides `wl-copy`/`wl-paste`) combined with `cliphist` as the
history daemon. `cliphist` stores clipboard entries in a SQLite database and exposes them via a
`list` subcommand that outputs entries in a dmenu-compatible format.

```bash
# Picker script (brief example — see Ch 32 for full cliphist installation, daemon setup, and picker integration patterns)
cliphist list | fuzzel --dmenu --prompt=" clip: " | cliphist decode | wl-copy
```

For emoji pickers, the cleanest approach uses a pre-built emoji list (rofimoji format or a plain
newline-delimited file). The `rofimoji` package ships one at
`/usr/share/rofimoji/data/emojis_en.csv`; a simpler plain-text list is available in `emoji-data`
packages on most distributions.

```bash
# Emoji picker with fuzzel (plain text list)
chosen=$(grep -v '^#' /usr/share/unicode/emoji/emoji-test.txt \
    | grep 'fully-qualified' \
    | sed 's/.*# //' \
    | fuzzel --dmenu --prompt=" emoji: ")
[[ -n "$chosen" ]] && printf '%s' "${chosen%% *}" | wl-copy
```

```bash
# Hyprland keybindings for picker scripts
bind = $mainMod, V,      exec, cliphist list | fuzzel --dmenu | cliphist decode | wl-copy
bind = $mainMod SHIFT, E,exec, ~/.local/bin/emoji-picker
```

---

## 28.11 Quickshell App Launcher

Quickshell (covered in depth in Ch 18) can build a fully custom launcher using QML. The approach
parses `.desktop` files via `Process` + `gio`, implements fuzzy search in JavaScript, and renders
results in an `IpcHandler`-driven overlay. This gives pixel-perfect control over layout and
animation that no external launcher binary can match, at the cost of more code.

```qml
// ~/.config/quickshell/launcher/Launcher.qml
import Quickshell
import Quickshell.Wayland
import Quickshell.Io
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ShellRoot {
    id: root

    PanelWindow {
        id: launcherWindow
        visible: false
        anchors.centerIn: true
        width: 480
        height: contentCol.implicitHeight + 32
        color: "transparent"

        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

        // Close on Escape
        Keys.onEscapePressed: { query.text = ""; visible = false }

        // Dismiss on focus loss
        onActiveChanged: if (!active) { visible = false }

        Rectangle {
            anchors.fill: parent
            color: "#ee1e1e2e"
            radius: 12
            border.width: 2
            border.color: "#89b4fa"

            ColumnLayout {
                id: contentCol
                anchors { left: parent.left; right: parent.right; top: parent.top }
                anchors.margins: 16
                spacing: 8

                TextField {
                    id: query
                    Layout.fillWidth: true
                    placeholderText: "Search applications…"
                    color: "#cdd6f4"
                    background: Rectangle {
                        color: "#313244"; radius: 8
                    }
                    padding: 10
                    font.family: "JetBrainsMono Nerd Font"
                    font.pixelSize: 14
                    onTextChanged: appModel.filter(text)
                }

                Repeater {
                    model: appModel.filtered
                    delegate: ItemDelegate {
                        Layout.fillWidth: true
                        height: 40
                        text: modelData.name
                        font.family: "JetBrainsMono Nerd Font"
                        font.pixelSize: 13
                        palette.text: "#cdd6f4"
                        palette.highlight: "#313244"
                        palette.highlightedText: "#89b4fa"
                        onClicked: {
                            Process.launch(modelData.exec.replace(/%[fFuUdDnNickvm]/g, ""))
                            query.text = ""
                            launcherWindow.visible = false
                        }
                    }
                }
            }
        }
    }

    // Application model populated by gio
    QtObject {
        id: appModel
        property var all: []
        property var filtered: []

        function load() {
            proc.running = true
        }

        function filter(q) {
            if (q.length === 0) {
                filtered = all.slice(0, 10)
                return
            }
            const lower = q.toLowerCase()
            filtered = all.filter(a =>
                a.name.toLowerCase().includes(lower) ||
                (a.keywords || "").toLowerCase().includes(lower)
            ).slice(0, 10)
        }

        Process {
            id: proc
            command: ["gio", "info", "--query-writable", "applications:"]
            // In practice use: bash -c "find /usr/share/applications ~/.local/share/applications -name '*.desktop'"
            // then parse with a helper script
        }
    }

    // IPC handler — signal from keybind to show/hide
    IpcHandler {
        target: "launcher"
        function toggle() {
            launcherWindow.visible = !launcherWindow.visible
            if (launcherWindow.visible) query.forceActiveFocus()
        }
    }
}
```

```bash
# Signal from Hyprland keybind (see Ch 18 for qs ipc details)
bind = $mainMod, SPACE, exec, qs ipc call launcher toggle
```

A full production Quickshell launcher would use a dedicated `.desktop` parser script that outputs
JSON (name, exec, icon, keywords), loads all entries into `appModel.all` at startup, and pre-caches
icon paths using the XDG icon theme algorithm. The QML fuzzy search function can be upgraded to
score matches by position (prefix match scores higher than mid-word match) for better ranking.
See Ch 18 for the complete Quickshell IPC and Process APIs.

---

## 28.12 Session Startup Integration

All launchers that run in daemon mode (walker) or need clipboard history (cliphist) must be started
as part of the Wayland session. The correct integration point differs by compositor.

```bash
# Sway: add to config
exec cliphist-watch     # wrapper script starting both wl-paste watchers
exec walker --gapplication-service

# Hyprland: add to hyprland.conf
exec-once = bash -c 'wl-paste --type text --watch cliphist store & wl-paste --type image --watch cliphist store &'
exec-once = walker --gapplication-service

# systemd user session (compositor-agnostic — see Ch 53)
# ~/.config/systemd/user/cliphist.service
[Unit]
Description=cliphist clipboard history daemon
PartOf=graphical-session.target

[Service]
ExecStart=/usr/bin/bash -c 'wl-paste --type text --watch cliphist store'
Restart=on-failure

[Install]
WantedBy=graphical-session.target
```

See Ch 53 for a full treatment of session startup ordering and the `graphical-session.target`
dependency tree. See Ch 15 (Sway) and Ch 8 (Hyprland) for compositor-specific keybinding syntax
and the `$mainMod` variable convention.

---

## Troubleshooting

**fuzzel shows no icons**
Check that the icon theme name in `fuzzel.ini` matches an installed theme:
```bash
ls /usr/share/icons/          # system-wide themes
ls ~/.local/share/icons/      # user themes
```
Rebuild the icon cache if needed: `gtk-update-icon-cache -f /usr/share/icons/<theme>`.
Run `fuzzel --log-level=debug 2>&1 | grep icon` to see which paths are searched.

**rofi-wayland fails to list windows**
The `window` mode requires `xdg-desktop-portal-hyprland` (or the equivalent for your compositor)
and `rofi` built with the matching window plugin. Verify:
```bash
rofi -list-detections      # shows available backends and plugins
```
On Hyprland, ensure `hyprland-ipc` is accessible: `hyprctl clients` should list windows.

**Anyrun plugins not loading**
Plugins must match the Anyrun ABI version exactly. If Anyrun was updated, recompile all plugins:
```bash
cd ~/src/anyrun && cargo build --release
ls target/release/lib*.so   # copy these to ~/.config/anyrun/
```

**walker daemon not pre-warming**
Confirm the `--gapplication-service` process is running:
```bash
pgrep -a walker
# Should show: walker --gapplication-service
```
If not, add the `exec-once` line to your compositor config and re-login. If it crashes, check
`journalctl --user -u walker` or `~/.local/share/walker/walker.log`.

**tofi anchor / positioning off on multi-monitor**
tofi uses the focused output by default. To force a specific output:
```bash
tofi-drun --output DP-1
```
List available outputs with `wlr-randr` or `hyprctl monitors`.

**cliphist not capturing images**
Ensure both `wl-paste` watcher instances are running (one for `text`, one for `image`). Check:
```bash
ps aux | grep wl-paste
```
Some applications only write to the `image/png` MIME type; verify with:
```bash
wl-paste --list-types
```

**General: launcher appears on wrong monitor**
Most wlr-layer-shell launchers default to the currently focused output. If your compositor does not
track focus correctly (e.g., focus follows mouse and mouse is between monitors), explicitly pass
`--output` where supported, or use `swaymsg -t get_outputs` / `hyprctl monitors` to identify the
active output and pass it via a wrapper script.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
