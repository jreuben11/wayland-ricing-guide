# Chapter 65 — The Wayland Security Model

## Overview

Security is Wayland's strongest architectural advantage over X11. While X11 was
designed in an era when network transparency and openness were the primary goals,
Wayland was built with modern threat models in mind — isolation-by-default,
compositor-mediated access, and per-resource permission gating.

This chapter explains the threat model Wayland addresses, what the protocol
actively prevents, where the remaining attack surface lies, and how to
construct a hardened Wayland setup for a security-conscious power user.
Understanding these mechanisms is essential before layering ricing customizations
on top — misconfiguring a compositor, portal, or session locker can silently
reopen vulnerabilities that Wayland is designed to close.

We cover the core isolation primitives, the role of XDG portals and Flatpak,
protocol-level access controls (screencopy, input inhibitor, session lock), and
practical hardening strategies including Bubblewrap namespaces and the emerging
`wp-security-context-v1` sandboxing protocol. See Ch 10 for Wayland protocol
fundamentals, Ch 20 for compositor architecture, and Ch 53 for session startup
where security-relevant environment variables are set.

---

## 65.1 The X11 Security Problem

On X11, every application shares a single global display server and can freely
interact with any other client's windows, input, and clipboard. The model was
acceptable in 1984, when all code on a workstation was trusted. Today, with
browsers running millions of lines of third-party JavaScript, package ecosystems
containing compromised dependencies, and complex sandboxed applications, this
design is indefensible.

Any X11 application — whether malicious or merely exploited — can:

- **Screenshot any other window** — `XGetImage()` on any window ID requires no
  privilege. A keylogger can silently photograph your password manager, banking
  portal, or SSH private key display without user interaction.
- **Keylog the entire session** — `XQueryKeymap()` polls the full keyboard state
  at any time. `XGrabKeyboard()` captures all input. `XSelectInput()` on the root
  window receives all KeyPress events.
- **Inject synthetic input events** — `XSendEvent()` sends fake keyboard or mouse
  events to any window. An attacker can type into your terminal or click "Confirm"
  in a privilege escalation dialog without touching the physical keyboard.
- **Enumerate all windows** — Any client can walk the complete window tree starting
  from the root, discovering every open application, its title, position, and class.
- **Read any clipboard contents** — XSelection is unguarded. Any app can request
  the PRIMARY, CLIPBOARD, or SECONDARY selection without restriction.
- **Intercept drag-and-drop** — XDnD transfers are visible to any client on the
  display.

The consequence is that on X11, process-level isolation (DAC, seccomp, namespaces)
does not protect you once an attacker has a foothold on the desktop session. The
display server is an ambient authority that erases userspace sandboxing boundaries.

### Practical Demonstration of X11 Keylogging

```bash
# This works on any X11 session — no privilege needed:
xinput list
# Find your keyboard device ID, then:
xinput test-xi2 --root <device-id>
# Every keystroke from every application appears here.

# Screenshot another window — replace 0x... with any window ID from xwininfo:
import -window 0x4200001 /tmp/stolen.png
```

This is not a theoretical attack. Tools like `xspy`, `xdotool`, and `xclip` are
widely used for legitimate purposes but have identical capabilities to malware.

---

## 65.2 Wayland's Isolation Model

The core Wayland security principle is **clients only see their own surfaces**.
This is not a configuration option or a policy — it is an architectural invariant
enforced by the protocol design.

The Wayland protocol passes object references through Unix domain sockets. A client
can only invoke methods on objects the compositor has explicitly given it. There is
no way to reference another client's `wl_surface` because you never received that
object handle. The compositor never broadcasts global window IDs analogous to X11
window handles — every client's surface namespace is private.

Key isolation guarantees:

- **No window enumeration**: Apps cannot list other apps' windows. There is no
  Wayland equivalent of `XQueryTree()`. The `xdg-foreign` protocol allows a client
  to export a specific handle that another client can import — but only if the
  exporting app chooses to do so.
- **No cross-app screencapture**: Capturing another application's pixels requires
  compositor cooperation via an explicit protocol (`zwlr-screencopy-v1` or
  `ext-image-capture-source-v1`). The compositor decides which clients may use these
  protocols.
- **No cross-app input injection**: The compositor routes input events exclusively
  to the surface that holds keyboard or pointer focus. No client can receive events
  destined for another, and there is no `XSendEvent()` equivalent in the core
  protocol.
- **No keylogging**: Keyboard events only reach the currently focused client. A
  background app cannot receive keystrokes that are typed into a different window.

**The compositor is the trust boundary.** Every shared resource — input, display,
clipboard, DRM output — is mediated by the compositor. A client's privileges are
exactly what the compositor grants it through the objects it receives at bind time
and through privileged protocols it chooses to advertise.

### What the Isolation Does Not Cover

Wayland isolation is a display-layer guarantee. It does not protect against:
- Filesystem attacks (reading `~/.ssh/` or `~/.gnupg/`)
- Network-level data exfiltration
- Shared memory exploits (though Wayland SHM pools are per-client)
- Side-channel attacks (CPU timing, shared L3 cache)
- Compromised compositor (the compositor itself is TCB)

For complete sandboxing, Wayland isolation must be combined with Flatpak, Bubblewrap,
or LSM policies. Wayland alone is a necessary but not sufficient condition for
application isolation.

---

## 65.3 Screenshot and Screen Capture Permissions

Wayland's screencapture story has multiple layers, and understanding each is critical
for both security analysis and for building tools like screen recorders and screenshot
utilities.

### Core Protocol Level

A client with only core Wayland protocols (`wl_compositor`, `xdg_shell`) can render
to its own surfaces and nothing else. There is no mechanism to read back another
surface's pixel data. This is the default for every sandboxed application.

### zwlr-screencopy-v1 (wlroots protocol)

`zwlr-screencopy-v1` is the wlroots-ecosystem protocol for screen capture. It allows
a client to copy frames from an output (monitor) or a specific `wl_surface` into a
shared memory buffer it provides.

```c
// Pseudo-code for what grim does internally:
zwlr_screencopy_frame_v1 *frame =
    zwlr_screencopy_manager_v1_capture_output(manager, 0, output);
zwlr_screencopy_frame_v1_add_listener(frame, &frame_listener, shm_buf);
// Compositor copies pixels into shm_buf at next frame
```

The security property: **any client that can bind `zwlr_screencopy_manager_v1`
gets full screen access**. wlroots-based compositors (Hyprland, Sway, river)
advertise this protocol to all local clients by default. There is no per-app
permission dialog.

This means `grim`, `slurp`, and screen recorders like `wf-recorder` work without
asking for permission — and so would a malicious native Wayland app. The protection
here is the portal layer for sandboxed apps.

```bash
# Capture the entire output to a file:
grim -o DP-1 ~/screenshot.png

# Capture a selected region:
grim -g "$(slurp)" ~/screenshot.png

# Record the screen:
wf-recorder -o DP-1 -f ~/screencast.mp4

# List available outputs:
wlr-randr
```

### ext-image-capture-source-v1 (standardized, 2024)

The newer `ext-image-capture-source-v1` + `ext-image-copy-capture-v1` protocols
are the standardization of screencopy, working toward a cross-compositor standard.
KDE Plasma, GNOME, and wlroots compositors are implementing these.

### XDG Desktop Portal (for sandboxed apps)

For Flatpak and other sandboxed applications, screen capture is gated through
`xdg-desktop-portal`. The portal presents a user-visible permission dialog before
granting access.

```bash
# Check which portal backend is active:
systemctl --user status xdg-desktop-portal
systemctl --user status xdg-desktop-portal-hyprland  # or -wlr, -kde, -gnome

# Inspect portal permissions:
flatpak permissions | grep -E "screenshot|screencast"

# Revoke screencast permission from a specific app:
flatpak permission-remove org.freedesktop.portal.ScreenCast com.discordapp.Discord
```

**Portal backends by compositor:**

| Compositor | Portal Backend | Package |
|---|---|---|
| Hyprland | xdg-desktop-portal-hyprland | `xdg-desktop-portal-hyprland` |
| Sway / wlroots | xdg-desktop-portal-wlr | `xdg-desktop-portal-wlr` |
| KDE Plasma | xdg-desktop-portal-kde | `plasma-desktop` |
| GNOME | xdg-desktop-portal-gnome | `xdg-desktop-portal-gnome` |

**What the portal prevents:** A malicious Flatpak cannot silently screencap your
password manager, banking portal, or GPG key operations. It must request the
`ScreenCast` portal, which triggers a user-visible dialog showing which application
is requesting access and allowing source selection.

### hyprland-toplevel-export-v1

Hyprland's `hyprland-toplevel-export-v1` is a per-window capture protocol:

- Captures a specific toplevel (individual window), not the full output
- Used by taskbar thumbnail previews (e.g., in `waybar` window switcher widgets)
- More granular than `zwlr-screencopy-v1`
- Still advertised to all local clients by default

```bash
# Check if Hyprland exposes the protocol:
wayland-info | grep toplevel-export
```

---

## 65.4 Input Isolation

Input security is one of Wayland's most significant improvements over X11. The
compositor has exclusive ownership of all input devices and makes deliberate routing
decisions for each event.

### Keyboard Event Routing

Keyboard events are delivered only to the surface holding keyboard focus. The
compositor tracks which surface has focus and sends `wl_keyboard.key` events only
to that client's seat. No other client receives those events — there is no broadcast
mechanism.

To receive keyboard events, an application must either:
1. Be the focused client (the user clicked on its window)
2. Hold a compositor-granted exclusive keyboard grab (session lockers only)
3. Use `hyprland-global-shortcuts-v1` to register a specific hotkey

```bash
# Verify your compositor's input protocol support:
wayland-info | grep -E "keyboard|input|shortcuts"

# Test keyboard routing with wev:
wev   # prints all events received by its own window — nothing from other windows
```

### Global Shortcuts (the right way)

The `hyprland-global-shortcuts-v1` protocol (and the cross-compositor
`ext-global-shortcuts-v1` being standardized) provides the correct mechanism for
global hotkeys without requiring a full keyboard grab:

```ini
# Hyprland config: register a hotkey via the compositor
bind = SUPER, Space, exec, rofi -show drun
```

The compositor receives the keybind, routes it to the registered handler, and the
application never needs ambient keyboard access. This is architecturally safe —
the compositor enforces which apps receive which shortcuts.

### Input Inhibitor Protocol

`zwp-input-inhibit-manager-v1` allows a client to prevent all input from reaching
other clients. This is used by:

- Session lockers (prevent input reaching desktop apps while locked)
- On-screen keyboards that need to capture all key events
- Screen sharing annotation tools

Only the compositor can honor this request; it will refuse if another client already
holds the inhibitor. This prevents two lockers competing or a malicious app grabbing
input indefinitely.

### What Wayland Input Isolation Prevents

Password managers, keyloggers, and screen scrapers that worked trivially on X11
cannot function on Wayland:

```bash
# These X11 attacks do NOT work on native Wayland windows:
# xdotool type "password"    ← no XSendEvent equivalent
# xdotool key Return          ← cannot inject into another app
# xinput test <device>        ← events not broadcast to all clients
```

The one exception: if you have XWayland running and are typing into an X11
application, other X11 apps within XWayland can still keylog each other. See §65.5.

---

## 65.5 The XWayland Security Perimeter

XWayland is a compatibility shim that runs an X11 server as a Wayland client,
translating between the two protocols. It is essential for running legacy X11
applications but reintroduces a significant portion of X11's security model within
its isolation boundary.

### What XWayland Reintroduces

Within the XWayland X11 server:
- X11 apps inside XWayland **can spy on each other** — `XGetImage()`, `xinput`,
  `xdotool` all work between X11 apps in the same XWayland instance
- X11 window enumeration is possible among X11 apps
- X11 clipboard is unguarded between X11 apps

### What XWayland Isolates

- X11 apps **cannot spy on native Wayland apps** — they are in separate protocol
  universes
- XWayland is an isolated X11 server — it has no access to the Wayland compositor's
  internal state, other Wayland clients, or Wayland surfaces
- The XWayland server itself runs as a Wayland client with only the access the
  compositor grants it

### Practical Implications

```bash
# Check which apps are running under XWayland:
xlsclients -display :0   # or whatever $DISPLAY XWayland uses

# Force Firefox to native Wayland (eliminates XWayland exposure):
MOZ_ENABLE_WAYLAND=1 firefox

# Force Electron apps to native Wayland:
electron --enable-features=UseOzonePlatform --ozone-platform=wayland

# Check if an app is running as Wayland or X11:
xprop -id $(xdotool getactivewindow) 2>/dev/null && echo "X11" || echo "Native Wayland"
```

Run security-sensitive applications — password managers, banking portals, SSH key
operations, secret decryption — as native Wayland apps. If a native Wayland version
is not available, consider running the app in a separate, isolated XWayland instance
(Xephyr or a dedicated XWayland process).

### Disabling XWayland

If you have no X11 applications, disabling XWayland entirely eliminates the attack
surface:

```ini
# Hyprland: disable XWayland entirely
xwayland {
    enabled = false
}
```

```bash
# Sway: launch without XWayland support
sway --no-xwayland

# Verify no XWayland is running:
ps aux | grep -i xwayland
```

Note: many screen sharing tools (OBS, some video conferencing) still require
XWayland. Test your workflow before permanently disabling it.

---

## 65.6 Session Locking: ext-session-lock-v1

Session locking is a critical security mechanism. On X11, screen lockers had a
notorious weakness: if the locker process crashed, the session was unlocked, exposing
the desktop. The `ext-session-lock-v1` Wayland protocol closes this race condition
by design.

### Protocol Security Properties

When a client invokes `ext_session_lock_manager_v1.lock()`:

1. The compositor immediately ceases all rendering to outputs (the screen goes
   dark/shows the locker surface) before returning success
2. All keyboard and pointer input is inhibited — no events reach desktop apps
3. Even if the locker client crashes, the compositor **maintains the locked state**
4. Only the locker client (or its successor process) can unlock by sending
   `ext_session_lock_v1.unlock_and_destroy()`
5. A new locker can connect and re-take ownership of the locked session

This is fundamentally different from X11 lockers, which relied on grabbing keyboard
and mouse (a race condition) and had no crash-safe semantics.

### Setting Up a Session Locker

```bash
# Install swaylock-effects (enhanced swaylock with blur/effects):
# Arch:
paru -S swaylock-effects

# Install hyprlock (Hyprland-native locker):
paru -S hyprlock

# Configure hyprlock (~/.config/hypr/hyprlock.conf):
cat > ~/.config/hypr/hyprlock.conf << 'EOF'
background {
    monitor =
    path = screenshot
    blur_passes = 3
    blur_size = 8
    brightness = 0.5
}

input-field {
    monitor =
    size = 350, 50
    outline_thickness = 3
    dots_size = 0.2
    outer_color = rgb(151515)
    inner_color = rgb(200, 200, 200)
    font_color = rgb(10, 10, 10)
    fade_on_empty = true
    placeholder_text = <i>Password</i>
    hide_input = false
    check_color = rgb(204, 136, 34)
    fail_color = rgb(204, 34, 34)
    fail_text = <i>$FAIL <b>($ATTEMPTS)</b></i>
    position = 0, -200
    halign = center
    valign = center
}
EOF

# Auto-lock on idle with hypridle:
cat > ~/.config/hypr/hypridle.conf << 'EOF'
general {
    lock_cmd = pidof hyprlock || hyprlock
    before_sleep_cmd = loginctl lock-session
    after_sleep_cmd = hyprctl dispatch dpms on
}

listener {
    timeout = 300
    on-timeout = hyprlock
    on-resume = hyprctl dispatch dpms on
}

listener {
    timeout = 600
    on-timeout = hyprctl dispatch dpms off
}
EOF

systemctl --user enable --now hypridle
```

### Lock on Suspend

```bash
# /etc/systemd/system/lock-on-suspend@.service
[Unit]
Description=Lock screen before suspend
Before=sleep.target
StopPropagatedFrom=sleep.target

[Service]
User=%i
Type=forking
Environment=DISPLAY=:0
Environment=WAYLAND_DISPLAY=wayland-1
ExecStart=/usr/bin/loginctl lock-session

[Install]
WantedBy=sleep.target
```

```bash
systemctl enable lock-on-suspend@$(whoami)
```

---

## 65.7 Compositor as Security Policy Enforcer

The compositor is the sole trust boundary in Wayland. Every security mechanism
ultimately flows through compositor enforcement. This section enumerates the
compositor's security responsibilities and how to audit them.

### Protocol Advertisement Policy

Compositors choose which protocols to advertise via `wl_registry`. Security-sensitive
protocols should only be advertised when appropriate:

| Protocol | Risk Level | Who Gets It |
|---|---|---|
| `zwlr-screencopy-v1` | High | All local clients (wlroots default) |
| `ext-image-capture-source-v1` | High | All local clients |
| `zwlr-layer-shell-v1` | Medium | All local clients |
| `hyprland-toplevel-export-v1` | Medium | All local clients |
| `ext-session-lock-v1` | High (but safe by design) | First requesting client |
| `zwp-input-inhibit-manager-v1` | High | First requesting client |
| `wp-security-context-v1` | Sandbox mechanism | Sandboxed clients only |

```bash
# Enumerate all protocols advertised by your compositor:
wayland-info | grep interface

# Check for screencopy specifically:
wayland-info | grep -E "screencopy|capture"
```

### Pointer Constraints

Games and applications that need pointer lock must request it via
`zwp-pointer-constraints-v1`. The compositor enforces that the pointer is only
locked when the constraining surface has focus:

```bash
# Test pointer constraint behavior:
# In Hyprland, a locked pointer is automatically released when you switch windows
# The app must re-request the lock when it regains focus
```

### Input Inhibitor Exclusivity

`zwp-input-inhibit-manager-v1` grants exclusive input ownership to one client at
a time. The compositor serializes these requests:

```bash
# Only one client can hold the inhibitor at once
# Verify your locker is actually using the protocol:
sudo strace -e trace=sendmsg -p $(pidof hyprlock) 2>&1 | grep inhibit
```

### Auditing Compositor Wayland Connections

```bash
# List active Wayland clients connected to your compositor (Hyprland):
hyprctl clients

# JSON output for scripting:
hyprctl -j clients | jq '.[].pid'

# Check which apps have active layer-shell surfaces:
hyprctl layers
```

---

## 65.8 Flatpak and Wayland Sandboxing

Flatpak combined with Wayland provides the strongest application isolation on Linux
outside of virtual machines. The two sandboxing layers complement each other:
Flatpak handles filesystem and process isolation; Wayland handles display-layer
isolation; the portal handles access to shared resources.

### Flatpak Sandbox + Wayland Integration

```bash
# Install an app via Flatpak:
flatpak install flathub com.brave.Browser

# Run with explicit sandbox overrides visible:
flatpak run --verbose com.brave.Browser 2>&1 | grep -E "allow|deny|portal"

# Inspect the manifest permissions:
flatpak info --show-permissions com.brave.Browser

# Override filesystem access (add read-only access to a directory):
flatpak override --user --filesystem=~/Documents:ro com.brave.Browser

# Block network access for a specific app:
flatpak override --user --unshare=network com.brave.Browser

# Check current overrides:
flatpak override --user --show com.brave.Browser
```

### Portal Permission Management

```bash
# List all portal permissions:
flatpak permissions

# List permissions for a specific app:
flatpak permission-list | grep -A5 discord

# Revoke specific permission types:
flatpak permission-remove org.freedesktop.portal.ScreenCast com.discordapp.Discord
flatpak permission-remove org.freedesktop.portal.Camera com.discordapp.Discord

# Reset all permissions for an app (user will be prompted again on next use):
flatpak permission-reset com.discordapp.Discord
```

### Portal Configuration File

The portal's behavior can be configured per-app via `~/.config/xdg-desktop-portal/`:

```ini
# ~/.config/xdg-desktop-portal/portals.conf
[preferred]
# Use hyprland portal for screen capture decisions:
org.freedesktop.portal.ScreenCast=hyprland
org.freedesktop.portal.Screenshot=hyprland
# Use GTK portal for file chooser:
org.freedesktop.portal.FileChooser=gtk
```

### Flatpak for Security-Sensitive Apps

| Threat | Mitigation |
|---|---|
| Keylogger in browser extension | Wayland input isolation (can't read other windows) |
| Malware in npm dependency | Flatpak filesystem sandbox |
| Screencap by background app | Portal ScreenCast permission dialog |
| Network exfiltration | `--unshare=network` override |
| File system access | `--filesystem=` override (default: none for Flatpak) |

---

## 65.9 Network Isolation with Bubblewrap and Namespaces

For maximum isolation beyond Flatpak — running untrusted binaries, one-off tools,
or security research — Linux namespaces via Bubblewrap provide fine-grained
sandboxing.

### Bubblewrap Basics

Bubblewrap (`bwrap`) is the low-level sandbox used internally by Flatpak. It creates
Linux namespace-isolated environments:

```bash
# Run a program with no network access, minimal filesystem:
bwrap \
  --unshare-net \
  --unshare-pid \
  --ro-bind /usr /usr \
  --ro-bind /lib /lib \
  --ro-bind /lib64 /lib64 \
  --ro-bind /etc /etc \
  --proc /proc \
  --dev /dev \
  --tmpfs /tmp \
  --bind "$WAYLAND_DISPLAY_PATH" "$WAYLAND_DISPLAY_PATH" \
  --setenv WAYLAND_DISPLAY "$WAYLAND_DISPLAY" \
  --setenv XDG_RUNTIME_DIR "$XDG_RUNTIME_DIR" \
  -- firefox --no-remote

# Simpler: run with no network, bind only home:
bwrap --unshare-net --bind / / --proc /proc --dev /dev \
  -- /usr/bin/some-untrusted-tool
```

### Binding the Wayland Socket

To give a sandboxed process access to the Wayland compositor, bind the socket:

```bash
export WAYLAND_SOCKET="$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY"

bwrap \
  --unshare-all \
  --share-net \
  --ro-bind /usr /usr \
  --tmpfs /tmp \
  --proc /proc \
  --dev /dev \
  --bind "$WAYLAND_SOCKET" "$WAYLAND_SOCKET" \
  --setenv WAYLAND_DISPLAY "$WAYLAND_DISPLAY" \
  --setenv XDG_RUNTIME_DIR /run/user/$(id -u) \
  -- mpv video.mkv
```

### wp-security-context-v1 (2024+)

The `wp-security-context-v1` protocol (merged into wayland-protocols 1.32) allows
a sandboxed client to announce its security context to the compositor. The compositor
can then apply policy decisions — refusing to advertise certain protocols (like
`zwlr-screencopy-v1`) to sandboxed clients.

```bash
# Check if your compositor supports it:
wayland-info | grep security-context

# In the future, Flatpak will pass its app ID as security context,
# allowing compositors to make per-app protocol decisions without portals.
```

This is the long-term solution for per-app screencopy permissions, eliminating
the need for the all-or-nothing current model. Compositor support is still being
rolled out as of 2025.

---

## 65.10 Hardening Checklist and Configuration

The following table summarizes the complete hardening posture for a security-conscious
Wayland desktop:

| Check | Action | Why |
|---|---|---|
| Run browsers as native Wayland | `MOZ_ENABLE_WAYLAND=1 firefox` | Eliminates XWayland X11 spy surface |
| Use Flatpak for untrusted apps | `flatpak install flathub <app>` | Portal-mediated screen access |
| Enable session lock on sleep | `hypridle` + `loginctl lock-session` | `ext-session-lock-v1` compositor enforcement |
| Disable XWayland if not needed | `xwayland { enabled = false }` | Eliminate X11 attack surface entirely |
| Use `ext-session-lock-v1` lockers | `hyprlock`, `swaylock` | Cannot be bypassed unlike X11 lockers |
| Register global shortcuts via compositor config | Hyprland bind declarations | Avoids needing input grab |
| Audit Flatpak permissions | `flatpak permissions` | Revoke unneeded portal access |
| Run untrusted binaries in bwrap | `bwrap --unshare-net ...` | Full namespace isolation |
| Verify portal backend is running | `systemctl --user status xdg-desktop-portal-*` | Ensures Flatpak apps get permission dialogs |
| Check for XWayland apps | `xlsclients -display :0` | Identify remaining X11 exposure |

### Environment Variables for Native Wayland

```bash
# Add to ~/.config/environment.d/wayland.conf or session startup (see Ch 53):
MOZ_ENABLE_WAYLAND=1
QT_QPA_PLATFORM=wayland
GDK_BACKEND=wayland
ELECTRON_OZONE_PLATFORM_HINT=wayland
SDL_VIDEODRIVER=wayland
CLUTTER_BACKEND=wayland
```

### Verifying Apps are Running Native Wayland

```bash
# Check all running apps' display backend:
for pid in $(hyprctl -j clients | jq '.[].pid'); do
  exe=$(readlink /proc/$pid/exe 2>/dev/null)
  maps=$(grep -c wayland /proc/$pid/maps 2>/dev/null || echo 0)
  echo "$exe: wayland_maps=$maps"
done

# Simpler: check if an app appears in xlsclients (X11) or not (native Wayland):
xlsclients -display :0 2>/dev/null
```

---

## 65.11 Remaining Limitations and Known Attack Surfaces

Wayland significantly reduces the desktop attack surface but does not eliminate it.
Honest security analysis requires acknowledging what is still vulnerable.

### Protocol-Level Gaps

- **`zwlr-screencopy-v1` is all-or-nothing** for non-sandboxed apps. Any native
  Wayland app on a wlroots compositor can screen capture without asking. This will
  be addressed by `wp-security-context-v1` as adoption grows.
- **No per-window access control for non-Flatpak apps**: the portal only applies
  to sandboxed apps. System-installed apps (APT/pacman packages) have full
  screencopy access.
- **`zwlr-layer-shell-v1` trust**: apps with layer-shell access can place overlays
  that cover other windows, create fake login prompts (UI spoofing), or implement
  hidden keyloggers via fake input overlays. Compositors should restrict this to
  trusted apps.
- **Clipboard still unguarded at the compositor level**: any client can read
  clipboard data via `wl_data_device`. For sensitive data, use clipboard managers
  with timeout policies.

### XWayland Remains the Weak Link

If XWayland is running, X11 apps can spy on each other. Mixed environments where
some apps are X11 and some are Wayland provide the isolation for the Wayland side
but not for the X11 side. The attack surface is:

```
X11 App A (XWayland) → can spy on → X11 App B (XWayland)
X11 App A (XWayland) → cannot spy on → Wayland App C
```

### Clipboard Security

```bash
# Install cliphist for clipboard management with history:
paru -S cliphist

# Configure wl-clipboard with a timeout (clear after 30s):
# In Hyprland config:
exec-once = wl-paste --watch cliphist store

# Clear clipboard on lock:
exec = hyprlock && wl-copy --clear
```

### Compositor Trust (TCB)

The compositor is the trusted computing base. A compromised or malicious compositor
can access everything. Verify your compositor binary integrity:

```bash
# Check compositor binary has not been tampered with (Arch):
pacman -Qk hyprland | grep -v ' 0 missing'

# Or use sha256sum against a known-good hash from the package:
sha256sum $(which Hyprland)
```

### Future Work: wp-security-context-v1

When `wp-security-context-v1` is fully adopted:
- Compositors will be able to make per-app protocol decisions
- `zwlr-screencopy-v1` will be deniable to sandboxed apps without portals
- Flatpak app IDs will be passed as security contexts, enabling compositor-level
  app policies

Monitor adoption via `wayland-protocols` releases and compositor changelogs.

---

## Troubleshooting

### Portal Not Working (No Permission Dialog for Flatpak Apps)

```bash
# Check portal daemon is running:
systemctl --user status xdg-desktop-portal
systemctl --user status xdg-desktop-portal-hyprland  # or -wlr, -kde, -gnome

# Check for conflicts (multiple portal backends):
ls /usr/share/xdg-desktop-portal/portals/

# Restart portal services:
systemctl --user restart xdg-desktop-portal
systemctl --user restart xdg-desktop-portal-hyprland

# Check portal logs:
journalctl --user -u xdg-desktop-portal -n 50

# Check DBUS activation:
dbus-send --session --print-reply \
  --dest=org.freedesktop.portal.Desktop \
  /org/freedesktop/portal/desktop \
  org.freedesktop.DBus.Introspectable.Introspect
```

### Session Lock Not Engaging

```bash
# Verify locker uses ext-session-lock-v1 (not just XRandR lock):
wayland-info | grep session-lock

# Test manual lock:
hyprlock &   # should lock immediately

# Check hypridle is running and has correct socket:
systemctl --user status hypridle
journalctl --user -u hypridle -n 20

# Verify loginctl can trigger lock:
loginctl lock-session
```

### XWayland Apps Not Getting Keyboard Input

```bash
# Check DISPLAY env var is set (XWayland needs it):
echo $DISPLAY   # should be :0 or similar

# Verify XWayland is running:
ps aux | grep -i xwayland

# For Hyprland, check XWayland is enabled:
hyprctl info | grep xwayland

# Restart XWayland (Hyprland):
hyprctl dispatch killactive  # if stuck in XWayland app
```

### grim / Screencopy Not Working

```bash
# Check screencopy protocol is available:
wayland-info | grep screencopy

# Verify WAYLAND_DISPLAY is set:
echo $WAYLAND_DISPLAY   # should be wayland-1 or similar

# Test with explicit display:
WAYLAND_DISPLAY=wayland-1 grim /tmp/test.png

# Check compositor supports the protocol (Hyprland debug):
hyprctl version | grep -i screencopy
```

### Flatpak App Not Sandboxed Correctly

```bash
# Run inside the Flatpak sandbox interactively:
flatpak run --command=sh com.example.App

# Check what filesystem access it actually has:
ls /host /run/host  # these exist inside Flatpak sandbox

# Verify network isolation override took effect:
flatpak override --user --show com.example.App | grep network

# Check bwrap is being used (Flatpak uses bwrap internally):
pgrep bwrap
```

---

*See also: Ch 10 (Wayland Protocol Architecture), Ch 20 (Compositor Internals),
Ch 53 (Session Startup and Environment), Ch 70 (Flatpak Ricing), Ch 80 (Network
Namespaces for Desktop Apps)*

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
