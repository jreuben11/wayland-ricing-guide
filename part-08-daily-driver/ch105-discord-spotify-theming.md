# Chapter 105 — Discord and Spotify Theming: Vencord and Spicetify

## Overview

Discord and Spotify are among the most-used apps on a riced desktop, and both
are Electron/web-based which means their UI is HTML+CSS — fully theme-able.
Vencord injects custom CSS and plugins into Discord; Spicetify patches Spotify's
web client. Both have large theme ecosystems and integrate with Catppuccin,
Gruvbox, and other popular palettes.

---

## 105.1 Vencord — Discord Theming

### What Vencord is

Vencord is a Discord client mod that injects into Discord's web rendering layer.
It provides:
- **QuickCSS** — live CSS editor, changes apply instantly
- **Themes** — BetterDiscord-compatible `.theme.css` files
- **Plugins** — JavaScript plugins for UI/UX changes

### Installation on Linux (Wayland)

**Vesktop** (recommended — purpose-built for Linux, native Wayland):
```bash
paru -S vesktop-bin
# or:
paru -S vesktop   # build from source

# Launch:
vesktop
```

Vesktop bundles Vencord and runs Discord as a proper Wayland app via Electron's
`--ozone-platform=wayland` flag. It also supports tray icons, custom window
controls, and proper screen sharing via the portal.

**Inject into existing Discord:**
```bash
paru -S vencord-installer
vencord-installer   # GUI installer, select your Discord installation
```

### QuickCSS

Open Discord → Settings → Vencord → QuickCSS. Changes apply live:

```css
/* QuickCSS — ~/path is not needed, write CSS directly */

/* Catppuccin Mocha colour variables */
:root {
    --background-primary:   #1e1e2e;
    --background-secondary: #181825;
    --background-tertiary:  #11111b;
    --channeltextarea-background: #313244;
    --text-normal:   #cdd6f4;
    --text-muted:    #6c7086;
    --text-link:     #89b4fa;
    --brand-500:     #cba6f7;
    --brand-360:     #b4befe;
    --header-primary: #cdd6f4;
    --header-secondary: #bac2de;
    --interactive-normal: #cdd6f4;
    --interactive-hover:  #ffffff;
}

/* Rounded corners */
.container_c2effd {
    border-radius: 12px;
    overflow: hidden;
}

/* Transparent sidebar */
.sidebar_a4d4d9 {
    background: rgba(17, 17, 27, 0.7) !important;
    backdrop-filter: blur(10px);
}

/* Custom scrollbar */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
    background: #45475a;
    border-radius: 2px;
}
```

### Installing Themes

Themes are `.theme.css` files. Place them in:
```bash
# Location (created by Vencord):
~/.config/vesktop/themes/          # Vesktop
~/.config/discord/themes/          # standard Discord with Vencord

# Or install via Vencord UI:
# Settings → Themes → Online Themes → search & enable
```

**Popular themes:**
```bash
# Catppuccin for Discord
# https://github.com/catppuccin/discord
# Copy the relevant .theme.css to your themes directory

# Midnight — clean dark with transparency
# https://github.com/refact0r/midnight-discord

# Comfy — cozy aesthetic
# https://github.com/Comfy-Themes/Discord
```

### Useful Vencord Plugins

| Plugin | Effect |
|--------|--------|
| `NitroBypass` | Use any emoji/sticker |
| `BetterRoleColors` | Use role colours in chat |
| `GifPaste` | Paste GIFs from clipboard |
| `NoTrack` | Disable Discord analytics |
| `Experiments` | Enable Discord experiments UI |
| `USRBG` | Custom user profile backgrounds |
| `WebRichPresence` | Browser-based rich presence |

Enable in: Settings → Vencord → Plugins

### Hyprland Window Rules for Discord

```conf
# hyprland.conf
# Vesktop
windowrulev2 = float,         class:^(vesktop)$, title:^(Discord Popout)$
windowrulev2 = workspace 3,   class:^(vesktop)$
windowrulev2 = opacity 0.95 0.90, class:^(vesktop)$

# Screen share picker (needs portal)
windowrulev2 = float, class:^(vesktop)$, title:^(ScreenPicker)$
```

### Wayland Screen Sharing with Vesktop

```bash
# Ensure the portal is set up (Ch 52):
sudo pacman -S xdg-desktop-portal-hyprland

# In Vesktop settings → Linux → enable "Use System ScreenShare picker"
# This routes through the portal instead of XWayland
```

---

## 105.2 Spicetify — Spotify Theming

### What Spicetify is

Spicetify patches Spotify's built-in web renderer (Spotify is a CEF/Chromium
app) to inject custom CSS, JavaScript, and extensions. Unlike Vencord, it
patches the app files directly — Spotify updates revert the patch, requiring
re-application.

### Installation

```bash
# Arch (AUR)
paru -S spicetify-cli

# Verify:
spicetify --version

# First-time setup (grant Spicetify write access to Spotify):
sudo chmod a+wr /opt/spotify
sudo chmod a+wr /opt/spotify/Apps -R
```

### Basic workflow

```bash
# Apply changes (after any config/theme edit):
spicetify apply

# Watch for errors:
spicetify apply --watch

# Restore Spotify to default (after an update):
spicetify restore backup apply

# Backup before first use:
spicetify backup apply
```

### Spicetify Marketplace (recommended)

Spicetify Marketplace is an extension that adds a theme/extension browser
inside Spotify itself:

```bash
# Install Marketplace
curl -fsSL https://raw.githubusercontent.com/spicetify/marketplace/main/resources/install.sh | sh

spicetify apply
```

After applying, open Spotify → Marketplace tab (in left sidebar) to browse and
install themes with one click.

### Manual Theme Installation

```bash
# Themes go in:
~/.config/spicetify/Themes/

# Extensions go in:
~/.config/spicetify/Extensions/

# Example: install Catppuccin
git clone https://github.com/catppuccin/spicetify \
    ~/.config/spicetify/Themes/catppuccin

# Apply a specific flavour:
spicetify config current_theme catppuccin color_scheme mocha
spicetify apply
```

### Spicetify config (`~/.config/spicetify/config-xpui.ini`)

```ini
[Setting]
spotify_path         = /opt/spotify
prefs_path           = /home/user/.config/spotify/prefs
current_theme        = catppuccin
color_scheme         = mocha
inject_css           = 1
replace_colors       = 1
overwrite_assets     = 0

[Preprocesses]
disable_ui_logging   = 1
remove_rtl_rule      = 1
expose_apis          = 1

[AdditionalOptions]
extensions           = shuffle+.js|fullAppDisplay.js
```

### Writing a Custom Spicetify Theme

```
~/.config/spicetify/Themes/MyTheme/
├── color.ini         ← colour palette
├── user.css          ← custom CSS
└── theme.js          ← optional JavaScript (advanced)
```

**color.ini:**
```ini
[mocha]
text               = CDD6F4
subtext            = BAC2DE
main               = 1E1E2E
sidebar            = 181825
player             = 11111B
card               = 313244
shadow             = 11111B
selected-row       = 45475A
button             = CBA6F7
button-active      = B4BEFE
button-disabled    = 6C7086
tab-active         = CBA6F7
notification       = 89B4FA
notification-error = F38BA8
misc               = 45475A
```

**user.css:**
```css
/* Custom CSS on top of the colour palette */

/* Rounded playlist cards */
.main-card-card {
    border-radius: 12px !important;
    overflow: hidden;
}

/* Custom scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-thumb {
    background: var(--spice-misc);
    border-radius: 3px;
}

/* Transparent now-playing bar */
.Root__now-playing-bar {
    background: rgba(var(--spice-rgb-main), 0.8) !important;
    backdrop-filter: blur(10px);
}

/* Larger album art */
.main-nowPlayingWidget-coverArt {
    width: 64px !important;
    height: 64px !important;
    border-radius: 8px;
}
```

Apply:
```bash
spicetify config current_theme MyTheme color_scheme mocha
spicetify apply
```

### Keeping Spicetify After Spotify Updates

Spotify auto-updates overwrite patched files. Create a hook:

```bash
# ~/.config/systemd/user/spicetify-restore.service
[Unit]
Description=Restore Spicetify after Spotify update
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/bin/spicetify restore backup apply

[Install]
WantedBy=default.target
```

Or use a pacman hook:
```
# /etc/pacman.d/hooks/spicetify.hook
[Trigger]
Operation = Upgrade
Type = Package
Target = spotify

[Action]
Description = Reapplying Spicetify...
When = PostTransaction
Exec = /bin/su -c 'spicetify restore backup apply' username
```

### Hyprland Window Rules for Spotify

```conf
# hyprland.conf
windowrulev2 = workspace name:music silent, class:^(Spotify)$
windowrulev2 = opacity 0.95 0.90,          class:^(Spotify)$
windowrulev2 = tile,                        class:^(Spotify)$
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
