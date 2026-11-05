"""It takes more for a girl to ask a guy out than the other way around (a rule you can turn up, down, or off)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _setup():
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    from tests.test_story import spec
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    assert c.post("/api/story/new", json={"spec": spec(per=6)}).status_code == 200
    return c, api.lab.sim


def _ask_terms(sim, asker, target, attraction, perceived):
    from lifeos.decision import Cand, _context
    w = sim.w
    r = w.ensure_rel(asker, target, w.day)
    r.attraction, r.perceived = attraction, perceived
    terms = _context(sim, w.chars[asker], Cand(sim.cat.actions["ask_out"], target, None, ""), {"events": []})
    return sum(v for _, v, _ in terms)


def _bar(sim, asker, target):
    from lifeos.decision import Cand, _context
    terms = _context(sim, sim.w.chars[asker], Cand(sim.cat.actions["ask_out"], target, None, ""), {"events": []})
    return [v for label, v, _ in terms if label == "she'd rather he asked"]


def test_a_girl_needs_more_to_ask_a_guy_out_and_the_rule_sets_how_much():
    c, sim = _setup()
    w = sim.w
    me = w.meta["protagonist"]
    fam = set(sim.siblings(me)) | {me}
    studs = [x for x in w.chars.values() if x.role == "student" and x.status == "active" and x.id not in fam]
    girl = next(x for x in studs if x.gender == "f")
    guy = next(x for x in studs if x.gender == "m" and x.id != girl.id)
    guy2 = next(x for x in studs if x.gender == "m" and x.id not in (guy.id,))
    girl2 = next(x for x in studs if x.gender == "f" and x.id != girl.id)
    her = _ask_terms(sim, girl.id, guy.id, 62, 55)
    c.post("/api/story/control", json={"girl_asks_guy": 0})
    same = _ask_terms(sim, girl.id, guy.id, 62, 55)
    c.post("/api/story/control", json={"girl_asks_guy": 1})
    assert her < same - 6  # same feelings, she's a lot less likely to make the move than a guy would be
    # she gets there when she's really into him and sure he likes her
    keen = _ask_terms(sim, girl.id, guy.id, 95, 90)
    assert keen > her + 6 and _bar(sim, girl.id, guy.id)[0] > -6.5
    # turned up: even less; off: the same as a guy
    r = c.post("/api/story/control", json={"girl_asks_guy": 3})
    assert r.status_code == 200 and r.json()["girl_asks_guy"] == 3
    assert _ask_terms(sim, girl.id, guy.id, 62, 55) < her - 6
    c.post("/api/story/control", json={"girl_asks_guy": 0})
    assert _bar(sim, girl.id, guy.id) == [] and _bar(sim, guy2.id, girl2.id) == []
    c.post("/api/story/control", json={"girl_asks_guy": 1})
    assert len(_bar(sim, girl.id, guy.id)) == 1 and _bar(sim, guy2.id, girl2.id) == []  # only her asking him
    c.post("/api/story/control", json={"girl_asks_guy": 0})
    assert c.post("/api/story/control", json={"girl_asks_guy": 7}).status_code == 422
    assert c.get("/api/phone/state").json()["control"]["girl_asks_guy"] == 0
