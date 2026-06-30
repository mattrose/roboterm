import signal

from gi.repository import Gtk, Adw, Gdk, Gio, GLib

from .window import TerminalWindow


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
