#!/usr/bin/env python3
"""Stepped grey bevel. Same layout and grey as 00-21-grey, different profile.

Hard chamfers instead of a round bar: a bright outer bevel, a dark groove,
a flat face with a thin lip light, then a sharp inner shadow. Corners are
mitered, so each facet turns on the diagonal.
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
    return a + (b - a) * t


def shade(t: float) -> tuple[float, float, float]:
    """Faceted bar. t=0 is outside, t=1 is inside. Light sits on the outer cuts."""
    t = min(1.0, max(0.0, t))
    # Widths chosen so each facet still shows when the band is drawn at 10px.
    if t < 0.06:
        v = 0.04
    elif t < 0.24:
        # Outer chamfer: hard specular at the leading edge, then it falls off.
        k = (t - 0.06) / 0.18
        v = lerp(0.96, 0.42, k * k)
    elif t < 0.34:
        # Groove between the two bevels.
        k = (t - 0.24) / 0.10
        v = lerp(0.16, 0.08, k)
    elif t < 0.40:
        # Lip light on the face, a thin line rather than a soft glow.
        k = (t - 0.34) / 0.06
        v = lerp(0.78, 0.46, k)
    elif t < 0.72:
        v = 0.40
    elif t < 0.90:
        # Inner chamfer, shadow only.
        k = (t - 0.72) / 0.18
        v = lerp(0.28, 0.07, k)
    else:
        v = 0.035
    # Same cool grey as the round frame.
    return v * 0.90, v * 0.92, v * 0.96


def make_tile(horizontal: bool) -> cairo.ImageSurface:
    tile = cairo.ImageSurface(cairo.FORMAT_ARGB32, THICK, THICK)
    buf = tile.get_data()
    stride = tile.get_stride()
    for i in range(THICK):
        r, g, b = shade((i + 0.5) / THICK)
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


def paint_corner(surface: cairo.ImageSurface, ox: int, oy: int, flip_x: bool, flip_y: bool) -> None:
    """Miter. Distance to the outer edges, so each facet turns on the diagonal."""
    buf = surface.get_data()
    stride = surface.get_stride()
    for ly in range(THICK):
        for lx in range(THICK):
            lx_c = lx + 0.5
            ly_c = ly + 0.5
            x = (THICK - lx_c) if flip_x else lx_c
            y = (THICK - ly_c) if flip_y else ly_c
            t = min(x, y) / THICK
            r, g, b = shade(t)
            p = (oy + ly) * stride + (ox + lx) * 4
            buf[p] = int(b * 255)
            buf[p + 1] = int(g * 255)
            buf[p + 2] = int(r * 255)
            buf[p + 3] = 255
    surface.mark_dirty()


def face_color(surface: cairo.ImageSurface) -> str:
    buf = surface.get_data()
    stride = surface.get_stride()
    x = THICK + 8
    y = int(THICK * 0.55)
    p = y * stride + x * 4
    b, g, r = buf[p], buf[p + 1], buf[p + 2]
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
    png = OUT / "00-21-grey-bevel.png"
    surface.write_to_png(str(png))
    line = face_color(surface)
    scale = 10 / THICK
    png.with_suffix(".conf").write_text(
        f"""# Stepped grey bevel. Hard outer highlight, flat face, sharp inner shadow.
# Corners are mitered. The tile repeats, so the sides stay one solid bar.
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
