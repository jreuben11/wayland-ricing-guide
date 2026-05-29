# Chapter 40 — Stylix: Auto-Theming Everything from One Wallpaper

## Overview

Stylix is a NixOS/Home Manager module that generates and applies a consistent color theme across
your entire system from a single wallpaper image or an explicit base16 palette declaration. Instead
of hand-editing color values in a dozen different config files — Waybar CSS, kitty.conf, foot.ini,
gtk.css, dunstrc, and so on — Stylix automates the entire propagation chain. You declare one source
of truth, rebuild, and every supported application receives a coherent, matching palette.

The module was created by danth and is now maintained under the nix-community umbrella. It targets
both NixOS system configurations and standalone Home Manager deployments, making it usable even on
non-NixOS distributions via Home Manager. Under the hood Stylix uses the
[base16](https://github.com/tinted-theming/home) specification, a palette system that assigns
semantic roles to exactly 16 colors and has been adopted by hundreds of terminal and editor themes.

Stylix integrates at the Nix evaluation layer: the colors are computed as Nix strings, injected into
application-specific config templates at build time, and written to disk before any application
launches. This means there is no runtime daemon, no IPC bus, and no need for live-reload hooks. The
cost is that a `home-manager switch` or `nixos-rebuild switch` is required whenever you change the
palette — but the guarantee you get in exchange is that the entire desktop is always consistent and
reproducible.

This chapter covers installation and flake integration, the full configuration surface, per-app
target tuning, custom template authoring, the Quickshell workaround, opacity and font management,
polarity and scheme selection, and a troubleshooting reference.

See **Ch 35** for GTK theming without Stylix and **Ch 36** for Qt theming without Stylix,
**Ch 34** for manual base16 palette management and color extraction tools, **Ch 41** for Catppuccin
and other theme ecosystems, and **Ch 53** for session startup order (relevant because GTK settings
must be visible before apps launch).

---

## 40.1 What Stylix Does

Stylix occupies a specific niche: it is not a theme in the traditional sense but a *theme
propagation engine*. You provide a stimulus — a JPEG/PNG wallpaper or an explicit YAML base16
scheme file — and Stylix derives or adopts a 16-color palette, then writes that palette into every
supported application's configuration directory under Home Manager management.

The derivation path when a wallpaper image is used relies on `imagemagick` or the
`matugen`/`colorthief` backends (configurable) to extract dominant colors, then maps those to the
base16 semantic slots: `base00` is the primary background, `base05` the primary foreground, `base0D`
the primary accent/blue, `base08` the error/red, and so on. The mapping algorithm varies by polarity
setting (`dark`, `light`, or `either`) and the chosen extraction backend.

When an explicit YAML scheme file is provided (e.g. from the `base16-schemes` or `tinted-schemes`
nixpkgs packages), Stylix skips extraction entirely and uses the declared values directly. This
gives pixel-perfect, community-validated palettes like Catppuccin Mocha, Gruvbox, Nord, or Tokyo
Night without any algorithmic approximation.

Supported application categories include:

| Category | Notable Apps |
|---|---|
| Terminal emulators | kitty, alacritty, foot, wezterm, ghostty |
| Editors | neovim, helix, emacs, vscode |
| Bars & launchers | waybar (CSS), rofi, wofi |
| Shell prompts | fish, bash, zsh, nushell |
| GTK 3 / 4 | system-wide GTK stylesheet + settings.ini |
| Qt / Kvantum | Kvantum SVG theme + qt5ct/qt6ct config |
| Browser | Firefox (userChrome/userContent), Chromium |
| Notifications | dunst, mako, swaync |
| Greeter / SDDM | greetd-tuigreet, sddm |
| Document viewers | zathura, evince |
| Other | spicetify (Spotify), steam, btop, cava |

The full canonical list is at https://stylix.danth.me/options/ and grows with each release.

---

## 40.2 Installation and Flake Integration

Stylix is distributed as a flake and must be added to your flake inputs before any module options
are available. The typical wiring for a NixOS + Home Manager co-located flake looks like this:

```nix
# flake.nix
{
  description = "My NixOS configuration";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    stylix = {
      url = "github:nix-community/stylix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, home-manager, stylix, ... } @ inputs: {
    nixosConfigurations.mymachine = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        ./configuration.nix
        home-manager.nixosModules.home-manager
        stylix.nixosModules.stylix        # NixOS-level targets (SDDM, grub, etc.)
        {
          home-manager.users.myuser = {
            imports = [
              stylix.homeModules.stylix   # user-level targets
              ./home.nix
            ];
          };
        }
      ];
    };
  };
}
```

For a standalone Home Manager setup (no NixOS), import only `stylix.homeModules.stylix` inside
your Home Manager `imports` list and omit `stylix.nixosModules.stylix`.

After adding the input, run `nix flake update stylix` to pin the latest version. Lock the input
when you want a stable baseline: simply commit your `flake.lock`. To update Stylix independently of
nixpkgs later, use `nix flake update stylix` again.

There are no additional package installations required — Stylix pulls in its own dependencies
(imagemagick, mustache tooling, base16 scheme files) through the Nix closure.

---

## 40.3 Basic Configuration

The minimum viable Stylix configuration requires only `enable = true` and a source for the palette.
Everything else has sensible defaults. A more realistic configuration that sets fonts, cursor, and
opacity looks like the following:

```nix
# home.nix or a dedicated stylix.nix module
{ config, pkgs, ... }:
{
  stylix = {
    enable = true;

    # Source of truth: derive palette from wallpaper image
    image = ./wallpapers/mountain-lake.jpg;

    # OR: use an explicit named scheme instead (comment out `image` above if scheme drives colors)
    # base16Scheme = "${pkgs.base16-schemes}/share/themes/catppuccin-mocha.yaml";
    # If both are set, base16Scheme wins for colors; image is still used as wallpaper.

    polarity = "dark";  # Hint for image-derived extraction: "dark" | "light" | "either"

    fonts = {
      monospace = {
        package = pkgs.nerd-fonts.jetbrains-mono;
        name    = "JetBrainsMono Nerd Font Mono";
      };
      sansSerif = {
        package = pkgs.inter;
        name    = "Inter";
      };
      serif = {
        package = pkgs.libertine;
        name    = "Linux Libertine O";
      };
      emoji = {
        package = pkgs.noto-fonts-emoji;
        name    = "Noto Color Emoji";
      };
      sizes = {
        desktop     = 10;
        applications = 11;
        terminal    = 12;
        popups      = 10;
      };
    };

    cursor = {
      package = pkgs.catppuccin-cursors.mochaDark;
      name    = "catppuccin-mocha-dark-cursors";
      size    = 24;
    };

    opacity = {
      terminal    = 0.92;
      desktop     = 1.0;
      popups      = 0.95;
      applications = 1.0;
    };
  };
}
```

The `image` field accepts any path, including `pkgs.fetchurl`-wrapped remote images. Derivation
paths produced by `builtins.fetchurl` or `pkgs.fetchurl` are valid. Relative paths like `./wp.jpg`
resolve relative to the Nix file that declares them, which is the most common pattern.

The `base16Scheme` field takes either a path to a YAML file or a derivation that produces one. The
`pkgs.base16-schemes` package ships many community palettes under
`share/themes/<name>.yaml`. You can also write an inline YAML scheme using `builtins.toFile`:

```nix
stylix.base16Scheme = builtins.toFile "my-scheme.yaml" ''
  scheme: "My Custom Palette"
  author: "me"
  base00: "1e1e2e"
  base01: "181825"
  base02: "313244"
  base03: "45475a"
  base04: "585b70"
  base05: "cdd6f4"
  base06: "f5e0dc"
  base07: "b4befe"
  base08: "f38ba8"
  base09: "fab387"
  base0A: "f9e2af"
  base0B: "a6e3a1"
  base0C: "94e2d5"
  base0D: "89b4fa"
  base0E: "cba6f7"
  base0F: "f2cdcd"
'';
```

---

## 40.4 Supported Applications: Enabling and Disabling Targets

Every supported application has a corresponding `stylix.targets.<name>.enable` option, which
defaults to `true` when the application is managed by Home Manager (i.e., its Home Manager module
is in scope). Stylix detects this automatically — it will not generate a kitty colorscheme unless
`programs.kitty.enable = true` is set somewhere in your configuration.

To disable Stylix theming for a specific application while keeping the application itself active:

```nix
stylix.targets.neovim.enable  = false;  # use LazyVim/Catppuccin plugin instead
stylix.targets.vscode.enable  = false;  # use VSCode marketplace theme
stylix.targets.firefox.enable = false;  # manage userChrome manually
stylix.targets.helix.enable   = false;  # helix has its own theme system
```

Some targets have additional sub-options beyond the toggle:

```nix
# Waybar: control which CSS variables are injected
stylix.targets.waybar = {
  enable          = true;
  enableLeftBackColors  = true;
  enableCenterBackColors = true;
  enableRightBackColors  = true;
};

# GNOME: choose which GNOME Shell extensions are themed
stylix.targets.gnome.enable = true;   # themes gnome-shell, nautilus, etc.

# Spicetify (Spotify)
stylix.targets.spicetify.enable = true;

# btop: generates btop.conf color section
stylix.targets.btop.enable = true;
```

A full enumeration of target names can be discovered via `nix eval .#homeConfigurations.myuser.config.stylix.targets --apply builtins.attrNames` after wiring is complete, or by reading https://stylix.danth.me/options/programs.html.

---

## 40.5 Qt and GTK via Stylix

Stylix handles both toolkit theming subsystems in a unified way, sparing you from manually
configuring `qt5ct`, `qt6ct`, `Kvantum`, `gtk-settings.ini`, and `colors.css` separately. This is
one of the highest-value features for Wayland ricing because toolkit theme inconsistency is one of
the most visible aesthetic problems.

For **GTK**, Stylix generates a GTK3 theme (written to `~/.local/share/themes/stylix/`) and a
corresponding `gtk-4.0/gtk.css` override, and writes `~/.config/gtk-3.0/settings.ini` and
`~/.config/gtk-4.0/settings.ini` pointing at it. Font, cursor, and icon settings are also written
here so that GTK applications inherit them.

```nix
stylix.targets.gtk.enable    = true;   # default: true when programs.gtk is managed by HM
stylix.targets.gtk.flatpakSupport.enable = false; # opt-in Flatpak override (writes to ~/.local)
```

For **Qt**, Stylix configures Kvantum by writing a generated `stylix.kvconfig` and
`stylix.svg` into `~/.config/Kvantum/stylix/`, and writes `~/.config/qt5ct/qt5ct.conf` and
`~/.config/qt6ct/qt6ct.conf` to select Kvantum as the style with the generated theme.

```nix
stylix.targets.qt.enable = true;   # default: true when qt.enable is set in HM

# Ensure the qt HM module is active to get env vars set:
qt = {
  enable   = true;
  style.name = "kvantum";   # Stylix sets this automatically when target is enabled
};
```

After a `home-manager switch`, launch `kvantummanager` to visually inspect the generated theme.
Qt applications should automatically pick up the new style. If they do not, verify that
`QT_STYLE_OVERRIDE=kvantum` is set in your environment (see Ch 38 for GTK/Qt env var wiring).

---

## 40.6 Font Management via Stylix

Stylix declares fonts for four semantic slots — `monospace`, `sansSerif`, `serif`, and `emoji` —
and writes them into every targeted application's config. This means changing `fonts.monospace` in
one place updates kitty, alacritty, foot, wezterm, rofi, waybar, GTK font settings, and any other
supported app simultaneously.

The `fonts.sizes` sub-options control per-context scaling:

| Option | Affects |
|---|---|
| `sizes.desktop` | Desktop environment font size (gtk settings) |
| `sizes.applications` | General application windows |
| `sizes.terminal` | Terminal emulator font size |
| `sizes.popups` | Notifications, tooltips, popups |

```nix
stylix.fonts = {
  monospace = {
    package = pkgs.nerd-fonts.fira-code;
    name    = "FiraCode Nerd Font Mono";
  };
  sansSerif = {
    package = pkgs.roboto;
    name    = "Roboto";
  };
  serif = {
    package = pkgs.noto-fonts;
    name    = "Noto Serif";
  };
  emoji = {
    package = pkgs.noto-fonts-emoji;
    name    = "Noto Color Emoji";
  };
  sizes = {
    desktop      = 10;
    applications = 11;
    terminal     = 13;
    popups       = 10;
  };
};
```

Nerd Fonts in nixpkgs as of late 2024 moved from `pkgs.nerdfonts` (the monolithic package) to
`pkgs.nerd-fonts.<font-name>` (individual packages). Use the split packages to avoid downloading
hundreds of fonts:

```nix
# Correct post-2024 syntax:
pkgs.nerd-fonts.jetbrains-mono
pkgs.nerd-fonts.fira-code
pkgs.nerd-fonts.hack
pkgs.nerd-fonts.iosevka

# Old (still works but downloads all Nerd Fonts):
pkgs.nerdfonts.override { fonts = [ "JetBrainsMono" "FiraCode" ]; }
```

---

## 40.7 Custom Templates: Theming Unsupported Applications

For applications not in Stylix's built-in target list, you can inject palette values directly via
Home Manager's `home.file` or `xdg.configFile` using Nix string interpolation. The color values are
exposed on `config.lib.stylix.colors` as:

- `base00` through `base0F` — hex values without `#` prefix (e.g. `"1e1e2e"`)
- `withHashtag.base00` through `withHashtag.base0F` — hex values with `#` prefix (e.g. `"#1e1e2e"`)
- `rgb.base00.r`, `.g`, `.b` — decimal 0–255 component values
- `dec.base00.r`, `.g`, `.b` — decimal 0.0–1.0 component values (useful for Cairo/Wayland protocols)

Example: generating a color config for `swaylock-effects`:

```nix
{ config, ... }:
let c = config.lib.stylix.colors.withHashtag; in
{
  programs.swaylock = {
    enable   = true;
    settings = {
      color           = config.lib.stylix.colors.base00;
      bs-hl-color     = config.lib.stylix.colors.base08;
      caps-lock-bs-hl-color = config.lib.stylix.colors.base09;
      caps-lock-key-hl-color = config.lib.stylix.colors.base0A;
      inside-color    = config.lib.stylix.colors.base01;
      inside-clear-color = config.lib.stylix.colors.base01;
      inside-ver-color   = config.lib.stylix.colors.base01;
      inside-wrong-color = config.lib.stylix.colors.base01;
      key-hl-color    = config.lib.stylix.colors.base0B;
      layout-bg-color = config.lib.stylix.colors.base00;
      layout-border-color = config.lib.stylix.colors.base03;
      layout-text-color   = config.lib.stylix.colors.base05;
      line-color      = config.lib.stylix.colors.base03;
      ring-color      = config.lib.stylix.colors.base0D;
      ring-clear-color = config.lib.stylix.colors.base0C;
      ring-ver-color   = config.lib.stylix.colors.base0D;
      ring-wrong-color = config.lib.stylix.colors.base08;
      text-color       = config.lib.stylix.colors.base05;
      text-clear-color = config.lib.stylix.colors.base05;
      text-ver-color   = config.lib.stylix.colors.base05;
      text-wrong-color = config.lib.stylix.colors.base08;
    };
  };
}
```

Example: a raw INI file for an app with no Home Manager module:

```nix
{ config, ... }:
let c = config.lib.stylix.colors; in
{
  home.file.".config/cava/config".text = ''
    [color]
    method = fixed
    fixed = ${c.withHashtag.base0D}
    background = ${c.withHashtag.base00}
  '';
}
```

Example: a CSS file for a custom rofi theme that extends the generated base:

```nix
{ config, ... }:
let c = config.lib.stylix.colors.withHashtag; in
{
  xdg.configFile."rofi/custom-override.rasi".text = ''
    * {
      background-color: ${c.base00};
      border-color:     ${c.base0D};
      text-color:       ${c.base05};
      selected-bg:      ${c.base02};
      selected-fg:      ${c.base0D};
      urgent-bg:        ${c.base08};
      urgent-fg:        ${c.base00};
    }
  '';
}
```

---

## 40.8 Polarity and Scheme Selection

The `polarity` option tells Stylix's color extraction algorithm whether to treat the wallpaper as a
dark or light image. It has three values:

| Value | Behavior |
|---|---|
| `"dark"` | Maps dominant dark colors to backgrounds, light colors to foregrounds |
| `"light"` | Inverts the mapping; best for pastel/light wallpapers |
| `"either"` | Stylix chooses based on image luminance analysis (default) |

Polarity only affects image-derived palettes. When `base16Scheme` is set explicitly, polarity is
ignored because the YAML file already encodes whether it is dark or light.

Selecting a named scheme is the most reliable way to get predictable results. The
`pkgs.base16-schemes` package (or `pkgs.tinted-schemes` for a superset) ships YAML files for
dozens of well-known palettes:

```nix
# List available schemes:
# ls $(nix build nixpkgs#base16-schemes --print-out-paths)/share/themes/
#
# Notable options:
stylix.base16Scheme = "${pkgs.base16-schemes}/share/themes/gruvbox-dark-hard.yaml";
stylix.base16Scheme = "${pkgs.base16-schemes}/share/themes/nord.yaml";
stylix.base16Scheme = "${pkgs.base16-schemes}/share/themes/tokyo-night-dark.yaml";
stylix.base16Scheme = "${pkgs.base16-schemes}/share/themes/dracula.yaml";
stylix.base16Scheme = "${pkgs.base16-schemes}/share/themes/solarized-dark.yaml";
stylix.base16Scheme = "${pkgs.base16-schemes}/share/themes/onedark.yaml";
stylix.base16Scheme = "${pkgs.base16-schemes}/share/themes/catppuccin-mocha.yaml";
stylix.base16Scheme = "${pkgs.base16-schemes}/share/themes/catppuccin-latte.yaml";
```

You can generate a scheme dynamically from a wallpaper using `matugen` and capture the output in a
derivation, then feed that to `base16Scheme`. This is an advanced pattern used when you want both a
specific wallpaper *and* a precisely tuned palette without manual color picking.

---

## 40.9 Stylix + Quickshell Integration

As of 2025, Stylix does not ship a built-in Quickshell target. Since Quickshell is QML-based,
theming goes through QML singletons rather than flat config files, requiring a small hand-written
bridge. The approach is to generate a QML Singleton file via `home.file` using Stylix color values,
and then `import` it from your Quickshell config.

**Step 1 — Generate the singleton:**

```nix
{ config, ... }:
let c = config.lib.stylix.colors.withHashtag; in
{
  home.file.".config/quickshell/theme/Colors.qml".text = ''
    pragma Singleton
    import Quickshell

    Singleton {
      // Base palette (base16)
      readonly property color base00: "${c.base00}"   // bg
      readonly property color base01: "${c.base01}"   // bg alt
      readonly property color base02: "${c.base02}"   // bg selection
      readonly property color base03: "${c.base03}"   // comment / inactive
      readonly property color base04: "${c.base04}"   // fg dim
      readonly property color base05: "${c.base05}"   // fg
      readonly property color base06: "${c.base06}"   // fg bright
      readonly property color base07: "${c.base07}"   // fg strongest
      readonly property color base08: "${c.base08}"   // red / error
      readonly property color base09: "${c.base09}"   // orange
      readonly property color base0A: "${c.base0A}"   // yellow / warning
      readonly property color base0B: "${c.base0B}"   // green / success
      readonly property color base0C: "${c.base0C}"   // cyan
      readonly property color base0D: "${c.base0D}"   // blue / accent
      readonly property color base0E: "${c.base0E}"   // magenta / purple
      readonly property color base0F: "${c.base0F}"   // brown / deprecated

      // Semantic aliases for ergonomic access
      readonly property color background:    base00
      readonly property color surface:       base01
      readonly property color overlay:       base02
      readonly property color muted:         base03
      readonly property color subtle:        base04
      readonly property color text:          base05
      readonly property color accent:        base0D
      readonly property color accentAlt:     base0E
      readonly property color success:       base0B
      readonly property color warning:       base0A
      readonly property color error:         base08
    }
  '';
}
```

**Step 2 — Declare the singleton in `qmldir`:**

```nix
home.file.".config/quickshell/theme/qmldir".text = ''
  module theme
  singleton Colors 1.0 Colors.qml
'';
```

**Step 3 — Use in your QML components:**

```qml
// bar/Bar.qml
import Quickshell
import "../../theme" as Theme

Rectangle {
    color: Theme.Colors.background

    Text {
        color: Theme.Colors.text
        font.family: "JetBrainsMono Nerd Font Mono"
        font.pixelSize: 13
    }
}
```

After `home-manager switch`, the generated `Colors.qml` file will contain the current palette's hex
values. When you change the wallpaper or scheme and rebuild, the file is atomically replaced by Nix,
and Quickshell will pick up the new values on next launch or reload.

---

## 40.10 Opacity Configuration

Stylix manages transparency for supported terminal emulators and other apps through the `opacity`
attribute set. Values range from `0.0` (fully transparent) to `1.0` (fully opaque).

```nix
stylix.opacity = {
  terminal     = 0.90;   # kitty, alacritty, foot, wezterm, ghostty
  desktop      = 1.0;    # desktop background rendering (for compositors that read it)
  popups       = 0.88;   # notification daemons (dunst/mako), rofi
  applications = 1.0;    # general GUI apps
};
```

Note that opacity in terminals is a background-color alpha channel setting, not a compositor
window-level transparency. For window-level transparency (e.g. Hyprland `windowrule = opacity`),
you configure that in your compositor rules independently of Stylix. The two levels compose: a
terminal window with `stylix.opacity.terminal = 0.9` *plus* a Hyprland `opacity 0.9` rule gives
you roughly `0.9 × 0.9 ≈ 0.81` effective opacity. See **Ch 22** for Hyprland window rule syntax.

---

## 40.11 Workflow: From Wallpaper to Complete Rice

The full end-to-end workflow once Stylix is wired up is genuinely fast:

1. Place a new wallpaper at `~/wallpapers/new.jpg` (or reference it in your flake via a store path).
2. Update `stylix.image = ./wallpapers/new.jpg` in your Home Manager config.
3. Optionally set `stylix.polarity = "dark"` or `"light"` to guide extraction.
4. Run `home-manager switch` (standalone) or `sudo nixos-rebuild switch` (NixOS).
5. Log out and back in, or restart affected processes (`hyprctl reload`, `pkill waybar`, etc.).
6. Every Stylix-managed application now reflects the new palette — no manual editing required.

For iterating quickly on a palette without committing to a wallpaper, use an explicit `base16Scheme`
and swap scheme files. You can keep several scheme declarations in a Nix let-binding and toggle
between them with a single line change:

```nix
let
  darkScheme  = "${pkgs.base16-schemes}/share/themes/catppuccin-mocha.yaml";
  lightScheme = "${pkgs.base16-schemes}/share/themes/catppuccin-latte.yaml";
  nordScheme  = "${pkgs.base16-schemes}/share/themes/nord.yaml";
in {
  stylix.base16Scheme = darkScheme;  # switch this variable to change theme
}
```

Committing the wallpaper image to your dotfiles repository (even as a relatively small file) means
that `nixos-rebuild switch` on any machine in the same flake will reproduce the exact same palette,
completing the NixOS reproducibility guarantee all the way to the aesthetics layer.

---

## 40.12 Selective Overrides within Styled Applications

Sometimes you want Stylix to handle 95% of an application's theming but override a specific color
or value. For applications configured through Home Manager module options, you can write additional
settings after Stylix's defaults using `lib.mkForce` or simple attribute-level overrides, since
Stylix uses regular priority `mkDefault`:

```nix
# Override one waybar color while keeping the rest Stylix-generated:
programs.waybar.style = lib.mkAfter ''
  #workspaces button.active {
    background: #${config.lib.stylix.colors.base0B};  /* use green instead of accent */
    color: #${config.lib.stylix.colors.base00};
  }
'';
```

```nix
# Force a specific neovim background that Stylix would otherwise set:
programs.neovim.extraLuaConfig = lib.mkAfter ''
  vim.cmd("highlight Normal guibg=#0d0d0d")
'';
```

For kitty, the generated colorscheme is written to `~/.config/kitty/colors.conf` and included by
`stylix`'s kitty config injection. You can append `include ~/.config/kitty/overrides.conf` after
it and put your overrides there, then manage `~/.config/kitty/overrides.conf` with `home.file`.

---

## Troubleshooting

**Colors are not applied after `home-manager switch`**

Stylix-generated files land in the Nix store and are symlinked into `~` by Home Manager. Verify
the symlinks exist with `ls -la ~/.config/kitty/colors.conf` (should point into `/nix/store/…`).
If the symlink is missing, check that `programs.kitty.enable = true` is set — Stylix targets only
activate for apps that Home Manager is managing.

**Waybar CSS is not being injected**

Ensure `stylix.targets.waybar.enable = true` and that `programs.waybar.enable = true` is set. If
you are providing `programs.waybar.style` as a plain string, Stylix may not be able to prepend to
it. Use `lib.mkBefore` or structure your style as a list and let Stylix insert its block:

```nix
programs.waybar.style = lib.mkBefore ''
  /* my custom rules that come before Stylix defaults */
'';
```

**Qt applications still use the wrong theme**

Check that `QT_STYLE_OVERRIDE=kvantum` and `QT_QPA_PLATFORMTHEME=qt5ct` (or `qt6ct`) are exported
in your environment. These variables must be set before any Qt application launches — typically in
your `.profile` or session startup script. See **Ch 53** for session startup env var wiring. Also
confirm that the Kvantum manager is not overriding to a different theme interactively.

**GTK apps have wrong fonts despite Stylix font config**

Run `gsettings get org.gnome.desktop.interface font-name` to see what GTK is currently reading. If
it does not match your Stylix font, the `~/.config/gtk-3.0/settings.ini` generated by Stylix may be
shadowed by an older file. Remove or inspect `~/.config/gtk-3.0/settings.ini` manually, then
re-run `home-manager switch`. Also ensure `stylix.targets.gtk.enable = true`.

**Image-derived colors look bad / washed out**

Switch from image derivation to an explicit `base16Scheme`. Image-based extraction is inherently
imprecise for photos with complex color distributions. Use a YAML scheme from `pkgs.base16-schemes`
or author a custom one as shown in section 40.3. Keep `stylix.image` set to your wallpaper for the
wallpaper-setting functionality but let `base16Scheme` govern colors.

**Quickshell Colors.qml is not found at runtime**

Verify the file exists at `~/.config/quickshell/theme/Colors.qml` after `home-manager switch`. If
it is missing, ensure the `home.file` declaration is actually evaluated (no `lib.mkIf false` wrapping
it, no typo in the attribute path). Double-check the `qmldir` file at
`~/.config/quickshell/theme/qmldir` lists `Colors` correctly. QML module resolution requires the
directory containing `qmldir` to be on the import path, either via `QML2_IMPORT_PATH` or by using a
relative `import "../theme"` path from your QML files.

**`nix flake update stylix` breaks existing configuration**

Stylix occasionally makes breaking changes between releases, usually renaming target options or
changing the font/cursor API. Read the Stylix changelog at
`https://github.com/nix-community/stylix/blob/master/CHANGELOG.md` after each update. Most
breakages manifest as `error: attribute 'X' missing` in `nix eval` and are fixed by renaming the
affected option in your config.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
