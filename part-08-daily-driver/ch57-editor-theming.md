# Chapter 57 — Editor Theming: Neovim, VS Code, Helix, Emacs

## Overview

The editor is the single largest surface area in most developer rices. A beautiful,
consistent editor theme ties the whole aesthetic together. Unlike a terminal background
or a bar widget, you spend the majority of your working time inside an editor — which
means every detail matters: the syntax highlight palette, the gutter color, the status
line font, the indent guide opacity, and the way the cursor blends with highlighted text.
Getting editor theming right is not simply "pick a colorscheme and move on"; it involves
coordinating font rendering, icon sets, integration with language servers, and ensuring
the editor matches the rest of your Wayland rice.

This chapter covers the four most popular editors in the modern Linux ricing scene:
Neovim (the dominant terminal editor), VS Code (the GUI hybrid), Helix (the rising
challenger), and Emacs (the lisp machine that never dies). Each section provides
complete, working configuration that you can drop into place. Cross-references to
adjacent chapters handle font installation (Ch 37), pywal palette generation (Ch 38),
Stylix for NixOS (Ch 40), and compositor window rules (Ch 53).

The guiding principle throughout is **consistency**: terminal background = editor
background = bar background = notification background. One palette, zero visual noise.

---

## 57.1 Neovim — The Ricing Editor of Choice

Neovim is the preferred canvas for ricing because its Lua configuration language gives
you full programmatic control over every visual element. The community has produced
hundreds of colorscheme plugins, each shipping their own palette and integration
hooks for nvim-treesitter, nvim-cmp, Telescope, lualine, and so forth. The result is
that switching colorschemes in Neovim means everything — syntax, UI chrome,
diagnostics, git annotations — flips to a coherent new palette in one line.

The dominant package manager as of 2025 is `lazy.nvim`. It handles lazy-loading,
lockfiles, and update hygiene. All code in this section assumes you are running
`lazy.nvim` configured at `~/.config/nvim/lua/plugins/`. If you are still on
`packer.nvim` or `vim-plug`, the plugin specs translate directly; only the wrapper
syntax differs. See the lazy.nvim migration guide at `https://lazy.folke.io/`.

### Installing a Colorscheme with lazy.nvim

Every colorscheme plugin follows the same pattern: high priority (so it loads before
UI plugins), an `opts` table passed to `setup()`, and a `config` function that applies
the scheme via `vim.cmd.colorscheme`. Setting `priority = 1000` ensures the
colorscheme is sourced before any other plugin, preventing flicker on startup.

```lua
-- ~/.config/nvim/lua/plugins/colorscheme.lua
return {
    {
        "catppuccin/nvim",
        name = "catppuccin",
        priority = 1000,
        opts = {
            flavour = "mocha",                -- latte | frappe | macchiato | mocha
            transparent_background = true,   -- works with terminal opacity
            show_end_of_buffer = false,
            term_colors = true,
            dim_inactive = { enabled = false, shade = "dark", percentage = 0.15 },
            styles = {
                comments = { "italic" },
                conditionals = { "italic" },
                loops = {},
                functions = {},
                keywords = {},
                strings = {},
                variables = {},
                numbers = {},
                booleans = {},
                properties = {},
                types = {},
                operators = {},
            },
            integrations = {
                cmp              = true,
                gitsigns         = true,
                nvimtree         = true,
                treesitter       = true,
                telescope        = { enabled = true, style = "nvchad" },
                which_key        = true,
                indent_blankline = { enabled = true, scope_color = "lavender" },
                mini             = { enabled = true, indentscope_color = "" },
                lsp_trouble      = true,
                mason            = true,
                neotree          = true,
                noice            = true,
                notify           = false,
                rainbow_delimiters = true,
            },
            custom_highlights = function(colors)
                return {
                    Comment     = { fg = colors.overlay1 },
                    LineNr      = { fg = colors.surface1 },
                    CursorLineNr = { fg = colors.lavender, style = { "bold" } },
                }
            end,
        },
        config = function(_, opts)
            require("catppuccin").setup(opts)
            vim.cmd.colorscheme "catppuccin"
        end,
    },
}
```

**Popular Neovim colorschemes:**

| Theme | Style | GitHub |
|-------|-------|--------|
| catppuccin | Soft pastel | catppuccin/nvim |
| kanagawa | Japanese ink | rebelot/kanagawa.nvim |
| rose-pine | Warm muted | rose-pine/neovim |
| tokyonight | Purple-blue | folke/tokyonight.nvim |
| gruvbox-material | Warm retro | sainnhe/gruvbox-material |
| nightfox | Forest tones | EdenEast/nightfox.nvim |
| onedark | VSCode-like | navarasu/onedark.nvim |
| everforest | Nature/earth | sainnhe/everforest |
| oxocarbon | IBM Carbon | nyoom-engineering/oxocarbon.nvim |
| melange | Warm mono | savq/melange-nvim |

### Status Line: lualine.nvim

lualine.nvim is the de-facto status line for Neovim ricing. It has first-class
theme support for all major colorschemes, accepts custom component lists, and renders
Nerd Font separators natively. The `theme = "auto"` option reads the active
colorscheme and applies the matching lualine theme automatically, which means
colorscheme-switches also update the bar.

```lua
-- ~/.config/nvim/lua/plugins/lualine.lua
return {
    {
        "nvim-lualine/lualine.nvim",
        dependencies = { "nvim-tree/nvim-web-devicons" },
        opts = {
            options = {
                theme                = "catppuccin",
                component_separators = { left = "", right = "" },
                section_separators   = { left = "", right = "" },
                globalstatus         = true,
                disabled_filetypes   = { statusline = { "dashboard", "alpha" } },
            },
            sections = {
                lualine_a = { "mode" },
                lualine_b = { "branch", "diff", "diagnostics" },
                lualine_c = { { "filename", path = 1, symbols = {
                    modified = " ●", readonly = " ", unnamed = "[No Name]"
                } } },
                lualine_x = {
                    { "encoding", show_bomb = false },
                    "fileformat",
                    { "filetype", icon_only = false },
                },
                lualine_y = { "progress" },
                lualine_z = { "location" },
            },
            inactive_sections = {
                lualine_c = { { "filename", path = 1 } },
                lualine_x = { "location" },
            },
            extensions = { "neo-tree", "lazy", "trouble", "quickfix" },
        },
    },
}
```

### File Icons: nvim-web-devicons

Nerd Font file icons appear throughout Neovim — in the status line filetype
component, in neo-tree or nvim-tree file browsers, in Telescope pickers, and in
nvim-cmp completion menus. The `nvim-web-devicons` plugin maps filetypes and
extensions to Unicode code points in your Nerd Font. It must be lazy-loaded as a
dependency rather than eagerly loaded.

```lua
-- ~/.config/nvim/lua/plugins/devicons.lua
return {
    {
        "nvim-tree/nvim-web-devicons",
        lazy = true,
        opts = {
            -- Override individual icons
            override_by_extension = {
                ["nix"] = { icon = "", color = "#7ebae4", name = "Nix" },
                ["toml"] = { icon = "", color = "#9ece6a", name = "Toml" },
            },
            default = true,
        },
    },
}
```

Requires a Nerd Font installed and configured as your terminal font (see Ch 37 for
font installation and `fc-cache -fv` cache rebuilding).

### Dashboard: alpha-nvim

A splash screen sets the tone for the entire session. `alpha-nvim` renders ASCII art,
keybind shortcuts, and recent-file lists on startup. The `startify` theme is a
minimal list; `dashboard` is the classic centered layout.

```lua
-- ~/.config/nvim/lua/plugins/alpha.lua
return {
    {
        "goolord/alpha-nvim",
        event = "VimEnter",
        dependencies = { "nvim-tree/nvim-web-devicons" },
        config = function()
            local alpha = require("alpha")
            local dashboard = require("alpha.themes.dashboard")

            dashboard.section.header.val = {
                "                                                     ",
                "  ███╗   ██╗███████╗ ██████╗ ██╗   ██╗██╗███╗   ███╗",
                "  ████╗  ██║██╔════╝██╔═══██╗██║   ██║██║████╗ ████║",
                "  ██╔██╗ ██║█████╗  ██║   ██║██║   ██║██║██╔████╔██║",
                "  ██║╚██╗██║██╔══╝  ██║   ██║╚██╗ ██╔╝██║██║╚██╔╝██║",
                "  ██║ ╚████║███████╗╚██████╔╝ ╚████╔╝ ██║██║ ╚═╝ ██║",
                "  ╚═╝  ╚═══╝╚══════╝ ╚═════╝   ╚═══╝  ╚═╝╚═╝     ╚═╝",
                "                                                     ",
            }
            dashboard.section.buttons.val = {
                dashboard.button("f", "  Find file",    ":Telescope find_files<CR>"),
                dashboard.button("r", "  Recent files", ":Telescope oldfiles<CR>"),
                dashboard.button("g", "  Grep text",    ":Telescope live_grep<CR>"),
                dashboard.button("n", "  New file",     ":enew<CR>"),
                dashboard.button("q", "  Quit",         ":qa<CR>"),
            }
            alpha.setup(dashboard.config)
        end,
    },
}
```

### Indent Guides: indent-blankline.nvim

Visual indent guides dramatically improve readability in deeply-nested code. The
v3 API uses the `ibl` module and supports scope highlighting that tracks the current
cursor context using treesitter:

```lua
-- ~/.config/nvim/lua/plugins/indent.lua
return {
    {
        "lukas-reineke/indent-blankline.nvim",
        main  = "ibl",
        event = "BufReadPost",
        opts  = {
            indent = {
                char      = "│",
                tab_char  = "│",
                highlight = "IblIndent",
            },
            scope = {
                enabled   = true,
                highlight = "IblScope",
                show_start = true,
                show_end   = false,
                injected_languages = false,
            },
            exclude = {
                filetypes = {
                    "help", "alpha", "dashboard", "neo-tree",
                    "Trouble", "trouble", "lazy", "mason",
                    "notify", "toggleterm", "lazyterm",
                },
            },
        },
    },
}
```

### pywal / matugen Integration

For users who generate dynamic palettes from wallpapers (see Ch 38 for pywal,
Ch 41 for matugen), Neovim can load these colors at startup:

```bash
# 1. Create the wal template at ~/.config/wal/templates/colors-wal.vim
cat > ~/.config/wal/templates/colors-wal.vim << 'EOF'
" Generated by pywal - do not edit manually
let g:terminal_color_0  = "{color0}"
let g:terminal_color_1  = "{color1}"
let g:terminal_color_2  = "{color2}"
let g:terminal_color_3  = "{color3}"
let g:terminal_color_4  = "{color4}"
let g:terminal_color_5  = "{color5}"
let g:terminal_color_6  = "{color6}"
let g:terminal_color_7  = "{color7}"
let g:terminal_color_8  = "{color8}"
let g:terminal_color_9  = "{color9}"
let g:terminal_color_10 = "{color10}"
let g:terminal_color_11 = "{color11}"
let g:terminal_color_12 = "{color12}"
let g:terminal_color_13 = "{color13}"
let g:terminal_color_14 = "{color14}"
let g:terminal_color_15 = "{color15}"
EOF

# 2. After running wal -i wallpaper.jpg, source the output in Neovim init.lua:
```

```lua
-- ~/.config/nvim/init.lua  (pywal dynamic colors)
local wal_colors = vim.fn.expand("~/.cache/wal/colors-wal.vim")
if vim.fn.filereadable(wal_colors) == 1 then
    vim.cmd("source " .. wal_colors)
end
```

For matugen users, the `base16-nvim` plugin combined with a matugen base16 template
provides the cleanest pipeline. See Ch 41 for the matugen template syntax.

---

## 57.2 VS Code Theming

VS Code (running as `code` or the open-source `code-oss`) on Wayland behaves like a
Chromium-based application: it requires explicit Ozone flags, can leverage compositor
transparency rules, and has its own extension marketplace for themes. The JSON-based
`settings.json` is the canonical theming surface.

Despite being a GUI app, VS Code is used in terminal-centric rices because of its
debugger, remote-SSH, and extension ecosystem. The goal is to make it visually
indistinguishable from the rest of your rice.

### Installing Color Themes

Themes are distributed as extensions. Install from the CLI to avoid the GUI:

```bash
# Catppuccin — ships Mocha, Macchiato, Frappe, Latte flavors + icon theme
code --install-extension catppuccin.catppuccin-vsc
code --install-extension catppuccin.catppuccin-vsc-icons

# Tokyo Night — three variants: Storm, Night, Moon
code --install-extension enkia.tokyo-night

# One Dark Pro
code --install-extension zhuangtongfa.material-theme

# Gruvbox Theme
code --install-extension jdinhlife.gruvbox

# Rosé Pine — Dawn, Moon, Main
code --install-extension mvllow.rose-pine

# Ayu — Light, Mirage, Dark
code --install-extension teabyii.ayu

# Dracula Official
code --install-extension dracula-theme.theme-dracula
```

**Popular VS Code themes:**

| Extension ID | Variants | Style |
|---|---|---|
| catppuccin.catppuccin-vsc | Mocha / Macchiato / Frappe / Latte | Soft pastel |
| enkia.tokyo-night | Night / Storm / Moon | Purple-blue |
| zhuangtongfa.material-theme | One Dark Pro / Flat / Mix | Dark minimal |
| jdinhlife.gruvbox | Dark/Light + soft/hard | Warm retro |
| mvllow.rose-pine | Main / Moon / Dawn | Muted warm |
| sdras.night-owl | Night Owl / Light Owl | Teal+orange |
| Equinusocio.vsc-material-theme | Many | Material Design |

### Complete settings.json for a Catppuccin Rice

The `settings.json` file lives at `~/.config/Code/User/settings.json` on Linux.
Wayland-specific launch flags should be set in `argv.json`, not here.

```json
{
    "workbench.colorTheme": "Catppuccin Mocha",
    "workbench.iconTheme": "catppuccin-mocha",
    "workbench.productIconTheme": "fluent-icons",
    "editor.fontFamily": "'JetBrainsMono Nerd Font', 'Fira Code', monospace",
    "editor.fontLigatures": true,
    "editor.fontSize": 13,
    "editor.lineHeight": 1.6,
    "editor.letterSpacing": 0.3,
    "editor.cursorBlinking": "smooth",
    "editor.cursorSmoothCaretAnimation": "on",
    "editor.cursorStyle": "line",
    "editor.renderWhitespace": "boundary",
    "editor.renderLineHighlight": "gutter",
    "editor.guides.indentation": true,
    "editor.guides.bracketPairs": true,
    "editor.bracketPairColorization.enabled": true,
    "editor.scrollbar.verticalScrollbarSize": 6,
    "editor.minimap.enabled": false,
    "editor.padding.top": 8,
    "terminal.integrated.fontFamily": "'JetBrainsMono Nerd Font'",
    "terminal.integrated.fontSize": 13,
    "window.titleBarStyle": "custom",
    "window.zoomLevel": 0,
    "workbench.colorCustomizations": {
        "editor.background": "#1e1e2e",
        "sideBar.background": "#181825",
        "activityBar.background": "#181825",
        "statusBar.background": "#181825",
        "titleBar.activeBackground": "#181825",
        "panel.background": "#181825",
        "editorGroupHeader.tabsBackground": "#181825",
        "tab.inactiveBackground": "#181825",
        "tab.activeBackground": "#1e1e2e"
    }
}
```

### Wayland Launch Flags

VS Code must be launched with Ozone flags to use native Wayland rendering. Without
them it falls back to XWayland, losing HiDPI sharpness and fractional scaling:

```bash
# ~/.config/code-flags.conf  (read by code wrapper on some distros)
--enable-features=UseOzonePlatform,WaylandWindowDecorations
--ozone-platform=wayland
--enable-wayland-ime

# Or set in ~/.config/electron-flags.conf for all Electron apps:
--enable-features=UseOzonePlatform,WaylandWindowDecorations
--ozone-platform=wayland
```

Alternatively create a wrapper script or desktop entry override:

```bash
# ~/.local/share/applications/code.desktop  (override)
[Desktop Entry]
Name=Visual Studio Code
Exec=/usr/bin/code --enable-features=UseOzonePlatform,WaylandWindowDecorations --ozone-platform=wayland %F
```

### Transparent VS Code on Wayland

Terminal-based editors get transparency for free from the terminal emulator's
compositor rules. VS Code requires different treatment:

```conf
# Hyprland window rules — ~/.config/hypr/hyprland.conf
windowrulev2 = opacity 0.93 0.88,class:^(Code)$
windowrulev2 = opacity 0.93 0.88,class:^(code-oss)$
```

For blur effect (Hyprland only):
```conf
decoration {
    blur {
        enabled = true
        size = 8
        passes = 2
        new_optimizations = true
    }
}
windowrulev2 = blur,class:^(Code)$
```

The `Custom CSS and JS Loader` extension (`be5invis.vscode-custom-css`) allows
CSS overrides including `backdrop-filter: blur()`, though this requires running VS
Code with `--no-sandbox` and trusting the extension:

```css
/* ~/.config/Code/User/custom.css */
.monaco-workbench {
    background: rgba(30, 30, 46, 0.85) !important;
}
.editor-group-container {
    background: transparent !important;
}
```

---

## 57.3 Helix — The Modern Modal Editor

Helix is a post-modern modal editor written in Rust, shipping with built-in LSP
support, tree-sitter highlighting, and a comprehensive theme library — all with zero
plugin infrastructure. For ricing purposes this is both a strength and a constraint:
you cannot install third-party colorscheme plugins, but every theme that ships
with Helix is already polished and integrated across all UI surfaces.

Helix themes are TOML files that define a palette and map semantic highlight
keys to palette colors. The standard distribution includes 60+ themes.

### Basic Configuration

```toml
# ~/.config/helix/config.toml
theme = "catppuccin_mocha"

[editor]
line-number          = "relative"
cursorline           = true
color-modes          = true
idle-timeout         = 50
completion-trigger-len = 1
auto-format          = true
rulers               = [80, 120]

[editor.cursor-shape]
insert  = "bar"
normal  = "block"
select  = "underline"

[editor.statusline]
left   = ["mode", "spinner", "file-name", "file-modification-indicator"]
center = []
right  = ["diagnostics", "selections", "primary-selection-length",
          "position", "position-percentage", "spacer",
          "total-line-numbers", "spacer", "file-encoding",
          "file-line-ending", "file-type"]
separator = "│"
mode.normal = "NORMAL"
mode.insert = "INSERT"
mode.select = "SELECT"

[editor.indent-guides]
render    = true
character = "│"
skip-levels = 1

[editor.lsp]
display-messages      = true
display-inlay-hints   = true
```

### Built-in Theme Catalog

```bash
# List all built-in themes
hx --health 2>/dev/null | grep -A1 "Theme"
ls /usr/share/helix/runtime/themes/      # system install
ls ~/.config/helix/runtime/themes/       # cargo install

# Popular built-in themes:
# catppuccin_mocha  catppuccin_latte  catppuccin_frappe  catppuccin_macchiato
# gruvbox           gruvbox_dark_hard  gruvbox_light
# tokyonight        tokyonight_storm   tokyonight_moon
# rose_pine         rose_pine_dawn     rose_pine_moon
# nord              dracula            everforest_dark
# ayu_dark          ayu_mirage         one_dark
# kanagawa          fleet_dark         mellow
```

### Writing a Custom Helix Theme

Custom themes live in `~/.config/helix/themes/`. They can inherit from a built-in
theme and override specific keys, keeping maintenance minimal:

```toml
# ~/.config/helix/themes/my_mocha.toml
inherits = "catppuccin_mocha"

# Override the background to match your terminal exactly
"ui.background" = { bg = "#1e1e2e" }
"ui.statusline"          = { fg = "text",    bg = "#181825" }
"ui.statusline.inactive" = { fg = "overlay1", bg = "#181825" }
"ui.popup"               = { bg = "#181825" }
"ui.menu"                = { bg = "#181825" }

# Tweak comment style
"comment"     = { fg = "overlay1", modifiers = ["italic"] }
"comment.doc" = { fg = "overlay2", modifiers = ["italic"] }
```

Then set `theme = "my_mocha"` in `config.toml`.

---

## 57.4 Emacs Theming

Emacs is the most extensible editor in this list — every face (Emacs' term for a
visual style element) is individually configurable down to fringe width and mode-line
box padding. The trade-off is configuration complexity. Two distributions dominate
the ricing scene: **DOOM Emacs** (fast, opinionated, large community) and **Spacemacs**
(heavier, more batteries-included). Both wrap upstream Emacs and provide their own
theme ecosystems.

This section covers DOOM Emacs primarily, with notes for vanilla Emacs users.

### DOOM Emacs Theming

DOOM ships its own theme collection under the `doom-themes` package. Each theme
integrates with DOOM's modeline, dashboard, treemacs, and org-mode faces:

```elisp
;; ~/.doom.d/config.el
(setq doom-theme 'doom-catppuccin)
;; Other popular choices:
;; doom-gruvbox  doom-gruvbox-light  doom-nord  doom-nord-light
;; doom-tokyo-night  doom-rose-pine  doom-dracula  doom-one
;; doom-solarized-dark  doom-vibrant  doom-moonlight

;; Font configuration
(setq doom-font (font-spec :family "JetBrainsMono Nerd Font" :size 12 :weight 'medium)
      doom-variable-pitch-font (font-spec :family "Inter" :size 13)
      doom-big-font (font-spec :family "JetBrainsMono Nerd Font" :size 18))

;; Fringe + line numbers
(setq display-line-numbers-type 'relative)

;; Transparent background (coordinates with Hyprland opacity rule)
(add-to-list 'default-frame-alist '(alpha-background . 90))
```

After editing `config.el`, reload with `M-x doom/reload` or restart:

```bash
~/.config/emacs/bin/doom sync
~/.config/emacs/bin/doom build
```

### Catppuccin for Vanilla Emacs

For users not running DOOM or Spacemacs, the `catppuccin-theme` package provides
the same palette through `use-package`:

```elisp
;; ~/.emacs.d/init.el
(use-package catppuccin-theme
    :ensure t
    :config
    (setq catppuccin-flavor 'mocha)  ;; latte | frappe | macchiato | mocha
    (load-theme 'catppuccin :no-confirm))

;; Font
(set-face-attribute 'default nil
    :family "JetBrainsMono Nerd Font"
    :height 120
    :weight 'medium)

;; Transparent frame
(set-frame-parameter nil 'alpha-background 90)
(add-to-list 'default-frame-alist '(alpha-background . 90))
```

### DOOM Modeline

DOOM modeline is the standard status line for both DOOM Emacs and vanilla Emacs:

```elisp
;; ~/.doom.d/config.el  (DOOM users — doom-modeline is included, just configure it)
(after! doom-modeline
  (setq doom-modeline-height 28
        doom-modeline-bar-width 4
        doom-modeline-window-width-limit 85
        doom-modeline-project-detection 'auto
        doom-modeline-icon t
        doom-modeline-major-mode-icon t
        doom-modeline-major-mode-color-icon t
        doom-modeline-buffer-state-icon t
        doom-modeline-buffer-modification-icon t
        doom-modeline-enable-word-count nil
        doom-modeline-time t))
```

For vanilla Emacs with `use-package`:

```elisp
(use-package doom-modeline
    :ensure t
    :hook (after-init . doom-modeline-mode)
    :custom
    (doom-modeline-height 28)
    (doom-modeline-icon t)
    (doom-modeline-project-detection 'project))
```

---

## 57.5 Transparent Editors

Transparency handling differs fundamentally between terminal-based editors and GUI
editors. Understanding this distinction prevents hours of confused debugging.

**Terminal-based editors** (Neovim in Kitty/Alacritty/foot, Helix) inherit transparency
from the terminal emulator. Set `background_opacity 0.92` in Kitty's config or the
equivalent for your terminal (see Ch 50), and Neovim's `transparent_background = true`
in its colorscheme opts removes the editor's own background fill so the terminal's
composited background shows through.

**GUI editors** (VS Code, Emacs GUI frame, Zed) are standalone windows managed
directly by the Wayland compositor. Transparency must be applied via compositor
window rules:

```conf
# Hyprland — ~/.config/hypr/hyprland.conf
# Format: windowrulev2 = opacity <active> <inactive>, class:^(WM_CLASS)$
windowrulev2 = opacity 0.92 0.92, class:^(Code)$
windowrulev2 = opacity 0.92 0.92, class:^(code-oss)$
windowrulev2 = opacity 0.94 0.90, class:^(emacs)$
windowrulev2 = opacity 0.94 0.90, class:^(Emacs)$
```

For Sway users, window opacity is set per-criteria:

```conf
# ~/.config/sway/config
for_window [app_id="code-oss"] opacity 0.92
for_window [app_id="emacs"]    opacity 0.94
```

VS Code additionally requires its `--enable-features=UseOzonePlatform` flag (see
§57.2) otherwise the opacity rule applies to the XWayland proxy window, producing
incorrect results on HiDPI displays. See Ch 53 for Hyprland window rules in depth.

---

## 57.6 Consistent Palette Across Tools

The final goal of editor theming is not just a beautiful editor in isolation — it is
a cohesive visual system where the terminal emulator, editor, status bar (Waybar/eww),
notification daemon (mako/dunst), file manager, and launcher all share a single palette.
Inconsistency here — a slightly different background hex in the editor versus the
terminal — is immediately visible and ruins the aesthetic.

The practical approach depends on your distribution and workflow:

**Manual hex coordination** — The simplest method. Pick one palette (e.g., Catppuccin
Mocha) and hard-code the hex values in every tool's config. `#1e1e2e` for base,
`#181825` for mantle, `#313244` for surface0. This is tedious to change but has zero
runtime dependencies.

| Catppuccin Mocha Color | Hex | Typical Use |
|---|---|---|
| Base | `#1e1e2e` | Editor background |
| Mantle | `#181825` | Sidebar, panel background |
| Crust | `#11111b` | Statusbar background |
| Surface0 | `#313244` | Inactive tab background |
| Overlay1 | `#7f849c` | Comments, inactive text |
| Text | `#cdd6f4` | Primary foreground |
| Lavender | `#b4befe` | Accent / cursor |
| Blue | `#89b4fa` | Functions |
| Green | `#a6e3a1` | Strings |
| Red | `#f38ba8` | Errors |
| Yellow | `#f9e2af` | Warnings |

**pywal / wallust** — Generates 16-color palettes from wallpapers and writes
templates for every tool simultaneously. After `wal -i ~/wallpaper.jpg`, source
`~/.cache/wal/colors.sh` in your shell profile and use the provided templates for
Kitty, Neovim, Waybar, mako, etc. See Ch 38 for the full pipeline.

**Stylix (NixOS)** — Declares a single `base16` palette in your NixOS configuration
and Stylix generates theme files for every supported application automatically. This
is the most maintainable approach for NixOS users — changing the wallpaper or palette
requires one line in `flake.nix`. See Ch 40 for Stylix setup.

**matugen** — A Material You palette generator that reads a wallpaper and outputs
tokens in any format you define via templates. More colorful than pywal, less
conservative. See Ch 41 for matugen integration.

A shell function to verify palette consistency across your active configs:

```bash
# ~/.config/shell/functions.sh
check_palette_consistency() {
    local bg="#1e1e2e"
    echo "=== Checking $bg across configs ==="
    grep -r "$bg" \
        ~/.config/nvim/ \
        ~/.config/helix/ \
        ~/.config/kitty/ \
        ~/.config/alacritty/ \
        ~/.config/waybar/ \
        ~/.config/hypr/ \
        2>/dev/null | grep -v ".git" | grep -v "cache"
}
```

---

## 57.7 Font Rendering in Editors

Font rendering quality is often overlooked in editor ricing guides, but it is as
visually impactful as the colorscheme. Wayland passes font rendering to the toolkit
(GTK/Qt/Electron) and ultimately to FreeType/HarfBuzz. For editors:

**Neovim in terminal**: Font rendering is 100% controlled by the terminal emulator.
Use Kitty or foot for best results — both support subpixel antialiasing and fractional
scaling. Configure in `~/.config/kitty/kitty.conf`:

```conf
# ~/.config/kitty/kitty.conf
font_family      JetBrainsMono Nerd Font
bold_font        JetBrainsMono Nerd Font Bold
italic_font      JetBrainsMono Nerd Font Italic
bold_italic_font JetBrainsMono Nerd Font Bold Italic
font_size        13.0
```

**VS Code**: Uses Chromium's text rendering. Enable font ligatures explicitly:

```json
{
    "editor.fontFamily": "'JetBrainsMono Nerd Font', monospace",
    "editor.fontLigatures": "'calt', 'liga', 'ss01', 'ss02'",
    "editor.fontSize": 13,
    "editor.fontWeight": "400"
}
```

**Helix**: Uses the terminal font. No special configuration needed.

**Emacs GUI**: Uses fontconfig and HarfBuzz directly. Enable subpixel rendering:

```elisp
(setq x-use-underline-position-properties t
      x-underline-at-descent-line nil)
;; For HiDPI displays:
(setq-default line-spacing 0.1)
```

System-wide font rendering settings apply to all GUI editors. Set them in
`~/.config/fontconfig/fonts.conf`:

```xml
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <match target="font">
    <edit name="antialias" mode="assign"><bool>true</bool></edit>
    <edit name="hinting" mode="assign"><bool>true</bool></edit>
    <edit name="hintstyle" mode="assign"><const>hintslight</const></edit>
    <edit name="rgba" mode="assign"><const>rgb</const></edit>
    <edit name="lcdfilter" mode="assign"><const>lcddefault</const></edit>
  </match>
</fontconfig>
```

---

## Troubleshooting

### Neovim: colorscheme not applied / flickering on startup

Ensure `priority = 1000` is set in the lazy.nvim spec. Lower-priority plugins that
also touch highlight groups will override your colorscheme if they load first. Check
load order with `:Lazy profile`.

```vim
:Lazy profile          " shows load order and timing
:checkhealth           " general health check
:TSUpdate              " update treesitter parsers (stale parsers break highlights)
```

### Neovim: Nerd Font icons missing (boxes or question marks)

The terminal font must be a Nerd Font. Verify:

```bash
fc-list | grep -i "nerd"
# If empty:
cd /tmp && wget https://github.com/ryanoasis/nerd-fonts/releases/latest/download/JetBrainsMono.tar.xz
tar xf JetBrainsMono.tar.xz -C ~/.local/share/fonts/
fc-cache -fv
```

Then set the terminal font to `JetBrainsMono Nerd Font` and restart the terminal.

### VS Code: blurry text on HiDPI / fractional scaling

VS Code under XWayland uses integer scaling. Fix by forcing native Wayland:

```bash
# Test with explicit flags:
code --enable-features=UseOzonePlatform,WaylandWindowDecorations \
     --ozone-platform=wayland \
     --force-device-scale-factor=1.5   # match your monitor scale
```

Persist in `~/.config/code-flags.conf` or a desktop entry override.

### VS Code: window opacity rule has no effect

Check whether VS Code is running under XWayland or native Wayland:

```bash
# Check the window's app_id in Hyprland:
hyprctl clients | grep -A5 "code"
# Native Wayland: app_id = "code-oss" or "code"
# XWayland:       app_id = "", class = "Code"
```

Hyprland compositor rules use `class:` for XWayland and `initialClass:` for native
Wayland. Adjust the window rule accordingly.

### Helix: custom theme not recognized

Helix looks for user themes in `~/.config/helix/themes/`. The filename (without
`.toml`) becomes the theme name. Verify:

```bash
ls ~/.config/helix/themes/
hx --health 2>&1 | grep -i theme
# In helix: :theme <tab>  to autocomplete and preview
```

### Emacs GUI: alpha-background not working on Wayland

The `alpha-background` frame parameter requires Emacs 29+ built with PGTK support
(`--with-pgtk`). Check your build:

```bash
emacs --version
emacs -Q --eval '(princ (version))' --batch
# PGTK build will show "pgtk" in the build flags:
emacs --batch --eval "(message \"%s\" system-configuration-features)" 2>&1 | grep -i pgtk
```

If your distribution ships an X11-only Emacs build, install `emacs-pgtk` or build
from source with `--with-pgtk`. PGTK (Pure GTK) is required for native Wayland
rendering and the alpha-background frame parameter.

### Inconsistent background colors between terminal and editor

Use `xcolor` or `hyprpicker` to sample the actual rendered pixel color, then compare
with configured hex values:

```bash
# Install hyprpicker
hyprpicker  # click anywhere to get hex value

# Or use xcolor (works on XWayland)
xcolor      # outputs hex to stdout

# Compare with expected:
echo "Expected: #1e1e2e"
```

Rounding differences in color profile conversion (sRGB vs linear) can shift hex
values by 1–2 steps. Force the terminal and editor to the same exact hex.

---

## 57.10 Authoring a Custom Neovim Colorscheme

Applying existing colorschemes is covered in §57.1–57.3. This section covers
creating your own — useful when you have a custom palette (from pywal, matugen,
or a design system) and need a fully integrated colorscheme rather than a
CSS-style override.

### Option A: Raw vim.api.nvim_set_hl()

The lowest-level approach uses the Neovim Lua API directly:

```lua
-- ~/.config/nvim/lua/colors/mycustom.lua
local M = {}

local palette = {
    bg       = "#1a1b26",
    bg2      = "#24283b",
    surface  = "#3b4261",
    fg       = "#a9b1d6",
    comment  = "#565f89",
    blue     = "#7aa2f7",
    cyan     = "#7dcfff",
    green    = "#9ece6a",
    yellow   = "#e0af68",
    orange   = "#ff9e64",
    red      = "#f7768e",
    purple   = "#bb9af7",
    teal     = "#1abc9c",
}

local function hi(group, opts)
    vim.api.nvim_set_hl(0, group, opts)
end

function M.load()
    vim.cmd("hi clear")
    vim.o.background = "dark"
    vim.g.colors_name = "mycustom"

    -- Core UI groups
    hi("Normal",       { fg = palette.fg,      bg = palette.bg })
    hi("NormalFloat",  { fg = palette.fg,      bg = palette.bg2 })
    hi("FloatBorder",  { fg = palette.surface, bg = palette.bg2 })
    hi("Comment",      { fg = palette.comment, italic = true })
    hi("Cursor",       { fg = palette.bg,      bg = palette.fg })
    hi("CursorLine",   { bg = palette.bg2 })
    hi("LineNr",       { fg = palette.surface })
    hi("CursorLineNr", { fg = palette.yellow,  bold = true })
    hi("SignColumn",   { bg = palette.bg })
    hi("StatusLine",   { fg = palette.fg,      bg = palette.bg2 })
    hi("VertSplit",    { fg = palette.surface, bg = palette.bg })
    hi("WinSeparator", { fg = palette.surface })
    hi("Pmenu",        { fg = palette.fg,      bg = palette.bg2 })
    hi("PmenuSel",     { fg = palette.bg,      bg = palette.blue })
    hi("Search",       { fg = palette.bg,      bg = palette.yellow })
    hi("IncSearch",    { fg = palette.bg,      bg = palette.orange })
    hi("Visual",       { bg = palette.surface })

    -- Syntax groups
    hi("Keyword",    { fg = palette.purple, bold = true })
    hi("Function",   { fg = palette.blue })
    hi("String",     { fg = palette.green })
    hi("Number",     { fg = palette.orange })
    hi("Boolean",    { fg = palette.orange })
    hi("Type",       { fg = palette.cyan })
    hi("Constant",   { fg = palette.orange })
    hi("Identifier", { fg = palette.fg })
    hi("Operator",   { fg = palette.cyan })
    hi("Delimiter",  { fg = palette.fg })
    hi("Special",    { fg = palette.yellow })
    hi("Error",      { fg = palette.red })
    hi("Todo",       { fg = palette.yellow, bold = true })

    -- Treesitter semantic tokens (nvim 0.9+)
    hi("@variable",          { fg = palette.fg })
    hi("@variable.builtin",  { fg = palette.red })
    hi("@function",          { fg = palette.blue })
    hi("@function.method",   { fg = palette.blue })
    hi("@keyword",           { fg = palette.purple, bold = true })
    hi("@string",            { fg = palette.green })
    hi("@number",            { fg = palette.orange })
    hi("@type",              { fg = palette.cyan })
    hi("@type.builtin",      { fg = palette.cyan, italic = true })
    hi("@property",          { fg = palette.teal })
    hi("@comment",           { fg = palette.comment, italic = true })
    hi("@punctuation",       { fg = palette.fg })
    hi("@tag",               { fg = palette.red })
    hi("@tag.attribute",     { fg = palette.yellow })

    -- Diagnostic groups
    hi("DiagnosticError",   { fg = palette.red })
    hi("DiagnosticWarn",    { fg = palette.yellow })
    hi("DiagnosticInfo",    { fg = palette.blue })
    hi("DiagnosticHint",    { fg = palette.teal })
    hi("DiagnosticUnderlineError", { sp = palette.red,    undercurl = true })
    hi("DiagnosticUnderlineWarn",  { sp = palette.yellow, undercurl = true })

    -- Git signs (gitsigns.nvim)
    hi("GitSignsAdd",    { fg = palette.green })
    hi("GitSignsChange", { fg = palette.yellow })
    hi("GitSignsDelete", { fg = palette.red })
end

return M
```

```lua
-- Load it from your init.lua or colorscheme.lua:
require("colors.mycustom").load()
```

### Option B: lush.nvim — HSL-based DSL

`lush.nvim` provides a Lua DSL with HSL color math, making it easy to define
a consistent palette with derived shades:

```lua
-- Install: lazy.nvim spec
{ "rktjmp/lush.nvim" }
```

```lua
-- ~/.config/nvim/lua/lush_theme/mytheme.lua
local lush = require("lush")
local hsl = lush.hsl

-- Define palette using HSL
local p = {
    bg       = hsl("#1a1b26"),
    fg       = hsl("#a9b1d6"),
    blue     = hsl("#7aa2f7"),
    green    = hsl("#9ece6a"),
    red      = hsl("#f7768e"),
    purple   = hsl("#bb9af7"),
    yellow   = hsl("#e0af68"),
    comment  = hsl("#565f89"),
}

-- lush DSL: each group is a function call with a table
local theme = lush(function(injected_fns)
    local sym = injected_fns.sym
    return {
        Normal      { bg = p.bg,      fg = p.fg },
        Comment     { fg = p.comment, gui = "italic" },
        Keyword     { fg = p.purple,  gui = "bold" },
        Function    { fg = p.blue },
        String      { fg = p.green },
        Number      { fg = p.yellow },
        Type        { fg = hsl(p.blue).lighten(10) },    -- auto-derived
        Error       { fg = p.red },

        -- Inheritance: link groups to other groups
        Identifier  { Normal },
        Constant    { Number },

        -- Treesitter: using lush sym() for forward references
        sym("@function") { Function },
        sym("@keyword")  { Keyword },
        sym("@string")   { String },
    }
end)

return theme
```

```lua
-- Apply the lush theme:
-- In a colors/mytheme.lua file:
vim.g.colors_name = "mytheme"
require("lush")(require("lush_theme.mytheme"))
```

### Testing highlight groups

```vim
" In Neovim command mode:
:Inspect          " Show highlight groups under cursor (nvim 0.9+)
:hi Comment       " Show current Comment highlight
:hi @function     " Show treesitter function highlight

" Reload colors after editing:
:luafile ~/.config/nvim/lua/colors/mycustom.lua
:luafile ~/.config/nvim/lua/colors/mycustom.lua | lua require("colors.mycustom").load()
```

### Exporting to base16 format

The base16 specification maps a 16-color palette to semantic roles:

```yaml
# ~/.config/base16/mytheme.yaml
scheme: "My Custom"
author: "you"
base00: "1a1b26"   # background
base01: "24283b"   # lighter background
base02: "3b4261"   # selection background
base03: "565f89"   # comments / disabled
base04: "a9b1d6"   # dark foreground
base05: "c0caf5"   # default foreground
base06: "cfc9c2"   # light foreground
base07: "d5d6db"   # lightest foreground
base08: "f7768e"   # red (errors, deletes)
base09: "ff9e64"   # orange (numbers)
base0A: "e0af68"   # yellow (warnings)
base0B: "9ece6a"   # green (strings, success)
base0C: "7dcfff"   # cyan (types, regex)
base0D: "7aa2f7"   # blue (functions)
base0E: "bb9af7"   # purple (keywords)
base0F: "db4b4b"   # brown (deprecated)
```

Use `base16-builder` or `tinted-theming` to generate terminal/editor configs
from this YAML for Kitty, Alacritty, Foot, and WezTerm automatically.

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
