# Chapter 55 — Dotfile Management: stow, chezmoi, yadm, bare git

## Contents

- [Overview](#overview)
- [Sections](#sections)
  - [55.1 The Problem Dotfile Tools Solve](#551-the-problem-dotfile-tools-solve)
  - [55.2 GNU Stow — Symlink Farm Manager](#552-gnu-stow-symlink-farm-manager)
  - [55.3 chezmoi — The Feature-Rich Option](#553-chezmoi-the-feature-rich-option)
  - [55.4 yadm — Yet Another Dotfiles Manager](#554-yadm-yet-another-dotfiles-manager)
  - [55.5 Bare Git Repository](#555-bare-git-repository)
  - [55.6 Choosing Your Approach](#556-choosing-your-approach)
  - [55.7 Sharing Your Rice](#557-sharing-your-rice)
  - [55.8 What to Track vs. Ignore](#558-what-to-track-vs-ignore)

---


## Overview
A rice without dotfile management is a rice you'll lose. This chapter covers
the four dominant approaches to tracking, versioning, and sharing dotfiles.

## Sections

### 55.1 The Problem Dotfile Tools Solve
- Config files live in `~/.config/`, `~/`, `/etc/` — scattered
- Need: version control + deployment across machines + sharing
- Want: minimal friction when editing (no copying or symlinking by hand)
- Nice to have: secrets management, per-machine variants

### 55.2 GNU Stow — Symlink Farm Manager

**Concept:** Mirror your home directory structure in a stow directory, then `stow` creates symlinks.

```
~/dotfiles/
├── hyprland/
│   └── .config/
│       └── hypr/
│           ├── hyprland.conf
│           └── hyprlock.conf
├── kitty/
│   └── .config/
│       └── kitty/
│           └── kitty.conf
└── zsh/
    └── .zshrc
```

```bash
cd ~/dotfiles
stow hyprland   # creates ~/.config/hypr/ → ~/dotfiles/hyprland/.config/hypr/
stow kitty      # creates ~/.config/kitty/ → ...
stow zsh        # creates ~/.zshrc → ~/dotfiles/zsh/.zshrc
stow --adopt *  # adopt existing dotfiles into stow structure
```

**Workflow:**
```bash
# Add a new config
mkdir -p ~/dotfiles/waybar/.config/waybar
mv ~/.config/waybar ~/dotfiles/waybar/.config/
stow waybar

# Edit normally — changes go to ~/dotfiles/waybar/... via symlink
# Commit: cd ~/dotfiles && git add -A && git commit -m "add waybar config"
```

**Pros:** Simple, no extra tooling, symlinks are transparent
**Cons:** No templating, no secrets, manual structure mirroring

### 55.3 chezmoi — The Feature-Rich Option

**Concept:** chezmoi manages dotfiles with templates, encrypted secrets, scripts.

```bash
# Install
sh -c "$(curl -fsLS get.chezmoi.io)"

# Initialize
chezmoi init
chezmoi add ~/.config/hypr/hyprland.conf

# Edit
chezmoi edit ~/.config/hypr/hyprland.conf
chezmoi apply     # deploy changes

# On a new machine
chezmoi init https://github.com/you/dotfiles
chezmoi apply
```

**chezmoi directory:** `~/.local/share/chezmoi/`

**Templates** (Go template syntax):
```
# dot_config/hypr/hyprland.conf.tmpl
monitor = {{ .monitor }},1920x1080@60,0x0,1

{{ if eq .chezmoi.hostname "work-laptop" }}
exec-once = /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1
{{ end }}
```

**Data file:** `~/.config/chezmoi/chezmoi.toml`
```toml
[data]
    monitor = "DP-1"
    name = "yourname"
```

**Encrypted secrets** (age or GPG):
```bash
chezmoi add --encrypt ~/.config/some-app/credentials
```

**Run scripts** (run on `chezmoi apply`):
```bash
# ~/.local/share/chezmoi/run_once_install-packages.sh.tmpl
#!/bin/bash
{{ if eq .chezmoi.os "linux" }}
pacman -S --noconfirm stow git neovim
{{ end }}
```

**Pros:** Templating, secrets, scripts, cross-platform, per-host variants
**Cons:** More complex, less transparent than stow

### 55.4 yadm — Yet Another Dotfiles Manager

**Concept:** Git wrapper that treats `$HOME` as a git repo, with multi-system support.

```bash
yadm init
yadm add ~/.config/hypr/hyprland.conf
yadm add ~/.zshrc
yadm commit -m "initial rice"
yadm remote add origin https://github.com/you/dotfiles
yadm push

# On new machine
yadm clone https://github.com/you/dotfiles
```

**Alternates** (per-host/OS files):
```
# Use different config on different hosts
~/.config/hypr/hyprland.conf##hostname.worklaptop
~/.config/hypr/hyprland.conf##hostname.desktop
~/.config/hypr/hyprland.conf          # fallback
```

```bash
yadm alt  # creates symlinks to the right alternate
```

**Pros:** Just git, low complexity, alternate system for machine variants
**Cons:** Less powerful templating than chezmoi, can pollute `git status` in home

### 55.5 Bare Git Repository

The "no extra tools" approach popularized by Atlassian/HackerNews:

```bash
# Initialize
git init --bare $HOME/.dotfiles
alias dot='git --git-dir=$HOME/.dotfiles/ --work-tree=$HOME'
dot config status.showUntrackedFiles no

# Add files
dot add .config/hypr/hyprland.conf
dot commit -m "add hyprland config"
dot remote add origin https://github.com/you/dotfiles
dot push

# On new machine
git clone --bare https://github.com/you/dotfiles $HOME/.dotfiles
alias dot='git --git-dir=$HOME/.dotfiles/ --work-tree=$HOME'
dot checkout  # deploy
```

**Pros:** Zero dependencies (just git), well-understood
**Cons:** No templates, no secrets, alias required, accidental `git status` in home dir

### 55.6 Choosing Your Approach

| Need | Best tool |
|------|-----------|
| Simplest possible | Bare git |
| Multiple machines, no config differences | GNU Stow + git |
| Per-machine config variants | chezmoi or yadm |
| Secrets in dotfiles | chezmoi (age encryption) |
| NixOS | Home Manager (replaces all of these) |
| "Just works" with scripts | chezmoi |

### 55.7 Sharing Your Rice
- Public GitHub/GitLab repo with good README + screenshots
- Include: package list, dependencies, screenshots, reading paths
- r/unixporn format: screenshot + spec table + config link
- `screenshot.png` in repo root: makes GitHub preview work
- Tag with: `dotfiles`, `rice`, `hyprland`/`sway`, your palette name

### 55.8 What to Track vs. Ignore
**Track:** compositor config, bar config, terminal config, shell config, Neovim config
**Don't track:** `~/.local/share/` (runtime state), cache, credentials, `~/.mozilla/`
**`.gitignore` template:**
```
# ~/.gitignore (for bare repo approach)
*
!.gitignore
!.config/hypr/**
!.config/kitty/**
!.config/quickshell/**
!.config/waybar/**
!.zshrc
!.config/starship.toml
```


---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).