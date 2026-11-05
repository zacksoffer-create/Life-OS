"""Mini games, classes and trivia: rounds that feed the story."""
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import classes, dialogue, minigames, moments, trivia  # noqa: E402
from lifeos.engine import Simulation  # noqa: E402
from lifeos.story import begin, create_story  # noqa: E402
from tests.test_story import spec  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT_PUBLIC = Path(__file__).resolve().parents[2] / "frontend" / "public" / "minigames"


@pytest.fixture(autouse=True)
def own_packs(tmp_path, monkeypatch):
    monkeypatch.setattr(dialogue, "USER_DIR", str(tmp_path / "dialogue"))
    dialogue.reload()
    yield
    dialogue.reload()


def story():
    sim = Simulation(create_story(spec(per=6)))
    begin(sim)
    for m in moments.pending(sim.w):
        moments.resolve(sim, m["id"], 0)
    return sim


def to_phase(sim, phases):
    for _ in range(40):
        if sim.current_phase() in phases and not moments.pending(sim.w):
            return
        for m in moments.pending(sim.w):
            moments.resolve(sim, m["id"], None)
        sim.step()
    raise AssertionError("never reached " + str(phases))


def test_trivia_bank_is_well_formed_and_math_is_right():
    for sub, qs in trivia.bank()["questions"].items():
        for q in qs:
            answers = [q["a"]] + q["w"]
            assert len(q["w"]) == 3 and len({a.strip().lower() for a in answers}) == 4, (sub, q["q"])
            assert 9 <= q.get("g", 9) <= 13
    rng = random.Random(5)
    for course in trivia.COURSES:
        for _ in range(200):
            q = trivia.math_question(rng, course)
            assert len(set(q["choices"])) == 4 and 0 <= q["answer"] < 4


def test_free_play_soccer_rewards_once_a_day():
    sim = story()
    to_phase(sim, ("after_school", "day", "evening"))
    c = sim.w.chars[sim.w.meta["protagonist"]]
    games = {g["id"]: g for g in minigames.free_list(sim)}
    assert games["soccer_pk"]["available"] and games["basketball"]["available"] and games["football"]["available"] and not games["paper_toss"]["available"]
    with pytest.raises(ValueError):
        minigames.start(sim, "paper_toss")  # not ready yet
    cfg = minigames.start(sim, "soccer_pk")
    assert cfg["file"] == "soccer.html" and 0 <= cfg["skill"] <= 100
    fit0, fun0 = c.skills["fitness"], c.needs["fun"]
    with pytest.raises(ValueError):
        minigames.finish(sim, cfg["session"], 9, 5)  # score > max
    r = minigames.finish(sim, cfg["session"], 5, 5)
    assert r["tier"] == "great" and c.skills["fitness"] > fit0 and c.needs["fun"] >= fun0
    fit1 = c.skills["fitness"]
    cfg2 = minigames.start(sim, "soccer_pk")
    r2 = minigames.finish(sim, cfg2["session"], 1, 5)
    assert r2["tier"] == "miss" and c.skills["fitness"] == fit1, "only the first round of the day counts as practice"
    assert minigames.state(sim.w)["best"]["soccer_pk"] == 1.0


def test_soccer_playmaker_is_soccers_game_day_game():
    sim = story()
    to_phase(sim, ("after_school", "day", "evening"))
    reg = minigames.reg()
    assert reg["sport_games"]["soccer"] == "soccer_11"
    g = reg["games"]["soccer_11"]
    assert g["status"] == "ready" and g["play"]["clutch"] == "clutch"
    assert (ROOT_PUBLIC / g["file"]).exists(), "the 11 v 11 page is synced into the minigames folder"
    games = {x["id"]: x for x in minigames.free_list(sim)}
    assert games["soccer_11"]["available"] and games["soccer_pk"]["available"], "penalty kicks stays as its own free play"
    cfg = minigames.start(sim, "soccer_11")
    assert cfg["file"] == "soccer11.html" and cfg["play"] == "menu"
    r = minigames.finish(sim, cfg["session"], 3, 3)
    assert r["tier"] == "great"


def test_class_schedule_and_grades():
    sim = story()
    c = sim.w.chars[sim.w.meta["protagonist"]]
    sched = classes.schedule(sim, c)
    names = [x["name"] for x in sched]
    assert any("English" in n for n in names) and any(n in ("Algebra I", "Honors Geometry") for n in names) and len(sched) == 7
    assert all(x["teacher"].split()[0] in ("Mr.", "Ms.", "Mrs.", "Dr.") for x in sched)
    gs = classes.grades(sim, c)
    assert all(g["letter"] and 40 <= g["pct"] <= 100 for g in gs)
    assert classes.schedule(sim, c) is sched, "the schedule is made once per school year"


def test_quiz_day_is_playable_and_counts_toward_the_exam():
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    cl = TestClient(api.app)
    assert cl.post("/api/story/new", json={"spec": spec(per=6)}).status_code == 200
    L = api.lab
    sim, w = L.sim, L.w
    quiz = None
    for _ in range(60 * 5):
        quiz = next((m for m in moments.pending(w) if m["kind"] == "class_quiz"), None)
        if quiz:
            break
        for m in moments.pending(w):
            moments.resolve(sim, m["id"], None)
        sim.step()
    assert quiz, "a quiz day came up"
    assert quiz["ctx"]["subjects"] and quiz["title"].startswith(quiz["ctx"]["exam"])
    r = cl.post(f"/api/phone/moment/{quiz['id']}", json={"index": 0}).json()
    cfg = r["minigame"]
    assert cfg["game"] == "trivia" and len(cfg["questions"]) == quiz["ctx"]["n"]
    done = cl.post(f"/api/phone/moment/{quiz['id']}", json={"index": 0, "session": cfg["session"], "score": cfg and len(cfg["questions"]), "max": len(cfg["questions"])})
    assert done.status_code == 200, done.text
    j = done.json()
    assert j["minigame"]["tier"] == "great"
    me = w.chars[w.meta["protagonist"]]
    assert me.flags["quiz_played"]["pct"] == 1.0
    for _ in range(3):  # through the classes slot, where the exam is scored
        sim.step()
    v = cl.get("/api/phone/classes").json()
    played = [x for x in v["classes"] if x["quizzes"]] or ([1] if classes.store(w)["quizzes"].get("_tests") else [])
    assert played, "the played quiz is remembered by its class"
    ex = [e for e in w.history.events.values() if e["type"] == "exam" and e["data"].get("event") == quiz["ctx"]["exam"]]
    assert ex


def test_unplayed_moment_rolls_the_fallback_and_hidden_choices():
    sim = story()
    w = sim.w
    c = w.chars[w.meta["protagonist"]]
    football = next(g for g in w.groups if w.groups[g].get("skill") == "football")
    # game day: the "play it yourself" choice only shows when that sport's game is ready
    reg = minigames.reg()
    old = reg["games"]["football"]["status"]
    try:
        reg["games"]["football"]["status"] = "coming"
        moments.trigger(sim, "game_day", c.id, {"group": football, "opponent": "Branford"})
        m = moments.pending(w)[-1]
        assert not any("yourself" in ch["label"] for ch in m["choices"]), "a game that isn't ready hides the choice"
    finally:
        reg["games"]["football"]["status"] = old
    moments.resolve(sim, m["id"], None)
    m["day"] -= 1  # game day moments are once a day; pretend that one was yesterday
    # football is ready: game day opens the option game's goal-line round
    moments.trigger(sim, "game_day", c.id, {"group": football, "opponent": "Madison"})
    m = moments.pending(w)[-1]
    i = next(k for k, ch in enumerate(m["choices"]) if "yourself" in ch["label"])
    cfg = minigames.start(sim, "sport", kind="moment", mid=m["id"], index=i, ctx=m["ctx"])
    assert cfg["game"] == "football" and cfg["mode"] == "clutch" and cfg["play"] == "clutch" and cfg["file"] == "football.html"
    minigames.finish(sim, cfg["session"], 10, 10)
    assert c.flags["game_clutch"] == 7 and c.flags["game_clutch_day"] == w.day


def test_dialogue_packs_add_trivia_and_minigame_scenes():
    pack = {"name": "Quiz night", "trivia": {"general": [{"q": "What is the tallest mountain on Earth?", "a": "Mount Everest", "w": ["K2", "Denali", "Kilimanjaro"], "g": 9}]},
            "scenes": [{"id": "pk_shootout", "who": "friend", "title": "Shootout", "text": "{them_first} wants a rematch.",
                        "choices": [{"label": "Take the kicks.", "ops": [["minigame", "soccer_pk", {"great": [["mood", 4]], "miss": [["mood", -2]]}, {"base": 0.5}]]},
                                    {"label": "Pass.", "ops": []}]}]}
    r = dialogue.check(pack)
    assert r["ok"], r["errors"]
    assert dialogue.add_pack(pack)["ok"]
    assert any(q["q"].startswith("What is the tallest") for q in trivia.questions("general"))
    bad = dict(pack, name="Bad", scenes=[dict(pack["scenes"][0], id="pk_bad", choices=[{"label": "x", "ops": [["minigame", "lacrosse", {"great": []}, {"base": 0.5}]]}, {"label": "y", "ops": []}])])
    assert any("isn't a mini game" in e for e in dialogue.check(bad)["errors"])
