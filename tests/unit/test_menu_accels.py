"""The macOS menu bar's shortcut labels are derived from the keybindings, so
they cannot drift from what the keys actually do (see CLAUDE.md).  These tests
cover that derivation, and that no hardcoded accelerator creeps back in.
"""

import pathlib
import re

import pytest

import roboterm.settings as settings_mod
from roboterm.app import _FIXED_MENU_ACCELS, _MENU_ACCEL_ACTIONS, _menu_accels
from roboterm.settings import _default_keybindings

_APP_PY = pathlib.Path(__file__).parents[2] / "roboterm" / "app.py"

_LITERAL_ACCEL_CALL = re.compile(r'set_accels_for_action\(\s*"[^"]+"\s*,\s*\[')


@pytest.fixture
def macos_defaults(monkeypatch):
    """The macOS keybindings, whatever platform the tests run on."""
    monkeypatch.setattr(settings_mod, "_MACOS", True)
    return _default_keybindings()


class TestMenuAccelActions:
    def test_every_mapped_action_is_a_real_keybinding(self, macos_defaults):
        assert set(_MENU_ACCEL_ACTIONS) <= set(macos_defaults)

    def test_action_names_are_namespaced(self):
        assert all(a.startswith(("win.", "app.")) for a in _MENU_ACCEL_ACTIONS.values())

    def test_no_hardcoded_accelerators_left_in_app_py(self):
        """Literal set_accels_for_action calls are what drifted before."""
        assert _LITERAL_ACCEL_CALL.search(_APP_PY.read_text()) is None


class TestMenuAccels:
    def test_defaults_are_passed_through(self, macos_defaults):
        accels = _menu_accels(macos_defaults)
        for name, action in _MENU_ACCEL_ACTIONS.items():
            assert accels[action] == [macos_defaults[name]]

    def test_split_right_matches_its_keybinding(self, macos_defaults):
        assert _menu_accels(macos_defaults)["win.split-right"] == ["<Meta>d"]

    def test_user_override_is_reflected(self, macos_defaults):
        overridden = {**macos_defaults, "split-right": "<Meta>k"}
        assert _menu_accels(overridden)["win.split-right"] == ["<Meta>k"]

    def test_disabled_binding_shows_no_shortcut(self, macos_defaults):
        assert _menu_accels({**macos_defaults, "new-tab": ""})["win.new-tab"] == []

    def test_missing_binding_shows_no_shortcut(self):
        assert _menu_accels({})["win.new-tab"] == []

    def test_copy_paste_labels_are_fixed(self, macos_defaults):
        accels = _menu_accels(macos_defaults)
        for action, accel in _FIXED_MENU_ACCELS.items():
            assert accels[action] == accel

    def test_copy_paste_are_not_keybindings(self, macos_defaults):
        assert "copy" not in macos_defaults and "paste" not in macos_defaults

    def test_every_menu_item_gets_an_entry(self, macos_defaults):
        expected = set(_MENU_ACCEL_ACTIONS.values()) | set(_FIXED_MENU_ACCELS)
        assert set(_menu_accels(macos_defaults)) == expected
