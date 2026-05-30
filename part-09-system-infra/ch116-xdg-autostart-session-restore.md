# Chapter 116 — XDG Autostart and Session Restore

## Overview

Two related problems: how do you start applications automatically when your Wayland session begins, and how do you restore your window layout after a reboot? The first is solved by **XDG autostart** — a freedesktop.org spec for `.desktop` files in `~/.config/autostart/` that are launched by a compliant session manager. The second requires compositor-specific state saving, usually via IPC scripting. Both are commonly confused with `exec-once` in hyprland.conf or `exec` in sway config, which are simpler but less interoperable.

**Cross-references:** Ch 53 — session startup and exec-once patterns. Ch 54 — display managers and session selection. Ch 88 — Hyprland IPC scripting (used for workspace state saving).

---

## 116.1 XDG Autostart

### The Spec

The [XDG Autostart specification](https://specifications.freedesktop.org/autostart-spec/latest/) defines that any `.desktop` file placed in `$XDG_CONFIG_HOME/autostart/` (default: `~/.config/autostart/`) or `/etc/xdg/autostart/` should be executed by the session manager at login, subject to conditions in the `.desktop` file itself.

Key fields:
- `Type=Application` — required
- `Exec=` — the command to run
- `Hidden=false` — if `true`, the entry is ignored
- `OnlyShowIn=GNOME;KDE;` — run only on listed DEs (use `Sway;Hyprland;` for custom)
- `NotShowIn=GNOME;` — run everywhere except listed DEs
- `X-GNOME-Autostart-enabled=true` — GTK3 session manager toggle
- `X-KDE-autostart-condition=` — KDE condition variable
- `AutostartCondition=` — conditional autostart (GNOME, systemd)

### Writing an Autostart Entry

```ini
# ~/.config/autostart/nextcloud.desktop
[Desktop Entry]
Type=Application
Name=Nextcloud
Comment=Nextcloud sync client
Exec=nextcloud --background
Icon=nextcloud
Hidden=false
X-GNOME-Autostart-enabled=true
```

```ini
# ~/.config/autostart/keepassxc.desktop
[Desktop Entry]
Type=Application
Name=KeePassXC
Exec=keepassxc --keyfile /path/to/keyfile.keyx /path/to/database.kdbx
Hidden=false
X-GNOME-Autostart-enabled=true
```

Disabling a system-wide autostart entry without deleting it:
```bash
# Copy to user dir and set Hidden=true
cp /etc/xdg/autostart/geoclue-demo-agent.desktop ~/.config/autostart/
echo "Hidden=true" >> ~/.config/autostart/geoclue-demo-agent.desktop
```

### systemd-xdg-autostart-generator

On systemd-based systems, `systemd-xdg-autostart-generator` converts `~/.config/autostart/*.desktop` files into transient systemd user units, which are then started as part of `xdg-autostart.target`:

```bash
# Check if the generator is available
systemctl --user cat xdg-autostart.target 2>/dev/null

# List units it generated
systemctl --user list-units 'app-*.service' | grep autostart

# Start/stop individual entries
systemctl --user start app-nextcloud-autostart.service
systemctl --user stop  app-nextcloud-autostart.service
```

For compositors without a systemd user session (no `graphical-session.target`), the generator won't fire. Start autostart entries manually in compositor config:

```bash
# Sway config
exec dex --autostart --environment sway

# Hyprland
exec-once = dex --autostart --environment Hyprland
```

`dex` (Desktop Entry eXecutor) is a standalone tool that processes XDG autostart entries:
```bash
sudo pacman -S dex   # Arch
sudo apt install dex # Ubuntu
```

### Difference from exec-once

| Property | exec-once / exec | XDG autostart |
|---|---|---|
| Config location | compositor config | `~/.config/autostart/` |
| Interoperable | No (compositor-specific) | Yes (works on GNOME, KDE, etc.) |
| Conditions | None | `OnlyShowIn`, `Hidden`, systemd conditions |
| Managed by | Compositor | Session manager / systemd |
| Restart on crash | No | Optional via systemd |
| Use case | Compositor daemons (bar, wallpaper) | Cross-DE user apps (Nextcloud, KeePassXC) |

Use `exec-once` for compositor-specific daemons (hypridle, hyprpaper, Waybar). Use XDG autostart for user applications that should work regardless of compositor.

---

## 116.2 Session Restore

Session restore saves your window layout (which applications are open, on which workspaces, in which sizes and positions) and restores it after reboot. There is no Wayland-native session restore protocol — each compositor approach is different.

### Hyprland: Workspace Persistence via IPC

Hyprland does not have built-in session restore, but its JSON IPC makes it scriptable:

```bash
#!/bin/bash
# ~/.local/bin/hypr-save-session
# Save the current window layout as a restore script

OUTPUT="$HOME/.config/hypr/session-restore.sh"
echo "#!/bin/bash" > "$OUTPUT"

hyprctl -j clients | jq -r '
  .[] |
  "# \(.class) — \(.title)\n" +
  "hyprctl dispatch movetoworkspacesilent " + (.workspace.id | tostring) +
  ",address:" + .address + "\n"
' >> "$OUTPUT"

# Also save workspace states
hyprctl -j workspaces | jq -r '
  .[] | "# Workspace \(.id): \(.name)"
' >> "$OUTPUT"

chmod +x "$OUTPUT"
echo "Session saved to $OUTPUT"
```

```bash
#!/bin/bash
# ~/.local/bin/hypr-restore-session
# Launch applications in their saved workspaces

declare -A WORKSPACE_APPS=(
    [1]="firefox"
    [2]="kitty"
    [3]="code"
    [4]="discord"
    [5]="spotify"
)

for ws in "${!WORKSPACE_APPS[@]}"; do
    app="${WORKSPACE_APPS[$ws]}"
    hyprctl dispatch exec "[workspace $ws silent] $app"
    sleep 0.3   # give time for window to open before next launch
done
```

Trigger restore at login:
```ini
# ~/.config/hypr/hyprland.conf
exec-once = sleep 2 && ~/.local/bin/hypr-restore-session
```

### Hyprland: pyprland save-layout

[pyprland](https://github.com/hyprland-community/pyprland) (covered in Ch 96) has a `layout_center` plugin that can persist workspace layouts:

```toml
# ~/.config/hypr/pyprland.toml
[plugins.scratchpad]
# ... scratchpad config

[plugins.layout_center]
enabled = true
```

### Sway: sway-session / i3-resurrect

```bash
# Install i3-resurrect (works with Sway via IPC compatibility)
pip install i3-resurrect

# Save current session (all workspaces)
i3-resurrect save

# Restore on login
i3-resurrect restore

# Save only specific workspace
i3-resurrect save -w 1
i3-resurrect restore -w 1
```

Configuration at `~/.config/i3-resurrect/config.json`:

```json
{
    "workspace_directory": "~/.config/i3-resurrect/workspaces",
    "programs": [
        {
            "criteria": {"class": "^firefox$"},
            "command": "firefox --profile ~/.mozilla/firefox/myprofile"
        },
        {
            "criteria": {"class": "^kitty$"},
            "command": "kitty"
        }
    ]
}
```

### Minimal Approach: Window Rules as "Restore"

The most robust approach for most users is not saving state but defining persistent window rules that place applications on the correct workspace whenever they open:

```ini
# Hyprland — applications always open on their assigned workspace
windowrulev2 = workspace 1 silent, class:^(firefox)$
windowrulev2 = workspace 2 silent, class:^(kitty)$
windowrulev2 = workspace 3 silent, class:^(code-oss)$
windowrulev2 = workspace 4 silent, class:^(discord)$
windowrulev2 = workspace 5 silent, class:^(spotify)$

# Then autostart them all
exec-once = firefox
exec-once = kitty
exec-once = code
exec-once = discord
exec-once = spotify
```

This is not "restore" in the sense of saving arbitrary state, but it provides predictable workspace layout on every login without any IPC scripting.

### Niri: Native Session Restore

Niri has experimental session restore support (as of 2024) via its `--session` flag, which records and replays the window arrangement. Check niri's CHANGELOG for current status:

```bash
niri --session   # start with session restore enabled
```
