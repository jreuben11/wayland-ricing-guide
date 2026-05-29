# Chapter 17 — PanelWindow, FloatingWindow, and Window Management

## Overview
Quickshell's window types map directly to Wayland protocols. Understanding which
type to use and how to configure it is the foundation of any shell component.

## Sections

### 17.1 PanelWindow — The Ricing Workhorse
- Backed by `zwlr-layer-shell-v1`
- Properties: `anchors`, `margins`, `exclusiveZone`, `layer`, `keyboardFocus`
- `anchors`: `Edges.Top | Edges.Left | Edges.Right` for a top bar
- `exclusiveZone`: how much screen space to reserve (push windows away)
- `exclusiveZone: -1`: ignore layout (overlay mode)

#### Layer Property Values
- `WlrLayer.Background`: beneath all windows (wallpaper layer)
- `WlrLayer.Bottom`: below windows but above background
- `WlrLayer.Top`: above windows (bars, widgets)
- `WlrLayer.Overlay`: above everything (lockscreens, notifications)

#### Keyboard Focus Modes
- `WlrKeyboardFocus.None`: bar doesn't need keyboard
- `WlrKeyboardFocus.OnDemand`: focus only when user interacts
- `WlrKeyboardFocus.Exclusive`: grab all keyboard input (lockscreen)

### 17.2 FloatingWindow — Standard Windows
- Regular XDG toplevel surface
- Used for settings panels, dashboards that are separate windows
- Properties: `title`, `minimumSize`, `maximumSize`, `visible`

### 17.3 PopupWindow
- For transient popups: calendar, volume control, context menus
- Anchored to a parent surface position
- Auto-closes on focus loss

### 17.4 Multi-Monitor Patterns with Variants
```qml
// One bar per screen
Variants {
    model: Quickshell.screens
    PanelWindow {
        required property var modelData  // the screen
        screen: modelData
        anchors.top: true
        anchors.left: true
        anchors.right: true
        height: 36
    }
}
```

### 17.5 Screen Management
- `Quickshell.screens`: reactive list of connected outputs
- `QsScreen` properties: `name`, `width`, `height`, `model`, `refreshRate`
- Handling monitor hot-plug events
- Primary monitor detection

### 17.6 Controlling Window Visibility
- `visible: false` to hide
- `LazyLoader { active: condition; PanelWindow { ... } }` for conditional creation
- Animation with visibility transitions

### 17.7 Worked Example: Top Bar + Side Panel
- Top bar anchored full-width with exclusiveZone
- Side panel that slides in on demand
- Focus management between the two

### 17.8 Z-Ordering and Stacking
- Layer ordering within a layer
- `WlrLayershell.namespace` for compositor-specific ordering rules
