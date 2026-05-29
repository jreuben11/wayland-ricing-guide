# Chapter 57 — Editor Theming: Neovim, VS Code, Helix, Emacs

## Overview
The editor is the single largest surface area in most developer rices. A beautiful,
consistent editor theme ties the whole aesthetic together.

## Sections

### 57.1 Neovim — The Ricing Editor of Choice

Neovim + Catppuccin/Kanagawa/Tokyo Night is the dominant combination in 2024–2026.

**Package manager: lazy.nvim**
```lua
-- ~/.config/nvim/lua/plugins/colorscheme.lua
return {
    {
        "catppuccin/nvim",
        name = "catppuccin",
        priority = 1000,
        opts = {
            flavour = "mocha",
            transparent_background = true,   -- works with terminal opacity
            integrations = {
                cmp = true,
                gitsigns = true,
                nvimtree = true,
                treesitter = true,
                telescope = true,
                which_key = true,
                indent_blankline = { enabled = true },
                mini = { enabled = true },
            },
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

**Status line: lualine.nvim**
```lua
{
    "nvim-lualine/lualine.nvim",
    opts = {
        options = {
            theme = "catppuccin",
            component_separators = { left = "", right = "" },
            section_separators = { left = "", right = "" },
        },
        sections = {
            lualine_a = { "mode" },
            lualine_b = { "branch", "diff", "diagnostics" },
            lualine_c = { { "filename", path = 1 } },
            lualine_x = { "encoding", "fileformat", "filetype" },
            lualine_y = { "progress" },
            lualine_z = { "location" },
        },
    },
}
```

**File icons: nvim-web-devicons**
```lua
{ "nvim-tree/nvim-web-devicons", lazy = true }
```
Requires a Nerd Font installed (Ch 37).

**Dashboard: alpha-nvim or dashboard-nvim**
```lua
-- Splash screen with ASCII art + shortcuts
{ "goolord/alpha-nvim", opts = { ... } }
```

**Indent guides: indent-blankline.nvim**
```lua
{ "lukas-reineke/indent-blankline.nvim", main = "ibl" }
```

**pywal/matugen integration:**
```bash
# Generate Neovim colorscheme from pywal colors
# wal template: ~/.config/wal/templates/colors-wal.vim
# Output: ~/.cache/wal/colors-wal.vim
```

### 57.2 VS Code Theming

**Installing a color theme:**
- Extensions marketplace: search "Catppuccin", "One Dark Pro", "Tokyo Night"
- `code --install-extension catppuccin.catppuccin-vsc`

**Popular VS Code themes:**
- **Catppuccin for VSCode**: `catppuccin.catppuccin-vsc`
- **Tokyo Night**: `enkia.tokyo-night`
- **One Dark Pro**: `zhuangtongfa.material-theme`
- **Gruvbox Theme**: `jdinhlife.gruvbox`
- **Rosé Pine**: `mvllow.rose-pine`
- **Ayu**: `teabyii.ayu`

**`settings.json` for a complete rice:**
```json
{
    "workbench.colorTheme": "Catppuccin Mocha",
    "workbench.iconTheme": "catppuccin-mocha",
    "editor.fontFamily": "'JetBrainsMono Nerd Font', monospace",
    "editor.fontLigatures": true,
    "editor.fontSize": 13,
    "editor.lineHeight": 1.6,
    "editor.cursorBlinking": "smooth",
    "editor.cursorSmoothCaretAnimation": "on",
    "window.titleBarStyle": "custom",
    "workbench.colorCustomizations": {
        "editor.background": "#1e1e2e",
        "sideBar.background": "#181825"
    }
}
```

**Transparent VS Code on Wayland:**
- `glassy-gnome` extension or custom CSS via `custom-css-and-js-loader`
- VS Code `--enable-transparent-titlebar` flag (partial support)

### 57.3 Helix — The Modern Modal Editor

Helix has built-in theming, no plugins needed for a great look:
```toml
# ~/.config/helix/config.toml
theme = "catppuccin_mocha"

[editor]
line-number = "relative"
cursorline = true
color-modes = true

[editor.statusline]
left = ["mode", "spinner", "file-name"]
right = ["diagnostics", "selections", "position", "file-encoding"]
```

Built-in Helix themes: `catppuccin_mocha/latte/frappe/macchiato`, `gruvbox`,
`tokyonight`, `rose_pine`, `nord`, `everforest`, `dracula`, and 50+ more.

Custom theme: `~/.config/helix/themes/mytheme.toml` (inherits from built-in).

### 57.4 Emacs Theming

**DOOM Emacs** (the most popular rice-friendly setup):
```elisp
;; ~/.doom.d/config.el
(setq doom-theme 'doom-catppuccin)
;; or: doom-gruvbox, doom-nord, doom-tokyo-night, doom-rose-pine

(setq doom-font (font-spec :family "JetBrainsMono Nerd Font" :size 12)
      doom-variable-pitch-font (font-spec :family "Inter" :size 12))
```

**catppuccin-theme for vanilla Emacs:**
```elisp
(use-package catppuccin-theme
    :config (load-theme 'catppuccin :no-confirm)
    (setq catppuccin-flavor 'mocha))
```

### 57.5 Transparent Editors
For terminal-based editors (Neovim, Helix): transparency comes from the terminal.
For GUI editors (VS Code, GUI Emacs):
- Compositor window rules:
  ```conf
  # Hyprland
  windowrulev2 = opacity 0.92 0.92,class:^(Code)$
  ```
- VS Code needs `--enable-features=UseOzonePlatform --ozone-platform=wayland`

### 57.6 Consistent Palette Across Tools
The goal: same background color in terminal, editor, and bar.
- Use the same hex values: `#1e1e2e` (Catppuccin Mocha base) everywhere
- Stylix (Ch 40) automates this for NixOS
- pywal templates (Ch 38) generate configs for all tools simultaneously
