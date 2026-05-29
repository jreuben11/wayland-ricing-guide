# Chapter 26 — Bars and Panels: Waybar, eww, AGS/Astal

## Overview

The status bar is one of the most visible components of any Linux desktop rice. It surfaces
system telemetry — CPU load, network state, volume, active workspaces — and links your compositor
session to everyday workflows. On Wayland, bars are first-class layer-shell clients: they anchor
to screen edges via the `wlr-layer-shell` protocol and never interfer with your window layout.

Before Quickshell dominated the scene (see Ch 27), three frameworks shaped the Wayland ricing
community: Waybar, eww, and AGS/Astal. Each has a distinct philosophy. Waybar offers a shallow
learning curve with a JSON + CSS configuration model that gets you a feature-complete bar in
under an hour. eww introduced a proper widget DSL (Yuck) with reactive data bindings years
before the competition. AGS/Astal brought TypeScript, GObject introspection, and a hot-reload
development loop to bar development, treating widgets as first-class software rather than
configuration files.

Understanding all three frameworks remains practically important even in 2025. Thousands of
community dotfiles target Waybar or eww. Compositors like Sway, labwc, and River have specific
Waybar modules. When you fork a dotfile, adapt a theme, or debug a colleague's setup, you will
encounter all three. This chapter gives you the depth to work confidently with each.

Cross-references: Ch 25 covers the `wlr-layer-shell` protocol that all these bars use. Ch 27
covers Quickshell, the QML-based successor. Ch 53 covers session startup, including how to
launch your bar from the compositor config or systemd user session.

---

## 26.1 Waybar — The Workhorse Bar

Waybar is the de-facto standard status bar for Sway, Hyprland, and most wlroots-based compositors.
It is written in C++ with a GTK3 rendering backend and exposes its configuration via a JSONC
(JSON with comments) file. The module system covers nearly every common use case out of the box:
clocks, workspaces, network, audio, Bluetooth, power profiles, media players via MPRIS, CPU
temperature, backlight, and more. Custom modules let you embed arbitrary shell-script output
when built-ins fall short.

Install Waybar from your distribution package manager or compile from source. On Arch Linux,
`waybar` is in the official repositories; `waybar-hyprland` used to be a separate AUR package
but upstream merged the Hyprland IPC workspace module years ago.

```bash
# Arch / Manjaro
sudo pacman -S waybar

# Fedora
sudo dnf install waybar

# Ubuntu 24.04+
sudo apt install waybar

# Build from source (for the latest git features)
git clone https://github.com/Alexays/Waybar.git
cd Waybar
meson setup build -Dexperimental=true
ninja -C build
sudo ninja -C build install
```

Waybar reads its configuration from `~/.config/waybar/config.jsonc` (or `config` without the
extension, or an XDG-compliant path passed via `--config`). The top-level structure is either a
single bar object or an array of bar objects for multi-bar setups.

```jsonc
// ~/.config/waybar/config.jsonc  — minimal single-bar config
{
    "layer": "top",           // wlr-layer-shell layer: top, bottom, overlay
    "position": "top",        // screen edge: top, bottom, left, right
    "height": 34,
    "spacing": 6,             // pixels between modules
    "modules-left":   ["hyprland/workspaces", "hyprland/window"],
    "modules-center": ["clock"],
    "modules-right":  ["pulseaudio", "network", "battery", "tray"],

    "hyprland/workspaces": {
        "format": "{icon}",
        "format-icons": {
            "1": "一", "2": "二", "3": "三",
            "active": "",
            "default": ""
        },
        "persistent-workspaces": {
            "*": 5    // show 5 workspaces on all monitors
        }
    },

    "clock": {
        "format": " {:%H:%M}",
        "format-alt": " {:%A, %B %d %Y}",
        "tooltip-format": "<big>{:%Y %B}</big>\n<tt><small>{calendar}</small></tt>"
    },

    "pulseaudio": {
        "format": "{icon}  {volume}%",
        "format-muted": "  muted",
        "format-icons": {
            "headphone": "",
            "default": ["", "", ""]
        },
        "on-click": "pavucontrol"
    },

    "network": {
        "format-wifi":     "  {essid} ({signalStrength}%)",
        "format-ethernet": "  {ipaddr}/{cidr}",
        "format-disconnected": "⚠  Disconnected",
        "tooltip-format": "{ifname}: {ipaddr}\nGateway: {gwaddr}\nUp: {bandwidthUpBytes}\nDown: {bandwidthDownBytes}"
    },

    "battery": {
        "states": { "warning": 30, "critical": 15 },
        "format": "{icon}  {capacity}%",
        "format-charging": "  {capacity}%",
        "format-plugged":  "  {capacity}%",
        "format-icons": ["", "", "", "", ""]
    },

    "tray": {
        "spacing": 10
    }
}
```

The `layer` field controls Z-order on the compositor. Use `"layer": "top"` to render above
normal windows, or `"layer": "bottom"` to render below them (useful for a desktop widget
strip). The `exclusive-zone` field (default: automatic) reserves screen space so windows do not
overlap the bar; set it to `-1` to disable exclusion if you want the bar to float over content.

Multiple bars are declared as a JSON array. Each object in the array can target a specific
monitor via the `"output"` field and use independent module sets:

```jsonc
// ~/.config/waybar/config.jsonc — multi-monitor / multi-bar
[
    {
        "output": "DP-1",
        "position": "top",
        "modules-left":   ["hyprland/workspaces"],
        "modules-center": ["clock"],
        "modules-right":  ["pulseaudio", "network", "battery", "tray"]
    },
    {
        "output": "HDMI-A-1",
        "position": "top",
        "modules-left":   ["hyprland/workspaces"],
        "modules-center": ["clock"],
        "modules-right":  ["cpu", "memory", "temperature"]
    }
]
```

### 26.1.1 Custom Modules

Custom modules execute an arbitrary shell command and display its stdout in the bar. They
support interval-based polling and signal-triggered updates. The output can be plain text or a
JSON object for rich formatting.

```jsonc
// In config.jsonc: add "custom/updates" to modules-right
"custom/updates": {
    "exec": "~/.config/waybar/scripts/updates.sh",
    "interval": 3600,           // poll every hour (seconds)
    "signal": 8,                // also trigger on SIGRTMIN+8
    "format": "  {}",
    "tooltip": true,
    "on-click": "kitty --hold yay -Syu"
}
```

```bash
#!/usr/bin/env bash
# ~/.config/waybar/scripts/updates.sh
# Outputs JSON for rich Waybar tooltip

count=$(yay -Qu 2>/dev/null | wc -l)
if [[ $count -gt 0 ]]; then
    echo "{\"text\": \"$count updates\", \"tooltip\": \"$(yay -Qu 2>/dev/null | tr '\n' '\\n')\"}"
else
    echo "{\"text\": \"\", \"tooltip\": \"System up to date\"}"
fi
```

Trigger a signal update from another script (e.g., after running an upgrade):

```bash
# Send SIGRTMIN+8 to all Waybar processes
pkill -SIGRTMIN+8 waybar
```

---

## 26.2 Waybar CSS Theming

Waybar renders with GTK3, which means its entire visual layer is controlled by CSS — the same
subset that GTK applications use. The stylesheet lives at `~/.config/waybar/style.css` by
default, or is specified via `--style`. GTK CSS is a restricted dialect: not every web-CSS
property is available, but `border-radius`, `box-shadow`, `transition`, `padding`, `margin`,
and CSS custom properties (variables) all work.

The widget hierarchy exposed to CSS mirrors the module names in your config. Key selectors:

```css
/* Overall bar window */
window#waybar { ... }

/* Named module containers */
#workspaces { ... }
#clock       { ... }
#pulseaudio  { ... }
#network     { ... }
#battery     { ... }
#tray        { ... }

/* Custom module (prefix #custom-) */
#custom-updates { ... }

/* Module groups (layout zones) */
.modules-left   { ... }
.modules-center { ... }
.modules-right  { ... }

/* State classes added by Waybar */
#battery.charging  { ... }
#battery.warning   { ... }
#battery.critical  { ... }
#network.disconnected { ... }
```

A complete Catppuccin Mocha theme that demonstrates CSS variables, pill-shaped module
backgrounds, and hover transitions:

```css
/* ~/.config/waybar/style.css — Catppuccin Mocha */

@define-color base   #1e1e2e;
@define-color mantle #181825;
@define-color crust  #11111b;
@define-color text   #cdd6f4;
@define-color subtext0 #a6adc8;
@define-color blue   #89b4fa;
@define-color green  #a6e3a1;
@define-color yellow #f9e2af;
@define-color red    #f38ba8;
@define-color mauve  #cba6f7;
@define-color peach  #fab387;
@define-color lavender #b4befe;

* {
    font-family: "JetBrainsMono Nerd Font", "Noto Sans", sans-serif;
    font-size: 13px;
    border: none;
    border-radius: 0;
    min-height: 0;
}

window#waybar {
    background-color: @base;
    color: @text;
    border-bottom: 2px solid @crust;
}

.modules-left, .modules-center, .modules-right {
    margin: 4px 6px;
}

/* Pill-shaped modules */
#workspaces,
#clock,
#pulseaudio,
#network,
#battery,
#cpu,
#memory,
#tray,
#custom-updates {
    background-color: @mantle;
    color: @text;
    padding: 2px 12px;
    border-radius: 20px;
    margin: 3px 3px;
    transition: all 0.2s ease;
}

#workspaces button {
    padding: 0 6px;
    color: @subtext0;
    background: transparent;
}

#workspaces button.active {
    color: @lavender;
    background-color: alpha(@lavender, 0.2);
    border-radius: 16px;
}

#workspaces button:hover {
    background: alpha(@blue, 0.2);
    border-radius: 16px;
    color: @blue;
}

#clock            { color: @blue; }
#pulseaudio       { color: @green; }
#network          { color: @mauve; }
#battery          { color: @yellow; }
#battery.charging { color: @green; }
#battery.warning:not(.charging) { color: @peach; }
#battery.critical:not(.charging) {
    color: @red;
    animation: blink 0.5s linear infinite alternate;
}
#custom-updates   { color: @peach; }

@keyframes blink {
    to { color: @base; background-color: @red; }
}
```

Hot-reloading Waybar after editing config or CSS:

```bash
# Send SIGUSR2 to reload style only (no restart)
pkill -SIGUSR2 waybar

# Full restart
pkill waybar && waybar &
```

You can also define a Hyprland keybind to reload Waybar:

```conf
# In hyprland.conf
bind = $mainMod SHIFT, B, exec, pkill waybar && waybar &
```

---

## 26.3 eww — Elkowar's Wacky Widgets

eww (Elkowar's Wacky Widgets) predates most Wayland widget frameworks and is the reason many
ricing dotfiles from 2021–2023 contain `.yuck` files. Its core insight was that a status bar is
just a set of small reactive programs: values come from shell commands, CSS applies presentation,
and a declarative widget tree assembles everything into a window. This model is more powerful
than Waybar's module system but requires more effort to configure.

eww's configuration language is Yuck, an S-expression DSL inspired by Lisp. All widgets,
windows, variables, and scripts are defined in `.yuck` files. CSS lives in a separate `.scss`
(SCSS, compiled internally) or `.css` file.

Install eww from source or the AUR:

```bash
# Arch AUR
yay -S eww-wayland

# From source (requires Rust toolchain)
git clone https://github.com/elkowarr/eww.git
cd eww
cargo build --release --no-default-features --features=wayland
install -Dm755 target/release/eww ~/.local/bin/eww
```

### 26.3.1 Yuck Fundamentals

```yuck
; ~/.config/eww/eww.yuck

; ── Variables ──────────────────────────────────────────────────────────
(defvar volume 50)   ; static variable (settable from CLI)

; ── Listeners (reactive shell output) ──────────────────────────────────
(deflisten workspaces
  :initial "[]"
  `hyprctl workspaces -j | jq '[.[] | {id, name, windows}]'`)

(deflisten active-workspace
  :initial "{}"
  `socat -u UNIX-CONNECT:$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock - \
   | stdbuf -o0 grep -E '^workspace>>' \
   | stdbuf -o0 sed 's/workspace>>//' \
   | xargs -I{} hyprctl activeworkspace -j`)

(deflisten volume-listener
  :initial "50"
  `pactl subscribe | grep --line-buffered "sink" | \
   xargs -I{} pactl get-sink-volume @DEFAULT_SINK@ | \
   grep -oP '\d+(?=%)' | head -1`)

; ── Widget Definitions ─────────────────────────────────────────────────
(defwidget workspace-btn [ws]
  (button
    :class {ws.id == (active-workspace.id ?: 0) ? "workspace active" : "workspace"}
    :onclick "hyprctl dispatch workspace ${ws.id}"
    "${ws.name ?: ws.id}"))

(defwidget workspaces-widget []
  (box
    :class "workspaces"
    :orientation "h"
    :spacing 4
    (for ws in workspaces
      (workspace-btn :ws ws))))

(defwidget clock-widget []
  (box
    :class "clock"
    :orientation "h"
    :spacing 6
    (label :text "" :class "icon")
    (label :text {formattime(EWW_TIME, "%H:%M")} :class "time")
    (label :text {formattime(EWW_TIME, "%a %b %d")} :class "date")))

(defwidget volume-widget []
  (box
    :class "volume"
    :orientation "h"
    :spacing 4
    (label :text "" :class "icon")
    (scale
      :class "vol-slider"
      :min 0
      :max 100
      :value volume-listener
      :onchange "pactl set-sink-volume @DEFAULT_SINK@ {}%")))

(defwidget bar-left []
  (box :orientation "h" :space-evenly false
    (workspaces-widget)))

(defwidget bar-center []
  (box :orientation "h" :space-evenly false
    (clock-widget)))

(defwidget bar-right []
  (box :orientation "h" :space-evenly false
    (volume-widget)
    (systray :class "tray" :icon-size 20 :spacing 8)))

(defwidget bar []
  (centerbox :orientation "h"
    (bar-left)
    (bar-center)
    (bar-right)))

; ── Window Definition ──────────────────────────────────────────────────
(defwindow bar
  :monitor 0
  :geometry (geometry
    :x "0%"
    :y "0%"
    :width "100%"
    :height "34px"
    :anchor "top center")
  :stacking "fg"
  :exclusive true
  :focusable false
  (bar))
```

```scss
/* ~/.config/eww/eww.scss */
$base:   #1e1e2e;
$text:   #cdd6f4;
$blue:   #89b4fa;
$green:  #a6e3a1;
$mauve:  #cba6f7;

.bar-window {
  background: $base;
  color: $text;
  font-family: "JetBrainsMono Nerd Font";
  font-size: 13px;
}

.workspaces {
  margin: 0 8px;
  .workspace {
    padding: 2px 8px;
    border-radius: 6px;
    background: transparent;
    color: lighten($text, 20%);
    &.active { background: alpha($blue, 0.25); color: $blue; }
  }
}

.clock { color: $blue; margin: 0 12px; }
.volume { color: $green; margin: 0 8px; }
```

Interact with eww from the command line:

```bash
# Open / close windows
eww open bar
eww close bar

# Update a variable
eww update volume=75

# Inspect widget state
eww state

# Reload config (no restart needed for yuck changes)
eww reload

# Kill the daemon
eww kill
```

eww remains an excellent choice for sidebars, dashboard overlays, and desktop widgets that
live outside the strict bar paradigm. Its `deflisten` model lets you build reactive UIs backed
by any Unix command that streams output. However, its development pace has slowed, and most new
projects favour AGS/Astal or Quickshell for similar functionality with better tooling support.

---

## 26.4 AGS / Astal — TypeScript Widgets

AGS (Aylur's GTK Shell) launched the idea of writing Wayland widgets in TypeScript with full
LSP support, hot-reload, and access to system daemons through typed GObject introspection
bindings. AGS v1 used GJS (GNOME JavaScript) directly. Astal (sometimes called AGS v2) is a
complete ground-up rewrite that separates the library layer (Astal) from the shell runner,
supports multiple languages (TypeScript, Lua, Python, Vala), and ships purpose-built libraries
for Hyprland IPC, Niri, MPRIS, networking, Bluetooth, power profiles, and more.

Install `astal` and the `ags` CLI:

```bash
# Arch AUR
yay -S astal-git ags

# Nix (Nixpkgs unstable / home-manager)
# Add to home.packages:
# pkgs.ags

# From source
git clone https://github.com/aylur/astal.git
cd astal
# Follow the per-language instructions in the repo README
```

### 26.4.1 A Minimal Astal Bar in TypeScript

A full Astal project has a `package.json`, `tsconfig.json`, and one or more `.tsx` source files.
The `ags` CLI compiles and runs the project.

```bash
# Scaffold a new project
ags init my-bar
cd my-bar
```

```typescript
// app.ts — entry point
import { App } from "astal/gtk3"
import Bar from "./widget/Bar"

App.start({
    main() {
        App.get_monitors().map(Bar)
    },
})
```

```typescript
// widget/Bar.tsx
import { App, Astal, Gtk, Gdk } from "astal/gtk3"
import { bind } from "astal"
import Hyprland from "gi://AstalHyprland"
import Mpris from "gi://AstalMpris"
import Network from "gi://AstalNetwork"
import Battery from "gi://AstalBattery"
import Wp from "gi://AstalWp"           // WirePlumber

const hypr    = Hyprland.get_default()
const network = Network.get_default()
const battery = Battery.get_default()
const audio   = Wp.get_default()

// ── Workspaces ──────────────────────────────────────────────────────────
function Workspaces() {
    return (
        <box class="workspaces" spacing={4}>
            {bind(hypr, "workspaces").as(wss =>
                wss.sort((a, b) => a.id - b.id).map(ws => (
                    <button
                        class={bind(hypr, "focusedWorkspace").as(fw =>
                            ws === fw ? "workspace active" : "workspace"
                        )}
                        onClicked={() => ws.focus()}
                    >
                        {ws.id}
                    </button>
                ))
            )}
        </box>
    )
}

// ── Clock ───────────────────────────────────────────────────────────────
function Clock() {
    const time = Variable<string>("").poll(1000, "date +'%H:%M'")
    return <label class="clock" label={bind(time)} />
}

// ── Network ─────────────────────────────────────────────────────────────
function NetworkIndicator() {
    return (
        <box class="network" spacing={4}>
            <icon icon={bind(network, "primary").as(p =>
                p === Network.Primary.WIFI
                    ? network.wifi?.iconName ?? "network-offline-symbolic"
                    : "network-wired-symbolic"
            )} />
        </box>
    )
}

// ── Volume ──────────────────────────────────────────────────────────────
function Volume() {
    const speaker = audio?.audio?.defaultSpeaker
    if (!speaker) return <box />
    return (
        <box class="volume" spacing={4}>
            <icon icon={bind(speaker, "volumeIcon")} />
            <label label={bind(speaker, "volume").as(v => `${Math.round(v * 100)}%`)} />
        </box>
    )
}

// ── Battery ─────────────────────────────────────────────────────────────
function BatteryIndicator() {
    if (!battery.isPresent) return <box />
    return (
        <box class="battery" spacing={4}>
            <icon icon={bind(battery, "batteryIconName")} />
            <label label={bind(battery, "percentage").as(p => `${Math.round(p * 100)}%`)} />
        </box>
    )
}

// ── Bar ─────────────────────────────────────────────────────────────────
export default function Bar(monitor: Gdk.Monitor) {
    const { TOP, LEFT, RIGHT } = Astal.WindowAnchor
    return (
        <window
            class="Bar"
            gdkmonitor={monitor}
            exclusivity={Astal.Exclusivity.EXCLUSIVE}
            anchor={TOP | LEFT | RIGHT}
            application={App}
        >
            <centerbox>
                <box hexpand halign={Gtk.Align.START}>
                    <Workspaces />
                </box>
                <box>
                    <Clock />
                </box>
                <box hexpand halign={Gtk.Align.END} spacing={8}>
                    <NetworkIndicator />
                    <Volume />
                    <BatteryIndicator />
                </box>
            </centerbox>
        </window>
    )
}
```

```scss
/* style.scss */
$base:   #1e1e2e;
$text:   #cdd6f4;
$blue:   #89b4fa;
$green:  #a6e3a1;
$mauve:  #cba6f7;
$yellow: #f9e2af;

.Bar {
    background-color: $base;
    color: $text;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 13px;
    border-bottom: 2px solid darken($base, 5%);
}

.workspace {
    padding: 2px 10px;
    border-radius: 14px;
    background: transparent;
    color: lighten($text, 15%);

    &.active {
        background: alpha($blue, 0.25);
        color: $blue;
    }
}

.clock   { color: $blue;   margin: 0 12px; }
.network { color: $mauve;  margin: 0 4px; }
.volume  { color: $green;  margin: 0 4px; }
.battery { color: $yellow; margin: 0 4px; }
```

Run and develop with hot reload:

```bash
# Run the bar (hot-reload on save)
ags run .

# Type-check only
ags check .

# Bundle to a single .js for production
ags bundle app.ts output.js
```

### 26.4.2 Astal Libraries Reference

| Library import | Purpose | Key bindings |
|---|---|---|
| `gi://AstalHyprland` | Hyprland IPC | workspaces, clients, focused window |
| `gi://AstalNiri` | Niri IPC | workspaces, windows |
| `gi://AstalMpris` | MPRIS media | player, trackTitle, playbackStatus |
| `gi://AstalNetwork` | NetworkManager | wifi, wired, primary |
| `gi://AstalBluetooth` | BlueZ | devices, connected |
| `gi://AstalBattery` | UPower | percentage, charging, isPresent |
| `gi://AstalWp` | WirePlumber | defaultSpeaker, defaultMicrophone |
| `gi://AstalTray` | StatusNotifier | tray items |
| `gi://AstalPowerProfiles` | power-profiles-daemon | activeProfile |

---

## 26.5 Choosing Your Bar Framework in 2025/2026

The right bar framework depends on how much time you want to invest versus how much control you
need. Waybar wins on accessibility: the JSON + CSS model maps closely to what most desktop users
already understand, the module library covers 95% of use cases, and community themes (Catppuccin,
Tokyo Night, Nord, Dracula) are available for immediate import. If you just want a beautiful bar
working tonight, Waybar is the answer.

eww is the right pick when you need a widget that does not fit the bar paradigm at all: an
overlay dashboard, a desktop-bound widget grid, or a sidebar that pops in from the screen edge.
Its `deflisten` reactive model is genuinely powerful. The downside is the Yuck syntax, which has
no LSP support and can become hard to read in large configs. For new projects the Astal sidebars
libraries fill the same niche with far better tooling.

AGS/Astal is the choice for TypeScript developers who want their bar to feel like a maintained
software project: type checking, LSP autocomplete, modular component files, unit-testable helper
functions, and hot reload. The Astal libraries give you typed bindings to every system daemon
rather than raw shell-script parsing. The trade-off is a build toolchain dependency (Node/Deno)
and a steeper initial scaffolding step.

Quickshell (Ch 27) represents the current frontier: Qt Quick / QML rendering, the best
Wayland protocol coverage, true GPU-accelerated animations, and per-screen shader effects. If
your bar needs smooth animations, video backgrounds, or blur effects that GTK3 cannot provide,
Quickshell is the path forward.

| | Waybar | eww | AGS/Astal | Quickshell |
|---|---|---|---|---|
| Config language | JSON + CSS | Yuck + CSS | TypeScript + SCSS | QML + JS |
| Learning curve | Low | Medium | Medium | Medium |
| Programmability | Low | High | High | Highest |
| Hot reload | No (SIGUSR2 for CSS) | Yes | Yes | Yes |
| LSP / type safety | Limited | None | Full (TypeScript) | Yes (QML) |
| Wayland protocols | Good | Good | Good | Best |
| Compositor IPC | Good | Via shell script | Native typed | Native typed |
| Rendering backend | GTK3 | GTK3 | GTK3 / GTK4 | Qt Quick |
| GPU animations | No | No | Limited | Yes |
| Community themes | Vast | Moderate | Growing | Emerging |
| Active development | Maintained | Slow | Active | Very active |

**Verdict 2025/2026**: Use Quickshell for new projects targeting Hyprland or Niri when you want
animations and shader effects. Use Waybar when you need a bar working in ten minutes or when
supporting Sway-first setups. Use AGS/Astal when you are a TypeScript developer who wants typed
daemon bindings. Keep eww in your toolkit for non-bar overlay widgets.

---

## 26.6 Integrating Bars with Compositor Startup

Bars should be launched as part of your compositor session, not as standalone systemd services,
because they require `WAYLAND_DISPLAY` to be set and the compositor to be ready before they can
connect to the layer-shell protocol. The two common approaches are: launching from the compositor
config, or registering with `systemd --user` after the graphical target.

### 26.6.1 Launching from Hyprland

```conf
# ~/.config/hypr/hyprland.conf
exec-once = waybar
# or
exec-once = ags run ~/.config/ags
# or
exec-once = eww open bar
```

`exec-once` runs the command once at startup. Use `exec` if you want the command to re-run on
config reload. For a restart keybind:

```conf
bind = $mainMod SHIFT, B, exec, pkill waybar; waybar &
```

### 26.6.2 systemd User Session (for compositor-agnostic setups)

```ini
# ~/.config/systemd/user/waybar.service
[Unit]
Description=Waybar status bar
PartOf=graphical-session.target
After=graphical-session.target
ConditionEnvironment=WAYLAND_DISPLAY

[Service]
ExecStart=/usr/bin/waybar
Restart=on-failure
RestartSec=3

[Install]
WantedBy=graphical-session.target
```

```bash
systemctl --user enable waybar.service
# Start immediately after compositor is up:
systemctl --user start waybar.service
```

See Ch 53 for a full treatment of systemd user session integration and environment variable
propagation from the compositor.

---

## Troubleshooting

**Waybar does not appear after startup**
Confirm `WAYLAND_DISPLAY` is set in the environment where Waybar is launched. Check
`journalctl --user -u waybar` or run `waybar` from a terminal to see error output.
Common cause: bar launched before compositor is ready; add a short `sleep 0.5 &&` prefix or
use `exec-once` instead of shell background `&`.

**Waybar CSS changes have no effect**
Run `pkill -SIGUSR2 waybar` to reload the stylesheet without restarting. If that has no effect,
check that Waybar found the correct style file: `waybar --style ~/.config/waybar/style.css`.

**Workspace module shows empty / wrong workspaces**
For Hyprland, confirm you have the `hyprland/workspaces` module (not `wlr/workspaces`, which
was deprecated). Check `hyprctl workspaces` returns data. If using persistent-workspaces, ensure
the number matches what your config creates.

**eww `deflisten` not updating**
Test the shell command in isolation: paste the `exec` string into a terminal and confirm it
streams line-by-line output. eww's `deflisten` reads one JSON value per line. If your script
buffers output, add `stdbuf -o0` before the command or use `unbuffer` from the `expect` package.

**eww window not appearing on Wayland**
Confirm you compiled eww with `--features=wayland` (not the X11-only default). Run `eww logs`
to view daemon output. Check that `exclusive` and `stacking` are set correctly in `defwindow`.

**AGS / Astal: TypeScript errors on AstalHyprland bindings**
Make sure the `astal-hyprland` native library is installed (separate from the `astal` core).
On Arch: `yay -S astal-hyprland-git`. Regenerate GObject introspection types: `ags check .`

**AGS hot reload not triggering**
AGS watches files in the project directory. If your editor writes files atomically (via a
temporary file + rename), inotify may miss the event. Switch to `ags run . --watch` and confirm
your editor's write mode, or add `--poll` to the watch flag.

**Bar overlaps windows / does not reserve space**
Check that `exclusive-zone` is not set to `-1` in Waybar config, or that `exclusive: true` is
set in eww's `defwindow` / Astal's `<window exclusivity={Astal.Exclusivity.EXCLUSIVE}>`. Confirm
the compositor respects `wlr-layer-shell` exclusive zones (all wlroots compositors do; Mutter
does not unless using a GNOME Shell extension).

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
