"""Roles: what your storylines need from your story, in one list. Each role says who fills it, or who's close and what
they're missing, and can be picked, fixed or filled with someone made to fit (all of it groundwork for a replay)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import dialogue  # noqa: E402
from tests.test_story import spec  # noqa: E402

STORIES = """=== Court Rivals
cast: kayla = older sister, soccer
cast: jordan = friend of kayla
years: freshman

--- Kayla's Game
kayla: You came!
* "Obviously."
kayla: Front row then.

--- Jordan
jordan: Kayla talks about you.
* "Good things?"
jordan: Mostly.

=== Sister Stuff
years: freshman

--- Borrowed Car [with older_sister]
older_sister: You're not driving my car.
* "Please?"
older_sister: Once.

--- Date Night [if dating]
partner: So where are we going?
* "Diner."
partner: Classic.

--- Rex [if has pet]
You walk the dog.
* "Good boy."
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
    r = dialogue.add_script(STORIES)
    assert r["ok"], r.get("errors")
    api._dialogue_changed(api.lab)
    yield client, api
    dialogue.reload()


def _role(b, key):
    return next(r for r in b["roles"] if r["key"] == key)


def test_every_role_your_storylines_use_in_one_list(c):
    client, api = c
    b = client.get("/api/phone/roles").json()
    keys = {r["key"] for r in b["roles"]}
    assert {"slot:kayla", "slot:jordan", "kind:older_sister", "req:dating", "req:has_pet"} <= keys, keys
    kay = _role(b, "slot:kayla")
    assert kay["status"] == "missing" and kay["label"].startswith("an older sister") and kay["storylines"][0]["name"] == "Court Rivals"
    near = {n["first"]: n for n in kay["near"]}
    assert near["Ally"]["why"] == "doesn't play soccer" and near["Ally"]["fix"]["sport"] == "soccer", kay["near"]
    assert "Mike" in near and "is your brother" in near["Mike"]["why"] and not near["Mike"].get("fix")
    sis = _role(b, "kind:older_sister")
    assert sis["status"] == "open" and {o["first"] for o in sis["options"]} == {"Ally", "Jen"}
    date = _role(b, "req:dating")
    assert date["status"] == "missing" and "not dating" in date["note"] and date["near"] and date["near"][0]["fix"]["pair"] == "dating"
    assert b["open"] == sum(1 for r in b["roles"] if r["status"] == "missing")
    assert [r["status"] for r in b["roles"]] == sorted((r["status"] for r in b["roles"]), key=["missing", "open", "set"].index)


def test_fix_someone_close_and_they_fill_it(c):
    client, api = c
    w = api.lab.w
    ally = next(x.id for x in w.chars.values() if x.first == "Ally")
    b = client.post("/api/phone/roles/fix", json={"role": "slot:kayla", "char": ally, "how": {"sport": "soccer"}}).json()
    kay = _role(b, "slot:kayla")
    assert kay["status"] == "set" and kay["who"]["id"] == ally and kay["by"] == "you"
    assert dialogue.bound(api.lab.sim, "kayla") == ally
    gw = client.get("/api/story/groundwork").json()["rows"]
    assert {r["kind"] for r in gw} >= {"person", "slot"}, "the fix and the pick come back on a replay"
    d = _role(b, "req:dating")["near"][0]
    b = client.post("/api/phone/roles/fix", json={"role": "req:dating", "char": d["id"], "how": d["fix"]}).json()
    assert _role(b, "req:dating")["status"] == "set"


def test_pick_one_person_for_every_storyline_and_add_who_isnt_there(c):
    client, api = c
    w = api.lab.w
    jen = next(x.id for x in w.chars.values() if x.first == "Jen")
    b = client.post("/api/phone/roles/pick", json={"role": "kind:older_sister", "char": jen}).json()
    r = _role(b, "kind:older_sister")
    assert r["who"]["id"] == jen and r["by"] == "you"
    pk = r["storylines"][0]["id"]
    assert dialogue.pick_cast(api.lab.sim, w.chars[w.meta["protagonist"]], pk, "older_sister",
                              dialogue.candidates(api.lab.sim, w.chars[w.meta["protagonist"]], "older_sister")) == jen
    b = client.get("/api/phone/roles").json()
    assert _role(b, "slot:jordan")["after"] == "slot:kayla" and not _role(b, "slot:jordan")["can_add"], "Kayla first"
    assert client.post("/api/phone/roles/add", json={"role": "slot:kayla"}).json()["fits"]
    j = client.post("/api/phone/roles/add", json={"role": "slot:jordan"}).json()
    assert j["fits"] and _role(j["board"], "slot:jordan")["who"]["id"] == j["id"]
    bad = client.post("/api/phone/roles/pick", json={"role": "kind:older_sister", "char": next(x.id for x in w.chars.values() if x.first == "Mike")})
    assert bad.status_code == 422
    assert client.post("/api/phone/roles/add", json={"role": "req:has_pet"}).status_code == 422
    # all of it comes back on a replay
    client.post("/api/story/restart", json={})
    b = client.get("/api/phone/roles").json()
    assert _role(b, "kind:older_sister")["who"]["id"] == jen and _role(b, "slot:jordan")["status"] == "set"
