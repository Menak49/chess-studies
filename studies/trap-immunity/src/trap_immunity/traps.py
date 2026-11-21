"""The traps followed, and how to recognise one in a game.

A trap is pinned to one position, the *bait*: the setter has just made the move
that invites the blunder and the victim is to move. What the victim plays there
is the observation.

Which replies count as falling is not written here by hand: Stockfish decides,
once per trap, in `classify` (a reply falls when it leaves the setter two pawns
up or more). `key_fall` is only the textbook blunder, kept to check that the
engine agrees with the literature. A candidate is followed only if the engine
found it admissible: a victim who replies well keeps the game level.

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
from trap_immunity import config
from trap_immunity.classify import load_classification


@dataclass(frozen=True)
class Trap:
    slug: str
    name: str
    #: SAN moves from the initial position to the bait position.
    line: tuple[str, ...]
    #: The textbook blunder, as the literature names it.
    key_fall: str
    #: When a datable video made the trap famous, and which one.
    popularised: YearMonth | None = None
    source: str = ""

    def __post_init__(self) -> None:
        self.bait_board.parse_san(self.key_fall)  # raises on an illegal line or move

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

    @property
    def event(self) -> YearMonth:
        """The trap's own popularisation, or the 2020 boom for traps without one."""
        return self.popularised or config.CHESS_BOOM[0]

    @property
    def event_label(self) -> str:
        return "video" if self.popularised else "2020 boom"

    @property
    def falls(self) -> frozenset[str]:
        entry = _CLASSIFICATION["traps"].get(self.slug, {})
        return frozenset(entry.get("falls", ()))

    def is_fall(self, san: str) -> bool:
        return normalise_san(san) in self.falls


def _line(text: str) -> tuple[str, ...]:
    return tuple(text.split())


_ROSEN = "Eric Rosen, YouTube"

#: Every trap considered. Those the engine finds admissible make `TRAPS`.
CANDIDATES: tuple[Trap, ...] = (
    Trap(
        "stafford", "Stafford Gambit, 6.Bg5",
        _line("e4 e5 Nf3 Nf6 Nxe5 Nc6 Nxc6 dxc6 d3 Bc5"), "Bg5",
        YearMonth(2020, 8), f"{_ROSEN}, 'Beating Everyone with the Same Opening Trap (Stafford Gambit)', 2020-08-01",
    ),
    Trap(
        "stafford-queen", "Stafford Gambit, 7.Bxd8",
        _line("e4 e5 Nf3 Nf6 Nxe5 Nc6 Nxc6 dxc6 d3 Bc5 Bg5 Nxe4"), "Bxd8",
        YearMonth(2020, 8), f"{_ROSEN}, 2020-08-01",
    ),
    Trap(
        "englund-rosen", "Englund Gambit, Rosen's trap, 5.dxe7",
        _line("d4 e5 dxe5 Bc5 Nf3 d6 exd6 Ne7"), "dxe7",
        YearMonth(2020, 11), f"{_ROSEN}, 'EVERYONE falls for this NEW opening trap', 2020-11-18",
    ),
    Trap(
        "englund", "Englund Gambit, 6.Bc3",
        _line("d4 e5 dxe5 Nc6 Nf3 Qe7 Bf4 Qb4+ Bd2 Qxb2"), "Bc3",
    ),
    Trap(
        "fishing-pole", "Fishing Pole, 6.hxg4",
        _line("e4 e5 Nf3 Nc6 Bb5 Nf6 O-O Ng4 h3 h5"), "hxg4",
        YearMonth(2021, 6), f"{_ROSEN}, 'Tricks & Traps Everyone Should Know in the Ruy Lopez', 2021-06-25",
    ),
    Trap(
        "blackburne-shilling", "Blackburne Shilling Gambit, 5.Nxf7",
        _line("e4 e5 Nf3 Nc6 Bc4 Nd4 Nxe5 Qg5"), "Nxf7",
    ),
    Trap(
        "scholars-mate", "Scholar's mate, 3...Nf6",
        _line("e4 e5 Bc4 Nc6 Qh5"), "Nf6",
    ),
    Trap(
        "noahs-ark", "Noah's Ark trap, 8.Qxd4",
        _line("e4 e5 Nf3 Nc6 Bb5 a6 Ba4 d6 d4 b5 Bb3 Nxd4 Nxd4 exd4"), "Qxd4",
    ),
    Trap(
        "siberian", "Siberian trap, 9.h3",
        _line("e4 c5 d4 cxd4 c3 dxc3 Nxc3 Nc6 Nf3 e6 Bc4 Qc7 O-O Nf6 Qe2 Ng4"), "h3",
    ),
    Trap(
        "caro-kann-smothered", "Caro-Kann smothered mate, 5...Ngf6",
        _line("e4 c6 d4 d5 Nc3 dxe4 Nxe4 Nd7 Qe2"), "Ngf6",
    ),
    Trap(
        "kieninger", "Budapest Gambit, Kieninger trap, 8.axb4",
        _line("d4 Nf6 c4 e5 dxe5 Ng4 Nf3 Nc6 Bf4 Bb4+ Nbd2 Qe7 a3 Ngxe5"), "axb4",
    ),
    Trap(
        "lasker", "Albin Countergambit, Lasker trap, 6.Bxb4",
        _line("d4 d5 c4 e5 dxe5 d4 e3 Bb4+ Bd2 dxe3"), "Bxb4",
    ),
    Trap(
        "legal", "Legal's mate, 5...Bxd1",
        _line("e4 e5 Nf3 d6 Bc4 Bg4 Nc3 g6 Nxe5"), "Bxd1",
    ),
)

_CLASSIFICATION = load_classification()


def _admissible(trap: Trap) -> bool:
    entry = _CLASSIFICATION["traps"].get(trap.slug)
    return bool(entry and entry["admissible"] and entry["falls"])


#: The traps the study follows: the candidates the engine found admissible.
TRAPS: tuple[Trap, ...] = tuple(trap for trap in CANDIDATES if _admissible(trap))
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
        self._depth = max((len(trap.line) for trap in traps), default=0)

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
