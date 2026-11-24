#!/usr/bin/env python3
"""Idempotently add a GNOME custom keybinding for `giraffe --clipboard`."""
import sys

from gi.repository import Gio

BASE = "org.gnome.settings-daemon.plugins.media-keys"
ITEM = BASE + ".custom-keybinding"
PATH = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/giraffe/"


def main(command: str, binding: str = "<Ctrl><Alt>g") -> int:
    settings = Gio.Settings.new(BASE)
    paths = list(settings.get_strv("custom-keybindings"))
    for p in paths:  # already registered under any path?
        s = Gio.Settings.new_with_path(ITEM, p)
        if s.get_string("command") == command:
            print("Shortcut already registered.")
            return 0
    item = Gio.Settings.new_with_path(ITEM, PATH)
    item.set_string("name", "Giraffe (clipboard)")
    item.set_string("command", command)
    item.set_string("binding", binding)
    if PATH not in paths:
        paths.append(PATH)
        settings.set_strv("custom-keybindings", paths)
    Gio.Settings.sync()
    print(f"Registered {binding} -> {command}")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
