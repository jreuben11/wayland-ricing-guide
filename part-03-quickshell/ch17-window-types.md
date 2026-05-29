# Chapter 17 — PanelWindow, FloatingWindow, and Window Management

## Overview

Quickshell's window system is built on a direct mapping to Wayland protocols. Where X11 gave every window the same basic shape — a rectangle managed by a single window manager — Wayland splits the concept of "window" into several distinct surface roles, each backed by a dedicated protocol extension. Getting comfortable with these roles and knowing which one to reach for is the single most important prerequisite for building any shell component.

This chapter covers the three window types you will use in almost every Quickshell project: `PanelWindow`, `FloatingWindow`, and popup surfaces. It also covers multi-monitor management, visibility control, Z-ordering, and a complete worked example combining multiple window types. By the end, you will be able to construct a full desktop shell: status bar, sidebar panel, notification popups, and an optional overlay lockscreen — each using the correct Wayland surface role.

Cross-references: For session startup and autoloading shell components, see Chapter 53. For theming and visual styling applied to these windows, see Chapter 22. For IPC between window components, see Chapter 31.

---

## 17.1 PanelWindow — The Ricing Workhorse

`PanelWindow` is the type you will use for bars, docks, sidebars, desktop widgets, notification popups, and any surface that needs to exist outside the normal window management flow. Under the hood it is backed by the `zwlr-layer-shell-v1` Wayland protocol, which allows a client to request placement on named "layers" above or below the compositor's normal window stack.

The layer-shell protocol gives your surface four degrees of freedom that a normal window does not have: the layer it occupies (background, bottom, top, overlay), which screen edges it anchors to, how much space it reserves so that maximised windows avoid it (the exclusive zone), and how it interacts with keyboard focus. These four axes fully describe the behavior of every status bar, every desktop clock, and every lockscreen you have ever used on a modern Wayland compositor.

The `anchors` property is a bitmask of `Edges` values. Setting `anchors.top: true; anchors.left: true; anchors.right: true` with a fixed `height` gives you a full-width top bar. Setting all four edges and no fixed dimensions stretches the surface to fill the entire output — useful for wallpaper engines or full-screen overlays. Partial anchoring (e.g., only `anchors.right: true`) centers the surface along the non-anchored axis, which is the basis for floating launchers and side panels.

The `exclusiveZone` property controls how much space the compositor reserves alongside your surface. A positive integer (in logical pixels) pushes maximised and tiled windows away from the anchored edge by that amount. Setting `exclusiveZone: -1` opts out of the protocol's layout mechanism entirely, placing the surface in "overlay" mode where it floats above everything without affecting window placement. Setting it to zero (the default) means the surface is visible but claims no reserved area.

> **Note:** `exclusiveZone` only takes effect when exactly **one or three** anchors are set. With two anchors (e.g., left + right) or all four anchors, the exclusive zone has no effect and the compositor ignores the reservation.

```qml
// Minimal full-width top bar
import Quickshell
import Quickshell.Wayland

PanelWindow {
    anchors {
        top:   true
        left:  true
        right: true
    }
    height: 36
    exclusiveZone: height   // reserve exactly the bar height
    WlrLayershell.layer: WlrLayer.Top
    color: "#1e1e2e"

    Text {
        anchors.centerIn: parent
        text: "Status Bar"
        color: "#cdd6f4"
    }
}
```

```qml
// Right-side dock, 60 px wide, vertically centered, no exclusive zone
PanelWindow {
    anchors {
        right:  true
    }
    width: 60
    height: 400
    exclusiveZone: 0
    WlrLayershell.layer: WlrLayer.Top
    color: "#181825"
}
```

### 17.1.1 Layer Property Values

The `layer` property determines where in the compositor's surface stack your panel sits. Compositors render layers in order: Background → Bottom → Normal windows → Top → Overlay. The table below summarises intended usage.

| Value | Numeric | Typical Use |
|---|---|---|
| `WlrLayer.Background` | 0 | Wallpaper engines, desktop icons |
| `WlrLayer.Bottom` | 1 | Desktop widgets below windows |
| `WlrLayer.Top` | 2 | Status bars, docks, widgets above windows |
| `WlrLayer.Overlay` | 3 | Lockscreens, on-screen keyboards, notifications |

Most shell components belong on `WlrLayer.Top`. The `WlrLayer.Overlay` layer is special: it is the only layer that stays visible when the session is locked, so lockscreen implementations must use it. Some compositors allow multiple surfaces on the same layer; their relative ordering is compositor-defined and can be influenced with the `namespace` property (see Section 17.8).

```qml
// Background layer — wallpaper with QML shader
PanelWindow {
    anchors { top: true; bottom: true; left: true; right: true }
    exclusiveZone: -1
    WlrLayershell.layer: WlrLayer.Background
    color: "transparent"

    ShaderEffect {
        anchors.fill: parent
        // ... shader uniforms
    }
}
```

### 17.1.2 Keyboard Focus Modes

| Value | Behavior |
|---|---|
| `WlrKeyboardFocus.None` | Surface receives no keyboard events (default for bars) |
| `WlrKeyboardFocus.OnDemand` | Compositor grants focus when the surface requests it |
| `WlrKeyboardFocus.Exclusive` | Surface grabs all keyboard input; all other clients lose focus |

`WlrKeyboardFocus.None` is the right choice for status bars, clocks, and any widget the user interacts with only via mouse. Use `WlrKeyboardFocus.OnDemand` for search launchers and input fields: when the user clicks the launcher, your QML calls `requestActivate()` and the compositor transfers focus. Use `WlrKeyboardFocus.Exclusive` only for lockscreens and on-screen keyboards where stealing all keyboard input is the explicit intent.

```qml
// Launcher with on-demand focus
PanelWindow {
    id: launcher
    anchors { bottom: true; left: true; right: true }
    height: visible ? 64 : 0
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.OnDemand

    onVisibleChanged: {
        if (visible) requestActivate()
    }

    TextField {
        id: searchInput
        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter }
        anchors.margins: 16
        placeholderText: "Search…"
        focus: parent.visible
        Keys.onEscapePressed: launcher.visible = false
    }
}
```

---

## 17.2 FloatingWindow — Standard XDG Toplevels

`FloatingWindow` creates a regular XDG toplevel surface — the same kind that every normal application window uses. The compositor manages placement, allows the user to move and resize it, and adds it to the taskbar or window switcher just like any other window. This is rarely what you want for shell components, but it is the right tool for companion panels, configuration UIs, and debug overlays that should behave like normal application windows.

Because `FloatingWindow` relies on `xdg-shell` rather than `zwlr-layer-shell-v1`, it inherits all the compositor window management rules: tiling, snapping, decorations (server-side or client-side), and alt-tab inclusion. If you are building a settings dialog that should appear in the taskbar and be tiled by a tiling compositor, use `FloatingWindow`. If you need precise positioning independent of the compositor's layout engine, use `PanelWindow` instead.

The main properties of `FloatingWindow` are `title`, `minimumSize`, `maximumSize`, and `visible`. You can set `minimumSize` and `maximumSize` to the same value to produce a fixed-size window that the user cannot resize. The `title` string appears in the compositor's window decorations and taskbar entries.

```qml
import Quickshell

FloatingWindow {
    id: settingsWindow
    title: "Shell Settings"
    minimumSize.width: 480
    minimumSize.height: 320
    maximumSize.width: 900
    maximumSize.height: 700
    visible: false    // shown on demand

    SettingsPanel {
        anchors.fill: parent
    }
}
```

```qml
// Fixed-size, always-on-top debug overlay (compositor permitting)
FloatingWindow {
    title: "Debug Overlay"
    minimumSize.width:  320
    minimumSize.height: 200
    maximumSize.width:  320
    maximumSize.height: 200

    Column {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 4
        Text { text: "FPS: " + Qt.application.arguments[0] }
        Text { text: "Heap: " + Math.round(performance.memory / 1024) + " KB" }
    }
}
```

Unlike `PanelWindow`, `FloatingWindow` respects the `QML_DISABLE_DISK_CACHE` environment variable and standard Qt platform window hints. You can pass `flags: Qt.WindowStaysOnTopHint` via the underlying `QQuickWindow` if your compositor supports the `zxdg-decoration-manager-v1` protocol extension for client-side decoration negotiation.

---

## 17.3 PopupWindow and Transient Surfaces

Popup surfaces are transient: they appear in response to a user action, anchor to a parent surface position, and dismiss automatically when the user clicks outside them or presses Escape. The canonical Quickshell type for this is the `PopupWindow` (sometimes surfaced via the `Popup` QML type in specific Quickshell builds; check the version you are targeting).

The design contract of a popup is: it belongs to a parent surface, it derives its position from a point on that parent, and the compositor dismisses it on focus loss. This maps to the `xdg-popup` role in `xdg-shell`. The primary use cases are volume control flyouts, calendar popups, context menus, and network manager applets.

Positioning a popup requires specifying an `anchor` rectangle on the parent surface and a `gravity` direction that tells the compositor which way to open the popup relative to that rectangle. If the popup would go off-screen in the chosen direction, the compositor is permitted to flip or slide it — this is the protocol's "constraint adjustment" mechanism and it means your popup will stay on-screen even on small monitors or near screen edges.

```qml
// Volume popup anchored to a bar icon
PanelWindow {
    id: topBar
    anchors { top: true; left: true; right: true }
    height: 36
    WlrLayershell.layer: WlrLayer.Top

    Row {
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        spacing: 8

        MouseArea {
            id: volumeArea
            width: 24; height: 24
            onClicked: volumePopup.visible = !volumePopup.visible

            Text { text: "🔊"; anchors.centerIn: parent }
        }
    }

    Popup {
        id: volumePopup
        parent: topBar
        x: volumeArea.mapToItem(topBar, 0, 0).x - width / 2
        y: topBar.height + 4
        width: 200
        height: 80
        visible: false
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        Rectangle {
            anchors.fill: parent
            color: "#1e1e2e"
            border.color: "#45475a"
            radius: 8

            Slider {
                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter }
                anchors.margins: 16
                from: 0; to: 100
                value: AudioManager.volume
                onValueChanged: AudioManager.setVolume(value)
            }
        }
    }
}
```

For context menus specifically, prefer using `Menu` and `MenuItem` from `QtQuick.Controls` with the `Popup.CloseOnPressOutside` close policy, as Quickshell delegates these to `xdg-popup` automatically on Wayland backends.

```qml
// Context menu popup
Menu {
    id: contextMenu

    MenuItem {
        text: "Open Settings"
        onTriggered: settingsWindow.visible = true
    }
    MenuItem {
        text: "Reload Shell"
        onTriggered: Quickshell.reload()
    }
    MenuSeparator {}
    MenuItem {
        text: "Quit"
        onTriggered: Qt.quit()
    }
}

MouseArea {
    anchors.fill: parent
    acceptedButtons: Qt.RightButton
    onClicked: (mouse) => contextMenu.popup(mouse.x, mouse.y)
}
```

---

## 17.4 Multi-Monitor Patterns with Variants

The `Variants` type is Quickshell's mechanism for instantiating one QML component per element of a model — and `Quickshell.screens` is the reactive model of all connected outputs. Combining them gives you a bar (or dock, or any surface) that automatically appears on every monitor, adjusts when you hot-plug or unplug a display, and receives the correct `ShellScreen` reference for positioning and DPI-aware sizing.

The pattern is always the same: wrap your window type in `Variants`, pass `model: Quickshell.screens`, declare `required property var modelData` inside the component, and assign `screen: modelData`. The `required` keyword is important — it causes Quickshell to pass the current screen as a property injection, giving you access to the screen's geometry and name.

Every `Variants` instantiation is reactive. When you plug in a second monitor, Quickshell adds an entry to `Quickshell.screens`, and `Variants` creates a new instance of your component for that screen. When you unplug, the instance is destroyed. No polling, no manual bookkeeping.

```qml
// Full top bar on every connected monitor
import Quickshell
import Quickshell.Wayland

Variants {
    model: Quickshell.screens

    PanelWindow {
        id: bar
        required property ShellScreen modelData

        screen: modelData
        anchors { top: true; left: true; right: true }
        height: 36
        exclusiveZone: height
        WlrLayershell.layer: WlrLayer.Top
        color: "#1e1e2e"

        Row {
            anchors.fill: parent
            anchors.margins: 6
            spacing: 8

            Text {
                text: modelData.name     // e.g. "DP-1", "HDMI-A-1"
                color: "#cdd6f4"
                font.pixelSize: 12
                verticalAlignment: Text.AlignVCenter
                height: parent.height
            }

            Text {
                text: Qt.formatDateTime(new Date(), "hh:mm")
                color: "#89b4fa"
                font.pixelSize: 13
                verticalAlignment: Text.AlignVCenter
                height: parent.height
            }
        }
    }
}
```

When you need different behavior on the primary monitor versus secondary monitors, compare `modelData.name` against your configured primary output name, or use a `property bool isPrimary: index === 0` guard. Note that Quickshell does not currently expose a compositor-defined "primary" concept — that is a compositor-specific extension outside the Wayland core protocol.

```qml
// Taskbar only on first monitor; clock on all
Variants {
    model: Quickshell.screens

    PanelWindow {
        required property ShellScreen modelData
        required property int index

        screen: modelData
        anchors { top: true; left: true; right: true }
        height: 36
        exclusiveZone: height
        WlrLayershell.layer: WlrLayer.Top

        Row {
            anchors.fill: parent
            anchors.margins: 4
            spacing: 8

            // Taskbar only on first screen
            Loader {
                active: index === 0
                sourceComponent: TaskbarComponent {}
            }

            Item { Layout.fillWidth: true }

            ClockWidget {}
        }
    }
}
```

---

## 17.5 Screen Management and ShellScreen Properties

`Quickshell.screens` is a `QML ListModel`-compatible object whose entries are `ShellScreen` instances. Each `ShellScreen` exposes the output's current configuration as read-only properties. The table below lists the most useful ones.

| Property | Type | Description |
|---|---|---|
| `name` | `string` | Connector name: "DP-1", "eDP-1", "HDMI-A-2" |
| `width` | `int` | Pixel width of the output in its current mode |
| `height` | `int` | Pixel height of the output in its current mode |
| `physicalSize` | `size` | Physical dimensions in millimetres |
| `refreshRate` | `real` | Refresh rate in Hz (e.g. 144.0) |
| `model` | `string` | Monitor model string from EDID |
| `manufacturer` | `string` | Monitor manufacturer from EDID |
| `serialNumber` | `string` | Monitor serial number from EDID |
| `scale` | `real` | Compositor output scale factor (1.0, 1.5, 2.0, …) |
| `transform` | `WlrOutputTransform` | Rotation/flip applied to the output |

You can use `physicalSize` and `width` to compute the actual DPI of an output and scale font sizes or icon sizes accordingly:

```qml
PanelWindow {
    required property ShellScreen modelData
    screen: modelData

    // Compute logical DPI — use for font scaling
    readonly property real dpi: modelData.width / (modelData.physicalSize.width / 25.4)

    // Scale bar height to physical size (target: 8mm tall)
    height: Math.round(8 * dpi / 25.4)
    exclusiveZone: height

    anchors { top: true; left: true; right: true }
    WlrLayershell.layer: WlrLayer.Top
}
```

To react to hot-plug events beyond the automatic `Variants` instantiation, you can connect to `Quickshell.screensChanged`:

```qml
Connections {
    target: Quickshell
    function onScreensChanged() {
        console.log("Screens updated. Count:", Quickshell.screens.length)
        for (let i = 0; i < Quickshell.screens.length; i++) {
            let s = Quickshell.screens[i]
            console.log(" ", s.name, s.width + "x" + s.height, "@", s.refreshRate, "Hz")
        }
    }
}
```

---

## 17.6 Controlling Window Visibility

Quickshell gives you several strategies for showing and hiding windows, each with different performance and lifecycle implications. Choosing the right strategy affects how much GPU memory is consumed when a surface is "hidden" and how quickly it can be shown again.

Setting `visible: false` on a `PanelWindow` unmaps the surface from the compositor — it disappears from the screen and stops receiving input events. The QML component and all its children remain alive in memory, so showing it again (`visible: true`) is instantaneous with no re-parsing cost. This is the right choice for surfaces you toggle frequently, like a launcher that appears and disappears on a keybind.

`LazyLoader` defers creating the component until `active` becomes `true`, and optionally destroys it when `active` becomes `false`. This is the right choice for surfaces you show rarely (a configuration panel you open once per session) — it saves the memory of instantiating all the child items when the window is not needed. The tradeoff is a small parsing cost on first open.

```qml
// Strategy 1: always instantiated, toggled with visible
PanelWindow {
    id: launcher
    visible: false
    anchors { bottom: true; left: true; right: true }
    height: 80
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.OnDemand

    SearchBar { anchors.fill: parent }
}

Shortcut {
    sequence: "Meta+Space"
    onActivated: launcher.visible = !launcher.visible
}
```

```qml
// Strategy 2: lazy creation — only built when first opened
LazyLoader {
    id: settingsLoader
    active: false

    sourceComponent: FloatingWindow {
        title: "Settings"
        visible: true
        width: 600
        height: 400
        onClosing: settingsLoader.active = false
        SettingsPanel { anchors.fill: parent }
    }
}

// Open settings
function openSettings() {
    settingsLoader.active = true
}
```

Animated visibility transitions should use `Behavior` on the `opacity` or `y` property rather than directly on `visible`, because `visible: false` cuts the surface immediately with no transition frame. A common pattern is to use a separate `shown` property that drives both opacity/transform and, after the hide animation completes, flips `visible`:

```qml
PanelWindow {
    id: sidebar
    property bool shown: false

    visible: shown || hideAnimation.running
    anchors { top: true; bottom: true; right: true }
    width: 280
    WlrLayershell.layer: WlrLayer.Top
    exclusiveZone: shown ? width : 0

    transform: Translate {
        x: sidebar.shown ? 0 : sidebar.width   // slides in from right
        Behavior on x {
            NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
        }
    }

    NumberAnimation {
        id: hideAnimation
        target: sidebar
        property: "opacity"
        to: 0; duration: 180
        running: false
        onFinished: sidebar.visible = false
    }

    opacity: shown ? 1.0 : 0.0
    Behavior on opacity {
        NumberAnimation { duration: 180; easing.type: Easing.InCubic }
    }
}
```

---

## 17.7 Worked Example — Top Bar + Slide-In Side Panel

This section builds a complete, functional two-component shell layout: a full-width status bar at the top that reserves screen space, and a side panel that slides in from the right when a button in the bar is clicked. Both components share a `shown` state variable and handle focus correctly.

The design goals are:
- The top bar is always visible and reserves 36 px at the top of the screen.
- The side panel slides in over normal windows (no exclusive zone while hidden, full width reserved while visible).
- Pressing Escape or clicking outside the side panel closes it.
- Both components instantiate once per monitor via `Variants`.

```qml
// shell/Main.qml
import Quickshell
import Quickshell.Wayland

Variants {
    model: Quickshell.screens

    Item {
        required property ShellScreen modelData

        // ---- Top Status Bar ----
        PanelWindow {
            id: topBar
            screen: modelData
            anchors { top: true; left: true; right: true }
            height: 36
            exclusiveZone: height
            WlrLayershell.layer: WlrLayer.Top
            color: "#1e1e2e"

            Row {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 8

                // Left: workspace indicators
                WorkspaceIndicator { height: parent.height }

                Item { width: 1; Layout.fillWidth: true }

                // Right: system tray items + panel toggle
                SystemTrayArea { height: parent.height }

                MouseArea {
                    width: 28; height: parent.height
                    onClicked: sidePanel.shown = !sidePanel.shown
                    Text {
                        anchors.centerIn: parent
                        text: sidePanel.shown ? "✕" : "☰"
                        color: "#cdd6f4"
                        font.pixelSize: 16
                    }
                }
            }
        }

        // ---- Slide-In Side Panel ----
        PanelWindow {
            id: sidePanel
            screen: modelData

            property bool shown: false

            anchors { top: true; bottom: true; right: true }
            width: 300
            exclusiveZone: shown ? width : 0
            WlrLayershell.layer: WlrLayer.Top
            WlrLayershell.keyboardFocus: shown ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None
            color: "#181825"

            visible: shown || slideAnim.running

            // Slide transform
            transform: Translate {
                x: sidePanel.shown ? 0 : sidePanel.width
                Behavior on x {
                    NumberAnimation {
                        id: slideAnim
                        duration: 220
                        easing.type: Easing.OutCubic
                    }
                }
            }

            // Close on Escape
            Keys.onEscapePressed: shown = false

            // Close on click-outside
            MouseArea {
                anchors.fill: parent
                propagateComposedEvents: true
                onClicked: (mouse) => {
                    if (mouse.x < 0) sidePanel.shown = false
                    else mouse.accepted = false
                }
            }

            Column {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 12

                Text {
                    text: "Control Panel"
                    color: "#cdd6f4"
                    font.pixelSize: 18
                    font.bold: true
                }

                BrightnessSlider {}
                VolumeSlider {}
                NetworkWidget {}
                BluetoothWidget {}
            }
        }
    }
}
```

Note that wrapping both windows in an `Item` per `Variants` entry allows them to share the `sidePanel` reference cleanly. Each monitor gets its own independent pair of bar + panel, so the side panel on monitor 2 does not affect the state on monitor 1.

---

## 17.8 Z-Ordering and Stacking

Within a single layer (e.g., `WlrLayer.Top`), the Wayland protocol does not define a standard mechanism for ordering surfaces relative to each other. The compositor is free to stack layer-shell surfaces in any order it chooses. Most compositors (Hyprland, Sway, niri) stack them in creation order, with later-created surfaces appearing above earlier ones.

The `WlrLayershell.namespace` property assigns a string identifier to a layer-shell surface. Some compositors use this string to apply per-namespace stacking rules. For example, Hyprland respects a `noanim` namespace suffix to disable compositor animations on that surface, and some builds let you configure z-priority per namespace in `hyprland.conf`.

```qml
PanelWindow {
    WlrLayershell.namespace: "quickshell-bar"
    WlrLayershell.layer: WlrLayer.Top
    // ...
}

PanelWindow {
    // Notification popup — should appear above the bar
    WlrLayershell.namespace: "quickshell-notification"
    WlrLayershell.layer: WlrLayer.Overlay   // Use Overlay to ensure it's above Top surfaces
    // ...
}
```

When you need a surface to reliably appear above another of the same layer, the safest approach is to place the "above" surface on a higher layer. If both must be on `WlrLayer.Top` (for example, a tooltip and a bar), create the tooltip surface last in the QML tree — compositors consistently stack it above the bar in practice.

For Hyprland-specific stacking, you can also use `hyprctl dispatch` to manipulate layer surfaces, though this is fragile and not recommended for production shells:

```bash
# List all layer surfaces with their namespaces
hyprctl layers

# Example output:
# Layer [0] (WlrLayer.Top) - "quickshell-bar" at 0,0 1920x36
# Layer [1] (WlrLayer.Top) - "quickshell-notification" at 1720,42 200x80
```

A better compositing strategy for notifications is to assign them `WlrLayer.Overlay` unconditionally — this guarantees they appear above bars, docks, and normal windows regardless of the compositor. Only `WlrLayer.Overlay` surfaces are shown on top of fullscreen applications.

---

## 17.9 Advanced PanelWindow Patterns

### Fractional Positioning and HiDPI

On HiDPI monitors with fractional scaling (e.g., 1.5x), logical pixel sizes may not map cleanly to physical pixels. Always use `Math.round()` when computing heights from physical measurements to avoid blurry sub-pixel rendering:

```qml
PanelWindow {
    required property ShellScreen modelData
    screen: modelData

    // 40 logical pixels, rounded to physical pixel boundary
    height: Math.round(40 / modelData.scale) * modelData.scale
    exclusiveZone: height
    anchors { top: true; left: true; right: true }
    WlrLayershell.layer: WlrLayer.Top
}
```

### Strut-Only Panels (Invisible Space Reservations)

Sometimes you want to reserve screen space without drawing anything visible — for example, to prevent maximised windows from covering a gap you fill with a transparent gradient. Set `color: "transparent"` and `exclusiveZone` to the desired reservation:

```qml
PanelWindow {
    anchors { bottom: true; left: true; right: true }
    height: 2    // hairline, nearly invisible
    exclusiveZone: 48   // but reserve 48 px
    WlrLayershell.layer: WlrLayer.Top
    color: "transparent"
}
```

### Input Passthrough

A surface with `inputRegion: null` (available in some Quickshell builds as `WlrLayershell.inputRegion`) receives no pointer or touch input, allowing clicks to pass through to windows beneath. This is useful for HUD overlays and screen annotations:

```qml
PanelWindow {
    anchors { top: true; bottom: true; left: true; right: true }
    exclusiveZone: -1
    WlrLayershell.layer: WlrLayer.Top
    color: "transparent"
    // Pointer events pass through to whatever is underneath
    WlrLayershell.inputRegion: Qt.rect(0, 0, 0, 0)  // empty input region

    // Overlay HUD text
    Text {
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        anchors.margins: 8
        text: fps + " fps"
        color: "#a6e3a1"
        font.pixelSize: 11
    }
}
```

---

## Troubleshooting

**Panel does not appear on screen**

Verify that your compositor supports `zwlr-layer-shell-v1`. Run:
```bash
wayland-info | grep layer_shell
# or
weston-info 2>/dev/null | grep layer
```
Compositors known to support it: Hyprland, Sway, river, labwc, wayfire, cage. GNOME Mutter (as of GNOME 46) has experimental support gated behind a gsettings key; KWin supports it from Plasma 5.27 onward.

**Bar height is correct but windows are not pushed away**

Check that `exclusiveZone` equals the bar's logical pixel height and that `anchors` has the edge matching the bar's position. A mismatch (anchoring top but forgetting `anchors.top: true`) causes the compositor to ignore the exclusive zone. Also verify you have exactly one or three anchors set — `exclusiveZone` has no effect with two or four anchors.

**Surface appears behind application windows**

You are likely on `WlrLayer.Bottom` instead of `WlrLayer.Top`. Check the `layer` property.

**Popup closes immediately after opening**

This is almost always a focus race: the popup requests focus, the compositor delivers it, but something else (e.g., a `MouseArea` with `acceptedButtons: Qt.AllButtons`) consumes the very click that opened the popup and triggers the close policy. Set `closePolicy: Popup.CloseOnEscape` only (removing `CloseOnPressOutside`) and add a manual dismiss `MouseArea` outside the popup bounds.

**`Variants` creates too many or too few windows on hot-plug**

Confirm you are passing `model: Quickshell.screens` (the live reactive list) and not a snapshot like `model: Quickshell.screens.slice(0)`. The `slice()` call creates a plain JavaScript array that is not reactive.

**Fractional-scale artifacts (blurry bar border)**

Set `QtQuick.Window.window.contentItem.layer.smooth: false` and ensure all pixel measurements are computed through `Math.round()` with the screen's `scale` factor as shown in Section 17.9.

**`WlrKeyboardFocus.Exclusive` locks out the entire session**

This is working as designed — exclusive focus grabs all keyboard input, including compositor keybinds. Always provide a programmatic escape path (a timeout, a `Keys.onEscapePressed` handler, or an IPC socket command) before using exclusive focus.

**Namespace not respected by compositor**

`WlrLayershell.namespace` is advisory. If your compositor ignores it, layer ordering must be achieved by using different `WlrLayer` values or by adjusting the compositor's own configuration. For Hyprland, check `hyprctl layers` to see registered namespaces.

---

*See also: Chapter 22 (Theming and Visual Styling), Chapter 31 (IPC Between Shell Components), Chapter 53 (Session Startup and Autoloading).*

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
