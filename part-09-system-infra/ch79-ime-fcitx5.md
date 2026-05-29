# Chapter 79 — Input Method Editors on Wayland: Fcitx5, IBus

## Overview
IMEs (Input Method Editors) allow typing in CJK (Chinese/Japanese/Korean),
Arabic, Indic scripts, and other languages requiring composition. Wayland's
IME protocol support lagged behind X11; the situation improved significantly
in 2023–2025.

## Sections

### 79.1 The Wayland IME Protocol Stack

```
User presses keys
    → Compositor receives key events
    → text-input-v3 protocol: compositor → IME framework
    → IME framework (Fcitx5/IBus) → generates composed character
    → text-input-v3: IME → compositor → focused app
```

Key protocols:
- `zwp-text-input-v3`: the standard text input protocol (input method)
- `zwp-input-method-v2`: IME side of the protocol (not yet universally supported)
- `gtk-text-input` (GNOME-specific): used by GTK apps on GNOME

**Reality check (2025):** Fcitx5 has the best Wayland support. IBus works but
has more quirks. Apps using Qt Wayland input method plugin work best.

### 79.2 Fcitx5 — Recommended IME

```bash
sudo pacman -S fcitx5 fcitx5-configtool fcitx5-qt fcitx5-gtk

# Chinese input engines:
sudo pacman -S fcitx5-chinese-addons    # Pinyin, Wubi, Cangjie, etc.
# Japanese:
sudo pacman -S fcitx5-mozc              # Mozc (Google's IME engine)
# Korean:
sudo pacman -S fcitx5-hangul
```

### 79.3 Environment Variables (Critical)

```bash
# /etc/environment or ~/.config/hypr/env.conf
GTK_IM_MODULE=fcitx
QT_IM_MODULE=fcitx
XMODIFIERS=@im=fcitx
SDL_IM_MODULE=fcitx
GLFW_IM_MODULE=ibus  # for some apps using GLFW
```

**Hyprland:**
```conf
# hyprland.conf
env = GTK_IM_MODULE,fcitx
env = QT_IM_MODULE,fcitx
env = XMODIFIERS,@im=fcitx
```

**NixOS:**
```nix
i18n.inputMethod = {
    enabled = "fcitx5";
    fcitx5.addons = with pkgs; [ fcitx5-chinese-addons fcitx5-mozc fcitx5-gtk ];
};
```

### 79.4 Starting Fcitx5

```conf
# hyprland.conf
exec-once = fcitx5 -d --replace
```

Or as a systemd user service:
```bash
systemctl --user enable --now fcitx5
```

**Verify it's running:**
```bash
fcitx5-diagnose   # diagnostic tool — very helpful for troubleshooting
```

### 79.5 Configuring Input Methods

```bash
fcitx5-configtool   # GUI configuration
```

Or edit `~/.config/fcitx5/config`:
```ini
[Hotkey]
TriggerKeys=Control+space  # or: Super+space

[Behavior]
DefaultInputMethod=pinyin  # default engine
```

**Add input methods:**
fcitx5-configtool → Input Method tab → Add → search for Pinyin/Mozc/Hangul

### 79.6 Fcitx5 Theming

```bash
sudo pacman -S fcitx5-material-color  # Material Design theme
# or: fcitx5-nord, fcitx5-catppuccin (AUR)
```

```ini
# ~/.config/fcitx5/conf/classicui.conf
Theme=catppuccin-mocha
Font=JetBrainsMono Nerd Font 11
```

### 79.7 IBus (Alternative)

```bash
sudo pacman -S ibus ibus-libpinyin ibus-mozc
```

```bash
# Environment
export GTK_IM_MODULE=ibus
export QT_IM_MODULE=ibus
export XMODIFIERS=@im=ibus

# Start
exec-once = ibus-daemon -drx
```

**IBus Wayland limitations (2025):**
- Input preview window may not position correctly in some apps
- Wayland native support is less complete than Fcitx5
- Qt Wayland: needs `IBUS_ENABLE_SYNC_MODE=1` for some apps

### 79.8 App-Specific Issues

**Firefox with Fcitx5:**
```bash
MOZ_ENABLE_WAYLAND=1   # already set
# Also ensure GTK_IM_MODULE=fcitx is in environment
```

**Electron apps (VS Code, etc.):**
```bash
# In flags file or launch options:
--enable-wayland-ime
```

**Terminal (Kitty, Foot):**
- Fcitx5 Wayland protocol (text-input-v3) supported in Kitty
- Foot: supported
- Alacritty: limited

**GTK4 apps:**
- Use fcitx5-gtk for the GTK4 input method module
- May need: `GTK_IM_MODULE=fcitx` explicitly (some GTK4 apps ignore it)

### 79.9 Troubleshooting

```bash
# Full diagnostic
fcitx5-diagnose 2>&1 | less

# Check if IME receives input
# → In an app, try Ctrl+Space to toggle IME mode

# Check protocol support
WAYLAND_DEBUG=1 fcitx5 2>&1 | grep -i "text-input"

# If input method works in GTK but not Qt:
# Ensure QT_IM_MODULE=fcitx and qt5-wayland/qt6-wayland installed
```
