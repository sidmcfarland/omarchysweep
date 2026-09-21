"""Rendering and the input loop: an Omarchy-flavoured minesweeper board."""

from __future__ import annotations

import time

from . import board as rules
from .board import CUSTOM, FLAGGED, HIDDEN, LOST, PLAYING, PRESETS, READY, REVEALED, WON, Board, Level
from .state import State
from .term import Line, Paint, Screen
from .theme import Theme

CELL = 2  # columns per cell, keeps the grid close to square
CHROME_ROWS = 10  # frame, header, status, rules, message and two hint rows
CHROME_COLS = 6  # frame borders, padding, and a breathing column each side
MIN_INNER = 38

HIDDEN_GLYPH = "·"  # ·
FLAG_GLYPH = "⚑"  # ⚑
MINE_GLYPH = "✱"  # ✱
WRONG_GLYPH = "✖"  # ✖

TOP_LEFT, TOP_RIGHT = "╭", "╮"
BOTTOM_LEFT, BOTTOM_RIGHT = "╰", "╯"
HORIZONTAL, VERTICAL = "─", "│"
TEE_LEFT, TEE_RIGHT = "├", "┤"

BOARD, OPTIONS, HELP = "board", "options", "help"

FIELDS = ("difficulty", "width", "height", "mines")


def fit_width(cols: int) -> int:
    return max(rules.MIN_WIDTH, min(rules.MAX_WIDTH, (cols - CHROME_COLS) // CELL))


def fit_height(rows: int) -> int:
    return max(rules.MIN_HEIGHT, min(rules.MAX_HEIGHT, rows - CHROME_ROWS))


def fit(text: str, width: int) -> str:
    """Clip a label so it can never push past the frame."""
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    return text[: max(0, width - 1)] + "\u2026"


def clock(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{min(seconds // 60, 99):02d}:{seconds % 60:02d}"


class Game:
    """Owns the board, the cursor, the view stack and the redraw loop."""

    def __init__(self, level: Level | None = None, state: State | None = None):
        self.state = state or State()
        self.theme = Theme.load()
        self.paint = Paint()
        self.theme_stamp = Theme.stamp()
        self.level = level or self.state.level
        self.view = BOARD
        self.message = ""
        self.running = True
        self.cursor = (0, 0)
        self.started: float | None = None
        self.finished: float | None = None
        self.draft = {
            "difficulty": self.level.name,
            "width": self.level.width,
            "height": self.level.height,
            "mines": self.level.mines,
        }
        self.field = 0
        self.board = Board(self.level)
        self.new_game(self.level)

    # -- game lifecycle --------------------------------------------------

    def new_game(self, level: Level | None = None) -> None:
        self.level = level or self.level
        self.board = Board(self.level)
        self.cursor = (self.level.width // 2, self.level.height // 2)
        self.started = None
        self.finished = None
        self.message = ""
        self.state.level = self.level
        self.state.save()

    @property
    def elapsed(self) -> float:
        if self.started is None:
            return 0.0
        return (self.finished or time.monotonic()) - self.started

    def _after_move(self) -> None:
        if self.board.status == PLAYING and self.started is None:
            self.started = time.monotonic()
        if self.board.over and self.finished is None:
            self.finished = time.monotonic()
            if self.board.status == WON:
                seconds = self.elapsed
                if self.state.record(self.level, seconds):
                    self.message = f"Cleared in {seconds:.1f}s - new best"
                else:
                    self.message = f"Cleared in {seconds:.1f}s"
            else:
                self.message = "Boom. Press n for a new game"

    # -- input -----------------------------------------------------------

    def move(self, dx: int, dy: int) -> None:
        x, y = self.cursor
        self.cursor = (
            max(0, min(self.board.width - 1, x + dx)),
            max(0, min(self.board.height - 1, y + dy)),
        )

    def handle_board_key(self, key: str) -> None:
        x, y = self.cursor
        if key in ("up", "k"):
            self.move(0, -1)
        elif key in ("down", "j"):
            self.move(0, 1)
        elif key in ("left", "h"):
            self.move(-1, 0)
        elif key in ("right", "l"):
            self.move(1, 0)
        elif key == "home":
            self.cursor = (0, y)
        elif key == "end":
            self.cursor = (self.board.width - 1, y)
        elif key == "pageup":
            self.cursor = (x, 0)
        elif key == "pagedown":
            self.cursor = (x, self.board.height - 1)
        elif key == "f":
            self.board.toggle_flag(x, y)
        elif key in ("d", "enter"):
            if self.board.state_at(x, y) == REVEALED:
                self.board.chord(x, y)
            else:
                self.board.reveal(x, y)
            self._after_move()
        elif key == "c":
            self.board.chord(x, y)
            self._after_move()
        elif key == "n":
            self.new_game()
        elif key == "o":
            self.open_options()
        elif key == "?":
            self.view = HELP
        elif key in ("q", "ctrl-c"):
            self.running = False

    def open_options(self) -> None:
        self.draft = {
            "difficulty": self.level.name,
            "width": self.level.width,
            "height": self.level.height,
            "mines": self.level.mines,
        }
        self.field = 0
        self.view = OPTIONS

    def handle_options_key(self, key: str, cols: int, rows: int) -> None:
        if key in ("up", "k"):
            self.field = (self.field - 1) % len(FIELDS)
        elif key in ("down", "j", "tab"):
            self.field = (self.field + 1) % len(FIELDS)
        elif key in ("left", "h", "right", "l", "pageup", "pagedown"):
            step = 1 if key in ("right", "l") else -1
            if key == "pageup":
                step = 5
            elif key == "pagedown":
                step = -5
            self.adjust(step, cols, rows)
        elif key == "enter":
            self.new_game(self.draft_level(cols, rows))
            self.view = BOARD
        elif key in ("escape", "o", "q"):
            self.view = BOARD
        elif key == "ctrl-c":
            self.running = False

    def adjust(self, step: int, cols: int, rows: int) -> None:
        field = FIELDS[self.field]
        max_w, max_h = fit_width(cols), fit_height(rows)
        if field == "difficulty":
            names = [level.name for level in PRESETS] + [CUSTOM]
            index = names.index(self.draft["difficulty"]) if self.draft["difficulty"] in names else len(names) - 1
            name = names[(index + (1 if step > 0 else -1)) % len(names)]
            self.draft["difficulty"] = name
            chosen = rules.preset(name)
            if chosen:
                self.draft.update(width=chosen.width, height=chosen.height, mines=chosen.mines)
            return
        if field == "width":
            self.draft["width"] = rules.clamp(self.draft["width"] + step, rules.MIN_WIDTH, max_w)
        elif field == "height":
            self.draft["height"] = rules.clamp(self.draft["height"] + step, rules.MIN_HEIGHT, max_h)
        elif field == "mines":
            ceiling = rules.max_mines(self.draft["width"], self.draft["height"])
            self.draft["mines"] = rules.clamp(self.draft["mines"] + step, 1, ceiling)
            self.draft["difficulty"] = CUSTOM
            return
        # Geometry changed: keep the mine count legal and drop the preset label.
        self.draft["mines"] = rules.clamp(
            self.draft["mines"], 1, rules.max_mines(self.draft["width"], self.draft["height"])
        )
        self.draft["difficulty"] = CUSTOM

    def draft_level(self, cols: int, rows: int) -> Level:
        level = rules.make_level(
            self.draft["difficulty"], self.draft["width"], self.draft["height"], self.draft["mines"]
        )
        return rules.make_level(
            level.name,
            min(level.width, fit_width(cols)),
            min(level.height, fit_height(rows)),
            level.mines,
        )

    # -- rendering -------------------------------------------------------

    def cell_segments(self, x: int, y: int) -> tuple[str, str, str, bool]:
        """Glyph, foreground, background and weight for one cell."""
        theme = self.theme
        state = self.board.state_at(x, y)
        selected = self.cursor == (x, y)
        mine = self.board.is_mine(x, y)
        glyph, fg, bg, bold = HIDDEN_GLYPH, theme.muted, theme.tile, False

        if state == FLAGGED:
            if self.board.status == LOST and not mine:
                glyph, fg = WRONG_GLYPH, theme.muted
            else:
                glyph, fg, bold = FLAG_GLYPH, theme.flag, True
        elif state == REVEALED:
            bg = theme.ground
            if mine:
                glyph, fg, bold = MINE_GLYPH, theme.mine, True
                if self.board.exploded == (x, y):
                    bg, fg = theme.lose, theme.bg
            else:
                count = self.board.count_at(x, y)
                if count:
                    glyph, fg, bold = str(count), theme.numbers[count], True
                else:
                    glyph, fg = " ", theme.muted
        if selected:
            bg = theme.cursor_bg
            if state == HIDDEN:
                fg, bold = theme.cursor_fg, True
        return glyph, fg, bg, bold

    def board_lines(self, inner: int) -> list[Line]:
        lines = []
        pad = max(0, (inner - (self.board.width * CELL - 1)) // 2)
        for y in range(self.board.height):
            line = Line(self.paint, self.theme.bg)
            line.pad(pad)
            for x in range(self.board.width):
                glyph, fg, bg, bold = self.cell_segments(x, y)
                line.add(glyph, fg, bg, bold)
                line.add(" ", bg=bg)
            line.pad_to(inner)
            lines.append(line)
        return lines

    def status_line(self, inner: int) -> Line:
        theme, b = self.theme, self.board
        line = Line(self.paint, theme.bg)
        line.add(f"{FLAG_GLYPH} ", theme.flag)
        line.add(f"{b.remaining:>3}", theme.fg, bold=True)
        middle = clock(self.elapsed)
        label, colour = {
            READY: ("ready", theme.muted),
            PLAYING: ("playing", theme.accent),
            WON: ("cleared", theme.win),
            LOST: ("boom", theme.lose),
        }[b.status]
        right_width = len(label)
        centre = (inner - len(middle)) // 2
        line.pad_to(centre)
        line.add(middle, theme.fg, bold=b.status == PLAYING)
        line.pad_to(inner - right_width)
        line.add(label, colour, bold=b.over)
        return line

    def header_line(self, inner: int) -> Line:
        theme = self.theme
        line = Line(self.paint, theme.bg)
        line.add(self.level.name, theme.accent, bold=True)
        right = f"{self.level.width}x{self.level.height} · {self.level.mines} mines"
        best = self.state.best_for(self.level)
        if best:
            right = f"best {best:.1f}s · " + right
        line.pad_to(inner - len(right))
        line.add(right, theme.muted)
        return line

    def game_body(self, inner: int) -> list[Line]:
        theme = self.theme
        body = [self.header_line(inner), self.status_line(inner), self.rule(inner)]
        body += self.board_lines(inner)
        body.append(self.rule(inner))
        note = Line(self.paint, theme.bg)
        if self.message:
            colour = theme.win if self.board.status == WON else theme.lose
            note.add(self.message, colour, bold=True)
        note.pad_to(inner)
        body.append(note)
        body += self.hints(inner, [
            ("←↑↓→", "move"),
            ("f", "flag"),
            ("d", "dig"),
            ("n", "new"),
            ("o", "setup"),
            ("?", "help"),
            ("q", "quit"),
        ])
        return body

    def options_body(self, inner: int, cols: int, rows: int) -> list[Line]:
        theme = self.theme
        max_w, max_h = fit_width(cols), fit_height(rows)
        ceiling = rules.max_mines(self.draft["width"], self.draft["height"])
        density = self.draft["mines"] / (self.draft["width"] * self.draft["height"]) * 100
        rows_spec = [
            ("Difficulty", self.draft["difficulty"], "cycle presets, or custom"),
            ("Width", f"{self.draft['width']}", f"{rules.MIN_WIDTH}-{max_w} columns"),
            ("Height", f"{self.draft['height']}", f"{rules.MIN_HEIGHT}-{max_h} rows"),
            ("Mines", f"{self.draft['mines']}", f"1-{ceiling} · {density:.0f}% of the grid"),
        ]
        body = [self.centred("SETUP", inner, theme.accent, bold=True), self.blank(inner)]
        for index, (label, value, hint) in enumerate(rows_spec):
            selected = index == self.field
            line = Line(self.paint, theme.bg)
            line.add("  " + ("▸ " if selected else "  "), theme.accent if selected else theme.bg)
            line.add(f"{label:<11}", theme.fg if selected else theme.muted, bold=selected)
            line.add(f"{value:<14}", theme.accent if selected else theme.fg, bold=True)
            line.add(fit(hint, inner - line.width), theme.muted)
            line.pad_to(inner)
            body.append(line)
        body.append(self.blank(inner))
        body.append(self.rule(inner))
        body += self.hints(inner, [
            ("↑↓", "field"),
            ("←→", "adjust"),
            ("pgup/pgdn", "±5"),
            ("enter", "play"),
            ("esc", "back"),
        ])
        return body

    def help_body(self, inner: int) -> list[Line]:
        theme = self.theme
        entries = [
            ("← ↑ ↓ →  /  h j k l", "move the selection"),
            ("f", "toggle a flag on the selected box"),
            ("d  /  enter", "dig the selected box"),
            ("d on a number", "chord: dig its unflagged neighbours"),
            ("home / end", "jump to the first or last column"),
            ("pgup / pgdn", "jump to the top or bottom row"),
            ("n", "new game, same settings"),
            ("o", "grid size and difficulty"),
            ("q", "quit"),
        ]
        body = [self.centred("HOW TO PLAY", inner, theme.accent, bold=True), self.blank(inner)]
        for key, text in entries:
            line = Line(self.paint, theme.bg)
            line.add("  " + f"{key:<20}", theme.accent, bold=True)
            line.add(text, theme.fg)
            line.pad_to(inner)
            body.append(line)
        body.append(self.blank(inner))
        body.append(self.centred(
            "The first dig is always safe.", inner, theme.muted))
        body.append(self.centred(
            "Clear every box that is not a mine to win.", inner, theme.muted))
        body.append(self.centred(
            "Colours follow the current Omarchy theme, live.", inner, theme.muted))
        body.append(self.blank(inner))
        body += self.hints(inner, [("any key", "back to the board")])
        return body

    # -- line helpers ----------------------------------------------------

    def blank(self, inner: int) -> Line:
        return Line(self.paint, self.theme.bg).pad_to(inner)

    def rule(self, inner: int) -> Line:
        line = Line(self.paint, self.theme.bg).add(HORIZONTAL * (inner + 2), self.theme.frame)
        line.is_rule = True
        return line

    def centred(self, text: str, inner: int, colour: str, bold: bool = False) -> Line:
        line = Line(self.paint, self.theme.bg)
        text = fit(text, inner)
        line.pad(max(0, (inner - len(text)) // 2))
        line.add(text, colour, bold=bold)
        return line.pad_to(inner)

    def hints(self, inner: int, pairs: list[tuple[str, str]]) -> list[Line]:
        """Key hints, wrapped onto as many lines as the frame width needs."""
        theme = self.theme
        lines: list[Line] = []
        line = Line(self.paint, theme.bg)
        for key, text in pairs:
            chunk = len(key) + len(text) + 1
            if line.width and line.width + 2 + chunk > inner:
                lines.append(line.pad_to(inner))
                line = Line(self.paint, theme.bg)
            if line.width:
                line.add("  ", theme.muted)
            line.add(fit(key, inner - line.width), theme.accent)
            line.add(fit(" " + text, inner - line.width), theme.muted)
        lines.append(line.pad_to(inner))
        return lines

    def frame(self, title: str, body: list[Line], inner: int) -> list[str]:
        theme, paint = self.theme, self.paint
        span = inner + 2
        top = Line(paint, theme.bg)
        top.add(TOP_LEFT + HORIZONTAL, theme.frame)
        if title and len(title) + 6 <= span:
            top.add(" " + title + " ", theme.accent, bold=True)
        top.add(HORIZONTAL * max(0, span + 1 - top.width), theme.frame)
        top.add(TOP_RIGHT, theme.frame)
        lines = [top.render()]
        for row in body:
            wrapped = Line(paint, theme.bg)
            if row.is_rule:
                wrapped.add(TEE_LEFT, theme.frame)
                wrapped.parts.extend(row.parts)
                wrapped.width += row.width
                wrapped.pad_to(span + 1, theme.frame)
                wrapped.add(TEE_RIGHT, theme.frame)
            else:
                wrapped.add(VERTICAL, theme.frame)
                wrapped.add(" ")
                wrapped.parts.extend(row.parts)
                wrapped.width += row.width
                wrapped.pad_to(span + 1)
                wrapped.add(VERTICAL, theme.frame)
            lines.append(wrapped.render())
        bottom = Line(paint, theme.bg)
        bottom.add(BOTTOM_LEFT + HORIZONTAL * span + BOTTOM_RIGHT, theme.frame)
        lines.append(bottom.render())
        return lines

    def too_small(self, cols: int, rows: int) -> list[str]:
        theme = self.theme
        need_cols = self.board.width * CELL + CHROME_COLS
        need_rows = self.board.height + CHROME_ROWS
        inner = max(20, min(cols - 4, 40))
        body = [
            self.centred("Terminal too small", inner, theme.lose, bold=True),
            self.blank(inner),
            self.centred(f"need {need_cols}x{need_rows}, have {cols}x{rows}", inner, theme.fg),
            self.centred("resize, or press o for a", inner, theme.muted),
            self.centred("smaller grid", inner, theme.muted),
        ]
        return self.frame("OmarchySweep", body, inner)

    def compose(self, cols: int, rows: int) -> list[str]:
        theme = self.theme
        if self.view == OPTIONS:
            inner = max(MIN_INNER, min(cols - 4, 58))
            block = self.frame("OmarchySweep", self.options_body(inner, cols, rows), inner)
        elif self.view == HELP:
            inner = max(MIN_INNER, min(cols - 4, 58))
            block = self.frame("OmarchySweep", self.help_body(inner), inner)
        elif (self.board.width * CELL + CHROME_COLS > cols) or (self.board.height + CHROME_ROWS > rows):
            block = self.too_small(cols, rows)
        else:
            inner = max(MIN_INNER, self.board.width * CELL + 2)
            inner = min(inner, cols - 2)
            title = f"OmarchySweep · {self.theme.name}"
            if len(title) + 6 > inner:
                title = "OmarchySweep"
            block = self.frame(title, self.game_body(inner), inner)

        fill = self.paint.bg(theme.bg)
        top_pad = max(0, (rows - len(block)) // 2)
        out = []
        for _ in range(top_pad):
            out.append(fill + " " * cols + "\x1b[0m")
        for line in block:
            width = _visible_width(line)
            indent = max(0, (cols - width) // 2)
            out.append(fill + " " * indent + line + fill + " " * max(0, cols - width - indent) + "\x1b[0m")
        while len(out) < rows:
            out.append(fill + " " * cols + "\x1b[0m")
        return out[:rows]

    # -- loop ------------------------------------------------------------

    def refresh_theme(self) -> None:
        stamp = Theme.stamp()
        if stamp != self.theme_stamp:
            self.theme_stamp = stamp
            self.theme = Theme.load()

    def run(self, screen: Screen) -> None:
        last_check = time.monotonic()
        while self.running:
            cols, rows = screen.size()
            screen.draw(self.compose(cols, rows))
            key = screen.key(timeout=0.25)
            now = time.monotonic()
            if now - last_check > 2:
                last_check = now
                self.refresh_theme()
            if not key:
                continue
            if self.view == HELP:
                self.view = BOARD
                if key == "ctrl-c":
                    self.running = False
            elif self.view == OPTIONS:
                self.handle_options_key(key, cols, rows)
            else:
                self.handle_board_key(key)
        self.state.save()


def _visible_width(line: str) -> int:
    width, index, length = 0, 0, len(line)
    while index < length:
        char = line[index]
        if char == "\x1b":
            end = index + 1
            while end < length and not line[end].isalpha():
                end += 1
            index = end + 1
            continue
        width += 1
        index += 1
    return width
