import pytest

from trap_immunity import config
from trap_immunity.config import period_of, quarters
from trap_immunity.traps import TRAPS, TRAPS_BY_SLUG, Trap, TrapDetector
from chesslab.settings import YearMonth

STAFFORD = TRAPS_BY_SLUG["stafford-bg5"]


def pgn(moves: str) -> str:
    return '[Event "x"]\n[Result "*"]\n\n' + moves + " *"


def test_every_trap_is_legal_and_unique():
    assert len({trap.bait_key for trap in TRAPS}) == len(TRAPS)
    assert len(TRAPS_BY_SLUG) == len(TRAPS)


def test_an_illegal_trap_is_refused():
    with pytest.raises(ValueError):
        Trap("bad", "bad", ("e4", "e5", "Ke3"), ("Kd4",))
    with pytest.raises(ValueError):
        Trap("bad", "bad", ("e4", "e5"), ("Qh8",))


def test_trap_sides_and_moves():
    assert STAFFORD.victim == "white" and STAFFORD.setter == "black"
    assert TRAPS_BY_SLUG["legal"].victim == "black"
    assert STAFFORD.setter_move == "Bc5"
    assert STAFFORD.parent_uci[-1] == "d2d3"
    assert STAFFORD.line_uci[-1] == "f8c5"


def test_castling_is_sent_the_standard_way():
    assert "e1g1" in TRAPS_BY_SLUG["fishing-pole"].line_uci


def test_detector_sees_a_fall_and_the_next_trap():
    moves = "1. e4 e5 2. Nf3 Nf6 3. Nxe5 Nc6 4. Nxc6 dxc6 5. d3 Bc5 6. Bg5 Nxe4 7. Bxd8 Bxf2+"
    moments = TrapDetector().scan(pgn(moves))
    assert [(m.trap.slug, m.victim_move, m.fell) for m in moments] == [
        ("stafford-bg5", "Bg5", True),
        ("stafford-queen", "Bxd8", True),
    ]


def test_detector_sees_an_avoided_trap():
    moves = "1. e4 e5 2. Nf3 Nf6 3. Nxe5 Nc6 4. Nxc6 dxc6 5. d3 Bc5 6. Be2 h5"
    (moment,) = TrapDetector().scan(pgn(moves))
    assert moment.fell is False and moment.victim_move == "Be2"


def test_detector_matches_transpositions():
    # 1.Nf3 Nf6 2.e4 e5 reaches the same position as 1.e4 e5 2.Nf3 Nf6.
    moves = "1. Nf3 Nf6 2. e4 e5 3. Nxe5 Nc6 4. Nxc6 dxc6 5. d3 Bc5 6. Bg5"
    (moment,) = TrapDetector().scan(pgn(moves))
    assert moment.trap is STAFFORD and moment.fell


def test_a_game_ending_at_the_bait_has_no_reply():
    moves = "1. e4 e5 2. Nf3 Nf6 3. Nxe5 Nc6 4. Nxc6 dxc6 5. d3 Bc5"
    (moment,) = TrapDetector().scan(pgn(moves))
    assert moment.victim_move is None and moment.fell is None


def test_an_unrelated_or_broken_game_finds_nothing():
    assert TrapDetector().scan(pgn("1. d4 d5 2. c4 e6 3. Nc3 Nf6")) == []
    assert TrapDetector().scan(pgn("1. e4 e5 2. Qxf7")) == []


def test_quarters_stop_at_the_last_complete_one():
    periods = quarters(2025, YearMonth(2026, 8))
    assert [p.label for p in periods] == ["2025Q1", "2025Q2", "2025Q3", "2025Q4", "2026Q1", "2026Q2"]
    assert periods[0].first == YearMonth(2025, 1) and periods[0].last == YearMonth(2025, 3)
    assert period_of(YearMonth(2020, 8)) == "2020Q3"


def test_chesscom_months_and_report_groups():
    assert config.chesscom_months(2026)[-1] <= config.LAST_MONTH
    assert config.report_group(999) == "<1200"
    assert config.report_group(1600) == "1600-1999"
    assert config.report_group(2700) == "2000+"
