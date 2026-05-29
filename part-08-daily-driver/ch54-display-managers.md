# Chapter 54 — Display Managers and Greeters: SDDM, GDM, greetd

## Overview
The display manager (DM) is the login screen you see before your compositor starts.
Choosing and theming it is part of a complete rice. This chapter covers the three
main options for Wayland setups.

## Sections

### 54.1 Display Manager Options

| DM | Wayland support | Theming | Notes |
|----|----------------|---------|-------|
| SDDM | Qt-based, full | QML themes | Best for Hyprland/KDE |
| GDM | Mutter-based | GNOME only | Best for GNOME |
| greetd | Minimal daemon | Via greeter | Most flexible, ricer's choice |
| LightDM | Partial | GTK greeters | Legacy, declining |
| ly | TUI | None | Minimal TTY-style |

### 54.2 SDDM — Qt-Based Login Screen

**Installation:**
```bash
sudo pacman -S sddm
sudo systemctl enable sddm
```

**Config:** `/etc/sddm.conf.d/sddm.conf`
```ini
[Theme]
Current=catppuccin-mocha
CursorTheme=Catppuccin-Mocha-Dark-Cursors
CursorSize=24

[General]
DisplayServer=wayland   # use Wayland SDDM session
GreeterEnvironment=QT_WAYLAND_SHELL_INTEGRATION=layer-shell

[Autologin]
# User=yourname      # enable for no-login setup
# Session=hyprland
```

**SDDM Theming:**
Themes are QML-based, located in `/usr/share/sddm/themes/` or `~/.local/share/sddm/themes/`

Popular SDDM themes:
- **Catppuccin** (`sddm-catppuccin-git` AUR): matches Catppuccin rice
- **Sugar-Dark**: clean minimal dark theme
- **Astronaut**: space-themed
- **Where is my SDDM theme**: highly customizable
- **Corners**: material-inspired

**Installing a theme:**
```bash
# Manual
git clone https://github.com/catppuccin/sddm ~/.local/share/sddm/themes/catppuccin
# Update /etc/sddm.conf.d/sddm.conf: Current=catppuccin

# NixOS
services.displayManager.sddm = {
    enable = true;
    wayland.enable = true;
    theme = "catppuccin-mocha";
    package = pkgs.sddm;
    extraPackages = [ pkgs.catppuccin-sddm ];
};
```

**Writing a custom SDDM theme:**
- QML file: `Main.qml` with `SessionModel`, `UserModel`, keyboard input
- Background image, clock, user avatar, password field all in QML
- Preview with: `sddm-greeter-qt6 --test-mode --theme /path/to/theme`

### 54.3 GDM — GNOME Display Manager

Best when using GNOME Shell. Themed via GNOME extensions or CSS.

**Config:** `/etc/gdm/custom.conf`
```ini
[daemon]
WaylandEnable=true
AutomaticLoginEnable=false
```

**Theming GDM:**
```bash
# Install a GDM theme extension
gnome-extensions install user-themes@gnome-shell-extensions.gcampax.github.com
# Apply theme
gsettings set org.gnome.shell.extensions.user-theme name "ThemeName"
```

**GDM background:**
```bash
# ~/.local/share/gnome-background-properties/custom.xml
# or via gdm-settings tool
```

### 54.4 greetd — The Compositor-Agnostic Daemon

greetd is a minimal login daemon that just launches a greeter (any Wayland app).
It's the most flexible option for custom riced login screens.

**Installation:**
```bash
sudo pacman -S greetd
sudo systemctl enable greetd
```

**Config:** `/etc/greetd/config.toml`
```toml
[terminal]
vt = 1

[default_session]
command = "agreety --cmd Hyprland"   # minimal TTY greeter
# or:
command = "regreet"                  # GTK4 greeter
# or:
command = "tuigreet --cmd Hyprland --time --greeting 'Welcome back'"
```

### 54.5 greetd Greeters

**ReGreet** — GTK4, themeable:
```toml
# /etc/greetd/config.toml
[default_session]
command = "regreet"
user = "greeter"

# /etc/greetd/regreet.toml
[background]
path = "/usr/share/wallpapers/default.jpg"
fit = "Cover"

[GTK]
application_prefer_dark_theme = true
theme_name = "catppuccin-mocha-mauve-standard+default"
icon_theme_name = "Papirus-Dark"
font_name = "Inter 11"
```

**tuigreet** — TUI (terminal-based greeter):
```bash
tuigreet --cmd Hyprland \
         --time \
         --remember \
         --remember-session \
         --greeting "Welcome"
```

**wlgreet** — wlroots-based minimal Wayland greeter:
- Pure Wayland rendering, very minimal
- Requires wlroots-based session compositor to run inside

**Quickshell greeter (Ch 24):**
- Full QML greeter using `Quickshell.Services.Greetd`
- Unlimited visual customization

### 54.6 No Display Manager — TTY Autologin

For minimal setups that skip the login screen entirely:
```bash
# /etc/systemd/system/getty@tty1.service.d/override.conf
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin yourname --noclear %I $TERM
```

Then in `~/.zprofile`:
```bash
if [ -z "$WAYLAND_DISPLAY" ] && [ "$XDG_VTNR" = "1" ]; then
    exec Hyprland
fi
```

### 54.7 Session Selection
`.desktop` files in `/usr/share/wayland-sessions/` define available sessions:
```ini
# /usr/share/wayland-sessions/hyprland.desktop
[Desktop Entry]
Name=Hyprland
Comment=A dynamic tiling Wayland compositor
Exec=Hyprland
Type=Application
```

SDDM and GDM read these automatically. greetd via `tuigreet --sessions /usr/share/wayland-sessions/`.
