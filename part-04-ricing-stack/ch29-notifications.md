# Chapter 29 — Notification Daemons: mako, dunst, swaync

## Contents

- [Overview](#overview)
- [29.1 The Freedesktop Notification Spec](#291-the-freedesktop-notification-spec)
- [29.2 mako — Minimal Sway-Focused Daemon](#292-mako-minimal-sway-focused-daemon)
- [29.3 dunst — The Feature-Rich Daemon](#293-dunst-the-feature-rich-daemon)
- [29.4 swaync — SwayNotificationCenter](#294-swaync-swaynotificationcenter)
- [29.5 Quickshell Native Notifications (Ch 22 Recap)](#295-quickshell-native-notifications-ch-22-recap)
- [29.6 Notification Styling Guide](#296-notification-styling-guide)
  - [Positioning and Anchoring](#positioning-and-anchoring)
  - [Stack Ordering and Overflow](#stack-ordering-and-overflow)
  - [Do-Not-Disturb and Focus Modes](#do-not-disturb-and-focus-modes)
  - [Critical Notification Persistence](#critical-notification-persistence)
- [29.7 Testing Notifications](#297-testing-notifications)
- [29.8 Choosing a Daemon](#298-choosing-a-daemon)
- [29.9 Session Startup Integration](#299-session-startup-integration)
- [Troubleshooting](#troubleshooting)

---


## Overview

Notification daemons are the silent workhorses of a riced desktop. Every time a chat app pings you, a build finishes, or a system event fires, a daemon intercepts the D-Bus call, decides how to render it, and pushes a popup to your compositor using the `wlr-layer-shell` protocol. On Wayland this is non-trivial: unlike X11, where any process could draw anywhere, Wayland requires explicit layer-shell privileges. Notification popups live on the `overlay` layer, above all windows, and the daemon must hold the compositor's trust to place them there.

Three daemons dominate the Wayland ecosystem in 2025: **mako** (minimal, Sway-native), **dunst** (feature-rich, cross-platform), and **swaync** (notification center with a full slide-out panel). A fourth path is skipping a standalone daemon entirely and embedding notification logic inside **Quickshell** (covered in Ch 22). Each approach trades off configuration complexity, visual flexibility, and notification-center functionality differently. This chapter covers all four in depth, shows you how to theme and position notifications precisely, and explains how to wire them into your session startup (see Ch 53 for session management).

The D-Bus interface and notification hints are the same regardless of daemon. Learning the spec once means you can switch daemons without changing your scripts. We cover the spec first, then each daemon, then cross-cutting topics: do-not-disturb, progress bars, scripted actions, and testing.

---

## 29.1 The Freedesktop Notification Spec

The specification lives at `https://specifications.freedesktop.org/notification-spec/`. Every compliant daemon listens on the session bus at the well-known name `org.freedesktop.Notifications`, object path `/org/freedesktop/Notifications`, interface `org.freedesktop.Notifications`. The wire protocol is DBus; any process that speaks DBus can send notifications without depending on a specific tool.

The core method is `Notify`. Its signature in DBus IDL is:

```
UINT32 Notify(
    STRING     app_name,
    UINT32     replaces_id,
    STRING     app_icon,
    STRING     summary,
    STRING     body,
    ARRAY      actions,
    DICT       hints,
    INT32      expire_timeout
)
```

`replaces_id` lets an application update an existing notification in-place — essential for progress bars and status updates. Set it to the return value of a previous `Notify` call. `expire_timeout` is in milliseconds; `-1` means use the daemon's default, `0` means never expire. The `actions` array alternates between action keys (opaque strings you define) and human-readable labels: `["default", "Open", "dismiss", "Dismiss"]`. When the user clicks an action, the daemon emits the `ActionInvoked` signal with the notification ID and the action key.

The `hints` dict is where the interesting per-notification customization lives:

| Hint key | DBus type | Meaning |
|---|---|---|
| `urgency` | BYTE | 0=Low, 1=Normal, 2=Critical |
| `image-data` | (iiibiiay) | Raw RGBA image for the notification icon |
| `image-path` | STRING | Filesystem path or `file://` URI to icon image |
| `sound-file` | STRING | Path to sound to play |
| `suppress-sound` | BOOL | Disable sound even if daemon would play one |
| `transient` | BOOL | Do not log to notification history |
| `desktop-entry` | STRING | `.desktop` name for the sending app |
| `category` | STRING | `"network.connected"`, `"transfer.complete"`, etc. |
| `value` | INT32 | Progress (0–100) for progress-bar display |
| `x-dunst-stack-tag` | STRING | dunst: group notifications with same tag |
| `x-canonical-private-synchronous` | STRING | Ubuntu/mako: replace notification with same tag |

The two signals you care about as a scripter are `NotificationClosed(id, reason)` — reason 1=expired, 2=user dismissed, 3=`CloseNotification` call, 4=undefined — and `ActionInvoked(id, action_key)`. You can monitor them with `dbus-monitor`:

```bash
# Monitor all notification signals live
dbus-monitor "interface='org.freedesktop.Notifications'" 2>/dev/null

# List all notifications currently tracked by the daemon (gdbus example)
gdbus call --session \
  --dest org.freedesktop.Notifications \
  --object-path /org/freedesktop/Notifications \
  --method org.freedesktop.Notifications.GetCapabilities
```

Capabilities vary by daemon. Common ones: `"body"` (HTML-like markup in body), `"body-markup"`, `"actions"`, `"icon-static"`, `"persistence"`, `"sound"`. Check what your daemon supports before relying on a feature.

---

## 29.2 mako — Minimal Sway-Focused Daemon

mako was written by Simon Ser (emersion), who also maintains `wlroots` and `swaync`. It is deliberately minimal: a single config file, a small runtime binary, and zero notification-center functionality. If you want a drawer or history panel, combine mako with a separate tool or switch to swaync. mako's strength is its criteria system — fine-grained per-app, per-urgency, per-category styling without a sprawling INI.

Install mako from your distribution or build from source:

```bash
# Arch
sudo pacman -S mako

# Fedora
sudo dnf install mako

# Build from source (requires meson, wayland-protocols, pango, cairo)
git clone https://github.com/emersion/mako.git && cd mako
meson setup build && ninja -C build && sudo ninja -C build install
```

The config file is `~/.config/mako/config`. A complete annotated example:

```ini
# ~/.config/mako/config

# --- Global defaults ---
font=JetBrainsMono Nerd Font 11
background-color=#1e1e2e
text-color=#cdd6f4
border-color=#89b4fa
border-size=2
border-radius=8
padding=12
width=360
height=100
margin=12
anchor=top-right
layer=overlay

# Stack behaviour
max-visible=5
sort=-time           # newest on top; use +time for oldest on top

# Timing
default-timeout=5000   # ms; 0 = no timeout
ignore-timeout=0       # 0 = respect notification's own timeout

# --- Criteria blocks override globals for matching notifications ---
# Low-urgency: quieter styling, auto-dismiss quickly
[urgency=low]
border-color=#45475a
default-timeout=3000

# Normal urgency: defaults already set above

# Critical urgency: persistent, red border, never auto-dismiss
[urgency=critical]
border-color=#f38ba8
background-color=#302030
default-timeout=0
ignore-timeout=1

# Firefox: blue border, wider for long URLs
[app-name="firefox"]
border-color=#74c7ec
width=420

# Volume notifications: small, bottom-right, rapid dismiss
[app-name="pactl" urgency=low]
anchor=bottom-right
default-timeout=1500
width=200

# Any notification tagged for muting (set via hint x-canonical-private-synchronous)
[hidden]
format=(%h more)
```

The `format` key uses tokens: `%a` (app-name), `%s` (summary), `%b` (body), `%i` (icon path), `%I` (icon name), `%n` (count of grouped), `%h` (hidden count). Markdown-style bold `<b>...</b>` and italic `<i>...</i>` work if your font supports them.

`makoctl` is the runtime control binary. Use it in keybindings or scripts:

```bash
# Dismiss the top notification
makoctl dismiss

# Dismiss all currently visible notifications
makoctl dismiss --all

# Restore the most recently dismissed notification
makoctl restore

# Invoke the default action on the top notification
makoctl invoke

# Show an interactive menu of actions for the top notification (needs a menu tool)
makoctl menu wofi --dmenu

# Reload config without restarting the daemon
makoctl reload

# Show current mode (normal / do-not-disturb)
makoctl mode

# Enable do-not-disturb
makoctl set-mode do-not-disturb

# Return to normal mode
makoctl set-mode default
```

Integrate mako into your Sway config (see Ch 53 for full session startup):

```
# ~/.config/sway/config
exec_always --no-startup-id mako
bindsym $mod+grave exec makoctl dismiss
bindsym $mod+shift+grave exec makoctl dismiss --all
```

---

## 29.3 dunst — The Feature-Rich Daemon

dunst predates Wayland but received full Wayland support in v1.7 (2022). It is the most configurable stand-alone notification daemon available: per-rule scripted actions, history recall, progress bars, mouse interaction profiles, recursive ID-based replacement, and a context menu for choosing among multiple actions. If you want mako's simplicity you use mako; if you need dunst's power, you tolerate its longer config.

```bash
# Arch
sudo pacman -S dunst

# Fedora
sudo dnf install dunst

# Ubuntu 24.04+
sudo apt install dunst
```

dunst reads `~/.config/dunst/dunstrc` (INI format). A thorough config:

```ini
# ~/.config/dunst/dunstrc

[global]
    # Display and positioning
    monitor = 0
    follow = none           # none | mouse | keyboard
    width = (0, 400)        # min/max width tuple
    height = (0, 120)
    origin = top-right
    offset = 12x12
    scale = 0               # 0 = auto HiDPI
    gap_size = 4
    notification_limit = 6

    # Appearance
    frame_width = 2
    frame_color = "#89b4fa"
    corner_radius = 8
    separator_height = 2
    separator_color = auto
    padding = 10
    horizontal_padding = 12
    text_icon_padding = 10

    # Typography
    font = JetBrainsMono Nerd Font 11
    line_height = 0
    markup = full           # none | strip | full
    format = "<b>%a</b>\n%s\n%b"
    alignment = left
    vertical_alignment = center
    word_wrap = yes
    ellipsize = middle
    ignore_newline = no
    stack_duplicates = true
    hide_duplicate_count = false
    show_indicators = yes

    # Icons
    enable_recursive_icon_lookup = true
    icon_theme = Papirus-Dark
    icon_position = left
    min_icon_size = 32
    max_icon_size = 64

    # History
    sticky_history = yes
    history_length = 50

    # Timeouts (ms)
    show_age_threshold = 60
    idle_threshold = 0

    # Behaviour
    sort = yes              # sort by urgency
    always_run_script = true
    browser = /usr/bin/xdg-open
    dmenu = /usr/bin/wofi --dmenu  # used for context menu

    # Mouse interaction
    mouse_left_click = close_current
    mouse_middle_click = context
    mouse_right_click = do_action, close_current

[urgency_low]
    background = "#1e1e2e"
    foreground = "#a6adc8"
    frame_color = "#45475a"
    timeout = 4

[urgency_normal]
    background = "#1e1e2e"
    foreground = "#cdd6f4"
    frame_color = "#89b4fa"
    timeout = 6

[urgency_critical]
    background = "#302030"
    foreground = "#f38ba8"
    frame_color = "#f38ba8"
    timeout = 0
    fullscreen = show      # show over fullscreen apps

# --- Rules ---
[volume]
    appname = pactl
    urgency = low
    timeout = 2
    format = "%s"

[mpris]
    appname = playerctl
    urgency = low
    icon_position = left
    timeout = 3

[scripted_action]
    appname = build-system
    urgency = normal
    script = /usr/local/bin/on-build-notify.sh
```

The `script` field points to a shell script that receives these positional arguments: `$1` = appname, `$2` = summary, `$3` = body, `$4` = icon, `$5` = urgency. Example script that sends a desktop bell for critical builds:

```bash
#!/usr/bin/env bash
# /usr/local/bin/on-build-notify.sh
URGENCY="$5"
if [[ "$URGENCY" == "2" ]]; then
    paplay /usr/share/sounds/freedesktop/stereo/bell.oga &
fi
```

The `dunstctl` binary is your runtime interface:

```bash
# Dismiss the top notification
dunstctl close

# Dismiss all notifications
dunstctl close-all

# Pop the most recently dismissed notification back to visible
dunstctl history-pop

# Show full history as JSON
dunstctl history

# Enable do-not-disturb
dunstctl set-paused true

# Disable DND
dunstctl set-paused false

# Toggle DND
dunstctl set-paused toggle

# Query current DND state
dunstctl is-paused

# Show the context menu for the top notification (uses dmenu= from config)
dunstctl context

# Count of notifications currently displayed
dunstctl count displayed

# Count in history
dunstctl count history
```

Progress bars are triggered by the `value` hint. The bar renders inside the notification popup automatically when `dunstrc` has `show_indicators = yes`. This is how media players and file managers use it:

```bash
# Simulate a download progress notification
for i in 10 30 50 75 100; do
    notify-send --app-name="downloader" \
        --hint=int:value:$i \
        --hint=string:x-dunst-stack-tag:dl-progress \
        "Downloading file.tar.gz" \
        "$i% complete"
    sleep 1
done
```

The `x-dunst-stack-tag` hint groups all notifications with the same tag so they replace each other in-place rather than stacking.

Recursive replacement by ID is more precise: capture the returned notification ID and reuse it:

```bash
#!/usr/bin/env bash
# Update a single notification in-place using its ID
ID=$(notify-send --print-id "Build started" "Compiling...")
sleep 5
notify-send --replace-id="$ID" "Build done" "Compiled in 5s"
```

---

## 29.4 swaync — SwayNotificationCenter

swaync (by ErikReider) goes beyond a popup daemon: it adds a persistent notification center — a slide-out sidebar panel that shows notification history, a do-not-disturb toggle, and custom widgets. Think macOS Notification Center or GNOME's notification shade, but fully customizable via CSS and JSON.

```bash
# Arch (AUR or official)
sudo pacman -S swaync

# Build from source (requires gtk4, gtk4-layer-shell, libnotify)
git clone https://github.com/ErikReider/SwayNotificationCenter && cd SwayNotificationCenter
meson setup build && ninja -C build && sudo ninja -C build install
```

swaync uses two config files: `~/.config/swaync/config.json` (behaviour) and `~/.config/swaync/style.css` (appearance).

A complete `config.json`:

```json
{
  "$schema": "/etc/xdg/swaync/configSchema.json",
  "positionX": "right",
  "positionY": "top",
  "layer": "overlay",
  "control-center-layer": "top",
  "layer-shell": true,
  "cssPriority": "application",
  "control-center-margin-top": 8,
  "control-center-margin-bottom": 8,
  "control-center-margin-right": 8,
  "control-center-margin-left": 0,
  "control-center-width": 500,
  "control-center-height": 600,
  "notification-2fa-action": true,
  "notification-inline-replies": false,
  "notification-icon-size": 64,
  "notification-body-image-height": 100,
  "notification-body-image-width": 200,
  "timeout": 10,
  "timeout-low": 5,
  "timeout-critical": 0,
  "fit-to-screen": false,
  "keyboard-shortcuts": true,
  "image-visibility": "when-available",
  "transition-time": 200,
  "hide-on-clear": false,
  "hide-on-action": true,
  "script-fail-notify": true,
  "scripts": {
    "example-script": {
      "app-name": "Spotify",
      "urgency": "Normal",
      "exec": "echo '$summary - $body' >> /tmp/spotify-notify.log"
    }
  },
  "notification-visibility": {
    "silent-apps": {
      "state": "muted",
      "app-name": "zoom"
    }
  },
  "widgets": ["inhibitors", "title", "dnd", "notifications"],
  "widget-config": {
    "inhibitors": {
      "text": "Inhibitors",
      "button-text": "Clear All",
      "clear-all-button": true
    },
    "title": {
      "text": "Notifications",
      "clear-all-button": true,
      "button-text": "Clear All"
    },
    "dnd": {
      "text": "Do Not Disturb"
    },
    "label": {
      "max-lines": 1,
      "text": "Notification Center"
    },
    "mpris": {
      "image-size": 96,
      "image-radius": 12
    }
  }
}
```

The CSS file controls the visual appearance entirely. swaync ships a default CSS you can copy and customize:

```bash
cp /etc/xdg/swaync/style.css ~/.config/swaync/style.css
```

Key CSS selectors for theming:

```css
/* ~/.config/swaync/style.css — Catppuccin Mocha excerpt */

.notification-row {
  outline: none;
}

.notification-row:focus,
.notification-row:hover {
  background: alpha(#cdd6f4, 0.05);
}

.notification {
  background: #1e1e2e;
  border: 2px solid #89b4fa;
  border-radius: 8px;
  padding: 8px;
  margin: 4px 8px;
  color: #cdd6f4;
  font-family: "JetBrainsMono Nerd Font";
  font-size: 13px;
}

.notification.critical {
  border-color: #f38ba8;
  background: #302030;
}

.notification.low {
  border-color: #45475a;
  color: #a6adc8;
}

.control-center {
  background: #181825;
  border: 2px solid #313244;
  border-radius: 12px;
  padding: 8px;
}

.control-center-list {
  background: transparent;
}

.widget-title > label {
  font-size: 1.4em;
  font-weight: bold;
  color: #cdd6f4;
}

.widget-dnd > switch {
  background: #313244;
}

.widget-dnd > switch:checked {
  background: #f38ba8;
}
```

The `swaync-client` binary controls the daemon at runtime:

```bash
# Toggle the notification center open/closed
swaync-client -t
# or
swaync-client --toggle-panel

# Open the notification center
swaync-client --open-panel

# Close the notification center
swaync-client --close-panel

# Toggle do-not-disturb
swaync-client -d
swaync-client --toggle-dnd

# Enable DND explicitly
swaync-client --dnd-on

# Disable DND
swaync-client --dnd-off

# Get DND state as JSON
swaync-client --get-dnd

# Reload config without restart
swaync-client --reload-config

# Reload CSS only
swaync-client --reload-css

# Subscribe to events (returns JSON stream on stdout)
swaync-client --subscribe
```

Waybar integration uses the `custom/swaync` module pattern. Add to your Waybar config:

```json
// ~/.config/waybar/config  — relevant excerpt
"custom/swaync": {
    "format": "{icon} {}",
    "format-icons": {
        "notification": " ",
        "none": " ",
        "dnd-notification": " ",
        "dnd-none": "󰂛",
        "inhibited-notification": " ",
        "inhibited-none": " ",
        "dnd-inhibited-notification": " ",
        "dnd-inhibited-none": "󰂛"
    },
    "return-type": "json",
    "exec-if": "which swaync-client",
    "exec": "swaync-client -swb",
    "on-click": "swaync-client -t -sw",
    "on-click-right": "swaync-client -d -sw",
    "escape": true
}
```

The `-swb` flag runs `swaync-client` in "subscribe with bar" mode — it outputs a JSON stream that Waybar reads as a custom module with a live notification count and icon state.

---

## 29.5 Quickshell Native Notifications (Ch 22 Recap)

Quickshell (covered in depth in Ch 22) can replace a standalone notification daemon by implementing the `org.freedesktop.Notifications` DBus interface natively in QML. The `NotificationServer` type from the `Quickshell.Services.Notifications` module handles the D-Bus ownership and exposes notifications as a QML model. This gives you total visual control: arbitrary animations, per-app layout rules, inline image rendering, and notification history — all in QML without touching a config file.

A minimal Quickshell notification popup (`notifications.qml`):

```qml
// notifications.qml — attach to your shell root
import Quickshell
import Quickshell.Services.Notifications

NotificationServer {
    id: notifServer
    // keepOnReload: true preserves notifications across shell reloads
    keepOnReload: true

    onNotification: (notif) => {
        // notif.summary, notif.body, notif.appName, notif.urgency
        // notif.actions: list of {identifier, text}
        // notif.image: image source (if provided)
        popupModel.append(notif)
        if (notif.expireTimeout > 0) {
            Qt.callLater(() => {
                var idx = popupModel.indexOf(notif)
                if (idx >= 0) popupModel.remove(idx)
            }, notif.expireTimeout)
        }
    }

    property var popupModel: []
}

// Render with a PanelWindow on the overlay layer
PanelWindow {
    anchors { top: true; right: true }
    margins { top: 12; right: 12 }
    layer: Layer.Overlay
    exclusiveZone: 0
    implicitWidth: column.implicitWidth
    implicitHeight: column.implicitHeight

    Column {
        id: column
        spacing: 8
        Repeater {
            model: notifServer.popupModel
            delegate: NotifPopup { notification: modelData }
        }
    }
}
```

Action handling is straightforward: call `notif.invokeAction(identifier)` from a button's `onClicked`. Dismissal calls `notif.dismiss()`. This approach is described in Ch 22, Section 22.4 with a full animation example using `NumberAnimation` and `Behavior`.

---

## 29.6 Notification Styling Guide

### Positioning and Anchoring

Every daemon exposes an anchor/origin concept. The compositor's layer-shell protocol defines edges and corners; daemons map their config to those. The common positions and their daemon-specific config keys:

| Position | mako | dunst | swaync |
|---|---|---|---|
| Top-right | `anchor=top-right` | `origin = top-right` | `"positionX":"right","positionY":"top"` |
| Top-left | `anchor=top-left` | `origin = top-left` | `"positionX":"left","positionY":"top"` |
| Bottom-right | `anchor=bottom-right` | `origin = bottom-right` | `"positionX":"right","positionY":"bottom"` |
| Bottom-center | `anchor=bottom-center` | `origin = bottom-center` | `"positionX":"center","positionY":"bottom"` |

For multi-monitor setups, dunst and swaync both have `monitor = N` and `follow = mouse|keyboard` to pin popups to a specific output or follow focus. mako uses `output=<name>` in a criteria block.

### Stack Ordering and Overflow

When more notifications arrive than `max-visible` (mako) or `notification_limit` (dunst) allows, overflow behavior matters. mako renders a summary notification `[N more]` using the `[hidden]` criteria format string. dunst simply queues and shows as older ones expire. swaync always shows all notifications in the center panel even when popups are hidden.

For a busy workflow, setting `max-visible=3` with `sort=-time` (newest on top) is cleaner than letting ten popups stack. Pair with a keybinding to `makoctl dismiss --all` or `dunstctl close-all` to clear the screen fast.

### Do-Not-Disturb and Focus Modes

All three daemons implement DND. The cleanest pattern integrates DND state with your Waybar/status-bar so you always know when it's active, and hooks it to a screen locker so DND automatically engages when you lock.

```bash
#!/usr/bin/env bash
# /usr/local/bin/dnd-toggle.sh — works with mako, dunst, or swaync
DAEMON="${NOTIF_DAEMON:-mako}"

case "$DAEMON" in
    mako)
        MODE=$(makoctl mode)
        if [[ "$MODE" == "do-not-disturb" ]]; then
            makoctl set-mode default
        else
            makoctl set-mode do-not-disturb
        fi
        ;;
    dunst)
        dunstctl set-paused toggle
        ;;
    swaync)
        swaync-client --toggle-dnd
        ;;
esac
```

Integrate with swayidle for auto-DND on idle:

```
# ~/.config/sway/config or swayidle config
exec swayidle -w \
    timeout 300 'makoctl set-mode do-not-disturb' \
    resume   'makoctl set-mode default' \
    before-sleep 'makoctl set-mode do-not-disturb'
```

### Critical Notification Persistence

Critical notifications should never auto-dismiss. They should also appear over fullscreen applications (dunst's `fullscreen = show` under `[urgency_critical]`). In mako, `ignore-timeout=1` under `[urgency=critical]` overrides any expire_timeout the sending application provides. For swaync, `"timeout-critical": 0` in config.json achieves the same.

---

## 29.7 Testing Notifications

A structured test harness confirms your daemon and config behave as expected. Keep these scripts around during theming sessions.

```bash
#!/usr/bin/env bash
# /usr/local/bin/notif-test.sh — comprehensive notification test suite

echo "=== Low urgency (auto-dismiss) ==="
notify-send --urgency=low "Low Priority" "This should auto-dismiss in 3-4 seconds"
sleep 2

echo "=== Normal urgency ==="
notify-send --urgency=normal "Normal" "Standard notification with <b>bold body</b>"
sleep 2

echo "=== Critical (persistent) ==="
notify-send --urgency=critical "CRITICAL" "This must not auto-dismiss" --expire-time=0
sleep 2

echo "=== With app icon ==="
notify-send --app-name="firefox" --icon=firefox "Firefox" "Browser notification"
sleep 2

echo "=== Progress bar (dunst/swaync) ==="
ID=$(notify-send --print-id \
    --hint=int:value:0 \
    --hint=string:x-dunst-stack-tag:test-progress \
    "Progress" "Starting...")
for pct in 25 50 75 100; do
    sleep 1
    notify-send --replace-id="$ID" \
        --hint=int:value:$pct \
        --hint=string:x-dunst-stack-tag:test-progress \
        "Progress" "$pct% complete"
done
sleep 2

echo "=== Action buttons ==="
notify-send "Action Test" "Click a button" \
    --action="yes=Yes, do it" \
    --action="no=No, cancel"

echo "=== Transient (no history) ==="
notify-send --hint=boolean:transient:true "Transient" "Not saved to history"

echo "Done. Check your notification history for completeness."
```

```bash
# Inspect D-Bus notification introspection
dbus-send --session --print-reply \
  --dest=org.freedesktop.Notifications \
  /org/freedesktop/Notifications \
  org.freedesktop.DBus.Introspectable.Introspect

# Send a raw D-Bus notification (no notify-send dependency)
gdbus call --session \
  --dest org.freedesktop.Notifications \
  --object-path /org/freedesktop/Notifications \
  --method org.freedesktop.Notifications.Notify \
  "test-app" 0 "dialog-information" "Test Summary" "Test Body" \
  "[]" "{}" 5000
```

---

## 29.8 Choosing a Daemon

| Feature | mako | dunst | swaync | Quickshell |
|---|---|---|---|---|
| Notification center panel | No | No | Yes | Custom QML |
| Per-app rules | Criteria blocks | `[rule]` sections | `notification-visibility` | Full QML logic |
| Scripted actions | No | `script=` key | `scripts` JSON | QML JavaScript |
| Progress bars | No | Yes | Yes | Yes |
| DND | `makoctl set-mode` | `dunstctl set-paused` | `swaync-client -d` | Model property |
| History recall | No | `dunstctl history-pop` | Center panel | Custom list model |
| Config format | Custom key=value | INI | JSON + CSS | QML |
| GTK dependency | No (Cairo/Pango) | No (Cairo/Pango) | GTK4 | Qt6 |
| Wayland-native | Yes | Yes (v1.7+) | Yes | Yes |
| Resource usage | Very low | Low | Medium (GTK4) | Medium (Qt6) |

**Recommendation matrix:**
- Minimal setup, Sway + no panel: **mako**
- Need scripted actions or progress bars, no panel: **dunst**
- Want macOS-style notification center: **swaync**
- Already using Quickshell for your bar and launcher: **Quickshell NotificationServer**

---

## 29.9 Session Startup Integration

Every daemon must be started exactly once per session. On Sway, use `exec_always` with process guards. On Hyprland, use `exec-once`. On a generic Wayland compositor, use a systemd user service.

```ini
# ~/.config/systemd/user/mako.service
[Unit]
Description=mako notification daemon
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/mako
Restart=on-failure
RestartSec=1

[Install]
WantedBy=graphical-session.target
```

```bash
systemctl --user enable --now mako.service
```

For dunst:

```bash
# dunst ships its own user service
systemctl --user enable --now dunst.service
# or manually:
systemctl --user start dunst
```

For swaync, the same pattern applies (a `.service` file in `~/.config/systemd/user/`). See Ch 53 for the full session management architecture including import of environment variables into systemd units.

```bash
# Verify the daemon owns the D-Bus name (should print the service name)
dbus-send --session --print-reply \
  --dest=org.freedesktop.DBus \
  /org/freedesktop/DBus \
  org.freedesktop.DBus.GetNameOwner \
  string:org.freedesktop.Notifications
```

---

## Troubleshooting

**No notifications appear at all**

Check that exactly one daemon is running and owns the D-Bus name. Multiple daemons fight for `org.freedesktop.Notifications` and the loser silently drops all calls.

```bash
# Who owns the notification name?
dbus-send --session --print-reply \
  --dest=org.freedesktop.DBus /org/freedesktop/DBus \
  org.freedesktop.DBus.GetNameOwner \
  string:org.freedesktop.Notifications

# Is the daemon process running?
pgrep -a mako
pgrep -a dunst
pgrep -a swaync
```

**mako: "layer surface rejected" in journal**

Your compositor does not support `wlr-layer-shell` or the daemon is running before the compositor is ready. Delay daemon start with `sleep 1` in your exec, or use `After=graphical-session.target` in the systemd unit.

**dunst: notifications appear on wrong monitor**

Set `monitor = 0` explicitly, or use `follow = mouse` so popups track your cursor. If using multiple outputs with different DPI, ensure `scale = 0` for auto-detection.

**swaync: notification center not opening**

Verify swaync is running (`pgrep swaync`) and the socket exists:

```bash
ls /run/user/$UID/swaync*
# Should show a socket file
swaync-client --toggle-panel  # triggers the daemon over the socket
```

If the Waybar integration shows no count, check that you used `-swb` (subscribe with bar) not `-s` (subscribe):

```bash
# Should stream JSON to stdout
swaync-client -swb
```

**notify-send: "No notification daemon running"**

The `libnotify` library used by `notify-send` queries D-Bus for the notification service. If nothing is listening, it prints this error. Start your daemon first.

**Actions not triggering scripts (dunst)**

The `always_run_script = true` global setting must be set; without it, scripts only run when the notification matches a rule. Also verify the script is executable (`chmod +x /path/to/script.sh`) and the path in `dunstrc` is absolute.

**mako criteria not matching**

Criteria matching is exact string comparison unless a wildcard is used. Use `dbus-monitor` to capture the exact `app_name` field sent by the application — it may differ from what you expect:

```bash
dbus-monitor "interface='org.freedesktop.Notifications',member='Notify'" 2>/dev/null | grep -A1 "string"
```

---

*See also: Ch 22 (Quickshell notification widgets), Ch 26 (Waybar status bar integration), Ch 53 (session startup and systemd user services), Ch 31 (screenshot and clipboard tools).*

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
