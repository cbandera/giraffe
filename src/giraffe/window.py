import os
import tempfile
from decimal import Decimal

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")
from gi.repository import Adw, Gdk, Gio, GLib, GObject, Graphene, Gtk

from . import epc, extract
from . import iban as iban_mod
from .amounts import format_amount, parse_amount
from .extract.models import MANUAL, PaymentData

CSS = b"""
.qr-frame { background: white; border-radius: 12px; padding: 8px; }
.source { font-size: 0.8em; opacity: 0.6; margin-right: 6px; }
.dropzone { border: 2px dashed alpha(currentColor, 0.3); border-radius: 18px; margin: 24px; }
"""


class QrView(Gtk.Widget):
    """Crisp QR rendering: always black on white, integer-sized modules."""
    __gtype_name__ = "GiraffeQrView"
    BORDER = 4

    def __init__(self):
        super().__init__()
        self.matrix = None
        self.set_size_request(300, 300)
        self.set_hexpand(True)
        self.set_vexpand(True)

    def set_matrix(self, matrix):
        self.matrix = [bytes(r) for r in matrix]
        self.queue_draw()

    def do_snapshot(self, snapshot):
        if not self.matrix:
            return
        n = len(self.matrix) + 2 * self.BORDER
        w, h = self.get_width(), self.get_height()
        cell = max(1, min(w, h) // n)
        size = cell * n
        x0, y0 = (w - size) // 2, (h - size) // 2
        white, black = Gdk.RGBA(), Gdk.RGBA()
        white.parse("white")
        black.parse("black")
        snapshot.append_color(white, Graphene.Rect().init(x0, y0, size, size))
        for y, row in enumerate(self.matrix):
            x = 0
            while x < len(row):
                if row[x]:
                    start = x
                    while x < len(row) and row[x]:
                        x += 1
                    snapshot.append_color(black, Graphene.Rect().init(
                        x0 + (start + self.BORDER) * cell, y0 + (y + self.BORDER) * cell,
                        (x - start) * cell, cell))
                else:
                    x += 1

    def do_measure(self, orientation, for_size):
        return 300, 300, -1, -1


class GiraffeWindow(Adw.ApplicationWindow):
    def __init__(self, **kw):
        super().__init__(title="Giraffe", default_width=900, default_height=560, **kw)
        self._loading = False
        self._png: bytes | None = None
        self.data = PaymentData()
        self._last_input: tuple[str, str] | None = None  # ("file"|"text", value)

        css = Gtk.CssProvider()
        css.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.toasts = Adw.ToastOverlay()
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        open_btn = Gtk.Button(icon_name="document-open-symbolic", tooltip_text="Open PDF (Ctrl+O)")
        open_btn.connect("clicked", lambda *_: self.choose_file())
        paste_btn = Gtk.Button(icon_name="edit-paste-symbolic", tooltip_text="Paste text (Ctrl+V)")
        paste_btn.connect("clicked", lambda *_: self.paste())
        header.pack_start(open_btn)
        header.pack_start(paste_btn)
        toolbar.add_top_bar(header)

        self.stack = Gtk.Stack()
        self.stack.add_named(self._build_empty(), "empty")
        self.stack.add_named(self._build_main(), "main")
        toolbar.set_content(self.stack)
        self.toasts.set_child(toolbar)
        self.set_content(self.toasts)

        self._add_shortcuts()
        drop = Gtk.DropTarget.new(GObject.TYPE_NONE, Gdk.DragAction.COPY)
        drop.set_gtypes([Gio.File, GObject.TYPE_STRING])
        drop.connect("drop", self._on_drop)
        self.add_controller(drop)

    # ---- construction -------------------------------------------------
    def _build_empty(self):
        page = Adw.StatusPage(
            icon_name="document-send-symbolic",
            title="Drop a PDF here",
            description="…or press Ctrl+V to paste invoice text, or Ctrl+O to open a file.\n"
                        "Tip: select the text in your PDF viewer or mail, copy it, and press the "
                        "Giraffe hotkey (Ctrl+Alt+G).")
        page.add_css_class("dropzone")
        return page

    def _build_main(self):
        box = Gtk.Box(spacing=24, margin_top=12, margin_bottom=18, margin_start=18, margin_end=18)

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, hexpand=True)
        self.group = Adw.PreferencesGroup(title="Payment details")
        self.rows: dict[str, Adw.EntryRow] = {}
        self.src_labels: dict[str, Gtk.Label] = {}
        self.dropdowns: dict[str, Gtk.DropDown] = {}
        for key, title in [("payee", "Payee"), ("iban", "IBAN"), ("bic", "BIC (optional)"),
                           ("amount", "Amount (EUR)"), ("remittance", "Remittance text")]:
            row = Adw.EntryRow(title=title)
            row.connect("changed", self._on_changed, key)
            lbl = Gtk.Label(css_classes=["source"], valign=Gtk.Align.CENTER)
            row.add_suffix(lbl)
            if key in ("iban", "amount"):
                dd = Gtk.DropDown.new_from_strings([])
                dd.set_valign(Gtk.Align.CENTER)
                dd.set_visible(False)
                dd.set_tooltip_text("Other detected candidates")
                dd.connect("notify::selected", self._on_candidate, key)
                row.add_suffix(dd)
                self.dropdowns[key] = dd
            self.group.add(row)
            self.rows[key] = row
            self.src_labels[key] = lbl
        left.append(self.group)

        self.message = Gtk.Label(wrap=True, xalign=0, selectable=False)
        left.append(self.message)
        self.hint = Gtk.Label(
            label="Check IBAN and payee name in your banking app before paying.",
            wrap=True, xalign=0, css_classes=["dim-label"])
        left.append(self.hint)
        box.append(left)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.qr = QrView()
        frame = Gtk.Box(css_classes=["qr-frame"], halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        frame.append(self.qr)
        self.qr_stack = Gtk.Stack(vexpand=True, hexpand=True)
        self.qr_stack.add_named(frame, "qr")
        self.qr_stack.add_named(Gtk.Label(label="No QR code", css_classes=["dim-label", "title-2"]), "none")
        right.append(self.qr_stack)
        actions = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER)
        self.save_btn = Gtk.Button(label="Save PNG…")
        self.save_btn.connect("clicked", lambda *_: self.save_png())
        self.copy_btn = Gtk.Button(label="Copy image")
        self.copy_btn.connect("clicked", lambda *_: self.copy_image())
        reread = Gtk.Button(label="Re-read input")
        reread.connect("clicked", lambda *_: self.reread())
        for b in (self.save_btn, self.copy_btn, reread):
            actions.append(b)
        right.append(actions)
        box.append(right)
        return box

    def _add_shortcuts(self):
        ctrl = Gtk.ShortcutController()
        ctrl.set_scope(Gtk.ShortcutScope.GLOBAL)
        for trigger, fn in [("<Control>o", self.choose_file), ("<Control>q", self.close)]:
            ctrl.add_shortcut(Gtk.Shortcut.new(
                Gtk.ShortcutTrigger.parse_string(trigger),
                Gtk.CallbackAction.new(lambda *_a, f=fn: (f(), True)[1])))
        self.add_controller(ctrl)
        # Ctrl+V: capture phase so it works unless a text entry has focus and wants it
        key = Gtk.EventControllerKey()
        key.connect("key-pressed", self._on_key)
        self.add_controller(key)

    def _on_key(self, _c, keyval, _code, state):
        if keyval in (Gdk.KEY_v, Gdk.KEY_V) and state & Gdk.ModifierType.CONTROL_MASK:
            focus = self.get_focus()
            if isinstance(focus, Gtk.Editable) or (focus and focus.get_ancestor(Gtk.Editable)):
                return False  # let the field paste normally
            self.paste()
            return True
        return False

    # ---- input --------------------------------------------------------
    def toast(self, msg: str):
        self.toasts.add_toast(Adw.Toast.new(msg))

    def open_path(self, path: str):
        self._last_input = ("file", path)
        try:
            data = extract.from_file(path)
        except extract.InputError as e:
            self.toast(str(e))
            return
        self.set_data(data)

    def open_text(self, text: str | None):
        if not text or not text.strip():
            self.toast("The clipboard contains no text.")
            return
        self._last_input = ("text", text)
        self.set_data(extract.from_text(text))

    def paste(self):
        def done(cb, result):
            try:
                text = cb.read_text_finish(result)
            except GLib.Error:
                text = None
            self.open_text(text)
        self.get_clipboard().read_text_async(None, done)

    def reread(self):
        if not self._last_input:
            return
        kind, value = self._last_input
        self.open_path(value) if kind == "file" else self.open_text(value)

    def choose_file(self):
        dialog = Gtk.FileDialog(title="Open invoice")
        flt = Gtk.FileFilter(name="PDF documents")
        flt.add_mime_type("application/pdf")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(flt)
        dialog.set_filters(filters)

        def done(d, result):
            try:
                f = d.open_finish(result)
            except GLib.Error:
                return
            self._open_gfile(f)
        dialog.open(self, None, done)

    def _open_gfile(self, f: Gio.File):
        path = f.get_path()
        if path:
            self.open_path(path)
            return
        # non-native location (e.g. remote): copy to a private temp dir, delete afterwards
        try:
            ok, content, _ = f.load_contents(None)
        except GLib.Error as e:
            self.toast(e.message)
            return
        if len(content) > extract.MAX_FILE_BYTES:
            self.toast("File is too large.")
            return
        with tempfile.TemporaryDirectory(prefix="giraffe-") as tmp:
            p = os.path.join(tmp, "input.pdf")
            with open(p, "wb") as fh:
                fh.write(content)
            self.open_path(p)
        self._last_input = None  # temp file is gone, re-read impossible

    def _on_drop(self, _t, value, _x, _y):
        if isinstance(value, Gio.File):
            self._open_gfile(value)
            return True
        if isinstance(value, str):
            lines = [l.strip() for l in value.splitlines() if l.strip()]
            if lines and all(l.startswith("file://") for l in lines):
                self._open_gfile(Gio.File.new_for_uri(lines[0]))
            else:
                self.open_text(value)
            return True
        return False

    # ---- state --------------------------------------------------------
    def set_data(self, data: PaymentData):
        self.data = data
        self._loading = True
        for key, row in self.rows.items():
            row.set_text(getattr(data, key))
        for key, cands in (("iban", data.iban_candidates), ("amount", data.amount_candidates)):
            dd = self.dropdowns[key]
            labels = [iban_mod.format_iban(c) if key == "iban" else c for c in cands]
            dd.set_model(Gtk.StringList.new(labels))
            dd.set_visible(len(cands) > 1)
            dd.set_selected(0)
        self._loading = False
        self.stack.set_visible_child_name("main")
        self._update_sources()
        self._refresh()
        if data.warnings:
            self.toast(data.warnings[0])

    def _update_sources(self):
        for key, lbl in self.src_labels.items():
            lbl.set_text(self.data.source(key))

    def _on_changed(self, row, key):
        if self._loading:
            return
        setattr(self.data, key, row.get_text())
        self.data.sources[key] = MANUAL
        self._update_sources()
        self._refresh()

    def _on_candidate(self, dd, _p, key):
        if self._loading:
            return
        cands = self.data.iban_candidates if key == "iban" else self.data.amount_candidates
        i = dd.get_selected()
        if i < len(cands):
            orig = self.data.sources.get(key, "text")
            self.rows[key].set_text(cands[i])
            self.data.sources[key] = orig if orig != MANUAL else "text"
            self._update_sources()

    def _refresh(self):
        d = self.data
        self._png = None
        self.message.remove_css_class("error")
        self.message.remove_css_class("warning")
        text = ""
        amount = None
        try:
            if d.currency != "EUR":
                raise epc.EpcError(f"Currency {d.currency} is not supported (EUR only).")
            if d.amount.strip():
                amount = parse_amount(d.amount)
                if amount is None:
                    raise epc.EpcError("Amount is not a valid number.")
            payload = epc.build_payload(d.payee, d.iban, amount, d.bic, d.remittance)
            self.qr.set_matrix(epc.make_qr(payload).matrix)
            self._png = epc.png_bytes(payload)
            self.qr_stack.set_visible_child_name("qr")
            if amount is None:
                text = "No amount: you will have to enter it in your banking app."
                self.message.add_css_class("warning")
        except epc.EpcError as e:
            text = str(e)
            self.message.add_css_class("error")
            self.qr_stack.set_visible_child_name("none")
        self.message.set_text(text)
        self.message.set_visible(bool(text))
        self.save_btn.set_sensitive(self._png is not None)
        self.copy_btn.set_sensitive(self._png is not None)

    # ---- actions ------------------------------------------------------
    def save_png(self):
        if not self._png:
            return
        dialog = Gtk.FileDialog(title="Save QR code", initial_name="girocode.png")

        def done(d, result):
            try:
                f = d.save_finish(result)
                f.replace_contents(self._png, None, False, Gio.FileCreateFlags.NONE, None)
                self.toast("QR code saved.")
            except GLib.Error as e:
                if not e.matches(Gtk.dialog_error_quark(), Gtk.DialogError.DISMISSED):
                    self.toast(e.message)
        dialog.save(self, None, done)

    def copy_image(self):
        if not self._png:
            return
        texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(self._png))
        self.get_clipboard().set_texture(texture)
        self.toast("QR image copied.")
