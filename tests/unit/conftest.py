# Roboterm - a GTK4/VTE terminal emulator.
# Copyright (C) 2026 Matt Rose
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <https://www.gnu.org/licenses/>.

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
