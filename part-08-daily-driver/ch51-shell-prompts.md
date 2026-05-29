# Chapter 51 — Shell Configuration and Prompts: Fish, Zsh, Starship, oh-my-posh

## Overview
The shell prompt is the second most-visible terminal element after the color
scheme. This chapter covers shell choice, framework configuration, and the
two dominant cross-shell prompt tools.

## Sections

### 51.1 Shell Choice for Ricing

| Shell | Scripting compat | Interactivity | Config complexity | Notes |
|-------|-----------------|---------------|-------------------|-------|
| Bash | Best (POSIX) | Basic | Low | Universal, already installed |
| Zsh | Good | Excellent | Medium-High | Most riced shell |
| Fish | Poor (non-POSIX) | Best | Low | Best out-of-box UX |
| Nushell | Poor | Good | Low | Structured data pipelines |

**For ricing**: Fish for daily use + Bash for scripts, or Zsh with a framework.

### 51.2 Zsh Setup

**Oh My Zsh** — the classic framework:
```bash
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
```
- Themes: `ZSH_THEME="agnoster"` (legacy) — better to use Starship instead
- Plugins: `plugins=(git zsh-autosuggestions zsh-syntax-highlighting z)`

**Zinit** — faster, more flexible:
```zsh
# ~/.zshrc
zinit light zsh-users/zsh-autosuggestions
zinit light zsh-users/zsh-syntax-highlighting
zinit light zsh-users/zsh-completions
```

**Essential Zsh options:**
```zsh
setopt AUTO_CD            # cd by typing directory name
setopt HIST_IGNORE_DUPS   # no duplicate history
setopt SHARE_HISTORY      # share history across sessions
setopt GLOB_COMPLETE      # complete globs
bindkey -e                # emacs key bindings (or -v for vi)
```

### 51.3 Fish Setup

**Fish** requires no framework for a great experience:
```fish
# ~/.config/fish/config.fish
set -gx EDITOR nvim
set -gx PATH $PATH ~/.local/bin

# Abbreviations (expand on space — better than aliases for interactive use)
abbr -a g git
abbr -a v nvim
abbr -a ll 'ls -lah'
```

**Fish plugins via Fisher:**
```fish
fisher install jorgebucaran/fisher
fisher install PatrickF1/fzf.fish        # fzf integration
fisher install jethrokuan/z              # directory jumping
fisher install meaningful-oasis/sponge  # clean history
```

**Fish functions:**
```fish
# ~/.config/fish/functions/mkcd.fish
function mkcd
    mkdir -p $argv && cd $argv
end
```

### 51.4 Starship — The Cross-Shell Prompt

Starship is a Rust-powered prompt that works in any shell and produces beautiful,
informative, fast prompts.

**Installation:**
```bash
curl -sS https://starship.rs/install.sh | sh
# Arch: pacman -S starship
```

**Shell integration:**
```bash
# Bash: ~/.bashrc
eval "$(starship init bash)"
# Zsh: ~/.zshrc
eval "$(starship init zsh)"
# Fish: ~/.config/fish/config.fish
starship init fish | source
```

**Config:** `~/.config/starship.toml`
```toml
format = """
[░▒▓](fg:#a3aed2)\
[ $os ](bg:#a3aed2 fg:#090c0c)\
[](fg:#a3aed2 bg:#769ff0)\
[ $directory ](bg:#769ff0 fg:#090c0c)\
[](fg:#769ff0 bg:#394260)\
[ $git_branch $git_status ](bg:#394260)\
[](fg:#394260 bg:#212736)\
[ $time ](bg:#212736)\
[](fg:#212736)\
$character"""

[directory]
style = "bg:#769ff0 fg:#090c0c"
format = "[ $path ]($style)"
truncation_length = 3

[git_branch]
symbol = ""
style = "bg:#394260"
format = '[[ $symbol $branch ](bg:#394260)]($style)'

[git_status]
style = "bg:#394260"
format = '[[($all_status$ahead_behind )](bg:#394260)]($style)'

[time]
disabled = false
format = '[ ♥ $time ]($style)'
style = "bg:#212736"
```

**Popular preset styles:**
```bash
starship preset catppuccin-powerline -o ~/.config/starship.toml
starship preset gruvbox-rainbow -o ~/.config/starship.toml
starship preset nerd-font-symbols -o ~/.config/starship.toml
```

**Module highlights:**
- `directory`: path with truncation, read-only icon
- `git_branch` + `git_status`: dirty/ahead/behind indicators
- `nodejs`, `python`, `rust`, `go`: language version in context
- `cmd_duration`: show slow command durations
- `battery`: laptop battery level
- `time`: right-aligned clock

### 51.5 oh-my-posh — Windows-Origin Cross-Shell Prompt

**Why oh-my-posh:** Richer segment types, JSON/YAML/TOML config, huge theme library

**Installation:**
```bash
curl -s https://ohmyposh.dev/install.sh | bash -s
```

**Shell integration:**
```bash
eval "$(oh-my-posh init bash --config ~/.config/ohmyposh/theme.toml)"
```

**Config:** TOML/JSON/YAML, with named "blocks" and "segments"
```toml
"$schema" = "https://raw.githubusercontent.com/JanDeDobbeleer/oh-my-posh/main/themes/schema.json"
version = 2

[[blocks]]
type = "prompt"
alignment = "left"

  [[blocks.segments]]
  type = "path"
  style = "powerline"
  foreground = "#ffffff"
  background = "#61AFEF"
  template = " {{ .Path }} "

  [[blocks.segments]]
  type = "git"
  style = "powerline"
  foreground = "#193549"
  background = "#FFEB3B"
  template = " {{ .HEAD }} "
```

**Browsing themes:** `oh-my-posh font install` + `oh-my-posh theme list`

### 51.6 Prompt Design Principles
- **Width**: don't use more than 50% of terminal width for left prompt
- **Information density**: git status + path + language version is enough
- **Color coherence**: match prompt colors to your base16/Catppuccin palette
- **Right prompt**: use for non-critical info (time, battery) — disappears when typing long commands
- **Transient prompt**: print minimal prompt for previous commands, full prompt only for current (Starship/OMPosh feature)

### 51.7 Directory Jumping: zoxide
```bash
# Install
pacman -S zoxide  # or cargo install zoxide

# Shell integration (replaces cd)
eval "$(zoxide init zsh)"  # or bash, fish

# Usage
z docs     # jump to most frecent dir matching "docs"
zi         # interactive selection with fzf
```

### 51.8 fzf — Fuzzy Finder Integration
```bash
# Key bindings installed automatically
CTRL-R  # fuzzy history search
CTRL-T  # fuzzy file find + insert path
ALT-C   # fuzzy cd

# ~/.config/fzf/fzf.conf
export FZF_DEFAULT_OPTS="
    --color=bg+:#313244,bg:#1e1e2e,spinner:#f5e0dc,hl:#f38ba8
    --color=fg:#cdd6f4,header:#f38ba8,info:#cba6f7,pointer:#f5e0dc
    --color=marker:#f5e0dc,fg+:#cdd6f4,prompt:#cba6f7,hl+:#f38ba8"
```

### 51.9 Shell Tools That Complete the Rice
- **bat**: `cat` with syntax highlighting — `alias cat=bat`
- **eza**: modern `ls` with icons — `alias ls='eza --icons'`
- **fd**: fast `find` replacement
- **ripgrep**: fast `grep` replacement — `alias grep=rg`
- **delta**: beautiful git diffs — set in `~/.gitconfig`
- **bottom/btm**: `htop` replacement with graphs
- **yazi**: TUI file manager with image previews (Ch 50 Kitty protocol integration)
