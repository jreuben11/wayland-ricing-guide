# Chapter 56 — PipeWire System Setup: WirePlumber, EasyEffects, Audio Routing

## Overview
PipeWire is the universal audio/video server that replaced PulseAudio and JACK on
modern Linux. Ch 21 covers the Quickshell API. This chapter covers installing,
configuring, and mastering PipeWire as a system.

## Sections

### 56.1 PipeWire Architecture
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
- **pipewire-pulse**: PulseAudio compatibility layer
- **pipewire-jack**: JACK compatibility layer (for pro audio)
- **pipewire-alsa**: ALSA compatibility

### 56.2 Installation

**Arch:**
```bash
sudo pacman -S pipewire pipewire-alsa pipewire-pulse pipewire-jack wireplumber
# Enable (usually auto-started via systemd user session)
systemctl --user enable --now pipewire pipewire-pulse wireplumber
```

**Verify:**
```bash
pactl info | grep "Server Name"  # should show PipeWire
pw-top                           # live graph view
```

**NixOS:**
```nix
hardware.pulseaudio.enable = false;
services.pipewire = {
    enable = true;
    alsa.enable = true;
    alsa.support32Bit = true;  # for 32-bit games (Wine/Steam)
    pulse.enable = true;
    jack.enable = true;        # optional: for pro audio
};
```

### 56.3 WirePlumber Configuration

WirePlumber rules live in `~/.config/wireplumber/`:
```lua
-- ~/.config/wireplumber/wireplumber.conf.d/51-disable-camera.conf
-- Disable a specific device
rule = {
    matches = { { { "node.name", "=", "v4l2_input.pci-..." } } },
    apply_properties = { ["node.disabled"] = true }
}
```

**Common WirePlumber tasks:**
- Set default sink/source: `wpctl set-default <ID>`
- Volume control: `wpctl set-volume @DEFAULT_AUDIO_SINK@ 50%`
- Mute: `wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle`
- List devices: `wpctl status`

### 56.4 pw-top — Live Audio Graph Monitor
```bash
pw-top         # like htop but for audio nodes
pw-cli list-objects
pactl list sinks   # PulseAudio compat
pactl list sources
```

### 56.5 Audio Quality Configuration

**High-quality resampling:**
```conf
# ~/.config/pipewire/pipewire.conf.d/10-quality.conf
context.properties = {
    default.clock.rate = 48000
    default.clock.quantum = 1024
    default.clock.min-quantum = 32
    resample.quality = 15      # 0-15, higher = better quality
}
```

**Low latency (pro audio):**
```conf
context.properties = {
    default.clock.rate = 48000
    default.clock.quantum = 64
    default.clock.min-quantum = 32
    default.clock.max-quantum = 64
}
```

### 56.6 EasyEffects — System-Wide Audio EQ and Effects
```bash
sudo pacman -S easyeffects  # or flatpak install easyeffects
```

- System-wide EQ, compressor, limiter, reverb on any sink/source
- Presets: community presets for popular headphones on GitHub
- Auto-start: `EasyEffects --gapplication-service` in exec-once
- Headphone EQ: AutoEQ project presets for hundreds of headphones

**Headphone EQ setup (AutoEQ):**
```bash
# Download preset for your headphones from AutoEQ GitHub
# Import in EasyEffects → Equalizer → Import Preset
```

### 56.7 Bluetooth Audio
```bash
sudo pacman -S bluez bluez-utils blueman
sudo systemctl enable --now bluetooth
```

**High-quality Bluetooth codecs:**
```bash
sudo pacman -S libspa-bluetooth  # codecs (AAC, aptX, LDAC)
# or: pipewire-bluetooth (newer name)
```

**Codec configuration:**
```conf
# ~/.config/wireplumber/wireplumber.conf.d/51-bluetooth-policy.conf
bluetooth.policy = {
    roles = [ a2dp_sink a2dp_source ]
    codecs = [ aac ldac aptx ]
}
```

**Headset profile switching:**
```bash
# Switch between A2DP (music) and HFP (calls with mic)
pactl set-card-profile bluez_card.XX_XX_XX_XX_XX_XX a2dp_sink
pactl set-card-profile bluez_card.XX_XX_XX_XX_XX_XX handsfree_head_unit
```

### 56.8 JACK Applications and Pro Audio
```bash
# JACK apps work transparently via pipewire-jack
# For DAWs: Ardour, Bitwig, Reaper
PIPEWIRE_LATENCY=256/48000 ardour
```

**Carla — plugin host:**
```bash
sudo pacman -S carla
# Use as JACK host for VST/LV2 plugins
```

### 56.9 Screen Recording Audio
```bash
# wf-recorder with audio
wf-recorder --audio -f recording.mp4

# Specify audio device
wf-recorder --audio=alsa_input.pci-... -f recording.mp4

# OBS: use PipeWire source, select application audio
```

### 56.10 Troubleshooting Audio
```bash
# No audio
systemctl --user restart pipewire pipewire-pulse wireplumber

# Check PipeWire is running
systemctl --user status pipewire

# Find your audio device
wpctl status
pactl list sinks short

# Test audio
speaker-test -c 2 -t wav
paplay /usr/share/sounds/freedesktop/stereo/bell.oga
```
