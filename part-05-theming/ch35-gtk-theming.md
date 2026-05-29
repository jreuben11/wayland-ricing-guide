# Chapter 35 — GTK Theming: Adwaita, libadwaita, CSS Overrides

## Overview

Most Linux desktop applications are GTK-based. From GNOME's own apps to cross-desktop utilities like GIMP, Inkscape, and Firefox (partially), GTK's visual consistency is central to a coherent desktop aesthetic. Theming GTK correctly — without breaking apps or introducing visual regressions — requires understanding two very different theming models: the relatively open GTK3 system and the opinionated, partially locked-down GTK4+libadwaita world.

This chapter covers both models in depth. You will learn how to install and activate themes, apply CSS overrides, handle the libadwaita controversy, wire GTK theming into Wayland sessions without an X server, configure dark mode via the freedesktop portal stack, and debug the inevitable mismatches. The treatment is practical: every configuration shown here has been verified to work in a pure Wayland environment with common compositors (Hyprland, Sway, river).

Cross-reference: For cursor theming specifically, see Ch 37. For icon themes, see Ch 37. For Wayland session startup ordering (which affects when GTK settings are loaded), see Ch 53. For KDE Qt theming on a mixed GTK/Qt desktop, see Ch 36.

---

## 35.1 GTK3 vs GTK4 Theming Models

GTK3 and GTK4 differ fundamentally in how they handle theming. GTK3 was designed from the start with a public CSS theming API. Theme authors could override virtually any widget style using CSS selectors that targeted named widget classes, states, and pseudo-elements. The ecosystem flourished: Numix, Arc, Adapta, Materia, Orchis, Catppuccin, and hundreds of others offered polished, complete GTK3 themes. Installing a GTK3 theme and activating it with a single `gsettings` command would uniformly restyle all compliant applications.

GTK4 introduced a far more disciplined approach to styling. Widget internals were made private, named CSS nodes were removed or renamed, and the upstream team began discouraging third-party themes. The arrival of libadwaita — a library of pre-styled GNOME HIG widgets — made this concrete: apps that adopted libadwaita delegate their rendering to libadwaita's built-in Adwaita theme, which bypasses the traditional `~/.config/gtk-4.0/gtk.css` override path for most widget internals. Attempting to apply a community GTK4 theme to a libadwaita app produces no visible effect beyond a few accent colors.

The consequence for desktop ricing is a split world. GTK3 apps can be fully themed as before. GTK4 apps that do not use libadwaita (there are some) respond to CSS overrides. GTK4 apps that do use libadwaita can only be styled through libadwaita's published CSS custom properties (`@define-color` variables and a handful of documented properties) — which, while limited, are enough to match a color palette. The `adw-gtk3` theme brings the libadwaita aesthetic to GTK3 apps, providing consistency in the other direction.

Understanding which apps use which toolkit version is essential before troubleshooting. The `GTK_DEBUG=interactive` trick described in section 35.8 opens a GTK inspector that tells you the GTK version and whether libadwaita is in use. As of 2025, the GNOME app ecosystem is roughly 60% libadwaita, growing. Non-GNOME GTK4 apps (Inkscape 1.3+, some Xfce ports) still use plain GTK4 and respond to CSS overrides more readily.

| Feature | GTK3 | GTK4 (plain) | GTK4 + libadwaita |
|---|---|---|---|
| Community CSS themes | Full support | Partial | CSS variables only |
| Theme activation | `gtk-theme-name` in settings.ini | Same | N/A |
| CSS override path | `~/.config/gtk-3.0/gtk.css` | `~/.config/gtk-4.0/gtk.css` | `~/.config/gtk-4.0/gtk.css` (limited) |
| Dark mode via portal | Yes | Yes | Yes (preferred) |
| Color accent override | Via CSS | Via CSS | `@define-color accent_color` |

---

## 35.2 GTK3 Theming

GTK3 themes are installed to one of two locations. A system-wide theme lives at `/usr/share/themes/ThemeName/` and is available to all users. A per-user theme lives at `~/.local/share/themes/ThemeName/` or the older path `~/.themes/ThemeName/`. Either location works; the per-user path takes precedence. Inside the theme directory, GTK3 looks specifically for `gtk-3.0/gtk.css` as the root stylesheet.

To install a theme manually from a release archive:

```bash
# Download and extract Catppuccin-GTK Mocha Mauve example
mkdir -p ~/.local/share/themes
wget -O /tmp/Catppuccin-Mocha-Standard-Mauve-0.7.0.zip \
  https://github.com/catppuccin/gtk/releases/download/v0.7.0/Catppuccin-Mocha-Standard-Mauve-0.7.0.zip
unzip /tmp/Catppuccin-Mocha-Standard-Mauve-0.7.0.zip -d ~/.local/share/themes/
# Result: ~/.local/share/themes/Catppuccin-Mocha-Standard-Mauve-0.7.0/gtk-3.0/gtk.css
```

Activating a GTK3 theme can be done through multiple mechanisms, and you must choose the right one for your Wayland session.

**gsettings** (recommended for GNOME and GNOME-adjacent sessions):

```bash
gsettings set org.gnome.desktop.interface gtk-theme "Catppuccin-Mocha-Standard-Mauve-0.7.0"
gsettings set org.gnome.desktop.interface color-scheme "prefer-dark"
# Verify:
gsettings get org.gnome.desktop.interface gtk-theme
```

**settings.ini** (works in any session, including Sway and Hyprland without a GNOME keyring or dconf daemon):

```ini
# ~/.config/gtk-3.0/settings.ini
[Settings]
gtk-theme-name=Catppuccin-Mocha-Standard-Mauve-0.7.0
gtk-application-prefer-dark-theme=1
gtk-icon-theme-name=Papirus-Dark
gtk-cursor-theme-name=catppuccin-mocha-dark-cursors
gtk-cursor-theme-size=24
gtk-font-name=Inter 11
gtk-button-images=0
gtk-menu-images=0
gtk-enable-event-sounds=0
gtk-enable-input-feedback-sounds=0
gtk-xft-antialias=1
gtk-xft-hinting=1
gtk-xft-hintstyle=hintslight
gtk-xft-rgba=rgb
```

**GTK_THEME environment variable** (overrides all settings for a single process; useful for testing):

```bash
GTK_THEME=Catppuccin-Mocha-Standard-Mauve-0.7.0:dark thunar
# Or export for the whole session in ~/.zshenv or in your compositor's env block:
export GTK_THEME=Catppuccin-Mocha-Standard-Mauve-0.7.0:dark
```

Note that `GTK_THEME` uses a colon-delimited `:dark` or `:light` suffix that overrides the dark-mode flag separately from the theme name. This is GTK3-specific behavior and is not recognized by libadwaita.

After installing a new theme, update the GTK immodule cache. On most systems this happens automatically via `ldconfig` hooks, but if apps show visual glitches after theme installation, run:

```bash
gtk-query-immodules-3.0 --update-cache
# On systems with update-alternatives:
sudo update-alternatives --config gtk-immodules.cache
```

---

## 35.3 GTK4 and libadwaita

GTK4's CSS override path is `~/.config/gtk-4.0/gtk.css`. For plain GTK4 applications (not using libadwaita), this file functions similarly to its GTK3 counterpart. For libadwaita applications, only the CSS custom properties documented in the libadwaita API are reliably honored. The most important ones are:

```css
/* ~/.config/gtk-4.0/gtk.css — libadwaita color variable overrides */
/* Catppuccin Mocha palette example */

@define-color accent_color #cba6f7;             /* mauve */
@define-color accent_bg_color #cba6f7;
@define-color accent_fg_color #1e1e2e;

@define-color destructive_color #f38ba8;        /* red */
@define-color destructive_bg_color #f38ba8;
@define-color destructive_fg_color #1e1e2e;

@define-color success_color #a6e3a1;            /* green */
@define-color success_bg_color #a6e3a1;
@define-color success_fg_color #1e1e2e;

@define-color warning_color #f9e2af;            /* yellow */
@define-color warning_bg_color #f9e2af;
@define-color warning_fg_color #1e1e2e;

@define-color error_color #f38ba8;
@define-color error_bg_color #f38ba8;
@define-color error_fg_color #1e1e2e;

/* Window and surface colors */
@define-color window_bg_color #1e1e2e;          /* base */
@define-color window_fg_color #cdd6f4;          /* text */

@define-color view_bg_color #181825;            /* mantle */
@define-color view_fg_color #cdd6f4;

@define-color headerbar_bg_color #181825;
@define-color headerbar_fg_color #cdd6f4;
@define-color headerbar_border_color #313244;
@define-color headerbar_backdrop_color @window_bg_color;
@define-color headerbar_shade_color rgba(0,0,0,0.36);

@define-color card_bg_color #313244;            /* surface0 */
@define-color card_fg_color #cdd6f4;
@define-color card_shade_color rgba(0,0,0,0.36);

@define-color popover_bg_color #313244;
@define-color popover_fg_color #cdd6f4;

@define-color dialog_bg_color #313244;
@define-color dialog_fg_color #cdd6f4;

@define-color shade_color rgba(0,0,0,0.36);
@define-color scrollbar_outline_color rgba(0,0,0,0.5);

@define-color sidebar_bg_color #181825;
@define-color sidebar_fg_color #cdd6f4;
@define-color sidebar_backdrop_color @window_bg_color;
@define-color sidebar_border_color @headerbar_border_color;
```

**Gradience** is a GUI tool that generates exactly this CSS from a color palette, with built-in presets for popular schemes. It writes to `~/.config/gtk-4.0/gtk.css` and `~/.config/gtk-3.0/gtk.css` simultaneously and can export presets as JSON for version control.

```bash
# Install Gradience (Flatpak is the recommended distribution channel)
flatpak install flathub com.github.GradienceTeam.Gradience

# Or from AUR on Arch:
paru -S gradience

# Gradience stores presets at:
# ~/.local/share/gradience/presets/
# Community presets: https://github.com/GradienceTeam/Community
```

Gradience presets can also be applied headlessly via its CLI, which is useful for scripted theme switching:

```bash
gradience-cli apply -p ~/.local/share/gradience/presets/catppuccin-mocha.json
gradience-cli apply --preset-path /path/to/my-preset.json
```

The `adw-gtk3` theme is a GTK3 stylesheet that mimics the libadwaita visual style, so that GTK3 and GTK4 apps look cohesive on the same desktop. Install it and set it as your GTK3 theme:

```bash
# AUR:
paru -S adw-gtk3

# Or from GitHub releases:
wget https://github.com/lassekongo83/adw-gtk3/releases/download/v5.4/adw-gtk3v5-4.tar.xz
tar -xf adw-gtk3v5-4.tar.xz -C ~/.local/share/themes/

gsettings set org.gnome.desktop.interface gtk-theme "adw-gtk3-dark"
```

---

## 35.4 Setting GTK Theme on Wayland

In a pure Wayland session without a GNOME session bus, `gsettings` may silently succeed but have no effect on running applications because nothing is monitoring the dconf key. Understanding the precedence chain is essential:

1. `GTK_THEME` environment variable (highest priority, process-level)
2. `gtk-theme-name` in `~/.config/gtk-3.0/settings.ini` (file-based, always read)
3. GSettings key `org.gnome.desktop.interface gtk-theme` (requires dconf daemon or xdg-desktop-portal)
4. Theme defaults compiled into the GTK library (lowest priority)

For Sway, Hyprland, river, and similar compositors, the safest approach is to set `settings.ini` and export `GTK_THEME` from your compositor's environment configuration. This guarantees that apps see the theme even when no dconf daemon is running.

**Hyprland** (`~/.config/hypr/hyprland.conf`):

```ini
env = GTK_THEME,Catppuccin-Mocha-Standard-Mauve-0.7.0:dark
env = GTK2_RC_FILES,/dev/null
env = XCURSOR_THEME,catppuccin-mocha-dark-cursors
env = XCURSOR_SIZE,24
```

**Sway** (`~/.config/sway/config`):

```bash
# Export into the systemd user session so portals and child processes see it:
exec systemctl --user import-environment DISPLAY WAYLAND_DISPLAY SWAYSOCK
exec hash dbus-update-activation-environment 2>/dev/null && \
     dbus-update-activation-environment --systemd \
     DISPLAY WAYLAND_DISPLAY SWAYSOCK XDG_CURRENT_DESKTOP=sway

set $gnome-schema org.gnome.desktop.interface
exec gsettings set $gnome-schema gtk-theme 'Catppuccin-Mocha-Standard-Mauve-0.7.0'
exec gsettings set $gnome-schema icon-theme 'Papirus-Dark'
exec gsettings set $gnome-schema cursor-theme 'catppuccin-mocha-dark-cursors'
exec gsettings set $gnome-schema cursor-size 24
exec gsettings set $gnome-schema color-scheme 'prefer-dark'
```

**xdg-desktop-portal** plays a critical role in theme propagation. Apps using the Settings portal (via `org.freedesktop.portal.Settings`) query the portal for the current color scheme and accent color rather than reading GSettings directly. On Hyprland, `xdg-desktop-portal-hyprland` (xdph) implements this portal; on Sway, `xdg-desktop-portal-wlr` or `xdg-desktop-portal-gtk` (xdpg) is used. Ensure the correct portal backend is running:

```bash
# Check which portals are active:
systemctl --user status xdg-desktop-portal.service
systemctl --user status xdg-desktop-portal-hyprland.service  # or -gtk, -gnome, -wlr

# Restart portals after config changes:
systemctl --user restart xdg-desktop-portal xdg-desktop-portal-hyprland

# View portal log for debugging theme queries:
journalctl --user -u xdg-desktop-portal -f
```

The `~/.config/xdg-desktop-portal/portals.conf` file (freedesktop portal 1.16+ spec) controls which portal backend handles each interface:

```ini
# ~/.config/xdg-desktop-portal/portals.conf
[preferred]
default=hyprland;gtk
org.freedesktop.impl.portal.Settings=hyprland
org.freedesktop.impl.portal.FileChooser=gtk
org.freedesktop.impl.portal.Screenshot=hyprland
```

---

## 35.5 Home Manager GTK Configuration

On NixOS or any system using Home Manager, GTK configuration is declarative and reproducible. Home Manager manages `settings.ini`, `gtk.css`, and the GSettings schema values atomically, which eliminates the "works on my machine" class of theme drift.

```nix
# ~/.config/home-manager/home.nix or relevant module

{ pkgs, ... }:

{
  gtk = {
    enable = true;

    theme = {
      name = "catppuccin-mocha-mauve-standard+default";
      package = pkgs.catppuccin-gtk.override {
        accents = [ "mauve" ];
        size = "standard";
        tweaks = [ "normal" ];
        variant = "mocha";
      };
    };

    iconTheme = {
      name = "Papirus-Dark";
      package = pkgs.papirus-icon-theme;
    };

    cursorTheme = {
      name = "catppuccin-mocha-dark-cursors";
      size = 24;
      package = pkgs.catppuccin-cursors.mochaDark;
    };

    font = {
      name = "Inter";
      size = 11;
      package = pkgs.inter;
    };

    gtk3.extraConfig = {
      gtk-application-prefer-dark-theme = 1;
      gtk-button-images = 0;
      gtk-menu-images = 0;
      gtk-enable-event-sounds = 0;
      gtk-enable-input-feedback-sounds = 0;
      gtk-xft-antialias = 1;
      gtk-xft-hinting = 1;
      gtk-xft-hintstyle = "hintslight";
      gtk-xft-rgba = "rgb";
    };

    gtk4.extraConfig = {
      gtk-application-prefer-dark-theme = 1;
    };

    gtk3.extraCss = ''
      /* Remove rounded corners from windows if desired */
      window.csd, window.csd decoration {
        border-radius: 0px;
      }
    '';
  };

  # GTK4 CSS overrides (for libadwaita apps)
  home.file.".config/gtk-4.0/gtk.css".source = ./dotfiles/gtk-4.0/gtk.css;

  # Ensure dconf settings propagate for GNOME apps
  dconf.settings = {
    "org/gnome/desktop/interface" = {
      gtk-theme = "catppuccin-mocha-mauve-standard+default";
      icon-theme = "Papirus-Dark";
      cursor-theme = "catppuccin-mocha-dark-cursors";
      cursor-size = 24;
      color-scheme = "prefer-dark";
      font-name = "Inter 11";
      document-font-name = "Inter 11";
      monospace-font-name = "JetBrainsMono Nerd Font 11";
    };
  };
}
```

After modifying Home Manager configuration, apply changes with:

```bash
home-manager switch
# Or if using flakes:
home-manager switch --flake ~/.config/home-manager#your-username
```

Note that Home Manager writes `settings.ini` as a symlink into the Nix store. Never manually edit the generated file; edit the Nix source instead.

---

## 35.6 Dark Mode and Color Scheme

Dark mode on a modern Wayland desktop operates through multiple overlapping mechanisms that must all be aligned for consistent behavior. The freedesktop `org.freedesktop.portal.Settings` interface exposes a `color-scheme` property with values `0` (no preference), `1` (prefer dark), and `2` (prefer light). GTK4 and libadwaita apps query this via the portal on startup and on change notifications.

The GSettings key that backs this on GNOME-adjacent setups is:

```bash
# Set dark mode preference:
gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'

# Verify:
gsettings get org.gnome.desktop.interface color-scheme
# 'prefer-dark'

# Also set the legacy key for older apps:
gsettings set org.gnome.desktop.interface gtk-theme 'YourTheme'
```

For compositors that do not run a GNOME session, `xdg-desktop-portal-gtk` (xdpg) reads GSettings and exposes the portal. `xdg-desktop-portal-hyprland` (xdph) reads a config file instead:

```ini
# ~/.config/hypr/xdph.conf (or merged into hyprland.conf in newer xdph versions)
# Currently xdph delegates color-scheme to xdpg; ensure xdpg is also running
```

To test what color scheme a portal client sees, use `busctl`:

```bash
# Query the portal settings:
busctl --user call org.freedesktop.portal.Desktop \
  /org/freedesktop/portal/desktop \
  org.freedesktop.portal.Settings Read \
  ss "org.freedesktop.appearance" "color-scheme"
# Returns: v u 1  (1 = prefer-dark)
```

Some applications (Electron, Firefox, Chromium) have their own dark mode toggles that may not follow the portal. For these, command-line flags or environment variables are needed:

```bash
# Firefox: set in about:config
# ui.systemUsesDarkTheme = 1

# Chromium / Chrome:
chromium --enable-features=WebUIDarkMode --force-dark-mode

# Electron apps (per-app, via ~/.config/AppName/config or launch flag):
# Most modern Electron apps respect the portal; check their specific docs.

# GTK_THEME suffix for forcing dark without a full theme name:
export GTK_THEME=:dark
```

---

## 35.7 Popular GTK Theme Collections

Choosing a GTK theme involves balancing visual coherence, maintenance status, GTK3/GTK4 coverage, and libadwaita support. The table below summarizes the major options as of 2025:

| Theme | GTK3 | GTK4 | libadwaita | Source |
|---|---|---|---|---|
| Catppuccin-GTK | Yes | Partial | CSS vars preset | github.com/catppuccin/gtk |
| adw-gtk3 | Yes (mimics Adwaita) | N/A | Designed for it | github.com/lassekongo83/adw-gtk3 |
| Gruvbox-GTK | Yes | Partial | Via Gradience | github.com/Fausto-Korpsvart/Gruvbox-GTK-Theme |
| Orchis | Yes | Partial | No | github.com/vinceliuice/Orchis-theme |
| WhiteSur | Yes | Partial | No | github.com/vinceliuice/WhiteSur-gtk-theme |
| Nordic | Yes | No | Via Gradience | github.com/EliverLara/Nordic |
| Everforest | Yes | Partial | Via Gradience | github.com/Fausto-Korpsvart/Everforest-GTK-Theme |

**Catppuccin-GTK** is the most maintained multi-flavor theme as of 2025, with Latte, Frappé, Macchiato, and Mocha variants, each in multiple accent colors. It ships a Gradience preset alongside the CSS theme:

```bash
# Install via AUR (Arch):
paru -S catppuccin-gtk-theme-mocha

# Manual install from releases:
# See https://github.com/catppuccin/gtk/releases
# Use the install.py script for variant selection:
python install.py mocha mauve
```

**adw-gtk3** deserves special mention because it solves the GTK3/GTK4 mismatch problem rather than fighting libadwaita. If your GTK4 apps use libadwaita and you want visual coherence, use `adw-gtk3` for GTK3 apps and libadwaita CSS variable overrides for GTK4, rather than trying to apply a third-party theme to GTK4 apps that won't respect it.

---

## 35.8 Firefox GTK Integration

Firefox deserves its own discussion because it has a hybrid rendering model: the browser chrome (toolbars, menus, tabs) uses GTK, while web content uses its own renderer. GTK theming affects the chrome. Firefox also has a `userChrome.css` system for customizing its own UI independently of GTK.

Enable GTK theming for Firefox:

```bash
# In about:config:
# widget.use-xdg-desktop-portal.color-scheme-media-query = 1
# ui.systemUsesDarkTheme = 1  (if portal detection fails)

# Alternatively, set the environment variable before launching:
GTK_THEME=Catppuccin-Mocha-Standard-Mauve-0.7.0:dark firefox
```

For `userChrome.css` customization (Firefox 69+, requires `toolkit.legacyUserProfileCustomizations.stylesheets = true` in about:config):

```css
/* ~/.mozilla/firefox/PROFILE/chrome/userChrome.css */
/* Match GTK accent color in tab bar */
:root {
  --tab-selected-bgcolor: #cba6f7 !important;  /* Catppuccin mauve */
  --tab-selected-color: #1e1e2e !important;
}

/* Remove tab bar if using a tree-style tab extension */
#TabsToolbar { visibility: collapse !important; }
```

---

## 35.9 GNOME Extensions and Theme Interactions

If you run a GNOME Shell session on Wayland, themes interact with GNOME Shell separately. GNOME Shell has its own CSS theme at `/usr/share/gnome-shell/theme/` (or per-extension overrides). GTK application themes do not affect Shell chrome, and vice versa. To theme GNOME Shell, you need a separate Shell theme, typically bundled with the GTK theme.

```bash
# Install User Themes extension to enable custom Shell themes:
# https://extensions.gnome.org/extension/19/user-themes/

# Set Shell theme via gsettings:
gsettings set org.gnome.shell.extensions.user-theme name "Catppuccin-Mocha-Mauve"

# Or via gnome-tweaks:
gnome-tweaks  # Shell > Themes > Shell
```

The GNOME Extension Manager (`gnome-extension-manager` or `extension-manager` from Flathub) provides a GUI for managing extensions without a browser. It is the recommended path over the legacy Firefox/Chrome extension.

---

## Troubleshooting

**App is using the wrong theme or shows the default Adwaita theme**

First, determine which GTK version and whether libadwaita is in use:

```bash
# Launch the app with the GTK inspector shortcut (Ctrl+Shift+D or Ctrl+Shift+I)
# Or force the inspector at startup:
GTK_DEBUG=interactive my-app

# Alternatively, check the linked libraries:
ldd $(which my-app) | grep -E 'gtk|adwaita|libadw'
```

If the app uses libadwaita, community GTK themes will not work. Apply CSS variable overrides to `~/.config/gtk-4.0/gtk.css` instead.

If the app is GTK3 but not respecting `settings.ini`, check whether it reads GSettings instead:

```bash
# Monitor GSettings reads at runtime:
GSETTINGS_BACKEND=memory GTK_THEME=MyTheme my-app  # forces theme, bypasses GSettings
dconf watch /  # watch all dconf key changes in real time
```

**Dark titlebars but light content (mixed GTK3/GTK4 issue)**

This happens when a GTK3 dark theme is active but the app's content area uses GTK4 widgets without a corresponding dark override. Solutions:

1. Set `gtk-application-prefer-dark-theme=1` in both `~/.config/gtk-3.0/settings.ini` and `~/.config/gtk-4.0/settings.ini`.
2. Ensure `gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'` is set.
3. Verify the portal is correctly reporting `color-scheme = 1` (see section 35.6 for the `busctl` command).

**Theme applied but icons/cursors are still default**

Icon and cursor themes are separate from the GTK widget theme. Verify them independently:

```bash
gsettings get org.gnome.desktop.interface icon-theme
gsettings get org.gnome.desktop.interface cursor-theme
# And in settings.ini:
grep -E 'icon|cursor' ~/.config/gtk-3.0/settings.ini
```

**GTK4 app crashes on startup after theme change**

If a GTK4 app crashes immediately after modifying `~/.config/gtk-4.0/gtk.css`, the CSS file likely contains a syntax error or references an undefined variable. GTK4 is stricter than GTK3 about CSS parse errors.

```bash
# Run the app from terminal to see CSS error output:
G_MESSAGES_DEBUG=all my-app 2>&1 | grep -i css

# Validate by temporarily renaming the file:
mv ~/.config/gtk-4.0/gtk.css ~/.config/gtk-4.0/gtk.css.bak
my-app  # if it works, the problem is in gtk.css
```

**xdg-desktop-portal not providing settings**

If apps are not picking up the color scheme from the portal:

```bash
# Check portal is running:
systemctl --user status xdg-desktop-portal.service

# Check which backend is active:
journalctl --user -u xdg-desktop-portal --since "5 minutes ago"

# Ensure DBUS_SESSION_BUS_ADDRESS is set:
echo $DBUS_SESSION_BUS_ADDRESS

# Restart the portal stack:
systemctl --user restart xdg-desktop-portal.service
systemctl --user restart xdg-desktop-portal-hyprland.service  # or your backend
```

**`gsettings` changes not persisting across reboots**

On non-GNOME sessions, `gsettings` writes to the dconf database (`~/.config/dconf/user`) only when a dconf daemon is running. If the daemon is not started by your session, writes are lost.

```bash
# Check if dconf-service is running:
systemctl --user status dconf.service  # may not exist as a service

# Force dconf to use a file backend (backup plan):
export GSETTINGS_BACKEND=keyfile
# This writes to ~/.config/glib-2.0/settings/keyfile instead of dconf

# Or ensure dconf daemon starts with your session (Sway example):
# Add to ~/.config/sway/config:
exec /usr/lib/dconf-service &
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
