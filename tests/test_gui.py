import os

import pytest

pytestmark = pytest.mark.skipif(not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")),
                                reason="no display")

TEXT = """Muster GmbH
Rechnung Nr. 2024-0815
Rechnungsbetrag 1.190,00 EUR
Kontoinhaber: Muster GmbH
IBAN: DE89 3704 0044 0532 0130 00
"""


def test_window_smoke():
    from giraffe.app import GiraffeApp
    from giraffe.window import GiraffeWindow
    from gi.repository import GLib

    app = GiraffeApp()
    result = {}

    def run(_app):
        win = GiraffeWindow(application=app)
        win.present()
        win.open_text(TEXT)
        result["png"] = win._png
        win.rows["iban"].set_text("DE00")
        result["bad_png"] = win._png
        result["msg"] = win.message.get_text()
        win.close()

    app.connect("activate", run)
    GLib.timeout_add(10000, app.quit)
    app.register(None)
    app.activate()
    assert result["png"] and result["png"].startswith(b"\x89PNG")
    assert result["bad_png"] is None and "IBAN" in result["msg"]
