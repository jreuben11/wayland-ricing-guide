# Chapter 58 — Browser Theming and Wayland Integration: Firefox, Chromium

## Contents

- [Overview](#overview)
- [58.1 Firefox Native Wayland](#581-firefox-native-wayland)
  - [Enabling the Backend](#enabling-the-backend)
  - [Verifying Wayland Window Integration](#verifying-wayland-window-integration)
  - [about:config Flags for Wayland Performance](#aboutconfig-flags-for-wayland-performance)
- [58.2 VA-API Hardware Video Decoding](#582-va-api-hardware-video-decoding)
  - [Installing VA-API Libraries](#installing-va-api-libraries)
  - [Verifying VA-API](#verifying-va-api)
  - [Verifying Decode in Firefox](#verifying-decode-in-firefox)
- [58.3 Firefox userChrome.css — Removing UI Chrome](#583-firefox-userchromecss-removing-ui-chrome)
  - [Enabling userChrome.css](#enabling-userchromecss)
  - [Finding Your Profile Directory](#finding-your-profile-directory)
  - [Core CSS Recipes](#core-css-recipes)
  - [Popular Firefox CSS Rices](#popular-firefox-css-rices)
- [58.4 Firefox Color Schemes and Palette Integration](#584-firefox-color-schemes-and-palette-integration)
  - [Firefox Color Extension](#firefox-color-extension)
  - [Pywalfox — Automatic wal/pywal Integration](#pywalfox-automatic-walpywal-integration)
  - [Catppuccin Theme](#catppuccin-theme)
  - [Custom New Tab Page](#custom-new-tab-page)
- [58.5 Chromium / Chrome Native Wayland](#585-chromium-chrome-native-wayland)
  - [Launch Flags](#launch-flags)
  - [Persistent Flags File](#persistent-flags-file)
  - [Chromium Theming](#chromium-theming)
- [58.6 Electron App Wayland Flags](#586-electron-app-wayland-flags)
  - [Per-Application Flags Files](#per-application-flags-files)
  - [Global Electron Flags](#global-electron-flags)
  - [NixOS Declarative Configuration](#nixos-declarative-configuration)
  - [Vesktop — Discord with Full Wayland Support](#vesktop-discord-with-full-wayland-support)
- [58.7 Browser in the Rice: Compositor Integration](#587-browser-in-the-rice-compositor-integration)
  - [Window Rules for Browsers](#window-rules-for-browsers)
  - [Firefox Release Channel Comparison](#firefox-release-channel-comparison)
  - [Multi-Account Containers Color Coding](#multi-account-containers-color-coding)
  - [Start Page / New Tab Theming Summary](#start-page-new-tab-theming-summary)
- [58.8 Troubleshooting](#588-troubleshooting)
  - [Firefox Falls Back to XWayland](#firefox-falls-back-to-xwayland)
  - [VA-API Not Working in Firefox](#va-api-not-working-in-firefox)
  - [Chromium Flags Not Being Read](#chromium-flags-not-being-read)
  - [Electron App is Blurry at Fractional Scale](#electron-app-is-blurry-at-fractional-scale)
  - [userChrome.css Changes Not Taking Effect](#userchromecss-changes-not-taking-effect)
  - [Firefox Crashes on Wayland with NVIDIA](#firefox-crashes-on-wayland-with-nvidia)
- [Cross-References](#cross-references)

---


## Overview

The browser is the most-used application for most desktop users. Getting it Wayland-native —
with proper hardware acceleration, no XWayland fallback, correct HiDPI handling, and a UI that
matches the rest of your rice — is one of the highest-impact customizations you can make. This
chapter covers Firefox and Chromium (plus Electron apps built on Chromium) end-to-end: enabling
the Wayland backend, eliminating unnecessary UI chrome with custom CSS, wiring color schemes to
your palette tool (pywal, Catppuccin, etc.), and ensuring each app starts cleanly under your
compositor.

The difference between a browser running under XWayland and one running natively on Wayland is
not subtle. Native Wayland means correct fractional scaling, input method protocol compliance
(IBus/Fcitx5), proper cursor scaling, VRR/variable-refresh cooperation, and no tearing artifacts
from the X11 → Wayland translation layer. Firefox has had a production-quality Wayland backend
since version 121 (late 2023). Chromium reached comparable maturity slightly later.

This chapter assumes you are running a Wayland compositor (Hyprland, Sway, Niri, or River). For
session startup details see **Ch 53 — Session Startup and Environment Variables**. For
portal/file-picker plumbing see **Ch 52 — xdg-desktop-portal: Screen Sharing, File Chooser, Settings**. For pywal/color pipeline
integration see **Ch 47 — Pywal and Automatic Color Theming**.

---

## 58.1 Firefox Native Wayland

### Enabling the Backend

Firefox chooses its windowing backend at startup. The canonical environment variable is
`MOZ_ENABLE_WAYLAND=1`. Without it, even on a Wayland session, Firefox will silently fall back
to XWayland (which requires `Xwayland` to be running). Set this in your compositor's environment
export, not just in `.bashrc`, so it applies to all launch paths including `.desktop` file
launches and application launchers.

```bash
# ~/.config/hypr/hyprland.conf — exec-once or env block
env = MOZ_ENABLE_WAYLAND,1
env = MOZ_DBUS_REMOTE,1          # required for remote-control (e.g. open-in-browser)

# Sway: ~/.config/sway/config
exec systemctl --user import-environment MOZ_ENABLE_WAYLAND
set $env_firefox MOZ_ENABLE_WAYLAND=1 MOZ_DBUS_REMOTE=1
```

For system-wide persistence across all session types, `/etc/environment` is the correct location:

```bash
# /etc/environment
MOZ_ENABLE_WAYLAND=1
MOZ_DBUS_REMOTE=1
```

To verify the backend is active, open Firefox and navigate to `about:support`. Under "Graphics"
look for "Window Protocol: wayland". If it shows "x11", the environment variable is not reaching
Firefox's launch context — double-check compositor env injection (see Ch 53).

### Verifying Wayland Window Integration

With the backend active, Firefox respects your compositor's window management protocol. Under
Hyprland, Firefox windows tile, float, and respect `windowrulev2` directives properly. Without
`MOZ_ENABLE_WAYLAND=1`, Firefox appears to the compositor as an XWayland foreign window and many
rules silently fail.

```bash
# Hyprland rules for Firefox — ~/.config/hypr/hyprland.conf
windowrulev2 = nomaxsize, class:^(firefox)$
windowrulev2 = nofloat, class:^(firefox)$, title:^(?!.*Picture-in-Picture).*$
```

See §58.7 for the complete Hyprland window-rule set including PiP pinning.

### about:config Flags for Wayland Performance

Open `about:config` (accept the warning) and set the following. These flags enable hardware
acceleration, portal integration, and Wayland-specific rendering paths.

| Flag | Value | Purpose |
|---|---|---|
| `gfx.webrender.all` | `true` | Force WebRender (GPU-accelerated renderer) |
| `gfx.webrender.compositor` | `true` | WebRender compositor mode |
| `media.hardware-video-decoding.force-enabled` | `true` | VA-API video decode |
| `media.ffmpeg.vaapi.enabled` | `true` | FFMPEG VA-API path |
| `media.av1.enabled` | `true` | AV1 codec (YouTube 4K) |
| `widget.use-xdg-desktop-portal.file-picker` | `1` | Portal file chooser |
| `widget.use-xdg-desktop-portal.mime-handler` | `1` | Portal MIME handler |
| `widget.use-xdg-desktop-portal.location` | `1` | Portal geolocation |
| `browser.tabs.drawInTitlebar` | `false` | Remove CSD title bar |
| `layers.acceleration.force-enabled` | `true` | Force GPU compositing |

Set these flags in bulk using a `user.js` file in your Firefox profile directory. This file is
read by Firefox on each startup and overrides `prefs.js` values — it is the correct way to
version-control your Firefox configuration.

```javascript
// ~/.mozilla/firefox/PROFILENAME.default-release/user.js
// Wayland + Hardware Acceleration
user_pref("gfx.webrender.all", true);
user_pref("gfx.webrender.compositor", true);
user_pref("gfx.webrender.compositor.force-enabled", true);
user_pref("media.hardware-video-decoding.force-enabled", true);
user_pref("media.ffmpeg.vaapi.enabled", true);
user_pref("media.av1.enabled", true);
user_pref("layers.acceleration.force-enabled", true);

// XDG Portal integration
user_pref("widget.use-xdg-desktop-portal.file-picker", 1);
user_pref("widget.use-xdg-desktop-portal.mime-handler", 1);
user_pref("widget.use-xdg-desktop-portal.location", 1);

// UI cleanup
user_pref("browser.tabs.drawInTitlebar", false);
user_pref("browser.compactmode.show", true);
user_pref("browser.uidensity", 1);  // 1 = compact, 0 = normal, 2 = touch

// Disable telemetry
user_pref("toolkit.telemetry.enabled", false);
user_pref("browser.newtabpage.activity-stream.feeds.telemetry", false);
```

---

## 58.2 VA-API Hardware Video Decoding

Hardware video decoding via VA-API dramatically reduces CPU usage when watching video. Without
it, a 4K YouTube video can consume 30–60% CPU on a modern machine; with it, the GPU handles
decode and CPU load drops to single digits. Firefox uses the `libva` interface; the specific
backend library depends on your GPU vendor.

### Installing VA-API Libraries

```bash
# AMD GPUs (open-source Mesa driver) — Arch Linux
sudo pacman -S libva-mesa-driver mesa-vdpau libva-utils

# Intel GPUs (Broadwell and newer, Gen 8+)
sudo pacman -S intel-media-driver libva-utils
# For older Intel (Haswell and earlier):
sudo pacman -S libva-intel-driver libva-utils

# NVIDIA (proprietary driver, requires 470+ for VA-API)
sudo pacman -S libva-nvidia-driver
# Enable in /etc/modprobe.d/nvidia.conf:
# options nvidia-drm modeset=1 fbdev=1

# Ubuntu/Debian equivalents:
sudo apt install libva-drm2 libva-x11-2 libva-wayland2 vainfo
sudo apt install intel-media-va-driver          # Intel
sudo apt install mesa-va-drivers                # AMD
```

### Verifying VA-API

```bash
vainfo
# Expected output (AMD example):
# vainfo: VA-API version: 1.20 (libva 2.20.0)
# vainfo: Driver version: Mesa Gallium driver 23.3.0 for ...
# vainfo: Supported profile and entrypoints
#   VAProfileH264ConstrainedBaseline: VAEntrypointVLD
#   VAProfileH264High:                VAEntrypointVLD
#   VAProfileVP9Profile0:             VAEntrypointVLD
#   VAProfileAV1Profile0:             VAEntrypointVLD

# Check which driver is being used
echo $LIBVA_DRIVER_NAME  # should be set if needed

# Force driver selection (add to /etc/environment if auto-detect fails):
# AMD:   LIBVA_DRIVER_NAME=radeonsi
# Intel: LIBVA_DRIVER_NAME=iHD (or i965 for older)
# NVIDIA: LIBVA_DRIVER_NAME=nvidia
```

If `vainfo` returns errors, hardware video decode will not work regardless of Firefox flags. Fix
the driver installation before debugging Firefox. The most common issue on AMD is a missing
`firmware-amdgpu` package or a kernel that is too old for the GPU.

### Verifying Decode in Firefox

After enabling `media.ffmpeg.vaapi.enabled` and `media.hardware-video-decoding.force-enabled`,
open `about:support` and look for "Video Decode" under the "Media" section. Play a YouTube video
and open the browser task manager (`about:performance`) — GPU process CPU usage should be low
and a dedicated "GPU Process" should be visible.

---

## 58.3 Firefox userChrome.css — Removing UI Chrome

`userChrome.css` is a CSS file Firefox loads after its own UI stylesheet. It has access to the
full Firefox XUL/HTML DOM and can hide, recolor, resize, or restructure any part of the browser
UI. This is the primary mechanism for making Firefox visually match your rice — eliminating the
default orange/purple branding, compressing the UI, and removing elements you do not use.

### Enabling userChrome.css

By default Firefox ignores userChrome.css for performance reasons. Enable loading via
`about:config`:

```
toolkit.legacyUserProfileCustomizations.stylesheets = true
```

Or add it to `user.js`:

```javascript
user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);
```

The file must be placed at:
```
~/.mozilla/firefox/PROFILENAME.default-release/chrome/userChrome.css
```

Create the `chrome/` directory if it does not exist. Firefox also loads `userContent.css` from
the same directory — this file targets web page content rather than the browser UI itself and is
useful for styling internal pages like `about:newtab`.

### Finding Your Profile Directory

```bash
# List all Firefox profiles
ls ~/.mozilla/firefox/

# Or use the profile manager
firefox --ProfileManager

# Programmatic lookup (useful for scripting)
PROFILE_DIR=$(find ~/.mozilla/firefox -name "*.default-release" -type d | head -1)
mkdir -p "$PROFILE_DIR/chrome"
echo "Profile chrome dir: $PROFILE_DIR/chrome"
```

### Core CSS Recipes

**Remove the tab bar (for use with a vertical tab extension like Sidebery or Tree Style Tab):**
```css
/* userChrome.css */
/* Hide horizontal tab bar entirely */
#TabsToolbar { visibility: collapse !important; }

/* Remove the title bar space */
#titlebar { display: none !important; }

/* Remove the navigation toolbar border */
#nav-bar { border-top: none !important; box-shadow: none !important; }
```

**Compact the toolbar to reclaim vertical space:**
```css
:root {
    /* Reduce tab height */
    --tab-min-height: 24px !important;
    --tab-block-margin: 2px !important;

    /* Reduce toolbar padding */
    --toolbar-field-focus-border-color: transparent !important;
    --toolbarbutton-inner-padding: 4px !important;

    /* Remove URL bar border on focus */
    #urlbar[breakout][breakout-extend] {
        margin-top: -1px !important;
        margin-bottom: -1px !important;
    }
}

/* Compact navigation toolbar */
#nav-bar {
    padding-top: 2px !important;
    padding-bottom: 2px !important;
}
```

**Hide the sidebar header (when using Tree Style Tab):**
```css
/* Remove sidebar header chrome, let TST handle its own header */
#sidebar-header { display: none !important; }
#sidebar-box {
    --sidebar-width: 200px !important;
}
```

**Match the toolbar to your rice color palette (Catppuccin Mocha example):**
```css
:root {
    /* Catppuccin Mocha */
    --crust:   #11111b;
    --mantle:  #181825;
    --base:    #1e1e2e;
    --surface0:#313244;
    --overlay0:#6c7086;
    --text:    #cdd6f4;
    --mauve:   #cba6f7;
    --blue:    #89b4fa;
}

/* Apply to toolbar */
#nav-bar, #TabsToolbar, toolbar {
    background-color: var(--crust) !important;
    color: var(--text) !important;
}

/* URL bar */
#urlbar-background {
    background-color: var(--surface0) !important;
    border-color: var(--overlay0) !important;
}

/* Active tab indicator */
.tabbrowser-tab[selected] .tab-background {
    background-color: var(--base) !important;
    border-top: 2px solid var(--mauve) !important;
}
```

### Popular Firefox CSS Rices

| Theme | Style | Repo |
|---|---|---|
| **ShyFox** | Ultra-minimal, all UI hidden by default | github.com/Naezr/ShyFox |
| **SimpleFox** | Clean minimal, no heavy customization | github.com/migueravila/SimpleFox |
| **cascade** | Vertical-first, collapsing URL bar | github.com/nicoth-in/Firefox-Cascade |
| **Firefox-One** | macOS Big Sur inspired | github.com/Goxore/firefox-one |
| **Catppuccin Firefox** | Catppuccin port for userChrome + theme | github.com/catppuccin/firefox |
| **Betterfox** | `user.js` only (perf + privacy, no CSS) | github.com/yokoffing/Betterfox |

Installing a CSS rice from GitHub:

```bash
# Example: Catppuccin userChrome
PROFILE_DIR=$(find ~/.mozilla/firefox -name "*.default-release" -type d | head -1)
mkdir -p "$PROFILE_DIR/chrome"

git clone https://github.com/catppuccin/firefox.git /tmp/catppuccin-firefox
cp /tmp/catppuccin-firefox/userChrome.css "$PROFILE_DIR/chrome/"

# Many rices provide a setup script
cd /tmp/catppuccin-firefox && ./setup.sh
```

---

## 58.4 Firefox Color Schemes and Palette Integration

### Firefox Color Extension

The **Firefox Color** extension (AMO: `firefox-color`) exposes Firefox's theme API via a web UI.
You can set toolbar background, text, icon, and tab colors independently. It generates a
shareable URL that encodes the full theme, making it easy to distribute or regenerate themes
from a script.

Install via:
```
https://addons.mozilla.org/en-US/firefox/addon/firefox-color/
```

### Pywalfox — Automatic wal/pywal Integration

Pywalfox reads your `~/.cache/wal/colors.json` (generated by `pywal` or `matugen`) and
automatically applies those colors to Firefox via the native messaging protocol. This means every
time you change your wallpaper and regenerate the palette, Firefox's UI updates to match.

```bash
# Install (note: use uv/pipx for isolation)
pipx install pywalfox

# Or with uv
uv tool install pywalfox

# Initial setup (patches the Firefox native messaging manifest)
pywalfox install

# After each pywal run, update Firefox:
pywalfox update

# To auto-update after wal, add to your wal post-hook:
# ~/.config/wal/templates/colors.sh (or in the wal config)
pywalfox update
```

For Hyprland users who run `wal` on wallpaper change via `hyprpaper` or `swww`, add the
`pywalfox update` call to your wallpaper-change script. See **Ch 47** for the full pywal pipeline.

### Catppuccin Theme

Catppuccin for Firefox consists of two layers: a browser extension theme (sets toolbar/tab
colors) and optional `userChrome.css` (structural changes). They can be used independently.

```bash
# Extension only (easiest) — install from AMO:
# https://addons.mozilla.org/en-US/firefox/addon/catppuccin-mocha-mauve/

# Full rice with userChrome:
PROFILE_DIR=$(find ~/.mozilla/firefox -name "*.default-release" -type d | head -1)
curl -sL https://raw.githubusercontent.com/catppuccin/firefox/main/userChrome.css \
    -o "$PROFILE_DIR/chrome/userChrome.css"
```

Available flavors: Latte (light), Frappé, Macchiato, Mocha (darkest). Accent colors: Rosewater,
Flamingo, Pink, Mauve, Red, Maroon, Peach, Yellow, Green, Teal, Sky, Sapphire, Blue, Lavender.

### Custom New Tab Page

Replacing the default new tab page is a high-visibility ricing win. Options:

```bash
# Option 1: nightTab extension (full UI, palette configurable)
# AMO: https://addons.mozilla.org/en-US/firefox/addon/nighttab/

# Option 2: Tabliss (widget-based, minimalist)
# AMO: https://addons.mozilla.org/en-US/firefox/addon/tabliss/

# Option 3: Local HTML file via user.js
# Create your custom page:
cat > ~/rice/newtab.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
<style>
  body { background: #1e1e2e; color: #cdd6f4; font-family: monospace; }
  /* Add your rice CSS here */
</style>
</head>
<body><h1>rice.local</h1></body>
</html>
EOF

# Point Firefox to it:
echo 'user_pref("browser.startup.homepage", "file:///home/USER/rice/newtab.html");' \
    >> "$PROFILE_DIR/user.js"
```

---

## 58.5 Chromium / Chrome Native Wayland

Chromium reached production-quality Wayland support with the Ozone platform abstraction layer.
The required launch flags differ from Firefox and must be set explicitly — Chromium does not
auto-detect Wayland like Firefox does with `MOZ_ENABLE_WAYLAND`.

### Launch Flags

```bash
# One-time test
chromium --ozone-platform=wayland \
         --enable-features=UseOzonePlatform,VaapiVideoDecodeLinuxGL,WaylandWindowDecorations \
         --use-gl=desktop

# For Google Chrome (same flags):
google-chrome-stable --ozone-platform=wayland \
                     --enable-features=UseOzonePlatform,VaapiVideoDecodeLinuxGL
```

### Persistent Flags File

Chromium reads a flags file at startup. The location differs by distribution and install method:

```bash
# Arch Linux (chromium package):
# ~/.config/chromium-flags.conf  OR  /etc/chromium/chromium.conf
cat > ~/.config/chromium-flags.conf << 'EOF'
--ozone-platform=wayland
--enable-features=UseOzonePlatform,VaapiVideoDecodeLinuxGL,WaylandWindowDecorations
--use-gl=desktop
--enable-gpu-rasterization
--enable-zero-copy
--ignore-gpu-blocklist
EOF

# Google Chrome (google-chrome package):
cat > ~/.config/google-chrome-flags.conf << 'EOF'
--ozone-platform=wayland
--enable-features=UseOzonePlatform,VaapiVideoDecodeLinuxGL
--use-gl=desktop
EOF

# Brave:
cat > ~/.config/brave-flags.conf << 'EOF'
--ozone-platform=wayland
--enable-features=UseOzonePlatform
EOF
```

Verify Chromium is running natively by visiting `chrome://gpu` — "GL_RENDERER" should list your
GPU name rather than a software rasterizer, and "Ozone platform" should show "wayland".

### Chromium Theming

Chromium themes are distributed via the Chrome Web Store and apply to the toolbar, new tab page
background, and tab colors. The customization depth is significantly shallower than Firefox
userChrome.css — there is no equivalent CSS injection API in production Chromium builds.

```bash
# Install Catppuccin theme for Chromium:
# chrome://extensions/ → "Open Chrome Web Store" → search "Catppuccin Mocha"

# Tokyo Night:
# https://chrome.google.com/webstore/detail/tokyo-night/

# For new tab page replacement in Chromium:
# chrome://extensions/ → "Tabliss" or "nightTab" (same extensions, cross-browser)
```

---

## 58.6 Electron App Wayland Flags

Electron is a Chromium wrapper. All Electron apps (VS Code, Slack, Discord, Obsidian, Notion,
Figma Desktop, etc.) require the same Ozone flags as Chromium to run natively on Wayland. Without
these flags, Electron apps run under XWayland and exhibit scaling artifacts, blurry fonts at
fractional scale factors, and broken cursor scaling.

### Per-Application Flags Files

Electron reads a `*-flags.conf` file from `~/.config/` at startup. The filename matches the
application binary name.

```bash
# VS Code
cat > ~/.config/code-flags.conf << 'EOF'
--ozone-platform=wayland
--enable-features=UseOzonePlatform,WaylandWindowDecorations
EOF

# VS Code Insiders
cat > ~/.config/code-insiders-flags.conf << 'EOF'
--ozone-platform=wayland
--enable-features=UseOzonePlatform,WaylandWindowDecorations
EOF

# Slack
cat > ~/.config/slack-flags.conf << 'EOF'
--ozone-platform=wayland
--enable-features=UseOzonePlatform
EOF

# Discord (official, not Vesktop)
cat > ~/.config/discord-flags.conf << 'EOF'
--ozone-platform=wayland
--enable-features=UseOzonePlatform
EOF

# Obsidian
cat > ~/.config/obsidian-flags.conf << 'EOF'
--ozone-platform=wayland
--enable-features=UseOzonePlatform,WaylandWindowDecorations
EOF

# Notion (Notion-app AUR)
cat > ~/.config/notion-app-enhanced-flags.conf << 'EOF'
--ozone-platform=wayland
EOF
```

### Global Electron Flags

A single `electron-flags.conf` file applies to all Electron applications that do not have their
own specific flags file. This is the most convenient approach and correct for most setups.

```bash
cat > ~/.config/electron-flags.conf << 'EOF'
--ozone-platform=wayland
--enable-features=UseOzonePlatform,WaylandWindowDecorations
EOF

# Some systems use electron-version-specific files:
# electron13-flags.conf, electron25-flags.conf, etc.
# Check which Electron version your app uses:
strings /usr/bin/APP | grep "Electron/"
```

### NixOS Declarative Configuration

On NixOS, per-app Wayland flags are set declaratively:

```nix
# home.nix or configuration.nix
programs.vscode = {
  enable = true;
  commandLineArgs = [
    "--ozone-platform=wayland"
    "--enable-features=UseOzonePlatform,WaylandWindowDecorations"
  ];
};

# For apps without dedicated options, use wrappers:
home.packages = with pkgs; [
  (discord.override {
    commandLineArgs = "--ozone-platform=wayland --enable-features=UseOzonePlatform";
  })
];
```

### Vesktop — Discord with Full Wayland Support

The standard Discord Electron app has inconsistent Wayland support. Vesktop (a Discord client
replacement built on Electron) ships with Vencord pre-installed and has better Wayland handling:

```bash
# Arch: AUR package
yay -S vesktop-bin

# Add flags:
cat > ~/.config/vesktop-flags.conf << 'EOF'
--ozone-platform=wayland
--enable-features=UseOzonePlatform,WaylandWindowDecorations
EOF
```

---

## 58.7 Browser in the Rice: Compositor Integration

### Window Rules for Browsers

A well-riced browser integrates seamlessly with your tiling layout. These rules cover the most
common edge cases:

```bash
# Hyprland — ~/.config/hypr/hyprland.conf

# Firefox: tile everywhere, float only known dialogs
windowrulev2 = nofloat, class:^(firefox)$, title:^(?!.*Picture-in-Picture).*$
windowrulev2 = float, class:^(firefox)$, title:^(Open File)$
windowrulev2 = float, class:^(firefox)$, title:^(Save As)$
windowrulev2 = float, class:^(firefox)$, title:^(Library)$
windowrulev2 = float, class:^(firefox)$, title:^(About Mozilla Firefox)$
windowrulev2 = size 600 400, class:^(firefox)$, title:^(About Mozilla Firefox)$

# PiP overlay pinned to bottom-right
windowrulev2 = float, class:^(firefox)$, title:^(Picture-in-Picture)$
windowrulev2 = pin, class:^(firefox)$, title:^(Picture-in-Picture)$
windowrulev2 = size 480 270, class:^(firefox)$, title:^(Picture-in-Picture)$
windowrulev2 = move 100%-490 100%-280, class:^(firefox)$, title:^(Picture-in-Picture)$

# Chromium
windowrulev2 = nofloat, class:^(chromium)$
windowrulev2 = float, class:^(chromium)$, title:^(Open Files)$

# Sway equivalent
for_window [app_id="firefox" title="Picture-in-Picture"] {
    floating enable
    sticky enable
    resize set 480 270
    move position 1440 780
}
```

### Firefox Release Channel Comparison

| Channel | Update Cadence | Wayland Maturity | Recommendation |
|---|---|---|---|
| **Firefox Developer Edition** | Nightly-ish | Bleeding edge, most features | For ricing exploration |
| **Firefox Nightly** | Daily | Experimental, may break | Testing only |
| **Firefox** (stable) | ~4 weeks | Production quality | Recommended |
| **Firefox ESR** | ~1 year | May lag on Wayland features | Avoid for Wayland rice |
| **Librewolf** | Tracks stable | Same as stable, extra privacy | Good alternative |
| **Zen Browser** | Tracks stable | Based on Firefox, vertical tabs | Rising option |

### Multi-Account Containers Color Coding

Firefox Multi-Account Containers assigns a color strip to each container's tabs. Align these
colors with your rice palette for a cohesive look:

```bash
# Install the extension:
# https://addons.mozilla.org/en-US/firefox/addon/multi-account-containers/

# Container colors available: blue, turquoise, green, yellow, orange, red, pink, purple
# Assign containers to domains via the extension UI or the containers.json file:
# ~/.mozilla/firefox/PROFILE/containers.json
```

### Start Page / New Tab Theming Summary

| Extension | Style | Color Customization | Clock/Widgets |
|---|---|---|---|
| **nightTab** | Grid of bookmarks | Full palette control | Yes |
| **Tabliss** | Widget-based | Background + text color | Yes |
| **Marble New Tab** | Minimal | Limited | No |
| **Custom HTML** | Unlimited | Full CSS control | Via JS |

---

## 58.8 Troubleshooting

### Firefox Falls Back to XWayland

**Symptom:** `about:support` shows "Window Protocol: x11" instead of "wayland".

**Causes and fixes:**
```bash
# 1. Check the env var is set in the compositor's environment, not just the shell:
hyprctl env | grep WAYLAND      # Hyprland
swaymsg -t get_outputs          # shows Sway is running (env set if compositor started)

# 2. Verify it reaches Firefox's launch context:
MOZ_ENABLE_WAYLAND=1 firefox --new-instance &
# Check about:support in this instance

# 3. If using a .desktop launcher, override the Exec line:
mkdir -p ~/.local/share/applications
cp /usr/share/applications/firefox.desktop ~/.local/share/applications/
# Edit Exec= line to prefix: env MOZ_ENABLE_WAYLAND=1 ...
sed -i 's|^Exec=firefox|Exec=env MOZ_ENABLE_WAYLAND=1 firefox|' \
    ~/.local/share/applications/firefox.desktop
update-desktop-database ~/.local/share/applications/
```

### VA-API Not Working in Firefox

**Symptom:** `about:support` → Media → "Video Decode" shows software path.

```bash
# 1. Verify vainfo works:
vainfo 2>&1 | head -20

# 2. Check LIBVA_DRIVER_NAME is correct:
# AMD: should be empty (auto-detected) or radeonsi
# Intel (modern): iHD
# Intel (old): i965

# 3. Run Firefox with VA-API debug logging:
LIBVA_MESSAGING_LEVEL=1 MOZ_ENABLE_WAYLAND=1 firefox 2>&1 | grep -i vaapi

# 4. Check that media.ffmpeg.vaapi.enabled AND
#    media.hardware-video-decoding.force-enabled are BOTH true in about:config

# 5. Flatpak Firefox needs additional portal flags:
flatpak override --user --env=LIBVA_DRIVER_NAME=radeonsi org.mozilla.firefox
```

### Chromium Flags Not Being Read

**Symptom:** `chrome://gpu` shows Ozone: x11 or software rasterizer.

```bash
# Check the flags file is in the right location and has correct syntax:
cat ~/.config/chromium-flags.conf

# Verify the file name matches your binary:
which chromium            # might be chromium-browser on Ubuntu/Debian
ls ~/.config/ | grep flag # list all flag files

# For Flatpak Chromium:
flatpak override --user \
    --env=CHROME_EXTRA_FLAGS="--ozone-platform=wayland" \
    com.github.Eloston.UngoogledChromium
```

### Electron App is Blurry at Fractional Scale

**Symptom:** VS Code, Slack, etc. appear blurry or have incorrect DPI when display is at 1.25x,
1.5x, etc.

```bash
# This indicates the app is running under XWayland (no Ozone flags)
# or the Wayland scaling hint is not being passed.

# Fix: Ensure ozone flags are set, then also add:
# ~/.config/code-flags.conf
--ozone-platform=wayland
--enable-features=UseOzonePlatform,WaylandWindowDecorations
--force-device-scale-factor=1.5    # match your display scale factor

# For GTK_SCALE-based apps (not Electron), set:
# GDK_BACKEND=wayland
# GDK_SCALE=2  (integer only for GTK3)
# GDK_DPI_SCALE=1.5  (fractional for text)
```

### userChrome.css Changes Not Taking Effect

```bash
# 1. Confirm the pref is set:
grep "legacyUserProfileCustomizations" "$PROFILE_DIR/prefs.js"
# Should show: user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);

# 2. Confirm the file is in the correct location:
ls -la "$PROFILE_DIR/chrome/"
# Should list: userChrome.css

# 3. Restart Firefox fully (not just reload):
pkill firefox && sleep 1 && firefox &

# 4. Check for CSS syntax errors via the Browser Toolbox:
# about:config → devtools.chrome.enabled = true
# Tools → Browser Tools → Browser Toolbox → Inspector
# Navigate to the element you expect to be styled and check computed styles
```

### Firefox Crashes on Wayland with NVIDIA

NVIDIA proprietary drivers have historically had issues with Firefox's Wayland backend due to EGL
context handling. If Firefox crashes on launch:

```bash
# Workaround 1: Force EGL
MOZ_ENABLE_WAYLAND=1 MOZ_WEBRENDER=1 firefox

# Workaround 2: Use GBM backend
MOZ_ENABLE_WAYLAND=1 GBM_BACKEND=nvidia-drm __GLX_VENDOR_LIBRARY_NAME=nvidia firefox

# Workaround 3: Stay on XWayland for Firefox, use Wayland for everything else
# (not ideal, but functional)
unset MOZ_ENABLE_WAYLAND
export GDK_BACKEND=x11
```

---

## Cross-References

- **Ch 47 — Pywal and Automatic Color Theming**: Full pywal/matugen pipeline, post-hooks for
  running `pywalfox update` after palette generation.
- **Ch 53 — Session Startup and Environment Variables**: Where and how to set `MOZ_ENABLE_WAYLAND`
  and `LIBVA_DRIVER_NAME` so they reach all launched applications.
- **Ch 52 — xdg-desktop-portal: Screen Sharing, File Chooser, Settings**: How `xdg-desktop-portal-hyprland` (or `-gtk`, `-wlr`) provides
  the file picker and screen sharing backends that Firefox uses via `widget.use-xdg-desktop-portal.*`.
- **Ch 35 — GTK Theming** and **Ch 36 — Qt and KDE Theming**: The same `GDK_BACKEND` and `QT_QPA_PLATFORM`
  variables that affect browsers also affect all GTK/Qt apps — set them consistently.
- **Ch 44 — Catppuccin End-to-End Theming**: Applying a single Catppuccin flavor across the
  terminal, compositor, bar, and browser simultaneously.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
