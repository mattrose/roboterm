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

"""The app's identity is written down twice: in Python (what the About dialog
shows, what GApplication registers) and in `macos/Info.plist` (what Finder, the
Dock, `lsappinfo` and `codesign` report). Nothing links the two files, and they
have drifted before — the GApplication id said `com.example.GtkVteTerminal`
while the bundle said `net.folkwolf.roboterm`. These tests pin them together.
"""

import pathlib
import plistlib

import pytest

import roboterm
from roboterm.app import APP_ID

_INFO_PLIST = pathlib.Path(__file__).parents[2] / "macos" / "Info.plist"


@pytest.fixture(scope="module")
def plist():
    with _INFO_PLIST.open("rb") as fh:
        return plistlib.load(fh)


class TestVersion:
    def test_matches_info_plist(self, plist):
        assert roboterm.__version__ == plist["CFBundleShortVersionString"]

    def test_build_version_starts_with_it(self, plist):
        """CFBundleVersion may carry an extra build component (1.0 -> 1.0.0),
        but it must describe the same release."""
        build = plist["CFBundleVersion"]
        assert build == roboterm.__version__ or build.startswith(roboterm.__version__ + ".")

    def test_is_dotted_numeric(self):
        """Apple rejects anything else in CFBundleShortVersionString."""
        parts = roboterm.__version__.split(".")
        assert parts and all(p.isdigit() for p in parts)


class TestAppId:
    def test_matches_info_plist(self, plist):
        assert APP_ID == plist["CFBundleIdentifier"]

    def test_is_reverse_dns(self):
        """GApplication rejects ids that aren't reverse-DNS, and macOS expects
        the same shape — a lone word would pass a naive equality check on both
        sides while still being wrong."""
        parts = APP_ID.split(".")
        assert len(parts) >= 2
        assert all(p and not p[0].isdigit() for p in parts)
        assert all(c.isalnum() or c in "-_" for p in parts for c in p)

    def test_is_not_a_placeholder(self):
        """The id it drifted to last time, and its siblings."""
        assert not APP_ID.startswith(("com.example", "org.example", "org.gtk.example"))
