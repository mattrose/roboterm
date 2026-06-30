from gi.repository import Gtk, Adw, Gdk, Pango

from .settings import Settings, THEMES, _rgba_to_hex


class PreferencesWindow(Adw.PreferencesWindow):
    def __init__(self, transient_for=None):
        super().__init__()
        self.set_title("Preferences")
        self.set_default_size(480, 560)
        if transient_for:
            self.set_transient_for(transient_for)
            self.set_modal(False)

        s = Settings.get()
        page = Adw.PreferencesPage()
        self.add(page)

        # ── Appearance ────────────────────────────────────────────────────────
        appearance = Adw.PreferencesGroup()
        appearance.set_title("Appearance")
        page.add(appearance)

        font_row = Adw.ActionRow()
        font_row.set_title("Font")
        font_btn = Gtk.FontDialogButton(dialog=Gtk.FontDialog())
        font_btn.set_valign(Gtk.Align.CENTER)
        font_btn.set_font_desc(Pango.FontDescription.from_string(s.get_value("font")))
        font_btn.connect("notify::font-desc",
            lambda btn, _: s.set_value("font", btn.get_font_desc().to_string()))
        font_row.add_suffix(font_btn)
        font_row.set_activatable_widget(font_btn)
        appearance.add(font_row)

        # ── Colors ────────────────────────────────────────────────────────────
        colors = Adw.PreferencesGroup()
        colors.set_title("Colors")
        page.add(colors)

        theme_names = ["Custom"] + list(THEMES.keys())
        theme_row = Adw.ComboRow()
        theme_row.set_title("Theme")
        theme_row.set_model(Gtk.StringList.new(theme_names))
        current = s.get_value("theme")
        theme_row.set_selected(theme_names.index(current) if current in theme_names else 0)
        colors.add(theme_row)

        def _make_color_btn(key: str) -> Gtk.ColorDialogButton:
            btn = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog())
            btn.set_valign(Gtk.Align.CENTER)
            rgba = Gdk.RGBA()
            rgba.parse(s.get_value(key))
            btn.set_rgba(rgba)
            return btn

        fg_btn = _make_color_btn("foreground")
        bg_btn = _make_color_btn("background")

        for label, btn, key in (
            ("Text",       fg_btn, "foreground"),
            ("Background", bg_btn, "background"),
        ):
            row = Adw.ActionRow()
            row.set_title(label)
            btn.connect("notify::rgba", lambda b, _, k=key: (
                s.set_value(k, _rgba_to_hex(b.get_rgba())),
                theme_row.handler_block(theme_handler_id),
                theme_row.set_selected(0),
                s._data.__setitem__("theme", "Custom"),
                s.save(),
                theme_row.handler_unblock(theme_handler_id),
            ))
            row.add_suffix(btn)
            row.set_activatable_widget(btn)
            colors.add(row)

        def _on_theme_selected(row, _):
            name = theme_names[row.get_selected()]
            s.apply_theme(name)
            fg = Gdk.RGBA(); fg.parse(s.get_value("foreground"))
            bg = Gdk.RGBA(); bg.parse(s.get_value("background"))
            fg_btn.set_rgba(fg)
            bg_btn.set_rgba(bg)

        theme_handler_id = theme_row.connect("notify::selected", _on_theme_selected)

        # ── Cursor ────────────────────────────────────────────────────────────
        cursor_group = Adw.PreferencesGroup()
        cursor_group.set_title("Cursor")
        page.add(cursor_group)

        shape_row = Adw.ComboRow()
        shape_row.set_title("Shape")
        shape_row.set_model(Gtk.StringList.new(["Block", "I-Beam", "Underline"]))
        shape_row.set_selected({"block": 0, "ibeam": 1, "underline": 2}.get(s.get_value("cursor_shape"), 0))
        shape_row.connect("notify::selected",
            lambda r, _: s.set_value("cursor_shape", ["block", "ibeam", "underline"][r.get_selected()]))
        cursor_group.add(shape_row)

        blink_row = Adw.ComboRow()
        blink_row.set_title("Blink")
        blink_row.set_model(Gtk.StringList.new(["System Default", "Always On", "Always Off"]))
        blink_row.set_selected({"system": 0, "on": 1, "off": 2}.get(s.get_value("cursor_blink"), 0))
        blink_row.connect("notify::selected",
            lambda r, _: s.set_value("cursor_blink", ["system", "on", "off"][r.get_selected()]))
        cursor_group.add(blink_row)

        # ── Terminal ──────────────────────────────────────────────────────────
        terminal_group = Adw.PreferencesGroup()
        terminal_group.set_title("Terminal")
        page.add(terminal_group)

        scroll_row = Adw.ActionRow()
        scroll_row.set_title("Scrollback Lines")
        scroll_adj = Gtk.Adjustment(value=s.get_value("scrollback_lines"),
                                    lower=100, upper=1_000_000,
                                    step_increment=1_000, page_increment=10_000)
        scroll_spin = Gtk.SpinButton(adjustment=scroll_adj, digits=0)
        scroll_spin.set_valign(Gtk.Align.CENTER)
        scroll_spin.connect("value-changed",
            lambda w: s.set_value("scrollback_lines", int(w.get_value())))
        scroll_row.add_suffix(scroll_spin)
        terminal_group.add(scroll_row)

        titlebar_row = Adw.ComboRow()
        titlebar_row.set_title("Pane Titlebar")
        titlebar_row.set_subtitle("Show the title bar above each terminal pane")
        titlebar_row.set_model(Gtk.StringList.new(["Automatic", "Always", "Never"]))
        titlebar_row.set_selected({"auto": 0, "always": 1, "never": 2}.get(s.get_value("pane_titlebar"), 0))
        titlebar_row.connect("notify::selected",
            lambda r, _: s.set_value("pane_titlebar", ["auto", "always", "never"][r.get_selected()]))
        terminal_group.add(titlebar_row)

        bold_row = Adw.ActionRow()
        bold_row.set_title("Bold Is Bright")
        bold_row.set_subtitle("Show bold text in bright color variants")
        bold_switch = Gtk.Switch()
        bold_switch.set_valign(Gtk.Align.CENTER)
        bold_switch.set_active(s.get_value("bold_is_bright"))
        bold_switch.connect("notify::active",
            lambda w, _: s.set_value("bold_is_bright", w.get_active()))
        bold_row.add_suffix(bold_switch)
        bold_row.set_activatable_widget(bold_switch)
        terminal_group.add(bold_row)
