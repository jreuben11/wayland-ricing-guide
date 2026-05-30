# Chapter 126 — Writing a Layer-Shell Client from Scratch

## Contents

- [Overview](#overview)
- [126.1 Protocol Fundamentals](#1261-protocol-fundamentals)
- [126.2 C with gtk4-layer-shell](#1262-c-with-gtk4-layer-shell)
  - [Dependencies](#dependencies)
  - [CMakeLists.txt](#cmakeliststxt)
  - [`main.c` — Clock Bar](#mainc-clock-bar)
- [126.3 Python with PyGObject + gtk4-layer-shell](#1263-python-with-pygobject-gtk4-layer-shell)
- [126.4 Rust with gtk4-rs + gtk4-layer-shell-rs](#1264-rust-with-gtk4-rs-gtk4-layer-shell-rs)
- [126.5 Advanced: Fullscreen Overlay with Click-Through](#1265-advanced-fullscreen-overlay-with-click-through)
- [126.6 Layer Ordering and Compositor Behavior](#1266-layer-ordering-and-compositor-behavior)

---


## Overview

The `zwlr-layer-shell-v1` protocol is the foundation of every status bar, notification popup, lock screen, and desktop overlay on wlroots-based Wayland compositors. Chapter 28 showed you how to *use* layer-shell applications; this chapter shows you how to *write* one — in C using `gtk4-layer-shell`, in Python using the same library via PyGObject, and as a reference in Rust using `gtk4-layer-shell-rs`. By the end you will have a working clock overlay in all three languages that anchors to the top-right corner of the screen, reserves exclusive zone space, and responds to click events.

**Cross-references:** Ch 03 — protocol extensions overview (layer-shell is an extension to xdg-shell). Ch 46 — writing protocol extensions. Ch 29 — notification daemons (use layer-shell). Ch 107 — Qt/qtwayland compositor (layer-shell from the compositor side).

---

## 126.1 Protocol Fundamentals

A layer-shell surface is created by wrapping a `wl_surface` in a `zwlr_layer_surface_v1` object. The key parameters set at creation:

| Parameter | Type | Description |
|---|---|---|
| `output` | `wl_output` (or null) | Target monitor (null = compositor chooses) |
| `layer` | enum | `background`, `bottom`, `top`, `overlay` |
| `namespace` | string | Identifier string (e.g., `"mybar"`) |

After creation, configure the surface with:
- `set_anchor` — which screen edges to anchor to (flags: top, bottom, left, right)
- `set_size` — pixel size (0 = stretch along anchored axis)
- `set_exclusive_zone` — pixels to reserve (positive = reserve space, -1 = ignore other zones)
- `set_keyboard_interactivity` — none, on-demand, exclusive

The compositor sends a `configure` event with the confirmed size; the client must `ack_configure` before committing the first buffer.

---

## 126.2 C with gtk4-layer-shell

### Dependencies

```bash
# Arch Linux
sudo pacman -S gtk4 gtk4-layer-shell

# Ubuntu 24.04+
sudo apt install libgtk-4-dev libgtk4-layer-shell-dev

# pkg-config names
# gtk4
# gtk4-layer-shell-0
```

### CMakeLists.txt

```cmake
cmake_minimum_required(VERSION 3.20)
project(clock-bar C)
find_package(PkgConfig REQUIRED)
pkg_check_modules(GTK4 REQUIRED gtk4)
pkg_check_modules(LAYER REQUIRED gtk4-layer-shell-0)

add_executable(clock-bar main.c)
target_include_directories(clock-bar PRIVATE ${GTK4_INCLUDE_DIRS} ${LAYER_INCLUDE_DIRS})
target_link_libraries(clock-bar PRIVATE ${GTK4_LIBRARIES} ${LAYER_LIBRARIES})
target_compile_options(clock-bar PRIVATE ${GTK4_CFLAGS_OTHER} ${LAYER_CFLAGS_OTHER})
```

### `main.c` — Clock Bar

```c
#include <gtk/gtk.h>
#include <gtk4-layer-shell.h>
#include <time.h>

static GtkWidget *clock_label;

static gboolean update_clock(gpointer data) {
    time_t now = time(NULL);
    struct tm *tm_info = localtime(&now);
    char buf[32];
    strftime(buf, sizeof(buf), "%H:%M:%S  %a %d %b", tm_info);
    gtk_label_set_text(GTK_LABEL(clock_label), buf);
    return G_SOURCE_CONTINUE;
}

static void activate(GtkApplication *app, gpointer user_data) {
    GtkWidget *window = gtk_application_window_new(app);

    /* ── Layer-shell setup ─────────────────────────────── */
    gtk_layer_init_for_window(GTK_WINDOW(window));
    gtk_layer_set_layer(GTK_WINDOW(window), GTK_LAYER_SHELL_LAYER_TOP);
    gtk_layer_set_namespace(GTK_WINDOW(window), "clock-bar");

    /* Anchor to top-right corner */
    gtk_layer_set_anchor(GTK_WINDOW(window), GTK_LAYER_SHELL_EDGE_TOP, TRUE);
    gtk_layer_set_anchor(GTK_WINDOW(window), GTK_LAYER_SHELL_EDGE_RIGHT, TRUE);

    /* Reserve 36px at the top */
    gtk_layer_set_exclusive_zone(GTK_WINDOW(window), 36);

    /* Margins from edges */
    gtk_layer_set_margin(GTK_WINDOW(window), GTK_LAYER_SHELL_EDGE_TOP, 0);
    gtk_layer_set_margin(GTK_WINDOW(window), GTK_LAYER_SHELL_EDGE_RIGHT, 0);

    /* Do not accept keyboard input */
    gtk_layer_set_keyboard_mode(GTK_WINDOW(window),
                                GTK_LAYER_SHELL_KEYBOARD_MODE_NONE);

    /* ── Widget content ────────────────────────────────── */
    clock_label = gtk_label_new("");
    gtk_widget_set_margin_start(clock_label, 16);
    gtk_widget_set_margin_end(clock_label, 16);
    gtk_window_set_child(GTK_WINDOW(window), clock_label);
    gtk_window_set_default_size(GTK_WINDOW(window), 280, 36);

    /* Apply CSS */
    GtkCssProvider *css = gtk_css_provider_new();
    gtk_css_provider_load_from_string(css,
        "window { background: rgba(26,27,38,0.92); }"
        "label  { color: #7dcfff; font-family: 'JetBrains Mono'; "
        "         font-size: 14px; font-weight: bold; }");
    gtk_style_context_add_provider_for_display(
        gtk_widget_get_display(window),
        GTK_STYLE_PROVIDER(css),
        GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);

    /* Start clock updates */
    update_clock(NULL);
    g_timeout_add_seconds(1, update_clock, NULL);

    gtk_widget_set_visible(window, TRUE);
}

int main(int argc, char *argv[]) {
    GtkApplication *app = gtk_application_new("com.example.clock-bar",
                                              G_APPLICATION_DEFAULT_FLAGS);
    g_signal_connect(app, "activate", G_CALLBACK(activate), NULL);
    int status = g_application_run(G_APPLICATION(app), argc, argv);
    g_object_unref(app);
    return status;
}
```

Build and run:
```bash
cmake -B build && cmake --build build
./build/clock-bar
```

---

## 126.3 Python with PyGObject + gtk4-layer-shell

```python
#!/usr/bin/env python3
"""Layer-shell clock bar in Python."""
import gi
import time

gi.require_version("Gtk",          "4.0")
gi.require_version("Gdk",          "4.0")
gi.require_version("GtkLayerShell","0.1")

from gi.repository import Gtk, GLib, GtkLayerShell, Gdk

class ClockBar(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)

        # ── Layer-shell setup ────────────────────────────
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_namespace(self, "clock-bar-python")

        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP,   True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)

        GtkLayerShell.set_exclusive_zone(self, 36)
        GtkLayerShell.set_keyboard_mode(
            self, GtkLayerShell.KeyboardMode.NONE)

        # ── CSS ─────────────────────────────────────────
        css = Gtk.CssProvider()
        css.load_from_string("""
            window { background: rgba(26,27,38,0.92); }
            label  { color: #7dcfff;
                     font-family: 'JetBrains Mono';
                     font-size: 14px;
                     font-weight: bold;
                     margin: 0 16px; }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        # ── Widgets ──────────────────────────────────────
        self.label = Gtk.Label()
        self.set_child(self.label)
        self.set_default_size(280, 36)
        self._update_clock()
        GLib.timeout_add_seconds(1, self._update_clock)
        self.set_visible(True)

    def _update_clock(self):
        self.label.set_text(time.strftime("%H:%M:%S  %a %d %b"))
        return GLib.SOURCE_CONTINUE

class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.example.clock-bar-python")

    def do_activate(self):
        ClockBar(self)

if __name__ == "__main__":
    App().run()
```

Run:
```bash
pip install pygobject   # if needed
python3 clock_bar.py
```

---

## 126.4 Rust with gtk4-rs + gtk4-layer-shell-rs

```toml
# Cargo.toml
[dependencies]
gtk4 = { version = "0.9", features = ["v4_14"] }
gtk4-layer-shell = "0.4"
glib = "0.20"
```

```rust
// src/main.rs
use gtk4::prelude::*;
use gtk4::{Application, ApplicationWindow, CssProvider, Label};
use gtk4_layer_shell::{Edge, KeyboardMode, Layer, LayerShell};
use glib::timeout_add_seconds_local;
use std::time::{SystemTime, UNIX_EPOCH};

fn format_time() -> String {
    // Use chrono in production; inline for zero-dependency example
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH).unwrap().as_secs();
    let h = (secs / 3600) % 24;
    let m = (secs / 60) % 60;
    let s = secs % 60;
    format!("{:02}:{:02}:{:02}", h, m, s)
}

fn build_ui(app: &Application) {
    let window = ApplicationWindow::builder()
        .application(app)
        .default_width(220)
        .default_height(36)
        .build();

    // Layer-shell setup
    window.init_layer_shell();
    window.set_layer(Layer::Top);
    window.set_namespace("clock-bar-rust");
    window.set_anchor(Edge::Top,   true);
    window.set_anchor(Edge::Right, true);
    window.set_exclusive_zone(36);
    window.set_keyboard_mode(KeyboardMode::None);

    // CSS
    let css = CssProvider::new();
    css.load_from_string(
        "window { background: rgba(26,27,38,0.92); } \
         label  { color: #7dcfff; font-family: 'JetBrains Mono'; \
                  font-size: 14px; font-weight: bold; margin: 0 16px; }"
    );
    gtk4::style_context_add_provider_for_display(
        &gtk4::gdk::Display::default().unwrap(),
        &css,
        gtk4::STYLE_PROVIDER_PRIORITY_APPLICATION,
    );

    // Clock label
    let label = Label::new(Some(&format_time()));
    window.set_child(Some(&label));
    window.present();

    // Update every second
    timeout_add_seconds_local(1, move || {
        label.set_text(&format_time());
        glib::ControlFlow::Continue
    });
}

fn main() {
    let app = Application::builder()
        .application_id("com.example.clock-bar-rust")
        .build();
    app.connect_activate(build_ui);
    app.run();
}
```

Build:
```bash
cargo build --release
./target/release/clock-bar-rust
```

---

## 126.5 Advanced: Fullscreen Overlay with Click-Through

A layer-shell overlay that covers the entire screen but passes pointer events through to windows underneath:

```c
/* In the activate callback — no widget handles input, window is transparent */
gtk_layer_set_layer(GTK_WINDOW(window), GTK_LAYER_SHELL_LAYER_OVERLAY);
gtk_layer_set_anchor(GTK_WINDOW(window), GTK_LAYER_SHELL_EDGE_TOP,    TRUE);
gtk_layer_set_anchor(GTK_WINDOW(window), GTK_LAYER_SHELL_EDGE_BOTTOM, TRUE);
gtk_layer_set_anchor(GTK_WINDOW(window), GTK_LAYER_SHELL_EDGE_LEFT,   TRUE);
gtk_layer_set_anchor(GTK_WINDOW(window), GTK_LAYER_SHELL_EDGE_RIGHT,  TRUE);
gtk_layer_set_exclusive_zone(GTK_WINDOW(window), -1);  // -1 = ignore exclusive zones
gtk_layer_set_keyboard_mode(GTK_WINDOW(window), GTK_LAYER_SHELL_KEYBOARD_MODE_NONE);

/* Make the background transparent */
gtk_widget_set_opacity(window, 0.0);  // for click-through, use input-region = empty
/* Or set an empty input region via the Wayland surface directly */
```

For true click-through (input region = empty), use the `wl_surface.set_input_region` request with an empty region via `wl_compositor.create_region()` + no adds:

```c
/* Get the native wl_surface from GTK */
GdkSurface *gdk_surface = gtk_native_get_surface(GTK_NATIVE(window));
struct wl_surface *wl_surf =
    gdk_wayland_surface_get_wl_surface(GDK_WAYLAND_SURFACE(gdk_surface));

struct wl_region *empty = wl_compositor_create_region(compositor);
wl_surface_set_input_region(wl_surf, empty);
wl_region_destroy(empty);
wl_surface_commit(wl_surf);
```

---

## 126.6 Layer Ordering and Compositor Behavior

| Layer | Z-order | Typical use |
|---|---|---|
| `background` | Below all windows | Wallpaper, desktop widgets |
| `bottom` | Above background, below normal windows | Desktop icons, lower bars |
| `top` | Above all windows, below overlay | Status bars, docks |
| `overlay` | Topmost | Lock screens, notification popups, power menus |

Surfaces on the same layer are ordered by the compositor (usually by creation time, most-recent on top). There is no protocol to explicitly set Z-order within a layer.
