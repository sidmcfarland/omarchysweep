# OmarchySweep

Classic Minesweeper for the terminal, built for [Omarchy](https://omarchy.org/).
It reads the palette of whatever theme you are running, so the board looks like
the rest of the desktop — and it re-colours itself the moment you switch themes.

```
╭─ OmarchySweep · Retro 82 ──────────────╮
│ Beginner                9x9 · 10 mines │
│ ⚑  8            00:14          playing │
├────────────────────────────────────────┤
│           · · · · · · · · ·            │
│           · · 1     1 ⚑ 2 ·            │
│           · · 1     1 2 2 ·            │
│           · 2 1       1 1 1            │
│           · ⚑ 1       1 · ·            │
│           · 2 2 1 1 1 2 · ·            │
│           · · · · · · · · ·            │
│           · · · · · · · · ·            │
│           · · · · · · · · ·            │
├────────────────────────────────────────┤
│ ←↑↓→ move  f flag  d dig               │
│ n new  o setup  ? help  q quit         │
╰────────────────────────────────────────╯
```

## Install

On Omarchy, from the AUR:

```bash
omarchy pkg aur add omarchysweep-git
```

Or from source, anywhere:

```bash
git clone https://github.com/sidmcfarland/omarchysweep
cd omarchysweep
./install.sh
```

`install.sh` symlinks the launcher into `~/.local/bin`, installs the icon, and
adds an **OmarchySweep** entry to the Omarchy menu — all user-local, no sudo.
The AUR package installs the same set system-wide. Either way the menu entry
opens the game with
`xdg-terminal-exec --app-id=TUI.float`, the app-id Omarchy already floats and
centres, so no Hyprland config is needed.

Right hand on the arrows, left hand on the home row: `f` and `d` sit next to
each other, so flagging and digging never move either hand.

`./uninstall.sh` removes all of it (`--purge` also drops your best times). The
AUR package installs the same things system-wide; remove it with `pacman -R`.

Requirements: Python 3.10+ and a terminal. Nothing else — no pip packages.

## Playing

| Key | Action |
| --- | --- |
| `←` `↑` `↓` `→` or `h` `j` `k` `l` | move the selection |
| `f` | toggle a flag on the selected box |
| `d` (or `enter`) | dig the selected box |
| `d` on a number | chord — dig its unflagged neighbours once the flags match |
| `home` / `end` | jump to the first or last column |
| `pgup` / `pgdn` | jump to the top or bottom row |
| `n` | new game, same settings |
| `o` | grid size and difficulty |
| `?` | help |
| `q` | quit |

The first dig is always safe and always opens a pocket — mines are dealt after
it. Clear every box that is not a mine to win. Best times are kept per grid in
`~/.local/state/omarchysweep/state.json`.

## Grid size and difficulty

Press `o` in game. `↑` `↓` pick a field, `←` `→` adjust it, `pgup`/`pgdn` step
by five, `enter` starts the new board.

| Preset | Grid | Mines |
| --- | --- | --- |
| Beginner | 9×9 | 10 |
| Intermediate | 16×16 | 40 |
| Expert | 30×16 | 99 |
| Custom | 5–40 × 5–24 | 1 upwards |

Width, height and mines are free to set; changing any of them switches the
level to Custom. The setup screen never offers a grid larger than the window
can show, and the last settings you played are remembered.

The same thing from the command line:

```bash
omarchysweep                                  # last game you played
omarchysweep -d expert                        # a preset
omarchysweep -W 24 -H 14 -m 60                # a custom grid
omarchysweep -W 24 -H 14 --density 18         # ...or by mine density
omarchysweep --setup                          # open the setup screen first
omarchysweep --theme-info                     # print the resolved palette
```

## Theming

Colours are resolved in this order:

1. `omarchy-theme-color --all` — the resolver Omarchy uses for its own
   templates, so aliases and derived shades match exactly.
2. `~/.local/state/omarchy/current/theme/colors.toml`, parsed directly.
3. A built-in Catppuccin-ish palette, for machines without Omarchy.

The theme file is re-checked while you play, so `omarchy theme set <name>` in
another window recolours the board in place.

Themes with a narrow palette often alias colours (blue and magenta being the
same hex, say). The 1–8 count colours and the cursor are nudged apart when that
happens, so every number stays distinguishable and the selection stays visible
against both covered tiles and open ground. All 22 stock themes are covered by
a test.

Terminals advertising `COLORTERM=truecolor` get exact 24-bit colour; everything
else falls back to the nearest xterm-256 entry. Force it either way with
`--colors truecolor` or `--colors 256`.

## Layout

```
omarchysweep/board.py   grid, mine placement, reveal, flag, chord, win/lose
omarchysweep/theme.py   Omarchy palette lookup and the derived colour roles
omarchysweep/term.py    raw terminal, key decoding, styled lines
omarchysweep/ui.py      rendering and the input loop
omarchysweep/state.py   remembered settings and best times
tests/                  python3 -m unittest discover -s tests
```

## Contributing

```bash
python3 -m unittest discover -s tests
```

No build step and no dependencies — edit and run. Bug reports and pull
requests are welcome at
[github.com/sidmcfarland/omarchysweep](https://github.com/sidmcfarland/omarchysweep).

## License

MIT — see [LICENSE](LICENSE).
