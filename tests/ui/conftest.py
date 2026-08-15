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
Session-scoped fixtures for PyAutoGUI GUI tests.

Starts an Xvfb virtual display at module load time (before pyautogui is
imported, since pyautogui connects to the X display on import), then
launches roboterm via dbus-run-session and waits for its window.
"""
import os
import signal
import subprocess
import sys
import time

import pytest

# ── Bootstrap a display before pyautogui tries to connect ────────────────────
# pyautogui opens the X display at import time on Linux.  We must ensure
# DISPLAY is set before the import happens.
_STARTED_DISPLAY = None
if not os.environ.get("DISPLAY"):
    from pyvirtualdisplay import Display as _Display
    _STARTED_DISPLAY = _Display(visible=False, size=(1280, 1024), color_depth=24)
    _STARTED_DISPLAY.start()
    os.environ["DISPLAY"] = _STARTED_DISPLAY.new_display_var

# pyscreeze checks XDG_SESSION_TYPE at import time to choose screenshot backend.
# Force x11 so it uses scrot (which we have installed).
os.environ.setdefault("XDG_SESSION_TYPE", "x11")

import pyautogui  # noqa: E402  (must follow display setup above)

from tests.ui.helpers import WindowHelper, wait_for_window  # noqa: E402

REPO_ROOT           = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
APP_STARTUP_TIMEOUT = 20.0


def _find_python_with_gi() -> str:
    """
    Return a python3 executable that can import gi (PyGObject) — the app needs
    it, and only some interpreters on the box have it installed.

    Prefers $ROBOTERM_TEST_PYTHON if set, then the interpreter running the tests,
    then plain `python3`, then `python3.N` for a range of minor versions. Fails
    the test run (rather than crashing collection) if none is found.
    """
    candidates = [
        os.environ.get("ROBOTERM_TEST_PYTHON"),
        sys.executable,
        "python3",
    ]
    candidates += [f"python3.{minor}" for minor in range(15, 8, -1)]  # 3.15 → 3.9

    seen = set()
    for exe in candidates:
        if not exe or exe in seen:
            continue
        seen.add(exe)
        try:
            r = subprocess.run([exe, "-c", "import gi"], capture_output=True)
        except OSError:
            continue  # not on PATH / not executable
        if r.returncode == 0:
            return exe
    return ""


# Resolved once per session; empty if nothing suitable was found (the `app`
# fixture turns that into a clear skip/failure rather than an import-time crash).
PYTHON = _find_python_with_gi()

# dbus-run-session wraps the app in a private D-Bus session, required by GTK4.
APP_CMD = ["dbus-run-session", PYTHON, "roboterm.py"]


@pytest.fixture(scope="session", autouse=True)
def virtual_display():
    """Yield the active DISPLAY string; stop Xvfb at session end if we started it."""
    yield os.environ["DISPLAY"]
    if _STARTED_DISPLAY is not None:
        _STARTED_DISPLAY.stop()


@pytest.fixture(scope="session", autouse=True)
def _pyautogui_settings():
    pyautogui.PAUSE    = 0.20
    pyautogui.FAILSAFE = False


def _window_width(window_id: str) -> int:
    """Return the window's current width, or 0 on failure."""
    r = subprocess.run(
        ["xdotool", "getwindowgeometry", "--shell", window_id],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        return 0
    for line in r.stdout.splitlines():
        if line.startswith("WIDTH="):
            try:
                return int(line.split("=", 1)[1])
            except ValueError:
                return 0
    return 0


@pytest.fixture()
def app(tmp_path, virtual_display):
    """
    Launch roboterm, wait for its window, yield:
        proc       — subprocess.Popen
        window_id  — xdotool window ID string (the "Terminal" window)
        helper     — WindowHelper bound to that window
    """
    env = os.environ.copy()
    env["DISPLAY"]               = virtual_display
    env["GDK_BACKEND"]           = "x11"
    env["GTK_A11Y"]              = "none"   # skip accessibility bus (not available in CI)
    env["HOME"]                  = str(tmp_path)
    env["GTK_DECORATION_LAYOUT"] = ":"      # no window buttons → hamburger flush at right edge

    if not PYTHON:
        pytest.fail(
            "No python3 with gi (PyGObject) found for UI tests. "
            "Install PyGObject or set ROBOTERM_TEST_PYTHON to a suitable interpreter."
        )

    # start_new_session=True puts dbus-run-session and its children (the python
    # interpreter running roboterm) in a new process group.  This lets teardown
    # kill the entire group with os.killpg, preventing orphaned interpreter
    # processes from leaving stale "Terminal" windows that confuse wait_for_window.
    proc = subprocess.Popen(
        APP_CMD,
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )

    # dbus-run-session forks, so proc.pid is dbus-run-session, not the interpreter.
    # Wait for a window named "Terminal" to appear on the display.
    window_id = wait_for_window(name="Terminal", timeout=APP_STARTUP_TIMEOUT)
    if window_id is None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        stderr = proc.stderr.read().decode(errors="replace")
        pytest.fail(
            f"roboterm window did not appear within {APP_STARTUP_TIMEOUT}s.\n"
            f"stderr:\n{stderr}"
        )

    # GTK4 maps windows at 1×1 initially and resizes them shortly after.
    # Poll until the window reaches its intended width (up to 5 s extra).
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if _window_width(window_id) > 100:
            break
        time.sleep(0.1)

    # Unconditional 1.0 s: VTE shell startup + time for any X11 keyboard grab
    # from a previous popover teardown to be fully released before the first
    # test action.
    time.sleep(1.0)

    helper = WindowHelper(window_id)
    yield {"proc": proc, "window_id": window_id, "helper": helper}

    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()
