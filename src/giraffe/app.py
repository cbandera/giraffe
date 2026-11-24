import os
import shutil
import subprocess

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib

from . import APP_ID, __version__
from .window import GiraffeWindow


class GiraffeApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.window: GiraffeWindow | None = None

    def _win(self) -> GiraffeWindow:
        if self.window is None:
            self.window = GiraffeWindow(application=self)
        return self.window

    def do_activate(self):
        self._win().present()

    def do_command_line(self, cmdline):
        args = cmdline.get_arguments()[1:]
        cwd = cmdline.get_cwd() or os.getcwd()
        if "--version" in args:
            cmdline.print_literal(f"giraffe {__version__}\n")
            return 0
        if "--help" in args or "-h" in args:
            cmdline.print_literal(
                "Usage: giraffe [--clipboard] [--background] [FILE.pdf]\n"
                "  --clipboard   parse the text currently in the clipboard\n"
                "  --background  stay resident without a window (hotkey shows it instantly)\n")
            return 0
        if "--background" in args:
            self.hold()
            args = [a for a in args if a != "--background"]
            if not args:
                return 0
        win = self._win()
        win.present()
        if "--clipboard" in args:
            # On Wayland the clipboard is only readable once the window has focus.
            GLib.timeout_add(150, self._read_clipboard)
        for a in args:
            if not a.startswith("-"):
                win.open_path(os.path.join(cwd, a))
                break
        return 0

    def _read_clipboard(self):
        win = self._win()
        clipboard = Gdk.Display.get_default().get_clipboard()

        def done(cb, result):
            try:
                text = cb.read_text_finish(result)
            except GLib.Error:
                text = None
            if not text:
                text = self._wl_paste()
            win.open_text(text)

        clipboard.read_text_async(None, done)
        return False

    @staticmethod
    def _wl_paste() -> str | None:
        exe = shutil.which("wl-paste")
        if not exe:
            return None
        try:
            out = subprocess.run([exe, "--no-newline"], capture_output=True, timeout=5,
                                 stdin=subprocess.DEVNULL).stdout
        except (OSError, subprocess.SubprocessError):
            return None
        return out[:2_000_000].decode("utf-8", "replace") or None
