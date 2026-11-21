from chesslab.pgn import normalise_san, san_moves

CHESSCOM_PGN = """[Event "Live Chess"]
[Site "Chess.com"]
[Result "0-1"]

1. e4 {[%clk 0:04:59.9]} 1... e5 {[%clk 0:04:58.1]} 2. Nf3 {[%clk 0:04:57]} 2... Nf6 {[%clk 0:04:55.2]} 3. Nxe5 {[%clk 0:04:50]} 3... Nc6 {[%clk 0:04:49.9]} 4. Nxc6 {[%clk 0:04:40]} 4... dxc6 {[%clk 0:04:39]} 0-1
"""

LICHESS_PGN = """[Event "Rated Blitz game"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Nd4 4. Nxe5 Qg5 5. Bxf7+ Ke7 1-0"""


def test_reads_chesscom_movetext_with_clocks():
    assert san_moves(CHESSCOM_PGN) == ["e4", "e5", "Nf3", "Nf6", "Nxe5", "Nc6", "Nxc6", "dxc6"]


def test_reads_lichess_movetext_and_strips_checks():
    assert san_moves(LICHESS_PGN) == [
        "e4", "e5", "Nf3", "Nc6", "Bc4", "Nd4", "Nxe5", "Qg5", "Bxf7", "Ke7",
    ]


def test_limit_stops_early():
    assert san_moves(LICHESS_PGN, limit=3) == ["e4", "e5", "Nf3"]


def test_bare_movetext_and_glued_move_numbers():
    assert san_moves("1.e4 e5 2.Nf3 $1 Nc6 *") == ["e4", "e5", "Nf3", "Nc6"]


def test_headers_without_moves_give_nothing():
    assert san_moves('[Event "x"]\n[Result "*"]\n') == []


def test_normalise_san_drops_marks_only():
    assert normalise_san("Qxf7#") == "Qxf7"
    assert normalise_san("O-O+!?") == "O-O"
    assert normalise_san("e8=Q+") == "e8=Q"
