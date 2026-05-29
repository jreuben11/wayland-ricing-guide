# Chapter 49 — Contributing to the Wayland Ecosystem

## Overview
The Wayland ecosystem is maintained by a relatively small community. This chapter
shows where contributions are most impactful and how to get started.

## Sections

### 49.1 The Ecosystem Map
- freedesktop.org projects: wayland, wayland-protocols, wlroots, mesa
- Compositor projects: sway, Hyprland, niri, labwc, river
- Shell tools: Quickshell, Waybar, mako, swww
- Applications: xdg-desktop-portal backends, system services

### 49.2 Where to Start
- **Docs and wikis**: always needed, low barrier
- **Bug reports**: detailed reproductions with `WAYLAND_DEBUG` logs
- **Translations**: i18n for GTK apps
- **Protocol testing**: test protocol implementations across compositors
- **Code contributions**: pick "good first issue" labels

### 49.3 Contributing to wayland-protocols
- Repository: https://gitlab.freedesktop.org/wayland/wayland-protocols
- Process: draft → MR → review → staging → stable
- Requirements: two independent implementations, real use case
- MR template: problem statement, protocol design rationale, implementation notes

### 49.4 Contributing to wlroots
- Repository: https://gitlab.freedesktop.org/wlroots/wlroots
- C code style: Linux kernel style
- Test requirements: `tinywl` must still work
- CI: GitLab CI with build matrix
- Focus areas: protocol implementations, backend improvements

### 49.5 Contributing to Quickshell
- Repository: https://git.outfoxxed.me/quickshell/quickshell (Forgejo)
- Mirror: https://github.com/quickshell-mirror/quickshell
- C++/QML codebase
- Adding new service modules: follow existing patterns in `services/`
- Documentation: the docs site is built from source

### 49.6 Contributing to Hyprland
- Repository: https://github.com/hyprwm/Hyprland
- C++ codebase
- Plugin API: `hyprland-plugin.h`
- Issue tracker: bug reports with full compositor logs
- Protocol extensions: the `protocols/` directory

### 49.7 Writing and Publishing Quickshell Configs
- Share on GitHub with good README and screenshots
- Tag: `quickshell`, `wayland`, `rice`, `dotfiles`
- r/unixporn: the community hub (include config link)
- GitHub dotfiles topic: discoverable
- NixOS flake: maximum portability

### 49.8 Filing Good Bug Reports
- Include: `WAYLAND_DEBUG` output, compositor version, OS, GPU
- Minimal reproduction: smallest config that triggers the bug
- Expected vs actual behavior
- Screenshots or recordings with `wf-recorder`

### 49.9 The Community
- **#wayland on Libera.Chat IRC / Matrix**: protocol development
- **#sway IRC**: sway and wlroots
- **Hyprland Discord**: active, large community
- **r/hyprland, r/unixporn**: ricing community
- **NixOS Discourse**: NixOS ricing help
- **freedesktop.org Matrix**: protocol and Mesa discussions
