# Chapter 67 — GNOME Shell on Wayland

## Overview

GNOME Shell is the #1 Wayland desktop by installed base. It has been Wayland-default
since GNOME 3.22 (2016) and is the most production-tested Wayland compositor.
Ricing GNOME means extensions, CSS overrides, and theming tools.

GNOME's ricing model differs fundamentally from compositors like Hyprland or Sway: rather
than editing plaintext config files, you layer extensions written in JavaScript, inject CSS
into the Shell's internal stylesheet, and use `gsettings`/`dconf` to tune nearly every
behavioral parameter. The shell is a live JavaScript runtime — extensions are hot-loaded
without a restart. This makes iteration fast, but the boundary between "working" and
"segfault-black-screen" is thinner than in static-config compositors.

Since GNOME 45, the extension API underwent a major overhaul (ESModules). Extensions
written for GNOME 44 and earlier require a ported version. The Extension Manager app
(see §67.3) marks compatibility clearly. Always match extension versions to your
installed GNOME Shell version (`gnome-shell --version`).

This chapter covers the complete GNOME ricing stack: compositor internals, extension
ecosystem, Shell CSS theming, libadwaita color schemes, Wayland-specific features, and
minimal install patterns. For session startup and environment variables, see Ch 53. For
portal configuration shared across compositors, see Ch 71.

---

## 67.1 GNOME's Wayland Architecture

GNOME Shell runs as a Mutter plugin — meaning the UI process (panel, Activities overview,
dash, notifications) and the compositor (KMS/DRM, rendering pipeline, input handling)
execute in the same OS process. This tight coupling enables smooth animations and direct
access to compositor state from JavaScript, but also means a crashing extension can take
down the entire desktop.

The rendering stack is:
- **Mutter**: compositor, handles DRM/KMS, libinput, wl_compositor, xdg-shell, xwayland
- **Clutter**: retained-mode scene graph, now part of Mutter; actors are the rendering primitives
- **Cogl**: OpenGL/Vulkan abstraction beneath Clutter
- **GNOME Shell**: JavaScript runtime (SpiderMonkey via GJS) running as a Mutter plugin

GNOME does not use wlroots. The entire stack is custom-built and maintained by the GNOME
Foundation. This means Wayland protocol support is selective — GNOME implements what it
needs for its own UX model, sometimes lagging behind wlroots-based compositors for
niche protocols.

**Key Wayland protocols GNOME implements:**

| Protocol | Status | Notes |
|---|---|---|
| xdg-shell | Full | Window management baseline |
| layer-shell (wlr-layer-shell) | Partial (GNOME 46+) | Required for waybar, eww on GNOME |
| xdg-output | Full | Multi-monitor layout |
| wp-fractional-scale | Full | Since GNOME 45 |
| xdg-decoration | Client-side only | GNOME uses CSD exclusively |
| idle-inhibit | Full | Caffeine extension uses this |
| xwayland | Full | XWayland managed by Mutter |
| remote-desktop | Full (RDP) | Built-in RDP server |
| screencopy (wlr-screencopy) | Not implemented | Use pipewire/portal instead |

**Process tree (typical session):**

```
systemd (user)
 └─ gnome-session
     ├─ gnome-shell            # Mutter + Shell plugin (compositor + UI)
     ├─ gnome-settings-daemon  # Hardware, power, color mgmt daemons
     ├─ gnome-keyring-daemon
     ├─ xdg-desktop-portal
     ├─ xdg-desktop-portal-gnome
     └─ pipewire / wireplumber
```

To inspect what protocols are advertised to clients:

```bash
# List all Wayland globals (requires wayland-utils)
wayland-info | grep -E 'interface|version'

# Or via weston-info (part of weston package)
weston-info
```

XWayland is launched on-demand by Mutter when the first X11 application connects. You
can force eager startup (reduces first-launch latency for X11 apps) with:

```bash
gsettings set org.gnome.mutter experimental-features "['kms-modifiers', 'xwayland-native-scaling']"
```

---

## 67.2 Installation

### Arch Linux (full GNOME)

```bash
sudo pacman -S gnome gnome-extra gnome-tweaks gdm
sudo systemctl enable gdm.service
```

`gnome` is the base group (shell, mutter, nautilus, settings, control-center, GDM).
`gnome-extra` adds applications (gedit, gnome-calendar, etc.) — install selectively if
disk space or minimalism matters. `gnome-tweaks` is not in either group but is essential
for ricing.

### Arch Linux (minimal — shell only)

```bash
sudo pacman -S gnome-shell mutter gnome-settings-daemon \
    gnome-control-center gnome-session gnome-keyring \
    gdm nautilus gnome-tweaks
# Optional but recommended for ricing:
sudo pacman -S gnome-text-editor gnome-terminal xdg-desktop-portal-gnome
```

### Fedora (GNOME Workstation default)

```bash
# Already installed on Fedora Workstation
# Reinstall if broken:
sudo dnf group install "GNOME Desktop Environment"
sudo systemctl enable gdm
```

### Ubuntu / Debian

```bash
sudo apt install gnome-shell gnome-session gnome-tweaks gdm3
sudo systemctl enable gdm3
```

Note: Ubuntu ships a patched GNOME with its own default extensions (Ubuntu Dock). To
get vanilla GNOME behavior, install `gnome-session-flashback` or switch to the
"GNOME" session (not "Ubuntu") at the GDM login screen.

### NixOS

```nix
# /etc/nixos/configuration.nix
services.xserver = {
  enable = true;
  desktopManager.gnome.enable = true;
  displayManager.gdm = {
    enable = true;
    wayland = true;   # default since NixOS 23.05
  };
};

environment.systemPackages = with pkgs; [
  gnome.gnome-tweaks
  gnome-extension-manager
  gradience
];

# Exclude unwanted GNOME apps:
environment.gnome.excludePackages = with pkgs; [
  gnome-tour
  gnome.gnome-music
  gnome.epiphany
];
```

### Verify Wayland session is active

```bash
echo $XDG_SESSION_TYPE   # should print: wayland
echo $WAYLAND_DISPLAY    # should print: wayland-0 or wayland-1
loginctl show-session $XDG_SESSION_ID -p Type
```

---

## 67.3 GNOME Ricing: The Extension Ecosystem

GNOME extensions are JavaScript (GJS + SpiderMonkey) and CSS bundles that run inside the
Shell process. They have full access to the Clutter scene graph, GSettings, and all Shell
internals. A well-written extension is indistinguishable from built-in Shell behavior; a
poorly-written one leaks memory or crashes the session.

Extensions are identified by a UUID string (e.g., `user-theme@gnome-shell-extensions.gcampax.github.com`).
They live in either the system path (`/usr/share/gnome-shell/extensions/`) or the user
path (`~/.local/share/gnome-shell/extensions/`). User-installed extensions take
precedence over system ones.

**Installing extensions — three methods:**

1. **Browser**: https://extensions.gnome.org with the GNOME Shell Integration browser
   extension (Chrome/Firefox). Requires the native connector:

```bash
# Arch
sudo pacman -S gnome-browser-connector

# Fedora
sudo dnf install gnome-browser-connector

# Ubuntu/Debian
sudo apt install chrome-gnome-shell
```

2. **Extension Manager** (recommended GUI tool):

```bash
flatpak install flathub com.mattjakeman.ExtensionManager
# Or on Arch:
yay -S extension-manager
```

3. **CLI** with `gnome-extensions` (built into GNOME Shell):

```bash
# List all installed extensions and their state
gnome-extensions list --enabled
gnome-extensions list --disabled

# Enable / disable
gnome-extensions enable blur-my-shell@aunetx
gnome-extensions disable blur-my-shell@aunetx

# Install from a downloaded zip
gnome-extensions install user-theme@gnome-shell-extensions.gcampax.github.com.zip

# Show info
gnome-extensions info user-theme@gnome-shell-extensions.gcampax.github.com
```

**Manage via dconf directly** (useful for scripting/automation):

```bash
# Get current enabled extensions list
gsettings get org.gnome.shell enabled-extensions

# Enable a specific extension (append to list)
CURRENT=$(gsettings get org.gnome.shell enabled-extensions | tr -d "[]'" | tr ',' '\n')
gsettings set org.gnome.shell enabled-extensions \
  "['$(echo "$CURRENT" $'\n' "blur-my-shell@aunetx" | sort -u | paste -sd,)']"
```

**Essential ricing extensions (2025, GNOME 47+):**

| Extension | UUID | Purpose |
|---|---|---|
| User Themes | `user-theme@gnome-shell-extensions.gcampax.github.com` | Load custom Shell themes from `~/.themes/` |
| Dash to Dock | `dash-to-dock@micxgx.gmail.com` | macOS-style floating dock |
| Dash to Panel | `dash-to-panel@jderose9.github.com` | Windows-style taskbar |
| Blur my Shell | `blur-my-shell@aunetx` | Blur panels, overview, lock screen |
| Just Perfection | `just-perfection-desktop@just-perfection` | Hide/adjust 60+ Shell elements |
| Rounded Window Corners | `rounded-window-corners@fxgn` | Round window corners via shader |
| Pop Shell | `pop-shell@system76.com` | Tiling WM overlay (System76) |
| Forge | `forge@jmmaranan.com` | i3/BSP-style tiling for GNOME |
| Caffeine | `caffeine@patapon.info` | Inhibit idle / screensaver |
| AppIndicator | `appindicatorsupport@rgcjonas.gmail.com` | System tray (legacy) icons |
| Clipboard Indicator | `clipboard-indicator@tudmotu.com` | Clipboard history in panel |
| Vitals | `Vitals@CoreCoding.com` | CPU/RAM/temp/network in panel |
| GSConnect | `gsconnect@andyholmes.github.com` | KDE Connect protocol for GNOME |
| Space Bar | `space-bar@luchrioh` | Named workspaces in top bar |
| Tactile | `tactile@lundal.io` | Keyboard tiling zones overlay |
| Status Area Horizontal Spacing | `status-area-horizontal-spacing@mathematical.coffee.gmail.com` | Reduce panel icon spacing |

**Extension troubleshooting: read the logs**

```bash
# Live extension error stream (GNOME 45+)
journalctl -f -o cat /usr/bin/gnome-shell

# Or filter for JS errors:
journalctl -b -u gdm -g "JS ERROR|Extension" --no-pager | tail -50

# Restart Shell without logging out (X11 only — on Wayland, use a nested session):
busctl --user call org.gnome.Shell /org/gnome/Shell org.gnome.Shell Eval s 'Meta.restart("Restarting…", global.context)'
```

---

## 67.4 GNOME Shell Theming

GNOME Shell's UI is rendered entirely via a CSS stylesheet (`gnome-shell.css`). This
controls the top panel, Activities overview, window switcher, notification bubbles,
on-screen display widgets, and more. Custom Shell themes override this file.

**Theme directory structure:**

```
~/.local/share/themes/
└── MyTheme/
    ├── gnome-shell/
    │   ├── gnome-shell.css          # Main Shell stylesheet
    │   ├── gnome-shell-high-contrast.css
    │   └── assets/                  # SVGs, PNGs used by the CSS
    ├── gtk-3.0/
    │   └── gtk.css                  # GTK3 application theming
    └── gtk-4.0/
        └── gtk.css                  # GTK4 application theming (limited effect with libadwaita)
```

**Install the User Themes extension and apply a theme:**

```bash
# Enable User Themes (must be done first)
gnome-extensions enable user-theme@gnome-shell-extensions.gcampax.github.com

# Apply via gsettings
gsettings set org.gnome.shell.extensions.user-theme name "Catppuccin-Mocha-Standard-Blue-Dark"

# Verify
gsettings get org.gnome.shell.extensions.user-theme name
```

**Popular GNOME Shell themes (2025):**

| Theme | Style | URL |
|---|---|---|
| Catppuccin GNOME Shell | Pastel, multiple flavors | github.com/catppuccin/gnome-shell |
| Marble Shell | Translucent, minimal | github.com/imarkoff/Marble-shell-theme |
| WhiteSur Shell | macOS Big Sur | github.com/vinceliuice/WhiteSur-gtk-theme |
| Orchis Shell | Material Design | github.com/vinceliuice/Orchis-theme |
| Tokyo Night | Dark, blue-tinted | github.com/Fausto-Korpsvart/Tokyo-Night-GTK-Theme |
| Gruvbox GTK | Warm retro | github.com/Fausto-Korpsvart/Gruvbox-GTK-Theme |

**Install Catppuccin GNOME Shell example:**

```bash
# Clone theme repo
git clone https://github.com/catppuccin/gnome-shell.git
cd gnome-shell

# Install for current user
mkdir -p ~/.local/share/themes/Catppuccin-Mocha/gnome-shell
cp -r src/* ~/.local/share/themes/Catppuccin-Mocha/gnome-shell/

# Apply
gsettings set org.gnome.shell.extensions.user-theme name "Catppuccin-Mocha"
```

**Inject custom CSS without a full theme** (quick overrides):

```bash
# ~/.config/gtk-4.0/gtk.css — affects GTK4/libadwaita apps
cat >> ~/.config/gtk-4.0/gtk.css << 'EOF'
/* Round window corners slightly more */
window.csd {
  border-radius: 14px;
}
/* Tighten headerbar */
headerbar {
  min-height: 38px;
  padding: 0 6px;
}
EOF
```

### Gradience — libadwaita Color Theming

Gradience is the authoritative tool for recoloring libadwaita applications. It generates
a `~/.config/gtk-4.0/gtk.css` and a Shell theme that share the same palette. Presets
exist for all major color schemes.

```bash
flatpak install flathub com.github.GradienceTeam.Gradience

# CLI usage (Gradience 0.4+):
gradience-cli apply -p catppuccin-mocha    # apply a named preset
gradience-cli list-presets
gradience-cli download-preset catppuccin-mocha

# Import community preset from file:
gradience-cli import-preset /path/to/preset.json
```

Gradience writes to `~/.config/gtk-4.0/gtk.css` (GTK4/libadwaita) and
`~/.config/gtk-3.0/gtk.css` (GTK3 compat). It also integrates with the User Themes
extension to generate matching Shell CSS.

---

## 67.5 gnome-tweaks and dconf

`gnome-tweaks` exposes settings that GNOME intentionally removed from the main Settings
app but that power users require. It is the single most important ricing utility for
GNOME outside of extensions.

```bash
# Install
sudo pacman -S gnome-tweaks          # Arch
sudo dnf install gnome-tweaks        # Fedora
sudo apt install gnome-tweaks        # Debian/Ubuntu
```

**Settings only accessible via gnome-tweaks:**

| Category | Setting |
|---|---|
| Fonts | Hinting (slight/medium/full), antialiasing (subpixel/grayscale) |
| Fonts | Interface, Document, Monospace, Legacy Window Title fonts |
| Appearance | Legacy GTK3 application theme |
| Appearance | Cursor theme and size |
| Appearance | Icon theme |
| Windows | Titlebar button layout (left/right, which buttons) |
| Windows | Attach modal dialogs |
| Windows | Edge tiling |
| Keyboard | Compose key, Caps Lock behavior |
| Mouse & Touchpad | Middle-click paste, Locate pointer |
| Startup Applications | Autostart entries |

**Scripting gnome-tweaks settings via dconf/gsettings:**

```bash
# Font rendering
gsettings set org.gnome.desktop.interface font-antialiasing 'rgba'
gsettings set org.gnome.desktop.interface font-hinting 'slight'

# Set fonts
gsettings set org.gnome.desktop.interface font-name 'Inter 11'
gsettings set org.gnome.desktop.interface monospace-font-name 'JetBrains Mono 10'
gsettings set org.gnome.desktop.interface document-font-name 'Inter 11'

# Icon theme
gsettings set org.gnome.desktop.interface icon-theme 'Papirus-Dark'

# Cursor theme and size
gsettings set org.gnome.desktop.interface cursor-theme 'Bibata-Modern-Ice'
gsettings set org.gnome.desktop.interface cursor-size 24

# Window button layout (left = macOS style, right = GNOME default)
gsettings set org.gnome.desktop.wm.preferences button-layout 'close,minimize,maximize:'
# Right side:
gsettings set org.gnome.desktop.wm.preferences button-layout ':minimize,maximize,close'

# GTK3 theme (legacy apps)
gsettings set org.gnome.desktop.interface gtk-theme 'Adwaita-dark'
# For GTK4/libadwaita dark mode:
gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'
```

**Dump and restore full dconf profile** (great for backups and new installs):

```bash
# Dump entire GNOME dconf tree
dconf dump /org/gnome/ > ~/gnome-settings-backup.ini

# Restore
dconf load /org/gnome/ < ~/gnome-settings-backup.ini

# Dump only Shell extensions settings
dconf dump /org/gnome/shell/extensions/ > ~/extensions-backup.ini
```

---

## 67.6 GNOME's Unique UX Features for Ricing

### Activities Overview Customization

The Activities overview is GNOME's central UX hub. Extensions like "Just Perfection" can
suppress the overview on startup, hide the hot corner, and change the overview layout.

```bash
# Disable hot corner (top-left screen edge trigger)
gsettings set org.gnome.desktop.interface enable-hot-corners false

# Never show the overview on startup
# Via Just Perfection extension:
gsettings set org.gnome.shell.extensions.just-perfection startup-status 0

# App grid columns (GNOME 42+)
gsettings set org.gnome.shell app-picker-columns 5
```

### Workspace Configuration

```bash
# Use fixed number of workspaces instead of dynamic
gsettings set org.gnome.mutter dynamic-workspaces false
gsettings set org.gnome.desktop.wm.preferences num-workspaces 6

# Workspaces span all monitors (false = each monitor has independent workspaces)
gsettings set org.gnome.mutter workspaces-only-on-primary false

# Workspace switching animation speed (ms)
gsettings set org.gnome.shell.overrides dynamic-workspaces false
```

### Custom Keyboard Shortcuts

```bash
# List all custom shortcuts
gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings

# Add a custom shortcut (terminal)
gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings \
  "['/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/']"

gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:\
/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/ \
  name 'Launch Terminal'
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:\
/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/ \
  command 'kgx'
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:\
/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/ \
  binding '<Super>Return'

# Window management keys
gsettings set org.gnome.desktop.wm.keybindings close "['<Super>q', '<Alt>F4']"
gsettings set org.gnome.desktop.wm.keybindings toggle-fullscreen "['<Super>f']"
gsettings set org.gnome.desktop.wm.keybindings toggle-maximized "['<Super>m']"
```

### Panel and Dash Tuning

The top panel and dash can be configured via extensions rather than CSS for layout changes.
For fine-grained CSS tweaks to the panel without a full Shell theme:

```bash
# ~/.local/share/gnome-shell/extensions/my-panel-tweak@local/
# Minimal extension to inject CSS without a full theme:
cat > ~/.local/share/gnome-shell/extensions/my-panel-tweak@local/stylesheet.css << 'EOF'
#panel {
  background-color: rgba(0, 0, 0, 0.7);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
#panel .panel-button:hover {
  background-color: rgba(255, 255, 255, 0.1);
}
EOF
```

---

## 67.7 GNOME Terminal and App Theming

### GNOME Console (kgx) and GNOME Terminal

GNOME Console (`kgx`) is the modern terminal in GNOME 42+ and respects the system
color scheme automatically. GNOME Terminal is configurable via dconf profiles.

```bash
# Export all GNOME Terminal profiles
dconf dump /org/gnome/terminal/legacy/profiles:/ > ~/terminal-profiles.ini

# Import
dconf load /org/gnome/terminal/legacy/profiles:/ < ~/terminal-profiles.ini

# Install Catppuccin for GNOME Terminal (official install script)
curl -Lo /tmp/install.py \
  https://raw.githubusercontent.com/catppuccin/gnome-terminal/v0.3.0/install.py
python3 /tmp/install.py

# List profiles and get their UUIDs
gsettings get org.gnome.Terminal.ProfilesList list
```

### Nautilus (Files) Theming

Nautilus uses GTK4/libadwaita. Direct theming is through `gtk.css` and Gradience:

```bash
# ~/.config/gtk-4.0/gtk.css
cat >> ~/.config/gtk-4.0/gtk.css << 'EOF'
/* Compact Nautilus sidebar */
.nautilus-window .sidebar {
  font-size: 0.9em;
}
/* Slightly transparent file manager background */
.nautilus-canvas-item {
  border-radius: 6px;
}
EOF
```

### Papirus Icon Theme

```bash
# Arch
sudo pacman -S papirus-icon-theme

# Or install latest from GitHub:
wget -qO- https://git.io/papirus-icon-theme-install | sh

# Apply
gsettings set org.gnome.desktop.interface icon-theme 'Papirus-Dark'

# Papirus folder colors (papirus-folders utility)
papirus-folders -C catppuccin-mocha --theme Papirus-Dark
```

### Fonts

```bash
# Install recommended fonts via Arch
sudo pacman -S ttf-inter ttf-jetbrains-mono noto-fonts noto-fonts-emoji

# Or via Nerd Fonts (for terminal powerline/icon support)
yay -S ttf-jetbrains-mono-nerd

# Apply
gsettings set org.gnome.desktop.interface font-name 'Inter 11'
gsettings set org.gnome.desktop.interface monospace-font-name 'JetBrainsMono Nerd Font 10'
gsettings set org.gnome.desktop.wm.preferences titlebar-font 'Inter Bold 11'
```

---

## 67.8 GNOME Wayland-Specific Configuration

### Screen Recording

GNOME has a built-in screen recorder since GNOME 41:

```bash
# Keyboard shortcut (built-in):
# Super+Shift+Ctrl+R  — start/stop recording (saves to ~/Videos/)

# CLI with gnome-screenshot:
gnome-screenshot -a          # interactive area selection
gnome-screenshot -w          # window screenshot
gnome-screenshot -f out.png  # full screen to file

# Kooha — GUI screen recorder with Wayland portal support:
flatpak install flathub io.github.seadve.Kooha

# OBS Studio (Wayland PipeWire capture):
flatpak install flathub com.obsproject.Studio
# In OBS: Add Source → Screen Capture (PipeWire)
```

### Screen Sharing and PipeWire

Screen sharing in GNOME Wayland works through `xdg-desktop-portal-gnome` and PipeWire.
Applications request a screencast stream via the portal; GNOME shows a picker dialog.

```bash
# Verify portal is running
systemctl --user status xdg-desktop-portal xdg-desktop-portal-gnome

# Check PipeWire screencast streams (requires pipewire-media-session or wireplumber)
pw-dump | python3 -m json.tool | grep -A5 '"type": "PipeWire:Interface:Node"'

# Force-restart portals if screen sharing is broken:
systemctl --user restart xdg-desktop-portal xdg-desktop-portal-gnome
```

### Night Light (Color Temperature)

```bash
# Enable Night Light
gsettings set org.gnome.settings-daemon.plugins.color night-light-enabled true

# Set color temperature (1000–10000 K, lower = warmer)
gsettings set org.gnome.settings-daemon.plugins.color night-light-temperature 3500

# Schedule (sunset-to-sunrise or manual times)
gsettings set org.gnome.settings-daemon.plugins.color night-light-schedule-automatic true

# Manual schedule:
gsettings set org.gnome.settings-daemon.plugins.color night-light-schedule-automatic false
gsettings set org.gnome.settings-daemon.plugins.color night-light-schedule-from 20.0
gsettings set org.gnome.settings-daemon.plugins.color night-light-schedule-to 7.0
```

### Remote Desktop (Built-in RDP Server)

GNOME 42+ includes an RDP server via the Wayland remote-desktop protocol:

```bash
# Enable in Settings → System → Remote Desktop
# Or via gsettings:
gsettings set org.gnome.desktop.remote-desktop.rdp enable true
gsettings set org.gnome.desktop.remote-desktop.rdp screen-share-mode extend

# Generate TLS credentials for RDP (required):
cd ~/.local/share/gnome-remote-desktop/
openssl req -new -newkey rsa:4096 -days 720 -nodes -x509 \
    -subj "/CN=gnome-remote-desktop" \
    -keyout rdp-tls.key -out rdp-tls.crt

# Connect with any RDP client (e.g., Remmina, FreeRDP):
xfreerdp /v:localhost /u:$USER /p:yourpassword /dynamic-resolution
```

### Fractional Scaling

GNOME supports fractional scaling natively via the `wp-fractional-scale` protocol:

```bash
# Enable fractional scaling (GNOME 45+ enables by default if detected)
gsettings set org.gnome.mutter experimental-features "['scale-monitor-framebuffer']"

# Set per-monitor scale from CLI (requires gnome-randr or mutter DBus)
# Via Settings → Displays, set scale to 125%, 150%, 175%, etc.

# Check current scales:
gsettings get org.gnome.desktop.interface text-scaling-factor

# For HiDPI: set text scaling factor independently of display scale
gsettings set org.gnome.desktop.interface text-scaling-factor 1.2
```

### Multi-Monitor Configuration

```bash
# Save and restore monitor layout (useful for docking station setups)
# GNOME saves monitor config to ~/.config/monitors.xml automatically

# View current monitor configuration:
cat ~/.config/monitors.xml

# Apply monitor changes via randr-like tool (gnome-randr):
pip install gnome-randr   # or: yay -S gnome-randr

gnome-randr                          # list monitors
gnome-randr modify HDMI-1 --scale 1  # set scale
gnome-randr modify DP-1 --rotate left
```

---

## 67.9 GNOME in a Minimal Setup

Running GNOME Shell without the full application suite yields a lightweight but fully
functional Wayland compositor. This is useful on servers with occasional GUI needs, or
when you want GNOME's stability and extension ecosystem without the disk footprint.

```bash
# Arch: minimal GNOME Shell
sudo pacman -S \
    gnome-shell \
    mutter \
    gnome-settings-daemon \
    gnome-control-center \
    gnome-session \
    gnome-keyring \
    gdm \
    xdg-desktop-portal \
    xdg-desktop-portal-gnome \
    pipewire \
    wireplumber \
    nautilus        # file manager — omit for headless-style setup

# Fonts and icons (minimal)
sudo pacman -S noto-fonts ttf-dejavu papirus-icon-theme
```

**Recommended extensions for a tiling-focused minimal GNOME:**

```bash
# Install via Extension Manager or gnome-extensions:
# 1. Pop Shell (tiling)
yay -S gnome-shell-extension-pop-shell

# 2. Just Perfection (hide overview dock, clock centered, etc.)
# Install from extensions.gnome.org UUID: just-perfection-desktop@just-perfection

# 3. AppIndicator (for apps that use tray icons)
# UUID: appindicatorsupport@rgcjonas.gmail.com

# Enable all three
gnome-extensions enable pop-shell@system76.com
gnome-extensions enable just-perfection-desktop@just-perfection
gnome-extensions enable appindicatorsupport@rgcjonas.gmail.com
```

**Pop Shell tiling configuration:**

```bash
# Pop Shell keyboard shortcuts (set via gsettings after enabling extension)
# These are the defaults — override as needed:
gsettings set org.gnome.shell.extensions.pop-shell tile-by-default true
gsettings set org.gnome.shell.extensions.pop-shell show-title false

# Toggle tiling mode on/off
# Default: Super+Y
```

**Autostart a custom bar or launcher on minimal GNOME:**

```bash
# ~/.config/autostart/waybar.desktop
cat > ~/.config/autostart/waybar.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=Waybar
Exec=waybar
X-GNOME-Autostart-enabled=true
EOF
```

Note: waybar requires `wlr-layer-shell` support. GNOME 46+ has partial support. Waybar
built with `--without-wlr` flag on GNOME works for most modules. See Ch 75 for waybar
configuration on GNOME.

---

## 67.10 GNOME vs. Custom Compositor

Choosing between GNOME Shell and a custom compositor (Hyprland, Sway, niri) is a
fundamental workflow decision. The table below covers the most relevant dimensions for
an experienced ricer.

| Aspect | GNOME Shell | Hyprland | Sway |
|---|---|---|---|
| Wayland maturity | Oldest, most tested (2016) | 2-3 years | 4+ years |
| Ricing language | JavaScript + CSS | Hyprlang + shell | i3-style config |
| Config file? | No — dconf/gsettings | Yes (~/.config/hypr/) | Yes (~/.config/sway/) |
| Tiling | Via extensions (Pop, Forge) | Native (dynamic) | Native (manual i3) |
| Animations | Built-in, extension-tweakable | Rich, shader-driven | Minimal |
| Accessibility | Best on Linux (AT-SPI2) | Partial | Minimal |
| Battery life | Good | Good | Very good |
| Ricing ceiling | Medium (libadwaita resists) | Unlimited | High |
| Per-app rules | Limited | Extensive | Moderate |
| Screenshare (Wayland) | Portal-native | Portal + hyprland-share-picker | Portal |
| Gaming / VRR | GNOME 46+ has VRR | Excellent | Basic |
| Setup time to daily-driver | ~1 hour | 1-3 days | 4-8 hours |
| Crash recovery | Restart shell in-session | Re-login required | Re-login required |
| Multi-monitor fractional scale | Native | Native | Basic |

GNOME excels at "set it and forget it" ricing: install 5 extensions, apply a Catppuccin
theme via Gradience, set fonts, and you have a polished desktop in under an hour.
Hyprland's ceiling is higher, but reaching it requires substantially more configuration
investment.

For users who want GNOME's stability with more keyboard-driven control: combine Pop Shell
or Forge (tiling extensions) with Space Bar (named workspaces) and Just Perfection
(minimal UI) to get within 80% of a Hyprland workflow while retaining GNOME's app
ecosystem and accessibility support.

---

## 67.11 GNOME Extensions: Writing a Minimal Custom Extension

When existing extensions don't quite meet your needs, writing a minimal GNOME Shell
extension is approachable. The following skeleton adds a custom indicator to the top panel.

```bash
# Create extension directory
EXT_UUID="my-indicator@example.com"
mkdir -p ~/.local/share/gnome-shell/extensions/$EXT_UUID
```

```json
// ~/.local/share/gnome-shell/extensions/my-indicator@example.com/metadata.json
{
  "name": "My Indicator",
  "description": "A minimal panel indicator example",
  "uuid": "my-indicator@example.com",
  "shell-version": ["45", "46", "47"],
  "version": 1
}
```

```javascript
// ~/.local/share/gnome-shell/extensions/my-indicator@example.com/extension.js
// GNOME 45+ ESModule syntax:
import St from 'gi://St';
import GObject from 'gi://GObject';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';

const MyIndicator = GObject.registerClass(
class MyIndicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, 'My Indicator');
        this.add_child(new St.Label({
            text: ' Hello Wayland ',
            y_align: 1,  // CLUTTER_ACTOR_ALIGN_CENTER
        }));
    }
});

let indicator = null;

export default class MyExtension {
    enable() {
        indicator = new MyIndicator();
        Main.panel.addToStatusArea('my-indicator', indicator);
    }
    disable() {
        indicator?.destroy();
        indicator = null;
    }
}
```

```bash
# Enable the extension (reload Shell first on Wayland via a nested session or re-login)
gnome-extensions enable my-indicator@example.com

# On X11 you can restart Shell without logout:
busctl --user call org.gnome.Shell /org/gnome/Shell org.gnome.Shell Eval s \
  'Main.loadTheme(); imports.ui.main.overview._overview.controls._workspacesDisplay.reactive = true;'
```

---

## Troubleshooting

### Extension fails to load or crashes Shell

```bash
# Check for JS errors in the journal:
journalctl -b -o short-monotonic /usr/bin/gnome-shell | grep -i "error\|extension" | tail -30

# Disable all extensions and re-enable one-by-one to find the culprit:
gsettings set org.gnome.shell enabled-extensions "[]"

# Safe mode (GNOME 40+) — starts Shell with all extensions disabled:
# At GDM, click gear icon → "GNOME (Safe Mode)"
# Or set via kernel cmdline in GRUB: gnome.shell.overrides disable-extension-version-validation=true
```

### Blank screen / Shell crash recovery

```bash
# Switch to TTY (Ctrl+Alt+F2) and restart GDM:
sudo systemctl restart gdm

# Or just restart gnome-shell (Wayland — loses extension state):
DISPLAY=:0 WAYLAND_DISPLAY=wayland-0 gnome-shell --replace &
```

### Theming not applying (libadwaita ignores GTK theme)

GTK4/libadwaita applications ignore the legacy `gtk-theme` gsetting. Use Gradience or
write `~/.config/gtk-4.0/gtk.css` directly:

```bash
# Check if an app uses GTK4:
ldd $(which nautilus) | grep -i gtk

# Force dark color scheme for all libadwaita apps:
gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'

# Per-app override via environment (in ~/.config/autostart/ or launcher):
# GTK_THEME=Adwaita:dark nautilus
```

### Screen sharing / screencasting not working

```bash
# Ensure portals are running:
systemctl --user status xdg-desktop-portal xdg-desktop-portal-gnome pipewire wireplumber

# Check for portal conflicts (only one portal should handle screencast):
ls /usr/share/xdg-desktop-portal/portals/
# Should see gnome.portal — if wlr.portal is also present, conflicts may arise on GNOME

# Restart everything:
systemctl --user restart pipewire wireplumber xdg-desktop-portal xdg-desktop-portal-gnome
```

### GDM not starting / black screen at login

```bash
# Check GDM logs:
journalctl -b -u gdm --no-pager | tail -50

# Ensure correct GPU drivers are loaded:
lspci -k | grep -A2 VGA
modprobe -v i915   # Intel
modprobe -v amdgpu # AMD
# For NVIDIA: ensure nvidia-drm.modeset=1 is in kernel cmdline

# Add to /etc/default/grub GRUB_CMDLINE_LINUX:
# nvidia-drm.modeset=1
sudo grub-mkconfig -o /boot/grub/grub.cfg
```

### Wayland app opens in XWayland unintentionally

```bash
# Check if app is running under XWayland:
xlsclients    # lists X11 clients — if your app appears here, it's using XWayland

# For Electron apps, force Wayland:
# Add to ~/.config/<app>/electron-flags.conf or use a wrapper:
chromium --ozone-platform=wayland
code --ozone-platform=wayland

# For Qt apps:
QT_QPA_PLATFORM=wayland slack %U
```

---

*Cross-references: See Ch 53 for session environment and systemd user services. See Ch 71
for xdg-desktop-portal configuration. See Ch 75 for waybar on GNOME Wayland. See Ch 82
for NVIDIA + GNOME Wayland setup.*

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
