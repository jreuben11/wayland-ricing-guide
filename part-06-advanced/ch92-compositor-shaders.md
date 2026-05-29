# Chapter 92 — Custom GLSL Shaders in Compositors

## Overview

Wayland compositors with OpenGL renderers apply shaders when compositing
windows and the desktop. Hyprland exposes a screen-shader hook; Wayfire ships
several shader-based plugins. This lets you apply full-screen post-processing:
color grading, CRT effects, blue-light filtering, vignette, and more — entirely
at the compositor level, affecting every pixel on screen.

---

## 92.1 Hyprland Screen Shaders

Hyprland applies a fragment shader after all windows are composited. The shader
receives the final frame as a texture and outputs the modified pixel color.

### Enabling a screen shader

```conf
# hyprland.conf
decoration {
    screen_shader = ~/.config/hypr/shaders/crt.frag
}
```

Reload to apply: `hyprctl reload`

Toggle at runtime:
```bash
# Enable shader
hyprctl keyword decoration:screen_shader ~/.config/hypr/shaders/crt.frag

# Disable shader
hyprctl keyword decoration:screen_shader ""
```

---

## 92.2 Shader Interface

Hyprland's screen shader receives these uniforms:

```glsl
// Available uniforms in Hyprland screen shaders
uniform sampler2D texture0;     // the composited frame
uniform float time;             // seconds since compositor start (float)
uniform int output_id;          // which monitor (multi-monitor setups)

// Interpolated from vertex shader:
varying vec2 v_texcoord;        // UV coordinates (0.0–1.0)
```

The output is `gl_FragColor` (RGBA).

Minimal passthrough shader:
```glsl
precision mediump float;
varying vec2 v_texcoord;
uniform sampler2D texture0;

void main() {
    gl_FragColor = texture2D(texture0, v_texcoord);
}
```

---

## 92.3 Practical Shaders

### Blue light / warm filter

```glsl
precision mediump float;
varying vec2 v_texcoord;
uniform sampler2D texture0;

void main() {
    vec4 color = texture2D(texture0, v_texcoord);
    // Reduce blue, boost red/green for warm tone
    color.r = min(color.r * 1.05, 1.0);
    color.g = min(color.g * 1.00, 1.0);
    color.b = color.b * 0.80;
    gl_FragColor = color;
}
```

### Invert colors

```glsl
precision mediump float;
varying vec2 v_texcoord;
uniform sampler2D texture0;

void main() {
    vec4 color = texture2D(texture0, v_texcoord);
    gl_FragColor = vec4(1.0 - color.rgb, color.a);
}
```

### Grayscale

```glsl
precision mediump float;
varying vec2 v_texcoord;
uniform sampler2D texture0;

void main() {
    vec4 color = texture2D(texture0, v_texcoord);
    float gray = dot(color.rgb, vec3(0.299, 0.587, 0.114));
    gl_FragColor = vec4(gray, gray, gray, color.a);
}
```

### Vignette

```glsl
precision mediump float;
varying vec2 v_texcoord;
uniform sampler2D texture0;

void main() {
    vec4 color = texture2D(texture0, v_texcoord);
    vec2 uv = v_texcoord - vec2(0.5);
    float vignette = 1.0 - dot(uv, uv) * 2.0;
    vignette = clamp(vignette, 0.0, 1.0);
    gl_FragColor = vec4(color.rgb * vignette, color.a);
}
```

### CRT scanlines

```glsl
precision mediump float;
varying vec2 v_texcoord;
uniform sampler2D texture0;
uniform float time;

void main() {
    vec4 color = texture2D(texture0, v_texcoord);

    // Scanlines — every other pixel row
    float scanline = sin(v_texcoord.y * 1080.0 * 3.14159) * 0.5 + 0.5;
    scanline = mix(0.75, 1.0, scanline);

    // Subtle chromatic aberration
    float offset = 0.001;
    vec4 r = texture2D(texture0, v_texcoord + vec2(offset, 0.0));
    vec4 b = texture2D(texture0, v_texcoord - vec2(offset, 0.0));
    color = vec4(r.r, color.g, b.b, color.a);

    // Phosphor glow (slight bloom by brightening)
    color.rgb = pow(color.rgb, vec3(0.9));

    gl_FragColor = vec4(color.rgb * scanline, color.a);
}
```

### Color grading (Catppuccin warm tint)

```glsl
precision mediump float;
varying vec2 v_texcoord;
uniform sampler2D texture0;

// Subtle warm tint toward Catppuccin Mocha palette
vec3 colorGrade(vec3 color) {
    // Lift shadows toward dark purple
    vec3 shadows = vec3(0.118, 0.118, 0.180);
    // Tint highlights toward warm cream
    vec3 highlights = vec3(0.847, 0.820, 0.973);

    float lum = dot(color, vec3(0.299, 0.587, 0.114));
    return mix(mix(color, shadows, (1.0 - lum) * 0.15),
               highlights, lum * 0.05);
}

void main() {
    vec4 color = texture2D(texture0, v_texcoord);
    gl_FragColor = vec4(colorGrade(color.rgb), color.a);
}
```

### Contrast and saturation boost

```glsl
precision mediump float;
varying vec2 v_texcoord;
uniform sampler2D texture0;

vec3 adjustSaturation(vec3 color, float sat) {
    float gray = dot(color, vec3(0.299, 0.587, 0.114));
    return mix(vec3(gray), color, sat);
}

vec3 adjustContrast(vec3 color, float c) {
    return (color - 0.5) * c + 0.5;
}

void main() {
    vec4 color = texture2D(texture0, v_texcoord);
    vec3 c = color.rgb;
    c = adjustSaturation(c, 1.15);   // +15% saturation
    c = adjustContrast(c, 1.05);      // +5% contrast
    c = clamp(c, 0.0, 1.0);
    gl_FragColor = vec4(c, color.a);
}
```

---

## 92.4 Toggling Shaders via Script

```bash
# ~/.config/hypr/scripts/toggle-shader.sh
SHADER_PATH="$HOME/.config/hypr/shaders"
CURRENT=$(hyprctl getoption decoration:screen_shader | grep "str:" | cut -d' ' -f2)

if [ -z "$CURRENT" ] || [ "$CURRENT" = "[[EMPTY]]" ]; then
    hyprctl keyword decoration:screen_shader "$SHADER_PATH/warm.frag"
    notify-send "Shader" "Warm filter ON"
else
    hyprctl keyword decoration:screen_shader ""
    notify-send "Shader" "Shader OFF"
fi
```

Bind to a key:
```conf
bind = SUPER SHIFT, S, exec, ~/.config/hypr/scripts/toggle-shader.sh
```

Cycle through multiple shaders:
```bash
#!/bin/bash
SHADERS=("" "warm.frag" "crt.frag" "vignette.frag")
SHADER_DIR="$HOME/.config/hypr/shaders"
STATE_FILE="/tmp/hypr-shader-idx"

idx=$(cat "$STATE_FILE" 2>/dev/null || echo 0)
idx=$(( (idx + 1) % ${#SHADERS[@]} ))
echo $idx > "$STATE_FILE"

shader="${SHADERS[$idx]}"
if [ -z "$shader" ]; then
    hyprctl keyword decoration:screen_shader ""
    notify-send "Shader" "None"
else
    hyprctl keyword decoration:screen_shader "$SHADER_DIR/$shader"
    notify-send "Shader" "$shader"
fi
```

---

## 92.5 Wayfire Shader Plugin

Wayfire exposes shaders through its rendering pipeline. The `wf-shader` plugin
(community) or the built-in `blur` and `animate` plugins use GLSL.

Writing a custom Wayfire rendering plugin requires the `wf::scene::node_t`
API and a `render_method_registry_t`. This is more involved than Hyprland's
single-file shader — see the Wayfire plugin API in ch09.

The simpler approach on Wayfire: use the color management plugin:
```ini
# wayfire.ini
[colormanagement]
saturation = 1.1
brightness = 1.0
contrast = 1.05
```

---

## 92.6 Performance Notes

Screen shaders run on every frame for every pixel. Rules of thumb:

- **Texture lookups**: each `texture2D()` call in a fragment shader has a cost;
  the passthrough shader (one lookup) costs ~0.1ms on a mid-range GPU
- **Branching**: avoid `if` statements in shaders; use `mix()` and `clamp()`
  instead — branching in GLSL causes both paths to execute on all pixels
- **Time-varying shaders** (CRT scanlines with scrolling): disable VFR
  (`misc.vfr = false`) if the animation is uneven — VFR skips frames at idle
  which makes time-dependent animations stutter
- **Power cost**: any non-trivial shader prevents the GPU from entering low-power
  idle; disable shaders when on battery unless necessary

Check render overhead:
```bash
# Compare frame delivery with/without shader
hyprctl keyword decoration:screen_shader ""
# Monitor GPU utilization: nvtop / radeontop / intel_gpu_top
```

---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
