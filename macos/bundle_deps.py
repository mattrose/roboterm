#!/usr/bin/env python3
"""Make Roboterm.app self-contained on macOS.

`make app` builds a bundle whose launcher points back into Homebrew at runtime.
This script (run by `make bundle` after `make app`) copies the entire native
stack — the Python framework, the GTK4/VTE dylib closure, PyGObject/pycairo,
GObject-introspection typelibs, GSettings schemas, gdk-pixbuf loaders, gettext
message catalogs and the Adwaita icon theme — into the .app and rewrites every
`install name` so nothing references `/opt/homebrew`. The result runs on a Mac
(same CPU arch) with no Homebrew installed.

Everything is derived from the interpreter running this script via `sysconfig`,
so there is no hardcoded Python version or Homebrew prefix. Invoke as:

    python3 macos/bundle_deps.py Roboterm.app

using the same interpreter the bundle was built against (the Makefile passes
$(PYTHON)).
"""
import glob
import os
import shutil
import subprocess
import sys
import sysconfig

PY_VER = "%d.%d" % sys.version_info[:2]

# ── Derived source locations (all from the running interpreter) ──────────────
PURELIB = sysconfig.get_path("purelib")                       # .../lib/pythonX.Y/site-packages
BREW = os.path.dirname(os.path.dirname(os.path.dirname(PURELIB)))  # e.g. /opt/homebrew
FRAMEWORK_SRC = os.path.join(sysconfig.get_config_var("PYTHONFRAMEWORKPREFIX"), "Python.framework")
FRAMEWORK_PY_REL = "Python.framework/Versions/%s/Python" % PY_VER

# rpaths added to every relocated Mach-O so @rpath deps resolve inside the .app
# regardless of where the file sits (all relative to the launcher binary).
RPATH_LIB = "@executable_path/../Resources/lib"
RPATH_FW = "@executable_path/../Frameworks"

# ── Small Mach-O helpers ─────────────────────────────────────────────────────

def run(*args):
    subprocess.run(args, check=True)


def macho_deps(path):
    """Dependency install names recorded in a Mach-O file (excludes the header)."""
    out = subprocess.run(["otool", "-L", path], capture_output=True, text=True).stdout
    return [line.strip().split(" (")[0].strip()
            for line in out.splitlines()[1:] if line.strip()]


def brew_deps(path):
    return [d for d in macho_deps(path)
            if d.startswith(BREW + "/") and d.endswith(".dylib")]


def dep_sources(path):
    """Real Homebrew source files a Mach-O depends on and that we should bundle.

    Covers absolute /opt/homebrew deps *and* @loader_path/@rpath ones: Homebrew's
    ICU libs (and others) reference their siblings relatively, so following only
    absolute paths would miss e.g. libicudata behind libicuuc."""
    base = os.path.dirname(os.path.realpath(path))
    brew_real = os.path.realpath(BREW)
    out = []
    for dep in macho_deps(path):
        if not dep.endswith(".dylib"):
            continue
        if dep.startswith(BREW + "/"):
            cand = dep
        elif dep.startswith("@loader_path/"):
            cand = os.path.join(base, dep[len("@loader_path/"):])
        elif dep.startswith("@rpath/"):
            name = dep[len("@rpath/"):]
            cand = os.path.join(base, name)
            if not os.path.exists(cand):
                cand = os.path.join(BREW, "lib", name)
        else:
            continue  # system libs (/usr/lib, /System) — never bundle
        if os.path.exists(cand) and os.path.realpath(cand).startswith(brew_real):
            out.append(cand)
    return out


def macho_rpaths(path):
    out = subprocess.run(["otool", "-l", path], capture_output=True, text=True).stdout
    lines = out.splitlines()
    rpaths = []
    for i, line in enumerate(lines):
        if "cmd LC_RPATH" in line:
            for j in range(i, min(i + 4, len(lines))):
                if "path " in lines[j]:
                    rpaths.append(lines[j].strip().split("path ", 1)[1].split(" (offset", 1)[0])
                    break
    return rpaths


def is_macho(path):
    if os.path.islink(path) or not os.path.isfile(path):
        return False
    try:
        with open(path, "rb") as fh:
            magic = fh.read(4)
    except OSError:
        return False
    return magic in (b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe",  # 64/32-bit LE
                     b"\xfe\xed\xfa\xcf", b"\xfe\xed\xfa\xce",  # 64/32-bit BE
                     b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca")  # fat


def all_macho(root):
    for dirpath, _, files in os.walk(root):
        for f in files:
            path = os.path.join(dirpath, f)
            if is_macho(path):
                yield path


def install_id(path):
    """LC_ID_DYLIB of a dylib, or None (loadable bundles have none)."""
    out = subprocess.run(["otool", "-D", path], capture_output=True, text=True).stdout.splitlines()
    return out[1].strip() if len(out) > 1 and out[1].strip() else None


def soname(path):
    """The basename a dylib is linked against — its install id (versioned), not
    the possibly-unversioned symlink name we may have reached it through."""
    return os.path.basename(install_id(path) or path)


def add_rpath(path, rpath):
    if rpath not in macho_rpaths(path):
        run("install_name_tool", "-add_rpath", rpath, path)


# ── Copy the native dependency closure (flat) into Resources/lib ─────────────

def typelib_seed_libs(libdest):
    """The shared libraries every bundled typelib names. gi dlopens these by
    bare name at runtime, so — unlike normal link deps — nothing in the bundle
    references them; they must be seeded explicitly (Gtk, Adw, Vte, …)."""
    seeds = set()
    for t in glob.glob(os.path.join(libdest, "girepository-1.0", "*.typelib")):
        out = subprocess.run(["strings", t], capture_output=True, text=True).stdout
        for line in out.splitlines():
            for tok in line.split(","):
                tok = tok.strip()
                cand = os.path.join(BREW, "lib", tok)
                if tok.endswith(".dylib") and os.path.exists(cand):
                    seeds.add(cand)
    return seeds


def copy_dep_closure(app, libdest):
    """Copy every Homebrew dylib reachable from (a) the typelibs' shared
    libraries and (b) the deps of every Mach-O already staged in the bundle,
    iterating to a fixpoint. Files are named by their install-id soname so the
    versioned names everything links against resolve."""
    present = set(os.listdir(libdest)) if os.path.isdir(libdest) else set()
    stack = list(typelib_seed_libs(libdest))
    for m in all_macho(app):
        stack += dep_sources(m)
    while stack:
        src = stack.pop()
        if not os.path.exists(src):
            continue
        name = soname(src)
        if name in present:
            continue
        shutil.copy(src, os.path.join(libdest, name))  # follows symlink → real file
        present.add(name)
        stack += dep_sources(src)


# ── Rewrite install names so no Mach-O references Homebrew ───────────────────

def relocate(path):
    os.chmod(path, os.stat(path).st_mode | 0o200)  # ensure writable
    idn = install_id(path)
    if idn and idn.startswith(BREW + "/"):
        run("install_name_tool", "-id", "@rpath/" + os.path.basename(path), path)
    for dep in macho_deps(path):
        if dep.startswith(BREW + "/") and dep.endswith((".dylib", ".so")):
            run("install_name_tool", "-change", dep, "@rpath/" + os.path.basename(dep), path)
        elif dep.endswith("/" + FRAMEWORK_PY_REL):
            run("install_name_tool", "-change", dep, "@rpath/" + FRAMEWORK_PY_REL, path)
    # Strip Homebrew's own LC_RPATHs (Python's extension modules and many dylibs
    # carry /opt/homebrew/lib). Left in place they precede ours, so @rpath deps
    # resolve to the Homebrew copy — the source of duplicate-load type clashes.
    for rp in macho_rpaths(path):
        if rp.startswith(BREW):
            run("install_name_tool", "-delete_rpath", rp, path)
    add_rpath(path, RPATH_LIB)
    add_rpath(path, RPATH_FW)


def relocate_all(app):
    for path in all_macho(app):
        relocate(path)


# ── Python framework ─────────────────────────────────────────────────────────

def copy_framework(frameworks):
    dest = os.path.join(frameworks, "Python.framework")
    shutil.copytree(FRAMEWORK_SRC, dest, symlinks=True)
    ver = os.path.join(dest, "Versions", PY_VER)
    stdlib = os.path.join(ver, "lib", "python%s" % PY_VER)
    for junk in ("test", "idlelib", "ensurepip", "tkinter", "turtledemo", "lib2to3"):
        shutil.rmtree(os.path.join(stdlib, junk), ignore_errors=True)
    for dirpath, dirnames, _ in os.walk(dest):
        for d in list(dirnames):
            if d == "__pycache__":
                shutil.rmtree(os.path.join(dirpath, d), ignore_errors=True)
                dirnames.remove(d)
    py = os.path.join(ver, "Python")
    os.chmod(py, os.stat(py).st_mode | 0o200)
    run("install_name_tool", "-id", "@rpath/" + FRAMEWORK_PY_REL, py)


# ── PyGObject + pycairo bindings ─────────────────────────────────────────────

def copy_bindings(libdest):
    sp = os.path.join(libdest, "python%s" % PY_VER, "site-packages")
    os.makedirs(sp, exist_ok=True)
    for pkg in ("gi", "cairo"):
        src = os.path.join(PURELIB, pkg)
        if os.path.isdir(src):
            # Homebrew symlinks these into site-packages from the Cellar; deref
            # (symlinks=False) so real files land in the bundle rather than links
            # that dangle once detached from Homebrew.
            shutil.copytree(src, os.path.join(sp, pkg), symlinks=False,
                            ignore=shutil.ignore_patterns("__pycache__"))


# ── typelibs, schemas, icons (pure data) ─────────────────────────────────────

def copy_data(res, libdest):
    shutil.copytree(os.path.join(BREW, "lib", "girepository-1.0"),
                    os.path.join(libdest, "girepository-1.0"), dirs_exist_ok=True)
    schemas = os.path.join(res, "share", "glib-2.0", "schemas")
    os.makedirs(schemas, exist_ok=True)
    shutil.copy(os.path.join(BREW, "share", "glib-2.0", "schemas", "gschemas.compiled"), schemas)
    icons = os.path.join(res, "share", "icons")
    os.makedirs(icons, exist_ok=True)
    for theme in ("Adwaita", "hicolor"):
        src = os.path.join(BREW, "share", "icons", theme)
        if os.path.exists(src):
            run("cp", "-RL", src, icons)  # deref Homebrew's cellar symlinks


# ── gettext message catalogs ─────────────────────────────────────────────────

# Domains whose translations reach the screen in a terminal: GTK's stock dialogs
# and menus, Adwaita's widgets, VTE, GLib/gdk-pixbuf error text. Homebrew drops
# every formula's catalogs into one share/locale tree, so the rest (git, wget,
# bash, the GTK3 stack…) would only pad the bundle. Extend this list rather than
# copying the tree wholesale.
LOCALE_DOMAINS = ("gtk40", "glib20", "libadwaita", "vte-2.91", "gdk-pixbuf")

# Languages shipped by default. Homebrew carries 123 of them at ~190KB apiece —
# 23MB of catalogs for a bundle that will only ever load one. This set keeps the
# widely-used ones (~4MB); anything omitted falls back to English, exactly as it
# did before any catalogs were bundled. Build with a different set via the
# environment, e.g. `ROBOTERM_LOCALES=all make bundle` or
# `ROBOTERM_LOCALES=de,fr,ja make bundle`.
LOCALE_LANGS = (
    "de", "en", "en_CA", "en_GB", "es", "fr", "it", "ja", "ko", "nl",
    "pl", "pt", "pt_BR", "ru", "sv", "tr", "zh_CN", "zh_TW",
)


def wanted_langs():
    """Language codes to bundle, or None for "every language Homebrew has"."""
    env = os.environ.get("ROBOTERM_LOCALES", "").strip()
    if not env:
        return set(LOCALE_LANGS)
    if env == "all":
        return None
    return {part.strip() for part in env.split(",") if part.strip()}


def copy_locales(res):
    """Copy the GTK stack's message catalogs into the bundle.

    Limited to LOCALE_DOMAINS x LOCALE_LANGS (see ROBOTERM_LOCALES to widen).

    These are inert on their own: every library hardcodes its own build-time
    Cellar path as its gettext lookup dir (e.g. gtk4 asks for
    /opt/homebrew/Cellar/gtk4/<ver>/share/locale), which does not exist on a Mac
    without Homebrew — so a relocated bundle silently falls back to untranslated
    English. roboterm/__init__.py rebinds each domain to the directory written
    here; the `domains` manifest is what it reads, so the two never drift.
    """
    src_root = os.path.join(BREW, "share", "locale")
    dest_root = os.path.join(res, "share", "locale")
    if not os.path.isdir(src_root):
        return
    langs = wanted_langs()
    found = set()
    for lang in sorted(os.listdir(src_root)):
        if langs is not None and lang not in langs:
            continue
        src_dir = os.path.join(src_root, lang, "LC_MESSAGES")
        if not os.path.isdir(src_dir):
            continue
        for domain in LOCALE_DOMAINS:
            src = os.path.join(src_dir, domain + ".mo")
            if not os.path.exists(src):
                continue
            dest_dir = os.path.join(dest_root, lang, "LC_MESSAGES")
            os.makedirs(dest_dir, exist_ok=True)
            shutil.copy(src, dest_dir)  # follows Homebrew's Cellar symlink
            found.add(domain)
    if not found:
        return
    os.makedirs(dest_root, exist_ok=True)
    with open(os.path.join(dest_root, "domains"), "w") as fh:
        fh.write("\n".join(sorted(found)) + "\n")


# ── gdk-pixbuf loaders + regenerated cache ───────────────────────────────────

def copy_pixbuf_loaders(libdest):
    rel = os.path.join("gdk-pixbuf-2.0", "2.10.0")
    src_dir = os.path.join(BREW, "lib", rel, "loaders")
    dest_dir = os.path.join(libdest, rel, "loaders")
    os.makedirs(dest_dir, exist_ok=True)
    loaders = sorted(f for f in os.listdir(src_dir) if f.endswith(".so"))
    for f in loaders:
        shutil.copy(os.path.join(src_dir, f), dest_dir)
    # Build the cache from the ORIGINAL loaders (valid signatures) — querying the
    # relocated copies would dlopen them, and install_name_tool has invalidated
    # their signatures, so macOS SIGKILLs the query. Rewrite the absolute loader
    # paths to the bare "loaders/NAME.so"; the launcher puts the loaders dir on
    # DYLD_LIBRARY_PATH so dyld resolves each leaf wherever the .app lives.
    # (gdk-pixbuf 2.44 no longer honours GDK_PIXBUF_MODULEDIR, and does not root a
    # relative cache entry at the cache dir — so leaf resolution is what works.)
    query = os.path.join(BREW, "bin", "gdk-pixbuf-query-loaders")
    out = subprocess.run([query] + [os.path.join(src_dir, f) for f in loaders],
                         capture_output=True, text=True, check=True).stdout
    out = out.replace(src_dir + "/", "loaders/")
    with open(os.path.join(libdest, rel, "loaders.cache"), "w") as fh:
        fh.write(out)


# ── final cleanup + codesign ─────────────────────────────────────────────────

def prune_broken_symlinks(app):
    """Homebrew leaves relative symlinks into the Cellar (e.g. the framework's
    site-packages link); once detached they dangle, which also fails codesign."""
    for dirpath, dirnames, files in os.walk(app):
        for name in list(dirnames) + files:
            path = os.path.join(dirpath, name)
            if os.path.islink(path) and not os.path.exists(path):
                os.unlink(path)
                if name in dirnames:
                    dirnames.remove(name)


def codesign(app):
    # Sign inside-out: every individual Mach-O first (fixes the signatures that
    # install_name_tool invalidated so dyld will load them), then re-seal each
    # framework as a bundle (regenerates its stale CodeResources), then the app.
    for path in all_macho(app):
        run("codesign", "--force", "--sign", "-", "--timestamp=none", path)
    for fw in glob.glob(os.path.join(app, "Contents", "Frameworks", "*.framework")):
        run("codesign", "--force", "--sign", "-", "--timestamp=none", fw)
    run("codesign", "--force", "--sign", "-", "--timestamp=none", app)


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: bundle_deps.py <App.app>")
    app = os.path.abspath(sys.argv[1])
    contents = os.path.join(app, "Contents")
    res = os.path.join(contents, "Resources")
    frameworks = os.path.join(contents, "Frameworks")
    libdest = os.path.join(res, "lib")
    os.makedirs(libdest, exist_ok=True)
    os.makedirs(frameworks, exist_ok=True)

    print("Bundling native deps from %s (Python %s) into %s" % (BREW, PY_VER, app))
    print("  [1/8] Python framework"); copy_framework(frameworks)
    print("  [2/8] PyGObject + pycairo"); copy_bindings(libdest)
    print("  [3/8] typelibs, schemas, icons"); copy_data(res, libdest)
    print("  [4/8] message catalogs"); copy_locales(res)
    print("  [5/8] gdk-pixbuf loaders"); copy_pixbuf_loaders(libdest)
    print("  [6/8] dependency closure"); copy_dep_closure(app, libdest)
    print("  [7/8] relocate install names"); relocate_all(app)
    print("  [8/8] prune symlinks + codesign")
    prune_broken_symlinks(app)
    codesign(app)
    print("Done. Self-contained bundle at %s" % app)


if __name__ == "__main__":
    main()
