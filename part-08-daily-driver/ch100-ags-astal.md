# Chapter 100 — AGS / Astal: TypeScript Shell Framework

## Overview

Astal (formerly AGS — Aylur's Gtk Shell) is a Wayland shell framework built on
GTK4 and GJS (GNOME JavaScript). Where Quickshell uses QML/QtQuick, Astal uses
TypeScript compiled to GJS, giving you a typed JS/TS environment with direct
access to GTK widgets, GLib APIs, and a growing library of Wayland-aware
modules. It is the main alternative to Quickshell for users who prefer
JavaScript over QML.

---

## 100.1 Architecture

```
TypeScript source (your config)
    ↓  tsc / esbuild
GJS (GNOME JavaScript runtime)
    ↓
GTK4 widgets + GLib mainloop
    ↓
Layer Shell (gtk4-layer-shell)  →  zwlr-layer-shell-v1
    ↓
Wayland compositor
```

Astal is structured as a monorepo of independent packages:

```
astal/
├── core/           — Astal.Application, Widget, Variable, bind()
├── io/             — Process, File, Socket
├── gtk3/           — GTK3 widget wrappers (legacy)
├── gtk4/           — GTK4 widget wrappers (current)
└── lib/
    ├── hyprland/   — Hyprland IPC client
    ├── mpris/      — MPRIS media player control
    ├── battery/    — UPower battery info
    ├── network/    — NetworkManager client
    ├── bluetooth/  — BlueZ client
    ├── wireplumber/ — PipeWire/WirePlumber audio
    ├── notifd/     — Notification daemon
    ├── tray/       — StatusNotifierItem system tray
    ├── powerprofiles/ — power-profiles-daemon
    └── greet/      — greetd session management
```

---

## 100.2 Installation

```bash
# Arch (AUR)
paru -S astal-git

# Or build from source (recommended for latest features)
git clone https://github.com/aylur/astal
cd astal && meson setup build && ninja -C build install

# Install the TypeScript library
npm install -g astal
# or via the monorepo:
cd astal && npm install && npm run build
```

For TypeScript support:
```bash
paru -S typescript gjs
npm install -g astal @girs/gjs @girs/gtk4-4.0
```

---

## 100.3 Project Structure

```
~/.config/ags/
├── app.ts          ← entry point
├── tsconfig.json
├── package.json
├── widget/
│   ├── Bar.ts
│   ├── Launcher.ts
│   └── NotificationPopup.ts
└── service/
    └── theme.ts
```

```json
// package.json
{
  "name": "my-shell",
  "scripts": {
    "dev": "astal app.ts",
    "build": "tsc && astal app.js"
  },
  "dependencies": {
    "astal": "^0.2.0"
  }
}
```

```json
// tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "bundler",
    "strict": true,
    "paths": {
      "astal/*": ["./node_modules/astal/dist/*"]
    }
  }
}
```

---

## 100.4 Entry Point — `app.ts`

```typescript
import { App } from "astal/gtk4"
import Bar from "./widget/Bar"

App.start({
    main() {
        // Create one bar per monitor
        App.get_monitors().map(Bar)
    },
})
```

Start the shell:
```bash
astal app.ts                # run directly
astal --inspect app.ts      # with GJS inspector
```

---

## 100.5 Creating Windows — Layer Shell

```typescript
import { App, Astal, Gtk, Gdk } from "astal/gtk4"

function Bar(monitor: Gdk.Monitor) {
    const { TOP, LEFT, RIGHT } = Astal.WindowAnchor

    return <window
        className="Bar"
        gdkmonitor={monitor}
        exclusivity={Astal.Exclusivity.EXCLUSIVE}
        anchor={TOP | LEFT | RIGHT}
        application={App}>
        <centerbox>
            <WorkspaceWidget />
            <ClockWidget />
            <SystemTray />
        </centerbox>
    </window>
}
```

| Property | Description |
|----------|-------------|
| `anchor` | `Astal.WindowAnchor` flags: TOP, BOTTOM, LEFT, RIGHT |
| `exclusivity` | `EXCLUSIVE` (reserve space), `NORMAL`, `IGNORE` |
| `layer` | `Astal.Layer`: BACKGROUND, BOTTOM, TOP, OVERLAY |
| `keyboardMode` | `Astal.KeyboardMode`: NONE, ON_DEMAND, EXCLUSIVE |
| `gdkmonitor` | `Gdk.Monitor` to pin the window to |
| `marginTop` etc. | Margins from anchored edges |

---

## 100.6 Reactive Variables

The `Variable` type is Astal's reactive primitive — equivalent to Quickshell's
property binding system:

```typescript
import { Variable, bind } from "astal"
import { Gtk } from "astal/gtk4"

// A simple reactive value
const count = Variable(0)

// Increment on click
const button = <button onClicked={() => count.set(count.get() + 1)}>
    <label label={bind(count).as(n => `Count: ${n}`)} />
</button>

// Derived variable (like a computed property)
const doubled = Variable.derive([count], n => n * 2)

// Poll a command every 2 seconds
const cpuUsage = Variable("0%").poll(2000, "bash -c \"top -bn1 | grep 'Cpu' | awk '{print $2}'\"")

// Watch a file
const wallpaper = Variable("").watch("/tmp/current-wallpaper")
```

### bind()

`bind(obj, prop?)` creates a reactive binding from any GObject property or
Variable:

```typescript
// Bind to a Variable
<label label={bind(myVar)} />

// Bind to a GObject property
<label label={bind(player, "track_title")} />

// Transform the value
<label label={bind(battery, "percentage").as(p => `${Math.round(p * 100)}%`)} />

// Combine multiple bindings
<label label={Variable.derive([title, artist], (t, a) => `${t} — ${a}`)()} />
```

---

## 100.7 Hyprland Module

```typescript
import Hyprland from "gi://AstalHyprland"

const hypr = Hyprland.get_default()

// Workspace bar
function Workspaces() {
    return <box className="Workspaces">
        {bind(hypr, "workspaces").as(wss => wss
            .filter(ws => ws.get_id() > 0)
            .sort((a, b) => a.get_id() - b.get_id())
            .map(ws => <button
                className={bind(hypr, "focused_workspace").as(fw =>
                    ws === fw ? "workspace active" : "workspace"
                )}
                onClicked={() => hypr.dispatch("workspace", String(ws.get_id()))}>
                {ws.get_id()}
            </button>)
        )}
    </box>
}

// Active window title
function WindowTitle() {
    return <label
        className="WindowTitle"
        label={bind(hypr, "focused_client").as(c =>
            c ? (c.get_title() || c.get_class()) : ""
        )}
    />
}
```

### Hyprland IPC dispatch

```typescript
// Dispatch any Hyprland action
hypr.dispatch("exec", "kitty")
hypr.dispatch("workspace", "2")
hypr.dispatch("killactive", "")

// Keyword (live config change)
hypr.set_keyword("general:gaps_out", "20")
hypr.set_keyword("decoration:rounding", "15")
```

---

## 100.8 Audio — WirePlumber Module

```typescript
import Wp from "gi://AstalWp"

const audio = Wp.get_default()?.get_audio()

function VolumeSlider() {
    return <slider
        className="VolumeSlider"
        min={0} max={1}
        value={bind(audio!.get_default_speaker()!, "volume")}
        onChangeValue={({ value }) => {
            audio!.get_default_speaker()!.set_volume(value)
        }}
    />
}

function VolumeButton() {
    const speaker = audio?.get_default_speaker()
    return <button
        className="Volume"
        onClicked={() => speaker?.set_mute(!speaker.get_mute())}
        tooltipText={bind(speaker!, "volume").as(v => `${Math.round(v * 100)}%`)}>
        <image
            iconName={bind(speaker!, "mute").as(m => m
                ? "audio-volume-muted-symbolic"
                : "audio-volume-high-symbolic"
            )}
        />
    </button>
}
```

---

## 100.9 Notifications

```typescript
import Notifd from "gi://AstalNotifd"

const notifd = Notifd.get_default()

// Listen for new notifications
notifd.connect("notified", (_, id) => {
    const notif = notifd.get_notification(id)
    if (!notif) return
    console.log(`[${notif.get_app_name()}] ${notif.get_summary()}`)
    // show popup...
})

// Notification popup component
function NotificationPopup({ id }: { id: number }) {
    const notif = notifd.get_notification(id)!
    return <box className={`Notification urgency-${notif.get_urgency()}`}>
        <image iconName={notif.get_app_icon()} />
        <box vertical>
            <label label={notif.get_summary()} />
            <label label={notif.get_body()} wrap />
        </box>
        <button onClicked={() => notif.dismiss()}>✕</button>
    </box>
}

// Notification history list
function NotificationCenter() {
    return <scrollable vexpand>
        <box vertical>
            {bind(notifd, "notifications").as(ns =>
                ns.map(n => <NotificationPopup id={n.get_id()} />)
            )}
        </box>
    </scrollable>
}
```

---

## 100.10 System Tray

```typescript
import Tray from "gi://AstalTray"

const tray = Tray.get_default()

function SystemTray() {
    return <box className="SystemTray">
        {bind(tray, "items").as(items => items.map(item =>
            <menubutton
                tooltipText={bind(item, "tooltip_markup")}
                menuModel={bind(item, "menu_model")}
                actionGroup={["dbusmenu", item.action_group]}
                onButtonPressEvent={(self, event) => {
                    if (event.get_button()[1] === 1)
                        item.activate(0, 0)
                }}>
                <image gicon={bind(item, "gicon")} pixelSize={16} />
            </menubutton>
        ))}
    </box>
}
```

---

## 100.11 Battery

```typescript
import Battery from "gi://AstalBattery"

const battery = Battery.get_default()

function BatteryWidget() {
    return <box className="Battery"
        visible={bind(battery, "is_present")}>
        <image iconName={bind(battery, "battery_icon_name")} />
        <label label={bind(battery, "percentage").as(p =>
            `${Math.round(p * 100)}%`
        )} />
    </box>
}
```

---

## 100.12 Network

```typescript
import Network from "gi://AstalNetwork"

const network = Network.get_default()

function NetworkWidget() {
    const wifi = network.get_wifi()
    return <button
        className="Network"
        tooltipText={bind(wifi!, "ssid").as(s => s ?? "Not connected")}>
        <image iconName={bind(wifi!, "icon_name")} />
    </button>
}
```

---

## 100.13 Complete Minimal Bar

```typescript
// widget/Bar.ts
import { App, Astal, Gtk, Gdk } from "astal/gtk4"
import { bind } from "astal"
import Hyprland from "gi://AstalHyprland"
import Wp from "gi://AstalWp"
import Battery from "gi://AstalBattery"
import { SystemClock } from "astal"

const hypr = Hyprland.get_default()

function Workspaces() {
    return <box spacing={4}>
        {bind(hypr, "workspaces").as(wss =>
            wss.sort((a, b) => a.get_id() - b.get_id()).map(ws =>
                <button
                    cssClasses={bind(hypr, "focused_workspace").as(fw =>
                        ws === fw ? ["workspace", "active"] : ["workspace"]
                    )}
                    onClicked={() => hypr.dispatch("workspace", String(ws.get_id()))}>
                    {String(ws.get_id())}
                </button>
            )
        )}
    </box>
}

function Clock() {
    const time = new SystemClock({ interval: 1000 })
    return <label
        className="Clock"
        label={bind(time, "now").as(t =>
            new Date(t * 1000).toLocaleTimeString("en-US", {
                hour: "2-digit", minute: "2-digit"
            })
        )}
    />
}

export default function Bar(monitor: Gdk.Monitor) {
    const { TOP, LEFT, RIGHT } = Astal.WindowAnchor
    return <window
        className="Bar"
        gdkmonitor={monitor}
        anchor={TOP | LEFT | RIGHT}
        exclusivity={Astal.Exclusivity.EXCLUSIVE}
        application={App}>
        <centerbox>
            <Workspaces />
            <Clock />
            <box halign={Gtk.Align.END} spacing={8}>
                {/* volume, battery, tray... */}
            </box>
        </centerbox>
    </window>
}
```

---

## 100.14 Styling

Astal uses GTK CSS. Place your stylesheet at `~/.config/ags/style.css` and
load it in `app.ts`:

```typescript
App.start({
    css: `${App.get_application_id()}/style.css`,
    main() { /* ... */ },
})
```

```css
/* ~/.config/ags/style.css */
.Bar {
    background: alpha(@bg, 0.85);
    border-bottom: 1px solid alpha(@surface1, 0.5);
    padding: 0 12px;
    font-size: 13px;
}

.workspace {
    min-width: 24px;
    min-height: 24px;
    border-radius: 6px;
    color: @subtext0;
    transition: all 200ms ease;
}

.workspace.active {
    background: @mauve;
    color: @base;
}

.Clock {
    font-weight: 600;
    color: @text;
}
```

---

## 100.15 AGS vs Quickshell

| Feature | AGS/Astal | Quickshell |
|---------|-----------|-----------|
| Language | TypeScript / GJS | QML / C++ |
| Toolkit | GTK4 | Qt6 / QtQuick |
| Hot reload | `astal --inspect` | Native (fast) |
| Type safety | Full TS types | QML type system |
| Ecosystem | npm packages | Qt ecosystem |
| GPU rendering | GTK4 GL | QtQuick hardware |
| Hyprland IPC | `gi://AstalHyprland` | `Quickshell.Hyprland` |
| Community configs | end_4/dotfiles, many more | outfoxxed, growing |
| Maturity | Established (AGS v1 → Astal v2) | Newer, rapid development |

Choose Astal if you are comfortable with TypeScript/JavaScript and prefer GTK
aesthetics. Choose Quickshell if you want QML's declarative layout model and
tighter Qt integration.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
