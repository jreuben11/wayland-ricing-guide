# Chapter 99 — Hyprland Lua Configuration

## Overview

Hyprland 0.55.0 (May 2026) introduced Lua as the new canonical configuration
format, replacing the custom `hyprlang` `.conf` syntax. The old `.conf` format
is deprecated and will be dropped within 1–2 releases after 0.55.

Lua configuration means your entire Hyprland setup is a real programming
language: loops that generate 10 workspace keybinds in 3 lines, conditionals
that detect your hostname and apply laptop vs desktop monitor layouts, functions
that group related binds, and an event system that reacts to windows opening or
monitors connecting at runtime.

This chapter covers the complete Lua API, practical patterns, and a full
migration guide from `.conf`.

---

## 99.1 Setup

### File location

```
~/.config/hypr/hyprland.lua
```

Hyprland checks for `hyprland.lua` before `hyprland.conf`. If the Lua file
exists it loads it; otherwise it falls back to the legacy conf manager.

```bash
# Explicit path (extension determines which parser is used):
Hyprland -c ~/.config/hypr/hyprland.lua

# Verify config without starting the compositor:
Hyprland --verify-config -c ~/.config/hypr/hyprland.lua
```

### The `hl` global

No `require()` call is needed. Hyprland injects the API as a global table
named `hl`. Every function in this chapter is a method on that table:

```lua
-- hyprland.lua — this works immediately, no imports
hl.config({ general = { gaps_out = 20 } })
```

Standard Lua libraries are fully available: `io`, `os`, `string`, `table`,
`math`, `coroutine`, `package`. LuaJIT is used where available.

### IDE support

Hyprland ships a stub generator (`meta/generateLuaStubs.py`) that produces
`lua-language-server` compatible type definitions for the entire `hl` API.

```bash
# Install lua-language-server
sudo pacman -S lua-language-server

# Generate stubs (run from the Hyprland source tree):
python3 meta/generateLuaStubs.py > ~/.config/hypr/hl_stubs.lua

# Configure lua-ls to load them in .luarc.json:
# { "workspace.library": ["~/.config/hypr"] }
```

With stubs, your editor gets full autocompletion for `hl.bind(`, `hl.dsp.*`,
and every other function in the API.

---

## 99.2 Core Configuration — `hl.config()`

`hl.config()` accepts a nested Lua table mirroring the hyprlang section
hierarchy. Multiple calls merge — you do not need one monolithic table.

```lua
hl.config({
    general = {
        gaps_in     = 5,
        gaps_out    = 20,
        border_size = 2,
        col = {
            active_border   = { colors = {"rgba(33ccffee)", "rgba(00ff99ee)"}, angle = 45 },
            inactive_border = "rgba(595959aa)",
        },
        resize_on_border = true,
        layout = "dwindle",
    },
    decoration = {
        rounding       = 10,
        rounding_power = 2,
        active_opacity   = 1.0,
        inactive_opacity = 0.92,
        shadow = {
            enabled      = true,
            range        = 4,
            render_power = 3,
            color        = 0xee1a1a1a,
        },
        blur = {
            enabled   = true,
            size      = 8,
            passes    = 2,
            vibrancy  = 0.17,
        },
    },
    input = {
        kb_layout    = "us",
        kb_options   = "caps:escape",
        follow_mouse = 1,
        sensitivity  = 0,
        accel_profile = "flat",
        touchpad = {
            natural_scroll      = true,
            tap_to_click        = true,
            disable_while_typing = true,
        },
    },
    gestures = {
        workspace_swipe = true,
        workspace_swipe_fingers = 3,
    },
    misc = {
        vfr = true,
        vrr = 2,
        disable_hyprland_logo   = true,
        disable_splash_rendering = true,
        force_default_wallpaper = 0,
    },
    dwindle = {
        preserve_split = true,
        pseudotile     = true,
    },
    master = {
        new_status  = "master",
        mfact       = 0.55,
    },
})
```

Read a config value at runtime:
```lua
local currentGaps = hl.get_config("general:gaps_out")
```

---

## 99.3 Monitors — `hl.monitor()`

```lua
-- Primary monitor
hl.monitor({
    output   = "DP-1",
    mode     = "2560x1440@165",
    position = "0 0",
    scale    = 1,
    vrr      = 2,        -- 0=off, 1=always, 2=fullscreen only
})

-- Laptop display (fractional scale)
hl.monitor({
    output   = "eDP-1",
    mode     = "preferred",
    position = "auto",
    scale    = 1.5,
})

-- Catch-all wildcard
hl.monitor({
    output   = "",
    mode     = "preferred",
    position = "auto",
    scale    = 1,
})

-- Disable a monitor
hl.monitor({ output = "HDMI-2", disabled = true })

-- 10-bit HDR
hl.monitor({
    output   = "DP-2",
    mode     = "3840x2160@144",
    position = "2560 0",
    scale    = 1,
    bitdepth = 10,
    cm       = "hdr",
    icc      = "/home/user/.config/icc/lg-oled.icc",
})
```

| Field | Description |
|-------|-------------|
| `output` | Connector name; `""` = wildcard |
| `mode` | `"WxH@Hz"`, `"preferred"`, or `"disable"` |
| `position` | `"x y"` or `"auto"` |
| `scale` | Float or `"auto"` |
| `transform` | 0–7 (wl_output_transform) |
| `mirror` | Connector to mirror |
| `bitdepth` | `8` or `10` |
| `vrr` | `0`/`1`/`2`/`3` |
| `icc` | Path to ICC profile |
| `cm` | `"srgb"`, `"hdr"` |
| `disabled` | `true` to disable |

---

## 99.4 Keybinds — `hl.bind()` and `hl.dsp.*`

### Basic syntax

```lua
hl.bind("MODS + KEY", dispatcher [, opts])
```

Modifiers: `SUPER`, `SHIFT`, `CTRL`, `ALT`. Combine with `+`.
Dispatchers live under `hl.dsp.*` and return closures — they are not called
immediately but when the key is pressed.

```lua
local M = "SUPER"

-- Window management
hl.bind(M .. " + Q",         hl.dsp.window.close())
hl.bind(M .. " + F",         hl.dsp.window.fullscreen())
hl.bind(M .. " + SHIFT + F", hl.dsp.window.float({ action = "toggle" }))
hl.bind(M .. " + P",         hl.dsp.window.pin())

-- Focus
hl.bind(M .. " + H", hl.dsp.focus({ direction = "l" }))
hl.bind(M .. " + L", hl.dsp.focus({ direction = "r" }))
hl.bind(M .. " + K", hl.dsp.focus({ direction = "u" }))
hl.bind(M .. " + J", hl.dsp.focus({ direction = "d" }))

-- Launch apps
hl.bind(M .. " + Return", hl.dsp.exec_cmd("kitty"))
hl.bind(M .. " + Space",  hl.dsp.exec_cmd("fuzzel"))
hl.bind(M .. " + E",      hl.dsp.exec_cmd("yazi"))
```

### Bind options

```lua
-- Repeat on hold (binde equivalent):
hl.bind(M .. " + ALT + L", hl.dsp.window.resize({ direction = "right", delta = 20 }),
    { repeating = true })

-- Locked (works on lockscreen):
hl.bind("XF86AudioRaiseVolume",
    hl.dsp.exec_cmd("wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+"),
    { locked = true, repeating = true })

-- Release bind (bindr equivalent):
hl.bind(M .. " + Escape", hl.dsp.submap("reset"), { release = true })

-- Mouse bind (bindm equivalent):
hl.bind(M .. " + mouse:272", hl.dsp.window.drag(),   { mouse = true })
hl.bind(M .. " + mouse:273", hl.dsp.window.resize(), { mouse = true })

-- Non-consuming (bindn equivalent):
hl.bind(M .. " + I", hl.dsp.exec_cmd("hyprctl layers"), { non_consuming = true })
```

| Option | Hyprlang equivalent | Description |
|--------|--------------------|-|
| `repeating` | `binde` | Fire repeatedly while held |
| `locked` | `bindl` | Works on lockscreen |
| `release` | `bindr` | Fires on key release |
| `mouse` | `bindm` | Mouse button bind |
| `non_consuming` | `bindn` | Doesn't consume the key event |

### Generating workspace binds with a loop

```lua
local M = "SUPER"

for i = 1, 10 do
    local key = i % 10   -- makes 10 → 0
    hl.bind(M .. " + " .. key,
        hl.dsp.workspace.switch({ workspace = i }))
    hl.bind(M .. " + SHIFT + " .. key,
        hl.dsp.window.move({ workspace = i }))
end
```

This replaces 20 lines of `.conf` with 5 lines of Lua.

### Binding to a plain Lua function

```lua
hl.bind(M .. " + X", function()
    local handle = io.popen("hyprctl -j activewindow")
    local info = handle:read("*a")
    handle:close()
    hl.notification.create({ text = info, duration = 3000 })
end)
```

### Submaps (modal keybinds)

```lua
hl.define_submap("resize", function()
    hl.bind("H", hl.dsp.window.resize({ direction = "left",  delta = 20 }), { repeating = true })
    hl.bind("L", hl.dsp.window.resize({ direction = "right", delta = 20 }), { repeating = true })
    hl.bind("K", hl.dsp.window.resize({ direction = "up",    delta = 20 }), { repeating = true })
    hl.bind("J", hl.dsp.window.resize({ direction = "down",  delta = 20 }), { repeating = true })
    hl.bind("Escape", hl.dsp.submap("reset"))
    hl.bind("Return", hl.dsp.submap("reset"))
end)

hl.bind(M .. " + R", hl.dsp.submap("resize"))
```

### Unbind

```lua
hl.unbind("SUPER + Q")   -- unbind a specific bind
hl.unbind("all")          -- unbind everything (useful before re-defining)
```

---

## 99.5 Dispatcher Reference (`hl.dsp.*`)

### Window (`hl.dsp.window.*`)

```lua
hl.dsp.window.close()
hl.dsp.window.kill()
hl.dsp.window.float({ action = "toggle" })       -- or "on"/"off"
hl.dsp.window.fullscreen({ mode = 0 })           -- 0=fullscreen, 1=maximize
hl.dsp.window.pseudo()
hl.dsp.window.move({ direction = "l" })
hl.dsp.window.move({ workspace = 3 })
hl.dsp.window.swap({ direction = "r" })
hl.dsp.window.center()
hl.dsp.window.pin()
hl.dsp.window.resize({ direction = "right", delta = 20 })
hl.dsp.window.bring_to_top()
hl.dsp.window.drag()
```

### Workspace (`hl.dsp.workspace.*`)

```lua
hl.dsp.workspace.switch({ workspace = 3 })
hl.dsp.workspace.switch({ workspace = "e+1" })      -- relative
hl.dsp.workspace.switch({ workspace = "previous" })
hl.dsp.workspace.switch({ workspace = "special" })
hl.dsp.workspace.rename({ name = "code" })
hl.dsp.workspace.move({ workspace = 2 })
hl.dsp.workspace.toggle_special({ name = "scratch" })
```

### Focus (`hl.dsp.focus.*`)

```lua
hl.dsp.focus({ direction = "l" })          -- l/r/u/d
hl.dsp.focus({ monitor = "DP-1" })
hl.dsp.focus({ window = "class:kitty" })
hl.dsp.focus({ cycle = "next" })
```

### Top-level dispatchers

```lua
hl.dsp.exec_cmd("kitty")
hl.dsp.exec_raw("kitty --hold")           -- no rule injection
hl.dsp.exit()
hl.dsp.submap("reset")
hl.dsp.submap("resize")
hl.dsp.dpms({ state = "off" })
hl.dsp.dpms({ state = "toggle", monitor = "DP-1" })
hl.dsp.force_renderer_reload()
hl.dsp.no_op()
```

---

## 99.6 Window Rules — `hl.window_rule()`

Returns a handle with `:set_enabled(bool)` — rules can be toggled at runtime.

```lua
-- Float pavucontrol
hl.window_rule({
    name  = "float-pavucontrol",
    match = { class = "^pavucontrol$" },
    float = true,
    size  = "800 600",
    center = true,
})

-- Suppress maximize events for all windows
local noMaximize = hl.window_rule({
    name           = "no-maximize",
    match          = { class = ".*" },
    suppress_event = "maximize",
})
-- noMaximize:set_enabled(false)  -- disable at runtime

-- Move Firefox to workspace 2 silently
hl.window_rule({
    name      = "firefox-ws2",
    match     = { class = "^firefox$" },
    workspace = "2",
    silent    = true,
})

-- Fix XWayland popup focus
hl.window_rule({
    name  = "fix-xwayland-drags",
    match = {
        class      = "^$",
        title      = "^$",
        xwayland   = true,
        float      = true,
        fullscreen = false,
    },
    no_focus = true,
})

-- Per-app opacity
hl.window_rule({
    name    = "kitty-opacity",
    match   = { class = "^kitty$" },
    opacity = { active = 0.92, inactive = 0.85 },
})
```

### Layer rules — `hl.layer_rule()`

```lua
hl.layer_rule({
    name      = "blur-bar",
    match     = { namespace = "waybar" },
    blur      = true,
    ignorezero = true,
})
```

### Workspace rules — `hl.workspace_rule()`

```lua
hl.workspace_rule({
    workspace = "1",
    monitor   = "DP-1",
    default   = true,
    persistent = true,
})

-- No gaps on fullscreen workspace
hl.workspace_rule({
    workspace = "f[1]",
    gaps_out  = 0,
    gaps_in   = 0,
})
```

---

## 99.7 Autostart — `hl.on("hyprland.start", fn)`

```lua
hl.on("hyprland.start", function()
    hl.exec_cmd("waybar")
    hl.exec_cmd("hyprpaper")
    hl.exec_cmd("hypridle")
    hl.exec_cmd("nm-applet --indicator")
    hl.exec_cmd("blueman-applet")
    hl.exec_cmd("dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP")
end)
```

`hl.exec_cmd()` accepts an optional second argument — a rule table applied to
the spawned process (equivalent to `execr` in hyprlang):

```lua
hl.exec_cmd("kitty", { float = true, size = "800 500", center = true })
```

---

## 99.8 Environment Variables — `hl.env()`

```lua
hl.env("XCURSOR_SIZE",        "24")
hl.env("XCURSOR_THEME",       "Catppuccin-Mocha-Dark-Cursors")
hl.env("HYPRCURSOR_SIZE",     "24")
hl.env("QT_QPA_PLATFORM",     "wayland")
hl.env("QT_QPA_PLATFORMTHEME","qt5ct")
hl.env("QT_STYLE_OVERRIDE",   "kvantum")
hl.env("MOZ_ENABLE_WAYLAND",  "1")
hl.env("GDK_BACKEND",         "wayland,x11")
hl.env("GTK_IM_MODULE",       "fcitx")
hl.env("QT_IM_MODULE",        "fcitx")
hl.env("XDG_CURRENT_DESKTOP", "Hyprland")
hl.env("XDG_SESSION_TYPE",    "wayland")
```

---

## 99.9 Splitting Config with `require()`

`package.path` is pre-configured to `~/.config/hypr/?.lua` so you can split
your config into files without any path setup:

```
~/.config/hypr/
├── hyprland.lua        ← entry point
├── theme.lua           ← colours, fonts, decoration
├── keybinds.lua        ← all binds
├── rules.lua           ← window/layer/workspace rules
├── monitors.lua        ← monitor config
└── autostart.lua       ← startup apps
```

```lua
-- hyprland.lua
require("theme")
require("monitors")
require("keybinds")
require("rules")
require("autostart")
```

```lua
-- theme.lua
local M = "SUPER"   -- local variables don't leak between files unless returned

hl.config({
    decoration = {
        rounding = 12,
        blur = { enabled = true, size = 8, passes = 2 },
    },
    general = {
        col = {
            active_border = { colors = {"rgba(cba6f7ee)", "rgba(89b4faee)"}, angle = 45 },
        },
    },
})
```

---

## 99.10 Lua-Specific Power Patterns

### Conditional config by hostname

```lua
local handle   = io.popen("hostname")
local hostname = handle:read("*a"):gsub("%s+", "")
handle:close()

if hostname == "work-laptop" then
    hl.monitor({ output = "eDP-1", scale = 1.5 })
    hl.config({ general = { gaps_out = 10 } })
else
    hl.monitor({ output = "eDP-1", scale = 1.0 })
    hl.config({ general = { gaps_out = 20 } })
end
```

### Reusable bind group function

```lua
local function appBinds(mod, key, cmd)
    hl.bind(mod .. " + " .. key,
        hl.dsp.exec_cmd(cmd))
    hl.bind(mod .. " + SHIFT + " .. key,
        hl.dsp.exec_cmd(cmd .. " --new-window"),
        { description = cmd .. " (new window)" })
end

local M = "SUPER"
appBinds(M, "B", "firefox")
appBinds(M, "F", "thunar")
appBinds(M, "S", "spotify-launcher")
```

### Per-app window rule generator

```lua
local function floatApp(class, w, h)
    hl.window_rule({
        name   = "float-" .. class,
        match  = { class = "^" .. class .. "$" },
        float  = true,
        size   = w .. " " .. h,
        center = true,
    })
end

floatApp("pavucontrol", 800, 600)
floatApp("blueman-manager", 700, 500)
floatApp("nm-connection-editor", 900, 600)
floatApp("qalculate-gtk", 400, 600)
```

### Reading environment at startup

```lua
local xdgDataHome = os.getenv("XDG_DATA_HOME") or (os.getenv("HOME") .. "/.local/share")
local wallpaperDir = xdgDataHome .. "/wallpapers"

hl.on("hyprland.start", function()
    hl.exec_cmd("swww img " .. wallpaperDir .. "/current.jpg")
end)
```

---

## 99.11 The Event System

React to compositor events in real time — no polling, no shell daemon needed.

```lua
-- Auto-move apps to workspaces when they open
hl.on("window.open", function(win)
    local class = win:get_class()
    if class == "Spotify" then
        hl.dsp.window.move({ workspace = "name:music" })()
    elseif class == "discord" then
        hl.dsp.window.move({ workspace = "name:chat" })()
    end
end)

-- Reconfigure monitors on hotplug
hl.on("monitor.added", function(mon)
    local name = mon:get_name()
    hl.notification.create({
        text     = "Monitor connected: " .. name,
        duration = 3000,
    })
    -- apply per-monitor config
end)

-- React to config reload
hl.on("config.reloaded", function()
    hl.notification.create({ text = "Config reloaded", duration = 1500 })
end)
```

### Full event list

| Event | Data | Description |
|-------|------|-------------|
| `hyprland.start` | — | Compositor fully started |
| `hyprland.shutdown` | — | Compositor shutting down |
| `window.open` | window | New window created |
| `window.open_early` | window | Window created, rules not applied yet |
| `window.close` | window | Window closed |
| `window.active` | window | Window focused |
| `window.title` | window | Window title changed |
| `window.class` | window | Window class changed |
| `window.fullscreen` | window | Fullscreen toggled |
| `window.move_to_workspace` | window | Window moved to workspace |
| `monitor.added` | monitor | Monitor connected |
| `monitor.removed` | monitor | Monitor disconnected |
| `monitor.focused` | monitor | Monitor focus changed |
| `workspace.active` | workspace | Active workspace changed |
| `workspace.created` | workspace | New workspace created |
| `workspace.removed` | workspace | Workspace destroyed |
| `config.reloaded` | — | Config successfully reloaded |
| `keybinds.submap` | string | Submap changed |
| `screenshare.state` | — | Screen sharing started/stopped |

---

## 99.12 Timers

```lua
-- Repeating timer (runs every 5 seconds)
local statusTimer = hl.timer(function()
    -- update something periodically
    local f = io.popen("free -m | awk 'NR==2{print $3\"/\"$2\" MB\"}'")
    local mem = f:read("*a"):gsub("%s+", "")
    f:close()
    -- could write to a file that a Quickshell FileView watches
end, { timeout = 5000, type = "repeat" })

-- One-shot timer (runs once after 2 seconds)
hl.timer(function()
    hl.notification.create({ text = "Ready!", duration = 2000 })
end, { timeout = 2000, type = "oneshot" })

-- Change the timer interval later:
statusTimer:set_timeout(10000)
```

---

## 99.13 Notifications — `hl.notification.create()`

```lua
hl.notification.create({
    text      = "Config loaded successfully",
    duration  = 3000,
    icon      = "info",      -- "info", "warning", "error", "ok", "hint", "confused", "none"
    color     = "rgba(89b4faee)",
    font_size = 14,
})
```

---

## 99.14 Permissions — `hl.permission()`

Grant screencopy and other privileged capabilities to specific applications:

```lua
hl.permission("/usr/(bin|local/bin)/grim",        "screencopy", "allow")
hl.permission("/usr/(bin|local/bin)/wl-screenrec", "screencopy", "allow")
hl.permission("/usr/(bin|local/bin)/obs",          "screencopy", "allow")
```

---

## 99.15 Animations — `hl.curve()` and `hl.animation()`

```lua
-- Bezier curve
hl.curve("overshot",   { type = "bezier", points = { {0.05, 0.9}, {0.1, 1.05} } })
hl.curve("smoothOut",  { type = "bezier", points = { {0.36, 0},   {0.66, -0.56} } })

-- Spring curve (new in Hyprland 0.55)
hl.curve("snappy",  { type = "spring", mass = 1, stiffness = 200, dampening = 20 })
hl.curve("bouncy",  { type = "spring", mass = 1, stiffness = 100, dampening = 10 })

-- Animations
hl.animation({ leaf = "global",       enabled = true, speed = 8,  bezier = "default" })
hl.animation({ leaf = "windows",      enabled = true, speed = 5,  spring = "snappy", style = "slide" })
hl.animation({ leaf = "windowsIn",    enabled = true, speed = 4,  spring = "bouncy", style = "popin 80%" })
hl.animation({ leaf = "windowsOut",   enabled = true, speed = 4,  bezier = "smoothOut", style = "slide" })
hl.animation({ leaf = "fade",         enabled = true, speed = 3,  bezier = "smoothOut" })
hl.animation({ leaf = "workspaces",   enabled = true, speed = 6,  spring = "snappy", style = "slidevert" })
hl.animation({ leaf = "layers",       enabled = true, speed = 3,  bezier = "default", style = "slide" })
hl.animation({ leaf = "border",       enabled = true, speed = 5,  bezier = "overshot" })
```

---

## 99.16 Migration from hyprlang `.conf`

### Automatic migration (recommended)

A migration tool exists:
```bash
paru -S hyprland-migrate   # or: check hyprland wiki for current tool
hyprland-migrate ~/.config/hypr/hyprland.conf > ~/.config/hypr/hyprland.lua
```

### Manual translation reference

| hyprlang | Lua equivalent |
|---------|----------------|
| `general { gaps_out = 20 }` | `hl.config({ general = { gaps_out = 20 } })` |
| `monitor = DP-1,2560x1440@165,0x0,1` | `hl.monitor({ output="DP-1", mode="2560x1440@165", position="0 0", scale=1 })` |
| `bind = SUPER, Q, killactive` | `hl.bind("SUPER + Q", hl.dsp.window.close())` |
| `binde = SUPER ALT, L, resizeactive, 20 0` | `hl.bind("SUPER + ALT + L", hl.dsp.window.resize(...), { repeating=true })` |
| `exec-once = waybar` | Inside `hl.on("hyprland.start", fn)`: `hl.exec_cmd("waybar")` |
| `env = QT_QPA_PLATFORM,wayland` | `hl.env("QT_QPA_PLATFORM", "wayland")` |
| `windowrulev2 = float, class:pavucontrol` | `hl.window_rule({ match={ class="^pavucontrol$" }, float=true })` |
| `source = other.conf` | `require("other")` |
| `$terminal = kitty` | `local terminal = "kitty"` |
| `bezier = overshot, 0.05, 0.9, 0.1, 1.05` | `hl.curve("overshot", { type="bezier", points={{0.05,0.9},{0.1,1.05}} })` |

### Timeline

- **v0.55.0** (May 2026): Lua introduced, hyprlang deprecated
- **v0.56–v0.57** (est.): hyprlang support removed
- **New features**: Only available in Lua going forward

---

## 99.17 Complete Minimal Config

```lua
-- ~/.config/hypr/hyprland.lua
-- Hyprland 0.55+ — minimal working config

local M = "SUPER"

-- Environment
hl.env("QT_QPA_PLATFORM",     "wayland")
hl.env("MOZ_ENABLE_WAYLAND",  "1")
hl.env("GDK_BACKEND",         "wayland,x11")
hl.env("XCURSOR_SIZE",        "24")
hl.env("XDG_CURRENT_DESKTOP", "Hyprland")

-- Monitors
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = 1 })

-- Core config
hl.config({
    general = {
        gaps_in = 5, gaps_out = 10,
        border_size = 2,
        col = {
            active_border   = "rgba(89b4faee)",
            inactive_border = "rgba(595959aa)",
        },
        layout = "dwindle",
    },
    decoration = { rounding = 10 },
    animations  = { enabled = true },
    input = { kb_layout = "us", follow_mouse = 1, sensitivity = 0 },
    misc  = { vfr = true, disable_hyprland_logo = true },
})

-- Autostart
hl.on("hyprland.start", function()
    hl.exec_cmd("waybar")
    hl.exec_cmd("hyprpaper")
    hl.exec_cmd("dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP")
end)

-- Basic keybinds
hl.bind(M .. " + Return", hl.dsp.exec_cmd("kitty"))
hl.bind(M .. " + Space",  hl.dsp.exec_cmd("fuzzel"))
hl.bind(M .. " + Q",      hl.dsp.window.close())
hl.bind(M .. " + F",      hl.dsp.window.fullscreen())
hl.bind(M .. " + SHIFT + F", hl.dsp.window.float({ action = "toggle" }))
hl.bind(M .. " + H", hl.dsp.focus({ direction = "l" }))
hl.bind(M .. " + L", hl.dsp.focus({ direction = "r" }))
hl.bind(M .. " + K", hl.dsp.focus({ direction = "u" }))
hl.bind(M .. " + J", hl.dsp.focus({ direction = "d" }))
hl.bind(M .. " + mouse:272", hl.dsp.window.drag(),   { mouse = true })
hl.bind(M .. " + mouse:273", hl.dsp.window.resize(), { mouse = true })

-- Workspace binds (generated with a loop)
for i = 1, 10 do
    local key = i % 10
    hl.bind(M .. " + " .. key, hl.dsp.workspace.switch({ workspace = i }))
    hl.bind(M .. " + SHIFT + " .. key, hl.dsp.window.move({ workspace = i }))
end

-- System
hl.bind(M .. " + SHIFT + E", hl.dsp.exit())
hl.bind(M .. " + SHIFT + R", function() hl.reload() end)
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
