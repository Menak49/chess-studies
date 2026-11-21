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
from trap_immunity.analysis import MIN_GAMES_PLOTTED, chesscom_rates, lichess_rates  # noqa: E402
from trap_immunity.chesscom_crawl import open_store as open_trap_store  # noqa: E402
from trap_immunity.lichess_grid import open_store as open_explorer_store  # noqa: E402
from trap_immunity.traps import TRAPS, Trap  # noqa: E402

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


def load_trap_games(years=config.CHESSCOM_YEARS) -> list[dict]:
    return [
        row
        for year in years
        for row in open_trap_store(config.trap_games_path(year)).read_all()
    ]


def generate_report(
    explorer_rows: list[dict] | None = None,
    trap_games: list[dict] | None = None,
    tables: Path = config.TABLES,
    figures: Path = config.FIGURES,
) -> list[Path]:
    """Write every table and figure; return their paths."""
    explorer_rows = load_explorer_rows() if explorer_rows is None else explorer_rows
    trap_games = load_trap_games() if trap_games is None else trap_games
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    lichess = lichess_rates(explorer_rows)
    chesscom = chesscom_rates(trap_games)
    if lichess.empty:
        logger.warning("no Lichess explorer cells yet: run `lichess` first")
    else:
        written.append(_csv(lichess, tables / "lichess_rates.csv"))
        by_speed = lichess_rates(explorer_rows, by=("trap", "period", "speed", "group"))
        written.append(_csv(by_speed, tables / "lichess_rates_by_speed.csv"))
    if chesscom.empty:
        logger.warning("no chess.com trap games yet: run `chesscom` first")
    else:
        written.append(_csv(chesscom, tables / "chesscom_rates.csv"))

    for trap in TRAPS:
        path = plot_trap(trap, lichess, chesscom, figures / f"{trap.slug}.png")
        if path is not None:
            written.append(path)
    return written


def _csv(frame: pd.DataFrame, path: Path) -> Path:
    frame.round(4).to_csv(path, index=False)
    return path


def _of_trap(frame: pd.DataFrame, trap: Trap) -> pd.DataFrame:
    if frame.empty:
        return frame
    return frame[frame["trap"] == trap.slug]


def plot_trap(trap: Trap, lichess: pd.DataFrame, chesscom: pd.DataFrame, path: Path) -> Path | None:
    """Three panels on one time axis: Lichess adoption, Lichess falls, chess.com falls."""
    lichess, chesscom = _of_trap(lichess, trap), _of_trap(chesscom, trap)
    if lichess.empty and chesscom.empty:
        return None

    panels = [
        ("Lichess: share of games where the trap is set", lichess, "adoption", "parent_games", "-"),
        ("Lichess: share of victims who take the bait", lichess, "fall_rate", "bait_games", "-"),
        ("chess.com: share of victims who take the bait", chesscom, "fall_rate", "bait_games", "o"),
    ]
    figure, axes = plt.subplots(len(panels), 1, figsize=(9, 9.5), sharex=True)
    for axis, (title, frame, rate, games, style) in zip(axes, panels):
        _panel(axis, title, frame, rate, games, style, trap)
    # One legend for the three panels, built from whichever panels have data.
    labelled = {}
    for axis in axes:
        for handle, label in zip(*axis.get_legend_handles_labels()):
            labelled.setdefault(label, handle)
    order = [label for _, _, label in config.REPORT_GROUPS if label in labelled]
    if order:
        figure.legend([labelled[label] for label in order], order, title="Rating group",
                      frameon=False, fontsize=8, title_fontsize=8, loc="upper right", ncol=len(order))
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
    axis.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    axis.grid(axis="y", color=GRID, linewidth=0.8)
    axis.set_axisbelow(True)
    for side in ("top", "right"):
        axis.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axis.spines[side].set_color(MUTED)
    axis.tick_params(colors=MUTED, labelsize=8)
    if trap.popularised is not None:
        when = trap.popularised.year + (trap.popularised.month - 1) / 12
        axis.axvline(when, color=MUTED, linestyle="--", linewidth=1)
        axis.annotate(
            "popularised", (when, 1), xycoords=("data", "axes fraction"),
            xytext=(3, -10), textcoords="offset points", fontsize=7, color=MUTED,
        )
    if frame.empty:
        axis.text(0.5, 0.5, "no data collected yet", transform=axis.transAxes,
                  ha="center", color=MUTED, fontsize=8)
        return
    for index, (_, _, group) in enumerate(config.REPORT_GROUPS):
        cells = frame[(frame["group"] == group) & (frame[games] >= MIN_GAMES_PLOTTED)]
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
                cells["midpoint"] + dodge, cells[rate],
                yerr=[cells[rate] - cells[f"{rate}_low"], cells[f"{rate}_high"] - cells[rate]],
                color=colour, marker="o", markersize=5, linewidth=2, capsize=0, label=group,
            )
    axis.set_ylim(bottom=0)
