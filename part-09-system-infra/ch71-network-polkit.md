# Chapter 71 — Network Management and Polkit: nmtui, nm-applet, pkexec

## Overview

Two things silently break every new Hyprland/Sway setup: no network manager UI
(can't connect to WiFi) and no polkit agent (apps fail without error). This chapter
fixes both.

A fresh wlroots compositor session inherits almost nothing from GNOME or KDE's session
infrastructure. You get a compositor, a terminal, and silence — no authentication
dialogs, no system tray network icon, no automatic privilege escalation. Understanding
*why* these things are missing, and exactly which daemons fill each role, is the
difference between a working daily driver and an eternally-broken rice.

This chapter covers the full network management stack (NetworkManager, iwd, nmcli,
nmtui, nm-applet) and the polkit privilege framework — what it is, how it works, which
agents exist, and how to configure rules for a smooth, passwordless-where-appropriate
experience. See Ch 22 for system tray integration with Quickshell, Ch 53 for session
startup ordering, and Ch 70 for other system services commonly needed in custom setups.

---

## 71.1 The Problem

On a fresh wlroots-based compositor setup:
- No system tray → `nm-applet` doesn't visually appear
- No polkit agent → mounting USB drives fails silently, sudo GUI apps crash
- NetworkManager is installed but has no UI
- Result: users Google "Hyprland no internet" and "Thunar can't mount"

The root cause is that Wayland compositors — unlike full desktop environments — do not
auto-start session services. GNOME Shell launches `gnome-keyring-daemon`,
`evolution-source-registry`, polkit agents, and network indicators as part of its own
session. When you run raw Hyprland from a TTY or display manager, you inherit none of
that. Every daemon must be explicitly declared in your `exec-once` (Hyprland) or `exec`
(Sway) blocks, or in a `systemd --user` unit with the correct `PartOf=` and `WantedBy=`
targets.

The failure mode for missing polkit is particularly confusing because the error is often
invisible. Thunar silently refuses to mount, `gparted` opens and immediately closes,
Flatpak's GUI installer hangs — none of these print a useful message to stderr. The
polkit D-Bus call times out, the requesting application receives a generic "not
authorized" error, and the user has no idea why. This chapter surfaces those hidden
dependencies and provides definitive working configurations for each tool.

A secondary complication: different distributions ship polkit agents in different
packages. Arch puts `polkit-gnome-authentication-agent-1` under `/usr/lib/polkit-gnome/`,
Fedora puts it under `/usr/libexec/polkit-gnome-authentication-agent-1`, NixOS wraps it
in a derivation path. The configurations below note these differences explicitly.

## 71.2 NetworkManager TUI: nmtui

The fastest solution — works without any graphical tools:

```bash
# Install and enable NetworkManager (Arch/Manjaro)
sudo pacman -S networkmanager
sudo systemctl enable --now NetworkManager

# Fedora/RHEL
sudo dnf install NetworkManager
sudo systemctl enable --now NetworkManager

# Debian/Ubuntu
sudo apt install network-manager
sudo systemctl enable --now NetworkManager

# Launch the TUI
nmtui
```

`nmtui` provides a full ncurses interface that works in any terminal — including a raw
TTY before any compositor starts. This makes it indispensable for bootstrapping: before
you have a working Wayland session, `nmtui` in a TTY is how you connect to get packages.

The three main screens in `nmtui`:

- **Activate a connection**: Lists all saved and available networks. Use arrow keys to
  select, Enter to connect. WiFi networks show signal strength. This is the 99% use case.
- **Edit a connection**: Full connection editor. Configure static IP addresses, custom
  DNS servers, IPv6 settings, 802.1X enterprise authentication, and proxy settings.
  Changes here persist across reboots.
- **Set system hostname**: Modifies `/etc/hostname` and calls `hostnamectl`. Less useful
  for network connectivity but useful during initial system setup.

`nmtui` has zero graphical dependencies — it links against ncurses, not GTK or Qt. It
will work over SSH, in a framebuffer terminal, and in recovery mode. For a Wayland rice,
keeping `nmtui` as a fallback while using `nm-applet` or a GUI for daily use is good
practice. Add a keybind in your compositor config:

```conf
# hyprland.conf — open nmtui in a floating terminal
bind = SUPER, N, exec, foot -a nmtui nmtui
windowrulev2 = float, class:nmtui
windowrulev2 = size 800 600, class:nmtui
windowrulev2 = center, class:nmtui
```

```conf
# sway config equivalent
bindsym $mod+n exec foot --app-id nmtui nmtui
for_window [app_id="nmtui"] floating enable, resize set 800 600
```

## 71.3 nm-applet — System Tray Widget

```bash
# Install
sudo pacman -S network-manager-applet   # Arch
sudo dnf install nm-connection-editor   # Fedora (includes nm-applet)
sudo apt install network-manager-gnome  # Debian/Ubuntu

# Add to compositor startup
# hyprland.conf:
exec-once = nm-applet --indicator

# sway config:
exec nm-applet --indicator
```

`nm-applet` shows in the system tray (requires a StatusNotifierItem/SystemTray host such
as the one in Quickshell — see Ch 22 — or Waybar's `tray` module). Once running and
visible, left-click shows available networks with signal-strength indicators; right-click
gives access to VPN connections, connection editor, and "Enable Networking" toggle.

The `--indicator` flag is critical on Wayland. Without it, `nm-applet` tries to use a
legacy XEmbed tray protocol that does not exist on pure Wayland. With `--indicator`, it
uses the StatusNotifierItem protocol (SNI), which is what Waybar's tray and Quickshell's
SystemTray widget both implement.

**Waybar tray module configuration:**

```jsonc
// ~/.config/waybar/config
{
  "tray": {
    "icon-size": 18,
    "spacing": 8,
    "show-passive-items": true
  }
}
```

**In Quickshell SystemTray (Ch 22):** nm-applet appears automatically once running, as
a `SystemTrayItem` exposed via the `SystemTray` singleton. No additional configuration
needed on the Quickshell side — just ensure the applet is running.

**Theming nm-applet:** It respects GTK3 themes. Set `GTK_THEME=Adwaita:dark` in your
environment or configure via `~/.config/gtk-3.0/settings.ini`:

```ini
[Settings]
gtk-theme-name=Catppuccin-Mocha-Standard-Blue-Dark
gtk-icon-theme-name=Papirus-Dark
gtk-font-name=Inter 11
gtk-cursor-theme-name=Bibata-Modern-Ice
```

**nm-connection-editor** is nm-applet's companion GUI for editing connections. Launch it
directly when you need to configure 802.1X enterprise WiFi, complex VPN profiles, or
bonded/bridged interfaces:

```bash
nm-connection-editor
# Or open it from nm-applet: right-click → Edit Connections
```

## 71.4 iwgtk — Lightweight WiFi Manager

For setups using `iwd` instead of NetworkManager:

```bash
# Arch
sudo pacman -S iwd iwgtk
sudo systemctl enable --now iwd

# Disable wpa_supplicant if switching from NetworkManager/wpa_supplicant
sudo systemctl disable --now wpa_supplicant
sudo systemctl disable --now NetworkManager  # if fully replacing NM

# Launch GUI
iwgtk

# Or: iwctl (iwd's interactive CLI)
iwctl
```

`iwd` (iNet wireless daemon) is an Intel-developed replacement for `wpa_supplicant`. It
is faster to associate, handles roaming more gracefully, and has a cleaner architecture.
Its main tradeoff: it only handles WiFi. For ethernet, DHCP, DNS, and VPNs, you still
need either NetworkManager (configured to use `iwd` as its WiFi backend) or separate
daemons (`dhcpcd`/`dhclient` + `systemd-resolved`).

The two common configurations are:

1. **iwd standalone** (WiFi only, manage ethernet separately): Suitable for laptops
   where you handle ethernet via `systemd-networkd` and DNS via `systemd-resolved`.
2. **NetworkManager with iwd backend** (recommended for most users): NetworkManager
   handles the full stack, but delegates WiFi association to iwd for better performance.

```ini
# /etc/NetworkManager/conf.d/wifi-backend.conf
# Use this to make NetworkManager use iwd as its WiFi backend
[device]
wifi.backend=iwd
```

```bash
# After creating the config:
sudo systemctl restart NetworkManager
# Verify iwd is active:
systemctl status iwd
```

`iwgtk` provides a minimal GTK3 GUI showing available networks, signal strength, and
connection state. It is significantly lighter than nm-applet (no D-Bus service, no tray
daemon) but lacks VPN management. Ideal for minimal rices where you rarely switch
networks.

## 71.5 CLI Network Management Reference

```bash
# ── NetworkManager CLI (nmcli) ────────────────────────────────────────────────

# Scan and list available WiFi networks
nmcli device wifi list

# Force a rescan
nmcli device wifi rescan

# Connect to a new WiFi network (saves the connection profile)
nmcli device wifi connect "My SSID" password "hunter2"

# Connect to a saved connection by name
nmcli connection up "Home WiFi"

# Disconnect from a connection
nmcli connection down "Home WiFi"

# List all saved connection profiles
nmcli connection show

# Show detailed status of all network interfaces
nmcli device status

# Show IP addresses and routing
nmcli device show eth0

# Add a static IP connection
nmcli connection add type ethernet ifname eth0 con-name "static-eth" \
  ipv4.method manual \
  ipv4.addresses "192.168.1.50/24" \
  ipv4.gateway "192.168.1.1" \
  ipv4.dns "1.1.1.1,8.8.8.8"

# Bring an interface up/down
nmcli device connect eth0
nmcli device disconnect eth0

# Enable/disable WiFi radio
nmcli radio wifi on
nmcli radio wifi off

# ── iwd CLI (iwctl) ──────────────────────────────────────────────────────────

iwctl
# Interactive prompt:
[iwd]# device list                    # list WiFi devices
[iwd]# station wlan0 scan             # scan for networks
[iwd]# station wlan0 get-networks     # list scan results
[iwd]# station wlan0 connect "SSID"   # connect (prompts for passphrase)
[iwd]# station wlan0 show             # show current connection state
[iwd]# known-networks list            # show saved networks
[iwd]# known-networks "SSID" forget   # remove saved network
[iwd]# quit

# Non-interactive iwd usage:
iwctl --passphrase "hunter2" station wlan0 connect "SSID"
```

For scripting network checks (useful in status bar scripts or startup conditions):

```bash
#!/usr/bin/env bash
# check-network.sh — used in Waybar custom modules or startup scripts

# Check if any interface has an IP
if nmcli -t -f STATE general | grep -q "connected"; then
  IFACE=$(nmcli -t -f DEVICE,STATE device | grep ":connected" | head -1 | cut -d: -f1)
  IP=$(nmcli -g IP4.ADDRESS device show "$IFACE" | head -1 | cut -d/ -f1)
  SSID=$(nmcli -t -f active,ssid device wifi | grep "^yes" | cut -d: -f2)
  echo "  $SSID ($IP)"
else
  echo "  Disconnected"
fi
```

## 71.6 DNS Configuration

```bash
# Check current DNS resolver status
resolvectl status
cat /etc/resolv.conf

# Show per-interface DNS settings
resolvectl dns
resolvectl domain

# Flush DNS cache
resolvectl flush-caches

# Manually query a name through systemd-resolved
resolvectl query example.com
```

```bash
# Set custom DNS via NetworkManager (per-connection override)
nmcli connection modify "WiFi-name" ipv4.dns "1.1.1.1 8.8.8.8"
nmcli connection modify "WiFi-name" ipv4.ignore-auto-dns yes
nmcli connection down "WiFi-name" && nmcli connection up "WiFi-name"

# For IPv6 DNS as well:
nmcli connection modify "WiFi-name" ipv6.dns "2606:4700:4700::1111"
nmcli connection modify "WiFi-name" ipv6.ignore-auto-dns yes
```

**Setting up systemd-resolved as the system resolver:**

```bash
sudo systemctl enable --now systemd-resolved

# Point /etc/resolv.conf at the stub resolver
sudo ln -sf /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf
```

```ini
# /etc/systemd/resolved.conf
# Global DNS fallback (used when per-interface DNS is not set)
[Resolve]
DNS=1.1.1.1 1.0.0.1 2606:4700:4700::1111
FallbackDNS=8.8.8.8 8.8.4.4
DNSSEC=allow-downgrade
DNSOverTLS=opportunistic
Cache=yes
```

**NetworkManager + systemd-resolved integration** (avoids DNS conflicts):

```ini
# /etc/NetworkManager/conf.d/dns.conf
[main]
dns=systemd-resolved
```

This makes NetworkManager push per-connection DNS to `systemd-resolved` rather than
writing to `/etc/resolv.conf` directly. With this configuration, the stub resolver
handles all queries, NetworkManager handles connection lifecycle, and there is no
conflict between the two.

---

## 71.7 What Polkit Is

Polkit (formerly PolicyKit) is the privilege escalation framework for Linux desktops.
When a GUI app needs root access (mounting drives, installing packages, changing system
settings), it sends a request to polkit, which asks the user for authentication via an
**authentication agent** — a dialog that appears asking for your password.

The polkit architecture has three components:

1. **The polkitd daemon**: A system D-Bus service (`org.freedesktop.PolicyKit1`) that
   receives authorization requests and evaluates rules. It runs as root and is started
   automatically by D-Bus activation — you do not need to start it manually.
2. **The requesting application**: Any process that calls `polkit_check_authorization()`
   or uses `pkexec`. The requesting process does not need to be running as root.
3. **The authentication agent**: A per-session process that receives the dialog request
   from polkitd, renders a password prompt, and returns the result. This is the component
   you must start in your Wayland session.

**Without a polkit agent running:**
- Thunar cannot mount USB drives → silently fails
- NetworkManager cannot manage system-wide connections → silently fails
- Flatpak GUI package managers cannot install → silently fails
- System settings apps that need root cannot apply changes → silently fails
- `pkexec` commands in scripts exit with error 126 ("not authorized")

The D-Bus call chain when a polkit agent is missing: the requesting app sends an
`CheckAuthorization` call to `polkitd`, polkitd determines that an authentication
challenge is needed and sends a `BeginAuthentication` signal to any registered agents
on the session bus — but if no agent is registered, the signal goes nowhere, the
authorization times out (typically 30 seconds), and the requesting app gets `NOT_AUTHORIZED`.

```bash
# Verify polkitd is running (should always be true if polkit package is installed)
systemctl status polkit

# Check if an agent is registered on the session bus
busctl --user list | grep polkit

# The output when an agent IS running should include something like:
# org.freedesktop.PolicyKit1.AuthenticationAgent
```

## 71.8 Available Polkit Agents

| Agent | Package | Toolkit | Binary Path | Notes |
|-------|---------|---------|-------------|-------|
| `polkit-gnome-authentication-agent-1` | `polkit-gnome` | GTK3 | `/usr/lib/polkit-gnome/` (Arch)<br>`/usr/libexec/` (Fedora) | Most common, works everywhere |
| `lxqt-policykit` | `lxqt-policykit` | Qt5/Qt6 | `/usr/bin/lxqt-policykit-agent` | Good for Qt rices |
| `kauth` / `polkit-kde-agent-1` | `polkit-kde-agent` | Qt/KDE | `/usr/lib/polkit-1-kde-authentication-agent-1` | KDE Plasma agent |
| `mate-polkit` | `mate-polkit` | GTK3 | `/usr/lib/mate-polkit/polkit-mate-authentication-agent-1` | MATE desktop agent |
| `xfce-polkit` | `xfce-polkit` | GTK3 | `/usr/lib/xfce-polkit/xfce-polkit` | XFCE agent, works standalone |
| `hyprpolkitagent` | `hyprpolkitagent` | Qt/Hypr | `/usr/lib/hyprpolkitagent` | Native Hyprland styling |
| `pantheon-agent-polkit` | `pantheon-agent-polkit` | GTK3 | varies | elementary OS |

**Choosing the right agent for your rice:**

For GTK-themed setups (Catppuccin, Dracula, Nord with GTK): use `polkit-gnome`. For Qt
setups (KvantumManager, Qt themes): use `lxqt-policykit` or `polkit-kde-agent`. For
Hyprland with native look: `hyprpolkitagent` renders dialogs that respect Hyprland's
borders and gaps configuration. The functional behavior is identical — the choice is
purely aesthetic and toolkit-consistency.

## 71.9 Starting a Polkit Agent

**Hyprland:**
```conf
# hyprland.conf — MUST use exec-once, not exec
# Using polkit-gnome (most common)
exec-once = /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1

# On Fedora/RHEL (different path):
# exec-once = /usr/libexec/polkit-gnome-authentication-agent-1

# Using lxqt-policykit (for Qt rices):
# exec-once = /usr/bin/lxqt-policykit-agent

# Using hyprpolkitagent (native Hyprland):
# exec-once = /usr/lib/hyprpolkitagent
```

**Sway:**
```conf
# sway config
exec /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1
# Note: sway uses 'exec' not 'exec-once'; sway tracks PIDs and won't double-start
```

**As a systemd user service (recommended for reliability):**

Using `systemd --user` ensures the agent restarts if it crashes, starts at the right
point in session initialization, and can be managed with standard `systemctl` commands.

```ini
# ~/.config/systemd/user/polkit-agent.service
[Unit]
Description=Polkit Authentication Agent
PartOf=graphical-session.target
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1
Restart=on-failure
RestartSec=1

[Install]
WantedBy=graphical-session.target
```

```bash
# Enable and start the service
systemctl --user enable --now polkit-agent.service

# Verify it is running
systemctl --user status polkit-agent.service

# Remove exec-once from hyprland.conf once systemd manages it
# (to avoid double-starting the agent)
```

**NixOS (Home Manager):**
```nix
# home.nix or flake home configuration
security.polkit.enable = true;

systemd.user.services.polkit-gnome-authentication-agent-1 = {
  description = "polkit-gnome-authentication-agent-1";
  wantedBy = [ "graphical-session.target" ];
  after = [ "graphical-session.target" ];
  serviceConfig = {
    Type = "simple";
    ExecStart = "${pkgs.polkit_gnome}/libexec/polkit-gnome-authentication-agent-1";
    Restart = "on-failure";
    RestartSec = 1;
  };
};
```

**Session startup order matters.** The polkit agent must start *after* the D-Bus session
bus is available and *after* the graphical session target. See Ch 53 for details on
`graphical-session.target` ordering. If you start the agent too early (before D-Bus),
it will fail to register and exit silently.

## 71.10 Testing Polkit

```bash
# Test 1: pkexec — should trigger a password dialog if agent is running
pkexec ls /root
# Expected: a graphical password dialog appears
# If no dialog appears and the command returns "Error executing command as another user":
#   → the agent is not running or not registered on the session bus

# Test 2: Check agent registration on session D-Bus
busctl --user introspect org.freedesktop.PolicyKit1 /org/freedesktop/PolicyKit1/AuthenticationAgent 2>/dev/null
# If the introspection returns data, an agent is registered

# Test 3: Mount a USB drive via udisks2 using pkexec
udisksctl mount -b /dev/sdb1
# (udisksctl uses polkit internally for system-level mounts)

# Test 4: Trigger through Thunar
# Plug in a USB drive → open Thunar → click the drive in the sidebar
# Expected: password dialog appears on first mount
# Failure: drive does not appear, or Thunar shows "Not authorized" briefly

# Test 5: Directly invoke a polkit action via dbus
dbus-send --system --print-reply \
  --dest=org.freedesktop.PolicyKit1 \
  /org/freedesktop/PolicyKit1/Authority \
  org.freedesktop.PolicyKit1.Authority.CheckAuthorization \
  "(sa{sv})org.freedesktop.udisks2.filesystem-mount {}" \
  b:true u:0
```

## 71.11 Polkit Rules (Advanced)

Polkit's rule engine runs JavaScript. Rules files are in `/etc/polkit-1/rules.d/`
(system) or `~/.local/share/polkit-1/rules.d/` (user, supported in newer polkit).
Files are evaluated in filename order (lower numbers first).

```javascript
// /etc/polkit-1/rules.d/10-udisks-user-mount.rules
// Allow users in the "users" group to mount/unmount removable drives without a password

polkit.addRule(function(action, subject) {
    var mountActions = [
        "org.freedesktop.udisks2.filesystem-mount",
        "org.freedesktop.udisks2.filesystem-unmount-others",
        "org.freedesktop.udisks2.eject-media",
        "org.freedesktop.udisks2.power-off-drive"
    ];
    if (mountActions.indexOf(action.id) !== -1 &&
        subject.local && subject.active && subject.isInGroup("users")) {
        return polkit.Result.YES;
    }
});
```

```javascript
// /etc/polkit-1/rules.d/20-network-manager.rules
// Allow wheel group members to manage NetworkManager system connections without password

polkit.addRule(function(action, subject) {
    if (action.id.indexOf("org.freedesktop.NetworkManager.") === 0 &&
        subject.isInGroup("wheel")) {
        return polkit.Result.YES;
    }
});
```

```javascript
// /etc/polkit-1/rules.d/50-allow-colord.rules
// Allow colord color management without a prompt (common in display calibration)

polkit.addRule(function(action, subject) {
    if (action.id === "org.freedesktop.color-manager.create-device" ||
        action.id === "org.freedesktop.color-manager.create-profile" ||
        action.id === "org.freedesktop.color-manager.delete-device" ||
        action.id === "org.freedesktop.color-manager.delete-profile" ||
        action.id === "org.freedesktop.color-manager.modify-device" ||
        action.id === "org.freedesktop.color-manager.modify-profile") {
        return polkit.Result.YES;
    }
});
```

```bash
# List all available polkit actions on your system:
pkaction --verbose 2>/dev/null | grep -E "^Action:|^\s+description:"

# Or filter for a specific subsystem:
pkaction | grep udisks
pkaction | grep NetworkManager
pkaction | grep flatpak

# Test a specific action against your user:
pkcheck --action-id org.freedesktop.udisks2.filesystem-mount --process $$ -u
```

**polkit-1 vs. polkit legacy (0.105 and older):** Older distributions may use
`/etc/polkit-1/localauthority/` with `.pkla` files instead of JavaScript rules. The
`.pkla` format is XML-like and does not support conditional logic. If your system's
`pkaction --version` shows < 0.106, consult the legacy documentation. All examples in
this chapter target polkit ≥ 0.106 (JavaScript rules).

## 71.12 VPN Setup

```bash
# ── OpenVPN ──────────────────────────────────────────────────────────────────

# Install the NetworkManager OpenVPN plugin
sudo pacman -S networkmanager-openvpn          # Arch
sudo dnf install NetworkManager-openvpn-gnome  # Fedora
sudo apt install network-manager-openvpn-gnome # Debian/Ubuntu

# Import an .ovpn configuration file
nmcli connection import type openvpn file ~/Downloads/client.ovpn

# Connect and disconnect
nmcli connection up "client"    # name from the .ovpn file's 'dev' or filename
nmcli connection down "client"

# ── WireGuard ────────────────────────────────────────────────────────────────

# Option A: wg-quick (simple, no NetworkManager integration)
sudo pacman -S wireguard-tools
# Place your config at /etc/wireguard/wg0.conf
sudo wg-quick up wg0
sudo wg-quick down wg0

# Enable as a systemd service (starts at boot):
sudo systemctl enable --now wg-quick@wg0

# Option B: NetworkManager WireGuard (integrated management)
sudo pacman -S networkmanager-wireguard  # if available for your distro
# Or use nmcli directly:
nmcli connection add type wireguard \
  con-name "wg-vpn" \
  ifname wg0 \
  wireguard.private-key "$(wg genkey)" \
  wireguard.listen-port 51820

# ── Tailscale ────────────────────────────────────────────────────────────────

sudo pacman -S tailscale
sudo systemctl enable --now tailscaled
sudo tailscale up --accept-routes --accept-dns

# Check status:
tailscale status
tailscale ping some-machine-name

# ── VPN status in Waybar ─────────────────────────────────────────────────────

# Custom Waybar module showing VPN state:
```

```jsonc
// ~/.config/waybar/config — custom VPN indicator
{
  "custom/vpn": {
    "exec": "~/.config/waybar/scripts/vpn-status.sh",
    "interval": 5,
    "format": "{}",
    "tooltip": true
  }
}
```

```bash
#!/usr/bin/env bash
# ~/.config/waybar/scripts/vpn-status.sh

if nmcli -t -f TYPE,STATE connection show --active | grep -q "vpn:activated"; then
  VPN_NAME=$(nmcli -t -f NAME,TYPE connection show --active | grep ":vpn" | head -1 | cut -d: -f1)
  echo "{\"text\": \" $VPN_NAME\", \"class\": \"connected\", \"tooltip\": \"VPN: $VPN_NAME\"}"
elif ip link show tailscale0 &>/dev/null && ip link show tailscale0 | grep -q "UP"; then
  TS_IP=$(tailscale ip -4 2>/dev/null)
  echo "{\"text\": \" Tailscale\", \"class\": \"tailscale\", \"tooltip\": \"Tailscale: $TS_IP\"}"
else
  echo "{\"text\": \" No VPN\", \"class\": \"disconnected\", \"tooltip\": \"No VPN active\"}"
fi
```

---

## Troubleshooting

### nm-applet not appearing in system tray

```bash
# Check if nm-applet is running:
pgrep -a nm-applet

# Check if it started with --indicator:
pgrep -a nm-applet | grep -c indicator
# Should return 1; if 0, it started without the flag and uses XEmbed (won't work on Wayland)

# Verify your tray host is running:
# For Waybar: check that "tray" is in your modules-right or modules-left
# For Quickshell: check Ch 22 for SystemTray component setup

# Check for SNI registration on D-Bus:
busctl --user list | grep StatusNotifier
# Should show: com.canonical.StatusNotifierWatcher

# Restart nm-applet with correct flag:
pkill nm-applet
nm-applet --indicator &
```

### Polkit agent not showing dialogs

```bash
# Step 1: Verify polkitd is running
systemctl status polkit
# Should show: active (running)

# Step 2: Verify your agent process is running
pgrep -a polkit
# Should show the agent binary

# Step 3: Check if agent is registered on session D-Bus
busctl --user list 2>/dev/null | grep -i polkit
# Look for: org.gnome.PolicyKit1.AuthenticationAgent or similar

# Step 4: Check for D-Bus session bus availability
echo $DBUS_SESSION_BUS_ADDRESS
# Must not be empty; if empty, D-Bus session is not set up

# Step 5: Restart the agent with verbose output for debugging
pkill polkit-gnome-authentication-agent-1
/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1 2>&1 &
# Watch for errors in the output

# Step 6: Verify with pkexec
pkexec --disable-internal-agent id
# If this shows your UID, polkit rules work even without the agent
# If this hangs/fails, polkitd itself has an issue
```

### NetworkManager not managing an interface

```bash
# Check if the interface is managed:
nmcli device status
# Look for "unmanaged" in the STATE column

# Interfaces can be unmanaged due to:
# 1. Listed in /etc/NetworkManager/conf.d/unmanaged.conf
cat /etc/NetworkManager/conf.d/*.conf 2>/dev/null | grep unmanaged

# 2. Managed by another service (systemd-networkd)
systemctl is-active systemd-networkd
# If active, it may have claimed the interface before NM

# 3. Interface has a custom MAC that NM doesn't recognize
# Force-manage the interface:
nmcli device set eth0 managed yes

# Check NetworkManager logs for why it ignored the interface:
journalctl -u NetworkManager -n 50 --no-pager
```

### DNS resolution failures

```bash
# Test resolution through different paths:
# 1. Direct test via systemd-resolved:
resolvectl query google.com

# 2. Test via /etc/resolv.conf:
nslookup google.com

# 3. Test with explicit DNS server:
dig @1.1.1.1 google.com

# Common issue: /etc/resolv.conf points to wrong file
ls -la /etc/resolv.conf
# Should be: /etc/resolv.conf -> /run/systemd/resolve/stub-resolv.conf

# If it's a plain file (not a symlink) from a previous install:
sudo rm /etc/resolv.conf
sudo ln -sf /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf
sudo systemctl restart systemd-resolved
sudo systemctl restart NetworkManager

# Check for DNS conflicts between NM and resolved:
resolvectl status
# Each interface should show the DNS servers NM configured
```

### iwd fails to connect to enterprise WiFi (WPA2-Enterprise / 802.1X)

```ini
# iwd does support 802.1X but requires manual profile creation
# Create: /var/lib/iwd/<SSID>.8021x

[Security]
EAP-Method=PEAP
EAP-Identity=username@domain.com
EAP-PEAP-Phase2-Method=MSCHAPV2
EAP-PEAP-Phase2-Identity=username@domain.com
EAP-PEAP-Phase2-Password=yourpassword

[Settings]
AutoConnect=true
```

```bash
# Verify the profile was loaded:
iwctl known-networks list
# If the SSID appears, try connecting:
iwctl station wlan0 connect "Corporate-WiFi"
```

---

## Summary

| Component | Purpose | Start Command | Config Location |
|-----------|---------|---------------|-----------------|
| `NetworkManager` | Full network stack management | `systemctl enable --now NetworkManager` | `/etc/NetworkManager/` |
| `nmtui` | TUI for WiFi/connection management | `nmtui` | n/a (reads NM profiles) |
| `nm-applet` | System tray network indicator | `exec-once = nm-applet --indicator` | GTK3 settings |
| `nmcli` | CLI for all NM operations | (always available) | n/a |
| `iwd` | Lightweight WiFi daemon | `systemctl enable --now iwd` | `/var/lib/iwd/` |
| `iwgtk` | GUI for iwd | `iwgtk` | n/a |
| `polkit-gnome-authentication-agent-1` | GTK polkit agent | `exec-once = /usr/lib/polkit-gnome/...` | `/etc/polkit-1/rules.d/` |
| `lxqt-policykit-agent` | Qt polkit agent | `exec-once = lxqt-policykit-agent` | same |
| `systemd-resolved` | DNS resolver/cache | `systemctl enable --now systemd-resolved` | `/etc/systemd/resolved.conf` |

Both NetworkManager and polkit follow the same pattern: they are system-level daemons
that start automatically, but they need *per-session* UI components (nm-applet, polkit
agent) started explicitly in your compositor startup. Get these two daemons right and
the silent failures disappear.

Cross-references: Ch 22 (Quickshell SystemTray for nm-applet), Ch 53 (session startup
ordering and `graphical-session.target`), Ch 70 (other system services: pipewire,
bluetooth, power management).

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
