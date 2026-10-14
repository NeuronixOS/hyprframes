#!/usr/bin/env python3
"""Quick hyprframes tester: list PNGs here, click one to apply + reload."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GdkPixbuf, GLib, Gtk, Pango

BDIR = Path(__file__).resolve().parent
ROOT = BDIR.parent
USE = ROOT / "use-border.sh"
THUMB = 96


def pngs() -> list[Path]:
    return sorted(BDIR.glob("*.png"), key=lambda p: p.name.lower())


def apply_border(path: Path) -> str:
    stem = path.stem
    if USE.is_file():
        r = subprocess.run(
            [str(USE), stem],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode != 0:
            return f"FAILED ({r.returncode})\n{out.strip()}"
        return out.strip() or f"applied {stem}"
    # Fallback without use-border.sh
    conf = Path.home() / ".config/hypr/hyprframes.conf"
    companion = path.with_suffix(".conf")
    conf.parent.mkdir(parents=True, exist_ok=True)
    if companion.is_file():
        text = companion.read_text(encoding="utf-8")
        lines = []
        replaced = False
        for line in text.splitlines():
            if line.lstrip().startswith("image"):
                lines.append(f"image = {path.resolve()}")
                replaced = True
            else:
                lines.append(line)
        if not replaced:
            lines.insert(0, f"image = {path.resolve()}")
        conf.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        conf.write_text(
            f"image = {path.resolve()}\nsizes = 5,5,5,5\ninsets = 1,1,1,1\n"
            "scale = 1\nsmooth = true\nblur = false\n",
            encoding="utf-8",
        )
    subprocess.run(["hyprctl", "dispatch", "hyprframesreload"], check=False)
    return f"applied {stem}"


class BorderPicker(Gtk.Window):
    def __init__(self) -> None:
        super().__init__(title="hyprframes — pick a frame")
        self.set_default_size(720, 560)
        self.set_border_width(10)
        self.connect("destroy", Gtk.main_quit)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.add(vbox)

        head = Gtk.Label()
        head.set_markup(
            "<b>hyprframes test</b> — click a PNG to apply "
            "<tt>hyprframesreload</tt>"
        )
        head.set_xalign(0)
        vbox.pack_start(head, False, False, 0)

        self.status = Gtk.Label(label="Select a border…")
        self.status.set_xalign(0)
        self.status.set_ellipsize(Pango.EllipsizeMode.END)
        vbox.pack_start(self.status, False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        vbox.pack_start(scroll, True, True, 0)

        self.store = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str)  # thumb, name, path
        self.view = Gtk.IconView.new_with_model(self.store)
        self.view.set_pixbuf_column(0)
        self.view.set_text_column(1)
        self.view.set_item_width(THUMB + 36)
        self.view.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.view.connect("item-activated", self._on_activated)
        self.view.connect("selection-changed", self._on_selection)
        scroll.add(self.view)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        vbox.pack_start(btn_row, False, False, 0)

        apply_btn = Gtk.Button.new_with_label("Apply selected")
        apply_btn.connect("clicked", lambda *_: self._apply_selected())
        btn_row.pack_start(apply_btn, False, False, 0)

        reload_btn = Gtk.Button.new_with_label("Reload current")
        reload_btn.connect("clicked", self._reload_only)
        btn_row.pack_start(reload_btn, False, False, 0)

        refresh_btn = Gtk.Button.new_with_label("Refresh list")
        refresh_btn.connect("clicked", lambda *_: self._fill())
        btn_row.pack_start(refresh_btn, False, False, 0)

        gen_btn = Gtk.Button.new_with_label("Regenerate PNGs")
        gen_btn.connect("clicked", self._regen)
        btn_row.pack_start(gen_btn, False, False, 0)

        close_btn = Gtk.Button.new_with_label("Close")
        close_btn.connect("clicked", lambda *_: self.destroy())
        btn_row.pack_end(close_btn, False, False, 0)

        self._fill()

    def _fill(self) -> None:
        self.store.clear()
        items = pngs()
        if not items:
            self.status.set_text("No PNGs — run generate.py")
            return
        for p in items:
            bg = GdkPixbuf.Pixbuf.new(
                GdkPixbuf.Colorspace.RGB, True, 8, THUMB, THUMB
            )
            bg.fill(0xE8E8E8FF)
            try:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    str(p), THUMB - 8, THUMB - 8, True
                )
                x = max(0, (THUMB - pb.get_width()) // 2)
                y = max(0, (THUMB - pb.get_height()) // 2)
                pb.composite(
                    bg,
                    x,
                    y,
                    pb.get_width(),
                    pb.get_height(),
                    float(x),
                    float(y),
                    1.0,
                    1.0,
                    GdkPixbuf.InterpType.NEAREST,
                    255,
                )
            except GLib.Error:
                pass
            self.store.append([bg, p.stem, str(p)])
        self.status.set_text(f"{len(items)} borders in {BDIR}")

    def _selected_path(self) -> Path | None:
        paths = self.view.get_selected_items()
        if not paths:
            return None
        it = self.store.get_iter(paths[0])
        return Path(self.store.get_value(it, 2))

    def _on_selection(self, *_args) -> None:
        p = self._selected_path()
        if p:
            self.status.set_text(f"Selected {p.name} (double-click or Apply)")

    def _on_activated(self, _view, _path) -> None:
        self._apply_selected()

    def _apply_selected(self) -> None:
        p = self._selected_path()
        if not p:
            self.status.set_text("Nothing selected")
            return
        self.status.set_text(f"Applying {p.name}…")
        while Gtk.events_pending():
            Gtk.main_iteration()
        msg = apply_border(p)
        self.status.set_text(msg.replace("\n", " | ")[:200])

    def _reload_only(self, *_args) -> None:
        r = subprocess.run(
            ["hyprctl", "dispatch", "hyprframesreload"],
            capture_output=True,
            text=True,
        )
        self.status.set_text(
            f"hyprframesreload → {(r.stdout or r.stderr or 'ok').strip()}"
        )

    def _regen(self, *_args) -> None:
        gen = BDIR / "generate.py"
        if not gen.is_file():
            self.status.set_text("generate.py missing")
            return
        self.status.set_text("Regenerating…")
        while Gtk.events_pending():
            Gtk.main_iteration()
        r = subprocess.run(
            [sys.executable, str(gen)],
            cwd=str(BDIR),
            capture_output=True,
            text=True,
        )
        self._fill()
        self.status.set_text(
            "Regenerated" if r.returncode == 0 else f"generate failed: {r.stderr[-120:]}"
        )


def main() -> None:
    # Prefer Wayland if Hyprland is up
    os.environ.setdefault("GDK_BACKEND", "wayland")
    win = BorderPicker()
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
