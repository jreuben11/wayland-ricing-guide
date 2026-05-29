# Chapter 77 — Plymouth Boot Splash: Themed Boot Screens

## Overview

Plymouth handles the graphical boot screen — the loading animation between GRUB and your login manager.
A themed Plymouth splash completes the visual continuity of a rice, matching the color palette from
BIOS POST to desktop. Rather than a wall of kernel text, you see a smooth branded animation at every
boot and shutdown. Because Plymouth runs inside the initramfs before any compositor, it operates
entirely through kernel mode-setting (KMS), making it uniquely independent of X11 or Wayland.

This chapter covers Plymouth installation, theme selection, custom theme authorship, LUKS passphrase
dialog theming, and smooth transitions to SDDM/GDM. The techniques here apply to Arch-based systems
(pacman/AUR), Debian/Ubuntu derivatives, and NixOS. See Ch 72 for GRUB visual theming (the stage
before Plymouth), and Ch 78 for SDDM/GDM theming (the stage after). For session startup scripts
that run after the login manager, see Ch 53.

| Stage | Component | Chapter |
|---|---|---|
| Firmware | UEFI splash / vendor logo | N/A |
| Bootloader | GRUB theme / systemd-boot | Ch 72 |
| Boot splash | Plymouth | **Ch 77** |
| Login manager | SDDM / GDM | Ch 78 |
| Compositor startup | Hyprland / sway launch | Ch 53 |

---

## 77.1 How Plymouth Works

Plymouth is a boot-splash daemon that starts very early in the boot process — before the root
filesystem is mounted, inside the initramfs. It relies on the Direct Rendering Manager (DRM) and
kernel mode-setting (KMS) to write directly to the framebuffer without a display server. This is
why your GPU driver module (e.g. `i915`, `amdgpu`, `nvidia_drm`) must be loaded early in the
initramfs hooks; otherwise Plymouth falls back to text mode or fails entirely.

The daemon lifecycle has four phases. First, Plymouth is spawned by the initramfs init system
(systemd or busybox) after KMS is available. Second, it shows the splash animation while the root
filesystem is assembled, cryptographic volumes are unlocked, and services start. Third, when the
display manager (SDDM, GDM, ly) starts, Plymouth receives a signal to quit, handing off the screen.
Fourth, a brief crossfade (configurable) transitions to the login screen. The `plymouth-quit-wait.service`
unit ensures the DM does not start until Plymouth has cleanly exited.

Plymouth theme scripts are written in a custom scripting language unique to Plymouth — not QML,
not Lua, not JavaScript. The language exposes a small API: `Image`, `Sprite`, `Window`, `Plymouth.*`
callbacks. This simplicity limits themes to what can be expressed with 2D images and timer callbacks,
but is sufficient for sophisticated animations using pre-rendered sprite sheets.

The configuration hierarchy to understand is: the `.plymouth` file defines theme metadata and which
Plymouth module to use (the most common is `script`, but `two-step` and `spinner` also exist).
The `.script` file drives the animation. Assets (PNG images) live alongside these files in
`/usr/share/plymouth/themes/<theme-name>/`. All of this is baked into the initramfs at build time,
so any change requires rebuilding the initramfs — Plymouth is not a live-editable component.

---

## 77.2 Installation

### Arch Linux

```bash
sudo pacman -S plymouth
```

After installing, Plymouth must be integrated into the initramfs. Edit `/etc/mkinitcpio.conf` and
add `plymouth` to the `HOOKS` array. It must appear after `base` (or `systemd`) and, critically,
**before** `encrypt` if you use LUKS full-disk encryption — otherwise the LUKS passphrase prompt
will not be themed:

```ini
# /etc/mkinitcpio.conf
# For systemd-based initramfs (recommended for modern setups):
HOOKS=(base systemd autodetect modconf kms keyboard sd-vconsole sd-encrypt plymouth filesystems fsck)

# For busybox-based initramfs (legacy):
HOOKS=(base udev autodetect modconf kms keyboard keymap consolefont encrypt plymouth filesystems fsck)
```

If you use `systemd` hook, use `sd-encrypt` instead of `encrypt`, and `sd-vconsole` instead of
`keymap consolefont`. After editing, rebuild:

```bash
sudo mkinitcpio -P
```

Enable the Plymouth systemd units so the boot and shutdown sequences use Plymouth:

```bash
sudo systemctl enable plymouth-quit-wait.service
sudo systemctl enable plymouth-quit.service
# For shutdown splash (optional):
sudo systemctl enable plymouth-reboot.service
sudo systemctl enable plymouth-halt.service
sudo systemctl enable plymouth-poweroff.service
```

### Debian / Ubuntu

```bash
sudo apt install plymouth plymouth-themes
# Optional: additional theme packs
sudo apt install plymouth-theme-spinner plymouth-theme-solar
```

On Debian/Ubuntu the initramfs is rebuilt automatically after install via update-initramfs hooks.
To rebuild manually:

```bash
sudo update-initramfs -u -k all
```

### Fedora / RHEL

Plymouth ships by default on Fedora. To reinstall or add themes:

```bash
sudo dnf install plymouth plymouth-theme-spinner plymouth-plugin-script
sudo dracut -f
```

### Kernel Parameters

Plymouth requires `quiet splash` on the kernel command line to suppress journal output and activate
the splash. Without `quiet`, the kernel log scrolls over Plymouth.

**GRUB** (`/etc/default/grub`):
```bash
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash loglevel=3 rd.udev.log_level=3 vt.global_cursor_default=0"
```

The `vt.global_cursor_default=0` suppresses the blinking text cursor that can appear over Plymouth.
After editing, regenerate GRUB config:

```bash
sudo grub-mkconfig -o /boot/grub/grub.cfg
```

**systemd-boot** (`/boot/loader/entries/arch.conf`):
```ini
title   Arch Linux
linux   /vmlinuz-linux
initrd  /intel-ucode.img
initrd  /initramfs-linux.img
options root=UUID=xxxx-xxxx rw quiet splash loglevel=3 rd.udev.log_level=3 vt.global_cursor_default=0
```

**Early KMS for Plymouth:** Add your GPU module to `MODULES` in `mkinitcpio.conf` so Plymouth can
use hardware acceleration before the root filesystem is mounted:

```ini
# /etc/mkinitcpio.conf
# Intel:
MODULES=(i915)
# AMD:
MODULES=(amdgpu)
# NVIDIA (proprietary, requires nvidia-drm.modeset=1 kernel param):
MODULES=(nvidia nvidia_modeset nvidia_uvm nvidia_drm)
```

For NVIDIA, also add `nvidia-drm.modeset=1` to kernel parameters:

```bash
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash loglevel=3 nvidia-drm.modeset=1"
```

---

## 77.3 Selecting and Previewing a Theme

Plymouth ships with a small set of built-in themes. Many more are available from the AUR or
distribution repositories. The `plymouth-set-default-theme` tool manages theme selection and
initramfs rebuilds.

```bash
# List all installed themes
plymouth-set-default-theme --list

# Show currently active theme
plymouth-set-default-theme

# Set a theme without rebuilding initramfs (for testing config only)
sudo plymouth-set-default-theme catppuccin-mocha

# Set a theme AND rebuild initramfs atomically (recommended)
sudo plymouth-set-default-theme -R catppuccin-mocha
```

To preview a theme without rebooting, you need a spare virtual terminal (TTY). This does not work
inside a Wayland session — you must switch to a VT first (`Ctrl+Alt+F2`, log in as root or with
sudo, then run):

```bash
# On a bare VT:
sudo plymouthd --debug --mode=boot --tty=/dev/tty2
sudo plymouth --show-splash
sleep 8
sudo plymouth --quit
sudo pkill plymouthd
```

For a quicker test cycle, use the `plymouth-x11` package on Arch (AUR) which renders Plymouth
inside an X11 window — useful for rapid iteration on custom theme scripts without rebooting.

```bash
paru -S plymouth-x11
# Then run theme preview inside X:
plymouthd --mode=boot --as-x-server
plymouth --show-splash
sleep 5
plymouth --quit
```

---

## 77.4 Popular Plymouth Themes

The Plymouth theme ecosystem on AUR is extensive. The table below covers the most popular options
alongside their aesthetic category and install command:

| Theme | Aesthetic | Install |
|---|---|---|
| `catppuccin-mocha` | Pastel / Catppuccin palette | `paru -S catppuccin-plymouth` |
| `catppuccin-latte` | Light Catppuccin | `paru -S catppuccin-plymouth` |
| `bgrt` | OEM UEFI vendor logo | Built-in (pacman plymouth) |
| `spinner` | Minimal spinner ring | Built-in |
| `hexagon` | Animated hex tiles | `paru -S plymouth-theme-hexagon-2-git` |
| `loader` | Progress bar + distro logo | `paru -S plymouth-theme-loader-git` |
| `darkmatter` | Dark sci-fi rings | `paru -S plymouth-theme-darkmatter` |
| `lone` | Minimalist line animation | `paru -S plymouth-theme-lone-git` |
| `chips` | Colorful particles | `paru -S plymouth-theme-chips` |
| `sleek` | Flat progress bar | `paru -S plymouth-theme-sleek` |

### Catppuccin Plymouth

```bash
paru -S catppuccin-plymouth
# Variants: catppuccin-mocha, catppuccin-macchiato, catppuccin-frappe, catppuccin-latte
sudo plymouth-set-default-theme -R catppuccin-mocha
```

### BGRT (OEM Logo)

BGRT (Boot Graphics Resource Table) uses the vendor logo embedded in your UEFI firmware — often the
laptop manufacturer's logo. It is the most "invisible" option, matching what most users expect from
a commercial laptop. No AUR package needed:

```bash
sudo plymouth-set-default-theme -R bgrt
```

### Spinner

Clean distro-agnostic spinner ring. No background image, uses system accent color from
`/etc/plymouth/plymouthd.conf`. Good fallback for headless or minimal installs:

```bash
sudo plymouth-set-default-theme -R spinner
```

### NixOS via Stylix

NixOS users can wire Plymouth into Stylix for automatic palette integration:

```nix
# configuration.nix or home-manager module
boot.plymouth = {
  enable = true;
  theme = "catppuccin-mocha";
  themePackages = [ pkgs.catppuccin-plymouth ];
};

# With Stylix auto-coloring:
stylix.targets.plymouth = {
  enable = true;
  logo = ./assets/my-logo.png;
  logoAnimated = true;
};
```

---

## 77.5 Writing a Custom Plymouth Theme

Custom themes are the deepest form of boot splash ricing. A minimal theme needs exactly two files
plus at least one PNG asset. Place everything in a new directory under
`/usr/share/plymouth/themes/<mytheme>/`:

```
/usr/share/plymouth/themes/mytheme/
├── mytheme.plymouth       # metadata + module declaration
├── mytheme.script         # animation logic
├── background.png         # 1920x1080 background (or per-resolution)
├── logo.png               # centered logo sprite
├── bar-bg.png             # progress bar background track
└── bar-fg.png             # progress bar fill (will be scaled)
```

### Theme Metadata File

```ini
# /usr/share/plymouth/themes/mytheme/mytheme.plymouth
[Plymouth Theme]
Name=My Rice Theme
Description=Custom boot splash matching Catppuccin Mocha palette
ModuleName=script

[script]
ImageDir=/usr/share/plymouth/themes/mytheme
ScriptFile=/usr/share/plymouth/themes/mytheme/mytheme.script
```

The `ModuleName=script` tells Plymouth to use the generic script engine. Other module names are
`spinner` (built-in spinner widget), `two-step` (spinner + logo overlay), and `space-flares`
(particle effects). For maximum customization, always use `script`.

### Animation Script

Plymouth's scripting language resembles a simplified C. The key objects are:

- `Image(filename)` — loads a PNG from `ImageDir`
- `Sprite(image)` — a drawable object with position, opacity, Z-order
- `Window.GetWidth()` / `Window.GetHeight()` — screen dimensions
- `Plymouth.SetBootProgressFunction(fn)` — called as boot progress updates (0.0–1.0)
- `Plymouth.SetUpdateStatusFunction(fn)` — called with status strings
- `Plymouth.SetDisplayMessageFunction(fn)` — called with display messages
- `Plymouth.SetDisplayPasswordFunction(fn)` — called when passphrase input is needed

```javascript
// /usr/share/plymouth/themes/mytheme/mytheme.script
// ── Catppuccin Mocha themed boot splash ──

// Screen dimensions
screen_width  = Window.GetWidth();
screen_height = Window.GetHeight();

// ── Background ──
bg_image  = Image("background.png");
bg_sprite = Sprite(bg_image);
bg_sprite.SetX(0);
bg_sprite.SetY(0);
bg_sprite.SetZ(-100);

// ── Centered logo ──
logo_image  = Image("logo.png");
logo_sprite = Sprite(logo_image);
logo_sprite.SetX((screen_width  - logo_image.GetWidth())  / 2);
logo_sprite.SetY((screen_height - logo_image.GetHeight()) / 2 - 60);
logo_sprite.SetZ(10);

// ── Progress bar track ──
bar_bg_image  = Image("bar-bg.png");
bar_bg_sprite = Sprite(bar_bg_image);
bar_bg_sprite.SetX((screen_width - bar_bg_image.GetWidth()) / 2);
bar_bg_sprite.SetY(screen_height * 0.75);
bar_bg_sprite.SetZ(10);

// ── Progress bar fill ──
bar_fg_image = Image("bar-fg.png");
bar_fg_sprite = Sprite();

// ── Boot progress callback ──
fun BootProgressCallback(duration, progress) {
    scaled_width = Math.Int(bar_fg_image.GetWidth() * progress);
    if (scaled_width < 1) scaled_width = 1;
    bar_scaled = bar_fg_image.Scale(scaled_width, bar_fg_image.GetHeight());
    bar_fg_sprite.SetImage(bar_scaled);
    bar_fg_sprite.SetX((screen_width - bar_bg_image.GetWidth()) / 2);
    bar_fg_sprite.SetY(screen_height * 0.75);
    bar_fg_sprite.SetZ(11);
}
Plymouth.SetBootProgressFunction(BootProgressCallback);

// ── Fade-in animation on first frame ──
logo_sprite.SetOpacity(0);
frame = 0;

fun RefreshCallback() {
    frame = frame + 1;
    if (frame < 30) {
        logo_sprite.SetOpacity(frame / 30.0);
    }
}
Plymouth.SetRefreshFunction(RefreshCallback);
```

### Generating Assets with ImageMagick

You can generate placeholder assets programmatically:

```bash
# Catppuccin Mocha background (#1e1e2e)
convert -size 1920x1080 xc:'#1e1e2e' background.png

# Simple white logo circle
convert -size 128x128 xc:transparent \
  -fill '#cdd6f4' -draw "circle 64,64 64,10" \
  logo.png

# Progress bar track (rounded rect, surface2 color)
convert -size 400x8 xc:'#585b70' \
  -fill '#585b70' -draw "roundrectangle 0,0 400,8 4,4" \
  bar-bg.png

# Progress bar fill (mauve #cba6f7)
convert -size 400x8 xc:'#cba6f7' \
  -fill '#cba6f7' -draw "roundrectangle 0,0 400,8 4,4" \
  bar-fg.png
```

### Installing and Activating the Custom Theme

```bash
# Copy theme directory
sudo cp -r ~/mytheme /usr/share/plymouth/themes/

# Register and rebuild initramfs
sudo plymouth-set-default-theme -R mytheme

# Verify
sudo plymouth-set-default-theme
```

---

## 77.6 LUKS Encryption Prompt Theming

When Plymouth runs early enough in the boot sequence (before `encrypt`/`sd-encrypt` in initramfs
hooks), it intercepts the LUKS passphrase prompt and renders it graphically. This is one of the
most compelling reasons to use Plymouth — replacing the bare `Enter passphrase:` TTY prompt with
a styled dialog that matches your rice.

For the `script` module, handle the password prompt with `SetDisplayPasswordFunction`:

```javascript
// In mytheme.script — add after existing code

// ── Password prompt (LUKS) ──
prompt_label_image = Image.Text("Passphrase:", "white", 1, "Sans 16");
prompt_label_sprite = Sprite(prompt_label_image);

input_image  = Image("input-bg.png");   // rounded rect input box asset
input_sprite = Sprite(input_image);

fun DisplayPasswordCallback(prompt, bullets) {
    // 'bullets' = number of characters entered (shown as dots)
    prompt_label_sprite.SetX((screen_width - prompt_label_image.GetWidth()) / 2);
    prompt_label_sprite.SetY(screen_height / 2);
    prompt_label_sprite.SetZ(20);

    input_sprite.SetX((screen_width - input_image.GetWidth()) / 2);
    input_sprite.SetY(screen_height / 2 + 40);
    input_sprite.SetZ(20);

    // Draw bullet dots
    bullet_str = "";
    i = 0;
    while (i < bullets) {
        bullet_str = bullet_str + "•";
        i = i + 1;
    }
    dots_image  = Image.Text(bullet_str, "white", 1, "Sans 20");
    dots_sprite = Sprite(dots_image);
    dots_sprite.SetX((screen_width - dots_image.GetWidth()) / 2);
    dots_sprite.SetY(screen_height / 2 + 42);
    dots_sprite.SetZ(21);
}
Plymouth.SetDisplayPasswordFunction(DisplayPasswordCallback);
```

The `two-step` module has a built-in font configuration for the passphrase dialog, exposed through
the `.plymouth` metadata file:

```ini
# For two-step module instead of script:
[two-step]
TitleFont=Inter Bold 20
SubTitleFont=Inter 14
HorizontalAlignment=.5
VerticalAlignment=.5
```

Verify your LUKS hook ordering in `/etc/mkinitcpio.conf`. Plymouth must appear before the
encryption hook:

```ini
# Correct order — Plymouth themes the passphrase prompt:
HOOKS=(base systemd autodetect modconf kms keyboard sd-vconsole plymouth sd-encrypt filesystems)

# Wrong order — Plymouth starts AFTER LUKS unlock (no themed prompt):
HOOKS=(base systemd autodetect modconf kms keyboard sd-vconsole sd-encrypt plymouth filesystems)
```

After changing hook order, always rebuild:

```bash
sudo mkinitcpio -P
```

---

## 77.7 Smooth Transition to the Login Manager

The handoff from Plymouth to SDDM, GDM, or ly is where jarring flashes most often occur. Several
factors control how seamless this transition is.

The `plymouth-quit-wait.service` systemd unit tells Plymouth to wait until the display manager
has claimed the VT before quitting. This prevents the framebuffer from going blank between Plymouth
and the DM. Ensure it is enabled:

```bash
sudo systemctl enable --now plymouth-quit-wait.service
```

For SDDM, install `sddm-plymouth` (AUR) on Arch to get a Plymouth-aware SDDM build:

```bash
paru -S sddm-plymouth
sudo systemctl enable sddm-plymouth.service
# Disable the stock sddm.service:
sudo systemctl disable sddm.service
```

For GDM, Plymouth integration is built in. Ensure GDM's early graphical target is used:

```bash
sudo systemctl enable gdm.service
# GDM reads /etc/gdm/custom.conf — no Plymouth-specific changes needed
```

Check that `quiet` and `splash` are both in kernel parameters — `quiet` suppresses the systemd
journal that otherwise scrolls over Plymouth, while `splash` is the flag Plymouth itself checks.
Without both, you may see partial text output during the transition.

The Plymouth configuration file `/etc/plymouth/plymouthd.conf` controls global behaviors:

```ini
# /etc/plymouth/plymouthd.conf
[Daemon]
Theme=mytheme
ShowDelay=0         # seconds to wait before showing splash (0 = immediate)
DeviceTimeout=5     # seconds to wait for DRM device
```

Setting `ShowDelay=0` ensures Plymouth appears immediately rather than waiting for a timeout that
can reveal the scrolling kernel log. Set `DeviceTimeout` higher (e.g. `8`) if your GPU takes
longer to initialize — common with discrete NVIDIA cards.

---

## 77.8 Multi-Resolution and HiDPI Support

Plymouth renders at the native framebuffer resolution. On HiDPI displays (2x scaling), your PNG
assets must be large enough or they will appear tiny. Plymouth does not do automatic DPI scaling.

The recommended approach is to provide multiple resolution-specific background images and use
`Window.GetWidth()` / `Window.GetHeight()` in the script to select the correct one:

```javascript
// Resolution-adaptive background selection
w = Window.GetWidth();
h = Window.GetHeight();

if (w >= 3840) {
    bg_image = Image("background-4k.png");
} else if (w >= 2560) {
    bg_image = Image("background-1440p.png");
} else {
    bg_image = Image("background-1080p.png");
}

bg_sprite = Sprite(bg_image);
bg_sprite.SetX(0);
bg_sprite.SetY(0);
bg_sprite.SetZ(-100);
```

Generate resolution variants with ImageMagick:

```bash
# 1080p
convert -size 1920x1080 xc:'#1e1e2e' background-1080p.png
# 1440p
convert -size 2560x1440 xc:'#1e1e2e' background-1440p.png
# 4K
convert -size 3840x2160 xc:'#1e1e2e' background-4k.png
```

For the logo and UI elements, scale them proportionally to screen height rather than using fixed
pixel positions:

```javascript
// Proportional positioning (works at any resolution)
scale   = screen_height / 1080.0;
logo_w  = Math.Int(128 * scale);
logo_h  = Math.Int(128 * scale);
logo_scaled = logo_image.Scale(logo_w, logo_h);
logo_sprite = Sprite(logo_scaled);
logo_sprite.SetX((screen_width  - logo_w) / 2);
logo_sprite.SetY((screen_height - logo_h) / 2 - Math.Int(60 * scale));
```

---

## 77.9 Plymouth on Encrypted Root with TPM2 Unlocking

When using `systemd-cryptenroll` with a TPM2 chip for automatic LUKS unlocking (no passphrase
prompt at boot), Plymouth still plays a role: it shows the splash while the TPM2 unsealing happens,
and only falls through to a passphrase prompt if unsealing fails.

```bash
# Enroll TPM2 key (after LUKS is already set up):
sudo systemd-cryptenroll --tpm2-device=auto --tpm2-pcrs=0+7 /dev/nvme0n1p2

# In /etc/crypttab.initramfs:
# luks-uuid UUID=xxxx none tpm2-device=auto,discard
```

With `sd-encrypt` and TPM2, the boot sequence is: Plymouth appears → TPM2 unseal runs silently
in background → root mounts → Plymouth quits → DM starts. The user sees only the splash, never
the cryptographic machinery. If TPM2 fails (PCR mismatch after BIOS update), Plymouth shows the
passphrase prompt. This is the optimal user experience for secure encrypted systems.

---

## Troubleshooting

Plymouth issues typically manifest as a black screen during boot, a text console visible over the
splash, or the DM appearing before Plymouth has finished. Work through these checks systematically.

### Plymouth Does Not Appear

```bash
# 1. Verify Plymouth is in initramfs hooks
grep HOOKS /etc/mkinitcpio.conf

# 2. Verify splash is in kernel parameters
cat /proc/cmdline
# Should contain: quiet splash

# 3. Check that initramfs was rebuilt after adding Plymouth
ls -la /boot/initramfs-linux.img   # modification time should be recent

# 4. Force rebuild if in doubt
sudo mkinitcpio -P
```

### Black Screen Instead of Splash

Usually a KMS issue — Plymouth cannot open the DRM device.

```bash
# Verify KMS driver is loading early
sudo dmesg | grep -E 'i915|amdgpu|nvidia_drm|DRM'

# Add GPU module to MODULES in mkinitcpio.conf, then rebuild:
# MODULES=(amdgpu)   # for AMD
# MODULES=(i915)     # for Intel
sudo mkinitcpio -P

# For NVIDIA: ensure modeset is enabled
grep nvidia-drm /proc/cmdline
# Should show nvidia-drm.modeset=1
```

### Kernel Text Scrolls Over Plymouth

```bash
# Ensure kernel parameters include both quiet AND splash
# Check /etc/default/grub:
grep GRUB_CMDLINE /etc/default/grub
# Should contain: quiet splash loglevel=3

# Also suppress udev logging:
# rd.udev.log_level=3  or  udev.log_priority=3
sudo grub-mkconfig -o /boot/grub/grub.cfg
```

### Plymouth Shows But DM Flashes / Blank Before Login

```bash
# Check plymouth-quit-wait.service is enabled and not masked
systemctl is-enabled plymouth-quit-wait.service
systemctl status plymouth-quit-wait.service

# Re-enable if needed:
sudo systemctl unmask plymouth-quit-wait.service
sudo systemctl enable plymouth-quit-wait.service
```

### LUKS Passphrase Prompt Not Themed

```bash
# Plymouth must be BEFORE encrypt/sd-encrypt in HOOKS:
grep HOOKS /etc/mkinitcpio.conf
# Correct: ... plymouth sd-encrypt ...
# Wrong:   ... sd-encrypt plymouth ...

# After fixing hook order:
sudo mkinitcpio -P
```

### Plymouth Debug Log

```bash
# Boot-time Plymouth log:
journalctl -b | grep -i plymouth

# Run Plymouth in debug mode for manual inspection:
sudo plymouthd --no-daemon --debug --tty=/dev/tty2 2>&1 | tee /tmp/plymouth-debug.log

# Check for missing assets or script errors:
grep -E 'error|warning|missing|failed' /tmp/plymouth-debug.log
```

### Theme Not Taking Effect After Set

```bash
# Verify theme is correctly set:
plymouth-set-default-theme

# Verify initramfs contains the theme files:
lsinitcpio /boot/initramfs-linux.img | grep plymouth | head -30

# If theme files are missing from initramfs, rebuild:
sudo mkinitcpio -P
```

### Testing Without Reboot

```bash
# Switch to a spare TTY (Ctrl+Alt+F3), log in, then:
sudo plymouthd --debug --mode=boot --tty=/dev/tty3
sudo plymouth --show-splash
sleep 10
sudo plymouth --quit

# Or use plymouth-x11 (AUR) to preview inside X:
paru -S plymouth-x11
plymouthd --mode=boot --as-x-server &
sleep 1
plymouth --show-splash
sleep 8
plymouth --quit
```

---

*See also: Ch 72 (GRUB Visual Theming), Ch 78 (SDDM / GDM Login Manager Theming), Ch 53 (Session Startup and Autostart Scripts), Ch 74 (systemd-boot and UKI).*

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
