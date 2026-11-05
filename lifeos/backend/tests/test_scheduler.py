"""The story scheduler (dense scene cadence): the acceptance tests from the handoff.

A synthetic season plan stands in for the real one (same shape: the brother's freshman basketball season with his senior
night and graduation, the twins a grade up, Homecoming with four branches, freshman baseball, college move-in, a crossover).
"""
import copy
import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import calendar as calm  # noqa: E402
from lifeos import dialogue, moments, scheduler  # noqa: E402
from lifeos.engine import Simulation  # noqa: E402
from lifeos.model import World  # noqa: E402
from lifeos.story import begin, create_story  # noqa: E402
from tests.test_story import spec  # noqa: E402

BROTHER = {"key": "bro", "first": "Mike", "gender": "m", "grade": 12, "archetype": "athlete",
           "interests": {"basketball": 95}, "skills": {"basketball": 80}, "positions": {"basketball": "PG"}}
TWINS = [{"key": "ally", "first": "Ally", "gender": "f", "grade": 10},
         {"key": "jen", "first": "Jen", "gender": "f", "grade": 10, "twin_of": "ally"}]


@pytest.fixture(autouse=True)
def own_packs(tmp_path, monkeypatch):
    monkeypatch.setattr(dialogue, "USER_DIR", str(tmp_path / "dialogue"))
    dialogue.reload()
    yield
    dialogue.reload()


def S(sid, who="best_friend", choices=None, title=None, **when):
    return {"id": sid, "title": title or sid.replace("_", " "), "who": who, "text": "{them_first} is here.", "when": when,
            "choices": choices or [{"label": "Go for it", "ops": [["remember", f"{sid}_yes"]]}, {"label": "Not today", "ops": []}]}


def season_plan():
    """Stand-ins for the storylines and a season plan."""
    bro = {"dialogue_pack": 1, "name": "Brothers: Same Team", "in_order": True,
           "cast": {"lead_brother": {"who": "older_brother", "sport": "basketball", "grade_offset": 3, "bind": "start"}},
           "scenes": [S("bro_team_01_first_morning", "cast:lead_brother", years=["freshman"]),
                      S("bro_team_02_lunch_table", "cast:lead_brother", years=["freshman"]),
                      S("bro_team_05_tryouts", "cast:lead_brother", years=["freshman"]),
                      S("bro_team_09_scrimmage", "cast:lead_brother", years=["freshman"]),
                      S("brother_final_13_senior_night", "cast:lead_brother", years=["freshman"]),
                      S("bro_team_17_last_school_game", "cast:lead_brother", years=["freshman"]),
                      S("bro_graduation_day", "cast:lead_brother", years=["freshman"]),
                      S("bro_college_call", "cast:lead_brother", years=["sophomore"])]}
    twins = {"dialogue_pack": 1, "name": "The Twins", "in_order": True,
             "cast": {"twin_a": {"who": "older_sister", "grade_offset": 1, "bind": "start"}},
             "scenes": [S("twins_first_week", "cast:twin_a", years=["freshman"]),
                        S("twins_homecoming_advice", "cast:twin_a", years=["freshman"]),
                        S("twins_graduation", "cast:twin_a", years=["junior"])]}
    hc = {"dialogue_pack": 1, "name": "Homecoming", "in_order": False, "scenes": [
        S("hc_ask", choices=[{"label": f"Go with {x}", "ops": [["remember", f"hc_{x}"]]} for x in ("a", "b", "c", "d")],
          years=["freshman"], chance=1.0)]
        + [S(f"hc_dance_{x}", years=["freshman"], remembered=[f"hc_{x}"], chance=1.0) for x in ("a", "b", "c", "d")]
        + [S(f"hc_after_{x}", years=["freshman"], after=[f"hc_dance_{x}"], chance=1.0) for x in ("a", "b", "c", "d")]}
    ball = {"dialogue_pack": 1, "name": "Diamond", "in_order": True, "scenes": [
        S("baseball_01_tryouts", years=["freshman"]), S("baseball_02_jv_debut", years=["freshman"]),
        S("baseball_03_varsity_call", years=["freshman"], months=[4, 5, 6])]}
    col = {"dialogue_pack": 1, "name": "Campus", "in_order": True, "scenes": [
        S("college_move_in", years=["college_freshman"]), S("college_first_class", years=["college_freshman"])]}
    plan = {"dialogue_pack": 1, "name": "Season plan",
            "cast": {"lead_brother": {"who": "older_brother", "sport": "basketball", "grade_offset": 3, "bind": "start"}}, "scenes": [
        S("cross_brother_twins", "cast:lead_brother", years=["freshman"], after=["brother_final_13_senior_night", "twins_homecoming_advice"],
          chance=1.0)],
        "schedule": {"bro_team_17_last_school_game": {"after": ["brother_final_13_senior_night"]},
                     "bro_graduation_day": {"after": ["bro_team_17_last_school_game"]},
                     "baseball_02_jv_debut": {"after": ["baseball_01_tryouts"]}}}
    return [bro, twins, hc, ball, col, plan]


def _install(packs):
    for p in packs:
        r = dialogue.add_pack(copy.deepcopy(p))
        assert r.get("ok", True), r
    dialogue.reload()


def _story(per=6, **kw):
    w = create_story(spec(per=per, siblings=[BROTHER] + TWINS, **kw))
    sim = Simulation(w)
    begin(sim)
    for m in moments.pending(w):
        moments.resolve(sim, m["id"], 0)
    return w, sim, w.chars[w.meta["protagonist"]]


def _independent(n, prefix="s", **when):
    return {"dialogue_pack": 1, "name": f"Independent {prefix}", "in_order": False,
            "scenes": [S(f"{prefix}{i:03d}", chance=1.0, **when) for i in range(n)]}


def _to_monday(sim):
    w = sim.w
    while calm.date_of(w.day).weekday() != 0 or not calm.is_school_day(w.day, sim.cat.world["calendar"]):
        sim.advance_days(1)
        for m in moments.pending(w):
            moments.resolve(sim, m["id"], 0)


def _drain_today(sim, limit=200):
    w = sim.w
    played = []
    for _ in range(limit):
        m = scheduler.continue_story(sim)
        if m is None:
            break
        played.append(m["kind"])
        moments.resolve(sim, m["id"], 0)
    return played


# 1 ------------------------------------------------------------------------------------------------
def test_twelve_independent_scenes_all_run_on_one_monday():
    _install([_independent(12, weekdays=["mon"])])  # (Monday-only, so none of them goes before the first Monday)
    w, sim, me = _story()
    _to_monday(sim)
    day = w.day
    played = _drain_today(sim)
    assert w.day == day, "the calendar never moved"
    assert {f"s{i:03d}" for i in range(12)} <= set(scheduler.done_map(w)), played
    assert all(scheduler.done_map(w)[f"s{i:03d}"][-1] == day for i in range(12))


# 2 ------------------------------------------------------------------------------------------------
def test_a_storyline_chains_the_same_day():
    _install([{"dialogue_pack": 1, "name": "Chain", "in_order": True,
               "scenes": [S("chain_a", weekdays=["mon"]), S("chain_b", after=["chain_a"], gap_days=0, weekdays=["mon"])]}])
    w, sim, me = _story()
    _to_monday(sim)
    day = w.day
    m = next((x for x in moments.pending(w) if x["kind"] == "chain_a"), None) or scheduler.continue_story(sim)
    while m and m["kind"] != "chain_a":
        moments.resolve(sim, m["id"], 0)
        m = scheduler.continue_story(sim)
    assert m and m["kind"] == "chain_a"
    assert scheduler.gate(sim, me, "chain_b", scheduler.catalog(sim)) == ("waiting_for_scene", "chain_a"), "after = resolved, not started"
    moments.resolve(sim, m["id"], 0)
    nxt = moments.pending(w)[0] if moments.pending(w) else scheduler.continue_story(sim)
    while nxt and nxt["kind"] != "chain_b":
        moments.resolve(sim, nxt["id"], 0)
        nxt = moments.pending(w)[0] if moments.pending(w) else scheduler.continue_story(sim)
    assert nxt and nxt["kind"] == "chain_b" and w.day == day, "B is there later the same Monday"


# 3 ------------------------------------------------------------------------------------------------
def test_an_explicit_gap_holds_however_many_scenes_resolve():
    _install([{"dialogue_pack": 1, "name": "Gap", "in_order": False,
               "scenes": [S("gap_a", chance=1.0, weekdays=["mon"]), S("gap_b", after=["gap_a"], gap_days=7, chance=1.0)]},
              _independent(50, "x", weekdays=["mon"])])
    w, sim, me = _story()
    _to_monday(sim)
    w.meta.setdefault("control", {})["pacing"] = "uncapped"
    played = _drain_today(sim)
    a_day = scheduler.done_map(w)["gap_a"][-1]
    assert sum(1 for p in played if p.startswith("x")) >= 50 and "gap_b" not in scheduler.done_map(w)
    cat = scheduler.catalog(sim)
    for k in range(1, 7):
        assert scheduler.gate(sim, me, "gap_b", cat, day=a_day + k) is not None, k
    assert scheduler.gate(sim, me, "gap_b", cat, day=a_day + 7) is None


# 4 ------------------------------------------------------------------------------------------------
def test_season_windows_keep_the_calendar_real():
    _install(season_plan())
    w, sim, me = _story()
    cat = scheduler.catalog(sim)
    info = cat["info"]
    # windows come from Guilford's own calendar: baseball tryouts are March 2, basketball ends February 27, graduation June 12
    assert info["baseball_01_tryouts"]["window"] == {"from": [2, 28], "to": [3, 16]}
    assert info["brother_final_13_senior_night"]["window"] == {"from": [2, 6], "to": [2, 24]}
    assert info["brother_final_13_senior_night"]["importance"] == "finale"
    assert info["bro_team_17_last_school_game"]["window"] == {"from": [2, 20], "to": [3, 20]}
    assert info["bro_team_05_tryouts"]["window"] == {"from": [11, 16], "to": [12, 2]}
    assert info["hc_ask"]["window"] == {"from": [10, 2], "to": [10, 23]} and info["hc_dance_a"]["window"] == {"from": [10, 17], "to": [10, 25]}
    assert info["hc_after_a"]["window"] == {"from": [10, 18], "to": [10, 30]}
    assert info["bro_graduation_day"]["window"] == {"from": [6, 8], "to": [6, 19]}
    assert info["college_move_in"]["window"] == {"from": [8, 20], "to": [9, 15]}
    sept = calm.md_to_day(0, (9, 15))
    assert scheduler.calendar_ok(sim, "baseball_01_tryouts", {}, info["baseball_01_tryouts"], sept)[0] == "wrong_season"
    assert scheduler.calendar_ok(sim, "baseball_01_tryouts", {}, info["baseball_01_tryouts"], calm.md_to_day(0, (3, 5))) is None
    june = calm.md_to_day(0, (6, 20))
    assert scheduler.calendar_ok(sim, "bro_team_17_last_school_game", {}, info["bro_team_17_last_school_game"], june)[0] == "wrong_season"
    assert scheduler.gate(sim, me, "college_move_in", cat) == ("too_early", "school year"), "not before your own graduation"
    w.meta["remembered"] = {}
    scheduler.done_map(w)["brother_final_13_senior_night"] = [calm.md_to_day(0, (2, 10))]
    w.day = calm.md_to_day(0, (7, 1))
    g = scheduler.gate(sim, me, "bro_team_17_last_school_game", cat)
    assert g[0] == "window_passed", "his last school game can't happen after his June graduation"


# 5 ------------------------------------------------------------------------------------------------
def test_homecoming_plays_exactly_the_branch_you_chose():
    _install(season_plan())
    w, sim, me = _story()
    w.meta["control"]["pacing"] = "uncapped"
    cat = scheduler.catalog(sim)
    m = dialogue.try_scene(sim, "hc_ask")
    moments.resolve(sim, m["id"], 1)  # you go with b
    for _ in range(60):
        sim.advance_days(1)
        for x in moments.pending(w):
            moments.resolve(sim, x["id"], 0)
        _drain_today(sim)
    done = scheduler.done_map(w)
    assert "hc_dance_b" in done and "hc_after_b" in done
    for x in ("a", "c", "d"):
        assert f"hc_dance_{x}" not in done and f"hc_after_{x}" not in done
        assert scheduler.permanent(sim, me, f"hc_dance_{x}", cat) == "branch_closed"
        assert scheduler.permanent(sim, me, f"hc_after_{x}", cat) == "after_unreachable"


# 6 ------------------------------------------------------------------------------------------------
def test_the_brother_stays_the_brother_and_shares_the_freshman_team():
    _install(season_plan())
    w, sim, me = _story()
    sim.advance_days(1)  # slots that bind at the start bind on the first morning
    bro = next(c for c in w.chars.values() if c.first == "Mike" and c.household_id == me.household_id)
    twins = [c for c in w.chars.values() if c.first in ("Ally", "Jen") and c.household_id == me.household_id]
    assert w.meta["cast_slots"]["lead_brother"]["id"] == bro.id, "bound at the start, to the brother"
    assert w.meta["cast_slots"]["twin_a"]["id"] in {t.id for t in twins}
    assert bro.grade - me.grade == 3 and all(t.grade - me.grade == 1 for t in twins)
    me.skills["basketball"] = 72
    me.interests["basketball"] = 95
    tryout = next(i for i in w.calendar if i["kind"] == "tryout" and i["group"] == "basketball")
    for cid in (me.id, bro.id):
        w.registrations.setdefault(tryout["key"], [])
        if cid not in w.registrations[tryout["key"]]:
            w.registrations[tryout["key"]].append(cid)
    w.meta["control"]["auto_scenes"] = True
    while w.day <= tryout["day"] + 1:
        sim.advance_days(1)
        for x in moments.pending(w):
            moments.resolve(sim, x["id"], None)
    team = w.groups["basketball"]["members"]
    assert me.id in team and bro.id in team, "same Guilford basketball team, freshman year"
    assert w.meta["cast_slots"]["lead_brother"]["id"] == bro.id
    rep = scheduler.identity(sim)
    assert all(not r["problems"] for r in rep), rep


# 7 ------------------------------------------------------------------------------------------------
def test_a_seven_year_dry_run_accounts_for_every_scene(tmp_path):
    _install(season_plan())
    w, sim, me = _story()
    w.seed = 4242
    run = scheduler.dry_run(sim, 7 * 365 + 10, "dense", full=False)
    rep = scheduler.report(sim, run)
    ids = {s["id"] for p in season_plan() for s in p.get("scenes", [])}
    rows = {r["sid"]: r for r in rep["scenes"]}
    assert ids <= set(rows)
    for sid in ids:
        r = rows[sid]
        assert r["state"] in ("played", "unreachable", "expired") or r.get("reason"), r
    assert not rep["warnings"], rep["warnings"]
    done = scheduler.done_map(w)

    def month(sid):
        return calm.date_of(done[sid][-1]).month
    for sid in ("bro_team_01_first_morning", "bro_team_05_tryouts", "brother_final_13_senior_night", "bro_team_17_last_school_game",
                "bro_graduation_day", "baseball_01_tryouts", "college_move_in"):
        assert sid in done, (sid, rows[sid])
    assert month("bro_team_01_first_morning") in (8, 9) and month("bro_team_05_tryouts") in (11, 12)
    assert month("brother_final_13_senior_night") == 2 and month("bro_team_17_last_school_game") in (2, 3), "the end of his last season"
    assert done["brother_final_13_senior_night"][-1] < done["bro_team_17_last_school_game"][-1]
    assert done["bro_team_17_last_school_game"][-1] < done["bro_graduation_day"][-1] and month("bro_graduation_day") == 6
    assert month("baseball_01_tryouts") in (2, 3) and month("baseball_03_varsity_call") in (4, 5, 6)
    assert calm.school_year_of(done["college_move_in"][-1]) - calm.school_year_of(done["bro_team_01_first_morning"][-1]) == 4
    assert month("college_move_in") in (8, 9)
    dances = [x for x in "abcd" if f"hc_dance_{x}" in done]
    assert len(dances) == 1 and f"hc_after_{dances[0]}" in done, "one Homecoming"
    md = scheduler.report_markdown(rep, "Synthetic season plan, 7 years")
    assert "bro_team_17_last_school_game" in md and "Cast identity" in md
    (tmp_path / "report.md").write_text(md)
    assert not any(r["problems"] for r in rep["identity"])


# 8 ------------------------------------------------------------------------------------------------
def test_ten_thousand_scenes_stay_fast_deterministic_and_saveable():
    packs = []
    for p in range(50):
        sc = []
        for i in range(200):
            when = {"years": ["high_school"]}
            if p and i % 5 == 0:
                when["after"] = [f"big{p - 1:02d}_{i:03d}"]
            sc.append(S(f"big{p:02d}_{i:03d}", **when))
        packs.append({"dialogue_pack": 1, "name": f"Big {p:02d}", "in_order": True, "scenes": sc})
    for p in packs:
        dialogue.add_pack(p)
    dialogue.reload()
    w, sim, me = _story()
    assert len(scheduler.catalog(sim)["scenes"]) >= 10000
    snap = World.from_dict(json.loads(json.dumps(w.to_dict())))

    def run(world, days=4):
        s = Simulation(world)
        s.w.meta["control"]["auto_scenes"] = True
        t = time.time()
        r = scheduler.dry_run(s, days, "dense", full=False)
        return r, time.time() - t, s
    r1, t1, s1 = run(w)
    r2, t2, s2 = run(snap)
    assert r1["per_day"] == r2["per_day"] and sum(len(v) for v in r1["per_day"].values()) >= 8, "same seed, same story"
    assert t1 < 60, t1
    blob = json.loads(json.dumps(s1.w.to_dict()))
    s3 = Simulation(World.from_dict(blob))
    assert scheduler.done_map(s3.w) == scheduler.done_map(s1.w)
    t = time.time()
    st = scheduler.status(s3)
    assert len(st["scenes"]) >= 10000 and time.time() - t < 60


# 9 ------------------------------------------------------------------------------------------------
def test_pending_scenes_wait_for_you_across_a_reload():
    _install([_independent(4, "p")])
    w, sim, me = _story()
    for i in range(4):
        dialogue.try_scene(sim, f"p{i:03d}")
    pend = [(m["id"], m["kind"], [c["label"] for c in m["choices"]]) for m in moments.pending(w)]
    assert len([p for p in pend if p[1].startswith("p")]) == 4
    w2 = World.from_dict(json.loads(json.dumps(w.to_dict())))
    sim2 = Simulation(w2)
    sim2.advance_days(6)
    after = [(m["id"], m["kind"], [c["label"] for c in m["choices"]]) for m in moments.pending(w2) if m["kind"].startswith("p")]
    assert after == [p for p in pend if p[1].startswith("p")], "nothing chose for you"
    w2.meta["control"]["auto_scenes"] = True  # Let my character decide
    sim2.advance_days(4)
    assert not [m for m in moments.pending(w2) if m["kind"].startswith("p")]


# 10 -----------------------------------------------------------------------------------------------
def test_relaxed_and_dense_differ_in_pace_not_in_canon():
    _install(season_plan() + [_independent(30, "amb", years=["freshman"])])
    w, sim, me = _story()
    snap = json.loads(json.dumps(w.to_dict()))
    out = {}
    for prof in ("relaxed", "dense"):
        s = Simulation(World.from_dict(copy.deepcopy(snap)))
        run = scheduler.dry_run(s, 300, prof, full=False)
        rep = scheduler.report(s, run)
        assert not rep["warnings"], (prof, rep["warnings"])
        done = scheduler.done_map(s.w)
        assert sum(1 for x in "abcd" if f"hc_dance_{x}" in done) <= 1
        bro = [sid for sid in scheduler.catalog(s)["chapters"][next(p for p in scheduler.catalog(s)["chapters"] if "brothers" in p)] if sid in done]
        assert [done[x][-1] for x in bro] == sorted(done[x][-1] for x in bro)
        first_month = sum(len(v) for d, v in run["per_day"].items() if d < run["start"] + 30)
        out[prof] = (sum(len(v) for v in run["per_day"].values()), max((len(v) for v in run["per_day"].values()), default=0), first_month)
    # the same stories either way (content is finite); dense just gets there faster, several a day
    assert out["dense"][1] > out["relaxed"][1] == 1 and out["dense"][2] > 2 * out["relaxed"][2], out
    assert abs(out["dense"][0] - out["relaxed"][0]) <= 6, out


# 11 -----------------------------------------------------------------------------------------------
def test_a_big_storyline_doesnt_starve_the_rest():
    big = {"dialogue_pack": 1, "name": "Big arc", "in_order": True,
           "scenes": [S(f"arc_{i:02d}_decision", importance="major") for i in range(10)]}
    _install([big, _independent(12, "side", importance="ambient")])
    w, sim, me = _story()
    pid = next(p["id"] for p in dialogue.packs() if p["pack"]["name"] == "Big arc")
    w.meta["story_weights"] = {pid: 5}
    run = scheduler.dry_run(sim, 7, "dense", full=False)
    done = scheduler.done_map(w)
    majors = [sid for sid in done if sid.startswith("arc_")]
    sides = [sid for sid in done if sid.startswith("side")]
    assert 1 <= len(majors) <= 2, majors
    assert len(sides) >= 6, sides
    assert len(scheduler.queue(w)["items"]) <= 10, "no runaway backlog"
    st = scheduler.status(sim)
    assert any(r["reason"] == "major_breather" for r in st["scenes"] if r["sid"].startswith("arc_") and r.get("reason")) or \
        scheduler.log(w).get(f"arc_{len(majors):02d}_decision", {}).get("reason") == "major_breather"


# 12 -----------------------------------------------------------------------------------------------
def test_the_validator_takes_an_old_season_plan_unchanged_and_the_new_fields():
    old = {"dialogue_pack": 1, "name": "Season plan",
           "schedule": {"bro_team_01_first_morning": {"years": ["freshman"]},
                        "bro_team_17_last_school_game": {"years": ["freshman"], "after": ["brother_final_13_senior_night"], "gap_days": 3},
                        "twins_graduation": {"years": ["junior"], "months": [6]}},
           "scenes": [S("cross_one", years=["freshman"], after=["bro_team_01_first_morning"])]}
    r = dialogue.check(old)
    assert r["ok"], r["errors"]
    new = copy.deepcopy(old)
    new["schedule"]["twins_graduation"].update({"not_before": "06-01", "not_after": "06-20", "importance": "finale"})
    new["scenes"][0]["when"].update({"not_before": "09-02", "importance": "regular"})
    assert dialogue.check(new)["ok"]
    bad = copy.deepcopy(new)
    bad["schedule"]["twins_graduation"]["not_after"] = "June"
    bad["schedule"]["twins_graduation"]["importance"] = "huge"
    errs = " | ".join(dialogue.check(bad)["errors"])
    assert "month-day" in errs and "ambient, regular, major or finale" in errs


def test_relaxed_keeps_the_old_spacing_and_pacing_is_a_setting():
    _install([{"dialogue_pack": 1, "name": "Slow", "in_order": True, "scenes": [S(f"slow_{i}") for i in range(4)]}])
    w, sim, me = _story()
    run = scheduler.dry_run(sim, 40, "relaxed", full=False)
    days = [scheduler.done_map(w)[f"slow_{i}"][-1] for i in range(4) if f"slow_{i}" in scheduler.done_map(w)]
    assert len(days) >= 3 and all(b - a >= scheduler.PROFILES["relaxed"]["chapter_gap"] for a, b in zip(days, days[1:])), days
    assert scheduler.control(w)["pacing"] == "relaxed" and set(scheduler.PROFILES) == {"relaxed", "standard", "dense", "uncapped"}


def test_the_lab_and_phone_endpoints():
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    _install(season_plan() + [_independent(6, "lab")])
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    assert c.post("/api/story/new", json={"spec": spec(per=6, siblings=[BROTHER] + TWINS)}).status_code == 200
    for m in moments.pending(api.lab.w):
        moments.resolve(api.lab.sim, m["id"], 0)
    st = c.get("/api/story/schedule").json()
    assert st["profile"] == "dense" and set(st["profiles"]) == set(scheduler.PROFILES) and st["storylines"] and st["scenes"]
    assert any(r["state"] == "waiting" and r["reason"] for r in st["scenes"])
    assert c.post("/api/story/control", json={"pacing": "uncapped"}).json()["pacing"] == "uncapped"
    assert c.post("/api/story/control", json={"pacing": "turbo"}).status_code == 422
    st = c.post("/api/story/schedule/settings", json={"pacing": "dense", "overrides": {"school": [3, 3]}, "weights": {"x": 2}}).json()
    assert st["settings"]["school"] in ((3, 3), [3, 3]) and st["weights"] == {"x": 2.0}
    assert c.post("/api/story/schedule/settings", json={"overrides": {"nonsense": 1}}).status_code == 422
    r = c.post("/api/story/schedule/continue").json()
    assert r["moment"] or r["note"]
    r = c.post("/api/story/schedule/step", json={"what": "today"}).json()
    assert isinstance(r["played"], list) and r["status"]["presented_today"] >= 0
    r = c.post("/api/story/schedule/step", json={"what": "day"}).json()
    assert "status" in r
    rel = c.post("/api/story/schedule/release", json={"sid": "baseball_01_tryouts"})
    assert rel.status_code == 200 and rel.json()["moment"]["kind"] == "baseball_01_tryouts"
    moments.resolve(api.lab.sim, rel.json()["moment"]["id"], 0)
    tl = c.get("/api/story/schedule/timeline").json()
    assert any(i["sid"] == "baseball_01_tryouts" for i in tl["items"])
    cmp = c.post("/api/story/schedule/compare", json={"profiles": ["relaxed", "dense"], "days": 40}).json()
    assert [x["profile"] for x in cmp["runs"]] == ["relaxed", "dense"] and len(cmp["runs"][0]["per_day"]) == 40
    md = c.get("/api/story/schedule/report?days=120&fmt=md")
    assert md.status_code == 200 and "Every scene" in md.text
    st = c.post("/api/story/schedule/season_map", json={"scene_windows": {"bro_team_02_lunch_table": [10]},
                                                        "importance": {"bro_team_02_lunch_table": "major"}}).json()
    row = next(r for r in st["scenes"] if r["sid"] == "bro_team_02_lunch_table")
    assert row["window"] == [10] and row["window_rule"] == "your override" and row["importance"] == "major"


def test_a_chapter_nobody_can_play_yet_doesnt_freeze_its_storyline():
    _install([{"dialogue_pack": 1, "name": "Mixed signals", "in_order": True, "scenes": [
        S("ms_01_your_partner", "partner", years=["freshman"]), S("ms_02_best_friend_take", years=["freshman"]),
        S("ms_03_more_friend", years=["freshman"])]}])
    w, sim, me = _story()
    assert not me.flags.get("partner")
    scheduler.dry_run(sim, 20, "dense", full=False)
    done = scheduler.done_map(w)
    assert "ms_02_best_friend_take" in done and "ms_03_more_friend" in done, "the story moves on past the chapter nobody can play"
    assert "ms_01_your_partner" not in done
    row = next(r for r in scheduler.rows(sim) if r["sid"] == "ms_01_your_partner")
    assert row["state"] == "waiting" and row["reason"] in ("missing_cast", "chapter_order")


def test_an_after_link_to_another_storyline_orders_it_but_doesnt_cut_it_off():
    plan = {"dialogue_pack": 1, "name": "Weave", "in_order": False, "scenes": [
        S("weave_choice", choices=[{"label": "A", "ops": [["remember", "weave_a"]]}, {"label": "B", "ops": [["remember", "weave_b"]]}], chance=1.0),
        S("weave_only_on_a", remembered=["weave_a"], chance=1.0)]}
    ball = {"dialogue_pack": 1, "name": "Ball", "in_order": True, "scenes": [S("ball_01_start", after=["weave_only_on_a"]), S("ball_02_more")]}
    _install([plan, ball])
    w, sim, me = _story()
    m = dialogue.try_scene(sim, "weave_choice")
    moments.resolve(sim, m["id"], 1)  # B: the scene ball_01 is "after" can never happen now
    cat = scheduler.catalog(sim)
    assert scheduler.permanent(sim, me, "weave_only_on_a", cat) == "branch_closed"
    assert scheduler.permanent(sim, me, "ball_01_start", cat) is None
    scheduler.dry_run(sim, 10, "dense", full=False)
    assert "ball_01_start" in scheduler.done_map(w) and "ball_02_more" in scheduler.done_map(w), "the baseball storyline still plays"


def test_the_report_says_what_a_missed_scene_was_waiting_on():
    _install([{"dialogue_pack": 1, "name": "Date night", "in_order": False, "scenes": [
        S("date_night_freshman", "partner", years=["freshman"], chance=1.0)]}])
    w, sim, me = _story()
    run = scheduler.dry_run(sim, 380, "dense", full=False)
    row = next(r for r in scheduler.report(sim, run)["scenes"] if r["sid"] == "date_night_freshman")
    assert row["state"] == "unreachable" and row["reason"] == "year_passed"
    assert row["missed"]["reason"] == "missing_cast" and "while it was waiting" in row["why"]
