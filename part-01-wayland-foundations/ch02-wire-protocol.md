# Chapter 2 — The Wire Protocol: Messages, Objects, and Interfaces

## Overview
How Wayland actually communicates over a Unix socket. Understanding the binary
protocol, object model, and event/request duality is essential for debugging
and for writing protocol extensions.

## Sections

### 2.1 The Unix Socket Transport
- Unix domain sockets: file-descriptor passing, SCM_RIGHTS
- Message framing: header format (object ID, opcode, size)
- Argument types: int, uint, fixed, string, object, new_id, array, fd
- Endianness and alignment rules

### 2.2 The Object Model
- Numeric object IDs and their lifecycle (birth via `new_id`, death via destructor)
- Server-allocated vs. client-allocated ID ranges
- The `wl_display` root object and its special status
- Interface versioning and capability negotiation

### 2.3 Requests and Events
- Requests: client → compositor (synchronous intent)
- Events: compositor → client (asynchronous state updates)
- The global registry: `wl_registry` and `wl_registry.bind`
- `wl_display.sync` and roundtrip semantics

### 2.4 The Global Registry Pattern
- Advertising compositor capabilities as globals
- Binding globals with version negotiation
- The `wl_shm` global: shared-memory buffers
- The `wl_compositor` global: creating surfaces

### 2.5 Surfaces and the Rendering Pipeline
- `wl_surface`: the fundamental rendering unit
- `wl_buffer`: attaching pixel data to a surface
- Commit semantics: double-buffered state
- Frame callbacks: pacing rendering to compositor vsync
- Damage tracking: partial surface updates

### 2.6 Debugging the Wire Protocol
- `WAYLAND_DEBUG=1` environment variable
- `wldbg` interactive debugger
- `weston-info` for capability inspection
- Reading hex dumps of the socket

## Code Examples
- Minimal C client using `wl_registry` to enumerate globals
- Rendering a colored rectangle with `wl_shm`
