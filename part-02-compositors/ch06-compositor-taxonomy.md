# Chapter 6 — Compositor Taxonomy: Tiling, Stacking, Dynamic, Kiosk

## Overview

Before committing dozens of hours to configuring a compositor, you need a mental model of the entire landscape. The Wayland compositor ecosystem is rich but fragmented: there are at least a dozen actively maintained compositors, each making different trade-offs around layout philosophy, configuration ergonomics, animation support, and portability. Choosing wrong means either a painful migration later or a perpetual sense that your tooling is fighting your workflow.

This chapter builds a taxonomy of all major compositor families along five orthogonal design axes. It then surveys each family in depth — not just listing compositors, but explaining the architectural decisions that make each family distinct. By the end you will have the vocabulary and mental framework to read compositor documentation, evaluate new entrants, and explain your choice to fellow ricers.

Cross-references: the individual compositors mentioned here are covered in full in Chapters 7 through 14. Chapter 53 covers session startup and display managers. Chapter 40 covers IPC scripting patterns common to several families.

---

## 6.1 Design Axes

Every Wayland compositor occupies a position on five independent design axes. Understanding these axes separates "this looks cool" shopping from informed selection.

### Axis 1 — Layout Model

The layout model determines how windows are initially placed and how they relate spatially to each other.

| Model | Description | Representative Compositors |
|-------|-------------|---------------------------|
| **Stacking (floating)** | Windows stack like paper; any can overlap any other | labwc, KWin, Mutter, weston |
| **Manual tiling** | User explicitly moves splits and windows; no auto-placement | Sway, dwl |
| **Automatic tiling** | Compositor tiles windows according to an algorithm; user overrides | Hyprland dwindle, Wayfire tiling plugin |
| **Dynamic (tag-driven)** | Layouts applied per-tag or per-workspace from an external list | river, dwl tags |
| **Scrollable / spatial** | Windows on an infinite 1-D or 2-D canvas; no workspaces needed | niri, PaperWM |
| **Kiosk / single-app** | One fullscreen application; compositor manages nothing else | cage, gamescope |

The layout model is the most consequential choice and the hardest to change after you've built muscle memory. Manual tiling gives you full control but demands constant interaction. Automatic tiling is faster for exploratory multi-window workflows but can surprise you when the algorithm disagrees with your intent.

### Axis 2 — Configuration Style

| Style | Pros | Cons | Example |
|-------|------|------|---------|
| **Declarative text config** | Version-controllable, scriptable, no GUI dependency | Syntax learning curve | Sway (`config`), Hyprland (`hyprland.conf`) |
| **IPC-scripted** | Dynamic reconfiguration at runtime, any language | Config not in one file | river (`riverctl` calls in shell script) |
| **Lua plugins** | Full programming language, hot-reload | Performance concerns with bad scripts | Wayfire, KWin scripts |
| **GUI settings** | Approachable, discoverable | Harder to reproduce across machines | GNOME Settings, KDE System Settings |
| **Hybrid** | Flexibility | Complexity, two systems to maintain | KWin (GUI + KWin Scripts) |

Ricers overwhelmingly prefer declarative text configs because they compose well with dotfile managers (chezmoi, stow) and are trivially reproducible across machines. If portability across multiple hosts is a priority, avoid GUI-only configuration entirely.

### Axis 3 — Base Library / Rendering Stack

| Base | Language | Compositors Built On It |
|------|----------|------------------------|
| **wlroots** | C | Sway, river, dwl, labwc, Wayfire |
| **Smithay** | Rust | niri, cosmic-comp, Anvil |
| **KWin** | C++ / QML | KDE Plasma, Plasma Mobile, lxqt-kwin |
| **Mutter** | C / GObject | GNOME Shell, Phosh |
| **Custom / minimal** | C | weston, cage, gamescope |

wlroots is the dominant shared library: it abstracts DRM/KMS, input event handling, Wayland protocol implementation, and the scene graph. Building on wlroots gives you free implementations of dozens of Wayland extension protocols (layer-shell, xdg-decoration, virtual-keyboard, etc.) at the cost of coupling your compositor's release cycle to wlroots'. Smithay is the emerging Rust-native alternative, prioritising memory safety and async I/O.

### Axis 4 — Workspace / Tag Model

| Model | Description | Compositors |
|-------|-------------|-------------|
| **Numbered workspaces** | Workspaces 1–N, one active per monitor | Sway, Hyprland, labwc |
| **Named workspaces** | String-named workspaces, arbitrary count | Hyprland, Sway |
| **Tags (bitmask)** | Windows assigned bitmask of tags; view is a set of active tags | dwl, river |
| **Scrollable timeline** | Windows on a horizontal strip; no discrete workspaces | niri |
| **Virtual desktops (KDE)** | Workspaces shared across all outputs | KWin/Plasma |

The dwm-inherited tag model is underappreciated: a window can be on multiple tags simultaneously, and you can view the union or intersection of tags. This allows very flexible "contexts" without duplicating windows.

### Axis 5 — Animation Philosophy

| Philosophy | Description | Compositors |
|------------|-------------|-------------|
| **None** | Strictly functional; no transitions | dwl, cage |
| **Subtle** | <100 ms fade/slide, disabled in configs | Sway (via swayipc), labwc |
| **Moderate** | Bezier-curve window animations, configurable | Hyprland, KWin |
| **Heavy / showcase** | 3D cube, wobbly windows, fire effects | Wayfire, KDE desktop effects |

Animation has a real latency cost. "Snappy" animations (30–80 ms) improve perceived responsiveness. Animations beyond ~200 ms actively slow work. Hyprland's `animation` stanza gives per-event, per-curve control; see Chapter 8 for tuning.

---

## 6.2 Stacking Compositors

Stacking compositors draw windows in a Z-ordered stack. The frontmost window fully occludes those behind it. All floating window managers since the 1980s follow this model; stacking Wayland compositors simply implement it under the Wayland protocol.

The canonical wlroots-based stacking compositor is **labwc** (Lightweight Accessible Button Compositor). It implements the OpenBox configuration format over Wayland, making it a natural migration target for users coming from X11 OpenBox setups. labwc supports layer-shell for panels and docks, xdg-activation, and foreign-toplevel-management, giving it compatibility with most Wayland-native taskbars.

**KWin** (bundled with KDE Plasma) is the most feature-complete stacking compositor. It supports both X11 and Wayland sessions, uses a tile-able floating model with optional manual tiling add-ons, and exposes a KWin Scripts API in QML for runtime automation. Its Wayland support reached production quality in Plasma 6.0 (early 2024); GPU-accelerated compositing, HDR, variable refresh rate, and explicit sync are all supported.

**GNOME Mutter** is the compositor underlying GNOME Shell. It is not configurable directly — GNOME Shell extensions mediate all customisation. For ricers who want GNOME's application ecosystem without GNOME's constraints, running a different compositor (Sway, Hyprland) while keeping GTK apps is perfectly viable.

**weston** is the reference compositor maintained by the Wayland project itself. It is intentionally minimal and is used primarily for protocol testing, not daily driving. Its kiosk shell (see §6.7) is an exception: it is production-quality for single-application deployments.

```bash
# Install labwc on Arch Linux
sudo pacman -S labwc

# Minimal labwc session: launch from TTY
exec labwc

# labwc rc.xml snippet — set window decorations and default placement
# ~/.config/labwc/rc.xml
cat > ~/.config/labwc/rc.xml << 'EOF'
<?xml version="1.0"?>
<openbox_config>
  <core>
    <decoration>client</decoration>
    <gap>4</gap>
  </core>
  <placement>
    <policy>UnderMouse</policy>
  </placement>
  <keyboard>
    <keybind key="Super-Return">
      <action name="Execute"><command>foot</command></action>
    </keybind>
    <keybind key="Super-d">
      <action name="Execute"><command>fuzzel</command></action>
    </keybind>
  </keyboard>
</openbox_config>
EOF

# Launch labwc with a status bar
cat > ~/.config/labwc/autostart << 'EOF'
waybar &
swaybg -i ~/wallpapers/bg.jpg -m fill &
EOF
```

---

## 6.3 Manual Tiling Compositors

Manual tiling compositors give the user complete, explicit control over window placement and split geometry. No window is placed automatically — you issue commands to split the current container horizontally or vertically, and the new window fills that split. Resizing is equally explicit. The mental model is close to an IDE split-pane editor: you build a layout deliberately.

**Sway** is the dominant manual tiling Wayland compositor, designed as a drop-in Wayland replacement for i3. Its configuration file is nearly syntax-compatible with i3's; most i3 configs require only minor changes (primarily replacing X11-specific invocations). Sway uses `wlroots` internally and exposes an IPC socket that speaks the i3 IPC protocol, allowing the entire i3 ecosystem of status bars (i3status, i3blocks), scripts, and tools to work with minimal modification.

Sway's container model: every output contains a tree of containers. Containers are either workspaces, horizontal splits, vertical splits, tabbed stacks, or stacked groups. Windows are leaves. You navigate and operate on this tree using keyboard shortcuts. The `swaymsg` command introspects and modifies the tree at runtime.

**dwl** (dwm for Wayland) is an ultra-minimal wlroots-based compositor that ports the dwm model. It is not a compositor you configure with a file — you patch and recompile the C source. This makes it extremely lightweight (<2000 lines of code) and infinitely customisable if you read C, but impractical for users who want configuration without compilation.

```bash
# Install Sway on Fedora
sudo dnf install sway swaybg swaylock swayidle waybar foot fuzzel

# Minimal ~/.config/sway/config
cat > ~/.config/sway/config << 'EOF'
# Variables
set $mod Mod4
set $term foot
set $menu fuzzel

# Output
output * bg ~/wallpapers/bg.jpg fill

# Input
input "type:keyboard" {
    xkb_layout us
    xkb_options caps:escape
}

# Key bindings — fundamentals
bindsym $mod+Return exec $term
bindsym $mod+d exec $menu
bindsym $mod+Shift+q kill
bindsym $mod+Shift+e exec swaymsg exit

# Layout splits
bindsym $mod+h splith
bindsym $mod+v splitv

# Focus
bindsym $mod+Left focus left
bindsym $mod+Right focus right
bindsym $mod+Up focus up
bindsym $mod+Down focus down

# Move windows
bindsym $mod+Shift+Left move left
bindsym $mod+Shift+Right move right
bindsym $mod+Shift+Up move up
bindsym $mod+Shift+Down move down

# Workspaces
bindsym $mod+1 workspace number 1
bindsym $mod+2 workspace number 2
bindsym $mod+3 workspace number 3
bindsym $mod+Shift+1 move container to workspace number 1

# Gaps
gaps inner 6
gaps outer 4
smart_gaps on

# Status bar
bar {
    swaybar_command waybar
}
EOF

# Query the window tree
swaymsg -t get_tree | jq '.nodes[].nodes[].nodes[].name'

# Move focused window to scratchpad
swaymsg move scratchpad

# Resize focused container by 10px
swaymsg resize grow width 10
```

```bash
# Build dwl from source (Arch)
sudo pacman -S wlroots wayland wayland-protocols libxkbcommon pixman base-devel
git clone https://codeberg.org/dwl/dwl.git && cd dwl
cp config.def.h config.h
# Edit config.h to set terminal, modifier key, colour scheme, etc.
make && sudo make install
```

---

## 6.4 Dynamic and Automatic Tiling Compositors

Dynamic tiling compositors apply a layout algorithm that automatically arranges all windows on a workspace according to a configurable rule. When a new window opens, the compositor reflows the entire layout. Users spend less time managing geometry and more time working; the cost is occasionally surprising reflows and less pixel-precise control.

**Hyprland** is the most popular dynamic tiling Wayland compositor as of 2024–2025. It ships two built-in layout algorithms: `dwindle` (a balanced binary-tree split, similar to bspwm) and `master` (one large master pane with a stack of secondary windows). Both are configurable at a fine level. Hyprland also supports animations, rounded corners, blur, drop shadows, and per-window opacity rules — features normally associated with compositing window managers on X11.

Hyprland's configuration language (`hyprland.conf`) uses a custom key=value format with sections. It supports live-reloading: `hyprctl reload` re-reads the config without restarting the compositor. The `hyprctl` binary provides a rich IPC interface to query and control everything at runtime.

**river** takes a different approach: it delegates layout computation entirely to external programs called "layout generators." The compositor itself manages windows and outputs, but a separate process (e.g., `rivertile`, `river-luatile`) calculates the geometry rectangles and communicates them back via the `river-layout-v3` protocol. This makes river extremely composable — you can write a layout generator in any language — but requires wiring up more pieces to get a working desktop.

**Way Cooler** (historical) was an early Rust-based automatic tiling compositor that has since been superseded by Smithay-based projects. It is mentioned here only for historical context; do not use it on new systems.

```bash
# Install Hyprland on Arch
sudo pacman -S hyprland hyprpaper hyprlock hypridle waybar foot fuzzel

# ~/.config/hypr/hyprland.conf — annotated starter
cat > ~/.config/hypr/hyprland.conf << 'EOF'
# Monitor configuration
monitor=,preferred,auto,1

# Variables
$terminal = foot
$fileManager = dolphin
$menu = fuzzel

# Autostart
exec-once = waybar
exec-once = hyprpaper
exec-once = hypridle

# Environment variables (for Electron/Qt/GTK Wayland)
env = XCURSOR_SIZE,24
env = QT_QPA_PLATFORM,wayland
env = GDK_BACKEND,wayland,x11

# Input
input {
    kb_layout = us
    kb_options = caps:escape
    follow_mouse = 1
    touchpad {
        natural_scroll = yes
        tap-to-click = yes
    }
}

# General appearance
general {
    gaps_in = 5
    gaps_out = 10
    border_size = 2
    col.active_border = rgba(33ccffee) rgba(00ff99ee) 45deg
    col.inactive_border = rgba(595959aa)
    layout = dwindle
}

# Decoration
decoration {
    rounding = 10
    blur {
        enabled = true
        size = 3
        passes = 1
    }
    drop_shadow = yes
    shadow_range = 4
    shadow_render_power = 3
}

# Animations
animations {
    enabled = yes
    bezier = myBezier, 0.05, 0.9, 0.1, 1.05
    animation = windows, 1, 7, myBezier
    animation = windowsOut, 1, 7, default, popin 80%
    animation = fade, 1, 7, default
    animation = workspaces, 1, 6, default
}

# Layout: dwindle
dwindle {
    pseudotile = yes
    preserve_split = yes
}

# Window rules
windowrulev2 = float, class:^(pavucontrol)$
windowrulev2 = size 800 600, class:^(pavucontrol)$
windowrulev2 = opacity 0.90 0.80, class:^(foot)$

# Key bindings
$mainMod = SUPER
bind = $mainMod, Return, exec, $terminal
bind = $mainMod, Q, killactive,
bind = $mainMod, M, exit,
bind = $mainMod, E, exec, $fileManager
bind = $mainMod, D, exec, $menu
bind = $mainMod, F, fullscreen,
bind = $mainMod, Space, togglefloating,
bind = $mainMod, P, pseudo,
bind = $mainMod, J, togglesplit,

# Focus movement
bind = $mainMod, left, movefocus, l
bind = $mainMod, right, movefocus, r
bind = $mainMod, up, movefocus, u
bind = $mainMod, down, movefocus, d

# Workspaces
bind = $mainMod, 1, workspace, 1
bind = $mainMod SHIFT, 1, movetoworkspace, 1
bind = $mainMod, 2, workspace, 2
bind = $mainMod SHIFT, 2, movetoworkspace, 2

# Scroll through workspaces
bind = $mainMod, mouse_down, workspace, e+1
bind = $mainMod, mouse_up, workspace, e-1

# Move/resize windows with mouse
bindm = $mainMod, mouse:272, movewindow
bindm = $mainMod, mouse:273, resizewindow
EOF

# Query active window info
hyprctl activewindow

# List all windows with their workspace
hyprctl clients | jq '.[] | {class, workspace: .workspace.name}'

# Switch layout at runtime
hyprctl keyword general:layout master
```

```bash
# Install river on Arch
sudo pacman -S river rivertile foot fuzzel waybar

# ~/.config/river/init — shell script executed at startup
cat > ~/.config/river/init << 'EOF'
#!/bin/sh

# Use rivertile for layout
riverctl default-layout rivertile
rivertile -view-padding 6 -outer-padding 6 &

# Set mod key
mod="Super"

# Terminal and launcher
riverctl map normal $mod Return spawn foot
riverctl map normal $mod D spawn fuzzel
riverctl map normal $mod+Shift Q close

# Focus and swap
riverctl map normal $mod J focus-view next
riverctl map normal $mod K focus-view previous
riverctl map normal $mod+Shift J swap next
riverctl map normal $mod+Shift K swap previous

# Layout orientation
riverctl map normal $mod H send-layout-cmd rivertile "main-ratio -0.05"
riverctl map normal $mod L send-layout-cmd rivertile "main-ratio +0.05"

# Tags (1-9)
for i in $(seq 1 9); do
    tags=$((1 << ($i - 1)))
    riverctl map normal $mod $i set-focused-tags $tags
    riverctl map normal $mod+Shift $i set-view-tags $tags
done

# Floating and fullscreen
riverctl map normal $mod Space toggle-float
riverctl map normal $mod F toggle-fullscreen

# Start bar
waybar &
EOF
chmod +x ~/.config/river/init
```

---

## 6.5 Plugin and Effect Compositors

Plugin-based compositors expose their rendering and behaviour through a plugin/extension API. Rather than baking every feature into the compositor core, they provide hooks where external code (loaded as shared libraries, Lua scripts, or QML) can intercept rendering, input, and window management events.

**Wayfire** is the primary wlroots-based plugin compositor. Its plugin architecture uses a C++ ABI: plugins implement well-defined interfaces (output, view, input transformer, etc.) and are loaded as `.so` files at startup. The `wf-config` system provides a structured INI-like config (`~/.config/wayfire/wayfire.ini`) with per-plugin sections. The **WCM** (Wayfire Config Manager) is a GTK GUI for `wayfire.ini`, but config-file editing is equally effective.

Wayfire ships with plugins for: grid tiling, expo (zoomed-out workspace overview), cube (3D rotating workspace cube), wobbly windows (simulating cloth physics), annotate (drawing on screen), and many more. The full community plugin list lives at `https://github.com/WayfireWM/wayfire-plugins-extra`.

**KWin Scripts** extend KWin in QML and JavaScript. A KWin Script can respond to any window lifecycle event, move or resize windows, change virtual desktops, or trigger system actions. This is how third-party tiling layouts (e.g., `kwin-bismuth`, `kwin-polonium`) are implemented on KDE without forking KWin itself. Scripts are installed through KDE's store or manually into `~/.local/share/kwin/scripts/`.

```ini
# ~/.config/wayfire/wayfire.ini — annotated example with common plugins

[core]
plugins = required autostart wm-actions fast-switcher resize move place \
          grid expo cube wobbly scale animate vswitch

[output:eDP-1]
mode = 1920x1080@60
position = 0,0
transform = normal

[autostart]
autostart_wf_shell = false
bar = waybar
background = swaybg -i ~/wallpapers/bg.jpg -m fill

[input]
kb_layout = us
kb_options = caps:escape
natural_scroll = true

[wm-actions]
toggle_fullscreen = <super> KEY_F
toggle_always_on_top = <super> KEY_T
toggle_sticky = <super> KEY_S

[move]
activate = <super> BTN_LEFT

[resize]
activate = <super> BTN_RIGHT

[grid]
# Snap windows to halves and corners
slot_bl = <super> KEY_KP1
slot_b  = <super> KEY_KP2
slot_br = <super> KEY_KP3
slot_l  = <super> KEY_KP4
slot_c  = <super> KEY_KP5
slot_r  = <super> KEY_KP6
slot_tl = <super> KEY_KP7
slot_t  = <super> KEY_KP8
slot_tr = <super> KEY_KP9

[expo]
# Show all workspaces zoomed out
toggle = <super> KEY_E

[cube]
# Rotate workspaces as a 3D cube
activate = <ctrl> <alt> BTN_LEFT

[wobbly]
friction = 3.0
spring_k = 15.0

[scale]
# Application switcher overlay (like GNOME Activities)
toggle = <super> KEY_TAB
```

```bash
# Install Wayfire on Arch
sudo pacman -S wayfire wcm wayfire-plugins-extra wf-shell

# Check available plugins
ls /usr/lib/wayfire/

# Install a KWin script (Polonium tiling)
git clone https://github.com/zeroxoneafour/polonium.git
cd polonium && make install
# Enable via: KDE System Settings → Window Management → KWin Scripts
```

---

## 6.6 Scrollable and Spatial Compositors

Scrollable compositors abandon the discrete workspace metaphor entirely. Instead of switching between numbered workspaces, windows are arranged on a continuous strip (or plane), and you navigate by panning. This mirrors the spatial memory model of a physical desk: you know roughly "where" each window lives and pan to it.

**niri** (written in Rust on Smithay) is the primary production-quality scrollable compositor. Its model is a horizontal strip: windows tile vertically within columns, and columns scroll horizontally. Opening a new window always creates a new column to the right of the current one. This encourages keeping related windows in the same column and browsing laterally across contexts. niri has strong animation support baked in and a KDL-format configuration file.

niri's killer feature for context-heavy work is that panning preserves context — you never lose a window because it fell off a workspace. Every window always exists somewhere on the strip; you can always find it by scrolling or using the `niri msg` query interface.

**PaperWM** is not a Wayland compositor itself; it is a GNOME Shell extension that implements scrollable tiling on top of Mutter. It is included here because many users encounter it as their first scrollable tiling experience before migrating to a standalone compositor. Its behaviour is very similar to niri, and if you like PaperWM, niri is the compositor to try on a standalone setup.

```bash
# Install niri on Arch (via AUR)
yay -S niri

# ~/.config/niri/config.kdl — minimal working config
cat > ~/.config/niri/config.kdl << 'EOF'
input {
    keyboard {
        xkb { layout "us"; options "caps:escape"; }
    }
    touchpad {
        tap
        natural-scroll
    }
}

output "eDP-1" {
    scale 1.0
    mode "1920x1080"
}

layout {
    gaps 8
    center-focused-column "never"
    preset-column-widths {
        proportion 0.33333
        proportion 0.5
        proportion 0.66667
    }
    default-column-width { proportion 0.5; }
    focus-ring {
        width 2
        active-color "#7fc8ff"
        inactive-color "#505050"
    }
}

animations {
    slowdown 1.0
}

spawn-at-startup "waybar"
spawn-at-startup "swaybg" "-i" "/home/user/wallpapers/bg.jpg" "-m" "fill"

binds {
    Mod+Return { spawn "foot"; }
    Mod+D { spawn "fuzzel"; }
    Mod+Q { close-window; }
    Mod+H { focus-column-left; }
    Mod+L { focus-column-right; }
    Mod+J { focus-window-down; }
    Mod+K { focus-window-up; }
    Mod+Shift+H { move-column-left; }
    Mod+Shift+L { move-column-right; }
    Mod+F { maximize-column; }
    Mod+Shift+F { fullscreen-window; }
    Mod+1 { focus-workspace 1; }
    Mod+Shift+1 { move-window-to-workspace 1; }
    Mod+2 { focus-workspace 2; }
    Mod+Shift+2 { move-window-to-workspace 2; }
    Mod+Minus { set-column-width "-10%"; }
    Mod+Equal { set-column-width "+10%"; }
    Mod+Comma { consume-window-into-column; }
    Mod+Period { expel-window-from-column; }
    Mod+Shift+E { quit; }
    Mod+Shift+Slash { show-hotkey-overlay; }
}
EOF

# Query niri state
niri msg workspaces
niri msg windows
niri msg focused-window
```

---

## 6.7 Kiosk and Embedded Compositors

Kiosk compositors are single-purpose: they launch one application fullscreen and prevent the user from escaping to a desktop. This is appropriate for digital signage, game launcher overlays, in-vehicle infotainment systems, and any device where "the application is the interface."

**cage** is the canonical minimal kiosk compositor. It accepts a single command as its argument, runs that command fullscreen, and exits when the command exits. It has no configuration file. cage is less than 1000 lines of C and is appropriate anywhere you want a minimal, auditable kiosk shell.

**gamescope** (developed by Valve) is a specialised gaming compositor. It embeds inside an existing session (Wayland or X11) as a nested compositor, captures a game's output, and can upscale it (via AMD FSR or pixel scaling), apply frame-rate limiting, handle VRR (variable refresh rate), and provide a clean fullscreen surface even from games that don't natively support fullscreen Wayland. Steam's Big Picture mode runs inside gamescope on SteamOS.

**weston kiosk shell** is weston run with the `kiosk-shell` plugin. Unlike cage, it supports multi-window kiosk scenarios (e.g., a panel and a main application) while still locking focus and preventing desktop escape.

```bash
# Run a single app fullscreen with cage
sudo pacman -S cage
cage -- firefox

# Autostart cage on TTY1 from /etc/systemd/system/cage-kiosk.service
cat > /etc/systemd/system/cage-kiosk.service << 'EOF'
[Unit]
Description=Cage Kiosk Session
After=systemd-user-sessions.service

[Service]
User=kiosk
PAMName=login
WorkingDirectory=/home/kiosk
TTYPath=/dev/tty1
StandardInput=tty
EnvironmentFile=-/etc/locale.conf
ExecStart=/usr/bin/cage -- /usr/bin/firefox --kiosk https://dashboard.example.com
Restart=always

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl enable --now cage-kiosk.service

# gamescope: run a game with FSR upscaling from 1440p → 4K
gamescope -W 3840 -H 2160 -w 2560 -h 1440 -f --fsr-upscaling -- %command%

# gamescope: nested inside an existing Wayland session
gamescope -e -- steam -gamepadui

# weston kiosk shell
cat > /etc/weston.ini << 'EOF'
[core]
shell=kiosk-shell.so
backend=drm-backend.so

[output]
name=eDP-1
mode=1920x1080

[kiosk]
application=/usr/bin/chromium --kiosk --no-sandbox
EOF
weston --config=/etc/weston.ini
```

---

## 6.8 Full Desktop Environment Compositors

Full DE compositors are not standalone compositors — they are deeply integrated with a complete desktop environment that provides panels, notifications, settings daemons, file managers, and application frameworks. The compositor is one component in a tightly coupled system.

**KWin + KDE Plasma** is the most feature-complete Linux desktop. Plasma 6 (released February 2024) ships with a Wayland session as default, retiring the X11 session for most use cases. KWin handles compositing, tiling (optional), window animations, screen edge gestures, and HDR. KDE's Wayland session supports explicit sync, proper variable refresh rate, and Plasma-specific protocols (KDE-specific layer-shell extensions, Plasma activities). Configuration is through System Settings; power users supplement with KWin Scripts.

**Mutter + GNOME Shell** powers the GNOME desktop. GNOME Shell is a JavaScript application running on top of Mutter (using GJS and Clutter). All GNOME visual customisation passes through Shell extensions. The GNOME Wayland session is extremely polished but opinionated: you get minimal user control without extensions. For heavy ricing, GNOME is typically used as an application compatibility layer (running GTK apps, portals, etc.) while running a different compositor.

**cosmic-comp + COSMIC Desktop** is System76's new Rust-native desktop environment (alpha/beta as of 2024–2025). `cosmic-comp` is built on Smithay, ships automatic tiling as first-class, and has a configuration API designed for programmatic management. The COSMIC desktop is the first significant new Linux DE in many years and worth monitoring as it matures.

```bash
# KDE Plasma Wayland session — ensure correct session is selected in SDDM
# /usr/share/wayland-sessions/plasma.desktop is installed by plasma-workspace

# Verify KWin is running on Wayland
qdbus org.kde.KWin /KWin supportInformation | head -5

# Enable a KWin Script via command line (Polonium example)
kwriteconfig5 --file kwinrc --group Plugins --key poloniumEnabled true
qdbus org.kde.KWin /KWin reconfigure

# Query KWin window list via D-Bus
qdbus org.kde.KWin /KWin org.kde.KWin.getWindowInfo $(qdbus org.kde.KWin /KWin activeWindow)

# GNOME Shell — list installed extensions
gnome-extensions list --enabled

# Disable an extension
gnome-extensions disable user-theme@gnome-shell-extensions.gcampax.github.com

# cosmic-comp is in early development; install from copr (Fedora) or AUR
# Arch AUR:
yay -S cosmic-session
# Launch:
# Select "COSMIC" from display manager session menu
```

---

## 6.9 Comprehensive Comparison Matrix

The table below compares every compositor discussed in this chapter across all five design axes. Use it as a quick reference when evaluating options.

| Compositor | Layout Model | Config Style | Base Library | Tag Model | Animation |
|------------|-------------|--------------|--------------|-----------|-----------|
| **Sway** | Manual tiling | Declarative text | wlroots | Numbered workspaces | Subtle (via swayipc) |
| **dwl** | Manual tiling + tags | C source patch | wlroots | dwm-style tags | None |
| **Hyprland** | Dynamic (dwindle/master) | Declarative text | Aquamarine | Named/numbered WS | Heavy, configurable |
| **river** | Dynamic (external generators) | IPC shell script | wlroots | dwm-style tags | None |
| **Wayfire** | Stacking + grid plugin | INI + plugins | wlroots | Numbered workspaces | Heavy (plugins) |
| **labwc** | Stacking | XML (OpenBox) | wlroots | Numbered workspaces | Subtle |
| **niri** | Scrollable columns | KDL declarative | Smithay | Workspaces + scroll | Built-in, smooth |
| **KWin** | Stacking + optional tiling | GUI + QML scripts | KWin (custom) | Virtual desktops | Heavy, configurable |
| **Mutter** | Stacking | JS extensions | Mutter (custom) | Virtual desktops | Moderate |
| **cosmic-comp** | Dynamic tiling | COSMIC API | Smithay | Workspaces | Moderate |
| **cage** | Kiosk | None | wlroots | N/A | None |
| **gamescope** | Kiosk/nested | CLI flags | SDL/wlroots | N/A | None |
| **weston** | Stacking/kiosk | INI | libweston | N/A | None |

---

## Troubleshooting

### Compositor fails to start on TTY

Most compositor startup failures are environment variable problems. Verify the `XDG_RUNTIME_DIR` is set and writable:

```bash
echo $XDG_RUNTIME_DIR          # should be /run/user/$(id -u)
ls -la $XDG_RUNTIME_DIR        # should be owned by your user, mode 0700
systemctl --user status        # systemd user session should be active
```

If `XDG_RUNTIME_DIR` is unset, start the compositor via a systemd user service or ensure `pam_systemd.so` is in your PAM stack (`/etc/pam.d/login`).

### GPU not detected / software rendering fallback

```bash
# Check DRM devices
ls /dev/dri/
# Should show card0 (or card1 for discrete GPU), renderD128

# Check GPU driver is loaded
lsmod | grep -E 'amdgpu|i915|nouveau|nvidia'

# For NVIDIA: proprietary driver requires GBM backend and specific env vars
export GBM_BACKEND=nvidia-drm
export __GLX_VENDOR_LIBRARY_NAME=nvidia
export WLR_NO_HARDWARE_CURSORS=1   # if cursor is invisible
```

### Screen tearing or flickering

```bash
# Force full-composition pipeline (Hyprland)
# In hyprland.conf:
misc {
    vfr = true          # variable frame rate — reduces idle power
    vrr = 1             # enable VRR on displays that support it
}

# For KWin: ensure compositor is not in "Suspend compositing" mode
qdbus org.kde.KWin /Compositor active   # should return true
qdbus org.kde.KWin /Compositor resume
```

### XWayland applications not launching

```bash
# Verify XWayland is installed
which Xwayland

# Check that the compositor started XWayland (look for DISPLAY=:0 or :1)
env | grep DISPLAY

# For Sway: XWayland is enabled by default; disable only if not needed:
# In config: xwayland disable

# For Hyprland: check hyprland log
cat /tmp/hypr/$(ls /tmp/hypr)/hyprland.log | grep -i xwayland
```

### Wayland-specific app rendering issues (blank windows, black screen)

```bash
# Force Electron apps to use Wayland backend
# Add to /usr/share/applications/code.desktop or ~/.local/share/applications/:
# Exec=code --ozone-platform=wayland --enable-features=WaylandWindowDecorations %F

# Force Qt apps
export QT_QPA_PLATFORM=wayland

# Force SDL apps
export SDL_VIDEODRIVER=wayland

# Firefox Wayland
export MOZ_ENABLE_WAYLAND=1

# Check which backend an app is using
# (for GTK apps, GDK_DEBUG=all is very verbose; filter for "wayland")
GDK_DEBUG=all gedit 2>&1 | grep -i 'backend\|wayland\|x11' | head -20
```

### Identifying which compositor is running

```bash
# Check WAYLAND_DISPLAY
echo $WAYLAND_DISPLAY   # e.g. wayland-1

# Compositor usually sets XDG_CURRENT_DESKTOP and/or DESKTOP_SESSION
echo $XDG_CURRENT_DESKTOP
echo $DESKTOP_SESSION

# Check compositor PID / name
pgrep -a 'sway\|Hyprland\|wayfire\|kwin_wayland\|niri\|river\|cage'
```

---

*See Chapter 7 (Sway Deep Dive) and Chapter 8 (Hyprland Deep Dive) for compositor-specific configuration detail. See Chapter 40 for IPC scripting patterns across all compositors. See Chapter 53 for display manager and session startup configuration.*

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
