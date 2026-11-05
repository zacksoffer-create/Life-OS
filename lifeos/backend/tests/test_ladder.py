"""The Scene tab's ladder: everyone ranked by the game's own popularity, who's moving week to week and why, what your
standing is made of, the superlatives, your storylines' people, and a move on anyone (who could introduce you)."""
import copy
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import dialogue, ladder, moments  # noqa: E402
from tests.test_scheduler import BROTHER, TWINS, season_plan  # noqa: E402
from tests.test_story import spec  # noqa: E402


@pytest.fixture(autouse=True)
def own_packs(tmp_path, monkeypatch):
    monkeypatch.setattr(dialogue, "USER_DIR", str(tmp_path / "dialogue"))
    dialogue.reload()
    yield
    dialogue.reload()


def _story(days=30):
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    for p in season_plan():
        dialogue.add_pack(copy.deepcopy(p))
    dialogue.reload()
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    assert c.post("/api/story/new", json={"spec": spec(per=10, siblings=[BROTHER] + TWINS)}).status_code == 200
    sim, w = api.lab.sim, api.lab.w
    for _ in range(days):
        sim.advance_days(1)
        for m in moments.pending(w):
            moments.resolve(sim, m["id"], None)
    return c, sim, w


def test_the_ladder_ranks_everyone_and_explains_your_standing():
    c, sim, w = _story()
    v = c.get("/api/phone/ladder").json()
    ranks = [r["rank"] for r in v["rows"]]
    assert ranks == sorted(ranks) and len(ranks) == v["of"] == v["you"]["of"]
    pops = [r["pop"] for r in v["rows"]]
    assert pops == sorted(pops, reverse=True), "ranked by the game's own popularity"
    you = v["you"]
    assert you["tags"] == ["you"] and 1 <= you["rank"] <= you["of"] and you["grade_label"] == "Freshmen"
    assert [p["key"] for p in you["parts"]] == ["reach", "liked", "fans", "groups", "rep"] and you["tip"]
    assert all(0 <= p["score"] <= 100 and p["line"] for p in you["parts"])
    assert you["next_up"] is None or you["next_up"]["rank"] == you["rank"] - 1
    labels = {s["label"] for s in v["superlatives"]}
    assert {"Most Popular", "Best Athlete", "Biggest Brain", "Life of the Party"} <= labels
    grade = c.get("/api/phone/ladder", params={"scope": "grade"}).json()
    assert grade["rows"] and all(r["grade"] == 9 for r in grade["rows"]) and grade["rows"][0]["scope_rank"] == 1
    assert c.get("/api/phone/ladder", params={"scope": "nonsense"}).json()["scope"] == "school"


def test_who_moved_this_week_and_why():
    c, sim, w = _story(days=36)
    h = ladder.hist(w)
    assert len(h["snaps"]) >= 4 and len(h["me"]) >= 4, "a snapshot every week"
    v = c.get("/api/phone/ladder").json()
    moved = [r for r in v["rows"] if r["move"]]
    assert moved, "somebody moved"
    assert all(m["move"] > 0 for m in v["movers"]["up"]) and all(m["move"] < 0 for m in v["movers"]["down"])
    assert len(v["you"]["history"]) >= 4 and v["week_of"]
    # a reason only ever points the right way
    since = ladder._week_ago(w)["day"]
    for m in v["movers"]["up"]:
        if m["why"]:
            assert ladder._why(sim, sim.w.chars[w.meta["protagonist"]], m["id"], since, +1) == m["why"]


def test_your_storylines_people_and_a_way_to_meet_anyone():
    c, sim, w = _story()
    v = c.get("/api/phone/ladder").json()
    bro = next(p for p in v["storyline_people"] if p["first"] == "Mike")
    assert "Brothers: Same Team" in bro["storylines"] and "storyline" in bro["tags"] and "family" in bro["tags"]
    stranger = next((r for r in v["rows"] if r["via"]), None)
    if stranger:  # someone you barely know, and a friend who could introduce you
        r = c.post("/api/phone/scene/intro", json={"via": stranger["via"]["id"], "to": stranger["id"]})
        assert r.status_code == 200, r.text
        again = next(x for x in c.get("/api/phone/ladder").json()["rows"] if x["id"] == stranger["id"])
        assert again["via"] is None and again["label"], "you know them now"
