# Chapter 40 — Stylix: Auto-Theming Everything from One Wallpaper

## Overview
Stylix is a NixOS/Home Manager module that generates and applies a consistent
color theme across your entire system from a single wallpaper or palette choice.

## Sections

### 40.1 What Stylix Does
- Takes: a wallpaper image OR a base16 scheme
- Produces: consistent theming for 50+ applications
- Applies to: terminals, editor, bar, GTK, Qt, browser, fonts, cursor, notifications

### 40.2 Installation
```nix
# flake.nix
inputs.stylix.url = "github:nix-community/stylix";

# In your NixOS/HM config:
imports = [ stylix.homeModules.stylix ];
```

### 40.3 Basic Configuration
```nix
stylix = {
    enable = true;
    image = ./wallpaper.jpg;      # source of truth for colors
    base16Scheme = "${pkgs.base16-schemes}/share/themes/catppuccin-mocha.yaml";
    # OR: let Stylix extract from image (default)

    fonts = {
        monospace = { package = pkgs.nerdfonts; name = "JetBrainsMono Nerd Font Mono"; };
        sansSerif = { package = pkgs.inter; name = "Inter"; };
        sizes.terminal = 12;
        sizes.applications = 11;
    };

    cursor = { package = pkgs.catppuccin-cursors.mochaDark; name = "catppuccin-mocha-dark-cursors"; };

    opacity = { terminal = 0.95; desktop = 1.0; };
};
```

### 40.4 Supported Applications (Partial List)
- **Terminals**: kitty, alacritty, foot, wezterm, ghostty
- **Editors**: neovim, helix, vscode (theme extension), emacs
- **Bars**: waybar (auto-generates CSS), (Quickshell: manual via colors)
- **Shells**: fish, bash, zsh (prompt colors)
- **GTK**: generates GTK3/GTK4 theme
- **Qt**: Kvantum theme generation
- **Browser**: Firefox, Chromium (via themes)
- **Notifications**: dunst, mako (auto-configures colors)
- **Login**: greetd, sddm
- **Games**: steam theme
- **Document viewer**: zathura
- Full list: https://stylix.danth.me/options/

### 40.5 Qt and GTK via Stylix
```nix
stylix.targets.gtk.enable = true;
stylix.targets.qt.enable = true;
# Stylix generates Kvantum theme for Qt
# Stylix generates GTK CSS for GTK4
```

### 40.6 Disabling Stylix for Specific Apps
```nix
stylix.targets.neovim.enable = false;  # manage nvim theme separately
stylix.targets.vscode.enable = false;  # use vscode marketplace theme
```

### 40.7 Custom Templates
- Stylix uses mustache-like templates
- Add a custom target for an unsupported app:
```nix
home.file.".config/myapp/colors.conf".text = ''
    background = ${config.lib.stylix.colors.base00}
    foreground = ${config.lib.stylix.colors.base05}
    accent = ${config.lib.stylix.colors.base0D}
'';
```

### 40.8 Polarity and Variants
- `stylix.polarity = "dark"` or `"light"` or `"either"`
- Base16 colors mapped to semantic roles
- Light vs. dark mode: different base16 schemes

### 40.9 Stylix + Quickshell Integration
- Stylix doesn't have a Quickshell target yet (2025)
- Workaround: generate a QML color file via `home.file`:
```nix
home.file.".config/quickshell/theme/colors_generated.qml".text = ''
    pragma Singleton
    import Quickshell
    Singleton {
        property color base00: "${config.lib.stylix.colors.withHashtag.base00}"
        property color accent: "${config.lib.stylix.colors.withHashtag.base0D}"
        // ...all 16 base colors
    }
'';
```

### 40.10 Workflow: From Wallpaper to Complete Rice
1. Drop a wallpaper in `~/wallpapers/`
2. Update `stylix.image = ./wallpapers/new.jpg` in flake
3. `home-manager switch` or `nixos-rebuild switch`
4. Every themed app updates automatically
5. No manual color matching needed
