from gi.repository import Gtk, Adw, GObject, Gio

from .panes import PaneManager
from .preferences import PreferencesWindow


class TabLabel(Gtk.Box):
    """A tab label widget: «Terminal N  ×»"""

    __gsignals__ = {
        "close-clicked": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, title: str):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        self._label = Gtk.Label(label=title)
        self.append(self._label)

        btn = Gtk.Button()
        btn.set_icon_name("window-close-symbolic")
        btn.add_css_class("flat")
        btn.add_css_class("circular")
        btn.set_focusable(False)
        btn.connect("clicked", lambda _: self.emit("close-clicked"))
        self.append(btn)

    def set_title(self, title: str) -> None:
        self._label.set_label(title)


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

        self._add_shortcut("<Control>comma",              self._open_preferences)
        self._add_shortcut("<Control><Shift>n",           lambda: self.get_application().new_window())
        self._add_shortcut("<Control><Shift>t",           self._new_tab)
        self._add_shortcut("<Control><Shift>a",           lambda: self._active_panes().split_auto())
        self._add_shortcut("<Control><Shift>e",           lambda: self._active_panes().split_active(Gtk.Orientation.HORIZONTAL))
        self._add_shortcut("<Control><Shift>o",           lambda: self._active_panes().split_active(Gtk.Orientation.VERTICAL))
        self._add_shortcut("<Control><Shift>bracketright",lambda: self._active_panes().rotate_cw())
        self._add_shortcut("<Control><Shift>bracketleft", lambda: self._active_panes().rotate_ccw())
        self._add_shortcut("<Control><Shift>w",           lambda: self._active_panes().close_active())
        self._add_shortcut("<Control>Page_Up",            lambda: self._notebook.prev_page())
        self._add_shortcut("<Control>Page_Down",          lambda: self._notebook.next_page())

    # ── Tab management ────────────────────────────────────────────────────────

    def _new_tab(self) -> None:
        self._tab_count += 1
        title = f"Terminal {self._tab_count}"

        panes = PaneManager()
        panes.connect("all-closed", self._on_tab_all_closed)
        panes.connect("new-tab",    lambda _p: self._new_tab())
        panes.connect("new-window", lambda _p: self.get_application().new_window())

        label = TabLabel(title)
        label.connect("close-clicked", lambda _lbl, p=panes: self._close_tab_for_panes(p))

        idx = self._notebook.append_page(panes, label)
        self._notebook.set_tab_reorderable(panes, True)
        self._notebook.set_current_page(idx)
        self._update_tab_bar_visibility()
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

    def _on_tab_all_closed(self, panes: PaneManager) -> None:
        self._close_tab_for_panes(panes)

    def _on_switch_page(self, _nb, page, _idx) -> None:
        if isinstance(page, PaneManager):
            page.focus_active()

    def _active_panes(self) -> PaneManager | None:
        return self._notebook.get_nth_page(self._notebook.get_current_page())

    def _update_tab_bar_visibility(self) -> None:
        self._notebook.set_show_tabs(self._notebook.get_n_pages() > 1)

    def _open_preferences(self) -> None:
        PreferencesWindow(transient_for=self).present()

    # ── Shortcuts ─────────────────────────────────────────────────────────────

    def _add_shortcut(self, accel: str, cb) -> None:
        trigger  = Gtk.ShortcutTrigger.parse_string(accel)
        action   = Gtk.CallbackAction.new(lambda *_: cb() or True)
        shortcut = Gtk.Shortcut(trigger=trigger, action=action)
        ctrl     = Gtk.ShortcutController()
        ctrl.set_scope(Gtk.ShortcutScope.GLOBAL)
        ctrl.add_shortcut(shortcut)
        self.add_controller(ctrl)
