"""Maximizing a pane: detach it from the split tree, then put it back."""

import pytest

from gi.repository import Gtk

from roboterm.panes import PaneManager
from roboterm.terminal import TerminalWidget


@pytest.fixture
def no_spawn(monkeypatch):
    """Keep PaneManager from launching real shells."""
    monkeypatch.setattr(TerminalWidget, "spawn_shell", lambda self, cwd=None: None)


@pytest.fixture
def panes(tmp_config, no_spawn):
    try:
        return PaneManager()
    except Exception as exc:            # no GTK display, no widgets
        pytest.skip(f"Cannot create PaneManager: {exc}")


def _split(panes: PaneManager, orientation=Gtk.Orientation.HORIZONTAL):
    """Split the active pane and return the newly created terminal."""
    before = {f.terminal for f in PaneManager._collect_frames(panes._root())}
    panes.split_active(orientation)
    after = {f.terminal for f in PaneManager._collect_frames(panes._root())}
    return (after - before).pop()


def _frames(panes: PaneManager) -> list:
    return PaneManager._collect_frames(panes._root())


class TestMaximize:
    def test_single_pane_cannot_be_maximized(self, panes):
        term = panes.get_first_child().terminal
        term.emit("focus-grabbed")
        panes.toggle_maximize_active()
        assert panes.maximized is False

    def test_maximize_leaves_only_the_active_frame_in_the_tab(self, panes):
        first = panes.get_first_child().terminal
        first.emit("focus-grabbed")
        second = _split(panes)
        second.emit("focus-grabbed")

        panes.toggle_maximize_active()

        assert panes.maximized is True
        assert panes.get_first_child() is second.get_parent()
        assert panes.get_first_child().get_next_sibling() is None

    def test_toggle_twice_restores_the_tree(self, panes):
        first = panes.get_first_child().terminal
        first.emit("focus-grabbed")
        second = _split(panes)
        second.emit("focus-grabbed")
        root = panes.get_first_child()

        panes.toggle_maximize_active()
        panes.toggle_maximize_active()

        assert panes.maximized is False
        assert panes.get_first_child() is root
        assert {f.terminal for f in _frames(panes)} == {first, second}

    def test_restore_puts_the_frame_back_in_its_own_slot(self, panes):
        first = panes.get_first_child().terminal
        first.emit("focus-grabbed")
        second = _split(panes)
        paned  = second.get_parent().get_parent()
        side   = "start" if paned.get_start_child() is second.get_parent() else "end"

        second.emit("focus-grabbed")
        panes.toggle_maximize_active()
        panes.toggle_maximize_active()

        restored = (paned.get_start_child() if side == "start" else paned.get_end_child())
        assert restored is second.get_parent()

    def test_maximizing_a_second_pane_restores_the_first(self, panes):
        first = panes.get_first_child().terminal
        first.emit("focus-grabbed")
        second = _split(panes)

        second.emit("focus-grabbed")
        panes.toggle_maximize_active()
        assert panes.get_first_child() is second.get_parent()

        panes.toggle_maximize_active()
        first.emit("focus-grabbed")
        panes.toggle_maximize_active()

        assert panes.get_first_child() is first.get_parent()

    def test_context_menu_signal_maximizes_that_pane(self, panes):
        first = panes.get_first_child().terminal
        first.emit("focus-grabbed")
        second = _split(panes)
        second.emit("focus-grabbed")

        # Right-clicking the *other* pane maximizes that one, not the focused one.
        first.emit("maximize-pane")

        assert panes.maximized is True
        assert panes.get_first_child() is first.get_parent()

    def test_titlebar_shows_maximized_indicator(self, panes):
        first = panes.get_first_child().terminal
        first.emit("focus-grabbed")
        second = _split(panes)
        second.emit("focus-grabbed")

        panes.toggle_maximize_active()
        assert second.get_parent()._maximized_icon.get_visible() is True

        panes.toggle_maximize_active()
        assert second.get_parent()._maximized_icon.get_visible() is False


class TestMaximizeInteractions:
    def test_split_restores_first(self, panes):
        first = panes.get_first_child().terminal
        first.emit("focus-grabbed")
        second = _split(panes)
        second.emit("focus-grabbed")
        panes.toggle_maximize_active()

        panes.split_active(Gtk.Orientation.VERTICAL)

        assert panes.maximized is False
        assert len(_frames(panes)) == 3

    def test_rotate_restores_first(self, panes):
        first = panes.get_first_child().terminal
        first.emit("focus-grabbed")
        second = _split(panes)
        second.emit("focus-grabbed")
        panes.toggle_maximize_active()

        panes.rotate_cw()

        assert panes.maximized is False
        assert {f.terminal for f in _frames(panes)} == {first, second}

    def test_closing_the_maximized_pane_restores_and_closes(self, panes):
        first = panes.get_first_child().terminal
        first.emit("focus-grabbed")
        second = _split(panes)
        second.emit("focus-grabbed")
        panes.toggle_maximize_active()

        panes.close_active()

        assert panes.maximized is False
        assert {f.terminal for f in _frames(panes)} == {first}

    def test_titlebars_are_visible_while_maximized(self, panes):
        """`auto` hides titlebars for a lone pane, but a maximized pane is not
        alone — the other panes are just hidden, so keep them visible."""
        first = panes.get_first_child().terminal
        first.emit("focus-grabbed")
        second = _split(panes)
        second.emit("focus-grabbed")

        panes.toggle_maximize_active()

        assert second.get_parent()._titlebar.get_visible() is True
