# Chapter 121 — Bluetooth Audio Codec Negotiation on PipeWire

## Overview

PipeWire supports Bluetooth audio with AAC, aptX, aptX HD, aptX-LL, aptX-Adaptive, LDAC, and LC3 codecs beyond the standard SBC — but they are not enabled by default, and codec selection requires explicit configuration of both BlueZ and PipeWire's bluetooth module. This chapter covers enabling high-quality codecs, verifying which codec is active, forcing a specific codec, configuring the HSP/HFP microphone profile for calls, and troubleshooting negotiation failures.

**Cross-references:** Ch 56 — PipeWire and WirePlumber system setup. Ch 81 — Bluetooth device management (bluetoothctl, blueman).

---

## 121.1 Codec Overview

| Codec | Quality | Latency | License | Needs |
|---|---|---|---|---|
| SBC | Low (328 kbps max) | Medium | Free | Default |
| SBC-XQ | Medium (improved params) | Medium | Free | bluez-monitor config |
| AAC | Good (256 kbps) | Medium | Patent | pipewire-codec-aptx |
| aptX | Good (352 kbps) | Low | Patent | pipewire-codec-aptx |
| aptX HD | High (576 kbps) | Medium | Patent | pipewire-codec-aptx |
| aptX-LL | Good (352 kbps) | Very low | Patent | pipewire-codec-aptx |
| aptX-Adaptive | Excellent (variable) | Low | Patent | pipewire-codec-aptx |
| LDAC | Excellent (990 kbps) | High | Patent/Free | libldac |
| LC3 | Excellent (LE Audio) | Very low | Patent | bluez 5.65+ |

The patent-encumbered codecs (aptX, LDAC) are available on Linux via the `pipewire-codec-aptx` package (which uses the open-source `fdk-aac` and `openaptx` libraries) and `libldac` (Sony's open-sourced LDAC encoder).

---

## 121.2 Installation

```bash
# Arch Linux — all Bluetooth codecs
sudo pacman -S pipewire-codec-aptx libldac

# Ubuntu 24.04+ — libldac (aptX requires manual build)
sudo apt install libldac-dev

# Verify pipewire has the codec plugins
ls /usr/lib/spa-0.2/bluez5/libspa-codec-bluez5-*.so
# Should show: aac, aptx, aptx-hd, aptx-ll, aptx-adaptive, ldac, lc3
```

After installing, restart PipeWire and WirePlumber:
```bash
systemctl --user restart pipewire pipewire-pulse wireplumber
```

---

## 121.3 BlueZ Configuration

BlueZ must be configured to enable codec negotiation and offer the extra codecs to devices:

```ini
# /etc/bluetooth/main.conf

[Policy]
AutoEnable=true
ReconnectAttempts=7
ReconnectIntervals=1,2,4,8,16,32,64

[General]
# Enable experimental features for LDAC and aptX-Adaptive
Experimental=true
KernelExperimental=true

# Enable LE Audio (for LC3 codec, requires BlueZ 5.65+)
# LeAutoEnable=true
```

```bash
sudo systemctl restart bluetooth
```

---

## 121.4 PipeWire Bluez5 Module Configuration

```lua
# ~/.config/wireplumber/wireplumber.conf.d/51-bluez-codecs.conf

monitor.bluez.properties = {
  # Enable all available codecs
  bluez5.codecs = [ sbc sbc_xq aac ldac aptx aptx_hd aptx_ll aptx_ll_duplex aptx_adaptive ]

  # Codec preference order (first = highest priority during negotiation)
  bluez5.codecs.prefer = [ ldac aptx_hd aptx aac sbc_xq sbc ]

  # LDAC quality setting: 0=auto, 1=low, 2=mid, 3=high
  bluez5.ldac.quality = 3

  # SBC-XQ bitpool (max=64 for enhanced quality)
  bluez5.sbc-xq.bitpool = 53

  # Enable A2DP duplex (simultaneous audio + microphone)
  bluez5.a2dp.ldac.hq = true

  # Role: allow both HSP and A2DP profiles
  bluez5.hfphsp-backend = native

  # Auto-select A2DP sink for media (not HFP)
  bluez5.autoswitch-profile = false
}
```

---

## 121.5 Verifying the Active Codec

```bash
# Check active codec for a connected Bluetooth device
pactl list cards | grep -A20 "bluez_card"

# More detail via pw-dump
pw-dump | jq '
  .[] |
  select(.info.props["api.bluez5.address"] != null) |
  {
    name:  .info.props["api.bluez5.alias"],
    codec: .info.props["api.bluez5.a2dp-codec"],
    profile: .info.props["api.bluez5.profile"]
  }'

# Or watch codec negotiation in real time
journalctl --user -u wireplumber -f | grep -i "codec\|LDAC\|aptX"
```

Example output showing LDAC active:
```
api.bluez5.a2dp-codec: "ldac"
api.bluez5.codec.ldac.quality: "3"
```

---

## 121.6 Forcing a Specific Codec

If automatic negotiation selects a lower-quality codec (e.g., because the device advertised aptX but LDAC negotiation failed), force the codec via pactl:

```bash
# List available codec switching options for a card
pactl list cards | grep -A5 "bluez_card"
# Look for "Attributes:" lines listing codecs

# Force LDAC via pactl card profile (device-dependent)
pactl set-card-profile bluez_card.XX_XX_XX_XX_XX_XX \
    a2dp-sink-ldac

# Force aptX HD
pactl set-card-profile bluez_card.XX_XX_XX_XX_XX_XX \
    a2dp-sink-aptx_hd

# Force SBC-XQ (better than SBC, more compatible)
pactl set-card-profile bluez_card.XX_XX_XX_XX_XX_XX \
    a2dp-sink-sbc_xq
```

For automation, switch codec via a script triggered by device connection:

```bash
#!/bin/bash
# ~/.local/bin/bt-set-codec
# Usage: bt-set-codec MAC CODEC
# e.g.: bt-set-codec AA:BB:CC:DD:EE:FF ldac

MAC="${1//:/_}"
CODEC="$2"
CARD="bluez_card.$MAC"
PROFILE="a2dp-sink-$CODEC"

pactl set-card-profile "$CARD" "$PROFILE" && \
    echo "Set $CARD → $PROFILE" || \
    echo "Failed — available profiles:" && \
    pactl list cards | grep -A2 "$CARD" | grep Profile
```

---

## 121.7 HSP/HFP: Microphone Profile for Calls

A2DP (high-quality stereo) and HFP (headset with microphone) are mutually exclusive profiles on most devices. Switching to HFP drops audio quality to ~8 kHz (SCO) but enables the microphone. WirePlumber autoswitch handles this:

```lua
# ~/.config/wireplumber/wireplumber.conf.d/52-hfp-autoswitch.conf
monitor.bluez.properties = {
  # Automatically switch to HFP when an app opens a microphone stream
  bluez5.autoswitch-profile = true
}
```

With `autoswitch-profile = true`, WirePlumber switches to the HFP profile when a video call app (Zoom, Teams, browser) opens a capture stream, then switches back to A2DP when the capture stream closes.

### mSBC / LC3-SWB for Better Call Quality

mSBC improves HFP audio to ~16 kHz wideband. LC3-SWB (via LE Audio) reaches 32 kHz. Enable in BlueZ:

```ini
# /etc/bluetooth/main.conf
[General]
Experimental=true   # required for mSBC
```

```lua
# wireplumber.conf.d
monitor.bluez.properties = {
  bluez5.hfphsp-backend = native
  # mSBC enabled automatically when both sides support it and Experimental=true
}
```

Verify mSBC is active during a call:
```bash
journalctl --user -u wireplumber | grep -i "msbc\|hfp"
```

---

## 121.8 Troubleshooting

### Device connects but only SBC is used despite LDAC support

1. Verify `libldac` and `pipewire-codec-aptx` are installed
2. Verify BlueZ `Experimental=true` in `main.conf`
3. Restart bluetooth + wireplumber + pipewire after config changes
4. Check if the device actually supports LDAC (some devices advertise it but require specific firmware)

```bash
# Check device capabilities via bluetoothctl
bluetoothctl info AA:BB:CC:DD:EE:FF | grep -i "LDAC\|aptX\|AAC"
```

### Audio dropout or crackling on LDAC

LDAC at quality 3 (990 kbps) requires a stable Bluetooth 5.0 connection. Reduce quality:

```lua
bluez5.ldac.quality = 2   # drop to mid quality (660 kbps)
```

Or switch to aptX HD (576 kbps, lower latency, more stable).

### HFP microphone not working

```bash
# Manually switch to HFP profile
pactl set-card-profile bluez_card.XX_XX_XX_XX_XX_XX headset-head-unit

# Check if the HFP source appears
pactl list sources | grep -i bluetooth
```

### WirePlumber not loading codec config

```bash
# Verify the conf file syntax (must be valid CONF not JSON)
wpexec --no-daemon ~/.config/wireplumber/wireplumber.conf.d/51-bluez-codecs.conf
# or just restart with debug logging:
WIREPLUMBER_DEBUG=4 wireplumber 2>&1 | grep bluez
```
