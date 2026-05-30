# Chapter 139 — Rice Bootstrap: One-Command Setup Scripts

## Contents

- [Overview](#overview)
- [139.1 Philosophy: Idempotent Bootstrap](#1391-philosophy-idempotent-bootstrap)
- [139.2 Directory Structure](#1392-directory-structure)
- [139.3 Entry Point: install.sh](#1393-entry-point-installsh)
- [139.4 Package Installer](#1394-package-installer)
- [139.5 Font Installer](#1395-font-installer)
- [139.6 Dotfile Linker](#1396-dotfile-linker)
- [139.7 Theme Applicator](#1397-theme-applicator)
- [139.8 Service Enabler](#1398-service-enabler)
- [139.9 Verification Script](#1399-verification-script)
- [139.10 Putting It Together: GitHub Workflow](#13910-putting-it-together-github-workflow)
- [Quick Install](#quick-install)

---


## Overview

A dotfiles repository gets you to "clone and stow" — but a full rice involves more: installing packages, enabling services, setting GTK and icon themes, installing fonts, setting up systemd user units, and verifying that all tools are present and correctly configured. This chapter builds a complete rice bootstrap system: a dependency installer, a dotfile linker, a font setup script, a theme applicator, and a verification script — all composable into a single entry point.

**Cross-references:** Ch 55 — dotfile management (stow, chezmoi, yadm, bare git). Ch 39 — Nix and Home Manager (the declarative alternative to bootstrap scripts). Ch 136 — UWSM session management (session unit setup).

---

## 139.1 Philosophy: Idempotent Bootstrap

A good bootstrap script runs multiple times without breaking anything:

- **Idempotent**: Run it again after already running → no changes, no errors
- **Non-destructive**: Never delete existing files without backing them up
- **Composable**: Each script does one thing; the entry point calls them in order
- **Verifiable**: A `verify` subcommand checks the rice is working correctly
- **Auditable**: Dry-run mode shows what would happen without doing it

---

## 139.2 Directory Structure

```
~/.dotfiles/
├── install.sh               ← entry point
├── scripts/
│   ├── install-packages.sh  ← package manager detection + install
│   ├── install-fonts.sh     ← font download + fc-cache
│   ├── link-dotfiles.sh     ← stow or manual symlinks
│   ├── apply-theme.sh       ← GTK, icon, cursor themes
│   ├── enable-services.sh   ← systemd user units
│   └── verify.sh            ← post-install checks
├── .config/
│   ├── hypr/
│   ├── waybar/
│   ├── kitty/
│   └── ...
└── fonts/
    └── JetBrainsMono/       ← included fonts (optional)
```

---

## 139.3 Entry Point: install.sh

```bash
#!/usr/bin/env bash
# ~/.dotfiles/install.sh
set -euo pipefail

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY_RUN=false
VERBOSE=false

# Colours
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'

log()  { echo -e "${BLUE}[rice]${NC} $*"; }
ok()   { echo -e "${GREEN}[ok]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
fail() { echo -e "${RED}[fail]${NC} $*" >&2; }

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Options:
  --dry-run        Show what would happen without doing it
  --verbose        Extra output
  --only SCRIPT    Run only one script (packages|fonts|dots|theme|services)
  --verify         Run verification only
  -h, --help       Show this help
EOF
}

ONLY=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)  DRY_RUN=true; shift ;;
        --verbose)  VERBOSE=true; shift ;;
        --only)     ONLY="$2"; shift 2 ;;
        --verify)   ONLY="verify"; shift ;;
        -h|--help)  usage; exit 0 ;;
        *) fail "Unknown option: $1"; usage; exit 1 ;;
    esac
done

export DOTFILES_DIR DRY_RUN VERBOSE

run() {
    local script="$DOTFILES_DIR/scripts/${1}.sh"
    if [[ ! -f "$script" ]]; then
        warn "Script not found: $script — skipping"
        return
    fi
    log "Running $1..."
    bash "$script"
}

if [[ -n "$ONLY" ]]; then
    run "$ONLY"
else
    run install-packages
    run install-fonts
    run link-dotfiles
    run apply-theme
    run enable-services
    run verify
fi

ok "Bootstrap complete."
```

---

## 139.4 Package Installer

```bash
#!/usr/bin/env bash
# ~/.dotfiles/scripts/install-packages.sh
set -euo pipefail

# Core packages — edit for your rice
ARCH_PACKAGES=(
    hyprland hyprlock hyprpaper hypridle
    waybar fuzzel mako foot kitty
    wl-clipboard cliphist
    swww grim slurp swappy
    pipewire wireplumber pipewire-pulse
    nerd-fonts-jetbrains-mono
    btop fastfetch
    stow git curl
    gtk4 libadwaita
    papirus-icon-theme bibata-cursor-theme
    ttf-font-awesome
)

DEBIAN_PACKAGES=(
    hyprland
    waybar fuzzel mako foot
    wl-clipboard
    grim slurp
    pipewire wireplumber
    fonts-jetbrains-mono
    btop neofetch
    stow git curl
    libgtk-4-1
)

NIX_PACKAGES=(
    hyprland waybar fuzzel mako foot
    wl-clipboard grim slurp swww
    pipewire wireplumber
    nerd-fonts.jetbrains-mono
    btop fastfetch stow
)

detect_pm() {
    if command -v pacman &>/dev/null; then echo "pacman"
    elif command -v apt &>/dev/null; then echo "apt"
    elif command -v nix-env &>/dev/null; then echo "nix"
    elif command -v dnf &>/dev/null; then echo "dnf"
    else echo "unknown"; fi
}

PM=$(detect_pm)
log "Package manager: $PM"

install_missing() {
    local pkgs=("$@")
    local missing=()
    for pkg in "${pkgs[@]}"; do
        case $PM in
            pacman) pacman -Qi "$pkg" &>/dev/null || missing+=("$pkg") ;;
            apt)    dpkg -l "$pkg" &>/dev/null | grep -q "^ii" || missing+=("$pkg") ;;
            nix)    nix-env -q "$pkg" &>/dev/null || missing+=("$pkg") ;;
        esac
    done
    if [[ ${#missing[@]} -eq 0 ]]; then
        ok "All packages already installed."; return
    fi
    log "Installing: ${missing[*]}"
    if [[ "$DRY_RUN" == "true" ]]; then
        warn "[dry-run] would install: ${missing[*]}"; return
    fi
    case $PM in
        pacman) sudo pacman -S --needed --noconfirm "${missing[@]}" ;;
        apt)    sudo apt install -y "${missing[@]}" ;;
        nix)    nix-env -iA nixpkgs."${missing[@]}" ;;
    esac
}

case $PM in
    pacman) install_missing "${ARCH_PACKAGES[@]}" ;;
    apt)    install_missing "${DEBIAN_PACKAGES[@]}" ;;
    nix)    install_missing "${NIX_PACKAGES[@]}" ;;
    *)      warn "Unknown package manager — skipping package install" ;;
esac

# AUR packages (Arch only)
if [[ $PM == "pacman" ]] && command -v yay &>/dev/null; then
    AUR_PKGS=(swww cliphist fastfetch bibata-cursor-theme-bin)
    missing_aur=()
    for pkg in "${AUR_PKGS[@]}"; do
        pacman -Qi "$pkg" &>/dev/null || missing_aur+=("$pkg")
    done
    if [[ ${#missing_aur[@]} -gt 0 ]]; then
        log "Installing AUR: ${missing_aur[*]}"
        [[ "$DRY_RUN" == "true" ]] || yay -S --needed --noconfirm "${missing_aur[@]}"
    fi
fi
```

---

## 139.5 Font Installer

```bash
#!/usr/bin/env bash
# ~/.dotfiles/scripts/install-fonts.sh
set -euo pipefail

FONT_DIR="$HOME/.local/share/fonts"
mkdir -p "$FONT_DIR"

# Fonts to install (name → download URL or local path)
declare -A FONTS=(
    ["JetBrainsMono"]="https://github.com/ryanoasis/nerd-fonts/releases/latest/download/JetBrainsMono.tar.xz"
    ["Iosevka"]="https://github.com/ryanoasis/nerd-fonts/releases/latest/download/Iosevka.tar.xz"
)

install_nerd_font() {
    local name="$1" url="$2"
    local target="$FONT_DIR/$name"
    if [[ -d "$target" ]]; then
        ok "Font $name already installed — skipping"
        return
    fi
    log "Downloading $name..."
    if [[ "$DRY_RUN" == "true" ]]; then
        warn "[dry-run] would download $url"; return
    fi
    local tmp=$(mktemp -d)
    curl -fsSL "$url" -o "$tmp/$name.tar.xz"
    mkdir -p "$target"
    tar -xJf "$tmp/$name.tar.xz" -C "$target"
    rm -rf "$tmp"
    ok "Installed $name"
}

for font in "${!FONTS[@]}"; do
    install_nerd_font "$font" "${FONTS[$font]}"
done

# Install local fonts bundled with dotfiles
if [[ -d "$DOTFILES_DIR/fonts" ]]; then
    cp -r "$DOTFILES_DIR/fonts/"* "$FONT_DIR/"
fi

# Rebuild font cache
log "Rebuilding font cache..."
[[ "$DRY_RUN" == "true" ]] || fc-cache -fv "$FONT_DIR" >/dev/null
ok "Font cache updated"

# Verify a key font is discoverable
verify_font() {
    local name="$1"
    if fc-list | grep -qi "$name"; then
        ok "Font '$name' is available"
    else
        warn "Font '$name' not found after install — check fc-list"
    fi
}

verify_font "JetBrains Mono"
```

---

## 139.6 Dotfile Linker

```bash
#!/usr/bin/env bash
# ~/.dotfiles/scripts/link-dotfiles.sh
set -euo pipefail

BACKUP_DIR="$HOME/.dotfiles-backup/$(date +%Y%m%d-%H%M%S)"

link() {
    local src="$DOTFILES_DIR/.config/$1"
    local dst="$HOME/.config/$1"
    [[ -d "$src" ]] || { warn "Source not found: $src"; return; }

    if [[ -L "$dst" ]]; then
        ok "Already linked: $dst"; return
    fi
    if [[ -e "$dst" ]]; then
        warn "Backing up existing: $dst"
        if [[ "$DRY_RUN" == "false" ]]; then
            mkdir -p "$BACKUP_DIR"
            mv "$dst" "$BACKUP_DIR/"
        fi
    fi
    log "Linking $dst"
    [[ "$DRY_RUN" == "true" ]] || ln -sfn "$src" "$dst"
}

# List all config directories to link
CONFIGS=(
    hypr waybar kitty foot alacritty
    fuzzel mako swww cliphist
    fastfetch starship.toml fish zsh
    nvim helix
)

mkdir -p "$HOME/.config"
for cfg in "${CONFIGS[@]}"; do
    link "$cfg"
done

# Link home-level dotfiles
link_home() {
    local src="$DOTFILES_DIR/$1"
    local dst="$HOME/$1"
    [[ -f "$src" ]] || return
    if [[ -e "$dst" && ! -L "$dst" ]]; then
        mkdir -p "$BACKUP_DIR"
        mv "$dst" "$BACKUP_DIR/"
    fi
    [[ "$DRY_RUN" == "true" ]] || ln -sfn "$src" "$dst"
    ok "Linked ~/$1"
}

link_home .bashrc
link_home .zshrc
link_home .gitconfig

[[ -d "$BACKUP_DIR" ]] && ok "Backed up originals to $BACKUP_DIR"
```

---

## 139.7 Theme Applicator

```bash
#!/usr/bin/env bash
# ~/.dotfiles/scripts/apply-theme.sh
set -euo pipefail

GTK_THEME="Catppuccin-Mocha-Standard-Blue-Dark"
ICON_THEME="Papirus-Dark"
CURSOR_THEME="Bibata-Modern-Classic"
CURSOR_SIZE=24

apply_gtk_theme() {
    if [[ "$DRY_RUN" == "true" ]]; then
        warn "[dry-run] would set GTK theme: $GTK_THEME"; return
    fi

    # GTK3
    mkdir -p "$HOME/.config/gtk-3.0"
    cat > "$HOME/.config/gtk-3.0/settings.ini" <<EOF
[Settings]
gtk-theme-name=$GTK_THEME
gtk-icon-theme-name=$ICON_THEME
gtk-cursor-theme-name=$CURSOR_THEME
gtk-cursor-theme-size=$CURSOR_SIZE
gtk-font-name=JetBrains Mono 11
gtk-application-prefer-dark-theme=1
EOF

    # GTK4
    mkdir -p "$HOME/.config/gtk-4.0"
    cat > "$HOME/.config/gtk-4.0/settings.ini" <<EOF
[Settings]
gtk-theme-name=$GTK_THEME
gtk-icon-theme-name=$ICON_THEME
gtk-cursor-theme-name=$CURSOR_THEME
gtk-cursor-theme-size=$CURSOR_SIZE
gtk-font-name=JetBrains Mono 11
gtk-application-prefer-dark-theme=1
EOF

    # gsettings (for apps that read GSettings)
    if command -v gsettings &>/dev/null; then
        gsettings set org.gnome.desktop.interface gtk-theme       "$GTK_THEME"
        gsettings set org.gnome.desktop.interface icon-theme      "$ICON_THEME"
        gsettings set org.gnome.desktop.interface cursor-theme    "$CURSOR_THEME"
        gsettings set org.gnome.desktop.interface cursor-size     "$CURSOR_SIZE"
        gsettings set org.gnome.desktop.interface color-scheme    "prefer-dark"
    fi

    ok "GTK theme applied: $GTK_THEME"
}

apply_cursor() {
    mkdir -p "$HOME/.icons/default"
    cat > "$HOME/.icons/default/index.theme" <<EOF
[Icon Theme]
Name=Default
Comment=Default cursor theme
Inherits=$CURSOR_THEME
EOF
    ok "Cursor theme set: $CURSOR_THEME"
}

apply_xresources() {
    # For XWayland apps that read Xresources
    cat > "$HOME/.Xresources" <<EOF
Xcursor.theme: $CURSOR_THEME
Xcursor.size:  $CURSOR_SIZE
EOF
    ok "Xresources updated"
}

apply_gtk_theme
apply_cursor
apply_xresources
```

---

## 139.8 Service Enabler

```bash
#!/usr/bin/env bash
# ~/.dotfiles/scripts/enable-services.sh
set -euo pipefail

USER_SERVICES=(
    pipewire.service
    pipewire-pulse.service
    wireplumber.service
    hypridle.service
)

for svc in "${USER_SERVICES[@]}"; do
    if systemctl --user is-enabled "$svc" &>/dev/null; then
        ok "Already enabled: $svc"
        continue
    fi
    log "Enabling: $svc"
    [[ "$DRY_RUN" == "true" ]] || systemctl --user enable "$svc"
done

# Start services immediately if in a Wayland session
if [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
    for svc in "${USER_SERVICES[@]}"; do
        systemctl --user is-active "$svc" &>/dev/null && continue
        log "Starting: $svc"
        [[ "$DRY_RUN" == "true" ]] || systemctl --user start "$svc"
    done
fi

ok "Services configured"
```

---

## 139.9 Verification Script

```bash
#!/usr/bin/env bash
# ~/.dotfiles/scripts/verify.sh
set -uo pipefail

PASS=0; FAIL=0

check() {
    local label="$1" cmd="$2"
    if eval "$cmd" &>/dev/null; then
        ok "$label"
        ((PASS++))
    else
        fail "$label"
        ((FAIL++))
    fi
}

check_font() {
    local name="$1"
    fc-list | grep -qi "$name"
}

log "=== Rice Verification ==="

# Required binaries
check "hyprland installed"     "command -v hyprland"
check "waybar installed"       "command -v waybar"
check "foot installed"         "command -v foot"
check "fuzzel installed"       "command -v fuzzel"
check "mako installed"         "command -v mako"
check "wl-paste installed"     "command -v wl-paste"
check "grim installed"         "command -v grim"
check "swww installed"         "command -v swww"
check "fastfetch installed"    "command -v fastfetch"

# Fonts
check "JetBrains Mono font"    "check_font 'JetBrains Mono'"
check "Nerd Font glyphs"       "fc-list | grep -qi 'nerd'"

# Config symlinks
check "Hyprland config linked" "[[ -L ~/.config/hypr ]]"
check "Waybar config linked"   "[[ -L ~/.config/waybar ]]"
check "Kitty config linked"    "[[ -L ~/.config/kitty ]]"

# Services
check "PipeWire service active"    "systemctl --user is-active pipewire"
check "WirePlumber service active" "systemctl --user is-active wireplumber"

# GTK theme
check "GTK3 settings exist"    "[[ -f ~/.config/gtk-3.0/settings.ini ]]"
check "GTK4 settings exist"    "[[ -f ~/.config/gtk-4.0/settings.ini ]]"

# Summary
echo ""
echo -e "${GREEN}Passed: $PASS${NC}  ${RED}Failed: $FAIL${NC}"
if [[ $FAIL -gt 0 ]]; then
    warn "Some checks failed — review the output above."
    exit 1
else
    ok "All checks passed. Rice is ready!"
fi
```

---

## 139.10 Putting It Together: GitHub Workflow

```markdown
# README.md for dotfiles repo

## Quick Install

\`\`\`bash
git clone https://github.com/yourname/dotfiles ~/.dotfiles
cd ~/.dotfiles
./install.sh
\`\`\`

Or dry-run first:
\`\`\`bash
./install.sh --dry-run
\`\`\`

Verify the install:
\`\`\`bash
./install.sh --verify
\`\`\`
```

Add a GitHub Actions workflow to test the bootstrap on a clean Arch container:

```yaml
# .github/workflows/test-install.yml
name: Test Bootstrap

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    container:
      image: archlinux:latest

    steps:
      - uses: actions/checkout@v4
        with:
          path: /root/.dotfiles

      - name: Install base tools
        run: pacman -Syu --noconfirm git sudo

      - name: Run install (packages only)
        run: |
          cd /root/.dotfiles
          ./install.sh --only packages

      - name: Run dotfile linking
        run: |
          cd /root/.dotfiles
          ./install.sh --only dots

      - name: Verify (non-graphical checks only)
        run: |
          cd /root/.dotfiles
          ./install.sh --verify
        continue-on-error: true   # graphical services won't start in CI
```
