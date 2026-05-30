# Chapter 66 — KDE Plasma 6 on Wayland

## Contents

- [Overview](#overview)
- [66.1 Why KDE Plasma 6 Matters](#661-why-kde-plasma-6-matters)
- [66.2 Installation](#662-installation)
  - [Arch Linux](#arch-linux)
  - [Fedora](#fedora)
  - [Ubuntu / Kubuntu](#ubuntu-kubuntu)
  - [NixOS (declarative)](#nixos-declarative)
  - [Session Verification](#session-verification)
- [66.3 KWin Configuration](#663-kwin-configuration)
  - [Core Compositor Settings](#core-compositor-settings)
  - [Window Behavior and Focus Policy](#window-behavior-and-focus-policy)
  - [NVIDIA-Specific KWin Settings](#nvidia-specific-kwin-settings)
- [66.4 KWin Tiling](#664-kwin-tiling)
  - [Native Tiling (Plasma 6.1+)](#native-tiling-plasma-61)
  - [Krohnkite: Scripted Dynamic Tiling](#krohnkite-scripted-dynamic-tiling)
  - [Bismuth (Alternative to Krohnkite)](#bismuth-alternative-to-krohnkite)
- [66.5 Plasma Theming — Ricing KDE](#665-plasma-theming-ricing-kde)
  - [The Theming Layers](#the-theming-layers)
  - [Installing Themes](#installing-themes)
  - [Popular KDE Themes for Ricing](#popular-kde-themes-for-ricing)
  - [Kvantum: Advanced Qt5/Qt6 Theming](#kvantum-advanced-qt5qt6-theming)
  - [KDE Color Scheme Files](#kde-color-scheme-files)
- [66.6 KDE Widgets (Plasmoids)](#666-kde-widgets-plasmoids)
  - [Managing Widgets](#managing-widgets)
  - [Popular Widgets for Ricing](#popular-widgets-for-ricing)
  - [Writing a Custom Widget](#writing-a-custom-widget)
- [66.7 Panel and Dock Configuration](#667-panel-and-dock-configuration)
  - [Plasma 6 Native Panels](#plasma-6-native-panels)
  - [Panel Opacity and Blur](#panel-opacity-and-blur)
- [66.8 HDR and Color Management](#668-hdr-and-color-management)
  - [Enabling HDR](#enabling-hdr)
  - [ICC Profile Integration](#icc-profile-integration)
  - [Night Color (Redshift-equivalent)](#night-color-redshift-equivalent)
- [66.9 Input Configuration](#669-input-configuration)
  - [Touchpad and Mouse](#touchpad-and-mouse)
  - [Keyboard Shortcuts](#keyboard-shortcuts)
- [66.10 KWin Scripts](#6610-kwin-scripts)
  - [Script Installation](#script-installation)
  - [Example: Pin Firefox to Virtual Desktop 1](#example-pin-firefox-to-virtual-desktop-1)
  - [Example: Force Floating for Picture-in-Picture](#example-force-floating-for-picture-in-picture)
  - [Example: Auto-maximize on Large Monitor, Float on Small](#example-auto-maximize-on-large-monitor-float-on-small)
  - [Window Rules (No Scripting Required)](#window-rules-no-scripting-required)
- [66.11 SDDM Login Screen Theming](#6611-sddm-login-screen-theming)
- [66.12 KDE vs. Custom Compositor Rices](#6612-kde-vs-custom-compositor-rices)
- [66.13 Troubleshooting](#6613-troubleshooting)
  - [Session starts in X11 instead of Wayland](#session-starts-in-x11-instead-of-wayland)
  - [KWin crashes on startup](#kwin-crashes-on-startup)
  - [Black screen after login](#black-screen-after-login)
  - [Fractional scaling looks blurry (XWayland apps)](#fractional-scaling-looks-blurry-xwayland-apps)
  - [Plasma Shell (plasmashell) crashes or freezes](#plasma-shell-plasmashell-crashes-or-freezes)
  - [Screen tearing with NVIDIA](#screen-tearing-with-nvidia)
  - [KWin effects not working (blur, transparency)](#kwin-effects-not-working-blur-transparency)
  - [High CPU usage from plasmashell](#high-cpu-usage-from-plasmashell)

---


## Overview

KDE Plasma 6 (released February 2024) made Wayland the default session, completing
a multi-year migration. It is the most feature-complete Wayland desktop: HDR,
fractional scaling, color management, virtual desktops, and the most polished
NVIDIA support of any compositor. It is also highly riceable, combining a full
Qt/QML theming stack with KWin's scriptable compositor engine.

Unlike tiling compositors such as Hyprland (see Ch 60) or Sway (see Ch 55),
Plasma 6 ships a complete desktop environment — panel system, file manager,
notification daemon, network applet, Bluetooth applet, screen locking, and more —
all tightly integrated and configurable through both a GUI settings application
and hand-editable INI-format configuration files.

This chapter covers installation across major distributions, deep KWin tuning,
tiling configurations, theming via Plasma's layered appearance system, widget
development and installation, HDR/color management, input configuration, SDDM
login theming, KWin scripting, and diagnostics for common failure modes.

*See Ch 53 for session startup and display-manager integration. See Ch 70 for
Wayland protocol debugging. See Ch 58 for NVIDIA driver preparation.*

---

## 66.1 Why KDE Plasma 6 Matters

Plasma 6 represents the culmination of roughly six years of incremental KWin
Wayland work. The jump from Plasma 5 to 6 dropped X11 as the default and aligned
the entire stack — KWin, Plasma Shell, Qt6 — on a single Wayland-native code path.
The practical result is that many features that were "works on X11 but broken on
Wayland" are now fully operational.

HDR is the headline feature distinguishing Plasma 6 from every other Wayland
compositor in 2025. KWin implements HDR10 with proper PQ (Perceptual Quantizer)
transfer function handling, ICC profile injection per output, and per-window
tone mapping for SDR apps playing on an HDR display. This is handled at the
compositor level without requiring per-app patching, which is architecturally
superior to application-side solutions.

Explicit sync support (landed in KWin 6.1) resolved the class of GPU hangs and
screen tearing that plagued NVIDIA cards on Wayland. KWin negotiates the
`linux-drm-syncobj-v1` protocol with Mesa/NVIDIA drivers, ensuring framebuffer
handoff happens only after rendering completes. This makes KDE Plasma 6 the
recommended Wayland environment for NVIDIA users as of mid-2025.

Fractional scaling uses the `wp-fractional-scale-v1` protocol, meaning XDG
toplevel surfaces render at the logical pixel density the compositor advertises
rather than being scaled up from integer resolution. GTK4 and Qt6 apps render
crisply at 1.25×, 1.5×, 1.75× without blurring. XWayland apps still render at
integer scale and are then upscaled, but most native applications benefit fully.

| Feature | Plasma 6 | Hyprland | Sway | GNOME 46+ |
|---------|----------|----------|------|-----------|
| Wayland default | Yes (6.0) | Yes | Yes | Yes (3.36) |
| HDR pipeline | Production | Experimental | No | Partial |
| Fractional scaling | wp-fractional-scale-v1 | wp-fractional-scale-v1 | No | Yes |
| Explicit sync | Yes (6.1+) | Yes | No | Yes |
| NVIDIA support | Best | Good | Fair | Good |
| KWin tiling | Native (6.1+) | N/A | N/A | N/A |
| Activities | Yes | No | No | No |
| Config reproducibility | Good (Nix module) | Excellent | Excellent | Fair |
| Setup time | ~30 min | Days | Hours | ~15 min |
| RAM baseline | ~600 MB | ~200 MB | ~120 MB | ~700 MB |

Activities are a KDE-unique concept: separate, independently-named window and
desktop sets that persist across reboots. A "Work" activity can have its own
virtual desktops, wallpaper, and running application set, completely distinct
from a "Personal" activity. No other major compositor or DE implements this.

---

## 66.2 Installation

### Arch Linux

For a full Plasma experience including the application suite:

```bash
sudo pacman -S plasma-meta kde-applications-meta sddm
sudo systemctl enable sddm
```

For a minimal installation — compositor, shell, terminal, file manager only:

```bash
sudo pacman -S plasma-desktop kwin sddm konsole dolphin \
    plasma-nm plasma-pa kscreen bluedevil powerdevil
sudo systemctl enable sddm
```

`plasma-nm` provides the network applet (NetworkManager integration). `plasma-pa`
provides PulseAudio/PipeWire volume control. `kscreen` is required for display
configuration. Without `powerdevil`, suspend/hibernate integration is absent.

### Fedora

```bash
sudo dnf groupinstall "KDE Plasma Workspaces"
sudo systemctl set-default graphical.target
```

Fedora ships KDE Plasma as a spin; using the KDE spin ISO is cleaner than
installing the group into a GNOME base. The spin configures SDDM, sets the
default session to `plasmawayland`, and pre-installs PipeWire integration.

### Ubuntu / Kubuntu

```bash
sudo apt install kubuntu-desktop sddm
sudo dpkg-reconfigure sddm   # set as default display manager
```

Or start from the Kubuntu 24.04+ ISO, which ships Plasma 6 with Wayland default.

### NixOS (declarative)

```nix
# /etc/nixos/configuration.nix
services.desktopManager.plasma6.enable = true;
services.displayManager.sddm = {
  enable = true;
  wayland.enable = true;       # SDDM itself runs on Wayland
};
services.displayManager.defaultSession = "plasma";

# Optional: exclude KDE apps you don't want
environment.plasma6.excludePackages = with pkgs.kdePackages; [
  elisa
  khelpcenter
  okular
];
```

Rebuild with `sudo nixos-rebuild switch`. The `plasma` session name (without
`wayland` suffix) is correct for Plasma 6 NixOS — the session file sets
`PLASMA_USE_QT_SCALING=1` and launches `startplasma-wayland` automatically.

### Session Verification

After logging in through SDDM:

```bash
echo $WAYLAND_DISPLAY          # should print: wayland-0 or wayland-1
echo $XDG_SESSION_TYPE         # should print: wayland
loginctl show-session $XDG_SESSION_ID | grep Type   # Type=wayland
```

If `XDG_SESSION_TYPE=x11` appears, SDDM launched the X11 session. Ensure the
SDDM session chooser is set to "Plasma (Wayland)" rather than "Plasma (X11)".

*See Ch 53 for detailed display manager configuration and session file locations.*

---

## 66.3 KWin Configuration

KWin is both the Wayland compositor and the window manager in Plasma. It handles
rendering (via OpenGL/Vulkan), compositing, window placement, animations,
keyboard shortcuts, and Virtual Desktop management. Its configuration lives in
`~/.config/kwinrc` (INI format).

All changes to `kwinrc` can be applied at runtime without restarting the session:

```bash
qdbus org.kde.KWin /KWin reconfigure
```

### Core Compositor Settings

```ini
# ~/.config/kwinrc

[Compositing]
# Use OpenGL (EGL) backend — recommended for all hardware
Backend=OpenGL
# Core profile for better performance on modern GPUs
GLCore=true
# Reduce input latency by allowing tearing in games (per-window override)
LatencyPolicy=High
# Disable if GPU falsely flagged as broken
OpenGLIsUnsafe=false
# VSync method: automatic lets KWin choose; can force: full, re-use
VSync=true

[Effect-overview]
# Desktop overview (Meta+W) animation speed — lower is faster
BorderActivate=9

[ElectricBorders]
# Hot corners: 0=none, 1=show desktop, 2=lock screen, etc.
TopLeft=0
TopRight=9
BottomRight=13

[Plugins]
# Individual effects
blurEnabled=true
contrastEnabled=true
kwin4_effect_fadeEnabled=true
zoomEnabled=false
```

### Window Behavior and Focus Policy

```ini
# ~/.config/kwinrc

[Windows]
# FocusPolicy: ClickToFocus, FocusFollowsMouse, FocusUnderMouse
FocusPolicy=ClickToFocus
# Bring focused window to front immediately
AutoRaise=false
# Delay for FocusFollowsMouse mode (ms)
AutoRaiseInterval=750
# Prevent apps from stealing focus
FocusStealingPreventionLevel=1

[Desktops]
Number=4
Rows=1
# Wrap-around when switching at edge
RollOverDesktops=true

[TabBox]
# Alt+Tab switcher style
LayoutName=thumbnail_grid
```

Apply with `qdbus org.kde.KWin /KWin reconfigure`.

### NVIDIA-Specific KWin Settings

For NVIDIA with explicit sync (driver 545+ required):

```ini
# ~/.config/kwinrc
[Compositing]
Backend=OpenGL
GLCore=true
# Explicit sync is negotiated automatically; no manual toggle needed
# If you see glitches, force software cursor:
SoftwareCursor=false
```

Set environment variables via `/etc/environment` or SDDM's environment file:

```bash
# /etc/environment (system-wide) or ~/.config/environment.d/nvidia.conf
KWIN_DRM_USE_EGL_STREAMS=0
KWIN_DRM_NO_AMS=0
__GL_GSYNC_ALLOWED=1
__GL_VRR_ALLOWED=1
```

---

## 66.4 KWin Tiling

### Native Tiling (Plasma 6.1+)

Plasma 6.1 introduced a built-in tiling system managed directly by KWin. It
operates per-virtual-desktop and supports both keyboard-driven and mouse-driven
workflow. Enable it in System Settings → Window Management → Tiling.

Key bindings for native tiling:

| Action | Default Keybind |
|--------|----------------|
| Toggle tiling on desktop | Meta+T |
| Tile window left half | Meta+Left |
| Tile window right half | Meta+Right |
| Tile window top-left quarter | Meta+U |
| Tile window top-right quarter | Meta+I |
| Tile window bottom-left quarter | Meta+J |
| Tile window bottom-right quarter | Meta+K |
| Maximize | Meta+Up |
| Minimize | Meta+Down |

These bindings are configurable in System Settings → Shortcuts → KWin.

Native tiling uses a "tile tree" model. Each virtual desktop has a root tile.
New windows are inserted into available slots. The tiling layout per-desktop
can be saved and restored across sessions.

### Krohnkite: Scripted Dynamic Tiling

Krohnkite is a KWin script implementing dynamic tiling similar to i3/bspwm.
It supports multiple layout algorithms and runs entirely within KWin's JavaScript
environment:

```bash
# Download from KDE Store or GitHub
wget https://github.com/esjeon/krohnkite/releases/latest/download/krohnkite.kwinscript

# Install
kpackagetool6 --type KWin/Script --install krohnkite.kwinscript

# Enable in System Settings → Window Management → KWin Scripts
```

Configure Krohnkite layout shortcuts:

```ini
# ~/.config/kwinrc
# These are set by the Krohnkite install, shown here for reference
[Script-krohnkite]
# Layout cycling: Tile, MonocleLayout, SpreadLayout, FloatingLayout
enableTileLayout=true
enableMonocleLayout=true
enableSpreadLayout=true
enableFloatingLayout=false
screenGapTop=4
screenGapBottom=4
screenGapLeft=4
screenGapRight=4
tileLayoutGap=4
```

Set shortcuts via System Settings → Shortcuts → search "Krohnkite".

### Bismuth (Alternative to Krohnkite)

```bash
# Install Bismuth from Arch AUR
yay -S plasma6-bismuth

# Or from KDE Store
plasmapkg2 --install bismuth.kwinscript
```

Bismuth offers a GUI configuration panel inside System Settings and supports
the same layouts as Krohnkite with a more polished integration for Plasma 6.

---

## 66.5 Plasma Theming — Ricing KDE

### The Theming Layers

KDE's appearance system is layered. Each layer can be changed independently:

| Layer | Location | File format |
|-------|----------|-------------|
| Global Theme | System Settings → Appearance → Global Theme | `.tar.gz` bundle |
| Plasma Style | System Settings → Appearance → Plasma Style | QML + SVG |
| Color Scheme | System Settings → Appearance → Colors | `.colors` (KConfig) |
| Window Decorations | System Settings → Appearance → Window Decorations | Aurorae/KDecoration2 |
| Icons | System Settings → Appearance → Icons | `.tar.gz` XDG icon theme |
| Cursors | System Settings → Appearance → Cursors | XCursor bundle |
| Fonts | System Settings → Appearance → Fonts | system fonts |
| GTK Theme | System Settings → Appearance → Legacy App Style | GTK2/3/4 theme |
| Splash Screen | System Settings → Startup and Shutdown → Splash Screen | QML |
| Login Screen | System Settings → Startup and Shutdown → Login Screen | SDDM theme |

A Global Theme sets all layers simultaneously. Individual layers can be overridden
after applying a global theme.

### Installing Themes

#### From the KDE Store (GUI)

Every System Settings appearance category has a "Get New..." button (or "Get New
[Type]..."). This fetches from `store.kde.org` directly. After download, the
theme is immediately available for selection.

#### From the Command Line

```bash
# Install a Plasma style
kpackagetool6 --type Plasma/Theme --install /path/to/theme.tar.gz

# Install a Global Theme
kpackagetool6 --type Plasma/LookAndFeel --install /path/to/theme.tar.gz

# Install a window decoration
kpackagetool6 --type KDecoration2/DecorationTheme --install /path/to/deco.tar.gz

# List installed themes of a type
kpackagetool6 --type Plasma/Theme --list

# Install a cursor theme (standard XDG method)
mkdir -p ~/.local/share/icons
tar -xzf cursor-theme.tar.gz -C ~/.local/share/icons/
```

#### Via Arch AUR

```bash
# Catppuccin KDE — comprehensive port
yay -S catppuccin-kde-theme-git

# Sweet theme
yay -S plasma6-themes-sweet-git

# Nordic theme
yay -S plasma-theme-nordic
```

### Popular KDE Themes for Ricing

| Theme | Style | Components |
|-------|-------|-----------|
| Sweet | Dark candy, vibrant purples | Plasma + Colors + Deco + Icons |
| Catppuccin KDE | Pastel, multiple flavors | Plasma + Colors + Kvantum |
| Layan | Flat macOS-inspired | Plasma + Colors + Deco |
| Nordic | Nord palette, cool blues | Plasma + Colors + Deco + Icons |
| Orchis KDE | Material-influenced | Plasma + Colors + Deco |
| Utterly Sweet | Updated Sweet fork | Full suite |
| Breeze (default) | Clean, neutral | Full suite |

### Kvantum: Advanced Qt5/Qt6 Theming

Kvantum is an SVG-based Qt theme engine that enables far more detailed styling
than stock QStyle allows:

```bash
# Arch
sudo pacman -S kvantum kvantum-qt5

# Ubuntu/Debian
sudo apt install qt6ct kvantum

# Set Kvantum as Qt style
cat > ~/.config/qt6ct/qt6ct.conf << 'EOF'
[Appearance]
style=kvantum-dark
EOF

# Or export environment variable
echo 'QT_STYLE_OVERRIDE=kvantum-dark' >> ~/.config/environment.d/qt.conf
```

Install a Kvantum theme:

```bash
kvantummanager --install /path/to/KvTheme.tar.gz
kvantummanager   # GUI: select installed theme
```

Popular Kvantum themes: `KvMat`, `KvLibadwaita`, `Catppuccin-Mocha-Kvantum`.

### KDE Color Scheme Files

Color scheme files live in `~/.local/share/color-schemes/`:

```ini
# ~/.local/share/color-schemes/MyDark.colors
[ColorEffects:Disabled]
ChangeSelectionColor=true
Color=112,111,110
ColorAmount=0
ColorEffect=0
ContrastAmount=0.65
ContrastEffect=1
GrayAmount=0.35
GrayEffect=2
IntensityAmount=0
IntensityEffect=0

[ColorEffects:Inactive]
ChangeSelectionColor=false
Color=112,111,110
ColorAmount=0.025
ColorEffect=2
ContrastAmount=0.1
ContrastEffect=2
GrayAmount=0.85
GrayEffect=2
IntensityAmount=0
IntensityEffect=0

[Colors:Button]
BackgroundAlternate=30,87,116
BackgroundNormal=49,54,59
DecorationFocus=61,174,233
DecorationHover=61,174,233
ForegroundActive=61,174,233
ForegroundInactive=161,169,177
ForegroundLink=41,128,185
ForegroundNegative=218,68,83
ForegroundNeutral=246,116,0
ForegroundNormal=252,252,252
ForegroundPositive=39,174,96
ForegroundVisited=127,140,141

[Colors:View]
BackgroundAlternate=27,30,32
BackgroundNormal=35,38,41
DecorationFocus=61,174,233
DecorationHover=61,174,233
ForegroundActive=61,174,233
ForegroundInactive=161,169,177
ForegroundLink=41,128,185
ForegroundNegative=218,68,83
ForegroundNeutral=246,116,0
ForegroundNormal=252,252,252
ForegroundPositive=39,174,96
ForegroundVisited=127,140,141

[Colors:Window]
BackgroundAlternate=49,54,59
BackgroundNormal=42,46,50
DecorationFocus=61,174,233
DecorationHover=61,174,233
ForegroundActive=61,174,233
ForegroundInactive=161,169,177
ForegroundLink=41,128,185
ForegroundNegative=218,68,83
ForegroundNeutral=246,116,0
ForegroundNormal=252,252,252
ForegroundPositive=39,174,96
ForegroundVisited=127,140,141

[General]
ColorScheme=MyDark
Name=My Dark
shadeSortColumn=true

[KDE]
contrast=4
```

Apply via: `plasma-apply-colorscheme ~/.local/share/color-schemes/MyDark.colors`

---

## 66.6 KDE Widgets (Plasmoids)

Plasma widgets (plasmoids) are QML components that run inside the Plasma Shell.
They can be placed on the desktop canvas, inside panels, or attached to system
tray area. They are isolated from each other but have access to Plasma's data
engines (weather, system stats, network, etc.).

### Managing Widgets

```bash
# Install a .plasmoid file
kpackagetool6 --type Plasma/Applet --install /path/to/widget.plasmoid

# List installed applets
kpackagetool6 --type Plasma/Applet --list

# Remove a widget
kpackagetool6 --type Plasma/Applet --remove org.kde.plasma.mywidget

# Restart Plasma Shell to pick up new widgets (without full logout)
kquitapp6 plasmashell && kstart plasmashell
```

### Popular Widgets for Ricing

| Widget | Function | Install Method |
|--------|----------|---------------|
| Eventcalendar | Calendar + Google/local events in panel | KDE Store |
| Window Title Applet | Show focused window title | KDE Store |
| Plasma Customization Saver | Save/restore full rice state | KDE Store |
| System Monitor (CPU/RAM/GPU) | Resource graphs in panel | Built-in |
| Media Controller | MPRIS playback control | Built-in |
| Panon | Audio visualizer on desktop | KDE Store |
| Simple Clock | Highly customizable clock | KDE Store |
| Netspeed Widget | Upload/download in panel | KDE Store |

### Writing a Custom Widget

Widgets live in `~/.local/share/plasma/plasmoids/<widget-id>/`. Minimal structure:

```
~/.local/share/plasma/plasmoids/org.example.mywidget/
├── metadata.json
└── contents/
    └── ui/
        └── main.qml
```

```json
// metadata.json
{
  "KPlugin": {
    "Id": "org.example.mywidget",
    "Name": "My Widget",
    "Description": "Shows current hostname",
    "Version": "1.0",
    "Category": "System Information",
    "Icon": "computer-symbolic"
  },
  "X-Plasma-API-Minimum-Version": "6.0"
}
```

```qml
// contents/ui/main.qml
import QtQuick 2.15
import org.kde.plasma.components 3.0 as PlasmaComponents
import org.kde.plasma.plasmoid 2.0

PlasmoidItem {
    id: root
    preferredRepresentation: compactRepresentation

    compactRepresentation: PlasmaComponents.Label {
        text: Qt.platform.os + ": " + (typeof Qt !== 'undefined' ? Qt.application.name : "")
        font.pixelSize: 14
        color: Kirigami.Theme.textColor
    }
}
```

Install and restart plasmashell to test:

```bash
kpackagetool6 --type Plasma/Applet --install ~/.local/share/plasma/plasmoids/org.example.mywidget
kquitapp6 plasmashell && kstart plasmashell
```

---

## 66.7 Panel and Dock Configuration

### Plasma 6 Native Panels

Plasma 6 panels improved significantly over Plasma 5, making Latte Dock
unnecessary for most use cases. Panels support:

- Floating mode (gap between panel and screen edge)
- Auto-hide (dodge windows or fully hide)
- Variable opacity (opaque, translucent, adaptive based on wallpaper)
- Per-screen panel assignment
- Multiple panels simultaneously

Right-click the desktop → Add Panel → choose a preset, then enter edit mode
to add/remove/rearrange widgets.

```bash
# Apply panel layout from a saved Global Theme
plasma-apply-lookandfeel --apply org.kde.breezedark.desktop

# Reset panel to defaults (CAUTION: removes custom panels)
# plasma-apply-lookandfeel --apply org.kde.breeze.desktop --resetLayout
```

### Panel Opacity and Blur

For a frosted-glass transparent panel:

1. Enter panel edit mode (right-click → Edit Panel)
2. Open Appearance tab
3. Set Opacity to "Adaptive" or set a fixed value
4. Enable "Blur" under System Settings → Workspace Behavior → Desktop Effects → Blur

The blur effect requires the KWin blur plugin to be active:

```ini
# ~/.config/kwinrc
[Plugins]
blurEnabled=true

[Effect-blur]
BlurStrength=10
NoiseStrength=0
```

Reload: `qdbus org.kde.KWin /KWin reconfigure`

---

## 66.8 HDR and Color Management

### Enabling HDR

HDR requires:
1. A display that supports HDR10 (advertises via EDID)
2. KDE Plasma 6.0+ with KWin on Wayland
3. A GPU with HDR-capable KMS support (most AMD GCN4+, NVIDIA 700+, Intel Xe)

```
System Settings → Display and Monitor → Display Configuration
→ Select HDR-capable monitor
→ Enable HDR: On
→ SDR brightness: 200–400 nits (match room lighting)
→ Peak brightness: your display's specified peak (e.g., 1000 for most HDR600+)
```

KWin handles tone mapping for SDR applications automatically. SDR content is
lifted to the HDR headroom using a configurable "SDR brightness" value as the
white point.

### ICC Profile Integration

```bash
# Install a monitor ICC profile
mkdir -p ~/.local/share/icc
cp MyMonitor.icc ~/.local/share/icc/

# Apply via colord (KWin picks it up through colord-kde)
colormgr import-profile ~/.local/share/icc/MyMonitor.icc
colormgr device-get-default-profile display_$(xrandr --query | grep ' connected' | head -1 | awk '{print $1}')
```

System Settings → Display and Monitor → Color Corrections → Add Profile

### Night Color (Redshift-equivalent)

```
System Settings → Display and Monitor → Night Color
→ Enable Night Color
→ Mode: Automatic location, Manual location, or Sun position
→ Night Color Temperature: 2700K–4000K typical
→ Transition duration: 30 min recommended
```

Via `kwriteconfig6`:

```bash
kwriteconfig6 --file kwinrc --group NightColor --key Active true
kwriteconfig6 --file kwinrc --group NightColor --key Mode 0
kwriteconfig6 --file kwinrc --group NightColor --key NightTemperature 3000
qdbus org.kde.KWin /KWin reconfigure
```

---

## 66.9 Input Configuration

### Touchpad and Mouse

```
System Settings → Input Devices → Touchpad
→ Tap-to-click
→ Natural scrolling
→ Pointer acceleration / speed
```

Via `kwriteconfig6` for scripting:

```bash
# Enable tap-to-click
kwriteconfig6 --file touchpadxlibinputrc --group "SynPS/2 Synaptics TouchPad" \
    --key tapToClick true

# Enable natural scrolling
kwriteconfig6 --file touchpadxlibinputrc --group "SynPS/2 Synaptics TouchPad" \
    --key naturalScroll true

# Reload input configuration
xinput --list   # lists device names for the group key above
qdbus org.kde.KWin /KWin reconfigure
```

### Keyboard Shortcuts

Shortcuts are managed per-component in `~/.config/kglobalshortcutsrc`:

```bash
# List all configured global shortcuts
kreadconfig6 --file kglobalshortcutsrc --group kwin

# Set a shortcut for toggle tiling (KWin action)
kwriteconfig6 --file kglobalshortcutsrc --group kwin \
    --key "Toggle Tiling" "Meta+T,none,Toggle Tiling"

qdbus org.kde.keyboard /modules/kwin reconfigure
```

---

## 66.10 KWin Scripts

KWin scripts use the KWin JavaScript API to automate window management, react
to events, and apply policies that the GUI cannot express. They run inside a
QJSEngine within the KWin compositor process.

### Script Installation

```bash
# Package structure
mkdir -p myscript/contents/code
cat > myscript/contents/code/main.js << 'JSEOF'
// script body here
JSEOF
cat > myscript/metadata.json << 'EOF'
{
  "KPlugin": {
    "Id": "myscript",
    "Name": "My KWin Script",
    "Version": "1.0"
  }
}
EOF
# Create package
cd .. && zip -r myscript.kwinscript myscript/

# Install and enable
kpackagetool6 --type KWin/Script --install myscript.kwinscript
# Enable in System Settings → Window Management → KWin Scripts
```

### Example: Pin Firefox to Virtual Desktop 1

```javascript
// Pin any Firefox window to virtual desktop 1 when it appears
workspace.windowAdded.connect(function(window) {
    if (window.resourceClass.toString().toLowerCase() === "firefox") {
        window.desktops = [workspace.desktops[0]];
    }
});
```

### Example: Force Floating for Picture-in-Picture

```javascript
// Force small browser PiP windows to always float above other windows
workspace.windowAdded.connect(function(window) {
    if (window.caption.indexOf("Picture-in-Picture") !== -1) {
        window.keepAbove = true;
        window.onAllDesktops = true;
        window.noBorder = true;
    }
});
```

### Example: Auto-maximize on Large Monitor, Float on Small

```javascript
// Maximize windows on displays wider than 2560px, otherwise tile normally
workspace.windowAdded.connect(function(window) {
    var screen = workspace.clientArea(KWin.MaximizeArea, window);
    if (screen.width >= 2560 && !window.specialWindow) {
        window.maximized = true;
    }
});
```

### Window Rules (No Scripting Required)

For simpler per-app rules, use KWin Window Rules (no scripting needed):

```
System Settings → Window Management → Window Rules → Add New
→ Window class: firefox
→ Apply: Force — Keep Above: Yes
→ Apply: Force — Virtual Desktop: 1
```

Rules are stored in `~/.config/kwinrulesrc`:

```ini
# ~/.config/kwinrulesrc
[1]
Description=Firefox on Desktop 1
desktops=00000000-0000-0000-0000-000000000001
desktopsrule=2
wmclass=firefox
wmclassmatch=1
```

---

## 66.11 SDDM Login Screen Theming

SDDM is the recommended display manager for Plasma. Its Wayland mode (SDDM 0.21+)
runs the greeter itself under a minimal compositor.

```bash
# Check SDDM version
sddm --version

# Install SDDM theme (example: Sugar Candy)
sudo git clone https://github.com/Kangie/sddm-sugar-candy \
    /usr/share/sddm/themes/sugar-candy

# Configure in SDDM config
sudo tee /etc/sddm.conf.d/theme.conf << 'EOF'
[Theme]
Current=sugar-candy
EOF

# Or configure via System Settings → Startup and Shutdown → Login Screen
```

Customize the Sugar Candy theme:

```ini
# /usr/share/sddm/themes/sugar-candy/theme.conf.user
[General]
background=Backgrounds/Mountain.jpg
ScreenWidth=2560
ScreenHeight=1440
FullBlur=true
PartialBlur=false
BlurRadius=100
HaveFormBackground=true
FormPosition=center
BackgroundImageHAlignment=center
BackgroundImageVAlignment=center
MainColor=#ffffff
AccentColor=61,174,233
```

---

## 66.12 KDE vs. Custom Compositor Rices

| Aspect | KDE Plasma 6 | Hyprland+Quickshell | Sway+Waybar |
|--------|-------------|---------------------|-------------|
| Setup time | 30 minutes | Days | 3–8 hours |
| HDR | Production-ready | Experimental | No |
| NVIDIA | Best | Good (explicit sync) | Fair |
| Customizability ceiling | High but bounded | Unlimited | Very high |
| Community rice culture | Moderate | Huge (r/unixporn) | Large |
| Config reproducibility | Good (Nix module) | Excellent (Nix/HM) | Excellent |
| Animations | Good (KWin effects) | Exceptional | Minimal |
| Resource usage | ~600 MB RAM | ~200 MB RAM | ~120 MB RAM |
| Tiling integration | Native (6.1+) | Core feature | Core feature |
| Touch/tablet support | Excellent | Partial | Minimal |
| Accessibility | Full (KDE A11y) | Minimal | Minimal |
| Per-app scaling | Yes (XDG protocol) | Yes | Yes |
| Activities | Yes (unique) | No | No |

KDE is the right choice when you want a full DE with minimal configuration
overhead, need HDR or color management, use an NVIDIA GPU, or require tablet/
touch input. Custom compositors win on memory footprint, ricing depth, and
community aesthetics culture.

*See Ch 60 for Hyprland. See Ch 55 for Sway.*

---

## 66.13 Troubleshooting

### Session starts in X11 instead of Wayland

Check the SDDM session chooser. The session files are in `/usr/share/wayland-sessions/`:

```bash
ls /usr/share/wayland-sessions/
# Should show: plasma.desktop

cat /usr/share/wayland-sessions/plasma.desktop
# Exec= should show startplasma-wayland
```

If the file is missing, reinstall `plasma-workspace`:

```bash
sudo pacman -S plasma-workspace   # Arch
sudo apt install --reinstall plasma-workspace  # Debian/Ubuntu
```

### KWin crashes on startup

```bash
# Check journalctl for crash details
journalctl --user -u plasma-kwin_wayland -b 0 --no-pager | tail -50

# Run KWin manually to see error output
kwin_wayland --no-lockscreen 2>&1 | head -100
```

Common causes: broken KWin scripts, incompatible OpenGL driver, missing
`libdrm` version. Disable all KWin scripts:

```bash
kwriteconfig6 --file kwinrc --group Plugins --key krohnkiteEnabled false
qdbus org.kde.KWin /KWin reconfigure
```

### Black screen after login

Usually a GPU driver or EGL issue:

```bash
# Try software rendering fallback
LIBGL_ALWAYS_SOFTWARE=1 startplasma-wayland

# Check EGL/OpenGL
glxinfo | grep "OpenGL renderer"
eglinfo | grep "EGL vendor"
```

For NVIDIA: ensure `nvidia-drm.modeset=1` is set in your kernel parameters:

```bash
# /etc/default/grub — add to GRUB_CMDLINE_LINUX_DEFAULT
nvidia-drm.modeset=1 nvidia-drm.fbdev=1

sudo update-grub && sudo reboot
```

### Fractional scaling looks blurry (XWayland apps)

XWayland apps render at integer scale and are upscaled. This is expected behavior.
For a sharper result, switch to integer scaling (200% instead of 150%) or run
the affected app natively on Wayland if a native binary exists:

```bash
# Force a GTK4 app to use Wayland directly (avoids XWayland)
GDK_BACKEND=wayland myapp

# Force an Electron app to use Wayland
myapp --ozone-platform=wayland --enable-features=WaylandWindowDecorations
```

### Plasma Shell (plasmashell) crashes or freezes

```bash
# Kill and restart without logout
kquitapp6 plasmashell
kstart plasmashell

# If plasmashell won't start, check for corrupt config
mv ~/.config/plasma-org.kde.plasma.desktop-appletsrc \
   ~/.config/plasma-org.kde.plasma.desktop-appletsrc.bak
kstart plasmashell
```

### Screen tearing with NVIDIA

Enable explicit sync and verify the kernel parameter:

```bash
# Check KWin is using explicit sync
journalctl --user -u plasma-kwin_wayland -b | grep -i "explicit\|sync"

# Verify nvidia-drm modeset
cat /sys/module/nvidia_drm/parameters/modeset   # should be Y
```

### KWin effects not working (blur, transparency)

```bash
# Check compositor status
qdbus org.kde.KWin /Compositor active   # should return true

# Check if effects are loaded
qdbus org.kde.KWin /Effects loadedEffects

# Force-enable blur
qdbus org.kde.KWin /Effects loadEffect blur
```

### High CPU usage from plasmashell

Identify which widget or dataengine is consuming CPU:

```bash
# Profile plasmashell
perf top -p $(pgrep plasmashell)

# Disable all widgets temporarily by moving config
mv ~/.config/plasma-org.kde.plasma.desktop-appletsrc /tmp/
kquitapp6 plasmashell && kstart plasmashell
```

Widgets polling frequently (weather, system monitor with high refresh rates)
are common culprits. Reduce poll intervals in widget settings.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
