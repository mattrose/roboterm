"""`roboterm.__version__` is what the About dialog shows; `Info.plist` is what
Finder, the Dock and `codesign` report. They are written in two different files
and nothing links them, so this pins them together — a bundle whose About box
disagrees with its own metadata is the kind of drift nobody notices by hand.
"""

import pathlib
import plistlib

import pytest

import roboterm

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
