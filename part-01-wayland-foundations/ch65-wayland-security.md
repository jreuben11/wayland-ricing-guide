# Chapter 65 — The Wayland Security Model

## Overview
Security is Wayland's strongest architectural advantage over X11. This chapter
explains the threat model, what Wayland prevents, what it doesn't, and how to
build a secure Wayland setup.

## Sections

### 65.1 The X11 Security Problem
On X11, any application can:
- **Screenshot any other window** — `XGetImage()` on any window ID
- **Keylog the entire session** — `XQueryKeymap()` or grab input
- **Inject input events** — `XSendEvent()` to any window
- **Enumerate all windows** — walk the window tree
- **Read clipboard of any app** — XSelection without restrictions

This means: a malicious app (or a compromised dependency) can trivially steal
passwords, sessions, and private data. There is no isolation.

### 65.2 Wayland's Isolation Model
The core Wayland security principle: **clients only see their own surfaces**.

- No window enumeration: apps cannot list other apps' windows
- No cross-app screencapture without compositor permission
- No cross-app input injection: compositor controls all input routing
- No keylogging: keyboard events only reach the focused client

**The compositor is the trust boundary.** It mediates all access to shared resources.

### 65.3 Screenshot and Screen Capture Permissions
**Without protocol cooperation:**
- `wl_surface` → client's own pixels only
- Screencopy requires `zwlr-screencopy-v1` or `ext-image-capture-source-v1`
- Compositor decides which surfaces can be captured

**With screencopy:**
- Tools like `grim` can capture the entire screen (runs as a privileged user app)
- `xdg-desktop-portal` adds a permission gate for sandboxed apps
- Flatpak apps: must request `ScreenCast` portal permission; user sees a dialog

**What this prevents:** A malicious Flatpak cannot silently screencap your bank
password. It must request permission and you must approve it.

### 65.4 Input Isolation
- Keyboard events go only to the focused surface
- No `XGrabKeyboard()` equivalent for arbitrary key capture
- Exception: layer-shell surfaces can request `WlrKeyboardFocus.Exclusive`
  (lockscreens, global launchers — compositor-controlled, not app-controlled)
- `hyprland-global-shortcuts-v1`: the correct way to register global hotkeys,
  requires explicit compositor registration

**What this prevents:** Password managers, keyloggers, and screen scrapers
that worked trivially on X11 cannot function on Wayland.

### 65.5 The XWayland Security Perimeter
XWayland reintroduces X11's security model for X11 apps:
- X11 apps inside XWayland can spy on each other
- X11 apps cannot spy on native Wayland apps
- XWayland is an isolated X11 server — it cannot access Wayland compositor state

**Implication:** Run security-sensitive apps (password managers, banking) as
native Wayland apps, not XWayland. Use Firefox native Wayland (`MOZ_ENABLE_WAYLAND=1`).

### 65.6 Screencopy Protocol Design
`zwlr-screencopy-v1` is intentionally an all-or-nothing protocol:
- Any client that can call it gets full screen access
- There is no per-window permission (unlike the portal)
- wlroots compositors grant this to any local client
- Security comes from the portal layer for sandboxed apps

**Hyprland `hyprland-toplevel-export-v1`:**
- Per-window capture (not full screen)
- Used by taskbar thumbnail previews
- More granular than screencopy

### 65.7 Compositor as Security Policy Enforcer
The compositor enforces:
- Session locking: `ext-session-lock-v1` — compositor-enforced, cannot be bypassed
- Input inhibition during lock: no client receives input while locked
- Portal permission dialogs: shown by compositor-controlled surface
- Pointer constraints: game pointer lock requires explicit user permission
- Input inhibitor protocol: lockscreens can grab all input

### 65.8 Flatpak and Wayland Sandboxing
Flatpak + Wayland provides the strongest application isolation on Linux:
- Flatpak filesystem sandbox: app cannot read `~/.ssh`, `~/.gnupg`
- Wayland sandbox: app cannot see other windows or capture input
- Portal layer: mediates file access, screencapture, camera, microphone
- `flatpak permissions`: inspect what each app has been granted

```bash
# What can this app access?
flatpak permission-list | grep discord

# Revoke a permission
flatpak permission-remove org.freedesktop.portal.ScreenCast discord
```

### 65.9 Network Isolation with Bubblewrap
For maximum isolation beyond Flatpak:
```bash
# Run an app with no network access
bwrap --unshare-net --ro-bind /usr /usr --proc /proc --dev /dev \
      firefox
```
Bubblewrap is what Flatpak uses internally.

### 65.10 Wayland Security Checklist
| Check | Why |
|-------|-----|
| Run browsers as native Wayland | No XWayland exposure |
| Use Flatpak for untrusted apps | Portal-mediated screen access |
| Enable session lock on sleep | `ext-session-lock-v1` compositor enforcement |
| Disable XWayland if not needed | Eliminate X11 attack surface |
| Use `ext-session-lock-v1` lockers | Cannot be bypassed unlike X11 lockers |
| Register global shortcuts via Quickshell | Avoids needing input grab |

### 65.11 Remaining Limitations
- `zwlr-screencopy-v1` is still all-or-nothing for non-sandboxed apps
- No per-window access control for non-Flatpak apps
- XWayland remains a weak point if X11 apps are used
- Color management protocols don't yet cover all color security concerns
- `wp-security-context-v1` (new, 2024): sandboxed Wayland connections — future solution
