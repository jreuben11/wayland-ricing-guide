# Chapter 62 — Opinionated Rice Bootstraps: Omarchy, ML4W, HyDE, CachyOS

## Contents

- [Overview](#overview)
- [62.1 What These Projects Are](#621-what-these-projects-are)
- [62.2 Omarchy — DHH's Developer Desktop](#622-omarchy-dhhs-developer-desktop)
- [62.3 ML4W — My Linux For Work](#623-ml4w-my-linux-for-work)
- [62.4 HyDE — Hyprland Desktop Environment](#624-hyde-hyprland-desktop-environment)
- [62.5 CachyOS — Optimized Arch with Hyprland ISO](#625-cachyos-optimized-arch-with-hyprland-iso)
- [62.6 EndeavourOS with Hyprland Community Edition](#626-endeavouros-with-hyprland-community-edition)
- [62.7 Comparison](#627-comparison)
- [62.8 Learning from Opinionated Setups](#628-learning-from-opinionated-setups)
- [62.9 Customizing From a Base](#629-customizing-from-a-base)
- [62.10 The Philosophical Divide](#6210-the-philosophical-divide)
- [Troubleshooting](#troubleshooting)

---


## Overview

Several projects bundle a complete, opinionated Arch + Hyprland setup that you
can install on bare hardware or into an existing Arch install. These are "rices
in a box" — useful as starting points, learning references, or daily drivers.
This chapter surveys the most actively maintained opinionated setups as of mid-2026,
explains how each one works at a technical level, and gives you the commands and
config patterns you need to either adopt one as-is or strip it for parts.

The projects covered here differ in scope. Omarchy is a pure Arch + dotfiles
bootstrapper. ML4W ships a GTK4 settings GUI on top of its dotfile stack. HyDE
provides a curated theme ecosystem of over 150 color schemes with a CLI manager.
CachyOS and EndeavourOS are full distributions that ship a Hyprland edition as an
installation target. Understanding the differences helps you pick the right
starting point — or decide to build from scratch using these as reference
implementations.

Before diving in, note that these projects change rapidly. The URLs, package
names, and command syntax shown here were current as of May 2026. Always check the
upstream README before running an install script on a machine you care about.
Cross-reference with Ch 53 (session startup and autostart), Ch 45 (Hyprland config
fundamentals), and Ch 58 (Waybar configuration) for the underlying primitives each
of these tools configure.

## 62.1 What These Projects Are

Rather than building from scratch, these tools give you a curated, working rice
with sensible defaults that you can then customize. They range from pure dotfiles
(Omarchy) to full installer scripts (ML4W, HyDE) to entire distributions (CachyOS
with Hyprland ISO). The common thread is that each project made hard choices so
you don't have to on day one — choices about which terminal, which launcher, which
notification daemon, which lock screen, and how all of these are wired together.

What distinguishes a good opinionated setup from a random dotfile dump is
integration coherence. Each component is tested against the others. Theming flows
consistently from the compositor to the bar to GTK apps. Keybindings follow a
logical scheme. The projects covered here all meet this bar, which is why they
have accumulated thousands of stars and active user communities.

From an architectural standpoint, opinionated setups are structured around a
small set of "touch points" — files that control everything else. In Hyprland-based
setups this is typically `hyprland.conf` (compositor and keybindings), a Waybar
JSON config (bar layout), a Rofi theme (launcher), and a GTK theme directory.
Once you understand where these touch points are in a given project, customizing
it is straightforward.

A word on sustainability: relying on an upstream opinionated setup means your
daily driver is at the mercy of someone else's update cadence. Most experienced
ricers use these projects as a bootstrap — install once, then detach from upstream
and evolve the config independently. The workflow for doing this cleanly is covered
in §62.9.

## 62.2 Omarchy — DHH's Developer Desktop

Omarchy (formerly Omakub) is David Heinemeier Hansson's (creator of Rails)
opinionated Arch Linux + Hyprland setup for developers. Launched June 2025,
current version 3.4.2 (March 2026). Used as the daily driver at 37signals
(Basecamp/HEY), which migrated its entire team from macOS to Linux using it. The
project's opinionated stance is its greatest strength and its most discussed
limitation: it makes very specific choices and doesn't try to be all things to all
users.

The design philosophy is "a developer's computer, not a power user's playground."
Omarchy ships a terminal-first workflow where almost everything is done from
Kitty. The GUI applications it includes — Chromium, Zoom, Spotify, LibreOffice —
are the minimum viable GUI layer needed for professional use. This is a deliberate
choice that mirrors how 37signals uses Linux: Neovim for editing, terminal for
Git and tooling, browser for everything web-based.

Omarchy's Hyprland configuration is among the cleanest in the opinionated-setup
space. It avoids animation overload, keeps decoration minimal, and uses a
consistent `SUPER` key scheme that maps closely to macOS muscle memory (SUPER+T
for terminal, SUPER+Space for launcher, SUPER+1-9 for workspaces). This makes it
particularly useful for macOS refugees who want a familiar mental model without
training wheels.

**Key characteristics:**
- Arch Linux base (not a separate distro — just Arch + scripts + dotfiles)
- Hyprland compositor with minimal, fast defaults
- Curated app stack: Neovim, Chromium, LibreOffice, Spotify, Zoom
- Full-disk encryption by default via `cryptsetup` + LVM
- Theme switcher with multiple Catppuccin and Gruvbox variants
- Menu system for common tasks via a custom `omarch` CLI
- Designed for single-user developer workstations

**Installation on a fresh Arch base:**

```bash
# Requires: base Arch install with sudo, git, curl
bash <(curl -s https://omarchy.org/install.sh)

# The installer will:
# 1. Install paru (AUR helper) if absent
# 2. Pull the omarchy package list (~80 packages)
# 3. Symlink dotfiles from ~/omarchy/ into ~/.config/
# 4. Run post-install hooks (font cache, systemd services)
# 5. Set zsh as default shell
```

**What you get after install:**

```
~/.config/
├── hypr/
│   ├── hyprland.conf          # Main compositor config
│   ├── keybinds.conf          # All SUPER key bindings
│   ├── windowrules.conf       # Per-app rules
│   └── autostart.conf         # Session autostart
├── waybar/
│   ├── config.jsonc           # Bar layout
│   └── style.css              # Bar colors + fonts
├── kitty/
│   ├── kitty.conf
│   └── themes/                # Color scheme files
├── nvim/ -> ~/omarchy/nvim/   # Symlinked LazyVim config
└── rofi/
    └── launchers/
```

**Theme switching with omarch:**

```bash
# List available themes
omarch theme list

# Apply a theme (updates hyprland border colors, waybar, GTK, kitty)
omarch theme catppuccin-mocha
omarch theme gruvbox-dark

# The theme command rewrites:
# ~/.config/hypr/colors.conf  (sourced by hyprland.conf)
# ~/.config/waybar/colors.css  (imported by style.css)
# ~/.config/gtk-3.0/settings.ini
# ~/.config/gtk-4.0/settings.ini
# ~/.config/kitty/current-theme.conf
```

**Customizing without fighting the installer:**

```bash
# Omarchy dotfiles live in ~/omarchy/
# Files are symlinked, so edits in ~/.config/ are reflected there

# To add a custom keybinding without modifying upstream files:
cat >> ~/.config/hypr/keybinds.conf << 'EOF'
# My custom bindings
bind = SUPER, F, exec, firefox
bind = SUPER SHIFT, S, exec, flameshot gui
EOF

# To override a waybar module, edit the JSONC directly:
nvim ~/.config/waybar/config.jsonc
```

**Repository:** https://github.com/basecamp/omarchy

## 62.3 ML4W — My Linux For Work

ML4W is a Hyprland dotfiles installer targeting developers and power users who
want more visual customization than Omarchy offers. It ships a GTK4 welcome
application that guides post-install setup and provides a theme browser. Where
Omarchy is deliberately minimal, ML4W leans into visual richness — animated
wallpapers, custom Rofi launchers with blur effects, and a richer Waybar layout
with system monitoring modules.

The ML4W project is accompanied by an extensive YouTube tutorial series (the
author, Stephan Raabe, publishes walkthroughs for each major feature). This makes
it exceptionally learner-friendly: you can follow along with a video while
configuring your system, rather than reading source code. The downside is that
this creates a learning dependency; the project is harder to maintain long-term if
you haven't watched the explanatory content.

ML4W's installer is more modular than Omarchy's. It separates dotfiles into
packages (core, apps, themes) and lets you opt out of components during install.
This makes it practical to take only the Hyprland + Waybar layer if you want ML4W's
bar aesthetic but prefer your own Neovim setup. The `ml4w-hyprland-settings`
package provides a GUI control panel that writes to the dotfile configs —
effectively a graphical settings app for your rice.

**Installation options:**

```bash
# Option A: from AUR (Arch/EndeavourOS/CachyOS)
paru -S ml4w-hyprland

# Option B: manual installer script
git clone https://github.com/mylinuxforwork/dotfiles
cd dotfiles
./install.sh

# The AUR package installs to /usr/share/ml4w/ and copies configs on first run
# The manual installer clones into ~/dotfiles/ and symlinks
```

**Core component stack:**

| Component | Package | Purpose |
|-----------|---------|---------|
| Compositor | hyprland | Window management |
| Bar | waybar | Status bar |
| Launcher | rofi-wayland | App launcher + menus |
| Notifications | dunst | Notification daemon |
| Wallpaper | swww | Animated wallpaper daemon |
| Lock screen | hyprlock | Compositor-native lock |
| Idle | hypridle | Idle management |
| Screenshot | grimblast + satty | Capture + annotate |
| Terminal | kitty | Terminal emulator |
| Shell | zsh + starship | Shell + prompt |

**Post-install welcome app:**

```bash
# Launch the ML4W Welcome app
ml4w-hyprland-welcome

# From within the app you can:
# - Browse and apply themes
# - Configure monitors
# - Set default browser/terminal
# - Open dotfile directories in Nautilus
```

**Animated wallpaper setup with swww:**

```bash
# swww daemon must be running (ML4W starts it via autostart.conf)
# To set a wallpaper:
swww img ~/Pictures/wallpaper.jpg \
  --transition-type grow \
  --transition-pos 0.5,0.5 \
  --transition-duration 1.5

# To cycle wallpapers randomly every 30 minutes:
# ML4W ships ~/.config/ml4w/scripts/wallpaper.sh
# Edit WALLPAPER_DIR to point to your collection
nvim ~/.config/ml4w/scripts/wallpaper.sh
```

**NVIDIA-specific profile activation:**

```bash
# ML4W detects NVIDIA at install time, but you can switch manually:
# Edit ~/.config/hypr/environments.conf
nvim ~/.config/hypr/environments.conf

# Ensure these are set for NVIDIA:
env = LIBVA_DRIVER_NAME,nvidia
env = __GLX_VENDOR_LIBRARY_NAME,nvidia
env = GBM_BACKEND,nvidia-drm
env = WLR_NO_HARDWARE_CURSORS,1       # if cursor is invisible
```

**Repository:** https://github.com/mylinuxforwork/dotfiles

## 62.4 HyDE — Hyprland Desktop Environment

HyDE (also called HyprDE) is the most comprehensive Hyprland rice installer
available. Its defining feature is a theme ecosystem of 150+ pre-built themes,
each of which coordinates wallpaper, Waybar color extraction, GTK theme, cursor,
icon pack, and Hyprland border colors. Switching themes is a single command.
This makes HyDE uniquely suited to users who want to dramatically change the look
of their desktop without touching config files.

Under the hood, HyDE's theming system works by extracting a color palette from
the active wallpaper using `pywal` or a similar tool, then applying derived colors
to all configured touch points. This means custom wallpapers automatically produce
matching system colors — a feature that puts HyDE well ahead of simpler dotfile
packs in terms of visual coherence. The `Hyde` CLI is a well-designed shell
script wrapper around this machinery.

HyDE's integration depth is its strength and its complexity cost. The project
ships scripts for nearly every common workflow: screenshot with annotation, screen
recording, Bluetooth pairing via Rofi, clipboard management with Cliphist, emoji
picking. The result is a desktop that feels complete out of the box but has many
more moving parts to understand. Plan on spending time reading the scripts in
`~/.config/hypr/scripts/` to understand what runs when.

**Installation (Arch-based):**

```bash
# Clone the repository
git clone --depth 1 https://github.com/prasanthrangan/hyprdots ~/HyDE
cd ~/HyDE/Scripts

# Run the installer (interactive, asks about NVIDIA/monitor config)
./install.sh

# For a minimal install (skip some optional packages):
./install.sh -m

# For reinstall/update preserving your modifications:
./install.sh -r
```

**Theme management with the Hyde CLI:**

```bash
# List all installed themes
Hyde theme list

# Apply a theme by name (case-insensitive partial match works)
Hyde theme set catppuccin-mocha
Hyde theme set gruvbox
Hyde theme set tokyonight

# Preview a theme without applying (requires gum):
Hyde theme preview

# List themes in a rofi menu:
Hyde theme menu
# Assign to a keybinding in hyprland.conf:
bind = SUPER SHIFT, T, exec, Hyde theme menu
```

**What a HyDE theme controls:**

```
Theme: catppuccin-mocha
├── Wallpaper:    ~/.config/hyde/themes/catppuccin-mocha/wallpaper.*
├── Waybar CSS:   Color palette derived from wallpaper via pywal
├── GTK theme:    ~/.config/gtk-3.0/ + gtk-4.0/ overrides
├── Cursor:       Specified in theme metadata file
├── Icons:        Specified in theme metadata file
├── Hyprland:     Border/gradient colors read from ~/.cache/wal/colors.sh
└── Rofi:         Color variables read from pywal cache
```

**Creating a custom HyDE theme:**

```bash
# Theme metadata lives in:
~/.config/hyde/themes/<theme-name>/

# Minimum required files:
# theme.conf  — name, gtk, cursor, icon, font settings
# wallpaper.*  — any image format swww supports

mkdir -p ~/.config/hyde/themes/my-theme
cat > ~/.config/hyde/themes/my-theme/theme.conf << 'EOF'
[Theme]
name=My Theme
gtk=Catppuccin-Mocha-Standard-Mauve-Dark
cursor=Bibata-Modern-Classic
icon=Papirus-Dark
font=JetBrainsMono Nerd Font 11
EOF

cp ~/Pictures/my-wallpaper.jpg ~/.config/hyde/themes/my-theme/wallpaper.jpg
Hyde theme set my-theme
```

**HyDE screenshot workflow:**

```bash
# Bound to PrintScreen by default:
# PrtSc         → region select, save to ~/Pictures/Screenshots/
# SUPER+PrtSc   → fullscreen screenshot
# SHIFT+PrtSc   → region select + annotate with satty

# The screenshot script:
cat ~/.config/hypr/scripts/screenshot.sh

# You can invoke manually:
~/.config/hypr/scripts/screenshot.sh area
~/.config/hypr/scripts/screenshot.sh full
```

**Repository:** https://github.com/prasanthrangan/hyprdots

## 62.5 CachyOS — Optimized Arch with Hyprland ISO

CachyOS is an Arch-based distribution with performance-optimized packages
(x86-64-v3/v4, PGO-compiled kernel) and a Hyprland ISO option. What sets CachyOS
apart from the dotfile-only projects is that it ships compiled binaries tuned for
modern CPU instruction sets — packages rebuilt with `-march=x86-64-v3` or
`-march=x86-64-v4` depending on your hardware profile. For CPU-bound workloads
(compilation, video encoding, package builds) the improvement is measurable.

The CachyOS kernel (`linux-cachyos`) applies a collection of upstream patches
before they land in mainline: the BORE scheduler (for interactive desktop
responsiveness), LATENCY_NICE support, and AMD/Intel power management improvements.
The scheduler change is particularly relevant for desktops: BORE prioritizes
foreground tasks more aggressively than CFS, reducing stutter during background
compilation or package updates. See Ch 71 for scheduler comparison benchmarks.

CachyOS ships its own repositories alongside Arch's official ones and the AUR.
The `cachyos-repository` package adds these repos to `pacman.conf` and provides
`pacman-cachyos` — a patched pacman with parallel downloads and zstd compression
enabled by default. You can add the CachyOS repos to an existing Arch install to
get the performance packages without reinstalling.

**Installing CachyOS Hyprland edition:**

```bash
# Download the Hyprland ISO from https://cachyos.org/download/
# Flash with:
dd if=cachyos-hyprland-*.iso of=/dev/sdX bs=4M status=progress oflag=sync
# or:
ventoy  # Put the ISO on a Ventoy USB, boot, select ISO

# The live environment boots directly into a working Hyprland session
# Launch the installer from the desktop or:
cachyos-installer
```

**Adding CachyOS repos to an existing Arch install:**

```bash
# Download the repo setup script
curl -O https://mirror.cachyos.org/cachyos-repo.tar.xz
tar xf cachyos-repo.tar.xz
cd cachyos-repo
sudo ./cachyos-repo.sh

# This adds to /etc/pacman.conf:
# [cachyos-v3]  (x86-64-v3 packages)
# [cachyos]     (x86-64-v2 packages, all CPUs)

# Install the optimized kernel:
sudo pacman -S linux-cachyos linux-cachyos-headers

# Install CachyOS settings (scheduler tuning, sysctl tweaks):
sudo pacman -S cachyos-settings
```

**CachyOS-specific Hyprland configuration:**

```bash
# CachyOS ships its own dotfiles for the Hyprland edition
# Config lives at:
~/.config/hypr/
~/.config/waybar/
~/.config/rofi/

# Update the CachyOS desktop rice:
sudo pacman -S cachyos-hyprland-settings

# The cachyos-hello app assists with post-install choices:
cachyos-hello
```

**Who should use CachyOS:** Users who want Arch's package ecosystem and rolling
release model but also want meaningful CPU performance gains without manually
patching and compiling packages. Particularly good for compile-heavy developer
workloads and users on AMD Zen 3/4 or Intel 12th-gen+ CPUs.

## 62.6 EndeavourOS with Hyprland Community Edition

EndeavourOS ships a Hyprland community edition ISO that provides a friendly path
to a functional Hyprland desktop without the full manual Arch install process.
The installer is Calamares — a standard GUI installer used by many distros — which
means partitioning, locale, and user setup are point-and-click rather than
command-line. The result is Arch-compatible packages and repositories with a
much lower time-to-desktop compared to a from-scratch install.

The EndeavourOS Hyprland edition is maintained by community contributors rather
than the core EOS team. This means the theming and config are less polished than
CachyOS's edition but benefit from direct community input and rapid iteration.
The community dotfiles are stored at the EOS GitHub org and accept PRs. If you
find a bug or want to contribute an improvement, the path to upstream is short.

EndeavourOS's post-install experience is built around `eos-update`, a wrapper
around pacman that also checks for reflector mirrors and AUR updates. The
`endeavouros-theming` package provides the EOS-branded GTK and icon themes.
For Hyprland users, the relevant post-install tool is `eos-hyprland-settings`,
which provides a small Yad-based GUI for monitor and input configuration.

**Installation workflow:**

```bash
# Download the Hyprland community ISO from:
# https://endeavouros.com/#Release
# (Select "Hyprland" under Community Editions)

# After install, run the EOS Welcome app which appears on first login:
eos-welcome

# Update all packages:
eos-update --yay   # includes AUR packages

# Install additional Hyprland utilities not in the default ISO:
yay -S hyprpicker hyprcursor hyprlock hypridle
```

**Post-install Hyprland tweaks for EOS:**

```bash
# EOS Hyprland config:
nvim ~/.config/hypr/hyprland.conf

# Fix monitor configuration (EOS leaves this as 'preferred'):
# Replace the default monitor line:
monitor = ,preferred,auto,1
# With your actual monitor setup:
monitor = DP-1,2560x1440@144,0x0,1
monitor = HDMI-A-1,1920x1080@60,2560x0,1

# EOS ships without hyprlock by default; add it:
yay -S hyprlock
cp /usr/share/hyprlock/hyprlock.conf ~/.config/hypr/hyprlock.conf
```

## 62.7 Comparison

The table below compares the five projects across dimensions that matter for
choosing a starting point. "Modification friction" is how hard it is to diverge
from defaults without fighting the project's update mechanism.

| Project | Type | Install time | Modification friction | NVIDIA support | Theme count | Best for |
|---------|------|-------------|----------------------|----------------|-------------|----------|
| Omarchy | Dotfiles script | ~20 min | Low (symlinks, fork-friendly) | Via env vars | ~8 | Developer workflows, macOS refugees |
| ML4W | Dotfiles + GUI | ~25 min | Low-medium (GUI writes configs) | Built-in profile | ~20 | Beginners who want to learn visually |
| HyDE | Dotfiles DE | ~30 min | Medium (many interacting scripts) | Detected at install | 150+ | Theme variety, turnkey rice |
| CachyOS | Full distro | ~15 min (ISO) | Low (standard Arch + custom packages) | Excellent | ~15 | Performance-first users |
| EndeavourOS | Full distro | ~15 min (ISO) | Low | Good | ~10 | Arch without the manual labor |

**Package manager compatibility:**

| Project | pacman | AUR (paru/yay) | Nix | Manual |
|---------|--------|----------------|-----|--------|
| Omarchy | Required | Required | No | Partial |
| ML4W | Required | Required | No | Yes |
| HyDE | Required | Required | No | Yes |
| CachyOS | Own repos | Yes | No | — |
| EndeavourOS | Arch-compat | Yes | No | — |

## 62.8 Learning from Opinionated Setups

Even if you ultimately build your own rice from scratch (as the rest of this book
teaches), spending time reading through these projects' configs is invaluable.
Omarchy's Hyprland config shows how a production-quality keybinding scheme is
structured. HyDE's theme switching scripts demonstrate how to apply color palettes
across multiple applications atomically. ML4W's YouTube series explains the "why"
behind configuration choices that documentation often skips.

A productive study pattern is to install one of these projects in a VM, get it
working, then open every config file and read it with the relevant chapter of this
book open alongside. You will encounter patterns documented in Ch 45 (hyprland.conf
structure), Ch 58 (Waybar modules), Ch 61 (Rofi theming), and Ch 53 (autostart)
in a working real-world context. This is far more effective than reading
documentation in isolation.

HyDE's scripts directory (`~/.config/hypr/scripts/`) is particularly educational.
Each script is a self-contained tool that demonstrates idiomatic Wayland scripting:
how to query `hyprctl` for window state, how to invoke `wl-clipboard` correctly,
how to coordinate `swww` and `pywal` for a wallpaper change. Read these before
writing your own utility scripts.

For font configuration, Omarchy's font stack is an excellent reference. It
installs `ttf-jetbrains-mono-nerd`, `noto-fonts`, `noto-fonts-emoji`, and
`noto-fonts-cjk` as a complete set that covers Latin, CJK, emoji, and Nerd Font
icons in a single coherent family. This prevents the "missing glyph rectangle"
problem in status bars and terminals. See Ch 37 for font installation and configuration.

## 62.9 Customizing From a Base

The recommended workflow for using an opinionated setup as a bootstrap — rather
than as a long-term upstream dependency — is: install, verify it works, then
detach from the upstream update mechanism and commit your config to your own Git
repository. This gives you the benefits of a working starting point without
the risk of future upstream updates breaking your customizations.

Omarchy and ML4W both use symlinks from a Git repository in `~/omarchy/` or
`~/dotfiles/` to `~/.config/`. The clean detachment workflow is to copy (not
symlink) the relevant config directories, then track your own copy in Git.
HyDE is more tightly integrated — its scripts reference internal paths — so plan
on either forking the whole project or maintaining a thin overlay on top.

```bash
# Fork Omarchy approach: copy the Hyprland config as your own baseline
git clone https://github.com/basecamp/omarchy ~/omarchy-base
cp -r ~/omarchy-base/.config/hypr ~/.config/hypr
cp -r ~/omarchy-base/.config/waybar ~/.config/waybar
cp -r ~/omarchy-base/.config/kitty ~/.config/kitty

# Initialize your own dotfiles repo:
mkdir ~/my-dotfiles && cd ~/my-dotfiles
git init
git add .
git commit -m "initial: based on omarchy 3.4.2"

# From now on, ~/.config/ is your territory, not omarchy's
```

```bash
# HyDE theme as a starting point — keep HyDE running, add personal overrides
Hyde theme set catppuccin-mocha

# Hyprland supports sourcing additional config files at the bottom of hyprland.conf:
echo "source = ~/.config/hypr/user.conf" >> ~/.config/hypr/hyprland.conf

# Create your personal overrides file (won't be touched by HyDE updates):
cat > ~/.config/hypr/user.conf << 'EOF'
# Personal overrides — sourced after HyDE defaults
general {
    border_size = 3
    gaps_in = 8
    gaps_out = 16
}
bind = SUPER, F, exec, firefox
bind = SUPER SHIFT, B, exec, bluetoothctl connect $(bluetoothctl devices | fzf | awk '{print $2}')
EOF
```

```bash
# ML4W customization: override without breaking the updater
# ML4W checks ~/.config/ml4w/settings/ for user overrides before applying defaults
mkdir -p ~/.config/ml4w/settings

cat > ~/.config/ml4w/settings/hyprland-custom.conf << 'EOF'
# My additions
windowrule = float, title:^(btop)$
windowrule = size 90% 85%, title:^(btop)$
bind = SUPER, G, exec, gimp
EOF

# Tell ML4W to source this file:
echo "source = ~/.config/ml4w/settings/hyprland-custom.conf" \
  >> ~/.config/hypr/hyprland.conf
```

## 62.10 The Philosophical Divide

The Wayland ricing community has a visible split between "from-scratch" and
"bootstrap" philosophy. From-scratch ricers argue that understanding every layer
is prerequisite to maintaining your setup over time — if you don't know why a
config line exists, you can't debug it when it breaks. Bootstrap ricers counter
that shipping a working desktop in an afternoon is a legitimate use of a tool, and
that incremental understanding can follow from a working system.

Both positions have merit, and the right choice depends on your situation. If
you're new to Wayland and want to understand how everything fits together, working
through this book from Ch 1 (Wayland fundamentals) and building your config piece
by piece is the deeper education. If you need a working development machine by
end of day and plan to customize over time, installing HyDE or ML4W and then
reading the config files is a perfectly sound approach.

What this book firmly opposes is cargo-culting: pasting config blocks you don't
understand and hoping they work. Whether your starting point is a blank Hyprland
config or an Omarchy install, the discipline is the same: read what you copy,
know what each line does, and maintain that understanding as you change things.

The projects described in this chapter are valuable precisely because their authors
made those choices deliberately and documented them. DHH's README explains why
Omarchy uses Chromium. HyDE's docs explain the pywal integration. Reading these
explanations is part of the learning, not just a step to skip on the way to a
pretty desktop.

## Troubleshooting

**Omarchy installer fails partway through**

```bash
# If the installer exits mid-run, check the log:
cat /tmp/omarchy-install.log

# Most failures are AUR build errors (missing dependencies) or network timeouts.
# Re-run the installer — it is designed to be idempotent:
bash <(curl -s https://omarchy.org/install.sh)

# If a specific package fails, install it manually then re-run:
paru -S <failing-package>
bash <(curl -s https://omarchy.org/install.sh)
```

**HyDE theme switching leaves artifacts (wrong bar colors after theme change)**

```bash
# HyDE writes colors to ~/.cache/wal/colors.sh; Waybar reads these at launch
# Force Waybar to reload:
pkill waybar && waybar &

# If GTK apps still show old colors, reset the GTK theme cache:
rm -rf ~/.cache/glib-2.0/
gsettings set org.gnome.desktop.interface gtk-theme 'Adwaita'  # reset
Hyde theme set <your-theme>  # reapply

# Verify pywal ran successfully:
cat ~/.cache/wal/colors.sh | head -20
```

**ML4W animated wallpapers not working (black screen or static)**

```bash
# Check swww daemon is running:
systemctl --user status swww-daemon.service
# If not:
swww-daemon &
swww img ~/Pictures/wallpaper.jpg

# swww requires a running Wayland compositor; verify WAYLAND_DISPLAY is set:
echo $WAYLAND_DISPLAY  # should output: wayland-1 (or similar)

# If swww crashes with GPU errors on NVIDIA:
export WLR_NO_HARDWARE_CURSORS=1
export GBM_BACKEND=nvidia-drm
swww-daemon &
```

**CachyOS: cachyos-v3 repo package conflicts with Arch main**

```bash
# If pacman reports conflicts after adding CachyOS repos:
# The v3 packages replace Arch packages; accept the replacements:
sudo pacman -Syu --needed

# To see which packages are from CachyOS repos:
pacman -Sl cachyos cachyos-v3 | grep installed

# If a specific package causes issues, pin it to Arch main:
# In /etc/pacman.conf, add to [options]:
# IgnorePkg = <package-name>
```

**All projects: Hyprland won't start after install (blank screen on login)**

```bash
# Check the Hyprland log:
cat ~/.local/share/hyprland/hyprland.log | tail -50

# Common causes:
# 1. NVIDIA: add to environment before exec-once or in /etc/environment:
export LIBVA_DRIVER_NAME=nvidia
export __GLX_VENDOR_LIBRARY_NAME=nvidia

# 2. XDG portal not starting — check:
systemctl --user status xdg-desktop-portal-hyprland.service
# Restart:
systemctl --user restart xdg-desktop-portal-hyprland.service

# 3. Wrong display server in SDDM/GDM — ensure you select "Hyprland" not "GNOME":
# At the login screen, look for a session selector (gear icon in SDDM)

# 4. Confirm hyprland binary is in PATH:
which hyprland
```

See Ch 53 for session startup debugging, Ch 45 for Hyprland config fundamentals,
and Ch 71 for performance tuning of Wayland compositors on specific hardware.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
