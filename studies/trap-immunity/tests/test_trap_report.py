import math

import pytest

from trap_immunity.analysis import cap_per_setter, chesscom_rates, lichess_rates, wilson_interval
from trap_immunity.cli import build_parser
from trap_immunity.report import generate_report

import pandas as pd


def explorer_row(period, rating, speed="blitz", trap="stafford-bg5", bait=100, falls=40):
    return {
        "trap": trap, "period": period, "speed": speed, "rating": rating,
        "parent_games": 1000, "setter_move_games": 200, "bait_games": bait,
        "fall_games": falls, "fall_white": 5, "fall_draws": 0, "fall_black": falls - 5,
        "bait_moves": {},
    }


def trap_game(i, setter, victim_rating, fell, month="2021-05", trap="stafford-bg5"):
    return {
        "game_id": f"g{i}", "month": month, "trap": trap, "setter": setter,
        "setter_rating": 1000, "victim": f"v{i}", "victim_rating": victim_rating,
        "victim_move": "Bg5" if fell else "Be2", "fell": fell,
    }


def test_wilson_interval():
    low, high = wilson_interval(50, 100)
    assert low == pytest.approx(0.4038, abs=1e-3) and high == pytest.approx(0.5962, abs=1e-3)
    assert all(math.isnan(x) for x in wilson_interval(0, 0))


def test_lichess_rates_sum_speeds_and_buckets_into_groups():
    rows = [
        explorer_row("2020Q3", 1200, "blitz", bait=100, falls=40),
        explorer_row("2020Q3", 1400, "rapid", bait=100, falls=20),
        explorer_row("2020Q3", 0, "blitz", bait=10, falls=9),
    ]
    rates = lichess_rates(rows).set_index("group")
    assert rates.loc["1200-1599", "bait_games"] == 200
    assert rates.loc["1200-1599", "fall_rate"] == pytest.approx(0.3)
    assert rates.loc["1200-1599", "adoption"] == pytest.approx(0.2)
    assert rates.loc["<1200", "fall_rate"] == pytest.approx(0.9)
    assert rates.loc["<1200", "midpoint"] == pytest.approx(2020 + 7.5 / 12)


def test_one_setter_is_capped_per_cell():
    rows = [trap_game(i, "prolific", 900, True) for i in range(30)]
    rows += [trap_game(100 + i, f"s{i}", 900, False) for i in range(5)]
    capped = cap_per_setter(pd.DataFrame(rows), cap=10)
    assert (capped["setter"] == "prolific").sum() == 10
    assert len(capped) == 15


def test_chesscom_rates_by_year_and_group():
    rows = [trap_game(i, f"s{i % 4}", 900, i % 2 == 0) for i in range(20)]
    rows += [trap_game(50 + i, "s9", 1700, False, month="2023-02") for i in range(3)]
    rates = chesscom_rates(rows).set_index(["year", "group"])
    cell = rates.loc[(2021, "<1200")]
    assert cell["bait_games"] == 20 and cell["fall_rate"] == pytest.approx(0.5)
    assert cell["setters"] == 4 and cell["largest_setter_share"] == pytest.approx(0.25)
    assert rates.loc[(2023, "1600-1999"), "fall_games"] == 0


def test_report_writes_tables_and_a_figure_per_trap(tmp_path):
    explorer = [explorer_row(f"{year}Q{q}", 1200) for year in (2019, 2020, 2021) for q in (1, 2, 3, 4)]
    games = [trap_game(i, f"s{i}", 900, i % 3 == 0, month=f"{2019 + i % 3}-05") for i in range(120)]
    written = generate_report(explorer, games, tables=tmp_path / "t", figures=tmp_path / "f")
    names = {path.name for path in written}
    assert {"lichess_rates.csv", "lichess_rates_by_speed.csv", "chesscom_rates.csv", "stafford-bg5.png"} <= names
    assert "englund.png" not in names  # nothing collected for it


def test_report_with_nothing_collected(tmp_path):
    assert generate_report([], [], tables=tmp_path / "t", figures=tmp_path / "f") == []


def test_cli_parses_its_options():
    args = build_parser().parse_args(["lichess", "--traps", "englund,legal", "--speeds", "blitz"])
    assert [trap.slug for trap in args.traps] == ["englund", "legal"] and args.speeds == ("blitz",)
    args = build_parser().parse_args(["chesscom", "--years", "2019-2021"])
    assert args.years == (2019, 2020, 2021)
    with pytest.raises(SystemExit):
        build_parser().parse_args(["lichess", "--traps", "nope"])
