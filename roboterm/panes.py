import weakref

from gi.repository import Gtk, GLib, GObject

from .settings import Settings
from .terminal import TerminalWidget


class PaneFrame(Gtk.Box):
    """A TerminalWidget wrapped in a vertical Box with an optional title bar."""

    def __init__(self, terminal: TerminalWidget):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_vexpand(True)
        self.set_hexpand(True)

        self._terminal = terminal

        self._titlebar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._titlebar.add_css_class("terminal-titlebar")

        self._title_label = Gtk.Label(label="Terminal")
        self._title_label.set_hexpand(True)
        self._title_label.set_ellipsize(3)   # Pango.EllipsizeMode.END
        self._title_label.set_xalign(0.5)
        self._title_label.add_css_class("terminal-title-label")
        self._titlebar.append(self._title_label)

        self._titlebar.set_visible(False)
        self.append(self._titlebar)
        self.append(terminal)

        terminal.vte.connect("window-title-changed", self._on_title_changed)
        terminal.connect("focus-grabbed", self._on_focus)

    @property
    def terminal(self) -> TerminalWidget:
        return self._terminal

    def show_titlebar(self) -> None:
        self._titlebar.set_visible(True)

    def hide_titlebar(self) -> None:
        self._titlebar.set_visible(False)

    def set_focused(self, focused: bool) -> None:
        if focused:
            self._titlebar.add_css_class("focused")
        else:
            self._titlebar.remove_css_class("focused")

    def _on_title_changed(self, vte) -> None:
        self._title_label.set_label(vte.props.window_title or "Terminal")

    def _on_focus(self, _terminal) -> None:
        pass


class PaneManager(Gtk.Box):
    """Manages a tree of Gtk.Paned splits containing PaneFrames.

    Emits:
        all-closed()  — fired when the last pane is closed
        new-tab()     — forwarded from any terminal's context menu
        new-window()  — forwarded from any terminal's context menu
    """

    __gsignals__ = {
        "all-closed":  (GObject.SignalFlags.RUN_LAST, None, ()),
        "new-tab":     (GObject.SignalFlags.RUN_LAST, None, ()),
        "new-window":  (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_vexpand(True)
        self.set_hexpand(True)

        self._active: TerminalWidget | None = None

        first = self._make_frame()
        self.append(first)
        first.terminal.spawn_shell()
        GLib.idle_add(first.terminal.grab_focus)

        pm_ref = weakref.ref(self)
        def _on_settings_changed():
            pm = pm_ref()
            if pm is not None:
                pm._update_titlebars()
        Settings.get().connect_changed(_on_settings_changed)
        self._update_titlebars()

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def active(self) -> TerminalWidget | None:
        return self._active

    def split_active(self, orientation: Gtk.Orientation) -> None:
        if self._active is None:
            return

        old_frame = self._active.get_parent()
        parent    = old_frame.get_parent()

        new_frame = self._make_frame()
        new_frame.terminal.spawn_shell()

        paned = Gtk.Paned(orientation=orientation)
        paned.set_vexpand(True)
        paned.set_hexpand(True)

        if isinstance(parent, Gtk.Paned):
            if parent.get_start_child() is old_frame:
                parent.set_start_child(None)
                paned.set_start_child(old_frame)
                paned.set_end_child(new_frame)
                parent.set_start_child(paned)
            else:
                parent.set_end_child(None)
                paned.set_start_child(old_frame)
                paned.set_end_child(new_frame)
                parent.set_end_child(paned)
        else:
            parent.remove(old_frame)
            paned.set_start_child(old_frame)
            paned.set_end_child(new_frame)
            parent.append(paned)

        self._update_titlebars()
        GLib.idle_add(self._equalize, paned, orientation)
        GLib.idle_add(new_frame.terminal.grab_focus)

    def split_auto(self) -> None:
        if self._active is None:
            return
        frame = self._active.get_parent()
        w = frame.get_width()
        h = frame.get_height()
        self.split_active(
            Gtk.Orientation.HORIZONTAL if w > h else Gtk.Orientation.VERTICAL
        )

    def rotate_cw(self) -> None:
        self._rotate(step=1)

    def rotate_ccw(self) -> None:
        self._rotate(step=-1)

    def close_active(self) -> None:
        if self._active is None:
            return
        self._close_specific(self._active)

    def focus_active(self) -> None:
        if self._active:
            GLib.idle_add(self._active.grab_focus)

    # ── Private ───────────────────────────────────────────────────────────────

    def _make_frame(self) -> PaneFrame:
        t = TerminalWidget()
        t.connect("focus-grabbed", self._on_focus_grabbed)
        t.connect("child-exited",  self._on_child_exited)
        t.connect("split-auto",    lambda term:  self._split_auto_specific(term))
        t.connect("split-right",   lambda term:  self._split_specific(term, Gtk.Orientation.HORIZONTAL))
        t.connect("split-down",    lambda term:  self._split_specific(term, Gtk.Orientation.VERTICAL))
        t.connect("close-pane",    lambda term:  self._close_specific(term))
        t.connect("rotate-cw",     lambda _term: self.rotate_cw())
        t.connect("rotate-ccw",    lambda _term: self.rotate_ccw())
        t.connect("new-tab",       lambda _term: self.emit("new-tab"))
        t.connect("new-window",    lambda _term: self.emit("new-window"))
        return PaneFrame(t)

    def _split_auto_specific(self, term: TerminalWidget) -> None:
        self._active = term
        self.split_auto()

    def _split_specific(self, term: TerminalWidget, orientation: Gtk.Orientation) -> None:
        self._active = term
        self.split_active(orientation)

    def _close_specific(self, term: TerminalWidget) -> None:
        old_frame = term.get_parent()
        parent    = old_frame.get_parent()

        if isinstance(parent, Gtk.Paned):
            survivor = (
                parent.get_end_child()
                if parent.get_start_child() is old_frame
                else parent.get_start_child()
            )

            parent.set_start_child(None)
            parent.set_end_child(None)

            grandparent = parent.get_parent()
            if isinstance(grandparent, Gtk.Paned):
                if grandparent.get_start_child() is parent:
                    grandparent.set_start_child(None)
                    grandparent.set_start_child(survivor)
                else:
                    grandparent.set_end_child(None)
                    grandparent.set_end_child(survivor)
            else:
                grandparent.remove(parent)
                grandparent.append(survivor)

            if self._active is term:
                self._active = None
            self._update_titlebars()
            first_leaf = self._first_leaf(survivor)
            if first_leaf:
                GLib.idle_add(first_leaf.grab_focus)
        else:
            self.emit("all-closed")

    def _rotate(self, step: int) -> None:
        root  = self.get_first_child()
        slots = self._collect_slots(root)
        n     = len(slots)
        if n < 2:
            return

        active_term = self._active
        frames = [
            (paned.get_start_child() if side == "start" else paned.get_end_child())
            for paned, side in slots
        ]
        rotated = frames[-step % n:] + frames[:-step % n]

        for paned, side in slots:
            if side == "start":
                paned.set_start_child(None)
            else:
                paned.set_end_child(None)

        for (paned, side), frame in zip(slots, rotated):
            if side == "start":
                paned.set_start_child(frame)
            else:
                paned.set_end_child(frame)

        if active_term is not None:
            GLib.idle_add(active_term.grab_focus)

    def _update_titlebars(self) -> None:
        frames  = self._collect_frames(self.get_first_child())
        setting = Settings.get().get_value("pane_titlebar")
        if setting == "always":
            visible = True
        elif setting == "never":
            visible = False
        else:
            visible = len(frames) > 1
        active_frame = self._active.get_parent() if self._active else None
        for frame in frames:
            if visible:
                frame.show_titlebar()
            else:
                frame.hide_titlebar()
            frame.set_focused(frame is active_frame)

    def _on_focus_grabbed(self, term: TerminalWidget) -> None:
        self._active = term
        self._update_titlebars()

    def _on_child_exited(self, term: TerminalWidget, _status: int) -> None:
        self._close_specific(term)

    @staticmethod
    def _collect_slots(widget) -> list:
        if isinstance(widget, Gtk.Paned):
            return (
                PaneManager._collect_slots(widget.get_start_child())
                + PaneManager._collect_slots(widget.get_end_child())
            )
        if isinstance(widget, PaneFrame):
            parent = widget.get_parent()
            if isinstance(parent, Gtk.Paned):
                side = "start" if parent.get_start_child() is widget else "end"
                return [(parent, side)]
        return []

    @staticmethod
    def _collect_frames(widget) -> list:
        if isinstance(widget, PaneFrame):
            return [widget]
        if isinstance(widget, Gtk.Paned):
            return (
                PaneManager._collect_frames(widget.get_start_child())
                + PaneManager._collect_frames(widget.get_end_child())
            )
        return []

    @staticmethod
    def _first_leaf(widget) -> TerminalWidget | None:
        if isinstance(widget, PaneFrame):
            return widget.terminal
        if isinstance(widget, Gtk.Paned):
            leaf = PaneManager._first_leaf(widget.get_start_child())
            if leaf:
                return leaf
            return PaneManager._first_leaf(widget.get_end_child())
        return None

    @staticmethod
    def _equalize(paned: Gtk.Paned, orientation: Gtk.Orientation) -> bool:
        size = paned.get_height() if orientation == Gtk.Orientation.VERTICAL else paned.get_width()
        if size > 1:
            paned.set_position(size // 2)
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE
