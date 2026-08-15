#!/usr/bin/env python3
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

"""Generate Roboterm.icns from a Cairo-drawn terminal icon.

Also installs the same artwork into a hicolor icon theme inside the bundle, so
GTK can resolve it by name (the About dialog's `application_icon`). macOS uses
the .icns for the Dock; GTK never reads .icns, hence both.
"""
import cairo
import math
import os
import plistlib
import shutil
import subprocess
import sys

SIZES = [16, 32, 64, 128, 256, 512, 1024]

# Sizes installed into the icon theme. The About dialog draws at 128px; the rest
# give GTK exact matches instead of rescaling.
THEME_SIZES = [32, 64, 128, 256, 512]

_INFO_PLIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Info.plist")

# Colours
BG      = (0.118, 0.122, 0.149)   # #1e1f26  dark blue-grey
SURFACE = (0.153, 0.161, 0.196)   # #272833  slightly lighter panel
GREEN   = (0.306, 0.878, 0.455)   # #4ee074  bright green
DIM     = (0.500, 0.510, 0.580)   # muted for the cursor bar


def rounded_rect(ctx, x, y, w, h, r):
    ctx.new_sub_path()
    ctx.arc(x + r,     y + r,     r, math.pi,       3 * math.pi / 2)
    ctx.arc(x + w - r, y + r,     r, 3 * math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0,             math.pi / 2)
    ctx.arc(x + r,     y + h - r, r, math.pi / 2,   math.pi)
    ctx.close_path()


def draw_icon(size: int) -> cairo.ImageSurface:
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx  = cairo.Context(surf)
    ctx.set_antialias(cairo.ANTIALIAS_BEST)

    s = size  # shorthand

    # ── Background rounded rect ──────────────────────────────────────────
    pad = s * 0.06
    r   = s * 0.18
    ctx.set_source_rgb(*BG)
    rounded_rect(ctx, pad, pad, s - 2 * pad, s - 2 * pad, r)
    ctx.fill()

    # ── Thin title-bar strip ─────────────────────────────────────────────
    bar_h = s * 0.13
    ctx.set_source_rgb(*SURFACE)
    rounded_rect(ctx, pad, pad, s - 2 * pad, bar_h + r, r)
    ctx.fill()
    # square off the bottom of the strip
    ctx.rectangle(pad, pad + r, s - 2 * pad, bar_h - r)
    ctx.fill()

    # Three traffic-light dots in the bar
    dot_r  = s * 0.038
    dot_y  = pad + bar_h * 0.52
    colors = [(0.937, 0.376, 0.357),   # red
              (0.980, 0.788, 0.318),   # yellow
              (0.259, 0.773, 0.373)]   # green
    for i, c in enumerate(colors):
        dot_x = pad + s * 0.09 + i * (dot_r * 2.8)
        ctx.set_source_rgb(*c)
        ctx.arc(dot_x, dot_y, dot_r, 0, 2 * math.pi)
        ctx.fill()

    # ── Prompt text  ">_" ────────────────────────────────────────────────
    font_size = s * 0.36
    ctx.select_font_face("Courier", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(font_size)

    text = ">_"
    ext  = ctx.text_extents(text)
    tx   = (s - ext.width)  / 2 - ext.x_bearing
    ty   = pad + bar_h + (s - pad - bar_h - ext.height) / 2 - ext.y_bearing + s * 0.01

    ctx.set_source_rgb(*GREEN)
    ctx.move_to(tx, ty)
    ctx.show_text(text)

    return surf


def app_id() -> str:
    """The bundle identifier, which is also the icon's themed name.

    Read from Info.plist rather than hardcoded: tests/unit/test_version.py
    already pins that key to roboterm.app.APP_ID, so this stays in step with
    the id the About dialog asks for without importing gi at build time.
    """
    with open(_INFO_PLIST, "rb") as fh:
        return plistlib.load(fh)["CFBundleIdentifier"]


def install_theme_icon(out_dir: str) -> None:
    """Write the icon into <out_dir>/share/icons/hicolor as <app-id>.png."""
    name = app_id()
    for size in THEME_SIZES:
        dest = os.path.join(out_dir, "share", "icons", "hicolor",
                            f"{size}x{size}", "apps")
        os.makedirs(dest, exist_ok=True)
        path = os.path.join(dest, f"{name}.png")
        draw_icon(size).write_to_png(path)
    print(f"  wrote hicolor theme icon {name}.png ({len(THEME_SIZES)} sizes)")


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    iconset  = os.path.join(out_dir, "Roboterm.iconset")
    os.makedirs(iconset, exist_ok=True)

    for size in SIZES:
        surf = draw_icon(size)
        for scale, suffix in ((1, ""), (2, "@2x")):
            if scale == 2 and size > 512:
                continue  # 1024@2x not needed
            fname = os.path.join(iconset, f"icon_{size}x{size}{suffix}.png")
            surf2 = draw_icon(size * scale) if scale == 2 else surf
            surf2.write_to_png(fname)
            print(f"  wrote {fname}")

    icns = os.path.join(out_dir, "Roboterm.icns")
    subprocess.run(["iconutil", "-c", "icns", iconset, "-o", icns], check=True)
    shutil.rmtree(iconset)
    print(f"Created {icns}")

    install_theme_icon(out_dir)


if __name__ == "__main__":
    main()
