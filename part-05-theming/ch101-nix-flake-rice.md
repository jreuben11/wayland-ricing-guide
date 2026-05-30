# Chapter 101 — Advanced Nix Flake Architecture for a Full Rice

## Contents

- [Overview](#overview)
- [101.1 Repository Structure](#1011-repository-structure)
- [101.2 Root flake.nix](#1012-root-flakenix)
- [101.3 Shared Host Config (`hosts/default.nix`)](#1013-shared-host-config-hostsdefaultnix)
- [101.4 Host-Specific Config (`hosts/laptop/default.nix`)](#1014-host-specific-config-hostslaptopdefaultnix)
- [101.5 Shared Home Config (`home/default.nix`)](#1015-shared-home-config-homedefaultnix)
- [101.6 Hyprland Home Module (`home/hyprland.nix`)](#1016-hyprland-home-module-homehyprlandnix)
- [101.7 Secrets Management with agenix](#1017-secrets-management-with-agenix)
  - [Setup](#setup)
  - [`secrets/secrets.nix` — key declarations](#secretssecretsnix-key-declarations)
  - [Encrypt a secret](#encrypt-a-secret)
  - [Use in NixOS config](#use-in-nixos-config)
- [101.8 sops-nix (Alternative to agenix)](#1018-sops-nix-alternative-to-agenix)
- [101.9 Custom Overlays](#1019-custom-overlays)
- [101.10 Reusable NixOS Module (`modules/nixos/wayland.nix`)](#10110-reusable-nixos-module-modulesnixoswaylandnix)
- [101.11 Deploy and Maintain](#10111-deploy-and-maintain)

---


## Overview

Chapter 39 covers Home Manager basics. This chapter goes further: structuring
a production-quality Nix flake that manages your complete rice across multiple
machines, with secrets management, custom modules, hardware-specific configs,
and overlay patterns. The goal is a single `git push` that reproducibly
rebuilds your entire desktop on any host.

---

## 101.1 Repository Structure

```
~/dotfiles/
├── flake.nix                   ← entry point
├── flake.lock
├── hosts/
│   ├── default.nix             ← shared host config imported by all hosts
│   ├── desktop/
│   │   ├── default.nix
│   │   └── hardware-configuration.nix
│   └── laptop/
│       ├── default.nix
│       └── hardware-configuration.nix
├── home/
│   ├── default.nix             ← shared home-manager config
│   ├── hyprland.nix
│   ├── quickshell.nix
│   ├── terminal.nix
│   └── theme.nix
├── modules/
│   ├── nixos/
│   │   ├── audio.nix           ← reusable NixOS modules
│   │   ├── gaming.nix
│   │   └── wayland.nix
│   └── home/
│       ├── ricing.nix          ← reusable HM modules
│       └── fonts.nix
├── pkgs/
│   └── custom-package/         ← overlay packages
├── secrets/
│   ├── secrets.nix             ← agenix secret declarations
│   └── *.age                   ← encrypted secret files
└── overlays/
    └── default.nix
```

---

## 101.2 Root flake.nix

```nix
{
  description = "Personal NixOS rice — multi-host configuration";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";    # use same nixpkgs, saves space
    };

    # Hardware-specific configs (Framework, ThinkPad, etc.)
    nixos-hardware.url = "github:NixOS/nixos-hardware";

    # Hyprland flake (bleeding-edge builds)
    hyprland = {
      url = "github:hyprwm/Hyprland";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Secrets management
    agenix = {
      url = "github:ryantm/agenix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Stylix auto-theming
    stylix = {
      url = "github:danth/stylix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Quickshell (if building from source)
    quickshell = {
      url = "github:quickshell-mirror/quickshell";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, home-manager, nixos-hardware,
              hyprland, agenix, stylix, quickshell, ... } @ inputs:
  let
    system = "x86_64-linux";

    # Shared arguments passed to every module via specialArgs
    specialArgs = {
      inherit inputs;
      myLib = import ./lib { inherit nixpkgs; };
    };

    # Overlays applied to nixpkgs across all configurations
    overlays = [ (import ./overlays) ];

    pkgs = import nixpkgs {
      inherit system;
      config.allowUnfree = true;
      inherit overlays;
    };

    # Helper to build a NixOS host config
    mkHost = { hostname, extraModules ? [] }:
      nixpkgs.lib.nixosSystem {
        inherit system specialArgs;
        modules = [
          # Base shared config
          ./hosts/default.nix
          # Host-specific config
          ./hosts/${hostname}
          # Home Manager as a NixOS module
          home-manager.nixosModules.home-manager {
            home-manager.useGlobalPkgs    = true;
            home-manager.useUserPackages  = true;
            home-manager.extraSpecialArgs = specialArgs;
            home-manager.users.jreuben11  = import ./home;
          }
          # Secrets
          agenix.nixosModules.default
          # Stylix
          stylix.nixosModules.stylix
          # Hyprland NixOS module
          hyprland.nixosModules.default
        ] ++ extraModules;
      };

  in {
    nixosConfigurations = {
      desktop = mkHost {
        hostname = "desktop";
        extraModules = [ ./modules/nixos/gaming.nix ];
      };

      laptop = mkHost {
        hostname = "laptop";
        extraModules = [
          nixos-hardware.nixosModules.lenovo-thinkpad-t14-amd-gen5
        ];
      };
    };

    # Expose packages for nix run / nix shell
    packages.${system} = import ./pkgs { inherit pkgs; };

    # Development shell for working on configs
    devShells.${system}.default = pkgs.mkShell {
      packages = [ pkgs.agenix pkgs.nixpkgs-fmt pkgs.deadnix pkgs.statix ];
    };
  };
}
```

---

## 101.3 Shared Host Config (`hosts/default.nix`)

```nix
{ config, pkgs, inputs, ... }:
{
  imports = [
    ../modules/nixos/wayland.nix
    ../modules/nixos/audio.nix
  ];

  nix = {
    settings = {
      experimental-features = [ "nix-command" "flakes" ];
      auto-optimise-store   = true;
      substituters = [
        "https://cache.nixos.org"
        "https://hyprland.cachix.org"
        "https://nix-community.cachix.org"
      ];
      trusted-public-keys = [
        "cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY="
        "hyprland.cachix.org-1:a7pgxzMz7+chwVL3/pzj6jIBMioiJM7ypFP8PwtkuGc="
        "nix-community.cachix.org-1:mB9FSh9qf2dCimDSUo8Zy7bkq5CX+/rkCWyvRCUSeBs="
      ];
    };
    gc = {
      automatic = true;
      dates     = "weekly";
      options   = "--delete-older-than 30d";
    };
  };

  boot.loader.systemd-boot.enable      = true;
  boot.loader.efi.canTouchEfiVariables = true;

  time.timeZone = "America/New_York";

  users.users.jreuben11 = {
    isNormalUser = true;
    extraGroups  = [ "wheel" "video" "audio" "input" "kvm" "libvirtd" ];
    shell        = pkgs.zsh;
  };

  programs.zsh.enable = true;
  environment.shells  = [ pkgs.zsh ];
}
```

---

## 101.4 Host-Specific Config (`hosts/laptop/default.nix`)

```nix
{ config, pkgs, inputs, ... }:
{
  imports = [
    ./hardware-configuration.nix
    ../../modules/nixos/laptop.nix
  ];

  networking.hostName = "laptop";

  # Override shared config for this host
  stylix.image = ./wallpaper-laptop.jpg;

  # Laptop-specific power management
  services.tlp.enable = true;
  services.power-profiles-daemon.enable = false;  # conflicts with tlp

  # Laptop display
  services.xserver.dpi = 144;   # for XWayland apps at 1.5× scale
}
```

---

## 101.5 Shared Home Config (`home/default.nix`)

```nix
{ config, pkgs, inputs, ... }:
{
  imports = [
    ./hyprland.nix
    ./terminal.nix
    ./theme.nix
  ];

  home.username      = "jreuben11";
  home.homeDirectory = "/home/jreuben11";
  home.stateVersion  = "25.11";

  home.packages = with pkgs; [
    # Ricing tools
    swww hyprpaper hypridle hyprlock hyprpicker
    grim slurp swappy wl-clipboard cliphist
    fuzzel mako wlsunset
    # Apps
    firefox kitty foot yazi
    btop nvtop
  ];

  programs.home-manager.enable = true;

  # XDG base directories
  xdg.enable = true;
  xdg.userDirs.enable    = true;
  xdg.userDirs.createDirectories = true;
}
```

---

## 101.6 Hyprland Home Module (`home/hyprland.nix`)

```nix
{ config, pkgs, inputs, lib, ... }:
{
  wayland.windowManager.hyprland = {
    enable        = true;
    package       = inputs.hyprland.packages.${pkgs.system}.hyprland;
    xwayland.enable = true;

    settings = {
      "$mod" = "SUPER";

      monitor = [
        "DP-1,2560x1440@165,0x0,1"
        ",preferred,auto,1"
      ];

      general = {
        gaps_in    = 5;
        gaps_out   = 10;
        border_size = 2;
        layout     = "dwindle";
      };

      decoration = {
        rounding = 10;
        blur = {
          enabled = true;
          size    = 8;
          passes  = 2;
        };
      };

      input = {
        kb_layout   = "us";
        kb_options  = "caps:escape";
        follow_mouse = 1;
        sensitivity  = 0;
        touchpad = {
          natural_scroll = true;
          tap-to-click   = true;
        };
      };

      misc = {
        vfr = true;
        disable_hyprland_logo = true;
      };

      bind = let mod = "$mod"; in [
        "${mod}, Return, exec, kitty"
        "${mod}, Space,  exec, fuzzel"
        "${mod}, Q,      killactive"
        "${mod}, F,      fullscreen"
      ] ++ (lib.concatLists (lib.genList (i:
        let ws = toString (i + 1);
            key = toString (lib.mod (i + 1) 10);
        in [
          "${mod}, ${key},       workspace,       ${ws}"
          "${mod} SHIFT, ${key}, movetoworkspace, ${ws}"
        ]
      ) 10));

      exec-once = [
        "waybar"
        "hyprpaper"
        "hypridle"
        "dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP"
      ];

      env = [
        "QT_QPA_PLATFORM,wayland"
        "MOZ_ENABLE_WAYLAND,1"
        "GDK_BACKEND,wayland,x11"
        "XDG_CURRENT_DESKTOP,Hyprland"
        "XDG_SESSION_TYPE,wayland"
      ];
    };
  };
}
```

---

## 101.7 Secrets Management with agenix

`agenix` encrypts secrets with `age` using your SSH public key. Encrypted files
are committed to git; decryption happens only on the target machine.

### Setup

```bash
# Install agenix CLI
nix shell nixpkgs#agenix

# Your public key (from ~/.ssh/id_ed25519.pub)
# Also add your host's SSH host key for machine-level secrets
cat /etc/ssh/ssh_host_ed25519_key.pub
```

### `secrets/secrets.nix` — key declarations

```nix
let
  # User keys — can decrypt on any machine you log into
  user = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... jreuben11@desktop";

  # Host keys — machine-specific, for secrets that shouldn't travel
  desktop = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... root@desktop";
  laptop  = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... root@laptop";
in {
  # Accessible from all machines (using user key)
  "wireguard-private-key.age".publicKeys = [ user desktop laptop ];
  "github-token.age".publicKeys          = [ user desktop laptop ];

  # Machine-specific
  "desktop-wifi-password.age".publicKeys = [ user desktop ];
}
```

### Encrypt a secret

```bash
cd secrets/
# Interactive: type the secret, Ctrl+D when done
agenix -e wireguard-private-key.age

# From a file:
agenix -e github-token.age < ~/my-token.txt
```

### Use in NixOS config

```nix
{ config, ... }:
{
  age.secrets.wireguard-key = {
    file  = ../secrets/wireguard-private-key.age;
    owner = "jreuben11";
    mode  = "0400";
  };

  # The decrypted path is available at runtime:
  # config.age.secrets.wireguard-key.path
  # → /run/agenix/wireguard-key

  networking.wireguard.interfaces.wg0 = {
    privateKeyFile = config.age.secrets.wireguard-key.path;
  };
}
```

---

## 101.8 sops-nix (Alternative to agenix)

`sops-nix` uses Mozilla SOPS with age/GPG. More flexible format (YAML/JSON/INI
secrets in one file), slightly more complex setup.

```nix
# flake.nix input
sops-nix.url = "github:Mic92/sops-nix";
```

```yaml
# secrets/secrets.yaml (encrypted with SOPS)
wireguard_key: ENC[AES256_GCM,data:...,type:str]
github_token:  ENC[AES256_GCM,data:...,type:str]
```

```nix
# In host config:
sops.defaultSopsFile = ../secrets/secrets.yaml;
sops.age.sshKeyPaths = [ "/etc/ssh/ssh_host_ed25519_key" ];

sops.secrets.wireguard_key = {
  owner = "jreuben11";
};
```

---

## 101.9 Custom Overlays

Override or add packages in `overlays/default.nix`:

```nix
final: prev: {
  # Override a package version
  hyprpaper = prev.hyprpaper.overrideAttrs (old: {
    src = prev.fetchFromGitHub {
      owner  = "hyprwm";
      repo   = "hyprpaper";
      rev    = "v0.8.0";
      sha256 = "sha256-...";
    };
  });

  # Add a custom package
  my-rice-scripts = final.writeShellScriptBin "rice-screenshot" ''
    ${final.grim}/bin/grim -t png - \
      | ${final.swappy}/bin/swappy -f -
  '';

  # Patch a package
  waybar = prev.waybar.override {
    withMediaPlayer = true;
    withSystemdActivation = true;
  };
}
```

---

## 101.10 Reusable NixOS Module (`modules/nixos/wayland.nix`)

```nix
{ config, lib, pkgs, ... }:
{
  options.my.wayland = {
    enable = lib.mkEnableOption "Wayland desktop environment";
  };

  config = lib.mkIf config.my.wayland.enable {
    services.greetd = {
      enable = true;
      settings.default_session = {
        command = "${pkgs.greetd.tuigreet}/bin/tuigreet --time --cmd Hyprland";
        user    = "greeter";
      };
    };

    security.polkit.enable = true;
    security.rtkit.enable  = true;

    services.pipewire = {
      enable            = true;
      alsa.enable       = true;
      alsa.support32Bit = true;
      pulse.enable      = true;
      jack.enable       = true;
      wireplumber.enable = true;
    };

    xdg.portal = {
      enable = true;
      extraPortals = [ pkgs.xdg-desktop-portal-hyprland ];
      config.common.default = "*";
    };

    environment.sessionVariables = {
      NIXOS_OZONE_WL = "1";
      MOZ_ENABLE_WAYLAND = "1";
    };
  };
}
```

Activate in a host:
```nix
my.wayland.enable = true;
```

---

## 101.11 Deploy and Maintain

```bash
# Apply changes to the current machine
sudo nixos-rebuild switch --flake .#$(hostname)

# Or using nh (better output):
nh os switch .

# Test without setting as boot default:
nh os test .

# Preview what will change:
nix run nixpkgs#nvd -- diff /run/current-system result

# Apply home-manager config independently:
nh home switch .

# Update all flake inputs:
nix flake update

# Update a single input:
nix flake lock --update-input hyprland

# Format all Nix files:
nix fmt . -- --all

# Check for dead code and common issues:
nix run nixpkgs#deadnix -- -l
nix run nixpkgs#statix -- check .
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
