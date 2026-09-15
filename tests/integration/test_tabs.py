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

"""Tab behaviour, against a real Adw.TabView.

Needs real libadwaita: the whole point is the signal contract around
`close-page` (a handler that takes the signal must finish the close itself)
and `Adw.TabPage`'s markup tooltip — neither survives a mocked gi.
"""

import pytest

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from roboterm.settings import Settings, _default_keybindings
from roboterm.window import TerminalWindow


class _App(Adw.Application):
    """TerminalApp's window handling, without presenting anything on screen."""

    def __init__(self):
        super().__init__(
            application_id="net.folkwolf.roboterm.tests",
            flags=Gio.ApplicationFlags.NON_UNIQUE,
        )
        self.windows_made = []

    def new_window(self, *, with_tab: bool = True) -> TerminalWindow:
        win = TerminalWindow(self, initial_tab=with_tab)
        self.windows_made.append(win)
        return win


@pytest.fixture
def app():
    app = _App()
    try:
        app.register(None)
    except Exception as exc:  # no display / no session bus
        pytest.skip(f"Cannot register application: {exc}")
    return app


@pytest.fixture
def window(tmp_config, app):
    """A TerminalWindow with its one initial tab, never presented."""
    try:
        win = TerminalWindow(app)
    except Exception as exc:
        pytest.skip(f"Cannot create TerminalWindow: {exc}")
    yield win
    win.destroy()


def _titles(win) -> list:
    view = win._tabs
    return [view.get_nth_page(i).get_title() for i in range(view.get_n_pages())]


def _flush() -> None:
    """Run the idle callbacks a window teardown is deferred through.

    Two things this has to do by hand: acquire the default main context (no
    loop has ever run here, so it is unowned and nothing would be dispatched),
    and stop on a sentinel idle rather than on the context running dry, since
    an on-screen window keeps its frame clock ticking. The sentinel is queued
    at the same priority as the callbacks being waited on, so it runs last.
    """
    done = []
    GLib.idle_add(lambda: done.append(True) and False)
    context = GLib.MainContext.default()
    context.acquire()
    try:
        for _ in range(200):
            if done:
                return
            context.iteration(False)
    finally:
        context.release()
    raise AssertionError("main loop never reached the sentinel idle")


def _find(widget, kind):
    """The first descendant of *widget* of type *kind*, depth first."""
    child = widget.get_first_child()
    while child is not None:
        if isinstance(child, kind):
            return child
        if (found := _find(child, kind)) is not None:
            return found
        child = child.get_next_sibling()
    return None


def _overview_accel(win) -> str:
    """The tab-overview default for whichever platform the tests run on."""
    return _default_keybindings()["tab-overview"]


def _watch_for_close(win) -> list:
    """Record `win` being closed, in a list that fills in later.

    The window has to be on screen for this: `Gtk.Window.close()` is a no-op
    until one is. The signal to watch is close-request rather than destroy,
    since the destroy only follows once GTK has unmapped the window.
    """
    closed = []
    win.connect("close-request", lambda _w: closed.append(True) or False)
    win.present()
    return closed


class TestNewTab:

    def test_first_tab_exists_and_is_selected(self, window):
        assert _titles(window) == ["Terminal 1"]
        assert window._tabs.get_selected_page().get_child() is window._active_panes()

    def test_new_tab_is_appended_and_selected(self, window):
        window._new_tab()
        window._new_tab()

        assert _titles(window) == ["Terminal 1", "Terminal 2", "Terminal 3"]
        assert window._tabs.get_selected_page().get_title() == "Terminal 3"


class TestSelection:

    def test_prev_and_next_move_the_selection(self, window):
        window._new_tab()
        window._new_tab()

        assert window._tabs.select_previous_page() is True
        assert window._tabs.get_selected_page().get_title() == "Terminal 2"
        assert window._tabs.select_next_page() is True
        assert window._tabs.get_selected_page().get_title() == "Terminal 3"

    def test_selection_does_not_wrap_at_the_ends(self, window):
        window._new_tab()

        assert window._tabs.select_next_page() is False
        window._tabs.select_previous_page()
        assert window._tabs.select_previous_page() is False


class TestTitles:

    def test_tooltip_escapes_markup_from_the_shell(self, window):
        page = window._tabs.get_selected_page()

        window._set_page_title(page, "make && ./run <file>")

        assert page.get_title() == "make && ./run <file>"
        assert page.get_tooltip() == "make &amp;&amp; ./run &lt;file&gt;"

    def test_empty_pane_title_falls_back_to_the_tab_name(self, window):
        window._new_tab()
        panes = window._active_panes()
        page = window._tabs.get_page(panes)
        window._set_page_title(page, "something the shell set")

        # A pane that has reported no title at all: PaneManager.title is ""
        window._on_panes_title_changed(panes)

        assert page.get_title() == "Terminal 2"


class TestClosing:

    def test_closing_a_tab_leaves_the_others(self, window):
        window._new_tab()
        window._new_tab()
        page = window._tabs.get_nth_page(1)

        window._tabs.close_page(page)

        assert _titles(window) == ["Terminal 1", "Terminal 3"]

    def test_all_closed_from_the_pane_manager_closes_its_tab(self, window):
        window._new_tab()
        panes = window._tabs.get_nth_page(0).get_child()

        panes.emit("all-closed")

        assert _titles(window) == ["Terminal 2"]

    def test_closing_the_last_tab_closes_the_window(self, window):
        closed = _watch_for_close(window)

        window._tabs.close_page(window._tabs.get_selected_page())
        _flush()

        assert window._tabs.get_n_pages() == 0
        assert closed == [True]

    def test_closing_a_tab_unwires_its_pane_manager(self, window):
        window._new_tab()
        panes = window._tabs.get_nth_page(0).get_child()

        window._tabs.close_page(window._tabs.get_nth_page(0))

        assert panes not in window._pane_handlers


class TestDragToNewWindow:
    """`create-window` plus the page transfer libadwaita performs after it."""

    def test_create_window_hands_back_an_empty_new_windows_view(self, window):
        view = window._on_create_window(window._tabs)

        new_window = window.get_application().windows_made[-1]
        assert view is new_window._tabs
        assert view.get_n_pages() == 0
        assert view is not window._tabs

    def test_a_transferred_tab_is_driven_by_its_new_window(self, window):
        window._new_tab()
        page = window._tabs.get_nth_page(1)
        panes = page.get_child()
        new_window = window.get_application().new_window(with_tab=False)

        window._tabs.transfer_page(page, new_window._tabs, 0)

        assert _titles(window) == ["Terminal 1"]
        assert _titles(new_window) == ["Terminal 2"]
        assert panes not in window._pane_handlers

        # The tab now answers to the window it landed in, not the one it left.
        panes.emit("all-closed")
        assert _titles(new_window) == []
        assert _titles(window) == ["Terminal 1"]

    def test_a_transferred_tab_keeps_its_fallback_name(self, window):
        page = window._tabs.get_selected_page()
        panes = page.get_child()
        new_window = window.get_application().new_window(with_tab=False)
        window._tabs.transfer_page(page, new_window._tabs, 0)
        window._set_page_title(page, "something the shell set")

        new_window._on_panes_title_changed(panes)

        assert page.get_title() == "Terminal 1"

    def test_dragging_out_the_last_tab_closes_the_window_behind_it(self, window):
        closed = _watch_for_close(window)
        page = window._tabs.get_selected_page()
        new_window = window.get_application().new_window(with_tab=False)

        window._tabs.transfer_page(page, new_window._tabs, 0)
        _flush()

        assert closed == [True]
        assert _titles(new_window) == ["Terminal 1"]


class TestOverview:
    """The header's Adw.TabButton and the Adw.TabOverview it opens."""

    def test_the_overview_wraps_the_window_content(self, window):
        assert window.get_content() is window._overview
        assert window._overview.get_view() is window._tabs
        assert isinstance(window._overview.get_child(), Adw.ToolbarView)

    def test_the_header_button_opens_the_overview(self, window):
        button = _find(window, Adw.TabButton)

        assert button is not None, "no Adw.TabButton in the window"
        assert button.get_view() is window._tabs
        # The action group Adw.TabOverview installs below itself.
        assert button.get_action_name() == "overview.open"

    def test_the_menus_action_toggles_it(self, window):
        action = window.lookup_action("tab-overview")

        assert action is not None, "win.tab-overview is what both menus point at"
        action.activate(None)
        assert window._overview.get_open() is True

    def test_the_overviews_new_tab_button_opens_a_tab(self, window):
        page = window._overview.emit("create-tab")

        assert _titles(window) == ["Terminal 1", "Terminal 2"]
        assert window._tabs.get_selected_page() is page


class TestKeyTable:
    """`_build_key_table`, against a real GDK keymap."""

    def _entry(self, window, accel):
        *_, keyval, mods = Gtk.accelerator_parse(accel)
        return window._key_table.get((mods, Gdk.keyval_to_lower(keyval)))

    def test_the_overview_binding_is_in_the_table(self, window):
        assert self._entry(window, _overview_accel(window)) is not None

    def test_a_shifted_punctuation_key_matches_what_gdk_delivers(self, window):
        """Cmd/Ctrl+Shift+\\ arrives as `bar`, not `backslash`."""
        accel = _overview_accel(window)
        *_, keyval, mods = Gtk.accelerator_parse(accel)
        ok, keys = Gdk.Display.get_default().map_keyval(keyval)
        if not (ok and keys):
            pytest.skip("keymap has no keycode for this key")
        delivered = Gdk.Display.get_default().translate_key(
            keys[0].keycode, mods, keys[0].group)[1]

        assert window._key_table.get((mods, Gdk.keyval_to_lower(delivered))) is not None

    def test_it_opens_and_closes_the_overview(self, window):
        toggle = self._entry(window, _overview_accel(window))

        toggle()
        assert window._overview.get_open() is True
        toggle()
        assert window._overview.get_open() is False

    def test_rebinding_it_rebuilds_the_table(self, window, tmp_config):
        settings = Settings.get()
        settings.set_value("keybindings", {"tab-overview": "<Control><Shift>F9"})

        assert self._entry(window, "<Control><Shift>F9") is not None
