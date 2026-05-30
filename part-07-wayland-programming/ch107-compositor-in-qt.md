# Chapter 107 — Building a Wayland Compositor with Qt/qtwayland

## Overview

Qt ships its own first-class Wayland compositor framework: the `QtWayland.Compositor` module, implemented in the [qtwayland](https://github.com/qt/qtwayland) repository. Unlike wlroots (Ch 47) or Smithay (Ch 48), which are low-level libraries that give you maximum protocol control at the cost of substantial boilerplate, qtwayland's compositor module lets you build a complete, interactive compositor in QML — the same declarative language used for Quickshell shell scripting (Ch 15–25). C++ extensions drop in alongside QML using the same plugin architecture.

The practical niche is clear: if your compositor needs a rich QML-driven UI layer — animated window decorations, GPU-accelerated effects, embedded web views, QML-based overlays — qtwayland composes with that intent naturally. KDE Plasma's Wayland session is built on KWin, which layers atop Qt; gamescope uses its own stack but Qt-based kiosks, digital signage compositors, and automotive IVI systems routinely use the QtWayland compositor API directly.

This chapter covers:

1. The two-level API: QML-first (high-productivity) and C++ (full control)
2. Project setup with CMake and Qt 6
3. A minimal QML compositor that renders XDG toplevels
4. C++ compositor classes: `QWaylandCompositor`, `QWaylandOutput`, `QWaylandSeat`
5. Shell protocol integration: XDG shell, layer-shell, IVI
6. Input routing, drag-and-drop, and clipboard
7. Multi-output and HiDPI
8. Custom protocol extensions via `QWaylandCompositorExtension`
9. Testing and debugging
10. Comparison with wlroots and Smithay

**Cross-references:** Ch 36 covers qtwayland from the *client* side (environment variables, theming). Ch 47 covers wlroots in C. Ch 48 covers Smithay in Rust. Ch 15–19 cover Quickshell QML patterns that apply directly here. Ch 46 explains Wayland protocol extension XML that feeds into §107.8.

---

## 107.1 qtwayland Architecture

The qtwayland repository compiles two distinct modules:

- **`Qt6::Wayland`** (client plugin) — the QPA backend that lets Qt applications run as Wayland clients (`QT_QPA_PLATFORM=wayland`). This is what Ch 36 is about.
- **`Qt6::WaylandCompositor`** (compositor library) — the classes and QML types that let you *be* the compositor. This chapter covers this module exclusively.

The compositor module has three layers:

```
┌──────────────────────────────────────────────────────────────────┐
│  QML Layer (QtWayland.Compositor, QtWayland.Compositor.XdgShell) │
│  ShellSurfaceItem  WaylandOutput  XdgShell  WaylandQuickItem     │
├──────────────────────────────────────────────────────────────────┤
│  C++ Quick Layer (QWaylandQuickCompositor, QWaylandQuickItem)    │
│  Bridges compositor events into Qt Quick scene graph signals     │
├──────────────────────────────────────────────────────────────────┤
│  C++ Core Layer (QWaylandCompositor, QWaylandOutput, ...)        │
│  Direct protocol control; usable without Qt Quick               │
└──────────────────────────────────────────────────────────────────┘
```

Internally, all three layers sit atop Qt's wayland-server integration which wraps `libwayland-server` — the same C library underlying wlroots. Qt generates protocol stub code from the same `*.xml` files that `wayland-scanner` processes for C compositors.

---

## 107.2 Project Setup

### Package Installation

```bash
# Arch Linux
sudo pacman -S qt6-wayland qt6-base cmake ninja

# Ubuntu 24.04+
sudo apt install qt6-wayland-dev libqt6waylandcompositor6-dev \
     qt6-base-dev cmake ninja-build

# Fedora 40+
sudo dnf install qt6-qtwayland-devel qt6-qtbase-devel cmake ninja-build
```

The `qt6-wayland` package on Arch ships both the client plugin and the compositor library. On Debian-based distros, the compositor headers are in a separate `-dev` package.

### CMakeLists.txt

```cmake
cmake_minimum_required(VERSION 3.22)
project(mycompositor CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)

find_package(Qt6 REQUIRED COMPONENTS
    Core
    Gui
    Quick
    WaylandCompositor
)

qt_add_executable(mycompositor
    main.cpp
    compositor.cpp
    compositor.h
)

target_link_libraries(mycompositor PRIVATE
    Qt6::Core
    Qt6::Gui
    Qt6::Quick
    Qt6::WaylandCompositor
)

# QML module for the compositor UI
qt_add_qml_module(mycompositor
    URI MyCompositor
    VERSION 1.0
    QML_FILES
        qml/main.qml
    RESOURCES
        qml/background.qml
)
```

For QML-only compositors (no custom C++ classes), you can skip the `qt_add_executable` entirely and use `qml` or `qmlscene` to run your compositor QML file directly — useful during development.

### Verifying the Wayland Socket

The compositor creates a Wayland socket in `$XDG_RUNTIME_DIR`. Run it nested inside an existing session first:

```bash
# Build
cmake -B build -G Ninja && ninja -C build

# Run nested (inside X11 or another Wayland compositor)
./build/mycompositor

# Check socket
ls $XDG_RUNTIME_DIR/wayland-*
# → wayland-0  wayland-1  ...

# Launch a client against your compositor
WAYLAND_DISPLAY=wayland-1 weston-terminal
WAYLAND_DISPLAY=wayland-1 foot
```

To run on bare DRM (no parent compositor), your binary needs `CAP_SYS_TTY_CONFIG` or must run as root. Qt will automatically use the `eglfs` platform plugin in that case.

---

## 107.3 QML-First: Minimal Working Compositor

The fastest path to a running compositor is pure QML. The entry point is a single `WaylandCompositor` root element; everything else — outputs, shell protocol handlers, the scene graph — hangs off it.

### `main.cpp` (launcher)

```cpp
#include <QGuiApplication>
#include <QQmlApplicationEngine>

int main(int argc, char *argv[])
{
    // Qt must know it is *running* as a compositor, not as a Wayland client
    qputenv("QT_QPA_PLATFORM", "xcb");  // nested on X11
    // qputenv("QT_QPA_PLATFORM", "wayland");  // nested on Wayland
    // remove both env overrides for bare DRM (eglfs)

    QGuiApplication app(argc, argv);
    QQmlApplicationEngine engine;
    engine.load(QUrl(u"qrc:/MyCompositor/qml/main.qml"_qs));
    return app.exec();
}
```

### `qml/main.qml`

```qml
import QtQuick
import QtQuick.Window
import QtWayland.Compositor
import QtWayland.Compositor.XdgShell

WaylandCompositor {
    id: compositor

    // ------------------------------------------------------------------
    // Output: one physical screen
    // ------------------------------------------------------------------
    WaylandOutput {
        id: output
        compositor: compositor
        sizeFollowsWindow: true          // output size tracks the QWindow

        window: Window {
            id: rootWindow
            width: 1280
            height: 800
            title: "My Compositor"
            visible: true
            color: "#1e1e2e"            // Catppuccin Mocha base

            // Render all mapped XDG surfaces
            Repeater {
                model: xdgSurfaces

                ShellSurfaceItem {
                    id: surfaceItem
                    shellSurface: modelData.shellSurface
                    focusOnClick: true

                    // Allow dragging windows
                    moveItem: Item { }

                    onSurfaceDestroyed: xdgSurfaces.remove(index)

                    // Simple window title bar
                    Rectangle {
                        id: titleBar
                        height: 28
                        width: parent.width
                        anchors.bottom: parent.top
                        color: "#313244"
                        radius: 4

                        Text {
                            anchors.centerIn: parent
                            text: modelData.title
                            color: "#cdd6f4"
                            font.pixelSize: 13
                        }

                        MouseArea {
                            anchors.fill: parent
                            drag.target: surfaceItem
                        }
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------
    // XDG Shell: handles xdg_wm_base (modern apps)
    // ------------------------------------------------------------------
    XdgShell {
        onToplevelCreated: (toplevel, xdgSurface) => {
            xdgSurfaces.append({
                shellSurface: xdgSurface,
                title: Qt.binding(() => toplevel.title)
            })
        }
    }

    // Window list backing the Repeater
    ListModel {
        id: xdgSurfaces
    }
}
```

This is a fully functional stacking compositor. Client windows appear, can be dragged, receive keyboard and pointer input through `ShellSurfaceItem`'s built-in focus management, and disappear correctly when the client disconnects. All in ~65 lines of QML.

---

## 107.4 C++ Core Layer

For compositors that need full protocol control — custom damage tracking, non-trivial render ordering, tight integration with a game engine or EGL context — drop into the C++ API.

### `compositor.h`

```cpp
#pragma once
#include <QWaylandCompositor>
#include <QWaylandOutput>
#include <QWaylandSeat>
#include <QWaylandXdgShell>
#include <QList>

class QWaylandSurface;
class XdgWindow;

class MyCompositor : public QWaylandCompositor
{
    Q_OBJECT
public:
    explicit MyCompositor(QObject *parent = nullptr);
    void create();

    const QList<XdgWindow *> &windows() const { return m_windows; }

signals:
    void windowAdded(XdgWindow *window);
    void windowRemoved(XdgWindow *window);

private slots:
    void onSurfaceCreated(QWaylandSurface *surface);
    void onToplevelCreated(QWaylandXdgToplevel *toplevel,
                           QWaylandXdgSurface  *xdgSurface);

private:
    QWaylandOutput    *m_output  = nullptr;
    QWaylandSeat      *m_seat    = nullptr;
    QWaylandXdgShell  *m_xdg    = nullptr;
    QList<XdgWindow *> m_windows;
};
```

### `compositor.cpp`

```cpp
#include "compositor.h"
#include <QWaylandXdgShell>
#include <QWaylandSurface>
#include <QOpenGLWindow>

// -------------------------------------------------------------------
// XdgWindow: pairs the protocol objects with render state
// -------------------------------------------------------------------
class XdgWindow : public QObject
{
    Q_OBJECT
public:
    QWaylandXdgSurface  *xdgSurface;
    QWaylandXdgToplevel *toplevel;
    QRect geometry;

    explicit XdgWindow(QWaylandXdgToplevel *tl,
                       QWaylandXdgSurface  *xs,
                       QObject *parent = nullptr)
        : QObject(parent), xdgSurface(xs), toplevel(tl)
    {
        connect(xs->surface(), &QWaylandSurface::mappedChanged,
                this, [this] {
                    if (!xdgSurface->surface()->isMapped())
                        emit unmapped();
                });
    }
signals:
    void unmapped();
};

// -------------------------------------------------------------------
// MyCompositor
// -------------------------------------------------------------------
MyCompositor::MyCompositor(QObject *parent)
    : QWaylandCompositor(parent)
{
    setSocketName("wayland-my");
}

void MyCompositor::create()
{
    // 1. Create the compositor (allocates the Wayland display and socket)
    QWaylandCompositor::create();

    // 2. Output — wraps a QWindow that provides the EGL surface
    auto *window = new QOpenGLWindow;
    window->resize(1280, 800);
    window->show();

    m_output = new QWaylandOutput(this, window);
    m_output->setManufacturer("Virtual");
    m_output->setModel("MyCompositor-1");
    m_output->setPhysicalSize({340, 190}); // mm — affects DPI reporting

    // 3. Seat — aggregates keyboard, pointer, touch
    m_seat = new QWaylandSeat(this, QWaylandSeat::Pointer
                                   | QWaylandSeat::Keyboard
                                   | QWaylandSeat::Touch);

    // 4. XDG shell extension
    m_xdg = new QWaylandXdgShell(this);
    connect(m_xdg, &QWaylandXdgShell::toplevelCreated,
            this,  &MyCompositor::onToplevelCreated);

    // 5. Surface creation signal (all protocols, not just XDG)
    connect(this, &QWaylandCompositor::surfaceCreated,
            this, &MyCompositor::onSurfaceCreated);
}

void MyCompositor::onSurfaceCreated(QWaylandSurface *surface)
{
    // Called for every new wl_surface — before any shell protocol
    // has wrapped it. Use to set up damage/commit tracking.
    connect(surface, &QWaylandSurface::damaged,
            this, [this, surface](const QRegion &damage) {
                // schedule repaint for the damaged region
                Q_UNUSED(damage);
                update(); // triggers QOpenGLWindow repaint
            });
}

void MyCompositor::onToplevelCreated(QWaylandXdgToplevel *toplevel,
                                     QWaylandXdgSurface  *xdgSurface)
{
    auto *win = new XdgWindow(toplevel, xdgSurface, this);
    m_windows.append(win);
    emit windowAdded(win);

    // Configure the toplevel: send initial size, capability flags
    toplevel->sendConfigure({800, 600},
        {QWaylandXdgToplevel::State::Activated});

    connect(win, &XdgWindow::unmapped, this, [this, win] {
        m_windows.removeOne(win);
        emit windowRemoved(win);
        win->deleteLater();
    });
}
```

### `main.cpp` (C++ path)

```cpp
#include <QGuiApplication>
#include "compositor.h"

int main(int argc, char *argv[])
{
    QGuiApplication app(argc, argv);
    MyCompositor compositor;
    compositor.create();
    return app.exec();
}
```

---

## 107.5 XDG Shell: Toplevels, Popups, and Positioners

The XDG shell protocol is the baseline for all modern desktop apps. qtwayland exposes it through `QWaylandXdgShell` and its related types.

### Toplevel State Machine

```cpp
// Send activation (focus) to a toplevel
void activateToplevel(QWaylandXdgToplevel *toplevel)
{
    QList<QWaylandXdgToplevel::State> states = {
        QWaylandXdgToplevel::State::Activated
    };
    toplevel->sendConfigure(toplevel->sizeForResize(
        toplevel->surface()->destinationSize(),
        QWaylandXdgToplevel::ResizeEdge::None),
        states);
}

// Maximize a window
void maximizeToplevel(QWaylandXdgToplevel *toplevel,
                      const QRect &screenGeometry)
{
    QList<QWaylandXdgToplevel::State> states = {
        QWaylandXdgToplevel::State::Activated,
        QWaylandXdgToplevel::State::Maximized
    };
    toplevel->sendConfigure(screenGeometry.size(), states);
    toplevel->sendMaximized(screenGeometry.size());
}
```

### Popups and Positioner

Popups (context menus, tooltips, combo-box dropdowns) use a `QWaylandXdgPositioner` to declare their desired position relative to their parent:

```cpp
void MyCompositor::onPopupCreated(QWaylandXdgPopup *popup,
                                  QWaylandXdgSurface *)
{
    const QWaylandXdgPositioner positioner = popup->positioner();
    QRect anchorRect = positioner.anchorRect();
    Qt::Edges anchor  = positioner.anchorEdges();
    Qt::Edges gravity = positioner.gravityEdges();

    // Compute final position honoring the positioner constraints
    QPoint pos = computePopupPosition(popup->parentXdgSurface(),
                                      anchorRect, anchor, gravity);

    popup->sendConfigure({pos, popup->surface()->destinationSize()});
}
```

In QML the handling is simpler — `XdgShell` emits `popupCreated` and `ShellSurfaceItem` positions itself relative to its parent `ShellSurfaceItem` automatically when `parentSurfaceItem` is set:

```qml
XdgShell {
    onToplevelCreated: (toplevel, surface) => { /* ... */ }

    onPopupCreated: (popup, surface) => {
        var parentItem = findSurfaceItem(popup.parentXdgSurface)
        var comp = Qt.createComponent("Popup.qml")
        comp.createObject(parentItem, {
            shellSurface: surface,
            parentSurfaceItem: parentItem
        })
    }
}
```

---

## 107.6 Input Handling

### Keyboard Focus

```cpp
// Give keyboard focus to a surface
void MyCompositor::focusSurface(QWaylandSurface *surface)
{
    QWaylandSeat *seat = defaultSeat();
    if (!surface) {
        seat->setKeyboardFocus(nullptr);
        return;
    }
    seat->setKeyboardFocus(surface);

    // Also send wl_keyboard.enter with current modifier state
    // (Qt handles this automatically when setKeyboardFocus is called)
}
```

### Pointer Events

`QWaylandSeat` converts Qt mouse events (delivered to your `QWindow`) into Wayland pointer events for the focused surface:

```cpp
// In your QOpenGLWindow subclass:
void CompositorWindow::mousePressEvent(QMouseEvent *event)
{
    QWaylandSeat *seat = m_compositor->defaultSeat();
    QWaylandView *view = viewAt(event->position());
    if (!view) return;

    seat->setMouseFocus(view);
    seat->sendMousePressEvent(event->button());
}

void CompositorWindow::mouseMoveEvent(QMouseEvent *event)
{
    QWaylandSeat *seat = m_compositor->defaultSeat();
    QWaylandView *view = viewAt(event->position());
    if (view) {
        // Convert from compositor coords to surface-local coords
        QPointF localPos = view->mapToSurface(event->position());
        seat->sendMouseMoveEvent(view, localPos, event->position());
    }
}

void CompositorWindow::wheelEvent(QWheelEvent *event)
{
    m_compositor->defaultSeat()->sendMouseWheelEvent(
        event->orientation(), event->delta());
}
```

In the QML path, `ShellSurfaceItem` handles all of this automatically. The C++ path is only necessary when you render surfaces via a custom OpenGL pipeline outside the Qt Quick scene graph.

### Touch Input

```cpp
void CompositorWindow::touchEvent(QTouchEvent *event)
{
    QWaylandSeat *seat = m_compositor->defaultSeat();
    const auto &points = event->points();
    for (const QEventPoint &pt : points) {
        switch (pt.state()) {
        case QEventPoint::Pressed:
            seat->sendTouchPointPressed(defaultOutput(),
                pt.id(), pt.position());
            break;
        case QEventPoint::Updated:
            seat->sendTouchPointMoved(defaultOutput(),
                pt.id(), pt.position());
            break;
        case QEventPoint::Released:
            seat->sendTouchPointReleased(defaultOutput(),
                pt.id(), pt.position());
            break;
        default: break;
        }
    }
    seat->sendTouchFrameEvent(defaultOutput());
}
```

### Drag-and-Drop

`QWaylandDataDevice` (exposed through `QWaylandSeat::dataDevice()`) implements the `wl_data_device` protocol. Qt routes drag events to the correct surface automatically when you use `ShellSurfaceItem`. For the C++ path, connect to `QWaylandDataSource` signals on the seat and forward drop events:

```cpp
connect(seat->dataDevice(), &QWaylandDataDevice::dragStarted,
    this, [this](QWaylandDrag *drag) {
        // drag->origin() — surface that initiated the drag
        // drag->icon()   — drag icon surface (optional)
        m_activeDrag = drag;
    });
```

---

## 107.7 Multi-Output and HiDPI

### Multiple Outputs

Create one `QWaylandOutput` per physical screen. Each gets its own `QWindow` (or `QScreen`-mapped window):

```cpp
void MyCompositor::addOutput(QScreen *screen)
{
    auto *window = new QOpenGLWindow;
    window->setScreen(screen);
    window->showFullScreen();

    auto *output = new QWaylandOutput(this, window);
    output->setPosition(screen->geometry().topLeft());
    output->setMode({screen->size(), qRound(screen->refreshRate() * 1000)});

    // Scale factor for HiDPI
    output->setScaleFactor(qRound(screen->devicePixelRatio()));

    m_outputs.append(output);
}
```

### Scale Factor and Buffer Transform

qtwayland propagates `wl_output.scale` to clients automatically when you set `setScaleFactor()`. Clients that support buffer scaling will send double-resolution buffers on 2× outputs. For non-integer scales (e.g., 1.5×), the `wp_fractional_scale_v1` protocol extension is available in Qt 6.6+:

```cpp
// Qt 6.6+
auto *fractionalScale = new QWaylandFractionalScaleManagerV1(this);
// Per-output fractional scale is set via QWaylandOutput::setScaleFactor
// with fractional values; Qt handles the protocol details
```

### Output Transforms

```cpp
// Rotate output 90° for a portrait monitor
output->setTransform(QWaylandOutput::Transform90);
// Options: TransformNormal, Transform90, Transform180, Transform270,
//          TransformFlipped, TransformFlipped90, etc.
```

---

## 107.8 Layer-Shell (wlr-layer-shell-v1)

The `wlr-layer-shell-unstable-v1` protocol — essential for bars, lock screens, and overlays — is available in Qt 6.3+ via `QWaylandLayerShellV1`:

```cpp
#include <QWaylandLayerShellV1>

// In compositor create():
m_layerShell = new QWaylandLayerShellV1(this);
connect(m_layerShell, &QWaylandLayerShellV1::layerSurfaceCreated,
        this, &MyCompositor::onLayerSurface);
```

```cpp
void MyCompositor::onLayerSurface(QWaylandLayerSurfaceV1 *layerSurface)
{
    using Layer = QWaylandLayerShellV1::Layer;
    using Anchor = QWaylandLayerSurfaceV1::Anchor;

    Layer layer   = layerSurface->layer();   // Background/Bottom/Top/Overlay
    Anchor anchor = layerSurface->anchors();
    int exclusiveZone = layerSurface->exclusiveZone();

    // Compute placement on the output
    QRect outputGeometry = layerSurface->output()
                               ? layerSurface->output()->geometry()
                               : defaultOutput()->geometry();

    QRect placement = computeLayerPlacement(outputGeometry,
                                            anchor,
                                            layerSurface->size(),
                                            exclusiveZone);

    // Acknowledge the surface and confirm its geometry
    layerSurface->sendConfigure(placement.size());
}
```

In QML, use the `LayerShell` extension type:

```qml
import QtWayland.Compositor
import QtWayland.Compositor.LayerShell   // Qt 6.3+

WaylandCompositor {
    // ... outputs, XdgShell ...

    LayerShell {
        onLayerSurfaceCreated: (layerSurface) => {
            var comp = Qt.createComponent("LayerSurfaceItem.qml")
            comp.createObject(layerRoot, { layerSurface: layerSurface })
        }
    }
}
```

```qml
// LayerSurfaceItem.qml
import QtQuick
import QtWayland.Compositor.LayerShell

Item {
    required property var layerSurface

    WaylandQuickItem {
        id: surfaceView
        surface: layerSurface.surface
        anchors.fill: parent
    }

    // Position the item based on anchors from the protocol
    Component.onCompleted: {
        var a = layerSurface.anchors
        if (a & LayerSurfaceV1.AnchorTop)    anchors.top    = parent.top
        if (a & LayerSurfaceV1.AnchorBottom) anchors.bottom = parent.bottom
        if (a & LayerSurfaceV1.AnchorLeft)   anchors.left   = parent.left
        if (a & LayerSurfaceV1.AnchorRight)  anchors.right  = parent.right
        layerSurface.sendConfigure(Qt.size(width, height))
    }
}
```

### IVI Application Shell (Automotive/Embedded)

For embedded and automotive targets, Qt ships the IVI application shell protocol (`ivi-application`). Use `QWaylandIviApplication` and `QWaylandIviSurface`:

```cpp
#include <QWaylandIviApplication>

// In create():
auto *ivi = new QWaylandIviApplication(this);
connect(ivi, &QWaylandIviApplication::iviSurfaceCreated,
        this, [this](QWaylandIviSurface *surface) {
            uint32_t iviId = surface->iviId();
            // Place surface according to HMI layout policy for this iviId
            auto *view = new QWaylandView(surface->surface(), this);
            Q_UNUSED(view);
        });
```

---

## 107.9 Custom Protocol Extensions

The `QWaylandCompositorExtension` base class makes it straightforward to implement custom or unstable protocols without leaving the Qt object model. The process mirrors Ch 46 but the glue code is generated by Qt's `qtwaylandscanner` tool (bundled with Qt) rather than raw `wayland-scanner`.

### Step 1: Protocol XML

Write your protocol XML following the Wayland extension conventions:

```xml
<!-- protocol/my-tiling-v1.xml -->
<protocol name="my_tiling_v1">
  <interface name="my_tiling_manager_v1" version="1">
    <request name="set_tiling_layout">
      <arg name="surface" type="object" interface="wl_surface"/>
      <arg name="layout"  type="uint"/>
    </request>
    <event name="layout_changed">
      <arg name="layout" type="uint"/>
    </event>
  </interface>
</protocol>
```

### Step 2: CMake Integration

```cmake
find_package(Qt6 REQUIRED COMPONENTS WaylandCompositor)

qt6_generate_wayland_protocol_server_sources(mycompositor
    FILES protocol/my-tiling-v1.xml
)
# This generates:
#   qwayland-server-my-tiling-v1.h
#   qwayland-server-my-tiling-v1.cpp
# and adds them to the mycompositor target automatically.
```

### Step 3: C++ Implementation

```cpp
#include "qwayland-server-my-tiling-v1.h"
#include <QWaylandCompositorExtensionTemplate>
#include <QWaylandQuickExtension>

class MyTilingManager
    : public QWaylandCompositorExtensionTemplate<MyTilingManager>
    , public QtWaylandServer::my_tiling_manager_v1
{
    Q_OBJECT
    QML_ELEMENT
public:
    explicit MyTilingManager(QWaylandCompositor *compositor = nullptr)
        : QWaylandCompositorExtensionTemplate<MyTilingManager>(compositor)
    {}

    void initialize() override {
        QWaylandCompositorExtensionTemplate<MyTilingManager>::initialize();
        QWaylandCompositor *compositor = this->compositor();
        init(compositor->display(), 1);  // bind protocol, version 1
    }

signals:
    void tilingLayoutRequested(QWaylandSurface *surface, uint32_t layout);

protected:
    // Generated stub — called when client sends set_tiling_layout
    void my_tiling_manager_v1_set_tiling_layout(Resource *resource,
                                                 wl_resource *surface_resource,
                                                 uint32_t layout) override
    {
        auto *surface = QWaylandSurface::fromResource(surface_resource);
        emit tilingLayoutRequested(surface, layout);
    }
};
```

### Step 4: Use in QML

```qml
WaylandCompositor {
    MyTilingManager {
        id: tilingManager
        onTilingLayoutRequested: (surface, layout) => {
            applyLayout(surface, layout)
        }
    }
}
```

---

## 107.10 Rendering Architecture

### Qt Quick Scene Graph (default)

`ShellSurfaceItem` and `WaylandQuickItem` participate in Qt Quick's scene graph. Composition happens on the render thread; damage from client buffers triggers incremental texture uploads and partial repaints. This is the right choice for compositors with animated UI elements (blur effects, spring animations, translucent panels).

```qml
ShellSurfaceItem {
    shellSurface: xdgSurface

    // Scene graph layer effects
    layer.enabled: true
    layer.effect: ShaderEffect {
        property real radius: 8
        // ... blur/shadow shader ...
    }

    // Spring animation on window open
    scale: 0.0
    Component.onCompleted: {
        scaleAnimation.start()
    }
    NumberAnimation on scale {
        id: scaleAnimation
        to: 1.0
        duration: 180
        easing.type: Easing.OutBack
    }
}
```

### Custom OpenGL Renderer (C++ path)

For compositors with a custom render pipeline, subclass `QOpenGLWindow` and drive rendering manually:

```cpp
void CompositorWindow::paintGL()
{
    QOpenGLFunctions *gl = QOpenGLContext::currentContext()->functions();
    gl->glClearColor(0.12f, 0.12f, 0.18f, 1.0f);
    gl->glClear(GL_COLOR_BUFFER_BIT);

    for (XdgWindow *win : m_compositor->windows()) {
        QWaylandSurface *surface = win->xdgSurface->surface();
        if (!surface->isMapped()) continue;

        // Acquire the buffer attached to this surface
        QWaylandBufferRef buf = surface->currentBuffer();
        if (!buf.hasBuffer()) continue;

        // Create or reuse a texture for this buffer
        auto *texture = buf.toOpenGLTexture();
        if (!texture) continue;

        texture->bind();
        drawQuad(win->geometry);  // your rendering code
        texture->release();

        // Mark the buffer as consumed so the client can reuse it
        surface->sendFrameCallbacks();
    }
}
```

### Explicit Synchronization (Qt 6.5+)

On AMD and Intel GPUs, explicit synchronization (`linux-drm-syncobj-v1`) eliminates GPU-CPU stalls when swapping buffers. Qt 6.5 adds compositor-side support; opt in at compositor creation:

```cpp
// Qt 6.5+
auto *explicitSync = new QWaylandLinuxDrmSyncobjManagerV1(this);
Q_UNUSED(explicitSync);  // auto-negotiated with clients that support it
```

---

## 107.11 XWayland Integration

qtwayland does not ship an XWayland manager, but you can integrate one by spawning `Xwayland` as a child process and connecting to its Wayland socket the same way any other client connects:

```cpp
void MyCompositor::startXwayland()
{
    // The XWM socket pair — used by Xwayland to communicate with
    // the compositor's X window manager component
    int wmFds[2];
    socketpair(AF_UNIX, SOCK_STREAM, 0, wmFds);

    m_xwaylandProcess = new QProcess(this);
    m_xwaylandProcess->setProgram("Xwayland");
    m_xwaylandProcess->setArguments({
        ":1",
        "-rootless",
        "-wm", QString::number(wmFds[0]),
        "-listenfd", QString::number(/* display fd */ 0),
    });

    // Inherit the compositor's Wayland socket in Xwayland's env
    QProcessEnvironment env = QProcessEnvironment::systemEnvironment();
    env.insert("WAYLAND_DISPLAY", socketName());
    m_xwaylandProcess->setProcessEnvironment(env);
    m_xwaylandProcess->start();

    // Use the WM fd (wmFds[1]) with an XCB connection
    // to implement the XWMICCCM/EWMH window manager protocol
    // See xcb_connect_to_fd() in libxcb
    close(wmFds[0]);
    m_xcbConn = xcb_connect_to_fd(wmFds[1], nullptr);
}
```

Full XWayland integration requires implementing the X11 WM protocol over XCB alongside the Wayland protocol — this is non-trivial. For compositors that must support legacy X11 applications, consider starting from an existing implementation (e.g., adopt Sway's XWayland code or use the `xwayland-satellite` standalone XWM daemon that works with any Wayland compositor).

---

## 107.12 Testing and Debugging

### Test Backend (Headless)

Use Qt's `offscreen` platform plugin to run your compositor in CI without a display:

```bash
QT_QPA_PLATFORM=offscreen ./mycompositor &
WAYLAND_DISPLAY=wayland-my weston-terminal &
sleep 2
kill %1 %2
```

For automated integration tests, use `QWaylandTestCompositor` patterns from Qt's own test suite (`qtwayland/tests/`):

```cpp
class TestCompositor : public QWaylandCompositor {
public:
    TestCompositor() { create(); }
    void processEvents() {
        QCoreApplication::processEvents();
        flushClients();
    }
};

void TestCase::testToplevelCreate()
{
    TestCompositor compositor;
    QWaylandXdgShell shell(&compositor);
    QWaylandXdgToplevel *received = nullptr;
    QObject::connect(&shell, &QWaylandXdgShell::toplevelCreated,
                     [&](auto *tl, auto *) { received = tl; });

    // Simulate a client creating a toplevel
    WaylandTestClient client(compositor.socketName());
    client.createXdgToplevel();

    compositor.processEvents();
    QVERIFY(received != nullptr);
}
```

### Wayland Debug Logging

```bash
# Qt-side Wayland debug output
QT_LOGGING_RULES="qt.wayland.compositor*=true" ./mycompositor 2>&1 | less

# Wire-level protocol tracing (all Wayland traffic)
WAYLAND_DEBUG=1 WAYLAND_DISPLAY=wayland-my foot 2>&1 | grep -v wl_display

# Qt scene graph debug (render thread, frame timing)
QSG_INFO=1 QSG_RENDER_TIMING=1 ./mycompositor
```

### Common Issues

| Symptom | Likely cause | Fix |
|---|---|---|
| Black window, no clients connect | Socket not created | Check `$XDG_RUNTIME_DIR`, call `create()` before `app.exec()` |
| Client renders but no input | Seat not created | `new QWaylandSeat(this, Pointer\|Keyboard)` |
| Popup appears at 0,0 | Positioner not consumed | Call `sendConfigure` with computed rect |
| CSD title bars double-rendered | Client draws CSD + compositor draws decorations | Send `XdgToplevel::sendServerSideDecorationMode` or suppress compositor decorations |
| HiDPI surface blurry | Scale factor mismatch | Set `output->setScaleFactor(devicePixelRatio)` |
| App crash on disconnect | Dangling surface pointer | Connect `surface->mappedChanged` and guard use |
| `QT_QPA_PLATFORM=wayland` in compositor env | Qt tries to connect to its own socket | Force `xcb` or `eglfs` before compositor starts |

---

## 107.13 Comparison: Qt vs. wlroots vs. Smithay

| Dimension | **qtwayland** | **wlroots (C)** | **Smithay (Rust)** |
|---|---|---|---|
| Language | QML + C++ | C | Rust |
| UI integration | Native Qt Quick | External (must render separately) | External (smithay-desktop) |
| Protocol coverage | XDG, layer-shell, IVI, text-input, data-device | Extensive (50+ protocols) | Growing (xdg, layer, text-input) |
| XWayland | Manual (no built-in XWM) | Built-in wlr_xwayland | `XWayland` smithay module |
| Rendering | Qt Quick scene graph or custom OpenGL | wlr_scene / wlr_renderer | GlesRenderer / PixmanRenderer |
| DRM/KMS | Via Qt's `eglfs` | wlr_backend (DRM, headless, x11, wayland) | DrmBackend + GbmAllocator |
| libinput | Via Qt's `libinput` QPA plugin | wlr_input_device | LibinputBackend |
| HiDPI | `output->setScaleFactor()` | `wlr_output.scale` | `Output::change_current_state` |
| Test backend | `offscreen` platform | `WLR_BACKENDS=headless` | WinitBackend |
| Production users | KWin (Plasma), gamescope | Sway, Hyprland, Wayfire, River | niri, Jay, cosmic-comp |
| Best for | Qt-native UI compositors, embedded/kiosk | Maximum protocol control, tiling WMs | Memory-safe, Rust-ecosystem compositors |

---

## Summary

qtwayland's compositor module spans the full spectrum from a 60-line QML prototype to a production compositor managing multiple outputs, layer-shell surfaces, custom protocol extensions, and a bespoke render pipeline. The QML path (`WaylandCompositor` + `ShellSurfaceItem`) is uniquely productive for compositors where the window management UI is itself a first-class QML application — think animated docks, blur-behind effects, spring-physics window transitions. The C++ path provides protocol-level control at the cost of more boilerplate, but integrates cleanly with the same Qt event loop and object ownership model.

**Further reading:**
- Qt documentation: `QWaylandCompositor`, `QWaylandXdgShell`, `QWaylandLayerShellV1`
- Qt examples: `qtwayland/examples/wayland/` (pure-QML `minimal-qml`, `overview-compositor`, `ivi-compositor`)
- Ch 47 — wlroots for maximum protocol flexibility
- Ch 48 — Smithay for memory-safe Rust compositors
- Ch 36 — qtwayland from the client side (theming and env vars)
- Ch 46 — Writing and registering Wayland protocol extensions
