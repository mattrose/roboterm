from gi.repository import Gtk, Adw, GObject, Gio, Gdk

from .panes import PaneManager
from .preferences import PreferencesWindow
from .settings import Settings


class TabLabel(Gtk.Box):
    """A tab label widget: «Terminal N  ×»"""

    __gsignals__ = {
        "close-clicked": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, title: str):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        self._default_title = title
        self._label = Gtk.Label(label=title)
        self._label.set_ellipsize(3)   # Pango.EllipsizeMode.END
        self._label.set_max_width_chars(24)
        self.append(self._label)

        btn = Gtk.Button()
        btn.set_icon_name("window-close-symbolic")
        btn.add_css_class("flat")
        btn.add_css_class("circular")
        btn.set_focusable(False)
        btn.connect("clicked", lambda _: self.emit("close-clicked"))
        self.append(btn)

    def set_title(self, title: str) -> None:
        """Show *title*, falling back to the tab's original name when empty."""
        self._label.set_label(title or self._default_title)

    @property
    def title(self) -> str:
        return self._label.get_label()


class TerminalWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Terminal")
        self.set_default_size(900, 600)

        header = Adw.HeaderBar()

        menu_model = Gio.Menu()

        win_section = Gio.Menu()
        win_section.append("New Window", "win.new-window")
        win_section.append("New Tab",    "win.new-tab")
        menu_model.append_section(None, win_section)

        split_section = Gio.Menu()
        split_section.append("Split Auto",  "win.split-auto")
        split_section.append("Split Right", "win.split-right")
        split_section.append("Split Down",  "win.split-down")
        menu_model.append_section(None, split_section)

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
            "split-auto":  lambda: self._active_panes().split_auto(),
            "split-right": lambda: self._active_panes().split_active(Gtk.Orientation.HORIZONTAL),
            "split-down":  lambda: self._active_panes().split_active(Gtk.Orientation.VERTICAL),
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

        self._notebook = Gtk.Notebook()
        self._notebook.set_scrollable(True)
        self._notebook.set_show_border(False)
        self._notebook.connect("switch-page", self._on_switch_page)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)
        toolbar_view.set_content(self._notebook)
        self.set_content(toolbar_view)

        self._tab_count = 0
        self._new_tab()

        self._setup_window_actions()
        self._setup_key_handler()

    # ── Tab management ────────────────────────────────────────────────────────

    def _new_tab(self) -> None:
        self._tab_count += 1
        title = f"Terminal {self._tab_count}"

        panes = PaneManager()
        panes.connect("all-closed",    self._on_tab_all_closed)
        panes.connect("new-tab",       lambda _p: self._new_tab())
        panes.connect("new-window",    lambda _p: self.get_application().new_window())
        panes.connect("title-changed", self._on_panes_title_changed)

        label = TabLabel(title)
        label.connect("close-clicked", lambda _lbl, p=panes: self._close_tab_for_panes(p))

        idx = self._notebook.append_page(panes, label)
        self._notebook.set_tab_reorderable(panes, True)
        self._notebook.set_current_page(idx)
        self._update_tab_bar_visibility()
        self._update_window_title()
        panes.focus_active()

    def _close_tab_for_panes(self, panes: PaneManager) -> None:
        idx = self._notebook.page_num(panes)
        if idx == -1:
            return
        self._notebook.remove_page(idx)
        if self._notebook.get_n_pages() == 0:
            self.get_application().quit()
        else:
            self._update_tab_bar_visibility()
            self._update_window_title()

    def _on_tab_all_closed(self, panes: PaneManager) -> None:
        self._close_tab_for_panes(panes)

    def _on_switch_page(self, _nb, page, _idx) -> None:
        if isinstance(page, PaneManager):
            self._update_window_title(page)
            page.focus_active()

    # ── Titles ────────────────────────────────────────────────────────────────

    def _on_panes_title_changed(self, panes: PaneManager) -> None:
        label = self._notebook.get_tab_label(panes)
        if isinstance(label, TabLabel):
            label.set_title(panes.title)
        if panes is self._active_panes():
            self._update_window_title(panes)

    def _update_window_title(self, panes: PaneManager | None = None) -> None:
        if panes is None:
            panes = self._active_panes()
        title = panes.title if isinstance(panes, PaneManager) else ""
        self.set_title(title or "Terminal")

    def _active_panes(self) -> PaneManager | None:
        return self._notebook.get_nth_page(self._notebook.get_current_page())

    def _update_tab_bar_visibility(self) -> None:
        self._notebook.set_show_tabs(self._notebook.get_n_pages() > 1)

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
        add("rotate-cw",   with_panes(lambda p: p.rotate_cw()))
        add("rotate-ccw",  with_panes(lambda p: p.rotate_ccw()))
        add("prev-tab",    self._notebook.prev_page)
        add("next-tab",    self._notebook.next_page)

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
            "new-window":  lambda: self.get_application().new_window(),
            "new-tab":     self._new_tab,
            "close-pane":  lambda: (p := self._active_panes()) and p.close_active(),
            "split-auto":  lambda: (p := self._active_panes()) and p.split_auto(),
            "split-right": lambda: (p := self._active_panes()) and p.split_active(Gtk.Orientation.HORIZONTAL),
            "split-down":  lambda: (p := self._active_panes()) and p.split_active(Gtk.Orientation.VERTICAL),
            "prev-tab":    self._notebook.prev_page,
            "next-tab":    self._notebook.next_page,
            "rotate-cw":   lambda: (p := self._active_panes()) and p.rotate_cw(),
            "rotate-ccw":  lambda: (p := self._active_panes()) and p.rotate_ccw(),
        }
        table = {}
        for name, accel in Settings.get().get_keybindings().items():
            if not accel or name not in actions:
                continue
            *_, keyval, mods = Gtk.accelerator_parse(accel)
            if keyval:
                table[(mods, Gdk.keyval_to_lower(keyval))] = actions[name]
        return table

    def _on_key_pressed(self, _ctrl, keyval, _keycode, state) -> bool:
        mods = state & (Gdk.ModifierType.META_MASK    | Gdk.ModifierType.SHIFT_MASK |
                        Gdk.ModifierType.ALT_MASK      | Gdk.ModifierType.CONTROL_MASK)
        kv = Gdk.keyval_to_lower(keyval)
        if cb := self._key_table.get((mods, kv)):
            cb()
            return True
        return False
