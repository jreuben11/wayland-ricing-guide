# Chapter 39 — Nix and Home Manager: Reproducible Rices

## Overview
NixOS and Home Manager turn a rice from a collection of dotfiles into a
reproducible, version-controlled system declaration. One config to rule all apps.

## Sections

### 39.1 Why Nix for Ricing
- Declarative: describe the desired state, Nix produces it
- Reproducible: same config → same result on any machine
- Rollback: previous generations preserved
- Multi-user: separate home environments per user
- No config drift: "works on my machine" becomes "works everywhere"

### 39.2 Home Manager Overview
- `programs.X` modules for hundreds of apps
- `services.X` for background daemons
- `wayland.windowManager.hyprland` / `.sway` modules
- `gtk`, `qt`, `fonts`, `icons`, `cursor` unified config

### 39.3 Flake-Based Setup
```nix
# flake.nix
{
    inputs = {
        nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
        home-manager = {
            url = "github:nix-community/home-manager";
            inputs.nixpkgs.follows = "nixpkgs";
        };
        hyprland.url = "github:hyprwm/Hyprland";
        quickshell.url = "git+https://git.outfoxxed.me/quickshell/quickshell";
    };
}
```

### 39.4 Compositor Configuration in Nix
```nix
# Hyprland
wayland.windowManager.hyprland = {
    enable = true;
    settings = {
        general = { gaps_in = 5; gaps_out = 10; };
        decoration = { rounding = 10; blur.enabled = true; };
        animations.enabled = true;
    };
    extraConfig = ''
        source = ~/.config/hypr/colors.conf
    '';
};
```

### 39.5 Quickshell in Home Manager
- No official HM module yet (2025): use `home.file` to symlink configs
- `home.packages = [ pkgs.quickshell ];`
- Config managed as QML source files in the Nix store
- Linking to `~/.config/quickshell/`

### 39.6 Terminal and Shell Configuration
```nix
programs.kitty = {
    enable = true;
    theme = "Catppuccin-Mocha";
    font.name = "JetBrainsMono Nerd Font";
    font.size = 12;
    settings = { background_opacity = "0.95"; };
};

programs.starship = {
    enable = true;
    settings = { add_newline = false; character.success_symbol = "[❯](bold green)"; };
};
```

### 39.7 Managing Dotfiles with Nix
- `home.file."path" = { source = ./dotfile; }`: static files
- `home.file."path" = { text = "..."; }`: inline content
- `programs.X.extraConfig`: append arbitrary config
- Template generation with `pkgs.writeText` or `pkgs.writeTextFile`

### 39.8 NixOS System-Level vs. Home Manager
- System-level: hardware, kernel, display manager, system services
- Home Manager: per-user apps, dotfiles, environment
- The hybrid: NixOS module installs Hyprland, HM configures it

### 39.9 Sharing Rices as Flakes
- Publish your rice as a Nix flake
- Others can use: `nix run github:you/dotfiles`
- Community: r/unixporn flake-based dotfiles
- Template: https://github.com/Misterio77/nix-starter-configs

### 39.10 Pitfalls
- Mutable state: files outside Nix store aren't managed
- Secrets: don't put passwords in the Nix store (use sops-nix, agenix)
- First-time setup: Nix learning curve is real
- Build times: large closures take time on first build
