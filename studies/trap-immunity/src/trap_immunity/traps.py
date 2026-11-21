"""The traps followed, and how to recognise one in a game.

A trap is pinned to one position, the *bait*: the setter has just made the move
that invites the blunder and the victim is to move. What the victim plays there
is the observation. A move listed in `falls` takes the bait; anything else
avoids it.

Every `falls` move below was checked with Stockfish 19 at depth 20 to lose at
least five pawns against the best move in the bait position (or to allow mate),
so "fell" means a real blunder rather than a merely dubious move.

Positions are matched as positions, so a game that reaches the bait by another
move order counts too. That is also how the Lichess explorer counts, which keeps
the two sites' observations alike.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

import chess

from chesslab.pgn import normalise_san, san_moves
from chesslab.settings import YearMonth


@dataclass(frozen=True)
class Trap:
    slug: str
    name: str
    #: SAN moves from the initial position to the bait position.
    line: tuple[str, ...]
    #: Victim moves that take the bait.
    falls: tuple[str, ...]
    #: When the trap went viral, if a datable event made it so.
    popularised: YearMonth | None = None
    note: str = ""

    def __post_init__(self) -> None:
        board = self.bait_board  # raises on an illegal line
        for san in self.falls:
            board.parse_san(san)

    @cached_property
    def bait_board(self) -> chess.Board:
        board = chess.Board()
        for san in self.line:
            board.push_san(san)
        return board

    @property
    def bait_key(self) -> str:
        return position_key(self.bait_board)

    @property
    def victim(self) -> str:
        return "white" if self.bait_board.turn == chess.WHITE else "black"

    @property
    def setter(self) -> str:
        return "black" if self.victim == "white" else "white"

    @property
    def line_uci(self) -> tuple[str, ...]:
        return tuple(move.uci() for move in self.bait_board.move_stack)

    @property
    def parent_uci(self) -> tuple[str, ...]:
        """The moves up to the setter's decision, one ply before the bait."""
        return self.line_uci[:-1]

    @property
    def setter_move(self) -> str:
        """The move that sets the trap, as played from the parent position."""
        return normalise_san(self.line[-1])

    def is_fall(self, san: str) -> bool:
        return normalise_san(san) in {normalise_san(fall) for fall in self.falls}


def _line(text: str) -> tuple[str, ...]:
    return tuple(text.split())


TRAPS: tuple[Trap, ...] = (
    Trap(
        slug="stafford-bg5",
        name="Stafford Gambit, 6.Bg5",
        line=_line("e4 e5 Nf3 Nf6 Nxe5 Nc6 Nxc6 dxc6 d3 Bc5"),
        falls=("Bg5",),
        popularised=YearMonth(2020, 8),
        note="Pinning the knight walks into 6...Nxe4!, which wins on the spot.",
    ),
    Trap(
        slug="stafford-queen",
        name="Stafford Gambit, 7.Bxd8",
        line=_line("e4 e5 Nf3 Nf6 Nxe5 Nc6 Nxc6 dxc6 d3 Bc5 Bg5 Nxe4"),
        falls=("Bxd8",),
        popularised=YearMonth(2020, 8),
        note="Taking the queen allows 7...Bxf2+ 8.Ke2 Bg4#.",
    ),
    Trap(
        slug="englund",
        name="Englund Gambit trap, 6.Bc3",
        line=_line("d4 e5 dxe5 Nc6 Nf3 Qe7 Bf4 Qb4+ Bd2 Qxb2"),
        falls=("Bc3",),
        note="6.Bc3 Bb4 7.Qd2 Bxc3 8.Qxc3 Qc1#. 6.Nc3 is fine for White.",
    ),
    Trap(
        slug="fishing-pole",
        name="Fishing Pole, 6.hxg4",
        line=_line("e4 e5 Nf3 Nc6 Bb5 Nf6 O-O Ng4 h3 h5"),
        falls=("hxg4",),
        note="Opening the h-file lets the queen and rook mate on h1.",
    ),
    Trap(
        slug="blackburne-shilling",
        name="Blackburne Shilling Gambit, 5.Nxf7",
        line=_line("e4 e5 Nf3 Nc6 Bc4 Nd4 Nxe5 Qg5"),
        falls=("Nxf7",),
        note="5...Qxg2 6.Rf1 Qxe4+ 7.Be2 Nf3# follows.",
    ),
    Trap(
        slug="legal",
        name="Legal's mate, 5...Bxd1",
        line=_line("e4 e5 Nf3 d6 Bc4 Bg4 Nc3 g6 Nxe5"),
        falls=("Bxd1",),
        note="A trap for Black: 6.Bxf7+ Ke7 7.Nd5#.",
    ),
)

TRAPS_BY_SLUG = {trap.slug: trap for trap in TRAPS}


def position_key(board: chess.Board) -> str:
    """Pieces, side to move, castling rights and en passant: what makes a position."""
    return board.epd()


@dataclass(frozen=True)
class TrapMoment:
    """A game reached a trap's bait; `victim_move` is None if it ended there."""

    trap: Trap
    ply: int
    victim_move: str | None

    @property
    def fell(self) -> bool | None:
        return None if self.victim_move is None else self.trap.is_fall(self.victim_move)


class TrapDetector:
    """Finds the bait positions a game passes through.

    Only the first few plies of a game are replayed: no bait lies deeper than
    the longest trap line, so a game is abandoned as soon as it is past them.
    """

    def __init__(self, traps: tuple[Trap, ...] = TRAPS) -> None:
        self._by_key: dict[str, list[Trap]] = {}
        for trap in traps:
            self._by_key.setdefault(trap.bait_key, []).append(trap)
        self._depth = max(len(trap.line) for trap in traps)

    def scan(self, pgn: str) -> list[TrapMoment]:
        moves = san_moves(pgn, limit=self._depth + 1)
        board = chess.Board()
        found: list[TrapMoment] = []
        for ply in range(min(len(moves), self._depth) + 1):
            for trap in self._by_key.get(position_key(board), ()):
                reply = moves[ply] if ply < len(moves) else None
                found.append(TrapMoment(trap, ply, reply))
            if ply >= len(moves):
                break
            try:
                board.push_san(moves[ply])
            except ValueError:
                break
        return found
