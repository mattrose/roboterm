# roboterm

A GTK4/VTE terminal emulator written in Python, with tab support, pane splitting, and a live preferences dialog.

## Features

- Multiple tabs with drag-to-reorder
- Horizontal and vertical pane splitting
- Pane rotation
- Per-pane title bar (shows shell/program title via OSC sequences)
- Clickable http/https URLs and OSC-8 hyperlinks (Cmd/Ctrl+click, or right-click for "Open Link")
- Preferences dialog: font, colors, 10 built-in themes, cursor shape/blink, scrollback, bold-is-bright
- Customizable keybindings, editable from the Preferences window
- Settings persisted to `~/.config/roboterm/settings.json`

## Dependencies

### macOS (Homebrew)

```bash
brew install gtk4 libadwaita vte3 pygobject3 gtk-mac-integration
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
PYTHONPATH="$(python3 -c 'import sysconfig; print(sysconfig.get_path("purelib"))')" python3 roboterm.py
```

This points `PYTHONPATH` at the `gi`/GTK bindings installed for whichever `python3` you run (any Python 3). On Linux with `python3-gi` installed system-wide, plain `python3 roboterm.py` usually works with no `PYTHONPATH`.

## Building the macOS app bundle

To build `Roboterm.app` — a native `.app` with a C launcher that embeds libpython, so the Dock shows "Roboterm" instead of "Python":

```bash
make app
```

This detects the `python3` on your `PATH` and builds against it, deriving the version, include dir, and libpython from `sysconfig` (no hardcoded version). To build against a specific interpreter:

```bash
make PYTHON=/opt/homebrew/bin/python3.13 app
```

Remove the bundle with `make clean`.

### Installing to Applications

Move the built bundle into your Applications folder so it shows up in Launchpad and Spotlight:

```bash
mv Roboterm.app /Applications/
```

The app still relies on the Homebrew GTK stack at runtime (see [Dependencies](#macos-homebrew)), so keep those packages installed. After moving it, launch it from the Dock, Launchpad, or `open /Applications/Roboterm.app`.

## Keyboard Shortcuts

Defaults below; every shortcut except Copy/Paste can be rebound from the Preferences window's Keybindings tab.

| Action                                          | macOS            | Linux / Other    |
|--------------------------------------------------|------------------|-------------------|
| Preferences                                      | `Cmd+,`          | `Ctrl+,`          |
| Copy selection                                   | `Cmd+C`          | `Ctrl+Shift+C`    |
| Paste clipboard                                  | `Cmd+V`          | `Ctrl+Shift+V`    |
| New window                                       | `Cmd+N`          | `Ctrl+Shift+N`    |
| New tab                                          | `Cmd+T`          | `Ctrl+Shift+T`    |
| Close active pane (closes tab when last pane)    | `Cmd+W`          | `Ctrl+Shift+W`    |
| Split pane automatically (based on dimensions)   | `Cmd+A`          | `Ctrl+Shift+A`    |
| Split pane right                                 | `Cmd+D`          | `Ctrl+Shift+E`    |
| Split pane down                                  | `Cmd+Shift+D`    | `Ctrl+Shift+O`    |
| Rotate panes clockwise                           | `Cmd+Option+]`   | `Ctrl+Shift+]`    |
| Rotate panes counter-clockwise                   | `Cmd+Option+[`   | `Ctrl+Shift+[`    |
| Previous tab                                     | `Cmd+Shift+[`    | `Ctrl+Page Up`    |
| Next tab                                         | `Cmd+Shift+]`    | `Ctrl+Page Down`  |

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

**Integration tests** (requires a Python 3 with GTK + VTE / PyGObject installed):

```bash
PYTHONPATH="$(python3 -c 'import sysconfig; print(sysconfig.get_path("purelib"))')" python3 -m pytest tests/integration/
```
