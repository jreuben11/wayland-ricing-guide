# Chapter 0 — Prerequisites and Environment Setup

## Overview
Everything you need before chapter 1. Covers assumed knowledge, hardware
requirements, initial OS setup, and how to verify you are running Wayland.

## Sections

### 0.1 Assumed Knowledge
- Comfortable in a Linux terminal (paths, pipes, basic shell)
- Familiar with at least one text editor
- Know how to install packages on your distro
- NOT assumed: X11 internals, C programming, NixOS (taught in relevant chapters)

### 0.2 Distribution Recommendations

| Distro | Wayland Support | Ricing Friendliness | Notes |
|--------|----------------|---------------------|-------|
| Arch Linux | Excellent | Best | Latest packages, AUR, most dotfile authors use it |
| NixOS | Excellent | Best (reproducible) | Steeper learning curve, unmatched once learned |
| Fedora | Very good | Good | Up-to-date, Wayland default since F34 |
| openSUSE Tumbleweed | Very good | Good | Rolling, good wlroots packages |
| Ubuntu 24.04+ | Good | Fair | Older packages, PPAs needed for cutting-edge |
| Debian Testing | Good | Fair | Laggy on compositor versions |
| Void Linux | Good | Good | Minimal, musl or glibc |

**Recommendation**: Arch or NixOS for following this book exactly. Fedora for easiest start.

### 0.3 Hardware Requirements

**Minimum:**
- Any 64-bit x86 CPU (2010+)
- 4 GB RAM (8 GB recommended)
- GPU with Mesa or NVIDIA drivers

**GPU-specific notes:**
- **AMD (Radeon RX 400+)**: Best Wayland experience. Mesa RADV/ACO, no extra config.
- **Intel (Gen 8+)**: Excellent. Mesa i915. Integrated graphics fine for most rices.
- **NVIDIA (GTX 900+)**: Requires extra setup. See §0.6 and Ch 8.
- **Older/unsupported**: May work with llvmpipe (software render), no gaming.

### 0.4 Bootloader and Kernel Parameters

**NVIDIA users — required:**
```
# /etc/default/grub or kernel params
nvidia-drm.modeset=1 nvidia.NVreg_PreserveVideoMemoryAllocations=1
```

**General recommended params:**
```
quiet loglevel=3          # cleaner boot
mitigations=off           # optional: performance (reduces security)
```

### 0.5 Verifying You Are on Wayland
```bash
# Should print "wayland"
echo $XDG_SESSION_TYPE

# Should show a socket like "wayland-1"
echo $WAYLAND_DISPLAY

# DISPLAY set means XWayland is also running (normal)
echo $DISPLAY
```

If `$XDG_SESSION_TYPE` is `x11`, you're not on Wayland yet.

### 0.6 Display Server Stack Installation

**Arch (base for Hyprland):**
```bash
sudo pacman -S hyprland waybar foot \
    xdg-desktop-portal-hyprland \
    polkit-gnome pipewire wireplumber \
    qt5-wayland qt6-wayland
```

**NixOS (flake-based minimal):**
```nix
environment.systemPackages = with pkgs; [ hyprland waybar foot ];
programs.hyprland.enable = true;
security.polkit.enable = true;
hardware.pulseaudio.enable = false;
services.pipewire = { enable = true; alsa.enable = true; pulse.enable = true; };
```

### 0.7 Login Manager Setup
- **SDDM** (Hyprland, KDE): `sudo systemctl enable sddm`
- **GDM** (GNOME): `sudo systemctl enable gdm`
- **greetd** (minimal): `sudo systemctl enable greetd`
- **Without a display manager**: add compositor to `~/.bash_profile` / `~/.zprofile`
  ```bash
  if [ -z "$WAYLAND_DISPLAY" ] && [ "$XDG_VTNR" = "1" ]; then
      exec Hyprland
  fi
  ```

### 0.8 Essential First Packages

**Navigation and basics:**
```bash
# Terminal
foot  # or kitty, alacritty

# File manager
yazi  # TUI — recommended
thunar  # GUI

# Text editor
nvim  # or hx (helix), kate

# App launcher (temporary until you set up Quickshell)
fuzzel

# Status bar (temporary)
waybar
```

### 0.9 Environment Variables Reference
Key variables that must be set for Wayland apps to work correctly:
```bash
# ~/.config/hypr/env.conf or shell profile
export MOZ_ENABLE_WAYLAND=1         # Firefox native Wayland
export QT_QPA_PLATFORM=wayland      # Qt apps on Wayland
export QT_WAYLAND_DISABLE_WINDOWDECORATION=1
export GDK_BACKEND=wayland,x11      # GTK apps prefer Wayland
export SDL_VIDEODRIVER=wayland      # SDL apps (some games)
export CLUTTER_BACKEND=wayland
export XDG_SESSION_TYPE=wayland
export XDG_CURRENT_DESKTOP=Hyprland # or sway, etc. — affects portal selection
```

### 0.10 What to Read First
- Skimming Ch 1 gives protocol intuition used throughout the book
- Ch 8 (Hyprland) or Ch 7 (Sway) — pick your compositor, read it next
- Ch 15–23 (Quickshell) — then build your shell
- Come back to rest as you need specific features
