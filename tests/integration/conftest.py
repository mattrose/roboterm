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
