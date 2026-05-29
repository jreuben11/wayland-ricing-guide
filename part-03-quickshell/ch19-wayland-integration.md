# Chapter 19 — Wayland Integration: Layer Shell, ToplevelManager, ScreenCopy

## Overview

The `Quickshell.Wayland` module is the bridge between your QML shell components and the underlying Wayland compositor protocols. Unlike X11, where a single global root window and EWMH atoms provided a chaotic but functional IPC mechanism, Wayland enforces strict protocol boundaries. Every capability — window listing, screen capture, session locking, keyboard grabs — requires explicit protocol support from the compositor and explicit opt-in from the client.

Quickshell wraps these protocols into idiomatic QML types that fit naturally into reactive, declarative UI code. The result is that tasks like building a taskbar, an overview screen, or a lockscreen can be written in a few dozen lines of QML rather than hundreds of lines of C. However, understanding the underlying protocols is essential when things go wrong or when compositors differ in their support level.

This chapter covers the full surface area of `Quickshell.Wayland`: the layer shell for panel positioning, the toplevel manager for window lists, screencopy for GPU-accelerated capture, session locking, keyboard focus grabbing, and the edge cases introduced by XWayland. Each section pairs API documentation with complete, copy-paste-ready examples.

**Prerequisites:** Chapters 17 (PanelWindow) and 18 (Quickshell core). For PAM integration with the lockscreen, see Chapter 24. For session startup and service ordering, see Chapter 53.

---

## 19.1 WlrLayershell and WlrLayer

The `wlr-layer-shell-unstable-v1` protocol (now effectively a stable de-facto standard despite its name) defines a special surface type that compositors place outside the normal window stack. Layer surfaces are anchored to screen edges, assigned to one of four z-order layers, and can claim exclusive zones that push other windows away.

In Quickshell, the `WlrLayershell` attached type is automatically applied to any `PanelWindow`. You interact with it via the `WlrLayershell` namespace on the window object. The most important properties are `layer` (which compositor layer the surface occupies), `namespace` (a string identifier used for compositor rules), and `exclusiveZone` (how many pixels of screen space to reserve).

The four layers, from bottom to top, are `WlrLayer.Background`, `WlrLayer.Bottom`, `WlrLayer.Top`, and `WlrLayer.Overlay`. Wallpaper managers render on `Background`. Most panels live on `Top`. Lockscreens and notifications that must appear above everything use `Overlay`. The `Bottom` layer is useful for desktop widgets that should sit above the wallpaper but below windows — conky replacements, icon grids, and so on.

The `namespace` string is a low-overhead way to let compositors identify your surfaces for rules. In Hyprland, the `layerrule` directive matches on namespace strings. This is how you apply blur, transparency, and animations to specific shell components without affecting others. Use short, descriptive, hyphen-separated names like `quickshell-bar`, `quickshell-launcher`, or `quickshell-notifications`.

```qml
// panels/TopBar.qml
import Quickshell
import Quickshell.Wayland

PanelWindow {
    id: topBar

    // Anchor to top edge, full width
    anchors {
        top: true
        left: true
        right: true
    }
    height: 36

    // Layer shell configuration via attached type
    WlrLayershell.layer: WlrLayer.Top
    WlrLayershell.namespace: "quickshell-bar"
    WlrLayershell.exclusiveZone: height   // reserve 36px for window tiling

    // Keyboard interactivity: none for a passive panel
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

    color: "transparent"

    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0.1, 0.1, 0.1, 0.85)
        // ... bar content
    }
}
```

In your Hyprland config, you can then reference this namespace:

```ini
# ~/.config/hypr/hyprland.conf

layerrule = blur, quickshell-bar
layerrule = ignorealpha 0.3, quickshell-bar
layerrule = animation slide top, quickshell-launcher
layerrule = noanim, quickshell-notifications
```

For a bottom dock with auto-hide, you would set `exclusiveZone` to `0` when hidden and restore it to the dock height when revealed. The compositor will reflow tiled windows accordingly — though note that rapid changes can cause a brief reflow flicker on some compositors.

```qml
// A dock that collapses to a 4px sliver
PanelWindow {
    id: dock

    property bool revealed: false

    anchors { bottom: true; left: true; right: true }
    height: revealed ? 56 : 4

    WlrLayershell.layer: WlrLayer.Top
    WlrLayershell.namespace: "quickshell-dock"
    WlrLayershell.exclusiveZone: revealed ? 56 : 0

    Behavior on height { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }

    HoverHandler {
        onHoveredChanged: dock.revealed = hovered
    }
}
```

---

## 19.2 ToplevelManager — Window List Access

The `wlr-foreign-toplevel-management-unstable-v1` protocol lets privileged clients — specifically layer shell surfaces — observe and control the window list. Quickshell exposes this through the `ToplevelManager` singleton. It provides a reactive model of all compositor-managed toplevels (normal application windows), updated automatically as windows open, close, focus, maximize, or minimize.

`ToplevelManager.toplevels` is a `QAbstractListModel` that you can bind directly to `Repeater` or `ListView`. Each element is a `Toplevel` object with observable properties and callable methods. The key read properties are `title` (window title string), `appId` (application identifier, usually the `.desktop` file name minus the extension), `activated` (whether the window has focus), `maximized`, `minimized`, and `fullscreen`. The writable methods are `activate()`, `minimize()`, `unminimize()`, `close()`, `requestMaximize()`, and `requestUnmaximize()`.

A complete taskbar implementation typically filters and groups toplevels by workspace, then renders a button row. Quickshell does not expose workspace data directly through ToplevelManager — that information comes from compositor-specific protocols (see Chapter 20 for Hyprland's IPC and Chapter 21 for niri's event socket). The pattern is to correlate toplevel `appId` and `title` against workspace data to build a combined model.

```qml
// components/Taskbar.qml
import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland

Item {
    id: taskbar

    RowLayout {
        anchors.fill: parent
        spacing: 4

        Repeater {
            model: ToplevelManager.toplevels

            delegate: TaskButton {
                required property Toplevel modelData
                required property int index

                title:    modelData.title
                appId:    modelData.appId
                active:   modelData.activated
                minimized: modelData.minimized

                onClicked: {
                    if (modelData.minimized) {
                        modelData.unminimize()
                        modelData.activate()
                    } else if (modelData.activated) {
                        modelData.minimize()
                    } else {
                        modelData.activate()
                    }
                }

                onMiddleClicked: modelData.close()
            }
        }
    }
}
```

For an application launcher that tracks running instances, combine `ToplevelManager` with your app list to show running indicators:

```qml
// Pinned app with running dot
Repeater {
    model: pinnedApps   // your static list of { appId, name, icon }

    delegate: AppIcon {
        required property var modelData

        property int runningCount: {
            var count = 0
            for (var i = 0; i < ToplevelManager.toplevels.count; i++) {
                if (ToplevelManager.toplevels.get(i).appId === modelData.appId)
                    count++
            }
            return count
        }

        showDot: runningCount > 0
        showBadge: runningCount > 1
        badgeText: runningCount.toString()
    }
}
```

For an expose/overview effect, you can render miniature representations of each window. Without ScreencopyView (covered next), you fall back to rendering the window's icon and title card. With ScreencopyView, you render an actual live preview. The two approaches are covered together in Section 19.3.

| Property | Type | Description |
|---|---|---|
| `title` | `string` | Current window title |
| `appId` | `string` | App identifier (WM_CLASS for XWayland) |
| `activated` | `bool` | Window has input focus |
| `maximized` | `bool` | Window is maximized |
| `minimized` | `bool` | Window is minimized |
| `fullscreen` | `bool` | Window is in fullscreen mode |

| Method | Description |
|---|---|
| `activate()` | Raise and focus the window |
| `minimize()` | Minimize the window |
| `unminimize()` | Restore from minimized |
| `close()` | Request the window close |
| `requestMaximize()` | Ask compositor to maximize |
| `requestUnmaximize()` | Ask compositor to unmaximize |

---

## 19.3 ScreencopyView — Screen Capture in QML

`ScreencopyView` is a QML `Item` that renders a live (or single-frame) copy of a compositor surface — either a full screen output or a specific `Toplevel`. Under the hood, it uses the `wlr-screencopy-v1` protocol, which copies frames from the compositor's GPU buffer into a texture that Qt can render. On most hardware this stays on GPU memory the entire time, avoiding a CPU round-trip.

The `captureSource` property accepts either a `QuickshellScreen` object (from `Quickshell.screens`) or a `Toplevel` object. With `liveUpdates: true`, the view subscribes to frame callbacks and re-renders at the compositor's output refresh rate. With `liveUpdates: false`, it captures a single frame and stops — useful for snapshots, app previews, and thumbnails in an overview grid.

The `ScreencopyView` renders with correct aspect ratio by default. Use the standard `fillMode` property (`Image.Stretch`, `Image.PreserveAspectFit`, `Image.PreserveAspectCrop`) to control how the captured content fits the item's geometry.

```qml
// Full-screen live mirror widget (e.g. for a second monitor preview in a panel)
import Quickshell
import Quickshell.Wayland

ScreencopyView {
    id: screenMirror
    width: 320
    height: 180

    captureSource: Quickshell.screens[1]   // second output
    liveUpdates: true
    fillMode: Image.PreserveAspectFit
}
```

For an overview/expose mode, use `liveUpdates: false` to take a snapshot when the overview opens, then display a grid:

```qml
// Overview.qml — snapshot grid of all open windows
import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland

Item {
    id: overview

    property bool active: false

    onActiveChanged: {
        if (active) captureTimer.start()
    }

    // Delay capture slightly so the overview surface is visible first
    Timer {
        id: captureTimer
        interval: 50
        onTriggered: snapshotRepeater.model = ToplevelManager.toplevels
    }

    GridView {
        anchors.fill: parent
        anchors.margins: 32
        cellWidth: width / 4
        cellHeight: cellWidth * 9 / 16

        model: ToplevelManager.toplevels

        delegate: Item {
            required property Toplevel modelData

            width: GridView.view.cellWidth - 8
            height: GridView.view.cellHeight - 8

            ScreencopyView {
                anchors.fill: parent
                captureSource: parent.modelData
                liveUpdates: false          // snapshot only
                fillMode: Image.PreserveAspectCrop
            }

            // Title overlay
            Rectangle {
                anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
                height: 24
                color: Qt.rgba(0, 0, 0, 0.6)
                Text {
                    anchors.centerIn: parent
                    text: parent.parent.modelData.title
                    color: "white"
                    font.pixelSize: 11
                    elide: Text.ElideRight
                }
            }

            MouseArea {
                anchors.fill: parent
                onClicked: {
                    parent.modelData.activate()
                    overview.active = false
                }
            }
        }
    }
}
```

For a screen magnifier, use a live capture of the current screen output and apply a clip/scale transform:

```qml
// Magnifier lens — shows a 4x zoom around the cursor
ScreencopyView {
    id: magnifier
    width: 200
    height: 200

    captureSource: Quickshell.screens[0]
    liveUpdates: true

    // Clip to a circular lens shape
    layer.enabled: true
    layer.effect: ShaderEffect {
        // simple circular clip
        fragmentShader: "qrc:/shaders/circle_clip.frag"
    }

    // Scale and offset so the center tracks the cursor
    // (requires a separate cursor position source)
    sourceClipRect: Qt.rect(
        cursorPos.x - 25, cursorPos.y - 25, 50, 50
    )
}
```

Performance considerations: each `ScreencopyView` with `liveUpdates: true` adds a full-frame copy per refresh cycle. On a 144 Hz monitor, six simultaneous live captures will produce 864 DMA copies per second. Use `liveUpdates: false` wherever possible for static previews. Stagger captures using short `Timer` delays when multiple snapshots are requested at once. For the GPU path to remain efficient, ensure the Qt scene graph runs with the Vulkan or OpenGL backend — the software rasterizer will serialize everything through CPU memory.

---

## 19.4 WlSessionLock — Building a Lockscreen

The `ext-session-lock-v1` protocol is the modern, security-conscious replacement for ad-hoc lockscreen hacks. When a client engages the lock, the compositor freezes all existing surfaces (no XSS blanker races) and renders only surfaces explicitly submitted by the locking client — one per output. Input is fully inhibited for all other clients. The lock persists until the client explicitly unlocks via the protocol, even if the client crashes (in that case, the compositor stays locked until a new locker connects).

`WlSessionLock` is the Quickshell singleton that manages this protocol. Set `WlSessionLock.locked: true` to engage. You must create a `WlSessionLockSurface` for every connected screen — Quickshell will not unlock until all screens have a surface. Use `Variants` (Quickshell's multi-output repeater) to handle multi-monitor setups correctly.

The lockscreen surface is a special layer surface that the compositor places above everything, including `WlrLayer.Overlay` surfaces. It is not a `PanelWindow` — it is its own QML component type that fills the entire screen output. All input (keyboard, mouse, touch) is delivered exclusively to lock surfaces.

```qml
// lockscreen/LockScreen.qml
import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Wayland

// This component is instantiated by your shell root when a lock is requested
Item {
    id: lockRoot

    WlSessionLock {
        id: sessionLock

        // Set to true to engage the lock protocol
        locked: lockRoot.lockRequested

        // Provide one surface per screen
        Variants {
            model: Quickshell.screens

            WlSessionLockSurface {
                id: lockSurface

                required property QuickshellScreen modelData
                screen: modelData

                // Your lockscreen UI
                LockScreenUI {
                    anchors.fill: parent
                    onUnlocked: sessionLock.locked = false
                }
            }
        }
    }
}
```

```qml
// lockscreen/LockScreenUI.qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    signal unlocked()

    // PAM authentication is handled in Chapter 24.
    // Here we show the UI skeleton.

    Image {
        id: wallpaper
        anchors.fill: parent
        source: "file:///home/user/.config/wallpaper.jpg"
        fillMode: Image.PreserveAspectCrop

        // Blur effect
        layer.enabled: true
        layer.effect: FastBlur { radius: 40 }
    }

    ColumnLayout {
        anchors.centerIn: parent
        spacing: 16

        // Clock
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: Qt.formatTime(new Date(), "hh:mm")
            font.pixelSize: 72
            color: "white"
        }

        Text {
            Layout.alignment: Qt.AlignHCenter
            text: Qt.formatDate(new Date(), "dddd, MMMM d")
            font.pixelSize: 18
            color: Qt.rgba(1, 1, 1, 0.7)
        }

        // Password field
        TextField {
            id: passwordField
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 300
            placeholderText: "Password"
            echoMode: TextInput.Password
            focus: true

            onAccepted: {
                // Call PAM auth (see Chapter 24)
                authService.authenticate(text, function(success) {
                    if (success) root.unlocked()
                    else {
                        passwordField.clear()
                        shakeAnimation.start()
                    }
                })
            }
        }
    }

    // Shake animation on auth failure
    SequentialAnimation {
        id: shakeAnimation
        loops: 1
        NumberAnimation { target: passwordField; property: "x"; from: -8; to: 8; duration: 50 }
        NumberAnimation { target: passwordField; property: "x"; from: 8; to: -8; duration: 50 }
        NumberAnimation { target: passwordField; property: "x"; from: -8; to: 0; duration: 50 }
    }

    // Update clock every second
    Timer {
        interval: 1000
        running: true
        repeat: true
        onTriggered: {
            clockText.text = Qt.formatTime(new Date(), "hh:mm")
            dateText.text = Qt.formatDate(new Date(), "dddd, MMMM d")
        }
    }
}
```

To trigger the lockscreen from an idle daemon or from a keybinding, connect to `WlSessionLock.locked` via a property in your shell root:

```qml
// shell/Root.qml (excerpt)
ShellRoot {
    property bool shouldLock: false

    // Trigger via Hyprland keybind calling `quickshell ipc call lock`
    IpcHandler {
        target: "lock"
        function handle() { shouldLock = true }
    }

    LockScreen {
        lockRequested: shouldLock
    }
}
```

For integration with `swayidle` or `hypridle`, use their lock/unlock commands pointing at your IPC endpoint. See Chapter 53 for service startup ordering to ensure the lockscreen process is ready before idle timers fire.

---

## 19.5 WlrKeyboardFocus — Grabbing Keyboard Input for Layer Surfaces

By default, layer shell surfaces with `WlrLayershell.layer: WlrLayer.Top` do not receive keyboard input — the focused application window continues to receive key events. For interactive overlays like launchers, command palettes, or any surface that needs text input, you must explicitly request keyboard focus.

The `WlrLayershell.keyboardFocus` property accepts three values: `WlrKeyboardFocus.None` (no keyboard events, default for passive panels), `WlrKeyboardFocus.Exclusive` (this surface exclusively receives all keyboard input, stealing it from any focused window), and `WlrKeyboardFocus.OnDemand` (the surface receives keyboard events when a client explicitly moves focus to it).

`Exclusive` is the correct mode for launchers and modal overlays. When the launcher is dismissed, set `keyboardFocus` back to `None` or toggle the surface's visibility — hiding it automatically returns focus to the previously active window on most compositors.

```qml
// launcher/AppLauncher.qml
import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Wayland

PanelWindow {
    id: launcher

    property bool open: false

    visible: open

    anchors { top: true; left: true; right: true }
    height: 400

    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "quickshell-launcher"
    WlrLayershell.exclusiveZone: -1      // do not reserve space
    WlrLayershell.keyboardFocus: open
        ? WlrKeyboardFocus.Exclusive
        : WlrKeyboardFocus.None

    color: "transparent"

    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0.08, 0.08, 0.12, 0.95)
        radius: 12

        Column {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 8

            TextField {
                id: searchInput
                width: parent.width
                placeholderText: "Search apps..."
                focus: launcher.open   // auto-focus when launcher opens

                onTextChanged: appModel.filter = text
                Keys.onEscapePressed: launcher.open = false
            }

            // ... app grid
        }
    }

    // Close on click outside
    TapHandler {
        onTapped: {
            // Check if tap was outside the inner rectangle
            launcher.open = false
        }
    }
}
```

The `OnDemand` mode is less commonly used from QML but is available when you want keyboard focus to follow which sub-item the user interacts with, rather than claiming it for the entire surface. A use case would be an embedded terminal or a surface that coexists with a focused window in a hybrid setup.

Note that `Exclusive` keyboard focus on a layer surface will prevent the compositor's own keyboard shortcuts from firing on some compositors (Sway honors this; Hyprland by default does not steal compositor binds). Test your launcher with your specific compositor to verify behavior.

---

## 19.6 Handling Wayland Events — Outputs, Capabilities, and Hot Plug

Wayland compositors expose connected outputs (monitors) via the `wl_output` global, and Quickshell makes these available as `Quickshell.screens`, a reactive list of `QuickshellScreen` objects. When a monitor is connected or disconnected at runtime, the list updates and any `Variants` or `Repeater` bound to it will automatically create or destroy the corresponding surfaces.

Each `QuickshellScreen` carries `name` (the DRM connector name, e.g. `DP-1`, `HDMI-A-1`), `width`, `height`, `scale` (fractional scaling factor), and `refreshRate`. Use these to make per-monitor decisions: a secondary display might show a minimal bar without system tray, or a higher DPI screen might use a larger panel height. Quickshell does not expose a compositor-defined "primary" concept; use `index === 0` as a proxy for the primary screen when needed.

```qml
// Shell root: one bar per screen, adapted to screen capabilities
Variants {
    model: Quickshell.screens

    TopBar {
        required property QuickshellScreen modelData
        screen: modelData

        // Compact mode on small displays
        compactMode: modelData.width < 1920

        // Debug label in dev mode
        screenName: modelData.name
    }
}
```

Protocol capability detection is important for portability. Not every compositor supports every protocol. At startup, Quickshell logs which Wayland globals were advertised by the compositor. You can check availability programmatically:

```qml
// Check ToplevelManager availability before using it
Component.onCompleted: {
    if (!ToplevelManager.available) {
        console.warn("wlr-foreign-toplevel-management not supported by compositor")
        taskbar.visible = false
    }
    if (!WlSessionLock.available) {
        console.warn("ext-session-lock-v1 not supported — lockscreen will not work")
    }
}
```

For graceful degradation, the pattern is to gate UI components behind availability checks and show fallback content or hide the feature entirely. A taskbar on a compositor that does not support `wlr-foreign-toplevel-management` (Mutter/GNOME, KWin without extensions) will simply show no windows — better than crashing.

Output change events are also relevant for multi-GPU setups and compositor reloads. When a Sway or Hyprland config is reloaded, outputs may be briefly destroyed and recreated. Structure your shell root to tolerate the destruction and recreation of screens without losing state in long-lived singletons.

| Protocol | Quickshell Type | Compositor Support |
|---|---|---|
| `wlr-layer-shell-unstable-v1` | `WlrLayershell` | wlroots, Hyprland, Sway, niri, KWin (partial) |
| `wlr-foreign-toplevel-management-v1` | `ToplevelManager` | wlroots, Hyprland, Sway, niri |
| `wlr-screencopy-v1` | `ScreencopyView` | wlroots, Hyprland, Sway |
| `ext-session-lock-v1` | `WlSessionLock` | wlroots, Hyprland, Sway, niri, KWin |
| `wlr-input-inhibitor-v1` | (implicit via lock) | wlroots compositors |

---

## 19.7 XWayland Considerations

XWayland bridges X11 applications into a Wayland session by running a nested X server and translating X11 window management calls into Wayland surfaces. For most purposes this is transparent, but several `ToplevelManager` behaviors differ for XWayland clients.

The `Toplevel.appId` for native Wayland clients is the `app_id` string set by the client itself, which is typically the `.desktop` file name (e.g. `firefox`, `org.gnome.Nautilus`). For XWayland clients, `appId` is derived from the X11 `WM_CLASS` property, which may include the instance name, class name, or both depending on the compositor's normalization. The class portion is usually what you want for matching against `.desktop` entries.

```qml
// Icon resolution that handles both Wayland and XWayland app IDs
function resolveIcon(appId) {
    // Try the appId directly first
    var icon = IconProvider.iconForApp(appId)
    if (icon !== "") return icon

    // XWayland WM_CLASS is often title-cased; try lowercase
    icon = IconProvider.iconForApp(appId.toLowerCase())
    if (icon !== "") return icon

    // Some apps set WM_CLASS to "app.name" — try the last component
    var parts = appId.split(".")
    if (parts.length > 1) {
        icon = IconProvider.iconForApp(parts[parts.length - 1].toLowerCase())
        if (icon !== "") return icon
    }

    return "application-x-executable"  // fallback
}
```

The `Toplevel.xwayland` boolean property (where supported) lets you branch logic explicitly. XWayland windows may not support all `Toplevel` methods — for example, some compositors do not propagate `requestMaximize()` correctly for XWayland surfaces:

```qml
ContextMenu {
    MenuItem {
        text: "Maximize"
        enabled: !modelData.xwayland || compositor.xwaylandMaximizeSupported
        onTriggered: modelData.requestMaximize()
    }
}
```

XWayland window titles are also more prone to rapid changes — some applications update the title every few hundred milliseconds (file managers showing transfer progress, terminals showing command output in the title). Throttle your taskbar label updates to avoid unnecessary redraws:

```qml
// Debounced title binding
property string _rawTitle: modelData.title
property string displayTitle: _rawTitle

Timer {
    id: titleDebounce
    interval: 200
    onTriggered: displayTitle = _rawTitle
}

onRawTitleChanged: titleDebounce.restart()
```

A practical consideration: XWayland must be running for XWayland toplevels to appear in `ToplevelManager`. If your compositor launches XWayland lazily (on first X11 client connection), the toplevel list may initially be shorter than expected. This is normal and not a bug in Quickshell.

---

## 19.8 Compositor-Specific Extensions

Beyond the portable protocols above, each major compositor exposes additional IPC for features that have no Wayland protocol equivalent. Hyprland provides a Unix socket with a rich JSON API for workspaces, window rules, animations, and monitors. Niri exposes a similar event socket. Sway uses the i3 IPC protocol.

Quickshell does not wrap these directly — they are accessed via `Process`, `Socket`, or dedicated community Quickshell extensions. The general pattern for Hyprland is:

```qml
// Reading workspaces via Hyprland socket
import Quickshell.Io

Process {
    id: hyprctl
    command: ["hyprctl", "-j", "workspaces"]

    property var workspaces: []

    stdout: SplitParser {
        onRead: (line) => {
            try {
                hyprctl.workspaces = JSON.parse(line)
            } catch(e) {}
        }
    }

    Component.onCompleted: running = true
}
```

For event-driven updates (window focus changes, workspace switches), connect to Hyprland's event socket at `$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock`. Chapter 20 covers this in depth.

---

## Troubleshooting

**Layer surface not appearing:**
Run `wlr-randr` or `wayland-info | grep layer_shell` to confirm the compositor advertises `zwlr_layer_shell_v1`. On KWin, layer shell support requires the `Layer Shell Qt` plasmoid or a compositor plugin — it is not available by default. Quickshell will log "Protocol not available" on startup if the global is missing.

**ToplevelManager.toplevels always empty:**
The `wlr-foreign-toplevel-management-unstable-v1` protocol requires the client to be a layer shell surface. If your Quickshell instance is running as a regular window (not via `PanelWindow`), the compositor will not grant access. Verify that your shell root uses `ShellRoot` and that at least one `PanelWindow` is visible. GNOME (Mutter) does not support this protocol at all — use the GNOME extension ecosystem instead.

**ScreencopyView shows a black rectangle:**
This is usually a permission issue. The Wayland session compositor restricts screencopy to clients with the `zwlr_screencopy_manager_v1` global. Confirm with `wayland-info | grep screencopy`. On Hyprland, screencopy is available by default. On Sway, it is also standard. If the compositor supports it but the view is still black, check that `captureSource` is not null — bind it only after confirming `Quickshell.screens.count > 0`.

**WlSessionLock not engaging / immediately releasing:**
The `ext-session-lock-v1` protocol requires that a `WlSessionLockSurface` be committed for every active output before the lock is considered engaged. If you have two monitors but only instantiate one surface, the compositor may reject the lock. Use `Variants { model: Quickshell.screens }` (not a hardcoded count) to ensure full coverage. Also, the lock surface must not be destroyed while `locked: true` — ensure the containing component's `visible` state does not hide the surfaces.

**Keyboard focus not transferring to launcher:**
Set `WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive` before making the surface visible. Some compositors (Hyprland pre-0.38) had a race condition where focus was not granted if the surface became visible and requested focus in the same frame. Add a 1-frame `Timer` delay between `visible = true` and setting `keyboardFocus` as a workaround.

**XWayland appId not matching .desktop entries:**
Use `hyprctl clients -j` or `swaymsg -t get_tree` and inspect the `class` field of XWayland entries to see the exact string the compositor reports. Cross-reference with `/usr/share/applications/*.desktop` `StartupWMClass` fields, which are specifically provided for this matching purpose.

**High GPU usage with multiple ScreencopyViews:**
Set `liveUpdates: false` for all views that do not need continuous updates. For overview grids, capture snapshots when the overview opens (not continuously). Profile with `WAYLAND_DEBUG=1` to count frame callbacks — each active ScreencopyView generates one per compositor frame.

---

*See also: Chapter 17 (PanelWindow basics), Chapter 20 (Hyprland IPC), Chapter 21 (niri socket), Chapter 24 (PAM authentication for lockscreen), Chapter 53 (session startup ordering).*

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
