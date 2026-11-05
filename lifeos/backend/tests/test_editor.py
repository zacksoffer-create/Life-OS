"""The editor: change anyone and anything between two people, quietly, with checks, and only while it's on."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _story():
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    from tests.test_story import spec
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    assert c.post("/api/story/new", json={"spec": spec(per=6)}).status_code == 200
    return c, api


def test_edit_a_person_everything_checked_first():
    c, api = _story()
    ed = c.get("/api/phone/editor").json()
    assert ed["people"][0]["me"] and {"traits", "aptitudes", "motives", "skills", "interests", "rel_fields"} <= set(ed["schema"])
    me = ed["people"][0]["id"]
    other = next(p for p in ed["people"] if not p["me"] and not p["family"])
    pid = other["id"]
    feed0 = c.get("/api/phone/state").json()["feed"]
    r = c.post(f"/api/phone/editor/person/{pid}", json={
        "traits": {"confidence": 95, "empathy": 10}, "aptitudes": {"athletic": 88}, "motives": {"pleasure": 70}, "skills": {"basketball": 77},
        "interests": {"gaming": 90}, "needs": {"stress": 5}, "mood": 81, "popularity": 66, "money": 250, "gpa": 3.9,
        "first": "Zed", "last": "Quinn", "bio": "New kid energy.", "look": {"hair_color": "red"}}).json()
    assert r["first"] == "Zed" and r["last"] == "Quinn" and r["bio"] == "New kid energy."
    assert r["traits"]["confidence"] == 95 and r["traits"]["empathy"] == 10 and r["aptitudes"]["athletic"] == 88
    assert r["skills"]["basketball"] == 77 and r["interests"]["gaming"] == 90 and r["needs"]["stress"] == 5
    assert r["mood"] == 81 and r["popularity"] == 66 and r["money"] == 250 and r["gpa"] == 3.9 and r["look"]["hair_color"] == "red"
    w = api.lab.w
    assert w.chars[pid].first == "Zed" and w.chars[pid].traits["confidence"] == 95
    # nothing changes if anything is wrong
    bad = c.post(f"/api/phone/editor/person/{pid}", json={"traits": {"confidence": 20, "made_up": 5}, "mood": 500})
    assert bad.status_code == 422 and "made_up" in bad.json()["detail"] and "mood" in bad.json()["detail"]
    assert w.chars[pid].traits["confidence"] == 95
    # quiet: nothing in your feed, but the lab's history has it
    feed1 = c.get("/api/phone/state").json()["feed"]
    assert [f["id"] for f in feed1] == [f["id"] for f in feed0]
    assert any(e["type"] == "lab" and "Zed" in (e.get("text") or "") for e in w.history.events.values())
    # you can edit yourself too
    r = c.post(f"/api/phone/editor/person/{me}", json={"traits": {"discipline": 99}, "money": 1000}).json()
    assert r["is_me"] and r["traits"]["discipline"] == 99 and r["money"] == 1000


def test_edit_any_relationship_presets_and_numbers():
    c, api = _story()
    w = api.lab.w
    ppl = c.get("/api/phone/editor").json()["people"]
    me = ppl[0]["id"]
    a, b = [p["id"] for p in ppl if not p["me"] and not p["family"]][:2]
    # numbers, both directions, between two other people
    p = c.post(f"/api/phone/editor/pair/{a}/{b}", json={"ab": {"affection": 90, "trust": 85, "familiarity": 90}, "ba": {"affection": -60}}).json()
    assert p["ab"]["label"] == "best friend" and p["ba"]["label"] == "dislikes"
    assert w.rels[(a, b)].affection == 90 and w.rels[(b, a)].affection == -60
    # attraction past the line is a crush (and they're into them now)
    p = c.post(f"/api/phone/editor/pair/{me}/{a}", json={"ab": {"attraction": 85, "familiarity": 40}}).json()
    assert p["ab"]["crush"] is True
    # dating is real: it ends whoever they were with
    c.post(f"/api/phone/editor/pair/{a}/{b}", json={"preset": "dating"})
    assert w.chars[a].flags.get("partner") == b and w.chars[b].flags.get("partner") == a
    p = c.post(f"/api/phone/editor/pair/{me}/{a}", json={"preset": "dating"}).json()
    assert p["dating"] and w.chars[me].flags.get("partner") == a and w.chars[b].flags.get("partner") is None
    assert "ex" in (w.bond(a, b) or {}).get("roles", [])
    # and back to friends: not dating anymore
    p = c.post(f"/api/phone/editor/pair/{me}/{a}", json={"preset": "friend"}).json()
    assert not p["dating"] and w.chars[me].flags.get("partner") is None and "partner" not in p["roles"]
    p = c.post(f"/api/phone/editor/pair/{me}/{a}", json={"preset": "strangers"}).json()
    assert p["ab"]["label"] == "stranger" and p["ab"]["affection"] == 0
    assert c.post(f"/api/phone/editor/pair/{me}/{a}", json={"preset": "soulmates"}).status_code == 422
    assert c.post(f"/api/phone/editor/pair/{me}/{a}", json={"ab": {"affection": 400}}).status_code == 422
    assert c.post(f"/api/phone/editor/pair/{me}/{me}", json={"preset": "friend"}).status_code == 422


def test_the_editor_switch():
    c, api = _story()
    assert c.get("/api/phone/state").json()["control"]["editor"] is True  # on to start
    assert c.post("/api/story/control", json={"editor": False}).json()["editor"] is False
    assert c.get("/api/phone/editor").status_code == 403
    me = api.lab.w.meta["protagonist"]
    assert c.post(f"/api/phone/editor/person/{me}", json={"mood": 90}).status_code == 403
    c.post("/api/story/control", json={"editor": True})
    assert c.get("/api/phone/editor").status_code == 200
