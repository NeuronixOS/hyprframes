#!/usr/bin/env python3
"""Generate 21-patch PNG frames for ImageBorders.

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

        cr.set_source_rgba(*rgba(accent))
        diamond(cr, cx0 + Wc / 2, T / 2, Wc * 0.46, T * 0.40)
        diamond(cr, cx0 + Wc / 2, size - T / 2, Wc * 0.46, T * 0.40)
        diamond(cr, L / 2, cy0 + Hc / 2, L * 0.40, Hc * 0.46)
        diamond(cr, size - R / 2, cy0 + Hc / 2, R * 0.40, Hc * 0.46)

    # Corner caps
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
image = {path}
sizes = {thickness},{thickness},{thickness},{thickness}
flanks = {flank},{flank},{flank},{flank}
centers = {center},{center},{center},{center}
insets = {inset_conf},{inset_conf},{inset_conf},{inset_conf}
scale = 1
smooth = {"true" if smooth else "false"}
blur = false
""",
        encoding="utf-8",
    )
    print(
        f"wrote {path.name}  ({size}x{size} thick={thickness} "
        f"flank={flank} tile={tile} center={center} {style})"
    )


# Hand-made frames the generator must not delete.
KEEP = {
    "dwarf.png",
    "dwarf.conf",
    "00-21-squares.png",
    "00-21-squares.conf",
    "05-bond.png",
    "05-bond.conf",
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for p in list(OUT.glob("*.png")) + list(OUT.glob("*.conf")):
        if p.name not in KEEP:
            p.unlink()

    # Heavy/thick only. center is the wide middle sample; flank is the
    # extra slice on each side of every corner.
    # (name, size, thickness, flank, center, inset, smooth, fill, accent, style)
    specs = [
        ("medium-thick", 136, 14, 32, 28, 2, True, "#c62828", "#ffc107", "dots"),
        ("large-chunky", 160, 16, 36, 36, 2, False, "#37474f", "#ff6e40", "stripe"),
        ("xl-heavy", 208, 20, 48, 48, 3, False, "#4e342e", "#ffd54f", "corner_caps"),
        ("xxl-bold", 256, 24, 56, 64, 3, False, "#263238", "#ffab40", "solid"),
    ]

    for i, (name, size, thick, flank, center, inset, smooth, fill, accent, style) in enumerate(specs):
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

    print(f"\n{len(list(OUT.glob('*.png')))} PNGs in {OUT}")
    print("Pick:  ./pick.sh   or   ../use-border.sh 01")


def write_square_reference(cell: int = 80) -> None:
    """One square outline per slice, including the unused middle.

    Layout (each cell is `cell` px, so every patch is a square):

      TL | FL | TILE | CTR | FL | TR
      FL |         unused          | FL
    TILE |                         | TILE
     CTR |                         | CTR
      FL |                         | FL
      BL | FL | TILE | CTR | FL | BR
    """
    n = 6  # thickness + flank + tile + center + flank + thickness
    size = cell * n
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

    def box(col: int, row: int, span: int, role: str, label: str) -> None:
        fill, stroke = role_color[role]
        x, y = col * cell, row * cell
        w = h = span * cell
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

    # Top row
    box(0, 0, 1, "corner", "TL")
    box(1, 0, 1, "flank", "FL")
    box(2, 0, 1, "tile", "TILE")
    box(3, 0, 1, "center", "CTR")
    box(4, 0, 1, "flank", "FL")
    box(5, 0, 1, "corner", "TR")
    # Right column, top to bottom (between corners)
    box(5, 1, 1, "flank", "FL")
    box(5, 2, 1, "tile", "TILE")
    box(5, 3, 1, "center", "CTR")
    box(5, 4, 1, "flank", "FL")
    # Bottom row, left to right
    box(0, 5, 1, "corner", "BL")
    box(1, 5, 1, "flank", "FL")
    box(2, 5, 1, "tile", "TILE")
    box(3, 5, 1, "center", "CTR")
    box(4, 5, 1, "flank", "FL")
    box(5, 5, 1, "corner", "BR")
    # Left column, top to bottom
    box(0, 1, 1, "flank", "FL")
    box(0, 2, 1, "tile", "TILE")
    box(0, 3, 1, "center", "CTR")
    box(0, 4, 1, "flank", "FL")
    # Unused middle is one square (4×4 cells)
    box(1, 1, 4, "hole", "")

    # Legend stays inside the unused square. That region is never drawn.
    hole = cell
    hole_span = 4 * cell
    cr.set_source_rgba(*rgba("#263238"))
    lines = [
        ("21 squares", True, 0.26),
        ("red     corner, drawn once", False, 0.18),
        ("amber   flank, drawn once", False, 0.18),
        ("green   tile, repeats", False, 0.18),
        ("blue    center, repeats", False, 0.18),
        ("        across half the side", False, 0.16),
        ("gray    middle, unused", False, 0.18),
        (f"{cell}px squares, {size}px frame", False, 0.16),
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
        f"""# 21-patch square grid. Every slice is one {cell}px square.
# Top/bottom strip: [FL][TILE][CTR][FL]
# Left/right strip: [FL][TILE][CTR][FL]
# Middle {4 * cell}px square is never drawn.
image = {path}
sizes = {cell},{cell},{cell},{cell}
flanks = {cell},{cell},{cell},{cell}
centers = {cell},{cell},{cell},{cell}
insets = 0,0,0,0
scale = 0.3
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
    flank = thick * 2 + gap
    tile = 8
    center = 8
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

    # Top: hazard toward the corner, white block inward. Both fill the border.
    hazard(thick, 0)
    block(thick + thick + gap, 0, white)
    right_flank_x = thick + flank + tile + center
    block(right_flank_x, 0, white)
    hazard(right_flank_x + thick + gap, 0)

    # Bottom
    bot = size - thick
    hazard(thick, bot)
    block(thick + thick + gap, bot, white)
    block(right_flank_x, bot, white)
    hazard(right_flank_x + thick + gap, bot)

    # Left: hazard beside the corner, white block further along the edge.
    hazard(0, thick)
    block(0, thick + thick + gap, white)
    low = size - thick - flank
    block(0, low, white)
    hazard(0, low + thick + gap)

    # Right
    rx = size - thick
    hazard(rx, thick)
    block(rx, thick + thick + gap, white)
    block(rx, low, white)
    hazard(rx, low + thick + gap)

    surface.write_to_png(str(path))
    conf = path.with_suffix(".conf")
    conf.write_text(
        f"""# HUD frame. Mid strip = [FLANK {flank}px][TILE {tile}px][CENTER {center}px][FLANK {flank}px]
# Each color block is {thick}px, the full border thickness.
# Tile and center are empty, so no line runs between the blocks.
image = {path}
sizes = {thick},{thick},{thick},{thick}
flanks = {flank},{flank},{flank},{flank}
centers = {center},{center},{center},{center}
insets = 1,1,1,1
scale = 0.55
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
    else:
        main()
