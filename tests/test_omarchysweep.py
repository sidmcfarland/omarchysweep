"""Unit tests: python3 -m unittest discover -s tests"""

import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from omarchysweep import board as rules
from omarchysweep.board import FLAGGED, HIDDEN, LOST, PLAYING, READY, REVEALED, WON, Board, Level
from omarchysweep.state import State
from omarchysweep.term import Line, Paint, _xterm256
from omarchysweep.theme import Theme, _distance, _mix
from omarchysweep.ui import Game, _visible_width, clock, fit


def played(level, seed=1):
    return Board(level, random.Random(seed))


class BoardRules(unittest.TestCase):
    def test_first_dig_is_never_a_mine_and_opens_a_pocket(self):
        for seed in range(30):
            board = played(rules.PRESETS[0], seed)
            board.reveal(4, 4)
            self.assertFalse(board.is_mine(4, 4))
            self.assertEqual(board.status, PLAYING)
            self.assertGreater(board.revealed, 1)

    def test_mine_count_matches_the_level(self):
        board = played(rules.PRESETS[1])
        board.reveal(0, 0)
        mines = sum(
            board.is_mine(x, y) for y in range(board.height) for x in range(board.width)
        )
        self.assertEqual(mines, board.mines)

    def test_numbers_count_adjacent_mines(self):
        board = played(rules.PRESETS[2])
        board.reveal(15, 8)
        for y in range(board.height):
            for x in range(board.width):
                if board.is_mine(x, y):
                    continue
                expected = sum(1 for nx, ny in board.neighbours(x, y) if board.is_mine(nx, ny))
                self.assertEqual(board.count_at(x, y), expected, f"at {x},{y}")

    def test_space_toggles_a_flag_both_ways(self):
        board = played(rules.PRESETS[0])
        self.assertTrue(board.toggle_flag(2, 2))
        self.assertEqual(board.state_at(2, 2), FLAGGED)
        self.assertEqual(board.remaining, board.mines - 1)
        self.assertTrue(board.toggle_flag(2, 2))
        self.assertEqual(board.state_at(2, 2), HIDDEN)
        self.assertEqual(board.remaining, board.mines)

    def test_flags_protect_a_cell_and_cannot_land_on_open_ground(self):
        board = played(rules.PRESETS[0])
        board.reveal(4, 4)
        board.toggle_flag(0, 0)
        self.assertFalse(board.reveal(0, 0))
        opened = next(
            (x, y)
            for y in range(board.height)
            for x in range(board.width)
            if board.state_at(x, y) == REVEALED
        )
        self.assertFalse(board.toggle_flag(*opened))

    def test_digging_a_mine_ends_the_game_and_shows_the_field(self):
        board = played(rules.PRESETS[0])
        board.reveal(0, 0)
        mine = next(
            (x, y)
            for y in range(board.height)
            for x in range(board.width)
            if board.is_mine(x, y)
        )
        board.reveal(*mine)
        self.assertEqual(board.status, LOST)
        self.assertEqual(board.exploded, mine)
        self.assertTrue(board.over)
        for y in range(board.height):
            for x in range(board.width):
                if board.is_mine(x, y):
                    self.assertNotEqual(board.state_at(x, y), HIDDEN)

    def test_clearing_every_safe_box_wins_and_flags_the_rest(self):
        board = played(Level("Tiny", 5, 5, 3))
        board.reveal(2, 2)
        for y in range(board.height):
            for x in range(board.width):
                if not board.is_mine(x, y):
                    board.reveal(x, y)
        self.assertEqual(board.status, WON)
        self.assertEqual(board.remaining, 0)
        self.assertEqual(board.flags, board.mines)

    def test_chord_only_fires_on_a_satisfied_number(self):
        board = played(rules.PRESETS[1], seed=5)
        board.reveal(8, 8)
        def chordable(x, y):
            if board.state_at(x, y) != REVEALED or board.count_at(x, y) != 1:
                return False
            hidden_safe = [
                (nx, ny)
                for nx, ny in board.neighbours(x, y)
                if board.state_at(nx, ny) == HIDDEN and not board.is_mine(nx, ny)
            ]
            return bool(hidden_safe)

        spot = next(
            (x, y)
            for y in range(board.height)
            for x in range(board.width)
            if chordable(x, y)
        )
        self.assertFalse(board.chord(*spot), "unflagged neighbours must not auto-open")
        mine = next(
            (nx, ny) for nx, ny in board.neighbours(*spot) if board.is_mine(nx, ny)
        )
        board.toggle_flag(*mine)
        before = board.revealed
        board.chord(*spot)
        self.assertGreater(board.revealed, before)

    def test_a_dense_board_still_deals(self):
        board = played(rules.make_level("Dense", 5, 5, rules.max_mines(5, 5)))
        board.reveal(2, 2)
        self.assertIn(board.status, (PLAYING, WON, LOST))

    def test_make_level_clamps_to_playable_bounds(self):
        level = rules.make_level("Custom", 999, 0, 10_000)
        self.assertEqual((level.width, level.height), (rules.MAX_WIDTH, rules.MIN_HEIGHT))
        self.assertLessEqual(level.mines, rules.max_mines(level.width, level.height))
        self.assertGreaterEqual(level.mines, 1)


class ThemeColours(unittest.TestCase):
    def test_every_stock_theme_yields_a_readable_palette(self):
        import glob

        import omarchysweep.theme as theme_module

        stock = sorted(glob.glob("/usr/share/omarchy/themes/*/colors.toml"))
        if not stock:
            self.skipTest("no Omarchy themes installed")
        original = theme_module.COLORS_TOML
        try:
            for path in stock:
                theme_module.COLORS_TOML = Path(path)
                theme = Theme(theme_module._from_toml(), Path(path).parent.name)
                with self.subTest(theme=theme.name):
                    self.assertEqual(len(set(theme.numbers.values())), 8)
                    contrast = min(
                        _distance(theme.cursor_bg, theme.tile),
                        _distance(theme.cursor_bg, theme.bg),
                    )
                    self.assertGreaterEqual(contrast, 60)
        finally:
            theme_module.COLORS_TOML = original

    def test_falls_back_when_omarchy_is_absent(self):
        theme = Theme({})
        self.assertTrue(theme.bg.startswith("#"))
        self.assertEqual(len(theme.numbers), 8)

    def test_theme_reloads_when_the_active_theme_changes(self):
        import omarchysweep.theme as theme_module
        import omarchysweep.ui as ui_module

        game = Game(rules.PRESETS[0], State(path=Path("/nonexistent/state.json")))
        stamps = iter([game.theme_stamp, game.theme_stamp + 1])
        loaded = []
        original_stamp, original_load = theme_module.Theme.stamp, theme_module.Theme.load
        try:
            theme_module.Theme.stamp = staticmethod(lambda: next(stamps))
            theme_module.Theme.load = classmethod(
                lambda cls: loaded.append(1) or Theme({"accent": "#ff0000"}, "Test")
            )
            ui_module.Theme = theme_module.Theme
            game.refresh_theme()
            self.assertEqual(loaded, [])
            game.refresh_theme()
            self.assertEqual(len(loaded), 1)
            self.assertEqual(game.theme.accent, "#ff0000")
        finally:
            theme_module.Theme.stamp = original_stamp
            theme_module.Theme.load = original_load

    def test_mix_interpolates(self):
        self.assertEqual(_mix("#000000", "#ffffff", 0.5), "#808080")


class Rendering(unittest.TestCase):
    def setUp(self):
        self.game = Game(rules.PRESETS[0], State(path=Path("/nonexistent/state.json")))

    def test_every_view_fills_the_screen_exactly(self):
        for cols, rows in ((80, 24), (120, 40), (60, 20), (200, 50)):
            for view in ("board", "options", "help"):
                self.game.view = view
                lines = self.game.compose(cols, rows)
                with self.subTest(view=view, size=(cols, rows)):
                    self.assertEqual(len(lines), rows)
                    self.assertEqual({_visible_width(l) for l in lines}, {cols})

    def test_expert_board_fits_a_standard_float(self):
        game = Game(rules.PRESETS[2], State(path=Path("/nonexistent/state.json")))
        lines = game.compose(100, 32)
        self.assertNotIn("Terminal too small", "".join(lines))

    def test_arrows_move_the_cursor_and_stop_at_the_edges(self):
        self.game.cursor = (0, 0)
        self.game.handle_board_key("left")
        self.game.handle_board_key("up")
        self.assertEqual(self.game.cursor, (0, 0))
        self.game.handle_board_key("right")
        self.game.handle_board_key("down")
        self.assertEqual(self.game.cursor, (1, 1))
        self.game.handle_board_key("end")
        self.assertEqual(self.game.cursor, (self.game.board.width - 1, 1))

    def test_f_flags_the_selected_box(self):
        self.game.cursor = (3, 3)
        self.game.handle_board_key("f")
        self.assertEqual(self.game.board.state_at(3, 3), FLAGGED)
        self.game.handle_board_key("f")
        self.assertEqual(self.game.board.state_at(3, 3), HIDDEN)

    def test_space_no_longer_touches_the_board(self):
        self.game.cursor = (3, 3)
        self.game.handle_board_key("space")
        self.assertEqual(self.game.board.state_at(3, 3), HIDDEN)
        self.assertEqual(self.game.board.status, READY)

    def test_d_and_enter_both_dig_and_start_the_clock(self):
        for key in ("d", "enter"):
            with self.subTest(key=key):
                self.setUp()
                self.assertEqual(self.game.board.status, READY)
                self.game.handle_board_key(key)
                self.assertEqual(self.game.board.status, PLAYING)
                self.assertIsNotNone(self.game.started)

    def test_setup_screen_adjusts_the_grid(self):
        self.game.open_options()
        self.game.field = 1  # width
        for _ in range(3):
            self.game.handle_options_key("right", 200, 60)
        self.assertEqual(self.game.draft["width"], 12)
        self.assertEqual(self.game.draft["difficulty"], rules.CUSTOM)
        self.game.handle_options_key("enter", 200, 60)
        self.assertEqual(self.game.board.width, 12)
        self.assertEqual(self.game.view, "board")

    def test_setup_presets_cycle(self):
        self.game.open_options()
        self.game.field = 0
        self.game.handle_options_key("right", 200, 60)
        self.assertEqual(self.game.draft["difficulty"], "Intermediate")
        self.assertEqual(self.game.draft["mines"], 40)

    def test_setup_keeps_the_grid_inside_the_window(self):
        self.game.open_options()
        self.game.field = 2  # height
        for _ in range(40):
            self.game.handle_options_key("right", 80, 24)
        self.assertLessEqual(self.game.draft["height"], 24 - 10)

    def test_mine_count_cannot_exceed_the_grid(self):
        self.game.open_options()
        self.game.field = 3
        for _ in range(200):
            self.game.handle_options_key("right", 200, 60)
        self.assertLessEqual(self.game.draft["mines"], rules.max_mines(9, 9))


class Terminal(unittest.TestCase):
    def test_line_tracks_visible_width_not_escapes(self):
        line = Line(Paint(True), "#000000")
        line.add("abc", "#ffffff", bold=True).pad_to(10)
        self.assertEqual(line.width, 10)
        self.assertEqual(_visible_width(line.render()), 10)

    def test_256_colour_fallback(self):
        self.assertEqual(_xterm256("#000000"), 16)
        self.assertEqual(_xterm256("#ffffff"), 231)
        self.assertIn("38;5;", Paint(False).fg("#ff0000"))
        self.assertIn("38;2;", Paint(True).fg("#ff0000"))

    def test_clock_and_fit(self):
        self.assertEqual(clock(0), "00:00")
        self.assertEqual(clock(61), "01:01")
        self.assertEqual(clock(9999), "99:39")
        self.assertEqual(fit("abcdef", 4), "abc…")
        self.assertEqual(fit("ab", 4), "ab")


class Persistence(unittest.TestCase):
    def test_best_time_round_trip(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            state = State(path=path)
            state.level = rules.PRESETS[1]
            self.assertTrue(state.record(rules.PRESETS[1], 42.0))
            self.assertFalse(state.record(rules.PRESETS[1], 50.0))
            self.assertTrue(state.record(rules.PRESETS[1], 30.0))
            state.save()
            reloaded = State(path=path)
            self.assertEqual(reloaded.level, rules.PRESETS[1])
            self.assertEqual(reloaded.best_for(rules.PRESETS[1]), 30.0)

    def test_corrupt_state_is_ignored(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text("{not json")
            state = State(path=path)
            self.assertEqual(state.level, rules.PRESETS[0])


if __name__ == "__main__":
    unittest.main()
