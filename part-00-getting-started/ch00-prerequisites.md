# Chapter 0 — Prerequisites and Environment Setup

## Contents

- [Overview](#overview)
- [Sections](#sections)
  - [0.1 Assumed Knowledge](#01-assumed-knowledge)
  - [0.2 Distribution Recommendations](#02-distribution-recommendations)
  - [0.3 Hardware Requirements](#03-hardware-requirements)
  - [0.4 Bootloader and Kernel Parameters](#04-bootloader-and-kernel-parameters)
  - [0.5 Verifying You Are on Wayland](#05-verifying-you-are-on-wayland)
  - [0.6 Display Server Stack Installation](#06-display-server-stack-installation)
  - [0.7 Login Manager Setup](#07-login-manager-setup)
  - [0.8 Essential First Packages](#08-essential-first-packages)
  - [0.9 Environment Variables Reference](#09-environment-variables-reference)
  - [0.10 Laptop Hardware Recommendations for Wayland Ricing](#010-laptop-hardware-recommendations-for-wayland-ricing)
  - [0.12 What to Read First](#012-what-to-read-first)

---


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

### 0.10 Laptop Hardware Recommendations for Wayland Ricing

For Wayland ricing specifically, the GPU vendor choice dominates everything else.

#### GPU Vendor Priority

**AMD iGPU (Ryzen) — clear winner.**
The RADV open-source Mesa Vulkan driver is excellent. VRR, explicit sync, and
Venus (VM Vulkan via Ch 84) all work out of the box. VA-API hardware decode is
reliable. No kernel parameter drama — works on any distro immediately. The best
virgl/Venus VM testing support if you want to use Ch 84.

**Intel Arc / Xe iGPU (12th gen+) — solid second.**
The ANV driver is mature, good Wayland support, slightly behind AMD on edge
features like explicit sync and HDR. Still a clean experience with no friction
for standard ricing workflows.

**NVIDIA discrete — avoid as primary ricing GPU.**
NVIDIA + Wayland in 2025 is functional but still carries friction: screen
sharing portals have known issues, explicit sync needs manual enabling, Looking
Glass flickering on wlroots compositors. Fine as a secondary dGPU alongside an
AMD/Intel iGPU that handles the display. Never as the sole display GPU if you
want a smooth experience with this book.

#### Recommended Laptops

**Framework 13 / 16 (AMD Ryzen 7040/8040) — the ricing laptop.**
Fully open hardware, exceptional Linux community support, repairability.
Framework has explicitly committed to Linux support in writing. Every feature
in this book works: VRR, VA-API, PipeWire, explicit sync, virgl VM testing.
The 16" model has a discrete Radeon dGPU option. No Wayland surprises.

**Lenovo ThinkPad T14s Gen 5 (AMD) — battle-tested.**
Consistent Linux support across generations. Excellent power management with
`tlp` and `power-profiles-daemon` (Ch 78). AMD variants are reliably better
than Intel variants for Wayland. Well-documented in the Linux community.

**System76 Lemur Pro / Galago Pro — zero friction.**
Ships with COSMIC desktop (Ch 68), hardware selected entirely for Linux.
If you want the absolute minimum driver friction out of the box. The Galago
Pro uses Intel but is fully supported by System76's open firmware.

**ASUS ROG / Zephyrus (AMD-only configs) — gaming + ricing.**
AMD-only configurations (no NVIDIA dGPU) are clean. VRR works on the built-in
display. The AMD-only G14/G15 models are popular in the ricing community.

#### What to Check Before Buying

- **Display output path:** confirm display is driven by the iGPU, not through
  NVIDIA Optimus. AMD laptops with a MUX switch let you bypass Optimus entirely.
- **Wi-Fi card:** Intel AX200/AX210/BE200 are the gold standard for Linux.
  Avoid MediaTek and Realtek Wi-Fi on budget machines.
- **Touchpad:** I2C HID touchpads work better than PS/2 emulation; libinput
  handles them well for gesture config (Ch 43).
- **RAM:** 16 GB minimum for compositor + apps. 32 GB if you want KVM ricing
  VMs alongside your daily driver session (Ch 84).
- **NVMe:** affects shader cache write speed and package install time — matters
  more for ricing than most users expect.

#### Bottom Line

**Framework 13 AMD Ryzen 8040** or **ThinkPad T14s Gen 5 AMD** are the two
laptops to recommend without hesitation. Both have zero Wayland surprises,
excellent community documentation, and every feature in this book works on
them including VRR, VA-API, PipeWire, explicit sync, and virgl VM testing.

---

### 0.12 What to Read First
- Skimming Ch 1 gives protocol intuition used throughout the book
- Ch 8 (Hyprland) or Ch 7 (Sway) — pick your compositor, read it next
- Ch 15–23 (Quickshell) — then build your shell
- Come back to rest as you need specific features


---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).