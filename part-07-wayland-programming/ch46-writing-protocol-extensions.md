# Chapter 46 — Writing a Wayland Protocol Extension

## Overview
Compositors can define custom protocol extensions. This chapter walks through
writing a real protocol extension from XML definition through client and server
implementation.

## Sections

### 46.1 When to Write a Protocol Extension
- Custom compositor-specific functionality (like Hyprland's protocols)
- Hardware-specific features not in wayland-protocols
- Application-compositor communication beyond xdg-shell

### 46.2 Protocol XML Anatomy
```xml
<?xml version="1.0" encoding="UTF-8"?>
<protocol name="my_compositor_ext">
    <copyright>...</copyright>

    <interface name="my_ext_manager_v1" version="1">
        <description summary="example extension manager">
            This interface manages example features.
        </description>

        <request name="get_example_object">
            <description summary="create an example object"/>
            <arg name="id" type="new_id" interface="my_ext_object_v1"/>
            <arg name="surface" type="object" interface="wl_surface"/>
        </request>

        <event name="global_event">
            <arg name="data" type="string"/>
        </event>
    </interface>

    <interface name="my_ext_object_v1" version="1">
        <request name="set_property">
            <arg name="value" type="int"/>
        </request>

        <event name="property_changed">
            <arg name="new_value" type="int"/>
        </event>

        <request name="destroy" type="destructor"/>
    </interface>
</protocol>
```

### 46.3 Generating Code with wayland-scanner
```bash
# Generate headers
wayland-scanner client-header my-protocol.xml my-protocol-client.h
wayland-scanner server-header my-protocol.xml my-protocol-server.h

# Generate implementation glue
wayland-scanner private-code my-protocol.xml my-protocol.c
```
- Client header: `_add_listener`, `_set_user_data` functions
- Server header: `_create_resource`, `_send_*` functions
- Private code: serialization/deserialization

### 46.4 Client-Side Implementation
```c
// Bind the global
static void registry_handle_global(void *data,
    struct wl_registry *registry, uint32_t name,
    const char *interface, uint32_t version)
{
    if (strcmp(interface, my_ext_manager_v1_interface.name) == 0) {
        manager = wl_registry_bind(registry, name,
            &my_ext_manager_v1_interface, 1);
    }
}

// Use the interface
struct my_ext_object_v1 *obj =
    my_ext_manager_v1_get_example_object(manager, surface);
my_ext_object_v1_set_property(obj, 42);
```

### 46.5 Server-Side Implementation in wlroots
```c
// Register the global
struct my_ext_manager *manager =
    my_ext_manager_create(server->wl_display);

// Handle requests
static void handle_get_example_object(struct wl_client *client,
    struct wl_resource *manager_resource,
    uint32_t id, struct wl_resource *surface_resource)
{
    struct my_ext_object *obj = calloc(1, sizeof(*obj));
    obj->resource = wl_resource_create(client,
        &my_ext_object_v1_interface, 1, id);
    wl_resource_set_implementation(obj->resource,
        &object_impl, obj, handle_object_destroy);
}
```

### 46.6 Protocol Versioning
- Version in `<interface version="N">`
- Backwards compatibility: old clients bind old version
- Adding new requests/events in version bumps
- `wl_resource_get_version()` check before using new features

### 46.7 Real-World Example: A Simple Blur Protocol
- Protocol: client requests blur level for a surface
- Compositor: reads the request, applies blur in the render pass
- Full XML + C implementation walkthrough

### 46.8 Upstreaming Protocols
- wayland-protocols submission process
- gitlab.freedesktop.org/wayland/wayland-protocols
- Staging vs. unstable vs. stable tiers
- What makes a good protocol candidate
