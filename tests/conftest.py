import sys
from unittest.mock import MagicMock

# Mock gi and all gi.repository sub-modules before any roboterm module is
# imported.  This lets unit tests run on any Python without a display or
# GTK libraries installed.
for _mod in [
    "gi", "gi.repository",
    "gi.repository.Gtk", "gi.repository.Adw",
    "gi.repository.Vte", "gi.repository.Gdk",
    "gi.repository.Pango", "gi.repository.GLib",
    "gi.repository.GObject", "gi.repository.Gio",
]:
    sys.modules.setdefault(_mod, MagicMock())
