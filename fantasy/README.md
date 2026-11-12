# Rolling 10

Fantasy basketball numbers for a season-long, head-to-head points keeper league: every NBA regular-season game since
2017-18, scored with the league's formula, with rolling windows, fantasy points per minute and box-score advanced stats.
The output is one phone page.

## Run it

```
pip install -r fantasy/requirements.txt
python3 fantasy/build.py            # fetch last night's games and rebuild everything (~15 seconds)
python3 fantasy/build.py --offline  # rebuild from what's already downloaded
python3 -m pytest fantasy/tests     # the scoring and window rules
```

Then publish `fantasy/site/rolling10.html` as the Artifact again (same URL), or open `fantasy/site/index.html` in a
browser.

## Where things are

| Path | What |
|---|---|
| `hoops/config.py` | The scoring formula, the window sizes and the trend baseline. Change it here and rebuild. |
| `hoops/fetch.py` | Downloads ESPN box scores and schedules (one parquet file per season). |
| `hoops/model.py` | Regular-season filter, fantasy points, advanced-stat pieces, windows, seasons. |
| `hoops/page.py` | Packs what the page needs into JSON and writes the page. |
| `web/template.html` | The page itself (layout, board, player card, charts). |
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

## Data

ESPN box scores and schedules, republished daily on GitHub by the
[sportsdataverse hoopR-nba-data](https://github.com/sportsdataverse/hoopR-nba-data) project. They usually land the
morning after the games.

Not in here yet: NBA.com's own advanced numbers (offensive/defensive rating, tracking and hustle stats). They come from
stats.nba.com, which this project's cloud sessions can't reach and which is unreliable from servers in general; it
works best run from a home computer.
