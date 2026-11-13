"""The knobs. Change a number here, run build.py again, and everything downstream follows."""
from __future__ import annotations

# The league's scoring: points per stat. A missed shot is an attempt that didn't go in.
SCORING = {
    "points": 1,
    "rebounds": 1,
    "assists": 1,
    "steals": 1,
    "blocks": 1,
    "turnovers": -1,
    "fg_made": 1,
    "fg_missed": -1,
    "ft_made": 1,
    "ft_missed": -1,
}

# Seasons are named by the year they end (ESPN's convention): 2018 is 2017-18.
FIRST_SEASON = 2018

# Rolling windows, in games played. A game he sat out is skipped, not counted as a zero, and a window reaches back into
# last season when this one is too young to fill it.
WINDOWS = {"l5": 5, "l10": 10, "l20": 20}

# "Trend" compares the last 10 games with the 30 games he played before them.
TREND_WINDOW = 10
BASELINE_GAMES = 30

# The page lists anyone who played in the current or the previous regular season.
PAGE_SEASONS_BACK = 1

# Where the GitHub Pages copy of the page (docs/fantasy/) reads its numbers. The "Rolling 10 data" workflow rewrites this
# file every morning on the fantasy-data branch, a branch that only ever holds the latest copy.
DATA_URL = "https://raw.githubusercontent.com/zacksoffer-create/Life-OS/fantasy-data/data.json"
