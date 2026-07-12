import json
import os
import sys

from gi.repository import Gdk, Vte, Pango

_MACOS = sys.platform == "darwin"


def _default_keybindings() -> dict:
    if _MACOS:
        return {
            "preferences": "<Meta>comma",
            "new-window":  "<Meta>n",
            "new-tab":     "<Meta>t",
            "close-pane":  "<Meta>w",
            "split-auto":  "<Meta>a",
            "split-right": "<Meta>d",
            "split-down":  "<Meta><Shift>d",
            "prev-tab":    "<Meta><Shift>bracketleft",
            "next-tab":    "<Meta><Shift>bracketright",
            "rotate-cw":   "<Meta><Alt>bracketright",
            "rotate-ccw":  "<Meta><Alt>bracketleft",
        }
    return {
        "preferences": "<Control>comma",
        "new-window":  "<Control><Shift>n",
        "new-tab":     "<Control><Shift>t",
        "close-pane":  "<Control><Shift>w",
        "split-auto":  "<Control><Shift>a",
        "split-right": "<Control><Shift>e",
        "split-down":  "<Control><Shift>o",
        "prev-tab":    "<Control>Page_Up",
        "next-tab":    "<Control>Page_Down",
        "rotate-cw":   "<Control><Shift>bracketright",
        "rotate-ccw":  "<Control><Shift>bracketleft",
    }


def _rgba_to_hex(rgba: Gdk.RGBA) -> str:
    return "#{:02x}{:02x}{:02x}".format(
        round(rgba.red * 255),
        round(rgba.green * 255),
        round(rgba.blue * 255),
    )


THEMES: dict = {
    "Gruvbox Dark": {
        "foreground": "#ebdbb2", "background": "#282828",
        "palette": [
            "#282828", "#cc241d", "#98971a", "#d79921",
            "#458588", "#b16286", "#689d6a", "#a89984",
            "#928374", "#fb4934", "#b8bb26", "#fabd2f",
            "#83a598", "#d3869b", "#8ec07c", "#ebdbb2",
        ],
    },
    "Gruvbox Light": {
        "foreground": "#3c3836", "background": "#fbf1c7",
        "palette": [
            "#fbf1c7", "#cc241d", "#98971a", "#d79921",
            "#458588", "#b16286", "#689d6a", "#7c6f64",
            "#928374", "#9d0006", "#79740e", "#b57614",
            "#076678", "#8f3f71", "#427b58", "#3c3836",
        ],
    },
    "Solarized Dark": {
        "foreground": "#839496", "background": "#002b36",
        "palette": [
            "#073642", "#dc322f", "#859900", "#b58900",
            "#268bd2", "#d33682", "#2aa198", "#eee8d5",
            "#002b36", "#cb4b16", "#586e75", "#657b83",
            "#839496", "#6c71c4", "#93a1a1", "#fdf6e3",
        ],
    },
    "Solarized Light": {
        "foreground": "#657b83", "background": "#fdf6e3",
        "palette": [
            "#eee8d5", "#dc322f", "#859900", "#b58900",
            "#268bd2", "#d33682", "#2aa198", "#073642",
            "#fdf6e3", "#cb4b16", "#93a1a1", "#839496",
            "#657b83", "#6c71c4", "#586e75", "#002b36",
        ],
    },
    "Dracula": {
        "foreground": "#f8f8f2", "background": "#282a36",
        "palette": [
            "#21222c", "#ff5555", "#50fa7b", "#f1fa8c",
            "#bd93f9", "#ff79c6", "#8be9fd", "#f8f8f2",
            "#6272a4", "#ff6e6e", "#69ff94", "#ffffa5",
            "#d6acff", "#ff92df", "#a4ffff", "#ffffff",
        ],
    },
    "Nord": {
        "foreground": "#d8dee9", "background": "#2e3440",
        "palette": [
            "#3b4252", "#bf616a", "#a3be8c", "#ebcb8b",
            "#81a1c1", "#b48ead", "#88c0d0", "#e5e9f0",
            "#4c566a", "#bf616a", "#a3be8c", "#ebcb8b",
            "#81a1c1", "#b48ead", "#8fbcbb", "#eceff4",
        ],
    },
    "One Dark": {
        "foreground": "#abb2bf", "background": "#282c34",
        "palette": [
            "#282c34", "#e06c75", "#98c379", "#e5c07b",
            "#61afef", "#c678dd", "#56b6c2", "#abb2bf",
            "#5c6370", "#e06c75", "#98c379", "#e5c07b",
            "#61afef", "#c678dd", "#56b6c2", "#ffffff",
        ],
    },
    "Monokai": {
        "foreground": "#f8f8f2", "background": "#272822",
        "palette": [
            "#272822", "#f92672", "#a6e22e", "#f4bf75",
            "#66d9e8", "#ae81ff", "#a1efe4", "#f8f8f2",
            "#75715e", "#f92672", "#a6e22e", "#f4bf75",
            "#66d9e8", "#ae81ff", "#a1efe4", "#f9f8f5",
        ],
    },
    "Tokyo Night": {
        "foreground": "#c0caf5", "background": "#1a1b26",
        "palette": [
            "#15161e", "#f7768e", "#9ece6a", "#e0af68",
            "#7aa2f7", "#bb9af7", "#7dcfff", "#a9b1d6",
            "#414868", "#f7768e", "#9ece6a", "#e0af68",
            "#7aa2f7", "#bb9af7", "#7dcfff", "#c0caf5",
        ],
    },
    "Catppuccin Mocha": {
        "foreground": "#cdd6f4", "background": "#1e1e2e",
        "palette": [
            "#45475a", "#f38ba8", "#a6e3a1", "#f9e2af",
            "#89b4fa", "#f5c2e7", "#94e2d5", "#bac2de",
            "#585b70", "#f38ba8", "#a6e3a1", "#f9e2af",
            "#89b4fa", "#f5c2e7", "#94e2d5", "#a6adc8",
        ],
    },
}


class Settings:
    CONFIG_PATH = os.path.expanduser("~/.config/roboterm/settings.json")

    DEFAULTS: dict = {
        "font":             "Monospace 12",
        "theme":            "Custom",
        "foreground":       "#ffffff",
        "background":       "#1e1e1e",
        "palette":          None,
        "cursor_shape":     "block",
        "cursor_blink":     "system",
        "scrollback_lines": 10_000,
        "bold_is_bright":   False,
        "pane_titlebar":    "auto",
        "keybindings":      {},
    }

    _instance: "Settings | None" = None

    @classmethod
    def get(cls) -> "Settings":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._data: dict = dict(self.DEFAULTS)
        self._listeners: list = []
        self._load()

    def _load(self) -> None:
        try:
            with open(self.CONFIG_PATH) as f:
                saved = json.load(f)
            for k, v in saved.items():
                if k in self.DEFAULTS:
                    self._data[k] = v
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.CONFIG_PATH), exist_ok=True)
        with open(self.CONFIG_PATH, "w") as f:
            json.dump(self._data, f, indent=2)

    def get_value(self, key: str):
        return self._data[key]

    def set_value(self, key: str, value) -> None:
        self._data[key] = value
        self.save()
        for cb in self._listeners:
            cb()

    def connect_changed(self, cb) -> None:
        self._listeners.append(cb)

    def get_keybindings(self) -> dict:
        """Return effective keybindings: platform defaults merged with user overrides."""
        result = _default_keybindings()
        result.update(self._data.get("keybindings", {}))
        return result

    def apply_theme(self, theme_name: str) -> None:
        self._data["theme"] = theme_name
        if theme_name in THEMES:
            t = THEMES[theme_name]
            self._data["foreground"] = t["foreground"]
            self._data["background"] = t["background"]
            self._data["palette"]    = t["palette"]
        else:
            self._data["palette"] = None
        self.save()
        for cb in self._listeners:
            cb()

    def apply_to_vte(self, vte: Vte.Terminal) -> None:
        vte.set_font(Pango.FontDescription.from_string(self._data["font"]))

        fg = Gdk.RGBA()
        fg.parse(self._data["foreground"])
        bg = Gdk.RGBA()
        bg.parse(self._data["background"])

        palette_data = self._data.get("palette")
        if palette_data and len(palette_data) == 16:
            palette = []
            for h in palette_data:
                c = Gdk.RGBA()
                c.parse(h)
                palette.append(c)
            vte.set_colors(fg, bg, palette)
        else:
            vte.set_color_foreground(fg)
            vte.set_color_background(bg)

        vte.set_cursor_shape({
            "block":     Vte.CursorShape.BLOCK,
            "ibeam":     Vte.CursorShape.IBEAM,
            "underline": Vte.CursorShape.UNDERLINE,
        }.get(self._data["cursor_shape"], Vte.CursorShape.BLOCK))

        vte.set_cursor_blink_mode({
            "system": Vte.CursorBlinkMode.SYSTEM,
            "on":     Vte.CursorBlinkMode.ON,
            "off":    Vte.CursorBlinkMode.OFF,
        }.get(self._data["cursor_blink"], Vte.CursorBlinkMode.SYSTEM))

        vte.set_scrollback_lines(self._data["scrollback_lines"])
        vte.set_bold_is_bright(self._data["bold_is_bright"])
