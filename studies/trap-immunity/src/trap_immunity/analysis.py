"""From stored counts and trap games to rates by trap, period and rating group.

Two rates are followed through time:

* the *fall rate*: among games reaching the bait, the share where the victim
  takes it. This is the immunity curve. On Lichess it is grouped by the average
  rating of the game, on chess.com by the victim's own rating;
* the *adoption* (Lichess only): among games reaching the setter's decision, the
  share where the trap is set. It shows who sets the trap and when, so that a
  falling fall rate can be told apart from a change in who meets it.
"""

from __future__ import annotations

import math
from typing import Iterable

import pandas as pd

from trap_immunity import config

#: Rates resting on fewer games are left out of the figures (kept in the tables).
MIN_GAMES_PLOTTED = 30


def wilson_interval(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval of a proportion; (nan, nan) without trials."""
    if trials <= 0:
        return math.nan, math.nan
    p = successes / trials
    denominator = 1 + z**2 / trials
    centre = (p + z**2 / (2 * trials)) / denominator
    half = z * math.sqrt(p * (1 - p) / trials + z**2 / (4 * trials**2)) / denominator
    return max(0.0, centre - half), min(1.0, centre + half)


def _add_rate(frame: pd.DataFrame, name: str, successes: str, trials: str) -> pd.DataFrame:
    frame[name] = frame[successes] / frame[trials].where(frame[trials] > 0)
    bounds = [wilson_interval(int(k), int(n)) for k, n in zip(frame[successes], frame[trials])]
    frame[f"{name}_low"] = [low for low, _ in bounds]
    frame[f"{name}_high"] = [high for _, high in bounds]
    return frame


def lichess_rates(rows: Iterable[dict], by: tuple[str, ...] = ("trap", "period", "group")) -> pd.DataFrame:
    """Explorer cells summed into `by` cells, with adoption and fall rates."""
    frame = pd.DataFrame(list(rows))
    if frame.empty:
        return frame
    frame["group"] = frame["rating"].map(config.report_group)
    counts = [
        "parent_games", "setter_move_games", "bait_games",
        "fall_games", "fall_white", "fall_draws", "fall_black",
    ]
    summed = frame.groupby(list(by), as_index=False)[counts].sum()
    summed = _add_rate(summed, "adoption", "setter_move_games", "parent_games")
    summed = _add_rate(summed, "fall_rate", "fall_games", "bait_games")
    return _with_period_midpoints(summed)


def cap_per_setter(frame: pd.DataFrame, cap: int = config.MAX_GAMES_PER_SETTER_PER_CELL, seed: int = 0) -> pd.DataFrame:
    """At most `cap` games per setter in each (year, trap, victim band) cell, drawn at random.

    The same cap the crawl used to fill its quotas: it keeps one prolific setter
    from standing for a whole band. The draw is random, not chronological, so
    that a setter's first months are not favoured.
    """
    frame = frame.assign(
        year=frame["month"].str[:4].astype(int),
        band=(frame["victim_rating"] // config.VICTIM_BAND_WIDTH) * config.VICTIM_BAND_WIDTH,
    )
    shuffled = frame.sample(frac=1.0, random_state=seed)
    capped = shuffled.groupby(["year", "trap", "band", "setter"], group_keys=False).head(cap)
    return capped.sort_values(["year", "trap", "month", "game_id"]).reset_index(drop=True)


def chesscom_rates(rows: Iterable[dict], by: tuple[str, ...] = ("trap", "year", "group")) -> pd.DataFrame:
    """Trap games, capped per setter, into fall rates by `by` cell."""
    frame = pd.DataFrame(list(rows))
    if frame.empty:
        return frame
    frame = cap_per_setter(frame)
    frame["group"] = frame["victim_rating"].map(config.report_group)
    frame["fell"] = frame["fell"].astype(int)
    grouped = frame.groupby(list(by))
    summary = grouped.agg(
        bait_games=("fell", "size"),
        fall_games=("fell", "sum"),
        setters=("setter", "nunique"),
        victims=("victim", "nunique"),
    ).reset_index()
    largest = grouped["setter"].agg(lambda setters: setters.value_counts().iloc[0])
    summary["largest_setter_share"] = (largest.to_numpy() / summary["bait_games"]).round(3)
    summary = _add_rate(summary, "fall_rate", "fall_games", "bait_games")
    if "year" in summary:
        summary["midpoint"] = summary["year"] + 0.5
    return summary


def _with_period_midpoints(frame: pd.DataFrame) -> pd.DataFrame:
    if "period" in frame:
        midpoints = {period.label: period.midpoint for period in config.PERIODS}
        frame["midpoint"] = frame["period"].map(midpoints)
    return frame
