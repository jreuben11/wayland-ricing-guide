# Chapter 49 — Contributing to the Wayland Ecosystem

## Contents

- [Overview](#overview)
- [49.1 The Ecosystem Map](#491-the-ecosystem-map)
- [49.2 Where to Start](#492-where-to-start)
  - [Documentation and Wikis](#documentation-and-wikis)
  - [Bug Reports with WAYLAND_DEBUG](#bug-reports-with-waylanddebug)
  - [Translations (i18n)](#translations-i18n)
  - [Protocol Testing Across Compositors](#protocol-testing-across-compositors)
- [49.3 Contributing to wayland-protocols](#493-contributing-to-wayland-protocols)
  - [Writing a Protocol Extension](#writing-a-protocol-extension)
  - [Generating Code from Protocol XML](#generating-code-from-protocol-xml)
- [49.4 Contributing to wlroots](#494-contributing-to-wlroots)
  - [Development Environment Setup](#development-environment-setup)
  - [Code Style](#code-style)
  - [Adding a New Protocol Implementation](#adding-a-new-protocol-implementation)
- [49.5 Contributing to Quickshell](#495-contributing-to-quickshell)
  - [Building from Source](#building-from-source)
  - [Adding a New Service Module](#adding-a-new-service-module)
  - [Documentation Contributions](#documentation-contributions)
- [49.6 Contributing to Hyprland](#496-contributing-to-hyprland)
  - [Development Environment](#development-environment)
  - [Writing a Plugin](#writing-a-plugin)
  - [Filing Bug Reports](#filing-bug-reports)
- [49.7 Writing and Publishing Quickshell Configs](#497-writing-and-publishing-quickshell-configs)
  - [Repository Structure](#repository-structure)
  - [Capturing Screenshots and Recordings for Showcasing](#capturing-screenshots-and-recordings-for-showcasing)
  - [NixOS Flake for Maximum Portability](#nixos-flake-for-maximum-portability)
  - [GitHub Tags for Discoverability](#github-tags-for-discoverability)
- [49.8 Filing Good Bug Reports](#498-filing-good-bug-reports)
  - [The Minimal Reproduction Technique](#the-minimal-reproduction-technique)
  - [Collecting WAYLAND_DEBUG Logs Cleanly](#collecting-waylanddebug-logs-cleanly)
  - [Compositor Version and Environment Info](#compositor-version-and-environment-info)
- [49.9 The Community](#499-the-community)
  - [Contributing Code: Social Etiquette](#contributing-code-social-etiquette)
- [Troubleshooting](#troubleshooting)
  - [WAYLAND_DEBUG Produces No Output](#waylanddebug-produces-no-output)
  - [Build Failures in wlroots](#build-failures-in-wlroots)
  - [Hyprland Plugin Load Failures](#hyprland-plugin-load-failures)
  - [Quickshell QML Errors at Runtime](#quickshell-qml-errors-at-runtime)
  - [GitLab CI Failures for freedesktop.org Projects](#gitlab-ci-failures-for-freedesktoporg-projects)
- [Summary](#summary)

---


## Overview

The Wayland ecosystem is maintained by a relatively small but highly skilled community of developers,
designers, and power users. Unlike monolithic desktop environments backed by large corporate sponsors,
most Wayland-native projects depend on volunteer contributions to drive protocol development,
compositor improvements, shell tooling, and documentation. This means individual contributions carry
disproportionate weight — a well-written bug report, a new protocol extension, or a thorough wiki
page can unblock dozens of other developers.

This chapter is a practical guide to making impactful contributions across the entire stack: from
low-level Wayland protocol extensions to compositor internals, shell scripting tools, and community
knowledge sharing. The content is organized by skill level and project type, so whether you are an
embedded C developer or a QML hobbyist, there is a meaningful contribution pathway available to you.

Contributions to open-source projects require understanding not just the code, but the social
norms and workflows of each community. Approval timelines, preferred communication channels,
coding standards, and architectural philosophy differ significantly between projects. Reading this
chapter before opening your first merge request will save you considerable frustration.

See Ch 44 for the overall Wayland protocol architecture, and Ch 50 for how to write custom
protocol extensions that may eventually be upstreamed into wayland-protocols.

---

## 49.1 The Ecosystem Map

The Wayland software stack is layered. Understanding which layer a project occupies tells you
what kind of contribution is appropriate and which other projects it interacts with.

**Core protocol layer** (freedesktop.org):
- `wayland` — the core protocol and `libwayland-client`/`libwayland-server` libraries
- `wayland-protocols` — extension protocols (xdg-shell, linux-dmabuf, fractional-scale, etc.)
- `xdg-desktop-portal` — the DBus portal interface layer for sandboxed apps

**Rendering and GPU layer**:
- `mesa` — the open-source OpenGL/Vulkan stack; EGL, GBM, DRM/KMS
- `libdrm` — Direct Rendering Manager userspace library
- `pixman` — software rendering used by many compositors

**Compositor library layer**:
- `wlroots` — the dominant Wayland compositor library (C); used by sway, river, Wayfire, labwc
- `smithay` — emerging Rust compositor library
- `kwin_wayland` — KDE Plasma's compositor (standalone, not a library)

**Compositor layer**:

| Compositor | Language | Library | Community |
|------------|----------|---------|-----------|
| sway       | C        | wlroots | IRC (#sway on Libera) |
| Hyprland   | C++      | custom  | Discord, GitHub |
| niri       | Rust     | smithay | Matrix, GitHub |
| river      | Zig      | wlroots | GitHub, IRC |
| labwc      | C        | wlroots | GitHub |
| Wayfire    | C++      | wlroots | GitHub, Gitter |

**Shell tools layer**:
- `Quickshell` — QML-based shell toolkit (Qt6); bars, overlays, widgets
- `Waybar` — C++/GTK3 status bar
- `mako` / `dunst` — notification daemons
- `swww` / `hyprpaper` — wallpaper daemons
- `fuzzel` / `wofi` / `tofi` — application launchers
- `grim` + `slurp` — screenshot tools

**Portal backend layer**:
- `xdg-desktop-portal-wlr` — wlroots-based portal backend
- `xdg-desktop-portal-hyprland` — Hyprland-specific portal backend
- `xdg-desktop-portal-gnome` / `-kde` — GNOME/KDE backends

Understanding this map lets you trace a bug from symptom to root cause. A fractured screen capture
could be a portal issue, a compositor protocol bug, or a Mesa EGL problem — knowing the layers
tells you where to look and which project to file the issue against.

---

## 49.2 Where to Start

New contributors often underestimate the value of non-code contributions. Maintainers consistently
report that high-quality documentation, detailed bug reports, and test cases save them more time
than average code PRs. Start with the highest-impact, lowest-barrier contributions before
attempting large architectural changes.

### Documentation and Wikis

Every project has gaps in its documentation. Wayland protocol semantics are notoriously subtle —
the difference between a `committed` and `applied` state in xdg-surface, for example, trips up
experienced developers. Look for wiki pages marked `stub`, outdated sections referencing removed
APIs, or missing guides for common workflows.

```bash
# Clone the sway wiki (GitHub wikis are git repos)
git clone https://github.com/swaywm/sway.wiki.git
cd sway.wiki
# Find pages needing work
grep -l "TODO\|FIXME\|stub\|outdated" *.md
```

For projects hosted on GitLab (freedesktop.org, wlroots), wiki contributions are made through
the GitLab wiki interface or by opening issues against documentation.

### Bug Reports with WAYLAND_DEBUG

A useful bug report includes the exact protocol exchange at the time of the failure. The
`WAYLAND_DEBUG` environment variable enables verbose protocol logging:

```bash
# Log all Wayland protocol messages (both directions)
WAYLAND_DEBUG=1 foot 2>&1 | tee /tmp/wayland-debug.log

# Filter to a specific interface
WAYLAND_DEBUG=1 foot 2>&1 | grep -E "xdg_toplevel|wl_surface" | head -100

# For compositor-side debugging (sway example)
SWAY_DEBUG=1 sway > /tmp/sway-debug.log 2>&1
```

Include in every bug report:
- Compositor name and exact version (`sway --version`, `hyprctl version`)
- Kernel version (`uname -r`)
- GPU model and driver (`glxinfo | grep renderer` or `vulkaninfo | grep deviceName`)
- Minimal reproducible configuration (strip to the fewest lines that trigger the bug)
- `WAYLAND_DEBUG` output trimmed to the relevant sequence
- Expected vs. actual behavior, with a screen recording if visual

### Translations (i18n)

GTK-based Wayland tools commonly use GNU gettext for internationalization. Contributing a
translation is a well-defined, self-contained task:

```bash
# Example: contributing a translation to mako
git clone https://github.com/emersion/mako
cd mako
# Find existing .po files
ls po/
# Copy an existing translation as a starting point
cp po/fr.po po/pt_BR.po
# Edit with poedit or a text editor, fill in msgstr fields
# Submit as a pull request
```

### Protocol Testing Across Compositors

The `wayland-protocols` staging area contains protocols that need validation across multiple
compositors before promotion to stable. Testing these is high-value work:

```bash
# Build a test client against a staging protocol
# Example: testing ext-idle-notify-v1
sudo pacman -S wayland-protocols  # ensure latest version

# Check which protocols are in staging
ls /usr/share/wayland-protocols/staging/
# → ext-idle-notify/  ext-session-lock/  xdg-activation/  ...
```

Write small client programs that exercise edge cases in the protocol and report findings as
comments on the relevant MR at gitlab.freedesktop.org.

---

## 49.3 Contributing to wayland-protocols

The `wayland-protocols` repository is the canonical home for extension protocols that are not
part of the core Wayland protocol. Protocols here range from widely-deployed stable interfaces
like `xdg-shell` to experimental staging protocols undergoing multi-compositor validation.

Repository: `https://gitlab.freedesktop.org/wayland/wayland-protocols`

The lifecycle of a new protocol extension follows a defined path:

```
Proposal (issue/discussion) → Draft MR → Unstable → Staging → Stable
```

**Unstable** protocols (`unstable/`) are deprecated in favor of the staging/stable pipeline.
New work targets **staging** (`staging/`) with the intent to eventually graduate to **stable**
(`stable/`). Graduation to stable requires:
1. At least two independent compositor implementations
2. At least two independent client implementations
3. No open protocol design issues
4. Sign-off from core reviewers (Simon Ser, others)

### Writing a Protocol Extension

Protocol files are written in the XML wire format. Study existing protocols before writing your own:

```bash
# Read an approachable staging protocol
cat /usr/share/wayland-protocols/staging/ext-idle-notify/ext-idle-notify-v1.xml
```

A minimal protocol skeleton:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<protocol name="my_custom_protocol_v1">
  <copyright>
    Copyright 2024 Your Name

    Permission is hereby granted, free of charge, to any person obtaining a
    copy of this software and associated documentation files (the "Software"),
    to deal in the Software without restriction...
  </copyright>

  <interface name="my_manager_v1" version="1">
    <description summary="manager for custom functionality">
      This interface provides access to custom functionality.
      Warning: This protocol is experimental and subject to change.
    </description>

    <request name="destroy" type="destructor">
      <description summary="destroy the manager">
        Destroys the manager object. Existing objects created through
        this interface remain valid.
      </description>
    </request>

    <request name="get_custom_handle">
      <description summary="get a handle for a surface">
        Creates a custom handle for the given surface.
      </description>
      <arg name="id" type="new_id" interface="my_handle_v1"/>
      <arg name="surface" type="object" interface="wl_surface"/>
    </request>
  </interface>

  <interface name="my_handle_v1" version="1">
    <description summary="handle for custom functionality">
      Represents custom state associated with a surface.
    </description>

    <request name="destroy" type="destructor"/>

    <event name="state_changed">
      <description summary="state has changed"/>
      <arg name="new_state" type="uint" enum="state"/>
    </event>

    <enum name="state">
      <entry name="inactive" value="0"/>
      <entry name="active" value="1"/>
    </enum>
  </interface>
</protocol>
```

When submitting a protocol MR, the description must include:
- **Problem statement**: what user-visible problem this solves
- **Design rationale**: why this approach over alternatives
- **Security considerations**: what untrusted clients can do
- **Implementation notes**: which compositors and clients you have implemented it in

### Generating Code from Protocol XML

```bash
# Generate C headers and glue code from your protocol XML
wayland-scanner client-header my_custom_protocol_v1.xml my_custom_protocol_v1-client-protocol.h
wayland-scanner private-code my_custom_protocol_v1.xml my_custom_protocol_v1-protocol.c

# Verify it compiles cleanly
gcc -c my_custom_protocol_v1-protocol.c $(pkg-config --cflags wayland-client)
```

See Ch 50 for a complete walkthrough of writing and implementing a custom protocol extension.

---

## 49.4 Contributing to wlroots

wlroots is the foundational compositor library used by sway, river, labwc, Wayfire, and others.
It handles input, output management, DRM/KMS, Vulkan/GLES2 rendering, and protocol implementation.
Contributions here have broad impact across multiple compositors.

Repository: `https://gitlab.freedesktop.org/wlroots/wlroots`

### Development Environment Setup

```bash
# Install build dependencies (Arch Linux)
sudo pacman -S meson ninja wayland wayland-protocols libdrm mesa \
    libinput libxkbcommon pixman vulkan-headers glslang seatd

# Install build dependencies (Debian/Ubuntu)
sudo apt install meson libwayland-dev libdrm-dev libgbm-dev \
    libinput-dev libxkbcommon-dev libpixman-1-dev libvulkan-dev \
    glslang-tools libseat-dev wayland-protocols

# Clone and build
git clone https://gitlab.freedesktop.org/wlroots/wlroots.git
cd wlroots
meson setup build -Dexamples=true
ninja -C build

# Run tinywl to verify basic functionality
./build/tinywl -s "foot"
```

### Code Style

wlroots follows Linux kernel coding style. Configure your editor:

```bash
# Check style with checkpatch (if available) or clang-format
clang-format --style="{BasedOnStyle: Linux, IndentWidth: 8, UseTab: ForIndentation}" \
    include/my_new_header.h

# The project uses tabs for indentation, 80-char line limit for comments
# Functions: opening brace on same line for K&R style
# Example:
# void wlr_my_function(struct wlr_thing *thing) {
#     if (thing->active) {
#         do_something(thing);
#     }
# }
```

### Adding a New Protocol Implementation

To add support for a new Wayland protocol in wlroots, follow the existing pattern in `types/`:

```c
// include/wlr/types/wlr_my_protocol.h
#ifndef WLR_TYPES_WLR_MY_PROTOCOL_H
#define WLR_TYPES_WLR_MY_PROTOCOL_H

#include <wayland-server-core.h>

struct wlr_my_protocol {
    struct wl_global *global;
    struct wl_list resources; // wl_resource list

    struct {
        struct wl_signal destroy;
    } events;

    void *data;
};

struct wlr_my_protocol *wlr_my_protocol_create(struct wl_display *display);
void wlr_my_protocol_destroy(struct wlr_my_protocol *protocol);

#endif
```

```c
// types/wlr_my_protocol.c
#include <stdlib.h>
#include <wlr/types/wlr_my_protocol.h>
#include <wlr/util/log.h>
#include "my-protocol-v1-protocol.h"

static void my_manager_handle_destroy(struct wl_client *client,
        struct wl_resource *resource) {
    wl_resource_destroy(resource);
}

static const struct my_manager_v1_interface my_manager_impl = {
    .destroy = my_manager_handle_destroy,
};

static void my_bind(struct wl_client *client, void *data,
        uint32_t version, uint32_t id) {
    struct wlr_my_protocol *proto = data;
    struct wl_resource *resource = wl_resource_create(client,
        &my_manager_v1_interface, version, id);
    if (!resource) {
        wl_client_post_no_memory(client);
        return;
    }
    wl_resource_set_implementation(resource, &my_manager_impl, proto, NULL);
    wl_list_insert(&proto->resources, wl_resource_get_link(resource));
}

struct wlr_my_protocol *wlr_my_protocol_create(struct wl_display *display) {
    struct wlr_my_protocol *proto = calloc(1, sizeof(*proto));
    if (!proto) return NULL;

    proto->global = wl_global_create(display, &my_manager_v1_interface,
        1, proto, my_bind);
    if (!proto->global) {
        free(proto);
        return NULL;
    }
    wl_signal_init(&proto->events.destroy);
    wl_list_init(&proto->resources);
    wlr_log(WLR_DEBUG, "my_protocol: created global");
    return proto;
}
```

CI runs a full build matrix with GCC and clang across multiple distros. Always check that
`tinywl` still launches and renders correctly before submitting your MR.

---

## 49.5 Contributing to Quickshell

Quickshell is a QML-based shell scripting toolkit purpose-built for Wayland. It provides a
framework for building bars, overlays, notification popups, and any other shell component
using Qt6 Quick. The codebase is C++ with an extensive QML API surface.

Repository: `https://git.outfoxxed.me/quickshell/quickshell` (primary, Forgejo)
Mirror: `https://github.com/quickshell-mirror/quickshell`

### Building from Source

```bash
# Install dependencies (Arch Linux)
sudo pacman -S qt6-base qt6-declarative qt6-wayland cmake ninja \
    wayland wayland-protocols libpipewire jq

# Clone the primary repo
git clone https://git.outfoxxed.me/quickshell/quickshell
cd quickshell

# Configure with cmake
cmake -B build -G Ninja \
    -DCMAKE_BUILD_TYPE=Debug \
    -DWAYLAND=ON \
    -DPIPEWIRE=ON
ninja -C build

# Run with a test config
./build/quickshell -c /path/to/your/shell.qml
```

### Adding a New Service Module

Quickshell services (battery, network, audio, etc.) live in `src/services/`. To add a new service:

```bash
# Study an existing simple service
ls src/services/
cat src/services/upower/CMakeLists.txt
cat src/services/upower/core.hpp
```

```cmake
# src/services/myservice/CMakeLists.txt
qt_add_library(quickshell-service-myservice STATIC)
qt_add_qml_module(quickshell-service-myservice
    URI Quickshell.Services.MyService
    VERSION 0.1
    SOURCES
        core.hpp
        core.cpp
)
target_link_libraries(quickshell-service-myservice
    PRIVATE Qt6::Core Qt6::Qml quickshell-core
)
install(TARGETS quickshell-service-myservice
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}/quickshell
)
```

```cpp
// src/services/myservice/core.hpp
#pragma once
#include <QObject>
#include <qqmlintegration.h>

class MyService : public QObject {
    Q_OBJECT;
    QML_ELEMENT;
    QML_SINGLETON;

    Q_PROPERTY(QString status READ status NOTIFY statusChanged)

public:
    explicit MyService(QObject* parent = nullptr);
    [[nodiscard]] QString status() const;

signals:
    void statusChanged();

private:
    QString mStatus;
    void refresh();
};
```

```cpp
// src/services/myservice/core.cpp
#include "core.hpp"
#include <QTimer>

MyService::MyService(QObject* parent): QObject(parent) {
    auto* timer = new QTimer(this);
    connect(timer, &QTimer::timeout, this, &MyService::refresh);
    timer->start(5000);
    refresh();
}

QString MyService::status() const { return mStatus; }

void MyService::refresh() {
    // read your data source here
    QString newStatus = "ok";
    if (newStatus != mStatus) {
        mStatus = newStatus;
        emit statusChanged();
    }
}
```

### Documentation Contributions

The Quickshell documentation site is built from source. API docs are generated from Qt's
qdoc toolchain. Contributing corrections to the docs site:

```bash
git clone https://git.outfoxxed.me/quickshell/quickshell-docs
# Edit .md files in docs/ or fix qdoc comments in the main repo
```

---

## 49.6 Contributing to Hyprland

Hyprland is a tiling Wayland compositor with a custom rendering engine, extensive plugin API,
and active development community. It does not use wlroots, having replaced it with its own
`aquamarine` backend library.

Repository: `https://github.com/hyprwm/Hyprland`

### Development Environment

```bash
# Install dependencies (Arch Linux — see official docs for other distros)
sudo pacman -S cmake meson ninja gcc libdrm libinput libxkbcommon \
    wayland wayland-protocols mesa tomlplusplus glm cairo pango \
    hyprutils aquamarine hyprlang hyprcursor

git clone --recursive https://github.com/hyprwm/Hyprland
cd Hyprland
cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=Debug
ninja -C build

# Run Hyprland from a TTY or nested under an existing compositor
HYPRLAND_TRACE=1 ./build/Hyprland > /tmp/hyprland.log 2>&1
```

### Writing a Plugin

Hyprland's plugin API exposes hooks into compositor events:

```cpp
// myplugin.cpp
#include <hyprland/src/plugins/PluginAPI.hpp>

APICREATOR_EXPORT PLUGIN_DESCRIPTION_INFO PLUGIN_INIT(HANDLE handle) {
    return {"MyPlugin", "Does something cool", "1.0", "Your Name"};
}

APICREATOR_EXPORT void PLUGIN_EXIT() {
    // cleanup
}

// Hook into window creation
static SDispatchResult onWindowCreated(std::any data) {
    auto* window = std::any_cast<PHLWINDOW>(data);
    Debug::log(LOG, "Window created: {}", window->m_szTitle);
    return {};
}

APICREATOR_EXPORT PLUGIN_DESCRIPTION_INFO PLUGIN_INIT(HANDLE handle) {
    HyprlandAPI::registerCallbackDynamic(handle,
        "openWindow", [](void*, SCallbackInfo&, std::any data) {
            onWindowCreated(data);
        });
    return {"MyPlugin", "Window creation logger", "1.0", "Your Name"};
}
```

```cmake
# CMakeLists.txt for a Hyprland plugin
cmake_minimum_required(VERSION 3.19)
project(myplugin)
find_package(PkgConfig REQUIRED)
pkg_check_modules(HYPRLAND REQUIRED hyprland)
add_library(myplugin SHARED myplugin.cpp)
target_include_directories(myplugin PRIVATE ${HYPRLAND_INCLUDE_DIRS})
target_link_libraries(myplugin ${HYPRLAND_LIBRARIES})
set_target_properties(myplugin PROPERTIES PREFIX "")
```

Load the plugin at runtime:

```
# In hyprland.conf
plugin = /path/to/myplugin.so
# Or dynamically
hyprctl plugin load /path/to/myplugin.so
```

### Filing Bug Reports

Hyprland logs are essential. Always attach full logs to issues:

```bash
# Collect full compositor log
journalctl --user -b -u hyprland.service > /tmp/hyprland-journal.log
# Or from direct launch:
Hyprland > /tmp/hyprland.log 2>&1

# Collect system info for the report
hyprctl version
hyprctl monitors
hyprctl systeminfo
```

---

## 49.7 Writing and Publishing Quickshell Configs

High-quality public configurations are valuable community resources. They demonstrate
patterns, teach QML techniques, and serve as starting points for others. A well-structured
dotfiles repository with a Quickshell config can gain significant visibility.

### Repository Structure

```
my-dotfiles/
├── .config/
│   ├── quickshell/
│   │   ├── shell.qml          # Entry point
│   │   ├── Bar.qml            # Status bar component
│   │   ├── Notifications.qml  # Notification popup
│   │   ├── Launcher.qml       # App launcher
│   │   └── services/          # Custom service wrappers
│   ├── hypr/
│   │   └── hyprland.conf
│   └── foot/
│       └── foot.ini
├── screenshots/
│   ├── overview.png
│   └── demo.gif
├── install.sh                 # Symlink installer
└── README.md
```

### Capturing Screenshots and Recordings for Showcasing

```bash
# Screenshot the entire compositor output
grim ~/screenshots/desktop.png

# Screenshot a selected region
grim -g "$(slurp)" ~/screenshots/selection.png

# Screen recording with wf-recorder
wf-recorder -o ~/recordings/demo.mp4
# Stop with Ctrl+C

# Convert to GIF for README embeds
ffmpeg -i demo.mp4 -vf "fps=15,scale=1280:-1:flags=lanczos" \
    -c:v gif demo.gif

# Annotated screenshot with satty
grim - | satty --filename -
```

### NixOS Flake for Maximum Portability

```nix
# flake.nix
{
  description = "My Wayland rice";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    quickshell = {
      url = "git+https://git.outfoxxed.me/quickshell/quickshell";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };
  outputs = { nixpkgs, home-manager, quickshell, ... }@inputs: {
    homeConfigurations."youruser@yourmachine" = home-manager.lib.homeManagerConfiguration {
      pkgs = nixpkgs.legacyPackages.x86_64-linux;
      extraSpecialArgs = { inherit inputs; };
      modules = [ ./home.nix ];
    };
  };
}
```

### GitHub Tags for Discoverability

After pushing your dotfiles repository, add these topics in the GitHub repository settings:

```
quickshell  wayland  dotfiles  rice  hyprland  unixporn  ricing
```

Post to r/unixporn with: a link to your repository, a screenshot showing the key visual elements,
and the list of tools used. The community appreciates detailed comments explaining unusual or
clever techniques.

---

## 49.8 Filing Good Bug Reports

A good bug report reduces the work required from the maintainer to zero for reproduction.
The maintainer should be able to read your report and reproduce the bug immediately without
guessing at your configuration, environment, or the exact steps.

### The Minimal Reproduction Technique

Start with your full configuration, then systematically remove sections until the bug
disappears, then re-add the last removed section. The result is a minimal config:

```bash
# Create a minimal sway config for reproduction
cat > /tmp/minimal-sway.conf << 'EOF'
# Minimal sway config for bug reproduction
output * bg #1a1a2e solid_color
input type:keyboard {
    repeat_delay 300
    repeat_rate 50
}
# Only include what is necessary to trigger the bug
exec foot
EOF

sway -c /tmp/minimal-sway.conf
```

### Collecting WAYLAND_DEBUG Logs Cleanly

```bash
# Run the reproducer and capture protocol trace
WAYLAND_DEBUG=1 your-app 2>/tmp/wayland-trace.log

# Trim the log to the relevant window
# Find the timestamp just before the bug occurs, take ±50 lines
grep -n "relevant_interface" /tmp/wayland-trace.log | head -20
# Then extract that range
sed -n '145,195p' /tmp/wayland-trace.log > /tmp/wayland-trace-trimmed.log
```

### Compositor Version and Environment Info

```bash
# Collect complete environment info in one command
cat << 'EOF' > /tmp/collect-env.sh
#!/bin/bash
echo "=== Compositor ===" 
sway --version 2>/dev/null || hyprctl version 2>/dev/null
echo "=== Kernel ===" && uname -r
echo "=== GPU ===" && lspci | grep -i vga
echo "=== Mesa ===" && glxinfo -B 2>/dev/null | grep "OpenGL version"
echo "=== Wayland ===" && pkg-config --modversion wayland-client 2>/dev/null
echo "=== Display Server ===" && echo $WAYLAND_DISPLAY $DISPLAY
EOF
bash /tmp/collect-env.sh
```

---

## 49.9 The Community

Different projects have different primary communication channels. Using the wrong channel
(e.g., posting a wlroots protocol question to the Hyprland Discord) reduces your chance of
getting a useful response and creates noise for people who are not relevant to your question.

| Project / Topic | Channel | URL |
|-----------------|---------|-----|
| Wayland protocol design | #wayland on Libera.Chat | irc.libera.chat |
| Wayland protocol design | Matrix: #wayland:matrix.org | matrix.to/#/#wayland:matrix.org |
| wlroots development | #wlroots on Libera.Chat | irc.libera.chat |
| sway configuration | #sway on Libera.Chat | irc.libera.chat |
| Hyprland all topics | Hyprland Discord | discord.gg/hyprland |
| niri | GitHub Discussions + Matrix | github.com/YaLTeR/niri |
| Quickshell | #quickshell Matrix | outfoxxed.me |
| Ricing showcase | r/unixporn | reddit.com/r/unixporn |
| Hyprland configs | r/hyprland | reddit.com/r/hyprland |
| NixOS Wayland | NixOS Discourse | discourse.nixos.org |
| freedesktop.org | Matrix: #freedesktop | matrix.freedesktop.org |
| Mesa/GPU | Mesa mailing list | mesa-dev@lists.freedesktop.org |

### Contributing Code: Social Etiquette

Before opening a large MR, open an issue or discuss the approach in the chat channel.
Maintainers are more receptive to code they have been consulted on in advance. For
wayland-protocols specifically, discussing your proposal on the mailing list or in the
#wayland IRC channel before writing the protocol XML is strongly recommended.

Always read `CONTRIBUTING.md` and follow its rules precisely. Missing a DCO sign-off line,
using the wrong commit message format, or skipping the test suite are common reasons for
immediate review rejection that have nothing to do with the quality of your code.

```bash
# Add DCO sign-off (required for many freedesktop.org projects)
git commit -s -m "wlr/my-protocol: add initial implementation"

# Verify your commit has the sign-off line
git log --format="%B" HEAD | grep "Signed-off-by:"
```

---

## Troubleshooting

### WAYLAND_DEBUG Produces No Output

If `WAYLAND_DEBUG=1 myapp` produces no Wayland protocol output, the application may be using
the Wayland EGL or Vulkan WSI path directly rather than libwayland-client, or it may be an
X11 application running under XWayland. Verify:

```bash
# Check if the app is actually connecting to Wayland
strace -e trace=openat myapp 2>&1 | grep -E "wayland|wl_"
# Check if it links against libwayland
ldd $(which myapp) | grep wayland
```

### Build Failures in wlroots

```bash
# Missing protocol headers (wayland-protocols version mismatch)
pkg-config --modversion wayland-protocols
# Required: check meson.build for minimum version

# Vulkan shader compilation fails (missing glslang)
which glslangValidator || sudo pacman -S glslang

# Regenerate protocol headers manually
wayland-scanner private-code \
    /usr/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml \
    protocol/xdg-shell-protocol.c
```

### Hyprland Plugin Load Failures

```bash
# Check ABI compatibility (plugin must match Hyprland version exactly)
hyprctl plugin list
# Error: "Plugin ABI mismatch" means rebuild the plugin against current Hyprland headers

# Rebuild with exact Hyprland headers
HYPRLAND_HEADERS=/path/to/hyprland/src cmake -B build ...

# Verify plugin exports the required symbols
nm -D myplugin.so | grep -E "PLUGIN_INIT|PLUGIN_EXIT"
```

### Quickshell QML Errors at Runtime

```bash
# Run with verbose QML debugging
QML_IMPORT_TRACE=1 quickshell -c shell.qml

# Check QML module path includes Quickshell's modules
echo $QML2_IMPORT_PATH
# Should include path where Quickshell installed its QML modules

# List registered QML types
quickshell --list-types 2>/dev/null | grep -i myservice
```

### GitLab CI Failures for freedesktop.org Projects

```bash
# Run the same build locally using Docker (matches CI environment)
docker pull registry.freedesktop.org/wayland/wlroots/ci/arch:latest
docker run -it --rm \
    -v $(pwd):/build \
    -w /build \
    registry.freedesktop.org/wayland/wlroots/ci/arch:latest \
    bash -c "meson setup build && ninja -C build"
```

---

## Summary

Contributing to the Wayland ecosystem spans a broad skill spectrum. The highest-leverage entry
points are detailed bug reports with protocol traces, documentation improvements, and protocol
testing across compositors. Code contributions to wlroots and wayland-protocols have the
broadest downstream impact, while Hyprland plugins and Quickshell service modules offer
contained, high-visibility opportunities for application-level contributors. Always engage
the community before large changes and follow each project's contribution guidelines precisely.

See Ch 50 for writing custom Wayland protocol extensions from scratch. See Ch 46 for wlroots
compositor development internals. See Ch 12 for session startup and WAYLAND_DISPLAY management.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
