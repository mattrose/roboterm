# Roboterm - a GTK4/VTE terminal emulator.
# Copyright (C) 2026 Matt Rose
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <https://www.gnu.org/licenses/>.

"""Tests for Settings.apply_to_vte() against a real Vte.Terminal."""
import pytest
from gi.repository import Vte

from roboterm.settings import Settings, THEMES


class TestCursorShape:
    @pytest.mark.parametrize("setting,expected", [
        ("block",     Vte.CursorShape.BLOCK),
        ("ibeam",     Vte.CursorShape.IBEAM),
        ("underline", Vte.CursorShape.UNDERLINE),
    ])
    def test_cursor_shape(self, tmp_config, vte_terminal, setting, expected):
        s = Settings.get()
        s.set_value("cursor_shape", setting)
        s.apply_to_vte(vte_terminal)
        assert vte_terminal.get_property("cursor-shape") == expected


class TestCursorBlink:
    @pytest.mark.parametrize("setting,expected", [
        ("system", Vte.CursorBlinkMode.SYSTEM),
        ("on",     Vte.CursorBlinkMode.ON),
        ("off",    Vte.CursorBlinkMode.OFF),
    ])
    def test_cursor_blink_mode(self, tmp_config, vte_terminal, setting, expected):
        s = Settings.get()
        s.set_value("cursor_blink", setting)
        s.apply_to_vte(vte_terminal)
        assert vte_terminal.get_property("cursor-blink-mode") == expected


class TestScrollback:
    def test_default_scrollback(self, tmp_config, vte_terminal):
        Settings.get().apply_to_vte(vte_terminal)
        assert vte_terminal.get_scrollback_lines() == 10_000

    @pytest.mark.parametrize("lines", [100, 1_000, 50_000, 1_000_000])
    def test_custom_scrollback(self, tmp_config, vte_terminal, lines):
        s = Settings.get()
        s.set_value("scrollback_lines", lines)
        s.apply_to_vte(vte_terminal)
        assert vte_terminal.get_scrollback_lines() == lines


class TestBoldIsBright:
    def test_bold_is_bright_true(self, tmp_config, vte_terminal):
        s = Settings.get()
        s.set_value("bold_is_bright", True)
        s.apply_to_vte(vte_terminal)
        assert vte_terminal.get_property("bold-is-bright") is True

    def test_bold_is_bright_false(self, tmp_config, vte_terminal):
        s = Settings.get()
        s.set_value("bold_is_bright", False)
        s.apply_to_vte(vte_terminal)
        assert vte_terminal.get_property("bold-is-bright") is False

    def test_bold_is_bright_default(self, tmp_config, vte_terminal):
        Settings.get().apply_to_vte(vte_terminal)
        assert vte_terminal.get_property("bold-is-bright") is False


class TestFont:
    def test_font_is_applied(self, tmp_config, vte_terminal):
        from gi.repository import Pango
        s = Settings.get()
        s.set_value("font", "Monospace 14")
        s.apply_to_vte(vte_terminal)
        fd = vte_terminal.get_property("font-desc")
        assert fd is not None
        assert fd.get_family().lower() == "monospace"
        assert fd.get_size() // Pango.SCALE == 14

    def test_font_change_takes_effect(self, tmp_config, vte_terminal):
        from gi.repository import Pango
        s = Settings.get()
        s.set_value("font", "Monospace 10")
        s.apply_to_vte(vte_terminal)
        fd_before = vte_terminal.get_property("font-desc").get_size()

        s.set_value("font", "Monospace 20")
        s.apply_to_vte(vte_terminal)
        fd_after = vte_terminal.get_property("font-desc").get_size()

        assert fd_after > fd_before


class TestApplyThemeToVte:
    @pytest.mark.parametrize("theme_name", list(THEMES.keys()))
    def test_theme_applies_without_error(self, tmp_config, vte_terminal, theme_name):
        s = Settings.get()
        s.apply_theme(theme_name)
        s.apply_to_vte(vte_terminal)

    def test_custom_theme_applies_without_error(self, tmp_config, vte_terminal):
        s = Settings.get()
        s.apply_theme("Custom")
        s.apply_to_vte(vte_terminal)

    def test_settings_change_callback_updates_vte(self, tmp_config, vte_terminal):
        import weakref
        s = Settings.get()
        vte_ref = weakref.ref(vte_terminal)

        def on_change():
            vte = vte_ref()
            if vte is not None:
                s.apply_to_vte(vte)

        s.connect_changed(on_change)
        s.set_value("scrollback_lines", 99_999)

        assert vte_terminal.get_scrollback_lines() == 99_999
