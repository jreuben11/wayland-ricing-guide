# Chapter 82 — Printing and Scanning on Wayland

## Overview

Printing and scanning on Linux under Wayland are often treated as afterthoughts, but they deserve careful attention — particularly in riced environments where you control every component of the desktop stack. The good news: neither CUPS (the printing subsystem) nor SANE (the scanning framework) requires Wayland-specific changes at the protocol level. Both operate as daemons that expose either a socket or a network interface, and application GUIs interact with them over those abstractions regardless of the display server.

The complexity surfaces in three areas: driver availability and packaging, GUI tooling that must run natively on Wayland without XWayland fallback for full feature parity, and network discovery through mDNS/DNS-SD which depends on correct system-level name resolution. This chapter walks through all three, from bare-metal CUPS installation through advanced network scanner configuration, CLI tooling, and debugging techniques for stubborn hardware.

The chapter assumes Arch Linux or an Arch-based distribution as the reference platform, with `pacman` and the AUR available. Commands for Fedora/Ubuntu equivalents are noted where they differ materially. For session startup integration, see Ch 53. For display server compatibility with GTK/Qt toolkits, see Ch 14.

---

## 82.1 CUPS Setup

CUPS (Common Unix Printing System) is the de facto standard print spooler on Linux and macOS. It exposes a web interface on `localhost:631` and a D-Bus interface that both GTK and Qt consume for their native print dialogs. On Wayland this means print dialogs in GTK4 and Qt6 apps work identically to X11 — there are no Wayland-protocol-level barriers to printing.

Install the core stack on Arch:

```bash
sudo pacman -S cups cups-pdf ghostscript gsfonts
sudo systemctl enable --now cups
```

`cups-pdf` installs a virtual PDF printer named `PDF` that writes output to `~/PDF/` — invaluable for testing print dialogs and generating PDFs from any app. `ghostscript` provides the PostScript/PDF rendering engine that many drivers delegate to. `gsfonts` ensures the standard 35 PostScript fonts are available for documents that reference them by name.

On Fedora:

```bash
sudo dnf install cups cups-pdf ghostscript ghostscript-fonts
sudo systemctl enable --now cups
```

On Ubuntu/Debian:

```bash
sudo apt install cups cups-pdf ghostscript gsfonts
sudo systemctl enable --now cups
```

The CUPS web UI is your primary management interface for adding printers, examining job queues, and reading printer capability files (PPD). Open `http://localhost:631` in any browser. Administrative operations require authentication — on most distros you either use the `root` password or add your user to the `lp` and/or `sys` group:

```bash
sudo usermod -aG lp,sys "$USER"
# Log out and back in, or:
newgrp lp
```

Confirm the daemon is healthy:

```bash
systemctl status cups
lpstat -H             # show CUPS server address
lpstat -p -d          # list all printers and default
```

CUPS stores its configuration in `/etc/cups/cupsd.conf`. The defaults are sane, but for a riced environment you may want to restrict the web UI to localhost only (it defaults to that) and set a higher `MaxJobRetainTime` for audit logging:

```bash
# /etc/cups/cupsd.conf relevant snippet
ServerName localhost
MaxJobRetainTime 604800    # keep completed jobs for 7 days
AccessLogLevel config      # log config changes, not every page
```

After editing `cupsd.conf`, reload without restarting:

```bash
sudo systemctl reload cups
```

### GTK and Qt Print Dialogs on Wayland

GTK4 applications use `gtk4-print-dialog` which calls CUPS directly via its IPP (Internet Printing Protocol) interface, not through XWayland or any display-server-specific path. Qt6 likewise uses its `QPrinter` backend that queries CUPS via IPP. This means Wayland-native apps like GNOME's Evince, Inkscape (GTK3), or KDE's Okular print correctly out of the box.

Electron apps (VS Code, etc.) use Chromium's printing path which also speaks IPP/CUPS. XWayland-launched apps use the X11 print dialog path, which still calls the same CUPS socket — functionally equivalent.

---

## 82.2 Adding Printers

### Automatic Discovery via Avahi/mDNS

Modern network printers advertise themselves via DNS-SD (also called Bonjour or mDNS). CUPS can discover and auto-install these printers if Avahi is running and your system's name resolution is configured to use it:

```bash
sudo pacman -S avahi nss-mdns
sudo systemctl enable --now avahi-daemon
```

Then edit `/etc/nsswitch.conf` to add `mdns_minimal` to the `hosts` line, before `resolve` and `dns`:

```
# /etc/nsswitch.conf
hosts: mymachines mdns_minimal [NOTFOUND=return] resolve [!UNAVAIL=return] files myhostname dns
```

The `[NOTFOUND=return]` after `mdns_minimal` prevents mDNS lookups from falling through to DNS for `.local` domains — important for performance.

Test mDNS discovery:

```bash
avahi-browse -a -t          # list all advertised services
avahi-browse _ipp._tcp      # list IPP printers specifically
avahi-browse _pdl-datastream._tcp  # list AppSocket/JetDirect printers
```

After Avahi is running and `nsswitch.conf` is correct, network printers should appear in the CUPS web UI under "Add Printer" > "Discovered Network Printers" within a few seconds of browsing.

### Manual HP Printers

HP maintains `hplip` (HP Linux Imaging and Printing), which provides drivers, a setup tool, and a scanning backend:

```bash
sudo pacman -S hplip python-pyqt5    # pyqt5 for hp-toolbox GUI
hp-setup                              # interactive wizard
```

`hp-setup` walks through USB or network detection. For a network printer, pass the IP directly:

```bash
hp-setup -i 192.168.1.42             # non-interactive install at given IP
```

After setup, verify with:

```bash
lpstat -p
hp-check                              # HPLIP diagnostic
```

If `hp-setup` fails with plugin errors (required for some LaserJet models), install the binary plugin:

```bash
hp-plugin                            # downloads and installs proprietary plugin
# Or non-interactively:
hp-plugin -i --plug-in-path /path/to/plugin.run
```

### Manual Canon, Epson, Brother Printers

Vendor-specific drivers are usually in the AUR. Identify your model and search:

```bash
yay -Ss canon | grep cups
yay -Ss epson-inkjet
yay -Ss brother-mfc
```

Common packages:

| Vendor  | AUR Package Pattern               | Notes                              |
|---------|-----------------------------------|------------------------------------|
| Canon   | `cnijfilter2`, `capt-src`         | cnijfilter2 covers most PIXMA/MF   |
| Epson   | `epson-inkjet-printer-escpr`      | ESC/P-R protocol, most inkjets     |
| Epson   | `epson-inkjet-printer-201601w`    | Older WorkForce series             |
| Brother | `brother-mfc-XXXX`                | Model-specific AUR packages        |
| Samsung | `splix`                           | Older Samsung SPL-2 lasers         |

For Canon imageCLASS/MF series:

```bash
yay -S cnijfilter2
# Then add in CUPS web UI, selecting the correct PPD from
# /usr/share/cups/model/ or letting CUPS auto-detect
```

For Epson:

```bash
yay -S epson-inkjet-printer-escpr
sudo systemctl restart cups
# CUPS will now show Epson models during printer add
```

For Brother:

```bash
yay -S brother-mfc-l2710dw         # replace with your model
# Brother's installer script usually calls lpadmin automatically
lpstat -p                           # verify
```

### Adding a Printer via lpadmin (CLI)

For automation or headless setups, skip the web UI:

```bash
# Find the device URI
lpinfo -v                                     # list all available device URIs

# Add a printer (IPP network printer)
sudo lpadmin -p "OfficeHP" \
             -v "ipp://192.168.1.42/ipp/print" \
             -m everywhere \                  # IPP Everywhere / driverless
             -E                              # enable immediately

# Add with explicit PPD
sudo lpadmin -p "CanonMF" \
             -v "usb://Canon/MF110" \
             -P /usr/share/cups/model/Canon/MF100.ppd \
             -E

# Set as default
sudo lpadmin -d "OfficeHP"
```

IPP Everywhere (`-m everywhere`) is the modern driverless path — it queries the printer for its capabilities via IPP and generates a dynamic PPD. It works with any IPP/2.0-capable printer (virtually all printers made after ~2013).

---

## 82.3 GUI Print Managers

The CUPS web UI handles most tasks, but a native GUI print manager integrates better with desktop workflows.

### system-config-printer (GTK)

```bash
sudo pacman -S system-config-printer
system-config-printer          # launch
```

This GTK3 application handles adding/removing printers, editing PPD options, viewing queues, and running test pages. It runs under XWayland by default but works without issues — there is no Wayland-native version as of mid-2025, though XWayland rendering is fine for an occasional management task.

To force XWayland explicitly (in case your session has no XWayland):

```bash
DISPLAY=:0 system-config-printer
# Or ensure XWayland is running — see Ch 14
```

### KDE Printer Manager

KDE Plasma's printer management is built into System Settings. No separate package required on a full Plasma install:

```
System Settings > Printers
```

For a minimal KDE setup:

```bash
sudo pacman -S print-manager
```

This is a Qt6/Wayland-native interface. It covers adding IPP/network/USB printers, setting defaults, and checking job status.

### GNOME Printers (Settings)

GNOME Settings includes printer management:

```
Settings > Printers > Add a Printer
```

On a minimal install:

```bash
sudo pacman -S gnome-control-center
```

The GNOME printer UI uses `cups-pk-helper` for PolicyKit-authenticated operations:

```bash
sudo pacman -S cups-pk-helper
```

---

## 82.4 SANE Scanning

SANE (Scanner Access Now Easy) is the Linux scanning framework. It provides a daemon (`saned`) and a library (`libsane`) that backends plug into. Frontends — `scanimage`, Simple Scan, XSane — query libsane to enumerate devices and acquire images.

```bash
sudo pacman -S sane sane-airscan
```

`sane-airscan` is the modern backend for scanners supporting eSCL (Apple AirScan) or WSD (Windows Scan) protocols. Most network scanners made after 2015 support eSCL. It supplements the older `hpaio` (HP), `epkowa` (Epson), and other vendor backends.

List all detected scanners:

```bash
scanimage -L
```

Expected output for a detected scanner:

```
device `airscan:e0:HP LaserJet MFP M130nw' is a HP LaserJet MFP M130nw eSCL network scanner
device `hpaio:/net/hp_laserjet_mfp_m130nw?ip=192.168.1.42' is a HP LaserJet MFP M130nw all-in-one
```

Acquire a scan from the CLI:

```bash
# Basic flatbed scan to PNG at 300 DPI
scanimage --device "airscan:e0:HP LaserJet MFP M130nw" \
          --resolution 300 \
          --format png \
          --output-file scan.png

# Scan with explicit geometry (A4 in mm)
scanimage -d "airscan:e0:HP LaserJet MFP M130nw" \
          --resolution 600 \
          --format tiff \
          -l 0 -t 0 -x 210 -y 297 \
          --output-file scan_a4_600dpi.tiff
```

List available options for a specific device:

```bash
scanimage -d "airscan:e0:HP LaserJet MFP M130nw" --all-options
```

### Simple Scan (GUI)

Simple Scan is the recommended GTK4 frontend — it is Wayland-native and covers 90% of use cases (flatbed, ADF, multi-page PDFs):

```bash
sudo pacman -S simple-scan
simple-scan
```

Key Simple Scan features:
- Auto-detects all SANE backends
- Saves to PDF (multi-page) or JPEG/PNG
- ADF (automatic document feeder) support
- OCR via tesseract if installed:

```bash
sudo pacman -S tesseract tesseract-data-eng    # English OCR data
```

With tesseract installed, Simple Scan can produce searchable PDFs.

### gscan2pdf (Advanced)

`gscan2pdf` is a GTK3 frontend with more control: ADF batch scanning, OCR with multiple engines, PDF/A output, and image post-processing:

```bash
sudo pacman -S gscan2pdf
# Optional OCR engines:
sudo pacman -S tesseract tesseract-data-eng
yay -S ocrmypdf                                # alternative OCR pipeline
```

`gscan2pdf` runs under XWayland. For Wayland-only setups, Simple Scan is the better choice.

### XSane (Legacy)

```bash
sudo pacman -S xsane
```

XSane is the classic SANE frontend. X11 only, runs under XWayland. Useful for accessing advanced scanner options not exposed by Simple Scan, but otherwise superseded.

---

## 82.5 Network Scanners

### eSCL / AirScan (Modern Standard)

Most network-connected MFPs manufactured after 2015 support eSCL, the AirScan protocol. `sane-airscan` discovers them automatically via mDNS (Avahi) or via explicit IP:

```bash
sudo pacman -S sane-airscan avahi
sudo systemctl enable --now avahi-daemon
```

After restarting SANE-dependent services, `scanimage -L` should list the network scanner. If it does not appear automatically, add it explicitly in `/etc/sane.d/airscan.conf`:

```ini
# /etc/sane.d/airscan.conf
[devices]
# Manual entry: "Friendly Name" = url, "Model Name"
"HP MFP M130"   = http://192.168.1.42:80/eSCL, "HP LaserJet MFP M130nw"
"Canon MF260"   = http://192.168.1.55:80/eSCL
```

Test the eSCL endpoint directly with curl to confirm reachability:

```bash
curl -s http://192.168.1.42:80/eSCL/ScannerCapabilities | xmllint --format -
```

A valid response is an XML document describing supported resolutions, color modes, and media sizes.

### WSD (Windows Scan)

Some scanners use WSD (Web Services for Devices) instead of eSCL. `sane-airscan` handles WSD as well — no extra packages needed. WSD uses UDP broadcast for discovery; if your scanner is on a different VLAN, add it manually:

```ini
# /etc/sane.d/airscan.conf
[devices]
"Brother MFC-L2710" = usb:0x04F9:0x02D0                # USB WSD
"Brother MFC-L2710N" = http://192.168.1.60:5358/        # Network WSD
```

### HP Network Scanners (hplip)

For HP all-in-ones on the network, `hplip` provides `hpaio` as a SANE backend:

```bash
sudo pacman -S hplip
hp-scan --device=net:192.168.1.42 --file=scan.png --res=300
```

List HP devices:

```bash
hp-scan -d   # detect all HP scanners
```

The `hpaio` backend also works through the standard SANE interface:

```bash
scanimage -d "hpaio:/net/hp_laserjet_mfp?ip=192.168.1.42" \
          --format png --resolution 300 --output-file out.png
```

### Epson Network Scanners (epsonscan2)

Epson's modern driver provides better feature access than the generic eSCL path:

```bash
yay -S epsonscan2
```

This installs both a CLI tool and the `epsonds` SANE backend. The `epsonscan2` GUI is Qt5 and runs under XWayland.

---

## 82.6 Printing via CLI

The CUPS command-line tools are the most reliable way to script print jobs and manage queues in a riced environment where you might not want a GUI open.

### Submitting Jobs

```bash
# Print to default printer
lp document.pdf

# Print to named printer
lp -d "OfficeHP" document.pdf

# Print multiple copies, specific pages
lp -d "OfficeHP" -n 3 -P 1-5,8 report.pdf

# Print with printer-specific options (duplex, paper size)
lp -d "OfficeHP" \
   -o sides=two-sided-long-edge \
   -o media=A4 \
   -o outputorder=reverse \
   document.pdf

# Print from stdin (pipe)
cat /etc/fstab | lp -d "OfficeHP" -o cpi=10

# Print image file
lp -d "OfficeHP" -o fit-to-page photo.jpg
```

### Queue Management

```bash
lpstat -p                    # list all printers and status
lpstat -p -d                 # also show default printer
lpstat -o                    # show all queued jobs
lpq                          # queued jobs for default printer
lpq -P "OfficeHP"            # queued jobs for specific printer

lprm -                       # cancel ALL jobs on default printer
lprm -P "OfficeHP" -         # cancel all jobs on specific printer
lprm 42                      # cancel job #42

cancel -a "OfficeHP"         # alternative cancel-all for a printer
cancel 42                    # cancel by job ID
```

### Printer Information

```bash
lpinfo -v                    # list all device URIs (shows connected hardware)
lpinfo -m                    # list all available PPD/drivers
lpinfo -m | grep -i canon    # filter by vendor

lpoptions -p "OfficeHP" -l   # list all options for a printer
lpoptions -p "OfficeHP"      # show current default options
lpoptions -p "OfficeHP" -o sides=two-sided-long-edge  # set default option
```

### Converting and Printing Arbitrary Formats

CUPS accepts PDF natively. For other formats:

```bash
# Convert DOCX to PDF then print (requires libreoffice)
libreoffice --headless --convert-to pdf document.docx
lp document.pdf

# Print Markdown as PDF (requires pandoc + a PDF engine)
pandoc README.md -o README.pdf --pdf-engine=xelatex
lp README.pdf

# Print HTML page
chromium --headless --print-to-pdf=page.pdf https://example.com
lp page.pdf

# Image to PDF then print
convert photo.jpg -page A4 photo.pdf   # ImageMagick
lp photo.pdf
```

---

## 82.7 CUPS-PDF Virtual Printer

The `cups-pdf` virtual printer is useful for testing print dialogs, generating PDFs from any application, and automating PDF creation in scripts.

After installing:

```bash
sudo pacman -S cups-pdf
sudo systemctl restart cups
lpstat -p | grep PDF          # confirm "PDF" printer exists
```

By default, output goes to `~/PDF/`. Change in `/etc/cups/cups-pdf.conf`:

```ini
# /etc/cups/cups-pdf.conf
Out ${HOME}/Documents/PDF         # output directory (${HOME} is expanded)
Label 1                            # prepend job title to filename
Grp lp                             # group ownership of output files
UserUMask 0033                     # permissions: user rw, group r, other r
GhostScript /usr/bin/gs
GhostScriptTimeout 300
```

Print to PDF from CLI:

```bash
lp -d PDF -t "my-document" document.ps
ls ~/PDF/                          # find the output
```

---

## 82.8 SANE Network Daemon (saned)

For sharing a locally-connected scanner over the network to other machines, SANE provides `saned`. This is useful in environments where one workstation has a USB scanner but multiple machines need access.

Enable via systemd socket activation:

```bash
sudo systemctl enable --now saned.socket
```

Configure which clients are allowed in `/etc/sane.d/saned.conf`:

```
# /etc/sane.d/saned.conf
# IP addresses or hostnames allowed to use this scanner
192.168.1.0/24
192.168.1.10
myworkstation.local
```

On the client machines, add the scanner server to `/etc/sane.d/net.conf`:

```
# /etc/sane.d/net.conf
connect_timeout = 60
192.168.1.20           # IP of machine with the physical scanner
scanner-server.local   # or hostname if mDNS works
```

Test from a client:

```bash
SANE_NET_HOSTS=192.168.1.20 scanimage -L
```

Open the firewall port if needed (saned uses port 6566 by default):

```bash
sudo ufw allow 6566/tcp
# Or with nftables:
sudo nft add rule inet filter input tcp dport 6566 accept
```

---

## 82.9 Printer and Scanner Permissions

USB device access for scanners is controlled by udev rules. Most distributions ship these, but if `scanimage -L` shows no devices despite the hardware being plugged in, check group membership:

```bash
ls -la /dev/bus/usb/$(lsusb | grep -i scanner | awk '{print $2"/"$4}' | tr -d :)
# Should show group "scanner" or "lp"
groups "$USER"      # confirm you're in the right group
sudo usermod -aG scanner,lp "$USER"
```

For HP hardware:

```bash
sudo usermod -aG lp "$USER"
# Reconnect USB or reload udev:
sudo udevadm trigger
```

CUPS printer access is controlled by the `lp` group for job submission and `sys`/`wheel` for administration.

---

## 82.10 Comparison of Scanning Frontends

| Frontend       | Protocol     | Wayland Native | ADF | OCR | Multi-Page PDF | Notes                        |
|----------------|-------------|----------------|-----|-----|----------------|------------------------------|
| Simple Scan    | SANE        | Yes (GTK4)     | Yes | Yes | Yes            | Best daily driver            |
| gscan2pdf      | SANE        | No (XWayland)  | Yes | Yes | Yes            | Advanced post-processing     |
| XSane          | SANE        | No (XWayland)  | Yes | No  | Yes            | Legacy; full option access   |
| hp-scan (CLI)  | HPLIP       | N/A (CLI)      | Yes | No  | No             | HP-only, scriptable          |
| scanimage (CLI)| SANE        | N/A (CLI)      | Yes | No  | No             | Scriptable, all backends     |
| epsonscan2     | Epson SDK   | No (XWayland)  | Yes | No  | No             | Epson-specific features      |

---

## 82.11 Automating Scans with Scripts

For a riced environment, a shell function for quick scans is more ergonomic than launching a GUI:

```bash
# ~/.zshrc or ~/.bashrc

scan-pdf() {
    local outfile="${1:-scan-$(date +%Y%m%d-%H%M%S).pdf}"
    local device="${SCAN_DEVICE:-}"
    local device_flag=""
    [[ -n "$device" ]] && device_flag="-d $device"

    scanimage $device_flag \
              --resolution 300 \
              --format tiff \
              --output-file /tmp/scan_tmp.tiff \
              --batch-count 1 2>&1

    if [[ $? -eq 0 ]]; then
        convert /tmp/scan_tmp.tiff -compress jpeg -quality 85 "$outfile"
        echo "Saved: $outfile"
        rm -f /tmp/scan_tmp.tiff
    else
        echo "Scan failed" >&2
        return 1
    fi
}

scan-batch-pdf() {
    # Scan all pages from ADF to a single PDF
    local outfile="${1:-batch-$(date +%Y%m%d-%H%M%S).pdf}"
    local device="${SCAN_DEVICE:-}"
    local device_flag=""
    [[ -n "$device" ]] && device_flag="-d $device"

    mkdir -p /tmp/scan_batch

    scanimage $device_flag \
              --batch="/tmp/scan_batch/page_%04d.tiff" \
              --batch-count=50 \
              --resolution 300 \
              --format tiff \
              --source "ADF" 2>&1

    convert /tmp/scan_batch/page_*.tiff \
            -compress jpeg -quality 85 \
            "$outfile"
    echo "Saved: $outfile ($(ls /tmp/scan_batch/*.tiff 2>/dev/null | wc -l) pages)"
    rm -rf /tmp/scan_batch
}
```

Set `SCAN_DEVICE` to your scanner's device string from `scanimage -L` in your shell profile:

```bash
export SCAN_DEVICE="airscan:e0:HP LaserJet MFP M130nw"
```

---

## Troubleshooting

### CUPS web UI not accessible at localhost:631

```bash
systemctl status cups         # check if service is running
journalctl -u cups -n 50      # recent logs
ss -tlnp | grep 631           # confirm port is bound
```

If cups is running but the port is not bound, check `cupsd.conf` for `Listen` directives:

```bash
grep -i listen /etc/cups/cupsd.conf
# Should include: Listen localhost:631
```

### Printer shows as "stopped" or jobs stuck

```bash
lpstat -p                     # check printer state
cupsenable "PrinterName"      # re-enable
lprm -P "PrinterName" -       # flush stuck jobs
sudo systemctl restart cups
```

For jobs stuck in "processing" with no output:

```bash
journalctl -u cups -f         # watch live CUPS log
# Look for filter errors, missing PPD, or driver failures
```

### No printers discovered on network

1. Confirm Avahi is running: `systemctl status avahi-daemon`
2. Confirm `mdns_minimal` is in `/etc/nsswitch.conf` hosts line
3. Test mDNS: `avahi-browse _ipp._tcp -t`
4. Check firewall: UDP port 5353 must be allowed for mDNS

```bash
sudo ufw allow 5353/udp
# nftables:
sudo nft add rule inet filter input udp dport 5353 accept
```

### scanimage -L shows no devices

1. Check USB connection: `lsusb | grep -i scanner`
2. Check group membership: `groups $USER` — need `scanner` and/or `lp`
3. Test with root to isolate permissions: `sudo scanimage -L`
4. Check SANE backend config: `cat /etc/sane.d/dll.conf | grep -v "^#"`
5. For network scanners, verify Avahi: `avahi-browse _scanner._tcp -t`

```bash
# Force reload SANE configuration
sudo udevadm trigger
# Restart any SANE-related services
sudo systemctl restart saned.socket
```

### HP printer/scanner requires proprietary plugin

```bash
hp-check -t                  # full diagnostic
hp-plugin -i                  # install plugin interactively
# If plugin download fails:
# 1. Download manually from HP: https://www.openprinting.org/download/printdriver/auxfiles/HP/plugins/
# 2. hp-plugin -i --plug-in-path /path/to/hplip-VERSION-plugin.run
```

### Canon/Epson AUR driver build failures

AUR packages for vendor drivers frequently fail to build due to glibc version changes or outdated checksums. Try:

```bash
# Clone the AUR package manually
git clone https://aur.archlinux.org/cnijfilter2.git
cd cnijfilter2
# Edit PKGBUILD to fix checksums or patches, then:
makepkg -si
```

For Epson's newer `epsonscan2`, the official Epson download page often has newer `.deb`/`.rpm` packages that can be extracted:

```bash
# Extract Epson .rpm to get shared libs and PPD
rpm2cpio epsonscan2-bundle.rpm | cpio -idmv
```

### Print quality issues: wrong paper size or scaling

```bash
lpoptions -p "PrinterName" -l | grep -i media   # check supported sizes
lpoptions -p "PrinterName" -o media=A4           # set default media
lpoptions -p "PrinterName" -o fit-to-page=true   # auto-scale
```

For PDF scaling issues, the problem is often the application's print dialog, not CUPS. Try printing via CLI with explicit scaling:

```bash
lp -d "PrinterName" -o scaling=100 -o media=A4 file.pdf
```

---

*See also: Ch 53 (Session startup and service management), Ch 14 (GTK/Qt Wayland compatibility), Ch 83 (Bluetooth and wireless peripherals).*

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
