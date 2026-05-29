# Chapter 16 — QML Foundations for Quickshell

## Overview

You don't need Qt or mobile development experience to use Quickshell, but
understanding QML's core concepts unlocks its full power. This chapter teaches
exactly what you need — no more, no less. QML (Qt Modeling Language) is a
declarative, JavaScript-superset language designed specifically for describing
user interfaces. It was created by the Qt project and is the UI layer powering
everything from embedded devices to desktop applications. In the context of
Wayland ricing, it is the language you write your shell configuration in when
using Quickshell.

Unlike shell scripts that imperatively call programs, or CSS that purely styles
HTML, QML occupies a distinct niche: it defines *object trees* whose properties
are *reactively bound* to expressions. When a value changes anywhere in the
tree, every binding that depended on it recomputes automatically — without any
manual event wiring. This makes it unusually well-suited to building live,
always-updating status bars, notification daemons, and system monitors.

This chapter is deliberately standalone. You do not need to install Qt Creator,
you do not need to understand signals-and-slots at the C++ level, and you do not
need prior Qt experience. Everything here is oriented toward reading and writing
Quickshell configuration files. For the complete Quickshell environment setup
refer to Ch 14, and for connecting QML objects to D-Bus services see Ch 21.

---

## 16.1 QML Basics

QML files describe a tree of objects using a brace-delimited syntax that looks
superficially like JSON but is substantially more powerful. Each object has a
*type* (capitalized), followed by a block of property assignments and nested
child objects. Properties are set with colon syntax. Semicolons separate
multiple properties on the same line, but newlines work just as well and are
usually preferred for readability.

The most important mental model is containment: child objects are *inside* their
parent both syntactically and visually. A `Rectangle` that contains a `Text`
item will render the text on top of, and clipped to, the rectangle by default.
The root object of any file is the top of the visual hierarchy for that file.

Property bindings are not assignments in the imperative sense — they are live
formulas. Writing `width: parent.width / 2` does not set the width once and
forget; it installs a reactive subscription so that any time `parent.width`
changes, `width` recomputes. This is the single most powerful feature of QML
and the reason live system monitors are easy to build.

The `id` property gives an object a name that can be referenced from anywhere
else in the same file. IDs are unique within their file scope and are not
strings — they are direct in-engine references. Using `id` is the canonical way
to reference a sibling or distant relative in the object tree without resorting
to parent-walking.

```qml
// hello.qml — minimal working QML file
import QtQuick 6.0

Rectangle {
    id: root
    width: 400
    height: 100
    color: "#1e1e2e"   // Catppuccin Mocha base

    Text {
        id: label
        anchors.centerIn: parent
        text: "Hello, Wayland"
        color: "#cdd6f4"   // Catppuccin text
        font.pixelSize: 24
        font.family: "JetBrainsMono Nerd Font"
    }
}
```

```qml
// Demonstrating live bindings — width tracks a slider value
import QtQuick 6.0
import QtQuick.Controls 6.0

Column {
    width: 400; height: 200

    Slider {
        id: slider
        from: 0; to: 400
        value: 200
        width: parent.width
    }

    Rectangle {
        // This binding recomputes every time slider.value changes
        width: slider.value
        height: 40
        color: "#89b4fa"
    }
}
```

---

## 16.2 Types and Properties

QML has a rich built-in type system that covers primitive values, geometric
types, and visual object types. Understanding the type system matters because
property types determine how values are coerced, how comparisons work, and
what animation targets are valid.

**Primitive types** — `int`, `real`, `bool`, `string`, `color`, `url`, `var`.
The `color` type accepts CSS color strings (`"#ff0000"`), `Qt.rgba()` calls, and
named colors (`"red"`). The `url` type is used for image sources and QML file
paths. The `var` type is a dynamically-typed escape hatch that can hold any
JavaScript value including arrays and objects.

**Geometric types** — `size`, `point`, `rect`, `font`, `matrix4x4`, `quaternion`,
`vector2d/3d/4d`. These are value types, not objects — they do not have `id`s
and are passed by value. They support dot notation for component access:
`myRect.x`, `myFont.pixelSize`.

**Custom properties** are declared with `property type name: defaultValue`. They
participate fully in the binding system — you can bind to them and bind from
them just like built-in properties. A `readonly property` is a computed value
that cannot be assigned from outside. A `required property` must be explicitly
provided when the component is instantiated; the engine throws an error if it is
omitted.

| Keyword            | Settable externally | Bindable | Use case                        |
|--------------------|---------------------|----------|---------------------------------|
| `property`         | Yes                 | Yes      | General mutable state           |
| `readonly property`| No                  | Yes      | Derived/computed values         |
| `required property`| Yes (mandatory)     | Yes      | Component API surface           |
| `default property` | Via children syntax | Yes      | Content property of a container |

```qml
// Custom property declarations
import QtQuick 6.0

Rectangle {
    id: root

    // Mutable — can be set from outside or bound
    property color accent: "#89b4fa"

    // Readonly — computed from accent, cannot be assigned
    readonly property color dimAccent: Qt.darker(accent, 1.4)

    // Required — parent MUST provide this when instantiating
    required property string labelText

    width: 200; height: 60
    color: dimAccent

    Text {
        anchors.centerIn: parent
        text: root.labelText
        color: root.accent
    }
}
```

```qml
// Using the above component from a parent file
// (assuming the file above is saved as AccentLabel.qml)
import QtQuick 6.0

Column {
    spacing: 8

    AccentLabel {
        labelText: "CPU"          // required property satisfied
        accent: "#a6e3a1"         // override default
    }

    AccentLabel {
        labelText: "RAM"
        // accent uses its default value "#89b4fa"
    }
}
```

---

## 16.3 Reactive Bindings

The binding engine is the heart of QML. Every property binding — any value that
uses the colon syntax with an expression — registers itself as a *dependent* of
every property it reads during evaluation. When any of those source properties
change, the binding is automatically re-evaluated and the target property
updates. This happens synchronously within the same event loop iteration.

Signal handlers named `on<PropertyName>Changed` fire after each reactive update.
They are the correct place for side effects triggered by property changes: saving
state to disk, triggering animations, sending a D-Bus message. Using them for
purely derived values is an anti-pattern — use `readonly property` bindings
instead, which are more efficient and compose better.

The most common QML gotcha is *binding breakage*. If you write `myItem.width =
300` in a JavaScript block (note the `=`, not `:`), you replace the binding with
a plain assignment. The live tracking is gone. The property will no longer update
when its former dependencies change. This is silent and is the most frequent
source of "my binding stopped working" bugs. To re-establish a binding from
JavaScript, use `Qt.binding()`.

Binding loops — where property A depends on property B which depends on property
A — are detected by the engine at runtime and generate a warning to stderr.
The engine breaks the loop by not propagating the update, which typically causes
a frozen or zero value. Always keep the dependency graph acyclic.

```qml
import QtQuick 6.0

Item {
    id: root
    width: 400; height: 200

    property real progress: 0.0

    // Binding: recomputes whenever progress changes
    readonly property color barColor: {
        if (progress < 0.5) return "#a6e3a1"   // green
        if (progress < 0.8) return "#f9e2af"   // yellow
        return "#f38ba8"                         // red
    }

    // Signal handler for side effects
    onProgressChanged: {
        if (progress >= 1.0)
            console.log("Task complete!")
    }

    Rectangle {
        width: root.progress * parent.width
        height: 24
        color: root.barColor   // bound to derived property
        anchors.verticalCenter: parent.verticalCenter

        Behavior on width { NumberAnimation { duration: 200 } }
        Behavior on color { ColorAnimation { duration: 200 } }
    }

    // Demonstrating binding re-establishment
    MouseArea {
        anchors.fill: parent
        onClicked: {
            // BAD: breaks the binding
            // root.progress = 0.75

            // CORRECT: re-establish binding after imperative set
            root.progress = Qt.binding(() => Math.random())
        }
    }
}
```

---

## 16.4 Signals and Signal Handlers

QML's signal system is the mechanism for communicating *events* between
components. Signals are typed — each signal declares zero or more parameters
with explicit types — and they are strictly unidirectional: a signal emitter
does not know or care who is listening.

Built-in signals cover interaction events (`onClicked`, `onPressed`,
`onReleased`, `onHovered`), lifecycle events (`Component.onCompleted`,
`Component.onDestruction`), property changes (`on<Name>Changed`), and
more. `Component.onCompleted` is especially important in Quickshell — it runs
once after the component is fully constructed and all properties have been
applied, making it the right place for initialization logic.

Custom signals are declared with `signal name(type param, ...)`. The handler is
automatically available as `onName` in any parent or peer that has a reference
to the object. For programmatic connections — especially connecting to signals on
objects obtained at runtime — use the `connect()` method: `source.someSignal
.connect(target.someSlot)`. Disconnection uses `disconnect()` with the same
arguments.

Signals can carry parameters. Handler functions receive those parameters as
arguments. When using `connect()` the connected function must accept the correct
parameter types, or you will get a type coercion warning at runtime.

```qml
// Custom signal with parameter
import QtQuick 6.0

Rectangle {
    id: button
    width: 120; height: 40
    color: mouseArea.containsPress ? "#313244" : "#1e1e2e"
    radius: 6
    border.color: "#89b4fa"; border.width: 1

    // Custom signal declaration
    signal clicked(string buttonLabel)

    required property string label

    Text {
        anchors.centerIn: parent
        text: button.label
        color: "#cdd6f4"
    }

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        onClicked: button.clicked(button.label)   // emit custom signal
    }
}
```

```qml
// Using connect() for programmatic wiring
import QtQuick 6.0

Item {
    width: 400; height: 200

    MyButton { id: btn1; label: "Save"; y: 20 }
    MyButton { id: btn2; label: "Load"; y: 80 }

    function handleButton(lbl) {
        console.log("Button pressed:", lbl)
    }

    Component.onCompleted: {
        btn1.clicked.connect(handleButton)
        btn2.clicked.connect(handleButton)
    }

    Component.onDestruction: {
        btn1.clicked.disconnect(handleButton)
        btn2.clicked.disconnect(handleButton)
    }
}
```

---

## 16.5 JavaScript in QML

QML integrates JavaScript as a first-class scripting language. JavaScript
expressions appear in three contexts: inline binding expressions, inline
function bodies, and imported `.js` modules. Understanding which context you are
in matters because the rules differ slightly between them.

**Inline binding expressions** — everything to the right of a colon property
binding — can use any JS expression and access any property visible in the
current scope. Block-form bindings (using `{}` to return a value) are evaluated
as functions; the last expression becomes the binding value. These are
re-evaluated reactively.

**Inline function bodies** in signal handlers and `function` declarations run
imperatively. They do not automatically track property dependencies. Code here
should be side-effect logic, not derived value computation. Performing expensive
computation in signal handlers rather than `readonly property` bindings is a
common early mistake that causes performance problems.

**Imported `.js` modules** are plain JavaScript files with a `.pragma library`
directive that makes them singletons, or without it (instantiated per-component).
They are the right place for utility functions, algorithms, and logic that has no
direct dependency on the QML object model. Import them with a named alias.

QML's JS runtime is V8 (same as Node.js), but there is no Node.js standard
library. There is no `fs`, no `http`, no `require()`. Instead you have the `Qt`
global object, `XMLHttpRequest` for HTTP, and QML-provided APIs for file I/O
(`Qt.resolvedUrl`, file models, etc.). For system integration, use Quickshell's
`Process` or D-Bus types rather than trying to spawn processes in JS.

```qml
// Block-form binding with conditional logic
import QtQuick 6.0

Item {
    property real cpuUsage: 0.72   // 72%

    readonly property string usageLabel: {
        const pct = Math.round(cpuUsage * 100)
        if (pct > 90) return pct + "% (!)"
        return pct + "%"
    }

    Text {
        text: parent.usageLabel
        color: "#cdd6f4"
        font.pixelSize: 14
    }
}
```

```js
// utils.js — shared utility module
.pragma library

function formatBytes(bytes) {
    if (bytes < 1024) return bytes + " B"
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB"
    if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + " MB"
    return (bytes / 1073741824).toFixed(2) + " GB"
}

function clamp(val, min, max) {
    return Math.min(Math.max(val, min), max)
}

function lerp(a, b, t) {
    return a + (b - a) * t
}
```

```qml
// Importing and using utils.js
import QtQuick 6.0
import "utils.js" as Utils

Text {
    property int memoryBytes: 3_758_096_384   // 3.5 GB

    text: Utils.formatBytes(memoryBytes)
    color: "#cdd6f4"
    font.pixelSize: 14
}
```

---

## 16.6 Components and Instantiation

A **Component** in QML is a reusable object template that can be instantiated on
demand. Unlike a standalone `.qml` file (which is always instantiated once when
loaded), a `Component {}` block defines a template inline that is only
instantiated when explicitly told to be. This is the primitive that powers
`Loader`, `Repeater`, and dynamic creation.

`Loader` is the swiss-army knife of conditional or deferred UI. Set its `source`
or `sourceComponent` to load something, clear it to destroy. The loaded item is
available as `loader.item`. Property bindings into a loaded item require care —
they may be null before loading completes, so always null-check with `loader.item
? loader.item.someProperty : fallback`.

`Repeater` instantiates a component once for each element of its `model`. The
model can be an integer (repeat N times), a JavaScript array, a `ListModel`, or
any QAbstractItemModel subclass. Inside the delegate, `index` and `modelData`
are always available. `Repeater` is for small, statically-sized collections;
for large or scrolling lists, prefer `ListView`.

`ListView` and `GridView` are virtualized: they only instantiate delegates for
the visible portion of the list plus a small buffer. This makes them suitable for
hundreds or thousands of items. They require a `model` and a `delegate`, and
optionally a `header`, `footer`, and `section.delegate`.

```qml
// Inline Component with Loader — toggle a heavy panel
import QtQuick 6.0

Item {
    width: 400; height: 300

    property bool showPanel: false

    Column {
        anchors.fill: parent
        spacing: 8

        Rectangle {
            id: toggleBtn
            width: 120; height: 36
            color: "#313244"; radius: 4

            Text {
                anchors.centerIn: parent
                text: showPanel ? "Hide Panel" : "Show Panel"
                color: "#cdd6f4"
            }

            MouseArea {
                anchors.fill: parent
                onClicked: showPanel = !showPanel
            }
        }

        Loader {
            id: panelLoader
            width: parent.width
            active: showPanel   // auto-loads/unloads
            sourceComponent: heavyPanel
        }
    }

    Component {
        id: heavyPanel
        Rectangle {
            height: 200
            color: "#181825"
            border.color: "#45475a"
            Text {
                anchors.centerIn: parent
                text: "Expensive Widget"
                color: "#cdd6f4"
            }
        }
    }
}
```

```qml
// Repeater with ListModel — workspace switcher
import QtQuick 6.0

Row {
    spacing: 4

    Repeater {
        model: ListModel {
            ListElement { wsNum: 1; active: true  }
            ListElement { wsNum: 2; active: false }
            ListElement { wsNum: 3; active: false }
            ListElement { wsNum: 4; active: false }
        }

        delegate: Rectangle {
            width: 28; height: 28
            radius: 4
            color: model.active ? "#89b4fa" : "#313244"

            Text {
                anchors.centerIn: parent
                text: model.wsNum
                color: model.active ? "#1e1e2e" : "#cdd6f4"
                font.bold: model.active
            }
        }
    }
}
```

---

## 16.7 Singletons

Singletons are QML files that are instantiated exactly once for the lifetime of
the shell and accessible by name from any other QML file in the same Quickshell
config tree. They are declared by adding `pragma Singleton` as the very first
line of the file (before any import statements). The file must also be registered
in a `qmldir` file or via Quickshell's automatic discovery.

Singletons are the canonical place for global state: the current color theme,
the active workspace, a shared timer, aggregated system stats. Any property
change on a singleton propagates reactively to all bindings that reference it,
across all panels and popup windows simultaneously — this is what makes theme
switching instantaneous.

Quickshell ships several built-in singletons. `Quickshell` provides access to
screen and panel management. `SystemClock` provides live time values with
configurable update intervals. `Hyprland` (when using the hyprland integration
module) provides live workspace and monitor data. These are imported via their
respective module imports, not via file-relative paths.

Take care about initialization order in singletons. `Component.onCompleted`
runs after all property bindings are established, making it the safe place for
first-time initialization. Singletons that read from the filesystem or run
subprocesses should do so in `onCompleted`, not at the property declaration
level, to avoid initialization ordering issues.

```qml
// Theme.qml — a custom global theme singleton
pragma Singleton
import QtQuick 6.0

QtObject {
    id: root

    // Color scheme (Catppuccin Mocha defaults)
    property color base:    "#1e1e2e"
    property color surface: "#313244"
    property color overlay: "#45475a"
    property color text:    "#cdd6f4"
    property color accent:  "#89b4fa"
    property color red:     "#f38ba8"
    property color green:   "#a6e3a1"
    property color yellow:  "#f9e2af"

    // Font settings
    property string fontFamily: "JetBrainsMono Nerd Font"
    property int    fontSize:   13
    property int    fontSizeLg: 16

    // Spacing
    property int paddingSmall:  4
    property int paddingMedium: 8
    property int paddingLarge:  16
    property int radius:        6

    // Switch between presets at runtime
    function useLatte() {
        base    = "#eff1f5"
        surface = "#e6e9ef"
        overlay = "#7c7f93"
        text    = "#4c4f69"
        accent  = "#1e66f5"
    }

    function useMocha() {
        base    = "#1e1e2e"
        surface = "#313244"
        overlay = "#45475a"
        text    = "#cdd6f4"
        accent  = "#89b4fa"
    }
}
```

```qml
// Using the Theme singleton from any other file
import QtQuick 6.0
import "." as Local   // or however your module is structured

Rectangle {
    color: Theme.base

    Text {
        text: "Status Bar"
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSizeLg
    }
}
```

---

## 16.8 Quickshell-Specific QML Patterns

Quickshell introduces several QML types that have no equivalent in standard
QtQuick. Understanding their roles is essential because they replace the
boilerplate patterns that other shell frameworks require you to implement manually.

`ShellRoot` is the mandatory top-level type in `shell.qml`. It is not a visual
element — it is the configuration root that Quickshell discovers when loading your
config. Everything inside a `ShellRoot` is part of your shell. `ShellRoot` does
not correspond to any window; windows are created by `PanelWindow` or
`FloatingWindow` children within it.

`Variants` solves the per-monitor problem elegantly. Pass a model of screens to
`Variants` and it instantiates its delegate once per screen, automatically
creating and destroying instances as monitors are hotplugged. The delegate
receives the screen object as a required property. This replaces the
`xrandr`-style manual per-monitor configuration that wrecks your config every
time you change monitor setup.

`LazyLoader` is a Quickshell-specific `Loader` variant that defers instantiation
until the first time the item is shown. Use it for popup menus, notification
overlays, and anything that is rarely visible. It saves startup time and memory.
Unlike standard `Loader`, `LazyLoader` will not re-create the item when hidden —
it keeps it in memory but hidden, which avoids creation jank on re-show.

`PersistentProperties` survives config reloads (`quickshell reload`). Normal QML
properties reset to their default values on reload because the entire object tree
is destroyed and recreated. Wrap properties you want to survive reload in a
`PersistentProperties` block; Quickshell serializes their values to disk and
restores them in the new instance.

```qml
// shell.qml — canonical Quickshell entry point
import QtQuick 6.0
import Quickshell 0.1

ShellRoot {

    // One bar per monitor, automatically managed
    Variants {
        model: Quickshell.screens

        delegate: PanelWindow {
            required property var modelData   // the screen object

            screen: modelData
            anchors {
                top: true
                left: true
                right: true
            }
            height: 36
            color: "transparent"
            exclusionMode: ExclusionMode.Exclusive

            StatusBar {
                anchors.fill: parent
                screen: parent.modelData
            }
        }
    }

    // Lazy popup — only instantiated when first opened
    LazyLoader {
        id: launcherLoader
        active: false

        sourceComponent: AppLauncher {
            onDismissed: launcherLoader.active = false
        }
    }

    // Persistent: survives quickshell reload
    PersistentProperties {
        id: persist
        property string lastWorkspace: "1"
        property bool notificationsEnabled: true
    }
}
```

```qml
// Scope — non-visual grouping with shared properties
import QtQuick 6.0
import Quickshell 0.1

ShellRoot {

    Scope {
        id: networkScope
        property string ssid: ""
        property int    signalStrength: 0
        property bool   connected: false

        // A process that polls network info
        Process {
            command: ["nmcli", "-t", "-f", "active,ssid,signal",
                      "dev", "wifi"]
            running: true
            // parse stdout and update networkScope properties
        }
    }

    // Any child can reference networkScope.ssid etc.
}
```

---

## 16.9 Debugging QML

QML debugging is primarily log-driven. The `console` object maps to stderr output
and provides `log`, `warn`, `error`, and `trace`. `console.trace()` prints the
current JavaScript call stack, which is invaluable when you cannot figure out
where a signal is originating from.

The `--log-rules` command-line flag controls Qt's categorized logging system.
Pass `"*.debug=true"` to enable all debug categories, or target specific ones:
`"quickshell.*.debug=true"` for Quickshell internals, `"qml.*.debug=true"` for
QML engine messages. Combine multiple rules with semicolons. When chasing a
binding loop the QML engine will print the warning with a stack trace if you
enable `"qml.binding.debug=true"`.

The `Qt.formatDateTime()`, `JSON.stringify()`, and `JSON.parse()` functions are
available and useful for formatting values in console output. For inspecting an
arbitrary object's properties at runtime, `JSON.stringify(object)` will
enumerate its enumerable JS properties (not QML properties — for those, use
`Object.keys` on the object cast with `({})` wrapping).

Common runtime errors and their meanings:

| Error message | Likely cause |
|---------------|--------------|
| `TypeError: Cannot read property 'X' of null` | Binding reads a child property before the child is constructed; gate with `if (item)` |
| `QML Rectangle: Binding loop detected for property "width"` | Property A depends on B which depends on A |
| `ReferenceError: id is not defined` | Referencing an `id` from a different file scope; use a property or singleton instead |
| `Cannot assign to non-existent property "X"` | Typo in property name, or property not declared |
| `Component.onCompleted` not firing | The object is inside a `Loader` with `active: false`; it hasn't been instantiated yet |
| `Loader item is null` | Accessing `loader.item` before the loader has finished; use `loader.status === Loader.Ready` guard |

```qml
// Defensive null-checking pattern
import QtQuick 6.0

Loader {
    id: myLoader
    active: false
    source: "HeavyPanel.qml"

    // Safe access: guard with status check
    onStatusChanged: {
        if (status === Loader.Ready) {
            console.log("Panel loaded, height:", item.height)
        }
    }
}

// Elsewhere — safe binding with null coalesce
Text {
    text: myLoader.item ? myLoader.item.title : "Loading..."
}
```

```bash
# Run Quickshell with verbose QML debug output
quickshell --log-rules "qml.debug=true;quickshell.*.debug=true" &

# Alternatively, watch only binding-loop warnings
quickshell --log-rules "qml.binding=true" 2>&1 | grep -i "binding loop"

# Reload config and capture output to file for review
quickshell reload && journalctl --user -u quickshell -f
```

---

## Troubleshooting

**QML file not found / module not found**
Quickshell discovers QML files relative to `shell.qml`. If you split your config
into subdirectories, add a `qmldir` file in each directory listing the types it
exports. Alternatively, use relative path imports (`import "components/"`) which
work without `qmldir` but sacrifice type safety.

**Property binding fires once then stops updating**
You have broken the binding with an imperative `=` assignment somewhere in a
signal handler or `onCompleted`. Search your handlers for direct assignments to
the property in question and replace them with `Qt.binding(() => expression)`.
Enable `--log-rules "qml.binding.debug=true"` to confirm binding installation.

**Singleton not accessible by name**
The singleton file must be listed in a `qmldir` or imported via its full module
path. If you are using Quickshell's directory-based discovery, ensure the
`pragma Singleton` line is the *first* line of the file — even before `import`
statements — or the engine will not register it as a singleton.

**`PersistentProperties` values not restored after reload**
The `PersistentProperties` block must have a stable `id` across reloads. If you
rename the `id`, Quickshell treats it as a new storage slot and the old values
are orphaned. The persistence file is stored in
`~/.local/share/quickshell/<config-name>/`. Inspect or delete it there.

**Performance: bindings updating too frequently**
A binding that reads a frequently-changing property (like a timer tick every 100ms)
and does expensive computation will stall the UI. Refactor: move computation into
a `Timer`-driven function that writes to a plain property, and bind to that
property instead. Also consider `FrameAnimation` for render-synchronized updates
instead of polling timers.

**Blank window / transparent output**
Ensure your root window type (`PanelWindow` or `FloatingWindow`) has a non-zero
`width` and `height`. Quickshell windows default to zero size. Also check that
you are not accidentally setting `color: "transparent"` on an outer `Rectangle`
that you expected to be opaque.

---

## Cross-References

- **Ch 14** — Installing and launching Quickshell, config directory layout
- **Ch 15** — `shell.qml` structure, `ShellRoot` deep-dive, module loading
- **Ch 17** — `PanelWindow` and Wayland layer-shell protocol integration
- **Ch 18** — Anchoring, layout types (`Row`, `Column`, `Grid`, `StackLayout`)
- **Ch 21** — Connecting QML to D-Bus services via Quickshell's DBus module
- **Ch 24** — The `Process` type: spawning subprocesses and parsing stdout
- **Ch 29** — Animations and `Behavior` blocks for smooth UI transitions
- **Ch 35** — Theme singletons in practice: live color scheme switching
- **Ch 53** — Session startup: launching Quickshell from a systemd user unit

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
