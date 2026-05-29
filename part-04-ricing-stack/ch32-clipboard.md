# Chapter 32 — Clipboard Management: wl-clipboard, cliphist

## Overview

Clipboard management on Wayland is architecturally different from X11, and understanding those differences is essential before reaching for tools. On X11, a persistent server (Xorg itself) retained clipboard content even after the source application exited. Wayland deliberately discards this model: the compositor is minimal, and clipboard content is owned by the *application*, not the compositor. When the application dies, its clipboard selection dies with it.

This chapter covers the canonical Wayland clipboard stack: `wl-clipboard` for low-level copy/paste, `cliphist` for persistent history, `copyq` for GUI-heavy workflows, and integration patterns across Hyprland, Sway, and Niri. We also examine primary selection semantics, MIME type handling, XWayland compatibility, and security considerations. By the end you will have a fully automated clipboard pipeline that survives application crashes, stores images, and surfaces history via your preferred launcher.

Cross-references: See Ch 24 for Hyprland `exec-once` startup. See Ch 35 for rofi/wofi/fuzzel launchers used as pickers. See Ch 53 for systemd user session startup alternatives.

---

## 32.1 Wayland Clipboard Architecture

Wayland's clipboard is defined by the `wl_data_device_manager` protocol and its extension `zwp_primary_selection_device_manager_v1`. When a client wants to offer data, it creates a `wl_data_source` object, advertises MIME types, and the compositor notifies the receiving client (the one with keyboard focus) via a `wl_data_offer`. The transfer itself happens over a pipe file descriptor — data is only transferred on demand, when the receiver actually requests it.

This lazy-evaluation design means clipboard content is never stored anywhere permanent by default. The moment the *offering* client is killed, the compositor drops the offer and paste returns nothing. For interactive desktop use this is tolerable when apps stay open, but it breaks any workflow that copies from a terminal, closes the terminal, and tries to paste elsewhere. `xclip` veterans encounter this constantly when first moving to Wayland.

There are three independent selection types to be aware of. The **clipboard selection** is the traditional Ctrl+C/Ctrl+V buffer. The **primary selection** is the X11-inherited concept where highlighted text is automatically placed in a separate buffer and pasted with the middle mouse button — many Wayland compositors support this via `zwp_primary_selection_device_manager_v1`. **Drag-and-drop** uses a third mechanism (`wl_data_device`) and is not persistent at all. Each selection type is independent: a clipboard manager must watch and store both clipboard and primary to provide full history.

Understanding MIME types matters for rich clipboard content. When a source advertises `text/plain;charset=utf-8` alongside `text/html`, a target application can choose which format to request. `wl-paste --list-types` shows what MIME types the current clipboard offer provides. Image applications typically offer `image/png`, while browsers often offer both `text/html` and `text/plain`. Your clipboard manager stores *all* offered types by default so decode fidelity is maintained.

```
# Inspect what the current clipboard is offering
wl-paste --list-types

# Example output when copying from a browser:
# text/html
# text/plain;charset=utf-8
# text/plain
```

---

## 32.2 wl-clipboard — The Core Tool

`wl-clipboard` provides two binaries: `wl-copy` and `wl-paste`. They are the standard low-level interface to the Wayland clipboard from the terminal and from scripts. Install them first — every other tool in this chapter depends on or interoperates with them.

```bash
# Arch Linux
sudo pacman -S wl-clipboard

# Debian/Ubuntu (24.04+)
sudo apt install wl-clipboard

# Fedora
sudo dnf install wl-clipboard

# Verify
wl-copy --version
wl-paste --version
```

**Writing to the clipboard** is straightforward. `wl-copy` reads from stdin or takes an argument. It then enters an event loop holding the selection until another client takes it or it is killed. This is why `wl-copy` appears to "hang" in a terminal — it is the source process that keeps the clipboard alive.

```bash
# Copy a string literal
wl-copy "Hello, Wayland"

# Copy file contents
wl-copy < ~/.ssh/id_ed25519.pub

# Copy with explicit MIME type (for rich content)
wl-copy --type text/html < snippet.html

# Copy an image
wl-copy --type image/png < screenshot.png

# Copy to primary selection (middle-click buffer)
wl-copy --primary "middle-click this"

# Copy and immediately exit (clipboard dies when source app closes — use cliphist instead)
wl-copy --paste-once "one-time paste"
```

**Reading from the clipboard** via `wl-paste` is non-blocking by default. Use `--watch` to monitor for changes:

```bash
# Paste current clipboard text
wl-paste

# Paste without trailing newline
wl-paste --no-newline

# Paste a specific MIME type
wl-paste --type image/png > clipboard-image.png

# Paste from primary selection
wl-paste --primary

# Watch mode: print each new clipboard value as it changes
wl-paste --watch cat

# Watch and pipe new entries into cliphist (the standard pattern)
wl-paste --type text --watch cliphist store
```

A useful shell function for shell configs — converts clipboard to/from base64 for transferring binary blobs:

```bash
# ~/.config/zsh/functions.zsh or ~/.bashrc

clip-b64-encode() {
    wl-paste --no-newline | base64 | wl-copy
}

clip-b64-decode() {
    wl-paste --no-newline | base64 -d | wl-copy --type application/octet-stream
}

# Copy a file path to clipboard by dragging it from terminal
clip-path() {
    realpath "$1" | tr -d '\n' | wl-copy
    echo "Copied: $(wl-paste)"
}
```

**MIME type negotiation** matters when scripting clipboard interactions with heterogeneous apps. The following pattern gracefully degrades from HTML to plain text:

```bash
#!/usr/bin/env bash
# clipboard-text.sh — get text regardless of MIME type offered

TYPES=$(wl-paste --list-types 2>/dev/null)

if echo "$TYPES" | grep -q "text/plain;charset=utf-8"; then
    wl-paste --type "text/plain;charset=utf-8"
elif echo "$TYPES" | grep -q "text/plain"; then
    wl-paste --type "text/plain"
elif echo "$TYPES" | grep -q "text/html"; then
    # Strip HTML tags via sed as a last resort
    wl-paste --type "text/html" | sed 's/<[^>]*>//g'
else
    echo "No usable text type in clipboard" >&2
    exit 1
fi
```

---

## 32.3 cliphist — Clipboard History

`cliphist` is a minimal, fast clipboard history daemon written in Go. It monitors clipboard changes via `wl-paste --watch`, stores entries in a SQLite database at `~/.cache/cliphist/db`, and exposes them for picker integration. It handles both text and binary (image) clipboard entries transparently.

```bash
# Install from source (requires Go)
go install go.senan.xyz/cliphist@latest

# Arch Linux AUR
yay -S cliphist

# Nix
nix-env -iA nixpkgs.cliphist
```

**Daemon setup** requires two watchers — one for text MIME types and one for images. Both should be started at compositor launch:

```bash
# Start text watcher (run at login)
wl-paste --type text --watch cliphist store &

# Start image watcher
wl-paste --type image --watch cliphist store &
```

These watchers block and must be run as background jobs or as compositor `exec-once` directives. Each time the clipboard changes with a compatible MIME type, `cliphist store` appends the new entry to the database with a timestamp and the raw bytes.

**Database configuration** is done via environment variables:

```bash
# ~/.config/environment.d/cliphist.conf (systemd user env)
# or export these in ~/.profile / ~/.zprofile

CLIPHIST_MAX_ITEMS=750          # maximum entries (default: 750)
CLIPHIST_MAX_DEDUPE_SEARCH=100  # deduplication window (default: 100)
```

**Querying and managing history:**

```bash
# List all history entries (ID \t preview)
cliphist list

# Example output:
# 1	Hello, Wayland
# 2	https://example.com/some-url
# 3	[[ binary data image/png 48.2 KiB ]]

# Decode entry by its raw list line (pipe from picker)
echo "2	https://example.com/some-url" | cliphist decode

# Decode and copy to clipboard
echo "2	https://example.com/some-url" | cliphist decode | wl-copy

# Delete a specific entry
echo "1	Hello, Wayland" | cliphist delete

# Delete all entries matching a pattern
cliphist delete-query "password"

# Wipe entire history
cliphist wipe

# Show database path and item count
cliphist list | wc -l
ls -lh ~/.cache/cliphist/db
```

**Picker integration** is where cliphist shines. The list output is designed to pipe cleanly into any dmenu-compatible fuzzy finder:

```bash
# With wofi
cliphist list | wofi --dmenu | cliphist decode | wl-copy

# With fuzzel
cliphist list | fuzzel --dmenu | cliphist decode | wl-copy

# With rofi
cliphist list | rofi -dmenu | cliphist decode | wl-copy

# With fzf in a floating terminal (e.g. foot -a cliphist-picker)
cliphist list | fzf --reverse | cliphist decode | wl-copy

# With tofi
cliphist list | tofi | cliphist decode | wl-copy
```

**Image clipboard previews** require a picker that can render images. cliphist generates previews for image entries that some pickers can display. With rofi 1.7+:

```bash
# cliphist-rofi-img — wrapper that generates /tmp previews for rofi
#!/usr/bin/env bash
# Save as ~/.local/bin/cliphist-rofi-img and chmod +x

if [[ "$1" == "img" ]]; then
    cliphist decode <<< "$2" | wl-copy
else
    cliphist list | rofi -dmenu \
        -display-columns 2 \
        -theme-str 'entry { placeholder: "Search clipboard..."; }' \
        | cliphist decode | wl-copy
fi
```

**Systemd user service** for robust startup (see Ch 53 for the full session startup pattern):

```ini
# ~/.config/systemd/user/cliphist-text.service
[Unit]
Description=Clipboard history daemon (text)
PartOf=graphical-session.target
After=graphical-session.target

[Service]
ExecStart=wl-paste --type text --watch cliphist store
Restart=on-failure
RestartSec=3

[Install]
WantedBy=graphical-session.target
```

```ini
# ~/.config/systemd/user/cliphist-image.service
[Unit]
Description=Clipboard history daemon (images)
PartOf=graphical-session.target
After=graphical-session.target

[Service]
ExecStart=wl-paste --type image --watch cliphist store
Restart=on-failure
RestartSec=3

[Install]
WantedBy=graphical-session.target
```

```bash
# Enable and start
systemctl --user enable --now cliphist-text.service cliphist-image.service
systemctl --user status cliphist-text.service
```

---

## 32.4 copyq — Cross-Platform GUI Manager

CopyQ is a feature-rich clipboard manager with a Qt GUI, scriptable via a built-in JavaScript/EcmaScript engine. It predates Wayland but has functional Wayland support through wl-clipboard as a backend. It is the right tool when you need scripted clipboard transformations, multi-tab item organization, or a persistent tray icon.

```bash
# Install
sudo pacman -S copyq         # Arch
sudo apt install copyq       # Debian/Ubuntu
sudo dnf install copyq       # Fedora

# Launch with Wayland backend forced
QT_QPA_PLATFORM=wayland copyq

# Or set in your environment permanently
echo 'export QT_QPA_PLATFORM=wayland' >> ~/.config/environment.d/qt.conf
```

**Key CopyQ configuration for Wayland** (`~/.config/copyq/copyq.conf` or via the GUI under Preferences):

```ini
[General]
CheckClipboard=true
CheckSelection=false        # Set true if you want primary selection too
MaxItems=500
SaveAfterItemCount=25

[Appearance]
style=fusion
theme=dark
```

**CopyQ command scripting** — the built-in JS engine allows clipboard transformations on capture. Open CopyQ → Preferences → Commands → Add:

```javascript
// Auto-trim whitespace from copied text
// Name: Trim Whitespace
// Match items: text/plain
// Script:
var text = str(clipboard());
var trimmed = text.trim();
if (text !== trimmed) {
    copy(trimmed);
}
```

```javascript
// Auto-detect and decode base64 in clipboard
// Name: Decode Base64
// Shortcut: Ctrl+Shift+B
// Script:
var text = selectedtext();
try {
    var decoded = frombase64(text);
    copy(decoded);
    popup("Decoded", "Base64 decoded to clipboard");
} catch (e) {
    popup("Error", "Not valid base64");
}
```

**CopyQ CLI** for scripting from the terminal:

```bash
# Copy text via CopyQ daemon
copyq copy "text to clipboard"

# Paste current item
copyq paste

# List history items (returns tab-separated id/text)
copyq tab

# Evaluate a CopyQ script
copyq eval 'copy("scripted content")'

# Add item to clipboard without activating focus
copyq add "background item"

# Export/import history
copyq exportData /tmp/copyq-backup.cpq
copyq importData /tmp/copyq-backup.cpq
```

---

## 32.5 Hyprland Clipboard Setup

Hyprland uses `exec-once` directives in `hyprland.conf` for daemon startup. The canonical clipboard stack for Hyprland starts both cliphist watchers at compositor launch and binds the history picker to a keybind.

```conf
# ~/.config/hypr/hyprland.conf

# Clipboard history daemons
exec-once = wl-paste --type text --watch cliphist store
exec-once = wl-paste --type image --watch cliphist store

# Keybind: open clipboard history picker
bind = SUPER, V, exec, cliphist list | wofi --dmenu | cliphist decode | wl-copy

# Alternative with fuzzel
bind = SUPER, V, exec, cliphist list | fuzzel --dmenu | cliphist decode | wl-copy

# Alternative with a floating foot terminal + fzf (if you prefer TUI pickers)
bind = SUPER, V, exec, foot --app-id=cliphist-picker -e bash -c 'cliphist list | fzf --reverse | cliphist decode | wl-copy'

# Floating rules for the TUI picker
windowrulev2 = float, class:cliphist-picker
windowrulev2 = size 700 500, class:cliphist-picker
windowrulev2 = center, class:cliphist-picker
```

**Preventing duplicate watchers** after Hyprland reload (`hyprctl reload`) is important. Use a wrapper script that kills existing instances first:

```bash
#!/usr/bin/env bash
# ~/.local/bin/cliphist-start
# Called from exec-once in hyprland.conf

pkill -f "wl-paste --type text --watch" 2>/dev/null
pkill -f "wl-paste --type image --watch" 2>/dev/null

sleep 0.5

wl-paste --type text --watch cliphist store &
wl-paste --type image --watch cliphist store &
```

```conf
# hyprland.conf (use the wrapper instead)
exec-once = ~/.local/bin/cliphist-start
```

**Hyprland clipboard with Hyprpicker** integration — copy color values directly to clipboard with formatting:

```conf
bind = SUPER SHIFT, C, exec, hyprpicker --autocopy --format hex
bind = SUPER SHIFT ALT, C, exec, hyprpicker --autocopy --format rgb
```

**Per-workspace clipboard isolation** is not natively supported but can be approximated by storing a prefix in each cliphist entry using a wrapper:

```bash
#!/usr/bin/env bash
# ~/.local/bin/cliphist-store-tagged
# Reads from stdin and prepends workspace number

WS=$(hyprctl activeworkspace -j | jq -r '.id')
TEXT=$(cat)
printf "[ws%s] %s" "$WS" "$TEXT" | cliphist store
```

---

## 32.6 Sway Clipboard Setup

Sway's clipboard configuration follows the same principles as Hyprland but uses `exec` in `~/.config/sway/config`:

```conf
# ~/.config/sway/config

# Clipboard history daemons
exec wl-paste --type text --watch cliphist store
exec wl-paste --type image --watch cliphist store

# Clipboard history picker (wofi)
bindsym $mod+v exec cliphist list | wofi --dmenu | cliphist decode | wl-copy

# With fuzzel (recommended for Sway — pure Wayland, fast)
bindsym $mod+v exec cliphist list | fuzzel --dmenu | cliphist decode | wl-copy

# With bemenu (lightweight GTK3/Wayland native)
bindsym $mod+v exec cliphist list | bemenu -i --prompt "clipboard:" | cliphist decode | wl-copy
```

**wl-clip-persist** is a Sway-ecosystem tool that specifically solves the "clipboard dies on app exit" problem by acting as a minimal clipboard persistence daemon. It is simpler than cliphist if you only need persistence, not history:

```bash
# Install
cargo install wl-clip-persist
# or: yay -S wl-clip-persist

# Run at login
exec wl-clip-persist --clipboard regular
# or persist both clipboard and primary:
exec wl-clip-persist --clipboard both
```

```bash
# Comparison: wl-clip-persist vs cliphist
```

| Feature | wl-clip-persist | cliphist |
|---------|----------------|---------|
| Clipboard persistence | Yes | Yes (side effect) |
| History depth | 1 (latest only) | Configurable (default 750) |
| Image support | Yes | Yes |
| Picker integration | No | Yes |
| Database size | None | SQLite ~MB |
| Resource usage | Very low | Low |
| Primary selection | Yes | Optional |

---

## 32.7 Primary Selection (Middle-Click Paste)

The primary selection — populated by text highlighting and pasted by middle-click — is a beloved X11 feature that Wayland carries forward via the `zwp_primary_selection_device_manager_v1` protocol extension. Support varies by compositor and toolkit.

```bash
# Check if your compositor supports primary selection
wl-paste --primary --list-types 2>&1
# If it returns types, primary selection is active
# If it errors: "Primary selection is not supported", your compositor lacks it

# Write to primary selection
wl-copy --primary "text for middle-click"

# Read from primary selection
wl-paste --primary

# Watch primary selection changes and store in cliphist
wl-paste --type text --watch --primary cliphist store
```

**XWayland apps** (e.g., older Electron apps, Wine programs) use the X11 primary selection. To bridge between Wayland primary selection and XWayland, use `xsel` or `xclip` via the `DISPLAY` variable set by XWayland:

```bash
# Read X11 primary selection (from XWayland apps)
xsel --primary --output

# Write to X11 primary selection
echo "text" | xsel --primary --input

# Bridge script: sync Wayland primary to X11 primary
#!/usr/bin/env bash
# ~/.local/bin/primary-bridge
wl-paste --primary --watch | while IFS= read -r line; do
    echo "$line" | xsel --primary --input 2>/dev/null
done
```

**Terminal emulator behavior** varies significantly. Most modern Wayland-native terminals implement primary selection correctly:

| Terminal | Primary Selection | Middle-Click Paste | wl-clipboard |
|----------|------------------|--------------------|-------------|
| foot | Yes | Yes | Yes |
| kitty (Wayland) | Yes | Yes | Yes |
| Alacritty (Wayland) | Yes | Yes | Yes |
| wezterm | Yes | Yes | Yes |
| xterm (XWayland) | X11 only | X11 only | Via bridge |
| gnome-terminal | Yes | Yes | Yes |

---

## 32.8 Quickshell Clipboard Widget

Quickshell is a QML-based compositor shell toolkit (see Ch 44). Its `Process` type can invoke system commands, making clipboard integration straightforward.

**Read current clipboard into a Quickshell label:**

```qml
// ClipboardMonitor.qml
import Quickshell
import Quickshell.Io
import QtQuick

Item {
    id: root
    property string clipboardText: ""

    Process {
        id: clipWatcher
        command: ["wl-paste", "--watch", "cat"]
        running: true

        stdout: SplitParser {
            onRead: data => {
                root.clipboardText = data
            }
        }
    }

    Text {
        text: root.clipboardText.length > 60
            ? root.clipboardText.substring(0, 60) + "…"
            : root.clipboardText
        color: "#cdd6f4"
        font.pixelSize: 12
    }
}
```

**Clipboard history panel** using cliphist list output:

```qml
// ClipHistPanel.qml
import Quickshell
import Quickshell.Io
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls

Rectangle {
    id: panel
    width: 400
    height: 500
    color: "#1e1e2e"
    radius: 8
    visible: false

    property var historyItems: []

    Process {
        id: listProc
        command: ["cliphist", "list"]
        running: false

        stdout: SplitParser {
            onRead: data => {
                panel.historyItems.push(data)
                histModel.append({ "entry": data })
            }
        }

        onRunningChanged: {
            if (!running) panel.visible = true
        }
    }

    function refresh() {
        historyItems = []
        histModel.clear()
        listProc.running = true
    }

    ListModel { id: histModel }

    ListView {
        anchors.fill: parent
        anchors.margins: 8
        model: histModel
        delegate: Rectangle {
            width: ListView.view.width
            height: 40
            color: mouseArea.containsMouse ? "#313244" : "transparent"
            radius: 4

            Text {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: 8
                anchors.right: parent.right
                anchors.rightMargin: 8
                text: model.entry.split("\t")[1] ?? model.entry
                color: "#cdd6f4"
                font.pixelSize: 11
                elide: Text.ElideRight
            }

            MouseArea {
                id: mouseArea
                anchors.fill: parent
                hoverEnabled: true
                onClicked: {
                    decodeProc.entryData = model.entry
                    decodeProc.running = true
                    panel.visible = false
                }
            }
        }
    }

    Process {
        id: decodeProc
        property string entryData: ""
        command: ["bash", "-c", `echo ${JSON.stringify(entryData)} | cliphist decode | wl-copy`]
        running: false
    }
}
```

---

## 32.9 Security Considerations

The clipboard is a high-value attack surface. Password managers, API tokens, and private keys pass through it. Several practices harden your clipboard pipeline.

**Automatic clearing** of sensitive clipboard content after a timeout:

```bash
#!/usr/bin/env bash
# ~/.local/bin/wl-copy-secure
# Like wl-copy but clears after N seconds (default: 45)

TIMEOUT=${1:-45}
shift

# Copy the content
wl-copy "$@"

# Schedule clear
(sleep "$TIMEOUT" && echo "" | wl-copy) &
echo "Clipboard will clear in ${TIMEOUT}s"
```

```bash
# Usage with pass (password manager)
pass show mysite/password | head -1 | wl-copy-secure 30
```

**Excluding password manager entries from cliphist.** Since cliphist stores everything `wl-paste --watch` sees, you need to block entries from password manager windows. The cleanest approach is a filter wrapper:

```bash
#!/usr/bin/env bash
# ~/.local/bin/cliphist-store-filtered
# Replaces direct cliphist store calls; skips entries from sensitive apps

# Check active window (Hyprland)
ACTIVE_CLASS=$(hyprctl activewindow -j 2>/dev/null | jq -r '.class // empty')

BLOCKED_CLASSES=("KeePassXC" "1Password" "Bitwarden" "keepassxc")

for blocked in "${BLOCKED_CLASSES[@]}"; do
    if [[ "$ACTIVE_CLASS" == "$blocked" ]]; then
        # Silently discard
        cat > /dev/null
        exit 0
    fi
done

cliphist store
```

```conf
# hyprland.conf — use filtered store
exec-once = wl-paste --type text --watch ~/.local/bin/cliphist-store-filtered
```

**cliphist database encryption** at rest is not built in. For high-security setups, store the database on a tmpfs:

```bash
# ~/.config/environment.d/cliphist.conf
XDG_CACHE_HOME=/run/user/1000/cache  # tmpfs — cleared on logout
```

**Sensitive MIME type filtering** — exclude clipboard entries that match common secret patterns:

```bash
#!/usr/bin/env bash
# ~/.local/bin/cliphist-store-nosecrets

INPUT=$(cat)

# Skip likely secrets: AWS keys, GitHub tokens, private keys
if echo "$INPUT" | grep -qE '(AKIA[A-Z0-9]{16}|ghp_[A-Za-z0-9]{36}|-----BEGIN.*PRIVATE KEY-----|password|secret)'; then
    exit 0
fi

echo "$INPUT" | cliphist store
```

---

## 32.10 Clipboard in Scripts and Automation

Clipboard utilities integrate cleanly into shell automation. These patterns cover common scripting scenarios.

**Screenshot to clipboard** — capture and immediately store in clipboard:

```bash
#!/usr/bin/env bash
# ~/.local/bin/screenshot-clip
# Requires: grim, slurp

TMPFILE=$(mktemp /tmp/screenshot-XXXXXX.png)

case "${1:-area}" in
    area)
        grim -g "$(slurp)" "$TMPFILE"
        ;;
    screen)
        grim "$TMPFILE"
        ;;
    window)
        # Active window geometry from Hyprland
        GEOM=$(hyprctl activewindow -j | jq -r '"\(.at[0]),\(.at[1]) \(.size[0])x\(.size[1])"')
        grim -g "$GEOM" "$TMPFILE"
        ;;
esac

wl-copy --type image/png < "$TMPFILE"
rm "$TMPFILE"
notify-send "Screenshot" "Copied to clipboard"
```

**URL extraction and processing:**

```bash
#!/usr/bin/env bash
# ~/.local/bin/clip-url
# Extract URLs from clipboard, pick one, open in browser

wl-paste | grep -oE 'https?://[^ ]+' | \
    sort -u | \
    wofi --dmenu --prompt "Open URL:" | \
    xargs -r xdg-open
```

**Translation via clipboard:**

```bash
#!/usr/bin/env bash
# ~/.local/bin/clip-translate
# Translate clipboard content using LibreTranslate (self-hosted) or a CLI tool

TEXT=$(wl-paste --no-newline)
TRANSLATED=$(trans -brief -to en "$TEXT" 2>/dev/null)
echo "$TRANSLATED" | wl-copy
notify-send "Translated" "$TRANSLATED"
```

**Clipboard diff** between two points in time:

```bash
#!/usr/bin/env bash
# Capture current clipboard, wait, diff with new clipboard
BEFORE=$(wl-paste 2>/dev/null)
echo "Snapshot taken. Change clipboard, then press Enter."
read -r
AFTER=$(wl-paste 2>/dev/null)
diff <(echo "$BEFORE") <(echo "$AFTER")
```

---

## 32.11 Tool Comparison

| Tool | Type | History | Images | Picker Integration | Wayland Native | Scripting |
|------|------|---------|--------|--------------------|----------------|-----------|
| wl-clipboard | CLI utility | No | Yes | N/A | Yes | Excellent |
| cliphist | History daemon | Yes (SQLite) | Yes | dmenu pipe | Yes | Good |
| wl-clip-persist | Persistence only | No (1 entry) | Yes | No | Yes | Minimal |
| copyq | GUI manager | Yes | Yes | Own GUI + CLI | Via QT_QPA | Excellent (JS) |
| greenclip | History daemon | Yes | No | rofi module | No (XWayland) | Minimal |
| clipman | History daemon | Yes | No | dmenu pipe | Yes | Minimal |

**Recommended stack by use case:**

| Use Case | Recommended Tools |
|----------|------------------|
| Minimal setup, just persistence | `wl-clipboard` + `wl-clip-persist` |
| Power user with keybind picker | `wl-clipboard` + `cliphist` + `fuzzel` |
| GUI-heavy workflow with scripting | `wl-clipboard` + `copyq` |
| High security (no history) | `wl-clipboard` + `wl-clip-persist` + secure clear script |
| Quickshell/custom shell | `wl-clipboard` + `cliphist` + QML Process integration |

---

## Troubleshooting

**Clipboard is empty after app closes**

This is expected Wayland behavior. Run `wl-clip-persist --clipboard regular` or set up cliphist watchers to preserve clipboard content after the source application exits.

```bash
# Verify wl-clip-persist is running
pgrep -a wl-clip-persist

# Check cliphist watchers are running
pgrep -a "wl-paste"
```

**cliphist list returns nothing**

The watcher processes may not be running, or the database may not exist yet.

```bash
# Check watchers
systemctl --user status cliphist-text.service cliphist-image.service

# Or check processes
pgrep -fa "wl-paste.*cliphist"

# Check database
ls -la ~/.cache/cliphist/db
sqlite3 ~/.cache/cliphist/db "SELECT count(*) FROM clipboard_items;" 2>/dev/null
```

**wl-paste: compositor does not support primary selection**

Your compositor may lack `zwp_primary_selection_device_manager_v1`. Hyprland supports it natively. Sway requires version 1.7+. For older compositors, use XWayland + xsel as a fallback.

```bash
# Check protocol support
wayland-info 2>/dev/null | grep -i primary
# or
weston-info 2>/dev/null | grep -i primary
```

**Picker shows binary garbage for image entries**

When piping cliphist list into a text-only picker (like rofi in plain dmenu mode), image entries show as `[[ binary data image/png N KiB ]]`. This is correct — they are still selectable and cliphist decode handles them. For image preview, use rofi with the `-show-icons` mode or the `cliphist-rofi-img` wrapper from Section 32.3.

**wl-copy "hangs" in terminal**

This is by design. `wl-copy` holds the clipboard selection alive by staying running. Press Ctrl+C to release the selection, or run `wl-copy < file &` to background it. The `--paste-once` flag exits after one paste.

```bash
# Background copy (exits after first paste request)
wl-copy --paste-once "this clears itself after one paste" &

# Or just background it
wl-copy "persistent" &
CLIP_PID=$!
# ... later ...
kill $CLIP_PID
```

**CopyQ not working on Wayland**

```bash
# Force Wayland platform
QT_QPA_PLATFORM=wayland copyq

# If still broken, check Qt plugin availability
qtdiag 2>/dev/null | grep -i wayland

# Fallback: run CopyQ under XWayland
DISPLAY=:0 copyq
```

**cliphist watcher consuming high CPU**

This typically indicates a runaway loop from a rapidly-changing clipboard source (e.g., a buggy app). Check `ps aux | grep wl-paste` and kill duplicate watchers.

```bash
# Kill all cliphist watchers cleanly
pkill -f "wl-paste.*cliphist"

# Restart cleanly
wl-paste --type text --watch cliphist store &
wl-paste --type image --watch cliphist store &
```

**Secret entries appearing in cliphist despite filtering**

The filter wrapper must be called *before* `cliphist store`, and the active window detection must fire within the watcher's stdin read window. If the timing is off (e.g., focus changed before watcher fired), the entry slips through. The safest mitigation is to run `cliphist delete-query` after sensitive operations:

```bash
# After using password manager, purge last N entries
cliphist list | head -5 | while IFS= read -r line; do
    echo "$line" | cliphist delete
done
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
