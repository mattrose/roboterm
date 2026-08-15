#!/usr/bin/env python
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

"""
roboterm — GTK4/VTE terminal emulator.

Keyboard shortcuts (Linux / macOS):
    Ctrl+,  / Cmd+,         — settings
    Ctrl+Shift+C / Cmd+C    — copy selection
    Ctrl+Shift+V / Cmd+V    — paste clipboard
    Ctrl+Shift+N / Cmd+N    — new window
    Ctrl+Shift+T / Cmd+T    — new tab
    Ctrl+Shift+W / Cmd+W    — close active pane  (closes tab when last pane)
    Ctrl+Shift+] / Cmd+Opt+]— rotate panes clockwise
    Ctrl+Shift+[ / Cmd+Opt+[— rotate panes counter-clockwise
    Ctrl+Shift+A / Cmd+Shift+A — split active pane automatically
    Ctrl+Shift+E / Cmd+Shift+E — split active pane right (vertical divider)
    Ctrl+Shift+O / Cmd+Shift+O — split active pane down  (horizontal divider)
    Ctrl+Page_Up  / Cmd+Shift+[ — previous tab
    Ctrl+Page_Down / Cmd+Shift+] — next tab

Right-click any pane for a context menu with split / close actions.
"""

from roboterm.app import TerminalApp

if __name__ == "__main__":
    TerminalApp().run()
