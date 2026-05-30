# Chapter 108 — eww Deep Dive: Yuck Language, State Model, and Desktop Widgets

## Overview

eww (Elkowar's Wacky Widgets) introduced a fundamentally different model for shell widgets in 2021: instead of a config-file-driven bar with a fixed set of modules, eww is a general-purpose widget runtime. You define *any* window shape — a status bar, a floating calendar, a full-screen dashboard, a corner clock — in a Lisp-flavoured DSL called Yuck, back it with reactive data from shell commands, and style it with CSS/SCSS. That model predated AGS, Quickshell, and Astal by years, and it explains why a large fraction of the ricing community's dotfiles still contain `.yuck` files.

Chapter 26 gave eww a section focused on bars. This chapter goes deeper: the full Yuck type system and expression language, all variable kinds (`defvar`, `deflisten`, `defpoll`), the magic built-in variables, advanced widget composition, desktop overlays that are not bars, multi-monitor workflows, SCSS variables that talk to pywal/matugen output, and a set of non-trivial real-world widget examples.

**Cross-references:** Ch 26 covers the eww installation and a minimal bar as a starting point. Ch 38 covers pywal/matugen colour extraction that feeds into §108.7. Ch 88 covers Hyprland IPC — the primary data source for workspace and window state fed via `deflisten`. Ch 59 covers desktop widget placement philosophy.

---

## 108.1 Architecture: How eww Works

eww runs as a background daemon (`eww daemon`) that:

1. Parses all `.yuck` files in `~/.config/eww/` (or `--config` path)
2. Spawns listener and poll processes for `deflisten`/`defpoll` variables
3. Exposes a Unix socket for CLI control (`eww open`, `eww update`, `eww state`)
4. Renders windows using GTK4 (eww ≥ 0.6) with a custom widget set

Each `defwindow` declaration maps to a GTK window that the daemon creates on demand. The window's layer-shell type, anchor, and exclusive zone are set at definition time and cannot change at runtime (they are protocol-level properties). The *content* of the window — every widget tree and every variable value — is fully reactive: changing a variable rerenders only the affected parts of the widget tree.

```
eww daemon
  ├── deflisten: hyprctl events → workspaces var
  ├── defpoll: date +%H:%M → clock var (every 5s)
  ├── GTK window: "bar" (layer-shell: top, exclusive)
  └── GTK window: "sidebar" (layer-shell: overlay, non-exclusive)
```

### Installing eww

```bash
# Arch AUR (prebuilt Wayland binary)
yay -S eww-wayland

# From source (Wayland feature flag required for layer-shell)
git clone https://github.com/elkowar/eww.git
cd eww
cargo build --release --no-default-features --features=wayland
install -Dm755 target/release/eww ~/.local/bin/eww

# Verify
eww --version   # → eww - ElKowar's Wacky Widgets 0.6.x
```

---

## 108.2 Yuck Language Fundamentals

Yuck is a Lisp-1 dialect: everything is an S-expression, atoms are unquoted strings, and lists are parenthesised. There is no compile step — the daemon interprets `.yuck` files directly.

### Comments and File Organisation

```yuck
; Single-line comments use semicolons.
; There are no block comments.

; Convention: split large configs into multiple files and include them:
(include "./windows/bar.yuck")
(include "./windows/sidebar.yuck")
(include "./widgets/workspaces.yuck")
(include "./widgets/system.yuck")
```

### Literals and Types

| Value | Yuck syntax | Notes |
|---|---|---|
| String | `"hello"` or `hello` (bare) | Bare strings are fine unless they contain spaces |
| Number | `42`, `3.14` | Integers and floats |
| Boolean | `true`, `false` | Used in `:visible`, `:sensitive` |
| JSON | `{key: val}`, `[a, b]` | `deflisten` typically produces JSON |
| Expression | `{...}` | Curly braces evaluate Yuck expressions |

### Expressions `{...}`

Curly-brace blocks are evaluated as Yuck expressions. Inside them you have:

```yuck
; Arithmetic
{volume * 2}
{battery_percentage / 100}

; String interpolation
{"Battery: ${battery_percentage}%"}

; Ternary
{volume > 0 ? "󰕾" : "󰝟"}

; Nested ternary (volume icon by level)
{volume >= 70 ? "󰕾" : volume >= 30 ? "󰖀" : volume > 0 ? "󰕿" : "󰝟"}

; JSON field access (dot notation)
{active_window.title}
{workspaces[0].name}

; Built-in functions
{formattime(EWW_TIME, "%H:%M")}
{round(cpu_usage, 1)}
{arraylength(workspaces)}
{string(some_number)}
{matches(window_title, ".*Firefox.*")}
```

### Built-in Functions Reference

| Function | Signature | Description |
|---|---|---|
| `formattime` | `(timestamp, format)` | Format a Unix timestamp using `strftime` patterns |
| `round` | `(number, decimals)` | Round to N decimal places |
| `floor` | `(number)` | Integer floor |
| `ceil` | `(number)` | Integer ceiling |
| `abs` | `(number)` | Absolute value |
| `min` / `max` | `(a, b)` | Minimum / maximum of two numbers |
| `arraylength` | `(array)` | Length of a JSON array |
| `matches` | `(string, regex)` | True if string matches regex |
| `replace` | `(string, regex, replacement)` | Regex replace |
| `search` | `(string, regex)` | Return first match group |
| `string` | `(value)` | Convert to string |
| `number` | `(value)` | Convert to number |
| `jq` | `(json, query)` | Apply a jq expression inline |
| `strlength` | `(string)` | String length |
| `substring` | `(string, start, end)` | Extract substring |
| `uppercase` / `lowercase` | `(string)` | Case conversion |

---

## 108.3 Variable Kinds

eww has three distinct ways to bring data into a Yuck config. Choosing correctly matters for performance and correctness.

### `defvar` — Static Mutable Variable

`defvar` declares a variable with a default value. It can be updated from the CLI (`eww update`) or from `:onchange` callbacks. It does *not* automatically change — it is the "manual toggle" primitive.

```yuck
; Sidebar open/closed state
(defvar sidebar-open false)

; Current active theme name
(defvar current-theme "catppuccin-mocha")

; User-adjustable clock format
(defvar clock-format "%H:%M")
```

Update from shell:
```bash
eww update sidebar-open=true
eww update current-theme=catppuccin-latte
```

Use in widgets:
```yuck
(defwidget sidebar []
  (box
    :class "sidebar"
    :visible sidebar-open
    (sidebar-content)))
```

### `deflisten` — Streaming Shell Command

`deflisten` subscribes to the *stdout* of a long-running shell command. Every line of output becomes the new variable value. This is the right tool for event-driven data: Hyprland IPC events, `pactl subscribe`, `inotifywait`, D-Bus `monitor` output.

```yuck
; Hyprland workspaces — refreshes on every workspace event
(deflisten workspaces
  :initial "[]"
  `hyprctl workspaces -j | jq '[.[] | {id, name, windows, monitor}]'`)

; Active workspace
(deflisten active-ws
  :initial "{}"
  `socat -u UNIX-CONNECT:$HYPRLAND_SOCKET2 - \
   | grep --line-buffered "^workspace>>" \
   | sed 's/workspace>>//' \
   | xargs -I{} hyprctl activeworkspace -j`)

; Active window title (Hyprland IPC)
(deflisten active-window
  :initial "{\"title\": \"\", \"class\": \"\"}"
  `socat -u UNIX-CONNECT:$HYPRLAND_SOCKET2 - \
   | grep --line-buffered "activewindow>>" \
   | sed 's/activewindow>>//' \
   | while IFS=',' read -r class title; do
       printf '{"class":"%s","title":"%s"}\n' "$class" "$title"
     done`)

; PulseAudio / PipeWire volume
(deflisten volume
  :initial "50"
  `pactl subscribe \
   | grep --line-buffered "'change' on sink" \
   | xargs -I{} sh -c \
       'pactl get-sink-volume @DEFAULT_SINK@ | grep -oP "\\d+(?=%)" | head -1'`)
```

The `:initial` value is used while the first output line has not yet been produced. It must be valid JSON if your widgets parse the value as JSON.

The shell command runs as a long-lived process. If it exits, eww restarts it after a short delay — do not add infinite loops manually; eww's restart logic is the loop.

### `defpoll` — Polling Shell Command

`defpoll` runs a shell command on a fixed interval and takes the *exit output* as the variable value. Use it for data that changes predictably over time: clock, date, battery percentage, CPU temperature.

```yuck
; Clock — updates every second
(defpoll clock
  :interval "1s"
  :initial "00:00"
  `date +%H:%M`)

; Date — updates every minute is sufficient
(defpoll date-str
  :interval "60s"
  :initial "Mon 01 Jan"
  `date "+%a %d %b"`)

; Battery — updates every 30 seconds
(defpoll battery
  :interval "30s"
  :initial "{\"percent\": 100, \"status\": \"Discharging\"}"
  `cat /sys/class/power_supply/BAT0/capacity | \
   xargs -I{} sh -c \
     'STATUS=$(cat /sys/class/power_supply/BAT0/status); \
      echo "{\"percent\": {}, \"status\": \"$STATUS\"}"'`)

; CPU usage — top one-shot, every 3 seconds
(defpoll cpu-usage
  :interval "3s"
  :initial "0.0"
  `top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d. -f1`)

; RAM usage in MB
(defpoll ram-used
  :interval "5s"
  :initial "0"
  `free -m | awk '/^Mem:/{print $3}'`)
```

| Aspect | `deflisten` | `defpoll` |
|---|---|---|
| Trigger | Event-driven (stdout lines) | Time-based (fixed interval) |
| Process lifetime | Long-running daemon | Spawned and killed each interval |
| Overhead | One persistent process | One process per interval |
| Best for | IPC events, D-Bus, `inotifywait` | Clock, battery, CPU, temperature |
| Latency | Instant (event fires update) | Up to one full interval |

### Magic Variables

eww provides a set of built-in variables that are always available without any `deflisten`/`defpoll` declaration. They refresh automatically.

| Variable | Type | Description |
|---|---|---|
| `EWW_TIME` | Unix timestamp | Current time (use with `formattime`) |
| `EWW_BATTERY` | JSON map | Battery info per device: `EWW_BATTERY.BAT0.capacity`, `.status` |
| `EWW_RAM` | JSON | `total_mem`, `used_mem`, `available_mem`, `free_mem` (bytes) |
| `EWW_CPU` | JSON array | Per-core usage: `EWW_CPU[0].usage` |
| `EWW_DISK` | JSON map | Per-mountpoint disk info: `EWW_DISK["/"].used_perc` |
| `EWW_NET` | JSON map | Per-interface network: `EWW_NET.eth0.NET_UP`, `.NET_DOWN` |
| `EWW_MONITORS` | JSON array | Monitor list: `.name`, `.width`, `.height`, `.x`, `.y` |
| `EWW_WORKSPACES` | JSON array | Workspace list (compositor-agnostic) |
| `EWW_ACTIVE_WINDOWS` | JSON map | Active window per monitor |

```yuck
; Use magic variables directly — no defpoll needed
(defwidget ram-widget []
  (box :class "ram"
    (label :text {"RAM: ${round(EWW_RAM.used_mem / 1073741824, 1)}G"})
    (levelbar
      :value {EWW_RAM.used_mem / EWW_RAM.total_mem * 100}
      :min 0 :max 100)))

(defwidget cpu-widget []
  (box :class "cpu"
    (label :text {"CPU: ${round(EWW_CPU[0].usage, 0)}%"})))
```

---

## 108.4 Window Definitions

`defwindow` is where you declare the GTK/layer-shell properties of a window. These properties are set once when the window opens and cannot change while it is open.

```yuck
(defwindow bar
  :monitor 0                     ; 0-indexed monitor (or monitor name string)
  :geometry (geometry
    :x "0%"                      ; position: percentage or pixel value
    :y "0px"
    :width "100%"                ; size: percentage fills the monitor width
    :height "36px"
    :anchor "top center")        ; anchor point: "top left/center/right", "bottom ...", "center"
  :stacking "fg"                 ; "fg" (top) | "bg" (below windows) | "overlay"
  :exclusive true                ; reserve space (exclusive zone)
  :focusable false               ; do not accept keyboard focus
  (bar-widget))
```

```yuck
; Sidebar: anchored right, full height, not exclusive
(defwindow sidebar
  :monitor 0
  :geometry (geometry
    :x "0px"
    :y "0px"
    :width "340px"
    :height "100%"
    :anchor "right center")
  :stacking "overlay"
  :exclusive false
  :focusable true
  (sidebar-widget))
```

```yuck
; Desktop background widget (behind all windows)
(defwindow desktop-clock
  :monitor 0
  :geometry (geometry
    :x "20px"
    :y "20px"
    :width "280px"
    :height "120px"
    :anchor "bottom left")
  :stacking "bg"                 ; rendered below all windows
  :exclusive false
  :focusable false
  (desktop-clock-widget))
```

```yuck
; Full-screen dashboard
(defwindow dashboard
  :monitor 0
  :geometry (geometry
    :width "100%"
    :height "100%"
    :anchor "center")
  :stacking "overlay"
  :exclusive false
  :focusable true
  :visible dashboard-open        ; controlled by a defvar
  (dashboard-widget))
```

---

## 108.5 Core Widget Reference

### Layout Widgets

```yuck
; box — the primary layout container
(box
  :orientation "h"              ; "h" (horizontal) | "v" (vertical)
  :space-evenly true            ; distribute children equally
  :spacing 8                    ; gap in pixels between children
  :halign "start"               ; "start" | "center" | "end" | "fill"
  :valign "center"
  :class "mybox"
  child1 child2 child3)

; centerbox — left | center | right in one widget
(centerbox
  :orientation "h"
  left-widget center-widget right-widget)

; scroll — scrollable container
(scroll
  :vscroll true
  :hscroll false
  :height 200
  inner-content)
```

### Display Widgets

```yuck
; label — text display
(label
  :text "Hello"
  :class "my-label"
  :justify "center"             ; "left" | "center" | "right"
  :ellipsize "end"              ; truncate long text
  :wrap false)

; image — render an image file or icon name
(image
  :path "/path/to/image.png"
  :image-width 24
  :image-height 24)

; icon — GTK named icon
(image
  :path "audio-volume-high"    ; named icons also work via :path on GTK icon theme

; circular-progress — ring-style progress indicator
(circular-progress
  :value cpu-usage
  :min 0 :max 100
  :thickness 4
  :class "cpu-ring"
  (label :text "${round(cpu-usage, 0)}%"))

; levelbar — horizontal/vertical filled bar
(levelbar
  :value battery-pct
  :min 0 :max 100
  :orientation "h"
  :class "battery-bar")

; graph — scrolling line graph
(graph
  :value cpu-usage
  :time-range 60                ; seconds of history
  :min 0 :max 100
  :thickness 2
  :class "cpu-graph")
```

### Interactive Widgets

```yuck
; button
(button
  :class "btn"
  :onclick "eww update sidebar-open=${!sidebar-open}"
  :onrightclick "foot"
  :tooltip "Open sidebar"
  "󰭎 Open")

; scale — slider
(scale
  :min 0 :max 100
  :value volume
  :orientation "h"
  :onchange "pactl set-sink-volume @DEFAULT_SINK@ {}%"
  :class "vol-slider")

; input — text input field
(input
  :class "search-input"
  :placeholder "Search..."
  :onaccept "do-search {}")

; checkbox
(checkbox
  :checked sidebar-open
  :onchecked "eww update sidebar-open=true"
  :onunchecked "eww update sidebar-open=false")

; combo-box-text
(combo-box-text
  :active current-theme
  :onchange "eww update current-theme={}"
  (list-box-row :value "catppuccin-mocha" "Catppuccin Mocha")
  (list-box-row :value "catppuccin-latte" "Catppuccin Latte")
  (list-box-row :value "gruvbox-dark"     "Gruvbox Dark"))
```

### Conditional Rendering

```yuck
; if/else
(if condition
  (then-widget)
  (else-widget))   ; else is optional

; Examples
(if {battery.status == "Charging"}
  (label :text "󰂄 Charging")
  (label :text {"󰁹 ${battery.percent}%"}))
```

### Iteration

```yuck
; for — iterate over a JSON array
(for ws in workspaces
  (workspace-button :workspace ws))

; Dynamic list from a variable
(for app in {jq(running-apps, "[.[]|{name,icon}]")}
  (taskbar-item :app app))
```

### Transitions and Reveal

```yuck
; revealer — animate widget visibility
(revealer
  :reveal sidebar-open
  :transition "slideright"     ; "slideright" | "slideleft" | "slideup" | "slidedown" | "crossfade" | "none"
  :duration "250ms"
  (sidebar-content))
```

---

## 108.6 Real-World Widget Examples

### Workspace Switcher (Hyprland)

```yuck
(deflisten workspaces
  :initial "[]"
  `hyprctl workspaces -j | jq '[.[]|{id,name,windows}]|sort_by(.id)'`)

(deflisten active-ws-id
  :initial "1"
  `socat -u UNIX-CONNECT:"$HYPRLAND_SOCKET2" - \
   | grep --line-buffered '^workspace>>' \
   | sed 's/^workspace>>//' \
   | xargs -I{} hyprctl activeworkspace -j \
   | jq -r '.id'`)

(defwidget ws-btn [ws]
  (button
    :class {ws.id == number(active-ws-id) ? "ws active" : "ws"}
    :onclick "hyprctl dispatch workspace ${ws.id}"
    :tooltip {ws.windows > 0 ? "${ws.windows} windows" : "empty"}
    {ws.name != "" ? ws.name : ws.id}))

(defwidget workspaces []
  (box :class "workspaces" :spacing 4 :orientation "h"
    (for ws in workspaces
      (ws-btn :ws ws))))
```

```scss
.workspaces {
  margin: 0 8px;
  .ws {
    min-width: 28px;
    padding: 2px 6px;
    border-radius: 6px;
    background: transparent;
    color: alpha(@text, 0.5);
    font-size: 13px;
    transition: all 150ms ease;

    &.active {
      background: alpha(@blue, 0.25);
      color: @blue;
      font-weight: bold;
    }

    &:hover {
      background: alpha(@surface1, 0.5);
      color: @text;
    }
  }
}
```

### System Monitor Panel (Not a Bar)

```yuck
(defwindow sysmon
  :monitor 0
  :geometry (geometry :width "260px" :height "400px" :anchor "bottom right"
                       :x "12px" :y "48px")
  :stacking "overlay"
  :focusable false
  :visible sysmon-open
  (sysmon-widget))

(defwidget sysmon-widget []
  (box :class "sysmon" :orientation "v" :spacing 12
    ; CPU
    (box :class "section" :orientation "v" :spacing 4
      (label :class "title" :text "CPU" :halign "start")
      (box :orientation "h" :spacing 8
        (circular-progress :value {EWW_CPU[0].usage} :min 0 :max 100
                           :thickness 5 :class "cpu-ring"
          (label :text {"${round(EWW_CPU[0].usage,0)}%"}))
        (box :orientation "v" :spacing 2
          (for core in EWW_CPU
            (levelbar :value {core.usage} :min 0 :max 100
                      :class {core.usage > 80 ? "core hot" : "core"})))))
    ; RAM
    (box :class "section" :orientation "v" :spacing 4
      (label :class "title" :text "Memory" :halign "start")
      (levelbar :value {EWW_RAM.used_mem / EWW_RAM.total_mem * 100}
                :min 0 :max 100 :class "ram-bar")
      (label :text {"${round(EWW_RAM.used_mem/1073741824,1)} / ${round(EWW_RAM.total_mem/1073741824,1)} GB"}
             :class "small"))
    ; Disk
    (box :class "section" :orientation "v" :spacing 4
      (label :class "title" :text "Disk (/)" :halign "start")
      (levelbar :value {EWW_DISK["/"].used_perc} :min 0 :max 100 :class "disk-bar")
      (label :text {"${EWW_DISK['/'].used} / ${EWW_DISK['/'].total}"}
             :class "small"))
    ; Network
    (box :class "section" :orientation "v" :spacing 4
      (label :class "title" :text "Network" :halign "start")
      (box :orientation "h" :spacing 8
        (label :text {"↑ ${EWW_NET.eth0.NET_UP}"})
        (label :text {"↓ ${EWW_NET.eth0.NET_DOWN}"})))))
```

### Calendar Widget

```yuck
(defpoll cal-output
  :interval "60s"
  :initial ""
  `cal | tail -n +2`)            ; skip month/year header line

(defwidget calendar-widget []
  (box :class "calendar" :orientation "v" :spacing 0
    ; Month/year header
    (box :class "cal-header" :orientation "h"
      (button :class "cal-nav" :onclick "eww update cal-month=prev" "<")
      (label  :class "cal-month" :text {formattime(EWW_TIME, "%B %Y")})
      (button :class "cal-nav" :onclick "eww update cal-month=next" ">"))
    ; Day-of-week row
    (box :class "cal-days" :orientation "h" :space-evenly true
      (label :text "Su") (label :text "Mo") (label :text "Tu")
      (label :text "We") (label :text "Th") (label :text "Fr")
      (label :text "Sa"))
    ; Weeks — rendered from the pre-formatted cal output
    (label :class "cal-grid" :text cal-output :wrap true)))
```

### Music Player (MPRIS via playerctl)

```yuck
(deflisten mpris-meta
  :initial "{\"title\":\"\",\"artist\":\"\",\"status\":\"Stopped\",\"art\":\"\"}"
  `playerctl -F metadata --format \
    '{"title":"{{title}}","artist":"{{artist}}","status":"{{status}}","art":"{{mpris:artUrl}}"}' \
   2>/dev/null || echo '{"title":"","artist":"","status":"Stopped","art":""}'`)

(defpoll mpris-pos
  :interval "1s"
  :initial "0"
  `playerctl position 2>/dev/null || echo 0`)

(defpoll mpris-len
  :interval "5s"
  :initial "0"
  `playerctl metadata mpris:length 2>/dev/null | awk '{print $1/1000000}' || echo 0`)

(defwidget player-widget []
  (box :class "player" :orientation "v" :spacing 8
    :visible {mpris-meta.status != "Stopped"}
    ; Album art
    (image :path {mpris-meta.art} :image-width 64 :image-height 64
           :class "album-art"
           :visible {mpris-meta.art != ""})
    ; Track info
    (label :class "track-title" :text {mpris-meta.title} :ellipsize "end")
    (label :class "track-artist" :text {mpris-meta.artist} :ellipsize "end")
    ; Progress
    (scale :class "progress" :min 0 :max mpris-len :value mpris-pos
           :onchange "playerctl position {}")
    ; Controls
    (box :class "controls" :orientation "h" :spacing 12 :halign "center"
      (button :class "ctrl" :onclick "playerctl previous" "⏮")
      (button :class "ctrl play"
              :onclick "playerctl play-pause"
              {mpris-meta.status == "Playing" ? "⏸" : "▶"})
      (button :class "ctrl" :onclick "playerctl next" "⏭"))))
```

---

## 108.7 SCSS and Theming

eww compiles SCSS internally using `grass` (a Rust SCSS compiler). You get variables, nesting, `@import`, functions, and mixins — all the SCSS you would use in Waybar CSS.

### Consuming pywal/matugen Output

```scss
/* ~/.config/eww/eww.scss */
/* Import colours generated by pywal or matugen */
@import "colors";    /* auto-generated by pywal: ~/.config/eww/colors.scss */

/* Or read from matugen output */
@import "~/.config/matugen/colors-eww.scss";

/* Rest of your stylesheet uses @color variables */
* {
  all: unset;
  font-family: "JetBrainsMono Nerd Font", monospace;
  font-size: 13px;
}

.bar-window {
  background: alpha($base, 0.88);
  color: $text;
}

.ws.active {
  background: alpha($blue, 0.3);
  color: $blue;
}
```

Generate `colors.scss` from pywal's cache:

```bash
# ~/.config/wal/templates/colors-eww.scss
# (place this in pywal's template directory)
{% for color in colors %}
$color{{loop.index0}}: {{color}};
{% endfor %}
$base:    {{colors[0]}};
$text:    {{colors[7]}};
$blue:    {{colors[4]}};
$green:   {{colors[2]}};
$yellow:  {{colors[3]}};
$red:     {{colors[1]}};
$mauve:   {{colors[5]}};
```

```bash
# Run after each wallpaper change:
wal -i ~/wallpapers/current.jpg
cp ~/.cache/wal/colors-eww.scss ~/.config/eww/colors.scss
eww reload
```

### GTK CSS Variables

In GTK4 (eww ≥ 0.6) you can reference GTK's named colours with `@color-name` syntax:

```scss
/* Reference GTK theme colours */
.accent  { color: @accent_color; }
.warning { color: @warning_color; }
```

---

## 108.8 Multi-Monitor Setup

`defwindow` takes a `:monitor` property that accepts either a 0-indexed integer or a connector name string:

```yuck
(defwindow bar-primary
  :monitor 0
  :geometry (geometry :width "100%" :height "36px" :anchor "top center")
  :stacking "fg" :exclusive true :focusable false
  (bar-widget))

(defwindow bar-secondary
  :monitor "HDMI-A-1"          ; connector name from hyprctl monitors -j
  :geometry (geometry :width "100%" :height "36px" :anchor "top center")
  :stacking "fg" :exclusive true :focusable false
  (bar-widget))
```

Open both bars in your session startup:

```bash
eww open bar-primary &
eww open bar-secondary &
```

Or in a single call:

```bash
eww open-many bar-primary bar-secondary
```

The `EWW_MONITORS` magic variable gives you the live monitor list so you can render per-monitor state dynamically:

```yuck
(defwidget monitor-info []
  (box :orientation "v"
    (for mon in EWW_MONITORS
      (label :text {"${mon.name}: ${mon.width}×${mon.height}"}))))
```

---

## 108.9 CLI Reference

```bash
# Daemon lifecycle
eww daemon            # start the daemon (background)
eww kill              # stop the daemon
eww reload            # hot-reload .yuck and .scss (no restart needed for content changes)

# Window management
eww open <window>     # open a named defwindow
eww close <window>    # close it
eww open-many w1 w2   # open multiple at once
eww toggle <window>   # open if closed, close if open

# Variable control
eww update var=value  # set a defvar
eww state             # print all variable values (JSON)

# Debugging
eww logs              # tail the daemon log
eww debug             # print compiled widget tree for all open windows
eww inspector         # open GTK inspector (useful for CSS debugging)

# Get value of one variable
eww get workspaces | jq '.[0].name'
```

---

## 108.10 Troubleshooting

### Widget renders but data is wrong

```bash
# Check variable state
eww state | jq '.workspaces'

# Run the deflisten command manually to see its output
socat -u UNIX-CONNECT:"$HYPRLAND_SOCKET2" - | grep '^workspace>>'
```

### SCSS compilation error

eww prints SCSS errors to the daemon log with a line number. Run `eww logs` to see them. Common issues: missing semicolons, undefined SCSS variables, `@import` paths that don't exist.

### Window appears but has wrong size or position

Layer-shell geometry is clamped to the monitor. If your geometry percentage results in a sub-pixel size, GTK may round unexpectedly. Switch to absolute pixel values (`"36px"` not `"3%"`) for bar heights.

### `deflisten` variable never updates

The command must produce *line-separated* output — each newline triggers a variable update. Commands that buffer output (e.g., grep without `--line-buffered`, awk without `fflush()`) will appear to hang. Always add `--line-buffered` to grep and `| stdbuf -oL` before other commands.

### eww can't find `HYPRLAND_SOCKET2`

The variable is only set in Hyprland sessions. Expand the socket path explicitly:

```yuck
(deflisten workspaces
  :initial "[]"
  `hyprctl workspaces -j | jq '[.[]|{id,name,windows}]'`)
```

For the event socket, hardcode the path from `hyprctl -j instances | jq -r '.[0].socketPath'`.

---

## Summary

eww's strength is the combination of a genuinely reactive data model (`deflisten` responds to events; `defpoll` handles time-based data; `defvar` gives you manual control), a composable widget DSL with enough expression power to avoid helper scripts for routine transformations, and the freedom to place windows anywhere — not just at screen edges. For desktop widgets that need to float behind windows, appear and disappear based on application state, or display continuously-streaming data from IPC sockets, eww remains one of the most capable tools in the ricing stack despite its slower development pace relative to newer frameworks.

**Further reading:**
- [eww documentation](https://elkowar.github.io/eww/)
- Ch 26 — bar comparison: Waybar vs. eww vs. AGS/Astal
- Ch 38 — pywal/matugen colour extraction that feeds into eww SCSS
- Ch 59 — desktop widget placement philosophy
- Ch 88 — Hyprland IPC scripting (primary data source for workspace/window state)
