# The Wayland Ricing Bible
## From Protocol Internals to the Perfect Desktop

A comprehensive multi-chapter guide covering Wayland from the wire protocol up through
compositor selection, Quickshell shell development, the full ricing toolchain, theming,
and writing your own Wayland extensions.

---

## Book Structure

| Part | Focus | Chapters |
|------|-------|----------|
| 0    | Getting Started | 0 |
| I    | Wayland Foundations | 1–5, 63–65 |
| II   | Compositor Landscape | 6–14, 66–68, 89, 99 |
| III  | Quickshell — Deep Dive | 15–25 |
| IV   | The Ricing Stack | 26–33, 69–70, 72, 104 |
| V    | Theming & Aesthetics | 34–40, 87, 94, 101, 103 |
| VI   | Advanced Topics | 41–45, 84–86, 88, 90, 92, 95–97, 102 |
| VII  | Writing for Wayland | 46–49, 73–74 |
| VIII | Application Layer | 50–51, 57–59, 75–76, 100 |
| IX   | System Infrastructure | 52–56, 60–62, 71, 77–83, 91, 93, 98 |
| —    | Appendices | A–E |

**Total: 105 chapters + 8 appendices**

---

## Chapter Index

### Part 0 — Getting Started
- [Chapter 00](part-00-getting-started/ch00-prerequisites.md) — Prerequisites, Hardware, and Environment Setup

### Part I — Wayland Foundations
- [Chapter 01](part-01-wayland-foundations/ch01-protocol-architecture.md) — The Wayland Protocol: Architecture and Philosophy
- [Chapter 02](part-01-wayland-foundations/ch02-wire-protocol.md) — The Wire Protocol: Messages, Objects, and Interfaces
- [Chapter 03](part-01-wayland-foundations/ch03-protocol-extensions.md) — Protocol Extensions: xdg-shell, layer-shell, wlr-protocols
- [Chapter 04](part-01-wayland-foundations/ch04-libwayland-programming.md) — libwayland Programming: Writing Wayland Clients in C
- [Chapter 05](part-01-wayland-foundations/ch05-wlroots.md) — wlroots: The Compositor Building Blocks
- [Chapter 63](part-01-wayland-foundations/ch63-gpu-rendering-stack.md) — The GPU Rendering Stack: DRM/KMS, Mesa, GBM, EGL
- [Chapter 64](part-01-wayland-foundations/ch64-xwayland-internals.md) — XWayland Internals: How X11 Apps Run on Wayland
- [Chapter 65](part-01-wayland-foundations/ch65-wayland-security.md) — The Wayland Security Model

### Part II — The Compositor Landscape
- [Chapter 06](part-02-compositors/ch06-compositor-taxonomy.md) — Compositor Taxonomy: Tiling, Stacking, Dynamic, Kiosk
- [Chapter 07](part-02-compositors/ch07-sway.md) — Sway: i3 on Wayland
- [Chapter 08](part-02-compositors/ch08-hyprland.md) — Hyprland: Dynamic Tiling with Animation DNA
- [Chapter 09](part-02-compositors/ch09-wayfire.md) — Wayfire: Plugin Architecture and 3D Effects
- [Chapter 10](part-02-compositors/ch10-river.md) — River: Tag-Based Minimalism
- [Chapter 11](part-02-compositors/ch11-niri.md) — Niri: The Scrollable Workspace Pioneer
- [Chapter 12](part-02-compositors/ch12-labwc.md) — labwc: The OpenBox Successor
- [Chapter 13](part-02-compositors/ch13-compositor-zoo.md) — The Full Zoo: dwl, Jay, cosmic-comp, KWin, GNOME Shell, gamescope
- [Chapter 14](part-02-compositors/ch14-compositor-selection.md) — Choosing Your Compositor: Decision Framework
- [Chapter 66](part-02-compositors/ch66-kde-plasma-6.md) — KDE Plasma 6 on Wayland
- [Chapter 67](part-02-compositors/ch67-gnome-shell-wayland.md) — GNOME Shell on Wayland
- [Chapter 68](part-02-compositors/ch68-cosmic-desktop.md) — COSMIC Desktop: System76's Rust DE
- [Chapter 89](part-02-compositors/ch89-hyprland-plugins.md) — Hyprland Plugins and hyprpm
- [Chapter 99](part-02-compositors/ch99-hyprland-lua.md) — Hyprland Lua Configuration (0.55+)

### Part III — Quickshell: The Modern Shell Framework
- [Chapter 15](part-03-quickshell/ch15-quickshell-architecture.md) — Quickshell Architecture and Philosophy
- [Chapter 16](part-03-quickshell/ch16-qml-foundations.md) — QML Foundations for Quickshell
- [Chapter 17](part-03-quickshell/ch17-window-types.md) — PanelWindow, FloatingWindow, and Window Management
- [Chapter 18](part-03-quickshell/ch18-core-modules.md) — Core Modules: Io, DBusMenu, Singletons
- [Chapter 19](part-03-quickshell/ch19-wayland-integration.md) — Wayland Integration: Layer Shell, ToplevelManager, ScreenCopy
- [Chapter 20](part-03-quickshell/ch20-compositor-ipc.md) — Compositor IPC: Hyprland and i3/Sway Modules
- [Chapter 21](part-03-quickshell/ch21-pipewire-audio.md) — Audio with PipeWire (Quickshell API)
- [Chapter 22](part-03-quickshell/ch22-system-services.md) — System Services: Notifications, MPRIS, UPower, SystemTray
- [Chapter 23](part-03-quickshell/ch23-building-a-bar.md) — Building a Complete Status Bar
- [Chapter 24](part-03-quickshell/ch24-lockscreen.md) — Lockscreens with PAM and Greetd
- [Chapter 25](part-03-quickshell/ch25-real-world-configs.md) — Real-World Quickshell Configurations

### Part IV — The Ricing Stack
- [Chapter 26](part-04-ricing-stack/ch26-bars-panels.md) — Bars and Panels: Waybar, eww, AGS/Astal
- [Chapter 27](part-04-ricing-stack/ch27-wallpaper.md) — Wallpaper Management: swww, hyprpaper, swaybg, mpvpaper
- [Chapter 28](part-04-ricing-stack/ch28-launchers.md) — Application Launchers: fuzzel, rofi, wofi, Anyrun, walker, tofi
- [Chapter 29](part-04-ricing-stack/ch29-notifications.md) — Notification Daemons: mako, dunst, swaync
- [Chapter 30](part-04-ricing-stack/ch30-screenlock.md) — Screen Locking: hyprlock, swaylock, gtklock
- [Chapter 31](part-04-ricing-stack/ch31-screenshot-recording.md) — Screenshots and Recording: grim, slurp, wf-recorder, OBS
- [Chapter 32](part-04-ricing-stack/ch32-clipboard.md) — Clipboard Management: wl-clipboard, cliphist
- [Chapter 33](part-04-ricing-stack/ch33-display-config.md) — Display Configuration: kanshi, wdisplays, wlr-randr, shikane
- [Chapter 69](part-04-ricing-stack/ch69-file-managers.md) — File Managers: Yazi, Thunar, Dolphin, lf
- [Chapter 70](part-04-ricing-stack/ch70-color-pickers.md) — Color Picker Tools: hyprpicker, wl-color-picker, pastel
- [Chapter 72](part-04-ricing-stack/ch72-media-players.md) — Media Players: mpv, VLC, and Wayland Playback
- [Chapter 104](part-04-ricing-stack/ch104-waybar-css.md) — Waybar CSS Theming Deep Dive

### Part V — Theming and Aesthetics
- [Chapter 34](part-05-theming/ch34-color-theory.md) — Color Theory for Desktop Ricing
- [Chapter 35](part-05-theming/ch35-gtk-theming.md) — GTK Theming: Adwaita, libadwaita, CSS Overrides
- [Chapter 36](part-05-theming/ch36-qt-theming.md) — Qt and KDE Theming: Kvantum, qt5ct/qt6ct
- [Chapter 37](part-05-theming/ch37-icons-cursors-fonts.md) — Icon Packs, Cursors, and Fonts
- [Chapter 38](part-05-theming/ch38-color-extraction.md) — pywal, matugen, and Automatic Color Extraction
- [Chapter 39](part-05-theming/ch39-nix-home-manager.md) — Nix and Home Manager: Reproducible Rices
- [Chapter 40](part-05-theming/ch40-stylix.md) — Stylix: Auto-Theming Everything from One Wallpaper
- [Chapter 87](part-05-theming/ch87-font-rendering.md) — Font Rendering Deep Dive: fontconfig, Hinting, CJK
- [Chapter 94](part-05-theming/ch94-color-management-icc.md) — Color Management and ICC Profiles
- [Chapter 101](part-05-theming/ch101-nix-flake-rice.md) — Advanced Nix Flake Architecture for a Full Rice
- [Chapter 103](part-05-theming/ch103-cursor-themes.md) — Cursor Theme Creation: xcursor and hyprcursor

### Part VI — Advanced Topics
- [Chapter 41](part-06-advanced/ch41-multi-monitor-hidpi.md) — Multi-Monitor, HiDPI, and Fractional Scaling
- [Chapter 42](part-06-advanced/ch42-gaming.md) — Gaming on Wayland: XWayland, gamescope, VRR, HDR
- [Chapter 43](part-06-advanced/ch43-input-customization.md) — Input Customization: libinput, kanata, keyd, wev
- [Chapter 44](part-06-advanced/ch44-accessibility.md) — Accessibility on Wayland: orca, at-spi2, zoom tools
- [Chapter 45](part-06-advanced/ch45-debugging.md) — Debugging Wayland: WAYLAND_DEBUG, weston-info, wldbg
- [Chapter 84](part-06-advanced/ch84-kvm-vm-wayland.md) — KVM/QEMU Virtual Machines for Wayland Development and Testing
- [Chapter 85](part-06-advanced/ch85-containerization-wayland.md) — Containerization, Sandboxing, WSL2, and Headless Wayland
- [Chapter 86](part-06-advanced/ch86-automation-testing.md) — Automation and Testing of Wayland Ricing Configs
- [Chapter 88](part-06-advanced/ch88-hyprland-ipc-scripting.md) — Hyprland IPC Scripting
- [Chapter 90](part-06-advanced/ch90-touchscreen-tablet.md) — Touchscreen and Drawing Tablet Support
- [Chapter 92](part-06-advanced/ch92-compositor-shaders.md) — Custom GLSL Shaders in Compositors
- [Chapter 95](part-06-advanced/ch95-gpu-monitoring-overclocking.md) — GPU Monitoring and Overclocking: lact, nvtop, radeontop
- [Chapter 96](part-06-advanced/ch96-workspace-automation.md) — Workspace Automation: pyprland, Scratchpads, Persistent Layouts
- [Chapter 97](part-06-advanced/ch97-wayland-mobile-embedded.md) — Wayland on Mobile and Embedded: Phosh, Sxmo, Weston Kiosk
- [Chapter 102](part-06-advanced/ch102-wine-wayland.md) — Wine Wayland: Native Windows Apps Without XWayland

### Part VII — Writing for Wayland
- [Chapter 46](part-07-wayland-programming/ch46-writing-protocol-extensions.md) — Writing a Wayland Protocol Extension
- [Chapter 47](part-07-wayland-programming/ch47-compositor-in-c.md) — Building a Minimal Compositor with wlroots (C)
- [Chapter 48](part-07-wayland-programming/ch48-compositor-in-rust.md) — Building a Compositor in Rust with Smithay
- [Chapter 49](part-07-wayland-programming/ch49-contributing.md) — Contributing to the Wayland Ecosystem
- [Chapter 73](part-07-wayland-programming/ch73-rust-wayland-client.md) — Writing Wayland Clients in Rust: wayland-client
- [Chapter 74](part-07-wayland-programming/ch74-quickshell-cpp-module.md) — Writing a Quickshell C++ Module

### Part VIII — Application Layer
- [Chapter 50](part-08-daily-driver/ch50-terminal-emulators.md) — Terminal Emulators: Kitty, Alacritty, Foot, WezTerm, Ghostty
- [Chapter 51](part-08-daily-driver/ch51-shell-prompts.md) — Shell Configuration and Prompts: Fish, Zsh, Starship, oh-my-posh
- [Chapter 57](part-08-daily-driver/ch57-editor-theming.md) — Editor Theming: Neovim, VS Code, Helix, Emacs
- [Chapter 58](part-08-daily-driver/ch58-browser-theming.md) — Browser Theming and Wayland Integration: Firefox, Chromium
- [Chapter 59](part-08-daily-driver/ch59-desktop-widgets.md) — Desktop Widgets, Overview Effects, and Conky Equivalents
- [Chapter 62](part-08-daily-driver/ch62-opinionated-setups.md) — Opinionated Rice Bootstraps: Omarchy, ML4W, HyDE, CachyOS
- [Chapter 75](part-08-daily-driver/ch75-quickshell-notification-center.md) — Quickshell Notification Center: Full Sidebar Implementation
- [Chapter 76](part-08-daily-driver/ch76-quickshell-osd.md) — Quickshell OSD: Volume, Brightness, and Media Displays
- [Chapter 100](part-08-daily-driver/ch100-ags-astal.md) — AGS / Astal: TypeScript Shell Framework

### Part IX — System Infrastructure
- [Chapter 52](part-08-daily-driver/ch52-xdg-desktop-portal.md) — xdg-desktop-portal: Screen Sharing, File Chooser, Settings
- [Chapter 53](part-08-daily-driver/ch53-session-startup.md) — Session Startup and Environment: exec-once, dbus, systemd user
- [Chapter 54](part-08-daily-driver/ch54-display-managers.md) — Display Managers and Greeters: SDDM, GDM, greetd
- [Chapter 55](part-08-daily-driver/ch55-dotfile-management.md) — Dotfile Management: stow, chezmoi, yadm, bare git
- [Chapter 56](part-08-daily-driver/ch56-pipewire-system.md) — PipeWire System Setup: WirePlumber, EasyEffects, Bluetooth Audio
- [Chapter 60](part-08-daily-driver/ch60-night-light.md) — Night Light and Color Temperature: wlsunset, gammastep, hyprsunset
- [Chapter 61](part-08-daily-driver/ch61-screen-sharing.md) — Screen Sharing and Video Calls: Portal Setup, WebRTC, OBS
- [Chapter 71](part-09-system-infra/ch71-network-polkit.md) — Network Management and Polkit: nmtui, nm-applet, pkexec
- [Chapter 77](part-09-system-infra/ch77-plymouth.md) — Plymouth Boot Splash: Themed Boot Screens
- [Chapter 78](part-09-system-infra/ch78-laptop-power.md) — Laptop Power Management: tlp, auto-cpufreq, VFR
- [Chapter 79](part-09-system-infra/ch79-ime-fcitx5.md) — Input Method Editors on Wayland: Fcitx5, IBus
- [Chapter 80](part-09-system-infra/ch80-remote-desktop.md) — Remote Desktop and Game Streaming: wayvnc, RDP, Sunshine
- [Chapter 81](part-09-system-infra/ch81-bluetooth.md) — Bluetooth Management: bluetui, blueman, bluetoothctl
- [Chapter 82](part-09-system-infra/ch82-printing-scanning.md) — Printing and Scanning: CUPS, SANE, simple-scan
- [Chapter 83](part-09-system-infra/ch83-package-manager-tui.md) — Package Manager TUI Tools: paru, pacseek, nh, Flatpak
- [Chapter 91](part-09-system-infra/ch91-xdg-mime-default-apps.md) — XDG MIME Types and Default Applications
- [Chapter 93](part-09-system-infra/ch93-dbus-essentials.md) — D-Bus Essentials for Wayland Power Users (+ Varlink)
- [Chapter 98](part-09-system-infra/ch98-varlink.md) — Varlink: Modern IPC for System Services

### Appendices
- [Appendix A](appendices/appendix-a-protocol-reference.md) — Protocol Quick Reference
- [Appendix B](appendices/appendix-b-dotfiles-gallery.md) — Dotfiles Repository Gallery
- [Appendix C](appendices/appendix-c-resources.md) — Resource Index and Links
- [Appendix D](appendices/appendix-d-quickshell-api.md) — Quickshell API Quick Reference
- [Appendix E](appendices/appendix-e-hyprland-cheatsheet.md) — Hyprland Configuration Quick Reference
- [Appendix F](appendices/appendix-f-ai-mcp-tools.md) — AI, Claude, and MCP Tools for Wayland Ricing
- [Appendix G](appendices/appendix-g-glossary.md) — Glossary of Terms
- [Appendix H](appendices/appendix-h-tool-index.md) — CLI Tool and Command Index



---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).