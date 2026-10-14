#!/usr/bin/env python3
"""Grey-black 21-patch. Same layout as 00-21-aspect.png.

A round moulding: highlight on the outer shoulder, shadow on the inner
curve, and a rounded outer corner. The tile is that same profile, so the
sides stay one solid bar.
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


def shade(t: float) -> tuple[float, float, float]:
    """Round bar, lit from the outside. t=0 is the outer edge, t=1 the inner."""
    t = min(1.0, max(0.0, t))
    # Soft shoulder highlight, then the face falls into the inner shadow.
    highlight = math.exp(-((t - 0.18) ** 2) / 0.010)
    face = math.exp(-((t - 0.40) ** 2) / 0.055)
    inner = math.exp(-((t - 0.72) ** 2) / 0.030)
    rim_out = math.exp(-(t ** 2) / 0.0012)
    rim_in = math.exp(-((t - 1.0) ** 2) / 0.0016)
    v = 0.07 + 0.86 * highlight + 0.34 * face + 0.06 * inner
    v *= (1.0 - 0.92 * rim_out) * (1.0 - 0.88 * rim_in)
    v = max(0.0, min(1.0, v))
    # Slightly cool grey, not pure white.
    return v * 0.90, v * 0.92, v * 0.96


def make_tile(horizontal: bool) -> cairo.ImageSurface:
    tile = cairo.ImageSurface(cairo.FORMAT_ARGB32, THICK, THICK)
    buf = tile.get_data()
    stride = tile.get_stride()
    for i in range(THICK):
        r, g, b = shade((i + 0.5) / THICK)
        R, G, B = int(r * 255), int(g * 255), int(b * 255)
        for j in range(THICK):
            if horizontal:
                x, y = j, i
            else:
                x, y = i, j
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


def paint_corner(surface: cairo.ImageSurface, ox: int, oy: int, flip_x: bool, flip_y: bool) -> None:
    """Quarter-round outer corner. The profile matches the straight rail."""
    buf = surface.get_data()
    stride = surface.get_stride()
    for ly in range(THICK):
        for lx in range(THICK):
            # Pixel centers, measured from the outer corner, so the arc
            # meets the straight rail on the same shade.
            lx_c = lx + 0.5
            ly_c = ly + 0.5
            x = (THICK - lx_c) if flip_x else lx_c
            y = (THICK - ly_c) if flip_y else ly_c
            dist = math.hypot(THICK - x, THICK - y)
            px = ox + lx
            py = oy + ly
            p = py * stride + px * 4
            if dist >= THICK + 0.75:
                buf[p] = buf[p + 1] = buf[p + 2] = buf[p + 3] = 0
                continue
            t = 1.0 - min(dist, THICK) / THICK
            alpha = 1.0 if dist <= THICK else max(0.0, (THICK + 0.75 - dist) / 0.75)
            r, g, b = shade(t)
            a = int(round(alpha * 255))
            buf[p] = int(b * a)
            buf[p + 1] = int(g * a)
            buf[p + 2] = int(r * a)
            buf[p + 3] = a
    surface.mark_dirty()


def face_color(surface: cairo.ImageSurface) -> str:
    buf = surface.get_data()
    stride = surface.get_stride()
    # Mid-face of the top rail, past the corner.
    x = THICK + 8
    y = int(THICK * 0.40)
    p = y * stride + x * 4
    b, g, r, a = buf[p], buf[p + 1], buf[p + 2], buf[p + 3]
    if a:
        r = min(255, r * 255 // a)
        g = min(255, g * 255 // a)
        b = min(255, b * 255 // a)
    return f"#{r:02x}{g:02x}{b:02x}"


def main() -> None:
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, WIDTH, HEIGHT)
    cr = cairo.Context(surface)
    cr.set_operator(cairo.OPERATOR_SOURCE)
    cr.set_source_rgba(0, 0, 0, 0)
    cr.paint()
    cr.set_operator(cairo.OPERATOR_OVER)

    across = make_tile(True)
    along = make_tile(False)
    stamp(cr, across, 0, 0, WIDTH, THICK)
    stamp(cr, flip_tile(across, across=False), 0, HEIGHT - THICK, WIDTH, THICK)
    stamp(cr, along, 0, THICK, THICK, HEIGHT - 2 * THICK)
    stamp(cr, flip_tile(along, across=True), WIDTH - THICK, THICK, THICK, HEIGHT - 2 * THICK)

    paint_corner(surface, 0, 0, False, False)
    paint_corner(surface, WIDTH - THICK, 0, True, False)
    paint_corner(surface, 0, HEIGHT - THICK, False, True)
    paint_corner(surface, WIDTH - THICK, HEIGHT - THICK, True, True)

    surface.flush()
    png = OUT / "00-21-grey.png"
    surface.write_to_png(str(png))
    line = face_color(surface)
    scale = 10 / THICK
    png.with_suffix(".conf").write_text(
        f"""# Grey-black round moulding. Highlight outside, shadow inside.
# The 40px tile repeats, so the sides stay one solid bar.
# scale draws the band at 10px.
image = {png.name}
sizes = {THICK},{THICK},{THICK},{THICK}
flanks = {H_FLANK},{V_FLANK},{H_FLANK},{V_FLANK}
centers = {H_CENTER},{V_CENTER},{H_CENTER},{V_CENTER}
insets = 0,0,0,0
scale = {scale:.6f}
line = {line}
smooth = true
blur = false
""",
        encoding="utf-8",
    )
    print(f"wrote {png.name} {WIDTH}x{HEIGHT} scale={scale:.2f} line={line}")


if __name__ == "__main__":
    main()
