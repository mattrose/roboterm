"""The macOS menu bar shows hardcoded accelerator labels (see CLAUDE.md): they
are display-only, and pressing the key actually goes through
TerminalWindow's key table.  Nothing forces the two to agree, so this guards
against the labels drifting away from the real default keybindings.
"""

import pathlib
import re

import pytest

import roboterm.settings as settings_mod
from roboterm.settings import _default_keybindings

_APP_PY = pathlib.Path(__file__).parents[2] / "roboterm" / "app.py"

_ACCEL_CALL = re.compile(
    r'set_accels_for_action\(\s*"(?:win|app)\.([a-z0-9-]+)"\s*,\s*\[([^\]]*)\]\s*\)'
)

# Menu items whose shortcut is handled in TerminalWidget._on_key_pressed rather
# than through Settings, so they have no entry to compare against.
_NOT_IN_SETTINGS = {"copy", "paste"}


@pytest.fixture
def macos_defaults(monkeypatch):
    """The macOS keybindings, whatever platform the tests run on."""
    monkeypatch.setattr(settings_mod, "_MACOS", True)
    return _default_keybindings()


def _menu_accels() -> dict:
    """{action name: accelerator} as written in _setup_menubar."""
    source = _APP_PY.read_text()
    return {
        action: accels.strip().strip('"')
        for action, accels in _ACCEL_CALL.findall(source)
    }


class TestMenuAccelLabels:
    def test_accel_calls_are_found(self):
        assert len(_menu_accels()) > 5

    def test_every_menu_action_is_a_real_keybinding(self, macos_defaults):
        unknown = set(_menu_accels()) - set(macos_defaults) - _NOT_IN_SETTINGS
        assert unknown == set()

    @pytest.mark.parametrize("action", sorted(set(_menu_accels()) - _NOT_IN_SETTINGS))
    def test_label_matches_default_keybinding(self, action, macos_defaults):
        assert _menu_accels()[action] == macos_defaults[action]
