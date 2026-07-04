APP      = Roboterm.app
SRC_PKG  = roboterm
PY_FILES = $(shell find $(SRC_PKG) -name '*.py')
PYTHON   = /opt/homebrew/bin/python3.13

.PHONY: app clean

PY_PREFIX = $(shell /opt/homebrew/bin/python3.13-config --prefix)
PY_INC    = $(PY_PREFIX)/include/python3.13
PY_LIB    = $(PY_PREFIX)/lib/libpython3.13.dylib

app: $(APP)

$(APP): roboterm.py $(PY_FILES) macos/launcher.c macos/Info.plist macos/create_icon.py
	rm -rf $@
	mkdir -p $@/Contents/MacOS $@/Contents/Resources
	# Compile native launcher embedding libpython (so Dock shows us, not Python)
	cc -O2 -Wall -I$(PY_INC) macos/launcher.c $(PY_LIB) \
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
