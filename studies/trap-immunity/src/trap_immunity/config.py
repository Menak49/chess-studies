"""The protocol of the study: periods, pools, quotas and where the data lives.

The two sites are read in two different ways, because they expose different
things:

* Lichess through its opening explorer, which counts every rated game reaching a
  position. One request per (trap, quarter, speed, rating group) cell, no game
  downloaded. Its rating group is the average of the two players.
* chess.com through the per-player monthly archives, the only access it offers.
  The crawl looks for the players who set a trap and reads their games, which
  gives the victim's own rating but a sample instead of a census.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from chesslab.lichess.explorer import RATING_GROUPS as EXPLORER_RATING_GROUPS
from chesslab.settings import DATA_ROOT, YearMonth

STUDY_ROOT = Path(__file__).resolve().parents[2]
DATA = DATA_ROOT / "trap-immunity"
REPORTS = STUDY_ROOT / "reports"
TABLES = REPORTS / "tables"
FIGURES = REPORTS / "figures"

FIRST_YEAR = 2015
#: The last month whose games are complete when the study was set up. The
#: explorer indexes each monthly dump some weeks after the month ends.
LAST_MONTH = YearMonth(2026, 9)


@dataclass(frozen=True)
class Period:
    """A run of months read together, named like `2020Q3`."""

    label: str
    first: YearMonth
    last: YearMonth

    @property
    def midpoint(self) -> float:
        """Decimal year at the middle of the period, for plotting."""
        start = self.first.year + (self.first.month - 1) / 12
        end = self.last.year + self.last.month / 12
        return (start + end) / 2


def quarters(first_year: int = FIRST_YEAR, last_month: YearMonth = LAST_MONTH) -> tuple[Period, ...]:
    """Every complete calendar quarter from `first_year` up to `last_month`."""
    periods = []
    for year in range(first_year, last_month.year + 1):
        for quarter in range(4):
            first = YearMonth(year, 3 * quarter + 1)
            last = YearMonth(year, 3 * quarter + 3)
            if last <= last_month:
                periods.append(Period(f"{year}Q{quarter + 1}", first, last))
    return tuple(periods)


def period_of(month: YearMonth) -> str:
    """The quarter label a month falls in."""
    return f"{month.year}Q{(month.month - 1) // 3 + 1}"


PERIODS: tuple[Period, ...] = quarters()

#: Traps are a fast-chess phenomenon; classical and correspondence are left out.
SPEEDS: tuple[str, ...] = ("bullet", "blitz", "rapid")


# --- Lichess: the explorer grid ---------------------------------------------

EXPLORER_RATINGS: tuple[int, ...] = EXPLORER_RATING_GROUPS


# --- chess.com: the adopter crawl -------------------------------------------

CHESSCOM_YEARS: tuple[int, ...] = tuple(range(FIRST_YEAR, LAST_MONTH.year + 1))

#: One month per quarter, the same ones every year, so that each year is read
#: across its seasons and the chess.com points line up with Lichess quarters.
CHESSCOM_SAMPLED_MONTHS: tuple[int, ...] = (2, 5, 8, 11)


def chesscom_months(year: int) -> tuple[YearMonth, ...]:
    return tuple(
        month
        for month in (YearMonth(year, m) for m in CHESSCOM_SAMPLED_MONTHS)
        if month <= LAST_MONTH
    )


#: Victims are binned on their own rating, in 200-point bands. Traps mostly
#: catch weak players, so the window starts lower than elo-drift's.
VICTIM_RATING_MIN = 400
VICTIM_RATING_MAX = 2400
VICTIM_BAND_WIDTH = 200

#: Trap games wanted per (trap, victim band) and per year.
TRAP_GAMES_PER_CELL = 60

#: How many games one setter may contribute to a single cell. An adopter can
#: play the Stafford a thousand times a year; without a cap the cell would
#: describe that player's opponents rather than the pool.
MAX_GAMES_PER_SETTER_PER_CELL = 10

#: A setter is followed (all their sampled months read) once seen setting a
#: trap this many times. One sighting is enough: reading them costs at most
#: five requests and a single sighting is a strong signal on such rare lines.
ADOPTER_MIN_SIGHTINGS = 1


# --- Reporting --------------------------------------------------------------

#: Coarse rating groups shared by both sites' figures, as (low, high, label).
#: On Lichess they group the explorer's average-rating buckets, on chess.com
#: the victim's rating.
REPORT_GROUPS: tuple[tuple[int, int | None, str], ...] = (
    (0, 1200, "<1200"),
    (1200, 1600, "1200-1599"),
    (1600, 2000, "1600-1999"),
    (2000, None, "2000+"),
)


def report_group(rating: int) -> str:
    for low, high, label in REPORT_GROUPS:
        if rating >= low and (high is None or rating < high):
            return label
    raise ValueError(rating)


# --- Paths ------------------------------------------------------------------

def explorer_path() -> Path:
    return DATA / "raw" / "lichess" / "explorer_cells.jsonl"


def trap_games_path(year: int) -> Path:
    return DATA / "raw" / "chesscom" / f"trap_games_{year}.jsonl"


def read_archives_path(year: int) -> Path:
    return DATA / "raw" / "chesscom" / f"read_archives_{year}.json"


def crawl_stats_path(year: int) -> Path:
    return DATA / "raw" / "chesscom" / f"crawl_stats_{year}.json"


def seed_cache_dir() -> Path:
    return DATA / "raw" / "chesscom"
