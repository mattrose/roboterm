import os
import weakref

from gi.repository import Gtk, Vte, GLib, GObject, Gdk, Gio

from .settings import Settings


class TerminalWidget(Gtk.ScrolledWindow):
    """A self-contained VTE terminal wrapped in a ScrolledWindow.

    Emits:
        child-exited(status)  — forwarded from Vte.Terminal
        focus-grabbed()       — fired when the inner VTE receives focus
        split-right()         — user chose "Split Right" from context menu
        split-down()          — user chose "Split Down" from context menu
        close-pane()          — user chose "Close Pane" from context menu
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

        self._build_context_menu()

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
        menu_model = Gio.Menu()

        clipboard_section = Gio.Menu()
        clipboard_section.append("Copy",  "term.copy")
        clipboard_section.append("Paste", "term.paste")
        menu_model.append_section(None, clipboard_section)

        tab_section = Gio.Menu()
        tab_section.append("New Window", "term.new-window")
        tab_section.append("New Tab",    "term.new-tab")
        menu_model.append_section(None, tab_section)

        split_section = Gio.Menu()
        split_section.append("Split Auto",  "term.split-auto")
        split_section.append("Split Right", "term.split-right")
        split_section.append("Split Down",  "term.split-down")
        menu_model.append_section(None, split_section)

        rotate_section = Gio.Menu()
        rotate_section.append("Rotate Clockwise",        "term.rotate-cw")
        rotate_section.append("Rotate Counterclockwise", "term.rotate-ccw")
        menu_model.append_section(None, rotate_section)

        close_section = Gio.Menu()
        close_section.append("Close Pane", "term.close-pane")
        menu_model.append_section(None, close_section)

        popover = Gtk.PopoverMenu.new_from_model(menu_model)
        popover.set_has_arrow(False)
        popover.set_parent(self._vte)

        ag = Gio.SimpleActionGroup()

        copy_action = Gio.SimpleAction.new("copy", None)
        copy_action.connect("activate", lambda _a, _p: self.copy_clipboard())
        ag.add_action(copy_action)

        paste_action = Gio.SimpleAction.new("paste", None)
        paste_action.connect("activate", lambda _a, _p: self.paste_clipboard())
        ag.add_action(paste_action)

        for name, signal in (
            ("new-window",  "new-window"),
            ("new-tab",     "new-tab"),
            ("split-auto",  "split-auto"),
            ("split-right", "split-right"),
            ("split-down",  "split-down"),
            ("rotate-cw",   "rotate-cw"),
            ("rotate-ccw",  "rotate-ccw"),
            ("close-pane",  "close-pane"),
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

    def _on_key_pressed(self, _ctrl, keyval, _keycode, state) -> bool:
        mods = state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK
                        | Gdk.ModifierType.ALT_MASK | Gdk.ModifierType.SUPER_MASK)
        if mods == (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK):
            if keyval in (Gdk.KEY_c, Gdk.KEY_C):
                self.copy_clipboard()
                return True
            if keyval in (Gdk.KEY_v, Gdk.KEY_V):
                self.paste_clipboard()
                return True
        return False

    def _on_right_click(self, gesture, _n_press, x, y, popover) -> None:
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
