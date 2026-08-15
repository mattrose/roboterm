"""The README's shortcut table is hand-maintained, so it can silently drift from
`_default_keybindings()` the way the macOS menu labels once did (see CLAUDE.md).
These tests pin every documented row to the real default, on both platforms.

A failure here means the table and the code disagree — fix whichever is wrong.
Adding a keybinding requires a README row; renaming a row requires updating
_ROW_FOR_BINDING below.
"""

import pathlib
import re

import pytest

import roboterm.settings as settings_mod
from roboterm.settings import _default_keybindings

_README = pathlib.Path(__file__).parents[2] / "README.md"

# Table row label -> keybinding name. Copy/Paste are deliberately absent: they
# are handled in TerminalWidget._on_key_pressed, not the keybindings dict.
_ROW_FOR_BINDING = {
    "preferences":   "Preferences",
    "new-window":    "New window",
    "new-tab":       "New tab",
    "close-pane":    "Close active pane (closes tab when last pane)",
    "split-auto":    "Split pane automatically (based on dimensions)",
    "split-right":   "Split pane right",
    "split-down":    "Split pane down",
    "maximize-pane": "Maximize / restore active pane",
    "rotate-cw":     "Rotate panes clockwise",
    "rotate-ccw":    "Rotate panes counter-clockwise",
    "prev-tab":      "Previous tab",
    "next-tab":      "Next tab",
}

# GTK accelerator syntax -> the notation the README uses.
_MODIFIERS = {"<Meta>": "Cmd+", "<Control>": "Ctrl+", "<Shift>": "Shift+"}
_KEY_NAMES = {
    "comma": ",", "bracketleft": "[", "bracketright": "]",
    "Page_Up": "Page Up", "Page_Down": "Page Down",
}

_ROW = re.compile(r"^\|\s*(.+?)\s*\|\s*`?([^|`]+?)`?\s*\|\s*`?([^|`]+?)`?\s*\|$", re.M)


def _as_documented(accel: str, macos: bool) -> str:
    """Render a GTK accelerator the way the README writes it."""
    out = accel
    for gtk, shown in _MODIFIERS.items():
        out = out.replace(gtk, shown)
    out = out.replace("<Alt>", "Option+" if macos else "Alt+")
    for gtk, shown in _KEY_NAMES.items():
        out = out.replace(gtk, shown)
    head, _, key = out.rpartition("+")
    if len(key) == 1 and key.isalpha():
        key = key.upper()
    return f"{head}+{key}" if head else key


@pytest.fixture(scope="module")
def documented():
    """{row label: (macOS cell, Linux cell)} parsed from the README table."""
    return {m[1]: (m[2], m[3]) for m in _ROW.finditer(_README.read_text())}


@pytest.fixture
def defaults(monkeypatch):
    """Both platforms' defaults, whichever platform the tests run on."""
    def for_platform(macos):
        monkeypatch.setattr(settings_mod, "_MACOS", macos)
        return _default_keybindings()
    return {"macos": for_platform(True), "linux": for_platform(False)}


class TestReadmeShortcutTable:
    def test_every_binding_has_a_row(self, defaults, documented):
        """A new keybinding must be documented, not just implemented."""
        assert set(defaults["macos"]) == set(_ROW_FOR_BINDING)

    def test_every_mapped_row_exists(self, documented):
        """Guards the map itself: a renamed row must not silently skip checks."""
        missing = [row for row in _ROW_FOR_BINDING.values() if row not in documented]
        assert not missing, f"rows not found in README: {missing}"

    @pytest.mark.parametrize("name", sorted(_ROW_FOR_BINDING))
    def test_macos_column_matches_default(self, name, defaults, documented):
        shown, _ = documented[_ROW_FOR_BINDING[name]]
        assert shown == _as_documented(defaults["macos"][name], macos=True)

    @pytest.mark.parametrize("name", sorted(_ROW_FOR_BINDING))
    def test_linux_column_matches_default(self, name, defaults, documented):
        _, shown = documented[_ROW_FOR_BINDING[name]]
        assert shown == _as_documented(defaults["linux"][name], macos=False)


class TestAccelRendering:
    @pytest.mark.parametrize("accel,macos,expected", [
        ("<Meta>z",                    True,  "Cmd+Z"),
        ("<Control><Shift>z",          False, "Ctrl+Shift+Z"),
        ("<Meta><Shift>d",             True,  "Cmd+Shift+D"),
        ("<Meta>comma",                True,  "Cmd+,"),
        ("<Meta><Alt>bracketright",    True,  "Cmd+Option+]"),
        ("<Control>Page_Up",           False, "Ctrl+Page Up"),
    ])
    def test_renders_like_the_readme(self, accel, macos, expected):
        assert _as_documented(accel, macos) == expected
