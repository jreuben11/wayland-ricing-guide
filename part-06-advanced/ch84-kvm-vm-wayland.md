# Chapter 84 — KVM/QEMU Virtual Machines for Wayland Development and Testing

## Contents

- [Overview](#overview)
- [84.1 Host Prerequisites](#841-host-prerequisites)
- [84.2 Tier 1: Virgl — 3D-Accelerated Wayland VMs](#842-tier-1-virgl-3d-accelerated-wayland-vms)
  - [virtio-gpu-gl vs virtio-vga-gl](#virtio-gpu-gl-vs-virtio-vga-gl)
  - [Display Path Options](#display-path-options)
  - [Guest Requirements](#guest-requirements)
  - [virt-manager XML — Optimal Virgl Setup](#virt-manager-xml-optimal-virgl-setup)
  - [QEMU CLI Equivalent](#qemu-cli-equivalent)
  - [Venus — Vulkan in the Guest (QEMU 9.2+)](#venus-vulkan-in-the-guest-qemu-92)
  - [Resolution and Multi-Monitor](#resolution-and-multi-monitor)
- [84.3 CPU Optimization](#843-cpu-optimization)
  - [CPU Model](#cpu-model)
  - [CPU Pinning](#cpu-pinning)
  - [isolcpus (aggressive, optional)](#isolcpus-aggressive-optional)
- [84.4 Memory Optimization](#844-memory-optimization)
  - [Hugepages](#hugepages)
  - [Memory Balloon (disable for performance)](#memory-balloon-disable-for-performance)
  - [NUMA topology (multi-socket hosts)](#numa-topology-multi-socket-hosts)
- [84.5 Storage Optimization](#845-storage-optimization)
- [84.6 Network and Clipboard](#846-network-and-clipboard)
  - [VirtIO Network](#virtio-network)
  - [Clipboard Sharing (SPICE)](#clipboard-sharing-spice)
  - [SSH + X11 Forwarding alternative](#ssh-x11-forwarding-alternative)
- [84.7 Audio in VMs](#847-audio-in-vms)
  - [VirtIO Sound (kernel 5.14+)](#virtio-sound-kernel-514)
  - [PipeWire JACK Bridge (host-side audio from guest)](#pipewire-jack-bridge-host-side-audio-from-guest)
- [84.8 Tier 2: Looking Glass — Shared GPU Frame Buffer](#848-tier-2-looking-glass-shared-gpu-frame-buffer)
  - [Setup Overview](#setup-overview)
  - [IVSHMEM Device](#ivshmem-device)
  - [Host Client](#host-client)
  - [/etc/tmpfiles.d/10-looking-glass.conf](#etctmpfilesd10-looking-glassconf)
- [84.9 Tier 3: VFIO GPU Passthrough](#849-tier-3-vfio-gpu-passthrough)
  - [Identify GPU IOMMU Groups](#identify-gpu-iommu-groups)
  - [Bind GPU to vfio-pci](#bind-gpu-to-vfio-pci)
  - [Libvirt XML — PCI Passthrough](#libvirt-xml-pci-passthrough)
  - [Evdev Input Passthrough](#evdev-input-passthrough)
- [84.10 Single GPU Passthrough — Complete libvirt Hook Implementation](#8410-single-gpu-passthrough-complete-libvirt-hook-implementation)
  - [Directory structure](#directory-structure)
  - [`/etc/libvirt/hooks/qemu` (dispatcher)](#etclibvirthooksqemu-dispatcher)
  - [`start.sh` — tear down the Wayland session](#startsh-tear-down-the-wayland-session)
  - [`revert.sh` — restore the Wayland session](#revertsh-restore-the-wayland-session)
  - [Wayland compositor-specific teardown notes](#wayland-compositor-specific-teardown-notes)
  - [AMD RDNA GPU reset bug](#amd-rdna-gpu-reset-bug)
- [84.12 Nested Wayland Compositors](#8412-nested-wayland-compositors)
  - [Nested Quickshell Testing](#nested-quickshell-testing)
- [84.13 VM Snapshots for Safe Ricing](#8413-vm-snapshots-for-safe-ricing)
- [84.14 Full Optimized virt-manager XML Template](#8414-full-optimized-virt-manager-xml-template)
- [84.15 NixOS VM Testing](#8415-nixos-vm-testing)
- [84.16 KVM Limitations for Wayland Ricing](#8416-kvm-limitations-for-wayland-ricing)
  - [Hard Limits — Unsolvable Without VFIO + Physical Display](#hard-limits-unsolvable-without-vfio-physical-display)
  - [Performance Limits](#performance-limits)
  - [Protocol and Feature Limits](#protocol-and-feature-limits)
  - [What VMs Are Actually Good For](#what-vms-are-actually-good-for)
- [84.17 Performance Checklist](#8417-performance-checklist)
- [84.18 Common Issues](#8418-common-issues)

---


## Overview

Running Wayland desktops in KVM virtual machines lets you iterate on configs,
test compositors, and experiment with ricing without risking your daily driver.
The critical insight: Wayland compositors need a GPU. With the wrong VM setup
you get a black screen or software rendering that makes animations useless.
This chapter covers three tiers:

| Tier | Mechanism | Use case |
|------|-----------|----------|
| **Virgl** | virtio-gpu-gl, host GPU shared via Mesa | Daily ricing dev, compositor testing |
| **Looking Glass** | IVSHMEM + KVMFR frame buffer | Near-native performance, shared display |
| **VFIO passthrough** | Full GPU dedicated to VM | Gaming, HDR testing, driver debugging |

---

## 84.1 Host Prerequisites

```bash
# Arch
sudo pacman -S qemu-full virt-manager virt-viewer libvirt dnsmasq \
               iptables-nft nftables bridge-utils openbsd-netcat

# Enable and start libvirt
sudo systemctl enable --now libvirtd
sudo usermod -aG libvirt,kvm $(whoami)
# Log out and back in for group to take effect

# Verify KVM is available
ls /dev/kvm && echo "KVM OK"
lsmod | grep kvm
```

**IOMMU (needed for VFIO passthrough, optional for virgl):**

```
# /etc/default/grub — add to GRUB_CMDLINE_LINUX_DEFAULT
# Intel:
intel_iommu=on iommu=pt
# AMD:
amd_iommu=on iommu=pt

sudo grub-mkconfig -o /boot/grub/grub.cfg
# Reboot, then verify:
dmesg | grep -i iommu | head -5
```

---

## 84.2 Tier 1: Virgl — 3D-Accelerated Wayland VMs

**Virgl** (VirGL Renderer) translates guest OpenGL calls through a Gallium IR
layer to the host GPU. As of virglrenderer v1.2.0 (January 2026) it is
considered feature-complete at OpenGL 4.3 / GLES 3.2 and is in maintenance
mode. Development focus has shifted to Venus (Vulkan) and vDRM.

### virtio-gpu-gl vs virtio-vga-gl

| Device | VGA compat shim | When to use |
|--------|----------------|-------------|
| `virtio-gpu-gl` | No | UEFI/OVMF guests — all modern Linux VMs |
| `virtio-vga-gl` | Yes (+8 MB PCI BAR) | BIOS/SeaBIOS guests, Windows guests, any guest that pokes VGA registers |

Use `virtio-gpu-gl` for Wayland Linux VMs booted with OVMF. The VGA shim adds
overhead and PCI address space consumption with no benefit for UEFI guests.

### Display Path Options

| Flag | Best for | Notes |
|------|----------|-------|
| `-display sdl,gl=on` | Local desktop (fastest) | Set `SDL_VIDEODRIVER=wayland` on Wayland host |
| `-display gtk,gl=on` | virt-manager integration | Native Wayland window |
| `-spice gl=on,...` + virt-viewer | Remote / libvirt-managed | Frames via Unix socket, slightly higher overhead |

SDL GL is noticeably smoother than SPICE GL for local use — prefer it when
not using virt-manager.

### Guest Requirements

```bash
# Inside the guest (Arch example)
sudo pacman -S mesa xf86-video-virtio
```

The guest's Mesa automatically detects `virtio-gpu` and uses the virgl driver.
Check: `glxinfo | grep renderer` → should show `virgl`. If it shows `llvmpipe`,
virgl failed to initialise — verify `gl=on` in the display config (see below).

### virt-manager XML — Optimal Virgl Setup

In virt-manager: Edit → Preferences → Enable XML editing.
Then open VM → XML tab and replace the `<video>` section:

```xml
<video>
  <model type="virtio" heads="1" primary="yes">
    <acceleration accel3d="yes"/>
  </model>
  <alias name="video0"/>
</video>
```

And the display:
```xml
<graphics type="spice" autoport="no" listen="127.0.0.1" port="5900">
  <listen type="address" address="127.0.0.1"/>
  <gl enable="yes" rendernode="/dev/dri/renderD128"/>
  <image compression="off"/>
</graphics>
```

> **Critical:** `gl enable="yes"` in the SPICE config is what enables virgl.
> Without it, `accel3d="yes"` in the video model does nothing.
> Use `virt-viewer` (not VNC clients) to connect — it supports SPICE+GL.

### QEMU CLI Equivalent

```bash
qemu-system-x86_64 \
  -enable-kvm \
  -m 8G \
  -smp cores=4,threads=2 \
  -cpu host \
  -machine type=q35,accel=kvm \
  -device virtio-gpu-gl,xres=2560,yres=1440 \
  -display sdl,gl=on \
  -device virtio-serial \
  -chardev spicevmc,id=vdagent,name=vdagent \
  -device virtserialport,chardev=vdagent,name=com.redhat.spice.0 \
  -drive file=disk.qcow2,if=virtio,cache=writeback,discard=unmap \
  -netdev user,id=net0 \
  -device virtio-net-pci,netdev=net0 \
  ...
```

For `-display`: use `sdl,gl=on` for a local window, `spice-app,gl=on` for
virt-viewer. GTK display (`-display gtk,gl=on`) also works.

### Venus — Vulkan in the Guest (QEMU 9.2+)

**Venus** is the Vulkan counterpart to virgl. QEMU 9.2.0 (December 2024)
merged Venus without patches — it is now in mainline QEMU.

```bash
# QEMU CLI — Venus requires blob memory
qemu-system-x86_64 \
  -enable-kvm \
  -m 8G \
  -object memory-backend-memfd,id=mem1,size=8G \
  -machine type=q35,accel=kvm,memory-backend=mem1 \
  -device virtio-gpu-gl,blob=on,hostmem=4G,venus=on \
  -display sdl,gl=on \
  ...
```

**Requirements:**
- QEMU 9.2.0+
- Guest kernel 5.16+ (kernel 6.13+ for RADV dGPU host)
- Host Vulkan driver: RADV 21.1+, ANV 21.1+, or Lavapipe 22.1+

**Guest packages:**
```bash
sudo pacman -S mesa vulkan-mesa-layers vulkan-virtio
# Verify Vulkan works in guest:
vulkaninfo | grep deviceName   # should show "virtio_gpu"
```

**What works:** Vulkan 1.3 API, DXVK, Zink (OpenGL via Vulkan), vkd3d-proton.

**What does not work with Venus:**
- NVIDIA proprietary host driver — EGL_NOT_INITIALIZED errors (tracker issue #524)
- Pre-GFX9 AMD GPUs (Polaris/Fiji) — lack `VK_EXT_image_drm_format_modifier`
- Intel Meteor Lake / Xe — requires kernel 6.16+ and QEMU 11.0+

For most Arch setups (RADV or ANV host), Venus works reliably in QEMU 9.2.
Venus is the preferred path for any guest workload that needs Vulkan.

### Resolution and Multi-Monitor

```xml
<!-- In the video model, set virtual display size -->
<model type="virtio" heads="2" primary="yes">
  <acceleration accel3d="yes"/>
</model>
```

Inside the guest, use `xrandr` (for XWayland) or compositor monitor config.
virtio-gpu supports virtual resolutions up to the host's framebuffer limit.

For Hyprland:
```conf
# /etc/hypr/hyprland.conf inside VM
monitor = Virtual-1, 2560x1440@60, 0x0, 1
monitor = Virtual-2, 1920x1080@60, 2560x0, 1
```

---

## 84.3 CPU Optimization

### CPU Model

Always use `-cpu host` (or `host-passthrough` in libvirt XML):

```xml
<cpu mode="host-passthrough" check="none" migratable="on">
  <topology sockets="1" dies="1" cores="4" threads="2"/>
</cpu>
```

`host-passthrough` exposes the exact CPU features your physical CPU has,
which matters for AVX/AVX2 (used by Mesa shader compilation).

### CPU Pinning

For a 6-core host running a 4-core VM, pin guest vCPUs to isolated host cores:

```xml
<cputune>
  <vcpupin vcpu="0" cpuset="2"/>
  <vcpupin vcpu="1" cpuset="3"/>
  <vcpupin vcpu="2" cpuset="4"/>
  <vcpupin vcpu="3" cpuset="5"/>
  <emulatorpin cpuset="0,1"/>   <!-- QEMU emulator threads on cores 0-1 -->
</cputune>
```

Identify available cores: `lscpu -e`. Leave 2+ cores for the host.

### isolcpus (aggressive, optional)

Add to kernel cmdline to fully remove cores from the host scheduler:
```
isolcpus=2,3,4,5 nohz_full=2,3,4,5 rcu_nocbs=2,3,4,5
```
Then pin the VM to those cores. Reduces scheduling jitter significantly.

---

## 84.4 Memory Optimization

### Hugepages

Hugepages reduce TLB pressure for memory-intensive workloads (GPU rendering,
shader compilation):

```bash
# /etc/sysctl.d/hugepages.conf
vm.nr_hugepages = 4096    # 4096 × 2MB = 8GB reserved for VMs

# Apply immediately:
sudo sysctl -p /etc/sysctl.d/hugepages.conf
```

In libvirt XML:
```xml
<memoryBacking>
  <hugepages/>
  <locked/>   <!-- prevent memory from being swapped out -->
</memoryBacking>
```

### Memory Balloon (disable for performance)

The memory balloon driver lets the host reclaim guest RAM but adds latency.
For a dedicated ricing VM, disable it:

```xml
<!-- Remove or comment out: -->
<!-- <memballoon model="virtio"/> -->
<memballoon model="none"/>
```

### NUMA topology (multi-socket hosts)

If your CPU has multiple NUMA nodes (Threadripper, dual-socket Xeon):
```xml
<cpu ...>
  <numa>
    <cell id="0" cpus="0-3" memory="8388608" unit="KiB" memAccess="shared"/>
  </numa>
</cpu>
```

---

## 84.5 Storage Optimization

```xml
<disk type="file" device="disk">
  <driver name="qemu" type="qcow2"
          cache="writeback"       <!-- writeback: safe + fast -->
          io="threads"            <!-- threaded I/O -->
          discard="unmap"         <!-- TRIM support -->
          detect_zeroes="unmap"/>
  <source file="/var/lib/libvirt/images/arch-rice.qcow2"/>
  <target dev="vda" bus="virtio"/>
</disk>
```

**Raw images** are faster than qcow2 for write-heavy workloads (shader caches,
package installation). Use qcow2 for snapshots during ricing experimentation.

**virtiofs** (shared host directory, faster than 9p):

```xml
<filesystem type="mount" accessmode="passthrough">
  <driver type="virtiofs"/>
  <binary path="/usr/lib/qemu/virtiofsd"/>
  <source dir="/home/user/shared"/>
  <target dir="host_shared"/>
</filesystem>
```

Guest mount:
```bash
sudo mount -t virtiofs host_shared /mnt/shared
# or in /etc/fstab:
host_shared /mnt/shared virtiofs defaults 0 0
```

---

## 84.6 Network and Clipboard

### VirtIO Network

```xml
<interface type="network">
  <source network="default"/>
  <model type="virtio"/>
  <driver name="vhost"/>    <!-- vhost-net: kernel-space virtio, much faster -->
</interface>
```

### Clipboard Sharing (SPICE)

The `spice-vdagent` daemon handles clipboard sync between host and guest:

```bash
# Guest
sudo pacman -S spice-vdagent
sudo systemctl enable --now spice-vdagentd
```

With Wayland compositors, `spice-vdagent` uses the Wayland clipboard API.
Works out of the box with most compositors on the guest side.

### SSH + X11 Forwarding alternative

For headless testing without a display, SSH into the guest and run:
```bash
ssh -X user@guest-ip quickshell  # XWayland forwarding
# Or for real Wayland forwarding (experimental):
WAYLAND_DISPLAY=wayland-1 ssh -Y user@guest-ip
```

---

## 84.7 Audio in VMs

### VirtIO Sound (kernel 5.14+)

```xml
<sound model="virtio"/>
```

Guest needs `snd-virtio` kernel module (included in mainline). PipeWire on the
guest connects to the virtual sound card.

### PipeWire JACK Bridge (host-side audio from guest)

More reliable: expose host PipeWire as a JACK server the guest connects to via
QEMU's `-audiodev`:

```bash
# QEMU CLI:
-audiodev pipewire,id=audio0 \
-device virtio-sound-pci,audiodev=audio0
```

In libvirt XML (add to `<qemu:commandline>`):
```xml
<qemu:commandline>
  <qemu:arg value="-audiodev"/>
  <qemu:arg value="pipewire,id=audio0"/>
</qemu:commandline>
```

---

## 84.8 Tier 2: Looking Glass — Shared GPU Frame Buffer

Looking Glass uses IVSHMEM (Inter-VM Shared Memory) to share the GPU's
framebuffer directly with the host, giving near-native latency. Requires
a second GPU (iGPU works) for the guest.

**Current version: B7 (2025-03-06)** — full Wayland host client parity with X11:
- `libdecor` support for compositor-side decorations on GNOME/KDE Wayland
- Fixed Wayland protocol errors when toggling capture mode
- Fixed clipboard-related crashes on Wayland
- Known issue: NVIDIA host + wlroots compositors (Hyprland/Sway) — flickering
  black rectangles due to EGL import path incompatibilities with NVIDIA Wayland

### Setup Overview

1. Pass a dedicated GPU to the guest via VFIO (see 84.9)
2. Add IVSHMEM shared memory device
3. Guest runs `looking-glass-host` (Windows or Linux)
4. Host runs `looking-glass-client` to display the frame buffer

### IVSHMEM Device

```xml
<shmem name="looking-glass">
  <model type="ivshmem-plain"/>
  <size unit="M">64</size>   <!-- 64MB for 1440p, 128MB for 4K -->
</shmem>
```

Size formula: `width × height × 4 (bytes/pixel) × 2 (double buffer) / 1MB`,
rounded up to next power of 2.

```bash
# Create the IVSHMEM device on the host
sudo touch /dev/shm/looking-glass
sudo chown user:kvm /dev/shm/looking-glass
sudo chmod 0660 /dev/shm/looking-glass
```

### Host Client

```bash
paru -S looking-glass
looking-glass-client -f /dev/shm/looking-glass
```

Keybinds: `ScrollLock` = capture/release mouse. `ScrollLock+F` = fullscreen.
`ScrollLock+I` = toggle interpolated frames.

### /etc/tmpfiles.d/10-looking-glass.conf

```
f /dev/shm/looking-glass 0660 user kvm -
```

---

## 84.9 Tier 3: VFIO GPU Passthrough

Full GPU passthrough gives the VM exclusive access to a physical GPU —
no sharing, near-native performance. Essential for testing HDR, VRR,
gaming, or NVIDIA driver behavior.

### Identify GPU IOMMU Groups

```bash
#!/bin/bash
# List IOMMU groups and their devices
for d in /sys/kernel/iommu_groups/*/devices/*; do
  n=${d#*/iommu_groups/}; n=${n%%/*}
  printf 'Group %s: ' "$n"
  lspci -nns "${d##*/}"
done | sort -V
```

The GPU and its audio function must be in the same IOMMU group (or the group
must contain only devices you want to pass through).

**ACS override patch status:** NOT in mainline Linux and explicitly rejected
by upstream (it asserts software-level isolation where devices may physically
share a PCIe bus, enabling DMA attacks). Before reaching for the patch, check
your BIOS for native ACS or ARI settings — AMD X570/B550/X670E platforms
typically expose GPU functions in separate IOMMU groups natively. Intel
consumer boards (Alder Lake, Raptor Lake) typically do not. The ACS patch
remains available as `linux-vfio` in the AUR or via
queuecumber.gitlab.io/linux-acs-override.

### Bind GPU to vfio-pci

```bash
# /etc/modprobe.d/vfio.conf
# Replace IDs with your GPU's vendor:device from lspci -nn
options vfio-pci ids=10de:2204,10de:1aef

# /etc/mkinitcpio.conf — add vfio modules BEFORE gpu drivers
MODULES=(vfio_pci vfio vfio_iommu_type1 ... nvidia)
# Rebuild initramfs:
sudo mkinitcpio -P
```

Verify on reboot:
```bash
lspci -nnk -d 10de:2204   # should show "Kernel driver in use: vfio-pci"
```

### Libvirt XML — PCI Passthrough

```xml
<hostdev mode="subsystem" type="pci" managed="yes">
  <source>
    <address domain="0x0000" bus="0x01" slot="0x00" function="0x0"/>
  </source>
  <address type="pci" domain="0x0000" bus="0x06" slot="0x00" function="0x0"/>
</hostdev>
<!-- GPU audio function: -->
<hostdev mode="subsystem" type="pci" managed="yes">
  <source>
    <address domain="0x0000" bus="0x01" slot="0x00" function="0x1"/>
  </source>
</hostdev>
```

### Evdev Input Passthrough

Pass keyboard/mouse directly to the VM without SPICE overhead:

```xml
<input type="evdev">
  <source dev="/dev/input/by-id/usb-Keychron-event-kbd" grab="all"
          repeat="on" grabToggle="ctrl-ctrl"/>
</input>
<input type="evdev">
  <source dev="/dev/input/by-id/usb-Logitech-event-mouse"/>
</input>
```

`grabToggle="ctrl-ctrl"`: press left+right Ctrl to toggle input between host and guest.

---

## 84.10 Single GPU Passthrough — Complete libvirt Hook Implementation

On systems with only one discrete GPU, VFIO passthrough requires tearing down
the host Wayland session before the VM starts and restoring it after the VM
stops. libvirt calls scripts in `/etc/libvirt/hooks/qemu.d/` at lifecycle events.

### Directory structure

```
/etc/libvirt/hooks/
├── qemu                          ← dispatcher script (required)
└── qemu.d/
    └── wayland-ricing-vm/        ← must match your VM name exactly
        ├── prepare/
        │   └── begin/
        │       └── start.sh      ← runs before VM starts
        └── release/
            └── end/
                └── revert.sh     ← runs after VM stops
```

### `/etc/libvirt/hooks/qemu` (dispatcher)

```bash
#!/bin/bash
GUEST_NAME="$1"
HOOK_NAME="$2"
STATE_NAME="$3"

BASEDIR="$(dirname $0)"
HOOKPATH="$BASEDIR/qemu.d/$GUEST_NAME/$HOOK_NAME/$STATE_NAME"

set -e  # exit on error in the hook itself

if [ -f "$HOOKPATH" ]; then
    chmod +x "$HOOKPATH"
    "$HOOKPATH"
elif [ -d "$HOOKPATH" ]; then
    for f in "$HOOKPATH"/*; do
        [ -f "$f" ] && chmod +x "$f" && "$f"
    done
fi
```

### `start.sh` — tear down the Wayland session

```bash
#!/bin/bash
# /etc/libvirt/hooks/qemu.d/wayland-ricing-vm/prepare/begin/start.sh
set -x

# 1. Stop the display manager (frees the GPU from the current session)
systemctl stop display-manager.service

# 2. Stop Hyprland user session if running without a DM (TTY autologin)
#    Replace "username" with your actual username
systemctl --user -M username@ stop hyprland.service 2>/dev/null || true

# 3. Wait for compositor to fully exit
sleep 1

# 4. Unbind VT consoles (free framebuffer)
echo 0 > /sys/class/vtconsole/vtcon0/bind
echo 0 > /sys/class/vtconsole/vtcon1/bind

# 5. Unbind EFI framebuffer (skip on AMD RX 5000+ — not needed)
#    echo efi-framebuffer.0 > /sys/bus/platform/drivers/efi-framebuffer/unbind

# 6. Wait for DRM to release
sleep 1

# 7. Unload GPU driver modules — adjust for your GPU:
# NVIDIA:
modprobe -r nvidia_drm nvidia_modeset nvidia_uvm nvidia 2>/dev/null || true
# AMD (usually not needed — amdgpu releases with vfio-pci bind, but if needed):
# modprobe -r amdgpu 2>/dev/null || true

# 8. Detach PCI devices from host and bind to vfio-pci
#    Replace addresses with your GPU's PCI IDs from lspci
virsh nodedev-detach pci_0000_01_00_0
virsh nodedev-detach pci_0000_01_00_1  # GPU audio function

modprobe vfio vfio_pci vfio_iommu_type1
```

### `revert.sh` — restore the Wayland session

```bash
#!/bin/bash
# /etc/libvirt/hooks/qemu.d/wayland-ricing-vm/release/end/revert.sh
set -x

# 1. Re-attach PCI devices to host
virsh nodedev-reattach pci_0000_01_00_0
virsh nodedev-reattach pci_0000_01_00_1

# 2. Reload GPU driver
# NVIDIA:
modprobe nvidia nvidia_modeset nvidia_uvm nvidia_drm
# AMD (if you unloaded it):
# modprobe amdgpu

# 3. Re-bind VT consoles
echo 1 > /sys/class/vtconsole/vtcon0/bind
echo 1 > /sys/class/vtconsole/vtcon1/bind

# 4. Re-bind EFI framebuffer (if you unbound it)
# echo efi-framebuffer.0 > /sys/bus/platform/drivers/efi-framebuffer/bind

sleep 1

# 5. Restart display manager
systemctl start display-manager.service
```

Make both scripts executable: `chmod +x start.sh revert.sh`

### Wayland compositor-specific teardown notes

**Hyprland:** The compositor holds an exclusive DRM lock. It must exit
completely before the GPU can be detached. `systemctl stop display-manager`
alone may not be enough if using TTY autologin — check that the Hyprland
process is gone with `pgrep Hyprland` before proceeding with the GPU detach.
Set `AQ_DRM_DEVICES=/dev/dri/card1` when Hyprland restarts to ensure it
reclaims the correct DRM node after the VM releases the GPU.

**Sway / wlroots:** Sway releases the DRM device cleanly on exit. No special
handling needed beyond stopping the DM.

### AMD RDNA GPU reset bug

AMD GPUs through approximately RDNA 2 (RX 5000/6000 series) have a hardware
limitation where the GPU cannot fully reset between passthrough cycles without
a system reboot. Symptoms: VM fails to start on the second passthrough attempt
(black screen, GPU hang), IOMMU fault in dmesg.

Fix: `vendor-reset` kernel module forces a hardware reset sequence:

```bash
paru -S vendor-reset-dkms

# Load the module
sudo modprobe vendor-reset

# Load at boot — add to start.sh BEFORE virsh nodedev-detach:
# echo 1 > /sys/bus/pci/devices/0000:01:00.0/reset

# Verify the module handles your GPU:
# dmesg | grep vendor_reset
# Should show: "vendor_reset: Resetting AMD RX 580"
```

**RDNA 3 (RX 7000 series):** The reset bug is largely fixed in hardware.
`vendor-reset` is generally not needed for 7000 series cards.

---

## 84.12 Nested Wayland Compositors

Run a compositor inside a compositor (useful for testing without rebooting):

```bash
# On host (Hyprland or any Wayland compositor):
# Start a nested Hyprland in a window:
WAYLAND_DISPLAY=wayland-nested WLR_BACKENDS=wayland WLR_RENDERER=vulkan \
  Hyprland --config /path/to/test-hyprland.conf

# Nested Sway:
WAYLAND_DISPLAY=wayland-1 WLR_BACKENDS=wayland sway

# Nested Weston (simplest test):
weston --backend=wayland-backend.so
```

Nested compositors use the `wlr-backend-wayland` or `wlr-backend-x11` backend
which renders into a regular window. No GPU passthrough needed — virgl or
software rendering is sufficient.

**Limitations of nested compositors:**
- No VRR, no HDR
- GPU features limited to what virgl/swrast exposes
- Input handling can be inconsistent
- Performance fine for config testing, not for benchmarking

### Nested Quickshell Testing

```bash
# Start a minimal Sway/Hyprland nested window for testing Quickshell:
WAYLAND_DISPLAY=wayland-test WLR_BACKENDS=wayland sway &
WAYLAND_DISPLAY=wayland-test quickshell
```

---

## 84.13 VM Snapshots for Safe Ricing

qcow2 snapshots let you save state before risky changes:

```bash
# Take a snapshot
virsh snapshot-create-as --domain arch-rice \
  --name "before-hyprland-plugin" \
  --description "Clean Hyprland 0.45, Quickshell 0.2" \
  --atomic

# List snapshots
virsh snapshot-list arch-rice

# Revert
virsh snapshot-revert arch-rice before-hyprland-plugin

# Delete old snapshot
virsh snapshot-delete arch-rice before-hyprland-plugin
```

**External snapshots** (live, non-disruptive):
```bash
virsh snapshot-create-as arch-rice "live-snap" \
  --disk-only --atomic --no-metadata
```

---

## 84.14 Full Optimized virt-manager XML Template

Complete libvirt domain XML for a Wayland ricing development VM:

```xml
<domain type="kvm">
  <name>wayland-rice-dev</name>
  <memory unit="GiB">8</memory>
  <currentMemory unit="GiB">8</currentMemory>
  <memoryBacking>
    <hugepages/>
  </memoryBacking>
  <vcpu placement="static">8</vcpu>
  <cputune>
    <vcpupin vcpu="0" cpuset="2"/>
    <vcpupin vcpu="1" cpuset="3"/>
    <vcpupin vcpu="2" cpuset="4"/>
    <vcpupin vcpu="3" cpuset="5"/>
    <vcpupin vcpu="4" cpuset="6"/>
    <vcpupin vcpu="5" cpuset="7"/>
    <vcpupin vcpu="6" cpuset="8"/>
    <vcpupin vcpu="7" cpuset="9"/>
    <emulatorpin cpuset="0,1"/>
  </cputune>
  <os>
    <type arch="x86_64" machine="q35">hvm</type>
    <loader readonly="yes" type="pflash">/usr/share/edk2/x64/OVMF_CODE.fd</loader>
    <nvram>/var/lib/libvirt/qemu/nvram/wayland-rice-dev_VARS.fd</nvram>
    <boot dev="hd"/>
  </os>
  <features>
    <acpi/>
    <apic/>
    <vmport state="off"/>
  </features>
  <cpu mode="host-passthrough" check="none" migratable="on">
    <topology sockets="1" dies="1" cores="4" threads="2"/>
  </cpu>
  <clock offset="localtime">
    <timer name="rtc" tickpolicy="catchup"/>
    <timer name="pit" tickpolicy="delay"/>
    <timer name="hpet" present="no"/>
  </clock>
  <devices>
    <!-- Disk -->
    <disk type="file" device="disk">
      <driver name="qemu" type="qcow2" cache="writeback"
              io="threads" discard="unmap" detect_zeroes="unmap"/>
      <source file="/var/lib/libvirt/images/wayland-rice-dev.qcow2"/>
      <target dev="vda" bus="virtio"/>
    </disk>
    <!-- Network -->
    <interface type="network">
      <source network="default"/>
      <model type="virtio"/>
      <driver name="vhost"/>
    </interface>
    <!-- SPICE with GL for virgl -->
    <graphics type="spice" listen="127.0.0.1" port="5900" autoport="no">
      <listen type="address" address="127.0.0.1"/>
      <gl enable="yes" rendernode="/dev/dri/renderD128"/>
      <image compression="off"/>
    </graphics>
    <!-- VirtIO GPU with 3D acceleration -->
    <video>
      <model type="virtio" heads="1" primary="yes">
        <acceleration accel3d="yes"/>
      </model>
    </video>
    <!-- Clipboard agent -->
    <channel type="spicevmc">
      <target type="virtio" name="com.redhat.spice.0"/>
    </channel>
    <!-- VirtIO serial for guest agent -->
    <channel type="unix">
      <target type="virtio" name="org.qemu.guest_agent.0"/>
    </channel>
    <!-- Sound -->
    <sound model="virtio"/>
    <!-- Memory balloon disabled for performance -->
    <memballoon model="none"/>
    <!-- VirtIO RNG for guest entropy -->
    <rng model="virtio">
      <backend model="random">/dev/urandom</backend>
    </rng>
    <!-- Shared host directory via virtiofs -->
    <filesystem type="mount" accessmode="passthrough">
      <driver type="virtiofs"/>
      <source dir="/home/user/vm-shared"/>
      <target dir="host_shared"/>
    </filesystem>
    <!-- USB tablet for accurate mouse in SPICE -->
    <input type="tablet" bus="usb"/>
    <input type="keyboard" bus="virtio"/>
  </devices>
</domain>
```

---

## 84.15 NixOS VM Testing

NixOS makes compositor testing ideal — switch configs without rebooting:

```nix
# flake.nix — define a VM configuration
{
  nixosConfigurations.wayland-test-vm = nixpkgs.lib.nixosSystem {
    system = "x86_64-linux";
    modules = [
      ({ pkgs, ... }: {
        virtualisation.qemu.options = [
          "-device virtio-gpu-gl"
          "-display sdl,gl=on"
        ];
        virtualisation.memorySize = 8192;
        virtualisation.cores = 4;

        programs.hyprland.enable = true;
        services.pipewire.enable = true;
        services.pipewire.wireplumber.enable = true;

        environment.systemPackages = with pkgs; [
          quickshell kitty foot waybar fuzzel
        ];

        # Auto-login to test compositor immediately
        services.getty.autologinUser = "test";
        users.users.test = {
          isNormalUser = true;
          extraGroups = [ "video" "audio" "input" ];
        };
      })
    ];
  };
}

# Build and run the VM:
nixos-rebuild build-vm --flake .#wayland-test-vm
./result/bin/run-wayland-test-vm-vm
```

Switch compositor config without rebooting inside the VM:
```bash
sudo nixos-rebuild switch --flake .#wayland-test-vm
```

---

## 84.16 KVM Limitations for Wayland Ricing

Understanding what VMs cannot replicate prevents wasting time debugging
problems that only exist in the VM environment.

### Hard Limits — Unsolvable Without VFIO + Physical Display

**No VRR / FreeSync / G-Sync.**
Variable refresh rate requires the GPU to signal the physical display over a
real KMS/DRM path. virgl and SPICE are software paths with no variable refresh
capability. Even with VFIO passthrough, VRR only works if the GPU is connected
to a physical monitor — Looking Glass bypasses this entirely by using a capture
card instead.

**No HDR.**
HDR metadata must flow through a real DRM connector to a real display. There
is no mechanism to expose HDR through virtio-gpu or SPICE. VFIO passthrough
to a physical display is the only path.

**No DMA-BUF zero-copy.**
Real Wayland compositors use DMA-BUF to hand GPU buffer handles between
processes without copying pixel data. virgl copies framebuffer content through
the host render pipeline on every frame. You cannot replicate zero-copy buffer
sharing behavior inside a VM.

**No explicit sync testing.**
The explicit sync protocol (`linux-drm-syncobj-v1`) and DRM timeline fences
are part of the real KMS stack. virgl does not expose them. Venus (Vulkan)
also lacks explicit sync. Always disable inside VMs:
```conf
# hyprland.conf — mandatory inside any VM
render {
    explicit_sync = 0
    explicit_sync_kms = 0
}
```

**Venus (Vulkan) has host driver restrictions.**
Venus on QEMU 9.2+ works with RADV and ANV host drivers. It does **not** work
with NVIDIA proprietary host drivers (EGL_NOT_INITIALIZED, tracker #524) and
requires GFX9+ AMD GPUs — Polaris/Fiji lack `VK_EXT_image_drm_format_modifier`
and Venus is unavailable on those hosts.

### Performance Limits

**Frame rate cap ~60fps through SPICE+GL.**
Even on a 165Hz host, the SPICE display path caps the guest at ~60fps.
Animation curves and easing feel different at 60fps — do not evaluate
animation quality in a VM.

**Shader compilation is slower.**
virgl recompiles GLSL shaders on the host side when they are first encountered.
First-launch stutter for any app using OpenGL is noticeably worse than on bare
metal. Shader disk caches inside the guest do not eliminate this.

**Input latency 5–15ms added by SPICE.**
Acceptable for config editing and testing; disqualifying for evaluating actual
desktop responsiveness or gaming. Use evdev passthrough (84.9) to eliminate
this when latency matters.

### Protocol and Feature Limits

**Fractional scaling rendering differs.**
`wp-fractional-scale-v1` works inside virgl VMs but the pixel pipeline is not
identical to the Mesa DRI path on bare metal. Do not use a VM to evaluate
sub-pixel rendering quality or font hinting.

**Screen sharing portals may fail.**
`xdg-desktop-portal-hyprland` uses wlr-screencopy which depends on DRM
capabilities that virgl only partially implements. WebRTC screen sharing (for
testing video calls, OBS) may produce garbled frames or fail to initialize.
Test screen sharing workflows on bare metal.

**Hyprland features requiring real GPU stack:**
| Feature | VM behavior |
|---------|-------------|
| `misc.vrr` | Ignored — no VRR path |
| `render.explicit_sync` | Must be `0` — crashes otherwise |
| `decoration.blur` | Works but performance is worse |
| `animations` | Works, but 60fps cap affects perceived quality |
| `render.direct_scanout` | Silently disabled |
| Plugin using EGL extensions | May fail if extension not in virgl |

### What VMs Are Actually Good For

VMs are well-suited for tasks that do not depend on the rendering pipeline's
performance characteristics or display hardware features:

- **Compositor config iteration** — hyprland.conf, sway config, window rules
- **Quickshell QML development** — reactive bindings, layout, services
- **Session/startup sequencing** — exec-once ordering, dbus environment, portals
- **Package installation testing** — AUR builds, NixOS flake changes
- **NixOS config switching** — `nixos-rebuild switch` without rebooting bare metal
- **Security/isolation testing** — Wayland security model, portal permissions
- **Multi-distro comparison** — run Arch/Fedora/Ubuntu side by side

---

## 84.17 Performance Checklist

| Setting | Optimal value | Impact |
|---------|--------------|--------|
| CPU model | `host-passthrough` | AVX/AVX2 for shader compilation |
| CPU pinning | Isolated cores | Reduces jitter |
| Hugepages | 2MB pages | Reduces TLB misses |
| Memory balloon | `none` | Eliminates allocation latency |
| Disk cache | `writeback` | 2–5× faster writes |
| Disk I/O | `threads` | Parallel I/O |
| Network driver | `vhost-net` | Kernel-space virtio |
| GPU device | `virtio-gpu-gl` | 3D acceleration via virgl |
| SPICE GL | `gl=on` | Actually enables virgl |
| UEFI | OVMF/UEFI | Required for some compositors |
| Input device | `virtio` keyboard/mouse | Lower latency than PS/2 |
| Sound | `virtio` | Lower latency than AC97/ICH9 |

---

## 84.18 Common Issues

**Compositor shows black screen / crashes immediately:**
- Verify `gl=on` in SPICE config — `accel3d=yes` alone is not enough
- Check guest has `mesa` and `xf86-video-virtio` installed
- Try `WLR_RENDERER=gles2` or `WLR_RENDERER=vulkan` env var
- Fallback: `WLR_RENDERER=pixman` (software, slow but guaranteed)

**`/dev/dri/renderD128` does not exist:**
- Host rendernode path varies; check with `ls /dev/dri/`
- May be `renderD129` on systems with multiple GPUs
- Specify correct path in the SPICE `rendernode` attribute

**Huge pages allocation fails:**
```bash
# Check available hugepages
cat /proc/meminfo | grep Huge
# If HugePages_Free = 0, reduce nr_hugepages or free memory first
sudo sysctl vm.nr_hugepages=2048   # halve the request
```

**virtiofs mount fails in guest:**
```bash
# Ensure virtiofsd is installed on host
sudo pacman -S virtiofsd
# Check socket path in libvirt (auto-managed when driver type="virtiofs")
```

**SPICE clipboard not syncing:**
```bash
# Guest — check spice-vdagentd is running
systemctl status spice-vdagentd
# If using Wayland compositor, check XDG_RUNTIME_DIR is set
loginctl show-session $(loginctl | grep user | awk '{print $1}') | grep Display
```

**Hyprland warning about missing GPU features inside VM:**
```conf
# hyprland.conf — add inside VM config
misc {
    vfr = false        # VFR causes issues in some VM setups
}
render {
    explicit_sync = 0  # disable explicit sync (not supported in virgl)
}
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
