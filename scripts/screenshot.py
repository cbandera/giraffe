#!/usr/bin/env python3
"""Render the main window with synthetic example data to docs/screenshot.png."""
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Graphene", "1.0")
from gi.repository import GLib, Graphene, Gtk

import giraffe.app as app_mod
from giraffe import extract

SAMPLE = """Muster Sanitär GmbH
Rechnung Nr. 2024-0815
Rechnungsbetrag 119,00 EUR
Kontoinhaber: Muster Sanitär GmbH
IBAN: DE89 3704 0044 0532 0130 00  BIC: COBADEFFXXX
"""

out = sys.argv[1] if len(sys.argv) > 1 else "docs/screenshot.png"
app_mod.APP_ID = "io.github.giraffe.GiraffeScreenshot"
app = app_mod.GiraffeApp()


def shoot(win):
    paintable = Gtk.WidgetPaintable.new(win)
    snap = Gtk.Snapshot()
    paintable.snapshot(snap, win.get_width(), win.get_height())
    node = snap.to_node()
    texture = win.get_native().get_renderer().render_texture(
        node, Graphene.Rect().init(0, 0, win.get_width(), win.get_height()))
    texture.save_to_png(out)
    print("wrote", out)
    app.quit()
    return False


def run():
    win = app._win()
    win.set_default_size(900, 520)
    win.present()
    win.set_data(extract.from_text(SAMPLE))
    GLib.timeout_add(1200, shoot, win)
    return False


GLib.idle_add(run)
sys.exit(app.run(["giraffe"]))
