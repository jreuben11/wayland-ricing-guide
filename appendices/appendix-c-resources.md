# Appendix C — Resource Index

## Official Documentation
| Resource | URL |
|----------|-----|
| Wayland Book | https://wayland-book.com |
| Wayland Protocol Explorer | https://wayland.app/protocols/ |
| wlroots docs | https://gitlab.freedesktop.org/wlroots/wlroots |
| Quickshell docs | https://quickshell.org/docs/ |
| Hyprland wiki | https://wiki.hyprland.org |
| Sway wiki | https://github.com/swaywm/sway/wiki |
| Niri wiki | https://github.com/YaLTeR/niri/wiki |
| Stylix docs | https://stylix.danth.me |
| Home Manager manual | https://nix-community.github.io/home-manager/ |

## Key Repositories
| Project | Repository |
|---------|-----------|
| wayland-protocols | https://gitlab.freedesktop.org/wayland/wayland-protocols |
| wlroots | https://gitlab.freedesktop.org/wlroots/wlroots |
| wlr-protocols | https://gitlab.freedesktop.org/wlroots/wlr-protocols |
| Quickshell | https://git.outfoxxed.me/quickshell/quickshell |
| Hyprland | https://github.com/hyprwm/Hyprland |
| Sway | https://github.com/swaywm/sway |
| Niri | https://github.com/YaLTeR/niri |
| River | https://codeberg.org/river/river |
| labwc | https://github.com/labwc/labwc |
| Wayfire | https://github.com/WayfireWM/wayfire |
| Smithay | https://github.com/Smithay/smithay |
| awesome-wayland | https://github.com/rcalixte/awesome-wayland |

## Tooling Reference
| Tool | Purpose | Repository |
|------|---------|-----------|
| swww | Wallpaper + transitions | https://github.com/LGFae/swww |
| hyprpaper | Hyprland wallpaper | https://github.com/hyprwm/hyprpaper |
| hyprlock | Hyprland lockscreen | https://github.com/hyprwm/hyprlock |
| hypridle | Idle daemon | https://github.com/hyprwm/hypridle |
| Waybar | Status bar | https://github.com/Alexays/Waybar |
| eww | Widgets | https://github.com/elkowar/eww |
| Astal/AGS | TS widgets | https://github.com/aylur/astal |
| mako | Notifications | https://github.com/emersion/mako |
| dunst | Notifications | https://github.com/dunst-project/dunst |
| swaync | Notif center | https://github.com/ErikReider/SwayNotificationCenter |
| fuzzel | Launcher | https://codeberg.org/dnkl/fuzzel |
| rofi (Wayland) | Launcher | https://github.com/lbonn/rofi |
| grim | Screenshots | https://sr.ht/~emersion/grim/ |
| slurp | Region selection | https://github.com/emersion/slurp |
| wf-recorder | Recording | https://github.com/ammen99/wf-recorder |
| wl-clipboard | Clipboard | https://github.com/bugaevc/wl-clipboard |
| cliphist | Clipboard history | https://github.com/sentriz/cliphist |
| kanshi | Monitor profiles | https://sr.ht/~emersion/kanshi/ |
| kanata | Key remapper | https://github.com/jtroo/kanata |
| pywal | Color extraction | https://github.com/dylanaraps/pywal |
| matugen | Material You colors | https://github.com/InioX/matugen |
| Stylix | NixOS auto-theme | https://github.com/nix-community/stylix |
| Catppuccin | Color palette | https://github.com/catppuccin/catppuccin |

## Learning Resources
| Resource | Type | Focus |
|----------|------|-------|
| https://wayland-book.com | Book | Wayland client programming |
| https://way-cooler.org/book/ | Book | wlroots compositor in Rust |
| https://wiki.archlinux.org/title/Wayland | Wiki | Practical Wayland setup |
| https://smithay.github.io/smithay/ | Book | Smithay compositor |
| https://deepwiki.com/quickshell-mirror/quickshell | Wiki | Quickshell internals |
| https://reddit.com/r/unixporn | Community | Rice showcase |
| https://reddit.com/r/hyprland | Community | Hyprland help |
| https://discourse.nixos.org | Forum | NixOS/HM help |

## Useful Commands Cheat Sheet
```bash
# Wayland environment check
echo $WAYLAND_DISPLAY
echo $XDG_SESSION_TYPE

# Protocol debug
WAYLAND_DEBUG=1 app 2>&1 | grep interface_name

# Compositor inspection
weston-info
hyprctl monitors -j
swaymsg -t get_outputs

# Screenshot pipeline
grim -g "$(slurp)" - | wl-copy

# Color extraction
matugen image ~/wallpaper.jpg --mode dark
wal -i ~/wallpaper.jpg

# Clipboard
wl-paste | wl-copy   # round-trip test
cliphist list | fuzzel --dmenu | cliphist decode | wl-copy
```
