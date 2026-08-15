import json
import pytest
from unittest.mock import MagicMock

from roboterm.settings import Settings, THEMES, _default_keybindings, _rgba_to_hex


@pytest.fixture(autouse=True)
def reset_singleton():
    Settings._instance = None
    yield
    Settings._instance = None


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    config = str(tmp_path / "settings.json")
    monkeypatch.setattr(Settings, "CONFIG_PATH", config)
    return config


# ── _rgba_to_hex ──────────────────────────────────────────────────────────────

class TestRgbaToHex:
    def _rgba(self, r, g, b):
        m = MagicMock()
        m.red, m.green, m.blue = r, g, b
        return m

    def test_black(self):
        assert _rgba_to_hex(self._rgba(0.0, 0.0, 0.0)) == "#000000"

    def test_white(self):
        assert _rgba_to_hex(self._rgba(1.0, 1.0, 1.0)) == "#ffffff"

    def test_pure_red(self):
        assert _rgba_to_hex(self._rgba(1.0, 0.0, 0.0)) == "#ff0000"

    def test_pure_green(self):
        assert _rgba_to_hex(self._rgba(0.0, 1.0, 0.0)) == "#00ff00"

    def test_pure_blue(self):
        assert _rgba_to_hex(self._rgba(0.0, 0.0, 1.0)) == "#0000ff"

    def test_rounding(self):
        # 0.5 * 255 = 127.5 → rounds to 128 = 0x80
        assert _rgba_to_hex(self._rgba(0.5, 0.5, 0.5)) == "#808080"

    def test_output_is_lowercase(self):
        result = _rgba_to_hex(self._rgba(0.678, 0.345, 0.123))
        assert result == result.lower()

    def test_output_starts_with_hash(self):
        assert _rgba_to_hex(self._rgba(0.1, 0.2, 0.3)).startswith("#")

    def test_output_length(self):
        assert len(_rgba_to_hex(self._rgba(0.1, 0.2, 0.3))) == 7


# ── Settings defaults ─────────────────────────────────────────────────────────

class TestDefaults:
    def test_all_default_keys_present(self, tmp_config):
        s = Settings.get()
        for key in Settings.DEFAULTS:
            assert s.get_value(key) == Settings.DEFAULTS[key]

    def test_default_font(self, tmp_config):
        assert Settings.get().get_value("font") == "Monospace 12"

    def test_default_theme(self, tmp_config):
        assert Settings.get().get_value("theme") == "Custom"

    def test_default_scrollback(self, tmp_config):
        assert Settings.get().get_value("scrollback_lines") == 10_000

    def test_default_palette_is_none(self, tmp_config):
        assert Settings.get().get_value("palette") is None

    def test_default_bold_is_bright(self, tmp_config):
        assert Settings.get().get_value("bold_is_bright") is False


# ── Singleton ─────────────────────────────────────────────────────────────────

class TestSingleton:
    def test_same_instance(self, tmp_config):
        a = Settings.get()
        b = Settings.get()
        assert a is b

    def test_mutation_visible_on_second_get(self, tmp_config):
        Settings.get().set_value("font", "Hack 11")
        assert Settings.get().get_value("font") == "Hack 11"


# ── Persistence ───────────────────────────────────────────────────────────────

class TestPersistence:
    def test_value_survives_reload(self, tmp_config):
        Settings.get().set_value("font", "Fira Code 14")
        Settings._instance = None
        assert Settings.get().get_value("font") == "Fira Code 14"

    def test_multiple_values_survive_reload(self, tmp_config):
        s = Settings.get()
        s.set_value("font", "JetBrains Mono 12")
        s.set_value("scrollback_lines", 50_000)
        Settings._instance = None
        s2 = Settings.get()
        assert s2.get_value("font") == "JetBrains Mono 12"
        assert s2.get_value("scrollback_lines") == 50_000

    def test_unknown_keys_in_file_are_ignored(self, tmp_config):
        with open(tmp_config, "w") as f:
            json.dump({"unknown_key": "ignored", "font": "Roboto Mono 10"}, f)
        assert Settings.get().get_value("font") == "Roboto Mono 10"

    def test_missing_file_gives_defaults(self, tmp_config):
        # tmp_config path exists but file was not written
        assert Settings.get().get_value("font") == Settings.DEFAULTS["font"]

    def test_corrupt_file_gives_defaults(self, tmp_config):
        with open(tmp_config, "w") as f:
            f.write("{ not valid json }")
        assert Settings.get().get_value("font") == Settings.DEFAULTS["font"]

    def test_save_creates_parent_directory(self, tmp_path, monkeypatch):
        nested = str(tmp_path / "a" / "b" / "settings.json")
        monkeypatch.setattr(Settings, "CONFIG_PATH", nested)
        Settings.get().set_value("font", "Hack 10")
        import os
        assert os.path.exists(nested)


# ── Callbacks ─────────────────────────────────────────────────────────────────

class TestCallbacks:
    def test_callback_fires_on_set_value(self, tmp_config):
        calls = []
        Settings.get().connect_changed(lambda: calls.append(1))
        Settings.get().set_value("font", "Hack 10")
        assert calls == [1]

    def test_callback_fires_each_set(self, tmp_config):
        calls = []
        Settings.get().connect_changed(lambda: calls.append(1))
        Settings.get().set_value("font", "A")
        Settings.get().set_value("font", "B")
        assert calls == [1, 1]

    def test_multiple_callbacks_all_fire(self, tmp_config):
        log = []
        s = Settings.get()
        s.connect_changed(lambda: log.append("x"))
        s.connect_changed(lambda: log.append("y"))
        s.set_value("font", "Z")
        assert log == ["x", "y"]

    def test_callback_fires_on_apply_theme(self, tmp_config):
        calls = []
        Settings.get().connect_changed(lambda: calls.append(1))
        Settings.get().apply_theme("Dracula")
        assert calls == [1]


# ── Keybindings ───────────────────────────────────────────────────────────────

class TestKeybindings:
    def test_maximize_pane_has_a_default(self, tmp_config):
        assert Settings.get().get_keybindings()["maximize-pane"]

    def test_maximize_pane_default_matches_platform(self, tmp_config):
        import roboterm.settings as settings_mod
        expected = "<Meta>z" if settings_mod._MACOS else "<Control><Shift>z"
        assert Settings.get().get_keybindings()["maximize-pane"] == expected

    def test_defaults_have_no_duplicate_accelerators(self, tmp_config):
        accels = [a for a in _default_keybindings().values() if a]
        assert len(accels) == len(set(accels))

    def test_maximize_pane_can_be_rebound(self, tmp_config):
        s = Settings.get()
        s.set_value("keybindings", {"maximize-pane": "<Control>z"})
        assert s.get_keybindings()["maximize-pane"] == "<Control>z"

    def test_rebinding_one_action_keeps_the_others(self, tmp_config):
        s = Settings.get()
        s.set_value("keybindings", {"maximize-pane": "<Control>z"})
        assert s.get_keybindings()["new-tab"] == _default_keybindings()["new-tab"]


# ── apply_theme ───────────────────────────────────────────────────────────────

class TestApplyTheme:
    def test_known_theme_sets_foreground(self, tmp_config):
        Settings.get().apply_theme("Dracula")
        assert Settings.get().get_value("foreground") == THEMES["Dracula"]["foreground"]

    def test_known_theme_sets_background(self, tmp_config):
        Settings.get().apply_theme("Dracula")
        assert Settings.get().get_value("background") == THEMES["Dracula"]["background"]

    def test_known_theme_sets_palette(self, tmp_config):
        Settings.get().apply_theme("Dracula")
        assert Settings.get().get_value("palette") == THEMES["Dracula"]["palette"]

    def test_known_theme_sets_theme_name(self, tmp_config):
        Settings.get().apply_theme("Nord")
        assert Settings.get().get_value("theme") == "Nord"

    def test_custom_clears_palette(self, tmp_config):
        s = Settings.get()
        s.apply_theme("Dracula")
        s.apply_theme("Custom")
        assert s.get_value("palette") is None

    def test_unknown_name_clears_palette(self, tmp_config):
        s = Settings.get()
        s.apply_theme("Dracula")
        s.apply_theme("DoesNotExist")
        assert s.get_value("palette") is None

    def test_theme_persists_after_reload(self, tmp_config):
        Settings.get().apply_theme("Nord")
        Settings._instance = None
        assert Settings.get().get_value("theme") == "Nord"

    @pytest.mark.parametrize("name", list(THEMES.keys()))
    def test_every_theme_can_be_applied(self, tmp_config, name):
        Settings.get().apply_theme(name)
        assert Settings.get().get_value("theme") == name
