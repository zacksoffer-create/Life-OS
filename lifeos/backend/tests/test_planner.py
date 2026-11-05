"""Your day at a glance: the parts of today, what needs you, the week ahead, and choices that say why they're there."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import messages, moments, pets, planner  # noqa: E402
from lifeos.calendar import DECISION_SLOTS  # noqa: E402
from tests.test_phone import story  # noqa: E402


def to_decision(sim, w, me):
    for _ in range(40):
        for m in moments.pending(w):
            moments.resolve(sim, m["id"], None)
        if sim.current_phase() in DECISION_SLOTS and me.id in sim.slot_actors(sim.current_phase()) and sim.options_for(me.id):
            return sim.options_for(me.id)
        sim.step()
    raise AssertionError("never got to a decision")


def options(sim, w, me):
    from lifeos.phone_api import phrase
    slot, dec = sim.options_for(me.id)
    out = []
    for i, cd in enumerate(dec["cands"]):
        o = {"index": i, "action": cd.a["id"], "label": cd.a["label"], "category": cd.a["category"], "risk": cd.a["risk"],
             "target": cd.target if isinstance(cd.target, str) and cd.target in w.chars else None, "target_name": sim.target_name(cd)}
        o["text"] = phrase(sim, o)
        out.append(o)
    return out


def test_the_day_strip_the_plate_and_the_week():
    w, sim = story()
    me = w.chars[w.meta["protagonist"]]
    sim.advance_days(16)
    to_decision(sim, w, me)
    t = planner.today(sim)
    phases = sim.phases()
    assert [s["phase"] for s in t["strip"]] == phases
    now = [s for s in t["strip"] if s["state"] == "now"]
    assert len(now) == 1 and now[0]["phase"] == sim.current_phase()
    assert all(s["state"] == "done" for s in t["strip"][:w.phase])
    assert len(t["week"]) == 7 and t["week"][0]["n"] == 0
    # something lands on the calendar tomorrow: it shows in the week and on your plate
    w.calendar.append({"day": w.day + 1, "kind": "exam", "slot": "classes", "name": "Chem quiz", "weight": 1, "key": "exam:test:1"})
    # a friend texts you something that wants an answer
    friend = next(o for o, r in w.out[me.id].items() if w.chars[o].role != "staff" and o not in sim.siblings(me.id))
    messages.post(sim, f"dm:{friend}", friend, "you coming tonight?", replies=messages._replies("chatter_plans", "x"))
    t = planner.today(sim)
    titles = [p["title"] for p in t["plate"]]
    assert any("Chem quiz tomorrow" == x for x in titles), titles
    assert any(w.chars[friend].first in x and "waiting" in x for x in titles), titles
    assert next(p for p in t["plate"] if "waiting" in p["title"])["go"] == f"phone/thread/dm:{friend}"
    assert any(i["label"] == "Chem quiz" for i in t["week"][1]["items"])
    # a test you already took this morning isn't on your plate anymore
    w.calendar.append({"day": w.day, "kind": "exam", "slot": sim.phases()[0], "name": "Spanish quiz", "weight": 1, "key": "exam:test:0"})
    assert not any("Spanish quiz" in p["title"] for p in planner.today(sim)["plate"])
    # someone you used to be close with, two weeks without a word: you're drifting
    r = w.rels[(me.id, friend)]
    r.affection, r.last_day = 70, w.day - 14
    assert any(p["title"] == f"{w.chars[friend].first}, 14 days" for p in planner.today(sim)["plate"])


def test_choices_say_why_and_sort_into_should_want_could():
    w, sim = story()
    me = w.chars[w.meta["protagonist"]]
    sim.advance_days(14)
    to_decision(sim, w, me)
    w.calendar.append({"day": w.day + 1, "kind": "exam", "slot": "classes", "name": "Bio quiz", "weight": 1, "key": "exam:test:2"})
    opts = planner.annotate(sim, me, options(sim, w, me))
    assert all(o["group"] in ("should", "want", "could") and o["reason"] for o in opts)
    order = [o["group"] for o in opts]
    assert order == sorted(order, key=["should", "want", "could"].index), "should first, then want, then could"
    study = [o for o in opts if o["action"] in ("study", "study_at_lunch")]
    if study:
        assert study[0]["group"] == "should" and study[0]["reason"] == "Bio quiz tomorrow"
    friend = next((o for o in opts if o.get("target") and o["action"] in ("sit_with", "hang_out", "chat_online")), None)
    if friend:
        r = w.rels[(me.id, friend["target"])]
        r.affection, r.last_day = 70, w.day - 10
        again = next(o for o in planner.annotate(sim, me, options(sim, w, me)) if o["index"] == friend["index"])
        assert again["group"] == "want" and again["reason"] == "10 days since you talked"


def test_a_choice_saved_for_later_happens_then():
    w, sim = story(pet=False)
    me = w.chars[w.meta["protagonist"]]
    pick = None
    for _ in range(40):
        to_decision(sim, w, me)
        opts = planner.annotate(sim, me, options(sim, w, me))
        pick = next((o for o in opts if o["later"] and o["action"] in ("study", "rest", "hobby", "practice_skill", "train")), None)
        if pick:
            break
        sim.act_as(me.id, opts[0]["index"])
    assert pick, "somewhere in a few days there's a choice that can wait"
    nxt = planner._next_slot(sim)
    plan = planner.save_for_later(sim, pick)
    assert plan["slot"] == nxt and w.meta["control"]["queued"]["slot"] == nxt
    assert any(s.get("kind") == "planned" for s in planner.strip(sim, me))
    # now: something else happens in this slot; the plan waits for its own
    sim.step()
    while sim.current_phase() != nxt:
        assert w.meta["control"].get("queued"), "the plan waits for its part of the day"
        sim.step()
    before = w.history.next_event
    sim.step()
    mine = [e for eid, e in w.history.events.items() if eid >= before and me.id in e["actors"] + e["targets"]]
    assert not w.meta["control"].get("queued"), "the plan is used up in its slot"
    # you did it, unless somebody pulled you into something else first (plans can get interrupted, like in life)
    assert any(e["type"] == pick["action"] for e in mine) or any(me.id in e["targets"] for e in mine), [e["type"] for e in mine]


def test_phone_today_and_later_routes():
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    from tests.test_story import spec
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    assert c.post("/api/story/new", json={"spec": spec(per=6)}).status_code == 200
    for m in c.get("/api/phone/state").json()["moments"]:
        c.post(f"/api/phone/moment/{m['id']}", json={"index": 0})
    c.post("/api/story/advance", json={"until": "decision"})
    t = c.get("/api/phone/today").json()
    assert t["strip"] and len(t["week"]) == 7 and isinstance(t["plate"], list)
    ch = c.get("/api/phone/choices").json()
    if ch["ready"]:
        assert all(o.get("group") and o.get("reason") is not None for o in ch["options"])
        assert ch["options"][0]["group"] in ("should", "want", "could")
        later = next((o for o in ch["options"] if o.get("later")), None)
        if later:
            r = c.post("/api/phone/later", json={"index": later["index"]})
            assert r.status_code == 200 and "Saved" in r.json()["note"]
            assert c.get("/api/phone/state").json()["queued"]
        no = next((o for o in ch["options"] if not o.get("later")), None)
        if no:
            assert c.post("/api/phone/later", json={"index": no["index"]}).status_code == 409


def test_invites_never_override_your_pick_or_answer_for_you():
    w, sim = story(pet=False)
    me = w.chars[w.meta["protagonist"]]
    assert not w.meta["control"]["ask_invites"], "the default: you don't get stopped for invites"
    asked = []
    for _ in range(60):
        to_decision(sim, w, me)
        opts = options(sim, w, me)
        mine = next((o for o in opts if o["action"] in ("study", "rest", "hobby", "practice_skill", "train", "sit_alone", "study_at_lunch")), opts[0])
        before = w.history.next_event
        sim.act_as(me.id, mine["index"])
        for eid, e in w.history.events.items():
            if eid >= before and e["type"] in ("interact.hang_out", "interact.date") and me.id in e["targets"] and me.id not in e["actors"]:
                asked.append(e)
        if len(asked) >= 2:
            break
    assert asked, "over a few weeks of picks, somebody asks you to hang out"
    for e in asked:
        assert e["outcome"] == "invited", (e["outcome"], e.get("text"))
    inv = [i for i in w.meta["inbox"] if i.get("later")]
    assert inv and all(i["status"] in ("pending", "expired", "accepted", "declined") for i in inv)
    # they texted you to try again, and it's yours to answer
    t = messages.phone(w)["threads"].get(f"dm:{inv[0]['from']}")
    assert t and any(m.get("ctx", {}).get("invite") == inv[0]["id"] and m["replies"] for m in t["msgs"])
    # say yes: the plan says what and with whom
    w.meta["control"]["queued"] = {"invite": inv[0]["id"]}
    label = planner.plan_label(sim, w.meta["control"]["queued"])
    first = w.chars[inv[0]["from"]].first
    assert label in (f"Hanging out with {first}, next time you're free", f"Going out with {first}, next time you're free"), label
