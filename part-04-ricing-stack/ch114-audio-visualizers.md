# Chapter 114 — Audio Visualizers: cava and glava on Wayland

## Contents

- [Overview](#overview)
- [114.1 cava](#1141-cava)
  - [Installation](#installation)
  - [PipeWire Source Configuration](#pipewire-source-configuration)
  - [Full Configuration](#full-configuration)
  - [Cyberpunk Color Profile](#cyberpunk-color-profile)
  - [Floating Terminal Visualizer](#floating-terminal-visualizer)
  - [Per-Application Visualization (Virtual Sink)](#per-application-visualization-virtual-sink)
  - [Embedding in eww Bar](#embedding-in-eww-bar)
- [114.2 glava](#1142-glava)
  - [Installation](#installation)
  - [PipeWire Source](#pipewire-source)
  - [Module Configuration](#module-configuration)
  - [Cyberpunk Radial Visualizer](#cyberpunk-radial-visualizer)
  - [Session Startup](#session-startup)
- [114.3 Troubleshooting](#1143-troubleshooting)
  - [cava shows flat bars / no audio](#cava-shows-flat-bars-no-audio)
  - [cava bars flicker or have gaps](#cava-bars-flicker-or-have-gaps)
  - [glava crashes with "failed to initialize EGL"](#glava-crashes-with-failed-to-initialize-egl)
  - [glava appears on top of windows instead of behind](#glava-appears-on-top-of-windows-instead-of-behind)

---


## Overview

Audio visualizers translate PipeWire audio data into animated graphics: bar charts dancing in a terminal, waveforms rendered in OpenGL behind your desktop, frequency spectra embedded in a Waybar module. On Wayland, two tools dominate: **cava** (terminal-based, extremely configurable, zero GPU overhead) and **glava** (OpenGL, runs as a desktop background overlay using layer-shell or X11 shaped windows). Both consume audio from PipeWire and both need explicit source configuration on a Wayland-native setup.

**Cross-references:** Ch 56 — PipeWire system setup (audio sources, monitor devices). Ch 26 — bars and panels (embedding cava output in a bar). Ch 92 — compositor shaders (alternative approach to visualizer effects). Ch 59 — desktop widgets (glava placement philosophy).

---

## 114.1 cava

cava (Console-based Audio Visualizer for ALSA, despite the name now working with PipeWire) renders a frequency-spectrum bar chart in the terminal. Its output is pure character art, making it easy to embed anywhere a terminal can appear: a floating terminal on the desktop, a bar module, a tmux pane.

### Installation

```bash
# Arch Linux
sudo pacman -S cava

# Ubuntu 24.04+ (PPA or build from source)
sudo add-apt-repository ppa:nicko64/ppa && sudo apt install cava
# or from source:
sudo apt install libfftw3-dev libpulse-dev libpipewire-0.3-dev libiniparser-dev
git clone https://github.com/karlstav/cava && cd cava
./autogen.sh && ./configure && make && sudo make install
```

### PipeWire Source Configuration

On a pure Wayland / PipeWire setup, cava needs an explicit audio source. The correct PipeWire monitor source for your default sink:

```bash
# Find your PipeWire monitor source name
pactl list sources short | grep monitor
# Typical output:
# 47  alsa_output.pci-0000_00_1f.3.analog-stereo.monitor  ...
```

```ini
# ~/.config/cava/config — PipeWire source
[input]
method = pipewire
source = auto   # auto detects the default sink monitor
# or explicitly:
# source = alsa_output.pci-0000_00_1f.3.analog-stereo.monitor
```

`source = auto` uses the monitor of the default PipeWire sink — this is what you want for a "visualize whatever is playing" setup. If you want to visualize a specific application's audio, use a virtual sink (see §114.1.4).

### Full Configuration

```ini
# ~/.config/cava/config

[general]
bars = 0               # 0 = auto (fills terminal width)
bar_width = 2
bar_spacing = 1
framerate = 60
sensitivity = 100      # 0–200; higher = reacts to quieter audio
lower_cutoff_freq = 50
higher_cutoff_freq = 10000
noise_reduction = 0.77 # 0.0 = no smoothing, 1.0 = max smoothing

[input]
method = pipewire
source = auto

[output]
method = ncurses       # ncurses (default) | noncurses | raw | wav | oss
channels = stereo      # stereo | mono

[color]
# Tokyo Night palette
gradient = 1
gradient_count = 8
gradient_color_1 = '#7aa2f7'   # blue (low frequencies)
gradient_color_2 = '#bb9af7'   # purple
gradient_color_3 = '#7dcfff'   # cyan
gradient_color_4 = '#9ece6a'   # green
gradient_color_5 = '#e0af68'   # yellow
gradient_color_6 = '#ff9e64'   # orange
gradient_color_7 = '#f7768e'   # red
gradient_color_8 = '#f7768e'   # red (high frequencies)
background = '#1a1b26'

[smoothing]
monstercat = 1         # monstercat-style smoothing (popular)
waves = 0
gravity = 100

[eq]
; Per-bar equalizer — 25 channels max
; Boost bass (bars 1-3) and treble (bars 23-25)
1 = 0.8
2 = 0.9
3 = 1.0
; middle bars default to 1.0
23 = 1.0
24 = 0.9
25 = 0.8
```

### Cyberpunk Color Profile

```ini
[color]
gradient = 1
gradient_count = 4
gradient_color_1 = '#00ffff'   # cyan (bass)
gradient_color_2 = '#00aaff'   # blue
gradient_color_3 = '#ff00ff'   # magenta
gradient_color_4 = '#ff003c'   # red (treble)
background = '#0a0a0f'
```

### Floating Terminal Visualizer

The most common rice placement: a transparent terminal running cava, positioned as a floating window in the lower portion of the screen.

```ini
# Hyprland window rule for the cava terminal
windowrulev2 = float,           class:^(kitty-cava)$
windowrulev2 = size 800 200,    class:^(kitty-cava)$
windowrulev2 = move 560 860,    class:^(kitty-cava)$
windowrulev2 = pin,             class:^(kitty-cava)$
windowrulev2 = nofocus,         class:^(kitty-cava)$
windowrulev2 = noborder,        class:^(kitty-cava)$
```

```ini
# Launch command
exec-once = kitty --class kitty-cava --override background_opacity=0.0 \
            --override font_size=8 cava
```

With `background_opacity=0.0` in Kitty and cava's `background` color set to `''` (empty), the visualizer bars float directly over the wallpaper.

### Per-Application Visualization (Virtual Sink)

To visualize only one application's audio (e.g., Spotify), route it through a virtual null sink and point cava at that sink's monitor:

```bash
# Create a virtual sink
pactl load-module module-null-sink sink_name=viz_sink \
    sink_properties=device.description=VisualizerSink

# Get the monitor source name
pactl list sources short | grep viz_sink
# → viz_sink.monitor

# Move Spotify to the virtual sink
pactl list sink-inputs short   # find Spotify's stream ID
pactl move-sink-input 42 viz_sink

# Point cava at the monitor
# In ~/.config/cava/config:
# source = viz_sink.monitor
```

### Embedding in eww Bar

```yuck
(deflisten cava-bars
  :initial "░░░░░░░░░░░░░░░░"
  `cava -p ~/.config/cava/config-eww 2>/dev/null | while read -r line; do
     echo "\"$line\""
   done`)

(defwidget cava-widget []
  (label :class "cava" :text cava-bars))
```

```ini
# ~/.config/cava/config-eww — raw output mode for eww
[output]
method = raw
raw_target = /dev/stdout
bit_format = 8bit
bars = 16

[color]
; No color in raw mode — eww's CSS handles it
```

```scss
/* eww.scss */
.cava {
  font-family: monospace;
  color: #7aa2f7;
  letter-spacing: 2px;
}
```

---

## 114.2 glava

glava renders audio visualizations using OpenGL, running as a borderless window that appears behind other windows (using `_NET_WM_WINDOW_TYPE_DESKTOP` on X11 or layer-shell on Wayland). Supported modules: bars, radial, graph, wave, circle.

### Installation

```bash
# Arch AUR
yay -S glava

# From source (Wayland layer-shell build)
sudo pacman -S meson glslang libpulse libxext glfw-wayland
git clone https://github.com/jarcode-foss/glava
cd glava
meson setup build --buildtype=release -Dforce_push_streams=true
ninja -C build
sudo ninja -C build install
```

### PipeWire Source

glava uses PulseAudio API (libpulse) which WirePlumber bridges. The source is configured in the glava config:

```glsl
// ~/.config/glava/audio.glsl
#request audio "alsa_output.pci-0000_00_1f.3.analog-stereo.monitor"
// or use the default monitor:
#request audio "@DEFAULT_MONITOR@"
```

### Module Configuration

glava's config system uses GLSL `#request` directives embedded in shader files:

```glsl
// ~/.config/glava/rc.glsl — main config

// Module selection
#request mod bars         // bars | radial | graph | wave | circle

// Window settings (for Wayland layer-shell)
#request setenv GLAVA_FORCE_LAYER_SHELL 1
#request layer background   // background | overlay
#request monitor 0
#request geometry 0 0 1920 200   // x y width height

// Bars module config
#request bars 64          // number of bars
#request fwidth 0.8       // bar width fraction (0.0-1.0)
#request fcap 0.05        // cap height fraction
#request capmode 2        // 0=none 1=flat 2=physics
#request gravity 2.5

// Colors — Tokyo Night
#request color_base_r 0.10  // bar base color
#request color_base_g 0.11
#request color_base_b 0.15

#request color_intensity_r 0.478  // top of bar: #7aa2f7 blue
#request color_intensity_g 0.635
#request color_intensity_b 0.969
```

### Cyberpunk Radial Visualizer

```glsl
// ~/.config/glava/rc.glsl — cyberpunk radial

#request mod radial
#request setenv GLAVA_FORCE_LAYER_SHELL 1
#request layer background
#request geometry 760 440 400 400   // centered on a 1920x1080 screen

#request inner_rad 0.5     // inner radius (0.0-1.0)
#request bar_width 1.5
#request rotate_speed 0.0

// Cyan → magenta gradient based on intensity
#request color_base_r 0.0
#request color_base_g 1.0
#request color_base_b 1.0    // cyan

#request color_intensity_r 1.0
#request color_intensity_g 0.0
#request color_intensity_b 1.0    // magenta at peaks
```

### Session Startup

```bash
# Start glava on compositor launch (Hyprland)
# ~/.config/hypr/hyprland.conf
exec-once = glava --desktop

# Reload config without restart
pkill glava && glava --desktop &
```

The `--desktop` flag tells glava to position itself on the desktop layer (behind all other windows).

---

## 114.3 Troubleshooting

### cava shows flat bars / no audio

```bash
# Verify PipeWire is running and audio is playing
pactl info
pw-top   # live PipeWire node view

# Check cava can see the source
cava -p /dev/null   # should show a "no input" message, not crash
```

### cava bars flicker or have gaps

Lower `framerate` to match your monitor's refresh rate, or enable `monstercat = 1` smoothing. On slow terminals, reduce bar count.

### glava crashes with "failed to initialize EGL"

Wayland EGL requires the correct platform:
```bash
EGL_PLATFORM=wayland glava --desktop
# or add to glava's config:
# #request setenv EGL_PLATFORM wayland
```

### glava appears on top of windows instead of behind

The `background` layer may not be supported by all compositors. Try `overlay` layer and use the compositor's window rules to keep it behind:
```ini
# Hyprland
windowrulev2 = nofocus, class:^(glava)$
windowrulev2 = pin, class:^(glava)$
```
