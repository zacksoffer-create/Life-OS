"""The league and the Sports tab: the conference's schools are real teams that all play every week, the table matches
the games your team actually played, Player of the Week and the regular-season title, prestige that follows the record,
big games that travel around school (feeding popularity), and the Sports tab built on all of it."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import dialogue, league, moments  # noqa: E402
from tests.test_scheduler import BROTHER, TWINS  # noqa: E402
from tests.test_story import spec  # noqa: E402


@pytest.fixture(autouse=True)
def own_packs(tmp_path, monkeypatch):
    monkeypatch.setattr(dialogue, "USER_DIR", str(tmp_path / "dialogue"))
    dialogue.reload()
    yield
    dialogue.reload()


def _story(days=60):
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    assert c.post("/api/story/new", json={"spec": spec(per=12, siblings=[BROTHER] + TWINS)}).status_code == 200
    sim, w = api.lab.sim, api.lab.w
    for _ in range(days):
        sim.advance_days(1)
        for m in moments.pending(w):
            moments.resolve(sim, m["id"], None)
    return c, sim, w


def test_the_table_is_the_games_that_were_played():
    c, sim, w = _story()
    leagues = list(w.meta["league"].values())
    assert leagues
    for lea in leagues:
        rows = league.table(lea)
        assert sum(r["w"] for r in rows) == sum(r["l"] for r in rows), "every game has a winner and a loser"
        assert sum(r["pf"] for r in rows) == sum(r["pa"] for r in rows)
        g = w.groups[lea["group"]]
        us = next(r for r in rows if r["ours"])
        assert (us["w"], us["l"]) == (g["record"]["w"], g["record"]["l"]), "the table matches the team's record"
        games = [e for e in w.history.events.values() if e["type"] == "game" and e.get("group") == g["id"]
                 and e["outcome"] in ("win", "loss") and e["data"].get("level") == "varsity"]
        ours = lea["teams"][lea["ours"]]["results"]
        assert [r["win"] for r in ours] == [e["outcome"] == "win" for e in sorted(games, key=lambda e: e["id"])]
        assert [r["vs"] for r in ours] == [e["data"]["opponent"] for e in sorted(games, key=lambda e: e["id"])]
        assert len({r["vs"] for r in ours}) == len(ours), "the schedule goes through the conference"
        assert "Hand" in lea["teams"] and lea["rival"] == "Hand" and lea["ours"] == "Guilford"


def test_player_of_the_week_prestige_and_word_getting_around():
    c, sim, w = _story(days=70)
    leas = list(w.meta["league"].values())
    assert any(lea["potw"] for lea in leas) and any(lea["power"] for lea in leas)
    for lea in leas:
        g = w.groups[lea["group"]]
        us = lea["teams"][lea["ours"]]
        if us["w"] + us["l"] >= 3:
            pct = us["w"] / (us["w"] + us["l"])
            assert (g["prestige"] > g["prestige_base"]) == (pct > 0.5) or pct == 0.5, (pct, g["prestige"], g["prestige_base"])
    for lea in leas:
        for p in lea["potw"]:
            if p.get("ours") and p["id"] in w.chars:
                assert any(a.get("potw") for a in w.chars[p["id"]].awards)
    # a big game travels: people who weren't there get to know the star
    star = next(e for e in sorted(w.history.events.values(), key=lambda e: -e["id"]) if e["type"] == "game" and e["outcome"] == "star"
                and e["importance"] >= 26)
    heard = [ch for ch in star["changes"] if ch[1] == "familiarity" and "big game" in str(ch[-1])]
    assert len(heard) >= 3 and all(ch[0].endswith(">" + star["actors"][0]) for ch in heard), "word gets around school"


def test_the_sports_tab():
    c, sim, w = _story()
    v = c.get("/api/phone/sports").json()
    assert v["teams"] and v["team"]["of"] == 15 and v["team"]["conference"] == "SCC"
    y = v["you"]
    ratings = [d["rating"] for d in y["depth"]]
    assert ratings == sorted(ratings, reverse=True) and sum(d["starter"] for d in y["depth"]) == min(y["starters"], len(ratings))
    assert next(d for d in y["depth"] if d["you"])["starter"] == y["starter"]
    assert [p["key"] for p in y["parts"]] == ["skill", "athletic", "fitness", "body", "confidence"]
    assert abs(sum(p["value"] for p in y["parts"]) + 6 - y["rating"]) < 0.6, "the parts are the rating"
    assert y["tip"] and v["standings"][0]["rank"] == 1 and v["leaders"]
    assert v["race"]["all_conf"] and all(a["per"] >= b["per"] for a, b in zip(v["race"]["all_conf"], v["race"]["all_conf"][1:]))
    if len(v["teams"]) > 1:
        other = v["teams"][1]["id"]
        assert c.get("/api/phone/sports", params={"team": other}).json()["team"]["id"] == other
