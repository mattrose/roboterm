#!/usr/bin/env python3
"""
GTK4 app with a VTE terminal widget embedded inside.
Each tab has its own independent pane manager supporting splits.
Dependencies: gtk4, vte-3.91 (Python GI bindings)

Install on Debian/Ubuntu:
    sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adwaita-1 gir1.2-vte-3.91

Install on Fedora:
    sudo dnf install python3-gobject gtk4 libadwaita vte391-gtk4

Install on Arch:
    sudo pacman -S python-gobject gtk4 libadwaita vte3

Keyboard shortcuts:
    Ctrl+Shift+C  — copy selection
    Ctrl+Shift+V  — paste clipboard
    Ctrl+Shift+N  — new window
    Ctrl+Shift+T  — new tab
    Ctrl+Shift+W  — close active pane  (closes tab when last pane)
    Ctrl+Shift+]  — rotate panes clockwise
    Ctrl+Shift+[  — rotate panes counter-clockwise
    Ctrl+Shift+A  — split active pane automatically (based on dimensions)
    Ctrl+Shift+E  — split active pane right (vertical divider)
    Ctrl+Shift+O  — split active pane down  (horizontal divider)
    Ctrl+Page_Up  — previous tab
    Ctrl+Page_Down— next tab

Right-click any pane for a context menu with split / close actions.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Vte", "3.91")

from gi.repository import Gtk, Adw, Vte, GLib, GObject, Gdk, Gio
import os

Adw.init()


# ── TerminalWidget ─────────────────────────────────────────────────────────────

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

    def __init__(self, scrollback_lines: int = 10_000):
        super().__init__()

        self.set_vexpand(True)
        self.set_hexpand(True)
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.ALWAYS)

        self._vte = Vte.Terminal()
        self._vte.set_scrollback_lines(scrollback_lines)
        self._vte.set_mouse_autohide(True)
        self.set_child(self._vte)

        self._vte.connect("child-exited", self._on_child_exited)

        focus_ctrl = Gtk.EventControllerFocus()
        focus_ctrl.connect("enter", lambda _ec: self.emit("focus-grabbed"))
        self._vte.add_controller(focus_ctrl)

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



# ── PaneFrame ─────────────────────────────────────────────────────────────────

class PaneFrame(Gtk.Box):
    """A TerminalWidget wrapped in a vertical Box with an optional title bar.

    The title bar is a slim label that displays the VTE window-title (set by
    the running shell/program via OSC escape sequences).  It is shown only
    when there is more than one pane in the tab; PaneManager controls this
    via show_titlebar() / hide_titlebar().
    """

    def __init__(self, terminal: "TerminalWidget"):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_vexpand(True)
        self.set_hexpand(True)

        self._terminal = terminal

        # ── Title bar ─────────────────────────────────────────────────────────
        self._titlebar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._titlebar.add_css_class("terminal-titlebar")

        self._title_label = Gtk.Label(label="Terminal")
        self._title_label.set_hexpand(True)
        self._title_label.set_ellipsize(3)   # Pango.EllipsizeMode.END = 3
        self._title_label.set_xalign(0.5)
        self._title_label.add_css_class("terminal-title-label")
        self._titlebar.append(self._title_label)

        self._titlebar.set_visible(False)
        self.append(self._titlebar)

        # ── Terminal ──────────────────────────────────────────────────────────
        self.append(terminal)

        # Track VTE window-title changes
        terminal.vte.connect("window-title-changed", self._on_title_changed)

        # Highlight titlebar when the terminal is focused
        terminal.connect("focus-grabbed", self._on_focus)

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def terminal(self) -> "TerminalWidget":
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

    # ── Private ───────────────────────────────────────────────────────────────

    def _on_title_changed(self, vte) -> None:
        title = vte.props.window_title or "Terminal"
        self._title_label.set_label(title)

    def _on_focus(self, _terminal) -> None:
        # Tell siblings to unfocus; PaneManager handles this centrally
        pass


# ── PaneManager ───────────────────────────────────────────────────────────────

class PaneManager(Gtk.Box):
    """Manages a tree of Gtk.Paned splits containing PaneFrames.

    Leaves of the tree are PaneFrame widgets (each wrapping a TerminalWidget).
    Internal nodes are Gtk.Paned.  PaneManager owns the show/hide logic for
    per-pane title bars: they appear whenever there is more than one pane.

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

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def active(self) -> TerminalWidget | None:
        return self._active

    def split_active(self, orientation: Gtk.Orientation) -> None:
        if self._active is None:
            return

        # _active is a TerminalWidget; its immediate parent is its PaneFrame
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
            # parent is this PaneManager box
            parent.remove(old_frame)
            paned.set_start_child(old_frame)
            paned.set_end_child(new_frame)
            parent.append(paned)

        self._update_titlebars()
        GLib.idle_add(self._equalize, paned, orientation)
        GLib.idle_add(new_frame.terminal.grab_focus)

    def split_auto(self) -> None:
        """Split based on the active pane's dimensions.

        Side-by-side (HORIZONTAL) when width > height; stacked (VERTICAL) otherwise.
        """
        if self._active is None:
            return
        frame = self._active.get_parent()
        w = frame.get_width()
        h = frame.get_height()
        self.split_active(
            Gtk.Orientation.HORIZONTAL if w > h else Gtk.Orientation.VERTICAL
        )

    def rotate_cw(self) -> None:
        """Rotate pane frames one step clockwise (reading-order shift left)."""
        self._rotate(step=1)

    def rotate_ccw(self) -> None:
        """Rotate pane frames one step counter-clockwise (reading-order shift right)."""
        self._rotate(step=-1)

    def close_active(self) -> None:
        if self._active is None:
            return
        self._close_specific(self._active)

    def focus_active(self) -> None:
        """Re-focus the active terminal (e.g. after switching tabs)."""
        if self._active:
            GLib.idle_add(self._active.grab_focus)

    # ── Private ───────────────────────────────────────────────────────────────

    def _make_frame(self) -> PaneFrame:
        """Create a new PaneFrame+TerminalWidget with all signals wired."""
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
        old_frame = term.get_parent()   # PaneFrame
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
            # Last pane in this tab
            self.emit("all-closed")

    def _rotate(self, step: int) -> None:
        """Rotate PaneFrames in reading order by swapping them between slots.

        Collects (paned, side) slot references, detaches all frames, then
        reattaches in rotated order.  No widget is ever parentless mid-cycle.
        """
        root  = self.get_first_child()
        slots = self._collect_slots(root)
        n     = len(slots)
        if n < 2:
            return

        active_term = self._active

        # Snapshot frames currently in each slot
        frames = [
            (paned.get_start_child() if side == "start" else paned.get_end_child())
            for paned, side in slots
        ]
        rotated = frames[-step % n:] + frames[:-step % n]

        # Phase 1: detach all
        for paned, side in slots:
            if side == "start":
                paned.set_start_child(None)
            else:
                paned.set_end_child(None)

        # Phase 2: reattach in rotated order
        for (paned, side), frame in zip(slots, rotated):
            if side == "start":
                paned.set_start_child(frame)
            else:
                paned.set_end_child(frame)

        # Restore focus (active TerminalWidget moved with its frame)
        if active_term is not None:
            GLib.idle_add(active_term.grab_focus)

    def _update_titlebars(self) -> None:
        """Show per-pane title bars when there is more than one pane; hide when solo."""
        frames  = self._collect_frames(self.get_first_child())
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
        """Return (paned, side) pairs for every PaneFrame leaf, in reading order."""
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
        """Return all PaneFrame leaves in reading order."""
        if isinstance(widget, PaneFrame):
            return [widget]
        if isinstance(widget, Gtk.Paned):
            return (
                PaneManager._collect_frames(widget.get_start_child())
                + PaneManager._collect_frames(widget.get_end_child())
            )
        return []

    @staticmethod
    def _first_leaf(widget) -> "TerminalWidget | None":
        """Return the TerminalWidget of the first PaneFrame leaf."""
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


# ── TabLabel ──────────────────────────────────────────────────────────────────

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


# ── TerminalWindow ─────────────────────────────────────────────────────────────

class TerminalWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Terminal")
        self.set_default_size(900, 600)

        # ── Header bar (Adw.HeaderBar — no set_titlebar needed) ─────────────
        header = Adw.HeaderBar()

        # Build a Gio.Menu and wire each item to a window-scoped action
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

        # Register SimpleActions on this window
        win_actions = {
            "new-window":  lambda: self.get_application().new_window(),
            "new-tab":     lambda: self._new_tab(),
            "split-auto":  lambda: self._active_panes().split_auto(),
            "split-right": lambda: self._active_panes().split_active(Gtk.Orientation.HORIZONTAL),
            "split-down":  lambda: self._active_panes().split_active(Gtk.Orientation.VERTICAL),
            "rotate-cw":   lambda: self._active_panes().rotate_cw(),
            "rotate-ccw":  lambda: self._active_panes().rotate_ccw(),
            "close-pane":  lambda: self._active_panes().close_active(),
        }
        for name, cb in win_actions.items():
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _a, _p, fn=cb: fn())
            self.add_action(action)

        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")
        menu_btn.set_menu_model(menu_model)
        header.pack_end(menu_btn)

        # ── Notebook ──────────────────────────────────────────────────────────
        self._notebook = Gtk.Notebook()
        self._notebook.set_scrollable(True)
        self._notebook.set_show_border(False)
        self._notebook.connect("switch-page", self._on_switch_page)

        # ── ToolbarView wires the header bar to the window content ────────────
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)
        toolbar_view.set_content(self._notebook)
        self.set_content(toolbar_view)

        self._tab_count = 0
        self._new_tab()

        # ── Keyboard shortcuts ────────────────────────────────────────────────
        self._add_shortcut("<Control><Shift>c", lambda: self._active_panes().active.copy_clipboard())
        self._add_shortcut("<Control><Shift>v", lambda: self._active_panes().active.paste_clipboard())
        self._add_shortcut("<Control><Shift>n", lambda: self.get_application().new_window())
        self._add_shortcut("<Control><Shift>t", self._new_tab)
        self._add_shortcut("<Control><Shift>a", lambda: self._active_panes().split_auto())
        self._add_shortcut("<Control><Shift>e", lambda: self._active_panes().split_active(Gtk.Orientation.HORIZONTAL))
        self._add_shortcut("<Control><Shift>o", lambda: self._active_panes().split_active(Gtk.Orientation.VERTICAL))
        self._add_shortcut("<Control><Shift>bracketright", lambda: self._active_panes().rotate_cw())
        self._add_shortcut("<Control><Shift>bracketleft",  lambda: self._active_panes().rotate_ccw())
        self._add_shortcut("<Control><Shift>w", lambda: self._active_panes().close_active())
        self._add_shortcut("<Control>Page_Up",   lambda: self._notebook.prev_page())
        self._add_shortcut("<Control>Page_Down", lambda: self._notebook.next_page())

    # ── Tab management ────────────────────────────────────────────────────────

    def _new_tab(self) -> None:
        self._tab_count += 1
        title = f"Terminal {self._tab_count}"

        panes = PaneManager()
        panes.connect("all-closed",  self._on_tab_all_closed)
        panes.connect("new-tab",     lambda _p: self._new_tab())
        panes.connect("new-window",  lambda _p: self.get_application().new_window())

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

    # ── Shortcuts ─────────────────────────────────────────────────────────────

    def _add_shortcut(self, accel: str, cb) -> None:
        trigger  = Gtk.ShortcutTrigger.parse_string(accel)
        action   = Gtk.CallbackAction.new(lambda *_: cb() or True)
        shortcut = Gtk.Shortcut(trigger=trigger, action=action)
        ctrl     = Gtk.ShortcutController()
        ctrl.set_scope(Gtk.ShortcutScope.GLOBAL)
        ctrl.add_shortcut(shortcut)
        self.add_controller(ctrl)


# ── TerminalApp ───────────────────────────────────────────────────────────────

class TerminalApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.example.GtkVteTerminal", flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.connect("activate", self.on_activate)

    def new_window(self) -> None:
        win = TerminalWindow(self)
        win.present()

    def on_activate(self, app):

        # Inject titlebar CSS
        css_provider = Gtk.CssProvider()
        css_provider.load_from_string(
            ".terminal-titlebar {"
            "  background-color: @headerbar_bg_color;"
            "  padding: 2px 6px;"
            "  border-bottom: 1px solid @borders;"
            "  min-height: 24px;"
            "}"
            ".terminal-titlebar.focused {"
            "  background-color: @accent_bg_color;"
            "  color: @accent_fg_color;"
            "}"
            ".terminal-title-label {"
            "  font-size: 0.75em;"
            "}"
        )
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        self.new_window()


if __name__ == "__main__":
    app = TerminalApp()
    app.run()
