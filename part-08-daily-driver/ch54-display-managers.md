# Chapter 54 — Display Managers and Greeters: SDDM, GDM, greetd

## Contents

- [Overview](#overview)
- [54.1 Display Manager Comparison](#541-display-manager-comparison)
- [54.2 SDDM — Qt-Based Login Screen](#542-sddm-qt-based-login-screen)
  - [Installation](#installation)
  - [Core Configuration](#core-configuration)
  - [Theme Installation](#theme-installation)
  - [Writing a Custom QML Theme](#writing-a-custom-qml-theme)
  - [NixOS Configuration](#nixos-configuration)
- [54.3 GDM — GNOME Display Manager](#543-gdm-gnome-display-manager)
  - [Installation and Basic Config](#installation-and-basic-config)
  - [Theming GDM](#theming-gdm)
- [54.4 greetd — The Compositor-Agnostic Daemon](#544-greetd-the-compositor-agnostic-daemon)
  - [Installation and Core Config](#installation-and-core-config)
- [54.5 greetd Greeters](#545-greetd-greeters)
  - [ReGreet — GTK4 Graphical Greeter](#regreet-gtk4-graphical-greeter)
  - [tuigreet — Terminal UI Greeter](#tuigreet-terminal-ui-greeter)
  - [wlgreet — Minimal Wayland Greeter](#wlgreet-minimal-wayland-greeter)
  - [Quickshell Greeter](#quickshell-greeter)
- [54.6 No Display Manager — TTY Autologin](#546-no-display-manager-tty-autologin)
  - [systemd getty Override](#systemd-getty-override)
  - [Shell Profile Compositor Launch](#shell-profile-compositor-launch)
- [54.7 Session Desktop Files](#547-session-desktop-files)
- [54.8 Multi-Monitor Display Manager Configuration](#548-multi-monitor-display-manager-configuration)
  - [SDDM Multi-Monitor](#sddm-multi-monitor)
  - [GDM Multi-Monitor](#gdm-multi-monitor)
  - [greetd Multi-Monitor](#greetd-multi-monitor)
- [54.9 PAM and Security Considerations](#549-pam-and-security-considerations)
  - [Checking the PAM Stack](#checking-the-pam-stack)
  - [Adding FIDO2 / YubiKey Authentication](#adding-fido2-yubikey-authentication)
  - [Fingerprint Authentication (fprintd)](#fingerprint-authentication-fprintd)
- [Troubleshooting](#troubleshooting)
  - [SDDM fails to start, black screen after enable](#sddm-fails-to-start-black-screen-after-enable)
  - [greetd greeter exits immediately / loop restart](#greetd-greeter-exits-immediately-loop-restart)
  - [GDM forces X11 instead of Wayland](#gdm-forces-x11-instead-of-wayland)
  - [SDDM theme not applying](#sddm-theme-not-applying)
  - [Session not appearing in DM session list](#session-not-appearing-in-dm-session-list)
  - [Autologin loop (TTY autologin)](#autologin-loop-tty-autologin)
- [54.10 Creating a Custom SDDM QML Theme from Scratch](#5410-creating-a-custom-sddm-qml-theme-from-scratch)
  - [Directory Structure](#directory-structure)
  - [theme.conf](#themeconf)
  - [Minimal Main.qml](#minimal-mainqml)
  - [SDDM QML API reference](#sddm-qml-api-reference)
  - [Installing and selecting the theme](#installing-and-selecting-the-theme)

---


## Overview

The display manager (DM) is the first visual element a user encounters after boot — the login screen
that authenticates you and launches your compositor session. For a fully realized rice, the login
experience must be cohesive with the rest of the desktop: matching colorschemes, fonts, wallpapers,
and cursor themes carry your aesthetic from BIOS to compositor. This chapter covers every major
display manager and greeter for Wayland setups, from heavyweight Qt-based SDDM to the razor-thin
greetd daemon, plus the no-DM autologin approach for users who want zero latency.

Understanding how display managers interact with Wayland is essential. Unlike X11 where a DM simply
ran an Xserver and a session script, Wayland DMs must handle PAM authentication, VT switching, seat
management via logind, and session environment injection — all before a single compositor frame is
rendered. SDDM and GDM ship their own compositor to render the login screen; greetd delegates that
entirely to a separate greeter process. This architectural difference shapes every theming and
configuration decision you make.

See Ch 53 for session startup scripts that run after the DM hands off to your compositor. See
Ch 12 for compositor-level environment variables that your DM must inject. If you are using a
custom PAM stack or systemd-homed, refer to Ch 58 (System Integration).

---

## 54.1 Display Manager Comparison

The table below summarizes the four viable options for Wayland-first setups in 2024. LightDM is
included for legacy reference but is not recommended for new rices — its Wayland support is partial
and the project is effectively unmaintained for Wayland use cases.

| DM         | Backend         | Theming system | Wayland native | Best for                  | Resource use |
|------------|-----------------|----------------|----------------|---------------------------|--------------|
| SDDM       | Qt / QML        | QML themes     | Yes (Qt6)      | Hyprland, KDE, Niri       | Medium       |
| GDM        | Mutter/GNOME    | GNOME CSS/ext  | Yes            | GNOME Shell               | High         |
| greetd     | None (daemon)   | Any Wayland app| Yes (via GTK4) | Any compositor, ricers    | Very low     |
| ly         | ncurses TUI     | Compile-time   | Partial        | TTY-only minimal rices    | Minimal      |
| LightDM    | GTK3 (legacy)   | GTK greeters   | Partial        | Legacy GTK setups         | Low          |

For most Wayland ricers the decision tree is: using GNOME Shell → GDM; using KDE Plasma → SDDM;
using anything else (Hyprland, Sway, niri, river, etc.) → greetd + a greeter of choice. The TTY
autologin path (Section 54.6) is appropriate when you want zero authentication overhead on a
single-user machine.

---

## 54.2 SDDM — Qt-Based Login Screen

SDDM (Simple Desktop Display Manager) is the reference DM for KDE Plasma and has become the most
popular choice for Hyprland and other wlroots compositors. Since version 0.21 it runs as a Wayland
compositor itself using the `kwin_wayland` backend, replacing the older X11-based greeter. This
means SDDM themes render in full Wayland with proper HiDPI support, fractional scaling, and
multi-monitor layouts.

SDDM reads session `.desktop` files from `/usr/share/wayland-sessions/` and
`/usr/share/xsessions/`, presents them in the session selector, and after authentication calls
`exec` on the session's `Exec=` line. PAM is handled via `/etc/pam.d/sddm`. The greeter itself
runs as the `sddm` system user; after login it drops to your user and starts the session.

### Installation

```bash
# Arch Linux
sudo pacman -S sddm

# Fedora
sudo dnf install sddm

# NixOS (see NixOS snippet below)

# Enable and start
sudo systemctl enable --now sddm
```

On Arch you may want `sddm-git` from the AUR to get the latest Wayland compositor backend:

```bash
paru -S sddm-git
```

### Core Configuration

The main config lives in `/etc/sddm.conf.d/`. Drop any `.conf` file there — SDDM merges all of
them. A minimal Wayland-first config:

```ini
# /etc/sddm.conf.d/10-wayland.conf
[General]
DisplayServer=wayland
GreeterEnvironment=QT_WAYLAND_SHELL_INTEGRATION=layer-shell,QT_QPA_PLATFORM=wayland

[Theme]
Current=catppuccin-mocha
CursorTheme=Catppuccin-Mocha-Dark-Cursors
CursorSize=24
Font=Inter,11,-1,5,400,0,0,0,0,0,Regular

[Users]
MaximumUid=60000
MinimumUid=1000
HideShells=/sbin/nologin,/bin/false
RememberLastUser=true
RememberLastSession=true

[Autologin]
# Uncomment for passwordless boot on single-user machines
# User=yourname
# Session=hyprland
# Relogin=false
```

For multi-monitor setups, specify which display SDDM renders on:

```ini
# /etc/sddm.conf.d/20-monitor.conf
[X11]
ServerArguments=-nolisten tcp -dpi 192

[Wayland]
CompositorCommand=kwin_wayland --no-lockscreen --inputmethod qtvirtualkeyboard --drm --locale1
```

### Theme Installation

SDDM themes are QML packages placed under `/usr/share/sddm/themes/` (system-wide) or
`~/.local/share/sddm/themes/` (user, for test-mode only — production SDDM runs as root).

Popular themes and their install methods:

```bash
# Catppuccin SDDM (AUR)
paru -S sddm-theme-catppuccin

# Or manual clone
sudo git clone https://github.com/catppuccin/sddm \
    /usr/share/sddm/themes/catppuccin-mocha

# Sugar-Dark (AUR)
paru -S sddm-sugar-dark

# Where Is My SDDM theme (highly configurable)
paru -S where-is-my-sddm-theme-git

# Preview a theme without rebooting
sddm-greeter-qt6 --test-mode --theme /usr/share/sddm/themes/catppuccin-mocha
```

### Writing a Custom QML Theme

Every SDDM theme must contain at minimum a `metadata.desktop` and a `Main.qml`. The QML file
receives injected `SessionModel`, `UserModel`, and `ScreenModel` objects.

```
/usr/share/sddm/themes/myrice/
├── metadata.desktop
├── Main.qml
├── background.jpg
├── components/
│   ├── UserField.qml
│   └── PasswordField.qml
└── theme.conf
```

```ini
# metadata.desktop
[SddmGreeterTheme]
Name=MyRice
Description=Custom rice greeter
Author=yourname
Version=1.0
License=CC-BY-4.0
Type=sddm-theme
```

```qml
// Main.qml — minimal working example
import QtQuick 2.15
import QtQuick.Controls 2.15
import SddmComponents 2.0

Rectangle {
    id: root
    color: "#1e1e2e"   // Catppuccin Mocha base

    property var config: config
    property var sessionModel: sessionModel
    property var userModel: userModel
    property var keyboard: keyboard

    Image {
        anchors.fill: parent
        source: config.background !== undefined ? config.background : ""
        fillMode: Image.PreserveAspectCrop
    }

    Column {
        anchors.centerIn: parent
        spacing: 16

        Text {
            text: Qt.formatDateTime(new Date(), "hh:mm")
            color: "#cdd6f4"
            font.pixelSize: 72
            font.family: "Inter"
            anchors.horizontalCenter: parent.horizontalCenter
        }

        TextField {
            id: passwordField
            width: 280
            placeholderText: "Password"
            echoMode: TextInput.Password
            color: "#cdd6f4"
            background: Rectangle { color: "#313244"; radius: 8 }
            Keys.onReturnPressed: sddm.login(userModel.lastUser, passwordField.text,
                                              sessionModel.lastIndex)
        }

        Button {
            text: "Login"
            onClicked: sddm.login(userModel.lastUser, passwordField.text,
                                  sessionModel.lastIndex)
        }
    }

    Connections {
        target: sddm
        function onLoginFailed() {
            passwordField.text = ""
            passwordField.focus = true
        }
    }
}
```

### NixOS Configuration

```nix
# configuration.nix
services.displayManager.sddm = {
  enable = true;
  wayland.enable = true;
  theme = "catppuccin-mocha";
  settings = {
    General = {
      DisplayServer = "wayland";
      GreeterEnvironment = "QT_WAYLAND_SHELL_INTEGRATION=layer-shell";
    };
    Theme = {
      CursorTheme = "Catppuccin-Mocha-Dark-Cursors";
      CursorSize = 24;
      Font = "Inter,11,-1,5,400,0,0,0,0,0,Regular";
    };
  };
  extraPackages = with pkgs; [
    catppuccin-sddm
    catppuccin-cursors.mochaDark
  ];
};
```

---

## 54.3 GDM — GNOME Display Manager

GDM is the reference display manager for GNOME Shell and is tightly coupled to GNOME's technology
stack: it uses Mutter as its compositor backend, communicates with GNOME Keyring via PAM, and
manages sessions through GNOME Session Manager. Outside of a GNOME Shell session it is overkill —
it pulls in the full GNOME compositor stack at login. If you run GNOME Shell as your daily driver,
however, it is the most polished option with flawless HiDPI and accessibility support.

GDM 44+ has improved Wayland support significantly: it defaults to Wayland on supported hardware,
handles XWayland for legacy apps in the greeter itself, and properly manages multi-seat setups. The
`/etc/gdm/custom.conf` file controls the daemon; per-user settings in `~/.config/gdm/` are rare.

### Installation and Basic Config

```bash
# Arch
sudo pacman -S gdm
sudo systemctl enable --now gdm

# Fedora (usually pre-installed)
sudo dnf install gdm
sudo systemctl enable --now gdm
```

```ini
# /etc/gdm/custom.conf
[daemon]
WaylandEnable=true
AutomaticLoginEnable=false
# AutomaticLogin=yourname
TimedLoginEnable=false
DefaultSession=gnome-wayland.desktop

[security]
AllowRemoteAutoLogin=false

[xdmcp]
Enable=false

[greeter]
IncludeAll=true
```

### Theming GDM

GDM inherits GNOME Shell's CSS theming. The login screen uses the same GNOME Shell theme as your
desktop session. To apply a custom theme:

```bash
# Install user-themes extension if not already present
gnome-extensions install user-themes@gnome-shell-extensions.gcampax.github.com

# Set the shell theme
gsettings set org.gnome.shell.extensions.user-theme name "Catppuccin-Mocha-Standard-Mauve-Dark"

# For GDM specifically, you need to compile the theme into the GDM gresource
# This requires the gdm-settings tool (recommended) or manual gresource manipulation
sudo pacman -S gdm-settings   # AUR: gdm-settings
gdm-settings   # GUI tool to set GDM background, theme, and panel options
```

For scripted GDM background changes without the GUI:

```bash
#!/usr/bin/env bash
# set-gdm-background.sh — compile a wallpaper into GDM's gresource bundle
WALLPAPER="$1"
GRESOURCE="/usr/share/gnome-shell/gnome-shell-theme.gresource"
WORKDIR=$(mktemp -d)

# Extract existing resources
gresource extract "$GRESOURCE" /org/gnome/shell/theme/gnome-shell.css > "$WORKDIR/gnome-shell.css"

# Write XML manifest with custom background
cat > "$WORKDIR/gdm.gresource.xml" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<gresources>
  <gresource prefix="/org/gnome/shell/theme">
    <file>gnome-shell.css</file>
    <file alias="background">$(basename "$WALLPAPER")</file>
  </gresource>
</gresources>
EOF

cp "$WALLPAPER" "$WORKDIR/$(basename "$WALLPAPER")"
glib-compile-resources --sourcedir="$WORKDIR" "$WORKDIR/gdm.gresource.xml" \
    --target="$WORKDIR/gnome-shell-theme.gresource"
sudo cp "$WORKDIR/gnome-shell-theme.gresource" "$GRESOURCE"
rm -rf "$WORKDIR"
```

---

## 54.4 greetd — The Compositor-Agnostic Daemon

greetd is architecturally different from SDDM and GDM: it is a tiny PAM daemon that knows nothing
about graphics. Its sole job is to accept an IPC connection from a greeter process, verify
credentials, and exec the user session. The greeter itself can be *any* process — a GTK4 app, a
TUI, a wlroots compositor, or a fully custom QML application. This makes greetd the ricer's
preferred option: you can match your login screen's aesthetic to any framework you like.

The greetd socket is at `/run/greetd.sock`. The protocol is a simple JSON IPC defined in the
greetd source. Greeters authenticate by exchanging JSON messages: `create_session`, `post_auth_message_response`, and `start_session`. For most users this is invisible — you configure
a greeter and it handles the protocol.

### Installation and Core Config

```bash
# Arch
sudo pacman -S greetd

# Enable
sudo systemctl enable --now greetd
```

```toml
# /etc/greetd/config.toml
[terminal]
vt = 1          # Virtual terminal to use; "next" picks the next available

[default_session]
# The greeter command; runs as the 'greeter' user by default
# Replace with your chosen greeter (see 54.5)
command = "tuigreet --cmd Hyprland --time --remember --remember-session"
user = "greeter"
```

The `greeter` user must exist and have the right PAM session permissions. greetd's install creates
this user, but verify:

```bash
id greeter          # should return greeter user info
# If missing:
sudo useradd -r -s /sbin/nologin greeter
```

greetd reads `/etc/pam.d/greetd` for PAM configuration. A safe default:

```
# /etc/pam.d/greetd
auth       include    system-login
account    include    system-login
session    include    system-login
```

---

## 54.5 greetd Greeters

### ReGreet — GTK4 Graphical Greeter

ReGreet is the most visually capable greetd greeter. It renders a GTK4 window using the layer-shell
protocol, supports GTK themes (including Catppuccin), icon themes, custom fonts, and wallpapers.

```bash
paru -S regreet   # AUR
# or build from source:
# cargo install regreet
```

```toml
# /etc/greetd/config.toml
[default_session]
command = "cage -s -- regreet"   # cage is a kiosk compositor for regreet
user = "greeter"
```

`cage` is required because regreet is a Wayland client that needs a Wayland server to render into.
The `cage` kiosk compositor provides a minimal wlroots compositor just for this purpose:

```bash
sudo pacman -S cage
```

```toml
# /etc/greetd/regreet.toml
[background]
path = "/usr/share/wallpapers/myrice.jpg"
fit = "Cover"           # Cover | Contain | Fill | ScaleDown | None

[GTK]
application_prefer_dark_theme = true
cursor_theme_name = "Catppuccin-Mocha-Dark-Cursors"
font_name = "Inter 11"
icon_theme_name = "Papirus-Dark"
theme_name = "catppuccin-mocha-mauve-standard+default"

[env]
# Environment variables injected into the greeter
QT_QPA_PLATFORM = "wayland"

[commands]
reboot = ["systemctl", "reboot"]
poweroff = ["systemctl", "poweroff"]
```

### tuigreet — Terminal UI Greeter

tuigreet is a TUI greeter that renders in the terminal. It is ideal when you want zero graphical
overhead at login, or when running headless/SSH-accessible machines.

```bash
paru -S greetd-tuigreet
# or
sudo pacman -S greetd-tuigreet   # available in community on Arch
```

```toml
# /etc/greetd/config.toml
[default_session]
command = """tuigreet \
  --cmd Hyprland \
  --time \
  --time-format '%Y-%m-%d %H:%M' \
  --remember \
  --remember-session \
  --sessions /usr/share/wayland-sessions \
  --xsessions /usr/share/xsessions \
  --greeting 'Welcome back' \
  --asterisks \
  --theme 'border=magenta;text=cyan;prompt=green;time=red;action=blue;button=yellow;container=black;input=red'"""
user = "greeter"
```

The `--theme` flag uses a key=value color string; valid color names map to terminal colors. This
lets tuigreet match your terminal colorscheme.

### wlgreet — Minimal Wayland Greeter

wlgreet is a bare-bones Wayland greeter using the wlr-layer-shell protocol. It renders directly in
a wlroots compositor, making it lighter than GTK4 alternatives. Configuration is a TOML file:

```bash
paru -S wlgreet
```

```toml
# /etc/greetd/config.toml
[default_session]
command = "sway --config /etc/greetd/sway-config"   # wlgreet runs inside sway
user = "greeter"
```

```
# /etc/greetd/sway-config
exec "wlgreet; swaymsg exit"
bindsym Mod4+shift+e exec swaynag ...
output * bg /usr/share/wallpapers/myrice.jpg fill
default_border none
```

### Quickshell Greeter

Quickshell (Ch 24) provides a `Quickshell.Services.Greetd` module that exposes the greetd IPC
directly in QML. This gives you unlimited visual customization with the full QML/Qt toolkit,
matching your bar and lockscreen exactly.

```bash
paru -S quickshell-git
```

A minimal Quickshell greeter config:

```qml
// ~/.config/quickshell/greeter/shell.qml
import Quickshell
import Quickshell.Services.Greetd
import QtQuick

ShellRoot {
    GreetdSession {
        id: greetd
        onSessionStarted: Qt.quit()
        onAuthError: passwordField.clear()
    }

    PanelWindow {
        anchors.fill: true
        color: "#1e1e2e"

        Column {
            anchors.centerIn: parent
            spacing: 12

            Text {
                text: "Enter Password"
                color: "#cdd6f4"
                font.pixelSize: 18
            }

            TextInput {
                id: passwordField
                echoMode: TextInput.Password
                color: "#cdd6f4"
                Keys.onReturnPressed: greetd.respond(text)
            }
        }
    }

    Component.onCompleted: greetd.createSession("yourname")
}
```

Launch it via greetd:

```toml
# /etc/greetd/config.toml
[default_session]
command = "quickshell -c /etc/greetd/quickshell-greeter"
user = "greeter"
```

---

## 54.6 No Display Manager — TTY Autologin

For single-user machines where authentication overhead is unwanted, or for compositors that behave
poorly under a DM, TTY autologin is a clean solution. systemd handles the autologin; your shell
profile launches the compositor. There is no login screen — the machine boots directly to your
desktop.

This approach has security implications: physical access = full session access. Do not use it on
shared or portable machines without full-disk encryption.

### systemd getty Override

```bash
sudo mkdir -p /etc/systemd/system/getty@tty1.service.d/
```

```ini
# /etc/systemd/system/getty@tty1.service.d/autologin.conf
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin yourname --noclear %I $TERM
Type=simple
```

```bash
sudo systemctl daemon-reload
sudo systemctl restart getty@tty1
```

### Shell Profile Compositor Launch

Add compositor launch logic to your login shell's profile file. Use a guard to prevent launching on
TTY2+, SSH sessions, or if a Wayland session is already running:

```bash
# ~/.zprofile  (or ~/.bash_profile / ~/.profile)
if [[ -z "$WAYLAND_DISPLAY" && -z "$DISPLAY" && "$XDG_VTNR" == "1" ]]; then
    # Inject session environment before compositor starts
    export XDG_SESSION_TYPE=wayland
    export XDG_CURRENT_DESKTOP=Hyprland
    export MOZ_ENABLE_WAYLAND=1
    export ELECTRON_OZONE_PLATFORM_HINT=wayland
    export QT_QPA_PLATFORM=wayland
    export SDL_VIDEODRIVER=wayland
    exec Hyprland > ~/.local/share/hyprland/session.log 2>&1
fi
```

For niri:

```bash
if [[ -z "$WAYLAND_DISPLAY" && "$XDG_VTNR" == "1" ]]; then
    exec niri-session
fi
```

For Sway, using dbus-run-session to ensure D-Bus is available:

```bash
if [[ -z "$WAYLAND_DISPLAY" && "$XDG_VTNR" == "1" ]]; then
    exec dbus-run-session sway
fi
```

---

## 54.7 Session Desktop Files

All display managers (and the TTY autologin path via `tuigreet --sessions`) read `.desktop` files
to enumerate available sessions. Wayland sessions go in `/usr/share/wayland-sessions/`; X11
sessions in `/usr/share/xsessions/`. Package managers install these files with the compositor
package, but you may need to create custom ones for unsupported sessions or custom launch wrappers.

```ini
# /usr/share/wayland-sessions/hyprland.desktop
[Desktop Entry]
Name=Hyprland
Comment=A dynamic tiling Wayland compositor
Exec=Hyprland
TryExec=Hyprland
Type=Application
DesktopNames=Hyprland
Keywords=wayland;compositor;tiling;
```

For a session that requires environment setup (e.g. wrapper script):

```ini
# /usr/share/wayland-sessions/hyprland-wrapped.desktop
[Desktop Entry]
Name=Hyprland (wrapped)
Comment=Hyprland with environment injection
Exec=/usr/local/bin/hyprland-session-wrapper
TryExec=Hyprland
Type=Application
DesktopNames=Hyprland
```

```bash
#!/usr/bin/env bash
# /usr/local/bin/hyprland-session-wrapper
export MOZ_ENABLE_WAYLAND=1
export ELECTRON_OZONE_PLATFORM_HINT=wayland
export QT_QPA_PLATFORM=wayland
export NIXOS_OZONE_WL=1
exec systemd-run --user --scope --collect \
    -p PAMName=login \
    Hyprland
```

greetd with tuigreet uses the `--sessions` flag to point at the directory:

```toml
[default_session]
command = "tuigreet --sessions /usr/share/wayland-sessions --remember-session"
```

SDDM and GDM scan `/usr/share/wayland-sessions/` automatically at startup — no additional config
needed.

---

## 54.8 Multi-Monitor Display Manager Configuration

Multi-monitor login screens require the DM to know about your monitor layout before KWin/Mutter/
wlroots starts. Each DM handles this differently.

### SDDM Multi-Monitor

SDDM uses kwin_wayland as its Wayland backend, which reads KScreen layouts from
`~/.local/share/kscreen/` — but since SDDM runs as the `sddm` system user, you need to place
configs in the `sddm` home directory (`/var/lib/sddm/`):

```bash
# Run sddm-greeter with test mode and configure monitors via KScreen
# Then copy the config
sudo cp -r ~/.local/share/kscreen /var/lib/sddm/.local/share/

# Or use xrandr-style args via the compositor command:
# In /etc/sddm.conf.d/monitors.conf:
```

```ini
[Wayland]
CompositorCommand=kwin_wayland --no-lockscreen --drm \
    --output-name DP-1 --output-mode 2560x1440@144 \
    --output-name HDMI-1 --output-mode 1920x1080@60
```

### GDM Multi-Monitor

GDM respects `~/.config/monitors.xml` for the `gdm` user. Copy your session monitors config:

```bash
sudo cp ~/.config/monitors.xml /var/lib/gdm/.config/monitors.xml
sudo chown gdm:gdm /var/lib/gdm/.config/monitors.xml
```

### greetd Multi-Monitor

Since the greeter is a regular Wayland client, multi-monitor support depends on the kiosk compositor
(e.g. `cage`). cage only renders on one output by default. For multi-output, use sway as the
greeter compositor:

```toml
# /etc/greetd/config.toml
[default_session]
command = "sway --config /etc/greetd/sway-greeter.conf"
user = "greeter"
```

```
# /etc/greetd/sway-greeter.conf
output DP-1 resolution 2560x1440 position 0,0
output HDMI-1 resolution 1920x1080 position 2560,0
output * bg /usr/share/wallpapers/myrice.jpg fill
exec "regreet; swaymsg exit"
default_border none
input * xkb_layout "us"
```

---

## 54.9 PAM and Security Considerations

Display managers authenticate through PAM (Pluggable Authentication Modules). Understanding the PAM
stack matters when using non-standard authentication like FIDO2 keys, fingerprint readers, or
systemd-homed.

### Checking the PAM Stack

```bash
# View the PAM config for your DM
cat /etc/pam.d/sddm
cat /etc/pam.d/gdm-password
cat /etc/pam.d/greetd

# Test PAM authentication (does not start a session)
pamtester sddm yourname authenticate
```

### Adding FIDO2 / YubiKey Authentication

```bash
sudo pacman -S pam-u2f

# Enroll your key
pamu2fcfg >> ~/.config/Yubico/u2f_keys

# Add to the PAM stack (before the password module)
# /etc/pam.d/sddm
# auth   sufficient   pam_u2f.so   authfile=/etc/security/u2f_keys   cue   [cue_prompt=Touch YubiKey: ]
```

### Fingerprint Authentication (fprintd)

```bash
sudo pacman -S fprintd
sudo systemctl enable --now fprintd

# Enroll fingerprint
fprintd-enroll yourname

# Add to PAM stack
# /etc/pam.d/sddm
# auth   sufficient   pam_fprintd.so
```

---

## Troubleshooting

### SDDM fails to start, black screen after enable

```bash
# Check the journal for SDDM errors
journalctl -u sddm -b --no-pager | tail -50

# Common cause: missing kwin_wayland or wrong DisplayServer setting
# Verify kwin_wayland exists:
which kwin_wayland || sudo pacman -S plasma-workspace

# Fallback: switch back to X11 mode temporarily
echo '[General]
DisplayServer=x11' | sudo tee /etc/sddm.conf.d/00-fallback.conf
sudo systemctl restart sddm
```

### greetd greeter exits immediately / loop restart

```bash
# greetd restarts the greeter on exit — check for greeter errors
journalctl -u greetd -b --no-pager

# Common causes:
# 1. 'cage' not installed (for regreet)
# 2. greeter binary not in PATH for the greeter system user
# 3. PAM misconfiguration

# Test the greeter command manually as the greeter user:
sudo -u greeter env XDG_RUNTIME_DIR=/run/user/$(id -u greeter) \
    tuigreet --cmd bash --time
```

### GDM forces X11 instead of Wayland

```bash
# Check if Wayland is disabled by udev rule (common on NVIDIA)
cat /usr/lib/udev/rules.d/61-gdm.rules | grep -i wayland

# Override: create a local rule to re-enable
sudo mkdir -p /etc/udev/rules.d/
# Copy and edit the rule, removing the WaylandEnable=false lines
sudo cp /usr/lib/udev/rules.d/61-gdm.rules /etc/udev/rules.d/61-gdm.rules
# Edit /etc/udev/rules.d/61-gdm.rules and remove NVIDIA-specific Wayland disabling

# Also check /etc/gdm/custom.conf:
grep -i wayland /etc/gdm/custom.conf
```

### SDDM theme not applying

```bash
# Verify theme path and name
ls /usr/share/sddm/themes/
cat /etc/sddm.conf.d/*.conf | grep Current

# Theme name must exactly match directory name
# Check for typos — SDDM silently falls back to default on mismatch

# Test theme directly
sddm-greeter-qt6 --test-mode --theme /usr/share/sddm/themes/catppuccin-mocha
```

### Session not appearing in DM session list

```bash
# Verify the .desktop file exists and is valid
ls /usr/share/wayland-sessions/
desktop-file-validate /usr/share/wayland-sessions/hyprland.desktop

# Check Exec= path is absolute and executable
which Hyprland

# For greetd+tuigreet: verify the --sessions flag points to the right dir
# and the .desktop files have valid TryExec= entries
```

### Autologin loop (TTY autologin)

If the compositor exits immediately and you get a fast autologin loop crashing the terminal:

```bash
# TTY2 escape: switch with Ctrl+Alt+F2, then:
# Disable the autologin override temporarily
sudo mv /etc/systemd/system/getty@tty1.service.d/autologin.conf \
        /etc/systemd/system/getty@tty1.service.d/autologin.conf.disabled
sudo systemctl daemon-reload && sudo systemctl restart getty@tty1

# Check the session log written by the compositor
cat ~/.local/share/hyprland/session.log
```

---

*See also: Ch 53 (Session Startup and Environment Injection), Ch 24 (Quickshell), Ch 12 (Wayland
Environment Variables), Ch 58 (System Integration and systemd-homed).*

---

## 54.10 Creating a Custom SDDM QML Theme from Scratch

SDDM's theming system is built on Qt QML. A theme is a directory installed under
`/usr/share/sddm/themes/` containing a `Main.qml` entry point, a `theme.conf`
metadata file, and any assets (images, fonts, SVGs). This section walks through
building a minimal but complete theme.

### Directory Structure

```
/usr/share/sddm/themes/my-rice-login/
├── Main.qml           — entry point (required)
├── theme.conf         — theme metadata (required)
├── preview.png        — screenshot shown in SDDM configurator
├── background.jpg     — wallpaper
└── components/
    ├── LoginForm.qml  — extracted login form component
    └── UserDelegate.qml
```

### theme.conf

```ini
[General]
name=My Rice Login
description=Tokyo Night themed SDDM login screen
type=sddm-theme
version=1.0
author=yourname
screenshot=preview.png
background=background.jpg
```

### Minimal Main.qml

```qml
// Main.qml — SDDM QML entry point

import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import SddmComponents 2.0      // SDDM-provided: UserModel, SessionModel, etc.

Rectangle {
    id: root
    width:  Screen.width
    height: Screen.height
    color:  "#1a1b26"          // Tokyo Night background

    // Background wallpaper
    Image {
        anchors.fill: parent
        source:       "background.jpg"
        fillMode:     Image.PreserveAspectCrop
        smooth:       true
    }

    // Frosted overlay
    Rectangle {
        anchors.fill: parent
        color:        Qt.rgba(0.1, 0.11, 0.15, 0.6)
    }

    // Center login card
    Rectangle {
        anchors.centerIn: parent
        width:            360
        height:           320
        radius:           12
        color:            "#24283b"
        border.color:     "#3b4261"
        border.width:     1

        ColumnLayout {
            anchors {
                fill:    parent
                margins: 32
            }
            spacing: 16

            // Session hostname
            Text {
                Layout.alignment: Qt.AlignHCenter
                text:             sddm.hostName
                font {
                    family:    "JetBrainsMono Nerd Font"
                    pointSize: 14
                    bold:      true
                }
                color: "#7aa2f7"
            }

            // User selector (drop-down from UserModel)
            ComboBox {
                id:             userBox
                Layout.fillWidth: true
                model:          UserModel
                textRole:       "name"
                displayText:    currentText
                currentIndex:   UserModel.lastIndex

                contentItem: Text {
                    text:             parent.displayText
                    font.family:      "JetBrainsMono Nerd Font"
                    font.pointSize:   11
                    color:            "#a9b1d6"
                    verticalAlignment: Text.AlignVCenter
                    leftPadding:      8
                }

                background: Rectangle {
                    color:        "#3b4261"
                    radius:       6
                    border.color: userBox.activeFocus ? "#7aa2f7" : "#565f89"
                    border.width: 1
                }
            }

            // Password field
            TextField {
                id:               passwordField
                Layout.fillWidth: true
                placeholderText:  "Password"
                echoMode:         TextInput.Password
                font.family:      "JetBrainsMono Nerd Font"
                font.pointSize:   11
                color:            "#a9b1d6"
                Keys.onReturnPressed: loginButton.clicked()

                background: Rectangle {
                    color:        "#3b4261"
                    radius:       6
                    border.color: passwordField.activeFocus ? "#7aa2f7" : "#565f89"
                    border.width: 1
                }
            }

            // Session selector
            ComboBox {
                id:               sessionBox
                Layout.fillWidth: true
                model:            SessionModel
                textRole:         "name"
                currentIndex:     SessionModel.lastIndex

                contentItem: Text {
                    text:             parent.displayText
                    font.family:      "JetBrainsMono Nerd Font"
                    font.pointSize:   10
                    color:            "#565f89"
                    verticalAlignment: Text.AlignVCenter
                    leftPadding:      8
                }

                background: Rectangle {
                    color:        "#1a1b26"
                    radius:       6
                    border.color: "#3b4261"
                    border.width: 1
                }
            }

            // Login button
            Button {
                id:               loginButton
                Layout.fillWidth: true
                text:             "Login"
                font.family:      "JetBrainsMono Nerd Font"
                font.pointSize:   11
                font.bold:        true

                contentItem: Text {
                    text:                  parent.text
                    font:                  parent.font
                    color:                 "#1a1b26"
                    horizontalAlignment:   Text.AlignHCenter
                    verticalAlignment:     Text.AlignVCenter
                }

                background: Rectangle {
                    color:  loginButton.pressed ? "#5a82d7" : "#7aa2f7"
                    radius: 6
                }

                onClicked: {
                    sddm.login(
                        userBox.currentText,
                        passwordField.text,
                        sessionBox.currentIndex
                    )
                }
            }
        }
    }

    // Error message from failed login
    Connections {
        target: sddm
        function onLoginFailed() {
            passwordField.clear()
            passwordField.placeholderText = "Incorrect password"
        }
    }

    // Clock in corner
    Text {
        anchors {
            bottom:       parent.bottom
            right:        parent.right
            margins:      24
        }
        text:  Qt.formatDateTime(new Date(), "hh:mm")
        color: "#a9b1d6"
        font {
            family:    "JetBrainsMono Nerd Font"
            pointSize: 32
            bold:      true
        }

        Timer {
            interval: 1000
            running:  true
            repeat:   true
            onTriggered: parent.text = Qt.formatDateTime(new Date(), "hh:mm")
        }
    }
}
```

### SDDM QML API reference

| Object | Type | Key properties |
|---|---|---|
| `sddm` | SDDM controller | `hostName`, `login(user, pass, sessionIndex)`, `suspend()`, `hibernate()`, `reboot()`, `powerOff()` |
| `UserModel` | ListModel | `name`, `realName`, `icon`, `lastIndex` |
| `SessionModel` | ListModel | `name`, `file`, `lastIndex` |
| `Screen` | Screen info | `width`, `height`, `name` |

### Installing and selecting the theme

```bash
# Install theme directory
sudo cp -r my-rice-login /usr/share/sddm/themes/

# Activate in /etc/sddm.conf.d/theme.conf
sudo mkdir -p /etc/sddm.conf.d
sudo tee /etc/sddm.conf.d/theme.conf <<'EOF'
[Theme]
Current=my-rice-login
EOF

# Test the theme without rebooting (renders it in a window)
sddm-greeter-qt6 --test-mode --theme /usr/share/sddm/themes/my-rice-login
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
