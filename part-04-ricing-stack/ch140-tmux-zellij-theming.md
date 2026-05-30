# Chapter 140 — tmux and Zellij Theming

## Overview

Terminal multiplexers are fixtures of nearly every developer rice. They provide session
persistence, split panes, and named windows — and their status bars are a highly visible
design surface. tmux with its status line and Zellij with its tab/status bars both
support deep theming via configuration. This chapter covers both tools: achieving a
coherent look that matches your terminal colorscheme, building powerline-style segments,
using community plugin themes, and integrating with pywal/matugen for dynamic palette
reloading.

---

## 140.1 tmux Status Line Fundamentals

The tmux status line is configured through a set of `set -g` options in `~/.config/tmux/tmux.conf`
(or `~/.tmux.conf`). Every color reference accepts a terminal-color name (`black`, `red`), a
256-color index (`colour231`), or a 24-bit hex value (`#1e1e2e` — requires `terminal-overrides`
to be set for your terminal).

### Enabling True Color

```conf
# ~/.config/tmux/tmux.conf

# Enable true color in tmux itself
set -g default-terminal "tmux-256color"
set -ag terminal-overrides ",xterm-256color:RGB"
# For Kitty / WezTerm / Ghostty / Foot:
set -ag terminal-overrides ",*256col*:Tc"
set -ag terminal-overrides ",xterm-kitty:RGB"
```

### Basic Status Line Structure

```conf
# Status bar position and dimensions
set -g status-position bottom        # top or bottom
set -g status-interval 2             # refresh every 2 seconds
set -g status-justify centre         # left | centre | right (for window list)

# Background and foreground of the status bar itself
set -g status-style "fg=#a9b1d6 bg=#1a1b26"

# Left segment (session name)
set -g status-left-length 30
set -g status-left "#[fg=#1a1b26,bg=#7aa2f7,bold] #S #[fg=#7aa2f7,bg=#1a1b26]"

# Right segment (hostname + time)
set -g status-right-length 60
set -g status-right "#[fg=#3b4261,bg=#1a1b26]#[fg=#a9b1d6,bg=#3b4261] %H:%M #[fg=#7aa2f7,bg=#3b4261]#[fg=#1a1b26,bg=#7aa2f7,bold] #h "

# Window list (center)
set -g window-status-format         "#[fg=#565f89,bg=#1a1b26] #I:#W "
set -g window-status-current-format "#[fg=#1a1b26,bg=#bb9af7,bold] #I:#W #[fg=#bb9af7,bg=#1a1b26]"
set -g window-status-separator ""
```

### Pane Borders

```conf
# Inactive pane border
set -g pane-border-style "fg=#3b4261"
# Active pane border (accent color)
set -g pane-active-border-style "fg=#7aa2f7"
# Pane border lines: single | double | heavy | simple | number
set -g pane-border-lines single

# Message bar (command input at bottom)
set -g message-style "fg=#c0caf5 bg=#3b4261"
set -g message-command-style "fg=#c0caf5 bg=#3b4261"
```

### Mode Colors (copy mode selection)

```conf
set -g mode-style "fg=#1a1b26 bg=#7aa2f7"
```

---

## 140.2 Full Tokyo Night Theme (Manual)

```conf
# ~/.config/tmux/themes/tokyo-night.conf
# Tokyo Night Storm variant

# Palette
TN_BG="#1a1b26"
TN_BG2="#24283b"
TN_SURFACE="#3b4261"
TN_FG="#a9b1d6"
TN_COMMENT="#565f89"
TN_BLUE="#7aa2f7"
TN_PURPLE="#bb9af7"
TN_GREEN="#9ece6a"
TN_CYAN="#7dcfff"
TN_RED="#f7768e"

# Note: tmux doesn't expand shell variables in set -g.
# Use the literal hex values inline:

set -g status-style "fg=#a9b1d6,bg=#1a1b26"
set -g status-left "#[fg=#1a1b26,bg=#7aa2f7,bold] #S #[fg=#7aa2f7,bg=#24283b]#[fg=#7aa2f7,bg=#24283b] "
set -g status-right "#[fg=#24283b,bg=#1a1b26]#[fg=#a9b1d6,bg=#24283b] %d/%m #[fg=#3b4261,bg=#24283b]#[fg=#a9b1d6,bg=#3b4261] %H:%M #[fg=#7aa2f7,bg=#3b4261]#[fg=#1a1b26,bg=#7aa2f7,bold]  #h "
set -g status-left-length  40
set -g status-right-length 80
set -g status-justify      left

set -g window-status-separator ""
set -g window-status-format         " #[fg=#565f89]#I #[fg=#a9b1d6]#W "
set -g window-status-current-format "#[fg=#24283b,bg=#7aa2f7]#[fg=#1a1b26,bg=#7aa2f7,bold] #I #W #[fg=#7aa2f7,bg=#24283b]"
set -g window-status-activity-style "fg=#f7768e,bg=#1a1b26"
set -g window-status-bell-style     "fg=#ff9e64,bg=#1a1b26,blink"

set -g pane-border-style        "fg=#3b4261"
set -g pane-active-border-style "fg=#7aa2f7"
set -g message-style            "fg=#7aa2f7,bg=#24283b"
set -g mode-style               "fg=#1a1b26,bg=#7aa2f7"
set -g copy-mode-current-match-style  "fg=#1a1b26,bg=#ff9e64"
set -g copy-mode-match-style         "fg=#1a1b26,bg=#bb9af7"

# Load this from tmux.conf:
# source-file ~/.config/tmux/themes/tokyo-night.conf
```

---

## 140.3 TPM and Community Theme Plugins

TPM (Tmux Plugin Manager) handles plugin installation with a git-based workflow:

```conf
# Install TPM
# git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm

# ~/.config/tmux/tmux.conf
set -g @plugin 'tmux-plugins/tpm'
set -g @plugin 'tmux-plugins/tmux-sensible'

# --- Pick one community theme ---

# Option A: tmux-tokyo-night
set -g @plugin 'janoamaral/tokyo-night-tmux'
set -g @tokyo-night-tmux_window_id_style none
set -g @tokyo-night-tmux_pane_id_style hsquare
set -g @tokyo-night-tmux_zoom_id_style dsquare
set -g @tokyo-night-tmux_show_music 1

# Option B: Catppuccin tmux
# set -g @plugin 'catppuccin/tmux'
# set -g @catppuccin_flavour 'mocha'
# set -g @catppuccin_window_right_separator "█ "
# set -g @catppuccin_window_status_enable "yes"
# set -g @catppuccin_status_modules_right "directory user host session"

# Initialize TPM (keep at the end of tmux.conf)
run '~/.tmux/plugins/tpm/tpm'
```

Install plugins: inside a tmux session press `<prefix> + I` (capital i).

---

## 140.4 Powerline Separators Reference

Powerline-style status lines use glyphs from Nerd Fonts to create seamless segment transitions:

| Glyph | Nerd Font codepoint | Usage |
|---|---|---|
| `` | U+E0B0 | Right-facing solid arrow (left→right segments) |
| `` | U+E0B2 | Left-facing solid arrow (right←left segments) |
| `` | U+E0B1 | Right-facing thin arrow separator |
| `` | U+E0B3 | Left-facing thin arrow separator |
| `` | U+E0B4 | Right-facing round segment |
| `` | U+E0B6 | Left-facing round segment |

In tmux.conf, embed these as literal UTF-8 characters or paste the glyph directly into the format string.

---

## 140.5 pywal Integration for tmux

When using pywal for dynamic theming, generate a tmux color template:

```bash
# ~/.config/wal/templates/tmux.conf
# Pywal template — variables are substituted at wal runtime

set -g status-style "fg={color7},bg={background}"
set -g status-left  "#[fg={background},bg={color4},bold] #S #[fg={color4},bg={background}]"
set -g status-right "#[fg={color8},bg={background}]#[fg={color7},bg={color8}] %H:%M #[fg={color4},bg={color8}]#[fg={background},bg={color4},bold] #h "
set -g window-status-format         "#[fg={color8}] #I:#W "
set -g window-status-current-format "#[fg={background},bg={color4},bold] #I:#W #[fg={color4},bg={background}]"
set -g pane-border-style            "fg={color8}"
set -g pane-active-border-style     "fg={color4}"
set -g message-style                "fg={color4},bg={background}"
set -g mode-style                   "fg={background},bg={color4}"
```

```bash
# In tmux.conf — source the generated file
if-shell "[ -f ~/.cache/wal/tmux.conf ]" "source-file ~/.cache/wal/tmux.conf"
```

```bash
# After running wal, reload tmux:
wal -i ~/wallpaper.jpg
tmux source-file ~/.config/tmux/tmux.conf
```

---

## 140.6 Zellij Theming Overview

Zellij is a modern terminal multiplexer written in Rust with a built-in layout and
plugin system. Theming is done through `themes` blocks in `~/.config/zellij/config.kdl`:

```kdl
// ~/.config/zellij/config.kdl

theme "tokyo-night"

// Define themes inline
themes {
    tokyo-night {
        fg          "#a9b1d6"
        bg          "#1a1b26"
        black       "#414868"
        red         "#f7768e"
        green       "#9ece6a"
        yellow      "#e0af68"
        blue        "#7aa2f7"
        magenta     "#bb9af7"
        cyan        "#7dcfff"
        white       "#c0caf5"
        orange      "#ff9e64"
    }
}
```

### Built-in Theme Names

Zellij ships several built-in themes:
`default`, `gruvbox`, `gruvbox-dark`, `gruvbox-light`, `nord`, `solarized-dark`,
`solarized-light`, `catppuccin-mocha`, `catppuccin-latte`, `one-dark`, `one-light`

```kdl
// Use a built-in:
theme "catppuccin-mocha"
```

### Cyberpunk Neon Theme

```kdl
themes {
    cyberpunk-neon {
        fg      "#e5e5e5"
        bg      "#0a0a0f"
        black   "#1a1a2e"
        red     "#ff003c"
        green   "#00ff41"
        yellow  "#ffe100"
        blue    "#00b4ff"
        magenta "#ff00ff"
        cyan    "#00ffff"
        white   "#e5e5e5"
        orange  "#ff6b00"
    }
}
```

---

## 140.7 Zellij Layout Files

Zellij layouts define the initial pane/tab structure in KDL format:

```kdl
// ~/.config/zellij/layouts/dev.kdl

layout {
    default_tab_template {
        pane size=1 borderless=true {
            plugin location="zellij:tab-bar"
        }
        children
        pane size=2 borderless=true {
            plugin location="zellij:status-bar"
        }
    }

    tab name="editor" focus=true {
        pane split_direction="vertical" {
            pane size="70%" command="nvim"
            pane split_direction="horizontal" {
                pane size="60%"
                pane
            }
        }
    }

    tab name="git" {
        pane command="lazygit"
    }

    tab name="shell" {
    }
}
```

Launch with a layout:
```bash
zellij --layout ~/.config/zellij/layouts/dev.kdl
```

---

## 140.8 Zellij UI Options

```kdl
// ~/.config/zellij/config.kdl

// Disable default bindings prefix hint bar
simplified_ui true

// Pane border style
pane_frames false          // hide pane borders entirely

// Mouse support
mouse_mode true

// Copy on select
copy_on_select true

// Default shell
default_shell "zsh"

// On-force-close behavior: exit | detach
on_force_close "detach"
```

---

## 140.9 Matching Multiplexer to Terminal Colorscheme

The key to a cohesive rice is using identical hex values in your terminal, multiplexer,
and compositor themes:

```bash
# Generate a color audit: show all color values from your active themes
echo "Terminal BG: check terminal config"
grep -r "background" ~/.config/kitty/kitty.conf
grep -r "fg\|bg" ~/.config/zellij/config.kdl | head -10
grep "status-style" ~/.config/tmux/tmux.conf

# Recommended: keep a single palette file and source from it
# ~/.config/palette.sh:
# export COL_BG="#1a1b26"
# export COL_FG="#a9b1d6"
# export COL_ACCENT="#7aa2f7"
# Then template tmux.conf and zellij config.kdl from it via envsubst or a generator script
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
