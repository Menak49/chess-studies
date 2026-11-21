"""Command line entry point of the trap-immunity study.

    classify  Stockfish            -> studies/trap-immunity/fall_moves.json (which replies fall)
    lichess   explorer.lichess.ovh -> data/trap-immunity/raw/lichess/explorer_cells.jsonl
    lichess-totals                 -> data/trap-immunity/raw/lichess/explorer_totals.jsonl (all games)
    chesscom  api.chess.com        -> data/trap-immunity/raw/chesscom/trap_games_<year>.jsonl
    report    both                 -> studies/trap-immunity/reports/ (tables, figures)

Collection commands resume where the previous run stopped. Only `classify`
needs the engine, once.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from pathlib import Path

from chesslab.settings import ENGINE_PATH
from trap_immunity import config
from trap_immunity.traps import TRAPS, TRAPS_BY_SLUG


def configure_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def parse_traps(text: str):
    if text == "all":
        return TRAPS
    slugs = [slug.strip() for slug in text.split(",") if slug.strip()]
    unknown = [slug for slug in slugs if slug not in TRAPS_BY_SLUG]
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown traps {unknown}; known: {sorted(TRAPS_BY_SLUG)}")
    return tuple(TRAPS_BY_SLUG[slug] for slug in slugs)


def parse_speeds(text: str) -> tuple[str, ...]:
    speeds = tuple(speed.strip() for speed in text.split(",") if speed.strip())
    unknown = set(speeds) - set(config.SPEEDS)
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown speeds {sorted(unknown)}")
    return speeds


def parse_years(text: str) -> tuple[int, ...]:
    years: set[int] = set()
    for part in text.split(","):
        if "-" in part:
            low, high = (int(bound) for bound in part.split("-"))
            years.update(range(low, high + 1))
        elif part.strip():
            years.add(int(part))
    unknown = years - set(config.CHESSCOM_YEARS)
    if unknown:
        raise argparse.ArgumentTypeError(f"outside the study period: {sorted(unknown)}")
    return tuple(sorted(years))


def run_classify(args: argparse.Namespace) -> int:
    from trap_immunity.classify import classify_traps, write_classification
    from trap_immunity.traps import CANDIDATES

    path = write_classification(classify_traps(CANDIDATES, args.engine, args.depth))
    logging.getLogger("classify").info("wrote %s", path)
    return 0


def run_lichess(args: argparse.Namespace) -> int:
    from chesslab.lichess.explorer import ExplorerClient
    from trap_immunity.lichess_grid import GridCollector, grid, open_store

    logger = logging.getLogger("lichess")
    store = open_store()
    cells = list(grid(args.traps, speeds=args.speeds))
    logger.info("%d cells in the grid, %d already stored", len(cells), len(store))
    with ExplorerClient.from_environment(min_interval_seconds=args.min_interval) as client:
        stats = GridCollector(client, store, max_requests=args.max_requests).collect(cells)
    logger.info("done: %s", vars(stats))
    return 0


def run_lichess_totals(args: argparse.Namespace) -> int:
    from chesslab.lichess.explorer import ExplorerClient
    from trap_immunity.lichess_grid import TotalsCollector, open_totals_store, total_grid

    logger = logging.getLogger("lichess-totals")
    store = open_totals_store()
    cells = list(total_grid(speeds=args.speeds))
    logger.info("%d slices, %d already stored", len(cells), len(store))
    with ExplorerClient.from_environment(min_interval_seconds=args.min_interval) as client:
        stats = TotalsCollector(client, store, max_requests=args.max_requests).collect(cells)
    logger.info("done: %s", vars(stats))
    return 0


def run_chesscom(args: argparse.Namespace) -> int:
    from chesslab.chesscom import ChessComClient
    from chesslab.store import VisitedLog
    from trap_immunity.chesscom_crawl import AdopterCrawler, ChessComArchives, TrapTarget, open_store
    from trap_immunity.chesscom_seeds import load_seeds

    logger = logging.getLogger("chesscom")
    with ChessComClient(min_interval_seconds=args.min_interval) as client:
        for year in args.years:
            store = open_store(config.trap_games_path(year))
            log = VisitedLog(config.read_archives_path(year))
            target = TrapTarget(args.traps, per_cell=args.per_cell)
            crawler = AdopterCrawler(
                ChessComArchives(client), store, year, target, log,
                traps=args.traps, rng=random.Random(args.seed + year),
                max_requests=args.max_requests,
            )
            logger.info("crawling %d: %d trap games stored so far", year, len(store))
            stats = crawler.crawl(load_seeds(client, year, config.seed_cache_dir()))
            logger.info("%d done: %s, coverage %s", year, stats.as_dict(), target.progress)
            config.crawl_stats_path(year).write_text(
                json.dumps({**stats.as_dict(), "coverage": target.progress}, indent=2),
                encoding="utf-8",
            )
    return 0


def run_report(args: argparse.Namespace) -> int:
    from trap_immunity.report import generate_report

    for path in generate_report():
        logging.getLogger("report").info("wrote %s", path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trap-immunity", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-v", "--verbose", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)

    classify = commands.add_parser("classify", help="let Stockfish decide which replies fall")
    classify.add_argument("--engine", type=Path, default=ENGINE_PATH)
    classify.add_argument("--depth", type=int, default=config.CLASSIFY_DEPTH)
    classify.set_defaults(handler=run_classify)

    lichess = commands.add_parser("lichess", help="read the explorer grid (needs $LICHESS_TOKEN)")
    lichess.add_argument("--traps", type=parse_traps, default=TRAPS, help="comma-separated slugs, or all")
    lichess.add_argument("--speeds", type=parse_speeds, default=config.SPEEDS)
    lichess.add_argument("--max-requests", type=int, default=20000)
    lichess.add_argument("--min-interval", type=float, default=0.5,
                         help="seconds between two explorer requests")
    lichess.set_defaults(handler=run_lichess)

    totals = commands.add_parser("lichess-totals",
                                 help="count all games per quarter, speed and rating (needs $LICHESS_TOKEN)")
    totals.add_argument("--speeds", type=parse_speeds, default=config.SPEEDS)
    totals.add_argument("--max-requests", type=int, default=2000)
    totals.add_argument("--min-interval", type=float, default=0.5,
                        help="seconds between two explorer requests")
    totals.set_defaults(handler=run_lichess_totals)

    chesscom = commands.add_parser("chesscom", help="follow trap setters through the archives")
    chesscom.add_argument("--years", type=parse_years, default=config.CHESSCOM_YEARS,
                          help="e.g. 2018-2023 or 2019,2021 (default: all)")
    chesscom.add_argument("--traps", type=parse_traps, default=TRAPS)
    chesscom.add_argument("--per-cell", type=int, default=config.TRAP_GAMES_PER_CELL,
                          help="trap games wanted per (trap, 200-point victim band) and year")
    chesscom.add_argument("--max-requests", type=int, default=5000, help="per year")
    chesscom.add_argument("--min-interval", type=float, default=0.0)
    chesscom.add_argument("--seed", type=int, default=20202026)
    chesscom.set_defaults(handler=run_chesscom)

    report = commands.add_parser("report", help="write the tables and figures")
    report.set_defaults(handler=run_report)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(args.verbose)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
