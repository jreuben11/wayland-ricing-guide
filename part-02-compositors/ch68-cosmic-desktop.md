# Chapter 68 — COSMIC Desktop: System76's Rust DE

## Overview

COSMIC is System76's new desktop environment written entirely in Rust, built on
Smithay (cosmic-comp). It takes a novel approach: tiling and stacking in one,
with a unique "autotiling" mode. First stable release: COSMIC Alpha 1 (2024).

COSMIC represents perhaps the most ambitious greenfield desktop environment
effort since KDE Plasma was rewritten for the 4.x series. Unlike incremental
evolutions of existing codebases, COSMIC was designed from scratch with
modern Rust idioms, a first-principles UI framework (iced), and Wayland
nativity baked in at every layer. For the ricing enthusiast, this means a
desktop where the customization surface is still being shaped — early adopters
can influence the direction, and the lack of legacy cruft means configs are
clean, well-structured, and machine-friendly.

This chapter covers installation across distributions, deep configuration of the
cosmic-comp compositor, COSMIC Panel customization, theme authoring in RON
format, building or packaging custom applets, and performance tuning for
both integrated graphics and discrete NVIDIA/AMD GPUs.

---

## 68.1 Why COSMIC Is Different

COSMIC is not a reskinned GNOME or a Qt-based KDE clone. Its entire stack —
from the compositor down to the calculator app — is written in Rust. This
choice has concrete engineering benefits: memory safety without garbage
collection pauses, fearless concurrency (critical for async Wayland event
loops), and compile-time guarantees that eliminate whole categories of runtime
crashes. For daily drivers who have experienced GNOME Shell lockups or KDE
Plasma segfaults after heavy extension use, this philosophy is appealing.

The compositor, `cosmic-comp`, is built on **Smithay**, the Rust Wayland
compositor library. Smithay handles the protocol machinery — `xdg-shell`,
`wlr-layer-shell`, input routing, DRM/KMS output management — while
`cosmic-comp` implements the layout engine and session logic on top. This is
analogous to how Mutter wraps core Wayland plumbing for GNOME Shell, but
without two decades of C legacy attached.

The **autotiling** feature deserves special mention because it is fundamentally
different from how tiling works in Hyprland or Sway. Rather than a separate
tiling mode you switch into, autotiling is a per-workspace toggle: windows
opened onto a workspace with autotiling enabled are automatically arranged in
a binary split tree. When you close a window, the gap closes. When you open
a new one, the tree re-balances. You can drag window borders to adjust splits
in real time. Floating windows coexist in the same workspace — you do not need
to "promote" a window out of tiling into float mode, you simply drag it by
the titlebar past the tiling grid.

Key properties that distinguish COSMIC from alternatives:

- **Full Rust stack**: `cosmic-comp` (Smithay), `cosmic-settings`, `cosmic-panel`,
  all COSMIC apps including terminal, file manager, text editor, and calculator
- **Not GNOME, not KDE**: genuinely new design language built on `iced`, not GTK
  or Qt — this means no GTK theming, no Qt styling, no adwaita override hacks
- **Autotile mode**: windows automatically tile per-workspace, toggled with
  `Super+Y`; stacking and tiling are not mutually exclusive states
- **System76 backing**: full-time funded development team, ships on Pop!_OS
  hardware as the primary customer; not a volunteer weekend project
- **Wayland-native from day 1**: no XWayland dependency for COSMIC's own apps,
  though XWayland is available for legacy X11 software
- **RON-based theming**: themes use Rust Object Notation, a structured human-
  readable format that is type-checked at parse time

| Aspect            | COSMIC            | Hyprland        | KDE Plasma      | GNOME Shell     |
|-------------------|-------------------|-----------------|-----------------|-----------------|
| Language          | Rust              | C++             | C++/QML         | C/JS            |
| Compositor base   | Smithay           | Aquamarine      | KWin            | Mutter          |
| Tiling            | Native (autotile) | Native          | KWin script     | Extension       |
| UI toolkit        | iced + libcosmic  | None            | Qt/QML          | GTK4/libadwaita |
| Theme format      | RON               | TOML/CSS        | Plasma theme    | adwaita tokens  |
| Maturity (2025)   | Beta              | Stable          | Very stable     | Very stable     |
| Ricing culture    | Growing           | Huge            | Large           | Medium          |
| Config location   | `~/.config/cosmic`| `~/.config/hypr`| `~/.config/kde` | `dconf`         |

---

## 68.2 Installation

### 68.2.1 Pop!_OS

COSMIC is the default desktop on Pop!_OS 24.04 and later. If you are running
Pop!_OS 22.04 with GNOME and want to migrate, System76 provides a transition
package. Be aware that Pop!_OS 22.04 and 24.04 are not simply a DE swap; the
underlying package management (system76-scheduler, apt vs. pop-upgrade) also
differs.

```bash
# On Pop!_OS 24.04, COSMIC is already installed. Verify:
cosmic-comp --version
cosmic-settings --version

# If upgrading from Pop!_OS 22.04:
sudo pop-upgrade release upgrade
# This is a full OS upgrade, not just a DE swap.
```

### 68.2.2 Arch Linux and Arch-Based Distributions

The `cosmic-epoch` AUR meta-package pulls in all required components. Building
from source via AUR takes considerable time on first install (~30 minutes on
a modern machine) because Rust compilation is CPU-intensive. Use a parallel
build and ensure you have `base-devel` and `rust` installed.

```bash
# Prerequisites
sudo pacman -S --needed base-devel rust git

# Install paru if not present
git clone https://aur.archlinux.org/paru.git /tmp/paru
cd /tmp/paru && makepkg -si

# Install full COSMIC epoch (recommended)
paru -S cosmic-epoch

# Or cherry-pick individual components
paru -S cosmic-comp          # the compositor
paru -S cosmic-settings      # settings application
paru -S cosmic-panel         # top panel
paru -S cosmic-launcher      # app launcher (Super key)
paru -S cosmic-session       # session manager
paru -S cosmic-greeter       # login greeter (requires display manager config)
paru -S cosmic-bg            # wallpaper daemon
paru -S cosmic-notifications # notification daemon (implements org.freedesktop.Notifications)
paru -S cosmic-workspaces    # workspace widget for panel
paru -S cosmic-app-library   # application grid

# Enable the COSMIC session in your display manager
# For SDDM:
sudo systemctl enable sddm
# Select "COSMIC" from the session dropdown at login

# For GDM (from a GNOME install):
sudo systemctl disable gdm
sudo systemctl enable sddm
```

To start a COSMIC session from TTY without a display manager:

```bash
# ~/.local/bin/start-cosmic
#!/bin/bash
export XDG_SESSION_TYPE=wayland
export XDG_SESSION_DESKTOP=cosmic
export XDG_CURRENT_DESKTOP=COSMIC
exec cosmic-session
```

```bash
chmod +x ~/.local/bin/start-cosmic
# Add to ~/.zprofile or ~/.bash_profile to auto-launch on TTY1:
if [[ -z $DISPLAY && $XDG_VTNR -eq 1 ]]; then
  exec ~/.local/bin/start-cosmic
fi
```

### 68.2.3 NixOS

The community flake maintained by `lilyinstarlight` provides the most complete
NixOS integration. As of 2025, COSMIC is not yet in the official `nixpkgs`
channel, but the flake tracks upstream closely and is the recommended path.

```nix
# flake.nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    cosmic.url = "github:lilyinstarlight/nixos-cosmic";
    cosmic.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { nixpkgs, cosmic, ... }: {
    nixosConfigurations.mymachine = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        cosmic.nixosModules.default
        {
          nix.settings = {
            substituters = [ "https://cosmic.cachix.org" ];
            trusted-public-keys = [
              "cosmic.cachix.org-1:Dya9IyXD4xdBehWjrkPv6rtxpmMdRel02smYzA85d/E="
            ];
          };
          services.desktopManager.cosmic.enable = true;
          services.displayManager.cosmic-greeter.enable = true;
        }
      ];
    };
  };
}
```

Without the Cachix substituter, NixOS will compile every COSMIC package from
source — plan for 1–2 hours on first build. The substituter provides binary
cache hits for most packages on `x86_64-linux` and `aarch64-linux`.

### 68.2.4 Fedora / openSUSE / Debian

As of mid-2025, COPR repos exist for Fedora and community OBS repos for
openSUSE. These are less mature than the Arch AUR packages.

```bash
# Fedora (COPR — check for current status before using)
sudo dnf copr enable ryanabx/cosmic-epoch
sudo dnf install cosmic-epoch

# openSUSE Tumbleweed (OBS)
sudo zypper ar https://download.opensuse.org/repositories/X11:/COSMIC/openSUSE_Tumbleweed/ cosmic
sudo zypper ref && sudo zypper in cosmic-epoch
```

---

## 68.3 cosmic-comp: The Compositor

`cosmic-comp` is the heart of the COSMIC desktop. Understanding its architecture
helps you configure it effectively and debug issues when they arise.

### 68.3.1 Architecture

cosmic-comp is a full-featured Wayland compositor implementing:

- `xdg-shell` (application windows)
- `wlr-layer-shell` (panels, overlays, wallpapers)
- `xdg-output-unstable-v1` (multi-monitor layout)
- `wp-fractional-scale-v1` (HiDPI fractional scaling)
- `wp-viewporter`
- `xwayland` (legacy X11 app support via the embedded XWayland instance)
- `cosmic-toplevel-info-unstable-v1` (COSMIC's own protocol for taskbars)
- `cosmic-workspace-unstable-v1` (workspace management protocol)

The layout engine supports three modes per workspace:

| Mode     | Behavior                                           | Toggle           |
|----------|----------------------------------------------------|------------------|
| Float    | Traditional stacking, windows overlap freely       | `Super+Y` (cycle)|
| Autotile | Binary split tree, new windows split the focused   | `Super+Y` (cycle)|
| Manual   | Tiling with explicit placement commands            | `Super+Y` (cycle)|

### 68.3.2 Config File Location and Schema

COSMIC uses a custom config schema system instead of INI, TOML, or JSON. Config
files are stored under `~/.config/cosmic/` in a directory hierarchy where each
segment encodes the app/component ID and schema version:

```
~/.config/cosmic/
├── com.system76.CosmicComp/
│   └── v1/
│       ├── autotile
│       ├── autotile_behavior
│       ├── gaps
│       ├── active_hint
│       └── xkb_config
├── com.system76.CosmicPanel.Panel/
│   └── v1/
│       └── config
└── com.system76.CosmicSettings/
    └── v1/
        └── color_scheme
```

Each file contains a single RON-encoded value. You can read and write them
directly with a text editor. Changes take effect on the next cosmic-settings
sync or compositor restart.

```bash
# Read current autotile setting
cat ~/.config/cosmic/com.system76.CosmicComp/v1/autotile
# Output: false  (or true)

# Enable autotile globally (sets default for new workspaces)
echo 'true' > ~/.config/cosmic/com.system76.CosmicComp/v1/autotile

# Set gap size (in logical pixels)
echo '8' > ~/.config/cosmic/com.system76.CosmicComp/v1/gaps

# Enable active window hint (colored border on focused window)
echo 'true' > ~/.config/cosmic/com.system76.CosmicComp/v1/active_hint
```

### 68.3.3 Keyboard Shortcuts

COSMIC keybindings are configured in:
`~/.config/cosmic/com.system76.CosmicComp/v1/keybindings`

The file format is a RON map of action to key combination. Example:

```ron
{
    "terminate": Some(("super", "backspace")),
    "close": Some(("super", "q")),
    "toggle_tiling": Some(("super", "y")),
    "focus_left": Some(("super", "h")),
    "focus_down": Some(("super", "j")),
    "focus_up": Some(("super", "k")),
    "focus_right": Some(("super", "l")),
    "move_left": Some(("super_shift", "h")),
    "move_down": Some(("super_shift", "j")),
    "move_up": Some(("super_shift", "k")),
    "move_right": Some(("super_shift", "l")),
    "workspace_1": Some(("super", "1")),
    "workspace_2": Some(("super", "2")),
    "workspace_3": Some(("super", "3")),
    "workspace_4": Some(("super", "4")),
    "workspace_5": Some(("super", "5")),
    "move_window_workspace_1": Some(("super_shift", "1")),
    "move_window_workspace_2": Some(("super_shift", "2")),
    "launch_terminal": Some(("super", "t")),
    "screenshot": Some(("super", "print")),
}
```

After editing, reload with:

```bash
# Soft reload (sends SIGUSR1 to cosmic-comp)
pkill -SIGUSR1 cosmic-comp

# Or restart the full session (use if SIGUSR1 has no effect)
loginctl terminate-session $XDG_SESSION_ID
```

### 68.3.4 XKB Configuration

Keyboard layout is set via:
`~/.config/cosmic/com.system76.CosmicComp/v1/xkb_config`

```ron
XkbConfig(
    rules: "",
    model: "",
    layout: "us",
    variant: "",
    options: Some("caps:escape,compose:ralt"),
)
```

For Colemak-DH with caps-as-escape:

```ron
XkbConfig(
    rules: "",
    model: "",
    layout: "us",
    variant: "colemak_dh",
    options: Some("caps:escape"),
)
```

---

## 68.4 COSMIC Panel

The top panel is a separate process (`cosmic-panel`) that communicates with
the compositor via `wlr-layer-shell`. This design means the panel can crash
without taking down the compositor or your open applications — a significant
improvement over GNOME Shell where the panel is part of the compositor process.

### 68.4.1 Panel Configuration

Panel config lives at:
`~/.config/cosmic/com.system76.CosmicPanel.Panel/v1/config`

```ron
CosmicPanelConfig(
    anchor: Top,
    anchor_gap: false,
    layer: Top,
    keyboard_interactivity: None,
    size: S,
    name: "Panel",
    background: ThemeDefault(None),
    plugins_wings: Some((
        ["com.system76.CosmicAppletWorkspaces", "com.system76.CosmicAppletAppMenu"],
        ["com.system76.CosmicAppletTime",
         "com.system76.CosmicAppletNetwork",
         "com.system76.CosmicAppletBluetooth",
         "com.system76.CosmicAppletBattery",
         "com.system76.CosmicAppletAudio",
         "com.system76.CosmicAppletNotifications",
         "com.system76.CosmicAppletPower"]
    )),
    plugins_center: Some([
        "com.system76.CosmicAppletTime",
    ]),
    expand_plugins_center: true,
    anchor_gap: false,
    opacity: 1.0,
    autohide: None,
)
```

### 68.4.2 Adding a Dock

COSMIC supports multiple panel instances. The dock is just a panel anchored to
the bottom with different applets. Create a dock config at:
`~/.config/cosmic/com.system76.CosmicPanel.Dock/v1/config`

```ron
CosmicPanelConfig(
    anchor: Bottom,
    anchor_gap: true,
    layer: Top,
    keyboard_interactivity: None,
    size: L,
    name: "Dock",
    background: ThemeDefault(Some(0.8)),
    plugins_wings: Some(([], [])),
    plugins_center: Some([
        "com.system76.CosmicAppletAppMenu",
    ]),
    expand_plugins_center: false,
    opacity: 0.9,
    autohide: Some(AutoHide(
        wait_time: 1000,
        transition_time: 200,
        handle_size: 4,
    )),
)
```

Register the dock panel with the session by adding it to the panels list:
`~/.config/cosmic/com.system76.CosmicPanel/v1/panels`

```ron
["Panel", "Dock"]
```

### 68.4.3 Writing a Custom Applet

Custom panel applets are Rust crates that implement the `cosmic-applet` API.
This is the most complex ricing task in COSMIC — you are writing Rust code,
not editing a config file.

```bash
# Scaffold a new applet
cargo new --lib cosmic-applet-mycustom
cd cosmic-applet-mycustom
```

`Cargo.toml`:

```toml
[package]
name = "cosmic-applet-mycustom"
version = "0.1.0"
edition = "2021"

[dependencies]
cosmic = { git = "https://github.com/pop-os/libcosmic", features = ["applet"] }
tokio = { version = "1", features = ["full"] }

[[bin]]
name = "cosmic-applet-mycustom"
path = "src/main.rs"
```

`src/main.rs` (minimal applet that shows a label):

```rust
use cosmic::app::{Command, Core};
use cosmic::applet::CosmicAppletHelper;
use cosmic::iced::widget::text;
use cosmic::iced::Length;
use cosmic::{Application, Element, Theme};

struct MyApplet {
    core: Core,
}

#[derive(Debug, Clone)]
enum Message {}

impl cosmic::Application for MyApplet {
    type Executor = cosmic::executor::Default;
    type Flags = ();
    type Message = Message;
    const APP_ID: &'static str = "com.example.CosmicAppletMycustom";

    fn core(&self) -> &Core { &self.core }
    fn core_mut(&mut self) -> &mut Core { &mut self.core }

    fn init(core: Core, _flags: ()) -> (Self, Command<Message>) {
        (Self { core }, Command::none())
    }

    fn view(&self) -> Element<Message> {
        self.core
            .applet
            .icon_button("weather-clear-symbolic")
            .into()
    }

    fn update(&mut self, _message: Message) -> Command<Message> {
        Command::none()
    }
}

fn main() -> cosmic::iced::Result {
    cosmic::applet::run::<MyApplet>(true, ())
}
```

Build and install:

```bash
cargo build --release
sudo cp target/release/cosmic-applet-mycustom /usr/local/bin/
# Register the applet desktop file
mkdir -p ~/.local/share/applications
cat > ~/.local/share/applications/cosmic-applet-mycustom.desktop <<EOF
[Desktop Entry]
Name=My Custom Applet
Exec=/usr/local/bin/cosmic-applet-mycustom
Type=Application
NoDisplay=true
X-CosmicApplet=true
EOF
```

Then add `"com.example.CosmicAppletMycustom"` to the plugins list in the
panel config and restart `cosmic-panel`.

---

## 68.5 COSMIC Theming

COSMIC uses a design token system — high-level semantic color names that map
to concrete hex values at render time. This is similar in concept to CSS custom
properties or Material Design tokens, but implemented in Rust with type-checked
RON files.

### 68.5.1 Theme Files

Theme files live at `~/.local/share/themes/cosmic/` and have a `.ron`
extension. The built-in themes (including Dracula and Catppuccin presets) are
compiled into `cosmic-settings` but user themes override them at this path.

```bash
# List installed themes
ls ~/.local/share/themes/cosmic/

# Install Catppuccin Mocha
git clone https://github.com/catppuccin/cosmic /tmp/catppuccin-cosmic
cp /tmp/catppuccin-cosmic/themes/*.ron ~/.local/share/themes/cosmic/
```

A minimal custom theme file (`~/.local/share/themes/cosmic/mytheme.ron`):

```ron
CosmicTheme(
    name: "Mytheme",
    background: CosmicPalette(
        base: Srgba(0.102, 0.102, 0.149, 1.0),
        component: CosmicComponent(
            base: Srgba(0.141, 0.141, 0.196, 1.0),
            hover: Srgba(0.180, 0.180, 0.240, 1.0),
            pressed: Srgba(0.120, 0.120, 0.170, 1.0),
            selected: Srgba(0.200, 0.180, 0.280, 1.0),
            selected_text: Srgba(0.800, 0.800, 1.000, 1.0),
            focus: Srgba(0.490, 0.360, 0.800, 1.0),
            divider: Srgba(0.250, 0.250, 0.320, 1.0),
            on: Srgba(0.880, 0.880, 0.960, 1.0),
            disabled: Srgba(0.400, 0.400, 0.480, 1.0),
            on_disabled: Srgba(0.300, 0.300, 0.380, 1.0),
            border: Srgba(0.200, 0.200, 0.280, 1.0),
            disabled_border: Srgba(0.180, 0.180, 0.240, 1.0),
        ),
    ),
    primary: CosmicPalette(...),
    secondary: CosmicPalette(...),
    accent: Srgba(0.490, 0.360, 0.800, 1.0),
    accent_button: CosmicComponent(...),
    success: CosmicComponent(...),
    warning: CosmicComponent(...),
    destructive: CosmicComponent(...),
    corner_radii: CornerRadii(
        radius_0: [0.0, 0.0, 0.0, 0.0],
        radius_xs: [4.0, 4.0, 4.0, 4.0],
        radius_s: [8.0, 8.0, 8.0, 8.0],
        radius_m: [16.0, 16.0, 16.0, 16.0],
        radius_l: [32.0, 32.0, 32.0, 32.0],
        radius_xl: [160.0, 160.0, 160.0, 160.0],
    ),
    spacing: Spacing(
        space_none: 0,
        space_xxxs: 4,
        space_xxs: 8,
        space_xs: 12,
        space_s: 16,
        space_m: 24,
        space_l: 32,
        space_xl: 48,
        space_xxl: 64,
        space_xxxl: 128,
    ),
    font_size: 14,
    font_name: "Fira Sans",
    mono_font_name: "JetBrains Mono",
)
```

### 68.5.2 Applying Themes via Settings

```bash
# Apply theme from CLI (the cosmic-settings tool accepts subcommands)
cosmic-settings appearance theme set "Mytheme"

# Or directly edit the setting file
echo '"Mytheme"' > ~/.config/cosmic/com.system76.CosmicTheme.Mode.Dark/v1/theme_name
# Trigger reload
pkill -SIGHUP cosmic-settings
```

### 68.5.3 Cursor and Icon Themes

COSMIC respects standard XDG cursor and icon theme conventions:

```bash
# Install cursor theme
tar -xf Bibata-Modern-Classic.tar.gz -C ~/.local/share/icons/

# Set via ~/.config/gtk-3.0/settings.ini (COSMIC reads this for cursor)
mkdir -p ~/.config/gtk-3.0
cat > ~/.config/gtk-3.0/settings.ini <<EOF
[Settings]
gtk-cursor-theme-name=Bibata-Modern-Classic
gtk-cursor-theme-size=24
gtk-icon-theme-name=Papirus-Dark
EOF

# Also set in ~/.icons/default/index.theme for X cursor inheritance
mkdir -p ~/.icons/default
cat > ~/.icons/default/index.theme <<EOF
[Icon Theme]
Inherits=Bibata-Modern-Classic
EOF
```

---

## 68.6 App Toolkit: iced + libcosmic

All COSMIC applications are built with the `iced` Rust GUI framework, wrapped
by `libcosmic` which provides COSMIC-specific widgets, theming integration,
and the applet/settings page API. Understanding this stack is useful both for
building apps that fit natively into COSMIC and for contributing to the
ecosystem.

### 68.6.1 iced Overview

`iced` is an Elm-inspired GUI framework: applications are pure functions from
state to view, and state changes happen via messages dispatched through an
update function. There is no callback hell, no shared mutable state — just
`(state, message) -> state` and `state -> view`.

This architecture makes COSMIC apps highly testable and the UI code easy to
reason about. It also means COSMIC apps feel consistently structured, which
is why the design language is so coherent across components that were written
by different contributors.

### 68.6.2 Available COSMIC Applications

| App                  | Binary               | Description                        |
|----------------------|----------------------|------------------------------------|
| `cosmic-files`       | `cosmic-files`       | File manager with tabs, dual-pane  |
| `cosmic-term`        | `cosmic-term`        | GPU-accelerated terminal (wgpu)    |
| `cosmic-edit`        | `cosmic-edit`        | Text editor with syntax highlight  |
| `cosmic-settings`    | `cosmic-settings`    | Unified system settings hub        |
| `cosmic-launcher`    | `cosmic-launcher`    | App launcher (Super key)           |
| `cosmic-store`       | `cosmic-store`       | Flatpak/package store              |
| `cosmic-screenshot`  | `cosmic-screenshot`  | Screenshot and recording tool      |
| `cosmic-reader`      | `cosmic-reader`      | Document viewer (PDF, ePub)        |
| `cosmic-player`      | `cosmic-player`      | Media player (GStreamer backend)   |

Install individual apps on Arch:

```bash
paru -S cosmic-files cosmic-term cosmic-edit cosmic-store
```

### 68.6.3 Using cosmic-term

`cosmic-term` is notable for its GPU rendering via `wgpu` (the same renderer
used in `wgpu` game engines). Configuration is via its own settings panel, but
the config file is at:
`~/.config/cosmic/com.system76.CosmicTerm/v1/`

```bash
# Key config knobs:
cat ~/.config/cosmic/com.system76.CosmicTerm/v1/font_name
# "JetBrains Mono"

echo '"Monaspace Neon"' > ~/.config/cosmic/com.system76.CosmicTerm/v1/font_name
echo '13' > ~/.config/cosmic/com.system76.CosmicTerm/v1/font_size
echo 'true' > ~/.config/cosmic/com.system76.CosmicTerm/v1/use_bright_bold
```

---

## 68.7 COSMIC vs. the Alternatives

Choosing COSMIC as your primary Wayland compositor in 2025 is a calculated
bet: you trade ecosystem maturity for Rust-native code quality and a design
that has no GTK/Qt baggage. For ricing purposes the comparison breaks down
into three categories: customization ceiling, configuration ergonomics, and
community resources.

**Customization ceiling**: Hyprland has the highest ceiling today — its
`hyprland.conf` is Turing-complete, the plugin system is mature, and the
community has produced thousands of dots configurations. COSMIC's ceiling is
theoretically higher (write Rust, compile a custom applet, ship it) but the
tooling is newer and the documentation is thinner. KDE Plasma's ceiling is
broad but not deep — Plasma themes change colors and borders but the underlying
architecture is fixed.

**Configuration ergonomics**: COSMIC's RON files are more structured than
Hyprland's bespoke DSL and more discoverable than dconf GVariant values. But
they lack hot-reload for most settings (compositor restart required for keybind
changes). Hyprland's IPC (`hyprctl`) and live reload are faster for iteration.

**Community resources**: Check `/r/unixporn` tag distributions: Hyprland posts
dominate, COSMIC is gaining. The `#cosmic-desktop` channel on System76's
Discord is the fastest place to get help.

| Property            | COSMIC             | Hyprland           | KDE Plasma          |
|---------------------|--------------------|--------------------|---------------------|
| Config hot-reload   | Partial (some daemons) | Full (`hyprctl reload`) | Full            |
| Plugin API          | Rust crate         | C++/Rust plugin    | KWin scripts / C++  |
| Wallpaper daemon    | `cosmic-bg`        | `hyprpaper`/`swww` | built-in            |
| Screenshot          | `cosmic-screenshot`| `grim`/`hyprshot`  | Spectacle           |
| Screen lock         | `cosmic-greeter`   | `hyprlock`         | kscreenlocker        |
| Notifications       | `cosmic-notifications` | `mako`/`dunst` | Plasma/Elisa        |
| App launcher        | `cosmic-launcher`  | `rofi`/`wofi`      | KRunner             |
| System tray         | Panel applet       | `nm-applet` + wlr  | Plasma systray      |

---

## 68.8 Multi-Monitor and Fractional Scaling

COSMIC implements `wp-fractional-scale-v1`, the Wayland protocol for
sub-integer display scaling. This works without the screen capture degradation
seen in older scale=2 approaches.

### 68.8.1 Configuring Displays

Display configuration is managed via `cosmic-settings` → Displays, or by
editing:
`~/.config/cosmic/com.system76.CosmicComp/v1/outputs`

```ron
{
    "DP-1": OutputConfig(
        mode: Some(((2560, 1440), Some(144000))),
        position: (0, 0),
        scale: 1.0,
        transform: Normal,
        vrr: false,
    ),
    "HDMI-A-1": OutputConfig(
        mode: Some(((1920, 1080), Some(60000))),
        position: (2560, 180),
        scale: 1.0,
        transform: Normal,
        vrr: false,
    ),
}
```

For a HiDPI 4K display at 150% scaling:

```ron
"DP-2": OutputConfig(
    mode: Some(((3840, 2160), Some(60000))),
    position: (0, 0),
    scale: 1.5,
    transform: Normal,
    vrr: false,
),
```

### 68.8.2 Variable Refresh Rate (VRR/Adaptive Sync)

```ron
"DP-1": OutputConfig(
    mode: Some(((2560, 1440), Some(165000))),
    position: (0, 0),
    scale: 1.0,
    transform: Normal,
    vrr: true,   # Enable VRR/FreeSync/G-Sync Compatible
),
```

VRR requires kernel support (`drm.use_vgaswitcheroo=0` is not needed for VRR,
but ensure your kernel is 6.1+) and the display must support Adaptive Sync.
For NVIDIA, VRR support in COSMIC requires driver 550+ and the `nvidia-drm.modeset=1`
kernel parameter (see Section 68.9.3).

---

## 68.9 GPU Considerations

### 68.9.1 AMD (Recommended)

COSMIC on AMD GPUs works out of the box with the in-tree `amdgpu` kernel driver.
No additional configuration is required. For best performance:

```bash
# Verify amdgpu is loaded
lsmod | grep amdgpu

# Check DRM render node
ls /dev/dri/

# Ensure hardware video acceleration (VA-API)
sudo pacman -S libva-mesa-driver mesa-vdpau

# For COSMIC apps using wgpu (cosmic-term, etc.):
export WGPU_BACKEND=vulkan  # explicit Vulkan backend
```

### 68.9.2 Intel (Integrated and Arc)

Intel integrated graphics works well. For Arc discrete GPUs, ensure kernel 6.2+
and updated Mesa (23.1+) for full performance:

```bash
# Check i915 / xe driver status
lsmod | grep -E "i915|xe"

# For Intel Arc (Xe kernel driver, 6.8+):
# Add to /etc/modprobe.d/i915.conf:
echo "options xe force_probe=*" | sudo tee /etc/modprobe.d/xe.conf
```

### 68.9.3 NVIDIA

NVIDIA support in COSMIC (and Smithay-based compositors generally) requires
careful setup. As of 2025, driver 555+ with explicit sync patches provides
good stability.

```bash
# Required kernel parameters (add to bootloader):
# GRUB example — edit /etc/default/grub:
GRUB_CMDLINE_LINUX_DEFAULT="quiet nvidia-drm.modeset=1 nvidia-drm.fbdev=1"
sudo grub-mkconfig -o /boot/grub/grub.cfg

# Required environment variables for Wayland NVIDIA:
# Add to /etc/environment or ~/.config/cosmic/com.system76.CosmicSession/v1/env
LIBVA_DRIVER_NAME=nvidia
GBM_BACKEND=nvidia-drm
__GLX_VENDOR_LIBRARY_NAME=nvidia
WLR_NO_HARDWARE_CURSORS=1
NVD_BACKEND=direct

# For cosmic-session to pick up env vars, create:
mkdir -p ~/.config/environment.d
cat > ~/.config/environment.d/nvidia-wayland.conf <<EOF
LIBVA_DRIVER_NAME=nvidia
GBM_BACKEND=nvidia-drm
__GLX_VENDOR_LIBRARY_NAME=nvidia
WLR_NO_HARDWARE_CURSORS=1
NVD_BACKEND=direct
EOF
```

---

## 68.10 Status and Roadmap (2025–2026)

COSMIC entered Beta in late 2024 and is targeted for a 1.0 stable release
with Pop!_OS 25.04. The following table summarizes feature status as of
mid-2025:

| Feature                   | Status (mid-2025)         | Notes                                    |
|---------------------------|---------------------------|------------------------------------------|
| Core Wayland protocols    | Complete                  | xdg-shell, layer-shell, output mgmt      |
| Autotiling                | Stable                    | Per-workspace, drag to adjust splits     |
| Fractional scaling        | Stable                    | wp-fractional-scale-v1                   |
| Multi-monitor             | Stable                    | Hot-plug, different scales per monitor   |
| VRR / Adaptive Sync       | Stable (AMD), Beta (NVIDIA) | Requires driver 550+ on NVIDIA         |
| HDR                       | In progress               | Planned for 1.0                          |
| NVIDIA explicit sync      | Beta                      | Driver 555+ required                     |
| Screen recording          | Beta                      | Via cosmic-screenshot                    |
| Touchpad gestures         | Stable                    | 3/4-finger swipe for workspace switch    |
| Tablet / stylus           | Beta                      | Basic pressure sensitivity               |
| Accessibility             | In progress               | AT-SPI2 integration                      |
| Flatpak portal            | Stable                    | xdg-desktop-portal-cosmic                |
| Custom applets (Rust)     | Stable API                | libcosmic applet API                     |
| Session restore           | In progress               | Planned                                  |

---

## 68.11 Troubleshooting

### Compositor Does Not Start / Black Screen

```bash
# Check cosmic-comp logs
journalctl --user -u cosmic-session --since "5 minutes ago"
journalctl --user -u cosmic-comp --since "5 minutes ago"

# Run cosmic-comp directly from a TTY for verbose output
RUST_LOG=cosmic_comp=debug cosmic-comp 2>&1 | tee /tmp/cosmic-debug.log

# Check DRM/KMS status
dmesg | grep -E "drm|kms|fbdev" | tail -30
```

### Settings Changes Not Taking Effect

```bash
# Most COSMIC settings require restarting the affected daemon:
pkill cosmic-settings && cosmic-settings &   # not usually needed
pkill cosmic-panel && cosmic-panel &          # restart panel after config change

# For compositor settings (keybindings, gaps, outputs):
pkill -SIGUSR1 cosmic-comp   # soft reload (not all settings)
# Or restart the full session:
loginctl terminate-session $XDG_SESSION_ID
```

### Panel Applet Not Appearing

```bash
# Verify applet binary is in PATH and executable
which cosmic-applet-mycustom
cosmic-applet-mycustom --version

# Check the desktop file is valid
desktop-file-validate ~/.local/share/applications/cosmic-applet-mycustom.desktop

# Verify panel config lists the applet ID
cat ~/.config/cosmic/com.system76.CosmicPanel.Panel/v1/config | grep CosmicApplet

# Restart the panel
pkill cosmic-panel
cosmic-panel &
journalctl --user -f -u cosmic-panel   # watch for errors
```

### XWayland Apps Crash or Freeze

```bash
# Check XWayland is running
pgrep Xwayland
# If missing:
sudo pacman -S xorg-xwayland

# Force a specific app to use XWayland
WAYLAND_DISPLAY="" GDK_BACKEND=x11 myapp

# Disable XWayland entirely if not needed (saves ~20MB RAM):
# Add to ~/.config/cosmic/com.system76.CosmicComp/v1/xwayland
echo 'false' > ~/.config/cosmic/com.system76.CosmicComp/v1/xwayland
```

### NVIDIA: Screen Tearing or Blank Output

```bash
# Confirm modeset is enabled
cat /sys/module/nvidia_drm/parameters/modeset
# Should output: Y

# If N, rebuild initramfs with the parameter set:
sudo nano /etc/modprobe.d/nvidia.conf
# Add: options nvidia-drm modeset=1 fbdev=1
sudo mkinitcpio -P   # Arch
sudo dracut --force  # Fedora/openSUSE

# Check explicit sync support (driver 555+)
nvidia-smi | grep "Driver Version"
```

### Font Rendering Issues

```bash
# COSMIC inherits fontconfig. Ensure fontconfig cache is current:
fc-cache -fv

# For subpixel rendering (LCD):
mkdir -p ~/.config/fontconfig
cat > ~/.config/fontconfig/fonts.conf <<EOF
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>
  <match target="font">
    <edit name="hinting" mode="assign"><bool>true</bool></edit>
    <edit name="hintstyle" mode="assign"><const>hintslight</const></edit>
    <edit name="antialias" mode="assign"><bool>true</bool></edit>
    <edit name="rgba" mode="assign"><const>rgb</const></edit>
    <edit name="lcdfilter" mode="assign"><const>lcddefault</const></edit>
  </match>
</fontconfig>
EOF
fc-cache -fv
```

---

## Cross-References

- **Ch 53** — Session startup and `systemd --user` unit integration: how to
  autostart services before or after `cosmic-session` targets
- **Ch 55** — Wayland protocols deep dive: `wlr-layer-shell` used by
  `cosmic-panel`, `xdg-output` used by multi-monitor layout
- **Ch 57** — Notification daemons: `cosmic-notifications` vs. `mako` vs.
  `dunst` on a COSMIC session
- **Ch 60** — Hyprland chapter for comparison of autotiling implementation
  differences
- **Ch 72** — Theming deep dive: RON format in depth, design token systems,
  and generating palettes from a base color
- **Ch 75** — NVIDIA on Wayland: explicit sync, `nvidia-drm.modeset`, and
  per-compositor notes including COSMIC

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
