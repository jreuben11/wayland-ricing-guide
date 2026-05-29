# Chapter 11 — Niri: The Scrollable Workspace Pioneer

## Overview

Niri is a Wayland compositor built on Smithay (not wlroots) that implements a
scrollable, infinite-column window layout — a paradigm borrowed from the
PaperWM GNOME extension and transplanted into a standalone Wayland compositor.
It is written entirely in Rust, and its design decisions are deliberate and
principled: no floating mode, no tiling in the traditional i3-sense, just an
endless horizontal canvas divided into columns. Each column holds one or more
windows stacked vertically; the viewport scrolls left and right to bring
columns into view.

As of mid-2025, Niri is in active development with a stable enough configuration
API for daily driving on x86\_64 desktops and laptops. Its Rust + Smithay
heritage means it benefits from memory safety and an independent implementation
of the Wayland protocol stack, decoupled from the wlroots release cycle. This
chapter covers installation, full configuration, layout mechanics, animations,
IPC, and integration with the broader Wayland ecosystem.

The audience for Niri leans toward power users who already understand tiling
window managers, spend significant time in terminals and editors, and want a
spatial metaphor that aligns well with how humans think about related tasks: as
adjacent columns of activity, not overlapping floating chaos. If you are coming
from PaperWM, Karousel, or Hyprscroller, Niri will feel immediately familiar.
If you are coming from i3 or Sway, expect to unlearn the workspace-first mental
model and embrace the scrollable canvas.

For compositor comparisons, see **Ch 08 (Hyprland)**, **Ch 07 (Sway)**, and
**Ch 10 (River)**. For session startup and display manager integration, see
**Ch 53**. For status bar configuration, see **Ch 22 (Waybar)** and
**Ch 24 (Quickshell)**.

---

## 11.1 The Scrollable Layout Concept

Traditional tiling window managers partition a fixed screen into regions. When
you open a fifth window on a 1080p monitor, every tile shrinks. The scrollable
column paradigm rejects this: the canvas is infinite horizontally, and windows
are opened as new columns (or stacked into existing ones). The monitor acts as a
viewport; navigation is spatial movement left and right, not cycling through a
list of workspaces.

This model has a decisive ergonomic advantage for wide monitors (2560px and
above): instead of a grid of tiny tiles, you see two or three full-width columns
at once, each the width of a comfortable editor or terminal. The fact that
adjacent work is always *adjacent* on screen — never hidden behind a workspace
switch — significantly reduces cognitive overhead. Your browser tab is literally
to the right of your editor.

Niri generalises this with per-output workspaces: each monitor has an
independent scrollable canvas. Workspaces in Niri are not named desktops in the
i3 sense; they are additional layers on the same output, each with its own
column sequence. You can have workspace 1 containing a coding session and
workspace 2 containing a documentation browser, and switch between them without
losing spatial context within either.

### Conceptual Comparison

| Feature                  | Niri           | PaperWM (GNOME)  | Hyprscroller     | Sway (i3-style)  |
|--------------------------|----------------|------------------|------------------|------------------|
| Scrollable canvas        | Yes            | Yes              | Yes              | No               |
| Standalone compositor    | Yes            | No (extension)   | No (Hyprland plugin) | Yes          |
| Floating layer           | No             | Yes (GNOME)      | Via Hyprland     | Yes              |
| Multi-monitor support    | Per-output WS  | Per-output WS    | Via Hyprland     | Per-output WS    |
| Wayland-native           | Yes            | Partial          | Yes              | Yes              |
| Config language          | KDL            | GSettings        | Hyprland conf    | i3-compat        |
| Animation system         | Built-in       | GNOME shell      | Hyprland         | None built-in    |

The keyboard navigation model follows spatial position: `FocusColumnLeft`,
`FocusColumnRight`, `FocusWindowDown`, `FocusWindowUp`. There is no concept of
"focus the next window in a list." If you want the window to the left of the
current focus, you press the binding for left. This predictability is a feature.

---

## 11.2 Installation

### From Source (Cargo)

Building from source requires Rust stable (≥1.76 as of 2025), and a set of
system libraries for the Wayland protocol, input handling, and DRM/KMS.

```bash
# Arch Linux / Manjaro
sudo pacman -S --needed \
  base-devel git rust cargo \
  wayland wayland-protocols \
  libxkbcommon libinput mesa \
  libseat libgbm pixman \
  pango cairo

# Fedora 40+
sudo dnf install -y \
  rust cargo \
  wayland-devel wayland-protocols-devel \
  libxkbcommon-devel libinput-devel \
  mesa-libgbm-devel libseat-devel \
  pixman-devel pango-devel cairo-devel

# Ubuntu 24.04+
sudo apt install -y \
  build-essential git cargo \
  libwayland-dev wayland-protocols \
  libxkbcommon-dev libinput-dev \
  libgbm-dev libseat-dev \
  libpixman-1-dev libpango1.0-dev libcairo2-dev

# Clone and build
git clone https://github.com/YaLTeR/niri.git
cd niri
cargo build --release
sudo install -Dm755 target/release/niri /usr/local/bin/niri
```

### Distribution Packages

```bash
# Arch AUR (most current)
yay -S niri
# or
paru -S niri

# Arch official repos (may lag behind)
sudo pacman -S niri

# Fedora (COPR)
sudo dnf copr enable yalter/niri
sudo dnf install niri

# openSUSE Tumbleweed
sudo zypper install niri

# Void Linux
sudo xbps-install niri
```

### NixOS Flake

Add niri to your flake inputs. Niri maintains an official flake with a NixOS
module and a home-manager module.

```nix
# flake.nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    niri.url = "github:YaLTeR/niri";
    niri.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { nixpkgs, niri, ... }: {
    nixosConfigurations.mymachine = nixpkgs.lib.nixosSystem {
      modules = [
        niri.nixosModules.niri
        {
          programs.niri.enable = true;
          # Use the package from the niri flake rather than nixpkgs
          programs.niri.package = niri.packages.x86_64-linux.niri;
        }
      ];
    };
  };
}
```

For home-manager integration:

```nix
# home.nix
{
  imports = [ niri.homeModules.niri ];

  programs.niri = {
    enable = true;
    settings = {
      # home-manager niri module uses structured settings
      # that are translated to KDL at build time
    };
  };
}
```

### Launching Niri

Niri supports being launched from a TTY or from a display manager. To launch
from a TTY:

```bash
# Direct launch (creates a nested session if already in a compositor)
niri

# Launch as a standalone session
niri --session
```

For display manager integration (SDDM, GDM, ly), install the desktop entry:

```bash
sudo install -Dm644 resources/niri.desktop \
  /usr/share/wayland-sessions/niri.desktop
```

See **Ch 53** for full session startup configuration including environment
variables, D-Bus activation, and systemd user session setup.

---

## 11.3 Configuration: KDL Format

Niri's configuration lives at `~/.config/niri/config.kdl`. It uses the KDL
document language — a human-readable format with nodes, typed arguments,
properties (key=value), and child blocks delimited by `{}`. Unlike TOML, KDL
does not require quotes around most strings and supports multi-level nesting
naturally.

```kdl
// This is a KDL comment
node-name argument1 argument2 key="value" {
    child-node argument
}
```

To validate and reload configuration without restarting:

```bash
# Validate config syntax
niri validate --config ~/.config/niri/config.kdl

# Reload config live (from within a running niri session)
niri msg action do-screen-transition
# or bind a key to reload:
# spawn "niri" "msg" "action" "reload-config"
```

### Complete Minimal Configuration

The following is a functional starting configuration. It covers the most
commonly needed blocks:

```kdl
// ~/.config/niri/config.kdl

// ── Input ────────────────────────────────────────────────────────────────────
input {
    keyboard {
        xkb {
            layout "us"
            variant ""
            options "ctrl:nocaps"   // CapsLock → Ctrl
        }
        repeat-delay 300
        repeat-rate 50
    }

    touchpad {
        tap
        natural-scroll
        accel-speed 0.2
        accel-profile "adaptive"
        scroll-method "two-finger"
        dwt   // disable-while-typing
    }

    mouse {
        accel-speed 0.0
        accel-profile "flat"
    }

    warp-mouse-to-focus
    focus-follows-mouse max-scroll-amount="0%"
}

// ── Outputs ──────────────────────────────────────────────────────────────────
output "DP-1" {
    mode "2560x1440@144"
    scale 1.0
    position x=0 y=0
}

output "HDMI-A-1" {
    mode "1920x1080@60"
    scale 1.0
    position x=2560 y=180   // vertically centred relative to DP-1
}

// ── Layout ───────────────────────────────────────────────────────────────────
layout {
    gaps 8
    center-focused-column "never"

    preset-column-widths {
        proportion 0.33333
        proportion 0.5
        proportion 0.66667
        proportion 1.0
    }

    default-column-width { proportion 0.5; }

    focus-ring {
        width 2
        active-color "#7fc8ff"
        inactive-color "#505050"
    }

    border {
        off
    }

    struts {
        left 0
        right 0
        top 0
        bottom 0
    }
}

// ── Animations ───────────────────────────────────────────────────────────────
animations {
    workspace-switch {
        spring damping-ratio=1.0 stiffness=1000 epsilon=0.0001
    }
    window-open {
        duration-ms 150
        curve "ease-out-expo"
    }
    window-close {
        duration-ms 150
        curve "ease-out-quad"
    }
    horizontal-view-movement {
        spring damping-ratio=1.0 stiffness=800 epsilon=0.0001
    }
    window-movement {
        spring damping-ratio=1.0 stiffness=800 epsilon=0.0001
    }
    config-notification-open-close {
        spring damping-ratio=0.6 stiffness=1000 epsilon=0.001
    }
}

// ── Spawn-at-startup ─────────────────────────────────────────────────────────
spawn-at-startup "waybar"
spawn-at-startup "swww-daemon"
spawn-at-startup "mako"
spawn-at-startup "xwayland-satellite"   // XWayland support

// ── Prefer-no-CSD ────────────────────────────────────────────────────────────
prefer-no-csd

// ── Screenshot path ──────────────────────────────────────────────────────────
screenshot-path "~/Pictures/Screenshots/Screenshot from %Y-%m-%d %H-%M-%S.png"

// ── Hotkey overlay ───────────────────────────────────────────────────────────
hotkey-overlay {
    skip-at-startup
}
```

---

## 11.4 Keybindings (`binds` Block)

The `binds` block maps key combinations to niri actions. Modifier names are
`Mod` (Super/Meta), `Ctrl`, `Alt`, `Shift`. Actions are niri IPC commands
expressed as node children.

```kdl
binds {
    // ── Applications ─────────────────────────────────────────────────────
    Mod+Return { spawn "foot"; }
    Mod+D       { spawn "fuzzel"; }
    Mod+B       { spawn "firefox"; }
    Mod+E       { spawn "thunar"; }

    // ── Niri session ─────────────────────────────────────────────────────
    Mod+Shift+E { quit; }
    Mod+Shift+R { reload-config; }
    Mod+Shift+P { power-off-monitors; }

    // ── Window management ────────────────────────────────────────────────
    Mod+Q           { close-window; }
    Mod+F           { maximize-column; }
    Mod+Shift+F     { fullscreen-window; }
    Mod+C           { center-column; }

    // ── Focus movement ───────────────────────────────────────────────────
    Mod+H           { focus-column-left; }
    Mod+L           { focus-column-right; }
    Mod+J           { focus-window-down; }
    Mod+K           { focus-window-up; }
    Mod+Left        { focus-column-left; }
    Mod+Right       { focus-column-right; }
    Mod+Down        { focus-window-down; }
    Mod+Up          { focus-window-up; }

    Mod+Home        { focus-column-first; }
    Mod+End         { focus-column-last; }

    // ── Window movement ──────────────────────────────────────────────────
    Mod+Shift+H     { move-column-left; }
    Mod+Shift+L     { move-column-right; }
    Mod+Shift+J     { move-window-down; }
    Mod+Shift+K     { move-window-up; }
    Mod+Shift+Left  { move-column-left; }
    Mod+Shift+Right { move-column-right; }
    Mod+Shift+Home  { move-column-to-first; }
    Mod+Shift+End   { move-column-to-last; }

    // ── Column width cycling ─────────────────────────────────────────────
    Mod+R           { switch-preset-column-width; }
    Mod+Minus       { set-column-width "-10%"; }
    Mod+Equal       { set-column-width "+10%"; }

    // ── Window height ────────────────────────────────────────────────────
    Mod+Shift+Minus { set-window-height "-10%"; }
    Mod+Shift+Equal { set-window-height "+10%"; }

    // ── Workspaces ───────────────────────────────────────────────────────
    Mod+1 { focus-workspace 1; }
    Mod+2 { focus-workspace 2; }
    Mod+3 { focus-workspace 3; }
    Mod+4 { focus-workspace 4; }
    Mod+5 { focus-workspace 5; }
    Mod+6 { focus-workspace 6; }
    Mod+7 { focus-workspace 7; }
    Mod+8 { focus-workspace 8; }
    Mod+9 { focus-workspace 9; }

    Mod+Shift+1 { move-column-to-workspace 1; }
    Mod+Shift+2 { move-column-to-workspace 2; }
    Mod+Shift+3 { move-column-to-workspace 3; }
    Mod+Shift+4 { move-column-to-workspace 4; }
    Mod+Shift+5 { move-column-to-workspace 5; }

    Mod+Tab         { focus-workspace-down; }
    Mod+Shift+Tab   { focus-workspace-up; }
    Mod+Ctrl+H      { move-column-to-workspace-down; }  // alias
    Mod+Ctrl+L      { move-column-to-workspace-up; }

    // ── Monitors ─────────────────────────────────────────────────────────
    Mod+Comma       { focus-monitor-left; }
    Mod+Period      { focus-monitor-right; }
    Mod+Shift+Comma  { move-column-to-monitor-left; }
    Mod+Shift+Period { move-column-to-monitor-right; }

    // ── Overview ─────────────────────────────────────────────────────────
    Mod+O           { toggle-overview; }

    // ── Screenshots ──────────────────────────────────────────────────────
    Print           { screenshot; }
    Ctrl+Print      { screenshot-screen; }
    Alt+Print       { screenshot-window; }

    // ── Volume / brightness (via wpctl / brightnessctl) ──────────────────
    XF86AudioRaiseVolume allow-when-locked=true {
        spawn "wpctl" "set-volume" "@DEFAULT_AUDIO_SINK@" "0.1+";
    }
    XF86AudioLowerVolume allow-when-locked=true {
        spawn "wpctl" "set-volume" "@DEFAULT_AUDIO_SINK@" "0.1-";
    }
    XF86AudioMute allow-when-locked=true {
        spawn "wpctl" "set-mute" "@DEFAULT_AUDIO_SINK@" "toggle";
    }
    XF86MonBrightnessUp {
        spawn "brightnessctl" "set" "5%+";
    }
    XF86MonBrightnessDown {
        spawn "brightnessctl" "set" "5%-";
    }
}
```

---

## 11.5 Layout Deep Dive

### Column Widths

Niri supports two width modes: `proportion` (a fraction of the output width)
and `fixed` (pixels). The `preset-column-widths` block defines a list that the
`switch-preset-column-width` action cycles through. You can also set widths
dynamically with `set-column-width`.

```kdl
layout {
    preset-column-widths {
        proportion 0.25    // quarter screen
        proportion 0.5     // half screen
        proportion 0.75    // three-quarters
        fixed 1200         // absolute pixel width
        proportion 1.0     // full screen
    }

    default-column-width { proportion 0.5; }
}
```

The `center-focused-column` setting controls whether niri automatically scrolls
to keep the focused column visually centered:

```kdl
layout {
    // "never"   — viewport scrolls minimally to keep focus visible
    // "always"  — focused column is always centred on screen
    // "on-overflow" — centres only when the column doesn't fully fit
    center-focused-column "on-overflow"
}
```

### Stacking Windows in a Column

When you move a window into another column's position, niri stacks them
vertically. Each window in a column is separated by `gaps` pixels. The
`set-window-height` action resizes individual windows within a column.

```kdl
// Two windows in the same column each take ~50%
// Adjust one to 70%:
Mod+G { set-window-height "70%"; }
```

### Workspaces

Workspaces in Niri are per-output dynamic lists. Creating a new workspace is
implicit: if you move a column past the last workspace, a new one is created.
Named workspaces can be declared in the config:

```kdl
workspace "code"
workspace "browser"
workspace "comms"
workspace "misc"
```

Named workspaces appear in the Waybar niri module (see §11.7) and can be
focused by name:

```bash
niri msg action focus-workspace --reference name:code
```

---

## 11.6 Window Rules (`window-rule`)

Window rules let you apply per-application or per-window layout overrides.
Rules match on `title`, `app-id`, `is-focused`, `is-active`, etc.

```kdl
// Make Firefox always open at 2/3 width
window-rule {
    match app-id="firefox"
    default-column-width { proportion 0.666; }
}

// Make floating dialogs (e.g. file pickers) open at fixed size
window-rule {
    match app-id="xdg-desktop-portal-gtk"
    default-column-width { fixed 800; }
    default-window-height { fixed 600; }
    open-floating true
}

// Kitty always gets 50% width
window-rule {
    match app-id="kitty"
    default-column-width { proportion 0.5; }
}

// Gimp: open on workspace 3
window-rule {
    match app-id="gimp"
    open-on-workspace "misc"
}

// Disable focus ring for a specific app
window-rule {
    match app-id="mpv"
    focus-ring { off; }
    border { off; }
}

// Opacity for terminals
window-rule {
    match app-id="foot"
    opacity 0.95
}
```

To find the `app-id` for a running window, use:

```bash
niri msg windows | grep app-id
# or with jq:
niri msg --json windows | jq '.[].app_id'
```

---

## 11.7 Animations and Visual Polish

Niri has a first-class animation system that requires no external compositor
plugins. Animations use either a fixed duration + easing curve or a spring
physics model (recommended for natural feel).

### Spring Parameters

The spring model requires three parameters:
- `damping-ratio`: 1.0 = critically damped (no overshoot), <1.0 = under-damped (springy)
- `stiffness`: higher = faster response
- `epsilon`: stopping threshold (smaller = more precise but longer tail)

```kdl
animations {
    // Smooth workspace switching
    workspace-switch {
        spring damping-ratio=1.0 stiffness=1000 epsilon=0.0001
    }

    // Snappy column movement
    horizontal-view-movement {
        spring damping-ratio=1.0 stiffness=800 epsilon=0.0001
    }

    // Slightly springy window open
    window-open {
        spring damping-ratio=0.8 stiffness=1200 epsilon=0.0001
    }

    // Quick close — no need for spring
    window-close {
        duration-ms 100
        curve "ease-out-quad"
    }

    // Window resizing
    window-resize {
        spring damping-ratio=1.0 stiffness=800 epsilon=0.0001
    }

    // Window movement within/between columns
    window-movement {
        spring damping-ratio=1.0 stiffness=800 epsilon=0.0001
    }

    // Config reload notification popup
    config-notification-open-close {
        spring damping-ratio=0.6 stiffness=1000 epsilon=0.001
    }

    // Disable all animations (for accessibility or low-power)
    // off
}
```

### Available Easing Curves

When using `duration-ms` + `curve` instead of spring:

| Curve name           | Character                        |
|----------------------|----------------------------------|
| `ease-out-quad`      | Fast start, gentle stop          |
| `ease-out-cubic`     | Slightly more pronounced         |
| `ease-out-expo`      | Very fast start, long soft stop  |
| `ease-in-out-cubic`  | Symmetric, smooth                |
| `linear`             | Constant speed                   |

---

## 11.8 Niri IPC (`niri msg`)

Niri exposes a Unix domain socket IPC. The `niri msg` CLI lets you query state
and dispatch actions from scripts, status bars, and hotkey daemons. The socket
path defaults to `$XDG_RUNTIME_DIR/niri/socket`.

### Querying State

```bash
# List all outputs
niri msg outputs

# List all windows (human-readable)
niri msg windows

# List all windows (JSON, for scripting)
niri msg --json windows | jq '.[] | {id, app_id, title, workspace_id}'

# List workspaces
niri msg --json workspaces | jq '.[] | {id, name, output, is_focused}'

# Get focused window info
niri msg --json focused-window
```

### Dispatching Actions

```bash
# Focus a workspace by number
niri msg action focus-workspace --reference index:2

# Move focused window to a specific workspace
niri msg action move-column-to-workspace --reference name:browser

# Spawn a program
niri msg action spawn -- foot

# Set column width
niri msg action set-column-width "50%"

# Take a screenshot
niri msg action screenshot

# Toggle overview
niri msg action toggle-overview
```

### Scripting Example: Focus-or-Launch

A common idiom: focus an existing window of an app, or launch a new instance if
none exists.

```bash
#!/usr/bin/env bash
# focus-or-launch.sh <app-id> <launch-command...>
APP_ID="$1"
shift

EXISTING=$(niri msg --json windows 2>/dev/null \
  | jq -r ".[] | select(.app_id == \"$APP_ID\") | .id" \
  | head -1)

if [[ -n "$EXISTING" ]]; then
    niri msg action focus-window --id "$EXISTING"
else
    "$@" &
fi
```

Use it in your config:

```kdl
Mod+Return { spawn "/path/to/focus-or-launch.sh" "foot" "foot"; }
Mod+B      { spawn "/path/to/focus-or-launch.sh" "firefox" "firefox"; }
```

---

## 11.9 Niri Ecosystem Integration

### Waybar

Waybar ships a `niri/workspaces` and `niri/language` module. Add them to your
Waybar config:

```json
{
  "modules-left": ["niri/workspaces"],
  "modules-center": ["niri/window"],
  "modules-right": ["niri/language", "clock"],

  "niri/workspaces": {
    "format": "{name}",
    "on-click": "activate"
  },

  "niri/window": {
    "format": "{}",
    "max-length": 60
  },

  "niri/language": {
    "format": "{shortDescription}"
  }
}
```

Waybar communicates with niri via the IPC socket. If the niri module shows an
error, ensure `$WAYLAND_DISPLAY` is set correctly in the Waybar environment.
See **Ch 22** for full Waybar configuration.

### Quickshell

Quickshell supports niri via the `Niri.workspaces` and `Niri.windows` QML
bindings. See **Ch 24** for Quickshell integration patterns.

### swww (Wallpaper)

```bash
# Install swww
cargo install swww
# or
yay -S swww

# Initialise the daemon (add to spawn-at-startup in config.kdl)
swww-daemon &

# Set a wallpaper
swww img ~/Pictures/wallpaper.jpg \
  --transition-type wipe \
  --transition-angle 45 \
  --transition-duration 2
```

### Screen Locking with swaylock / hyprlock

```bash
# swaylock
swaylock \
  --screenshot \
  --clock \
  --indicator \
  --effect-blur 7x5 \
  --fade-in 0.2

# Add to niri config:
# Mod+Shift+L { spawn "swaylock"; }
```

### XWayland Support

Niri supports XWayland via `xwayland-satellite` (a rootful XWayland bridge)
rather than a built-in XWayland implementation. This is intentional: it keeps
the Niri codebase clean and delegates X11 compatibility to a separate process.

```bash
# Install xwayland-satellite
yay -S xwayland-satellite
# or build from source:
git clone https://github.com/Supreeeme/xwayland-satellite
cd xwayland-satellite && cargo build --release

# Add to niri config.kdl:
spawn-at-startup "xwayland-satellite"
```

The `DISPLAY` environment variable will be set automatically for launched apps.

---

## 11.10 Niri's Current Limitations (2025 Status)

Niri is production-quality for most workflows but has known gaps compared to
Hyprland. Understanding these helps you make an informed choice.

| Feature                      | Niri Status (mid-2025)     | Notes                                    |
|------------------------------|----------------------------|------------------------------------------|
| HDR (High Dynamic Range)     | Not yet implemented        | Tracked upstream, Smithay work in progress |
| DRM sync objects             | Partial                    | Impacts GPU performance on some setups   |
| Floating windows             | Not supported natively     | By design; use xwayland-satellite workaround |
| VRR / Adaptive sync          | Supported                  | Via `vrr` output block                   |
| Screen capture (wlr-screencopy) | Supported               | Works with OBS, wf-recorder              |
| Inhibit idle (xdg-inhibitor) | Supported                  |                                          |
| Multi-seat                   | Not supported              | Single-seat only                         |
| Tablet / stylus input        | Basic support              | Full pressure curve config planned       |
| Plugin system                | None (Rust-native only)    | Hyprland-style plugins not available     |
| Touch gestures               | Basic swipe-to-scroll      | Full gesture scripting not yet available |

For users who need floating windows extensively (e.g., Gimp, legacy apps),
Hyprland (Ch 08) or Sway (Ch 07) are better choices. For scrollable-layout
users willing to handle floating needs via XWayland workarounds, Niri is
excellent.

---

## 11.11 Niri vs. Hyprland: When Scrollable Wins

The choice between Niri and Hyprland is not primarily about features — it is
about workflow philosophy. Hyprland's flexible tiling accommodates both floating
and tiled workflows, at the cost of greater configuration surface area and the
need to manage layout rules. Niri's opinionated scrollable model eliminates
layout decisions entirely: every window is in a column, columns are adjacent,
you scroll.

Wide-monitor workflows (3440×1440 ultrawide, 4K, or dual 1440p) benefit most
from Niri. The scrollable canvas fills the horizontal space naturally without
requiring manual layout management or complex workspace schemes. Three columns at
33% width each gives three full usable panels on a 2560px monitor.

Document-heavy work — academic research, writing, reading PDFs while taking
notes — maps beautifully to adjacent columns. The document is column N, the
editor is column N+1, the terminal for running pandoc is column N+2. No
alt-tabbing, no workspace switches, just left/right.

Users migrating from PaperWM or i3-gaps will find Niri immediately intuitive.
PaperWM users get native Wayland performance without GNOME Shell overhead. i3
users lose named workspaces but gain a spatial model that, once internalised,
is faster for multi-tasking.

```
Scrollable layout mental model:

  [vim]  [firefox]  [foot]  [docs]  [slack]   ... (infinite)
  ┌────┐  ┌───────┐  ┌────┐  ┌────┐  ┌─────┐
  │    │  │       │  │    │  │    │  │     │
  │    │  │       │  │    │  │    │  │     │
  └────┘  └───────┘  └────┘  └────┘  └─────┘
              ^^ viewport (monitor) ^^
```

---

## Troubleshooting

### Niri fails to start: "No seat available"

Niri requires logind (or elogind) and a PAM seat session. Ensure you are
launching from a login shell on a TTY, not via SSH.

```bash
# Check seat status
loginctl show-session $(loginctl | grep seat | awk '{print $1}') | grep Seat
# Should show: Seat=seat0

# Check libseat / seatd if not using logind
sudo systemctl enable --now seatd
sudo usermod -aG seat $USER
```

### Blank screen / GPU issue

```bash
# Check DRM devices
ls -la /dev/dri/

# Force software rendering (for testing)
WLR_RENDERER=pixman niri

# Check Mesa
glxinfo | grep "OpenGL renderer"
vulkaninfo | grep deviceName
```

### Waybar niri modules not updating

```bash
# Ensure Waybar is launched after niri socket is available
# Check socket path
ls -la $XDG_RUNTIME_DIR/niri/

# Restart waybar
pkill waybar && waybar &
```

### XWayland apps not working

```bash
# Check xwayland-satellite is running
pgrep xwayland-satellite

# Check DISPLAY env var in a launched terminal
echo $DISPLAY   # Should be :0 or similar

# Manually start and check output
xwayland-satellite :10 2>&1 | head -20
```

### Config reload fails silently

```bash
# Validate before reloading
niri validate --config ~/.config/niri/config.kdl

# Common KDL errors:
# - Missing semicolons inside single-line children: { action; }
# - Quoting: strings with spaces need quotes: "my value"
# - Stale syntax from older niri versions: check release notes
```

### Focus ring / border not visible

Ensure the colors are set as hex strings and the width is non-zero:

```kdl
layout {
    focus-ring {
        width 3
        active-color "#7fc8ff"
        inactive-color "#404040"
        active-gradient from="#7fc8ff" to="#00d4ff" angle=45
    }
}
```

### High CPU usage with animations

```bash
# Disable animations temporarily
# In config.kdl, add inside animations {}:
animations {
    off
}

# Check compositor rendering time
niri msg --json output-info
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
