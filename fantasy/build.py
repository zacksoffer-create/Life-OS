"""Rolling 10: download the box scores, rebuild the warehouse, write the phone page.

    pip install -r fantasy/requirements.txt
    python3 fantasy/build.py              # refresh this season's games and rebuild everything (about 15 seconds)
    python3 fantasy/build.py --offline    # rebuild from what's already downloaded

What it writes (all under fantasy/, none of it committed; rebuild any time):
- data/raw/          ESPN box scores and schedules as downloaded, one file per season
- data/warehouse/    player_games.parquet (every regular-season player-game since 2017-18 with fantasy points, the
                     advanced-stat pieces and rolling 10s) and player_seasons.parquet. Open them with pandas or DuckDB.
- site/rolling10.html  the phone page with the numbers inside (the claude.ai Artifact)
- site/index.html      the same page as a standalone file you can open in a browser
- site/data.json       the numbers alone; the "Rolling 10 data" workflow publishes this every morning
- ../docs/fantasy/     the GitHub Pages copy (committed): it loads data.json when it opens, so it never needs rebuilding
                       for new games, only when the page itself changes
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from hoops import config, espn, fetch, model, page  # noqa: E402


def load(raw_dir: str, first: int, last: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    boxes, scheds = [], []
    for season in range(first, last + 1):
        boxes.append(pd.read_parquet(fetch.local_path(raw_dir, "player_box", season)))
        scheds.append(pd.read_parquet(fetch.local_path(raw_dir, "schedule", season)))
    return pd.concat(boxes, ignore_index=True), pd.concat(scheds, ignore_index=True)


def report_league(league: dict | None, df: pd.DataFrame) -> None:
    """What came back from ESPN, in the build log, so a bad read is easy to spot."""
    if not league:
        print("  No league data this run; the page builds without the league columns")
        return
    mine = next((t for t in league["teams"] if t["id"] == league["me"]), None)
    print(f"  \"{league['name']}\": {len(league['teams'])} teams; yours: "
          + (f"{mine['name']} (team {mine['id']})" if mine else "NOT FOUND - check MY_TEAM in hoops/config.py"))
    known = set(df[df.played].player_id.unique())
    rostered = {pid: x for pid, x in league["players"].items() if x.get("team")}
    for t in league["teams"]:
        n = sum(1 for x in rostered.values() if x["team"] == t["id"])
        print(f"    {t['abbrev']:>5}  {t['name']}: {n} players")
    missing = [x.get("name") or str(pid) for pid, x in rostered.items() if pid not in known]
    print(f"  Rostered: {len(rostered)}; with box scores: {len(rostered) - len(missing)}"
          + (f"; no games on record: {', '.join(missing)}" if missing else ""))
    ages = sum(1 for x in league["players"].values() if "age" in x)
    inj = sum(1 for x in league["players"].values() if x.get("inj"))
    print(f"  Ages: {ages} players; injury tags: {inj}; keepers per team: {league.get('keepers') or config.KEEPERS}")
    if league["scoring"]:
        print("  League scoring: " + ", ".join(f"{name} {pts:+g}" for name, pts in league["scoring"]))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="don't download; use the files already in data/raw")
    ap.add_argument("--data", default=os.path.join(HERE, "data"))
    ap.add_argument("--out", default=os.path.join(HERE, "site"))
    ap.add_argument("--pages", default=os.path.join(HERE, "..", "docs", "fantasy"),
                    help="where the GitHub Pages copy goes (it fetches its numbers from --data-url)")
    ap.add_argument("--data-url", default=config.DATA_URL)
    args = ap.parse_args(argv)

    t0 = time.time()
    raw = os.path.join(args.data, "raw")
    season = fetch.season_for(dt.date.today())
    if args.offline:
        while season > config.FIRST_SEASON and not os.path.exists(fetch.local_path(raw, "player_box", season)):
            season -= 1
    else:
        print("Downloading box scores and schedules")
        season = fetch.download(raw, config.FIRST_SEASON, season)

    box, sched = load(raw, config.FIRST_SEASON, season)
    df = model.clean(model.regular_season(box, sched))
    df = model.add_rolling(model.add_advanced(df), config.TREND_WINDOW)
    through = df[df.played].date.max().date()
    print(f"{df.played.sum():,} games played by {df[df.played].player_id.nunique():,} players, "
          f"{config.FIRST_SEASON - 1}-{str(config.FIRST_SEASON)[2:]} through {through:%b %d, %Y}")

    wh = os.path.join(args.data, "warehouse")
    os.makedirs(wh, exist_ok=True)
    df.to_parquet(os.path.join(wh, "player_games.parquet"), index=False)
    model.seasons(df).to_parquet(os.path.join(wh, "player_seasons.parquet"), index=False)

    league = None
    if config.ESPN_LEAGUE_ID:
        print(f"ESPN league {config.ESPN_LEAGUE_ID}")
        league = espn.parse(espn.download(raw, season, config.ESPN_LEAGUE_ID, offline=args.offline), config.MY_TEAM)
        report_league(league, df)

    cur_sched = sched[sched.season == season]
    payload = page.build_payload(df, cur_sched, season, league)
    paths = page.render(payload, os.path.join(HERE, "web", "template.html"), args.out, args.pages, args.data_url)
    size = os.path.getsize(paths[0]) / 1e6
    print(f"Page: {len(payload['players'])} players, {size:.1f} MB -> {os.path.relpath(paths[0])}")
    print(f"Done in {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
