"""Reading the moves out of a PGN without a full parse.

`chess.pgn.read_game` builds a whole game tree and is far too slow for a crawl
that scans every game of thousands of archives only to look at the first dozen
moves. Both sites write a flat movetext, without variations, so a tokenizer is
enough: drop the comments, move numbers, annotations and the result, and what
remains is the list of SAN moves.
"""

from __future__ import annotations

import re

#: `{[%clk 0:02:13.7]}` and any other comment; removed first, because the
#: tenths of a second inside look exactly like move numbers.
_COMMENT = re.compile(r"\{[^}]*\}")
_MOVE_NUMBER = re.compile(r"^\d+\.(?:\.\.)?$")
_RESULTS = frozenset({"1-0", "0-1", "1/2-1/2", "*"})


def movetext(pgn: str) -> str:
    """The movetext of a PGN: everything after the header block."""
    if pgn.lstrip().startswith("["):
        _, separator, body = pgn.partition("\n\n")
        return body if separator else ""
    return pgn


def san_moves(pgn: str, limit: int | None = None) -> list[str]:
    """The SAN moves of a PGN, in order, at most `limit` of them.

    Handles both `12. Nf3 12... Nc6` (chess.com) and `12. Nf3 Nc6` (Lichess).
    Check and annotation marks are stripped, so `Bxf7+!` reads `Bxf7`.
    """
    moves: list[str] = []
    for token in _COMMENT.sub(" ", movetext(pgn)).split():
        if limit is not None and len(moves) >= limit:
            break
        if token in _RESULTS or token.startswith("$"):
            continue
        number, dot, rest = token.partition(".")
        if _MOVE_NUMBER.match(token):
            continue
        if dot and number.isdigit():  # `12.Nf3`, written without the space
            token = rest.lstrip(".")
            if not token:
                continue
        moves.append(normalise_san(token))
    return moves


def normalise_san(san: str) -> str:
    """Drop check, mate and annotation marks, the parts two writers disagree on."""
    return san.rstrip("+#!?")
