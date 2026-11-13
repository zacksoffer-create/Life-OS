"""Reading the ESPN league: rosters, availability, injuries, ages; and the keeper score."""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hoops import espn, page  # noqa: E402


def sample():
    def entry(pid, name, inj="ACTIVE", own=99.0):
        return {"playerId": pid, "playerPoolEntry": {"player": {"id": pid, "fullName": name, "proTeamId": 7,
                                                                "injuryStatus": inj, "ownership": {"percentOwned": own}}}}
    league = {
        "settings": {"name": "Test League", "draftSettings": {"keeperCount": 6},
                     "scoringSettings": {"scoringItems": [{"statId": 0, "points": 1.0}, {"statId": 11, "points": -1.0}]}},
        "members": [{"id": "{ABC}", "firstName": "Private", "lastName": "Person"}],
        "teams": [
            {"id": 1, "abbrev": "PROC", "name": "The Process", "owners": ["{ABC}"],
             "roster": {"entries": [entry(3112335, "Nikola Jokic"), entry(42, "Hurt Guy", inj="OUT", own=60.0)]}},
            {"id": 2, "abbrev": "OTH", "location": "Other", "nickname": "Team", "roster": {"entries": []}},
        ],
    }
    pool = {"players": [
        {"id": 7, "onTeamId": 0, "status": "WAIVERS", "player": {"id": 7, "fullName": "Waiver Wire", "injuryStatus": "DAY_TO_DAY",
                                                                  "ownership": {"percentOwned": 12.34}}},
        {"id": 8, "onTeamId": 0, "status": "FREEAGENT", "player": {"id": 8, "fullName": "Free Agent"}},
    ]}
    rosters = {"7": {"athletes": [{"id": "3112335", "age": 31}, {"id": "8", "age": 22}]}}
    return {"league": league, "pool": pool, "rosters": rosters}


def test_parse_league():
    lg = espn.parse(sample(), "the process")
    assert lg["me"] == 1
    assert [t["name"] for t in lg["teams"]] == ["The Process", "Other Team"]  # old-style location + nickname too
    p = lg["players"]
    assert p[3112335]["team"] == 1 and p[3112335]["age"] == 31
    assert p[42]["inj"] == "OUT" and p[42]["own"] == 60.0
    assert p[7].get("team") is None and p[7]["waivers"] and p[7]["inj"] == "DTD" and p[7]["own"] == 12.3
    assert p[8]["age"] == 22 and not p[8].get("team")
    assert lg["keepers"] == 6
    assert lg["scoring"] == [("PTS", 1.0), ("TO", -1.0)]


def test_league_members_names_stay_out():
    lg = espn.parse(sample(), "The Process")
    assert "Private" not in repr(lg) and "Person" not in repr(lg)


def test_no_league_data():
    assert espn.parse({"league": None, "pool": None, "rosters": None}) is None


def test_keeper_score_weights_last_season():
    sums = {
        "season": pd.DataFrame({"fp": [400.0], "gp": [10]}, index=[1]),  # 40 FP/G this season
        "last": pd.DataFrame({"fp": [2400.0, 1000.0], "gp": [80, 50]}, index=[1, 2]),  # 30 FP/G last season
    }
    kv = page.keeper_scores(sums, 0.5)
    assert kv[1] == pytest.approx((400 + 0.5 * 2400) / (10 + 0.5 * 80))  # 32.0: last season's 80 games count as 40
    assert kv[2] == pytest.approx(20.0)  # only last season
