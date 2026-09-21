"""Minesweeper rules: the grid, mine placement, revealing, flagging, win/lose."""

from __future__ import annotations

import random
from dataclasses import dataclass

HIDDEN = 0
REVEALED = 1
FLAGGED = 2

READY = "ready"
PLAYING = "playing"
WON = "won"
LOST = "lost"

MINE = -1

MIN_WIDTH, MAX_WIDTH = 5, 40
MIN_HEIGHT, MAX_HEIGHT = 5, 24


@dataclass(frozen=True)
class Level:
    """A board geometry plus the number of mines hidden in it."""

    name: str
    width: int
    height: int
    mines: int

    @property
    def geometry(self) -> str:
        return f"{self.width}x{self.height}/{self.mines}"

    @property
    def density(self) -> float:
        return self.mines / (self.width * self.height)


PRESETS = (
    Level("Beginner", 9, 9, 10),
    Level("Intermediate", 16, 16, 40),
    Level("Expert", 30, 16, 99),
)

CUSTOM = "Custom"


def preset(name: str) -> Level | None:
    for level in PRESETS:
        if level.name.lower() == name.lower():
            return level
    return None


def max_mines(width: int, height: int) -> int:
    """Leave room for the safe 3x3 opening around the first dig."""
    return max(1, width * height - 9)


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def make_level(name: str, width: int, height: int, mines: int) -> Level:
    width = clamp(width, MIN_WIDTH, MAX_WIDTH)
    height = clamp(height, MIN_HEIGHT, MAX_HEIGHT)
    mines = clamp(mines, 1, max_mines(width, height))
    return Level(name, width, height, mines)


class Board:
    """One game of minesweeper.

    Mines are placed after the first dig, so the opening move is always safe
    and always opens a pocket.
    """

    def __init__(self, level: Level, rng: random.Random | None = None):
        self.level = level
        self.width = level.width
        self.height = level.height
        self.mines = level.mines
        self.status = READY
        self.flags = 0
        self.revealed = 0
        self.exploded: tuple[int, int] | None = None
        self._counts = [[0] * self.width for _ in range(self.height)]
        self._state = [[HIDDEN] * self.width for _ in range(self.height)]
        self._rng = rng or random.Random()

    # -- queries ---------------------------------------------------------

    @property
    def cells(self) -> int:
        return self.width * self.height

    @property
    def remaining(self) -> int:
        """Mines minus flags, the classic (possibly negative) counter."""
        return self.mines - self.flags

    @property
    def over(self) -> bool:
        return self.status in (WON, LOST)

    def state_at(self, x: int, y: int) -> int:
        return self._state[y][x]

    def count_at(self, x: int, y: int) -> int:
        return self._counts[y][x]

    def is_mine(self, x: int, y: int) -> bool:
        return self._counts[y][x] == MINE

    def neighbours(self, x: int, y: int):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    yield nx, ny

    # -- moves -----------------------------------------------------------

    def toggle_flag(self, x: int, y: int) -> bool:
        """Flag or unflag a hidden cell. Returns True if anything changed."""
        if self.over:
            return False
        state = self._state[y][x]
        if state == REVEALED:
            return False
        if state == FLAGGED:
            self._state[y][x] = HIDDEN
            self.flags -= 1
        else:
            self._state[y][x] = FLAGGED
            self.flags += 1
        return True

    def reveal(self, x: int, y: int) -> bool:
        """Dig a cell. Flagged cells are protected, as in the original."""
        if self.over or self._state[y][x] != HIDDEN:
            return False
        if self.status == READY:
            self._place_mines(x, y)
            self.status = PLAYING
        if self._counts[y][x] == MINE:
            self._state[y][x] = REVEALED
            self.exploded = (x, y)
            self._lose()
            return True
        self._flood(x, y)
        self._check_win()
        return True

    def chord(self, x: int, y: int) -> bool:
        """On a satisfied number, dig every unflagged neighbour at once."""
        if self.over or self._state[y][x] != REVEALED:
            return False
        count = self._counts[y][x]
        if count <= 0:
            return False
        flagged = sum(1 for nx, ny in self.neighbours(x, y) if self._state[ny][nx] == FLAGGED)
        if flagged != count:
            return False
        changed = False
        for nx, ny in list(self.neighbours(x, y)):
            if self._state[ny][nx] == HIDDEN:
                changed |= self.reveal(nx, ny)
            if self.over:
                break
        return changed

    # -- internals -------------------------------------------------------

    def _place_mines(self, safe_x: int, safe_y: int) -> None:
        safe = {(safe_x, safe_y)}
        safe.update(self.neighbours(safe_x, safe_y))
        spots = [
            (x, y)
            for y in range(self.height)
            for x in range(self.width)
            if (x, y) not in safe
        ]
        # A dense board may not leave a full safe 3x3; shrink the pocket
        # rather than refuse to deal.
        while len(spots) < self.mines:
            spots.append(safe.pop())
        for x, y in self._rng.sample(spots, self.mines):
            self._counts[y][x] = MINE
        for y in range(self.height):
            for x in range(self.width):
                if self._counts[y][x] == MINE:
                    continue
                self._counts[y][x] = sum(
                    1 for nx, ny in self.neighbours(x, y) if self._counts[ny][nx] == MINE
                )

    def _flood(self, x: int, y: int) -> None:
        stack = [(x, y)]
        while stack:
            cx, cy = stack.pop()
            if self._state[cy][cx] != HIDDEN:
                continue
            self._state[cy][cx] = REVEALED
            self.revealed += 1
            if self._counts[cy][cx] == 0:
                stack.extend(self.neighbours(cx, cy))

    def _check_win(self) -> None:
        if self.revealed == self.cells - self.mines:
            self.status = WON
            for y in range(self.height):
                for x in range(self.width):
                    if self._counts[y][x] == MINE and self._state[y][x] != FLAGGED:
                        self._state[y][x] = FLAGGED
                        self.flags += 1

    def _lose(self) -> None:
        self.status = LOST
        for y in range(self.height):
            for x in range(self.width):
                if self._counts[y][x] == MINE and self._state[y][x] == HIDDEN:
                    self._state[y][x] = REVEALED
