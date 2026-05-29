# Chapter 82 — Printing and Scanning on Wayland

## Overview
CUPS handles printing on Linux; SANE handles scanning. Both work on Wayland
without protocol changes. The challenge is the GUI tooling and driver setup.

## Sections

### 82.1 CUPS Setup

```bash
sudo pacman -S cups cups-pdf ghostscript gsfonts
sudo systemctl enable --now cups
```

**Web interface:** http://localhost:631 — add printers, manage queues

**Print dialogs on Wayland:**
GTK apps use CUPS via the GTK print dialog (works natively).
Qt apps use Qt's print dialog (works natively).
No Wayland-specific issues here.

### 82.2 Adding Printers

**Automatic (Avahi/DNS-SD for network printers):**
```bash
sudo pacman -S avahi nss-mdns
sudo systemctl enable --now avahi-daemon
```
Edit `/etc/nsswitch.conf`: `hosts: ... mdns_minimal resolve ...`

Most modern printers will appear automatically in the CUPS web UI.

**Manual (HP):**
```bash
sudo pacman -S hplip
hp-setup  # HP's own setup wizard
```

**Manual (Canon/Epson/Brother):**
- Check AUR for vendor-specific drivers: `canonXXX-cups`, `epson-inkjet-printer-*`

### 82.3 GUI Print Managers

```bash
sudo pacman -S system-config-printer  # GTK printer manager
# Or KDE's printer manager (via system settings)
```

### 82.4 SANE Scanning

```bash
sudo pacman -S sane sane-airscan    # sane-airscan for modern IPP-over-USB/network scanners
```

**List detected scanners:**
```bash
scanimage -L
```

**Simple-scan (GUI):**
```bash
sudo pacman -S simple-scan
simple-scan  # GTK4, Wayland-native
```

**gscan2pdf (advanced):**
```bash
sudo pacman -S gscan2pdf
```

### 82.5 Network Scanners

Most modern network scanners support IPP Scan (eSCL/WSD):
```bash
sudo pacman -S sane-airscan
# Test:
scanimage -L  # should show network scanner
```

For HP network scanners:
```bash
hp-scan  # included with hplip
```

### 82.6 Printing via CLI

```bash
lp file.pdf                          # print to default printer
lp -d "Printer-Name" file.pdf        # specific printer
lpstat -p                            # list printers
lpq                                  # queue status
lprm -                               # cancel all jobs
```
