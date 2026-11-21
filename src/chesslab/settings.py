"""Settings shared by every study: where things live, how to talk to the APIs,
and the engine that serves as the measuring instrument.

A study's own protocol (years, rating window, sampling quotas) lives in that
study's `config` module, never here. The engine settings are here on purpose:
scores computed by different studies are only comparable, and only reusable from
one study to the next, if they come from the same instrument.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Each study keeps its data under `DATA_ROOT / <study name>`.
DATA_ROOT = REPO_ROOT / "data"


@dataclass(frozen=True, order=True)
class YearMonth:
    """A month of play, the granularity of the chess.com archive endpoint."""

    year: int
    month: int

    def __str__(self) -> str:
        return f"{self.year}-{self.month:02d}"

    @property
    def path_fragment(self) -> str:
        """The `YYYY/MM` fragment used by the archive URL."""
        return f"{self.year}/{self.month:02d}"

    @classmethod
    def parse(cls, text: str) -> "YearMonth":
        year, month = text.split("-")
        return cls(int(year), int(month))


# --- Engine analysis --------------------------------------------------------

#: Fixed search depth. Identical for every game of every year and platform: the
#: measurement instrument must not drift between the things being compared.
ENGINE_DEPTH = 12

#: Opening plies skipped when scoring. Book moves are memorised, not calculated,
#: and their availability has changed over the years; scoring them would measure
#: opening preparation rather than playing strength.
OPENING_PLIES_SKIPPED = 8

#: Safety cap on how many plies of a single game are scored, counted from the
#: end of the opening. Set high enough that ordinary games are scored in full;
#: it exists so that a pathological 300-move game cannot monopolise a worker.
MAX_PLIES_SCORED_PER_GAME = 200

#: Where the UCI engine binary lives, and how many are run at once.
ENGINE_PATH = REPO_ROOT / "tools" / "stockfish" / "stockfish.exe"
DEFAULT_ENGINE_WORKERS = 14


# --- HTTP -------------------------------------------------------------------

API_ROOT = "https://api.chess.com/pub"
LICHESS_ROOT = "https://lichess.org"

#: Both sites ask for a contactable User-Agent and throttle parallel callers.
USER_AGENT = "chess-studies-research/1.0 (academic study; contact via repository)"
REQUEST_TIMEOUT_SECONDS = 60
MAX_RETRIES = 4
BACKOFF_BASE_SECONDS = 2.0

#: Lichess asks that a client which receives a 429 waits a full minute.
LICHESS_RATE_LIMIT_PAUSE_SECONDS = 61.0

#: The opening explorer is served from its own host and, unlike the rest of the
#: public API, answers only requests carrying a personal token. Any token works,
#: without a scope; it is read from this environment variable, never stored.
LICHESS_EXPLORER_ROOT = "https://explorer.lichess.ovh"
LICHESS_TOKEN_ENV = "LICHESS_TOKEN"
