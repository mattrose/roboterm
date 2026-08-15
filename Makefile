APP      = Roboterm.app
SRC_PKG  = roboterm
PY_FILES = $(shell find $(SRC_PKG) -name '*.py')

# Python interpreter used to build the bundle. Defaults to whatever `python3`
# is on PATH; override with e.g. `make PYTHON=/opt/homebrew/bin/python3.13`.
# Everything below is derived from this interpreter via sysconfig, so the
# bundle is built for (and embeds) the detected Python — no hardcoded version.
PYTHON     ?= python3

# PY_VERSION is "3.X"; it is empty if PYTHON is missing or older than 3, which
# the $(APP) recipe checks before building.
PY_VERSION := $(shell $(PYTHON) -c 'import sys; sys.exit(1) if sys.version_info[0] < 3 else print("%d.%d" % sys.version_info[:2])' 2>/dev/null)
PY_INC     := $(shell $(PYTHON) -c 'import sysconfig; print(sysconfig.get_path("include"))' 2>/dev/null)
PY_LIBDIR  := $(shell $(PYTHON) -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))' 2>/dev/null)
PY_LIB     := $(PY_LIBDIR)/libpython$(PY_VERSION).dylib

.PHONY: app bundle clean

app: clean $(APP)

# Self-contained bundle: build the app, then copy + relocate the entire native
# stack (Python framework, GTK4/VTE dylibs, typelibs, schemas, icons) into it so
# it runs on a Mac with no Homebrew. Uses the same $(PYTHON) the app was built
# against. See macos/bundle_deps.py.
#
# ROBOTERM_LOCALES picks which languages' message catalogs ship: a comma-
# separated list, or "all" for every one Homebrew has (adds ~19MB). Exported so
# it works as both `make bundle ROBOTERM_LOCALES=all` and as an env var.
export ROBOTERM_LOCALES

bundle: app
	$(PYTHON) macos/bundle_deps.py $(APP)

$(APP): roboterm.py $(PY_FILES) macos/launcher.c macos/Info.plist macos/create_icon.py
	@test -n "$(PY_VERSION)" || { \
		echo "Error: '$(PYTHON)' is not a Python 3+ interpreter."; \
		echo "Install Python 3 or pass one, e.g. make PYTHON=/opt/homebrew/bin/python3.13"; \
		exit 1; }
	@echo "Building with $(PYTHON) (Python $(PY_VERSION))"
	rm -rf $@
	mkdir -p $@/Contents/MacOS $@/Contents/Resources
	# Compile native launcher embedding libpython (so Dock shows us, not Python).
	# ROBOTERM_PY_VER tells the launcher which Python version to locate at runtime.
	cc -O2 -Wall -DROBOTERM_PY_VER='"$(PY_VERSION)"' -I$(PY_INC) macos/launcher.c $(PY_LIB) \
		-Wl,-rpath,/opt/homebrew/lib \
		-Wl,-rpath,/usr/local/lib \
		-o $@/Contents/MacOS/Roboterm
	# Build the .icns icon
	$(PYTHON) macos/create_icon.py $@/Contents/Resources
	cp macos/Info.plist            $@/Contents/
	cp roboterm.py                 $@/Contents/Resources/
	rsync -a --exclude='__pycache__' $(SRC_PKG) $@/Contents/Resources/
	@echo "Built $@"

clean:
	rm -rf $(APP)
