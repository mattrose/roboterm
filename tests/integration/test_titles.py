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

"""Title propagation: VTE → TerminalWidget → PaneFrame/PaneManager.

Titles are driven by escape sequences the shell writes (OSC 0/2 for the window
title, OSC 7 for the current directory).  `Vte.Terminal.feed` injects those as
if the child had written them, but VTE only parses incoming data once the
widget is realized and the main loop runs — hence the `stage` fixture.
"""

import pytest

from gi.repository import GLib, Gtk

from roboterm.panes import PaneFrame, PaneManager
from roboterm.terminal import TerminalWidget


class Stage:
    """A realized window used to drive VTE parsing from the main loop."""

    def __init__(self, window: Gtk.Window):
        self._window = window

    def show(self, widget) -> None:
        self._window.set_child(widget)
        self._window.present()
        self.pump()

    def pump(self, ms: int = 250) -> None:
        loop = GLib.MainLoop()
        GLib.timeout_add(ms, lambda: (loop.quit(), GLib.SOURCE_REMOVE)[1])
        loop.run()


@pytest.fixture
def stage():
    if not Gtk.init_check():
        pytest.skip("no display available")
    window = Gtk.Window()
    window.set_default_size(400, 200)
    try:
        yield Stage(window)
    finally:
        window.destroy()


@pytest.fixture
def no_spawn(monkeypatch):
    """Keep PaneManager from launching real shells."""
    monkeypatch.setattr(TerminalWidget, "spawn_shell", lambda self, cwd=None: None)


def _osc_title(title: str) -> bytes:
    return f"\033]0;{title}\a".encode()


def _osc_cwd(path: str) -> bytes:
    return f"\033]7;file://localhost{path}\033\\".encode()


# ── TerminalWidget ────────────────────────────────────────────────────────────

class TestTerminalWidgetTitle:
    def test_starts_empty(self, tmp_config, stage):
        term = TerminalWidget()
        stage.show(term)
        assert term.title == ""

    def test_osc_title_updates_title(self, tmp_config, stage):
        term = TerminalWidget()
        stage.show(term)
        term.vte.feed(_osc_title("my prompt"))
        stage.pump()
        assert term.title == "my prompt"

    def test_osc_title_emits_signal(self, tmp_config, stage):
        term = TerminalWidget()
        stage.show(term)
        seen = []
        term.connect("title-changed", lambda t: seen.append(t.title))
        term.vte.feed(_osc_title("first") + _osc_title("second"))
        stage.pump()
        assert seen[-1] == "second"

    def test_cwd_is_used_when_no_window_title(self, tmp_config, stage):
        term = TerminalWidget()
        stage.show(term)
        term.vte.feed(_osc_cwd("/usr/local/lib"))
        stage.pump()
        assert term.title == "lib"

    def test_window_title_wins_over_cwd(self, tmp_config, stage):
        term = TerminalWidget()
        stage.show(term)
        term.vte.feed(_osc_cwd("/usr/local/lib") + _osc_title("explicit"))
        stage.pump()
        assert term.title == "explicit"


# ── PaneFrame ─────────────────────────────────────────────────────────────────

class TestPaneFrameTitle:
    def test_titlebar_follows_terminal(self, tmp_config, stage):
        term  = TerminalWidget()
        frame = PaneFrame(term)
        stage.show(frame)
        term.vte.feed(_osc_title("pane title"))
        stage.pump()
        assert frame._title_label.get_label() == "pane title"


# ── PaneManager ───────────────────────────────────────────────────────────────

class TestPaneManagerTitle:
    def test_title_is_empty_without_active_pane(self, tmp_config, no_spawn, stage):
        pm = PaneManager()
        stage.show(pm)
        assert pm.title == ""

    def test_title_follows_active_pane(self, tmp_config, no_spawn, stage):
        pm = PaneManager()
        stage.show(pm)
        term = pm.get_first_child().terminal
        term.emit("focus-grabbed")
        term.vte.feed(_osc_title("active pane"))
        stage.pump()
        assert pm.title == "active pane"

    def test_emits_title_changed_for_active_pane(self, tmp_config, no_spawn, stage):
        pm = PaneManager()
        stage.show(pm)
        term = pm.get_first_child().terminal
        term.emit("focus-grabbed")
        seen = []
        pm.connect("title-changed", lambda p: seen.append(p.title))
        term.vte.feed(_osc_title("active pane"))
        stage.pump()
        assert seen[-1] == "active pane"

    def test_inactive_pane_does_not_change_manager_title(self, tmp_config, no_spawn, stage):
        pm = PaneManager()
        stage.show(pm)
        first, second = _split(pm, stage)

        first.emit("focus-grabbed")
        first.vte.feed(_osc_title("one"))
        second.vte.feed(_osc_title("two"))
        stage.pump()

        assert pm.title == "one"

    def test_focus_change_switches_manager_title(self, tmp_config, no_spawn, stage):
        pm = PaneManager()
        stage.show(pm)
        first, second = _split(pm, stage)

        first.emit("focus-grabbed")
        first.vte.feed(_osc_title("one"))
        second.vte.feed(_osc_title("two"))
        stage.pump()

        seen = []
        pm.connect("title-changed", lambda p: seen.append(p.title))
        second.emit("focus-grabbed")

        assert pm.title == "two"
        assert seen == ["two"]


def _split(pm: PaneManager, stage: Stage) -> tuple[TerminalWidget, TerminalWidget]:
    """Split the manager once and return (original, new) terminals."""
    first = pm.get_first_child().terminal
    first.emit("focus-grabbed")
    pm.split_active(Gtk.Orientation.HORIZONTAL)
    stage.pump()
    frames = PaneManager._collect_frames(pm.get_first_child())
    second = next(f.terminal for f in frames if f.terminal is not first)
    return first, second
