"""Your group (the boys), zero maintenance, and pets that never use up your free time."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import messages, moments, pets, phone_api, squad  # noqa: E402
from tests.test_hangouts import _to_slot, _world  # noqa: E402


def _boys():
    w, sim, me, pals = _world(friends=6)
    boys = [p for p in pals if w.chars[p].gender == me.gender][:3]
    for p in pals:
        if p not in boys:
            w.rels[(me.id, p)].affection = 20
    w.meta.pop("squad", None)
    return w, sim, me, boys


def test_your_group_forms_on_its_own_from_your_closest_friends():
    w, sim, me, boys = _boys()
    s = squad.state(sim)
    assert s and set(s["ids"]) <= set(boys) | set(w.out[me.id]) and len(s["ids"]) >= 2
    assert not any(i in sim.siblings(me.id) for i in s["ids"])
    genders = {w.chars[i].gender for i in s["ids"]} | {me.gender}
    assert s["name"] == ("the boys" if genders == {"m"} else "the girls" if genders == {"f"} else "the crew")
    v = squad.view(sim)
    assert v["name"] == s["name"] and len(v["members"]) == len(s["ids"]) and 0 <= v["cohesion"] <= 100


def test_hop_on_the_game_with_the_boys_is_one_choice():
    w, sim, me, boys = _boys()
    ch = _to_slot(sim, w, me, slots=("evening",))
    grp = [o for o in ch["options"] if o["action"] == "squad"]
    assert grp and all(o["section"] == "people" and o["crew"] and o["act"] for o in grp)
    game = next((o for o in grp if o["act"] == "game"), grp[0])
    s = squad.state(sim)
    assert game["text"] == squad.label(sim, game["act"], s)
    coh = s["cohesion"]
    r = phone_api.phone_choose({"index": game["index"], "crew": game["crew"], "act": game["act"]})
    ev = next(e for e in w.history.events.values() if e["type"] == "interact.hang_out" and e["data"].get("act") == game["act"])
    lines = squad.D()["acts"][game["act"]]["lines"]
    assert any(ev["text"].startswith(x.split("{")[0][:12]) for x in lines), ev["text"]
    assert ev["data"].get("crew"), "the rest of the group came"
    assert squad.state(sim)["cohesion"] > coh and squad.state(sim)["last_you"] == w.day
    scene = next((m for m in moments.pending(w) if m["kind"].startswith("hang_")), None)
    if scene and game["act"] == "game":
        assert scene["kind"].startswith("hang_game_"), scene["kind"]
    assert any(l["type"] == "interact.hang_out" for l in r["lines"])


def test_the_group_makes_plans_and_skipping_them_costs_almost_nothing():
    w, sim, me, boys = _boys()
    s = squad.state(sim)
    s["plan"] = {"day": w.day, "slot": "evening", "act": "game"}
    squad._chat(sim, s, "plan", "game")
    from lifeos import planner
    assert any(p["id"] == f"squad:{w.day}" for p in planner.today(sim)["plate"])
    t = messages.phone(w)["threads"]["squad"]
    assert t["kind"] == "group" and all(not m.get("replies") for m in t["msgs"]) and t["unread"] == 0
    assert not next(x for x in messages.threads_view(sim) if x["id"] == "squad")["needs_reply"], "their chat never needs you"
    coh, n = s["cohesion"], len(t["msgs"])
    squad.night(sim)
    assert squad.state(sim)["cohesion"] == coh - 1.5 and not squad.state(sim).get("plan")
    fomo = messages.phone(w)["threads"]["squad"]["msgs"][n:]
    assert len(fomo) == 1 and not fomo[0].get("replies"), "they went without you, and you hear about it (no answer needed)"


def test_game_nights_get_game_scenes():
    from lifeos import hangouts
    w, sim, me, boys = _boys()
    s = squad.state(sim)
    m = hangouts.maybe_scene(sim, me.id, s["ids"][0], "group", s["ids"][1:], "online", act="game")
    assert m and m["kind"].startswith("hang_game_")
    assert "{" not in m["text"], m["text"]


def test_pets_never_use_up_your_free_time():
    w, sim, me, pals = _world()
    ch = _to_slot(sim, w, me, slots=("evening", "day", "after_school"))
    assert not any(o["action"].startswith("pet_") for o in ch["options"])
    hp = pets.household_pets(w, me.household_id)
    if not hp:
        return
    pet = hp[0]
    pid = pet["id"]
    if pets.setup_needed(w, pid):
        pets.set_duties(sim, pid, pets.default_duties(sim, pet))
    v = pets.view(sim, pet)
    assert all(a["quick"] for a in v["activities"])
    phase = sim.current_phase()
    if pet["species"] == "dog":
        out = pets.quick(sim, pid, "walk")
        assert pet["today"].get("walk") == me.id and out["text"]
    out = pets.quick(sim, pid, "play")
    assert out["text"] and sim.current_phase() == phase, "a quick tap: time doesn't move"
    pets.quick(sim, pid, "clean")
    try:
        pets.quick(sim, pid, "clean")
        assert False, "once a day"
    except ValueError as e:
        assert "Already" in str(e)
