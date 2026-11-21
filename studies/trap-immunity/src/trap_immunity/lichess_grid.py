"""Lichess: the explorer read over a grid of traps, quarters, speeds and ratings.

Each cell of the grid costs two requests:

* the *parent* position, where the setter chooses whether to set the trap. The
  share of games continuing with the setter's move is the trap's adoption;
* the *bait* position, where the victim moves. Every reply is stored with its
  results; the analysis then counts the falls.

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
    """The stored form of a cell: raw counts only.

    Every reply played at the bait is kept with its results, and nothing is
    classified here. Which replies fall is decided by the engine classification
    at analysis time, so changing the threshold never means collecting again.
    """
    setter_move = parent.move(cell.trap.setter_move)
    return {
        "trap": cell.trap.slug,
        "period": cell.period.label,
        "speed": cell.speed,
        "rating": cell.rating,
        "parent_games": parent.games,
        "setter_move_games": setter_move.games if setter_move else 0,
        "bait_games": bait.games if bait else 0,
        "bait_moves": {
            move.san: [move.white, move.draws, move.black] for move in (bait.moves if bait else ())
        },
    }


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
        self.stats.requests += 1
        return fetch_position(
            self._client, play, speeds=[cell.speed], ratings=[cell.rating],
            since=cell.period.first, until=cell.period.last,
        )
