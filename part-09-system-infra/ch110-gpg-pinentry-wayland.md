# Chapter 110 — GPG, SSH Agents, and pinentry on Wayland

## Overview

Every riced desktop that uses GPG-signed git commits, pass (the password manager), SSH keys stored on a YubiKey, or age-encrypted secrets eventually hits the same wall: `gpg: signing failed: No secret key` or a pinentry dialog that opens in a terminal nobody sees, or a password prompt that silently fails. These failures have the same root cause — the GPG agent cannot find a working pinentry program in the Wayland session environment.

This chapter covers the full agent stack for a Wayland session: gpg-agent configuration and socket activation, choosing and configuring a Wayland-native pinentry, SSH agent options (gpg-agent's built-in SSH support vs. `ssh-agent` vs. `gnome-keyring`), troubleshooting agent visibility, and integrating everything cleanly with systemd user units. A working pinentry setup is a prerequisite for `pass`, `gopass`, `git commit -S`, `sops`, `age` key import, and any tool that delegates to GPG for secret handling.

**Cross-references:** Ch 53 — session startup and environment injection, where agent socket variables must be exported. Ch 93 — D-Bus essentials (the transport that some pinentry programs use). Ch 55 — dotfile management, where GPG-encrypted secrets often appear.

---

## 110.1 Why X11 pinentry Breaks on Wayland

On X11, `gpg-agent` defaults to `pinentry-x11` (or `pinentry-gtk-2`), which opens a dialog by connecting to the X display specified in `$DISPLAY`. On a pure Wayland session:

- `$DISPLAY` is not set (or points to XWayland's synthetic display, which may not be accessible from the agent's environment)
- Even with XWayland active, the pinentry window may appear on the wrong screen or be invisible
- `gpg-agent` is typically started by systemd before your compositor is running, so it inherits no display variables

The fix is to configure `gpg-agent` to use a pinentry program that speaks Wayland natively or falls back to the terminal.

---

## 110.2 Pinentry Programs: Comparison

| Program | Toolkit | Wayland | Notes |
|---|---|---|---|
| `pinentry-gnome3` | GTK3 via gcr | Yes (native Wayland via gcr-prompter) | Best choice for GNOME or any compositor with a working D-Bus session |
| `pinentry-qt` | Qt6 | Yes (with `QT_QPA_PLATFORM=wayland`) | Good for KDE/Qt environments |
| `pinentry-gtk-2` | GTK2 | No (X11 only) | Avoid on pure Wayland |
| `pinentry-x11` | X11 | No | Avoid |
| `pinentry-curses` | ncurses | Yes (terminal) | Fallback; works in any terminal |
| `pinentry-tty` | Raw TTY | Yes (terminal) | Even simpler fallback; no ncurses |
| `pinentry-bemenu` | bemenu (wlroots layer-shell) | Yes | AUR/community; good for minimalist setups |
| `pinentry-rofi` | rofi-wayland | Yes | AUR; matches rofi launcher aesthetic |
| `pinentry-wl` | custom Wayland | Yes | Minimal, no GTK/Qt dependency |

### Recommended Choice

For most setups: **`pinentry-gnome3`**. It uses the `gcr-system-prompter` D-Bus service, which means the pinentry dialog is managed by the GNOME Keyring / GCR stack and will appear correctly on screen without needing `$DISPLAY` or `$WAYLAND_DISPLAY` in the agent's environment. It works on any compositor, not just GNOME.

Second choice: **`pinentry-qt`** with `QT_QPA_PLATFORM=wayland` set in the agent's environment.

Terminal fallback: **`pinentry-curses`**, which opens in whichever terminal gpg was invoked from. This always works but requires a terminal to be focused.

---

## 110.3 Installing pinentry-gnome3

```bash
# Arch Linux
sudo pacman -S pinentry  # includes pinentry-gnome3 as /usr/bin/pinentry-gnome3

# Ubuntu 24.04+
sudo apt install pinentry-gnome3

# Fedora 40+
sudo dnf install pinentry-gnome3
```

Verify it is present:
```bash
which pinentry-gnome3
pinentry-gnome3 --version
```

---

## 110.4 Configuring gpg-agent

### `~/.gnupg/gpg-agent.conf`

```
# Use pinentry-gnome3 as the primary pinentry
pinentry-program /usr/bin/pinentry-gnome3

# Cache passphrase for 4 hours (in seconds)
default-cache-ttl 14400
max-cache-ttl 86400

# Enable SSH agent support (see §110.7)
enable-ssh-support

# For debugging: log to a file
# debug-level guru
# log-file /tmp/gpg-agent-debug.log
```

If `pinentry-gnome3` fails (no D-Bus session, no GNOME Keyring running), provide a fallback via a wrapper script:

```bash
#!/bin/bash
# ~/.local/bin/pinentry-wayland
# Try gnome3, fall back to curses
if [ -n "$WAYLAND_DISPLAY" ] || [ -n "$DISPLAY" ]; then
    exec /usr/bin/pinentry-gnome3 "$@"
else
    exec /usr/bin/pinentry-curses "$@"
fi
```

```
# ~/.gnupg/gpg-agent.conf
pinentry-program /home/username/.local/bin/pinentry-wayland
```

### Reloading gpg-agent

```bash
gpg-connect-agent reloadagent /bye
# or
gpgconf --kill gpg-agent
gpgconf --launch gpg-agent
```

---

## 110.5 Agent Environment Variables

`gpg-agent` needs `$WAYLAND_DISPLAY`, `$XDG_RUNTIME_DIR`, and (for `pinentry-qt`) `$QT_QPA_PLATFORM` to open a pinentry dialog. When the agent is started by systemd's user instance before the compositor, it does not inherit these.

### Method 1: systemd import-environment (recommended)

In your compositor startup (hyprland.conf exec-once, sway config exec, etc.):

```bash
# Export session variables into the systemd user manager
exec-once = systemctl --user import-environment WAYLAND_DISPLAY XDG_RUNTIME_DIR DISPLAY
exec-once = dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_RUNTIME_DIR DISPLAY
```

After this, all systemd user units (including gpg-agent, if managed by systemd) can see `$WAYLAND_DISPLAY`.

### Method 2: gpg-agent systemd user unit override

Create a drop-in that sets the variables explicitly:

```ini
# ~/.config/systemd/user/gpg-agent.service.d/wayland.conf
[Service]
Environment=WAYLAND_DISPLAY=wayland-1
Environment=XDG_RUNTIME_DIR=/run/user/1000
Environment=GCR_SYSTEM_PROMPTER=1
```

Adjust `wayland-1` and `1000` to your actual socket name and UID.

### Method 3: `~/.gnupg/gpg-agent.conf` extra-socket

Not directly useful for display variables, but `extra-socket` lets external processes connect to the agent:

```
extra-socket /run/user/1000/gnupg/S.gpg-agent.extra
```

This is needed for forwarding the agent over SSH (§110.8).

---

## 110.6 Socket Activation and Session Startup

Modern distributions manage `gpg-agent` via systemd socket activation:

```
~/.gnupg/S.gpg-agent           ← main socket (GPG operations)
~/.gnupg/S.gpg-agent.ssh       ← SSH socket (if enable-ssh-support)
~/.gnupg/S.gpg-agent.browser   ← browser extensions
~/.gnupg/S.gpg-agent.extra     ← extra socket for forwarding
```

Check agent status:
```bash
gpgconf --list-dirs agent-socket   # path to the main socket
gpg-connect-agent /bye             # test: should exit 0 silently
gpg-connect-agent 'getinfo version' /bye  # should print gpg-agent version
```

If the agent is not running:
```bash
gpgconf --launch gpg-agent
```

---

## 110.7 SSH Agent Support

`gpg-agent` can act as an SSH agent, storing SSH private keys in the GPG keystore. This is useful when your SSH key is on a hardware token (YubiKey, Nitrokey) alongside GPG keys.

### Enable in gpg-agent.conf

```
enable-ssh-support
```

### Export the SSH socket

Add to your shell profile (`~/.zshrc`, `~/.bashrc`, `~/.config/fish/config.fish`):

```bash
# bash/zsh
export SSH_AUTH_SOCK=$(gpgconf --list-dirs agent-ssh-socket)
```

```fish
# fish
set -gx SSH_AUTH_SOCK (gpgconf --list-dirs agent-ssh-socket)
```

Also export it for systemd user units:

```bash
# In compositor startup
exec-once = systemctl --user import-environment SSH_AUTH_SOCK
```

### Adding SSH keys to gpg-agent

```bash
# Add an authentication-capable GPG subkey as an SSH identity
# First, get the keygrip of the authentication subkey
gpg --with-keygrip -K your@email.com

# Add the keygrip to sshcontrol
echo "KEYGRIP_HERE" >> ~/.gnupg/sshcontrol

# Verify
ssh-add -l
```

For hardware tokens (YubiKey), the key is loaded automatically when the card is plugged in:
```bash
gpg --card-status   # reads the card and imports the stub
ssh-add -l          # should show the card's authentication key
```

---

## 110.8 Alternatives: gnome-keyring and ssh-agent

### gnome-keyring (GNOME sessions)

GNOME Keyring provides its own SSH and GPG agents. On GNOME Wayland it starts automatically. It conflicts with `gpg-agent` for SSH if both SSH sockets are exported — pick one:

```bash
# Disable gnome-keyring's SSH component
mkdir -p ~/.config/autostart
cp /etc/xdg/autostart/gnome-keyring-ssh.desktop ~/.config/autostart/
echo "X-GNOME-Autostart-enabled=false" >> ~/.config/autostart/gnome-keyring-ssh.desktop
```

### Standalone ssh-agent

For setups that only need SSH key management (no GPG):

```bash
# Start ssh-agent as a systemd user service
systemctl --user enable --now ssh-agent

# ~/.config/systemd/user/ssh-agent.service
[Unit]
Description=OpenSSH Agent
Documentation=man:ssh-agent(1)
After=default.target

[Service]
Type=simple
Environment=SSH_AUTH_SOCK=%t/ssh-agent.socket
ExecStart=/usr/bin/ssh-agent -D -a $SSH_AUTH_SOCK

[Install]
WantedBy=default.target
```

```bash
# In shell profile
export SSH_AUTH_SOCK="$XDG_RUNTIME_DIR/ssh-agent.socket"
```

### keychain

`keychain` is a POSIX shell script that manages ssh-agent and gpg-agent lifetime across login sessions, reusing existing agents rather than spawning new ones. Useful for TTY logins that start a Wayland session without a display manager:

```bash
# Install
sudo pacman -S keychain    # Arch
sudo apt install keychain  # Ubuntu

# In ~/.zprofile or ~/.bash_profile (login shell)
eval $(keychain --eval --quiet --gpg2 --agents gpg,ssh id_ed25519 YOUR_GPG_KEY_ID)
```

---

## 110.9 pass and gopass

`pass` (the standard Unix password manager) wraps GPG for encryption. With a working `pinentry-gnome3` and `gpg-agent`, it works transparently on Wayland:

```bash
# Initialize
pass init your@gpg.email

# Add a password (triggers pinentry dialog on first use)
pass insert social/twitter

# Get a password (copies to Wayland clipboard for 45 seconds)
pass -c social/twitter

# Edit
pass edit social/twitter
```

### pass-wayland Clipboard Integration

`pass` uses `xclip` by default, which requires X11. For native Wayland clipboard:

```bash
# Set wl-clipboard as the clipboard tool
export PASSWORD_STORE_CLIP_TIME=45
export PASSWORD_STORE_X_SELECTION=clipboard

# Or configure wl-copy directly via a wrapper
# In ~/.local/share/pass/extensions/wayland-copy.bash:
# ...
```

Better: use `wl-clipboard` as the `pass` clipboard tool by setting:

```bash
# ~/.zshrc
export PASSWORD_STORE_CLIP_TIME=45

# Then in your shell's clipboard override:
# pass already detects wl-copy when $WAYLAND_DISPLAY is set and xclip is absent
```

Remove `xclip` if you want `pass` to automatically fall through to `wl-copy`:
```bash
# Arch: xclip is not installed by default; ensure wl-clipboard is installed
sudo pacman -S wl-clipboard
```

### gopass

`gopass` is a modern multi-store drop-in for `pass` with team sharing support:

```bash
sudo pacman -S gopass
gopass setup   # interactive setup wizard
```

gopass uses `wl-copy` automatically when `$WAYLAND_DISPLAY` is set.

---

## 110.10 sops and age

`sops` (Secrets OPerationS) encrypts YAML/JSON/env files using GPG, age, or cloud KMS. On Wayland, sops operations that require GPG decryption trigger pinentry automatically through the configured gpg-agent:

```bash
# Encrypt a file with your GPG key
sops --encrypt --pgp YOUR_KEY_FINGERPRINT secrets.yaml > secrets.enc.yaml

# Decrypt (triggers pinentry if passphrase not cached)
sops --decrypt secrets.enc.yaml
```

`age` is a simpler alternative that does not use GPG at all — no pinentry needed. It uses a plain key file:

```bash
# Generate key
age-keygen -o ~/.config/age/key.txt

# Encrypt
age -r $(age-keygen -y ~/.config/age/key.txt) -o secrets.enc plaintext.txt

# Decrypt
age -d -i ~/.config/age/key.txt secrets.enc
```

For `age` keys derived from SSH keys (no separate key file):
```bash
age -r $(ssh-keygen -e -f ~/.ssh/id_ed25519.pub -m RFC4716 | age-ssh-to-age) -o out.enc in.txt
```

---

## 110.11 Troubleshooting

### "gpg: signing failed: No secret key"

```bash
# Check that the key is available
gpg --list-secret-keys

# Check gpg-agent is running
gpg-connect-agent /bye

# Test pinentry manually
echo "GETPIN" | pinentry-gnome3
```

### Pinentry appears but is invisible / behind windows

`pinentry-gnome3` uses `gcr-prompter` as a D-Bus-activated service that creates a dialog with `urgency=critical`. Some compositors may not bring it to front. Fix:

```bash
# Verify gcr-prompter is active
systemctl --user status gcr-prompter.service

# Start it if not running
systemctl --user start gcr-prompter
```

For compositors without `urgency` support, switch to `pinentry-qt`:

```bash
# ~/.gnupg/gpg-agent.conf
pinentry-program /usr/bin/pinentry-qt

# Ensure Qt uses Wayland
# Add to compositor env exports:
# QT_QPA_PLATFORM=wayland
```

### pinentry-gnome3 fails with "could not open connection to session bus"

D-Bus session bus is not running or gpg-agent cannot find it. Ensure `DBUS_SESSION_BUS_ADDRESS` is imported into systemd user environment:

```bash
exec-once = dbus-update-activation-environment --systemd DBUS_SESSION_BUS_ADDRESS
```

### SSH agent socket not found

```bash
# Check the socket path
gpgconf --list-dirs agent-ssh-socket

# Check SSH_AUTH_SOCK in your environment
echo $SSH_AUTH_SOCK

# Test
ssh-add -l
```

### Two agents fighting (gnome-keyring + gpg-agent)

```bash
# Find which agent owns SSH_AUTH_SOCK
ls -la $SSH_AUTH_SOCK

# Disable gnome-keyring SSH component (see §110.8)
```

---

## Summary

A working Wayland GPG/pinentry stack requires three aligned pieces: `gpg-agent` configured with `pinentry-gnome3` (or `pinentry-qt`), the agent's environment containing `WAYLAND_DISPLAY` and `DBUS_SESSION_BUS_ADDRESS` (injected via `systemctl --user import-environment` in compositor startup), and `SSH_AUTH_SOCK` exported to the shell and systemd user units if using gpg-agent for SSH. With these in place, `pass`, `gopass`, git signing, and SSH key operations all work transparently without terminal interaction.

**Further reading:**
- Ch 53 — session startup and environment variable injection
- Ch 93 — D-Bus session bus and activation
- Ch 55 — dotfile management and encrypted secrets
- Ch 32 — Wayland clipboard (relevant for `pass -c`)
