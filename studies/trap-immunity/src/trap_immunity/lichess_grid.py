"""Lichess: the explorer read over a grid of traps, quarters, speeds and ratings.

Each cell of the grid costs two requests:

* the *parent* position, where the setter chooses whether to set the trap. The
  share of games continuing with the setter's move is the trap's adoption;
* the *bait* position, where the victim moves. The share continuing with a
  `falls` move is the fall rate, and the results of those games say what
  falling cost.

A cell whose parent was never reached is stored without its second request: no
game can then have reached the bait either, short of a transposition too rare
to pay a request for.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Iterator, NamedTuple

from chesslab.http import ApiError
from chesslab.lichess.explorer import ExplorerPosition, fetch_position
from trap_immunity import config
from trap_immunity.config import Period
from trap_immunity.storage import KeyedJsonl
from trap_immunity.traps import Trap

logger = logging.getLogger(__name__)


class Cell(NamedTuple):
    trap: Trap
    period: Period
    speed: str
    rating: int

    @property
    def key(self) -> tuple[str, str, str, int]:
        return (self.trap.slug, self.period.label, self.speed, self.rating)


def cell_key(row: dict) -> tuple[str, str, str, int]:
    return (row["trap"], row["period"], row["speed"], int(row["rating"]))


def open_store() -> KeyedJsonl:
    return KeyedJsonl(config.explorer_path(), cell_key)


def grid(
    traps: Iterable[Trap],
    periods: Iterable[Period] = config.PERIODS,
    speeds: Iterable[str] = config.SPEEDS,
    ratings: Iterable[int] = config.EXPLORER_RATINGS,
) -> Iterator[Cell]:
    """Every cell, one trap at a time, so that an interrupted run leaves whole curves."""
    periods, speeds, ratings = tuple(periods), tuple(speeds), tuple(ratings)
    for trap in traps:
        for period in periods:
            for speed in speeds:
                for rating in ratings:
                    yield Cell(trap, period, speed, rating)


def cell_row(cell: Cell, parent: ExplorerPosition, bait: ExplorerPosition | None) -> dict:
    """The stored form of a cell: counts only, enough to recompute every rate."""
    setter_move = parent.move(cell.trap.setter_move)
    row = {
        "trap": cell.trap.slug,
        "period": cell.period.label,
        "speed": cell.speed,
        "rating": cell.rating,
        "parent_games": parent.games,
        "setter_move_games": setter_move.games if setter_move else 0,
        "bait_games": 0,
        "fall_games": 0,
        "fall_white": 0,
        "fall_draws": 0,
        "fall_black": 0,
        "bait_moves": {},
    }
    if bait is None:
        return row
    falls = [move for move in bait.moves if cell.trap.is_fall(move.san)]
    row.update(
        bait_games=bait.games,
        fall_games=sum(move.games for move in falls),
        fall_white=sum(move.white for move in falls),
        fall_draws=sum(move.draws for move in falls),
        fall_black=sum(move.black for move in falls),
        bait_moves={move.san: move.games for move in bait.moves},
    )
    return row


@dataclass
class GridStats:
    requests: int = 0
    cells_stored: int = 0
    cells_skipped: int = 0
    failures: int = 0


class GridCollector:
    """Fills the store cell by cell; re-running it resumes where it stopped."""

    def __init__(
        self,
        client,
        store: KeyedJsonl,
        *,
        max_requests: int = 20000,
        max_consecutive_failures: int = 5,
    ) -> None:
        self._client = client
        self._store = store
        self._max_requests = max_requests
        self._max_failures = max_consecutive_failures
        # The bait of one trap can be the parent of the next (the two Stafford
        # positions), so a position read once in a run is not read again.
        self._cache: dict[tuple, ExplorerPosition] = {}
        self.stats = GridStats()

    def collect(self, cells: Iterable[Cell]) -> GridStats:
        consecutive_failures = 0
        for cell in cells:
            if cell.key in self._store:
                self.stats.cells_skipped += 1
                continue
            if self.stats.requests + 2 > self._max_requests:
                logger.warning("request budget of %d reached", self._max_requests)
                break
            try:
                row = self._read(cell)
            except ApiError as exc:
                consecutive_failures += 1
                self.stats.failures += 1
                logger.warning("cell %s failed: %s (%d in a row)", cell.key, exc, consecutive_failures)
                if consecutive_failures >= self._max_failures:
                    logger.error("explorer looks unavailable, stopping")
                    break
                continue
            consecutive_failures = 0
            self._store.add(row)
            self.stats.cells_stored += 1
            if self.stats.cells_stored % 100 == 0:
                logger.info(
                    "%d cells stored, %d requests, now at %s", self.stats.cells_stored,
                    self.stats.requests, cell.key,
                )
        return self.stats

    def _read(self, cell: Cell) -> dict:
        parent = self._position(cell, cell.trap.parent_uci)
        bait = self._position(cell, cell.trap.line_uci) if parent.games else None
        return cell_row(cell, parent, bait)

    def _position(self, cell: Cell, play: tuple[str, ...]) -> ExplorerPosition:
        key = (play, cell.period.label, cell.speed, cell.rating)
        if key not in self._cache:
            self._cache[key] = fetch_position(
                self._client, play, speeds=[cell.speed], ratings=[cell.rating],
                since=cell.period.first, until=cell.period.last,
            )
            self.stats.requests += 1
        return self._cache[key]
