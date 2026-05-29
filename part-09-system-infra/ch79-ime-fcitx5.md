# Chapter 79 — Input Method Editors on Wayland: Fcitx5, IBus

## Overview

IMEs (Input Method Editors) allow typing in CJK (Chinese/Japanese/Korean), Arabic, Indic
scripts, and other languages requiring composition. Wayland's IME protocol support lagged
behind X11 for years; the situation improved significantly through 2023–2025 as compositors
adopted the `zwp-text-input-v3` and `zwp-input-method-v2` protocols. This chapter covers
everything you need to get a fully functional IME on a Wayland compositor such as Hyprland,
Sway, KDE Plasma (Wayland), and GNOME.

Before diving into configuration, understand that IME on Wayland is fundamentally different
from X11. Under X11, the XIM protocol was a universal glue layer and every toolkit could use
it. Under Wayland, each toolkit (GTK, Qt, SDL, GLFW) has its own integration path. The
`GTK_IM_MODULE`, `QT_IM_MODULE`, and `XMODIFIERS` environment variables remain relevant, but
their meaning changes: on Wayland native apps they are toolkit-specific, not X11 bridges.

The upside of Wayland's modular approach is that a well-integrated IME like Fcitx5 can use
the native Wayland protocol directly, bypassing the historical XIM quirks entirely. The
downside is that apps which have not yet adopted `text-input-v3` will need a fallback — and
a few apps still break regardless.

See Ch 12 for session startup fundamentals, Ch 53 for systemd user service management, and
Ch 41 for Hyprland environment variable configuration.

---

## 79.1 The Wayland IME Protocol Stack

Understanding the protocol stack prevents hours of debugging. The chain from keypress to
rendered glyph involves multiple layers and each can be a source of breakage.

```
User presses keys
    → Compositor receives key events (evdev → libinput → compositor)
    → text-input-v3 protocol: compositor notifies IME framework of focus/state
    → IME framework (Fcitx5 / IBus) processes keys
    → IME generates composed character(s) via preedit or commit
    → text-input-v3: IME commits text → compositor forwards to focused app
    → App renders the committed text
```

The two relevant Wayland protocol extensions are:

- **`zwp-text-input-v3`** (`text-input-unstable-v3.xml`): the "client side" — how an
  application tells the compositor it wants text input and receives committed text.
- **`zwp-input-method-v2`** (`input-method-unstable-v2.xml`): the "IME side" — how an
  input method framework (Fcitx5, IBus) connects to the compositor to receive raw key
  events and inject text.

The compositor acts as the broker. If a compositor does not implement `input-method-v2`, a
fallback path via XWayland (for legacy X11 apps) or the virtual keyboard protocol is used,
but native Wayland apps will not work without it.

**Compositor support matrix (2025):**

| Compositor     | `text-input-v3` | `input-method-v2` | Notes                              |
|----------------|-----------------|-------------------|------------------------------------|
| Sway 1.9+      | Yes             | Yes               | Full Fcitx5/IBus support           |
| Hyprland 0.40+ | Yes             | Yes               | Stable since 0.36                  |
| KDE Plasma 6   | Yes             | Yes               | Also has own KWin IME path         |
| GNOME 46+      | Yes             | Partial           | Uses `gtk-text-input` for GTK apps |
| Weston 13+     | Yes             | Yes               | Reference implementation           |
| river           | Yes             | Yes               | Via wlroots                        |

**GTK-specific note:** GNOME's Mutter implements a proprietary `gtk-text-input` protocol for
GTK apps, which can bypass `input-method-v2` entirely. Fcitx5 handles this transparently via
its GTK IM module. This is why `fcitx5-gtk` is a required dependency when targeting GNOME.

---

## 79.2 Fcitx5 — Recommended IME

Fcitx5 is the recommended IME for Wayland ricing in 2025. It has the most complete Wayland
protocol support, the best toolkit coverage, and the most active development. IBus is
discussed in section 79.7 for completeness but Fcitx5 is the default recommendation.

### Installation by Distribution

**Arch Linux / EndeavourOS / Manjaro:**
```bash
# Core packages (always needed)
sudo pacman -S fcitx5 fcitx5-configtool fcitx5-qt fcitx5-gtk

# Chinese input engines (choose based on script)
sudo pacman -S fcitx5-chinese-addons    # Pinyin, Wubi, Cangjie, Chewing (Traditional)

# Japanese
sudo pacman -S fcitx5-mozc              # Mozc engine (Google's open-source IME)
# or:
sudo pacman -S fcitx5-anthy             # Anthy engine (lighter alternative to Mozc)

# Korean
sudo pacman -S fcitx5-hangul

# Vietnamese
sudo pacman -S fcitx5-unikey            # AUR

# Arabic / Indic (via table-based input)
sudo pacman -S fcitx5-table-extra       # Additional table input methods

# Verify installed
pacman -Ql fcitx5 | grep '/usr/bin'
```

**Fedora / RHEL-based:**
```bash
sudo dnf install fcitx5 fcitx5-configtool fcitx5-qt5 fcitx5-qt6 \
                 fcitx5-gtk2 fcitx5-gtk3 fcitx5-gtk4 \
                 fcitx5-chinese-addons fcitx5-mozc fcitx5-hangul
```

**Debian / Ubuntu:**
```bash
sudo apt install fcitx5 fcitx5-config-qt fcitx5-frontend-qt5 \
                 fcitx5-frontend-gtk2 fcitx5-frontend-gtk3 fcitx5-frontend-gtk4 \
                 fcitx5-chinese-addons fcitx5-mozc fcitx5-hangul
```

**NixOS (declarative):**
```nix
# /etc/nixos/configuration.nix
i18n.inputMethod = {
    enable = true;
    type = "fcitx5";
    fcitx5.addons = with pkgs; [
        fcitx5-chinese-addons
        fcitx5-mozc
        fcitx5-hangul
        fcitx5-gtk
        fcitx5-nord           # theme
    ];
};

# Environment variables are set automatically by NixOS
# but you can override them in your home-manager config
```

**Home Manager (NixOS / nix-darwin):**
```nix
# home.nix
i18n.inputMethod = {
    enable = true;
    type = "fcitx5";
    fcitx5.addons = with pkgs; [ fcitx5-chinese-addons fcitx5-mozc ];
};
```

---

## 79.3 Environment Variables (Critical)

Getting environment variables right is the single most common source of IME failures on
Wayland. The variables must be set **before the compositor starts** and must be visible to all
applications launched from the session. Setting them only in `.bashrc` or `.zshrc` is
insufficient for graphical sessions — the compositor itself needs to see them at launch time.

The canonical place depends on your session startup method:

**System-wide `/etc/environment` (works for most setups):**
```bash
# /etc/environment
GTK_IM_MODULE=fcitx
QT_IM_MODULE=fcitx
XMODIFIERS=@im=fcitx
SDL_IM_MODULE=fcitx
INPUT_METHOD=fcitx
```

Note: `INPUT_METHOD` is read by some Java/Swing applications. `SDL_IM_MODULE` covers SDL2
games. `GLFW_IM_MODULE=ibus` is sometimes needed for apps using GLFW (set to `ibus` even
when using Fcitx5 — this is a known GLFW quirk).

**Hyprland `hyprland.conf`:**
```conf
# ~/.config/hypr/hyprland.conf
env = GTK_IM_MODULE,fcitx
env = QT_IM_MODULE,fcitx
env = XMODIFIERS,@im=fcitx
env = SDL_IM_MODULE,fcitx
env = INPUT_METHOD,fcitx
# For GLFW apps (e.g., Minecraft Java via GLFW):
env = GLFW_IM_MODULE,ibus
```

**Sway `config`:**
```bash
# ~/.config/sway/config
set $fcitx_env GTK_IM_MODULE=fcitx QT_IM_MODULE=fcitx XMODIFIERS=@im=fcitx

exec --no-startup-id env $fcitx_env fcitx5 -d --replace
# Or use environment variables via systemd user environment:
exec systemctl --user import-environment GTK_IM_MODULE QT_IM_MODULE XMODIFIERS
```

**systemd user environment (propagated to all user services):**
```bash
# ~/.config/environment.d/fcitx5.conf
# This file is sourced by systemd-environment-d-generator
GTK_IM_MODULE=fcitx
QT_IM_MODULE=fcitx
XMODIFIERS=@im=fcitx
SDL_IM_MODULE=fcitx
```

After creating this file, run:
```bash
systemctl --user daemon-reload
# Then re-login for changes to take effect, or:
systemctl --user import-environment GTK_IM_MODULE QT_IM_MODULE XMODIFIERS
```

**Variable reference table:**

| Variable         | Affects              | Value for Fcitx5 | Value for IBus |
|------------------|----------------------|------------------|----------------|
| `GTK_IM_MODULE`  | GTK2/3/4 apps        | `fcitx`          | `ibus`         |
| `QT_IM_MODULE`   | Qt5/6 apps           | `fcitx`          | `ibus`         |
| `XMODIFIERS`     | X11/XWayland apps    | `@im=fcitx`      | `@im=ibus`     |
| `SDL_IM_MODULE`  | SDL2 games           | `fcitx`          | `ibus`         |
| `INPUT_METHOD`   | Java/Swing apps      | `fcitx`          | `ibus`         |
| `GLFW_IM_MODULE` | GLFW apps (Minecraft)| `ibus` (quirk)   | `ibus`         |

---

## 79.4 Starting Fcitx5

Fcitx5 must be started as a daemon **after the Wayland compositor is ready** but before any
applications that need IME are launched. Starting too early (before the compositor's Wayland
socket is up) causes Fcitx5 to silently fail the protocol connection.

**Hyprland (recommended: exec-once):**
```conf
# ~/.config/hypr/hyprland.conf
exec-once = fcitx5 -d --replace
```

The `--replace` flag ensures a clean takeover if Fcitx5 was already running (useful when
reloading config). The `-d` flag daemonizes it.

**Systemd user service (recommended for cleaner process management):**
```bash
# Fcitx5 ships with a systemd user service unit.
# Enable and start it:
systemctl --user enable --now fcitx5

# Check its status:
systemctl --user status fcitx5

# View recent logs:
journalctl --user -u fcitx5 -n 50
```

If you use the systemd service, remove the `exec-once = fcitx5 -d` from your compositor
config to avoid double-starting it. The compositor's systemd user target ensures ordering.

**Sway with systemd integration:**
```bash
# ~/.config/sway/config
exec systemctl --user start fcitx5
# Or: exec fcitx5 -d --replace
```

**Diagnosing startup problems:**
```bash
# Run Fcitx5 in foreground with verbose logging:
fcitx5 --verbose '*:5'

# Check if the Wayland socket is detected:
echo $WAYLAND_DISPLAY    # Should be wayland-0 or wayland-1
ls /run/user/$(id -u)/    # Should contain wayland-0 (or similar)
```

**Verify Fcitx5 is connected to the compositor:**
```bash
fcitx5-diagnose   # The definitive diagnostic tool
# Look for: "Wayland Input Method" entries with green/OK status
```

---

## 79.5 Configuring Input Methods

Fcitx5's configuration lives in `~/.config/fcitx5/`. The primary configuration file is
`~/.config/fcitx5/config` and per-addon configs live in `~/.config/fcitx5/conf/`.

**Using the GUI configuration tool:**
```bash
fcitx5-configtool
# Navigate: Input Method tab → "+" to add input methods
# Global Options tab → set trigger key (default: Ctrl+Space)
```

**Manual configuration of `~/.config/fcitx5/config`:**
```ini
[Hotkey]
# Trigger: toggle between direct (Latin) and IME mode
TriggerKeys=Control+space
# Alternatively: Super+space, Shift_L (shift key alone), etc.

# In-group switch (cycle through enabled IMEs)
EnumerateGroupForwardKeys=Super+space
EnumerateGroupBackwardKeys=Super+Shift+space

[Behavior]
# First IME in the list is the default after login
DefaultInputMethod=pinyin

# Show a notification when switching IME
ShowInputMethodInformation=True
showInputMethodInformationWhenFocusIn=False

# Page size for the candidate list
PageSize=5
```

**Pinyin addon configuration (`~/.config/fcitx5/conf/pinyin.conf`):**
```ini
[General]
# Enable or disable fuzzy pinyin (e.g., z/zh substitution)
FuzzyPinyin=True

# Enable Cloud Pinyin for extended candidates (requires network)
CloudPinyinEnabled=False

# Candidate list orientation
CandidateList=Vertical

[Fuzzy]
# Individual fuzzy rules:
VG_VNG=True     # en/eng confusion
ZZH=True        # z/zh confusion
CZH=False       # c/ch confusion (disable if unwanted)
```

**Mozc (Japanese) addon configuration:**
```bash
# Open the Mozc configuration tool directly:
/usr/lib/mozc/mozc_tool --mode=config_dialog
# Or access through: fcitx5-configtool → Addons → Mozc → Configure
```

**Listing installed input methods via command line:**
```bash
# List all available input methods Fcitx5 found:
fcitx5-remote -l
# Example output:
# keyboard-us
# pinyin
# mozc
# hangul
```

**Switching input methods programmatically:**
```bash
# Switch to pinyin:
fcitx5-remote -s pinyin

# Switch to keyboard (direct input):
fcitx5-remote -s keyboard-us

# Toggle current IME on/off:
fcitx5-remote -t
```

This is useful for keybindings in Hyprland:
```conf
# hyprland.conf: bind Super+Shift+Space to cycle IME
bind = SUPER SHIFT, SPACE, exec, fcitx5-remote -t
```

---

## 79.6 Fcitx5 Theming

Fcitx5 uses its own theming system for the candidate window (the popup that shows
suggestions). Themes control colors, fonts, borders, and layout. The classic UI (classicui)
is the primary theme interface; a material-color theme provides modern aesthetics.

**Installing themes:**
```bash
# Arch:
sudo pacman -S fcitx5-material-color    # Material Design-inspired

# AUR themes:
paru -S fcitx5-catppuccin              # Catppuccin Mocha/Latte/etc.
paru -S fcitx5-nord                    # Nord color palette
paru -S fcitx5-dracula                 # Dracula theme

# Manual installation from GitHub:
git clone https://github.com/gaelicwinter/fcitx5-gruvbox ~/.local/share/fcitx5/themes/gruvbox
```

**Classic UI configuration (`~/.config/fcitx5/conf/classicui.conf`):**
```ini
# Theme name (must match directory in ~/.local/share/fcitx5/themes/ or system path)
Theme=catppuccin-mocha

# Font for candidate text
Font=JetBrainsMono Nerd Font 11

# Font for menu/tray UI
MenuFont=JetBrainsMono Nerd Font 11

# Tray font
TrayFont=JetBrainsMono Nerd Font Bold 10

# Position: Follow cursor (0), Manual (1)
Vertical Candidate List=False

# Whether to show preedit text inline vs. in candidate window
UseInputMethodLanguageToDisplayText=True
```

**Creating a custom minimal theme:**
```bash
mkdir -p ~/.local/share/fcitx5/themes/my-theme
cat > ~/.local/share/fcitx5/themes/my-theme/theme.conf << 'EOF'
[Metadata]
Name=My Custom Theme
Version=1
Author=You
Description=A minimal custom theme

[InputPanel]
# Colors: R,G,B,A (0-255)
NormalColor=30,30,46,230
HighlightColor=137,180,250,255
HighlightBackgroundColor=49,50,68,255
HighlightTextColor=205,214,244,255
EOF
```

**Verifying the theme is applied:**
```bash
# Restart Fcitx5 to pick up theme changes:
fcitx5 -r   # (reload) — sends SIGHUP to running instance
# or:
kill -HUP $(pidof fcitx5)
```

---

## 79.7 IBus (Alternative)

IBus is the older, more established IME framework and is the default for GNOME. On Wayland it
is usable but has more rough edges than Fcitx5. If you are on a GNOME Wayland session and
cannot switch away from IBus, the following configurations apply.

**Installation:**
```bash
# Arch:
sudo pacman -S ibus ibus-libpinyin ibus-mozc ibus-hangul ibus-anthy

# Fedora (IBus is default):
sudo dnf install ibus ibus-libpinyin ibus-mozc ibus-hangul

# Ubuntu/Debian:
sudo apt install ibus ibus-pinyin ibus-mozc ibus-hangul
```

**Environment variables for IBus:**
```bash
# /etc/environment or ~/.config/environment.d/ibus.conf
GTK_IM_MODULE=ibus
QT_IM_MODULE=ibus
XMODIFIERS=@im=ibus

# Required for some Qt apps on Wayland:
IBUS_ENABLE_SYNC_MODE=1
```

**Starting IBus:**
```bash
# Start daemon with replace and XIM support:
exec-once = ibus-daemon -drx

# Or: via systemd (if unit is available):
systemctl --user enable --now org.freedesktop.IBus.session.GNOME.service
```

**IBus Wayland limitations (2025):**

| Feature                             | IBus Status        | Fcitx5 Status |
|-------------------------------------|--------------------|---------------|
| `text-input-v3` native support      | Partial            | Full          |
| Candidate window positioning        | Sometimes off      | Correct       |
| Qt Wayland native mode              | Needs `SYNC_MODE=1`| Works natively|
| Hyprland/Sway support               | Works with workarounds | Works OOB |
| GNOME Wayland support               | First-class        | Good          |
| Configtool (GUI)                    | `ibus-setup`       | `fcitx5-configtool`|

**IBus on Hyprland workaround:**
If IBus candidate window appears at the top-left corner instead of at the cursor:
```bash
# Force IBus to use XIM protocol (less ideal but functional):
unset GTK_IM_MODULE
unset QT_IM_MODULE
export XMODIFIERS=@im=ibus
# Then launch your app under XWayland via:
env WAYLAND_DISPLAY= your-app
```

---

## 79.8 App-Specific Issues

Different application frameworks have different levels of Wayland IME support. This section
documents known issues and their workarounds as of mid-2025.

### Firefox

Firefox on Wayland has good Fcitx5 support when launched with the Wayland backend:
```bash
# Ensure Wayland mode is active (should already be set in your environment):
MOZ_ENABLE_WAYLAND=1 firefox

# If GTK_IM_MODULE is not inherited, force it at launch:
GTK_IM_MODULE=fcitx MOZ_ENABLE_WAYLAND=1 firefox

# Firefox-specific: some users need to disable the in-content IM (preedit in addressbar):
# about:config → ui.useNativeIMEInContentProcess → false (if preedit breaks)
```

**Firefox user.js settings for IME:**
```javascript
// ~/.mozilla/firefox/<profile>/user.js
// Enable Wayland text input protocol:
user_pref("widget.wayland.use-move-to-rect", true);
// If preedit composition shows double characters:
user_pref("intl.ime.use_composition_events_for_insert_text", false);
```

### Electron Apps (VS Code, Slack, Discord, Obsidian)

Electron 22+ has Wayland IME support but it must be explicitly enabled:
```bash
# Per-app flags file — example for VS Code:
cat >> ~/.config/code-flags.conf << 'EOF'
--enable-wayland-ime
--wayland-text-input-version=3
EOF
```

For apps using `electron-flags.conf` or similar:
```ini
# ~/.config/electron-flags.conf (read by many Electron apps)
--enable-wayland-ime
--wayland-text-input-version=3
```

**VS Code specifically (`~/.config/code/argv.json`):**
```json
{
    "enable-crash-reporter": false,
    "wayland-text-input-version": "3",
    "enable-wayland-ime": true
}
```

### Terminal Emulators

| Terminal   | Wayland IME (`text-input-v3`) | Preedit in-terminal | Notes                           |
|------------|-------------------------------|---------------------|---------------------------------|
| Kitty      | Yes (0.29+)                   | Yes                 | Best-in-class Wayland IME       |
| Foot       | Yes                           | Yes                 | Excellent Wayland-native support|
| Alacritty  | Partial (0.13+)               | No                  | Commits text only, no preedit   |
| WezTerm    | Yes                           | Yes                 | Good Wayland support            |
| Ghostty    | Yes (1.0+)                    | Yes                 | Native Wayland design           |
| gnome-terminal | Via GTK4                  | Yes                 | Uses `gtk-text-input`           |

### GTK4 Apps

GTK4 apps use the `im-module` mechanism differently from GTK3. The `GTK_IM_MODULE` variable
is read only as a fallback; GTK4 prefers the Wayland-native `text-input-v3` protocol when
available via `fcitx5-gtk`:

```bash
# Verify fcitx5-gtk is installed and provides the GTK4 module:
ls /usr/lib/gtk-4.0/4.0.0/immodules/ 2>/dev/null || \
ls /usr/lib/x86_64-linux-gnu/gtk-4.0/4.0.0/immodules/ 2>/dev/null
# Should list: libim-fcitx5.so or similar

# If GTK4 app still doesn't work:
GTK_IM_MODULE=fcitx your-gtk4-app
```

### Java / Swing Applications

Java apps use the `AWT_TOOLKIT` and `XMODIFIERS` paths:
```bash
# In /etc/environment or before launching:
export AWT_TOOLKIT=MToolkit    # legacy, may help with some apps
export XMODIFIERS=@im=fcitx
export INPUT_METHOD=fcitx

# Or use Java flags:
java -Dawt.useSystemAAFontSettings=on \
     -Dswing.aatext=true \
     -Djava.awt.im.style=on-the-spot \
     -jar your-app.jar
```

### XWayland Apps

X11 apps running under XWayland use the `XMODIFIERS=@im=fcitx` variable and communicate
through the XIM protocol. Fcitx5 bridges this automatically via its XIM support:

```bash
# Verify XIM bridge is active:
fcitx5-diagnose | grep -i "xim\|xmodifiers"

# If XIM bridge is not starting:
# Ensure fcitx5-xim package is installed (some distros split it):
sudo pacman -S fcitx5        # on Arch this is bundled
# Fedora:
sudo dnf install fcitx5-xim
```

---

## 79.9 Advanced: Per-Window IME Toggle with Hyprland

For power users who want fine-grained control over when the IME activates, Hyprland's window
rules and Fcitx5's remote control can be combined:

```conf
# ~/.config/hypr/hyprland.conf

# Disable IME for specific apps (e.g., gaming, passphrase dialogs):
bind = SUPER, F12, exec, fcitx5-remote -c    # close/deactivate IME

# Automate: disable IME when a game (Steam) window becomes focused
windowrulev2 = workspace special:gaming, class:^(steam_app_.*)$

# Script: auto-toggle based on focused window class
# Save as ~/.local/bin/hypr-ime-watch.sh
```

```bash
#!/usr/bin/env bash
# ~/.local/bin/hypr-ime-watch.sh
# Auto-disable Fcitx5 when focused window class is in the blocklist
BLOCKLIST=("steam_app_" "gamescope" "lutris" "wine")

socat -u UNIX-CONNECT:/tmp/hypr/${HYPRLAND_INSTANCE_SIGNATURE}/.socket2.sock - | \
while IFS= read -r event; do
    if [[ "$event" == activewindow* ]]; then
        class=$(echo "$event" | cut -d',' -f2 | tr -d '[:space:]')
        for blocked in "${BLOCKLIST[@]}"; do
            if [[ "$class" == *"$blocked"* ]]; then
                fcitx5-remote -c   # deactivate
                break
            fi
        done
    fi
done
```

```conf
# Launch the watch script on startup:
exec-once = ~/.local/bin/hypr-ime-watch.sh
```

---

## 79.10 Troubleshooting

This section covers the most common failure modes in order of frequency.

### Diagnostic First Steps

Always run `fcitx5-diagnose` first. It checks:
- Whether the correct environment variables are set
- Whether the Fcitx5 process can connect to the Wayland compositor
- Whether toolkit IM modules are found and loaded
- Whether the XIM bridge is functional

```bash
# Run full diagnostic and pipe to a pager:
fcitx5-diagnose 2>&1 | less

# Save to file for sharing:
fcitx5-diagnose 2>&1 > /tmp/fcitx5-diagnose.txt
```

### IME Has No Effect / Ctrl+Space Does Nothing

```bash
# 1. Check Fcitx5 is running:
pgrep -a fcitx5

# 2. Check the trigger key binding hasn't been overridden:
fcitx5-configtool  # Global Options → Hotkey → Trigger Keys

# 3. Check the compositor isn't stealing the keybind:
# In hyprland.conf, search for Ctrl+Space:
grep -i "control.*space\|ctrl.*space" ~/.config/hypr/hyprland.conf

# 4. Force restart:
pkill fcitx5; sleep 0.5; fcitx5 -d --replace
```

### Works in Some Apps But Not Others

This typically means the IME is active but one toolkit's module is missing or misconfigured:

```bash
# Test GTK3 app:
GTK_IM_MODULE=fcitx gedit    # or any GTK3 text editor

# Test Qt5 app:
QT_IM_MODULE=fcitx kate

# Test terminal:
WAYLAND_DEBUG=1 kitty 2>&1 | grep -i "text_input\|im_"

# Check which IM module GTK is loading:
GTK_IM_MODULE=fcitx GTK_DEBUG=modules gedit 2>&1 | grep -i "fcitx\|input method"
```

### Candidate Window Not Appearing / Appearing in Wrong Position

```bash
# Wayland protocol debug — look for text_input and input_method events:
WAYLAND_DEBUG=1 fcitx5 2>&1 | grep -i "text.input\|commit\|preedit" | head -50

# If using classicui and candidate window is off-screen:
# Edit: ~/.config/fcitx5/conf/classicui.conf
# Ensure: UseInputMethodLanguageToDisplayText=True
# Also try toggling: Vertical Candidate List=True/False

# KDE Plasma: make sure the Fcitx5 Plasma applet is added to the system tray
# (it provides positioning hints to KWin)
```

### Qt Apps Not Working on Wayland Native Mode

Qt apps can run in Wayland native mode or XWayland mode. IME only works properly in native
mode with `QT_IM_MODULE=fcitx`:

```bash
# Force Qt Wayland backend:
QT_QPA_PLATFORM=wayland your-qt-app

# Verify Qt is not falling back to XCB:
QT_QPA_PLATFORM=wayland QT_IM_MODULE=fcitx your-qt-app

# Check which Qt IM plugin is available:
find /usr -name "libfcitx5platforminputcontextplugin.so" 2>/dev/null
# Should be in: /usr/lib/qt5/plugins/platforminputcontexts/ (Qt5)
#           or: /usr/lib/qt6/plugins/platforminputcontexts/ (Qt6)
```

### Fcitx5 Crashes or Fails to Start

```bash
# Run in foreground with maximum verbosity:
fcitx5 --verbose '*:5' 2>&1 | tee /tmp/fcitx5-verbose.log

# Common crash cause: corrupted config files
# Reset to defaults (backup first):
cp -r ~/.config/fcitx5 ~/.config/fcitx5.bak
rm -rf ~/.config/fcitx5
fcitx5 -d    # regenerates default config

# Check for conflicting processes:
ps aux | grep -E "fcitx|ibus|uim|scim"
# Kill any orphaned IM processes before starting Fcitx5
```

### Environment Variables Not Reaching Apps

If environment variables set in `/etc/environment` or `~/.config/environment.d/` are not
reaching applications, the issue is typically systemd environment propagation:

```bash
# Check current systemd user environment:
systemctl --user show-environment | grep -E "GTK_IM|QT_IM|XMODIFIERS"

# If missing, import them manually:
systemctl --user import-environment GTK_IM_MODULE QT_IM_MODULE XMODIFIERS SDL_IM_MODULE

# Or use a DBus activation helper (for GNOME sessions):
dbus-update-activation-environment --systemd GTK_IM_MODULE=fcitx QT_IM_MODULE=fcitx XMODIFIERS=@im=fcitx
```

For Hyprland users, add this to your config to ensure systemd gets the variables:
```conf
# ~/.config/hypr/hyprland.conf
exec-once = systemctl --user import-environment GTK_IM_MODULE QT_IM_MODULE XMODIFIERS
exec-once = dbus-update-activation-environment --systemd GTK_IM_MODULE QT_IM_MODULE XMODIFIERS
```

---

*See also: Ch 12 (Session Startup), Ch 41 (Hyprland Environment Configuration),
Ch 53 (Systemd User Services), Ch 87 (Font Rendering and Locale), Ch 44 (Accessibility Tools).*

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
