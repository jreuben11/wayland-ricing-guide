# Chapter 36 — Qt and KDE Theming: Kvantum, qt5ct/qt6ct

## Contents

- [Overview](#overview)
- [36.1 Qt Theme Mechanisms](#361-qt-theme-mechanisms)
- [36.2 qt5ct and qt6ct](#362-qt5ct-and-qt6ct)
- [36.3 Kvantum — SVG-Based Qt Theme Engine](#363-kvantum-svg-based-qt-theme-engine)
  - [Installing Kvantum](#installing-kvantum)
  - [Kvantum Theme Locations](#kvantum-theme-locations)
  - [Kvantum Manager GUI](#kvantum-manager-gui)
  - [Popular Kvantum Themes](#popular-kvantum-themes)
  - [Writing a Custom Kvantum Theme](#writing-a-custom-kvantum-theme)
- [36.4 Environment Variables for Qt on Wayland](#364-environment-variables-for-qt-on-wayland)
  - [Hyprland](#hyprland)
  - [Sway](#sway)
  - [Shell Profile (Fallback)](#shell-profile-fallback)
- [36.5 Breeze for Non-KDE Setups](#365-breeze-for-non-kde-setups)
- [36.6 Home Manager Qt Configuration](#366-home-manager-qt-configuration)
- [36.7 Fonts for Qt and GTK](#367-fonts-for-qt-and-gtk)
  - [Installing Fonts](#installing-fonts)
  - [Fontconfig Configuration](#fontconfig-configuration)
  - [DPI Configuration](#dpi-configuration)
- [36.8 Consistent Look Across GTK and Qt](#368-consistent-look-across-gtk-and-qt)
- [Troubleshooting](#troubleshooting)
  - [Qt apps ignore QT_QPA_PLATFORMTHEME](#qt-apps-ignore-qtqpaplatformtheme)
  - [Kvantum theme not visible / Fusion style shown](#kvantum-theme-not-visible-fusion-style-shown)
  - [Qt apps crash or show blank windows on Wayland](#qt-apps-crash-or-show-blank-windows-on-wayland)
  - [Font rendering differs between Qt and GTK](#font-rendering-differs-between-qt-and-gtk)
  - [Kvantum compositor effects (blur/transparency) not working](#kvantum-compositor-effects-blurtransparency-not-working)
  - [qt5ct/qt6ct GUI won't launch](#qt5ctqt6ct-gui-wont-launch)

---


## Overview

Qt applications require a completely separate theming pipeline from GTK applications. While GTK apps respond to `~/.config/gtk-3.0/gtk.css` and related files, Qt uses its own style engine, platform theme plugins, and configuration format. On a non-KDE Wayland compositor such as Hyprland, Sway, or River, there is no KDE Plasma session running to push Qt theming defaults — so every Qt application will render with bare-bones Fusion style unless you configure the stack manually.

The canonical approach for non-KDE setups is: **qt5ct / qt6ct** as the platform theme manager (which replaces what KDE's session would normally provide), and **Kvantum** as the style engine (which uses SVG-defined widget shapes for full visual customization). Together these two components give you the same level of control over Qt apps that GTK's CSS gives you over GTK apps, and with some coordination effort you can achieve a unified look across both toolkits.

This chapter covers Qt's theming architecture, the qt5ct/qt6ct configuration tool, the Kvantum theme engine in depth (including custom theme authoring), environment variables required to activate everything under Wayland, font configuration for both toolkits, and strategies for keeping GTK and Qt visually consistent. For automated cross-toolkit theming via Nix, see Ch 40 (Stylix). For session startup and environment variable injection, see Ch 53.

---

## 36.1 Qt Theme Mechanisms

Qt's rendering pipeline is composed of several distinct layers, and understanding where each layer applies is essential for effective theming. At the lowest level, a **Qt Style** (also called a QStyle plugin) controls how individual widgets are drawn: button shapes, scroll bar geometry, combo box arrows, and similar primitives. Qt ships with built-in styles including `Fusion` (the cross-platform default), `Windows` (Windows-like), and on KDE systems `Breeze`. Each style can be overridden at runtime via the `QT_STYLE_OVERRIDE` environment variable, though styles also set programmatically in an application take precedence.

Above the style layer sits the **Platform Theme** plugin. Platform themes are responsible for higher-level defaults that span the whole application: default fonts, color palettes, icon themes, file dialog backends, and menu behavior. On KDE Plasma, the `kde` platform theme plugin is active and reads settings from KDE's configuration store (`~/.config/kdeglobals`). On GNOME-based systems, the `gtk3` or `gnome` platform theme plugin tries to match Qt to GTK settings. On bare Wayland compositors without a desktop environment, no useful platform theme is active by default, which is why `qt5ct` / `qt6ct` exist — they provide a platform theme that reads from their own config files.

The `QT_QPA_PLATFORMTHEME` environment variable selects the active platform theme plugin. Setting it to `qt5ct` causes Qt 5 applications to read from `~/.config/qt5ct/qt5ct.conf`; setting it to `qt6ct` causes Qt 6 applications to read from `~/.config/qt6ct/qt6ct.conf`. If this variable is unset, Qt falls back to built-in defaults which are usually the bare `Fusion` style with no icon theme and system default fonts.

The third layer is the **Wayland QPA (Qt Platform Abstraction)** backend itself, selected by `QT_QPA_PLATFORM=wayland`. This controls how Qt creates windows, handles input, and integrates with the compositor. On XWayland-hybrid setups you may see `QT_QPA_PLATFORM=wayland;xcb` to allow fallback to XWayland for apps that do not support native Wayland. The Wayland QPA also handles client-side decorations (CSD) — `QT_WAYLAND_DISABLE_WINDOWDECORATION=1` tells Qt to not draw its own title bars and borders, relying on the compositor's server-side decorations (SSD) if available.

| Environment Variable | Effect |
|---|---|
| `QT_QPA_PLATFORM` | Selects windowing backend (wayland, xcb, offscreen) |
| `QT_QPA_PLATFORMTHEME` | Selects platform theme plugin (qt5ct, qt6ct, kde, gnome) |
| `QT_STYLE_OVERRIDE` | Forces a specific QStyle plugin (kvantum, Fusion, Breeze) |
| `QT_WAYLAND_DISABLE_WINDOWDECORATION` | Suppress Qt CSD title bars (1 = disable) |
| `QT_AUTO_SCREEN_SCALE_FACTOR` | Enable automatic DPI scaling from display metadata |
| `QT_SCALE_FACTOR` | Manual global DPI scale multiplier (e.g. 1.5 for 150%) |
| `QT_SCREEN_SCALE_FACTORS` | Per-monitor scale (e.g. `eDP-1=1.5;DP-1=1.0`) |
| `QT_FONT_DPI` | Override font DPI independently of scale factor |

---

## 36.2 qt5ct and qt6ct

`qt5ct` and `qt6ct` are platform theme plugins that ship as separate packages from Qt itself. Their purpose is to give users running non-KDE, non-GNOME desktops a GUI tool for configuring Qt theming. Without them, a user on Hyprland has no way to set a consistent icon theme, color palette, or font for Qt apps without patching environment variables or writing code.

To install on common distributions:

```bash
# Arch Linux / Manjaro
sudo pacman -S qt5ct qt6ct

# Fedora
sudo dnf install qt5ct qt6ct

# Debian / Ubuntu (qt6ct may be in newer releases only)
sudo apt install qt5ct qt6ct

# openSUSE
sudo zypper install qt5ct qt6ct
```

After installation, activate the platform theme by setting the environment variable before any Qt application starts. The correct place for this is your compositor's environment configuration or your shell profile sourced early in session startup (see Ch 53 for session env injection):

```bash
# Hyprland: ~/.config/hypr/hyprland.conf or a sourced env file
env = QT_QPA_PLATFORMTHEME,qt5ct
# For Qt6 applications use qt6ct:
env = QT_QPA_PLATFORMTHEME,qt6ct
```

Because `qt5ct` and `qt6ct` are separate plugins and Qt 5 vs Qt 6 applications each only read their own config, you need both variables set if you run a mix of Qt 5 and Qt 6 applications. However, many users find it sufficient to set only `qt6ct` as most active development has shifted to Qt 6. Check which version an application uses with `ldd /usr/bin/app_name | grep -E 'libQt[56]'`.

Launch the configuration GUI:

```bash
qt5ct    # Configure Qt5 apps
qt6ct    # Configure Qt6 apps
```

The GUI has tabs for Style (selects the QStyle plugin), Color Palette (define or load palettes), Fonts (UI font and fixed-width font), Interface (icon theme, cursor, and dialog behavior), and Style Sheets (raw Qt CSS injected into all Qt5/6 apps). Configuration is written to `~/.config/qt5ct/qt5ct.conf` and `~/.config/qt6ct/qt6ct.conf`.

A typical `qt5ct.conf` after configuring Kvantum + Papirus icons:

```ini
[Appearance]
color_scheme_path=
custom_palette=false
icon_theme=Papirus-Dark
standard_dialogs=default
style=kvantum-dark

[Fonts]
fixed="JetBrains Mono,10,-1,5,50,0,0,0,0,0"
general="Inter,10,-1,5,50,0,0,0,0,0"

[Interface]
activate_item_on_single_click=1
buttonbox_layout=0
cursor_flash_time=1000
dialog_buttons_have_icons=1
double_click_interval=400
gui_effects=@Invalid()
keyboard_scheme=2
menus_have_icons=true
show_shortcuts_in_context_menus=true
stylesheets=@Invalid()
toolbutton_style=4
underline_shortcut=1
wheel_scroll_lines=3

[SettingsWindow]
geometry=@ByteArray(...)
```

The `style=kvantum-dark` entry under `[Appearance]` tells qt5ct to activate the `kvantum-dark` QStyle plugin, which is the dark-mode variant of Kvantum. Similarly, `style=kvantum` activates the light variant. Note: you still need `QT_STYLE_OVERRIDE=kvantum` set at the environment level for apps that do not respect the platform theme's style suggestion — some Qt apps hardcode their style.

---

## 36.3 Kvantum — SVG-Based Qt Theme Engine

Kvantum is a Qt style engine that replaces Qt's built-in widget rendering with SVG-defined shapes. Every widget — buttons, scroll bars, check boxes, tab bars, combo boxes, progress bars, sliders — has its appearance defined in an SVG file alongside an INI configuration file. This gives Kvantum themes the same expressive power as CSS for web browsers: you can define rounded corners, gradients, blur effects, opacity, and complex geometric shapes without writing any C++ code.

### Installing Kvantum

```bash
# Arch Linux
sudo pacman -S kvantum

# Fedora
sudo dnf install kvantum

# Debian / Ubuntu
sudo apt install qt5-style-kvantum qt5-style-kvantum-themes

# openSUSE
sudo zypper install kvantum-manager

# NixOS (system or home-manager)
environment.systemPackages = [ pkgs.libsForQt5.qtstyleplugin-kvantum ];
# or
home.packages = [ pkgs.libsForQt5.qtstyleplugin-kvantum pkgs.kdePackages.qtstyleplugin-kvantum ];
```

### Kvantum Theme Locations

Kvantum looks for themes in these directories, in order of precedence:

```
~/.config/Kvantum/                   # User-local themes (highest priority)
~/.local/share/Kvantum/              # Alternate user location
/usr/share/Kvantum/                  # System-wide themes
/usr/local/share/Kvantum/            # Locally-installed themes
```

Each theme occupies a subdirectory whose name is the theme name. Inside that directory there must be at minimum a `ThemeName.kvconfig` (INI) file and a `ThemeName.svg` file:

```
~/.config/Kvantum/
└── MyTheme/
    ├── MyTheme.kvconfig
    └── MyTheme.svg
```

### Kvantum Manager GUI

`kvantummanager` provides a GUI for selecting the active theme and previewing it live. Launch it as:

```bash
kvantummanager
```

The "Change/Delete Theme" tab lists all installed themes. Select one and click "Use this theme." The active theme is stored in `~/.config/Kvantum/kvantum.kvconfig`:

```ini
[General]
theme=CatppuccinMochaLavender
```

The "Configure Active Theme" tab exposes per-theme overrides: you can adjust opacity, blur radius, menu shadow, and composite settings without touching the SVG.

### Popular Kvantum Themes

| Theme | Style | Source |
|---|---|---|
| Catppuccin-Kvantum | Mocha/Macchiato/Frappé/Latte | github.com/catppuccin/Kvantum |
| Gruvbox-Kvantum | Gruvbox Dark/Light variants | github.com/theglitchh/kvantum-gruvbox |
| Nordic-Kvantum | Nord-inspired blue-grey | github.com/EliverLara/Nordic |
| Orchid | Purple/translucent modern | included in kvantum package |
| Materia | Material Design flat | github.com/nana-4/materia-theme |
| KvGnome | GNOME-like flat | included in kvantum package |
| Dracula | Dracula palette | github.com/dracula/kvantum |
| TokyoNight | Tokyo Night dark | github.com/Luwx/Luwx-kvantum |

Installing a community theme from a tarball or git repo:

```bash
# Clone Catppuccin Kvantum theme
git clone https://github.com/catppuccin/Kvantum.git /tmp/catppuccin-kvantum

# Copy desired flavour to user Kvantum directory
mkdir -p ~/.config/Kvantum
cp -r /tmp/catppuccin-kvantum/themes/Catppuccin-Mocha-Lavender \
      ~/.config/Kvantum/

# Activate via kvantummanager or directly
cat > ~/.config/Kvantum/kvantum.kvconfig << 'EOF'
[General]
theme=Catppuccin-Mocha-Lavender
EOF
```

### Writing a Custom Kvantum Theme

A Kvantum theme consists of two files. The `.kvconfig` file is an INI file that sets colors, sizes, opacity, and which SVG element IDs map to which widget parts. The `.svg` file contains the actual vector art that Kvantum renders for each widget state.

Minimal `.kvconfig` skeleton:

```ini
[%General]
author=YourName
comment=A minimal custom theme
x11drag=true
alt_mnemonic=true
left_tabs=false
attach_inactive_tabs=false
composite=true
menu_shadow_depth=6
spread_menuitems=false
tooltip_shadow_depth=3
scroll_width=8
scroll_arrows=false
scroll_min_extent=36
transient_scrollbar=true
center_toolbar_handle=true
slim_toolbars=true
toolbutton_style=0
menuitem_separator_height=3
menu_separator_height=5

[GeneralColors]
window.color=#1e1e2e
base.color=#181825
alt.base.color=#1e1e2e
button.color=#313244
light.color=#45475a
mid.light.color=#585b70
mid.color=#45475a
dark.color=#313244
text.color=#cdd6f4
window.text.color=#cdd6f4
button.text.color=#cdd6f4
disabled.text.color=#585b70
tooltip.base.color=#181825
tooltip.text.color=#cdd6f4
highlight.color=#89b4fa
highlighted.text.color=#1e1e2e
link.color=#89dceb
link.visited.color=#cba6f7

[Hacks]
transparent_dolphin_view=false
blur_konsole=true
transparent_ktitle_label=true
transparent_menutitle=true
respect_darkness=true
```

The `.svg` file uses specific element IDs that Kvantum recognizes. Each widget type has a naming convention: `pushbutton`, `pushbutton-normal`, `pushbutton-focused`, `pushbutton-pressed`, `pushbutton-toggled`, etc. A minimal button definition in SVG:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="30">
  <!-- Normal state button -->
  <rect id="pushbutton-normal-top"   x="0" y="0" width="4" height="4"
        rx="4" fill="#313244"/>
  <rect id="pushbutton-normal-bottom" x="0" y="26" width="4" height="4"
        rx="4" fill="#313244"/>
  <rect id="pushbutton-normal-left"  x="0" y="4" width="4" height="22"
        fill="#313244"/>
  <rect id="pushbutton-normal-right" x="96" y="4" width="4" height="22"
        fill="#313244"/>
  <rect id="pushbutton-normal-center" x="4" y="4" width="92" height="22"
        fill="#313244"/>

  <!-- Focused state -->
  <rect id="pushbutton-focused-center" x="4" y="4" width="92" height="22"
        fill="#45475a"/>
  <rect id="pushbutton-focused-top"   x="0" y="0" width="4" height="4"
        rx="4" fill="#89b4fa"/>
</svg>
```

In practice, complete Kvantum SVGs are hundreds of elements long. Study an existing theme (Orchid or KvGnome, which ship with Kvantum) as a starting template and modify colors and shapes incrementally.

---

## 36.4 Environment Variables for Qt on Wayland

All Qt environment variables must be set before any Qt application process is spawned. The exact mechanism for injecting them depends on your compositor and session management setup. Below is a complete reference configuration for Hyprland, followed by equivalents for Sway and generic shell profiles.

### Hyprland

```bash
# ~/.config/hypr/hyprland.conf (or sourced via source = ~/.config/hypr/env.conf)

# Wayland backend with XCB fallback
env = QT_QPA_PLATFORM,wayland;xcb

# Platform theme: use qt6ct for Qt6 apps
env = QT_QPA_PLATFORMTHEME,qt6ct

# Force Kvantum style engine
env = QT_STYLE_OVERRIDE,kvantum

# Disable Qt client-side decorations (compositor handles SSD)
env = QT_WAYLAND_DISABLE_WINDOWDECORATION,1

# HiDPI: auto-scale from monitor metadata
env = QT_AUTO_SCREEN_SCALE_FACTOR,1

# If auto-scale is off, set explicit factor (e.g. for 2x HiDPI)
# env = QT_SCALE_FACTOR,2

# Accessibility: cursor theme matching your GTK cursor theme
env = XCURSOR_THEME,Bibata-Modern-Classic
env = XCURSOR_SIZE,24
```

### Sway

```bash
# ~/.config/sway/config

set $qt_env \
    QT_QPA_PLATFORM=wayland \
    QT_QPA_PLATFORMTHEME=qt5ct \
    QT_STYLE_OVERRIDE=kvantum \
    QT_WAYLAND_DISABLE_WINDOWDECORATION=1 \
    QT_AUTO_SCREEN_SCALE_FACTOR=1

exec --no-startup-id env $qt_env dbus-update-activation-environment --all
```

Or use `~/.config/environment.d/` (systemd-based session):

```ini
# ~/.config/environment.d/qt.conf
QT_QPA_PLATFORM=wayland;xcb
QT_QPA_PLATFORMTHEME=qt6ct
QT_STYLE_OVERRIDE=kvantum
QT_WAYLAND_DISABLE_WINDOWDECORATION=1
QT_AUTO_SCREEN_SCALE_FACTOR=1
```

Files in `~/.config/environment.d/` are read by `systemd --user` and exported into the user session environment before any user services start, making them visible to all D-Bus-activated applications.

### Shell Profile (Fallback)

```bash
# ~/.bash_profile or ~/.zprofile (sourced in login sessions)
export QT_QPA_PLATFORM=wayland
export QT_QPA_PLATFORMTHEME=qt5ct
export QT_STYLE_OVERRIDE=kvantum
export QT_WAYLAND_DISABLE_WINDOWDECORATION=1
export QT_AUTO_SCREEN_SCALE_FACTOR=1
```

Note: shell profiles are only sourced for login shells. Applications launched by the compositor directly (not through a terminal) may not see these variables unless you use `environment.d` or the compositor's `env` directive.

---

## 36.5 Breeze for Non-KDE Setups

KDE's Breeze style is not exclusive to Plasma. It is available as a standalone Qt style plugin and can be used on any Wayland compositor. Breeze provides a polished, modern look with good HiDPI support and is actively maintained by the KDE community.

```bash
# Arch Linux
sudo pacman -S breeze breeze-gtk breeze-icons

# Fedora
sudo dnf install breeze-icon-theme breeze-gtk-theme plasma-breeze

# Debian / Ubuntu
sudo apt install breeze qt5-style-plugin-breeze
```

Breeze ships two color schemes: `Breeze` (light) and `Breeze Dark`. These are stored as `~/.local/share/color-schemes/*.colors` files. You can use them with qt5ct/qt6ct by selecting the color scheme in the GUI's "Color Palette" tab or by pointing `color_scheme_path` in `qt5ct.conf` to the `.colors` file:

```ini
[Appearance]
color_scheme_path=/usr/share/color-schemes/BreezeDark.colors
custom_palette=true
style=Breeze
```

The Breeze icon theme supports both GTK and Qt applications via the `hicolor` and `breeze` icon theme specs. Set it in qt5ct/qt6ct and separately in `~/.config/gtk-3.0/settings.ini`:

```ini
# ~/.config/gtk-3.0/settings.ini
[Settings]
gtk-icon-theme-name=breeze-dark
gtk-cursor-theme-name=breeze_cursors
gtk-cursor-theme-size=24
```

Using Breeze without Plasma means you lose KDE's live theming D-Bus calls, so theme changes require restarting applications. This is a known limitation of running KDE components outside a Plasma session. For live reloading, Stylix (Ch 40) provides an alternative approach through Nix rebuilds.

---

## 36.6 Home Manager Qt Configuration

NixOS users with Home Manager can declaratively configure the entire Qt theming stack. Home Manager's `qt` module manages `qt5ct`/`qt6ct` config generation, installs Kvantum, and injects the required environment variables into the user session.

```nix
# ~/.config/home-manager/home.nix (or modules/qt.nix)

{ pkgs, ... }:
{
  qt = {
    enable = true;

    # Use qtct as the platform theme (generates qt5ct.conf and qt6ct.conf)
    platformTheme.name = "qtct";

    # Set Kvantum as the style engine
    style = {
      name = "kvantum";
      package = pkgs.kdePackages.qtstyleplugin-kvantum;
    };
  };

  # Install Catppuccin Kvantum theme
  home.packages = with pkgs; [
    catppuccin-kvantum
    qt5ct
    qt6ct
    libsForQt5.qtstyleplugin-kvantum
    kdePackages.qtstyleplugin-kvantum
    papirus-icon-theme
  ];

  # Write the Kvantum theme selection config
  xdg.configFile."Kvantum/kvantum.kvconfig".text = ''
    [General]
    theme=Catppuccin-Mocha-Lavender
  '';

  # qt5ct config with Papirus icons and JetBrains Mono font
  xdg.configFile."qt5ct/qt5ct.conf".text = ''
    [Appearance]
    icon_theme=Papirus-Dark
    style=kvantum-dark

    [Fonts]
    fixed="JetBrains Mono,10,-1,5,50,0,0,0,0,0"
    general="Inter,10,-1,5,50,0,0,0,0,0"

    [Interface]
    menus_have_icons=true
    toolbutton_style=4
  '';

  # Same for qt6ct
  xdg.configFile."qt6ct/qt6ct.conf".source =
    config.xdg.configFile."qt5ct/qt5ct.conf".source;

  # Session environment
  home.sessionVariables = {
    QT_QPA_PLATFORM = "wayland;xcb";
    QT_QPA_PLATFORMTHEME = "qt6ct";
    QT_STYLE_OVERRIDE = "kvantum";
    QT_WAYLAND_DISABLE_WINDOWDECORATION = "1";
    QT_AUTO_SCREEN_SCALE_FACTOR = "1";
  };
}
```

After applying with `home-manager switch`, all Qt environment variables are exported through `~/.nix-profile/etc/profile.d/hm-session-vars.sh` which is sourced by login shells. For Wayland compositors started by a display manager, ensure the display manager sources login shell profiles or that `~/.config/environment.d/` is populated — Home Manager can also write to that directory via `home.sessionVariablesPackage`.

For Stylix-based fully automated theming (shared palette applied to Qt, GTK, terminal, shell prompt, etc.), see Ch 40. Stylix generates Kvantum themes automatically from a base16/base24 color scheme.

---

## 36.7 Fonts for Qt and GTK

Font configuration on Linux is handled by fontconfig, which is used by both Qt and GTK for font discovery, fallback chains, hinting, antialiasing, and subpixel rendering. Qt also has its own font rendering pipeline on top of fontconfig, and the interaction between the two can produce subtle differences in rendered text between Qt and GTK apps.

### Installing Fonts

```bash
# User font directory (no root required)
mkdir -p ~/.local/share/fonts

# Example: install JetBrains Mono Nerd Font
cd /tmp
wget https://github.com/ryanoasis/nerd-fonts/releases/latest/download/JetBrainsMono.zip
unzip JetBrainsMono.zip -d ~/.local/share/fonts/JetBrainsMono/

# Example: install Inter
wget https://github.com/rsms/inter/releases/latest/download/Inter-4.0.zip
unzip Inter-4.0.zip -d ~/.local/share/fonts/Inter/

# Rebuild font cache
fc-cache -fv

# Verify font is found
fc-list | grep -i "JetBrains"
fc-match "JetBrains Mono"
```

### Fontconfig Configuration

The main user fontconfig file lives at `~/.config/fontconfig/fonts.conf`. A well-tuned config for modern LCD displays:

For a complete, annotated fontconfig template see Ch 87 §87.9. The Qt-relevant family preferences are:

```xml
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>

  <!-- Qt UI font preferences -->
  <alias>
    <family>sans-serif</family>
    <prefer>
      <family>Inter</family>
      <family>Noto Sans</family>
    </prefer>
  </alias>

  <alias>
    <family>serif</family>
    <prefer>
      <family>Noto Serif</family>
      <family>DejaVu Serif</family>
    </prefer>
  </alias>

  <alias>
    <family>monospace</family>
    <prefer>
      <family>JetBrains Mono</family>
      <family>Noto Sans Mono</family>
    </prefer>
  </alias>

</fontconfig>
```

After editing `fonts.conf`, rebuild the cache: `fc-cache -fv`. Test rendering with `fc-query` and `pango-view` (for GTK) or write a small Qt test app.

### DPI Configuration

High-DPI displays require consistent DPI configuration across fontconfig, Xft, Qt, and GTK to avoid mixed-resolution rendering artifacts:

```bash
# Xresources (for XWayland compatibility)
echo "Xft.dpi: 192" >> ~/.Xresources
xrdb -merge ~/.Xresources

# Qt: set font DPI explicitly if auto-scaling produces wrong sizes
export QT_FONT_DPI=192

# GTK: uses fontconfig which uses Xresources or GNOME settings
# For non-GNOME, set gsettings:
gsettings set org.gnome.desktop.interface text-scaling-factor 1.5
```

| Hint Style | Effect |
|---|---|
| `hintnone` | No hinting — best for HiDPI (>200dpi effective) |
| `hintslight` | Minimal hinting — good compromise for ~1.5–2x HiDPI |
| `hintmedium` | Moderate — traditional LCD tuning |
| `hintfull` | Maximum hinting — crisp at 1x DPI but distorts shapes |

---

## 36.8 Consistent Look Across GTK and Qt

Getting GTK and Qt applications to look visually identical is the central challenge of desktop ricing on mixed-toolkit environments. The toolkit authors use different rendering engines, different color role names, and different style APIs, so true 1:1 pixel-identical rendering is not possible — but close visual harmony is achievable.

The most important shared element is the **color palette**. Define your palette once in a canonical format (a base16 YAML, a Catppuccin flavor, or a custom JSON), then derive GTK CSS colors and Kvantum `[GeneralColors]` entries from the same source values. If you are doing this manually:

```bash
# Example: extract hex values from a Catppuccin Mocha palette
BASE=1e1e2e   # Background
SURFACE=313244 # Surface0
OVERLAY=45475a # Overlay0
TEXT=cdd6f4   # Text
BLUE=89b4fa   # Blue (accent/highlight)
MAUVE=cba6f7  # Mauve (secondary accent)
```

Apply `BASE` to both GTK's `@theme_bg_color` and Kvantum's `window.color`. Apply `BLUE` to both GTK's `@theme_selected_bg_color` and Kvantum's `highlight.color`. The visual result will not be pixel-identical but will share the same emotional tone and color relationships.

**Icon themes** must support both GTK and Qt. The icon theme spec (freedesktop.org) is shared between toolkits, so themes like Papirus, Numix, or Breeze work for both. Install and set consistently:

```bash
# Install Papirus icons
sudo pacman -S papirus-icon-theme   # Arch
sudo apt install papirus-icon-theme  # Debian/Ubuntu

# Set for GTK
gsettings set org.gnome.desktop.interface icon-theme 'Papirus-Dark'
# or edit ~/.config/gtk-3.0/settings.ini:
# gtk-icon-theme-name=Papirus-Dark

# Set for Qt in qt5ct/qt6ct GUI or directly in config:
# icon_theme=Papirus-Dark  (in [Appearance] section of qt5ct.conf)
```

**Cursor themes** are also shared via the `XCURSOR_THEME` environment variable and `~/.config/gtk-3.0/settings.ini`. Set both:

```bash
export XCURSOR_THEME=Bibata-Modern-Classic
export XCURSOR_SIZE=24

# GTK
echo "gtk-cursor-theme-name=Bibata-Modern-Classic" >> ~/.config/gtk-3.0/settings.ini
echo "gtk-cursor-theme-size=24" >> ~/.config/gtk-3.0/settings.ini

# Hyprland (for compositor-level cursor)
# cursor {
#   theme = Bibata-Modern-Classic
#   size = 24
# }
```

For automated cross-toolkit theming, **Stylix** (Ch 40) generates coordinated GTK CSS, Kvantum SVGs/configs, Alacritty colors, shell prompt themes, and more from a single Nix-managed color scheme. This is the most maintainable approach for NixOS users. For non-NixOS users, **Gradience** (formerly Adwaita Manager) can export palettes to GTK CSS and has community scripts for generating Kvantum configs from the same palette.

---

## Troubleshooting

### Qt apps ignore QT_QPA_PLATFORMTHEME

Verify the variable is actually in the environment when the app starts:

```bash
# Launch app with env explicitly set
QT_QPA_PLATFORMTHEME=qt5ct QT_STYLE_OVERRIDE=kvantum dolphin

# Check if the variable is in your session environment
env | grep QT

# If using systemd user session, ensure variables are exported there
systemctl --user show-environment | grep QT
# If missing, import them:
systemctl --user import-environment QT_QPA_PLATFORMTHEME QT_STYLE_OVERRIDE
```

Some apps launched via `.desktop` files through a D-Bus activation path bypass shell environment. Use `~/.config/environment.d/qt.conf` to ensure variables reach all systemd-user-activated processes.

### Kvantum theme not visible / Fusion style shown

If apps show Fusion instead of Kvantum despite `QT_STYLE_OVERRIDE=kvantum`:

```bash
# Check Kvantum plugin is installed and found
ls /usr/lib/qt/plugins/styles/libkvantum*
ls /usr/lib/x86_64-linux-gnu/qt5/plugins/styles/libkvantum*

# Test explicitly
QT_STYLE_OVERRIDE=kvantum kvantummanager

# If Kvantum plugin is missing for Qt6
find /usr -name "*kvantum*" -name "*qt6*" 2>/dev/null

# Arch: ensure both Qt5 and Qt6 Kvantum packages are installed
sudo pacman -S kvantum kvantum-qt5
```

Also check that `~/.config/Kvantum/kvantum.kvconfig` exists and contains a valid `theme=` entry pointing to an installed theme.

### Qt apps crash or show blank windows on Wayland

```bash
# Test with XCB fallback
QT_QPA_PLATFORM=xcb app_name

# Enable Wayland debug logging
QT_LOGGING_RULES="qt.qpa.wayland*=true" app_name 2>&1 | head -50

# Check XDG_RUNTIME_DIR is set (required for Wayland socket)
echo $XDG_RUNTIME_DIR
ls $XDG_RUNTIME_DIR/wayland-*

# For apps that don't support native Wayland, force XWayland
QT_QPA_PLATFORM=xcb app_name
```

### Font rendering differs between Qt and GTK

```bash
# Check what fontconfig returns for a family
fc-match "Inter"
fc-match "Inter:weight=bold"

# Check DPI being used
xdpyinfo | grep resolution   # X11/XWayland DPI
# Qt reads Xft.dpi from Xresources, check:
xrdb -query | grep dpi

# Force consistent DPI
export QT_FONT_DPI=96
export GDK_DPI_SCALE=1.0
```

If Qt fonts appear larger than GTK fonts at the same nominal size, the DPI values are mismatched. Set `QT_FONT_DPI` to match the value reported by `xdpyinfo` or the value set in `Xft.dpi`.

### Kvantum compositor effects (blur/transparency) not working

Kvantum's compositor effects (translucent menus, blurred backgrounds) require a Wayland compositor with blur support. On Hyprland:

```ini
# ~/.config/hypr/hyprland.conf
decoration {
    blur {
        enabled = true
        size = 8
        passes = 3
        new_optimizations = true
    }
    rounding = 8
}
```

Also ensure Kvantum's "Composite Effects" checkbox is enabled in `kvantummanager`. Check that the active theme's `.kvconfig` has `composite=true` in its `[%General]` section.

### qt5ct/qt6ct GUI won't launch

```bash
# Ensure the platformtheme variable is NOT set to qt5ct when launching qt5ct itself
# (it can cause a recursive loop on some versions)
env -u QT_QPA_PLATFORMTHEME qt5ct

# Or use a different platform:
QT_QPA_PLATFORM=xcb qt5ct
```

---

*See also: Ch 35 (GTK theming and gtk.css), Ch 37 (icon, cursor, and font themes), Ch 40 (Stylix automated theming), Ch 53 (session startup and environment injection)*

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
