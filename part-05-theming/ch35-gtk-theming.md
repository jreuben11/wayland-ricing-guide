# Chapter 35 — GTK Theming: Adwaita, libadwaita, CSS Overrides

## Overview
Most Linux apps are GTK-based. Theming GTK correctly — without breaking apps —
requires understanding both GTK3 and GTK4's very different theming models.

## Sections

### 35.1 GTK3 vs GTK4 Theming Models
- GTK3: CSS theming, community themes work well
- GTK4 + libadwaita: Adwaita hardcoded, community themes removed
- The libadwaita controversy: GNOME's decision and its fallout
- How to handle the split world in 2025

### 35.2 GTK3 Theming
- Theme location: `~/.local/share/themes/ThemeName/gtk-3.0/gtk.css`
- Setting active theme:
  - `gsettings set org.gnome.desktop.interface gtk-theme "ThemeName"`
  - `~/.config/gtk-3.0/settings.ini`
  - GTK_THEME environment variable
- Popular GTK3 themes: Catppuccin-GTK, Gruvbox-GTK, Orchis, Gradience output

### 35.3 GTK4 and libadwaita
- GTK4 theme location: `~/.config/gtk-4.0/gtk.css`
- `adw-gtk3` theme: brings libadwaita look to GTK3 apps
- CSS variable overrides for libadwaita:
  ```css
  /* ~/.config/gtk-4.0/gtk.css */
  @define-color accent_color #89b4fa;
  @define-color window_bg_color #1e1e2e;
  @define-color headerbar_bg_color #181825;
  ```
- **Gradience**: GUI tool for generating libadwaita CSS overrides from palettes
- Gradience presets: Catppuccin, Nord, Gruvbox, etc.

### 35.4 Setting GTK Theme on Wayland
- `gsettings` vs. `dconf` vs. settings.ini
- Environment variables: `GTK_THEME=ThemeName:dark`
- `xdg-desktop-portal` and its settings interface
- Why some apps don't respect the theme (portal issues)
- `gtk-theme-name` in `settings.ini` for Wayland sessions

### 35.5 Home Manager GTK Configuration
```nix
gtk = {
    enable = true;
    theme = { name = "catppuccin-mocha-mauve-standard"; package = pkgs.catppuccin-gtk; };
    iconTheme = { name = "Papirus-Dark"; package = pkgs.papirus-icon-theme; };
    cursorTheme = { name = "Catppuccin-Mocha-Dark-Cursors"; size = 24; };
    gtk3.extraConfig = { gtk-application-prefer-dark-theme = 1; };
    gtk4.extraConfig = { gtk-application-prefer-dark-theme = 1; };
};
```

### 35.6 Dark Mode and Color Scheme
- `org.gnome.desktop.interface color-scheme 'prefer-dark'`
- `xdg-desktop-portal` settings: how apps query dark mode preference
- Portal color scheme on Hyprland: `xdg-desktop-portal-hyprland`

### 35.7 Popular GTK Theme Collections
- **Catppuccin GTK**: https://github.com/catppuccin/gtk
- **Gruvbox-GTK**: dark gruvbox theme
- **Orchis**: clean Material-ish theme
- **WhiteSur**: macOS Big Sur inspired
- **Adw-Gtk3**: makes GTK3 match GTK4/libadwaita

### 35.8 Troubleshooting GTK Theming
- App using wrong theme: check `GTK_THEME`, portal settings
- libadwaita ignoring theme: use CSS variable overrides
- Dark titlebars but light content: mixed GTK3/GTK4 issue
- `gtk-query-immodules-3.0` rebuild after theme install
