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

"""Tests for _rgba_to_hex using real Gdk.RGBA objects."""
from gi.repository import Gdk

from roboterm.settings import _rgba_to_hex


def _rgba(r, g, b):
    c = Gdk.RGBA()
    c.red, c.green, c.blue, c.alpha = r, g, b, 1.0
    return c


class TestRgbaToHexReal:
    def test_black(self):
        assert _rgba_to_hex(_rgba(0.0, 0.0, 0.0)) == "#000000"

    def test_white(self):
        assert _rgba_to_hex(_rgba(1.0, 1.0, 1.0)) == "#ffffff"

    def test_pure_red(self):
        assert _rgba_to_hex(_rgba(1.0, 0.0, 0.0)) == "#ff0000"

    def test_pure_green(self):
        assert _rgba_to_hex(_rgba(0.0, 1.0, 0.0)) == "#00ff00"

    def test_pure_blue(self):
        assert _rgba_to_hex(_rgba(0.0, 0.0, 1.0)) == "#0000ff"

    def test_rounding(self):
        assert _rgba_to_hex(_rgba(0.5, 0.5, 0.5)) == "#808080"

    def test_parse_roundtrip(self):
        """Gdk.RGBA.parse() then _rgba_to_hex() must round-trip exactly."""
        for hex_color in ("#1e2030", "#ebdbb2", "#282828", "#ff5555", "#000000", "#ffffff"):
            rgba = Gdk.RGBA()
            rgba.parse(hex_color)
            assert _rgba_to_hex(rgba) == hex_color, f"round-trip failed for {hex_color}"

    def test_theme_foreground_colors_roundtrip(self):
        """Every foreground/background color in THEMES survives a parse→hex round-trip."""
        from roboterm.settings import THEMES
        for name, theme in THEMES.items():
            for key in ("foreground", "background"):
                original = theme[key]
                rgba = Gdk.RGBA()
                rgba.parse(original)
                result = _rgba_to_hex(rgba)
                assert result == original, f"{name}.{key}: {original!r} → {result!r}"
