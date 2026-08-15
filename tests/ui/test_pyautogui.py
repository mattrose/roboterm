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

"""
End-to-end GUI smoke tests for roboterm using PyAutoGUI.

Each test gets a fresh `app` fixture (a new process + window).
Visual verification uses raw pixel-change counting rather than template
matching to avoid GTK theme fragility.

Run headless (Xvfb started automatically by conftest):
    pytest tests/ui/ -v

Run on a real X display:
    DISPLAY=:0 GDK_BACKEND=x11 pytest tests/ui/ -v
"""
import subprocess
import time

import pyautogui
import pytest
from PIL import Image

from tests.ui.helpers import WindowHelper, wait_for_named_window

pytestmark = pytest.mark.ui

HEADERBAR_H = 47   # px — Adwaita CSD header bar height
TAB_BAR_H   = 35   # px — Gtk.Notebook tab strip height


# ── Pixel helpers ─────────────────────────────────────────────────────────────

def _shot(x: int, y: int, w: int, h: int) -> Image.Image:
    return pyautogui.screenshot(region=(x, y, w, h))


def _changed(before: Image.Image, after: Image.Image) -> int:
    b = before.tobytes()
    a = after.tobytes()
    ch = len(before.getbands())
    return sum(
        b[i * ch:(i + 1) * ch] != a[i * ch:(i + 1) * ch]
        for i in range(len(b) // ch)
    )


def _pixel_variance(img: Image.Image) -> float:
    import statistics
    values = list(img.convert("RGB").tobytes())
    return statistics.stdev(values) if len(values) > 1 else 0.0


# ═════════════════════════════════════════════════════════════════════════════
# Test 1 — Window basics
# ═════════════════════════════════════════════════════════════════════════════

class TestWindowBasics:

    def test_window_title(self, app):
        assert app["helper"].title() == "Terminal"

    def test_window_default_size(self, app):
        g = app["helper"].geometry()
        assert abs(g["WIDTH"]  - 900) <= 20, f"unexpected width: {g}"
        assert abs(g["HEIGHT"] - 600) <= 20, f"unexpected height: {g}"

    def test_window_renders_non_blank(self, app):
        helper: WindowHelper = app["helper"]
        # Raise and focus the window to trigger any pending GTK4 expose/draw
        # events that have not yet been flushed to the X11 backing store.
        helper.focus()
        g   = helper.geometry()
        var = 0.0
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            img = _shot(g["X"], g["Y"], g["WIDTH"], g["HEIGHT"])
            var = _pixel_variance(img)
            if var > 5.0:
                break
            time.sleep(0.2)
        assert var > 5.0, (
            f"Window appears blank (pixel stdev={var:.1f}). GTK may not have rendered."
        )


# ═════════════════════════════════════════════════════════════════════════════
# Test 2 — Hamburger menu
# ═════════════════════════════════════════════════════════════════════════════

class TestHamburgerMenu:

    def _menu_region(self, g: dict) -> tuple:
        """
        The popover appears below the hamburger button in the top-right area.
        Capture the right 300px wide, 250px tall region (from the headerbar down).
        Pre-compute from a geometry dict to avoid calling geometry() after a click.
        """
        return g["X"] + g["WIDTH"] - 300, g["Y"], 300, 250

    def test_menu_opens_on_click(self, app):
        helper: WindowHelper = app["helper"]
        helper.focus()

        # Pre-compute all coordinates BEFORE clicking (popover creation can
        # temporarily affect window state on bare Xvfb).
        g = helper.geometry()
        region = self._menu_region(g)
        hx, hy = helper.headerbar_hamburger()

        before = _shot(*region)
        pyautogui.click(hx, hy)
        time.sleep(0.6)
        after = _shot(*region)

        # Dismiss before asserting so subsequent tests start clean
        pyautogui.press("escape")
        time.sleep(0.2)

        assert _changed(before, after) > 0, (
            "Top-right window region did not change after clicking the hamburger. "
            "The popover menu may not have opened."
        )

    def test_menu_dismissed_by_escape(self, app):
        helper: WindowHelper = app["helper"]
        helper.focus()

        g = helper.geometry()
        region = self._menu_region(g)
        hx, hy = helper.headerbar_hamburger()

        pyautogui.click(hx, hy)
        time.sleep(0.6)
        with_menu = _shot(*region)

        pyautogui.press("escape")
        time.sleep(0.4)
        after_dismiss = _shot(*region)

        assert _changed(with_menu, after_dismiss) > 0, (
            "Escape did not dismiss the hamburger menu — region unchanged."
        )


# ═════════════════════════════════════════════════════════════════════════════
# Test 3 — New tab (Ctrl+Shift+T)
# ═════════════════════════════════════════════════════════════════════════════

class TestNewTab:

    def _tab_strip(self, helper: WindowHelper) -> tuple:
        g = helper.geometry()
        return g["X"], g["Y"] + HEADERBAR_H, g["WIDTH"], TAB_BAR_H

    def test_new_tab_via_ctrl_shift_t(self, app):
        helper: WindowHelper = app["helper"]
        helper.focus()

        before = _shot(*self._tab_strip(helper))

        pyautogui.hotkey("ctrl", "shift", "t")
        time.sleep(0.7)

        after = _shot(*self._tab_strip(helper))

        assert _changed(before, after) > 50, (
            "Tab-bar region barely changed after Ctrl+Shift+T. "
            "The second tab may not have been created."
        )
        assert app["proc"].poll() is None, "App crashed after creating new tab"


# ═════════════════════════════════════════════════════════════════════════════
# Test 4 — Typing in the terminal
# ═════════════════════════════════════════════════════════════════════════════

class TestTypingOutput:

    def _content_region(self, helper: WindowHelper) -> tuple:
        g = helper.geometry()
        return g["X"], g["Y"] + HEADERBAR_H, g["WIDTH"], g["HEIGHT"] - HEADERBAR_H

    def test_typed_command_changes_terminal(self, app):
        helper: WindowHelper = app["helper"]
        helper.focus()

        tx, ty = helper.terminal_centre()
        pyautogui.click(tx, ty)
        time.sleep(0.2)

        before = _shot(*self._content_region(helper))

        pyautogui.typewrite("printf 'RBTOK\\n'", interval=0.04)
        pyautogui.press("return")
        time.sleep(0.8)

        after = _shot(*self._content_region(helper))
        assert _changed(before, after) > 100, (
            "Terminal content barely changed after typing a command."
        )

    def test_second_command_changes_terminal(self, app):
        helper: WindowHelper = app["helper"]
        helper.focus()

        tx, ty = helper.terminal_centre()
        pyautogui.click(tx, ty)
        time.sleep(0.2)

        pyautogui.typewrite("true", interval=0.04)
        pyautogui.press("return")
        time.sleep(0.5)

        before = _shot(*self._content_region(helper))

        pyautogui.typewrite("printf 'RBTOK2\\n'", interval=0.04)
        pyautogui.press("return")
        time.sleep(0.8)

        after = _shot(*self._content_region(helper))
        assert _changed(before, after) > 100
        assert app["proc"].poll() is None


# ═════════════════════════════════════════════════════════════════════════════
# Test 5 — Preferences window
# ═════════════════════════════════════════════════════════════════════════════

class TestPreferences:

    def test_preferences_opens_via_keyboard(self, app):
        helper: WindowHelper = app["helper"]
        helper.focus()

        # Give VTE keyboard focus, then press Ctrl+,.  The shortcut is handled
        # by a CAPTURE-phase controller on the window so it fires before VTE.
        pyautogui.click(*helper.terminal_centre())
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", ",")
        prefs_id = wait_for_named_window("Preferences", timeout=5.0)

        assert prefs_id is not None, (
            "Preferences window did not appear within 5 s after Ctrl+,"
        )

        subprocess.run(["xdotool", "windowclose", prefs_id], check=False)
        time.sleep(0.3)

    def test_preferences_opens_via_menu(self, app):
        helper: WindowHelper = app["helper"]
        helper.focus()

        g   = helper.geometry()
        hx, hy = helper.headerbar_hamburger()
        # Capture only the menu area: right 300 px, top 450 px (covers all items).
        # Using a narrow region avoids VTE cursor blink polluting the diff.
        menu_region = (g["X"] + g["WIDTH"] - 300, g["Y"], 300, 450)

        # Baseline screenshot before clicking — lets the window settle.
        before = _shot(*menu_region)

        # Open the hamburger menu; retry once if the popover did not appear.
        for _attempt in range(2):
            pyautogui.click(hx, hy)
            time.sleep(1.0)

            # Poll until the menu region stabilises (Adwaita open animation
            # complete).  On a loaded system this can take over 1 s.
            prev = _shot(*menu_region)
            curr = prev
            for _ in range(30):  # up to 3 s extra
                time.sleep(0.1)
                curr = _shot(*menu_region)
                if _changed(prev, curr) < 10:
                    break
                prev = curr

            if _changed(before, curr) > 50:
                break
            # Popover did not open; dismiss anything stray and retry.
            pyautogui.press("escape")
            time.sleep(0.3)

        # Navigate to Preferences using keyboard instead of mouse coordinates.
        # The menu has 9 items (New Window, New Tab, Split Auto, Split Right,
        # Split Down, Rotate CW, Rotate CCW, Close Pane, Preferences).
        # GTK4 popover grabs the keyboard; XTEST key events are delivered to the
        # grab owner, so Down×8 navigates from item 1 to item 9, then Return
        # activates it.
        for _ in range(8):
            pyautogui.press("down")
        pyautogui.press("return")
        time.sleep(0.5)

        prefs_id = wait_for_named_window("Preferences", timeout=5.0)
        assert prefs_id is not None, (
            "Preferences window did not appear after selecting via hamburger menu."
        )
        subprocess.run(["xdotool", "windowclose", prefs_id], check=False)
        time.sleep(0.3)


# ═════════════════════════════════════════════════════════════════════════════
# Test 6 — Split panes
# ═════════════════════════════════════════════════════════════════════════════

class TestSplitPanes:

    def _content_region(self, helper: WindowHelper) -> tuple:
        g = helper.geometry()
        return g["X"], g["Y"] + HEADERBAR_H, g["WIDTH"], g["HEIGHT"] - HEADERBAR_H

    def test_split_right_creates_two_panes(self, app):
        helper: WindowHelper = app["helper"]
        helper.focus()
        pyautogui.click(*helper.terminal_centre())
        time.sleep(0.2)

        before = _shot(*self._content_region(helper))

        pyautogui.hotkey("ctrl", "shift", "e")
        time.sleep(1.0)

        after = _shot(*self._content_region(helper))
        assert _changed(before, after) > 200, (
            "Content barely changed after Ctrl+Shift+E (split right)."
        )
        assert app["proc"].poll() is None

    def test_split_down_creates_two_panes(self, app):
        helper: WindowHelper = app["helper"]
        helper.focus()
        pyautogui.click(*helper.terminal_centre())
        time.sleep(0.2)

        before = _shot(*self._content_region(helper))

        pyautogui.hotkey("ctrl", "shift", "o")
        time.sleep(1.0)

        after = _shot(*self._content_region(helper))
        assert _changed(before, after) > 200, (
            "Content barely changed after Ctrl+Shift+O (split down)."
        )
        assert app["proc"].poll() is None

    def test_close_pane_removes_split(self, app):
        helper: WindowHelper = app["helper"]
        helper.focus()
        pyautogui.click(*helper.terminal_centre())
        time.sleep(0.2)

        single = _shot(*self._content_region(helper))

        pyautogui.hotkey("ctrl", "shift", "e")
        time.sleep(1.0)
        split = _shot(*self._content_region(helper))

        pyautogui.hotkey("ctrl", "shift", "w")
        time.sleep(0.7)
        restored = _shot(*self._content_region(helper))

        changed_by_split   = _changed(single, split)
        changed_by_restore = _changed(split, restored)

        assert changed_by_restore >= changed_by_split * 0.7, (
            f"Close-pane restored only {changed_by_restore} px "
            f"vs {changed_by_split} px changed by split."
        )
        assert app["proc"].poll() is None
