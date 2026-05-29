# Chapter 74 — Writing a Quickshell C++ Module

## Overview
Quickshell is extensible: new service modules are C++ + QML pairs. This chapter
walks through adding a custom service module — from CMake build setup through
exposing a QML singleton.

## Sections

### 74.1 Module Architecture

A Quickshell module has:
```
src/services/myservice/
├── myservice.hpp        ← C++ class declaration
├── myservice.cpp        ← implementation
├── myservice.qml        ← optional: QML wrapper
└── CMakeLists.txt       ← build rules
```

The C++ class inherits from `QObject` and is exposed to QML via `QML_SINGLETON` or
`QML_ELEMENT`. Quickshell's build system handles the rest.

### 74.2 A Minimal Singleton Service

**Example: expose `/sys/class/power_supply/BAT0/capacity` as a QML property**

```cpp
// battery_fast.hpp
#pragma once
#include <QObject>
#include <QQmlEngine>
#include <QFileSystemWatcher>

class BatteryFast : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(int level READ level NOTIFY levelChanged)

public:
    explicit BatteryFast(QObject* parent = nullptr);
    int level() const { return mLevel; }

signals:
    void levelChanged();

private slots:
    void onFileChanged(const QString& path);

private:
    int mLevel = 0;
    QFileSystemWatcher mWatcher;
    void readLevel();
};
```

```cpp
// battery_fast.cpp
#include "battery_fast.hpp"
#include <QFile>

BatteryFast::BatteryFast(QObject* parent) : QObject(parent) {
    mWatcher.addPath("/sys/class/power_supply/BAT0/capacity");
    connect(&mWatcher, &QFileSystemWatcher::fileChanged,
            this, &BatteryFast::onFileChanged);
    readLevel();
}

void BatteryFast::readLevel() {
    QFile f("/sys/class/power_supply/BAT0/capacity");
    if (f.open(QIODevice::ReadOnly)) {
        mLevel = f.readAll().trimmed().toInt();
        emit levelChanged();
    }
}

void BatteryFast::onFileChanged(const QString&) { readLevel(); }
```

### 74.3 CMakeLists.txt

```cmake
qt_add_qml_module(quickshell-battery-fast
    URI "Quickshell.Services.BatteryFast"
    VERSION 1.0
    SOURCES battery_fast.cpp battery_fast.hpp
)

target_link_libraries(quickshell-battery-fast PRIVATE
    Qt6::Core Qt6::Qml
)
```

### 74.4 Using the Module in QML

```qml
import Quickshell.Services.BatteryFast

Text {
    text: BatteryFast.level + "%"
    color: BatteryFast.level < 20 ? "#f38ba8" : "#a6e3a1"
}
```

### 74.5 Process-Based Services (Simpler Alternative)

For most use cases, the `Process` type in QML is sufficient and requires
no C++. Use C++ when:
- You need inotify/kernel-level file watching (faster than polling)
- You're wrapping a C library (libinput, dbus-glib, etc.)
- You need multi-threaded work without blocking the QML thread
- You need custom data types not expressible in QML primitives

### 74.6 D-Bus Service Module Pattern

```cpp
// Uses Qt's D-Bus integration
#include <QDBusConnection>
#include <QDBusInterface>

class NetworkStatus : public QObject {
    Q_OBJECT
    QML_SINGLETON

    Q_PROPERTY(QString ssid READ ssid NOTIFY ssidChanged)
    // ...

    QDBusInterface* mNM;  // NetworkManager D-Bus proxy
};
```

### 74.7 Registering with Quickshell's Build

In Quickshell's source tree, add to the top-level `CMakeLists.txt`:
```cmake
add_subdirectory(src/services/myservice)
target_link_libraries(quickshell PRIVATE quickshell-myservice)
```

Or build as a plugin (out-of-tree):
```cmake
add_library(qs-myservice MODULE ...)
install(TARGETS qs-myservice DESTINATION ${QT_INSTALL_QML}/Quickshell/Services/MyService)
```

### 74.8 Contributing Your Module

If the module would be useful to others:
1. Follow Quickshell's code style (clang-format config in repo)
2. Add documentation comments (`/*!  */` format)
3. Add a test QML file in `test/`
4. Open an MR on Forgejo: https://git.outfoxxed.me/quickshell/quickshell
5. Or publish standalone on GitHub/AUR

### 74.9 Existing Module Source as Reference

Study these existing modules:
- `src/services/pipewire/`: D-Bus + PipeWire C API integration
- `src/services/upower/`: D-Bus interface
- `src/wayland/toplevel_management/`: Wayland protocol + QML
- `src/io/process.cpp`: process management with async I/O
