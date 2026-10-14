# hyprframes — how the PNG is drawn

The plugin treats the PNG as a **21-patch frame** (`flanks = 0` is the older 13-patch; `centers = 0` is a 9-slice):

- **4 corners** — one square each (TL, TR, BR, BL), drawn once at the border size, never tiled
- **8 corner sides** — the flank graphic beside each corner, drawn once at its PNG length
- **4 edge tiles** — REPEAT in the gaps beside the center band, each copy at the sample's own size
- **4 edge centers** — one graphic each, drawn once at its PNG size, never tiled
- **Inner middle** of the PNG — never drawn (window content sits there)

```
PNG mid-strip layout (each edge):

  [ FLANK ][ TILE sample ][ CENTER motif ][ FLANK ]

corners use `sizes` (L,R,T,B). `flanks` is the extra slice beside each
corner (top, right, bottom, left). `centers` is the center sample
(topW, rightH, bottomW, leftH). The rest of that mid strip is the tile.
```

On screen, each edge is drawn as:

```
  [corner][flank][tile…][center…][…tile][flank][corner]
```

Each flank is the graphic beside a corner. It is drawn once, at the pixel length stored in the PNG, and is not repeated. The center sample is one graphic, drawn once at its own pixel size. Top, right, bottom, and left each have their own center graphic. Tiles repeat in the gaps, one sample wide each time. Nothing is stretched to fit the window.

```
example.png  (16×16)     sizes = 5,5,5,5   centers = 0,0,0,0  (9-slice)

  0        5        11       16
  ├── 5px ─┼── 6px ─┼── 5px ─┤
    10|  ┌────────┬────────┬────────┐  0
  │   TL   │   TOP  │   TR   │  5px  corners: copied 1:1
  ├────────┼────────┼────────┤  5
  │  LEFT  │ unused │ RIGHT  │  6px  edges: tiled (OpenGL REPEAT)
  ├────────┼────────┼────────┤  11
  │   BL   │ BOTTOM │   BR   │  5px
  └────────┴────────┴────────┘  16
```

With a center motif (e.g. mid = 40px, `centers = 16,…`):

```
  Top edge strip in PNG:  [ TILE 24px ][ CENTER 16px ]
  Drawn on a 800px window: [tile…][center repeating across 600px][…tile]
```

## File rules

| Rule | Why |
|------|-----|
| **PNG only** | Loaded with Cairo `cairo_image_surface_create_from_png`. JPEG/WebP will fail. |
| **RGBA / alpha** | Fully transparent pixels are discarded (`DISCARD_ALPHA`). Use alpha for the inner hole and for soft edges. |
| **Square is easiest** | Not required. Width must be `left + right + mid > 0`. Height must be `top + bottom + mid > 0`. |
| **Does not have to be tiny** | 16×16 is a pixel-art demo. 64, 128, 256+ PNGs work. Larger art → larger `sizes` / `centers`. |

If `left + right >= image width` (or top+bottom vs height), slicing is rejected and borders stay off.

## What to paint in each region

**Corners (TL, TR, BR, BL)**  
One square each, drawn once at the border size. Put unique detail here (screws, rounded caps, ornaments). They do **not** tile.

**Edge tiles (TOP/BOTTOM/LEFT/RIGHT tile samples)**  
These must **tile seamlessly**. TOP/BOTTOM tile horizontally; LEFT/RIGHT tile vertically. In the PNG they sit in the **first** part of each mid strip (`[TILE][CENTER]`).

**Edge centers (one motif per side)**  
Non-repeating art for the middle of each side (emblem, latch, flourish). Sized by `centers`. Drawn once, centered on that edge, with tiles on both sides.

**Inner middle**  
Ignored. Keep it transparent (or any fill). It is never sampled on screen.

## Matching `sizes` and `centers` to the art

```
sizes   = LEFT, RIGHT, TOP, BOTTOM     # corner / edge thickness (PNG px)
centers = topW, rightH, bottomW, leftH # center motif size on each edge (PNG px)
```

`centers = 0` (or omit) → classic 9-slice; the whole mid strip is the tile.

For a 128×128 frame, 24px border, 32px center motifs:

```
sizes   = 24,24,24,24
centers = 32,32,32,32
```

Mid width = `128 - 24 - 24 = 80` → top strip is `[TILE 48px][CENTER 32px]`.

Uneven frames are allowed:

```
sizes   = 16,16,32,16
centers = 40,20,40,20
```

## On-screen thickness: `scale` and `insets`

Drawn thickness is:

```
visible_px = (sizes[side] - insets[side]) * scale * monitor_scale
```

| Key | Effect |
|-----|--------|
| `scale` | Multiply everything. |
| `insets` | Pull the frame **into** the window. |
| `smooth` | `false` = nearest-neighbor (pixel art). `true` = smoothed when scaled. |
| `blur` | Blur behind transparent parts of the frame. |
| `flanks` | Flank graphic beside each corner, in PNG pixels. Drawn once at that size. `0` skips them. |
| `centers` | One mid-edge graphic per side, in PNG pixels. Drawn once at that size. `0` = no center. |

## Making a new border (checklist)

1. Draw a **rectangular frame** in Aseprite, GIMP, or similar. Export **PNG**.
2. Leave the **inside empty** (alpha 0).
3. Measure frame thickness → `sizes`. Measure each side’s center motif → `centers`.
4. Confirm **tile** parts wrap seamlessly; center motifs can be unique.
5. Put the file somewhere stable, e.g. `~/.config/hypr/borders/` or `/usr/share/hyprframes/`.
6. Point settings at it (use an absolute `image` path):

```
# ~/.config/hypr/hyprframes.conf
image = /usr/share/hyprframes/example.png
sizes = 5,5,5,5
centers = 0,0,0,0
insets = 1,1,1,1
scale = 1
smooth = false
blur = false
```

7. Apply without logging out:

```
hyprctl dispatch hyprframesreload
```

Prefer this over `hyprctl reload` (full config reload still fights hyprbars on this desktop).

Do **not** put these keys in `hyprland.conf`. This plugin reads only `hyprframes.conf`.

## Generated test borders

```bash
cd borders && python3 generate.py   # heavy/thick 13-patch PNGs + .conf
./pick.sh                           # GTK picker → writes conf + hyprframesreload
# or: ../use-border.sh 01
```

---

## Build

**Deps:** CMake, a C++23 compiler, pkg-config, Hyprland headers (`hyprland`), `libdrm`, `pixman-1`, `pangocairo`, plus `curl` or `wget` for the one-time header fetch.

`third_party/` is **not** in git. Configure/build downloads [hyprutils v0.13.0](https://github.com/hyprwm/hyprutils/releases/tag/v0.13.0) headers there (needed so builds still work when the system has libhyprutils ≥ 0.14).

```bash
./fetch-third-party.sh   # optional; also run automatically by cmake / debug.sh
./debug.sh               # cmake + build → build/libhyprframes.so
./enable-next-login.sh   # then a new Hyprland session — not hyprctl plugin load
```

Or without the helper scripts:

```bash
cmake -S . -B build      # runs fetch-third-party.sh if headers are missing
cmake --build build -j"$(nproc)"
```

Load with `plugin = /path/to/libhyprframes.so` in `hyprland.conf` **before** hyprbars (or other titlebar plugins). Prefer a new session over `hyprctl plugin load` / `hyprctl reload` after hyprbars is already up.
