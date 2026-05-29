# Chapter 15 — Quickshell Architecture and Philosophy

Quickshell represents the current state of the art in Wayland desktop shell development. Written
by outfoxxed, it emerged around 2024 as a response to the limitations of every prior shell
framework. This chapter provides the deep architectural understanding you need before writing a
single line of QML — how the engine works, why design decisions were made the way they were, and
what the complete module ecosystem looks like. Subsequent chapters build on this foundation.

> **See also:** Ch 16 for your first working shell, Ch 17 for multi-monitor layouts, Ch 53 for
> session startup integration, Ch 54 for systemd service unit wrappers.

---

## 15.1 The Shell Framework Landscape

A "shell framework" is not the same thing as a bar program or a widget toolkit. A bar program
(Waybar, lemonbar, i3bar) presents a single, narrow surface populated with modules defined
entirely in configuration files. You choose from a fixed list of modules and tweak colors.
A widget toolkit (GTK, Qt, Dear ImGui) gives you primitives — windows, buttons, layouts — but
nothing specific to desktop integration. A shell framework sits between these: it wraps desktop
protocols (layer shell, D-Bus, compositor IPC) behind a high-level API and provides a reactive
programming model that makes it practical to describe complex, stateful UIs declaratively.

Understanding where Quickshell fits requires understanding what came before it. On X11, the
canonical tools were xmobar (Haskell, text-only, config-driven) and polybar (C++, config-driven,
moderate programmability via IPC scripts). Both are X11-only in any meaningful sense; polybar
has incomplete XDG output support and no layer-shell awareness. Their design assumption is a
single monitor with a top-level configuration file — they were never designed for dynamic
reconfiguration, multiple outputs with per-output layouts, or protocol-level integration.

The first generation of Wayland-aware shell frameworks arrived with eww (Elkowar's Wacky
Widgets). eww introduced a custom declarative language called Yuck (S-expression syntax) and
SCSS styling, running on GTK. Its reactive model is based on polling shell scripts and listening
to file changes. eww works, and real desktops have been built with it, but its architecture
exposes its seams under load: GTK theming complexity, the impedance mismatch between Yuck and
actual programming constructs, limited IPC, and the polling-based data model create friction
for anything beyond a status bar. eww does support layer shell and basic window management
constructs, which was a significant step forward.

AGS (Aylur's GTK Shell), later refactored into the Astal framework, moved the scripting
language to TypeScript over GJS (GNOME's JavaScript/SpiderMonkey runtime). This gave shell
authors a proper type system and the entire npm ecosystem in theory. In practice, GJS has
rough edges: garbage collection pauses, limited GTK4 support in older versions, and the
JavaScript-to-GObject bridge adds overhead and awkwardness. Astal has since restructured into
a library of independent C widgets that can be consumed from multiple language bindings
(Python, Lua, TypeScript), which is a cleaner architecture, but it remains GTK-based and
inherits GTK's rendering pipeline and theming complexity.

Waybar is not a shell framework in the above sense — it is a bar program that happens to be
highly configurable. Its module system is fixed. You can inject custom content via the `custom`
module executing shell scripts, but you cannot add new protocol integrations, cannot build
overlay windows or popups that respond to compositor events, and cannot implement a lockscreen
or notification daemon within Waybar. Waybar is excellent for its intended use case, but that
use case is narrower than what Quickshell targets.

| Framework | Language | Rendering | Layer Shell | Hot Reload | Type Safety | Wayland-Native |
|-----------|----------|-----------|-------------|------------|-------------|----------------|
| eww | Yuck/SCSS | GTK | Yes | Partial | No | Partial |
| AGS/Astal | TypeScript | GTK | Yes | Yes | Yes (TS) | Partial |
| Waybar | JSON config | GTK | Yes | No | No | Yes |
| Quickshell | QML/JS | Qt/OpenGL | Yes (native) | Yes | Yes (QML) | Yes (full) |

---

## 15.2 Why Quickshell Wins for Serious Ricing

QML (Qt Meta Language / Qt Modeling Language) is a declarative language designed by Qt for
describing user interfaces. It has been shipping in production in embedded systems, automotive
infotainment, and mobile applications since Qt 4.7 (2010). This longevity matters: QML is
not an experimental language. It has a well-specified type system, a JavaScript engine
(V8 or QtJSC depending on build), a layout engine, an animation framework, and full access
to the underlying Qt C++ API. The Qt Company backs it with paid engineering staff and a
long-term commitment to API stability.

The LSP (Language Server Protocol) support for QML is provided by `qmlls`, the official
Qt language server. Combined with `clangd` for any C++ backends, you get real autocomplete,
jump-to-definition, type checking, and hover documentation in any LSP-enabled editor (Neovim,
VSCode, Helix, Emacs via eglot). This changes the development experience dramatically compared
to writing Yuck or plain shell scripts. When you type `Quickshell.Wayland.`, your editor shows
you every available type with its properties. Errors in property bindings are flagged at
edit time, not at runtime.

Hot reload is not merely a convenience — it changes how you work. Quickshell watches your
QML files for changes and reloads modified components in place. For a status bar this means
you edit your clock format and see it update immediately. For a complex panel with state
(current workspaces, notification queue) the runtime attempts to preserve state across
reloads where possible. This tightens the feedback loop from minutes (stop shell, edit,
restart, observe) to seconds (edit, save, observe). The combination of hot reload and
LSP-backed editing makes iterative shell development feel closer to web frontend work than
traditional sysconfig.

Qt's module ecosystem provides capabilities that would require separate daemons or D-Bus
services in GTK-based frameworks. Network requests use `QtNetwork` directly in QML — no
curl subprocess needed. Animations use Qt's animation framework with easing curves, springs,
and sequencing. The QtMultimedia module gives you audio playback. The QtBluetooth module
exposes Bluetooth device management. These are not third-party bindings; they are first-class
Qt modules available in QML via `import Qt*`. For complex shells that want animated
transitions, network-fetched widgets (weather, calendar), or media control with cover art,
this matters.

Multimonitor handling is designed in from the start, not bolted on. The `Quickshell` singleton
exposes a `screens` list that updates dynamically as monitors are connected or disconnected.
A `ShellRoot` with `screen` bound to a specific entry in that list creates a surface on that
monitor. You can iterate over all screens with a `Variants` or `Repeater` to spawn per-screen
surfaces automatically. Contrast this with Waybar's `output` configuration key, which requires
listing monitors by name in config — if you plug in a new monitor, you restart Waybar.

Wayland protocol integration is native, not wrapped. Quickshell implements `wlr-layer-shell-unstable-v1`
directly; it does not call into a separate `wlr-randr` or `wl-clipboard` subprocess. The
`Quickshell.Wayland` namespace includes direct bindings to `wlr-screencopy`, `ext-session-lock`,
and `wlr-foreign-toplevel-management`. These are zero-copy (where the protocol allows) and
synchronous with the compositor's event loop.

---

## 15.3 Architecture Deep Dive

Quickshell's process model is: one process, one QML engine, multiple Wayland surfaces. There
is no plugin subprocess model and no D-Bus activation of sub-components. Everything runs in
the main process under Qt's event loop. This is both a strength and a constraint: a crash
anywhere in your QML terminates the whole shell, but inter-component communication is just
property binding — no IPC overhead.

```
quickshell process
├── Qt event loop (main thread)
│   ├── QML engine (V8/QtJSC)
│   │   ├── shell.qml (root)
│   │   │   ├── Bar.qml instances (one per screen)
│   │   │   ├── NotificationOverlay.qml
│   │   │   └── Lockscreen.qml
│   │   └── Singleton objects (services, state)
│   ├── Wayland connection (fd polling via Qt event loop)
│   │   ├── wl_compositor, wl_shm, zwlr_layer_shell_v1
│   │   ├── zwlr_foreign_toplevel_manager_v1
│   │   └── ext_session_lock_v1
│   └── D-Bus connections (org.freedesktop.Notifications, org.mpris.*, etc.)
└── PipeWire connection (pw_main_loop integrated via Qt socket notifier)
```

The QML engine evaluates your `.qml` files lazily: `shell.qml` is parsed first, then
components referenced by it. Types defined in the same directory are available without
explicit import statements — Quickshell's type loader picks up all `.qml` files in the
config directory automatically. Files in subdirectories require either an `import "./subdir"`
statement or a `qmldir` file.

The `Quickshell` singleton is the root object that Quickshell registers before evaluating
your `shell.qml`. It exposes:

- `Quickshell.screens` — list of `QuickshellScreen` objects, one per connected output
- `Quickshell.reload()` — trigger a hot reload programmatically
- `Quickshell.quit()` — exit the shell
- `Quickshell.configPath` — absolute path to the config directory

A typical `shell.qml` entry point looks like this:

```qml
// ~/.config/quickshell/shell.qml
import Quickshell
import Quickshell.Wayland

ShellRoot {
    // Spawn a bar on every screen
    Variants {
        model: Quickshell.screens
        delegate: Bar { screen: modelData }
    }

    // Single notification overlay (compositor decides placement)
    NotificationOverlay {}

    // Lockscreen (hidden until activated)
    Lockscreen { id: lockscreen }

    // IPC handler for external scripts
    IpcHandler {
        target: "shell"
        function reload() { Quickshell.reload() }
        function lock()   { lockscreen.lock() }
    }
}
```

Property bindings are the reactive glue of QML. When you write:

```qml
Text {
    text: "CPU: " + SystemStats.cpuPercent.toFixed(1) + "%"
    color: SystemStats.cpuPercent > 90 ? "#ff5555" : "#cdd6f4"
}
```

QML's binding engine registers that `text` and `color` depend on `SystemStats.cpuPercent`.
When that property changes, both bindings re-evaluate automatically. There is no manual
subscription, no `addEventListener`, no `useEffect` hook — the dependency graph is constructed
implicitly at bind time. This is the core reason QML is so productive for reactive UIs.

JavaScript functions defined with `function` break reactivity — they are imperative. Use
property bindings and computed properties wherever possible. Reserve JavaScript functions for
event handlers (button clicks, timer callbacks) and side effects. A common beginner mistake
is replacing a property binding with a function that imperatively updates a property; this
loses reactivity and forces you to manually trigger updates.

Singletons (types annotated with `pragma Singleton`) are global objects instantiated once.
Quickshell provides many built-in singletons (the `Quickshell` object itself, service
singletons like `Notifications`, `SystemTray`, `MprisController`). You can define your own:

```qml
// ~/.config/quickshell/services/AppState.qml
pragma Singleton
import QtQuick

QtObject {
    property int activeWorkspace: 1
    property bool doNotDisturb: false
    property string currentLayout: "us"
}
```

Then reference it from any other QML file as `AppState.activeWorkspace` after adding the
singleton to your imports (or placing it in the config root so it is auto-discovered).

---

## 15.4 The Config Directory Layout

The config directory is `~/.config/quickshell/` by default. You can override this with the
`-c` / `--config` flag to run named configurations:

```bash
# Run the default config
quickshell

# Run a named config (looks for ~/.config/quickshell/myconfig/shell.qml)
quickshell -c myconfig

# Run an explicit path
quickshell --config /path/to/my/shell.qml
```

A well-organized config directory for a moderately complex shell:

```
~/.config/quickshell/
├── shell.qml                  ← entry point
├── qmldir                     ← optional: explicit type registrations
├── bar/
│   ├── Bar.qml                ← top-level bar component
│   ├── WorkspaceButtons.qml
│   ├── ClockWidget.qml
│   ├── SystemTrayWidget.qml
│   └── qmldir                 ← makes bar/ importable as a module
├── notifications/
│   ├── NotificationOverlay.qml
│   ├── NotificationPopup.qml
│   └── qmldir
├── lockscreen/
│   ├── Lockscreen.qml
│   ├── PasswordField.qml
│   └── qmldir
├── services/
│   ├── AppState.qml           ← pragma Singleton
│   ├── NetworkMonitor.qml     ← pragma Singleton
│   └── qmldir
└── theme/
    ├── Theme.qml              ← pragma Singleton, color/font constants
    └── qmldir
```

The `qmldir` file in each subdirectory tells the QML engine which types are exported and
optionally their version numbers. A minimal `qmldir`:

```
# bar/qmldir
module bar
Bar 1.0 Bar.qml
WorkspaceButtons 1.0 WorkspaceButtons.qml
ClockWidget 1.0 ClockWidget.qml
SystemTrayWidget 1.0 SystemTrayWidget.qml
```

With this layout, `shell.qml` imports sub-modules cleanly:

```qml
import Quickshell
import "bar"
import "notifications"
import "lockscreen"
import "services"
import "theme"

ShellRoot {
    Variants {
        model: Quickshell.screens
        delegate: Bar { screen: modelData }
    }
    NotificationOverlay {}
    Lockscreen {}
}
```

---

## 15.5 Module Namespace Map

Quickshell's QML API is organized into namespaces that map cleanly to functional areas.
Knowing which namespace provides which capability is essential before reading the documentation.

| Namespace | Import Statement | Purpose |
|-----------|-----------------|---------|
| `Quickshell` | `import Quickshell` | Core: ShellRoot, PanelWindow, Variants, IpcHandler, singletons |
| `Quickshell.Io` | `import Quickshell.Io` | Process execution, Unix sockets, file I/O, JSON/CSV parsers |
| `Quickshell.Wayland` | `import Quickshell.Wayland` | Layer shell, WlrLayershell, screencopy, session lock, toplevels |
| `Quickshell.Hyprland` | `import Quickshell.Hyprland` | Hyprland IPC: monitors, workspaces, windows, events |
| `Quickshell.I3` | `import Quickshell.I3` | i3/Sway IPC: workspaces, nodes |
| `Quickshell.Services.Notifications` | `import Quickshell.Services.Notifications` | D-Bus org.freedesktop.Notifications server |
| `Quickshell.Services.Mpris` | `import Quickshell.Services.Mpris` | MPRIS2 media player control |
| `Quickshell.Services.Pipewire` | `import Quickshell.Services.Pipewire` | PipeWire audio nodes and links |
| `Quickshell.Services.UPower` | `import Quickshell.Services.UPower` | Battery status, power profiles |
| `Quickshell.Services.SystemTray` | `import Quickshell.Services.SystemTray` | StatusNotifierItem system tray |
| `Quickshell.Services.Pam` | `import Quickshell.Services.Pam` | PAM authentication (for lockscreen) |
| `Quickshell.Services.Greetd` | `import Quickshell.Services.Greetd` | greetd login greeter protocol |
| `Quickshell.Widgets` | `import Quickshell.Widgets` | Reusable components (clock formatter, marquee, etc.) |
| `Quickshell.DBusMenu` | `import Quickshell.DBusMenu` | com.canonical.dbusmenu for tray context menus |

The `Quickshell.Io` namespace deserves special attention. Running external processes in a
Quickshell shell is done via `Process` (one-shot), `PersistentProcess` (daemon), or
`Socket` (Unix domain socket client). These are the escape hatches for integrating anything
not natively supported:

```qml
import Quickshell.Io

// One-shot process execution
Process {
    id: brightnessQuery
    command: ["brightnessctl", "get"]
    running: true  // run immediately

    stdout: SplitParser {
        onRead: (line) => { brightnessValue = parseInt(line) }
    }
}

// Persistent socket connection (e.g., to a custom daemon)
Socket {
    id: myDaemon
    path: "/run/user/1000/mydaemon.sock"
    connected: true

    parser: SplitParser {
        splitMarker: "\n"
        onRead: (line) => handleDaemonMessage(JSON.parse(line))
    }

    function sendCommand(cmd) {
        myDaemon.write(JSON.stringify(cmd) + "\n")
    }
}
```

---

## 15.6 Installation and Building

### Distribution Packages

The fastest path to a running Quickshell is a distro package. Availability as of mid-2026:

| Distribution | Package | Command |
|-------------|---------|---------|
| Arch Linux | `quickshell-git` (AUR) | `paru -S quickshell-git` or `yay -S quickshell-git` |
| Arch Linux | `quickshell` (AUR, stable) | `paru -S quickshell` |
| NixOS | flake input | See NixOS section below |
| Void Linux | In progress (check xbps-src) | — |
| Other | Build from source | See below |

For Arch, the AUR `quickshell-git` package tracks the `main` branch and rebuilds against
current Qt6 packages. This is the recommended path for most Arch users:

```bash
# With paru
paru -S quickshell-git

# With yay
yay -S quickshell-git

# Or manually from AUR
git clone https://aur.archlinux.org/quickshell-git.git
cd quickshell-git
makepkg -si
```

### NixOS Flake

Quickshell provides an official Nix flake. Add it to your system flake:

```nix
# flake.nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    quickshell = {
      url = "github:quickshell-mirror/quickshell";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, quickshell, ... }: {
    nixosConfigurations.mymachine = nixpkgs.lib.nixosSystem {
      modules = [
        ({ pkgs, ... }: {
          environment.systemPackages = [
            quickshell.packages.${pkgs.system}.default
          ];
        })
      ];
    };
  };
}
```

For home-manager integration:

```nix
# home.nix
{ inputs, pkgs, ... }: {
  home.packages = [ inputs.quickshell.packages.${pkgs.system}.default ];

  # Optional: manage the config via home-manager
  xdg.configFile."quickshell" = {
    source = ./quickshell-config;
    recursive = true;
  };
}
```

### Building from Source

Building from source requires Qt6 development headers and CMake. On Arch:

```bash
# Install build dependencies
sudo pacman -S qt6-base qt6-declarative qt6-wayland qt6-svg \
               qt6-5compat cmake ninja pkg-config \
               wayland-protocols wayland pipewire

# Optional modules (enable more namespaces)
sudo pacman -S qt6-bluetooth qt6-networkauth

# Clone and build
git clone https://github.com/quickshell-mirror/quickshell.git
cd quickshell
mkdir build && cd build

# Configure — adjust feature flags as needed
cmake .. \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=/usr \
  -GNinja \
  -DQUICKSHELL_WAYLAND_ENABLE=ON \
  -DQUICKSHELL_PIPEWIRE_ENABLE=ON \
  -DQUICKSHELL_HYPRLAND_ENABLE=ON \
  -DQUICKSHELL_I3_ENABLE=ON \
  -DQUICKSHELL_NOTIFICATIONS_ENABLE=ON \
  -DQUICKSHELL_MPRIS_ENABLE=ON

ninja
sudo ninja install
```

Feature flags available at configure time:

| CMake Flag | Default | Description |
|------------|---------|-------------|
| `QUICKSHELL_WAYLAND_ENABLE` | ON | Wayland layer shell, screencopy, session lock |
| `QUICKSHELL_PIPEWIRE_ENABLE` | ON | PipeWire audio integration |
| `QUICKSHELL_HYPRLAND_ENABLE` | ON | Hyprland IPC |
| `QUICKSHELL_I3_ENABLE` | ON | i3/Sway IPC |
| `QUICKSHELL_NOTIFICATIONS_ENABLE` | ON | D-Bus notification server |
| `QUICKSHELL_MPRIS_ENABLE` | ON | MPRIS2 media player |
| `QUICKSHELL_PAM_ENABLE` | ON | PAM authentication |
| `QUICKSHELL_GREETD_ENABLE` | OFF | greetd greeter (enable for login screens) |

### Runtime Dependencies

Once installed, Quickshell needs the following at runtime:

```bash
# Core runtime (must be present)
qt6-base        # QCoreApplication, Qt event loop
qt6-declarative # QML engine
qt6-wayland     # Qt Wayland platform plugin

# For visual rendering
qt6-svg         # SVG icon rendering
qt6-5compat     # QRegularExpression and other compat APIs

# For services (only needed if you use those namespaces)
pipewire        # Quickshell.Services.Pipewire
libpipewire     # PipeWire client library
```

Verify the Qt Wayland platform plugin is loading correctly:

```bash
QT_QPA_PLATFORM=wayland quickshell --version
# Should print version without "Could not connect to display" error
```

---

## 15.7 The QML Language in 5 Minutes

If you are new to QML, this section provides enough background to read Quickshell QML configs
without confusion. QML files define object trees. Each file describes one root object:

```qml
import QtQuick        // imports the QtQuick module
import Quickshell     // imports Quickshell types

// Root object type
Rectangle {
    id: root          // unique id for referencing this object
    width: 300
    height: 40
    color: "#1e1e2e"  // property assignment

    // Child object
    Text {
        id: label
        anchors.centerIn: parent  // layout via anchors
        text: "Hello, shell"
        color: "#cdd6f4"
        font.pixelSize: 14
    }

    // Property binding — updates automatically when width changes
    property real halfWidth: width / 2

    // Signal handler
    MouseArea {
        anchors.fill: parent
        onClicked: console.log("clicked at", mouse.x, mouse.y)
    }
}
```

QML supports JavaScript expressions anywhere a property value is expected. Conditional
properties, ternary expressions, and function calls all work:

```qml
Rectangle {
    color: isActive ? "#89b4fa" : "#313244"
    opacity: visible ? 1.0 : 0.0
    width: Math.max(minWidth, contentWidth + 2 * padding)
}
```

Signals are declared with `signal name(type param)` and connected with `onName: { ... }`.
The built-in `Component.onCompleted` signal fires when a component finishes loading:

```qml
Item {
    Component.onCompleted: {
        console.log("Component loaded, screen:", screen.name)
        initializeServices()
    }
}
```

Repeaters and `Variants` create multiple instances of a delegate from a model:

```qml
// Variants: Quickshell's model type for typed lists (e.g., screens, workspaces)
Variants {
    model: Quickshell.screens
    delegate: PanelWindow {
        required property var modelData
        screen: modelData
        // ...
    }
}

// Repeater: standard QML, works with arrays and ListModel
Repeater {
    model: ["cpu", "ram", "net", "disk"]
    delegate: StatWidget { label: modelData }
}
```

---

## 15.8 Community and Resources

The Quickshell ecosystem has concentrated around a few high-quality resources. The official
documentation at `https://quickshell.org/docs/` is comprehensive and includes API reference,
type documentation with property listings, and tutorial articles. The documentation is
generated from the source, so it always reflects the current `main` branch.

DeepWiki at `https://deepwiki.com/quickshell-mirror/quickshell` provides an AI-assisted
wiki of the Quickshell source code, useful for understanding implementation details or
internal APIs not yet formally documented. It is particularly useful when you need to
understand how a specific protocol binding works at the C++ level.

The Discord server (linked from the Quickshell website) and Matrix room are the primary
support channels. The community is small but technically sophisticated. Before asking,
search the `#showcase` channel — most common shell patterns have been shared there with
source code. The author (outfoxxed) is active and responsive to bug reports filed on
the GitHub repository.

Notable reference configurations worth studying:

| Config | Author | URL | Notable Features |
|--------|--------|-----|-----------------|
| dots-hyprland | end_4 | github.com/end-4/dots-hyprland | AI assistant integration, complex animations |
| outfoxxed's dotfiles | outfoxxed | github.com/outfoxxed/dotfiles | Reference implementation, idiomatic patterns |
| illogical-impulse | end_4 | github.com/end-4/dots-hyprland (v5+) | Full-featured, production-quality shell |

When reading community configs, pay attention to how they structure singletons, handle
per-screen state, and organize the file hierarchy. Patterns that appear in multiple
independent configs are usually the idiomatic approach for a given problem.

---

## 15.9 Troubleshooting

### Quickshell fails to start: "Could not connect to display"

This means the Qt Wayland platform plugin is not being selected. Ensure you are running under
a Wayland compositor and that `WAYLAND_DISPLAY` is set:

```bash
echo $WAYLAND_DISPLAY  # should print e.g. "wayland-1"
echo $XDG_SESSION_TYPE  # should print "wayland"

# Force the Wayland platform plugin
QT_QPA_PLATFORM=wayland quickshell
```

If running from a TTY or a script without the Wayland environment variables set, add them:

```bash
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-1}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
quickshell
```

### Module not found: "Quickshell.Hyprland"

This means Quickshell was built without that feature flag, or the module is not in Qt's
QML import path. Check how you installed Quickshell:

```bash
# Check what features are compiled in
quickshell --help | grep -i feature

# Check QML import paths
QML_IMPORT_TRACE=1 quickshell 2>&1 | head -40
```

If you built from source, reconfigure with the relevant `_ENABLE` flag and rebuild.

### Hot reload triggers but UI does not update

Hot reload works by replacing the QML component in the engine. If your component has
imperative state set in `Component.onCompleted` or via JavaScript assignments, that state
is re-run on each reload. If it appears unchanged, check:

```bash
# Enable QML debug output
QML_DISABLE_OPTIMIZER=1 quickshell 2>&1 | grep -i reload
```

Make sure the file being edited is actually under the config root path Quickshell is watching.
If you have symlinks pointing outside the config directory, inotify may not follow them.

### PipeWire service not working

The PipeWire integration requires `libpipewire-0.3.so` at runtime. On Arch:

```bash
pacman -Qi pipewire | grep Version  # should be 0.3.x
ldconfig -p | grep pipewire         # should show libpipewire-0.3
```

If PipeWire is running but the `Quickshell.Services.Pipewire` types are not working, check
that your user PipeWire session is active:

```bash
systemctl --user status pipewire.service pipewire-pulse.service
wpctl status  # should show audio devices
```

### Shell crash on Hyprland IPC event

Some IPC events arrive before Quickshell has fully initialized its object tree. Use
`Component.onCompleted` guards and null checks:

```qml
HyprlandWorkspace {
    onWindowAdded: function(win) {
        if (!win || !win.address) return  // guard against null
        console.log("window added:", win.address)
    }
}
```

Also check the Hyprland socket path is correct for your user:

```bash
echo $HYPRLAND_INSTANCE_SIGNATURE  # must be set
ls /tmp/hypr/$HYPRLAND_INSTANCE_SIGNATURE/  # should exist
```

> **See also:** Ch 16 for your first working QML shell, Ch 17 for multi-monitor PanelWindow
> layouts, Ch 20 for Hyprland IPC integration, Ch 40 for the notification service,
> Ch 53 for systemd session startup.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
