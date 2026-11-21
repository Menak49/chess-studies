"""Which victim moves count as falling into a trap, decided by the engine.

A trap has worked when the victim's move leaves the setter with a clear
advantage: at least `FALL_THRESHOLD_CP` centipawns by Stockfish's evaluation.
The bait position is the same in every game that reaches it, so evaluating
every legal reply there once is the same as evaluating each game's position
after the victim's move, at the cost of one analysis per trap.

One rule makes a trap admissible: with the victim's best reply, the setter must
stay below the threshold. A bait the setter already wins whatever the victim
plays is a lost position, not a trap, and every move there would "fall".

The result is written to `fall_moves.json`, tracked with the study, so that the
collection and the analysis never need the engine and a reader can check every
classification.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable

import chess
import chess.engine

from trap_immunity import config

logger = logging.getLogger(__name__)

MATE_CP = 10_000


def classify_bait(board: chess.Board, engine: chess.engine.SimpleEngine, depth: int) -> dict:
    """Evaluate every legal victim reply, from the setter's point of view."""
    setter = not board.turn
    replies = engine.analyse(
        board, chess.engine.Limit(depth=depth), multipv=board.legal_moves.count()
    )
    moves: dict[str, int] = {}
    for info in replies:
        move = info["pv"][0]
        score = info["score"].pov(setter).score(mate_score=MATE_CP)
        moves[board.san(move).rstrip("+#")] = int(score)
    return classification(moves)


def classification(moves: dict[str, int], threshold: int = config.FALL_THRESHOLD_CP) -> dict:
    """Falls and admissibility from each reply's evaluation for the setter."""
    best_for_victim = min(moves.values())
    return {
        "setter_cp_after_best_reply": best_for_victim,
        "admissible": best_for_victim < threshold,
        "falls": sorted(san for san, cp in moves.items() if cp >= threshold),
        "setter_cp_by_reply": dict(sorted(moves.items(), key=lambda item: item[1])),
    }


def classify_traps(traps: Iterable, engine_path: Path, depth: int = config.CLASSIFY_DEPTH) -> dict:
    with chess.engine.SimpleEngine.popen_uci(str(engine_path)) as engine:
        name = engine.id.get("name", "unknown engine")
        result = {
            "engine": name,
            "depth": depth,
            "threshold_cp": config.FALL_THRESHOLD_CP,
            "traps": {},
        }
        for trap in traps:
            entry = classify_bait(trap.bait_board, engine, depth)
            result["traps"][trap.slug] = entry
            logger.info(
                "%s: %s, falls %s (setter %+d after the best reply)",
                trap.slug, "admissible" if entry["admissible"] else "NOT admissible",
                entry["falls"], entry["setter_cp_after_best_reply"],
            )
    return result


def write_classification(result: dict, path: Path = config.FALL_MOVES_PATH) -> Path:
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_classification(path: Path = config.FALL_MOVES_PATH) -> dict:
    if not path.exists():
        return {"traps": {}}
    return json.loads(path.read_text(encoding="utf-8"))
