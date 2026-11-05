"""Story mode, sports and life after high school."""
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import calendar as calm  # noqa: E402
from lifeos import college, moments, sports  # noqa: E402
from lifeos.history import Effects  # noqa: E402
from lifeos.engine import Simulation  # noqa: E402
from lifeos.story import StoryError, begin, create_story, validate_story  # noqa: E402


def spec(grade=9, per=8, **kw):
    s = {"title": "Test story",
         "protagonist": {"first": "Zack", "last": "Soffer", "gender": "m", "grade": grade, "archetype": "athlete", "attracted_to": ["f"],
                         "traits": {"discipline": 75, "competitiveness": 85}, "aptitudes": {"athletic": 85},
                         "interests": {"football": 85, "basketball": 80, "baseball": 90},
                         "skills": {"football": 45, "basketball": 48, "baseball": 55},
                         "body": {"height_in": 71, "build": "athletic"}, "positions": {"football": "WR", "basketball": "SG", "baseball": "SS"},
                         "jersey": 2, "birthday": [4, 12]},
         "family": {"last": "Soffer", "guardians": ["Linda Soffer", "Rob Soffer"], "style": "warm", "income": "middle"},
         "siblings": [{"key": "bro", "first": "Mike", "gender": "m", "grade": 12, "archetype": "athlete"},
                      {"key": "ally", "first": "Ally", "gender": "f", "grade": 11},
                      {"key": "jen", "first": "Jen", "gender": "f", "grade": 11, "twin_of": "ally"}],
         "cast": [{"key": "bf", "first": "Danny", "last": "Kim", "gender": "m", "grade": 9, "archetype": "athlete",
                   "relationships": [{"to": "me", "type": "best_friend"}]},
                  {"key": "rival", "first": "Cole", "last": "Price", "gender": "m", "grade": 9,
                   "relationships": [{"to": "me", "type": "rival"}]},
                  {"key": "coach", "role": "staff", "first": "Frank", "last": "Duda", "gender": "m", "coach_of": "baseball"}],
         "students_per_grade": per, "gen_seed": 77}
    s.update(kw)
    return s


def test_story_builds_you_your_family_and_your_people():
    w = create_story(spec())
    sim = Simulation(w)
    begin(sim)
    me = w.chars[w.meta["protagonist"]]
    keys = w.meta["story"]["keys"]
    assert me.grade == 9 and me.custom and me.positions["baseball"] == "SS" and me.body["height_in"] == 71 and me.jersey == 2
    assert calm.date_of(me.birth_day).month == 4 and calm.date_of(me.birth_day).day == 12
    sibs = {w.chars[s].first: w.chars[s] for s in sim.siblings(me.id)}
    assert sibs["Mike"].grade == 12 and sibs["Ally"].grade == 11 and sibs["Jen"].grade == 11
    assert sibs["Ally"].birth_day == sibs["Jen"].birth_day
    assert "twin" in w.bond(keys["ally"], keys["jen"])["roles"]
    assert all("sibling" in w.bond(me.id, s.id)["roles"] for s in sibs.values())
    assert w.rels[(keys["bf"], me.id)].affection >= 80 and w.rels[(me.id, keys["bf"])].label in ("best friend", "close friend")
    assert w.rels[(keys["rival"], me.id)].rivalry >= 60
    assert w.groups["baseball"]["staff"] == keys["coach"]
    for g in (9, 10, 11, 12):
        assert sum(1 for c in w.students() if c.grade == g) == 8
    pend = moments.pending(w)
    assert pend and pend[0]["kind"] == "first_day"
    assert all(55 <= c.body["height_in"] <= 80 for c in w.chars.values() if c.body)


@pytest.mark.parametrize("pet,expect", [(None, None), ({"species": "dog", "name": "Buster"}, "Buster")])
def test_family_pet_can_be_none_or_named(pet, expect):
    s = spec(per=6)
    s["family"]["pet"] = pet
    w = create_story(s)
    h = w.households[w.chars[w.meta["protagonist"]].household_id]
    assert (h["pet"] or {}).get("name") == expect


def test_picked_pet_keeps_breed_and_coat_and_bad_picks_are_flagged():
    from lifeos import pets
    s = spec(per=6)
    s["family"]["pet"] = {"species": "dog", "name": "Scout", "breed": "Golden Retriever", "coat": "golden"}
    sim = Simulation(create_story(s))
    begin(sim)
    pet = next(iter(pets.pets(sim.w).values()))
    assert (pet["name"], pet["breed"], pet["coat"]) == ("Scout", "Golden Retriever", "golden")
    s["family"]["pet"] = {"species": "dog", "name": " ", "breed": "Poodle", "coat": "purple"}
    with pytest.raises(StoryError) as e:
        validate_story(s)
    msg = " | ".join(e.value.errors)
    assert "needs a name" in msg and "breed" in msg and "coat" in msg


def test_siblings_on_auto_look_like_you_when_you_pick_your_look():
    from lifeos import appearance
    s = spec(per=6)
    s["protagonist"]["look"] = {"skin": "porcelain", "hair_color": "red", "eyes": "green"}
    s["siblings"][1]["look"] = {"hair_color": "black"}  # Ally picked her own hair color
    w = create_story(s)
    sibs = {c.first: appearance.look_of(c) for c in w.chars.values() if c.first in ("Mike", "Ally", "Jen") and c.last == "Soffer"}
    assert len(sibs) == 3
    skins = appearance.SKIN
    for name, look in sibs.items():
        assert abs(skins.index(look["skin"]) - skins.index("porcelain")) <= 1, name
        assert look["hair"] not in ("afro", "locs", "braids")
    assert sibs["Ally"]["hair_color"] == "black"


def test_story_validation_lists_every_problem():
    bad = spec()
    bad["protagonist"] = {"first": "", "gender": "q", "grade": 14, "traits": {"swagger": 50}, "positions": {"football": "XX"}}
    bad["cast"][0]["relationships"] = [{"to": "nobody", "type": "best_friend"}]
    with pytest.raises(StoryError) as e:
        validate_story(bad)
    msg = " | ".join(e.value.errors)
    for frag in ("first name", "gender", "grade", "swagger", "position", "nobody"):
        assert frag in msg


def test_moment_choices_change_state_and_are_recorded():
    w = create_story(spec())
    sim = Simulation(w)
    begin(sim)
    m = moments.pending(w)[0]
    ev = moments.resolve(sim, m["id"], 0)
    assert w.meta["control"]["focus"] == "athletics"
    tryout = next(i for i in w.calendar if i["kind"] == "tryout" and i["group"] == "football")
    assert w.meta["protagonist"] in w.registrations[tryout["key"]]
    assert ev["type"] == "moment" and ev["id"] in w.history.events
    with pytest.raises(ValueError):
        moments.resolve(sim, m["id"], 0)


def test_football_season_has_rosters_box_scores_and_stats():
    w = create_story(spec(per=14))  # enough boys for football and boys' soccer in the same fall
    w.tracing = True
    sim = Simulation(w)
    begin(sim)
    moments.resolve(sim, moments.pending(w)[0]["id"], 0)
    sim.advance_days(45)
    g = w.groups["football"]
    assert len(g["members"]) >= 11 and set(g["levels"].values()) <= {"varsity", "jv"}
    games = [e for e in w.history.events.values() if e["type"] == "game" and e["outcome"] in ("win", "loss")]
    assert games and all(e["data"]["box"] for e in games)
    played = [c for c in w.chars.values() if any(k.startswith("football:") for k in c.stats)]
    assert played
    st = next(st for c in played for k, st in c.stats.items() if k.startswith("football:"))
    assert st["games"] >= 1 and st["line"] is not None and st["impact"] > 0
    me = w.chars[w.meta["protagonist"]]
    assert "football" in me.memberships or any(e["type"] == "tryout" and me.id in e["actors"] for e in w.history.events.values())


def test_senior_year_ends_in_a_path_and_college_life():
    w = create_story(spec(grade=12, per=6, siblings=[], cast=[]))
    w.tracing = False
    sim = Simulation(w)
    begin(sim)
    me = w.chars[w.meta["protagonist"]]
    grad = next(i for i in w.calendar if i["kind"] == "graduation")
    while w.day < grad["day"]:
        sim.advance_days(7)
        for m in moments.pending(w):
            if m["kind"] == "college_decision":
                opts = m["ctx"]["paths"]
                pick = next((i for i, o in enumerate(opts) if o["kind"] == "college"), 0)
                moments.resolve(sim, m["id"], pick)
            else:
                moments.resolve(sim, m["id"], None)
    sim.advance_days(2)
    assert me.role == "alumni" and me.path, "every senior leaves with a path"
    if me.path["kind"] != "college":
        me.path = {"kind": "college", "college": "uconn", "name": "University of Connecticut", "tier": "D1", "sport": "baseball", "scholarship": True}
    others = [c for c in w.chars.values() if c.role == "alumni" and c.id != me.id]
    assert others and all(c.path for c in others)
    while calm.school_year_of(w.day) == 0:
        sim.advance_days(1)
        for m in moments.pending(w):
            moments.resolve(sim, m["id"], None)
    sim.advance_days(1)
    assert me.school == "college" and me.location == "college" and me.grade == 13
    assert w.meta["college"]["id"] == me.path["college"]
    assert any(g.get("school") == "college" for g in w.groups.values())
    assert any("roommate" in b["roles"] for k, b in w.bonds.items() if me.id in k)
    away = [c for c in w.chars.values() if c.location == "away"]
    stayed = [c for c in w.chars.values() if c.role == "alumni" and c.path.get("kind") == "work"]
    assert away or stayed
    assert all(any(w.groups[g].get("adult") for g in c.memberships) for c in stayed)
    thanksgiving = calm.md_to_day(1, (11, 26))
    sim.advance_days(thanksgiving - w.day + 1)
    assert me.location == "hollow_creek", "home for Thanksgiving"
    assert all(c.location == "hollow_creek" for c in away if c.household_id)


def test_story_api_flow():
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    assert c.get("/api/story").json() == {"active": False}
    cat = c.get("/api/story/catalog").json()
    assert "football" in cat["sports"] and any(r["id"] == "twin" for r in cat["relationships"])
    assert c.post("/api/story/validate", json={"spec": {"protagonist": {"first": ""}}}).status_code == 422
    r = c.post("/api/story/new", json={"spec": spec()})
    assert r.status_code == 200 and r.json()["protagonist"]
    s = c.get("/api/story").json()
    assert s["active"] and s["moments"][0]["kind"] == "first_day" and len(s["family"]) == 3
    assert c.post(f"/api/story/moment/{s['moments'][0]['id']}", json={"index": 1}).status_code == 200
    assert c.post("/api/story/control", json={"focus": "academics", "ask_invites": True}).json()["focus"] == "academics"
    assert c.post("/api/story/control", json={"focus": "nonsense"}).status_code == 422
    j = c.post("/api/story/advance", json={"until": "decision"}).json()
    assert j["status"] == "done" and j["stop"] in ("decision", "moment")
    if j["stop"] == "decision":
        opts = c.post(f"/api/play/{s['protagonist']}/options").json()
        # the Lab explains the top few choices; studying gets the academics focus whenever it's explained
        study = [o for o in opts["options"] if o["action"] in ("study", "study_at_lunch")]
        assert opts["options"] and study
        assert all("your focus" in str(o["terms"]) for o in study if o.get("terms"))
    j = c.post("/api/story/advance", json={"until": "week"}).json()
    while j["status"] == "running":
        time.sleep(0.2)
        j = c.get("/api/sim/job").json()
    assert j["status"] == "done", j.get("error")
    me = c.get(f"/api/characters/{s['protagonist']}").json()
    assert me["is_protagonist"] and me["positions"]["football"] == "WR" and "seasons" in me
    new = c.post("/api/characters", json={"first": "Riley", "last": "Moss", "gender": "f", "grade": 10,
                                          "relationships": [{"to": "me", "type": "crush"}]}).json()
    assert new["custom"] and new["grade"] == 10


def test_guilford_and_the_real_colleges():
    w = create_story(spec(per=6))
    sim = Simulation(w)
    assert w.name == "Guilford" and sim.cat.world["school"]["name"] == "Guilford High School"
    assert w.groups["football"]["name"] == "Guilford Football"
    assert "Hand" in sim.cat.world["opponents"]["hchs"]
    ids = {c["id"] for c in sim.cat.colleges}
    assert {"uconn", "stanford", "ucla", "lsu", "unc", "texas", "oklahoma", "fsu", "miami", "michigan"} <= ids
    lsu, uconn = sim.cat.college_by_id["lsu"], sim.cat.college_by_id["uconn"]
    assert sports.recruit_bar(lsu, "baseball") > sports.recruit_bar(uconn, "baseball")
    assert sports.recruit_bar(uconn, "basketball") > sports.recruit_bar(lsu, "basketball")


def test_a_sibling_can_be_set_to_play_basketball_at_uconn():
    s = spec(per=6)
    s["siblings"][0]["path"] = {"college": "uconn", "sport": "basketball"}
    w = create_story(s)
    sim = Simulation(w)
    mike = w.chars[w.meta["story"]["keys"]["bro"]]
    assert mike.flags["preset_path"] == {"kind": "college", "college": "uconn", "sport": "basketball"}
    assert mike.interests["basketball"] >= 80
    mike.gpa = 2.0  # even a rough senior spring doesn't undo a commitment
    sports.admissions(sim.institutions, sim.streams.get("t", 1))
    sports.choose_path(sim.institutions, mike, sim.streams.get("t", 2))
    assert mike.path["college"] == "uconn" and mike.path["sport"] == "basketball" and mike.path["aid"] == "full scholarship"
    bad = spec()
    bad["siblings"][0]["path"] = {"college": "harvard"}
    with pytest.raises(StoryError):
        validate_story(bad)


def test_grades_matter_offers_need_the_gpa():
    w = create_story(spec(grade=12, per=6, siblings=[], cast=[]))
    sim = Simulation(w)
    me = w.chars[w.meta["protagonist"]]
    sports.make_offer(sim.institutions, me, sim.cat.college_by_id["stanford"], "baseball", committed=True)
    sports.make_offer(sim.institutions, me, sim.cat.college_by_id["lsu"], "baseball", committed=True)
    me.gpa = 2.9
    sports.admissions(sim.institutions, sim.streams.get("t", 3))
    assert [o["college"] for o in me.recruiting["offers"]] == ["lsu"]
    assert me.recruiting["lost_offers"][0]["college"] == "stanford"
    assert any(e["type"] == "recruiting" and e["outcome"] == "pulled" for e in w.history.events.values())
    gpas = [c.gpa for c in w.students()]
    assert 2.6 <= sum(gpas) / len(gpas) <= 3.6


def _college_junior(sim, college_id="lsu"):
    w = sim.w
    me = w.chars[w.meta["protagonist"]]
    col = sim.cat.college_by_id[college_id]
    me.path = {"kind": "college", "college": col["id"], "name": col["name"], "tier": col["tier"], "sport": "baseball", "scholarship": True, "started": 0}
    me.role, me.grade, me.school, me.location = "student", 15, "college", "college"
    college.ensure_college(sim, col["id"])
    Effects(w, None).join(me.id, "col_baseball", "test")
    me.skills["baseball"], me.skills["fitness"] = 86, 80
    me.stats["baseball:2030-31:varsity"] = {"sport": "baseball", "level": "varsity", "team": "col_baseball", "team_name": "LSU Baseball",
                                            "school": "college", "games": 14, "starts": 14, "wins": 9, "losses": 5, "line": {"h": 20, "ab": 52},
                                            "impact": 14 * 84.0}
    return me


def test_mlb_draft_after_college_junior_year_and_the_finale():
    w = create_story(spec(grade=12, per=6, siblings=[], cast=[]))
    sim = Simulation(w)
    begin(sim)
    moments.resolve(sim, moments.pending(w)[0]["id"], None)
    me = _college_junior(sim)
    proj = sports.draft_score(sim, me)
    assert proj["round"] is not None and proj["terms"]
    sports.mlb_draft(sim)
    d = me.recruiting["draft"]
    assert d["status"] == "drafted" and d["team"] in sim.cat.sports["mlb"]["teams"] and 1 <= d["round"] <= 20 and d["bonus"] > 0
    m = next(m for m in moments.pending(w) if m["kind"] == "mlb_draft")
    assert d["team"] in m["title"] and len(m["choices"]) == 2
    moments.resolve(sim, m["id"], 0)
    assert me.path["kind"] == "pro" and me.path["team"] == d["team"] and me.location == "away" and "col_baseball" not in me.memberships
    w.meta["story"]["start_day"] = w.day - 7 * 365 + 40
    import datetime
    while (calm.date_of(w.day).month, calm.date_of(w.day).day) <= (7, 13) or calm.date_of(w.day).month >= 9:
        w.day += 1
    sim._story_dawn()
    end = next(m for m in moments.pending(w) if m["kind"] == "story_end")
    assert d["team"] in end["text"] and w.meta["story"]["complete"]


def test_offscreen_college_athletes_get_seasons():
    w = create_story(spec(per=6))
    sim = Simulation(w)
    mike = w.chars[w.meta["story"]["keys"]["bro"]]
    mike.path = {"kind": "college", "college": "uconn", "name": "University of Connecticut", "sport": "basketball", "started": 0}
    mike.role, mike.grade, mike.school, mike.location = "student", 13, "away:uconn", "away"
    college.offscreen_season(sim, "basketball")
    st = next(st for k, st in mike.stats.items() if k.startswith("basketball:"))
    assert st["offscreen"] and st["games"] >= 10 and st["team_name"] == "UConn Men's Basketball" and st["line"].get("pts", 0) > 0
