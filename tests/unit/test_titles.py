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
