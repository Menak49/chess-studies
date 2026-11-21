"""Starting accounts for the chess.com crawl of one year.

Seeds only start the walk: as soon as the opponent graph and the setters it
reveals are there, the crawler visits them first. They are drawn from large
club rosters, keeping only accounts that had joined before the year began, so
that a seed could have played that year at all. The same rule applies to every
year, so the bootstrap favours none of them.
"""

from __future__ import annotations

import json
import logging
import random
from datetime import datetime, timezone
from pathlib import Path

from chesslab.chesscom import ChessComClient, fetch_club_members_with_dates

logger = logging.getLogger(__name__)

SEED_CLUBS: tuple[str, ...] = (
    "team-usa", "team-england", "team-germany", "team-spain", "team-brazil",
    "team-netherlands", "team-poland", "team-france", "team-australia",
    "team-sweden", "team-india", "team-canada",
)


def load_seeds(client: ChessComClient, year: int, cache_dir: Path) -> list[str]:
    """Club members who had joined before `year`, in a shuffled order fixed per year."""
    pool = _load_pool(client, cache_dir)
    cutoff = datetime(year, 1, 1, tzinfo=timezone.utc).timestamp()
    seeds = sorted(name for name, joined in pool if joined and joined < cutoff)
    random.Random(year).shuffle(seeds)
    logger.info("[chesscom %d] %d seeds", year, len(seeds))
    return seeds


def _load_pool(client: ChessComClient, cache_dir: Path) -> list[tuple[str, int]]:
    """The rosters, fetched once and cached: every year filters the same pool."""
    cache = cache_dir / "seed_pool.json"
    if cache.exists():
        return [tuple(item) for item in json.loads(cache.read_text(encoding="utf-8"))]
    members: dict[str, int] = {}
    for club in SEED_CLUBS:
        roster = fetch_club_members_with_dates(client, club)
        for name, joined in roster:
            members[name] = min(members.get(name, joined), joined)
        logger.info("club %s: %d members", club, len(roster))
    pool = sorted(members.items())
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(pool), encoding="utf-8")
    return pool
