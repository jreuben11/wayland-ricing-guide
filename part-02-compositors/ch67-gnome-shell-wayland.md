# Chapter 67 — GNOME Shell on Wayland

## Overview
GNOME Shell is the #1 Wayland desktop by installed base. It has been Wayland-default
since GNOME 3.22 (2016) and is the most production-tested Wayland compositor.
Ricing GNOME means extensions, CSS overrides, and theming tools.

## Sections

### 67.1 GNOME's Wayland Architecture
- **Mutter**: the compositor (handles KMS/DRM, rendering, input)
- **GNOME Shell**: the UI process (panel, Activities, dash) — runs as a Mutter plugin
- **Mutter + GNOME Shell** = compositor + window manager in one process
- Uses **Clutter** (scene graph) for rendering
- No wlroots: fully custom compositor stack

### 67.2 Installation

**Arch:**
```bash
sudo pacman -S gnome gnome-extra gdm
sudo systemctl enable gdm
```

**NixOS:**
```nix
services.xserver.desktopManager.gnome.enable = true;
services.displayManager.gdm.enable = true;
```

### 67.3 GNOME Ricing: The Extension Ecosystem

GNOME extensions are JavaScript + CSS running inside GNOME Shell:

**Install extensions:**
1. Browser: https://extensions.gnome.org (with GNOME Shell Integration extension)
2. CLI: `gnome-extensions install uuid.v.shell-extension.zip`
3. GUI: **Extension Manager** app (recommended)

```bash
sudo pacman -S gnome-browser-connector
flatpak install flathub com.mattjakeman.ExtensionManager
```

**Essential ricing extensions (2025):**
| Extension | Purpose |
|-----------|---------|
| **User Themes** | Load custom Shell themes from `~/.themes/` |
| **Dash to Dock / Dash to Panel** | Customize the app dock/panel |
| **Blur my Shell** | Blur panels, overview, lock screen |
| **Just Perfection** | Hide/adjust dozens of Shell elements |
| **Rounded Window Corners** | Round window corners (built into some themes) |
| **Pop Shell** | Tiling window management (System76) |
| **Forge** | Advanced tiling for GNOME |
| **Caffeine** | Prevent screen lock |
| **AppIndicator** | System tray icons |
| **Clipboard Indicator** | Clipboard history in panel |
| **Vitals** | CPU/RAM/temp in panel |
| **GSConnect** | KDE Connect for GNOME (phone integration) |

### 67.4 GNOME Shell Theming

**Shell theme (gnome-shell CSS):**
Theme location: `~/.local/share/themes/ThemeName/gnome-shell/gnome-shell.css`
```bash
# Enable User Themes extension first, then:
gsettings set org.gnome.shell.extensions.user-theme name "ThemeName"
```

**Popular GNOME Shell themes:**
- **Catppuccin GNOME Shell**: https://github.com/catppuccin/gnome-shell
- **Marble Shell**: clean, translucent
- **WhiteSur Shell**: macOS Big Sur
- **Orchis Shell**: material-ish

**Gradience** (for libadwaita/GTK4 + Shell theming):
```bash
flatpak install flathub com.github.GradienceTeam.Gradience
# Presets: Catppuccin, Nord, Gruvbox, Tokyo Night, etc.
```

### 67.5 gnome-tweaks

Essential for GNOME ricing:
```bash
sudo pacman -S gnome-tweaks
```

Settings only accessible via tweaks:
- Font hinting and antialiasing
- Legacy GTK theme (GTK3)
- Window titlebars: maximize/minimize buttons
- Startup applications
- Extensions management (backup to Extension Manager)
- Mouse: middle-click paste, locate pointer

### 67.6 GNOME's Unique UX Features for Ricing

**Activities Overview:**
- `Super` key: shows all open windows
- Workspace switcher on right
- App grid for launchers

**Custom keyboard shortcuts:**
System Settings → Keyboard → Keyboard Shortcuts → Custom Shortcuts

**Workspace configuration:**
- System Settings → Multitasking → Workspaces
- Dynamic (auto-create) or fixed count
- Workspace switching: `Super+PgUp/PgDn`

### 67.7 GNOME Terminal and App Theming

GNOME Terminal profiles:
```bash
# Export profile
dconf dump /org/gnome/terminal/legacy/profiles:/ > terminal-profile.ini
# Catppuccin profile: install script at github.com/catppuccin/gnome-terminal
```

**Nautilus (files) CSS:**
`~/.config/gtk-4.0/gtk.css` — affects Nautilus since it uses GTK4/libadwaita.

### 67.8 GNOME Wayland-Specific Configuration

**Screen recording:**
Built-in: `Super+Shift+Ctrl+R` starts/stops
Or: `gnome-screenshot`, `kooha` app

**Screen sharing:**
Works automatically via `xdg-desktop-portal-gnome` (included with GNOME).

**Night light:**
System Settings → Display → Night Light (built-in, no extra tools needed)

**Remote desktop:**
System Settings → System → Remote Desktop (built-in RDP server via Wayland protocol)

### 67.9 GNOME in a Minimal Setup

Minimal GNOME without the full app suite:
```bash
sudo pacman -S gnome-shell mutter gnome-settings-daemon \
    gnome-control-center gnome-keyring gdm nautilus
```

Add extensions for tiling (Pop Shell, Forge) to get a keyboard-driven workflow.

### 67.10 GNOME vs. Custom Compositor

| Aspect | GNOME | Hyprland+Quickshell |
|--------|-------|---------------------|
| Polish | Exceptional | Exceptional (with effort) |
| Extension language | JavaScript | QML |
| Tiling | Via extensions | Native |
| Accessibility | Best on Linux | Partial |
| Battery life | Good (wayland-optimized) | Good |
| Ricing ceiling | Medium (libadwaita fights you) | Unlimited |
| Setup time | 1 hour | Days |
| Wayland maturity | Oldest, most tested | 2-3 years |
