# Chapter 120 — WirePlumber Lua Scripting

## Contents

- [Overview](#overview)
- [120.1 WirePlumber Architecture](#1201-wireplumber-architecture)
  - [Script Entry Points](#script-entry-points)
- [120.2 Configuration Overrides (No Lua Required)](#1202-configuration-overrides-no-lua-required)
- [120.3 Device Priority: Prefer USB Audio](#1203-device-priority-prefer-usb-audio)
- [120.4 Auto-Profile Switching on Headphone Plug](#1204-auto-profile-switching-on-headphone-plug)
- [120.5 Volume Persistence Per Device](#1205-volume-persistence-per-device)
- [120.6 Custom Link Policy: Route App to Specific Device](#1206-custom-link-policy-route-app-to-specific-device)
- [120.7 Reload and Debug](#1207-reload-and-debug)
- [120.8 Script Loading Reference](#1208-script-loading-reference)

---


## Overview

WirePlumber is the session manager for PipeWire — the daemon that decides which nodes connect to which, which profile an audio device uses, what volume to restore when a device plugs in, and how to route a video stream from a camera to a recording application. Its behavior is entirely controlled by Lua scripts that run in an embedded interpreter, reacting to PipeWire graph events.

Chapter 56 covers WirePlumber as a system service with standard configuration files. This chapter goes deeper: writing Lua scripts that implement custom routing rules, automatic profile switching on hardware events, device priority ordering, and persistent volume policies. These techniques solve problems that config file knobs cannot reach.

**Cross-references:** Ch 56 — PipeWire and WirePlumber setup. Ch 21 — PipeWire audio in Quickshell. Ch 114 — audio visualizers (PipeWire source selection).

---

## 120.1 WirePlumber Architecture

WirePlumber loads a set of Lua scripts on startup. Each script runs in a sandboxed Lua environment with access to a small API that wraps PipeWire's object model:

```
WirePlumber process
  ├── Lua interpreter (embedded)
  │   ├── built-in scripts: /usr/share/wireplumber/scripts/
  │   └── user scripts:     ~/.config/wireplumber/scripts/
  ├── Configuration: ~/.config/wireplumber/wireplumber.conf.d/
  └── PipeWire connection (monitors graph, creates/destroys links)
```

The built-in scripts handle standard behavior. User scripts in `~/.config/wireplumber/scripts/` are loaded alongside them.

### Script Entry Points

Scripts interact with WirePlumber via:
- `Core.connect()` — hook into PipeWire connection lifecycle
- `ObjectManager` — watch for new/removed objects matching a filter
- `Node`, `Device`, `Port`, `Link` — PipeWire object wrappers
- `Interest` — predicate for matching objects by property
- `SimpleEventHook`, `AsyncEventHook` — react to WirePlumber events

---

## 120.2 Configuration Overrides (No Lua Required)

Before writing Lua, check whether a built-in config knob solves your problem. Config files in `~/.config/wireplumber/wireplumber.conf.d/` override defaults:

```lua
-- ~/.config/wireplumber/wireplumber.conf.d/50-alsa-config.conf
monitor.alsa.rules = [
  {
    matches = [ { node.name = "~alsa_output.*" } ]
    actions = {
      update-props = {
        audio.format = "S32LE"
        audio.rate   = 48000
        api.alsa.period-size   = 1024
        api.alsa.headroom      = 0
      }
    }
  }
]
```

```lua
-- ~/.config/wireplumber/wireplumber.conf.d/51-disable-camera.conf
-- Disable the built-in laptop camera
monitor.v4l2.rules = [
  {
    matches = [ { node.name = "~v4l2_input.*front.*" } ]
    actions = { update-props = { node.disabled = true } }
  }
]
```

---

## 120.3 Device Priority: Prefer USB Audio

WirePlumber chooses the "default" sink/source based on priority. To always prefer an external USB audio interface over built-in audio when plugged in:

```lua
-- ~/.config/wireplumber/scripts/prefer-usb-audio.lua

local usb_priority = 2000   -- higher than internal (1000)

local om = ObjectManager {
  Interest { type = "node",
             Constraint { "media.class", "=", "Audio/Sink" } }
}

om:connect("object-added", function(om, node)
  local desc = node.properties["device.description"] or ""
  -- USB devices have "usb" in their device path or description
  local is_usb = (node.properties["api.alsa.card.longname"] or ""):lower():find("usb")
               or (node.properties["node.name"] or ""):lower():find("usb")

  if is_usb then
    node.properties["priority.session"] = usb_priority
    Log.info("USB audio sink found: " .. desc .. " — priority set to " .. usb_priority)
  end
end)

om:activate()
```

Load this script by referencing it in wireplumber.conf:

```lua
-- ~/.config/wireplumber/wireplumber.conf.d/60-prefer-usb.conf
wireplumber.scripts = [
  { name = "prefer-usb-audio.lua" }
]
```

---

## 120.4 Auto-Profile Switching on Headphone Plug

Switch an ALSA device to the "headphones" profile when headphones are plugged in (detected via ALSA UCM jack events), and back to "speakers" when unplugged:

```lua
-- ~/.config/wireplumber/scripts/auto-profile-headphones.lua

local headphones_profile = "output:analog-stereo+input:analog-stereo"
local speakers_profile   = "output:analog-stereo"

local devices = ObjectManager {
  Interest { type = "device",
             Constraint { "media.class", "=", "Audio/Device" } }
}

local function set_profile(device, profile_name)
  local profiles = device:iterate { type = "param", id = "EnumProfile" }
  for p in profiles do
    local name = p.pod["name"] or ""
    if name == profile_name then
      device:set_params("Profile", p.pod)
      Log.info("Switched " .. device.properties["device.description"]
               .. " to profile: " .. profile_name)
      return
    end
  end
  Log.warning("Profile not found: " .. profile_name)
end

devices:connect("object-added", function(_, device)
  -- Watch for jack detection events on this device
  device:connect("params-changed", function(device, id)
    if id ~= "Route" then return end

    local routes = device:iterate { type = "param", id = "Route" }
    local headphones_active = false
    for route in routes do
      local name  = route.pod["name"] or ""
      local avail = route.pod["available"] or "unknown"
      if name:lower():find("headphone") and avail == "yes" then
        headphones_active = true
        break
      end
    end

    if headphones_active then
      set_profile(device, headphones_profile)
    else
      set_profile(device, speakers_profile)
    end
  end)
end)

devices:activate()
```

---

## 120.5 Volume Persistence Per Device

WirePlumber restores saved volumes when a device reconnects. To set initial volumes for specific devices:

```lua
-- ~/.config/wireplumber/scripts/initial-volumes.lua

local VOLUMES = {
  ["alsa_output.usb-Focusrite_Scarlett_Solo_USB-00.analog-stereo"] = 0.8,
  ["alsa_output.pci-0000_00_1f.3.analog-stereo"] = 0.6,
}

local om = ObjectManager {
  Interest { type = "node",
             Constraint { "media.class", "=", "Audio/Sink" } }
}

om:connect("object-added", function(_, node)
  local name = node.properties["node.name"] or ""
  local vol  = VOLUMES[name]
  if vol and not node:is_linked() then
    -- Only set volume if no saved state exists
    node:set_params("Props", Pod.Object {
      Pod.Property { "volume", "f", vol },
      Pod.Property { "mute",   "b", false },
    })
    Log.info("Set initial volume for " .. name .. " to " .. vol)
  end
end)

om:activate()
```

---

## 120.6 Custom Link Policy: Route App to Specific Device

Route a specific application (by name) to a specific audio device, bypassing WirePlumber's default "route to default sink" policy:

```lua
-- ~/.config/wireplumber/scripts/route-spotify-to-usb.lua
-- Always send Spotify's audio to the USB DAC

local TARGET_APP  = "Spotify"
local TARGET_SINK = "alsa_output.usb-.*analog-stereo"

local nodes = ObjectManager {
  Interest { type = "node",
             Constraint { "media.class", "=", "Stream/Output/Audio" } }
}

local sinks = ObjectManager {
  Interest { type = "node",
             Constraint { "media.class", "=", "Audio/Sink" } }
}

local function find_sink()
  for s in sinks:iterate() do
    local name = s.properties["node.name"] or ""
    if name:find(TARGET_SINK) then return s end
  end
  return nil
end

nodes:connect("object-added", function(_, node)
  local app = node.properties["application.name"] or
              node.properties["node.name"] or ""
  if not app:find(TARGET_APP) then return end

  local sink = find_sink()
  if not sink then
    Log.warning("Target sink not found for " .. TARGET_APP)
    return
  end

  -- Create an explicit link: Spotify's output → USB DAC's input
  local link = Link("link-factory", {
    ["link.output.node"] = node.id,
    ["link.output.port"] = 0,
    ["link.input.node"]  = sink.id,
    ["link.input.port"]  = 0,
    ["object.linger"]    = true,
  })
  link:activate(Feature.Proxy.BOUND)
  Log.info("Linked " .. app .. " → " .. (sink.properties["node.name"] or "sink"))
end)

nodes:activate()
sinks:activate()
```

---

## 120.7 Reload and Debug

```bash
# Reload WirePlumber after script changes (no restart needed for conf changes)
systemctl --user restart wireplumber

# Watch WirePlumber logs
journalctl --user -u wireplumber -f

# Enable verbose Lua logging
WIREPLUMBER_DEBUG=3 wireplumber 2>&1 | grep -E "lua|Lua|WARN|ERR"

# Inspect the current PipeWire graph
pw-dump | jq '.[] | select(.type == "PipeWire:Interface:Node") | {name: .info.props["node.name"], class: .info.props["media.class"]}'
```

---

## 120.8 Script Loading Reference

```lua
-- ~/.config/wireplumber/wireplumber.conf.d/99-custom-scripts.conf
wireplumber.scripts = [
  { name = "prefer-usb-audio.lua",          type = "config/lua" }
  { name = "auto-profile-headphones.lua",   type = "config/lua" }
  { name = "route-spotify-to-usb.lua",      type = "config/lua" }
  { name = "initial-volumes.lua",           type = "config/lua" }
]
```

Scripts in `~/.config/wireplumber/scripts/` are found automatically when referenced by name. Absolute paths also work.
