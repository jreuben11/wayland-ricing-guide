# Chapter 123 — Input Latency Measurement on Wayland

## Overview

Wayland compositors often claim lower input latency than X11, but verifying this claim requires concrete measurement tools. This chapter covers the toolchain for measuring input latency on Wayland: from kernel event timestamps through compositor pipeline to display scanout. It also covers practical latency reduction techniques at the kernel, compositor, and hardware levels.

**Cross-references:** Ch 43 — input customization (libinput settings). Ch 122 — gaming protocols (tearing, VRR interaction). Ch 42 — gaming overview.

---

## 123.1 Where Latency Hides

```
Physical input device
  → Linux kernel HID driver (< 0.1 ms with threadirqs)
  → libinput event queue (0–2 ms)
  → Wayland compositor event dispatch (0–1 ms on same frame)
  → Application input handling (varies)
  → Application render (frame time)
  → Compositor compositing (0–2 ms)
  → DRM/KMS scanout (0–16.6 ms vsync wait at 60Hz)
  → Display propagation (0–2 ms, panel response time)
  → Photon hits eye
Total: 10–50 ms typical, 1–5 ms theoretical minimum
```

The dominant latency source is the **vsync wait**: a compositor that waits for vblank to present a frame adds up to one full frame period (16.6 ms at 60 Hz, 6.9 ms at 144 Hz). Tearing (Ch 122) and VRR (Ch 41) both reduce this component.

---

## 123.2 Kernel-Level Measurement: evtest

`evtest` captures raw kernel input events with microsecond timestamps from `/dev/input/eventN`:

```bash
# Install
sudo pacman -S evtest

# List devices
sudo evtest --query /dev/input/event*

# Capture mouse button events with timestamps
sudo evtest /dev/input/event4 | grep -E "EV_KEY|time"
# Output format:
# Event: time 1718000000.123456, type 1 (EV_KEY), code 272 (BTN_LEFT), value 1
```

The timestamp in `evtest` is the kernel's `struct timeval` from the input event. Compare this to the `wp_presentation` feedback timestamp (Ch 122) in a test application to measure the full pipeline latency.

### Automated Latency Sampling Script

```bash
#!/bin/bash
# Measure keyboard input → kernel timestamp gap
# Press a key repeatedly and measure inter-event jitter

sudo evtest /dev/input/by-id/usb-YOUR_KEYBOARD-event-kbd 2>/dev/null | \
  awk '/EV_KEY.*value 1/ {
    if (prev != "") {
      split($2, a, ".")
      split(prev, b, ".")
      diff = (a[1] - b[1]) * 1000 + (a[2] - b[2]) / 1000
      print "Event gap: " diff " ms"
    }
    prev = $2
  }'
```

---

## 123.3 libinput Timestamp Analysis

`libinput debug-events` shows processed input events with timestamps, reflecting the latency added by libinput's event processing:

```bash
sudo libinput debug-events --verbose 2>&1 | grep -E "POINTER|KEYBOARD" | head -20
```

The delta between `evtest` timestamps and `libinput debug-events` timestamps is libinput's processing overhead (typically < 0.5 ms).

---

## 123.4 Compositor-to-Display Latency: wev + Frame Timing

`wev` (Wayland event viewer) shows Wayland events received by a client, including frame callbacks:

```bash
# Install
sudo pacman -S wev

# Run and observe frame callback timing
wev 2>&1 | grep -E "frame|timestamp"
```

For frame timing measurement, write a minimal Wayland client that:
1. Receives pointer events via `wl_pointer`
2. Records the event timestamp
3. Renders a frame immediately
4. Records the `wp_presentation` timestamp when the frame is presented
5. Computes the difference

---

## 123.5 End-to-End Measurement: Camera Method

The most accurate latency measurement uses a high-frame-rate camera (120fps+) pointed at both the input device and the display:

1. Set up the camera to record both the mouse/keyboard and the screen
2. Perform a click or keypress
3. Count frames between the physical input and the first pixel change on screen
4. Multiply by frame duration (8.33 ms at 120fps)

This measures the complete photon-to-photon latency including display propagation. A typical Wayland result on a 144Hz monitor: **15–25 ms** end-to-end. X11 baseline on the same hardware: **25–40 ms**.

Open-source tools for automated camera-based measurement:
```bash
# displaylag-benchmark (if available)
# Or use a smartphone in slo-mo video mode (240fps = 4.2ms resolution)
```

---

## 123.6 Latency Reduction Techniques

### Kernel: threadirqs

`threadirqs` moves interrupt handlers to dedicated kernel threads, preventing USB input interrupts from being delayed by other interrupt handlers:

```bash
# Add to GRUB_CMDLINE_LINUX in /etc/default/grub:
GRUB_CMDLINE_LINUX="... threadirqs"
sudo grub-mkconfig -o /boot/grub/grub.cfg
```

Effect: reduces worst-case input latency jitter from ~2ms to ~0.1ms.

### Kernel: preempt=full

A fully preemptible kernel (`CONFIG_PREEMPT=y`) reduces scheduler latency:

```bash
# Check current preempt model
cat /boot/config-$(uname -r) | grep CONFIG_PREEMPT

# On Arch: linux-rt or linux-zen has better preemption
sudo pacman -S linux-zen linux-zen-headers
```

### USB Polling Rate

USB mice default to 125 Hz (8ms between polls). High-end gaming mice support 1000 Hz (1ms) or 4000–8000 Hz (0.125ms):

```bash
# Check current USB polling rate
sudo usbhid-ups   # or:
cat /sys/bus/usb/devices/*/speed

# Force 1000Hz polling (USB HID quirk)
# Add to /etc/udev/rules.d/99-mouse-poll.rules:
# SUBSYSTEM=="usb", ATTR{idVendor}=="046d", ATTR{idProduct}=="c548", \
#   ATTR{bcdUSB}=="0200", RUN+="/sbin/modprobe -q usbhid && \
#   /bin/sh -c 'echo 1 > /sys/bus/usb/devices/BUSNUM-PORTNUM/1000'"
```

The simpler approach for supported mice:
```bash
# Install and use `razer-nari-udev` or `openrazer` for Razer
# For Logitech: `logiops`
# For general HID polling: `usbhid-dkms` with polling rate parameter
sudo modprobe usbhid mousepoll=1   # 1 = 1000Hz
```

### Compositor: Reduce Pipeline Stages

```ini
# Hyprland: disable unnecessary effects for gaming workspace
# workspace 6 = gaming workspace
workspace = 6, rounding:false, decorate:false, gapsout:0, gapsin:0

# Disable animations for the gaming workspace
windowrulev2 = noanim, workspace:6
```

### VRR for Latency Reduction

With VRR active, the compositor presents each frame as soon as it's ready, without waiting for the next vblank. This reduces average latency by approximately half the frame period:

```ini
# Hyprland
misc {
    vrr = 1   # 0=off, 1=on, 2=fullscreen-only
}
```

At 144Hz with VRR: average latency ~3.5 ms from render-complete to present, vs ~6.9 ms without VRR.

---

## 123.7 Latency Profiling Summary

| Tool | Measures | Typical value |
|---|---|---|
| `evtest` timestamps | Kernel HID event time | < 0.1 ms jitter with threadirqs |
| `libinput debug-events` | libinput processing overhead | 0.1–0.5 ms |
| `wev` frame callbacks | Compositor frame delivery | 0–1 ms |
| `wp_presentation` feedback | Compositor → scanout | 0–16.6 ms (vsync) |
| Camera (120fps) | Full end-to-end | 15–50 ms |
