from chesslab.http import ApiError
from chesslab.settings import YearMonth
from trap_immunity.config import Period
from trap_immunity.lichess_grid import GridCollector, TotalsCollector, cell_key, grid, total_grid, total_key
from trap_immunity.storage import KeyedJsonl
from trap_immunity.traps import TRAPS_BY_SLUG

STAFFORD = TRAPS_BY_SLUG["stafford"]
Q3 = Period("2020Q3", YearMonth(2020, 7), YearMonth(2020, 9))

PARENT = {
    "white": 60, "draws": 0, "black": 40,
    "moves": [
        {"san": "Bc5", "uci": "f8c5", "white": 30, "draws": 0, "black": 20},
        {"san": "h6", "uci": "h7h6", "white": 30, "draws": 0, "black": 20},
    ],
}
BAIT = {
    "white": 20, "draws": 2, "black": 28,
    "moves": [
        {"san": "Bg5", "uci": "c1g5", "white": 4, "draws": 0, "black": 16},
        {"san": "Be2", "uci": "f1e2", "white": 16, "draws": 2, "black": 12},
    ],
}
EMPTY = {"white": 0, "draws": 0, "black": 0, "moves": []}
START = {"white": 5000, "draws": 400, "black": 4600, "moves": []}


class FakeExplorer:
    """Answers by position: the parent and the bait of the 6.Bg5 trap."""

    def __init__(self, fail_first=0, empty=False):
        self.calls = []
        self.fail_first = fail_first
        self.empty = empty

    def get(self, path, *, params=None):
        self.calls.append(params)
        if self.fail_first:
            self.fail_first -= 1
            raise ApiError("HTTP 502")
        if self.empty:
            return EMPTY
        if "play" not in params:
            return START
        play = tuple(params["play"].split(","))
        if play == STAFFORD.parent_uci:
            return PARENT
        if play == STAFFORD.line_uci:
            return BAIT
        return EMPTY


def store(tmp_path):
    return KeyedJsonl(tmp_path / "cells.jsonl", cell_key)


def test_a_cell_keeps_the_raw_counts(tmp_path):
    cells = store(tmp_path)
    GridCollector(FakeExplorer(), cells).collect(grid([STAFFORD], [Q3], ["blitz"], [1200]))
    (row,) = cells.read_all()
    assert row["parent_games"] == 100 and row["setter_move_games"] == 50
    assert row["bait_games"] == 50
    assert row["bait_moves"] == {"Bg5": [4, 0, 16], "Be2": [16, 2, 12]}


def test_an_unreached_parent_saves_the_second_request(tmp_path):
    client = FakeExplorer(empty=True)
    cells = store(tmp_path)
    GridCollector(client, cells).collect(grid([STAFFORD], [Q3], ["blitz"], [0]))
    assert len(client.calls) == 1
    (row,) = cells.read_all()
    assert row["parent_games"] == 0 and row["bait_games"] == 0


def test_a_resumed_run_skips_stored_cells(tmp_path):
    cells = grid([STAFFORD], [Q3], ["blitz", "rapid"], [1200])
    GridCollector(FakeExplorer(), store(tmp_path)).collect(cells)
    client = FakeExplorer()
    stats = GridCollector(client, store(tmp_path)).collect(grid([STAFFORD], [Q3], ["blitz", "rapid"], [1200]))
    assert client.calls == [] and stats.cells_skipped == 2


def test_failures_are_skipped_then_stop_the_run(tmp_path):
    cells = grid([STAFFORD], [Q3], ["blitz"], [1000, 1200, 1400])
    stats = GridCollector(FakeExplorer(fail_first=1), store(tmp_path)).collect(cells)
    assert stats.failures == 1 and stats.cells_stored == 2

    many = grid([STAFFORD], [Q3], ["bullet"], [1000, 1200, 1400])
    stats = GridCollector(
        FakeExplorer(fail_first=10), store(tmp_path), max_consecutive_failures=2
    ).collect(many)
    assert stats.failures == 2 and stats.cells_stored == 0


def test_the_budget_is_respected(tmp_path):
    client = FakeExplorer()
    GridCollector(client, store(tmp_path), max_requests=4).collect(
        grid([STAFFORD], [Q3], ["blitz"], [1000, 1200, 1400])
    )
    assert len(client.calls) == 4


def test_totals_read_the_starting_position_once_per_slice(tmp_path):
    client = FakeExplorer()
    totals = KeyedJsonl(tmp_path / "totals.jsonl", total_key)
    stats = TotalsCollector(client, totals, max_requests=3).collect(
        total_grid([Q3], ["blitz", "rapid"], [1200, 1400])
    )
    assert len(client.calls) == 3 and stats.cells_stored == 3  # one request per slice
    assert all("play" not in params for params in client.calls)
    first = next(iter(totals.read_all()))
    assert first == {"period": "2020Q3", "speed": "blitz", "rating": 1200, "games": 10000}
