# roboterm

A GTK4/VTE terminal emulator written in Python, with tab support, pane splitting, and a live preferences dialog.

## Features

- Multiple tabs with drag-to-reorder
- Horizontal and vertical pane splitting
- Pane rotation
- Per-pane title bar (shows shell/program title via OSC sequences)
- Preferences dialog: font, colors, 10 built-in themes, cursor shape/blink, scrollback, bold-is-bright
- Settings persisted to `~/.config/roboterm/settings.json`
- Ctrl+C in the launching terminal cleanly quits the app

## Dependencies

### macOS (Homebrew)

```bash
brew install gtk4 libadwaita vte3 pygobject3
```

### Debian / Ubuntu

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adwaita-1 gir1.2-vte-3.91
```

### Fedora

```bash
sudo dnf install python3-gobject gtk4 libadwaita vte391-gtk4
```

### Arch

```bash
sudo pacman -S python-gobject gtk4 libadwaita vte3
```

## Running

```bash
PYTHONPATH=/opt/homebrew/lib/python3.13/site-packages python3.13 roboterm.py
```

## Keyboard Shortcuts

| Shortcut         | Action                                         |
|------------------|------------------------------------------------|
| `Ctrl+,`         | Preferences                                    |
| `Ctrl+Shift+C`   | Copy selection                                 |
| `Ctrl+Shift+V`   | Paste clipboard                                |
| `Ctrl+Shift+N`   | New window                                     |
| `Ctrl+Shift+T`   | New tab                                        |
| `Ctrl+Shift+W`   | Close active pane (closes tab when last pane)  |
| `Ctrl+Shift+A`   | Split pane automatically (based on dimensions) |
| `Ctrl+Shift+E`   | Split pane right                               |
| `Ctrl+Shift+O`   | Split pane down                                |
| `Ctrl+Shift+]`   | Rotate panes clockwise                         |
| `Ctrl+Shift+[`   | Rotate panes counter-clockwise                 |
| `Ctrl+Page Up`   | Previous tab                                   |
| `Ctrl+Page Down` | Next tab                                       |

Right-click any pane for a context menu with the same split and close actions.

## Project Layout

```
roboterm.py          entry point
roboterm/
  __init__.py          gi version requirements and Adw.init()
  settings.py          Settings singleton, THEMES, _rgba_to_hex
  terminal.py          TerminalWidget (VTE + copy/paste + context menu)
  panes.py             PaneFrame, PaneManager
  preferences.py       PreferencesWindow
  window.py            TabLabel, TerminalWindow
  app.py               TerminalApp
tests/
  unit/                mocked-gi unit tests (any Python, no display needed)
  integration/         real-gi tests against Vte.Terminal and Gdk.RGBA
```

## Tests

**Unit tests** (no display required, uses brew pytest):

```bash
pytest tests/unit/
```

**Integration tests** (requires GTK + VTE via Python 3.13):

```bash
PYTHONPATH=/opt/homebrew/lib/python3.13/site-packages python3.13 -m pytest tests/integration/
```
