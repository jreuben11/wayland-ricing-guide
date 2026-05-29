# Chapter 29 — Notification Daemons: mako, dunst, swaync

## Overview
Notification daemons implement `org.freedesktop.Notifications` on D-Bus and
render popups using layer-shell. Alternatively, Quickshell can handle this natively.

## Sections

### 29.1 The Freedesktop Notification Spec
- D-Bus interface: `org.freedesktop.Notifications`
- `Notify` method: app_name, id, icon, summary, body, actions, hints, timeout
- `NotificationClosed` / `ActionInvoked` signals
- Urgency levels: 0=Low, 1=Normal, 2=Critical
- `x-dunst-stack-tag`, `x-canonical-private-synchronous`: vendor hints

### 29.2 mako — Minimal Sway-Focused Daemon
- Config: `~/.config/mako/config`
- Criteria-based styling: `[app-name="firefox"] border-color=#ff0000`
- `max-visible`, `sort`: notification stack behavior
- `default-timeout`, `ignore-timeout`
- `makoctl`: runtime control (`dismiss`, `restore`, `invoke`, `menu`)
- Fonts, colors, border, border-radius, padding config
- Anchor and margin for positioning

### 29.3 dunst — The Feature-Rich Daemon
- Highly configurable INI config
- Rules: matching by app_name, summary, urgency
- Actions: scripts triggered by notification events
- History: `dunstctl history-pop` to see past notifications
- `dunstctl set-paused true`: do-not-disturb mode
- Progress bar support (hint: `value=N`)
- `context` menu for action selection
- Recursive replacement by ID

### 29.4 swaync — SwayNotificationCenter
- Notification center (drawer/sidebar) + popups
- Toggle: `swaync-client -t` (open/close the panel)
- Config JSON + CSS styling
- DND mode: `swaync-client --dnd-on`
- Waybar integration: `custom/swaync` module
- Action widgets in notifications
- Per-app notification rules

### 29.5 Quickshell Native Notifications (Ch 22 Recap)
- Replace the daemon entirely with Quickshell's `NotificationServer`
- Full visual control: animations, custom layout, any QML widget
- Action buttons, image attachments, progress bars
- Notification history sidebar

### 29.6 Notification Styling Guide
- Popup positioning: top-right vs. bottom-right vs. bottom-center
- Stack behavior: newest on top vs. bottom
- Animation: slide in, fade out
- Critical notifications: persistent, different styling
- Do-not-disturb / focus mode implementation

### 29.7 Testing Notifications
```bash
notify-send "Test" "This is a notification" --urgency=normal
notify-send "Critical!" "Something broke" --urgency=critical --expire-time=0
notify-send "Progress" "Downloading..." -h int:value:42
```
