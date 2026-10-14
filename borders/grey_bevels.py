#!/usr/bin/env python3
"""Three more grey bevels. Same cool grey as the round bar and the step.

ridge  — a lit crest down the middle, dark on both rims
cove   — bright lips on both edges, a hollow shadow between them
bead   — two round beads with a dark gap
"""
from __future__ import annotations

import math
from pathlib import Path

import cairo

OUT = Path(__file__).resolve().parent
THICK = 40
H_FLANK, H_CENTER = 16 * THICK, 40 * THICK
V_FLANK, V_CENTER = 10 * THICK, 24 * THICK
WIDTH = THICK + H_FLANK + THICK + H_CENTER + H_FLANK + THICK
HEIGHT = THICK + V_FLANK + THICK + V_CENTER + V_FLANK + THICK


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * min(1.0, max(0.0, t))


def grey(v: float) -> tuple[float, float, float]:
    v = min(1.0, max(0.0, v))
    return v * 0.90, v * 0.92, v * 0.96


def ridge(t: float) -> tuple[float, float, float]:
    """Triangular crown. The highlight is the peak, not the outer shoulder."""
    t = min(1.0, max(0.0, t))
    if t < 0.08 or t > 0.92:
        v = 0.04
    elif t < 0.50:
        v = lerp(0.08, 0.98, (t - 0.08) / 0.42)
    else:
        v = lerp(0.98, 0.08, (t - 0.50) / 0.42)
    return grey(v)


def cove(t: float) -> tuple[float, float, float]:
    """Concave. Both lips catch light, the middle is a dark scoop."""
    t = min(1.0, max(0.0, t))
    if t < 0.05 or t > 0.95:
        v = 0.04
    elif t < 0.20:
        v = lerp(0.95, 0.40, (t - 0.05) / 0.15)
    elif t < 0.80:
        # Scoop: darkest at the center of the hollow.
        u = (t - 0.20) / 0.60
        v = 0.40 - 0.32 * math.sin(u * math.pi)
    else:
        v = lerp(0.40, 0.82, (t - 0.80) / 0.15)
    return grey(v)


def bead(t: float) -> tuple[float, float, float]:
    """Two separate rounds and a slot between them."""
    t = min(1.0, max(0.0, t))
    outer = math.exp(-((t - 0.22) ** 2) / 0.006)
    inner = math.exp(-((t - 0.74) ** 2) / 0.005)
    v = 0.045 + 0.92 * outer + 0.55 * inner
    if 0.40 < t < 0.58:
        v = 0.04
    return grey(min(1.0, v))


PROFILES = (
    ("00-21-grey-ridge", ridge, "Ridge. The highlight is a crest down the middle of the bar."),
    ("00-21-grey-cove", cove, "Cove. Both edges are lit, and the face is a dark hollow."),
    ("00-21-grey-bead", bead, "Double bead. Two round highlights with a dark slot between them."),
)


def make_tile(profile, horizontal: bool) -> cairo.ImageSurface:
    tile = cairo.ImageSurface(cairo.FORMAT_ARGB32, THICK, THICK)
    buf = tile.get_data()
    stride = tile.get_stride()
    for i in range(THICK):
        r, g, b = profile((i + 0.5) / THICK)
        R, G, B = int(r * 255), int(g * 255), int(b * 255)
        for j in range(THICK):
            x, y = (j, i) if horizontal else (i, j)
            p = y * stride + x * 4
            buf[p] = B
            buf[p + 1] = G
            buf[p + 2] = R
            buf[p + 3] = 255
    tile.mark_dirty()
    return tile


def flip_tile(tile: cairo.ImageSurface, across: bool) -> cairo.ImageSurface:
    flipped = cairo.ImageSurface(cairo.FORMAT_ARGB32, THICK, THICK)
    cr = cairo.Context(flipped)
    if across:
        cr.translate(THICK, 0)
        cr.scale(-1, 1)
    else:
        cr.translate(0, THICK)
        cr.scale(1, -1)
    cr.set_source_surface(tile, 0, 0)
    cr.paint()
    flipped.flush()
    return flipped


def stamp(cr: cairo.Context, tile: cairo.ImageSurface, x: float, y: float, w: float, h: float) -> None:
    cr.save()
    cr.rectangle(x, y, w, h)
    cr.clip()
    pat = cairo.SurfacePattern(tile)
    pat.set_extend(cairo.EXTEND_REPEAT)
    pat.set_filter(cairo.FILTER_NEAREST)
    cr.set_source(pat)
    cr.paint()
    cr.restore()


def paint_corner(surface: cairo.ImageSurface, profile, ox: int, oy: int, flip_x: bool, flip_y: bool) -> None:
    buf = surface.get_data()
    stride = surface.get_stride()
    for ly in range(THICK):
        for lx in range(THICK):
            x = (THICK - (lx + 0.5)) if flip_x else lx + 0.5
            y = (THICK - (ly + 0.5)) if flip_y else ly + 0.5
            r, g, b = profile(min(x, y) / THICK)
            p = (oy + ly) * stride + (ox + lx) * 4
            buf[p] = int(b * 255)
            buf[p + 1] = int(g * 255)
            buf[p + 2] = int(r * 255)
            buf[p + 3] = 255
    surface.mark_dirty()


def face_color(surface: cairo.ImageSurface) -> str:
    buf = surface.get_data()
    stride = surface.get_stride()
    p = int(THICK * 0.5) * stride + (THICK + 8) * 4
    b, g, r = buf[p], buf[p + 1], buf[p + 2]
    return f"#{r:02x}{g:02x}{b:02x}"


def write_one(name: str, profile, blurb: str) -> None:
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, WIDTH, HEIGHT)
    cr = cairo.Context(surface)
    cr.set_operator(cairo.OPERATOR_SOURCE)
    cr.set_source_rgba(0, 0, 0, 0)
    cr.paint()
    cr.set_operator(cairo.OPERATOR_OVER)

    across = make_tile(profile, True)
    along = make_tile(profile, False)
    stamp(cr, across, 0, 0, WIDTH, THICK)
    stamp(cr, flip_tile(across, False), 0, HEIGHT - THICK, WIDTH, THICK)
    stamp(cr, along, 0, THICK, THICK, HEIGHT - 2 * THICK)
    stamp(cr, flip_tile(along, True), WIDTH - THICK, THICK, THICK, HEIGHT - 2 * THICK)
    for ox, oy, fx, fy in (
        (0, 0, False, False),
        (WIDTH - THICK, 0, True, False),
        (0, HEIGHT - THICK, False, True),
        (WIDTH - THICK, HEIGHT - THICK, True, True),
    ):
        paint_corner(surface, profile, ox, oy, fx, fy)

    surface.flush()
    png = OUT / f"{name}.png"
    surface.write_to_png(str(png))
    line = face_color(surface)
    png.with_suffix(".conf").write_text(
        f"""# {blurb}
# Same cool grey as the round bar. The tile repeats. scale draws the band at 10px.
image = {png.name}
sizes = {THICK},{THICK},{THICK},{THICK}
flanks = {H_FLANK},{V_FLANK},{H_FLANK},{V_FLANK}
centers = {H_CENTER},{V_CENTER},{H_CENTER},{V_CENTER}
insets = 0,0,0,0
scale = {10 / THICK:.6f}
line = {line}
smooth = true
blur = false
""",
        encoding="utf-8",
    )
    print(f"wrote {png.name} line={line}")


def main() -> None:
    for name, profile, blurb in PROFILES:
        write_one(name, profile, blurb)


if __name__ == "__main__":
    main()
