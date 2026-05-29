# Chapter 85 — Containerization, Sandboxing, WSL2, and Headless Wayland

## Overview

Beyond full VMs (Ch 84), several lighter-weight isolation mechanisms exist for
running Wayland apps and testing ricing workflows: OCI containers via Distrobox
or Podman, Flatpak portal-based sandboxing, Windows Subsystem for Linux (WSLg),
macOS via UTM/Parallels, and headless Wayland for CI. Each trades isolation
depth for integration depth in a different way.

| Mechanism | Isolation | GPU acceleration | Wayland integration | Best for |
|-----------|-----------|-----------------|---------------------|----------|
| Distrobox | Minimal (homedir shared) | Full (Intel/AMD), CDI for NVIDIA | Full socket pass-through | Cross-distro packages |
| Podman direct | SELinux namespace | Full with `--device /dev/dri` | Socket mount | Reproducible app envs |
| Flatpak | Strong (bwrap) | Portal-mediated | Portal API | Shipping/installing apps |
| bubblejail | Medium (bwrap) | `--wayland` flag | Direct socket | Per-app sandboxing |
| WSLg | VM (Weston+RDP) | D3D12 Mesa | Weston nested | Windows host dev |
| UTM (macOS) | VM (QEMU) | virgl (community tap) | SPICE/SDL GL | macOS host ricing dev |
| wlr-headless | None | Software or host GPU | Headless output | CI / testing |

---

## 85.1 Distrobox — Cross-Distro Packages with Wayland Access

Distrobox (v1.8.x, October 2024) runs any OCI container image with your home
directory mounted. It is the most transparent containerization option — apps
inside the container feel identical to host apps.

### How Wayland Forwarding Works

Distrobox bind-mounts `$XDG_RUNTIME_DIR` from the host into the container,
then exports `WAYLAND_DISPLAY` and `DISPLAY` automatically. The container sees
the same socket path the host uses:

```
Host: /run/user/1000/wayland-1
Container: /run/user/1000/wayland-1  (same path, same socket)
```

No config is needed — Wayland just works.

### Basic Setup

```bash
# Install
sudo pacman -S distrobox

# Create a container (any distro)
distrobox create --name ubuntu-ricing --image ubuntu:24.04
distrobox create --name fedora-tools  --image fedora:41

# Enter
distrobox enter ubuntu-ricing

# Inside the container:
sudo apt install neovim
```

### GPU Acceleration

Intel and AMD GPUs: `/dev/dri` devices are accessible without extra flags.
Test inside the container:
```bash
glxinfo | grep renderer   # should show real GPU, not llvmpipe
vainfo                    # VA-API hardware decode
```

**NVIDIA (requires CDI):**
```bash
# Host: configure NVIDIA Container Toolkit with CDI
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml

# Create container with NVIDIA access
distrobox create --name nvidia-dev --image ubuntu:24.04 \
  --additional-flags "--gpus all"

# Verify inside:
nvidia-smi
```

The older `--nvidia` flag (bind-mounts any host file containing "nvidia") is
fragile and breaks on NixOS or non-FHS hosts — use CDI instead.

### Exporting Apps to Host

Apps installed inside a container can be launched from the host:
```bash
# Inside container:
distrobox-export --app firefox
distrobox-export --bin /usr/bin/some-tool --export-path ~/.local/bin

# From host, the app runs inside the container transparently:
firefox   # launches in the container with host Wayland socket
```

### Hard Limits

- **No isolation for `$HOME`** — the container has full read/write access to
  your home directory. Distrobox is an integration tool, not a security sandbox.
- Rootless containers cannot access `/dev/kfd` (AMD ROCm) without group changes.
- Running a full Wayland **compositor** (Hyprland, Sway) inside a rootless
  container fails — compositors need DRM access which requires privileges
  containers do not have. Only Wayland **clients** (apps) work.

---

## 85.2 Podman and Docker — Direct Wayland Socket Mounting

For more controlled environments (reproducible dev containers, app testing):

### Minimal Working Wayland Container (Podman)

```bash
podman run --rm \
  -e WAYLAND_DISPLAY="$WAYLAND_DISPLAY" \
  -e XDG_RUNTIME_DIR=/tmp/xdg \
  -v "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY":/tmp/xdg/"$WAYLAND_DISPLAY":ro \
  --device /dev/dri \
  --group-add video \
  --group-add render \
  --security-opt label=disable \
  archlinux:latest \
  foot
```

`--security-opt label=disable` is required on SELinux hosts (Fedora default)
because the container label cannot access `/dev/dri` without a custom policy.

### Adding PipeWire Audio

```bash
  -e PIPEWIRE_RUNTIME_DIR=/tmp/xdg \
  -v "$XDG_RUNTIME_DIR/pipewire-0":/tmp/xdg/pipewire-0 \
```

### Adding D-Bus (for tray, notifications, portals)

```bash
  -e DBUS_SESSION_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS" \
  -v /run/user/1000/bus:/run/user/1000/bus \
```

### Toolbox (Fedora/RHEL)

Toolbox is the correct choice on immutable Fedora (Silverblue, Kinoite) where
`dnf` cannot modify the host filesystem:

```bash
toolbox create --image registry.fedoraproject.org/fedora-toolbox:41
toolbox enter
# now dnf install works normally; Wayland socket forwarded automatically
```

Toolbox is identical to Distrobox technically (both wrap Podman) but restricted
to Fedora/RHEL container images.

---

## 85.3 Flatpak — Portal-Based Sandboxing

Flatpak uses bubblewrap (bwrap) to sandbox apps, and xdg-desktop-portal to
broker access to host resources. It is the strongest isolation model for
desktop apps while retaining usable Wayland integration.

### Portal Status (2025–2026)

| Portal | Status | Notes |
|--------|--------|-------|
| FileChooser | Stable | Broad compositor support |
| ScreenCast v5 | Stable | PipeWire video stream; compositor must implement screencast protocol |
| Screenshot | Stable | Single-frame variant of ScreenCast |
| Clipboard | **Incomplete** | Gaps in Mutter (GNOME) and KWin (KDE) implementations |
| Print | Stable | |
| Notifications | Stable | |
| Settings (dark mode) | Stable | |
| Inhibit (suspend) | Stable | |

The clipboard portal is the most notable outstanding gap — cross-app clipboard
for sandboxed Flatpak apps remains unreliable on Wayland.

### Flatpak Wayland Permissions

```bash
# Grant Wayland socket access (most apps need this):
flatpak override --user --socket=wayland org.app.Name

# Remove X11 fallback (Wayland-only):
flatpak override --user --nosocket=x11 org.app.Name

# Grant GPU:
flatpak override --user --device=dri org.app.Name

# Check current overrides:
flatpak override --user --show org.app.Name
```

### wp-security-context-v1 — Compositor Support

This protocol (wayland-protocols 1.32, July 2023) lets the compositor restrict
sandboxed clients from screenscraping, fullscreen overlays, and keyboard hijacking.
All major compositors now implement it:

| Compositor | Version |
|-----------|---------|
| KWin (KDE) | 6.6+ |
| Mutter (GNOME) | 49.2+ |
| Sway | 1.11+ |
| Hyprland | 0.52.1+ |
| Niri | 25.11+ |
| River | 0.3.13+ |
| Weston | 14.0.2+ |
| COSMIC, labwc, Wayfire | Various 2025 releases |

Flatpak uses this protocol to attach app-ID metadata to sandboxed Wayland
connections. The compositor uses this to enforce restrictions without needing
to know about Flatpak specifically.

---

## 85.4 bubblejail — Targeted App Sandboxing

bubblejail wraps bubblewrap (the same engine as Flatpak) with pre-built
per-application profiles. It provides stronger isolation than running apps
unsandboxed, without the full Flatpak package format.

```bash
paru -S bubblejail

# Run an app in a bubblejail sandbox:
bubblejail run firefox

# List available profiles:
bubblejail list-profiles

# Create a custom profile:
bubblejail create --profile firefox my-firefox
```

The `--wayland` flag in profiles enables Wayland socket access.
About 50 profiles ship with bubblejail covering common desktop apps.

bubblejail is better aligned with Wayland than Firejail because it uses the
same namespace mechanism as Flatpak rather than a separate interception layer.

### Firejail — Avoid on Wayland

Firejail's namespace approach breaks `XDG_RUNTIME_DIR` path resolution, causing
"cannot connect to Wayland display" errors for most applications. It is an X11
era tool not yet adapted for Wayland. Use bubblejail or Flatpak instead.

---

## 85.5 WSL2 / Windows Host (WSLg)

WSLg (Windows Subsystem for Linux GUI) runs Weston with an RDP backend inside
a companion VM. Weston composites X11 (via XWayland) and native Wayland
application windows, then streams them to the Windows desktop via enhanced RDP.

### Architecture

```
Windows display ← RDP ← Weston (companion VM)
                               ↑
                    WSLg Wayland socket
                               ↑
                    User distro VM (Ubuntu/Arch/etc)
                    └── GUI apps (GTK, Qt, Electron)
```

GPU path: D3D12 Gallium driver (Mesa) → DirectX 12 → Windows GPU.
This is **not** virgl — WSLg uses a D3D12 translation layer developed with
Collabora. `virtio-gpu-wddm2` exposes the Windows GPU to the Linux VM.

Current version: **WSLg 1.0.66** (February 2025).

### What Works

- GTK4/Qt6 Wayland apps display natively via WSLg
- XWayland for legacy apps
- VA-API hardware video decode via D3D12 backend
- Clipboard sync between Windows and Linux apps

**Sway (nested):** Works. Sway's wlroots Wayland backend runs nested inside
WSLg's Weston. You get a full tiling session in a window. Performance is
limited by the RDP path and there is no VRR/HDR.

### What Does Not Work

**Hyprland:** Does not work in WSLg. Hyprland requires `/dev/dri/card*` DRM
nodes for its rendering pipeline. WSLg's user VM does not expose DRM nodes —
only the companion Weston VM has GPU access through the virtio-gpu-wddm2 bridge.
This is a fundamental architectural constraint, not a configuration issue.

**Performance overhead:** The rendered framebuffer is copied from VRAM to
system memory before RDP transmission. At high frame rates this introduces
~50% overhead compared to native Linux rendering. Animations feel noticeably
worse than bare metal.

**VRR, HDR:** Not available through the RDP display path.

### Installation and Testing

```powershell
# PowerShell (Windows):
wsl --install
wsl --update   # get latest WSLg

# In WSL:
sudo pacman -S sway foot  # or apt install on Ubuntu
sway   # starts nested inside WSLg window
```

---

## 85.6 macOS Host

### UTM — QEMU Frontend for Apple Silicon and Intel

UTM uses QEMU internally. virgl support requires the community-maintained
`homebrew-qemu-virgl` tap:

```bash
brew tap knazarov/qemu-virgl
brew install qemu-virgl

# Apple Silicon (M-series): use virtio-gpu-gl-pci (NOT virtio-gpu-pci)
qemu-system-aarch64 \
  -machine virt,accel=hvf \
  -device virtio-gpu-gl-pci \
  -display sdl,gl=es \
  ...

# Intel Mac: use virtio-vga-gl
qemu-system-x86_64 \
  -device virtio-vga-gl \
  -display sdl,gl=on \
  ...
```

Wayland guests with OpenGL acceleration work via this tap. Note this is
community-maintained (35+ open issues) — stability varies.

UTM's **Virtualization.framework backend** (VZ, used for native ARM Linux VMs
on M-series) does not support virgl — it uses Apple's own graphics layer.
Wayland guests on the VZ backend get software rendering only.

### Parallels Desktop

Parallels 17.1.0+ uses VirGL instead of its proprietary graphics driver:
- Enabled by default for new VMs on supported kernel versions (5.10+)
- Confirm: `sudo dmesg | grep virgl` → should show `+virgl`
- "Improved Wayland protocol support" claimed but Parallels Tools clipboard
  sync and dynamic resolution remain incomplete on Wayland sessions
- Missing mouse pointer when switching to Wayland on some distros (OpenSUSE KDE)
  — known issue, workaround: use X11 session

### Lima / colima

Lima and colima are designed for container workloads, not display forwarding.
Wayland socket forwarding to macOS is not supported and makes limited sense —
macOS has no native Wayland compositor. For Wayland GUI apps from Lima VMs on
macOS, use SSH X11 forwarding or VNC instead.

---

## 85.7 Headless Wayland — CI, Testing, Cloud

The `wlr-headless` backend runs a Wayland compositor with no physical display.
This is the standard approach for CI/CD and automated testing of Wayland apps.

### Sway Headless

```bash
export WLR_BACKENDS=headless
export WLR_LIBINPUT_NO_DEVICES=1
export SWAYSOCK=/tmp/sway-ipc.sock
sway &

# Wait for compositor socket
while [ ! -S "$SWAYSOCK" ]; do sleep 0.1; done

# Run tests against the headless compositor
WAYLAND_DISPLAY=wayland-1 your-app --test-mode
```

### Weston Headless

```bash
weston --backend=headless-backend.so &
export WAYLAND_DISPLAY=wayland-1

# Create a virtual output with specific resolution:
weston-terminal --fullscreen &
```

Weston headless is the drop-in replacement for Xvfb on platforms that have
removed X11 support (CentOS Stream 10, Fedora immutable variants).

### GitHub Actions / GitLab CI

```yaml
# .github/workflows/test.yml
jobs:
  test:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - name: Install compositor
        run: sudo apt install -y sway weston
      - name: Run tests under headless Wayland
        run: |
          export WLR_BACKENDS=headless WLR_LIBINPUT_NO_DEVICES=1
          sway &
          sleep 1
          WAYLAND_DISPLAY=wayland-1 cargo test --features wayland
```

### Cloud VMs (AWS, GCE, Azure)

GPU-accelerated cloud VMs (T4, A100, L40S) expose the GPU via PCIe passthrough.
The headless backend works with software rendering for compositor testing.
For GPU-accelerated rendering in cloud VMs:

```bash
# Use EGL surfaceless for GPU compute without a display:
export EGL_PLATFORM=surfaceless
# Or use the DRM backend with a headless output:
WLR_BACKENDS=drm WLR_DRM_DEVICES=/dev/dri/renderD128 sway
```

Cloud VMs do not have display outputs connected, so the DRM backend requires
a virtual connector. Create one:
```bash
# Add to Hyprland config for headless operation:
monitor = HEADLESS-1, 1920x1080@60, 0x0, 1
```

### Quickshell Testing Without a Compositor

For testing Quickshell QML without running a full compositor:

```bash
# Run under headless sway:
WLR_BACKENDS=headless WLR_LIBINPUT_NO_DEVICES=1 sway &
WAYLAND_DISPLAY=wayland-1 quickshell

# Or use the Qt embedded platform for pure QML testing (no Wayland):
QT_QPA_PLATFORM=offscreen quickshell   # no window, just process test
```

---

## 85.8 Isolation Summary and Recommendations

| Use case | Recommended approach |
|----------|---------------------|
| Test Hyprland config changes | KVM + virgl (Ch 84) or nested compositor |
| Run Ubuntu app on Arch host | Distrobox |
| Reproduce a bug in a specific distro | Podman + socket mount |
| Ship a hardened app | Flatpak with portal permissions |
| Sandbox an untrusted X11/Wayland app | bubblejail (not Firejail) |
| Develop on Windows, target Linux | WSLg + Sway (not Hyprland) |
| Develop on macOS, target Linux | UTM with virgl tap |
| CI for Wayland app test suite | wlr-headless + sway or Weston |
| Test screen sharing portals | KVM VM (virgl has partial screencast support) |
| Test VRR/HDR/explicit sync | Bare metal only |

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
