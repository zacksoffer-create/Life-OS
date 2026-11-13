# Rolling 10

Fantasy basketball numbers for a season-long, head-to-head points keeper league: every NBA regular-season game since
2017-18, scored with the league's formula, with rolling windows, fantasy points per minute and box-score advanced stats.
The output is one phone page.

**On your phone:** https://zacksoffer-create.github.io/Life-OS/fantasy/ (Safari, then Share > Add to Home Screen).

## Young players

**https://zacksoffer-create.github.io/Life-OS/fantasy/young/**, refreshed every morning with the live page. Every
player in his first three seasons, with:
- **Starter odds and star odds:** the chance of a top-100 or a top-30 fantasy season in years 3 to 5, from a model
  trained on every rookie class since 2002-03 (box scores back to 2001-02, scored with the league's formula, each
  season ranked on its own so eras compare fairly). One model reads a first season, one reads the first two.
- **His rolling-10 arc** (FP per minute, FP/G and minutes across his career), what's moving his odds, and where he
  stands against past players at the same point.
- **The five closest past players** by early profile, and what each became.

What the research behind it found: the year-2 average carries most of the signal. On top of it, a rolling-10 FP per
minute that keeps climbing, producing efficiently on limited minutes, the year 1 to year 2 jump and youth predict a
better career; hot 10-game stretches, finishing strong and consistency don't. Out of sample, the two-season model
separates future starters from the rest with an AUC of 0.88 (stars 0.94), and when it says 90%+, 96% did.

Ages come from `seasons/birthdates.json` (fetched once from ESPN: Actions tab > Rolling 10 data > Run workflow >
birthdates; the daily job fills in new rookies). Code: `hoops/young.py`, page `web/young.html`.

## League history and finished seasons

**History:** https://zacksoffer-create.github.io/Life-OS/fantasy/history/. Every season the league has played on ESPN
(2019-20 on), together:
- **Managers:** champions, every manager's finish and record each season, and the all-time table (titles, playoffs,
  average finish, all-play record and luck). Managers are followed by an opaque owner key from ESPN, never a name, and
  shown under their latest team name.
- **Rivals:** any manager's record against each other manager, regular season and playoffs.
- **Draft:** which rounds produce value, how keepers paid off by the round they cost, who drafts best, the most-kept
  players, and the best and worst picks.
- **Lessons:** three tests on every NBA season since 2017-18: what carries over from season to season (FP per minute
  far more than minutes), what predicts the next 10 games (the season so far beats L10; about 80/20 is best), and how
  much of a hot streak lasts (minutes-driven streaks keep about twice as much as per-minute ones).

**Each season:** https://zacksoffer-create.github.io/Life-OS/fantasy/2025-26/ (and 2024-25 back to 2019-20, from the
season picker). A finished season is its own page and never needs refreshing. Each season is scored with that
season's own league settings, read from the import. It has four tabs:

- **Players:** every player's whole season. The board has Total FP, FP/G, FP per minute, best 10-game stretch, floor
  and ceiling games, how much his games swing, and games missed. A player's card adds his rolling-10 arc with the hot
  and cold stretches marked, month by month, week by week, and which fantasy teams had him and how many of his points
  they started or benched.
- **Weeks:** the league's 19 matchup weeks (16 regular season, then playoff rounds). Each week's card has every
  matchup, the top players, points left on benches, and how many games each NBA team played.
- **League:** standings with all-play records and luck, every team's score every week, and the playoffs. A team's
  card has its week-by-week results and everyone who played for it: how they got him, when he left, and the points he
  scored while started or benched.
- **Draft:** every pick against where that player finished ("vs slot"), each team's draft, and the keepers view: each
  final roster ranked by full-season FP/G, with the keeper line.

How it's made, once per season:
1. **Import the league from ESPN:** Actions tab > Rolling 10 data > Run workflow, with `import_season` set to `2026`
   (or a range like `2020-2026`). This saves `fantasy/seasons/<season>/espn/` (settings, standings, matchups, the
   draft, and every team's lineup every day) and commits it.
2. **Build the page:** run `python3 fantasy/build_season.py 2026` and commit `docs/fantasy/2025-26/`.
3. **Rebuild the history:** run `python3 fantasy/build_history.py` and commit `docs/fantasy/history/`.

The build rebuilds every team's daily score from the lineups and the box scores and checks it against ESPN's: 97-99.5%
of team-days match exactly in every season (the rest are a point or two off from ESPN stat corrections), except the
last two weeks of 2019-20, before the shutdown, where ESPN's lineups don't fully line up with the box scores.

## How it stays current

The **Rolling 10 data** workflow (`.github/workflows/fantasy-data.yml`) runs every morning at 6:37 Eastern and again at
11:37: it downloads last night's box scores, runs the tests, rebuilds, and puts `data.json` on the `fantasy-data` branch
(replaced each time, so that branch is always one file and one commit). The page in `docs/fantasy/` loads that file
when it opens, so new games never need a commit to main.

- **Refresh now:** Actions tab > Rolling 10 data > Run workflow.
- **The header date stops moving:** open the latest Rolling 10 data run on the Actions tab to see which step failed.
  GitHub also pauses scheduled workflows in a repository that's had no activity for 60 days; the Actions tab shows a
  button to turn it back on.
- **Changed the page or the scoring?** Run `python3 fantasy/build.py` and commit `docs/fantasy/` (the page) along with
  the code; the next workflow run picks up the new scoring.

## Run it yourself

```
pip install -r fantasy/requirements.txt
python3 fantasy/build.py            # fetch last night's games and rebuild everything (~15 seconds)
python3 fantasy/build.py --offline  # rebuild from what's already downloaded
python3 -m pytest fantasy/tests     # the scoring and window rules
```

`fantasy/site/index.html` is the page with the numbers inside, to open from disk; `fantasy/site/rolling10.html` is the
same for the claude.ai Artifact.

## Where things are

| Path | What |
|---|---|
| `hoops/config.py` | The scoring formula, the window sizes and the trend baseline. Change it here and rebuild. |
| `hoops/fetch.py` | Downloads ESPN box scores and schedules (one parquet file per season). |
| `hoops/espn.py` | Reads the ESPN fantasy league (rosters, free agents and waivers, injury tags, % owned) and NBA rosters (ages). |
| `hoops/model.py` | Regular-season filter, fantasy points, advanced-stat pieces, windows, seasons. |
| `hoops/page.py` | Packs what the page needs into JSON and writes the page. |
| `web/template.html` | The live page (layout, board, player card, charts). |
| `web/season.html` | A finished season's page. Both pages share `web/base.css`. |
| `hoops/season.py`, `build_season.py` | A finished season: player arcs, weeks, the league replayed, the draft review. |
| `build_history.py`, `web/history.html` | The league history page. |
| `hoops/studies.py` | The tests on the Lessons tab. |
| `hoops/young.py`, `web/young.html` | The young-player model and page. |
| `tools/fetch_birthdates.py` | The one-time birthdate fetch (into `seasons/birthdates.json`). |
| `tools/import_season.py` | The one-time ESPN import of a finished season, into `seasons/<season>/espn/` (committed). |
| `tools/espn_probe.py` | Prints the shape of ESPN's answers, for debugging the league read. |
| `../docs/fantasy/` | The GitHub Pages copy of the page, built from the template (committed). |
| `../.github/workflows/fantasy-data.yml` | The twice-daily refresh. |
| `data/raw/` | Downloads (not committed). |
| `data/warehouse/` | `player_games.parquet`, one row per player per game with fantasy points, every advanced-stat piece and the rolling 10s; `player_seasons.parquet`, one row per player per season. Not committed; open with pandas or DuckDB. |
| `site/` | The built page (not committed). |

## The rules

- **Scoring:** points +1, rebounds +1, assists +1, steals +1, blocks +1, turnovers -1, made FG +1, missed FG -1,
  made FT +1, missed FT -1.
- **Windows (L5 / L10 / L20)** are the last games *played*. A DNP is skipped, not a zero. When this season is too young
  to fill a window, it reaches back into last season, and the page tags players whose window is mostly old games.
- **Regular season only:** no playoffs, play-in, All-Star game or NBA Cup final.
- **FP per minute** is total fantasy points over total minutes in the window.
- **Trend** compares the last 10 games with the 30 before them. The change in FP/G splits exactly into a minutes part,
  `(min now - min before) x FP/min before`, and a per-minute part, `min now x (FP/min now - FP/min before)`.
- **Advanced stats** use Basketball-Reference's box-score formulas (TS%, eFG%, Usage%, AST%, REB%, OREB%, DREB%, TOV%,
  STL%, BLK%), summed over the window rather than averaged game by game.
- **Wk** on the board counts the team's games left this week (Monday to Sunday); the small number is that times L10
  FP/G.
- **The league** (ESPN league 24493685, public, so no login): every player is tagged with his fantasy team, FA or
  WAIVERS, plus ESPN's injury tag. The picker at the top shows All players, Available, your team (The Process) or any
  other team. League members' names are never stored; only team names and abbreviations.
- **Keeper score (Keep):** FP/G over this season and last, where each of last season's games counts half a game. The
  Keepers view sorts by it and draws the keeper line (6 per team, 60 across the league). Ages come from ESPN's NBA
  rosters.
- If ESPN can't be read on a run, the page still builds, with the last league data downloaded or without the league
  columns, and the build log says so. The log also prints every team's roster count and the league's own scoring
  settings, to check against `SCORING`.

## Data

ESPN box scores and schedules, republished daily on GitHub by the
[sportsdataverse hoopR-nba-data](https://github.com/sportsdataverse/hoopR-nba-data) project. They usually land the
morning after the games.

Not in here yet: NBA.com's own advanced numbers (offensive/defensive rating, tracking and hustle stats). They come from
stats.nba.com, which this project's cloud sessions can't reach and which is unreliable from servers in general; it
works best run from a home computer.
