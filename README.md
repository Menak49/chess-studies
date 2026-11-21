# chess-studies

Measurement studies of online chess, run on public data from chess.com and Lichess.

Each study asks a question where the obvious number can mislead: a rating that
stays put while the pool around it drifts, a win that says nothing about the
position on the board, a correlation that only reflects who chose to play. The
studies answer these by going back to the games themselves. They collect them
with a sampling design built for the question, and re-analyse every move with
one fixed engine instead of trusting the sites' own figures.

## Studies

| Study | Question | Findings |
|---|---|---|
| [elo-drift](studies/elo-drift/README.md) | What playing strength does a rating buy, year by year from 2014 to 2026, on chess.com and Lichess? How do the four big online pools convert into one another in 2026? | [findings.md](studies/elo-drift/reports/findings.md) |

## How the repository is organised

The studies share infrastructure and nothing else.

```
src/chesslab/              shared, study-independent
  settings.py              paths, API settings, and the engine settings
  http.py                  retrying, throttled HTTP client both sites share
  chesscom/                chess.com client and endpoint wrappers
  lichess/                 Lichess client, game export and opening explorer
  pgn.py                   reading the moves of a PGN without a full parse
  records.py               GameRecord (one game, two sides) and RatingSnapshot
  store.py                 append-only, resumable JSONL stores
  engine/                  UCI analysis, accuracy/ACPL scoring, parallel runner
studies/<name>/
  src/<name>/              the study: its config, how it samples, how it analyses
  tests/
  reports/                 its deliverable: findings.md, tables, figures
  README.md                its question, method and results
data/<name>/               each study's collected and processed data (not tracked)
tools/stockfish/           the engine binary (not tracked)
tests/                     tests of the shared package
```

What belongs where:

- **`chesslab` knows how, a study decides what.** Talking to an API, storing a
  game or scoring a move is shared. Which accounts to visit, which games to keep,
  the quotas, the strata and the inclusion rules all belong to the study, in its
  own `config.py`.
- **The engine is the common instrument.** Its depth, the opening plies skipped
  and the binary are set once in `chesslab.settings`. Scores from different
  studies are comparable, and reusable from one study to another, only because
  they come from the same instrument. Changing these settings changes every
  study's results.
- **Each study has its own sample.** A game collected by one study can save
  another a download or an engine pass, but it must never enter the other study's
  sample just because it is already on disk: it carries the first study's
  selection with it.

## Setup

```bash
pip install -r requirements.txt
pip install -e .                  # installs chesslab and every study package
```

Without installing, put the shared package and the study on the path, for
instance `PYTHONPATH="src;studies/elo-drift/src"` on Windows (`:` instead of `;`
elsewhere).

The engine is not vendored. Download a Stockfish build and put the binary at
`tools/stockfish/stockfish.exe`. Any recent version works, as long as one version
is used for everything that is compared. The studies so far used Stockfish 19.

Each study is run through its own command line, described in its README:

```bash
python -m elo_drift.cli collect | survey | evaluate | report
```

## Rules that hold for every study

- **One Lichess job at a time, across all studies.** Lichess serves one request at
  a time per client and locks an address out of its streaming endpoints for about
  an hour when a stream is abandoned. Never run two Lichess crawls at once, and
  never kill one mid-request.
- **Same engine, same depth.** Re-analysing part of a corpus with another Stockfish
  version or depth makes its scores incomparable with the rest.
- **Published results are tagged.** Before changing shared code in a way that
  could move an existing study's numbers, check that its `report` still
  reproduces its tracked tables. The state of elo-drift as first published is
  tagged `elo-drift-v1.0`.

## Adding a study

1. Create `studies/<name>/src/<name>/` with a `config.py` holding the protocol, and
   a `cli.py` that drives collection and analysis.
2. Write data under `data/<name>/` (`chesslab.settings.DATA_ROOT / "<name>"`).
3. Add `studies/<name>/src` to `where` and `pythonpath`, and
   `studies/<name>/tests` to `testpaths`, in `pyproject.toml`.
4. Add a row to the table above once the study has findings.

## Testing

```bash
python -m pytest
```

The suite is offline: the APIs are faked and no engine is started.
