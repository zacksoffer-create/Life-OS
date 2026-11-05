"""Drama and gossip: what you hear, what you do with it, friends fighting, triangles, falling out and making up."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class Always:
    """An rng that always says yes."""
    def random(self):
        return 0.0

    def gauss(self, *_):
        return 0.0


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
    w = api.lab.w
    me = w.chars[w.meta["protagonist"]]
    sibs = set(api.lab.sim.siblings(me.id))
    ppl = [p["id"] for p in c.get("/api/phone/editor").json()["people"] if not p["me"] and p["id"] not in sibs and p["role"] == "student"]
    return c, api, me, ppl


def _pick(c, kind, label_has=None, index=None):
    m = next(m for m in c.get("/api/phone/state").json()["moments"] if m["kind"] == kind)
    i = index if index is not None else next(i for i, ch in enumerate(m["choices"]) if label_has in ch["label"])
    return m, c.post(f"/api/phone/moment/{m['id']}", json={"index": i}).json()


def test_gossip_reaches_you_and_you_decide_what_to_do_with_it():
    from lifeos import drama, social
    c, api, me, ppl = _story()
    w = api.lab.w
    friend, other = ppl[0], ppl[1]
    c.post(f"/api/phone/editor/pair/{me.id}/{friend}", json={"preset": "best_friend"})
    rid = social.make_rumor(api.lab.sim, other, "rejected", f"{w.chars[other].name} asked someone out and got shut down", True, -0.3, 0.8,
                            None, [friend], None)
    drama._gossip_reaches_you(api.lab.sim, me, drama.state(w), Always())
    assert me.id in w.rumors[rid]["known_by"] and w.rumors[rid]["known_by"][me.id][1] == friend
    talk = c.get("/api/phone/scene").json()["talk"]
    t = next(x for x in talk if x["id"] == rid)
    assert t["from"] == w.chars[friend].first and not t["about_you"] and t["spread"]
    assert c.post("/api/phone/scene/rumor", json={"id": rid, "what": "deny"}).status_code == 409  # not about you
    r = c.post("/api/phone/scene/rumor", json={"id": rid, "what": "tell"}).json()
    assert other in w.rumors[rid]["known_by"] and any("heads-up" in l["text"] for l in r["lines"])
    assert c.post("/api/phone/scene/rumor", json={"id": rid, "what": "pass"}).status_code == 409  # once per rumor
    # about you: set the record straight, own it, or find out who started it
    rid2 = social.make_rumor(api.lab.sim, me.id, "fabricated", f"{me.name} cheated on the bio test", False, -0.6, 0.8, other, [me.id, friend], None)
    t2 = next(x for x in c.get("/api/phone/scene").json()["talk"] if x["id"] == rid2)
    assert t2["about_you"] and t2["true"] is False
    assert c.post("/api/phone/scene/rumor", json={"id": rid2, "what": "tell"}).status_code == 409
    r = c.post("/api/phone/scene/rumor", json={"id": rid2, "what": "find"}).json()
    assert r["lines"]


def test_two_friends_fall_out_and_you_pick_a_side_or_fix_it():
    from lifeos import drama
    c, api, me, ppl = _story()
    w = api.lab.w
    a, b = ppl[0], ppl[1]
    c.post(f"/api/phone/editor/pair/{me.id}/{a}", json={"preset": "best_friend"})
    c.post(f"/api/phone/editor/pair/{me.id}/{b}", json={"preset": "close_friend"})
    c.post(f"/api/phone/editor/pair/{a}/{b}", json={"preset": "close_friend"})
    assert drama._friends_fight(api.lab.sim, me, drama.state(w), Always())
    pair = {(x["a"], x["b"]) for x in [{"a": f["a"], "b": f["b"]} for f in drama.state(w)["fallouts"]]}
    fa, fb = next(iter(pair))
    assert w.rels[(fa, fb)].affection < 50
    assert c.get("/api/phone/scene").json()["fights"]
    before = w.rels[(fb, me.id)].affection
    m, r = _pick(c, "drama_sides", label_has=f"Side with {w.chars[fa].first}")
    assert w.rels[(fb, me.id)].affection < before and r["lines"]


def test_your_crush_gets_taken_and_you_tell_them_anyway():
    from lifeos import drama
    from lifeos.model import pair_key
    c, api, me, ppl = _story()
    w = api.lab.w
    crush, other = ppl[0], ppl[1]
    c.post(f"/api/phone/editor/pair/{me.id}/{crush}", json={"ab": {"attraction": 85, "familiarity": 60}, "ba": {"attraction": 90, "affection": 60}})
    c.post(f"/api/phone/editor/pair/{crush}/{other}", json={"preset": "dating"})
    w.bonds[pair_key(crush, other)]["since"]["partner"] = w.day  # just happened
    assert drama._crush_taken(api.lab.sim, me, drama.state(w), Always())
    m, r = _pick(c, "drama_crush_taken", label_has="Tell")
    assert r["lines"]
    assert w.chars[crush].flags.get("partner") in (me.id, other)


def test_someone_after_your_partner():
    from lifeos import drama
    c, api, me, ppl = _story()
    w = api.lab.w
    p, o = ppl[0], ppl[1]
    c.post(f"/api/phone/editor/pair/{me.id}/{p}", json={"preset": "dating"})
    c.post(f"/api/phone/editor/pair/{o}/{p}", json={"ab": {"attraction": 80, "familiarity": 40}})
    assert drama._partner(api.lab.sim, me, drama.state(w), Always())
    m, r = _pick(c, "drama_partner", label_has="Ask")
    assert m["ctx"]["other"] == o and r["lines"]


def test_falling_out_and_making_up():
    from lifeos import drama
    c, api, me, ppl = _story()
    w = api.lab.w
    f = ppl[0]
    c.post(f"/api/phone/editor/pair/{me.id}/{f}", json={"preset": "best_friend"})
    w.rels[(f, me.id)].affection = -10  # they went cold
    st = drama.state(w)
    drama._notice_cold(api.lab.sim, me, st)
    assert f in st["cold"]
    assert drama._fallout(api.lab.sim, me, st, Always())
    m, r = _pick(c, "drama_fallout", label_has="Give it time")
    assert f in st["makeup"]
    w.day = st["makeup"][f]
    assert drama._makeup(api.lab.sim, me, st, Always())
    m, r = _pick(c, "drama_makeup", label_has="Hear them out")
    assert w.rels[(f, me.id)].affection > 0
