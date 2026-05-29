# Chapter 63 — The GPU Rendering Stack: DRM/KMS, Mesa, GBM, EGL

## Overview

Understanding how pixels actually reach the screen — from `wl_surface` commit
through the kernel's DRM subsystem to the display — demystifies compositor
development, debugging, and GPU selection decisions. This chapter traces the
full rendering pipeline from application buffer allocation through kernel mode
setting to physical display output, explaining each layer's responsibilities
and how they interconnect.

The GPU rendering stack on Linux is a collaborative system spanning userspace
libraries, kernel drivers, and hardware. Unlike Windows or macOS where the
graphics stack is largely opaque, Linux's open architecture means every layer
is inspectable, tunable, and replaceable. For a ricer, this matters: you can
diagnose tearing, force specific rendering paths, enable HDR output, control
power states, and unlock hardware overlays — all by understanding which knob
lives at which layer.

This chapter focuses on the path a pixel takes in a Wayland session. For
X11 rendering history and XWayland's translation layer, see Ch 61. For
compositor-specific rendering configuration (Hyprland render settings, Sway
renderer selection), see Ch 71. For display calibration and color management,
see Ch 77.

## Sections

### 63.1 The Full Stack

The rendering pipeline connects Wayland clients to physical displays through
four major layers: the Wayland compositor's renderer, Mesa (userspace GPU
drivers), the DRM/KMS kernel subsystem, and the display hardware itself.

```
Wayland client                    Compositor (Hyprland/Sway/niri)
wl_surface.commit()  ──────────► wlr_renderer / scene graph
     │                                    │
wl_buffer (SHM or DMA-BUF)         OpenGL ES / Vulkan
     │                              Mesa (radv/anv/iris/nvk)
     │                                    │
     └───────────────────────────► KMS/DRM (kernel)
                                          │
                                    CRTC → Encoder → Connector
                                          │
                                       Monitor
```

Each arrow in this diagram represents a well-defined interface. `wl_surface.commit()`
is the Wayland protocol boundary. The transition from Mesa to KMS crosses the
kernel/userspace boundary via `ioctl`. The CRTC-to-connector path is handled
entirely in the kernel and hardware. Understanding these boundaries tells you
*which layer to debug* when something breaks.

In a hardware-accelerated session, the compositor renders each frame to a
GBM-backed framebuffer using OpenGL ES or Vulkan (via Mesa), then submits that
framebuffer to KMS for hardware flip at the next vsync interval. The entire
path from compositor render completion to pixel emission is typically one
vsync period — about 16 ms at 60 Hz or 8 ms at 120 Hz.

### 63.2 DRM/KMS — The Kernel Layer

DRM (Direct Rendering Manager) is the Linux kernel subsystem responsible for
two related but distinct jobs: managing GPU access from multiple userspace
processes (the "DRM" part), and configuring display output pipelines (KMS —
Kernel Mode Setting). Before KMS, display mode setting was done by X server
code running in userspace with root privileges and direct hardware access.
KMS moved that responsibility into the kernel, enabling features like fast
virtual terminal switching, early boot graphics, and safe concurrent GPU access.

The KMS object model maps physical display hardware into an abstract tree of
kernel objects. A **CRTC** (Cathode Ray Tube Controller, a legacy name)
represents one complete display pipeline — one active monitor's scanout path.
A **Plane** is a layer within that pipeline: the PRIMARY plane carries the
main framebuffer, CURSOR planes handle hardware cursors (no GPU compositing
needed), and OVERLAY planes allow hardware compositing of additional surfaces.
An **Encoder** converts the CRTC's digital signal to the format required by
the physical connector. A **Connector** represents a physical output port.

```bash
# Inspect the full DRM object tree for all GPUs
sudo drm_info

# List connectors, encoders, CRTCs, and supported display modes
sudo modetest -M amdgpu      # specify driver module
sudo modetest -M i915

# Check which outputs are currently connected
cat /sys/class/drm/card*/status

# See the current mode for each output
for f in /sys/class/drm/card*-*/modes; do echo "$f:"; cat "$f"; done

# List DRM devices
ls -la /dev/dri/
# card0 = KMS (display), renderD128 = render-only (compute/decode)
```

**Direct scanout** is an optimization where the compositor detects that a
fullscreen application's buffer already matches the format, size, and
properties required by the KMS plane, and submits it directly — bypassing
compositor rendering entirely. The GPU does zero work in this path; the
hardware scanout engine reads the buffer directly. This is why fullscreen
gaming on Wayland can match or exceed X11 performance: there is no extra copy,
no compositing overhead.

For direct scanout to trigger, the buffer must match the plane's format
constraints (pixel format, modifier), the application must be the only visible
surface, and the compositor must explicitly attempt the atomic commit with the
client buffer. Compositors like Hyprland and Sway attempt direct scanout
opportunistically and fall back to compositing if the commit fails.

```bash
# Enable DRM debug logging to trace KMS commits (very verbose)
echo 0x1f | sudo tee /sys/module/drm/parameters/debug
journalctl -k -f | grep -E "drm|KMS|plane|crtc"

# Disable after debugging
echo 0x0 | sudo tee /sys/module/drm/parameters/debug

# Check for direct scanout in Hyprland
hyprctl monitors | grep -i scanout
HYPRLAND_LOG_LEVEL=TRACE hyprland 2>&1 | grep -i "direct\|scanout\|overlay"
```

**Atomic modesetting** (versus the legacy API) allows multiple KMS property
changes to be submitted as a single atomic transaction. If any property change
fails (e.g., a format isn't supported), the entire transaction is rolled back
— no partial state. Modern compositors exclusively use atomic modesetting via
the `DRM_IOCTL_MODE_ATOMIC` ioctl. The `--atomic` flag in `modetest` exercises
this path.

```bash
# Test atomic modesetting capability
sudo modetest --atomic -M amdgpu

# Check if atomic is available for your driver
cat /sys/kernel/debug/dri/0/state   # requires debugfs mounted
```

### 63.3 GBM — Generic Buffer Management

GBM (Generic Buffer Management) is a thin abstraction library (part of Mesa)
that allocates DMA-BUF-backed buffers suitable for both GPU rendering and KMS
scanout. It sits between EGL/Vulkan (which need surfaces to render into) and
DRM (which needs specific buffer formats and memory layouts). Without GBM,
a compositor would have to call driver-specific allocation APIs directly.

A `gbm_bo` (buffer object) represents one allocated buffer. When creating it,
you specify the width, height, pixel format, and usage flags. The format
`GBM_FORMAT_XRGB8888` is the universal baseline (32-bit color, no alpha,
suitable for scanout). For HDR pipelines, `GBM_FORMAT_XRGB2101010` provides
10 bits per channel. The `GBM_BO_USE_SCANOUT` flag tells GBM to allocate the
buffer in memory accessible to the display engine; `GBM_BO_USE_RENDERING`
ensures it's accessible to the GPU renderer. Allocating with both flags
ensures the buffer can serve as both render target and scanout source.

```bash
# Install GBM development tools and inspect GBM capabilities
sudo pacman -S mesa-utils libgbm      # Arch
sudo apt install mesa-utils libgbm-dev  # Debian/Ubuntu

# gbmtool can dump GBM device capabilities
gbmtool /dev/dri/card0

# List supported pixel formats and modifiers via weston-info
weston-info 2>&1 | grep -A2 "zwp_linux_dmabuf"

# Check format support through vulkaninfo (Vulkan path uses same GBM allocator)
vulkaninfo 2>&1 | grep -i format | head -30
```

In wlroots-based compositors, `wlr_gbm_allocator` wraps the GBM API and
provides buffers to `wlr_renderer`. When Hyprland or Sway initializes its
renderer, it opens the DRM device, creates a GBM device from it, then creates
a GBM surface for the output. This surface provides EGL with a native window
to render into, and the GBM device provides EGL with a native display.

**Buffer modifiers** are a critical concept for high-performance compositing.
A modifier encodes the memory layout of a buffer — tiled, compressed,
vendor-specific arrangements that the GPU prefers for rendering. For example,
AMD GPUs prefer DCC (Delta Color Compression) tiled layouts
(`DRM_FORMAT_MOD_AMD_GFX9_...`). When clients allocate buffers with matching
modifiers, the compositor can import them without format conversion. The
`zwp-linux-dmabuf-v1` protocol negotiates these modifiers between client and
compositor.

### 63.4 EGL — The OpenGL-Wayland Bridge

EGL is the glue layer between OpenGL ES (or OpenGL) and platform-specific
display systems. Where GLX tied OpenGL to X11, EGL is platform-neutral: it can
target GBM (for compositors), Wayland surfaces (for clients), offscreen
surfaces, and more. EGL's job is to create GL contexts, manage surfaces
(things you render into), and handle buffer swapping.

For a Wayland **compositor**, EGL uses the `EGL_KHR_platform_gbm` extension.
The compositor opens the DRM device, wraps it in a GBM device, then creates
an `EGLDisplay` from that GBM device. It creates an `EGLContext` for OpenGL ES
rendering and `EGLSurface` objects backed by GBM surfaces. When it calls
`eglSwapBuffers()`, GBM rotates the backing buffer, making the freshly rendered
frame available for KMS submission.

For Wayland **clients**, EGL uses `EGL_KHR_platform_wayland`. The client
creates an `EGLDisplay` from its `wl_display` connection, an `EGLSurface` from
a `wl_egl_window` (which wraps a `wl_surface`), and renders normally. EGL
handles the conversion to `wl_buffer` under the hood, typically using DMA-BUF
for zero-copy transfer to the compositor.

```bash
# List all EGL extensions available on your system
eglinfo            # from mesa-utils or egl-utils
eglinfo | grep EGL_KHR_platform

# Check EGL client/display/device extensions
EGL_LOG_LEVEL=debug app 2>&1 | head -20

# Diagnose EGL initialization failures
LIBGL_DEBUG=verbose glxgears 2>&1
EGL_PLATFORM=gbm eglinfo

# Dump EGL config attributes for debugging surface creation
eglinfo -B    # brief format showing all configs
```

**Key EGL extensions for Wayland:**

| Extension | Purpose |
|-----------|---------|
| `EGL_KHR_platform_wayland` | Wayland client rendering |
| `EGL_KHR_platform_gbm` | Compositor rendering via GBM |
| `EGL_EXT_image_dma_buf_import` | Import DMA-BUF into GL as EGLImage |
| `EGL_EXT_image_dma_buf_import_modifiers` | DMA-BUF with format modifiers |
| `EGL_KHR_fence_sync` | GPU synchronization primitives |
| `EGL_EXT_present_opaque` | Force opaque alpha for scanout |
| `EGL_KHR_no_config_context` | Context without tied EGLConfig |
| `EGL_IMG_context_priority` | Request high-priority GPU context |
| `EGL_EXT_buffer_age` | Query buffer age for partial updates |

The `EGL_EXT_image_dma_buf_import` extension is the foundation of zero-copy
compositing. When a Wayland client sends a DMA-BUF buffer via
`zwp-linux-dmabuf-v1`, the compositor uses this extension to create an
`EGLImage` from the DMA-BUF file descriptor. That EGLImage can then be bound
as a GL texture — the compositor samples it in its render shader without any
memory copy.

```bash
# Verify DMA-BUF import extension is present (required for zero-copy)
eglinfo | grep dma_buf

# Test EGL Wayland platform specifically
EGL_PLATFORM=wayland eglinfo 2>/dev/null || echo "Wayland EGL platform not available"

# Check Mesa's EGL platform support
MESA_DEBUG=1 weston 2>&1 | grep -i "egl\|platform"
```

### 63.5 Mesa — The Open Source GPU Stack

Mesa is the userspace implementation of OpenGL, OpenGL ES, and Vulkan for most
Linux GPUs. It translates API calls into hardware-specific command streams,
manages shader compilation, handles GPU memory allocation, and submits work to
the kernel driver (via DRM render nodes). Mesa's driver architecture separates
the frontend (API implementation) from the backend (hardware-specific code),
allowing code reuse: for instance, the NIR (New IR) intermediate representation
is shared by all Mesa Gallium drivers, and ACO (AMD's shader compiler) is used
by both `radv` (Vulkan) and `radeonsi` (OpenGL via Gallium).

| Driver | GPU | API | Notes |
|--------|-----|-----|-------|
| `radv` | AMD GCN+ (GFX6+) | Vulkan | Primary Vulkan driver; ACO compiler; production quality |
| `radeonsi` | AMD GCN+ | OpenGL/GLES | Gallium driver; mature and stable |
| `anv` | Intel Gen8+ (Broadwell+) | Vulkan | Primary Intel Vulkan; good perf |
| `iris` | Intel Gen8+ | OpenGL/GLES | Replaced i965; Gallium-based |
| `nvk` | NVIDIA Turing+ (RTX 20xx+) | Vulkan | New as of Mesa 23.3; improving rapidly |
| `nouveau` | NVIDIA (legacy) | OpenGL | Limited perf; no reclocking on modern GPUs |
| `zink` | Any with Vulkan | OpenGL over Vulkan | Compatibility layer; sometimes faster than native |
| `llvmpipe` | CPU | OpenGL/GLES | Software renderer; no GPU needed |
| `virgl` | VirtIO GPU | OpenGL | VM guest driver |
| `d3d12` | WDDM (WSL2) | OpenGL via D3D12 | Microsoft Gallium driver for WSL |

```bash
# Identify the active Mesa driver and version
glxinfo | grep -E "OpenGL renderer|OpenGL version|vendor"
vulkaninfo --summary | grep -E "driverName|apiVersion|driverVersion"

# Check Mesa version
mesa-demo --version 2>/dev/null || glxgears -info 2>&1 | head -5
pacman -Q mesa          # Arch
dpkg -l libgl1-mesa-dri  # Debian/Ubuntu

# Check shader cache location and size
du -sh ~/.cache/mesa_shader_cache/
ls ~/.cache/mesa_shader_cache/

# Force shader cache rebuild (after Mesa upgrade)
rm -rf ~/.cache/mesa_shader_cache/

# Enable Mesa debug output for specific subsystems
MESA_DEBUG=flush,incomplete_tex app   # flush-related bugs
MESA_DEBUG=perf app                   # performance warnings

# Override driver (useful for testing zink fallback)
MESA_LOADER_DRIVER_OVERRIDE=zink app
GALLIUM_DRIVER=softpipe app           # force software rendering
```

Mesa's **shader compiler pipeline** is a key performance factor. Source
shaders (GLSL/SPIR-V) are parsed into an internal IR (NIR for Gallium+Vulkan,
or TGSI for legacy Gallium). NIR undergoes optimization passes (dead code
elimination, constant folding, vectorization) then is lowered to hardware
instructions. AMD uses the ACO backend by default for `radv`; Intel uses NIR
with backend-specific lowering. Compiled shaders are cached in
`~/.cache/mesa_shader_cache/` (keyed by shader hash + driver version), so
subsequent runs avoid recompilation.

```bash
# Monitor shader compilation in real time
MESA_SHADER_CACHE_DISABLE=true app   # disable cache to observe recompiles
AMD_DEBUG=shaders app 2>&1 | grep -c "compiled"  # count shader compiles (AMD)
INTEL_DEBUG=vs,fs app 2>&1 | head -50  # dump vertex/fragment shaders (Intel)

# Check VA-API (video decode) driver integration
vainfo
LIBVA_DRIVER_NAME=radeonsi vainfo   # AMD
LIBVA_DRIVER_NAME=iHD vainfo        # Intel (iHD = newer), i965 (legacy)
LIBVA_MESSAGING_LEVEL=1 vainfo      # verbose initialization
```

### 63.6 DMA-BUF — Zero-Copy Buffer Sharing

DMA-BUF (Direct Memory Access Buffer) is a Linux kernel mechanism for sharing
GPU-accessible memory between processes and between subsystems, without CPU
copies. A DMA-BUF is represented as a file descriptor that can be passed over
Unix sockets. Any process that receives the FD can map or import the underlying
memory — the actual allocation lives in kernel space, reference-counted.

In the Wayland context, DMA-BUF enables the critical zero-copy rendering path:
(1) a client renders directly into a DMA-BUF using its GPU, (2) sends the FD
to the compositor via the `zwp-linux-dmabuf-v1` protocol, (3) the compositor
imports it as an EGLImage and samples it in a composite shader — or, better,
passes it directly to KMS via a hardware plane. No data moves through the CPU
at any step.

```bash
# Verify zwp-linux-dmabuf-v1 protocol support in compositor
wayland-info | grep dmabuf
weston-info 2>&1 | grep -A 10 "zwp_linux_dmabuf"

# Test DMA-BUF import with a simple client
# kmscube uses DMA-BUF internally — useful smoke test
sudo pacman -S kmscube
kmscube                    # run directly on DRM, no compositor needed
kmscube -A 2>&1 | head    # with verbose allocation info

# Check if a running app is using DMA-BUF (needs root or ptrace cap)
# Look for fd with DMA-BUF magic in /proc
ls -la /proc/$(pgrep mpv)/fd | wc -l   # count open FDs (DMA-BUF adds many)

# Force wl_shm (CPU copy) fallback for debugging
# Most apps respect WAYLAND_RENDERER env var or app-specific flags
mpv --gpu-api=opengl --gpu-context=wayland video.mkv  # explicit Wayland context
```

**wl_shm** (shared memory) is the fallback buffer mechanism when DMA-BUF is
unavailable — typically for software-rendered clients (e.g., old GTK2 apps,
unaccelerated terminals). The client allocates a POSIX shared memory object,
maps it, draws pixels into it via CPU, then passes the FD to the compositor.
The compositor must then copy or upload this data to GPU memory before
compositing. This is slower but universally supported and requires no GPU
capability from the client.

**Why DMA-BUF matters for ricing specifically:**
- `ScreencopyView` in Quickshell captures screen regions via DMA-BUF — zero-copy
  means it's suitable for live wallpapers and previews without GPU overhead
- Video players (mpv, VLC) use hardware video decode (VA-API) that outputs
  directly to DMA-BUF, which then goes directly to a compositor overlay plane
  — the video never touches the GPU 3D pipeline at all
- Screen recorders (wf-recorder, OBS with Pipewire capture) use DMA-BUF for
  efficient frame capture without impacting the display pipeline
- Shader tools and desktop effects that process captured frames (hyprshade)
  can import composited output via DMA-BUF for post-processing

### 63.7 Explicit vs. Implicit Synchronization

GPU synchronization governs when it is safe to read a buffer that a GPU is
writing to. The GPU processes work asynchronously — when the CPU tells it to
render something, execution happens in the future. Before another consumer
(the compositor, the display engine) reads the rendered result, it must wait
for the GPU to finish. How that waiting is communicated is the synchronization
model.

**Implicit synchronization** (the legacy model, used by X11 and early Wayland)
embeds fence state inside the buffer itself. When the GPU driver writes to a
buffer, it attaches an implicit fence to it. The next reader (compositor, KMS)
waits on that fence automatically, without the caller managing any fence
objects explicitly. This "just works" for simple cases but hides synchronization
logic from userspace and makes it hard to pipeline work efficiently.

**Explicit synchronization** (the modern model) exposes fence objects directly
to userspace. The client or compositor creates a fence, associates it with a
GPU submission, and passes the fence alongside the buffer. The compositor
receives both the buffer and the fence, and knows exactly when the buffer is
ready. This enables more sophisticated pipelining, better debugging, and is
required for cross-driver/cross-process scenarios where implicit sync metadata
doesn't propagate correctly.

The `linux-drm-syncobj-v1` Wayland protocol (merged 2023) exposes explicit
sync to Wayland clients. Combined with `wp-linux-drm-syncobj-v1`, clients and
compositors can exchange DRM syncobj handles as acquire and release fences.
Hyprland added full explicit sync support in June 2024, which dramatically
improved stability for NVIDIA users.

```bash
# Check if your compositor supports explicit sync protocols
wayland-info | grep -E "syncobj|sync"
WAYLAND_DEBUG=1 hyprland 2>&1 | grep -i sync | head -20

# NVIDIA-specific: check if nvidia-drm module is loaded with modeset
cat /sys/module/nvidia_drm/parameters/modeset   # should be Y
sudo modprobe nvidia-drm modeset=1

# Add modeset permanently for NVIDIA
echo 'options nvidia-drm modeset=1' | sudo tee /etc/modprobe.d/nvidia-drm.conf
sudo mkinitcpio -P   # Arch: rebuild initramfs

# Check sync_file kernel support (required for explicit sync)
zcat /proc/config.gz | grep CONFIG_SYNC_FILE   # should be y or m
ls /sys/kernel/debug/sync/   # sync debug (if debugfs mounted)

# Verify Hyprland explicit sync status
hyprctl getoption render:explicit_sync
hyprctl keyword render:explicit_sync 2   # 0=off, 1=on, 2=auto
```

The practical impact for NVIDIA users: with old compositors (Mutter pre-45,
Hyprland pre-0.41) using implicit sync but NVIDIA's proprietary driver using
explicit sync internally, the compositor submitted buffers to KMS before the
GPU had finished writing them — causing tearing, flickering, and corruption.
With explicit sync on both sides, both parties agree on exactly when the buffer
is ready.

### 63.8 The Compositor Render Loop

The compositor's render loop is the heartbeat of the entire desktop. It fires
on vsync, composites all visible surfaces, and submits the result to hardware.
Understanding it lets you reason about latency, jitter, and performance
implications of your ricing choices (blur, rounded corners, animations).

```
1. DRM 'vblank' interrupt fires (hardware vsync event)
2. Kernel delivers event via DRM FD (poll/epoll in compositor)
3. wlr_output 'frame' signal emitted
4. Compositor traverses scene graph (wlr_scene or custom)
   a. Identify damaged regions (dirty surfaces since last frame)
   b. Cull occluded surfaces
   c. Check for direct scanout opportunity
5. If direct scanout: submit client buffer directly to KMS plane
   Else: bind GBM/EGL framebuffer, clear, render all surfaces
   a. For each surface: bind DMA-BUF as GL texture
   b. Render quad with surface texture + effects (blur, shadows)
   c. Apply screen-space shaders (hyprshade, etc.)
6. wlr_output_state_set_buffer() — attach rendered FB to output
7. DRM atomic commit (TEST first, then COMMIT)
8. KMS schedules page flip at next vblank
9. 'present' event fires after flip
10. wp-presentation-time: notify clients of exact present timestamp
11. Clients use timestamp for animation frame scheduling
```

The **damage tracking** in step 4a is critical for performance. If only one
window moved, there's no reason to re-render the entire screen. Compositors
track the union of all dirty rectangles since the last frame and only redraw
those areas. Disabling animations or setting them to very short durations
reduces the damaged area and compositor GPU load. Hyprland's `damage_tracking`
option controls this.

```bash
# Visualize damage regions in real time (Hyprland)
hyprctl keyword debug:damage_tracking 1    # highlight damaged regions
hyprctl keyword debug:render_modification  # mark render passes

# Monitor compositor frame timing
hyprctl monitors | grep -E "Hz|refresh"
wp-timing-info 2>/dev/null   # if available

# Check frame pacing with presentation time protocol
WAYLAND_DEBUG=1 weston-simple-egl 2>&1 | grep wp_presentation | head -20

# Frame time profiling with Tracy (if Hyprland built with HYPRLAND_TRACY)
# Or use frame timing data from hyprctl
hyprctl monitors
hyprctl activewindow
```

### 63.9 Debugging GPU Issues

GPU issues on Wayland manifest as visual corruption, black screens, crashes,
high GPU usage, or poor performance. The layered architecture means the root
cause could be in Mesa, the kernel driver, the compositor, or the app. A
systematic approach — checking each layer's debug output — is far faster than
guessing.

```bash
# ── Mesa / OpenGL debugging ──────────────────────────────────────────────────
MESA_DEBUG=1 hyprland 2>&1 | grep -iE "error|warn|fail"
MESA_DEBUG=incomplete_tex,perf app   # specific categories
LIBGL_DEBUG=verbose app              # verbose GL init

# Check for GL errors in an app
MESA_DEBUG=flush app                 # flush after every draw call (slow, catches use-after-free)

# Gallium driver (AMD/Intel OpenGL) debugging
GALLIUM_HUD=fps,cpu app              # heads-up display overlay
GALLIUM_HUD=GPU-load,VRAM-usage app

# ── Vulkan debugging ─────────────────────────────────────────────────────────
VK_LOADER_DEBUG=all app 2>&1 | head -30          # loader debug
VK_INSTANCE_LAYERS=VK_LAYER_KHRONOS_validation app  # validation layer
RADV_DEBUG=errors app 2>&1 | grep -i err         # AMD Vulkan errors
INTEL_DEBUG=errors app 2>&1 | grep -i err        # Intel Vulkan errors

# ── DRM / kernel debugging ───────────────────────────────────────────────────
# Enable verbose DRM logging (very noisy, use briefly)
echo 0x1f | sudo tee /sys/module/drm/parameters/debug
journalctl -k -f --no-pager | grep -E "drm|amdgpu|i915|nouveau"
echo 0x0 | sudo tee /sys/module/drm/parameters/debug  # disable after capture

# Check for GPU hangs, resets, firmware errors
dmesg | grep -iE "gpu hang|gpu reset|amdgpu|i915 reset|nouveau ERR"
journalctl -k -b | grep -iE "hang|reset|timeout" | tail -20

# ── Hyprland-specific diagnostics ────────────────────────────────────────────
HYPRLAND_LOG_LEVEL=TRACE hyprland > /tmp/hyprland.log 2>&1 &
tail -f /tmp/hyprland.log | grep -iE "error|warn|fail|drm|egl"
hyprctl version       # confirm build flags (e.g., explicit sync, Tracy)
hyprctl systeminfo    # GPU info, renderer, Wayland protocols

# ── General GPU health ────────────────────────────────────────────────────────
# AMD
watch -n1 "cat /sys/class/drm/card0/device/gpu_busy_percent"
radeontop              # real-time AMD GPU utilization breakdown
sudo umr -O bits,context -wa gfx_ring0  # decode GPU ring status (AMDgpu Micro Register)

# Intel
intel_gpu_top          # Intel GPU utilization (from igt-gpu-tools)
sudo intel_reg read 0x2358  # ring buffer head/tail register

# NVIDIA (proprietary)
nvidia-smi dmon -s pucvmet   # per-second GPU metrics
watch -n0.5 nvidia-smi

# ── EGL platform issues ───────────────────────────────────────────────────────
# If an app is trying X11 EGL instead of Wayland EGL:
DISPLAY="" EGL_PLATFORM=wayland app   # force Wayland EGL
# Or check which platform is being picked:
EGL_LOG_LEVEL=debug app 2>&1 | grep platform
```

**Common issues and what they mean:**

| Symptom | Likely Layer | Debug Step |
|---|---|---|
| Black screen after compositor start | DRM/KMS | `journalctl -k` for DRM errors |
| Tearing in fullscreen | Sync/Presentation | Check VRR, direct scanout config |
| App crashes on render | Mesa/EGL | `VK_LAYER_KHRONOS_validation` |
| NVIDIA flickering | Explicit sync | Check `nvidia-drm modeset=1` |
| High GPU usage with compositor | Compositor scene | Disable blur/shadows, check damage |
| GPU hang (screen freezes) | Kernel driver | `dmesg` for reset messages |
| Corrupt textures | DMA-BUF sync | Test with `MESA_DEBUG=flush` |

### 63.10 Hardware Video Acceleration (VA-API / VDPAU / NVDEC)

Hardware video acceleration offloads decode/encode work from the CPU to
dedicated fixed-function GPU hardware. On Wayland this integrates tightly with
the DMA-BUF pipeline: decoded video frames emerge from the hardware decoder
as DMA-BUF objects that can go directly to compositor overlay planes, achieving
zero-copy video playback with minimal GPU 3D usage.

**VA-API** (Video Acceleration API, maintained by Intel) is the primary
interface on modern Linux. It supports decode of H.264, H.265, AV1, VP9,
and more across AMD, Intel, and NVIDIA GPUs. The VA-API driver is loaded
by `libva` based on the `LIBVA_DRIVER_NAME` environment variable or
auto-detection.

**VDPAU** (Video Decode and Presentation API for Unix) is the older NVIDIA-
originated API. Less common on modern systems but still supported. Mesa
provides a `libvdpau-va-gl` bridge that implements VDPAU over VA-API.

**NVDEC** is NVIDIA's proprietary hardware decode interface. On Linux with
the proprietary driver, it's accessed via `libva-nvidia-driver` (open source)
or directly by applications via NVDEC APIs.

```bash
# ── Check VA-API setup ────────────────────────────────────────────────────────
vainfo                         # list supported profiles and entry points
vainfo --display drm --device /dev/dri/renderD128  # force DRM backend

# AMD VA-API (via Mesa radeonsi or radv)
LIBVA_DRIVER_NAME=radeonsi vainfo
# Intel VA-API (iHD = modern, i965 = legacy)
LIBVA_DRIVER_NAME=iHD vainfo
LIBVA_DRIVER_NAME=i965 vainfo
# NVIDIA VA-API (requires libva-nvidia-driver)
LIBVA_DRIVER_NAME=nvidia vainfo

# ── Install VA-API drivers ────────────────────────────────────────────────────
# Arch Linux
sudo pacman -S libva-mesa-driver mesa-vdpau    # AMD + Intel (open)
sudo pacman -S intel-media-driver              # Intel iHD (newer GPUs)
sudo pacman -S libva-intel-driver             # Intel i965 (older GPUs)
# NVIDIA VA-API (open source wrapper)
yay -S libva-nvidia-driver

# ── Test hardware decode with mpv ─────────────────────────────────────────────
mpv --hwdec=vaapi video.mkv                    # VA-API decode
mpv --hwdec=vaapi-copy video.mkv               # VA-API decode + CPU copy (safer)
mpv --hwdec=nvdec video.mkv                    # NVIDIA NVDEC
mpv --vo=gpu-next --hwdec=auto-safe video.mkv  # auto select, gpu-next renderer

# Check what mpv actually uses
mpv -v --hwdec=auto video.mkv 2>&1 | grep -iE "hwdec|decoder|vaapi|nvdec"

# ── Firefox hardware decode ───────────────────────────────────────────────────
# about:config settings for VA-API in Firefox:
# media.ffmpeg.vaapi.enabled = true
# media.hardware-video-decoding.force-enabled = true (if blocked)
# Run Firefox with VA-API:
MOZ_DISABLE_RDD_SANDBOX=1 firefox
# Check if hardware decode is active: about:support → Media → Hardware Video Decoding

# ── Chromium / Chrome hardware decode ────────────────────────────────────────
chromium --enable-features=VaapiVideoDecodeLinuxGL \
         --use-gl=desktop \
         --ozone-platform=wayland
# chrome://gpu → check "Video Decode" row

# ── VDPAU check ───────────────────────────────────────────────────────────────
vdpauinfo   # list VDPAU capabilities
```

The DMA-BUF integration means that in an optimal setup, hardware-decoded video
frames are presented to KMS as an overlay plane directly — the compositor's
OpenGL pipeline is bypassed entirely for video. mpv with `--vo=vaapi` and a
compatible compositor achieves this. This is especially visible on low-power
systems (laptops, ARM SBCs) where the power savings are dramatic.

### 63.11 HDR and Wide Color Gamut

High dynamic range (HDR) output requires changes at every layer of the stack.
The KMS layer must set the output to HDR mode (EDID-negotiated via the
`HDR_OUTPUT_METADATA` DRM property). Mesa must allocate 10-bit or 16-bit
framebuffers. The compositor must apply color space transforms. This stack
is actively being developed as of 2024-2025.

```bash
# Check if monitor supports HDR
sudo drm_info | grep -A20 "HDR_OUTPUT_METADATA\|EDID" | head -40

# Check EDID for HDR capability
sudo edid-decode /sys/class/drm/card0-HDMI-A-1/edid | grep -iE "hdr|luminance|eotf"

# KMS HDR metadata property (set by compositor or manually)
# DRM_HDMI_STATIC_METADATA_TYPE1 struct in kernel headers

# Mesa 10-bit format support
weston-info 2>&1 | grep -i "XRGB2101010\|ARGB2101010\|10bit"

# Hyprland HDR (experimental as of 2024)
hyprctl keyword monitor HDMI-A-1,2560x1440@120,0x0,1,hdr:1
# Or in hyprland.conf:
# monitor = HDMI-A-1, 2560x1440@120, 0x0, 1, hdr:1, sdrbrightness:1.0

# Check color management protocol support
wayland-info | grep -E "xx_color|color_manager|wp_color"
```

For the current state of Wayland HDR support, refer to the upstream tracking
issue at freedesktop.org/mesa and the Hyprland GitHub. The
`xx-color-management-v4` protocol (proposed 2024) standardizes color management
for both SDR and HDR content. See Ch 77 for display calibration and ICC
profile management.

## Troubleshooting

This section consolidates the most common GPU/rendering issues encountered
when setting up a Wayland desktop.

**Problem: Compositor fails to start, DRM/KMS errors in journal**
```bash
journalctl -k -b | grep -iE "drm|kms|amdgpu|i915|mode"
# Look for: "failed to set mode", "no valid CRTC", "GPU reset"
# Fix: check that /dev/dri/card0 is accessible (add user to 'video' group)
groups $USER | grep -o video
sudo usermod -aG video $USER   # then re-login
```

**Problem: Screen flickers or tears with NVIDIA proprietary driver**
```bash
# Ensure KMS is enabled for NVIDIA
cat /sys/module/nvidia_drm/parameters/modeset
# If 'N': add to kernel cmdline or modprobe
echo 'options nvidia-drm modeset=1' | sudo tee /etc/modprobe.d/nvidia-kms.conf
sudo mkinitcpio -P

# Ensure explicit sync is supported by compositor
hyprctl keyword render:explicit_sync 2

# Check compositor is using Vulkan renderer (better NVIDIA support)
hyprctl keyword renderer:backend vulkan
```

**Problem: Hardware video decode not working in Firefox/Chromium**
```bash
vainfo   # must show decode profiles — if empty, install driver first
# AMD: sudo pacman -S libva-mesa-driver
# Intel: sudo pacman -S intel-media-driver

# Firefox: set media.ffmpeg.vaapi.enabled=true in about:config
# Then restart Firefox with:
MOZ_DISABLE_RDD_SANDBOX=1 MOZ_ENABLE_WAYLAND=1 firefox
```

**Problem: High GPU usage from compositor even with no activity**
```bash
# Identify the cost: disable effects progressively
hyprctl keyword animations:enabled 0       # disable animations
hyprctl keyword decoration:blur:enabled 0  # disable blur
hyprctl keyword decoration:shadow:enabled 0

# Check damage tracking
hyprctl keyword debug:damage_tracking 1    # visually confirm damage regions

# Profile the compositor render loop
HYPRLAND_LOG_LEVEL=TRACE hyprland 2>&1 | grep -E "render|frame|ms" | head -50
```

**Problem: Application renders with software (llvmpipe) instead of GPU**
```bash
glxinfo | grep "OpenGL renderer"   # shows "llvmpipe" if software
# Causes: missing Mesa driver, wrong LIBGL_DRIVERS_PATH, app forcing software

# Force correct driver
LIBGL_DRIVERS_PATH=/usr/lib/dri glxinfo | grep renderer
DRI_PRIME=0 app    # AMD multi-GPU: force primary GPU (0) or secondary (1)

# Intel + AMD hybrid: force dedicated GPU
DRI_PRIME=1 app    # use discrete GPU
```

**Problem: DMA-BUF import fails, app falls back to wl_shm**
```bash
# Check that zwp-linux-dmabuf-v1 is advertised
wayland-info | grep dmabuf

# Check kernel DMA-BUF support
zcat /proc/config.gz | grep CONFIG_DMA_BUF

# Common cause: mismatched format/modifier negotiation
WAYLAND_DEBUG=1 app 2>&1 | grep -iE "dmabuf|format|modifier" | head -30
```

---

*Related chapters: Ch 61 (X11 vs Wayland architecture), Ch 71 (Compositor
rendering configuration), Ch 74 (VRR and adaptive sync), Ch 77 (Color
management and HDR), Ch 82 (NVIDIA-specific setup). See Ch 53 for session
startup and environment variable injection.*

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
