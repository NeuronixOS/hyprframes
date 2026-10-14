#!/usr/bin/env python3
"""Cut the generated frame pictures into 21-patch PNGs.

Pixels are copied, not redrawn. Each edge becomes:

  [corner][flank, drawn once][tile, the repeat][center, drawn once][flank][corner]

The black around the frame and the hole become transparent.
"""
from __future__ import annotations

import math
from collections import deque
from pathlib import Path

import cairo
import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf

OUT = Path(__file__).resolve().parent

DARK = 4


def load(path: Path) -> tuple[int, int, int, int, bytes]:
    pb = GdkPixbuf.Pixbuf.new_from_file(str(path))
    if pb.get_n_channels() not in (3, 4):
        raise SystemExit(f"{path.name}: unsupported channels")
    return (
        pb.get_width(),
        pb.get_height(),
        pb.get_rowstride(),
        pb.get_n_channels(),
        bytes(pb.get_pixels()),
    )


def classify(w: int, h: int, rs: int, n: int, src: bytes) -> bytearray:
    """0 content, 1 outside, 2 hole."""
    dark = bytearray(w * h)
    for y in range(h):
        row = y * rs
        base = y * w
        for x in range(w):
            i = row + x * n
            if src[i] <= DARK and src[i + 1] <= DARK and src[i + 2] <= DARK:
                dark[base + x] = 1

    kind = bytearray(w * h)

    def flood(sx: int, sy: int, mark: int) -> None:
        if not (0 <= sx < w and 0 <= sy < h):
            return
        start = sy * w + sx
        if not dark[start] or kind[start]:
            return
        q = deque([start])
        kind[start] = mark
        while q:
            i = q.popleft()
            x, y = i % w, i // w
            if x > 0:
                j = i - 1
                if dark[j] and not kind[j]:
                    kind[j] = mark
                    q.append(j)
            if x + 1 < w:
                j = i + 1
                if dark[j] and not kind[j]:
                    kind[j] = mark
                    q.append(j)
            if y > 0:
                j = i - w
                if dark[j] and not kind[j]:
                    kind[j] = mark
                    q.append(j)
            if y + 1 < h:
                j = i + w
                if dark[j] and not kind[j]:
                    kind[j] = mark
                    q.append(j)

    flood(0, 0, 1)
    flood(w - 1, 0, 1)
    flood(0, h - 1, 1)
    flood(w - 1, h - 1, 1)
    flood(w // 2, h // 2, 2)

    # Drop the jpeg fringe on the hole and the outside.
    extra = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if kind[i]:
                continue
            si = y * rs + x * n
            if max(src[si], src[si + 1], src[si + 2]) > 28:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                xx, yy = x + dx, y + dy
                if 0 <= xx < w and 0 <= yy < h and kind[yy * w + xx] in (1, 2):
                    extra[i] = kind[yy * w + xx]
                    break
    for i, m in enumerate(extra):
        if m:
            kind[i] = m
    return kind


def spans(w: int, h: int, kind: bytearray) -> tuple[list[int], list[int], list[int], list[int]]:
    """Per row: hole left, hole right, content left, content right. -1 if none."""
    hole_l = [-1] * h
    hole_r = [-1] * h
    cont_l = [-1] * h
    cont_r = [-1] * h
    for y in range(h):
        base = y * w
        for x in range(w):
            k = kind[base + x]
            if k == 2:
                if hole_l[y] < 0:
                    hole_l[y] = x
                hole_r[y] = x
            elif k == 0:
                if cont_l[y] < 0:
                    cont_l[y] = x
                cont_r[y] = x
    return hole_l, hole_r, cont_l, cont_r


def side_thickness(hole_at: list[int], outer_at: list[int], along: range) -> tuple[int, int, list[int]]:
    """Return (median rail, band, thickness per index).

    The band is a high percentile, not the single deepest column. A leaf gap
    or a jpeg speckle would otherwise swallow the whole edge.
    """
    thick: list[int] = []
    for i in along:
        if hole_at[i] < 0 or outer_at[i] < 0:
            thick.append(0)
            continue
        thick.append(max(0, hole_at[i] - outer_at[i]))
    nz = [t for t in thick if t > 0]
    if not nz:
        raise SystemExit("no frame band")
    nz.sort()
    med = nz[len(nz) // 2]
    band = nz[min(len(nz) - 1, int((len(nz) - 1) * 0.92))]
    return med, band, thick


def bulge_width(thick: list[int], rail: int) -> int:
    if not thick:
        return 0
    limit = rail + max(12, int(rail * 0.15))
    mid = len(thick) // 2
    # Walk out from the middle while the band is deeper than the rail.
    if thick[mid] < limit and thick[min(len(thick) - 1, mid + 1)] < limit:
        return 0
    a = mid
    while a > 0 and thick[a - 1] >= limit:
        a -= 1
    b = mid
    while b + 1 < len(thick) and thick[b + 1] >= limit:
        b += 1
    # Ignore a bulge that is really the whole edge.
    width = b - a + 1
    if width > len(thick) * 0.85:
        return 0
    return width


def best_period(cols: list[tuple[int, int, int]], want: int) -> int:
    n = len(cols)
    if n < 8:
        return max(1, n)
    lo = max(8, min(want // 2, n // 2))
    hi = max(lo, min(n - 1, max(want * 2, lo)))
    best_p, best_s = lo, None
    for p in range(lo, hi + 1):
        err = 0
        count = 0
        step = max(1, (n - p) // 80)
        for i in range(0, n - p, step):
            a, b = cols[i], cols[i + p]
            err += abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])
            count += 1
        if not count:
            continue
        score = err / count
        # Prefer a period near one border square when the match is close.
        score += abs(p - want) * 0.15
        if best_s is None or score < best_s:
            best_s = score
            best_p = p
    return best_p


def column_colors(
    src: bytes, rs: int, nch: int, kind: bytearray, w: int, x0: int, x1: int, y0: int, y1: int
) -> list[tuple[int, int, int]]:
    cols = []
    for x in range(x0, x1):
        r = g = b = c = 0
        for y in range(y0, y1):
            if kind[y * w + x] != 0:
                continue
            i = y * rs + x * nch
            r += src[i]
            g += src[i + 1]
            b += src[i + 2]
            c += 1
        if c:
            cols.append((r // c, g // c, b // c))
        else:
            cols.append((0, 0, 0))
    return cols


def row_colors(
    src: bytes, rs: int, nch: int, kind: bytearray, w: int, x0: int, x1: int, y0: int, y1: int
) -> list[tuple[int, int, int]]:
    rows = []
    for y in range(y0, y1):
        r = g = b = c = 0
        base = y * w
        for x in range(x0, x1):
            if kind[base + x] != 0:
                continue
            i = y * rs + x * nch
            r += src[i]
            g += src[i + 1]
            b += src[i + 2]
            c += 1
        if c:
            rows.append((r // c, g // c, b // c))
        else:
            rows.append((0, 0, 0))
    return rows


def pack(mid: int, thick: int, ornament: int) -> tuple[int, int, int]:
    """Flank length, center length, and the gap the tile is sampled from.

    The tile keeps a real stretch of the rail. Flanks take what is left,
    up to four times the band, and the center stays one piece around 400px.
    """
    tile_keep = max(48, min(96, max(48, thick // 3)))
    center = 400
    if ornament > 420:
        center = min(ornament + 8, 640)
    if center + tile_keep * 2 + 32 > mid:
        center = max(tile_keep, (mid - tile_keep * 2) // 2)
    flank = max(8, (mid - center - tile_keep * 2) // 2)
    flank = min(flank, 4 * thick)
    gap = (mid - center) // 2 - flank
    return flank, center, max(tile_keep // 2, gap)


def blit(
    buf,
    stride: int,
    src: bytes,
    rs: int,
    nch: int,
    kind: bytearray,
    sw: int,
    sx: int,
    sy: int,
    dx: int,
    dy: int,
    cw: int,
    ch: int,
) -> None:
    for yy in range(ch):
        srow = (sy + yy) * rs
        krow = (sy + yy) * sw
        drow = (dy + yy) * stride
        for xx in range(cw):
            di = drow + (dx + xx) * 4
            if kind[krow + sx + xx] != 0:
                buf[di : di + 4] = b"\x00\x00\x00\x00"
                continue
            si = srow + (sx + xx) * nch
            r, g, b = src[si], src[si + 1], src[si + 2]
            buf[di] = b
            buf[di + 1] = g
            buf[di + 2] = r
            buf[di + 3] = 255


def map_one(path: Path, stem: str) -> None:
    path = path.resolve()
    w, h, rs, nch, src = load(path)
    kind = classify(w, h, rs, nch, src)
    hole_l, hole_r, cont_l, cont_r = spans(w, h, kind)
    for y in range(h):
        if hole_l[y] < 0 or hole_r[y] - hole_l[y] < w * 0.35:
            hole_l[y] = -1
            hole_r[y] = -1

    # Column spans for the horizontal edges.
    hole_t = [-1] * w
    hole_b = [-1] * w
    cont_t = [-1] * w
    cont_b = [-1] * w
    for y in range(h):
        base = y * w
        for x in range(w):
            k = kind[base + x]
            if k == 2:
                if hole_t[x] < 0:
                    hole_t[x] = y
                hole_b[x] = y
            elif k == 0:
                if cont_t[x] < 0:
                    cont_t[x] = y
                cont_b[x] = y
    for x in range(w):
        if hole_t[x] < 0 or hole_b[x] - hole_t[x] < h * 0.35:
            hole_t[x] = -1
            hole_b[x] = -1

    rows = range(h)
    cols = range(w)
    left_med, left_max, left_prof = side_thickness(hole_l, cont_l, rows)
    right_hole_from_right = [w - 1 - hole_r[y] if hole_r[y] >= 0 else -1 for y in rows]
    right_outer_from_right = [w - 1 - cont_r[y] if cont_r[y] >= 0 else -1 for y in rows]
    right_med, right_max, right_prof = side_thickness(right_hole_from_right, right_outer_from_right, rows)
    top_med, top_max, top_prof = side_thickness(hole_t, cont_t, cols)
    bot_hole_from_bot = [h - 1 - hole_b[x] if hole_b[x] >= 0 else -1 for x in cols]
    bot_outer_from_bot = [h - 1 - cont_b[x] if cont_b[x] >= 0 else -1 for x in cols]
    bot_med, bot_max, bot_prof = side_thickness(bot_hole_from_bot, bot_outer_from_bot, cols)

    L, R, T, B = left_max, right_max, top_max, bot_max
    # Content box the bands are measured from.
    ys = [i for i, v in enumerate(cont_l) if v >= 0]
    xs = [i for i, v in enumerate(cont_t) if v >= 0]
    minx, maxx = min(cont_l[y] for y in ys), max(cont_r[y] for y in ys)
    miny, maxy = min(cont_t[x] for x in xs), max(cont_b[x] for x in xs)
    # Inclusive max -> half-open end.
    maxx += 1
    maxy += 1

    src_mid_w = (maxx - minx) - L - R
    src_mid_h = (maxy - miny) - T - B
    if src_mid_w < 32 or src_mid_h < 32:
        raise SystemExit(f"{stem}: frame band ate the edge ({src_mid_w}x{src_mid_h})")

    top_orn = bulge_width(top_prof[minx + L : maxx - R], top_med)
    bot_orn = bulge_width(bot_prof[minx + L : maxx - R], bot_med)
    left_orn = bulge_width(left_prof[miny + T : maxy - B], left_med)
    right_orn = bulge_width(right_prof[miny + T : maxy - B], right_med)

    f_top, c_top, gap_top = pack(src_mid_w, T, top_orn)
    f_bot, c_bot, gap_bot = pack(src_mid_w, B, bot_orn)
    f_left, c_left, gap_left = pack(src_mid_h, L, left_orn)
    f_right, c_right, gap_right = pack(src_mid_h, R, right_orn)

    # Tile period from the rail between the flank and the center.
    def tile_w(gap: int, thick: int, x0: int, y0: int, y1: int) -> int:
        if gap < 8:
            return max(1, gap)
        cols_c = column_colors(src, rs, nch, kind, w, x0, x0 + gap, y0, y1)
        return min(gap, best_period(cols_c, max(8, min(thick, gap))))

    def tile_h(gap: int, thick: int, y0: int, x0: int, x1: int) -> int:
        if gap < 8:
            return max(1, gap)
        rows_c = row_colors(src, rs, nch, kind, w, x0, x1, y0, y0 + gap)
        return min(gap, best_period(rows_c, max(8, min(thick, gap))))

    top_x0 = minx + L
    left_y0 = miny + T

    tw = tile_w(gap_top, T, top_x0 + f_top, miny, miny + T)
    bw = tile_w(gap_bot, B, top_x0 + f_bot, maxy - B, maxy)
    lh = tile_h(gap_left, L, left_y0 + f_left, minx, minx + L)
    rh = tile_h(gap_right, R, left_y0 + f_right, maxx - R, maxx)

    def shrink_to(flank: int, tile: int, center: int, mid_out: int) -> tuple[int, int, int]:
        """Shorten flanks so this edge matches the other. The tile period stays."""
        extra = 2 * flank + tile + center - mid_out
        if extra > 0:
            take = min(extra, max(0, (flank - 8) * 2))
            flank -= take // 2
            extra -= (take // 2) * 2
            if extra > 0:
                center = max(16, center - extra)
        span = 2 * flank + tile + center
        if span != mid_out and center + (mid_out - span) > 0:
            center += mid_out - span
        return flank, tile, center

    mid_w = min(2 * f_top + tw + c_top, 2 * f_bot + bw + c_bot)
    mid_h = min(2 * f_left + lh + c_left, 2 * f_right + rh + c_right)
    f_top, tw, c_top = shrink_to(f_top, tw, c_top, mid_w)
    f_bot, bw, c_bot = shrink_to(f_bot, bw, c_bot, mid_w)
    f_left, lh, c_left = shrink_to(f_left, lh, c_left, mid_h)
    f_right, rh, c_right = shrink_to(f_right, rh, c_right, mid_h)
    width = L + mid_w + R
    height = T + mid_h + B

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    buf = surface.get_data()
    stride = surface.get_stride()

    def copy(sx: int, sy: int, dx: int, dy: int, cw: int, ch: int) -> None:
        sx = max(0, min(sx, w - 1))
        sy = max(0, min(sy, h - 1))
        cw = max(0, min(cw, w - sx, width - dx))
        ch = max(0, min(ch, h - sy, height - dy))
        blit(buf, stride, src, rs, nch, kind, w, sx, sy, dx, dy, cw, ch)

    # Corners, exact source blocks.
    copy(minx, miny, 0, 0, L, T)
    copy(maxx - R, miny, width - R, 0, R, T)
    copy(maxx - R, maxy - B, width - R, height - B, R, B)
    copy(minx, maxy - B, 0, height - B, L, B)

    # Top: flank, one tile period, center, flank. Source mid is not the output mid.
    copy(top_x0, miny, L, 0, f_top, T)
    copy(top_x0 + f_top, miny, L + f_top, 0, tw, T)
    copy(top_x0 + (src_mid_w - c_top) // 2, miny, L + f_top + tw, 0, c_top, T)
    copy(top_x0 + src_mid_w - f_top, miny, L + f_top + tw + c_top, 0, f_top, T)

    # Bottom.
    by = maxy - B
    copy(top_x0, by, L, height - B, f_bot, B)
    copy(top_x0 + f_bot, by, L + f_bot, height - B, bw, B)
    copy(top_x0 + (src_mid_w - c_bot) // 2, by, L + f_bot + bw, height - B, c_bot, B)
    copy(top_x0 + src_mid_w - f_bot, by, L + f_bot + bw + c_bot, height - B, f_bot, B)

    # Left.
    copy(minx, left_y0, 0, T, L, f_left)
    copy(minx, left_y0 + f_left, 0, T + f_left, L, lh)
    copy(minx, left_y0 + (src_mid_h - c_left) // 2, 0, T + f_left + lh, L, c_left)
    copy(minx, left_y0 + src_mid_h - f_left, 0, T + f_left + lh + c_left, L, f_left)

    # Right.
    rx = maxx - R
    copy(rx, left_y0, width - R, T, R, f_right)
    copy(rx, left_y0 + f_right, width - R, T + f_right, R, rh)
    copy(rx, left_y0 + (src_mid_h - c_right) // 2, width - R, T + f_right + rh, R, c_right)
    copy(rx, left_y0 + src_mid_h - f_right, width - R, T + f_right + rh + c_right, R, f_right)

    surface.mark_dirty()
    png = OUT / f"{stem}.png"
    surface.write_to_png(str(png))

    peak = max(L, R, T, B)
    # The file stays at the source pixel size. Scale keeps the band at most
    # 10px wide on a window. Center length is still the PNG length.
    scale = 1.0 if peak <= 10 else math.floor((10 / peak) * 1_000_000) / 1_000_000
    conf = png.with_suffix(".conf")
    conf.write_text(
        f"""# 21-patch mapped from {path.name}. Pixels copied, not redrawn.
# Top  [FLANK {f_top}][TILE {tw}][CENTER {c_top}][FLANK {f_top}]
# Right [FLANK {f_right}][TILE {rh}][CENTER {c_right}][FLANK {f_right}]
# Bottom [FLANK {f_bot}][TILE {bw}][CENTER {c_bot}][FLANK {f_bot}]
# Left [FLANK {f_left}][TILE {lh}][CENTER {c_left}][FLANK {f_left}]
image = {png.name}
sizes = {L},{R},{T},{B}
flanks = {f_top},{f_right},{f_bot},{f_left}
centers = {c_top},{c_right},{c_bot},{c_left}
insets = 0,0,0,0
scale = {scale}
line = #c9a36a
smooth = true
blur = false
""",
        encoding="utf-8",
    )
    print(
        f"{stem}: {width}x{height} sizes={L},{R},{T},{B} "
        f"flanks={f_top},{f_right},{f_bot},{f_left} "
        f"tiles={tw},{rh},{bw},{lh} centers={c_top},{c_right},{c_bot},{c_left} "
        f"scale={scale} rail={left_med},{right_med},{top_med},{bot_med}"
    )


def main() -> None:
    import sys

    if len(sys.argv) < 2:
        print(
            f"usage: {Path(sys.argv[0]).name} <frame-image> [output-stem …]",
            file=sys.stderr,
        )
        print(
            "  Cuts a rectangular frame photo into a 21-patch PNG + .conf "
            "beside this script.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    path = Path(sys.argv[1])
    if not path.is_file():
        raise SystemExit(f"missing image: {path}")
    stem = sys.argv[2] if len(sys.argv) > 2 else path.stem
    map_one(path, stem)


if __name__ == "__main__":
    main()
