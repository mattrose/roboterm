import signal
import sys

from gi.repository import Gtk, Adw, Gdk, Gio, GLib

from .settings import Settings
from .window import TerminalWindow

_MACOS = sys.platform == "darwin"

# Menu items whose shortcut label comes from the matching keybinding.
_MENU_ACCEL_ACTIONS = {
    "preferences":   "win.preferences",
    "new-window":    "app.new-window",
    "new-tab":       "win.new-tab",
    "close-pane":    "win.close-pane",
    "split-auto":    "win.split-auto",
    "split-right":   "win.split-right",
    "split-down":    "win.split-down",
    "maximize-pane": "win.maximize-pane",
    "rotate-cw":     "win.rotate-cw",
    "rotate-ccw":    "win.rotate-ccw",
    "prev-tab":      "win.prev-tab",
    "next-tab":      "win.next-tab",
}

# Copy/Paste are handled in TerminalWidget._on_key_pressed and are not part of
# the customizable keybindings, so their labels stay fixed.
_FIXED_MENU_ACCELS = {
    "win.copy":  ["<Meta>c"],
    "win.paste": ["<Meta>v"],
}


def _menu_accels(keybindings: dict) -> dict:
    """{menu action: [accelerator]} for the macOS menu bar's shortcut labels.

    A disabled (empty) keybinding yields no accelerator, so the menu item
    shows no shortcut rather than a stale one.
    """
    accels = dict(_FIXED_MENU_ACCELS)
    for name, action in _MENU_ACCEL_ACTIONS.items():
        accel = keybindings.get(name, "")
        accels[action] = [accel] if accel else []
    return accels


class TerminalApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="net.folkwolf.roboterm",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.connect("activate", self._on_activate)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self.quit)

    def new_window(self) -> None:
        win = TerminalWindow(self)
        win.present()

    def _on_activate(self, _app) -> None:
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
        self._refresh_menu_accels()
        Settings.get().connect_changed(self._refresh_menu_accels)

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
        maximize_sec = Gio.Menu()
        maximize_sec.append("Toggle Maximize", "win.maximize-pane")
        view_menu.append_section(None, maximize_sec)
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

    def _refresh_menu_accels(self) -> None:
        """Relabel the menu bar from the live keybindings, user overrides included."""
        for action, accels in _menu_accels(Settings.get().get_keybindings()).items():
            self.set_accels_for_action(action, accels)
