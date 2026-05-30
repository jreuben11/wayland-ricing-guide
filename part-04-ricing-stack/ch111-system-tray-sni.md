# Chapter 111 — System Tray and the StatusNotifierItem Protocol

## Contents

- [Overview](#overview)
- [111.1 StatusNotifierItem: Protocol Overview](#1111-statusnotifieritem-protocol-overview)
  - [The Three Roles](#the-three-roles)
  - [D-Bus Interface Summary](#d-bus-interface-summary)
- [111.2 Which Apps Use SNI](#1112-which-apps-use-sni)
- [111.3 Waybar Tray Module](#1113-waybar-tray-module)
  - [Basic Configuration](#basic-configuration)
  - [CSS Styling](#css-styling)
  - [Waybar as the SNI Watcher](#waybar-as-the-sni-watcher)
- [111.4 Quickshell SystemTray](#1114-quickshell-systemtray)
  - [Basic Tray Widget](#basic-tray-widget)
  - [Menu Rendering](#menu-rendering)
  - [Filtering by Status](#filtering-by-status)
  - [Attention Animation](#attention-animation)
- [111.5 Standalone StatusNotifierWatcher](#1115-standalone-statusnotifierwatcher)
  - [xembedsniproxy (KDE)](#xembedsniproxy-kde)
  - [swaybar-protocol watcher (swaybar users)](#swaybar-protocol-watcher-swaybar-users)
- [111.6 snixembed: Legacy X11 Tray Bridge](#1116-snixembed-legacy-x11-tray-bridge)
  - [Installation](#installation)
  - [Session Startup](#session-startup)
  - [Verifying snixembed Is Working](#verifying-snixembed-is-working)
- [111.7 eww Systray Widget](#1117-eww-systray-widget)
- [111.8 D-Bus Debugging](#1118-d-bus-debugging)
  - [List All Registered SNI Items](#list-all-registered-sni-items)
  - [Inspect a Specific Item](#inspect-a-specific-item)
  - [Monitor All SNI Traffic](#monitor-all-sni-traffic)
  - [Call an Item's Method](#call-an-items-method)
- [111.9 Ayatana / libappindicator Extension](#1119-ayatana-libappindicator-extension)
- [111.10 Troubleshooting](#11110-troubleshooting)
  - [Tray is empty / no icons appear](#tray-is-empty-no-icons-appear)
  - [Icons appear but are missing for one specific app](#icons-appear-but-are-missing-for-one-specific-app)
  - [Icons appear but click does nothing](#icons-appear-but-click-does-nothing)
  - [Two watchers conflict (Waybar + KWin both running)](#two-watchers-conflict-waybar-kwin-both-running)
  - [Steam / Discord icon appears but disappears after a few seconds](#steam-discord-icon-appears-but-disappears-after-a-few-seconds)
  - [Icons are too small / blurry](#icons-are-too-small-blurry)
- [Summary](#summary)

---


## Overview

The system tray — that cluster of small icons near the clock that indicates running apps, network status, volume, and a dozen other things — is one of the most common sources of confusion on a freshly riced Wayland desktop. Icons for Steam, Discord, Nextcloud, KeePassXC, and network managers that appeared automatically on X11 simply vanish. This chapter explains why, and how to fix it.

The root issue is a protocol mismatch. The old X11 tray protocol (`_NET_SYSTEM_TRAY_OPCODE`) used X window properties and is inherently X11-specific. The modern replacement is the **StatusNotifierItem** (SNI) D-Bus protocol, created by KDE and subsequently adopted by GNOME, Electron apps, and most modern system daemons. Wayland-native bars that implement SNI — Waybar, Quickshell, eww — display these icons correctly. The gap occurs when an app implements the old X11 protocol instead of SNI, or when the bar's SNI host is misconfigured.

This chapter covers the SNI protocol in depth, bar-side configuration for Waybar and Quickshell, the `snixembed` bridge for legacy X11 tray icons, per-app SNI implementation status, and troubleshooting.

**Cross-references:** Ch 26 — bars and panels overview. Ch 104 — Waybar CSS (styling tray icons). Ch 22 — Quickshell system services (Tray module). Ch 93 — D-Bus session bus fundamentals.

---

## 111.1 StatusNotifierItem: Protocol Overview

SNI is a D-Bus protocol with three participants:

```
Application                 StatusNotifierWatcher           Bar (StatusNotifierHost)
(StatusNotifierItem)        (system-wide registry)          (renders icons)

1. Register:
   RegisterStatusNotifierItem(service) ──────────────────►
                                                           2. Notify host:
                             StatusNotifierItemRegistered ──────────────────►
3. Bar queries item:
   ◄──────── Get(Title, Icon, Menu, ...)

4. User clicks icon:
   ◄──────── Activate(x, y) or ContextMenu(x, y)
```

### The Three Roles

**StatusNotifierItem** (the app): registers a D-Bus service under a well-known name (`org.kde.StatusNotifierItem-PID-ID`), exposes a set of properties (icon name, tooltip, status), and signals (NewIcon, NewStatus, etc.), and implements the `Activate`, `SecondaryActivate`, `ContextMenu`, and `Scroll` methods.

**StatusNotifierWatcher**: a singleton service at `org.kde.StatusNotifierWatcher`. It maintains the list of registered items and registered hosts. In a Plasma session, KWin runs the watcher. On other compositors, the bar (Waybar, Quickshell) or a standalone daemon (`xembedsniproxy`, `snixembed`) must register one.

**StatusNotifierHost** (the bar): registers itself with the watcher, subscribes to registration events, and displays an icon for each registered item. One host can be registered per session (the watcher notifies the host of additions and removals).

### D-Bus Interface Summary

```
org.kde.StatusNotifierItem
  Properties:
    Category         STRING  — ApplicationStatus | Communications | SystemServices | Hardware
    Id               STRING  — unique ID for the application
    Title            STRING  — human-readable name (tooltip)
    Status           STRING  — Passive | Active | NeedsAttention
    IconName         STRING  — XDG icon theme name
    IconPixmap       a(iiay) — array of (width, height, ARGB data) for custom icons
    AttentionIconName STRING  — icon shown in NeedsAttention state
    ToolTip          (sa(iiay)ss) — (icon-name, icon-data, title, description)
    ItemIsMenu       BOOL    — if true, primary click opens menu instead of Activate
    Menu             OBJECT  — D-Bus object path to a com.canonical.dbusmenu menu

  Methods:
    Activate(x INT, y INT)
    SecondaryActivate(x INT, y INT)
    ContextMenu(x INT, y INT)
    Scroll(delta INT, orientation STRING)

  Signals:
    NewIcon
    NewAttentionIcon
    NewOverlayIcon
    NewToolTip
    NewStatus(status STRING)
    XAyatanaNewLabel(label STRING, guide STRING)  [Ayatana extension, Ubuntu]
```

---

## 111.2 Which Apps Use SNI

| App | Protocol | Notes |
|---|---|---|
| Steam | SNI (libappindicator) | Works with any SNI host |
| Discord | SNI (Electron) | Uses `@electron/systray` which implements SNI |
| Slack | SNI (Electron) | Same as Discord |
| Nextcloud Desktop | SNI (Qt) | Uses Qt's SNI implementation |
| KeePassXC | SNI (Qt) | Full SNI including context menu |
| NetworkManager (nm-applet) | SNI (libappindicator) | Requires a running watcher |
| Blueman (blueman-applet) | SNI (libappindicator) | |
| Dropbox | X11 legacy tray | Requires `snixembed` |
| Spotify | X11 legacy tray on Linux | Requires `snixembed` |
| Telegram Desktop | SNI | |
| PulseAudio/PipeWire (pasystray) | SNI | |
| Syncthing (syncthing-gtk) | SNI | |
| Thunderbird | SNI | |
| qBittorrent | X11 legacy tray | Requires `snixembed` |
| Skype | SNI | |
| 1Password | SNI | |
| Bitwarden | SNI (Electron) | |
| VirtualBox | X11 legacy tray | Requires `snixembed` |
| Remmina | SNI | |

Apps in the "X11 legacy tray" row use `XEmbed` (the old protocol) and require the `snixembed` bridge (§111.6) to appear in a Wayland tray.

---

## 111.3 Waybar Tray Module

Waybar ships a built-in SNI host. Enabling it requires only adding `"tray"` to the bar's modules list.

### Basic Configuration

```json
// ~/.config/waybar/config.jsonc
{
    "layer": "top",
    "position": "top",
    "modules-left": ["hyprland/workspaces"],
    "modules-center": ["clock"],
    "modules-right": ["tray", "pulseaudio", "battery"],

    "tray": {
        "icon-size": 20,
        "spacing": 8,
        "show-passive-items": false,    // hide Passive-status items
        "reverse-direction": false,     // icon order: first-registered first
        "tooltip": true
    }
}
```

### CSS Styling

```css
/* ~/.config/waybar/style.css */
#tray {
    margin: 0 4px;
}

#tray > .passive {
    -gtk-icon-effect: dim;
    opacity: 0.6;
}

#tray > .needs-attention {
    -gtk-icon-effect: highlight;
    background-color: alpha(@yellow, 0.2);
    border-radius: 4px;
    animation: attention-pulse 1s ease-in-out infinite;
}

@keyframes attention-pulse {
    0%   { background-color: alpha(@yellow, 0.2); }
    50%  { background-color: alpha(@yellow, 0.5); }
    100% { background-color: alpha(@yellow, 0.2); }
}
```

### Waybar as the SNI Watcher

When Waybar's tray module is active, Waybar registers itself as both the StatusNotifierWatcher and the StatusNotifierHost. This means apps registered before Waybar starts may not appear (they registered with no watcher). Always ensure Waybar starts before your apps in session startup (see Ch 53), or use a standalone watcher (§111.5).

---

## 111.4 Quickshell SystemTray

Quickshell exposes SNI through the `SystemTray` singleton, which provides a live model of all registered tray items.

### Basic Tray Widget

```qml
import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Services.SystemTray

// In your bar's Item:
RowLayout {
    spacing: 6

    Repeater {
        model: SystemTray.items

        delegate: Item {
            id: trayItem
            required property SystemTrayItem modelData

            width: 22
            height: 22

            // Icon
            Image {
                anchors.centerIn: parent
                source: modelData.icon
                width: 20
                height: 20
                smooth: true
                mipmap: true
            }

            // Left click: activate or open menu
            TapHandler {
                onTapped: {
                    if (modelData.hasMenu)
                        trayItem.openMenu()
                    else
                        modelData.activate()
                }
                onLongPressed: trayItem.openMenu()
            }

            // Right click: always open menu
            TapHandler {
                acceptedButtons: Qt.RightButton
                onTapped: trayItem.openMenu()
            }

            // Tooltip
            HoverHandler {
                onHoveredChanged: {
                    if (hovered && modelData.tooltip !== "")
                        toolTipText.text = modelData.tooltip
                }
            }

            function openMenu() {
                if (modelData.hasMenu)
                    modelData.menu.open(trayItem)
            }
        }
    }
}
```

### Menu Rendering

Quickshell's `SystemTrayItem.menu` is a `QsMenuHandle` that can be opened as a native QML menu or a popup:

```qml
// Open as a platform menu (native-looking)
modelData.menu.open(trayItem, Qt.point(0, height))
```

### Filtering by Status

```qml
Repeater {
    model: SystemTray.items.filter(item =>
        item.status !== SystemTrayItem.Status.Passive || showPassive)
    // ...
}
```

### Attention Animation

```qml
SequentialAnimation on opacity {
    running: modelData.status === SystemTrayItem.Status.NeedsAttention
    loops: Animation.Infinite
    NumberAnimation { to: 0.3; duration: 500; easing.type: Easing.InOutSine }
    NumberAnimation { to: 1.0; duration: 500; easing.type: Easing.InOutSine }
}
```

---

## 111.5 Standalone StatusNotifierWatcher

Some setups need the SNI watcher to be running before any bar or app starts — for example, when apps are launched at session start via systemd user services that execute before Waybar. The standalone watcher `snixembed` (§111.6) includes a watcher, or you can use `xembedsniproxy` (from KDE) as a watcher-only daemon.

### xembedsniproxy (KDE)

```bash
# Arch
sudo pacman -S xembedsniproxy    # part of plasma-workspace

# Run standalone (registers as watcher + XEmbed bridge)
/usr/lib/x86_64-linux-gnu/libexec/xembedsniproxy &
# or on Arch:
/usr/lib/kf6/xembedsniproxy &
```

`xembedsniproxy` registers `org.kde.StatusNotifierWatcher` on the session bus and also bridges XEmbed tray icons to SNI (bridging legacy X11 apps). It requires XWayland to be running for the XEmbed side.

### swaybar-protocol watcher (swaybar users)

Sway's built-in bar (`swaybar`) has its own tray implementation using `xembedsniproxy`. If you use Waybar alongside Sway, disable swaybar's tray to avoid watcher conflicts:

```
# ~/.config/sway/config
bar {
    swaybar_command waybar  # use Waybar instead of swaybar
    # swaybar's tray is not started when swaybar_command is overridden
}
```

---

## 111.6 snixembed: Legacy X11 Tray Bridge

Apps like Dropbox, older Spotify, qBittorrent, and VirtualBox implement the old `_NET_SYSTEM_TRAY_OPCODE` X11 protocol instead of SNI. They call `XSendEvent` on the selection owner window set by the tray host. Without a running X11 tray host on XWayland, these icons simply disappear.

`snixembed` solves this by running a minimal X11 tray host inside XWayland, intercepting `XEmbed` icon requests, and forwarding them to the session bus as proper SNI items. The Waybar or Quickshell tray then picks them up as normal SNI icons.

### Installation

```bash
# Arch AUR
yay -S snixembed

# From source
git clone https://github.com/nicowillis/snixembed
cd snixembed
make
install -Dm755 snixembed ~/.local/bin/snixembed
```

snixembed requires XWayland (for the X11 side) and a running SNI watcher (provided by Waybar, Quickshell, or xembedsniproxy).

### Session Startup

```ini
# ~/.config/hypr/hyprland.conf
exec-once = waybar &
exec-once = sleep 1 && snixembed --fork  # start after Waybar registers the watcher
```

Or as a systemd user service:

```ini
# ~/.config/systemd/user/snixembed.service
[Unit]
Description=XEmbed to StatusNotifierItem bridge
After=graphical-session.target

[Service]
ExecStart=/usr/local/bin/snixembed --fork
Restart=on-failure

[Install]
WantedBy=graphical-session.target
```

### Verifying snixembed Is Working

```bash
# Check that snixembed registered as a tray host on X11
DISPLAY=:0 xprop -root | grep TRAY

# Check SNI items on D-Bus
busctl --user call org.kde.StatusNotifierWatcher \
    /StatusNotifierWatcher org.kde.StatusNotifierWatcher \
    RegisteredStatusNotifierItems

# Or watch for new registrations
dbus-monitor --session "interface='org.kde.StatusNotifierWatcher'"
```

---

## 111.7 eww Systray Widget

eww has a built-in `systray` widget that acts as an SNI host:

```yuck
(defwidget tray []
  (systray
    :class "tray"
    :orientation "h"
    :spacing 8
    :icon-size 20
    :prepend-new false))   ; false = append new icons to the right
```

Place it inside a `defwindow`:

```yuck
(defwidget bar-right []
  (box :orientation "h" :space-evenly false :spacing 8
    (volume-widget)
    (tray)
    (clock-widget)))
```

The eww systray also registers as a watcher, so no separate watcher process is needed when using eww as your bar.

---

## 111.8 D-Bus Debugging

### List All Registered SNI Items

```bash
busctl --user introspect org.kde.StatusNotifierWatcher \
    /StatusNotifierWatcher

# Get the list of registered items
busctl --user get-property org.kde.StatusNotifierWatcher \
    /StatusNotifierWatcher org.kde.StatusNotifierWatcher \
    RegisteredStatusNotifierItems
```

### Inspect a Specific Item

```bash
# Find the item's bus name from the watcher output (e.g., :1.42)
busctl --user introspect :1.42 /StatusNotifierItem

# Get its icon name
busctl --user get-property :1.42 /StatusNotifierItem \
    org.kde.StatusNotifierItem IconName

# Get its title
busctl --user get-property :1.42 /StatusNotifierItem \
    org.kde.StatusNotifierItem Title

# Get its status
busctl --user get-property :1.42 /StatusNotifierItem \
    org.kde.StatusNotifierItem Status
```

### Monitor All SNI Traffic

```bash
dbus-monitor --session \
    "interface='org.kde.StatusNotifierWatcher'" \
    "interface='org.kde.StatusNotifierItem'"
```

### Call an Item's Method

```bash
# Simulate a left click on an item
busctl --user call :1.42 /StatusNotifierItem \
    org.kde.StatusNotifierItem Activate ii 0 0

# Open context menu
busctl --user call :1.42 /StatusNotifierItem \
    org.kde.StatusNotifierItem ContextMenu ii 0 0
```

---

## 111.9 Ayatana / libappindicator Extension

Ubuntu's `libappindicator` added an Ayatana extension to the SNI protocol. The most visible addition is `XAyatanaNewLabel(label, guide)` — a text label that appears next to the icon (used by email clients to show unread count). Some bars support this; others ignore it.

Apps using Ayatana extensions: `nm-applet` (network status text), Thunderbird (unread count in some configurations), `indicator-*` family from Ubuntu.

If an app's icon appears but the label does not, your bar's tray module likely doesn't implement the Ayatana extension. Waybar does not display Ayatana labels; Quickshell can access them via `SystemTrayItem.xAyatanaLabel`.

---

## 111.10 Troubleshooting

### Tray is empty / no icons appear

1. Check that a StatusNotifierWatcher is running:
   ```bash
   busctl --user status org.kde.StatusNotifierWatcher 2>&1 | head -5
   ```
   If it errors, no watcher is running. Start Waybar, Quickshell, or `xembedsniproxy` first.

2. Check that the app is running and has registered:
   ```bash
   busctl --user | grep StatusNotifier
   ```

3. Ensure Waybar's `tray` module is in the modules list (not just in the module config block).

### Icons appear but are missing for one specific app

The app may use the old X11 protocol. Check:
```bash
DISPLAY=:0 xprop -root _NET_SYSTEM_TRAY_S0
```
If this returns a window ID, an X11 tray host is already running (likely snixembed). If not, start snixembed.

### Icons appear but click does nothing

Check the item's menu vs. Activate behaviour:
```bash
busctl --user get-property :1.XX /StatusNotifierItem \
    org.kde.StatusNotifierItem ItemIsMenu
```
If `true`, the item expects `ContextMenu` on left click, not `Activate`. Ensure your bar passes `ItemIsMenu` correctly.

### Two watchers conflict (Waybar + KWin both running)

On a KDE/Hyprland hybrid setup, KWin may register the watcher. If Waybar also tries to register, one will fail silently. Check:
```bash
busctl --user status org.kde.StatusNotifierWatcher
```
The "Unit:" field shows which service owns the name. If it's KWin, Waybar's watcher registration failed but the icons still appear through KWin's watcher. This is usually fine.

### Steam / Discord icon appears but disappears after a few seconds

These apps check that the watcher is still alive. If Waybar restarts (config reload), the watcher temporarily disappears and the app de-registers. `exec-once = waybar` ensures Waybar only starts once; avoid restarting it just to reload — use `pkill -SIGUSR2 waybar` instead (hot-reload without restart).

```bash
# Reload Waybar config without restarting (preserves SNI registration)
pkill -SIGUSR2 waybar
```

### Icons are too small / blurry

The icon size in the tray config must match the bar height. For a 36px bar:
```json
"tray": {
    "icon-size": 22   // typically bar-height - 14px for margins
}
```
If icons are still blurry, the app is providing a low-resolution bitmap. Check `IconPixmap` sizes:
```bash
busctl --user get-property :1.XX /StatusNotifierItem \
    org.kde.StatusNotifierItem IconPixmap
```
Apps should provide multiple pixmap sizes; if only one is given and it's 16×16, nothing can be done on the bar side.

---

## Summary

The system tray on Wayland requires an SNI watcher (provided by Waybar, Quickshell's `SystemTray`, or a standalone daemon like `xembedsniproxy`), a bar module that acts as the SNI host, and optionally `snixembed` to bridge legacy X11 tray icons. Most modern apps (Steam, Discord, Nextcloud, KeePassXC, nm-applet) implement SNI natively; older apps (Dropbox, qBittorrent) need the XEmbed bridge. The `busctl` commands in §111.8 are the primary debugging tool — they let you verify what is registered, inspect icon state, and simulate clicks without touching the bar.

**Further reading:**
- Ch 26 — bars and panels: Waybar, eww, Quickshell bar setup
- Ch 93 — D-Bus session bus fundamentals
- Ch 104 — Waybar CSS (tray icon styling)
- Ch 53 — session startup order (watcher must start before apps)
