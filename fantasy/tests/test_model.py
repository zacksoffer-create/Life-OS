"""The rules the numbers rest on: the league's scoring, last-10-played windows, and regular season only."""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hoops import config, model  # noqa: E402


def box_row(game_id, date, season=2027, player=1, team=1, opp=2, minutes=30.0, dnp=False, season_type=2, **stats):
    row = {
        "game_id": game_id, "season": season, "season_type": season_type, "game_date": date, "athlete_id": float(player),
        "athlete_display_name": f"Player {player}", "athlete_position_abbreviation": "G", "team_id": team,
        "team_abbreviation": f"T{team}", "opponent_team_id": opp, "opponent_team_abbreviation": f"T{opp}",
        "home_away": "home", "starter": True, "did_not_play": dnp, "reason": "REST" if dnp else None,
        "minutes": None if dnp else minutes,
    }
    for espn in model.RENAME:
        if espn != "minutes":
            row[espn] = 0.0 if dnp else float(stats.get(model.RENAME[espn], 0))
    return row


def test_scoring_matches_the_league_formula():
    # ESPN: FGM +1, FGA -1, FTM +1, FTA -1, where an attempt is every shot. 27 pts, 11 reb, 8 ast, 1 stl, 1 blk, 1 TO,
    # 10-16 FG, 6-8 FT: 27 + 11 + 8 + 1 + 1 - 1 + (10 - 16) + (6 - 8) = 39 (each miss costs 1, a make nets 0)
    df = pd.DataFrame([box_row(1, "2026-11-11", pts=27, reb=11, ast=8, stl=1, blk=1, tov=1, fgm=10, fga=16, ftm=6, fta=8)])
    assert model.clean(df).fp.iloc[0] == 39


def test_scoring_reads_the_config():
    df = model.clean(pd.DataFrame([box_row(1, "2026-11-11", pts=10, fgm=4, fga=9)]))
    doubled = {k: 2 * v for k, v in config.SCORING.items()}
    assert model.fantasy_points(df, doubled).iloc[0] == 2 * df.fp.iloc[0]


def test_regular_season_only():
    box = pd.DataFrame([
        box_row(1, "2026-11-01", pts=10),
        box_row(2, "2027-04-20", season_type=3, pts=10),  # playoffs
        box_row(3, "2027-04-15", season_type=5, pts=10),  # play-in
        box_row(4, "2027-02-14", team=31, opp=32, pts=10),  # All-Star game
        box_row(5, "2026-12-16", pts=10),  # NBA Cup final
    ])
    sched = pd.DataFrame({"game_id": [1, 4, 5], "type_abbreviation": ["STD", "ALLSTAR", "CC"]})
    assert model.regular_season(box, sched).game_id.tolist() == [1]


def test_last_ten_skips_dnps_and_reaches_into_last_season():
    rows = []
    # Last season: games worth 100 FP each (100 points). This season: 4 games of 10 FP, then he sits two, then 1 more.
    for i in range(20):
        rows.append(box_row(100 + i, f"2026-03-{i + 1:02d}", season=2026, pts=100))
    for i in range(4):
        rows.append(box_row(200 + i, f"2026-10-{21 + i}", pts=10))
    rows.append(box_row(210, "2026-10-26", dnp=True))
    rows.append(box_row(211, "2026-10-27", dnp=True))
    rows.append(box_row(220, "2026-10-28", pts=10))
    df = model.add_advanced(model.clean(pd.DataFrame(rows)))
    w = model.windows(df, 2027)
    l10 = model.rates(w["l10"]).loc[1]
    assert l10.gp == 10  # the two DNPs aren't in it
    assert l10.fpg == pytest.approx((5 * 10 + 5 * 100) / 10)  # five from this season, five from last
    assert model.rates(w["season"]).loc[1].gp == 5
    assert model.rates(w["base"]).loc[1].gp == 15  # the 15 games before the last 10


def test_fp_per_minute_weights_by_minutes():
    df = pd.DataFrame([box_row(1, "2026-11-01", minutes=40, pts=40), box_row(2, "2026-11-03", minutes=10, pts=0)])
    df = model.add_advanced(model.clean(df))
    l5 = model.rates(model.windows(df, 2027)["l5"]).loc[1]
    assert l5.fpm == pytest.approx(40 / 50)  # total points over total minutes, not the average of 1.0 and 0.0
    assert l5.fpg == pytest.approx(20)


def test_scoring_from_espn_settings():
    # FGM +1, FG missed -1 (statId 23) and a double-double bonus (statId 37)
    sc, unknown = model.scoring_from_espn([{"statId": 0, "points": 1}, {"statId": 13, "points": 1},
                                           {"statId": 23, "points": -1}, {"statId": 37, "points": 2}])
    assert not unknown and sc == {"points": 1, "fgm": 2, "fga": -1, "dd": 2}
    df = model.clean(pd.DataFrame([box_row(1, "2026-11-11", pts=20, reb=10, fgm=8, fga=15)]))
    assert model.fantasy_points(df, sc).iloc[0] == 20 + 2 * 8 - 15 + 2  # a double-double
    assert model.scoring_from_espn([{"statId": 999, "points": 1}])[1] == [999]
