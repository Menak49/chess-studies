"""chess.com: finding trap games by following the players who set them.

chess.com offers no search by position, only each player's monthly archives.
Sampling players at random would be hopeless: a given trap appears in a tiny
fraction of games, so thousands of archives would yield a handful of baits. The
crawl therefore runs in two modes:

* *discovery*: read one sampled month of an account met in the opponent graph,
  as elo-drift does. Most of these archives contain no bait, but every bait
  found names its setter.
* *following*: read every sampled month of the year for a setter. Players who
  set a trap tend to set it again and again, so one setter's archives hold
  dozens of baits, each with its own victim.

Two rules keep the sample honest:

* Setters are found among the year's own games, never by looking back from
  today. A crawl that started from today's adopters would only see the players
  for whom the trap kept working, and would flatten the very decline the study
  looks for.
* Every bait found is stored, but a setter counts towards a cell's quota for at
  most `MAX_GAMES_PER_SETTER_PER_CELL` games, and the analysis applies the same
  cap. One prolific setter must not stand for a whole rating band.
"""

from __future__ import annotations

import logging
import random
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Protocol

from chesslab.chesscom import ChessComClient, fetch_available_months, fetch_monthly_archive
from chesslab.http import ApiError
from chesslab.records import classify_result
from chesslab.settings import YearMonth
from chesslab.store import VisitedLog
from trap_immunity import config
from trap_immunity.storage import KeyedJsonl
from trap_immunity.traps import TRAPS, Trap, TrapDetector

logger = logging.getLogger(__name__)

STANDARD_START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

#: A cell of the design: one trap, one 200-point band of victim rating.
Cell = tuple[str, int]

#: Accounts kept in the discovery queue; beyond this, new opponents are dropped.
MAX_FRONTIER = 200_000


class ArchiveSource(Protocol):
    def available_months(self, username: str) -> list[YearMonth]: ...

    def games(self, username: str, month: YearMonth) -> list[dict[str, Any]]: ...


class ChessComArchives:
    """The two archive endpoints, one request each."""

    def __init__(self, client: ChessComClient) -> None:
        self._client = client

    def available_months(self, username: str) -> list[YearMonth]:
        return fetch_available_months(self._client, username)

    def games(self, username: str, month: YearMonth) -> list[dict[str, Any]]:
        return fetch_monthly_archive(self._client, username, month)


def victim_band(rating: int) -> int | None:
    if not config.VICTIM_RATING_MIN <= rating < config.VICTIM_RATING_MAX:
        return None
    offset = (rating - config.VICTIM_RATING_MIN) // config.VICTIM_BAND_WIDTH
    return config.VICTIM_RATING_MIN + offset * config.VICTIM_BAND_WIDTH


def victim_bands() -> tuple[int, ...]:
    return tuple(range(config.VICTIM_RATING_MIN, config.VICTIM_RATING_MAX, config.VICTIM_BAND_WIDTH))


def trap_rows(raw: dict[str, Any], month: YearMonth, detector: TrapDetector) -> list[dict[str, Any]]:
    """The baits one archived game reached, as rows, or [] if it is not eligible.

    Eligible: standard chess from the initial position, rated, bullet to rapid.
    Thematic tournaments start from a gambit already on the board and would
    count baits nobody chose to set. A bait where the game ended (time, resign)
    has no victim move and is left out.
    """
    if raw.get("rules") != "chess" or not raw.get("rated"):
        return []
    if raw.get("time_class") not in config.SPEEDS:
        return []
    if raw.get("initial_setup", STANDARD_START) != STANDARD_START:
        return []
    white, black = raw.get("white"), raw.get("black")
    if not isinstance(white, dict) or not isinstance(black, dict):
        return []
    if not (white.get("rating") and black.get("rating") and raw.get("pgn")):
        return []

    sides = {"white": white, "black": black}
    rows = []
    for moment in detector.scan(raw["pgn"]):
        if moment.victim_move is None:
            continue
        victim = sides[moment.trap.victim]
        setter = sides[moment.trap.setter]
        rows.append({
            "game_id": raw.get("uuid") or raw["url"],
            "url": raw.get("url", ""),
            "month": str(month),
            "period": config.period_of(month),
            "end_time": int(raw.get("end_time") or 0),
            "time_class": raw["time_class"],
            "time_control": str(raw.get("time_control", "")),
            "trap": moment.trap.slug,
            "setter": str(setter["username"]).lower(),
            "setter_rating": int(setter["rating"]),
            "victim": str(victim["username"]).lower(),
            "victim_rating": int(victim["rating"]),
            "victim_move": moment.victim_move,
            "fell": bool(moment.fell),
            "victim_result": classify_result(str(victim.get("result", ""))),
        })
    return rows


def row_key(row: dict[str, Any]) -> tuple[str, str]:
    return (row["game_id"], row["trap"])


def open_store(path: Path) -> KeyedJsonl:
    return KeyedJsonl(path, row_key)


class TrapTarget:
    """Per-(trap, victim band) quotas for one year, counting capped contributions."""

    def __init__(
        self,
        traps: Iterable[Trap] = TRAPS,
        per_cell: int = config.TRAP_GAMES_PER_CELL,
        per_setter: int = config.MAX_GAMES_PER_SETTER_PER_CELL,
    ) -> None:
        self.cells: tuple[Cell, ...] = tuple(
            (trap.slug, band) for trap in traps for band in victim_bands()
        )
        self._cell_set = set(self.cells)
        self.per_cell = per_cell
        self.per_setter = per_setter
        self._counts: dict[Cell, int] = defaultdict(int)
        self._setter_counts: dict[tuple[str, Cell], int] = defaultdict(int)

    def cell_of(self, row: dict[str, Any]) -> Cell | None:
        band = victim_band(row["victim_rating"])
        cell = (row["trap"], band)
        return cell if band is not None and cell in self._cell_set else None

    def credit(self, row: dict[str, Any]) -> bool:
        """Count a stored row if its cell still wants it from this setter."""
        cell = self.cell_of(row)
        if cell is None or self._counts[cell] >= self.per_cell:
            return False
        if self._setter_counts[(row["setter"], cell)] >= self.per_setter:
            return False
        self._counts[cell] += 1
        self._setter_counts[(row["setter"], cell)] += 1
        return True

    def trap_deficit(self, slug: str) -> int:
        return sum(max(0, self.per_cell - self._counts[c]) for c in self.cells if c[0] == slug)

    @property
    def is_complete(self) -> bool:
        return all(self._counts[cell] >= self.per_cell for cell in self.cells)

    @property
    def progress(self) -> str:
        filled = sum(min(self._counts[cell], self.per_cell) for cell in self.cells)
        return f"{filled}/{len(self.cells) * self.per_cell}"


@dataclass
class CrawlStats:
    index_requests: int = 0
    archives_read: int = 0
    games_scanned: int = 0
    baits_found: int = 0
    baits_stored: int = 0
    baits_credited: int = 0
    players_discovered: int = 0
    setters_followed: int = 0
    failures: int = 0

    @property
    def requests(self) -> int:
        return self.index_requests + self.archives_read

    def as_dict(self) -> dict[str, int]:
        return {**asdict(self), "requests": self.requests}


class AdopterCrawler:
    """Walks one year of chess.com, following every setter it meets."""

    def __init__(
        self,
        source: ArchiveSource,
        store: KeyedJsonl,
        year: int,
        target: TrapTarget,
        log: VisitedLog,
        *,
        traps: tuple[Trap, ...] = TRAPS,
        rng: random.Random | None = None,
        max_requests: int = 5000,
        stall_requests: int = 1500,
        max_consecutive_failures: int = 10,
    ) -> None:
        self._source = source
        self._store = store
        self._months = config.chesscom_months(year)
        self._year = year
        self._target = target
        self._log = log
        self._detector = TrapDetector(traps)
        self._rng = rng or random.Random(year)
        self._max_requests = max_requests
        self._stall_requests = stall_requests
        self._max_failures = max_consecutive_failures

        # A list popped at random rather than a queue: read in order, the walk
        # would stay among the first seeds' acquaintances for thousands of visits.
        self._frontier: list[str] = []
        self._queued: set[str] = set()
        #: setter -> (times seen setting a trap, which traps)
        self._candidates: dict[str, tuple[int, set[str]]] = {}
        self._last_progress_at = 0
        self.stats = CrawlStats()

    # -- the log keeps three kinds of entries, so a resumed run skips them all --

    def _read_key(self, username: str, month: YearMonth) -> str:
        return f"{username}|{month}"

    def _followed(self, username: str) -> bool:
        return f"@{username}" in self._log

    def _discovered(self, username: str) -> bool:
        return f"~{username}" in self._log

    # -- public API ---------------------------------------------------------

    def crawl(self, seeds: list[str]) -> CrawlStats:
        self._resume()
        seed_queue = deque(seeds)
        failures = 0
        while not self._target.is_complete and self.stats.requests < self._max_requests:
            if self.stats.requests - self._last_progress_at >= self._stall_requests:
                logger.warning(
                    "[chesscom %d] nothing credited in %d requests, stopping at %s",
                    self._year, self._stall_requests, self._target.progress,
                )
                break
            step = self._next(seed_queue)
            if step is None:
                logger.warning("[chesscom %d] no account left to visit", self._year)
                break
            username, follow = step
            try:
                if follow:
                    self._follow(username)
                else:
                    self._discover(username)
            except ApiError as exc:
                failures += 1
                self.stats.failures += 1
                logger.warning("[chesscom %d] skipping %s: %s", self._year, username, exc)
                if failures >= self._max_failures:
                    logger.error("[chesscom %d] API looks unavailable, stopping", self._year)
                    break
            else:
                failures = 0
            visits = self.stats.players_discovered + self.stats.setters_followed
            if visits % 50 == 0:
                self._log.save()
                logger.info(
                    "[chesscom %d] %d requests, %d baits stored, %d setters followed, coverage %s",
                    self._year, self.stats.requests, self.stats.baits_stored,
                    self.stats.setters_followed, self._target.progress,
                )
        self._log.save()
        return self.stats

    # -- internals ----------------------------------------------------------

    def _resume(self) -> None:
        """Count what is stored and requeue its setters, as the first run left them."""
        for row in self._store.read_all():
            self._target.credit(row)
            self._sighting(row)

    def _next(self, seed_queue: deque[str]) -> tuple[str, bool] | None:
        setter = self._best_candidate()
        if setter is not None:
            return setter, True
        while self._frontier:
            username = self._pop_random()
            if not self._discovered(username) and not self._followed(username):
                return username, False
        while seed_queue:
            username = seed_queue.popleft()
            if not self._discovered(username) and not self._followed(username):
                return username, False
        return None

    def _pop_random(self) -> str:
        index = self._rng.randrange(len(self._frontier))
        self._frontier[index], self._frontier[-1] = self._frontier[-1], self._frontier[index]
        return self._frontier.pop()

    def _best_candidate(self) -> str | None:
        """The setter seen most often among those whose traps still want games."""
        best, best_score = None, 0
        for username, (sightings, traps) in self._candidates.items():
            if sightings < config.ADOPTER_MIN_SIGHTINGS:
                continue
            if not any(self._target.trap_deficit(slug) for slug in traps):
                continue
            if sightings > best_score:
                best, best_score = username, sightings
        if best is not None:
            del self._candidates[best]
        return best

    def _months_to_read(self, username: str) -> list[YearMonth]:
        self.stats.index_requests += 1
        available = set(self._source.available_months(username))
        return [
            month for month in self._months
            if month in available and self._read_key(username, month) not in self._log
        ]

    def _discover(self, username: str) -> None:
        self._log.add(f"~{username}")
        self.stats.players_discovered += 1
        months = self._months_to_read(username)
        if months:
            self._read(username, self._rng.choice(months))

    def _follow(self, username: str) -> None:
        self._log.add(f"@{username}")
        self.stats.setters_followed += 1
        for month in self._months_to_read(username):
            if self.stats.requests >= self._max_requests:
                return
            self._read(username, month)

    def _read(self, owner: str, month: YearMonth) -> None:
        raw_games = self._source.games(owner, month)
        self._log.add(self._read_key(owner, month))
        self.stats.archives_read += 1
        for raw in raw_games:
            self.stats.games_scanned += 1
            self._queue_opponents(raw, owner)
            for row in trap_rows(raw, month, self._detector):
                self.stats.baits_found += 1
                self._sighting(row)
                if self._store.add(row):
                    self.stats.baits_stored += 1
                    if self._target.credit(row):
                        self.stats.baits_credited += 1
                        self._last_progress_at = self.stats.requests

    def _sighting(self, row: dict[str, Any]) -> None:
        setter = row["setter"]
        if self._followed(setter):
            return
        sightings, traps = self._candidates.get(setter, (0, set()))
        traps.add(row["trap"])
        self._candidates[setter] = (sightings + 1, traps)

    def _queue_opponents(self, raw: dict[str, Any], owner: str) -> None:
        if len(self._frontier) >= MAX_FRONTIER:
            return
        for colour in ("white", "black"):
            side = raw.get(colour)
            if not isinstance(side, dict) or not side.get("username"):
                continue
            username = str(side["username"]).lower()
            if username == owner or username in self._queued:
                continue
            self._queued.add(username)
            self._frontier.append(username)
