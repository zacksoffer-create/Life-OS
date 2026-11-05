"""The phone: pets and their chores, texting, contacts, first-person text, looks."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import messages, moments, pets, pov  # noqa: E402
from lifeos.appearance import look_of  # noqa: E402
from lifeos.engine import Simulation  # noqa: E402
from lifeos.story import begin, create_story  # noqa: E402
from tests.test_story import spec  # noqa: E402


def story(pet=True, **kw):
    s = spec(per=6, **kw)
    s["family"]["pet"] = {"species": "dog", "name": "Buster"} if pet else None
    w = create_story(s)
    sim = Simulation(w)
    begin(sim)
    moments.resolve(sim, moments.pending(w)[0]["id"], None)
    return w, sim


def test_family_dog_is_a_real_pet_with_a_one_time_chore_setup():
    w, sim = story()
    p = w.meta["protagonist"]
    hp = pets.household_pets(w, w.chars[p].household_id)
    assert len(hp) == 1 and hp[0]["name"] == "Buster" and hp[0]["species"] == "dog"
    pid = hp[0]["id"]
    assert pets.setup_needed(w, pid)
    sib = sim.siblings(p)[0]
    pets.set_duties(sim, pid, {"feed_am": "parents", "feed_pm": "rotate", "walk": "me", "bath": sib})
    assert not pets.setup_needed(w, pid)
    with pytest.raises(ValueError):
        pets.set_duties(sim, pid, {"walk": "the-neighbor"})
    assert pets.owner_today(sim, hp[0], "walk") == p
    sim.advance_days(10)
    pet = pets.pets(w)[pid]
    assert pet["bond"][p] > 40 and pet["streaks"].get("me", 0) + sum(1 for e in w.history.events.values() if e["type"] == "pet"
                                                                    and e.get("outcome") == "chore_missed") >= 1
    assert "family" in messages.phone(w)["threads"]


def test_pet_menu_everything_is_a_quick_tap():
    w, sim = story()
    pid = next(iter(pets.pets(w)))
    out = pets.quick(sim, pid, "treat")
    assert "treat" in out["text"].lower()
    for _ in range(2):
        pets.quick(sim, pid, "treat")
    with pytest.raises(ValueError):
        pets.quick(sim, pid, "treat")
    # the park (and walks, play, training) are quick taps now: they happen right away and never use up your free time
    p = w.meta["protagonist"]
    day, phase = w.day, w.phase
    out = pets.quick(sim, pid, "park")
    assert out["text"] and (w.day, w.phase) == (day, phase)
    assert any(e["type"] == "pet_park" and p in e["actors"] for e in w.history.events.values())
    with pytest.raises(ValueError):
        pets.queue(sim, pid, "park")  # nothing to plan for later anymore


def test_asking_for_a_pet_and_adopting_one():
    w, sim = story(pet=False)
    p = w.meta["protagonist"]
    assert not pets.household_pets(w, w.chars[p].household_id)
    with pytest.raises(ValueError):
        pets.adopt(sim, "dog", "Moose")  # ask first
    res = pets.ask_for_pet(sim, "dog")
    assert "yes" in res and res["text"]
    with pytest.raises(ValueError):
        pets.ask_for_pet(sim, "dog")  # too soon
    w.meta["pet_approved"] = {"species": "dog", "day": w.day}
    v = pets.adopt(sim, "dog", "Moose", breed="Beagle", coat="tricolor")
    assert v["name"] == "Moose" and v["breed"] == "Beagle" and v["setup_needed"]
    assert any(m["kind"] == "pet_adopted" for m in messages.phone(w)["threads"]["family"]["msgs"])


def test_texts_come_from_what_happens_and_replies_matter():
    w, sim = story()
    sim.advance_days(21)
    ph = messages.phone(w)
    assert ph["threads"], "three weeks in, somebody has texted"
    p = w.meta["protagonist"]
    friend = next(o for o in ph["contacts"] if o in w.chars and o not in sim.siblings(p))
    before = w.ensure_rel(friend, p, w.day).affection
    opts = {o["kind"] for o in messages.text_options(sim, friend)}
    assert "hey" in opts and "hang" in opts
    res = messages.text_first(sim, friend, "hey")
    assert res["result"] in ("replied", "read")
    from lifeos import chat
    bar = chat.view(sim, friend)
    assert bar["can_type"] and (bar["suggestions"] or bar["status"] == "done"), "the conversation keeps going until they wrap it up"
    th = next((t for t in ph["threads"].values() for m in t["msgs"] if messages._reply_open(sim, m) and not m["replies"][0]["fx"].startswith(("moment", "invite"))), None)
    if th:
        m = next(m for m in th["msgs"] if messages._reply_open(sim, m) and not m["replies"][0]["fx"].startswith(("moment", "invite")))
        messages.reply(sim, th["id"], m["id"], 0)
        assert m["chosen"] == 0 and th["msgs"][-1]["from"] in ("me",) + tuple(th["members"]) + tuple(x["id"] for x in messages.parent_names(sim))
    assert w.ensure_rel(friend, p, w.day).affection >= before - 5


def test_making_plans_by_text_means_they_show_up():
    w, sim = story()
    p = w.meta["protagonist"]
    friend = next(o for o, r in sorted(w.out[p].items(), key=lambda x: -x[1].affection) if o not in sim.siblings(p))
    messages.add_contact(sim, friend)
    w.meta.setdefault("control", {})["queued"] = {"action": "hang_out", "target": friend, "agreed": True, "day": w.day}
    for _ in range(30):
        if "queued" not in w.meta["control"]:
            break
        sim.step()
    hang = [e for e in w.history.events.values() if e["type"] == "interact.hang_out" and p in e["actors"] and friend in e["targets"]]
    assert hang and hang[-1]["outcome"] not in ("declined",)


def test_second_person_text():
    w, sim = story()
    me = w.chars[w.meta["protagonist"]]
    assert pov.second_person(f"{me.first} made Guilford Football varsity!", me) == "You made Guilford Football varsity!"
    assert pov.second_person(f"{me.first} was named captain.", me) == "You were named captain."
    assert pov.second_person(f"Danny texted {me.first}.", me) == "Danny texted you."
    assert pov.second_person(f"{me.first}'s dog is happy.", me) == "Your dog is happy."


def test_everyone_has_a_look_and_custom_looks_stick():
    s = spec(per=6)
    s["protagonist"]["look"] = {"skin": "olive", "hair": "curly_short", "hair_color": "black", "glasses": True}
    w = create_story(s)
    me = w.chars[w.meta["protagonist"]]
    lk = look_of(me)
    assert lk["skin"] == "olive" and lk["hair"] == "curly_short" and lk["glasses"] is True and lk["eyes"]
    assert all(look_of(c)["skin"] for c in w.chars.values())
    from lifeos.story import StoryError, validate_story
    bad = spec()
    bad["protagonist"]["look"] = {"hair": "mohawk"}
    with pytest.raises(StoryError):
        validate_story(bad)


def test_phone_api_flow():
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    s = spec(per=6)
    s["family"]["pet"] = {"species": "dog", "name": "Buster"}
    assert c.post("/api/story/new", json={"spec": s}).status_code == 200
    st = c.get("/api/phone/state").json()
    assert st["active"] and st["scene"]["art"] and st["moments"] and st["pet_setup_needed"]
    assert c.post(f"/api/phone/moment/{st['moments'][0]['id']}", json={"index": 0}).json()["lines"]
    pid = st["pets"][0]["id"]
    assert c.post(f"/api/phone/pet/{pid}/setup", json={"duties": {"walk": "me"}}).status_code == 200
    assert not c.get("/api/phone/state").json()["pet_setup_needed"]
    c.post("/api/story/advance", json={"until": "decision"})
    ch = c.get("/api/phone/choices").json()
    if ch["ready"]:
        assert ch["options"] and all(o["text"] for o in ch["options"])
        out = c.post("/api/phone/choose", json={"index": ch["options"][0]["index"]}).json()
        assert "lines" in out and "chips" in out
    assert c.post(f"/api/phone/pet/{pid}/do", json={"activity": "cuddle"}).json()["done"]
    assert c.get("/api/phone/contacts").json()["groups"]
    assert c.get("/api/phone/threads").status_code == 200
    assert c.get("/api/net").json()["port"]


def test_character_worksheet_round_trip():
    import io
    from openpyxl import load_workbook
    from lifeos import worksheet
    from lifeos.story import validate_story
    wb = load_workbook(io.BytesIO(worksheet.build_workbook()))
    assert {"Start Here", "Story & Family", "You", "Siblings", "Your People", "Reference"} <= set(wb.sheetnames)

    def put(ws, code, col, val):
        row = next(i for i in range(2, ws.max_row + 1) if ws.cell(row=i, column=1).value == code)
        ws.cell(row=row, column=col, value=val)
    you = wb["You"]
    for k, v in {"first": "Zack", "gender": "m", "grade": 9, "height_ft": 5, "height_in": 10, "pos:baseball": "SS",
                 "traits:discipline": 72, "look:glasses": "yes"}.items():
        put(you, k, 4, v)
    put(wb["Story & Family"], "pet", 4, "dog")
    put(wb["Story & Family"], "pet_name", 4, "Buster")
    sib = wb["Siblings"]
    for col, (n, g) in enumerate([("Mike", "m"), ("Ally", "f"), ("Jen", "f")], 4):
        put(sib, "first", col, n)
        put(sib, "gender", col, g)
    put(sib, "twin_of", 6, "S2")
    put(sib, "path", 4, "uconn:basketball")
    out = io.BytesIO()
    wb.save(out)
    spec = worksheet.parse_workbook(out.getvalue())
    validate_story(spec)
    assert spec["protagonist"]["body"]["height_in"] == 70 and spec["protagonist"]["look"]["glasses"] is True
    assert spec["siblings"][0]["path"] == {"college": "uconn", "sport": "basketball"} and spec["siblings"][2]["twin_of"] == "S2"
    assert spec["family"]["pet"] == {"species": "dog", "name": "Buster"}
    md = worksheet.guide_markdown()
    assert "```json" in md and "uconn" in md
