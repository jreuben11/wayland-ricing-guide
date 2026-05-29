# Chapter 66 — KDE Plasma 6 on Wayland

## Overview
KDE Plasma 6 (released February 2024) made Wayland the default session, completing
a multi-year migration. It's the most feature-complete Wayland desktop: HDR,
fractional scaling, color management, virtual desktops, and the most polished
NVIDIA support of any compositor. It's also highly riceable.

## Sections

### 66.1 Why KDE Plasma 6 Matters
- Wayland default since Plasma 6.0 (February 2024)
- **HDR**: production-ready, the only DE with full HDR pipeline (2025)
- **Color management**: ICC profiles, wide gamut, HDR tone mapping
- **Best NVIDIA support**: explicit sync, tested at scale
- **Fractional scaling**: protocol-native, apps render at correct DPI
- **Virtual desktops**: full implementation (Hyprland has workspaces, KDE has both)
- **Activities**: separate window/desktop sets (unique to KDE)
- Settings GUI: everything configurable without touching config files
- KWin Scripts: JavaScript/QML compositor automation

### 66.2 Installation

**Arch:**
```bash
sudo pacman -S plasma-meta kde-applications-meta sddm
sudo systemctl enable sddm
```

**Minimal Plasma (no extra apps):**
```bash
sudo pacman -S plasma-desktop kwin sddm konsole dolphin
sudo systemctl enable sddm
```

**NixOS:**
```nix
services.desktopManager.plasma6.enable = true;
services.displayManager.sddm.enable = true;
services.displayManager.defaultSession = "plasmawayland";
```

### 66.3 KWin Configuration

KWin is both the compositor and the window manager. Configure via:
- **System Settings → Window Management**: tiling, focus, virtual desktops
- **System Settings → Compositor**: VSync, tear prevention, OpenGL backend
- `~/.config/kwinrc`: direct config file
- `qdbus org.kde.KWin /KWin reconfigure`: reload after manual edits

**Key KWin settings for performance:**
```ini
# ~/.config/kwinrc
[Compositing]
Backend=OpenGL
GLCore=true
LatencyPolicy=High      # reduce input latency
OpenGLIsUnsafe=false
```

### 66.4 KWin Tiling

Plasma 6.1+ includes native tiling:
- System Settings → Window Management → Tiling
- Keyboard-driven: `Meta+T` to toggle tiling mode
- Quarter, half, 2/3 presets
- Per-virtual-desktop tiling state

**Krohnkite** (scripted tiling, like i3 in KWin):
```bash
kpackagetool6 --type KWin/Script --install krohnkite.kwinscript
```
Layouts: tile, monocle, spread, stacking.

### 66.5 Plasma Theming — Ricing KDE

**Global Theme** (one-click complete rice):
- System Settings → Appearance → Global Theme
- Installs: color scheme + Plasma style + window decorations + icons + cursor

**Component-by-component:**
```
Plasma Style     → System Settings → Appearance → Plasma Style
Color Scheme     → System Settings → Appearance → Colors
Window Deco      → System Settings → Appearance → Window Decorations
Icons            → System Settings → Appearance → Icons
Cursors          → System Settings → Appearance → Cursors
Fonts            → System Settings → Appearance → Fonts
Splash Screen    → System Settings → Appearance → Splash Screen
Login Screen     → System Settings → Startup and Shutdown → Login Screen (SDDM)
```

**Popular KDE themes:**
- **Sweet**: dark, candy-colored, very popular
- **Catppuccin KDE**: Catppuccin port (Mocha/Frappe/etc)
- **Layan**: clean flat macOS-inspired
- **Nordic**: Nord palette
- **Orchis KDE**: material-ish

**Installing from KDE Store:**
System Settings → Get New... button on any appearance category.

### 66.6 KDE Widgets (Plasmoids)

Plasma widgets are QML-based and run inside the desktop or panel:
```bash
# Install widget from store
plasmapkg2 --install widget.plasmoid

# List installed widgets
plasmapkg2 --list
```

**Popular widgets for ricing:**
- **Eventcalendar**: google/local calendar in panel
- **Plasma Customization Saver**: save/restore complete setups
- **Window Title Applet**: show focused window title in panel
- **Memory/CPU/GPU monitor** widgets
- **Latte Dock** → largely superseded by Plasma 6 panel improvements

### 66.7 KDE Latte Dock Alternative: Plasma Panel

Plasma 6 panels have improved enough to replace Latte Dock for most:
```
Right-click panel → Add Panel → Application Dashboard
Panel settings → Height, position, floating mode
Add widgets → drag to panel
```

Floating panel: right-click → Edit Panel → toggle floating mode.

### 66.8 HDR Setup on KDE

```
System Settings → Display and Monitor → HDR
Toggle: Enable HDR
SDR brightness: 200-400 nits
Peak brightness: your display's spec
```

**Per-app HDR**: KWin routes HDR-capable apps through the HDR pipeline automatically.
**SDR content**: tone-mapped to HDR headroom.

### 66.9 KWin Scripts

KWin scripts run JavaScript to automate window management:
```javascript
// ~/.local/share/kwin/scripts/myscript/contents/code/main.js
workspace.windowActivated.connect(function(window) {
    if (window.resourceClass === "firefox")
        workspace.currentDesktop = workspace.desktops[0];
});
```
Install: `kpackagetool6 --type KWin/Script --install myscript.kwinscript`

### 66.10 KDE vs. Custom Compositor Rices

| Aspect | KDE | Hyprland+Quickshell |
|--------|-----|---------------------|
| Setup time | 30 minutes | Days |
| HDR | Production-ready | Experimental |
| NVIDIA | Best | Good (explicit sync) |
| Customizability ceiling | High but bounded | Unlimited |
| Community rice culture | Moderate | Huge |
| Config reproducibility | Partial (Nix module exists) | Excellent (Nix/HM) |
| Animations | Good | Exceptional |
| Resource usage | ~600 MB RAM | ~200 MB RAM |
