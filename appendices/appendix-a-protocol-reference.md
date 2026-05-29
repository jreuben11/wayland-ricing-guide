# Appendix A — Protocol Quick Reference

## Core Wayland Protocols (wayland.xml)
| Protocol | Purpose |
|----------|---------|
| `wl_display` | Root object, sync, error reporting |
| `wl_registry` | Global capability advertisement |
| `wl_compositor` | Create surfaces |
| `wl_surface` | Rendering unit (attach buffer, commit) |
| `wl_buffer` | Pixel data (shm or dmabuf) |
| `wl_shm` | Shared memory buffer creation |
| `wl_seat` | Input device group |
| `wl_keyboard` | Keyboard input |
| `wl_pointer` | Pointer input |
| `wl_touch` | Touch input |
| `wl_output` | Monitor/display representation |
| `wl_subcompositor` | Sub-surfaces |
| `wl_data_device_manager` | Clipboard / drag-and-drop |

## Standard Extensions (wayland-protocols)
| Protocol | Namespace | Purpose |
|----------|-----------|---------|
| xdg-shell | `xdg_wm_base` | Window management (applications) |
| xdg-popup | `xdg_popup` | Menus and popups |
| xdg-output | `zxdg_output_manager_v1` | Logical output metadata |
| xdg-decoration | `zxdg_decoration_manager_v1` | CSD vs SSD negotiation |
| xdg-activation | `xdg_activation_v1` | Focus stealing prevention |
| presentation-time | `wp_presentation` | Precise frame timing |
| viewporter | `wp_viewporter` | Surface scaling/cropping |
| fractional-scale | `wp_fractional_scale_manager_v1` | Fractional HiDPI |
| cursor-shape | `wp_cursor_shape_manager_v1` | Cursor themes |
| linux-dmabuf | `zwp_linux_dmabuf_v1` | GPU buffer sharing |
| pointer-constraints | `zwp_pointer_constraints_v1` | Pointer lock/confine |
| relative-pointer | `zwp_relative_pointer_manager_v1` | Raw mouse motion |
| virtual-keyboard | `zwp_virtual_keyboard_manager_v1` | Software keyboard |
| input-method | `zwp_input_method_manager_v2` | IME |
| ext-session-lock | `ext_session_lock_manager_v1` | Session lockscreen |
| color-management | `wp_color_manager_v1` | HDR and color spaces |

## wlr-protocols (wlroots ecosystem)
| Protocol | Purpose |
|----------|---------|
| `zwlr_layer_shell_v1` | Bars, widgets, wallpapers (RICING CORE) |
| `zwlr_screencopy_manager_v1` | Screenshots, recording |
| `zwlr_output_manager_v1` | Monitor configuration |
| `zwlr_foreign_toplevel_management_v1` | Window list/taskbar |
| `zwlr_data_control_manager_v1` | Clipboard access from non-focused apps |
| `zwlr_input_inhibitor_v1` | Lockscreen input inhibition (older) |
| `zwlr_gamma_control_manager_v1` | Night light/gamma |
| `zwlr_virtual_pointer_manager_v1` | Synthetic pointer events |
| `zwlr_export_dmabuf_manager_v1` | DMA-BUF screen capture |

## Hyprland Custom Protocols
| Protocol | Purpose |
|----------|---------|
| `hyprland_global_shortcuts_v1` | Register global hotkeys |
| `hyprland_toplevel_export_v1` | Thumbnail capture |
| `hyprland_ctm_control_v1` | Color transform matrices |
| `hyprland_focus_grab_v1` | Input focus grab for overlays |

## Protocol Explorer
- Browse all protocols: https://wayland.app/protocols/
- wayland-protocols repo: https://gitlab.freedesktop.org/wayland/wayland-protocols
- wlr-protocols: https://gitlab.freedesktop.org/wlroots/wlr-protocols
