# Rolling 10

Fantasy basketball numbers for a season-long, head-to-head points keeper league: every NBA regular-season game since
2017-18, scored with the league's formula, with rolling windows, fantasy points per minute and box-score advanced stats.
The output is one phone page.

**On your phone:** https://zacksoffer-create.github.io/Life-OS/fantasy/ (Safari, then Share > Add to Home Screen).

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
| `web/template.html` | The page itself (layout, board, player card, charts). |
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
