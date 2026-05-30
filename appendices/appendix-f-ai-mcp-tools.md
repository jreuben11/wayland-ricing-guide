# Appendix F — AI, Claude, and MCP Tools for Wayland Ricing

## Contents

- [Overview](#overview)
- [F.1 Claude Code + MCP Servers](#f1-claude-code-mcp-servers)
  - [context7 — Live Library Documentation](#context7-live-library-documentation)
  - [arxiv MCP — Research Papers](#arxiv-mcp-research-papers)
  - [GitHub MCP — Dotfile and Config Search](#github-mcp-dotfile-and-config-search)
- [F.2 Claude Code for Ricing Tasks](#f2-claude-code-for-ricing-tasks)
  - [QML Generation](#qml-generation)
  - [Hyprland Config Debugging](#hyprland-config-debugging)
  - [Config Translation](#config-translation)
  - [Theme Generation](#theme-generation)
  - [Script Generation](#script-generation)
- [F.3 AI Wallpaper Generation](#f3-ai-wallpaper-generation)
  - [Local (Ollama + Stable Diffusion)](#local-ollama-stable-diffusion)
  - [ComfyUI (recommended for scripting)](#comfyui-recommended-for-scripting)
  - [Integration with pywal / matugen](#integration-with-pywal-matugen)
- [F.4 AI-Assisted Color Palette Tools](#f4-ai-assisted-color-palette-tools)
  - [pastel + Claude](#pastel-claude)
  - [matugen templates](#matugen-templates)
- [F.5 AI Tools for Protocol and Code Work](#f5-ai-tools-for-protocol-and-code-work)
  - [Writing Wayland Protocol Extensions](#writing-wayland-protocol-extensions)
  - [Debugging with WAYLAND_DEBUG](#debugging-with-waylanddebug)
  - [Rust Wayland Client Code](#rust-wayland-client-code)
- [F.6 Quickshell-Specific AI Workflow](#f6-quickshell-specific-ai-workflow)
  - [Prompt template for Quickshell component generation](#prompt-template-for-quickshell-component-generation)
- [F.7 Relevant Community AI Resources](#f7-relevant-community-ai-resources)

---


## Overview

Large language models and AI-powered tooling have become genuinely useful for Wayland ricing workflows, covering tasks that previously required deep manual research: generating QML components, querying up-to-date library documentation through MCP servers, searching dotfile repositories for specific patterns, explaining protocol internals from wire traces, and producing color palettes from wallpaper images. This appendix surveys the tools and workflows worth knowing, organized into six areas: Claude Code with MCP servers (context7 for live docs, arxiv for research, GitHub for dotfile search), Claude Code prompt recipes for common ricing tasks, AI image generation for wallpapers (Stable Diffusion/ComfyUI, with pywal/matugen integration), AI-assisted color palette tools, AI support for protocol and Rust code work, and Quickshell-specific AI workflow patterns. The final section lists community AI resources including wallpaper-generation communities and AI-assisted theming projects.

## Installation

**Claude Code CLI:** https://claude.ai/code · https://github.com/anthropics/claude-code

```bash
# Install Claude Code (requires Node.js 18+)
npm install -g @anthropic-ai/claude-code

# Arch Linux — Node.js
sudo pacman -S nodejs npm

# Nix
nix-env -iA nixpkgs.nodejs
npm install -g @anthropic-ai/claude-code
# Or: nix-env -iA nixpkgs.claude-code  (if packaged in nixpkgs)

# ComfyUI (AI image generation, covered in §F.3)
# git clone https://github.com/comfyanonymous/ComfyUI
# pip install -r requirements.txt

# Ollama (local LLM runtime)
# Arch: paru -S ollama  |  Nix: nix-env -iA nixpkgs.ollama
```

---

## F.1 Claude Code + MCP Servers

Claude Code (the CLI) supports Model Context Protocol (MCP) servers that expose
domain-specific tooling directly into the AI context. Several are directly
useful for Wayland ricing work.

### context7 — Live Library Documentation

Fetches current documentation for any library or framework, bypassing training
data cutoffs. Indispensable for:
- Quickshell API (changes frequently — training data is often stale)
- Latest Hyprland config options and new dispatchers
- wlroots API changes between versions
- Qt6 QML type documentation

Usage in Claude Code: mention a library by name and Claude will automatically
query context7 for current docs before answering.

```
# In Claude Code conversation:
"How do I use PwNodeAudio in Quickshell?"
→ Claude queries context7 for quickshell docs, returns current API
```

### arxiv MCP — Research Papers

Directly relevant if you are implementing compositor features, working on color
management, or researching display technology:
- HDR tone-mapping algorithms
- Color science (CIECAM02, ICtCp, etc.)
- Perceptual display calibration
- Wayland security research

### GitHub MCP — Dotfile and Config Search

Browse any public GitHub repository from within Claude Code:
- Inspect a specific real-world Hyprland config before copying patterns
- Read the actual Quickshell source for a type you're implementing
- Check the Waybar wiki for custom module examples
- Examine end_4/dots-hyprland for specific component patterns

```
# In Claude Code:
"Read the HyprlandWorkspace implementation in quickshell source"
→ Claude fetches the actual file from GitHub
```

---

## F.2 Claude Code for Ricing Tasks

Claude Code (with `claude` CLI or the VS Code extension) is well-suited for
these specific ricing workflows:

### QML Generation

Quickshell components follow predictable patterns. Describe the widget you want:

```
"Write a Quickshell PanelWindow that shows the current MPRIS track title
 and artist, updates reactively, and fades out when nothing is playing.
 Use the MprisController service."
```

Claude will generate the QML, import paths, and reactive bindings correctly
when given access to current Quickshell docs via context7.

### Hyprland Config Debugging

```
"My Hyprland windowrulev2 is not matching Firefox PiP windows.
 The rule is: windowrulev2 = float, title:^(Picture-in-Picture)$
 What's wrong?"
```

### Config Translation

```
"Convert this i3 config block to sway format:
 [paste i3 config]"

"Translate this Waybar JSON module to a Quickshell equivalent using
 the Process type."
```

### Theme Generation

```
"Generate a Catppuccin Mocha color palette as:
 1. CSS variables for Waybar
 2. Hyprland col.active_border gradient
 3. Alacritty TOML colors block"
```

### Script Generation

```
"Write a bash script that:
 1. Takes a screenshot with grim
 2. Pipes it to hyprpicker in --stdin mode to get the dominant color
 3. Updates the Hyprland active border color via hyprctl keyword"
```

---

## F.3 AI Wallpaper Generation

AI image generation tools for producing unique ricing wallpapers.

### Local (Ollama + Stable Diffusion)

```bash
# Ollama for text generation / color palette from description
paru -S ollama
ollama pull llama3.2

# AUTOMATIC1111 / Forge for image generation
paru -S stable-diffusion-webui-git
# Prompts for ricing wallpapers:
# "abstract geometric gradient, catppuccin mocha palette, 4k, minimalist"
# "dark forest fog, moonlight, purple tones, desktop wallpaper"
# "synthwave city skyline, neon pink and blue, 2560x1440"
```

### ComfyUI (recommended for scripting)

ComfyUI has a JSON API, making it scriptable from shell or Python:

```python
# Generate wallpaper and set it via swww
import requests, json, base64

workflow = {
    "prompt": "dark minimal abstract wallpaper, purple hues, 4k",
    "width": 2560, "height": 1440
}
result = requests.post("http://127.0.0.1:8188/prompt", json={"prompt": workflow})
# ... save image, then:
# subprocess.run(["swww", "img", output_path])
```

### Integration with pywal / matugen

Generate an AI wallpaper, then auto-extract a palette:

```bash
# Generate wallpaper (via API or local tool)
ai-wallpaper generate --output ~/wallpapers/generated.png

# Extract palette and apply everywhere
wal -i ~/wallpapers/generated.png
# or Material You:
matugen image ~/wallpapers/generated.png
```

---

## F.4 AI-Assisted Color Palette Tools

### pastel + Claude

The `pastel` CLI (Rust) manipulates colors. Combine with Claude for palette
generation:

```bash
# Generate a harmonious 8-color palette from a seed color
pastel color "#89b4fa" | pastel analogous | pastel format hex

# Ask Claude: "Generate a Catppuccin-inspired palette with this base blue"
# Then use pastel to derive the full set:
pastel gradient "#1e1e2e" "#cba6f7" --number 8 | pastel format hex
```

### matugen templates

matugen (Material You) generates color schemes from wallpapers and supports
custom templates. Ask Claude to write a new matugen template:

```
"Write a matugen template that outputs Hyprland border colors,
 Waybar CSS variables, and Alacritty TOML colors from a Material You palette"
```

---

## F.5 AI Tools for Protocol and Code Work

### Writing Wayland Protocol Extensions

When writing a new `.xml` protocol (Ch 46), Claude with context7 can:
- Generate the XML boilerplate from a description
- Explain existing protocol patterns from wayland-protocols source
- Draft the C implementation stubs from the XML

```
"Write a Wayland protocol extension XML for a 'compositor-hints' protocol
 that lets clients request a preferred accent color from the compositor.
 Follow the wayland-protocols XML conventions."
```

### Debugging with WAYLAND_DEBUG

Paste `WAYLAND_DEBUG=1` output into Claude and ask:

```
"Here is WAYLAND_DEBUG output from my app failing to create a layer shell
 surface. Identify the request/event sequence and what's going wrong."
```

Claude can read wire protocol traces and identify protocol violations,
missing globals, or wrong object lifecycle management.

### Rust Wayland Client Code

```
"Using the wayland-client crate with Dispatch trait pattern (Ch 73),
 write a minimal client that subscribes to wl_output events and prints
 the current monitor refresh rate."
```

---

## F.6 Quickshell-Specific AI Workflow

Given Quickshell's relatively small documentation surface area and fast-moving
API, the recommended workflow is:

1. **Fetch current docs via context7** before asking any API question
2. **Reference the official examples** at `outfoxxed/quickshell-examples` on GitHub
   (accessible via GitHub MCP)
3. **Use qmllint** to validate generated code before running it
4. **Ask about the module namespace explicitly**: e.g., "using
   `Quickshell.Services.Notifications`" rather than just "notifications"

### Prompt template for Quickshell component generation

```
Context: I'm writing a Quickshell (https://quickshell.org) shell component
using QML/QtQuick. The version is 0.2.x. I want [describe component].

Requirements:
- Use [specific Quickshell module] 
- The component should [behavior]
- Style: [colors, fonts, sizes]

Please generate a complete, self-contained .qml file with all necessary
imports. Use pragma Singleton if appropriate.
```

---

## F.7 Relevant Community AI Resources

| Resource | What it's for |
|----------|--------------|
| r/unixporn AI threads | AI-generated wallpapers posted with configs |
| quickshell Discord #ai-assistance | Community prompt sharing for Quickshell |
| HyDE AI theming | HyDE (Ch 62) uses AI for theme generation |
| wallhaven.cc API | Programmatic wallpaper fetching; combine with wal |
| unsplash.com API | High-res photos for AI palette extraction |

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
