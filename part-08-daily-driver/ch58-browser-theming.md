# Chapter 58 — Browser Theming and Wayland Integration: Firefox, Chromium

## Overview
The browser is the most-used app for most people. Getting it Wayland-native,
removing chrome (UI), and theming it to match the rice is a big quality-of-life win.

## Sections

### 58.1 Firefox Native Wayland

**Enable Wayland backend:**
```bash
# Environment variable (set in compositor env config)
export MOZ_ENABLE_WAYLAND=1

# Or via /etc/environment
MOZ_ENABLE_WAYLAND=1
```

Verify: Firefox titlebar should respect compositor's window decorations.
With Hyprland `windowrulev2 = nofloat, class:firefox` — Firefox respects tiling.

**Firefox flags for Wayland (about:config):**
- `gfx.webrender.all = true` — WebRender accelerated rendering
- `media.hardware-video-decoding.force-enabled = true` — VA-API video decode
- `media.ffmpeg.vaapi.enabled = true` — FFMPEG VA-API
- `widget.use-xdg-desktop-portal.file-picker = 1` — use portal file chooser
- `widget.use-xdg-desktop-portal.mime-handler = 1`

**VA-API hardware video decoding:**
```bash
# AMD: 
sudo pacman -S libva-mesa-driver mesa-vdpau

# Intel:
sudo pacman -S intel-media-driver

# NVIDIA:
sudo pacman -S libva-nvidia-driver

# Verify
vainfo  # should list supported codecs
```

### 58.2 Firefox userChrome.css — Removing UI Chrome

`userChrome.css` lets you completely redesign Firefox's UI with CSS.

**Enable it first** (about:config):
```
toolkit.legacyUserProfileCustomizations.stylesheets = true
```

**Location:** `~/.mozilla/firefox/PROFILE.default/chrome/userChrome.css`

**Hide the tab bar (when using vertical tabs):**
```css
/* Hide horizontal tab bar */
#TabsToolbar { visibility: collapse !important; }
/* Hide title bar */
#titlebar { display: none !important; }
```

**Compact mode (reclaim vertical space):**
```css
:root {
    --tab-min-height: 24px !important;
    --toolbar-field-focus-border-color: transparent !important;
}
```

**Popular Firefox CSS rices:**
- **ShyFox**: minimal, hides all UI by default
- **SimpleFox**: clean minimal UI
- **cascade**: vertical-first UI
- **Betterfox** (user.js): performance + privacy, no CSS
- **Firefox-One**: macOS Big Sur inspired
- **Catppuccin Firefox**: color scheme port

**Installation pattern:**
```bash
git clone https://github.com/nicothin/nicothin-firefox-mods \
    ~/.mozilla/firefox/PROFILE/chrome/
```

### 58.3 Firefox Color Schemes

**Firefox Color extension:**
- Install: https://addons.mozilla.org/en-US/firefox/addon/firefox-color/
- Creates a complete Firefox theme from a color palette
- Pywal integration: `pywalfox` syncs pywal colors to Firefox automatically

**Pywalfox:**
```bash
pip install pywalfox
pywalfox install  # patches Firefox for native dark/light theme
# After wal runs: pywalfox update
```

**Catppuccin theme:**
- Install from Firefox Add-ons: search "Catppuccin Mocha"
- Or apply via Firefox Color

### 58.4 Chromium / Chrome Native Wayland

```bash
# Launch flags
chromium --ozone-platform=wayland --enable-features=UseOzonePlatform
# or via Electron apps that use Chromium:
code --ozone-platform=wayland --enable-features=UseOzonePlatform
```

**Persistent flags file** (`~/.config/chromium-flags.conf` or `/etc/chromium/chromium.conf`):
```
--ozone-platform=wayland
--enable-features=UseOzonePlatform,VaapiVideoDecodeLinuxGL
--use-gl=desktop
```

**Chromium themes:**
- Install from Chrome Web Store: search "Catppuccin", "Tokyo Night"
- Or create via chrome://theme/ (limited customization)

### 58.5 Electron App Wayland Flags

Most Electron apps (VS Code, Slack, Discord, Obsidian, etc.) need explicit flags:

```bash
# Per-app: create/edit the flags file
# VS Code:
echo "--ozone-platform=wayland" >> ~/.config/code-flags.conf

# Slack:
echo "--ozone-platform=wayland" >> ~/.config/slack-flags.conf

# Via NIXOS:
programs.vscode.commandLineArgs = ["--ozone-platform=wayland"];
```

**Global Electron Wayland** (affects all Electron apps):
```bash
# /etc/electron-flags.conf or ~/.config/electron-flags.conf
--ozone-platform=wayland
--enable-features=UseOzonePlatform,WaylandWindowDecorations
```

### 58.6 Browser in the Rice: Practical Tips

**Remove title bar for tiling:**
```conf
# Hyprland window rule
windowrulev2 = nomaxsize, class:^(firefox)$
```

**Firefox ESR vs. Firefox vs. Firefox Developer Edition:**
- Developer Edition: most up-to-date Wayland features
- Regular: stable, recommended
- ESR: older, avoid for Wayland cutting-edge features

**Multi-account containers (Firefox):**
- Color-coded containers visible in tab bar
- Themed to match or complement the rice color palette

**Start page / new tab theming:**
- `nightTab` extension: fully customizable new tab
- `tabliss`: widget-based new tab
- Custom `user.js` to set a local HTML file as new tab
