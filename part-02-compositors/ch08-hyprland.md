# Chapter 8 — Hyprland: Dynamic Tiling with Animation DNA

## Overview

Hyprland is the dominant ricing compositor of 2024–2026. Written from scratch in C++ on top of
wlroots/Aquamarine, it prioritizes animations, customization depth, and visual polish at the cost
of some stability. It has its own plugin ecosystem, IPC protocol, and an enormous dotfiles
community. Where Sway aims for i3 parity and correctness, Hyprland aims for spectacle — and
delivers it.

This chapter covers installation, the hyprlang configuration language, layout algorithms, window
rules, keybindings, animations, IPC scripting, and the broader Hyprland ecosystem of utilities.
By the end you will have a fully functional, visually polished desktop configuration. See Ch 3
for a compositor comparison table, Ch 07 for Sway as an alternative, and Ch 53 for session
startup automation.

---

## 8.1 History and Philosophy

Hyprland was written by vaxerski (known online as "vaxry") starting around 2022 as a personal
project to achieve smooth animations and deep customizability that neither Sway nor other wlroots
compositors provided. It is not a fork of anything — the entire rendering stack, input handling,
and configuration parser were written fresh. This architectural independence is both its strength
(no upstream constraints) and its occasional weakness (less battle-tested code paths).

In 2023–2024 the project replaced its wlroots backend dependency with **Aquamarine**, a custom
backend library that abstracts DRM/KMS, libinput, and other seat management concerns. This gave
the team full control over rendering paths and enabled features like explicit sync for NVIDIA
without waiting for wlroots upstream. The `hyprland.conf` parser was also extracted into the
standalone `hyprlang` library, enabling third-party tools to parse configs reliably.

The community crystallized around a distinctive aesthetic: rounded corners, frosted-glass blur,
per-workspace wallpapers, smooth workspace slide animations, and highly colorful color schemes
(Catppuccin Mocha being the canonical example). The subreddit r/hyprland became the primary
showcase venue. In 2025 vaxry introduced a subscription tier ("vaxry's Patreon fast-track") that
caused some community friction, though the project itself remains MIT-licensed and the code is
fully open.

By the 2025/2026 release series (v0.44+) the notorious crash-on-game-launch and NVIDIA-specific
rendering glitches had largely been resolved. Production-readiness for daily driving improved
substantially, though it still lags behind Sway for pure stability requirements.

| Attribute | Hyprland | Sway |
|---|---|---|
| Language | C++ | C |
| Backend | Aquamarine (custom) | wlroots |
| Config format | hyprlang | i3-compatible |
| Animation system | Built-in, rich | Minimal |
| Plugin support | hyprpm | None (patches) |
| NVIDIA support | Explicit sync (v0.41+) | Passable |
| Stability | Good (improving) | Excellent |

---

## 8.2 Installation

### Arch Linux

The fastest path on Arch is the AUR. `hyprland` is in the official `extra` repository as of
2024. Install with pacman directly for a stable release, or use the `hyprland-git` AUR package
for HEAD:

```bash
# Stable (official repos)
sudo pacman -S hyprland xdg-desktop-portal-hyprland

# Or git version via AUR
yay -S hyprland-git xdg-desktop-portal-hyprland-git
```

You also need a set of supporting packages for a usable desktop:

```bash
sudo pacman -S \
  hyprpaper hyprlock hypridle hyprshot \
  waybar wofi dunst \
  kitty \
  pipewire wireplumber \
  polkit-gnome \
  qt5-wayland qt6-wayland \
  nwg-look  # GTK theme configurator
```

### NixOS

Hyprland ships an official NixOS module. Add it to your `flake.nix`:

```nix
# flake.nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    hyprland.url = "github:hyprwm/Hyprland";
  };

  outputs = { nixpkgs, hyprland, ... }: {
    nixosConfigurations.mymachine = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        hyprland.nixosModules.default
        {
          programs.hyprland = {
            enable = true;
            xwayland.enable = true;
          };
        }
      ];
    };
  };
}
```

For home-manager integration (config managed declaratively), see Section 8.11.

### Fedora / Ubuntu

Fedora ships Hyprland in Copr; Ubuntu has a community PPA maintained by `solopasha`:

```bash
# Fedora
sudo dnf copr enable solopasha/hyprland
sudo dnf install hyprland

# Ubuntu 24.04+
sudo add-apt-repository ppa:hyprwm/hyprland
sudo apt update && sudo apt install hyprland
```

### Building from Source

```bash
# Install build deps (Arch)
sudo pacman -S cmake meson ninja clang \
  wayland wayland-protocols libdrm mesa \
  libxkbcommon pixman libinput \
  xcb-util-wm xcb-util-renderutil \
  glm libliftoff pango cairo

git clone --recursive https://github.com/hyprwm/Hyprland
cd Hyprland
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)
sudo cmake --install build
```

### NVIDIA Considerations

NVIDIA GPUs require specific setup to avoid flickering and XWayland corruption:

```bash
# /etc/modprobe.d/nvidia.conf
options nvidia-drm modeset=1 fbdev=1

# Rebuild initramfs
sudo mkinitcpio -P   # Arch
sudo dracut --force  # Fedora/others
```

Add to your Hyprland session environment (e.g., `~/.config/hypr/env.conf`):

```ini
env = LIBVA_DRIVER_NAME,nvidia
env = XDG_SESSION_TYPE,wayland
env = GBM_BACKEND,nvidia-drm
env = __GLX_VENDOR_LIBRARY_NAME,nvidia
env = NVD_BACKEND,direct   # For hardware video decode
env = ELECTRON_OZONE_PLATFORM_HINT,auto
```

Explicit sync (required for glitch-free rendering on 555+ drivers) is enabled automatically in
Hyprland v0.41+. Verify with `hyprctl monitors` — you should see no tearing on cursor movement.

### First Launch Checklist

```
1. Log into a TTY (Ctrl+Alt+F2), not a display manager session
2. Run: Hyprland
3. A default config is auto-created at ~/.config/hypr/hyprland.conf
4. Super+Q opens kitty (default terminal) if installed
5. Super+M exits Hyprland
6. Check ~/.local/share/hyprland/hyprland.log for errors
```

---

## 8.3 The hyprlang Configuration Language

Hyprland's configuration lives in `~/.config/hypr/hyprland.conf`. The language is `hyprlang`,
a purpose-built format that resembles a mix of ini and custom DSL. It supports `source =` for
file includes, enabling modular configs. Whitespace and comment handling is lenient — `#` begins
a line comment.

```ini
# ~/.config/hypr/hyprland.conf — top-level includes example
source = ~/.config/hypr/monitors.conf
source = ~/.config/hypr/env.conf
source = ~/.config/hypr/keybinds.conf
source = ~/.config/hypr/windowrules.conf
source = ~/.config/hypr/animations.conf
```

### Monitor Directives

```ini
# monitor = name, resolution@refreshrate, position, scale
monitor = DP-1, 2560x1440@165, 0x0, 1
monitor = HDMI-A-1, 1920x1080@60, 2560x0, 1
monitor = eDP-1, preferred, auto, 1.5   # laptop panel, auto-detect res

# Disable a monitor
monitor = DP-2, disable

# Mirror DP-1 onto HDMI-A-2
monitor = HDMI-A-2, 1920x1080@60, 0x0, 1, mirror, DP-1
```

Use `hyprctl monitors` to list detected connector names.

### `general` Block

```ini
general {
    gaps_in = 5           # gaps between windows
    gaps_out = 10         # gaps to monitor edge
    border_size = 2
    col.active_border = rgba(cba6f7ff) rgba(89b4faff) 45deg  # gradient
    col.inactive_border = rgba(595959aa)
    layout = dwindle      # or master
    resize_on_border = true
    hover_icon_on_border = true
}
```

### `decoration` Block

```ini
decoration {
    rounding = 12         # corner radius in pixels

    blur {
        enabled = true
        size = 8
        passes = 2
        new_optimizations = true
        xray = false
        ignore_opacity = false
    }

    drop_shadow = true
    shadow_range = 20
    shadow_render_power = 3
    col.shadow = rgba(1a1a1aee)

    active_opacity = 1.0
    inactive_opacity = 0.92
    fullscreen_opacity = 1.0
}
```

### `animations` Block

```ini
animations {
    enabled = true

    bezier = myBezier, 0.05, 0.9, 0.1, 1.05
    bezier = linear, 0.0, 0.0, 1.0, 1.0
    bezier = easeOut, 0.0, 0.0, 0.2, 1.0

    animation = windows, 1, 7, myBezier
    animation = windowsOut, 1, 7, default, popin 80%
    animation = border, 1, 10, default
    animation = borderangle, 1, 8, default
    animation = fade, 1, 7, default
    animation = workspaces, 1, 6, default
    animation = specialWorkspace, 1, 6, default, slidevert
}
```

### `input` Block

```ini
input {
    kb_layout = us
    kb_variant =
    kb_options = caps:escape   # Caps Lock → Escape

    follow_mouse = 1
    sensitivity = 0            # -1.0 to 1.0, 0 = no modification
    accel_profile = flat       # flat, adaptive, custom

    touchpad {
        natural_scroll = true
        disable_while_typing = true
        tap-to-click = true
        drag_lock = false
        scroll_factor = 0.8
    }
}
```

### `misc` Block

```ini
misc {
    force_default_wallpaper = 0   # disable Hyprland anime girl wallpapers
    disable_hyprland_logo = true
    disable_splash_rendering = true
    vfr = true                    # variable frame rate — saves power
    vrr = 0                       # adaptive sync: 0=off, 1=on, 2=fullscreen
    focus_on_activate = false
    mouse_move_enables_dpms = true
    key_press_enables_dpms = true
}
```

---

## 8.4 Layout Algorithms

Hyprland ships two built-in tiling layouts and supports additional ones via plugins.

### Dwindle Layout

Dwindle uses a recursive binary-split strategy: each new window splits the currently focused
tile in half, alternating horizontal and vertical splits to maintain a golden-ratio-like
proportion. This produces a natural tiling for programming workflows where new terminals are
opened frequently.

```ini
dwindle {
    pseudotile = true           # windows keep floating size while tiled
    preserve_split = true       # remember split direction per node
    smart_split = false         # use focus history to decide split direction
    smart_resizing = true       # resize from opposite side for balance
    force_split = 0             # 0=right/bottom, 1=right, 2=bottom
    use_active_for_splits = true
    default_split_ratio = 1.0   # golden ratio: try 1.618
}
```

Useful dispatchers for dwindle:

```ini
bind = SUPER, P, pseudo,          # toggle pseudotile
bind = SUPER, J, togglesplit,     # flip split direction
```

### Master Layout

Master/stack places one "master" window on the left (or top) taking `mfact` fraction of the
screen, and all other windows share the remaining area in a vertical stack:

```ini
master {
    new_is_master = false     # new windows go to stack, not master
    new_on_top = false        # stack order: false = append to bottom
    mfact = 0.55              # master area fraction (0.0–1.0)
    orientation = left        # left, right, top, bottom
    inherit_fullscreen = true
    always_center_master = false
    smart_resizing = true
}
```

Switch layouts at runtime:

```bash
hyprctl keyword general:layout master
hyprctl keyword general:layout dwindle
```

Or bind it:

```ini
bind = SUPER SHIFT, space, exec, hyprctl keyword general:layout \
    $(hyprctl -j getoption general:layout | jq -r '.str | if . == "dwindle" then "master" else "dwindle" end')
```

### hyprscroller Plugin

hyprscroller provides a PaperWM-inspired scrollable layout where workspaces extend horizontally
beyond the monitor edge. Install via `hyprpm`:

```bash
hyprpm add https://github.com/dawsers/hyprscroller
hyprpm enable hyprscroller
```

Then set the layout:

```ini
plugin {
    scroller {
        column_default_width = onehalf   # onefourth, onethird, onehalf, twothirds, one
        focus_wrap = false
    }
}
general {
    layout = scroller
}
```

---

## 8.5 Window Rules and Layer Rules

Window rules let you apply automatic behaviors to windows matching specific criteria. Hyprland
uses `windowrulev2` (the v2 API) which accepts a comma-separated predicate list. Rules are
evaluated in order; last match wins for most properties.

### windowrulev2 Syntax

```
windowrulev2 = action, predicate1, predicate2, ...
```

Common predicates:

| Predicate | Example | Matches |
|---|---|---|
| `class:regex` | `class:^(firefox)$` | window class (app_id) |
| `title:regex` | `title:^(.*Spotify.*)$` | window title |
| `workspace:N` | `workspace:2` | on workspace 2 |
| `floating:0/1` | `floating:1` | floating state |
| `fullscreen:0/1` | `fullscreen:0` | fullscreen state |
| `monitor:name` | `monitor:DP-1` | on monitor |
| `xwayland:0/1` | `xwayland:1` | XWayland window |

Common actions:

```ini
# Float specific apps
windowrulev2 = float, class:^(pavucontrol)$
windowrulev2 = float, class:^(nm-connection-editor)$
windowrulev2 = float, title:^(Picture-in-Picture)$

# Size floating windows
windowrulev2 = size 800 600, class:^(pavucontrol)$
windowrulev2 = center, class:^(pavucontrol)$

# Send to specific workspaces (silent = don't switch to it)
windowrulev2 = workspace 2 silent, class:^(firefox)$
windowrulev2 = workspace 3 silent, class:^(discord)$
windowrulev2 = workspace 5 silent, class:^(Spotify)$

# Opacity
windowrulev2 = opacity 0.90 0.80, class:^(kitty)$  # active inactive

# No blur for specific windows (perf)
windowrulev2 = noblur, class:^(firefox)$

# Force tiling for apps that default to floating
windowrulev2 = tile, class:^(Spotify)$

# Ignore maximize requests
windowrulev2 = suppressevent maximize, class:.*

# Pinned PiP window (floats on all workspaces)
windowrulev2 = pin, title:^(Picture-in-Picture)$

# XWayland scaling fix
windowrulev2 = xwayland:force-scaled, class:^(steam)$
```

### layerrule

Layer rules apply to layer-shell surfaces (bars, notification daemons, lock screens). The primary
use case is animating them:

```ini
# Animate waybar slide-in from top
layerrule = animation slide top, class:waybar

# Animate dunst notifications sliding from right
layerrule = animation slide right, namespace:notifications

# Allow blur on waybar background
layerrule = blur, class:waybar
layerrule = ignorezero, class:waybar  # don't blur fully transparent areas
```

---

## 8.6 Keybindings and Dispatchers

Hyprland's bind directives are among its most expressive features. There are five bind variants:

| Directive | Behavior |
|---|---|
| `bind` | Standard: fires once on key down |
| `binde` | Repeat: fires repeatedly while held |
| `bindm` | Mouse: binds to mouse button + mod |
| `bindr` | Release: fires on key up |
| `bindn` | No-lock: fires even when input is locked |
| `bindl` | Lock: fires even on locked screen |

### Complete Keybinding Configuration

```ini
# ~/.config/hypr/keybinds.conf
$mod = SUPER
$term = kitty
$browser = firefox
$filemanager = thunar
$launcher = wofi --show drun

# Applications
bind = $mod, Return, exec, $term
bind = $mod, B, exec, $browser
bind = $mod, E, exec, $filemanager
bind = $mod, space, exec, $launcher
bind = $mod, V, exec, cliphist list | wofi --dmenu | cliphist decode | wl-copy

# Window management
bind = $mod, Q, killactive,
bind = $mod SHIFT, Q, exit,
bind = $mod, F, fullscreen,
bind = $mod SHIFT, F, fakefullscreen,
bind = $mod, T, togglefloating,
bind = $mod, P, pseudo,
bind = $mod, J, togglesplit,
bind = $mod, S, togglespecialworkspace, magic

# Focus movement (vim-style)
bind = $mod, H, movefocus, l
bind = $mod, L, movefocus, r
bind = $mod, K, movefocus, u
bind = $mod, J, movefocus, d

# Window movement
bind = $mod SHIFT, H, movewindow, l
bind = $mod SHIFT, L, movewindow, r
bind = $mod SHIFT, K, movewindow, u
bind = $mod SHIFT, J, movewindow, d

# Resize (binde = repeat while held)
binde = $mod ALT, H, resizeactive, -30 0
binde = $mod ALT, L, resizeactive, 30 0
binde = $mod ALT, K, resizeactive, 0 -30
binde = $mod ALT, J, resizeactive, 0 30

# Mouse window management
bindm = $mod, mouse:272, movewindow
bindm = $mod, mouse:273, resizewindow

# Workspaces
bind = $mod, 1, workspace, 1
bind = $mod, 2, workspace, 2
bind = $mod, 3, workspace, 3
bind = $mod, 4, workspace, 4
bind = $mod, 5, workspace, 5
bind = $mod SHIFT, 1, movetoworkspace, 1
bind = $mod SHIFT, 2, movetoworkspace, 2
bind = $mod SHIFT, 3, movetoworkspace, 3

# Scroll through workspaces
bind = $mod, mouse_down, workspace, e+1
bind = $mod, mouse_up, workspace, e-1

# Media / brightness
bindl = , XF86AudioMute, exec, wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle
binde = , XF86AudioLowerVolume, exec, wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-
binde = , XF86AudioRaiseVolume, exec, wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+
bind = , XF86AudioPlay, exec, playerctl play-pause
bind = , XF86AudioNext, exec, playerctl next
bind = , XF86AudioPrev, exec, playerctl previous
binde = , XF86MonBrightnessUp, exec, brightnessctl set 5%+
binde = , XF86MonBrightnessDown, exec, brightnessctl set 5%-

# Screenshots
bind = , Print, exec, hyprshot -m output
bind = SHIFT, Print, exec, hyprshot -m region
bind = $mod, Print, exec, hyprshot -m window
```

### Submaps (Modal Keybinding Layers)

Submaps let you create Emacs/Vim-style modal modes. The pattern is: bind to enter the submap,
bind `escape` to exit it, then define binds active only within it:

```ini
# Enter resize mode with SUPER+R
bind = $mod, R, submap, resize

submap = resize
binde = , H, resizeactive, -20 0
binde = , L, resizeactive, 20 0
binde = , K, resizeactive, 0 -20
binde = , J, resizeactive, 0 20
bind = , escape, submap, reset
bind = , Return, submap, reset
submap = reset
```

---

## 8.7 Animations

Hyprland's animation system is one of its defining features. Every animation is defined by a
bezier curve plus a duration and a style. Understanding the bezier control points lets you tune
the exact feel of every transition.

### Bezier Curve Definitions

A bezier curve in Hyprland is defined by its two middle control points (P1 and P2, the
endpoints are implicitly (0,0) and (1,1)):

```ini
# bezier = name, x1, y1, x2, y2
bezier = myBezier,   0.05, 0.9,  0.1, 1.05    # slight overshoot (bouncy)
bezier = easeOut,    0.0,  0.0,  0.2, 1.0     # fast then slow
bezier = easeIn,     0.4,  0.0,  1.0, 1.0     # slow then fast
bezier = easeInOut,  0.42, 0.0,  0.58, 1.0    # slow-fast-slow
bezier = linear,     0.0,  0.0,  1.0, 1.0     # constant speed
bezier = snappy,     0.68,-0.55, 0.265,1.55   # aggressive overshoot
```

Use https://cubic-bezier.com to visualize curves visually before committing.

### Animation Declarations

```ini
# animation = name, onoff, speed, curve [, style]
# speed is in 10ths of a second — 7 means 700ms

animations {
    enabled = true

    bezier = myBezier, 0.05, 0.9, 0.1, 1.05
    bezier = easeOut, 0.0, 0.0, 0.2, 1.0

    # Window open/close
    animation = windows,     1, 7,  myBezier
    animation = windowsIn,   1, 7,  myBezier, slide      # slide, popin, fade
    animation = windowsOut,  1, 7,  easeOut,  popin 80%  # shrink to 80% then disappear
    animation = windowsMove, 1, 5,  myBezier

    # Layers (waybar, rofi, etc.)
    animation = layers,      1, 7,  myBezier
    animation = layersIn,    1, 7,  myBezier, slide
    animation = layersOut,   1, 7,  easeOut, fade

    # Workspace transitions
    animation = workspaces,       1, 6, myBezier           # horizontal slide
    animation = workspacesIn,     1, 6, myBezier, slidevert
    animation = workspacesOut,    1, 6, myBezier, slidevert
    animation = specialWorkspace, 1, 6, myBezier, slidevert

    # Borders
    animation = border,      1, 10, default
    animation = borderangle, 1, 8,  linear     # rotating gradient border
    animation = fade,        1, 7,  default
}
```

### Performance Tuning

Animations have GPU cost. On lower-end hardware, reduce `passes` in blur, disable shadows, and
shorten animation speeds:

```ini
decoration {
    blur { passes = 1; size = 4 }
    drop_shadow = false
}
misc {
    vfr = true   # skip rendering unchanged frames — biggest win
}
# Reduce animation durations
animation = windows, 1, 3, myBezier
animation = workspaces, 1, 3, myBezier
```

Verify GPU load with `nvidia-smi dmon` (NVIDIA) or `intel_gpu_top` (Intel).

---

## 8.8 Hyprland IPC

Hyprland exposes a Unix domain socket IPC. Two sockets exist per running instance:

- **Command socket**: `$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket.sock`
- **Event socket**: `$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock`

The `hyprctl` binary wraps the command socket. The event socket streams newline-delimited events
that can be consumed by any language.

### hyprctl Reference

```bash
# Query active workspace
hyprctl activeworkspace

# List all windows as JSON
hyprctl -j clients | jq '.[] | {class, title, workspace}'

# List monitors
hyprctl monitors

# Dispatch a command
hyprctl dispatch workspace 3
hyprctl dispatch exec "kitty --title floatterm"
hyprctl dispatch movewindow l

# Change a config option at runtime (survives until reload)
hyprctl keyword general:gaps_in 10
hyprctl keyword decoration:rounding 0

# Reload config
hyprctl reload

# Get plugin list
hyprctl plugin list

# Send arbitrary keyword
hyprctl keyword animations:enabled false
```

### Event Socket Scripting

The event socket emits one event per line in the format `eventname>>data`. Subscribe like so:

```bash
# Print all events
socat -u UNIX-CONNECT:"$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock" -

# React to workspace changes
socat -u UNIX-CONNECT:"$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock" - \
  | while IFS= read -r event; do
      case "$event" in
        workspace*) notify-send "Switched to workspace ${event#*>>}" ;;
        activewindow*) echo "Active window: ${event#*>>}" ;;
      esac
    done
```

### Python Integration with pyprland

`pyprland` is a plugin daemon that wraps Hyprland IPC and provides scratchpads, monitors
management helpers, and more:

```bash
pip install pyprland   # or use uv: uv tool install pyprland
```

```toml
# ~/.config/hypr/pyprland.toml
[pyprland]
plugins = ["scratchpads", "magnify"]

[scratchpads.term]
animation = "fromBottom"
command = "kitty --class scratchpad"
class = "scratchpad"
size = "75% 60%"

[scratchpads.music]
animation = "fromRight"
command = "spotify"
class = "Spotify"
size = "50% 80%"
```

```ini
# hyprland.conf — toggle scratchpads
bind = $mod, grave, exec, pypr toggle term
bind = $mod, M,     exec, pypr toggle music
```

---

## 8.9 The Plugin Ecosystem

Hyprland ships `hyprpm`, the official plugin manager introduced in v0.30. Plugins are compiled
C++ shared libraries that hook into Hyprland's internal APIs. This gives them first-class access
to everything: rendering, input, dispatchers, config.

### hyprpm Workflow

```bash
# Add a plugin repository (fetches headers, compiles)
hyprpm add https://github.com/hyprwm/hyprland-plugins
hyprpm add https://github.com/KZDKM/hyprspace

# List available plugins from added repos
hyprpm update   # fetch new commits

# Enable/disable
hyprpm enable hyprexpo
hyprpm disable hyprexpo

# List installed plugins and their status
hyprpm list
```

Auto-load plugins on startup in `hyprland.conf`:

```ini
plugin = /home/user/.local/share/hyprpm/installedPlugins/hyprexpo/hyprexpo.so
```

Or use `hyprpm` in your startup script:

```bash
# ~/.config/hypr/scripts/start.sh
hyprpm reload -n  # reload all enabled plugins silently
```

### Notable Plugins

| Plugin | Description | Repo |
|---|---|---|
| `hyprexpo` | Expo/overview mode (all workspaces tiled) | hyprwm/hyprland-plugins |
| `hyprspace` | Workspace overview (Apple Mission Control style) | KZDKM/hyprspace |
| `hy3` | i3-style manual tiling layout | outfoxxed/hy3 |
| `hyprscroller` | PaperWM horizontal scrollable layout | dawsers/hyprscroller |
| `hyprfocus` | Focus-based window dimming | VortexCoyote/hyprfocus |
| `hycov` | Grid-based window switcher | DreamMaoMao/hycov |

### hyprexpo Configuration

```ini
plugin {
    hyprexpo {
        columns = 3
        gap_size = 5
        bg_col = rgb(111111)
        workspace_method = center current  # or "first 1"
        enable_gesture = true
        gesture_fingers = 3
        gesture_distance = 300
        gesture_positive = true
    }
}
bind = $mod, tab, hyprexpo:expo, toggle
```

---

## 8.10 Hyprland Utilities

The official Hyprland ecosystem includes purpose-built Wayland-native utilities that integrate
tightly with Hyprland IPC. Using these instead of generic alternatives avoids compatibility
friction and ensures visual consistency.

### hyprpaper

hyprpaper is a wallpaper daemon with IPC control. It preloads images to avoid a blank flash at
startup. It supports per-monitor wallpapers and runtime switching.

```ini
# ~/.config/hypr/hyprpaper.conf
preload = ~/Pictures/walls/catppuccin-mocha.png
preload = ~/Pictures/walls/nordic-peaks.png

wallpaper = DP-1,~/Pictures/walls/catppuccin-mocha.png
wallpaper = HDMI-A-1,~/Pictures/walls/nordic-peaks.png

ipc = on   # enable IPC socket
splash = false
```

```bash
# Launch in hyprland.conf
exec-once = hyprpaper

# Switch wallpaper at runtime
hyprctl hyprpaper wallpaper "DP-1,~/Pictures/walls/new.png"

# Per-workspace wallpaper script using event socket
socat ... | while read ev; do
  [[ "$ev" == workspace* ]] && ws="${ev#*>>}"
  hyprctl hyprpaper wallpaper "DP-1,~/Pictures/walls/ws${ws}.png"
done
```

### hyprlock

hyprlock is a GPU-accelerated lockscreen with a shader-based blur of the screen capture. Its
configuration uses the same hyprlang format:

```ini
# ~/.config/hypr/hyprlock.conf
background {
    monitor =
    path = screenshot                # live screenshot, then blur
    blur_passes = 3
    blur_size = 7
    brightness = 0.5
}

input-field {
    monitor =
    size = 300 60
    outline_thickness = 3
    col.outer = rgb(cba6f7)
    col.inner = rgb(1e1e2e)
    col.fail = rgb(f38ba8)
    font_color = rgb(cdd6f4)
    inner_color = rgb(1e1e2e)
    font_family = JetBrains Mono Nerd Font
    placeholder_text = <i>Password...</i>
    position = 0, -80
    halign = center
    valign = center
}

label {
    monitor =
    text = cmd[update:1000] date '+%H:%M'
    color = rgba(cdd6f4ff)
    font_size = 90
    font_family = JetBrains Mono Nerd Font
    position = 0, 300
    halign = center
    valign = center
}
```

### hypridle

hypridle handles DPMS screen blanking and runs arbitrary commands at configurable timeouts. It
integrates with hyprlock via the `loginctl lock-session` trigger:

```ini
# ~/.config/hypr/hypridle.conf
general {
    lock_cmd = pidof hyprlock || hyprlock   # don't spawn multiple lockers
    before_sleep_cmd = loginctl lock-session
    after_sleep_cmd = hyprctl dispatch dpms on
}

listener {
    timeout = 150     # 2.5 min: dim screen
    on-timeout = brightnessctl -s set 10
    on-resume = brightnessctl -r
}

listener {
    timeout = 300     # 5 min: lock screen
    on-timeout = loginctl lock-session
}

listener {
    timeout = 380     # ~6 min: DPMS off
    on-timeout = hyprctl dispatch dpms off
    on-resume = hyprctl dispatch dpms on
}

listener {
    timeout = 1800    # 30 min: suspend
    on-timeout = systemctl suspend
}
```

Start both in `hyprland.conf`:

```ini
exec-once = hypridle
exec-once = hyprlock  # lock immediately on session start (optional)
```

### hyprshot

hyprshot wraps `grim` + `slurp` for screenshots with automatic hyprland-aware window targeting:

```bash
hyprshot -m output               # screenshot focused monitor
hyprshot -m output --clipboard   # to clipboard instead of file
hyprshot -m region               # interactive selection
hyprshot -m window               # focused window
hyprshot -m window --class firefox  # specific app window
```

Default save location: `~/Pictures/Screenshots/`. Override:

```bash
hyprshot -m region -o ~/Desktop
```

### hyprsunset

hyprsunset applies a color temperature filter (blue light reduction) for evening use. It does
not require a running compositor-specific backend:

```bash
hyprsunset -t 4000   # 4000K warm color temperature
hyprsunset -t 6500   # 6500K neutral (daytime)

# Automatically at sunset using a cron or timer:
exec-once = hyprsunset -t 4500
```

---

## 8.11 Configuration Gallery

### Minimal + Fast Config

Suitable for low-powered hardware or preference for speed over eye candy:

```ini
# ~/.config/hypr/hyprland.conf — MINIMAL
monitor = ,preferred,auto,1

input {
    kb_layout = us
    sensitivity = 0
    follow_mouse = 1
}

general {
    gaps_in = 4
    gaps_out = 8
    border_size = 2
    col.active_border = rgba(33ccffee)
    col.inactive_border = rgba(595959aa)
    layout = dwindle
}

decoration {
    rounding = 6
    blur { enabled = false }
    drop_shadow = false
}

animations { enabled = false }

misc {
    vfr = true
    disable_hyprland_logo = true
    force_default_wallpaper = 0
}

dwindle {
    pseudotile = true
    preserve_split = true
}

$mod = SUPER
bind = $mod, Return, exec, kitty
bind = $mod, Q, killactive,
bind = $mod, M, exit,
bind = $mod, F, fullscreen,
bind = $mod, T, togglefloating,
bind = $mod, 1, workspace, 1
bind = $mod, 2, workspace, 2
bind = $mod, 3, workspace, 3
bind = $mod SHIFT, 1, movetoworkspace, 1
bind = $mod SHIFT, 2, movetoworkspace, 2
bind = $mod SHIFT, 3, movetoworkspace, 3
```

### Heavy Eye-Candy Config (Catppuccin Mocha)

```ini
# ~/.config/hypr/hyprland.conf — EYE CANDY (excerpt)
general {
    gaps_in = 6
    gaps_out = 12
    border_size = 3
    col.active_border = rgba(cba6f7ff) rgba(89b4faff) rgba(a6e3a1ff) 60deg
    col.inactive_border = rgba(45475aaa)
    layout = dwindle
}

decoration {
    rounding = 14
    active_opacity = 1.0
    inactive_opacity = 0.88

    blur {
        enabled = true
        size = 10
        passes = 3
        new_optimizations = true
        xray = true
        noise = 0.02
        contrast = 0.9
        brightness = 0.8
    }

    drop_shadow = true
    shadow_range = 24
    shadow_render_power = 4
    col.shadow = rgba(1a1a2eee)
}

animations {
    enabled = true
    bezier = smooth, 0.05, 0.9, 0.1, 1.05
    bezier = overshoot, 0.68, -0.55, 0.265, 1.55
    bezier = easeOut, 0.0, 0.0, 0.2, 1.0

    animation = windows, 1, 8, smooth
    animation = windowsIn, 1, 8, overshoot, slide
    animation = windowsOut, 1, 7, easeOut, popin 80%
    animation = border, 1, 12, default
    animation = borderangle, 1, 8, linear
    animation = fade, 1, 7, default
    animation = workspaces, 1, 7, smooth, slide
    animation = specialWorkspace, 1, 7, smooth, slidevert
}
```

### NixOS home-manager Module

```nix
# home.nix (using home-manager with Hyprland flake input)
{ config, pkgs, hyprland, ... }:
{
  wayland.windowManager.hyprland = {
    enable = true;
    package = hyprland.packages.${pkgs.system}.hyprland;
    xwayland.enable = true;

    settings = {
      monitor = [ "DP-1,2560x1440@165,0x0,1" "eDP-1,preferred,auto,1.5" ];

      general = {
        gaps_in = 5;
        gaps_out = 10;
        border_size = 2;
        "col.active_border" = "rgba(cba6f7ff) rgba(89b4faff) 45deg";
        layout = "dwindle";
      };

      decoration = {
        rounding = 12;
        blur = {
          enabled = true;
          size = 8;
          passes = 2;
        };
      };

      exec-once = [
        "hyprpaper"
        "hypridle"
        "waybar"
        "${pkgs.polkit_gnome}/libexec/polkit-gnome-authentication-agent-1"
      ];

      "$mod" = "SUPER";
      bind = [
        "$mod, Return, exec, kitty"
        "$mod, Q, killactive,"
        "$mod, M, exit,"
      ];
    };
  };
}
```

---

## 8.12 Troubleshooting

### Black Screen on Launch

1. Check `~/.local/share/hyprland/hyprland.log` for error messages.
2. Verify `XDG_RUNTIME_DIR` is set and writable (should be `/run/user/1000`).
3. NVIDIA: confirm `nvidia-drm.modeset=1` is active: `cat /sys/module/nvidia_drm/parameters/modeset`.
4. Try launching from a TTY, not from inside another Wayland session.

```bash
# Check current modeset value
cat /sys/module/nvidia_drm/parameters/modeset
# Should print: Y

# Verify session type
echo $XDG_SESSION_TYPE
```

### Screen Tearing / Flickering (NVIDIA)

```ini
# Add to env.conf
env = GBM_BACKEND,nvidia-drm
env = __GLX_VENDOR_LIBRARY_NAME,nvidia
env = __GL_GSYNC_ALLOWED,1
env = __GL_VRR_ALLOWED,1
```

Also ensure you are on the latest proprietary driver (555+ recommended for explicit sync support).
Check with `nvidia-smi | grep Driver`.

### Apps Look Blurry on HiDPI

```ini
# For GTK apps
env = GDK_SCALE,1
env = GDK_DPI_SCALE,1

# For Qt apps
env = QT_AUTO_SCREEN_SCALE_FACTOR,1
env = QT_SCALE_FACTOR,1

# For XWayland apps — use xrandr to set DPI
exec-once = xrandr --dpi 192
```

For per-app XWayland scaling with the `xwayland:force-scaled` windowrule:

```ini
windowrulev2 = xwayland:force-scaled, class:^(.*jetbrains.*)$
```

### Waybar / Status Bar Not Showing

```bash
# Test waybar directly
waybar &
# Check output for GTK errors

# Ensure xdg-desktop-portal-hyprland is running
systemctl --user status xdg-desktop-portal-hyprland

# Restart it
systemctl --user restart xdg-desktop-portal-hyprland
```

### Hyprpm Plugin Fails to Compile

```bash
# Update plugin headers
hyprpm update

# Check hyprland version matches plugin's required version
hyprctl version | grep Tag
# Compare with plugin's README COMPATIBLE section

# Force recompile
hyprpm remove <plugin>
hyprpm add <repo-url>
hyprpm enable <plugin>
```

### Input Lag / High Latency Feel

```ini
misc {
    vfr = true          # most important setting for latency feel
    no_direct_scanout = false   # allow direct scanout when possible
}
# Disable blur if on integrated graphics
decoration {
    blur { enabled = false }
}
```

For gaming, switch to the `game` window rule preset:

```ini
windowrulev2 = immediate, class:^(steam_app_.*)$
windowrulev2 = noblur, class:^(steam_app_.*)$
windowrulev2 = noshadow, class:^(steam_app_.*)$
```

### Config Reload Errors

```bash
# Reload and see errors
hyprctl reload
hyprctl -j getoption general:border_size  # check a specific option parsed correctly

# Validate syntax without reloading
hyprctl --instance 0 dispatch exec true  # smoke test IPC is alive
```

---

## See Also

- **Ch 3** — Compositor comparison: Hyprland vs Sway vs river vs niri
- **Ch 07** — Sway: i3-compatible Wayland tiling
- **Ch 21** — Waybar: building a Hyprland status bar
- **Ch 27** — Themes and GTK/Qt styling on Wayland
- **Ch 34** — Notification daemons: dunst, mako, swaync
- **Ch 44** — Clipboard management: cliphist + wl-copy
- **Ch 53** — Session startup: PAM, environment variables, autostart

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
