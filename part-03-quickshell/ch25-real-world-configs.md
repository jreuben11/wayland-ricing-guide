# Chapter 25 — Real-World Quickshell Configurations

## Overview

This chapter dissects exemplary community Quickshell configurations, drawing architectural patterns,
performance strategies, and aesthetic approaches from real-world rices. Rather than presenting toy
examples, we examine production-quality dotfiles used daily by their authors. By studying these
configurations you will learn the idioms that experienced Quickshell users have converged on,
understand the trade-offs between different structural approaches, and gain a library of patterns
to apply in your own work.

Quickshell's declarative QML model encourages a component-centric design that diverges
significantly from shell scripts or Eww S-expressions. The configurations explored here demonstrate
that QML's binding system, when applied thoughtfully, enables reactive UIs that respond instantly
to compositor events, network changes, and color scheme switches without the polling overhead of
traditional status bars. Each community config reviewed below illustrates different points on the
spectrum from minimal-and-focused to maximal-and-comprehensive.

Prerequisites: you should be comfortable with basic Quickshell shell roots and the
`ShellRoot`/`PanelWindow` lifecycle from Chapters 20–22. A working Hyprland or Niri installation
is assumed for the compositor-specific examples. See Chapter 53 for session startup integration,
and Chapter 18 for IPC foundations that several patterns here depend upon.

---

## 25.1 end_4/dots-hyprland

Repository: [https://github.com/end-4/dots-hyprland](https://github.com/end-4/dots-hyprland)

The `dots-hyprland` project is one of the most-starred Hyprland rice repositories on GitHub and
serves as a reference implementation for ambitious Quickshell configurations. The architecture is
explicitly modular: each shell surface (bar, sidebar, overview, lock screen) lives in an
independent directory and is loaded only when needed. This deliberate decoupling means you can
transplant individual components into your own config without understanding the entire codebase.

The AI-integration layer is the project's most distinctive feature. A floating sidebar communicates
with local Ollama models, streaming responses into a QML `ListView` backed by a custom list model
updated from process stdout. The entire pipeline — process spawn, stdout parsing, model injection,
scroll management — is implemented in QML and TypeScript-flavoured JS with no native plugins. This
demonstrates that Quickshell's `Process` type and property bindings can replace Python glue
scripts for LLM interfaces.

Color propagation uses **matugen**, Google's Material You color generation tool. On wallpaper
change, a small shell command regenerates `~/.config/quickshell/theme/colors.qml`, and Quickshell
watches the file with `FileView`. The resulting live theme switch — without restarting the shell —
takes under 200 ms on typical hardware. Animations throughout the config use `Easing.OutExpo` for
reveals and `Easing.InExpo` for hides, giving a polished feel that distinguishes it from rices
that rely on plain linear transitions.

**Cloning and examining the config:**

```bash
git clone https://github.com/end-4/dots-hyprland ~/scratch/dots-hyprland
# Quickshell configs live in:
ls ~/scratch/dots-hyprland/.config/quickshell/
```

**Key lessons from end_4:**

| Technique | Implementation | Why It Works |
|-----------|---------------|--------------|
| AI sidebar | `Process` + stdout streaming + `ListModel` | No extra daemon; QML owns the lifecycle |
| Live color reload | `FileView` watching generated `.qml` | Bindings propagate without restart |
| Easing vocabulary | `OutExpo` reveal, `InExpo` hide | Consistent motion language |
| Component isolation | One directory per surface | Transplantable without full understanding |
| Singleton state | `pragma Singleton` per domain | Single source of truth for shared data |

---

## 25.2 outfoxxed's Configurations

outfoxxed is Quickshell's primary author, and examining their personal configurations reveals the
idioms the library was designed to express. The configs use `Variants`, `Scope`, and `LazyLoader`
in ways that document intended usage as clearly as any manual entry. In particular, `Variants`
appears as the canonical mechanism for per-monitor state, not just for multi-monitor setups but
also to drive per-workspace conditional display.

The `Scope` type appears extensively to bind services to surfaces. Rather than a global singleton
for every piece of state, outfoxxed's configs use `Scope` to push service instances down into
component trees, allowing multiple independent bar instances to each own their own workspace
tracker while still sharing a single system-level Bluetooth state singleton. This pattern avoids
the over-globalisation antipattern where everything becomes a singleton and property contention
increases with config size.

`LazyLoader` usage is conservative and purposeful — it is used only where the component being
loaded is genuinely expensive (compositor screenshot overlays, heavy SVG assets) or should not
exist when inactive (e.g., the lock screen surface). This is an important calibration: wrapping
every widget in `LazyLoader` adds indirection without benefit; wrapping expensive or conditionally
active components pays real dividends in startup time and memory.

**Illustrative Scope pattern from outfoxxed-style configs:**

```qml
// services/WorkspaceTracker.qml
import Quickshell
import Quickshell.Hyprland

QtObject {
    id: root
    required property var screen

    property int activeWorkspace: 1
    property var workspaceList: []

    Component.onCompleted: {
        HyprlandIpc.addListener(ipcListener)
    }

    Connections {
        target: HyprlandIpc
        function onEvent(event) {
            if (event.type === "workspace") {
                root.activeWorkspace = parseInt(event.data)
            }
        }
    }
}
```

```qml
// bar/BarRoot.qml — one instance per monitor via Variants
Variants {
    model: Quickshell.screens

    PanelWindow {
        required property var modelData
        id: barWindow
        screen: modelData

        // WorkspaceTracker is scoped to this bar instance
        WorkspaceTracker {
            id: tracker
            screen: barWindow.screen
        }

        WorkspaceWidget {
            tracker: tracker
        }
    }
}
```

**LazyLoader for the lock screen surface:**

```qml
LazyLoader {
    id: lockLoader
    // Only materialise the lock surface when the session lock is requested.
    // A WlSessionLock is expensive: it captures all outputs.
    active: SessionLock.locked

    WlSessionLock {
        Variants {
            model: Quickshell.screens
            LockSurface {
                required property var modelData
                screen: modelData
            }
        }
    }
}
```

---

## 25.3 ekremx25/quickshell — Multi-Compositor Configuration

Repository: [https://github.com/ekremx25/quickshell](https://github.com/ekremx25/quickshell)

This configuration is notable for its explicit multi-compositor support. The same QML codebase
runs under Hyprland, Niri, and MangoWC by branching on a detected compositor string set in an
environment variable. Rather than maintaining separate forks, a single `shell.qml` imports
compositor-specific IPC modules conditionally, keeping shared widget code DRY while keeping
compositor glue isolated.

The **10-band equaliser widget** is a stand-out feature. PipeWire exposes equaliser filters as
objects in the PipeWire graph; the widget uses Quickshell's `Process` type to drive `pw-cli` and
parse its output into a repeating `Slider` row. Slider value changes write back to PipeWire
immediately, producing real-time audio adjustment without a dedicated native plugin.

Material You color extraction is done differently from end_4: instead of shelling out to matugen,
this config runs a small Python script via `Process` that calls the `materialyoucolor` Python
package, writes a JSON file, and exits. Quickshell reads the JSON with `JsonObject` (a JS `JSON.parse`
in a `FileView` watcher). This approach keeps the color engine in Python where the Material You
algorithm is well-tested, while keeping the UI layer in QML.

**Compositor detection pattern:**

```qml
// shell.qml
import Quickshell
import "hyprland" as Hyprland
import "niri" as Niri

ShellRoot {
    property string compositor: Qt.environment("XDG_CURRENT_DESKTOP").toLowerCase()

    Loader {
        active: compositor === "hyprland"
        source: "hyprland/HyprlandIpcBridge.qml"
    }

    Loader {
        active: compositor === "niri"
        source: "niri/NiraIpcBridge.qml"
    }
}
```

**10-band EQ widget skeleton:**

```qml
// widgets/Equalizer.qml
import Quickshell
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    property var bands: [63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000, 20000]
    property var gains: Array(10).fill(0)

    Process {
        id: pw
        command: ["pw-cli", "set-param", "..."]
        running: false
    }

    RowLayout {
        Repeater {
            model: root.bands
            Column {
                Slider {
                    orientation: Qt.Vertical
                    from: -12; to: 12; value: root.gains[index]
                    onValueChanged: {
                        root.gains[index] = value
                        applyGain(index, value)
                    }
                }
                Text { text: modelData >= 1000 ? (modelData / 1000) + "k" : modelData }
            }
        }
    }

    function applyGain(band, db) {
        // Write gain to PipeWire filter node via pw-cli
        pw.command = ["pw-cli", "set-param", pwNodeId, "Props",
                      JSON.stringify({bands: root.gains})]
        pw.running = true
    }
}
```

**Multi-monitor architecture summary:**

```qml
// Multi-monitor bar using Variants — one instance per screen
Variants {
    model: Quickshell.screens

    PanelWindow {
        required property var modelData
        screen: modelData
        anchors { top: true; left: true; right: true }
        height: 36

        RowLayout {
            anchors.fill: parent
            WorkspacePips { screen: parent.screen }
            Item { Layout.fillWidth: true }
            ClockWidget {}
            SysTrayWidget {}
        }
    }
}
```

---

## 25.4 doannc2212/quickshell-config — 206-Theme Switcher

Repository: [https://github.com/doannc2212/quickshell-config](https://github.com/doannc2212/quickshell-config)

This config takes a "take what you like" philosophy: the bar, launcher, notification popups, and
theme switcher are each independently functional and can be removed without breaking the others.
The architecture achieves this by funneling all cross-component communication through service
singletons rather than direct property references, so any component can be deleted by simply
removing its `Loader` line from `shell.qml`.

The **206-theme switcher** is the headline feature. A JSON file ships 206 complete color palettes
(Catppuccin, Nord, Gruvbox, Dracula, Rosé Pine, and many originals). The switcher UI presents
them in a filterable grid; selecting one writes the chosen object to `~/.config/quickshell/active-theme.json`
and the `Theme` singleton's `FileView` watcher triggers an immediate re-evaluation of all bound
colors. The entire switch — JSON parse, property propagation, repaints — completes in one frame on
a Wayland compositor with hardware acceleration.

The notification subsystem implements the full D-Bus `org.freedesktop.Notifications` interface.
Incoming notifications are queued in a `ListModel`, rendered in a `Repeater` backed `Column`, and
dismissed by swiping right (a `DragHandler` with `xAxis.minimum: 0`). Persistence is optional:
the model can be dumped to `~/.local/share/quickshell/notifications.json` on `ShellRoot` destroy
and reloaded on startup, implementing notification history without a separate daemon.

**The Theme singleton with FileView hot-reload:**

```qml
// theme/Theme.qml
pragma Singleton
import Quickshell
import Qt.labs.folderlistmodel
import QtQuick

Singleton {
    id: root

    property color background:   "#1e1e2e"
    property color surface:      "#181825"
    property color overlay:      "#313244"
    property color text:         "#cdd6f4"
    property color subtext:      "#bac2de"
    property color accent:       "#89b4fa"
    property color accentAlt:    "#cba6f7"
    property color red:          "#f38ba8"
    property color green:        "#a6e3a1"
    property color yellow:       "#f9e2af"

    FileView {
        id: themeFile
        path: Qt.resolvedUrl("~/.config/quickshell/active-theme.json")
        onTextChanged: loadTheme(themeFile.text)
    }

    function loadTheme(jsonText) {
        try {
            var obj = JSON.parse(jsonText)
            root.background  = obj.background  ?? root.background
            root.surface     = obj.surface     ?? root.surface
            root.text        = obj.text        ?? root.text
            root.accent      = obj.accent      ?? root.accent
            root.accentAlt   = obj.accentAlt   ?? root.accentAlt
        } catch(e) {
            console.warn("Theme parse error:", e)
        }
    }
}
```

**Notification popup with swipe-to-dismiss:**

```qml
// notifications/NotificationPopup.qml
import Quickshell
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: popup
    required property var notification

    color: Theme.surface
    radius: 8
    width: 380; height: contentCol.implicitHeight + 24

    // Swipe right to dismiss
    DragHandler {
        id: drag
        xAxis.minimum: 0
        onActiveChanged: {
            if (!active && drag.centroid.position.x > popup.width * 0.4)
                notification.dismiss()
        }
    }

    Behavior on x {
        NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
    }

    ColumnLayout {
        id: contentCol
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 12 }
        spacing: 4

        Text {
            text: notification.appName
            color: Theme.subtext
            font.pixelSize: 11
        }
        Text {
            text: notification.summary
            color: Theme.text
            font.pixelSize: 14
            font.bold: true
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        Text {
            visible: notification.body !== ""
            text: notification.body
            color: Theme.subtext
            font.pixelSize: 12
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
    }
}
```

---

## 25.5 Common Architecture Patterns

Across all major Quickshell configurations, a set of recurring structural patterns has emerged.
These patterns are worth internalising as idioms; they represent the community's accumulated
experience with what scales well versus what breaks down as configs grow.

### Pattern: The Theme Singleton

The most universal pattern is a `pragma Singleton` QML file that centralises all color, typography,
and spacing values. Using a singleton over plain property objects achieves two things: the singleton
is lazily initialised once and shared by reference everywhere, and any property change on the
singleton propagates instantly to every binding in every component that references it. Live theme
switching — the holy grail of ricing — is essentially free with this pattern.

```qml
// theme/Theme.qml
pragma Singleton
import Quickshell

Singleton {
    property color background: "#1e1e2e"
    property color foreground: "#cdd6f4"
    property color accent:     "#89b4fa"
    property int   cornerRadius: 8
    property string fontFamily: "JetBrainsMono Nerd Font"
    property real  fontSize:    12

    // Optionally load from pywal: read ~/.cache/wal/colors.json
    // Use a FileView watcher here and update properties in onTextChanged
}
```

All consuming components reference it via the module alias:

```qml
import "../theme" as T

Rectangle {
    color: T.Theme.background
    radius: T.Theme.cornerRadius
    Text {
        font.family: T.Theme.fontFamily
        font.pixelSize: T.Theme.fontSize
        color: T.Theme.foreground
    }
}
```

### Pattern: Reactive Wallpaper-Based Colors

Several major configs auto-generate a color scheme from the current wallpaper using either
**matugen** (Material You) or **pywal** (k-means color extraction). The integration pattern is
consistent: a hook in the wallpaper-setting workflow (often a Hyprland `exec-once` or a `swww`
post-set hook) runs the color tool and writes output to a watched file. Quickshell's `FileView`
detects the change and triggers a JS callback that updates the Theme singleton.

```bash
# ~/.config/hypr/scripts/set-wallpaper.sh
#!/usr/bin/env bash
WALL="$1"
swww img "$WALL" --transition-type wipe --transition-duration 1
# Generate Material You palette
matugen image "$WALL" --type scheme-content \
    --json hex > ~/.config/quickshell/theme/colors.json
```

```qml
// theme/Theme.qml (addition)
FileView {
    id: colorFile
    path: StandardPaths.writableLocation(StandardPaths.HomeLocation) +
          "/.config/quickshell/theme/colors.json"
    onTextChanged: {
        try {
            var palette = JSON.parse(colorFile.text)
            Theme.background = palette.background
            Theme.accent      = palette.primary
            Theme.foreground  = palette.onBackground
        } catch (e) { /* keep defaults on parse failure */ }
    }
}
```

### Pattern: Reveal Animations

Panels that slide in/out use height or opacity animations. `NumberAnimation` with cubic easing is
the community standard. Note: animating `height` on a `PanelWindow` is legal in Quickshell —
the compositor layer-shell protocol accepts size changes on each frame.

```qml
PanelWindow {
    id: panel
    property bool revealed: false
    readonly property int fullHeight: 320

    height: revealed ? fullHeight : 0
    Behavior on height {
        NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
    }

    // Trigger reveal from IPC or keyboard shortcut:
    Shortcut {
        sequence: "Meta+D"
        onActivated: panel.revealed = !panel.revealed
    }
}
```

For panels that anchor to an edge and should not leave a gap when hidden, use `exclusiveZone: 0`
combined with a height animation:

```qml
PanelWindow {
    anchors { top: true; left: true; right: true }
    exclusiveZone: revealed ? 36 : 0   // no reserved space when hidden
    height: revealed ? 36 : 0
    Behavior on height { NumberAnimation { duration: 180 } }
    Behavior on exclusiveZone { NumberAnimation { duration: 180 } }
}
```

### Pattern: Conditional Modules via LazyLoader

`LazyLoader` delays component instantiation until `active` becomes true, destroying the component
tree again when `active` returns to false. This is essential for optional hardware (battery
widgets on desktops), session-state surfaces (lock screens), and expensive overlays.

```qml
// Only show battery widget if a battery device is present
LazyLoader {
    id: battLoader
    active: batteryDevice !== null

    BatteryWidget {
        device: battLoader.item ? batteryDevice : null
    }
}

// Lock screen: only create the WlSessionLock surface when locked
LazyLoader {
    active: SessionLockState.locked

    WlSessionLock {
        Variants {
            model: Quickshell.screens
            LockSurface {
                required property var modelData
                screen: modelData
                // Full-screen auth UI here
            }
        }
    }
}
```

### Pattern: Per-Monitor State with Variants

`Variants` instantiates one delegate per entry in `model`. When `model` is `Quickshell.screens`,
you get one delegate per connected monitor. Each delegate is a fully independent QML subtree — its
own `WorkspaceTracker`, `TitleWatcher`, and `ClockModel`. This avoids the stateless-bar antipattern
where a single global `activeWorkspace` variable is shared across monitors and updates incorrectly
when focus moves.

```qml
Variants {
    model: Quickshell.screens

    QtObject {
        required property var modelData
        id: monitorState

        property int  activeWorkspace: 1
        property string windowTitle:  ""
        property bool  isFullscreen:  false

        // Update from Hyprland IPC events filtered by monitor
        Connections {
            target: HyprlandIpc
            function onEvent(event) {
                if (event.type === "focusedmon" &&
                    event.data.split(",")[0] === monitorState.modelData.name) {
                    monitorState.activeWorkspace = parseInt(event.data.split(",")[1])
                }
            }
        }
    }
}
```

---

## 25.6 Performance Tuning

Performance in Quickshell is primarily about avoiding unnecessary re-evaluation of bindings and
not instantiating QML component trees that are invisible or unused. The two most impactful
techniques are `visible: false` with `clip: false` for temporarily hidden widgets, and
`LazyLoader` for components that should not exist at all when inactive. Understanding the
difference matters: `visible: false` keeps the object alive and its bindings active, which is
cheap for simple widgets but expensive for animated or data-heavy ones; `LazyLoader` with
`active: false` destroys the tree entirely.

ScreencopyView for screenshot-based workspace thumbnails is the single most expensive operation
in a typical Quickshell config. Leaving `liveUpdates: true` on all thumbnails consumes significant
GPU time even on mid-range hardware. Set `liveUpdates: false` and update on demand (e.g., when the
overview panel opens):

```qml
ScreencopyView {
    id: thumbCapture
    liveUpdates: overviewPanel.revealed   // only capture when visible
    captureSource: workspaceWindow

    onLiveUpdatesChanged: {
        if (liveUpdates) forceUpdate()
    }
}
```

Binding loops are the most common source of CPU spikes. They manifest as rapid property
oscillation that keeps the QML engine's change-propagation loop running at full speed. The
symptom is a single CPU core pinned at 100%. Diagnosing requires enabling verbose QML logging:

```bash
QML_IMPORT_TRACE=1 quickshell 2>&1 | grep -i "binding loop"
# Or with Quickshell's own log filter:
quickshell --log-rules "qml.binding.loop=true"
```

Property aliasing (`property alias foo: someChild.bar`) is zero-cost compared to a computed
property (`property var foo: someChild.bar`) because an alias is a direct reference pointer while
a computed property schedules a binding evaluation on every change. Use aliases everywhere you
are simply re-exposing a child property at the parent interface boundary:

```qml
// Efficient: alias to child property
Rectangle {
    property alias label: labelText.text
    property alias labelColor: labelText.color
    Text { id: labelText }
}

// Avoid: computed property causes extra binding evaluation on every change
Rectangle {
    property string label: labelText.text   // creates a binding, not an alias
    Text { id: labelText }
}
```

**Performance checklist:**

| Area | Recommendation |
|------|---------------|
| ScreencopyView | Set `liveUpdates: overviewVisible` |
| Invisible widgets | Use `LazyLoader active: false` for expensive, `visible: false` for cheap |
| Property sharing | Use `alias` not computed `property` at component boundaries |
| Repeater items | Keep delegates lightweight; move heavy logic to `Component.onCompleted` |
| Animations | Prefer `NumberAnimation` over `PropertyAnimation` — it avoids boxing |
| Image assets | Set `cache: true` on static images; `sourceSize` to prevent over-decode |
| Fonts | Load custom fonts once in the root; QML font loading is not free |

---

## 25.7 Debugging Production Configs

Debugging a large Quickshell config requires a layered approach: first confirm the process
launches without fatal errors, then isolate the component tree that is misbehaving, and finally
profile the binding graph if the issue is performance rather than logic.

The primary logging surface is Quickshell's `--log-rules` flag, which maps to Qt's categorised
logging system. Useful categories include `qml.binding.loop`, `qml.warning`, and
`quickshell.ipc.*`. Run with all warnings enabled during development:

```bash
# Enable all QML warnings and Quickshell IPC tracing
quickshell --log-rules "*.warning=true,quickshell.ipc.hyprland=true" 2>&1 | tee /tmp/qs-debug.log

# Watch the log in a second terminal
tail -f /tmp/qs-debug.log | grep -E "warning|error|binding"
```

For binding loops specifically, `console.trace()` inside a property's `onChanged` handler will
print the JS call stack at the moment of each evaluation, revealing which component is oscillating:

```qml
property int someValue: computedExpression
onSomeValueChanged: {
    console.trace()   // print call stack on every change — remove after diagnosis
    console.log("someValue changed to", someValue)
}
```

Qt's built-in QML profiler can be attached to a running Quickshell instance to identify which
bindings and signal handlers consume the most time. The profiler output is read by Qt Creator's
profiler view, but can also be parsed with the `qmlprofiler` command-line tool:

```bash
# Start Quickshell with the QML profiler server enabled
QML_PROFILER=1 QML_PROFILER_PORT=8080 quickshell

# In a second terminal, record a trace
qmlprofiler --attach localhost:8080 --record 10 --output /tmp/qs-profile.qtd
```

A useful debugging workflow for IPC-driven state is to replay IPC events manually. For Hyprland:

```bash
# Send a fake workspace change event to the Hyprland IPC socket
echo -n "workspace>>2" | socat - UNIX-CONNECT:/tmp/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock
```

This lets you test how your workspace tracker responds to events without actually switching
workspaces, and is invaluable when debugging per-monitor state logic.

---

## 25.8 Config Organisation Recommendations

A clean directory layout pays dividends when a config grows beyond a handful of files. The
structure below has been independently arrived at by multiple major config authors and represents
the community consensus:

```
~/.config/quickshell/
├── shell.qml                   ← ShellRoot only; imports and instantiates surfaces
├── bar/
│   ├── Bar.qml                 ← Variants over Quickshell.screens
│   ├── WorkspacePips.qml
│   ├── ClockWidget.qml
│   ├── SysTray.qml
│   └── AudioWidget.qml
├── notifications/
│   ├── NotificationServer.qml  ← D-Bus service singleton
│   ├── NotificationPopup.qml
│   └── NotificationHistory.qml
├── osd/
│   ├── VolumeOsd.qml
│   └── BrightnessOsd.qml
├── overview/
│   ├── Overview.qml            ← LazyLoader-wrapped PanelWindow
│   └── WorkspaceThumbnail.qml
├── launcher/
│   ├── Launcher.qml
│   └── AppItem.qml
├── lockscreen/
│   ├── LockRoot.qml
│   └── AuthWidget.qml
├── widgets/
│   ├── Clock.qml
│   └── Calendar.qml
├── theme/
│   ├── Theme.qml               ← pragma Singleton with all design tokens
│   └── colors.json             ← written by matugen/pywal; watched by FileView
└── services/
    ├── AudioService.qml        ← PipeWire/PulseAudio singleton
    ├── NetworkService.qml      ← NetworkManager DBus singleton
    ├── BluetoothService.qml
    └── BatteryService.qml
```

The `shell.qml` root should be minimal — its only job is to instantiate the top-level surfaces via
`Loader` or direct instantiation:

```qml
// shell.qml
import Quickshell

ShellRoot {
    // Status bar — always present
    Bar {}

    // OSD — loaded on demand via internal state
    VolumeOsd {}
    BrightnessOsd {}

    // Notification popups
    NotificationServer {}

    // Overview — heavy, LazyLoader-guarded inside the component
    Overview {}

    // Launcher — hidden by default, revealed by keybind
    Launcher {}

    // Lock screen — LazyLoader-guarded inside the component
    LockRoot {}
}
```

Keep services in their own directory and use `pragma Singleton` so they are never accidentally
instantiated twice. A `services/qmldir` file registers them:

```
# services/qmldir
singleton AudioService    1.0 AudioService.qml
singleton NetworkService  1.0 NetworkService.qml
singleton BluetoothService 1.0 BluetoothService.qml
singleton BatteryService  1.0 BatteryService.qml
```

Cross-reference: for session startup integration that launches Quickshell after the compositor
is ready, see Chapter 53. For the D-Bus notification server implementation details, see Chapter 28.
For theming and color extraction tooling (matugen, pywal, wallutils), see Chapter 32.

---

## Troubleshooting

**Quickshell starts but no bar appears**

Check that your `PanelWindow` has at least one anchor set (`anchors.top: true` etc.) and a
non-zero `height`. A `PanelWindow` with all anchors false and zero height is valid but invisible.
Run with `--log-rules "*.warning=true"` to surface any binding evaluation errors that might be
zeroing a height expression.

```bash
quickshell --log-rules "*.warning=true" 2>&1 | grep -i "height\|anchor\|panel"
```

**Theme singleton changes not propagating**

If editing `Theme.qml` at runtime does not update bound properties, confirm Quickshell's hot-reload
is enabled (`--hot-reload` flag or `quickshell.json` setting). Also verify the consuming components
use the `T.Theme.property` alias syntax, not a local copy: `property color bg: Theme.accent` creates
a one-time binding snapshot, not a live binding.

**Variants not creating one instance per monitor**

If `Variants { model: Quickshell.screens }` produces only one delegate, the `Quickshell.screens`
model may not yet be populated at ShellRoot construction time. Wrap in a `Binding { restoreMode:
Binding.RestoreNone }` or add a `Component.onCompleted` trigger. As a diagnostic, log the model
count:

```qml
Component.onCompleted: console.log("screens:", Quickshell.screens.length)
```

**High CPU usage — binding loop suspected**

```bash
# Confirm a binding loop is running
quickshell --log-rules "qml.binding.loop=true" 2>&1 | head -40

# Identify the oscillating property by adding a trace in onChanged
```

**IPC events not received from Hyprland**

Verify `HYPRLAND_INSTANCE_SIGNATURE` is set in the environment Quickshell inherits. If launching
from a systemd user service, ensure `PassEnvironment=HYPRLAND_INSTANCE_SIGNATURE` is set. Check:

```bash
echo $HYPRLAND_INSTANCE_SIGNATURE
# Should be a UUID-like string, e.g. "abc123_1_DP-1"

# Test IPC manually:
hyprctl monitors   # should return monitor info
```

**Notification popups not appearing despite D-Bus service registration**

Use `busctl` to confirm Quickshell has acquired the notification service name and to send a test
notification directly:

```bash
# Confirm the name is owned
busctl --user list | grep freedesktop.Notifications

# Send a test notification bypassing libnotify
busctl --user call org.freedesktop.Notifications /org/freedesktop/Notifications \
    org.freedesktop.Notifications Notify \
    "susssasa{sv}i" "test-app" 0 "" "Test" "Body text" 0 0 {} 5000
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
