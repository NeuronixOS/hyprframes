# ImageBorders — how the PNG is drawn

The plugin treats the PNG as a **21-patch frame** (`flanks = 0` is the older 13-patch; `centers = 0` is a 9-slice):

- **4 corners** — drawn once, never tiled
- **8 corner sides** — one extra image on each edge that meets a corner, drawn once
- **4 edge tiles** — REPEAT in the gaps beside the center band
- **4 edge centers** — REPEAT across **half** of that side (window width on top/bottom, window height on left/right)
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

Each flank is the extra image on that side of the corner and is drawn once. The center sample repeats until it covers half of that side, without covering the flanks. Tiles repeat in the gaps.

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
Drawn once at each window corner. Put unique detail here (screws, rounded caps, ornaments). They do **not** tile.

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
| `flanks` | Fixed slice on each side of every corner (PNG px). `0` skips them. |
| `centers` | Repeating mid-edge sample. The band covers half of that side. `0` = no center. |

## Making a new border (checklist)

1. Draw a **rectangular frame** in Aseprite, GIMP, or similar. Export **PNG**.
2. Leave the **inside empty** (alpha 0).
3. Measure frame thickness → `sizes`. Measure each side’s center motif → `centers`.
4. Confirm **tile** parts wrap seamlessly; center motifs can be unique.
5. Put the file somewhere stable, e.g. `~/.config/hypr/borders/` or `/usr/share/neuronix/imgborders/`.
6. Point settings at it:

```
# ~/.config/hypr/imgborders.conf
image = /usr/share/neuronix/imgborders/example.png
sizes = 5,5,5,5
centers = 0,0,0,0
insets = 1,1,1,1
scale = 1
smooth = false
blur = false
```

7. Apply without logging out:

```
hyprctl dispatch imgbordersreload
```

Prefer this over `hyprctl reload` (full config reload still fights hyprbars on this desktop).

Do **not** put these keys in `hyprland.conf`. This plugin reads only `imgborders.conf`.

## Generated test borders

```bash
cd borders && python3 generate.py   # heavy/thick 13-patch PNGs + .conf
./pick.sh                           # GTK picker → writes conf + imgbordersreload
# or: ../use-border.sh 01
```

---

## Debug log (survives crashes)

Plugin writes a flushed log to:

```
~/.cache/hyprland/imgborders.log
```

Override with `IMGBORDERS_LOG=/path`. On SEGV/ABRT it appends
`*** IMGBORDERS CRASH signal=… stage=…` (last breadcrumb) then chains to
Hyprland’s crash reporter.

```bash
tail -100 ~/.cache/hyprland/imgborders.log
```

## Build / ISO (this machine)

```bash
./debug.sh
./enable-next-login.sh    # then a new Hyprland session — not hyprctl plugin load
```

ISO: `neuronix-iso/setup.sh` stages sources to `/usr/src/neuronix/imgborders`; hook `998` builds `libimgborders.so` to `/usr/local/lib/hyprland/plugins/`. `hyprland.conf` uses `plugin =` **before** hyprbars.
