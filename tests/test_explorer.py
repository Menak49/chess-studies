import pytest

from chesslab import settings
from chesslab.lichess.explorer import (
    ExplorerClient,
    MissingTokenError,
    fetch_position,
    parse_position,
)
from chesslab.settings import YearMonth

PAYLOAD = {
    "white": 120,
    "draws": 10,
    "black": 70,
    "moves": [
        {"uci": "f1e2", "san": "Be2", "white": 80, "draws": 8, "black": 32, "averageRating": 1500},
        {"uci": "c1g5", "san": "Bg5", "white": 40, "draws": 2, "black": 38, "averageRating": 1400},
    ],
    "topGames": [],
    "opening": {"eco": "C42", "name": "Russian Game: Stafford Gambit"},
}


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, path, *, params=None):
        self.calls.append((path, params))
        return self.payload


def test_parse_position_counts_games_and_moves():
    position = parse_position(PAYLOAD)
    assert position.games == 200
    assert position.move("Bg5").games == 80
    assert position.move("Bg5+").black == 38  # marks do not matter
    assert position.move("h3") is None


def test_fetch_position_asks_for_one_cell():
    client = FakeClient(PAYLOAD)
    fetch_position(
        client, ["e2e4", "e7e5"], speeds=["blitz"], ratings=[1200],
        since=YearMonth(2020, 7), until=YearMonth(2020, 9),
    )
    path, params = client.calls[0]
    assert path == "/lichess"
    assert params["play"] == "e2e4,e7e5"
    assert params["speeds"] == "blitz"
    assert params["ratings"] == "1200"
    assert (params["since"], params["until"]) == ("2020-07", "2020-09")
    assert params["topGames"] == 0 and params["recentGames"] == 0


def test_client_requires_a_token(monkeypatch):
    monkeypatch.delenv(settings.LICHESS_TOKEN_ENV, raising=False)
    with pytest.raises(MissingTokenError):
        ExplorerClient.from_environment()


def test_client_sends_the_token(monkeypatch):
    monkeypatch.setenv(settings.LICHESS_TOKEN_ENV, "lip_secret")
    with ExplorerClient.from_environment() as client:
        assert client._session.headers["Authorization"] == "Bearer lip_secret"
