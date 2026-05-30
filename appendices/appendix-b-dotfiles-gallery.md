# Appendix B — Dotfiles Repository Gallery

## Overview

This appendix is a curated, annotated reference library of real-world Wayland rices, organized by compositor and configuration stack. Each entry documents what the configuration does, why it is worth studying, and which concrete techniques you can extract for your own work — this is not a popularity contest but a selection of repositories that demonstrate distinct architectural choices, high code quality, or novel solutions to hard ricing problems. Coverage spans Quickshell+Hyprland setups, Waybar-based configurations, Sway rices, NixOS flake-based reproducible environments, and the emerging Niri ecosystem. At the end you will find an Annotated Dotfile Reading Guide with a five-step methodology for approaching any unfamiliar rice without wasting time copying things you do not understand. Use the **Annotated Dotfile Reading Guide** at the end of this appendix before diving into any repository. Cross-references: See **Chapter 4** for Hyprland compositor fundamentals, **Chapter 12** for Waybar configuration deep-dives, **Chapter 18** for Quickshell architecture, **Chapter 29** for NixOS flake patterns, and **Chapter 35** for color theming pipelines.

---

## Contents

- [Exemplary Quickshell + Hyprland Rices](#exemplary-quickshell-hyprland-rices)
  - [end_4/dots-hyprland](#end4dots-hyprland)
  - [outfoxxed's configurations](#outfoxxeds-configurations)
  - [ekremx25/quickshell](#ekremx25quickshell)
- [Hyprland + Waybar Rices](#hyprland-waybar-rices)
  - [notwidgets dotfiles](#notwidgets-dotfiles)
  - [prasanthrangan/hyprdots (HyDE)](#prasanthranganhyprdots-hyde)
- [Sway Rices](#sway-rices)
  - [swaywm example configs](#swaywm-example-configs)
  - [ben9ex dotfiles](#ben9ex-dotfiles)
- [NixOS Flake Rices](#nixos-flake-rices)
  - [Misterio77/nix-config](#misterio77nix-config)
  - [Frost-Phoenix/nixos-config](#frost-phoenixnixos-config)
  - [ryan4yin/nix-config](#ryan4yinnix-config)
- [Niri Rices](#niri-rices)
- [Finding More Rices](#finding-more-rices)
  - [Using GitHub Search Effectively](#using-github-search-effectively)
- [Annotated Dotfile Reading Guide](#annotated-dotfile-reading-guide)
  - [Step 1: Compositor Configuration](#step-1-compositor-configuration)
  - [Step 2: Bar Configuration](#step-2-bar-configuration)
  - [Step 3: Trace the Theme Pipeline](#step-3-trace-the-theme-pipeline)
  - [Step 4: Map the Startup Sequence](#step-4-map-the-startup-sequence)
  - [Step 5: Study the Keybindings](#step-5-study-the-keybindings)
- [Troubleshooting: Cloning and Running Someone Else's Config](#troubleshooting-cloning-and-running-someone-elses-config)
  - [Missing Fonts](#missing-fonts)
  - [Missing Dependencies](#missing-dependencies)
  - [Monitor Name Mismatch](#monitor-name-mismatch)
  - [Broken Waybar Modules](#broken-waybar-modules)
  - [Hyprland IPC Version Mismatch](#hyprland-ipc-version-mismatch)

---


## Exemplary Quickshell + Hyprland Rices

Quickshell is a QML-based shell toolkit that has rapidly displaced Waybar and EWW for power users who want composable, animated, stateful widgets. The rices in this section are worth studying precisely because they push Quickshell to its architectural limits, exposing patterns that less sophisticated configurations hide.

Quickshell's QML model means that each widget is a declarative component with a clearly defined state machine. When you read these configs, pay attention to how state is lifted to a shared singleton versus kept local to a component — this mirrors React's state management philosophy and determines whether your shell will be maintainable at scale. The rices below each make different trade-offs.

### end_4/dots-hyprland

- **URL**: https://github.com/end-4/dots-hyprland
- **Stack**: Hyprland + Quickshell + matugen
- **Style**: Colorful, animated, Material You
- **Notable**: AI assistant widget, dynamic theming, comprehensive keybinding overlay

This is arguably the most feature-complete public Quickshell rice as of 2025. The repository is structured as a collection of QML modules under `~/.config/quickshell/`, with a clear separation between layout components, service bindings, and theme utilities. The AI assistant widget demonstrates how to integrate an async subprocess call (spawning a Python helper) with QML's signal-slot mechanism.

The dynamic theming pipeline is: wallpaper change → `matugen` generates a `colors.json` palette → a QML `FileWatcher` detects the change → a singleton `Colors` object reloads and emits `colorsChanged` → all widgets that bind to `Colors.*` properties update automatically. This is a textbook example of reactive theming without a shell restart.

To clone and examine the structure without installing:

```bash
git clone --depth=1 https://github.com/end-4/dots-hyprland /tmp/dots-hyprland
tree -L 3 /tmp/dots-hyprland/.config/quickshell/
# Examine the theming singleton
cat /tmp/dots-hyprland/.config/quickshell/modules/theme/Colors.qml
```

The keybinding overlay widget (`CheatSheet.qml`) parses `~/.config/hypr/keybinds.conf` at runtime using a small regex-based QML parser, then renders it as a floating grid. This technique — treating your own config as a data source — is reusable in any Quickshell setup.

**What to extract**: The `Colors.qml` singleton pattern, the `FileWatcher`-based hot-reload loop, and the async subprocess wrapper in `AIChat.qml`.

### outfoxxed's configurations

- **URL**: https://git.outfoxxed.me (Quickshell author's own dotfiles)
- **Stack**: Quickshell reference implementation patterns
- **Notable**: Shows intended idioms directly from the framework author

Because this is the Quickshell author's personal configuration, it represents the canonical way to use the framework. Where community rices sometimes work around Quickshell's API with hacks, outfoxxed's config uses the API as designed. When you see something done differently here versus in a community rice, prefer the outfoxxed approach for long-term stability.

Key patterns to study: the `Scope` component for encapsulating IPC state, the `PanelWindow` anchoring model, and how `Variants` is used to generate per-monitor bar instances without duplicating QML.

```qml
// Per-monitor bar pattern using Variants (from outfoxxed idioms)
Variants {
    model: Quickshell.screens
    PanelWindow {
        property var modelData
        screen: modelData
        anchors {
            top: true; left: true; right: true
        }
        height: 36
        Bar { screen: modelData }
    }
}
```

**What to extract**: Use this repository as a style guide whenever you are unsure how Quickshell is supposed to work.

### ekremx25/quickshell

- **URL**: https://github.com/ekremx25/quickshell
- **Stack**: Hyprland / Niri / MangoWC + Quickshell
- **Style**: Material You, multi-compositor
- **Notable**: Multi-compositor abstraction layer, 10-band EQ widget, Pipewire integration

This rice solves a hard problem: making one shell config work across multiple Wayland compositors. The abstraction is a thin QML shim (`CompositorBackend.qml`) that exposes a normalized interface regardless of whether the underlying compositor speaks the Hyprland IPC protocol, the niri event socket, or a generic wlr-foreign-toplevel protocol.

The 10-band EQ widget wraps `easyeffects` via DBus. Studying this widget teaches you how to drive arbitrary DBus services from QML using `DBusServiceWatch` and `DBusObjectProxy`.

```qml
// DBus EQ integration sketch (ekremx25 pattern)
DBusServiceWatch {
    serviceName: "com.github.wwmm.easyeffects"
    onServiceRegistered: equalizerProxy.connected = true
    onServiceUnregistered: equalizerProxy.connected = false
}
DBusObjectProxy {
    id: equalizerProxy
    service: "com.github.wwmm.easyeffects"
    path: "/com/github/wwmm/easyeffects/effects/equalizer"
}
```

**What to extract**: The compositor abstraction layer and the DBus service integration pattern.

---

## Hyprland + Waybar Rices

Waybar remains the dominant bar solution for users who prefer JSON configuration over QML. Its plugin ecosystem is mature, its CSS styling is well-documented, and it starts faster than Quickshell for simple use cases. The rices in this section represent best-in-class Waybar usage.

Waybar's configuration splits into `config.jsonc` (layout and module parameters) and `style.css` (visual presentation). The split is clean but can cause confusion when a module's appearance depends on both files simultaneously — for example, a custom module that emits Pango markup will have its markup styles defined in CSS via class selectors. The rices below handle this cleanly.

### notwidgets dotfiles

- **Style**: Classic clean Hyprland + Waybar
- **Theme**: Catppuccin Mocha
- **Notable**: Minimal dependency footprint, easy to fork

This is a good "baseline" rice — it doesn't try to do everything, which makes it readable. The Waybar config uses only standard modules (workspaces, clock, pulseaudio, network, battery) but styles them with precise CSS that avoids the visual clutter common in beginner configs.

The Catppuccin Mocha palette is defined once in a CSS variable block at the top of `style.css` and referenced throughout. This means retheming requires changing only the variable block:

```css
/* Catppuccin Mocha variables */
:root {
    --base:    #1e1e2e;
    --mantle:  #181825;
    --crust:   #11111b;
    --text:    #cdd6f4;
    --subtext0:#a6adc8;
    --overlay0:#6c7086;
    --blue:    #89b4fa;
    --mauve:   #cba6f7;
    --red:     #f38ba8;
    --green:   #a6e3a1;
    --yellow:  #f9e2af;
    --peach:   #fab387;
}

window#waybar {
    background: var(--base);
    color: var(--text);
    font-family: "JetBrainsMono Nerd Font";
    font-size: 13px;
}
```

**What to extract**: The CSS variable theming pattern and the module configuration minimalism.

### prasanthrangan/hyprdots (HyDE)

- **URL**: https://github.com/prasanthrangan/hyprdots
- **Stack**: Hyprland + Waybar + multiple theme presets
- **Notable**: Theme switcher with 100+ presets, wallpaper-driven palette generation

HyDE (Hyprland Desktop Environment) is less a rice and more a full desktop environment framework built on dotfiles. Its theme switcher script, `themeswitch.sh`, is worth reading in full: it replaces color tokens in multiple config files simultaneously using `sed` substitution patterns backed by a theme manifest file.

The architecture: each theme lives in `~/.config/hyde/themes/<ThemeName>/` and contains a `theme.bash` file exporting color variables, a `waybar/style.css`, and a `hypr/colors.conf`. The switcher sources `theme.bash`, exports the variables, then runs `envsubst` over template config files:

```bash
# Simplified version of HyDE's theme switching core
THEME_DIR="$HOME/.config/hyde/themes/$1"
source "$THEME_DIR/theme.bash"

# Replace Waybar style
envsubst < "$THEME_DIR/waybar/style.css.tmpl" \
    > "$HOME/.config/waybar/style.css"

# Replace Hyprland colors
envsubst < "$THEME_DIR/hypr/colors.conf.tmpl" \
    > "$HOME/.config/hypr/colors.conf"

# Reload Waybar
pkill waybar && waybar &
```

**What to extract**: The `envsubst`-based theme template system and the theme manifest directory layout.

---

## Sway Rices

Sway is the mature, stable Wayland compositor for users who want the i3 workflow without X11. Its configuration syntax is nearly identical to i3's, making it the lowest-friction migration path from X11. Sway rices tend to prioritize functionality over visual spectacle, which makes them excellent references for workflow-oriented customization.

Sway uses wlroots under the hood and has first-class support for the wlr-protocols ecosystem. This means any tool built on `wlr-layer-shell`, `wlr-screencopy`, or `wlr-output-management` will work with Sway out of the box. Sway also has the most complete and stable `swaymsg` IPC API of any compositor, which enables automation scripts that would be fragile on Hyprland.

### swaywm example configs

- **Official wiki**: https://github.com/swaywm/sway/wiki/Sway-config-examples
- **Style**: Classic i3-aesthetic adapted for Wayland
- **Notable**: These are vetted by the Sway maintainers

The official example configs are underrated. They demonstrate correct use of `swaymsg` for scripting, proper output configuration with `swaymsg output`, and the recommended way to handle HiDPI with mixed-DPI multi-monitor setups:

```bash
# ~/.config/sway/config — HiDPI mixed monitor example
output eDP-1 scale 2 resolution 2560x1600@60Hz position 0,0
output DP-1  scale 1 resolution 2560x1440@144Hz position 1280,0

# Per-output background
output eDP-1 background ~/walls/laptop.jpg fill
output DP-1  background ~/walls/desktop.jpg fill

# Swaymsg scripting: move all windows on workspace 3 to DP-1
bindsym $mod+Shift+m exec swaymsg '[workspace=3] move workspace to output DP-1'
```

**What to extract**: Multi-monitor HiDPI handling and `swaymsg` IPC scripting patterns.

### ben9ex dotfiles

- **Style**: Minimal Sway + mako + waybar
- **Theme**: Gruvbox
- **Notable**: Extremely lean dependency graph, reproducible setup script

This configuration stands out for its discipline: it uses only packages available in every major distribution's main repositories, making it deployable on a fresh Fedora, Debian, or Arch install without AUR or COPR. The setup script (`install.sh`) documents every dependency explicitly, which is useful as a checklist when setting up a new machine.

The Gruvbox palette implementation in Waybar CSS:

```css
:root {
    --bg:      #282828;
    --bg1:     #3c3836;
    --bg2:     #504945;
    --fg:      #ebdbb2;
    --yellow:  #d79921;
    --orange:  #d65d0e;
    --red:     #cc241d;
    --green:   #98971a;
    --blue:    #458588;
    --purple:  #b16286;
    --aqua:    #689d6a;
}
```

The mako notification daemon configuration uses `criteria` blocks to style notifications by application, a feature that is commonly overlooked:

```ini
# ~/.config/mako/config
background-color=#282828
text-color=#ebdbb2
border-color=#504945
border-radius=6
default-timeout=5000
max-visible=5

[app-name=discord]
background-color=#3c3836
border-color=#458588

[urgency=critical]
background-color=#cc241d
text-color=#ebdbb2
border-color=#9d0006
ignore-timeout=1
```

**What to extract**: The mako criteria-based notification styling and the minimal dependency discipline.

---

## NixOS Flake Rices

NixOS rices represent a fundamentally different approach to dotfile management. Rather than placing files in `~/.config/`, a NixOS rice declares the entire system — packages, services, user configurations, and theming — as a reproducible Nix expression. The result is a configuration that can be reproduced byte-for-byte on any NixOS machine.

Home Manager (HM) is the standard tool for managing user-space configurations within NixOS flakes. It generates symlinks from the Nix store into `~/.config/`, which means you never edit config files directly — you edit the Nix source and run `home-manager switch`. This discipline initially feels restrictive but eliminates configuration drift entirely.

See **Chapter 29** for a complete walkthrough of NixOS flake architecture. This section focuses on repository-level patterns.

### Misterio77/nix-config

- **URL**: https://github.com/Misterio77/nix-config
- **Stack**: NixOS flake + Home Manager + Hyprland
- **Notable**: Excellent module architecture, color scheme as a flake input

This is the canonical example of a well-architected NixOS flake. The key insight is that the color scheme is passed as a flake input rather than hardcoded in modules. This allows Stylix or a custom theming module to consume the palette from a single source and distribute it to every program that needs colors:

```nix
# flake.nix — color scheme as input
{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    nix-colors.url = "github:misterio77/nix-colors";
  };

  outputs = { nixpkgs, home-manager, nix-colors, ... }@inputs: {
    homeConfigurations."user@host" = home-manager.lib.homeManagerConfiguration {
      modules = [
        nix-colors.homeManagerModules.default
        ./home.nix
      ];
      extraSpecialArgs = { inherit inputs; };
    };
  };
}
```

```nix
# home.nix — consuming the color scheme
{ config, inputs, ... }: {
  colorScheme = inputs.nix-colors.colorSchemes.catppuccin-mocha;
  
  programs.waybar = {
    enable = true;
    style = with config.colorScheme.palette; ''
      :root {
        --base:    #${base00};
        --surface: #${base01};
        --text:    #${base05};
        --accent:  #${base0D};
      }
    '';
  };
}
```

**What to extract**: The `nix-colors` input pattern and the palette-interpolation technique for generating CSS/configs from Nix color values.

### Frost-Phoenix/nixos-config

- **Theme**: Catppuccin Mocha
- **Stack**: Hyprland, clean Nix structure
- **Notable**: Readable module separation, good example of host-specific overrides

This configuration is notable for its readability. The module tree is shallower than Misterio77's, making it easier to understand as a second NixOS flake. Host-specific overrides are handled by a `hosts/` directory where each host's `configuration.nix` imports shared modules and overrides specific settings:

```nix
# hosts/desktop/configuration.nix
{ config, pkgs, ... }: {
  imports = [
    ../../modules/hyprland.nix
    ../../modules/waybar.nix
    ./hardware-configuration.nix
  ];
  
  # Host-specific overrides
  monitors = [
    { name = "DP-1"; width = 2560; height = 1440; refreshRate = 144; }
    { name = "HDMI-A-1"; width = 1920; height = 1080; refreshRate = 60; }
  ];
}
```

**What to extract**: The host-specific override pattern and the shallow module hierarchy for readability.

### ryan4yin/nix-config

- **URL**: https://github.com/ryan4yin/nix-config
- **Stack**: Multi-host NixOS with Hyprland
- **Notable**: Darwin + NixOS dual-platform support, detailed documentation

This config is exceptional for its documentation — nearly every non-obvious Nix expression has an inline comment explaining the decision. The dual Darwin/NixOS support is achieved through conditional module imports:

```nix
# Conditional platform imports
{ lib, pkgs, ... }: {
  home.packages = with pkgs; [
    # Wayland-specific tools (Linux only)
  ] ++ lib.optionals pkgs.stdenv.isLinux [
    hyprland
    waybar
    rofi-wayland
    wl-clipboard
  ] ++ lib.optionals pkgs.stdenv.isDarwin [
    # macOS equivalents
    aerospace
  ];
}
```

**What to extract**: The `lib.optionals` platform-conditional package pattern and the documentation discipline.

---

## Niri Rices

Niri is a scrollable-tiling Wayland compositor that entered serious production use in 2024–2025. Its tiling model is fundamentally different from Hyprland's or Sway's: windows are arranged in an infinite horizontal scroll rather than a fixed grid. This makes it excellent for ultra-wide monitors and multi-project workflows.

Niri's configuration format (`~/.config/niri/config.kdl`) uses KDL (KDL Document Language), which is more readable than Sway's i3-derived syntax for complex configurations. Niri supports the wlr-layer-shell protocol, so Waybar and Quickshell both work with it.

Niri rices are younger than Hyprland or Sway configurations — the ecosystem is smaller but growing rapidly. As of 2025, the `/r/hyprland` subreddit regularly features Niri migration posts, and the `#showcase` channel in the Niri Discord contains a growing collection.

```kdl
// ~/.config/niri/config.kdl — annotated starter
input {
    keyboard {
        xkb { layout "us" }
        repeat-delay 300
        repeat-rate 50
    }
    touchpad {
        tap
        natural-scroll
        dwt  // disable while typing
    }
}

output "eDP-1" {
    scale 2.0
    mode "2560x1600@60.000"
    position x=0 y=0
}

layout {
    gaps 12
    center-focused-column "never"
    preset-column-widths {
        proportion 0.333
        proportion 0.5
        proportion 0.667
        full-width
    }
    default-column-width { proportion 0.5 }
}

// Quickshell layer shell integration
layer-rule {
    match namespace="quickshell"
    shadow { on; }
}
```

The scrollable tiling model requires rethinking keybindings. Where Hyprland binds `focusleft`/`focusright`/`focusup`/`focusdown`, Niri binds `focus-column-left`/`focus-column-right`/`focus-window-up`/`focus-window-down`:

```kdl
binds {
    Mod+h { focus-column-left }
    Mod+l { focus-column-right }
    Mod+k { focus-window-up }
    Mod+j { focus-window-down }
    Mod+Shift+h { move-column-left }
    Mod+Shift+l { move-column-right }
    Mod+f { maximize-column }
    Mod+Shift+f { fullscreen-window }
}
```

**Recommended starting point for Niri rices**: Search the Niri GitHub Discussions under "show and tell" and the `#dotfiles` channel in the Niri Discord. Several comprehensive configs are linked there that are too new to have established GitHub star counts but are technically excellent.

---

## Finding More Rices

The following table summarizes the primary discovery channels for Wayland rices, with notes on the signal-to-noise ratio and what each source does best:

| Source | URL | Signal | Best For |
|---|---|---|---|
| r/unixporn | https://reddit.com/r/unixporn | Medium | Visual inspiration, stack identification |
| r/hyprland | https://reddit.com/r/hyprland | High | Hyprland-specific configs, troubleshooting |
| GitHub topic: dotfiles | https://github.com/topics/dotfiles?q=hyprland | High | Deep study, full repositories |
| GitHub topic: rice | https://github.com/topics/rice | Medium | Discovery of obscure setups |
| Hyprland Discord #showcase | discord.gg/hyprland | High | Cutting-edge, pre-public configs |
| Niri Discord #dotfiles | discord.gg/niri | High | Niri-specific, recent |
| Quickshell Discord | discord.gg/quickshell | Very High | QML patterns from active developers |
| AwesomeWM Wiki (X11) | wiki.archlinux.org | Low (Wayland) | Historical reference only |

When you find a rice on r/unixporn, the first thing to do is check the comments for a dotfiles link — many posts include one. If there is no link, use the `neofetch` / `fastfetch` output in the screenshot to identify the stack, then search GitHub for that combination of compositor + bar + color scheme.

### Using GitHub Search Effectively

GitHub's code search can find specific patterns across all public dotfiles repositories. Examples:

```bash
# Find all public configs using a specific Hyprland option
gh search code "monitor = , preferred, auto, 2" --language markdown

# Find Quickshell configs with a specific module pattern
gh search code "PanelWindow" --extension qml

# Find NixOS configs using nix-colors with Hyprland
gh search code "nix-colors" "hyprland" --extension nix
```

The GitHub topic system is also useful: repositories tagged `dotfiles`, `hyprland`, `ricing`, `wayland`, `nixos`, or `quickshell` form overlapping discovery sets. Combining two tags narrows results significantly.

---

## Annotated Dotfile Reading Guide

When you encounter a new rice repository, the temptation is to immediately copy the parts that look visually appealing. This leads to configs you don't understand and can't debug. The following systematic approach builds understanding first.

### Step 1: Compositor Configuration

Start with the compositor config: `~/.config/hypr/hyprland.conf`, `~/.config/sway/config`, `~/.config/niri/config.kdl`, or equivalent. This file establishes the fundamental environment: monitors, keybindings, window rules, and the autostart sequence. Read it in full before touching anything else.

Pay particular attention to:
- `exec-once` / `exec` lines — these reveal every daemon and background process in the stack
- `windowrulev2` / `for_window` rules — these show how specific applications are handled
- `input` section — reveals intended keyboard layout, touchpad behavior, and pointer settings
- `env` lines — exposes environment variables set at compositor startup (critical for Wayland compatibility)

```bash
# Quick extraction of all exec-once lines from a Hyprland config
grep -E '^exec(-once)?' ~/.config/hypr/hyprland.conf | sort

# Find all window rules
grep -E '^windowrulev2' ~/.config/hypr/hyprland.conf
```

### Step 2: Bar Configuration

After the compositor, read the bar config. For Waybar: `config.jsonc` + `style.css`. For Quickshell: the root `shell.qml` and the `Bar.qml` component. For AGS: the TypeScript entry point.

The bar config reveals:
- Which system services the rice monitors (network, audio, battery, etc.)
- How the rice handles workspaces and window titles
- The theming approach (hardcoded hex values vs. CSS variables vs. generated file)

### Step 3: Trace the Theme Pipeline

Identify where colors are defined and how they propagate. The answer is usually one of:

| Pipeline | Description |
|---|---|
| Hardcoded | Colors are literal hex values in each config file |
| CSS variables | A `:root {}` block in Waybar CSS defines palette |
| Generated file | A script writes `colors.conf` or `colors.css` from wallpaper |
| Nix module | `config.colorScheme.palette` interpolated at build time |
| Stylix | NixOS module auto-generates configs from a base16 palette |

```bash
# Find all hex color literals in a config directory
grep -r '#[0-9a-fA-F]\{6\}' ~/.config/ --include="*.css" --include="*.conf" \
    | grep -v '.git' | sort -u | head -40

# Check if matugen is in the autostart
grep -i 'matugen\|pywal\|wallust\|wpgtk' ~/.config/hypr/hyprland.conf
```

### Step 4: Map the Startup Sequence

The startup sequence determines what is running when you log in and in what order. A botched startup sequence (wrong order, missing dependencies) is the most common cause of broken rices after cloning.

```bash
# Reconstruct startup sequence from Hyprland config
grep -E '^exec' ~/.config/hypr/hyprland.conf | \
    nl -ba | \
    awk '{print $1"\t"$3" "$4" "$5" "$6}'
```

See **Chapter 53** for session startup management and how to use `systemd --user` targets to impose ordering on startup daemons.

### Step 5: Study the Keybindings

Keybindings reveal the author's workflow philosophy: how they think about window management, application launching, workspace organization, and system control. A well-designed keybinding scheme is internally consistent (similar operations share a modifier pattern) and minimal (no bindings for tasks that are rare enough to do through a launcher).

```bash
# Extract and tabulate all keybindings from a Hyprland config
grep '^bind' ~/.config/hypr/keybinds.conf | \
    awk -F'=' '{print $2}' | \
    column -t -s ',' | \
    sort
```

---

## Troubleshooting: Cloning and Running Someone Else's Config

Applying a public rice to your own machine almost always requires adaptation. The following problems occur most frequently.

### Missing Fonts

Most rices assume Nerd Fonts are installed. The most common is JetBrainsMono Nerd Font or FiraCode Nerd Font. Symptoms: boxes or question marks in the bar, incorrect icon rendering.

```bash
# Check which Nerd Font the rice uses
grep -r 'font-family\|font_family\|font =' /path/to/rice-config/ | \
    grep -i 'nerd\|mono\|code\|fira' | head -10

# Install on Arch
yay -S ttf-jetbrains-mono-nerd nerd-fonts-fira-code

# Install on Ubuntu/Debian
sudo apt install fonts-jetbrains-mono
# Then install the Nerd Font variant manually:
mkdir -p ~/.local/share/fonts
curl -Lo /tmp/jbm-nerd.zip \
    "https://github.com/ryanoasis/nerd-fonts/releases/latest/download/JetBrainsMono.zip"
unzip /tmp/jbm-nerd.zip -d ~/.local/share/fonts/JetBrainsMonoNerd/
fc-cache -fv
```

### Missing Dependencies

Identify all executables called in `exec-once` and bar module `exec` fields before cloning to your live config:

```bash
# Extract all executables from exec lines
grep -E '^exec' /path/to/hyprland.conf | \
    grep -oP '(?<=exec(-once)? = )[^ ]+' | \
    sort -u | \
    while read cmd; do
        which "$cmd" 2>/dev/null && echo "OK: $cmd" || echo "MISSING: $cmd"
    done
```

### Monitor Name Mismatch

The rice will have monitor names specific to the original author's hardware. Find your monitor names and update the `monitor =` lines:

```bash
# List connected outputs (run inside a Hyprland session)
hyprctl monitors | grep -E '^Monitor|description|id'

# Or from any Wayland session:
wlr-randr
# Or:
niri msg outputs
```

### Broken Waybar Modules

Custom modules with `exec` scripts fail silently if the script path is wrong or the script is not executable. Debug with:

```bash
# Test a Waybar custom module script directly
bash -x ~/.config/waybar/scripts/network-info.sh

# Check Waybar logs
journalctl --user -u waybar -f

# Or launch Waybar in foreground with debug output
waybar -l debug 2>&1 | grep -i error
```

### Hyprland IPC Version Mismatch

If you are on a different version of Hyprland than the rice author, some `hyprctl` commands or window rules may have changed syntax. Check:

```bash
hyprctl version
# Compare against the rice's last commit date on GitHub
# Then check the Hyprland changelog for breaking changes:
# https://github.com/hyprwm/Hyprland/releases
```

---

*Cross-references: Chapter 4 (Hyprland fundamentals), Chapter 12 (Waybar deep-dive), Chapter 18 (Quickshell architecture), Chapter 29 (NixOS flake patterns), Chapter 35 (color theming pipelines), Chapter 53 (session startup management).*

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
