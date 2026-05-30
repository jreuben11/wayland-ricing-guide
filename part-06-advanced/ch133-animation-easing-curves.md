# Chapter 133 — Animation Easing Curves and Visual Tuning

## Overview

Animation easing is the difference between a rice that feels alive and one that feels mechanical. A bezier curve controls how a property changes over time — it can make a window open with a gentle bounce, a workspace switch feel instant but smooth, or a border glow pulse in sync with an aesthetic. This chapter covers bezier curve fundamentals, the Hyprland animation system in depth, Niri's spring model, Wayfire's animation plugins, and a reference table of curves tuned to common ricing aesthetics.

**Cross-references:** Ch 08 — Hyprland config overview (animation block basics). Ch 09 — Wayfire (animation plugins). Ch 11 — Niri. Ch 92 — compositor shaders (post-processing effects, distinct from animation). Ch 112 — aesthetic ricing meta-chapter (per-aesthetic recommendations).

---

## 133.1 Bezier Curve Fundamentals

A cubic bezier curve is defined by four points: P0 (start), P1 (control 1), P2 (control 2), P3 (end). In animation systems, P0=(0,0) and P3=(1,1) are fixed — the curve maps time (0→1) to progress (0→1). Only P1 and P2 are configurable, giving two (x,y) pairs: `bezier(P1x, P1y, P2x, P2y)`.

```
Progress
1.0 ┤                              ╭──── P3
    │                         ╭────╯
    │                    ╭────╯
    │              ╭─────╯
    │         ╭────╯
    │    ╭────╯
0.0 ┼────╯ P0                              Time
    0.0                                   1.0
```

Key named curves (CSS standard — widely used as references):

| Name | P1 | P2 | Feel |
|---|---|---|---|
| `linear` | 0.0, 0.0 | 1.0, 1.0 | Constant speed — robotic |
| `ease` | 0.25, 0.1 | 0.25, 1.0 | Slow start, fast middle, slight end decel |
| `ease-in` | 0.42, 0.0 | 1.0, 1.0 | Slow start, fast end — launching |
| `ease-out` | 0.0, 0.0 | 0.58, 1.0 | Fast start, slow end — landing |
| `ease-in-out` | 0.42, 0.0 | 0.58, 1.0 | Slow start and end — natural |
| `overshoot` | 0.34, 1.56 | 0.64, 1.0 | Overshoots target then settles — bouncy |

P1y and P2y values outside [0,1] create overshoot (y > 1 = goes past target, then returns).

---

## 133.2 Hyprland Animation System

### Core Config

```ini
# ~/.config/hypr/hyprland.conf

animations {
    enabled = true

    # Define custom bezier curves
    bezier = myEaseOut,    0.05, 0.9,  0.1,  1.05   # slight overshoot
    bezier = myLinear,     0.0,  0.0,  1.0,  1.0    # linear
    bezier = snappy,       0.1,  1.0,  0.1,  1.0    # fast settle
    bezier = gentle,       0.37, 0.0,  0.63, 1.0    # ease-in-out
    bezier = bounce,       0.34, 1.56, 0.64, 1.0    # overshoot + settle

    # animation = type, enable, speed, curve[, style]
    animation = windows,          1, 5,  myEaseOut, slide
    animation = windowsIn,        1, 4,  bounce,    popin 85%
    animation = windowsOut,       1, 3,  myEaseOut, popin 85%
    animation = windowsMove,      1, 4,  snappy
    animation = fade,             1, 4,  myEaseOut
    animation = fadeIn,           1, 4,  myEaseOut
    animation = fadeOut,          1, 3,  myEaseOut
    animation = fadeSwitch,       1, 4,  myEaseOut
    animation = fadeShadow,       1, 4,  myEaseOut
    animation = fadeDim,          1, 4,  myEaseOut
    animation = border,           1, 8,  myEaseOut
    animation = borderangle,      1, 8,  linear,    once  # gradient rotation
    animation = workspaces,       1, 5,  snappy,    slide
    animation = specialWorkspace, 1, 5,  gentle,    slidevert
    animation = layers,           1, 3,  myEaseOut, slide
}
```

### Speed Units

Speed in Hyprland is `deciseconds × 10 = animation duration in ms`.

```
speed = 1  → 100ms
speed = 3  → 300ms
speed = 5  → 500ms
speed = 8  → 800ms
speed = 10 → 1000ms
```

The relationship is: `duration_ms = speed × 100`.

### Animation Types Reference

| Type | What it animates |
|---|---|
| `windows` | All window state changes (catch-all) |
| `windowsIn` | Window opening (overrides `windows`) |
| `windowsOut` | Window closing (overrides `windows`) |
| `windowsMove` | Window being dragged/moved |
| `fade` | All opacity transitions |
| `fadeIn` | Window appearing |
| `fadeOut` | Window disappearing |
| `fadeSwitch` | Focus change opacity shift |
| `fadeShadow` | Shadow opacity on focus change |
| `fadeDim` | Inactive window dimming |
| `border` | Border color transition |
| `borderangle` | Border gradient angle (requires `once` or speed for rotation) |
| `workspaces` | Workspace switching |
| `specialWorkspace` | Special workspace slide-in/out |
| `layers` | Layer-shell surfaces (bars, overlays) |
| `activewindow` | Active window indicator |

### Window Animation Styles

```ini
# Slide styles (direction)
animation = windowsIn, 1, 4, myBezier, slide          # slide from edge
animation = windowsIn, 1, 4, myBezier, slidevert      # slide from top/bottom

# Slide with fade combined
animation = windowsIn, 1, 4, myBezier, slidefade      # slide + fade
animation = windowsIn, 1, 4, myBezier, slidefadevert  # slide vertical + fade

# Pop-in scale (with percentage of starting scale)
animation = windowsIn, 1, 4, bounce,   popin          # scale from 0%
animation = windowsIn, 1, 4, bounce,   popin 70%      # scale from 70%
animation = windowsIn, 1, 4, bounce,   popin 90%      # subtle scale from 90%

# Fade only
animation = windowsIn, 1, 4, myBezier, fade
```

### Workspace Animation Styles

```ini
animation = workspaces, 1, 5, snappy, slide         # horizontal slide
animation = workspaces, 1, 5, snappy, slidevert     # vertical slide
animation = workspaces, 1, 5, snappy, slidefade     # slide + fade
animation = workspaces, 1, 5, gentle, fade          # pure crossfade
animation = workspaces, 1, 5, linear                # (no style = default)
```

### Per-Window Animation Override

Use `windowrulev2` to give specific windows different animations:

```ini
# Rofi slides in, other windows pop
windowrulev2 = animation slide, class:^(rofi|fuzzel|wofi)$

# Game windows have no animation
windowrulev2 = noanim, class:^(cs2|steam_app_).*$

# Terminal scratchpad slides from top
windowrulev2 = animation slidevert, class:^dropdown$
```

---

## 133.3 Bezier Presets by Aesthetic

### Tokyo Night — Gentle, Organic

```ini
# Calm, blue-purple aesthetic: smooth transitions, no overshoot
bezier = tokyoEase,   0.37, 0.0, 0.63, 1.0    # clean ease-in-out
bezier = tokyoOpen,   0.21, 1.0, 0.36, 1.0    # windows open with deceleration

animation = windows,    1, 6, tokyoEase,  slidefade
animation = windowsIn,  1, 5, tokyoOpen,  popin 88%
animation = windowsOut, 1, 4, tokyoEase,  popin 88%
animation = workspaces, 1, 5, tokyoEase,  slide
animation = border,     1, 10, tokyoEase
animation = fade,       1, 5,  tokyoEase
```

### Cyberpunk Neon — Snappy, Aggressive

```ini
# Electric aesthetic: fast transitions, slight overshoot, angular
bezier = cyberSnap,   0.1,  1.0,  0.1,  1.0   # very fast settle
bezier = cyberPunch,  0.0,  0.85, 0.0,  1.15  # fast with overshoot

animation = windows,    1, 3, cyberSnap,  slide
animation = windowsIn,  1, 3, cyberPunch, popin 75%
animation = windowsOut, 1, 2, cyberSnap,  popin 75%
animation = workspaces, 1, 3, cyberSnap,  slide
animation = border,     1, 4, cyberSnap
animation = borderangle, 1, 2, linear, loop  # continuous gradient rotation
animation = fade,       1, 3, cyberSnap
```

### Tron / Digital — Minimal, Precise

```ini
# Grid aesthetic: near-instant, no organic curves
bezier = tronLinear,  0.0, 0.0, 1.0, 1.0   # linear
bezier = tronCrisp,   0.0, 0.0, 0.2, 1.0   # instant start, slow finish

animation = windows,    1, 2, tronLinear, slide
animation = windowsIn,  1, 2, tronCrisp,  slide
animation = windowsOut, 1, 1, tronLinear, slide
animation = workspaces, 1, 2, tronCrisp,  slide
animation = border,     1, 3, tronLinear
animation = fade,       1, 2, tronLinear
```

### Synthwave / Retro — Bouncy, Fun

```ini
# Warm neon aesthetic: exaggerated overshoot, retro feel
bezier = synthBounce, 0.34, 1.56, 0.64, 1.0   # classic overshoot
bezier = synthWobble, 0.0,  1.2,  0.5,  1.0   # late-starting overshoot

animation = windows,    1, 6,  synthBounce, popin 80%
animation = windowsIn,  1, 6,  synthBounce, popin 80%
animation = windowsOut, 1, 4,  synthBounce, popin 80%
animation = workspaces, 1, 6,  synthWobble, slide
animation = border,     1, 12, synthBounce
animation = fade,       1, 5,  synthBounce
```

### Nord / Minimal — Subtle, Clean

```ini
# Cool tones, understated motion
bezier = nordFade, 0.4, 0.0, 0.6, 1.0   # symmetric ease

animation = windows,    1, 7,  nordFade, slidefade
animation = windowsIn,  1, 6,  nordFade, slidefade
animation = windowsOut, 1, 5,  nordFade, slidefade
animation = workspaces, 1, 6,  nordFade, slidefade
animation = border,     1, 10, nordFade
animation = fade,       1, 6,  nordFade
```

---

## 133.4 Niri: Spring Animations

Niri uses a physics-based spring model instead of bezier curves. Springs are defined by stiffness, damping ratio, and mass:

```kdl
// ~/.config/niri/config.kdl

animations {
    // Enable all animations
    // (animations are on by default in recent niri)

    workspace-switch {
        spring stiffness=1000 damping-ratio=0.6 epsilon=0.0001
    }

    window-open {
        duration-ms 200
        curve "ease-out-expo"
    }

    window-close {
        duration-ms 150
        curve "ease-in-quad"
    }

    window-movement {
        spring stiffness=800 damping-ratio=0.8 epsilon=0.0001
    }

    window-resize {
        spring stiffness=800 damping-ratio=0.8 epsilon=0.0001
    }

    // Disable all animations
    // off
}
```

Spring parameter intuition:
- **stiffness**: How fast the spring pulls toward target. Higher = snappier. Range: 200–2000.
- **damping-ratio**: 1.0 = critically damped (no overshoot). < 1.0 = underdamped (bouncy). > 1.0 = overdamped (sluggish).
- **epsilon**: How close to target counts as "done". Smaller = longer tail.

```
damping-ratio 0.5 = very bouncy (2–3 overshoots)
damping-ratio 0.7 = light bounce (1 overshoot)
damping-ratio 1.0 = no overshoot, fastest settle
damping-ratio 1.5 = no overshoot, slower settle (overdamped)
```

Named curves available in Niri (for duration-ms mode):

| Curve | Feel |
|---|---|
| `ease-out-cubic` | Natural deceleration |
| `ease-out-expo` | Fast start, very gentle end |
| `ease-out-bounce` | Bouncy landing |
| `ease-in-quad` | Accelerating exit (for close) |
| `linear` | Constant speed |

---

## 133.5 Wayfire Animation Plugins

Wayfire uses a plugin system for animations. Enable in `~/.config/wayfire.ini`:

```ini
[core]
plugins = animate wobbly scale expo

[animate]
# Duration for all animations (milliseconds)
duration = 400
# Type: fade, zoom, fire, zap, none
open_animation  = zoom
close_animation = zoom
# Easing: linear, sine, quadratic, cubic, quartic, quintic, circular, bounce, back
open_easing  = cubic
close_easing = back
zoom_effect_factor = 0.85   # start scale (e.g., 0.85 = opens from 85% size)

# Per-app overrides
[animate/rules]
# app-id matches support basic glob
animation_for_app_id = foot  = fade
animation_for_app_id = fuzzel = zoom

[wobbly]
# Window wobbles when dragged
friction = 3.0
spring_k  = 8.0
# friction: higher = less wobble
# spring_k: higher = stiffer spring (less exaggerated)

[scale]
# Overview/expose mode
duration       = 300
toggle_binding = <super> KEY_E
bg_color       = 0.1 0.1 0.1 0.8   # RGBA dimming

[expo]
# Virtual desktop expo view (like GNOME Activities)
duration       = 300
toggle_binding = <super> KEY_GRAVE
```

Plugin overview:

| Plugin | What it does |
|---|---|
| `animate` | Open/close animations |
| `wobbly` | Jelly window dragging |
| `scale` | Window overview (expose) |
| `expo` | Workspace grid overview |
| `blur` | Background blur |
| `winshadow` | Drop shadows |
| `vswitch` | Workspace switching with animation |
| `wayfire-shadows` | Alternative shadow plugin |

---

## 133.6 Frame Rate Alignment

Animation durations that align to multiples of your monitor's refresh interval feel smoother:

```
60Hz  → frame = 16.7ms → align to: 100, 167, 200, 250, 333ms
75Hz  → frame = 13.3ms → align to: 133, 200, 267, 333ms
120Hz → frame = 8.3ms  → align to: 83,  167, 250, 333ms
144Hz → frame = 6.9ms  → align to: 69,  138, 208, 277ms
165Hz → frame = 6.1ms  → align to: 61,  122, 183, 244ms
```

In Hyprland:
```ini
# 60Hz: speed=5 → 500ms → 30 frames (clean)
# 60Hz: speed=3 → 300ms → 18 frames (clean)
# 60Hz: speed=4 → 400ms → 24 frames (clean)
```

---

## 133.7 Disabling Animations (Performance Mode)

For gaming workspaces or low-powered machines:

```ini
# Hyprland — disable per workspace via windowrulev2
windowrulev2 = noanim, workspace:5   # workspace 5 = gaming, no animations
windowrulev2 = noanim, class:^(cs2|dota2)$

# Or disable globally via IPC
hyprctl keyword animations:enabled false
hyprctl keyword animations:enabled true

# Keybind to toggle
bind = SUPER ALT, A, exec, \
  if hyprctl getoption animations:enabled | grep -q "int: 1"; then \
    hyprctl keyword animations:enabled false; \
  else \
    hyprctl keyword animations:enabled true; \
  fi
```

```kdl
// Niri — disable all
animations {
    off
}
```

---

## 133.8 Animation Debugging

Slow-motion mode for tuning (makes animations run at 10% speed):

```bash
# Hyprland — MISC config
misc {
    animate_manual_resizes = true   # animate resize drag
    animate_mouse_windowdragging = true

    # No slow-motion in Hyprland — use a long speed value instead:
    # animation = windows, 1, 50, bounce  → 5000ms = very slow for tuning
}
```

Benchmarking animation smoothness:

```bash
# Check if frames are dropping during animation
hyprctl monitors | grep "refresh"

# Watch compositor frame timing
WAYLAND_DEBUG=1 foot 2>&1 | grep -i "frame\|present"
```
