"""Command line entry point."""

from __future__ import annotations

import argparse
import sys

from . import __version__, board as rules
from .state import State
from .term import Paint, Screen
from .theme import Theme
from .ui import Game, OPTIONS, fit_height, fit_width


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="omarchysweep",
        description="Classic minesweeper for the terminal, themed by Omarchy.",
        epilog="Arrows move, f flags, d digs. Press o in game to change the grid.",
    )
    parser.add_argument(
        "-d",
        "--difficulty",
        metavar="NAME",
        help="beginner, intermediate, expert or custom (default: last played)",
    )
    parser.add_argument("-W", "--width", type=int, metavar="N", help="grid width in boxes")
    parser.add_argument("-H", "--height", type=int, metavar="N", help="grid height in boxes")
    parser.add_argument("-m", "--mines", type=int, metavar="N", help="number of mines")
    parser.add_argument(
        "--density",
        type=float,
        metavar="PCT",
        help="mines as a percentage of the grid, instead of --mines",
    )
    parser.add_argument("-s", "--setup", action="store_true", help="open the setup screen first")
    parser.add_argument(
        "--colors",
        choices=("auto", "truecolor", "256"),
        default="auto",
        help="colour depth to paint with (default: auto)",
    )
    parser.add_argument("--theme-info", action="store_true", help="print the resolved palette and exit")
    parser.add_argument("--version", action="version", version=f"omarchysweep {__version__}")
    return parser.parse_args(argv)


def resolve_level(args: argparse.Namespace, state: State) -> rules.Level:
    """CLI flags on top of the preset, on top of whatever was played last."""
    base = state.level
    if args.difficulty:
        chosen = rules.preset(args.difficulty)
        if chosen:
            base = chosen
        elif args.difficulty.lower() != rules.CUSTOM.lower():
            names = ", ".join(level.name.lower() for level in rules.PRESETS)
            raise SystemExit(f"omarchysweep: unknown difficulty {args.difficulty!r} (try {names}, custom)")

    width = args.width or base.width
    height = args.height or base.height
    if args.density is not None:
        mines = round(width * height * args.density / 100)
    else:
        mines = args.mines or base.mines
        if (args.width or args.height) and not args.mines:
            # Keep the density of the level being resized.
            mines = round(width * height * base.density)

    name = base.name
    if (width, height, mines) != (base.width, base.height, base.mines):
        name = rules.CUSTOM
    if args.difficulty and args.difficulty.lower() == rules.CUSTOM.lower():
        name = rules.CUSTOM
    return rules.make_level(name, width, height, mines)


def print_theme() -> None:
    theme = Theme.load()
    print(f"theme      {theme.name} ({theme.mode})")
    for role in ("bg", "fg", "accent", "muted", "frame", "tile", "cursor_bg", "flag", "mine"):
        print(f"{role:<10} {getattr(theme, role)}")
    for number, colour in sorted(theme.numbers.items()):
        print(f"{number:<10} {colour}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.theme_info:
        print_theme()
        return 0
    if not sys.stdout.isatty():
        print("omarchysweep: needs an interactive terminal", file=sys.stderr)
        return 1

    state = State()
    level = resolve_level(args, state)
    game = Game(level, state)
    if args.colors != "auto":
        game.paint = Paint(truecolor=args.colors == "truecolor")

    with Screen() as screen:
        cols, rows = screen.size()
        # Never open a board the window cannot show; setup can grow it later.
        game.new_game(rules.make_level(
            level.name,
            min(level.width, fit_width(cols)),
            min(level.height, fit_height(rows)),
            level.mines,
        ))
        if args.setup:
            game.open_options()
        try:
            game.run(screen)
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
