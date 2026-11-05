"""Who can be into you: never family, never a teacher with a student, never someone outside who they're into. And a date
to the dance is someone who's actually into you (or your partner), not just a friend."""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import chat, decision, social  # noqa: E402
from lifeos.engine import Simulation  # noqa: E402
from lifeos.history import Effects  # noqa: E402
from lifeos.story import begin, create_story  # noqa: E402
from tests.test_story import spec  # noqa: E402


def _story():
    sim = Simulation(create_story(spec(per=8)))
    begin(sim)
    w = sim.w
    me = w.chars[w.meta["protagonist"]]
    keys = w.meta["story"]["keys"]
    return sim, w, me, {k: w.chars[v] for k, v in keys.items() if v in w.chars}


def _girl(sim, me, into_guys=True):
    w = sim.w
    g = next(c for c in w.students() if c.gender == "f" and c.household_id != me.household_id and abs((c.grade or 0) - me.grade) <= 1)
    g.attracted_to = ["m"] if into_guys else ["f"]
    return g


def test_attraction_never_grows_toward_family_a_teacher_or_outside_who_they_like():
    sim, w, me, k = _story()
    bro, bf, coach = k["bro"], k["bf"], k["coach"]
    bf.attracted_to = ["f"]
    girl = _girl(sim, me)
    fx = Effects(w, None)
    for who in (bro, bf, coach):
        fx.rel(who.id, me.id, "attraction", 30, "a party")
        fx.rel(me.id, who.id, "attraction", 30, "a party")
    assert all(w.rels[(x.id, me.id)].attraction == 0 for x in (bro, bf, coach))
    assert w.rels[(me.id, bro.id)].attraction == 0
    assert abs(fx.rel(girl.id, me.id, "attraction", 30, "a party") - 30) < 1e-6, "someone who could be into you still can be"
    assert abs(fx.rel(girl.id, me.id, "attraction", -10, "it got awkward") + 10) < 1e-6, "going down always works"
    assert not social.can_be_into(w, bro.id, me.id) and social.family(w, bro.id, me.id)
    assert chat.read(sim, bro.id)["label"] == "Family"


def test_a_dance_date_is_someone_into_you_not_a_friend_or_your_brother():
    sim, w, me, k = _story()
    bro, bf = k["bro"], k["bf"]
    girl = _girl(sim, me)
    for x in (bro, bf, girl):
        r = w.ensure_rel(x.id, me.id, w.day)
        r.affection, r.familiarity = 90.0, 90.0
    bf.attracted_to = ["f"]
    dance = {"key": "hc", "name": "Homecoming", "grades": None}
    act = {"id": "ask_to_dance", "target": "dance_date"}

    def asks(c):
        known = [(oid, r) for oid, r in w.out.get(c.id, {}).items() if oid in w.chars]
        return [t[0] for t in decision.targets(sim, c, act, "lunch", {"known": known, "dance": dance}, random.Random(1))]

    assert me.id not in asks(bro), "your brother never asks you to the dance"
    assert me.id not in asks(bf), "your best friend doesn't either, however close you are"
    assert me.id not in asks(girl), "close isn't enough: they have to be into you"
    w.rels[(girl.id, me.id)].attraction = 50.0
    assert me.id in asks(girl)


def test_old_saves_are_cleaned_once():
    sim, w, me, k = _story()
    bro, bf = k["bro"], k["bf"]
    bf.attracted_to = ["f"]
    for x in (bro, bf):
        r = w.ensure_rel(x.id, me.id, w.day)
        r.attraction, r.crush = 70.0, True
    w.dance_dates["hc"] = {bf.id: me.id, me.id: bf.id}
    w.meta.setdefault("moments", []).append({"id": "mo999", "kind": "asked_to_dance", "day": w.day, "status": "pending",
                                            "ctx": {"other": bro.id, "event": "Homecoming"}, "choices": []})
    w.meta.pop("romance_rules", None)
    Simulation(w)
    assert w.rels[(bro.id, me.id)].attraction == 0 and not w.rels[(bro.id, me.id)].crush
    assert w.rels[(bf.id, me.id)].attraction == 0
    assert w.dance_dates["hc"] == {}
    assert next(m for m in w.meta["moments"] if m["id"] == "mo999")["status"] == "resolved"
    w.rels[(bro.id, me.id)].attraction = 5.0  # once only: it doesn't run on every load
    Simulation(w)
    assert w.rels[(bro.id, me.id)].attraction == 5.0
