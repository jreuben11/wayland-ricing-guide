# Chapter 125 — The data-control Protocol and Clipboard Scripting

## Overview

The `zwlr_data_control_manager_v1` protocol (wlr-data-control) gives privileged clients — clipboard managers, password managers, screenshot tools — programmatic read and write access to the Wayland clipboard and primary selection without requiring a focused window. This is the protocol that powers `wl-paste`, `wl-copy`, and `cliphist`. Understanding it enables writing custom clipboard tools, watchers, and transformers entirely in Wayland-native code.

**Cross-references:** Ch 32 — clipboard tools overview (`wl-clipboard`, `cliphist`). Ch 93 — D-Bus (alternative IPC for clipboard events). Ch 125 is the protocol implementation companion to Ch 32's user-facing guide.

---

## 125.1 Protocol Overview

`zwlr_data_control_manager_v1` exposes two operations:

```
zwlr_data_control_manager_v1
  ├── get_data_device(seat) → zwlr_data_control_device_v1
  │     ├── event: data_offer(offer)   — clipboard content changed
  │     ├── event: selection(offer)    — selection (primary) changed
  │     └── event: primary_selection(offer)
  └── create_data_source() → zwlr_data_control_source_v1
        ├── offer(mime_type)           — advertise MIME types
        └── event: send(mime_type, fd) — write content to fd
```

A **data offer** represents available clipboard content. The client reads it by calling `receive(mime_type, fd)` which causes the clipboard owner to write the content to the provided file descriptor.

A **data source** lets a client *own* the clipboard — it advertises MIME types and handles `send` requests when another app pastes.

---

## 125.2 Reading the Clipboard (Python + pywayland)

```python
#!/usr/bin/env python3
"""Read the current Wayland clipboard content."""
import os
import select
from pywayland.client import Display
from pywayland.protocol.wlr_data_control_unstable_v1 import (
    ZwlrDataControlManagerV1,
)
from pywayland.protocol.wayland import WlSeat

class ClipboardReader:
    def __init__(self):
        self.display = Display()
        self.display.connect()
        self.registry = self.display.get_registry()
        self.manager = None
        self.seat = None
        self.content = None

        @self.registry.dispatcher["global"]
        def on_global(registry, name, interface, version):
            if interface == "zwlr_data_control_manager_v1":
                self.manager = registry.bind(
                    name, ZwlrDataControlManagerV1, version
                )
            elif interface == "wl_seat":
                self.seat = registry.bind(name, WlSeat, version)

        self.display.roundtrip()
        assert self.manager and self.seat, "Protocol not available"

    def read(self) -> str | None:
        device = self.manager.get_data_device(self.seat)
        received = []

        @device.dispatcher["selection"]
        def on_selection(device, offer):
            if offer is None:
                received.append(None)
                return

            # Request the text/plain;charset=utf-8 MIME type
            r_fd, w_fd = os.pipe()
            offer.receive("text/plain;charset=utf-8", w_fd)
            os.close(w_fd)
            self.display.roundtrip()

            data = b""
            while True:
                ready, _, _ = select.select([r_fd], [], [], 1.0)
                if not ready:
                    break
                chunk = os.read(r_fd, 4096)
                if not chunk:
                    break
                data += chunk
            os.close(r_fd)
            received.append(data.decode("utf-8", errors="replace"))
            offer.destroy()

        self.display.roundtrip()
        return received[0] if received else None

    def close(self):
        self.display.disconnect()

if __name__ == "__main__":
    reader = ClipboardReader()
    content = reader.read()
    if content is not None:
        print(content, end="")
    reader.close()
```

---

## 125.3 Writing to the Clipboard

```python
#!/usr/bin/env python3
"""Write text to the Wayland clipboard."""
import os
import sys
from pywayland.client import Display
from pywayland.protocol.wlr_data_control_unstable_v1 import ZwlrDataControlManagerV1
from pywayland.protocol.wayland import WlSeat

def set_clipboard(text: str):
    display = Display()
    display.connect()
    registry = display.get_registry()
    manager = None
    seat = None

    @registry.dispatcher["global"]
    def on_global(registry, name, interface, version):
        nonlocal manager, seat
        if interface == "zwlr_data_control_manager_v1":
            manager = registry.bind(name, ZwlrDataControlManagerV1, version)
        elif interface == "wl_seat":
            seat = registry.bind(name, WlSeat, version)

    display.roundtrip()
    device = manager.get_data_device(seat)
    source  = manager.create_data_source()

    encoded = text.encode("utf-8")

    source.offer("text/plain;charset=utf-8")
    source.offer("text/plain")
    source.offer("UTF8_STRING")

    @source.dispatcher["send"]
    def on_send(source, mime_type, fd):
        try:
            os.write(fd, encoded)
        finally:
            os.close(fd)

    @source.dispatcher["cancelled"]
    def on_cancelled(source):
        # Another app took clipboard ownership
        source.destroy()
        display.disconnect()

    device.set_selection(source)
    display.roundtrip()

    # Keep running until cancelled (another app pastes)
    while True:
        display.dispatch()

if __name__ == "__main__":
    text = sys.stdin.read() if len(sys.argv) == 1 else " ".join(sys.argv[1:])
    set_clipboard(text)
```

---

## 125.4 Clipboard Watcher

A clipboard watcher invokes a callback every time the clipboard content changes:

```python
#!/usr/bin/env python3
"""Watch Wayland clipboard for changes and print new content."""
import os, select, subprocess, sys
from pywayland.client import Display
from pywayland.protocol.wlr_data_control_unstable_v1 import ZwlrDataControlManagerV1
from pywayland.protocol.wayland import WlSeat

def watch_clipboard(callback):
    display = Display()
    display.connect()
    registry = display.get_registry()
    manager = seat = None

    @registry.dispatcher["global"]
    def on_global(registry, name, interface, version):
        nonlocal manager, seat
        if interface == "zwlr_data_control_manager_v1":
            manager = registry.bind(name, ZwlrDataControlManagerV1, version)
        elif interface == "wl_seat":
            seat = registry.bind(name, WlSeat, version)

    display.roundtrip()
    device = manager.get_data_device(seat)

    def read_offer(offer, mime="text/plain;charset=utf-8"):
        r_fd, w_fd = os.pipe()
        offer.receive(mime, w_fd)
        os.close(w_fd)
        display.roundtrip()
        data = b""
        while select.select([r_fd], [], [], 0.5)[0]:
            chunk = os.read(r_fd, 4096)
            if not chunk: break
            data += chunk
        os.close(r_fd)
        offer.destroy()
        return data.decode("utf-8", errors="replace")

    @device.dispatcher["selection"]
    def on_selection(device, offer):
        if offer is None: return
        text = read_offer(offer)
        if text:
            callback(text)

    display.roundtrip()
    print("Watching clipboard...", file=sys.stderr)
    while True:
        display.dispatch()

if __name__ == "__main__":
    watch_clipboard(print)
```

---

## 125.5 cliphist: Production Clipboard History

`cliphist` is a production-ready clipboard history daemon built on data-control:

```bash
# Install
sudo pacman -S cliphist   # Arch
# or: cargo install cliphist

# Start the history daemon (add to compositor exec-once)
exec-once = wl-paste --type text --watch cliphist store
exec-once = wl-paste --type image --watch cliphist store

# Pick from history using fuzzel/rofi
bind = SUPER, V, exec, cliphist list | fuzzel --dmenu | cliphist decode | wl-copy
# or with rofi:
bind = SUPER, V, exec, cliphist list | rofi -dmenu | cliphist decode | wl-copy

# Clear history
cliphist wipe
```

cliphist stores entries in `~/.cache/cliphist/db` (sqlite3) and supports images, text, and arbitrary MIME types.

---

## 125.6 Primary Selection (Middle-Click Paste)

The primary selection (the Unix "middle-click to paste" clipboard) is a separate selection from the clipboard. The data-control protocol exposes it via `set_primary_selection` / `primary_selection` events on the device:

```bash
# Read primary selection (highlighted text)
wl-paste --primary

# Write primary selection
echo "selected text" | wl-copy --primary

# Sync clipboard → primary selection (bidirectional)
# Run as a background daemon:
wl-paste --watch wl-copy --primary &
wl-paste --primary --watch wl-copy &
```

---

## 125.7 wl-copy / wl-paste Quick Reference

```bash
# Copy stdin to clipboard
echo "hello" | wl-copy
wl-copy < file.txt
wl-copy "literal text"

# Copy with specific MIME type
wl-copy --type text/html < page.html
wl-copy --type image/png < image.png

# Paste clipboard
wl-paste                          # text/plain
wl-paste --type text/html         # specific MIME type
wl-paste --list-types             # list available MIME types
wl-paste --no-newline             # omit trailing newline

# Primary selection (highlighted text)
wl-paste --primary
echo "selected" | wl-copy --primary

# Watch for changes
wl-paste --watch cat              # print clipboard whenever it changes
wl-paste --type image/png --watch \
    sh -c 'cat > /tmp/latest-clip.png'  # save images automatically
```
