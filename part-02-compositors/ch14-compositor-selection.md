# Chapter 14 — Choosing Your Compositor: Decision Framework

This chapter provides a rigorous, opinionated framework for selecting a Wayland compositor that
fits your hardware, workflow, and aesthetic goals. Rather than cataloguing every project that
has ever called itself a compositor, the focus is on the compositors that have active communities,
real ricing ecosystems, and meaningful differentiation. By the end of the chapter you will
understand the trade-offs well enough to make a confident choice — and to migrate later without
starting from scratch.

See Ch 15 for deep-dive Hyprland configuration, Ch 16 for Sway/i3-inspired tiling, Ch 22 for
Niri scrollable workspaces, and Ch 53 for session startup and display manager integration.

---

## Contents

- [14.1 Decision Criteria](#141-decision-criteria)
- [14.2 The NVIDIA Question](#142-the-nvidia-question)
- [14.3 Full Comparison Matrix](#143-full-comparison-matrix)
- [14.4 Recommended Starting Points](#144-recommended-starting-points)
- [14.5 Migration Paths](#145-migration-paths)
- [14.6 Ecosystem Tools That Are Compositor-Agnostic](#146-ecosystem-tools-that-are-compositor-agnostic)
- [14.7 Performance Profiling Your Compositor Choice](#147-performance-profiling-your-compositor-choice)
- [14.8 Troubleshooting](#148-troubleshooting)

---


## 14.1 Decision Criteria

Choosing a compositor is a multi-dimensional decision. The five axes that matter most are
workflow, hardware, aesthetics, configuration style, and community size. Getting one axis wrong
is recoverable; getting two or more wrong means you will spend weeks fighting your environment
instead of using it.

**Workflow** is the primary axis. Tiling-first compositors (Sway, River, Hyprland) reward
keyboard-driven, many-window workflows common in software development and terminal-heavy use.
Stacking compositors (labwc, KWin, COSMIC) match the muscle memory of macOS or Windows users
making a first Linux transition. Scrollable-column compositors (Niri) suit wide-monitor setups
where horizontal space is abundant and vertical real estate is precious. Plugin-driven compositors
(Wayfire) suit users whose primary satisfaction comes from visual experimentation.

**Hardware** constraints narrow the field sharply. Older or low-end integrated graphics (Intel
HD 4000 era, ARM Mali) work reliably with software-rendered compositors and avoid features such
as HDR or VRR that require modern display pipelines. Mid-range discrete GPUs (AMD RX 5000+,
Intel Arc) support every compositor without caveats. NVIDIA GPUs require special attention (see
Section 14.2). Laptop users on battery must weigh compositor CPU/GPU overhead: Sway has the
lowest steady-state overhead of the major tiling compositors; KWin's compositing pipeline costs
more but is well-tuned for power management under Plasma.

**Aesthetic goals** split users into two camps: those who want zero visual distraction (Sway,
River, labwc with a stripped config) and those who treat the desktop as a canvas (Hyprland,
Wayfire, KWin with fancy effects). Animation speed and quality correlate strongly with GPU load
and therefore battery life. Hyprland's default bezier curves are beautiful but add measurable
frame time on a 60 Hz panel with a discrete GPU under moderate load; disabling them halves
the overhead immediately.

**Config style preference** determines long-term maintainability. File-based configs (Sway's
`config` in i3 syntax, Hyprland's `hyprland.conf` in its own hyprlang (custom DSL), Niri's KDL) are
Git-friendly and reproduce identically on a new machine via a dotfiles repo. GUI-first configs
(KWin via System Settings, COSMIC via its own settings app) reduce the learning cliff but are
harder to automate with `home-manager` or `chezmoi`. Scriptable runtime configs (River's
`riverctl` commands executed from a shell init script, Sway's IPC via `swaymsg`) integrate
natively with shell automation.

**Community and ecosystem** determines how quickly you can solve problems and how large the
dotfiles library is to learn from. As of mid-2025, Hyprland has the largest active ricing
community on GitHub and r/unixporn by a wide margin. Sway has the deepest documentation and
the longest history. KDE/KWin has by far the largest overall user base and corporate backing.
River and Niri have small but high-signal communities with thoughtful design cultures.

---

## 14.2 The NVIDIA Question

NVIDIA support under Wayland has been a recurring friction point since 2019 and deserves its
own section because the failure modes are silent and the fixes are non-obvious. The root cause
is that the Wayland protocol's DMA-BUF sharing model assumed KMS drivers would export GEM
handles in a universally importable format; NVIDIA's proprietary driver historically used a
different memory model. Explicit sync (the `linux-drm-syncobj-v1` protocol) landed in the
kernel in 2024 and the major compositors adopted it in 2024–2025, largely resolving the
previously common screen-tearing and frame-drop issues.

**Kernel parameters.** For any NVIDIA GPU with the proprietary driver (550+), add the
following to your bootloader:

```
nvidia-drm.modeset=1 nvidia-drm.fbdev=1
```

For GRUB2, edit `/etc/default/grub`:

```bash
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash nvidia-drm.modeset=1 nvidia-drm.fbdev=1"
sudo grub-mkconfig -o /boot/grub/grub.cfg
```

For systemd-boot, edit `/boot/loader/entries/arch.conf`:

```
options root=UUID=... rw quiet nvidia-drm.modeset=1 nvidia-drm.fbdev=1
```

**Environment variables.** Most compositors require these in your session environment
(`~/.config/hypr/hyprland.conf`, `~/.config/sway/config`, or `/etc/environment`):

```bash
# Hyprland — place in hyprland.conf
env = LIBVA_DRIVER_NAME,nvidia
env = XDG_SESSION_TYPE,wayland
env = GBM_BACKEND,nvidia-drm
env = __GLX_VENDOR_LIBRARY_NAME,nvidia
env = NVD_BACKEND,direct

# Sway — place at top of config or in /etc/environment
export LIBVA_DRIVER_NAME=nvidia
export GBM_BACKEND=nvidia-drm
export __GLX_VENDOR_LIBRARY_NAME=nvidia
export WLR_NO_HARDWARE_CURSORS=1
```

**Explicit sync.** Hyprland 0.41+ enables explicit sync by default when the kernel and driver
support it. Verify it is active:

```bash
hyprctl getoption general:allow_tearing
# check /tmp/hypr/*/hyprland.log for "explicit sync"
```

**Compositor-by-compositor NVIDIA status (mid-2025):**

| Compositor | NVIDIA Status | Notes |
|------------|--------------|-------|
| Hyprland | Good | Explicit sync since 0.41; `WLR_NO_HARDWARE_CURSORS` no longer needed on 550+ |
| KWin (Plasma) | Best | First-class support; tested by Valve for Steam Deck OLED |
| Sway | Improved | Still requires `WLR_NO_HARDWARE_CURSORS=1` on some systems; wlroots 0.18 improved |
| Wayfire | Fair | Inherits wlroots NVIDIA improvements; no dedicated QA |
| labwc | Fair | Same wlroots base as Sway; similar caveats |
| River | Poor–Fair | Minimal NVIDIA QA; community reports vary |
| Niri | Fair | Smithay backend; improving rapidly in 2025 |
| COSMIC | Fair | Also Smithay; System76 has AMD dev hardware; NVIDIA is secondary priority |

**Nouveau (open-source NVIDIA).** The `nouveau` driver with Vulkan support (via NVK, merged
in kernel 6.6) is viable for Maxwell-era and newer GPUs as of 2025. Reclocking support remains
incomplete on Ampere and newer, meaning performance is capped. For ricing purposes nouveau is
fine; for gaming it is still behind the proprietary driver.

```bash
# Check if NVK is active
vulkaninfo --summary | grep -i nouveau
# Expected: VK_DRIVER_ID_MESA_NVK
```

---

## 14.3 Full Comparison Matrix

The table below compares seven major compositors across the axes most relevant to ricing and
daily-driving. Entries marked `*` have important caveats explained in the rows that follow.

| Feature | Sway | Hyprland | Wayfire | River | Niri | labwc | KWin |
|---------|------|----------|---------|-------|------|-------|------|
| Layout | Manual tiling | Dynamic tiling | Plugin | Tag/manual | Scrollable columns | Stacking | Tiling + Stacking |
| Backend library | wlroots | Aquamarine | wlroots | wlroots | Smithay | wlroots | KWin (custom) |
| Implementation lang | C | C++ | C++ | Zig | Rust | C | C++ / QML |
| Config format | i3-syntax text | hyprlang (custom DSL) | INI + GUI | Shell script | KDL | XML + theme | GUI + KWin scripts |
| Animations | Minimal | Heavy (tweakable) | Heavy | None | Moderate | None | Moderate |
| NVIDIA support | Fair | Good | Fair | Poor–Fair | Fair | Fair | Best |
| HDR support | No | Partial (0.42+) | No | No | Planned | No | Yes (Plasma 6.3+) |
| Variable refresh rate | Yes | Yes | Yes | Partial | Yes | Partial | Yes |
| Quickshell / eww | Yes | Best | Yes | Yes | Yes | Yes | Limited |
| Waybar | Yes | Yes | Yes | Yes | Yes | Yes | Replaces (Plasma bar) |
| IPC / scripting | swaymsg / i3ipc | hyprctl / hyprland-ipc | dbus | riverctl | niri msg | Limited | KWin scripting / dbus |
| Idle / lock | swayidle + swaylock | hypridle + hyprlock | Built-in plugin | swayidle + swaylock | swayidle + swaylock | swayidle + swaylock | KScreenLocker |
| Ricing community | Large | Huge | Medium | Small | Growing | Small | Large (KDE) |
| Stability | Excellent | Good | Good | Excellent | Good | Excellent | Excellent |
| First stable release | 2017 | 2022 | 2019 | 2021 | 2023 | 2021 | 2002 (X11 era) |
| Primary dev language | C | C++ | C++ | Zig | Rust | C | C++ |

**Aquamarine vs wlroots.** Hyprland migrated away from wlroots to its own backend library,
Aquamarine, in 0.41 (early 2024). This gave the project full control over DRM/KMS scheduling,
explicit sync implementation, and the VRR pipeline — at the cost of being the sole maintainer
of those primitives. The rest of the wlroots-based compositors (Sway, River, Wayfire, labwc)
share wlroots maintenance burden and benefit from cross-project fixes. Smithay-based compositors
(Niri, COSMIC) are built on a pure-Rust Wayland server library and represent a third independent
lineage.

**KWin's special status.** KWin is not a standalone compositor in the same sense as the others:
it requires the Plasma session infrastructure (KWayland, Plasma Framework, KWin scripting daemon)
to be meaningful. If you want KWin features without the full Plasma stack, the effort is
significant and unsupported. Treat "KWin" as shorthand for "KDE Plasma on Wayland."

**River's tag model.** River implements a tag-based workspace model similar to dwm rather than
the numbered-workspace model common elsewhere. Each window can be assigned to multiple tags
simultaneously; views are visible when their tags intersect the focused tag set. This is more
flexible than numbered workspaces but requires deliberate mental model adjustment.

---

## 14.4 Recommended Starting Points

The recommendations below are prescriptive. The qualifications are real; if your situation does
not match the profile, read the alternatives before committing.

**Migrating from X11 i3 or i3-gaps — use Sway.**
Sway's config format is a near-superset of i3's. Most i3 configs load in Sway with only the
`xwayland enable` line added and a few X11-specific `exec` calls removed. The bar syntax, keybind
syntax, `for_window` rules, and `assign` rules are identical. The ecosystem (swaybar, i3status-rust,
swayidle, swaylock) mirrors the X11 equivalents. Migration time is typically under an hour.

```bash
# Minimal Sway config derived from an i3 config
# ~/.config/sway/config

# Inherit your existing i3 config, then override
include ~/.config/sway/i3-compat.conf

# Required Wayland additions
xwayland enable
exec dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP

# Replace i3bar
bar {
    swaybar_command waybar
}
```

**Wants beautiful animations and a huge dotfiles ecosystem — use Hyprland.**
Hyprland's animation system is the most configurable of any compositor. Bezier curves,
per-animation overrides, layer-specific effects, and blur parameters can all be tuned. The
Hyprland subreddit, the `hyprland-community` GitHub org, and the `hyprland-dotfiles` topic
on GitHub have thousands of complete setups to reference. The config language is expressive
and the `hyprctl` IPC client makes runtime reconfiguration easy.

```ini
# ~/.config/hypr/hyprland.conf — animation showcase config
animations {
    enabled = yes

    bezier = overshot,  0.13, 0.99, 0.29, 1.1
    bezier = smoothOut, 0.36, 0,    0.66, -0.56
    bezier = smoothIn,  0.25, 1,    0.5,  1

    animation = windows,     1, 5,  overshot,  slide
    animation = windowsOut,  1, 4,  smoothOut, slide
    animation = windowsMove, 1, 4,  smoothIn
    animation = border,      1, 10, default
    animation = fade,        1, 10, smoothIn
    animation = fadeDim,     1, 10, smoothIn
    animation = workspaces,  1, 6,  overshot,  slidevert
}
```

**Wide monitors, scrollable focus model — use Niri.**
Niri arranges windows in infinite horizontal columns rather than workspaces. Each column is
resizable; a focus gesture slides the view left or right. This matches the mental model of
many knowledge workers who keep a browser, a terminal, and a reference document in view
simultaneously without window overlap. Configuration is in KDL; the format is terse and
readable. See Ch 22 for a full Niri configuration walkthrough.

```kdl
// ~/.config/niri/config.kdl — minimal starter
input {
    keyboard {
        xkb { layout "us" }
    }
    touchpad {
        tap
        natural-scroll
    }
}

layout {
    gaps 8
    center-focused-column "on-overflow"
    default-column-width { proportion 0.45; }
}

binds {
    Mod+Return { spawn "alacritty"; }
    Mod+D      { spawn "fuzzel"; }
    Mod+Q      { close-window; }
    Mod+H      { focus-column-left; }
    Mod+L      { focus-column-right; }
    Mod+J      { focus-window-down; }
    Mod+K      { focus-window-up; }
}
```

**Compiz nostalgia, 3D cube, wobbly windows — use Wayfire.**
Wayfire ships a `wcm` (Wayfire Config Manager) GUI that lets you enable and configure plugins
without editing text files. The `cube` plugin reproduces the Compiz Desktop Cube. The `wobbly`
plugin adds spring-physics window dragging. The plugin API is documented and new plugins can be
written in C++ against the Wayfire plugin ABI.

```ini
# ~/.config/wayfire.ini — enable nostalgic effects
[core]
plugins = required autostart cube wobbly animate

[cube]
skydome = true
skydome_mirror = true

[wobbly]
spring_k = 8
friction  = 3
mass      = 1

[animate]
open_animation  = zoom
close_animation = zoom
```

**Traditional floating desktop without a full DE — use labwc.**
labwc (Lab Wayland Compositor) follows the openbox configuration model: XML `rc.xml` for
window management rules, `autostart` for startup applications, and theme directories for
decoration styling. It pairs naturally with Waybar, dunst, and a standalone app launcher.
No daemon, no compositor effects by default — just fast, reliable stacking window management.

```bash
# Install on Arch Linux
yay -S labwc waybar dunst fuzzel

# ~/.config/labwc/autostart
waybar &
dunst &
swaybg -i ~/wallpapers/current.png -m fill &
```

**NixOS full integration — use KWin (Plasma) or Hyprland with home-manager.**
Both have excellent NixOS module coverage. The `nixos-hardware` and `nixpkgs` teams maintain
KDE Plasma Wayland as a tier-1 configuration target. The `hyprland-flake` project provides
a NixOS module and a home-manager module. See Ch 47 for NixOS-specific dotfile management.

```nix
# flake.nix snippet for Hyprland on NixOS
{
  inputs.hyprland.url = "github:hyprwm/Hyprland";

  outputs = { nixpkgs, hyprland, ... }: {
    nixosConfigurations.myhost = nixpkgs.lib.nixosSystem {
      modules = [
        hyprland.nixosModules.default
        {
          programs.hyprland = {
            enable = true;
            xwayland.enable = true;
          };
        }
      ];
    };
  };
}
```

**Minimal, hackable, close to the metal — use dwl.**
dwl is a dwm-inspired compositor written in C, intentionally kept under 2000 lines. There is
no official config file; configuration is done by editing `config.h` and recompiling. Patches
are distributed as diff files in the same tradition as dwm. If you want to understand what a
compositor actually does at the wlroots API level, dwl is the fastest path to that knowledge.

```bash
# Build dwl from source (Arch)
git clone https://codeberg.org/dwl/dwl.git
cd dwl
cp config.def.h config.h
# Edit config.h for your keybinds and terminal
$EDITOR config.h
make
sudo make install
```

**Gaming-first setup — use gamescope + Hyprland.**
gamescope is a micro-compositor optimised for game rendering: it handles upscaling (FSR, NIS),
VRR, HDR tonemapping, and frame-rate limiting without touching the desktop compositor. The
correct production pattern is to run gamescope nested inside Hyprland, not as a replacement
for it.

```bash
# Launch a game inside gamescope nested in Hyprland
gamescope -W 2560 -H 1440 -r 165 --hdr-enabled --adaptive-sync \
    --backend wayland -- steam -gamepadui
```

---

## 14.5 Migration Paths

Migration between compositors is less painful than it appears because Wayland tooling (Waybar,
swayidle, dunst, fuzzel, wl-clipboard) is compositor-agnostic. The compositor config and the
window manager keybinds are the only parts that do not transfer. A well-structured dotfiles
repo separates these cleanly.

**X11 i3 → Sway.**
This is the smoothest migration path in the entire Linux desktop ecosystem. The config syntax
is intentionally compatible. Steps:

1. Install Sway and its companion tools (`swayidle`, `swaylock`, `swaybar` or Waybar).
2. Copy your `~/.config/i3/config` to `~/.config/sway/config`.
3. Add `xwayland enable` at the top for legacy X11 apps.
4. Replace `i3bar` stanzas with `swaybar_command waybar` if desired.
5. Replace `exec compton` or `picom` with nothing (Sway composites natively).
6. Test with `sway` from a TTY; use `swaymsg` to debug rule matching.

```bash
# Validate your migrated config without starting a session
sway --validate
# Output: "Configuration file is valid."
```

**X11 bspwm → Hyprland or River.**
bspwm users are accustomed to a split between the compositor/WM (`bspwm`) and a separate
hotkey daemon (`sxhkd`). Neither Hyprland nor River uses `sxhkd`, but both have built-in
keybind support. River's `riverctl map` calls in your `init` script are the closest
conceptual match to `sxhkd` rules. Hyprland's `bind` directives are more tightly integrated.

```bash
# River init script (~/.config/river/init, must be executable)
#!/bin/sh
riverctl map normal Super Return spawn alacritty
riverctl map normal Super D     spawn fuzzel
riverctl map normal Super Q     close
riverctl map normal Super+Shift E exit

# Set the default layout generator
riverctl default-layout rivertile
rivertile -view-padding 6 -outer-padding 6 &

riverctl init
```

**X11 Openbox → labwc.**
The XML configuration format of labwc is deliberately modelled on Openbox. The `rc.xml`
structure, keyboard binding syntax, and mouse binding syntax are nearly identical. Autostart
behaviour differs: labwc runs `~/.config/labwc/autostart` (a shell script) instead of
Openbox's `~/.config/openbox/autostart`.

```xml
<!-- ~/.config/labwc/rc.xml — keybinds matching Openbox style -->
<keyboard>
  <keybind key="W-Return">
    <action name="Execute"><command>alacritty</command></action>
  </keybind>
  <keybind key="W-d">
    <action name="Execute"><command>fuzzel</command></action>
  </keybind>
  <keybind key="W-q">
    <action name="Close"/>
  </keybind>
</keyboard>
```

**X11 dwm → dwl.**
The patch ecosystem for dwl mirrors dwm's: patches are applied with `git am` or `patch -p1`
before compilation. The `dwl-patches` Codeberg repository catalogues available patches. Both
use `config.h` for layout and keybind customisation. The conceptual model (master-stack layout,
tag-based workspaces) is identical.

**GNOME X11/Wayland → COSMIC.**
System76's COSMIC desktop (first stable release: 2024) provides a GNOME-like workflow with
a Rust codebase and a proprietary-but-open settings system. Extensions are not compatible
but the layout (activities overview, dash, top bar) is familiar. COSMIC uses Smithay as its
compositor backend.

**KDE X11 → KDE Wayland.**
This is a same-config migration: Plasma stores settings in `~/.config/kwinrc`,
`~/.config/plasmarc`, and KConfig files that are session-protocol-agnostic. The Wayland
session is selected at the display manager; everything else is automatic.

```bash
# Verify KWin is running under Wayland
qdbus org.kde.KWin /KWin supportInformation | grep "Compositor"
# Output should include: Backend: Wayland
```

---

## 14.6 Ecosystem Tools That Are Compositor-Agnostic

A common misconception is that switching compositors means rebuilding your entire desktop
stack. In reality, most of the visible ricing surface is compositor-agnostic. The table below
shows which tools work across all major compositors:

| Tool | Role | Compositor support |
|------|------|--------------------|
| Waybar | Status bar | All major Wayland compositors |
| Eww | Widget engine | All (requires `wlr-layer-shell` or `ext-session-lock`) |
| Quickshell | QML widget shell | All (layer-shell protocol) |
| dunst | Notification daemon | All (uses `libnotify` D-Bus interface) |
| mako | Notification daemon | All wlroots-based; others vary |
| swayidle | Idle management | All; not needed on KWin |
| swaylock / hyprlock | Screen lock | swaylock: most; hyprlock: Hyprland-optimised |
| fuzzel | App launcher | All (layer-shell) |
| rofi (Wayland fork) | App launcher | All |
| wl-clipboard | Clipboard CLI | All |
| grim + slurp | Screenshot | All wlroots-based; KWin has spectacle |
| wf-recorder | Screen capture | Most; uses `wlr-screencopy` |
| imv | Image viewer | All |
| swaybg / swww | Wallpaper | All (layer-shell) |
| kanshi | Output management | All; uses `wlr-output-management` |

When structuring your dotfiles repo, separate compositor-specific configs (one directory per
compositor) from shared tool configs (waybar, dunst, fuzzel, etc.). This makes A/B testing
compositors trivial. See Ch 53 for a dotfiles layout that implements this pattern.

---

## 14.7 Performance Profiling Your Compositor Choice

Before committing to a compositor for a production setup, profile it on your hardware.
The three metrics that matter for ricing are: steady-state CPU/GPU usage, animation frame time,
and input latency.

**Steady-state profiling.** Measure compositor process CPU and GPU usage with no input events:

```bash
# CPU usage of compositor process (replace hyprland with sway, niri, etc.)
pidstat -p $(pgrep hyprland) 1 10

# GPU usage (AMD)
radeontop -d - -l 5 | grep GPU

# GPU usage (NVIDIA)
nvidia-smi dmon -s u -d 1 -c 10

# GPU usage (Intel)
intel_gpu_top -s 1000 -l | head -20
```

**Animation frame time.** Hyprland exposes timing data via its IPC:

```bash
hyprctl monitors | grep -E "refreshRate|id"
# Then watch the compositor log during window open/close:
tail -f /tmp/hypr/$(ls /tmp/hypr/)/hyprland.log | grep -i "frame\|render"
```

**Input latency.** The `wl-latency` tool (available in some distros; build from source otherwise)
measures end-to-end input latency for Wayland compositors:

```bash
git clone https://github.com/Consolatis/wl-latency
cd wl-latency && make
./wl-latency -n 1000  # 1000 samples
```

Typical results on mid-range hardware (Ryzen 5 5600, RX 6700 XT, 165 Hz display):

| Compositor | Idle CPU | Idle GPU | Anim frame time (avg) | Input latency (avg) |
|-----------|----------|----------|----------------------|---------------------|
| Sway | 0.1% | 1–2% | N/A (minimal) | 4–7 ms |
| Hyprland | 0.2% | 3–5% | 8–12 ms | 5–8 ms |
| Niri | 0.15% | 2–3% | 10–14 ms | 5–9 ms |
| KWin (Plasma) | 0.3% | 4–6% | 12–16 ms | 6–10 ms |
| Wayfire | 0.2% | 3–5% | 10–15 ms | 6–10 ms |

These numbers are representative; your hardware will differ. The key takeaway is that tiling
compositors with minimal animations (Sway, River) have measurably lower overhead than
animation-heavy ones.

---

## 14.8 Troubleshooting

This section covers the most common failures encountered when first starting a new compositor
session. If you hit a problem not covered here, the compositor's issue tracker and the
`#compositor-name` channels on the Wayland Discord are the fastest paths to resolution.

**Compositor exits immediately after launch.**
Check the log output. Every major compositor writes a startup log:

```bash
# Hyprland
cat /tmp/hypr/$(ls -t /tmp/hypr/ | head -1)/hyprland.log | tail -50

# Sway
sway -d 2>&1 | head -100

# Niri
RUST_LOG=niri=debug niri msg version  # then check journalctl
journalctl --user -u niri --since "1 min ago"
```

Common causes: missing `XDG_RUNTIME_DIR`, GPU driver not loaded, missing DRM device permissions.

**Black screen on NVIDIA.**
The most common cause is missing `nvidia-drm.modeset=1`. Verify:

```bash
cat /sys/module/nvidia_drm/parameters/modeset
# Must return: Y
```

If it returns `N`, the kernel parameter was not applied. Re-check bootloader config and rebuild
initramfs if using mkinitcpio with the `nvidia` module:

```bash
sudo mkinitcpio -P
sudo grub-mkconfig -o /boot/grub/grub.cfg
reboot
```

**Cursor invisible or stuck.**
Set `WLR_NO_HARDWARE_CURSORS=1` (for wlroots compositors) or the compositor-specific
equivalent before launching:

```bash
# Quick test without modifying config
WLR_NO_HARDWARE_CURSORS=1 sway
# or
env HYPRLAND_NO_SD_NOTIFY=1 WLR_NO_HARDWARE_CURSORS=1 Hyprland
```

If that fixes it, add the variable to your session environment permanently:

```bash
# /etc/environment or ~/.config/sway/config / hyprland.conf
WLR_NO_HARDWARE_CURSORS=1
```

**XWayland applications not starting.**
Ensure `xwayland enable` is in your Sway config or `xwayland:force_zero_scaling = true` in
Hyprland. Also verify the `xwayland` package is installed:

```bash
# Arch
pacman -Q xorg-xwayland

# Debian/Ubuntu
dpkg -l xwayland
```

**Screen sharing (PipeWire) not working.**
Screen sharing via WebRTC (browser, Discord, etc.) requires the `xdg-desktop-portal-wlr`
or `xdg-desktop-portal-hyprland` portal backend to be running, plus PipeWire:

```bash
# Check running portals
systemctl --user status xdg-desktop-portal
systemctl --user status xdg-desktop-portal-wlr  # or -hyprland

# If stopped, start manually for testing
/usr/lib/xdg-desktop-portal-wlr &
/usr/lib/xdg-desktop-portal &

# Verify PipeWire is running
pactl info | grep "Server Name"
pw-cli info | head -5
```

The correct portal backend for each compositor:

| Compositor | Correct XDG portal backend |
|-----------|--------------------------|
| Sway, River, labwc | `xdg-desktop-portal-wlr` |
| Hyprland | `xdg-desktop-portal-hyprland` |
| KWin | `xdg-desktop-portal-kde` |
| GNOME | `xdg-desktop-portal-gnome` |
| Niri, COSMIC | `xdg-desktop-portal-gnome` or `-wlr` (check distro) |

**High CPU usage at idle.**
First rule out hardware cursor emulation (covered above). Then check if a panel/bar is
polling too aggressively. Waybar modules with `interval` values below 2 seconds can spike
CPU on slow filesystems. Profile with:

```bash
perf top -p $(pgrep waybar)
```

Also check if an animation plugin or idle inhibitor is stuck in active state:

```bash
# Hyprland
hyprctl activeinhibitors

# Sway
swaymsg -t get_inputs | jq '.[] | select(.inhibit_idle == true)'
```

---

*See also: Ch 15 (Hyprland deep dive), Ch 16 (Sway configuration), Ch 22 (Niri scrollable layout),
Ch 47 (NixOS module configuration), Ch 53 (session startup and display manager integration).*

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
