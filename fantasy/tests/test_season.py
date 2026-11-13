"""A finished season: weeks from the matchups, lineups, roster moves, a player's season shape, and the draft review."""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hoops import model, page, season  # noqa: E402
from tests.test_model import box_row  # noqa: E402

OPENING = pd.Timestamp("2025-10-21")
BASE = int((OPENING - page.EPOCH).days) - 1  # page day of scoring period 0


def league(matchups):
    return {"settings": {"name": "L", "schedule": {"matchupPeriodCount": 1, "playoffTeamCount": 2},
                         "draft": {"keeperCount": 6}},
            "teams": [{"id": 1, "abbrev": "A", "name": "The Process", "record": {"overall": {"wins": 1, "losses": 0}}},
                      {"id": 2, "abbrev": "B", "name": "Other", "record": {"overall": {"wins": 0, "losses": 1}}}],
            "schedule": matchups, "draft": {"picks": [
                {"overall": 1, "round": 1, "roundPick": 1, "team": 1, "player": 10, "keeper": True},
                {"overall": 2, "round": 1, "roundPick": 2, "team": 2, "player": 20, "keeper": False}]}}


def test_weeks_come_from_the_matchup_scores():
    lg = league([{"mp": 1, "home": {"team": 1, "byDay": {"1": 5, "6": 9}}, "away": {"team": 2, "byDay": {"1": 3}}},
                 {"mp": 2, "home": {"team": 1, "byDay": {"7": 1, "27": 2}}, "away": None}])
    weeks = season.calendar(lg, OPENING)
    assert weeks == [[1, BASE + 1, BASE + 6, 0], [2, BASE + 7, BASE + 27, 1]]  # week 2 is past the regular season


def test_lineups_and_roster_moves():
    days = {"1": [[1, 10, 0], [1, 11, 12], [2, 20, 11]],
            "2": [[1, 10, 0], [2, 11, 13], [2, 20, 11], [2, 30, 12]],
            "3": [[1, 10, 0], [2, 11, 1], [2, 30, 12]]}
    lu = season.lineups(days, OPENING)
    st = {(d - BASE, p): s for d, p, s in zip(lu.day, lu.player_id, lu.st)}
    assert st[(1, 10)] == 1 and st[(1, 11)] == 0 and st[(2, 11)] == 2  # started, bench, IR
    moves = {(d - BASE, kind, team, pid, other) for d, kind, team, pid, other in season.transactions(lu)}
    assert (2, "trade", 2, 11, 1) in moves  # moved from team 1 to team 2
    assert (2, "add", 2, 30, 0) in moves
    assert (3, "drop", 2, 20, 0) in moves


def test_a_players_season_shape_and_the_draft_review():
    rows = []
    for i in range(30):  # 30 games: ten bad, ten great, ten middling, then he misses three
        pts = 10 if i < 10 else 40 if i < 20 else 20
        rows.append(box_row(1000 + i, (OPENING + pd.Timedelta(days=i)).strftime("%Y-%m-%d"), season=2026, player=10, pts=pts))
    for i in range(30, 33):
        rows.append(box_row(1000 + i, (OPENING + pd.Timedelta(days=i)).strftime("%Y-%m-%d"), season=2026, player=10, dnp=True))
    rows.append(box_row(2000, "2025-10-22", season=2026, player=20, team=2, opp=1, pts=5))
    df = model.add_advanced(model.clean(pd.DataFrame(rows)))
    lg = league([{"mp": 1, "home": {"team": 1, "total": 0, "byDay": {"1": 0, "40": 0}}, "away": {"team": 2, "total": 0, "byDay": {}},
                  "winner": "HOME", "tier": "NONE"}])
    espn = {"league": lg, "days": {"1": [[1, 10, 0], [2, 20, 12]], "2": [[1, 10, 0], [2, 20, 12]]}, "names": {}}
    out = season.build(df, 2026, espn)
    p = {x["id"]: x for x in out["players"]}
    a = dict(zip(out["meta"]["arcFields"], p[10]["a"]))
    assert a["total"] == 700 and a["rank"] == 1
    assert a["best10"] == 40 and a["worst10"] == 10
    assert a["missed"] == 3 and a["absence"] == 3
    log = [dict(zip(out["meta"]["logFields"], g)) for g in p[10]["log"]]
    assert log[0]["ft"] == 1 and log[0]["st"] == 1  # on his fantasy team and started on opening night
    assert dict(zip(out["meta"]["logFields"], p[20]["log"][0]))["st"] == 0  # benched by his team
    pick1, pick2 = out["draft"]
    assert pick1[5] == 1 and pick1[8] == 0  # a keeper who finished first, right at his slot
    assert pick2[8] == pytest.approx(5 - 5)  # pick 2 against the 2nd-best total (his own 5)
    assert out["meta"]["league"]["me"] == 1
