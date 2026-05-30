# Chapter 89 — Hyprland Plugins and hyprpm

## Contents

- [Overview](#overview)
- [89.1 hyprpm — Plugin Manager](#891-hyprpm-plugin-manager)
  - [Loading plugins in hyprland.conf](#loading-plugins-in-hyprlandconf)
- [89.2 Popular Plugins](#892-popular-plugins)
  - [hy3 — Manual tiling layout (i3/AwesomeWM style)](#hy3-manual-tiling-layout-i3awesomewm-style)
  - [hyprscroller — i3-like scrolling columns](#hyprscroller-i3-like-scrolling-columns)
  - [hyprexpo — Workspace overview (Exposé)](#hyprexpo-workspace-overview-exposé)
  - [hyprspace — Workspace switcher overlay](#hyprspace-workspace-switcher-overlay)
  - [hyprtrails — Window movement trails](#hyprtrails-window-movement-trails)
  - [hyprbars — Window title bars (if you want them)](#hyprbars-window-title-bars-if-you-want-them)
- [89.3 Writing a Hyprland Plugin](#893-writing-a-hyprland-plugin)
  - [Project structure](#project-structure)
  - [CMakeLists.txt](#cmakeliststxt)
  - [main.cpp — minimal plugin skeleton](#maincpp-minimal-plugin-skeleton)
  - [Hooking into window events](#hooking-into-window-events)
  - [Available hook events](#available-hook-events)
  - [Adding a custom dispatcher](#adding-a-custom-dispatcher)
  - [Adding custom config options](#adding-custom-config-options)
  - [Building and testing](#building-and-testing)
- [89.4 Plugin Development Workflow](#894-plugin-development-workflow)
- [89.5 Plugin Distribution with hyprpm](#895-plugin-distribution-with-hyprpm)

---


## Overview

Hyprland's plugin system lets C++ code hook directly into the compositor:
intercept window events, override layout algorithms, add new dispatchers, and
draw custom decorations. `hyprpm` is the package manager. This chapter covers
installing plugins, using the most popular ones, and writing your own.

---

## 89.1 hyprpm — Plugin Manager

`hyprpm` is bundled with Hyprland (available as `hyprpm` in PATH).

```bash
# Add a plugin repository (GitHub URL)
hyprpm add https://github.com/outfoxxed/hy3
hyprpm add https://github.com/dawsers/hyprscroller
hyprpm add https://github.com/KZDKM/hyprspace

# List available plugins from all added repos
hyprpm list

# Install a plugin
hyprpm enable hy3
hyprpm enable hyprscroller

# Load enabled plugins into the running compositor (required after enable/disable)
hyprpm reload

# Update all plugins
hyprpm update

# Disable a plugin (keeps it installed)
hyprpm disable hy3

# Remove a plugin entirely
hyprpm remove hy3
```

Plugins are built against the **exact Hyprland headers** installed on your
system. `hyprpm update` rebuilds after a Hyprland upgrade.

### Loading plugins in hyprland.conf

```conf
# Load via hyprpm (recommended):
# Run 'hyprpm reload' after enabling plugins, or add to autostart so plugins
# load automatically on compositor startup:
exec-once = hyprpm reload -n

# Or load manually:
plugin = /home/user/.local/share/hyprpm/repos/hy3/hy3.so
```

---

## 89.2 Popular Plugins

### hy3 — Manual tiling layout (i3/AwesomeWM style)

hy3 replaces Hyprland's dwindle/master with a manual tiling layout where you
explicitly split containers horizontally or vertically.

```bash
hyprpm add https://github.com/outfoxxed/hy3
hyprpm enable hy3
```

```conf
# hyprland.conf
plugin:hy3:no_gaps_when_only = 1
plugin:hy3:tab_first_window = 1

# Switch to hy3 layout
general {
    layout = hy3
}

# hy3-specific binds
bind = SUPER, h, hy3:makegroup, h          # split horizontal
bind = SUPER, v, hy3:makegroup, v          # split vertical
bind = SUPER, t, hy3:makegroup, tab        # tabbed group
bind = SUPER, e, hy3:changegroup, opposite # toggle split direction
bind = SUPER, a, hy3:movetoworkspace, +1   # move group to next workspace
bind = SUPER SHIFT, h, hy3:movefocus, l
bind = SUPER SHIFT, l, hy3:movefocus, r
```

### hyprscroller — i3-like scrolling columns

Windows arrange in columns; navigate and resize horizontally:

```bash
hyprpm add https://github.com/dawsers/hyprscroller
hyprpm enable hyprscroller
```

```conf
general { layout = scroller }

plugin:scroller:column_default_width = onehalf
plugin:scroller:focus_wrap = false

bind = SUPER, left,  scroller:movefocus, l
bind = SUPER, right, scroller:movefocus, r
bind = SUPER SHIFT, left,  scroller:movewindow, l
bind = SUPER SHIFT, right, scroller:movewindow, r
bind = SUPER, bracketleft,  scroller:setwidth, onethird
bind = SUPER, bracketright, scroller:setwidth, twothirds
```

### hyprexpo — Workspace overview (Exposé)

Shows a grid of all workspaces like macOS Exposé / GNOME Activities:

```bash
hyprpm add https://github.com/hyprwm/hyprland-plugins
hyprpm enable hyprexpo
```

```conf
plugin:hyprexpo:columns = 3
plugin:hyprexpo:gap_size = 5
plugin:hyprexpo:bg_col = rgb(111111)
plugin:hyprexpo:workspace_method = center current  # or: first 1

bind = SUPER, grave, hyprexpo:expo, toggle
```

### hyprspace — Workspace switcher overlay

A different workspace overview with animation and app search:

```bash
hyprpm add https://github.com/KZDKM/hyprspace
hyprpm enable hyprspace
```

```conf
bind = SUPER, tab, overview:toggle
```

### hyprtrails — Window movement trails

Draws ghost trails when windows move — a pure visual effect:

```bash
hyprpm add https://github.com/hyprwm/hyprland-plugins
hyprpm enable hyprtrails
```

```conf
plugin:hyprtrails:color = rgba(89b4faaa)
```

### hyprbars — Window title bars (if you want them)

Adds configurable title bars to windows:

```bash
hyprpm add https://github.com/hyprwm/hyprland-plugins
hyprpm enable hyprbars
```

```conf
plugin:hyprbars:bar_height = 20
plugin:hyprbars:bar_color = rgb(1e1e2e)
plugin:hyprbars:col.text = rgb(cdd6f4)
plugin:hyprbars:bar_text_size = 11
plugin:hyprbars:bar_text_font = JetBrainsMono Nerd Font

plugin:hyprbars:buttons {
    button_size = 11
    col.button_close = rgb(f38ba8)
    col.button_minimize = rgb(fab387)
}
```

---

## 89.3 Writing a Hyprland Plugin

Hyprland plugins are shared libraries loaded at runtime. They use the
Hyprland plugin API exposed through `<hyprland/src/includes.hpp>` and the
plugin headers.

### Project structure

```
my-plugin/
├── CMakeLists.txt
├── main.cpp
└── include/
    └── globals.hpp
```

### CMakeLists.txt

```cmake
cmake_minimum_required(VERSION 3.19)
project(my-plugin)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

find_package(PkgConfig REQUIRED)
pkg_check_modules(HYPRLAND REQUIRED hyprland)

add_library(my-plugin SHARED main.cpp)

target_include_directories(my-plugin PRIVATE
    ${HYPRLAND_INCLUDE_DIRS}
    /usr/include/hyprland
    /usr/include/hyprland/protocols
    /usr/include/hyprland/wlr
)

target_compile_options(my-plugin PRIVATE ${HYPRLAND_CFLAGS_OTHER})
```

### main.cpp — minimal plugin skeleton

```cpp
#include <hyprland/src/plugins/PluginAPI.hpp>
#include <hyprland/src/desktop/DesktopTypes.hpp>

inline HANDLE PHANDLE = nullptr;

// Required: Hyprland uses this to verify the API version the plugin was compiled against
APICALL EXPORT std::string PLUGIN_API_VERSION() {
    return HYPRLAND_API_VERSION;  // Do NOT change this
}

// Called when the plugin loads
APICALL EXPORT PLUGIN_DESCRIPTION_INFO PLUGIN_INIT(HANDLE handle) {
    PHANDLE = handle;

    // Always verify headers match the running Hyprland build
    if (__hyprland_api_get_hash() != __hyprland_api_get_client_hash()) {
        HyprlandAPI::addNotification(handle, "[my-plugin] Mismatched headers! Plugin will not load.", CColor{1,0,0,1}, 5000);
        throw std::runtime_error("Mismatched headers");
    }

    return {"My Plugin", "Description", "Author", "1.0"};
}

// Called when Hyprland unloads the plugin
APICALL EXPORT void PLUGIN_EXIT() {
    // cleanup
}
```

### Hooking into window events

```cpp
#include <hyprland/src/plugins/PluginAPI.hpp>
#include <hyprland/src/managers/EventManager.hpp>

HANDLE g_pPluginHandle = nullptr;

// Handler called when a window opens
void onWindowOpen(void* self, SCallbackInfo& info, std::any data) {
    auto pWindow = std::any_cast<PHLWINDOW>(data);
    if (!pWindow) return;

    // Example: auto-float windows smaller than 400px
    if (pWindow->m_vReportedSize.x < 400) {
        pWindow->m_bIsFloating = true;
    }
}

APICALL EXPORT PLUGIN_DESCRIPTION_INFO PLUGIN_INIT(HANDLE handle) {
    g_pPluginHandle = handle;

    // Register event hook
    HyprlandAPI::registerCallbackDynamic(
        handle,
        "openWindow",
        [&](void* self, SCallbackInfo& info, std::any data) {
            onWindowOpen(self, info, data);
        }
    );

    return {"Auto-float Small Windows", "Float windows < 400px", "me", "1.0"};
}

APICALL EXPORT void PLUGIN_EXIT() {
    // Hooks are automatically unregistered
}
```

### Available hook events

| Event | Data type | Description |
|-------|-----------|-------------|
| `openWindow` | `PHLWINDOW` | Window created |
| `closeWindow` | `PHLWINDOW` | Window closed |
| `moveWindow` | `PHLWINDOW` | Window moved |
| `windowUpdateRules` | `PHLWINDOW` | Window rules applied |
| `focusedMon` | `PHLMONITOR` | Monitor focus changed |
| `monitorAdded` | `PHLMONITOR` | Monitor connected |
| `render` | `eRenderStage` | Before/during/after render |
| `keyPress` | `IKeyboard*` | Key pressed |
| `mouseMove` | `Vector2D` | Mouse moved |

### Adding a custom dispatcher

```cpp
void myDispatcher(std::string args) {
    // args is the string after the dispatcher name in bind = ...
    HyprlandAPI::addNotification(
        g_pPluginHandle,
        "Plugin action: " + args,
        CColor{0.2f, 0.8f, 0.4f, 1.0f},
        3000  // ms
    );
}

APICALL EXPORT PLUGIN_DESCRIPTION_INFO PLUGIN_INIT(HANDLE handle) {
    g_pPluginHandle = handle;

    HyprlandAPI::addDispatcher(handle, "myplugin:action", myDispatcher);

    return {"My Plugin", "Demo dispatcher", "me", "1.0"};
}
```

Use in config: `bind = SUPER, X, myplugin:action, hello`

### Adding custom config options

```cpp
APICALL EXPORT PLUGIN_DESCRIPTION_INFO PLUGIN_INIT(HANDLE handle) {
    g_pPluginHandle = handle;

    // Register config variables
    HyprlandAPI::addConfigValue(handle, "plugin:myplugin:opacity", SConfigValue{.floatValue = 0.9f});
    HyprlandAPI::addConfigValue(handle, "plugin:myplugin:color",   SConfigValue{.intValue = 0xFF89b4fa});

    return {"My Plugin", "Config demo", "me", "1.0"};
}

// Reading config values at runtime:
float opacity = HyprlandAPI::getConfigValue(g_pPluginHandle, "plugin:myplugin:opacity")->floatValue;
```

### Building and testing

```bash
mkdir build && cd build
cmake ..
make -j$(nproc)

# Load for testing
hyprctl plugin load $(pwd)/libmy-plugin.so

# Unload
hyprctl plugin unload $(pwd)/libmy-plugin.so
```

---

## 89.4 Plugin Development Workflow

```bash
# Watch for rebuild trigger
while inotifywait -e modify ../main.cpp; do
  make -j$(nproc) && \
    hyprctl plugin unload $(pwd)/libmy-plugin.so && \
    hyprctl plugin load $(pwd)/libmy-plugin.so && \
    echo "Reloaded"
done
```

Use `hyprctl notify` for in-compositor feedback during development:
```cpp
HyprlandAPI::addNotification(handle, "Plugin loaded", CColor{0,1,0,1}, 2000);
```

---

## 89.5 Plugin Distribution with hyprpm

To distribute a plugin via hyprpm, create a `hyprpm.toml` at the repo root:

```toml
[repository]
name = "my-plugin"
authors = ["yourname"]
commit_pins = [
    # Each entry is [hyprland_commit_hash, plugin_commit_hash]
    ["<hyprland-commit-hash>", "<plugin-commit-hash>"]
]
```

Users then: `hyprpm add https://github.com/you/my-plugin`

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
