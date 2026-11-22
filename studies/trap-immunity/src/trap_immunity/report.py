"""Tables and figures of the study, rebuilt from whatever has been collected.

Each site is reported independently: a run with only the Lichess grid, or only
some chess.com years, still produces its part.
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from trap_immunity import config  # noqa: E402
from trap_immunity.analysis import (  # noqa: E402
    FREQUENCY_SCALE,
    MIN_GAMES_PLOTTED,
    SITES,
    before_after,
    chesscom_monthly_cells,
    chesscom_rates,
    coverage,
    lichess_monthly_cells,
    lichess_rates,
    manual_entry_frame,
)
from trap_immunity.chesscom_crawl import open_store as open_trap_store  # noqa: E402
from trap_immunity.lichess_grid import open_store as open_explorer_store  # noqa: E402
from trap_immunity.lichess_grid import open_totals_store  # noqa: E402
from trap_immunity.traps import TRAPS, TRAPS_BY_SLUG, Trap  # noqa: E402

logger = logging.getLogger(__name__)

#: One blue, light to dark, for rating groups from weakest to strongest. The
#: groups are ordered, so an ordinal ramp, not categorical hues. Checked with
#: the dataviz validator (ordinal, light surface).
GROUP_COLOURS = dict(zip(
    [label for _, _, label in config.REPORT_GROUPS],
    ["#86b6ef", "#3987e5", "#1c5cab", "#0d366b"],
))
INK, MUTED, GRID = "#2b2b2b", "#6b6b6b", "#e6e6e3"


def load_explorer_rows() -> list[dict]:
    return list(open_explorer_store().read_all())


def load_explorer_totals() -> list[dict]:
    return list(open_totals_store().read_all())


def load_trap_games(years=config.CHESSCOM_YEARS) -> list[dict]:
    return [
        row
        for year in years
        for row in open_trap_store(config.trap_games_path(year)).read_all()
    ]


def generate_report(
    explorer_rows: list[dict] | None = None,
    trap_games: list[dict] | None = None,
    totals: list[dict] | None = None,
    manual: pd.DataFrame | None = None,
    tables: Path = config.TABLES,
    figures: Path = config.FIGURES,
) -> list[Path]:
    """Write every table and figure; return their paths.

    A trap is reported for a site only once `MIN_TRAP_GAMES` baits were reached
    there. Rarer traps are dropped from that site's tables and figures and only
    appear in `coverage.csv`, which says why.
    """
    explorer_rows = load_explorer_rows() if explorer_rows is None else explorer_rows
    trap_games = load_trap_games() if trap_games is None else trap_games
    totals = load_explorer_totals() if totals is None else totals
    manual = manual_entry_frame() if manual is None else manual
    if explorer_rows and not totals:
        logger.info("no Lichess totals yet: run `lichess-totals` for the frequency")
    if not explorer_rows and not trap_games:
        logger.warning("nothing collected yet: run `lichess` or `chesscom` first")
        return []
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)

    lichess = lichess_rates(explorer_rows, totals=totals)
    chesscom = chesscom_rates(trap_games)
    covered = coverage(lichess, chesscom)
    written = [_csv(covered, tables / "coverage.csv")]
    kept = {
        site: set(covered.loc[(covered["site"] == site) & covered["reported"], "trap"])
        for site in SITES
    }
    for site, frame in (("lichess", lichess), ("chesscom", chesscom)):
        dropped = sorted(set(covered.loc[covered["site"] == site, "trap"]) - kept[site])
        if dropped:
            logger.info("%s: too few baits to report %s", site, ", ".join(dropped))
    lichess = _keep(lichess, kept["lichess"])
    chesscom = _keep(chesscom, kept["chesscom"])

    if not lichess.empty:
        written.append(_csv(lichess, tables / "lichess_rates.csv"))
        by_speed = _keep(lichess_rates(explorer_rows, by=("trap", "period", "speed", "group"), totals=totals), kept["lichess"])
        written.append(_csv(by_speed, tables / "lichess_rates_by_speed.csv"))
    if not chesscom.empty:
        written.append(_csv(chesscom, tables / "chesscom_rates.csv"))

    comparison = pd.concat([
        before_after(_keep(lichess_monthly_cells(explorer_rows), kept["lichess"]), "lichess"),
        before_after(_keep(chesscom_monthly_cells(trap_games), kept["chesscom"]), "chesscom"),
    ], ignore_index=True)
    if not comparison.empty:
        written.append(_csv(comparison, tables / "before_after.csv"))

    if not manual.empty:
        written.append(_csv(manual, tables / "chesscom_explorer_entry.csv"))
        written.append(plot_entry(manual, figures / "chesscom_explorer_entry.png"))

    for trap in TRAPS:
        path = plot_trap(trap, lichess, chesscom, figures / f"{trap.slug}.png")
        if path is not None:
            written.append(path)
    return written


def _keep(frame: pd.DataFrame, traps: set[str]) -> pd.DataFrame:
    if frame.empty:
        return frame
    return frame[frame["trap"].isin(traps)].reset_index(drop=True)


def _csv(frame: pd.DataFrame, path: Path) -> Path:
    frame.round(4).to_csv(path, index=False)
    return path


def _of_trap(frame: pd.DataFrame, trap: Trap) -> pd.DataFrame:
    if frame.empty:
        return frame
    return frame[frame["trap"] == trap.slug]


def plot_trap(trap: Trap, lichess: pd.DataFrame, chesscom: pd.DataFrame, path: Path) -> Path | None:
    """Four panels on one time axis: Lichess frequency and adoption, then the falls on both sites."""
    lichess, chesscom = _of_trap(lichess, trap), _of_trap(chesscom, trap)
    if lichess.empty and chesscom.empty:
        return None

    panels = [
        (f"Lichess: games reaching the bait per {FREQUENCY_SCALE:,} games", lichess, "frequency",
         "all_games", "-"),
        ("Lichess: share of games where the trap is set", lichess, "adoption", "parent_games", "-"),
        ("Lichess: share of victims who take the bait", lichess, "fall_rate", "bait_games", "-"),
        ("chess.com: share of victims who take the bait", chesscom, "fall_rate", "bait_games", "o"),
    ]
    figure, axes = plt.subplots(len(panels), 1, figsize=(9, 12), sharex=True)
    for axis, (title, frame, rate, games, style) in zip(axes, panels):
        _panel(axis, title, frame, rate, games, style, trap)
    # One legend for all panels, built from whichever panels have data.
    labelled = {}
    for axis in axes:
        for handle, label in zip(*axis.get_legend_handles_labels()):
            labelled.setdefault(label, handle)
    order = [label for _, _, label in config.REPORT_GROUPS if label in labelled]
    if order:
        figure.legend([labelled[label] for label in order], order, title="Rating group",
                      frameon=False, fontsize=8, title_fontsize=8, loc="upper right", ncol=len(order))
    # The whole study period on every figure, whatever has been collected, so
    # that two traps' figures can be read side by side.
    years = range(config.FIRST_YEAR, config.LAST_MONTH.year + 2)
    axes[-1].set_xlim(years[0], years[-1])
    axes[-1].set_xticks(list(years))
    axes[-1].set_xlabel("Year", color=INK)
    figure.suptitle(trap.name, color=INK, fontsize=12, x=0.07, ha="left")
    note = (
        "Lichess groups games by the average rating of both players; chess.com by the victim's rating. "
        f"Points resting on fewer than {MIN_GAMES_PLOTTED} games are hidden."
    )
    figure.text(0.07, 0.01, note, fontsize=7, color=MUTED)
    figure.tight_layout(rect=(0, 0.03, 1, 0.97))
    figure.savefig(path, dpi=150)
    plt.close(figure)
    return path


def _panel(axis, title, frame, rate, games, style, trap: Trap) -> None:
    axis.set_title(title, fontsize=9, color=INK, loc="left")
    if rate != "frequency":
        axis.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    axis.grid(axis="y", color=GRID, linewidth=0.8)
    axis.set_axisbelow(True)
    for side in ("top", "right"):
        axis.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axis.spines[side].set_color(MUTED)
    axis.tick_params(colors=MUTED, labelsize=8)
    boom_start, boom_end = (_decimal(month) for month in config.CHESS_BOOM)
    axis.axvspan(boom_start, boom_end + 1 / 12, color=GRID, alpha=0.6, linewidth=0)
    axis.annotate("2020 boom", (boom_start, 1), xycoords=("data", "axes fraction"),
                  xytext=(3, -10), textcoords="offset points", fontsize=7, color=MUTED)
    if trap.popularised is not None:
        when = _decimal(trap.popularised)
        axis.axvline(when, color=MUTED, linestyle="--", linewidth=1)
        axis.annotate("video", (when, 1), xycoords=("data", "axes fraction"),
                      xytext=(3, -20), textcoords="offset points", fontsize=7, color=MUTED)
    if frame.empty or frame[rate].isna().all():
        axis.text(0.5, 0.5, "no data collected yet", transform=axis.transAxes,
                  ha="center", color=MUTED, fontsize=8)
        return
    for index, (_, _, group) in enumerate(config.REPORT_GROUPS):
        cells = frame[(frame["group"] == group) & (frame[games] >= MIN_GAMES_PLOTTED) & frame[rate].notna()]
        cells = cells.sort_values("midpoint")
        if cells.empty:
            continue
        colour = GROUP_COLOURS[group]
        if style == "-":
            axis.plot(cells["midpoint"], cells[rate], color=colour, linewidth=2, label=group)
            axis.fill_between(cells["midpoint"], cells[f"{rate}_low"], cells[f"{rate}_high"],
                              color=colour, alpha=0.15, linewidth=0)
        else:
            # Yearly points of the four groups share an x; a small offset
            # keeps their intervals from hiding one another.
            dodge = (index - (len(config.REPORT_GROUPS) - 1) / 2) * 0.08
            axis.errorbar(
                (cells["midpoint"] + dodge).to_numpy(), cells[rate].to_numpy(),
                # Clipped: at 0% or 100% rounding can put a bound a hair inside the rate.
                yerr=[(cells[rate] - cells[f"{rate}_low"]).clip(lower=0).to_numpy(),
                      (cells[f"{rate}_high"] - cells[rate]).clip(lower=0).to_numpy()],
                color=colour, marker="o", markersize=5, linewidth=2, capsize=0, label=group,
            )
    axis.set_ylim(bottom=0)


def plot_entry(frame: pd.DataFrame, path: Path) -> Path:
    """Share of games entering each trap on chess.com, by year: one panel per trap.

    The traps' shares differ by an order of magnitude, so each gets its own
    panel and scale rather than sharing one axis.
    """
    slugs = [slug for slug in dict.fromkeys(frame["trap"])]
    figure, axes = plt.subplots(len(slugs), 1, figsize=(9, 2.8 * len(slugs) + 0.6), sharex=True,
                                squeeze=False)
    for axis, slug in zip(axes[:, 0], slugs):
        cells = frame[frame["trap"] == slug].sort_values("year")
        row = cells.iloc[0]
        trap = TRAPS_BY_SLUG.get(slug)
        # The opening only: the readings measure entering the gambit, not the trap move.
        opening = trap.name.split(",")[0] if trap else slug
        title = f"{opening}: share of games at {row['position']} continuing {row['entry_move']}"
        axis.set_title(title, fontsize=9, color=INK, loc="left")
        axis.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(100))
        axis.grid(axis="y", color=GRID, linewidth=0.8)
        axis.set_axisbelow(True)
        for side in ("top", "right"):
            axis.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            axis.spines[side].set_color(MUTED)
        axis.tick_params(colors=MUTED, labelsize=8)
        boom_start, boom_end = (_decimal(month) for month in config.CHESS_BOOM)
        axis.axvspan(boom_start, boom_end + 1 / 12, color=GRID, alpha=0.6, linewidth=0)
        if trap is not None and trap.popularised is not None:
            axis.axvline(_decimal(trap.popularised), color=MUTED, linestyle="--", linewidth=1)
        # A calendar year is plotted at its middle, like the chess.com rates.
        x = cells["year"] + 0.5
        axis.plot(x, cells["played_pct"], color=GROUP_COLOURS["1600-1999"], linewidth=2,
                  marker="o", markersize=5)
        peak = cells.loc[cells["played_pct"].idxmax()]
        axis.annotate(f"{peak['played_pct']:g}%", (peak["year"] + 0.5, peak["played_pct"]),
                      xytext=(0, 6), textcoords="offset points", ha="center", fontsize=8, color=INK)
        axis.set_ylim(0, cells["played_pct"].max() * 1.2)
    years = range(config.FIRST_YEAR, config.LAST_MONTH.year + 2)
    axes[-1, 0].set_xlim(years[0], years[-1])
    axes[-1, 0].set_xticks(list(years))
    axes[-1, 0].set_xlabel("Year", color=INK)
    figure.suptitle("chess.com opening explorer, read by hand", color=INK, fontsize=12, x=0.07, ha="left")
    figure.text(0.07, 0.01, "Shaded: the 2020 boom. Dashed: the trap's video. Filters in manual/README.md.",
                fontsize=7, color=MUTED)
    figure.tight_layout(rect=(0, 0.03, 1, 0.97))
    figure.savefig(path, dpi=150)
    plt.close(figure)
    return path


def _decimal(month) -> float:
    return month.year + (month.month - 1) / 12
