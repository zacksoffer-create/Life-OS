"""Download ESPN box scores and schedules, as republished on GitHub by sportsdataverse (the hoopR project).

One parquet file per season and kind. Past seasons are downloaded once and kept; the current season is downloaded again
on every run, since it grows every night.
"""
from __future__ import annotations

import datetime as dt
import os
import urllib.error
import urllib.request

BASE = "https://raw.githubusercontent.com/sportsdataverse/hoopR-nba-data/main/nba"
PATHS = {
    "player_box": "player_box/parquet/player_box_{season}.parquet",
    "schedule": "schedules/parquet/nba_schedule_{season}.parquet",
}


def season_for(day: dt.date) -> int:
    """The season a date belongs to, named by the year it ends. From September on, it's next year's."""
    return day.year + 1 if day.month >= 9 else day.year


def local_path(raw_dir: str, kind: str, season: int) -> str:
    return os.path.join(raw_dir, f"{kind}_{season}.parquet")


def download(raw_dir: str, first: int, last: int, log=print) -> int:
    """Fetch every file from `first` through `last`. Returns the newest season that has box scores.

    The newest season is re-downloaded each time. A season that hasn't started yet (no file upstream) is skipped.
    """
    os.makedirs(raw_dir, exist_ok=True)
    newest = first - 1
    for season in range(first, last + 1):
        for kind, pattern in PATHS.items():
            dest = local_path(raw_dir, kind, season)
            if os.path.exists(dest) and season < last:
                continue
            url = f"{BASE}/{pattern.format(season=season)}"
            tmp = dest + ".part"
            try:
                urllib.request.urlretrieve(url, tmp)
            except urllib.error.HTTPError as e:
                if e.code == 404 and season == last:
                    log(f"  {kind} {season}: not published yet, skipping")
                    break
                raise
            os.replace(tmp, dest)
            log(f"  {kind} {season}: {os.path.getsize(dest) / 1e6:.1f} MB")
        if os.path.exists(local_path(raw_dir, "player_box", season)):
            newest = season
    return newest
