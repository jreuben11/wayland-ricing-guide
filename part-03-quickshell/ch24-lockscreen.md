# Chapter 24 — Lockscreens with PAM and Greetd

## Overview

Wayland's security model fundamentally changed how lockscreens work compared to X11. Under X11, a lockscreen was just another window, and any sufficiently privileged process could bypass it by killing the locker or drawing over it. Wayland's `ext-session-lock-v1` protocol eliminates this attack surface: the compositor freezes all other surfaces until the lock is explicitly released by the locking client itself. If the locking client crashes, the compositor keeps the screen locked rather than unlocking it.

Quickshell exposes this protocol through `WlSessionLock` and its companion `WlSessionLockSurface`, and provides PAM integration via `Quickshell.Services.Pam`. For the pre-login use case — where no session exists yet — Quickshell integrates with `greetd` through `Quickshell.Services.Greetd`. This chapter covers both paths in depth: building a hardened session lockscreen and building a full greetd login greeter.

Cross-references: See Ch 18 for Quickshell IPC fundamentals (used for external lock triggers), Ch 22 for idle daemon integration, and Ch 53 for session startup configuration with greetd as the display manager.

---

## 24.1 The Two Locking Use Cases

Wayland lock and login are architecturally distinct. Understanding which protocol handles which case prevents a common mistake: trying to use `WlSessionLock` before a session exists, or trying to use greetd inside an active session.

| Scenario | Protocol | Quickshell Type | Auth |
|---|---|---|---|
| User logged in, screen idle | `ext-session-lock-v1` | `WlSessionLock` + `WlSessionLockSurface` | PAM via `PamContext` |
| No session yet, login prompt | greetd socket | `Greetd` service | greetd backend (PAM, fprintd, etc.) |
| TTY-based login (fallback) | n/a | n/a | getty / login |

The **session lock** path (`WlSessionLock`) runs inside the user's compositor session. Hyprland, Sway, niri, and any other `ext-session-lock-v1`-capable compositor will honour it. The user must already be logged in. Idle daemons such as `hypridle` or `swayidle` are the typical trigger.

The **greetd path** runs before the user session. `greetd` is a minimal daemon that listens on a Unix socket (`/run/greetd.sock`) and accepts a JSON protocol for authenticating a user and launching a session. Quickshell can serve as a greetd "greeter" — a UI that communicates over that socket — replacing heavier greeters like `regreet` or `tuigreet`. This requires Quickshell to be launched by greetd as the greeter command, not from within a running session.

---

## 24.2 Session Lock with WlSessionLock

`WlSessionLock` is a Quickshell singleton that wraps the `ext-session-lock-v1` Wayland protocol extension. Setting its `locked` property to `true` initiates the lock; the compositor will stop presenting any other surface until the lock is released. Releasing requires calling `WlSessionLock.unlock()` or setting `locked` back to `false` from QML — the compositor will not release it on its own.

A critical requirement: you must create a `WlSessionLockSurface` for every connected screen before the compositor considers the lock complete. If any output is uncovered, the compositor may reject the lock or present a blank screen on that output rather than your UI. Use `Quickshell.screens` (a live model that updates on hotplug) as the `Variants` model to handle multi-monitor setups automatically.

```qml
// lockscreen/lock.qml
import Quickshell
import Quickshell.Wayland
import Quickshell.Services.Pam

ShellRoot {
    WlSessionLock {
        id: lock
        locked: lockState.shouldLock

        // Signal emitted after unlock() succeeds
        onUnlocked: lockState.shouldLock = false

        Variants {
            model: Quickshell.screens
            WlSessionLockSurface {
                required property var modelData
                screen: modelData

                // Each surface fills its output
                LockscreenUI {
                    anchors.fill: parent
                    isPrimary: modelData === Quickshell.screens[0]
                }
            }
        }
    }

    // Global lock state — shared across all surfaces
    QtObject {
        id: lockState
        property bool shouldLock: false
    }

    // IPC entry point for external triggers (hypridle, keybind)
    IpcHandler {
        target: "lockScreen"
        function lockScreen() {
            lockState.shouldLock = true
        }
    }
}
```

The `isPrimary` flag lets you show the password input only on the primary monitor while secondary monitors display a decorative surface (clock, wallpaper blur). This avoids confusing duplicate input fields across outputs.

`WlSessionLock.locked` is a read/write property, but it should only transition from `false` to `true` before the surfaces are shown, never after. The protocol requires the lock to be engaged before any surface renders; if you try to set `locked = true` after the UI is visible, some compositors will reject the request entirely.

---

## 24.3 PAM Authentication

PAM (Pluggable Authentication Modules) is the standard Linux authentication framework. Quickshell's `PamContext` object in `Quickshell.Services.Pam` drives a PAM conversation: it calls a named PAM service (one of the files in `/etc/pam.d/`), handles the exchange of prompts and responses, and emits `authComplete` with a success or failure result.

The PAM conversation model is asynchronous and message-driven. PAM may issue multiple prompts in sequence (e.g., username then password, or password then TOTP code for multi-factor setups). Each prompt arrives as a `PamConversationMessage` in the `onConversationRequest` signal. Your QML must respond to each message by calling `conv.respond(text)` or, for non-prompt message types (informational, error), simply acknowledge them.

```qml
// lockscreen/PamAuth.qml
import Quickshell.Services.Pam

PamContext {
    id: pam
    // Use an existing PAM service file. Common choices:
    //   "system-local-login"  — works on most distros
    //   "login"               — standard login service
    //   "hyprlock"            — if you have hyprlock's pam.d entry
    //   "swaylock"            — same
    configurationName: "system-local-login"

    onConversationRequest: function(conv) {
        switch (conv.type) {
            case PamMessageType.Prompt:
                // Silent prompt — password
                conv.respond(passwordField.text)
                passwordField.clear()
                break
            case PamMessageType.PromptEcho:
                // Echo prompt — username or TOTP
                conv.respond(usernameField.text)
                break
            case PamMessageType.Info:
                // Informational message — show to user
                infoLabel.text = conv.message
                break
            case PamMessageType.Error:
                // PAM error — show and abort
                errorLabel.text = conv.message
                break
        }
    }

    onAuthComplete: function(success, message) {
        if (success) {
            lock.unlock()
        } else {
            failedAttempts++
            errorLabel.text = message || "Authentication failed"
            // Optional: add a delay before re-enabling input
            retryTimer.start()
        }
    }
}
```

The `configurationName` maps directly to a file under `/etc/pam.d/`. If you use `"hyprlock"` but that file does not exist, PAM will fail immediately. The safest cross-distro choice is `"system-local-login"` or `"login"`. You can also ship your own `/etc/pam.d/quickshell-lock` file and reference it as `"quickshell-lock"`.

For a typical single-password setup, the conversation will issue exactly one `Prompt` message and then emit `authComplete`. For fingerprint readers using `fprintd-pam`, you may receive an `Info` message asking the user to swipe before `authComplete` fires — your UI should handle that gracefully by showing a "Swipe fingerprint" prompt.

```qml
// /etc/pam.d/quickshell-lock  (create this file as root)
// Minimal PAM config for lockscreen:
// auth      include   system-local-login
// account   include   system-local-login
// session   include   system-local-login

// Then set configurationName: "quickshell-lock"
```

---

## 24.4 Complete Lockscreen UI Design

A production lockscreen needs to combine visual polish with robustness. The key components are: a background layer (blurred wallpaper or solid colour), a clock/date display, the password input, error feedback, failed-attempt handling, and optional power buttons.

The background is typically a blurred screenshot captured at lock time, or the current wallpaper. Quickshell can read the wallpaper path from your Hyprland config or a shared state file; blurring is easiest via a `ShaderEffect` or by using Hyprland's built-in blur if you set `blur_new_optimizations = true` and `special_fallthrough = true` on the lock surface.

```qml
// lockscreen/LockscreenUI.qml
import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Services.Pam

Item {
    id: root
    property bool isPrimary: false

    // ── Background ──────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: "#0d0e10"

        Image {
            id: wallpaper
            anchors.fill: parent
            source: Qt.resolvedUrl("file:///home/" + Quickshell.env("USER") + "/.config/wallpaper.png")
            fillMode: Image.PreserveAspectCrop

            layer.enabled: true
            layer.effect: FastBlur {
                radius: 64
            }
        }

        // Darken overlay
        Rectangle {
            anchors.fill: parent
            color: "#88000000"
        }
    }

    // ── Clock ────────────────────────────────────────────────────────
    Column {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.verticalCenter: parent.verticalCenter
        anchors.verticalCenterOffset: isPrimary ? -120 : 0
        spacing: 8

        Text {
            id: clockLabel
            anchors.horizontalCenter: parent.horizontalCenter
            text: Qt.formatTime(new Date(), "hh:mm")
            font.pixelSize: 96
            font.weight: Font.Thin
            color: "#ffffff"

            Timer {
                interval: 1000
                running: true
                repeat: true
                onTriggered: clockLabel.text = Qt.formatTime(new Date(), "hh:mm")
            }
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: Qt.formatDate(new Date(), "dddd, MMMM d")
            font.pixelSize: 22
            color: "#aaffffff"
        }
    }

    // ── Auth panel (primary screen only) ────────────────────────────
    Column {
        visible: root.isPrimary
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 180
        spacing: 16

        property int failedAttempts: 0

        PamContext {
            id: pam
            configurationName: "system-local-login"

            onConversationRequest: function(conv) {
                if (conv.type === PamMessageType.Prompt) {
                    conv.respond(passwordField.text)
                    passwordField.clear()
                }
            }

            onAuthComplete: function(success, message) {
                if (success) {
                    lock.unlock()
                } else {
                    parent.failedAttempts++
                    errorLabel.text = parent.failedAttempts >= 3
                        ? "Too many failed attempts (" + parent.failedAttempts + ")"
                        : "Incorrect password"
                    shakeAnimation.start()
                    retryTimer.start()
                    passwordField.enabled = false
                }
            }
        }

        Timer {
            id: retryTimer
            interval: 2000
            onTriggered: {
                passwordField.enabled = true
                passwordField.forceActiveFocus()
                errorLabel.text = ""
            }
        }

        Text {
            id: userLabel
            anchors.horizontalCenter: parent.horizontalCenter
            text: Quickshell.env("USER")
            font.pixelSize: 18
            color: "#ccffffff"
        }

        Rectangle {
            id: passwordContainer
            width: 320
            height: 48
            radius: 24
            color: "#33ffffff"
            border.color: passwordField.activeFocus ? "#ffffff" : "#55ffffff"
            border.width: 2

            SequentialAnimation {
                id: shakeAnimation
                PropertyAnimation { target: passwordContainer; property: "x"; from: 0; to: -12; duration: 50 }
                PropertyAnimation { target: passwordContainer; property: "x"; from: -12; to: 12; duration: 50 }
                PropertyAnimation { target: passwordContainer; property: "x"; from: 12; to: -12; duration: 50 }
                PropertyAnimation { target: passwordContainer; property: "x"; from: -12; to: 0; duration: 50 }
            }

            TextField {
                id: passwordField
                anchors.fill: parent
                anchors.margins: 16
                echoMode: TextInput.Password
                placeholderText: "Password"
                color: "#ffffff"
                background: null
                font.pixelSize: 16

                Keys.onReturnPressed: pam.authenticate()
                Keys.onEnterPressed: pam.authenticate()

                Component.onCompleted: forceActiveFocus()
            }
        }

        Text {
            id: errorLabel
            anchors.horizontalCenter: parent.horizontalCenter
            text: ""
            color: "#ff6b6b"
            font.pixelSize: 14
        }

        // Power buttons
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 24

            Repeater {
                model: [
                    { icon: "⏻", cmd: "systemctl poweroff",  tip: "Power off" },
                    { icon: "↺", cmd: "systemctl reboot",    tip: "Reboot" },
                    { icon: "⏾", cmd: "systemctl suspend",   tip: "Suspend" }
                ]

                delegate: Rectangle {
                    width: 40; height: 40; radius: 20
                    color: hovered ? "#44ffffff" : "#22ffffff"
                    property bool hovered: false

                    Text {
                        anchors.centerIn: parent
                        text: modelData.icon
                        font.pixelSize: 18
                        color: "#ffffff"
                    }

                    ToolTip.visible: hovered
                    ToolTip.text: modelData.tip

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        onEntered: parent.hovered = true
                        onExited: parent.hovered = false
                        onClicked: Process.exec(modelData.cmd.split(" "))
                    }
                }
            }
        }
    }
}
```

---

## 24.5 Triggering the Lock

Triggering the lockscreen from outside Quickshell requires either `loginctl lock-session` (which the compositor translates to a `WlSessionLock` engage) or a direct IPC call into your Quickshell instance. The preferred production approach is `IpcHandler` because it does not depend on the compositor relaying the `lock-session` signal.

```qml
// In lock.qml ShellRoot
IpcHandler {
    target: "lockScreen"
    function lockScreen() {
        lockState.shouldLock = true
    }
    function unlockScreen() {
        // For testing only — do not expose in production
        lockState.shouldLock = false
    }
}
```

With this in place, any process can trigger the lock:

```bash
# From a keybind in hyprland.conf:
bind = SUPER, L, exec, quickshell ipc call lockScreen

# From hypridle:
# ~/.config/hypridle.conf
listener {
    timeout = 300        # 5 minutes idle
    on-timeout = quickshell ipc call lockScreen
    on-resume  = true    # nothing to do on resume; PAM handles unlock
}

# From swayidle:
swayidle -w \
    timeout 300 'quickshell ipc call lockScreen' \
    before-sleep 'quickshell ipc call lockScreen'

# From a systemd service (e.g., lid close):
# /etc/systemd/system/lock-on-lid@.service
# ExecStart=/usr/bin/quickshell ipc call lockScreen
```

For `loginctl lock-session` integration (e.g., when another program calls it), configure your compositor to forward it. In Hyprland this is automatic: `misc:allow_session_lock_restore = true` in `hyprland.conf` ensures the lock survives compositor restarts.

If you want the screen to lock before suspend, add a systemd sleep hook:

```ini
# ~/.config/systemd/user/lock-before-sleep.service
[Unit]
Description=Lock screen before sleep
Before=sleep.target

[Service]
Type=oneshot
ExecStart=/usr/bin/quickshell ipc call lockScreen

[Install]
WantedBy=sleep.target
```

```bash
systemctl --user enable lock-before-sleep.service
systemctl --user daemon-reload
```

---

## 24.6 Greetd Integration

`greetd` is a minimal display manager daemon. Unlike GDM or SDDM, it does not provide a UI — it merely manages the PAM conversation and session launch, exposing a JSON API over a Unix socket. This makes it ideal for custom Quickshell-based login greeters.

To use Quickshell as a greeter, install greetd and set Quickshell as the greeter command:

```toml
# /etc/greetd/config.toml
[terminal]
vt = 1

[default_session]
command = "quickshell -c /etc/greetd/greeter"
user = "greeter"
```

Create the greeter config directory and ensure the `greeter` system user exists:

```bash
sudo useradd -M -G video greeter
sudo mkdir -p /etc/greetd/greeter
sudo chown greeter:greeter /etc/greetd/greeter
```

The `Greetd` QML type handles the socket protocol automatically:

```qml
// /etc/greetd/greeter/shell.qml
import Quickshell
import Quickshell.Services.Greetd

ShellRoot {
    Greetd {
        id: greetd

        // Called when greetd needs a secret (password)
        onRequestSecret: function(prompt) {
            secretPromptLabel.text = prompt
            passwordField.forceActiveFocus()
        }

        // Called for non-secret prompts (username, MFA codes)
        onRequestResponse: function(prompt) {
            responsePromptLabel.text = prompt
            responseField.forceActiveFocus()
        }

        // Auth completed
        onAuthComplete: function() {
            // Launch the selected session
            greetd.startSession(sessionSelector.currentSession.exec)
        }

        // Error from greetd backend
        onError: function(errorType, errorDescription) {
            errorLabel.text = errorDescription
            // Reset for retry
            greetd.cancelLogin()
            usernameField.forceActiveFocus()
        }
    }

    // ... UI defined below
}
```

The greetd session lifecycle is:

1. Call `greetd.createSession(username)` to start a PAM session.
2. Respond to `onRequestSecret` / `onRequestResponse` signals with `greetd.respond(text)`.
3. On `onAuthComplete`, call `greetd.startSession(["Hyprland"])` or equivalent.
4. On error, call `greetd.cancelLogin()` and restart from step 1.

```qml
// Full greeter UI skeleton
Column {
    anchors.centerIn: parent
    spacing: 20

    TextField {
        id: usernameField
        placeholderText: "Username"
        onAccepted: greetd.createSession(text)
    }

    TextField {
        id: passwordField
        echoMode: TextInput.Password
        placeholderText: "Password"
        onAccepted: greetd.respond(text)
    }

    // Session picker — reads /usr/share/wayland-sessions/*.desktop
    ComboBox {
        id: sessionSelector
        model: ListModel {
            Component.onCompleted: {
                var sessions = Quickshell.execSync(
                    ["bash", "-c",
                     "grep -h '^Exec=' /usr/share/wayland-sessions/*.desktop | cut -d= -f2-"]
                ).split("\n").filter(Boolean)
                sessions.forEach(function(s) { append({exec: s, text: s}) })
            }
        }
        property var currentSession: model.get(currentIndex)
    }

    Text {
        id: errorLabel
        color: "#ff6b6b"
    }
}
```

For user enumeration (listing available system users), read `/etc/passwd` and filter by UID >= 1000:

```qml
// User list model
ListModel {
    id: userModel
    Component.onCompleted: {
        var lines = Quickshell.readFile("/etc/passwd").split("\n")
        lines.forEach(function(line) {
            var parts = line.split(":")
            if (parts.length >= 7 && parseInt(parts[2]) >= 1000) {
                append({ username: parts[0], shell: parts[6] })
            }
        })
    }
}
```

---

## 24.7 Security Considerations

The `ext-session-lock-v1` protocol provides compositor-enforced locking. The compositor is responsible for not rendering any other surface once a lock is engaged, and for keeping the screen black if the locking client crashes (rather than exposing the session). This is fundamentally different from X11 where `xdotool`, `xrandr`, or a Ctrl+Alt+F switch could bypass a locker.

**Race condition prevention.** The most critical security rule: set `WlSessionLock.locked = true` before any UI is rendered. If you flip `locked` after `visible: true`, there is a window between render and lock where the screen content is visible. Always structure your state machine so the lock is engaged first:

```qml
// Correct order — lock first, then show UI
WlSessionLock {
    locked: true   // Constant true, or bound to a state that starts true
    // UI renders only after locked is acknowledged by compositor
}

// Wrong — do NOT do this:
WlSessionLock {
    locked: showingUI   // showingUI might be set after the surface appears
}
```

**PAM service hardening.** The default `system-local-login` PAM service usually includes `pam_faildelay.so` which adds a 2-second delay after failure. Verify your `/etc/pam.d/system-local-login` includes it. For additional protection, add a failed-attempt lockout via `pam_tally2` or `pam_faillock`:

```
# /etc/pam.d/quickshell-lock
auth     required   pam_faillock.so preauth
auth     include    system-local-login
auth     required   pam_faillock.so authfail
account  include    system-local-login
```

**Compositor-specific notes.**

| Compositor | Lock support | Notes |
|---|---|---|
| Hyprland | Full (`ext-session-lock-v1`) | Set `misc:allow_session_lock_restore = true` |
| Sway | Full | `sway --unsupported-gpu` may break lock surface |
| niri | Full | Supported since niri 0.1 |
| KWin (KDE) | Partial | Uses its own lock protocol; `WlSessionLock` may not work |
| Mutter (GNOME) | No | Uses `org_gnome_shell` protocol; incompatible |

**Greetd security.** The greeter runs as a dedicated low-privilege `greeter` user, not root. Do not grant the greeter user unnecessary permissions. The greetd socket at `/run/greetd.sock` is owned by root and the `greeter` group; do not widen permissions. If you need GPU access for GPU-accelerated animations in the greeter, add the `greeter` user to the `video` group (as shown in 24.6) and nothing more.

---

## 24.8 Multi-Screen and Hotplug Handling

When `Quickshell.screens` changes (monitor connected or disconnected while locked), the `Variants` block automatically creates or destroys `WlSessionLockSurface` instances. However, you should verify that your compositor's implementation correctly handles the surface set changing while a lock is active.

A defensive approach is to track the screen count and re-engage the lock if any surface becomes uncovered:

```qml
WlSessionLock {
    id: lock
    locked: lockState.shouldLock

    Connections {
        target: Quickshell
        onScreensChanged: {
            if (lockState.shouldLock && lock.locked) {
                // Force re-evaluation of Variants model
                lockState.shouldLock = false
                lockState.shouldLock = true
            }
        }
    }

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

For projectors or temporary displays that appear only briefly, you may want a shorter timeout before re-locking to avoid a flash of unprotected content.

---

## 24.9 Idle Daemon Integration Reference

| Daemon | Config location | Lock trigger | Resume hook |
|---|---|---|---|
| `hypridle` | `~/.config/hypridle.conf` | `on-timeout` command | `on-resume` command |
| `swayidle` | CLI args or `~/.config/swayidle/config` | `timeout N 'cmd'` | `resume 'cmd'` |
| `systemd-logind` | `/etc/systemd/logind.conf` | `IdleAction=lock` | n/a |
| Manual keybind | Compositor config | `quickshell ipc call lockScreen` | PAM unlock |

Example complete `hypridle.conf`:

```ini
# ~/.config/hypridle.conf
general {
    lock_cmd = quickshell ipc call lockScreen
    before_sleep_cmd = quickshell ipc call lockScreen
    after_sleep_cmd = true
}

listener {
    timeout = 300
    on-timeout = quickshell ipc call lockScreen
}

listener {
    timeout = 600
    on-timeout = hyprctl dispatch dpms off
    on-resume   = hyprctl dispatch dpms on
}
```

Start hypridle at session launch:

```bash
# In hyprland.conf:
exec-once = hypridle
```

---

## Troubleshooting

**Lock surface not appearing on all monitors.**
Ensure `Quickshell.screens` is used as the `Variants` model and that the `screen:` property on each `WlSessionLockSurface` is set to the correct output object. Verify with `wlr-randr` or `hyprctl monitors` that all expected outputs are listed.

**PAM returns "Authentication service cannot retrieve authentication info".**
The PAM service file does not exist. Check `/etc/pam.d/` for the file named by `configurationName`. Fall back to `"login"` or `"system-local-login"`. Verify the PAM module files exist: `ls /lib/security/pam_unix.so`.

**Password field is not focused after lock engages.**
Call `passwordField.forceActiveFocus()` in `Component.onCompleted` of `LockscreenUI`, or in a connection to `WlSessionLock.onLocked`. The Wayland focus model means keyboard input requires explicit focus.

**Shake animation does not reset position.**
If `shakeAnimation` ends with the container at an offset, add a final `PropertyAnimation` that returns `x` to `0`. Always end shake animations at the natural position.

**Greetd: "error starting session" after successful auth.**
The session command does not exist or is not in the `greeter` user's PATH. Use absolute paths in `greetd.startSession(["/usr/bin/Hyprland"])`. Check `journalctl -u greetd` for the full error.

**Greetd: compositor fails to start (blank screen after login).**
Ensure the compositor has `WAYLAND_DISPLAY` and `XDG_RUNTIME_DIR` set. greetd sets these automatically, but verify with `systemctl status greetd` and look for env var lines.

**Lock screen bypassed by VT switch (Ctrl+Alt+Fn).**
VT switching is handled by the kernel, not Wayland. To prevent it, add `HandleVTSwitchKey=off` in `/etc/elogind/logind.conf` (if using elogind) or configure the compositor to consume VT switch keys. Alternatively, use PAM `pam_securetty` to ensure the VT has no login prompt while locked.

**`quickshell ipc call lockScreen` returns "no handler found".**
The `IpcHandler` target name is case-sensitive. Verify the target string matches exactly. Also ensure the Quickshell instance is running; `pgrep quickshell` should return a PID.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
