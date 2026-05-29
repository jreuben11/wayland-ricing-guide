# Chapter 14 — Choosing Your Compositor: Decision Framework

## Overview
A practical guide to picking the right compositor for your workflow, hardware,
and aesthetic goals. Includes a full comparison matrix.

## Sections

### 14.1 Decision Criteria
- Workflow: coding, design, browsing, gaming, multimedia
- Hardware: GPU (NVIDIA caveats), RAM constraints, laptop vs. desktop
- Aesthetic goals: minimal/clean vs. animated/eye-candy
- Config style preference: file-based, GUI, or scriptable
- Distro: NixOS (all compositors work), Arch (best AUR support), others

### 14.2 The NVIDIA Question
- Hyprland NVIDIA setup: `nvidia-drm.modeset=1`, explicit sync
- Sway NVIDIA support (limited historically)
- KWin as the most NVIDIA-friendly wlroots-adjacent option
- NVIDIA proprietary vs. nouveau (2025 status: nouveau Vulkan improving)

### 14.3 Full Comparison Matrix

| Feature | Sway | Hyprland | Wayfire | River | Niri | labwc | KWin |
|---------|------|----------|---------|-------|------|-------|------|
| Layout | Manual tiling | Dynamic | Plugin | Tag | Scrollable | Stacking | Both |
| Base | wlroots | Aquamarine | wlroots | wlroots | Smithay | wlroots | KWin |
| Language | C | C++ | C++ | Zig | Rust | C | C++/QML |
| Config | text | text | INI+GUI | script | KDL | XML | GUI+scripts |
| Animations | minimal | heavy | heavy | none | moderate | none | moderate |
| NVIDIA | poor | good* | fair | poor | fair | poor | best |
| HDR | no | partial | no | no | no | no | yes |
| Quickshell | yes | best | yes | yes | yes | yes | - |
| Ricing community | large | huge | medium | small | growing | small | large (KDE) |
| Stability | excellent | good | good | excellent | good | excellent | excellent |

### 14.4 Recommended Starting Points
- **First-timer coming from i3**: Sway
- **Wants beautiful animations, huge dotfiles ecosystem**: Hyprland
- **Wide monitors, scrollable focus model**: Niri
- **Compiz nostalgia, 3D effects**: Wayfire
- **Traditional floating desktop**: labwc + Waybar
- **NixOS full integration**: KWin (Plasma) or Hyprland with home-manager
- **Minimal, hackable, C**: dwl
- **Gaming-first**: gamescope + Hyprland

### 14.5 Migration Paths
- X11 i3 → Sway (near-zero friction)
- X11 bspwm → Hyprland or River
- X11 Openbox → labwc
- X11 dwm → dwl
- GNOME → COSMIC or back to GNOME Wayland
- KDE X11 → KDE Wayland (same config)
