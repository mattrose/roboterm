#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <mach-o/dyld.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/*
 * Python version this bundle was built against, e.g. "3.13". Normally supplied
 * by the Makefile (-DROBOTERM_PY_VER=...) from the interpreter it detected;
 * the fallback only matters if launcher.c is compiled by hand.
 */
#ifndef ROBOTERM_PY_VER
#define ROBOTERM_PY_VER "3.13"
#endif

/* Prepend value to an existing colon-separated env var, or set it. */
static void prepend_env(const char *key, const char *value) {
    const char *cur = getenv(key);
    if (cur && cur[0]) {
        char *buf = NULL;
        if (asprintf(&buf, "%s:%s", value, cur) >= 0) {
            setenv(key, buf, 1);
            free(buf);
        }
    } else {
        setenv(key, value, 1);
    }
}

int main(int argc, char *argv[]) {
    /* ── Locate Contents/Resources/roboterm.py relative to our binary ── */
    char exe[4096];
    uint32_t size = sizeof(exe);
    if (_NSGetExecutablePath(exe, &size) != 0) {
        fprintf(stderr, "Roboterm: cannot determine executable path\n");
        return 1;
    }
    char *p = strrchr(exe, '/'); if (p) *p = '\0'; /* drop binary name */
    p = strrchr(exe, '/');       if (p) *p = '\0'; /* drop MacOS/      */
    /* exe → .../Roboterm.app/Contents */

    char script[4096], resources[4096];
    snprintf(resources, sizeof(resources), "%s/Resources", exe);
    snprintf(script,    sizeof(script),    "%s/roboterm.py", resources);

    /*
     * ── Self-contained vs. Homebrew mode ──
     * `make bundle` copies the whole native stack into the .app and leaves a
     * Python.framework under Contents/Frameworks. When that exists we root every
     * path inside the bundle so it runs with no Homebrew present; otherwise we
     * fall back to the Homebrew prefix (the `make app` dev build).
     */
    char frameworks[4096];
    snprintf(frameworks, sizeof(frameworks),
             "%s/Frameworks/Python.framework/Versions/" ROBOTERM_PY_VER, exe);
    int bundled = (access(frameworks, F_OK) == 0);

    const char *brew = (access("/opt/homebrew/bin/python" ROBOTERM_PY_VER, F_OK) == 0)
                       ? "/opt/homebrew" : "/usr/local";
    /* Root for data (share/) and native libs (lib/): the bundle or Homebrew. */
    const char *base = bundled ? resources : brew;

    /* ── GTK4 environment (safe to inherit — GTK needs them at runtime) ── */
    char buf[2048];
    snprintf(buf, sizeof(buf), "%s/share:/usr/share", base);
    prepend_env("XDG_DATA_DIRS", buf);

    snprintf(buf, sizeof(buf), "%s/share/glib-2.0/schemas", base);
    setenv("GSETTINGS_SCHEMA_DIR", buf, 1);

    snprintf(buf, sizeof(buf), "%s/lib/gdk-pixbuf-2.0/2.10.0/loaders.cache", base);
    setenv("GDK_PIXBUF_MODULE_FILE", buf, 0);

    /* GObject-introspection typelibs (dlopen their dylibs by bare name). */
    snprintf(buf, sizeof(buf), "%s/lib/girepository-1.0", base);
    setenv("GI_TYPELIB_PATH", buf, 1);

    if (bundled) {
        /* Regenerated loaders.cache stores paths relative to this dir. */
        snprintf(buf, sizeof(buf), "%s/lib/gdk-pixbuf-2.0/2.10.0", base);
        setenv("GDK_PIXBUF_MODULEDIR", buf, 1);
    }

    /* GTK4 dylibs — gi typelibs dlopen these by bare name */
    snprintf(buf, sizeof(buf), "%s/lib", base);
    prepend_env("DYLD_LIBRARY_PATH", buf);

    /* ── Embed Python and run the script ── */
    PyConfig config;
    PyConfig_InitPythonConfig(&config);
    config.isolated = 0;
    config.use_environment = 1;

    /*
     * Set PYTHONHOME and PYTHONPATH via PyConfig rather than setenv() so
     * these variables are never placed in the process environment and cannot
     * leak into shells spawned by VTE.
     */
    if (bundled) {
        snprintf(buf, sizeof(buf), "%s", frameworks);
    } else {
        snprintf(buf, sizeof(buf),
            "%s/opt/python@" ROBOTERM_PY_VER
            "/Frameworks/Python.framework/Versions/" ROBOTERM_PY_VER, brew);
    }
    wchar_t *whome = Py_DecodeLocale(buf, NULL);
    PyConfig_SetString(&config, &config.home, whome);
    PyMem_RawFree(whome);

    char pypath[4096];
    snprintf(pypath, sizeof(pypath),
        "%s:%s/lib/python" ROBOTERM_PY_VER "/site-packages", resources, base);
    wchar_t *wpypath = Py_DecodeLocale(pypath, NULL);
    PyConfig_SetString(&config, &config.pythonpath_env, wpypath);
    PyMem_RawFree(wpypath);

    /* Run as: python roboterm.py */
    wchar_t *wscript = Py_DecodeLocale(script, NULL);
    PyConfig_SetString(&config, &config.run_filename, wscript);
    PyMem_RawFree(wscript);

    PyConfig_SetBytesArgv(&config, argc, argv);

    PyStatus status = Py_InitializeFromConfig(&config);
    if (PyStatus_Exception(status)) {
        Py_ExitStatusException(status);
    }
    PyConfig_Clear(&config);

    return Py_RunMain();
}
