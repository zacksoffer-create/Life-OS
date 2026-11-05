"""Big nights: a party or a dance plays out as a few scenes built around who's there, does real things, and ends with a recap."""
import os
import random
import sys
import time

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


def _people(api):
    w = api.lab.w
    me = w.chars[w.meta["protagonist"]]
    sibs = set(api.lab.sim.siblings(me.id))
    return me, [o for o in w.out.get(me.id, {}) if w.chars[o].role == "student" and o not in sibs][:9]


def _play(c, api, pick=0, limit=8):
    from lifeos import moments
    seen = []
    for _ in range(limit):
        pend = [m for m in moments.pending(api.lab.w) if m["kind"].startswith("night_")]
        if not pend:
            break
        m = c.get("/api/phone/state").json()["moments"][0]
        assert m["kind"].startswith("night_") and m["storyline"] and " of " in m["storyline"]
        assert "{" not in m["text"] and "{" not in m["title"] and all("{" not in ch["label"] for ch in m["choices"])
        assert len(m["choices"]) >= 2
        seen.append(m["kind"])
        i = min(pick, len(m["choices"]) - 1)
        r = c.post(f"/api/phone/moment/{m['id']}", json={"index": i}).json()
        if r.get("minigame"):
            cfg = r["minigame"]
            r = c.post(f"/api/phone/moment/{m['id']}", json={"index": i, "session": cfg["session"], "score": 6, "max": 6}).json()
        last = r
    return seen, last


def test_a_party_night_plays_out_and_ends_with_a_recap():
    from lifeos import engine, nights
    c, api = _story()
    sim, w = api.lab.sim, api.lab.w
    me, ppl = _people(api)
    host = ppl[0]
    key = f"party:{host}:{w.day}"
    w.parties[key] = {"key": key, "day": w.day, "host": host, "invited": [me.id] + ppl[1:], "slot": "evening"}
    sim.slot = engine.SlotState("evening")
    sim.slot.attend[("party", key)] = [me.id] + ppl[1:]
    sim.institutions.party(key, random.Random(3))
    st = w.meta["night"]
    assert st["event"] == f"{w.chars[host].first}'s party" and len(st["plan"]) == 4 and st["plan"][0] == "arrive"
    seen, last = _play(c, api)
    assert seen == ["night_" + b for b in st["plan"]]
    assert "night" not in w.meta
    assert any(l["text"].startswith("Your night:") for l in last["lines"])
    assert any(m["kind"] == "night" and w.chars[host].first in m["text"] for m in me.memories)
    eps = [e for e in w.meta.get("episodes", []) if e["kind"].startswith("night_")]
    assert len(eps) == 1 and len(eps[0]["choices"]) == 4  # one episode, every choice remembered


def test_your_crush_the_porch_and_maybe_more():
    from lifeos import nights
    c, api = _story()
    w = api.lab.w
    me, ppl = _people(api)
    crush = ppl[1]
    me.aptitudes["charisma"] = 90
    c.post(f"/api/phone/editor/pair/{me.id}/{crush}", json={"ab": {"attraction": 90, "affection": 60, "familiarity": 60},
                                                            "ba": {"attraction": 92, "affection": 70, "familiarity": 60}})
    nights.start(api.lab.sim, "party", "party:test", "Kai's party", [me.id] + ppl, host=ppl[0])
    st = w.meta["night"]
    assert st["cast"]["crush"] == crush
    m = c.get("/api/phone/state").json()["moments"][0]
    go = next(i for i, ch in enumerate(m["choices"]) if w.chars[crush].first in ch["label"])
    c.post(f"/api/phone/moment/{m['id']}", json={"index": go})
    assert w.meta["night"]["plan"][1] == "porch"  # you went looking: that's what happens next
    before = w.rels[(crush, me.id)].attraction
    m = c.get("/api/phone/state").json()["moments"][0]
    assert m["kind"] == "night_porch" and m["ctx"]["them"] == crush
    r = c.post(f"/api/phone/moment/{m['id']}", json={"index": 0}).json()
    assert w.rels[(crush, me.id)].attraction != before
    if w.meta["night"]["kissed"] == crush:
        assert me.flags.get("partner") == crush and any("together" in l["text"] for l in r["lines"])


def test_a_dance_with_a_date_has_the_slow_song_and_the_dance_off():
    from lifeos import nights
    c, api = _story()
    w = api.lab.w
    me, ppl = _people(api)
    nights.start(api.lab.sim, "dance", "dance:hc", "Homecoming Dance", [me.id] + ppl, date=ppl[0])
    assert w.meta["night"]["plan"] == ["getready_date", "dancefloor", "slow", "end"]
    seen, last = _play(c, api)
    assert seen[1] == "night_dancefloor" and "night" not in w.meta


def test_skipping_ahead_plays_the_night_for_you():
    from lifeos import nights
    c, api = _story()
    w = api.lab.w
    me, ppl = _people(api)
    nights.start(api.lab.sim, "party", "party:skip", "Kai's party", [me.id] + ppl, host=ppl[0], busted=True)
    assert w.meta["night"]["plan"][-1] == "busted"
    j = c.post("/api/story/advance", json={"until": "day"}).json()
    while j.get("status") == "running":
        time.sleep(0.1)
        j = c.get("/api/sim/job").json()
    assert not any(m["kind"].startswith("night_") and m["status"] == "pending" for m in w.meta["moments"])
    assert "night" not in w.meta


def test_weekend_parties_show_up_and_picking_one_starts_the_night():
    c, api = _story()
    w = api.lab.w
    ms, tried = [], 0
    for _ in range(300):
        ch = c.get("/api/phone/choices").json()
        party = next((o for o in ch.get("options") or [] if o.get("action") == "go_to_party"), None)
        if party:
            tried += 1
            r = c.post("/api/phone/choose", json={"index": party["index"]})
            assert r.status_code == 200
            ms = c.get("/api/phone/state").json()["moments"]
            if ms and ms[0]["kind"] == "night_arrive":
                break  # (a party the first weekend of school can flop: hardly anyone knows anyone yet)
        for m in c.get("/api/phone/state").json()["moments"]:
            c.post(f"/api/phone/moment/{m['id']}", json={"index": None})
        c.post("/api/story/advance", json={"until": "decision"})
    assert tried, "a weekend party should come up within a few weeks"
    assert ms and ms[0]["kind"] == "night_arrive" and "party" in ms[0]["title"]
    seen, last = _play(c, api)
    assert len(seen) == 4 and "night" not in w.meta
