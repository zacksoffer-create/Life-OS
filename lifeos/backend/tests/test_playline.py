"""Play a storyline start to finish to see what's in it, and add a scene right where it goes: the chapters come one
after another on a copy of your story (your choices steer the branches; nothing counts in your real story), and the
prompt for a new scene carries the storyline's own words around the spot and exactly how to wire it in."""
import copy
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import dialogue, moments, scheduler  # noqa: E402
from tests.test_scheduler import BROTHER, TWINS, season_plan  # noqa: E402
from tests.test_story import spec  # noqa: E402

BRO_SCENES = ["bro_team_01_first_morning", "bro_team_02_lunch_table", "bro_team_05_tryouts", "bro_team_09_scrimmage",
              "brother_final_13_senior_night", "bro_team_17_last_school_game", "bro_graduation_day", "bro_college_call"]
BRO = "=== Brothers: Same Team\ncast: lead_brother = older brother, plays basketball, 3 years older, from the start\n\n" + "\n".join(
    f"--- {sid.replace('_', ' ')}  [{'sophomore' if sid == 'bro_college_call' else 'freshman'}] #{sid}\n{{lead_brother}} is here.\n"
    f"* Go for it  | remember {sid}_yes\n* Not today\n" for sid in BRO_SCENES)


@pytest.fixture(autouse=True)
def own_packs(tmp_path, monkeypatch):
    monkeypatch.setattr(dialogue, "USER_DIR", str(tmp_path / "dialogue"))
    dialogue.reload()
    yield
    dialogue.reload()


def _client():
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    for p in season_plan():
        if p["name"] != "Brothers: Same Team":
            dialogue.add_pack(copy.deepcopy(p))
    assert dialogue.add_script(BRO)["ok"]
    dialogue.reload()
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    assert c.post("/api/story/new", json={"spec": spec(per=6, siblings=[BROTHER] + TWINS)}).status_code == 200
    return c, api


def _pack(api, name):
    return next(p["id"] for p in dialogue.packs() if p["pack"].get("name") == name)


def _play_all(c, first, pick=0):
    """Every chapter in a row, choosing `pick` each time. The chapters played and the ones skipped (with why)."""
    r, played, skipped = first, [], []
    for _ in range(80):
        skipped += r.get("skipped", [])
        if r.get("done"):
            return played, skipped, r
        played.append(r["moment"]["kind"])
        out = c.post("/api/story/playline/choose", json={"index": pick}).json()
        assert out["lines"], "you see what happened"
        while out.get("moment"):  # the scene keeps going
            out = c.post("/api/story/playline/choose", json={"index": 0}).json()
        r = c.post("/api/story/playline/next").json()
    raise AssertionError("never finished")


def test_a_storyline_plays_start_to_finish_and_your_real_story_is_untouched():
    c, api = _client()
    w = api.lab.w
    day, done, pend = w.day, dict(scheduler.done_map(w)), [m["id"] for m in moments.pending(w)]
    bro = _pack(api, "Brothers: Same Team")
    r = c.post("/api/story/playline/start", json={"pack": bro}).json()
    assert r["chapter"] == 1 and r["of"] == len(r["chapters"]) == 8 and r["moment"]["storyline"].startswith("Brothers")
    assert "{" not in r["moment"]["title"] and "Mike" in r["moment"]["text"], "names filled in: it's about your brother"
    played, skipped, end = _play_all(c, r)
    assert len(played) == 8 and not skipped and end["path"][0]["picks"] == ["Go for it"]
    assert w.day == day and dict(scheduler.done_map(w)) == done and [m["id"] for m in moments.pending(w)] == pend


def test_your_choices_steer_the_branches_and_skipped_chapters_say_why():
    c, api = _client()
    hc = _pack(api, "Homecoming")
    played, skipped, _ = _play_all(c, c.post("/api/story/playline/start", json={"pack": hc}).json(), pick=1)  # go with b
    assert played == ["hc_ask", "hc_dance_b", "hc_after_b"], played
    why = {s["sid"]: s["why"] for s in skipped}
    assert "only if you chose “Go with a” in “hc ask”" in why["hc_dance_a"]
    assert "didn't happen on this path" in why["hc_after_a"]
    # from a chapter in the middle
    r = c.post("/api/story/playline/start", json={"pack": _pack(api, "Brothers: Same Team"), "from": "bro_team_05_tryouts"}).json()
    assert r["moment"]["kind"] == "bro_team_05_tryouts" and r["chapter"] == 3


BENCHED = """Sure, here's the scene:
```
--- Benched  [freshman]
{lead_brother} sits at the end of the bench all game.
* Ask him about it
    lead_brother: Not now.
* Leave it
```"""


def test_add_a_scene_right_here_prompt():
    c, api = _client()
    bro = _pack(api, "Brothers: Same Team")
    _play_all(c, c.post("/api/story/playline/start", json={"pack": bro}).json())
    r = c.get("/api/story/add/weave", params={"pack": bro, "after": "bro_team_02_lunch_table", "ask": "Mike gets benched and won't talk about it"}).json()
    p = r["prompt"]
    assert r["pack_name"] == "Brothers: Same Team" and r["next"] == "bro_team_05_tryouts"
    assert "Mike gets benched" in p and "right after scene 2" in p and "Mike Soffer" in p
    assert "--- bro team 02 lunch table  [freshman] #bro_team_02_lunch_table" in p, "the storyline's own script"
    assert "{lead_brother} is here." in p and "{lead_brother}" in p
    assert "“Go for it”" in p, "what you chose when you played it"
    assert "No `===` line" in p and "# LIFE OS story scripts" in p and "texts <pool>" not in p
    # ChatGPT's answer: just the scene. Previewed on a copy, then put in right after scene 2
    pv = c.post("/api/story/add/preview", json={"pack": bro, "after": "bro_team_02_lunch_table", "text": BENCHED}).json()
    assert pv["ok"], pv
    assert [x["title"] for x in pv["new"]] == ["Benched"] and pv["new"][0]["state"] == "played", pv["new"]
    assert bro in pv["replaces"] and "Benched" not in dialogue.script_of(bro), "nothing saved"
    fixed = c.post("/api/story/add/preview", json={"pack": bro, "after": "bro_team_02_lunch_table", "text": BENCHED.replace("* Leave it", "* Leave it | fnu +")}).json()
    assert fixed["ok"] and any("'fnu' read as 'fun'" in n for n in fixed["notes"]), fixed
    ins = c.post("/api/story/add/insert", json={"pack": bro, "after": "bro_team_02_lunch_table", "text": BENCHED})
    assert ins.status_code == 200, ins.text
    src = dialogue.script_of(bro)
    assert src.index("#bro_team_02_lunch_table") < src.index("--- Benched") < src.index("#bro_team_05_tryouts")


def test_a_scene_you_added_plays_right_where_it_goes():
    c, api = _client()
    bro = _pack(api, "Brothers: Same Team")
    assert c.post("/api/story/add/insert", json={"pack": bro, "after": "bro_team_02_lunch_table", "text": BENCHED}).status_code == 200
    benched = next(sc["id"] for sc in next(p for p in dialogue.packs() if p["id"] == bro)["pack"]["scenes"] if sc["title"] == "Benched")
    r = c.post("/api/story/playline/start", json={"pack": bro}).json()
    order = ["bro_team_01_first_morning", "bro_team_02_lunch_table", benched, "bro_team_05_tryouts"]
    assert [x["sid"] for x in r["chapters"]][:4] == order
    played, skipped, _ = _play_all(c, r)
    assert played[:4] == order and not skipped
    p = c.get("/api/story/add/weave", params={"pack": bro, "after": benched}).json()
    assert "Benched" in p["prompt"] and p["next"] == "bro_team_05_tryouts"
    # before the first scene, and the errors you'd see pasting nonsense
    assert c.post("/api/story/add/insert", json={"pack": bro, "after": "", "text": "--- Day zero  [freshman]\nIt starts.\n* Okay\n"}).status_code == 200
    assert dialogue.script_of(bro).index("--- Day zero") < dialogue.script_of(bro).index("#bro_team_01_first_morning")
    assert c.post("/api/story/add/insert", json={"pack": bro, "after": "", "text": "just words"}).status_code == 422


def test_let_it_happen_and_the_read_back():
    c, api = _client()
    r = c.post("/api/story/playline/start", json={"pack": _pack(api, "Brothers: Same Team")}).json()
    out = c.post("/api/story/playline/choose", json={"index": None}).json()  # your character decides
    assert out["read"]["title"] == r["moment"]["title"] and out["read"]["text"] == r["moment"]["text"]
    assert out["read"]["chose"] in ("Go for it", "Not today") and out["chapter_done"]
