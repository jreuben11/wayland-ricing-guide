# Chapter 27 — Wallpaper Management: swww, hyprpaper, swaybg, mpvpaper

## Overview

Wallpaper tools on Wayland use the `wlr-layer-shell` protocol to place images and video on the
`BACKGROUND` layer — a dedicated compositing layer that sits beneath all windows but above the
raw display plane. Unlike X11 where setting the root window pixmap was a single `xsetroot` or
`feh --bg-fill` call, Wayland requires a dedicated client process that holds a layer-shell surface
open for the lifetime of the wallpaper. This architectural difference means your wallpaper daemon
is a long-running process, and changing wallpapers requires either IPC messaging or process restart.

Each tool covered in this chapter makes different trade-offs: swww excels at animated transitions
and real-time IPC; hyprpaper integrates tightly with Hyprland's own socket for seamless preloading;
swaybg is minimal and universally compatible; wpaperd automates timed cycling; mpvpaper renders
live video or animated formats. Quickshell enables shader-based and fully procedural wallpapers
in QML. Understanding these differences lets you choose the right tool for your rice and compose
them with your color-scheme pipeline.

All tools discussed here require a compositor that implements `wlr-layer-shell-unstable-v1`.
This includes Hyprland, Sway, River, Wayfire, labwc, and most wlroots-based compositors. GNOME
and KDE Plasma use their own layer-shell extensions and are not compatible with these tools.

See **Ch 08** for compositor fundamentals and protocol details, **Ch 53** for session startup
ordering, and **Ch 38** for pywal/matugen color scheme pipelines that feed into wallpaper scripts.

---

## 27.1 swww — The Transition King

swww (Simple Wayland Wallpaper) is the most feature-rich wallpaper daemon available for
wlroots-based compositors. Its headline feature is GPU-accelerated animated transitions: a
background `swww-daemon` process receives `swww img` commands over a Unix socket and renders
the transition frame-by-frame using wgpu. The result is buttery crossfades, directional wipes,
circular grows, and wave-form reveals — all composited at full refresh rate.

The architecture separates the daemon from the client binary. `swww-daemon` must be started
once at login and left running. All subsequent `swww img` calls are lightweight IPC messages.
The daemon caches the current wallpaper in shared memory, so display reconnects (e.g. plugging
in a monitor after login) restore the wallpaper automatically without re-sending the image.

swww tracks per-output state, meaning each monitor can hold a different wallpaper at any time.
You address outputs by their Wayland output name (e.g. `DP-1`, `HDMI-A-1`, `eDP-1`) using the
`--outputs` flag. Omitting the flag applies the change to all outputs simultaneously.

**Installation:**

```bash
# Arch Linux (AUR)
paru -S swww

# Build from source (requires Rust toolchain)
git clone https://github.com/LGFae/swww
cd swww
cargo build --release
install -Dm755 target/release/swww /usr/local/bin/swww
install -Dm755 target/release/swww-daemon /usr/local/bin/swww-daemon
```

**Starting the daemon (add to Hyprland config or session startup):**

```ini
# ~/.config/hypr/hyprland.conf
exec-once = swww-daemon --no-cache
```

```bash
# Or in a shell startup script
swww-daemon &
# Wait for the socket to appear before sending commands
swww img ~/Pictures/wallpapers/mountain.jpg
```

**Basic usage and transition parameters:**

```bash
# Simple set with defaults
swww img ~/Pictures/wallpapers/forest.jpg

# Crossfade over 1.5 seconds at 60 fps on all outputs
swww img ~/Pictures/wallpapers/forest.jpg \
    --transition-type fade \
    --transition-duration 1.5 \
    --transition-fps 60

# Directional wipe from the left
swww img ~/Pictures/wallpapers/city.jpg \
    --transition-type wipe \
    --transition-angle 0 \
    --transition-duration 1.0

# Circular grow from cursor position
swww img ~/Pictures/wallpapers/abstract.png \
    --transition-type grow \
    --transition-pos "cursor" \
    --transition-duration 0.8

# Wave transition with custom bezier easing
swww img ~/Pictures/wallpapers/gradient.jpg \
    --transition-type wave \
    --transition-wave "20,10" \
    --transition-bezier ".43,1.19,1,.4" \
    --transition-duration 1.2

# Target a specific output only
swww img ~/Pictures/wallpapers/secondary.jpg --outputs DP-2
```

**Resize and filter modes:**

| Mode       | Description                                   |
|------------|-----------------------------------------------|
| `crop`     | Fill the output, center-cropping excess        |
| `fit`      | Letterbox/pillarbox to fit without cropping    |
| `no`       | Display at original pixel size, centered       |

| Filter     | Quality vs. Speed trade-off                   |
|------------|-----------------------------------------------|
| `Lanczos`  | Best quality, slowest (default)               |
| `CatmullRom` | High quality, good performance              |
| `Mitchell` | Balanced sharpness/smoothness                 |
| `Bilinear` | Fast, acceptable quality                      |
| `Nearest`  | Pixel-perfect for pixel art                   |

```bash
# Pixel-art wallpaper — no filtering
swww img ~/Pictures/pixel-art.png \
    --resize no \
    --filter Nearest

# Photography — best quality crop
swww img ~/Pictures/landscape.jpg \
    --resize crop \
    --filter Lanczos
```

**Querying current state:**

```bash
# Print current wallpaper path and resolution per output
swww query
# Example output:
# DP-1: image: /home/user/Pictures/forest.jpg, 3840x2160
# eDP-1: image: /home/user/Pictures/city.jpg, 1920x1080
```

---

## 27.2 hyprpaper — Hyprland-Native

hyprpaper is the official wallpaper utility for Hyprland. Rather than running its own IPC socket,
it communicates through Hyprland's hyprctl socket using the `hyprpaper` keyword namespace. This
tight integration means hyprpaper starts with Hyprland's plugin system and requires no separate
socket management in your scripts.

The key performance feature is preloading: you declare wallpapers in the config with `preload`,
causing hyprpaper to load the decoded image into GPU memory at startup. Wallpaper changes then
become near-instantaneous sub-millisecond operations because no disk read or GPU upload is needed.
This makes hyprpaper ideal for rapid wallpaper cycling scripts that must feel snappy.

hyprpaper intentionally omits transition animations. The reasoning is that Hyprland's own
animation system (workspace switching, window opening) provides context transitions, and a
separate wallpaper fade creates visual interference. If you want crossfades on wallpaper changes
you should use swww instead.

**Installation:**

```bash
# Arch Linux
sudo pacman -S hyprpaper

# Build from source
git clone https://github.com/hyprwm/hyprpaper
cd hyprpaper
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
sudo cmake --install build
```

**Configuration file (`~/.config/hypr/hyprpaper.conf`):**

```ini
# Preload images into GPU memory at startup
preload = /home/user/Pictures/wallpapers/mountain.jpg
preload = /home/user/Pictures/wallpapers/forest.jpg
preload = /home/user/Pictures/wallpapers/abstract.png

# Assign wallpapers to outputs (use output name from `hyprctl monitors`)
wallpaper = DP-1,/home/user/Pictures/wallpapers/mountain.jpg
wallpaper = eDP-1,/home/user/Pictures/wallpapers/forest.jpg

# Wildcard assigns to all outputs not explicitly listed
wallpaper = ,/home/user/Pictures/wallpapers/abstract.png

# Disable splash text overlay (default: false)
splash = false

# IPC listening (required for runtime changes)
ipc = on
```

**Starting hyprpaper from Hyprland config:**

```ini
# ~/.config/hypr/hyprland.conf
exec-once = hyprpaper
```

**Runtime wallpaper changes via hyprctl:**

```bash
# Preload a new image at runtime
hyprctl hyprpaper preload "/home/user/Pictures/wallpapers/night.jpg"

# Set it on a specific output
hyprctl hyprpaper wallpaper "DP-1,/home/user/Pictures/wallpapers/night.jpg"

# Set on all outputs
hyprctl hyprpaper wallpaper ",/home/user/Pictures/wallpapers/night.jpg"

# List currently loaded wallpapers
hyprctl hyprpaper listloaded

# Unload a preloaded image to free GPU memory
hyprctl hyprpaper unload "/home/user/Pictures/wallpapers/old.jpg"

# Unload all images not currently displayed
hyprctl hyprpaper unload all
```

**Scripted wallpaper rotation with hyprpaper:**

```bash
#!/usr/bin/env bash
# ~/.local/bin/hypr-wallpaper-cycle.sh
# Cycle through wallpapers in a directory every N minutes
WALLPAPER_DIR="$HOME/Pictures/wallpapers"
INTERVAL=1800  # seconds

while true; do
    WALL=$(find "$WALLPAPER_DIR" -type f \( -name "*.jpg" -o -name "*.png" -o -name "*.webp" \) | shuf -n1)
    hyprctl hyprpaper preload "$WALL"
    hyprctl hyprpaper wallpaper ",$WALL"
    sleep "$INTERVAL"
    hyprctl hyprpaper unload all
done
```

---

## 27.3 swaybg — Simple and Reliable

swaybg is the reference wallpaper implementation for Sway and the broader wlroots ecosystem. It
implements only the `wlr-layer-shell` and `xdg-output` protocols, making it the most portable
and universally compatible option. It has no daemon mode, no IPC, and no transitions — it simply
renders a static image and holds the surface open. To change the wallpaper, you kill the swaybg
process and start a new one.

Despite its simplicity, swaybg is the correct tool for stable setups where wallpaper changes are
infrequent and you want zero overhead. Sway's default configuration uses it, and it is the only
wallpaper tool that ships in Sway's official package. It also serves as a reliable fallback when
other daemons are misbehaving during debugging.

swaybg is also useful as a solid-color background for setups that use transparent or frosted-glass
effects — setting a color background with `-c` instead of an image gives the blur something to
composite against.

**Installation:**

```bash
# Arch Linux
sudo pacman -S swaybg

# Fedora
sudo dnf install swaybg

# Build from source
git clone https://github.com/swaywm/swaybg
cd swaybg
meson setup build
ninja -C build
sudo ninja -C build install
```

**Usage:**

```bash
# Fill output with image (crop to fill)
swaybg -i ~/Pictures/wallpapers/landscape.jpg -m fill

# Fit image (letterbox)
swaybg -i ~/Pictures/wallpapers/portrait.png -m fit

# Tile a texture
swaybg -i ~/Pictures/textures/noise.png -m tile

# Center image on solid black background
swaybg -i ~/Pictures/wallpapers/logo.png -m center

# Stretch image to output resolution (ignores aspect ratio)
swaybg -i ~/Pictures/wallpapers/photo.jpg -m stretch

# Solid color background (no image)
swaybg -c "#1e1e2e"

# Per-output with different images
swaybg -o DP-1 -i ~/Pictures/wallpapers/left.jpg -m fill \
       -o eDP-1 -i ~/Pictures/wallpapers/right.jpg -m fill
```

**Display modes reference:**

| Mode      | Behavior                                              |
|-----------|-------------------------------------------------------|
| `fill`    | Scale to fill; crop edges if aspect ratio differs     |
| `fit`     | Scale to fit; leave bars if aspect ratio differs      |
| `stretch` | Distort to exactly fill output dimensions             |
| `center`  | Original size, centered; solid color in margins       |
| `tile`    | Repeat image to fill output                           |

**Sway config integration:**

```ini
# ~/.config/sway/config
output * bg ~/Pictures/wallpapers/default.jpg fill
output DP-1 bg ~/Pictures/wallpapers/4k.jpg fill
output HDMI-A-1 bg "#282a36" solid_color
```

**Scripted wallpaper change (kill + restart pattern):**

```bash
#!/usr/bin/env bash
# ~/.local/bin/swaybg-set.sh
WALL="$1"
pkill swaybg
swaybg -i "$WALL" -m fill &
disown
```

---

## 27.4 wpaperd — Timed Wallpaper Cycling

wpaperd (Wallpaper Daemon) fills the niche between swaybg's static approach and the fully
scripted flexibility of swww. Its primary feature is time-based automatic wallpaper cycling:
you configure a directory or list of images per output, set a `duration`, and wpaperd handles
the rotation without any external cron jobs or shell scripts.

The configuration uses a TOML file per output section. Each section can specify a directory
(wpaperd picks randomly from all images in it) or an explicit list. The `sorting` field
controls whether the rotation is random or alphabetical. `apply-shadow` adds a subtle drop
shadow to the image edges for a depth effect.

wpaperd also exposes a D-Bus-adjacent IPC through `wpaperctl`, letting you trigger manual
advances, go to the previous wallpaper, or query the current wallpaper path from scripts.

**Installation:**

```bash
# Arch Linux (AUR)
paru -S wpaperd

# Build from source
git clone https://github.com/danyspin97/wpaperd
cd wpaperd
cargo build --release
install -Dm755 target/release/wpaperd /usr/local/bin/wpaperd
install -Dm755 target/release/wpaperctl /usr/local/bin/wpaperctl
```

**Configuration (`~/.config/wpaperd/wallpaper.toml`):**

```toml
[any]
# Applies to all outputs not otherwise specified
path = "/home/user/Pictures/wallpapers"
duration = "30m"
sorting = "random"
mode = "center"

[DP-1]
path = "/home/user/Pictures/wallpapers/ultrawide"
duration = "1h"
sorting = "alphabetical"
mode = "fill"
apply-shadow = false

[eDP-1]
path = "/home/user/Pictures/wallpapers/laptop"
duration = "15m"
sorting = "random"
mode = "fit"
```

**Duration format examples:**

| Value    | Meaning          |
|----------|------------------|
| `"30s"`  | 30 seconds       |
| `"5m"`   | 5 minutes        |
| `"2h"`   | 2 hours          |
| `"1d"`   | 1 day            |

**wpaperctl commands:**

```bash
# Advance to next wallpaper immediately
wpaperctl next DP-1

# Go back to previous wallpaper
wpaperctl previous eDP-1

# Print current wallpaper path
wpaperctl current DP-1

# Pause/resume cycling
wpaperctl pause
wpaperctl resume
```

**Starting wpaperd at session startup:**

```ini
# ~/.config/hypr/hyprland.conf
exec-once = wpaperd
```

---

## 27.5 mpvpaper — Video Wallpapers

mpvpaper renders any video or animated format that mpv supports as a live wallpaper on a
layer-shell surface. This includes MP4, WebM, MKV, GIF, and anything else mpv can decode.
The wallpaper is rendered at full GPU compositing speed, with mpv's full shader and post-processing
pipeline available for upscaling, color correction, and custom GLSL shaders.

Performance impact is the primary consideration. A 1080p video at 30 fps adds roughly 8-15%
GPU load on modern discrete GPUs; 4K video or 60 fps on an iGPU can make the system feel sluggish.
Use `--mpv-options "vo=dmabuf-wayland"` to minimize copy overhead by sharing DMA buffers directly
with the compositor. Disable audio with `no-audio` unless you explicitly want ambient sound.

The `--fork` flag detaches mpvpaper from the terminal, and `--auto-stop` / `--auto-pause` suspend
playback when all outputs are covered by opaque windows to save power.

**Installation:**

```bash
# Arch Linux (AUR)
paru -S mpvpaper

# Build from source (requires mpv development headers)
git clone https://github.com/GhostNaN/mpvpaper
cd mpvpaper
meson setup build
ninja -C build
sudo ninja -C build install
```

**Basic usage:**

```bash
# Looping video wallpaper, no audio
mpvpaper -o "no-audio loop" DP-1 ~/Videos/wallpapers/looping-scene.mp4

# All outputs
mpvpaper -o "no-audio loop" '*' ~/Videos/wallpapers/looping-scene.mp4

# GIF wallpaper
mpvpaper -o "loop" eDP-1 ~/Pictures/animated/ripple.gif

# Fork to background, pause when windows cover the screen
mpvpaper --fork --auto-pause -o "no-audio loop" '*' ~/Videos/wallpapers/ocean.mp4
```

**Quality and performance options:**

```bash
# High quality upscaling with ewa_lanczossharp
mpvpaper -o "no-audio loop scale=ewa_lanczossharp cscale=ewa_lanczossharp" \
    DP-1 ~/Videos/wallpapers/1080p-upscale.mp4

# Low power mode: software decode, lower fps cap
mpvpaper -o "no-audio loop hwdec=no framedrop=vo" \
    eDP-1 ~/Videos/wallpapers/ambient.mp4

# Custom GLSL shader (e.g. CAS sharpening)
mpvpaper -o "no-audio loop glsl-shaders='~~/shaders/CAS.glsl'" \
    DP-1 ~/Videos/wallpapers/sharp.mp4

# DMA-BUF direct buffer sharing (lowest overhead)
mpvpaper -o "no-audio loop vo=dmabuf-wayland" \
    '*' ~/Videos/wallpapers/scene.mp4
```

**Playback control via mpv's IPC socket:**

```bash
# Start with IPC socket
mpvpaper -o "no-audio loop input-ipc-server=/tmp/mpvpaper.sock" \
    '*' ~/Videos/wallpapers/scene.mp4

# Pause playback
echo '{"command": ["set_property", "pause", true]}' | \
    socat - UNIX-CONNECT:/tmp/mpvpaper.sock

# Change video at runtime
echo '{"command": ["loadfile", "/path/to/new.mp4", "replace"]}' | \
    socat - UNIX-CONNECT:/tmp/mpvpaper.sock
```

---

## 27.6 Quickshell Wallpaper (via ScreencopyView or Image)

Quickshell is a QtQuick-based shell framework for Wayland that can render arbitrary QML directly
on a `WlrLayershell` surface. This makes it uniquely capable of producing fully procedural,
shader-animated, or data-driven wallpapers that no external tool can match. You write QML
components and they run as your wallpaper.

The `Image` component placed inside a `WlrLayershell` with `WlrLayershell.Layer.Background` is
the simplest static case — equivalent to swaybg but written in QML. More interesting is using
`ShaderEffect` to write GLSL fragment shaders that run live, producing animated gradients,
plasma effects, or reactive audio visualizations. The `AnimatedImage` type handles GIFs natively
through Qt's image plugin system.

For advanced use, `ScreencopyView` (part of the Quickshell Hyprland extension) can capture live
window content into a texture, enabling blur-behind effects or picture-in-picture wallpapers.

**Static image wallpaper in QML:**

```qml
// ~/.config/quickshell/wallpaper.qml
import Quickshell
import Quickshell.Wayland
import QtQuick

ShellRoot {
    Variants {
        model: Quickshell.screens
        WlrLayershell {
            required property var modelData
            screen: modelData
            layer: WlrLayershell.Layer.Background
            anchors.fill: parent
            exclusiveZone: -1

            Image {
                anchors.fill: parent
                source: "/home/user/Pictures/wallpapers/mountain.jpg"
                fillMode: Image.PreserveAspectCrop
                smooth: true
            }
        }
    }
}
```

**Animated GLSL plasma shader wallpaper:**

```qml
// ~/.config/quickshell/plasma-wallpaper.qml
import Quickshell
import Quickshell.Wayland
import QtQuick

ShellRoot {
    Variants {
        model: Quickshell.screens
        WlrLayershell {
            required property var modelData
            screen: modelData
            layer: WlrLayershell.Layer.Background
            anchors.fill: parent
            exclusiveZone: -1

            Rectangle {
                anchors.fill: parent
                color: "black"

                ShaderEffect {
                    anchors.fill: parent
                    property real time: 0
                    property vector2d resolution: Qt.vector2d(width, height)

                    NumberAnimation on time {
                        from: 0; to: 1000; duration: 1000000; loops: Animation.Infinite
                    }

                    fragmentShader: "
                        uniform float time;
                        uniform vec2 resolution;
                        varying vec2 qt_TexCoord0;

                        void main() {
                            vec2 uv = qt_TexCoord0 * 2.0 - 1.0;
                            uv.x *= resolution.x / resolution.y;
                            float v = sin(uv.x * 5.0 + time * 0.5)
                                    + sin(uv.y * 4.0 + time * 0.3)
                                    + sin((uv.x + uv.y) * 3.0 + time * 0.4);
                            vec3 col = 0.5 + 0.5 * cos(v + vec3(0.0, 2.094, 4.188));
                            gl_FragColor = vec4(col, 1.0);
                        }
                    "
                }
            }
        }
    }
}
```

See **Ch 15** for a deeper introduction to Quickshell and WlrLayershell surface configuration.

---

## 27.7 Wallpaper Automation Scripts

The real power of Wayland wallpaper tools emerges when you connect them to your broader rice
pipeline. A common pattern is "random wallpaper on startup" — pick a random file from a
directory and apply it with swww at login. A more sophisticated pattern links wallpaper selection
to time of day: dark dramatic images at night, bright landscapes during the day. Both patterns
are straightforward shell scripts.

The most impactful integration is with color scheme generators: pywal, matugen, and wallust all
derive a terminal and application color palette from a wallpaper image. Running these tools after
each wallpaper change makes your entire desktop theme — bar colors, terminal colors, rofi theme,
GTK colors — shift to match the new image automatically. This is the centerpiece of the "unified
aesthetic" rice philosophy.

See **Ch 38** for pywal and matugen color pipeline configuration, and **Ch 53** for session
startup ordering that ensures wallpaper and color schemes are applied before the bar renders.

**Random wallpaper script with swww:**

```bash
#!/usr/bin/env bash
# ~/.local/bin/random-wallpaper.sh
# Usage: random-wallpaper.sh [--transition-type fade]

WALLPAPER_DIR="$HOME/Pictures/wallpapers"
TRANSITION="${2:-fade}"
TRANSITION_DURATION="${3:-1.0}"

WALL=$(find "$WALLPAPER_DIR" -type f \( -iname "*.jpg" -o -iname "*.png" \
    -o -iname "*.webp" -o -iname "*.jpeg" \) | shuf -n1)

echo "Setting wallpaper: $WALL"
swww img "$WALL" \
    --transition-type "$TRANSITION" \
    --transition-duration "$TRANSITION_DURATION" \
    --transition-fps 60 \
    --resize crop \
    --filter Lanczos
```

**Time-of-day wallpaper switching:**

```bash
#!/usr/bin/env bash
# ~/.local/bin/time-wallpaper.sh
WALL_DIR="$HOME/Pictures/wallpapers"
HOUR=$(date +%H)

if   (( HOUR >= 6  && HOUR < 9  )); then DIR="morning"
elif (( HOUR >= 9  && HOUR < 17 )); then DIR="day"
elif (( HOUR >= 17 && HOUR < 20 )); then DIR="evening"
else                                      DIR="night"
fi

WALL=$(find "$WALL_DIR/$DIR" -type f | shuf -n1)
swww img "$WALL" --transition-type fade --transition-duration 2.0
```

**pywal integration (sets wallpaper and regenerates terminal colors):**

```bash
#!/usr/bin/env bash
# ~/.local/bin/wal-wallpaper.sh
WALL="$1"
if [[ -z "$WALL" ]]; then
    WALL=$(find "$HOME/Pictures/wallpapers" -type f | shuf -n1)
fi

# Generate color scheme from image
wal -i "$WALL" -n --backend haishoku

# Set wallpaper with swww
swww img "$WALL" \
    --transition-type grow \
    --transition-pos "0.5,0.5" \
    --transition-duration 1.0

# Reload apps that read pywal colors
# Reload waybar
pkill -SIGUSR2 waybar

# Reload dunst
pkill dunst && dunst &

echo "Wallpaper and color scheme updated: $WALL"
```

**matugen integration:**

```bash
#!/usr/bin/env bash
# ~/.local/bin/matugen-wallpaper.sh
WALL="$1"
[[ -z "$WALL" ]] && WALL=$(find "$HOME/Pictures/wallpapers" -type f | shuf -n1)

# matugen derives Material You palette and applies templates
matugen image "$WALL"

# swww uses the same image
swww img "$WALL" --transition-type wipe --transition-angle 30 --transition-duration 0.8
```

**Keybinding in Hyprland config:**

```ini
# ~/.config/hypr/hyprland.conf
bind = $mainMod, W, exec, ~/.local/bin/random-wallpaper.sh
bind = $mainMod SHIFT, W, exec, ~/.local/bin/wal-wallpaper.sh
```

---

## 27.8 Wallpaper Sources and Management

A good wallpaper collection is the foundation of a successful rice. Managing hundreds of images
requires consistent directory structure, metadata tagging, and tooling for browsing and picking.
The tools in this section handle browsing (`imv`, `nsxiv`), color-scheme generation from
arbitrary images (`wallust`), and collection organization best practices.

Directory structure matters when scripts reference subdirectories by mood or time of day. A
flat directory is fine for random pickers, but organizing by theme (`nature/`, `abstract/`,
`cityscape/`, `dark/`, `light/`) lets you build targeted scripts that fit your current mood or
display conditions.

wallust is a rust-rewrite alternative to pywal that is faster at palette generation and supports
more backends and template formats. It is fully compatible with pywal's template syntax and can
be a drop-in replacement in most ricing pipelines.

**Directory structure recommendation:**

```
~/Pictures/wallpapers/
├── dark/
│   ├── night/
│   └── moody/
├── light/
│   ├── morning/
│   └── day/
├── abstract/
├── nature/
├── cityscape/
└── current -> ../wallpapers/dark/night/selected.jpg  # symlink
```

**imv — lightweight image viewer for wallpaper selection:**

```bash
# Install
sudo pacman -S imv

# Browse directory; press Enter/Space to advance, Q to quit
imv ~/Pictures/wallpapers/

# Use selected file path in a script
WALL=$(imv -n 1 ~/Pictures/wallpapers/ 2>&1 | tail -1)
swww img "$WALL"
```

**nsxiv — image grid browser:**

```bash
# Install
sudo pacman -S nsxiv   # or paru -S nsxiv

# Grid thumbnail view; mark with m, print marked paths with Enter
WALL=$(nsxiv -t -o ~/Pictures/wallpapers/ | head -1)
[[ -n "$WALL" ]] && swww img "$WALL"
```

**wallust — fast pywal-compatible palette generator:**

```bash
# Install (AUR)
paru -S wallust

# Generate colors from image (writes to ~/.config/wallust/)
wallust run ~/Pictures/wallpapers/forest.jpg

# Apply colors to templates (same template format as pywal)
wallust run ~/Pictures/wallpapers/forest.jpg --backend kmeans

# Use with swww
wallust run "$WALL" && swww img "$WALL"
```

**Symlink-based "current wallpaper" pattern:**

```bash
#!/usr/bin/env bash
# ~/.local/bin/set-wallpaper.sh
# Maintains a stable symlink so other tools always know the current wallpaper
WALL="$1"
ln -sf "$WALL" "$HOME/Pictures/wallpapers/current"
swww img "$WALL" --transition-type fade --transition-duration 1.0
wal -i "$WALL" -n  # update color scheme
```

---

## Troubleshooting

**swww-daemon not found / socket not created:**
Ensure `swww-daemon` is in your `PATH` and was started before calling `swww img`. Add a small
wait or check for socket existence:

```bash
swww-daemon &
# Wait up to 3 seconds for socket
timeout 3 bash -c 'until [[ -S "$XDG_RUNTIME_DIR/swww/swww.socket" ]]; do sleep 0.1; done'
swww img ~/Pictures/wallpapers/default.jpg
```

**Blank/black background on compositor startup:**
Your wallpaper daemon may start before the compositor fully initializes outputs. Use
`exec-once` in Hyprland (not `exec`) and ensure you're not racing with output configuration.
For multi-monitor setups, query `hyprctl monitors` and wait for all outputs to appear before
sending per-output wallpaper commands.

**hyprpaper IPC refusing connections:**
Confirm `ipc = on` is set in `hyprpaper.conf`. Verify the hyprctl socket path with
`echo $HYPRLAND_INSTANCE_SIGNATURE` and ensure you are in the same user session.

**swww transitions stutter or tear:**
Set `--transition-fps` to match your monitor's refresh rate. On variable-refresh displays, cap
to the base refresh rate. Ensure `LIBVA_DRIVER_NAME` and `WLR_RENDERER` are set correctly for
your GPU. Try `--filter Bilinear` if `Lanczos` is CPU-bound.

**mpvpaper high GPU usage:**
Add `vo=dmabuf-wayland hwdec=vaapi` to mpv options. Reduce `--mpv-options "fps=24"` to cap
playback frame rate. Use `--auto-pause` to stop rendering when windows cover the output.

```bash
mpvpaper --auto-pause -o "no-audio loop vo=dmabuf-wayland hwdec=vaapi fps=24" \
    '*' ~/Videos/wallpapers/ambient.mp4
```

**Wallpaper not spanning ultrawide / wrong aspect ratio on multi-head:**
Use `--resize crop` with swww, or `fill` mode with swaybg. For per-head images, explicitly
address each output by name. Query output names with `wayland-info | grep wl_output` or
`hyprctl monitors | grep Monitor`.

**swaybg exits immediately:**
swaybg requires a valid Wayland display. Ensure `WAYLAND_DISPLAY` is set in the environment
of the calling process. If running from a systemd service, add
`Environment=WAYLAND_DISPLAY=wayland-1` or use `EnvironmentFile` pointing to your user
environment exports.

**Color scheme not updating after wallpaper change:**
pywal and matugen write color files to `~/.cache/wal/` and `~/.cache/matugen/` respectively.
Apps that read these files at startup need to be restarted or sent SIGHUP/SIGUSR2. Waybar
respects `SIGUSR2` for reload. Foot terminal reads `~/.config/foot/foot.ini` which you can
regenerate via a pywal template and then send SIGHUP to running instances.

---

*See also:* **Ch 38** — pywal and matugen color pipelines | **Ch 15** — Quickshell shell
framework | **Ch 53** — Session startup ordering | **Ch 08** — Wayland protocol fundamentals

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
