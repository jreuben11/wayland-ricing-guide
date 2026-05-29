# Chapter 6 — Compositor Taxonomy: Tiling, Stacking, Dynamic, Kiosk

## Overview
A mental map of all compositor categories before diving into individual ones.
Understand the design axes so you can make an informed choice.

## Sections

### 6.1 Design Axes
- **Layout model**: manual tiling / automatic tiling / dynamic / stacking / scrollable
- **Configuration style**: text config / IPC-scripted / GUI settings
- **Base library**: wlroots-based / Smithay-based / KWin / GNOME Shell / custom
- **Tag model**: i3-style workspaces / tagging (dwm-style) / scrollable (niri)
- **Animation philosophy**: none / subtle / heavy

### 6.2 Stacking Compositors
- Windows float by default, overlap freely
- Examples: labwc, KWin (KDE Plasma), GNOME Mutter, lxqt-kwin, weston
- Best for: familiar desktop users, floating-heavy workflows

### 6.3 Manual Tiling Compositors
- User controls layout explicitly; no automatic placement
- Examples: Sway (i3 model), dwl (dwm model)
- Best for: keyboard-driven, minimal, reproducible layouts

### 6.4 Dynamic/Automatic Tiling Compositors
- Compositor auto-tiles based on rules or algorithms
- Examples: Hyprland (dwindle/master), river (external layouts), Way Cooler
- Best for: fast multi-window workflows

### 6.5 Plugin/Effect Compositors
- Compositing behavior defined by plugins
- Examples: Wayfire (wf-config + WCM), KWin (KWin Scripts)
- Best for: heavy visual customization, 3D effects

### 6.6 Scrollable/Spatial Compositors
- Windows arranged on an infinite scrollable canvas
- Examples: Niri, PaperWM (GNOME extension)
- Best for: context switching without workspaces

### 6.7 Kiosk and Embedded Compositors
- Single-app or locked-down environments
- Examples: cage, gamescope, weston kiosk shell
- Best for: digital signage, game launchers, embedded devices

### 6.8 Full Desktop Environment Compositors
- Integrated with complete DE (panels, file managers, settings)
- Examples: KWin + Plasma, Mutter + GNOME, cosmic-comp + COSMIC
- Best for: out-of-the-box completeness

## Comparison Matrix
(Table comparing all compositors across all axes — to be completed in final chapter)
