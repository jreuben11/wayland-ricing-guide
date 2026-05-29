# Chapter 42 — Gaming on Wayland: XWayland, gamescope, VRR, HDR

## Overview
Gaming on Wayland is now production-ready for most users. This chapter covers
the full gaming stack: from Steam/Proton through gamescope to display optimization.

## Sections

### 42.1 Wayland Gaming Status (2025/2026)
- Native Wayland games: SDL2/SDL3, Unity (partial), Unreal Engine 5
- XWayland games: all older games, most Steam titles
- Performance parity: Wayland ≥ X11 for most workloads
- Remaining pain points: some anti-cheat, rare input issues

### 42.2 XWayland for Games
- Most games still run via XWayland (transparent to user)
- Fullscreen: XWayland can take exclusive fullscreen via compositor
- Input latency: comparable to native X11
- `XWayland fullscreen passthrough` in Hyprland: improves performance
- Environment: `DISPLAY=:0` automatically set

### 42.3 gamescope — The Gaming Compositor
- Valve's microcompositor: wraps a single game
- Benefits: independent scaling, FSR upscaling, VRR, limiter, HDR
- Basic usage: `gamescope -w 1920 -h 1080 -f -- %command%`
- Steam integration: add to launch options
- Nested mode: runs inside your compositor
- Embedded mode: full display takeover (SteamOS style)

#### gamescope Flags
- `-W`, `-H`: output resolution
- `-w`, `-h`: game resolution (for upscaling)
- `--fsr-upscaling`, `--nis-upscaling`: upscaling algorithms
- `--fsr-sharpness`: 0-20 sharpness
- `--hdr-enabled`: HDR output
- `-r 165`: frame rate limit
- `--mangoapp`: Mangohud integration
- `--expose-wayland`: use Wayland backend

### 42.4 Variable Refresh Rate for Gaming
- VRR reduces tearing without vsync latency
- Compositor: `vrr = 2` (Hyprland: only for fullscreen games)
- Monitor requirement: FreeSync (AMD) / G-Sync compatible
- DisplayPort required (most HDMI VRR also works at lower refresh)
- gamescope: `--adaptive-sync`

### 42.5 HDR Gaming
- **KWin/Plasma**: full HDR pipeline, production-ready 2025
- **Hyprland**: HDR experimental/in development
- gamescope: HDR passthrough (SDR → HDR tonemapping)
- Requirements: HDR display + `drm.hdr=1` kernel parameter
- Game support: Proton games with DXVK HDR support

### 42.6 Input and Latency
- `wl_pointer.set_cursor` for cursor confinement in games
- Pointer lock: `zwp-pointer-constraints-v1` protocol
- Relative motion: `zwp-relative-pointer-manager-v1`
- `libinput` flat acceleration for gaming: `input.accel_profile = flat`
- `WLR_NO_HARDWARE_CURSORS=1` for NVIDIA cursor bugs

### 42.7 Performance Monitoring
- **Mangohud**: FPS overlay, GPU/CPU stats
  - `MANGOHUD=1 game`
  - `MangoHud.conf` for customization
- **Goverlay**: GUI for Mangohud config
- **DXVK HUD**: built-in DXVK performance overlay

### 42.8 NVIDIA-Specific Gaming Setup
- `nvidia-drm.modeset=1` kernel parameter (required)
- `__GL_GSYNC_ALLOWED=1` for VRR
- Explicit sync: `HYPRLAND_NO_DIRECT_SCANOUT=1` workaround
- Vulkan ICD: `VK_DRIVER_FILES` if needed
- `LIBVA_DRIVER_NAME=nvidia` for hardware video decode

### 42.9 Proton and Wine on Wayland
- Proton with Wayland support: native Wayland window (no XWayland)
- `PROTON_ENABLE_WAYLAND=1` experimental flag
- Wine + `wine-wayland`: native Wayland wine backend
- DirectX → Vulkan via DXVK: runs on Wayland natively

### 42.10 Controller Support
- `udev` rules for controller access without root
- Steam Input: handles all controller remapping
- `xboxdrv` for Xbox controllers (usually uneeded now)
- Bluetooth pairing: standard BlueZ stack
