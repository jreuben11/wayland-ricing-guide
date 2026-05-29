# Appendix E — Hyprland Configuration Quick Reference

## Monitor Configuration
```conf
monitor = NAME,WIDTHxHEIGHT@HZ,XxY,SCALE
monitor = DP-1,2560x1440@165,0x0,1
monitor = eDP-1,1920x1080@60,auto,1.5   # 'auto' = place right of previous
monitor = ,preferred,auto,1             # wildcard: any unmatched monitor
```

## Common Keybind Patterns
```conf
bind   = MOD, KEY, dispatcher, args   # normal bind
binde  = MOD, KEY, dispatcher, args   # repeat on hold
bindr  = MOD, KEY, dispatcher, args   # on release
bindm  = MOD, KEY, dispatcher, args   # mouse button bind
bindn  = MOD, KEY, dispatcher, args   # non-consuming (doesn't block key)
bindl  = MOD, KEY, dispatcher, args   # locked (works while screen locked)
```

## Essential Dispatchers
```conf
# Window management
bind = SUPER, Q, killactive
bind = SUPER, F, fullscreen, 0        # 0=fullscreen, 1=maximized
bind = SUPER SHIFT, F, togglefloating
bind = SUPER, P, pin                   # pin floating window

# Focus
bind = SUPER, H, movefocus, l
bind = SUPER, L, movefocus, r
bind = SUPER, K, movefocus, u
bind = SUPER, J, movefocus, d
bind = SUPER, Tab, cyclenext

# Move window
bind = SUPER SHIFT, H, movewindow, l
bind = SUPER SHIFT, L, movewindow, r

# Workspaces
bind = SUPER, 1, workspace, 1
bind = SUPER SHIFT, 1, movetoworkspace, 1
bind = SUPER, mouse_down, workspace, e+1   # scroll to next
bind = SUPER, S, togglespecialworkspace, magic

# Resize (binde = repeat)
binde = SUPER ALT, H, resizeactive, -20 0
binde = SUPER ALT, L, resizeactive, 20 0

# Exec
bind = SUPER, Return, exec, kitty
bind = SUPER, Space, exec, fuzzel
```

## Window Rules v2
```conf
# Syntax: windowrulev2 = action, predicates
windowrulev2 = float, class:^(pavucontrol)$
windowrulev2 = float, title:^(Picture-in-Picture)$
windowrulev2 = size 800 600, class:^(pavucontrol)$
windowrulev2 = center, class:^(pavucontrol)$
windowrulev2 = workspace 2 silent, class:^(firefox)$
windowrulev2 = opacity 0.92 0.85, class:^(kitty)$
windowrulev2 = nofocus, class:^()$, title:^()$, xwayland:1    # fix XWayland popups
windowrulev2 = tile, class:^(Spotify)$
windowrulev2 = noborder, fullscreen:1

# Predicates: class, title, workspace, monitor, xwayland, floating, fullscreen
```

## Layer Rules
```conf
layerrule = blur, waybar
layerrule = ignorezero, waybar           # don't blur transparent pixels
layerrule = animation slide top, waybar
layerrule = xray 1, waybar               # blur ignores windows behind
```

## Animations
```conf
animations {
    enabled = yes

    # Bezier curves
    bezier = overshot, 0.05, 0.9, 0.1, 1.05
    bezier = smoothOut, 0.36, 0, 0.66, -0.56
    bezier = smoothIn, 0.25, 1, 0.5, 1

    # Window animations
    animation = windows, 1, 5, overshot, slide
    animation = windowsOut, 1, 4, smoothOut, slide
    animation = windowsMove, 1, 4, smoothIn, slide

    # Fade
    animation = fade, 1, 3, smoothIn
    animation = fadeOut, 1, 3, smoothOut

    # Workspaces
    animation = workspaces, 1, 6, overshot, slidevert
    # or: slide, slidevert, fade, slidefadevert, slidefade

    # Layer surfaces
    animation = layers, 1, 3, default, slide
    animation = layersIn, 1, 3, overshot, slide
}
```

## Decoration
```conf
decoration {
    rounding = 10

    blur {
        enabled = true
        size = 8
        passes = 2
        new_optimizations = on
        xray = false          # blur through windows (performance cost)
    }

    drop_shadow = yes
    shadow_range = 4
    shadow_render_power = 3
    col.shadow = rgba(1a1a1aee)

    active_opacity = 1.0
    inactive_opacity = 0.9
    fullscreen_opacity = 1.0

    dim_inactive = false
    dim_strength = 0.1
}
```

## General Layout
```conf
general {
    gaps_in = 5
    gaps_out = 10
    border_size = 2
    col.active_border = rgba(89b4faee) rgba(cba6f7ee) 45deg
    col.inactive_border = rgba(595959aa)
    layout = dwindle   # or: master
    resize_on_border = true
}
```

## Dwindle Layout
```conf
dwindle {
    pseudotile = yes
    preserve_split = yes
    smart_split = false
    force_split = 2          # 0=follow cursor, 1=always left/top, 2=always right/bottom
}
```

## Master Layout
```conf
master {
    new_is_master = false
    mfact = 0.55             # master window ratio
    orientation = left       # left, right, top, bottom, center
    inherit_fullscreen = true
}
```

## Input
```conf
input {
    kb_layout = us
    kb_variant =
    kb_options = caps:escape   # Caps → Esc

    follow_mouse = 1
    sensitivity = 0
    accel_profile = flat
    numlock_by_default = true

    touchpad {
        natural_scroll = yes
        tap-to-click = yes
        disable_while_typing = yes
        scroll_factor = 0.3
    }
}

gestures {
    workspace_swipe = on
    workspace_swipe_fingers = 3
    workspace_swipe_distance = 300
}
```

## Misc Performance
```conf
misc {
    vfr = true                   # variable frame rate — battery saver
    vrr = 2                      # VRR: 0=off, 1=always, 2=fullscreen only
    no_direct_scanout = false
    disable_hyprland_logo = true
    disable_splash_rendering = true
    force_default_wallpaper = 0
    new_window_takes_over_fullscreen = 2
}
```

## Environment Variables (in hyprland.conf)
```conf
env = XCURSOR_SIZE,24
env = XCURSOR_THEME,Catppuccin-Mocha-Dark-Cursors
env = QT_QPA_PLATFORM,wayland
env = QT_QPA_PLATFORMTHEME,qt5ct
env = QT_STYLE_OVERRIDE,kvantum
env = MOZ_ENABLE_WAYLAND,1
env = GDK_BACKEND,wayland,x11
env = GTK_IM_MODULE,fcitx
env = QT_IM_MODULE,fcitx
env = XDG_CURRENT_DESKTOP,Hyprland
env = XDG_SESSION_TYPE,wayland
```

## hyprctl Reference
```bash
hyprctl monitors [-j]
hyprctl clients [-j]
hyprctl workspaces [-j]
hyprctl activewindow [-j]
hyprctl dispatch <dispatcher> [args]
hyprctl keyword <key> <value>
hyprctl reload
hyprctl version
hyprctl setcursor <theme> <size>
hyprctl plugin load <path>
```
