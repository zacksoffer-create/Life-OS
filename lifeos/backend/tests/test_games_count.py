"""One game day is one game: for a varsity or JV player, in the stats, the team record and the phone. Football scores add up."""
import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos.sports import football_score  # noqa: E402


def test_football_scores_are_touchdowns_and_field_goals():
    r = random.Random(7)
    for margin in (0.5, 3, 8, 15, 30, 55):
        for _ in range(40):
            a, b, (wtd, ltd) = football_score(margin, r)
            assert a > b >= 0
            assert any(7 * t + 3 * f == a for t in range(10) for f in range(8)) and 7 * wtd <= a
            assert any(7 * t + 3 * f == b for t in range(10) for f in range(8)) and 7 * ltd <= b


def _first_game(level):
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    from tests.test_story import spec
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    assert c.post("/api/story/new", json={"spec": spec(per=6)}).status_code == 200
    played = None
    for _ in range(400):
        w = api.lab.w
        me = w.chars[w.meta["protagonist"]]
        if "football" in me.memberships and level == "jv":
            w.groups["football"].setdefault("levels", {})[me.id] = "jv"
        st = c.get("/api/phone/state").json()
        for m in st["moments"]:
            if m["kind"] == "game_day" and played is None:
                i = next(k for k, ch in enumerate(m["choices"]) if "yourself" in ch["label"])
                r = c.post(f"/api/phone/moment/{m['id']}", json={"index": i}).json()
                c.post(f"/api/phone/moment/{m['id']}", json={"index": i, "session": r["minigame"]["session"], "score": 10, "max": 10})
                played = st["day"]
            else:
                r = c.post(f"/api/phone/moment/{m['id']}", json={"index": 0}).json()
                if r.get("minigame"):
                    c.post(f"/api/phone/moment/{m['id']}", json={"index": 0, "auto": True})
        if played is not None and api.lab.w.day > played:
            break
        j = c.post("/api/story/advance", json={"until": "moment"}).json()
        while j.get("status") == "running":
            time.sleep(0.1)
            j = c.get("/api/story/job").json()
    assert played is not None, "the season got to a game day"
    return c, api.lab.w


def test_one_game_day_is_one_game_varsity_and_jv():
    for level in ("varsity", "jv"):
        c, w = _first_game(level)
        me = w.chars[w.meta["protagonist"]]
        st = me.stats[next(k for k in me.stats if k.startswith("football:"))]
        assert st["games"] == 1 and st["level"] == level, (level, st)
        card = c.get("/api/phone/state").json()["teams"][0]
        assert card["level"] == level and card["record"]["w"] + card["record"]["l"] == 1, (level, card)
        mine = [e for e in w.history.events.values() if e["type"] == "game" and e.get("outcome") in ("win", "loss") and me.id in e["actors"]]
        assert len(mine) == 1, [e.get("text") for e in mine]


def _game_slot():
    """A story on the afternoon of the first football game, with you on varsity."""
    from lifeos import api, moments
    from lifeos.history import Effects
    from lifeos.storage import Store
    from tests.test_phone import story
    w, sim = story(pet=False)
    me = w.chars[w.meta["protagonist"]]
    it = next(i for i in w.calendar if i["kind"] == "game" and i["group"] == "football")
    sim.advance_days(it["day"] - w.day)
    if "football" not in me.memberships:
        Effects(w, None).join(me.id, "football", "test")
    w.groups["football"].setdefault("levels", {})[me.id] = "varsity"
    me.flags.pop("injured_until", None)
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    api.lab.replace_world(w)
    sim = api.lab.sim
    while sim.current_phase() != it["slot"]:
        for m in moments.pending(w):
            moments.resolve(sim, m["id"], None)
        sim.step()
    for m in moments.pending(w):
        moments.resolve(sim, m["id"], None)
    return api, w, sim, me, it


def test_on_game_day_you_just_play_and_skipping_still_says_so():
    from lifeos import phone_api
    api, w, sim, me, it = _game_slot()
    ch = phone_api.phone_choices()
    assert not ch["ready"] and ch["committed"]["kind"] == "game", "your game isn't a choice: you play"
    assert phone_api.phone_state()["committed"]["kind"] == "game"
    before = w.history.next_event
    sim.step()
    played = [e for eid, e in w.history.events.items() if eid >= before and e["type"] == "game" and e.get("outcome") in ("win", "loss")
              and e["data"].get("level") == "varsity"]
    assert played and me.id in played[0]["actors"]
    # the lab can still overrule it; then the team plays without you, and you hear about it
    api2, w2, sim2, me2, it2 = _game_slot()
    slot, dec = sim2.options_for(me2.id)
    other = next(i for i, cd in enumerate(dec["cands"]) if cd.a["id"] not in ("attend_event", "attend_practice"))
    before = w2.history.next_event
    sim2.act_as(me2.id, other)
    missed = [e for eid, e in w2.history.events.items() if eid >= before and e["type"] == "game" and e["outcome"] == "missed"]
    assert len(missed) == 1 and me2.id in missed[0]["actors"]


def test_a_saved_plan_waits_until_after_your_game():
    from lifeos import phone_api
    api, w, sim, me, it = _game_slot()
    w.meta["control"]["queued"] = {"action": "rest", "day": w.day}
    before = w.history.next_event
    sim.step()  # you didn't pick: the game slot runs on its own
    played = [e for eid, e in w.history.events.items() if eid >= before and e["type"] == "game" and e.get("outcome") in ("win", "loss")
              and e["data"].get("level") == "varsity"]
    assert played and me.id in played[0]["actors"], "you play your game"
    assert w.meta["control"].get("queued", {}).get("action") == "rest", "the plan is still waiting for your next free time"
    card = next(t for t in phone_api.phone_state()["teams"] if t["id"] == "football")
    assert card["mine"] == card["record"], card


def test_a_game_is_played_once_even_if_the_slot_runs_again():
    from lifeos import sports
    api, w, sim, me, it = _game_slot()
    g = w.groups["football"]
    sim.step()  # the game slot: the game is played
    rec = dict(g["record"])
    st = {k: dict(v) for k, v in me.stats.items()}
    from lifeos.engine import SlotState
    sim.slot = SlotState(it["slot"])  # the same slot again, say after a reload: you're there, the game isn't played twice
    sim.slot.attend[("event", it["key"])] = [me.id]
    sports.play_game(sim.institutions, it, sim.streams.get("collective", w.day, it["slot"]))
    sim.slot = None
    assert g["record"] == rec and sum(rec.values()) == 1
    assert {k: v["games"] for k, v in me.stats.items()} == {k: v["games"] for k, v in st.items()}
