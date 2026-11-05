"""Cast slots: a storyline about one specific person (your older brother, the basketball star, a senior when you're a
freshman), bound once and kept for the whole story, shared by every pack that names the same slot, and never a sister.

The family here is the one from the brothers handoff: you (grade 9), twin sisters (grade 10), an older brother (grade 12)
who plays basketball."""
import copy
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import dialogue, moments  # noqa: E402
from tests.test_story import spec  # noqa: E402


@pytest.fixture(autouse=True)
def own_packs(tmp_path, monkeypatch):
    monkeypatch.setattr(dialogue, "USER_DIR", str(tmp_path / "dialogue"))
    dialogue.reload()
    yield
    dialogue.reload()


BROTHER = {"key": "bro", "first": "Mike", "gender": "m", "grade": 12, "archetype": "athlete",
           "interests": {"basketball": 95}, "skills": {"basketball": 80}, "positions": {"basketball": "PG"}}
TWINS = [{"key": "ally", "first": "Ally", "gender": "f", "grade": 10},
         {"key": "jen", "first": "Jen", "gender": "f", "grade": 10, "twin_of": "ally"}]


def _scene(sid, years, text, choices, **when):
    return {"id": sid, "title": f"{sid}", "who": "older_sibling", "text": text, "when": {"years": years, **when}, "choices": choices}


def _ok(label, *ops):
    return {"label": label, "ops": list(ops)}


# Stand-ins for the two real packs: same shape (older_sibling, remembered chains, a mini game, a texted version, freshman
# then sophomore chapters), written before cast slots existed.
BROTHERS = {"dialogue_pack": 1, "name": "Brothers: Same Team", "in_order": True, "scenes": [
    _scene("bro_team_01_first_morning", ["freshman"], "{them_first} drives you to your first day of high school. He's a senior. You're nobody.",
           [_ok("Ride with him.", ["remember", "bro_ride"], ["rel", "them", "affection", 3], ["say", "He plays your song. Twice."]),
            _ok("Take the bus.", ["rel", "them", "affection", -30], ["rel_back", "them", "trust", -30], ["say", "He looks hurt. He'd never say it."])]),
    _scene("bro_team_02_scrimmage", ["freshman"], "{them_first} pulls you into his scrimmage with the varsity guys.",
           [_ok("Play it yourself.", ["minigame", "basketball", {"great": [["remember", "bro_scrimmage_win"], ["say", "You hit the game winner over him."]],
                                                                "good": [["say", "You hold your own."]], "miss": [["say", "He blocks you. Twice."]]},
                                     {"base": 0.5, "athletic": 0.3}]),
            _ok("Just rebound for him.", ["rel", "them", "affection", 2]),
            _ok("Talk trash from the bench.", ["rel_back", "them", "respect", -4])], after=["bro_team_01_first_morning"]),
    _scene("bro_team_03_senior_night", ["freshman"], "Senior night. {them_first} hands you his warmup jacket before they call his name.",
           [_ok("Wear it to the game.", ["remember", "bro_jacket"]), _ok("Tell him he's corny.", ["rel_back", "them", "affection", 1])],
           after=["bro_team_02_scrimmage"]),
    _scene("bro_team_04_baseball", ["freshman"], "{them_first} skips a pickup run to watch your baseball game.",
           [_ok("Point at him after your hit.", ["rel", "them", "affection", 3]), _ok("Pretend you didn't see him.", ["rel_back", "them", "affection", -2])]),
    {**_scene("bro_team_05_college_call", ["sophomore"], "First practice without him. {them_first} calls from campus.",
              [_ok("Tell him everything.", ["remember", "bro_call"]), _ok("Keep it short.", ["rel_back", "them", "affection", -3])],
              after=["bro_team_03_senior_night"]), "by_text": "{them_first}: how's the team without me lol"},
    _scene("bro_team_06_visit", ["sophomore", "junior"], "{them_first} drives home for a weekend and you play one on one in the driveway.",
           [_ok("Make it a real game.", ["remember", "bro_visit"]), _ok("Let him win.", ["rel", "them", "affection", 2])], remembered=["bro_ride"]),
]}
FRIDAY = {"dialogue_pack": 1, "name": "Friday Nights: My Brother's Last Season", "in_order": True, "scenes": [
    _scene("fn_01_opening_night", ["freshman"], "Opening night. {them_first} finds you in the student section and points.",
           [_ok("Point back.", ["remember", "fn_courtside"]), _ok("Pretend to be embarrassed.", ["rel", "them", "affection", 1])]),
    _scene("fn_02_rivalry_game", ["freshman"], "{them_first} drops 30 in the rivalry game.",
           [_ok("Rush the court.", ["rel", "them", "affection", 3]), _ok("Text him after.", ["rel", "them", "affection", 1])],
           after=["fn_01_opening_night"]),
    _scene("fn_03_letter", ["sophomore"], "{them_first} mails you the program from his first college game.",
           [_ok("Hang it up.", ["remember", "fn_program"]), _ok("Text him a photo of it.", ["rel", "them", "affection", 2])],
           remembered=["fn_courtside"]),
]}
LOCK = {"slot": "lead_brother", "who": "older_brother", "sport": "basketball", "grade_offset": 3,
        "bond": {"familiarity": 95, "affection": 75, "trust": 75}, "floor": {"affection": 55, "trust": 55}, "replace": ["older_sibling"]}


def _client(siblings):
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    s = spec(per=6, siblings=siblings)
    assert c.post("/api/story/new", json={"spec": s}).status_code == 200
    for m in moments.pending(api.lab.w):
        moments.resolve(api.lab.sim, m["id"], None)
    return c, api


def _install(c, *packs):
    for p in packs:
        r = c.post("/api/dialogue/packs", json={"pack": copy.deepcopy(p)})
        assert r.status_code == 200, r.text


def _lock_both(c):
    ids = {p["name"]: p["id"] for p in c.get("/api/dialogue/packs").json()["packs"]}
    out = {}
    for name in ("Brothers: Same Team", "Friday Nights: My Brother's Last Season"):
        r = c.post(f"/api/dialogue/packs/{ids[name]}/lock-cast", json=LOCK)
        assert r.status_code == 200, r.text
        out[name] = r.json()
    return out, ids


def _sib(api, first):
    w = api.lab.w
    me = w.meta["protagonist"]
    return next(s for s in api.lab.sim.siblings(me) if w.chars[s].first == first)


def _them(c, api, sid):
    m = dialogue.try_scene(api.lab.sim, sid)
    them = m["ctx"]["them"]
    moments.resolve(api.lab.sim, m["id"], 0)
    return them


def test_the_validator_takes_cast_slots_and_the_handoff_spelling():
    pk = {"name": "x", "cast": {"lead_brother": {"relationship_to_player": "older_brother", "gender": "male",
                                                 "grade_offset_at_player_freshman": 3, "basketball_player": True,
                                                 "same_high_school_at_start": True, "bind_once": True}},
          "scenes": [{"id": "x_one", "who": "cast:lead_brother", "title": "t", "text": "{them_first} waves.",
                      "choices": [_ok("a", ["mood", 1]), _ok("b", ["mood", 2])]}]}
    r = dialogue.check(pk)
    assert r["ok"], r["errors"]
    n = dialogue.normalize_slot(pk["cast"]["lead_brother"])
    assert n == {"who": "older_brother", "gender": "m", "grade_offset": 3, "sport": "basketball", "bind": "first_scene"}
    bad = copy.deepcopy(pk)
    bad["scenes"][0]["who"] = "cast:nobody"
    bad["cast"]["lead_brother"]["gender"] = "female"
    msg = " | ".join(dialogue.check(bad)["errors"])
    assert "cast slot named 'nobody'" in msg and "doesn't match 'older_brother'" in msg


def test_both_packs_lock_onto_the_same_senior_brother_never_a_sister():
    c, api = _client([BROTHER] + TWINS)
    w, sim = api.lab.w, api.lab.sim
    me = w.chars[w.meta["protagonist"]]
    mike, ally, jen = _sib(api, "Mike"), _sib(api, "Ally"), _sib(api, "Jen")
    assert me.grade == 9 and w.chars[ally].grade == 10 and w.chars[jen].grade == 10 and w.chars[mike].grade == 12
    _install(c, BROTHERS, FRIDAY)
    assert set(dialogue.candidates(sim, me, "older_sibling")) == {mike, ally, jen}  # the problem: sisters fit older_sibling
    out, ids = _lock_both(c)
    assert out["Brothers: Same Team"]["locked"] == 6 and out["Friday Nights: My Brother's Last Season"]["locked"] == 3
    assert out["Brothers: Same Team"]["bound"]["id"] == mike
    assert w.meta["cast_slots"]["lead_brother"]["id"] == mike
    # the migration only changed who: same ids, text, choices, remembered facts
    new = {p["pack"]["name"]: p["pack"] for p in dialogue.packs() if p["source"] == "yours"}
    for old in (BROTHERS, FRIDAY):
        got = new[old["name"]]
        assert got["cast"]["lead_brother"]["who"] == "older_brother"
        for a, b in zip(old["scenes"], got["scenes"]):
            assert b["who"] == "cast:lead_brother" and {k: v for k, v in a.items() if k != "who"} == {k: v for k, v in b.items() if k != "who"}
    # every brother scene, in both packs, is Mike
    for sid in ("bro_team_01_first_morning", "fn_01_opening_night", "bro_team_04_baseball"):
        assert _them(c, api, sid) == mike
    cast = c.get(f"/api/dialogue/cast?pack={ids['Brothers: Same Team']}").json()
    slot = cast["slots"][0]
    assert slot["current"]["id"] == mike and "Friday Nights: My Brother's Last Season" in slot["shared_with"]
    assert [o["id"] for o in slot["options"]] == [mike]  # the sisters aren't even options


def test_he_stays_the_same_brother_after_he_graduates_and_the_memories_follow():
    c, api = _client([BROTHER] + TWINS)
    w, sim = api.lab.w, api.lab.sim
    me = w.chars[w.meta["protagonist"]]
    mike = _sib(api, "Mike")
    _install(c, BROTHERS, FRIDAY)
    _lock_both(c)
    assert _them(c, api, "bro_team_01_first_morning") == mike  # "Ride with him." -> remembers bro_ride (with Mike)
    assert _them(c, api, "fn_01_opening_night") == mike         # remembers fn_courtside
    assert w.meta["remembered"]["bro_ride"]["them"] == mike
    # a year later: you're a sophomore, he's in college (and not even on a team anymore)
    me.grade = 10
    for s in (_sib(api, "Ally"), _sib(api, "Jen")):
        w.chars[s].grade = 11
    M = w.chars[mike]
    M.grade, M.school, M.location, M.role = 13, "college", "away", "student"
    M.memberships = []
    M.skills["basketball"] = 10
    M.interests["basketball"] = 10
    assert mike not in dialogue.slot_candidates(sim, me, dialogue.slot_spec("lead_brother"))  # no longer "eligible"...
    assert dialogue.bound(sim, "lead_brother") == mike                                        # ...still the same person
    # the senior-year chapters were missed (scrimmage, senior night): the college arc isn't stranded
    for sid in ("bro_team_05_college_call", "bro_team_06_visit", "fn_03_letter"):
        assert _them(c, api, sid) == mike
    log = [x for x in w.meta["cast_log"] if x[1] == "lead_brother"]
    assert len(log) == 1 and log[0][2] == mike  # bound once, to him


def test_only_the_twin_sisters_no_brother_story_happens():
    c, api = _client(TWINS)
    w, sim = api.lab.w, api.lab.sim
    me = w.chars[w.meta["protagonist"]]
    _install(c, BROTHERS, FRIDAY)
    ids = {p["name"]: p["id"] for p in c.get("/api/dialogue/packs").json()["packs"]}
    r = c.post(f"/api/dialogue/packs/{ids['Brothers: Same Team']}/lock-cast", json=LOCK)
    assert r.status_code == 200 and r.json()["bound"] is None
    assert "lead_brother" not in w.meta.get("cast_slots", {})
    with pytest.raises(ValueError, match="nobody in your story fits 'lead_brother'"):
        dialogue.try_scene(sim, "bro_team_01_first_morning")
    for _ in range(40):  # weeks of mornings: none of his scenes ever start
        dialogue.maybe_scene(sim)
        w.day += 1
    assert not any(m["kind"].startswith("bro_team") for m in w.meta.get("moments", []))
    # the other pack still uses older_sibling, and either sister can be its person
    assert set(dialogue.candidates(sim, me, "older_sibling")) == {_sib(api, "Ally"), _sib(api, "Jen")}
    them = dialogue.try_scene(sim, "fn_01_opening_night")["ctx"]["them"]
    assert them in (_sib(api, "Ally"), _sib(api, "Jen"))


def test_inseparable_the_bond_holds_whatever_you_choose():
    c, api = _client([BROTHER] + TWINS)
    w = api.lab.w
    me = w.meta["protagonist"]
    mike = _sib(api, "Mike")
    _install(c, BROTHERS, FRIDAY)
    _lock_both(c)
    assert w.rels[(me, mike)].affection >= 75 and w.rels[(mike, me)].trust >= 75  # starts close (bond)
    m = dialogue.try_scene(api.lab.sim, "bro_team_01_first_morning")
    moments.resolve(api.lab.sim, m["id"], 1)  # "Take the bus." (affection -30, his trust -30)
    assert w.rels[(me, mike)].affection >= 55 and w.rels[(mike, me)].trust >= 55  # it stings, but the floor holds
    assert w.rels[(me, mike)].affection < 75  # and it still moved


def test_every_mini_game_outcome_and_the_texted_version():
    for tier, score in (("great", 10), ("good", 6), ("miss", 1)):
        c, api = _client([BROTHER] + TWINS)
        w = api.lab.w
        mike = _sib(api, "Mike")
        _install(c, BROTHERS, FRIDAY)
        _lock_both(c)
        m = dialogue.try_scene(api.lab.sim, "bro_team_02_scrimmage")
        assert m["ctx"]["them"] == mike
        r = c.post(f"/api/phone/moment/{m['id']}", json={"index": 0}).json()
        cfg = r["minigame"]
        r = c.post(f"/api/phone/moment/{m['id']}", json={"index": 0, "session": cfg["session"], "score": score, "max": 10}).json()
        assert r["minigame"]["tier"] == tier
        assert ("bro_scrimmage_win" in w.meta.get("remembered", {})) == (tier == "great")
    # the texted version: it comes from him
    w.meta["remembered"] = {}
    api.lab.w.chars[api.lab.w.meta["protagonist"]].grade = 10
    for _ in range(12):
        m = dialogue.try_scene(api.lab.sim, "bro_team_05_college_call")
        assert m["ctx"]["them"] == mike
        if m.get("by_text"):
            assert m["text"].startswith(w.chars[mike].first)
            break
        moments.resolve(api.lab.sim, m["id"], 0)
        w.meta["scenes_seen"].pop("bro_team_05_college_call", None)
        w.day += 1


def test_a_seeded_playthrough_logs_one_brother_from_start_to_finish():
    c, api = _client([BROTHER] + TWINS)
    w, sim = api.lab.w, api.lab.sim
    mike = _sib(api, "Mike")
    _install(c, BROTHERS, FRIDAY)
    _lock_both(c)
    who = []
    me = w.chars[w.meta["protagonist"]]
    for _ in range(430 * 6):  # freshman year, his graduation, and into your sophomore year, played out
        for m in moments.pending(w):
            if m["kind"].startswith(("bro_team", "fn_")):
                who.append((m["day"], m["kind"], m["ctx"].get("them"), me.grade, w.chars[mike].grade, w.chars[mike].location))
            moments.resolve(sim, m["id"], None)
        sim.step()
    assert who, "the brother storylines should play"
    assert {x[2] for x in who} == {mike}
    assert any(x[3] == 10 for x in who), "sophomore-year chapters (him in college) should play too"
    assert all(x[4] != 12 for x in who if x[3] == 10)  # by then he's graduated
    assert len({x[1] for x in who}) == len(who)  # no chapter twice
    assert len([x for x in w.meta["cast_log"] if x[1] == "lead_brother"]) == 1  # bound once
    order = [x[1] for x in who if x[1].startswith("bro_team")]
    assert order == sorted(order)  # chapters in order
