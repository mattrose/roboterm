import os
import sys

import gi

# Shown in the About dialog. Kept in step with macos/Info.plist's
# CFBundleShortVersionString by tests/unit/test_version.py.
__version__ = "1.0"

if sys.platform == "darwin":
    os.environ.setdefault("GSK_RENDERER", "cairo")

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Vte", "3.91")

from gi.repository import Adw


def _bind_bundled_locales() -> None:
    """Point gettext at the message catalogs inside the .app bundle.

    Every GTK/GLib dylib hardcodes its build-time Homebrew Cellar path as its
    gettext lookup directory, and `install_name_tool` can't rewrite a plain C
    string — so a relocated bundle looks somewhere that doesn't exist on a Mac
    without Homebrew and silently falls back to untranslated English. Rebinding
    each domain here is what makes the catalogs `macos/bundle_deps.py` copied
    into Resources/share/locale actually load.

    Runs after `Adw.init()` on purpose: GTK does its own `bindtextdomain` during
    init, so binding earlier would just be overwritten. The domain list comes
    from the manifest the bundler wrote, so it can't drift from what was copied.
    """
    res = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    locale_dir = os.path.join(res, "share", "locale")
    manifest = os.path.join(locale_dir, "domains")
    if not os.path.isfile(manifest):
        return  # source checkout or `make app` build — the Homebrew paths are live
    try:
        import ctypes

        libintl = ctypes.CDLL("libintl.8.dylib")
        libintl.bindtextdomain.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        libintl.bindtextdomain.restype = ctypes.c_char_p
        with open(manifest) as fh:
            for domain in fh.read().split():
                libintl.bindtextdomain(domain.encode(), locale_dir.encode())
    except (OSError, AttributeError):
        pass  # an untranslated UI is cosmetic — never fail to start over it


Adw.init()

if sys.platform == "darwin":
    _bind_bundled_locales()
