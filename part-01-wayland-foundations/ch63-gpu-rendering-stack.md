# Chapter 63 — The GPU Rendering Stack: DRM/KMS, Mesa, GBM, EGL

## Overview
Understanding how pixels actually reach the screen — from `wl_surface` commit
through the kernel's DRM subsystem to the display — demystifies compositor
development, debugging, and GPU selection decisions.

## Sections

### 63.1 The Full Stack
```
Wayland client                    Compositor (Hyprland/Sway)
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

### 63.2 DRM/KMS — The Kernel Layer
- **DRM** (Direct Rendering Manager): kernel subsystem for GPU access
- **KMS** (Kernel Mode Setting): configuring display modes from userspace
- Key objects:
  - **CRTC**: a display pipeline (one per active monitor)
  - **Plane**: a hardware overlay (PRIMARY, CURSOR, OVERLAY)
  - **Encoder**: converts CRTC signal to connector format
  - **Connector**: physical output (HDMI, DP, eDP)
  - **Framebuffer**: the buffer being scanned out

**Direct scanout:** When a fullscreen app's buffer matches the plane format
exactly, the compositor can hand it directly to KMS without compositing.
Zero GPU overhead — this is why fullscreen gaming is fast on Wayland.

```bash
# Inspect DRM state
sudo drm_info        # detailed DRM object tree
sudo modetest        # list connectors, modes, planes
cat /sys/class/drm/card*/status   # connected outputs
```

### 63.3 GBM — Generic Buffer Management
- GBM allocates DMA-BUF buffers that DRM can scan out
- `gbm_bo_create()`: allocate a buffer with format + usage flags
- Format matters: `GBM_FORMAT_XRGB8888`, `GBM_FORMAT_ARGB2101010` (HDR)
- Usage flags: `GBM_BO_USE_SCANOUT | GBM_BO_USE_RENDERING`
- wlroots' `wlr_gbm_allocator` wraps this

### 63.4 EGL — The OpenGL-Wayland Bridge
- EGL: creates OpenGL ES contexts on top of native display systems
- `EGL_KHR_platform_gbm`: create EGL display from a GBM device
- `EGLImage` + `EGL_EXT_image_dma_buf_import`: import DMA-BUF into OpenGL
- This is how compositors render to a texture then display it

**Key EGL extensions for Wayland:**
| Extension | Purpose |
|-----------|---------|
| `EGL_KHR_platform_wayland` | Wayland client rendering |
| `EGL_KHR_platform_gbm` | Compositor rendering |
| `EGL_EXT_image_dma_buf_import` | DMA-BUF import |
| `EGL_KHR_fence_sync` | GPU synchronization |
| `EGL_EXT_present_opaque` | Alpha compositing |

### 63.5 Mesa — The Open Source GPU Stack
Mesa implements OpenGL, OpenGL ES, and Vulkan for AMD, Intel, and (increasingly) NVIDIA:

| Driver | GPU | API | Notes |
|--------|-----|-----|-------|
| `radv` | AMD (GCN+) | Vulkan | Primary, production |
| `amdgpu` | AMD | OpenGL via radeonsi | |
| `anv` | Intel (Gen8+) | Vulkan | Primary |
| `iris` | Intel (Gen8+) | OpenGL | |
| `nvk` | NVIDIA (Turing+) | Vulkan | New, improving |
| `zink` | Any | OpenGL over Vulkan | Compatibility layer |
| `llvmpipe` | CPU | All | Software fallback |

```bash
# Check active driver
glxinfo | grep "OpenGL renderer"
vulkaninfo --summary
vainfo  # video acceleration
```

### 63.6 DMA-BUF — Zero-Copy Buffer Sharing
- DMA-BUF: a Linux mechanism for sharing GPU buffers without CPU copies
- Client renders to a DMA-BUF → compositor imports it via `zwp-linux-dmabuf-v1`
- No CPU copy: client → compositor → display is zero-copy on GPU
- `wl_shm` (shared memory): CPU copy required — used only as fallback

**Why DMA-BUF matters for ricing:**
- `ScreencopyView` in Quickshell uses DMA-BUF for efficient screen capture
- Video players (mpv, vlc) use DMA-BUF for zero-copy video display
- Hardware video decoding output goes directly to the compositor via DMA-BUF

### 63.7 Explicit vs. Implicit Synchronization
- **Implicit sync**: GPU fence embedded in buffer (legacy, X11 model)
- **Explicit sync**: caller manages fences explicitly
- `linux-drm-syncobj-v1` Wayland protocol: explicit sync
- Critical for NVIDIA: NVIDIA drivers use explicit sync; old compositors assumed implicit → tearing/corruption
- Hyprland added explicit sync support (2024) → NVIDIA stability improved dramatically

### 63.8 The Compositor Render Loop
```
1. wlr_output 'frame' event fires (vsync)
2. Compositor traverses scene graph
3. For each surface: acquire damage region
4. Render damaged areas with OpenGL/Vulkan
5. wlr_output_state_set_buffer() → submit to KMS
6. KMS → DRM → hardware flip
7. wlr_output 'present' event → notify clients via wp-presentation-time
```

### 63.9 Debugging GPU Issues
```bash
# Mesa debug
MESA_DEBUG=1 hyprland 2>&1 | grep -i error
LIBGL_DEBUG=verbose app

# DRM debug
echo 0x1f > /sys/module/drm/parameters/debug  # verbose DRM logs
journalctl -k | grep drm

# Vulkan
VK_LOADER_DEBUG=all app 2>&1 | head -50

# Check for GPU hangs
dmesg | grep -i "gpu\|hang\|reset\|amdgpu\|i915"
```

### 63.10 Hardware Video Acceleration (VA-API / VDPAU)
- VA-API: Intel/AMD/NVIDIA hardware video decode
- Used by: Firefox, mpv, Chromium, OBS
- `libva-mesa-driver` (AMD/Intel), `libva-nvidia-driver` (NVIDIA)
```bash
vainfo  # list supported codecs
# mpv with VA-API:
mpv --hwdec=vaapi video.mkv
```
