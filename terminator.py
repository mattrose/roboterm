#!/usr/bin/env python3
"""
roboterm — GTK4/VTE terminal emulator.

Keyboard shortcuts:
    Ctrl+,            — preferences
    Ctrl+Shift+C      — copy selection
    Ctrl+Shift+V      — paste clipboard
    Ctrl+Shift+N      — new window
    Ctrl+Shift+T      — new tab
    Ctrl+Shift+W      — close active pane  (closes tab when last pane)
    Ctrl+Shift+]      — rotate panes clockwise
    Ctrl+Shift+[      — rotate panes counter-clockwise
    Ctrl+Shift+A      — split active pane automatically (based on dimensions)
    Ctrl+Shift+E      — split active pane right (vertical divider)
    Ctrl+Shift+O      — split active pane down  (horizontal divider)
    Ctrl+Page_Up      — previous tab
    Ctrl+Page_Down    — next tab

Right-click any pane for a context menu with split / close actions.
"""

from roboterm.app import TerminalApp

if __name__ == "__main__":
    TerminalApp().run()
