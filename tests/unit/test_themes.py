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

import re
import pytest

from roboterm.settings import THEMES

HEX_COLOR = re.compile(r"^#[0-9a-f]{6}$")

THEME_NAMES = list(THEMES.keys())


def is_hex(value: str) -> bool:
    return bool(HEX_COLOR.match(value))


class TestThemeStructure:
    @pytest.mark.parametrize("name", THEME_NAMES)
    def test_has_foreground(self, name):
        assert "foreground" in THEMES[name]

    @pytest.mark.parametrize("name", THEME_NAMES)
    def test_has_background(self, name):
        assert "background" in THEMES[name]

    @pytest.mark.parametrize("name", THEME_NAMES)
    def test_has_palette(self, name):
        assert "palette" in THEMES[name]

    @pytest.mark.parametrize("name", THEME_NAMES)
    def test_palette_has_16_colors(self, name):
        assert len(THEMES[name]["palette"]) == 16

    @pytest.mark.parametrize("name", THEME_NAMES)
    def test_foreground_is_hex(self, name):
        assert is_hex(THEMES[name]["foreground"]), (
            f"{name}.foreground = {THEMES[name]['foreground']!r}"
        )

    @pytest.mark.parametrize("name", THEME_NAMES)
    def test_background_is_hex(self, name):
        assert is_hex(THEMES[name]["background"]), (
            f"{name}.background = {THEMES[name]['background']!r}"
        )

    @pytest.mark.parametrize("name", THEME_NAMES)
    def test_all_palette_entries_are_hex(self, name):
        for i, color in enumerate(THEMES[name]["palette"]):
            assert is_hex(color), f"{name}.palette[{i}] = {color!r}"


class TestThemesCollection:
    def test_at_least_one_theme(self):
        assert len(THEMES) >= 1

    def test_no_duplicate_names(self):
        assert len(THEMES) == len(set(THEMES.keys()))

    def test_expected_themes_present(self):
        expected = {"Gruvbox Dark", "Solarized Dark", "Dracula", "Nord", "One Dark"}
        assert expected.issubset(THEMES.keys())
