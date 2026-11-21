"""From stored counts and trap games to rates by trap, period and rating group.

Rates followed through time:

* the *fall rate*: among games reaching the bait, the share where the victim's
  reply leaves the setter two pawns up or more (the engine classification). This
  is the immunity curve. On Lichess it is grouped by the average rating of the
  game, on chess.com by the victim's own rating;
* the *key fall rate*: the same for the textbook blunder alone, the move the
  videos show. Learning that specific move and learning to play the position
  well are not the same thing;
* the *adoption* (Lichess only): among games reaching the setter's decision, the
  share where the trap is set. It shows who sets the trap and when, so that a
  falling fall rate can be told apart from a change in who meets it.

Falls are recomputed here from the raw replies, never read from the stored
rows: the classification can then change without collecting anything again.
"""

from __future__ import annotations

import math
from typing import Iterable

import pandas as pd

from chesslab.pgn import normalise_san
from chesslab.settings import YearMonth
from trap_immunity import config
from trap_immunity.traps import TRAPS_BY_SLUG, Trap

#: Rates resting on fewer games are left out of the figures (kept in the tables).
MIN_GAMES_PLOTTED = 30

SITES = ("lichess", "chesscom")


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


# --- Lichess -----------------------------------------------------------------


def _explorer_counts(row: dict, trap: Trap) -> dict:
    """Falls, key falls and the setter's score after a fall, from one cell's replies."""
    key_fall = normalise_san(trap.key_fall)
    setter_index = 0 if trap.setter == "white" else 2
    fall = key = points = 0.0
    for san, (white, draws, black) in row.get("bait_moves", {}).items():
        games = white + draws + black
        if trap.is_fall(san):
            fall += games
            points += (white, draws, black)[setter_index] + 0.5 * draws
        if normalise_san(san) == key_fall:
            key += games
    return {"fall_games": int(fall), "key_fall_games": int(key), "fall_setter_points": points}


def explorer_frame(rows: Iterable[dict]) -> pd.DataFrame:
    """One line per explorer cell of a followed trap, with its falls counted."""
    records = []
    for row in rows:
        trap = TRAPS_BY_SLUG.get(row["trap"])
        if trap is None:
            continue
        records.append({
            **{key: row[key] for key in ("trap", "period", "speed", "rating")},
            "parent_games": row["parent_games"],
            "setter_move_games": row["setter_move_games"],
            "bait_games": row["bait_games"],
            **_explorer_counts(row, trap),
        })
    frame = pd.DataFrame(records)
    if not frame.empty:
        frame["group"] = frame["rating"].map(config.report_group)
    return frame


def lichess_rates(rows: Iterable[dict], by: tuple[str, ...] = ("trap", "period", "group")) -> pd.DataFrame:
    """Explorer cells summed into `by` cells, with adoption and fall rates."""
    frame = explorer_frame(rows)
    if frame.empty:
        return frame
    counts = ["parent_games", "setter_move_games", "bait_games", "fall_games",
              "key_fall_games", "fall_setter_points"]
    summed = frame.groupby(list(by), as_index=False)[counts].sum()
    summed = _add_rate(summed, "adoption", "setter_move_games", "parent_games")
    summed = _add_rate(summed, "fall_rate", "fall_games", "bait_games")
    summed = _add_rate(summed, "key_fall_rate", "key_fall_games", "bait_games")
    summed["setter_score_after_fall"] = (
        summed["fall_setter_points"] / summed["fall_games"].where(summed["fall_games"] > 0)
    )
    if "period" in summed:
        midpoints = {period.label: period.midpoint for period in config.PERIODS}
        summed["midpoint"] = summed["period"].map(midpoints)
    return summed


# --- chess.com ---------------------------------------------------------------


def trap_games_frame(rows: Iterable[dict]) -> pd.DataFrame:
    """Trap games of followed traps, falls recomputed, capped per setter."""
    frame = pd.DataFrame([row for row in rows if row["trap"] in TRAPS_BY_SLUG])
    if frame.empty:
        return frame
    traps = frame["trap"].map(TRAPS_BY_SLUG)
    frame["fell"] = [int(trap.is_fall(move)) for trap, move in zip(traps, frame["victim_move"])]
    frame["key_fell"] = [
        int(normalise_san(move) == normalise_san(trap.key_fall))
        for trap, move in zip(traps, frame["victim_move"])
    ]
    frame["group"] = frame["victim_rating"].map(config.report_group)
    return cap_per_setter(frame)


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
    frame = trap_games_frame(rows)
    if frame.empty:
        return frame
    grouped = frame.groupby(list(by))
    summary = grouped.agg(
        bait_games=("fell", "size"),
        fall_games=("fell", "sum"),
        key_fall_games=("key_fell", "sum"),
        setters=("setter", "nunique"),
        victims=("victim", "nunique"),
    ).reset_index()
    largest = grouped["setter"].agg(lambda setters: setters.value_counts().iloc[0])
    summary["largest_setter_share"] = (largest.to_numpy() / summary["bait_games"]).round(3)
    summary = _add_rate(summary, "fall_rate", "fall_games", "bait_games")
    summary = _add_rate(summary, "key_fall_rate", "key_fall_games", "bait_games")
    if "year" in summary:
        summary["midpoint"] = summary["year"] + 0.5
    return summary


# --- Across sites ------------------------------------------------------------


def coverage(lichess: pd.DataFrame, chesscom: pd.DataFrame) -> pd.DataFrame:
    """Baits reached per trap and site, and whether that is enough to report it."""
    records = []
    for trap in TRAPS_BY_SLUG.values():
        for site, frame in zip(SITES, (lichess, chesscom)):
            games = int(frame.loc[frame["trap"] == trap.slug, "bait_games"].sum()) if not frame.empty else 0
            records.append({
                "trap": trap.slug, "site": site, "bait_games": games,
                "reported": games >= config.MIN_TRAP_GAMES,
            })
    return pd.DataFrame(records)


def _month_index(month: YearMonth) -> int:
    return month.year * 12 + month.month - 1


def before_after(cells: pd.DataFrame, site: str) -> pd.DataFrame:
    """Fall rate before each trap's event and from `AFTER_LAG_MONTHS` after it.

    `cells` holds `trap`, `group`, `month` (YYYY-MM, start of the cell),
    `bait_games` and `fall_games`. The difference comes with a normal-
    approximation 95% interval; the months in between are left out, as the
    news was still spreading.
    """
    if cells.empty:
        return pd.DataFrame()
    records = []
    for (slug, group), frame in cells.groupby(["trap", "group"]):
        trap = TRAPS_BY_SLUG[slug]
        event = _month_index(trap.event)
        months = frame["month"].map(lambda text: _month_index(YearMonth.parse(text)))
        before = frame[months < event]
        after = frame[months >= event + config.AFTER_LAG_MONTHS]
        n0, k0 = int(before["bait_games"].sum()), int(before["fall_games"].sum())
        n1, k1 = int(after["bait_games"].sum()), int(after["fall_games"].sum())
        record = {
            "site": site, "trap": slug, "group": group, "event": str(trap.event),
            "event_kind": trap.event_label, "before_games": n0, "after_games": n1,
            "before_rate": k0 / n0 if n0 else math.nan,
            "after_rate": k1 / n1 if n1 else math.nan,
        }
        record["change"] = record["after_rate"] - record["before_rate"]
        if n0 and n1:
            p0, p1 = k0 / n0, k1 / n1
            half = 1.96 * math.sqrt(p0 * (1 - p0) / n0 + p1 * (1 - p1) / n1)
            record["change_low"], record["change_high"] = record["change"] - half, record["change"] + half
        else:
            record["change_low"] = record["change_high"] = math.nan
        records.append(record)
    return pd.DataFrame(records)


def lichess_monthly_cells(rows: Iterable[dict]) -> pd.DataFrame:
    """Lichess counts by (trap, group, quarter), the quarter dated by its first month."""
    rates = lichess_rates(rows, by=("trap", "period", "group"))
    if rates.empty:
        return rates
    starts = {period.label: str(period.first) for period in config.PERIODS}
    return rates.assign(month=rates["period"].map(starts)).dropna(subset=["month"])


def chesscom_monthly_cells(rows: Iterable[dict]) -> pd.DataFrame:
    frame = trap_games_frame(rows)
    if frame.empty:
        return frame
    return frame.groupby(["trap", "group", "month"], as_index=False).agg(
        bait_games=("fell", "size"), fall_games=("fell", "sum")
    )
