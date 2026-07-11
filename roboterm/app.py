import signal
import sys

from gi.repository import Gtk, Adw, Gdk, Gio, GLib

from .window import TerminalWindow

_MACOS = sys.platform == "darwin"


class TerminalApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="com.example.GtkVteTerminal",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.connect("activate", self._on_activate)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self.quit)

    def new_window(self) -> None:
        win = TerminalWindow(self)
        win.present()

    def _on_activate(self, _app) -> None:
        if not _MACOS:
            # Register Ctrl+, at the application level so it fires via the
            # application's accelerator group (processed in CAPTURE phase),
            # before VTE can consume the event.
            self.set_accels_for_action("win.preferences", ["<Control>comma"])

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
        if _MACOS:
            self._setup_menubar()
        self.new_window()

    def _setup_menubar(self) -> None:
        # ── App-level action ─────────────────────────────────────────────────
        new_win = Gio.SimpleAction.new("new-window", None)
        new_win.connect("activate", lambda *_: self.new_window())
        self.add_action(new_win)

        # Accelerators — displayed in menu labels; key handling is the CAPTURE handler
        self.set_accels_for_action("win.preferences",  ["<Meta>comma"])
        self.set_accels_for_action("app.new-window",   ["<Meta>n"])
        self.set_accels_for_action("win.new-tab",      ["<Meta>t"])
        self.set_accels_for_action("win.close-pane",   ["<Meta>w"])
        self.set_accels_for_action("win.copy",         ["<Meta>c"])
        self.set_accels_for_action("win.paste",        ["<Meta>v"])
        self.set_accels_for_action("win.split-right",  ["<Meta><Shift>e"])
        self.set_accels_for_action("win.split-down",   ["<Meta><Shift>o"])
        self.set_accels_for_action("win.split-auto",   ["<Meta><Shift>a"])
        self.set_accels_for_action("win.rotate-cw",    ["<Meta><Alt>bracketright"])
        self.set_accels_for_action("win.rotate-ccw",   ["<Meta><Alt>bracketleft"])
        self.set_accels_for_action("win.prev-tab",     ["<Meta><Shift>bracketleft"])
        self.set_accels_for_action("win.next-tab",     ["<Meta><Shift>bracketright"])

        # ── Menu structure ───────────────────────────────────────────────────
        menubar = Gio.Menu()

        # File (Settings lives here — avoids duplicating the macOS app menu)
        file_menu = Gio.Menu()
        new_sec = Gio.Menu()
        new_sec.append("New Window", "app.new-window")
        new_sec.append("New Tab",    "win.new-tab")
        file_menu.append_section(None, new_sec)
        settings_sec = Gio.Menu()
        settings_sec.append("Settings", "win.preferences")
        file_menu.append_section(None, settings_sec)
        close_sec = Gio.Menu()
        close_sec.append("Close", "win.close-pane")
        file_menu.append_section(None, close_sec)
        menubar.append_submenu("File", file_menu)

        # Edit
        edit_menu = Gio.Menu()
        edit_menu.append("Copy",  "win.copy")
        edit_menu.append("Paste", "win.paste")
        menubar.append_submenu("Edit", edit_menu)

        # View
        view_menu = Gio.Menu()
        split_sec = Gio.Menu()
        split_sec.append("Split Right", "win.split-right")
        split_sec.append("Split Down",  "win.split-down")
        split_sec.append("Split Auto",  "win.split-auto")
        view_menu.append_section(None, split_sec)
        rotate_sec = Gio.Menu()
        rotate_sec.append("Rotate Clockwise",         "win.rotate-cw")
        rotate_sec.append("Rotate Counter-Clockwise", "win.rotate-ccw")
        view_menu.append_section(None, rotate_sec)
        menubar.append_submenu("View", view_menu)

        # Window
        win_menu = Gio.Menu()
        tab_sec = Gio.Menu()
        tab_sec.append("Previous Tab", "win.prev-tab")
        tab_sec.append("Next Tab",     "win.next-tab")
        win_menu.append_section(None, tab_sec)
        menubar.append_submenu("Window", win_menu)

        self.set_menubar(menubar)
