# Appendix D — Quickshell API Quick Reference

## Import Map

```qml
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland
import Quickshell.I3
import Quickshell.Widgets
import Quickshell.DBusMenu
import Quickshell.Services.Notifications
import Quickshell.Services.Mpris
import Quickshell.Services.Pipewire
import Quickshell.Services.UPower
import Quickshell.Services.SystemTray
import Quickshell.Services.Pam
import Quickshell.Services.Greetd
```

---

## Quickshell (Core)

### Global Singleton: `Quickshell`
| Property/Method | Type | Description |
|----------------|------|-------------|
| `screens` | `list<QsScreen>` | All connected outputs (reactive) |
| `workingDirectory` | `string` | Config directory path |
| `reload()` | method | Hot-reload configuration |

### QsScreen
| Property | Type | Description |
|----------|------|-------------|
| `name` | `string` | Output name (e.g. "DP-1") |
| `width`, `height` | `int` | Resolution in pixels |
| `x`, `y` | `int` | Position in compositor space |
| `model` | `string` | Monitor model string |
| `refreshRate` | `real` | Refresh rate in Hz |
| `devicePixelRatio` | `real` | Scale factor |

### Window Types
| Type | Protocol | Use case |
|------|----------|----------|
| `PanelWindow` | zwlr-layer-shell | Bars, widgets, wallpapers |
| `FloatingWindow` | xdg-toplevel | Regular app windows |
| `PopupWindow` | xdg-popup | Transient overlays |

### PanelWindow Key Properties
| Property | Type | Description |
|----------|------|-------------|
| `screen` | `QsScreen` | Target output |
| `anchors` | `Edges` | `Edges.Top \| Edges.Left \| Edges.Right` etc. |
| `margins` | `Margins` | Margin from anchored edges |
| `exclusiveZone` | `int` | Pixels to reserve (-1 = ignore layout) |
| `layer` | `WlrLayer` | Background/Bottom/Top/Overlay |
| `keyboardFocus` | `WlrKeyboardFocus` | None/OnDemand/Exclusive |

### Utility Types
| Type | Description |
|------|-------------|
| `Variants { model: list }` | One instance per model item |
| `LazyLoader { active: bool }` | Conditional component creation |
| `Scope {}` | Non-visual grouping |
| `SystemClock` | `time`, `date`, `updateInterval` |
| `PersistentProperties {}` | Survives hot-reload |

---

## Quickshell.Io

| Type | Key Properties/Methods | Description |
|------|----------------------|-------------|
| `Process` | `command`, `running`, `stdout`, `stderr`, `onExited` | Run shell commands |
| `StdioCollector` | `text`, `onStreamFinished` | Collect all output |
| `SplitParser` | `splitMarker`, `onRead(data)` | Line-by-line streaming |
| `FileView` | `path`, `text`, `watchChanges` | Read/watch files |
| `Socket` | `path`, `connected`, `send(data)` | Unix socket client |
| `SocketServer` | `path`, `onConnection` | Unix socket server |
| `IpcHandler` | `defineFunction(name, fn)` | External IPC endpoint |
| `JsonAdapter` | `sourceModel`, `property` | Parse JSON reactively |
| `DataStream` | `source` | Streaming data source |

---

## Quickshell.Wayland

| Type | Key Properties/Methods | Description |
|------|----------------------|-------------|
| `ToplevelManager` | `.toplevels: list<Toplevel>` | All open windows |
| `Toplevel` | `title`, `appId`, `activated`, `maximized` | Window info |
| `Toplevel` | `activate()`, `close()`, `minimize()` | Window control |
| `WlrLayershell` | `layer`, `namespace`, `exclusiveZone` | Layer shell attachment |
| `WlSessionLock` | `locked: bool`, `onUnlocked` | Session lock |
| `WlSessionLockSurface` | `screen` | Per-output lock surface |
| `ScreencopyView` | `captureSource`, `liveUpdates` | Screen capture widget |
| `WlrKeyboardFocus` | enum: None/OnDemand/Exclusive | Keyboard focus mode |
| `WlrLayer` | enum: Background/Bottom/Top/Overlay | Layer enum |

---

## Quickshell.Hyprland

| Type | Key Properties/Methods | Description |
|------|----------------------|-------------|
| `Hyprland` | `.monitors`, `.workspaces`, `.clients` | Global state |
| `Hyprland` | `.focusedMonitor`, `.focusedClient` | Focus tracking |
| `Hyprland` | `.dispatch(cmd)`, `.keyword(k,v)` | Compositor control |
| `HyprlandMonitor` | `id`, `name`, `width`, `height`, `scale` | Output info |
| `HyprlandMonitor` | `activeWorkspace`, `focused` | Monitor state |
| `HyprlandWorkspace` | `id`, `name`, `monitor`, `windows` | Workspace info |
| `HyprlandWindow` | `address`, `title`, `class`, `workspace`, `floating` | Window info |
| `HyprlandEvent` | `onActiveWindowV2Changed`, `onWorkspaceChanged` | Raw events |
| `HyprlandFocusGrab` | `active` | Input focus grab |
| `GlobalShortcut` | `name`, `description`, `onPressed` | Global hotkey |

---

## Quickshell.I3

| Type | Key Properties/Methods | Description |
|------|----------------------|-------------|
| `I3` | `.workspaces`, `.monitors`, `.focusedWorkspace` | Global state |
| `I3` | `.command(cmd)` | i3/Sway IPC command |
| `I3Monitor` | `name`, `rect`, `focused` | Output info |
| `I3Workspace` | `id`, `name`, `focused`, `urgent` | Workspace info |
| `I3Event` | `onWorkspaceEvent`, `onWindowEvent` | Raw events |

---

## Quickshell.Services.Notifications

| Type | Key Properties/Methods | Description |
|------|----------------------|-------------|
| `NotificationServer` | `onNotification(notif)` | D-Bus notification server |
| `Notification` | `summary`, `body`, `appName`, `appIcon` | Notification data |
| `Notification` | `urgency`, `expireTimeout`, `actions` | Notification metadata |
| `Notification` | `dismiss()`, `invoke(actionId)` | Notification control |
| `NotificationUrgency` | Low/Normal/Critical | Urgency enum |
| `NotificationAction` | `id`, `text` | Action button |

---

## Quickshell.Services.Mpris

| Type | Key Properties/Methods | Description |
|------|----------------------|-------------|
| `MprisController` | `.players: list<MprisPlayer>` | All MPRIS players |
| `MprisPlayer` | `trackTitle`, `trackArtist`, `trackAlbum` | Track info |
| `MprisPlayer` | `trackArtUrl`, `position`, `length` | Playback state |
| `MprisPlayer` | `playbackState`, `loopState`, `shuffleState` | Player state |
| `MprisPlayer` | `play()`, `pause()`, `playPause()`, `next()`, `previous()` | Control |
| `MprisPlayer` | `seek(delta)`, `setPosition(pos)` | Position control |
| `MprisPlaybackState` | Playing/Paused/Stopped | State enum |

---

## Quickshell.Services.Pipewire

| Type | Key Properties/Methods | Description |
|------|----------------------|-------------|
| `PipeWire` | `.nodes`, `.defaultAudioSink`, `.defaultAudioSource` | Graph access |
| `PwNode` | `id`, `name`, `description`, `type`, `running` | Node info |
| `PwNodeAudio` | `volume`, `muted`, `channels` | Audio properties |
| `PwNodeAudio` | `volumeFor(channel)` | Per-channel volume |
| `PwLink` | `output`, `input` | Node connection |
| `PwNodeType` | Sink/Source/Stream | Node type enum |

---

## Quickshell.Services.UPower

| Type | Key Properties/Methods | Description |
|------|----------------------|-------------|
| `UPower` | `.devices: list<UPowerDevice>` | All power devices |
| `UPower` | `.onBattery`, `.lidIsClosed` | System power state |
| `UPowerDevice` | `percentage`, `state`, `type` | Battery info |
| `UPowerDevice` | `timeToEmpty`, `timeToFull`, `energy` | Charge details |
| `UPowerDeviceState` | Charging/Discharging/FullyCharged/etc | State enum |
| `UPowerDeviceType` | Battery/LinePower/Ups/etc | Type enum |

---

## Quickshell.Services.SystemTray

| Type | Key Properties/Methods | Description |
|------|----------------------|-------------|
| `SystemTray` | `.items: list<SystemTrayItem>` | All tray items |
| `SystemTrayItem` | `title`, `icon`, `tooltip`, `status` | Item info |
| `SystemTrayItem` | `menu: DBusMenuHandle` | Right-click menu |
| `SystemTrayItem` | `activate(x,y)`, `secondaryActivate(x,y)` | Click actions |
| `SystemTrayItemStatus` | Active/Passive/NeedsAttention | Status enum |

---

## Quickshell.Services.Pam

| Type | Key Properties/Methods | Description |
|------|----------------------|-------------|
| `PamContext` | `configurationName`, `onConversationRequest` | PAM auth session |
| `PamContext` | `authenticate()`, `onAuthComplete(success, msg)` | Auth control |
| `PamMessage` | `type`, `message`, `respond(text)` | Conversation message |
| `PamMessageType` | Prompt/PromptEcho/Info/Error | Message type enum |

---

## Quickshell.Services.Greetd

| Type | Key Properties/Methods | Description |
|------|----------------------|-------------|
| `Greetd` | `onRequestSecret`, `onAuthComplete`, `onError` | Login session |
| `Greetd` | `respond(text)`, `startSession(cmd)`, `cancelSession()` | Control |
| `GreetdErrorType` | AuthError/Error | Error type enum |

---

## Quickshell.Widgets

| Type | Description |
|------|-------------|
| `ClippingRectangle` | Rectangle with rounded-corner clipping |
| `IconImage` | System icon by name (resolves icon theme) |
| `WrapperManager` | Layout wrapper with margin and mouse area |

---

## DBusMenu

| Type | Key Properties | Description |
|------|---------------|-------------|
| `DBusMenuHandle` | `rootItem`, `open(x,y)` | D-Bus menu root |
| `DBusMenuItem` | `label`, `icon`, `enabled`, `children` | Menu item |
| `DBusMenuItem` | `onTriggered`, `checkState` | Item signals |
