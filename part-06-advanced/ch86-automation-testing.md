# Chapter 86 — Automation and Testing of Wayland Ricing Configs

## Overview

A ricing config is code. Like any code, it can be tested. This chapter covers
the full testing stack: static config validation, linting dotfiles, asserting
compositor state via IPC, screenshot regression testing, synthetic input
injection, and CI pipelines that catch breakage across compositor updates.

The headless compositor substrate (how to run sway/Hyprland with no display) is
covered in §85.7. This chapter assumes that foundation and builds assertions
on top of it.

---

## 86.1 Static Config Validation

The first line of defence — validate configs without starting the compositor.

### sway

```bash
sway -C                    # validates config, exits immediately
sway -C -c /path/to/config # validate a specific file
echo $?                    # 0 = valid, non-zero = errors printed to stderr
```

Catches: syntax errors, unknown directives, invalid option values. Does **not**
catch: wrong output names, missing executables in `exec` lines, input device
identifiers that don't match any device.

Add to CI:
```bash
sway -C || { echo "sway config invalid"; exit 1; }
```

### Hyprland

```bash
Hyprland --verify-config              # parse config, exit before starting server
Hyprland --verify-config -c path/to/hyprland.conf
echo $?                               # 0 = valid, 1 = errors
```

The IPC command `hyprctl configerrors` queries errors from a **running**
instance — useful for post-reload diagnostics, not static CI.

Live reload with error capture:
```bash
# Inside a running Hyprland session:
hyprctl reload
hyprctl configerrors      # list any errors from the reload
```

### niri

```bash
niri validate             # parse KDL config, exit
niri validate -c /path/to/config.kdl
```

### labwc / river

Neither has a validation flag. labwc logs errors to stderr at startup; SIGHUP
triggers reload. For CI purposes, launch in a headless environment and check
exit status:
```bash
WLR_BACKENDS=headless labwc 2>&1 | grep -i error
```

### Config validation in CI (GitHub Actions)

```yaml
name: Validate Wayland Configs
on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4

      - name: Install compositors
        run: |
          sudo apt-get install -y sway niri

      - name: Validate sway config
        run: sway -C -c .config/sway/config

      - name: Validate niri config
        run: niri validate -c .config/niri/config.kdl

      - name: Validate Hyprland config
        run: |
          # Hyprland needs display-less environment
          DISPLAY= Hyprland --verify-config -c .config/hypr/hyprland.conf
```

---

## 86.2 Dotfile Linting

### Shell scripts (shellcheck)

```bash
sudo pacman -S shellcheck

# Single file
shellcheck ~/.config/hypr/scripts/screenshot.sh

# All scripts in dotfiles
find ~/.config -name "*.sh" -exec shellcheck {} +

# Common suppressions
shellcheck -e SC2034 script.sh   # unused variable (ok for sourced files)
shellcheck -e SC1091 script.sh   # sourced file not found
```

### TOML configs (taplo)

```bash
paru -S taplo-cli

# Validate syntax
taplo check ~/.config/alacritty/alacritty.toml
taplo check ~/.config/starship.toml

# Format check (CI mode — no modification)
taplo fmt --check ~/.config/foot/foot.ini   # foot uses ini, not toml

# Format in place
taplo fmt ~/.config/alacritty/alacritty.toml
```

Applies to: Alacritty (`alacritty.toml`), Starship (`starship.toml`),
WezTerm (`wezterm.lua` uses Lua not TOML), Helix (`config.toml`).

### YAML configs (yamllint)

```bash
sudo pacman -S yamllint

yamllint ~/.config/waybar/config.jsonc  # will warn on JSONC comments
yamllint -d relaxed ~/.config/kanshi/config
```

Waybar uses JSONC (JSON with comments), not valid YAML. Use `jq` to catch
JSON syntax errors after stripping comments:
```bash
# Strip // comments and validate JSON structure:
sed '/^\s*\/\//d' ~/.config/waybar/config | jq . > /dev/null
```

### QML / Quickshell (qmllint)

```bash
# qmllint is part of qt6-declarative
sudo pacman -S qt6-declarative

# Lint a single file
qmllint ~/.config/quickshell/shell.qml

# Lint with module path
qmllint -I ~/.config/quickshell ~/.config/quickshell/shell.qml

# JSON output for CI integration (Qt 6.2+)
qmllint --json shell.qml

# Treat unused imports as errors
qmllint --unused-imports=error shell.qml

# Suppress specific warnings inline:
// qmllint disable unqualified
someProperty: someValue
// qmllint enable unqualified
```

What qmllint catches:
- Unqualified property accesses
- Signal handlers without matching signals
- Missing import statements
- Deprecated component properties
- Compile-to-C++ compatibility issues

### All-in-one lint script

```bash
#!/bin/bash
# lint-dotfiles.sh — run from your dotfiles root
set -e

echo "=== shellcheck ==="
find . -name "*.sh" | xargs shellcheck

echo "=== taplo ==="
find . -name "*.toml" | xargs taplo check

echo "=== waybar json ==="
for f in $(find . -path "*/waybar/config*"); do
  sed '/^\s*\/\//d' "$f" | jq . > /dev/null && echo "$f: OK"
done

echo "=== qmllint ==="
find . -name "*.qml" | xargs -I{} qmllint {}

echo "All checks passed."
```

---

## 86.3 Synthetic Input Injection

Testing interactive workflows requires injecting keyboard and mouse events into
the Wayland session.

### wtype — keyboard input (wlroots compositors only)

wtype uses the `zwp_virtual_keyboard_manager_v1` protocol. Works on Sway,
Hyprland, River, labwc. Does **not** work on GNOME/KDE.

```bash
sudo pacman -S wtype

# Type text
wtype "hello world"

# Key combos
wtype -M ctrl c -m ctrl          # Ctrl+C (hold mod, press key, release mod)
wtype -M super -P Return -p Return -m super   # Super+Enter

# Named keys
wtype -P XF86AudioRaiseVolume -p XF86AudioRaiseVolume

# With delay between keystrokes (ms)
wtype -d 100 "slow typing"

# From stdin
echo "test input" | wtype -
```

For Hyprland specifically, IPC dispatch can also type text:
```bash
hyprctl dispatch type "hello"
hyprctl dispatch sendshortcut SUPER, Return, exec, kitty
```

### ydotool — compositor-agnostic input via uinput

ydotool writes to `/dev/uinput`, bypassing the Wayland protocol entirely.
Works on any compositor, X11, or TTY.

```bash
sudo pacman -S ydotool

# Required: udev rule for non-root access
echo 'KERNEL=="uinput", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"' \
  | sudo tee /etc/udev/rules.d/60-ydotool.rules
sudo usermod -aG input $(whoami)
sudo udevadm trigger

# Start the daemon (required since v1.0.0)
ydotoold &

# Type text
ydotool type "hello world"

# Mouse click (0xC0 = left button)
ydotool click 0xC0
ydotool mousemove 100 200

# Key by keycode (see /usr/include/linux/input-event-codes.h)
ydotool key 28:1 28:0   # Enter press and release
```

### dotool — simpler uinput tool (no daemon)

```bash
paru -S dotool   # or: git clone https://sr.ht/~geb/dotool && make install

# Symbolic key names, reads from stdin
echo "type Hello World" | dotool
echo "key ctrl+c" | dotool
echo "mousemove 100 200" | dotool
echo "click left" | dotool

# Script
{
  echo "key super+Return"
  sleep 0.5
  echo "type kitty --title test-terminal"
  echo "key Return"
} | dotool
```

dotool requires the same uinput udev rule as ydotool but needs no daemon.

### Which input tool to use

| Scenario | Tool |
|----------|------|
| wlroots compositor (Sway/Hyprland) | `wtype` — simplest, no daemon |
| Any compositor or TTY | `dotool` — no daemon, symbolic keys |
| GNOME/KDE session | `ydotool` — uinput, compositor-agnostic |
| Mouse automation | `ydotool` or `dotool` |
| Hyprland-specific dispatch | `hyprctl dispatch` |

---

## 86.4 Compositor State Assertions via IPC

After injecting input or launching apps, assert the compositor reached the
expected state using its IPC interface.

### Sway IPC with jq

```bash
# Assert a window with app_id "kitty" is present
swaymsg -t get_tree | jq -e '.. | .app_id? | select(. == "kitty")' > /dev/null
echo "kitty window found: $?"

# Assert focused window
swaymsg -t get_tree | jq -r '.. | select(.focused == true) | .name'

# Assert window count on workspace 1
count=$(swaymsg -t get_workspaces | jq '.[] | select(.name == "1") | .windows')
[ "$count" -eq 2 ] || { echo "Expected 2 windows on ws1, got $count"; exit 1; }

# Assert window position
swaymsg -t get_tree | jq '.. | select(.app_id? == "kitty") | .rect'
# → {"x":0,"y":23,"width":960,"height":1057}

# Wait for a window to appear (poll)
wait_for_app() {
  local app_id="$1"
  for i in $(seq 30); do
    swaymsg -t get_tree | jq -e ".. | .app_id? | select(. == \"$app_id\")" \
      > /dev/null 2>&1 && return 0
    sleep 0.2
  done
  echo "Timeout waiting for $app_id"
  return 1
}
wait_for_app kitty
```

### Hyprland IPC with jq

```bash
# Note: -j flag goes BEFORE the subcommand
hyprctl -j clients         # all clients as JSON array
hyprctl -j activewindow    # focused window
hyprctl -j workspaces      # all workspaces

# Assert window class exists
hyprctl -j clients | jq -e '.[] | select(.class == "kitty")' > /dev/null

# Assert floating state
is_float=$(hyprctl -j clients | jq '.[] | select(.class == "pavucontrol") | .floating')
[ "$is_float" = "true" ] || echo "FAIL: pavucontrol should be floating"

# Assert window count on workspace 1
count=$(hyprctl -j clients | jq '[.[] | select(.workspace.id == 1)] | length')
[ "$count" -ge 1 ] || { echo "FAIL: no windows on workspace 1"; exit 1; }

# Assert window position
pos=$(hyprctl -j clients | jq '.[] | select(.class == "kitty") | .at')
echo "kitty at: $pos"    # → [0,0]

# Poll until window appears
wait_for_class() {
  local class="$1"
  for i in $(seq 50); do
    hyprctl -j clients | jq -e ".[] | select(.class == \"$class\")" \
      > /dev/null 2>&1 && return 0
    sleep 0.1
  done
  return 1
}
```

---

## 86.5 Screenshot Regression Testing

Capture compositor output and compare against a baseline to detect visual
regressions.

### Capturing screenshots with grim

```bash
# Full screenshot to file
grim baseline.png

# Specific output
grim -o HDMI-1 baseline.png

# Region (from known coordinates)
grim -g "0,0 1920x1080" region.png

# Fast PPM to stdout (for piping to ImageMagick)
grim -t ppm - | convert - baseline.png

# No compression (fastest, for scripts)
grim -l 0 current.png
```

### Comparing with ImageMagick

```bash
# Absolute Error — count of differing pixels (most reliable for CI)
ae_count=$(compare -metric AE baseline.png current.png diff.png 2>&1)
if [ "$ae_count" -gt 0 ]; then
  echo "REGRESSION: $ae_count pixels differ"
  exit 1
fi

# With fuzz tolerance (ignore minor antialiasing/subpixel differences)
ae_count=$(compare -metric AE -fuzz 2% baseline.png current.png diff.png 2>&1)
[ "$ae_count" -gt 100 ] && { echo "FAIL: $ae_count pixel diff"; exit 1; }

# SSIM structural similarity (0=identical, higher=more different; inverted from PSNR)
ssim=$(compare -metric SSIM baseline.png current.png /dev/null 2>&1)
echo "SSIM: $ssim"

# Highlight differences visually
compare baseline.png current.png -highlight-color red -lowlight-color white diff.png
```

> **Note:** `compare -metric PSNR` outputs to **stderr** and its exit code is
> 0 whether images match or not — use `AE` for exit-code-based CI.

### odiff — fast perceptual comparison

```bash
# Install via npm (binary distribution)
npm install -g odiff-bin

# Compare (exit 0=match, 1=different)
odiff baseline.png current.png diff.png
echo $?

# In CI:
if ! odiff -t 0.1 baseline.png current.png diff.png; then
  echo "Visual regression detected"
  exit 1
fi
```

odiff uses YIQ perceptual color space and is ~6× faster than ImageMagick for
large screenshots. The `-t` threshold controls sensitivity.

### Full regression test script

```bash
#!/bin/bash
# wayland-regression-test.sh
set -e
BASELINE_DIR="./test/baselines"
CURRENT_DIR="./test/current"
DIFF_DIR="./test/diffs"
COMPOSITOR="${COMPOSITOR:-sway}"

mkdir -p "$CURRENT_DIR" "$DIFF_DIR"

# Start headless compositor (see Ch 85.7)
export WLR_BACKENDS=headless WLR_LIBINPUT_NO_DEVICES=1
$COMPOSITOR &
COMP_PID=$!
sleep 1

# Launch the test subject
WAYLAND_DISPLAY=wayland-1 quickshell &
APP_PID=$!
sleep 2

# Capture
WAYLAND_DISPLAY=wayland-1 grim "$CURRENT_DIR/shell.png"

# Compare
ae=$(compare -metric AE -fuzz 2% \
  "$BASELINE_DIR/shell.png" "$CURRENT_DIR/shell.png" \
  "$DIFF_DIR/shell.png" 2>&1) || true

kill $APP_PID $COMP_PID 2>/dev/null

if [ "${ae:-0}" -gt 500 ]; then
  echo "FAIL: $ae pixel regression in shell.png"
  exit 1
fi
echo "PASS: shell.png within threshold ($ae differing pixels)"
```

---

## 86.6 QML Component Testing (Quickshell)

### qmllint — static analysis

See §86.2. Run as part of the test pipeline before the visual tests.

### QQuickTest — unit tests for QML components

Qt's built-in QML test framework allows testing component logic without a full
compositor:

```qml
// tests/tst_WorkspaceBar.qml
import QtTest
import ".."   // import your Quickshell component

TestCase {
    name: "WorkspaceBar"

    function test_workspaceCount() {
        var bar = createTemporaryObject(WorkspaceBar, testCase)
        compare(bar.workspaces.count, 0)
    }

    function test_activeWorkspace() {
        var bar = createTemporaryObject(WorkspaceBar, testCase)
        bar.activeId = 2
        compare(bar.activeId, 2)
    }
}
```

C++ runner:
```cpp
// tests/main.cpp
#include <QtQuickTest>
QUICK_TEST_MAIN(quickshell_tests)
```

```cmake
# CMakeLists.txt
find_package(Qt6 REQUIRED COMPONENTS QuickTest)
add_executable(tst_quickshell tests/main.cpp)
target_link_libraries(tst_quickshell Qt6::QuickTest)
qt_add_qml_module(tst_quickshell ...)
```

Run: `QT_QPA_PLATFORM=offscreen ./tst_quickshell`

The `offscreen` platform runs Qt without any display server — tests component
logic and bindings without needing a Wayland compositor.

---

## 86.7 NixOS VM Tests — Gold Standard

The NixOS test framework is the most powerful approach: it spins up a full VM
with a real compositor and uses QEMU's framebuffer + OCR for assertions — no
X11, no special protocol access required.

### Architecture

```
NixOS VM (QEMU + virtio-gpu pixman)
  └── WLR_RENDERER=pixman sway --validate && sway
       └── Wayland compositor running
            └── test script (Python driver)
                 ├── machine.screenshot() → QEMU framebuffer
                 ├── machine.wait_for_text("regex") → OCR on framebuffer
                 ├── machine.send_key("super-Return") → QEMU QMP
                 └── swaymsg IPC assertions (via machine.succeed())
```

### Writing a sway ricing test

```nix
# tests/sway-rice.nix
{ pkgs, ... }:
pkgs.testers.runNixOSTest {
  name = "sway-rice";

  nodes.machine = { ... }: {
    imports = [ ./sway-config-module.nix ];

    virtualisation.qemu.options = [ "-vga none -device virtio-gpu-pci" ];

    environment.variables = {
      WLR_RENDERER = "pixman";   # software render — no GPU needed in VM
      WLR_LIBINPUT_NO_DEVICES = "1";
    };

    programs.sway.enable = true;
    environment.systemPackages = [ pkgs.foot pkgs.grim ];

    services.getty.autologinUser = "alice";
    users.users.alice = {
      isNormalUser = true;
      extraGroups = [ "video" "input" ];
    };

    programs.bash.loginShellInit = ''
      if [ "$(tty)" = "/dev/tty1" ]; then
        sway -C && exec sway
      fi
    '';
  };

  testScript = ''
    machine.wait_for_unit("multi-user.target")
    # Wait for Wayland socket
    machine.wait_for_file("/run/user/1000/wayland-1")
    machine.sleep(2)

    # Take baseline screenshot
    machine.screenshot("startup")

    # Assert compositor running via IPC
    machine.succeed("SWAYSOCK=/run/user/1000/sway-ipc.*.sock "
                    "swaymsg -t get_version")

    # Launch terminal, assert window appears
    machine.send_key("super-Return")
    machine.sleep(1)
    machine.succeed("SWAYSOCK=/run/user/1000/sway-ipc.*.sock "
                    "swaymsg -t get_tree | jq -e '.. | .app_id? "
                    "| select(. == \"foot\")'")

    machine.screenshot("foot-open")

    # Visual assertion via OCR
    machine.wait_for_text(r"alice@")   # prompt visible in terminal

    # Test a keybind
    machine.send_key("super-shift-q")  # close window
    machine.sleep(0.5)
    windows = machine.succeed("SWAYSOCK=/run/user/1000/sway-ipc.*.sock "
                              "swaymsg -t get_tree | jq '[.. | .app_id? "
                              "| select(. == \"foot\")] | length'")
    assert windows.strip() == "0", f"Expected 0 foot windows, got {windows}"
  '';
}
```

Run: `nix build .#checks.x86_64-linux.sway-rice`

### Key Python driver methods and Wayland compat

| Method | Wayland? | Notes |
|--------|----------|-------|
| `machine.screenshot(name)` | Yes | QEMU framebuffer, any display server |
| `machine.send_key(key)` | Yes | QEMU QMP, any display server |
| `machine.send_chars(text)` | Yes | QEMU QMP |
| `machine.wait_for_text(re)` | Yes | OCR via tesseract; add `enableOCR = true` |
| `machine.wait_for_window(re)` | **No** | Uses `xwininfo` — X11 only |
| `machine.wait_for_x()` | No | Waits for X socket |
| `machine.succeed(cmd)` | Yes | Runs shell command, returns stdout |
| `machine.wait_for_unit(svc)` | Yes | Waits for systemd unit |

For Wayland window detection, use `machine.succeed()` with IPC queries instead
of `wait_for_window()`.

---

## 86.8 Continuous Integration for Dotfiles

### GitHub Actions — full dotfile CI pipeline

```yaml
# .github/workflows/dotfiles-ci.yml
name: Dotfile CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  lint:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4

      - name: Install tools
        run: |
          sudo apt-get update
          sudo apt-get install -y shellcheck sway niri jq
          npm install -g odiff-bin

      - name: shellcheck
        run: find . -name "*.sh" | xargs shellcheck

      - name: TOML validation (taplo)
        uses: uncenter/setup-taplo@v1
        with: { version: "0.9.3" }
      - run: find . -name "*.toml" | xargs taplo check

      - name: Validate sway config
        run: sway -C -c .config/sway/config

      - name: Validate niri config
        run: niri validate -c .config/niri/config.kdl

      - name: Validate Waybar JSON
        run: |
          for f in .config/waybar/config*; do
            sed '/^\s*\/\//d; /^\s*$/d' "$f" | jq . > /dev/null \
              && echo "$f: valid" || { echo "$f: invalid JSON"; exit 1; }
          done

      - name: qmllint
        run: |
          sudo apt-get install -y qml6-base-dev
          find .config/quickshell -name "*.qml" | xargs qmllint

  visual-regression:
    runs-on: ubuntu-24.04
    needs: lint
    steps:
      - uses: actions/checkout@v4
        with: { lfs: true }   # store baselines in Git LFS

      - name: Install compositor + tools
        run: |
          sudo apt-get install -y sway grim imagemagick

      - name: Screenshot test
        run: |
          export WLR_BACKENDS=headless WLR_LIBINPUT_NO_DEVICES=1
          sway -c .config/sway/config &
          sleep 2
          WAYLAND_DISPLAY=wayland-1 grim /tmp/current.png
          compare -metric AE -fuzz 2% \
            test/baselines/sway-startup.png /tmp/current.png /tmp/diff.png 2>&1
          [ $? -le 1 ] || exit 1   # exit 0=match, 1=diff (check AE count)
```

### Updating baselines

```bash
# Update a baseline after intentional visual change
WAYLAND_DISPLAY=wayland-1 grim test/baselines/sway-startup.png
git add test/baselines/sway-startup.png
git commit -m "update: sway startup baseline after bar redesign"
```

Store baseline screenshots in Git LFS to avoid bloating history.

---

## 86.9 Testing Hyprland-Specific Config

### Config validation + IPC round-trip test

```bash
#!/bin/bash
# test-hyprland-config.sh
set -e

# 1. Static validation
Hyprland --verify-config -c "$HOME/.config/hypr/hyprland.conf"
echo "Config syntax: OK"

# 2. Start headless Hyprland
export WLR_BACKENDS=headless WLR_LIBINPUT_NO_DEVICES=1
export AQ_DRM_DEVICES=""   # prevent Hyprland from trying real DRM nodes
Hyprland -c "$HOME/.config/hypr/hyprland.conf" &
HYPR_PID=$!
sleep 2

# 3. Assert it started and socket exists
HYPR_SOCK=$(ls /tmp/hypr/*/.socket.sock 2>/dev/null | head -1)
[ -n "$HYPR_SOCK" ] || { echo "FAIL: Hyprland socket not found"; kill $HYPR_PID; exit 1; }
export HYPRLAND_INSTANCE_SIGNATURE="${HYPR_SOCK%/.socket.sock}"
HYPRLAND_INSTANCE_SIGNATURE="${HYPRLAND_INSTANCE_SIGNATURE#/tmp/hypr/}"

# 4. Query version via IPC
hyprctl version
echo "Hyprland IPC: OK"

# 5. Assert no config errors
errors=$(hyprctl configerrors)
[ -z "$errors" ] || { echo "Config errors: $errors"; kill $HYPR_PID; exit 1; }
echo "Config errors: none"

# 6. Take screenshot
grim /tmp/hyprland-headless.png
echo "Screenshot: OK"

kill $HYPR_PID
echo "All checks passed."
```

### Window rule testing

```bash
# Launch a test app, assert window rule was applied
hyprctl dispatch exec "[class:test-float]" foot --title test-float
sleep 0.5

# Assert the window is floating (from windowrulev2 = float, class:test-float)
is_float=$(hyprctl -j clients | jq '.[] | select(.class == "foot" and .title == "test-float") | .floating')
[ "$is_float" = "true" ] || echo "FAIL: window rule float not applied"
```

---

## 86.10 Performance Benchmarking

### Frame timing via wp_presentation

The `wp_presentation` Wayland protocol (stable in wayland-protocols) allows
clients to receive precise timestamps for when each frame was displayed. Use
it to measure compositor frame delivery consistency.

There is no standalone CLI for this. Use a benchmark app like `vkmark` or
`glmark2-wayland`, or instrument your own app using the libwayland API.

For quick compositor responsiveness testing:

```bash
# wlroots debug logging (very verbose)
WLR_DEBUG=1 sway 2>&1 | grep -i "frame\|render\|present"

# Mesa frame timing
MESA_DEBUG=1 app 2>&1 | grep -i "frame\|present\|swap"

# Simple frame counter via Hyprland
watch -n1 'hyprctl -j monitors | jq ".[0].activelyTearing"'
```

### Compositor startup time

```bash
# Measure time from launch to first frame (Wayland socket appearing)
time (
  sway &
  while [ ! -S "$XDG_RUNTIME_DIR/wayland-1" ]; do sleep 0.01; done
  echo "compositor ready"
  kill $!
)
```

### Config reload time (Hyprland)

```bash
time hyprctl reload
# Measures round-trip: send reload IPC → compositor reloads → response
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
