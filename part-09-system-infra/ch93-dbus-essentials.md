# Chapter 93 — D-Bus Essentials for Wayland Power Users

## Contents

- [Overview](#overview)
- [93.1 Session Bus vs System Bus](#931-session-bus-vs-system-bus)
- [93.2 busctl — The Best D-Bus CLI](#932-busctl-the-best-d-bus-cli)
  - [busctl monitor (event stream)](#busctl-monitor-event-stream)
- [93.3 gdbus — GNOME D-Bus Tool](#933-gdbus-gnome-d-bus-tool)
- [93.4 dbus-monitor — Traffic Monitoring](#934-dbus-monitor-traffic-monitoring)
- [93.5 Scripting D-Bus from Shell](#935-scripting-d-bus-from-shell)
  - [Send a desktop notification](#send-a-desktop-notification)
  - [Control MPRIS media player](#control-mpris-media-player)
  - [Query UPower battery](#query-upower-battery)
  - [NetworkManager status](#networkmanager-status)
- [93.6 Writing a D-Bus Service from Shell](#936-writing-a-d-bus-service-from-shell)
- [93.7 D-Bus in Quickshell](#937-d-bus-in-quickshell)
- [93.8 Varlink — The D-Bus Successor for System Services](#938-varlink-the-d-bus-successor-for-system-services)
  - [What uses Varlink today](#what-uses-varlink-today)
  - [Querying Varlink from the CLI](#querying-varlink-from-the-cli)
  - [Varlink interface definition (IDL)](#varlink-interface-definition-idl)
  - [When to use Varlink vs D-Bus](#when-to-use-varlink-vs-d-bus)
- [93.9 dbus-run-session — Headless D-Bus Testing](#939-dbus-run-session-headless-d-bus-testing)

---


## Overview

D-Bus is the IPC backbone of a Linux desktop. Portals, notifications, MPRIS,
Bluetooth, NetworkManager, polkit, and most other system services speak D-Bus.
Understanding it lets you script any desktop service from the command line,
build Quickshell components that talk to arbitrary D-Bus APIs, and debug silent
failures in portal interactions.

Varlink (systemd's newer IPC mechanism for system services) is covered in §93.8.

---

## 93.1 Session Bus vs System Bus

```
Session bus  (/run/user/1000/bus)   — one per login session
  ├── org.freedesktop.portal.Desktop  (xdg-desktop-portal)
  ├── org.freedesktop.Notifications   (mako, dunst, swaync)
  ├── org.mpris.MediaPlayer2.*        (mpv, Spotify, etc.)
  ├── com.hyprland.IPC                (Hyprland, if registered)
  └── org.kde.StatusNotifierWatcher  (system tray)

System bus   (/run/dbus/system_bus_socket)
  ├── org.bluez                       (Bluetooth)
  ├── org.freedesktop.NetworkManager  (NetworkManager)
  ├── org.freedesktop.login1          (logind)
  └── org.freedesktop.UPower          (battery)
```

```bash
# These should be set in your session environment
echo $DBUS_SESSION_BUS_ADDRESS
# → unix:path=/run/user/1000/bus
```

---

## 93.2 busctl — The Best D-Bus CLI

`busctl` (from systemd) is the most ergonomic D-Bus tool:

```bash
# List all services on the session bus
busctl --user list

# List all services on the system bus
busctl list

# Introspect a service (see all interfaces, methods, properties)
busctl --user introspect org.freedesktop.Notifications /org/freedesktop/Notifications

# Call a method
busctl --user call \
  org.freedesktop.Notifications \
  /org/freedesktop/Notifications \
  org.freedesktop.Notifications \
  Notify \
  "susssasa{sv}i" \
  "myapp" 0 "dialog-info" "Title" "Body" 0 0 {} {} 5000

# Get a property
busctl get-property \
  org.freedesktop.UPower \
  /org/freedesktop/UPower/devices/battery_BAT0 \
  org.freedesktop.UPower.Device \
  Percentage

# Set a property
busctl --user set-property \
  org.bluez \
  /org/bluez/hci0 \
  org.bluez.Adapter1 \
  Powered b true
```

### busctl monitor (event stream)

```bash
# Monitor all D-Bus traffic on the session bus
busctl --user monitor

# Filter by service
busctl --user monitor org.freedesktop.Notifications

# Filter by interface
busctl --user monitor --match "interface=org.mpris.MediaPlayer2.Player"
```

---

## 93.3 gdbus — GNOME D-Bus Tool

```bash
# Call a method (alternative to busctl)
gdbus call --session \
  --dest org.freedesktop.Notifications \
  --object-path /org/freedesktop/Notifications \
  --method org.freedesktop.Notifications.Notify \
  "myapp" 0 "dialog-info" "Title" "Body" "[]" "{}" 5000

# Get a property
gdbus get-property --system \
  --dest org.freedesktop.UPower \
  --object-path /org/freedesktop/UPower \
  --interface org.freedesktop.UPower \
  DaemonVersion
```

---

## 93.4 dbus-monitor — Traffic Monitoring

```bash
# Monitor all session bus traffic
dbus-monitor --session

# Filter by message type
dbus-monitor --session "type='signal'"

# Filter by interface
dbus-monitor --session "interface='org.mpris.MediaPlayer2.Player'"

# Monitor system bus (for Bluetooth, NM events)
dbus-monitor --system "interface='org.bluez.Device1'"
```

---

## 93.5 Scripting D-Bus from Shell

### Send a desktop notification

```bash
notify() {
  local title="$1" body="$2" icon="${3:-dialog-info}"
  busctl --user call \
    org.freedesktop.Notifications \
    /org/freedesktop/Notifications \
    org.freedesktop.Notifications Notify \
    susssasa{sv}i \
    "shell-script" 0 "$icon" "$title" "$body" 0 0 {} {} 3000
}

notify "Build Done" "cargo build finished in 4.2s" "emblem-default"
```

### Control MPRIS media player

```bash
# Find active MPRIS player
player=$(busctl --user list | grep "org.mpris.MediaPlayer2" | awk '{print $1}' | head -1)

# Pause/play
busctl --user call "$player" /org/mpris/MediaPlayer2 \
  org.mpris.MediaPlayer2.Player PlayPause

# Next track
busctl --user call "$player" /org/mpris/MediaPlayer2 \
  org.mpris.MediaPlayer2.Player Next

# Get current track info
busctl --user get-property "$player" /org/mpris/MediaPlayer2 \
  org.mpris.MediaPlayer2.Player Metadata
```

### Query UPower battery

```bash
# Get battery percentage
battery_path=$(busctl call \
  org.freedesktop.UPower /org/freedesktop/UPower \
  org.freedesktop.UPower EnumerateDevices \
  2>/dev/null | grep -o '/org/freedesktop/UPower/devices/battery[^"]*')

percent=$(busctl get-property \
  org.freedesktop.UPower "$battery_path" \
  org.freedesktop.UPower.Device Percentage 2>/dev/null | awk '{print $2}')

echo "Battery: ${percent}%"
```

### NetworkManager status

```bash
# Get current connection state
busctl call org.freedesktop.NetworkManager \
  /org/freedesktop/NetworkManager \
  org.freedesktop.NetworkManager state

# Get active SSID
busctl call org.freedesktop.NetworkManager \
  /org/freedesktop/NetworkManager \
  org.freedesktop.NetworkManager GetAllDevices
```

---

## 93.6 Writing a D-Bus Service from Shell

For scripts that need to expose a D-Bus API (e.g., a Quickshell component
that triggers shell actions):

```bash
#!/bin/bash
# Simple D-Bus service that accepts commands
# Start with: dbus-run-session ./my-service.sh  (for testing)
# Or register on existing session bus

dbus-daemon --session --address="unix:path=/tmp/test-bus" --print-address &
export DBUS_SESSION_BUS_ADDRESS="unix:path=/tmp/test-bus"

# Use dbus-send to reply (simplified pattern)
# For real services, use python-dbus or dbus-glib
```

**Python is more practical for D-Bus services:**

```python
#!/usr/bin/env python3
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

class RicingController(dbus.service.Object):
    def __init__(self):
        bus = dbus.SessionBus()
        bus.request_name("org.ricing.Controller")
        super().__init__(bus, "/org/ricing/Controller")

    @dbus.service.method("org.ricing.Controller",
                         in_signature="s", out_signature="s")
    def SetShader(self, shader_name):
        import subprocess
        if shader_name == "":
            subprocess.run(["hyprctl", "keyword", "decoration:screen_shader", ""])
        else:
            path = f"/home/user/.config/hypr/shaders/{shader_name}.frag"
            subprocess.run(["hyprctl", "keyword", "decoration:screen_shader", path])
        return f"Set shader: {shader_name}"

    @dbus.service.signal("org.ricing.Controller", signature="s")
    def ShaderChanged(self, shader_name):
        pass

controller = RicingController()
GLib.MainLoop().run()
```

Call from shell:
```bash
busctl --user call org.ricing.Controller /org/ricing/Controller \
  org.ricing.Controller SetShader s "crt"
```

---

## 93.7 D-Bus in Quickshell

Quickshell's `DBusMenu` module handles StatusNotifierItem tray menus.
For arbitrary D-Bus calls from QML, use the `Process` type to call `busctl`:

```qml
import Quickshell.Io

// Control MPRIS from QML
Process {
    id: mprisNext
    command: ["busctl", "--user", "call",
              "org.mpris.MediaPlayer2.mpv",
              "/org/mpris/MediaPlayer2",
              "org.mpris.MediaPlayer2.Player", "Next"]
}

// Trigger via:
// mprisNext.startDetached()
```

For property monitoring, use `IpcHandler` with `dbus-monitor` piped through:
```qml
Process {
    id: dbusMonitor
    command: ["dbus-monitor", "--session",
              "interface='org.mpris.MediaPlayer2.Player'"]
    running: true
    stdout: StdioCollector {
        onStreamedLine: line => {
            // parse D-Bus event lines
        }
    }
}
```

---

## 93.8 Varlink — The D-Bus Successor for System Services

Varlink is systemd's newer IPC protocol for system-level services. It uses
Unix sockets with a JSON-based type system. It is **not replacing session-bus
D-Bus** for desktop services — notifications, MPRIS, and portals will stay on
D-Bus. Varlink targets: systemd services, `io.systemd.*` interfaces, and new
kernel/userspace boundaries. For a full treatment of Varlink services, the wire
format, and writing clients and servers, see **Ch 98**.

### What uses Varlink today

```
io.systemd.Journal          — journald log streaming
io.systemd.Resolve          — systemd-resolved DNS
io.systemd.UserDatabase     — NSS user/group lookups
io.systemd.Network          — networkd link management
io.systemd.MachineRegistry  — container/VM registry
io.systemd.oom              — oomd pressure events
```

### Querying Varlink from the CLI

```bash
# Install varlink CLI tool
paru -S varlink-cli   # or: cargo install varlink-cli

# Connect to a Varlink service
varlink call unix:/run/systemd/resolve/io.systemd.Resolve \
  io.systemd.Resolve.ResolveHostname '{"name":"archlinux.org","ifindex":0,"family":2}'

# Using varlinkctl (from systemd 256+)
varlinkctl introspect /run/systemd/resolve/io.systemd.Resolve \
  io.systemd.Resolve

varlinkctl call /run/systemd/resolve/io.systemd.Resolve \
  io.systemd.Resolve.ResolveHostname \
  '{"name":"archlinux.org","family":2}'
```

### Varlink interface definition (IDL)

Varlink uses a simple IDL for interface definitions (`.varlink` files):

```varlink
# Example interface
interface io.example.Ricing

type ShaderInfo (
    name: string,
    active: bool
)

method GetShader() -> (shader: ShaderInfo)
method SetShader(name: string) -> ()

error InvalidShader (name: string)
```

### When to use Varlink vs D-Bus

As a quick rule of thumb: use **D-Bus** for anything desktop/session-facing
(notifications, MPRIS, portals, system tray, Quickshell services) and
**Varlink** for new system-level services and existing `io.systemd.*`
interfaces (DNS resolution, journal streaming, user database). See
**Ch 98 §98.8** for the full decision guide with a comprehensive comparison
table.

---

## 93.9 dbus-run-session — Headless D-Bus Testing

```bash
# Start a fresh session bus for testing (isolated from your running session)
dbus-run-session bash

# Inside: your tests have a clean session bus
busctl --user list   # shows only the default services

# Run a test notification daemon
dbus-run-session -- mako &
dbus-run-session -- busctl --user call \
  org.freedesktop.Notifications ... Notify ...
```

Useful for CI testing of D-Bus services without polluting the running session.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
