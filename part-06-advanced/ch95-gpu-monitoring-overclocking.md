# Chapter 95 — GPU Monitoring and Overclocking

## Contents

- [Overview](#overview)
- [95.1 nvtop — Universal GPU Monitor](#951-nvtop-universal-gpu-monitor)
- [95.2 radeontop — AMD-Specific Terminal Monitor](#952-radeontop-amd-specific-terminal-monitor)
- [95.3 intel_gpu_top — Intel GPU Monitor](#953-intelgputop-intel-gpu-monitor)
- [95.4 lact — Linux AMD Control Tool (Wayland GUI)](#954-lact-linux-amd-control-tool-wayland-gui)
  - [lact features](#lact-features)
  - [Fan curve configuration (lact)](#fan-curve-configuration-lact)
  - [CLI-level control (bypassing lact GUI)](#cli-level-control-bypassing-lact-gui)
- [95.5 corectrl — Qt AMD/Intel Control](#955-corectrl-qt-amdintel-control)
- [95.6 GPU Status in the Status Bar](#956-gpu-status-in-the-status-bar)
  - [Quickshell module (reading from sysfs)](#quickshell-module-reading-from-sysfs)
  - [AMD sysfs paths](#amd-sysfs-paths)
  - [NVIDIA sysfs / nvidia-smi](#nvidia-sysfs-nvidia-smi)
  - [Waybar custom GPU module](#waybar-custom-gpu-module)
- [95.7 AMD Overclocking via sysfs (without lact)](#957-amd-overclocking-via-sysfs-without-lact)
  - [AMD voltage offset (RDNA 2/3 undervolting)](#amd-voltage-offset-rdna-23-undervolting)
- [95.8 Persist Overclocking at Boot](#958-persist-overclocking-at-boot)

---


## Overview

GPU monitoring gives you real-time performance data (temperature, clock speeds,
VRAM usage) for your status bar or terminal. Overclocking/undervolting squeezes
more performance from ricing GPU tasks (compositing, shader effects) or reduces
power consumption and heat. All tools here are Wayland-native or terminal-based.

---

## 95.1 nvtop — Universal GPU Monitor

nvtop supports NVIDIA, AMD, Intel, and Apple Silicon GPUs in a unified TUI:

```bash
sudo pacman -S nvtop
nvtop
```

Displays per-GPU: utilization %, VRAM used/total, temperature, power draw,
clock speeds, and per-process GPU usage. Press `F2` for setup, `q` to quit.

For status bar integration:
```bash
# Extract GPU utilization for Waybar custom module
nvtop --no-color 2>/dev/null | grep -oP '\d+(?=%)' | head -1
```

---

## 95.2 radeontop — AMD-Specific Terminal Monitor

```bash
sudo pacman -S radeontop
radeontop         # requires root or membership in 'video' group
radeontop -c      # color output
radeontop -d -    # dump to stdout (for scripts)
```

Shows the AMD GPU pipeline utilization bars: Graphics Pipe, Texture Addresser,
Shader Export, Scan Converter, etc. More detailed than nvtop for AMD internals.

```bash
# Add user to video group for non-root access
sudo usermod -aG video $(whoami)
```

---

## 95.3 intel_gpu_top — Intel GPU Monitor

```bash
sudo pacman -S intel-gpu-tools
intel_gpu_top     # requires root
sudo intel_gpu_top -d drm:/dev/dri/renderD128
```

Shows render engine, blitter, video decode, video enhance utilization.

---

## 95.4 lact — Linux AMD Control Tool (Wayland GUI)

lact is a GTK4/Wayland-native GPU control application for AMD GPUs. It provides
OC/UV, fan curves, power profiles, and monitoring in one GUI.

```bash
paru -S lact
sudo systemctl enable --now lactd    # daemon required

# Launch GUI
lact
```

### lact features

- **Power profiles**: Balanced / Performance / Power Save
- **Clock ranges**: set min/max GPU and memory clocks
- **Fan curve**: custom RPM-to-temperature mapping
- **Voltage offset**: undervolting (reduces heat and power)
- **VRAM clock limit**: reduce for efficiency
- **Power limit**: cap max wattage

### Fan curve configuration (lact)

In the lact GUI → Fan Control → Manual:
```
Temperature (°C) | Fan Speed (%)
35               | 20
55               | 40
70               | 60
80               | 80
90               | 100
```

### CLI-level control (bypassing lact GUI)

lact's daemon exposes a REST API:
```bash
# Get current GPU info
curl http://localhost:6969/api/devices | jq

# Set power profile
curl -X POST http://localhost:6969/api/devices/0/power/profile \
  -H "Content-Type: application/json" \
  -d '"performance"'
```

---

## 95.5 corectrl — Qt AMD/Intel Control

```bash
paru -S corectrl

# Allow corectrl to adjust GPU without password
# /etc/polkit-1/rules.d/90-corectrl.rules:
polkit.addRule(function(action, subject) {
    if ((action.id == "org.corectrl.helper.init" ||
         action.id == "org.corectrl.helperkiller.init") &&
        subject.local == true && subject.active == true &&
        subject.isInGroup("your-username")) {
        return polkit.Result.YES;
    }
});
```

corectrl uses Qt6 and renders natively on Wayland. Features similar to lact
but supports Intel Arc GPUs additionally.

---

## 95.6 GPU Status in the Status Bar

### Quickshell module (reading from sysfs)

```qml
// GpuMonitor.qml
import Quickshell
import Quickshell.Io

pragma Singleton

Singleton {
    id: root

    property real gpuUsage: 0
    property real gpuTemp: 0
    property real gpuVram: 0

    // AMD: read from hwmon
    FileView {
        id: tempFile
        path: "/sys/class/hwmon/hwmon1/temp1_input"  // adjust hwmon index
        onTextChanged: root.gpuTemp = parseInt(text.trim()) / 1000.0
    }

    // Poll every 2 seconds
    Timer {
        interval: 2000
        running: true
        repeat: true
        onTriggered: {
            tempFile.reload()
            usageProc.startDetached()
        }
    }

    Process {
        id: usageProc
        command: ["sh", "-c",
            "cat /sys/class/drm/card0/device/gpu_busy_percent"]
        stdout: StdioCollector {
            onStreamedLine: line => root.gpuUsage = parseInt(line.trim())
        }
    }
}
```

### AMD sysfs paths

```bash
# GPU utilization
cat /sys/class/drm/card0/device/gpu_busy_percent

# GPU temperature (hwmon — adjust index for your GPU)
ls /sys/class/hwmon/  # find the amdgpu hwmon
cat /sys/class/hwmon/hwmon2/temp1_input    # milli-degrees C, divide by 1000

# VRAM usage
cat /sys/class/drm/card0/device/mem_info_vram_used   # bytes
cat /sys/class/drm/card0/device/mem_info_vram_total  # bytes

# GPU clock speed
cat /sys/class/drm/card0/device/pp_dpm_sclk | grep '*'

# Power draw
cat /sys/class/hwmon/hwmon2/power1_average   # microwatts
```

### NVIDIA sysfs / nvidia-smi

```bash
# GPU utilization
nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits

# Temperature
nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits

# VRAM
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader

# Power draw
nvidia-smi --query-gpu=power.draw --format=csv,noheader,nounits
```

### Waybar custom GPU module

```json
// waybar config
"custom/gpu": {
    "exec": "cat /sys/class/drm/card0/device/gpu_busy_percent",
    "format": "󰢮 {}%",
    "interval": 2,
    "tooltip-format": "GPU: {}%"
}
```

---

## 95.7 AMD Overclocking via sysfs (without lact)

```bash
# Check current power profile
cat /sys/class/drm/card0/device/power_dpm_force_performance_level

# Set to manual (required for OC)
echo "manual" | sudo tee /sys/class/drm/card0/device/power_dpm_force_performance_level

# Show available GPU clock states
cat /sys/class/drm/card0/device/pp_dpm_sclk

# Lock GPU to highest clock state (e.g., state 7)
echo "7" | sudo tee /sys/class/drm/card0/device/pp_dpm_sclk

# Set performance profile (replaces manual for simple boost)
# Options: auto, low, high, manual, battery, balanced, performance
echo "performance" | sudo tee /sys/class/drm/card0/device/power_dpm_force_performance_level

# Restore auto
echo "auto" | sudo tee /sys/class/drm/card0/device/power_dpm_force_performance_level
```

### AMD voltage offset (RDNA 2/3 undervolting)

```bash
# Enable OverDrive (required for voltage control)
# Add to kernel cmdline:
# amdgpu.ppfeaturemask=0xffffffff

# Set voltage offset (e.g., -50mV)
echo "s 0 -50" | sudo tee /sys/class/drm/card0/device/pp_od_clk_voltage
echo "c" | sudo tee /sys/class/drm/card0/device/pp_od_clk_voltage  # commit
```

This is better managed through lact's GUI which validates ranges safely.

---

## 95.8 Persist Overclocking at Boot

```bash
# /etc/systemd/system/gpu-overclock.service
[Unit]
Description=GPU Performance Profile
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'echo "performance" > /sys/class/drm/card0/device/power_dpm_force_performance_level'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

Or use lact which handles persistence automatically via its daemon.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
