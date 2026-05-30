# Chapter 12 — labwc: The OpenBox Successor

## Contents

- [Overview](#overview)
- [12.1 Design Goals](#121-design-goals)
- [12.2 Installation and Setup](#122-installation-and-setup)
  - [Distribution packages](#distribution-packages)
  - [Building from source](#building-from-source)
  - [Starting labwc directly (TTY)](#starting-labwc-directly-tty)
  - [Session configuration for display managers](#session-configuration-for-display-managers)
  - [The autostart file](#the-autostart-file)
  - [The environment file](#the-environment-file)
- [12.3 Configuration](#123-configuration)
  - [rc.xml structure](#rcxml-structure)
  - [menu.xml](#menuxml)
- [12.4 Theming labwc](#124-theming-labwc)
  - [Installing themes](#installing-themes)
  - [GTK theme integration](#gtk-theme-integration)
  - [Qt theme integration](#qt-theme-integration)
- [12.5 Building a Complete Desktop with labwc](#125-building-a-complete-desktop-with-labwc)
  - [Component stack](#component-stack)
  - [sfwbar configuration example](#sfwbar-configuration-example)
  - [waybar configuration for labwc](#waybar-configuration-for-labwc)
  - [Full LXQt-on-Wayland setup](#full-lxqt-on-wayland-setup)
- [12.6 labwc vs. Other Stacking Compositors](#126-labwc-vs-other-stacking-compositors)
- [12.7 labwc in 2025/2026](#127-labwc-in-20252026)
  - [Feature completeness status (2025)](#feature-completeness-status-2025)
  - [LXQt project adoption](#lxqt-project-adoption)
  - [Community and distribution support](#community-and-distribution-support)
- [12.8 Troubleshooting](#128-troubleshooting)
  - [labwc fails to start on TTY](#labwc-fails-to-start-on-tty)
  - [Applications not rendering on Wayland (falling back to XWayland)](#applications-not-rendering-on-wayland-falling-back-to-xwayland)
  - [Keyboard shortcuts not working](#keyboard-shortcuts-not-working)
  - [Blank screen after labwc starts (no autostart output)](#blank-screen-after-labwc-starts-no-autostart-output)
  - [Screen tearing or poor performance](#screen-tearing-or-poor-performance)
  - [HiDPI scaling](#hidpi-scaling)

---


## Overview

labwc is a stacking Wayland compositor inspired by OpenBox, designed for traditional
floating desktop use. It is written in C, built on wlroots, and deliberately scoped
as a compositor-only tool — it supplies window management and rendering but does not
bundle a panel, systray, notification daemon, or file manager. This separation-of-concerns
philosophy mirrors OpenBox itself and makes labwc an excellent foundation for assembling
a custom, lightweight desktop on Wayland.

labwc parses a strict subset of OpenBox XML configuration, meaning users migrating from
an OpenBox session can often drop in their existing `rc.xml` and `menu.xml` files with
minimal changes. This is a deliberate design choice: rather than inventing a new config
format, labwc leverages the large body of existing OpenBox documentation and community
tooling (such as `obconf` for theme selection, though a Wayland-native equivalent is
preferred).

Because labwc is compositor-only, pairing it with a panel (e.g., `sfwbar`, `waybar`, or
`lxqt-panel`) and a session manager is mandatory for a usable desktop. This also means
labwc is highly composable — you can build anything from a minimal window manager
replacement to a full LXQt-on-Wayland session around it.

As of 2025, labwc has been officially adopted as the display backend for LXQt on Wayland,
making it a first-class project with active distribution packaging and a growing user base.
See Ch 53 for session startup integration and display manager configuration.

---

## 12.1 Design Goals

labwc's design is guided by several explicit principles that distinguish it from
feature-complete compositors like KWin or GNOME Mutter. Understanding these goals helps
set expectations and guides configuration decisions.

The core goal is **OpenBox compatibility**. labwc reads `rc.xml` and `menu.xml` in the
OpenBox XML schema, including keyboard bindings, mouse bindings, window placement rules,
and margin/snap settings. Not every OpenBox directive is implemented (the full matrix is
tracked in the upstream compatibility table at the labwc GitHub wiki), but the common
99% of desktop use cases are covered.

**Minimal runtime footprint** is the second pillar. labwc links only against wlroots,
libxkbcommon, libinput, cairo, pango, and a small number of Wayland protocol libraries.
There is no built-in scripting engine, no embedded Lua or JavaScript interpreter, and no
DBus-activated plugin system. What you configure in XML is what you get.

**Compositor-only scope** is the third and most architecturally significant goal. labwc
does not manage a taskbar, system tray, notifications, or power management. Each of these
responsibilities is delegated to external tools. This makes labwc easier to audit, debug,
and replace components around, but requires more upfront assembly than an all-in-one
compositor like GNOME or KDE Plasma.

labwc supports the following Wayland protocols relevant to ricing:

| Protocol | Purpose |
|---|---|
| `xdg-shell` | Application windows, popups, and dialogs |
| `layer-shell` (wlr-layer-shell) | Panels, overlays, desktop widgets |
| `xdg-output` | Output layout information for panels |
| `wlr-output-management` | Display configuration (resolution, rotation) |
| `xdg-decoration` | Server-side vs. client-side window decorations |
| `wlr-foreign-toplevel-management` | Taskbar window list protocol |
| `pointer-constraints` | Mouse locking for games and CAD tools |
| `relative-pointer` | Relative mouse motion |
| `xwayland` (optional) | Legacy X11 application support |

---

## 12.2 Installation and Setup

labwc is packaged in all major distributions as of 2025. Install via your system package
manager first; build from source only when you need a feature from git HEAD or a custom
patch.

### Distribution packages

```bash
# Arch Linux / Arch-based (labwc is in [community])
sudo pacman -S labwc

# Fedora 39+
sudo dnf install labwc

# Debian Bookworm / Ubuntu 24.04+
sudo apt install labwc

# openSUSE Tumbleweed
sudo zypper install labwc

# Alpine Linux
sudo apk add labwc

# NixOS — add to configuration.nix or home-manager
programs.labwc.enable = true;
```

### Building from source

```bash
# Install build dependencies (Arch example)
sudo pacman -S meson ninja wlroots libxkbcommon cairo pango \
               libinput wayland wayland-protocols xorg-xwayland

# Clone and build
git clone https://github.com/labwc/labwc.git
cd labwc
meson setup build \
  -Dxwayland=enabled \
  -Dman-pages=enabled \
  --buildtype=release
ninja -C build
sudo ninja -C build install
```

### Starting labwc directly (TTY)

The simplest way to test labwc is to launch it from a TTY:

```bash
# Launch with a status command (replaces the default swaybg)
labwc

# Pass a custom config directory
labwc -C ~/.config/labwc-testing

# Enable debug logging
labwc -d 2>~/labwc-debug.log
```

### Session configuration for display managers

To integrate with GDM, SDDM, or LightDM, install a `.desktop` session file:

```ini
# /usr/share/wayland-sessions/labwc.desktop
[Desktop Entry]
Name=labwc
Comment=Wayland stacking compositor (OpenBox-inspired)
Exec=labwc
Type=Application
DesktopNames=labwc
```

Most distribution packages install this automatically. Verify with:

```bash
ls /usr/share/wayland-sessions/
```

### The autostart file

`~/.config/labwc/autostart` is a shell script executed by labwc on startup. Unlike
OpenBox's autostart which is a list of `&`-terminated commands, labwc's autostart is a
full POSIX shell script. Use it to launch panels, set wallpaper, and start daemons.
See also Ch 53 for full session startup best practices.

```bash
# ~/.config/labwc/autostart

# Set wallpaper using swaybg
swaybg -m fill -i ~/.local/share/wallpapers/current.jpg &

# Start notification daemon
mako &

# Launch panel (sfwbar or waybar)
sfwbar &

# Polkit agent (required for GUI privilege escalation)
lxqt-policykit-agent &

# Input method framework
fcitx5 -d &

# Compositor-level screen lock daemon
swayidle -w \
  timeout 300 'swaylock -f -c 000000' \
  timeout 600 'labwc --exit || true' \
  before-sleep 'swaylock -f -c 000000' &
```

### The environment file

`~/.config/labwc/environment` is sourced before the autostart script and is the correct
place to set Wayland-specific environment variables:

```bash
# ~/.config/labwc/environment

# Force Wayland for Qt and GTK apps
QT_QPA_PLATFORM=wayland
GDK_BACKEND=wayland,x11
CLUTTER_BACKEND=wayland

# Cursor theme and size
XCURSOR_THEME=Adwaita
XCURSOR_SIZE=24

# Fix Java AWT on Wayland
_JAVA_AWT_WM_NONREPARENTING=1

# Firefox Wayland backend
MOZ_ENABLE_WAYLAND=1

# Electron apps on Wayland (Electron 22+)
ELECTRON_OZONE_PLATFORM_HINT=wayland
```

---

## 12.3 Configuration

labwc configuration lives in `~/.config/labwc/`. The four primary files are
`rc.xml`, `menu.xml`, `autostart`, and `environment`. All changes to `rc.xml` and
`menu.xml` take effect after running `labwc --reconfigure` (sends SIGHUP) or by
right-clicking the desktop and choosing "Reconfigure".

### rc.xml structure

`rc.xml` is an XML document with a root `<openbox_config>` element. It is divided into
sections: `<resistance>`, `<focus>`, `<placement>`, `<theme>`, `<desktops>`,
`<resize>`, `<applications>`, `<keyboard>`, and `<mouse>`.

A minimal functional `rc.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!-- ~/.config/labwc/rc.xml -->
<openbox_config xmlns="http://openbox.org/3.4/rc"
                xmlns:xi="http://www.w3.org/2001/XInclude">

  <resistance>
    <strength>10</strength>
    <screen_edge_strength>20</screen_edge_strength>
  </resistance>

  <focus>
    <focusNew>yes</focusNew>
    <followMouse>no</followMouse>
    <focusLast>yes</focusLast>
    <underMouse>no</underMouse>
    <focusDelay>200</focusDelay>
    <raiseOnFocus>no</raiseOnFocus>
  </focus>

  <placement>
    <policy>Smart</policy>
    <center>yes</center>
  </placement>

  <theme>
    <name>Clearlooks</name>
    <titleLayout>NLIMC</titleLayout>
    <keepBorder>yes</keepBorder>
    <animateIconify>no</animateIconify>
    <font place="ActiveWindow">
      <name>Sans</name>
      <size>10</size>
      <weight>bold</weight>
      <slant>normal</slant>
    </font>
  </theme>

  <desktops>
    <number>4</number>
    <firstdesk>1</firstdesk>
    <names>
      <name>Desktop 1</name>
      <name>Desktop 2</name>
      <name>Desktop 3</name>
      <name>Desktop 4</name>
    </names>
    <popupTime>875</popupTime>
  </desktops>

  <keyboard>
    <!-- Application launcher -->
    <keybind key="Super_L-Return">
      <action name="Execute">
        <command>alacritty</command>
      </action>
    </keybind>

    <!-- Application launcher (fuzzel) -->
    <keybind key="Super_L-d">
      <action name="Execute">
        <command>fuzzel</command>
      </action>
    </keybind>

    <!-- Close window -->
    <keybind key="Super_L-q">
      <action name="Close"/>
    </keybind>

    <!-- Virtual desktops -->
    <keybind key="Super_L-1">
      <action name="GoToDesktop"><to>1</to></action>
    </keybind>
    <keybind key="Super_L-2">
      <action name="GoToDesktop"><to>2</to></action>
    </keybind>
    <keybind key="Super_L-3">
      <action name="GoToDesktop"><to>3</to></action>
    </keybind>
    <keybind key="Super_L-4">
      <action name="GoToDesktop"><to>4</to></action>
    </keybind>

    <!-- Move window to desktop -->
    <keybind key="Super_L-Shift-1">
      <action name="SendToDesktop"><to>1</to><follow>yes</follow></action>
    </keybind>
    <keybind key="Super_L-Shift-2">
      <action name="SendToDesktop"><to>2</to><follow>yes</follow></action>
    </keybind>

    <!-- Window snapping (half-screen) -->
    <keybind key="Super_L-Left">
      <action name="SnapToEdge"><direction>left</direction></action>
    </keybind>
    <keybind key="Super_L-Right">
      <action name="SnapToEdge"><direction>right</direction></action>
    </keybind>
    <keybind key="Super_L-Up">
      <action name="Maximize"/>
    </keybind>
    <keybind key="Super_L-Down">
      <action name="Unmaximize"/>
    </keybind>

    <!-- Screenshot -->
    <keybind key="Print">
      <action name="Execute">
        <command>grim -g "$(slurp)" - | wl-copy</command>
      </action>
    </keybind>

    <!-- Screen lock -->
    <keybind key="Super_L-l">
      <action name="Execute">
        <command>swaylock -f -c 000000</command>
      </action>
    </keybind>

    <!-- Reconfigure labwc -->
    <keybind key="Super_L-F5">
      <action name="Reconfigure"/>
    </keybind>

    <!-- Exit labwc -->
    <keybind key="Super_L-Shift-e">
      <action name="Exit"/>
    </keybind>
  </keyboard>

  <mouse>
    <dragThreshold>8</dragThreshold>
    <doubleClickTime>200</doubleClickTime>
    <screenEdgeWarpTime>400</screenEdgeWarpTime>
    <screenEdgeWarpMouse>false</screenEdgeWarpMouse>

    <context name="Desktop">
      <mousebind button="Middle" action="Click">
        <action name="ShowMenu"><menu>client-list-combined-menu</menu></action>
      </mousebind>
      <mousebind button="Right" action="Click">
        <action name="ShowMenu"><menu>root-menu</menu></action>
      </mousebind>
    </context>

    <context name="Titlebar">
      <mousebind button="Left" action="Drag">
        <action name="Move"/>
      </mousebind>
      <mousebind button="Left" action="DoubleClick">
        <action name="ToggleMaximize"/>
      </mousebind>
      <mousebind button="Right" action="Click">
        <action name="ShowMenu"><menu>client-menu</menu></action>
      </mousebind>
    </context>

    <context name="Frame">
      <mousebind button="Left" action="Drag">
        <action name="Resize"/>
      </mousebind>
    </context>
  </mouse>

  <applications>
    <!-- Float certain apps regardless of their hints -->
    <application name="pavucontrol">
      <floating>yes</floating>
      <position><x>center</x><y>center</y></position>
      <size><width>700</width><height>500</height></size>
    </application>
    <application name="Gimp" type="dialog">
      <floating>yes</floating>
    </application>
    <!-- Open terminal on desktop 2 -->
    <application name="Alacritty">
      <desktop>2</desktop>
    </application>
  </applications>

</openbox_config>
```

### menu.xml

The right-click desktop menu is defined in `menu.xml`. labwc supports static and
pipe menus. Pipe menus execute a command and parse its output as additional menu XML,
enabling dynamic entries (e.g., a list of open windows or available Wi-Fi networks).

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!-- ~/.config/labwc/menu.xml -->
<openbox_menu xmlns="http://openbox.org/3.4/menu">

  <menu id="root-menu" label="Desktop Menu">
    <item label="Terminal">
      <action name="Execute"><command>alacritty</command></action>
    </item>
    <item label="Browser">
      <action name="Execute"><command>firefox</command></action>
    </item>
    <item label="Files">
      <action name="Execute"><command>pcmanfm-qt</command></action>
    </item>
    <separator/>
    <menu id="apps-submenu" label="Applications">
      <item label="Text Editor">
        <action name="Execute"><command>gedit</command></action>
      </item>
      <item label="Image Viewer">
        <action name="Execute"><command>eog</command></action>
      </item>
    </menu>
    <separator/>
    <item label="Reconfigure">
      <action name="Reconfigure"/>
    </item>
    <item label="Exit labwc">
      <action name="Exit"/>
    </item>
  </menu>

  <!-- Dynamic window list (pipe menu) -->
  <menu id="client-list-combined-menu" label="Windows"
        execute="labwc-menu-generator"/>

</openbox_menu>
```

Install `labwc-menu-generator` (part of the labwc ecosystem) to generate XDG
application menus dynamically:

```bash
sudo pacman -S labwc-menu-generator   # Arch
# or build from https://github.com/labwc/labwc-menu-generator
```

---

## 12.4 Theming labwc

labwc uses Openbox-compatible window decoration themes, meaning the large existing library
of Openbox themes works out of the box. Themes control titlebar color gradients, button
styles, border widths, and font rendering in window decorations.

### Installing themes

```bash
# System-wide Openbox themes are stored in:
ls /usr/share/themes/

# User themes go in:
mkdir -p ~/.local/share/themes/

# Install a theme pack (Arch example)
sudo pacman -S openbox-themes

# Or clone community themes:
git clone https://github.com/addy-dclxvi/openbox-theme-collections \
  ~/.local/share/themes/openbox-collections
```

Set the active theme in `rc.xml` under `<theme><name>`:

```xml
<theme>
  <name>Numix</name>
  <titleLayout>NLIMC</titleLayout>
  <font place="ActiveWindow">
    <name>Inter</name>
    <size>10</size>
    <weight>bold</weight>
  </font>
  <font place="InactiveWindow">
    <name>Inter</name>
    <size>10</size>
    <weight>normal</weight>
  </font>
  <font place="MenuItem">
    <name>Inter</name>
    <size>10</size>
    <weight>normal</weight>
  </font>
</theme>
```

The `titleLayout` string controls which buttons appear in the titlebar and in what order.
Characters and their meanings:

| Character | Button |
|---|---|
| `N` | Window icon (application icon) |
| `L` | Window label (title text) |
| `I` | Iconify (minimize) |
| `M` | Maximize/restore |
| `C` | Close |
| `S` | Shade/unshade |
| `D` | Toggle omnipresent (all-desktops) |

### GTK theme integration

Because labwc does not dictate a GTK theme, you configure it through standard GTK
settings. For GTK3, create or edit `~/.config/gtk-3.0/settings.ini`:

```ini
[Settings]
gtk-theme-name=Arc-Dark
gtk-icon-theme-name=Papirus-Dark
gtk-font-name=Inter 10
gtk-cursor-theme-name=Adwaita
gtk-cursor-theme-size=24
gtk-toolbar-style=GTK_TOOLBAR_ICONS
gtk-button-images=0
gtk-menu-images=0
gtk-enable-event-sounds=0
gtk-enable-input-feedback-sounds=0
gtk-xft-antialias=1
gtk-xft-hinting=1
gtk-xft-hintstyle=hintslight
gtk-xft-rgba=rgb
```

For GTK4 add `~/.config/gtk-4.0/settings.ini` with the same keys (minus deprecated
toolbar/button-images options). Use `gsettings` to apply changes at runtime:

```bash
gsettings set org.gnome.desktop.interface gtk-theme 'Arc-Dark'
gsettings set org.gnome.desktop.interface icon-theme 'Papirus-Dark'
gsettings set org.gnome.desktop.interface cursor-theme 'Adwaita'
gsettings set org.gnome.desktop.interface cursor-size 24
gsettings set org.gnome.desktop.interface font-name 'Inter 10'
```

### Qt theme integration

Qt applications use the `qt5ct` / `qt6ct` tools for theme configuration outside a full
KDE session:

```bash
sudo pacman -S qt5ct qt6ct kvantum

# Add to ~/.config/labwc/environment:
QT_QPA_PLATFORMTHEME=qt5ct
```

Then launch `qt5ct` and select a style (e.g., kvantum, Breeze, or Fusion). Kvantum
provides SVG-based themes for a visually consistent Qt look:

```bash
# Install a Kvantum theme
sudo pacman -S kvantum-theme-materia
kvantummanager  # GUI to select and apply the theme
```

---

## 12.5 Building a Complete Desktop with labwc

labwc's "compositor-only" scope means you need to assemble the remaining desktop
components yourself. The following is a proven, lightweight stack that delivers a full
floating desktop experience.

### Component stack

| Component | Recommended tool | Alternatives |
|---|---|---|
| Panel | `sfwbar` | `waybar`, `lxqt-panel` |
| Application launcher | `fuzzel` | `wofi`, `rofi-wayland` |
| Wallpaper | `swaybg` | `swww`, `mpvpaper` |
| Notifications | `mako` | `dunst`, `swaync` |
| File manager | `pcmanfm-qt` | `thunar`, `nemo` |
| Screen lock | `swaylock` | `gtklock` |
| Polkit agent | `lxqt-policykit-agent` | `polkit-gnome` |
| Screenshot | `grim` + `slurp` | `flameshot` |
| Clipboard manager | `cliphist` + `wl-clipboard` | `copyq` |
| Input method | `fcitx5` | `ibus` |
| Audio | `pipewire` + `wireplumber` | `pulseaudio` |

### sfwbar configuration example

`sfwbar` is a featureful, labwc-aware panel. A minimal config at
`~/.config/sfwbar/sfwbar.config`:

```
Scanner {
  PollInterval = "1000"
}

Layout {
  include "/usr/share/sfwbar/taskbar.widget"
  include "/usr/share/sfwbar/tray.widget"

  Label {
    Style = "clock"
    Value = "$(date '+%H:%M %Y-%m-%d')"
    Interval = 5000
  }
}
```

### waybar configuration for labwc

waybar works with labwc via the `wlr/taskbar` module (requires
`wlr-foreign-toplevel-management`, which labwc supports):

```json
// ~/.config/waybar/config
{
  "layer": "top",
  "position": "top",
  "height": 30,
  "modules-left": ["wlr/taskbar", "wlr/workspaces"],
  "modules-center": ["clock"],
  "modules-right": ["tray", "pulseaudio", "network", "battery"],

  "wlr/workspaces": {
    "format": "{icon}",
    "on-click": "activate",
    "format-icons": {
      "1": "1", "2": "2", "3": "3", "4": "4"
    }
  },
  "wlr/taskbar": {
    "format": "{icon}",
    "icon-size": 18,
    "on-click": "activate",
    "on-click-middle": "close"
  },
  "clock": {
    "format": "{:%H:%M  %Y-%m-%d}",
    "tooltip-format": "<big>{:%B %Y}</big>\n<tt><small>{calendar}</small></tt>"
  },
  "pulseaudio": {
    "format": "{volume}% {icon}",
    "format-muted": "muted",
    "on-click": "pavucontrol"
  }
}
```

### Full LXQt-on-Wayland setup

LXQt 2.0+ officially supports labwc as its Wayland compositor backend. The setup:

```bash
# Install full LXQt suite (Arch)
sudo pacman -S lxqt lxqt-wayland-session labwc

# Or minimal set:
sudo pacman -S lxqt-session lxqt-panel lxqt-policykit \
               pcmanfm-qt lximage-qt qterminal labwc

# Select "LXQt Wayland" at the display manager login screen, or launch:
startlxqt-wayland
```

LXQt's Wayland session script sets the correct environment variables and launches labwc
with LXQt's session manager, so `lxqt-session` handles autostart and logout.

---

## 12.6 labwc vs. Other Stacking Compositors

When evaluating labwc against alternatives, the axis of comparison is almost always
"feature richness vs. simplicity." The following table gives an honest overview.

| Feature | labwc | KWin (KDE Plasma) | GNOME Mutter | Wayfire |
|---|---|---|---|---|
| Configuration format | OpenBox XML | KConfig + KWin scripts | GNOME Settings + Extensions | INI (wayfire.ini) |
| Scripting / plugins | None built-in | KWin scripts (JS) | GNOME Shell extensions (JS) | Wayfire plugins (C++) |
| Tiling support | Edge snap only | KWin tiling plugin | GNOME tiling (limited) | Grid plugin |
| Animations | Minimal fade | Full GPU animations | Full GPU animations | Plugin-based |
| Multi-monitor | Yes | Yes | Yes | Yes |
| XWayland | Yes (optional) | Yes | Yes | Yes |
| Compositor overhead | Very low (~30MB RSS) | High (200MB+ for KWin) | High (200MB+ for Mutter) | Medium (~60MB) |
| OpenBox config compat | Yes (subset) | No | No | No |
| LXQt integration | Official | None | None | Unofficial |
| Learning curve | Low (XML) | Medium | High (extensions) | Medium |

**vs. KWin**: KWin is the right choice when you need compositing effects, a fully
integrated panel/taskbar (KDE Plasma), or KWin's powerful scripting API. labwc wins
on resource usage and simplicity. On a device with 2GB RAM, labwc leaves far more memory
for applications.

**vs. GNOME Mutter**: Mutter is not designed to run standalone. It requires the full
GNOME Shell and is only worth choosing if you want the GNOME ecosystem. labwc is a
direct replacement for users who want a traditional desktop without the integrated
shell.

**vs. Wayfire in stacking mode**: Wayfire supports a "stacking" layout through
configuration but its strength is its plugin architecture for desktop effects and
tiling. labwc has no plugin system; if you want compositing effects or grid tiling,
Wayfire is the better base. See Ch 09 for Wayfire coverage.

---

## 12.7 labwc in 2025/2026

labwc's trajectory from a personal project to an officially adopted compositor for LXQt
represents one of the more interesting developments in the Wayland compositor ecosystem.
The project has stabilized its core XML configuration format and the OpenBox compatibility
surface is considered feature-complete for the common desktop use case.

### Feature completeness status (2025)

As of labwc 0.8.x, the following key features are stable:

- Virtual desktops (multiple workspaces)
- Window snap-to-edge (half/quarter screen)
- Server-side decorations with Openbox themes
- XWayland support
- `layer-shell` for panels and overlays
- `wlr-foreign-toplevel-management` for taskbars
- Output management (multi-monitor, rotation, scaling)
- `xdg-decoration` negotiation (prefers server-side)
- `pointer-constraints` and `relative-pointer` for games

Planned or in-progress for 0.9.x / 1.0:

- Improved animation framework
- Native `labwc-config-gui` for graphical configuration
- Per-application HiDPI overrides
- Better Pipewire screen-cast integration

### LXQt project adoption

Starting with LXQt 2.1, labwc is the recommended Wayland compositor for LXQt sessions.
The `lxqt-wayland-session` package provides a fully integrated session that replaces
the X11 Openbox+LXQt combination. Distribution packagers for Fedora, openSUSE, Arch,
and Debian have all added `lxqt-wayland-session` as a result.

### Community and distribution support

labwc ships in the default repositories of Arch, Fedora, Debian Bookworm, Ubuntu 24.04,
openSUSE Tumbleweed, and Alpine. The upstream issue tracker is active and releases happen
on a roughly monthly cadence. The `#labwc` channel on Libera.Chat IRC and the GitHub
Discussions page are the primary community venues.

For users coming from X11 OpenBox sessions, the migration story is the simplest of any
Wayland compositor: copy your existing `rc.xml` and `menu.xml` into
`~/.config/labwc/`, write a simple `autostart` and `environment` file, and you have a
functionally equivalent Wayland session in under an hour.

---

## 12.8 Troubleshooting

### labwc fails to start on TTY

Check that your TTY user is in the `input` and `video` groups, as wlroots requires
direct device access for DRM/KMS:

```bash
sudo usermod -aG input,video $USER
# Log out and back in, then verify:
groups
```

If you see `DRM_IOCTL_MODE_GETRESOURCES failed`, your user lacks the necessary device
permissions. On systems using `seatd` or `logind`, verify the service is running:

```bash
systemctl status seatd
# or
systemctl status systemd-logind
```

### Applications not rendering on Wayland (falling back to XWayland)

Diagnose which backend an application is using:

```bash
# For GTK apps, check GDK_BACKEND
GDK_BACKEND=wayland app-name

# For Qt apps
QT_QPA_PLATFORM=wayland app-name

# Check if a window is XWayland:
xlsclients -l  # lists X11 clients — if the app appears here, it's using XWayland
```

Ensure `MOZ_ENABLE_WAYLAND=1` for Firefox and `ELECTRON_OZONE_PLATFORM_HINT=wayland`
for Electron apps are set in `~/.config/labwc/environment`.

### Keyboard shortcuts not working

labwc reads key names from `xkbcommon`. Verify your key names using:

```bash
wev  # Wayland event viewer — shows exact key names as labwc sees them
sudo pacman -S wev
```

Cross-reference key names against the `xkbcommon-keysyms.h` list. Common mistakes:
- `Super_L` not `Super` for the left Meta/Win key
- `Return` not `Enter`
- `ISO_Left_Tab` for Shift+Tab

### Blank screen after labwc starts (no autostart output)

If the autostart script fails silently, redirect its output:

```bash
# In ~/.config/labwc/autostart, add at the top:
exec > ~/.local/share/labwc/autostart.log 2>&1
set -x
```

Then review `~/.local/share/labwc/autostart.log` after the next login.

### Screen tearing or poor performance

labwc uses direct scanout where possible, but tearing can occur with certain GPU drivers.
Enable VRR/adaptive sync if your monitor supports it by adding to `rc.xml`:

```xml
<outputs>
  <output name="DP-1">
    <vrr>adaptive</vrr>
  </output>
</outputs>
```

For Intel graphics, ensure the `modesetting` driver is active (not `intel`):

```bash
cat /sys/kernel/debug/dri/0/i915_display_info | grep -i vblank
```

### HiDPI scaling

Set per-output scaling in `rc.xml`:

```xml
<outputs>
  <output name="DP-1">
    <scale>2</scale>
  </output>
  <output name="HDMI-A-1">
    <scale>1</scale>
  </output>
</outputs>
```

For mixed DPI (one HiDPI + one regular monitor), also set
`XCURSOR_SIZE=48` (2x the default 24) in `environment` so cursors look correct on the
HiDPI output.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
