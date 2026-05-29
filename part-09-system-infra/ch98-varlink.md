# Chapter 98 — Varlink: Modern IPC for System Services

## Overview

Varlink is a typed, interface-oriented IPC protocol developed alongside systemd.
It uses Unix sockets with null-byte-delimited JSON framing (for `io.systemd.*` services; some third-party implementations use newlines instead) — simpler than D-Bus
binary encoding, faster to implement, and designed for system services rather
than desktop session bus communication. This chapter covers the full protocol,
the IDL type system, the `io.systemd.*` service catalogue, writing services and
clients, and the practical question of when to use Varlink versus D-Bus.

---

## 98.1 Why Varlink Exists

D-Bus is excellent at what it does: broadcasting signals, introspecting a running
session, routing messages between arbitrary processes. But it carries significant
complexity: a separate daemon (`dbus-daemon`), a binary wire format, XML introspection
documents, and a connection model oriented around sessions.

For system services that need simple, fast, type-safe RPC between exactly two
processes — a daemon and its client — D-Bus is overbuilt. Varlink was designed
for this narrower problem:

- **Simple wire format**: newline-delimited JSON, directly human-readable
- **No daemon required**: direct Unix socket connection, point-to-point
- **Typed IDL**: interfaces defined once, bindings generated for any language
- **Streaming support**: methods can stream multiple replies
- **Socket activation**: integrates natively with systemd socket units
- **Versioned interfaces**: interface names are reverse-DNS URIs (`io.systemd.Resolve`)

Varlink is not a replacement for D-Bus for desktop services. MPRIS, system tray,
notifications, and portals will stay on D-Bus. Varlink targets the system layer:
`systemd-resolved`, `systemd-journal`, `systemd-networkd`, NSS lookups, OOM
management.

---

## 98.2 Architecture

```
Client process
    │  connect(2) to Unix socket path
    ▼
Varlink socket  (e.g. /run/systemd/resolve/io.systemd.Resolve)
    │  read/write null-byte-delimited JSON (io.systemd.* services)
    ▼
Service process (systemd-resolved, user daemon, etc.)
    │  implements io.systemd.Resolve interface
    ▼
Response JSON  → client parses typed struct
```

There is no central broker. The client connects directly to the service's socket.
Socket paths follow the convention: `/run/<daemon>/<interface-name>`.

### Wire format

A Varlink call is a single JSON object on one line:

```json
{"method":"io.systemd.Resolve.ResolveHostname","parameters":{"name":"archlinux.org","family":2},"more":false}
```

A response:
```json
{"parameters":{"addresses":[{"family":2,"address":[95,216,183,27],"ifindex":2}],"name":"archlinux.org","flags":0}}
```

Streaming responses use `"continues":true` on intermediate replies and omit it
on the final reply. Errors use `"error":"io.systemd.Resolve.NoSuchResourceRecord"`.

---

## 98.3 Varlink IDL

Interfaces are defined in `.varlink` files. The IDL has a small, regular syntax.

### Basic interface structure

```varlink
# A comment
interface io.example.Ricing

# Type definitions
type ColorScheme (
    name: string,
    primary: string,
    secondary: string,
    background: string,
    foreground: string
)

type ShaderInfo (
    name: string,
    path: ?string,    # ? prefix = optional (nullable)
    active: bool
)

# Method: takes parameters, returns parameters
method GetActiveScheme() -> (scheme: ColorScheme)
method SetShader(name: string) -> ()
method ListShaders() -> (shaders: []ShaderInfo)    # array return

# Streaming method (client passes "more": true, server sends multiple replies)
method StreamEvents() -> (event: string, data: string)

# Error types
error SchemeNotFound (name: string)
error InvalidShader (path: string, reason: string)
```

### Type system

| Type | Example | Notes |
|------|---------|-------|
| `string` | `"hello"` | UTF-8 string |
| `int` | `42` | 64-bit signed integer |
| `float` | `3.14` | 64-bit float |
| `bool` | `true` / `false` | boolean |
| `?T` | `?string` | nullable / optional |
| `[]T` | `[]string` | array |
| `[string]T` | `[string]int` | map (string keys) |
| `(...)` | inline struct | anonymous struct |
| enum | `(a, b, c)` used as type | enumeration |

### Struct definitions

```varlink
type Address (
    family: int,       # 2=IPv4, 10=IPv6
    address: []int,    # octets
    ifindex: ?int
)

type ResolveResult (
    addresses: []Address,
    name: string,
    flags: int,
    canonical: ?string
)
```

### Error definitions

Errors are typed. The client can match on the error name string:

```varlink
error NoSuchResourceRecord ()
error DNSError (rcode: int)
error AllProtocolsFailed (last_error: ?string)
```

---

## 98.4 varlinkctl — The CLI Client

`varlinkctl` is included in systemd 256+ (Arch: `pacman -S systemd`, always present).

```bash
# Introspect a service — show all methods and types
varlinkctl introspect /run/systemd/resolve/io.systemd.Resolve

# Call a method with parameters
varlinkctl call /run/systemd/resolve/io.systemd.Resolve \
  io.systemd.Resolve.ResolveHostname \
  '{"name":"archlinux.org","family":2,"ifindex":0,"flags":0}'

# Call and format output with jq
varlinkctl call /run/systemd/resolve/io.systemd.Resolve \
  io.systemd.Resolve.ResolveHostname \
  '{"name":"archlinux.org","family":2}' | jq '.addresses[].address'

# Streaming call (server sends multiple replies)
varlinkctl call --more /run/systemd/journal/io.systemd.Journal \
  io.systemd.Journal.Subscribe \
  '{"last_seqnum":0}'

# List available Varlink services on the system
varlinkctl list-interfaces

# Discover socket paths
ls /run/systemd/*/io.systemd.*
```

### Older approach: varlink-tool

Before `varlinkctl`, the community tool was `varlink-tool`:

```bash
paru -S varlink-tool  # if available; varlinkctl is preferred

varlink call \
  unix:/run/systemd/resolve/io.systemd.Resolve \
  io.systemd.Resolve.ResolveHostname \
  '{"name":"archlinux.org"}'
```

---

## 98.5 The `io.systemd.*` Service Catalogue

### io.systemd.Resolve (systemd-resolved)

Socket: `/run/systemd/resolve/io.systemd.Resolve`

```bash
# Resolve a hostname
varlinkctl call /run/systemd/resolve/io.systemd.Resolve \
  io.systemd.Resolve.ResolveHostname \
  '{"name":"archlinux.org","family":2,"flags":0}'

# Reverse DNS lookup
varlinkctl call /run/systemd/resolve/io.systemd.Resolve \
  io.systemd.Resolve.ResolveAddress \
  '{"address":[8,8,8,8],"family":2,"flags":0}'

# Resolve a service record (SRV)
varlinkctl call /run/systemd/resolve/io.systemd.Resolve \
  io.systemd.Resolve.ResolveService \
  '{"name":"_xmpp._tcp.example.com","flags":0}'

# Get DNS server status
varlinkctl call /run/systemd/resolve/io.systemd.Resolve \
  io.systemd.Resolve.GetStatus \
  '{}'
```

Key methods: `ResolveHostname`, `ResolveAddress`, `ResolveRecord`, `ResolveService`,
`GetStatus`, `SetLinkDNS`, `FlushCaches`.

### io.systemd.Journal (systemd-journald)

Socket: `/run/systemd/journal/io.systemd.Journal`

```bash
# Stream new journal entries (streaming method)
varlinkctl call --more /run/systemd/journal/io.systemd.Journal \
  io.systemd.Journal.Subscribe \
  '{"last_seqnum":0}' | jq '.message // empty'

# Get journal entries matching a filter
varlinkctl call /run/systemd/journal/io.systemd.Journal \
  io.systemd.Journal.Query \
  '{"matches":["_SYSTEMD_UNIT=hyprland.service"],"n_entries":20}'
```

### io.systemd.Network (systemd-networkd)

Socket: `/run/systemd/netif/io.systemd.Network`

```bash
# List network links
varlinkctl call /run/systemd/netif/io.systemd.Network \
  io.systemd.Network.ListLinks '{}'

# Get link status (replace 2 with your interface index from ip link)
varlinkctl call /run/systemd/netif/io.systemd.Network \
  io.systemd.Network.GetLinkStatus \
  '{"index":2}'

# Reconfigure a link
varlinkctl call /run/systemd/netif/io.systemd.Network \
  io.systemd.Network.Reconfigure \
  '{"index":2}'
```

### io.systemd.UserDatabase (systemd-userdbd)

Socket: `/run/systemd/userdb/io.systemd.UserDatabase`

```bash
# Get all users (streaming)
varlinkctl call --more /run/systemd/userdb/io.systemd.UserDatabase \
  io.systemd.UserDatabase.GetUserRecord \
  '{"service":"io.systemd.NameServiceSwitch"}'

# Get a specific user
varlinkctl call /run/systemd/userdb/io.systemd.UserDatabase \
  io.systemd.UserDatabase.GetUserRecord \
  '{"userName":"alice","service":"io.systemd.NameServiceSwitch"}'
```

### io.systemd.MachineRegistry (systemd-machined)

```bash
# List running containers and VMs
varlinkctl call /run/systemd/machine/io.systemd.MachineRegistry \
  io.systemd.MachineRegistry.List '{}'
```

### io.systemd.oom (systemd-oomd)

Socket: `/run/systemd/oomd/io.systemd.oom`

```bash
# Get OOM memory pressure status
varlinkctl call /run/systemd/oomd/io.systemd.oom \
  io.systemd.oom.DumpByMachineID '{}'
```

---

## 98.6 Writing a Varlink Service

### Shell / bash client (scripting)

Shell can speak Varlink directly using `socat` or `nc` since the wire format
is just newline-delimited JSON:

```bash
#!/bin/bash
# varlink-call.sh — minimal varlink client
SOCKET="$1"
METHOD="$2"
PARAMS="${3:-{}}"

printf '{"method":"%s","parameters":%s}\n' "$METHOD" "$PARAMS" \
  | socat - UNIX-CONNECT:"$SOCKET" \
  | head -1
```

```bash
# Usage:
./varlink-call.sh \
  /run/systemd/resolve/io.systemd.Resolve \
  io.systemd.Resolve.ResolveHostname \
  '{"name":"archlinux.org","family":2}'
```

### Python client

```python
#!/usr/bin/env python3
import socket, json, os

def varlink_call(sock_path: str, method: str, params: dict) -> dict:
    """Make a single Varlink call and return the response."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.connect(sock_path)
        payload = json.dumps({"method": method, "parameters": params}) + "\0"
        s.sendall(payload.encode())
        buf = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk
            if b"\0" in buf:
                break
        response_bytes = buf.split(b"\0")[0]
        return json.loads(response_bytes)

# Resolve a hostname
result = varlink_call(
    "/run/systemd/resolve/io.systemd.Resolve",
    "io.systemd.Resolve.ResolveHostname",
    {"name": "archlinux.org", "family": 2, "flags": 0}
)

for addr in result.get("parameters", {}).get("addresses", []):
    print(".".join(str(b) for b in addr["address"]))
```

> **Note:** The wire format uses `\0` (null byte) as the message delimiter in
> some implementations, and `\n` in others. systemd's services use `\0`.
> `varlinkctl` handles this transparently.

### Rust service (using the `varlink` crate)

```rust
// Cargo.toml
// [dependencies]
// varlink = "11"
// serde = { version = "1", features = ["derive"] }
// serde_json = "1"

use varlink::{Connection, VarlinkService};

// Define the interface programmatically or generate from .varlink file
// using varlink_generator in build.rs

// With varlink_generator:
// build.rs:
//   varlink_generator::Generator::new("src/io.example.ricing.varlink")
//     .generate_to_out_dir();

include!(concat!(env!("OUT_DIR"), "/io.example.ricing.rs"));

struct RicingService;

impl VarlinkInterface for RicingService {
    fn get_active_scheme(
        &self,
        call: &mut dyn Call_GetActiveScheme,
    ) -> varlink::Result<()> {
        call.reply(ColorScheme {
            name: "catppuccin-mocha".into(),
            primary: "#cba6f7".into(),
            secondary: "#89b4fa".into(),
            background: "#1e1e2e".into(),
            foreground: "#cdd6f4".into(),
        })
    }

    fn set_shader(
        &self,
        call: &mut dyn Call_SetShader,
        name: String,
    ) -> varlink::Result<()> {
        // Apply shader via hyprctl
        std::process::Command::new("hyprctl")
            .args(["keyword", "decoration:screen_shader",
                   &format!("~/.config/hypr/shaders/{}.frag", name)])
            .status().ok();
        call.reply()
    }
}

fn main() {
    let service = VarlinkService::new(
        "io.example",
        "Ricing Controller",
        "1.0",
        "https://github.com/example/ricing-varlink",
        vec![Box::new(io_example_ricing::new(Box::new(RicingService)))],
    );
    varlink::listen(service, &"unix:/run/user/1000/io.example.ricing", 1, 1, 0)
        .expect("varlink listen failed");
}
```

### Go service

```go
// Minimal Go Varlink service using the varlink-go package
package main

import (
    "github.com/varlink/go/varlink"
    "context"
)

func main() {
    service, _ := varlink.NewService(
        "io.example", "Ricing", "1.0", "https://example.com",
    )

    service.RegisterInterface(varlink.NewInterface(
        "io.example.ricing",
        `interface io.example.ricing
method GetWallpaper() -> (path: string)`,
        varlink.MethodHandler("io.example.ricing.GetWallpaper",
            func(ctx context.Context, call varlink.Call) error {
                return call.Reply(&struct {
                    Path string `json:"path"`
                }{Path: "/home/user/wallpapers/current.jpg"})
            }),
    ))

    service.Listen(context.Background(), "unix:/run/user/1000/io.example.ricing")
}
```

---

## 98.7 Socket Activation with systemd

Varlink services integrate cleanly with systemd socket activation — the
service starts on first connection:

```ini
# /etc/systemd/user/io.example.ricing.socket
[Unit]
Description=Ricing Controller Varlink Socket

[Socket]
ListenStream=%t/io.example.ricing
SocketMode=0660

[Install]
WantedBy=sockets.target
```

```ini
# /etc/systemd/user/io.example.ricing.service
[Unit]
Description=Ricing Controller Varlink Service
Requires=io.example.ricing.socket
After=io.example.ricing.socket

[Service]
Type=notify
ExecStart=/usr/local/bin/ricing-varlink-service
StandardError=journal
```

Enable:
```bash
systemctl --user enable --now io.example.ricing.socket
# Service starts automatically on first varlinkctl call
```

In the IDL, mark the interface as socket-activated:
```varlink
interface io.example.ricing
# SystemdActivation = true  (set via generator, not in IDL syntax directly)
```

---

## 98.8 Varlink vs D-Bus Decision Guide

| Requirement | Use Varlink | Use D-Bus |
|-------------|-------------|-----------|
| Point-to-point RPC to a system daemon | ✅ | — |
| Broadcast signals to multiple subscribers | — | ✅ |
| Desktop notification (org.freedesktop.Notifications) | — | ✅ |
| MPRIS media control | — | ✅ |
| System tray (StatusNotifierItem) | — | ✅ |
| Portal access (xdg-desktop-portal) | — | ✅ |
| DNS resolution | ✅ (systemd-resolved) | — |
| Journal log streaming | ✅ (io.systemd.Journal) | — |
| New system service (2025+) | ✅ (preferred) | — |
| Introspection / service discovery at runtime | — | ✅ |
| Scripting from bash | Both (varlinkctl / busctl) | Both |
| Language binding availability | C, C++, Rust, Go, Python, JS | Broader (any language) |
| Wire format human-readable | ✅ JSON | — (binary) |
| Requires session daemon | ❌ No | ✅ (dbus-daemon) |

**Practical summary**: For new system-level daemons in 2025, Varlink is the
better choice. For anything touching the desktop session (notifications, MPRIS,
trays, portals), D-Bus is the only practical option and will remain so.

---

## 98.9 Monitoring Varlink Traffic

```bash
# Capture all Varlink traffic on a socket (requires strace or eBPF)
strace -e trace=read,write -p $(pgrep systemd-resolved) 2>&1 \
  | grep -a '\\n' | head -20

# Or use socket sniffing with socat proxy:
# 1. Move original socket aside
mv /run/systemd/resolve/io.systemd.Resolve /run/systemd/resolve/io.systemd.Resolve.real

# 2. Create transparent proxy that logs
socat -v UNIX-LISTEN:/run/systemd/resolve/io.systemd.Resolve,fork \
  UNIX-CONNECT:/run/systemd/resolve/io.systemd.Resolve.real 2>&1 \
  | tee /tmp/varlink-trace.log

# Restore when done:
mv /run/systemd/resolve/io.systemd.Resolve.real /run/systemd/resolve/io.systemd.Resolve
```

---

## 98.10 Varlink in the Ricing Context

Most ricing workflows interact with Varlink indirectly — `resolvectl`,
`networkctl`, and `journalctl` are high-level wrappers around Varlink calls.
Direct Varlink use becomes relevant when:

1. **Building a Quickshell network monitor** — poll `io.systemd.Network.GetLinkStatus`
   for live link state and IP address without running `ip` as a subprocess
2. **Streaming journal to a status bar** — subscribe to `io.systemd.Journal.Subscribe`
   for live log output in a terminal widget
3. **Writing a custom system service** — any new daemon you write that needs
   to expose an API should use Varlink rather than D-Bus for the reasons above
4. **DNS-based scripting** — query `io.systemd.Resolve` from shell scripts
   instead of parsing `dig` or `host` output

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
