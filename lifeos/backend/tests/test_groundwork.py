"""Groundwork carries into a replay: who people are, people you added, relationships you set and who your storylines are
about all come back when you start over (the same setup builds the same town); where things stood in the run doesn't.
And a storyline person nobody fits can be made to fit."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import dialogue  # noqa: E402
from tests.test_story import spec  # noqa: E402

SIS_STORY = """=== Sister Stuff
cast: ally = older sister
years: freshman

--- Borrowed Car
ally: You're not driving my car.
* "Please?"
ally: Fine. Once.
* "Fine."
ally: Good.
"""
SLOTS = """=== Court Rivals
cast: kayla = older sister, soccer
cast: jordan = friend of kayla
years: freshman

--- Kayla's Game
kayla: You came!
* "Obviously."
kayla: Front row then.
* "Mom made me."
kayla: Wow.
"""


@pytest.fixture
def c(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    monkeypatch.setattr(dialogue, "USER_DIR", str(tmp_path / "dialogue"))
    dialogue.reload()
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    client = TestClient(api.app)
    assert client.post("/api/story/new", json={"spec": spec(per=6)}).status_code == 200
    yield client, api
    dialogue.reload()


def _id(w, first):
    return next(x.id for x in w.chars.values() if x.first == first)


def test_start_over_brings_back_your_groundwork_and_not_the_run(c):
    client, api = c
    w = api.lab.w
    me = w.meta["protagonist"]
    mike, danny, ally = _id(w, "Mike"), _id(w, "Danny"), _id(w, "Ally")
    other = next(x.id for x in w.students() if x.id not in (me, mike, danny, ally) and x.grade == 9)
    ids_before = sorted(w.chars)
    client.post(f"/api/phone/editor/person/{mike}", json={"traits": {"volatility": 90}, "look": {"hair_color": "black"},
                                                          "positions": {"basketball": "C"}, "mood": 10, "gpa": 1.2})
    tessa = client.post("/api/phone/editor/new", json={"first": "Tessa", "last": "Marlowe", "gender": "f", "grade": 9, "to_me": "friend"}).json()["id"]
    client.post(f"/api/phone/editor/pair/{danny}/{other}", json={"preset": "best_friend"})
    pid = dialogue.add_script(SIS_STORY)["ids"][0]
    sisters = [s for s in dialogue.candidates(api.lab.sim, w.chars[me], "older_sister")]
    jen = _id(w, "Jen")
    assert jen in sisters
    assert client.post("/api/dialogue/cast", json={"pack": pid, "who": "older_sister", "char": jen}).status_code == 200
    rows = client.get("/api/story/groundwork").json()
    kinds = {r["kind"] for r in rows["rows"]}
    assert kinds == {"added", "person", "pair", "pick"} and rows["count"] == 4, rows
    assert next(r for r in rows["rows"] if r["kind"] == "person")["what"] == "personality, look, positions", "mood and GPA aren't groundwork"
    client.post("/api/story/advance", json={"days": 6})
    j = client.post("/api/story/restart", json={}).json()
    assert j["carried"]["done"] == 4 and not j["carried"]["skipped"], j["carried"]
    w2 = api.lab.w
    assert w2 is not w and w2.day == 0
    assert set(ids_before) <= set(w2.chars), "the same town: everyone from the setup is back"
    m = w2.chars[mike]
    assert m.traits["volatility"] == 90 and m.look.get("hair_color") == "black" and m.positions["basketball"] == "C"
    assert m.gpa != 1.2 and m.mood != 10, "where things stood doesn't come back"
    t = next(x for x in w2.chars.values() if x.first == "Tessa")
    assert t.id == tessa and w2.rels[(t.id, me)].affection > 10
    assert w2.rels[(danny, other)].label in ("best friend", "close friend", "friend") and w2.rels[(danny, other)].affection > 50
    assert dialogue.pick_cast(api.lab.sim, w2.chars[me], pid, "older_sister", [ally, jen]) == jen
    # again: it carries again, and nothing doubles up
    j = client.post("/api/story/restart", json={}).json()
    assert j["carried"]["done"] == 4 and sum(1 for x in api.lab.w.chars.values() if x.first == "Tessa") == 1
    assert client.get("/api/story/groundwork").json()["count"] == 4


def test_leave_things_out_or_start_clean(c):
    client, api = c
    w = api.lab.w
    mike = _id(w, "Mike")
    client.post(f"/api/phone/editor/person/{mike}", json={"traits": {"volatility": 90}})
    client.post("/api/phone/editor/new", json={"first": "Tessa", "gender": "f", "grade": 10})
    rows = client.get("/api/story/groundwork").json()["rows"]
    left = client.post("/api/story/groundwork/remove", json={"kind": "person", "key": mike}).json()
    assert left["count"] == 1 and left["rows"][0]["kind"] == "added"
    client.post("/api/story/restart", json={})
    w2 = api.lab.w
    assert w2.chars[mike].traits["volatility"] != 90 and any(x.first == "Tessa" for x in w2.chars.values())
    client.post("/api/story/restart", json={"keep": False})
    assert not any(x.first == "Tessa" for x in api.lab.w.chars.values())
    assert client.get("/api/story/groundwork").json()["count"] == 0
    assert len(rows) == 2


def test_a_new_setup_can_bring_the_groundwork_too(c):
    client, api = c
    w = api.lab.w
    danny = _id(w, "Danny")
    client.post(f"/api/phone/editor/person/{danny}", json={"traits": {"empathy": 99}, "attracted_to": ["f", "m"]})
    s = spec(per=6)
    s["siblings"][0]["first"] = "Michael"  # changed in the setup: a different person now
    j = client.post("/api/story/new", json={"spec": s, "carry": True}).json()
    w2 = api.lab.w
    assert j["carried"]["done"] == 1
    d2 = w2.chars[danny]
    assert d2.traits["empathy"] == 99 and d2.attracted_to == ["f", "m"]
    assert any(x.first == "Michael" for x in w2.chars.values())
    client.post("/api/story/new", json={"spec": s})
    assert api.lab.w.chars[danny].traits["empathy"] != 99, "without carry, a new story is just the setup"


def test_someone_who_fits_a_storyline_nobody_fits(c):
    client, api = c
    w = api.lab.w
    me = w.chars[w.meta["protagonist"]]
    pid = dialogue.add_script(SLOTS)["ids"][0]
    cast = client.get("/api/dialogue/cast", params={"pack": pid}).json()
    kay = next(s for s in cast["slots"] if s["slot"] == "kayla")
    assert not kay["options"], "nobody in this story is an older sister who plays soccer"
    j = client.post("/api/phone/editor/fit", json={"slot": "kayla"}).json()
    k = api.lab.w.chars[j["id"]]
    assert j["fits"] and k.gender == "f" and k.grade == 10 and k.household_id == me.household_id
    assert dialogue.bound(api.lab.sim, "kayla") == k.id
    jo = client.post("/api/phone/editor/fit", json={"slot": "jordan"}).json()
    assert jo["fits"] and dialogue.bound(api.lab.sim, "jordan") == jo["id"]
    assert api.lab.w.rels[(jo["id"], k.id)].affection > 30, "a friend of Kayla's"
    # they're groundwork: a replay makes them again and they're still who the storyline is about
    client.post("/api/story/restart", json={})
    w2 = api.lab.w
    assert dialogue.bound(api.lab.sim, "kayla") == k.id and w2.chars[k.id].first == k.first
    assert dialogue.bound(api.lab.sim, "jordan") == jo["id"]
    r = client.post("/api/phone/editor/fit", json={"slot": "nope"})
    assert r.status_code == 422
