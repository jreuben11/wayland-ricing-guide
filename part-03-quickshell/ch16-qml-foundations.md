# Chapter 16 — QML Foundations for Quickshell

## Overview
You don't need Qt or mobile development experience to use Quickshell, but
understanding QML's core concepts unlocks its full power. This chapter teaches
exactly what you need — no more, no less.

## Sections

### 16.1 QML Basics
- QML is a declarative language: describe WHAT, not HOW
- Objects and properties: `Rectangle { width: 100; color: "red" }`
- Hierarchy: parent-child visual containment
- Property bindings: `width: parent.width / 2` (reactive, live)
- JavaScript expressions in bindings
- `id`: naming objects for cross-reference

### 16.2 Types and Properties
- Basic types: `int`, `real`, `bool`, `string`, `color`, `url`
- Composite types: `size`, `point`, `rect`, `font`
- Object types: `Item`, `Rectangle`, `Text`, `Image`, `MouseArea`
- `property type name: defaultValue` — custom properties
- `readonly property` — computed, not settable
- `required property` — must be provided by parent

### 16.3 Reactive Bindings
- How bindings update automatically when dependencies change
- `onPropertyChanged` signal handlers
- Breaking bindings with `=` assignment (gotcha!)
- `Qt.binding()` for re-establishing bindings in JavaScript

### 16.4 Signals and Signal Handlers
- Built-in signals: `onClicked`, `onPressed`, `Component.onCompleted`
- `signal mySignal(type arg)` — defining custom signals
- `connect()` for programmatic handler attachment
- `emit mySignal(value)`

### 16.5 JavaScript in QML
- Inline JavaScript expressions in bindings
- `.js` import files for logic modules
- `Qt.include()` and `import` statements
- Limitations: no DOM, no node.js — this is a UI runtime

### 16.6 Components and Instantiation
- `Component {}` block: a reusable template
- `Loader {}`: dynamic component loading
- `Repeater {}`: instantiate components from a model
- `ListView {}`, `GridView {}`: scrollable repeaters

### 16.7 Singletons
- `pragma Singleton` at top of a QML file
- Accessible by name from any file in the same config
- Use for global state: current theme, active window, etc.
- Quickshell's built-in singletons: `Quickshell`, `SystemClock`

### 16.8 Quickshell-Specific QML Patterns
- `ShellRoot {}` as the top-level component in `shell.qml`
- `Variants {}` for creating per-screen component instances
- `LazyLoader {}` for deferred loading of heavy components
- `Scope {}` for non-visual grouping
- `PersistentProperties {}` for state that survives config reloads

### 16.9 Debugging QML
- `console.log()`, `console.warn()`, `console.trace()`
- `--log-rules "*.debug=true"` Quickshell flag
- Qt Creator's QML debugger (optional)
- Common errors and what they mean
