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

from gi.repository import Gtk, Adw, GLib, Gio, Gdk

from .panes import PaneManager
from .preferences import PreferencesWindow
from .settings import Settings


def _accel_keyvals(keyval: int, mods) -> set:
    """Every keyval a key press for this accelerator can arrive as.

    An accelerator names the unshifted key — `<Meta><Shift>backslash` — but the
    event GDK delivers for it carries the *shifted* keyval, `bar`. A table keyed
    only on the accelerator's own keyval therefore never matches any binding
    whose key is punctuation (the tab and rotate defaults, say). Ask the keymap
    what that key produces under these modifiers and accept that too.
    """
    keyvals = {keyval}
    display = Gdk.Display.get_default()
    if display is None:
        return keyvals
    found, keys = display.map_keyval(keyval)
    if found and keys:
        ok, shifted, *_ = display.translate_key(keys[0].keycode, mods, keys[0].group)
        if ok:
            keyvals.add(shifted)
    return keyvals


class TerminalWindow(Adw.ApplicationWindow):
    def __init__(self, app, *, initial_tab: bool = True):
        """A window with one tab, or with none when a dragged-out tab is on its
        way in (see `_on_create_window`)."""
        super().__init__(application=app, title="Terminal")
        self.set_default_size(900, 600)

        header = Adw.HeaderBar()

        menu_model = Gio.Menu()

        win_section = Gio.Menu()
        win_section.append("New Window",    "win.new-window")
        win_section.append("New Tab",       "win.new-tab")
        win_section.append("Show All Tabs", "win.tab-overview")
        menu_model.append_section(None, win_section)

        split_section = Gio.Menu()
        split_section.append("Split Auto",  "win.split-auto")
        split_section.append("Split Right", "win.split-right")
        split_section.append("Split Down",  "win.split-down")
        menu_model.append_section(None, split_section)

        maximize_section = Gio.Menu()
        maximize_section.append("Toggle Maximize", "win.maximize-pane")
        menu_model.append_section(None, maximize_section)

        rotate_section = Gio.Menu()
        rotate_section.append("Rotate Clockwise",        "win.rotate-cw")
        rotate_section.append("Rotate Counterclockwise", "win.rotate-ccw")
        menu_model.append_section(None, rotate_section)

        close_section = Gio.Menu()
        close_section.append("Close Pane", "win.close-pane")
        menu_model.append_section(None, close_section)

        prefs_section = Gio.Menu()
        prefs_section.append("Preferences", "win.preferences")
        menu_model.append_section(None, prefs_section)

        win_actions = {
            "new-window":  lambda: self.get_application().new_window(),
            "new-tab":     lambda: self._new_tab(),
            "tab-overview": lambda: self._toggle_overview(),
            "split-auto":  lambda: self._active_panes().split_auto(),
            "split-right": lambda: self._active_panes().split_active(Gtk.Orientation.HORIZONTAL),
            "split-down":  lambda: self._active_panes().split_active(Gtk.Orientation.VERTICAL),
            "maximize-pane": lambda: self._active_panes().toggle_maximize_active(),
            "rotate-cw":   lambda: self._active_panes().rotate_cw(),
            "rotate-ccw":  lambda: self._active_panes().rotate_ccw(),
            "close-pane":  lambda: self._active_panes().close_active(),
            "preferences": lambda: self._open_preferences(),
        }
        for name, cb in win_actions.items():
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _a, _p, fn=cb: fn())
            self.add_action(action)

        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")
        menu_btn.set_menu_model(menu_model)
        header.pack_end(menu_btn)

        self._tabs = Adw.TabView()
        self._tabs.connect("notify::selected-page", self._on_page_selected)
        self._tabs.connect("close-page", self._on_close_page)
        self._tabs.connect("page-attached", self._on_page_attached)
        self._tabs.connect("page-detached", self._on_page_detached)
        self._tabs.connect("create-window", self._on_create_window)

        # Adw.TabBar draws the tabs themselves (label, close button, reordering,
        # drag-and-drop) and hides itself while there is only one page, which is
        # why nothing here sets a tab label widget or toggles the strip.
        tab_bar = Adw.TabBar(view=self._tabs)

        # Shows the tab count, and opens the overview through the action group
        # Adw.TabOverview installs on the widgets below it.
        header.pack_end(Adw.TabButton(view=self._tabs, action_name="overview.open"))

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)
        toolbar_view.add_top_bar(tab_bar)
        toolbar_view.set_content(self._tabs)

        # libadwaita expects the overview to be the window's direct child, with
        # everything else hanging off it as its child.
        self._overview = Adw.TabOverview(
            view=self._tabs,
            child=toolbar_view,
            enable_new_tab=True,
            enable_search=True,
        )
        self._overview.connect("create-tab", lambda _o: self._new_tab())
        self.set_content(self._overview)

        self._tab_count = 0
        self._pane_handlers: dict[PaneManager, list[int]] = {}
        if initial_tab:
            self._new_tab()

        self._setup_window_actions()
        self._setup_key_handler()

    # ── Tab management ────────────────────────────────────────────────────────

    def _new_tab(self) -> Adw.TabPage:
        """Open a tab and return its page — the overview's "New Tab" button
        takes the page as the return value of its `create-tab` handler."""
        self._tab_count += 1

        panes = PaneManager()
        panes.default_title = f"Terminal {self._tab_count}"

        # Appending wires the pane signals up — see _on_page_attached.
        page = self._tabs.append(panes)
        self._set_page_title(page, panes.default_title)
        self._tabs.set_selected_page(page)
        self._update_window_title()
        panes.focus_active()
        return page

    def _on_page_attached(self, _view, page: Adw.TabPage, _pos: int) -> None:
        """Connect a tab's PaneManager to *this* window.

        Tabs are wired here rather than in `_new_tab` because a tab can also
        arrive by being dragged in from another window, and the handlers it
        carried over pointed at that one.
        """
        panes = page.get_child()
        self._pane_handlers[panes] = [
            panes.connect("all-closed",    self._on_tab_all_closed),
            panes.connect("new-tab",       lambda _p: self._new_tab()),
            panes.connect("new-window",    lambda _p: self.get_application().new_window()),
            panes.connect("title-changed", self._on_panes_title_changed),
        ]

    def _on_page_detached(self, view: Adw.TabView, page: Adw.TabPage, _pos: int) -> None:
        panes = page.get_child()
        for handler in self._pane_handlers.pop(panes, []):
            panes.disconnect(handler)
        if view.get_n_pages() == 0:
            # Don't tear the window down from in here: the page may be in the
            # middle of a transfer into another window, and destroying this
            # widget tree now would take it with us. Let the move land first.
            GLib.idle_add(self._close_if_empty)

    def _close_if_empty(self) -> bool:
        if self._tabs.get_n_pages() == 0:
            self.close()
        return GLib.SOURCE_REMOVE

    def _on_create_window(self, _view) -> Adw.TabView:
        """A tab dropped onto the desktop: hand back the tab view of a new,
        empty window for libadwaita to move the page into."""
        return self.get_application().new_window(with_tab=False)._tabs

    def _on_tab_all_closed(self, panes: PaneManager) -> None:
        if (page := self._tabs.get_page(panes)) is not None:
            self._tabs.close_page(page)

    def _on_close_page(self, view: Adw.TabView, page: Adw.TabPage) -> bool:
        """Close *page* — from the tab's × button or from `close_page` above.

        Taking the signal (returning True) means finishing the close ourselves;
        doing it synchronously is fine since nothing here asks the user first.
        The window closes with its last tab, via `_on_page_detached`.
        """
        view.close_page_finish(page, True)
        self._update_window_title()
        return True

    def _toggle_overview(self) -> None:
        self._overview.set_open(not self._overview.get_open())

    def _on_page_selected(self, _view, _pspec) -> None:
        if panes := self._active_panes():
            self._update_window_title(panes)
            panes.focus_active()

    # ── Titles ────────────────────────────────────────────────────────────────

    def _set_page_title(self, page: Adw.TabPage, title: str) -> None:
        page.set_title(title)
        # The tooltip carries the full title for tabs the strip has ellipsized.
        # It is parsed as markup, so a shell-set title has to be escaped.
        page.set_tooltip(GLib.markup_escape_text(title))

    def _on_panes_title_changed(self, panes: PaneManager) -> None:
        page = self._tabs.get_page(panes)
        if page is not None:
            self._set_page_title(page, panes.title or panes.default_title)
        if panes is self._active_panes():
            self._update_window_title(panes)

    def _update_window_title(self, panes: PaneManager | None = None) -> None:
        if panes is None:
            panes = self._active_panes()
        title = panes.title if isinstance(panes, PaneManager) else ""
        self.set_title(title or "Terminal")

    def _active_panes(self) -> PaneManager | None:
        page = self._tabs.get_selected_page()
        return page.get_child() if page is not None else None

    def _open_preferences(self) -> None:
        PreferencesWindow(transient_for=self).present()

    # ── Actions (used by macOS menu bar) ─────────────────────────────────────

    def _setup_window_actions(self) -> None:
        def add(name, cb):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda *_: cb())
            self.add_action(action)

        def with_panes(cb):
            def fn():
                if p := self._active_panes():
                    cb(p)
            return fn

        add("new-tab",     self._new_tab)
        add("close-pane",  with_panes(lambda p: p.close_active()))
        add("preferences", self._open_preferences)
        add("split-right", with_panes(lambda p: p.split_active(Gtk.Orientation.HORIZONTAL)))
        add("split-down",  with_panes(lambda p: p.split_active(Gtk.Orientation.VERTICAL)))
        add("split-auto",  with_panes(lambda p: p.split_auto()))
        add("maximize-pane", with_panes(lambda p: p.toggle_maximize_active()))
        add("rotate-cw",   with_panes(lambda p: p.rotate_cw()))
        add("rotate-ccw",  with_panes(lambda p: p.rotate_ccw()))
        add("prev-tab",    self._tabs.select_previous_page)
        add("next-tab",    self._tabs.select_next_page)
        add("tab-overview", self._toggle_overview)

        def _copy():
            if (p := self._active_panes()) and p.active:
                p.active.copy_clipboard()

        def _paste():
            if (p := self._active_panes()) and p.active:
                p.active.paste_clipboard()

        add("copy",  _copy)
        add("paste", _paste)

    # ── Shortcuts ─────────────────────────────────────────────────────────────

    def _setup_key_handler(self) -> None:
        """Intercept keys before VTE via CAPTURE phase — needed on all platforms."""
        self._key_table = self._build_key_table()
        Settings.get().connect_changed(self._reload_key_table)
        ctrl = Gtk.EventControllerKey()
        ctrl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(ctrl)

    def _reload_key_table(self) -> None:
        self._key_table = self._build_key_table()

    def _build_key_table(self) -> dict:
        """Return {(modifier_mask, keyval): callback} from current settings."""
        actions = {
            "preferences": self._open_preferences,
            "quit":        lambda: self.get_application().quit(),
            "new-window":  lambda: self.get_application().new_window(),
            "new-tab":     self._new_tab,
            "close-pane":  lambda: (p := self._active_panes()) and p.close_active(),
            "split-auto":  lambda: (p := self._active_panes()) and p.split_auto(),
            "split-right": lambda: (p := self._active_panes()) and p.split_active(Gtk.Orientation.HORIZONTAL),
            "split-down":  lambda: (p := self._active_panes()) and p.split_active(Gtk.Orientation.VERTICAL),
            "maximize-pane": lambda: (p := self._active_panes()) and p.toggle_maximize_active(),
            "prev-tab":    self._tabs.select_previous_page,
            "next-tab":    self._tabs.select_next_page,
            "tab-overview": self._toggle_overview,
            "rotate-cw":   lambda: (p := self._active_panes()) and p.rotate_cw(),
            "rotate-ccw":  lambda: (p := self._active_panes()) and p.rotate_ccw(),
        }
        table = {}
        for name, accel in Settings.get().get_keybindings().items():
            if not accel or name not in actions:
                continue
            *_, keyval, mods = Gtk.accelerator_parse(accel)
            if not keyval:
                continue
            for kv in _accel_keyvals(keyval, mods):
                table[(mods, Gdk.keyval_to_lower(kv))] = actions[name]
        return table

    def _on_key_pressed(self, _ctrl, keyval, _keycode, state) -> bool:
        mods = state & (Gdk.ModifierType.META_MASK    | Gdk.ModifierType.SHIFT_MASK |
                        Gdk.ModifierType.ALT_MASK      | Gdk.ModifierType.CONTROL_MASK)
        kv = Gdk.keyval_to_lower(keyval)
        if cb := self._key_table.get((mods, kv)):
            cb()
            return True
        return False
