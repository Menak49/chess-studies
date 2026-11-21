# trap-immunity

When an opening trap goes viral, does the pool learn to avoid it? If so, how
fast, and at which ratings?

The Stafford Gambit is the reference case. It was close to forgotten until IM
Eric Rosen built a series of videos around it from August 2020, and it then
became one of the most played traps online. If the pool learns, the share of
victims who take its bait should fall after 2020. The fall should come sooner
at the ratings where players watch that kind of content and meet the trap most
often.

## The traps

Each trap is pinned to one position, the *bait*: the setter has just made the
move that invites the blunder, and the victim is to move. The observation is
what the victim plays there.

| Slug | Bait reached after | Falling move | Popularised |
|---|---|---|---|
| `stafford-bg5` | 1.e4 e5 2.Nf3 Nf6 3.Nxe5 Nc6 4.Nxc6 dxc6 5.d3 Bc5 | 6.Bg5 | 2020-08 |
| `stafford-queen` | ... 6.Bg5 Nxe4 | 7.Bxd8 | 2020-08 |
| `englund` | 1.d4 e5 2.dxe5 Nc6 3.Nf3 Qe7 4.Bf4 Qb4+ 5.Bd2 Qxb2 | 6.Bc3 | |
| `fishing-pole` | 1.e4 e5 2.Nf3 Nc6 3.Bb5 Nf6 4.O-O Ng4 5.h3 h5 | 6.hxg4 | |
| `blackburne-shilling` | 1.e4 e5 2.Nf3 Nc6 3.Bc4 Nd4 4.Nxe5 Qg5 | 5.Nxf7 | |
| `legal` | 1.e4 e5 2.Nf3 d6 3.Bc4 Bg4 4.Nc3 g6 5.Nxe5 | 5...Bxd1 | |

Every falling move was checked with Stockfish 19 at depth 20. Each one loses at
least five pawns against the best move in the bait position, or allows mate. The
traps without a popularisation date serve as controls: their fall rate should
not show a break in 2020.

The 2020-08 date is when Rosen's first Stafford video came out, according to a
Lichess community blog. It is a secondary source, worth checking against the
video itself.

Positions are matched as positions. A game that reaches the bait by another move
order counts too, both in the explorer and in the chess.com crawl.

## Two sites, two methods

The two sites expose different things, so they are read differently. The
difference is part of the design, not an accident of convenience.

**Lichess: the opening explorer, a census.** `explorer.lichess.ovh` counts every
rated Lichess game reaching a position, by speed, by rating group and by month.
The study reads it over a grid of trap × quarter (2015Q1 to 2026Q3) × speed
(bullet, blitz, rapid) × rating group (the explorer's nine), with two requests
per cell:

- the position *before* the setter's move. The share of games continuing with
  the trap move is the trap's **adoption**: who sets it, and when;
- the bait position. The share continuing with the falling move is the
  **fall rate**.

No game is downloaded and no engine is run. The limit is that the explorer files
a game under the *average* rating of its two players, not the victim's.

**chess.com: following the setters, a sample.** chess.com has no search by
position, only each player's monthly archives. A trap appears in a tiny fraction
of games, so reading random players would cost thousands of archives per handful
of baits. The crawl instead runs in two modes:

- *discovery*: read one sampled month of an account met in the opponent graph.
  Every bait found there names its setter;
- *following*: read every sampled month of the year (February, May, August,
  November) for each setter found. Setters set their trap again and again, so
  one setter's archives hold dozens of baits, each with its own victim.

This gives the **victim's own rating**, which the explorer cannot. Three rules
keep the sample honest:

- **Setters are found within each year, never from today.** Following the
  players who set the Stafford in 2026 would only show those for whom it kept
  working, and would hide the decline the study looks for.
- **A setter counts for at most 10 games per (year, trap, victim band) cell**,
  both in the crawl's quotas and in the analysis, drawn at random. One prolific
  setter must not stand for a whole band.
- **Thematic tournaments are excluded.** They start from a position already set
  up, which nobody chose to play into.

The victims are, by construction, players who met a setter. That is exactly the
population the question is about: given that you face the trap, do you fall
into it?

## What a pool that learns looks like, and what else could look like it

A falling fall rate is the expected signature of learning, but it has two
impostors:

- **The setters change.** Early adopters are curious players setting the trap
  against anyone. Later adopters are specialists who may choose their victims
  differently. The Lichess adoption panel and the per-setter cap on chess.com
  are there to tell the two apart.
- **The victims change.** If the pool at a given rating changes (more new
  accounts, for instance), the fall rate moves without anyone learning anything.
  The control traps, which had no viral event, should show that kind of drift if
  it exists.

## Running it

From the repository root, with `PYTHONPATH="src;studies/trap-immunity/src"`
on Windows, or after `pip install -e .`:

```bash
# Lichess: needs a personal token, any token without scope
# (https://lichess.org/account/oauth/token), in an environment variable.
export LICHESS_TOKEN=lip_...
python -m trap_immunity.cli lichess                    # the whole grid
python -m trap_immunity.cli lichess --traps stafford-bg5 --speeds blitz

# chess.com: one year at a time or all of them
python -m trap_immunity.cli chesscom --years 2019-2022

python -m trap_immunity.cli report
```

All three commands resume where they stopped. The repository-wide rule still
holds: one Lichess job at a time.

Orders of magnitude:

- **Lichess.** The full grid is 6 traps × 47 quarters × 3 speeds × 9 rating
  groups, at most two requests per cell, so about 15,000 requests. Empty cells
  (a speed that did not exist yet, a trap nobody played) cost one request.
- **chess.com.** A trial on 2021 found 186 baits in 80 requests (45 seconds).
  Filling 60 games per (trap, victim band) cell takes about 1,500 to 2,000
  requests per year. Rare traps (`legal`, `fishing-pole`) may stay
  under-filled; a year stops after 1,500 requests without progress.

## Outputs

- `data/trap-immunity/raw/lichess/explorer_cells.jsonl`: one line per explorer
  cell, with the raw counts (including every move played at the bait), so any
  rate can be recomputed.
- `data/trap-immunity/raw/chesscom/trap_games_<year>.jsonl`: one line per bait
  reached, with the setter, the victim, both ratings, the victim's move and the
  result.
- `reports/tables/lichess_rates.csv`, `lichess_rates_by_speed.csv`,
  `chesscom_rates.csv`: adoption and fall rates with 95% Wilson intervals.
- `reports/figures/<trap>.png`: per trap, three panels on one time axis:
  Lichess adoption, Lichess fall rate, chess.com fall rate, by rating group.
