# Chapter 56 — PipeWire System Setup: WirePlumber, EasyEffects, Audio Routing

## Overview

PipeWire is the universal audio/video server that replaced PulseAudio and JACK on modern Linux systems. It provides a unified API for audio and video processing with compatibility layers for legacy PulseAudio and JACK applications. Ch 21 covers the Quickshell PipeWire API (`Quickshell.Services.Pipewire`). This chapter covers installing, configuring, and mastering PipeWire as a complete system — from initial setup through pro audio routing, Bluetooth codecs, EQ, and screen capture.

PipeWire was designed from the ground up to solve the long-standing fragmentation of the Linux audio stack. Before PipeWire, you had to choose between PulseAudio (desktop audio, mixing, per-application volume) and JACK (pro audio, low-latency, routing). PipeWire unifies both use cases in a single daemon that speaks all their protocols natively. This makes it possible to run an Ardour session on the same system that serves your Discord voice chat, at the same time, without glitches.

The graph architecture at PipeWire's core is the key to its flexibility. Every audio producer and consumer is a "node" in a directed graph. Links connect nodes, and buffers flow along those links. WirePlumber, the session manager, decides which nodes to create and how to link them according to configurable policy. Understanding this model is essential before diving into configuration — almost every PipeWire config option refers to some aspect of node properties, buffer sizing, or link policy.

See Ch 53 for session startup and autolaunch of audio services. See Ch 57 for notification sounds and event audio integration. See Ch 61 for media key bindings that interact with PipeWire's volume control.

---

## 56.1 PipeWire Architecture

The PipeWire stack has five major components that work together:

```
Hardware (ALSA) ↔ PipeWire daemon (pipewire)
                    ↕
               WirePlumber (session manager — routes and policy)
                    ↕
         ┌──────────┼──────────┐
    PulseAudio   JACK API   Native PW
    compat       compat      clients
    (pipewire-pulse) (pipewire-jack)
```

- **pipewire**: the graph daemon (nodes, links, buffers)
- **wireplumber**: the session manager (routing decisions, device policy)
- **pipewire-pulse**: PulseAudio compatibility layer (replaces pulseaudio daemon)
- **pipewire-jack**: JACK compatibility layer (for pro audio, transparent to JACK clients)
- **pipewire-alsa**: ALSA compatibility (routes ALSA calls through PipeWire graph)

The PipeWire daemon itself is relatively thin — it manages the shared memory graph and schedules buffer passing between nodes. All intelligence about which devices to create, which applications to connect to which sinks, and what to do when a Bluetooth headset connects, lives in WirePlumber. WirePlumber is scriptable in Lua, which gives you fine-grained control over policy without patching C code.

The compatibility layers deserve special attention. `pipewire-pulse` starts a socket at the same path PulseAudio used (`/run/user/1000/pulse/native`), so any application that calls `libpulse` connects to PipeWire transparently. Similarly, `pipewire-jack` provides a JACK server socket. This means unmodified binary applications compiled against PulseAudio or JACK work without recompilation. The compatibility is nearly complete — the only gaps are obscure PulseAudio extensions that had no equivalent functionality.

Understanding the clock hierarchy helps when tuning for latency. PipeWire uses a cycle-based scheduler: every quantum (buffer size in frames) the scheduler wakes up, processes all nodes in topological order, and sleeps until the next cycle. The `default.clock.quantum` property controls this buffer size. Larger quanta mean less CPU overhead but more latency. Smaller quanta mean more responsive audio but higher CPU and risk of xruns (buffer underruns that cause crackling).

| Component | Role | Config Path |
|---|---|---|
| pipewire | graph daemon, buffer scheduling | `~/.config/pipewire/pipewire.conf.d/` |
| wireplumber | session manager, routing policy | `~/.config/wireplumber/wireplumber.conf.d/` |
| pipewire-pulse | PulseAudio protocol proxy | inherits pipewire config |
| pipewire-jack | JACK protocol proxy | `PIPEWIRE_LATENCY` env var |
| pipewire-alsa | ALSA plugin redirect | system alsa conf |

---

## 56.2 Installation

### Arch Linux

On Arch, all PipeWire components are in the official repositories. If you have PulseAudio installed, remove it first to avoid conflicts — both provide the same socket path and only one can win.

```bash
# Remove PulseAudio if present (it conflicts)
sudo pacman -Rs pulseaudio pulseaudio-bluetooth pulseaudio-alsa 2>/dev/null || true

# Install core PipeWire stack
sudo pacman -S pipewire pipewire-alsa pipewire-pulse pipewire-jack wireplumber

# Install audio utilities
sudo pacman -S pipewire-audio  # meta package pulling common extras

# Enable user services (usually auto-started via systemd user session)
systemctl --user enable --now pipewire pipewire-pulse wireplumber

# Verify they started correctly
systemctl --user status pipewire wireplumber
```

After installation, verify the compatibility layer is active and PipeWire is serving as the PulseAudio backend:

```bash
pactl info | grep "Server Name"
# Expected: Server Name: PulseAudio (on PipeWire 1.x.y)

pw-top                           # live graph view (q to quit)
wpctl status                     # list all devices and streams
```

### Ubuntu / Debian

Ubuntu 22.04+ ships PipeWire by default but may not enable all compatibility layers. On older Ubuntu versions you need to enable the pipewire-pulse socket manually:

```bash
# Ubuntu 22.04+: PipeWire is present but pulse may need enabling
systemctl --user --now enable pipewire-pulse

# Verify
pactl info | grep "Server Name"

# If still showing pulseaudio, disable it
systemctl --user disable --now pulseaudio pulseaudio.socket
systemctl --user enable --now pipewire pipewire-pulse wireplumber
```

### NixOS

NixOS has first-class PipeWire support. The `services.pipewire` module handles everything including socket activation and service ordering:

```nix
# /etc/nixos/configuration.nix or audio.nix module
hardware.pulseaudio.enable = false;  # explicitly disable PulseAudio
security.rtkit.enable = true;        # real-time scheduling for low latency

services.pipewire = {
    enable = true;
    alsa.enable = true;
    alsa.support32Bit = true;  # for 32-bit games (Wine/Steam)
    pulse.enable = true;
    jack.enable = true;        # optional: for pro audio
    wireplumber.enable = true;

    # Extra config via extraConfig
    extraConfig.pipewire."10-clock-rate" = {
        "context.properties" = {
            "default.clock.rate" = 48000;
            "default.clock.quantum" = 1024;
        };
    };
};
```

---

## 56.3 WirePlumber Configuration

WirePlumber is the session manager that makes routing decisions. It watches for new devices (USB audio interfaces, Bluetooth headsets, HDMI monitors with audio) and new applications, and applies policy to link them. Configuration lives in `~/.config/wireplumber/wireplumber.conf.d/` as Lua-syntax `.conf` files. Files are loaded in lexicographic order, so prefix them with numbers to control precedence.

The WirePlumber configuration language is a hybrid: it looks like Lua but is actually parsed as a structured properties format with Lua-callable API hooks. The `rule` construct is the workhorse — it matches nodes by their properties and applies property overrides. Matching is done with simple string equality, prefix matching, or glob patterns.

**Disable a specific unwanted device:**

```lua
-- ~/.config/wireplumber/wireplumber.conf.d/51-disable-camera.conf
rule = {
    matches = {
        {
            { "node.name", "=", "v4l2_input.pci-0000:00:14.0-usb-0:3:1.0-video-index0" }
        }
    },
    apply_properties = {
        ["node.disabled"] = true
    }
}
```

**Force a device to a specific sample rate:**

```lua
-- ~/.config/wireplumber/wireplumber.conf.d/52-force-samplerate.conf
rule = {
    matches = {
        {
            { "node.name", "~", "alsa_output.*" }
        }
    },
    apply_properties = {
        ["audio.rate"] = 48000,
        ["audio.format"] = "S32LE",
    }
}
```

**Persistent device priority (prefer USB audio over onboard):**

```lua
-- ~/.config/wireplumber/wireplumber.conf.d/53-device-priority.conf
rule = {
    matches = {
        {
            { "device.name", "~", "alsa_card.usb*" }
        }
    },
    apply_properties = {
        ["device.priority"] = 2000,  -- higher = preferred default
    }
}
```

**Common WirePlumber CLI commands:**

```bash
# List all audio devices and streams with IDs
wpctl status

# Set default output (sink)
wpctl set-default <SINK_ID>

# Set default input (source)
wpctl set-default <SOURCE_ID>

# Volume control (0-1.5 scale, >1.0 is amplification)
wpctl set-volume @DEFAULT_AUDIO_SINK@ 0.5        # 50%
wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%+         # increase 5%
wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-         # decrease 5%
wpctl set-volume @DEFAULT_AUDIO_SINK@ 1.5         # 150% (boosted)

# Mute toggle
wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle
wpctl set-mute @DEFAULT_AUDIO_SOURCE@ 1           # force mute mic

# Get current volume as float
wpctl get-volume @DEFAULT_AUDIO_SINK@

# Inspect a specific node's properties
wpctl inspect <NODE_ID>
```

Reload WirePlumber after config changes without rebooting:

```bash
systemctl --user restart wireplumber
```

---

## 56.4 pw-top and Monitoring the Audio Graph

`pw-top` is an ncurses interface showing all active PipeWire nodes, their sample rates, latency, and driver status. It is indispensable for diagnosing xruns and identifying which application is driving the graph clock.

```bash
pw-top         # like htop but for audio nodes; 'q' to quit

# One-shot snapshot of graph objects
pw-cli list-objects

# Dump detailed info about all nodes
pw-cli dump Node

# Monitor graph events in real time
pw-mon

# PulseAudio compat queries (still useful)
pactl list sinks short
pactl list sources short
pactl list sink-inputs short    # playing streams
pactl list source-outputs short # recording streams
```

The `pw-top` columns to watch:

| Column | Meaning |
|---|---|
| NAME | Node name (alsa_output.*, bluez_output.*) |
| QUANT | Current quantum (buffer size in frames) |
| RATE | Sample rate |
| WAIT | Time node waited for data (should be stable) |
| BUSY | Processing time per cycle |
| W/Q | WAIT/QUANTUM ratio — spikes indicate xruns |

When `W/Q` consistently exceeds 1.0, you have buffer underruns. Increase `default.clock.quantum` or check for CPU throttling (disable power saving for audio work: `cpupower frequency-set -g performance`).

For scripting and monitoring from waybar or eww widgets, the `pw-dump` command outputs JSON:

```bash
# Get current default sink volume as percentage for status bar
pw-dump | python3 -c "
import json, sys
data = json.load(sys.stdin)
for obj in data:
    if obj.get('type') == 'PipeWire:Interface:Node':
        props = obj.get('info', {}).get('props', {})
        if props.get('media.class') == 'Audio/Sink':
            print(props.get('node.nick', props.get('node.name', 'unknown')))
"
```

---

## 56.5 Audio Quality Configuration

The default PipeWire configuration is conservative — tuned for compatibility rather than quality. For a daily driver, you should explicitly set the sample rate, bit depth, and resampling quality to match your audio hardware and use case.

Create a drop-in config file in `~/.config/pipewire/pipewire.conf.d/`. Drop-ins override only the keys they set, leaving everything else at defaults. This is safer than editing the system-wide `pipewire.conf` directly.

**High-quality desktop audio (best for music listening):**

```conf
# ~/.config/pipewire/pipewire.conf.d/10-quality.conf
context.properties = {
    default.clock.rate = 48000
    default.clock.quantum = 1024
    default.clock.min-quantum = 32
    default.clock.max-quantum = 8192
    resample.quality = 15      # 0-15, 15 = sinc resampler (highest quality)
}
```

**Low latency (pro audio / live monitoring):**

```conf
# ~/.config/pipewire/pipewire.conf.d/11-low-latency.conf
context.properties = {
    default.clock.rate = 48000
    default.clock.quantum = 64          # ~1.3ms at 48kHz
    default.clock.min-quantum = 32      # allows driver to request smaller
    default.clock.max-quantum = 64      # cap at 64 to prevent sudden jumps
    default.clock.rate = 48000
}
```

**High-resolution audio (DAC with 96kHz/192kHz support):**

```conf
# ~/.config/pipewire/pipewire.conf.d/12-hires.conf
context.properties = {
    default.clock.rate = 96000          # or 192000 if your DAC supports it
    default.clock.allowed-rates = [ 44100 48000 88200 96000 192000 ]
    default.clock.quantum = 2048
    resample.quality = 15
}
```

The `default.clock.allowed-rates` list tells PipeWire which sample rates are acceptable. When a stream requests a rate in this list, PipeWire will switch to that rate instead of resampling — important for audiophile setups where resampling introduces artifacts. `resample.quality = 15` uses the highest-quality windowed sinc resampler for all conversions that do occur.

Apply changes by restarting the PipeWire daemon:

```bash
systemctl --user restart pipewire
# wireplumber automatically reconnects
```

---

## 56.6 EasyEffects — System-Wide Audio EQ and Effects

EasyEffects (formerly PulseEffects) is a GTK application that inserts a virtual sink into the PipeWire graph. All audio routed through this virtual sink passes through a configurable chain of effects: parametric EQ, compressor, limiter, reverb, stereo enhancer, and more. It operates at the PipeWire level — entirely compatible and zero reconfiguration needed for new applications.

```bash
# Arch
sudo pacman -S easyeffects

# Flatpak (works on any distro, sandboxed)
flatpak install flathub com.github.wwmm.easyeffects

# Ubuntu/Debian
sudo apt install easyeffects
```

Run EasyEffects as a background service so it starts before any audio plays:

```bash
# Add to your Hyprland/Sway exec-once / autostart
easyeffects --gapplication-service

# Or as a systemd user service:
cat > ~/.config/systemd/user/easyeffects.service << 'EOF'
[Unit]
Description=EasyEffects audio effects service
After=pipewire.service wireplumber.service
Wants=pipewire.service

[Service]
ExecStart=/usr/bin/easyeffects --gapplication-service
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
EOF
systemctl --user enable --now easyeffects
```

**Headphone EQ setup with AutoEQ:**

AutoEQ is a community project that has measured hundreds of headphone models and generated correction EQ curves for them. The corrections compensate for the headphone's frequency response deviation from the Harman target curve.

```bash
# Find your headphone model at https://github.com/jaakkopasanen/AutoEq
# Download the ParametricEQ.txt for your model

# Example: Sennheiser HD 600
wget "https://raw.githubusercontent.com/jaakkopasanen/AutoEq/master/results/oratory1990/harman_over-ear_2018/Sennheiser%20HD%20600/Sennheiser%20HD%20600%20ParametricEQ.txt" \
     -O ~/Downloads/hd600-eq.txt

# In EasyEffects:
# 1. Open EasyEffects → Output tab
# 2. Add effect: Equalizer
# 3. Click "Import APO preset" or manually enter the PEQ bands
# 4. Save as preset with your headphone model name
```

EasyEffects presets are stored as JSON in `~/.config/easyeffects/output/`. You can version-control these and share them:

```bash
ls ~/.config/easyeffects/output/
# hd600.json  desktop-speakers.json  gaming.json

# Example preset structure (truncated)
cat ~/.config/easyeffects/output/hd600.json | python3 -m json.tool | head -30
```

**Adding a compressor for consistent volume levels (great for movies/podcasts):**

In EasyEffects, add a Compressor effect with these starting values and tune to taste:
- Attack: 20ms, Release: 250ms, Ratio: 4:1, Threshold: -18dB, Knee: 6dB, Makeup: auto

---

## 56.7 Bluetooth Audio

Bluetooth audio in PipeWire is handled through the `libspa-bluetooth` plugin, which is included in most distributions as part of `pipewire-bluetooth`. It supports a wide range of Bluetooth audio profiles and codecs including the high-quality LDAC and aptX HD codecs found in Android flagship devices.

```bash
# Arch: install Bluetooth stack
sudo pacman -S bluez bluez-utils blueman
sudo systemctl enable --now bluetooth

# Verify bluetooth service
bluetoothctl show

# Install high-quality codec support
sudo pacman -S libspa-bluetooth    # or pipewire-bluetooth (distro-dependent name)
```

**Codec support matrix:**

| Codec | Quality | Latency | Requires |
|---|---|---|---|
| SBC | Baseline (lossy) | ~150ms | Built-in |
| AAC | Good (lossy) | ~150ms | libspa-bluetooth |
| aptX | Good (lossy) | ~80ms | libspa-bluetooth |
| aptX HD | High quality | ~80ms | libspa-bluetooth |
| LDAC | Near-lossless | ~200ms | libspa-bluetooth |
| LC3 | Bluetooth LE Audio | ~50ms | Kernel ≥6.0 |

**Configure codec preference in WirePlumber:**

```conf
# ~/.config/wireplumber/wireplumber.conf.d/51-bluetooth-policy.conf
bluetooth.policy = {
    roles = [ a2dp_sink a2dp_source hfp_hf hfp_ag ]
    codecs = [ ldac aptx_hd aac sbc ]  # priority order: try first to last
}

monitor.bluez.properties = {
    bluez5.roles = [ a2dp_sink a2dp_source hfp_hf hfp_ag ]
    bluez5.codecs = [ ldac aptx_hd aac sbc ]
    bluez5.enable-sbc-xq = true         # enable SBC-XQ (improved SBC quality)
    bluez5.enable-msbc = true           # mSBC for HFP voice calls
    bluez5.enable-hw-volume = true      # hardware volume control
    bluez5.headset-roles = [ hfp_hf hsp_hs ]
}
```

**Pair a Bluetooth device from the command line:**

```bash
bluetoothctl
# Inside bluetoothctl interactive shell:
power on
agent on
scan on
# ... wait for your device MAC to appear, e.g. 00:1A:2B:3C:4D:5E
pair 00:1A:2B:3C:4D:5E
connect 00:1A:2B:3C:4D:5E
trust 00:1A:2B:3C:4D:5E
scan off
exit
```

**Switch between A2DP (music) and HFP (voice calls with mic):**

```bash
# List Bluetooth card profiles
pactl list cards | grep -A 20 bluez

# Switch to high-quality stereo (A2DP)
pactl set-card-profile bluez_card.00_1A_2B_3C_4D_5E a2dp_sink

# Switch to headset mode (HFP — enables microphone but lower quality audio)
pactl set-card-profile bluez_card.00_1A_2B_3C_4D_5E headset_head_unit

# Or using wpctl
wpctl set-profile <CARD_ID> <PROFILE_NAME>
```

Auto-switch to A2DP when no VoIP application is active. Add this WirePlumber rule:

```lua
-- ~/.config/wireplumber/wireplumber.conf.d/54-bluetooth-auto-switch.conf
-- Prefer A2DP over HFP unless a communication app is active
monitor.bluez.rules = [
    {
        matches = [ { "device.name" = "~bluez_card.*" } ]
        actions = {
            update-props = {
                "bluez5.auto-connect" = [ "a2dp_sink" "hfp_hf" ]
            }
        }
    }
]
```

---

## 56.8 JACK Applications and Pro Audio

`pipewire-jack` replaces the JACK daemon entirely. JACK clients connect to PipeWire's JACK socket (`/run/user/1000/pipewire-0` for the native protocol, or the JACK socket path). From the application's perspective, PipeWire IS the JACK server.

The key advantage over the old JACK setup: no more exclusive mode, no more killing PulseAudio to run JACK, no more `pasuspender`. PipeWire serves both JACK and PulseAudio clients simultaneously with no manual intervention.

**Running JACK-aware applications:**

```bash
# JACK apps work transparently via pipewire-jack
# The PIPEWIRE_LATENCY env var sets the buffer size for JACK clients
# Format: frames/samplerate
PIPEWIRE_LATENCY="256/48000" ardour   # ~5ms latency

# Bitwig Studio
PIPEWIRE_LATENCY="128/48000" bitwig-studio

# Reaper
PIPEWIRE_LATENCY="256/48000" reaper

# qjackctl (JACK patchbay GUI) works for visual routing
qjackctl
```

**Carla — plugin host for VST/LV2 routing:**

```bash
sudo pacman -S carla

# Launch Carla with PipeWire JACK backend
carla

# In Carla settings: Engine → Audio Driver → JACK
# Then add VST2/VST3/LV2 plugins as processing nodes
# They appear as PipeWire nodes and can be linked with any other node
```

**qpwgraph — native PipeWire patchbay (better than qjackctl for PW):**

```bash
sudo pacman -S qpwgraph

# qpwgraph shows the full PipeWire graph including non-JACK nodes
# Drag connections between ports to route audio manually
# Save patches (connection sets) to files for recall
```

**Verify JACK compatibility is working:**

```bash
# Check that the JACK server socket is present
ls /run/user/$(id -u)/pipewire-0   # native PW socket

# jack_lsp lists JACK ports (should work via pipewire-jack)
jack_lsp

# Test round-trip latency (requires a loopback)
jack_iodelay
```

---

## 56.9 Screen Recording Audio

PipeWire handles screen recording audio capture through its native API, which portals use to grant per-application capture permissions. wf-recorder (Wayland-native) and OBS both support this natively.

```bash
# wf-recorder: capture screen + audio from default source
wf-recorder --audio -f ~/Videos/recording.mp4

# Specify a particular audio source by node name
wf-recorder --audio=alsa_input.pci-0000_00_1f.3.analog-stereo -f recording.mp4

# Capture with a specific codec and quality
wf-recorder --audio -c libx264 --codec-param crf=18 -f recording.mp4

# List available audio sources to pass to --audio=
pactl list sources short | awk '{print $2}'

# Capture application audio (create a loopback from a sink monitor)
# First find the monitor source for your output
pactl list sources short | grep monitor
# then pass that monitor name to --audio=
```

**OBS Studio with PipeWire:**

```bash
sudo pacman -S obs-studio

# In OBS Sources → Add → Audio Input Capture
# Select "PipeWire Audio Capture" (not ALSA or PulseAudio)
# This uses the xdg-desktop-portal for permission

# For per-application audio capture in OBS:
# Add multiple Audio Input Capture sources, each selecting a different PW node
# This lets you record game audio and Discord audio on separate tracks
```

**Create a virtual loopback for mixing multiple sources:**

```bash
# Create a null sink (virtual mixer bus)
pactl load-module module-null-sink sink_name=virtual_mix \
      sink_properties=device.description=VirtualMix

# Route applications to it
pactl move-sink-input <STREAM_ID> virtual_mix

# Capture the mix in wf-recorder
wf-recorder --audio=virtual_mix.monitor -f recording.mp4
```

For persistent virtual devices, add them to a WirePlumber config instead of loading PulseAudio modules — the `module-null-sink` approach is temporary and lost on restart.

```conf
# ~/.config/pipewire/pipewire.conf.d/20-virtual-sink.conf
context.modules = [
    {
        name = libpipewire-module-null-sink
        args = {
            sink.props = {
                node.name = "virtual_mix"
                node.description = "Virtual Mix Bus"
                audio.channels = 2
                audio.rate = 48000
            }
        }
    }
]
```

---

## 56.10 Troubleshooting Audio

This section covers the most common PipeWire problems and their solutions. For session startup issues see Ch 53. For HDMI audio specifically, see Ch 58.

### No Audio Output

The most common cause is a service that failed to start, or a conflict with PulseAudio still running.

```bash
# Check service status
systemctl --user status pipewire pipewire-pulse wireplumber

# Restart the full stack
systemctl --user restart pipewire pipewire-pulse wireplumber

# Verify PipeWire is serving as the PulseAudio backend
pactl info | grep "Server Name"
# Must show "PulseAudio (on PipeWire ...)" not "PulseAudio"

# Check for PulseAudio process conflict
pgrep -a pulseaudio
# If this shows anything, kill it and disable it:
pkill pulseaudio
systemctl --user disable --now pulseaudio pulseaudio.socket
```

### Finding Your Audio Device

```bash
# List all audio sinks (outputs)
wpctl status
pactl list sinks short

# Verbose sink info including available ports
pactl list sinks | grep -A 5 "Name:\|Active Port:"

# ALSA-level device list (bypasses PipeWire)
aplay -l

# Check if your card is detected by ALSA
cat /proc/asound/cards
```

### Test Audio Playback

```bash
# Basic speaker test (L/R channels)
speaker-test -c 2 -t wav

# Play a system sound via PulseAudio compat
paplay /usr/share/sounds/freedesktop/stereo/bell.oga

# Play via ALSA directly (bypasses PipeWire — useful for isolation testing)
aplay -D default /usr/share/sounds/freedesktop/stereo/bell.oga

# Generate a test tone and pipe to paplay
ffmpeg -f lavfi -i "sine=frequency=440:duration=3" -f wav - | paplay
```

### Xruns and Crackling Audio

Xruns (buffer underruns) cause audible clicks and pops. `pw-top` shows them as spikes in the W/Q column.

```bash
# Monitor xruns in real time
pw-top
# Look for nodes with W/Q > 1.0

# Increase buffer size to reduce xrun risk
cat > ~/.config/pipewire/pipewire.conf.d/99-xrun-fix.conf << 'EOF'
context.properties = {
    default.clock.quantum = 2048
    default.clock.min-quantum = 1024
    default.clock.max-quantum = 4096
}
EOF
systemctl --user restart pipewire

# Check for CPU frequency scaling interfering with audio
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
# If "powersave", switch to performance for audio work:
sudo cpupower frequency-set -g performance
```

### Bluetooth Audio Issues

```bash
# Check Bluetooth service
systemctl status bluetooth

# Verify codec negotiation
journalctl --user -u wireplumber -f
# Look for "Negotiated codec:" lines after connecting a BT device

# Reset Bluetooth adapter if device refuses to connect
bluetoothctl power off
sleep 2
bluetoothctl power on

# Remove and re-pair a device
bluetoothctl remove 00:1A:2B:3C:4D:5E
# Then pair again

# Force A2DP if stuck on HFP
pactl set-card-profile bluez_card.00_1A_2B_3C_4D_5E a2dp_sink
```

### WirePlumber Logs

When PipeWire misbehaves, WirePlumber's logs are the primary diagnostic source:

```bash
# Follow WirePlumber logs in real time
journalctl --user -u wireplumber -f

# PipeWire daemon logs
journalctl --user -u pipewire -f

# Enable debug logging temporarily
WIREPLUMBER_DEBUG=4 wireplumber

# Check for module load failures
journalctl --user -u pipewire -b | grep -i "error\|failed\|warn"
```

### Microphone Not Detected

```bash
# List audio sources
pactl list sources short
wpctl status | grep -A 20 "Sources:"

# Test microphone recording
arecord -d 5 -f cd /tmp/test.wav && aplay /tmp/test.wav

# Via PulseAudio compat
parecord --channels=1 --rate=44100 /tmp/test.wav

# Check mic input level (not muted)
wpctl get-volume @DEFAULT_AUDIO_SOURCE@
wpctl set-mute @DEFAULT_AUDIO_SOURCE@ 0   # unmute

# Alsamixer for hardware gain controls not exposed by PipeWire
alsamixer -c 0    # card 0; use F6 to select card, F4 for capture
```

---

## Quick Reference

| Task | Command |
|---|---|
| List all devices | `wpctl status` |
| Set default output | `wpctl set-default <ID>` |
| Volume up 5% | `wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%+` |
| Mute toggle | `wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle` |
| Live graph view | `pw-top` |
| Visual patchbay | `qpwgraph` |
| Restart audio stack | `systemctl --user restart pipewire pipewire-pulse wireplumber` |
| Check PipeWire active | `pactl info \| grep Server` |
| Record screen+audio | `wf-recorder --audio -f out.mp4` |
| JACK buffer size | `PIPEWIRE_LATENCY="256/48000" <app>` |
| BT codec priority | Edit `~/.config/wireplumber/wireplumber.conf.d/51-bluetooth-policy.conf` |

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
