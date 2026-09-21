"""Raw-terminal plumbing: alternate screen, key decoding, truecolor painting.

The game paints with 24-bit SGR sequences so it can use the exact hex values
from the Omarchy theme; on terminals that only claim 256 colors the same hex
is snapped to the nearest xterm cube entry.
"""

from __future__ import annotations

import os
import select
import sys
import termios
import tty

ESC = "\x1b"
ALT_SCREEN_ON = "\x1b[?1049h"
ALT_SCREEN_OFF = "\x1b[?1049l"
CURSOR_HIDE = "\x1b[?25l"
CURSOR_SHOW = "\x1b[?25h"
HOME = "\x1b[H"
CLEAR_BELOW = "\x1b[J"
CLEAR_LINE = "\x1b[K"
RESET = "\x1b[0m"

KEYS = {
    "\x1b[A": "up",
    "\x1b[B": "down",
    "\x1b[C": "right",
    "\x1b[D": "left",
    "\x1bOA": "up",
    "\x1bOB": "down",
    "\x1bOC": "right",
    "\x1bOD": "left",
    "\x1b[H": "home",
    "\x1b[F": "end",
    "\x1b[1~": "home",
    "\x1b[4~": "end",
    "\x1b[5~": "pageup",
    "\x1b[6~": "pagedown",
    "\r": "enter",
    "\n": "enter",
    " ": "space",
    "\t": "tab",
    "\x7f": "backspace",
    "\x1b": "escape",
    "\x03": "ctrl-c",
}


def truecolor_supported() -> bool:
    if os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit"):
        return True
    term = os.environ.get("TERM", "")
    return "direct" in term or "truecolor" in term


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _cube(value: int) -> int:
    steps = (0, 95, 135, 175, 215, 255)
    return min(range(6), key=lambda i: abs(steps[i] - value))


def _xterm256(hex_color: str) -> int:
    r, g, b = _rgb(hex_color)
    if r == g == b:
        if r < 8:
            return 16
        if r > 248:
            return 231
        return 232 + round((r - 8) / 247 * 23)
    return 16 + 36 * _cube(r) + 6 * _cube(g) + _cube(b)


class Paint:
    """Turns hex colors into SGR sequences, with a small memo cache."""

    def __init__(self, truecolor: bool | None = None):
        self.truecolor = truecolor_supported() if truecolor is None else truecolor
        self._fg: dict[str, str] = {}
        self._bg: dict[str, str] = {}

    def fg(self, hex_color: str) -> str:
        if hex_color not in self._fg:
            if self.truecolor:
                self._fg[hex_color] = "\x1b[38;2;%d;%d;%dm" % _rgb(hex_color)
            else:
                self._fg[hex_color] = "\x1b[38;5;%dm" % _xterm256(hex_color)
        return self._fg[hex_color]

    def bg(self, hex_color: str) -> str:
        if hex_color not in self._bg:
            if self.truecolor:
                self._bg[hex_color] = "\x1b[48;2;%d;%d;%dm" % _rgb(hex_color)
            else:
                self._bg[hex_color] = "\x1b[48;5;%dm" % _xterm256(hex_color)
        return self._bg[hex_color]


class Line:
    """A row of styled text that keeps track of its own visible width."""

    def __init__(self, paint: Paint, bg: str | None = None):
        self.paint = paint
        self.default_bg = bg
        self.parts: list[str] = []
        self.width = 0
        self.is_rule = False

    def add(self, text: str, fg: str | None = None, bg: str | None = None, bold: bool = False) -> "Line":
        if not text:
            return self
        style = ""
        if bold:
            style += "\x1b[1m"
        if fg:
            style += self.paint.fg(fg)
        background = bg or self.default_bg
        if background:
            style += self.paint.bg(background)
        self.parts.append(style + text + RESET)
        self.width += len(text)
        return self

    def pad(self, count: int, bg: str | None = None) -> "Line":
        if count > 0:
            self.add(" " * count, bg=bg)
        return self

    def pad_to(self, target: int, bg: str | None = None) -> "Line":
        return self.pad(target - self.width, bg=bg)

    def render(self) -> str:
        return "".join(self.parts)


class Screen:
    """Alternate-screen session in cbreak mode, restored on the way out."""

    def __init__(self, stream=None):
        self.stream = stream or sys.stdout
        self.fd = sys.stdin.fileno()
        self._saved = None

    def __enter__(self) -> "Screen":
        try:
            self._saved = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        except termios.error:
            self._saved = None
        self.write(ALT_SCREEN_ON + CURSOR_HIDE)
        return self

    def __exit__(self, *_exc) -> None:
        self.write(RESET + CLEAR_BELOW + ALT_SCREEN_OFF + CURSOR_SHOW)
        if self._saved is not None:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self._saved)

    def write(self, text: str) -> None:
        try:
            self.stream.write(text)
            self.stream.flush()
        except (BrokenPipeError, ValueError):
            pass

    def size(self) -> tuple[int, int]:
        try:
            size = os.get_terminal_size(self.stream.fileno())
            return size.columns, size.lines
        except OSError:
            return 80, 24

    def draw(self, lines: list[str]) -> None:
        body = (CLEAR_LINE + "\r\n").join(lines)
        self.write(HOME + body + CLEAR_LINE + CLEAR_BELOW)

    # -- input -----------------------------------------------------------

    def _read(self, timeout: float | None) -> str:
        ready, _, _ = select.select([self.fd], [], [], timeout)
        if not ready:
            return ""
        try:
            return os.read(self.fd, 1).decode("utf-8", "replace")
        except OSError:
            return ""

    def key(self, timeout: float | None = None) -> str:
        """Block up to `timeout` seconds for one key, returned as a name."""
        char = self._read(timeout)
        if not char:
            return ""
        if char != ESC:
            return KEYS.get(char, char)
        sequence = ESC
        while True:
            nxt = self._read(0.02)
            if not nxt:
                break
            sequence += nxt
            if nxt.isalpha() or nxt == "~":
                break
            if len(sequence) > 8:
                break
        return KEYS.get(sequence, "escape" if sequence == ESC else sequence)
