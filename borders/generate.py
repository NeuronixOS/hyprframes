#!/usr/bin/env python3
"""Generate 21-patch PNG frames for hyprframes.

Each edge of the PNG, between the corners:

  [FLANK][TILE sample][CENTER motif][FLANK]

The flank is the extra image on that side of the corner (drawn once).
`flanks` is its length along the edge. `centers` is the center sample.
Both are PNG pixels. flanks=0 keeps a 13-patch.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import cairo

OUT = Path(__file__).resolve().parent


def rgba(hex_color: str, a: float = 1.0) -> tuple[float, float, float, float]:
    h = hex_color.lstrip("#")
    return (
        int(h[0:2], 16) / 255.0,
        int(h[2:4], 16) / 255.0,
        int(h[4:6], 16) / 255.0,
        a,
    )


def diamond(cr: cairo.Context, cx: float, cy: float, rx: float, ry: float | None = None) -> None:
    if ry is None:
        ry = rx
    cr.move_to(cx, cy - ry)
    cr.line_to(cx + rx, cy)
    cr.line_to(cx, cy + ry)
    cr.line_to(cx - rx, cy)
    cr.close_path()
    cr.fill()


def make_frame(
    path: Path,
    size: int,
    thickness: int,
    center: int,
    flank: int,
    fill: str,
    accent: str,
    style: str,
    inset_conf: int = 0,
    smooth: bool = True,
) -> None:
    """21-patch frame. mid = flank + tile + center + flank."""
    assert size > 2 * thickness >= 2
    mid = size - 2 * thickness
    flank = max(0, min(flank, mid // 2))
    center = max(0, min(center, mid - 2 * flank))
    tile = mid - 2 * flank - center
    if tile < 1 and center > 0:
        center = max(0, mid - 2 * flank - 1)
        tile = mid - 2 * flank - center

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    cr = cairo.Context(surface)
    cr.set_operator(cairo.OPERATOR_CLEAR)
    cr.paint()
    cr.set_operator(cairo.OPERATOR_OVER)

    L = R = T = B = thickness
    F = flank
    Wt, Wc = tile, center
    Ht, Hc = tile, center

    # --- fill edge bands (frame ring) ---
    cr.set_source_rgba(*rgba(fill))
    cr.rectangle(0, 0, size, size)
    cr.rectangle(L, T, mid, mid)
    cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    cr.fill()

    # Tile-region texture (left of top center, above left center, …)
    cr.set_source_rgba(*rgba(accent, 0.85))
    bead = max(1.2, thickness * 0.22)

    def beads_h(x0: float, y: float, w: float) -> None:
        if w <= 0:
            return
        n = max(1, int(w / (bead * 3)))
        for i in range(n):
            x = x0 + (i + 0.5) * (w / n)
            cr.arc(x, y, bead, 0, 2 * math.pi)
            cr.fill()

    def beads_v(x: float, y0: float, h: float) -> None:
        if h <= 0:
            return
        n = max(1, int(h / (bead * 3)))
        for i in range(n):
            y = y0 + (i + 0.5) * (h / n)
            cr.arc(x, y, bead, 0, 2 * math.pi)
            cr.fill()

    tile_x = L + F
    tile_y = T + F
    if style in ("dots", "glow") and Wt > 0:
        beads_h(tile_x, T / 2, Wt)
        beads_h(tile_x, size - T / 2, Wt)
        beads_v(L / 2, tile_y, Ht)
        beads_v(size - R / 2, tile_y, Ht)
    elif style == "stripe" and Wt > 0:
        cr.set_line_width(max(1.0, thickness * 0.18))
        cr.set_source_rgba(*rgba(accent))
        for y in (T / 2, size - T / 2):
            cr.move_to(tile_x, y)
            cr.line_to(tile_x + Wt, y)
            cr.stroke()
        for x in (L / 2, size - R / 2):
            cr.move_to(x, tile_y)
            cr.line_to(x, tile_y + Ht)
            cr.stroke()

    # Corner-side slices: circle on the near end of an edge, square on the far end.
    if F > 0:
        cr.set_source_rgba(*rgba(accent))
        rad = min(F, thickness) * 0.28

        def mark(cx: float, cy: float, square: bool) -> None:
            if square:
                cr.rectangle(cx - rad, cy - rad, rad * 2, rad * 2)
                cr.fill()
            else:
                cr.arc(cx, cy, rad, 0, 2 * math.pi)
                cr.fill()

        mark(L + F / 2, T / 2, False)
        mark(L + F + Wt + Wc + F / 2, T / 2, True)
        mark(L + F / 2, size - T / 2, False)
        mark(L + F + Wt + Wc + F / 2, size - T / 2, True)
        mark(L / 2, T + F / 2, False)
        mark(L / 2, T + F + Ht + Hc + F / 2, True)
        mark(size - R / 2, T + F / 2, False)
        mark(size - R / 2, T + F + Ht + Hc + F / 2, True)

    # Center panels fill the CENTER slot. Width/height track `center`,
    # so a 2× center value is a 2× panel (not a thickness-capped diamond).
    if Wc > 0 and Hc > 0:
        cr.set_source_rgba(*rgba(accent, 0.55))
        cx0 = L + F + Wt
        cy0 = T + F + Ht
        cr.rectangle(cx0, 0, Wc, T)
        cr.rectangle(cx0, size - B, Wc, B)
        cr.rectangle(0, cy0, L, Hc)
        cr.rectangle(size - R, cy0, R, Hc)
        cr.fill()

        # One unique center graphic per side. Each spans the center slot
        # (400px long) and is drawn once.
        cr.set_source_rgba(*rgba(accent))
        diamond(cr, cx0 + Wc / 2, T / 2, Wc * 0.46, T * 0.40)
        cr.save()
        cr.translate(size - R / 2, cy0 + Hc / 2)
        cr.scale(R * 0.40, Hc * 0.46)
        cr.arc(0, 0, 1, 0, 2 * math.pi)
        cr.restore()
        cr.fill()
        bw, bh = Wc * 0.72, B * 0.62
        cr.rectangle(cx0 + (Wc - bw) / 2, size - (B + bh) / 2, bw, bh)
        cr.fill()
        cr.move_to(L / 2, cy0 + Hc * 0.08)
        cr.line_to(L * 0.82, cy0 + Hc * 0.92)
        cr.line_to(L * 0.18, cy0 + Hc * 0.92)
        cr.close_path()
        cr.fill()

    # Corner caps stay one square. Only some styles mark them.
    if style in ("corner_caps", "glow"):
        cr.set_source_rgba(*rgba(accent))
        r = thickness * 0.32
        for cx, cy in (
            (L / 2, T / 2),
            (size - R / 2, T / 2),
            (size - R / 2, size - B / 2),
            (L / 2, size - B / 2),
        ):
            cr.arc(cx, cy, r, 0, 2 * math.pi)
            cr.fill()

    surface.write_to_png(str(path))

    # centers = topW, rightH, bottomW, leftH
    conf = path.with_suffix(".conf")
    conf.write_text(
        f"""# Auto-generated 21-patch for {path.name}
# Mid strip = [FLANK {flank}px][TILE {tile}px][CENTER {center}px][FLANK {flank}px]
image = {path.name}
sizes = {thickness},{thickness},{thickness},{thickness}
flanks = {flank},{flank},{flank},{flank}
centers = {center},{center},{center},{center}
insets = {inset_conf},{inset_conf},{inset_conf},{inset_conf}
scale = {min(1.0, 10 / max(1, thickness - inset_conf)):.6f}
line = #c9a36a
smooth = {"true" if smooth else "false"}
blur = false
""",
        encoding="utf-8",
    )
    print(
        f"wrote {path.name}  ({size}x{size} thick={thickness} "
        f"flank={flank} tile={tile} center={center} {style})"
    )


# name, thickness, fill, fill2, accent, rail, flank style
# Flank length is 4× thickness. Center is 400px, drawn once.
# The tile is one thickness square and must repeat cleanly.
GALLERY = [
    ("06-oak", 18, "#7a4a22", "#4a2c12", "#f2d48b", "#c4924a", "diamond"),
    ("07-iron", 14, "#2c333a", "#14181c", "#e7edf2", "#8b949e", "plate"),
    ("08-jade", 16, "#0f6a4a", "#063528", "#f3d78c", "#d4b15a", "circle"),
    ("09-frost", 14, "#c5e4f5", "#7eafd0", "#ffffff", "#3e7398", "cluster"),
    ("10-ember", 16, "#1a100c", "#0a0706", "#ff7a2a", "#ffb15e", "streak"),
    ("11-copper", 18, "#c56a38", "#6e3418", "#f6e6c8", "#3faf96", "circle"),
    ("12-midnight", 14, "#101428", "#070912", "#8ef0ff", "#3d6d88", "neon"),
    ("13-sand", 20, "#e6cb9e", "#b89262", "#5c3d22", "#8a6844", "ticks"),
    ("14-pine", 16, "#1b4a30", "#0c2818", "#d5e07a", "#8fb56a", "triangle"),
    ("15-porcelain", 18, "#f4f1ea", "#ddd6c8", "#1e4f8a", "#163a66", "circle"),
    ("16-lacquer", 16, "#7a1020", "#3c0610", "#f0d48b", "#c9a24a", "diamond"),
    ("17-ink", 12, "#161616", "#050505", "#e4e4e4", "#8a8a8a", "square"),
]

TILE_BEAD = {
    "plate": "circle",
    "circle": "circle",
    "cluster": "diamond",
    "ticks": "tick",
}

CENTER_MARK = ("diamond", "circle", "plaque", "triangle")


def _gallery_names() -> set[str]:
    names: set[str] = set()
    for row in GALLERY:
        names.add(f"{row[0]}.png")
        names.add(f"{row[0]}.conf")
    return names


# Hand-made frames the generator must not delete.
KEEP = {
    "dwarf.png",
    "dwarf.conf",
    "00-21-squares.png",
    "00-21-squares.conf",
    "00-21-aspect.png",
    "00-21-aspect.conf",
    "00-21-wood.png",
    "00-21-wood.conf",
    "00-21-steel.png",
    "00-21-steel.conf",
    "00-21-hitech.png",
    "00-21-hitech.conf",
    "00-21-bond.png",
    "00-21-bond.conf",
    "00-21-runeplate.png",
    "00-21-runeplate.conf",
    "00-21-grey.png",
    "00-21-grey.conf",
    "00-21-grey-bevel.png",
    "00-21-grey-bevel.conf",
    "00-21-grey-ridge.png",
    "00-21-grey-ridge.conf",
    "00-21-grey-cove.png",
    "00-21-grey-cove.conf",
    "00-21-grey-bead.png",
    "00-21-grey-bead.conf",
    "00-21-oak.png",
    "00-21-oak.conf",
    "05-bond.png",
    "05-bond.conf",
    "moria.png",
    "moria.conf",
    "moria-1024.png",
    "moria-1024.conf",
    "18-filigree.png",
    "18-filigree.conf",
    "19-scales.png",
    "19-scales.conf",
    "20-rune-plate.png",
    "20-rune-plate.conf",
    "21-hex-steel.png",
    "21-hex-steel.conf",
    "22-stone-rune.png",
    "22-stone-rune.conf",
    "23-rivet.png",
    "23-rivet.conf",
    "24-furnace.png",
    "24-furnace.conf",
    "25-glow-wood.png",
    "25-glow-wood.conf",
    "26-neon.png",
    "26-neon.conf",
    "27-plasma.png",
    "27-plasma.conf",
    "28-scales.png",
    "28-scales.conf",
    "29-rune-plate.png",
    "29-rune-plate.conf",
    "30-hex-steel.png",
    "30-hex-steel.conf",
    "31-stone-rune.png",
    "31-stone-rune.conf",
    "32-rivet.png",
    "32-rivet.conf",
    "33-furnace.png",
    "33-furnace.conf",
    "34-glow-wood.png",
    "34-glow-wood.conf",
    "35-neon.png",
    "35-neon.conf",
    "36-plasma.png",
    "36-plasma.conf",
} | _gallery_names()


def _clip_ring(cr: cairo.Context, size: int, t: int) -> None:
    cr.rectangle(0, 0, size, size)
    cr.rectangle(t, t, size - 2 * t, size - 2 * t)
    cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    cr.clip()
    cr.set_fill_rule(cairo.FILL_RULE_WINDING)


def _mark(cr: cairo.Context, cx: float, cy: float, kind: str, t: float) -> None:
    s = t * 0.36
    if kind == "diamond":
        diamond(cr, cx, cy, s, s * 0.86)
    elif kind == "circle":
        cr.arc(cx, cy, s * 0.82, 0, 2 * math.pi)
        cr.fill()
    elif kind == "square":
        cr.rectangle(cx - s * 0.78, cy - s * 0.78, s * 1.56, s * 1.56)
        cr.fill()
    elif kind == "triangle":
        cr.move_to(cx, cy - s)
        cr.line_to(cx + s * 0.92, cy + s * 0.72)
        cr.line_to(cx - s * 0.92, cy + s * 0.72)
        cr.close_path()
        cr.fill()
    elif kind == "plaque":
        pw, ph = s * 2.5, s * 1.05
        cr.rectangle(cx - pw / 2, cy - ph / 2, pw, ph)
        cr.fill()


def _lerp(a: str, b: str, u: float) -> tuple[float, float, float, float]:
    ca, cb = rgba(a), rgba(b)
    return tuple(ca[i] + (cb[i] - ca[i]) * u for i in range(4))


def _rail(cr: cairo.Context, size: int, t: int, color: str, pos: float, width: float) -> None:
    dist = t * pos
    cr.set_source_rgba(*rgba(color, 0.95))
    cr.set_line_width(width)
    cr.rectangle(dist, dist, size - 2 * dist, size - 2 * dist)
    cr.stroke()


def _paint_tile(cr: cairo.Context, box: tuple[int, int, int, int], bead: str | None, color: str, t: int, along: str) -> None:
    if not bead:
        return
    x, y, w, h = box
    cx, cy = x + w / 2, y + h / 2
    cr.save()
    cr.rectangle(x, y, w, h)
    cr.clip()
    cr.set_source_rgba(*rgba(color))
    if bead == "circle":
        cr.arc(cx, cy, max(1.15, t * 0.15), 0, 2 * math.pi)
        cr.fill()
    elif bead == "diamond":
        diamond(cr, cx, cy, t * 0.16, t * 0.16)
    elif bead == "tick":
        cr.set_line_width(max(1.25, t * 0.12))
        cr.set_line_cap(cairo.LINE_CAP_BUTT)
        if along == "h":
            cr.move_to(cx, y + h * 0.28)
            cr.line_to(cx, y + h * 0.72)
        else:
            cr.move_to(x + w * 0.28, cy)
            cr.line_to(x + w * 0.72, cy)
        cr.stroke()
    cr.restore()


def _paint_flank(cr: cairo.Context, box: tuple[int, int, int, int], style: str, color: str, metal: str, t: int) -> None:
    x, y, w, h = box
    horizontal = w >= h
    cx, cy = x + w / 2, y + h / 2
    cr.save()
    cr.rectangle(x + 1, y + 1, max(1, w - 2), max(1, h - 2))
    cr.clip()
    cr.set_source_rgba(*rgba(color))
    if style == "plate":
        if horizontal:
            pw, ph = w * 0.62, h * 0.48
        else:
            pw, ph = w * 0.48, h * 0.62
        cr.rectangle(cx - pw / 2, cy - ph / 2, pw, ph)
        cr.fill()
        cr.set_source_rgba(*rgba(metal))
        gap = (pw if horizontal else ph) * 0.28
        r = max(1.1, t * 0.13)
        for sign in (-1, 1):
            if horizontal:
                cr.arc(cx + sign * gap, cy, r, 0, 2 * math.pi)
            else:
                cr.arc(cx, cy + sign * gap, r, 0, 2 * math.pi)
            cr.fill()
    elif style == "streak":
        cr.set_line_width(max(2.0, t * 0.30))
        cr.set_line_cap(cairo.LINE_CAP_BUTT)
        if horizontal:
            cr.move_to(x + w * 0.18, cy)
            cr.line_to(x + w * 0.82, cy)
        else:
            cr.move_to(cx, y + h * 0.18)
            cr.line_to(cx, y + h * 0.82)
        cr.stroke()
    elif style == "cluster":
        for o in (-0.72, 0.0, 0.72):
            if horizontal:
                diamond(cr, cx + o * t, cy, t * 0.18, t * 0.18)
            else:
                diamond(cr, cx, cy + o * t, t * 0.18, t * 0.18)
    elif style == "ticks":
        cr.set_line_width(max(1.6, t * 0.14))
        cr.set_line_cap(cairo.LINE_CAP_BUTT)
        for o in (-0.72, 0.0, 0.72):
            if horizontal:
                px = cx + o * t
                cr.move_to(px, y + h * 0.22)
                cr.line_to(px, y + h * 0.78)
            else:
                py = cy + o * t
                cr.move_to(x + w * 0.22, py)
                cr.line_to(x + w * 0.78, py)
            cr.stroke()
    elif style == "neon":
        _mark(cr, cx, cy, "diamond", t * 1.05)
    else:
        _mark(cr, cx, cy, style, t * 1.2)
    cr.restore()


def _paint_center(cr: cairo.Context, box: tuple[int, int, int, int], style: str, color: str, metal: str, t: int, kind: str) -> None:
    """One 400px graphic: a bar, end marks, and a middle mark. Not a repeat."""
    x, y, w, h = box
    horizontal = w >= h
    cx, cy = x + w / 2, y + h / 2
    cr.save()
    cr.rectangle(x, y, w, h)
    cr.clip()
    cr.set_source_rgba(*rgba(color))
    if style == "plate":
        if horizontal:
            pw, ph = w * 0.86, h * 0.42
        else:
            pw, ph = w * 0.42, h * 0.86
        cr.rectangle(cx - pw / 2, cy - ph / 2, pw, ph)
        cr.fill()
        cr.set_source_rgba(*rgba(metal))
        _mark(cr, cx, cy, "circle", t * 0.85)
        end = (pw if horizontal else ph) * 0.38
        r = max(1.1, t * 0.12)
        cr.set_source_rgba(*rgba(metal))
        for sign in (-1, 1):
            if horizontal:
                cr.arc(cx + sign * end, cy, r, 0, 2 * math.pi)
            else:
                cr.arc(cx, cy + sign * end, r, 0, 2 * math.pi)
            cr.fill()
    else:
        cr.set_line_width(max(1.6, t * 0.20))
        cr.set_line_cap(cairo.LINE_CAP_BUTT)
        if horizontal:
            cr.move_to(x + t * 0.45, cy)
            cr.line_to(x + w - t * 0.45, cy)
        else:
            cr.move_to(cx, y + t * 0.45)
            cr.line_to(cx, y + h - t * 0.45)
        cr.stroke()
        if horizontal:
            ends = ((x + t * 0.95, cy), (x + w - t * 0.95, cy))
        else:
            ends = ((cx, y + t * 0.95), (cx, y + h - t * 0.95))
        for ex, ey in ends:
            diamond(cr, ex, ey, t * 0.20, t * 0.20)
        _mark(cr, cx, cy, kind, t * 1.35)
    cr.restore()


def write_gallery() -> None:
    """Themed 21-patch frames. Each tile period is one border square."""
    center = 400
    for name, t, fill, fill2, accent, rail, style in GALLERY:
        flank = 4 * t
        tile = t
        size = t * 2 + flank * 2 + tile + center
        path = OUT / f"{name}.png"
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
        cr = cairo.Context(surface)
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        cr.set_line_join(cairo.LINE_JOIN_MITER)
        cr.set_line_cap(cairo.LINE_CAP_BUTT)

        grad = cairo.LinearGradient(0, 0, size, size)
        grad.add_color_stop_rgba(0, *rgba(fill))
        grad.add_color_stop_rgba(1, *rgba(fill2))
        cr.set_source(grad)
        cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        cr.rectangle(0, 0, size, size)
        cr.rectangle(t, t, size - 2 * t, size - 2 * t)
        cr.fill()
        cr.set_fill_rule(cairo.FILL_RULE_WINDING)

        x_fl = t
        x_tile = t + flank
        x_ctr = t + flank + tile
        x_fl2 = t + flank + tile + center
        y_fl = t
        y_tile = t + flank
        y_ctr = t + flank + tile
        y_fl2 = t + flank + tile + center
        right = size - t
        bottom = size - t
        tiles = [
            ((x_tile, 0, tile, t), "h"),
            ((right, y_tile, t, tile), "v"),
            ((x_tile, bottom, tile, t), "h"),
            ((0, y_tile, t, tile), "v"),
        ]

        cr.save()
        _clip_ring(cr, size, t)
        # Flat tile color. A gradient slice would show a seam every time it repeats.
        for box, _along in tiles:
            x, y, w, h = box
            u = ((x + w / 2) + (y + h / 2)) / (2 * size)
            cr.set_source_rgba(*_lerp(fill, fill2, u))
            cr.rectangle(x, y, w, h)
            cr.fill()
        cr.set_source_rgba(0, 0, 0, 0.40)
        cr.set_line_width(max(1.0, t * 0.08))
        cr.rectangle(1, 1, size - 2, size - 2)
        cr.stroke()
        cr.rectangle(t - 1.5, t - 1.5, size - 2 * (t - 1.5), size - 2 * (t - 1.5))
        cr.stroke()
        rail_w = max(1.15, t * 0.10)
        if style == "neon":
            _rail(cr, size, t, accent, 0.36, rail_w)
            _rail(cr, size, t, accent, 0.64, rail_w)
        else:
            _rail(cr, size, t, rail, 0.50, rail_w)

        bead = TILE_BEAD.get(style)
        for box, along in tiles:
            _paint_tile(cr, box, bead, accent, t, along)

        flanks = [
            (x_fl, 0, flank, t),
            (x_fl2, 0, flank, t),
            (right, y_fl, t, flank),
            (right, y_fl2, t, flank),
            (x_fl, bottom, flank, t),
            (x_fl2, bottom, flank, t),
            (0, y_fl, t, flank),
            (0, y_fl2, t, flank),
        ]
        for box in flanks:
            _paint_flank(cr, box, style, accent, fill2, t)

        centers = [
            ((x_ctr, 0, center, t), CENTER_MARK[0]),
            ((right, y_ctr, t, center), CENTER_MARK[1]),
            ((x_ctr, bottom, center, t), CENTER_MARK[2]),
            ((0, y_ctr, t, center), CENTER_MARK[3]),
        ]
        for box, kind in centers:
            _paint_center(cr, box, style, accent, fill2, t, kind)

        corners = [
            (t / 2, t / 2),
            (size - t / 2, t / 2),
            (size - t / 2, size - t / 2),
            (t / 2, size - t / 2),
        ]
        corner_kind = {
            "plate": "circle",
            "streak": "circle",
            "cluster": "diamond",
            "ticks": "square",
            "neon": "square",
        }.get(style, style)
        cr.set_source_rgba(*rgba(accent))
        for cx, cy in corners:
            _mark(cr, cx, cy, corner_kind, t * 0.95)
        cr.restore()

        surface.write_to_png(str(path))
        conf = path.with_suffix(".conf")
        conf.write_text(
            f"""# Gallery 21-patch for {path.name}
# Mid strip = [FLANK {flank}px once][TILE {tile}px, repeats][CENTER {center}px once][FLANK {flank}px once]
# TILE is one border square. Its opposite edges match, so it can repeat for any window size.
image = {path.name}
sizes = {t},{t},{t},{t}
flanks = {flank},{flank},{flank},{flank}
centers = {center},{center},{center},{center}
insets = 1,1,1,1
scale = {min(1.0, 10 / max(1, t - 1)):.6f}
line = #c9a36a
smooth = true
blur = false
""",
            encoding="utf-8",
        )
        print(
            f"wrote {path.name}  ({size}x{size} thick={t} "
            f"flank={flank} tile={tile} center={center} {style})"
        )


def _gaps(text: str, key: str) -> list[int]:
    for line in text.splitlines():
        body = line.split("#", 1)[0]
        if "=" not in body:
            continue
        k, v = body.split("=", 1)
        if k.strip() == key:
            return [int(float(p)) for p in v.split(",") if p.strip()]
    raise ValueError(f"{key} missing")


def _blit(cr: cairo.Context, src: cairo.ImageSurface, sx: int, sy: int, sw: int, sh: int, dx: int, dy: int) -> None:
    if sw <= 0 or sh <= 0:
        return
    cr.save()
    cr.rectangle(dx, dy, sw, sh)
    cr.clip()
    cr.set_source_surface(src, dx - sx, dy - sy)
    cr.paint()
    cr.restore()


def _repeat(cr: cairo.Context, src: cairo.ImageSurface, sx: int, sy: int, sw: int, sh: int, dx: int, dy: int, times: int, horizontal: bool) -> None:
    for i in range(times):
        if horizontal:
            _blit(cr, src, sx, sy, sw, sh, dx + i * sw, dy)
        else:
            _blit(cr, src, sx, sy, sw, sh, dx, dy + i * sh)


def expand_native_flanks(
    png: Path,
    times: int = 4,
    source_conf: Path | None = None,
    dest_conf: Path | None = None,
    scale_layout: int = 1,
) -> None:
    """Lengthen each flank by repeating its own pixels. No resample.

    Corners, the tile sample, and the center graphic are copied 1:1.
    """
    if not png.exists():
        print(f"skip {png.name} (missing)")
        return
    src_conf = source_conf or png.with_suffix(".conf")
    out_conf = dest_conf or src_conf
    if not src_conf.exists():
        print(f"skip {png.name} (no conf)")
        return
    text = src_conf.read_text(encoding="utf-8")
    if out_conf.exists() and "native flank length" in out_conf.read_text(encoding="utf-8"):
        print(f"skip {png.name} (already native flank length)")
        return

    sizes = [v * scale_layout for v in _gaps(text, "sizes")]
    flanks = [v * scale_layout for v in _gaps(text, "flanks")]
    centers = [v * scale_layout for v in _gaps(text, "centers")]
    L, R, T, B = sizes
    src = cairo.ImageSurface.create_from_png(str(png))
    w, h = src.get_width(), src.get_height()
    tile_w = (w - L - R) - 2 * flanks[0] - centers[0]
    tile_h = (h - T - B) - 2 * flanks[1] - centers[1]
    if min(tile_w, tile_h) < 1:
        raise SystemExit(f"{png.name}: tile sample collapsed ({tile_w}x{tile_h})")

    new_f = [v * times for v in flanks]
    new_w = L + new_f[0] + tile_w + centers[0] + new_f[0] + R
    new_h = T + new_f[1] + tile_h + centers[1] + new_f[1] + B
    dst = cairo.ImageSurface(cairo.FORMAT_ARGB32, new_w, new_h)
    cr = cairo.Context(dst)
    cr.set_operator(cairo.OPERATOR_CLEAR)
    cr.paint()
    cr.set_operator(cairo.OPERATOR_SOURCE)

    # Corners, 1:1.
    _blit(cr, src, 0, 0, L, T, 0, 0)
    _blit(cr, src, w - R, 0, R, T, new_w - R, 0)
    _blit(cr, src, w - R, h - B, R, B, new_w - R, new_h - B)
    _blit(cr, src, 0, h - B, L, B, 0, new_h - B)

    def edge(horizontal: bool, along0: int, thick: int, flank: int, center: int, tile: int, sx: int, sy: int, dx: int, dy: int, new_flank: int) -> None:
        if horizontal:
            _repeat(cr, src, sx, sy, flank, thick, dx, dy, times, True)
            _blit(cr, src, sx + flank, sy, tile, thick, dx + new_flank, dy)
            _blit(cr, src, sx + flank + tile, sy, center, thick, dx + new_flank + tile, dy)
            _repeat(cr, src, sx + flank + tile + center, sy, flank, thick, dx + new_flank + tile + center, dy, times, True)
        else:
            _repeat(cr, src, sx, sy, thick, flank, dx, dy, times, False)
            _blit(cr, src, sx, sy + flank, thick, tile, dx, dy + new_flank)
            _blit(cr, src, sx, sy + flank + tile, thick, center, dx, dy + new_flank + tile)
            _repeat(cr, src, sx, sy + flank + tile + center, thick, flank, dx, dy + new_flank + tile + center, times, False)

    edge(True, 0, T, flanks[0], centers[0], tile_w, L, 0, L, 0, new_f[0])
    edge(True, 0, B, flanks[2], centers[2], tile_w, L, h - B, L, new_h - B, new_f[2])
    edge(False, 0, L, flanks[3], centers[3], tile_h, 0, T, 0, T, new_f[3])
    edge(False, 0, R, flanks[1], centers[1], tile_h, w - R, T, new_w - R, T, new_f[1])

    dst.write_to_png(str(png))
    # Rewrite sizes that the layout scale changed, and the new flank lengths.
    lines = []
    if "native flank length" not in text:
        lines.append("# native flank length: each flank is its own pixels, repeated, not scaled")
    for line in text.splitlines():
        body = line.split("#", 1)[0]
        if "=" in body:
            key = body.split("=", 1)[0].strip()
            if key == "flanks":
                vals = ",".join(str(v) for v in new_f)
                lines.append(f"flanks = {vals}")
                continue
            if key == "sizes" and scale_layout != 1:
                vals = ",".join(str(v) for v in sizes)
                lines.append(f"sizes = {vals}")
                continue
            if key == "centers" and scale_layout != 1:
                vals = ",".join(str(v) for v in centers)
                lines.append(f"centers = {vals}")
                continue
            if key == "image":
                lines.append(f"image = {png.name}")
                continue
        lines.append(line)
    out_conf.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"expanded {png.name}  {w}x{h} -> {new_w}x{new_h} "
        f"flanks={','.join(str(v) for v in new_f)}"
    )


def _fill_repeat(
    cr: cairo.Context,
    src: cairo.ImageSurface,
    sx: int,
    sy: int,
    sw: int,
    sh: int,
    dx: int,
    dy: int,
    dest_w: int,
    dest_h: int,
    horizontal: bool,
) -> None:
    if sw <= 0 or sh <= 0 or dest_w <= 0 or dest_h <= 0:
        return
    if horizontal:
        x = 0
        while x < dest_w:
            w = min(sw, dest_w - x)
            _blit(cr, src, sx, sy, w, sh, dx + x, dy)
            x += w
    else:
        y = 0
        while y < dest_h:
            h = min(sh, dest_h - y)
            _blit(cr, src, sx, sy, sw, h, dx, dy + y)
            y += h


def widen_centers(png: Path, length: int = 400) -> None:
    """Set each center graphic to `length` pixels. Drawn once, not scaled.

    A shorter picture is copied 1:1 into the middle and the gap is filled
    with the tile sample. A longer picture is cropped from its middle.
    """
    conf = png.with_suffix(".conf")
    if not png.exists() or not conf.exists():
        print(f"skip {png.name} (missing)")
        return
    text = conf.read_text(encoding="utf-8")
    marker = f"center = {length}px"
    if marker in text.split("\n", 1)[0]:
        print(f"skip {png.name} ({marker})")
        return
    sizes = _gaps(text, "sizes")
    flanks = _gaps(text, "flanks")
    centers = _gaps(text, "centers")
    L, R, T, B = sizes
    src = cairo.ImageSurface.create_from_png(str(png))
    w, h = src.get_width(), src.get_height()
    tile_w = (w - L - R) - 2 * flanks[0] - centers[0]
    tile_h = (h - T - B) - 2 * flanks[1] - centers[1]
    if min(tile_w, tile_h) < 1:
        raise SystemExit(f"{png.name}: tile sample collapsed ({tile_w}x{tile_h})")
    new_cw = length
    new_ch = length
    if new_cw == centers[0] and new_ch == centers[1]:
        if not text.startswith(f"# {marker}"):
            conf.write_text(f"# {marker}\n" + text, encoding="utf-8")
        print(f"skip {png.name} (center already {length}px)")
        return

    new_w = L + flanks[0] + tile_w + new_cw + flanks[2] + R
    new_h = T + flanks[1] + tile_h + new_ch + flanks[3] + B
    dst = cairo.ImageSurface(cairo.FORMAT_ARGB32, new_w, new_h)
    cr = cairo.Context(dst)
    cr.set_operator(cairo.OPERATOR_CLEAR)
    cr.paint()
    cr.set_operator(cairo.OPERATOR_SOURCE)

    _blit(cr, src, 0, 0, L, T, 0, 0)
    _blit(cr, src, w - R, 0, R, T, new_w - R, 0)
    _blit(cr, src, w - R, h - B, R, B, new_w - R, new_h - B)
    _blit(cr, src, 0, h - B, L, B, 0, new_h - B)

    def place_h(thick: int, flank_a: int, flank_b: int, center: int, new_center: int, sy: int, dy: int) -> None:
        # flanks and the tile sample, 1:1
        _blit(cr, src, L, sy, flank_a, thick, L, dy)
        tile_sx = L + flank_a
        _blit(cr, src, tile_sx, sy, tile_w, thick, L + flank_a, dy)
        slot_x = L + flank_a + tile_w
        src_center = tile_sx + tile_w
        if new_center >= center:
            _fill_repeat(cr, src, tile_sx, sy, tile_w, thick, slot_x, dy, new_center, thick, True)
            _blit(cr, src, src_center, sy, center, thick, slot_x + (new_center - center) // 2, dy)
        else:
            crop = (center - new_center) // 2
            _blit(cr, src, src_center + crop, sy, new_center, thick, slot_x, dy)
        _blit(cr, src, src_center + center, sy, flank_b, thick, slot_x + new_center, dy)

    def place_v(thick: int, flank_a: int, flank_b: int, center: int, new_center: int, sx: int, dx: int) -> None:
        _blit(cr, src, sx, T, thick, flank_a, dx, T)
        tile_sy = T + flank_a
        _blit(cr, src, sx, tile_sy, thick, tile_h, dx, T + flank_a)
        slot_y = T + flank_a + tile_h
        src_center = tile_sy + tile_h
        if new_center >= center:
            _fill_repeat(cr, src, sx, tile_sy, thick, tile_h, dx, slot_y, thick, new_center, False)
            _blit(cr, src, sx, src_center, thick, center, dx, slot_y + (new_center - center) // 2)
        else:
            crop = (center - new_center) // 2
            _blit(cr, src, sx, src_center + crop, thick, new_center, dx, slot_y)
        _blit(cr, src, sx, src_center + center, thick, flank_b, dx, slot_y + new_center)

    place_h(T, flanks[0], flanks[0], centers[0], new_cw, 0, 0)
    place_h(B, flanks[2], flanks[2], centers[2], new_cw, h - B, new_h - B)
    place_v(L, flanks[3], flanks[3], centers[3], new_ch, 0, 0)
    place_v(R, flanks[1], flanks[1], centers[1], new_ch, w - R, new_w - R)

    dst.write_to_png(str(png))
    new_centers = [new_cw, new_ch, new_cw, new_ch]
    lines = [f"# center = {length}px"]
    for line in text.splitlines():
        body = line.split("#", 1)[0]
        if "=" in body and body.split("=", 1)[0].strip() == "centers":
            lines.append("centers = " + ",".join(str(v) for v in new_centers))
            continue
        lines.append(line)
    conf.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"set {png.name} centers {centers[0]} -> {new_cw}, "
        f"{w}x{h} -> {new_w}x{new_h}"
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for p in list(OUT.glob("*.png")) + list(OUT.glob("*.conf")):
        if p.name not in KEEP:
            p.unlink()

    # Flank is four of its old squares, painted at that size.
    # Center graphic is 400px long, painted at that size, drawn once.
    # (name, thickness, flank, tile, center, inset, smooth, fill, accent, style)
    specs = [
        ("medium-thick", 14, 128, 16, 400, 2, True, "#c62828", "#ffc107", "dots"),
        ("large-chunky", 16, 144, 20, 400, 2, False, "#37474f", "#ff6e40", "stripe"),
        ("xl-heavy", 20, 192, 24, 400, 3, False, "#4e342e", "#ffd54f", "corner_caps"),
        ("xxl-bold", 24, 224, 32, 400, 3, False, "#263238", "#ffab40", "solid"),
    ]

    for i, (name, thick, flank, tile, center, inset, smooth, fill, accent, style) in enumerate(specs):
        size = thick * 2 + flank * 2 + tile + center
        make_frame(
            OUT / f"{i+1:02d}-{name}.png",
            size=size,
            thickness=thick,
            center=center,
            flank=flank,
            fill=fill,
            accent=accent,
            style=style,
            inset_conf=inset,
            smooth=smooth,
        )

    write_square_reference()
    write_bond_frame()
    expand_native_flanks(
        OUT / "moria-1024.png",
        source_conf=OUT / "moria.conf",
        dest_conf=OUT / "moria-1024.conf",
        scale_layout=2,
    )
    expand_native_flanks(OUT / "moria.png")
    expand_native_flanks(OUT / "dwarf.png")
    for framed in ("dwarf.png", "moria.png", "moria-1024.png"):
        widen_centers(OUT / framed)
    write_gallery()

    print(f"\n{len(list(OUT.glob('*.png')))} PNGs in {OUT}")
    print("Pick:  ./pick.sh   or   ../use-border.sh 01")


def write_aspect_guide(cell: int = 40) -> None:
    """Labeled 21-patch at the aspect ratio pieces are drawn.

    Thickness is one square. On a wide window the top and bottom are longer
    than the left and right: flanks are 16 and 10 squares, centers are 40 and
    24. The tile stays one square. File order is flank, tile, center, flank.
    """
    h_flank, h_center = 16, 40
    v_flank, v_center = 10, 24
    cols = 1 + h_flank + 1 + h_center + h_flank + 1
    rows = 1 + v_flank + 1 + v_center + v_flank + 1
    width, height = cols * cell, rows * cell
    path = OUT / "00-21-aspect.png"
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    cr = cairo.Context(surface)
    cr.set_operator(cairo.OPERATOR_CLEAR)
    cr.paint()
    cr.set_operator(cairo.OPERATOR_OVER)

    role_color = {
        "corner": ("#ff8a80", "#b71c1c"),
        "flank": ("#ffe082", "#e65100"),
        "tile": ("#b9f6ca", "#1b5e20"),
        "center": ("#81d4fa", "#01579b"),
        "hole": ("#eceff1", "#455a64"),
    }

    def box(col: int, row: int, span_c: int, span_r: int, role: str, label: str) -> None:
        fill, stroke = role_color[role]
        x, y = col * cell, row * cell
        w, h = span_c * cell, span_r * cell
        cr.set_source_rgba(*rgba(fill, 0.92 if role != "hole" else 0.35))
        cr.rectangle(x, y, w, h)
        cr.fill()
        cr.set_source_rgba(*rgba(stroke))
        cr.set_line_width(3)
        cr.rectangle(x + 1.5, y + 1.5, max(1, w - 3), max(1, h - 3))
        cr.stroke()
        if not label:
            return
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(min(w, h) * (0.42 if len(label) <= 3 else 0.28))
        ext = cr.text_extents(label)
        cr.move_to(
            x + (w - ext.width) / 2 - ext.x_bearing,
            y + (h - ext.height) / 2 - ext.y_bearing,
        )
        cr.show_text(label)

    x_fl, x_tile = 1, 1 + h_flank
    x_ctr = x_tile + 1
    x_fl2 = x_ctr + h_center
    x_corner = x_fl2 + h_flank
    y_fl, y_tile = 1, 1 + v_flank
    y_ctr = y_tile + 1
    y_fl2 = y_ctr + v_center
    y_corner = y_fl2 + v_flank

    box(0, 0, 1, 1, "corner", "TL")
    box(x_fl, 0, h_flank, 1, "flank", "FL")
    box(x_tile, 0, 1, 1, "tile", "TILE")
    box(x_ctr, 0, h_center, 1, "center", "CTR")
    box(x_fl2, 0, h_flank, 1, "flank", "FL")
    box(x_corner, 0, 1, 1, "corner", "TR")

    box(x_corner, y_fl, 1, v_flank, "flank", "FL")
    box(x_corner, y_tile, 1, 1, "tile", "TILE")
    box(x_corner, y_ctr, 1, v_center, "center", "CTR")
    box(x_corner, y_fl2, 1, v_flank, "flank", "FL")

    box(0, y_corner, 1, 1, "corner", "BL")
    box(x_fl, y_corner, h_flank, 1, "flank", "FL")
    box(x_tile, y_corner, 1, 1, "tile", "TILE")
    box(x_ctr, y_corner, h_center, 1, "center", "CTR")
    box(x_fl2, y_corner, h_flank, 1, "flank", "FL")
    box(x_corner, y_corner, 1, 1, "corner", "BR")

    box(0, y_fl, 1, v_flank, "flank", "FL")
    box(0, y_tile, 1, 1, "tile", "TILE")
    box(0, y_ctr, 1, v_center, "center", "CTR")
    box(0, y_fl2, 1, v_flank, "flank", "FL")

    box(1, 1, cols - 2, rows - 2, "hole", "")

    thick = cell
    h_flank_px, h_center_px = h_flank * cell, h_center * cell
    v_flank_px, v_center_px = v_flank * cell, v_center * cell
    hole, hole_w, hole_h = cell, (cols - 2) * cell, (rows - 2) * cell
    cr.set_source_rgba(*rgba("#263238"))
    lines = [
        ("21-patch guide, drawn aspect", True, 28),
        (f"red corner {thick}×{thick}, the border thickness", False, 20),
        (f"amber flank, top/bottom {h_flank_px}×{thick}, sides {v_flank_px}×{thick}", False, 20),
        (f"green tile {thick}×{thick}, the repeat sample", False, 20),
        (f"blue center, top/bottom {h_center_px}×{thick}, sides {v_center_px}×{thick}", False, 20),
        ("same thickness as the corner, nothing stretched", False, 20),
        (f"image {width}×{height}", False, 20),
    ]
    measured = []
    for text, bold, size_px in lines:
        cr.select_font_face(
            "Sans",
            cairo.FONT_SLANT_NORMAL,
            cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL,
        )
        cr.set_font_size(size_px)
        measured.append((text, bold, size_px, cr.text_extents(text)))
    gap = 12
    block_h = sum(item[3].height for item in measured) + gap * (len(measured) - 1)
    y = hole + (hole_h - block_h) / 2
    for text, bold, size_px, ext in measured:
        cr.select_font_face(
            "Sans",
            cairo.FONT_SLANT_NORMAL,
            cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL,
        )
        cr.set_font_size(size_px)
        cr.move_to(hole + (hole_w - ext.width) / 2 - ext.x_bearing, y - ext.y_bearing)
        cr.show_text(text)
        y += ext.height + gap

    surface.write_to_png(str(path))
    path.with_suffix(".conf").write_text(
        f"""# Aspect guide. Thickness is one {thick}px square on every piece.
# Top/bottom flank {h_flank_px}px, center {h_center_px}px.
# Left/right flank {v_flank_px}px, center {v_center_px}px.
# Tile is one {thick}px square. Order: flank, tile, center, flank.
image = {path.name}
sizes = {thick},{thick},{thick},{thick}
flanks = {h_flank_px},{v_flank_px},{h_flank_px},{v_flank_px}
centers = {h_center_px},{v_center_px},{h_center_px},{v_center_px}
insets = 0,0,0,0
scale = {min(1.0, 10 / thick):.6f}
line = #43a047
smooth = false
blur = false
""",
        encoding="utf-8",
    )
    print(f"wrote {path.name}  ({width}x{height}, thickness {thick})")


def write_square_reference(cell: int = 80) -> None:
    """Patch map. Corner and tile sample are one square. Each flank is four
    squares long. Each center graphic is 400px long.

      TL | FL×4 | TILE | CTR×5 | FL×4 | TR
    """
    flank_cells = 4
    center_cells = 5  # 5 × 80px = 400px
    # corner + flank + tile + center + flank + corner
    n = 1 + flank_cells + 1 + center_cells + flank_cells + 1
    size = cell * n
    flank_px = cell * flank_cells
    center_px = cell * center_cells
    path = OUT / "00-21-squares.png"
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    cr = cairo.Context(surface)
    cr.set_operator(cairo.OPERATOR_CLEAR)
    cr.paint()
    cr.set_operator(cairo.OPERATOR_OVER)

    # role -> (fill, stroke)
    role_color = {
        "corner": ("#ff8a80", "#b71c1c"),
        "flank": ("#ffe082", "#e65100"),
        "tile": ("#b9f6ca", "#1b5e20"),
        "center": ("#81d4fa", "#01579b"),
        "hole": ("#eceff1", "#455a64"),
    }

    def box(col: int, row: int, cols: int, rows: int, role: str, label: str) -> None:
        fill, stroke = role_color[role]
        x, y = col * cell, row * cell
        w, h = cols * cell, rows * cell
        cr.set_source_rgba(*rgba(fill, 0.92 if role != "hole" else 0.35))
        cr.rectangle(x, y, w, h)
        cr.fill()
        cr.set_source_rgba(*rgba(stroke))
        cr.set_line_width(3)
        # Inset so neighboring strokes don't cover each other.
        cr.rectangle(x + 1.5, y + 1.5, w - 3, h - 3)
        cr.stroke()
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(cell * (0.28 if len(label) <= 3 else 0.20))
        ext = cr.text_extents(label)
        cr.move_to(
            x + (w - ext.width) / 2 - ext.x_bearing,
            y + (h - ext.height) / 2 - ext.y_bearing,
        )
        cr.show_text(label)

    tile_col = 1 + flank_cells
    center_col = tile_col + 1
    flank2_col = center_col + center_cells
    corner2 = flank2_col + flank_cells
    # Top row
    box(0, 0, 1, 1, "corner", "TL")
    box(1, 0, flank_cells, 1, "flank", "FL")
    box(tile_col, 0, 1, 1, "tile", "TILE")
    box(center_col, 0, center_cells, 1, "center", "CTR")
    box(flank2_col, 0, flank_cells, 1, "flank", "FL")
    box(corner2, 0, 1, 1, "corner", "TR")
    # Right column, top to bottom (between corners)
    box(corner2, 1, 1, flank_cells, "flank", "FL")
    box(corner2, tile_col, 1, 1, "tile", "TILE")
    box(corner2, center_col, 1, center_cells, "center", "CTR")
    box(corner2, flank2_col, 1, flank_cells, "flank", "FL")
    # Bottom row, left to right
    box(0, corner2, 1, 1, "corner", "BL")
    box(1, corner2, flank_cells, 1, "flank", "FL")
    box(tile_col, corner2, 1, 1, "tile", "TILE")
    box(center_col, corner2, center_cells, 1, "center", "CTR")
    box(flank2_col, corner2, flank_cells, 1, "flank", "FL")
    box(corner2, corner2, 1, 1, "corner", "BR")
    # Left column, top to bottom
    box(0, 1, 1, flank_cells, "flank", "FL")
    box(0, tile_col, 1, 1, "tile", "TILE")
    box(0, center_col, 1, center_cells, "center", "CTR")
    box(0, flank2_col, 1, flank_cells, "flank", "FL")
    # Unused middle
    hole_span_cells = n - 2
    box(1, 1, hole_span_cells, hole_span_cells, "hole", "")

    # Legend stays inside the unused square. That region is never drawn.
    hole = cell
    hole_span = hole_span_cells * cell
    cr.set_source_rgba(*rgba("#263238"))
    lines = [
        ("21 patches, native pixels", True, 0.22),
        ("red     corner, one square", False, 0.16),
        ("amber   flank, four squares long", False, 0.16),
        ("green   tile, repeats at this size", False, 0.16),
        ("blue    center, 400px, drawn once", False, 0.16),
        ("gray    middle, unused", False, 0.16),
        (f"flanks {flank_px}px, centers {center_px}px", False, 0.15),
    ]
    measured: list[tuple[str, bool, float, cairo.TextExtents]] = []
    for text, bold, rel in lines:
        cr.select_font_face(
            "Sans",
            cairo.FONT_SLANT_NORMAL,
            cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL,
        )
        cr.set_font_size(cell * rel)
        measured.append((text, bold, rel, cr.text_extents(text)))
    gap = cell * 0.10
    block_h = sum(item[3].height for item in measured) + gap * (len(measured) - 1)
    y = hole + (hole_span - block_h) / 2
    for text, bold, rel, ext in measured:
        cr.select_font_face(
            "Sans",
            cairo.FONT_SLANT_NORMAL,
            cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL,
        )
        cr.set_font_size(cell * rel)
        cr.move_to(
            hole + (hole_span - ext.width) / 2 - ext.x_bearing,
            y - ext.y_bearing,
        )
        cr.show_text(text)
        y += ext.height + gap

    surface.write_to_png(str(path))
    conf = path.with_suffix(".conf")
    conf.write_text(
        f"""# 21-patch map. Corner and tile are one {cell}px square.
# Each flank is {flank_px}px long (four squares).
# Each center is {center_px}px long, drawn once.
# Drawn at these pixel sizes. Nothing is stretched.
image = {path.name}
sizes = {cell},{cell},{cell},{cell}
flanks = {flank_px},{flank_px},{flank_px},{flank_px}
centers = {center_px},{center_px},{center_px},{center_px}
insets = 0,0,0,0
scale = {min(1.0, 10 / cell):.6f}
line = #43a047
smooth = false
blur = false
""",
        encoding="utf-8",
    )
    print(f"wrote {path.name}  ({size}x{size}, {cell}px squares)")


def write_bond_frame() -> None:
    """HUD frame. Each flank block is a square the size of the border thickness.

    No inner rails. Mid strip is [FLANK][TILE][CENTER][FLANK]. Tile and center
    stay empty so nothing repeats between the blocks.
    """
    thick = 40
    gap = 4
    # Blocks stay one border square. The flank slice that holds them is 4× longer.
    flank = (thick * 2 + gap) * 4
    tile = 8
    center = 400
    mid = flank + tile + center + flank
    size = thick * 2 + mid
    path = OUT / "05-bond.png"

    orange = rgba("#ff5714")
    white = rgba("#f4f5f7")

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    cr = cairo.Context(surface)
    cr.set_operator(cairo.OPERATOR_CLEAR)
    cr.paint()
    cr.set_operator(cairo.OPERATOR_OVER)
    cr.set_line_cap(cairo.LINE_CAP_BUTT)
    cr.set_line_join(cairo.LINE_JOIN_MITER)

    def block(x: float, y: float, color: tuple[float, float, float, float]) -> None:
        cr.set_source_rgba(*color)
        cr.rectangle(x, y, thick, thick)
        cr.fill()

    def hazard(x: float, y: float) -> None:
        cr.save()
        cr.rectangle(x, y, thick, thick)
        cr.clip()
        cr.set_source_rgba(*orange)
        cr.set_line_width(thick * 0.16)
        cr.set_line_cap(cairo.LINE_CAP_SQUARE)
        step = thick * 0.32
        t = -thick
        while t < thick * 2:
            cr.move_to(x + t, y + thick)
            cr.line_to(x + t + thick, y)
            cr.stroke()
            t += step
        cr.restore()

    def bracket(ox: float, oy: float, sx: float, sy: float) -> None:
        cr.save()
        cr.translate(ox, oy)
        cr.scale(sx, sy)
        cr.set_source_rgba(*orange)
        cr.set_line_width(7)
        cr.move_to(3.5, thick - 8)
        cr.line_to(3.5, 3.5)
        cr.line_to(thick - 8, 3.5)
        cr.stroke()
        cr.restore()

    bracket(0, 0, 1, 1)
    bracket(size, 0, -1, 1)
    bracket(size, size, -1, -1)
    bracket(0, size, 1, -1)

    # Hazard sits against the corner. White sits at the inner end of the flank.
    # Both blocks stay `thick` px, the native border square.
    hazard(thick, 0)
    block(thick + flank - thick, 0, white)
    right_flank_x = thick + flank + tile + center
    block(right_flank_x, 0, white)
    hazard(right_flank_x + flank - thick, 0)

    bot = size - thick
    hazard(thick, bot)
    block(thick + flank - thick, bot, white)
    block(right_flank_x, bot, white)
    hazard(right_flank_x + flank - thick, bot)

    hazard(0, thick)
    block(0, thick + flank - thick, white)
    low = size - thick - flank
    block(0, low, white)
    hazard(0, low + flank - thick)

    rx = size - thick
    hazard(rx, thick)
    block(rx, thick + flank - thick, white)
    block(rx, low, white)
    hazard(rx, low + flank - thick)

    surface.write_to_png(str(path))
    conf = path.with_suffix(".conf")
    conf.write_text(
        f"""# HUD frame. Mid strip = [FLANK {flank}px][TILE {tile}px][CENTER {center}px][FLANK {flank}px]
# Each color block is {thick}px, the full border thickness.
# Tile and center are empty, so no line runs between the blocks.
image = {path.name}
sizes = {thick},{thick},{thick},{thick}
flanks = {flank},{flank},{flank},{flank}
centers = {center},{center},{center},{center}
insets = 1,1,1,1
scale = {min(1.0, 10 / max(1, thick - 1)):.6f}
line = #ff5714
smooth = true
blur = false
""",
        encoding="utf-8",
    )
    print(
        f"wrote {path.name}  ({size}x{size} thick={thick} "
        f"flank={flank} tile={tile} center={center})"
    )


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "reference":
        OUT.mkdir(parents=True, exist_ok=True)
        write_square_reference()
    elif len(sys.argv) > 1 and sys.argv[1] == "bond":
        OUT.mkdir(parents=True, exist_ok=True)
        write_bond_frame()
    elif len(sys.argv) > 1 and sys.argv[1] == "gallery":
        OUT.mkdir(parents=True, exist_ok=True)
        write_gallery()
    elif len(sys.argv) > 1 and sys.argv[1] == "aspect":
        OUT.mkdir(parents=True, exist_ok=True)
        write_aspect_guide()
    else:
        main()
