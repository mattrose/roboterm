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

import os

from roboterm.terminal import _title_for_directory


HOME = os.path.expanduser("~")


class TestTitleForDirectory:
    def test_home_is_tilde(self):
        assert _title_for_directory(HOME) == "~"

    def test_home_with_trailing_slash_uses_basename(self):
        # A trailing slash means the path is not literally $HOME; the basename
        # is still a sensible title.
        assert _title_for_directory(HOME + "/") == os.path.basename(HOME)

    def test_nested_directory_uses_basename(self):
        assert _title_for_directory("/Users/someone/Code/roboterm") == "roboterm"

    def test_trailing_slash_is_ignored(self):
        assert _title_for_directory("/usr/local/") == "local"

    def test_root_stays_root(self):
        assert _title_for_directory("/") == "/"

    def test_directory_with_spaces(self):
        assert _title_for_directory("/tmp/my project") == "my project"
