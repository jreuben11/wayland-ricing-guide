# Chapter 62 — Opinionated Rice Bootstraps: Omarchy, ML4W, HyDE, CachyOS

## Overview
Several projects bundle a complete, opinionated Arch + Hyprland setup that you
can install on bare hardware or into an existing Arch install. These are "rices
in a box" — useful as starting points, learning references, or daily drivers.

## Sections

### 62.1 What These Projects Are

Rather than building from scratch, these tools give you a curated, working rice
with sensible defaults that you can then customize. They range from pure dotfiles
(Omarchy) to full installer scripts (ML4W, HyDE) to entire distributions (CachyOS
with Hyprland ISO).

### 62.2 Omarchy — DHH's Developer Desktop

**What it is:**
Omarchy (formerly Omakub) is David Heinemeier Hansson's (creator of Rails)
opinionated Arch Linux + Hyprland setup for developers. Launched June 2025,
current version 3.4.2 (March 2026). Used as the daily driver at 37signals
(Basecamp/HEY), which migrated its entire team from macOS to Linux using it.

**Key characteristics:**
- Arch Linux base (not a separate distro — just Arch + scripts + dotfiles)
- Hyprland compositor
- Curated app stack: Neovim, Chromium, LibreOffice, Spotify, Zoom
- Full-disk encryption by default
- Theme switcher with multiple color schemes
- Menu system for common tasks
- Designed for single-user developer workstations

**Installation:**
```bash
# On fresh Arch install
bash <(curl -s https://omarchy.org/install.sh)
```

**What you get:**
- Hyprland config with sensible keybindings
- Waybar status bar
- Kitty terminal with configured themes
- Neovim pre-configured (LazyVim-based)
- Preconfigured font stack (JetBrains Mono Nerd Font)
- `omarch` CLI for theme switching and system management

**Omarchy's opinionated choices:**
- Chromium over Firefox (for the developer audience)
- No compositor animation tweaks — minimal, fast
- Terminal-first workflow
- No app store / GUI package manager

**Using Omarchy as a learning reference:**
Even if you don't install it, the Omarchy GitHub repo is valuable for seeing how
a production-quality Arch + Hyprland setup is structured. Fork it and customize.

**Repository:** https://github.com/basecamp/omarchy

### 62.3 ML4W — My Linux For Work

ML4W is a Hyprland dotfiles installer targeting developers and power users.
More customizable than Omarchy, with a GUI settings app.

**What it is:**
- Installer script for Arch/Endeavour/CachyOS
- Hyprland + Waybar + Rofi + Dunst + swww + lots more
- Multiple theme presets with live switching
- ML4W Welcome app (GTK4): guided setup, theme browser
- Actively maintained, YouTube tutorial series

**Installation:**
```bash
paru -S ml4w-hyprland
```

**Features:**
- Animated wallpaper support
- Built-in dotfile updater
- Multiple monitor support
- NVIDIA support profile
- Waybar modules with ML4W customizations

**Repository:** https://github.com/mylinuxforwork/dotfiles

### 62.4 HyDE (Hyprland Desktop Environment)

HyDE (also known as HyprDE) is the most comprehensive Hyprland rice installer.

**What it is:**
- Full "desktop environment" feel built on Hyprland
- 150+ built-in themes (theme switching with one command)
- Integrated tools: `hyprlock`, `hypridle`, `waybar`, custom scripts
- HYDE CLI for theme and configuration management
- Active GitHub community

**Features:**
- `Hyde theme set catppuccin-mocha` — instant theme switch
- Per-theme wallpaper + bar colors + GTK theme + cursor
- Screenshot with annotation workflow
- Workspace rules and keybinding reference card

**Installation (Arch):**
```bash
git clone --depth 1 https://github.com/prasanthrangan/hyprdots
cd hyprdots/Scripts && ./install.sh
```

**Repository:** https://github.com/prasanthrangan/hyprdots (HyprDE)

### 62.5 CachyOS — Optimized Arch with Hyprland ISO

CachyOS is an Arch-based distribution with performance-optimized packages
(x86-64-v3/v4, PGO-compiled kernel) and a Hyprland ISO option.

**Why it's different:**
- Real distribution (not just dotfiles) — has its own repositories
- Performance-tuned packages: cachyos-kernel, cachyos-settings
- Hyprland ISO: boot, install, get a working Hyprland in 10 minutes
- `cachyos-hello` and `cachyos-settings` for easy post-install config

**Who it's for:** Users who want Arch performance without manual optimization.

### 62.6 EndeavourOS with Hyprland Community Edition

EndeavourOS ships a Hyprland community edition ISO:
- Based on Arch, with a friendly installer (Calamares)
- Hyprland + preconfigured dotfiles from the community
- `eos-update` script for easy updates
- Active forum community

### 62.7 Comparison

| Project | Type | Customizability | Maintenance | Best for |
|---------|------|----------------|-------------|----------|
| Omarchy | Dotfiles script | High (fork it) | Active (DHH + team) | Developer workflows, macOS refugees |
| ML4W | Dotfiles installer | Very high | Active | Beginners who want to learn |
| HyDE | Dotfiles DE | High | Very active | Theme variety, turnkey rice |
| CachyOS | Full distro | High | Active | Performance-first users |
| EndeavourOS | Full distro | High | Active | Arch without the manual labor |

### 62.8 Learning from Opinionated Setups

These projects are also the best study material:
- Read Omarchy's Hyprland config to see production keybindings
- Study HyDE's theme switching scripts for palette engineering
- ML4W's YouTube series explains each component clearly

### 62.9 Customizing From a Base

```bash
# Fork Omarchy approach:
git clone https://github.com/basecamp/omarchy ~/omarchy-base
cp -r ~/omarchy-base/.config/hypr ~/.config/hypr
# Now customize from a working baseline

# HyDE theme as a starting point:
Hyde theme set catppuccin-mocha
# Then edit ~/.config/hypr/hyprland.conf to taste
```

### 62.10 The Philosophical Divide
- **From-scratch ricers**: control everything, understand everything
- **Bootstrap ricers**: functional fast, customize incrementally
- Neither is wrong — this book teaches from-scratch so you understand every layer,
  but Omarchy/HyDE/ML4W are valid if you need a working system today.
