# Chapter 138 — xdg-activation-v1: Focus Stealing Prevention

## Contents

- [Overview](#overview)
- [138.1 The Problem: Focus Stealing on X11 vs Wayland](#1381-the-problem-focus-stealing-on-x11-vs-wayland)
- [138.2 Protocol Architecture](#1382-protocol-architecture)
- [138.3 Token Lifecycle](#1383-token-lifecycle)
- [138.4 Application Support](#1384-application-support)
  - [GTK4](#gtk4)
  - [Qt6](#qt6)
  - [D-Bus Activation (XDG Portal)](#d-bus-activation-xdg-portal)
  - [Terminal Apps via DESKTOP_STARTUP_ID](#terminal-apps-via-desktopstartupid)
- [138.5 Writing a Client (Python + pywayland)](#1385-writing-a-client-python-pywayland)
- [138.6 Compositor Implementation Status](#1386-compositor-implementation-status)
- [138.7 Debugging Focus Activation](#1387-debugging-focus-activation)
- [138.8 Window Rules: noinitialfocus](#1388-window-rules-noinitialfocus)
- [138.9 XDG Activation vs EWMH (X11 Legacy)](#1389-xdg-activation-vs-ewmh-x11-legacy)

---


## Overview

One of Wayland's strongest security improvements over X11 is that applications cannot arbitrarily steal focus. On X11, any process could call `_NET_ACTIVE_WINDOW` and bring itself to the foreground. Wayland forbids this at the protocol level: a window can only gain focus if the user or the compositor grants it an **activation token**. The `xdg-activation-v1` protocol is the mechanism that apps use to legitimately request focus — it is how clicking a link in a terminal raises the browser, how a file manager raises an already-open editor, and how notifications can focus a specific window on user interaction.

**Cross-references:** Ch 03 — protocol extensions overview. Ch 52 — xdg-desktop-portal (related portal protocol). Ch 131 — window rules (`noinitialfocus` action). Ch 65 — the Wayland security model.

---

## 138.1 The Problem: Focus Stealing on X11 vs Wayland

```
X11 world:
  Any process → XSendEvent(_NET_ACTIVE_WINDOW) → window gets focus
  No authentication. Any background app can steal focus mid-typing.

Wayland world:
  Client A wants focus for Client B → needs a token
  Token is issued by compositor only when triggered by user input
  Token has a short lifetime (~seconds)
  Only the compositor honors the token
```

This is why you may see notifications "waiting" for the user to act rather than immediately stealing focus, and why some older apps (built for X11) fail to raise themselves on Wayland.

---

## 138.2 Protocol Architecture

The `xdg-activation-v1` protocol lives in `xdg-activation-v1.xml` (part of wayland-protocols):

```
xdg_activation_v1 (global interface)
  ├── get_activation_token() → xdg_activation_token_v1
  │     ├── set_serial(serial, seat)   ← links token to user input event
  │     ├── set_app_id(app_id)         ← app requesting focus
  │     ├── set_surface(surface)       ← surface requesting focus (optional)
  │     ├── commit()                   ← finalize; triggers "done" event
  │     └── event: done(token_str)     ← string token to pass to target app
  └── activate(token_str, surface)     ← request focus for surface using token
```

Key constraint: `set_serial` links the token to a **seat input event** (keyboard keypress, button press). This proves the request originated from a user action. Without a valid serial, compositors may reject the token.

---

## 138.3 Token Lifecycle

```
1. User presses Ctrl+Click in terminal (generates input serial S)
2. Terminal calls xdg_activation_v1.get_activation_token()
3. Terminal calls set_serial(S, seat) on the token
4. Terminal calls set_app_id("org.mozilla.firefox")
5. Terminal calls commit()
6. Compositor sends done(token="abc123def")
7. Terminal passes "abc123def" to Firefox via IPC/CLI/env var
8. Firefox calls xdg_activation_v1.activate("abc123def", its_surface)
9. Compositor verifies token is valid, raises Firefox window
```

Tokens are single-use and expire (typically within a few seconds).

---

## 138.4 Application Support

### GTK4

GTK4 handles xdg-activation automatically when you use `gtk_window_present()` or `gtk_show_uri()`. The framework manages token acquisition and passing transparently.

```c
// GTK4 — raise a window in response to user action
gtk_window_present(GTK_WINDOW(other_window));
// GTK4 internally acquires an activation token and activates the window
```

### Qt6

Qt6 supports xdg-activation via `QWindow::requestActivate()`:

```cpp
// Qt6
QWindow *window = ...;
window->requestActivate();  // uses xdg-activation internally on Wayland
```

### D-Bus Activation (XDG Portal)

Applications launched via D-Bus (e.g., from a .desktop file or `gio open`) receive activation tokens through the `org.freedesktop.portal.Activation` interface:

```bash
# Launch an app with focus via D-Bus (portal handles the token)
gdbus call --session \
    --dest org.freedesktop.portal.Desktop \
    --object-path /org/freedesktop/portal/desktop \
    --method org.freedesktop.portal.OpenURI.OpenURI \
    "" "https://example.com" \
    "{'activation_token': <'your-token'>}"
```

### Terminal Apps via DESKTOP_STARTUP_ID

The legacy `DESKTOP_STARTUP_ID` environment variable carries activation tokens for apps launched by file managers and launchers:

```bash
# A launcher sets this before exec'ing the app:
export DESKTOP_STARTUP_ID="$activation_token"
exec firefox "$url"

# The app reads it and uses it to activate
```

Modern apps read `XDG_ACTIVATION_TOKEN` (the newer standard env var):

```bash
export XDG_ACTIVATION_TOKEN="abc123def"
exec some-app
```

---

## 138.5 Writing a Client (Python + pywayland)

A minimal Python client that requests an activation token and passes it to another process:

```python
#!/usr/bin/env python3
"""Request an xdg-activation token and print it."""
import os, sys
from pywayland.client import Display
from pywayland.protocol.xdg_activation_v1 import XdgActivationV1
from pywayland.protocol.wayland import WlSeat

class Activator:
    def __init__(self):
        self.display = Display()
        self.display.connect()
        self.registry = self.display.get_registry()
        self.activation = None
        self.seat = None
        self.token = None

        @self.registry.dispatcher["global"]
        def on_global(reg, name, iface, version):
            if iface == "xdg_activation_v1":
                self.activation = reg.bind(name, XdgActivationV1, version)
            elif iface == "wl_seat":
                self.seat = reg.bind(name, WlSeat, version)

        self.display.roundtrip()
        if not self.activation:
            raise RuntimeError("xdg_activation_v1 not available")

    def get_token(self, app_id: str) -> str:
        tok = self.activation.get_activation_token()
        tok.set_app_id(app_id)
        # Note: without set_serial, some compositors may reject the token
        # For a user-triggered flow, pass the input serial here:
        # tok.set_serial(serial, self.seat)
        tok.commit()

        result = []

        @tok.dispatcher["done"]
        def on_done(token_obj, token_str):
            result.append(token_str)
            token_obj.destroy()

        self.display.roundtrip()
        return result[0] if result else ""

    def activate(self, token: str, surface):
        """Activate a surface using a previously obtained token."""
        self.activation.activate(token, surface)
        self.display.roundtrip()

    def close(self):
        self.display.disconnect()


if __name__ == "__main__":
    app_id = sys.argv[1] if len(sys.argv) > 1 else "org.mozilla.firefox"
    act = Activator()
    token = act.get_token(app_id)
    print(token)   # pass to target app via env var or IPC
    act.close()
```

Usage:
```bash
TOKEN=$(python3 get_activation_token.py org.mozilla.firefox)
XDG_ACTIVATION_TOKEN="$TOKEN" firefox
```

---

## 138.6 Compositor Implementation Status

| Compositor | xdg-activation-v1 | Notes |
|---|---|---|
| **Hyprland** | Yes | Full support; tokens tied to input events |
| **Sway** | Yes | Full support |
| **KWin** | Yes | Full support (KDE Plasma 6) |
| **GNOME Shell** | Yes | Full support |
| **Niri** | Yes | Supported |
| **River** | Partial | Basic support |
| **Wayfire** | Yes | Via wlroots |
| **labwc** | Yes | Via wlroots |

---

## 138.7 Debugging Focus Activation

```bash
# See xdg-activation protocol traffic
WAYLAND_DEBUG=1 firefox 2>&1 | grep -i "xdg_activation"

# Monitor activation events in real-time
WAYLAND_DEBUG=xdg_activation_v1 yourapp 2>&1

# Hyprland — check if a window received focus from activation
hyprctl activewindow   # see which window is focused

# Test: does the app correctly read XDG_ACTIVATION_TOKEN?
XDG_ACTIVATION_TOKEN=testtoken yourapp
# (compositor will reject "testtoken" as invalid, but the app should not crash)
```

---

## 138.8 Window Rules: noinitialfocus

Compositors provide a way to suppress unwanted focus via window rules, which is the practical "focus-stealing prevention" tool for ricers:

```ini
# Hyprland — prevent these apps from stealing focus when they open
windowrulev2 = noinitialfocus, class:^(steam|discord|telegram-desktop)$
windowrulev2 = noinitialfocus, class:^(dunst|mako)$  # notification popups

# Global focus-on-activate suppression
misc {
    focus_on_activate = false  # true = allow xdg-activation requests
                               # false = ignore them (mark as urgent instead)
}
```

With `focus_on_activate = false`, Hyprland still marks activated windows as urgent (they flash in the task bar if you have one) but does not switch to them automatically.

```bash
# Sway equivalent
# No global flag; use for_window inhibit
for_window [app_id="discord"] focus
# To deny focus: there's no direct "inhibit focus" in Sway
# Use: no_focus [app_id="discord"]
no_focus [app_id="^(telegram-desktop|discord)$"]
```

---

## 138.9 XDG Activation vs EWMH (X11 Legacy)

When XWayland apps request focus via the legacy `_NET_ACTIVE_WINDOW` EWMH hint:

- XWayland translates the EWMH request to an `xdg-activation-v1` request internally
- The compositor applies the same token-based validation
- Apps that relied on unconditional X11 focus stealing will find requests denied or treated as urgent

```bash
# Check if an app is going through XWayland
xlsclients -display :0 2>/dev/null | grep appname
# If listed: it's an X11 app via XWayland
# If not listed: it's a native Wayland app
```
