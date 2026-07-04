#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <mach-o/dyld.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

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

    /* ── Detect Homebrew prefix ── */
    const char *brew = (access("/opt/homebrew/bin/python3.13", F_OK) == 0)
                       ? "/opt/homebrew" : "/usr/local";

    /* ── GTK4 environment ── */
    char buf[2048];
    snprintf(buf, sizeof(buf), "%s/share:/usr/share", brew);
    prepend_env("XDG_DATA_DIRS", buf);

    snprintf(buf, sizeof(buf), "%s/share/glib-2.0/schemas", brew);
    setenv("GSETTINGS_SCHEMA_DIR", buf, 1);

    snprintf(buf, sizeof(buf), "%s/lib/gdk-pixbuf-2.0/2.10.0/loaders.cache", brew);
    setenv("GDK_PIXBUF_MODULE_FILE", buf, 0);

    /* GTK4 dylibs - gi typelibs dlopen these by bare name */
    snprintf(buf, sizeof(buf), "%s/lib", brew);
    prepend_env("DYLD_LIBRARY_PATH", buf);

    /* ── Python stdlib ── */
    snprintf(buf, sizeof(buf),
        "%s/opt/python@3.13/Frameworks/Python.framework/Versions/3.13", brew);
    setenv("PYTHONHOME", buf, 0);

    /* Ensure our Resources/ and the Homebrew site-packages are on sys.path */
    snprintf(buf, sizeof(buf),
        "%s:%s/lib/python3.13/site-packages", resources, brew);
    prepend_env("PYTHONPATH", buf);

    /* ── Embed Python and run the script ── */
    PyConfig config;
    PyConfig_InitPythonConfig(&config);
    config.isolated = 0;
    config.use_environment = 1;

    /* Run as: python roboterm.py */
    wchar_t *wscript = Py_DecodeLocale(script, NULL);
    PyConfig_SetString(&config, &config.run_filename, wscript);
    PyMem_RawFree(wscript);

    /* argv[0] = script path so sys.argv[0] is right */
    wchar_t *wargv0 = Py_DecodeLocale(script, NULL);
    PyConfig_SetBytesArgv(&config, argc, argv);
    PyMem_RawFree(wargv0);

    PyStatus status = Py_InitializeFromConfig(&config);
    if (PyStatus_Exception(status)) {
        Py_ExitStatusException(status);
    }
    PyConfig_Clear(&config);

    return Py_RunMain();
}
