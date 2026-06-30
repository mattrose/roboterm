import pytest

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Vte", "3.91")

from gi.repository import Vte

from roboterm.settings import Settings


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


@pytest.fixture
def vte_terminal():
    """Real Vte.Terminal instance."""
    try:
        return Vte.Terminal()
    except Exception as exc:
        pytest.skip(f"Cannot create Vte.Terminal: {exc}")
