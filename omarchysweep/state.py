"""Remembered settings and best times, kept in the XDG state directory."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .board import CUSTOM, PRESETS, Level, make_level


def state_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or (Path.home() / ".local/state")
    return Path(base) / "omarchysweep"


class State:
    def __init__(self, path: Path | None = None):
        self.path = path or (state_dir() / "state.json")
        self.level: Level = PRESETS[0]
        self.best: dict[str, float] = {}
        self.load()

    def load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        level = data.get("level") or {}
        try:
            self.level = make_level(
                str(level.get("name", CUSTOM)),
                int(level["width"]),
                int(level["height"]),
                int(level["mines"]),
            )
        except (KeyError, TypeError, ValueError):
            pass
        best = data.get("best")
        if isinstance(best, dict):
            self.best = {
                str(k): float(v)
                for k, v in best.items()
                if isinstance(v, (int, float)) and v > 0
            }

    def save(self) -> None:
        payload = {
            "level": {
                "name": self.level.name,
                "width": self.level.width,
                "height": self.level.height,
                "mines": self.level.mines,
            },
            "best": self.best,
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            pass

    # -- best times ------------------------------------------------------

    def best_for(self, level: Level) -> float | None:
        return self.best.get(level.geometry)

    def record(self, level: Level, seconds: float) -> bool:
        """Store a win. Returns True when it beats the previous best."""
        previous = self.best.get(level.geometry)
        if previous is not None and previous <= seconds:
            return False
        self.best[level.geometry] = round(seconds, 1)
        self.save()
        return True
