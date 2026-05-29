# Chapter 77 — Plymouth Boot Splash: Themed Boot Screens

## Overview
Plymouth handles the graphical boot screen — the loading animation between
GRUB and your login manager. A themed Plymouth splash completes the visual
continuity of a rice, matching the color palette from BIOS POST to desktop.

## Sections

### 77.1 How Plymouth Works
- Plymouth starts very early in the boot process (initramfs)
- Renders using kernel mode-setting (KMS) — no X11/Wayland needed
- Transitions to the login manager by hiding itself
- Theme scripts are Plymouth-specific (not QML or GTK)

### 77.2 Installation

```bash
sudo pacman -S plymouth
```

**Enable in initramfs** (`/etc/mkinitcpio.conf`):
```
HOOKS=(base systemd ... plymouth ...)
# plymouth must come after 'base' and before 'encrypt' (if using LUKS)
sudo mkinitcpio -P
```

**Enable in systemd:**
```bash
sudo systemctl enable plymouth-quit-wait.service
sudo systemctl enable plymouth.service
```

**Kernel parameters** (GRUB `/etc/default/grub`):
```
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash loglevel=3 rd.udev.log_level=3"
```
```bash
sudo grub-mkconfig -o /boot/grub/grub.cfg
```

**systemd-boot** (`/boot/loader/entries/*.conf`):
```
options quiet splash
```

### 77.3 Selecting a Theme

```bash
# List available themes
plymouth-set-default-theme --list

# Preview a theme (in virtual terminal, not Wayland)
plymouthd --debug --mode=boot
plymouth --show-splash
sleep 5
plymouth --quit

# Set default theme
sudo plymouth-set-default-theme -R catppuccin-mocha-plymouth
# -R rebuilds initramfs automatically
```

### 77.4 Popular Plymouth Themes

**Catppuccin Plymouth:**
```bash
paru -S catppuccin-plymouth     # AUR
sudo plymouth-set-default-theme -R catppuccin-mocha
```

**BGRT (OEM logo):**
- Uses your system's UEFI vendor logo
- `sudo plymouth-set-default-theme -R bgrt`

**Spinner (minimal):**
- Clean, distro-agnostic spinner
- `sudo plymouth-set-default-theme -R spinner`

**Hexagon:**
- Animated hexagon tiles
- `paru -S plymouth-theme-hexagon-2-git`

**Loader:**
- Progress bar with distro logo
- `paru -S plymouth-theme-loader-git`

**NixOS theming via Stylix:**
```nix
boot.plymouth = {
    enable = true;
    theme = "catppuccin-mocha";
    themePackages = [ pkgs.catppuccin-plymouth ];
};
```

### 77.5 Writing a Custom Plymouth Theme

Plymouth themes consist of:
```
/usr/share/plymouth/themes/mytheme/
├── mytheme.plymouth      ← theme metadata
└── mytheme.script        ← animation script
```

**mytheme.plymouth:**
```ini
[Plymouth Theme]
Name=My Theme
Description=Custom rice splash
ModuleName=script

[script]
ImageDir=/usr/share/plymouth/themes/mytheme
ScriptFile=/usr/share/plymouth/themes/mytheme/mytheme.script
```

**mytheme.script (simple progress bar):**
```
// Load background
bg_image = Image("background.png");
bg_sprite = Sprite(bg_image);
bg_sprite.SetX(0); bg_sprite.SetY(0); bg_sprite.SetZ(-100);

// Progress bar
bar_bg = Image.CreateFromFile("bar-bg.png");
bar_fg = Image.CreateFromFile("bar-fg.png");
bar_sprite = Sprite();

// Animation callback
fun progress_callback(duration, progress) {
    bar_sprite.SetImage(bar_fg.Scale(bar_fg.GetWidth() * progress, bar_fg.GetHeight()));
}
Plymouth.SetBootProgressFunction(progress_callback);
```

### 77.6 LUKS Encryption Prompt Theming

Plymouth also handles the LUKS password prompt. Configure in `.plymouth`:
```ini
[two-step]
TitleFont=Inter 20
SubTitleFont=Inter 14
```

Custom passphrase dialog position and styling via the script API.

### 77.7 Smooth Transition to Login Manager

For seamless handoff between Plymouth and SDDM/GDM:
```bash
# SDDM: no extra config needed — Plymouth quits when DM starts
# For systemd-based:
sudo systemctl enable plymouth-quit.service
```

Check that `quiet` is in kernel params — hides the text journal output between
Plymouth and the DM.

### 77.8 Troubleshooting Plymouth

```bash
# Check Plymouth status
systemctl status plymouth-quit-wait.service

# See Plymouth debug log
journalctl -b | grep -i plymouth

# Force Plymouth mode (for testing)
sudo plymouthd --no-daemon --debug 2>&1

# Ensure KMS driver loads early
# In /etc/mkinitcpio.conf MODULES= add: amdgpu (AMD) or i915 (Intel) or nvidia_drm (NVIDIA)
```
