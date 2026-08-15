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

import subprocess
import time


class WindowHelper:
    """Thin wrapper around xdotool for a specific X window."""

    def __init__(self, window_id: str):
        self.window_id = window_id

    def title(self) -> str:
        r = subprocess.run(
            ["xdotool", "getwindowname", self.window_id],
            capture_output=True, text=True, check=True,
        )
        return r.stdout.strip()

    def geometry(self) -> dict:
        """Returns {'X': int, 'Y': int, 'WIDTH': int, 'HEIGHT': int}."""
        r = subprocess.run(
            ["xdotool", "getwindowgeometry", "--shell", self.window_id],
            capture_output=True, text=True, check=True,
        )
        geo = {}
        for line in r.stdout.strip().split("\n"):
            if "=" in line:
                k, v = line.split("=", 1)
                geo[k.strip()] = int(v.strip())
        return geo

    def focus(self) -> None:
        # windowactivate requires a WM that supports _NET_ACTIVE_WINDOW; skip it.
        # windowraise + windowfocus work on bare Xvfb with no WM.
        subprocess.run(["xdotool", "windowraise", self.window_id], check=False)
        subprocess.run(["xdotool", "windowfocus", self.window_id], check=False)
        time.sleep(0.25)

    def abs_point(self, rel_x: int, rel_y: int) -> tuple[int, int]:
        """Convert window-relative coords to screen-absolute coords."""
        g = self.geometry()
        return g["X"] + rel_x, g["Y"] + rel_y

    def headerbar_hamburger(self) -> tuple[int, int]:
        """
        Screen-absolute centre of the hamburger MenuButton.

        Adwaita ignores GTK_DECORATION_LAYOUT so the window always shows
        min/max/close buttons on the right.  The hamburger (pack_end) sits to
        the left of those three buttons, roughly 140 px from the right edge.
        """
        g = self.geometry()
        x = g["X"] + g["WIDTH"] - 140
        y = g["Y"] + 24
        return x, y

    def terminal_centre(self) -> tuple[int, int]:
        """Screen-absolute centre of the terminal content area (below header)."""
        g = self.geometry()
        HEADER_H = 47
        x = g["X"] + g["WIDTH"] // 2
        y = g["Y"] + HEADER_H + (g["HEIGHT"] - HEADER_H) // 2
        return x, y


def wait_for_window(name: str = "", pid: int | None = None, timeout: float = 15.0) -> str | None:
    """
    Poll xdotool until a matching window appears.
    Prefers --pid lookup when pid is provided; falls back to --name regex.
    Returns the window-id string, or None on timeout.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pid is not None:
            r = subprocess.run(
                ["xdotool", "search", "--pid", str(pid)],
                capture_output=True, text=True,
            )
        else:
            r = subprocess.run(
                ["xdotool", "search", "--name", f"^{name}$"],
                capture_output=True, text=True,
            )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().split()[-1]
        time.sleep(0.2)
    return None


def wait_for_named_window(name: str, timeout: float = 10.0) -> str | None:
    """Poll xdotool until a window whose name contains `name` appears."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = subprocess.run(
            ["xdotool", "search", "--name", name],
            capture_output=True, text=True,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().split()[-1]
        time.sleep(0.2)
    return None
