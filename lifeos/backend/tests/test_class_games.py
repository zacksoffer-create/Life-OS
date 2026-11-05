"""Class games: quick challenges in class most school days. The data is sound, the rounds are fair and correct, and the
whole loop works: it shows up, you play it (or hand it off), it counts a little toward that class, skip-ahead plays it for you."""
import json
import os
import random
import re
import string
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import classgames  # noqa: E402
from lifeos.minigames import reg  # noqa: E402

FILL = {"period", "class_name", "teacher", "them_first"}


def _fields(s):
    return {f for _, f, _, _ in string.Formatter().parse(s) if f}


def test_setups_cover_every_class_and_only_use_known_names():
    games = reg()["games"]
    subjects = set()
    for g in json.load(open(os.path.join(os.path.dirname(__file__), "..", "data", "classes.json")))["grades"].values():
        for r in g:
            subjects |= {r["std"][1], r["hon"][1]}
    for s in classgames.D()["setups"]:
        assert s["game"] in games and games[s["game"]]["status"] == "ready", s["id"]
        assert s["game"] == "trivia" or games[s["game"]].get("class"), s["id"]
        for key in ("text", "great", "good", "miss"):
            assert s[key], (s["id"], key)
            for line in s[key]:
                assert _fields(line) <= FILL, (s["id"], line)
    for pool in ("pass_label", "sit_label", "pass", "sit"):
        for line in classgames.D()[pool]:
            assert _fields(line) <= FILL
    for subj in subjects | {"health", "art", "music", "tech", "psychology", "economics"}:
        assert len(classgames.setups_for(subj)) >= 2, f"{subj} needs at least two class games"


def test_lineup_banks_are_orderable_and_atoms_count_right():
    banks = classgames.D()["banks"]["lineup"]
    for key, b in banks.items():
        for items in b.get("sets") or ([b["items"]] if "items" in b else []):
            vals = [x[1] for x in items]
            assert len(set(vals)) == len(vals), key
    assert classgames.atoms_in("H2O") == 3
    assert classgames.atoms_in("C6H12O6") == 24
    assert classgames.atoms_in("C2H5OH") == 9
    assert classgames.atoms_in("NaHCO3") == 6
    for a, b in classgames.D()["banks"]["oddone"]["spanish"]["pairs"]:
        assert a != b and len(a) == len(b)


class _C:
    def __init__(self, grade):
        self.grade = grade


def _eval(q):
    q = q.replace("−", "-").replace("×", "*").replace("÷", "//")
    m = re.match(r"^(\d+)% of (\d+)$", q)
    if m:
        return int(m.group(1)) * int(m.group(2)) // 100
    m = re.match(r"^(\d+)²$", q)
    if m:
        return int(m.group(1)) ** 2
    return eval(q)  # only digits and + - * // from the generator


def test_rounds_are_correct_for_every_game():
    for seed in range(40):
        for grade, diff in ((9, 45), (12, 57), (15, 66)):
            c = _C(grade)
            ctx = {"subject": "math"}
            r = classgames.round_for(None, c, "mathdash", ctx, seed, diff, 50)
            assert len(r["problems"]) == 5
            for p in r["problems"]:
                assert len(p["choices"]) == 3 and len(set(p["choices"])) == 3
                assert int(p["choices"][p["answer"]]) == _eval(p["q"]), p
            r = classgames.round_for(None, c, "mathdash", {"cg_skin": "money"}, seed, diff, 50)
            for p in r["problems"]:
                assert len(set(p["choices"])) == 3 and all(x.startswith("$") for x in p["choices"])
            for skin, subject in (("history", "us_history"), ("history", "government"), ("chemistry", "chemistry"), ("english", "english"),
                                  ("spanish", "spanish"), ("tech", "tech"), ("math", "math"), ("art", "art"), ("biology", "biology"),
                                  ("physics", "physics"), ("music", "music")):
                r = classgames.round_for(None, c, "lineup", {"cg_skin": skin, "subject": subject}, seed, diff, 50)
                for rd in r["rounds"]:
                    vals = [rd["items"][i]["value"] for i in rd["order"]]
                    assert vals == sorted(vals), (skin, rd)
                    assert sorted(rd["order"]) == list(range(len(rd["items"])))
            for skin in ("english", "spanish", "dna", "color", "general"):
                r = classgames.round_for(None, c, "oddone", {"cg_skin": skin}, seed, diff, 50)
                for rd in r["rounds"]:
                    odd = rd["tiles"][rd["odd"]]
                    others = [t for i, t in enumerate(rd["tiles"]) if i != rd["odd"]]
                    assert len(set(others)) == 1 and odd != others[0]
            r = classgames.round_for(None, c, "hold", {}, seed, diff, 50)
            assert all(0.45 <= t["center"] <= 0.85 and t["center"] + t["hw"] < 1 and t["T"] >= 1.2 for t in r["tries"])
            r = classgames.round_for(None, c, "flash", {}, seed, diff, 50)
            assert len(r["rounds"][1]) == len(r["rounds"][0]) + 1 and all(0 <= t < 9 for s in r["rounds"] for t in s)
            r = classgames.round_for(None, c, "reflex", {}, seed, diff, 50)
            assert r["great_ms"] < r["ok_ms"] and len(r["tries"]) == 3
    # the pendulum stops at the bottom
    assert all(t["center"] == 0.5 for t in classgames.round_for(None, _C(10), "sweep", {"cg_skin": "pendulum"}, 3, 50, 50)["tries"])


def _story():
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    from tests.test_story import spec
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    assert c.post("/api/story/new", json={"spec": spec(per=6)}).status_code == 200
    return c, api


def test_class_games_show_up_play_and_count():
    c, api = _story()
    played = handed = 0
    kinds = set()
    for _ in range(120):
        st = c.get("/api/phone/state").json()
        for m in st["moments"]:
            if m["kind"] != "class_game":
                c.post(f"/api/phone/moment/{m['id']}", json={"index": None})
                continue
            kinds.add(m["ctx"]["cg_game"])
            assert len(m["choices"]) == 3 and m["choices"][0].get("game") and not m["choices"][1].get("game")
            assert m["ctx"]["class_name"] and m["ctx"]["period"]
            assert "{" not in m["text"] and "{" not in m["title"]
            if played <= handed:
                r = c.post(f"/api/phone/moment/{m['id']}", json={"index": 0}).json()
                cfg = r["minigame"]
                assert cfg["mode"] == "class" and cfg["subject"] == m["ctx"]["class_name"]
                assert cfg.get("round") or cfg.get("questions")
                r = c.post(f"/api/phone/moment/{m['id']}", json={"index": 0, "session": cfg["session"], "score": 6, "max": 6}).json()
                assert r["minigame"]["tier"] == "great"
                assert any("went for it" in l["text"] for l in r["lines"])
                played += 1
            else:
                r = c.post(f"/api/phone/moment/{m['id']}", json={"index": 1}).json()
                assert any("take it" in l["text"] for l in r["lines"])
                handed += 1
        c.post("/api/story/advance", json={"until": "decision"})
    assert played >= 3 and handed >= 2, (played, handed)
    assert len(kinds) >= 3
    rows = c.get("/api/phone/classes").json()["classes"]
    assert sum(r["games"] for r in rows) == played and sum(r["games_won"] for r in rows) == played
    w = api.lab.w
    assert w.meta["class_games"]["played"] == played
    # never an episode, never on a quiz day
    assert not any(e["kind"] == "class_game" for e in w.meta.get("episodes", []))
    days = {}
    for m in w.meta["moments"]:
        days.setdefault(m["day"], set()).add(m["kind"])
    assert not any({"class_quiz", "class_game"} <= k for k in days.values())


def test_skip_ahead_plays_class_games_for_you_and_the_toggle_turns_them_off():
    c, api = _story()
    import time
    for _ in range(3):
        j = c.post("/api/story/advance", json={"until": "week"}).json()
        while j.get("status") == "running":
            time.sleep(0.2)
            j = c.get("/api/sim/job").json()
        for m in c.get("/api/phone/state").json()["moments"]:
            assert m["kind"] != "class_game", "a skip-ahead shouldn't stop for a class game"
            c.post(f"/api/phone/moment/{m['id']}", json={"index": None})
    w = api.lab.w
    auto = [m for m in w.meta["moments"] if m["kind"] == "class_game"]
    assert auto and all(m["status"] == "resolved" and m["by"] == "auto" for m in auto)
    assert c.post("/api/story/control", json={"class_games": False}).json()["class_games"] is False
    before = len([m for m in w.meta["moments"] if m["kind"] == "class_game"])
    for _ in range(25):
        c.post("/api/story/advance", json={"until": "decision"})
        for m in c.get("/api/phone/state").json()["moments"]:
            c.post(f"/api/phone/moment/{m['id']}", json={"index": None})
    assert len([m for m in w.meta["moments"] if m["kind"] == "class_game"]) == before


def test_packs_can_use_class_games_in_their_scenes():
    from lifeos import dialogue
    guide = dialogue.guide_markdown()
    for g in ("hold", "sweep", "mathdash", "flash", "oddone", "lineup", "reflex"):
        assert f"`{g}`" in guide
