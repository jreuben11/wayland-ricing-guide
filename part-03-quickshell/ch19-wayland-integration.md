# Chapter 19 — Wayland Integration: Layer Shell, ToplevelManager, ScreenCopy

## Overview
The Quickshell.Wayland module exposes Wayland protocols directly to QML,
giving shell components access to window lists, screen capture, and session locking.

## Sections

### 19.1 WlrLayershell and WlrLayer
- Already covered in Ch17 from the PanelWindow perspective
- Direct API: `WlrLayershell.namespace`, `WlrLayershell.exclusiveZone`
- Setting the namespace string for compositor window rules
- Using `layerrule` in Hyprland to animate specific shell components

### 19.2 ToplevelManager — Window List Access
```qml
import Quickshell.Wayland

Repeater {
    model: ToplevelManager.toplevels
    delegate: WindowButton {
        required property Toplevel modelData
        text: modelData.title
        icon: modelData.appId
    }
}
```
- `ToplevelManager.toplevels`: reactive list of all open windows
- `Toplevel` properties: `title`, `appId`, `activated`, `maximized`, `minimized`
- `Toplevel.activate()`, `minimize()`, `close()`: control windows
- Use case: taskbar, window switcher, expose/overview

### 19.3 ScreencopyView — Screen Capture in QML
```qml
ScreencopyView {
    captureSource: screen  // or a specific Toplevel
    liveUpdates: true      // stream vs. one-shot
}
```
- Live screen mirroring widget
- One-shot capture for screenshots
- Use cases: screen preview in overview, magnifier, recording indicator
- Performance considerations: GPU texture path

### 19.4 WlSessionLock — Building a Lockscreen
```qml
WlSessionLock {
    id: sessionLock
    locked: true

    Variants {
        model: Quickshell.screens
        WlSessionLockSurface {
            screen: modelData
            // lockscreen UI goes here
        }
    }
}
```
- `WlSessionLock.locked`: engage the session lock protocol
- `WlSessionLockSurface`: one surface per screen (required)
- Input inhibition is automatic while locked
- Integration with PAM (Chapter 24)
- `ext-session-lock-v1` protocol under the hood

### 19.5 WlrKeyboardFocus
- Grabbing keyboard focus for a layer surface
- Use case: app launcher that needs keyboard input
- Releasing focus when dismissed

### 19.6 Handling Wayland Events
- Output added/removed: `Quickshell.screens` is reactive
- Compositor capability detection
- Graceful degradation when protocols aren't supported

### 19.7 XWayland Considerations
- `Toplevel.appId` for XWayland clients uses WM_CLASS
- Differences in window management API behavior
- Checking `Toplevel.xwayland` property
