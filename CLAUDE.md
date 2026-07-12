# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

roboterm is a GTK4/VTE terminal emulator written in Python (tabs, pane splitting, live preferences). It targets macOS (Homebrew GTK stack, packaged as a native `.app`) and Linux.

## Commands

### Running

```bash
PYTHONPATH=/opt/homebrew/lib/python3.13/site-packages python3.13 roboterm.py
```

On Linux, `PYTHONPATH` typically isn't needed if `python3-gi` etc. are installed system-wide — just `python3 roboterm.py`.

### Building the macOS app bundle

```bash
make app     # produces Roboterm.app (native C launcher embeds libpython so the Dock shows "Roboterm", not "Python")
make clean
```

### Tests

Three tiers, each with different environment requirements:

```bash
# Unit tests — gi/GTK is fully mocked (see tests/unit/conftest.py), runs anywhere
pytest tests/unit/

# Integration tests — needs a real GTK4/VTE/PyGObject install
PYTHONPATH=/opt/homebrew/lib/python3.13/site-packages python3.13 -m pytest tests/integration/

# UI/e2e tests — Linux only; drives a real app window via PyAutoGUI/xdotool inside
# an Xvfb virtual display, spawned with `dbus-run-session python3.12 roboterm.py`.
# Needs the `ui-tests` extra (pyautogui, python-xlib, Pillow, pyvirtualdisplay) plus
# xdotool/scrot/dbus on the host. Marked with `pytest.mark.ui`.
pytest tests/ui/
```

Run a single test: `pytest tests/unit/test_settings.py::TestRgbaToHex::test_black`.

Settings tests always reset the `Settings` singleton (`Settings._instance = None`) via an autouse `reset_singleton` fixture and redirect `Settings.CONFIG_PATH` to a tmp file via the `tmp_config` fixture — follow this pattern for any new test that touches `Settings`, since it's a process-wide singleton.

## Architecture

### Signal-driven, no central controller

Widgets communicate via custom GObject signals rather than direct references pointing "up" the tree — e.g. `TerminalWidget` emits `split-right`/`split-down`/`close-pane`/`rotate-cw`/`new-tab`/etc. and `PaneManager` (in `panes.py`) is what actually connects to and acts on them (`_make_frame` wires every new terminal's signals). `PaneManager` itself emits `all-closed`/`new-tab`/`new-window`, which `TerminalWindow` (in `window.py`) connects to per-tab. This means the same user action (e.g. "split right") can be triggered from the VTE context menu, the app menu bar (macOS), or a keybinding, and all three converge on the same signal/action path — when adding a new pane/tab operation, wire it the same way (emit a signal from the leaf widget, handle it in the owning manager) rather than reaching into widget internals.

### Settings is a global singleton with a change-notification bus

`Settings.get()` (in `settings.py`) is a classic singleton backed by `~/.config/roboterm/settings.json`. Any code that mutates it (`set_value`, `apply_theme`) calls `save()` and fires every registered `connect_changed` callback. `TerminalWidget`, `PaneManager`, and `TerminalWindow` all register listeners (using `weakref` where the listener outlives a widget that might be destroyed) so that changing a preference live-updates every open terminal/pane/keybinding table without any explicit "refresh" call. When adding a new setting, add it to `DEFAULTS`, wire persistence through `set_value`/`apply_to_vte`, and expect it to propagate automatically to anything with a `connect_changed` listener — don't hand-roll a separate update path.

### Keybindings: two separate paths that must stay conceptually distinct

1. **Actual key handling** — `TerminalWindow._build_key_table()` (in `window.py`) builds a `{(modifier_mask, keyval): callback}` dict straight from `Settings.get().get_keybindings()`, applied via a `Gtk.EventControllerKey` in the **CAPTURE** phase (so it intercepts before VTE sees the key on every platform). This table rebuilds automatically on `Settings.connect_changed`, which is what makes keybindings live-editable from Preferences.
2. **macOS menu-bar accelerator labels** — `TerminalApp._setup_menubar()` (in `app.py`) calls `set_accels_for_action(...)` with hardcoded `<Meta>...` accelerators. These exist only so the native macOS menu bar displays the right shortcut text next to each item; they are not what fires when you press the key, and they do **not** reflect user rebinding via Preferences. If you change a default keybinding, update both `_default_keybindings()` in `settings.py` and the corresponding `set_accels_for_action` call in `app.py`, or the menu label will drift from actual behavior.

Copy/Paste (`Cmd+C`/`Cmd+V` on macOS, `Ctrl+Shift+C`/`Ctrl+Shift+V` elsewhere) is handled separately and directly in `TerminalWidget._on_key_pressed` (`terminal.py`) — it is **not** part of the customizable `Settings` keybindings dict and can't be rebound from Preferences.

### Pane tree

`PaneManager` (`panes.py`) manages a binary tree of `Gtk.Paned` splits containing `PaneFrame`s (a `PaneFrame` wraps one `TerminalWidget` plus an optional title-bar). Splitting inserts a new `Gtk.Paned` in place of the old frame; closing walks up to the parent `Paned` and promotes the sibling into the grandparent's slot. `rotate_cw`/`rotate_ccw` flatten the tree's leaf slots left-to-right via `_collect_slots`, cycle the frame assignment, and reassign — this only supports rotation of the tree as currently shaped, not re-balancing. Pane titlebars are shown based on the `pane_titlebar` setting (`auto`/`always`/`never`) and re-evaluated in `_update_titlebars` on every split/close/settings-change.

### Testing gi/GTK without a display

`tests/unit/conftest.py` pre-populates `sys.modules` with `MagicMock()` for `gi` and every `gi.repository.*` submodule *before* any `roboterm` module is imported, so unit tests can import `roboterm.settings`/`roboterm.preferences`/etc. on any machine with no GTK install. This only works for logic that doesn't depend on real GObject signal semantics (handler blocking, `notify::` signal emission) — tests that need real signal behavior belong in `tests/integration/` (real `gi`/GTK/VTE) instead.

## Project Layout

```
roboterm.py             entry point
roboterm/
  __init__.py            gi version requirements + Adw.init()
  settings.py             Settings singleton, THEMES, _rgba_to_hex
  terminal.py              TerminalWidget (VTE + copy/paste + URL click + context menu)
  panes.py                 PaneFrame, PaneManager (split/rotate/close tree logic)
  preferences.py           PreferencesWindow, ShortcutRow (keybinding recorder)
  window.py                TabLabel, TerminalWindow (tabs, menu, key handling)
  app.py                   TerminalApp (Adw.Application, macOS menu bar)
macos/                   native launcher.c, Info.plist, icon generator for the .app bundle
tests/
  unit/                   mocked-gi tests, no display needed
  integration/             real-gi tests against Vte.Terminal / Gdk.RGBA
  ui/                       PyAutoGUI end-to-end tests (Linux/Xvfb only)
```
