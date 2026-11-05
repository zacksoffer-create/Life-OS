"""The full editor on the phone: everything the story builder sets can be changed mid-story (gender, who they're into,
birthday, height and build, sport positions and jersey, what's next after high school, their type), checked the same way,
and someone new can be added; who can be into who follows right away."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.test_story import spec  # noqa: E402


@pytest.fixture
def c():
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    client = TestClient(api.app)
    assert client.post("/api/story/new", json={"spec": spec(per=6)}).status_code == 200
    return client


def _someone(c, me):
    return next(p for p in c.get("/api/phone/editor").json()["people"] if not p.get("me") and p["id"] != me and p.get("year"))


def test_everything_the_builder_sets_can_be_edited_later(c):
    from lifeos import api, calendar as calm
    w = api.lab.w
    me = w.meta["protagonist"]
    p = _someone(c, me)
    before = c.get(f"/api/phone/editor/person/{p['id']}").json()
    for k in ("attracted_to", "birthday", "body", "positions", "jersey", "path", "archetype", "pronouns"):
        assert k in before, k
    cat = c.get("/api/story/catalog").json()
    sport = next(s for s, v in cat["sports"].items() if v.get("positions"))
    pos = next(iter(cat["sports"][sport]["positions"]))
    college = cat["colleges"][0]["id"]
    arch = cat["archetypes"][-1]["id"]
    out = c.post(f"/api/phone/editor/person/{p['id']}", json={
        "gender": "nb", "attracted_to": ["f", "m"], "birthday": [12, 25], "body": {"height_in": 74, "build": "athletic"},
        "positions": {sport: pos}, "jersey": 23, "path": {"kind": "college", "college": college}, "archetype": arch}).json()
    ch = w.chars[p["id"]]
    assert ch.gender == "nb" and ch.pronouns.startswith("they") and ch.attracted_to == ["f", "m"]
    bd = calm.date_of(ch.birth_day)
    assert (bd.month, bd.day) == (12, 25) and out["birthday"] == [12, 25]
    assert ch.body["height_in"] == 74 and ch.body["build"] == "athletic" and ch.positions[sport] == pos and ch.jersey == 23
    assert ch.path == {"kind": "college", "college": college} and ch.archetype == arch
    # they stay in their own class whatever their birthday
    b0 = calm.date_of(w.chars[p["id"]].birth_day)
    c.post(f"/api/phone/editor/person/{p['id']}", json={"birthday": [3, 1]})
    b1 = calm.date_of(w.chars[p["id"]].birth_day)
    assert (b1.year + (b1.month >= 9)) == (b0.year + (b0.month >= 9))
    # off the team, back to letting it play out
    c.post(f"/api/phone/editor/person/{p['id']}", json={"positions": {sport: None}, "path": None, "jersey": None, "body": {"build": None}})
    assert sport not in ch.positions and ch.path == {} and ch.jersey == 0 and "build" not in ch.body


@pytest.mark.parametrize("bad", [{"gender": "x"}, {"attracted_to": ["q"]}, {"birthday": [2, 31]}, {"body": {"height_in": 200}},
                                 {"positions": {"curling": "skip"}}, {"jersey": 140}, {"path": {"kind": "college", "college": "nope"}},
                                 {"archetype": "wizard"}])
def test_the_same_checks_as_the_builder_and_nothing_changes(c, bad):
    from lifeos import api
    me = api.lab.w.meta["protagonist"]
    p = _someone(c, me)
    before = c.get(f"/api/phone/editor/person/{p['id']}").json()
    r = c.post(f"/api/phone/editor/person/{p['id']}", json={"first": "Changed", **bad})
    assert r.status_code == 422
    assert c.get(f"/api/phone/editor/person/{p['id']}").json()["first"] == before["first"], "all or nothing"


def test_who_theyre_into_takes_effect_right_away(c):
    from lifeos import api
    w = api.lab.w
    me = w.meta["protagonist"]
    other = next(x for x in w.students() if x.id != me and x.household_id != w.chars[me].household_id and x.gender != w.chars[me].gender)
    r = w.rels[(other.id, me)]
    other.attracted_to = [w.chars[me].gender]
    r.attraction, r.crush = 40.0, True
    c.post(f"/api/phone/editor/person/{other.id}", json={"attracted_to": [other.gender]})
    assert r.attraction == 0 and not r.crush, "not into you any more: the crush is gone"


def test_add_someone_mid_story(c):
    from lifeos import api
    w = api.lab.w
    me = w.meta["protagonist"]
    n = len(w.chars)
    j = c.post("/api/phone/editor/new", json={"first": "Tessa", "last": "Marlowe", "gender": "f", "grade": 10, "to_me": "friend"}).json()
    t = w.chars[j["id"]]
    assert len(w.chars) == n + 1 and t.first == "Tessa" and t.grade == 10 and t.status == "active"
    assert w.rels[(t.id, me)].affection > 10 and w.rels[(me, t.id)].affection > 10
    assert any(p["id"] == t.id for p in c.get("/api/phone/editor").json()["people"])
    sib = c.post("/api/phone/editor/new", json={"first": "Max", "gender": "m", "grade": 9, "family": True}).json()
    assert w.chars[sib["id"]].household_id == w.chars[me].household_id
    coach = c.post("/api/phone/editor/new", json={"first": "Dana", "last": "Reyes", "gender": "f", "role": "staff"}).json()
    assert w.chars[coach["id"]].role == "staff"
    for bad in ({"gender": "f"}, {"first": "A", "gender": "f", "grade": 7}, {"first": "A", "gender": "f", "to_me": "nemesis"}):
        assert c.post("/api/phone/editor/new", json=bad).status_code == 422


def test_what_works_flirting_is_yours_to_set_and_it_carries_into_a_replay(c):
    from lifeos import api
    from lifeos.chat import personality_tastes, tastes
    from lifeos.messages import phone
    w = api.lab.w
    me = w.meta["protagonist"]
    o = _someone(c, me)["id"]
    p = c.get(f"/api/phone/editor/person/{o}").json()
    assert [s["style"] for s in p["flirt"]["styles"]] == ["tease", "sweet", "bold", "funny", "cheesy"]
    assert not p["flirt"]["custom"] and all(not s["set"] for s in p["flirt"]["styles"])
    base = personality_tastes(w.chars[o])
    flip = {k: (-1 if v >= 0 else 1) for k, v in base.items()}
    phone(w).setdefault("tastes", {})[o] = {"tease": base["tease"]}  # you'd already figured out how teasing goes over
    r = c.post(f"/api/phone/editor/person/{o}", json={"flirt": {"tease": flip["tease"], "sweet": flip["sweet"]}})
    assert r.status_code == 200, r.text
    got = {s["style"]: s for s in r.json()["flirt"]["styles"]}
    assert got["tease"]["value"] == flip["tease"] and got["tease"]["set"] and got["bold"]["value"] == base["bold"] and not got["bold"]["set"]
    assert tastes(w.chars[o])["tease"] == flip["tease"] and tastes(w.chars[o])["sweet"] == flip["sweet"]
    assert phone(w)["tastes"][o]["tease"] == flip["tease"]  # what you knew about them is what's true now
    # one more style on top keeps the others; null puts one back
    c.post(f"/api/phone/editor/person/{o}", json={"flirt": {"bold": flip["bold"], "sweet": None}})
    assert tastes(w.chars[o]) == dict(base, tease=flip["tease"], bold=flip["bold"])
    assert c.post(f"/api/phone/editor/person/{o}", json={"flirt": {"sarcasm": 1}}).status_code == 422
    assert c.post(f"/api/phone/editor/person/{o}", json={"flirt": {"tease": 2}}).status_code == 422
    # Start over: the same person, the same tastes
    name = w.chars[o].name
    assert c.post("/api/story/restart", json={}).status_code == 200
    w = api.lab.w
    o2 = next(x for x, ch in w.chars.items() if ch.name == name)
    assert tastes(w.chars[o2]) == dict(personality_tastes(w.chars[o2]), tease=flip["tease"], bold=flip["bold"])
    # and back to their personality
    c.post(f"/api/phone/editor/person/{o2}", json={"flirt": None})
    assert tastes(w.chars[o2]) == personality_tastes(w.chars[o2]) and not c.get(f"/api/phone/editor/person/{o2}").json()["flirt"]["custom"]
