"""The Lichess opening explorer: game counts for one position, without the games.

The explorer indexes the rated games of Lichess by position. For a position and
a filter (speeds, rating groups, a range of months) it answers how many games
reached it, and how many continued with each move and how those ended. A study
that needs counts at a few known positions can read them here in one request per
cell instead of downloading and replaying the monthly dumps.

Two properties of the index matter to whoever reads its counts:

* A game sits in the rating group of the *average* of its two players' ratings,
  not of either player.
* Positions are matched as positions, so a game reaching one by transposition
  counts there too.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from chesslab import settings
from chesslab.env import get_secret
from chesslab.lichess.client import LichessClient
from chesslab.pgn import normalise_san
from chesslab.settings import YearMonth

#: The rating groups the explorer knows, each named by its lower bound.
RATING_GROUPS: tuple[int, ...] = (0, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2500)

#: How many continuations to ask for. The default (12) can cut off a rare
#: move, and the rare move is often precisely the one a study counts.
MAX_MOVES = 50


class MissingTokenError(RuntimeError):
    """The explorer refuses anonymous requests and no token was configured."""


@dataclass(frozen=True)
class MoveCount:
    """Games that continued from the position with one move, by result."""

    san: str
    uci: str
    white: int
    draws: int
    black: int

    @property
    def games(self) -> int:
        return self.white + self.draws + self.black


@dataclass(frozen=True)
class ExplorerPosition:
    """What the explorer knows of one position under one filter."""

    white: int
    draws: int
    black: int
    moves: tuple[MoveCount, ...]

    @property
    def games(self) -> int:
        return self.white + self.draws + self.black

    def move(self, san: str) -> MoveCount | None:
        """The continuation played as `san`, or None if nobody played it."""
        wanted = normalise_san(san)
        for move in self.moves:
            if move.san == wanted:
                return move
        return None


class ExplorerClient(LichessClient):
    """A client for explorer.lichess.ovh, authenticated with a personal token."""

    def __init__(self, token: str, *, root: str = settings.LICHESS_EXPLORER_ROOT, **kwargs) -> None:
        super().__init__(root=root, **kwargs)
        self._session.headers.update({"Authorization": f"Bearer {token}"})

    @classmethod
    def from_environment(cls, **kwargs) -> "ExplorerClient":
        token = get_secret(settings.LICHESS_TOKEN_ENV)
        if not token:
            raise MissingTokenError(
                f"the Lichess explorer needs a personal token: set {settings.LICHESS_TOKEN_ENV} "
                "in the .env file at the repository root (create one without any scope at "
                "https://lichess.org/account/oauth/token)"
            )
        return cls(token, **kwargs)


def fetch_position(
    client: LichessClient,
    play: Iterable[str],
    *,
    speeds: Iterable[str],
    ratings: Iterable[int],
    since: YearMonth,
    until: YearMonth,
) -> ExplorerPosition:
    """Counts at the position reached by the UCI moves `play`, from the start.

    `since` and `until` are both inclusive months. Asking for a single speed and
    a single rating group per call is what lets a caller build a grid.
    """
    params = {
        "variant": "standard",
        "play": ",".join(play),
        "speeds": ",".join(speeds),
        "ratings": ",".join(str(rating) for rating in ratings),
        "since": str(since),
        "until": str(until),
        "moves": MAX_MOVES,
        "topGames": 0,
        "recentGames": 0,
    }
    return parse_position(client.get("/lichess", params=params))


def parse_position(payload: dict[str, Any]) -> ExplorerPosition:
    moves = tuple(
        MoveCount(
            san=normalise_san(str(move.get("san", ""))),
            uci=str(move.get("uci", "")),
            white=int(move.get("white", 0)),
            draws=int(move.get("draws", 0)),
            black=int(move.get("black", 0)),
        )
        for move in payload.get("moves", [])
    )
    return ExplorerPosition(
        white=int(payload.get("white", 0)),
        draws=int(payload.get("draws", 0)),
        black=int(payload.get("black", 0)),
        moves=moves,
    )
