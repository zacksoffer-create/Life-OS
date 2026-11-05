"""Phone → Scene: where you stand, the groups, who's together, and meeting friends of friends."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _story():
    from fastapi.testclient import TestClient
    from lifeos import api, moments
    from lifeos.storage import Store
    from tests.test_story import spec
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    assert c.post("/api/story/new", json={"spec": spec(per=6)}).status_code == 200
    for m in moments.pending(api.lab.w):
        moments.resolve(api.lab.sim, m["id"], None)
    return c, api


def test_where_you_stand_and_whos_together():
    c, api = _story()
    w = api.lab.w
    me = w.meta["protagonist"]
    v = c.get("/api/phone/scene").json()
    assert 1 <= v["me"]["rank"] <= v["me"]["of"] and v["me"]["tier"]
    assert {"groups", "couples", "breakups", "popular", "meet"} <= set(v)
    ppl = [p["id"] for p in c.get("/api/phone/editor").json()["people"] if not p["me"] and not p["family"]]
    a, b = ppl[:2]
    c.post(f"/api/phone/editor/pair/{a}/{b}", json={"preset": "dating"})
    v = c.get("/api/phone/scene").json()
    pair = next(x for x in v["couples"] if {x["a"]["id"], x["b"]["id"]} == {a, b})
    assert not pair["you"]
    c.post(f"/api/phone/editor/pair/{a}/{b}", json={"preset": "ex"})
    v = c.get("/api/phone/scene").json()
    assert not any({x["a"]["id"], x["b"]["id"]} == {a, b} for x in v["couples"])
    assert any({x["a"]["id"], x["b"]["id"]} == {a, b} for x in v["breakups"])
    me_c = w.chars[me]
    me_c.reputation["host"] = 12
    assert "throws the best parties" in c.get("/api/phone/scene").json()["me"]["reputation"]


def test_meet_friends_of_friends_through_an_intro_once_a_day():
    c, api = _story()
    w = api.lab.w
    me = w.meta["protagonist"]
    ppl = [p["id"] for p in c.get("/api/phone/editor").json()["people"] if not p["me"] and not p["family"]]
    friend, new = ppl[0], ppl[-1]
    c.post(f"/api/phone/editor/pair/{me}/{friend}", json={"preset": "best_friend"})
    c.post(f"/api/phone/editor/pair/{friend}/{new}", json={"preset": "close_friend"})
    c.post(f"/api/phone/editor/pair/{me}/{new}", json={"preset": "strangers"})
    v = c.get("/api/phone/scene").json()
    p = next(x for x in v["meet"] if x["id"] == new)
    assert p["via"]["id"] == friend and w.chars[friend].first in p["mutual"]
    r = c.post("/api/phone/scene/intro", json={"via": friend, "to": new}).json()
    assert any("introduced" in l["text"] for l in r["lines"])
    assert w.rels[(me, new)].familiarity >= 18 and r["scene"]["intro_today"]
    again = c.post("/api/phone/scene/intro", json={"via": friend, "to": ppl[1]})
    assert again.status_code == 409 and "tomorrow" in again.json()["detail"]
    bad = c.post("/api/phone/scene/plan", json={"with": "nobody"})
    assert bad.status_code == 409
    assert "Danny" in c.post("/api/phone/scene/plan", json={"with": friend}).json()["note"] or w.meta["control"]["queued"]["target"] == friend
