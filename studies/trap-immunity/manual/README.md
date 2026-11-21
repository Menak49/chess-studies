# Manual readings of the chess.com explorer

chess.com has no public API for position counts, and its terms forbid reading
the site with a bot. `chesscom_explorer.csv` is filled by hand from
https://www.chess.com/analysis/explorer, one row per trap and year.

What each row measures: at `position`, how often the side to move enters the
trap with `entry_move`, and how those games end.

- `games_with_move`: number of games where `entry_move` was played.
- `played_pct`: share of games at `position` continuing with `entry_move`.
- `white_win_pct`, `black_win_pct`: results of the games with `entry_move`, as
  the explorer shows them. Draws are the remainder.

Percentages are written as numbers without the % sign (18.3, not 18.3%).

## Filters

Use the same filters for every row and write them here, so the readings can be
repeated:

- Game database:
- Time controls:
- Ratings:
- Date range: one calendar year per row (January to December)
- Date of the readings:
