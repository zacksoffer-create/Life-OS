"""The knobs. Change a number here, run build.py again, and everything downstream follows."""
from __future__ import annotations

# The league's scoring, as ESPN's league settings list it. On ESPN an attempt is every shot, made or missed, so with
# FGM +1 and FGA -1 a made shot nets 0 and a miss costs 1 (same for free throws). ESPN's own fantasy averages for the
# league match this exactly; the build log compares them every run.
SCORING = {
    "points": 1,
    "rebounds": 1,
    "assists": 1,
    "steals": 1,
    "blocks": 1,
    "turnovers": -1,
    "fgm": 1,
    "fga": -1,
    "ftm": 1,
    "fta": -1,
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

# The ESPN league (public, so no login needed) and your team in it. Set the id to None to build without a league.
ESPN_LEAGUE_ID = 24493685
MY_TEAM = "The Process"

# Keepers per team, unless ESPN's league settings say otherwise. The keeper score is FP/G over this season and last,
# with last season's games counting this much each (so early on it leans on last year, by spring on this one).
KEEPERS = 6
KEEPER_LAST_SEASON_WEIGHT = 0.5

# Where the GitHub Pages copy of the page (docs/fantasy/) reads its numbers. The "Rolling 10 data" workflow rewrites this
# file every morning on the fantasy-data branch, a branch that only ever holds the latest copy.
DATA_URL = "https://raw.githubusercontent.com/zacksoffer-create/Life-OS/fantasy-data/data.json"
