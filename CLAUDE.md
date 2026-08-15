# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

roboterm is a GTK4/VTE terminal emulator written in Python (tabs, pane splitting, live preferences). It targets macOS (Homebrew GTK stack, packaged as a native `.app`) and Linux.

## Commands

### Running

```bash
PYTHONPATH="$(python3 -c 'import sysconfig; print(sysconfig.get_path("purelib"))')" python3 roboterm.py
```

`PYTHONPATH` points at the `gi`/GTK bindings for whichever `python3` is used (any Python 3). On Linux, `PYTHONPATH` typically isn't needed if `python3-gi` etc. are installed system-wide — just `python3 roboterm.py`.

### Building the macOS app bundle

```bash
make app     # produces Roboterm.app (native C launcher embeds libpython so the Dock shows "Roboterm", not "Python")
make bundle  # make app + copy/relocate the whole native stack in → self-contained .app (no Homebrew at runtime)
make clean
```

The Makefile detects the `python3` on `PATH` and derives the version, include dir, and libpython it embeds via `sysconfig` — it fails with a message if that interpreter is missing or older than Python 3. Build against a different interpreter with `make PYTHON=/opt/homebrew/bin/python3.13`. The detected version is passed to `macos/launcher.c` as `-DROBOTERM_PY_VER` so the launcher locates the matching Python at runtime (there is no hardcoded version in either file).

`make app` builds a bundle that still points at the Homebrew stack at runtime (fast, for development). `make bundle` runs `macos/bundle_deps.py` on top of it to copy the Python framework, the GTK4/VTE dylib closure, PyGObject/pycairo, typelibs, GSettings schemas, gdk-pixbuf loaders and the Adwaita icon theme into the `.app`, rewrite every `install name` off `/opt/homebrew`, and ad-hoc codesign — producing a distributable, dependency-free bundle. `launcher.c` detects at runtime whether `Contents/Frameworks/Python.framework` exists and roots all paths (`PYTHONHOME`, `GI_TYPELIB_PATH`, `DYLD_LIBRARY_PATH`, schema/pixbuf/icon dirs) inside the bundle when it does, else falls back to Homebrew — so one launcher serves both build modes. Key bundling subtleties `bundle_deps.py` handles (each learned from a concrete failure): dylibs are named by their versioned install-id soname (so `@rpath/libgtk-4.1.dylib` resolves); the dependency closure follows `@loader_path`/`@rpath` deps too (Homebrew's ICU libs reference siblings relatively — miss this and `libvte` fails to load); typelib shared-libraries are seeded as extra roots (Gtk/Adw/Vte are `dlopen`'d via typelibs, not linked); Homebrew's own `LC_RPATH` entries are stripped (else `@rpath` deps resolve to the Homebrew copy, causing duplicate-type-system clashes); and the gdk-pixbuf `loaders.cache` is regenerated from the *original* loaders (querying the relocated copies SIGKILLs on the invalidated signature).

Note: launching the built binary directly from a shell (`./Roboterm.app/Contents/MacOS/Roboterm`) can crash in VTE's child-spawn fd walk due to inherited shell file descriptors; launch via `open Roboterm.app` (the real path) to test.

### Tests

Three tiers, each with different environment requirements:

```bash
# Unit tests — gi/GTK is fully mocked (see tests/unit/conftest.py), runs anywhere
pytest tests/unit/

# Integration tests — needs a real GTK4/VTE/PyGObject install
PYTHONPATH="$(python3 -c 'import sysconfig; print(sysconfig.get_path("purelib"))')" python3 -m pytest tests/integration/

# UI/e2e tests — Linux only; drives a real app window via PyAutoGUI/xdotool inside
# an Xvfb virtual display, spawned with `dbus-run-session <python3> roboterm.py`.
# The harness auto-detects a python3 that can import gi (override with
# ROBOTERM_TEST_PYTHON=...); see _find_python_with_gi in tests/ui/conftest.py.
# Needs the `ui-tests` extra (pyautogui, python-xlib, Pillow, pyvirtualdisplay) plus
# xdotool/scrot/dbus on the host. Marked with `pytest.mark.ui`.
pytest tests/ui/
```

Run a single test: `pytest tests/unit/test_settings.py::TestRgbaToHex::test_black`.

Settings tests always reset the `Settings` singleton (`Settings._instance = None`) via an autouse `reset_singleton` fixture and redirect `Settings.CONFIG_PATH` to a tmp file via the `tmp_config` fixture — follow this pattern for any new test that touches `Settings`, since it's a process-wide singleton.

## Architecture

### Signal-driven, no central controller

Widgets communicate via custom GObject signals rather than direct references pointing "up" the tree — e.g. `TerminalWidget` emits `split-right`/`split-down`/`close-pane`/`rotate-cw`/`new-tab`/etc. and `PaneManager` (in `panes.py`) is what actually connects to and acts on them (`_make_frame` wires every new terminal's signals). `PaneManager` itself emits `all-closed`/`new-tab`/`new-window`/`title-changed`, which `TerminalWindow` (in `window.py`) connects to per-tab. Titles travel the same way: VTE's `window-title-changed`/`current-directory-uri` become `TerminalWidget`'s `title-changed`, which `PaneFrame` uses for its titlebar and `PaneManager` re-emits for the *active* pane only, so `TerminalWindow` can update that tab's label and the window title. This means the same user action (e.g. "split right") can be triggered from the VTE context menu, the app menu bar (macOS), or a keybinding, and all three converge on the same signal/action path — when adding a new pane/tab operation, wire it the same way (emit a signal from the leaf widget, handle it in the owning manager) rather than reaching into widget internals.

### Settings is a global singleton with a change-notification bus

`Settings.get()` (in `settings.py`) is a classic singleton backed by `~/.config/roboterm/settings.json`. Any code that mutates it (`set_value`, `apply_theme`) calls `save()` and fires every registered `connect_changed` callback. `TerminalWidget`, `PaneManager`, and `TerminalWindow` all register listeners (using `weakref` where the listener outlives a widget that might be destroyed) so that changing a preference live-updates every open terminal/pane/keybinding table without any explicit "refresh" call. When adding a new setting, add it to `DEFAULTS`, wire persistence through `set_value`/`apply_to_vte`, and expect it to propagate automatically to anything with a `connect_changed` listener — don't hand-roll a separate update path.

### Keybindings: two separate paths, one source of truth

Both paths read `Settings.get().get_keybindings()`, but they do very different things with it:

1. **Actual key handling** — `TerminalWindow._build_key_table()` (in `window.py`) builds a `{(modifier_mask, keyval): callback}` dict straight from `Settings.get().get_keybindings()`, applied via a `Gtk.EventControllerKey` in the **CAPTURE** phase (so it intercepts before VTE sees the key on every platform). This table rebuilds automatically on `Settings.connect_changed`, which is what makes keybindings live-editable from Preferences.
2. **macOS menu-bar accelerator labels** — `TerminalApp._refresh_menu_accels()` (in `app.py`) maps keybinding names to menu action names via `_MENU_ACCEL_ACTIONS` and feeds `set_accels_for_action(...)`, re-running on `Settings.connect_changed`. These accelerators exist only so the native macOS menu bar displays the right shortcut text next to each item; they are **not** what fires when you press the key. A new pane/tab operation with a menu item needs an entry in `_MENU_ACCEL_ACTIONS`, and nothing else — never hardcode an accelerator string in a `set_accels_for_action` call, which is how the labels drifted from actual behavior in the first place (`tests/unit/test_menu_accels.py` fails if one reappears).

Copy/Paste (`Cmd+C`/`Cmd+V` on macOS, `Ctrl+Shift+C`/`Ctrl+Shift+V` elsewhere) is handled separately and directly in `TerminalWidget._on_key_pressed` (`terminal.py`) — it is **not** part of the customizable `Settings` keybindings dict and can't be rebound from Preferences.

### Pane tree

`PaneManager` (`panes.py`) manages a binary tree of `Gtk.Paned` splits containing `PaneFrame`s (a `PaneFrame` wraps one `TerminalWidget` plus an optional title-bar). Splitting inserts a new `Gtk.Paned` in place of the old frame; closing walks up to the parent `Paned` and promotes the sibling into the grandparent's slot. `rotate_cw`/`rotate_ccw` flatten the tree's leaf slots left-to-right via `_collect_slots`, cycle the frame assignment, and reassign — this only supports rotation of the tree as currently shaped, not re-balancing. `toggle_maximize_active` detaches one `PaneFrame` from its `Gtk.Paned` slot, swaps the whole tree out of the `PaneManager` box for that frame, and remembers `(root, paned, side, frame)` in `_maximized` so `unmaximize` can put it back; while maximized the tree root lives only in that tuple, so anything that walks the tree must go through `_root()`, and every tree mutation (split/rotate/close) calls `unmaximize(refocus=False)` first. Pane titlebars are shown based on the `pane_titlebar` setting (`auto`/`always`/`never`) and re-evaluated in `_update_titlebars` on every split/close/settings-change.

### Known bug: first window blank until a keypress on macOS

On some Homebrew GTK4 builds (confirmed on GTK 4.22.4 / VTE 0.84.0), the very first window's content is never painted after `win.present()` — the shell spawns and prints its prompt into VTE's buffer fine (`contents-changed` fires), but nothing reaches the screen until the window receives a real, OS-delivered input event. This is a rendering bug in the GTK4 macOS backend, not in roboterm's code (there's no freeze/realize/paint logic here to fix).

Confirmed *not* to fix it, despite looking plausible: resizing the window programmatically, `Gdk.Surface.queue_render()` (even called repeatedly), toggling `win.set_visible(False/True)`, forcing `GSK_RENDERER=cairo`. The only thing that reliably works is a real keystroke or click delivered through the actual OS input pipeline (verified via `System Events` synthetic key events with Accessibility permission) — GLib-timer-driven redraw requests don't go through whatever AppKit display-commit path a real NSEvent does. Subsequent tabs/splits/windows are unaffected since their host window is already receiving real frame-clock ticks. See the "Known Issues" note in README.md.

`roboterm/__init__.py` sets `GSK_RENDERER=cairo` on macOS anyway. Don't read that as a fix — it was tested clean across 8 separate trials (4 as a shell-level env var, 4 in-process via `os.environ.setdefault` before any `gi` import) and reproduced the blank window in all but one, which is best explained as a fluke rather than the renderer mattering. It's kept on request despite the unproven benefit and the real cost (Cairo software rendering is slower than the default GPU-backed renderer, which matters for a terminal doing frequent scrollback/redraw). If revisiting this bug, don't waste time re-deriving that GSK_RENDERER doesn't help — start from the "real OS input event" finding above instead.

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
