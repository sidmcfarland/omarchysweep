"""Read the live Omarchy palette so the board matches the rest of the desktop.

Resolution order, best source first:

1. ``omarchy-theme-color --all`` - the same resolver Omarchy uses for its own
   templates, so aliases and derived shades match exactly.
2. The current theme's ``colors.toml``, parsed directly.
3. A built-in palette, for machines without Omarchy.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

STATE_THEME = Path.home() / ".local/state/omarchy/current/theme"
COLORS_TOML = STATE_THEME / "colors.toml"
THEME_NAME = Path.home() / ".local/state/omarchy/current/theme.name"

FALLBACK = {
    "mode": "dark",
    "accent": "#89b4fa",
    "background": "#1e1e2e",
    "dark_background": "#161622",
    "darker_background": "#101019",
    "lighter_background": "#313244",
    "foreground": "#cdd6f4",
    "dark_foreground": "#6c7086",
    "light_foreground": "#bac2de",
    "bright_foreground": "#cdd6f4",
    "muted": "#585b70",
    "selection": "#45475a",
    "red": "#f38ba8",
    "orange": "#f6b6ab",
    "yellow": "#f9e2af",
    "green": "#a6e3a1",
    "cyan": "#94e2d5",
    "blue": "#89b4fa",
    "magenta": "#f5c2e7",
    "brown": "#7b5b55",
    "bright_red": "#f38ba8",
    "bright_green": "#a6e3a1",
    "bright_yellow": "#f9e2af",
}


def _hex(value: str) -> str | None:
    value = value.strip().strip("\"'")
    if len(value) == 7 and value.startswith("#"):
        try:
            int(value[1:], 16)
        except ValueError:
            return None
        return value.lower()
    return None


def _from_command() -> dict[str, str]:
    if not shutil.which("omarchy-theme-color"):
        return {}
    try:
        out = subprocess.run(
            ["omarchy-theme-color", "--all"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    if out.returncode != 0:
        return {}
    colors: dict[str, str] = {}
    for line in out.stdout.splitlines():
        key, _, value = line.partition("\t")
        key = key.strip()
        if key == "mode":
            colors["mode"] = value.strip() or "dark"
        elif (parsed := _hex(value)) is not None:
            colors[key] = parsed
    return colors


def _from_toml() -> dict[str, str]:
    try:
        text = COLORS_TOML.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    colors: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip().strip("\"'")
        quoted = re.match(r"""\s*["'](.*?)["']""", value)
        value = quoted.group(1) if quoted else value.split("#", 1)[0]
        if key in ("mode", "theme_type"):
            colors.setdefault("mode", value.strip() or "dark")
        elif (parsed := _hex(value)) is not None:
            colors[key] = parsed
    return colors


def _luminance(hex_color: str) -> float:
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255


def _distance(a: str, b: str) -> float:
    return sum(abs(int(a[i : i + 2], 16) - int(b[i : i + 2], 16)) for i in (1, 3, 5))


def _mix(a: str, b: str, amount: float) -> str:
    parts = []
    for i in (1, 3, 5):
        av, bv = int(a[i : i + 2], 16), int(b[i : i + 2], 16)
        parts.append(round(av * (1 - amount) + bv * amount))
    return "#%02x%02x%02x" % tuple(parts)


class Theme:
    """A resolved palette plus the handful of roles the game paints with."""

    def __init__(self, colors: dict[str, str] | None = None, name: str = "Omarchy"):
        merged = dict(FALLBACK)
        merged.update(colors or {})
        self.colors = merged
        self.name = name
        self.mode = merged.get("mode", "dark")
        self.dark = self.mode != "light"
        self._derive()

    def get(self, key: str, fallback: str = "foreground") -> str:
        return self.colors.get(key) or self.colors.get(fallback) or "#cdd6f4"

    def _derive(self) -> None:
        bg = self.get("background")
        fg = self.get("foreground")
        toward_fg = 0.14 if self.dark else 0.10

        self.bg = bg
        self.fg = fg
        self.accent = self.get("accent", "blue")
        self.muted = self.get("muted", "dark_foreground")
        self.frame = _mix(self.get("muted"), bg, 0.35)
        self.panel = self.get("lighter_background", "background")
        if abs(_luminance(self.panel) - _luminance(bg)) < 0.02:
            self.panel = _mix(bg, fg, toward_fg)
        # Hidden cells read as a raised tile; revealed ground sits flat on the
        # background so opened areas visibly recede.
        self.tile = self.panel
        self.tile_dim = _mix(self.panel, bg, 0.45)
        self.ground = bg
        # The cursor has to read against both a hidden tile and open ground,
        # so try the theme's own selection first and fall back to accent tints.
        candidates = [self.get("selection", "lighter_background")]
        candidates += [_mix(self.accent, bg, amount) for amount in (0.55, 0.7, 0.4)]
        candidates += [_mix(self.accent, fg, 0.25), self.accent]
        contrast = lambda colour: min(_distance(colour, self.tile), _distance(colour, bg))
        self.cursor_bg = next(
            (colour for colour in candidates if contrast(colour) >= 70),
            max(candidates, key=contrast),
        )
        self.cursor_fg = max(
            (self.get("bright_foreground", "foreground"), bg, fg),
            key=lambda colour: _distance(colour, self.cursor_bg),
        )
        self.flag = self.get("red", "accent")
        self.mine = self.get("bright_red", "red")
        self.win = self.get("green", "accent")
        self.lose = self.get("red", "accent")
        self.numbers = self._number_colors()

    def _number_colors(self) -> dict[int, str]:
        """The classic 1-8 ramp, kept legible on themes with a narrow palette.

        Several Omarchy themes alias colors (blue == magenta, say). Counts that
        would otherwise collide are nudged toward the foreground or background
        until they read apart on the board.
        """
        wanted = [
            self.get("blue", "accent"),
            self.get("green", "accent"),
            self.get("red", "accent"),
            self.get("magenta", "blue"),
            self.get("orange", "yellow"),
            self.get("cyan", "blue"),
            self.get("bright_foreground", "foreground"),
            self.get("muted", "dark_foreground"),
        ]
        light = self.get("bright_foreground", "foreground")
        dark = self.get("background")
        first, second = (light, dark) if self.dark else (dark, light)
        taken: list[str] = []
        numbers: dict[int, str] = {}
        for index, colour in enumerate(wanted, start=1):
            attempts = [colour]
            attempts += [_mix(colour, first, amount) for amount in (0.3, 0.5, 0.7)]
            attempts += [_mix(colour, second, amount) for amount in (0.3, 0.5)]
            for candidate in attempts:
                if all(_distance(candidate, used) > 40 for used in taken):
                    colour = candidate
                    break
            taken.append(colour)
            numbers[index] = colour
        return numbers

    # -- loading ---------------------------------------------------------

    @staticmethod
    def stamp() -> float:
        """Mtime of the active theme, used to hot-reload on `omarchy theme set`."""
        best = 0.0
        for path in (COLORS_TOML, THEME_NAME, STATE_THEME):
            try:
                best = max(best, os.lstat(path).st_mtime)
            except OSError:
                continue
        return best

    @classmethod
    def load(cls) -> "Theme":
        colors = _from_command() or _from_toml()
        try:
            name = THEME_NAME.read_text(encoding="utf-8").strip()
        except OSError:
            name = ""
        pretty = name.replace("-", " ").title() if name else "Omarchy"
        return cls(colors, pretty)
