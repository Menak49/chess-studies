# trap-immunity

When an opening trap goes viral, does the pool learn to avoid it? If so, how
fast, and at which ratings?

The study covers 2018 to 2025: two years before the 2020 chess boom and the
first viral traps, five years after. Two kinds of event are compared:

- **A datable video.** IM Eric Rosen's Stafford Gambit video came out on
  2020-08-01 and turned a forgotten gambit into one of the most played traps
  online. His Englund Gambit trap followed on 2020-11-18, and the Fishing Pole
  appeared in his Ruy Lopez traps video of 2021-06-25.
- **The 2020 boom itself** (lockdowns from March, *The Queen's Gambit* in late
  October). It is a popularisation event for every trap: millions of new
  players met the classic traps through the same videos and courses. Traps that
  no single video made famous are dated by the boom alone.

If the pool learns, the share of victims who take the bait should fall after
the event. It should fall sooner at the ratings where players watch that kind
of content and meet the trap most often.

## What falling into a trap means

Each trap is pinned to one position, the *bait*: the setter has just made the
move that invites the blunder, and the victim is to move. The observation is
what the victim plays there.

**A trap has worked when the victim's move leaves the setter at least two pawns
ahead**, by Stockfish 19's evaluation at depth 20. The bait position is the same
in every game that reaches it, so evaluating each legal reply once is the same as
evaluating each game's position after the victim's move, for one analysis per
trap instead of one per game. `python -m trap_immunity.cli classify` runs it and
writes [fall_moves.json](fall_moves.json), with the evaluation of every reply,
so each classification can be checked.

Two consequences of that definition:

- **A fall is any losing reply, not only the textbook blunder.** In the Stafford
  bait, 6.Bg5 is the move the videos show, but 6.Qh5 or 6.f4 lose just as surely.
  The study reports both the fall rate (any reply worth two pawns to the setter)
  and the key fall rate (the textbook move alone). Learning one move and learning
  to play the position are not the same thing.
- **A candidate is followed only if the victim can escape.** If the setter is
  already two pawns up after the victim's best reply, the bait is a lost
  position, not a trap. Two candidates were dropped that way: Legal's mate
  (5.Nxe5 is already +2.2 for White after 4...g6) and the Stafford's 7.Bxd8
  (6...Nxe4 already leaves Black +5.7).

The engine depth here (20) is deeper than the repository's accuracy depth (12).
It is run once per trap rather than on every move of thousands of games, and a
trap often only works because of a tactic several moves deep.

## The traps

| Slug | Bait reached after | Textbook blunder | Event |
|---|---|---|---|
| `stafford` | 1.e4 e5 2.Nf3 Nf6 3.Nxe5 Nc6 4.Nxc6 dxc6 5.d3 Bc5 | 6.Bg5 | video, 2020-08 |
| `englund-rosen` | 1.d4 e5 2.dxe5 Bc5 3.Nf3 d6 4.exd6 Ne7 | 5.dxe7 | video, 2020-11 |
| `fishing-pole` | 1.e4 e5 2.Nf3 Nc6 3.Bb5 Nf6 4.O-O Ng4 5.h3 h5 | 6.hxg4 | video, 2021-06 |
| `englund` | 1.d4 e5 2.dxe5 Nc6 3.Nf3 Qe7 4.Bf4 Qb4+ 5.Bd2 Qxb2 | 6.Bc3 | 2020 boom |
| `blackburne-shilling` | 1.e4 e5 2.Nf3 Nc6 3.Bc4 Nd4 4.Nxe5 Qg5 | 5.Nxf7 | 2020 boom |
| `scholars-mate` | 1.e4 e5 2.Bc4 Nc6 3.Qh5 | 3...Nf6 | 2020 boom |
| `noahs-ark` | 1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 d6 5.d4 b5 6.Bb3 Nxd4 7.Nxd4 exd4 | 8.Qxd4 | 2020 boom |
| `siberian` | 1.e4 c5 2.d4 cxd4 3.c3 dxc3 4.Nxc3 Nc6 5.Nf3 e6 6.Bc4 Qc7 7.O-O Nf6 8.Qe2 Ng4 | 9.h3 | 2020 boom |
| `caro-kann-smothered` | 1.e4 c6 2.d4 d5 3.Nc3 dxe4 4.Nxe4 Nd7 5.Qe2 | 5...Ngf6 | 2020 boom |
| `kieninger` | 1.d4 Nf6 2.c4 e5 3.dxe5 Ng4 4.Nf3 Nc6 5.Bf4 Bb4+ 6.Nbd2 Qe7 7.a3 Ngxe5 | 8.axb4 | 2020 boom |
| `lasker` | 1.d4 d5 2.c4 e5 3.dxe5 d4 4.e3 Bb4+ 5.Bd2 dxe3 | 6.Bxb4 | 2020 boom |

In every case the engine classifies the textbook blunder as a fall, which a
test checks.

The video dates were read from each video's YouTube page (`uploadDate`):

- *Beating Everyone with the Same Opening Trap (Stafford Gambit)*, Eric Rosen,
  2020-08-01.
- *EVERYONE falls for this NEW opening trap*, Eric Rosen, 2020-11-18. This is
  a newer Englund line than the classic 6.Bc3. The moves were taken from a
  Listudy study of the video.
- *Tricks & Traps Everyone Should Know in the Ruy Lopez*, Eric Rosen with Anna
  Cramling, 2021-06-25. The Fishing Pole is one trap among several there, so
  this event is weaker than the other two.

Positions are matched as positions. A game that reaches the bait by another move
order counts too, both in the explorer and in the chess.com crawl.

## Two sites, two methods

The two sites expose different things, so they are read differently. The
difference is part of the design, not an accident of convenience.

**Lichess: the opening explorer, a census.** `explorer.lichess.ovh` counts every
rated Lichess game reaching a position, by speed, by rating group and by month.
The study reads it over a grid of trap × quarter (2018Q1 to 2025Q4) × speed
(bullet, blitz, rapid) × rating group (the explorer's nine), with two requests
per cell:

- the position *before* the setter's move. The share of games continuing with
  the trap move is the trap's **adoption**: who sets it, and when;
- the bait position. Every reply is stored with its results (white wins, draws,
  black wins), and the falls are counted at analysis time. Changing the
  threshold therefore never means collecting again.

A third, much smaller grid reads the starting position once per quarter × speed
× rating group (864 requests). Its count is every rated game of that slice, and
dividing a trap's baits by it gives the trap's **frequency**: games reaching the
bait per 10,000 games. The adoption says whether those who can set the trap do;
the frequency also moves with the opening's popularity, and says how often a
player meets the trap at all.

No game is downloaded. The limit is that the explorer files a game under the
*average* rating of its two players, not the victim's.

chess.com has no such count. Its crawl follows setters on purpose, so the share
of baits in the games it reads says more about the method than about the pool,
and the frequency is only reported for Lichess.

**chess.com: following the setters, a sample.** chess.com has no search by
position, only each player's monthly archives. A trap appears in a tiny fraction
of games, so reading random players would cost thousands of archives per handful
of baits. The crawl instead runs in two modes:

- *discovery*: read one sampled month of an account met in the opponent graph.
  Every bait found there names its setter;
- *following*: read every sampled month of the year (February, May, August,
  November) for a setter. Setters set their trap again and again, so one
  setter's archives hold dozens of baits, each with its own victim.

Setters are followed in order of what they bring: their sightings of each trap,
weighted by the share of that trap's quota still missing. Without the weight,
Scholar's mate, which is set in a fair share of all 1.e4 e5 games, would take
the whole budget long after its cells were full.

This gives the **victim's own rating**, which the explorer cannot. Three rules
keep the sample honest:

- **Setters are found within each year, never from today.** Following the
  players who set the Stafford in 2025 would only show those for whom it kept
  working, and would hide the decline the study looks for.
- **A setter counts for at most 10 games per (year, trap, victim band) cell**,
  both in the crawl's quotas and in the analysis, drawn at random. One prolific
  setter must not stand for a whole band.
- **Thematic tournaments are excluded.** They start from a position already set
  up, which nobody chose to play into.

The victims are, by construction, players who met a setter. That is exactly the
population the question is about: given that you face the trap, do you fall
into it?

**Victims are followed from 400 to 1799**, in 200-point bands. The 2021 trial
found about 3,000 baits below 1500, 47 at 1500-1799 and 4 above: these traps are
set against weak players, and bands above 1800 would never fill. Baits met above
the ceiling are stored but left out of the analysis, so the chess.com
`1600-1999` group only holds 1600-1799. The Lichess explorer keeps its whole
scale: its ratings run higher than chess.com's and file a game under the average
of both players, so a Lichess 1600 still covers much of the trap's audience.

**Rare traps are dropped, not forced.** A trap is reported for a site only once
300 baits were reached there in total. `coverage.csv` lists every trap and site
with its count and whether it made the cut.

## What a pool that learns looks like, and what else could look like it

A falling fall rate is the expected signature of learning, but it has two
impostors:

- **The setters change.** Early adopters are curious players setting the trap
  against anyone. Later adopters are specialists who may choose their victims
  differently. The Lichess adoption panel and the per-setter cap on chess.com
  are there to tell the two apart.
- **The victims change.** The boom brought millions of beginners, so the pool at
  a given rating was not the same before and after it. Traps dated by a video
  can be compared with the boom-only traps, and the Stafford's video came five
  months after the boom began.

The before/after table compares the fall rate up to each trap's event with the
fall rate from 12 months after it. The months in between are left out while the
news was spreading.

## Running it

From the repository root, with `PYTHONPATH="src;studies/trap-immunity/src"` on
Windows, or after `pip install -e .`.

The Lichess explorer needs a personal token: any token, without a scope, from
https://lichess.org/account/oauth/token. Copy `.env.example` to `.env` at the
repository root and put it after `LICHESS_TOKEN=`. The `.env` file is ignored by
git, and a variable set in the environment takes precedence over it.

```bash
python -m trap_immunity.cli classify                   # only if the traps or the threshold change
python -m trap_immunity.cli lichess                    # the whole grid
python -m trap_immunity.cli lichess --traps stafford --speeds blitz
python -m trap_immunity.cli lichess-totals             # all games per slice, for the frequency
python -m trap_immunity.cli chesscom --years 2018-2025
python -m trap_immunity.cli report
```

The collection commands resume where they stopped. The repository-wide rule
still holds: one Lichess job at a time.

Orders of magnitude:

- **Lichess.** 11 traps × 32 quarters × 3 speeds × 9 rating groups, at most two
  requests per cell: about 19,000 requests. Empty cells (a trap nobody played at
  that level) cost one. The totals add 864 requests, about ten minutes.
- **chess.com.** A trial on 2021 found about 3,000 baits in 240 requests (four
  minutes), although most of them were Scholar's mate. Filling 60 games per
  (trap, victim band) cell takes thousands of requests per year. Rare traps
  (Siberian, Kieninger, Lasker, Noah's Ark) will probably stay under-filled and
  be dropped. A year stops after 1,500 requests without progress.

## Outputs

- `data/trap-immunity/raw/lichess/explorer_cells.jsonl`: one line per explorer
  cell, with every reply played at the bait and its results.
- `data/trap-immunity/raw/lichess/explorer_totals.jsonl`: one line per quarter,
  speed and rating group, with the number of games of that slice.
- `data/trap-immunity/raw/chesscom/trap_games_<year>.jsonl`: one line per bait
  reached, with the setter, the victim, both ratings, the victim's move and the
  result.
- `reports/tables/coverage.csv`: baits per trap and site, and which are
  reported.
- `reports/tables/lichess_rates.csv`, `lichess_rates_by_speed.csv`: frequency
  per 10,000 games, adoption, fall rate, key fall rate and the setter's score after a fall, by quarter and
  rating group, with 95% Wilson intervals.
- `reports/tables/chesscom_rates.csv`: fall and key fall rates by year and
  victim rating group, with the number of setters and the largest setter's
  share.
- `reports/tables/before_after.csv`: the fall rate before each trap's event and
  from 12 months after it, with the difference and its 95% interval.
- `reports/figures/<trap>.png`: per trap, four panels on one time axis:
  Lichess frequency, Lichess adoption, Lichess fall rate, chess.com fall rate,
  by rating group.
  The 2020 boom is shaded and the video date, if any, is marked.
