# Appendix G — Glossary of Terms

Terms used throughout this book, alphabetically ordered.

---

## Contents

- [A](#a)
- [B](#b)
- [C](#c)
- [D](#d)
- [E](#e)
- [F](#f)
- [G](#g)
- [H](#h)
- [I](#i)
- [J](#j)
- [K](#k)
- [L](#l)
- [M](#m)
- [N](#n)
- [O](#o)
- [P](#p)
- [Q](#q)
- [R](#r)
- [S](#s)
- [T](#t)
- [U](#u)
- [V](#v)
- [W](#w)
- [X](#x)
- [Y](#y)
- [Z](#z)

---


## A

**A2DP** (Advanced Audio Distribution Profile)
Bluetooth audio profile for high-quality stereo music playback. Does not include
a microphone channel. Contrast with HFP. See Ch 81.

**ACO** (AMD Compiler Optimised)
The current Mesa shader compiler backend for AMD GPUs, replacing the older LLVM
backend. Produces significantly faster OpenGL and Vulkan shader compilation.

**ANV**
Intel's Mesa Vulkan driver for Intel Gen 8+ integrated and discrete GPUs.
Equivalent to AMD's RADV. Supports explicit sync and Venus (Vulkan virgl).

**AGS / Astal**
A TypeScript/JavaScript framework for building Wayland shell components,
originally built as "Ags" then rebranded Astal. Uses GJS (GNOME JavaScript).
Alternative to Quickshell and Waybar. See Ch 26.

**at-spi2** (Assistive Technology Service Provider Interface 2)
The Linux accessibility bus. Screen readers (Orca) and assistive tools use it
to query the UI tree. Required for GNOME accessibility features. See Ch 44.

---

## B

**BlueZ**
The official Linux Bluetooth protocol stack. All Bluetooth on Linux goes through
BlueZ and its D-Bus API (`org.bluez`). See Ch 81.

**bwrap** (Bubblewrap)
A low-level sandboxing primitive that creates Linux namespaces. Used internally
by Flatpak. Also exposed directly via the `bubblejail` tool. See Ch 85.

---

## C

**cage**
A minimal Wayland compositor that runs a single application fullscreen, designed
for kiosk and embedded use. See Ch 97.

**Catppuccin**
A pastel colour palette family (Latte, Frappé, Macchiato, Mocha) that became
the most popular ricing colour scheme in 2023–2026. See Ch 34.

**chezmoi**
A dotfile manager that supports templating, secrets management, and `run_once`
scripts. More powerful than GNU Stow for complex multi-machine setups. See Ch 55.

**cliphist**
A clipboard history daemon for Wayland. Stores clipboard entries persistently
and integrates with rofi/fuzzel for selection. See Ch 32.

**colord**
The D-Bus daemon that manages ICC colour profiles and display device
associations on Linux. See Ch 94.

**COSMIC**
System76's custom Rust desktop environment, built on Smithay/iced. Ships on
Pop!_OS; also available on Arch via AUR. See Ch 68.

**CUPS** (Common Unix Printing System)
The standard Linux printing daemon. See Ch 82.

---

## D

**D-Bus**
The standard Linux desktop IPC mechanism. Two buses: session (per-user,
notifications/MPRIS/portals) and system (Bluetooth/NetworkManager/logind).
See Ch 93.

**DMA-BUF** (Direct Memory Access Buffer)
A Linux kernel mechanism for sharing GPU memory buffers between processes
without copying. Critical for zero-copy video decode and Wayland buffer sharing.
See Ch 63.

**DRM** (Direct Rendering Manager)
The Linux kernel subsystem for GPU access. Exposes `/dev/dri/card*` and
`/dev/dri/renderD*` devices. All Wayland compositors use DRM/KMS directly.
See Ch 63.

**dwl**
A minimal Wayland compositor based on dwm's patching philosophy. Written in C,
configured by editing source code. See Ch 13.

---

## E

**EGL**
The Khronos API that connects OpenGL/Vulkan to the native windowing system
(or DRM for compositors). Wayland compositors use EGL to create rendering
contexts. See Ch 63.

**exec-once**
Hyprland's config directive for launching processes at compositor startup.
Equivalent to sway's `exec` but guaranteed to run only once per session. See Ch 53.

**explicit sync**
A Wayland protocol (`linux-drm-syncobj-v1`) that allows applications and the
compositor to synchronize GPU work using DRM timeline fences, eliminating
tearing without implicit synchronization overhead. See Ch 63.

**eww** (Elkowar's Wacky Widgets)
A Wayland widget system configured in the Yuck language. Can create bars, docks,
overlays, and desktop widgets. See Ch 26.

---

## F

**Flatpak**
A distribution-agnostic Linux application sandboxing and packaging system.
Sandboxes use bubblewrap; host resource access goes through portals. See Ch 52, 85.

**fontconfig**
The library and configuration system that manages font discovery, fallback
chains, and rendering parameters (hinting, rgba, lcdfilter) on Linux. See Ch 87.

**foot**
A fast, minimal Wayland-native terminal emulator written in C. Features a
daemon mode (`footclient`) for near-instant startup. See Ch 50.

**Fcitx5**
The recommended input method framework for Wayland. Implements the
`zwp_text_input_v3` protocol. Supports Chinese (Pinyin/Cangjie), Japanese
(Mozc/Anthy), Korean (Hangul), and many other input methods. See Ch 79.

**fuzzel**
A Wayland-native application launcher with a minimal design. Uses xdg-desktop
entries. Configured via `~/.config/fuzzel/fuzzel.ini`. See Ch 28.

---

## G

**GBM** (Generic Buffer Management)
A Mesa library for allocating GPU-memory-backed DRM buffers used as rendering
targets by Wayland compositors. See Ch 63.

**gamescope**
Valve's embedded Wayland compositor designed for running games. Supports FSR
upscaling, VRR, HDR, and nested Wayland mode. See Ch 42.

**Ghostty**
A fast GPU-accelerated terminal emulator written in Zig with a GTK4 backend.
Native Wayland support. See Ch 50.

**greetd**
A minimal display manager / session greeter daemon. Pairs with ReGreet (GTK),
tuigreet (TUI), or custom greeters. See Ch 54.

**grim**
A Wayland screenshot tool using the `wlr-screencopy` protocol. Outputs PNG/JPEG
to a file or stdout. Core tool for screenshot workflows. See Ch 31.

**Gruvbox**
A retro-style colour palette with warm, earthy tones. Popular alternative to
Catppuccin. See Ch 34.

---

## H

**HFP** (Hands-Free Profile)
Bluetooth audio profile that includes both playback and microphone. Lower
audio quality than A2DP. Required for voice calls. See Ch 81.

**HDR** (High Dynamic Range)
Display technology supporting luminance from ~0.001 to 10,000 nits and wider
colour gamuts. Wayland protocol: `wp-color-management-v1`. Production-ready on
KDE Plasma 6.4+. See Ch 33, 42, 94.

**Home Manager**
A NixOS/Nix module system for declaratively managing user configuration files,
programs, and services. See Ch 39.

**hyprctl**
The Hyprland IPC command-line tool. Can query compositor state, dispatch
actions, change config values at runtime, and manage plugins. See Ch 8, Appendix E.

**Hyprland**
A dynamic tiling Wayland compositor built on wlroots (via the Aquamarine
backend). Known for animations, a rich plugin system (hyprpm), and active
development. See Ch 8.

**hyprlock**
Hyprland's official screen locker. Implements `ext-session-lock-v1`. Configured
in `~/.config/hypr/hyprlock.conf`. See Ch 30.

**hypridle**
Hyprland's idle daemon. Triggers actions (dim screen, lock, suspend) after
configurable idle timeouts. See Ch 30.

**hyprpaper**
Hyprland's wallpaper daemon. Supports per-monitor wallpapers and IPC-based
hot-swapping. See Ch 27.

**hyprcursor**
Hyprland's custom cursor theme format. SVG-based, supports rotation and
fractional scaling. See Ch 37.

**hyprpm**
Hyprland's plugin manager. Adds and builds plugins from GitHub repositories
against the installed Hyprland headers. See Ch 89.

---

## I

**IBus** (Intelligent Input Bus)
An input method framework for Linux. Largely superseded by Fcitx5 for Wayland
due to incomplete `zwp_text_input_v3` support. See Ch 79.

**ICC profile**
A binary file that characterises a display's colour behaviour, used by colour
management systems to correct colour output. See Ch 94.

**IPC** (Inter-Process Communication)
Mechanism for processes to communicate. Hyprland uses Unix sockets; Sway uses
the i3/sway IPC protocol; D-Bus and Varlink are the system-level IPC mechanisms.

**iio-sensor-proxy**
A D-Bus service that exposes hardware sensors (accelerometer, orientation) to
applications. Used for auto-screen-rotation on convertibles. See Ch 90.

---

## J

**Jay**
A Wayland compositor written in Rust using Smithay. Features a unique input
focus model and scripted configuration. See Ch 13.

**journalctl**
The systemd journal query tool. Under the hood it calls `io.systemd.Journal`
via Varlink. See Ch 93, 98.

---

## K

**kanshi**
A display configuration daemon that applies monitor profiles based on connected
outputs. Equivalent to autorandr for Wayland. See Ch 33.

**KMS** (Kernel Mode Setting)
The Linux kernel component that controls display hardware (resolution, refresh,
output routing). Works in conjunction with DRM. See Ch 63.

**Kitty**
A GPU-accelerated terminal emulator featuring the Kitty Graphics Protocol
(inline images), kittens (scripting framework), and session management. See Ch 50.

**KWin**
KDE's window manager and Wayland compositor. Powers KDE Plasma. Supports HDR,
VRR, fractional scaling, and the `wp-security-context-v1` protocol. See Ch 66.

**Kvantum**
An SVG-based Qt theme engine. Allows pixel-perfect Qt app theming using vector
theme files. See Ch 36.

---

## L

**labwc**
An OpenBox-compatible Wayland compositor built on wlroots. Stacking layout.
Minimal and stable. See Ch 12.

**lact** (Linux AMD Control Tool)
A GTK4 Wayland-native GUI for AMD GPU monitoring, overclocking, fan curves,
and power management. Requires the `lactd` daemon. See Ch 95.

**layer-shell** (`zwlr-layer-shell-v1`)
The Wayland protocol extension that lets applications create surfaces at
specific z-layers (Background, Bottom, Top, Overlay) anchored to screen edges.
Used by status bars, overlays, lock screens, and wallpaper daemons. See Ch 3.

**libinput**
The input handling library used by wlroots and most Wayland compositors.
Handles touchpad gestures, pointer acceleration, tablet input. See Ch 43.

**libwayland**
The reference implementation of the Wayland protocol in C. Provides
`libwayland-client` (for applications) and `libwayland-server` (for
compositors). See Ch 4.

**Looking Glass**
A tool for displaying a VM's GPU framebuffer on the host screen via shared
memory (IVSHMEM/KVMFR), enabling near-native VM display performance. See Ch 84.

---

## M

**mako**
A lightweight Wayland notification daemon. Configured via
`~/.config/mako/config` with criteria-based rules. See Ch 29.

**matugen**
A colour palette generator that uses Material You (Material Design 3) dynamic
colour algorithms to derive a full palette from a wallpaper image. See Ch 38.

**Mesa**
The open-source OpenGL/Vulkan/etc. implementation for Linux. Contains all
AMD (RADV), Intel (ANV/iris), and software (llvmpipe/lavapipe) drivers.
See Ch 63.

**mpv**
A versatile media player with deep Wayland support: VA-API hardware decode,
custom GLSL shaders (Anime4K, FSRCNNX), MPRIS integration, and `mpvpaper`
for video wallpapers. See Ch 72.

**MPRIS** (Media Player Remote Interfacing Specification)
A D-Bus interface standard for controlling media players. Exposed as
`org.mpris.MediaPlayer2.*`. Used by Quickshell's `MprisController`. See Ch 22.

**Mutter**
GNOME's Wayland compositor. Powers GNOME Shell. Implements
`wp-security-context-v1` since GNOME 49.2. See Ch 67.

---

## N

**niri**
A Wayland compositor with a scrollable column layout. Built on Smithay/Rust.
Configured in KDL. See Ch 11.

**Nord**
A cool-toned, arctic-inspired colour palette. Popular for minimalist ricing.
See Ch 34.

**NixOS**
A Linux distribution based on the Nix package manager. Fully declarative and
reproducible. Excellent for ricing: entire desktop environments can be
version-controlled. See Ch 39.

**nvtop**
A terminal-based GPU monitor supporting NVIDIA, AMD, Intel, and Apple Silicon
in a unified TUI. See Ch 95.

---

## O

**OBS** (OBS Studio)
Open Broadcaster Software. On Wayland, uses PipeWire for screen capture via
the screencast portal. See Ch 31, 61.

**Omarchy**
DHH's (David Heinemeier Hansson) opinionated Arch Linux + Hyprland setup,
used at 37signals (Basecamp/HEY). Not a distro — Arch + dotfiles + scripts.
See Ch 62.

**OpenTabletDriver**
A cross-platform open-source graphics tablet driver. Supports Huion, XP-Pen,
Gaomon, and some Wacom tablets not well-served by the kernel driver. See Ch 90.

---

## P

**PanelWindow**
The Quickshell type for creating layer-shell surfaces (bars, overlays, docks).
Wraps `zwlr-layer-shell-v1`. See Ch 17.

**PipeWire**
The modern Linux audio (and video) server. Replaces PulseAudio and JACK.
Handles screen recording capture via the PipeWire camera/screencast API.
See Ch 56.

**Plymouth**
The Linux boot splash daemon. Provides themed graphical boot screens.
Integrates with mkinitcpio on Arch. See Ch 77.

**polkit** (PolicyKit)
An authorisation framework that allows unprivileged processes to request
privileged actions from authorised helpers. Many GUI operations (network
management, Bluetooth, mounting) require a running polkit agent. See Ch 71.

**postmarketOS**
A Linux distribution based on Alpine Linux targeting mobile devices (phones,
tablets). Primary platform for Phosh and Sxmo. See Ch 97.

**pyprland**
A Python daemon for Hyprland that provides high-level plugins: scratchpads,
expose, workspace automation, per-workspace wallpaper. See Ch 96.

**pywal**
A tool that extracts a colour palette from a wallpaper image and applies it
to terminals, CSS, config templates, etc. via a template system. See Ch 38.

---

## Q

**QML** (Qt Meta Language / Qt Modeling Language)
A declarative UI language used by Qt. Quickshell configurations are written
in QML. See Ch 16.

**qt5ct / qt6ct**
Standalone Qt theme configuration tools for non-KDE environments. Set the
application style, icon theme, and fonts for Qt 5 and Qt 6 apps. See Ch 36.

**Quickshell**
A Wayland shell framework built on QML/QtQuick. The primary subject of Part III
of this book. Provides layer-shell windows, Hyprland IPC, PipeWire, MPRIS,
system tray, and more. See Ch 15–25.

---

## R

**RADV**
AMD's Mesa Vulkan driver. Open source, high-performance, supports all features
needed for Wayland including explicit sync, Venus, and DMA-BUF. See Ch 63.

**rice**
Customising a Linux desktop for aesthetic effect. Derived from the automotive
tuning culture ("Race Inspired Cosmetic Enhancements"). A "rice" is a configured
desktop; to "rice" is to configure it.

**River**
A Wayland compositor with a tag-based window management model. Written in Zig.
Configured entirely via `riverctl` commands (usually in a shell script). See Ch 10.

**rofi**
An application launcher/menu that has a Wayland fork (`rofi-wayland`). Highly
themeable with CSS-like configuration. See Ch 28.

---

## S

**SANE** (Scanner Access Now Easy)
The standard Linux scanning framework. `sane-airscan` adds support for modern
IPP Scan/eSCL network scanners. See Ch 82.

**SDDM** (Simple Desktop Display Manager)
The display manager used by KDE and Hyprland setups. QML-based; supports
Catppuccin and other custom themes. See Ch 54.

**slurp**
A Wayland region selection tool. Used with grim for interactive screenshot
cropping. See Ch 31.

**Smithay**
A Rust compositor framework (library). Used by Niri, COSMIC, Jay, and others
as an alternative to wlroots. See Ch 48.

**socat**
A versatile Unix socket relay tool. Used to communicate directly with Wayland
compositors' IPC sockets and Varlink services. See Ch 88, 98.

**Starship**
A cross-shell prompt framework written in Rust. Configured in TOML, supports
all shells, extensive module system. See Ch 51.

**stow** (GNU Stow)
A symlink farm manager. Used for dotfile management by symlinking files from
a central repository to their target locations. See Ch 55.

**swww**
A wallpaper daemon for wlroots compositors with animated transitions (fade,
wipe, grow, etc.). See Ch 27.

**swaync** (Sway Notification Center)
A notification daemon with a full notification center sidebar. Compatible with
Hyprland and Sway. See Ch 29.

**Stylix**
A NixOS/Home Manager module that auto-themes 50+ applications from a single
wallpaper using base16 colour schemes. See Ch 40.

---

## T

**ToplevelManager** (`zwlr-foreign-toplevel-management-v1`)
A Wayland protocol that exposes running windows (toplevels) to shell
components. Used by Quickshell's `ToplevelManager` for taskbars. See Ch 19.

**Tokyo Night**
A dark purple/blue colour palette inspired by the Tokyo night skyline. Popular
for Neovim and desktop ricing. See Ch 34.

---

## U

**UPower**
A D-Bus service that provides battery and power supply information. Used by
Quickshell's `UPowerDevice` type and Waybar's battery module. See Ch 22.

---

## V

**VA-API** (Video Acceleration API)
The Linux API for hardware-accelerated video decode/encode. AMD and Intel iGPUs
support it well via Mesa. See Ch 63, 72.

**Varlink**
A typed, socket-based IPC protocol developed alongside systemd. Uses
newline-delimited JSON framing. Used by `io.systemd.*` services. See Ch 98.

**Venus**
The Vulkan protocol extension for VirtIO-GPU. Forwards Vulkan calls from a
VM guest to the host GPU. Merged into QEMU 9.2.0 (December 2024). See Ch 84.

**VFR** (Variable Frame Rate)
`misc.vfr = true` in Hyprland config. Lets the compositor skip rendering frames
when nothing changes, significantly reducing GPU and CPU usage on battery. The
single most important power-saving setting in Hyprland. See Ch 78, Appendix E.

**VFIO** (Virtual Function I/O)
Linux kernel mechanism for passing PCI devices (typically GPUs) directly to
virtual machines. Used for GPU passthrough in QEMU/KVM. See Ch 84.

**virgl** (VirGL)
A virtual GPU device that translates OpenGL calls from a VM guest to the host's
Mesa OpenGL implementation. Enables 3D-accelerated Wayland compositors inside
VMs. See Ch 84.

**VRR** (Variable Refresh Rate)
Display technology (FreeSync/G-Sync) where the monitor refresh rate adapts to
the GPU's output rate, eliminating tearing. Wayland native support since
wlroots 0.15. See Ch 33, 42.

---

## W

**Wayland**
A display server protocol that replaces X11. A Wayland compositor handles both
compositing and display server roles. See Ch 1–3.

**Waybar**
The most popular Wayland status bar. JSON+CSS configuration, extensive module
library, layer-shell integration. See Ch 26.

**wayland-scanner**
A code generator that reads Wayland XML protocol definitions and generates C
header and implementation files for both client and server sides. See Ch 4, 46.

**WezTerm**
A GPU-accelerated terminal with Lua scripting, built-in multiplexer, and
native Wayland support. See Ch 50.

**wev**
A Wayland event viewer. Opens a test window and prints all input events (key,
mouse, touch, stylus) in real time. Essential for debugging keybinds. See Ch 43.

**WirePlumber**
The session manager for PipeWire. Manages device routing, policy, and
permission. Scripted in Lua. See Ch 56.

**wl-clipboard** (`wl-copy` / `wl-paste`)
The standard Wayland clipboard command-line tools. See Ch 32.

**wlr-randr**
A Wayland output management tool for wlroots compositors. Gets/sets monitor
resolution, refresh rate, scale, and transform. See Ch 33.

**wlroots**
A modular compositor library in C. The foundation of Sway, Hyprland (via
Aquamarine), River, labwc, and many others. See Ch 5.

**wp-fractional-scale-v1**
A Wayland protocol extension for fractional display scaling (e.g., 1.25×,
1.5×). Used by compositors that support non-integer scaling. See Ch 41.

**wp-security-context-v1**
A Wayland protocol that lets sandboxed clients (Flatpak) be identified and
restricted by the compositor. Implemented by all major compositors as of
2025. See Ch 65, 85.

**wtype**
A Wayland keyboard input injection tool using `zwp_virtual_keyboard_manager_v1`.
Works on wlroots compositors (Hyprland, Sway, River). See Ch 86.

---

## X

**XDG** (Cross-Desktop Group)
A freedesktop.org standards body. Defines many Linux desktop conventions:
`XDG_CONFIG_HOME`, base directories, desktop entry files, MIME associations,
autostart, portals. See Ch 52, 91.

**xdg-desktop-portal**
A D-Bus broker that mediates sandboxed app access to host resources: files,
screen capture, clipboard, printing. Backend implementations (hyprland, wlr,
gnome, kde) implement the portals. See Ch 52.

**xdg-open**
A command that opens a file or URL with the appropriate default application,
as determined by `mimeapps.list`. See Ch 91.

**XWayland**
An X11 compatibility layer that runs as a Wayland client, providing a
backward-compatible X server for legacy X11 applications. See Ch 64.

---

## Y

**Yazi**
A terminal file manager written in Rust with the Kitty Graphics Protocol for
image previews, extensive plugin system, and shell integrations. See Ch 69.

**ydotool**
A compositor-agnostic input injection tool that writes to `/dev/uinput`.
Requires the `ydotoold` daemon. See Ch 86.

---

## Z

**Zink**
A Mesa OpenGL-over-Vulkan translation layer. Allows applications using OpenGL
to run on Vulkan drivers. Useful in VMs when only Venus (Vulkan) is available.

**ZSH**
The Z Shell. Popular with oh-my-zsh and Zinit for plugin management and
prompt customisation. Pairs with Starship for cross-shell prompts. See Ch 51.

**zwlr** prefix
Namespace for wlroots-specific Wayland protocol extensions
(`zwlr-layer-shell-v1`, `zwlr-screencopy-v1`, etc.). "z" indicates unstable.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
