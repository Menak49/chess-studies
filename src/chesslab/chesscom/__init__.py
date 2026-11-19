"""Thin, typed access layer over the chess.com public API."""

from chesslab.chesscom.archives import (
    fetch_available_months,
    fetch_club_members_with_dates,
    fetch_country_players,
    fetch_monthly_archive,
)
from chesslab.chesscom.client import ChessComClient, ChessComError, NotFoundError

__all__ = [
    "ChessComClient",
    "ChessComError",
    "NotFoundError",
    "fetch_available_months",
    "fetch_club_members_with_dates",
    "fetch_country_players",
    "fetch_monthly_archive",
]
