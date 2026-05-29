# Chapter 24 — Lockscreens with PAM and Greetd

## Overview
Quickshell can implement both a session lockscreen (while logged in) using
WlSessionLock + PAM, and a login greeter using the Greetd service.

## Sections

### 24.1 The Two Locking Use Cases
- **Session lock**: user is logged in, screen locked, authenticate to return
  - Protocol: `ext-session-lock-v1` via `WlSessionLock`
  - Auth: PAM via `Quickshell.Services.Pam`
- **Login greeter**: pre-session, full login screen
  - Protocol: greetd socket via `Quickshell.Services.Greetd`

### 24.2 Session Lock with WlSessionLock
```qml
WlSessionLock {
    id: lock
    locked: lockState.shouldLock

    Variants {
        model: Quickshell.screens
        WlSessionLockSurface {
            required property var modelData
            screen: modelData
            LockscreenUI { anchors.fill: parent }
        }
    }
}
```
- `WlSessionLock.locked = true`: engages the lock
- Compositor will not render other surfaces until unlocked
- Must create a `WlSessionLockSurface` for EVERY connected screen
- `WlSessionLock.unlocked()` signal: emitted on successful auth

### 24.3 PAM Authentication
```qml
PamContext {
    id: pam
    configurationName: "system-local-login"  // or "hyprlock", "swaylock"

    onConversationRequest: conv => {
        if (conv.type === PamMessageType.Prompt) {
            conv.response = passwordField.text
            passwordField.clear()
        }
    }

    onAuthComplete: (success, message) => {
        if (success) lock.locked = false
        else showError(message)
    }
}

TextField {
    id: passwordField
    echoMode: TextInput.Password
    onAccepted: pam.authenticate()
}
```
- `PamContext.configurationName`: PAM service name from `/etc/pam.d/`
- `PamMessageType`: Prompt (password), Echo (username), Info, Error
- `PamErrorType`: for auth failure details
- Handling multi-factor auth conversation

### 24.4 Lockscreen UI Design
- Background: blurred screenshot or wallpaper
- Clock and date display
- Password input with visual feedback
- Failed attempts counter and timeout
- Power buttons (shutdown, reboot) via `Process`

### 24.5 Triggering the Lock
- `hypridle` integration: `loginctl lock-session`
- `swayidle` integration
- Manual lock keybinding: `Hyprland.dispatch("exec quickshell ipc call lockScreen")`
- `IpcHandler` for external lock commands

### 24.6 Greetd Integration
```qml
Greetd {
    id: greetd

    onRequestSecret: greetd.respond(passwordField.text)
    onAuthComplete: greetd.startSession(session.command)
    onError: showError(errorType, errorDescription)
}
```
- `GreetdState`: RequestSecret, AuthError, Success
- Starting a session: `greetd.startSession(["Hyprland"])`
- Session selection UI: listing entries from `/usr/share/wayland-sessions/`
- User selection: listing from `/etc/passwd`

### 24.7 Complete Lockscreen Example
Full annotated `lockscreen/` Quickshell config with:
- Blurred wallpaper background
- Digital clock
- PAM-authenticated password field
- Multi-screen support
- Idle activation via hypridle

### 24.8 Security Considerations
- Why Quickshell lockscreens are compositor-enforced
- Difference from X11 lockscreens (compositor-bypass attacks no longer possible)
- PAM configuration for security
- Race conditions: locked flag must be set before `visible: true`
