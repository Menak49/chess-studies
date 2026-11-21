import random

from chesslab.http import ApiError
from chesslab.settings import YearMonth
from chesslab.store import VisitedLog
from trap_immunity.chesscom_crawl import (
    AdopterCrawler,
    TrapTarget,
    open_store,
    trap_rows,
    victim_band,
)
from trap_immunity import config
from trap_immunity.traps import TRAPS_BY_SLUG, TrapDetector

STAFFORD_FALL = "1. e4 e5 2. Nf3 Nf6 3. Nxe5 Nc6 4. Nxc6 dxc6 5. d3 Bc5 6. Bg5 h6 7. Bh4"
STAFFORD_SAFE = "1. e4 e5 2. Nf3 Nf6 3. Nxe5 Nc6 4. Nxc6 dxc6 5. d3 Bc5 6. Be2 h5"
QUIET = "1. d4 d5 2. c4 e6 3. Nc3 Nf6"
MONTHS = config.chesscom_months(2020)


def game(gid, white, black, moves, *, white_rating=1000, black_rating=1100, **overrides):
    raw = {
        "uuid": gid,
        "url": f"https://example.invalid/{gid}",
        "rules": "chess",
        "rated": True,
        "time_class": "blitz",
        "time_control": "180",
        "end_time": 1,
        "pgn": f'[Event "Live Chess"]\n\n{moves} 0-1',
        "white": {"username": white, "rating": white_rating, "result": "resigned"},
        "black": {"username": black, "rating": black_rating, "result": "win"},
    }
    raw.update(overrides)
    return raw


class FakeArchives:
    def __init__(self, archives):
        self.archives = archives  # {(user, month): [games]}
        self.reads = []
        self.index_reads = []
        self.broken = set()

    def available_months(self, username):
        self.index_reads.append(username)
        if username in self.broken:
            raise ApiError("HTTP 502")
        return sorted({month for user, month in self.archives if user == username})

    def games(self, username, month):
        self.reads.append((username, month))
        return self.archives.get((username, month), [])


def world():
    """A seed whose one month shows a Stafford setter, who plays it every quarter."""
    archives = {("seed", MONTHS[0]): [
        game("g0", "seed", "staff", STAFFORD_FALL),
        game("q0", "seed", "friend", QUIET),
    ]}
    for m, month in enumerate(MONTHS):
        archives[("staff", month)] = [
            game(f"s{m}-{i}", f"victim{m}{i}", "staff", STAFFORD_FALL if i % 2 else STAFFORD_SAFE,
                 white_rating=600 + 200 * (i % 3))
            for i in range(6)
        ]
    archives[("seed", YearMonth(2019, 2))] = [game("old", "seed", "staff", STAFFORD_FALL)]
    return archives


def crawler(tmp_path, source, **kwargs):
    store = open_store_at(tmp_path)
    log = VisitedLog(tmp_path / "log.json")
    target = TrapTarget(per_cell=kwargs.pop("per_cell", 5), per_setter=kwargs.pop("per_setter", 3))
    return AdopterCrawler(
        source, store, 2020, target, log, rng=random.Random(1), **kwargs
    ), store


def open_store_at(tmp_path):
    return open_store(tmp_path / "trap_games_2020.jsonl")


# -- reading one game ----------------------------------------------------------


def test_trap_rows_describe_setter_victim_and_move():
    (row,) = trap_rows(game("g", "Alice", "Bob", STAFFORD_FALL), MONTHS[2], TrapDetector())
    assert row["trap"] == "stafford"
    assert (row["victim"], row["setter"]) == ("alice", "bob")
    assert (row["victim_rating"], row["setter_rating"]) == (1000, 1100)
    assert row["victim_move"] == "Bg5" and row["fell"] is True
    assert row["victim_result"] == "loss" and row["period"] == "2020Q3"


def test_trap_rows_reject_ineligible_games():
    detector = TrapDetector()
    themed = game("t", "a", "b", STAFFORD_FALL, initial_setup="r1bqkb1r/pppp1ppp/2n2n2/4N3/4P3/8/PPPP1PPP/RNBQKB1R w KQkq - 1 4")
    assert trap_rows(themed, MONTHS[0], detector) == []
    assert trap_rows(game("u", "a", "b", STAFFORD_FALL, rated=False), MONTHS[0], detector) == []
    assert trap_rows(game("d", "a", "b", STAFFORD_FALL, time_class="daily"), MONTHS[0], detector) == []
    assert trap_rows(game("q", "a", "b", QUIET), MONTHS[0], detector) == []


def test_victim_bands():
    assert victim_band(399) is None and victim_band(400) == 400
    assert victim_band(1399) == 1200 and victim_band(2400) is None


# -- the crawl -----------------------------------------------------------------


def test_a_setter_met_in_discovery_is_followed_over_the_year(tmp_path):
    source = FakeArchives(world())
    walk, store = crawler(tmp_path, source, max_requests=50)
    walk.crawl(["seed"])

    assert ("seed", MONTHS[0]) in source.reads
    assert ("seed", YearMonth(2019, 2)) not in source.reads  # another year
    assert all(("staff", month) in source.reads for month in MONTHS)
    rows = list(store.read_all())
    assert len(rows) == 1 + 6 * len(MONTHS)  # every bait found is stored
    assert {row["setter"] for row in rows} == {"staff"}
    assert walk.stats.setters_followed == 1


def test_one_setter_counts_only_up_to_the_cap(tmp_path):
    walk, _ = crawler(tmp_path, FakeArchives(world()), per_setter=2)
    walk.crawl(["seed"])
    # staff's victims fall in three bands (600, 800, 1000): two credited each.
    assert walk.stats.baits_credited == 3 * 2


def test_discovery_reads_a_single_month(tmp_path):
    archives = {("seed", month): [game(f"q{month}", "seed", "x", QUIET)] for month in MONTHS}
    source = FakeArchives(archives)
    walk, _ = crawler(tmp_path, source)
    walk.crawl(["seed"])
    assert len([read for read in source.reads if read[0] == "seed"]) == 1


def test_a_resumed_crawl_reads_nothing_twice(tmp_path):
    source = FakeArchives(world())
    walk, _ = crawler(tmp_path, source)
    walk.crawl(["seed"])
    reads = list(source.reads)

    again, _ = crawler(tmp_path, source)
    again.crawl(["seed"])
    assert source.reads == reads


def test_a_failing_account_is_skipped(tmp_path):
    source = FakeArchives(world())
    source.broken.add("seed")
    walk, _ = crawler(tmp_path, source)
    stats = walk.crawl(["seed"])
    assert stats.failures == 1 and source.reads == []


def test_the_traps_are_wired_to_the_target():
    target = TrapTarget(per_cell=1, per_setter=1)
    row = {"trap": "stafford", "victim_rating": 900, "setter": "s"}
    assert target.credit(row) and not target.credit({**row, "setter": "t"})
    assert target.trap_deficit("stafford") == len(target.cells) // len(TRAPS_BY_SLUG) - 1


def test_setters_of_traps_still_missing_games_come_first(tmp_path):
    walk, _ = crawler(tmp_path, FakeArchives({}), per_cell=2, per_setter=2)
    for i in range(2 * 10):  # fill every Stafford band
        walk._target.credit({"trap": "stafford", "victim_rating": 400 + 100 * i, "setter": f"x{i}"})
    walk._sighting({"trap": "stafford", "setter": "busy"})
    walk._sighting({"trap": "stafford", "setter": "busy"})
    walk._sighting({"trap": "englund", "setter": "rare"})
    assert walk._best_candidate() == "rare"
    assert walk._best_candidate() is None  # Stafford is full: not worth following
