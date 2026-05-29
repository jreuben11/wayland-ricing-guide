# Chapter 68 — COSMIC Desktop: System76's Rust DE

## Overview
COSMIC is System76's new desktop environment written entirely in Rust, built on
Smithay (cosmic-comp). It takes a novel approach: tiling and stacking in one,
with a unique "autotiling" mode. First stable release: COSMIC Alpha 1 (2024).

## Sections

### 68.1 Why COSMIC Is Different
- **Full Rust stack**: cosmic-comp (Smithay), cosmic-settings, cosmic-panel
- **Not GNOME, not KDE**: genuinely new design language
- **Autotile mode**: windows automatically tile, can be toggled per-workspace
- **Stacking + tiling**: switch modes freely
- **System76 backing**: funded development, ships on Pop!_OS hardware
- **Wayland-native from day 1**: no X11 legacy code

### 68.2 Installation

**Pop!_OS** (the natural home):
- Included as the default DE on Pop!_OS 24.04+

**Arch:**
```bash
# AUR packages
paru -S cosmic-epoch  # meta-package
# or individual components:
paru -S cosmic-comp cosmic-settings cosmic-panel cosmic-launcher
```

**NixOS:**
```nix
# Community flake (not yet official nixpkgs)
inputs.cosmic.url = "github:lilyinstarlight/nixos-cosmic";
services.desktopManager.cosmic.enable = true;
services.displayManager.cosmic-greeter.enable = true;
```

### 68.3 cosmic-comp: The Compositor

cosmic-comp is Smithay-based with a unique layout engine:
- **Float mode**: traditional stacking
- **Tile mode**: tiling with configurable gaps and proportions
- **Per-workspace mode**: each workspace has its own float/tile setting
- Switching: `Super+Y` toggles autotiling on current workspace

**Config:** `~/.config/cosmic/com.system76.CosmicComp/v1/`
(COSMIC uses its own config schema system, not INI/TOML/JSON)

### 68.4 COSMIC Panel

The top panel is separate from the compositor:
- Left: workspace switcher, app menu
- Center: clock (clickable for calendar)
- Right: system tray, quick settings

Applets are Rust crates compiled into the panel process. Adding a custom applet
requires writing Rust code and registering it with the panel daemon.

### 68.5 COSMIC Theming

COSMIC uses its own design tokens and theme system:
```
System Settings → Appearance
  → Color Scheme (Dracula, Catppuccin presets built-in)
  → Accent Color
  → Window Management (rounding, gaps)
  → Interface Density
```

**Catppuccin COSMIC:** https://github.com/catppuccin/cosmic

COSMIC themes are `.ron` (Rust Object Notation) files:
`~/.local/share/themes/cosmic/`

### 68.6 App Toolkit: iced + libcosmic

COSMIC apps are built with `iced` (Rust GUI framework) + `libcosmic`:
- Consistent look across all COSMIC apps
- Adaptive layout (phone/tablet/desktop)
- First-class accessibility

**COSMIC apps available:**
- `cosmic-files`: file manager
- `cosmic-term`: terminal (GPU-accelerated, Rust)
- `cosmic-edit`: text editor
- `cosmic-settings`: system settings
- `cosmic-launcher`: app launcher (Super key)

### 68.7 COSMIC vs. the Alternatives

| Aspect | COSMIC | Hyprland | KDE | GNOME |
|--------|--------|----------|-----|-------|
| Language | Rust | C++ | C++/QML | C/JS |
| Compositor base | Smithay | Aquamarine | KWin | Mutter |
| Tiling | Native (autotile) | Native | Extension | Extension |
| Theming | Token-based | Unlimited | Qt/Plasma | libadwaita |
| Maturity | Alpha/Beta | Stable | Very stable | Very stable |
| Ricing culture | Growing | Huge | Large | Medium |

### 68.8 Status and Roadmap (2025/2026)
- Alpha/Beta phase: daily-driveable but expect rough edges
- HDR: planned
- Fractional scaling: implemented
- NVIDIA: improving
- App ecosystem: growing rapidly
- Full release: targeted for Pop!_OS 25.04+
