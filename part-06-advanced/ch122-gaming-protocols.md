# Chapter 122 — Gaming Protocols: Tearing, Pointer Lock, and Frame Pacing

## Contents

- [Overview](#overview)
- [122.1 tearing-control-v1](#1221-tearing-control-v1)
  - [What It Does](#what-it-does)
  - [Enabling in Hyprland](#enabling-in-hyprland)
  - [Enabling in Sway](#enabling-in-sway)
  - [Verifying Tearing Is Active](#verifying-tearing-is-active)
  - [Tearing vs. VRR](#tearing-vs-vrr)
- [122.2 relative-pointer-unstable-v1](#1222-relative-pointer-unstable-v1)
  - [What It Does](#what-it-does)
  - [Game Engine Support](#game-engine-support)
  - [Enabling in Games](#enabling-in-games)
  - [Mouse Acceleration Interaction](#mouse-acceleration-interaction)
- [122.3 pointer-constraints-unstable-v1](#1223-pointer-constraints-unstable-v1)
  - [What It Does](#what-it-does)
  - [Verifying Lock Is Working](#verifying-lock-is-working)
  - [Forcing Native Wayland for Games](#forcing-native-wayland-for-games)
  - [Compositor-side: Pointer Lock Behavior](#compositor-side-pointer-lock-behavior)
- [122.4 wp-presentation (Presentation Time)](#1224-wp-presentation-presentation-time)
  - [What It Does](#what-it-does)
  - [For Game Developers](#for-game-developers)
  - [Compositor Support](#compositor-support)
- [122.5 gamescope for Gaming (Protocol Summary)](#1225-gamescope-for-gaming-protocol-summary)
- [122.6 Per-Game Configuration Recipe](#1226-per-game-configuration-recipe)
- [122.7 Troubleshooting](#1227-troubleshooting)
  - [Mouse feels floaty / accelerated in game](#mouse-feels-floaty-accelerated-in-game)
  - [Game sees cursor on screen (pointer not locked)](#game-sees-cursor-on-screen-pointer-not-locked)
  - [Tearing only happens on some monitors](#tearing-only-happens-on-some-monitors)
  - [No improvement in input latency after enabling tearing](#no-improvement-in-input-latency-after-enabling-tearing)

---


## Overview

Four Wayland protocols are critical for gaming but rarely documented outside compositor changelogs: **tearing-control-v1** (allow screen tearing for maximum frame rate), **relative-pointer-unstable-v1** (raw delta mouse input for FPS games), **pointer-constraints-unstable-v1** (lock or confine the cursor to a window), and **wp-presentation** (frame pacing feedback for vsync-aware renderers). This chapter explains what each protocol does, how compositors expose it, how game engines and runners use it, and how to enable, verify, and troubleshoot each.

**Cross-references:** Ch 42 — gaming on Wayland overview (gamescope, VRR, HDR). Ch 43 — input customization. Ch 63 — GPU rendering stack (VRR, explicit sync).

---

## 122.1 tearing-control-v1

### What It Does

The `wp_tearing_control_v1` protocol allows a client to declare that it prefers tearing over vsync wait. The compositor can honor this by presenting the client's buffer immediately when ready, without waiting for vblank — at the cost of visible screen tearing. This is the Wayland equivalent of `glXSwapInterval(0)`.

The protocol has two hint values:
- `vsync` — the client wants vsync (default for all surfaces)
- `async` — the client prefers tearing over vsync latency

### Enabling in Hyprland

```ini
# ~/.config/hypr/hyprland.conf
general {
    allow_tearing = true   # global enable — required before per-window rules work
}

# Per-window tearing rule (recommended: only for games)
windowrulev2 = immediate, class:^(cs2)$
windowrulev2 = immediate, class:^(steam_app_\d+)$   # any Steam game
windowrulev2 = immediate, class:^(gamescope)$
```

The `immediate` window rule sets the tearing hint to `async` for matched windows.

### Enabling in Sway

```bash
# Sway 1.9+ with tearing support
# In sway config:
# No per-window rule yet — global toggle via WLR_DRM_NO_ATOMIC
WLR_DRM_NO_ATOMIC=1 sway   # legacy DRM API, enables tearing on some setups
```

Sway's tearing support is less mature than Hyprland's. gamescope (§122.5) is the recommended path for competitive gaming under Sway.

### Verifying Tearing Is Active

```bash
# Check the protocol is advertised
wayland-info | grep tearing

# Watch for tearing hint in compositor logs
HYPRLAND_LOG=1 Hyprland 2>&1 | grep -i tearing

# GPU-side: verify no vsync wait in game
# NVIDIA: nvidia-smi dmon -s u | grep idle
# AMD: radeontop (frame time should be <16.6ms at 60fps)
```

### Tearing vs. VRR

With VRR (FreeSync/G-Sync) active, tearing is less valuable because the monitor refreshes at the frame rate — no need to tear through the blanking interval. Prefer VRR when available (Ch 41); use `allow_tearing` only when VRR is not available or for non-VRR displays.

---

## 122.2 relative-pointer-unstable-v1

### What It Does

`zwp_relative_pointer_manager_v1` provides raw, unaccelerated pointer delta values (`dx`, `dy`) separate from the cursor position. FPS games need this because:
- The cursor position is clamped to screen bounds on Wayland (unlike X11 where `XWarpPointer` could loop)
- Acceleration curves applied by the compositor should not affect aiming
- The game needs to know "how far did the mouse physically move" not "where is the cursor now"

### Game Engine Support

All major game engines and runners support `zwp_relative_pointer_manager_v1` on Wayland:

| Engine / Runtime | Status |
|---|---|
| SDL2 / SDL3 | Supported since SDL2 2.0.16 |
| GLFW 3.4+ | Supported |
| Wine / Proton | Supported via winewayland.drv |
| CS2 (Source 2) | Native Wayland via SDL3 |
| Godot 4 | Supported |
| Unreal Engine 5 | Via SDL3 layer |

### Enabling in Games

Most games enable relative pointer automatically when running on Wayland. If a game falls back to XWayland, it may not use the Wayland relative pointer. Force native Wayland for SDL games:

```bash
# Force SDL2/SDL3 Wayland backend
SDL_VIDEODRIVER=wayland game_binary

# For Steam games
SDL_VIDEODRIVER=wayland %command%   # in Steam launch options
```

### Mouse Acceleration Interaction

On Wayland, the compositor applies acceleration to the *cursor*, not to relative pointer events. If relative pointer is working correctly, your in-game sensitivity should be unaffected by compositor acceleration settings. Verify:

```bash
# Check libinput acceleration for your mouse
libinput list-devices | grep "Pointer acceleration"

# To disable for gaming without affecting other devices,
# use a per-device udev rule (Ch 43)
```

---

## 122.3 pointer-constraints-unstable-v1

### What It Does

`zwp_pointer_constraints_v1` provides two operations:
- **Confine** (`zwp_confined_pointer_v1`): restrict the cursor to a region within a surface
- **Lock** (`zwp_locked_pointer_v1`): lock the cursor at a fixed position (games use this with relative pointer)

FPS games lock the pointer when the game has focus and unlock it when the window loses focus or the player presses Escape.

### Verifying Lock Is Working

When a game correctly locks the pointer, the cursor should disappear from the screen and mouse movement should only affect in-game camera rotation. If the cursor is still visible and escapes the game window, the game is probably running under XWayland without native pointer lock.

```bash
# Verify pointer-constraints is advertised
wayland-info | grep pointer_constraints

# Check that the game is running native Wayland (not XWayland)
xlsclients   # the game's window should NOT appear here if native Wayland
```

### Forcing Native Wayland for Games

```bash
# Games that are SDL-based and can be forced to Wayland
SDL_VIDEODRIVER=wayland ./game

# Wine games with winewayland.drv
WAYLAND_DISPLAY=$WAYLAND_DISPLAY DISPLAY="" wine game.exe

# Proton (via Steam)
# Add to game's Steam launch options:
PROTON_ENABLE_WAYLAND=1 SDL_VIDEODRIVER=wayland %command%
```

### Compositor-side: Pointer Lock Behavior

Hyprland respects pointer lock requests from focused windows automatically. No additional config is needed. If a game's pointer lock is being broken (cursor escapes on alt-tab), check that the game is properly unlocking and re-locking:

```ini
# Hyprland — prevent cursor from escaping window during pointer lock
# (default behavior — no explicit config needed)
# If needed for stubborn games:
windowrulev2 = forceinput, class:^(cs2)$
```

---

## 122.4 wp-presentation (Presentation Time)

### What It Does

`wp_presentation` provides feedback to a client about exactly *when* its frame was presented to the display. The compositor sends a `presented` event with:
- `tv_sec`, `tv_nsec` — the wall-clock time of presentation
- `refresh` — the nominal display refresh interval in nanoseconds
- `seq` — the frame counter (monotonically increasing per output)
- `flags` — whether vsync was honored, whether the frame was presented late

Vsync-aware renderers (Vulkan apps using `VK_KHR_swapchain`, some game engines) use this to calibrate their sleep-and-render loop, minimizing input latency while maintaining smooth output.

### For Game Developers

```c
/* Wayland client: subscribe to presentation feedback */
struct wp_presentation *presentation = /* bound from registry */;

/* After each wl_surface_commit: */
struct wp_presentation_feedback *feedback =
    wp_presentation_feedback(presentation, surface);

wp_presentation_feedback_add_listener(feedback,
    &presentation_feedback_listener, NULL);

/* In the 'presented' callback: */
static void on_presented(void *data,
    struct wp_presentation_feedback *feedback,
    uint32_t tv_sec_hi, uint32_t tv_sec_lo,
    uint32_t tv_nsec, uint32_t refresh_ns,
    uint32_t seq_hi, uint32_t seq_lo,
    uint32_t flags)
{
    uint64_t present_ns = ((uint64_t)tv_sec_lo * 1000000000ULL) + tv_nsec;
    /* Use refresh_ns to schedule the next frame */
    schedule_next_frame_at(present_ns + refresh_ns - TARGET_RENDER_TIME_NS);
}
```

### Compositor Support

All major Wayland compositors implement `wp_presentation`. Verify:

```bash
wayland-info | grep presentation
# Should show: wp_presentation
```

---

## 122.5 gamescope for Gaming (Protocol Summary)

gamescope (Valve's micro-compositor for gaming) handles all four protocols internally:

```bash
# gamescope wraps the game in its own compositor session
# with tearing, relative pointer, pointer lock, and presentation time
gamescope -W 1920 -H 1080 -r 144 --adaptive-sync --immediate-flips -- game_binary

# Via Steam:
# Right-click game → Properties → Launch Options:
gamescope -W 1920 -H 1080 -r 144 -f --adaptive-sync -- %command%
```

Key gamescope flags:
- `--immediate-flips` — tearing mode (equivalent to `allow_tearing`)
- `--adaptive-sync` — VRR passthrough
- `-f` — fullscreen
- `--hdr-enabled` — HDR passthrough (requires HDR-capable display and driver)
- `--mangoapp` — embedded MangoHud overlay

---

## 122.6 Per-Game Configuration Recipe

```ini
# Hyprland: gaming window rules for a clean experience
# ~/.config/hypr/hyprland.conf

# CS2: tearing + no border + no shadow + pin to workspace 6
windowrulev2 = immediate,            class:^(cs2)$
windowrulev2 = noborder,             class:^(cs2)$
windowrulev2 = noshadow,             class:^(cs2)$
windowrulev2 = workspace 6 silent,   class:^(cs2)$
windowrulev2 = fullscreen,           class:^(cs2)$

# Generic Steam game (any app matching steam_app_)
windowrulev2 = immediate,            class:^(steam_app_)$
windowrulev2 = noborder,             class:^(steam_app_)$

# gamescope sessions
windowrulev2 = immediate,            class:^(gamescope)$
windowrulev2 = fullscreen,           class:^(gamescope)$
```

---

## 122.7 Troubleshooting

### Mouse feels floaty / accelerated in game

The game is using the absolute cursor position instead of relative pointer. Check:
```bash
WAYLAND_DEBUG=1 game 2>&1 | grep -i "relative\|pointer"
```
If `zwp_relative_pointer_manager_v1` is not requested, the game is not using relative pointer. Force XWayland as a workaround or use gamescope.

### Game sees cursor on screen (pointer not locked)

The `zwp_locked_pointer_v1` request was either rejected or not made. On Hyprland, pointer lock requires the game window to be focused. Check that no compositor keybind is intercepting the key that the game uses to request focus.

### Tearing only happens on some monitors

`allow_tearing = true` must be set globally; the `immediate` window rule applies per-window. Tearing only works on the output where the window is displayed. A window spanning two outputs may not tear on both.

### No improvement in input latency after enabling tearing

Tearing reduces frame *presentation* latency, not input *sampling* latency. For lower input latency, also:
- Enable `raw_input` in game settings
- Disable compositor VRR (which adds latency in some implementations)
- Pin the game to a real-time process group: `schedtool -R -p 90 $(pgrep game)`
