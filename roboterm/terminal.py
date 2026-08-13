import os
import sys
import weakref

from gi.repository import Gtk, Vte, GLib, GObject, Gdk, Gio

_MACOS = sys.platform == "darwin"

_URL_PATTERN = r"https?://[-a-zA-Z0-9+&@#/%?=~_|!:,.;]*[-a-zA-Z0-9+&@#/%=~_|]"

from .settings import Settings


class TerminalWidget(Gtk.ScrolledWindow):
    """A self-contained VTE terminal wrapped in a ScrolledWindow.

    Emits:
        child-exited(status)  — forwarded from Vte.Terminal
        focus-grabbed()       — fired when the inner VTE receives focus
        split-right()         — user chose "Split Right" from context menu
        split-down()          — user chose "Split Down" from context menu
        close-pane()          — user chose "Close Pane" from context menu
        maximize-pane()       — user chose "Toggle Maximize" from context menu
    """

    __gsignals__ = {
        "child-exited":  (GObject.SignalFlags.RUN_LAST, None, (int,)),
        "focus-grabbed": (GObject.SignalFlags.RUN_LAST, None, ()),
        "split-right":   (GObject.SignalFlags.RUN_LAST, None, ()),
        "split-down":    (GObject.SignalFlags.RUN_LAST, None, ()),
        "close-pane":    (GObject.SignalFlags.RUN_LAST, None, ()),
        "new-tab":       (GObject.SignalFlags.RUN_LAST, None, ()),
        "new-window":    (GObject.SignalFlags.RUN_LAST, None, ()),
        "split-auto":    (GObject.SignalFlags.RUN_LAST, None, ()),
        "rotate-cw":     (GObject.SignalFlags.RUN_LAST, None, ()),
        "rotate-ccw":    (GObject.SignalFlags.RUN_LAST, None, ()),
        "maximize-pane": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self):
        super().__init__()

        self.set_vexpand(True)
        self.set_hexpand(True)
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.ALWAYS)

        self._vte = Vte.Terminal()
        self._vte.set_mouse_autohide(True)
        self.set_child(self._vte)

        settings = Settings.get()
        settings.apply_to_vte(self._vte)
        vte_ref = weakref.ref(self._vte)
        def _on_settings_changed():
            vte = vte_ref()
            if vte is not None:
                settings.apply_to_vte(vte)
        settings.connect_changed(_on_settings_changed)

        self._vte.connect("child-exited", self._on_child_exited)

        focus_ctrl = Gtk.EventControllerFocus()
        focus_ctrl.connect("enter", lambda _ec: self.emit("focus-grabbed"))
        self._vte.add_controller(focus_ctrl)

        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self._vte.add_controller(key_ctrl)

        self._context_url: str | None = None
        self._url_regex = None
        self._url_tag: int = -1
        self._build_context_menu()
        self._setup_url_handling()

    # ── Public API ────────────────────────────────────────────────────────────

    def spawn_shell(self, cwd: str | None = None) -> None:
        shell = os.environ.get("SHELL", "/bin/bash")
        self.spawn([shell], cwd=cwd)

    def spawn(
        self,
        argv: list[str],
        env: list[str] | None = None,
        cwd: str | None = None,
    ) -> None:
        if env is None:
            env = [f"{k}={v}" for k, v in os.environ.items()]
        if cwd is None:
            cwd = os.path.expanduser("~")

        self._vte.spawn_async(
            Vte.PtyFlags.DEFAULT,
            cwd, argv, env,
            GLib.SpawnFlags.DEFAULT,
            None, None, -1, None,
            self._on_spawn_done,
        )

    def grab_focus(self) -> None:
        self._vte.grab_focus()

    def copy_clipboard(self) -> None:
        self._vte.copy_clipboard_format(Vte.Format.TEXT)

    def paste_clipboard(self) -> None:
        self._vte.paste_clipboard()

    @property
    def vte(self) -> Vte.Terminal:
        return self._vte

    # ── Private ───────────────────────────────────────────────────────────────

    def _build_context_menu(self) -> None:
        self._menu_with_url    = self._make_menu_model(has_url=True)
        self._menu_without_url = self._make_menu_model(has_url=False)

        popover = Gtk.PopoverMenu.new_from_model(self._menu_without_url)
        popover.set_has_arrow(False)
        popover.set_parent(self._vte)

        ag = Gio.SimpleActionGroup()

        open_url_action = Gio.SimpleAction.new("open-url", None)
        open_url_action.connect("activate",
            lambda _a, _p: self._context_url and self._open_url(self._context_url))
        ag.add_action(open_url_action)

        copy_action = Gio.SimpleAction.new("copy", None)
        copy_action.connect("activate", lambda _a, _p: self.copy_clipboard())
        ag.add_action(copy_action)

        paste_action = Gio.SimpleAction.new("paste", None)
        paste_action.connect("activate", lambda _a, _p: self.paste_clipboard())
        ag.add_action(paste_action)

        for name, signal in (
            ("new-window",    "new-window"),
            ("new-tab",       "new-tab"),
            ("split-auto",    "split-auto"),
            ("split-right",   "split-right"),
            ("split-down",    "split-down"),
            ("maximize-pane", "maximize-pane"),
            ("rotate-cw",     "rotate-cw"),
            ("rotate-ccw",    "rotate-ccw"),
            ("close-pane",    "close-pane"),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _a, _p, sig=signal: self.emit(sig))
            ag.add_action(action)

        self._vte.insert_action_group("term", ag)

        gesture = Gtk.GestureClick()
        gesture.set_button(Gdk.BUTTON_SECONDARY)
        gesture.connect("pressed", self._on_right_click, popover)
        self._vte.add_controller(gesture)

        self._popover = popover

    @staticmethod
    def _make_menu_model(has_url: bool) -> Gio.Menu:
        menu = Gio.Menu()
        if has_url:
            url_sec = Gio.Menu()
            url_sec.append("Open Link", "term.open-url")
            menu.append_section(None, url_sec)
        clip_sec = Gio.Menu()
        clip_sec.append("Copy",  "term.copy")
        clip_sec.append("Paste", "term.paste")
        menu.append_section(None, clip_sec)
        tab_sec = Gio.Menu()
        tab_sec.append("New Window", "term.new-window")
        tab_sec.append("New Tab",    "term.new-tab")
        menu.append_section(None, tab_sec)
        split_sec = Gio.Menu()
        split_sec.append("Split Auto",      "term.split-auto")
        split_sec.append("Split Right",     "term.split-right")
        split_sec.append("Split Down",      "term.split-down")
        split_sec.append("Toggle Maximize", "term.maximize-pane")
        menu.append_section(None, split_sec)
        rotate_sec = Gio.Menu()
        rotate_sec.append("Rotate Clockwise",        "term.rotate-cw")
        rotate_sec.append("Rotate Counterclockwise", "term.rotate-ccw")
        menu.append_section(None, rotate_sec)
        close_sec = Gio.Menu()
        close_sec.append("Close Pane", "term.close-pane")
        menu.append_section(None, close_sec)
        return menu

    _PCRE2_MULTILINE = 0x00000400  # required by vte_terminal_match_add_regex

    def _setup_url_handling(self) -> None:
        try:
            self._url_regex = Vte.Regex.new_for_match(
                _URL_PATTERN, len(_URL_PATTERN.encode()), self._PCRE2_MULTILINE)
            self._url_tag = self._vte.match_add_regex(self._url_regex, 0)
            self._vte.match_set_cursor_name(self._url_tag, "pointer")
        except GLib.Error:
            pass

        click = Gtk.GestureClick()
        click.set_button(Gdk.BUTTON_PRIMARY)
        click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        click.connect("pressed", self._on_primary_click)
        self._vte.add_controller(click)

    def _url_at_coords(self, x: float, y: float) -> str | None:
        if self._url_tag < 0:
            return None
        try:
            cw = self._vte.get_char_width()
            ch = self._vte.get_char_height()
            if cw > 0 and ch > 0:
                col = int(x / cw)
                row = int(y / ch)
                url, _tag = self._vte.match_check(col, row)
                if url:
                    return url
        except Exception:
            pass
        return None

    def _open_url(self, url: str) -> None:
        try:
            Gio.AppInfo.launch_default_for_uri(url, None)
        except GLib.Error as e:
            print(f"Failed to open URL: {e.message}")

    def _on_primary_click(self, gesture, _n_press, x, y) -> None:
        open_mod = Gdk.ModifierType.META_MASK if _MACOS else Gdk.ModifierType.CONTROL_MASK
        mods = gesture.get_current_event_state() & (
            Gdk.ModifierType.META_MASK | Gdk.ModifierType.CONTROL_MASK
        )
        if mods != open_mod:
            return
        url = self._url_at_coords(x, y)
        if url:
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
            self._open_url(url)

    def _on_key_pressed(self, _ctrl, keyval, _keycode, state) -> bool:
        mods = state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK
                        | Gdk.ModifierType.ALT_MASK | Gdk.ModifierType.META_MASK)
        if _MACOS:
            copy_paste_mod = Gdk.ModifierType.META_MASK
        else:
            copy_paste_mod = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK
        if mods == copy_paste_mod:
            if keyval in (Gdk.KEY_c, Gdk.KEY_C):
                self.copy_clipboard()
                return True
            if keyval in (Gdk.KEY_v, Gdk.KEY_V):
                self.paste_clipboard()
                return True
        return False

    def _on_right_click(self, gesture, _n_press, x, y, popover) -> None:
        self._context_url = self._url_at_coords(x, y)
        popover.set_menu_model(
            self._menu_with_url if self._context_url else self._menu_without_url)
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        popover.set_pointing_to(rect)
        popover.popup()

    def _on_spawn_done(self, _terminal, _pid, error) -> None:
        if error:
            print(f"TerminalWidget: failed to spawn process: {error.message}")

    def _on_child_exited(self, _vte, status: int) -> None:
        self.emit("child-exited", status)
