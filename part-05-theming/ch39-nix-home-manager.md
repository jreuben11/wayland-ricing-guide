# Chapter 39 — Nix and Home Manager: Reproducible Rices

## Overview

NixOS and Home Manager transform a rice from a fragile collection of dotfiles into a reproducible, version-controlled system declaration. Where traditional ricing means copying configs between machines and hoping nothing drifts, a Nix-based rice is a pure function: the same inputs always produce the same desktop environment. This chapter covers the full stack — flake structure, Home Manager modules for Wayland compositors, theming through `gtk`/`qt`/`cursor` attributes, secrets management, and sharing your rice with the community.

The Nix approach addresses the three core ricing pain points: reproducibility (deploy the same environment on a new machine in minutes), rollback (broken update? `home-manager generations` shows every previous state, `home-manager rollback` restores it), and sharability (publish a flake, anyone can `nix run` your exact setup). These aren't theoretical — seasoned ricers on r/unixporn increasingly share flake-based dotfiles precisely because they work reliably for others.

This chapter assumes familiarity with basic Nix syntax (attribute sets, `let`/`in`, `with`) and that you have either NixOS or Nix installed on another distro. If you're on a non-NixOS distro, the standalone Home Manager path works fine — every code example here targets that scenario unless explicitly noted. See Chapter 40 for NixOS-specific system configuration and Chapter 53 for session startup integration.

---

## 39.1 Why Nix for Ricing

The traditional dotfile approach accumulates entropy. A symlink farm managed by `stow` or `chezmoi` tracks files but not packages — you still need to install `hyprland`, `waybar`, `foot`, and thirty other tools before the symlinks are meaningful. Nix solves this by declaring both the packages and their configuration in a single language. Activate a new profile with `home-manager switch` and every package is installed at exactly the version your config pins, every dotfile is written, every service is started.

Reproducibility in Nix is enforced by the store model. Every package is built in a sandbox with no network access and a fixed set of inputs, then stored under a content-addressed path like `/nix/store/3j9w4k2...-hyprland-0.47.0/`. Two machines running the same flake lock file reference identical store paths. This is not best-effort reproducibility — it's a property of the build system.

Rollback is a first-class feature. Home Manager creates a new "generation" on every successful `switch`. If a font change breaks your terminal or a config option was removed upstream, you revert with a single command. The old generation's store paths are still present (until garbage collection) so the rollback is instantaneous. Compare this to git-based dotfiles: you'd need to re-install packages at the old versions, which is nontrivial.

Nix also enables per-project or per-user environment isolation that dovetails with ricing. You can have a minimal "work" profile and a full-featured "home" profile as separate Home Manager configurations, switching between them with `nix profile`. Secrets — wallpapers with embedded EXIF, API keys in waybar scripts — can be managed with `sops-nix` or `agenix` without ever storing sensitive data in the Nix store (covered in section 39.10).

**Key advantages summary:**

| Concern | Traditional dotfiles | Nix + Home Manager |
|---|---|---|
| Package management | Manual / separate | Declarative, same file |
| Config drift | Accumulates silently | Impossible (pure builds) |
| New machine setup | Hours | Minutes (`home-manager switch`) |
| Rollback | `git checkout` + reinstall | `home-manager rollback` |
| Sharing | "Works on my machine" | `nix run github:you/dots` |
| Secrets | Plaintext in repo | sops-nix / agenix |

---

## 39.2 Home Manager Overview

Home Manager is a Nix library that exposes hundreds of `programs.*` and `services.*` modules — one per application — and aggregates their outputs into a single activation script. When you set `programs.kitty.enable = true;`, Home Manager writes `~/.config/kitty/kitty.conf` with values derived from the other attributes you set. You never manually edit that file again; the source of truth is your Nix config.

The module tree relevant to Wayland ricing breaks down into three layers. The **compositor layer** includes `wayland.windowManager.hyprland`, `wayland.windowManager.sway`, and (via overlays) `wayland.windowManager.niri`. These modules write the compositor's config file and can start it as a systemd user service. The **theming layer** covers `gtk.theme`, `gtk.iconTheme`, `gtk.cursorTheme`, `qt.style`, and `home.pointerCursor` — a unified place to set the Catppuccin Mocha theme for every GTK and Qt application simultaneously. The **application layer** is the bulk of Home Manager: terminals (`foot`, `kitty`, `alacritty`, `wezterm`), shells (`bash`, `zsh`, `fish`, `nushell`), status bars (`programs.waybar`), launchers, notification daemons, and so on.

For applications without an official module (Quickshell, as of mid-2025, is the prominent example), Home Manager provides escape hatches: `home.file` for static files, `home.activation` for imperative post-switch scripts, and `systemd.user.services` for custom services. Nothing is off-limits — if an application can be configured with a file, you can manage it.

Home Manager can be used in three deployment modes. **Standalone** (any distro): install Nix, run `nix-channel --add` or use the flake-based setup, run `home-manager switch`. **NixOS module**: add `home-manager.nixosModules.home-manager` to your `nixosConfigurations` and manage your user's home from within the system config. **nix-darwin module**: same pattern on macOS. This chapter focuses on standalone and NixOS module usage.

---

## 39.3 Flake-Based Setup

Flakes are the modern Nix project format. They pin all inputs in `flake.lock` (equivalent to a lockfile in cargo or npm), making builds hermetic. For a rice, the flake declares where to fetch nixpkgs, home-manager, and any community overlays (hyprland, quickshell, anyrun, etc.).

```nix
# flake.nix — full starter for a Wayland rice
{
  description = "Personal Wayland rice — NixOS + Home Manager";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Hyprland from its own flake for latest commits
    hyprland = {
      url = "github:hyprwm/Hyprland";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Quickshell from the upstream git repository
    quickshell = {
      url = "git+https://git.outfoxxed.me/quickshell/quickshell";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Catppuccin theme overlays
    catppuccin.url = "github:catppuccin/nix";

    # sops-nix for secret management
    sops-nix = {
      url = "github:Mic92/sops-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, home-manager, hyprland, quickshell, catppuccin, sops-nix, ... }@inputs:
  let
    system = "x86_64-linux";
    pkgs = nixpkgs.legacyPackages.${system};
  in {
    # NixOS system configuration (optional — omit for standalone HM)
    nixosConfigurations.myhostname = nixpkgs.lib.nixosSystem {
      inherit system;
      modules = [
        ./hosts/myhostname/configuration.nix
        home-manager.nixosModules.home-manager
        {
          home-manager.useGlobalPkgs = true;
          home-manager.useUserPackages = true;
          home-manager.users.alice = import ./home.nix;
          home-manager.extraSpecialArgs = { inherit inputs; };
        }
      ];
    };

    # Standalone Home Manager configuration
    homeConfigurations."alice@myhostname" = home-manager.lib.homeManagerConfiguration {
      inherit pkgs;
      modules = [
        catppuccin.homeModules.catppuccin
        sops-nix.homeManagerModules.sops
        ./home.nix
      ];
      extraSpecialArgs = { inherit inputs; };
    };
  };
}
```

After creating this file in your dotfiles directory, run:

```bash
# Initialize the flake lock file
nix flake update

# Apply the standalone Home Manager config (first time)
nix run home-manager -- switch --flake .#alice@myhostname

# Subsequent switches (home-manager must be on PATH)
home-manager switch --flake .#alice@myhostname

# Or if using NixOS module, rebuild the system
sudo nixos-rebuild switch --flake .#myhostname
```

The `inputs.nixpkgs.follows` directives ensure every input uses the same nixpkgs, preventing multiple versions of glibc from appearing in your closure — a common source of large store sizes.

---

## 39.4 Compositor Configuration in Nix

The `wayland.windowManager.hyprland` module is the most feature-complete compositor module in Home Manager as of 2025. It accepts settings as a Nix attribute set, translating them to Hyprland's config syntax at activation time. You can mix declarative settings with `extraConfig` for anything the module doesn't expose.

```nix
# home.nix (relevant excerpt)
{ inputs, pkgs, ... }:
{
  wayland.windowManager.hyprland = {
    enable = true;
    # Use the Hyprland flake package rather than nixpkgs version
    package = inputs.hyprland.packages.${pkgs.system}.hyprland;

    settings = {
      # Monitor layout
      monitor = [
        "DP-1,2560x1440@144,0x0,1"
        "HDMI-A-1,1920x1080@60,2560x0,1"
      ];

      general = {
        gaps_in = 6;
        gaps_out = 12;
        border_size = 2;
        "col.active_border" = "rgba(cba6f7ff) rgba(89b4faff) 45deg";
        "col.inactive_border" = "rgba(313244aa)";
        layout = "dwindle";
        resize_on_border = true;
      };

      decoration = {
        rounding = 12;
        active_opacity = 1.0;
        inactive_opacity = 0.92;
        blur = {
          enabled = true;
          size = 8;
          passes = 2;
          new_optimizations = true;
          xray = false;
        };
        shadow = {
          enabled = true;
          range = 20;
          render_power = 3;
          color = "rgba(1a1a2eee)";
        };
      };

      animations = {
        enabled = true;
        bezier = [
          "myBezier, 0.05, 0.9, 0.1, 1.05"
          "linear, 0.0, 0.0, 1.0, 1.0"
          "overshot, 0.13, 0.99, 0.29, 1.1"
        ];
        animation = [
          "windows, 1, 7, myBezier"
          "windowsOut, 1, 7, default, popin 80%"
          "border, 1, 10, default"
          "fade, 1, 7, default"
          "workspaces, 1, 6, overshot, slide"
        ];
      };

      input = {
        kb_layout = "us";
        follow_mouse = 1;
        sensitivity = 0;
        touchpad = {
          natural_scroll = true;
          tap-to-click = true;
        };
      };

      dwindle = {
        pseudotile = true;
        preserve_split = true;
      };

      misc = {
        force_default_wallpaper = 0;
        disable_hyprland_logo = true;
        vrr = 1;
      };

      # Window rules
      windowrulev2 = [
        "float,class:^(pavucontrol)$"
        "float,class:^(nm-applet)$"
        "opacity 0.90 0.85,class:^(kitty)$"
        "workspace 2,class:^(firefox)$"
        "workspace 3,class:^(code)$"
        "noanim,class:^(xwaylandvideobridge)$"
      ];

      # Keybinds — $mainMod is SUPER by default
      "$mainMod" = "SUPER";
      bind = [
        "$mainMod, Return, exec, kitty"
        "$mainMod, Q, killactive"
        "$mainMod, M, exit"
        "$mainMod, E, exec, nautilus"
        "$mainMod, V, togglefloating"
        "$mainMod, R, exec, fuzzel"
        "$mainMod, P, pseudo"
        "$mainMod, J, togglesplit"
        "$mainMod, F, fullscreen, 1"
        # Workspace switching
        "$mainMod, 1, workspace, 1"
        "$mainMod, 2, workspace, 2"
        "$mainMod, 3, workspace, 3"
        "$mainMod SHIFT, 1, movetoworkspace, 1"
        "$mainMod SHIFT, 2, movetoworkspace, 2"
        "$mainMod SHIFT, 3, movetoworkspace, 3"
        # Screenshots
        ", Print, exec, grimblast copy area"
        "$mainMod, Print, exec, grimblast save area"
      ];

      bindm = [
        "$mainMod, mouse:272, movewindow"
        "$mainMod, mouse:273, resizewindow"
      ];

      exec-once = [
        "waybar"
        "dunst"
        "swww-daemon"
        "[workspace 1 silent] kitty"
      ];
    };

    # Anything the module doesn't expose
    extraConfig = ''
      source = ~/.config/hypr/colors.conf
      source = ~/.config/hypr/local.conf
    '';

    # Start as a systemd user service (recommended)
    systemd.enable = true;
  };
}
```

For Sway users, the `wayland.windowManager.sway` module follows an almost identical structure with sway-specific options (`swaybg`, `swayidle`, `swaylock` have their own modules too):

```nix
wayland.windowManager.sway = {
  enable = true;
  config = {
    modifier = "Mod4";
    terminal = "foot";
    menu = "fuzzel";
    bars = [];  # managed by waybar separately

    output = {
      "DP-1" = { resolution = "2560x1440"; refresh_rate = "144"; };
    };

    gaps = { inner = 6; outer = 12; };

    keybindings = let mod = "Mod4"; in {
      "${mod}+Return" = "exec foot";
      "${mod}+q" = "kill";
      "${mod}+r" = "exec fuzzel";
      "${mod}+Shift+e" = "exec swaymsg exit";
    };

    startup = [
      { command = "waybar"; }
      { command = "mako"; }
      { command = "swww-daemon"; }
    ];
  };

  extraConfig = ''
    include ~/.config/sway/colors.conf
  '';
};
```

---

## 39.5 Quickshell in Home Manager

Quickshell does not yet (as of mid-2025) have an official Home Manager module. The recommended approach is to manage the package declaratively and symlink configuration with `home.file`. Because Quickshell configs are QML files rather than opaque binaries, the Nix store path is a directory of source files — you can symlink it directly or copy it into `~/.config/quickshell/`.

```nix
{ inputs, pkgs, ... }:
{
  # Install Quickshell from its flake
  home.packages = [
    inputs.quickshell.packages.${pkgs.system}.default
  ];

  # Symlink QML config from the dotfiles repo into the expected location
  # Option A: symlink the entire config directory
  home.file.".config/quickshell" = {
    source = ./quickshell;  # relative to home.nix
    recursive = true;
  };

  # Option B: manage individual files with inline content
  home.file.".config/quickshell/shell.qml" = {
    text = ''
      import Quickshell
      import QtQuick

      ShellRoot {
          PanelWindow {
              anchors { top: true; left: true; right: true }
              height: 36
              // ... bar content
          }
      }
    '';
  };

  # Autostart Quickshell via systemd user service
  systemd.user.services.quickshell = {
    Unit = {
      Description = "Quickshell shell compositor layer";
      After = [ "graphical-session.target" ];
      PartOf = [ "graphical-session.target" ];
    };
    Service = {
      ExecStart = "${inputs.quickshell.packages.${pkgs.system}.default}/bin/quickshell";
      Restart = "on-failure";
      RestartSec = "3s";
    };
    Install.WantedBy = [ "graphical-session.target" ];
  };
}
```

See Chapter 53 for session startup and Chapter 42 for Quickshell QML architecture details.

---

## 39.6 Unified Theming: GTK, Qt, Fonts, and Cursors

One of Home Manager's most powerful ricing features is unified theming. Instead of setting GTK theme in `~/.config/gtk-3.0/settings.ini`, the Qt style in `~/.config/qt5ct/qt5ct.conf`, and the cursor theme in `~/.icons/default/index.theme`, you declare everything once and Home Manager writes all the files.

```nix
{ pkgs, ... }:
{
  # GTK theming
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

    gtk3.extraConfig = {
      gtk-application-prefer-dark-theme = 1;
      gtk-button-images = 0;
      gtk-menu-images = 0;
      gtk-enable-event-sounds = 0;
    };

    gtk4.extraConfig = {
      gtk-application-prefer-dark-theme = 1;
    };
  };

  # Qt theming via qt5ct / kvantum
  qt = {
    enable = true;
    platformTheme.name = "qtct";
    style = {
      name = "kvantum";
      package = pkgs.catppuccin-kvantum.override {
        accent = "Mauve";
        variant = "Mocha";
      };
    };
  };

  # Unified cursor (also sets Wayland cursor env vars)
  home.pointerCursor = {
    gtk.enable = true;
    x11.enable = true;
    name = "catppuccin-mocha-dark-cursors";
    size = 24;
    package = pkgs.catppuccin-cursors.mochaDark;
  };

  # Fonts
  fonts.fontconfig.enable = true;
  home.packages = with pkgs; [
    # Nerd fonts for terminal and status bar glyphs
    nerd-fonts.jetbrains-mono
    nerd-fonts.symbols-only
    # UI fonts
    inter
    cantarell-fonts
    # CJK support
    noto-fonts-cjk-sans
    # Emoji
    noto-fonts-emoji
  ];
}
```

For the Catppuccin ecosystem specifically, the `catppuccin/nix` flake input (used in the flake.nix above) provides a `catppuccin` Home Manager module that centralises the accent and variant selection:

```nix
# With catppuccin.homeManagerModules.catppuccin imported
{
  catppuccin = {
    enable = true;
    flavor = "mocha";
    accent = "mauve";
  };

  # Individual overrides still possible
  catppuccin.hyprland.enable = true;
  catppuccin.waybar.enable = true;
  catppuccin.kitty.enable = true;
  catppuccin.fish.enable = true;
}
```

---

## 39.7 Terminal and Shell Configuration

Home Manager modules for terminals and shells are among the most complete in the ecosystem. Setting a terminal's colorscheme, font, opacity, keybindings, and shell integration all happen in one attribute set.

```nix
{ pkgs, ... }:
{
  programs.kitty = {
    enable = true;
    font = {
      name = "JetBrainsMono Nerd Font";
      size = 12.5;
    };
    settings = {
      background_opacity = "0.95";
      window_padding_width = 12;
      cursor_shape = "beam";
      cursor_blink_interval = "0.5";
      enable_audio_bell = false;
      confirm_os_window_close = 0;
      # Catppuccin Mocha colors
      foreground = "#CDD6F4";
      background = "#1E1E2E";
      selection_foreground = "#1E1E2E";
      selection_background = "#F5E0DC";
      cursor = "#F5E0DC";
      color0 = "#45475A";
      color8 = "#585B70";
      color1 = "#F38BA8";
      color9 = "#F38BA8";
    };
    keybindings = {
      "ctrl+shift+t" = "new_tab_with_cwd";
      "ctrl+shift+enter" = "new_window_with_cwd";
    };
  };

  programs.foot = {
    enable = true;
    settings = {
      main = {
        font = "JetBrainsMono Nerd Font:size=12";
        pad = "12x12";
      };
      colors = {
        foreground = "cdd6f4";
        background = "1e1e2e";
        regular0 = "45475a";
        regular1 = "f38ba8";
        regular2 = "a6e3a1";
        regular3 = "f9e2af";
        regular4 = "89b4fa";
        regular5 = "f5c2e7";
        regular6 = "94e2d5";
        regular7 = "bac2de";
      };
      mouse.hide-when-typing = "yes";
    };
  };

  programs.zsh = {
    enable = true;
    autosuggestion.enable = true;
    syntaxHighlighting.enable = true;
    enableCompletion = true;
    history = {
      size = 100000;
      save = 100000;
      share = true;
      ignoreDups = true;
      ignoreSpace = true;
    };
    initExtra = ''
      setopt AUTO_CD
      setopt GLOB_DOTS
      bindkey '^[[A' history-search-backward
      bindkey '^[[B' history-search-forward
    '';
  };

  programs.starship = {
    enable = true;
    settings = {
      add_newline = false;
      format = "$directory$git_branch$git_status$nix_shell$character";
      character = {
        success_symbol = "[❯](bold green)";
        error_symbol = "[❯](bold red)";
      };
      directory = {
        style = "bold blue";
        truncation_length = 4;
      };
      git_branch = {
        symbol = " ";
        style = "bold purple";
      };
      nix_shell = {
        symbol = " ";
        style = "bold cyan";
      };
    };
  };

  programs.fish = {
    enable = true;
    interactiveShellInit = ''
      set fish_greeting ""
      fish_vi_key_bindings
    '';
    shellAliases = {
      ls = "eza --icons";
      ll = "eza -la --icons --git";
      cat = "bat --style=plain";
      grep = "rg";
      find = "fd";
    };
    plugins = [
      { name = "z"; src = pkgs.fishPlugins.z.src; }
      { name = "fzf-fish"; src = pkgs.fishPlugins.fzf-fish.src; }
    ];
  };
}
```

---

## 39.8 Managing Dotfiles with Nix

Not every application has a Home Manager module. For those that don't, `home.file` provides full control over the file contents, permissions, and placement. Understanding the three common patterns lets you manage any application declaratively.

```nix
{ pkgs, ... }:
{
  # Pattern 1: source file from the repo (tracked by git)
  home.file.".config/hypr/colors.conf".source = ./hypr/colors.conf;

  # Pattern 2: inline text — good for generated/derived content
  home.file.".config/mako/config".text = ''
    [urgency=low]
    background-color=#1e1e2e
    text-color=#cdd6f4
    border-color=#313244
    border-radius=12
    default-timeout=5000

    [urgency=normal]
    background-color=#1e1e2e
    text-color=#cdd6f4
    border-color=#cba6f7
    border-radius=12
    default-timeout=7000

    [urgency=critical]
    background-color=#f38ba8
    text-color=#1e1e2e
    border-color=#f38ba8
    border-radius=12
    default-timeout=0
  '';

  # Pattern 3: pkgs.writeText for computed/large content
  home.file.".config/fuzzel/fuzzel.ini".source = pkgs.writeText "fuzzel.ini" ''
    [main]
    font=JetBrainsMono Nerd Font:size=12
    dpi-aware=yes
    prompt=❯ 
    terminal=kitty -e

    [colors]
    background=1e1e2eff
    text=cdd6f4ff
    match=cba6f7ff
    selection=313244ff
    selection-text=cdd6f4ff
    border=cba6f7ff

    [border]
    width=2
    radius=12

    [dmenu]
    mode=text
  '';

  # Pattern 4: generate a file from a Nix expression
  home.file.".config/waybar/colors.css".text =
    let
      colors = {
        base = "#1e1e2e";
        mantle = "#181825";
        crust = "#11111b";
        text = "#cdd6f4";
        mauve = "#cba6f7";
        blue = "#89b4fa";
        green = "#a6e3a1";
        red = "#f38ba8";
        yellow = "#f9e2af";
        surface0 = "#313244";
        surface1 = "#45475a";
      };
    in ''
      @define-color base ${colors.base};
      @define-color mantle ${colors.mantle};
      @define-color text ${colors.text};
      @define-color mauve ${colors.mauve};
      @define-color blue ${colors.blue};
      @define-color green ${colors.green};
      @define-color red ${colors.red};
      @define-color yellow ${colors.yellow};
      @define-color surface0 ${colors.surface0};
    '';
}
```

The `home.activation` attribute lets you run imperative commands after every switch — for operations Nix can't model purely (like running `dconf write` or `gsettings set`):

```nix
home.activation.gtkSettings = lib.hm.dag.entryAfter ["writeBoundary"] ''
  ${pkgs.glib}/bin/gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'
  ${pkgs.glib}/bin/gsettings set org.gnome.desktop.interface cursor-theme 'catppuccin-mocha-dark-cursors'
'';
```

---

## 39.9 NixOS System-Level vs. Home Manager

Understanding what belongs at the system level versus the user level prevents subtle conflicts. The general principle: anything affecting hardware, kernel, or multiple users belongs in `configuration.nix`; anything affecting a single user's environment belongs in `home.nix`.

| Concern | NixOS (`configuration.nix`) | Home Manager (`home.nix`) |
|---|---|---|
| GPU drivers | `hardware.graphics.enable = true` | N/A |
| Display manager / greeter | `services.greetd` | N/A |
| Hyprland package install | `programs.hyprland.enable = true` | `wayland.windowManager.hyprland.enable = true` |
| Hyprland config | N/A | `wayland.windowManager.hyprland.settings` |
| System fonts | `fonts.packages` | `home.packages` (user scope) |
| Pipewire | `services.pipewire.enable = true` | N/A (system service) |
| GTK theme | N/A | `gtk.theme` |
| User shell | `users.users.alice.shell` | `programs.zsh.enable = true` |
| Secrets | N/A (use agenix) | N/A (use sops-nix) |

The hybrid pattern is common: NixOS installs Hyprland's binary and sets the polkit helper, while Home Manager writes `hyprland.conf`. To avoid a "double install" that wastes store space, set `wayland.windowManager.hyprland.package = null;` in Home Manager when NixOS already provides the binary, or prefer the flake-based approach where the same package is referenced by both.

```nix
# configuration.nix
{ inputs, ... }:
{
  programs.hyprland = {
    enable = true;
    package = inputs.hyprland.packages.${pkgs.system}.hyprland;
    portalPackage = inputs.hyprland.packages.${pkgs.system}.xdg-desktop-portal-hyprland;
  };

  # Pipewire (system-level audio)
  services.pipewire = {
    enable = true;
    alsa.enable = true;
    alsa.support32Bit = true;
    pulse.enable = true;
    wireplumber.enable = true;
  };

  # Required for Wayland screen sharing
  xdg.portal = {
    enable = true;
    extraPortals = [ pkgs.xdg-desktop-portal-gtk ];
  };
}
```

```nix
# home.nix — references the same flake package to avoid duplication
{ inputs, pkgs, ... }:
{
  wayland.windowManager.hyprland = {
    enable = true;
    package = inputs.hyprland.packages.${pkgs.system}.hyprland;
    # ... settings
  };
}
```

---

## 39.10 Sharing Rices as Flakes

Flake-based dotfiles are the current gold standard for sharing a rice. Because `flake.lock` pins every dependency, anyone who clones your repo gets an identical build. The workflow for consumers is minimal.

```bash
# Try someone's rice in a temporary environment (no install)
nix run github:someuser/dotfiles

# Clone and adapt
git clone https://github.com/someuser/dotfiles ~/.dotfiles
cd ~/.dotfiles
# Edit home.nix: change username, monitor names, keyboard layout
home-manager switch --flake .#yourusername@yourhostname
```

To publish your own rice, structure the repo so the flake is at the root and each machine has its own attribute:

```
dotfiles/
├── flake.nix
├── flake.lock
├── home.nix              # shared user config
├── hosts/
│   ├── desktop/
│   │   ├── configuration.nix
│   │   └── hardware-configuration.nix
│   └── laptop/
│       ├── configuration.nix
│       └── hardware-configuration.nix
├── modules/
│   ├── hyprland.nix
│   ├── theming.nix
│   ├── terminals.nix
│   └── waybar.nix
└── quickshell/
    └── shell.qml
```

The `modules/` pattern lets you compose your Home Manager config from focused files:

```nix
# home.nix
{ ... }:
{
  imports = [
    ./modules/hyprland.nix
    ./modules/theming.nix
    ./modules/terminals.nix
    ./modules/waybar.nix
  ];

  home = {
    username = "alice";
    homeDirectory = "/home/alice";
    stateVersion = "24.11";
  };
}
```

Community resources for finding and sharing flake-based rices: the [Nix starter configs](https://github.com/Misterio77/nix-starter-configs) template, [awesome-nix](https://github.com/nix-community/awesome-nix), and the weekly r/unixporn threads where flake links are increasingly common.

---

## 39.11 Secrets Management with sops-nix

Secrets (API keys in waybar scripts, passwords for network mounts, SSH keys) must never enter the Nix store — store paths are world-readable. The two dominant solutions are `sops-nix` (uses Mozilla SOPS with age or GPG) and `agenix` (uses age directly). Both decrypt secrets at activation time and write them to paths outside the store.

```nix
# flake.nix already has sops-nix input (see 39.3)

# home.nix
{ config, ... }:
{
  sops = {
    defaultSopsFile = ./secrets/secrets.yaml;
    defaultSopsFormat = "yaml";
    age.keyFile = "${config.home.homeDirectory}/.config/sops/age/keys.txt";

    secrets = {
      # Decrypted to /run/user/1000/secrets/waybar-weather-key
      waybar-weather-key = {};
      # Decrypted to a specific path with specific permissions
      ssh-private-key = {
        path = "${config.home.homeDirectory}/.ssh/id_ed25519";
        mode = "0600";
      };
    };
  };

  # Reference the secret path in waybar config
  programs.waybar = {
    enable = true;
    settings.mainBar = {
      modules-right = [ "custom/weather" "clock" ];
      "custom/weather" = {
        exec = ''
          API_KEY=$(cat ${config.sops.secrets.waybar-weather-key.path})
          curl -s "wttr.in/?format=1&key=$API_KEY"
        '';
        interval = 1800;
        format = "{}";
      };
    };
  };
}
```

To create the secrets file:

```bash
# Generate an age key
mkdir -p ~/.config/sops/age
age-keygen -o ~/.config/sops/age/keys.txt

# Get the public key
age-keygen -y ~/.config/sops/age/keys.txt

# Create .sops.yaml at the repo root
cat > .sops.yaml << 'EOF'
keys:
  - &alice age1ql3z7hjy54pw3hyww5ayyfg7zqgvc7w3j2elw8zmrj2kg5sfn9aqmcac8p
creation_rules:
  - path_regex: secrets/.*\.yaml
    key_groups:
      - age:
          - *alice
EOF

# Create and encrypt the secrets file
sops secrets/secrets.yaml
# (editor opens — add your secrets as YAML, save and close)
```

---

## 39.12 Useful Nix Patterns for Ricing

Several Nix idioms appear repeatedly in well-structured rice configs. Understanding them makes reading others' configs and writing your own much smoother.

**Conditional modules** — enable or disable features based on a flag:

```nix
{ lib, config, ... }:
{
  options.myRice.gaming.enable = lib.mkEnableOption "gaming packages and configs";

  config = lib.mkIf config.myRice.gaming.enable {
    home.packages = with pkgs; [ steam gamemode mangohud ];
    wayland.windowManager.hyprland.settings.windowrulev2 = [
      "immediate,class:^(cs2)$"
      "fullscreen,class:^(cs2)$"
    ];
  };
}
```

**Per-host overrides** using `lib.mkMerge` or host-specific imports:

```nix
# hosts/laptop/home.nix
{ ... }:
{
  imports = [ ../../home.nix ];

  # Override for laptop: lower opacity (battery), enable touchpad gestures
  wayland.windowManager.hyprland.settings.decoration.inactive_opacity = 0.85;
  wayland.windowManager.hyprland.settings.gestures = {
    workspace_swipe = true;
    workspace_swipe_fingers = 3;
  };
}
```

**Color palette as a Nix value** — define once, use everywhere:

```nix
# modules/colors.nix
{ lib, ... }:
let
  palette = {
    mocha = {
      base = "#1e1e2e";
      text = "#cdd6f4";
      mauve = "#cba6f7";
      blue = "#89b4fa";
      green = "#a6e3a1";
      red = "#f38ba8";
    };
  };
in {
  options.myRice.palette = lib.mkOption {
    type = lib.types.attrsOf (lib.types.attrsOf lib.types.str);
    default = palette;
  };
}
```

---

## Troubleshooting

**`home-manager switch` fails with "collision between..."**

Two packages provide the same file. Common cause: both `home.packages` and a `programs.X` module install the same binary. Fix: remove the package from `home.packages` and let the module manage it, or vice versa.

```bash
# Identify the collision
home-manager switch --flake .#alice@hostname 2>&1 | grep "collision"
# Typical output: collision between /nix/store/abc-foo-1.0/bin/foo and /nix/store/xyz-foo-1.1/bin/foo
```

**Changes not taking effect after `home-manager switch`**

Some applications cache config at launch. Kill the process and restart it. For Hyprland: `hyprctl reload`. For waybar: `pkill waybar && waybar &`. For GTK apps, the dconf/gsettings database may need clearing: `dconf reset -f /`.

**`nix flake update` breaks the build**

A flake input updated to a version that changed an API. Check which input changed:

```bash
git diff flake.lock | grep '"lastModified"'
# Identify the changed input, then check its changelog
# To pin back to a specific commit:
nix flake lock --update-input nixpkgs --override-input nixpkgs github:nixos/nixpkgs/abc123
```

**Home Manager module option doesn't exist yet**

Check the Home Manager release notes and option search at `https://home-manager-options.extranix.com`. If the option is missing, use `home.file` as the fallback. To see all available options for a module:

```bash
nix repl
nix-repl> :load-flake .
nix-repl> homeConfigurations."alice@hostname".options.programs.kitty
```

**Hyprland crashes immediately after `home-manager switch`**

Likely a config syntax error generated by the module. Test with:

```bash
hyprland --config ~/.config/hypr/hyprland.conf 2>&1 | head -30
# Or check the generated config
cat ~/.config/hypr/hyprland.conf
```

**`sops-nix` decryption fails at activation**

The age key path is wrong or the key doesn't match the one used to encrypt. Verify:

```bash
# Check key identity
age-keygen -y ~/.config/sops/age/keys.txt
# Compare to .sops.yaml recipient
cat .sops.yaml
# Test decryption manually
sops --decrypt secrets/secrets.yaml
```

**Large closure size / slow builds**

Run `nix why-depends` to find what's pulling in large packages:

```bash
nix why-depends .#homeConfigurations."alice@hostname".activationPackage nixpkgs#chromium
# If you don't want chromium, find what depends on it and exclude it
home.packages = lib.mkForce (lib.filter (p: p.pname or "" != "chromium") config.home.packages);
```

---

*See also:*
- *Chapter 35 — GTK Theming: Adwaita, libadwaita, CSS Overrides*
- *Chapter 36 — Qt and KDE Theming: Kvantum, qt5ct/qt6ct*
- *Chapter 40 — NixOS System Configuration for Wayland*
- *Chapter 42 — Quickshell Deep Dive*
- *Chapter 53 — Session Startup and Autostart*

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
