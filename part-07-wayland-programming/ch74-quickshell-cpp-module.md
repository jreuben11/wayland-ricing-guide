# Chapter 74 — Writing a Quickshell C++ Module

## Contents

- [Overview](#overview)
- [When to Write a C++ Module](#when-to-write-a-c-module)
- [Module Architecture](#module-architecture)
- [A Minimal Singleton Service: Battery Monitor](#a-minimal-singleton-service-battery-monitor)
- [CMakeLists.txt for the Module](#cmakeliststxt-for-the-module)
- [Using the Module in QML](#using-the-module-in-qml)
- [D-Bus Service Module Pattern](#d-bus-service-module-pattern)
- [Multi-Threaded Module with QThread](#multi-threaded-module-with-qthread)
- [Custom QAbstractListModel for Structured Data](#custom-qabstractlistmodel-for-structured-data)
- [Registering with Quickshell's Build System](#registering-with-quickshells-build-system)
  - [In-Tree Integration](#in-tree-integration)
  - [Out-of-Tree Plugin](#out-of-tree-plugin)
- [Existing Modules as Reference](#existing-modules-as-reference)
- [Contributing Your Module Upstream](#contributing-your-module-upstream)
- [Troubleshooting](#troubleshooting)

---


## Overview

Quickshell is designed from the ground up to be extensible at the C++ layer. Unlike shell-script–based compositors that wrap external processes, Quickshell allows you to write native service modules that live inside the compositor process itself, sharing its event loop and Qt object model. This means zero-latency data delivery to QML, type-safe bindings, and the full power of Qt's signals-and-slots system — all without forking a subprocess or parsing text output.

This chapter covers the full lifecycle of authoring a Quickshell C++ module: directory layout and naming conventions, writing C++ classes that expose themselves to QML as singletons, integrating with inotify through `QFileSystemWatcher`, wrapping D-Bus interfaces, threading safely, and finally building and installing your module either in-tree or as a standalone out-of-tree plugin. By the end you will have a reusable template suitable for any system-level data source.

Cross-references: See Ch 53 for Quickshell session startup and IPC. See Ch 71 for QML fundamentals in Quickshell. See Ch 75 for wrapping Wayland protocols in C++. See Ch 80 for contributing modules upstream.

## When to Write a C++ Module

The `Process` and `ShellService` QML types cover the majority of rice use-cases: reading stdout from scripts, polling files, launching daemons. C++ modules add value in a distinct set of situations:

**Kernel-level event sources.** inotify-based `QFileSystemWatcher` reacts to sysfs and procfs changes the moment the kernel delivers the event, without any polling interval. Battery capacity, backlight brightness, and CPU temperature can all be monitored at sub-millisecond latency this way.

**C library bindings.** Libraries like libinput, libpulse, libnl, and libudev expose C APIs that cannot be called from QML or shell scripts without a wrapper. A C++ module provides the correct ownership model (the Qt object owns the C handle, its destructor releases it) and translates raw events into Qt signals.

**Multi-threaded work.** QML runs on a single GUI thread. If you need to perform I/O-bound work — parsing large JSON files, querying SQLite, doing cryptographic operations — you must do it on a worker thread. `QThread` and `QtConcurrent` integrate naturally with `QObject`, and you can post results back to the main thread using `QMetaObject::invokeMethod` or queued connections.

**Custom data types.** When your data has structure — a list of Wi-Fi access points, each with an SSID, BSSID, signal strength, and security flags — you want a proper `QAbstractListModel` subclass, not a flat string you parse in QML. C++ lets you define proper model classes that QML's `ListView` and `Repeater` bind to natively.

| Use Case | QML `Process` | C++ Module |
|---|---|---|
| Simple command output | Yes | Overkill |
| Sysfs polling | Yes (poll interval) | Yes (inotify) |
| D-Bus signals | Via `qdbus` subprocess | Yes (native) |
| C library (libpulse, libnl) | No | Required |
| Multi-threaded I/O | No | Yes |
| Custom list models | No | Yes |
| Zero-subprocess overhead | No | Yes |

## Module Architecture

Every Quickshell module follows a consistent directory structure. Convention matters here because Quickshell's CMake macros rely on predictable source layout, and contributors reviewing your module will look for these files in expected locations.

```
src/services/myservice/
├── myservice.hpp        ← C++ class declaration
├── myservice.cpp        ← implementation
├── myservice.qml        ← optional: pure-QML wrapper or demo
├── qmldir               ← optional: manual module descriptor
└── CMakeLists.txt       ← build rules for this module
```

The C++ class inherits from `QObject` and is exposed to QML via the `QML_ELEMENT` and optionally `QML_SINGLETON` macros. `QML_ELEMENT` registers the class with the QML type system under the URI declared in `CMakeLists.txt`. `QML_SINGLETON` additionally restricts instantiation to a single instance managed by the QML engine — the idiom for service objects that represent unique system resources (there is only one battery, one network adapter, etc.).

The URI scheme mirrors the directory hierarchy by convention: `Quickshell.Services.MyService`. The QML import statement therefore reads `import Quickshell.Services.MyService`, which makes the provenance of the type immediately obvious in QML files.

Header guards should use `#pragma once` rather than traditional include guards — this is consistent with Quickshell's existing codebase and avoids naming collision issues. All Qt-specific macros (`Q_OBJECT`, `Q_PROPERTY`, `Q_INVOKABLE`) must appear inside the class body before any member declarations.

## A Minimal Singleton Service: Battery Monitor

The canonical starting example is reading battery capacity from sysfs. The kernel updates `/sys/class/power_supply/BAT0/capacity` in place, so `QFileSystemWatcher` can monitor it directly. This is faster than a polling timer and has zero CPU overhead when the battery level is not changing.

**battery_fast.hpp**

```cpp
#pragma once
#include <QObject>
#include <QQmlEngine>
#include <QFileSystemWatcher>
#include <QString>

class BatteryFast : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON

    Q_PROPERTY(int level    READ level    NOTIFY levelChanged)
    Q_PROPERTY(bool charging READ charging NOTIFY chargingChanged)
    Q_PROPERTY(QString status READ status NOTIFY statusChanged)

public:
    explicit BatteryFast(QObject* parent = nullptr);

    int level() const    { return mLevel; }
    bool charging() const { return mCharging; }
    QString status() const { return mStatus; }

signals:
    void levelChanged();
    void chargingChanged();
    void statusChanged();

private slots:
    void onFileChanged(const QString& path);

private:
    int mLevel = 0;
    bool mCharging = false;
    QString mStatus;
    QFileSystemWatcher mWatcher;

    void readLevel();
    void readStatus();
    static QString batteryPath(const QString& attr);
};
```

**battery_fast.cpp**

```cpp
#include "battery_fast.hpp"
#include <QFile>
#include <QDir>

static QString batteryBase() {
    // Find the first available battery
    const QDir psDir("/sys/class/power_supply");
    for (const QString& entry : psDir.entryList(QDir::Dirs | QDir::NoDotAndDotDot)) {
        if (entry.startsWith("BAT")) return psDir.absoluteFilePath(entry);
    }
    return "/sys/class/power_supply/BAT0"; // fallback
}

QString BatteryFast::batteryPath(const QString& attr) {
    return batteryBase() + "/" + attr;
}

BatteryFast::BatteryFast(QObject* parent) : QObject(parent) {
    mWatcher.addPath(batteryPath("capacity"));
    mWatcher.addPath(batteryPath("status"));

    connect(&mWatcher, &QFileSystemWatcher::fileChanged,
            this, &BatteryFast::onFileChanged);

    readLevel();
    readStatus();
}

void BatteryFast::readLevel() {
    QFile f(batteryPath("capacity"));
    if (!f.open(QIODevice::ReadOnly)) return;
    const int newLevel = f.readAll().trimmed().toInt();
    if (newLevel != mLevel) {
        mLevel = newLevel;
        emit levelChanged();
    }
}

void BatteryFast::readStatus() {
    QFile f(batteryPath("status"));
    if (!f.open(QIODevice::ReadOnly)) return;
    const QString raw = f.readAll().trimmed();
    const bool newCharging = (raw == "Charging");
    if (raw != mStatus) {
        mStatus = raw;
        emit statusChanged();
    }
    if (newCharging != mCharging) {
        mCharging = newCharging;
        emit chargingChanged();
    }
}

void BatteryFast::onFileChanged(const QString& path) {
    // QFileSystemWatcher may remove the watch after an inotify IN_IGNORED event.
    // Re-add the path to ensure continued monitoring.
    if (!mWatcher.files().contains(path)) {
        mWatcher.addPath(path);
    }
    if (path.endsWith("capacity")) readLevel();
    else readStatus();
}
```

Note the `onFileChanged` re-add pattern: sysfs files can trigger `IN_IGNORED` inotify events when the kernel re-creates the backing data structure internally. `QFileSystemWatcher` interprets this as a file deletion and silently removes the watch. Re-adding the path in the slot restores monitoring.

## CMakeLists.txt for the Module

Qt 6's `qt_add_qml_module` macro handles source file compilation, QML type registration (the `_metatypes.json` and `_qmltypes` files), and module descriptor generation in a single call. You do not need a manual `qmldir` file for pure C++ modules.

```cmake
# src/services/battery_fast/CMakeLists.txt

qt_add_qml_module(quickshell-battery-fast
    URI "Quickshell.Services.BatteryFast"
    VERSION 1.0
    SOURCES
        battery_fast.cpp
        battery_fast.hpp
)

target_link_libraries(quickshell-battery-fast
    PRIVATE
        Qt6::Core
        Qt6::Qml
)

# Expose the include directory to the parent target
target_include_directories(quickshell-battery-fast
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}
)
```

If your module requires additional Qt subsystems, add them to `target_link_libraries`. Common additions:

| Qt Module | CMake Target | Use Case |
|---|---|---|
| Qt6::DBus | Qt6::DBus | D-Bus service integration |
| Qt6::Network | Qt6::Network | HTTP, sockets |
| Qt6::Concurrent | Qt6::Concurrent | Worker thread helpers |
| Qt6::Widgets | Qt6::Widgets | Rarely needed; avoid if possible |
| Qt6::Quick | Qt6::Quick | `QQuickItem` subclasses |

## Using the Module in QML

Once built and registered, the singleton is available in any QML file that imports its URI. No instantiation required — the QML engine creates the singleton on first access.

```qml
import QtQuick
import Quickshell.Services.BatteryFast

Item {
    // Simple text indicator
    Text {
        id: batteryText
        text: BatteryFast.level + "%"
        color: BatteryFast.level < 15 ? "#f38ba8"   // red
             : BatteryFast.level < 30 ? "#fab387"   // orange
             : "#a6e3a1"                             // green
    }

    // Icon that changes on charging state
    Text {
        id: batteryIcon
        text: BatteryFast.charging ? "" : ""
        font.family: "Font Awesome 6 Free"
        color: batteryText.color
    }

    // Tooltip with detailed status
    ToolTip.visible: hoverHandler.hovered
    ToolTip.text: "Battery: " + BatteryFast.level + "% (" + BatteryFast.status + ")"

    HoverHandler { id: hoverHandler }
}
```

Because `BatteryFast` is a `QML_SINGLETON`, you reference it by its class name directly — there is no `id` to assign. All bound properties update reactively via the signals declared with `NOTIFY`.

## D-Bus Service Module Pattern

Many system services on modern Linux (NetworkManager, UPower, BlueZ, PipeWire) expose their state over D-Bus. Qt's `QtDBus` module provides generated proxy classes from introspection XML, making it straightforward to write strongly-typed bindings.

**Step 1: Generate the proxy class from introspection XML**

```bash
# Dump the introspection XML for a D-Bus service
qdbus --system org.freedesktop.NetworkManager \
    /org/freedesktop/NetworkManager \
    org.freedesktop.DBus.Introspectable.Introspect \
    > nm_introspect.xml

# Generate a C++ proxy class
qdbusxml2cpp -c NetworkManagerProxy -p nm_proxy \
    nm_introspect.xml
```

This produces `nm_proxy.h` and `nm_proxy.cpp` — Qt classes you include directly in your module.

**network_status.hpp**

```cpp
#pragma once
#include <QObject>
#include <QQmlEngine>
#include <QDBusConnection>
#include "nm_proxy.h"

class NetworkStatus : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON

    Q_PROPERTY(QString ssid        READ ssid        NOTIFY ssidChanged)
    Q_PROPERTY(bool connected      READ connected   NOTIFY connectedChanged)
    Q_PROPERTY(int signalStrength  READ signalStrength NOTIFY signalStrengthChanged)

public:
    explicit NetworkStatus(QObject* parent = nullptr);

    QString ssid()         const { return mSsid; }
    bool connected()       const { return mConnected; }
    int signalStrength()   const { return mSignalStrength; }

signals:
    void ssidChanged();
    void connectedChanged();
    void signalStrengthChanged();

private slots:
    void onStateChanged(uint newState, uint oldState, uint reason);
    void refresh();

private:
    OrgFreedesktopNetworkManagerInterface* mNM = nullptr;
    QString mSsid;
    bool mConnected = false;
    int mSignalStrength = 0;
};
```

**network_status.cpp**

```cpp
#include "network_status.hpp"
#include <QDBusObjectPath>

NetworkStatus::NetworkStatus(QObject* parent) : QObject(parent) {
    mNM = new OrgFreedesktopNetworkManagerInterface(
        "org.freedesktop.NetworkManager",
        "/org/freedesktop/NetworkManager",
        QDBusConnection::systemBus(),
        this
    );

    connect(mNM, &OrgFreedesktopNetworkManagerInterface::StateChanged,
            this, &NetworkStatus::onStateChanged);

    refresh();
}

void NetworkStatus::onStateChanged(uint newState, uint /*oldState*/, uint /*reason*/) {
    Q_UNUSED(newState);
    refresh();
}

void NetworkStatus::refresh() {
    // NM connectivity states: 70 = FULL, 60 = LIMITED, etc.
    const bool nowConnected = (mNM->connectivity() >= 70);
    if (nowConnected != mConnected) {
        mConnected = nowConnected;
        emit connectedChanged();
    }
    // Fetching active SSID requires traversing ActiveConnection → AccessPoint
    // omitted here for brevity — see the full example in the companion repo
}
```

The CMakeLists for this module adds `Qt6::DBus` and includes the generated proxy sources:

```cmake
qt_add_qml_module(quickshell-network-status
    URI "Quickshell.Services.NetworkStatus"
    VERSION 1.0
    SOURCES
        network_status.cpp
        network_status.hpp
        nm_proxy.cpp
        nm_proxy.h
)

target_link_libraries(quickshell-network-status
    PRIVATE Qt6::Core Qt6::Qml Qt6::DBus
)
```

## Multi-Threaded Module with QThread

When your module performs blocking I/O — reading large files, querying a database, parsing network responses — you must not do this on the QML GUI thread. The standard Qt pattern is a worker `QObject` moved to a separate `QThread`.

```cpp
// threaded_reader.hpp
#pragma once
#include <QObject>
#include <QQmlEngine>
#include <QThread>

class ReaderWorker : public QObject {
    Q_OBJECT
public slots:
    void doWork(const QString& path);
signals:
    void resultReady(const QString& data);
    void errorOccurred(const QString& message);
};

class ThreadedReader : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON

    Q_PROPERTY(QString data READ data NOTIFY dataChanged)

public:
    explicit ThreadedReader(QObject* parent = nullptr);
    ~ThreadedReader();

    QString data() const { return mData; }

    Q_INVOKABLE void fetch(const QString& path);

signals:
    void dataChanged();
    void requestWork(const QString& path);   // connected to worker slot

private:
    QString mData;
    QThread mWorkerThread;
    ReaderWorker* mWorker;

private slots:
    void handleResult(const QString& data);
};
```

```cpp
// threaded_reader.cpp
#include "threaded_reader.hpp"
#include <QFile>

void ReaderWorker::doWork(const QString& path) {
    QFile f(path);
    if (!f.open(QIODevice::ReadOnly)) {
        emit errorOccurred("Cannot open: " + path);
        return;
    }
    // Simulate slow I/O
    emit resultReady(f.readAll());
}

ThreadedReader::ThreadedReader(QObject* parent) : QObject(parent) {
    mWorker = new ReaderWorker;
    mWorker->moveToThread(&mWorkerThread);

    connect(&mWorkerThread, &QThread::finished, mWorker, &QObject::deleteLater);
    connect(this, &ThreadedReader::requestWork, mWorker, &ReaderWorker::doWork);
    connect(mWorker, &ReaderWorker::resultReady, this, &ThreadedReader::handleResult);

    mWorkerThread.start();
}

ThreadedReader::~ThreadedReader() {
    mWorkerThread.quit();
    mWorkerThread.wait();
}

void ThreadedReader::fetch(const QString& path) {
    emit requestWork(path);
}

void ThreadedReader::handleResult(const QString& data) {
    if (data != mData) {
        mData = data;
        emit dataChanged();
    }
}
```

The critical safety rule: never access `mWorker` members directly from the main thread after `moveToThread`. All cross-thread calls must go through signal-slot connections, which Qt automatically queues across thread boundaries.

## Custom QAbstractListModel for Structured Data

When your data is a collection — network interfaces, audio sinks, running processes — expose it as a `QAbstractListModel` subclass rather than a flat string. This enables direct binding to QML's `ListView`, `Repeater`, and `TableView` without any JavaScript parsing.

```cpp
// process_list.hpp
#pragma once
#include <QAbstractListModel>
#include <QQmlEngine>
#include <QVector>

struct ProcessInfo {
    int pid;
    QString name;
    float cpuPercent;
    qint64 rssKb;
};

class ProcessList : public QAbstractListModel {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON

    enum Roles {
        PidRole = Qt::UserRole + 1,
        NameRole,
        CpuRole,
        RssRole,
    };

public:
    explicit ProcessList(QObject* parent = nullptr);

    int rowCount(const QModelIndex& parent = {}) const override;
    QVariant data(const QModelIndex& index, int role = Qt::DisplayRole) const override;
    QHash<int, QByteArray> roleNames() const override;

    Q_INVOKABLE void refresh();

private:
    QVector<ProcessInfo> mProcesses;
    void loadFromProc();
};
```

In QML, the model binds directly:

```qml
import Quickshell.Services.ProcessList

ListView {
    model: ProcessList
    delegate: Row {
        spacing: 8
        Text { text: model.pid }
        Text { text: model.name; width: 160 }
        Text { text: model.cpu.toFixed(1) + "%" }
        Text { text: (model.rss / 1024).toFixed(0) + " MB" }
    }
}
```

## Registering with Quickshell's Build System

### In-Tree Integration

If you are building a fork of Quickshell or contributing a module upstream, add your module's subdirectory to the top-level `CMakeLists.txt`:

```cmake
# In Quickshell's root CMakeLists.txt
add_subdirectory(src/services/battery_fast)
add_subdirectory(src/services/network_status)

target_link_libraries(quickshell
    PRIVATE
        quickshell-battery-fast
        quickshell-network-status
)
```

Rebuild with the standard Quickshell build procedure:

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr \
    -DQT_QML_OUTPUT_DIRECTORY="${CMAKE_BINARY_DIR}/qml"
cmake --build build -j$(nproc)
sudo cmake --install build
```

### Out-of-Tree Plugin

For modules you maintain separately, build as a Qt QML plugin. This does not require touching Quickshell's source tree:

```cmake
# Standalone CMakeLists.txt
cmake_minimum_required(VERSION 3.20)
project(qs-battery-fast CXX)

find_package(Qt6 REQUIRED COMPONENTS Core Qml)
qt_standard_project_setup()

qt_add_qml_module(qs-battery-fast
    URI "Quickshell.Services.BatteryFast"
    VERSION 1.0
    PLUGIN_TARGET qs-battery-fast
    SOURCES battery_fast.cpp battery_fast.hpp
)

target_link_libraries(qs-battery-fast PRIVATE Qt6::Core Qt6::Qml)

include(GNUInstallDirs)
install(TARGETS qs-battery-fast
    LIBRARY DESTINATION "${CMAKE_INSTALL_LIBDIR}/qt6/qml/Quickshell/Services/BatteryFast"
)
install(FILES
    "${CMAKE_CURRENT_BINARY_DIR}/Quickshell/Services/BatteryFast/qmldir"
    "${CMAKE_CURRENT_BINARY_DIR}/Quickshell/Services/BatteryFast/BatteryFast.qmltypes"
    DESTINATION "${CMAKE_INSTALL_LIBDIR}/qt6/qml/Quickshell/Services/BatteryFast"
)
```

Build and install:

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)
sudo cmake --install build
```

After installation, Quickshell discovers the plugin automatically via Qt's QML module search path. No configuration file changes are needed.

## Existing Modules as Reference

Quickshell ships several production-quality modules worth studying before writing your own:

| Module Path | What It Demonstrates |
|---|---|
| `src/services/pipewire/` | C API wrapping (libpipewire), complex object model |
| `src/services/upower/` | D-Bus proxy, UPower battery interface |
| `src/services/mpris/` | D-Bus, MPRIS2 media player control |
| `src/wayland/toplevel_management/` | Wayland protocol extension + QML model |
| `src/io/process.cpp` | Async process I/O with `QProcess` |
| `src/io/datastream.cpp` | Line-oriented async data streaming |

Clone and browse the Quickshell source:

```bash
git clone https://git.outfoxxed.me/quickshell/quickshell.git
cd quickshell
# Grep for the pattern you need
grep -r "QML_SINGLETON" src/services/ --include="*.hpp" -l
grep -r "QDBusInterface" src/ --include="*.hpp" -l
```

## Contributing Your Module Upstream

If your module would benefit the broader Quickshell community, contributing it upstream is straightforward. The maintainers are receptive to well-structured service modules, particularly for common hardware and desktop infrastructure.

**Code style.** The repository includes a `.clang-format` configuration. Run `clang-format -i src/services/myservice/*.cpp src/services/myservice/*.hpp` before committing. The style is based on Qt's coding conventions with a few local modifications (brace placement, pointer alignment).

**Documentation.** Add QDoc-style comments to your public API. Quickshell's documentation is generated from these comments:

```cpp
/*!
 * \qmltype BatteryFast
 * \inqmlmodule Quickshell.Services.BatteryFast
 * \brief Provides real-time battery capacity via inotify.
 *
 * BatteryFast monitors \c /sys/class/power_supply/BAT*/capacity using
 * kernel inotify events rather than polling, giving sub-millisecond
 * update latency with zero idle CPU overhead.
 *
 * \qmlproperty int BatteryFast::level
 * Battery charge level as a percentage (0–100).
 *
 * \qmlproperty bool BatteryFast::charging
 * \c true when the AC adapter is connected and charging.
 */
```

**Testing.** Add a minimal QML test file to `test/services/myservice/test.qml` that instantiates your type and verifies basic property access. Quickshell's CI will run this under `qmltestrunner`.

**Submission.** Fork the repository on Forgejo at `https://git.outfoxxed.me/quickshell/quickshell`, push your branch, and open a merge request. Include a short description of the use case, the system API it wraps, and any known limitations (e.g., requires `BAT0` to exist, only tested on AC97 ACPI).

Alternatively, publish as a standalone AUR package or GitHub repository. Follow the naming convention `qs-<service>` for the package name and `Quickshell.Services.<Service>` for the URI.

## Troubleshooting

**The module is not found at runtime (`module "Quickshell.Services.BatteryFast" is not installed`).**
Check that the `qmldir` file and the plugin `.so` are installed to the correct Qt QML path:
```bash
# Find where Qt expects QML modules
qmake -query QT_INSTALL_QML
# Verify your module is there
ls $(qmake -query QT_INSTALL_QML)/Quickshell/Services/BatteryFast/
```
If missing, re-run `cmake --install` with `sudo` or verify `CMAKE_INSTALL_LIBDIR` matches Qt's expectation.

**`QFileSystemWatcher` stops receiving events after a few changes.**
This is the inotify `IN_IGNORED` issue described in the implementation section. Ensure `onFileChanged` re-adds the path to the watcher when it is no longer listed in `mWatcher.files()`.

**D-Bus proxy methods return empty values or errors.**
Verify the service is running: `qdbus --system org.freedesktop.NetworkManager`. Check that your application has the required D-Bus policy permissions — system bus interfaces often require a policy file in `/etc/dbus-1/system.d/`. For session bus services this is usually not required.

**`QML_SINGLETON` instantiation error: "Cannot create singleton".**
The QML engine requires that singleton types have a public default constructor or a static `create(QQmlEngine*, QJSEngine*)` factory method. Add the factory if your constructor requires arguments:
```cpp
static BatteryFast* create(QQmlEngine*, QJSEngine*) {
    return new BatteryFast(nullptr);
}
```
And register it with `QML_SINGLETON` plus `qmlRegisterSingletonType` if using the older registration API.

**Build fails with "undefined reference to vtable for MyClass".**
The `Q_OBJECT` macro requires `moc` (Meta-Object Compiler) to generate companion code. Ensure your header is listed in the `SOURCES` argument of `qt_add_qml_module` — `cmake` discovers `.hpp` files there and runs `moc` automatically. If building with a raw `Makefile`, run `moc myservice.hpp -o moc_myservice.cpp` and include `moc_myservice.cpp` in your compilation.

**Changes to properties do not update QML bindings.**
Verify that every `Q_PROPERTY` with a `NOTIFY` clause actually emits the named signal when the backing value changes. A common mistake is changing `mLevel` without emitting `levelChanged()`. Add a guard (`if (newVal != mLevel)`) to avoid signal storms, but always emit when the value actually changes.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
