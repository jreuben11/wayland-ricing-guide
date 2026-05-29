# Chapter 83 — Package Manager TUI Tools: paru, pacseek, nix-search, Flatpak

## Overview

Daily package management in a terminal-centric rice benefits enormously from TUI and CLI tools that go beyond the bare-minimum interfaces of `pacman`, `nix-env`, or `apt`. The friction of looking up package names in a browser, copying commands, and running multiple queries can be collapsed into a single interactive session with the right tooling. A polished package manager experience is as much a part of your rice as your bar configuration or color scheme.

This chapter covers three distinct package ecosystems — Arch Linux / AUR, NixOS / Nix flakes, and the universal Flatpak system — along with containerization tools (Distrobox) for cross-distro package access. Each section provides installation instructions, daily-use workflows, configuration tips, and integration patterns suited to a Wayland-first environment.

Package manager TUI tools integrate naturally with terminal emulators like Kitty or Foot (see Ch 14) and can be launched from application launchers such as fuzzel or Rofi-Wayland (see Ch 42). When combined with a well-configured shell (Ch 71) and `tmux` or `zellij` session management (Ch 72), package operations become a seamless part of your workflow rather than an interruption.

The philosophy throughout is: reduce context-switching, give rich information at the point of decision, and make rollback or cleanup as easy as installation. Each tool covered here satisfies at least two of those three goals.

---

## 83.1 Arch: AUR Helpers

### paru — The Recommended AUR Helper

**paru** is written in Rust and wraps `pacman` with AUR support, a built-in review step, and sensible defaults. It is maintained by the same developer as the older `yay` and is now the community consensus recommendation for most Arch users.

paru is designed to be a drop-in `pacman` replacement: every `pacman` flag works, and AUR packages are handled transparently. The key difference from running `pacman` directly is that paru resolves AUR dependencies automatically, presents PKGBUILDs for review before building, and cleans up build artifacts when configured to do so.

Installation requires bootstrapping from the AUR itself, which only needs to happen once. After that, `paru -Syu` keeps both official and AUR packages current in a single command:

```bash
# Bootstrap paru from the AUR (requires base-devel group)
sudo pacman -S --needed git base-devel
git clone https://aur.archlinux.org/paru-bin.git
cd paru-bin
makepkg -si
cd ..
rm -rf paru-bin

# Verify installation
paru --version
```

Daily usage mirrors `pacman` with AUR awareness:

```bash
paru -S package-name           # install from official repos or AUR
paru -Syu                      # full system update (official + AUR)
paru -Ss keyword               # search (official + AUR, with AUR stats)
paru -Si package-name          # detailed package info
paru -Rns package-name         # remove package + orphan deps + config files
paru -Qdtq | paru -Rns -       # remove all orphaned packages
paru --cleanafter              # remove build files after each install
paru -Gc package-name          # display AUR comments for the package
paru --fm bat -S package-name  # use bat to review PKGBUILD with syntax highlighting
```

paru's configuration file lives at `~/.config/paru/paru.conf`. Key options to set early:

```ini
# ~/.config/paru/paru.conf
[options]
BottomUp          # show AUR results below official (less noise)
SudoLoop          # keep sudo alive during long builds
CleanAfter        # always clean build dirs
NewsOnUpgrade     # show Arch news before upgrading
CombinedUpgrade   # upgrade official and AUR in one pass
UpgradeMenu       # interactive selection of which AUR packages to upgrade
BatchInstall      # batch PKGBUILD review before building
```

### yay — Go-Based Alternative

**yay** predates paru and remains popular due to its maturity and very similar interface. Install it via paru once paru is bootstrapped:

```bash
paru -S yay

# yay usage is near-identical to paru
yay -S package-name
yay -Syu
yay --devel --combinedupgrade   # update VCS packages (-git, -svn, etc.)
```

The main reason to keep `yay` around even if you use `paru` is that some scripts or dotfile setups reference it. Both tools coexist without conflict. For new setups, prefer `paru`; for existing configurations that already use `yay`, there is no strong reason to migrate.

### aura — Haskell-Based AUR Helper

**aura** takes a different philosophy: it versions packages using its own cache layer, supports package set management across machines, and has a log inspection sub-tool. It is heavier to install but valuable in multi-machine environments.

```bash
paru -S aura-bin

# aura AUR operations use -A (AUR) prefix
aura -A package-name       # install AUR package
aura -Au                   # upgrade all AUR packages
aura -As keyword           # search AUR
aura -Ai package-name      # info

# aura unique features
aura -Bl                   # list all packages in build log
aura downgrade package-name # downgrade to a previous version from cache
aura -L                    # view install log
aura -Li package-name      # package install history
```

### Comparison: AUR Helpers

| Feature                   | paru     | yay      | aura     |
|---------------------------|----------|----------|----------|
| Language                  | Rust     | Go       | Haskell  |
| pacman compatibility      | Full     | Full     | Partial  |
| PKGBUILD review           | Yes      | Yes      | Yes      |
| Downgrade support         | No       | No       | Yes      |
| VCS package detection     | Yes      | Yes      | No       |
| AUR comment viewer        | Yes      | No       | No       |
| Active maintenance        | Yes      | Reduced  | Yes      |
| Recommended for new setups| Yes      | No       | Niche    |

---

## 83.2 pacseek — Pacman/AUR TUI Browser

pacseek is an interactive terminal UI for browsing and managing packages from both the official Arch repositories and the AUR. It offers a fuzzy-search interface, package detail panels, and the ability to install or remove packages without leaving the TUI.

The interface splits into a search pane on the left and a detail pane on the right. Navigation is keyboard-driven and documented inline. For riced setups, pacseek's colors adapt to the terminal theme, making it visually cohesive with the rest of the environment.

```bash
# Install pacseek
paru -S pacseek

# Launch
pacseek

# Key bindings (default)
# /          focus search box
# Tab        switch between search and list
# Enter      show package details / install
# d          install selected package
# r          remove selected package
# u          check for updates on selected package
# q          quit
```

pacseek stores its configuration at `~/.config/pacseek/config.json`. Useful customizations:

```json
{
  "aur_url": "https://aur.archlinux.org",
  "aur_search_delay": 200,
  "max_search_results": 50,
  "install_command": "paru -S %s",
  "uninstall_command": "paru -Rns %s",
  "sysupgrade_command": "paru -Syu",
  "search_by": "name-desc",
  "disable_colors": false,
  "computing_stats": true
}
```

To launch pacseek as a floating window from a Hyprland keybind (see Ch 22):

```ini
# ~/.config/hypr/keybindings.conf
bind = $mod SHIFT, P, exec, kitty --class=pacseek pacseek
```

And the corresponding window rule to float it:

```ini
# ~/.config/hypr/windowrules.conf
windowrulev2 = float, class:^(pacseek)$
windowrulev2 = size 1200 700, class:^(pacseek)$
windowrulev2 = center, class:^(pacseek)$
```

---

## 83.3 baph — Minimal AUR Helper

baph (Bare-minimum AUR Package Helper) occupies the opposite end of the complexity spectrum from paru. It is a small shell script with no configuration file, no dependency resolution, and no prompting beyond the build step itself. Its purpose is to be auditable (short enough to read in two minutes) and fast for power users who already know what they are installing.

```bash
# Install baph (it bootstraps itself from the AUR)
paru -S baph

# baph usage
baph -i package-name    # install one or more packages from AUR
baph -r package-name    # remove package
baph -u                 # update all AUR packages tracked by baph
baph -s keyword         # search AUR
baph -l                 # list installed AUR packages
```

baph maintains its own package list at `~/.cache/baph/`. Because it does not resolve dependencies automatically, you may need to install missing dependencies via `pacman` first. This is by design — baph targets users who read PKGBUILDs before building.

baph and paru can coexist on the same system. A common pattern is to use paru for everyday package management and baph for one-off AUR installs where you want minimal overhead and a clean audit trail.

---

## 83.4 NixOS: nix-search and Related Tools

### Built-in nix search

NixOS provides `nix search` as part of the standard Nix tooling. It queries the nixpkgs flake registry and presents matching packages with attribute paths and descriptions. The output is verbose but complete:

```bash
# Search nixpkgs for a package
nix search nixpkgs firefox

# Search with a regex
nix search nixpkgs 'python3.*requests'

# Alternative: nix-env query (legacy, but works on non-flake setups)
nix-env -qaP keyword            # query available packages
nix-env -qa --description keyword  # include descriptions
```

For flake-based NixOS configurations, add `nixpkgs` to your flake inputs and use the standard `nix search` path:

```nix
# flake.nix (excerpt)
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };
}
```

### nix-search-cli — Fast Offline Search

`nix-search-cli` indexes the nixpkgs package set locally for near-instant fuzzy search without a network round-trip on every query:

```bash
# Run directly from nixpkgs (no install required)
nix run nixpkgs#nix-search-cli -- firefox

# Or install permanently
nix-env -iA nixpkgs.nix-search-cli

# After install
nix-search firefox
nix-search --type app waybar     # search apps specifically
nix-search --json firefox        # machine-readable output
```

### nh — Nix Helper

**nh** is a wrapper around `nixos-rebuild`, `home-manager`, and `nix-collect-garbage` with dramatically better output: colored diffs, progress spinners, and a summary of what changed. It is the closest thing NixOS has to a "friendly frontend."

```bash
# Install nh
nix-env -iA nixpkgs.nh
# or in configuration.nix:
# environment.systemPackages = [ pkgs.nh ];

# Rebuild and activate NixOS configuration
nh os switch /etc/nixos              # switch using path
nh os switch                         # switch using flake in current dir
nh os test                           # activate but don't set as boot default
nh os boot                           # set as boot default without activating now

# home-manager operations
nh home switch                       # switch home-manager config
nh home switch ~/.config/home-manager

# Garbage collection
nh clean all                         # remove old generations + collect garbage
nh clean user                        # clean only user profile generations
nh clean --keep 3                    # keep last 3 generations

# Show what would be cleaned without doing it
nh clean all --dry-run
```

nh can be configured via environment variables:

```bash
# In ~/.config/fish/config.fish or ~/.zshrc
export NH_FLAKE="/etc/nixos"         # default flake path for nh os
export NH_NOM=1                      # use nix-output-monitor for builds
```

### nvd — NixOS Version Diff

**nvd** compares two Nix store paths and reports exactly which packages were added, removed, or updated. It is invaluable for reviewing the impact of a `nixos-rebuild switch` before committing to it:

```bash
# Compare current system with a new build result
nix run nixpkgs#nvd -- diff /run/current-system result

# Compare two arbitrary store paths
nvd diff /nix/store/old-system /nix/store/new-system

# Show only package changes (no path noise)
nvd diff --format min /run/current-system result
```

A typical NixOS upgrade workflow using these tools:

```bash
# 1. Update flake inputs
nix flake update

# 2. Build without activating
nixos-rebuild build --flake .#hostname

# 3. Review what will change
nvd diff /run/current-system result

# 4. If acceptable, switch
nh os switch
```

### Comparison: NixOS Package Tools

| Tool              | Purpose                          | Requires Network | Interactive TUI |
|-------------------|----------------------------------|------------------|-----------------|
| `nix search`      | Search nixpkgs                   | Yes              | No              |
| `nix-search-cli`  | Fast offline package search      | First-run only   | No              |
| `nh`              | Rebuild / clean wrapper          | For builds       | Partial         |
| `nvd`             | Diff between system generations  | No               | No              |
| `nix-output-monitor` | Prettier build output         | No               | Yes             |

---

## 83.5 Flatpak Package Management

Flatpak provides a distribution-agnostic packaging layer, primarily hosting GUI applications via the Flathub registry. On Arch, it runs on top of pacman; on NixOS, it can be enabled as a module; on any distro, it works alongside the native package manager.

Flatpak applications are sandboxed and isolated from the host system, which has security benefits but can complicate Wayland theming integration. The portal system (xdg-desktop-portal-hyprland, xdg-desktop-portal-wlr — see Ch 31) is the correct mechanism for allowing Flatpak apps to access host resources like file pickers, screen capture, and clipboard.

### Basic Flatpak Setup

```bash
# Arch
sudo pacman -S flatpak

# NixOS — add to configuration.nix
# services.flatpak.enable = true;
# Then run: sudo nixos-rebuild switch

# Add Flathub remote
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

# Verify remotes
flatpak remotes

# Search for packages
flatpak search firefox

# Install
flatpak install flathub org.mozilla.firefox
flatpak install flathub org.signal.Signal
flatpak install flathub com.spotify.Client

# Run
flatpak run org.mozilla.firefox

# List installed
flatpak list --app             # only user-visible apps
flatpak list --runtime         # only runtime dependencies

# Update everything
flatpak update

# Uninstall
flatpak uninstall org.mozilla.firefox
flatpak uninstall --unused      # remove unused runtimes
```

### Flatpak Permissions and Portals

Flatpak permissions control what the sandboxed app can access. On Wayland, most issues stem from incorrect or missing permissions:

```bash
# View permissions for an installed app
flatpak info --show-permissions org.mozilla.firefox

# Override a permission (add filesystem access)
flatpak override --user org.mozilla.firefox --filesystem=home

# Grant Wayland socket access explicitly (usually automatic)
flatpak override --user app.id --socket=wayland

# Reset all overrides for an app
flatpak override --user --reset org.mozilla.firefox

# View all overrides
flatpak override --user --show org.mozilla.firefox
```

The `flatseal` app provides a GUI for managing Flatpak permissions, which is easier for fine-grained control:

```bash
flatpak install flathub com.github.tchx84.Flatseal
flatpak run com.github.tchx84.Flatseal
```

### Theming Flatpak Apps on Wayland

Flatpak apps use GTK or Qt portals for theming. To apply your GTK theme to Flatpak GTK apps:

```bash
# Install the theme as a Flatpak runtime
flatpak install flathub org.gtk.Gtk3theme.Adwaita-dark

# Set the GTK theme for all Flatpak apps
flatpak override --user --env=GTK_THEME=Adwaita:dark

# For Kvantum/Qt Flatpak apps
flatpak override --user --env=QT_STYLE_OVERRIDE=kvantum

# Ensure font access
flatpak override --user --filesystem=~/.local/share/fonts:ro
flatpak override --user --filesystem=~/.config/fontconfig:ro
```

### Warehouse — Flatpak GUI Manager

Warehouse is a Flatpak app for managing other Flatpak apps. It supports batch operations, permission inspection, and data management:

```bash
flatpak install flathub io.github.flattool.Warehouse
flatpak run io.github.flattool.Warehouse
```

Features: batch install/uninstall, leftover data cleanup, snapshot and restore app data, remote management.

---

## 83.6 Toolbox / Distrobox — Containerized Packages

Distrobox and Toolbox allow running full Linux distribution environments inside containers, with seamless integration into the host system. The key distinction from regular containers is that home directory, display server, audio, and D-Bus are shared with the host — apps exported from the container appear in your application launcher and run like native apps.

This is valuable for running software only available as `.deb` or `.rpm` packages, testing software without polluting the host, or maintaining stable developer environments while keeping the host on a rolling release.

### Distrobox Setup

```bash
# Install distrobox
sudo pacman -S distrobox
# or on NixOS:
# environment.systemPackages = [ pkgs.distrobox ];

# Requires Podman (preferred) or Docker
sudo pacman -S podman

# Create containers
distrobox create --name ubuntu24 --image ubuntu:24.04
distrobox create --name fedora40 --image fedora:40
distrobox create --name debian12 --image debian:12
distrobox create --name archbox  --image archlinux:latest

# Enter a container
distrobox enter ubuntu24

# Inside the container, use the distro's package manager normally
# apt update && apt install -y build-essential
# After installing a GUI app, export it to the host:
distrobox-export --app firefox
distrobox-export --bin /usr/bin/some-cli-tool --export-path ~/.local/bin

# List containers
distrobox list

# Stop a container
distrobox stop ubuntu24

# Remove a container
distrobox rm ubuntu24
```

### Distrobox on NixOS

NixOS requires additional configuration because the container images expect a Filesystem Hierarchy Standard (FHS) layout that NixOS does not provide. Use `nix-ld` or a dedicated compatibility layer:

```nix
# configuration.nix
{
  programs.nix-ld.enable = true;
  virtualisation.podman = {
    enable = true;
    dockerCompat = true;
  };
  environment.systemPackages = [ pkgs.distrobox ];
}
```

### Toolbox (GNOME/Fedora)

Toolbox is a simpler alternative developed by the GNOME project, supporting Fedora and RHEL-based images:

```bash
# Install toolbox
sudo pacman -S toolbox    # Arch has it in extra

# Create a Fedora toolbox
toolbox create --distro fedora --release 40

# Enter
toolbox enter fedora-toolbox-40

# List
toolbox list

# Remove
toolbox rm fedora-toolbox-40
```

### Comparison: Distrobox vs Toolbox vs Flatpak

| Feature                    | Distrobox       | Toolbox          | Flatpak         |
|----------------------------|-----------------|------------------|-----------------|
| Multi-distro support       | Yes (any OCI)   | Fedora/RHEL only | N/A             |
| App export to host         | Yes             | Yes              | Native          |
| CLI tool integration       | Yes             | Yes              | Limited         |
| Sandboxing/isolation       | Low (by design) | Low              | High            |
| Wayland socket access      | Shared host     | Shared host      | Via portals     |
| Package manager            | Distro native   | Distro native    | Flatpak runtime |
| Use case                   | Dev envs, .deb  | Fedora ecosystem | End-user apps   |

---

## 83.7 Keeping the System Clean

Package accumulation is unavoidable on a system used for active development and ricing. Orphaned packages, stale cache entries, old Nix generations, and unused Flatpak runtimes can collectively consume tens of gigabytes. A regular cleaning routine is essential.

### Arch Cleanup

```bash
# Remove orphaned packages (deps no longer needed by anything)
paru -Rns $(paru -Qdtq)

# Alternative: interactive orphan removal
paru --clean

# Clean pacman package cache (keep last 2 versions of each package)
sudo paccache -rk2

# Remove ALL cached packages except installed versions
sudo paccache -ruk0

# View cache size before cleaning
du -sh /var/cache/pacman/pkg/

# List explicitly installed packages (for backup / new machine bootstrap)
pacman -Qe > ~/pkglist-explicit.txt
pacman -Qn > ~/pkglist-native.txt
pacman -Qm > ~/pkglist-aur.txt      # AUR/foreign packages only

# Restore on a new machine
paru -S - < ~/pkglist-explicit.txt

# Find large installed packages
expac -s "%-30n %m" | sort -rhk 2 | head -20

# Check for .pacnew and .pacsave files (config update leftovers)
sudo find /etc -name "*.pacnew" -o -name "*.pacsave" 2>/dev/null
pacdiff    # tool to review and merge these files
```

Set up a systemd timer for automatic cache cleaning:

```bash
# Enable paccache timer (cleans cache weekly, keeps 3 versions)
sudo systemctl enable --now paccache.timer
systemctl status paccache.timer
```

### NixOS Cleanup

```bash
# List current system generations
sudo nix-env --list-generations --profile /nix/var/nix/profiles/system

# Delete all but the last N generations
sudo nix-env --delete-generations +3 --profile /nix/var/nix/profiles/system

# Delete generations older than a time period
sudo nix-collect-garbage --delete-older-than 14d

# Delete ALL old generations and collect garbage
nix-collect-garbage -d

# The nh way (recommended — handles both system and user profiles)
nh clean all --keep 3
nh clean all --keep-since 14d

# Show disk usage of Nix store
du -sh /nix/store
nix path-info --all -s | sort -nk2 | tail -20    # largest store paths

# Optimize store (hard-link identical files)
nix store optimise
```

To automate NixOS garbage collection:

```nix
# configuration.nix
{
  nix.gc = {
    automatic = true;
    dates = "weekly";
    options = "--delete-older-than 30d";
  };
  nix.settings.auto-optimise-store = true;
}
```

### Flatpak Cleanup

```bash
# Remove unused runtimes
flatpak uninstall --unused

# List runtimes vs apps to identify orphans
flatpak list --runtime
flatpak list --app

# Remove leftover app data for uninstalled apps
flatpak repair --user

# View disk usage by Flatpak installation
du -sh ~/.local/share/flatpak/
du -sh /var/lib/flatpak/

# Remove a remote and all packages from it
flatpak remote-delete --force some-remote-name
```

---

## Troubleshooting

### paru / AUR Build Failures

**Error: `gpg: keyserver receive failed`**

The package maintainer's signing key is not in your keyring. Import it manually:

```bash
gpg --recv-keys KEYID                    # from the PKGBUILD's validpgpkeys array
# If key server is unreachable:
gpg --keyserver hkps://keys.openpgp.org --recv-keys KEYID
```

**Error: `==> ERROR: One or more PGP signatures could not be verified!`**

Skip PGP verification for a single build (use sparingly):

```bash
paru --skippgpcheck -S package-name
```

**Build fails due to missing dependency**

Force a full dependency resolution:

```bash
paru -Syu --rebuildtree package-name
```

**paru hangs on sudo prompt during long builds**

Ensure `SudoLoop` is set in `~/.config/paru/paru.conf`, or configure sudo to persist:

```bash
# /etc/sudoers.d/timestamp (use visudo or sudoedit)
Defaults timestamp_timeout=60
```

### NixOS Build Failures

**`error: attribute 'X' missing` in flake**

Run `nix flake update` to refresh the flake lock file, then rebuild. If the attribute genuinely disappeared from nixpkgs, find the current name:

```bash
nix search nixpkgs oldname    # check if it was renamed
nix-env -qaP '.*oldname.*'
```

**Flake evaluation error on import**

Use `--show-trace` for full error context:

```bash
nixos-rebuild switch --flake .#hostname --show-trace 2>&1 | less
```

**System runs out of disk space during rebuild**

Clean old generations first, then retry:

```bash
nh clean all --keep 1
nix store optimise
nixos-rebuild switch --flake .#hostname
```

### Flatpak Issues on Wayland

**App shows blank window or crashes on startup**

Wayland socket may not be accessible. Force Wayland mode and verify socket:

```bash
flatpak override --user app.id --socket=wayland
flatpak override --user app.id --env=GDK_BACKEND=wayland
flatpak run --env=WAYLAND_DISPLAY=$WAYLAND_DISPLAY app.id
```

**File picker opens blank / portal not working**

Ensure the correct portal backend is installed and running (see Ch 31):

```bash
# For Hyprland
sudo pacman -S xdg-desktop-portal-hyprland

# Verify portal is running
systemctl --user status xdg-desktop-portal.service
systemctl --user status xdg-desktop-portal-hyprland.service

# Restart portals
systemctl --user restart xdg-desktop-portal.service
```

**Flatpak app not picking up system font or GTK theme**

Check overrides and grant font filesystem access:

```bash
flatpak override --user --filesystem=~/.local/share/fonts:ro app.id
flatpak override --user --filesystem=/usr/share/fonts:ro app.id
flatpak override --user --env=GTK_THEME=YourThemeName app.id
```

### Distrobox Issues

**Container cannot display GUI apps (DISPLAY / WAYLAND_DISPLAY not set)**

Distrobox sets these automatically when you `enter`, but if running commands directly via `distrobox run`:

```bash
distrobox run --name ubuntu24 -- env WAYLAND_DISPLAY=$WAYLAND_DISPLAY DISPLAY=$DISPLAY firefox
```

**Host fonts not visible inside container**

Mount the font directory explicitly:

```bash
distrobox create --name ubuntu24 --image ubuntu:24.04 \
  --volume ~/.local/share/fonts:/home/$USER/.local/share/fonts:ro
```

---

## Cross-References

- Ch 14 — Kitty and Foot terminal configuration (for launching TUIs)
- Ch 22 — Hyprland keybindings (bind package TUIs to keys)
- Ch 31 — xdg-desktop-portal setup (required for Flatpak on Wayland)
- Ch 42 — Application launchers (fuzzel, Rofi-Wayland) for package search integration
- Ch 71 — Shell configuration (zsh/fish/nushell — AUR helper shell completion)
- Ch 72 — Terminal multiplexers (tmux/zellij for persistent build sessions)
- Ch 84 — System monitoring TUI tools (btop, bottom — for watching builds)

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
