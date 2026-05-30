# Chapter 129 — Firefox userChrome.css: Deep Browser Ricing

## Contents

- [Overview](#overview)
- [129.1 Enabling userChrome.css](#1291-enabling-userchromecss)
- [129.2 Finding Selectors with the Browser Toolbox](#1292-finding-selectors-with-the-browser-toolbox)
- [129.3 Compact / Ultra-Compact Mode](#1293-compact-ultra-compact-mode)
- [129.4 Hiding the Tab Bar (Tree Style Tab / Vertical Tabs)](#1294-hiding-the-tab-bar-tree-style-tab-vertical-tabs)
  - [For Tree Style Tab extension](#for-tree-style-tab-extension)
  - [For Firefox 133+ native vertical tabs](#for-firefox-133-native-vertical-tabs)
  - [Sidebar width tuning](#sidebar-width-tuning)
- [129.5 Tokyo Night Theme](#1295-tokyo-night-theme)
- [129.6 Cyberpunk Neon Theme](#1296-cyberpunk-neon-theme)
- [129.7 userContent.css: New Tab and About Pages](#1297-usercontentcss-new-tab-and-about-pages)
- [129.8 Pre-made Theme Frameworks](#1298-pre-made-theme-frameworks)
- [129.9 Firefox Color Extension vs. Manual CSS](#1299-firefox-color-extension-vs-manual-css)
- [129.10 CSD and Wayland Window Controls](#12910-csd-and-wayland-window-controls)
- [129.11 Useful about:config Flags](#12911-useful-aboutconfig-flags)
- [129.12 Integrating with pywal / matugen](#12912-integrating-with-pywal-matugen)

---


## Overview

Firefox exposes its entire UI as styleable XUL/HTML elements, accessible via `userChrome.css` for the browser chrome (toolbars, tabs, menus) and `userContent.css` for page content (new-tab page, about: pages). This makes Firefox the most thoroughly riceable browser on Linux — every pixel of the interface can be restyled to match your desktop aesthetic. This chapter covers the mechanics of the system, writing selectors using the browser toolbox, pre-made theme frameworks, and complete Tokyo Night and Cyberpunk examples.

**Cross-references:** Ch 58 — browser theming overview (environment variables, theme engines). Ch 35 — GTK theming (Firefox uses GTK for system dialogs). Ch 112 — aesthetic ricing meta-chapter (palette integration).

---

## Installation

**Project:** https://www.firefox.com

```bash
# Arch Linux
sudo pacman -S firefox

# Nix (nixpkgs)
nix-env -iA nixpkgs.firefox
# home-manager: programs.firefox.enable = true;
```

---

## 129.1 Enabling userChrome.css

Firefox disables legacy userChrome customization by default. Enable it once:

```
about:config → toolkit.legacyUserProfileCustomizations.stylesheets = true
```

Then create the files:

```bash
# Find your profile directory
PROFILE=$(ls -d ~/.mozilla/firefox/*.default-release 2>/dev/null || \
          ls -d ~/.mozilla/firefox/*.default 2>/dev/null | head -1)

mkdir -p "$PROFILE/chrome"
touch "$PROFILE/chrome/userChrome.css"
touch "$PROFILE/chrome/userContent.css"

echo "Profile: $PROFILE"
```

The structure:
```
~/.mozilla/firefox/<profile>/
└── chrome/
    ├── userChrome.css   ← browser UI (toolbars, tabs, sidebar)
    └── userContent.css  ← page content (new tab, about:pages)
```

Changes take effect after restarting Firefox. For live reloading during development, use:
```
about:config → devtools.chrome.enabled = true
               devtools.debugger.remote-enabled = true
```
Then Ctrl+Alt+Shift+I opens the browser toolbox without restart.

---

## 129.2 Finding Selectors with the Browser Toolbox

The Browser Toolbox (Ctrl+Alt+Shift+I) lets you inspect the actual XUL/HTML elements of the Firefox UI — the same workflow as DevTools for web pages, but applied to Firefox itself.

```
1. about:config → devtools.chrome.enabled = true
2. Tools → Browser Tools → Browser Toolbox
3. Click the Inspector cursor icon
4. Click on any UI element (tab bar, toolbar button, urlbar)
5. The element's id= and class= attributes appear in the inspector
6. Right-click → Copy → CSS Selector to get the full path
```

Key element IDs to know:

| Element | Selector |
|---|---|
| Tab bar strip | `#TabsToolbar` |
| Individual tab | `.tabbrowser-tab` |
| Active/selected tab | `.tabbrowser-tab[selected]` |
| URL bar container | `#urlbar` |
| Navigation toolbar | `#nav-bar` |
| Sidebar | `#sidebar-box` |
| Menu bar | `#toolbar-menubar` |
| Extensions area | `#unified-extensions-button` |
| Window title bar | `#titlebar` |

---

## 129.3 Compact / Ultra-Compact Mode

Firefox 89+ removed compact density from the UI but kept the CSS variable:

```css
/* userChrome.css — restore compact mode */
@media (-moz-bool-pref: "browser.compactmode.show") {}

/* Force compact density directly */
:root {
  --tab-min-height: 28px !important;
}

#TabsToolbar {
  --tab-min-height: 28px;
}

#nav-bar {
  --toolbarbutton-inner-padding: 4px !important;
}
```

For ultra-compact (hide menu bar and bookmarks bar permanently):
```css
#toolbar-menubar { display: none !important; }
#PersonalToolbar  { display: none !important; }
```

---

## 129.4 Hiding the Tab Bar (Tree Style Tab / Vertical Tabs)

The most common userChrome customization: hide the horizontal tab bar when using Tree Style Tab (TST) or Firefox's native vertical tabs (134+).

### For Tree Style Tab extension

```css
/* userChrome.css */
#TabsToolbar {
  visibility: collapse !important;
}

/* Keep the close button accessible via CSD */
#TabsToolbar-customization-target {
  display: none !important;
}
```

### For Firefox 133+ native vertical tabs

Firefox 133 added native vertical tab support. Enable it:
```
about:config → sidebar.revamp = true
               sidebar.verticalTabs = true
```

Then hide the now-redundant top tab bar:
```css
/* Only hide when sidebar is showing vertical tabs */
:root:has(#sidebar-main:not([hidden])) #TabsToolbar {
  display: none !important;
}
```

### Sidebar width tuning

```css
#sidebar-box {
  min-width: 200px !important;
  max-width: 350px !important;
}

/* TST sidebar background match */
#sidebar {
  background-color: #1a1b26 !important;
}
```

---

## 129.5 Tokyo Night Theme

Complete Tokyo Night userChrome.css:

```css
/* userChrome.css — Tokyo Night */
@import url("tokyo-night-variables.css");

:root {
  /* Palette */
  --tn-bg:       #1a1b26;
  --tn-bg-dark:  #16161e;
  --tn-bg-light: #24283b;
  --tn-fg:       #a9b1d6;
  --tn-blue:     #7aa2f7;
  --tn-cyan:     #7dcfff;
  --tn-purple:   #bb9af7;
  --tn-red:      #f7768e;
  --tn-green:    #9ece6a;
  --tn-border:   #292e42;
  --tn-comment:  #565f89;

  /* Apply to Firefox chrome variables */
  --toolbar-bgcolor:          var(--tn-bg) !important;
  --toolbar-color:            var(--tn-fg) !important;
  --toolbarbutton-hover-background: rgba(122,162,247,0.15) !important;
  --tab-selected-bgcolor:     var(--tn-bg-light) !important;
  --tab-selected-color:       var(--tn-blue) !important;
  --urlbar-background-color:  var(--tn-bg-dark) !important;
  --urlbar-color:             var(--tn-fg) !important;
  --panel-background:         var(--tn-bg) !important;
  --panel-color:              var(--tn-fg) !important;
}

/* Window background */
#main-window {
  background-color: var(--tn-bg) !important;
}

/* Tab bar */
#TabsToolbar {
  background-color: var(--tn-bg-dark) !important;
}

.tabbrowser-tab .tab-background {
  border-radius: 6px 6px 0 0 !important;
  margin-block: 4px 0 !important;
}

.tabbrowser-tab[selected] .tab-background {
  background-color: var(--tn-bg-light) !important;
  border-top: 2px solid var(--tn-blue) !important;
}

.tabbrowser-tab:not([selected]):hover .tab-background {
  background-color: rgba(122,162,247,0.08) !important;
}

.tab-text {
  color: var(--tn-comment) !important;
}

.tabbrowser-tab[selected] .tab-text {
  color: var(--tn-blue) !important;
  font-weight: 600 !important;
}

/* URL bar */
#urlbar {
  background-color: var(--tn-bg-dark) !important;
  border: 1px solid var(--tn-border) !important;
  border-radius: 8px !important;
  color: var(--tn-fg) !important;
}

#urlbar:focus-within {
  border-color: var(--tn-blue) !important;
  box-shadow: 0 0 0 2px rgba(122,162,247,0.2) !important;
}

#urlbar-input {
  color: var(--tn-fg) !important;
}

/* Toolbar buttons */
.toolbarbutton-1 > .toolbarbutton-icon {
  fill: var(--tn-comment) !important;
}

.toolbarbutton-1:hover > .toolbarbutton-icon {
  fill: var(--tn-blue) !important;
}

/* Navigation toolbar */
#nav-bar {
  background-color: var(--tn-bg) !important;
  border-bottom: 1px solid var(--tn-border) !important;
}

/* Dropdown panels */
.panel-arrowcontent, .menupopup-arrowscrollbox {
  background-color: var(--tn-bg-light) !important;
  border: 1px solid var(--tn-border) !important;
  border-radius: 8px !important;
}

.menuitem-iconic, menuitem, .menuitem-text-only {
  color: var(--tn-fg) !important;
}

menuitem:hover {
  background-color: rgba(122,162,247,0.15) !important;
  color: var(--tn-blue) !important;
}
```

---

## 129.6 Cyberpunk Neon Theme

```css
/* userChrome.css — Cyberpunk Neon */
:root {
  --cp-bg:      #0a0a0f;
  --cp-bg-alt:  #0d0d14;
  --cp-cyan:    #00ffff;
  --cp-magenta: #ff00ff;
  --cp-yellow:  #f7f70a;
  --cp-fg:      #e0e0f0;
  --cp-border:  #1a1a2e;
  --cp-dim:     #555577;

  --toolbar-bgcolor: var(--cp-bg) !important;
  --toolbar-color:   var(--cp-fg) !important;
}

#main-window {
  background-color: var(--cp-bg) !important;
}

#TabsToolbar {
  background-color: var(--cp-bg-alt) !important;
  border-bottom: 1px solid var(--cp-cyan) !important;
}

.tabbrowser-tab[selected] .tab-background {
  background-color: var(--cp-bg) !important;
  border-top: 2px solid var(--cp-cyan) !important;
}

.tabbrowser-tab[selected] .tab-text {
  color: var(--cp-cyan) !important;
  text-shadow: 0 0 8px var(--cp-cyan) !important;
}

#urlbar {
  background-color: var(--cp-bg-alt) !important;
  border: 1px solid var(--cp-border) !important;
  border-radius: 0 !important;
  color: var(--cp-fg) !important;
}

#urlbar:focus-within {
  border-color: var(--cp-magenta) !important;
  box-shadow: 0 0 8px rgba(255,0,255,0.4) !important;
}

#nav-bar {
  background-color: var(--cp-bg) !important;
  border-bottom: 1px solid #1a1a2e !important;
}

.toolbarbutton-1 > .toolbarbutton-icon {
  fill: var(--cp-dim) !important;
}
.toolbarbutton-1:hover > .toolbarbutton-icon {
  fill: var(--cp-magenta) !important;
  filter: drop-shadow(0 0 4px var(--cp-magenta)) !important;
}
```

---

## 129.7 userContent.css: New Tab and About Pages

`userContent.css` applies to page content, including the new tab page and `about:` pages:

```css
/* userContent.css */

/* New tab page — dark background if not using an extension */
@-moz-document url("about:newtab"), url("about:home") {
  body {
    background-color: #1a1b26 !important;
    color: #a9b1d6 !important;
  }

  /* Hide default Firefox sponsored shortcuts */
  .top-site-outer.sponsored {
    display: none !important;
  }

  /* Hide Pocket content */
  section[data-section-id="topstories"] {
    display: none !important;
  }
}

/* about:config page */
@-moz-document url("about:config") {
  :root {
    background-color: #1a1b26 !important;
    color: #a9b1d6 !important;
  }
  table { background-color: #16161e !important; }
  td, th { border-color: #292e42 !important; }
  tr:hover td { background-color: #24283b !important; }
}
```

---

## 129.8 Pre-made Theme Frameworks

Rather than writing from scratch, several frameworks provide a base:

| Framework | Style | Installation |
|---|---|---|
| **Firefox-One** | Minimal, floating tabs | Copy to `chrome/` |
| **Catppuccin for Firefox** | Mocha/Latte/Frappé | CSS + `about:addons` theme |
| **WhiteSur** | macOS-like | Script installer |
| **Arc-for-the-win** | Arc theme port | CSS files |
| **Lepton** | Compact, ProtonFix | `install.sh` |

```bash
# Catppuccin — install via extension (simpler) + userChrome accent
# https://github.com/catppuccin/firefox

# Lepton (compact + many fixes)
git clone https://github.com/black7375/Firefox-UI-Fix
cd Firefox-UI-Fix
./install.sh
```

---

## 129.9 Firefox Color Extension vs. Manual CSS

The **Firefox Color** extension (addons.mozilla.org) provides a GUI for recoloring the Firefox chrome without touching CSS files. It exports/imports theme JSON, making it easy to share palettes.

Limitations vs. userChrome.css:
- Cannot restructure the UI (move/hide elements)
- Cannot restyle tabs beyond colors/fonts
- Cannot touch userContent.css (new tab page)

Use Firefox Color for quick palette matching, userChrome.css for structural changes.

---

## 129.10 CSD and Wayland Window Controls

On Wayland with client-side decorations, Firefox draws its own title bar and window buttons. To restyle them:

```css
/* Remove CSD title bar (compositor handles decorations) */
#titlebar {
  display: none !important;
}

/* Or restyle the drag area */
.titlebar-buttonbox-container {
  display: none !important;
}

/* Move window controls into the toolbar */
#TabsToolbar .titlebar-buttonbox-container {
  display: flex !important;
}
```

For compositors like Hyprland that handle all window decorations (SSD), you typically want:
```css
/* Hide the Firefox CSD buttons entirely */
.titlebar-buttonbox { display: none !important; }
#titlebar { height: 0 !important; }
```

---

## 129.11 Useful about:config Flags

```
# Wayland-specific
media.ffmpeg.vaapi.enabled = true          # VAAPI hardware video decoding
widget.wayland.fractional-scale.enabled = true  # Fractional scale (130+)
apz.gtk.kinetic_scroll.enabled = true      # Smooth touchpad scrolling

# Theming
browser.theme.content-theme = 0           # Force dark content (0=dark, 1=light, 2=system)
browser.compactmode.show = true           # Restore compact density option
devtools.chrome.enabled = true            # Enable browser toolbox

# Performance
gfx.webrender.all = true                  # Force WebRender
layers.acceleration.force-enabled = true  # GPU acceleration
```

---

## 129.12 Integrating with pywal / matugen

Generate a Firefox userChrome.css from your active color scheme:

```bash
# ~/.config/wal/templates/userChrome.css
# (pywal template syntax)

:root {
  --wal-bg:      {background};
  --wal-fg:      {foreground};
  --wal-color0:  {color0};
  --wal-color1:  {color1};
  --wal-color2:  {color2};
  --wal-color4:  {color4};
  --wal-color5:  {color5};
  --wal-color6:  {color6};

  --toolbar-bgcolor: var(--wal-bg) !important;
  --toolbar-color:   var(--wal-fg) !important;
  --tab-selected-bgcolor: var(--wal-color0) !important;
}
```

```bash
# Apply after wal runs
wal -i ~/wallpapers/current.png
cp ~/.cache/wal/userChrome.css \
   ~/.mozilla/firefox/*.default-release/chrome/userChrome.css
```

For `matugen`:
```toml
# ~/.config/matugen/config.toml
[[templates]]
input_path  = "~/.config/matugen/templates/userChrome.css"
output_path = "~/.mozilla/firefox/<profile>/chrome/userChrome.css"
```
