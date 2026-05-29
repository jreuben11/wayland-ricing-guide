# Chapter 83 — Package Manager TUI Tools: paru, pacseek, nix-search, Flatpak

## Overview
Daily package management in a terminal-centric rice benefits from TUI tools.
This chapter covers the Arch, NixOS, and universal (Flatpak) package ecosystems.

## Sections

### 83.1 Arch: AUR Helpers

**paru** (Rust, recommended):
```bash
# Install paru
git clone https://aur.archlinux.org/paru-bin.git && cd paru-bin && makepkg -si

# Usage (mostly pacman-compatible)
paru -S package-name          # install (AUR + official)
paru -Syu                     # full system update
paru -Ss keyword              # search
paru -Rns package-name        # remove + orphans + config
paru --cleanafter             # remove build files after install
```

**yay** (Go, popular alternative):
```bash
paru -S yay
yay -S package-name
```

### 83.2 pacseek — Pacman/AUR TUI Browser

```bash
paru -S pacseek
pacseek  # interactive package browser
```

pacseek provides:
- Fuzzy search across official repos and AUR
- Package info, dependencies, reverse deps
- Install/remove directly from TUI
- AUR comment viewer

### 83.3 baph — AUR Helper with TUI

```bash
paru -S baph
baph -i package-name   # install from AUR
```

### 83.4 NixOS: nix-search and Related Tools

**nix search:**
```bash
nix search nixpkgs package-name    # search official nixpkgs
nix-env -qaP keyword               # alternative search
```

**nix-search-cli** (faster, offline):
```bash
nix run nixpkgs#nix-search-cli -- package-name
```

**nh — Nix Helper (highly recommended):**
```bash
nix run nixpkgs#nh -- os switch    # rebuild NixOS (better output than nixos-rebuild)
nh os test                          # test without setting as boot default
nh clean all                        # clean old generations
nh home switch                      # switch home-manager
```

**nvd — NixOS Version Diff:**
```bash
# Shows what changed between builds
nix run nixpkgs#nvd -- diff /run/current-system result
```

### 83.5 Flatpak Package Management

```bash
sudo pacman -S flatpak
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

# Usage
flatpak install flathub org.app.Name
flatpak update                     # update all
flatpak list                       # installed apps
flatpak run org.app.Name           # launch
flatpak uninstall org.app.Name
flatpak uninstall --unused         # remove runtime orphans
```

**Warehouse — Flatpak GUI manager:**
```bash
flatpak install flathub io.github.flattool.Warehouse
```

### 83.6 Toolbox / Distrobox — Containerized Packages

For running packages from other distros without affecting the host:
```bash
sudo pacman -S distrobox
distrobox create -n ubuntu -i ubuntu:24.04
distrobox enter ubuntu
# Inside: apt install whatever
# Apps exported to host with: distrobox-export --app app-name
```

Useful for: running Ubuntu-only apps on Arch, testing without polluting host.

### 83.7 Keeping the System Clean

**Arch:**
```bash
# Remove orphaned packages
paru -Rns $(paru -Qdtq)
# or:
paru --clean

# Clean pacman cache (keep last 2 versions)
sudo paccache -rk2

# List explicitly installed packages
pacman -Qe > ~/pkglist.txt
```

**NixOS:**
```bash
# Delete old generations (keep last 3)
sudo nix-env --delete-generations +3 --profile /nix/var/nix/profiles/system
sudo nixos-rebuild switch --upgrade
nix-collect-garbage -d   # delete unreachable store paths
nh clean all             # recommended: nh's cleaner
```
